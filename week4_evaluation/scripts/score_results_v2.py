import json
import csv
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RESULTS_FILE = (
    PROJECT_ROOT
    / "week4_evaluation"
    / "results"
    / "model_evaluation_results_v2.json"
)

DATASET_FILE = (
    PROJECT_ROOT
    / "week4_evaluation"
    / "dataset"
    / "evaluation_dataset.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "week4_evaluation"
    / "results"
    / "model_scores_v2.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_dataset(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return {
            row["id"]: row
            for row in csv.DictReader(f)
        }


def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def file_mentions_answer(answer, relevant_files):
    """
    Heuristic retrieval/grounding check.

    This is not the final correctness score.
    It checks whether the model answer mentions at least
    one of the expected repository files.
    """
    answer_norm = normalize(answer)

    for file_path in relevant_files:
        file_path = file_path.strip()
        if not file_path:
            continue

        variants = {
            normalize(file_path),
            normalize(file_path.replace("/", "\\")),
            normalize(Path(file_path).name),
        }

        if any(v and v in answer_norm for v in variants):
            return True

    return False


def expected_keywords(row):
    """
    Extract useful terms from the manually defined criteria.
    This provides a transparent auxiliary signal rather than
    pretending to be a complete semantic evaluator.
    """
    text = " ".join(
        [
            row.get("ground_truth", ""),
            row.get("correctness_criteria", ""),
            row.get("relevance_criteria", ""),
        ]
    ).lower()

    keywords = []

    important_terms = [
        "flood",
        "earthquake",
        "cyclone",
        "chroma",
        "ollama",
        "embedding",
        "retrieve_documents",
        "generate_response",
        "detect_disaster",
        "build_context",
        "/api/chat",
        "retrieval_service.py",
        "embedding_service.py",
        "llm_service.py",
        "orchestration_service.py",
        "main.py",
        "app.jsx",
        "top_k",
        "distance",
        "threshold",
        "hallucination",
        "relief supplies",
        "tents",
        "water supply",
        "sanitation",
        "transport",
        "communication",
        "medical supplies",
        "1.3",
        "wind speed",
        "recovery",
        "reconstruction",
        "sdrf",
        "ndrf",
    ]

    for term in important_terms:
        if term in text:
            keywords.append(term)

    return keywords


def keyword_coverage(answer, keywords):
    """
    Transparent auxiliary score:
    fraction of expected important terms appearing in answer.
    """
    if not keywords:
        return 0.0

    answer_norm = normalize(answer)
    hits = sum(1 for k in keywords if k in answer_norm)

    return hits / len(keywords)


def evaluate_record(record, row):
    """
    Produces auxiliary deterministic metrics.

    IMPORTANT:
    These are evidence signals, not an automatic replacement
    for human correctness judgment.
    """
    answer = record.get("answer", "")
    category = row["category"]

    relevant_files = [
        x.strip()
        for x in row.get("relevant_files", "").split(";")
        if x.strip()
    ]

    keywords = expected_keywords(row)

    result = {
        "question_id": record["question_id"],
        "category": category,
        "model": record["model"],
        "retrieval_source": record.get("retrieval_source"),
        "retrieved_chunk_count": record.get(
            "retrieved_chunk_count", 0
        ),
        "retrieval_latency_seconds": record.get(
            "retrieval_latency_seconds"
        ),
        "generation_latency_seconds": record.get(
            "generation_latency_seconds"
        ),
        "prompt_eval_count": record.get(
            "prompt_eval_count"
        ),
        "eval_count": record.get(
            "eval_count"
        ),
        "generation_failed": "error" in record,
    }

    if "error" in record:
        result.update(
            {
                "retrieval_success": (
                    record.get("retrieved_chunk_count", 0) > 0
                ),
                "repository_file_grounding": None,
                "keyword_coverage": None,
                "status": "generation_failure",
                "error": record["error"],
            }
        )
        return result

    result["retrieval_success"] = (
        record.get("retrieved_chunk_count", 0) > 0
    )

    result["repository_file_grounding"] = (
        file_mentions_answer(
            answer,
            relevant_files
        )
        if category
        in {
            "Code Retrieval",
            "Dependency Understanding",
            "Bug Analysis",
            "Code Generation",
            "Refactoring",
        }
        else None
    )

    result["keyword_coverage"] = round(
        keyword_coverage(answer, keywords),
        3
    )

    result["status"] = "success"

    return result


