# Sprint 1 Runbook — v2026.04 Foundation Bundle

**Kickoff:** Friday, May 1, 2026 (today)
**Goal:** Ship `rop_v2026.04-foundation` by Friday, May 8, 2026.

Friday-to-Friday cycle: today's afternoon is Athena selection + ingest
kickoff; weekend is supervised orchestrator runs and output inspection;
Monday-Friday is the analytical work (dedup, parse, annotate, QC, bundle).

**Working environment:** VS Code + Claude Code on the big laptop. Compute:
A100-class or 4090-class GPU for the local BioLORD-2023 embedding model
(Tuesday/Thursday). No API dependencies — RoP is open source and the
bundle must be reproducible offline.

**Scope clarification — what RoP is and isn't:**
RoP is a CDE schema specification — it defines *what fields describe a thing*.
Resource catalogs (CARD Catalog), boutique CDE collections (Path-ND, GP2-CDE),
and individual-level data (PPMI participants, iNDI cell lines) are
*consumers* of RoP, not content of RoP. Theme 13a Resources defines the
schema for cataloging resources; the 236 rows of CARD Catalog content live
in the CARD Catalog Streamlit app and in Forge as data, NOT in RoP.

**Definition of done for Friday:**
- ~2.5–3M deduplicated CDE rows across the 12 themes
- Every numeric row that can have plausible bounds + units has them
- `equivalent_rop_ids` arrays populated where source-cross-references are
  resolvable (HPO↔Mondo, OMOP concept_relationship, etc.)
- `canonical_concept_id` set to OMOP pivot wherever an OMOP mapping exists
- Embeddings computed for every row using local BioLORD-2023, indexed in FAISS
- Bundle Parquet + FAISS + manifest produced, content-hashed, signed
- 33 existing tests still passing, plus new tests for value-set logic

---

## Day 1 — Friday, May 1 (today)

### Afternoon kickoff (2-3 hours)

**Athena vocabulary selection + submit**

- [ ] Register at https://forums.ohdsi.org if not already
- [ ] Go to https://athena.ohdsi.org → Download tab
- [ ] Select open vocabularies per the list below (License-required ones
      stay unselected per the open-source criterion)
- [ ] Click Submit; wait for email link (typically 5-30 min for a large
      selection)

**While Athena builds the ZIP, run the auto-downloads:**

```bash
cd ~/rop_build
git checkout -b sprint1-execution
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pydicom pyyaml pyarrow

# Auto-fetched sources only (no Athena yet — that's still building)
python scripts/sprint1_download_all.py \
    --sources hpo,mondo,duo,bids,cdisc,phenx,dicom,ninds_cde
```

This pulls HPO/Mondo/DUO/BIDS via git clone, CDISC via NCI EVS HTTP,
PhenX via direct ZIP, parses DICOM from pydicom, and ingests the
already-staged NINDS-CDE bulk export. Expect ~5-10 minutes wallclock.

**When the Athena email arrives:**

- [ ] Download the ZIP (1.5-3 GB depending on selection)
- [ ] Extract to `data/sources/athena/<release>/`
- [ ] Run the Athena ingest:

```bash
python scripts/sprint1_download_all.py --sources athena --skip-download
```

This walks `CONCEPT.csv`, `CONCEPT_RELATIONSHIP.csv`, and
`CONCEPT_SYNONYM.csv` and emits parquet to
`data/foundation/staging/athena.parquet`. Expect ~30-60 minutes wallclock
for ~3-5M rows.

**End of Friday:** all 8 source parquets in
`data/foundation/staging/`, manifest.json written. Commit and push.

---

## Day 2-3 — Saturday/Sunday (light supervision)

**Source output inspection** (2-3 hours total spread across the weekend)

- [ ] Spot-check parquet outputs:
  - LOINC (via Athena): does six-axis come through via CONCEPT_RELATIONSHIP?
  - HPO/Mondo: do xrefs land in metadata?
  - NINDS-CDE: are cross-references and units captured?
  - PhenX: do plausibility bounds make sense?
  - Check row counts against expected ranges (in CLAUDE.md)
