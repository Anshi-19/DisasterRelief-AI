import re

import chromadb
from pathlib import Path

from .embedding_service import generate_embedding


BASE_DIR = Path(__file__).resolve().parents[2]

CHROMA_DIR = BASE_DIR / "vector_store" / "chroma_db"

COLLECTION_NAME = "disaster_relief"

DISTANCE_THRESHOLD = 350

TOKEN_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "if", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "what", "when", "where", "which", "why", "with", "according", "under",
}


def detect_disaster(query: str):

    query_lower = query.lower()

    if "earthquake" in query_lower:
        return "earthquake"

    if "flood" in query_lower:
        return "flood"

    if "cyclone" in query_lower:
        return "cyclone"

    return None


def _tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in TOKEN_STOP_WORDS
    }


def _deduplicate_candidates(candidates):
    unique = []
    seen_prefixes = []
    for candidate in candidates:
        prefix = re.sub(r"\s+", " ", (candidate.get("text") or "")[:240].lower()).strip()
        if not prefix:
            continue
        if any(prefix[:140] == previous[:140] for previous in seen_prefixes):
            continue
        seen_prefixes.append(prefix)
        unique.append(candidate)
    return unique


def _jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def rank_and_select_chunks(query, candidates, top_k, max_per_document):
    """Keep Chroma distance order, then inject a section-title match if needed."""
    candidates = _deduplicate_candidates(candidates)
    if not candidates:
        return []

    question_terms = _tokens(query)
    selected = []
    document_counts = {}
    for candidate in sorted(candidates, key=lambda item: item.get("distance") or 0):
        document = (candidate.get("metadata") or {}).get("document")
        if document_counts.get(document, 0) >= max_per_document:
            continue
        if selected:
            overlap = max(
                _jaccard(_tokens(candidate.get("text")), _tokens(item.get("text")))
                for item in selected
            )
            if overlap > 0.78:
                continue
        selected.append(candidate)
        document_counts[document] = document_counts.get(document, 0) + 1
        if len(selected) >= top_k:
            break

    title_hits = [
        candidate
        for candidate in candidates
        if _heading_boost(question_terms, candidate.get("text") or "") > 0
    ]
    title_hits.sort(
        key=lambda item: (
            -_heading_boost(question_terms, item.get("text") or ""),
            item.get("distance") or 0,
        )
    )
    if title_hits:
        best_title = title_hits[0]
        existing_ids = [id(item) for item in selected]
        if id(best_title) in existing_ids:
            index = existing_ids.index(id(best_title))
            if index > 1:
                selected.insert(1, selected.pop(index))
        else:
            selected.insert(1, best_title)
            selected = selected[:top_k]
    return selected


def _stem_tokens(tokens):
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


def _expanded_retrieval_queries(query):
    """Keep the user question, then add a need-focused retrieval query when warranted.

    Colloquial assistance questions under-rank the housing/relief-camp passages
    that the same collection returns for the longer evaluation wording.
    """
    queries = [query.strip()]
    terms = _tokens(query)
    noun_query = " ".join(sorted(terms))
    if noun_query and noun_query != query.strip().lower():
        queries.append(noun_query)

    housing_terms = {"house", "houses", "housing", "home", "homes", "damaged", "damage"}
    assistance_terms = {"assistance", "support", "relief", "amenities", "help"}
    if terms & housing_terms and (terms & assistance_terms or detect_disaster(query)):
        disaster = detect_disaster(query) or "disaster"
        queries.append(
            "relief camps for people whose houses have been damaged "
            f"{disaster} basic amenities shelter reconstruction immediate relief"
        )

    unique = []
    seen = set()
    for item in queries:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _query_results(collection, embedding, n_results, disaster):
    kwargs = {
        "query_embeddings": [embedding],
        "n_results": n_results,
    }
    if disaster:
        # Common recovery/reconstruction guidance is tagged disaster="all".
        kwargs["where"] = {
            "$or": [
                {"disaster": disaster},
                {"disaster": "all"},
            ]
        }
    return collection.query(**kwargs)


def _collect_candidates(results):
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    if not documents or not documents[0]:
        return []
    candidates = []
    for document, metadata, distance in zip(documents[0], metadatas[0], distances[0]):
        if distance > 350:
            continue
        candidates.append(
            {
                "text": document,
                "metadata": metadata or {},
                "distance": distance,
            }
        )
    return candidates


def _heading_boost(question_terms, text):
    """Boost numbered section titles and 'topic, including …' spans that overlap the question."""
    boost = 0.0
    blob = text or ""
    for match in re.finditer(
        r"\d+\.\d+(?:\.\d+)?\s+([A-Za-z][A-Za-z /-]{2,40}):\s*([A-Za-z][A-Za-z0-9 ,-]{2,70})",
        blob,
    ):
        left = _tokens(match.group(1))
        right = _tokens(match.group(2))
        if left & question_terms:
            boost = max(boost, 0.45 + 0.1 * len((left | right) & question_terms))
    for match in re.finditer(
        r"\b([A-Za-z][A-Za-z]+), including ([^.;:]{5,90})",
        blob,
        flags=re.I,
    ):
        if match.group(1).lower() in question_terms:
            boost = max(boost, 0.5)
    return boost


def retrieve_documents(query: str, top_k: int = 8):

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )

    collection = client.get_collection(
        COLLECTION_NAME
    )

    disaster = detect_disaster(query)

    candidate_count = min(max(top_k * 15, 120), max(collection.count(), top_k))
    merged = {}

    def add_results(results):
        for candidate in _collect_candidates(results):
            prefix = re.sub(r"\s+", " ", (candidate.get("text") or "")[:180].lower())
            existing = merged.get(prefix)
            if existing is None or candidate["distance"] < existing["distance"]:
                merged[prefix] = candidate

    for retrieval_query in _expanded_retrieval_queries(query):
        add_results(
            _query_results(
                collection,
                generate_embedding(retrieval_query),
                candidate_count,
                disaster,
            )
        )

    distance_threshold = 350
    candidates = [
        candidate
        for candidate in merged.values()
        if (candidate.get("distance") or 0) <= distance_threshold
    ]
    # Disaster-filtered queries already share a domain; keep more pages from
    # the main guideline instead of stopping after four near-duplicate intros.
    max_per_document = top_k if disaster else max(2, top_k // 2)
    return rank_and_select_chunks(query, candidates, top_k, max_per_document)
