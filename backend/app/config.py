import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

# The embedding model is already cached locally from the indexing run --
# skip sentence-transformers' hub-update check, which otherwise blocks on a
# network round-trip to huggingface.co on every cold start
os.environ.setdefault("HF_HUB_OFFLINE", "1")

DB_PATH = ROOT / "data" / "processed" / "clinical.db"
INDEX_DIR = ROOT / "data" / "index"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K = 8