- [ ] Note any column-name mismatches that need parser tweaks Monday AM

**Build the RoP eval set** (~300 known boutique-to-standard pairs)

- [ ] Sample 300 CDE definitions from existing Path-ND / CARD content
      where the target standard-authority match is known
- [ ] Format as JSON: `{boutique_id, boutique_name, boutique_description,
      target_authority, target_code, target_name, relationship}`
- [ ] Save as `tests/eval_set/sprint1_boutique_to_standard.json`

---

## Day 4 — Monday, May 4

**Embedding model lock-in** (BioLORD-2023 vs alternatives, evaluated
against the eval set built over the weekend)

- [ ] Run eval: BioLORD-2023, SapBERT, ClinicalBERT, MedCPT
- [ ] Select model with best top-1 / top-5 accuracy on the 300 known pairs
- [ ] Document choice in `docs/EMBED_MODEL_DECISION.md`

**Value set table migration** (002_value_sets.sql)

- [ ] Refactor inline `values` strings into normalized `value_sets` table
- [ ] Migrate existing parquet rows
- [ ] Add tests for value-set lookup

---

## Day 5 — Tuesday, May 5

**Pass 1: Concept-level deduplication** — DuckDB throughout, scales to
the 5–8M rows produced by Athena's open-vocabulary selection.

**Step 1: Six-axis recovery for LOINC** (already done by ingest)

Athena flattens LOINC into single CONCEPT.csv rows, but the six-axis
structure (Component / Property / Time / System / Scale / Method) is
encoded in CONCEPT_RELATIONSHIP edges. The Athena ingest layer
(`rop/ingest/athena.py`) now reads CONCEPT_RELATIONSHIP and pivots the
six-axis edges into flat `axis_*` metadata fields on each LOINC row
during ingest. No separate enrichment script needed.

Sanity check after the Friday ingest finishes:

```python
import pyarrow.parquet as pq
df = pq.read_table("data/foundation/staging/athena.parquet").to_pandas()
loinc = df[df["metadata_"].apply(lambda m: m.get("omop_vocabulary_id") == "LOINC")]
print(f"LOINC rows: {len(loinc)}")
print(f"With axis_component: "
      f"{loinc['metadata_'].apply(lambda m: 'axis_component' in m).sum()}")
```

Expected: ~80% of LOINC observable concepts have axis_component
populated. If <20%, the relationship_id strings need adjustment for
your Athena release — check OHDSI Vocabulary v5.0 wiki LOINC page.

**Step 2: Cross-source equivalence harvest** (before dedup)

```bash
python -c "from rop.build import xref_harvest; \
  xref_harvest.run_harvest(staging_dir='data/foundation/staging')"
```

Walks per-source metadata.*_xrefs arrays plus Athena CONCEPT_RELATIONSHIP
to land high-precision equivalence edges. Skeleton in
`rop/build/xref_harvest.py` documents the per-source extraction strategy;
Tuesday's work fills in the SQL queries. Edge sources and expected yield:

| Source                                | Expected edges |
|---------------------------------------|----------------|
| Mondo metadata.mondo_xrefs            | ~80K           |
| HPO metadata.hpo_xrefs                | ~20K           |
| NINDS metadata.ninds_xrefs            | ~3K            |
| Athena CONCEPT_RELATIONSHIP "Maps to" | ~250-400K      |
| LOINC six-axis                        | ~500K          |
| **Total**                             | **~850K-1M**   |

If the harvest comes in well below this, something is wrong with
metadata extraction in one of the sources — check the parquet schema
for the metadata.*_xrefs columns.

**Output:** `data/foundation/staging/xref_edges.parquet`

**Step 3: Dedup proper** (DuckDB, via `rop.build.dedup`)

```bash
python -c "from rop.build import dedup; \
  dedup.run_dedup(staging_dir='data/foundation/staging', \
                  xref_edges_path='data/foundation/staging/xref_edges.parquet')"
```

Skeleton in `rop/build/dedup.py` with the SQL strategy documented;
Tuesday's work fills in the actual collapse query and the cross-source
clustering. Two phases:

