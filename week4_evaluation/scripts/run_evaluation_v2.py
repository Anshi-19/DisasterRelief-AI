import sys
from pathlib import Path
import csv
import json
import time

import requests
import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = PROJECT_ROOT

DATASET_FILE = (
    BASE_DIR
    / "week4_evaluation"
    / "dataset"
    / "evaluation_dataset.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "week4_evaluation"
    / "results"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "model_evaluation_results_v2.json"
)

OLLAMA_URL = "http://localhost:11434/api/generate"

EMBEDDING_URL = (
    "http://localhost:11434/api/embeddings"
)

EMBEDDING_MODEL = "nomic-embed-text:latest"

MODELS = [
    "codellama:latest",
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
]

TOP_K = 8

TEMPERATURE = 0.0
NUM_PREDICT = 300

CHROMA_PATH = (
    BASE_DIR
    / "vector_store"
)

CODE_COLLECTION = "disaster_relief_code"


# ============================================================
# SHARED SYSTEM PROMPT
# ============================================================

SYSTEM_INSTRUCTION = """
You are an AI assistant being evaluated on a software repository
understanding and question-answering benchmark.

You will receive:

1. A USER QUESTION
2. A RETRIEVED CONTEXT from the DisasterRelief AI repository
   or disaster knowledge base.

Answer the user's question using ONLY the supplied context.

For repository questions:
- Base your answer on the supplied repository context.
- Do not invent files, functions, APIs, dependencies, or behavior.
- Identify relevant file paths and function/class names when available.
- If the requested information is not present, clearly say so.

For RAG questions:
- Use only facts explicitly present in the retrieved knowledge base.
- Do not use outside knowledge.
- Do not invent schemes, eligibility rules, financial amounts,
  procedures, contacts, deadlines, or requirements.
- Preserve numerical information accurately.
- Identify the source document and page when available.

For code-generation questions:
- Produce valid Python code when Python is requested.
- Use repository context when relevant.
- Do not invent project APIs.
- Keep the implementation focused on the requested task.

For refactoring questions:
- Preserve the behavior specified in the question.
- Do not introduce unnecessary dependencies.

Be concise and directly answer the question.
Do not describe hidden reasoning.
"""


# ============================================================
# EMBEDDING
# ============================================================

def generate_embedding(text):

    response = requests.post(
        EMBEDDING_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text,
        },
        timeout=120,
    )

    response.raise_for_status()

    return response.json()["embedding"]


# ============================================================
# DISASTER KNOWLEDGE-BASE RETRIEVAL
# ============================================================

def retrieve_disaster_documents(question):

    from backend.services.retrieval_service import (
        retrieve_documents
    )

    return retrieve_documents(
        question,
        top_k=TOP_K
    )


# ============================================================
# REPOSITORY CODE RETRIEVAL
# ============================================================

def retrieve_repository_code(question):

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    collection = client.get_collection(
        CODE_COLLECTION
    )

    query_embedding = generate_embedding(
        question
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
    )

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    output = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):
        output.append(
            {
                "text": document,
                "metadata": metadata,
                "distance": distance,
            }
        )

    return output


# ============================================================
# CATEGORY ROUTING
# ============================================================

def should_use_repository(row):

    category = row["category"].strip().lower()

    repository_categories = {
        "code retrieval",
        "dependency understanding",
        "bug analysis",
        "code generation",
        "refactoring",
    }

    return category in repository_categories


# ============================================================
# BUILD CONTEXT
# ============================================================

