"""Mondo Disease Ontology ingest.

Mondo is distributed via github.com/monarch-initiative/mondo under CC-BY-4.0.
The release artifact is mondo.obo. Mondo carries the highest-quality
cross-reference graph between OMIM, Orphanet, DOID, ICD-10/11, MeSH, and SNOMED
for disease concepts; it's the canonical bridge for rare-disease equivalence
in RoP.

For RoP, Mondo contributes to:
- Theme 12 (Clinical Concepts) — diagnoses
- Theme 4 (Ancestry & Pedigree) — disease status references

Download instructions:
    git clone --depth 1 https://github.com/monarch-initiative/mondo.git \\
        data/sources/mondo
"""
from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Iterator

from rop.ingest._common import (
    DEFAULT_SOURCES_DIR,
    IngestStats,
    git_clone,
    normalize_pipe_delimited,
    obo_extract_definition,
    obo_extract_synonyms,
    obo_extract_xrefs,
    parse_obo,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)

MONDO_REPO_URL = "https://github.com/monarch-initiative/mondo.git"


def find_mondo_obo(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    mondo_dir = Path(sources_dir) / "mondo"
    candidates = (
        list(mondo_dir.rglob("mondo.obo")) +
        list(mondo_dir.rglob("mondo-base.obo")) +
        list(mondo_dir.rglob("mondo-edit.obo"))
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        f"mondo.obo not found in {mondo_dir}. Run: git clone --depth 1 "
        f"{MONDO_REPO_URL} {mondo_dir}"
    )


def download_mondo(sources_dir: Path = DEFAULT_SOURCES_DIR):
    return git_clone(MONDO_REPO_URL, Path(sources_dir) / "mondo")


def ingest_mondo(
    obo_path: Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield RoPElement per non-obsolete Mondo term.

    Mondo xrefs (to OMIM, ICD10, MESH, SNOMED, Orphanet) are captured in
    metadata_['mondo_xrefs'] for downstream cross-vocab annotation.
    """
    obo_path = obo_path or find_mondo_obo(sources_dir)
    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"Mondo-{retrieved_date.isoformat()}"

    for term in parse_obo(obo_path):
        if term.get("is_obsolete") == "true":
            continue
        mondo_id = term.get("id", "").strip()
        if not mondo_id.startswith("MONDO:"):
            continue
        name = term.get("name", "").strip()
        if not name:
            continue

        synonyms = obo_extract_synonyms(term)
        xrefs = obo_extract_xrefs(term)
        defn = obo_extract_definition(term) or name

        metadata = {"mondo_xrefs": xrefs} if xrefs else None

        try:
            yield RoPElement(
                item=name[:255],
                description=defn,
                item_type=ItemType.ENUM,
                source_authority=SourceAuthority.MONDO,
                source_code=mondo_id,
                source_version=source_version,
                source_url=f"https://monarchinitiative.org/disease/{mondo_id}",
                source_retrieved_date=retrieved_date,
                alternate_names=normalize_pipe_delimited(*synonyms),
                metadata_=metadata,
                curation_status=CurationStatus.AUTO_MATCHED,
            )
        except Exception as exc:
            logger.warning("Skipped Mondo term %s: %s", mondo_id, exc)
            continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="Mondo")
    t0 = time.time()
    for _ in ingest_mondo(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
