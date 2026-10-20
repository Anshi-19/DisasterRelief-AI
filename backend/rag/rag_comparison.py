import sys
import requests

from .retrieval import retrieve
from .rag_service import build_context


OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "codellama:latest"


def ask_codellama_without_rag(question):

    prompt = f"""
Answer the following question.

Question:
{question}

Answer:
"""

    response = requests.post(
        OLLAMA_GENERATE_URL,
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        },
        timeout=180
    )

    response.raise_for_status()

    return response.json()["response"].strip()


def ask_codellama_with_rag(question):

    results = retrieve(question, top_k=8)

    if not results:
        return (
            "The retrieved knowledge base does not contain enough "
            "information to answer this question."
        ), []

    context = build_context(results)

    prompt = f"""
You are DisasterRelief AI, a document-grounded question answering system.

IMPORTANT:
You must answer using ONLY the supplied knowledge-base context.

Do not use outside knowledge.

Do not invent:
- government schemes
- eligibility requirements
- financial amounts
- procedures
- contact information
- deadlines
- legal requirements

If the context does not contain enough information to answer the
question, say exactly:

"The retrieved knowledge base does not contain enough information
to answer this question."

Preserve numerical values and conditions exactly as they appear
in the context.

Identify the source document and page number when making factual claims.

================ KNOWLEDGE BASE CONTEXT ================

{context}

================ END KNOWLEDGE BASE CONTEXT ================

QUESTION:

{question}

Provide a concise answer based ONLY on the retrieved context.

ANSWER:
"""

    response = requests.post(
        OLLAMA_GENERATE_URL,
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        },
        timeout=180
    )

    response.raise_for_status()

    answer = response.json()["response"].strip()

    return answer, results


def main():

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = (
            "My house was damaged by a flood. "
            "What assistance may be relevant?"
        )

    print("\n" + "=" * 80)
    print("EXERCISE 3 — RAG VS NON-RAG COMPARISON")
    print("=" * 80)

    print("\nQUESTION:")
    print(question)

    # --------------------------------------------------
    # WITHOUT RAG
    # --------------------------------------------------

    print("\n" + "-" * 80)
    print("1. CODE LLAMA WITHOUT RAG")
    print("-" * 80)

    non_rag_answer = ask_codellama_without_rag(question)

    print("\nRESPONSE:")
    print(non_rag_answer)

    # --------------------------------------------------
    # WITH RAG
    # --------------------------------------------------

    print("\n" + "-" * 80)
    print("2. CODE LLAMA WITH RAG")
    print("-" * 80)

    rag_answer, sources = ask_codellama_with_rag(question)

    print("\nRESPONSE:")
    print(rag_answer)

    # --------------------------------------------------
    # RETRIEVED SOURCES
    # --------------------------------------------------

    print("\n" + "-" * 80)
    print("RETRIEVED SOURCES")
    print("-" * 80)

    if not sources:
        print("\nNo relevant sources retrieved.")
    else:
        for index, source in enumerate(sources, start=1):

            metadata = source["metadata"]

            print(
                f"\n[{index}] "
                f"{metadata['document']} | "
                f"Authority: {metadata['authority']} | "
                f"Pages: {metadata['pages']} | "
                f"Disaster: {metadata['disaster']}"
            )

    # --------------------------------------------------
    # PIPELINE
    # --------------------------------------------------

    print("\n" + "=" * 80)
    print("RAG PIPELINE")
    print("=" * 80)

    print("""
User Question
      ↓
Query Embedding
      ↓
ChromaDB Vector Similarity
      ↓
Relevant Document Chunks
      ↓
Knowledge-Base Context
      ↓
Context + Question
      ↓
Ollama API
      ↓
Code Llama
      ↓
Grounded Response
""")

    print("=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()