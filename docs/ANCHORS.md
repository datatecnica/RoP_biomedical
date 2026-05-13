# Core Anchor CDEs

The Core Anchor CDEs are the strictly-typed floor of the RoP contract. Every cohort claiming interoperability must declare anchors in the themes relevant to the data being submitted. This document is the human-readable reference; the normative definitions live in `data/anchors/*.json`.

## Themes, not tiers or modules

RoP organizes its anchor floor into **13 themes**: 12 covering general CDEs harmonized from upstream source authorities (LOINC, OMOP/Athena, ICD-10/11, SNOMED-via-OMOP, RxNorm, MedDRA, HPO, OMIM, Mondo, NACC, NINDS-CDE, PhenX, CDISC, DUO, plus DataTecnica-derived rows), and 1 forming the **Discoverability** layer (Resources + Special Collections, as sub-themes 13a / 13b) that catalogs what data exists and how it's organized. The term "theme" replaces earlier "tier" / "module" because the 13 groupings are not strictly hierarchical: themes 9–13 are orthogonal attestations rather than additional analytical layers, and themes can have sub-themes. Some legacy code and documentation uses "tier" or "module" as backward-compatible synonyms.

| Theme | Name | File(s) |
|-------|------|---------|
| 1   | Identity | `01_identity.json` |
| 2   | Time | `02_time.json` |
| 3   | Sex | `03_sex.json` |
| 4   | Ancestry & Pedigree (merged) | `04_ancestry_pedigree.json` |
| 5   | Biosample (sub-themes: 5a core, 5b anatomy/cell type) | `05_biosample.json`, `05b_anatomy_celltype.json` |
| 6   | Omics Platform | `06_omics.json` |
| 7   | Imaging Acquisition Metadata (DICOM/BIDS) | `07_imaging_acquisition.json` |
| 8   | Clinical Assessment Instruments | `08_clinical_instruments.json` |
| 9   | Governance & Consent | `09_governance.json` |
| 10  | Data Asset References | `10_data_assets.json` |
| 11  | Summary Statistics | `11_summary_stats.json` |
| 12  | **Clinical Concepts** (ICD, OMOP/Athena, LOINC clinical labs, RxNorm, MedDRA, SNOMED-via-OMOP) | `12_clinical_concepts.json` |
| 13a | Discoverability — Resources | `13a_resources.json` |
| 13b | Discoverability — Special Collections | `13b_collections.json` |

### Where source authorities fit

Sources are **orthogonal to themes**: a single source authority typically contributes to multiple themes based on what its content describes. A given RoP row carries `source_authority`, `source_code`, and `source_version` regardless of which theme owns its anchor coverage. Multiple sources can contribute to a single theme.

| Source | Primary themes | Secondary themes |
|--------|----------------|------------------|
| **LOINC** | 12 (clinical labs, vital signs), 6 (omics six-axis foundation) | 8 (instrument panel codes), 4 (lab-based ancestry markers) |
| **OMOP / Athena** | 12 (cross-vocab pivot — concept_id space) | All themes (standardized concept resolution) |
| **DICOM** | 7 (imaging acquisition tags) | — |
| **BIDS** | 7 (imaging organization conformance) | — |
| **ICD-10 / ICD-11** | 12 (diagnoses) | 4 (when used for pedigree disease status) |
| **SNOMED CT** (via OMOP) | 12 (clinical findings, procedures) | 5 (body structures) |
| **RxNorm** | 12 (drug exposures) | — |
| **MedDRA** | 12 (adverse events) | 11 (AE summary stats) |
| **HPO** | 12 (clinical findings) | 4 (when used), 11 (HPO-based summary stats) |
| **OMIM** | 12 (Mendelian conditions) | 4 (when used) |
| **Mondo** | 12 (rare disease, diagnosis xrefs) | 4 (when used) |
| **NACC / NINDS-CDE / PhenX** | 8 (clinical instruments), 12 (observations) | 4 (demographics) |
| **CDISC** | 11 (summary stats), 12 (AE/CM/MH domains) | — |
| **DUO** | 9 (consent class) | — |



## Why anchors are different from ordinary RoP rows

Most RoP rows are reference material — concepts a cohort *might* use, surfaced through Forge's matcher when an incoming variable resolves to them. Anchors are different in three ways:

1. **They are mandatory** for the data classes they govern. A longitudinal cohort that doesn't declare Tier 1 anchors fails validation.
2. **They have transformation rules.** When NACC ships visit numbers and PPMI ships years-from-enrollment, Forge transforms between the canonical representations rather than asking a curator to map them.
3. **They have stricter controlled vocabularies.** Where a regular RoP row might use free text plus a derived controlled-vocab field, anchors lean toward the controlled side and treat free text as supplementary.

Anchors define the minimum interoperability surface. Everything else is optional convenience.

## Theme 1: Identity

**File**: `data/anchors/00_identity.json`

Identity is the prerequisite that everything else attaches to. Without a stable, cohort-unique participant identifier, there is no longitudinal linkage, no sample lineage, no family-based genetics, and no governance enforcement. The Tier 0 design adds two federation mechanisms alongside the primary identifier: cross-cohort aliases for identity resolution, and structured GA4GH-aligned external dataset linkages that get downstream consumers to the actual repositories where each individual's data lives.

| Anchor | Type | Description |
|--------|------|-------------|
| `IndividualID` | string | Cohort-unique participant identifier; FK target for biosample, visit, and observation rows |
| `IndividualAliases` | string (JSON array) | Cross-cohort/system identifier aliases as `{authority, identifier, linkage_method, linkage_confidence}` entries |
| `IndividualExternalDatasets` | string (JSON array) | GA4GH-aligned per-repository linkages: which repositories hold this individual's data, which GA4GH services they expose (DRS, Beacon v2, Data Connect, Phenopackets, TES), endpoint URLs, authentication requirements, and data scope |

**PHI handling**: `IndividualID` is treated as PHI. When data crosses institutional boundaries, exported `IndividualID` values should be pseudonymized derivatives (HMAC of the cohort-native identifier under a per-recipient key) rather than the raw identifier. The mapping back to the raw identifier lives in the alias map and is loaded only in environments holding the appropriate Data Use Agreements.

**Federation pattern**: Two cohorts can share data linked at the individual level without a shared identifier namespace. PPMI and GP2 each maintain their own `IndividualID` values; their `IndividualAliases` entries point at each other (along with linkage method and confidence). Privacy-preserving record linkage (PPRL) workflows can populate this with high-confidence cryptographic matches without ever exposing the raw identifiers.

**GA4GH external linkage pattern**: `IndividualExternalDatasets` extends the alias mechanism by adding actionable repository pointers. Each entry describes one repository (PPMI, GP2, AMP-PD, AllOfUs Workbench, UK Biobank RAP, etc.) and the GA4GH services that repository exposes for this individual: DRS endpoints for file retrieval, Beacon v2 endpoints for variant discovery, Data Connect endpoints for federated SQL-like query, Phenopackets endpoints for structured phenotype, TES/WES endpoints for compute task submission. Repositories that aren't GA4GH-compliant get a `non-GA4GH` service-type entry with a plain endpoint URL. Together with `IndividualAliases` and Tier 8's `DataAssetURI`, this closes the federation loop — a downstream consumer holding one IndividualID can mechanically traverse from there to every file in every repository where the individual's data exists, without reading tribal documentation or emailing PIs.

GA4GH alignment references:
- Service Info: https://ga4gh-discovery.github.io/ga4gh-service-info/
- DRS: https://www.ga4gh.org/product/data-repository-service-drs/
- Beacon v2: https://docs.genomebeacons.org/
- Data Connect: https://github.com/ga4gh-discovery/data-connect
- Phenopackets: https://phenopacket-schema.readthedocs.io/
- Passports: https://www.ga4gh.org/product/ga4gh-passports/

## Theme 2: Time

**File**: `data/anchors/01_time.json`

Time is the single hardest field to harmonize across cohorts. Calendar dates leak PHI. Visit numbers don't align across studies. Years-from-enrollment requires a baseline. The Tier 1 solution is to require all three canonical representations (or one, with a baseline anchor that makes the others derivable).

| Anchor | Type | Description |
|--------|------|-------------|
| `VisitBaselineDate` | date | The enrollment / baseline visit date, the anchor that makes other representations convertible |
| `VisitDate` | date | Calendar date of the visit |
| `VisitNumber` | numeric | Sequential index, 0 = baseline |
| `YearsFromEnrollment` | numeric | Float years, supports fractions |
| `AgeAtVisit` | numeric | Censored to 90+ when HIPAA Safe Harbor applies |
| `YearsSinceDiagnosis` | numeric | Negative values permitted for prodromal cohorts |
| `YearsSinceSymptomOnset` | numeric | Distinct from diagnosis date |

**Transformation rules**: if any one of {`VisitDate`, `VisitNumber`, `YearsFromEnrollment`} is present along with `VisitBaselineDate`, Forge derives the others. Failure to derive is a hard error.

## Theme 3: Sex

**File**: `data/anchors/02_sex.json`

Three concepts kept distinct. Conflation breaks genetic analyses; this is the place to be strict.

| Anchor | Type | Description |
|--------|------|-------------|
| `SexChromosomal` | enum | XX, XY, XO, XXY, XYY, XXX, other_aneuploidy, unknown — what the genetics actually shows |
| `SexAtBirth` | enum | Male, Female, Intersex, Unknown — what was recorded clinically |
| `GenderIdentity` | enum | Self-reported gender, optional |

