"""
Embeds chunks.jsonl (produced by prepare_data.py) and persists:
  - data/index/embeddings.npy   float16 vector matrix, loaded fully into RAM at
                                 runtime -- this is the only thing that needs to be
                                 (the dot-product search needs the whole matrix)
  - data/index/chunks.db        SQLite table with id/patient_id/record_type/date/text,
                                 rowid matching the embeddings row order. Chunk TEXT
                                 stays on disk and is fetched only for the ~15-25
                                 results actually returned per query.

Earlier versions used sentence-transformers (PyTorch-backed) for embeddings. That
worked locally but its baseline memory footprint (PyTorch import + model, several
hundred MB) turned out to exceed Render free tier's 512MB limit on its own, before
even accounting for the corpus data -- confirmed by the app still OOMing after the
corpus-side fixes below (SQLite text storage, float16, 100-patient sample) brought
the data footprint down to a few MB. Switched to fastembed (ONNX Runtime, no
PyTorch) for a much lighter runtime dependency.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

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

    model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    dim = 384

    # BGE-small's max sequence length is 512 tokens (~2000 chars). Some clinical
    # note chunks run past 9000 chars -- without truncation, batching a few very
    # long texts with many short ones blows up attention cost quadratically with
    # the longest sequence in the batch, which is what caused build_index.py to
    # spike to several GB of RAM and stall. Embedding quality doesn't need the
    # full text anyway; the semantic gist is captured well within this cap.
    EMBED_TEXT_MAX_CHARS = 1000

    all_embeddings = np.zeros((len(chunks), dim), dtype="float32")
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"][:EMBED_TEXT_MAX_CHARS] for c in batch]
        # parallel=1 disables fastembed's automatic multiprocessing, which
        # otherwise spawns extra worker processes -- each loading its own full
        # copy of the ONNX model -- and was the actual cause of multi-GB memory
        # growth during indexing (not the text length, though that's capped too)
        emb = np.array(list(model.embed(texts, parallel=1)))
        # normalize explicitly -- don't rely on the model's own output already
        # being unit-length, since retrieve() treats dot product as cosine similarity
        emb = emb / np.linalg.norm(emb, axis=1, keepdims=True)
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
