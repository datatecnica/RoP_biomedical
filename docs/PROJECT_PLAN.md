# Project Status & Execution Plan

**As of**: April 2026
**Bundle target**: v2026.04 (foundation), v2026.07 (mega corpus complete)
**Boutique CDE check**: targeted post-v2026.07

This document maps where the RoP project currently stands, what's required to reach a complete mega corpus, and the concrete plan for evaluating it against DataTecnica's ~4,000 in-house "boutique CDEs."

---

## 1. Current State (April 2026)

### 1.1 What's complete

**Specification**: 12-section normative spec (`docs/SPEC.md`) covering element schema, source authorities, conditional-required grammar, content hashing, bundle format, versioning policy, equivalence semantics, and conformance levels. Ready for external review.

**Anchor floor**: 88 strictly-typed anchor CDEs across 8 tiers — Identity (2), Time (7), Sex (3), Ancestry (7), Biosample (12), Anatomy/Cell (8), Omics platform (22), Governance (27). Each tier carries conditional-required validation rules, source authority pinning, and metadata sufficient for downstream consumers to reproduce intent.

**Validation engine**: working Python implementation of conditional-required parser, element-level structural checks, collection-level coverage and consistency checks, time anchor derivability check. 19/19 tests pass. Handles all current priority grammar including multi-word values.

**Embedding pipeline**: SapBERT + FAISS reference implementation (`rop/embed.py`). Configurable model; biomedical default is `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`. Bundle builder produces `rop.parquet` + `rop_embeddings.parquet` + `rop.faiss` + `manifest.json`.

**Schema migration**: production-ready additive SQL (`migrations/001_rop_extension.sql`) extending Forge's `elements` table. Drops cleanly into existing Forge Postgres deployments without breaking existing rows.

**Documentation**: README, SPEC, ANCHORS, GOVERNANCE, ROADMAP, CONTRIBUTING. ~50 pages of normative content; explicit framing that the architecture transfers to non-biomedical verticals.

### 1.2 What's deferred / stubbed

- **Source authority ingest pipelines**: skeletons exist in `rop/ingest.py` with documented contracts; no implementations yet
- **Biosample lineage validator**: emits `LINEAGE_CHECK_DEFERRED` placeholder; full graph traversal pending
- **Forge UI integration**: anchor validation gates need to wire into Forge's existing ingest UI as hard checkpoints
- **Equivalence claim review UI**: HitL queue mechanics for medium-confidence matches
- **Public proposal pathway**: GitHub Issues templates and routing exist on paper; not deployed

### 1.3 Quantitative snapshot

```
Lines of code (Python):           ~1,400
Lines of SQL (migration):         ~200
Anchor CDE definitions:           88
Documentation pages:              ~50
Test coverage:                    19 tests, all passing
Source authorities recognized:    11 (LOINC, HPO, OMIM, Mondo, OMOP, NACC,
                                  NINDS-CDE, PhenX, CDISC, DUO, DataTecnica-derived)
Conformance levels defined:       7 (Levels 1-6 + Sharing-Ready S)
```

---

## 2. Mega Corpus Build Path

The "mega corpus" is the populated, embedded, and indexed bundle covering all recognized source authorities — the artifact that turns RoP from specification into operating infrastructure.

### 2.1 Source authority ingest priority

Ordered by combination of (a) value to boutique CDE matching, (b) implementation tractability, (c) license clarity. Effort estimates assume one focused engineer with current LLM tooling — the team's actual operating pace, not industry-default-conservative.

**Sprint 1 — v2026.04 foundation (target: 1.5 weeks)**

| Authority | Priority | Volume | Effort | Notes |
|-----------|----------|--------|--------|-------|
| LOINC | Critical | ~100K terms | ~6 hours | Single CSV, well-documented; foundation for omics six-axis |
| OMOP/Athena | Critical | ~8.7M concepts | ~1 day | Cross-vocab pivot via `concept_id`; bulk CSV load, embedding is the long pole |
| HPO | High | ~17K terms | ~4 hours | OBO via `parse_obo`; xref arrays carry OMIM, MESH cross-refs |
| DUO | High | ~50 terms | ~2 hours | Tiny ontology |
| Path-ND seed | Critical | ~500 CDEs | ~3 hours | Already curator-blessed |

Wall-clock with parallel ingest: **3-4 days of focused work**, plus one day of bundle build, embedding generation, and validation. Realistic to ship by mid-May 2026 from the current state.

