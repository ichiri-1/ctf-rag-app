from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.settings import settings


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def load_index(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text(encoding="utf-8"))


def save_index(index_path: Path, chunks: list[dict[str, Any]]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ingest_documents(index_path: Path, documents: list[dict[str, Any]]) -> dict[str, int]:
    existing = load_index(index_path)

    pending_chunks: list[dict[str, Any]] = []
    texts_to_embed: list[str] = []

    for doc in documents:
        doc_id = doc["id"]
        text = doc["text"]
        metadata = doc.get("metadata", {})

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            pending_chunks.append(
                {
                    "doc_id": doc_id,
                    "chunk_id": f"{doc_id}-{i}",
                    "text": chunk,
                    "metadata": metadata,
                }
            )
            texts_to_embed.append(chunk)

    if texts_to_embed:
        model = get_embedder()
        embeddings = model.encode(
            texts_to_embed,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        for item, emb in zip(pending_chunks, embeddings, strict=False):
            item["embedding"] = emb.tolist()

    all_chunks = existing + pending_chunks
    save_index(index_path, all_chunks)

    return {
        "documents": len(documents),
        "new_chunks": len(pending_chunks),
        "total_chunks": len(all_chunks),
    }


def retrieve(index_path: Path, question: str, top_k: int = 3) -> list[dict[str, Any]]:
    chunks = load_index(index_path)
    if not chunks:
        return []

    model = get_embedder()
    query_embedding = model.encode(
        question,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    ranked: list[tuple[dict[str, Any], float]] = []
    query_vec = np.array(query_embedding, dtype=np.float32)

    for chunk in chunks:
        emb = np.array(chunk["embedding"], dtype=np.float32)
        score = float(np.dot(query_vec, emb))
        ranked.append((chunk, score))

    ranked.sort(key=lambda x: x[1], reverse=True)

    results: list[dict[str, Any]] = []
    for chunk, score in ranked[:top_k]:
        item = {k: v for k, v in chunk.items() if k != "embedding"}
        item["score"] = score
        results.append(item)

    return results