import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient


class _FakeStorageBucket:
    def __init__(self, files: dict[str, bytes]):
        self._files = files

    def upload(self, path: str, file: bytes, file_options=None):
        self._files[path] = file

    def download(self, path: str) -> bytes:
        return self._files[path]

    def remove(self, paths: list[str]):
        for p in paths:
            self._files.pop(p, None)


class _FakeStorage:
    def __init__(self, files: dict[str, bytes]):
        self._files = files

    def from_(self, bucket: str) -> _FakeStorageBucket:
        return _FakeStorageBucket(self._files)


class _FakeResult:
    def __init__(self, data: list):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: dict, filters: dict | None = None):
        self._rows = rows
        self._filters = filters or {}

    def eq(self, key: str, value) -> "_FakeQuery":
        return _FakeQuery(self._rows, {**self._filters, key: value})

    def execute(self) -> _FakeResult:
        data = [
            row for row in self._rows.values()
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        return _FakeResult(data)


class _FakeInsert:
    def __init__(self, rows: dict, row: dict):
        self._rows = rows
        self._row = row

    def execute(self) -> _FakeResult:
        self._rows[self._row["id"]] = self._row
        return _FakeResult([self._row])


class _FakeDelete:
    def __init__(self, rows: dict, filters: dict | None = None):
        self._rows = rows
        self._filters = filters or {}

    def eq(self, key: str, value) -> "_FakeDelete":
        return _FakeDelete(self._rows, {**self._filters, key: value})

    def execute(self) -> _FakeResult:
        keys = [
            k for k, row in self._rows.items()
            if all(row.get(f) == v for f, v in self._filters.items())
        ]
        for k in keys:
            del self._rows[k]
        return _FakeResult([])


class _FakeTable:
    def __init__(self, rows: dict):
        self._rows = rows

    def select(self, *args) -> _FakeQuery:
        return _FakeQuery(self._rows)

    def insert(self, row: dict) -> _FakeInsert:
        return _FakeInsert(self._rows, row)

    def delete(self) -> _FakeDelete:
        return _FakeDelete(self._rows)


class _FakeSupabase:
    def __init__(self):
        self._rows: dict[str, dict] = {}
        self._files: dict[str, bytes] = {}
        self.storage = _FakeStorage(self._files)

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self._rows)


@pytest.fixture
def client(monkeypatch):
    import app.rag as rag_module
    import app.writeup as writeup_module

    qdrant = QdrantClient(":memory:")
    rag_module._qdrant_client.cache_clear()
    monkeypatch.setattr(rag_module, "_qdrant_client", lambda: qdrant)
    rag_module._openai_client.cache_clear()

    fake_sb = _FakeSupabase()
    writeup_module._supabase.cache_clear()
    monkeypatch.setattr(writeup_module, "_supabase", lambda: fake_sb)

    from app.main import app
    return TestClient(app)
