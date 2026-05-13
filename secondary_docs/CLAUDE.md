# RoP — Project Memory for Claude Code

This file is read automatically by Claude Code at session start. It contains the
architecture, conventions, and current state of the RoP project so you don't
have to re-explain context every session.

## What RoP is

**RoP** = Ring of Power (internal) / Biomedical Reference of Parameters (external).
A portable interoperability contract for biomedical Common Data Elements (CDEs)
that operationalizes through DataTecnica's "The Forge" governance tool.

Tagline: "One CDE set to rule them all..."

License: AGPLv3 (code) + CC-BY-NC-4.0 (data/docs). **Open source for non-commercial use.**

**Interested in using RoP?** Submit inquiries via the [RoP Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform)

## Critical scope distinction — RoP defines schemas, not content

RoP is a **CDE schema specification**. It defines *what fields describe a thing*.
It does NOT redistribute the things themselves.

| Layer | What it is | Where it lives |
|-------|-----------|----------------|
| **CDE schemas** (anchor floor) | What fields describe a thing | Theme 13a anchors (26) |
| **Boutique CDE collections** (curated bundles) | Project-specific subsets/extensions | Theme 13b registry (Sprint 2) |
| **Resource instances** (actual data) | PPMI participants, iNDI cell lines, CARD Catalog rows | NOT in RoP — these consume RoP |

Practical consequences:
- The CARD Catalog has 236 resource rows, 1,578 publications, 626 iNDI cell
  lines. **None of this content goes into RoP.** The 26 Theme 13a anchors
  ARE the schema for cataloging resources; CARD Catalog's content stays in
  the CARD Catalog Streamlit app and in Forge as data
- CARD-Catalog-CDE will land in Sprint 2 as a Theme 13b registry row pointing
  back at Theme 13a's schema, not as a content import
- iNDI: `ResourceCellLineMetadata` JSON object captures the iNDI-pattern
  schema; the 626 cell lines live elsewhere

This distinction was explicit Mike-correction during build: don't confuse
schema work with content migration.

## Embedding model — local only, no API dependency

RoP v2026.04 uses **SapBERT** (`cambridgeltl/SapBERT-from-PubMedBERT-fulltext`)
for embeddings.

**Model selection (Saturday May 3, 2026):**
- **BioLORD-2023** evaluated: +2% MedSTS accuracy (88.3 vs 86.3) over SapBERT
- **Hardware constraint:** BioLORD-2023 unstable on RTX 4080 laptop GPU (CUDA
  illegal memory access crashes after ~90 min runtime)
- **Decision:** SapBERT selected for v2026.04-foundation due to GPU stability,
  proven biomedical performance (MedSTS 86.3, state-of-art 2021), and 6.2 hour
  runtime vs 30+ hours for BioLORD
- **Future:** Revisit BioLORD-2023 for v2026.07 with datacenter GPU

**Production run (Saturday 5:22pm → Sunday 12:59am):**
- **Elements embedded:** 1,326,063 concepts (all deduplicated RoP elements)
- **Runtime:** 6.2 hours (22,430 seconds) on RTX 4080 Laptop GPU
- **Throughput:** 59 texts/sec
- **Batch size:** 512 elements per batch, checkpoint every 100 batches (51,200 elements)
- **Output:** 3.8GB embeddings.npy (1,326,063 × 768 float32, L2-normalized)
- **Quality validation:** Perfect row alignment, perfect normalization (all norms = 1.0),
  semantic capture verified (MSH2 genetic variants show 97.7% similarity)
- **GPU stability:** Required checkpoint-based auto-restart system due to periodic
  CUDA crashes; checkpoint saved embeddings every 100 batches (51,200 elements)

Specifically NOT used:
- Anthropic API (Claude is generative-only; no embedding endpoint exists)
- Voyage / OpenAI / Cohere / Google embedding APIs (would add runtime API
  dependency for downstream bundle consumers; embeddings can't be
  re-reproduced without the vendor's key)

Local biomedical models perform well on RoP's actual workload (biomedical
concept matching), are free, run on GPU, and produce redistributable
embeddings as bundle artifacts.

