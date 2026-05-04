// import { marked } from "marked";

// --- 型定義 ---

interface WriteupListItem {
  id: string;
  title: string;
  ctf_name: string;
  category: string;
  tags: string[];
  created_at: string;
}

interface WriteupDetail {
  id: string;
  title: string;
  ctf_name: string;
  category: string;
  tags: string[];
  created_at: string;
  markdown_content: string;
}

interface SearchResult {
  id: string;
  title: string;
  category: string;
  tags: string[];
  summary: string;
  distance: number;
}

interface HintResponse {
  common_points: string[];
  suspicious_methods: string[];
  next_actions: string[];
}

// --- タブ切り替え ---

(window as any).switchTab = function(name: string): void {
  document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('pane-' + name)!.classList.add('active');
  (['writeups', 'register', 'search'] as const).forEach((n, i) => {
    if (n === name) (document.querySelectorAll('nav button')[i] as HTMLElement).classList.add('active');
  });
  if (name === 'writeups') loadWriteups();
};

// --- Writeup 一覧 ---

async function loadWriteups(): Promise<void> {
  const q        = (document.getElementById('filter-q') as HTMLInputElement).value;
  const category = (document.getElementById('filter-category') as HTMLSelectElement).value;
  const params   = new URLSearchParams();
  if (q)        params.set('q', q);
  if (category) params.set('category', category);

  const container = document.getElementById('writeups-container')!;
  container.innerHTML = '<p>読み込み中...</p>';

  try {
    const res   = await fetch('/api/writeups/list?' + params);
    const items = await res.json() as WriteupListItem[];
    renderWriteupsList(items);
  } catch {
    container.innerHTML = '<p>読み込みエラー</p>';
  }
}
(window as any).loadWriteups = loadWriteups;

