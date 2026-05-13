# RoP Specification

**Version**: 1.0-draft
**Status**: Working draft
**Target audience**: implementers, reviewers, downstream consumers

## 1. Scope

This document specifies the structure, semantics, and operational requirements of the RoP (Biomedical Reference of Parameters) interoperability contract. It is intended to be sufficient for an independent implementation of a RoP-compliant data store and validation layer, separate from The Forge.

### 1.1 What this specification defines

- The schema of a RoP element row, including required and optional columns
- The five Core Anchor tiers and their conditional-required validation rules
- The serialization formats for distributable RoP bundles (Parquet, FAISS, manifest)
- The provenance, versioning, and deprecation policies
- The semantics of cross-source-authority equivalence claims

### 1.2 What this specification does not define

- The internal architecture of The Forge or any other governance implementation
- Specific embedding model choices (recommended models are noted but not mandatory)
- Database vendor or storage backend (Postgres + pgvector and DuckDB are reference implementations)

## 2. Element Row Structure

A RoP element extends the standard Forge `elements` table with a documented set of additional columns. The full set:

### 2.1 Identity columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | UUID | yes | Database primary key, stable, never recycled |
| `rop_accession` | str(20) | yes | Public-facing stable identifier, format `RoP:NNNNNNN`, never recycled |
| `content_hash` | char(64) | yes | SHA-256 of canonicalized content payload (see §6) |
| `schema_id` | UUID | yes | FK to `schemas` table; for RoP rows, points to the canonical RoP schema record |

### 2.2 Standard CDE columns (inherited from Forge schema)

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `item` | str(255) | yes | Human-readable name, unique within schema |
| `description` | text | yes | Definition of the concept |
| `collection` | str(255) | no | Category within the schema (e.g., "Demographics", "Cognitive Assessments") |
| `item_type` | str(50) | no | One of: `numeric`, `string`, `date`, `enum`, `binary` |
| `values` | text | no | Inline pipe-delimited permitted values, or range expression |
| `value_set_ref` | text | no | Reference to a versioned ValueSet, format `<uuid>@<version>` |
| `alternate_names` | text | no | Pipe-separated synonyms |
| `priority` | str(50) | no | Validation priority; supports conditional-required syntax (see §4) |
| `sort_order` | int | no | Display order |
| `is_active` | bool | yes | Soft-delete flag |
| `metadata_` | JSONB | no | Free-form extension; source-specific fields live here |
| `created_at`, `updated_at` | timestamp | yes | Audit timestamps |

### 2.2.1 Quantitative semantics columns (added v2026.04)

These columns close the four critical harmonization gaps identified during the boutique CDE review (HARMONIZATION_ISSUES.md §1–§4). All are optional at the field level; conditional-required rules apply (see below).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `unit_of_measure` | str(64) | conditional* | UCUM-preferred unit string. Required when `item_type=numeric` AND (`plausible_min` OR `plausible_max`) is populated |
| `unit_vocabulary` | str(20) | no | One of: `UCUM`, `SNOMED-units`, `free-text` |
| `plausible_min` | float | no | Plausibility lower bound for outlier and unit-error detection. **Not** a clinical reference range |
| `plausible_max` | float | no | Plausibility upper bound. Must be ≥ `plausible_min` when both populated (CHECK constraint) |
| `numeric_precision` | smallint | no | Decimal places (0–20) for numeric item_types. Ignored on non-numeric (warning) |
| `cardinality` | str(16) | yes (default `single`) | One of: `single`, `multiple`, `unbounded` |
| `missing_value_convention` | str(64) | no | Sentinel for missing data (default `null`). Numeric sentinels (`-9`, `-99`, `999`) prohibited in conformant data |

**Conventions:**

