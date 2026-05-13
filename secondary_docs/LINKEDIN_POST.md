# LinkedIn Post: RoP v2026.04 Release

---

**RoP is 1.33 million harmonized biomedical Common Data Elements with semantic embeddings, value sets, and governance parameters that make multi-cohort research actually interoperable.**

RoP decreases activation energy in biomedical research by accelerating progress past the biggest bottlenecks ... data wrangling, interoperability and AI-readiness.

**The Forge uses AI-assisted HitL workflows to 10x the speed of data harmonization across federated silos.**

Today DataTecnica is releasing RoP v2026.04 — the open-source CDE reference powering The Forge's federated harmonization platform.

**Get started:**
- 📥 **Download RoP bundle** → [Hugging Face](https://huggingface.co/datasets/DataTecnica/RoP_biomedical) (1.33M CDEs, embeddings, search index)
- 🔨 **Build from source** → [GitHub](https://github.com/DataTecnica/RoP_biomedical) (full reproducibility, 7 hours on GPU)
- 📋 **Interested in help using RoP? Try The Forge** → [Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform)

---

**The problem:**

PPMI calls it "MoCA Total Score"
NACC calls it `MOCATOTS`
ADNI calls it `MOCA`
Your site calls it `moca_total`

Same 30-point cognitive assessment. Four cohorts. **Zero automatic interoperability.**

Multiply by 500 variables × 10 cohorts = **person-years of manual harmonization before your first analysis.**

---

**The solution:**

**RoP** = 1,328,973 harmonized CDEs from OMOP, LOINC, ICD-10, HPO, Mondo, NINDS-CDE, PhenX, CDISC, DICOM, BIDS, DUO

**The Forge** = AI-assisted governance platform that:
1. Suggests RoP matches using semantic embeddings (not keyword search)
2. Human curator reviews AI suggestions in **<10 minutes** (vs 6 months manual)
3. Validates consent codes (DUO), value ranges, required fields
4. **Blocks non-compliant data at ingest** (governance enforced, not aspirational)
5. Runs **federated** — data stays at local sites, only harmonized schemas + stats shared

**Business Impact:** Biomedical researchers spend 40-70% of their time on harmonization and data wrangling (Kaggle survey). RoP + The Forge reduce this by an order of magnitude in both time and cost. Already powering our work in massive federated studies, enabling true interoperability and AI readiness at scale.

---

**What we shipped this weekend:**

✅ 1,328,973 harmonized CDEs (foundation + 9 boutique collections)
✅ SapBERT embeddings (768-dim, trained on 23M PubMed abstracts)
✅ FAISS similarity index (sub-second search across 1.33M elements)
✅ SHA256 checksums, DOI versioning, full build scripts
✅ Open source: AGPLv3 (code) + CC-BY-NC 4.0 (data) — free for research

---

**Running in production:** across hundreds of thousands of samples and multiple millions of data points for collaborators leading massive federated open science initiatives.

**Applications underway (new verticals with collaborators):**
- Stock trading (social data + market integration)
- Motorsports (safety, performance, marketing integration)

The harmonization pattern (AI-assisted HitL + federated governance + versioned schemas) transfers cleanly beyond biomedicine.

---

**Why this matters:**

We want to accelerate the biomedical research community. Let's make research as FAIR as possible. Releasing RoP openly because the field needs shared infrastructure, not siloed CDE projects.

**Quarterly releases. No SNOMED/MedDRA license fees. Federated-first architecture.**

---

**Acknowledgments:**

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Collaborators:** Mette Peters, Hampton Leonard, Andy Henrie, Amara Alexander, Elise Marsan, Yang Fann, Mark Cookson, Cornelis Blauwendraat, Andy Singleton, Huw Morris, Tim Hohman, Sara Biber, John Crary, Syed Shah, Brittany Dugger, David Gutman, Chris Morris, Pat Brannelly, Liesel Jones, Mat Koretsky, Cole Tindall, Mukta Phatak, Zane Jaunmuktane, Mimi Tambi, Brandon Jernigan, Terri Thompson, Mike Karlovich, Kurt Farrell, and many more... **CDEs are a community effort.**

**Collaborative Efforts:** NIH CARD, GP2, NACC, Answer ALS, SEA-AD, ADSP-PHC, ASAP, BDR, BDSA, PART through their connection with the Path-ND Consortium by the 10,000 Brains Project

**Foundational Concepts:** Foundational concepts for this work are based on this preprint (Long et al 2024, https://pubmed.ncbi.nlm.nih.gov/39484274/) hopefully in press very soon.

**Built with 🔨 by DataTecnica** | [www.datatecnica.com](https://www.datatecnica.com)

---

#DataHarmonization #FederatedResearch #Bioinformatics #FAIR #Neuroscience #AIassistedWorkflows #OpenScience