def build_context(results, repository=False):

    context_parts = []

    for index, result in enumerate(
        results,
        start=1
    ):

        metadata = result["metadata"]

        if repository:

            file_path = metadata.get(
                "file_path",
                "unknown"
            )

            symbol = metadata.get(
                "symbol",
                "unknown"
            )

            language = metadata.get(
                "language",
                "unknown"
            )

            source = (
                f"[SOURCE {index}]\n"
                f"File: {file_path}\n"
                f"Language: {language}\n"
                f"Symbol: {symbol}\n"
                f"Code type: "
                f"{metadata.get('code_type', 'unknown')}\n"
                f"Chunk: "
                f"{metadata.get('chunk_number', 'unknown')}\n"
            )

        else:

            source = (
                f"[SOURCE {index}]\n"
                f"Document: "
                f"{metadata.get('document')}\n"
                f"Authority: "
                f"{metadata.get('authority')}\n"
                f"Disaster: "
                f"{metadata.get('disaster')}\n"
                f"Page(s): "
                f"{metadata.get('pages')}\n"
            )

        context_parts.append(
            source
            + "\nCONTENT:\n"
            + result["text"]
            + "\n[END SOURCE]"
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# LOAD DATASET
# ============================================================

def load_dataset():

    with DATASET_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as f:

        return list(
            csv.DictReader(f)
        )


# ============================================================
# CALL OLLAMA
# ============================================================

def generate_response(
    question,
    context,
    model
):

    prompt = f"""
{SYSTEM_INSTRUCTION}

================ RETRIEVED CONTEXT ================

{context}

================ END RETRIEVED CONTEXT ============

USER QUESTION:

{question}

================ ANSWER ===========================

ANSWER:
"""

    start_time = time.perf_counter()

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": NUM_PREDICT,
            },
        },
        timeout=300,
    )

    latency = (
        time.perf_counter()
        - start_time
    )

    response.raise_for_status()

    data = response.json()

    return {
        "answer":
            data.get(
                "response",
                ""
            ).strip(),

        "latency_seconds":
            round(latency, 3),

        "prompt_eval_count":
            data.get(
                "prompt_eval_count"
            ),

        "eval_count":
            data.get(
                "eval_count"
            ),

        "total_duration_ns":
            data.get(
                "total_duration"
            ),

        "load_duration_ns":
            data.get(
                "load_duration"
            ),

        "prompt_eval_duration_ns":
            data.get(
                "prompt_eval_duration"
            ),

        "eval_duration_ns":
            data.get(
                "eval_duration"
            ),
    }


# ============================================================
# SERIALIZE SOURCES
# ============================================================

def serialize_sources(
    results,
    repository=False
):

    sources = []

    for rank, result in enumerate(
        results,
        start=1
    ):

        metadata = result["metadata"]

        if repository:

            sources.append(
                {
                    "rank": rank,
                    "file_path":
                        metadata.get(
                            "file_path"
                        ),
                    "symbol":
                        metadata.get(
                            "symbol"
                        ),
                    "language":
                        metadata.get(
                            "language"
                        ),
                    "chunk_number":
                        metadata.get(
                            "chunk_number"
                        ),
                    "distance":
                        result.get(
                            "distance"
                        ),
                    "text":
                        result.get(
                            "text"
                        ),
                }
            )

        else:

            sources.append(
                {
                    "rank": rank,
                    "document":
                        metadata.get(
                            "document"
                        ),
                    "authority":
                        metadata.get(
                            "authority"
                        ),
                    "disaster":
                        metadata.get(
                            "disaster"
                        ),
                    "pages":
                        metadata.get(
                            "pages"
                        ),
                    "distance":
                        result.get(
                            "distance"
                        ),
                    "text":
                        result.get(
                            "text"
                        ),
                }
            )

    return sources


