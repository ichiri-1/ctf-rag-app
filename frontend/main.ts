// APIレスポンスの型定義
interface QueryResponse {
    answer: string;
    sources: {
        chunk_id: string;
        text: string;
        score: number;
        metadata: { title: string; authors: string; year: number | null };
    }[];
}

// ページ読み込み完了後に処理を開始
document.addEventListener("DOMContentLoaded", () => {
    setupIngestForm();
    setupQueryForm();
    setupUploadForm();
});

// 登録フォーム(/ingest)
function setupIngestForm(): void {
    const form = document.getElementById("ingest-form") as HTMLFormElement;
    const resultEl = document.getElementById("ingest-result") as HTMLParagraphElement;

    form.addEventListener("submit", async (e) => {
        e.preventDefault(); // フォームのデフォルト動作をキャンセル

        const id = (document.getElementById("doc-id") as HTMLInputElement).value;
        const text = (document.getElementById("doc-text") as HTMLTextAreaElement).value;

        const res = await fetch("/ingest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                documents: [{
                    id, text,
                    title: (document.getElementById("doc-title") as HTMLInputElement).value,
                    authors: (document.getElementById("doc-authors") as HTMLInputElement).value,
                    year: Number((document.getElementById("doc-year") as HTMLInputElement).value) || null,
                    metadata: {}
                }] // IngestRequestの形式に合わせる
            }),
        });

        if (res.ok) {
            resultEl.textContent = "登録しました";
            form.reset(); // フォームを空にする
        } else {
            resultEl.textContent = "登録に失敗しました";
        }
    });
}

// PDF 登録フォーム
function setupUploadForm(): void {
    const form = document.getElementById("upload-form") as HTMLFormElement;
    const resultEl = document.getElementById("upload-result") as HTMLParagraphElement;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = (document.getElementById("pdf-file") as HTMLInputElement).files?.[0];
        if (!file) return;

        // PDF はバイナリなので FormData で送る (JSONではない)
        const formData = new FormData();
        formData.append("file", file);
        formData.append("title", (document.getElementById("pdf-title") as HTMLInputElement).value);
        formData.append("authors", (document.getElementById("pdf-authors") as HTMLInputElement).value);
        formData.append("year", (document.getElementById("pdf-year") as HTMLInputElement).value);

        const res = await fetch("/upload", {
            method: "POST",
            body: formData, // Content-Type は自動設定されるので headers は不要
        });

        if (res.ok) {
            const data = await res.json();
            resultEl.textContent = `登録しました (${data.new_chunks} チャンク)`;
            form.reset();
        } else {
            resultEl.textContent = "登録に失敗しました";
        }
    })
}

// 質問フォーム(/query)
function setupQueryForm(): void {
    const form = document.getElementById("query-form") as HTMLFormElement;
    const answerEl = document.getElementById("answer") as HTMLDivElement;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const question = (document.getElementById("question") as HTMLInputElement).value;
        answerEl.textContent = "送信中..."; // ローディング表示

        const res = await fetch("/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question }),
        });

        const data = await res.json() as QueryResponse;

        // 回答を表示
        answerEl.textContent = data.answer;

        // ソースを表示
        const sourceText = data.sources.map((s) =>
            `[${s.chunk_id}] ${s.metadata.title || "タイトルなし"} (${s.metadata.authors || "著者不明"})\n${s.text}`).join("\n\n");
        answerEl.textContent += "\n\n ---- ソース ----" + sourceText;
    });
}