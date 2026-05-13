"""Generate embeddings using SapBERT biomedical model via transformers.

Default model: cambridgeltl/SapBERT-from-PubMedBERT-fulltext (v2026.04 decision).
Uses direct transformers import to bypass torchvision dependency issues.

BioLORD-2023 evaluated (+2% MedSTS) but deferred to v2026.07 due to RTX 4080
GPU instability. SapBERT provides stable 8-10hr runtime with proven biomedical
performance (MedSTS 86.3).

Usage:
    python scripts/generate_embeddings_direct.py \\
        --input data/foundation/staging/dedup_pass1.parquet \\
        --output data/foundation/staging/embeddings.npy \\
        --batch-size 512 \\
        --device cuda
"""
import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch

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


def mean_pooling(model_output, attention_mask):
    """Mean pooling - take attention mask into account for correct averaging."""
    token_embeddings = model_output[0]  # First element is last_hidden_state
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input parquet file")
    parser.add_argument("--output", required=True, help="Output numpy embeddings file (.npy)")
    parser.add_argument("--model", default="cambridgeltl/SapBERT-from-PubMedBERT-fulltext")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default=None, help="cuda or cpu (auto-detect if not specified)")
    args = parser.parse_args()

    # Determine device
    if args.device:
        device = torch.device(args.device)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)

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

    # Load model and tokenizer directly from transformers
    logger.info("Loading model %s", args.model)
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModel.from_pretrained(args.model)
    model = model.to(device)
    model.eval()
    logger.info("Model loaded on device: %s", device)

    # Check for existing checkpoint
    checkpoint_path = output_path.parent / f"{output_path.stem}_checkpoint.npz"
    start_idx = 0
    all_embeddings = []

    if checkpoint_path.exists():
        logger.info("Found checkpoint at %s, resuming...", checkpoint_path)
        checkpoint = np.load(checkpoint_path)
        all_embeddings = [checkpoint['embeddings']]
        start_idx = checkpoint['last_idx']
        logger.info("Resuming from batch %d", start_idx // args.batch_size)

    # Encode in batches
    logger.info("Encoding %d texts (batch_size=%d)", len(texts), args.batch_size)
    t0 = time.time()

    with torch.no_grad():
        for i in range(start_idx, len(texts), args.batch_size):
            batch_texts = texts[i:i + args.batch_size]

            # Tokenize
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            encoded = {k: v.to(device) for k, v in encoded.items()}

            # Get embeddings
            model_output = model(**encoded)
            embeddings = mean_pooling(model_output, encoded["attention_mask"])

            # Normalize
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

            # Move to CPU and convert to numpy
            all_embeddings.append(embeddings.cpu().numpy())

            batch_num = i // args.batch_size + 1
            total_batches = (len(texts) + args.batch_size - 1) // args.batch_size

            if batch_num % 100 == 0:
                logger.info("Processed %d/%d batches", batch_num, total_batches)

                # Save checkpoint every 100 batches
                partial_embeddings = np.vstack(all_embeddings)
                np.savez_compressed(
                    checkpoint_path,
                    embeddings=partial_embeddings,
                    last_idx=i + args.batch_size
                )
                logger.info("Checkpoint saved: %d elements", len(partial_embeddings))

    # Concatenate all batches
    embeddings = np.vstack(all_embeddings)
    elapsed = time.time() - t0
    logger.info("Encoded %d texts in %.1fs (%.0f texts/sec)",
                len(texts), elapsed, len(texts) / elapsed)

    # Save final output
    logger.info("Saving embeddings to %s", output_path)
    np.save(output_path, embeddings)
    logger.info("Saved embeddings: shape=%s dtype=%s", embeddings.shape, embeddings.dtype)

    # Clean up checkpoint
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("Checkpoint removed")


if __name__ == "__main__":
    main()
