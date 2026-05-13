# RoP Build Environment Setup

**Last updated:** 2026-05-02
**Status:** Venv configured, 99 tests passing

---

## Environment Setup (Completed)

### 1. Python Virtual Environment

```bash
# Create venv with system site-packages access
python3 -m venv --system-site-packages .venv

# Activate
source .venv/bin/activate

# Verify
python --version  # Python 3.10.12
which python      # /mnt/c/.../rop_build/.venv/bin/python
```

**Note:** Using `--system-site-packages` because WSL environment has pre-installed dependencies (pyarrow, pydantic) in user site-packages that we want to leverage.

### 2. Dependencies Installed

Core dependencies available via system site-packages:
- **pytest 9.0.3** — test runner
- **pyarrow 20.0.0** — parquet I/O
- **pydantic 2.11.7** — schema validation
- **duckdb 1.5.2** — SQL dedup/merge engine
- **pydicom 3.0.2** — DICOM tag ingest
- **pyyaml 5.4.1** — BIDS schema parsing

All dependencies from [pyproject.toml](../pyproject.toml) are satisfied.

### 3. Test Baseline

```bash
source .venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -q
```

**Result:** **99 passed in 1.06s** ✅

Breakdown (from CLAUDE.md):
- 33 schema/validation tests
- 17 ingest pipeline tests
- 17 equivalence tests
- 32 security tests

---

## Staged Data Sources

### NINDS-CDE (Pre-staged by Mike)

```
data/sources/ninds_cde/cde-details_20260501_150832.csv
  Size: 34 MB
  Rows: ~38,000 expected
  Columns: 27 (includes LOINC/SNOMED/caDSR/CDISC xrefs)
```

### Athena (Pre-staged by Mike)

```
data/sources/athena/athena_download-May1st2026/
```

| File | Size | Notes |
|------|------|-------|
| CONCEPT.csv | 1.3 GB | One row per concept across all vocabularies |
| CONCEPT_RELATIONSHIP.csv | 2.6 GB | Cross-vocab edges; source of LOINC six-axis + Maps-to |
| CONCEPT_ANCESTOR.csv | 1.8 GB | Hierarchical closure (not used in v2026.04) |
| CONCEPT_SYNONYM.csv | 344 MB | Alternate names per concept |
| DRUG_STRENGTH.csv | 151 MB | RxNorm dose (not used in v2026.04) |
| VOCABULARY.csv | 15 KB | Vocabulary metadata + versions |

**Delimiter detected:** **TAB** (not comma, despite CLAUDE.md note about newer releases)

The `_sniff_delimiter()` helper in [rop/ingest/athena.py](../rop/ingest/athena.py:59-76) auto-detects this correctly via header inspection.

---

## Git Repository Status

**Not initialized as git repo yet.** Working directory for local build; will push to git after bundle is built and signed off.

Per Mike's instruction: "we are doing this locally then pushing to git"

Commit strategy deferred until Sprint 1 checkpoints are ready for version control.

---

## Next Steps (Awaiting Mike's Go-Ahead)

Sprint 1 Day 1 work ready to start:

1. **Auto-download sources:** HPO, Mondo, DUO, BIDS, CDISC, PhenX, DICOM
2. **Ingest NINDS-CDE** (already staged)
3. **Ingest Athena** (already staged, skip download)

Orchestrator command:
```bash
source .venv/bin/activate
python scripts/sprint1_download_all.py \
    --sources hpo,mondo,duo,bids,cdisc,phenx,dicom,ninds_cde,athena \
    --skip-download  # for athena only
```

Or run sources individually to validate output before proceeding to next.

**Mike: Which sources should we fetch first?**
