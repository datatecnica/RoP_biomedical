"""PhenX Toolkit data dictionary ingest.

PhenX makes bulk database downloads available at
https://www.phenxtoolkit.org/resources/download under CC-BY-4.0.

The DD_CSV bulk export contains one row per variable across all 983
protocols, with columns: Variable_Name, Variable_Description, Variable_Type,
Variable_Unit, Variable_Min, Variable_Max, Protocol_ID, Protocol_Name,
Domain_Name, ...

For RoP, PhenX contributes:
- Theme 8 (Clinical Instruments) — for questionnaire/scale protocols
- Theme 12 (Clinical Concepts) — for biomarker/lab/exposure variables
- Theme 4 (Ancestry & Pedigree) — demographic protocols
- Theme 5 (Biosample) — biospecimen-collection protocols

We do NOT ingest the instrument forms (DCW Word docs); we only ingest the
variable-level data dictionary, which is the metadata layer.

Download instructions:
1. Visit https://www.phenxtoolkit.org/resources/download
2. Download the latest bulk DD_CSV release (no registration required)
3. Place at data/sources/phenx/PhenX_DD_<release>.csv
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
    extract_archive,
    http_download,
    normalize_pipe_delimited,
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)

# Direct URL for the bulk DD_CSV ZIP. PhenX publishes this without
# authentication under CC-BY-4.0; URL is stable across releases.
PHENX_DD_CSV_URL = (
    "https://www.phenxtoolkit.org/toolkit_content/documents/data_dictionary/"
    "ALL_DD_CSV_Files.zip"
)


def download_phenx(sources_dir: Path = DEFAULT_SOURCES_DIR) -> DownloadResult:
    """Auto-download the bulk PhenX Data Dictionary CSV ZIP and extract it.

    The ZIP contains one CSV per protocol (~983 protocols). All CSVs share
    the same column structure, and the parser iterates over all of them.
    """
    phenx_dir = Path(sources_dir) / "phenx"
    zip_dest = phenx_dir / "ALL_DD_CSV_Files.zip"
    result = http_download(PHENX_DD_CSV_URL, zip_dest)
    # Extract into a sibling 'extracted' subdir (idempotent)
    extracted_dir = phenx_dir / "extracted"
    if not extracted_dir.exists() or not any(extracted_dir.rglob("*.csv")):
        extract_archive(zip_dest, extracted_dir)
    return result


def find_phenx_csvs(sources_dir: Path = DEFAULT_SOURCES_DIR) -> list[Path]:
    """Return all PhenX per-protocol DD CSV files in the staging directory.

    Looks under both the top-level phenx/ and phenx/extracted/ to handle
    both manual-staged single-file uploads and orchestrator-driven ZIP
    extraction.
    """
    phenx_dir = Path(sources_dir) / "phenx"
    csvs: list[Path] = []
    csvs.extend(phenx_dir.glob("*.csv"))
    csvs.extend((phenx_dir / "extracted").rglob("*.csv"))
    # Deduplicate while preserving order
    seen: set[Path] = set()
    out: list[Path] = []
    for c in csvs:
        if c.resolve() not in seen:
            seen.add(c.resolve())
            out.append(c)
    if not out:
        raise FileNotFoundError(
            f"No PhenX DD CSV files found in {phenx_dir}. "
            f"Run download_phenx() or place files under {phenx_dir}/."
        )
    return out


# PhenX variable type → RoP item_type
PHENX_TYPE_TO_ITEMTYPE: dict[str, ItemType] = {
    "numeric": ItemType.NUMERIC,
    "integer": ItemType.NUMERIC,
    "decimal": ItemType.NUMERIC,
    "categorical": ItemType.ENUM,
    "categoric": ItemType.ENUM,
    "encoded": ItemType.ENUM,
    "string": ItemType.STRING,
    "text": ItemType.STRING,
    "date": ItemType.DATE,
    "datetime": ItemType.DATE,
}


def ingest_phenx(
    csv_path: Path | list[Path] | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield RoPElement per PhenX variable across all per-protocol DD CSVs.

    The PhenX bulk download is a ZIP of per-protocol DD CSVs (one CSV per
    protocol, ~983 protocols total). All share the same column structure.
    This function iterates over all CSVs in the staging dir.

    Parameters
    ----------
    csv_path : Path | list[Path] | None
        - None: auto-discover all CSVs under data/sources/phenx/
        - Path: parse single CSV (legacy / test fixture mode)
        - list[Path]: parse the listed CSVs

    PhenX DD CSV column names vary slightly across releases. The parser
    tolerates common variants (Variable_Name vs variable_name vs varName).
    """
    if csv_path is None:
        csv_paths = find_phenx_csvs(sources_dir)
    elif isinstance(csv_path, (list, tuple)):
        csv_paths = list(csv_path)
    else:
        csv_paths = [Path(csv_path)]
    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"PhenX-{retrieved_date.isoformat()}"

    # Build column-name lookup tolerant of variants (closure used per-row)
    def col(row: dict, *names: str) -> str:
        for n in names:
            for k in (n, n.lower(), n.upper(), n.replace("_", " ")):
                if k in row and row[k] is not None:
                    return str(row[k]).strip()
        return ""

    for path in csv_paths:
        logger.debug("Parsing PhenX CSV: %s", path)
        with Path(path).open(encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            for row in reader:
                var_name = col(row, "Variable_Name", "variable_name", "Variable", "VARNAME")
                if not var_name:
                    continue

                description = (
                    col(row, "Variable_Description", "Description", "definition", "VARDESC")
                    or var_name
                )
                var_type = col(row, "Variable_Type", "type", "DataType", "TYPE").lower()
                unit = col(row, "Variable_Unit", "Unit", "Units", "UNITS") or None
                v_min = col(row, "Variable_Min", "Min", "Minimum", "MIN")
                v_max = col(row, "Variable_Max", "Max", "Maximum", "MAX")
                protocol_id = col(row, "Protocol_ID", "ProtocolID", "Protocol")
                protocol_name = col(row, "Protocol_Name", "ProtocolName")
                domain = col(row, "Domain_Name", "Domain")
                value_set = col(row, "Variable_Values", "Values", "Codes")

                item_type = PHENX_TYPE_TO_ITEMTYPE.get(var_type)

                plausible_min = None
                plausible_max = None
                if item_type is ItemType.NUMERIC:
                    try:
                        plausible_min = float(v_min) if v_min else None
                        plausible_max = float(v_max) if v_max else None
                        # Skip degenerate inverted bounds rather than fail validation
                        if (plausible_min is not None and plausible_max is not None
                                and plausible_min > plausible_max):
                            plausible_min, plausible_max = None, None
                    except ValueError:
                        plausible_min = plausible_max = None

                metadata = {
                    "phenx_protocol_id": protocol_id or None,
                    "phenx_protocol_name": protocol_name or None,
                    "phenx_domain": domain or None,
                }
                metadata = {k: v for k, v in metadata.items() if v}

                try:
                    yield RoPElement(
                        item=var_name[:255],
                        description=description[:8000],
                        item_type=item_type,
                        values=value_set or None,
                        source_authority=SourceAuthority.PHENX,
                        source_code=var_name,
                        source_version=source_version,
                        source_url=f"https://www.phenxtoolkit.org/protocols/view/{protocol_id}"
                                  if protocol_id else None,
                        source_retrieved_date=retrieved_date,
                        unit_of_measure=unit,
                        unit_vocabulary="free-text" if unit else None,
                        plausible_min=plausible_min,
                        plausible_max=plausible_max,
                        member_of_collections=[f"PhenX-{protocol_id}"] if protocol_id else [],
                        metadata_=metadata or None,
                        curation_status=CurationStatus.AUTO_MATCHED,
                    )
                except Exception as exc:
                    logger.warning("Skipped PhenX %s: %s", var_name, exc)
                    continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="PhenX")
    t0 = time.time()
    for _ in ingest_phenx(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
