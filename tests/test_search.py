from unittest.mock import patch


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


def test_search_returns_results(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        client.post("/api/writeups", json={
            "title": "PNG XOR",
            "ctf_name": "picoCTF 2025",
            "category": "crypto",
            "tags": ["xor", "png"],
            "markdown_content": "## Problem\nBroken PNG.\n## Solution\nXOR key found.",
        })

    with patch("app.rag._embed", side_effect=_fake_embed):
        resp = client.post("/api/search", json={
            "query_text": "壊れたPNG",
            "notes": "XORっぽい",
        })

    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert len(body["results"]) >= 1
    result = body["results"][0]
    assert "id" in result
    assert "title" in result
    assert "distance" in result
    assert "summary" in result
    assert "tags" in result


def test_search_empty_db(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        resp = client.post("/api/search", json={
            "query_text": "some query",
            "notes": "",
        })
    assert resp.status_code == 200
    assert resp.json()["results"] == []