For genetic analyses (X-linked, mitochondrial, dosage), `SexChromosomal` is what matters. Most clinical forms only capture `SexAtBirth`. They are correlated but not identical, and treating them as one is how XXY participants get filtered out of X-chromosome PRS by accident.

## Theme 4: Ancestry & Pedigree

**File**: `data/anchors/04_ancestry_pedigree.json`

Theme 4 covers two related but distinct concerns that share natural co-location: how individuals identify and are genetically classified at the population level, and how individuals relate to each other within families. **Phenotypes are deliberately excluded** — they live in Theme 8 (Clinical Instruments) and Theme 12 (Clinical Concepts). Theme 4 is structural metadata about populations and pedigrees; what diseases or traits any individual has is captured in the clinical themes.

### Self-reported demographics (OMB-aligned)

| Anchor | Type | Description |
|--------|------|-------------|
| `RaceSelfReported` | enum (multi-select) | OMB Directive 15 categories |
| `EthnicitySelfReported` | enum | OMB binary (Hispanic/Latino vs. not) |
| `AncestrySelfReported` | string | Free-text or ISO-3166-coded self-described ancestry — distinct from race/ethnicity |

### Genetic ancestry

| Anchor | Type | Description |
|--------|------|-------------|
| `AncestryGeneticSuperpop` | enum | 1KG: AFR, AMR, EAS, EUR, SAS, OCE, ADMIXED, Unknown |
| `AncestryGeneticSubpop` | enum | GP2 11-class: AAC, AFR, AJ, AMR, CAH, CAS, EAS, EUR, FIN, MDE, SAS, +ADMIXED, Unknown |
| `AncestryGeneticMethod` | enum | PCA-projection, ADMIXTURE, RFMix, GLOBETrotter, IBD-segment, Other |
| `AncestryGeneticReferencePanel` | enum | 1KG-phase3, TOPMed-Bravo, HGDP, gnomAD-v3, GP2-internal, Other |

### Pedigree structure

| Anchor | Type | Description |
|--------|------|-------------|
| `FamilyID` | string | Pedigree identifier; PLINK FAM column 1 maps directly here |
| `PaternalIndividualID` | string | FK to IndividualID; null when father not enrolled or unknown |
| `MaternalIndividualID` | string | FK to IndividualID; null when mother not enrolled or unknown |
| `PaternalKnown` | enum | in-cohort / out-of-cohort / unknown / adopted / donor-conceived |
| `MaternalKnown` | enum | Same semantics as PaternalKnown |
| `FounderStatus` | enum | founder / non-founder / unknown |
| `MonozygoticTwinGroup` | string | MZ twin/multiple grouping (100% IBD-identical) |
| `DizygoticTwinGroup` | string | DZ twin/multiple grouping (~50% IBD, shared gestation) |
| `RelationshipToProband` | enum | proband / mother / father / sister / brother / [grand-/]aunt-uncle / cousin / etc. |
| `PedigreeFileURI` | string | Pointer to canonical PLINK FAM, GEDCOM, PED, or CSV pedigree file |
| `ConsanguinityFlag` | enum | consanguineous / non-consanguineous / unknown |

**Required-when rules**: any populated `AncestryGenetic*` field requires `AncestryGeneticMethod` and `AncestryGeneticReferencePanel` (without method and panel, an "EUR" label is meaningless). When `has_pedigree=true`, `FamilyID`, `PaternalIndividualID`, and `MaternalIndividualID` are required. `MonozygoticTwinGroup` is required when `has_mz_twins=true`.

**Why ancestry and pedigree are co-located**: both describe how individuals relate to populations and to each other — ancestry at the population scale, pedigree at the family scale. Genetic-ancestry inference and pedigree-aware analyses share covariates (PCs derived from genotype matrices used for both ancestry and IBD), share validation challenges (consanguineous unions affect both ancestry estimation and IBD inference), and share the same source-vocabulary constraints (1KG, gnomAD, GP2 reference panels). A cohort declaring genetic ancestry typically also has the `FamilyID` infrastructure to declare pedigree; co-locating means one validation pass rather than two.

**Why phenotypes are NOT in Theme 4**: an earlier draft included a `PedigreePhenotypes` JSON array in the pedigree theme, capturing affected/unaffected/prodromal/at-risk-asymptomatic status. That was removed because phenotypes belong in the clinical themes — Theme 8 captures structured clinical instrument scores (cognitive, motor, neuropsychiatric); Theme 12 captures diagnoses and clinical findings via OMOP concept_id. The proband-relationship anchor `RelationshipToProband` is retained because it's structural metadata (who is the index case for ascertainment purposes) rather than phenotype data.

## Theme 5: Biosample

**Files**: `data/anchors/04_biosample.json`, `data/anchors/05_anatomy_celltype.json`

The biosample tier is structurally rich because biosample identity, lineage, and provenance are where most cross-cohort harmonization quietly fails.

### Identity and lineage

| Anchor | Type | Description |
|--------|------|-------------|
| `IsBiosample` | binary | Trigger flag for biosample-required validation |
| `BiosampleID` | string | Globally unique within cohort |
| `ParentBiosampleID` | string | Null for top-level draws, set for aliquots |
| `ExternalBiosampleIDs` | JSON array | Cross-system tracking pairs `[{authority, identifier}]` |

### Type and material

| Anchor | Type | Description |
|--------|------|-------------|
| `TissueSampleType` | string | Free-text ground truth ("frontal cortex BA9 contralateral frozen") |
| `SampleTypeControlled` | enum | Controlled-vocab derivation (Blood-PBMC, CSF, Brain-Tissue-Frozen, ...) |
| `BiosampleSubjectID` | string | FK to participant |
| `BiosampleVisitID` | string | FK to visit (composite SubjectID + VisitNumber) |
| `CollectionDate` | date | Calendar date of draw |
| `ProcessingProtocol` | string | DOI or named SOP version |
| `StorageTemperature` | enum | -80C, -20C, LN2, 4C, RT, Other, Unknown |
| `AliquotVolumeUL` | numeric | Microliters; null for solid tissue |

### Anatomy and cell type

| Anchor | Type | Description |
|--------|------|-------------|
| `AnatomicalRegion` | string | Free-text ground truth |
| `AnatomicalRegionVocabulary` | enum | UBERON (default), AllenBrainAtlas, NCIT, FMA, Other, NotApplicable |
| `AnatomicalRegionCode` | string | Code in chosen vocabulary (e.g., `UBERON:0002038`) |
| `Hemisphere` | enum | Left, Right, Bilateral, Midline, NotApplicable, Unknown |
| `CellType` | string | Free-text for cell isolates ("dopaminergic neuron, A9 group") |
| `CellTypeVocabulary` | enum | CL (default), BICCN-CCN, PCL, Other, NotApplicable |
| `CellTypeCode` | string | Code in chosen vocabulary (e.g., `CL:0000540`) |
| `SpeciesOfOrigin` | string | NCBITaxon identifier (`NCBITaxon:9606` for human) |

**Required-when** rules: `IsBiosample=true` triggers required `BiosampleID`, `TissueSampleType`, `BiosampleSubjectID`, `CollectionDate`. Tissue biosamples additionally require `AnatomicalRegion`. Cell-isolate biosamples additionally require `CellType`. Non-human samples require `SpeciesOfOrigin`.

## Theme 6: Omics Platform

**File**: `data/anchors/06_omics.json`

Tier 5 follows LOINC's six-axis clinical assay structure (Component, Property, Time, System, Scale, Method) directly, with documented extensions where omics granularity exceeds LOINC's coverage.

### LOINC six-axis core

| Anchor | LOINC Axis | Description |
|--------|-----------|-------------|
| `AssayAnalyteComponent` | 1: Component | What's measured |
| `AssayProperty` | 2: Property | Kind of quantity (LOINC native + omics extensions) |
| `AssayTime` | 3: Time | Time aspect (Pt for most omics) |
| `AssaySystem` | 4: System | Specimen — bridges to Tier 4 biosample anchors |
| `AssayScale` | 5: Scale | Qn, Ord, Nom, Nar, Ql, Doc |
| `AssayMethod` | 6: Method | Assay technology category |
| `AssayLOINCCode` | — | Direct LOINC code when six-axis tuple resolves |

### Property axis: LOINC-native vs. RoP-extended values

LOINC native: `MCnc, NCnc, SCnc, ACnc, CCnc, NFr, MFr, SFr, Type, Find, Imp, PrThr`

RoP extended (documented for transparency, intended for upstream LOINC submission):
`Counts, TPM, FPKM, LogFC, VAF, Beta, MValue, NAbund, Ratio`

### Method axis: Platform sub-block (extends LOINC Axis 6)

LOINC's method granularity stops at categories like `Sequencing.NGS`. The Platform sub-block captures the vendor / model / kit / batch detail required for batch-effect correction and reproducibility.

