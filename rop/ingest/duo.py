"""Data Use Ontology (DUO) ingest.

DUO is distributed via github.com/EBISPOT/DUO under CC-BY-4.0. It's the
smallest source in RoP (~30 terms) but anchors Theme 9 governance: the
DUO consent class enum that gates whether a cohort can be re-shared,
combined, or used for specific analyses.

Download instructions:
    git clone --depth 1 https://github.com/EBISPOT/DUO.git data/sources/duo
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
    parse_obo,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)

DUO_REPO_URL = "https://github.com/EBISPOT/DUO.git"


def find_duo_obo(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    duo_dir = Path(sources_dir) / "duo"
    candidates = list(duo_dir.rglob("duo.owl")) + list(duo_dir.rglob("duo.obo"))
    obo_only = [c for c in candidates if c.suffix == ".obo"]
    if obo_only:
        return obo_only[0]
    if candidates:
        # If only OWL is present, document the limitation
        raise FileNotFoundError(
            f"DUO ships as OWL in {duo_dir}; this parser expects OBO. "
            "Convert via robot or use Athena's DUO mirror."
        )
    raise FileNotFoundError(
        f"DUO not found in {duo_dir}. Run: git clone --depth 1 {DUO_REPO_URL} {duo_dir}"
    )


def download_duo(sources_dir: Path = DEFAULT_SOURCES_DIR):
    return git_clone(DUO_REPO_URL, Path(sources_dir) / "duo")


def ingest_duo(
    obo_path: Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield one RoPElement per DUO term.

    DUO terms become Theme 9 governance value-set members (e.g.,
    DUO:0000004 'no restriction', DUO:0000007 'disease specific research').
    """
    obo_path = obo_path or find_duo_obo(sources_dir)
    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"DUO-{retrieved_date.isoformat()}"

    for term in parse_obo(obo_path):
        if term.get("is_obsolete") == "true":
            continue
        duo_id = term.get("id", "").strip()
        if not duo_id.startswith("DUO:"):
            continue
        name = term.get("name", "").strip()
        if not name:
            continue

        synonyms = obo_extract_synonyms(term)
        defn = obo_extract_definition(term) or name

        try:
            yield RoPElement(
                item=name[:255],
                description=defn,
                item_type=ItemType.ENUM,
                source_authority=SourceAuthority.DUO,
                source_code=duo_id,
                source_version=source_version,
                source_url=f"http://purl.obolibrary.org/obo/{duo_id.replace(':', '_')}",
                source_retrieved_date=retrieved_date,
                alternate_names=normalize_pipe_delimited(*synonyms),
                collection="RoP-Core-Governance",
                curation_status=CurationStatus.AUTO_MATCHED,
            )
        except Exception as exc:
            logger.warning("Skipped DUO term %s: %s", duo_id, exc)
            continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="DUO")
    t0 = time.time()
    for _ in ingest_duo(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
