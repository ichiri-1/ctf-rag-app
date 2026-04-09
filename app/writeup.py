from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.rag import add_writeup, chunk_markdown
from app.rag import delete_writeup as rag_delete_writeup
from app.settings import settings


def _index_path() -> Path:
    return settings.meta_dir / "index.json"


def _load_index() -> list[dict[str, Any]]:
    path = _index_path()

    if not path.exists():
        return []
    
    return json.loads(path.read_text(encoding="utf-8"))


def _save_index(entries: list[dict[str, Any]]) -> None:
    settings.meta_dir.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _extract_summary(markdown_content: str) -> str:
    """本文の最初の非空・非ヘッダ行を返す"""

    """本文の最初の非空・非ヘッダ行を返す（最大200文字）。"""
    body = re.sub(r"^---\n.*?\n---\n?", "", markdown_content, flags=re.DOTALL)
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:200]
    return ""


def create(title: str, ctf_name: str, category: str, tags: list[str], markdown_content: str) -> str:
    """Writeup を登録して ID を返す"""

    writeup_id = str(uuid.uuid4())

    settings.writeups_dir.mkdir(parents=True, exist_ok=True)
    filepath = settings.writeups_dir / f"{writeup_id}.md"
    filepath.write_text(markdown_content, encoding="utf-8")

    chunks = chunk_markdown(markdown_content)
    add_writeup(writeup_id, chunks, title, category)

    entry: dict[str, Any] = {
        "id": writeup_id,
        "title": title,
        "ctf_name": ctf_name,
        "category": category,
        "tags": tags,
        "summary": _extract_summary(markdown_content),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": f"{writeup_id}.md",
    }
    index = _load_index()
    index.append(entry)
    _save_index(index)

    return writeup_id



def get(writeup_id: str) -> dict[str, Any] | None:
    """Writeup の詳細を返す。存在しない場合は None。"""

    filepath = settings.writeups_dir / f"{writeup_id}.md"

    if not filepath.exists():
        return None

    content = filepath.read_text(encoding="utf-8")
    index = _load_index()
    entry = next((e for e in index if e["id"] == writeup_id), None)
    if entry is None:
        return None

    return {
        "id": writeup_id,
        "title": entry["title"],
        "ctf_name": entry["ctf_name"],
        "category": entry["category"],
        "tags": entry["tags"],
        "created_at": entry["created_at"],
        "markdown_content": content,
    }


def list_writeups(category: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    """Writeup 一覧を返す。category / q でフィルタできる。"""

    entries = _load_index()

    if category:
        entries = [e for e in entries if e.get("category") == category]

    if q:
        q_lower = q.lower()
        entries = [
            e for e in entries
            if q_lower in e.get("title", "").lower()
            or q_lower in e.get("ctf_name", "").lower()
            or any(q_lower in tag.lower() for tag in e.get("tags", []))
        ]

    return entries


def delete(writeup_id: str) -> bool:

    """Writeup を削除する。存在しない場合は False を返す。"""
    
    filepath = settings.writeups_dir / f"{writeup_id}.md"
    if not filepath.exists():
        return False

    rag_delete_writeup(writeup_id)
    filepath.unlink()

    index = _load_index()
    index = [e for e in index if e["id"] != writeup_id]
    _save_index(index)

    return True