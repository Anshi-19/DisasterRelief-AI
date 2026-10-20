import requests

from .retrieval import retrieve


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

LLM_MODEL = "codellama:latest"


INSUFFICIENT_ANSWER = (
    "The retrieved knowledge base does not contain enough information "
    "to answer this question."
)


def build_context(results):
    """
    Convert retrieved results into structured context for the LLM.
    """

    context_parts = []

    for index, result in enumerate(results, start=1):

        metadata = result["metadata"]

        source = (
            f"[SOURCE {index}]\n"
            f"Document: {metadata['document']}\n"
            f"Authority: {metadata['authority']}\n"
            f"Disaster: {metadata['disaster']}\n"
            f"Page(s): {metadata['pages']}\n"
        )

        context_parts.append(
            source
            + "\n"
            + "CONTENT:\n"
            + result["text"]
            + "\n[END SOURCE]"
        )

    return "\n\n".join(context_parts)


def select_relevant_evidence(question, results):
    """
    Select the most relevant retrieved passages.

    Retrieval already ranks the documents by semantic similarity.
    This function additionally prioritizes passages containing
    important terms from the user's question.
    """

    if not results:
        return []

    question_lower = question.lower()

    # Important terms from the user's question.
    keywords = [
        word.strip(".,?!")
        for word in question_lower.split()
        if len(word.strip(".,?!")) >= 4
    ]

    scored = []

    for result in results:

        text = result["text"].lower()

        keyword_score = 0

        for keyword in keywords:

            if keyword in text:
                keyword_score += 1

        # Lower Chroma distance means stronger semantic similarity.
        distance = result["distance"]

        scored.append(
            (
                keyword_score,
                -distance,
                result
            )
        )

    # Highest keyword score first.
    # Then strongest semantic similarity.
    scored.sort(
        key=lambda item: (
            item[0],
            item[1]
        ),
        reverse=True
    )

    # Keep only the strongest evidence.
    selected = [
        item[2]
        for item in scored[:4]
    ]

    return selected


def has_direct_evidence(question, results):
    """
    Determine whether the retrieved text contains obvious evidence
    related to the question.

    This is intentionally conservative.

    It does NOT determine legal eligibility or assistance eligibility.
    It only checks whether the retrieved documents contain language
    relevant enough to send to the LLM.
    """

    if not results:
        return False

    question_lower = question.lower()

    # ---------------------------------------------------------
    # House damage questions
    # ---------------------------------------------------------

    house_terms = [
        "house",
        "home",
        "housing",
        "building"
    ]

    damage_terms = [
        "damaged",
        "damage",
        "destroyed",
        "collapsed"
    ]

    assistance_terms = [
        "assistance",
        "relief",
        "rehabilitation",
        "recovery",
        "reconstruction",
        "shelter",
        "relief camps",
        "basic amenities"
    ]

    asks_about_house = any(
        term in question_lower
        for term in house_terms
    )

    asks_about_damage = any(
        term in question_lower
        for term in damage_terms
    )

    asks_about_assistance = any(
        term in question_lower
        for term in assistance_terms
    )

    if asks_about_house and asks_about_damage:

        for result in results:

            text = result["text"].lower()

            if (
                "houses have been damaged" in text
                or "houses have been damaged by floods" in text
                or "houses have been damaged by an earthquake" in text
                or "damaged by floods" in text
                or "damaged by an earthquake" in text
            ):
                return True

    if asks_about_assistance:

        for result in results:

            text = result["text"].lower()

            if any(
                term in text
                for term in assistance_terms
            ):
                return True

    # ---------------------------------------------------------
    # General question matching
    # ---------------------------------------------------------

    question_words = [
        word.strip(".,?!")
        for word in question_lower.split()
        if len(word.strip(".,?!")) >= 5
    ]

    for result in results:

        text = result["text"].lower()

        matches = sum(
            1
            for word in question_words
            if word in text
        )

        if matches >= 2:
            return True

    return False


