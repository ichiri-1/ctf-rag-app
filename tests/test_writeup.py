from unittest.mock import patch


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


def test_create_and_get(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        resp = client.post("/api/writeups", json={
            "title": "XOR Image",
            "ctf_name": "picoCTF 2025",
            "category": "crypto",
            "tags": ["xor", "png"],
            "markdown_content": "## Problem\nBroken PNG.\n## Solution\nXOR key=0x42.",
        })
    assert resp.status_code == 200
    writeup_id = resp.json()["id"]

    resp = client.get(f"/api/writeups/{writeup_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["title"] == "XOR Image"
    assert detail["category"] == "crypto"
    assert "markdown_content" in detail


def test_list_with_filters(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        client.post("/api/writeups", json={
            "title": "Web SQLi",
            "ctf_name": "DEF CON 33",
            "category": "web",
            "tags": ["sqli"],
            "markdown_content": "## Problem\nSQL injection.",
        })
        client.post("/api/writeups", json={
            "title": "Crypto XOR",
            "ctf_name": "picoCTF 2025",
            "category": "crypto",
            "tags": ["xor"],
            "markdown_content": "## Problem\nXOR decrypt.",
        })

    resp = client.get("/api/writeups/list")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/api/writeups/list?category=web")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["category"] == "web"

    resp = client.get("/api/writeups/list?q=pico")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["ctf_name"] == "picoCTF 2025"


def test_delete(client) -> None:
    with patch("app.rag._embed", side_effect=_fake_embed):
        resp = client.post("/api/writeups", json={
            "title": "To Delete",
            "ctf_name": "test",
            "category": "misc",
            "tags": [],
            "markdown_content": "## Problem\nTest.",
        })
    writeup_id = resp.json()["id"]

    resp = client.delete(f"/api/writeups/{writeup_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/writeups/{writeup_id}")
    assert resp.status_code == 404


def test_get_not_found(client) -> None:
    resp = client.get("/api/writeups/nonexistent-id")
    assert resp.status_code == 404