def aggregate(scores):
    by_model = defaultdict(list)

    for score in scores:
        by_model[score["model"]].append(score)

    output = {}

    for model, rows in by_model.items():
        successful = [
            r for r in rows
            if not r["generation_failed"]
        ]

        retrieval_success = [
            r for r in successful
            if r["retrieval_success"]
        ]

        grounded = [
            r for r in successful
            if r["repository_file_grounding"] is True
        ]

        keyword_values = [
            r["keyword_coverage"]
            for r in successful
            if r["keyword_coverage"] is not None
        ]

        latencies = [
            r["generation_latency_seconds"]
            for r in successful
            if r["generation_latency_seconds"]
            is not None
        ]

        output[model] = {
            "total_experiments": len(rows),
            "successful_generations": len(successful),
            "generation_failures": (
                len(rows) - len(successful)
            ),
            "retrieval_success_rate": round(
                len(retrieval_success)
                / len(successful)
                if successful else 0,
                3,
            ),
            "repository_file_grounding_rate": round(
                len(grounded)
                / len(
                    [
                        r for r in successful
                        if r["repository_file_grounding"]
                        is not None
                    ]
                )
                if any(
                    r["repository_file_grounding"]
                    is not None
                    for r in successful
                )
                else 0,
                3,
            ),
            "mean_keyword_coverage": round(
                sum(keyword_values)
                / len(keyword_values)
                if keyword_values else 0,
                3,
            ),
            "mean_generation_latency_seconds": round(
                sum(latencies)
                / len(latencies)
                if latencies else 0,
                3,
            ),
        }

    return output


def category_aggregate(scores):
    grouped = defaultdict(list)

    for score in scores:
        grouped[
            (
                score["model"],
                score["category"]
            )
        ].append(score)

    output = {}

    for (model, category), rows in grouped.items():
        successful = [
            r for r in rows
            if not r["generation_failed"]
        ]

        keyword_values = [
            r["keyword_coverage"]
            for r in successful
            if r["keyword_coverage"] is not None
        ]

        output.setdefault(model, {})[category] = {
            "experiments": len(rows),
            "successful": len(successful),
            "failures": (
                len(rows) - len(successful)
            ),
            "retrieval_success_rate": round(
                sum(
                    r["retrieval_success"]
                    for r in successful
                )
                / len(successful)
                if successful else 0,
                3,
            ),
            "mean_keyword_coverage": round(
                sum(keyword_values)
                / len(keyword_values)
                if keyword_values else 0,
                3,
            ),
            "mean_generation_latency_seconds": round(
                sum(
                    r["generation_latency_seconds"]
                    for r in successful
                    if r["generation_latency_seconds"]
                    is not None
                )
                / len(
                    [
                        r for r in successful
                        if r["generation_latency_seconds"]
                        is not None
                    ]
                )
                if any(
                    r["generation_latency_seconds"]
                    is not None
                    for r in successful
                )
                else 0,
                3,
            ),
        }

    return output


def main():
    results = load_json(RESULTS_FILE)
    dataset = load_dataset(DATASET_FILE)

    scores = []

    for record in results:
        row = dataset[record["question_id"]]
        scores.append(
            evaluate_record(record, row)
        )

    final = {
        "evaluation_version": "v2_auxiliary_scoring",
        "description": (
            "Deterministic auxiliary metrics for V2. "
            "Keyword coverage and file grounding are "
            "evidence signals, not standalone correctness "
            "or hallucination judgments."
        ),
        "total_records": len(scores),
        "overall": aggregate(scores),
        "by_category": category_aggregate(scores),
        "records": scores,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            final,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("=" * 70)
    print("V2 AUXILIARY SCORING COMPLETE")
    print("=" * 70)

    print(f"\nRecords scored: {len(scores)}")

    print("\nOVERALL:")
    for model, metrics in final["overall"].items():
        print(f"\n{model}")
        for key, value in metrics.items():
            print(f"  {key}: {value}")

    print("\nCATEGORY METRICS:")

    for model, categories in final["by_category"].items():
        print(f"\n{model}")

        for category, metrics in categories.items():
            print(f"  {category}")
            print(
                f"    retrieval_success_rate: "
                f"{metrics['retrieval_success_rate']}"
            )
            print(
                f"    mean_keyword_coverage: "
                f"{metrics['mean_keyword_coverage']}"
            )
            print(
                f"    mean_generation_latency_seconds: "
                f"{metrics['mean_generation_latency_seconds']}"
            )

    print(
        f"\nSaved to:\n{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
