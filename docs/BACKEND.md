# バックエンド仕様書

このドキュメントは、途中からプロジェクトに参加した開発者が「バックエンドが何をしていて、どこを触ればよいか」を短時間で把握できるようにまとめたものです。

対象コード:

- [app/main.py](../app/main.py) — FastAPI エンドポイント / ヒント生成
- [app/rag.py](../app/rag.py) — チャンク分割 / 埋め込み / Qdrant 操作
- [app/writeup.py](../app/writeup.py) — Writeup の CRUD / Supabase 操作
- [app/settings.py](../app/settings.py) — 設定管理

---

## 1. 何を作っているアプリか

**CTF Recall** は、過去に自分（またはチーム）が解いた CTF の Writeup を溜め込み、**新しく出会った問題に近いものを検索**して、さらに LLM で **「共通点 / 疑うべき手法 / 次に試すこと」というヒント** を生成する RAG（Retrieval-Augmented Generation）アプリです。

ざっくり動作:

1. ユーザーが Markdown 形式で Writeup を登録する
2. Writeup は ① Markdown 本文をオブジェクトストレージに保存、② メタデータを DB に保存、③ 意味的検索用にベクトル化して Qdrant に保存、の3か所に分散して保管される
3. ユーザーが問題文とメモを投げると、ベクトル検索で類似 Writeup を返す
4. 選んだ Writeup を context として、OpenAI にヒント生成を依頼する

---

## 2. 全体構成図

```
                    ┌───────────────────────┐
                    │  Frontend (静的配信)  │
                    │  frontend/index.html  │
                    └──────────┬────────────┘
                               │ fetch
                               ▼
   ┌────────────────────────────────────────────────────┐
   │                  FastAPI (app/main.py)             │
   │                                                    │
   │  /health          /api/writeups (CRUD)             │
   │  /api/search      /api/hint                        │
   └───┬──────────────────────┬──────────────────┬──────┘
       │                      │                  │
       ▼                      ▼                  ▼
 ┌──────────────┐   ┌────────────────────┐  ┌──────────────┐
 │ app/writeup  │   │     app/rag        │  │ OpenAI API   │
 │              │   │                    │  │ (chat)       │
 │ CRUD ロジック│   │ 埋め込み・検索    │  └──────────────┘
 └──┬────────┬──┘   └──────┬──────┬──────┘
    │        │             │      │
    ▼        ▼             ▼      ▼
 ┌────────────────┐  ┌──────────────┐  ┌────────────┐
 │  Supabase      │  │ Qdrant Cloud │  │ OpenAI     │
 │  ├ writeups(DB)│  │ collection:  │  │ embedding  │
 │  └ Storage     │  │  writeups    │  │ API        │
 └────────────────┘  └──────────────┘  └────────────┘
```

3つの外部サービスに役割を分担している点がポイントです:

| サービス | 何を保存しているか | なぜここに置くか |
|---|---|---|
| **Supabase Storage** | Markdown 本文（`{writeup_id}.md`） | DB に長文を入れず、ファイルとして安く保存するため |
| **Supabase Postgres** (`writeups` テーブル) | Writeup のメタデータ（タイトル、CTF 名、カテゴリ、タグ、要約、作成日） | 一覧・絞り込み・ID→ファイル名の対応表 |
| **Qdrant Cloud** (`writeups` コレクション) | チャンクごとのベクトル + payload（writeup_id / title / category / chunk_index / text） | 意味的類似検索のため |

---

## 3. データフロー

### 3.1 Writeup 登録: `POST /api/writeups`

