import sys
import ast
from pathlib import Path
import requests
import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text:latest"

CHROMA_PATH = PROJECT_ROOT / "vector_store"
COLLECTION_NAME = "disaster_relief_code"

SOURCE_DIRS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "frontend" / "src",
]

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx"
}

EXCLUDED_PARTS = {
    "venv",
    "node_modules",
    "__pycache__",
}


def should_include(path):
    if path.suffix not in ALLOWED_EXTENSIONS:
        return False

    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False

    if path.name == "__init__.py":
        return False

    return True


def get_source_files():
    files = []

    for directory in SOURCE_DIRS:
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file() and should_include(path):
                    files.append(path)

    return sorted(files)


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


def chunk_python_code(text):
    """
    Function/class-aware chunking for Python.
    Falls back to line-based chunks if AST parsing fails.
    """

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return chunk_generic_code(text)

    lines = text.splitlines()
    chunks = []

    # Capture top-level functions/classes and methods.
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        )
    ]

    # Sort by source position.
    nodes.sort(key=lambda node: (node.lineno, node.end_lineno))

    used_ranges = []

    if nodes:
        module_text = "\n".join(lines[: max(0, nodes[0].lineno - 1)]).strip()
        if module_text:
            chunks.append(
                {
                    "name": "<module>",
                    "type": "module",
                    "text": module_text,
                }
            )

    for node in nodes:
        start = max(0, node.lineno - 1)
        end = min(len(lines), node.end_lineno)

        code = "\n".join(lines[start:end])

        if not code.strip():
            continue

        # Avoid duplicate nested method chunks when they are already
        # contained completely inside a larger class chunk.
        is_contained = False

        for previous_start, previous_end in used_ranges:
            if start >= previous_start and end <= previous_end:
                is_contained = True
                break

        if is_contained:
            continue

        chunks.append(
            {
                "name": getattr(node, "name", "code"),
                "type": type(node).__name__,
                "text": code,
            }
        )

        used_ranges.append((start, end))

    # Capture important imports / top-level code if needed.
    if not chunks:
        return chunk_generic_code(text)

    return chunks


