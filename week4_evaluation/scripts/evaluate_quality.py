"""Rubric-based quality scoring and code-generation execution.

Score types:
- rubric: deterministic checks against the dataset correctness/relevance/
  hallucination criteria and repository ground truth
- measured: code executed against the real backend package
- heuristic: auxiliary signals that are never used as the sole score
"""

from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
import tempfile
import textwrap
from collections import defaultdict
from pathlib import Path
from statistics import mean

from eval_config import (
    CODEGEN_RESULTS_FILE,
    DATASET_FILE,
    PROJECT_ROOT,
    QUALITY_SCORES_FILE,
    RAW_RESULTS_FILE,
    V4_RESULTS_DIR,
)

BACKEND_DIR = PROJECT_ROOT / "backend"
KNOWN_FILES = {
    "backend/main.py",
    "backend/services/orchestration_service.py",
    "backend/services/retrieval_service.py",
    "backend/services/embedding_service.py",
    "backend/services/llm_service.py",
    "frontend/src/App.jsx",
    "frontend/src/main.jsx",
    "backend/rag/rag_service.py",
    "backend/rag/retrieval.py",
    "backend/rag/embeddings.py",
    "backend/ingestion/ingest.py",
}


def load_dataset():
    with DATASET_FILE.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def ternary(full, partial):
    if full:
        return 1.0
    if partial:
        return 0.5
    return 0.0


def mentions_any(text, terms):
    blob = normalize(text)
    return any(normalize(term) in blob for term in terms)


def mentions_all(text, terms):
    blob = normalize(text)
    return all(normalize(term) in blob for term in terms)


def count_mentions(text, term_groups):
    hits = 0
    for group in term_groups:
        if isinstance(group, str):
            group = [group]
        if mentions_any(text, group):
            hits += 1
    return hits, len(term_groups)


def extract_code(answer):
    if not answer:
        return ""
    fences = re.findall(r"```(?:python)?\n(.*?)```", answer, flags=re.S | re.I)
    if fences:
        return textwrap.dedent(max(fences, key=len)).strip()
    if re.search(r"^\s*(import |from |def |class |assert )", answer, re.M):
        return textwrap.dedent(answer).strip()
    return ""


def syntax_valid(code):
    if not code:
        return False
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def split_files(value):
    return [part.strip() for part in re.split(r"[;|,]", value or "") if part.strip()]


def invented_files(answer, expected):
    expected_names = {Path(item).name.lower() for item in expected}
    expected_paths = {item.lower() for item in expected}
    found = set(re.findall(r"[A-Za-z0-9_./-]+\.(?:py|jsx|js|ts|tsx)", answer or ""))
    invented = []
    for item in found:
        name = Path(item).name.lower()
        path = item.replace("\\", "/").lower()
        if path in expected_paths or name in expected_names:
            continue
        if any(path.endswith(known.split("/", 1)[-1]) or Path(known).name.lower() == name for known in KNOWN_FILES):
            continue
        invented.append(item)
    return invented


def score_hallucination(answer, row, context, correctness):
    """0 = none, 0.5 = minor, 1 = significant unsupported claim."""
    reasons = []
    expected = split_files(row.get("relevant_files"))
    invented = invented_files(answer, expected)
    blob = normalize(answer)
    context_blob = normalize(context)

    if invented:
        reasons.append(f"mentioned files not in expected/known set: {invented[:5]}")

    forbidden = [
        "mongodb",
        "pinecone",
        "elasticsearch",
        "langchain",
        "openai",
        "gpt-4",
        "internet search",
        "web search",
    ]
    extra = [term for term in forbidden if term in blob and term not in context_blob]
    if extra:
        reasons.append(f"unsupported stack claims: {extra}")

    if row["category"] == "RAG":
        money = re.findall(r"(?:rs\.?|inr|₹)\s*[\d,]+", blob)
        if money and not any(item in context_blob for item in money):
            reasons.append("unsupported monetary amount")
        eligibility = ["you are eligible", "you may qualify", "you can claim"]
        if mentions_any(answer, eligibility) and not mentions_any(context, eligibility):
            reasons.append("eligibility claim not present in retrieved context")

    if "100% safe" in blob or "completely eliminates hallucination" in blob:
        reasons.append("absolute safety claim")

    if not reasons:
        # Wrong answer with supporting context is a context-use issue, not hallucination.
        if correctness < 1.0 and context_blob:
            return 0.0, "no unsupported claims; residual error treated as context-use/answer-selection", "rubric"
        return 0.0, "no unsupported factual claims detected", "rubric"

    significant = any("unsupported" in reason or "eligibility" in reason or "monetary" in reason for reason in reasons)
    score = 1.0 if significant and len(reasons) > 1 else 0.5
    if any("monetary" in reason or "eligibility" in reason or "stack" in reason for reason in reasons):
        score = 1.0
    return score, "; ".join(reasons), "rubric"


