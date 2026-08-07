import sqlite3
from functools import lru_cache
from typing import Optional

import numpy as np
from fastembed import TextEmbedding

from app.config import EMBEDDING_MODEL, INDEX_DIR, TOP_K


@lru_cache(maxsize=1)
def _model():
    return TextEmbedding(model_name=EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def _embeddings():
    # keep as float16 in memory -- numpy's dot product promotes to float32 for the
    # computation transiently, but the resident array stays at half the size.
    # (upcasting here with .astype("float32") would defeat the point: it allocates
    # a permanent full-size float32 copy, not just a per-query working array.)
    return np.load(INDEX_DIR / "embeddings.npy")


def _db_conn():
    # sqlite3 connections aren't guaranteed thread-safe to share across FastAPI's
    # threadpool workers -- open one per call rather than caching a single instance
    return sqlite3.connect(INDEX_DIR / "chunks.db")


@lru_cache(maxsize=1)
def _patient_row_indices():
    """patient_id -> list of row indices into _embeddings(). Small (just ints +
    patient_id strings), fine to cache in memory unlike the full chunk text."""
    conn = _db_conn()
    rows = conn.execute("SELECT row_index, patient_id FROM chunks").fetchall()
    conn.close()
    mapping: dict[str, list[int]] = {}
    for row_index, patient_id in rows:
        mapping.setdefault(patient_id, []).append(row_index)
    return mapping


def _fetch_chunk_rows(row_indices: list[int]) -> dict[int, dict]:
    if not row_indices:
        return {}
    conn = _db_conn()
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(row_indices))
    rows = conn.execute(
        f"SELECT row_index, id, patient_id, record_type, date, text FROM chunks "
        f"WHERE row_index IN ({placeholders})",
        row_indices,
    ).fetchall()
    conn.close()
    return {r["row_index"]: dict(r) for r in rows}


def _embed_query(question: str) -> np.ndarray:
    # query_embed applies the model's recommended query-side instruction prefix
    # (BGE models are trained to expect this on queries, not on indexed documents)
    vec = next(_model().query_embed([question]))
    vec = vec / np.linalg.norm(vec)
    return vec.astype("float32")


def retrieve(question: str, patient_id: Optional[str] = None, top_k: int = TOP_K):
    """
    Brute-force cosine similarity (normalized vectors -> dot product) over the
    full corpus, or a patient-filtered subset. At ~93k chunks this is a few
    milliseconds either way -- no ANN index needed at this scale. Chunk text is
    fetched from SQLite only for the top_k results, not held in RAM for the
    whole corpus.
    """
    query_vec = _embed_query(question)
    embeddings = _embeddings()

    if patient_id:
        row_indices = _patient_row_indices().get(patient_id, [])
        if not row_indices:
            return []
        candidate_embeddings = embeddings[row_indices]
    else:
        row_indices = list(range(embeddings.shape[0]))
        candidate_embeddings = embeddings

    scores = candidate_embeddings @ query_vec
    top_local = np.argsort(-scores)[:top_k]
    top_global_indices = [row_indices[i] for i in top_local]

    chunk_rows = _fetch_chunk_rows(top_global_indices)

    hits = []
    for local_idx, global_idx in zip(top_local, top_global_indices):
        row = chunk_rows.get(global_idx)
        if row is None:
            continue
        hits.append({**row, "score": round(float(scores[local_idx]), 4)})
    return hits
