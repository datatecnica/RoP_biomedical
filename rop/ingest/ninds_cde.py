"""NINDS Common Data Elements (NINDS-CDE) ingest.

NINDS-CDE bulk export is downloaded from
https://www.commondataelements.ninds.nih.gov/ — the catalog supports a
"Show All / Export All" option that produces a single CSV containing every
CDE across all disease areas (~45K rows as of 2026-05).

The CSV ships with a UTF-8 BOM and 27 columns including built-in
cross-references (External Id Loinc, Snomed, caDSR, CDISC). These xrefs
are gold for the cross-source annotate pass — NINDS-CDE rows arrive
pre-mapped to LOINC and SNOMED concepts.

For RoP, NINDS-CDE contributes:
- Theme 8 (Clinical Instruments) — neurological assessment instruments
- Theme 12 (Clinical Concepts) — clinical findings, observations
- Theme 4 (Ancestry & Pedigree) — demographic CDEs

Same CDE ID can appear multiple times in the export with different
Classification, Population, or CRF Module values (NINDS-CDEs are reused
across studies). The parser yields one RoPElement per row; the dedup
pass during merge collapses to canonical rows with unioned metadata.

Download instructions:
1. Visit https://www.commondataelements.ninds.nih.gov/cde-catalog
2. Use the catalog's bulk export to download all CDEs as CSV
3. Place at data/sources/ninds_cde/cde-details_*.csv
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
    normalize_pipe_delimited,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)


# NINDS Data Type → RoP item_type. Real values seen in the export:
# "Numeric Values", "Alphanumeric", "Date or Date & Time", "Date", "Time"
NINDS_TYPE_TO_ITEMTYPE: dict[str, ItemType] = {
    "numeric values": ItemType.NUMERIC,
    "numeric": ItemType.NUMERIC,
    "number": ItemType.NUMERIC,
    "integer": ItemType.NUMERIC,
    "alphanumeric": ItemType.STRING,
    "text": ItemType.STRING,
    "string": ItemType.STRING,
    "date": ItemType.DATE,
    "date or date & time": ItemType.DATE,
    "date & time": ItemType.DATE,
    "time": ItemType.STRING,
}


def find_ninds_csvs(sources_dir: Path = DEFAULT_SOURCES_DIR) -> list[Path]:
    """Return all NINDS-CDE CSV files in the staging directory."""
    ninds_dir = Path(sources_dir) / "ninds_cde"
    csvs = sorted(ninds_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(
            f"No NINDS-CDE CSV found in {ninds_dir}. Download bulk catalog "
            "export from https://www.commondataelements.ninds.nih.gov/cde-catalog"
        )
    return csvs


def _strip_bom(s: str) -> str:
    """Strip UTF-8 BOM from a string (NINDS CSV header has \ufeff prefix)."""
    return s.lstrip("\ufeff")


def _col(row: dict, *names: str) -> str:
    """Tolerant column lookup with BOM-stripped key matching."""
    for n in names:
        for k in (n, n.lower(), n.upper(), _strip_bom(n)):
            if k in row and row[k] is not None:
                return str(row[k]).strip()
        # Also try matching against BOM-stripped row keys
        for raw_key in row:
            if _strip_bom(raw_key) == n and row[raw_key] is not None:
                return str(row[raw_key]).strip()
    return ""


def _parse_xref(vocab: str, raw: str) -> list[str]:
    """Split semicolon/comma-delimited xref values; emit normalized 'VOCAB:CODE'."""
    if not raw or raw.strip() in ("", "-", "N/A", "n/a", "None"):
        return []
    out = []
    for token in raw.replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            out.append(token)
        else:
            out.append(f"{vocab}:{token}")
    return out


def ingest_ninds_cde(
    csv_paths: list[Path] | Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield RoPElement per row in the NINDS-CDE bulk CSV(s).

    Captures (when populated):
      - source_code = CDE ID (e.g., 'C00001')
      - item        = Variable Name (or CDE Name fallback)
      - description = Definition (or Short Description fallback)
      - values      = Permissible Values + PV Descriptions, normalized to pipe
      - unit_of_measure = Measurement Type (free-text, e.g. 'week', 'mg/dL')
      - plausible_min/max = Min Value / Max Value
      - cardinality, item_type per Data Type
      - metadata_:
          ninds_cde_id, ninds_classification, ninds_version, ninds_population,
          ninds_crf_module, ninds_subdomain, ninds_domain, ninds_question_text,
          ninds_xrefs (list of LOINC/SNOMED/caDSR/CDISC cross-references)
    """
    if csv_paths is None:
        csv_paths = find_ninds_csvs(sources_dir)
    elif isinstance(csv_paths, (str, Path)):
        csv_paths = [Path(csv_paths)]
    else:
        csv_paths = [Path(p) for p in csv_paths]

    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"NINDS-CDE-{retrieved_date.isoformat()}"

    for csv_path in csv_paths:
        logger.debug("Parsing NINDS-CDE CSV: %s", csv_path)
        # utf-8-sig handles the BOM that the NINDS export ships with
        with Path(csv_path).open(encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)

            for row in reader:
                cde_id = _col(row, "CDE ID", "CDE_ID")
                if not cde_id:
                    continue

                # NINDS export occasionally has malformed rows where the CDE ID
                # column contains long descriptive text (e.g., classification
                # descriptions or citation paragraphs). Real CDE IDs are
                # always short (e.g., 'C00001', 'C12345'). Skip rows where
                # the value is too long to be a real ID.
                if len(cde_id) > 40:
                    logger.debug("Skipping NINDS row — CDE ID looks malformed: %s",
                                 cde_id[:60])
                    continue

                cde_name = _col(row, "CDE Name", "CDE_Name")
                variable_name = _col(row, "Variable Name", "VariableName")
                definition = _col(row, "Definition")
                short_desc = _col(row, "Short Description")
                question_text = _col(row, "Question Text")
                permissible = _col(row, "Permissible Values")
                pv_desc = _col(row, "PV Descriptions")
                data_type = _col(row, "Data Type").lower()
                population = _col(row, "Population")
                classification = _col(row, "Classification (e.g., Core)",
                                      "Classification")
                version_number = _col(row, "Version Number")
                crf_module = _col(row, "CRF Module / Guideline",
                                  "CRF Module/Guideline", "CRF Module")
                subdomain = _col(row, "Subdomain Name", "Sub-Domain", "Subdomain")
                domain = _col(row, "Domain Name", "Domain")
                min_value = _col(row, "Min Value")
                max_value = _col(row, "Max Value")
                measurement_type_raw = _col(row, "Measurement Type") or ""
                # Measurement Type column sometimes contains citation text
                # instead of actual units. Drop if it's longer than the field
                # max (64 chars) — real units are short ('week', 'mg/dL', etc.)
                if len(measurement_type_raw) > 64:
                    measurement_type = None
                else:
                    measurement_type = measurement_type_raw or None
                ext_loinc = _col(row, "External Id Loinc", "External Id LOINC")
                ext_snomed = _col(row, "External Id Snomed", "External Id SNOMED")
                ext_cadsr = _col(row, "External Id caDSR", "External Id CaDSR")
                ext_cdisc = _col(row, "External Id CDISC")

                item = variable_name or cde_name
                description = definition or short_desc or cde_name
                if not item or not description:
                    continue

                item_type = NINDS_TYPE_TO_ITEMTYPE.get(data_type)

                plausible_min = None
                plausible_max = None
                if item_type is ItemType.NUMERIC:
                    try:
                        plausible_min = float(min_value) if min_value else None
                        plausible_max = float(max_value) if max_value else None
                        if (plausible_min is not None and plausible_max is not None
                                and plausible_min > plausible_max):
                            plausible_min, plausible_max = None, None
                    except ValueError:
                        plausible_min = plausible_max = None

                values_field = None
                if permissible:
                    if pv_desc:
                        values_field = f"{permissible} | {pv_desc}"
                    else:
                        values_field = permissible
                    values_field = values_field.replace(";", "|").strip()

                # Cross-references — built into NINDS export, gold for annotate pass
                xrefs: list[str] = []
                xrefs.extend(_parse_xref("LOINC", ext_loinc))
                xrefs.extend(_parse_xref("SNOMED", ext_snomed))
                xrefs.extend(_parse_xref("caDSR", ext_cadsr))
                xrefs.extend(_parse_xref("CDISC", ext_cdisc))

                metadata = {
                    "ninds_cde_id": cde_id,
                    "ninds_classification": classification or None,
                    "ninds_version": version_number or None,
                    "ninds_population": population or None,
                    "ninds_crf_module": crf_module or None,
                    "ninds_subdomain": subdomain or None,
                    "ninds_domain": domain or None,
                    "ninds_question_text": question_text or None,
                    "ninds_xrefs": xrefs if xrefs else None,
                }
                metadata = {k: v for k, v in metadata.items() if v}

                collections = []
                if domain:
                    collections.append(f"NINDS-{domain}")
                if subdomain and subdomain != domain:
                    parent = f"NINDS-{domain}" if domain else "NINDS"
                    collections.append(f"{parent}-{subdomain}")

                try:
                    yield RoPElement(
                        item=item[:255],
                        description=description[:8000],
                        item_type=item_type,
                        values=values_field,
                        source_authority=SourceAuthority.NINDS_CDE,
                        source_code=cde_id,
                        source_version=source_version,
                        source_url="https://www.commondataelements.ninds.nih.gov/",
                        source_retrieved_date=retrieved_date,
                        unit_of_measure=measurement_type,
                        unit_vocabulary="free-text" if measurement_type else None,
                        plausible_min=plausible_min,
                        plausible_max=plausible_max,
                        member_of_collections=collections,
                        metadata_=metadata,
                        curation_status=CurationStatus.AUTO_MATCHED,
                    )
                except Exception as exc:
                    logger.warning("Skipped NINDS-CDE %s: %s", cde_id, exc)
                    continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="NINDS-CDE")
    t0 = time.time()
    for _ in ingest_ninds_cde(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
