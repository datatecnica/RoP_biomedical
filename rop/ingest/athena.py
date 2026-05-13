"""OHDSI Athena vocabulary ingest.

Athena (https://athena.ohdsi.org) is the canonical distribution of the OMOP
vocabulary. After free registration users select desired source vocabularies
(LOINC, SNOMED, MedDRA, RxNorm, ICD-10, ICD-10-CM, OMIM, UCUM, etc.) and
download a ZIP containing CSV files in OMOP CDM table format.

For RoP this is the load-bearing ingest: every commercial-licensed vocabulary
(SNOMED, MedDRA, OMIM) reaches RoP exclusively via Athena, never as a direct
source-authority download. License hygiene sits with OHDSI Foundation, not
DataTecnica.

Files we use:
    CONCEPT.csv               — one row per concept across all vocabularies
    CONCEPT_RELATIONSHIP.csv  — equivalence/mapping edges between concepts
    CONCEPT_SYNONYM.csv       — alternate names per concept
    VOCABULARY.csv            — vocabulary metadata (version per source)

Download instructions:
1. Register at https://athena.ohdsi.org
2. Click "Download" → select vocabularies
3. Receive download link by email; download ZIP to data/sources/athena/
4. Extract; the CSVs land in data/sources/athena/<release>/
"""
from __future__ import annotations

import csv
import logging
import time
from datetime import date
from pathlib import Path
from typing import Iterator

from rop.ingest._common import (
    DEFAULT_SOURCES_DIR,
    IngestStats,
    extract_archive,
    normalize_pipe_delimited,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)


# OMOP concept's domain_id → recommended RoPElement.item_type
# This is a coarse mapping; some concepts may need refinement post-ingest.
OMOP_DOMAIN_TO_ITEMTYPE: dict[str, ItemType] = {
    "Measurement": ItemType.NUMERIC,
    "Observation": ItemType.STRING,
    "Condition": ItemType.ENUM,
    "Drug": ItemType.ENUM,
    "Procedure": ItemType.ENUM,
    "Device": ItemType.STRING,
    "Unit": ItemType.STRING,
    "Specimen": ItemType.ENUM,
}


def _sniff_delimiter(csv_path: Path, sample_bytes: int = 8192) -> str:
    """Detect whether an Athena CSV uses tab or comma as field delimiter.

    Older Athena releases ship tab-delimited CSVs (despite the .csv
    extension). Newer releases (post-2025) ship comma-delimited.
    Sniffing the header row is reliable: VOCABULARY/CONCEPT files always
    start with a known column name followed by the delimiter.
    """
    with csv_path.open(encoding="utf-8", errors="replace") as f:
        sample = f.read(sample_bytes)
    # Look for the delimiter in the first line (the header)
    first_line = sample.split("\n", 1)[0] if sample else ""
    tab_count = first_line.count("\t")
    comma_count = first_line.count(",")
    if tab_count >= 1 and tab_count >= comma_count:
        return "\t"
    return ","


