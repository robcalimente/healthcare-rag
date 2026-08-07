"""
Generates a ground-truth eval set of ~40 Q&A pairs, mixed patient-scoped and
population-scoped, where every answer is computed directly from clinical.db --
independent of the RAG pipeline being evaluated, so it's a real ground truth,
not a guess.

Output: backend/eval/eval_set.json
"""
import json
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "processed" / "clinical.db"
OUT_PATH = Path(__file__).resolve().parent / "eval_set.json"

random.seed(42)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_patient_scoped_questions(conn, n=20):
    patients = conn.execute(
        "SELECT id, first_name, last_name FROM patients WHERE deathdate IS NULL ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()

    questions = []
    for p in patients:
        pid, name = p["id"], f"{p['first_name']} {p['last_name']}"

        meds = conn.execute(
            "SELECT description FROM medications WHERE patient_id = ? AND stop IS NULL",
            (pid,),
        ).fetchall()
        med_list = sorted(set(m["description"] for m in meds))
        questions.append({
            "mode": "patient",
            "patient_id": pid,
            "patient_name": name,
            "question": f"What medications is {name} currently on?",
            "expected_answer_type": "medication_list",
            "expected": med_list,
        })

        conds = conn.execute(
            "SELECT description FROM conditions WHERE patient_id = ?",
            (pid,),
        ).fetchall()
        cond_list = sorted(set(c["description"] for c in conds))
        questions.append({
            "mode": "patient",
            "patient_id": pid,
            "patient_name": name,
            "question": f"What conditions has {name} been diagnosed with?",
            "expected_answer_type": "condition_list",
            "expected": cond_list,
        })

    return questions[:n]


def build_population_scoped_questions(conn, n=20):
    total = conn.execute("SELECT COUNT(*) FROM patients WHERE deathdate IS NULL").fetchone()[0]

    top_conditions = conn.execute(
        "SELECT description, COUNT(DISTINCT patient_id) as n FROM conditions "
        "GROUP BY description ORDER BY n DESC LIMIT 15"
    ).fetchall()
    top_medications = conn.execute(
        "SELECT description, COUNT(DISTINCT patient_id) as n FROM medications "
        "WHERE stop IS NULL GROUP BY description ORDER BY n DESC LIMIT 15"
    ).fetchall()

    questions = []
    for c in random.sample(top_conditions, min(10, len(top_conditions))):
        pct = round(100 * c["n"] / total, 1) if total else 0.0
        questions.append({
            "mode": "population",
            "question": f"How many patients have {c['description'].split(' (')[0]}?",
            "expected_answer_type": "count",
            "expected": {"n": c["n"], "total": total},
        })
        questions.append({
            "mode": "population",
            "question": f"What percentage of patients have {c['description'].split(' (')[0]}?",
            "expected_answer_type": "percentage",
            "expected": {"n": c["n"], "total": total, "percentage": pct},
        })

    for m in random.sample(top_medications, min(5, len(top_medications))):
        pct = round(100 * m["n"] / total, 1) if total else 0.0
        questions.append({
            "mode": "population",
            "question": f"How many patients are taking {m['description'].split(' (')[0]}?",
            "expected_answer_type": "count",
            "expected": {"n": m["n"], "total": total},
        })

    return questions[:n]


def main():
    conn = get_conn()
    questions = build_patient_scoped_questions(conn, n=20) + build_population_scoped_questions(conn, n=20)
    conn.close()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
    print(f"wrote {len(questions)} eval questions to {OUT_PATH}")


if __name__ == "__main__":
    main()
