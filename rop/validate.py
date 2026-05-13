"""Validation engine for RoP submissions.

This is the most novel piece of the codebase: the conditional-required
parser that turns priority strings like "Required-when-IsBiosample-true"
into executable validation rules. SPEC §4 documents the grammar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from rop.anchors import AnchorRegistry, load_anchors
from rop.schema import RoPElement


# =============================================================================
# Conditional-required priority grammar
# =============================================================================

class PriorityKind(str, Enum):
    """Categories of priority expression we recognize."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    REQUIRED_WHEN_FIELD_VALUE = "required_when_field_value"
    REQUIRED_WHEN_FIELD_PRESENT = "required_when_field_present"
    REQUIRED_FOR_CONTEXT = "required_for_context"
    REQUIRED_OR_DERIVABLE = "required_or_derivable"
    RECOMMENDED = "recommended"
    UNKNOWN = "unknown"


@dataclass
class PriorityRule:
    """Parsed representation of a priority string.

    Examples (raw → parsed):

    "Required"                              → REQUIRED
    "Optional"                              → OPTIONAL
    "Required-when-IsBiosample-true"        → REQUIRED_WHEN_FIELD_VALUE,
                                              field="IsBiosample", value="true"
    "Required-when-genetic-ancestry-present"→ REQUIRED_WHEN_FIELD_PRESENT,
                                              field="genetic-ancestry"
    "Required-for-tissue-biosamples"        → REQUIRED_FOR_CONTEXT,
                                              context="tissue-biosamples"
    "Required-or-derivable"                 → REQUIRED_OR_DERIVABLE
    "Recommended-for-omics-data"            → RECOMMENDED, context="omics-data"
    """

    kind: PriorityKind
    raw: str
    field_name: str | None = None
    field_value: str | None = None
    context: str | None = None


_FIELD_VALUE_RE = re.compile(r"^Required-when-([A-Z][A-Za-z0-9]*)-(.+)$")
_FIELD_PRESENT_RE = re.compile(r"^Required-when-(.+)-present$")
_REQUIRED_FOR_RE = re.compile(r"^Required-(?:for|when)-(.+)$")
_RECOMMENDED_RE = re.compile(r"^Recommended-(?:for|when)-(.+)$")


def parse_priority_rule(priority: str | None) -> PriorityRule:
    """Parse a priority string into a structured rule (SPEC §4)."""
    if priority is None or priority.strip() == "":
        return PriorityRule(kind=PriorityKind.UNKNOWN, raw="")

    raw = priority.strip()
    lower = raw.lower()

    if lower == "required":
        return PriorityRule(kind=PriorityKind.REQUIRED, raw=raw)
    if lower == "optional":
        return PriorityRule(kind=PriorityKind.OPTIONAL, raw=raw)
    if lower == "required-or-derivable":
        return PriorityRule(kind=PriorityKind.REQUIRED_OR_DERIVABLE, raw=raw)

    # Order matters: check "*-present" first so "X-Y-present" doesn't get
    # parsed as field=X-Y, value=present by the more permissive value regex.
    m = _FIELD_PRESENT_RE.match(raw)
    if m:
        return PriorityRule(
            kind=PriorityKind.REQUIRED_WHEN_FIELD_PRESENT,
            raw=raw,
            field_name=m.group(1),
        )

    # Required-when-<Field>-<value>  (Field uses CamelCase, value is a token)
    m = _FIELD_VALUE_RE.match(raw)
    if m:
        return PriorityRule(
            kind=PriorityKind.REQUIRED_WHEN_FIELD_VALUE,
            raw=raw,
            field_name=m.group(1),
            field_value=m.group(2),
        )

    # Recommended-for-<context> | Recommended-when-<context>
    m = _RECOMMENDED_RE.match(raw)
    if m:
        return PriorityRule(
            kind=PriorityKind.RECOMMENDED,
            raw=raw,
            context=m.group(1),
        )

    # Required-for-<context> | Required-when-<context>
    m = _REQUIRED_FOR_RE.match(raw)
    if m:
        return PriorityRule(
            kind=PriorityKind.REQUIRED_FOR_CONTEXT,
            raw=raw,
            context=m.group(1),
        )

    return PriorityRule(kind=PriorityKind.UNKNOWN, raw=raw)