| Anchor | Description |
|--------|-------------|
| `PlatformVendor` | Illumina, 10X-Genomics, Oxford-Nanopore, PacBio, Thermo-Fisher, Affymetrix, Bruker, Agilent, BD, Standard-BioTools, Element-Biosciences, Ultima-Genomics, Singular-Genomics, Other |
| `PlatformModel` | Free text + recommended values (NovaSeq-6000, Chromium-X, PromethION-24, ...) |
| `KitChemistry` | Free text ("TruSeq Stranded mRNA", "Single Cell 3' v3.1") |
| `KitVersion` | Version string |
| `BatchID` | Cohort-scoped batch identifier |
| `ReferenceAssembly` | GRCh38, GRCh37, T2T-CHM13, hg38, hg19, mm10, mm39, GRCm39, Other, NotApplicable |
| `PipelineSoftware` | Free text ("DRAGEN", "GATK4-HaplotypeCaller", "CellRanger") |
| `PipelineSoftwareVersion` | Version string |
| `PipelineSourceRepository` | Git URL or container registry URL — secondary to PipelineSoftware, names where the code lives |
| `PipelineSourceCommit` | Commit SHA or container image digest pinning the exact code state |
| `PipelineSourceReference` | Branch, tag, or release identifier for human-readable context |
| `PipelineContainerImage` | Container image:tag identifying the runtime environment |
| `PipelineConfigReference` | Pointer to the parameter set used for this run (DOI, URL, hash, or repo path) |

## Theme 7: Imaging Acquisition Metadata

**File**: `data/anchors/07_imaging_acquisition.json`

Theme 7 captures DICOM/BIDS-aligned acquisition metadata for neuroimaging modalities — MRI, fMRI, dMRI, MRS, PET, SPECT, CT, ultrasound, OCT, fundus photography, and the EEG/MEG/ECG modalities that share acquisition-time provenance concerns. The theme covers what was acquired, on what hardware, with what parameters, and to what quality — but not the post-acquisition processing (which lives in Theme 11 Summary Stats when results are derived) or the binary file references (which live in Theme 10 Data Assets).

The design follows DICOM tag conventions where they exist (e.g., `(0008,0060)` Modality, `(0018,0087)` MagneticFieldStrength, `(0020,000E)` SeriesInstanceUID) and BIDS structure for organizational metadata, with extensions for modality-specific concerns (PET tracer chemistry, MRI sequence taxonomy) that DICOM under-specifies.

### Modality and hardware

| Anchor | Type | Description |
|--------|------|-------------|
| `ImagingModality` | enum | MRI / fMRI / dMRI / MRS / PET / SPECT / CT / X-ray / ultrasound / OCT / fundus-photography / EEG / MEG / ECG / other |
| `ImagingScannerManufacturer` | string | DICOM `(0008,0070)` — Siemens, GE, Philips, Canon, etc. |
| `ImagingScannerModel` | string | DICOM `(0008,1090)` — MAGNETOM Prisma, SIGNA Premier, Ingenia Elition, etc. |
| `ImagingScannerSoftwareVersion` | string | DICOM `(0018,1020)` — software versions can change reconstruction subtly |
| `ImagingFieldStrength` | numeric | DICOM `(0018,0087)` Tesla — required when modality is MRI/fMRI/dMRI/MRS |

### Acquisition parameters

| Anchor | Type | Description |
|--------|------|-------------|
| `ImagingSequenceType` | string | T1w-MPRAGE, T2w-FLAIR, DTI-64dir, rs-fMRI, ASL-pCASL, PET-static-30min, etc. |
| `ImagingAcquisitionParameters` | JSON object | Modality-specific parameter block (TR, TE, voxel_size for MRI; scan_duration, frame_count for PET; tube_voltage, current for CT) |
| `ImagingContrastAgent` | JSON object | Gadolinium agent / iodinated CT agent: name, dose, route, timing — null for native-contrast |

### PET-specific

| Anchor | Type | Description |
|--------|------|-------------|
| `ImagingPETTracer` | JSON object | Required for PET — tracer name, target, isotope, batch — distinguishes amyloid (florbetaben/florbetapir/flutemetamol/PiB) from tau (flortaucipir/MK-6240/PI-2620) from FDG/FDOPA/DaTscan |
| `ImagingPETInjectedDoseMBq` | numeric | DICOM `(0018,1074)` — required for SUV computation |

### Provenance and conformance

| Anchor | Type | Description |
|--------|------|-------------|
| `ImagingDICOMSeriesUID` | string | DICOM `(0020,000E)` — globally unique series identifier for traceability |
| `ImagingBIDSConformance` | enum | BIDS-compliant / BIDS-partial / BIDS-derivatives / non-BIDS / unknown |
| `ImagingProtocolReference` | string | DOI/URL/protocol-ID of acquisition protocol document |
| `ImagingQCStatus` | JSON object | QC pipeline output: `{status, qc_pipeline (MRIQC/FMRIPREP/dMRIQC), qc_pipeline_version, qc_notes, manual_review}` |

**Why this is its own theme rather than Theme 6 omics extensions**: imaging acquisition metadata is structurally distinct from omics platform metadata. Omics uses LOINC's six-axis (Component/Property/Time/System/Scale/Method) which doesn't translate well to imaging — an MRI sequence is not a LOINC component, a PET tracer is not a LOINC analyte, and DICOM tags don't map onto LOINC's axes. Imaging has its own well-established standards (DICOM, BIDS) that the theme follows directly.

**Cross-cohort harmonization concerns**: scanner manufacturer/model produces systematic batch effects even at nominally identical sequences and field strength; multi-site studies typically include manufacturer as a covariate. Software version drift introduces subtle quantitative differences even on the same scanner. PET tracer choice fundamentally determines what pathology is being measured — combining amyloid-PET with tau-PET as if interchangeable is a category error. BIDS conformance gates whether community pipelines (fMRIPrep, QSIPrep, MRIQC) can be applied directly. All of these concerns are addressable when the metadata is captured at acquisition time and follows them through the analysis pipeline.



## Theme 8: Clinical Assessment Instruments

**File**: `data/anchors/08_clinical_instruments.json`

Theme 8 captures instrument-level metadata for clinical assessment instruments — cognitive batteries (MoCA, MMSE, ACE-III), motor exams (MDS-UPDRS, BBS, 9HPT, TUG), neuropsychiatric inventories (NPI, NPI-Q), mood scales (GDS, BDI, HAM-D), functional assessments (FAQ, Lawton IADL), quality-of-life instruments (PDQ-39, EQ-5D), and composite batteries. The module describes the instrument itself; individual item-level CDEs (e.g., a single MoCA delayed-recall item) live as ordinary RoP rows referencing their parent InstrumentID.

### Identity and version

| Anchor | Type | Description |
|--------|------|-------------|
| `InstrumentID` | string | Stable identifier (`RoP-Instrument:NNNNNNN`); never recycled |
| `InstrumentName` | string | Full name |
| `InstrumentAbbreviation` | string | Short identifier (MoCA, MMSE, MDS-UPDRS, etc.) |
| `InstrumentVersion` | string | Critical because revisions change scoring (MoCA-7.0 vs 8.1 are distinct InstrumentID records) |
| `InstrumentLanguage` | string | ISO 639-1 code with optional region (en, es-MX, ja, zh-CN) — different language versions are distinct records |

### Categorization

| Anchor | Type | Description |
|--------|------|-------------|
| `InstrumentDomain` | enum | global-cognition / domain-specific-cognition / motor / neuropsychiatric / mood / behavioral / functional-ADL / functional-IADL / quality-of-life / sleep / autonomic / olfactory / composite / other |
| `InstrumentLOINCCode` | string | LOINC panel code when one exists (MMSE = 72106-8, MoCA = 72172-0) |

### Licensing and reference

| Anchor | Type | Description |
|--------|------|-------------|
| `InstrumentLicense` | enum | open / open-with-attribution / registered-free-use / paid-license-required / restricted-distribution / proprietary / unknown |
| `InstrumentValidationReference` | string | DOI of primary validation publication |

### Scoring conventions

| Anchor | Type | Description |
|--------|------|-------------|
| `InstrumentTotalScoreRange` | JSON object | `{min, max, valid_increments}` — plausibility bounds for outlier detection (a MoCA of 38 is impossible) |
| `InstrumentScoreDirection` | enum | higher-is-better / higher-is-worse / both-extremes-are-worse / not-applicable — sign errors here are the most common cross-cohort meta-analysis failure mode |
| `InstrumentSubscaleStructure` | JSON array | Per-subscale: `{subscale_name, score_range, item_numbers, loinc_code}` |
| `InstrumentNormativeReference` | JSON object | Population reference for Z-score conversion: `{population_name, age_range, education_range, ancestry, language, source_doi, z_score_formula}` |

**Why this is its own module**: clinical assessment instruments are a distinct class of biomedical CDEs with their own provenance, versioning, scoring conventions, and licensing landscape. They span what NACC, NINDS-CDE, PhenX, and most cohort-specific boutique CDE collections actually contain — by some estimates >40% of typical cohort CDE counts are clinical instrument items. Modeling instrument-level metadata as a dedicated module lets Forge enforce instrument version pinning, score-direction sign correction, and cross-language harmonization at ingest time, none of which is possible when instrument metadata is scattered across per-row `metadata_` blobs.

**Operational pattern**: a NACC participant who completed MoCA-8.1 in English gets one set of item-level CDE rows referencing `InstrumentID=RoP-Instrument:MoCA-8.1-en`. The total score CDE references the same InstrumentID, with the participant's value bounded by `InstrumentTotalScoreRange` and sign-aware via `InstrumentScoreDirection`. A meta-analyst combining MoCA scores across PPMI, ADNI, and NACC checks that all three resolve to the same InstrumentID before pooling; if not, they apply documented cross-version conversion rules or stratify.

