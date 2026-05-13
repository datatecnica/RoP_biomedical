# Harmonization Issues to Watch For

Critical review of the v2026.04 design with boutique CDE integration in mind. Each issue is something likely to surface during the ~4K boutique CDE evaluation; some are genuine spec gaps, others are guidance the curator team needs.

## Critical (fix before spec freeze)

### 1. Missing-data conventions are not specified

**STATUS: ✅ Resolved in v2026.04** — added `missing_value_convention` column to RoPElement (SPEC §2.2.1). Default convention is `null`/`NA`. Numeric sentinels (`-9`, `-99`, `999`) prohibited in conformant data.

**Original issue**: RoPElement had no documented sentinel for missing values. Boutique CDEs from various NIH cohorts use `-9`, `99`, `999`, `-1`, empty string, "Missing", "N/A", "NK", "Unknown", and null interchangeably. Without a canonical RoP convention, ingest pipelines have to make ad-hoc decisions.

**Fix**: Add a top-level RoPElement field `missing_value_convention` (string) and a SPEC §13 "Missing data" section documenting:
- Default: `null` (or `NA` in tabular exports)
- Numeric sentinels (-9, -99) prohibited in RoP-conformant data
- "Unknown", "Not Reported", "Not Assessed" as distinct values when the controlled vocabulary distinguishes them
- Tier 0a `PedigreePhenotypeStatus` already specifies NA correctly; pattern should be uniform

### 2. Units of measurement have no canonical home

**STATUS: ✅ Resolved in v2026.04** — added `unit_of_measure` and `unit_vocabulary` columns (SPEC §2.2.1). Required-when rule: `unit_of_measure` mandatory when `item_type=numeric` AND plausibility bounds populated. UCUM is the recommended vocabulary.

**Original issue**: A CDE called `Weight` could be kg or lb. `Age` could be years or months. `Glucose` could be mg/dL or mmol/L. RoP had no dedicated `unit` field on RoPElement; the only place to record it was `metadata_.unit` by convention, which was not enforced. Most boutique CDEs do not record unit explicitly.

### 3. Numeric range constraints are inline string-encoded

**STATUS: ✅ Resolved in v2026.04** — added `plausible_min`, `plausible_max`, `numeric_precision` columns (SPEC §2.2.1). DB-level CHECK constraint enforces `plausible_min ≤ plausible_max`. Inline range strings in `values` remain supported for backward compatibility.

**Original issue**: `values` field carried `"0..120"` for numeric ranges. Parsers had to interpret. Boutique CDEs commonly had implicit range expectations (`Age` is implicitly 0-120) that weren't recorded.

**Scope clarification**: plausibility bounds for outlier and unit-error detection only — **not** clinical reference ranges. Clinical ranges are policy/locality/sex/ancestry-specific and out of scope.

### 4. Cardinality is implicit

**STATUS: ✅ Resolved in v2026.04** — added `cardinality` column (SPEC §2.2.1) with values `single` / `multiple` / `unbounded` (default `single`). Pipe (`|`) is the canonical delimiter for multi-valued CDEs; ingest pipelines normalize source-data delimiters (comma, semicolon, whitespace) to pipe. Validation emits an INFO advisory when `cardinality=multiple/unbounded` but the `values` column shows non-pipe delimiters.

**Original issue**: A CDE like `MedicationName` may be single-valued (one drug) or multi-valued (current medications list). RoP's `item_type` did not distinguish. Boutique CDEs frequently use comma-separated strings for what should be array fields.

## Significant (resolve during boutique evaluation, not blocking spec freeze)

### 5. Effect-size encoding ambiguity in summary stats

**Issue**: Tier 9 `SummaryStatsType=GWAS-SNP` doesn't specify whether the underlying file uses beta+SE, OR+CI, log(OR), or effect_size+p_value. Different statistical software emits different conventions; meta-analysis requires consistency.

**Fix**: Add `SummaryStatsEffectMeasure` enum to Tier 9: `beta-SE | OR-CI | log-OR-SE | HR-CI | effect-size-pvalue | other`. Required for variant-level and gene-level summary stats. Document that GWAS Catalog harmonized format uses beta+SE as the canonical form.

### 6. Allele encoding for variant-level summary stats

**Issue**: Variant-level results need `effect_allele` and `other_allele` (or `non_effect_allele`) columns to be interpretable. RoP currently records this only at the file level via `SummaryStatsHarmonizedFormat`. A non-harmonized file might call them `A1/A2`, `REF/ALT`, `risk/non-risk`, etc.

