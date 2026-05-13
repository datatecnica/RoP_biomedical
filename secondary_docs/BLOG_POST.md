# RoP v2026.04: AI-Assisted Data Harmonization That Actually Works

**Published:** May 13, 2026
**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

---

## Decreasing Activation Energy in Biomedical Research

**RoP is 1.33 million harmonized biomedical Common Data Elements with semantic embeddings, value sets, and governance parameters that make multi-cohort research actually interoperable.**

RoP decreases activation energy in biomedical research by accelerating progress past the biggest bottlenecks ... data wrangling, interoperability and AI-readiness.

If you run multi-cohort biomedical studies, you know this pattern:

**Your team spends 6 months mapping variables before the first analysis.**

PPMI calls it "MoCA Total Score." NACC calls it `MOCATOTS`. ADNI calls it `MOCA`. Your site calls it `moca_total`.

Same cognitive assessment. Same 30-point scale. Four different names across four cohorts. No automatic way to merge them.

Multiply this by 500 variables across 10 cohorts, and you're looking at **person-years of manual harmonization** — expert panels, circulating spreadsheets, someone maintaining a 47-tab Excel crosswalk that becomes the single point of failure for your entire consortium.

This isn't a niche problem. Every multi-cohort meta-analysis, every data catalog, every biobank integration hits this wall.

**Today we're releasing the solution we built for ourselves — and open-sourcing it.**

---

## What We Shipped This Weekend

**RoP v2026.04** — 1.33 million harmonized Common Data Elements powering The Forge's AI-assisted, federated harmonization platform.

