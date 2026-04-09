from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import chromadb
from openai import OpenAI

from app.settings import settings


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key.get_secret_value())


def _embed(texts: list[str]) -> list[list[float]]:
    resp = _openai_client().embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in resp.data]


def chunk_markdown(content: str) -> list[str]:
    """## ヘッダー単位で Markdown をチャンク分割する。frontmatter は除去する"""
    body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL).strip()
    if not body:
        return []
    
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    return [s.strip() for s in sections if s.strip()]


@lru_cache(maxsize=1)
def _get_collection() -> chromadb.Collection:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def add_writeup(writeup_id: str, chunks: list[str], title: str, category: str) -> None:
    """Writeup のチャンクを ChromaDB に追加する"""

    if not chunks:
        return
    
    collection = _get_collection()
    embeddings = _embed(chunks)
    collection.add(
        ids=[f"{writeup_id}_chunk_{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings, # type: ignore[arg-type]
        metadatas=[
            {"writeup_id": writeup_id, "title": title, "category": category, "chunk_index": i}
            for i in range(len(chunks))
        ],
    )


def delete_writeup(writeup_id: str) -> None:
    """writeup_id に紐づく全チャンクを ChromaDB から削除する"""

    collection = _get_collection()
    results = collection.get(where={"writeup_id": writeup_id})

    if results["ids"]:
        collection.delete(ids=results["ids"])


def search(query_text: str, notes: str = "", k: int | None = None) -> list[dict[str, Any]]:
    """クエリに類似する Writeup を返す。writeup 単位で集約する"""

    collection = _get_collection()

    if collection.count() == 0:
        return []

    top_k = k or settings.retrieval_top_k
    combined_query = f"{query_text}\n{notes}".strip()
    query_vec = _embed([combined_query])[0]
    n_results = min(top_k * 3, collection.count())

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=n_results,
        include=["documents", "metadatas", "distances"], # type: ignore[arg-type]
    )

    # writeup_id ごとに最小 distance で集約
    best: dict[str, dict[str, Any]] = {}
    for _chunk_id, text, meta, distance in zip(
        results["ids"][0],
        results["documents"][0],  # type: ignore[index]
        results["metadatas"][0],  # type: ignore[index]
        results["distances"][0],  # type: ignore[index]
    ):
        wid = str(meta["writeup_id"])
        if wid not in best or distance < best[wid]["distance"]:
            best[wid] = {
                "id": wid,
                "title": str(meta.get("title", "")),
                "category": str(meta.get("category", "")),
                "distance": float(distance),
                "matched_chunk": text,
            }

    sorted_results = sorted(best.values(), key=lambda x: x["distance"])
    return sorted_results[:top_k]