# paper-rag-template

2人で共有するための最小ローカルRAGテンプレートです。

- 開発環境: Dev Container + Docker Compose
- Python依存管理: uv
- 検索: `sentence-transformers/all-MiniLM-L6-v2`
- 生成: `cyberagent/open-calm-small`
- API: FastAPI
- Claude Code: `.claude/` + `CLAUDE.md`

## 初回セットアップ

```bash
cp .env.example .env