- Phase A (within-source): same (source_authority, source_code) collapse
  to one row with metadata array union, scalar field rank-merge
- Phase B (cross-source): union-find clustering using xref_edges.parquet,
  assigns canonical_concept_id (preferring OMOP concept_id when in
  cluster), populates equivalent_rop_ids array per row

DuckDB throughout — required at this scale. Memory limit set to 8GB in
the module; bump if needed for your workstation.

**Output:** `data/foundation/staging/dedup_pass1.parquet` with one row
per unique (source_authority, source_code) pair.

---

## Day 6 — Wednesday, May 6

**Pass 2: Structured field extraction**

- [ ] Parse units to UCUM where free-text units exist
- [ ] Validate plausibility bounds against numeric_precision
- [ ] Resolve cardinality (single/multiple/etc.)
- [ ] Output: `data/foundation/staging/parsed_pass2.parquet`

---

## Day 7 — Thursday, May 7

**Pass 3: Annotate (cross-source overlap detection — fuzzy enrichment)**

Tuesday's dedup pass landed deterministic equivalences via xref tables
(Mondo/HPO/NINDS xrefs, Athena Maps-to). Thursday adds the soft matches
the deterministic graph misses.

- [ ] Method A (already done Tuesday): deterministic crosswalks
      Skip — already in dedup_pass1.parquet
- [ ] Method B: BioLORD-2023 cosine similarity > 0.92 threshold
      Embed every dedup row with the model locked Monday. For each row
      without a deterministic equivalence, find top-10 nearest neighbors
      across other sources; flag as candidate equivalences with
      `evidence='biolord_cosine'`.
- [ ] Method C: normalized string match
      For rows still without equivalences after B: lowercase, strip
      punctuation, exact match across sources. Catches naming-only
      synonyms that BioLORD missed.

Each annotation tagged with method + confidence in the
`equivalent_rop_ids` JSONB array. Output:
`data/foundation/staging/annotated_pass3.parquet`.

Expected gain over Tuesday: an additional ~50K-150K equivalences from
fuzzy matching on top of the ~200K-500K deterministic edges.

---

## Day 8 — Friday, May 8 (target ship)

**QC + bundle build**

- [ ] Run all 50 tests + add coverage tests for the bundle
- [ ] Validate: every numeric row has units OR explicit no-unit reason
- [ ] Validate: every Theme 12 row has at least one of {OMOP concept_id,
      LOINC code, HPO term, Mondo term, ICD-10 code}
- [ ] Build: `rop bundle --version 2026.04 --out dist/`
- [ ] Sign manifest, content-hash all artifacts
- [ ] Tag git: `v2026.04-foundation`
- [ ] Push to S3 + Zenodo (DOI generation)
- [ ] Merge `sprint1-execution` → `main`
- [ ] Announcement post in CARD/GP2 Slack

---

## Athena vocabulary selection (open-vocab list for v2026.04)

**Bulk source downloads** — parsers and orchestrator are ready, see
`scripts/sprint1_download_all.py` and `rop/ingest/`. Each source has its own
module under `rop/ingest/<source>.py` with `ingest_<source>()` and
`run_ingest()` functions. Orchestrator runs auto-downloads (git clones)
in parallel, then dispatches to parsers.

**Auto-downloaded** (orchestrator handles, no manual step):
- [ ] HPO via `git clone github.com/obophenotype/human-phenotype-ontology`
      (also provides OMIM xrefs)
- [ ] Mondo via `git clone github.com/monarch-initiative/mondo`
      (also provides OMIM, ICD-10, SNOMED, Orphanet xrefs)
- [ ] DUO via `git clone github.com/EBISPOT/DUO`
- [ ] BIDS via `git clone github.com/bids-standard/bids-specification`
- [ ] CDISC SDTM Terminology via direct HTTP from NCI EVS FTP
- [ ] PhenX bulk DD CSV ZIP via direct HTTP (auto-extracts to per-protocol CSVs)
- [ ] DICOM tags via `pydicom` library (no download — embedded)