エンドポイント: [app/main.py:47](../app/main.py#L47) → 実装: [app/writeup.py:35](../app/writeup.py#L35) の `create()`

処理の流れ:

1. `writeup_id = uuid4()` を発番する
2. Markdown 本文を Supabase Storage の `writeups` バケットに `{writeup_id}.md` として **アップロード**
3. Markdown を `chunk_markdown()` で **チャンク分割**（[app/rag.py:47](../app/rag.py#L47)）
   - フロントマター（`--- ... ---`）を除去
   - `## ` 見出しでセクション単位に分割
4. 各チャンクを OpenAI Embeddings API（`text-embedding-3-small`、1536 次元）で **ベクトル化**
5. `PointStruct` として Qdrant にまとめて **upsert**（[app/rag.py:57](../app/rag.py#L57)）
   - point ID: `abs(hash(f"{writeup_id}_{i}")) % 2^63`
   - payload: `writeup_id / title / category / chunk_index / text`
6. Supabase の `writeups` テーブルにメタデータ行を **insert**
   - `summary` は `_extract_summary()` で本文の最初の非見出し行を先頭 200 文字だけ取り出したもの

登録失敗時のロールバックは実装していない（ストレージ/DB/Qdrant のいずれかが失敗するとデータが半端に残る可能性がある）ので、要件次第で追加を検討する。

### 3.2 Writeup 取得・一覧・削除

- **取得** `GET /api/writeups/{writeup_id}` → [app/writeup.py:62](../app/writeup.py#L62) `get()`
  - Postgres でメタデータを取得 → Storage から Markdown を download → 両方をマージして返す
- **一覧** `GET /api/writeups/list?category=&q=` → [app/writeup.py:81](../app/writeup.py#L81) `list_writeups()`
  - `category` は DB クエリで `.eq()` により絞り込み
  - `q` は取得後の**インメモリフィルタ**（title / ctf_name / tags を lower-case で部分一致）
- **削除** `DELETE /api/writeups/{writeup_id}` → [app/writeup.py:109](../app/writeup.py#L109) `delete()`
  - Qdrant からチャンクを削除（`writeup_id` で Filter）→ Storage からファイル削除 → DB 行削除

**ルート順序の注意**（[app/main.py:59](../app/main.py#L59)）: FastAPI はルートを宣言順にマッチするため、`/api/writeups/list` を `/api/writeups/{writeup_id}` より **前に定義**しないと `list` が UUID として吸い込まれてしまう。

### 3.3 検索: `POST /api/search`

エンドポイント: [app/main.py:85](../app/main.py#L85) → 検索本体: [app/rag.py:94](../app/rag.py#L94) `search()`

1. `query_text` と `notes` を改行で結合 → 1本のクエリ文字列にする
2. OpenAI Embeddings でベクトル化
3. Qdrant に `limit = top_k * 3` で類似検索（コサイン類似度）
   - 1 Writeup が複数チャンクを持つので **余裕を持って多めに引く**
4. `writeup_id` ごとに **最も類似度が高いチャンクだけ**残して集約
5. 類似度降順で上位 `top_k` 件（デフォルト 5）を返す
6. `main.py` 側で `_load_index()` を呼び、DB のメタデータ（tags, summary）で結果を **enrich** してレスポンス

レスポンス:

```json
{
  "results": [
    {
      "id": "...",
      "title": "...",
      "category": "...",
      "tags": ["..."],
      "summary": "...",
      "distance": 0.87
    }
  ]
}
```

**注意**: フィールド名は `distance` だがコサイン類似度が入る（値が大きいほど近い）。命名と意味が食い違うので、UI 側で扱う際は「score」的に読む必要がある。

### 3.4 ヒント生成: `POST /api/hint`

エンドポイント: [app/main.py:126](../app/main.py#L126)

1. `retrieved_ids`（フロントで検索結果から選ばれた ID 群）を1件ずつ `get()` で取り出す
2. 各 Writeup を `### {title} ({category})` + 本文 **先頭 1000 文字** に整形して連結
3. `_HINT_SYSTEM_PROMPT`（[app/main.py:109](../app/main.py#L109)）+ ユーザー入力 + 参考 Writeup を messages に組み立てて Chat Completions API（`gpt-4o-mini`）を叩く
4. `response_format={"type": "json_object"}` で JSON を強制
5. パースに失敗したら空の3キーで包んで返す

返す JSON の構造（LLM への指示で固定）:

```json
{
  "common_points": ["..."],
  "suspicious_methods": ["..."],
  "next_actions": ["..."]
}
```

---

## 4. モジュール別の責務

| モジュール | 責務 | 外部依存 |
|---|---|---|
| [app/main.py](../app/main.py) | ルーティング、リクエスト/レスポンスモデル定義、ヒント生成のプロンプト組み立て、静的ファイル配信 | OpenAI (chat) |
| [app/rag.py](../app/rag.py) | Markdown チャンク分割、埋め込み、Qdrant への upsert / delete / search | OpenAI (embedding), Qdrant |
| [app/writeup.py](../app/writeup.py) | Writeup の CRUD 実装、要約抽出、`rag.py` の呼び出しの調停 | Supabase (DB + Storage) |
| [app/settings.py](../app/settings.py) | `.env` の読み込み、シークレット管理、デフォルト値 | pydantic-settings |

**依存方向**: `main.py → writeup.py → rag.py`。`rag.py` は `writeup.py` を知らない。逆流させないこと。

### 4.1 クライアント初期化のパターン

OpenAI / Qdrant / Supabase の各クライアントは `@lru_cache(maxsize=1)` を付けた `_openai_client()` / `_qdrant_client()` / `_supabase()` で作られる。**プロセス内 1 インスタンスの遅延生成**。テストでは `cache_clear()` してからモンキーパッチで差し替える（[tests/conftest.py:103](../tests/conftest.py#L103)）。

### 4.2 Qdrant コレクションの自動作成

`_ensure_collection()`（[app/rag.py:37](../app/rag.py#L37)）が `add_writeup` と `search` の入口で呼ばれる。存在しなければ:

- ベクトルサイズ 1536（`text-embedding-3-small` の次元）
- 距離: コサイン

で作成する。埋め込みモデルを変更する場合は次元数も直す必要がある点に注意。

### 4.3 Point ID の作り方

`abs(hash(f"{writeup_id}_{i}")) % 2^63`（[app/rag.py:66](../app/rag.py#L66)）で 64bit 整数化している。Python の `hash()` はプロセスごとに変わる（`PYTHONHASHSEED`）ため、**同じ Writeup を後で再登録すると別 ID が生成される**。今の実装だと再登録で古いチャンクが上書きされずゴミが残る可能性があるので、更新機能を作る場合はここも見直す。

---

## 5. 設定と環境変数

[app/settings.py](../app/settings.py) が `.env` を読む。`SecretStr` は `.get_secret_value()` を呼ばないと生値が取れない。

| 変数 | 用途 | デフォルト |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI 認証 | `""` |
| `OPENAI_EMBEDDING_MODEL` | 埋め込みモデル | `text-embedding-3-small` |
| `OPENAI_CHAT_MODEL` | チャットモデル | `gpt-4o-mini` |
| `RETRIEVAL_TOP_K` | 検索結果の返却件数 | `5` |
| `SUPABASE_URL` | Supabase URL | `""` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 認証（service_role） | `""` |
| `QDRANT_URL` | Qdrant Cloud URL | `""` |
| `QDRANT_API_KEY` | Qdrant 認証 | `""` |
| `QDRANT_COLLECTION` | コレクション名 | `writeups` |

`.env` はコミットしない（`.gitignore` 済み）。

---

## 6. データモデル

### 6.1 Supabase `writeups` テーブル

| カラム | 型 | 説明 |
|---|---|---|
| `id` | UUID PK | Writeup ID |
| `title` | TEXT | タイトル |
| `ctf_name` | TEXT | 大会名 |
| `category` | TEXT | カテゴリ（crypto / web / rev など） |
| `tags` | TEXT[] | 自由タグ |
| `summary` | TEXT | 本文冒頭から抽出した要約（200 文字） |
| `created_at` | TIMESTAMPTZ | 作成日時（UTC） |
| `filename` | TEXT | Storage 上のファイル名（`{id}.md`） |

`GRANT ALL ON public.writeups TO service_role;` を忘れると `service_role` からも書けない。

### 6.2 Supabase Storage バケット `writeups`

- 非公開バケット
- ファイル名: `{writeup_id}.md`
- 中身: 登録時にユーザーが送った Markdown 本文そのまま

### 6.3 Qdrant コレクション `writeups`

- ベクトルサイズ: 1536
- 距離: COSINE
- 1 point = 1 チャンク
- payload:
  - `writeup_id` (str)
  - `title` (str)
  - `category` (str)
  - `chunk_index` (int)
  - `text` (str) — チャンク本文

---

## 7. エンドポイント一覧

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| POST | `/api/writeups` | Writeup 登録 |
| GET | `/api/writeups/list` | 一覧取得（`?category=`, `?q=`） |
| GET | `/api/writeups/{writeup_id}` | 個別取得（本文込み） |
| DELETE | `/api/writeups/{writeup_id}` | 削除 |
| POST | `/api/search` | 意味的検索 |
| POST | `/api/hint` | LLM によるヒント生成 |
| GET | `/*`（上記以外） | `frontend/` を静的配信（[app/main.py:163](../app/main.py#L163)） |

Swagger UI: `http://localhost:8000/docs`

---

## 8. テスト戦略

`pytest` で実行（`uv run pytest`）。外部サービスを叩かない構成:

- **Qdrant**: `QdrantClient(":memory:")` でインメモリ動作（[tests/conftest.py:107](../tests/conftest.py#L107)）
- **Supabase**: `_FakeSupabase` クラスで `table()` / `storage.from_()` を偽装
- **OpenAI**: テストごとに個別モック（`test_search.py` / `test_hint.py` で `_embed` / `chat.completions.create` を差し替え）

`client` フィクスチャ（[tests/conftest.py:102](../tests/conftest.py#L102)）は各クライアントの `lru_cache` を `cache_clear()` してからモンキーパッチするので、**テスト同士でクライアントが漏れない**。

---

## 9. 新規参加者向けの「まずここを触ってみる」ガイド

1. **API を1本追加してみる場合** → [app/main.py](../app/main.py) にエンドポイントを足し、ロジックは `writeup.py` か `rag.py` に置く。Pydantic モデルは main.py 上部にまとめる。
2. **検索のチューニング** → [app/rag.py:94](../app/rag.py#L94) の `search()`。`limit = top_k * 3` の倍率、集約ロジック、`chunk_markdown()` の分割単位が主な調整点。
3. **プロンプトの改善** → [app/main.py:109](../app/main.py#L109) の `_HINT_SYSTEM_PROMPT` と、`user_message` の組み立て部分。
4. **モデル変更** → `.env` の `OPENAI_EMBEDDING_MODEL` / `OPENAI_CHAT_MODEL`。埋め込みを変えたら Qdrant のベクトル次元 (`app/rag.py:43`) も要調整。既存データのマイグレーション（再埋め込み）も忘れずに。
5. **テスト追加** → `tests/` に `test_*.py` を作り、`client` フィクスチャを引数に取ればフルスタックの E2E が書ける（外部通信ゼロ）。

---

## 10. 既知の注意点 / 改善余地

- **登録失敗のロールバック無し**: Storage / DB / Qdrant のいずれかが落ちるとデータが不整合になる。
- **`distance` の命名**: 中身はコサイン類似度（大きいほど近い）。フィールド名を `score` にリネームするのが妥当。
- **Point ID が非決定的**: 再登録すると別 ID になり、古いチャンクが残る。更新機能を作るときは `delete_writeup()` → `add_writeup()` の順で運用するか、ID 生成を決定的にする。
- **CLAUDE.md の内容が古い**: プロジェクトルートの `CLAUDE.md` はローカル RAG（sentence-transformers / open-calm-small / `data/index.json`）時代の記述。実装は OpenAI + Qdrant + Supabase に移行済み。ドキュメント更新は別 PR で。