## Repo layout

```
rop_build/
├── README.md                    Top-level positioning + quickstart
├── CLAUDE.md                    This file
├── CONTRIBUTING.md              Proposal workflow
├── pyproject.toml
├── data/anchors/                14 JSON files, 224 anchors total (13 themes,
│                                Biosample has sub-themes 5a + 5b inside Theme 5)
├── docs/
│   ├── SPEC.md                  Normative specification
│   ├── ANCHORS.md               Per-theme anchor reference (human-readable)
│   ├── GOVERNANCE.md            Forge as governance layer
│   ├── ROADMAP.md               Quarterly release cadence
│   ├── PROJECT_PLAN.md          Sprint 1 → v1.0 timeline
│   ├── HARMONIZATION_ISSUES.md  Boutique-CDE harmonization gap analysis
│   └── SPRINT_1.md              Day-by-day runbook for current sprint
├── rop/
│   ├── __init__.py
│   ├── schema.py                Pydantic RoPElement model — single source of truth
│   ├── anchors.py               Anchor JSON loader + AnchorRegistry
│   ├── validate.py              Conditional-required parser + collection validator
│   ├── embed.py                 BioLORD-2023 embedding pipeline (locked Monday)
│   ├── bundle.py                Versioned Parquet+FAISS+manifest builder
│   ├── equivalence.py           Cross-source xref harvest — pulls xrefs from
│   │                            metadata_, normalizes vocab names, emits unified
│   │                            edge table for the dedup pass
│   ├── ingest/                  Per-source ingest package (10 sources)
│   │   ├── _common.py           Shared download/parse/build infrastructure
│   │   ├── loinc.py             LOINC release CSV (six-axis preserved) — OPTIONAL
│   │   ├── athena.py            OMOP/Athena CONCEPT.csv (Theme 12 backbone)
│   │   ├── hpo.py               HPO OBO via parse_obo (xrefs to OMIM/MESH; UMLS xrefs dropped)
│   │   ├── mondo.py             Mondo OBO with xref extraction (OMIM/ICD/MeSH)
│   │   ├── duo.py               DUO OBO (smallest, ~30 rows)
│   │   ├── dicom.py             DICOM tag dictionary via pydicom
│   │   ├── bids.py              BIDS spec YAML schemas
│   │   ├── cdisc.py             CDISC SDTM controlled terminology
│   │   ├── phenx.py             PhenX bulk DD_CSV (per-protocol)
│   │   └── ninds_cde.py         NINDS-CDE bulk export with built-in xrefs
│   └── cli.py                   `rop info | validate | parse-priority | bundle`
├── scripts/
│   ├── sprint1_download_all.py  Friday — orchestrator for ingest
│   ├── enrich_athena_loinc_six_axis.py
│   │                            Tuesday step 1 — DuckDB recovers LOINC six-axis
│   │                            from Athena CONCEPT_RELATIONSHIP edges
│   └── sprint1_dedup_pass1.py   Tuesday step 3 — DuckDB-based dedup pass over
│                                all per-source parquets, scales to 5-8M rows
├── migrations/
│   └── 001_rop_extension.sql    Additive migration on Forge `elements` table
└── tests/
    ├── test_validate.py         33 schema/validation tests
    ├── test_ingest.py           17 ingest pipeline tests
    └── test_equivalence.py      17 xref harvest tests
```

**Total tests: 67, all passing.**

## The 13 themes

