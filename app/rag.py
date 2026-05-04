from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.settings import settings


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key.get_secret_value())

@lru_cache(maxsize=1)
def _qdrant_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key.get_secret_value())


def _embed(texts: list[str]) -> list[list[float]]:
    resp = _openai_client().embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in resp.data]

def _ensure_collection() -> None:
    client = _qdrant_client()
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )


def chunk_markdown(content: str) -> list[str]:
    """## ヘッダー単位で Markdown をチャンク分割する。frontmatter は除去する"""
    body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL).strip()
    if not body:
        return []
    
    sections = re.split(r"(?=^## )", body, flags=re.MULTILINE)
    return [s.strip() for s in sections if s.strip()]


def add_writeup(writeup_id: str, chunks: list[str], title: str, category: str) -> None:
    """Writeup のチャンクを qdrant に追加する"""
    if not chunks:
        return
    
    _ensure_collection()
    embeddings = _embed(chunks)
    point = [
        PointStruct(
            id = abs(hash(f"{writeup_id}_{i}")) % (2**63),
            vector=emb,
            payload={
                "writeup_id": writeup_id,
                "title": title,
                "category": category,
                "chunk_index": i,
                "text": chunk,
            },
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    _qdrant_client().upsert(
        collection_name=settings.qdrant_collection,
        points=point,
    )

def delete_writeup(writeup_id: str) -> None:
    """writeup_id に紐づく全チャンクを qdrant から削除する"""

    _qdrant_client().delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[FieldCondition(key="writeup_id", match=MatchValue(value=writeup_id))]
        ),
    )


def search(query_text: str, notes: str = "", k: int | None = None) -> list[dict[str, Any]]:
    """クエリに類似する Writeup を返す。writeup 単位で集約する"""
    
    _ensure_collection()
    top_k = k or settings.retrieval_top_k
    combined_query = f"{query_text}\n{notes}".strip()
    query_vec = _embed([combined_query])[0]

    results = _qdrant_client().query_points(
        collection_name=settings.qdrant_collection,
        query=query_vec,
        limit=top_k*3,
        with_payload=True,
    )

    # writeup_id ごとに最小 distance で集約
    best: dict[str, dict[str, Any]] = {}
    for hit in results.points:
        payload = hit.payload or {}
        wid = payload.get("writeup_id", "")
        score = hit.score # コサイン類似度
        if wid not in best or score > best[wid]["distance"]:
            best[wid] = {
                "id": wid,
                "title": payload.get("title", ""),
                "category": payload.get("category", ""),
                "distance": score,
            }
    return sorted(best.values(), key=lambda x: x["distance"], reverse=True)[:top_k]