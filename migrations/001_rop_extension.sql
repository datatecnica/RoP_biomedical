-- =============================================================================
-- RoP — Biomedical Reference of Parameters
-- Schema extension for The Forge: additive migration on the elements table.
-- -----------------------------------------------------------------------------
-- Internal name : Ring of Power (RoP)
-- External name : Biomedical Reference of Parameters
-- Target        : PostgreSQL 14+ with pgvector extension
-- Strategy      : RoP is its own schemas row (UUID-pinned, versioned quarterly).
--                 Every RoP CDE is an element with schema_id = <RoP schema UUID>.
--                 No new tables required; only additive columns on `elements`.
-- =============================================================================

-- pgvector for embedding-based semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- 1. Provenance block — where this CDE came from, pinned to a release
-- =============================================================================
ALTER TABLE elements
    ADD COLUMN source_authority      VARCHAR(50),
    ADD COLUMN source_code           VARCHAR(255),
    ADD COLUMN source_version        VARCHAR(50),
    ADD COLUMN source_url            TEXT,
    ADD COLUMN source_retrieved_date DATE;

COMMENT ON COLUMN elements.source_authority IS
    'Upstream authority: NACC | OMOP | LOINC | HPO | OMIM | Mondo | NINDS-CDE | PhenX | CDISC | DataTecnica-derived';
COMMENT ON COLUMN elements.source_code IS
    'Native identifier at the source authority (e.g., LOINC 72172-0, HP:0001300)';
COMMENT ON COLUMN elements.source_version IS
    'Pinned release of the source authority (e.g., LOINC-2.78, Athena-2026-03)';

-- =============================================================================
-- 2. Multi-collection membership — RoP rows can serve many cohort projects
-- =============================================================================
ALTER TABLE elements
    ADD COLUMN member_of_collections TEXT[];

COMMENT ON COLUMN elements.member_of_collections IS
    'Array of project/cohort tags this CDE serves: Path-ND, GP2, PPMI-multiomics, ADSP-PHC, NACC-UDS3, ...';

CREATE INDEX idx_elements_collections_gin
    ON elements USING gin (member_of_collections);

-- =============================================================================
-- 3. Cross-vocabulary linkage — pivot to omni_vocab via OMOP concept_id
-- =============================================================================
ALTER TABLE elements
    ADD COLUMN canonical_concept_id BIGINT,
    ADD COLUMN equivalent_rop_ids   UUID[];

COMMENT ON COLUMN elements.canonical_concept_id IS
    'OMOP concept_id used as the cross-vocabulary pivot (joins omni_vocab.concept)';
COMMENT ON COLUMN elements.equivalent_rop_ids IS
    'Other RoP elements considered semantically equivalent (e.g., NACC and LOINC versions of the same concept)';

CREATE INDEX idx_elements_concept_id ON elements(canonical_concept_id)
    WHERE canonical_concept_id IS NOT NULL;
CREATE INDEX idx_elements_equiv_gin  ON elements USING gin (equivalent_rop_ids);

-- =============================================================================
-- 4. Forge governance state — tracks Forge's two-stage matcher + HitL outcomes
-- =============================================================================
ALTER TABLE elements
    ADD COLUMN curation_status   VARCHAR(50),
    ADD COLUMN curator           VARCHAR(255),
    ADD COLUMN curation_date     DATE,
    ADD COLUMN match_confidence  NUMERIC(3,2);

COMMENT ON COLUMN elements.curation_status IS
    'auto-matched | HitL-confirmed | expert-curated | deprecated | under-review';
COMMENT ON COLUMN elements.curator IS
    'ORCID or DataTecnica handle of the human or system that last set the status';

CREATE INDEX idx_elements_curation_status ON elements(curation_status);

-- =============================================================================
-- 5. Embedding + searchable text — payload for Forge's first-stage retrieval
-- =============================================================================
ALTER TABLE elements
    ADD COLUMN embedding   vector(384),
    ADD COLUMN search_text TEXT;