# ============================================================
# MAIN EVALUATION
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    dataset = load_dataset()

    print("=" * 70)
    print(
        "DISASTERRELIEF AI - WEEK 4 MODEL EVALUATION V2"
    )
    print("=" * 70)

    print(
        f"\nDataset: {DATASET_FILE}"
    )

    print(
        f"Questions: {len(dataset)}"
    )

    print(
        f"Models: {len(MODELS)}"
    )

    print(
        f"Expected experiments: "
        f"{len(dataset) * len(MODELS)}"
    )

    print("\nModels:")

    for model in MODELS:
        print(
            f"  - {model}"
        )

    print("\nEmbedding model:")

    print(
        f"  - {EMBEDDING_MODEL}"
    )

    print("\nRetrieval routing:")

    print(
        "  - Repository categories "
        "-> disaster_relief_code"
    )

    print(
        "  - RAG category -> "
        "disaster_relief knowledge base"
    )

    print(
        "\n" + "=" * 70
    )

    all_results = []

    for question_number, row in enumerate(
        dataset,
        start=1
    ):

        question_id = row["id"]
        question = row["question"]
        category = row["category"]

        use_repository = should_use_repository(
            row
        )

        print(
            f"\n[{question_number}/{len(dataset)}] "
            f"{question_id} - {category}"
        )

        print(
            f"Question: {question}"
        )

        print(
            "Retrieval source: "
            + (
                "REPOSITORY CODE"
                if use_repository
                else "DISASTER KNOWLEDGE BASE"
            )
        )

        retrieval_start = (
            time.perf_counter()
        )

        try:

            if use_repository:

                retrieved_results = (
                    retrieve_repository_code(
                        question
                    )
                )

            else:

                retrieved_results = (
                    retrieve_disaster_documents(
                        question
                    )
                )

            retrieval_latency = (
                time.perf_counter()
                - retrieval_start
            )

            context = build_context(
                retrieved_results,
                repository=use_repository
            )

            sources = serialize_sources(
                retrieved_results,
                repository=use_repository
            )

        except Exception as e:

            print(
                f"  RETRIEVAL ERROR: {e}"
            )

            retrieved_results = []
            context = ""
            sources = []

            retrieval_latency = (
                time.perf_counter()
                - retrieval_start
            )

        print(
            f"Retrieved chunks: "
            f"{len(retrieved_results)}"
        )

        print(
            f"Retrieval latency: "
            f"{retrieval_latency:.3f}s"
        )

        # ----------------------------------------------------
        # RUN ALL THREE MODELS ON SAME CONTEXT
        # ----------------------------------------------------

        for model in MODELS:

            print(
                f"  Running {model}..."
            )

            try:

                result = generate_response(
                    question=question,
                    context=context,
                    model=model
                )

                record = {

                    "evaluation_version":
                        "v2_repository_routing",

                    "question_id":
                        question_id,

                    "category":
                        category,

                    "question":
                        question,

                    "model":
                        model,

                    "embedding_model":
                        EMBEDDING_MODEL,

                    "retrieval_source":
                        (
                            "repository"
                            if use_repository
                            else "disaster_knowledge_base"
                        ),

                    "top_k":
                        TOP_K,

                    "retrieval_latency_seconds":
                        round(
                            retrieval_latency,
                            3
                        ),

                    "retrieved_chunk_count":
                        len(
                            retrieved_results
                        ),

                    "retrieved_sources":
                        sources,

                    "answer":
                        result["answer"],

                    "generation_latency_seconds":
                        result[
                            "latency_seconds"
                        ],

                    "prompt_eval_count":
                        result[
                            "prompt_eval_count"
                        ],

                    "eval_count":
                        result[
                            "eval_count"
                        ],

                    "total_duration_ns":
                        result[
                            "total_duration_ns"
                        ],

                    "load_duration_ns":
                        result[
                            "load_duration_ns"
                        ],

                    "prompt_eval_duration_ns":
                        result[
                            "prompt_eval_duration_ns"
                        ],

                    "eval_duration_ns":
                        result[
                            "eval_duration_ns"
                        ],
                }

                all_results.append(
                    record
                )

                print(
                    f"    ✓ completed "
                    f"({result['latency_seconds']:.2f}s)"
                )

            except Exception as e:

                print(
                    f"    ✗ ERROR: {e}"
                )

                all_results.append(
                    {
                        "evaluation_version":
                            "v2_repository_routing",

                        "question_id":
                            question_id,

                        "category":
                            category,

                        "question":
                            question,

                        "model":
                            model,

                        "retrieval_source":
                            (
                                "repository"
                                if use_repository
                                else "disaster_knowledge_base"
                            ),

                        "error":
                            str(e),
                    }
                )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_results,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(
        "\n" + "=" * 70
    )

    print(
        "V2 EVALUATION COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"\nTotal experiment records: "
        f"{len(all_results)}"
    )

    successful = [
        r
        for r in all_results
        if "error" not in r
    ]

    failed = [
        r
        for r in all_results
        if "error" in r
    ]

    print(
        f"Successful: {len(successful)}"
    )

    print(
        f"Failed: {len(failed)}"
    )

    print(
        f"\nResults saved to:\n"
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()