def score_relevance(answer, row, correctness):
    question = normalize(row["question"])
    blob = normalize(answer)
    if not blob:
        return 0.0, "empty answer", "rubric"
    if correctness == 1.0:
        return 1.0, "answer satisfies correctness criteria for this question", "rubric"
    if correctness == 0.5:
        return 0.5, "partially addresses the asked task", "rubric"
    # Off-topic refusal vs wrong topic
    if "not available in the retrieved" in blob and "rag" not in row["category"].lower():
        return 0.5, "refused instead of answering a repository question", "rubric"
    key_terms = [term for term in re.findall(r"[a-z0-9_]{5,}", question) if term not in {"according", "explain", "which", "write"}]
    overlap = sum(1 for term in key_terms if term in blob)
    if key_terms and overlap / len(key_terms) >= 0.3:
        return 0.5, "shares question terminology but fails correctness", "heuristic"
    return 0.0, "largely irrelevant to the asked task", "rubric"


QUESTION_CHECKS = {
    "E01": [
        ["app.jsx", "analyzeSituation"],
        ["/api/chat"],
        ["main.py", "chat("],
        ["process_question"],
        ["retrieve_documents"],
        ["build_context"],
        ["generate_response"],
        ["fallback", "does not contain enough"],
    ],
    "E02": [
        ["detect_disaster"],
        ["generate_embedding"],
        ["chroma"],
        ["disaster"],
        ["350"],
        ["per-document", "per document", "max_per_document", "max(2"],
    ],
    "E03": [
        ["generate_response"],
        ["prompt", "system instruction", "context"],
        ["ollama"],
        ["question"],
        ["context"],
    ],
    "E04": [
        ["retrieved", "document"],
        ["only", "forbidden", "not invent", "ground"],
        ["fallback", "does not contain enough"],
    ],
    "CR01": [["backend/main.py", "main.py"]],
    "CR02": [["retrieval_service.py"]],
    "CR03": [["llm_service.py"]],
    "CR04": [["embedding_service.py"]],
    "D01": [
        ["app.jsx"],
        ["/api/chat"],
        ["process_question"],
        ["retrieve_documents"],
        ["build_context"],
        ["generate_response"],
    ],
    "D02": [
        ["generate_embedding"],
        ["retrieval_service"],
        ["vector", "chroma", "embedding"],
    ],
    "D03": [
        ["retrieve_documents", "retrieval"],
        ["process_question", "orchestration", "build_context"],
        ["generate_response", "llm_service"],
    ],
    "D04": [
        ["embedding_service"],
        ["retrieval"],
        ["compatible", "regenerat", "chroma", "vector"],
    ],
    "B01": [
        ["threshold", "distance"],
        ["discard", "filter", "reject", "recall", "relevant"],
        ["fallback", "too little", "no document", "insufficient", "miss"],
    ],
    "B02": [
        ["top_k", "top-k", "too low", "few"],
        ["chunk", "context", "omit", "incomplete", "coverage"],
    ],
    "B03": [
        ["hallucin"],
        ["retriev"],
        ["not guarantee", "still", "cannot", "prompt", "incomplete", "misinterpret"],
    ],
    "B04": [
        ["not receive", "missing", "without", "fail to retrieve", "recall"],
        ["fallback", "incomplete", "cannot answer", "hallucin"],
    ],
    "RF01": [
        ["dict", "dictionary", "mapping", "tuple", "list"],
        ["flood"],
        ["earthquake"],
        ["cyclone"],
    ],
    "RF02": [
        ["document"],
        ["authority"],
        ["disaster"],
        ["page"],
        ["content"],
    ],
    "RF03": [
        ["max_per_document", "per-document", "per document"],
        ["top_k", "top_k // 2", "max(2"],
    ],
    "RF04": [
        ["os.environ", "getenv", "environment", "config", "dataclass", "settings"],
        ["llm_model", "model", "temperature", "num_predict"],
    ],
    "RG01": [
        ["relief supplies", "relief supply"],
        ["tent"],
        ["water"],
        ["sanitation"],
        ["transport"],
        ["communication"],
        ["medical"],
    ],
    "RG02": [
        ["relief supplies", "relief supply"],
        ["tent"],
        ["water"],
        ["sanitation"],
        ["transport"],
        ["communication"],
        ["medical"],
    ],
    "RG03": [["cyclone shelter", "cyclone shelters"]],
    "RG04": [
        ["long-term", "long term"],
        ["recovery", "reconstruction"],
    ],
}


