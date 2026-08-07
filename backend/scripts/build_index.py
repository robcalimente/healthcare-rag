"""
Embeds chunks.jsonl (produced by prepare_data.py) and persists a raw embeddings
matrix plus a metadata sidecar at data/index/. Run once offline before deploying
the backend -- the backend loads this pre-built index at startup rather than
embedding at request time.

Plain numpy (not Chroma, not a FAISS index structure) was chosen for the deployed
index specifically for its small memory footprint: at ~93k chunks, a brute-force
dot product against a raw float32 matrix is a few milliseconds and needs no
SQLite/HNSW-graph storage overhead, which matters on a free-tier host. A FAISS/ANN
index only pays for itself at much larger corpus sizes than this project has.
"""
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
INDEX_DIR = ROOT / "data" / "index"

BATCH_SIZE = 256


def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    chunks = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    print(f"loaded {len(chunks)} chunks")

    ids = [c["id"] for c in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate chunk ids found -- rerun prepare_data.py")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    dim = model.get_sentence_embedding_dimension()

    all_embeddings = np.zeros((len(chunks), dim), dtype="float32")
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        emb = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        all_embeddings[i : i + len(batch)] = emb
        if (i // BATCH_SIZE) % 20 == 0:
            print(f"embedded {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")

    # normalized vectors -> dot product = cosine similarity, computed directly in
    # vectorstore.py at query time (see module docstring for why no FAISS index)
    np.save(INDEX_DIR / "embeddings.npy", all_embeddings)

    metadata = [
        {
            "id": c["id"],
            "patient_id": c["patient_id"],
            "record_type": c["record_type"],
            "date": c["date"],
            "text": c["text"],
        }
        for c in chunks
    ]
    with open(INDEX_DIR / "metadata.jsonl", "w", encoding="utf-8") as f:
        for m in metadata:
            f.write(json.dumps(m) + "\n")

    print(f"done. index persisted at {INDEX_DIR}")


if __name__ == "__main__":
    main()