# =============================================================================
# Validation results
# =============================================================================

class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    severity: Severity
    code: str
    message: str
    item: str | None = None
    field: str | None = None


@dataclass
class ValidationResult:
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    info: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, err: ValidationError) -> None:
        target = {
            Severity.ERROR: self.errors,
            Severity.WARNING: self.warnings,
            Severity.INFO: self.info,
        }[err.severity]
        target.append(err)

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)


# =============================================================================
# Element-level validation
# =============================================================================

def validate_element(element: RoPElement) -> ValidationResult:
    """Validate a single RoPElement.

    Pydantic has already validated structural correctness; this layer adds
    semantic checks that span fields (e.g., embedding present iff search_text
    present).
    """
    result = ValidationResult()

    if element.embedding is not None and not element.search_text:
        result.add(
            ValidationError(
                severity=Severity.WARNING,
                code="EMBEDDING_WITHOUT_SEARCH_TEXT",
                message="embedding is set but search_text is empty; "
                        "downstream consumers cannot reproduce the embedding",
                item=element.item,
                field="search_text",
            )
        )

    if element.replaced_by_rop_id is not None and element.is_active:
        result.add(
            ValidationError(
                severity=Severity.ERROR,
                code="ACTIVE_BUT_REPLACED",
                message="replaced_by_rop_id is set but is_active is True",
                item=element.item,
                field="is_active",
            )
        )

    # v2026.04: unit_of_measure required when item_type=numeric and bounds populated
    _validate_unit_required_when_numeric(element, result)
    # v2026.04: numeric_precision only meaningful for numeric item types
    _validate_numeric_precision_consistency(element, result)
    # v2026.04: cardinality consistency with values column
    _validate_cardinality_consistency(element, result)

    return result


def _validate_unit_required_when_numeric(
    element: RoPElement, result: ValidationResult
) -> None:
    """Numeric CDEs with plausibility bounds must declare a unit.

    Rationale: an unbounded numeric CDE may be unitless (e.g., a count).
    Once you assert plausibility bounds (min/max), the bounds are unit-bearing
    and the unit must be explicit. Otherwise a downstream consumer cannot
    interpret the bounds.
    """
    item_type = element.item_type
    if hasattr(item_type, "value"):
        item_type = item_type.value
    if item_type != "numeric":
        return

    has_bounds = element.plausible_min is not None or element.plausible_max is not None
    if has_bounds and not element.unit_of_measure:
        result.add(
            ValidationError(
                severity=Severity.ERROR,
                code="NUMERIC_BOUNDS_WITHOUT_UNIT",
                message=(
                    "item_type=numeric with plausible_min/max populated requires "
                    "unit_of_measure. Bounds are unit-bearing; consumers cannot "
                    "interpret them without an explicit unit."
                ),
                item=element.item,
                field="unit_of_measure",
            )
        )


def _validate_numeric_precision_consistency(
    element: RoPElement, result: ValidationResult
) -> None:
    """numeric_precision only applies to numeric item types."""
    if element.numeric_precision is None:
        return
    item_type = element.item_type
    if hasattr(item_type, "value"):
        item_type = item_type.value
    if item_type != "numeric":
        result.add(
            ValidationError(
                severity=Severity.WARNING,
                code="NUMERIC_PRECISION_ON_NON_NUMERIC",
                message=(
                    f"numeric_precision is set ({element.numeric_precision}) but "
                    f"item_type={item_type!r} is not numeric. Field will be ignored."
                ),
                item=element.item,
                field="numeric_precision",
            )
        )


