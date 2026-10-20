from pathlib import Path
import json
import re

from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE = BASE_DIR / "knowledge_base"
OUTPUT_DIR = BASE_DIR / "vector_store"
OUTPUT_FILE = OUTPUT_DIR / "chunks.json"


DOCUMENTS = [
    {
        "path": KNOWLEDGE_BASE / "common" / "mha_recovery_reconstruction_2024.pdf",
        "disaster": "all",
        "authority": "Ministry of Home Affairs",
        "document": "Guidelines on Constitution and Administration of Recovery and Reconstruction Funding Window",
        "year": 2024,
        "category": "recovery_reconstruction",
        "source_url": "https://www.mha.gov.in/sites/default/files/2024-08/DMGuideline_20082024.pdf",
    },
    {
        "path": KNOWLEDGE_BASE / "flood" / "flood_guidelines.pdf",
        "disaster": "flood",
        "authority": "National Disaster Management Authority",
        "document": "National Disaster Management Guidelines: Management of Floods",
        "year": 2008,
        "category": "preparedness_response_recovery",
        "source_url": "https://nidm.gov.in/pdf/guidelines/floods.pdf",
    },
    {
        "path": KNOWLEDGE_BASE / "cyclone" / "cyclone_guidelines.pdf",
        "disaster": "cyclone",
        "authority": "National Disaster Management Authority",
        "document": "National Disaster Management Guidelines: Management of Cyclones",
        "year": 2010,
        "category": "preparedness_response_recovery",
        "source_url": "https://nidm.gov.in/pdf/guidelines/new/cyclones.pdf",
    },
    {
        "path": KNOWLEDGE_BASE / "earthquake" / "earthquake_guidelines.pdf",
        "disaster": "earthquake",
        "authority": "National Disaster Management Authority",
        "document": "National Disaster Management Guidelines: Management of Earthquakes",
        "year": 2007,
        "category": "preparedness_response_recovery",
        "source_url": "https://nidm.gov.in/pdf/guidelines/new/earthquakes.pdf",
    },
]


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_SIZE = 200


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\u00a0", " ")

    # Normalize Windows/Mac line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive spaces while preserving line structure
    text = re.sub(r"[ \t]+", " ", text)

    # Remove repeated blank lines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # Fix spaces before punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return text.strip()


def extract_pages(pdf_path):
    """Extract non-empty pages from a PDF."""
    reader = PdfReader(str(pdf_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")

        if len(text) >= 50:
            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

    return pages, len(reader.pages)


def split_text(text):
    """Create overlapping chunks while preferring natural boundaries."""
    chunks = []

    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))

        if end < len(text):
            # Prefer paragraph boundary
            boundary = text.rfind("\n\n", start, end)

            # Then sentence boundary
            if boundary == -1:
                boundary = text.rfind(". ", start, end)

            # Then newline
            if boundary == -1:
                boundary = text.rfind("\n", start, end)

            if boundary > start + MIN_CHUNK_SIZE:
                end = boundary

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


def merge_short_chunks(chunks):
    """Merge very short chunks with the following chunk."""
    merged = []
    buffer = ""

    for chunk in chunks:
        if len(chunk) < MIN_CHUNK_SIZE:
            buffer = f"{buffer}\n{chunk}".strip()
        else:
            if buffer:
                chunk = f"{buffer}\n{chunk}".strip()
                buffer = ""

            merged.append(chunk)

    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]}\n{buffer}".strip()
        else:
            merged.append(buffer)

    return merged


def process_document(config):
    path = config["path"]

    if not path.exists():
        print(f"WARNING: File not found: {path}")
        return []

    print(f"\nProcessing: {path.name}")

    pages, total_pages = extract_pages(path)

    # Combine extracted pages into one logical document stream.
    full_text_parts = []
    page_boundaries = []

    current_position = 0

    for item in pages:
        text = item["text"]

        full_text_parts.append(text)

        page_boundaries.append(
            {
                "start": current_position,
                "end": current_position + len(text),
                "page": item["page"],
            }
        )

        current_position += len(text) + 2

    full_text = "\n\n".join(full_text_parts)

    raw_chunks = split_text(full_text)
    chunks = merge_short_chunks(raw_chunks)

    document_chunks = []

    for chunk_index, chunk in enumerate(chunks):

        # Determine which source pages contributed to this chunk.
        chunk_start = full_text.find(chunk)

        if chunk_start == -1:
            page_numbers = []
        else:
            chunk_end = chunk_start + len(chunk)

            page_numbers = [
                item["page"]
                for item in page_boundaries
                if item["start"] < chunk_end
                and item["end"] > chunk_start
            ]

        document_chunks.append(
            {
                "text": chunk,
                "metadata": {
                    "disaster": config["disaster"],
                    "authority": config["authority"],
                    "document": config["document"],
                    "year": config["year"],
                    "category": config["category"],
                    "source_url": config["source_url"],
                    "pages": page_numbers,
                    "chunk": chunk_index,
                },
            }
        )

    print(f"Pages: {total_pages}")
    print(f"Usable pages: {len(pages)}")
    print(f"Chunks: {len(document_chunks)}")

    return document_chunks


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for document in DOCUMENTS:
        all_chunks.extend(process_document(document))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            all_chunks,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\n" + "=" * 50)
    print("INGESTION COMPLETE")
    print("=" * 50)
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()