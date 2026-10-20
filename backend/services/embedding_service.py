import requests


OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text:latest"


def generate_embedding(text: str):

    response = requests.post(
        OLLAMA_EMBEDDING_URL,
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text
        },
        timeout=120
    )

    response.raise_for_status()

    return response.json()["embedding"]