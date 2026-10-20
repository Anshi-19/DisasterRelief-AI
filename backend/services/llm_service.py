import time
import re
import requests


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
LLM_MODEL = "codellama:latest"


FALLBACK_RESPONSE = (
    "The retrieved knowledge base does not contain enough information "
    "to answer this question."
)

INSUFFICIENT_MARKERS = (
    "no_supported_information",
    "does not contain enough information",
    "does not contain any information",
    "not explicitly mentioned in the context",
    "not explicitly stated in the retrieved",
    "not explicitly stated in the context",
    "not available in the retrieved knowledge base",
    "can't assist with that",
    "cannot assist with that",
)

FOCUS_STOP_WORDS = {
    "according", "and", "are", "does", "for", "from", "guidelines", "information",
    "is", "in", "of", "provided", "the", "this", "to", "what", "which", "with",
}

FOCUS_RANKING_STOP_WORDS = FOCUS_STOP_WORDS | {
    "cyclone", "earthquake", "flood", "relevant",
}


SYSTEM_INSTRUCTION = """
You are DisasterRelief AI.
Answer only from the retrieved knowledge-base evidence supplied by the
backend. The evidence has already passed a deterministic answerability
check.

Produce a polished answer, not an evidence dump:
- Start with a short, direct answer to what the user needs to know.
- Synthesize only facts that directly answer the question.
- Use 2-6 concise Markdown bullets when several items improve readability.
- For an ordinary assistance question, usually stay within 80-180 words.
- Paraphrase the evidence. Do not copy full sentences, paragraphs, raw
  excerpts, source blocks, or metadata into the answer.
- Do not repeat a fact in both quoted and summarized form.
- Ignore retrieved passages that are unrelated to the question.
- A passage is not relevant merely because it mentions the same disaster
  type. Include only concrete assistance, services, measures, or facts
  that directly address what the user asked.
- Use no more than six bullets. Do not inventory every retrieved source.
- Do not add outside knowledge, unsupported details, or assumptions.
- Do not add a source inventory or raw source labels. The frontend shows
  source documents and pages in a separate Evidence Explorer.
- If only part of the question is supported, answer that part and briefly
  state what is unavailable.
- Use headings only when they genuinely improve a longer answer.
"""


ALLOWED_MODELS = {
    "codellama:latest",
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
}


def resolve_model(model: str | None):
    if not model:
        return LLM_MODEL
    if model not in ALLOWED_MODELS:
        raise ValueError(
            f"Unsupported model '{model}'. Allowed: {sorted(ALLOWED_MODELS)}"
        )
    return model


def _stem_focus_tokens(tokens):
    expanded = set(tokens)
    for token in tokens:
        if token.endswith("ies") and len(token) > 5:
            expanded.add(token[:-3] + "y")
        if token.endswith("es") and len(token) > 4:
            expanded.add(token[:-2])
        if token.endswith("s") and len(token) > 3:
            expanded.add(token[:-1])
        if token.endswith("ing") and len(token) > 5:
            expanded.add(token[:-3])
        if token.endswith("ed") and len(token) > 4:
            expanded.add(token[:-2])
    return expanded


def build_focus_excerpt(question: str, context: str, limit: int = 1200):
    question_terms = _stem_focus_tokens(
        {
            token
            for token in re.findall(r"[a-z0-9]+", question.lower())
            if len(token) > 2 and token not in FOCUS_RANKING_STOP_WORDS
        }
    )
    passages = re.split(r"(?<=[.!?])\s+|\n+", context)
    ranked = []
    for position, passage in enumerate(passages):
        cleaned = passage.strip()
        if len(cleaned) < 30:
            continue
        passage_terms = _stem_focus_tokens(set(re.findall(r"[a-z0-9]+", cleaned.lower())))
        overlap = len(question_terms & passage_terms)
        if overlap:
            ranked.append((overlap, -position, cleaned))

    selected = []
    characters = 0
    for _, _, passage in sorted(ranked, reverse=True):
        if passage in selected:
            continue
        if characters + len(passage) > limit:
            continue
        selected.append(passage)
        characters += len(passage)
        if len(selected) >= 6:
            break
    return "\n".join(f"- {passage}" for passage in selected)


def query_focus_support(question: str, context: str):
    normalized = question.lower().strip()
    if normalized.startswith("according to ") and "," in normalized:
        normalized = normalized.split(",", 1)[1]
    normalized = re.sub(r"^(what|which|who|where|when|how)\s+", "", normalized)
    normalized = re.split(r"\s+(?:in|of|from)\s+", normalized, maxsplit=1)[0]
    focus_terms = _stem_focus_tokens(
        {
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if len(token) > 3 and token not in FOCUS_STOP_WORDS
        }
    )
    context_terms = _stem_focus_tokens(set(re.findall(r"[a-z0-9]+", context.lower())))
    matched_focus = sorted(focus_terms & context_terms)
    return bool(matched_focus), sorted(focus_terms), matched_focus


