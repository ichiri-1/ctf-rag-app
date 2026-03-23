# paper-rag-template

ローカルで動作するシンプルな RAG アプリ
ベクトル DB に ChromaDB を使用し、FastAPI でエンドポイントを提供

## 技術スタック

| 役割 | 技術 |
|---|---|
| API | FastAPI |
| 埋め込みモデル | `sentence-transformers/all-MiniLM-L6-v2` |
| 生成モデル | `cyberagent/open-calm-small` |
| ベクトル DB | ChromaDB（ローカルファイル永続化） |
| 依存管理 | uv |
| 開発環境 | Dev Container + Docker Compose |

## 前提条件

- [Docker](https://www.docker.com/)
- [Visual Studio Code](https://code.visualstudio.com/)
- VS Code 拡張: [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

## セットアップ

```bash
# 1. リポジトリをクローン
git clone <repository-url>
cd paper-rag-template

# 2. 環境変数ファイルを作成
cp .env.example .env
```

その後、VS Code で `Reopen in Container` を実行
コンテナ起動時に `uv sync --dev` が自動実行され、依存関係をインストール

## アプリの起動

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

起動後、`http://localhost:8000/docs` で Swagger UI を確認

## API の使い方

### ヘルスチェック

```bash
curl http://localhost:8000/health
```

### ドキュメントの登録 (`/ingest`)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "id": "doc1",
        "text": "ChromaDBはローカルで動作する軽量なベクトルデータベースです。",
        "metadata": {"source": "test"}
      }
    ]
  }'
```

### 質問応答 (`/query`)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ChromaDBとは何ですか？",
    "top_k": 1
  }'
```

レスポンスの `sources` フィールドに検索で取得したチャンクが含まれる
`answer` フィールドはローカル生成モデルによる回答（モデルが小さいため精度は低め）

## 開発コマンド例（uv と Makefile を使う2種類どっちでも）

```bash
# 依存関係の同期
uv sync --dev

make sync

# lock ファイルの更新
uv lock

make lock

# テスト実行
uv run pytest

make test

# lint 実行
uv run ruff check .

make lint

# lint 自動修正
uv run ruff check . --fix 

make format
```

## ディレクトリ構成

```
.
├── app/
│   ├── main.py       # FastAPI エンドポイント・生成処理
│   ├── rag.py        # チャンク分割・埋め込み・ChromaDB 操作
│   └── settings.py   # 環境変数による設定管理
├── data/
│   └── chroma/       # ChromaDB の永続化ディレクトリ（.gitignore 対象）
├── .devcontainer/    # Dev Container 設定
├── .env.example      # 環境変数のテンプレート
├── compose.yml       # Docker Compose 設定
├── Makefile          # make を使うコマンド設定
└── pyproject.toml    # Python 依存関係・ツール設定
```

## 環境変数

`.env.example` をコピーして `.env` を作成し、必要に応じて変更

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 埋め込みモデル |
| `GENERATION_MODEL` | `cyberagent/open-calm-small` | 生成モデル |
| `APP_DATA_DIR` | `data` | データ保存ディレクトリ |
| `MAX_NEW_TOKENS` | `160` | 生成トークンの最大数 |
| `RETRIEVAL_TOP_K` | `3` | 検索で返すチャンク数 |
