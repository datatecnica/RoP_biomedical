"""RoP source-authority ingest package.

One module per upstream source authority. Each exposes:
    - ingest_<source>(...)  → Iterator[RoPElement]
    - download_<source>(...) where applicable (for git-cloned sources)
    - run_ingest(sources_dir) → IngestStats   (uniform interface)

The unified orchestrator in scripts/sprint1_download_all.py drives the
Monday-morning bulk ingest by walking SOURCES below.
"""
from __future__ import annotations

from rop.ingest import (
    athena,
    bids,
    cdisc,
    dicom,
    duo,
    hpo,
    loinc,
    mondo,
    ninds_cde,
    phenx,
)
from rop.ingest._common import (
    DEFAULT_SOURCES_DIR,
    DEFAULT_STAGING_DIR,
    DownloadResult,
    IngestStats,
    extract_archive,
    git_clone,
    http_download,
    write_manifest,
)

# Registry of ingest modules keyed by short name.
# Used by scripts/sprint1_download_all.py to iterate.
SOURCES = {
    "loinc": loinc,
    "athena": athena,
    "hpo": hpo,
    "mondo": mondo,
    "duo": duo,
    "dicom": dicom,
    "bids": bids,
    "cdisc": cdisc,
    "phenx": phenx,
    "ninds_cde": ninds_cde,
}

__all__ = [
    "SOURCES",
    "DEFAULT_SOURCES_DIR",
    "DEFAULT_STAGING_DIR",
    "DownloadResult",
    "IngestStats",
    "http_download",
    "git_clone",
    "extract_archive",
    "write_manifest",
    "athena",
    "bids",
    "cdisc",
    "dicom",
    "duo",
    "hpo",
    "loinc",
    "mondo",
    "ninds_cde",
    "phenx",
]