def generate_answer(question, context):

    prompt = f"""
You are DisasterRelief AI.

You are a document-grounded question answering system.

The KNOWLEDGE BASE below is your ONLY source of factual information.

Do NOT use general knowledge.

Do NOT use your pretrained knowledge.

Do NOT invent facts.

Do NOT make assumptions.

Do NOT invent eligibility.

Do NOT invent financial assistance.

Do NOT invent government schemes.

Do NOT invent procedures.

Do NOT invent contact information.

Do NOT invent deadlines.

============================================================
KNOWLEDGE BASE
============================================================

{context}

============================================================
USER QUESTION
============================================================

{question}

============================================================
ANSWERING RULES
============================================================

1. Answer ONLY from the supplied knowledge base.

2. Only include information that directly answers the question.

3. Do not summarize unrelated retrieved passages.

4. If the source describes what a government agency,
   hospital, NGO, community, or response team does,
   describe it as THEIR action.

5. Do NOT turn an organization's action into an instruction
   for the user unless the source explicitly tells the user
   to perform that action.

6. Never say the user is eligible for assistance unless the
   retrieved source explicitly establishes eligibility for
   that exact situation.

7. Preserve numerical values exactly.

8. Distinguish between:
   - immediate relief
   - rehabilitation
   - recovery
   - reconstruction

9. Do not combine different disasters unless the sources
   explicitly support doing so.

10. If the question asks what the user should do but the
    retrieved documents only describe government or
    organizational response, say that the retrieved
    knowledge base does not specify additional user actions.

11. Keep the answer concise.

12. Prefer 2-4 bullet points when multiple directly relevant
    facts are available.

13. Mention the supporting document and page number.

14. Do not repeat the question.

15. Do not write reasoning or analysis.

If the knowledge base does not contain enough information,
respond exactly:

The retrieved knowledge base does not contain enough information to answer this question.

============================================================
FINAL ANSWER
============================================================
"""

    response = requests.post(
        OLLAMA_GENERATE_URL,
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 220
            }
        },
        timeout=180
    )

    response.raise_for_status()

    return response.json()["response"].strip()


def clean_answer(answer):
    """
    Remove accidental formatting generated by the LLM.
    """

    if "ANSWER:" in answer:
        answer = answer.split("ANSWER:", 1)[1]

    if "GROUNDING:" in answer:
        answer = answer.split("GROUNDING:", 1)[0]

    return answer.strip()


def remove_unsupported_eligibility(answer):
    """
    Remove explicit unsupported eligibility claims.
    """

    forbidden_phrases = [
        "you may be eligible",
        "the user may be eligible",
        "you are eligible",
        "the user is eligible",
        "may be eligible for",
        "eligible for assistance",
        "eligible for relief",
        "eligible to receive",
        "you can claim assistance",
        "you can claim relief",
        "the user can claim assistance",
        "the user can claim relief",
    ]

    lines = answer.splitlines()

    cleaned_lines = []

    for line in lines:

        lower_line = line.lower()

        if any(
            phrase in lower_line
            for phrase in forbidden_phrases
        ):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def answer_question(question, top_k=8):

    # ---------------------------------------------------------
    # 1. Retrieve
    # ---------------------------------------------------------

    results = retrieve(
        question,
        top_k=top_k
    )

    # ---------------------------------------------------------
    # 2. No retrieval results
    # ---------------------------------------------------------

    if not results:

        return {
            "question": question,
            "answer": INSUFFICIENT_ANSWER,
            "sources": []
        }

    # ---------------------------------------------------------
    # 3. Select strongest evidence
    # ---------------------------------------------------------

    evidence = select_relevant_evidence(
        question,
        results
    )

    # ---------------------------------------------------------
    # 4. Check whether evidence actually relates
    # ---------------------------------------------------------

    if not has_direct_evidence(
        question,
        evidence
    ):

        return {
            "question": question,
            "answer": INSUFFICIENT_ANSWER,
            "sources": [
                {
                    "document": result["metadata"]["document"],
                    "authority": result["metadata"]["authority"],
                    "pages": result["metadata"]["pages"],
                    "disaster": result["metadata"]["disaster"],
                    "distance": result["distance"]
                }
                for result in evidence
            ]
        }

    # ---------------------------------------------------------
    # 5. Build smaller, focused context
    # ---------------------------------------------------------

    context = build_context(evidence)

    # ---------------------------------------------------------
    # 6. Generate grounded answer
    # ---------------------------------------------------------

    answer = generate_answer(
        question,
        context
    )

    # ---------------------------------------------------------
    # 7. Clean answer
    # ---------------------------------------------------------

    answer = clean_answer(answer)

    answer = remove_unsupported_eligibility(answer)

    # ---------------------------------------------------------
    # 8. Final response
    # ---------------------------------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": [
            {
                "document": result["metadata"]["document"],
                "authority": result["metadata"]["authority"],
                "pages": result["metadata"]["pages"],
                "disaster": result["metadata"]["disaster"],
                "distance": result["distance"]
            }
            for result in evidence
        ]
    }


if __name__ == "__main__":

    import sys

    if len(sys.argv) > 1:

        question = " ".join(sys.argv[1:])

    else:

        question = (
            "My house was damaged by a flood. "
            "What kind of assistance or relief may be relevant?"
        )

    result = answer_question(question)

    print("\n" + "=" * 70)
    print("RAG RESPONSE")
    print("=" * 70)

    print("\nQUESTION:")
    print(result["question"])

    print("\nANSWER:")
    print(result["answer"])

    print("\nSOURCES:")

    if not result["sources"]:

        print("No relevant sources retrieved.")

    else:

        for source in result["sources"]:

            print(
                f"- {source['document']} | "
                f"Pages: {source['pages']} | "
                f"Disaster: {source['disaster']}"
            )