- **Plausibility is not reference range.** A plausibility bound flags clear data errors and unit mis-specification (age = 250 years, glucose = 50000 mg/dL). Clinical reference ranges are policy-, locality-, sex-, and ancestry-specific and are out of RoP's scope; downstream consumers apply them at analysis time.
- **Unit-of-measure attribution rule.** A numeric CDE may be unitless (a count). Once `plausible_min` or `plausible_max` is populated, the bounds are unit-bearing and `unit_of_measure` becomes required. Without this attribution rule, a downstream consumer cannot interpret the bounds.
- **Cardinality and the canonical delimiter.** RoP enforces pipe (`|`) as the canonical delimiter for multi-valued CDEs. Source data using comma, semicolon, or whitespace delimiters is normalized at ingest time. Validation emits an INFO-level advisory when `cardinality=multiple/unbounded` but the `values` column shows non-pipe delimiters (e.g., semicolon-separated lists).
- **UCUM is preferred.** UCUM is the standard biomedical units vocabulary; `unit_vocabulary=UCUM` is the recommended default. UCUM "1" is the unit "one" (dimensionless); use it for counts, scores, and ratios.



### 2.3 Provenance columns (RoP additions)

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `source_authority` | str(50) | yes | Upstream authority; enumerated in §3.1 |
| `source_code` | str(255) | no | Native identifier at source authority |
| `source_version` | str(50) | yes | Pinned release identifier (e.g., `LOINC-2.78`, `Athena-2026-03`) |
| `source_url` | text | no | Deep link to authoritative definition |
| `source_retrieved_date` | date | yes | Date the row was pulled from upstream |

### 2.4 Multi-collection membership

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `member_of_collections` | text[] | no | Array of project tags this row serves (e.g., `["Path-ND", "GP2", "PPMI"]`) |

This is the **join column** that lets one RoP row serve many cohort projects. A new collection adopting RoP appends its tag to this array on the rows it consumes; it does not duplicate or fork rows.

### 2.5 Cross-vocabulary linkage

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `canonical_concept_id` | bigint | no | OMOP concept_id used as cross-vocabulary pivot |
| `equivalent_rop_ids` | UUID[] | no | RoP IDs of semantically equivalent rows from other source authorities |

### 2.6 Governance state

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `curation_status` | str(50) | yes | One of: `auto-matched`, `HitL-confirmed`, `expert-curated`, `deprecated`, `under-review` |
| `curator` | str(255) | no | ORCID or governance-system handle of last curator |
| `curation_date` | date | no | Date of last curation event |
| `match_confidence` | numeric(3,2) | no | Confidence score `[0.0, 1.0]` from the matching system |
| `replaced_by_rop_id` | UUID | no | If `curation_status='deprecated'`, the RoP ID that supersedes this row |

### 2.7 Search and embedding

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `search_text` | text | yes | Pre-concatenated input that produced the embedding |
| `embedding` | vector(384) | no | Sentence-transformer embedding over `search_text`; dimension matches model in use |

The reference embedding model is `cambridgeltl/SapBERT-from-PubMedBERT-fulltext` (384-dim after pooling). Implementations may use other models but must record the model identifier in the bundle manifest.

## 3. Source Authorities and Vocabularies

### 3.1 Recognized source authorities

```
LOINC                  Logical Observation Identifiers Names and Codes
HPO                    Human Phenotype Ontology
OMIM                   Online Mendelian Inheritance in Man
Mondo                  Monarch Disease Ontology
OMOP                   OHDSI/Athena standardized vocabularies
NACC                   National Alzheimer's Coordinating Center
NINDS-CDE              NIH/NINDS Common Data Elements
PhenX                  PhenX Toolkit
CDISC                  Clinical Data Interchange Standards Consortium
DUO                    GA4GH Data Use Ontology (consent class vocabulary)
DataTecnica-derived    Curated by RoP maintainers; no upstream authority
```

SNOMED CT, MedDRA, and CPT4 are intentionally **not** listed as RoP source authorities due to the open-source vocabulary inclusion criterion (their content licensing precludes redistribution in an open bundle). Their *identifiers* remain available as `target_code` values in the equivalence edge graph (carried through cross-references in HPO, Mondo, NINDS-CDE External_Id columns, and OMOP CONCEPT_RELATIONSHIP edges) — but no SNOMED/MedDRA/CPT4 names or descriptions are redistributed in any RoP bundle.

### 3.2 Recognized vocabularies for anchor controlled fields