COMMENT ON COLUMN elements.embedding IS
    'Sentence-transformer embedding (384-dim) over search_text. Default model: pritamdeka/S-BioBert-snli-multinli-stsb';
COMMENT ON COLUMN elements.search_text IS
    'Pre-concatenated input that produced the embedding: description ⊕ source_authority+code ⊕ collection ⊕ member_of_collections ⊕ key metadata';

-- IVFFlat index for fast approximate cosine search; tune lists post-load
CREATE INDEX idx_elements_embedding_ivfflat
    ON elements USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 200);

-- =============================================================================
-- 5.5. Quantitative semantics (added v2026.04) — units, ranges, cardinality
-- =============================================================================
-- Closes four critical gaps identified during boutique CDE harmonization review:
--   #1 missing-value sentinel
--   #2 units of measure
--   #3 plausibility bounds (NOT clinical reference ranges; those are
--      policy-/locality-/sex-/ancestry-specific and out of scope)
--   #4 cardinality
ALTER TABLE elements
    ADD COLUMN unit_of_measure          VARCHAR(64),
    ADD COLUMN unit_vocabulary          VARCHAR(20),
    ADD COLUMN plausible_min            DOUBLE PRECISION,
    ADD COLUMN plausible_max            DOUBLE PRECISION,
    ADD COLUMN numeric_precision        SMALLINT,
    ADD COLUMN cardinality              VARCHAR(16) NOT NULL DEFAULT 'single',
    ADD COLUMN missing_value_convention VARCHAR(64);

COMMENT ON COLUMN elements.unit_of_measure IS
    'UCUM-preferred unit string (e.g., mg/dL, a for years). Required when item_type=numeric and plausible bounds are populated.';
COMMENT ON COLUMN elements.unit_vocabulary IS
    'UCUM | SNOMED-units | free-text';
COMMENT ON COLUMN elements.plausible_min IS
    'Plausibility lower bound for outlier and unit-error detection. NOT a clinical reference range.';
COMMENT ON COLUMN elements.plausible_max IS
    'Plausibility upper bound for outlier and unit-error detection. NOT a clinical reference range.';
COMMENT ON COLUMN elements.numeric_precision IS
    'Decimal places for numeric item_types (0-20)';
COMMENT ON COLUMN elements.cardinality IS
    'single | multiple | unbounded. Multi-valued CDEs use pipe (|) as canonical delimiter in values column.';
COMMENT ON COLUMN elements.missing_value_convention IS
    'Sentinel for missing data (default null). Numeric sentinels (-9, -99) prohibited in conformant data.';

-- Range ordering check — fires only when both bounds populated
ALTER TABLE elements
    ADD CONSTRAINT chk_plausible_range_order
    CHECK (plausible_min IS NULL OR plausible_max IS NULL OR plausible_min <= plausible_max);

-- Cardinality enum check
ALTER TABLE elements
    ADD CONSTRAINT chk_cardinality
    CHECK (cardinality IN ('single', 'multiple', 'unbounded'));

-- Unit vocabulary enum check
ALTER TABLE elements
    ADD CONSTRAINT chk_unit_vocabulary
    CHECK (unit_vocabulary IS NULL
           OR unit_vocabulary IN ('UCUM', 'SNOMED-units', 'free-text'));

-- Index on unit_of_measure: cross-cohort unit-mismatch queries during
-- boutique evaluation will scan by this column. Plausible bounds are
-- per-CDE static so don't warrant indexes.
CREATE INDEX idx_elements_unit ON elements(unit_of_measure)
    WHERE unit_of_measure IS NOT NULL;