def score_correctness_from_checks(answer, question_id):
    groups = QUESTION_CHECKS.get(question_id)
    if not groups:
        return None, "", "rubric"
    hits, total = count_mentions(answer, groups)
    if hits == total:
        return 1.0, f"matched {hits}/{total} required evidence groups", "rubric"
    if hits >= max(1, total // 2):
        return 0.5, f"matched {hits}/{total} required evidence groups", "rubric"
    return 0.0, f"matched {hits}/{total} required evidence groups", "rubric"


def execute_generated_code(question_id, code):
    result = {
        "question_id": question_id,
        "extracted_code": code,
        "syntax_valid": syntax_valid(code),
        "executed": False,
        "passed": False,
        "error_type": None,
        "error": None,
        "stdout": "",
        "stderr": "",
        "task_logic_correctness": 0.0,
        "logic_notes": [],
    }
    if not code:
        result["error_type"] = "no_code"
        result["error"] = "No Python code could be extracted from the answer."
        return result
    if not result["syntax_valid"]:
        result["error_type"] = "syntax"
        result["error"] = "Extracted code failed ast.parse()."
        return result

    notes = []
    blob = code
    if question_id in {"CG01", "CG02"}:
        imported = "detect_disaster" in blob and "retrieval_service" in blob
        uses_fn = "detect_disaster(" in blob
        notes.append(f"imports_detect_disaster={imported}")
        notes.append(f"calls_detect_disaster={uses_fn}")
        if question_id == "CG01":
            flood_query = "flood" in blob.lower()
            expects_flood = bool(re.search(r"""(==|is)\s*['\"]flood['\"]|['\"]flood['\"]""", blob))
            notes.append(f"flood_query={flood_query}")
            notes.append(f"expects_flood={expects_flood}")
            logic = ternary(imported and uses_fn and flood_query and expects_flood, imported or uses_fn)
        else:
            query_strings = re.findall(r"""['\"]([^'\"]+)['\"]""", blob)
            disaster_words = ("flood", "earthquake", "cyclone")
            clean_strings = [
                value
                for value in query_strings
                if value.strip()
                and not any(word in value.lower() for word in disaster_words)
            ]
            has_clean_query = bool(clean_strings) and bool(
                re.search(r"detect_disaster\(\s*(['\"][^'\"]+['\"]|[A-Za-z_]\w*)", blob)
            )
            expects_none = "none" in blob.lower()
            notes.append(f"has_query_call={has_clean_query}")
            notes.append(f"expects_none={expects_none}")
            logic = ternary(imported and uses_fn and expects_none and has_clean_query, imported or uses_fn)
        result["task_logic_correctness"] = logic
    elif question_id == "CG03":
        has_fn = bool(re.search(r"def\s+\w+\s*\(", blob))
        uses_strip = "strip(" in blob
        notes.append(f"defines_function={has_fn}")
        notes.append(f"uses_strip={uses_strip}")
        result["task_logic_correctness"] = ternary(has_fn and uses_strip, has_fn)
    elif question_id == "CG04":
        imported = "build_context" in blob and "orchestration_service" in blob
        calls = "build_context(" in blob
        fields = sum(name in blob for name in ["document", "authority", "disaster", "pages", "content"])
        notes.append(f"imports_build_context={imported}")
        notes.append(f"calls_build_context={calls}")
        notes.append(f"metadata_fields={fields}/5")
        result["task_logic_correctness"] = ternary(imported and calls and fields >= 4, imported or calls)
    result["logic_notes"] = notes

    harness = build_harness(question_id, code)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{question_id}.py"
        path.write_text(harness, encoding="utf-8")
        pythonpath = str(PROJECT_ROOT) + __import__("os").pathsep + str(BACKEND_DIR)
        env = dict(**{**__import__("os").environ, "PYTHONPATH": pythonpath})
        try:
            completed = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=20,
                env=env,
            )
        except subprocess.TimeoutExpired:
            result["executed"] = True
            result["error_type"] = "timeout"
            result["error"] = "Generated code execution exceeded 20 seconds."
            return result

    result["executed"] = True
    result["stdout"] = completed.stdout[-4000:]
    result["stderr"] = completed.stderr[-4000:]
    if unittest_execution_passed(completed):
        result["passed"] = True
        return result

    combined = (completed.stdout + "\n" + completed.stderr).lower()
    if "assertionerror" in combined:
        result["error_type"] = "assertion"
    elif "modulenotfounderror" in combined or "importerror" in combined:
        result["error_type"] = "import"
    elif "syntaxerror" in combined:
        result["error_type"] = "syntax"
    else:
        result["error_type"] = "runtime"
    result["error"] = (completed.stderr or completed.stdout)[-1500:]
    return result


