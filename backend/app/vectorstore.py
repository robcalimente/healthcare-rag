import json
from functools import lru_cache
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL, INDEX_DIR, TOP_K


@lru_cache(maxsize=1)
def _model():
    return SentenceTransformer(EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _embeddings():
    return np.load(INDEX_DIR / "embeddings.npy")


@lru_cache(maxsize=1)
def _metadata():
    rows = []
    with open(INDEX_DIR / "metadata.jsonl", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


@lru_cache(maxsize=1)
def _patient_index_map():
    """patient_id -> list of row indices into _metadata()/_embeddings()"""
    mapping: dict[str, list[int]] = {}
    for i, m in enumerate(_metadata()):
        mapping.setdefault(m["patient_id"], []).append(i)
    return mapping


def _embed_query(question: str) -> np.ndarray:
    vec = _model().encode([question], normalize_embeddings=True)[0]
    return vec.astype("float32")


def retrieve(question: str, patient_id: Optional[str] = None, top_k: int = TOP_K):
    """
    Brute-force cosine similarity (normalized vectors -> dot product) over the
    full corpus, or a patient-filtered subset. At ~93k chunks this is a few
    milliseconds either way -- no ANN index needed at this scale.
    """
    query_vec = _embed_query(question)
    metadata = _metadata()

    if patient_id:
        row_indices = _patient_index_map().get(patient_id, [])
        if not row_indices:
            return []
        candidate_embeddings = _embeddings()[row_indices]
    else:
        row_indices = range(len(metadata))
        candidate_embeddings = _embeddings()

    scores = candidate_embeddings @ query_vec
    top_local = np.argsort(-scores)[:top_k]

    hits = []
    for local_idx in top_local:
        global_idx = row_indices[local_idx] if patient_id else local_idx
        m = metadata[global_idx]
        hits.append({**m, "score": round(float(scores[local_idx]), 4)})
    return hits