```
UBERON                 Anatomy ontology (cross-species)
AllenBrainAtlas        Allen Institute brain region nomenclature
NCIT                   NCI Thesaurus
FMA                    Foundational Model of Anatomy
CL                     Cell Ontology
BICCN-CCN              BRAIN Initiative Common Cell Type Nomenclature
PCL                    Provisional Cell Ontology
NCBITaxon              NCBI Taxonomy (species)
OBI                    Ontology for Biomedical Investigations (assays)
EFO                    Experimental Factor Ontology
SO                     Sequence Ontology
HGNC                   HUGO Gene Nomenclature Committee
ChEBI                  Chemical Entities of Biological Interest
```

## 4. Conditional-Required Validation

The `priority` column supports both flat values (`Required`, `Optional`) and structured conditional-required expressions:

```
Required-when-<field>-<value>
Required-when-<field>-present
Required-for-<context>
Required-or-derivable
Recommended-for-<context>
```

Examples:

```
Required                                # always required
Required-when-IsBiosample-true          # required when IsBiosample=true
Required-when-genetic-ancestry-present  # required when any AncestryGenetic* field populated
Required-for-tissue-biosamples          # required when SampleTypeControlled is a tissue
Required-or-derivable                   # required unless transformable from other fields
```

Implementations must parse these expressions and enforce them at validation time. The reference parser is in `rop/validate.py`.

## 5. The Nine Core Anchor Tiers

The Core Anchor CDEs constitute the strictly-typed floor of the contract. Any cohort claiming interoperability must declare all anchors in the tiers relevant to the data being submitted. Anchor definitions live in `data/anchors/` as JSON files; their full content is normative.

### 5.1 Tier 0: Identity

The prerequisite that everything else attaches to. `IndividualID` is the cohort-unique participant identifier and the FK target for biosample, visit, and observation rows. `IndividualAliases` records cross-cohort/cross-system alias mappings as structured `{authority, identifier, linkage_method, linkage_confidence}` entries, supporting federated identification across sparse datasets without forcing every consumer to load the alias map. See `data/anchors/00_identity.json`.

### 5.2 Tier 1: Time

Strict canonical representations: ISO date, sequential visit number, fractional years from enrollment. A baseline anchor (`VisitBaselineDate`) is required so that the three representations are mutually convertible. See `data/anchors/01_time.json`.

### 5.3 Tier 2: Sex

Three distinct concepts kept separate: chromosomal sex (genetic), sex assigned at birth (clinical/administrative), gender identity (self-reported). Conflation is a validation error. See `data/anchors/02_sex.json`.

### 5.4 Tier 3: Ancestry and Demographics

Self-reported race and ethnicity (OMB), self-reported ancestry (free), genetic ancestry at superpopulation and subpopulation granularity, with required companion fields for method and reference panel. See `data/anchors/03_ancestry.json`.

### 5.5 Tier 4: Biosample

Identity, lineage (parent/child for aliquots), external ID cross-references, free-text tissue description with parallel controlled vocabulary, anatomical region with vocabulary and code, hemisphere, cell type with vocabulary and code, species of origin. See `data/anchors/04_biosample.json` and `data/anchors/05_anatomy_celltype.json`.

### 5.6 Tier 5: Omics Platform

Six-axis LOINC clinical assay structure (Component, Property, Time, System, Scale, Method) with documented Property-axis extensions for omics-specific quantities and a Method-axis platform sub-block (vendor, model, kit, batch, reference assembly, pipeline software, pipeline source repository, commit, container image, config reference). See `data/anchors/06_omics.json`.

### 5.7 Tier 7: Governance and Consent

DUO-aligned consent class with restriction modifiers, jurisdictional regulation, sharing/compute/recontact controls (re-share, download, cloud compute, participant re-contact, PI re-contact, re-consent), statistical disclosure control thresholds, and accountability contacts (IRB protocol, DAC, DUA reference, registration of record, PI contact, data steward contact). Required for any data flowing through Forge for re-distribution. See `data/anchors/07_governance.json`.

### 5.8 Tier 8: Data Asset References

