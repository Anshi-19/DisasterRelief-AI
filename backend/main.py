from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.llm_service import ALLOWED_MODELS, LLM_MODEL, resolve_model
from services.orchestration_service import process_comparison, process_question


app = FastAPI(
    title="DisasterRelief AI",
    description="Evidence-Grounded Disaster Relief Assistance Navigator",
    version="1.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None


class CompareRequest(BaseModel):
    message: str


@app.get("/")
def home():

    return {
        "message": "DisasterRelief AI API is running"
    }


@app.post("/api/chat")
def chat(request: ChatRequest):

    try:
        model = resolve_model(request.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = process_question(
        request.message,
        top_k=8,
        model=model,
    )

    metrics = result.get("metrics") or {}

    return {
        "response": result["answer"],
        "sources": result["sources"],
        "model": result.get("model") or model or LLM_MODEL,
        "retrieved_context": result.get("retrieved_context") or "",
        "retrieved_chunk_count": result.get("retrieved_chunk_count", len(result["sources"])),
        "retrieval_latency": result.get("retrieval_latency"),
        "response_latency": metrics.get("response_latency"),
        "prompt_tokens": metrics.get("prompt_tokens"),
        "generated_tokens": metrics.get("generated_tokens"),
        "total_tokens": metrics.get("total_tokens"),
        "throughput": metrics.get("throughput"),
        "allowed_models": sorted(ALLOWED_MODELS),
    }


@app.post("/api/chat/compare")
def compare_models(request: CompareRequest):
    comparison = process_comparison(request.message, top_k=8)

    return {
        "question": comparison["question"],
        "sources": comparison["sources"],
        "retrieved_context": comparison["retrieved_context"],
        "retrieved_chunk_count": comparison["retrieved_chunk_count"],
        "retrieval_latency": comparison["retrieval_latency"],
        "context_hash": comparison["context_hash"],
        "results": [
            {
                "response": item["answer"],
                "model": item["model"],
                "response_latency": item["metrics"].get("response_latency"),
                "prompt_tokens": item["metrics"].get("prompt_tokens"),
                "generated_tokens": item["metrics"].get("generated_tokens"),
                "total_tokens": item["metrics"].get("total_tokens"),
                "throughput": item["metrics"].get("throughput"),
                "success": item["success"],
                "error": item["error"],
            }
            for item in comparison["results"]
        ],
    }