def response_focus_instruction(question: str):
    normalized = question.lower()
    housing = any(
        term in normalized
        for term in ("house", "houses", "housing", "home", "homes", "damaged")
    )
    if any(term in normalized for term in ("assistance", "support", "relief")):
        housing_line = ""
        if housing:
            housing_line = (
                " The user asked about a damaged house. Prefer evidence about "
                "relief camps, shelter, housing, reconstruction, and supplies "
                "for displaced households. Do not lead with medical, epidemic, "
                "or mosquito-control measures unless the user asked about "
                "health or that is the only supported assistance."
            )
        return (
            "This is an assistance question. Include only concrete aid, "
            "services, supplies, or response support that directly benefits "
            "affected people. Exclude general policy, education, research, "
            "documentation, institutional background, and management studies."
            + housing_line
        )
    return (
        "Include only facts or measures that directly address the specific "
        "subject of the question; omit broader background on the disaster."
    )


def clean_response(question: str, answer: str):
    lines = answer.splitlines()
    cleaned = []
    bullet_count = 0
    assistance_question = any(
        term in question.lower() for term in ("assistance", "support", "relief")
    )
    irrelevant_assistance_markers = (
        "capacity development",
        "curricul",
        "documentation",
        "education",
        "management studies",
        "research",
    )
    meta_markers = (
        "these are the most relevant",
        "the answer is based on the evidence",
        "the evidence statements",
    )

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith(("sources:", "source list:")):
            break
        if any(marker in lowered for marker in meta_markers):
            continue
        if assistance_question and any(
            marker in lowered for marker in irrelevant_assistance_markers
        ):
            continue
        if re.match(r"^(?:[-*+]|\d+[.)])\s+", stripped):
            bullet_count += 1
            if bullet_count > 6:
                continue
        cleaned.append(line.rstrip())

    result = "\n".join(cleaned).strip().strip('"')
    if re.match(r"^(?:[-*+]|\d+[.)])\s+", result):
        result = "Based on the retrieved evidence:\n\n" + result
    return result or FALLBACK_RESPONSE


def generate_response(question: str, context: str, model: str | None = None):
    selected_model = resolve_model(model)
    print(f"[MODEL] {selected_model}", flush=True)
    print(f"[CONTEXT] characters={len(context)}", flush=True)

    focus_excerpt = build_focus_excerpt(question, context)
    _, _, matched_focus = query_focus_support(question, context)
    user_prompt = f"""
{SYSTEM_INSTRUCTION}

RELEVANCE FILTER:
{response_focus_instruction(question)}

Use only the evidence below. The backend answerability check found these
core question terms in the evidence: {", ".join(matched_focus)}.
Write a concise synthesis of the relevant facts. The focused passages are
internal reading aids only: do not quote or enumerate them as evidence.

INTERNAL RELEVANCE HINTS:
{focus_excerpt}

EVIDENCE:

{context}

END EVIDENCE

QUESTION:
{question}

ANSWER:
"""

    print("[GENERATION] started", flush=True)
    start = time.perf_counter()
    response = requests.post(
        OLLAMA_CHAT_URL,
        json={
            "model": selected_model,
            "messages": [
                {"role": "user", "content": user_prompt},
                {
                    "role": "assistant",
                    "content": (
                        "A concise answer with no more than six distinct, "
                        f"directly relevant {', '.join(matched_focus)} items is:"
                    ),
                },
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 220,
                "num_ctx": 4096,
            }
        },
        timeout=180
    )

    response.raise_for_status()
    latency = round(time.perf_counter() - start, 3)

    data = response.json()
    answer = ((data.get("message") or {}).get("content") or "").strip()
    prompt_tokens = data.get("prompt_eval_count")
    generated_tokens = data.get("eval_count")
    eval_duration_ns = data.get("eval_duration")
    throughput = None
    if generated_tokens and eval_duration_ns:
        seconds = eval_duration_ns / 1e9
        if seconds > 0:
            throughput = round(generated_tokens / seconds, 3)
    total_tokens = None
    if prompt_tokens is not None and generated_tokens is not None:
        total_tokens = prompt_tokens + generated_tokens

    if not answer:
        answer = FALLBACK_RESPONSE
    elif any(marker in answer.lower() for marker in INSUFFICIENT_MARKERS):
        answer = FALLBACK_RESPONSE
    else:
        answer = clean_response(question, answer)

    print("[GENERATION] completed", flush=True)
    print(f"[OUTPUT] tokens={generated_tokens}", flush=True)

    return {
        "answer": answer,
        "model": selected_model,
        "response_latency": latency,
        "prompt_tokens": prompt_tokens,
        "generated_tokens": generated_tokens,
        "total_tokens": total_tokens,
        "throughput": throughput,
    }