def _validate_cardinality_consistency(
    element: RoPElement, result: ValidationResult
) -> None:
    """Multi-valued CDEs should use pipe ('|') as canonical delimiter.

    For cardinality=multiple/unbounded, if values is populated and contains
    suspicious delimiter characters (comma, semicolon outside the standard
    enum-list pattern) without any pipe, emit an INFO advisory. Genuine
    enum-list values like "0|1|NA|prodromal" are recognized by pipe presence.
    """
    cardinality = element.cardinality
    if hasattr(cardinality, "value"):
        cardinality = cardinality.value
    if cardinality == "single":
        return  # No delimiter convention to enforce

    values = element.values
    if not values:
        return  # No values to inspect

    has_pipe = "|" in values
    has_suspicious_delimiter = any(
        d in values for d in (";", ", ")  # ", " catches comma-space, not "0,1"
    )
    if has_suspicious_delimiter and not has_pipe:
        result.add(
            ValidationError(
                severity=Severity.INFO,
                code="CARDINALITY_DELIMITER_CONVENTION",
                message=(
                    f"cardinality={cardinality!r} but values contains semicolon or "
                    f"comma-space without pipe. RoP enforces pipe ('|') as canonical "
                    f"delimiter for multi-valued CDEs. Ingest pipelines should "
                    f"normalize source delimiters to pipe."
                ),
                item=element.item,
                field="values",
            )
        )


# =============================================================================
# Collection-level validation
# =============================================================================

@dataclass
class CollectionContext:
    """Context for validating a submission against the contract.

    Carries the set of fields actually populated in the submission (so
    conditional-required rules can resolve "Required-when-X-Y") plus
    descriptive flags about the cohort (longitudinal? genetic? tissue
    biosamples? non-human samples? cross-cohort? sharing-ready?
    has data assets?).
    """

    populated_fields: set[str]
    field_values: dict[str, Any]
    is_longitudinal: bool = False
    is_genetic_cohort: bool = False
    is_cross_cohort: bool = False
    has_biosamples: bool = False
    has_tissue_biosamples: bool = False
    has_cell_isolate_biosamples: bool = False
    has_non_human_biosamples: bool = False
    has_omics_data: bool = False
    has_genomic_data: bool = False
    has_paired_organ_tissues: bool = False
    requires_sharing_ready: bool = False  # If True, governance tier required
    has_data_assets: bool = False  # Cohort references external data files
    has_indexable_data_assets: bool = False  # VCF/BAM/CRAM/etc. needing index files
    has_genomic_data_assets: bool = False  # Asset types needing reference assembly
    has_pedigree: bool = False  # Cohort includes family/pedigree information
    has_mz_twins: bool = False  # Cohort includes monozygotic twins
    has_dz_twins: bool = False  # Cohort includes dizygotic twins
    has_summary_stats: bool = False  # Submission includes summary stats datasets
    has_meta_analysis: bool = False  # Summary stats are from meta-analysis
    has_case_control: bool = False  # Summary stats are case-control design
    has_variant_level_summary_stats: bool = False  # GWAS/QTL variant-level results
    has_pca_loadings: bool = False  # Component loadings from PCA
    has_projected_loadings: bool = False  # Loadings projected from external reference
    has_component_loadings: bool = False  # Any component loadings dataset


