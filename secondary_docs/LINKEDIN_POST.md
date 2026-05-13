# LinkedIn Post: RoP v2026.04 Release

---

**Stop spending 6 months manually mapping variables across cohorts.**

**The Forge uses AI-assisted HitL workflows to 10x the speed of data harmonization across federated silos.**

Today DataTecnica is releasing RoP v2026.04 — the open-source CDE reference powering The Forge's federated harmonization platform.

**Get started:**
- 📥 **Download RoP bundle** → [Hugging Face](https://huggingface.co/datasets/datatecnica/rop) (1.33M CDEs, embeddings, search index)
- 🔨 **Build from source** → [GitHub](https://github.com/datatecnica/rop_build) (full reproducibility, 7 hours on GPU)
- 📋 **Try The Forge** → [Interest Form](https://docs.google.com/forms/d/e/1FAIpQLSfo9btfS1FxrptzAXWAMUT9bfkEJUEL0Swmg3jkEBIncGbI4A/viewform) (AI-assisted harmonization for your cohort)

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

**Running in production (biomedical):**
- GP2 (Global Parkinson's Genetics Program)
- NIH CARD (Alzheimer's / Related Dementias)
- NACC (National Alzheimer's Coordinating Center)
- Answer ALS, SEA-AD, Path-ND, 10,000 Brains Project

**Applications underway (new verticals with collaborators):**
- Stock trading (social data + market integration)
- Motorsports (safety, performance, marketing integration)

The harmonization pattern (AI-assisted HitL + federated governance + versioned schemas) transfers cleanly beyond biomedicine.

---

**Why this matters:**

Every consortium we work with hits the same harmonization wall. We built RoP + The Forge to solve it — releasing RoP openly because the field needs shared infrastructure, not siloed CDE projects.

**Quarterly releases. No SNOMED/MedDRA license fees. Federated-first architecture.**

---

**Acknowledgments:**

**Primary Authors:** Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale

**Collaborators:** Mette Peters, Hampton Leonard, Andy Henrie, Amara Alexander, Elise Marsan, Yang Fann, Mark Cookson, Cornelis Blauwendraat, Andy Singleton, Huw Morris, Tim Hohman, Sara Biber, John Crary, Syed Shah, Brittany Dugger, David Gutman, Chris Morris, Pat Brannelly, Liesel Jones, Mat Koretsky, Cole Tindall, Mukta Phatak, Zane Jaunmuktane, Mimi Tambi, Brandon Jernigan, Terri Thompson, Mike Karlovich, Kurt Farrell, and many more... **CDEs are a community effort.**

**Partners:** NIH CARD, GP2, NACC, Answer ALS, SEA-AD, Path-ND, 10,000 Brains Project, ASAP, BDR, BDSA, PART

**Built with 🔨 by DataTecnica** | [www.datatecnica.com](https://www.datatecnica.com)

---

#DataHarmonization #FederatedResearch #Bioinformatics #FAIR #Neuroscience #AIassistedWorkflows #OpenScience
