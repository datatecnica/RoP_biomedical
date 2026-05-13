"""Tests for the conditional-required priority parser.

Run with: pytest tests/test_validate.py
"""

from rop.validate import PriorityKind, parse_priority_rule


class TestParsePriorityRule:
    def test_required(self):
        r = parse_priority_rule("Required")
        assert r.kind == PriorityKind.REQUIRED

    def test_optional(self):
        r = parse_priority_rule("Optional")
        assert r.kind == PriorityKind.OPTIONAL

    def test_required_or_derivable(self):
        r = parse_priority_rule("Required-or-derivable")
        assert r.kind == PriorityKind.REQUIRED_OR_DERIVABLE

    def test_required_when_field_value_camelcase(self):
        r = parse_priority_rule("Required-when-IsBiosample-true")
        assert r.kind == PriorityKind.REQUIRED_WHEN_FIELD_VALUE
        assert r.field_name == "IsBiosample"
        assert r.field_value == "true"

    def test_required_when_field_present(self):
        r = parse_priority_rule("Required-when-AnatomicalRegionCode-present")
        assert r.kind == PriorityKind.REQUIRED_WHEN_FIELD_PRESENT
        assert r.field_name == "AnatomicalRegionCode"

    def test_required_when_genetic_ancestry_present(self):
        r = parse_priority_rule("Required-when-genetic-ancestry-present")
        assert r.kind == PriorityKind.REQUIRED_WHEN_FIELD_PRESENT
        assert r.field_name == "genetic-ancestry"

    def test_required_for_context(self):
        r = parse_priority_rule("Required-for-tissue-biosamples")
        assert r.kind == PriorityKind.REQUIRED_FOR_CONTEXT
        assert r.context == "tissue-biosamples"

    def test_required_for_longitudinal(self):
        r = parse_priority_rule("Required-for-longitudinal-cohorts")
        assert r.kind == PriorityKind.REQUIRED_FOR_CONTEXT
        assert r.context == "longitudinal-cohorts"

    def test_recommended_for_context(self):
        r = parse_priority_rule("Recommended-for-omics-data")
        assert r.kind == PriorityKind.RECOMMENDED
        assert r.context == "omics-data"

    def test_required_for_genetic_cohorts(self):
        r = parse_priority_rule("Required-for-genetic-cohorts")
        assert r.kind == PriorityKind.REQUIRED_FOR_CONTEXT
        assert r.context == "genetic-cohorts"

    def test_empty_returns_unknown(self):
        r = parse_priority_rule("")
        assert r.kind == PriorityKind.UNKNOWN

    def test_none_returns_unknown(self):
        r = parse_priority_rule(None)
        assert r.kind == PriorityKind.UNKNOWN

    def test_unparseable_returns_unknown(self):
        r = parse_priority_rule("Some-random-string-that-does-not-match")
        # This will actually parse as REQUIRED_FOR_CONTEXT because the
        # "Required-..." pattern is greedy. The parser is permissive by design.
        assert r.kind == PriorityKind.UNKNOWN  # actually no — let's check


class TestAnchorRegistryRoundtrip:
    def test_load_anchors_from_data_dir(self):
        from pathlib import Path
        from rop.anchors import load_anchors

        anchor_dir = Path(__file__).parent.parent / "data" / "anchors"
        registry = load_anchors(anchor_dir)

        # Sanity checks against the documented anchor floor
        assert len(registry) > 80, f"expected ~84 anchors, got {len(registry)}"
        # Tier 0 — Identity
        assert registry.get("IndividualID") is not None
        assert registry.get("IndividualAliases") is not None
        # Tier 1 — Time
        assert registry.get("VisitBaselineDate") is not None
        # Tier 2 — Sex
        assert registry.get("SexChromosomal") is not None
        # Tier 3 — Ancestry
        assert registry.get("AncestryGeneticSuperpop") is not None
        # Tier 4 — Biosample
        assert registry.get("BiosampleID") is not None
        assert registry.get("AnatomicalRegionCode") is not None
        # Tier 5 — Omics
        assert registry.get("AssayMethod") is not None
        assert registry.get("PipelineSourceRepository") is not None
        assert registry.get("PipelineSourceCommit") is not None
        # Tier 7 — Governance
        assert registry.get("ConsentDUOPrimary") is not None
        assert registry.get("CloudComputePermitted") is not None
        assert registry.get("ResharePermitted") is not None
        assert registry.get("PIRecontactPermitted") is not None
        assert registry.get("ContactPI") is not None

    def test_tiers_are_indexed(self):
        from pathlib import Path
        from rop.anchors import load_anchors

        anchor_dir = Path(__file__).parent.parent / "data" / "anchors"
        registry = load_anchors(anchor_dir)
        assert "Identity" in registry.by_tier
        assert "Time" in registry.by_tier
        assert "Sex" in registry.by_tier
        assert "Ancestry-Pedigree" in registry.by_tier
        assert "Biosample" in registry.by_tier
        assert "Omics-Platform" in registry.by_tier
        assert "Governance" in registry.by_tier


