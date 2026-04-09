import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import app.rag as rag_module
    import app.settings as settings_module
    import app.writeup as writeup_module

    new_settings = settings_module.Settings()
    monkeypatch.setattr(settings_module, "settings", new_settings)
    monkeypatch.setattr(rag_module, "settings", new_settings)
    monkeypatch.setattr(writeup_module, "settings", new_settings)

    rag_module._get_collection.cache_clear()
    rag_module._openai_client.cache_clear()

    from app.main import app
    return TestClient(app)
