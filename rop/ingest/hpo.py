"""Human Phenotype Ontology (HPO) ingest.

HPO is distributed via github.com/obophenotype/human-phenotype-ontology under
CC-BY-4.0. The release artifact is hp.obo (or hp.json); we use the OBO format
because the parsing is straightforward and well-defined.

For RoP, HPO contributes to:
- Theme 12 (Clinical Concepts) — clinical findings, phenotypes
- Theme 4 (Ancestry & Pedigree) — when phenotypes are recorded for pedigree
  members (the actual phenotype data lives in clinical themes; HPO codes
  resolve those clinical concepts)

Download instructions:
    git clone --depth 1 https://github.com/obophenotype/human-phenotype-ontology \\
        data/sources/hpo
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

HPO_REPO_URL = "https://github.com/obophenotype/human-phenotype-ontology.git"


def find_hpo_obo(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    """Locate hp.obo in the staging directory."""
    hpo_dir = Path(sources_dir) / "hpo"
    candidates = list(hpo_dir.rglob("hp.obo")) + list(hpo_dir.rglob("hp-base.obo"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        f"hp.obo not found in {hpo_dir}. Run: git clone --depth 1 "
        f"{HPO_REPO_URL} {hpo_dir}"
    )


def download_hpo(sources_dir: Path = DEFAULT_SOURCES_DIR):
    """Convenience: shallow-clone HPO if not already present."""
    return git_clone(HPO_REPO_URL, Path(sources_dir) / "hpo")


def ingest_hpo(
    obo_path: Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield one RoPElement per non-obsolete HPO term.

    Each emitted element has:
        item              = HPO term name
        description       = HPO definition (or term name if no def)
        source_code       = HP:NNNNNNN
        source_authority  = HPO
        alternate_names   = pipe-joined synonyms
        metadata_         = {hpo_xrefs: [OMIM:..., MONDO:..., MESH:...]}
                            (UMLS xrefs in HPO source are dropped during
                            equivalence harvest — UMLS is not in the RoP
                            open-source corpus)
    """
    obo_path = obo_path or find_hpo_obo(sources_dir)
    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"HPO-{retrieved_date.isoformat()}"

    for term in parse_obo(obo_path):
        if term.get("is_obsolete") == "true":
            continue

        hp_id = term.get("id", "").strip()
        if not hp_id.startswith("HP:"):
            continue

        name = term.get("name", "").strip()
        if not name:
            continue

        synonyms = obo_extract_synonyms(term)
        xrefs = obo_extract_xrefs(term)
        defn = obo_extract_definition(term) or name

        metadata = {}
        if xrefs:
            metadata["hpo_xrefs"] = xrefs

        try:
            yield RoPElement(
                item=name[:255],
                description=defn,
                item_type=ItemType.ENUM,
                source_authority=SourceAuthority.HPO,
                source_code=hp_id,
                source_version=source_version,
                source_url=f"https://hpo.jax.org/app/browse/term/{hp_id}",
                source_retrieved_date=retrieved_date,
                alternate_names=normalize_pipe_delimited(*synonyms),
                metadata_=metadata or None,
                curation_status=CurationStatus.AUTO_MATCHED,
            )
        except Exception as exc:
            logger.warning("Skipped HPO term %s: %s", hp_id, exc)
            continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="HPO")
    t0 = time.time()
    for _ in ingest_hpo(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
