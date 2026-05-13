"""Package RoP v2026.04-foundation bundle.

Creates final bundle structure with manifest, checksums, and metadata.

Usage:
    python scripts/package_bundle.py \\
        --version 2026.04-foundation \\
        --staging data/foundation/staging \\
        --output dist/rop_v2026.04-foundation
"""
import argparse
import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("bundle")


def sha256_file(filepath):
    """Calculate SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Bundle version (e.g., 2026.04-foundation)")
    parser.add_argument("--staging", required=True, help="Staging directory with dedup/embeddings/faiss")
    parser.add_argument("--output", required=True, help="Output bundle directory")
    args = parser.parse_args()

    staging_dir = Path(args.staging)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Packaging RoP %s bundle", args.version)

    # Copy core files
    files_to_package = [
        ("dedup_pass1.parquet", "elements.parquet"),
        ("embeddings.npy", "embeddings.npy"),
        ("embeddings.faiss", "embeddings.faiss"),
    ]

    manifest = {
        "version": args.version,
        "created": datetime.utcnow().isoformat() + "Z",
        "description": "RoP v2026.04 foundation bundle - 1.32M deduplicated biomedical CDEs with SapBERT embeddings",
        "license": "AGPLv3 (code) + CC-BY-NC-4.0 (data)",
        "files": {}
    }

    for src_name, dest_name in files_to_package:
        src_path = staging_dir / src_name
        dest_path = output_dir / dest_name

        if not src_path.exists():
            logger.error("Missing required file: %s", src_path)
            raise FileNotFoundError(f"Required file not found: {src_path}")

        logger.info("Copying %s -> %s", src_path.name, dest_path.name)
        shutil.copy2(src_path, dest_path)

        # Calculate hash
        logger.info("  Calculating SHA256...")
        file_hash = sha256_file(dest_path)
        file_size = dest_path.stat().st_size

        manifest["files"][dest_name] = {
            "sha256": file_hash,
            "size_bytes": file_size,
            "size_mb": round(file_size / 1024**2, 1)
        }

        logger.info("  %s (%.1f MB, sha256: %s...)", dest_name,
                   file_size / 1024**2, file_hash[:16])

    # Write manifest
    manifest_path = output_dir / "manifest.json"
    logger.info("Writing manifest to %s", manifest_path)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Summary
    total_size_gb = sum(f["size_bytes"] for f in manifest["files"].values()) / 1024**3
    logger.info("")
    logger.info("✅ Bundle packaged successfully")
    logger.info("   Version: %s", args.version)
    logger.info("   Location: %s", output_dir.absolute())
    logger.info("   Files: %d", len(manifest["files"]))
    logger.info("   Total size: %.2f GB", total_size_gb)
    logger.info("")
    logger.info("Bundle contents:")
    for name, info in manifest["files"].items():
        logger.info("  - %s (%.1f MB)", name, info["size_mb"])


if __name__ == "__main__":
    main()
