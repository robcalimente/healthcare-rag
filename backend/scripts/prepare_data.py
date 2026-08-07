"""
Filters raw Synthea output down to the last N years per patient, and produces:
  - data/processed/clinical.db          SQLite store for structured/counting queries
  - data/processed/chunks.jsonl         Retrievable text chunks for the vector index

Run once after generating Synthea data, before build_index.py.
"""
import csv
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data" / "synthea_output"
OUT = Path(__file__).resolve().parents[2] / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

YEARS_OF_HISTORY = 5
CUTOFF = datetime.utcnow() - timedelta(days=365 * YEARS_OF_HISTORY)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(s):
    if not s:
        return None
    return datetime.strptime(s[:10], "%Y-%m-%d")


def load_csv(name):
    with open(RAW / "csv" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_sqlite(patients, conditions, medications, encounters):
    db_path = OUT / "clinical.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE patients (
            id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
            birthdate TEXT, deathdate TEXT, gender TEXT,
            race TEXT, ethnicity TEXT, city TEXT, state TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (p["Id"], p["FIRST"], p["LAST"], p["BIRTHDATE"], p["DEATHDATE"] or None,
             p["GENDER"], p["RACE"], p["ETHNICITY"], p["CITY"], p["STATE"])
            for p in patients
        ],
    )

    cur.execute("""
        CREATE TABLE conditions (
            patient_id TEXT, encounter_id TEXT, start TEXT, stop TEXT, description TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO conditions VALUES (?,?,?,?,?)",
        [
            (c["PATIENT"], c["ENCOUNTER"], c["START"], c["STOP"] or None, c["DESCRIPTION"])
            for c in conditions
        ],
    )

    cur.execute("""
        CREATE TABLE medications (
            patient_id TEXT, encounter_id TEXT, start TEXT, stop TEXT, description TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO medications VALUES (?,?,?,?,?)",
        [
            (m["PATIENT"], m["ENCOUNTER"], m["START"], m["STOP"] or None, m["DESCRIPTION"])
            for m in medications
        ],
    )

    cur.execute("""
        CREATE TABLE encounters (
            id TEXT PRIMARY KEY, patient_id TEXT, start TEXT, stop TEXT,
            class TEXT, description TEXT, reason TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO encounters VALUES (?,?,?,?,?,?,?)",
        [
            (e["Id"], e["PATIENT"], e["START"], e["STOP"],
             e["ENCOUNTERCLASS"], e["DESCRIPTION"], e["REASONDESCRIPTION"] or None)
            for e in encounters
        ],
    )

    conn.commit()
    conn.close()
    print(f"wrote {db_path}")


def iter_observations_recent():
    """Stream observations.csv, yield only rows within the cutoff (file is 135MB)."""
    with open(RAW / "csv" / "observations.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = parse_date(row["DATE"])
            if d and d >= CUTOFF:
                yield row


def build_observation_chunks():
    """One chunk per (patient, encounter) summarizing that visit's labs/vitals."""
    panels = {}
    for row in iter_observations_recent():
        key = (row["PATIENT"], row["ENCOUNTER"])
        panels.setdefault(key, {"date": row["DATE"][:10], "items": []})
        val = row["VALUE"]
        units = row["UNITS"]
        panels[key]["items"].append(f"{row['DESCRIPTION']}: {val} {units}".strip())

    chunks = []
    for (patient_id, encounter_id), data in panels.items():
        text = f"Labs/vitals from visit on {data['date']}: " + "; ".join(data["items"])
        chunks.append({
            "id": f"obs-{patient_id}-{encounter_id}",
            "patient_id": patient_id,
            "record_type": "observation_panel",
            "date": data["date"],
            "text": text,
        })
    return chunks


def build_note_chunks():
    chunks = []
    for path in (RAW / "notes").glob("*.txt"):
        # filename: First_Last_<uuid>.txt -- patient id is the uuid
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.txt$", path.name)
        if not m:
            continue
        patient_id = m.group(1)
        text = path.read_text(encoding="utf-8")

        lines = text.split("\n")
        sections = []
        current_date = None
        current_lines = []
        for line in lines:
            if DATE_RE.match(line.strip()):
                if current_date and current_lines:
                    sections.append((current_date, "\n".join(current_lines).strip()))
                current_date = line.strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_date and current_lines:
            sections.append((current_date, "\n".join(current_lines).strip()))

        for i, (date_str, body) in enumerate(sections):
            d = parse_date(date_str)
            if not d or d < CUTOFF or not body:
                continue
            chunks.append({
                "id": f"note-{patient_id}-{i}",
                "patient_id": patient_id,
                "record_type": "clinical_note",
                "date": date_str,
                "text": f"Clinical note from visit on {date_str}:\n{body}",
            })
    return chunks


def main():
    print(f"cutoff date: {CUTOFF.date()} (last {YEARS_OF_HISTORY} years)")

    patients = load_csv("patients.csv")
    conditions = [c for c in load_csv("conditions.csv") if (parse_date(c["START"]) or CUTOFF) >= CUTOFF]
    medications = [m for m in load_csv("medications.csv") if (parse_date(m["START"]) or CUTOFF) >= CUTOFF]
    encounters = [e for e in load_csv("encounters.csv") if (parse_date(e["START"]) or CUTOFF) >= CUTOFF]
    print(f"patients={len(patients)} conditions={len(conditions)} medications={len(medications)} encounters={len(encounters)}")

    build_sqlite(patients, conditions, medications, encounters)

    chunks = []
    for i, c in enumerate(conditions):
        chunks.append({
            "id": f"cond-{i}-{c['PATIENT']}-{c['CODE']}",
            "patient_id": c["PATIENT"],
            "record_type": "condition",
            "date": c["START"],
            "text": f"Condition diagnosed {c['START']}: {c['DESCRIPTION']}" + (f", resolved {c['STOP']}" if c["STOP"] else ", ongoing"),
        })
    for i, m in enumerate(medications):
        chunks.append({
            "id": f"med-{i}-{m['PATIENT']}-{m['CODE']}",
            "patient_id": m["PATIENT"],
            "record_type": "medication",
            "date": m["START"][:10],
            "text": f"Medication started {m['START'][:10]}: {m['DESCRIPTION']}" + (f", stopped {m['STOP'][:10]}" if m["STOP"] else ", currently active") + (f" (for {m['REASONDESCRIPTION']})" if m.get("REASONDESCRIPTION") else ""),
        })
    for e in encounters:
        chunks.append({
            "id": f"enc-{e['Id']}",
            "patient_id": e["PATIENT"],
            "record_type": "encounter",
            "date": e["START"][:10],
            "text": f"{e['ENCOUNTERCLASS'].title()} encounter on {e['START'][:10]}: {e['DESCRIPTION']}" + (f", reason: {e['REASONDESCRIPTION']}" if e["REASONDESCRIPTION"] else ""),
        })

    obs_chunks = build_observation_chunks()
    print(f"observation panel chunks: {len(obs_chunks)}")
    chunks.extend(obs_chunks)

    note_chunks = build_note_chunks()
    print(f"clinical note chunks: {len(note_chunks)}")
    chunks.extend(note_chunks)

    seen = set()
    dupes = 0
    for c in chunks:
        if c["id"] in seen:
            dupes += 1
            c["id"] = f"{c['id']}-dup{dupes}"
        seen.add(c["id"])
    if dupes:
        print(f"warning: found and disambiguated {dupes} duplicate chunk ids")

    out_path = OUT / "chunks.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    print(f"wrote {len(chunks)} total chunks to {out_path}")


if __name__ == "__main__":
    main()
