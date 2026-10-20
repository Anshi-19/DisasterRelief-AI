import time
from hashlib import sha256

from .retrieval_service import retrieve_documents
from .llm_service import ALLOWED_MODELS, generate_response, query_focus_support


FALLBACK_RESPONSE = (
    "The retrieved knowledge base does not contain enough "
    "information to answer this question."
)

MODEL_LOG_NAMES = {
    "codellama:latest": "CodeLlama",
    "qwen2.5-coder:7b": "Qwen2.5-Coder",
    "deepseek-coder:6.7b": "DeepSeek-Coder",
}


def empty_generation_metrics(model):
    return {
        "answer": FALLBACK_RESPONSE,
        "model": model or "codellama:latest",
        "response_latency": None,
        "prompt_tokens": None,
        "generated_tokens": None,
        "total_tokens": None,
        "throughput": None,
    }


def build_context(results):

    context_parts = []

    for index, result in enumerate(results, start=1):

        metadata = result["metadata"]

        source = (
            f"[SOURCE {index}]\n"
            f"Document: {metadata['document']}\n"
            f"Authority: {metadata['authority']}\n"
            f"Disaster: {metadata['disaster']}\n"
            f"Page(s): {metadata['pages']}\n"
        )

        context_parts.append(
            source
            + "\nCONTENT:\n"
            + result["text"]
            + "\n[END SOURCE]"
        )

    return "\n\n".join(context_parts)


def serialize_sources(results):
    return [
        {
            "document": result["metadata"]["document"],
            "authority": result["metadata"]["authority"],
            "pages": result["metadata"]["pages"],
            "disaster": result["metadata"]["disaster"],
            "distance": result["distance"],
            "text": result["text"],
        }
        for result in results
    ]


def retrieve_context(question, top_k):
    retrieval_start = time.perf_counter()
    results = retrieve_documents(question, top_k=top_k)
    retrieval_latency = round(time.perf_counter() - retrieval_start, 3)
    context = build_context(results) if results else ""
    print(f"[RETRIEVAL] chunks={len(results)}", flush=True)
    return results, context, retrieval_latency


def process_question(question: str, top_k: int = 4, model: str | None = None):

    if not (question or "").strip():
        generation = empty_generation_metrics(model)
        return {
            "question": question,
            "answer": generation["answer"],
            "sources": [],
            "retrieved_context": "",
            "retrieved_chunk_count": 0,
            "retrieval_latency": 0.0,
            "model": generation["model"],
            "metrics": generation,
        }

    results, context, retrieval_latency = retrieve_context(question, top_k)

    if not results:
        generation = empty_generation_metrics(model)
        return {
            "question": question,
            "answer": generation["answer"],
            "sources": [],
            "retrieved_context": "",
            "retrieved_chunk_count": 0,
            "retrieval_latency": retrieval_latency,
            "model": generation["model"],
            "metrics": generation,
        }

    context_is_usable, _, matched_focus = query_focus_support(question, context)
    if context_is_usable:
        print(
            f"[RETRIEVAL] usable_context=true matched_focus={matched_focus}",
            flush=True,
        )
        generation = generate_response(
            question,
            context,
            model=model,
        )
    else:
        print("[RETRIEVAL] usable_context=false", flush=True)
        generation = empty_generation_metrics(model)

    return {
        "question": question,
        "answer": generation["answer"],
        "sources": serialize_sources(results),
        "retrieved_context": context,
        "retrieved_chunk_count": len(results),
        "retrieval_latency": retrieval_latency,
        "model": generation["model"],
        "metrics": generation,
    }


def process_comparison(question: str, top_k: int = 4):
    if not (question or "").strip():
        return {
            "question": question,
            "sources": [],
            "retrieved_context": "",
            "retrieved_chunk_count": 0,
            "retrieval_latency": 0.0,
            "context_hash": sha256(b"").hexdigest(),
            "results": [
                {
                    "model": model,
                    "answer": FALLBACK_RESPONSE,
                    "metrics": empty_generation_metrics(model),
                    "success": True,
                    "error": None,
                }
                for model in sorted(ALLOWED_MODELS)
            ],
        }

    results, context, retrieval_latency = retrieve_context(question, top_k)
    sources = serialize_sources(results)
    context_hash = sha256(context.encode("utf-8")).hexdigest()
    print(f"[COMPARE] Shared retrieval: {len(results)} chunks", flush=True)
    context_is_usable, _, matched_focus = query_focus_support(question, context)
    print(
        f"[COMPARE] Usable context: {context_is_usable}; "
        f"matched focus={matched_focus}",
        flush=True,
    )

    comparison_results = []
    for model in sorted(ALLOWED_MODELS):
        if not results or not context_is_usable:
            generation = empty_generation_metrics(model)
            comparison_results.append(
                {
                    "model": model,
                    "answer": generation["answer"],
                    "metrics": generation,
                    "success": True,
                    "error": None,
                }
            )
            print(
                f"[COMPARE] {MODEL_LOG_NAMES.get(model, model)}: "
                "fallback (no usable retrieved context)",
                flush=True,
            )
            continue

        try:
            generation = generate_response(question, context, model=model)
            comparison_results.append(
                {
                    "model": model,
                    "answer": generation["answer"],
                    "metrics": generation,
                    "success": True,
                    "error": None,
                }
            )
            print(f"[COMPARE] {MODEL_LOG_NAMES.get(model, model)}: success", flush=True)
        except Exception as exc:
            comparison_results.append(
                {
                    "model": model,
                    "answer": "",
                    "metrics": empty_generation_metrics(model),
                    "success": False,
                    "error": str(exc),
                }
            )
            print(
                f"[COMPARE] {MODEL_LOG_NAMES.get(model, model)}: "
                f"failed ({type(exc).__name__})",
                flush=True,
            )

    return {
        "question": question,
        "sources": sources,
        "retrieved_context": context,
        "retrieved_chunk_count": len(results),
        "retrieval_latency": retrieval_latency,
        "context_hash": context_hash,
        "results": comparison_results,
    }
