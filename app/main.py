from __future__ import annotations

from functools import lru_cache
from typing import Any

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.rag import ingest_documents, retrieve
from app.settings import settings

app = FastAPI(title="paper-rag-template", version="0.1.0")

class DocumentIn(BaseModel):
    id: str = Field(..., description="Document identifier")
    text: str = Field(..., description="Raw document text")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[DocumentIn]


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None


@lru_cache(maxsize=1)
def get_tokenizer() -> Any:
    tokenizer = AutoTokenizer.from_pretrained(settings.generation_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer

@lru_cache(maxsize=1)
def get_generator() -> Any:
    return AutoModelForCausalLM.from_pretrained(settings.generation_model)


def build_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No context found."

    lines = []
    for item in results:
        lines.append(f"[{item['chunk_id']}] {item['text']}")
    return "\n".join(lines)


def fallback_answer(question: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return "関連する文書がまだありません。先に /ingest で文書を登録してください。"

    context = build_context(results)
    return (
        "生成モデルを使わずに、取得コンテキストをそのまま返します。\n\n"
        f"質問:\n{question}\n\n"
        f"取得コンテキスト:\n{context}"
    )

def postprocess_answer(text: str) -> str:
    text = text.strip()

    stop_markers = [
        "質問:",
        "コンテキスト:",
        "文書:",
        "回答例:",
        "###",
    ]
    for marker in stop_markers:
        if marker in text:
            text = text.split(marker)[0].strip()

    return text

def generate_answer(question: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return fallback_answer(question, results)

    context = build_context(results)

    prompt = f"""以下の文書だけを根拠に、日本語で2文以内で簡潔に答えてください。
分からない場合は「分かりません」と答えてください。
根拠に使った chunk_id を最後に1つ以上書いてください。

質問:
{question}

文書:
{context}

回答:
"""

    tokenizer = get_tokenizer()
    model = get_generator()

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=768,
    )

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=settings.max_new_tokens,
            do_sample=False,
            repetition_penalty=settings.repetition_penalty,
            no_repeat_ngram_size=settings.no_repeat_ngram,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    answer = tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
    answer = postprocess_answer(answer)

    if not answer:
        return fallback_answer(question, results)

    return answer


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(payload: IngestRequest) -> dict[str, int]:
    docs = [doc.model_dump() for doc in payload.documents]
    return ingest_documents(docs)


@app.post("/query")
def query(payload: QueryRequest) -> dict[str, Any]:
    top_k = payload.top_k or settings.retrieval_top_k
    results = retrieve(payload.question, top_k)
    answer = generate_answer(payload.question, results)
    return {
        "answer": answer,
        "sources": results,
    }