**Manual-staged** (one source, requires email-link workflow):
- [ ] Athena vocabulary ZIP → `data/sources/athena/<release>/`
      Register at https://forums.ohdsi.org → go to https://athena.ohdsi.org →
      select **open vocabularies only** (skip the License-required ones —
      see the actual menu in `docs/athena_vocab_menu.pdf` for reference):

      ```
      Pre-selected (keep): RxNorm, RxNorm Extension, ATC, NDC, HCPCS,
                           ICD10CM, ICD10, ICD9CM, ICD9Proc, ICD10PCS,
                           UCUM, OMOP Extension, Vocabulary, Domain,
                           Concept Class, Relationship, Type Concept,
                           Race, Ethnicity, Gender, Specimen Type,
                           CMS Place of Service, Visit, etc.

      Add (no license): LOINC, MeSH, NDFRT, CVX, ICDO3, NUCC,
                        OMOP Genomic, ClinVar, HGNC, OncoTree,
                        OMOP Invest Drug, NCIt, Cancer Modifier,
                        SPL, HemOnc, NAACCR, CIViC, CGI, JAX, CTD,
                        CIEL, ABMS, SMQ, VANDF, VA Class, Indication,
                        ETC, UCUM, KCD7, ICD10GM, ICD10CN, ICD9ProcCN,
                        OPS, CCAM, OPCS4, dm+d, BDPM, JMDC, EDI,
                        CDISC, EORTC QLQ, HPO, PPI, Nebraska Lexicon,
                        SG COHORTS, NHS Ethnic Category, NHS Place,
                        DRG, MDC, APC, Revenue Code, Currency,
                        Provider, Supplier, Episode Type, Cohort,
                        SUS, NCCD, GGR, BDPM, AMT, DPD, COCONNECT,
                        UK Biobank, SNOMED Veterinary, KNHIS, KDC

      SKIP (License required): SNOMED, MedDRA, CPT4 (EULA), Multum,
                               Read, GPI, Multilex, GCN_SEQNO,
                               EphMRA ATC, NFC, LPD_Australia,
                               LPD_Belgium, GRR, MMI, CDT, ISBT,
                               ISBT Attribute, MEDRT, OncoKB

      SKIP (currently not available per Athena): CCS, AMIS, EU Product,
                                                 COSMIC
      ```

      Submit → wait for email link (2-10 min) → download → extract.

**Optional** (skip unless you specifically want six-axis flat fields):
- [ ] LOINC release ZIP → `data/sources/loinc/Loinc_*.zip`
      Athena's LOINC content covers the v2026.04 bundle needs; direct
      LOINC ingest is only useful for advanced omics-platform tooling
      that wants flat six-axis fields rather than CONCEPT_RELATIONSHIP
      walks.

**Already staged** (uploaded by Mike):
- [x] NINDS-CDE bulk export → `data/sources/ninds_cde/cde-details_20260501.csv`
      Single 38K-row CSV with 27 columns including LOINC/SNOMED/caDSR/CDISC
      cross-references and unit/plausibility-bound metadata. Parser tested
      against real data — 99.8% yield rate (rejects 65 malformed rows
      with upstream data quality issues).

**Notes on what RoP does NOT include in v2026.04:**

- **SNOMED CT, MedDRA, CPT4 descriptions** — license-required vocabularies
  that conflict with RoP's open-source redistribution posture. ICD-10-CM
  + Mondo + HPO cover the clinical-findings space adequately for v2026.04.
- **OMIM as a primary source** — not in Athena. OMIM identifiers reach
  RoP via Mondo and HPO xref arrays (both ontologies carry OMIM
  cross-references natively in their OBO files), and via NINDS-CDE
  external_id_loinc/snomed columns. This is sufficient for identifier-level
  coverage; we don't ingest OMIM clinical synopsis text (which would
  require a commercial JHU license anyway).

**Run the orchestrator:**
```bash
python scripts/sprint1_download_all.py --sources all
```

This will:
1. Run git clones in parallel (4 sources in ~2 minutes)
2. Run each ingest module against staged sources
3. Write per-source parquet to `data/foundation/staging/<source>.parquet`
4. Write a `manifest.json` summarizing downloads and row counts