## Theme 9: Governance & Consent

**File**: `data/anchors/07_governance.json`

Governance is the difference between a research artifact and a deployable contract. The Tier 7 design captures consent class, jurisdictional regulation, sharing/compute/recontact controls, and accountability contacts in a single coherent block. It is structured around GA4GH's Data Use Ontology (DUO) for consent class, with explicit fields for the practical operational questions that DUO does not directly model: what cloud is permitted, can the participant be re-contacted, can the PI be re-contacted, can the data be re-shared.

### Consent class (DUO-aligned)

| Anchor | Type | Description |
|--------|------|-------------|
| `ConsentDUOPrimary` | enum | Primary DUO class: GRU, HMB, DS, POA, GSO, NPU, NRES, Mixed, Unknown |
| `ConsentDUOCode` | string | Full DUO URI (`DUO:NNNNNNN`) |
| `ConsentDUORestrictions` | string (JSON array) | Modifier codes (NCU, MOR, GS, TS, IRB, COL, PUB, US, IS, PS) with structured parameters |
| `ConsentDUODiseaseSpecific` | string | When primary class is `DS`, the disease scope (Mondo/HPO preferred) |
| `ConsentVersion` | string | Identifier of the consent form version the participant signed |
| `ConsentDateGiven` | date | Date of most recent applicable consent |

### Re-consent and re-contact

| Anchor | Type | Description |
|--------|------|-------------|
| `ReconsentPermitted` | binary | May re-consent be sought? |
| `ReconsentRequired` | binary | Is re-consent required for new uses beyond original scope? |
| `ReconsentDate` | date | Date of most recent re-consent event, if any |
| `ParticipantRecontactPermitted` | binary | May the participant be re-contacted at all? |
| `ParticipantRecontactPurposes` | string | Permitted purposes (return-of-results, follow-up-survey, etc.) |
| `PIRecontactPermitted` | binary | May the originating PI be re-contacted? |

### Sharing, compute, and disclosure controls

These three axes are functionally distinct and must be recorded separately. A repository may permit cloud compute within its enclave, prohibit download, and prohibit reshare — that is exactly the All of Us / UK Biobank RAP / NIAGADS DSS pattern.

| Anchor | Type | Description |
|--------|------|-------------|
| `ResharePermitted` | enum | Onward redistribution: permitted / permitted-with-DAC-approval / prohibited / unknown |
| `DownloadOutsideEnclavePermitted` | enum | Export from enclave: permitted / permitted-with-DAC-approval / summary-statistics-only / model-weights-only / prohibited / unknown |
| `EnclaveEnvironment` | string | Named enclave when download is restricted (AllOfUs Workbench, UKB RAP, NIH STRIDES, DNAnexus, Terra, NIAGADS DSS, AnVIL, BioData Catalyst) |
| `CloudComputePermitted` | enum | Compute environment class: any-cloud / government-cloud-only / specific-cloud-only / on-premises-only / unknown |
| `CloudComputeRestrictions` | string | Specific approved cloud environments when gated |
| `JurisdictionalRegulation` | enum | HIPAA, GDPR, UK-GDPR, PIPEDA, LGPD, PIPL, APP, POPIA, Multiple, None, Unknown |
| `DataResidencyRequirement` | enum | Geographic restrictions on storage/processing location |
| `MinimumSummaryCellSize` | numeric | k-anonymity threshold; minimum cell size below which summary statistics must be suppressed (typical: 5, 10, 11, 20) |
| `SmallCellSuppressionRule` | string | Description of the suppression rule including complementary suppression requirements |

### Accountability and contacts

| Anchor | Type | Description |
|--------|------|-------------|
| `IRBProtocolNumber` | string | IRB/REC protocol approval number |
| `DataAccessCommittee` | string (JSON object) | DAC name, identifier, contact, governance URL |
| `DUAReference` | string | DOI, hash, or repository ID of the governing DUA |
| `RegistrationOfRecord` | string | clinicaltrials.gov NCT, EudraCT, ISRCTN, or institutional registry |
| `ContactPI` | string (JSON object) | PI: name, ORCID, email, institution, ROR |
| `ContactDataSteward` | string (JSON object) | Data steward: name, email, role, institution |

**Required-when** rules: `ConsentDUODiseaseSpecific` is required when `ConsentDUOPrimary=DS`. `CloudComputeRestrictions` is required when `CloudComputePermitted=specific-cloud-only`. `DataResidencyRequirement` is required when `JurisdictionalRegulation=GDPR` (or includes GDPR among multiple regulations). `DataAccessCommittee` is required when `ResharePermitted=permitted-with-DAC-approval`. `ReconsentDate` is recommended when `ReconsentRequired=true` and re-consent has been performed.

**Why this is its own tier rather than free metadata**: governance is what gates re-share, controls cloud deployment, defines re-contact pathways, and provides accountability when something goes wrong. It is the operational layer that turns RoP from "data we agree on" into "data we can responsibly move." Implementing it as a strictly-typed anchor tier means Forge can validate it at ingest the same way it validates time or biosample lineage — refusing to admit data without complete governance metadata, the same way it refuses data without a baseline visit date.

## Theme 10: Data Asset References

**File**: `data/anchors/08_data_assets.json`

Tier 8 closes the gap between RoP's CDE metadata and the actual binary data files those CDEs describe. Without it, Tier 5's omics platform metadata records *how* data was generated but not *where it lives*; the same is true for imaging assets, mass-spec output, derived counts matrices, and clinical document attachments. The Tier 8 design aligns with GA4GH's Data Repository Service (DRS) URI scheme as the preferred reference format and adds structured companion fields for the operational properties every downstream pipeline needs.

### Asset identity and type

| Anchor | Type | Description |
|--------|------|-------------|
| `DataAssetURI` | string | Canonical reference; DRS URI preferred (`drs://hostname/object_id`); S3/GCS/Azure/HTTPS accepted as fallback |
| `DataAssetType` | enum | VCF, gVCF, BCF, BAM, CRAM, SAM, FASTQ, counts-matrix, expression-matrix, methylation-matrix, proteomics-matrix, h5ad, loom, MatrixMarket, Parquet, HDF5, Zarr, DICOM, NIfTI, TIFF, mzML, MGF, imzML, GFF, GTF, BED, PDF, TSV, CSV, JSON, other |
| `DataAssetFormat` | string | Specific format version (VCFv4.2, BAMv1.6, AnnData-0.10, DICOM-3.0, etc.) |
| `DataAssetSampleScope` | enum | per-individual / per-biosample / per-cohort / per-batch / per-tissue-block / aggregate-derived / other |

### Access and integrity

| Anchor | Type | Description |
|--------|------|-------------|
| `DataAssetAccessProtocol` | enum | DRS, htsget, S3, GCS, Azure-blob, HTTPS, HTTP, SFTP, FTP, local-filesystem, other |
| `DataAssetIndexURI` | string | Companion index URI (TBI, CSI, BAI, CRAI, etc.); required for indexable types |
| `DataAssetChecksum` | string | Cryptographic hash for integrity verification |
| `DataAssetChecksumAlgorithm` | enum | SHA-256, SHA-1, SHA-512, MD5, etag, crc32c, other |
| `DataAssetSizeBytes` | numeric | Asset size for storage planning |

### GA4GH authorization

| Anchor | Type | Description |
|--------|------|-------------|
| `DataAssetGA4GHPassportRequired` | binary | Whether the asset requires a GA4GH Passport visa for access |
| `DataAssetGA4GHVisaTypes` | string | Required visa scopes when passport is required |

### Provenance and licensing

| Anchor | Type | Description |
|--------|------|-------------|
| `DataAssetReferenceAssembly` | enum | Reference build for genomic asset types (GRCh38, GRCh37, T2T-CHM13, hg38, hg19, mm10, mm39, GRCm39, Other, NotApplicable) |
| `DataAssetGeneratedAt` | date | Timestamp when the pipeline produced the asset |
| `DataAssetReadmeURI` | string | Link to asset-specific documentation |
| `DataAssetLicense` | string | Per-asset license when distinct from cohort default (SPDX preferred) |

**Required-when** rules: when a cohort declares any data assets (`has_data_assets=true`), `DataAssetURI`, `DataAssetType`, `DataAssetSampleScope`, `DataAssetAccessProtocol`, `DataAssetFormat`, and `DataAssetGA4GHPassportRequired` are required. `DataAssetIndexURI` is required for indexable asset types (VCF, BAM, CRAM, etc.). `DataAssetReferenceAssembly` is required for genomic asset types. `DataAssetChecksumAlgorithm` is required when `DataAssetChecksum` is present. `DataAssetGA4GHVisaTypes` is required when `DataAssetGA4GHPassportRequired=true`.

**Why this is its own tier rather than per-row metadata in Tier 5**: data assets aren't omics-specific. The same structure applies to imaging (DICOM/NIfTI), mass-spec (mzML/MGF), derived statistics (Parquet/HDF5 summary tables), and clinical document attachments (PDF). Pulling asset references into a dedicated tier keeps Tier 5 focused on assay platform metadata and lets imaging-only or proteomics-only cohorts use Tier 8 without inheriting omics anchors that don't apply to them.