| # | Name | File | Anchors |
|---|------|------|---------|
| 1 | Identity | `01_identity.json` | 3 |
| 2 | Time | `02_time.json` | 7 |
| 3 | Sex | `03_sex.json` | 3 |
| 4 | Ancestry & Pedigree (merged) | `04_ancestry_pedigree.json` | 18 |
| 5 | Biosample (5a core + 5b anatomy/cell) | `05_biosample.json` + `05b_anatomy_celltype.json` | 20 |
| 6 | Omics Platform (LOINC six-axis) | `06_omics.json` | 22 |
| 7 | Imaging Acquisition (DICOM/BIDS) | `07_imaging_acquisition.json` | 14 |
| 8 | Clinical Assessment Instruments | `08_clinical_instruments.json` | 13 |
| 9 | Governance & Consent | `09_governance.json` | 27 |
| 10 | Data Asset References (GA4GH DRS) | `10_data_assets.json` | 15 |
| 11 | Summary Statistics | `11_summary_stats.json` | 27 |
| 12 | Clinical Concepts (OMOP-backbone) | `12_clinical_concepts.json` | 13 |
| 13a | Discoverability — Resources | `13a_resources.json` | 26 |
| 13b | Discoverability — Special Collections | `13b_collections.json` | 16 |

**Total: 224 anchors.** Tests confirm all load cleanly.

## Conformance attestations (orthogonal to analytical levels)

```
Levels 1–9 stack analytically (Identity → Time → Sex → Ancestry-Pedigree →
  Biosample → Omics → Imaging → Clinical Instruments → Clinical Concepts)
S — Sharing-Ready    (Theme 9   Governance)         re-distribution
D — Asset-Linked     (Theme 10  Data Assets)        binary file retrieval
P — Pedigree-Linked  (Theme 4 pedigree subset)      family-based analyses
A — Analytics-Linked (Theme 11  Summary Stats)      meta-analysis & covariate reuse
R — Resource-Cataloged (Theme 13a Resources)        catalog discoverability
C — Collection-Tagged (Theme 13b Collections)       boutique bundle membership
```

## Key conventions

**Source authorities recognized** (in `SourceAuthority` enum, `rop/schema.py`):
LOINC, HPO, OMIM, Mondo, OMOP, NACC, NINDS-CDE, PhenX, CDISC, DUO, DICOM, BIDS,
DataTecnica-derived. Note: SNOMED CT, MedDRA, CPT4 are intentionally not
recognized — they require commercial licenses that conflict with RoP's
open-source distribution posture.

**Source access map (corrected):**

| Source | Access path in RoP |
|--------|---------------------|
| LOINC | **Via Athena** (primary). Direct LOINC ingest is optional; see rop/ingest/loinc.py |
| ICD-10 / ICD-10-CM / ICD-10-PCS / ICD-9 | Via Athena |
| RxNorm / NDC / HCPCS | Via Athena |
| MeSH / UCUM / ATC / CVX / NDFRT | Via Athena |
| ClinVar / OncoKB / COSMIC / CIViC (genomics) | Via Athena |
| HPO | Direct git clone (CC-BY-4.0) — also in Athena (vocabulary 159, Feb 2026 release), but git clone gives us richer OBO xrefs that we want for cross-vocab annotation |
| Mondo | Direct git clone (CC-BY-4.0) — not in Athena |
| DUO | Direct git clone (CC-BY-4.0) — not in Athena |
| DICOM | Embedded in pydicom |
| BIDS | Direct git clone (CC0) |
| CDISC SDTM | Direct HTTP from NCI EVS FTP (free, public) — also in Athena (vocabulary 156), but direct download is simpler and auto-fetched by orchestrator |
| PhenX | Direct HTTP from PhenX Toolkit (CC-BY-4.0) |
| NINDS-CDE | Direct CSV from catalog bulk export at https://www.commondataelements.ninds.nih.gov/cde-catalog (use the "Export All" / "Show All" CSV download). Single 38K-row file with 27 columns including built-in cross-references to LOINC/SNOMED/caDSR/CDISC. Free, no login. |
| **OMIM** | **NO direct ingest.** OMIM identifiers reach RoP exclusively via Mondo and HPO xrefs (both carry OMIM cross-references natively). OMIM is not in Athena. |
| **SNOMED CT, MedDRA, CPT4** | **NOT included** in v2026.04 bundle. These require commercial licenses for redistribution that don't fit RoP's open-source posture. |
| **UMLS** | **NOT used.** UMLS license precludes redistributing CUIs in an open-source bundle. UMLS xref tokens that appear in upstream OBO files (HPO carries some) are dropped during equivalence harvest. RoP's equivalence graph is built from cross-source xrefs (Mondo/HPO/NINDS) plus OMOP `Maps to` edges instead. |

