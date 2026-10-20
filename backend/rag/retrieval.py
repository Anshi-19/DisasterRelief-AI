import chromadb
import requests
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

CHROMA_DIR = BASE_DIR / "vector_store" / "chroma_db"

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

COLLECTION_NAME = "disaster_relief"


def get_query_embedding(query: str):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": query
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["embedding"]


def detect_disaster(query: str):

    query_lower = query.lower()

    if "earthquake" in query_lower:
        return "earthquake"

    if "flood" in query_lower:
        return "flood"

    if "cyclone" in query_lower:
        return "cyclone"

    return None


def retrieve(query: str, top_k: int = 8):

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    collection = client.get_collection(
        COLLECTION_NAME
    )

    query_embedding = get_query_embedding(query)

    disaster = detect_disaster(query)

    candidate_count = max(top_k * 5, 30)

    if disaster:

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_count,
            where={"disaster": disaster}
        )

    else:

        # Only perform generic retrieval when the query is clearly
        # related to disaster management.
        disaster_terms = [
            "disaster",
            "relief",
            "rehabilitation",
            "recovery",
            "reconstruction",
            "evacuation",
            "rescue",
            "damage",
            "damaged",
            "affected",
            "emergency",
            "victim",
            "house",
            "property",
            "compensation",
            "assistance",
            "aid",
            "response",
            "flood",
            "earthquake",
            "cyclone"
        ]

        if not any(term in query.lower() for term in disaster_terms):
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_count
        )

    candidates = []

    query_words = set(
        word.lower().strip(".,?!")
        for word in query.split()
        if len(word) > 3
    )

    important_words = {
        "house",
        "houses",
        "home",
        "homes",
        "damaged",
        "damage",
        "assistance",
        "relief",
        "recovery",
        "reconstruction",
        "financial",
        "repair",
        "rehabilitation"
    }

    for i in range(len(results["documents"][0])):

        text = results["documents"][0][i]
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        text_lower = text.lower()

        keyword_matches = sum(
            1
            for word in query_words
            if word in text_lower
        )

        important_matches = sum(
            1
            for word in important_words
            if word in text_lower
            and word in query_words
        )

        # Lower is better.
        # Semantic distance remains the main signal,
        # while keyword matches provide a relevance boost.
        score = (
            distance
            - (keyword_matches * 8)
            - (important_matches * 12)
        )

        candidates.append(
            {
                "text": text,
                "metadata": metadata,
                "distance": distance,
                "score": score
            }
        )

    candidates.sort(
        key=lambda x: x["score"]
    )

    selected = []
    document_counts = {}

    max_per_document = max(2, top_k // 2)

    for candidate in candidates:

        document = candidate["metadata"]["document"]

        count = document_counts.get(document, 0)

        if count >= max_per_document:
            continue

        selected.append(candidate)

        document_counts[document] = count + 1

        if len(selected) >= top_k:
            break

    return selected

if __name__ == "__main__":

    import sys

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = (
            "My house was damaged by a flood. "
            "What kind of assistance or relief may be relevant?"
        )

    disaster = detect_disaster(question)

    print(f"\nQUESTION: {question}")
    print(f"DETECTED DISASTER: {disaster or 'generic'}")

    results = retrieve(question)

    print("\n" + "=" * 70)
    print("RETRIEVAL RESULTS")
    print("=" * 70)

    for index, result in enumerate(results, start=1):

        print(f"\n--- RESULT {index} ---")

        print("Distance:", result["distance"])

        print("Disaster:", result["metadata"]["disaster"])

        print("Authority:", result["metadata"]["authority"])

        print("Document:", result["metadata"]["document"])

        print("Pages:", result["metadata"]["pages"])

        print("\nText:")
        print(result["text"][:1000])