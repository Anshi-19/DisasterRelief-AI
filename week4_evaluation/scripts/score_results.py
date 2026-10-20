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
    / "model_evaluation_results.json"
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
    / "scored_results.csv"
)


def normalize(text):
    """Normalize text for simple keyword/exact matching."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def keyword_match(answer, ground_truth):
    """
    Calculate how much of the ground-truth text is represented
    in the model answer using meaningful keywords.
    """
    answer = normalize(answer)
    truth = normalize(ground_truth)

    if not truth:
        return 0.0

    # Remove very common words.
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in",
        "is", "are", "for", "on", "with", "from", "that",
        "this", "be", "by", "as", "it", "their", "its",
        "within", "under", "which", "has", "have"
    }

    words = re.findall(r"[a-zA-Z0-9_./:-]+", truth)
    words = [w for w in words if w not in stopwords and len(w) > 2]

    if not words:
        return 0.0

    matched = sum(1 for word in words if word in answer)

    return matched / len(words)


def source_match(answer, sources):
    """Check whether retrieved source/document names appear in the answer."""
    if not sources:
        return 0.0

    answer_normalized = normalize(answer)

    matches = 0

    for source in sources:
        document = normalize(source.get("document", ""))

        if document and (
            document in answer_normalized
            or Path(document).stem in answer_normalized
        ):
            matches += 1

    return matches / len(sources)


def calculate_retrieval_score(record):
    """
    Retrieval coverage score.

    1.0 = useful chunks retrieved
    0.0 = no chunks retrieved
    """
    count = record.get("retrieved_chunk_count", 0)

    if count and count > 0:
        return 1.0

    return 0.0


def calculate_hallucination_score(answer, ground_truth, retrieved_count):
    """
    Conservative heuristic.

    If there is no retrieval context, we flag the answer for review
    rather than claiming that it is definitely hallucinated.
    """
    if retrieved_count == 0:
        return "REVIEW"

    coverage = keyword_match(answer, ground_truth)

    if coverage >= 0.60:
        return 0.0

    if coverage >= 0.30:
        return 0.5

    return 1.0


def calculate_correctness(answer, ground_truth):
    """
    Convert ground-truth keyword coverage into a 0-1 score.
    """
    return round(keyword_match(answer, ground_truth), 3)


def calculate_relevance(answer):
    """Basic relevance heuristic based on whether an answer exists."""
    if not answer or not answer.strip():
        return 0.0

    answer_length = len(answer.split())

    if answer_length < 5:
        return 0.25

    if answer_length < 15:
        return 0.50

    if answer_length < 30:
        return 0.75

    return 1.0


def load_dataset():
    dataset = {}

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            dataset[row["id"]] = row

    return dataset


def main():
    print("=" * 70)
    print("WEEK 4 — AUTOMATIC SCORING")
    print("=" * 70)

    print(f"\nLoading results:")
    print(RESULTS_FILE)

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)

    print(f"Loaded experiment records: {len(results)}")

    dataset = load_dataset()

    print(f"Loaded dataset questions: {len(dataset)}")

    scored = []

    for record in results:
        question_id = record["question_id"]

        question_data = dataset.get(question_id)

        if question_data is None:
            print(f"WARNING: No dataset entry for {question_id}")
            continue

        answer = record.get("answer", "")
        ground_truth = question_data["ground_truth"]

        sources = record.get("sources", [])

        retrieved_count = record.get(
            "retrieved_chunk_count",
            len(record.get("retrieved_chunks", []))
        )

        correctness = calculate_correctness(
            answer,
            ground_truth
        )

        relevance = calculate_relevance(answer)

        hallucination = calculate_hallucination_score(
            answer,
            ground_truth,
            retrieved_count
        )

        retrieval_score = calculate_retrieval_score(record)

        source_score = source_match(
            answer,
            sources
        )

        scored_record = {
            "question_id": question_id,
            "category": record["category"],
            "model": record["model"],
            "question": record["question"],

            "answer": answer,

            "ground_truth": ground_truth,

            "retrieved_chunk_count": retrieved_count,

            "correctness_score": correctness,

            "relevance_score": relevance,

            "hallucination_score": hallucination,

            "retrieval_score": retrieval_score,

            "source_citation_score": round(source_score, 3),

            "latency_seconds": record.get(
                "latency_seconds",
                record.get("latency", "")
            ),

            "input_tokens": record.get(
                "input_tokens",
                ""
            ),

            "output_tokens": record.get(
                "output_tokens",
                ""
            ),

            "total_tokens": record.get(
                "total_tokens",
                ""
            ),
        }

        scored.append(scored_record)

    fieldnames = [
        "question_id",
        "category",
        "model",
        "question",
        "answer",
        "ground_truth",
        "retrieved_chunk_count",
        "correctness_score",
        "relevance_score",
        "hallucination_score",
        "retrieval_score",
        "source_citation_score",
        "latency_seconds",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(scored)

    print("\n" + "=" * 70)
    print("SCORING COMPLETE")
    print("=" * 70)

    print(f"\nScored records: {len(scored)}")
    print(f"Output: {OUTPUT_FILE}")

    # Summary
    summary = defaultdict(list)

    for row in scored:
        summary[row["model"]].append(row)

    print("\nMODEL SUMMARY")
    print("-" * 70)

    for model, rows in sorted(summary.items()):

        correctness_values = [
            r["correctness_score"]
            for r in rows
        ]

        relevance_values = [
            r["relevance_score"]
            for r in rows
        ]

        retrieval_values = [
            r["retrieval_score"]
            for r in rows
        ]

        valid_hallucination = [
            r["hallucination_score"]
            for r in rows
            if isinstance(r["hallucination_score"], (int, float))
        ]

        avg_correctness = (
            sum(correctness_values)
            / len(correctness_values)
        )

        avg_relevance = (
            sum(relevance_values)
            / len(relevance_values)
        )

        avg_retrieval = (
            sum(retrieval_values)
            / len(retrieval_values)
        )

        avg_hallucination = (
            sum(valid_hallucination)
            / len(valid_hallucination)
            if valid_hallucination
            else 0
        )

        print(f"\n{model}")
        print(f"  Records:             {len(rows)}")
        print(f"  Avg correctness:     {avg_correctness:.3f}")
        print(f"  Avg relevance:       {avg_relevance:.3f}")
        print(f"  Retrieval coverage:  {avg_retrieval:.3f}")
        print(f"  Hallucination risk:  {avg_hallucination:.3f}")


if __name__ == "__main__":
    main()
