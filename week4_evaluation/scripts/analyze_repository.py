"""Exercise 6: repository-level multi-file understanding evaluation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean

from eval_config import (
    DATASET_FILE,
    PROJECT_ROOT,
    QUALITY_SCORES_FILE,
    RAW_RESULTS_FILE,
    REPOSITORY_EVAL_FILE,
    RESULTS_DIR,
    RETRIEVAL_METRICS_FILE,
)

REPO_QUESTION_IDS = [
    "E01",
    "CR01",
    "CR02",
    "CR03",
    "CR04",
    "D01",
    "D02",
    "D03",
    "D04",
    "B04",
    "RF04",
    "CG04",
]


def load_dataset():
    with DATASET_FILE.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def split_files(value):
    return [part.strip() for part in value.split(";") if part.strip()]


def mentioned_files(answer, expected):
    blob = (answer or "").lower()
    hits = []
    for path in expected:
        name = Path(path).name.lower()
        if path.lower() in blob or name in blob:
            hits.append(path)
    return hits


def dependency_score(question_id, answer):
    blob = (answer or "").lower()
    checks = {
        "E01": [["app.jsx"], ["/api/chat"], ["process_question"], ["retrieve_documents"], ["generate_response"]],
        "D01": [["app.jsx"], ["/api/chat"], ["process_question"], ["retrieve_documents"], ["build_context"], ["generate_response"]],
        "D02": [["generate_embedding"], ["chroma", "vector"]],
        "D03": [["build_context"], ["generate_response"]],
        "D04": [["embedding_service"], ["retrieval"]],
        "B04": [["retriev"], ["fallback", "llm", "context"]],
        "RF04": [["llm_model", "model"], ["temperature", "num_predict", "config"]],
        "CR01": [["main.py"]],
        "CR02": [["retrieval_service.py"]],
        "CR03": [["llm_service.py"]],
        "CR04": [["embedding_service.py"]],
        "CG04": [["build_context"]],
    }
    groups = checks.get(question_id, [])
    if not groups:
        return None, "no dependency rubric for this item"
    hits = 0
    for group in groups:
        if any(term in blob for term in group):
            hits += 1
    score = round(hits / len(groups), 4)
    return score, f"matched {hits}/{len(groups)} relationship checks"


def evaluate_record(record, row, retrieval, quality):
    expected = split_files(row.get("relevant_files", ""))
    identified = mentioned_files(record.get("answer"), expected)
    file_score = round(len(identified) / len(expected), 4) if expected else None
    dep_score, dep_note = dependency_score(record["question_id"], record.get("answer"))
    overall_parts = [part for part in [file_score, dep_score, quality.get("correctness") if quality else None] if part is not None]
    overall = round(mean(overall_parts), 4) if overall_parts else None
    return {
        "question": record["question"],
        "question_id": record["question_id"],
        "model": record["model"],
        "expected_files": expected,
        "retrieved_files": (retrieval or {}).get("retrieved_files") or [
            source.get("file_path")
            for source in (record.get("retrieved_sources") or [])
            if source.get("file_path")
        ],
        "identified_files_in_answer": identified,
        "model_answer": record.get("answer"),
        "file_identification_score": file_score,
        "dependency_reasoning_score": dep_score,
        "dependency_note": dep_note,
        "quality_correctness": quality.get("correctness") if quality else None,
        "overall_score": overall,
        "success": record.get("success"),
        "pipeline_reference": {
            "frontend": "frontend/src/App.jsx analyzeSituation()",
            "api": "backend/main.py chat() POST /api/chat",
            "orchestration": "backend/services/orchestration_service.py process_question()",
            "retrieval": "backend/services/retrieval_service.py retrieve_documents()",
            "context": "backend/services/orchestration_service.py build_context()",
            "generation": "backend/services/llm_service.py generate_response()",
            "llm": "Ollama POST /api/generate model=codellama:latest in the live app",
            "no_results": "process_question returns FALLBACK_RESPONSE without calling generate_response",
        },
    }


def aggregate(rows):
    by_model = {}
    for row in rows:
        by_model.setdefault(row["model"], []).append(row)
    summary = {}
    for model, group in by_model.items():
        usable = [item for item in group if item["overall_score"] is not None]
        summary[model] = {
            "n": len(group),
            "mean_file_identification_score": round(
                mean(item["file_identification_score"] for item in usable if item["file_identification_score"] is not None),
                4,
            )
            if usable
            else None,
            "mean_dependency_reasoning_score": round(
                mean(
                    item["dependency_reasoning_score"]
                    for item in usable
                    if item["dependency_reasoning_score"] is not None
                ),
                4,
            )
            if usable
            else None,
            "mean_overall_score": round(mean(item["overall_score"] for item in usable), 4)
            if usable
            else None,
        }
    return summary


def main():
    dataset = load_dataset()
    records = json.loads(RAW_RESULTS_FILE.read_text(encoding="utf-8"))
    quality = {
        (item["model"], item["question_id"]): item
        for item in json.loads(QUALITY_SCORES_FILE.read_text(encoding="utf-8"))["per_question"]
    }
    retrieval = {
        (item["model"], item["question_id"]): item
        for item in json.loads(RETRIEVAL_METRICS_FILE.read_text(encoding="utf-8"))["per_question"]
    }
    selected = [
        record
        for record in records
        if record.get("question_id") in REPO_QUESTION_IDS
    ]
    rows = [
        evaluate_record(
            record,
            dataset[record["question_id"]],
            retrieval.get((record["model"], record["question_id"])),
            quality.get((record["model"], record["question_id"])),
        )
        for record in selected
    ]
    output = {
        "project_root": str(PROJECT_ROOT),
        "questions_evaluated": REPO_QUESTION_IDS,
        "per_question": rows,
        "aggregates": aggregate(rows),
        "actual_call_graph": [
            "frontend/src/App.jsx analyzeSituation() POST http://127.0.0.1:8000/api/chat",
            "backend/main.py chat(ChatRequest) -> process_question(message, top_k=8)",
            "orchestration_service.process_question -> retrieve_documents",
            "retrieval_service.retrieve_documents -> detect_disaster + generate_embedding + Chroma collection disaster_relief",
            "if no results: return FALLBACK_RESPONSE",
            "else build_context -> generate_response -> Ollama /api/generate",
        ],
    }
    REPOSITORY_EVAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPOSITORY_EVAL_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {REPOSITORY_EVAL_FILE} ({len(rows)} rows)")
    for model, values in output["aggregates"].items():
        print(f"{model}: overall={values['mean_overall_score']}")


if __name__ == "__main__":
    main()
