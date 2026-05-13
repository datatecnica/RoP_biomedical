"""BIDS specification controlled vocabulary ingest.

The Brain Imaging Data Structure (BIDS) defines entities, suffixes, and
metadata fields used to organize neuroimaging datasets. The spec is
distributed as a git repo under CC0 from
github.com/bids-standard/bids-specification.

For RoP, BIDS contributes Theme 7 (Imaging Acquisition) controlled vocabulary
entries — the entity names (sub-, ses-, task-, run-) and metadata field
keys (RepetitionTime, EchoTime, FlipAngle) that BIDS pipelines expect.

Download instructions:
    git clone --depth 1 https://github.com/bids-standard/bids-specification.git \\
        data/sources/bids
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
)
from rop.schema import CurationStatus, ItemType, RoPElement, SourceAuthority

logger = logging.getLogger(__name__)

BIDS_REPO_URL = "https://github.com/bids-standard/bids-specification.git"


def find_bids_schema_dir(sources_dir: Path = DEFAULT_SOURCES_DIR) -> Path:
    """The BIDS schema lives in src/schema/ as YAML files since BIDS 1.7+."""
    bids_dir = Path(sources_dir) / "bids"
    schema_dir = bids_dir / "src" / "schema"
    if schema_dir.is_dir():
        return schema_dir
    # Older layouts
    candidates = list(bids_dir.rglob("schema")) + list(bids_dir.rglob("schema.json"))
    if candidates:
        return candidates[0] if candidates[0].is_dir() else candidates[0].parent
    raise FileNotFoundError(
        f"BIDS schema not found in {bids_dir}. Run: git clone --depth 1 "
        f"{BIDS_REPO_URL} {bids_dir}"
    )


def download_bids(sources_dir: Path = DEFAULT_SOURCES_DIR):
    return git_clone(BIDS_REPO_URL, Path(sources_dir) / "bids")


def ingest_bids(
    schema_dir: Path | None = None,
    *,
    source_version: str | None = None,
    retrieved_date: date | None = None,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
) -> Iterator[RoPElement]:
    """Yield RoPElement per BIDS entity, suffix, datatype, and metadata field.

    BIDS schema is YAML under src/schema/objects/ with subfolders:
        entities.yaml          — sub, ses, task, run, ...
        suffixes.yaml          — T1w, T2w, bold, dwi, ...
        datatypes.yaml         — anat, func, dwi, ...
        metadata.yaml          — RepetitionTime, EchoTime, ...
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; skipping BIDS ingest. "
                       "Run: pip install pyyaml")
        return

    schema_dir = schema_dir or find_bids_schema_dir(sources_dir)
    retrieved_date = retrieved_date or date.today()
    source_version = source_version or f"BIDS-{retrieved_date.isoformat()}"

    objects_dir = Path(schema_dir) / "objects"
    if not objects_dir.is_dir():
        # Fall back to recursive search
        yaml_files = list(Path(schema_dir).rglob("*.yaml"))
    else:
        yaml_files = list(objects_dir.rglob("*.yaml"))

    for yaml_path in yaml_files:
        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Skipped BIDS YAML %s: %s", yaml_path, exc)
            continue

        if not isinstance(data, dict):
            continue

        # Categorize file by parent folder
        category = yaml_path.parent.name  # "entities", "suffixes", etc.

        for key, defn in data.items():
            if not isinstance(defn, dict):
                continue
            display_name = defn.get("display_name") or key
            description = defn.get("description") or display_name
            if not isinstance(description, str):
                description = str(description)

            metadata = {"bids_category": category}
            if "type" in defn:
                metadata["bids_type"] = str(defn["type"])
            if "format" in defn:
                metadata["bids_format"] = str(defn["format"])
            if "value" in defn:
                metadata["bids_value"] = str(defn["value"])

            # Coarse item_type assignment
            bids_type = (defn.get("type") or "").lower()
            item_type: ItemType | None = None
            if bids_type in ("number", "integer", "float"):
                item_type = ItemType.NUMERIC
            elif bids_type == "boolean":
                item_type = ItemType.ENUM
            elif bids_type == "string":
                item_type = ItemType.STRING
            elif bids_type in ("array", "object"):
                item_type = ItemType.STRING

            try:
                yield RoPElement(
                    item=str(key)[:255],
                    description=description.strip(),
                    item_type=item_type,
                    source_authority=SourceAuthority.BIDS,
                    source_code=f"BIDS:{category}:{key}",
                    source_version=source_version,
                    source_retrieved_date=retrieved_date,
                    collection="RoP-Core-Imaging",
                    metadata_=metadata,
                    curation_status=CurationStatus.AUTO_MATCHED,
                )
            except Exception as exc:
                logger.warning("Skipped BIDS %s/%s: %s", category, key, exc)
                continue


def run_ingest(sources_dir: Path = DEFAULT_SOURCES_DIR) -> IngestStats:
    stats = IngestStats(source_name="BIDS")
    t0 = time.time()
    for _ in ingest_bids(sources_dir=sources_dir):
        stats.rows_yielded += 1
    stats.elapsed_seconds = time.time() - t0
    return stats