def find_athena_dir(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    """Locate the directory containing CONCEPT.csv. Extracts ZIP if needed."""
    athena_root = Path(sources_dir) / "athena"
    csv_candidates = list(athena_root.rglob("CONCEPT.csv"))
    if csv_candidates:
        return csv_candidates[0].parent

    zips = list(athena_root.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"No Athena ZIP or CONCEPT.csv found in {athena_root}. "
            "Register at https://athena.ohdsi.org and place the download here."
        )
    extracted = extract_archive(zips[0], athena_root / "extracted")
    csv_candidates = list(extracted.rglob("CONCEPT.csv"))
    if not csv_candidates:
        raise FileNotFoundError(f"CONCEPT.csv not found in {zips[0]}")
    return csv_candidates[0].parent


def _read_vocabularies(athena_dir: Path) -> dict[str, str]:
    """Return {vocabulary_id: vocabulary_version} from VOCABULARY.csv."""
    vocab_csv = athena_dir / "VOCABULARY.csv"
    out: dict[str, str] = {}
    if not vocab_csv.exists():
        return out
    delim = _sniff_delimiter(vocab_csv)
    with vocab_csv.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            vid = (row.get("vocabulary_id") or "").strip()
            ver = (row.get("vocabulary_version") or "").strip()
            if vid:
                out[vid] = ver or "unknown"
    return out


def _read_synonyms(athena_dir: Path) -> dict[int, list[str]]:
    """Return {concept_id: [synonym, …]} from CONCEPT_SYNONYM.csv."""
    syn_csv = athena_dir / "CONCEPT_SYNONYM.csv"
    out: dict[int, list[str]] = {}
    if not syn_csv.exists():
        return out
    delim = _sniff_delimiter(syn_csv)
    with syn_csv.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            try:
                cid = int(row["concept_id"])
            except (KeyError, ValueError, TypeError):
                continue
            syn = (row.get("concept_synonym_name") or "").strip()
            if syn:
                out.setdefault(cid, []).append(syn)
    return out


# OMOP relationship_ids that decompose LOINC into its six axes. These are
# the canonical strings used in CONCEPT_RELATIONSHIP for LOINC concepts;
# see the OHDSI Vocabulary v5.0 wiki LOINC page for documentation.
LOINC_AXIS_RELATIONSHIPS: dict[str, str] = {
    "Has component":   "axis_component",
    "Has property":    "axis_property",
    "Has time aspect": "axis_time",
    "Has system":      "axis_system",
    "Has scale type":  "axis_scale",
    "Has method type": "axis_method",
}


def _build_loinc_six_axis_map(athena_dir: Path) -> dict[int, dict[str, str]]:
    """Build {loinc_concept_id: {axis_component, axis_property, ...}}.

    Streams CONCEPT.csv to learn LOINC Part concept names, then streams
    CONCEPT_RELATIONSHIP.csv to find each LOINC concept's six-axis links,
    then resolves the Part concept_ids to their names.

    Memory cost is O(num_LOINC_Part_concepts) ≈ ~50K × ~80 bytes ≈ 4 MB
    plus the output map (~200K LOINC concepts × 6 axes × ~50 bytes ≈
    60 MB). No DuckDB or pandas dependency; pure streaming.

    Returns empty dict if either CSV is absent (graceful degradation —
    LOINC concepts still ingest, just without six-axis enrichment).
    """
    concept_csv = athena_dir / "CONCEPT.csv"
    rel_csv = athena_dir / "CONCEPT_RELATIONSHIP.csv"
    if not concept_csv.exists() or not rel_csv.exists():
        logger.info("Six-axis recovery skipped — CONCEPT_RELATIONSHIP.csv "
                    "not present in %s", athena_dir)
        return {}

    # Pass 1: collect concept_id -> name for ALL LOINC concepts
    # (both the LOINC observable concepts and the LOINC Part concepts they
    # link to via six-axis relationships)
    loinc_names: dict[int, str] = {}
    concept_delim = _sniff_delimiter(concept_csv)
    # Increase CSV field size limit for large concept names (some reach 500KB)
    csv.field_size_limit(10 * 1024 * 1024)  # 10 MB limit
    with concept_csv.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=concept_delim)
        for row in reader:
            if (row.get("vocabulary_id") or "").strip() != "LOINC":
                continue
            try:
                cid = int(row["concept_id"])
            except (KeyError, ValueError, TypeError):
                continue
            name = (row.get("concept_name") or "").strip()
            if name:
                loinc_names[cid] = name
    logger.info("Six-axis recovery: %d LOINC concepts loaded", len(loinc_names))

    # Pass 2: walk CONCEPT_RELATIONSHIP for the six axis relationships
    six_axis: dict[int, dict[str, str]] = {}
    rel_rows = 0
    rel_delim = _sniff_delimiter(rel_csv)
    with rel_csv.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=rel_delim)
        for row in reader:
            relationship_id = (row.get("relationship_id") or "").strip()
            axis_field = LOINC_AXIS_RELATIONSHIPS.get(relationship_id)
            if not axis_field:
                continue
            if (row.get("invalid_reason") or "").strip():
                continue
            try:
                cid_1 = int(row["concept_id_1"])
                cid_2 = int(row["concept_id_2"])
            except (KeyError, ValueError, TypeError):
                continue
            if cid_1 not in loinc_names:
                continue
            part_name = loinc_names.get(cid_2)
            if not part_name:
                continue
            six_axis.setdefault(cid_1, {})[axis_field] = part_name
            rel_rows += 1
    logger.info("Six-axis recovery: %d axis edges resolved across %d LOINC "
                "concepts", rel_rows, len(six_axis))
    return six_axis


