# CLAUDE.md

## プロジェクト概要
このリポジトリは、シンプルなローカル RAG アプリを作りながら、RAGのシステムを学ぶ開発初心者向けのの最小テンプレートです。

現在の構成:
- FastAPI バックエンド
- `data/index.json` を使ったローカル保存型インデックス
- `sentence-transformers/all-MiniLM-L6-v2` による埋め込み検索
- `cyberagent/open-calm-small` によるローカル生成
- Dev Container + Docker Compose + uv による共通開発環境

## 開発方針
- できるだけ小さく、読みやすい構成を保つ
- 大きな全面改修より、小さな変更を積み重ねる
- 明示的に必要になるまでは重いフレームワークを追加しない
- 意図的な移行でない限り、シンプルなローカル RAG 構成を維持する
- コーディングは開発者が行う
- aiエージェントはコードの案を出したり、修正案、エラーの対応を行う

## Python コーディング規約
- Python 3.12 以上を前提とする
- Ruff の lint ルールに従う
- 新しく追加する関数には型ヒントを付ける
- 関数は小さく、テストしやすく保つ

## よく使うコマンド
- 依存関係の同期: `uv sync --dev`
- lock ファイルの更新: `uv lock`
- アプリ起動: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- テスト実行: `uv run pytest`
- lint 実行: `uv run ruff check .`

## アーキテクチャメモ
- `app/rag.py` はチャンク分割、埋め込み、インデックス保存、検索を担当する
- `app/main.py` は FastAPI のエンドポイントとローカル生成を担当する
- `data/index.json` は生成物なのでコミットしない
- `.env` にはローカル設定や秘密情報が入るためコミットしない

## 今後の拡張候補
- PDF 取り込み機能の追加
- 論文比較・要約向けの専用処理追加
- ベクトル DB への移行
- Teams 連携の追加