**Sprint 2 — v2026.07 mega corpus (target: 2 weeks after Sprint 1)**

| Authority | Priority | Volume | Effort | Notes |
|-----------|----------|--------|--------|-------|
| Mondo | High | ~25K terms | ~1 day | OBO; xref arrays drive `equivalent_rop_ids` for rare disease |
| OMIM | High | ~26K phenotypes | ~1 day | API access registration is the gating step |
| NACC UDS-3.0 | Critical for ND | ~600 CDEs | ~6 hours | DUA review is the gating step |
| NINDS-CDE | High | ~3,500 CDEs | ~1 day | Library structure parser |
| PhenX | Medium | ~22K data elements | ~1 day | Toolkit-format |
| CDISC SDTM | Medium | ~variable | ~1 day | AE/CM/MH domains |
| UBERON, CL, OBI | Medium | ~16K + 2.6K + 4K | ~1 day | OBO format, similar parser pattern |
| NCBITaxon, HGNC, ChEBI, EFO, SO | Bridge | varies | ~1 day | Companion vocabularies |

Wall-clock: **6-8 days of focused work** for the full set, parallelizable across multiple engineers if needed. Most ingests share a parser pattern, so the second OBO ingest is faster than the first.

### 2.2 Cross-vocabulary equivalence pipeline (~2 days)

After ingest, the equivalence graph gets bootstrapped:

1. **Cross-source xref co-reference**: rows from different source authorities whose xrefs target the same identifier (HPO/Mondo/NINDS xrefs) become equivalence candidates
2. **OMOP concept_id matching**: rows with the same `canonical_concept_id` become high-confidence equivalence
3. **Mondo xref propagation**: rare disease equivalences cascade through Mondo's curated cross-reference graph
4. **Confidence scoring**: each equivalence claim gets a confidence based on supporting evidence
5. **HitL escalation**: medium-confidence (0.5–0.85) claims queue for curator review

Estimated initial graph size: ~500K equivalence edges across ~3M nodes. Build is mostly SQL joins + scoring heuristics; no novel algorithms needed.

### 2.3 Embedding generation at scale (~2 hours)

For ~3M rows on a single rented A100:

```
Encoding throughput (SapBERT, batch=64):  ~800 rows/second
Total time for 3M rows:                   ~1 hour
FAISS index build (IndexFlatIP, 768-dim): ~5 minutes
Bundle write:                             ~10 minutes
Wall-clock end-to-end:                    ~75 minutes plus setup
Cost on rented GPU:                       ~$10
```

### 2.4 Quality validation (~1 day)

Before declaring v2026.04 ready:

- **Round-trip integrity**: every row in the bundle re-validates through the schema
- **Embedding sanity**: nearest-neighbors of 50 known CDEs are sensible
- **Cross-source equivalence spot-check**: 100 random equivalence claims hand-reviewed by curator
- **Conformance smoke test**: 5 cohort submissions run through `rop validate` with realistic context flags
- **Bundle reload**: bundle written to disk → reloaded → identical row count + identical content hash summary

### 2.5 Bundle release process (~half day)

Build → manifest review → sign → Zenodo deposit → S3 mirror → GitHub release → release notes. Mostly mechanical; the only manual step is the manifest review.

---

## 3. Boutique CDE Evaluation Plan

Once the mega corpus is built, the ~4,000 DataTecnica-developed CDEs become the first comprehensive coverage and quality test of RoP's matching infrastructure.

### 3.1 Why this matters

The boutique CDE library is the closest thing to "real-world adoption pressure" we have access to. Every boutique CDE was created to fill a gap that an existing CDE library didn't cover for some specific cohort or analysis need. So three things will be visible in the match results:

1. **What % of boutique CDEs already exist in standard authorities** — a coverage measurement of the existing CDE landscape against actual practitioner needs
2. **Where the gaps are** — which clinical/omics/biosample concepts the standard authorities systematically under-serve
3. **Whether RoP's matching infrastructure is good enough to find those matches** — a measurement of SapBERT + FAISS + structured metadata as a matching engine

### 3.2 Workflow