-- =============================================================================
-- 6. Convenience view — RoP rows only, joined to omni_vocab crosswalk
-- =============================================================================
-- Assumes omni_vocab.concept_crosswalk_wide exists from earlier work.
-- Adjust the schema_id literal below to your RoP schemas row UUID after seeding.
CREATE OR REPLACE VIEW rop_enriched AS
SELECT
    e.id                      AS rop_id,
    e.item,
    e.description,
    e.collection              AS forge_collection,
    e.item_type,
    e.values,
    e.alternate_names,
    e.source_authority,
    e.source_code,
    e.source_version,
    e.member_of_collections,
    e.canonical_concept_id,
    e.curation_status,
    e.match_confidence,
    -- v2026.04 quantitative semantics
    e.unit_of_measure,
    e.unit_vocabulary,
    e.plausible_min,
    e.plausible_max,
    e.numeric_precision,
    e.cardinality,
    e.missing_value_convention,
    -- Cross-vocab arrays from omni_vocab (SNOMED column intentionally omitted)
    cw.icd10cm_codes,
    cw.icd10_codes,
    cw.loinc_codes,
    cw.hpo_codes,
    cw.omim_codes,
    cw.mondo_codes
FROM elements e
LEFT JOIN omni_vocab.concept_crosswalk_wide cw
       ON cw.canonical_concept_id = e.canonical_concept_id
WHERE e.schema_id = '00000000-0000-0000-0000-000000000000'  -- replace with RoP schemas.id
  AND e.is_active = TRUE;

-- =============================================================================
-- 7. Helper function — recompute search_text from current row state
-- =============================================================================
-- Call after any UPDATE to description / source_* / collection / member_of_collections
-- so the embedding rebuild stays consistent with the materialized search_text.
CREATE OR REPLACE FUNCTION rop_compose_search_text(e elements)
RETURNS TEXT LANGUAGE SQL IMMUTABLE AS $$
    SELECT concat_ws(' | ',
        e.description,
        CASE WHEN e.source_authority IS NOT NULL
             THEN e.source_authority || ' ' || COALESCE(e.source_code, '') END,
        e.collection,
        array_to_string(e.member_of_collections, ' '),
        e.metadata_::text
    );
$$;

-- =============================================================================
-- ROLLOUT NOTES
-- =============================================================================
--
-- 1. Seed order:
--    a. INSERT a `schemas` row for RoP. Pin its UUID; use it as the
--       canonical schema_id for every RoP element.
--    b. Phase 1: ingest curated CDEs from Path-ND, GP2, PPMI, NACC-UDS3,
--       NINDS-CDE library. Set curation_status='expert-curated'.
--    c. Phase 2: ingest from omni_vocab (LOINC, ICD, HPO, OMIM, Mondo).
--       Set curation_status='auto-matched'. Bridge to Phase 1 rows via
--       cross-source xrefs (Mondo/HPO/NINDS External_Id_*) and OMOP
--       Maps_to relationships; promote bridges to equivalent_rop_ids.
--
-- 2. Embedding rebuild:
--    Run after each ingest batch:
--       UPDATE elements SET search_text = rop_compose_search_text(elements.*)
--         WHERE schema_id = <RoP UUID> AND search_text IS NULL;
--    Then encode search_text → embedding in Python (sentence-transformers),
--    UPDATE elements SET embedding = ? WHERE id = ?, batched ~1000/txn.
--
-- 3. Versioning:
--    Quarterly RoP releases produce a Parquet + FAISS bundle for offline /
--    enclave Forge deployments. Bundle filename pattern:
--       rop_v<YYYY.QQ>.parquet  (e.g. rop_v2026.04.parquet)
--
-- 4. SNOMED, MedDRA, CPT4 content are intentionally omitted from the RoP
--    source_authority enum per the open-source vocabulary inclusion
--    criterion. Their identifiers can still appear as cross-references
--    (target_code values in equivalence_edges) since IDs are not
--    licensed text — but no SNOMED/MedDRA/CPT4 names or descriptions
--    are redistributed in any RoP bundle.