Expected output: ~3.5–4M raw rows across all sources.

**Build the RoP eval set** (~300 known boutique-to-standard pairs, used Tuesday
PM to lock the embedding model)

- [ ] Sample 300 CDE definitions from existing Path-ND/CARD content where the
      target standard-authority match is known
- [ ] Format as JSON: `{boutique_id, boutique_name, boutique_description,
      target_authority, target_code, target_name, relationship}`
- [ ] Save as `tests/eval_set/sprint1_boutique_to_standard.json`

**Success criterion:** Orchestrator completes with manifest showing all 10
sources at expected row counts; `data/foundation/staging/*.parquet` files
exist and load cleanly.

### Afternoon block (4 hours)

**Value-set table migration**

- [ ] Add `value_sets` and `value_set_members` table DDL to a new migration
      `migrations/002_value_sets.sql` (design from earlier conversation:
      `id, vs_accession, name, description, source_authority, source_version,
      is_open, is_postcoordinated, parent_vs_id` for value_sets; per-member
      rows with `value, display_label, description, source_code,
      canonical_concept_id, alternate_codes (JSONB), is_default, is_active`)
- [ ] Add `value_set_id` foreign key column on the elements table extension
- [ ] Pydantic models: `ValueSet` and `ValueSetMember` in
      `rop/schema.py` matching the SQL
- [ ] Refactor inline `values` strings on existing 224 anchors into proper
      value-set rows where appropriate. Closed enums (sex, founder status,
      score direction, ancestry superpop) become value sets. Open string lists
      stay inline.
- [ ] Run tests; expect new value-set tests to be authored as part of this work

**Success criterion:** Tests pass with value-set tables populated; existing
inline-values anchors still resolve cleanly through the new pathway.

---

## Day 2 — Tuesday

### Morning block (4 hours) — MERGE pass 1: concept-level deduplication

The mechanical pass. For each theme, identify rows from different sources that
share an upstream identifier and collapse to a canonical row + crosswalk.

- [ ] Within Theme 6 (Omics): LOINC codes appearing in both direct LOINC
      ingest and Athena ingest. Canonical = direct LOINC. Athena entries
      become `alternate_codes` JSONB on the canonical.
- [ ] Within Theme 12 (Clinical Concepts): every Athena concept row is
      canonical. ICD-10/SNOMED/RxNorm/etc. rows become alternate_codes when
      they share an Athena concept_id.
- [ ] Within Theme 4 (Ancestry-Pedigree): HPO/Mondo/OMIM rows describing
      Mendelian conditions. HPO is canonical for phenotype-level entries;
      Mondo for disease entries; OMIM identifiers fold in as alternate_codes.
- [ ] Within Theme 8 (Clinical Instruments): PhenX and NINDS-CDE both define
      MoCA, MMSE, MDS-UPDRS instrument-level rows. Identify and merge by
      instrument abbreviation + version.
- [ ] Output: `data/foundation/staging/dedup_pass1.parquet` — one row per
      canonical concept, with `alternate_codes` array populated

**Success criterion:** Row count drops from ~3.5–4M raw to ~2.5–3M deduplicated.
Spot-check a sample of 20 clusters by hand to verify dedup correctness.

### Afternoon block (4 hours) — embedding model lock-in

- [ ] Run BioLORD-2023, SapBERT, MedCPT against the eval set built Monday
- [ ] Compute Recall@1, Recall@5, Recall@10 for each model
- [ ] Compute average cosine similarity for the (correct match) pairs vs.
      (random pair) baseline — bigger gap is better
- [ ] Lock the winner in `rop/embed.py` config; document the eval results in
      `docs/EMBEDDING_EVAL.md`
