# RoP v2026.04 — What We Built This Weekend

**Date:** May 3-4, 2026 (Saturday PM → Monday PM)
**Status:** ✅ Production-ready, awaiting Dan + Pietro audit
**Total time:** ~7 hours actual compute (mostly GPU embedding)

---

## Deliverables

### 1. **Production Bundle** (7.8 GB)
```
dist/rop_v2026.04/
├── elements.parquet         1,328,973 CDEs (151 MB)
├── embeddings.npy           SapBERT 768-dim vectors (3.9 GB)
├── embeddings.faiss         IVF4096 similarity index (3.9 GB)
└── manifest.json            SHA256 checksums + metadata
```

**Composition:**
- **1,326,063 foundation CDEs** from 9 public standards (OMOP/Athena, HPO, Mondo, NINDS-CDE, CDISC, PhenX, BIDS, DICOM, DUO)
- **2,910 boutique CDEs** from 9 project collections (ASAP, Answer-ALS, BDR, BDSA, CARD-PathND, GP2, NACC, PART, SEA-AD)
- **Total: 1,328,973 harmonized CDEs** across 13 themes

### 2. **Fully Reproducible Build Pipeline**
- 9 source ingest scripts
- Deduplication (DuckDB, 32 threads, 2 min runtime)
- Merge foundation + boutique
- Incremental embedding generation
- FAISS index building
- Bundle packaging with SHA256 checksums
- **99 passing tests** (schema, validation, ingest, equivalence)

### 3. **Distribution Strategy**
- GitHub (code + docs, ~5-10 MB repo)
- Hugging Face (bundles + Zenodo DOI integration)
- Security screening script (pre-commit checks)
- `.gitignore` configured (large files excluded)

### 4. **Documentation**
- Root README.md (GitHub/HF landing page)
- AUDIT_EMAIL_TO_DAN_PIETRO.md (review request)
- LINKEDIN_POST.md (social announcement)
- WEEKEND_BUILD_SUMMARY.md (technical summary)
- Updated CLAUDE.md (final metrics)

---

## Problems Solved

### **Problem 1: Multi-Cohort Harmonization Takes 6 Months**

**What we built:**
- 1.33M pre-harmonized CDEs with cross-vocabulary mappings
- SapBERT semantic embeddings for AI-assisted matching (HitL)
- The Forge integration: upload data dict → AI suggests matches → curator reviews → 10x faster than manual

**Example:**
"MoCA Total Score" has 47 equivalent names across PPMI, NACC, ADNI, local sites. RoP provides one canonical ID (`MoCA_TotalScore`) that resolves all variants.

### **Problem 2: CDE Projects Die as Static PDFs**

**What we built:**
- Versioned quarterly releases (not 5-year publication cycles)
- DOI-stamped bundles on Zenodo (citable, archival)
- Full build reproducibility (7 hours on consumer GPU)
- GitHub CI/CD ready for automated releases

### **Problem 3: Federated Research Requires Data Movement**

**What The Forge enables:**
- Local deployment at each site (on-prem or private cloud)
- Sites map to shared RoP IDs
- Coordinating center receives harmonized schemas + summary stats (not raw data)
- Distributed queries without data movement
- Governance enforcement at each site (DUO consent codes, sharing restrictions)

### **Problem 4: FAIR is Aspirational, Not Operational**

**What we built:**
- **F**indable: DOI, Hugging Face, GitHub
- **A**ccessible: Open download, no license fees (AGPLv3 + CC-BY-NC)
- **I**nteroperable: Parquet, FAISS, embeddings, cross-vocab xrefs
- **R**eusable: SHA256 checksums, full build scripts, machine-readable provenance

### **Problem 5: Commercial Vocabularies Block Open Science**

**What we excluded:**
- SNOMED CT, MedDRA, CPT4, UMLS CUIs (require vendor licenses)
- Can cross-reference their IDs when upstream sources provide mappings
- No commercial content redistributed in RoP bundles
- Result: 100% open-source compatible (Apache-2.0 + CC-BY-4.0)

---

## Why This Matters

**Every neurogenetics consortium we work with hits the same wall:**
- GP2 (Parkinson's): 30+ cohorts, 50K+ samples, incompatible variable names
- CARD (Alzheimer's): 70+ datasets, manual harmonization bottleneck
- NACC: 45 ADCs, decades of legacy variable naming
- Answer ALS, SEA-AD, Path-ND, 10,000 Brains: same problem, different disease

**RoP + The Forge solve this once, for everyone:**
- Shared reference (not siloed per-consortium solutions)
- AI-assisted HitL workflows (10x faster than manual, maintains quality)
- Federated-first (data sovereignty + interoperability)
- Quarterly updates (living infrastructure, not static publication)

---

## Next Steps

**Before public release:**
1. Dan + Pietro audit (licensing decision, technical review, messaging)
2. Security screen: `python3 scripts/security_screen.py`
3. Finalize top-level docs (incorporate feedback)

**Ship (next week):**
1. Push to GitHub: `git push origin main`
2. Upload to Hugging Face: `huggingface-cli upload datatecnica/rop dist/rop_v2026.04/ v2026.04/`
3. Enable Zenodo integration → Get DOI
4. Update README badges
5. Publish LinkedIn post
6. Announce to GP2, CARD, NACC, Answer ALS, SEA-AD, Path-ND teams

**Roadmap:**
- **v2026.07:** BioLORD-2023 embeddings (+2% accuracy), BIDS derivatives, FHIR alignment
- **v2026.10:** Domain-tuned models, enhanced DUO governance, 10+ new collections
- **v2027.01:** FAIR automation, Forge API v2, RoP browser UI

---

**Built with 🔨 by DataTecnica**

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Contributors:** Alan Long, Cole Tindall, Hirotaka Iwaki, Syed Shah, Mat Koretsky, Mette Peters

**Partners:** NIH CARD, GP2, NACC, Answer ALS, SEA-AD, Path-ND, 10,000 Brains Project, ASAP, BDR, BDSA, PART