**Athena release file inventory** (May 1 2026 download, comma-delimited).
Use these sizes as sanity checks; significant deviation suggests selection
mistake or download corruption.

| File | Approximate size | Notes |
|------|------------------|-------|
| CONCEPT.csv | 1.3 GB | One row per concept; vocabulary_id pivots all sources |
| CONCEPT_RELATIONSHIP.csv | 2.6 GB | Cross-vocab edges; source of LOINC six-axis + Maps-to |
| CONCEPT_ANCESTOR.csv | 1.8 GB | Hierarchical closure; not used in v2026.04 (defer) |
| CONCEPT_SYNONYM.csv | 350 MB | Alternate names per concept |
| DRUG_STRENGTH.csv | 154 MB | RxNorm dose composition; not used in v2026.04 |
| CONCEPT_CLASS.csv, DOMAIN.csv, RELATIONSHIP.csv, VOCABULARY.csv | <100 KB each | Lookup metadata |

Note on delimiter format: newer Athena releases (2025+) ship the CSVs with
commas as the field delimiter despite older OHDSI documentation that
references tab-delimited. The `_sniff_delimiter()` helper in
`rop/ingest/athena.py` detects header-line delimiter automatically;
parsers and DuckDB scripts use the sniffed value. **No manual delimiter
configuration is needed.**

**Sources are orthogonal to themes.** A single source contributes to multiple
themes. LOINC primarily Theme 12 + 6, secondarily 8 + 4. Athena cross-cuts
all themes via concept_id pivot. Source-to-theme map is in `docs/ANCHORS.md`.

**Encoding conventions:**
- Pipe (`|`) is the canonical multi-value delimiter
- Phenotypes use 0/1/NA encoding (NOT PLINK 1/2; PLINK export is a transform)
- `null` is the canonical missing-value sentinel; numeric sentinels (-9, -99)
  prohibited in conformant data
- UCUM is the preferred unit vocabulary
- Plausibility bounds are for outlier/unit-error detection; NOT clinical
  reference ranges (those are out of scope, locality-specific)

**Quantitative semantics fields** (added v2026.04 in pre-spec-freeze pass):
`unit_of_measure`, `unit_vocabulary`, `plausible_min`, `plausible_max`,
`numeric_precision`, `cardinality`, `missing_value_convention`. All optional,
backward-compatible. Required-when-numeric-with-bounds rule for unit_of_measure.

**Naming:** RoP CDEs use CamelCase. `member_of_collections` is a string array
where each entry is a `CollectionAbbreviation` from a Theme 13b registry row.

## What's locked (do not change without serious thought)

- **13-theme structure.** Reasoned through extensively. "Theme" as the term
  (not "tier" or "module"). Theme 4 merges ancestry + pedigree (phenotypes
  excluded — those go to Theme 8 and 12). Theme 13 has sub-themes 13a + 13b.
- **Athena-only access for OMIM/SNOMED/MedDRA/RxNorm/ICD.** License hygiene.
  LOINC stays direct because we need its six-axis content for Theme 6.
- **OMOP `concept_id` as the canonical cross-vocabulary pivot.** Theme 12's
  `ClinicalConceptStandardCode` is OMOP concept_id space.
- **Three-axis sharing controls in Theme 9** (reshare / download / cloud) —
  not the simpler binary "open vs controlled" model.
- **Multi-phenotype `PedigreePhenotypes` array was dropped** when pedigree
  merged into Theme 4 — phenotypes belong in clinical themes.

## What's pending (Sprint 1 work)

See `docs/SPRINT_1.md` for the day-by-day runbook. Summary:
- Value-set design + migration (Theme 13b registry already exists; need the
  per-CDE value-set storage tables — see SPEC.md §2.2.1 for fields already
  present on RoPElement; the value_sets / value_set_members tables are TBD)
- Embedding model lock-in (BioLORD-2023 default, eval may surprise)
- Bulk ingest of 10 standard sources (Mon AM concurrent download)
- Merge / parse / annotate pass — the actual hard work, Tue–Thu
- v2026.04-foundation bundle frozen Friday → boutique ingest Sprint 2

