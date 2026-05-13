# Non-Standard OMOP Concepts in RoP v2026.04

## Background

OMOP vocabularies distinguish between **standard** and **non-standard** concepts:

- **Standard concepts** (`standard_concept='S'`): Canonical terms used for analysis
  - ~1.2M standard concepts in Athena May 2026 release
  - Examples: SNOMED CT preferred terms, LOINC codes, RxNorm ingredients

- **Non-standard concepts** (`standard_concept != 'S'`): Legacy codes, synonyms, deprecated terms
  - ~8.8M non-standard concepts
  - Examples: ICD-10-CM billing codes, legacy drug names, retired SNOMED terms
  - Each has a "Maps to" relationship to one or more standard concepts

## Design Decision: Option B — Embed `alternate_codes` in Elements Table

**Date:** Saturday, May 3, 2026
**Decision maker:** Mike Nalls
**Context:** Sprint 1 dedup pass implementation

### Options Considered

**Option A:** Separate crosswalks table
- Normalized schema: `elements` + `alternate_codes` tables
- Requires JOINs for Forge lookups
- Better for write-heavy workloads

**Option B:** Embed `alternate_codes` JSONB in elements table ✅ **SELECTED**
- Single-table lookups in Forge
- Trade: larger row size for faster reads
- JSONB array field on `RoPElement` schema

### Rationale

Forge's primary use case is **read-heavy lookups** where users search by ICD-10, legacy drug codes, or deprecated terms and need to resolve to the canonical RoP element. Single-table queries are critical for sub-100ms response times at scale.

### Implementation

#### Schema Addition (`rop/schema.py`)

```python
class RoPElement(BaseModel):
    # ... existing fields ...

    alternate_codes: list[dict[str, str]] = Field(
        default_factory=list,
        description="Non-standard codes that map to this standard concept. "
                    "Format: [{\"vocabulary\": \"ICD10CM\", \"code\": \"E11.9\"}, ...]. "
                    "Populated from Athena Maps-to relationships during dedup.",
    )
```

#### Dedup Pass Aggregation (`scripts/sprint1_dedup_pass1.py`)

Athena CONCEPT_RELATIONSHIP "Maps to" edges are extracted and aggregated:

```sql
-- Extract Maps-to edges (non-standard → standard)
SELECT
    'OMOP' AS src_authority,
    CAST(c1.concept_code AS VARCHAR) AS src_code,
    c1.vocabulary_id AS src_vocab,
    c2.concept_id AS target_concept_id,
    'omop_maps_to' AS evidence
FROM concept_relationship cr
JOIN concept c1 ON cr.concept_id_1 = c1.concept_id
JOIN concept c2 ON cr.concept_id_2 = c2.concept_id
WHERE cr.relationship_id = 'Maps to'
  AND c1.standard_concept != 'S'  -- Only non-standard sources
  AND c2.standard_concept = 'S'   -- Only standard targets

-- Aggregate into alternate_codes array per target concept_id
SELECT
    target_concept_id,
    LIST(DISTINCT STRUCT_PACK(
        vocabulary := src_vocab,
        code := src_code
    )) AS alternate_codes
FROM athena_maps_to_edges
GROUP BY target_concept_id
```

## Statistics (v2026.04-foundation)

From Saturday May 3, 2026 dedup run:

- **Total deduplicated elements:** 1,326,063
- **Elements with alternate_codes:** 11,455 (0.9%)
- **Athena Maps-to edges extracted:** 49,392
- **Most common vocabularies in alternate_codes:**
  - ICD10CM (International Classification of Diseases, 10th Revision, Clinical Modification)
  - ICD10PCS (ICD-10 Procedure Coding System)
  - ICD9CM (ICD-9, Clinical Modification — legacy)
  - Read (UK primary care codes — deprecated)
  - HCPCS (Healthcare Common Procedure Coding System)

## Source Exclusivity

**IMPORTANT:** `alternate_codes` are **only** populated from Athena OMOP vocabularies. Other sources (Mondo, HPO, NINDS-CDE) provide cross-references that populate `equivalent_rop_ids` instead, not `alternate_codes`.

| Field | Source | Purpose |
|-------|--------|---------|
| `alternate_codes` | Athena Maps-to only | Non-standard billing/legacy codes → canonical RoP lookup |
| `equivalent_rop_ids` | Cross-source xrefs (Mondo/HPO/NINDS) | Same-concept mappings across vocabularies |
| `canonical_concept_id` | OMOP concept_id | Primary pivot for analytics |

## Forge Lookup Examples

### Query 1: Resolve ICD-10-CM code to RoP element

```sql
-- User searches for "E11.9" (Type 2 diabetes without complications)
SELECT *
FROM rop_elements
WHERE alternate_codes @> '[{"vocabulary": "ICD10CM", "code": "E11.9"}]'::jsonb;
```

### Query 2: Find all elements with ICD-10-CM alternates

```sql
SELECT
    rop_id,
    description,
    source_authority,
    source_code,
    jsonb_array_length(alternate_codes) AS num_alternates
FROM rop_elements
WHERE alternate_codes @> '[{"vocabulary": "ICD10CM"}]'::jsonb
ORDER BY num_alternates DESC;
```

### Query 3: Expand all alternate codes for a standard concept

```sql
-- Given a standard SNOMED concept, show all ICD-10/ICD-9 legacy codes
SELECT
    source_code AS standard_code,
    description,
    jsonb_array_elements(alternate_codes) AS alternate
FROM rop_elements
WHERE source_authority = 'OMOP'
  AND source_code = '201826'  -- Example SNOMED concept_id
  AND jsonb_array_length(alternate_codes) > 0;
```

## Performance Considerations

- **JSONB GIN index recommended** for `alternate_codes` column in Forge deployment
- **Median alternate_codes array size:** 4 entries (based on Athena May 2026)
- **Max observed:** 37 alternate codes for a single standard concept (common chronic conditions)
- **Storage overhead:** ~2KB per element with alternates (negligible vs embedding vectors at 3KB each)

## License Hygiene

All alternate codes come from **open vocabularies** in Athena:
- ICD-10-CM/PCS: Public domain (WHO/CMS)
- ICD-9-CM: Public domain
- HCPCS: Public domain (CMS)
- RxNorm: Public domain (NLM)
- Read codes: Open under NHS terms

**Excluded from RoP** (not in Athena selection):
- SNOMED CT (IHTSDO license required for redistribution)
- MedDRA (MSSO license required)
- CPT-4 (AMA license required)

This ensures the v2026.04 bundle remains fully open-source redistributable under Apache-2.0 + CC-BY-4.0.

## References

- OHDSI Athena: https://athena.ohdsi.org
- OMOP CDM Vocabulary Conventions: https://ohdsi.github.io/CommonDataModel/cdm54.html#vocabulary_tables
- RoP schema.py: `rop/schema.py` lines 49-54
- Dedup implementation: `scripts/sprint1_dedup_pass1.py` lines 150-180