**Fix**: Document in SPEC §7 (Bundle Format) that variant-level summary stats files referenced by Tier 9 must follow a documented column schema. Curator-pool guidance: if `SummaryStatsHarmonizedFormat=false`, the curator must populate `metadata_.column_mapping` describing the file's column convention.

### 7. Compound CDEs

**Issue**: Boutique CDEs from older NIH cohorts often have compound fields like `BloodPressure_120_80` (systolic_diastolic) or `Date_of_Onset_Year_Month` packed into one field. RoP's atomic CDE model requires these to be split, but boutique source data won't be pre-split.

**Fix**: Document in CONTRIBUTING.md a "Compound CDE Splitting" section: when a boutique CDE contains multiple values, the curator splits it into multiple RoP rows during ingest, with `metadata_.derived_from` pointing back to the original compound name. Curator workload note: budget extra time for compound splitting in the boutique evaluation.

### 8. Conditional-required dependencies between CDEs

**Issue**: Many boutique CDEs have rules like "if `Pregnancy=Yes` then `EstimatedDueDate` required" or "if `OnMedication_X=Yes` then `Dose_X` required". RoP's conditional-required grammar handles single field-value conditions but not chained dependencies or cross-CDE business rules.

**Fix**: Two-track approach. Simple cases (`Required-when-X-Y`) covered by current grammar. Complex business rules go in `metadata_.depends_on` as a JSON-Logic expression that downstream tools can interpret. Document that complex rules are advisory rather than gating in v2026.04 to avoid blocking ingest.

### 9. Reference ranges are deliberately out of scope

