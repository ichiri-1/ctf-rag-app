from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_query(client) -> None:
    client = TestClient(app)

    # 先にドキュメントを登録
    client.post("/ingest", json={
        "documents": [
            {
                "id": "test-doc2",
                "text": "FastAPIはPythonの高速なWebフレームワークです。",
                "metadata": {}
            }
        ]
    })

    with patch("app.main.generate_ans_openai", return_value="モック回答"):
        response = client.post("/query", json={
            "question": "FastAPIとは何ですか？",
            "top_k": 1
        })

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert len(body["sources"]) == 1
    assert body["sources"][0]["chunk_id"] == "test-doc2-0"
    assert body["sources"][0]["score"] > 0