**Multi-asset biosamples**: a single biosample typically has multiple data assets — raw FASTQ, aligned BAM, called VCF, derived counts matrix. Each is a separate row in the cohort's element manifest, all linked back to the biosample via shared identifier. Same relational pattern as multiple omics observations attached to one biosample.

## Theme 11: Summary Statistics & Component Loadings

**File**: `data/anchors/09_summary_stats.json`

Tier 9 is structurally different from the other tiers. Most tiers describe individuals or biosamples; Tier 9 describes *result datasets* — GWAS summary stats, gene/protein effect-size tables, QTL maps, polygenic scores, and the PCA/UMAP loadings that get reused as covariates across analyses. The right abstraction is to model the **dataset** as the RoP entity (with provenance, scope, method, software) and reference the actual per-result rows (millions of variants, thousands of genes) via Tier 8 data assets. This avoids trying to put 8M GWAS variant rows into the anchor floor — wrong abstraction — while still capturing everything a downstream consumer needs to know about the result dataset to use it correctly.

### Summary statistics dataset metadata

| Anchor | Type | Description |
|--------|------|-------------|
| `SummaryStatsType` | enum | GWAS-SNP / GWAS-INDEL / GWAS-SV / GWAS-CNV / gene-burden / gene-expression-association / protein-association / methylation-association / metabolite-association / TWAS / PWAS / MWAS / colocalization / Mendelian-randomization / polygenic-score / sQTL / eQTL / pQTL / mQTL / other |
| `SummaryStatsTrait` | string | Free-text trait name (e.g., "Parkinson disease", "CSF total tau levels") |
| `SummaryStatsTraitCode` | string | Controlled vocabulary code for the trait (EFO, Mondo, HPO, MeSH) |
| `SummaryStatsScope` | enum | primary-single-cohort / meta-analysis-fixed-effects / meta-analysis-random-effects / meta-analysis-MetaSoft / conditional-analysis / sex-stratified / ancestry-stratified / trans-ancestry / case-only / family-based / other |
| `SummaryStatsContributingCohorts` | string (JSON array) | When meta-analysis: per-cohort `{cohort_name, cohort_id, sample_size, case_count, control_count, ancestry}` entries — required to avoid double-counting in downstream meta-analysis |
| `SummaryStatsTotalN` | numeric | Effective sample size; sum across contributors for meta-analyses |
| `SummaryStatsCaseN` | numeric | Cases (case-control studies); null for quantitative traits |
| `SummaryStatsControlN` | numeric | Controls (case-control studies) |

### Method and software

| Anchor | Type | Description |
|--------|------|-------------|
| `SummaryStatsModel` | string | Statistical model: logistic regression / linear regression / Cox PH / mixed-effects (BOLT-LMM, SAIGE, REGENIE) / firth-corrected logistic / SKAT / BURDEN / ACAT-V / ACAT-O / STAAR |
| `SummaryStatsCovariates` | string (JSON array) | Covariates included; pipe-delimited or structured list including PCA components when used |
| `SummaryStatsSoftwareReference` | string | Software + version: PLINK-2.0.0 / BOLT-LMM-2.4.1 / SAIGE-1.3.0 / REGENIE-3.4 / GENESIS-2.30.0 / METAL-2020-05-05 / METASOFT-2.0.1 |

### Genomic context

| Anchor | Type | Description |
|--------|------|-------------|
| `SummaryStatsGenomicReference` | enum | GRCh38 / GRCh37 / T2T-CHM13 / hg38 / hg19 / NotApplicable — required when variant-level |
| `SummaryStatsImputationPanel` | string | TOPMed-r3 / HRC-r1.1 / 1000G-Phase3 / gnomAD-v3 / GP2-internal |
| `SummaryStatsAncestry` | string | Single ancestry label or per-ancestry JSON array for trans-ancestry meta-analyses |

### Results file and access

| Anchor | Type | Description |
|--------|------|-------------|
| `SummaryStatsResultsURI` | string | URI of the results file (per-variant / per-gene / per-component result table); DRS-preferred per Tier 8 rules |
| `SummaryStatsHarmonizedFormat` | binary | true / false / partial — whether results conform to GWAS Catalog harmonized format |
| `SummaryStatsAccessLevel` | enum | open / registered-access / controlled-access / embargoed / inherits-cohort-DUA |

### Diagnostics

| Anchor | Type | Description |
|--------|------|-------------|
| `SummaryStatsLambdaGC` | numeric | Genomic inflation factor; values >1.10 indicate residual stratification |
| `SummaryStatsLDSCIntercept` | string (JSON) | LDSC intercept, h2-SNP estimate, ratio — standardized variant-level diagnostics |

### Component loadings (PCA, UMAP, NMF)

Component loadings get their own anchor sub-block within Tier 9 because they are typically used as *covariates* in summary-stats-generating analyses rather than as primary results, and consumers need to retrieve specific components (PC1-10, UMAP-1/2) by name. Critical to distinguish per-individual loadings (suitable as covariates) from per-feature loadings (suitable for back-projection of variants/genes onto components).

| Anchor | Type | Description |
|--------|------|-------------|
| `ComponentLoadingsType` | enum | genotype-PCA / expression-PCA / methylation-PCA / proteomics-PCA / expression-UMAP / expression-tSNE / spatial-UMAP / NMF / ICA / factor-model / other |
| `ComponentLoadingsURI` | string | URI of the loadings file; format depends on use (per-individual covariate file vs. per-feature back-projection file) |
| `ComponentLoadingsScope` | enum | per-individual / per-feature / both |
| `ComponentLoadingsNComponents` | numeric | Number of components; typically 10-20 for PCA covariates, 2-3 for UMAP/t-SNE visualization |
| `ComponentLoadingsInputFeatures` | string | Description of the input feature set the dim-reduction was computed over (e.g., "GP2 release 7 imputed genotypes, MAF>0.01, LD-pruned r2<0.1") |
| `ComponentLoadingsSoftware` | string | PLINK-2.0.0 --pca / flashpca-2.1 / scikit-learn-1.4 PCA / umap-learn-0.5.6 / scanpy-1.10 / GENESIS-2.30 PC-AiR |
| `ComponentLoadingsVarianceExplained` | string (JSON array) | Per-component variance explained; the standard "scree plot" values for PCA |
| `ComponentLoadingsDerivedFrom` | string | When loadings are projected from an external reference (canonical case: PCA-projection ancestry inference using 1KG, gnomAD, or GP2-internal as the source), the source dataset identifier |

**Required-when** rules: when `has_summary_stats=true`, the dataset metadata block is required (Type, Trait, Scope, TotalN, Model, Covariates, Software, Ancestry, ResultsURI, AccessLevel). Variant-level summary stats add GenomicReference as required and HarmonizedFormat / LambdaGC / LDSCIntercept as recommended. Meta-analyses add ContributingCohorts as required. Case-control add CaseN / ControlN as required. Component loadings have an analogous required block when `has_component_loadings=true`. Projected loadings additionally require `ComponentLoadingsDerivedFrom`.

**Why this is its own tier rather than Tier 5 omics extensions**: summary statistics and component loadings describe analytical results, not raw measurements. The same structure applies to non-omics analyses (GWAS of CSF biomarkers, polygenic scores, MR studies) and to derived datasets that have no associated biosample. Pulling these into a dedicated tier keeps Tier 5 focused on assay platform metadata and lets meta-analytic and derivative-data scenarios flow cleanly through the contract.

**Operational pattern for covariates**: a typical GWAS analysis cites Tier 9 PCA loadings (`ComponentLoadingsType=genotype-PCA`, scope `per-individual`) in its `SummaryStatsCovariates` field. The loadings dataset is published once with its provenance fully specified, then referenced by every analysis that uses it as a covariate. Downstream meta-analysts can verify that contributing studies used compatible PCA conventions before combining results — without this, "PC1-10 included as covariates" is an unverifiable claim.

## Theme 12: Clinical Concepts

**File**: `data/anchors/12_clinical_concepts.json`

Theme 12 is the massive general clinical terminology theme: diagnoses (ICD-10/11, SNOMED-via-OMOP), drugs (RxNorm), procedures (CPT, HCPCS, ICD-10-PCS, SNOMED-Procedure), lab tests (LOINC), vital signs (LOINC), observations, devices (SNOMED-Device, GMDN), specimens, and adverse events (MedDRA). Where the other themes are specialized — Theme 7 for omics platform metadata, Theme 8 for clinical assessment instrument metadata — Theme 12 is the broad bread-and-butter clinical content that the OMOP Common Data Model harmonizes. It uses **OMOP CDM concept structure as the controlling backbone**: every Theme 12 concept gets an OMOP `concept_id` as its canonical identifier, with the source vocabulary code and version preserved alongside.

This is the theme where **ICD, OMOP/Athena, RxNorm, MedDRA, SNOMED-via-OMOP, and LOINC's clinical-lab/vital-sign content all converge**. Other authorities contribute: HPO clinical findings sit alongside SNOMED clinical findings via cross-vocabulary mappings; Mondo disease concepts cross-walk to ICD-10 and SNOMED; NACC and PhenX clinical observations resolve to OMOP concept_ids where possible.

### Concept identity

