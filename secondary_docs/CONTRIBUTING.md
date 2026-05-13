# Contributing to RoP

Thank you for considering a contribution. RoP grows through community participation; the value of the contract is proportional to how many groups use it and propose improvements.

## Quick guide: which workflow do I want?

| I want to… | Workflow |
|------------|----------|
| Propose a new RoP row for a concept that's missing | GitHub Issue, label `proposal:new-row` |
| Propose a new equivalence between existing rows | GitHub Issue, label `proposal:equivalence` |
| Propose a new source authority | GitHub Discussion under `governance` |
| Propose a new anchor or anchor tier | GitHub Discussion + draft PR |
| Report a bug in the validation engine | GitHub Issue, label `bug` |
| Improve documentation | Pull request directly |
| Improve domain-agnostic core code | Pull request with tests |
| Adopt RoP for my cohort | See `docs/ADOPTION.md` (forthcoming v2026.07) |

## Proposing a new RoP row

Open an issue with the `proposal:new-row` label. Structure the issue body as JSON conforming to the element schema in `docs/SPEC.md` §2. Required fields:

```json
{
  "item": "MyNewCDE",
  "description": "Clear, complete definition.",
  "source_authority": "LOINC | HPO | OMIM | ...",
  "source_code": "<native ID>",
  "source_version": "<pinned release>",
  "source_url": "<deep link>",
  "rationale": "Why this concept isn't already in RoP and why it matters."
}
```

The issue is automatically routed to the curator pool for the relevant tier. Expect a response within 5 business days. Approved proposals are added in the next quarterly bundle.

## Proposing an equivalence claim

Open an issue with `proposal:equivalence`. Body must include:

```
RoP rows: [RoP:0001234, RoP:0005678]
Justification:
  - Cross-source xref agreement (cite source xref tokens)
  - Same OMOP concept_id (cite concept_id)
  - OMOP CONCEPT_RELATIONSHIP 'Maps to' edge (cite both concept_ids)
  - Domain expertise (provide curator credentials)
Confidence: high | medium | low
```

Equivalences with `confidence: low` are typically held for HitL review; medium and high may be auto-applied with appropriate audit trail.

## Proposing a new source authority

Open a Discussion under the `governance` category. Address:

1. **Licensing**: Is the authority openly redistributable? If license-gated, what is the handling plan (full bundle vs. public bundle, attribution requirements)?
2. **Versioning**: How does the authority release versions? Is the release cadence predictable?
3. **Coverage**: What does this authority add that existing authorities don't?
4. **Ingest plan**: Who will write and maintain the ingest pipeline?
5. **Curator commitment**: Who will provide ongoing review of authority-specific rows?

Adding a source authority requires consensus among existing maintainers. Expect 2–4 weeks for resolution.

## Proposing a new anchor or anchor tier

This is the highest-friction proposal type because anchors are mandatory for conformance. Anchors must clear a higher bar than ordinary RoP rows.

Step 1: Open a Discussion describing the harmonization failure mode you're addressing. Include concrete examples from at least 3 existing collections.

Step 2: Draft a PR against `data/anchors/`, following the format of existing tier files. Include:
- Per-anchor descriptions, types, controlled vocabularies
- Conditional-required validation rules
- Transformation rules where applicable
- Citation of the source authority for any controlled vocabularies used

Step 3: Solicit feedback from at least one curator outside DataTecnica (CARD, GP2, or external collection owner).

Step 4: Maintainer review and consensus.

Anchor proposals that don't clear all four steps are deferred to subsequent releases. We err strongly toward stability.

## Code contributions

All code is AGPLv3 licensed. By submitting a pull request you agree to license your contribution under those terms.

### Style

- Python: black-formatted, ruff-clean, type hints on public functions
- SQL: lowercase keywords, indented uniformly, comments for any non-obvious logic
- Markdown: prose preferred over heavy bullet lists in normative documents

### Tests

New or modified validation logic must include tests. We use `pytest`. Run locally:

```bash
pip install -e ".[dev]"
pytest tests/
```

### Domain-agnostic core vs. biomedical instantiation

A current priority is strengthening the separation between the domain-agnostic core (validation engine, embedding pipeline, bundle format, conditional-required parser) and the biomedical instantiation (anchor tiers, default vocabularies, source authorities). Pull requests that move logic from biomedical-specific modules into domain-agnostic ones are particularly welcome.

## Code of conduct

- Be civil. Disagreement is fine; ad hominem is not.
- Attribute work and ideas. Curators and proposers are credited in the audit trail and in release notes.
- Assume good faith. RoP exists to lower friction in collaborative science. Internal disagreements should not increase that friction.
- If a discussion is unproductive, maintainers may close it and reopen the underlying technical question separately.

## Recognition

Contributors are listed in `CONTRIBUTORS.md`, updated each release. Significant contributions (anchor tiers, source authority ingests, major code modules) earn co-authorship on the corresponding methods publication.

## Contact

- Public discussion: GitHub Discussions
- Sensitive or licensing-related questions: info@datatecnica.com
- Security issues: security@datatecnica.com (use PGP key from website)
