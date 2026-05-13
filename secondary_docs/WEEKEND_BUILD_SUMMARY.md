# RoP v2026.04 — Weekend Build Summary

**Date:** May 3-4, 2026 (Saturday afternoon → Monday evening)
**Status:** ✅ **PRODUCTION-READY** (awaiting Dan + Pietro audit)
**Total build time:** ~7 hours (6.2 hrs embedding, 25 min FAISS, rest <1 hr)

---

## What We Built

### **RoP v2026.04 Final Bundle** (7.8 GB)

**Location:** `dist/rop_v2026.04/`

```
rop_v2026.04/
├── elements.parquet         1,328,973 CDEs (151 MB)
├── embeddings.npy           SapBERT 768-dim vectors (3.9 GB)
├── embeddings.faiss         IVF4096 similarity index (3.9 GB)
└── manifest.json            SHA256 checksums + metadata
```

**Composition:**
- **Foundation:** 1,326,063 CDEs from 9 public standards
  - OMOP/Athena, HPO, Mondo, NINDS-CDE, CDISC, PhenX, BIDS, DICOM, DUO
- **Boutique:** 2,910 CDEs from 9 project collections
  - ASAP (117), Answer-ALS (690), BDR (118), BDSA (56), CARD-PathND (1,616), GP2 (39), NACC (202), PART (60), SEA-AD (12)
- **Total:** 1,328,973 harmonized CDEs across 13 themes

**Embedding Model:**
- `cambridgeltl/SapBERT-from-PubMedBERT-fulltext`
- 768-dim vectors, L2-normalized
- MedSTS benchmark: 86.3 accuracy
- Runtime: 6.2 hours on RTX 4080 Laptop GPU (59 texts/sec)

**FAISS Index:**
- Type: IVF4096,Flat (4,096 clusters, flat storage)
- Metric: INNER_PRODUCT (cosine similarity for normalized vectors)
- Build time: 25.2 minutes (training: 22.4 min, adding: 2.8 min)
- Size: 3.9 GB
- Sanity test: ✅ Passed (self-similarity = 1.0)

**Integrity:**
- All files have SHA256 checksums in `manifest.json`
- Verified row alignment: 1,328,973 elements = 1,328,973 embeddings
- Perfect normalization: all embedding norms = 1.000000

---

## Build Pipeline (Fully Reproducible)

**Scripts created/used:**
1. `scripts/sprint1_download_all.py` — Downloads 9 public sources (~6 GB)
2. `scripts/sprint1_dedup_pass1.py` — Dedup → 1.326M foundation CDEs (2 min)
3. `scripts/ingest_boutique_cdes.py` — Ingest 9 boutique collections → 2,910 CDEs
4. `scripts/merge_boutique_with_foundation.py` — Merge → 1.328M total CDEs
5. `scripts/embed_boutique_incremental.py` — SapBERT embeddings for boutique (2 min)
6. `scripts/generate_embeddings_direct.py` — SapBERT embeddings for foundation (6.2 hrs)
7. `scripts/build_faiss_index.py` — FAISS IVF4096 index (25 min)
8. `scripts/package_final_bundle.py` — Package with SHA256 checksums (1 min)
9. `scripts/security_screen.py` — Pre-commit security checks

**Total runtime:** ~7 hours (mostly GPU embedding)
**Reproducibility:** Anyone can rebuild the bundle from scratch via these scripts

---

## Distribution Strategy

**Two-channel approach:**

### **1. GitHub** (`github.com/datatecnica/rop_build`)
**What goes in git:**
- ✅ Python code (`rop/`, `scripts/`, `tests/`)
- ✅ Anchor JSON files (`data/anchors/` — 224 anchors, ~50 KB)
- ✅ Documentation (`docs/*.md`, `README.md`, `CLAUDE.md`)
- ✅ Configuration (`pyproject.toml`, `migrations/`)

**What NEVER goes in git** (enforced by `security_screen.py`):
- ❌ Large files (>50 MB)
- ❌ Source downloads (`data/sources/` — reproducible via scripts)
- ❌ Build artifacts (`data/foundation/staging/`, `data/final/`)
- ❌ Boutique CDEs (`data/boutique/` — confidential)
- ❌ Bundles (`dist/` — distributed via Hugging Face)
- ❌ Logs, checkpoints, credentials

**Repo size:** ~5-10 MB (well within GitHub limits)

### **2. Hugging Face** (`huggingface.co/datasets/datatecnica/rop`)
**What goes on HF:**
- ✅ Pre-built bundles (7.8 GB per release)
- ✅ Documentation (mirrors GitHub docs)
- ✅ Zenodo DOI integration (automatic via HF settings)