def ingest_athena(
    athena_dir: Path | None = None,
    *,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
    standard_only: bool = True,
    skip_loinc: bool = False,
) -> Iterator[RoPElement]:
    """Yield RoPElement per Athena concept.

    Parameters
    ----------
    standard_only : bool
        If True, only emit concepts where standard_concept='S' (canonical).
        Non-standard concepts are still represented via CONCEPT_RELATIONSHIP
        but don't get their own RoP row.
    skip_loinc : bool
        Default False. Athena's LOINC content is the primary LOINC ingest
        path for v2026.04. Set True only if running Athena alongside a
        separate direct LOINC ingest (advanced; the dedup pass handles
        overlap, but skipping avoids the redundant rows entirely).
    """
    athena_dir = Path(athena_dir) if athena_dir else find_athena_dir(sources_dir)
    retrieved_date = retrieved_date or date.today()

    vocab_versions = _read_vocabularies(athena_dir)
    synonyms = _read_synonyms(athena_dir)
    # Six-axis recovery — only worth running if we're emitting LOINC rows
    six_axis_map: dict[int, dict[str, str]] = {}
    if not skip_loinc:
        six_axis_map = _build_loinc_six_axis_map(athena_dir)
    logger.info("Athena: %d vocabularies, %d concepts have synonyms, "
                "%d LOINC concepts have six-axis enrichment",
                len(vocab_versions), len(synonyms), len(six_axis_map))

    concept_csv = athena_dir / "CONCEPT.csv"
    main_delim = _sniff_delimiter(concept_csv)
    logger.info("CONCEPT.csv detected delimiter: %s",
                "tab" if main_delim == "\t" else "comma")
    # Increase CSV field size limit for large concept names
    csv.field_size_limit(10 * 1024 * 1024)  # 10 MB limit
    with concept_csv.open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=main_delim)
        for row in reader:
            try:
                concept_id = int(row["concept_id"])
            except (KeyError, ValueError, TypeError):
                continue

            if standard_only and (row.get("standard_concept") or "").strip() != "S":
                continue

            vocab_id = (row.get("vocabulary_id") or "").strip()
            if not vocab_id:
                continue
            if skip_loinc and vocab_id == "LOINC":
                continue

            concept_name = (row.get("concept_name") or "").strip()
            concept_code = (row.get("concept_code") or "").strip()
            domain = (row.get("domain_id") or "").strip()
            if not concept_name:
                continue

            item_type = OMOP_DOMAIN_TO_ITEMTYPE.get(domain)
            alt_names = normalize_pipe_delimited(*synonyms.get(concept_id, []))

            metadata = {
                "omop_concept_id": concept_id,
                "omop_domain_id": domain or None,
                "omop_concept_class_id": (row.get("concept_class_id") or "").strip() or None,
                "omop_standard_concept": (row.get("standard_concept") or "").strip() or None,
                "omop_vocabulary_id": vocab_id,
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}

            # LOINC six-axis enrichment from CONCEPT_RELATIONSHIP
            if vocab_id == "LOINC" and concept_id in six_axis_map:
                metadata.update(six_axis_map[concept_id])

            try:
                yield RoPElement(
                    item=concept_name[:255],
                    description=concept_name,
                    item_type=item_type,
                    source_authority=SourceAuthority.OMOP,
                    source_code=concept_code or str(concept_id),
                    source_version=f"Athena-{vocab_id}-{vocab_versions.get(vocab_id, 'unknown')}",
                    source_url=f"https://athena.ohdsi.org/search-terms/terms/{concept_id}",
                    source_retrieved_date=retrieved_date,
                    alternate_names=alt_names,
                    canonical_concept_id=concept_id,
                    metadata_=metadata,
                    curation_status=CurationStatus.AUTO_MATCHED,
                )
            except Exception as exc:
                logger.warning("Skipped OMOP concept %s: %s", concept_id, exc)
                continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="Athena/OMOP")
    t0 = time.time()
    for _ in ingest_athena(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
