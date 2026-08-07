"""
Deterministic, rule-based router for population-mode questions.

Vector similarity search is good at "what patterns exist" but bad at exact counts --
it retrieves *relevant* records, not *all* matching records. So any question that's
really asking for a count/percentage gets routed to a real SQL aggregate query over
the structured Synthea tables instead. Everything else goes to vector RAG.

Deliberately not an LLM call: this routing decision is shown to the user in the
retrieval trace panel, and a rule is easier to audit/explain than "the model decided."
"""
import re

from app import db

COUNT_PATTERNS = [
    r"\bhow many\b",
    r"\bwhat percentage\b",
    r"\bwhat percent\b",
    r"\bcount of\b",
    r"\bnumber of patients\b",
]

MEDICATION_HINTS = ["medication", "med ", "meds", "drug", "taking", "prescribed", "on "]
CONDITION_HINTS = ["condition", "diagnos", "disease", "disorder", "have "]

STRIP_PARENS = re.compile(r"\s*\([^)]*\)\s*$")
EXTRACT_AFTER = re.compile(
    r"(?:have|with|diagnosed with|on|taking|prescribed)\s+(.+?)(?:\?|$)", re.IGNORECASE
)


def is_count_question(question: str) -> bool:
    q = question.lower()
    return any(re.search(p, q) for p in COUNT_PATTERNS)


def _candidate_phrase(question: str) -> str:
    m = EXTRACT_AFTER.search(question)
    phrase = m.group(1) if m else question
    return phrase.strip().rstrip("?.").lower()


def _best_match(candidate: str, names: list[str]) -> str | None:
    """
    Tiered matching, most confident first:
      1. exact match
      2. stripped name starts with "candidate " (word-boundary prefix) -- e.g.
         candidate "diabetes" matches "diabetes mellitus type 2", not
         "prediabetes" (doesn't start with "diabetes") and not a complication
         name like "...due to type II diabetes mellitus" (contains it mid-string).
      3. candidate starts with "stripped " (user gave a longer phrase than the
         condition name)
      4. last resort: substring anywhere, shortest wins
    Within a tier, shortest stripped name wins (prefer the more generic/direct
    condition over an overly specific complication that happens to match too).
    """
    if not candidate:
        return None

    tiers: list[list[tuple[int, str]]] = [[], [], [], []]
    for name in names:
        stripped = STRIP_PARENS.sub("", name).strip().lower()
        if not stripped:
            continue
        if candidate == stripped:
            return name
        if stripped.startswith(candidate + " "):
            tiers[1].append((len(stripped), name))
        elif candidate.startswith(stripped + " "):
            tiers[2].append((len(stripped), name))
        elif candidate in stripped or stripped in candidate:
            tiers[3].append((len(stripped), name))

    for tier in tiers[1:]:
        if tier:
            tier.sort(key=lambda x: x[0])
            return tier[0][1]
    return None


def route_population_question(question: str) -> dict:
    """Returns a trace dict describing which path was chosen and why."""
    if not is_count_question(question):
        return {"path": "vector", "reason": "no counting/aggregate pattern matched"}

    q_lower = question.lower()
    candidate = _candidate_phrase(question)

    domain = "either"
    if any(h in q_lower for h in MEDICATION_HINTS):
        domain = "medication"
    elif any(h in q_lower for h in CONDITION_HINTS):
        domain = "condition"

    condition_match = _best_match(candidate, db.distinct_condition_names()) if domain in ("condition", "either") else None
    medication_match = _best_match(candidate, db.distinct_medication_names()) if domain in ("medication", "either") else None

    if not condition_match and not medication_match and domain != "either":
        # domain heuristic (e.g. the word "medication" appearing inside a condition
        # name like "Medication review due") pointed at the wrong table -- retry
        # unrestricted before giving up on a structured answer
        condition_match = _best_match(candidate, db.distinct_condition_names())
        medication_match = _best_match(candidate, db.distinct_medication_names())

    if not condition_match and not medication_match:
        return {
            "path": "vector",
            "reason": f"counting pattern matched, but no known condition/medication matched phrase '{candidate}' -- falling back to vector RAG",
        }

    is_percentage = "percentage" in q_lower or "percent" in q_lower
    total = db.total_patient_count()

    if condition_match:
        n = db.count_patients_with_condition(condition_match)
        sql = f"SELECT COUNT(DISTINCT patient_id) FROM conditions WHERE description = '{condition_match}'"
        entity_type, entity = "condition", condition_match
    else:
        n = db.count_patients_on_medication(medication_match)
        sql = f"SELECT COUNT(DISTINCT patient_id) FROM medications WHERE description = '{medication_match}' AND stop IS NULL"
        entity_type, entity = "medication", medication_match

    result = {"n": n, "total": total}
    if is_percentage:
        result["percentage"] = round(100 * n / total, 1) if total else 0.0

    return {
        "path": "structured",
        "reason": f"matched counting pattern, routed to structured query on {entity_type} '{entity}'",
        "sql": sql,
        "entity_type": entity_type,
        "entity": entity,
        "result": result,
    }