def unittest_execution_passed(completed):
    """Treat a genuine passing unittest run as success.

    V3 bug: generated files that called unittest.main() printed OK to stderr
    and exited 0 before the harness could print TEST_PASS. Those runs were
    incorrectly marked as runtime failures even though the tests passed.
    """
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    blob = f"{stdout}\n{stderr}"
    if completed.returncode == 0 and "TEST_PASS" in stdout:
        return True
    if completed.returncode not in (0, None):
        return False
    if re.search(r"FAILED\s*\(", blob) or "AssertionError" in blob:
        return False
    if "ModuleNotFoundError" in blob or "ImportError" in blob:
        return False
    if "SyntaxError" in blob:
        return False
    if re.search(r"(^|\n)OK(\n|$)", blob) and "Ran " in blob:
        return True
    return False


def build_harness(question_id, code):
    backend = str(BACKEND_DIR)
    project = str(PROJECT_ROOT)
    if question_id == "CG03":
        return f"""
import sys
sys.path.insert(0, {project!r})
sys.path.insert(1, {backend!r})
_generated = {code!r}
_namespace = {{"__name__": "generated_submission"}}
exec(compile(_generated, "<generated>", "exec"), _namespace)

candidates = [
    name for name, obj in list(_namespace.items())
    if callable(obj) and not name.startswith("_")
]
fn = None
for name in candidates:
    fn = _namespace[name]
    break
if fn is None:
    raise SystemExit("NO_FUNCTION")
def _invalid(value):
    out = fn(value)
    if isinstance(out, bool):
        return out is True
    return bool(out)
assert _invalid("") or fn("") in (True, False, None)
# Treat True as invalid/empty OR False as valid depending on documented behavior.
empty_out = fn("")
space_out = fn("   ")
ok_out = fn("flood relief query")
# Accept either "True means invalid" or "False means invalid".
def is_empty_flag(value):
    if value in (True, 1, "invalid", "empty"):
        return True
    if value in (False, 0, "valid"):
        return False
    return bool(value) if not isinstance(value, str) else len(str(value).strip()) == 0
# Prefer strip-based functions that return boolean.
if type(empty_out) is bool:
    # True = invalid or False = invalid? Distinguish using ok_out.
    empty_is_invalid_true = empty_out is True and space_out is True and ok_out is False
    empty_is_invalid_false = empty_out is False and space_out is False and ok_out is True
    assert empty_is_invalid_true or empty_is_invalid_false
else:
    assert fn("").strip() == "" if isinstance(fn(""), str) else True
print("TEST_PASS")
"""
    return f"""
import sys
import inspect
import ast
import unittest
sys.path.insert(0, {project!r})
sys.path.insert(1, {backend!r})
_orig_main = unittest.main
def _safe_main(*args, **kwargs):
    kwargs["exit"] = False
    return _orig_main(*args, **kwargs)
unittest.main = _safe_main
_generated = {code!r}
_namespace = {{"__name__": "generated_submission"}}
try:
    exec(compile(_generated, "<generated>", "exec"), _namespace)
except SystemExit as exc:
    if exc.code not in (0, None):
        raise
_ran = False
_classes = [
    obj for obj in list(_namespace.values())
    if inspect.isclass(obj) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase
]
if _classes:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(_classes[0])
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stderr).run(suite)
    _ran = True
    if not result.wasSuccessful():
        raise SystemExit(1)
else:
    for _name, _obj in list(_namespace.items()):
        if _name.startswith("test_") and callable(_obj):
            try:
                _obj()
            except TypeError:
                continue
            _ran = True
if not _ran and not any(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(_generated))):
    raise SystemExit("NO_EXECUTABLE_TEST")
print("TEST_PASS")
"""