**Boutique CDE collections (Path-ND, GP2-CDE, CARD-Catalog-CDE, Gates-Ventures-CDE,
ADSP-PHC-CDE, others) ingest as one wave in Sprint 2** after the foundation bundle
is locked. Mike will provide them. Each lands as a Theme 13b registry row plus
member CDE rows tagged via `member_of_collections`.

## Conventions for working in this repo

**Always run tests before committing:**
```bash
cd rop_build && PYTHONPATH=. python3 -m pytest tests/ -q
```

**Adding a new anchor:** edit the relevant `data/anchors/NN_*.json` file,
following the existing schema (each file is a JSON array of objects). The
loader auto-discovers files matching `NN_*.json` patterns. Run tests to
confirm — the corpus-conformance smoke test catches schema violations.

**Adding a new validation rule:** add to `rop/validate.py` as a function
called from `validate_element`, and add a test class in
`tests/test_validate.py`. Use `Severity.ERROR` for hard failures,
`Severity.WARNING` for advisory issues, `Severity.INFO` for guidance.

**Adding a new source authority:** add to `SourceAuthority` enum in
`rop/schema.py`. Update the source-to-theme map in `docs/ANCHORS.md` and
`README.md`. Document the access path (free download? license needed?
proxied via Athena?) in any new `docs/SOURCE_LICENSING.md`.

**File creation discipline:** every anchor JSON file declaration should
include `source_authority`, `source_version`, `source_retrieved_date`,
`member_of_collections`, `curation_status`. Use `"DataTecnica-derived"` +
`"RoP-2026.04"` for newly-minted anchors.

## Current status (Monday May 4, 2026 evening - v2026.04 COMPLETE)

**Sprint 1 foundation bundle — in progress:**

- ✅ **Ingest complete:** 9 sources ingested (Athena, HPO, Mondo, NINDS-CDE, CDISC, PhenX, BIDS, DICOM, DUO)
  - 1,386,471 total rows pre-dedup
  - All parsers working, all source files staged

- ✅ **LOINC six-axis recovery:** 228,606 LOINC codes enriched with Component/Property/Time/System/Scale/Method axes from Athena CONCEPT_RELATIONSHIP

- ✅ **Cross-source xref harvest:** 88,387 equivalence edges extracted
  - Mondo xrefs (OMIM, ICD-10, MeSH)
  - HPO xrefs (OMIM, MeSH)
  - NINDS-CDE xrefs (LOINC, SNOMED, caDSR, CDISC)

- ✅ **Athena Maps-to edges:** 49,392 non-standard → standard OMOP mappings extracted

- ✅ **Dedup pass 1 complete:** 1,326,063 deduplicated rows
  - Option B implemented: `alternate_codes` embedded in elements table
  - 11,455 rows have alternate_codes populated (non-standard OMOP concepts)
  - Cross-source equivalences applied
  - Completed in ~100 seconds using 32 threads

- ✅ **SapBERT embeddings:** COMPLETE (Sunday 12:59am)
  - 1,326,063 elements embedded in 6.2 hours (59 texts/sec)
  - 3.8GB embeddings.npy (768-dim, L2-normalized, validated)
  - BioLORD-2023 evaluated but deferred to v2026.07 (GPU instability)

- ✅ **FAISS index:** COMPLETE (Sunday 8:20am)
  - IVF4096 index built in 26.6 minutes (1,595 seconds)
  - 3.9GB embeddings.faiss (4,096 clusters, 1.32M vectors)
  - Training: 23.6 min, Adding vectors: 3 min
  - Sanity test passed (self-similarity = 1.0)

- ✅ **v2026.04-foundation bundle:** PACKAGED (Sunday 5:25pm)
  - **Location:** `dist/rop_v2026.04-foundation/`
  - **Total size:** 7.76 GB
  - **Files:**
    - `elements.parquet` (150.3 MB) - 1,326,063 deduplicated CDEs
    - `embeddings.npy` (3,885 MB) - SapBERT vectors
    - `embeddings.faiss` (3,907 MB) - IVF4096 similarity index
    - `manifest.json` - SHA256 checksums + metadata
  - **License:** AGPLv3 (code) + CC-BY-NC-4.0 (data)