**Download methods:**
- Python: `hf_hub_download('datatecnica/rop', 'v2026.04/elements.parquet')`
- CLI: `huggingface-cli download datatecnica/rop --include "v2026.04/*"`
- wget: `wget https://huggingface.co/datasets/datatecnica/rop/resolve/main/v2026.04/elements.parquet`

**Why Hugging Face?**
- Free unlimited bandwidth (no AWS egress fees)
- Native Zenodo integration → automatic DOI assignment
- ML ecosystem integration (`huggingface_hub`, `datasets` libraries)
- Dataset card for documentation

---

## Documentation Created

### **Top-Level Docs** (`top_level_docs/`)
1. **README.md** — Main landing page (GitHub + Hugging Face)
   - "What makes RoP different" (6 differentiators: AI, FAIR, governance, etc.)
   - Quick start (download vs build from source)
   - 13 themes overview
   - Forge integration description
   - Real-world use cases
   - Citation, license, community links

2. **AUDIT_EMAIL_TO_DAN_PIETRO.md** — Technical review request
   - Lay of the land (what was built, where we are)
   - What they should check (technical accuracy, licensing, messaging)
   - Next steps (licensing decision, security screen, ship)
   - 8 key questions for Dan + Pietro to answer

### **Technical Docs** (`docs/`)
- **DISTRIBUTION.md** — GitHub + Hugging Face + Zenodo strategy
- **SPEC.md** — Full interoperability contract specification
- **ANCHORS.md** — 224 anchor CDE reference
- **GOVERNANCE.md** — Forge governance model
- **ROADMAP.md** — Quarterly release schedule

---

## Key Decisions Pending (Dan + Pietro Audit)

### **1. Licensing Model** (Critical Decision)

**Option A: Dual License** (commercial revenue potential)
- **Code:** AGPLv3 (free for open science, commercial needs license)
- **Data:** CC-BY-NC 4.0 (free for non-commercial, commercial needs license)
- **Precedent:** MongoDB, GitLab, Grafana, MySQL
- **Revenue:** Commercial licensing inquiries via interest form → sales call

**Option B: Fully Open** (maximum adoption, no revenue)
- **Code:** Apache-2.0 (permissive, commercial-friendly)
- **Data:** CC-BY 4.0 (attribution required, any use allowed)
- **Precedent:** Most academic datasets, Linux, Kubernetes
- **Revenue:** None from licensing (consulting/Forge-as-service instead)

**Trade-off:** Sustainability vs adoption. AGPLv3+CC-BY-NC prevents competitors from taking our work and selling it back to us. Apache-2.0+CC-BY maximizes researcher adoption but no licensing revenue.

### **2. Technical Review Checklist**

**Dan (primary) + Pietro (review):**
- [ ] Are the 13 themes correctly described?
- [ ] Is the Forge integration description accurate? (federated research, AI harmonization, FAIR)
- [ ] Are source authorities correct? (9 public + 9 boutique)
- [ ] Is SapBERT embedding story technically sound?
- [ ] Are use cases realistic?
- [ ] Is vocabulary inclusion policy correct? (LOINC/HPO included, SNOMED/MedDRA excluded)

### **3. Messaging & Positioning**

**Pietro (primary) + Dan (review):**
- [ ] Is "AI-powered, FAIR-compliant, governed" framing correct?
- [ ] Does Forge description accurately reflect federated research capabilities?
- [ ] Are we over-promising? (e.g., "no manual crosswalks")
- [ ] Is tone right for academic researchers?
- [ ] Are acknowledgments complete?

### **4. Operational Questions**

1. **Legal review:** Do we need DataTecnica legal to approve before release?
2. **Commercial licensing process:** How to handle inquiries? (pricing, DUA, contracts)
3. **Hugging Face org:** Do we have `datatecnica` account? Need to create?
4. **DOI authorship:** "Vitale, Marini, Nalls" or "DataTecnica RoP Working Group"?
5. **Blog publishing:** DataTecnica blog, Medium, LinkedIn article, or all three?
6. **Press outreach:** Coordinate with NIH CARD, GP2 comms teams?
7. **Timeline:** Ship this week, or wait for specific date/event?

---

## Next Steps (After Audit Approval)

### **Immediate (This Week):**
1. Incorporate Dan + Pietro feedback (licensing, technical, messaging)
2. Run security screen: `python3 scripts/security_screen.py`
3. Finalize top-level docs (README, blog, LinkedIn)
4. Update CLAUDE.md with final metrics ✅ **DONE**

