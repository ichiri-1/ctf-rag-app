from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.rag import add_writeup, chunk_markdown
from app.rag import delete_writeup as rag_delete_writeup
from app.settings import settings

_BUCKET = "writeups"


@lru_cache(maxsize=1)
def _supabase() -> Client:
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )


def _extract_summary(markdown_content: str) -> str:
    body = re.sub(r"^---\n.*?\n---\n?", "", markdown_content, flags=re.DOTALL)
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return ""


def create(title: str, ctf_name: str, category: str, tags: list[str], markdown_content: str) -> str:
    writeup_id = str(uuid.uuid4())
    filename = f"{writeup_id}.md"

    _supabase().storage.from_(_BUCKET).upload(
        path=filename,
        file=markdown_content.encode("utf-8"),
        file_options={"content-type": "text/markdown"},
    )

    chunks = chunk_markdown(markdown_content)
    add_writeup(writeup_id, chunks, title, category)

    _supabase().table("writeups").insert({
        "id": writeup_id,
        "title": title,
        "ctf_name": ctf_name,
        "category": category,
        "tags": tags,
        "summary": _extract_summary(markdown_content),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
    }).execute()

    return writeup_id


def get(writeup_id: str) -> dict[str, Any] | None:
    resp = _supabase().table("writeups").select("*").eq("id", writeup_id).execute()
    if not resp.data:
        return None
    entry = resp.data[0]

    content_bytes: bytes = _supabase().storage.from_(_BUCKET).download(entry["filename"])

    return {
        "id": writeup_id,
        "title": entry["title"],
        "ctf_name": entry["ctf_name"],
        "category": entry["category"],
        "tags": entry["tags"],
        "created_at": entry["created_at"],
        "markdown_content": content_bytes.decode("utf-8"),
    }


def list_writeups(category: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    query = _supabase().table("writeups").select(
        "id, title, ctf_name, category, tags, summary, created_at"
    )
    if category:
        query = query.eq("category", category)

    entries: list[dict[str, Any]] = query.execute().data

    if q:
        q_lower = q.lower()
        entries = [
            e for e in entries
            if q_lower in e.get("title", "").lower()
            or q_lower in e.get("ctf_name", "").lower()
            or any(q_lower in tag.lower() for tag in e.get("tags", []))
        ]

    return entries


def _load_index() -> list[dict[str, Any]]:
    """main.py の search エンドポイントとの互換用"""
    return _supabase().table("writeups").select(
        "id, title, ctf_name, category, tags, summary, created_at"
    ).execute().data


def delete(writeup_id: str) -> bool:
    resp = _supabase().table("writeups").select("filename").eq("id", writeup_id).execute()
    if not resp.data:
        return False

    filename = resp.data[0]["filename"]

    rag_delete_writeup(writeup_id)
    _supabase().storage.from_(_BUCKET).remove([filename])
    _supabase().table("writeups").delete().eq("id", writeup_id).execute()

    return True
