# CTF Recall

過去の CTF Writeup から解法の方向性を思い出すための RAG アプリ

## 技術スタック

| 役割 | 技術 |
|---|---|
| API | FastAPI |
| 埋め込み・生成 | OpenAI API（`text-embedding-3-small` / `gpt-4o-mini`） |
| ベクトル DB | Qdrant Cloud |
| ファイルストレージ | Supabase Storage |
| メタデータ DB | Supabase PostgreSQL |
| フロントエンド | HTML + CSS + TypeScript（フレームワークなし） |
| 依存管理 | uv |
| 開発環境 | Dev Container + Docker Compose |
| デプロイ | Render |

## 前提条件

- [Docker](https://www.docker.com/)
- [Visual Studio Code](https://code.visualstudio.com/)
- VS Code 拡張: [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- Supabase プロジェクト
- Qdrant Cloud クラスター
- OpenAI API キー

## セットアップ

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd ctf-recall

# 2. 環境変数ファイルを作成
cp .env.example .env
# .env を編集して各サービスの接続情報を設定
```

その後、VS Code で `Reopen in Container` を実行。
コンテナ起動時に `uv sync --dev` が自動実行される。

### Supabase のセットアップ

SQL Editor で以下を実行してテーブルを作成：

```sql
CREATE TABLE writeups (
    id          UUID        PRIMARY KEY,
    title       TEXT        NOT NULL,
    ctf_name    TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    tags        TEXT[]      NOT NULL DEFAULT '{}',
    summary     TEXT        NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filename    TEXT        NOT NULL
);

GRANT ALL ON public.writeups TO service_role;
```

Storage に `writeups` バケットを作成（非公開）。

## アプリの起動

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

起動後、`http://localhost:8000` でフロントエンド UI を確認。
`http://localhost:8000/docs` で Swagger UI を確認。

## API の使い方

### ヘルスチェック

```bash
curl http://localhost:8000/health
```

### Writeup の登録

```bash
curl -X POST http://localhost:8000/api/writeups \
  -H "Content-Type: application/json" \
  -d '{
    "title": "PNG XOR",
    "ctf_name": "picoCTF 2025",
    "category": "crypto",
    "tags": ["xor", "png"],
    "markdown_content": "## Problem\nBroken PNG.\n## Solution\nXOR key found."
  }'
```

### Writeup の検索

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "壊れた画像ファイル",
    "notes": "XORっぽい"
  }'
```

### ヒントの生成

```bash
curl -X POST http://localhost:8000/api/hint \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "壊れたPNGが与えられた",
    "notes": "ヘッダが異常",
    "retrieved_ids": ["<writeup-id>"]
  }'
```

## 開発コマンド

```bash
# 依存関係の同期
uv sync --dev

# テスト実行
uv run pytest

# lint 実行
uv run ruff check .

# lint 自動修正
uv run ruff check . --fix
```

## テスト

テストはアプリを起動せずに実行可能。
Qdrant はインメモリクライアント、Supabase はフェイク実装を使うためクラウドへの接続不要。

| テストファイル | 内容 |
|---|---|
| `tests/test_health.py` | `/health` が正常に応答するか |
| `tests/test_writeup.py` | Writeup の CRUD が正しく動作するか |
| `tests/test_search.py` | ベクトル検索が結果を返すか |
| `tests/test_hint.py` | ヒント生成が正しいフォーマットを返すか |

## ディレクトリ構成

```
.
├── app/
│   ├── main.py       # FastAPI エンドポイント・ヒント生成
│   ├── rag.py        # チャンク分割・埋め込み・Qdrant 操作
│   ├── writeup.py    # Writeup CRUD・Supabase 操作
│   └── settings.py   # 環境変数による設定管理
├── frontend/
│   ├── index.html    # UI
│   ├── style.css     # スタイル
│   ├── main.ts       # TypeScript ソース
│   └── main.js       # ビルド成果物（.gitignore 対象）
├── tests/
│   ├── conftest.py       # テスト用フィクスチャ
│   ├── test_health.py
│   ├── test_writeup.py
│   ├── test_search.py
│   └── test_hint.py
├── .devcontainer/    # Dev Container 設定
├── compose.yml       # Docker Compose 設定
├── Dockerfile        # 本番用イメージ
├── render.yaml       # Render デプロイ設定
├── Makefile
└── pyproject.toml    # Python 依存関係・ツール設定
```

## 環境変数

`.env.example` をコピーして `.env` を作成し設定する。

| 変数名 | 説明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI API キー |
| `SUPABASE_URL` | Supabase プロジェクト URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service_role キー |
| `QDRANT_URL` | Qdrant Cloud クラスター URL |
| `QDRANT_API_KEY` | Qdrant Cloud API キー |

## フロントエンドのビルド

TypeScript を編集した場合は再ビルドが必要：

```bash
cd frontend
npx tsc
```
