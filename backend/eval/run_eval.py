"""
Runs the eval set against a live backend (default http://localhost:8000) and writes
results for review. Retrieval quality is scored automatically (does the router path
match expectation, for population mode); answer correctness is left for manual
grading in results.json (grade: null -> fill in 1/0 by hand after reading transcript).

Usage: backend/.venv/bin/python backend/eval/run_eval.py [--base-url http://localhost:8000]
"""
import argparse
import json
import time
from pathlib import Path

import requests

EVAL_SET_PATH = Path(__file__).resolve().parent / "eval_set.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

# Groq free tier caps llama-3.1-8b-instant at 6000 tokens/minute -- running the eval
# set back-to-back can burn through that. Space requests out and retry on 429 rather
# than fail the whole run (this is a test-harness pacing issue, not a production
# concern: real demo traffic won't fire 40 requests/minute).
REQUEST_DELAY_SECONDS = 3


def post_with_retry(url, payload, max_retries=5):
    for attempt in range(max_retries):
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    questions = json.loads(EVAL_SET_PATH.read_text())
    results = []

    for i, q in enumerate(questions):
        payload = {"mode": q["mode"], "question": q["question"]}
        if q["mode"] == "patient":
            payload["patient_id"] = q["patient_id"]

        resp = post_with_retry(f"{args.base_url}/api/chat", payload)
        data = resp.json()

        router_ok = None
        if q["mode"] == "population":
            expected_path = "structured" if q["expected_answer_type"] in ("count", "percentage") else "vector"
            router_ok = data["trace"]["router_path"] == expected_path

        results.append({
            "question": q["question"],
            "mode": q["mode"],
            "expected": q["expected"],
            "expected_answer_type": q["expected_answer_type"],
            "model_answer": data["answer"],
            "router_path": data["trace"]["router_path"],
            "router_reason": data["trace"]["router_reason"],
            "router_path_correct": router_ok,
            "retrieved_record_types": [r["record_type"] for r in data["trace"]["retrieved"]],
            "answer_correct": None,  # fill in manually: true/false, after reading model_answer vs expected
        })
        print(f"[{i+1}/{len(questions)}] {q['question'][:60]}... -> router={data['trace']['router_path']}")

        RESULTS_PATH.write_text(json.dumps(results, indent=2))
        if i < len(questions) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)
    print(f"\nwrote {len(results)} results to {RESULTS_PATH}")
    print("next: manually grade 'answer_correct' for each result, then run score_eval.py")


if __name__ == "__main__":
    main()