GA4GH DRS-aligned pointers to external binary data assets (VCF, BAM, CRAM, FASTQ, counts matrices, h5ad, DICOM, NIfTI, mzML, etc.) associated with biosamples or individuals. Includes asset URI, type, format, sample scope, access protocol, companion index URI, integrity checksum, GA4GH Passport authorization requirements, reference assembly for genomic assets, and per-asset licensing. Required for any cohort whose RoP submission references retrievable binary data. See `data/anchors/08_data_assets.json`.

> Tier 6 is reserved for the Imaging metadata tier (see `docs/ROADMAP.md`, target v2026.10) and is intentionally skipped in the current numbering. Tier 8 (Data Assets) handles imaging *file references* in the meantime; Tier 6 will add imaging-specific *acquisition metadata* (modality, sequence parameters, reconstruction software).

## 6. Content Hashing and Change Detection

Each RoP element row carries a `content_hash` (SHA-256 hex). The hash input is a canonical JSON serialization of the following fields:

```python
{
  "description":      row.description,
  "item_type":        row.item_type,
  "values":           row.values,
  "value_set_ref":    row.value_set_ref,
  "source_authority": row.source_authority,
  "source_code":      row.source_code,
  "source_version":   row.source_version,
  "alternate_names":  sorted(row.alternate_names.split("|")),
  "collections":      sorted(row.member_of_collections or []),
  "metadata_":        canonicalize_jsonb(row.metadata_)
}
```

Excluded from the hash: `id`, `rop_accession`, audit timestamps, governance state (`curation_status`, `curator`, `curation_date`, `match_confidence`), derived fields (`embedding`, `search_text`), and lifecycle fields (`is_active`, `replaced_by_rop_id`).

The hash drives:
- Embedding rebuild triggers (only re-embed when content actually changes)
- Bundle manifest fingerprinting (consumers detect changed rows since prior bundle)
- Idempotent re-ingest from upstream sources

## 7. Bundle Format

A RoP distribution bundle is a directory:

```
rop_v<VERSION>/
├── rop.parquet         # element rows, all columns from §2 except embedding
├── rop_embeddings.parquet  # rop_accession → embedding vector (separate for size)
├── rop.faiss           # FAISS IndexFlatIP over normalized embeddings
├── manifest.json       # bundle metadata (see §7.1)
├── README.md           # human-readable provenance summary
└── LICENSE.md          # license terms; references upstream source authority licenses
```

### 7.1 Manifest schema

```json
{
  "bundle_version": "2026.04",
  "bundle_built_at": "2026-04-15T18:30:00Z",
  "row_count": 3584921,
  "source_versions": {
    "LOINC": "2.78",
    "HPO": "2026-02-06",
    "OMIM": "2026-03-15",
    "Mondo": "2026-04-01",
    "OMOP": "Athena-2026-03",
    "NACC": "UDS-3.0",
    "NINDS-CDE": "v3.1",
    "PhenX": "Toolkit-2024",
    "CDISC": "SDTM-3.4"
  },
  "embedding_model": "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
  "embedding_dim": 384,
  "anchor_tier_versions": {
    "01_time": "1.0",
    "02_sex": "1.0",
    "03_ancestry": "1.0",
    "04_biosample": "1.0",
    "05_anatomy_celltype": "1.0",
    "06_omics": "1.0"
  },
  "content_hash_summary": "sha256:abcd1234..."
}
```

## 8. Versioning and Deprecation Policy

### 8.1 Release cadence

RoP bundles are released **quarterly**, with version strings of the form `YYYY.QQ` (e.g., `2026.04` for the Q2 2026 release). Off-cycle patch releases (`YYYY.QQ.N`) are permitted for critical corrections.

### 8.2 ID stability

`rop_accession` values are **never recycled**. A retired concept retains its accession with `is_active=false` and may carry `replaced_by_rop_id` pointing to a successor. References from published harmonizations always resolve to a row, even if marked superseded.

### 8.3 Backward compatibility commitment

For any major version of RoP:
- All accessions present in version N remain resolvable in version N+1
- Deprecated accessions are marked, not removed
- Schema column additions are backward-compatible; column removals require a major version bump