- ✅ **Boutique CDE collections:** INGESTED (Sunday 11:07pm)
  - **Total CDEs:** 2,910 boutique CDEs from 9 collections
  - **Largest collection:** CARD-PathND (1,616 CDEs)
  - **Collections:**
    - ASAP: 117 CDEs
    - Answer-ALS: 690 CDEs
    - BDR: 118 CDEs
    - BDSA: 56 CDEs
    - CARD-PathND: 1,616 CDEs
    - GP2: 39 CDEs
    - NACC: 202 CDEs
    - PART: 60 CDEs
    - SEA-AD: 12 CDEs
  - **Output:** `data/boutique/staging/boutique_cdes.parquet`
  - **Schema:** Collection name extracted from filename (e.g., "GP2_39.csv" → "GP2"), tagged via `member_of_collections`
  - **Metadata:** Source column from CSV preserved in `metadata_.boutique_source`

- ✅ **Final v2026.04 bundle:** COMPLETE (Monday 6:42pm)
  - **Merged:** Foundation (1,326,063) + Boutique (2,910) = **1,328,973 total CDEs**
  - **Embeddings:** Incremental SapBERT generation for boutique CDEs (2 min), merged with foundation
  - **FAISS index:** Rebuilt IVF4096 for full 1.33M dataset (25.2 min)
  - **Final package:** 7.8 GB with SHA256 checksums
  - **Location:** `dist/rop_v2026.04/`
    - `elements.parquet` (151 MB) - 1,328,973 deduplicated CDEs
    - `embeddings.npy` (3.9 GB) - SapBERT vectors (768-dim, L2-normalized)
    - `embeddings.faiss` (3.9 GB) - IVF4096 similarity index
    - `manifest.json` - SHA256 checksums + metadata (authors, collections, stats)

- ✅ **Distribution strategy:** COMPLETE
  - GitHub + Hugging Face (with Zenodo DOI integration)
  - Security screening script created
  - `.gitignore` updated (large files, boutique CDEs, logs excluded)

- ✅ **Top-level documentation:** DRAFTED
  - **README.md:** Comprehensive landing page with AI/FAIR/governance positioning
  - **Audit email:** Technical review request for Dan + Pietro
  - **Acknowledgments:** Alan Long, Cole Tindall, Hirotaka Iwaki, Syed Shah, Mat Koretsky, Mette Peters, +many more

- ⏳ **Next steps (awaiting Dan + Pietro audit):**
  - Licensing decision: AGPLv3+CC-BY-NC (dual, commercial licensing) vs AGPLv3+CC-BY (fully open)
  - Technical review of docs, messaging, positioning
  - Security screen: `python3 scripts/security_screen.py`
  - Ship to GitHub + Hugging Face
  - Create Zenodo DOI via HF integration
  - Announce via blog + LinkedIn

**Tests:** 99 passing (schema validation, ingest pipelines, equivalence harvest, Option B alternate_codes)

**Weekend build time:** ~7 hours total (6.2 hrs embedding on RTX 4080 GPU, 25 min FAISS, rest <1 hr)

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale (DataTecnica)

Mike's working directory: VS Code + Claude Code on the big laptop. v2026.04 bundle production-ready, awaiting final audit before public release.

## Style notes for working with Mike

- Dense technical writing, decisive recommendations with rationale
- Acknowledge when his catches surface real gaps (the OMIM commercial-licensing
  issue, the dropped-conformance-section bug, the source-authority enum gap)
- Explicit timelines and concrete deliverables, not aspirational
- Tolkien references occasional but appropriate
- Industry-default-conservative pacing is the wrong default; he runs hot
- Don't bury decisions in bullet lists; lead with the recommendation, then
  the rationale
- Everything he does including security checks and results gets validated and documented
- Postive and negative controls are necessary for each step
- Long work sessions as sprints