| Anchor | Type | Description |
|--------|------|-------------|
| `ClinicalConceptDomain` | enum | OMOP domain: Condition / Drug / Procedure / Measurement / Observation / Device / Specimen / Visit / Death / Note / Episode / Provider / Cost / PayerPlan / Geography / Other |
| `ClinicalConceptStandardCode` | numeric | OMOP `concept_id` — the canonical pivot identifier |
| `ClinicalConceptStandardName` | string | OMOP `concept.concept_name` preferred form |
| `ClinicalConceptStandardVocabulary` | enum | The standard vocabulary OMOP designates as authoritative for this concept's domain (SNOMED for Condition, RxNorm for Drug, LOINC for Measurement, etc.) |

### Source provenance

| Anchor | Type | Description |
|--------|------|-------------|
| `ClinicalConceptSourceCode` | string | Source code as captured at the data origin (e.g., 'E11.9' for ICD-10-CM type 2 diabetes) |
| `ClinicalConceptSourceVocabulary` | string | Source vocabulary the source code came from |
| `ClinicalConceptSourceVersion` | string | Release version of the source vocabulary |

### Cross-vocabulary mapping

| Anchor | Type | Description |
|--------|------|-------------|
| `ClinicalConceptAlternativeCodes` | JSON array | Cross-vocabulary mappings: per-vocabulary `{vocabulary, code, version, mapping_type, mapping_quality}` entries from OMOP CONCEPT_RELATIONSHIP |
| `ClinicalConceptHierarchyAncestors` | JSON array | OMOP CONCEPT_ANCESTOR rollups for hierarchical query — querying for "Type 2 diabetes" should also surface descendants when appropriate |

### Validity and semantics

