"""
Aggregates results.json (after manual grading of answer_correct) into summary
numbers for the methodology/eval page. Run after run_eval.py and after manually
filling in answer_correct: true/false for each result.
"""
import json
from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def main():
    results = json.loads(RESULTS_PATH.read_text())

    ungraded = [r for r in results if r["answer_correct"] is None]
    if ungraded:
        print(f"warning: {len(ungraded)}/{len(results)} results have not been manually graded yet")

    graded = [r for r in results if r["answer_correct"] is not None]
    pop_with_router = [r for r in results if r["router_path_correct"] is not None]

    summary = {
        "total_questions": len(results),
        "graded_questions": len(graded),
        "answer_accuracy": round(sum(1 for r in graded if r["answer_correct"]) / len(graded), 3) if graded else None,
        "router_accuracy": round(sum(1 for r in pop_with_router if r["router_path_correct"]) / len(pop_with_router), 3) if pop_with_router else None,
        "by_mode": {},
    }

    for mode in ("patient", "population"):
        mode_graded = [r for r in graded if r["mode"] == mode]
        if mode_graded:
            summary["by_mode"][mode] = {
                "n": len(mode_graded),
                "answer_accuracy": round(sum(1 for r in mode_graded if r["answer_correct"]) / len(mode_graded), 3),
            }

    out_path = RESULTS_PATH.parent / "summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