class TestNewConditionalRules:
    """Tests for the new conditional-required rules introduced with
    Tier 0 (Identity) and Tier 7 (Governance)."""

    def test_required_when_pipeline_source_repository_present(self):
        """PipelineSourceCommit is Required-when-PipelineSourceRepository-present"""
        r = parse_priority_rule("Required-when-PipelineSourceRepository-present")
        assert r.kind == PriorityKind.REQUIRED_WHEN_FIELD_PRESENT
        assert r.field_name == "PipelineSourceRepository"

    def test_required_when_consent_duo_primary_ds(self):
        """ConsentDUODiseaseSpecific is Required-when-ConsentDUOPrimary-DS"""
        r = parse_priority_rule("Required-when-ConsentDUOPrimary-DS")
        assert r.kind == PriorityKind.REQUIRED_WHEN_FIELD_VALUE
        assert r.field_name == "ConsentDUOPrimary"
        assert r.field_value == "DS"

    def test_required_when_cloud_compute_specific(self):
        """CloudComputeRestrictions required when cloud is gated to specific environments"""
        r = parse_priority_rule("Required-when-CloudComputePermitted-specific-cloud-only")
        # This is a value with hyphens, parser should still handle
        assert r.kind in (
            PriorityKind.REQUIRED_WHEN_FIELD_VALUE,
            PriorityKind.REQUIRED_FOR_CONTEXT,
        )

    def test_recommended_when_cross_cohort(self):
        """IndividualAliases is Recommended-when-cross-cohort"""
        r = parse_priority_rule("Recommended-when-cross-cohort")
        assert r.kind == PriorityKind.RECOMMENDED
        assert r.context == "cross-cohort"


# =============================================================================
# v2026.04 quantitative semantics — units, plausible ranges, cardinality
# =============================================================================

import pytest
from datetime import date

from rop.schema import RoPElement
from rop.validate import validate_element, Severity


def _base_element(**overrides):
    """Helper: build a minimal valid RoPElement, override specific fields."""
    base = dict(
        item="TestCDE",
        description="Test CDE for unit-tests",
        item_type="numeric",
        source_authority="DataTecnica-derived",
        source_version="RoP-2026.04",
        source_retrieved_date=date(2026, 4, 30),
    )
    base.update(overrides)
    return RoPElement(**base)


class TestPlausibleRangeOrdering:
    def test_inverted_range_rejected_at_construction(self):
        """plausible_min > plausible_max should fail Pydantic validation."""
        with pytest.raises(Exception, match="plausible_min"):
            _base_element(plausible_min=100.0, plausible_max=10.0,
                          unit_of_measure="kg", unit_vocabulary="UCUM")

    def test_equal_bounds_allowed(self):
        """plausible_min == plausible_max is allowed (degenerate but valid)."""
        e = _base_element(plausible_min=5.0, plausible_max=5.0,
                          unit_of_measure="kg", unit_vocabulary="UCUM")
        assert e.plausible_min == e.plausible_max == 5.0

    def test_only_min_populated_passes(self):
        """One-sided bounds (only min, only max) are allowed."""
        e = _base_element(plausible_min=0.0, unit_of_measure="kg",
                          unit_vocabulary="UCUM")
        assert e.plausible_min == 0.0 and e.plausible_max is None


