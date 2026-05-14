# LinkedIn Post: RoP v2026.04 Release

---

**We're releasing RoP v2026.04 — 1.33 million harmonized biomedical Common Data Elements — openly for the research community.**

## What & Why

**RoP is 1.33 million harmonized biomedical Common Data Elements with semantic embeddings, value sets, and governance parameters that make multi-cohort research actually interoperable.**

RoP is the foundation for **The Forge** — our automated data and schema harmonization registry with human-in-the-loop validation. Think of RoP as fuel for the harmonization engine.

Right now, multi-cohort studies spend months manually mapping variables. PPMI calls it "MoCA Total Score," NACC calls it `MOCATOTS`, ADNI calls it `MOCA`. Same assessment, zero automatic compatibility.

**The cost:** Biomedical researchers spend 40-70% of their time on data wrangling and harmonization (Kaggle survey). RoP + The Forge save an order of magnitude in both time and cost for data standardization.

**We want to accelerate the biomedical research community. Let's make research as FAIR as possible.**

RoP provides a shared reference covering every layer of biomedical data—from individual identity and clinical phenotypes to genomics, imaging, governance, and resource catalogs. Built on OMOP, LOINC, ICD-10, HPO, Mondo, and 9 other major vocabularies.

**This isn't aspirational. It's running in production** across hundreds of thousands of samples and multiple millions of data points for collaborators leading massive federated open science initiatives.

![RoP v2026.04](https://huggingface.co/datasets/DataTecnica/RoP_biomedical/resolve/main/docs/rop_v2026.04_summary.png)

## What's Inside

- **1,328,973 CDEs** organized into **13 themes**
- **768-dim semantic embeddings** (SapBERT, trained on 23M PubMed abstracts)
- **IVF4096 FAISS index** (sub-second similarity search)
- **Full reproducibility** (SHA256 checksums, build scripts)

**Sources:** 9 public standards (OMOP, LOINC, ICD-10, HPO, Mondo, NINDS-CDE, PhenX, CDISC, DICOM, BIDS, DUO) + 9 project collections

## Get RoP

📥 **Data:** [Hugging Face](https://huggingface.co/datasets/DataTecnica/RoP_biomedical) (7.8 GB, DOI: 10.57967/hf/8781)

💻 **Code & Docs:** [GitHub](https://github.com/DataTecnica/RoP_biomedical) (full documentation, build from source)

📋 **Questions / Help:** [Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform)

✏️ **CDE Suggestions:** [Schema Feedback](https://docs.google.com/forms/d/1AMvVxiTCRVtiqchtzG3hzMo0p2ix81muvJIYdcV4axw/edit?usp=sharing_eip&ts=69fe1129)

## Community Effort

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Collaborators:** Mette Peters, Hampton Leonard, Andy Henrie, Amara Alexander, Elise Marsan, Yang Fann, Mark Cookson, Cornelis Blauwendraat, Andy Singleton, Huw Morris, Tim Hohman, Sara Biber, John Crary, Syed Shah, Brittany Dugger, David Gutman, Chris Morris, Pat Brannelly, Liesel Jones, Mat Koretsky, Cole Tindall, Mukta Phatak, Zane Jaunmuktane, Mimi Tambi, Brandon Jernigan, Terri Thompson, Mike Karlovich, Kurt Farrell, and many more... **CDEs are a community effort.**

**Collaborative Efforts:** NIH CARD, GP2, NACC, Answer ALS, SEA-AD, ADSP-PHC, ASAP, BDR, BDSA, PART through their connection with the Path-ND Consortium by the 10,000 Brains Project

**Foundational Concepts:** Based on the preprint by Long et al 2024 (https://pubmed.ncbi.nlm.nih.gov/39484274/)

## License

**Data:** CC-BY-NC-4.0 (free for non-commercial use)
**Code:** AGPLv3 (open source)
**Commercial:** Contact info@datatecnica.com

**Built with 🔨 by DataTecnica | [datatecnica.com](https://datatecnica.com)**

---

#OpenScience #DataHarmonization #FAIR #Bioinformatics #Neuroscience #Genomics #ClinicalResearch
