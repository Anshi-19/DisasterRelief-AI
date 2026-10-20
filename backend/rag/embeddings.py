import json
from pathlib import Path

import chromadb
import requests


BASE_DIR = Path(__file__).resolve().parents[2]

CHUNKS_FILE = BASE_DIR / "vector_store" / "chunks.json"
CHROMA_DIR = BASE_DIR / "vector_store" / "chroma_db"

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

COLLECTION_NAME = "disaster_relief"


def get_embedding(text: str):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["embedding"]


def main():
    print("Loading chunks...")

    with open(CHUNKS_FILE, "r", encoding="utf-8") as file:
        chunks = json.load(file)

    print(f"Chunks loaded: {len(chunks)}")

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "DisasterRelief AI knowledge base"
        }
    )

    total = len(chunks)

    for index, item in enumerate(chunks):

        embedding = get_embedding(item["text"])

        metadata = item["metadata"]

        document_id = (
            f"{metadata['disaster']}_"
            f"{metadata['chunk']}_"
            f"{index}"
        )

        collection.upsert(
            ids=[document_id],
            documents=[item["text"]],
            embeddings=[embedding],
            metadatas=[metadata]
        )

        if (index + 1) % 25 == 0 or index == total - 1:
            print(
                f"Embedded {index + 1}/{total}"
            )

    print("\n" + "=" * 50)
    print("EMBEDDING COMPLETE")
    print("=" * 50)
    print(f"Total vectors: {collection.count()}")
    print(f"Database: {CHROMA_DIR}")


if __name__ == "__main__":
    main()