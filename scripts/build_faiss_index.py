"""Build FAISS index for fast similarity search over RoP embeddings.

Usage:
    python scripts/build_faiss_index.py \\
        --embeddings data/foundation/staging/embeddings.npy \\
        --output data/foundation/staging/embeddings.faiss
"""
import argparse
import logging
import time
from pathlib import Path

import faiss
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("faiss")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embeddings", required=True, help="Input embeddings.npy file")
    parser.add_argument("--output", required=True, help="Output FAISS index file")
    parser.add_argument("--index-type", default="IVF4096,Flat",
                       help="FAISS index type (default: IVF4096,Flat for 1.3M vectors)")
    args = parser.parse_args()

    embeddings_path = Path(args.embeddings)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load embeddings
    logger.info("Loading embeddings from %s", embeddings_path)
    embeddings = np.load(embeddings_path)
    logger.info("Loaded embeddings: shape=%s dtype=%s", embeddings.shape, embeddings.dtype)

    n, d = embeddings.shape
    logger.info("Building FAISS index: %s for %d vectors (dim=%d)", args.index_type, n, d)

    # Build index
    t0 = time.time()

    # Use IndexIVFFlat for large datasets (1M+ vectors)
    # IVF4096 = 4096 Voronoi cells (good for 1-10M vectors)
    quantizer = faiss.IndexFlatIP(d)  # Inner product (cosine for normalized vectors)
    index = faiss.IndexIVFFlat(quantizer, d, 4096, faiss.METRIC_INNER_PRODUCT)

    logger.info("Training index on %d vectors", n)
    index.train(embeddings)

    logger.info("Adding vectors to index")
    index.add(embeddings)

    elapsed = time.time() - t0
    logger.info("Built index in %.1fs", elapsed)

    # Save index
    logger.info("Saving index to %s", output_path)
    faiss.write_index(index, str(output_path))

    # Verify
    index_size_mb = output_path.stat().st_size / 1024**2
    logger.info("Index saved: %.1f MB", index_size_mb)
    logger.info("Index stats: ntotal=%d, nlist=%d", index.ntotal, index.nlist)

    # Quick sanity test
    logger.info("Running sanity test (k=10 neighbors for first vector)")
    index.nprobe = 10  # Search 10 cells (speed/accuracy tradeoff)
    D, I = index.search(embeddings[:1], 10)
    logger.info("  Top neighbor distances: %s", D[0][:5])
    logger.info("  Top neighbor indices: %s", I[0][:5])

    if I[0][0] == 0 and D[0][0] > 0.99:
        logger.info("✅ Sanity test passed (self is top result)")
    else:
        logger.warning("⚠️ Sanity test unexpected: self not top result")

    logger.info("FAISS index build complete")


if __name__ == "__main__":
    main()
