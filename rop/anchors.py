"""Anchor CDE registry.

Loads the JSON anchor definitions from data/anchors/, indexes them by tier
and item name, and provides lookup utilities.

The anchor JSON files are the normative definition of the Core Anchor tiers.
This module is a loader, not the source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default location relative to package root; overridable per-call
DEFAULT_ANCHOR_DIR = Path(__file__).resolve().parent.parent / "data" / "anchors"

# Tier ordering: file prefix → tier name
# Theme ordering: file prefix → theme name.
# We use "theme" terminology because the 13 functional groupings are not strictly
# hierarchical (the orthogonal attestations break a strict tier ordering) AND
# themes naturally accommodate sub-themes — Theme 6 (Biosample) groups the main
# biosample anchors with anatomy/cell sub-content, and Theme 13 (Discoverability)
# splits into 13a (Resources) and 13b (Collections) sub-themes.
THEME_ORDER = [
    ("01_identity", "Identity"),
    ("02_time", "Time"),
    ("03_sex", "Sex"),
    ("04_ancestry_pedigree", "Ancestry-Pedigree"),
    ("05_biosample", "Biosample"),
    ("05b_anatomy_celltype", "Biosample"),
    ("06_omics", "Omics-Platform"),
    ("07_imaging_acquisition", "Imaging-Acquisition"),
    ("08_clinical_instruments", "Clinical-Instruments"),
    ("09_governance", "Governance"),
    ("10_data_assets", "Data-Assets"),
    ("11_summary_stats", "Summary-Stats"),
    ("12_clinical_concepts", "Clinical-Concepts"),
    ("13a_resources", "Discoverability"),
    ("13b_collections", "Discoverability"),
]

# Backward-compat aliases
MODULE_ORDER = THEME_ORDER
TIER_ORDER = THEME_ORDER


@dataclass
class AnchorDefinition:
    """One anchor CDE as parsed from a tier JSON file."""

    item: str
    description: str
    collection: str | None = None
    item_type: str | None = None
    values: str | None = None
    alternate_names: str | None = None
    priority: str | None = None
    metadata_: dict[str, Any] | None = None
    source_authority: str | None = None
    source_code: str | None = None
    source_version: str | None = None
    source_url: str | None = None
    member_of_collections: list[str] = field(default_factory=list)
    curation_status: str = "expert-curated"
    # v2026.04 quantitative semantics
    unit_of_measure: str | None = None
    unit_vocabulary: str | None = None
    plausible_min: float | None = None
    plausible_max: float | None = None
    numeric_precision: int | None = None
    cardinality: str = "single"
    missing_value_convention: str | None = None
    tier: str | None = None  # filled in by registry

    @classmethod
    def from_dict(cls, d: dict[str, Any], tier: str | None = None) -> AnchorDefinition:
        # Filter to known fields; drop unknowns gracefully so anchor JSONs
        # can carry extra documentation fields without breaking the parser
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in d.items() if k in known}
        kwargs["tier"] = tier
        return cls(**kwargs)


@dataclass
class AnchorRegistry:
    """Registry of all anchor definitions across modules."""

    by_item: dict[str, AnchorDefinition] = field(default_factory=dict)
    by_tier: dict[str, list[AnchorDefinition]] = field(default_factory=dict)

    def get(self, item: str) -> AnchorDefinition | None:
        return self.by_item.get(item)

    def tier_items(self, tier: str) -> list[AnchorDefinition]:
        return self.by_tier.get(tier, [])

    # Theme-terminology aliases (preferred going forward)
    @property
    def by_theme(self) -> dict[str, list[AnchorDefinition]]:
        return self.by_tier

    def theme_items(self, theme: str) -> list[AnchorDefinition]:
        return self.by_tier.get(theme, [])

    # Module-terminology aliases (intermediate naming, also supported)
    @property
    def by_module(self) -> dict[str, list[AnchorDefinition]]:
        return self.by_tier

    def module_items(self, module: str) -> list[AnchorDefinition]:
        return self.by_tier.get(module, [])

    @property
    def all_items(self) -> list[str]:
        return list(self.by_item.keys())

    def __len__(self) -> int:
        return len(self.by_item)


def load_anchors(anchor_dir: Path | str = DEFAULT_ANCHOR_DIR) -> AnchorRegistry:
    """Load all anchor tier JSON files from a directory.

    Returns a fully-indexed registry. Files are loaded in MODULE_ORDER; unknown
    files in the directory are loaded as a fallback module named after the file.
    """
    anchor_dir = Path(anchor_dir)
    if not anchor_dir.exists():
        raise FileNotFoundError(f"Anchor directory not found: {anchor_dir}")

    registry = AnchorRegistry()
    seen_files: set[str] = set()

    for prefix, module_name in MODULE_ORDER:
        matching = sorted(anchor_dir.glob(f"{prefix}*.json"))
        for path in matching:
            seen_files.add(path.name)
            _load_module_file(path, module_name, registry)

    # Fallback: any *.json not matched above
    for path in sorted(anchor_dir.glob("*.json")):
        if path.name in seen_files:
            continue
        module_name = path.stem
        _load_module_file(path, module_name, registry)

    return registry


def _load_module_file(path: Path, module_name: str, registry: AnchorRegistry) -> None:
    """Parse one module JSON file into the registry."""
    with path.open() as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Anchor file {path} must contain a JSON array")

    module_items: list[AnchorDefinition] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError(f"Anchor entry in {path} must be an object")
        anchor = AnchorDefinition.from_dict(entry, tier=module_name)
        if anchor.item in registry.by_item:
            raise ValueError(
                f"Duplicate anchor item '{anchor.item}' in {path} "
                f"(also defined in module '{registry.by_item[anchor.item].tier}')"
            )
        registry.by_item[anchor.item] = anchor
        module_items.append(anchor)

    if module_name in registry.by_tier:
        registry.by_tier[module_name].extend(module_items)
    else:
        registry.by_tier[module_name] = module_items


# Backward-compat alias
_load_tier_file = _load_module_file