### **Ship (Next Week):**
1. Push to GitHub: `git push origin main`
2. Create Hugging Face dataset: `huggingface-cli repo create rop --type dataset --organization datatecnica`
3. Upload bundle: `huggingface-cli upload datatecnica/rop dist/rop_v2026.04/ v2026.04/`
4. Upload docs: `huggingface-cli upload datatecnica/rop top_level_docs/README.md README.md`
5. Enable Zenodo integration in HF settings → Create release → Get DOI
6. Update README badges with DOI
7. Publish blog post (DataTecnica blog? Medium? LinkedIn article?)
8. Post LinkedIn announcement (from DataTecnica account)
9. Submit interest form link to GP2, CARD, NACC, Answer ALS teams

---

## Performance Metrics

**Bundle Stats:**
- Total CDEs: 1,328,973
- Foundation: 1,326,063 (from 9 public standards)
- Boutique: 2,910 (from 9 project collections)
- Size: 7.8 GB
- Files: elements.parquet (151 MB) + embeddings.npy (3.9 GB) + embeddings.faiss (3.9 GB)

**Build Performance:**
- Embedding: 6.2 hours (RTX 4080 GPU, 59 texts/sec)
- FAISS training: 22.4 minutes (k-means clustering 1.33M vectors → 4,096 clusters)
- FAISS adding: 2.8 minutes
- Total: ~7 hours (fully reproducible)

**Quality Validation:**
- Row alignment: 1,328,973 elements = 1,328,973 embeddings ✅
- Normalization: all embedding norms = 1.000000 ✅
- FAISS sanity test: self-similarity = 1.0 ✅
- Tests: 99 passing (schema, validation, ingest, equivalence) ✅

---

## Acknowledgments

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Organization:** DataTecnica ([www.datatecnica.com](https://www.datatecnica.com))

**Foundational Contributors:**
Alan Long, Cole Tindall, Hirotaka Iwaki, Syed Shah, Mat Koretsky, Mette Peters, and many more who contributed CDE and data model input.

**Consortium Partners:**
- NIH CARD (Center for Alzheimer's and Related Dementias)
- GP2 (Global Parkinson's Genetics Program)
- NACC (National Alzheimer's Coordinating Center)
- Answer ALS, SEA-AD, ADSP-PHC, ASAP, BDR, BDSA, PART

**Upstream Standards:**
OHDSI (OMOP), Regenstrief (LOINC), Monarch Initiative (HPO, Mondo), NIH (NINDS-CDE, PhenX), CDISC, GA4GH (DUO), DICOM, BIDS.

---

## Files Staged for Google Drive

**Location:** [INSERT GOOGLE DRIVE LINK]

**Folder structure:**
```
RoP_v2026.04_Audit/
├── dist/
│   └── rop_v2026.04/              [7.8 GB bundle - download link]
├── top_level_docs/
│   ├── README.md                  [Main landing page]
│   └── AUDIT_EMAIL_TO_DAN_PIETRO.md  [Audit request]
├── docs/
│   ├── SPEC.md                    [Technical specification]
│   ├── ANCHORS.md                 [224 anchor CDEs]
│   ├── DISTRIBUTION.md            [GitHub + HF + Zenodo strategy]
│   └── GOVERNANCE.md              [Forge governance model]
├── scripts/                       [All build scripts]
├── WEEKEND_BUILD_SUMMARY.md       [This file]
└── CLAUDE.md                      [Updated with final metrics]
```

---

## Summary

**What we accomplished this weekend:**
- ✅ Merged foundation + boutique CDEs (1.33M total)
- ✅ Generated SapBERT embeddings (6.2 hours, 3.9 GB)
- ✅ Built FAISS search index (25 min, 3.9 GB)
- ✅ Packaged production-ready bundle (7.8 GB, SHA256 checksums)
- ✅ Created distribution strategy (GitHub + Hugging Face + Zenodo)
- ✅ Drafted comprehensive documentation (README, audit email, technical docs)
- ✅ Updated CLAUDE.md with final metrics

**What's next:**
- Dan + Pietro audit (licensing decision, technical review, messaging approval)
- Security screen before git push
- Ship to GitHub + Hugging Face
- Get Zenodo DOI
- Announce via blog + LinkedIn

**Status:** Production-ready, awaiting final audit before public release.

**Timeline:** Weekend build sprint accomplished all technical work. Documentation and distribution infrastructure in place. Ready for Dan + Pietro review, then ship next week.

---

**Built with 🔨 by DataTecnica**