**Note**: Earlier drafts considered sex-specific or ancestry-specific clinical reference ranges (e.g., testosterone, hemoglobin, ferritin, creatinine). These are deliberately **out of scope** for v2026.04 because clinical reference ranges are policy-, locality-, sex-, ancestry-, and lab-specific, and properly belong to the consuming clinical analysis context rather than the data interoperability contract. RoP captures only `plausible_min`/`plausible_max` (issue #3 above) for catching clear data errors and unit mis-specification.

If a downstream consumer needs lab reference ranges, they apply them at analysis time using whatever clinical authority is appropriate for their use case (LOINC normal ranges, institutional lab standards, etc.). This is the same pattern as not encoding clinical decision rules in the data layer.

## Lower priority (track but don't fix yet)

### 10. Data quality / completeness flags at the row level

**Issue**: No canonical place to record per-row data quality (e.g., "this glucose measurement was flagged as suspect by the lab"). Boutique CDEs sometimes carry this as a parallel `flag_*` field per measurement.

**Recommendation**: Document the convention `metadata_.qc_status` with values `pass | warn | fail` and `metadata_.qc_notes` for free text. Don't promote to top-level until v2026.10.

### 11. Time zone handling

**Issue**: `CollectionDate` and similar date fields don't specify time zone. For most cohort analyses this doesn't matter (date-level granularity). For pharmacology and circadian studies it does.

**Recommendation**: Document that RoP dates are assumed local-civil-date unless `CollectionDateTime` (with timezone) is also populated. Add `CollectionDateTime` as an optional Tier 4 anchor in v2026.07.

### 12. Display vs storage format

**Issue**: A boutique CDE might be displayed as "Yes/No" in a CRF but stored as 1/0. RoP captures storage format only.

**Recommendation**: When boutique CDEs have explicit display/storage divergence, store the storage form and capture display labels in `metadata_.display_labels` as `{"1": "Yes", "0": "No"}`. Curator-pool guidance only; not a schema change.

### 13. Data type "ordinal" not in item_type enum

**Issue**: `item_type` enum is `numeric | string | date | enum | binary`. Many boutique scales (Likert, MoCA subscores, MDS-UPDRS items) are ordinal — discrete with order, but not arithmetic. RoP currently treats these as `enum` (loses order) or `numeric` (loses discreteness).

**Recommendation**: Add `ordinal` to `item_type` enum in v2026.07. Backward-compatible since downstream tools that don't recognize `ordinal` can fall back to treating it as `enum`.

### 14. Multi-language descriptions

**Issue**: Some boutique CDEs (especially GP2 contributions from non-English-language cohorts) have descriptions in source language plus English translation. RoP's `description` field is single-string.

**Recommendation**: Document the convention `metadata_.descriptions_by_lang` as `{"en": "...", "es": "...", "ja": "..."}`. Ingest pipelines for Spanish-language LATAM cohorts and Japanese cohorts will need this. Don't promote to top-level until external demand emerges.

## Boutique-specific harmonization risks

### 15. NACC UDS-3.0 has its own value coding conventions

**Issue**: NACC uses cohort-specific codes like `NACCAGE` (age, capped at 89) and discrete categorical encodings that differ from OMOP, LOINC, and HPO conventions. Path-ND boutique CDEs derived from NACC inherit these conventions.

**Mitigation**: Curator-pool guidance for NACC-derived rows: preserve NACC codes in `source_code` and provide harmonized values in `values` field. Equivalence claims to LOINC/OMOP rows include explicit value-mapping in `equivalent_rop_ids` metadata.

### 16. Cohort-specific PRS weights and locus annotations

**Issue**: PRS weight files and locus-level annotations from boutique GP2-internal analyses have file formats specific to internal pipelines that don't match GWAS Catalog standards.

**Mitigation**: Tier 9 `SummaryStatsHarmonizedFormat=false` covers this technically. Curator workload note: budget for converting internal PRS weights to PGS Catalog format if external publication is desired.

### 17. Naming convention drift across collections

**Issue**: Boutique collections from different eras and projects use different naming styles: `CamelCase` (newer), `snake_case` (older NIH), `ALL_CAPS` (legacy NACC), and mixed. RoP standard is CamelCase per the existing anchor naming.

**Mitigation**: Inventory step (Step 1 of boutique evaluation) normalizes names to CamelCase, preserves originals in `alternate_names`. Document the mapping rules so it's reproducible.

### 18. "Free text plus controlled vocab" pattern not consistently applied

**Issue**: RoP anchor design uses parallel free-text + controlled-vocab fields (e.g., `TissueSampleType` free text + `SampleTypeControlled` enum). Boutique CDEs typically have only one or the other.

**Mitigation**: During boutique ingest, derive the missing companion field where possible (LLM-assisted controlled-vocab mapping for free-text values; reverse lookup for orphan controlled codes). Curator review for ambiguous cases. Track derivation as `curation_status=auto-matched`.

## Recommended pre-spec-freeze additions — ✅ LANDED in v2026.04

Before v2026.04 ships, add these four schema fields to RoPElement:

```python
class RoPElement(BaseModel):
    # ... existing fields ...
    unit_of_measure: str | None = None
    unit_vocabulary: Literal["UCUM", "SNOMED-units", "free-text", None] = None
    cardinality: Literal["single", "multiple", "unbounded"] = "single"
    missing_value_convention: str | None = None  # default: "null"
    # Plausibility bounds for outlier and unit-error detection.
    # NOT clinical reference ranges (policy/locality/sex/ancestry-specific, out of scope).
    plausible_min: float | None = None
    plausible_max: float | None = None
    numeric_precision: int | None = None
```

These are additive to the existing schema, backward-compatible, and close the four critical gaps (#1-4) that would otherwise generate sustained curator pain during the boutique evaluation.

**Implementation summary** (v2026.04):

- All seven fields are present on `RoPElement` (Pydantic) and `AnchorDefinition` (dataclass)
- SQL migration adds the columns to the Forge `elements` extension (Section 5.5) with CHECK constraints for range ordering, cardinality enum, unit vocabulary enum, plus an index on `unit_of_measure`
- Three element-level validation rules in `rop.validate.validate_element`:
  - `NUMERIC_BOUNDS_WITHOUT_UNIT` (ERROR) — numeric CDE with bounds must declare unit
  - `NUMERIC_PRECISION_ON_NON_NUMERIC` (WARNING) — precision ignored on non-numeric types
  - `CARDINALITY_DELIMITER_CONVENTION` (INFO) — multi-valued CDE should use pipe delimiter
- Content hash payload extended to include all seven fields, so semantic changes propagate to hash
- 14 new test cases covering ordering, unit requirement, precision consistency, cardinality conventions, and full-corpus conformance
- 19 numeric anchors in the existing 224-anchor corpus populated with UCUM units and plausibility bounds — full pass against the corpus-conformance smoke test
- **Side effect caught by smoke test**: DICOM and BIDS added to the `SourceAuthority` enum (Theme 7 imaging anchors needed these as recognized authorities)

Total elapsed effort: ~2 hours as estimated, including the unit-population pass and the DICOM/BIDS gap fix.
