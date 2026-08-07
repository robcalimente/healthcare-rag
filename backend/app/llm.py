import time

from groq import Groq, RateLimitError

from app.config import GROQ_API_KEY, GROQ_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


SYSTEM_PROMPT = (
    "You are a clinical chart assistant answering questions about SYNTHETIC patient "
    "data (Synthea-generated, not real patients). Answer only using the provided "
    "context records. If the context does not contain the answer, say so plainly -- "
    "do not guess or use outside medical knowledge. Cite the record dates you used. "
    "Keep answers concise.\n\n"
    "Context records are tagged by type: [condition], [medication], [encounter], "
    "[observation_panel], [clinical_note]. For factual questions about what "
    "medications a patient is CURRENTLY on, or what conditions they have been "
    "DIAGNOSED with, treat [medication] and [condition] records as the authoritative "
    "source of truth -- they explicitly state active/stopped status and diagnosis "
    "dates. Do NOT infer current medication or diagnosis status from a "
    "[clinical_note]'s narrative text (e.g. a note's \"Medications\" section "
    "describes what was prescribed as of THAT visit's date, not necessarily what is "
    "active now) -- use notes only for context/narrative, not as the source for "
    "current-status claims. If [medication]/[condition] records for this patient are "
    "empty or absent, say the patient has no such records rather than pulling an "
    "answer from a note."
)


MAX_CHUNK_CHARS = 400  # keeps context small enough for Groq free-tier TPM limits


def _create_with_retry(messages: list[dict], max_tokens: int, max_retries: int = 3):
    """
    Groq's free tier caps llama-3.1-8b-instant at 6000 tokens/minute. A hiring
    manager clicking through the demo quickly (or the eval harness) can hit that --
    retry with backoff instead of surfacing a 500.
    """
    for attempt in range(max_retries):
        try:
            return _get_client().chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens,
            )
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    context_text = "\n\n".join(
        f"[{c['record_type']} | {c['date']}] {c['text'][:MAX_CHUNK_CHARS]}"
        for c in context_chunks
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context records:\n{context_text}\n\nQuestion: {question}",
        },
    ]
    response = _create_with_retry(messages, max_tokens=500)
    return response.choices[0].message.content


def generate_structured_answer(question: str, structured_result: dict) -> str:
    """Answer a counting/aggregate question using the router's SQL result directly."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"A structured database query already computed the exact answer to this "
                f"question. Phrase it as a natural answer, do not recompute or second-guess "
                f"the number.\n\nQuestion: {question}\n\nQuery result: {structured_result}"
            ),
        },
    ]
    response = _create_with_retry(messages, max_tokens=200)
    return response.choices[0].message.content
