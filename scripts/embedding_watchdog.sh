#!/bin/bash
# Embedding watchdog - auto-restart on GPU crashes
# Runs until embeddings.npy exists and is complete

set -e

LOG_FILE="embedding_watchdog.log"
CHECKPOINT_FILE="data/foundation/staging/embeddings_checkpoint.npz"
OUTPUT_FILE="data/foundation/staging/embeddings.npy"
SCRIPT="scripts/generate_embeddings_direct.py"

echo "$(date): Watchdog started" | tee -a "$LOG_FILE"

attempt=0
while [ ! -f "$OUTPUT_FILE" ]; do
    attempt=$((attempt + 1))
    echo "$(date): Attempt $attempt - Starting embedding generation" | tee -a "$LOG_FILE"

    if [ -f "$CHECKPOINT_FILE" ]; then
        checkpoint_size=$(stat -f%z "$CHECKPOINT_FILE" 2>/dev/null || stat -c%s "$CHECKPOINT_FILE")
        echo "$(date): Found checkpoint: $(numfmt --to=iec $checkpoint_size)" | tee -a "$LOG_FILE"
    fi

    # Run with auto-restart on failure
    python3 "$SCRIPT" \
        --input data/foundation/staging/dedup_pass1.parquet \
        --output "$OUTPUT_FILE" \
        --batch-size 512 \
        --device cuda \
        --model cambridgeltl/SapBERT-from-PubMedBERT-fulltext \
        2>&1 | tee -a embedding_sapbert_watchdog.txt

    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "$(date): SUCCESS - Embeddings complete!" | tee -a "$LOG_FILE"
        break
    else
        echo "$(date): CRASH detected (exit code $exit_code) - restarting in 10s..." | tee -a "$LOG_FILE"
        sleep 10
    fi
done

echo "$(date): Watchdog finished - embeddings.npy created" | tee -a "$LOG_FILE"
