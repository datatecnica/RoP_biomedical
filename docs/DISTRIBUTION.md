# RoP Distribution Strategy

## Two-Channel Strategy: GitHub + Hugging Face

### Channel 1: GitHub — Code + Docs
**Repository:** `github.com/datatecnica/rop_build`

**What goes in git:**
- ✅ Python code (`rop/`, `scripts/`, `tests/`)
- ✅ Anchor JSON files (`data/anchors/` — 224 anchors, ~50 KB)
- ✅ Documentation (`docs/*.md`, `README.md`, `CLAUDE.md`)
- ✅ Configuration (`pyproject.toml`, `migrations/`)
- ✅ `.gitkeep` files for directory structure

**What NEVER goes in git** (enforced by security_screen.py):
- ❌ Files >50 MB (GitHub soft limit)
- ❌ Source downloads (`data/sources/`) — reproducible via scripts
- ❌ Build artifacts (`data/foundation/staging/`, `data/final/`)
- ❌ Boutique CDEs (`data/boutique/`) — confidential
- ❌ Bundles (`dist/`) — distributed via Hugging Face
- ❌ Logs, checkpoints, credentials

**Repo size:** ~5-10 MB

---

### Channel 2: Hugging Face — Bundles + Docs (with Zenodo DOI)
**Repository:** `huggingface.co/datasets/datatecnica/rop`

**What goes on Hugging Face:**
- ✅ `v2026.04/elements.parquet` (151 MB)
- ✅ `v2026.04/embeddings.npy` (3.9 GB)
- ✅ `v2026.04/embeddings.faiss` (3.9 GB)
- ✅ `v2026.04/manifest.json` (SHA256 checksums)
- ✅ `README.md` (dataset card)
- ✅ Documentation (mirrors GitHub docs/)

**Zenodo DOI Integration:**
Hugging Face natively integrates with Zenodo:
1. Enable Zenodo integration in HF repo settings
2. Create release on HF
3. Automatic DOI assignment via Zenodo
4. DOI badge added to repo

---

## Command-Line Workflows

### GitHub: Push Code + Docs
```bash
# Before every commit, run security screen
python3 scripts/security_screen.py

# Commit and push
git add rop/ scripts/ tests/ docs/ data/anchors/ README.md pyproject.toml
git commit -m "v2026.04: Final release"
git push origin main
```

### Hugging Face: Upload Bundle + Docs
```bash
# Install Hugging Face CLI
pip install huggingface_hub

# Login (one-time)
huggingface-cli login

# Create dataset repo (one-time)
huggingface-cli repo create rop --type dataset --organization datatecnica

# Upload v2026.04 bundle
huggingface-cli upload datatecnica/rop dist/rop_v2026.04/ v2026.04/ --repo-type dataset

# Upload docs (mirror from GitHub)
huggingface-cli upload datatecnica/rop docs/ docs/ --repo-type dataset
huggingface-cli upload datatecnica/rop README.md README.md --repo-type dataset

# Create release + DOI (via HF web UI or API)
# Settings → Enable Zenodo integration → Create release → Get DOI
```

---

## User Download Methods

### Method 1: Hugging Face Hub (Python)
```python
from huggingface_hub import hf_hub_download

# Download specific files
elements = hf_hub_download("datatecnica/rop", "v2026.04/elements.parquet")
embeddings = hf_hub_download("datatecnica/rop", "v2026.04/embeddings.npy")
faiss_index = hf_hub_download("datatecnica/rop", "v2026.04/embeddings.faiss")
manifest = hf_hub_download("datatecnica/rop", "v2026.04/manifest.json")
```

### Method 2: Hugging Face CLI
```bash
huggingface-cli download datatecnica/rop --repo-type dataset --local-dir ./rop_bundle --include "v2026.04/*"
```

### Method 3: wget/curl
```bash
wget https://huggingface.co/datasets/datatecnica/rop/resolve/main/v2026.04/elements.parquet
wget https://huggingface.co/datasets/datatecnica/rop/resolve/main/v2026.04/embeddings.npy
wget https://huggingface.co/datasets/datatecnica/rop/resolve/main/v2026.04/embeddings.faiss
wget https://huggingface.co/datasets/datatecnica/rop/resolve/main/v2026.04/manifest.json
```

### Method 4: Build from Source (GitHub)
```bash
git clone https://github.com/datatecnica/rop_build.git
cd rop_build
python3 -m venv venv && source venv/bin/activate
pip install -e .

# Reproduce full bundle (6-7 hours)
python3 scripts/sprint1_download_all.py
python3 scripts/sprint1_dedup_pass1.py
python3 scripts/generate_embeddings_direct.py  # 6 hours (GPU)
python3 scripts/build_faiss_index.py           # 25 min
python3 scripts/package_bundle.py

# Output: dist/rop_v2026.04/
```

---

## Integrity Verification

After download, verify SHA256 checksums:
```bash
sha256sum -c <(jq -r '.files | to_entries[] | "\(.value.sha256)  \(.key)"' v2026.04/manifest.json)
```

Expected output:
```
elements.parquet: OK
embeddings.npy: OK
embeddings.faiss: OK
```

---

## Citation

Once Zenodo DOI is assigned via Hugging Face integration:

```bibtex
@dataset{rop_v202604,
  author       = {Vitale, Dan and
                  Marini, Pietro and
                  Nalls, Michael A.},
  title        = {RoP v2026.04 - Biomedical Reference of Parameters},
  year         = {2026},
  publisher    = {Hugging Face},
  doi          = {10.5281/zenodo.XXXXXX},
  url          = {https://huggingface.co/datasets/datatecnica/rop}
}
```

---

## License

**Dual-licensed:**
- **Code** (Python, scripts): AGPLv3
- **Data** (anchors, elements, embeddings): CC-BY-NC-4.0

**Attribution requirement (CC-BY-NC-4.0):**
> This work includes data from RoP (Biomedical Reference of Parameters) v2026.04,
> © 2026 Pietro Marini, Alan Long, Hirotaka Iwaki, Mike Nalls, Dan Vitale (DataTecnica),
> licensed under CC-BY-NC-4.0. https://doi.org/10.5281/zenodo.XXXXXX
> Commercial use: info@datatecnica.com

---

## Security Screening

Before every git push:
```bash
python3 scripts/security_screen.py
```

Checks:
- ✅ No files >50 MB
- ✅ No API keys, tokens, credentials
- ✅ No PHI/PII patterns
- ✅ No forbidden directories tracked
- ✅ All large files gitignored

---

## Implementation Checklist

- [x] `.gitignore` configured
- [x] Security screening script created
- [ ] Run security screen: `python3 scripts/security_screen.py`
- [ ] Create Hugging Face dataset repo: `datatecnica/rop`
- [ ] Upload v2026.04 bundle to Hugging Face
- [ ] Upload docs to Hugging Face
- [ ] Enable Zenodo integration in HF settings
- [ ] Create HF release → Get DOI
- [ ] Update README.md with download instructions + DOI badge
- [ ] Git push to GitHub
