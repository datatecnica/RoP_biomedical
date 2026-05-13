#!/usr/bin/env python3
"""Package final v2026.04 release bundle.

Combines:
- v2026.04_elements.parquet (1,328,973 rows, 151 MB)
- v2026.04_embeddings.npy (1,328,973 × 768, 3.9 GB)
- v2026.04_embeddings.faiss (IVF4096 index, ~3.9 GB)

Output:
- dist/rop_v2026.04/
  - elements.parquet
  - embeddings.npy
  - embeddings.faiss
  - manifest.json (SHA256 checksums + metadata)
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
import shutil

def sha256_file(filepath):
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def format_size(bytes_size):
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def main():
    # Source files
    elements_src = Path("data/final/v2026.04_elements.parquet")
    embeddings_src = Path("data/final/v2026.04_embeddings.npy")
    faiss_src = Path("data/final/v2026.04_embeddings.faiss")

    # Output directory
    output_dir = Path("dist/rop_v2026.04")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Destination files
    elements_dst = output_dir / "elements.parquet"
    embeddings_dst = output_dir / "embeddings.npy"
    faiss_dst = output_dir / "embeddings.faiss"
    manifest_dst = output_dir / "manifest.json"

    print("=" * 70)
    print("RoP v2026.04 FINAL BUNDLE PACKAGING")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print()

    # Check source files exist
    print("🔍 Checking source files...")
    for src_path, name in [(elements_src, "elements.parquet"),
                            (embeddings_src, "embeddings.npy"),
                            (faiss_src, "embeddings.faiss")]:
        if not src_path.exists():
            print(f"   ❌ ERROR: {name} not found at {src_path}")
            return 1
        size_mb = src_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ {name}: {size_mb:.1f} MB")
    print()

    # Copy files
    print("📦 Copying files to bundle directory...")

    print(f"   Copying {elements_src.name}...")
    shutil.copy2(elements_src, elements_dst)
    print(f"   ✅ {elements_dst.name}")

    print(f"   Copying {embeddings_src.name}...")
    shutil.copy2(embeddings_src, embeddings_dst)
    print(f"   ✅ {embeddings_dst.name}")

    print(f"   Copying {faiss_src.name}...")
    shutil.copy2(faiss_src, faiss_dst)
    print(f"   ✅ {faiss_dst.name}")
    print()

    # Calculate SHA256 checksums
    print("🔐 Calculating SHA256 checksums...")
    files_metadata = {}

    for filepath, name in [(elements_dst, "elements.parquet"),
                           (embeddings_dst, "embeddings.npy"),
                           (faiss_dst, "embeddings.faiss")]:
        print(f"   Hashing {name}...")
        sha256 = sha256_file(filepath)
        size_bytes = filepath.stat().st_size

        files_metadata[name] = {
            "size_bytes": size_bytes,
            "size_human": format_size(size_bytes),
            "sha256": sha256
        }
        print(f"   ✅ {sha256[:16]}...")
    print()

    # Calculate total size
    total_size_bytes = sum(f["size_bytes"] for f in files_metadata.values())
    total_size_human = format_size(total_size_bytes)

    # Create manifest
    print("📄 Creating manifest.json...")
    manifest = {
        "version": "v2026.04",
        "created": datetime.utcnow().isoformat() + "Z",
        "description": "RoP v2026.04 - 1.33M deduplicated biomedical CDEs with SapBERT embeddings + 9 boutique collections",
        "authors": ["Dan Vitale", "Pietro Marini", "Michael A. Nalls"],
        "organization": "DataTecnica",
        "license": "AGPLv3 (code) + CC-BY-NC-4.0 (data)",
        "total_size_bytes": total_size_bytes,
        "total_size_human": total_size_human,
        "statistics": {
            "total_cdes": 1328973,
            "foundation_cdes": 1326063,
            "boutique_cdes": 2910,
            "boutique_collections": 9,
            "collections": ["ASAP", "Answer-ALS", "BDR", "BDSA", "CARD-PathND",
                           "GP2", "NACC", "PARTS", "SEA-AD"],
            "embedding_model": "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
            "embedding_dim": 768,
            "faiss_index_type": "IVF4096,Flat",
            "faiss_metric": "INNER_PRODUCT"
        },
        "sources": [
            "OMOP/Athena", "HPO", "Mondo", "NINDS-CDE", "CDISC",
            "PhenX", "BIDS", "DICOM", "DUO", "Boutique Collections"
        ],
        "files": files_metadata
    }

    with open(manifest_dst, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"   ✅ {manifest_dst.name}")
    print()

    # Summary
    print("=" * 70)
    print("✅ FINAL BUNDLE PACKAGED SUCCESSFULLY")
    print("=" * 70)
    print(f"Version:      v2026.04")
    print(f"Total CDEs:   1,328,973")
    print(f"  Foundation: 1,326,063")
    print(f"  Boutique:       2,910 (9 collections)")
    print()
    print(f"Collections:  ASAP, Answer-ALS, BDR, BDSA, CARD-PathND,")
    print(f"              GP2, NACC, PARTS, SEA-AD")
    print()
    print(f"Bundle size:  {total_size_human}")
    print(f"Location:     {output_dir}/")
    print()
    print("Files:")
    for name, meta in files_metadata.items():
        print(f"  {name:25s} {meta['size_human']:>10s}  {meta['sha256'][:16]}...")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    exit(main())