def validate_collection(
    elements: Iterable[RoPElement],
    context: CollectionContext,
    registry: AnchorRegistry | None = None,
) -> ValidationResult:
    """Validate an entire collection submission against the contract.

    Performs:
      1. Per-element structural validation (§2)
      2. Anchor coverage check: are mandatory anchors present?
      3. Conditional-required resolution against the supplied context
      4. Cross-field consistency checks

    Returns a ValidationResult aggregating all findings. Empty result.errors
    means the submission is RoP-conformant (§10).
    """
    if registry is None:
        registry = load_anchors()

    result = ValidationResult()
    elements_list = list(elements)

    # 1. Element-level structural validation
    for elem in elements_list:
        result.merge(validate_element(elem))

    # 2 & 3. Anchor coverage + conditional-required
    populated = context.populated_fields
    for anchor in registry.by_item.values():
        rule = parse_priority_rule(anchor.priority)
        is_required = _is_anchor_required(rule, anchor, context)
        is_present = anchor.item in populated

        if is_required and not is_present:
            result.add(
                ValidationError(
                    severity=Severity.ERROR,
                    code="ANCHOR_MISSING",
                    message=(
                        f"Anchor '{anchor.item}' is required for this submission "
                        f"(rule: {rule.kind.value} / {rule.raw}) but was not found"
                    ),
                    item=anchor.item,
                )
            )

    # 4. Cross-field consistency
    _check_companion_field_rules(context, registry, result)
    _check_time_anchor_derivability(context, result)
    _check_biosample_lineage(context, elements_list, result)

    return result


def _is_anchor_required(
    rule: PriorityRule,
    anchor: Any,
    context: CollectionContext,
) -> bool:
    """Resolve whether an anchor is required given the submission context."""
    kind = rule.kind

    if kind == PriorityKind.REQUIRED:
        return True
    if kind == PriorityKind.OPTIONAL:
        return False
    if kind == PriorityKind.REQUIRED_OR_DERIVABLE:
        # Derivability checked separately by _check_time_anchor_derivability;
        # we treat this as soft-required for the coverage check
        return False
    if kind == PriorityKind.RECOMMENDED:
        return False

    if kind == PriorityKind.REQUIRED_WHEN_FIELD_VALUE:
        # e.g. "Required-when-IsBiosample-true" — required iff context has
        # IsBiosample populated AND its value matches
        fname = rule.field_name
        fval = (rule.field_value or "").lower()
        actual = context.field_values.get(fname)
        if actual is None:
            return False
        return str(actual).lower() == fval

    if kind == PriorityKind.REQUIRED_WHEN_FIELD_PRESENT:
        fname = rule.field_name or ""
        # Check both literal field-presence and known context flags
        if fname in context.populated_fields:
            return True
        # Map common semantic phrases to context flags
        if "genetic-ancestry" in fname:
            return any(
                f.startswith("AncestryGenetic")
                for f in context.populated_fields
            )
        if "data-asset" in fname:
            return context.has_data_assets
        if "pedigree" in fname:
            return context.has_pedigree
        if "summary-stats" in fname or "summary_stats" in fname:
            return context.has_summary_stats
        return False

    if kind == PriorityKind.REQUIRED_FOR_CONTEXT:
        ctx = (rule.context or "").lower()
        if "longitudinal" in ctx:
            return context.is_longitudinal
        if "genetic-cohort" in ctx or ("genetic" in ctx and "data-asset" not in ctx):
            return context.is_genetic_cohort
        if "tissue-biosample" in ctx:
            return context.has_tissue_biosamples
        if "cell-isolate" in ctx:
            return context.has_cell_isolate_biosamples
        if "paired-organ" in ctx:
            return context.has_paired_organ_tissues
        if "non-human" in ctx:
            return context.has_non_human_biosamples
        if "omics-data" in ctx:
            return context.has_omics_data
        if "genomic" in ctx and "data-asset" not in ctx and "summary-stats" not in ctx:
            return context.has_genomic_data
        if "data-asset-indexable" in ctx:
            return context.has_indexable_data_assets
        if "data-asset-genomic" in ctx:
            return context.has_genomic_data_assets
        if "data-asset" in ctx:
            return context.has_data_assets
        if "cross-cohort" in ctx:
            return context.is_cross_cohort
        if "sharing-ready" in ctx or "re-share" in ctx or "redistribute" in ctx:
            return context.requires_sharing_ready
        # Pedigree contexts
        if "pedigree" in ctx:
            return context.has_pedigree
        if "mz-twin" in ctx or "monozygotic" in ctx:
            return context.has_mz_twins
        if "dz-twin" in ctx or "dizygotic" in ctx:
            return context.has_dz_twins
        # Summary stats contexts
        if "meta-analysis" in ctx:
            return context.has_meta_analysis
        if "case-control" in ctx:
            return context.has_case_control
        if "variant-level-summary" in ctx or "variant-level" in ctx:
            return context.has_variant_level_summary_stats
        if "summary-stats-dataset" in ctx or "summary-stats" in ctx:
            return context.has_summary_stats
        if "pca-loadings" in ctx:
            return context.has_pca_loadings
        if "projected-loadings" in ctx:
            return context.has_projected_loadings
        if "component-loadings-dataset" in ctx or "component-loadings" in ctx:
            return context.has_component_loadings
        return False

    return False