def chunk_javascript(text):
    """Extract function/component-like blocks from JS/JSX files."""
    import re

    lines = text.splitlines()
    pattern = re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
        r"^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:\(|function)"
    )
    starts = []
    for index, line in enumerate(lines):
        match = pattern.search(line.strip())
        if match:
            name = match.group(1) or match.group(2) or "code"
            starts.append((index, name))

    if not starts:
        return chunk_generic_code(text)

    chunks = []
    module_text = "\n".join(lines[: starts[0][0]]).strip()
    if module_text:
        chunks.append(
            {
                "name": "<module>",
                "type": "module",
                "text": module_text,
            }
        )
    for i, (start, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        code = "\n".join(lines[start:end]).strip()
        if code:
            chunks.append(
                {
                    "name": name,
                    "type": "function",
                    "text": code,
                }
            )
    return chunks or chunk_generic_code(text)


def chunk_generic_code(text, chunk_size=1200, overlap=200):
    """
    Generic line-based chunking for JavaScript/JSX/TypeScript
    and Python fallback.
    """

    lines = text.splitlines()
    chunks = []

    current = []
    current_length = 0

    for line in lines:
        line_length = len(line) + 1

        if current and current_length + line_length > chunk_size:
            chunks.append(
                {
                    "name": "code",
                    "type": "code",
                    "text": "\n".join(current),
                }
            )

            overlap_lines = []
            overlap_length = 0

            for previous_line in reversed(current):
                overlap_lines.insert(0, previous_line)
                overlap_length += len(previous_line) + 1

                if overlap_length >= overlap:
                    break

            current = overlap_lines
            current_length = overlap_length

        current.append(line)
        current_length += line_length

    if current:
        chunks.append(
            {
                "name": "code",
                "type": "code",
                "text": "\n".join(current),
            }
        )

    return [chunk for chunk in chunks if chunk["text"].strip()]


def python_import_path(relative_path, symbol=None):
    path = Path(str(relative_path))
    if path.suffix != ".py":
        return None
    module = ".".join(path.with_suffix("").parts)
    if symbol and symbol not in {"<module>", "code"}:
        return f"from {module} import {symbol}"
    return f"import {module}"


def create_chunks(file_path):
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    if file_path.suffix == ".py":
        return chunk_python_code(text)

    if file_path.suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return chunk_javascript(text)

    return chunk_generic_code(text)


def main():

    print("=" * 70)
    print("Week 4 - Improved Repository Code Indexing")
    print("=" * 70)

    source_files = get_source_files()

    print(f"\nSource files found: {len(source_files)}")

    for path in source_files:
        print(f"  - {path.relative_to(PROJECT_ROOT)}")

    client = chromadb.PersistentClient(
        path=str(CHROMA_PATH)
    )

    # Only replace the repository collection.
    try:
        client.delete_collection(COLLECTION_NAME)
        print(
            f"\nExisting '{COLLECTION_NAME}' "
            "collection deleted."
        )
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description":
                "Repository source code for Week 4 evaluation",
            "embedding_model":
                EMBEDDING_MODEL,
            "chunking":
                "function-aware",
        },
    )

    documents = []
    embeddings = []
    metadatas = []
    ids = []

    counter = 0

    print("\nCreating function-aware code chunks...")

    for file_path in source_files:

        relative_path = file_path.relative_to(
            PROJECT_ROOT
        )

        chunks = create_chunks(file_path)

        print(
            f"  {relative_path}: "
            f"{len(chunks)} chunks"
        )

        for chunk_number, chunk in enumerate(chunks):

            relative = str(relative_path)
            execution_path = (
                "legacy" if relative.startswith("backend/rag/") else "live"
            )
            import_hint = python_import_path(relative, chunk["name"])
            embedding_text = (
                f"FILE PATH: {relative}\n"
                f"LANGUAGE: {file_path.suffix}\n"
                f"SYMBOL: {chunk['name']}\n"
                f"CODE TYPE: {chunk['type']}\n"
                f"EXECUTION PATH: {execution_path}\n"
            )
            if import_hint:
                embedding_text += f"PYTHON IMPORT: {import_hint}\n"
            embedding_text += f"\n{chunk['text']}"

            try:
                embedding = generate_embedding(
                    embedding_text
                )
            except Exception as e:
                print(
                    f"ERROR embedding "
                    f"{relative_path} "
                    f"chunk {chunk_number}: {e}"
                )
                continue

            documents.append(embedding_text)
            embeddings.append(embedding)

            metadatas.append(
                {
                    "file_path": str(relative_path),
                    "language": file_path.suffix,
                    "symbol": chunk["name"],
                    "code_type": chunk["type"],
                    "chunk_number": chunk_number,
                    "execution_path": execution_path,
                    "python_import": import_hint or "",
                }
            )

            ids.append(
                f"repo_code_{counter}"
            )

            counter += 1

    print(
        f"\nAdding {len(documents)} chunks "
        "to Chroma..."
    )

    batch_size = 100

    for start in range(
        0,
        len(documents),
        batch_size
    ):
        end = start + batch_size

        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )

        print(
            f"  Added chunks "
            f"{start + 1}-"
            f"{min(end, len(documents))}"
        )

    print("\n" + "=" * 70)
    print("Improved repository indexing complete")
    print("=" * 70)

    print(
        f"Collection:       {COLLECTION_NAME}"
    )
    print(
        f"Files indexed:    {len(source_files)}"
    )
    print(
        f"Chunks indexed:   {len(documents)}"
    )
    print(
        f"Embedding model:  {EMBEDDING_MODEL}"
    )
    print(
        f"Chunking:         Function/class-aware"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
