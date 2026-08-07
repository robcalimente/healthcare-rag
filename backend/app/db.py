import sqlite3
from functools import lru_cache

from app.config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_patients():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, first_name, last_name, birthdate, gender, city, state "
        "FROM patients WHERE deathdate IS NULL ORDER BY last_name, first_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient(patient_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


@lru_cache(maxsize=1)
def distinct_condition_names():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT description FROM conditions").fetchall()
    conn.close()
    return [r["description"] for r in rows]


@lru_cache(maxsize=1)
def distinct_medication_names():
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT description FROM medications").fetchall()
    conn.close()
    return [r["description"] for r in rows]


def total_patient_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM patients WHERE deathdate IS NULL").fetchone()[0]
    conn.close()
    return n


def count_patients_with_condition(description: str):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(DISTINCT patient_id) FROM conditions WHERE description = ?",
        (description,),
    ).fetchone()[0]
    conn.close()
    return n


def count_patients_on_medication(description: str):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(DISTINCT patient_id) FROM medications WHERE description = ? AND stop IS NULL",
        (description,),
    ).fetchone()[0]
    conn.close()
    return n
