"""Controlled Week 4 multi-model evaluation.

Fairness rules:
- same questions
- same retrieval configuration
- same top_k, temperature, max tokens, prompt structure
- repository questions use disaster_relief_code
- RAG questions use the Week 3 disaster_relief knowledge base
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import requests

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parents[1]))

from eval_config import (
    CODE_CHROMA_DIR,
    CODE_COLLECTION,
    DATASET_FILE,
    EMBEDDING_MODEL,
    EVALUATION_DATE,
    EVALUATION_VERSION,
    MAX_RETRIES,
    MODELS,
    NUM_PREDICT,
    OLLAMA_EMBEDDING_URL,
    OLLAMA_GENERATE_URL,
    PROJECT_ROOT,
    RAW_RESULTS_FILE,
    RAG_CATEGORIES,
    REPOSITORY_CATEGORIES,
    REQUEST_TIMEOUT,
    RESULTS_DIR,
    RETRY_DELAY_SECONDS,
    SYSTEM_INSTRUCTION,
    TEMPERATURE,
    TOP_K,
)
from measure_resources import ResourceSampler, ns_to_seconds, tokens_per_second


def load_dataset():
    with DATASET_FILE.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def generate_embedding(text):
    response = requests.post(
        OLLAMA_EMBEDDING_URL,
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def retrieve_disaster_documents(question):
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from services.retrieval_service import retrieve_documents

    return retrieve_documents(question, top_k=TOP_K)


def retrieve_repository_code(question):
    client = chromadb.PersistentClient(path=str(CODE_CHROMA_DIR))
    collection = client.get_collection(CODE_COLLECTION)
    results = collection.query(
        query_embeddings=[generate_embedding(question)],
        n_results=min(max(TOP_K * 6, 40), collection.count()),
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    candidates = []
    for semantic_rank, (document, metadata, distance) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        metadata = metadata or {}
        candidates.append(
            {
                "text": document,
                "metadata": metadata,
                "distance": distance,
                "_semantic_rank": semantic_rank,
                "_hybrid_score": repository_relevance_score(
                    question, document, metadata, semantic_rank
                ),
            }
        )

    candidates.sort(
        key=lambda item: (-item["_hybrid_score"], item["_semantic_rank"])
    )
    output = []
    per_file = defaultdict(int)
    per_file_limit = 1 if asks_which_file(question) else 2
    for item in candidates:
        file_path = item["metadata"].get("file_path", "unknown")
        if per_file[file_path] >= per_file_limit:
            continue
        output.append(
            {
                "text": item["text"],
                "metadata": item["metadata"],
                "distance": item["distance"],
            }
        )
        per_file[file_path] += 1
        if len(output) >= TOP_K:
            break
    return output


TOKEN_STOP_WORDS = {
    "a", "an", "and", "are", "as", "be", "contains", "could", "does", "for",
    "from", "how", "if", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "user", "what", "when", "where", "which", "why", "with",
}


def tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9_./-]+", (text or "").lower())
        if len(token) > 2 and token not in TOKEN_STOP_WORDS
    }


def python_import_from_metadata(metadata):
    explicit = (metadata or {}).get("python_import")
    if explicit:
        return explicit
    file_path = (metadata or {}).get("file_path") or ""
    symbol = (metadata or {}).get("symbol") or ""
    path = Path(file_path)
    if path.suffix != ".py":
        return ""
    module = ".".join(path.with_suffix("").parts)
    if symbol and symbol not in {"<module>", "code", "unknown"}:
        return f"from {module} import {symbol}"
    return f"import {module}"


def repository_relevance_score(question, document, metadata, semantic_rank):
    """Hybrid semantic/lexical ranker over indexed repository evidence."""
    question_lower = (question or "").lower()
    question_terms = tokens(question)
    file_path = (metadata.get("file_path") or "").lower()
    symbol = (metadata.get("symbol") or "").lower()
    code_terms = tokens(document)
    path_terms = tokens(file_path.replace("/", " ").replace("_", " "))
    symbol_terms = tokens(symbol.replace("_", " "))
    import_terms = tokens(python_import_from_metadata(metadata))

    lexical_coverage = (
        len(question_terms & code_terms) / max(len(question_terms), 1)
    )
    identity_hits = len(question_terms & (path_terms | symbol_terms | import_terms))
    score = (0.55 / (semantic_rank + 3)) + (0.45 * lexical_coverage)
    score += min(identity_hits * 0.16, 0.64)

    mentioned_files = re.findall(
        r"[a-zA-Z0-9_./-]+\.(?:py|jsx|js|ts|tsx)", question
    )
    if any(file_path.endswith(name.lower()) for name in mentioned_files):
        score += 1.0

    if symbol and symbol in question_lower.replace("-", "_"):
        score += 0.55
    for term in question_terms:
        if len(term) < 6:
            continue
        stem = term[:6]
        if stem in symbol or stem in file_path:
            score += 0.3

    asks_for_live_path = not any(
        marker in question_lower for marker in ("legacy", "older", "backend/rag")
    )
    execution_path = metadata.get("execution_path")
    if asks_for_live_path and (
        execution_path == "live"
        or file_path.startswith("backend/services/")
        or file_path.startswith("frontend/")
        or file_path == "backend/main.py"
    ):
        score += 0.55
    if asks_for_live_path and (
        execution_path == "legacy" or file_path.startswith("backend/rag/")
    ):
        score -= 0.45
    return score


def asks_which_file(question):
    blob = (question or "").lower()
    return bool(
        re.search(
            r"which file|what file|where is .* defined|where is .* implemented",
            blob,
        )
    )


def retrieval_source_for(row):
    category = row["category"].strip()
    if category in RAG_CATEGORIES:
        return "disaster_knowledge_base"
    if category in REPOSITORY_CATEGORIES:
        return "repository"
    return "repository"


def evidence_index(results, repository=False):
    lines = ["EVIDENCE INDEX (most relevant first):"]
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        if repository:
            import_hint = python_import_from_metadata(metadata)
            suffix = f" | {import_hint}" if import_hint else ""
            lines.append(
                f"{index}. [{metadata.get('execution_path', 'unspecified')}] "
                f"{metadata.get('file_path', 'unknown')} :: "
                f"{metadata.get('symbol', 'unknown')}{suffix}"
            )
        else:
            lines.append(
                f"{index}. {metadata.get('document')} | "
                f"p.{metadata.get('pages')} | {metadata.get('disaster')}"
            )
    return "\n".join(lines)


def build_context(results, repository=False):
    # Preserve retrieval rank so the strongest evidence stays first.
    parts = [evidence_index(results, repository=repository), ""]
    for index, result in enumerate(results, start=1):
        metadata = result["metadata"] or {}
        if repository:
            import_hint = python_import_from_metadata(metadata)
            header = (
                f"[SOURCE {index}]\n"
                f"File: {metadata.get('file_path', 'unknown')}\n"
                f"Language: {metadata.get('language', 'unknown')}\n"
                f"Symbol: {metadata.get('symbol', 'unknown')}\n"
                f"Code type: {metadata.get('code_type', 'unknown')}\n"
                f"Execution path: {metadata.get('execution_path', 'unspecified')}\n"
            )
            if import_hint:
                header += f"PYTHON IMPORT: {import_hint}\n"
        else:
            header = (
                f"[SOURCE {index}]\n"
                f"Document: {metadata.get('document')}\n"
                f"Authority: {metadata.get('authority')}\n"
                f"Disaster: {metadata.get('disaster')}\n"
                f"Page(s): {metadata.get('pages')}\n"
            )
        parts.append(
            header + "\nCONTENT:\n" + result["text"] + "\n[END SOURCE]"
        )
    return "\n\n".join(parts)


def task_guidance(category):
    guidance = {
        "Code Retrieval": (
            "Start with File: <live path>. Name the live function. Mention legacy "
            "paths only to say they are not the active application path."
        ),
        "Explanation": (
            "Use headings Answer / Key points / Evidence only if useful. Name every "
            "live file, function, threshold, and fallback needed to cover the question."
        ),
        "Dependency Understanding": (
            "Trace the live call chain with exact files and functions; include each "
            "intermediate component."
        ),
        "Bug Analysis": (
            "State the cause, the pipeline consequence, and the fallback/answer risk "
            "from the implementation shown."
        ),
        "Code Generation": (
            "Return one complete Python code block with no placeholders. Copy the "
            "exact live PYTHON IMPORT line for the function named in the question "
            "(backend/services/X.py means from backend.services.X import symbol). "
            "Do not invent modules. The code must run from the repository root."
        ),
        "Refactoring": (
            "Refactor the live function shown. Preserve every existing field and "
            "behavior; briefly say what stays the same."
        ),
        "RAG": (
            "Give the precise requested fact first. Prefer the named measure, "
            "facility, or purpose from the matching section over a nearby design "
            "detail. Keep exact purpose wording and numbers when present. Then add "
            "short key points and evidence only if they help."
        ),
    }
    return guidance.get(category, "Answer every part using exact retrieved evidence.")


def serialize_sources(results, repository=False):
    sources = []
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"] or {}
        if repository:
            sources.append(
                {
                    "rank": rank,
                    "file_path": metadata.get("file_path"),
                    "symbol": metadata.get("symbol"),
                    "language": metadata.get("language"),
                    "code_type": metadata.get("code_type"),
                    "execution_path": metadata.get("execution_path"),
                    "python_import": python_import_from_metadata(metadata),
                    "distance": result.get("distance"),
                    "text": result.get("text"),
                }
            )
        else:
            sources.append(
                {
                    "rank": rank,
                    "document": metadata.get("document"),
                    "authority": metadata.get("authority"),
                    "disaster": metadata.get("disaster"),
                    "pages": metadata.get("pages"),
                    "distance": result.get("distance"),
                    "text": result.get("text"),
                }
            )
    return sources


FALLBACK_RESPONSE = (
    "The retrieved knowledge base does not contain enough information "
    "to answer this question."
)


def context_is_sufficient(question, context, repository):
    if not (context or "").strip():
        return False
    if repository:
        return True
    question_terms = tokens(question)
    context_terms = tokens(context)
    return bool(question_terms & context_terms)


def call_ollama(question, context, model, category):
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"TASK TYPE: {category}\n"
        f"RESPONSE REQUIREMENT: {task_guidance(category)}\n\n"
        "RETRIEVED CONTEXT:\n\n"
        f"{context}\n\n"
        "END CONTEXT\n\n"
        f"USER QUESTION:\n{question}\n\n"
        "ANSWER:\n"
    )
    sampler = ResourceSampler()
    sampler.start()
    start = time.perf_counter()
    last_error = None
    response = None
    attempts = 0

    for attempt in range(MAX_RETRIES + 1):
        attempts = attempt + 1
        try:
            response = requests.post(
                OLLAMA_GENERATE_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": TEMPERATURE,
                        "num_predict": NUM_PREDICT,
                    },
                },
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code >= 500:
                raise requests.HTTPError(
                    f"{response.status_code} Server Error: {response.reason} "
                    f"for url: {OLLAMA_GENERATE_URL}",
                    response=response,
                )
            response.raise_for_status()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                break

    latency = time.perf_counter() - start
    resource_summary = sampler.stop()

    if last_error is not None:
        status_code = None
        body = None
        if isinstance(last_error, requests.HTTPError) and last_error.response is not None:
            status_code = last_error.response.status_code
            body = last_error.response.text[:2000]
        return {
            "success": False,
            "answer": None,
            "error": str(last_error),
            "http_status": status_code,
            "error_body": body,
            "attempts": attempts,
            "latency_seconds": round(latency, 3),
            "resource_summary": resource_summary,
            "prompt_eval_count": None,
            "eval_count": None,
            "total_duration": None,
            "load_duration": None,
            "prompt_eval_duration": None,
            "eval_duration": None,
        }

    data = response.json()
    return {
        "success": True,
        "answer": (data.get("response") or "").strip(),
        "error": None,
        "http_status": response.status_code,
        "error_body": None,
        "attempts": attempts,
        "latency_seconds": round(latency, 3),
        "resource_summary": resource_summary,
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "total_duration": data.get("total_duration"),
        "load_duration": data.get("load_duration"),
        "prompt_eval_duration": data.get("prompt_eval_duration"),
        "eval_duration": data.get("eval_duration"),
    }


def save_results(records):
    RAW_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_existing_results():
    if not RAW_RESULTS_FILE.exists():
        return []
    try:
        records = json.loads(RAW_RESULTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(records, list):
        return []
    return [
        record
        for record in records
        if record.get("evaluation_version") == EVALUATION_VERSION
    ]


def result_key(record):
    return (record.get("model"), record.get("question_id"))


def main():
    dataset = load_dataset()
    only_ids = [
        item.strip()
        for item in os.environ.get("WEEK4_QUESTION_IDS", "").split(",")
        if item.strip()
    ]
    if only_ids:
        dataset = [row for row in dataset if row["id"] in only_ids]
    print("=" * 70)
    print("DisasterRelief-AI Week 4 controlled evaluation")
    print("=" * 70)
    print(f"Questions: {len(dataset)}")
    print(f"Models: {MODELS}")
    print(f"Expected experiments: {len(dataset) * len(MODELS)}")
    print(f"top_k={TOP_K} temperature={TEMPERATURE} num_predict={NUM_PREDICT}")
    print(f"embedding={EMBEDDING_MODEL}")
    print(f"version={EVALUATION_VERSION}")

    all_results = load_existing_results()
    completed = {result_key(record) for record in all_results}
    if completed:
        print(f"Resuming: {len(completed)} completed experiments will be skipped.")
    timestamp = datetime.now(timezone.utc).isoformat()

    for index, row in enumerate(dataset, start=1):
        question_id = row["id"]
        question = row["question"]
        source = retrieval_source_for(row)
        repository = source == "repository"

        print(f"\n[{index}/{len(dataset)}] {question_id} {row['category']}")
        print(f"Retrieval: {source}")

        retrieval_start = time.perf_counter()
        retrieval_error = None
        try:
            if repository:
                retrieved = retrieve_repository_code(question)
            else:
                retrieved = retrieve_disaster_documents(question)
        except Exception as exc:
            retrieval_error = str(exc)
            retrieved = []
            print(f"  RETRIEVAL ERROR: {exc}")

        retrieval_latency = round(time.perf_counter() - retrieval_start, 3)
        context = (
            build_context(retrieved, repository=repository) if retrieved else ""
        )
        sources = serialize_sources(retrieved, repository=repository)
        answerable = context_is_sufficient(question, context, repository)
        print(
            f"  chunks={len(retrieved)} retrieval_latency={retrieval_latency}s "
            f"answerable={answerable}"
        )

        for model in MODELS:
            if (model, question_id) in completed:
                print(f"  {model} skip (already completed)")
                continue
            print(f"  {model} ...", flush=True)
            if not answerable:
                generation = {
                    "success": True,
                    "answer": FALLBACK_RESPONSE,
                    "error": None,
                    "http_status": None,
                    "error_body": None,
                    "attempts": 0,
                    "latency_seconds": 0.0,
                    "resource_summary": {
                        "sample_count": 0,
                        "mean_ollama_rss_mb": None,
                        "max_ollama_rss_mb": None,
                        "mean_ollama_cpu_percent": None,
                        "max_ollama_cpu_percent": None,
                    },
                    "prompt_eval_count": None,
                    "eval_count": None,
                    "total_duration": None,
                    "load_duration": None,
                    "prompt_eval_duration": None,
                    "eval_duration": None,
                }
            else:
                generation = call_ollama(
                    question, context, model, category=row["category"]
                )
            prompt_tokens = generation["prompt_eval_count"]
            generated_tokens = generation["eval_count"]
            total_tokens = None
            if prompt_tokens is not None and generated_tokens is not None:
                total_tokens = prompt_tokens + generated_tokens

            record = {
                "evaluation_version": EVALUATION_VERSION,
                "evaluation_date": EVALUATION_DATE,
                "timestamp": timestamp,
                "model": model,
                "question_id": question_id,
                "category": row["category"],
                "question": question,
                "answer": generation["answer"],
                "retrieved_context": context,
                "retrieved_sources": sources,
                "retrieved_chunk_count": len(retrieved),
                "retrieval_latency": retrieval_latency,
                "response_latency": generation["latency_seconds"],
                "prompt_tokens": prompt_tokens,
                "generated_tokens": generated_tokens,
                "total_tokens": total_tokens,
                "generation_duration": ns_to_seconds(generation["eval_duration"]),
                "throughput": tokens_per_second(
                    generated_tokens, generation["eval_duration"]
                ),
                "model_load_duration": ns_to_seconds(generation["load_duration"]),
                "prompt_eval_duration": ns_to_seconds(
                    generation["prompt_eval_duration"]
                ),
                "success": generation["success"],
                "error": generation["error"],
                "http_status": generation["http_status"],
                "error_body": generation["error_body"],
                "attempts": generation["attempts"],
                "retrieval_source": source,
                "retrieval_error": retrieval_error,
                "embedding_model": EMBEDDING_MODEL,
                "top_k": TOP_K,
                "temperature": TEMPERATURE,
                "num_predict": NUM_PREDICT,
                "resource_summary": generation["resource_summary"],
                "context_answerable": answerable,
            }
            all_results.append(record)
            save_results(all_results)
            status = "ok" if generation["success"] else "FAIL"
            print(
                f"    {status} {generation['latency_seconds']:.2f}s "
                f"attempts={generation['attempts']}"
            )

    successful = sum(1 for r in all_results if r["success"])
    failed = len(all_results) - successful
    print("\n" + "=" * 70)
    print(f"Done. records={len(all_results)} success={successful} failed={failed}")
    print(f"Saved {RAW_RESULTS_FILE}")


if __name__ == "__main__":
    main()