```
                  ┌───────────────────────────────┐
                  │ DataTecnica boutique CDE store │
                  │      (~4,000 CDEs across       │
                  │       N collections)           │
                  └───────────────┬───────────────┘
                                  │
                          [1] Inventory + normalize
                                  ▼
                  ┌───────────────────────────────┐
                  │ Boutique CDEs as RoPElement[]  │
                  │ source_authority="DT-derived"  │
                  │ member_of_collections=[...]    │
                  └───────────────┬───────────────┘
                                  │
                          [2] Encode + embed
                                  ▼
                  ┌───────────────────────────────┐
                  │ Boutique embeddings (4K x 768) │
                  └───────────────┬───────────────┘
                                  │
                          [3] FAISS top-k search
                                  ▼
                  ┌───────────────────────────────┐
                  │ Match candidates per CDE       │
                  │ k=10 neighbors + cosine score  │
                  └───────────────┬───────────────┘
                                  │
                          [4] AI vetting (Forge)
                                  ▼
        ┌─────────────────────────┴─────────────────────────┐
        ▼                         ▼                         ▼
  high confidence          medium confidence          low confidence
   (auto-bind)              (HitL queue)             (likely novel)
   bind boutique →           curator                  promote to
   existing RoP row          decision               new RoP row
        │                         │                         │
        └─────────────────────────┴─────────────────────────┘
                                  │
                          [5] Coverage analysis
                                  ▼
                  ┌───────────────────────────────┐
                  │ Per-collection coverage report  │
                  │ Gap analysis by domain          │
                  │ Curator workload projection     │
                  └───────────────────────────────┘
```

### 3.3 Step-by-step

**[1] Inventory and normalize (1-2 days)**

Pull ~4K boutique CDEs from existing storage into a single JSON conforming to RoPElement schema. Set `source_authority="DataTecnica-derived"`, populate `member_of_collections` per originating boutique. Compute `search_text` and `content_hash`. The "1-2 days" assumes the source data is roughly tabular; if it's spread across multiple formats or systems, add a day for ETL.

**[2] Encode and embed (~10 minutes GPU)**

Run boutique CDEs through the SapBERT pipeline. Trivially fast at this scale.

**[3] FAISS top-k search (~minutes)**

Query the mega corpus FAISS index for top-10 neighbors per boutique CDE. Record cosine scores and source authority of each neighbor.

**[4] AI vetting and triage (~3-5 days curator time, parallelizable)**

Per boutique CDE:

| Top-1 cosine | Action | Volume estimate |
|--------------|--------|-----------------|
| ≥ 0.92 | Auto-bind: boutique CDE's `equivalent_rop_ids` populated; counted as "covered" | ~40-50% of CDEs (~1,600-2,000) |
| 0.80–0.92 | HitL: AI vetting produces a structured equivalence proposal; curator confirms, rejects, or proposes alternative | ~25-35% of CDEs (~1,000-1,400) |
| 0.65–0.80 | HitL with caution: AI vetting flags as borderline; curator likely proposes new RoP row | ~10-15% of CDEs (~400-600) |
| < 0.65 | Likely novel: AI vetting confirms; curator promotes to new RoP row | ~5-15% of CDEs (~200-600) |

Curator time scales with the HitL queue size. Expected ~2,000 HitL decisions; at 30-60 seconds per decision with AI-vetted proposals to confirm/reject, that's 17-33 hours of curator time. Parallelizable across 2-3 curators, finishes in 2-3 wall-clock days.

**[5] Coverage analysis (~1-2 days)**

Per boutique collection: bind rate, equivalence rate, novel rate, domain breakdown of novel CDEs, identified gaps in standard authorities, curator workload distribution. Methods paper draft falls out of this.

### 3.4 Outcomes

By end of boutique CDE evaluation:

1. **Boutique CDEs are bound to RoP** — all ~4K live as RoPElement rows with explicit `equivalent_rop_ids` linkage where standard-authority counterparts exist
2. **DataTecnica's curated knowledge becomes a published source authority** — DataTecnica-derived rows in the bundle are openly available to the field
3. **Coverage gaps are documented** — quantitative evidence of where standard authorities systematically under-serve practitioner needs
4. **The matching infrastructure has been stress-tested at realistic scale** — we know whether SapBERT + FAISS + structured metadata is good enough or whether a stronger matcher is needed
5. **Methods paper in draft** — the obvious deliverable from a coverage analysis at this scale

