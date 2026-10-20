"""Exercise 5: RAG pipeline case studies from actual evaluation traces."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from eval_config import (
    DATASET_FILE,
    QUALITY_SCORES_FILE,
    RAG_CASE_STUDIES_FILE,
    RAW_RESULTS_FILE,
    RESULTS_DIR,
    RETRIEVAL_METRICS_FILE,
)

PREFERRED_IDS = ["RG01", "RG02", "RG03", "RG04", "E02"]
FACT_TERMS = {
    "RG01": ["tent", "water", "sanitation", "transport", "communication", "medical", "relief"],
    "RG02": ["tent", "water", "sanitation", "transport", "communication", "medical", "relief"],
    "RG03": ["cyclone shelter", "shelter", "1.3 times", "wind speed"],
    "RG04": ["long-term", "recovery", "reconstruction"],
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_dataset():
    with DATASET_FILE.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def classify_behavior(case):
    hit = case["retrieval"]["hit_at_k"]
    correctness = case["scores"]["correctness"]
    hallucination = case["scores"]["hallucination"]
    missed = case["missed_information"]
    irrelevant = case["irrelevant_information"]
    refusal = "does not contain enough information" in (case["model_response"] or "").lower()
    fact_in_context = bool(case["key_relevant_information"]) and not missed

    if hit and correctness == 1.0 and hallucination == 0:
        return "strong retrieval → correct grounded response"
    if hit and fact_in_context and correctness is not None and correctness < 1.0 and hallucination == 0:
        return "relevant context but wrong/incomplete answer selection"
    if hit and hallucination and hallucination > 0:
        return "hallucination despite retrieved context"
    if refusal:
        return "refusal / insufficient-information behavior"
    if missed:
        return "missing information in retrieved context"
    if irrelevant and (not hit or correctness == 0):
        return "noisy retrieval"
    if hit:
        return "partially successful retrieval and generation"
    return "weak retrieval"


def context_fact_analysis(question_id, context, answer, ground_truth):
    terms = FACT_TERMS.get(question_id, [])
    context_l = (context or "").lower()
    answer_l = (answer or "").lower()
    relevant = []
    missed = []
    used = []
    for term in terms:
        in_context = term.lower() in context_l
        in_answer = term.lower() in answer_l
        if in_context:
            relevant.append(term)
            if in_answer:
                used.append(term)
        else:
            missed.append(term)
    return relevant, missed, used


def irrelevant_snippets(sources, question_id):
    terms = FACT_TERMS.get(question_id, [])
    snippets = []
    for source in sources or []:
        text = source.get("text") or ""
        blob = text.lower()
        if terms and not any(term.lower() in blob for term in terms):
            label = source.get("file_path") or source.get("document") or f"rank {source.get('rank')}"
            snippets.append(
                {
                    "source": label,
                    "rank": source.get("rank"),
                    "excerpt": text[:400],
                }
            )
    return snippets[:4]


def build_case(record, dataset_row, quality, retrieval):
    context = record.get("retrieved_context") or ""
    answer = record.get("answer") or ""
    relevant, missed, used = context_fact_analysis(
        record["question_id"], context, answer, dataset_row["ground_truth"]
    )
    irrelevant = irrelevant_snippets(record.get("retrieved_sources"), record["question_id"])
    case = {
        "question_id": record["question_id"],
        "model": record["model"],
        "category": record["category"],
        "question": record["question"],
        "retrieved_documents": [
            {
                "rank": source.get("rank"),
                "file_path": source.get("file_path"),
                "document": source.get("document"),
                "symbol": source.get("symbol"),
                "pages": source.get("pages"),
                "disaster": source.get("disaster"),
                "distance": source.get("distance"),
                "excerpt": (source.get("text") or "")[:700],
            }
            for source in (record.get("retrieved_sources") or [])
        ],
        "retrieved_context": context,
        "key_relevant_information": relevant,
        "facts_used_in_answer": used,
        "irrelevant_information": irrelevant,
        "missed_information": missed,
        "model_response": answer,
        "ground_truth": dataset_row["ground_truth"],
        "scores": {
            "correctness": quality.get("correctness") if quality else None,
            "relevance": quality.get("relevance") if quality else None,
            "hallucination": quality.get("hallucination") if quality else None,
            "correctness_rationale": quality.get("correctness_rationale") if quality else None,
            "hallucination_rationale": quality.get("hallucination_rationale") if quality else None,
        },
        "retrieval": retrieval or {},
        "success": record.get("success"),
    }
    question_id = record["question_id"]
    if question_id == "RG03":
        used_wind = "1.3" in (answer or "") or "wind speed" in (answer or "").lower()
        used_shelter = "shelter" in (answer or "").lower()
        shelter_in_context = "shelter" in (context or "").lower()
        if used_wind and not used_shelter:
            if shelter_in_context:
                analysis = (
                    "The cyclone-shelter passage was present in retrieved context, "
                    "but the model answered with a different buildings-related fact "
                    "(1.3× wind speed). This is a context-use / answer-selection "
                    "failure, not hallucination of the 1.3× figure."
                )
            else:
                analysis = (
                    "Retrieved context contained a buildings-section detail about designing "
                    "for 1.3× basic wind speed (IS 875). The expected ground-truth fact "
                    "(cyclone shelters) was not present in the retrieved chunks. The model "
                    "answered from a different retrieved buildings fact. This is classified "
                    "as a context-use / answer-selection problem combined with retrieval "
                    "miss of the shelter passage, not as hallucination of the 1.3× figure."
                )
            case["behavior"] = "relevant context but wrong/incomplete answer selection"
            case["analysis"] = analysis
            return case

    behavior = classify_behavior(case)
    case["behavior"] = behavior
    if behavior == "relevant context but wrong/incomplete answer selection":
        analysis = (
            "The retrieved context contained at least one required fact, but the "
            "model answer did not fully use those facts. This is classified as a "
            "context-use / answer-selection problem rather than hallucination."
        )
    elif behavior == "strong retrieval → correct grounded response":
        analysis = (
            "At least one expected source was retrieved and the answer matched the "
            "ground-truth rubric without unsupported claims."
        )
    elif behavior == "hallucination despite retrieved context":
        analysis = (
            "The answer included unsupported claims relative to the retrieved "
            "context and dataset hallucination criteria."
        )
    elif behavior == "missing information in retrieved context":
        analysis = (
            "One or more ground-truth facts were absent from the retrieved chunks, "
            "so the generation stage could not be fully grounded even if the model "
            "refused or answered partially."
        )
    elif behavior == "noisy retrieval":
        analysis = (
            "Several retrieved chunks did not contain the requested facts, which "
            "diluted the prompt context."
        )
    else:
        analysis = (
            "Observed RAG behavior for this question/model pair based on the "
            "retrieved chunks, rubric scores, and ground-truth facts."
        )
    case["analysis"] = analysis
    return case


def select_cases(cases):
    selected = []
    seen_ids = set()

    def add(case):
        key = (case["question_id"], case["model"])
        if key in seen_ids:
            return
        selected.append(case)
        seen_ids.add(key)

    # Always include one RG03 trace if present (1.3× wind-speed context-use case).
    for case in cases:
        if case["question_id"] == "RG03":
            add(case)
            break

    seen_behaviors = {case["behavior"] for case in selected}
    for behavior in [
        "strong retrieval → correct grounded response",
        "relevant context but wrong/incomplete answer selection",
        "noisy retrieval",
        "missing information in retrieved context",
        "refusal / insufficient-information behavior",
        "hallucination despite retrieved context",
        "weak retrieval",
        "partially successful retrieval and generation",
    ]:
        if behavior in seen_behaviors:
            continue
        for case in cases:
            if case["behavior"] == behavior:
                add(case)
                seen_behaviors.add(behavior)
                break
    for qid in PREFERRED_IDS:
        if len(selected) >= 6:
            break
        for case in cases:
            if case["question_id"] == qid:
                add(case)
                break
    if len(selected) < 5:
        for case in cases:
            add(case)
            if len(selected) >= 5:
                break
    return selected[:8]


def main():
    dataset = load_dataset()
    records = load_json(RAW_RESULTS_FILE)
    quality = {
        (item["model"], item["question_id"]): item
        for item in load_json(QUALITY_SCORES_FILE)["per_question"]
    }
    retrieval = {
        (item["model"], item["question_id"]): item
        for item in load_json(RETRIEVAL_METRICS_FILE)["per_question"]
    }
    rag_records = [
        record
        for record in records
        if record.get("category") == "RAG" or record.get("question_id") in PREFERRED_IDS
    ]
    cases = [
        build_case(
            record,
            dataset[record["question_id"]],
            quality.get((record["model"], record["question_id"])),
            retrieval.get((record["model"], record["question_id"])),
        )
        for record in rag_records
    ]
    selected = select_cases(cases)
    output = {
        "selection_rule": (
            "Cases are selected from actual evaluation traces to illustrate "
            "different RAG behaviors. Answers and retrieved chunks are not edited."
        ),
        "cases": selected,
        "all_rag_cases": cases,
    }
    RAG_CASE_STUDIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAG_CASE_STUDIES_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {RAG_CASE_STUDIES_FILE} ({len(selected)} inspector cases, {len(cases)} full RAG traces)")


if __name__ == "__main__":
    main()
