from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.rag import _openai_client, search
from app.settings import settings
from app.writeup import create, delete, get, list_writeups

app = FastAPI(title="CTF Recall", version="0.1.0")


# --- リクエストモデル ---

class WriteupIn(BaseModel):
    title: str
    ctf_name: str
    category: str
    tags: list[str]
    markdown_content: str


class SearchIn(BaseModel):
    query_text: str
    notes: str = ""


class HintIn(BaseModel):
    query_text: str
    notes: str = ""
    retrieved_ids: list[str]


# --- ヘルス ---

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Writeup CRUD ---

@app.post("/api/writeups")
def create_writeup(payload: WriteupIn) -> dict[str, str]:
    writeup_id = create(
        title=payload.title,
        ctf_name=payload.ctf_name,
        category=payload.category,
        tags=payload.tags,
        markdown_content=payload.markdown_content,
    )
    return {"id": writeup_id, "message": "created"}


# NOTE: /api/writeups/list を /{writeup_id} より先に定義する（FastAPI のルート順序）
@app.get("/api/writeups/list")
def list_writeups_endpoint(
    category: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    return list_writeups(category=category, q=q)


@app.get("/api/writeups/{writeup_id}")
def get_writeup(writeup_id: str) -> dict[str, Any]:
    result = get(writeup_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Writeup not found")
    return result


@app.delete("/api/writeups/{writeup_id}")
def delete_writeup(writeup_id: str) -> dict[str, str]:
    if not delete(writeup_id):
        raise HTTPException(status_code=404, detail="Writeup not found")
    return {"message": "deleted"}


# --- 検索 ---

@app.post("/api/search")
def search_writeups(payload: SearchIn) -> dict[str, Any]:
    results = search(query_text=payload.query_text, notes=payload.notes)

    from app.writeup import _load_index
    index = {e["id"]: e for e in _load_index()}

    enriched = []
    for r in results:
        entry = index.get(r["id"], {})
        enriched.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "tags": entry.get("tags", []),
            "summary": entry.get("summary", ""),
            "distance": r["distance"],
        })

    return {"results": enriched}


# --- ヒント生成 ---

_HINT_SYSTEM_PROMPT = """\
あなたは CTF の解法想起を助けるアシスタントです。
過去の類似 Writeup を参考に、現在の問題に対する短いヒントを JSON 形式で返してください。

出力形式（必ずこの JSON のみ）:
{
  "common_points": ["..."],
  "suspicious_methods": ["..."],
  "next_actions": ["..."]
}

- common_points: 過去問と現在の問題の共通パターン（2〜3件）
- suspicious_methods: 疑うべき攻撃・解析手法（3〜5件）
- next_actions: 今すぐ試すべき具体的なアクション（3〜5件）
長文不要。箇条書きで簡潔に。"""


@app.post("/api/hint")
def generate_hint(payload: HintIn) -> dict[str, Any]:
    writeup_contents = []
    for wid in payload.retrieved_ids:
        entry = get(wid)
        if entry:
            writeup_contents.append(
                f"### {entry['title']} ({entry['category']})\n{entry['markdown_content'][:1000]}"
            )

    if not writeup_contents:
        raise HTTPException(status_code=400, detail="有効な Writeup が見つかりません")

    user_message = (
        f"現在の問題:\n{payload.query_text}\n\n"
        f"メモ:\n{payload.notes}\n\n"
        f"参考にする過去の Writeup:\n" + "\n\n".join(writeup_contents)
    )

    response = _openai_client().chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": _HINT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        hint = json.loads(content)
    except json.JSONDecodeError:
        hint = {"common_points": [], "suspicious_methods": [], "next_actions": [content]}

    return hint


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
