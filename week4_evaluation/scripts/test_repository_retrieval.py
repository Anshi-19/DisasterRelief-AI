import sys
from pathlib import Path
import requests
import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text:latest"

CHROMA_PATH = PROJECT_ROOT / "vector_store"
COLLECTION_NAME = "disaster_relief_code"


def generate_embedding(text):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text,
        },
        timeout=120,
    )

    response.raise_for_status()
    return response.json()["embedding"]


def search_code(question, top_k=5):
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(COLLECTION_NAME)

    embedding = generate_embedding(question)

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
    )

    return results


questions = [
    "Where is the disaster type detected in the application?",
    "Where is the POST /api/chat endpoint defined?",
    "Which file calls retrieve_documents?",
    "Which file contains the Ollama LLM generation logic?",
    "Where is the ChromaDB collection accessed?",
    "Which frontend file sends the chat request to the backend?",
]


print("=" * 70)
print("Repository Retrieval Test")
print("=" * 70)

for question in questions:
    print(f"\nQUESTION: {question}")
    print("-" * 70)

    results = search_code(question)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        print("NO RESULTS")
        continue

    for i, (doc, metadata, distance) in enumerate(
        zip(documents, metadatas, distances),
        start=1,
    ):
        print(
            f"\n{i}. {metadata['file_path']} "
            f"(chunk {metadata['chunk_number']}, distance={distance:.4f})"
        )

        print(doc[:500].replace("\n", " "))
