"""Bundle builder.

Emits the versioned distributable artifact described in SPEC §7:

    rop_v<VERSION>/
    ├── rop.parquet
    ├── rop_embeddings.parquet
    ├── rop.faiss
    ├── manifest.json
    ├── README.md
    └── LICENSE.md
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import polars as pl

from rop.schema import RoPElement, compute_content_hash, compose_search_text
from rop.embed import (
    EmbeddingConfig,
    DEFAULT_MODEL,
    encode_elements,
    build_faiss_index,
    save_faiss_index,
)


# Default upstream source authority versions; override in build_bundle() call
DEFAULT_SOURCE_VERSIONS = {
    "LOINC": "2.78",
    "HPO": "2026-02-06",
    "OMIM": "2026-03-15",
    "Mondo": "2026-04-01",
    "OMOP": "Athena-2026-03",
    "NACC": "UDS-3.0",
    "NINDS-CDE": "v3.1",
    "PhenX": "Toolkit-2024",
    "CDISC": "SDTM-3.4",
}

ANCHOR_TIER_VERSIONS = {
    "01_time": "1.0",
    "02_sex": "1.0",
    "03_ancestry": "1.0",
    "04_biosample": "1.0",
    "05_anatomy_celltype": "1.0",
    "06_omics": "1.0",
}


def build_bundle(
    elements: Iterable[RoPElement],
    out_dir: Path | str,
    bundle_version: str,
    source_versions: dict[str, str] | None = None,
    embedding_config: EmbeddingConfig | None = None,
    use_ivf: bool = False,
) -> Path:
    """Build a complete RoP bundle from an iterable of elements.

    Returns the bundle directory path.
    """
    out_dir = Path(out_dir).resolve()
    bundle_dir = out_dir / f"rop_v{bundle_version}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    elements_list = list(elements)

    # Fill in derived fields where missing
    for e in elements_list:
        if not e.search_text:
            e.search_text = compose_search_text(e)
        if not e.content_hash:
            e.content_hash = compute_content_hash(e)

    # Encode embeddings
    config = embedding_config or EmbeddingConfig()
    vectors = encode_elements(elements_list, config)

    # --- Write rop.parquet (everything except embedding) ---
    elements_df = _elements_to_polars(elements_list)
    elements_path = bundle_dir / "rop.parquet"
    elements_df.write_parquet(elements_path, compression="zstd")

    # --- Write rop_embeddings.parquet (embedding sidecar) ---
    accessions = [e.rop_accession or "" for e in elements_list]
    embeddings_df = pl.DataFrame(
        {
            "rop_accession": accessions,
            "embedding": [v.tolist() for v in vectors],
        }
    )
    embeddings_path = bundle_dir / "rop_embeddings.parquet"
    embeddings_df.write_parquet(embeddings_path, compression="zstd")

    # --- Build and write FAISS index ---
    index = build_faiss_index(vectors, use_ivf=use_ivf)
    faiss_path = bundle_dir / "rop.faiss"
    save_faiss_index(index, faiss_path)

    # --- Write manifest ---
    manifest = _build_manifest(
        bundle_version=bundle_version,
        elements=elements_list,
        source_versions=source_versions or DEFAULT_SOURCE_VERSIONS,
        embedding_model=config.model_name,
        embedding_dim=int(vectors.shape[1]),
    )
    manifest_path = bundle_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    # --- Write per-bundle README ---
    readme_path = bundle_dir / "README.md"
    readme_path.write_text(_render_bundle_readme(manifest))

    # --- Write LICENSE summary ---
    license_path = bundle_dir / "LICENSE.md"
    license_path.write_text(_render_bundle_license(manifest))

    return bundle_dir


def _elements_to_polars(elements: list[RoPElement]) -> pl.DataFrame:
    """Convert RoPElement list to a Polars DataFrame, omitting embedding column."""
    rows = []
    for e in elements:
        d = e.model_dump(mode="json", exclude={"embedding"})
        # Polars handles UUIDs as strings cleanly
        for key in ("id", "schema_id", "replaced_by_rop_id"):
            if d.get(key) is not None:
                d[key] = str(d[key])
        if d.get("equivalent_rop_ids"):
            d["equivalent_rop_ids"] = [str(x) for x in d["equivalent_rop_ids"]]
        rows.append(d)
    return pl.DataFrame(rows)


def _build_manifest(
    bundle_version: str,
    elements: list[RoPElement],
    source_versions: dict[str, str],
    embedding_model: str,
    embedding_dim: int,
) -> dict:
    # Compute a single rolled-up content hash for the whole bundle —
    # the hash of all per-row content hashes, sorted
    all_hashes = sorted(e.content_hash or "" for e in elements)
    rollup = hashlib.sha256("\n".join(all_hashes).encode("utf-8")).hexdigest()

    return {
        "bundle_version": bundle_version,
        "bundle_built_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(elements),
        "source_versions": source_versions,
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
        "anchor_tier_versions": ANCHOR_TIER_VERSIONS,
        "content_hash_summary": f"sha256:{rollup}",
    }


def _render_bundle_readme(manifest: dict) -> str:
    src_lines = "\n".join(
        f"- **{k}**: {v}" for k, v in sorted(manifest["source_versions"].items())
    )
    return f"""# RoP Bundle v{manifest['bundle_version']}

Built at: `{manifest['bundle_built_at']}`
Rows: {manifest['row_count']:,}
Embedding model: `{manifest['embedding_model']}` ({manifest['embedding_dim']}-dim)
Content hash summary: `{manifest['content_hash_summary']}`

## Source authority versions

{src_lines}

## Files

- `rop.parquet` — element rows (no embedding column)
- `rop_embeddings.parquet` — `rop_accession → embedding[]`
- `rop.faiss` — FAISS index over normalized embeddings, inner-product metric
- `manifest.json` — machine-readable bundle metadata
- `LICENSE.md` — license summary

## Usage

```python
import polars as pl, faiss
from rop.embed import encode_query, search

elements = pl.read_parquet("rop.parquet")
embeddings = pl.read_parquet("rop_embeddings.parquet")
index = faiss.read_index("rop.faiss")

q = encode_query("dopaminergic neuron substantia nigra")
scores, idx = search(index, q, k=5)
```

See https://github.com/datatecnica/rop for the full specification.
"""


def _render_bundle_license(manifest: dict) -> str:
    src_lines = "\n".join(
        f"- {k} (version pinned to `{v}`): see upstream license at the source authority"
        for k, v in sorted(manifest["source_versions"].items())
    )
    return f"""# License Summary

## RoP code, schema, and anchor definitions

AGPLv3 (code), CC-BY-NC-4.0 (documentation, anchors, bundle metadata).

## Source authority content

This bundle references concepts from the following source authorities. The
`source_code` and `source_url` fields point back to authoritative definitions.
Re-use of source authority content is subject to upstream license terms:

{src_lines}

LOINC, HPO, OMIM, and Mondo permit free redistribution. NACC, NINDS-CDE,
PhenX, and CDISC content is referenced by code only; users intending to
incorporate definitions or values from these authorities should consult
upstream licenses and DUAs.

## Citation

If you use this bundle in a publication, please cite the bundle DOI from
Zenodo (per-release) and the methods paper (https://doi.org/<TBD>).
"""
