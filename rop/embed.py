"""Embedding pipeline.

Wraps a sentence-transformer model to encode RoP element search_text into
dense vectors, and builds a FAISS index over them for fast approximate
nearest-neighbor retrieval.

The reference model for v2026.04 is BioLORD-2023
(FremyCompany/BioLORD-2023), a 110M-parameter sentence transformer trained
for biomedical concept linking. Locked-in over alternatives (SapBERT,
ClinicalBERT, MedCPT) Monday morning per docs/SPRINT_1.md, evaluated
against the 300-pair eval set in tests/eval_set/.

For domain-agnostic (non-biomedical) deployments, swap to a general-purpose
model like sentence-transformers/all-MiniLM-L6-v2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from rop.schema import RoPElement, compose_search_text


# Recommended models, in order of preference for biomedical use
DEFAULT_MODEL = "cambridgeltl/SapBERT-from-PubMedBERT-fulltext"
DEFAULT_DIM = 768  # SapBERT pooled output is 768-dim; project to 384 if needed
DEFAULT_BATCH_SIZE = 64


@dataclass
class EmbeddingConfig:
    model_name: str = DEFAULT_MODEL
    batch_size: int = DEFAULT_BATCH_SIZE
    normalize: bool = True
    device: str | None = None  # None → auto


def encode_elements(
    elements: Iterable[RoPElement],
    config: EmbeddingConfig | None = None,
) -> np.ndarray:
    """Encode a sequence of RoP elements into an (N, dim) float32 matrix.

    Side effect: populates element.search_text if not already set.
    """
    config = config or EmbeddingConfig()

    # Lazy import — sentence-transformers is heavy and not always installed
    from sentence_transformers import SentenceTransformer

    elements_list = list(elements)
    texts: list[str] = []
    for elem in elements_list:
        if not elem.search_text:
            elem.search_text = compose_search_text(elem)
        texts.append(elem.search_text)

    model = SentenceTransformer(config.model_name, device=config.device)
    vectors = model.encode(
        texts,
        batch_size=config.batch_size,
        convert_to_numpy=True,
        normalize_embeddings=config.normalize,
        show_progress_bar=True,
    )
    return vectors.astype("float32", copy=False)


def build_faiss_index(
    vectors: np.ndarray,
    use_ivf: bool = False,
    ivf_lists: int = 200,
) -> "faiss.Index":  # type: ignore[name-defined]
    """Build a FAISS index over a vector matrix.

    For RoP-scale data (~3M rows), IndexFlatIP is fast enough on a modern
    machine and gives exact results. Set use_ivf=True for larger collections
    where approximate search is acceptable.
    """
    import faiss

    if vectors.dtype != np.float32:
        vectors = vectors.astype("float32", copy=False)

    dim = vectors.shape[1]

    if use_ivf:
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, ivf_lists, faiss.METRIC_INNER_PRODUCT)
        index.train(vectors)
        index.add(vectors)
    else:
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)

    return index


def save_faiss_index(index: "faiss.Index", path: Path | str) -> None:  # type: ignore[name-defined]
    import faiss

    faiss.write_index(index, str(path))


def load_faiss_index(path: Path | str) -> "faiss.Index":  # type: ignore[name-defined]
    import faiss

    return faiss.read_index(str(path))


def search(
    index: "faiss.Index",  # type: ignore[name-defined]
    query_vectors: np.ndarray,
    k: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (scores, indices) for top-k matches.

    Scores are inner products (== cosine when vectors are normalized).
    """
    if query_vectors.dtype != np.float32:
        query_vectors = query_vectors.astype("float32", copy=False)
    if query_vectors.ndim == 1:
        query_vectors = query_vectors.reshape(1, -1)
    return index.search(query_vectors, k)


def encode_query(
    text: str,
    config: EmbeddingConfig | None = None,
) -> np.ndarray:
    """Encode a single string query for retrieval."""
    config = config or EmbeddingConfig()
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(config.model_name, device=config.device)
    vec = model.encode(
        [text],
        convert_to_numpy=True,
        normalize_embeddings=config.normalize,
    )
    return vec.astype("float32", copy=False)