def score_codegen(answer, question_id):
    code = extract_code(answer)
    execution = execute_generated_code(question_id, code)
    if execution["passed"]:
        correctness = 1.0
        note = "generated code executed successfully against the real repository"
        method = "measured"
    elif execution["task_logic_correctness"] == 1.0 and execution["error_type"] == "import":
        correctness = 0.5
        note = "task logic matched the rubric but execution failed on import/path integration"
        method = "rubric+measured"
    elif execution["task_logic_correctness"] >= 0.5:
        correctness = 0.5
        note = f"partial task logic; execution error={execution['error_type']}"
        method = "rubric+measured"
    elif execution["syntax_valid"]:
        correctness = 0.5 if execution["task_logic_correctness"] == 0.5 else 0.0
        note = "syntactically valid but did not satisfy the task rubric"
        method = "rubric+measured"
    else:
        correctness = 0.0
        note = execution["error"] or "no executable code"
        method = "measured"
    return correctness, note, method, execution


def score_record(record, row):
    answer = record.get("answer") or ""
    context = record.get("retrieved_context") or ""
    execution = None
    if not record.get("success"):
        return {
            "model": record["model"],
            "question_id": record["question_id"],
            "category": row["category"],
            "correctness": None,
            "relevance": None,
            "hallucination": None,
            "correctness_method": "excluded_failed_generation",
            "relevance_method": "excluded_failed_generation",
            "hallucination_method": "excluded_failed_generation",
            "correctness_rationale": record.get("error"),
            "relevance_rationale": "failed generation excluded from quality averages",
            "hallucination_rationale": "failed generation excluded from quality averages",
            "success": False,
            "codegen": None,
        }

    if row["category"] == "Code Generation":
        correctness, c_note, c_method, execution = score_codegen(answer, row["id"])
    else:
        correctness, c_note, c_method = score_correctness_from_checks(answer, row["id"])
        if row["id"] == "CR02" and mentions_any(answer, ["retrieval_service.py"]):
            if mentions_any(answer, ["backend/rag/retrieval.py"]) and not mentions_any(
                answer, ["active", "current", "services/retrieval"]
            ):
                correctness = min(correctness, 0.5)
                c_note += "; older rag/ path mentioned without identifying the active service"

    relevance, r_note, r_method = score_relevance(answer, row, correctness)
    hallucination, h_note, h_method = score_hallucination(answer, row, context, correctness)

    return {
        "model": record["model"],
        "question_id": record["question_id"],
        "category": row["category"],
        "correctness": correctness,
        "relevance": relevance,
        "hallucination": hallucination,
        "correctness_method": c_method,
        "relevance_method": r_method,
        "hallucination_method": h_method,
        "correctness_rationale": c_note,
        "relevance_rationale": r_note,
        "hallucination_rationale": h_note,
        "success": True,
        "codegen": execution,
        "human_review": {
            "required": row["category"] in {"Refactoring", "Explanation", "Bug Analysis"},
            "status": "optional_override_not_applied",
            "note": (
                "Automatic rubric scores are used. A reviewer may override "
                "individual items using results/human_review_template.csv "
                "without changing raw model answers."
            ),
        },
    }