| Anchor | Type | Description |
|--------|------|-------------|
| `ClinicalConceptValidPeriod` | JSON object | OMOP-style `{valid_start_date, valid_end_date, invalid_reason}` |
| `ClinicalConceptSemanticTags` | JSON array | Source-vocabulary semantic tags (SNOMED's "disorder", "finding", "procedure", "body structure", etc.) |
| `ClinicalConceptValueSetMembership` | JSON array | Phenotype value sets this concept belongs to (PheKB, OHDSI Phoebe, NLM-VSAC, DataTecnica) |
| `ClinicalConceptUnitConcept` | numeric | For Measurement domain only: OMOP `concept_id` of the canonical unit (mg/dL, mmol/L) |

**Why this is its own theme rather than scattered metadata**: OMOP harmonizes ~8.7M clinical concepts under a single concept_id space. Without a dedicated theme using OMOP as the controlling backbone, every analysis tool re-implements cross-vocabulary mapping, hierarchy traversal, and unit normalization from scratch — and gets it slightly wrong each time. Theme 12 makes "what concept did this row mean?" a single OMOP concept_id lookup rather than a vocabulary-version-dependent string match.

**Operational pattern for cross-cohort harmonization**: Cohort A captures diabetes diagnoses as ICD-10-CM 'E11.9'; cohort B as ICD-9-CM '250.00'; cohort C as SNOMED 44054006. All three resolve to the same OMOP `concept_id` (201826 = "Type 2 diabetes mellitus") in `ClinicalConceptStandardCode`. Cross-cohort queries pivot on the standard code; the source codes remain visible for audit and source-fidelity analyses.



## Theme 13a: Resources

**File**: `data/anchors/13a_resources.json`

> **Definition.** A *resource* is a first-class entity in the biomedical research world that exists independently of any single dataset it produces. It has a stable identity, an institutional owner, a discoverable URL, and persists across time. Theme 13a catalogs resources and the relationships among them.

### What a resource is

The Resource theme answers one question: **"What is the entity that produced, hosts, or describes this data?"**

PPMI is a resource. ADNI is a resource. AMP-PD is a resource. GenoTools, the iNDI cell-line catalog, gnomAD, dbGaP, NIH NeuroBioBank, the CARD Catalog itself — all resources. They sit at the top of a hierarchy: resources *produce* data assets (Theme 10), *produce* summary statistics (Theme 11), are *governed by* governance records (Theme 9), are *referenced by* individuals via `IndividualExternalDatasets` (Theme 1), and *contribute to* curated CDE collections (Theme 13b).

A resource is the noun. The data, files, analyses, governance instruments, and curated CDE bundles are the verbs that resources produce or are subject to.

### What a resource is not

- **Not a CDE row.** Individual data points and measurements live in Themes 1–8 and 12 with appropriate `source_authority`/`source_code` provenance.
- **Not an analysis result.** Summary statistics, GWAS results, PCA loadings live in Theme 11.
- **Not a binary file.** VCF, BAM, h5ad, DICOM files live in Theme 10 with DRS-aligned URIs.
- **Not a CDE bundle.** Path-ND, GP2-CDE, CARD-Catalog-CDE, etc. are *collections* and live in Theme 13b. The distinction: Path-ND is a curated set of CDE definitions; PPMI is a study that captures data using (some of) those CDEs. Path-ND is a Collection; PPMI is a Resource.
- **Not a DUA or IRB protocol.** Governance instruments live in Theme 9 with explicit references back to the resources they govern.

### Resource types (`ResourceType` enum)

Controlled-value array — a single resource can have multiple types:

| Type | Examples |
|------|----------|
| Study / Cohort | PPMI, ADNI, NACC, GP2, DIAN, BioFIND, PDBP, ROS, MAP, ADSP-PHC, DIAN |
| Data Repository | AMP-PD, dbGaP, Synapse, NIAGADS DSS, AnVIL, BioData Catalyst, AllOfUs Workbench, UK Biobank RAP, LONI |
| Biorepository | NIH NeuroBioBank, NCRAD, Coriell, Alzheimer's Disease Center brain banks |
| Data Catalog | CARD Catalog, BioPortal, OBO Foundry, FAIRsharing, Zenodo |
| Code Repository | GenoTools, FAIRkit, The Forge, Dragon, nf-core pipelines, OHDSI tools |
| Knowledge Graph | Mondo, OpenTargets, neo4j-based PD knowledge graph |
| Reference Dataset | 1000 Genomes, gnomAD, GTEx, ENCODE, HCA, BICCN, T2T-CHM13 |
| Tool / Service | REDCap, LabKey, ClinVar, ClinGen, dbSNP, ClinicalTrials.gov |
| Publication Index | PubMed, PubMed Central |
| Other | catch-all for resources that don't fit cleanly |

### The 26 anchors, organized in 8 groups

| Group | Anchors | Purpose |
|-------|---------|---------|
| **Identity** (3) | ResourceID, ResourceName, ResourceAbbreviation | Stable identity; never-recycled accession |
| **Categorization** (5) | ResourceType, ResourceDescription, ResourceCoarseModality, ResourceGranularModality, ResourceDiseases | What this resource is and what it covers |
| **Scale** (1) | ResourceSampleSize | Structured `{total_n, cases_n, controls_n, biosamples_n, as_of_date}` — replaces CARD's free-text counts |
| **Access** (2) | ResourceAccessURL, ResourceAlternativeURLs | Where to find it (canonical + mirrors) |
| **FAIR** (3) | ResourceFAIRScore (0-9), ResourceFAIRIssues (tag array), ResourceFAIRNotes | FAIR adherence scoring per CARD methodology |
| **Curation** (3) | ResourceCurator (ORCID, role), ResourceDateAdded, ResourceDateLastUpdated | Who reviewed it, when |
| **Provenance** (2) | ResourceProvenanceSource, ResourceImportedFromCatalog | How this record entered RoP (manual / auto-discovered / promoted / imported) |
| **Relationships** (7) | ResourceLinkedDataAssets, ResourceLinkedSummaryStats, ResourcePublications, ResourceCodeRepositories, ResourceParentResources, ResourceLinkedGovernance, ResourceCellLineMetadata | Cross-references and resource-graph traversal |

### Concrete examples

**PPMI — Parkinson's Progression Markers Initiative**
```
ResourceID: RoP-Resource:0000042
ResourceType: ["Study", "Cohort"]
CoarseModality: ["clinical", "longitudinal", "imaging", "genetics", "biospecimen-only"]
Diseases: [{name: "Parkinson disease", code: "Mondo:0005180", vocabulary: "Mondo"}]
SampleSize: {total_n: 1700, cases_n: 1100, controls_n: 600, as_of_date: "2026-03-16"}
FAIRScore: 8
ParentResources: []
LinkedGovernance: [<Theme 9 governance row for PPMI DUA>]
LinkedDataAssets: [<Theme 10 DataAssetURI references>]
ProvenanceSource: "manual-curation"
```

**AMP-PD — Accelerating Medicines Partnership Parkinson Disease**
```
ResourceType: ["Data Repository"]
CoarseModality: ["clinical", "longitudinal", "genetics", "transcriptomics", "proteomics"]
ParentResources: [PPMI, BioFIND, PDBP, HBS, SURE-PD3, LBD]   # ← derived resource
SampleSize: {total_n: 10500, ...}
FAIRScore: 7
ProvenanceSource: "manual-curation"
```

**GenoTools** (DataTecnica's genetic analysis toolkit)
```
ResourceType: ["Code Repository", "Tool/Service"]
CoarseModality: ["computational-tool"]
AccessURL: "https://github.com/dvitale199/GenoTools"
FAIRScore: 9
ParentResources: []
ProvenanceSource: "manual-curation"
```

**iNDI — iPSC Neurodegenerative Disease Initiative**
```
ResourceType: ["Biorepository", "Reference Dataset"]
CoarseModality: ["genetics", "biospecimen-only"]
CellLineMetadata: {
  parental_line: "KOLF2.1J",
  genome_assembly: "GRCh38",
  distribution_route: "JAX Mice and Services",
  n_lines_total: 626,
  edit_types: ["SNV", "DEL", "REV", "HALO", "KI", "PTC", "INDEL"]
}
# Each of the 626 cell lines becomes an individual-level RoP row linked
# to this resource via shared identifier — not a separate resource record.
```

**CARD Catalog**
```
ResourceType: ["Data Catalog", "Publication Index"]
AccessURL: "https://card-catalog-v0.streamlit.app/"
FAIRScore: 8
ProvenanceSource: "manual-curation"
# When CARD Catalog rows are imported into RoP as Theme 13a Resources,
# each imported row carries ProvenanceSource="imported-from-external-catalog"
# and ResourceImportedFromCatalog={catalog_name: "CARD Catalog", original_record_id: ...}
```

### Why a separate (sub-)theme

Three reasons resources don't belong inline with other themes:

1. **Resources are referenced from many themes.** Individual external datasets (Theme 1), data assets (Theme 10), summary stats (Theme 11), and collections (Theme 13b) all FK back to `ResourceID`. A single resource record describes "what PPMI is" once; without it, that information scatters across thousands of individual-level rows or has to be reconstructed from string-matching cohort names.

2. **Resources can exist without individual-level data.** A code repository, a knowledge graph, a publication index, a public reference dataset (1000 Genomes, gnomAD) — all valuable to catalog even when there's no participant-level data attached to them in RoP. Modeling resources as first-class entities accommodates this.

3. **Resources have their own metadata vocabulary.** FAIR scoring, curator attribution, parent-derivation graphs, modality classification, sample-size structure — these are resource-level concerns that have no natural home in other themes.

### Relationship to Theme 13b (Collections)

Both 13a (Resources) and 13b (Collections) sit under **Theme 13 — Discoverability** because both answer "what data exists and how is it organized?" — but they describe categorically different things:

| | Resource (13a) | Collection (13b) |
|--|---|---|
| **What it is** | A thing in the world | A curated CDE bundle |
| **Examples** | PPMI, AMP-PD, iNDI, GenoTools, CARD Catalog | Path-ND, GP2-CDE, CARD-Catalog-CDE, ADSP-PHC-CDE |
| **Produced by** | Institutions, consortia, labs | Curators applying judgment about what CDEs matter for a project |
| **Contains** | Participants, biosamples, files, analyses | CDE definitions tagged with the collection abbreviation |
| **References** | `LinkedDataAssets`, `LinkedSummaryStats`, `Publications` | `LinkedResources`, `SourceAuthorities`, `ParentCollections` |

The two cross-reference each other. `Collection.LinkedResources` points at the resources a collection draws data from (Path-ND ← NACC + GP2 + PPMI + ADSP-PHC). `Resource.LinkedGovernance` points at the governance records that bind the resource. Together, the two sub-themes form the **Discoverability** layer that gates the **R** (Resource-Cataloged) and **C** (Collection-Tagged) attestations in the conformance table.



The design is informed by the CARD Catalog schema (DataTecnica's existing biomedical resource inventory) with several improvements: JSON arrays replace ambiguous comma/semicolon-delimited strings, structured sample-size objects replace free-text counts, JSON arrays replace Python list-literal strings for URLs, and all FAIR scoring conventions are preserved. Tier 10 also captures the two-source provenance model (manual curation vs automated discovery) and the parent-resource graph for derived/aggregated resources.

### Identity

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceID` | string | Stable RoP-internal identifier (`RoP-Resource:NNNNNNN`); never recycled |
| `ResourceName` | string | Full human-readable name |
| `ResourceAbbreviation` | string | Short identifier (PPMI, ADNI, NACC, etc.) |

### Categorization and content

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceType` | JSON array | Controlled-value array: Study / Cohort / Data Repository / Biorepository / Data Catalog / Code Repository / Knowledge Graph / Reference Dataset / Tool/Service / Publication Index / Other |
| `ResourceDescription` | string | Free-text description of the resource |
| `ResourceCoarseModality` | JSON array | Controlled-value modalities: clinical / longitudinal / demographics / imaging / genetics / transcriptomics / proteomics / metabolomics / epigenomics / microbiome / single-cell / spatial-omics / behavioral / wearable-sensor / EHR / claims / biospecimen-only / computational-tool |
| `ResourceGranularModality` | JSON array | Free-text detailed modalities (MRI, PET-amyloid, snRNA-seq, etc.) |
| `ResourceDiseases` | JSON array | Per-disease entries with name + Mondo/HPO/OMIM/MeSH code + vocabulary |
| `ResourceSampleSize` | JSON object | Structured `{total_n, cases_n, controls_n, biosamples_n, as_of_date, is_estimate, notes}` |

### Access

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceAccessURL` | string | Primary canonical landing URL |
| `ResourceAlternativeURLs` | JSON array | Mirror, archive, regional URLs (replaces CARD's Python list-literal-string convention) |

### FAIR assessment (carried over from CARD methodology)

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceFAIRScore` | numeric | 0-9 scale (carried over from CARD Catalog) |
| `ResourceFAIRIssues` | JSON array | Tag strings flagging FAIR shortcomings (No Version Info, No Container, No Dependencies, No README, etc.) |
| `ResourceFAIRNotes` | string | Free-text reviewer commentary |

### Curation provenance

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceCurator` | JSON array | Per-curator entries with `{name, orcid, affiliation, review_role}` — replaces CARD's slash-delimited initials convention |
| `ResourceDateAdded` | date | First addition to catalog |
| `ResourceDateLastUpdated` | date | Last review or update |
| `ResourceProvenanceSource` | enum | manual-curation / automated-discovery / automated-discovery-promoted-to-curated / imported-from-external-catalog / user-submitted |

### Relationships

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceLinkedDataAssets` | JSON array | Tier 8 DataAssetURI references owned/hosted by this resource |
| `ResourceLinkedSummaryStats` | JSON array | Tier 9 summary statistics derived from this resource's data |
| `ResourcePublications` | JSON array | Per-publication entries with `{pmid, doi, pmc_id, title, year, citation_type}` — citation_type distinguishes produced-by-resource / uses-resource / method-paper / cohort-description / review |
| `ResourceCodeRepositories` | JSON array | Per-repo entries with `{url, owner, languages, purpose, fair_score, fair_issues, biomedical_relevance, code_summary}` — preserves CARD's YES/NO/UNCLEAR LLM-vetting convention |
| `ResourceParentResources` | JSON array | Parent ResourceID values when this resource is derived/aggregated (AMP-PD aggregates PPMI + others; Path-ND uses NACC + GP2 + PPMI + ADSP-PHC) |
| `ResourceLinkedGovernance` | JSON array | Tier 7 governance row references that apply to this resource |

### Specialized sub-types

| Anchor | Type | Description |
|--------|------|-------------|
| `ResourceCellLineMetadata` | JSON object | When the resource is a cell-line catalog (iNDI-pattern): parental_line, genome_assembly, distribution_route, n_lines_total, edit_types — captures iNDI's "mostly-constant fields" without forcing them into per-row anchors |
| `ResourceImportedFromCatalog` | JSON object | When provenance is `imported-from-external-catalog`: source catalog name, version, original record ID, import date, import curator — supports bidirectional traceability for CARD Catalog → RoP migrations |

**Why this is its own tier rather than per-row metadata**: resource-level identity is the join target for cross-references from data assets, summary stats datasets, and individual external dataset linkages. Pulling resource metadata into a dedicated tier means a single record describes "what PPMI is" rather than that information being scattered across 10,000 individual-level rows. Critically, resources can be imported wholesale from external catalogs (CARD Catalog, BioPortal, OBO Foundry) with provenance preserved, and a resource record can exist in RoP without any associated individual-level data — useful for cataloging public data repositories or computational tools.

**CARD Catalog migration path**: The Tier 10 design is a structured improvement over CARD's flat tabular format. Migration: each CARD `resources-inventory` row becomes a Tier 10 record with `ResourceProvenanceSource=imported-from-external-catalog` and full traceability via `ResourceImportedFromCatalog`. CARD's `code` and `publications` tables collapse into Tier 10's `ResourceCodeRepositories` and `ResourcePublications` arrays. CARD's `iNDI_inventory` becomes a Tier 10 record with populated `ResourceCellLineMetadata`, and the per-line entries (626 lines) become individual-level RoP rows linked to the resource by `ResourceID`.

## Theme 13b: Special Collections Registry

**File**: `data/anchors/13_collections.json`

Module 13 is the registry of project-specific curated CDE bundles drawn from multiple source authorities — Path-ND, GP2-CDE, CARD-Catalog-CDE, Gates-Ventures-CDE, ADSP-PHC-CDE, and similar collections that DataTecnica or partner organizations maintain. Where Modules 1–12 cover the *anchor floor* of general CDEs harmonized from upstream authorities, Module 13 catalogs the *boutique bundles* that mix-and-match from those general CDEs (plus DataTecnica-derived rows where standard authorities don't cover a project's needs) and present them as coherent project-specific deliverables.

**The collection lives in one row per collection**; the actual member CDEs live across Modules 1–12 with appropriate `member_of_collections` tags. Looking up "what CDEs are in Path-ND v2.1" is a join: `SELECT * FROM rop_elements WHERE 'Path-ND' = ANY(member_of_collections)`.

### Identity and versioning

| Anchor | Type | Description |
|--------|------|-------------|
| `CollectionID` | string | Stable identifier (`RoP-Collection:NNNNNNN`); never recycled |
| `CollectionName` | string | Full name |
| `CollectionAbbreviation` | string | Short identifier — this is the value in `member_of_collections` arrays on individual CDE rows |
| `CollectionVersion` | string | Semantic version preferred (`1.0.0`, `2.3.1`) or date-based (`2026-04`) |
| `CollectionDescription` | string | Free-text description of purpose and scope |

### Ownership and curation

| Anchor | Type | Description |
|--------|------|-------------|
| `CollectionOwner` | JSON object | `{name, identifier (ROR/DUNS), contact_email, governance_url}` |
| `CollectionCurators` | JSON array | Per-curator: `{name, orcid, affiliation, role}` |

### Scope and provenance

| Anchor | Type | Description |
|--------|------|-------------|
| `CollectionScope` | JSON object | `{disease_areas, modalities, target_cohorts, out_of_scope}` |
| `CollectionSourceAuthorities` | JSON array | Upstream authorities contributing to this collection (LOINC, HPO, NACC, NINDS-CDE, PhenX, DataTecnica-derived, ...) |
| `CollectionParentCollections` | JSON array | Parent CollectionIDs when this is a derived/subset collection |
| `CollectionEquivalentCollections` | JSON array | Other collections covering similar scope with overlap estimates |
| `CollectionLinkedResources` | JSON array | Module 12 ResourceID references for source resources |

### Governance and FAIR

| Anchor | Type | Description |
|--------|------|-------------|
| `CollectionGovernanceClass` | JSON object | Default DUO class, sharing posture, DUA reference, license |
| `CollectionFAIRScore` | numeric | 0–9 collection-level FAIR score (CARD methodology) |

### Operational tracking

| Anchor | Type | Description |
|--------|------|-------------|
| `CollectionMemberCount` | JSON object | `{total, by_module, by_source_authority, snapshot_date}` — computed at bundle build time |
| `CollectionPromotionStatus` | JSON object | Tracks upstream submission of DataTecnica-derived CDEs to LOINC, HPO, etc. — quantifies contribution to public CDE infrastructure |

**Why this is its own module rather than a column on the elements table**: the elements table already has `member_of_collections` for per-row collection tagging. What Module 13 adds is the *registry*: collections are first-class objects with their own metadata, governance, curators, FAIR scoring, and lifecycle. Without a registry, "Path-ND" is just a string tag with no metadata; with a registry, it's a versioned bundle with documented scope, governance, contributing authorities, equivalent alternatives, and an audit trail for upstream-promotion of its DataTecnica-derived rows.

**The promotion pipeline**: DataTecnica-derived CDEs in a collection that turn out to be genuinely novel (no upstream equivalent in any standard authority) become candidates for upstream submission to LOINC, HPO, OMIM, etc. `CollectionPromotionStatus` tracks where each candidate is in that pipeline. Once accepted upstream, the boutique row is deprecated (`is_active=false`, `replaced_by_rop_id=<upstream-row>`) and the upstream row becomes canonical. The collection retains its membership but cites the upstream CDE rather than the deprecated boutique row. This is the structural fix to the proliferation of disconnected CDE efforts: rather than every project minting its own permanent CDE library, the boutique CDEs are an explicit feeder into the standard authorities.



A submission is RoP-conformant at increasing levels. Modules 1–7 stack analytically; the orthogonal attestations (S, D, P, A, R, C) capture independent capabilities — a cohort can be analytically conformant at any level without these attestations, but each one gates a specific class of downstream use.

| Level / Attestation | Requirement | Enables |
|---------------------|-------------|---------|
| 1 | Standard RoP element columns valid + Module 1 (Identity) | Basic ingest, intra-cohort use |
| 2 | + Module 3 (Time) | Longitudinal analysis |
| 3 | + Module 4 (Sex) | Sex-stratified analysis |
| 4 | + Module 5 (Ancestry) | Genetic association analysis |
| 5 | + Module 6 (Biosample) | Sample-level data linkage |
| 6 | + Module 7 (Omics) | Multi-omics meta-analysis |
| 7 | + Module 8 (Clinical Instruments) | Cross-cohort cognitive/motor/QoL meta-analysis |
| **S** | + Module 9 (Governance) | **Re-share, cross-institutional transfer, federated analysis** |
| **D** | + Module 10 (Data Assets) | **Binary data retrieval; pipeline-driven analysis on raw/aligned/processed files** |
| **P** | + Module 2 (Pedigree) | **Family-based association tests, IBD inference, transmission analyses** |
| **A** | + Module 11 (Summary Stats) | **Meta-analysis contribution, PRS construction, MR studies, covariate re-use** |
| **R** | + Module 12 (Resource) | **Resource-catalog inclusion, cross-resource discovery, FAIR-scored discoverability** |
| **C** | + Module 13 (Collections) | **Special-collection membership tracking, project-specific bundle distribution, upstream-promotion provenance** |

Cross-cohort meta-analysis eligibility starts at Level 3 (clinical), Level 6 (multi-omics), or Level 7 (cognitive/motor); in all cases requires Sharing-Ready (S) status. Computational re-analysis on raw or processed binary data requires Asset-Linked (D). Family-based analyses require Pedigree-Linked (P). Contributing to or aggregating cross-cohort summary statistics requires Analytics-Linked (A). Discoverability through resource catalogs requires Resource-Cataloged (R). Membership in DataTecnica-curated boutique collections (Path-ND, GP2-CDE, CARD, Gates Ventures, ADSP-PHC) requires Collection-Tagged (C).

## Conformance Levels

A submission is RoP-conformant at increasing levels. Themes 1–9 stack analytically; the orthogonal attestations (S, D, P, A, R, C) capture independent capabilities — a cohort can be analytically conformant at any level without these attestations, but each one gates a specific class of downstream use.

| Level / Attestation | Requirement | Enables |
|---------------------|-------------|---------|
| 1 | Standard RoP element columns valid + Theme 1 (Identity) | Basic ingest, intra-cohort use |
| 2 | + Theme 2 (Time) | Longitudinal analysis |
| 3 | + Theme 3 (Sex) | Sex-stratified analysis |
| 4 | + Theme 4 (Ancestry & Pedigree, ancestry subset) | Genetic association analysis |
| 5 | + Theme 5 (Biosample) | Sample-level data linkage |
| 6 | + Theme 6 (Omics) | Multi-omics meta-analysis |
| 7 | + Theme 7 (Imaging Acquisition) | Cross-cohort imaging meta-analysis with consistent acquisition metadata |
| 8 | + Theme 8 (Clinical Instruments) | Cross-cohort cognitive/motor/QoL meta-analysis |
| 9 | + Theme 12 (Clinical Concepts) | EHR/claims-style clinical analysis with OMOP-resolved diagnoses, drugs, procedures, labs |
| **S** | + Theme 9 (Governance) | **Re-share, cross-institutional transfer, federated analysis** |
| **D** | + Theme 10 (Data Assets) | **Binary data retrieval; pipeline-driven analysis on raw/aligned/processed files** |
| **P** | + Theme 4 (pedigree subset) | **Family-based association tests, IBD inference, transmission analyses** |
| **A** | + Theme 11 (Summary Stats) | **Meta-analysis contribution, PRS construction, MR studies, covariate re-use** |
| **R** | + Theme 13a (Resources) | **Resource-catalog inclusion, cross-resource discovery, FAIR-scored discoverability** |
| **C** | + Theme 13b (Collections) | **Special-collection membership, project-specific bundle distribution, upstream-promotion provenance** |

Cross-cohort meta-analysis eligibility starts at Level 3 (clinical), Level 6 (multi-omics), Level 7 (cognitive/motor), or Level 8 (EHR-style); in all cases requires Sharing-Ready (S) status. Computational re-analysis on raw or processed binary data requires Asset-Linked (D). Family-based analyses require Pedigree-Linked (P). Contributing to or aggregating cross-cohort summary statistics requires Analytics-Linked (A). Discoverability through resource catalogs requires Resource-Cataloged (R). Membership in DataTecnica-curated boutique collections (Path-ND, GP2-CDE, CARD, Gates Ventures, ADSP-PHC) requires Collection-Tagged (C).



The current anchor floor covers identity (sex, ancestry), time, biosample lineage, and omics platform. Candidate future tiers under discussion:

- **Imaging metadata** — modality, manufacturer, model, sequence parameters, reconstruction software (would mirror Tier 5 omics structure but for radiology)
- **Clinical rating instruments** — instrument identity, version, language, scoring conventions (covers MoCA, MMSE, MDS-UPDRS, etc.)
- **Consent and DUA** — consent type, IRB approval, allowable downstream uses (operational rather than scientific, but increasingly necessary)
- **Drug exposure** — RxNorm pivot, dosing, indication, adherence (extends LEDD-style harmonization to all therapeutic exposures)

Proposals for new anchors follow the workflow in `docs/GOVERNANCE.md`.