- [ ] If results are tied or close, default to BioLORD-2023 (best published
      benchmarks on EHR-Rel-B and MedSTS, which match RoP's workload)

**Success criterion:** A single model is locked; `rop/embed.py` config has it
hard-coded; the eval results document is committed.

---

## Day 3 — Wednesday — PARSE pass 2: structured field extraction

For every numeric and enum row, extract structured `unit_of_measure`,
`plausible_min`, `plausible_max`, `numeric_precision`, `cardinality`,
`value_set_id` from the source metadata.

- [ ] LOINC rows: pull UCUM units from LOINC's `EXAMPLE_UCUM_UNITS` field;
      `EXAMPLE_RANGE` field gives plausible bounds for many measurement
      concepts
- [ ] Athena rows: `unit_concept_id` joins to the UCUM-domain concept space;
      pull canonical units; range information not in OMOP standard, leave null
- [ ] PhenX rows: data dictionaries explicitly carry value ranges and units
      for many variables; parse the DD CSV for `units` and `range_min/max`
      columns
- [ ] HPO/Mondo: mostly enumeration concepts, no units; ensure `cardinality`
      is set correctly (most are `single`, some Mondo entries with comma-list
      synonyms become `multiple` after delimiter normalization)
- [ ] DICOM rows: tag dictionary has VR (Value Representation) field that
      maps to RoP `item_type`; value multiplicity (VM) maps to `cardinality`
- [ ] Where source metadata is insufficient to populate a structured field,
      leave it null and emit an INFO-level entry to a curator-review queue
      `data/foundation/staging/curator_review_queue.json`

**Success criterion:** Every row that *can* have structured fields has them;
the curator review queue file lists rows needing human attention (target:
<5% of numeric rows in the queue).

---

## Day 4 — Thursday — ANNOTATE pass 3: cross-source overlap detection

The hardest day. Build the equivalence map across source authorities.

### Mechanism A — direct identifier crosswalks (deterministic)

- [ ] OMOP `concept_relationship` table: for every "Maps to" relationship,
      populate `equivalent_rop_ids` on the source row pointing at the
      standard concept's RoP row
- [ ] HPO xref annotations: `hpo:0000001` has `xref: MONDO:0000001` →
      bidirectional equivalence
- [ ] Mondo xref annotations to OMIM, ICD-10, MeSH, SNOMED → equivalence
- [ ] CDISC controlled terminology often references LOINC/SNOMED/UCUM → walk
      those crosswalks

### Mechanism B — embedding-similarity clustering (judgment-dependent)

- [ ] Compute embeddings for every row using the locked model from Tuesday
- [ ] Build FAISS HNSW index across all theme rows
- [ ] For each row, query top-10 nearest neighbors from *different source
      authorities*
- [ ] Threshold: cosine similarity >0.92 → propose as equivalent (TUNE THIS
      against Monday's eval set; threshold may need to move to 0.88 or 0.95
      based on precision/recall tradeoff)
- [ ] All proposed equivalences below 0.97 confidence go to the curator
      review queue, not auto-applied

### Mechanism C — exact string matching after normalization

- [ ] Normalize description strings: lowercase, strip punctuation, stem
- [ ] Within a theme, group rows from different sources with matching
      normalized descriptions
- [ ] These are typically high-confidence equivalences but should still be
      QC'd because some source authorities define very different concepts
      under near-identical names (e.g., "glucose" alone is dangerously
      ambiguous between blood/urine/CSF)

**Success criterion:** `equivalent_rop_ids` arrays populated across the
corpus. Every row with an OMOP standard concept has its `canonical_concept_id`
set. Curator review queue has <2,000 entries (manageable for Sprint 2 Week 1
review).

---

## Day 5 — Friday — QC and bundle build

### Morning block — QC

- [ ] Sample 200 equivalence clusters across the 13 themes; manual spot-check
      for false positives
- [ ] Run `pytest` — confirm 33 existing tests still pass plus new value-set
      tests
- [ ] Run the corpus-conformance smoke test against the full unified corpus
- [ ] Compute coverage stats per theme: % rows with units, % with plausible
      bounds, % with canonical_concept_id, % with at least one equivalent
- [ ] Generate a Sprint 1 stats report at
      `docs/SPRINT_1_FINAL_STATS.md`

### Afternoon block — bundle build

- [ ] Run `rop bundle build --version 2026.04-foundation`
- [ ] Output: `bundles/rop_v2026.04-foundation/` containing:
      - `manifest.json` (content hashes, version, build date, source versions)
      - `elements.parquet` (full corpus, ~2.5–3M rows)
      - `embeddings.parquet` (per-row embedding vectors)
      - `faiss.index` (HNSW index for similarity search)
      - `value_sets.parquet` + `value_set_members.parquet`
      - `crosswalks.parquet` (equivalent_rop_ids edges as a relation table)
- [ ] Tag git commit `v2026.04-foundation`
- [ ] Deposit to Zenodo for DOI (manual step, but URL/scripted)

**Success criterion:** Bundle builds without errors, content hashes verify,
total bundle size is in the 1–2 GB range, downstream load test passes.

---

## End of Sprint 1 — Monday AM (week 2)

Sprint 1 close ceremony:

- [ ] v2026.04-foundation tagged, archived, on Zenodo with DOI
- [ ] Sprint 2 kickoff: boutique CDE collections (Path-ND, GP2-CDE,
      CARD-Catalog-CDE, Gates-Ventures-CDE, ADSP-PHC-CDE, others) ingest
      as one wave against the foundation bundle
- [ ] Each boutique collection lands as a Theme 13b registry row with full
      metadata
- [ ] Each boutique CDE definition gets matched against the foundation
      corpus using the locked embedding model; high-confidence matches
      auto-link via `equivalent_rop_ids`; low-confidence go to curator
      review

**Sprint 2 deliverable: v2026.04 (full release, foundation + boutique).**

---

## What to do if a step blocks

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Source download fails | Server down / new auth | Try mirrors; check upstream announcements |
| Parser fails on new release format | Source authority changed format | Pin to last working version; file issue upstream |
| Embedding model OOM | Model too big for GPU | Switch to fp16 inference; or BioLORD-2023-C (smaller variant) |
| Tests fail unexpectedly | Schema drift | Read the test failure carefully — usually says exactly what changed |
| Curator review queue >5,000 entries | Threshold too aggressive | Loosen the 0.92 cosine cutoff to 0.95; precision-first over recall |
| Bundle build OOM | 3M rows in memory | Stream-process by theme; build per-theme parquets, concat at end |
| Zenodo deposit fails | API or rate limit | Manual upload via web UI is fine for v2026.04-foundation |

## Compute checklist before Monday

- [ ] GPU available (A100 ideal, V100/A6000 acceptable, RTX 4090 fine for
      this corpus size)
- [ ] ≥500 GB free disk for sources + intermediate parquets + bundle output
- [ ] ≥64 GB RAM for the merge/parse passes
- [ ] Python 3.11+ with environment from `pyproject.toml` ready
- [ ] PostgreSQL 14+ with pgvector running (for migrations and Forge
      integration; Sprint 1 doesn't strictly need it, but Sprint 2 will)

## What's deliberately out of scope for Sprint 1

- ❌ Boutique CDE ingest (Sprint 2)
- ❌ Theme 13b Collections registry rows — the schema is shipped in Sprint 1,
      but registry rows populate when boutique collections ingest in Sprint 2
- ❌ Resource instance content (CARD Catalog's 236 rows, iNDI's 626 cell lines,
      PPMI/ADNI/etc. records) — these are consumers of RoP, not content of RoP
- ❌ Forge UI integration (later sprint)
- ❌ Methods paper drafting (Sprint 4)
- ❌ External adopter case studies (Sprint 5)
- ❌ Cloud embedding APIs (Voyage, OpenAI, Cohere) — RoP uses local
      BioLORD-2023 to keep the bundle reproducible offline and free of
      runtime API dependencies

## What's in scope and already complete (Sprint 0 work)

- ✅ All 13 theme schema definitions (224 anchors)
- ✅ Theme 13a Resources schema (26 anchors) — this IS the CARD Catalog
      schema in RoP form; no content migration needed
- ✅ Theme 13b Collections registry schema (16 anchors) — ready to receive
      boutique collection registry rows in Sprint 2
- ✅ Quantitative semantics fields (units, plausible bounds, cardinality,
      missing-value convention)
- ✅ 33 tests passing including corpus-conformance smoke test
