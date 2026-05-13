"""Generate embeddings for all elements in dedup_pass1.parquet.

Usage:
    python scripts/generate_embeddings.py \\
        --input data/foundation/staging/dedup_pass1.parquet \\
        --output data/foundation/staging/embeddings.npy \\
        --model cambridgeltl/SapBERT-from-PubMedBERT-fulltext
"""
import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("embed")


def compose_search_text(row) -> str:
    """Build search text from element row (description + source + collection)."""
    parts = [row["description"]]

    src = row["source_authority"]
    if row.get("source_code"):
        parts.append(f"{src} {row['source_code']}")
    else:
        parts.append(src)

    if row.get("collection"):
        parts.append(row["collection"])

    return " ".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input parquet file")
    parser.add_argument("--output", required=True, help="Output numpy embeddings file (.npy)")
    parser.add_argument("--model", default="cambridgeltl/SapBERT-from-PubMedBERT-fulltext")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default=None, help="cuda or cpu (auto-detect if not specified)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading elements from %s", input_path)
    table = pq.read_table(input_path)
    df = table.to_pandas()
    logger.info("Loaded %d elements", len(df))

    # Build search texts
    logger.info("Building search texts")
    texts = [compose_search_text(row) for _, row in df.iterrows()]
    logger.info("Built %d search texts", len(texts))

    # Load model
    logger.info("Loading model %s", args.model)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model, device=args.device)
    logger.info("Model loaded on device: %s", model.device)

    # Encode
    logger.info("Encoding %d texts (batch_size=%d)", len(texts), args.batch_size)
    t0 = time.time()
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    elapsed = time.time() - t0
    logger.info("Encoded %d texts in %.1fs (%.0f texts/sec)",
                len(texts), elapsed, len(texts) / elapsed)

    # Save
    logger.info("Saving embeddings to %s", output_path)
    np.save(output_path, embeddings)
    logger.info("Saved embeddings: shape=%s dtype=%s", embeddings.shape, embeddings.dtype)


if __name__ == "__main__":
    main()
