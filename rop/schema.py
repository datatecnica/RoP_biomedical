"""Schema models for RoP elements.

Mirrors the SQL schema in migrations/001_rop_extension.sql. Pydantic models
serve as the single source of truth for in-memory representation, JSON
serialization, and validation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceAuthority(str, Enum):
    """Recognized source authorities (SPEC §3.1).

    SNOMED CT, MedDRA, and CPT4 are intentionally excluded due to
    redistribution licensing constraints. Their IDs remain accessible
    via cross-references in upstream OBO files (Mondo, HPO) and in
    NINDS-CDE External_Id columns, but no SNOMED/MedDRA/CPT4 content
    is redistributed in any RoP bundle.
    """

    LOINC = "LOINC"
    HPO = "HPO"
    OMIM = "OMIM"
    MONDO = "Mondo"
    OMOP = "OMOP"
    NACC = "NACC"
    NINDS_CDE = "NINDS-CDE"
    PHENX = "PhenX"
    CDISC = "CDISC"
    DUO = "DUO"
    DICOM = "DICOM"
    BIDS = "BIDS"
    DATATECNICA = "DataTecnica-derived"


class CurationStatus(str, Enum):
    """Governance state for a RoP element (SPEC §2.6)."""

    AUTO_MATCHED = "auto-matched"
    HITL_CONFIRMED = "HitL-confirmed"
    EXPERT_CURATED = "expert-curated"
    DEPRECATED = "deprecated"
    UNDER_REVIEW = "under-review"


class ItemType(str, Enum):
    """Forge-native item types."""

    NUMERIC = "numeric"
    STRING = "string"
    DATE = "date"
    ENUM = "enum"
    BINARY = "binary"


class Cardinality(str, Enum):
    """Cardinality of a CDE — how many values per row this CDE expects.

    For multi-valued CDEs, RoP enforces pipe ('|') as the canonical delimiter
    in the values column. Source data using comma, semicolon, or other
    delimiters is normalized to pipe at ingest time.
    """

    SINGLE = "single"
    MULTIPLE = "multiple"
    UNBOUNDED = "unbounded"


class UnitVocabulary(str, Enum):
    """Controlled vocabulary tag for unit_of_measure (SPEC §3.x)."""

    UCUM = "UCUM"
    SNOMED_UNITS = "SNOMED-units"
    FREE_TEXT = "free-text"


# Canonical delimiter for cardinality=multiple/unbounded values columns.
# This is enforced at validation time; ingest pipelines normalize source-data
# delimiters (comma, semicolon, whitespace) to pipe.
RoP_LIST_DELIMITER = "|"


class RoPElement(BaseModel):
    """A single RoP element row.

    Conforms to the schema specified in docs/SPEC.md §2. Pydantic enforces
    type correctness; conditional-required validation is applied separately
    by rop.validate.
    """

    model_config = ConfigDict(
        use_enum_values=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    # --- Identity (§2.1) ---
    id: UUID | None = Field(None, description="Database PK; assigned at insert")
    rop_accession: str | None = Field(
        None,
        pattern=r"^RoP:\d{7}$",
        description="Public stable identifier; never recycled",
    )
    content_hash: str | None = Field(
        None,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 of canonicalized content; computed by compute_content_hash()",
    )
    schema_id: UUID | None = Field(None, description="FK to schemas table")

    # --- Standard CDE columns (§2.2) ---
    item: str = Field(..., max_length=255)
    description: str = Field(..., min_length=1)
    collection: str | None = Field(None, max_length=255)
    item_type: ItemType | None = None
    values: str | None = None
    value_set_ref: str | None = Field(
        None,
        pattern=r"^[a-f0-9-]+@\d+$",
        description="Format: <uuid>@<version>",
    )
    alternate_names: str | None = Field(None, description="Pipe-separated synonyms")
    priority: str | None = Field(
        None,
        max_length=50,
        description="Validation priority; supports conditional-required syntax",
    )
    sort_order: int | None = None
    is_active: bool = True
    metadata_: dict[str, Any] | None = None

    # --- Quantitative semantics (§2.2.1, added v2026.04) ---
    unit_of_measure: str | None = Field(
        None,
        max_length=64,
        description="Unit of measure string (e.g., 'mg/dL', 'a' for years per UCUM)",
    )
    unit_vocabulary: UnitVocabulary | None = Field(
        None,
        description="Controlled vocabulary tag for unit_of_measure",
    )
    plausible_min: float | None = Field(
        None,
        description="Plausibility lower bound for outlier and unit-error detection. NOT a clinical reference range.",
    )
    plausible_max: float | None = Field(
        None,
        description="Plausibility upper bound for outlier and unit-error detection. NOT a clinical reference range.",
    )
    numeric_precision: int | None = Field(
        None,
        ge=0,
        le=20,
        description="Number of decimal places for numeric item_types",
    )
    cardinality: Cardinality = Field(
        Cardinality.SINGLE,
        description="How many values per row this CDE expects. Multi-valued CDEs use pipe '|' as delimiter.",
    )
    missing_value_convention: str | None = Field(
        None,
        max_length=64,
        description="Sentinel for missing data (default 'null'). Numeric sentinels (-9, -99) prohibited in conformant data.",
    )

    # --- Provenance (§2.3) ---
    source_authority: SourceAuthority
    source_code: str | None = Field(None, max_length=255)
    source_version: str = Field(..., max_length=50)
    source_url: str | None = None
    source_retrieved_date: date

    # --- Multi-collection membership (§2.4) ---
    member_of_collections: list[str] = Field(default_factory=list)

    # --- Cross-vocabulary linkage (§2.5) ---
    canonical_concept_id: int | None = None
    equivalent_rop_ids: list[UUID] = Field(default_factory=list)
    alternate_codes: list[dict[str, str]] = Field(
        default_factory=list,
        description="Non-standard codes that map to this standard concept. "
                    "Format: [{\"vocabulary\": \"ICD10CM\", \"code\": \"E11.9\"}, ...]. "
                    "Populated from Athena Maps-to relationships during dedup.",
    )

    # --- Governance state (§2.6) ---
    curation_status: CurationStatus = CurationStatus.AUTO_MATCHED
    curator: str | None = Field(None, max_length=255)
    curation_date: date | None = None
    match_confidence: float | None = Field(None, ge=0.0, le=1.0)
    replaced_by_rop_id: UUID | None = None

    # --- Search/embedding (§2.7) ---
    search_text: str | None = None
    embedding: list[float] | None = Field(
        None,
        description="Sentence-transformer embedding; dimension recorded in bundle manifest",
    )

    # --- Audit timestamps ---
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("alternate_names")
    @classmethod
    def _normalize_alternate_names(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Normalize: strip per-token, drop empties, deduplicate, preserve order
        seen: set[str] = set()
        out: list[str] = []
        for tok in v.split("|"):
            tok = tok.strip()
            if tok and tok not in seen:
                seen.add(tok)
                out.append(tok)
        return "|".join(out) if out else None

    @field_validator("member_of_collections")
    @classmethod
    def _normalize_collections(cls, v: list[str]) -> list[str]:
        # Sorted, deduplicated, stripped
        return sorted({c.strip() for c in v if c and c.strip()})

    @model_validator(mode="after")
    def _validate_plausible_range_ordering(self) -> "RoPElement":
        """plausible_min must be ≤ plausible_max when both are populated."""
        if (
            self.plausible_min is not None
            and self.plausible_max is not None
            and self.plausible_min > self.plausible_max
        ):
            raise ValueError(
                f"plausible_min ({self.plausible_min}) must be ≤ plausible_max ({self.plausible_max})"
            )
        return self


def compute_content_hash(element: RoPElement) -> str:
    """Compute the SHA-256 content hash for an element (SPEC §6).

    Hashed fields are exactly those in the spec; all others (id, accession,
    timestamps, governance, derived) are deliberately excluded.
    """
    payload: dict[str, Any] = {
        "description": element.description,
        "item_type": element.item_type if isinstance(element.item_type, str) else (
            element.item_type.value if element.item_type else None
        ),
        "values": element.values,
        "value_set_ref": element.value_set_ref,
        "source_authority": (
            element.source_authority
            if isinstance(element.source_authority, str)
            else element.source_authority.value
        ),
        "source_code": element.source_code,
        "source_version": element.source_version,
        "alternate_names": (
            sorted(element.alternate_names.split("|"))
            if element.alternate_names
            else None
        ),
        "collections": sorted(element.member_of_collections),
        "metadata_": _canonicalize_jsonb(element.metadata_),
        # v2026.04 quantitative semantics fields
        "unit_of_measure": element.unit_of_measure,
        "unit_vocabulary": (
            element.unit_vocabulary if isinstance(element.unit_vocabulary, str)
            else (element.unit_vocabulary.value if element.unit_vocabulary else None)
        ),
        "plausible_min": element.plausible_min,
        "plausible_max": element.plausible_max,
        "numeric_precision": element.numeric_precision,
        "cardinality": (
            element.cardinality if isinstance(element.cardinality, str)
            else element.cardinality.value
        ),
        "missing_value_convention": element.missing_value_convention,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonicalize_jsonb(obj: Any) -> Any:
    """Recursively canonicalize a JSONB-shaped object for stable hashing."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _canonicalize_jsonb(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_canonicalize_jsonb(x) for x in obj]
    return obj


def compose_search_text(element: RoPElement) -> str:
    """Build the search_text payload that gets embedded.

    Concatenates description, source identity, collection context, and
    salient metadata. This is the operationalization of the insight that
    description + source + collection together produce more discriminative
    embeddings than description alone.
    """
    parts: list[str] = [element.description]

    src = element.source_authority
    if not isinstance(src, str):
        src = src.value
    if element.source_code:
        parts.append(f"{src} {element.source_code}")
    else:
        parts.append(src)

    if element.collection:
        parts.append(element.collection)

    if element.member_of_collections:
        parts.append(" ".join(element.member_of_collections))

    if element.metadata_:
        # Flatten only string-valued metadata keys for embedding context
        meta_str = " ".join(
            f"{k} {v}"
            for k, v in element.metadata_.items()
            if isinstance(v, str)
        )
        if meta_str:
            parts.append(meta_str)

    return " | ".join(parts)
