# Governance

RoP is a contract. The Forge is the governance layer that operationalizes it.

This document describes how the contract is enforced, how the contract grows, and how the community contributes.

## 1. Why "governance" and not just "tooling"

A static reference document is not enforceable. A CDE PDF can be ignored, misread, or selectively applied. The reason RoP is described as a contract rather than a publication is that compliance is *operationally checked* every time data flows through The Forge. The contract has teeth because the tool runs the contract.

This is the difference between a constitution and a court system. RoP without Forge is a thoughtful document. Forge without RoP is a useful piece of infrastructure. Together, they are a working interoperability regime.

## 2. The Five Roles of The Forge

When data enters The Forge, the governance layer plays five distinct roles:

### 2.1 Validator

Forge checks every incoming submission against the relevant Core Anchor tiers. Conditional-required rules are parsed and enforced. Violations are surfaced as ingest errors before any data lands in shared infrastructure. Cross-row consistency checks (biosample lineage, visit-date / collection-date alignment, six-axis omics tuples that resolve to a real biosample) are performed as a post-ingest pass.

### 2.2 Matcher

Variables in incoming submissions that don't map directly to existing RoP rows are routed through Forge's two-stage semantic matcher: an embedding-based first-stage retrieval that produces a candidate set, followed by an AI vetting stage that scores semantic equivalence against full RoP context (description, source authority, collection memberships, value set). High-confidence matches auto-bind. Borderline cases escalate to HitL.

### 2.3 Curator

When the matcher escalates a novel concept, a domain curator reviews the candidate. The curator can:
- Confirm a proposed match (promotes `auto-matched` → `HitL-confirmed`)
- Reject and propose an alternative (modifies `equivalent_rop_ids`)
- Declare the concept genuinely novel (creates a new RoP row)
- Mark a concept as ambiguous (flag for collection-specific resolution)

Every curation decision is attributed (ORCID or governance handle) and timestamped.

### 2.4 Versioner

Forge computes content hashes on every committed change. When a row's content changes, the embedding is rebuilt; when an upstream source updates and the row content is unchanged, only `source_version` is updated. Quarterly bundle releases roll up changes since the prior bundle into a versioned, signed artifact.

### 2.5 Auditor

Every row, every change, every match decision, every curator action is queryable. This satisfies NIH FAIR principles and reproducibility requirements without a separate effort. When a journal reviewer asks "how did you arrive at this harmonization", the answer is a signed audit trail.

## 3. Reference Implementation vs. Specification

The Forge is **the reference implementation** of RoP governance, but the contract itself does not require Forge specifically. Other tools could implement the contract — and we will accept upstream patches that strengthen the separation between contract and implementation.

However, we explicitly commit to Forge being a high-quality, full-featured reference. New cohorts that don't have a governance layer yet should not be put in the position of writing one from scratch. Forge will continue to be the path of least resistance.

## 4. The Living Repository

RoP is a living repository. Three operational commitments make this real:

### 4.1 Public release cadence

Quarterly bundles. No exceptions. Even when the delta is small. Predictability is what makes a contract trustworthy. Off-cycle patches are permitted for corrections; major version bumps are rare and announced months in advance.

### 4.2 Backward compatibility

`rop_accession` values are forever. Deprecations preserve rows with `is_active=false` and `replaced_by_rop_id`. References from published harmonizations always resolve. Schema additions are additive; removals require a major version bump.

### 4.3 Public proposal pathway

External groups can propose new anchors, source authorities, vocabulary additions, or equivalence claims. Proposals are reviewed through Forge's HitL workflow. Decisions are made transparently, with attribution preserved.

## 5. Contribution Workflow

### 5.1 Proposing a new RoP row

A new row may be proposed when:
- A source authority has a concept not currently represented in RoP
- A cohort has a CDE that doesn't match any existing row even after manual review
- A new value set is needed for an existing item

Proposal mechanism: GitHub Issue with the `proposal:new-row` label, structured as JSON conforming to §2 of `SPEC.md`. The issue is automatically routed to the curator pool for the relevant tier (time, sex, ancestry, biosample, anatomy/cell, omics, or general).

