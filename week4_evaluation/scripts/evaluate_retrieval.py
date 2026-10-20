"""Objective retrieval metrics using dataset ground-truth files/documents."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

from eval_config import (
    DATASET_FILE,
    RAW_RESULTS_FILE,
    RESULTS_DIR,
    RETRIEVAL_METRICS_FILE,
    TOP_K,
)


def load_dataset():
    with DATASET_FILE.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def split_files(value):
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;|,]", value) if part.strip()]


def normalize_path(value):
    if not value:
        return ""
    text = str(value).replace("\\", "/").strip().lower()
    text = re.sub(r"^file path:\s*", "", text)
    return text


def basename(value):
    return Path(normalize_path(value)).name


def retrieved_identifiers(record):
    identifiers = []
    for source in record.get("retrieved_sources") or []:
        if source.get("file_path"):
            identifiers.append(
                {
                    "rank": source.get("rank"),
                    "path": normalize_path(source.get("file_path")),
                    "name": basename(source.get("file_path")),
                    "kind": "file",
                }
            )
        elif source.get("document"):
            identifiers.append(
                {
                    "rank": source.get("rank"),
                    "path": normalize_path(source.get("document")),
                    "name": basename(source.get("document")),
                    "kind": "document",
                }
            )
    return identifiers


def expected_identifiers(row):
    expected = []
    for item in split_files(row.get("relevant_files", "")):
        expected.append(
            {
                "path": normalize_path(item),
                "name": basename(item),
                "raw": item,
            }
        )
    return expected


def is_match(expected, retrieved):
    exp_path = expected["path"]
    exp_name = expected["name"]
    ret_path = retrieved["path"]
    ret_name = retrieved["name"]
    if not exp_path or not ret_path:
        return False
    if exp_path == ret_path:
        return True
    if exp_path in ret_path or ret_path in exp_path:
        return True
    if exp_name and exp_name == ret_name:
        return True
    # PDF / guideline aliases stored as document titles.
    aliases = {
        "flood_guidelines.pdf": ["flood"],
        "earthquake_guidelines.pdf": ["earthquake"],
        "cyclone_guidelines.pdf": ["cyclone"],
        "mha_recovery_reconstruction_2024.pdf": [
            "recovery",
            "reconstruction",
            "home affairs",
            "mha",
        ],
    }
    if exp_name in aliases:
        blob = ret_path
        return all(token in blob for token in aliases[exp_name][:1]) and any(
            token in blob for token in aliases[exp_name]
        )
    return False


def first_relevant_rank(expected, retrieved):
    for item in retrieved:
        rank = item.get("rank") or 0
        for exp in expected:
            if is_match(exp, item):
                return rank
    return None


def matched_expected(expected, retrieved):
    matched = []
    for exp in expected:
        if any(is_match(exp, item) for item in retrieved):
            matched.append(exp["raw"])
    return matched


def evaluate_record(record, dataset_row):
    expected = expected_identifiers(dataset_row)
    retrieved = retrieved_identifiers(record)
    k = record.get("top_k") or TOP_K
    rank = first_relevant_rank(expected, retrieved)
    hit = rank is not None
    matched = matched_expected(expected, retrieved)
    precision = (
        round(len(matched) / max(len(retrieved), 1), 4) if retrieved else 0.0
    )
    # Precision@K using file-level uniqueness: count retrieved items that
    # match any expected file, divided by K retrieved items.
    relevant_retrieved = 0
    for item in retrieved:
        if any(is_match(exp, item) for exp in expected):
            relevant_retrieved += 1
    precision_at_k = (
        round(relevant_retrieved / max(len(retrieved), 1), 4) if retrieved else 0.0
    )
    recall_at_k = (
        round(len(matched) / max(len(expected), 1), 4) if expected else None
    )
    return {
        "model": record.get("model"),
        "question_id": record.get("question_id"),
        "category": record.get("category"),
        "retrieval_source": record.get("retrieval_source"),
        "expected_files": [item["raw"] for item in expected],
        "retrieved_files": [
            item["path"] or item["name"] for item in retrieved
        ],
        "matched_expected_files": matched,
        "hit_at_k": hit,
        "k": k,
        "first_relevant_rank": rank,
        "reciprocal_rank": round(1.0 / rank, 4) if rank else 0.0,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "unique_expected_hit_precision": precision,
        "retrieved_chunk_count": record.get("retrieved_chunk_count"),
        "scoring_method": "ground_truth_file_match",
    }


def aggregate(rows):
    by_model = defaultdict(list)
    by_model_category = defaultdict(list)
    for row in rows:
        by_model[row["model"]].append(row)
        by_model_category[(row["model"], row["category"])].append(row)

    def summarize(group):
        hits = [1 if item["hit_at_k"] else 0 for item in group]
        mrr = [item["reciprocal_rank"] for item in group]
        precision = [item["precision_at_k"] for item in group]
        recall = [
            item["recall_at_k"]
            for item in group
            if item["recall_at_k"] is not None
        ]
        return {
            "n": len(group),
            "hit_at_k": round(mean(hits), 4) if hits else None,
            "mrr": round(mean(mrr), 4) if mrr else None,
            "precision_at_k": round(mean(precision), 4) if precision else None,
            "recall_at_k": round(mean(recall), 4) if recall else None,
        }

    return {
        "k": TOP_K,
        "definition": {
            "hit_at_k": "1 if at least one ground-truth relevant file/document appears in the top-K retrieved results.",
            "mrr": "Mean of 1/rank of the first relevant retrieved result; 0 if none.",
            "precision_at_k": "Fraction of retrieved chunks whose file/document matches a ground-truth relevant item.",
            "recall_at_k": "Fraction of ground-truth relevant files/documents found in the retrieved set.",
            "matching": "Path containment, basename match, and document-title aliases for NDMA/MHA PDFs. Not keyword scoring of answers.",
        },
        "models": {model: summarize(group) for model, group in by_model.items()},
        "by_category": {
            f"{model}::{category}": summarize(group)
            for (model, category), group in by_model_category.items()
        },
    }


def main():
    dataset = load_dataset()
    records = json.loads(RAW_RESULTS_FILE.read_text(encoding="utf-8"))
    per_question = [evaluate_record(record, dataset[record["question_id"]]) for record in records]
    output = {
        "per_question": per_question,
        "aggregates": aggregate(per_question),
    }
    RETRIEVAL_METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RETRIEVAL_METRICS_FILE.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {RETRIEVAL_METRICS_FILE}")
    for model, values in output["aggregates"]["models"].items():
        print(
            f"{model}: Hit@{TOP_K}={values['hit_at_k']} "
            f"MRR={values['mrr']} P@{TOP_K}={values['precision_at_k']} "
            f"R@{TOP_K}={values['recall_at_k']}"
        )


if __name__ == "__main__":
    main()
