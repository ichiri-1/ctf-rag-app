from __future__ import annotations

from functools import lru_cache
from typing import Any

import chromadb
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

@lru_cache(maxsize=1)
def get_chroma_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},

    )

def ingest_documents(documents: list[dict[str, Any]]) -> dict[str, int]:
    collection = get_chroma_collection()
    model = get_embedder()
    
    ids: list[str] = []
    embeddings: list[list[float]] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for doc in documents:
        doc_id = doc["id"]
        metadata = doc.get("metadata", {})

        for i, chunk in enumerate(chunk_text(doc["text"])):
            ids.append(f"{doc_id}-{i}")
            texts.append(chunk)
            metadatas.append({"doc_id": doc_id, **metadata})
        
    if not ids:
        return {"documents": 0, "new_chunks": 0, "total_chunks": collection.count()}

    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    embeddings = [v.tolist() for v in vecs]

    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    return {
        "documents": len(documents),
        "new_chunks": len(ids),
        "total_chunks": collection.count(),
    }


def retrieve(question: str, top_k: int = 3) -> list[dict[str, Any]]:
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []

    model = get_embedder()
    query_vec = model.encode(question, normalize_embeddings=True, show_progress_bar=False)

    results = collection.query(
        query_embeddings=[query_vec.tolist()],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    output: list[dict[str, Any]] = []
    for chunk_id, text, meta, distance in zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "chunk_id": chunk_id,
            "text": text,
            "metadata": meta,
            "score": 1 - distance,  # コサイン距離 → 類似度に変換
        })

    return output