def aggregate(scores):
    by_model = defaultdict(list)
    by_cat = defaultdict(list)
    codegen = defaultdict(list)
    for item in scores:
        if item["correctness"] is None:
            continue
        by_model[item["model"]].append(item)
        by_cat[(item["model"], item["category"])].append(item)
        if item["category"] == "Code Generation" and item.get("codegen"):
            codegen[item["model"]].append(item["codegen"])

    def summarize(group):
        return {
            "n": len(group),
            "correctness": round(mean(x["correctness"] for x in group), 4),
            "relevance": round(mean(x["relevance"] for x in group), 4),
            "hallucination": round(mean(x["hallucination"] for x in group), 4),
            "hallucination_rate_significant": round(
                mean(1 if x["hallucination"] >= 1.0 else 0 for x in group), 4
            ),
            "hallucination_rate_any": round(
                mean(1 if x["hallucination"] > 0 else 0 for x in group), 4
            ),
        }

    codegen_summary = {}
    for model, rows in codegen.items():
        executable = [row for row in rows if row.get("syntax_valid")]
        passed = [row for row in rows if row.get("passed")]
        codegen_summary[model] = {
            "n": len(rows),
            "syntax_valid": sum(1 for row in rows if row.get("syntax_valid")),
            "executed": sum(1 for row in rows if row.get("executed")),
            "passed": len(passed),
            "test_pass_rate": round(len(passed) / len(executable), 4) if executable else None,
            "functional_pass_rate": round(len(passed) / len(rows), 4) if rows else None,
            "mean_task_logic_correctness": round(
                mean(row.get("task_logic_correctness") or 0 for row in rows), 4
            ),
            "error_types": {
                error: sum(1 for row in rows if row.get("error_type") == error)
                for error in sorted({row.get("error_type") for row in rows if row.get("error_type")})
            },
        }

    return {
        "score_definitions": {
            "correctness": "1.0 fully satisfies the dataset rubric, 0.5 partial, 0.0 incorrect. Failed generations are excluded.",
            "relevance": "1.0 directly answers, 0.5 partial, 0.0 largely irrelevant.",
            "hallucination": "0 none, 0.5 minor unsupported claim, 1 significant unsupported claim. Wrong selection from retrieved context is not counted as hallucination.",
            "test_pass_rate": "passed generated-code tests / syntactically valid generated-code tests",
            "task_logic_correctness": "rubric over required imports, function use, inputs, and expected values, independent of import-path execution. CG02 accepts detect_disaster(query) when a nearby string assignment is a non-disaster query, not only inline string literals.",
            "codegen_execution": "A generated unittest that reports OK and exit code 0 is a pass even if unittest.main() exited before the harness printed TEST_PASS. This corrects a V3 scoring bug; it does not change the dataset rubric.",
        },
        "models": {model: summarize(group) for model, group in by_model.items()},
        "by_category": {
            f"{model}::{category}": summarize(group)
            for (model, category), group in by_cat.items()
        },
        "code_generation": codegen_summary,
    }


def write_human_review_template(scores):
    path = V4_RESULTS_DIR / "human_review_template.csv"
    V4_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "question_id",
        "category",
        "automatic_correctness",
        "automatic_relevance",
        "automatic_hallucination",
        "manual_correctness",
        "manual_relevance",
        "manual_hallucination",
        "reviewer_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in scores:
            writer.writerow(
                {
                    "model": item["model"],
                    "question_id": item["question_id"],
                    "category": item["category"],
                    "automatic_correctness": item["correctness"],
                    "automatic_relevance": item["relevance"],
                    "automatic_hallucination": item["hallucination"],
                    "manual_correctness": "",
                    "manual_relevance": "",
                    "manual_hallucination": "",
                    "reviewer_notes": "",
                }
            )


def main():
    dataset = load_dataset()
    records = json.loads(RAW_RESULTS_FILE.read_text(encoding="utf-8"))
    scores = [score_record(record, dataset[record["question_id"]]) for record in records]
    codegen_rows = [item["codegen"] | {"model": item["model"], "question_id": item["question_id"]} for item in scores if item.get("codegen")]
    output = {
        "per_question": scores,
        "aggregates": aggregate(scores),
    }
    QUALITY_SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_SCORES_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    CODEGEN_RESULTS_FILE.write_text(json.dumps(codegen_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    write_human_review_template(scores)
    print(f"Wrote {QUALITY_SCORES_FILE}")
    print(f"Wrote {CODEGEN_RESULTS_FILE}")
    for model, values in output["aggregates"]["models"].items():
        print(
            f"{model}: correctness={values['correctness']} "
            f"relevance={values['relevance']} "
            f"hallucination={values['hallucination']}"
        )


if __name__ == "__main__":
    main()
