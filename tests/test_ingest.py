from fastapi.testclient import TestClient

from app.main import app


def test_ingest(client) -> None:
    client = TestClient(app)
    response = client.post("/ingest", json={
        "documents": [
            {
                "id": "test-doc1",
                "text": "ChromaDBはローカルで動作する軽量なベクトルデータベースです。",
                "metadata": {"source": "test"}
            }
        ]
    })

    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 1
    assert body["new_chunks"] >= 1
    assert body["total_chunks"] >= 1
