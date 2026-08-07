"""
Embeds chunks.jsonl (produced by prepare_data.py) and persists:
  - data/index/embeddings.npy   float16 vector matrix, loaded fully into RAM at
                                 runtime -- this is the only thing that needs to be
                                 (the dot-product search needs the whole matrix)
  - data/index/chunks.db        SQLite table with id/patient_id/record_type/date/text,
                                 rowid matching the embeddings row order. Chunk TEXT
                                 stays on disk and is fetched only for the ~15-25
                                 results actually returned per query.

Earlier version kept a Python list of 92k dicts (with full text) in memory at
runtime alongside the embeddings matrix -- that's what blew past Render free tier's
512MB RAM limit on first deploy. Text doesn't need to be in RAM for search; only
retrieved results need it, and SQLite with an index on patient_id serves that
cheaply without holding the whole corpus resident.
"""
import json
import sqlite3
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

    # float16 halves the in-RAM footprint of the one thing that must stay resident;
    # normalized vectors -> dot product = cosine similarity, precision loss here
    # doesn't meaningfully affect retrieval ranking
    np.save(INDEX_DIR / "embeddings.npy", all_embeddings.astype("float16"))

    db_path = INDEX_DIR / "chunks.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE chunks (
            row_index INTEGER PRIMARY KEY,
            id TEXT,
            patient_id TEXT,
            record_type TEXT,
            date TEXT,
            text TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO chunks VALUES (?,?,?,?,?,?)",
        [
            (i, c["id"], c["patient_id"], c["record_type"], c["date"], c["text"])
            for i, c in enumerate(chunks)
        ],
    )
    conn.execute("CREATE INDEX idx_chunks_patient ON chunks(patient_id)")
    conn.commit()
    conn.close()

    print(f"done. index persisted at {INDEX_DIR}")


if __name__ == "__main__":
    main()
