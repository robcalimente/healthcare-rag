from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import db, llm, router as rule_router, vectorstore
from app.schemas import ChatRequest, ChatResponse, ChatTrace, RetrievedChunk

app = FastAPI(title="Healthcare RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def preload():
    """Load the embedding model, vectors, and metadata once at boot rather than
    lazily on the first request -- avoids a slow/cold first request timing out."""
    vectorstore._model()
    vectorstore._embeddings()
    vectorstore._patient_row_indices()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/patients")
def patients():
    return db.list_patients()


def _snippet(text: str, length: int = 220) -> str:
    return text if len(text) <= length else text[:length].rstrip() + "..."


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if req.mode == "patient":
        if not req.patient_id:
            raise HTTPException(400, "patient_id required for patient mode")
        if not db.get_patient(req.patient_id):
            raise HTTPException(404, "patient not found")

        # patient corpora are small (~90 chunks/patient avg) -- retrieve deeper than
        # the population-mode default so "list all X" questions aren't truncated by
        # top_k when a patient has more than 8 relevant records
        hits = vectorstore.retrieve(req.question, patient_id=req.patient_id, top_k=15)
        answer = llm.generate_answer(req.question, hits)
        trace = ChatTrace(
            router_path="vector",
            router_reason="patient mode always uses scoped vector retrieval",
            patient_id=req.patient_id,
            retrieved=[
                RetrievedChunk(
                    id=h["id"], record_type=h["record_type"], date=h["date"],
                    patient_id=h["patient_id"], score=h["score"], snippet=_snippet(h["text"]),
                )
                for h in hits
            ],
            cited_ids=[h["id"] for h in hits],
        )
        return ChatResponse(answer=answer, trace=trace)

    # population mode
    route = rule_router.route_population_question(req.question)

    if route["path"] == "structured":
        answer = llm.generate_structured_answer(req.question, route["result"])
        trace = ChatTrace(
            router_path="structured",
            router_reason=route["reason"],
            retrieved=[],
            cited_ids=[],
            sql=route["sql"],
        )
        return ChatResponse(answer=answer, trace=trace)

    hits = vectorstore.retrieve(req.question, patient_id=None)
    answer = llm.generate_answer(req.question, hits)
    trace = ChatTrace(
        router_path="vector",
        router_reason=route["reason"],
        retrieved=[
            RetrievedChunk(
                id=h["id"], record_type=h["record_type"], date=h["date"],
                patient_id=h["patient_id"], score=h["score"], snippet=_snippet(h["text"]),
            )
            for h in hits
        ],
        cited_ids=[h["id"] for h in hits],
    )
    return ChatResponse(answer=answer, trace=trace)