function renderWriteupsList(items: WriteupListItem[]): void {
  const container = document.getElementById('writeups-container')!;
  if (!items.length) {
    container.innerHTML = '<p>Writeup がありません。「登録」タブから追加してください。</p>';
    return;
  }
  const rows = items.map(item => `
    <tr onclick="openDetail('${esc(item.id)}')">
      <td>${esc(item.title)}</td>
      <td>${esc(item.ctf_name)}</td>
      <td>${esc(item.category)}</td>
      <td>${(item.tags ?? []).map(t => esc(t)).join(', ')}</td>
      <td>${(item.created_at ?? '').slice(0, 10)}</td>
      <td>
        <button onclick="event.stopPropagation(); deleteWriteup('${esc(item.id)}')">削除</button>
      </td>
    </tr>`).join('');
  container.innerHTML = `
    <table>
      <thead><tr><th>タイトル</th><th>CTF名</th><th>カテゴリ</th><th>タグ</th><th>日付</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// --- Writeup 詳細 ---

async function openDetail(id: string): Promise<void> {
  try {
    const data = await fetch(`/api/writeups/${id}`).then(r => r.json()) as WriteupDetail;
    (document.getElementById('modal-title') as HTMLElement).textContent = data.title;
    (document.getElementById('modal-meta') as HTMLElement).textContent =
      `${data.category}  ${(data.tags ?? []).join(', ')}  ${esc(data.ctf_name)}  ${(data.created_at ?? '').slice(0, 10)}`;
    (document.getElementById('modal-content') as HTMLElement).innerHTML = (window as any).marked.parse(data.markdown_content) as string;
    (document.getElementById('detail-modal') as HTMLElement).style.display = 'block';
  } catch {
    alert('詳細の取得に失敗しました');
  }
}
(window as any).openDetail = openDetail;

(window as any).closeModal = function(): void {
  (document.getElementById('detail-modal') as HTMLElement).style.display = 'none';
};

// --- Writeup 削除 ---

async function deleteWriteup(id: string): Promise<void> {
  if (!confirm('このWriteupを削除しますか？')) return;
  await fetch(`/api/writeups/${id}`, { method: 'DELETE' });
  loadWriteups();
}
(window as any).deleteWriteup = deleteWriteup;

// --- Writeup 登録 ---

(window as any).registerWriteup = async function(): Promise<void> {
  const title            = (document.getElementById('reg-title')   as HTMLInputElement).value.trim();
  const ctf_name         = (document.getElementById('reg-ctf')     as HTMLInputElement).value.trim();
  const category         = (document.getElementById('reg-category') as HTMLSelectElement).value;
  const tags             = (document.getElementById('reg-tags')    as HTMLInputElement).value
                             .split(',').map(t => t.trim()).filter(Boolean);
  const markdown_content = (document.getElementById('reg-content') as HTMLTextAreaElement).value.trim();
  const msgEl            = document.getElementById('register-msg')!;

  if (!title || !ctf_name || !category || !markdown_content) {
    msgEl.textContent = '必須項目（タイトル・CTF名・カテゴリ・本文）を入力してください';
    return;
  }
  msgEl.textContent = '登録中...';

  try {
    const res  = await fetch('/api/writeups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, ctf_name, category, tags, markdown_content }),
    });
    const data = await res.json();
    if (res.ok) {
      msgEl.textContent = `登録しました（ID: ${data.id}）`;
      (['reg-title', 'reg-ctf', 'reg-tags', 'reg-content'] as const)
        .forEach(id => { (document.getElementById(id) as HTMLInputElement).value = ''; });
      (document.getElementById('reg-category') as HTMLSelectElement).value = '';
    } else {
      msgEl.textContent = `エラー: ${JSON.stringify(data)}`;
    }
  } catch {
    msgEl.textContent = '通信エラーが発生しました';
  }
};

// --- 検索 ---

let lastResults: SearchResult[] = [];

(window as any).doSearch = async function(): Promise<void> {
  const query_text = (document.getElementById('search-query') as HTMLTextAreaElement).value.trim();
  const notes      = (document.getElementById('search-notes') as HTMLInputElement).value.trim();
  const resultsEl  = document.getElementById('search-results')!;
  const hintEl     = document.getElementById('hint-area')!;

  if (!query_text) {
    resultsEl.textContent = '問題文を入力してください';
    return;
  }
  resultsEl.innerHTML = '<p>検索中...</p>';
  hintEl.innerHTML    = '';

  try {
    const res    = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_text, notes }),
    });
    const data   = await res.json() as { results: SearchResult[] };
    lastResults  = data.results ?? [];
    renderSearchResults(lastResults);
  } catch {
    resultsEl.textContent = '検索エラーが発生しました';
  }
};

function renderSearchResults(results: SearchResult[]): void {
  const el = document.getElementById('search-results')!;
  if (!results.length) {
    el.textContent = '類似する Writeup が見つかりませんでした。';
    return;
  }
  const cards = results.map(r => `
    <div>
      <p>距離: ${r.distance.toFixed(3)}</p>
      <h3 onclick="openDetail('${esc(r.id)}')" style="cursor:pointer">${esc(r.title)}</h3>
      <p>${esc(r.category)}  ${(r.tags ?? []).map(t => esc(t)).join(', ')}</p>
      <p>${esc(r.summary)}</p>
    </div>`).join('<hr>');
  el.innerHTML = `
    <p>${results.length} 件の類似 Writeup</p>
    ${cards}
    <button onclick="generateHint()">これらを参考にヒントを生成</button>`;
}

// --- ヒント生成 ---

async function generateHint(): Promise<void> {
  const query_text    = (document.getElementById('search-query') as HTMLTextAreaElement).value.trim();
  const notes         = (document.getElementById('search-notes') as HTMLInputElement).value.trim();
  const retrieved_ids = lastResults.map(r => r.id);
  const hintEl        = document.getElementById('hint-area')!;

  hintEl.innerHTML = '<p>ヒント生成中...</p>';

  try {
    const res  = await fetch('/api/hint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query_text, notes, retrieved_ids }),
    });
    const hint = await res.json() as HintResponse;
    renderHint(hint);
  } catch {
    hintEl.textContent = 'ヒント生成エラーが発生しました';
  }
}
(window as any).generateHint = generateHint;

function renderHint(hint: HintResponse): void {
  const toList = (items: string[]) =>
    '<ul>' + (items ?? []).map(s => `<li>${esc(s)}</li>`).join('') + '</ul>';

  document.getElementById('hint-area')!.innerHTML = `
    <h2>ヒント</h2>
    <h3>共通点</h3>${toList(hint.common_points)}
    <h3>疑うべき手法</h3>${toList(hint.suspicious_methods)}
    <h3>次に試すこと</h3>${toList(hint.next_actions)}`;
}

// --- ユーティリティ ---

function esc(str: string): string {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// --- 初期ロード ---

document.addEventListener('DOMContentLoaded', () => {
  loadWriteups();
});
