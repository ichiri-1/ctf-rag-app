# テスト用に一時ディレクトリを使用(data/chroma/に書き込まれないようにするため)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))

    # settings と get_chroma_collection のキャッシュをリセット
    from app import settings as settings_module
    settings_module.settings = settings_module.Settings()

    import app.rag as rag_module
    rag_module.get_chroma_collection.cache_clear()

    from app.main import app
    return TestClient(app)
