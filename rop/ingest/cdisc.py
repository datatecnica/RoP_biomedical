"""CDISC SDTM controlled terminology ingest.

CDISC Terminology is published by the US National Cancer Institute's
Enterprise Vocabulary Services (NCI-EVS) and distributed via FTP at
https://evs.nci.nih.gov/ftp1/CDISC/SDTM/. It's free without licensing
restrictions and ships in multiple formats; we use the .txt (tab-delimited)
release as it's the most ingestion-friendly.

For RoP, CDISC contributes:
- Theme 11 (Summary Statistics) — CT codelists for analysis-ready summaries
- Theme 12 (Clinical Concepts) — AE/CM/MH domain terms for AEs, drugs,
  medical history

Download instructions:
    Browse https://evs.nci.nih.gov/ftp1/CDISC/SDTM/ and grab the latest
    'SDTM Terminology YYYY-MM-DD.txt' file. Place at
    data/sources/cdisc/SDTM_Terminology_<date>.txt
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
    DownloadResult,
    IngestStats,
    http_download,
    normalize_pipe_delimited,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)

# Direct URL for the SDTM Terminology tab-delimited file. NCI EVS publishes
# this without authentication. URL is stable across releases (the file is
# overwritten in place on each quarterly publication).
CDISC_SDTM_URL = "https://evs.nci.nih.gov/ftp1/CDISC/SDTM/SDTM%20Terminology.txt"


def download_cdisc(sources_dir: Path = DEFAULT_SOURCES_DIR) -> DownloadResult:
    """Auto-download the latest CDISC SDTM Terminology TXT from NCI EVS.

    No login required; file is published quarterly at a stable URL.
    """
    cdisc_dir = Path(sources_dir) / "cdisc"
    dest = cdisc_dir / "SDTM_Terminology.txt"
    return http_download(CDISC_SDTM_URL, dest)


def find_cdisc_file(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    cdisc_dir = Path(sources_dir) / "cdisc"
    candidates = (
        list(cdisc_dir.glob("SDTM*.txt"))
        + list(cdisc_dir.glob("SDTM*.tsv"))
        + list(cdisc_dir.glob("*Terminology*.txt"))
    )
    if not candidates:
        raise FileNotFoundError(
            f"CDISC SDTM terminology file not found in {cdisc_dir}. "
            f"Download from https://evs.nci.nih.gov/ftp1/CDISC/SDTM/"
        )
    return candidates[0]


def ingest_cdisc(
    csv_path: Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield one RoPElement per CDISC SDTM term.

    NCI EVS file format (tab-delimited): each row is a term with columns
    Code, Codelist Code, Codelist Extensible (Yes/No), Codelist Name,
    CDISC Submission Value, CDISC Synonym(s), CDISC Definition, NCI
    Preferred Term.
    """
    csv_path = csv_path or find_cdisc_file(sources_dir)
    retrieved_date = retrieved_date or date.today()
    # Try to extract release date from filename
    if not source_version:
        stem = Path(csv_path).stem
        # filename pattern: 'SDTM Terminology 2026-03-27'
        for tok in stem.replace("_", " ").split():
            if len(tok) == 10 and tok[4] == "-" and tok[7] == "-":
                source_version = f"CDISC-SDTM-{tok}"
                break
        if not source_version:
            source_version = f"CDISC-SDTM-{retrieved_date.isoformat()}"

    with Path(csv_path).open(encoding="utf-8", errors="replace") as f:
        # Try tab delimiter first; fall back to CSV
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if "\t" in sample else ","
        reader = csv.DictReader(f, delimiter=delim)

        for row in reader:
            code = (row.get("Code") or row.get("code") or "").strip()
            if not code:
                continue
            sub_value = (row.get("CDISC Submission Value") or
                        row.get("CDISC Submission") or "").strip()
            preferred = (row.get("NCI Preferred Term") or
                        row.get("Preferred Term") or "").strip()
            defn = (row.get("CDISC Definition") or
                   row.get("Definition") or "").strip()
            synonyms = (row.get("CDISC Synonym(s)") or
                       row.get("Synonyms") or "").strip()
            codelist_name = (row.get("Codelist Name") or "").strip()

            item = sub_value or preferred or code
            description = defn or preferred or sub_value or item

            metadata = {}
            if codelist_name:
                metadata["cdisc_codelist"] = codelist_name
            if (cl_code := (row.get("Codelist Code") or "").strip()):
                metadata["cdisc_codelist_code"] = cl_code

            try:
                yield RoPElement(
                    item=item[:255],
                    description=description,
                    item_type=ItemType.ENUM,
                    source_authority=SourceAuthority.CDISC,
                    source_code=code,
                    source_version=source_version,
                    source_url=f"https://evs.nci.nih.gov/ftp1/CDISC/SDTM/",
                    source_retrieved_date=retrieved_date,
                    alternate_names=normalize_pipe_delimited(synonyms),
                    metadata_=metadata or None,
                    curation_status=CurationStatus.AUTO_MATCHED,
                )
            except Exception as exc:
                logger.warning("Skipped CDISC %s: %s", code, exc)
                continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="CDISC")
    t0 = time.time()
    for _ in ingest_cdisc(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