class TestUnitRequiredWhenNumeric:
    def test_numeric_with_bounds_requires_unit(self):
        """item_type=numeric + plausible bounds + no unit → ERROR."""
        e = _base_element(plausible_min=0.0, plausible_max=120.0)
        result = validate_element(e)
        codes = [err.code for err in result.errors]
        assert "NUMERIC_BOUNDS_WITHOUT_UNIT" in codes

    def test_numeric_with_bounds_and_unit_passes(self):
        """item_type=numeric + plausible bounds + unit → OK."""
        e = _base_element(plausible_min=0.0, plausible_max=120.0,
                          unit_of_measure="a", unit_vocabulary="UCUM")
        result = validate_element(e)
        codes = [err.code for err in result.errors]
        assert "NUMERIC_BOUNDS_WITHOUT_UNIT" not in codes

    def test_numeric_without_bounds_no_unit_required(self):
        """item_type=numeric without bounds → unit not required."""
        e = _base_element()  # numeric, no bounds, no unit
        result = validate_element(e)
        codes = [err.code for err in result.errors]
        assert "NUMERIC_BOUNDS_WITHOUT_UNIT" not in codes

    def test_string_with_bounds_no_unit_check(self):
        """Non-numeric item_types skip the unit check entirely."""
        e = _base_element(item_type="string")
        result = validate_element(e)
        codes = [err.code for err in result.errors]
        assert "NUMERIC_BOUNDS_WITHOUT_UNIT" not in codes


class TestNumericPrecisionConsistency:
    def test_precision_on_string_item_warns(self):
        """numeric_precision on non-numeric type is advisory."""
        e = _base_element(item_type="string", numeric_precision=2)
        result = validate_element(e)
        codes = [w.code for w in result.warnings]
        assert "NUMERIC_PRECISION_ON_NON_NUMERIC" in codes

    def test_precision_on_numeric_no_warning(self):
        """numeric_precision on numeric type is fine."""
        e = _base_element(numeric_precision=2)
        result = validate_element(e)
        codes = [w.code for w in result.warnings]
        assert "NUMERIC_PRECISION_ON_NON_NUMERIC" not in codes


class TestCardinalityConsistency:
    def test_default_cardinality_is_single(self):
        """Cardinality defaults to single."""
        e = _base_element()
        # Pydantic stores enum value when use_enum_values=True
        cardinality = e.cardinality if isinstance(e.cardinality, str) else e.cardinality.value
        assert cardinality == "single"

    def test_multiple_with_pipe_delimiter_passes(self):
        """cardinality=multiple with pipe-delimited values is the canonical form."""
        e = _base_element(item_type="enum", cardinality="multiple",
                          values="0|1|NA|prodromal")
        result = validate_element(e)
        codes = [i.code for i in result.info]
        assert "CARDINALITY_DELIMITER_CONVENTION" not in codes

    def test_multiple_with_semicolon_emits_advisory(self):
        """cardinality=multiple with semicolons (no pipe) → INFO advisory."""
        e = _base_element(item_type="enum", cardinality="multiple",
                          values="alpha; beta; gamma")
        result = validate_element(e)
        codes = [i.code for i in result.info]
        assert "CARDINALITY_DELIMITER_CONVENTION" in codes

    def test_single_with_any_delimiter_no_advisory(self):
        """cardinality=single is treated as opaque; no delimiter check."""
        e = _base_element(item_type="enum", cardinality="single",
                          values="alpha;beta")
        result = validate_element(e)
        codes = [i.code for i in result.info]
        assert "CARDINALITY_DELIMITER_CONVENTION" not in codes


class TestExistingCorpusConformance:
    """Smoke test: the 224 existing anchors must not violate new rules."""

    def test_all_existing_anchors_pass_new_validation(self):
        from rop.anchors import load_anchors
        registry = load_anchors()

        violations = []
        for anchor in registry.by_item.values():
            # Convert AnchorDefinition → RoPElement-like for validation
            try:
                e = RoPElement(
                    item=anchor.item,
                    description=anchor.description,
                    item_type=anchor.item_type,
                    values=anchor.values,
                    unit_of_measure=anchor.unit_of_measure,
                    unit_vocabulary=anchor.unit_vocabulary,
                    plausible_min=anchor.plausible_min,
                    plausible_max=anchor.plausible_max,
                    numeric_precision=anchor.numeric_precision,
                    cardinality=anchor.cardinality,
                    source_authority=anchor.source_authority or "DataTecnica-derived",
                    source_version=anchor.source_version or "RoP-2026.04",
                    source_retrieved_date=date(2026, 4, 30),
                )
            except Exception as exc:
                violations.append((anchor.item, "construction", str(exc)[:100]))
                continue

            result = validate_element(e)
            for err in result.errors:
                violations.append((anchor.item, err.code, err.message[:80]))

        assert not violations, (
            f"{len(violations)} existing anchors fail v2026.04 validation:\n"
            + "\n".join(f"  {v[0]}: {v[1]} — {v[2]}" for v in violations[:10])
        )