def _check_companion_field_rules(
    context: CollectionContext,
    registry: AnchorRegistry,
    result: ValidationResult,
) -> None:
    """Enforce companion_fields rules from anchor metadata."""
    populated = context.populated_fields
    for anchor in registry.by_item.values():
        if not anchor.metadata_:
            continue
        companions = anchor.metadata_.get("companion_fields") or []
        if not isinstance(companions, list):
            continue
        if anchor.item not in populated:
            continue
        for companion in companions:
            if companion not in populated:
                result.add(
                    ValidationError(
                        severity=Severity.WARNING,
                        code="MISSING_COMPANION_FIELD",
                        message=(
                            f"'{anchor.item}' is populated but its companion "
                            f"field '{companion}' is missing; some downstream "
                            f"analyses will be unable to use this row"
                        ),
                        item=anchor.item,
                        field=companion,
                    )
                )


def _check_time_anchor_derivability(
    context: CollectionContext,
    result: ValidationResult,
) -> None:
    """For longitudinal cohorts, ensure all time representations are derivable."""
    if not context.is_longitudinal:
        return

    populated = context.populated_fields
    has_baseline = "VisitBaselineDate" in populated
    has_date = "VisitDate" in populated
    has_number = "VisitNumber" in populated
    has_years = "YearsFromEnrollment" in populated

    # We need at least baseline + one of the three representations
    if not has_baseline:
        result.add(
            ValidationError(
                severity=Severity.ERROR,
                code="NO_TIME_BASELINE",
                message=(
                    "Longitudinal cohort lacks VisitBaselineDate; without it "
                    "the three time representations cannot be inter-converted"
                ),
                field="VisitBaselineDate",
            )
        )

    if has_baseline and not (has_date or has_number or has_years):
        result.add(
            ValidationError(
                severity=Severity.ERROR,
                code="NO_TIME_REPRESENTATION",
                message=(
                    "Longitudinal cohort has VisitBaselineDate but no concrete "
                    "time representation (VisitDate, VisitNumber, or "
                    "YearsFromEnrollment)"
                ),
            )
        )


def _check_biosample_lineage(
    context: CollectionContext,
    elements: list[RoPElement],
    result: ValidationResult,
) -> None:
    """Placeholder for biosample lineage validation.

    The full implementation walks the parent_biosample_id graph and verifies
    that all aliquots resolve to a top-level biosample with consistent
    SubjectID and SampleTypeControlled. The graph traversal lives in a
    separate module (rop.lineage) once it's wired up; for the v0.1 scaffold
    we only emit an INFO-level note.
    """
    if not context.has_biosamples:
        return

    result.add(
        ValidationError(
            severity=Severity.INFO,
            code="LINEAGE_CHECK_DEFERRED",
            message=(
                "Biosample lineage validation is not yet implemented in v0.1; "
                "graph-shaped consistency checks (parent ID resolution, "
                "subject-sample-visit triples) will land in v0.2"
            ),
        )
    )