**Download:**
- 📥 [Hugging Face](https://huggingface.co/datasets/DataTecnica/RoP_biomedical) — Pre-built bundle (7.8 GB)
- 🔨 [GitHub](https://github.com/DataTecnica/RoP_biomedical) — Build from source (7 hours on GPU)

### The Bundle
```
v2026.04/
├── elements.parquet         1,328,973 harmonized CDEs (151 MB)
├── embeddings.npy           SapBERT 768-dim vectors (3.9 GB)
├── embeddings.faiss         IVF4096 similarity index (3.9 GB)
└── manifest.json            SHA256 checksums + metadata
```

**What's inside:**
- **1,326,063 foundation CDEs** from 9 public standards: OMOP, LOINC, ICD-10, HPO, Mondo, NINDS-CDE, PhenX, CDISC, DICOM, BIDS, DUO
- **2,910 boutique CDEs** from 9 project collections: GP2, CARD, NACC, Answer ALS, SEA-AD, Path-ND, 10,000 Brains Project, ASAP, BDR, BDSA, PART
- **SapBERT embeddings** (768-dim, trained on 23M PubMed abstracts)
- **FAISS similarity index** (sub-second search across 1.33M elements)

---

## How The Forge Uses RoP to 10x Harmonization Speed

**The Forge uses AI-assisted human-in-the-loop workflows to 10x the speed of data harmonization across federated silos.**

### The Old Way (6 Months)
1. Consortium forms harmonization committee
2. Committee meets monthly to review variable mappings
3. Expert debates equivalence ("Is UPDRS Part III Motor Score the same as MDS-UPDRS Part III?")
4. Someone maintains Excel crosswalk
5. New cohort joins → restart from step 1

### The Forge Way (<10 Minutes Per Cohort)
1. **Upload data dictionary** → Forge ingests your variable list
2. **AI suggests matches** → Semantic embeddings find `MoCA_TotalScore` and 47 equivalent CDEs across all cohorts
3. **Human curator reviews** → Expert validates AI suggestions in <10 minutes (not 6 months)
4. **Governance enforcement** → Forge validates consent codes (DUO), value ranges, required fields
5. **Block non-compliant data** → Violations caught at ingest, before data enters your pipeline
6. **Federated deployment** → Each site runs Forge locally, data never leaves institution

**This isn't aspirational. It's running in production** across hundreds of thousands of samples and multiple millions of data points for collaborators leading massive federated open science initiatives.

---

## Six Things That Make RoP Different

### 1. **1.33 Million Harmonized CDEs (Not 200 Committee-Approved Variables)**

Most CDE projects publish 50-500 "consensus" variables and hope the field adopts them.

**RoP integrates everything:** OMOP (1.2M concepts), LOINC (100K+ lab tests), ICD-10 (70K+ diagnoses), HPO (17K+ phenotypes), Mondo (25K+ diseases), plus NINDS-CDE, PhenX, CDISC, DICOM, BIDS, DUO.

**Cross-vocabulary mappings preserved as first-class data.** Looking for "Parkinson's disease"? RoP connects:
- ICD-10-CM: `G20`
- OMOP: `378419` (Primary parkinsonism)
- HPO: `HP:0001300` (Parkinsonism)
- Mondo: `MONDO:0005180`
- NINDS-CDE: `ParkinsonsDisease_DiagnosticStatus`

One RoP tag → interoperability across all five vocabularies.

### 2. **AI-Assisted (Not AI-Automated) Matching**

**We don't trust AI alone.** The Forge uses semantic embeddings to *suggest* matches, then routes to human experts for review.

**The workflow:**
- AI: "Your `moca_total` variable looks 94% similar to RoP's `MoCA_TotalScore`. Here are 12 other cohorts using this CDE."
- Human curator: "Correct, approve" or "Wrong scale, it's actually MoCA-BLIND, map to this other CDE instead"
- Forge: Learns from correction, improves suggestions for next cohort

**Result:** 10x faster than manual (minutes vs months), maintains expert quality control.

### 3. **Federated by Design (Data Sovereignty + Interoperability)**

Most "federated" solutions are aspirational. The Forge runs this in production:

**How it works:**
- Each site deploys Forge locally (on-prem or private cloud)
- Sites map their variables to shared RoP IDs
- Coordinating center receives **harmonized schemas + summary statistics** (not raw data)
- Distributed queries run across sites without data movement
- Governance rules (consent codes, sharing restrictions) enforced at each site

**Real-world example:** GP2 has 30+ cohorts across 15 countries. Each site runs Forge locally. Coordinating center sees harmonized `LRRK2_G2019S_Status` from all sites without seeing individual-level data.

### 4. **Governed at Ingest (Not "After the Paper")**

Most CDE projects publish standards and hope people adopt them.

**The Forge enforces conformance when data enters your system:**
- Upload violates DUO consent code → **blocked at ingest**
- Value outside plausible range (age = 350) → **blocked at ingest**
- Missing required field for Theme 9 (governance) → **blocked at ingest**

Non-compliant data never reaches your analysis pipeline.

### 5. **FAIR as Infrastructure (Not Aspiration)**

RoP bundles are **Findable, Accessible, Interoperable, Reusable** by design:

- **F**indable: DOI-versioned releases on Zenodo + Hugging Face
- **A**ccessible: Open download, no SNOMED/MedDRA license fees (AGPLv3 + CC-BY-NC)
- **I**nteroperable: Parquet format, FAISS index, semantic embeddings, cross-vocab xrefs
- **R**eusable: SHA256 checksums, full build scripts, reproducible pipelines

Every release includes machine-readable provenance (`manifest.json`), cryptographic integrity checks, and scripts to rebuild the bundle from scratch (7 hours on consumer GPU).

### 6. **Quarterly Releases (Not 5-Year Publication Cycles)**

**Traditional CDEs:** Committee publishes v1.0 in 2020 → Errata in 2022 → Maybe v2.0 in 2025

**RoP:** Quarterly releases (v2026.04, v2026.07, v2026.10, v2027.01...) with:
- New vocabularies and collections
- Improved embeddings (BioLORD-2023 next quarter: +2% accuracy)
- Bug fixes, governance updates, schema migrations

Pin the version in your methods section for reproducibility. Upgrade when you're ready.

---

## Beyond Biomedicine: Stock Trading + Motorsports

**The harmonization pattern transfers cleanly to other verticals.**

We're exploring applications with collaborators in:
- **Stock trading:** Social data + market integration (harmonizing Bloomberg, Reuters, social sentiment, alternative data)
- **Motorsports:** Safety, performance, marketing integration (harmonizing telemetry, incident reports, fan engagement metrics)

Same problems (fragmented data silos, manual mapping, governance challenges), same solution (AI-assisted HitL + federated architecture + versioned schemas).

---

## Who This Is For

### Multi-Cohort Researchers
Map 500 variables to RoP IDs once → merge PPMI, ADNI, NACC, Answer ALS with zero manual crosswalks.

### Data Catalog Builders
Use Theme 13 (Discoverability) for standardized study metadata: sample sizes, modalities, consent codes, FAIR scores.

### Biobank/Repository Operators
Use Theme 9 + Forge to block data uploads violating DUO consent codes or sharing restrictions — before data enters your system.

### Meta-Analysis Teams
Theme 11 (Summary Statistics) harmonizes GWAS covariates: no more "which ancestry PCs did they use?" detective work.

### Federated Consortia
Deploy Forge at each site, harmonize to shared RoP IDs, run distributed analyses without data movement.

---

## Why We're Open-Sourcing This

**We want to accelerate the biomedical research community. Let's make research as FAIR as possible.**

We built RoP + The Forge to solve the harmonization bottleneck we saw across every major project we worked on.

**We're releasing RoP openly (AGPLv3 + CC-BY-NC)** because the field needs shared infrastructure, not siloed CDE projects.

**Free for research. Commercial licensing available for for-profit use.**

---

## Get Started

**Download RoP v2026.04:**
- 📥 Hugging Face (fastest): [DataTecnica/RoP_biomedical](https://huggingface.co/datasets/DataTecnica/RoP_biomedical)
- 📚 Zenodo (DOI): [10.57967/hf/8781](https://doi.org/10.57967/hf/8781)

**Build from source:**
```bash
git clone https://github.com/DataTecnica/RoP_biomedical.git
cd RoP_biomedical && pip install -e .
python3 scripts/sprint1_download_all.py          # Download 9 sources (6 GB)
python3 scripts/sprint1_dedup_pass1.py           # Dedup (2 min)
python3 scripts/generate_embeddings_direct.py    # Embed (6 hrs GPU / 30 hrs CPU)
python3 scripts/build_faiss_index.py             # Index (25 min)
python3 scripts/package_bundle.py                # Package (1 min)
```

**Interested in help using RoP? Try The Forge:**
[Submit Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform)

---

## What's Next

**v2026.07 (July):**
- BioLORD-2023 embeddings (+2% MedSTS accuracy over SapBERT)
- BIDS derivatives metadata, imaging QC flags
- FHIR alignment for EHR interoperability

**v2026.10 (October):**
- Domain-tuned embedding models (Alzheimer's-specific, Parkinson's-specific)
- Enhanced DUO governance (granular use restrictions)
- 10+ new boutique collections

**v2027.01 (January):**
- FAIR assessment automation
- Forge API v2 (GraphQL)
- RoP browser UI (search, explore, contribute)

---

## Acknowledgments

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Collaborators:** Mette Peters, Hampton Leonard, Andy Henrie, Amara Alexander, Elise Marsan, Yang Fann, Mark Cookson, Cornelis Blauwendraat, Andy Singleton, Huw Morris, Tim Hohman, Sara Biber, John Crary, Syed Shah, Brittany Dugger, David Gutman, Chris Morris, Pat Brannelly, Liesel Jones, Mat Koretsky, Cole Tindall, Mukta Phatak, Zane Jaunmuktane, Mimi Tambi, Brandon Jernigan, Terri Thompson, Mike Karlovich, Kurt Farrell, and many more... **CDEs are a community effort.**

**Collaborative Efforts:**
NIH CARD, GP2, NACC, Answer ALS, SEA-AD, ADSP-PHC, ASAP, BDR, BDSA, PART through their connection with the Path-ND Consortium by the 10,000 Brains Project

**Upstream Standards:**
OHDSI (OMOP), Regenstrief (LOINC), Monarch Initiative (HPO, Mondo), NIH (NINDS-CDE, PhenX), CDISC, GA4GH (DUO), DICOM, BIDS

**Foundational Concepts:**
Foundational concepts for this work are based on this preprint (Long et al 2024, https://pubmed.ncbi.nlm.nih.gov/39484274/) hopefully in press very soon.

---

## Join the RoP Community

- **📋 Interest Form:** [Start here](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform)
- **🐛 Bug Reports:** [GitHub Issues](https://github.com/DataTecnica/RoP_biomedical/issues)
- **📧 Email:** info@datatecnica.com

---

## Citation

```bibtex
@dataset{rop_v202604,
  author       = {Vitale, Dan and
                  Marini, Pietro and
                  Nalls, Michael A.},
  title        = {RoP v2026.04 - Biomedical Reference of Parameters},
  year         = {2026},
  publisher    = {Hugging Face},
  doi          = {10.57967/hf/8781},
  url          = {https://huggingface.co/datasets/DataTecnica/RoP_biomedical}
}
```

---

**License:** AGPLv3 (code) + CC-BY-NC 4.0 (data) — free for research, commercial licensing available
**Built with 🔨 by DataTecnica | [www.datatecnica.com](https://www.datatecnica.com)**
