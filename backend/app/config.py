import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

# NOTE: do not force HF_HUB_OFFLINE here. It's tempting (avoids a network
# round-trip to huggingface.co on every cold start when the model is already
# cached locally), but on a fresh deploy host there is no local cache yet --
# forcing offline mode then makes the app fail hard on startup instead of just
# downloading the model once. Learned this the hard way on the first Render
# deploy (OSError: couldn't connect to huggingface.co, couldn't find cached
# files). The startup preload in app/main.py already ensures this download
# happens once at boot, not per-request, so the cost is a slightly slower
# first deploy rather than a broken one.

DB_PATH = ROOT / "data" / "processed" / "clinical.db"
INDEX_DIR = ROOT / "data" / "index"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
TOP_K = 8
