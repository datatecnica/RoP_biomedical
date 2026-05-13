"""DICOM data dictionary ingest.

DICOM tags are defined in the DICOM standard PS3.6 (Data Dictionary), a
public document. The most reliable programmatic source is the pydicom
library which embeds the dictionary as Python data — installing pydicom
gives you the dictionary without needing to parse PS3.6 directly.

For RoP, DICOM contributes to Theme 7 (Imaging Acquisition Metadata) — the
specific tag identifiers that scanner manufacturers / pipelines populate.

Install: `pip install pydicom`. The script will fall back gracefully if
pydicom is unavailable, recording a placeholder for v2026.04 and emitting
a deferred-ingest note.

Download instructions: none — pydicom embeds the dictionary.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Iterator

from rop.ingest._common import DEFAULT_SOURCES_DIR, IngestStats, normalize_pipe_delimited
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)


# DICOM Value Representation (VR) → RoP item_type mapping.
# Reference: DICOM PS3.5 §6.2.
DICOM_VR_TO_ITEMTYPE: dict[str, ItemType] = {
    "AE": ItemType.STRING, "AS": ItemType.STRING, "AT": ItemType.STRING,
    "CS": ItemType.ENUM,   "DA": ItemType.DATE,   "DS": ItemType.NUMERIC,
    "DT": ItemType.DATE,   "FL": ItemType.NUMERIC, "FD": ItemType.NUMERIC,
    "IS": ItemType.NUMERIC, "LO": ItemType.STRING, "LT": ItemType.STRING,
    "OB": ItemType.BINARY, "OD": ItemType.BINARY, "OF": ItemType.BINARY,
    "OL": ItemType.BINARY, "OV": ItemType.BINARY, "OW": ItemType.BINARY,
    "PN": ItemType.STRING, "SH": ItemType.STRING, "SL": ItemType.NUMERIC,
    "SQ": ItemType.STRING, "SS": ItemType.NUMERIC, "ST": ItemType.STRING,
    "SV": ItemType.NUMERIC, "TM": ItemType.STRING, "UC": ItemType.STRING,
    "UI": ItemType.STRING, "UL": ItemType.NUMERIC, "UN": ItemType.BINARY,
    "UR": ItemType.STRING, "US": ItemType.NUMERIC, "UT": ItemType.STRING,
    "UV": ItemType.NUMERIC,
}


def ingest_dicom(
    *,
    source_version: str = "DICOM-2024",
    retrieved_date: date | None = None,
) -> Iterator[RoPElement]:
    """Yield one RoPElement per DICOM data dictionary entry.

    Uses pydicom's embedded DicomDictionary if available. The dictionary maps
    tag tuples (group, element) → (VR, VM, name, retired_flag, keyword).
    """
    retrieved_date = retrieved_date or date.today()
    try:
        from pydicom._dicom_dict import DicomDictionary
    except ImportError:
        logger.warning("pydicom not installed; skipping DICOM ingest. "
                       "Run: pip install pydicom")
        return

    for tag_int, (vr, vm, name, retired, keyword) in DicomDictionary.items():
        if retired:
            continue
        # Format tag as standard DICOM (group,element)
        group = (tag_int >> 16) & 0xFFFF
        element = tag_int & 0xFFFF
        tag_str = f"({group:04X},{element:04X})"

        # First VR if multi-valued; some DICOM tags have multiple VRs
        primary_vr = vr.split(" or ")[0] if " or " in vr else vr
        item_type = DICOM_VR_TO_ITEMTYPE.get(primary_vr.upper())

        # Cardinality from VM (Value Multiplicity)
        cardinality = "single"
        if vm and vm not in ("1",):
            cardinality = "multiple" if vm.endswith("n") or "-" in vm else "single"

        try:
            yield RoPElement(
                item=keyword[:255] if keyword else name[:255],
                description=name,
                item_type=item_type,
                cardinality=cardinality,
                source_authority=SourceAuthority.DICOM,
                source_code=tag_str,
                source_version=source_version,
                source_retrieved_date=retrieved_date,
                collection="RoP-Core-Imaging",
                metadata_={
                    "dicom_vr": primary_vr,
                    "dicom_vm": vm,
                    "dicom_keyword": keyword,
                },
                curation_status=CurationStatus.AUTO_MATCHED,
            )
        except Exception as exc:
            logger.warning("Skipped DICOM tag %s: %s", tag_str, exc)
            continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="DICOM")
    t0 = time.time()
    for _ in ingest_dicom():
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
