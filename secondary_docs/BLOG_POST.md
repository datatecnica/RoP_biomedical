# RoP v2026.04: 1.33 Million Harmonized Biomedical Data Elements

**Published:** May 13, 2026
**Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale (DataTecnica)

---

## What Is RoP?

**RoP is 1.33 million harmonized biomedical Common Data Elements with semantic embeddings, value sets, and governance parameters that make multi-cohort research actually interoperable.**

RoP is the foundation for **The Forge** — our automated data and schema harmonization registry with human-in-the-loop validation. Think of RoP as fuel for the harmonization engine.

Right now, multi-cohort studies spend months (often years) manually mapping variables—PPMI calls it "MoCA Total Score," NACC calls it `MOCATOTS`, ADNI calls it `MOCA`. Same assessment, zero automatic compatibility. Multiply this by 500 variables across 10 cohorts, and you're looking at **person-years of manual mapping** before analysis even starts.

**The cost:** Biomedical researchers spend 40-70% of their time on data wrangling and harmonization (Kaggle survey). RoP + The Forge save an order of magnitude in both time and cost for data standardization.

**RoP provides 1.33 million pre-harmonized Common Data Elements (CDEs)** organized into **13 themes** covering every layer of biomedical data—from individual identity and clinical phenotypes to genomics, imaging, governance, and resource catalogs. Built on OMOP, LOINC, ICD-10, HPO, Mondo, and 9 other major vocabularies.

**This isn't aspirational. It's running in production** across hundreds of thousands of samples and multiple millions of data points for collaborators leading massive federated open science initiatives.

![RoP v2026.04 Summary](https://huggingface.co/datasets/DataTecnica/RoP_biomedical/resolve/main/docs/rop_v2026.04_summary.png)

---

## Why It Matters

**We want to accelerate the biomedical research community. Let's make research as FAIR as possible.**

Multi-cohort research shouldn't require 6 months of manual variable mapping before the first analysis. RoP solves this by providing a shared reference that enables:

- **Interoperability:** Tag your variable with a RoP ID once → instant compatibility across federated studies
- **AI-readiness:** Semantic embeddings enable AI-assisted harmonization (10x faster than manual)
- **FAIR principles:** Findable (DOI-versioned), Accessible (open download), Interoperable (cross-vocab mappings), Reusable (full reproducibility)

**The work behind RoP:** Weeks of planning, one weekend of compute, decades of experience. The v2026.04 release represents 6+ person-years of expert harmonization work, distilled into a 7.8 GB download.

---

## What's Inside

```
v2026.04/
├── elements.parquet         1,328,973 CDEs (151 MB)
├── embeddings.npy           768-dim SapBERT vectors (3.9 GB)
├── embeddings.faiss         IVF4096 similarity index (3.9 GB)
└── manifest.json            SHA256 checksums + metadata
```

**Sources:** 1,326,063 foundation CDEs from 9 public standards (OMOP, LOINC, ICD-10, HPO, Mondo, NINDS-CDE, PhenX, CDISC, DICOM, BIDS, DUO) + 2,910 boutique CDEs from 9 project collections.

**13 Themes:** Identity, Time, Sex, Ancestry & Pedigree, Biosample, Omics, Imaging, Clinical Instruments, Governance, Data Assets, Summary Stats, Clinical Concepts, Discoverability (Resources + Collections).

---

## Get RoP

**📥 Download the data:**
[Hugging Face Dataset](https://huggingface.co/datasets/DataTecnica/RoP_biomedical) (7.8 GB, DOI: 10.57967/hf/8781)

**💻 Get the code & full documentation:**
[GitHub Repository](https://github.com/DataTecnica/RoP_biomedical) (build from source, reproducible pipeline)

**🔨 Get help using RoP with The Forge:**
[Submit Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform) (AI-assisted harmonization, governance enforcement)

**✏️ Suggest CDE additions or corrections:**
[Schema Feedback Form](https://docs.google.com/forms/d/1AMvVxiTCRVtiqchtzG3hzMo0p2ix81muvJIYdcV4axw/edit?usp=sharing_eip&ts=69fe1129)

---

## Community & Open Science

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Collaborators:** Mette Peters, Hampton Leonard, Andy Henrie, Amara Alexander, Elise Marsan, Yang Fann, Mark Cookson, Cornelis Blauwendraat, Andy Singleton, Huw Morris, Tim Hohman, Sara Biber, John Crary, Syed Shah, Brittany Dugger, David Gutman, Chris Morris, Pat Brannelly, Liesel Jones, Mat Koretsky, Cole Tindall, Mukta Phatak, Zane Jaunmuktane, Mimi Tambi, Brandon Jernigan, Terri Thompson, Mike Karlovich, Kurt Farrell, and many more... **CDEs are a community effort.**

**Collaborative Efforts:** NIH CARD, GP2, NACC, Answer ALS, SEA-AD, ADSP-PHC, ASAP, BDR, BDSA, PART through their connection with the Path-ND Consortium by the 10,000 Brains Project

**Upstream Standards:** OHDSI (OMOP), Regenstrief (LOINC), Monarch Initiative (HPO, Mondo), NIH (NINDS-CDE, PhenX), CDISC, GA4GH (DUO), DICOM, BIDS

**Foundational Concepts:** This work is based on the preprint by Long et al 2024 (https://pubmed.ncbi.nlm.nih.gov/39484274/), hopefully in press very soon.

---

## License

- **Data** (CDEs, embeddings): **CC-BY-NC-4.0** — Free for non-commercial use with attribution
- **Code** (Python, scripts): **AGPLv3** — Open source, copyleft, non-commercial

**Commercial Use:** Requires separate licensing. Contact **info@datatecnica.com**

---

## Citation

```bibtex
@dataset{rop_v202604,
  author       = {Vitale, Dan and Marini, Pietro and Nalls, Michael A.},
  title        = {RoP v2026.04 - Biomedical Reference of Parameters},
  year         = {2026},
  publisher    = {Hugging Face},
  doi          = {10.57967/hf/8781},
  url          = {https://huggingface.co/datasets/DataTecnica/RoP_biomedical}
}
```

---

**Built with 🔨 by DataTecnica | [datatecnica.com](https://datatecnica.com)**
