# Roadmap

This roadmap is intentionally conservative. RoP's value depends on predictability — promising less and delivering on schedule beats promising more and missing.

## Release cadence

Quarterly bundle releases, aligned with the calendar quarter:

| Version | Target | Status |
|---------|--------|--------|
| `2026.04` | Q2 2026 | In active development; first public release |
| `2026.07` | Q3 2026 | Planned |
| `2026.10` | Q4 2026 | Planned |
| `2027.01` | Q1 2027 | Planned |

Off-cycle patch releases (`YYYY.QQ.N`) are issued only for critical corrections (incorrect equivalence claims, broken cross-vocabulary links, security issues in tooling).

## v2026.04 — Foundation (Q2 2026)

**Goal**: First public release. Establish the contract, the bundle format, and the governance workflow.

Scope:
- All five Core Anchor tiers defined and documented
- Reference implementation of the validation engine
- Reference implementation of the embedding pipeline
- Reference implementation of the bundle builder
- Schema migration for existing Forge deployments
- Initial seed from Path-ND, GP2, and PPMI curated CDEs (~5,000 expert-curated rows)
- Initial omni_vocab backbone from LOINC, HPO, OMIM, Mondo, OMOP/Athena (~3M rows)
- Zenodo deposit with DOI
- GitHub Discussions enabled for proposals

Out of scope for v2026.04:
- NACC UDS-3.0 ingest (deferred to v2026.07 pending DUA review)
- NINDS-CDE library full ingest (deferred to v2026.07)
- PhenX Toolkit full ingest (deferred to v2026.07)
- Imaging metadata anchor tier
- Clinical rating instrument anchor tier
- BioPortal mirror
- OLS-compatible serving

## v2026.07 — Adoption breadth (Q3 2026)

**Goal**: Broaden source authority coverage; first cross-cohort harmonization demonstration.

Scope:
- NACC UDS-3.0 ingest (pending DUA finalization)
- NINDS-CDE library ingest
- PhenX Toolkit ingest
- CDISC SDTM-3.4 ingest for AE/CM/MH domains
- Cross-cohort harmonization case study published as preprint (Path-ND ↔ GP2 ↔ PPMI ↔ ADSP-PHC re-harmonization)
- Forge integration: anchor validation gates wired into ingest UI

Stretch:
- BioPortal mirror submission
- First external collection adoption (target: NIH-funded consortium outside DataTecnica's existing portfolio)

## v2026.10 — Imaging tier (Q4 2026)

**Goal**: Add Tier 6 (Imaging) to the anchor floor.

Scope:
- Anchor tier 6 defined: modality, manufacturer, model, sequence parameters, reconstruction
- DICOM metadata bridges
- Acquisition and reconstruction software provenance
- Integration with existing imaging biobanks (PPMI, ADNI structures)

## v2027.01 — Clinical instruments tier (Q1 2027)

**Goal**: Add Tier 7 (Clinical Rating Instruments) to anchor floor.

Scope:
- Anchor tier 7: instrument identity, version, language, scoring conventions
- Coverage of MoCA, MMSE, MDS-UPDRS, NPI, GDS, FAQ, CDR, ADAS-Cog
- Score normalization and crosswalks for instruments with multiple versions

## Beyond v2027 — Vertical extensions

The structural pattern of RoP (anchor tiers + source-authority provenance + governance layer) is domain-agnostic. We commit to maintaining a clean separation between the biomedical instantiation and the domain-agnostic core.

### Confirmed: continued biomedical depth

- Drug exposure tier (RxNorm pivot)
- Consent and DUA tier
- Trial protocol tier (clinicaltrials.gov bridges)
- Real-world evidence tier (claims data, EHR extracts)

### Possible: domain-agnostic core extraction

If sufficient external interest emerges, we will extract the domain-agnostic core into a separate package (`rop-core`) with the biomedical instantiation as the first reference (`rop-biomedical`). This would enable parallel development of:

- `rop-financial` — instruments, transactions, parties, regulatory authorities
- `rop-environmental` — sensors, locations, calibration, time series
- `rop-legal` — jurisdictions, document types, parties, dates
- `rop-manufacturing` — assets, batches, measurement methods
- `rop-education` — students, instruments, cohorts, longitudinal observations

Each domain instantiation would have its own anchor tiers, source authorities, and curator pool, while sharing the validation engine, embedding pipeline, bundle format, conditional-required parser, and governance model.

We will not pursue domain extraction speculatively. It happens when there is concrete demand from a credible domain partner.

## Quality metrics

Per-release quality metrics published in each bundle's manifest:

| Metric | Target |
|--------|--------|
| Auto-resolution rate (incoming variables → existing RoP rows) | Increasing per release as RoP grows |
| Median HitL queue time-to-resolution | < 5 business days |
| Cross-cohort harmonization wins (cohorts onboarded per quarter) | ≥ 2 |
| Adoption (Zenodo downloads, citing publications) | Tracked, not gated |
| Anchor coverage (% of cohorts at conformance Level 3+) | ≥ 80% by v2027.01 |

These metrics are reported transparently each release. They are not used to gate the release itself.

## Sustainability commitment

We commit to operating RoP through at least 2030. If maintenance ever transfers to a different organization, we commit to providing a clean handoff with at least 12 months of overlap and continuity of the bundle's accession namespace.

Source code is AGPLv3; documentation, anchor definitions, and bundle data are CC-BY-NC-4.0. These licenses do not lapse if maintenance changes hands.
