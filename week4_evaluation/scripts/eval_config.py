"""Shared Week 4 evaluation configuration.

The Week 3 application remains unchanged. This module is used only by
the Week 4 evaluation scripts.
"""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEEK4_DIR = PROJECT_ROOT / "week4_evaluation"

DATASET_FILE = WEEK4_DIR / "dataset" / "evaluation_dataset.csv"
RESULTS_DIR = WEEK4_DIR / "results"
V4_RESULTS_DIR = RESULTS_DIR / "v4_improved"
REPORTS_DIR = WEEK4_DIR / "reports"
EXPORTS_DIR = WEEK4_DIR / "exports"
DASHBOARD_DIR = WEEK4_DIR / "dashboard"
DASHBOARD_DATA_FILE = DASHBOARD_DIR / "dashboard_data.json"

RAW_RESULTS_FILE = Path(
    os.environ["WEEK4_RAW_RESULTS"]
) if os.environ.get("WEEK4_RAW_RESULTS") else RESULTS_DIR / "raw" / "week4_v4_improved.json"
RAW_CANONICAL_COPY = RAW_RESULTS_FILE
V3_RAW_RESULTS_FILE = RESULTS_DIR / "raw" / "week4_v3_controlled.json"
V3_QUALITY_SCORES_FILE = RESULTS_DIR / "quality_scores.json"
V3_RETRIEVAL_METRICS_FILE = RESULTS_DIR / "retrieval_metrics.json"
V3_RESOURCE_METRICS_FILE = RESULTS_DIR / "resource_metrics.json"
V3_SUMMARY_FILE = RESULTS_DIR / "benchmark_summary.json"
QUALITY_SCORES_FILE = V4_RESULTS_DIR / "quality_scores.json"
RETRIEVAL_METRICS_FILE = V4_RESULTS_DIR / "retrieval_metrics.json"
RESOURCE_METRICS_FILE = V4_RESULTS_DIR / "resource_metrics.json"
RAG_CASE_STUDIES_FILE = V4_RESULTS_DIR / "rag_case_studies.json"
REPOSITORY_EVAL_FILE = V4_RESULTS_DIR / "repository_evaluation.json"
CODEGEN_RESULTS_FILE = V4_RESULTS_DIR / "codegen_evaluation.json"
SUMMARY_FILE = V4_RESULTS_DIR / "benchmark_summary.json"
V3_V4_COMPARISON_FILE = V4_RESULTS_DIR / "v3_v4_comparison.json"

EVALUATION_VERSION = os.environ.get("WEEK4_EVALUATION_VERSION", "week4_v4_improved")
EVALUATION_DATE = "2026-09-18"

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"

EMBEDDING_MODEL = "nomic-embed-text:latest"

MODELS = [
    "codellama:latest",
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
]

MODEL_DISPLAY = {
    "codellama:latest": "CodeLlama",
    "qwen2.5-coder:7b": "Qwen2.5-Coder",
    "deepseek-coder:6.7b": "DeepSeek-Coder",
}

TOP_K = 8
TEMPERATURE = 0.0
NUM_PREDICT = 640
REQUEST_TIMEOUT = 300
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3.0

DISASTER_CHROMA_DIR = PROJECT_ROOT / "vector_store" / "chroma_db"
DISASTER_COLLECTION = "disaster_relief"

CODE_CHROMA_DIR = PROJECT_ROOT / "vector_store"
CODE_COLLECTION = "disaster_relief_code"

APPLICATION_LLM_MODEL = "codellama:latest"

REPOSITORY_CATEGORIES = {
    "Explanation",
    "Code Retrieval",
    "Dependency Understanding",
    "Bug Analysis",
    "Code Generation",
    "Refactoring",
}

RAG_CATEGORIES = {
    "RAG",
}

SYSTEM_INSTRUCTION = """
Answer the user's actual question directly. Use the supplied context as the
only factual evidence. Select the passages that answer the question and ignore
unrelated ones. Do not invent facts, files, functions, modules, APIs, imports,
or behavior. If the requested fact is in the context, answer it; do not refuse.
Prefer live application files (execution_path=live, backend/services, frontend)
over legacy backend/rag unless the question asks about legacy code. For code,
use the exact paths, symbols, signatures, and PYTHON IMPORT lines in context.
Keep the answer concise, complete, and organized. Omit sections that do not
apply to the question. If evidence is genuinely insufficient, say so briefly.
""".strip()