### 3.5 Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Auto-bind threshold too aggressive → false equivalences | Medium | Hand-review first 100 auto-binds; re-calibrate thresholds before bulk run |
| Curator workload exceeds capacity | Low-Medium | AI vetting reduces curator load ~70% vs manual; parallelize across curators if needed |
| SapBERT embeddings underperform on highly specialized domain language | Low | Fall back to ensemble: BioLORD-2023 + SapBERT + general sentence-transformer; pick best per domain |
| Boutique CDEs reveal that >30% are genuinely novel | Low | This is a feature, not a bug — those become DataTecnica-derived contributions to the field |
| LOINC release changes mid-evaluation | Low | Bundle versions are pinned; re-run evaluation against frozen bundle |

---

## 4. Calendar (Compressed)

DataTecnica execution velocity, not industry-default-conservative. Calendar dates are targets, not safety buffers.

```
2026 May (Wks 1-2)   v2026.04 SPRINT — foundation bundle
                     ├─ Wk 1: LOINC, OMOP/Athena, HPO, DUO, Path-ND ingest
                     │        (parallel; ~4 days focused work)
                     ├─ Wk 1: Embedding generation (~2 hours GPU)
                     │        Bundle build + manifest
                     ├─ Wk 2: Quality validation
                     ├─ Wk 2: Zenodo deposit + GitHub release
                     └─ END WEEK 2: First public bundle (v2026.04)

2026 May–Jun (Wks 3-5) v2026.07 SPRINT — mega corpus
                     ├─ Wk 3: Mondo, OMIM, NACC, NINDS-CDE ingest
                     ├─ Wk 4: PhenX, CDISC, UBERON, CL, OBI ingest
                     │        Companion vocabs (NCBITaxon, HGNC, ChEBI, EFO, SO)
                     ├─ Wk 4: Cross-vocabulary equivalence pipeline
                     ├─ Wk 4: Lineage validator implementation
                     ├─ Wk 5: Forge UI integration
                     └─ END WEEK 5: Full mega corpus (v2026.07)

2026 Jun (Wk 6)      BOUTIQUE CDE EVALUATION
                     ├─ Day 1-2: Inventory + normalize ~4K boutique CDEs
                     ├─ Day 3: Embed + FAISS match against mega corpus
                     ├─ Day 4-5: AI vetting + HitL curation pass
                     ├─ Day 6-7: Coverage analysis + methods paper outline
                     └─ END WEEK 6: Coverage report drafted

2026 Jul             v2026.10 PRELOAD — imaging + refinements
                     ├─ Wk 7: Imaging anchor tier (Tier 6) finalized
                     ├─ Wk 7: Refinements based on boutique findings
                     ├─ Wk 8: Methods paper polish + journal submission
                     └─ Wk 8: External adopter outreach (NIH consortia)

2026 Aug-Sep         ADOPTION + EXPANSION
                     ├─ External adopter case studies (preprints)
                     ├─ Drug exposure tier (RxNorm pivot)
                     ├─ Domain-agnostic core extraction (rop-core)
                     │  if external interest emerges
                     └─ Stable v1.0 declaration target: end of Q3 2026
```

**Total time from current state to stable v1.0 with mega corpus, boutique evaluation, methods paper, and at least one external adopter case study: roughly 4-5 months**, not 12. Compressed timeline assumes:

- One focused engineer for ingest pipelines (~6 weeks of full-time engineering)
- 2-3 curators available for HitL review during the boutique evaluation week
- Standard cloud GPU access (~$50-100 in compute over the full run)
- No external blocking (DUA reviews for OMIM/NACC start in Week 1, not Week 5)

The original 12-month plan had 2-3x slack at each stage. Stripping the slack, the realistic finish is end of summer 2026.

---

## 5. Decision Points

Things to resolve in Week 1 to keep the schedule tight:

1. **Embedding model**: stay with SapBERT or evaluate alternatives? Decide before Week 1's bundle build.
2. **Boutique CDE preparation lead**: who at DataTecnica owns the inventory step? This is upstream of the boutique evaluation week and should run in parallel with Sprint 2.
3. **Curator availability**: ~2-3 curators for the boutique evaluation week. Block calendars now.
4. **Public release policy for boutique CDEs**: are all DataTecnica-derived rows publishable in the open bundle, or do some require DUA/IP review? Resolve in Week 1 to avoid blocking v2026.07 release.
5. **Methods paper authorship and venue**: target *npj Digital Medicine* or *JAMIA*. Decide author list and target venue in Week 1 so the analysis frames itself for that audience.
6. **OMIM API access registration and NACC DUA review**: start in Week 1 so they don't gate Sprint 2.