### 8.4 Source authority version pinning

Each row's `source_version` is the exact upstream release the row was derived from. When upstream updates, RoP rows are re-evaluated:
- If content unchanged → `source_version` updated, `content_hash` unchanged
- If content changed → `source_version` updated, `content_hash` recomputed, embedding rebuilt

## 9. Equivalence Claims

The `equivalent_rop_ids` array expresses semantic equivalence between RoP rows from different source authorities. A claim of equivalence is asserted by:

1. Cross-source xref co-reference (Mondo/HPO/NINDS External_Id_* fields agree on a target identifier; or OMOP CONCEPT_RELATIONSHIP 'Maps to' edges link concepts), *plus*
2. Either identical OMOP `canonical_concept_id` *or* expert curation (`curation_status` ∈ `{HitL-confirmed, expert-curated}`)

Equivalence is **symmetric** but not stored bidirectionally; consumers querying equivalence must check both `WHERE A IN equivalent_rop_ids` and `WHERE B IN equivalent_rop_ids` (or use the materialized view shipped in the bundle).

Equivalence is **not transitive** by default — chains of `A ≡ B ≡ C` may require curator review before asserting `A ≡ C`. This prevents cascading false equivalences from low-confidence machine matches.

## 10. Conformance

A data submission is **RoP-conformant** at level N when all listed requirements are met. Levels 1–6 stack analytically. The Sharing-Ready (S) and Asset-Linked (D) attestations are orthogonal: a cohort can be analytically conformant at any level without S or D, but data cannot flow through Forge for re-distribution without S, and downstream pipelines cannot retrieve binary files without D.

| Level | Requirement |
|-------|-------------|
| 1 | All required columns from §2 are present and validated, AND Tier 0 (Identity) declared |
| 2 | + Tier 1 (Time) anchors declared and convertible |
| 3 | + Tier 2 (Sex) anchors declared without conflation |
| 4 | + Tier 3 (Ancestry) declared with required companion fields |
| 5 | + Tier 4 (Biosample) declared with valid lineage |
| 6 | + Tier 5 (Omics platform) declared with six-axis structure |
| **S** | + Tier 7 (Governance) declared with consent class, regulation, sharing controls, contacts |
| **D** | + Tier 8 (Data Assets) declared with GA4GH-aligned URI, type, format, scope, access protocol |

Conformance levels stack: a Level-3 submission satisfies Levels 1, 2, and 3. Cross-cohort meta-analysis eligibility starts at Level 3 (clinical) or Level 6 (multi-omics), in either case requires Sharing-Ready (S) status. Computational re-analysis on raw or processed binary data requires Asset-Linked (D) status. A submission missing S can support intra-cohort analysis but is not eligible for re-distribution; a submission missing D can support metadata-driven analysis but not pipeline re-execution.

## 11. Beyond Biomedicine

The structural pattern of this specification — strictly-typed anchors, source-authority provenance, content-hash change detection, conditional-required validation, equivalence graphs, governed embedding-driven matching — is domain-agnostic. Implementers in other verticals (financial, environmental, legal, manufacturing, education) can fork this scaffolding, replace §3 (source authorities), §5 (anchor tiers), and the JSON anchor definitions in `data/anchors/`, and run the same governance pattern.

We commit to maintaining a clear separation between the domain-agnostic core (validation engine, embedding pipeline, bundle format, conditional-required parser) and the biomedical-specific instantiation (anchor tiers, default vocabularies, source authorities). Pull requests that strengthen this separation are welcome.

## 12. References

- HL7 LOINC, https://loinc.org/
- Human Phenotype Ontology, https://hpo.jax.org/
- OMIM, https://omim.org/
- Mondo Disease Ontology, https://mondo.monarchinitiative.org/
- OHDSI Athena, https://athena.ohdsi.org/
- UBERON, http://uberon.org/
- Cell Ontology, http://obofoundry.org/ontology/cl.html
- BRAIN Initiative Cell Census Network, https://www.biccn.org/
- Allen Brain Atlas, http://atlas.brain-map.org/