### 5.2 Proposing a new equivalence claim

A new entry in `equivalent_rop_ids` may be proposed when two existing RoP rows from different source authorities are demonstrably synonymous. The claim must include:
- Both `rop_accession` values
- Justification (cross-source xref agreement, OMOP concept_id match, OMOP CONCEPT_RELATIONSHIP 'Maps to' edge, or domain expertise)
- A confidence assessment

Proposal mechanism: GitHub Issue with the `proposal:equivalence` label.

### 5.3 Proposing a new source authority

Adding a source authority is a structural change. Proposals must address:
- The authority's licensing (open redistribution preferred; license-gated authorities require explicit handling)
- Versioning practices
- Coverage relative to existing authorities
- Curator commitment for ongoing ingest

Proposal mechanism: GitHub Discussion under the `governance` category. Requires consensus among existing maintainers.

### 5.4 Proposing a new anchor or anchor tier

Adding to the anchor floor is the highest-friction proposal type because anchors are mandatory for conformance. Proposals must:
- Identify a class of cross-cohort harmonization failure that the new anchor would prevent
- Propose specific column definitions following the existing anchor pattern
- Include conditional-required validation rules
- Demonstrate that 3+ existing collections would benefit

Proposal mechanism: GitHub Discussion plus a draft PR against `data/anchors/`. Requires consensus among existing maintainers and at least one external collection owner.

## 6. Curator Pool

Curators are domain experts who have demonstrated familiarity with both the source authorities and the RoP contract. The current pool includes:

- DataTecnica RoP Working Group (default routing for all proposals)
- NIH CARD (neurodegeneration; default routing for HPO, OMIM, Mondo, NACC)
- Global Parkinson's Genetics Program (genetic ancestry, biosample, omics)
- Per-collection owners (routing for proposals affecting their collection)

New curators are added by consensus of existing maintainers. Curator decisions are appealable to the maintainer group.

## 7. Conflict Resolution

When source authorities disagree on a concept (e.g., NACC and PhenX define overlapping but non-identical fields), RoP preserves both as distinct rows linked by `equivalent_rop_ids` with the appropriate confidence. RoP does not adjudicate which authority is "correct" — that adjudication is left to the consuming analyst, who can choose which authority's row to bind their cohort variable to.

When two RoP rows from the same source authority appear to duplicate, the older `rop_accession` wins; the newer is deprecated with `replaced_by_rop_id` set. This rule is mechanical and does not require curator review.

When a curator decision is contested, the contesting party may file an appeal as a GitHub Issue with the `appeal` label. Appeals are reviewed by the maintainer group. If consensus is not reached within 30 days, the original decision stands.

## 8. Funding and Sustainability

RoP is operated by DataTecnica LLC with material in-kind contributions from NIH CARD and the Global Parkinson's Genetics Program. The bundle and specification are open. The Forge governance implementation is a commercial product; alternative implementations are welcome and will be linked from this repository.

We commit to:
- Maintaining the bundle and specification as openly licensed (CC-BY-NC-4.0 for content, AGPLv3 for code)
- Continuing quarterly releases through at least 2030
- Providing migration paths if RoP maintenance ever transfers to a different organization

## 9. How RoP Replaces "Just Another CDE Project"

The implicit promise of RoP is that the field should not need another single-cohort CDE list. When NIH funds the next consortium, the right move is to add a `member_of_collections` tag to existing RoP rows and propose new rows where needed — not to convene a six-month committee to produce another PDF.

This is the structural fix to the proliferation of disconnected CDE efforts. The cost of saying so plainly is that we have to back it up with reliable governance, predictable releases, and genuinely lower friction than the alternative. That is what this repository commits to.

## 10. The Internal Joke

The internal name of this project is *Ring of Power*. The external name is *Biomedical Reference of Parameters*.

The internal name appears in code comments, internal Slack channels, and team documents. The external name appears in publications, NIH reports, and any context where someone might reasonably search for "another CDE thing for biomedicine."

Both names refer to the same thing. The team will use the internal name. The world will see the external name. This is intentional.
