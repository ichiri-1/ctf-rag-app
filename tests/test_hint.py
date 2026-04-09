import json
from unittest.mock import MagicMock, patch


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


def _mock_openai_client(hint_json: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = hint_json
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_hint_generation(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        resp = client.post("/api/writeups", json={
            "title": "PNG XOR",
            "ctf_name": "picoCTF 2025",
            "category": "crypto",
            "tags": ["xor"],
            "markdown_content": "## Problem\nBroken PNG.\n## Solution\nXOR.",
        })
    writeup_id = resp.json()["id"]

    hint_json = json.dumps({
        "common_points": ["ファイルヘッダが重要"],
        "suspicious_methods": ["単純XOR", "PNGシグネチャ確認"],
        "next_actions": ["先頭16バイト確認", "既知ヘッダとXOR比較"],
    })

    # main.py は app.rag._openai_client を import しているため app.main._openai_client をパッチ
    with patch("app.main._openai_client", return_value=_mock_openai_client(hint_json)):
        resp = client.post("/api/hint", json={
            "query_text": "壊れたPNGが与えられた",
            "notes": "XORっぽい",
            "retrieved_ids": [writeup_id],
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "common_points" in body
    assert "suspicious_methods" in body
    assert "next_actions" in body
    assert len(body["next_actions"]) >= 1


def test_hint_invalid_ids(client) -> None:
    resp = client.post("/api/hint", json={
        "query_text": "test",
        "notes": "",
        "retrieved_ids": ["nonexistent-id"],
    })
    assert resp.status_code == 400
