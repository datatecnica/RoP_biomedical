"""LOINC release ingest — OPTIONAL for v2026.04.

**Status: Optional.** Athena's LOINC content is the primary LOINC source for
RoP v2026.04 (see rop/ingest/athena.py). Direct LOINC ingest preserves the
six-axis decomposition (Component/Property/Time/System/Scale/Method) in flat
metadata fields rather than as CONCEPT_RELATIONSHIP edges, which is useful
for sophisticated omics-platform queries but not load-bearing for the
foundation bundle.

Use this module when:
  - You need flat six-axis fields on every LOINC row without joining
    CONCEPT_RELATIONSHIP
  - You want the latest LOINC release (Athena lags by ~1-3 months)
  - You're building specialized omics or laboratory tooling

Skip this module (the default) when:
  - You're building the v2026.04 foundation bundle and want simplicity
  - You don't want to deal with the LOINC login workflow

LOINC ships as a license-gated ZIP from https://loinc.org/downloads/, but the
contents (Loinc.csv) are redistribution-permissive with attribution.

Download instructions (only if using):
1. Register at https://loinc.org/join/ (free)
2. Download the latest LOINC release ZIP
3. Place at data/sources/loinc/Loinc_<version>.zip
   The script will extract Loinc.csv automatically.
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
    normalize_pipe_delimited,
)
from rop.schema import (
    CurationStatus,
    ItemType,
    RoPElement,
    SourceAuthority,
)

logger = logging.getLogger(__name__)

# LOINC publishes releases roughly twice yearly. Update this when refreshing.
DEFAULT_LOINC_VERSION = "2.78"


def find_or_extract_loinc_csv(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    """Locate Loinc.csv in the staging directory, extracting from ZIP if needed.

    The LOINC ZIP contains many files; we only need the main Loinc.csv
    (LoincTable/Loinc.csv inside the archive).
    """
    loinc_dir = Path(sources_dir) / "loinc"
    csv_candidates = list(loinc_dir.rglob("Loinc.csv"))
    if csv_candidates:
        return csv_candidates[0]

    zips = list(loinc_dir.glob("Loinc_*.zip")) + list(loinc_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"No Loinc.csv or Loinc ZIP found in {loinc_dir}. "
            "Download from https://loinc.org/downloads/ and place ZIP here."
        )
    extracted = extract_archive(zips[0], loinc_dir / "extracted")
    csv_candidates = list(extracted.rglob("Loinc.csv"))
    if not csv_candidates:
        raise FileNotFoundError(f"Loinc.csv not found inside {zips[0]}")
    return csv_candidates[0]


def ingest_loinc(
    csv_path: Path | None = None,
    *,
    source_version: str = DEFAULT_LOINC_VERSION,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield RoPElement instances from a LOINC release CSV.

    Each LOINC term contributes:
        item              = LOINC SHORTNAME (or COMPONENT if SHORTNAME blank)
        description       = LONG_COMMON_NAME
        source_code       = LOINC_NUM
        source_authority  = LOINC
        alternate_names   = pipe-joined RELATEDNAMES2 + SHORTNAME variants
        item_type         = numeric | string | enum (heuristic from SCALE_TYP)
        unit_of_measure   = EXAMPLE_UCUM_UNITS when populated
        unit_vocabulary   = UCUM when unit populated
        metadata_         = six-axis fields plus CLASS, STATUS, EXAMPLE_UNITS

    The six-axis decomposition (component / property / time / system / scale /
    method) is preserved in metadata_ so Theme 6 omics queries can join on
    individual axes.

    Yields one RoPElement per active LOINC term. Inactive (DEPRECATED, TRIAL)
    terms are filtered out.
    """
    csv_path = csv_path or find_or_extract_loinc_csv(sources_dir)
    retrieved_date = retrieved_date or date.today()

    with Path(csv_path).open(encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = (row.get("STATUS") or "").upper()
            if status not in ("ACTIVE", ""):
                continue

            loinc_num = (row.get("LOINC_NUM") or "").strip()
            if not loinc_num:
                continue

            shortname = (row.get("SHORTNAME") or "").strip()
            component = (row.get("COMPONENT") or "").strip()
            long_name = (row.get("LONG_COMMON_NAME") or "").strip()

            item = shortname or component or loinc_num
            description = long_name or shortname or component or f"LOINC {loinc_num}"

            scale = (row.get("SCALE_TYP") or "").strip().upper()
            item_type: ItemType | None = None
            if scale in ("QN",):
                item_type = ItemType.NUMERIC
            elif scale in ("ORD", "NOM", "OC"):
                item_type = ItemType.ENUM
            elif scale in ("NAR", "DOC"):
                item_type = ItemType.STRING
            elif scale == "SET":
                item_type = ItemType.STRING

            unit = (row.get("EXAMPLE_UCUM_UNITS") or "").strip() or None
            example_units = (row.get("EXAMPLE_UNITS") or "").strip() or None

            alt_names = normalize_pipe_delimited(
                row.get("RELATEDNAMES2"),
                shortname if shortname and shortname != item else None,
            )

            metadata = {
                "loinc_class": (row.get("CLASS") or "").strip() or None,
                "loinc_status": status or None,
                "axis_component": component or None,
                "axis_property": (row.get("PROPERTY") or "").strip() or None,
                "axis_time": (row.get("TIME_ASPCT") or "").strip() or None,
                "axis_system": (row.get("SYSTEM") or "").strip() or None,
                "axis_scale": scale or None,
                "axis_method": (row.get("METHOD_TYP") or "").strip() or None,
                "example_units": example_units,
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}

            try:
                yield RoPElement(
                    item=item[:255],
                    description=description,
                    item_type=item_type,
                    source_authority=SourceAuthority.LOINC,
                    source_code=loinc_num,
                    source_version=f"LOINC-{source_version}",
                    source_url=f"https://loinc.org/{loinc_num}/",
                    source_retrieved_date=retrieved_date,
                    alternate_names=alt_names,
                    unit_of_measure=unit,
                    unit_vocabulary="UCUM" if unit else None,
                    metadata_=metadata or None,
                    curation_status=CurationStatus.AUTO_MATCHED,
                )
            except Exception as exc:
                logger.warning("Skipped LOINC %s: %s", loinc_num, exc)
                continue


def run_ingest(
    sources_dir: Path = DEFAULT_SOURCES_DIR,
    source_version: str = DEFAULT_LOINC_VERSION,
) -> IngestStats:
    """Execute LOINC ingest end-to-end; return stats."""
    stats = IngestStats(source_name="LOINC")
    t0 = time.time()
    for elem in ingest_loinc(source_version=source_version, sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
