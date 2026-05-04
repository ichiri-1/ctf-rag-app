"use strict";
// import { marked } from "marked";
// --- タブ切り替え ---
window.switchTab = function (name) {
    document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.getElementById('pane-' + name).classList.add('active');
    ['writeups', 'register', 'search'].forEach((n, i) => {
        if (n === name)
            document.querySelectorAll('nav button')[i].classList.add('active');
    });
    if (name === 'writeups')
        loadWriteups();
};
// --- Writeup 一覧 ---
async function loadWriteups() {
    const q = document.getElementById('filter-q').value;
    const category = document.getElementById('filter-category').value;
    const params = new URLSearchParams();
    if (q)
        params.set('q', q);
    if (category)
        params.set('category', category);
    const container = document.getElementById('writeups-container');
    container.innerHTML = '<p>読み込み中...</p>';
    try {
        const res = await fetch('/api/writeups/list?' + params);
        const items = await res.json();
        renderWriteupsList(items);
    }
    catch {
        container.innerHTML = '<p>読み込みエラー</p>';
    }
}
window.loadWriteups = loadWriteups;
function renderWriteupsList(items) {
    const container = document.getElementById('writeups-container');
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
async function openDetail(id) {
    try {
        const data = await fetch(`/api/writeups/${id}`).then(r => r.json());
        document.getElementById('modal-title').textContent = data.title;
        document.getElementById('modal-meta').textContent =
            `${data.category}  ${(data.tags ?? []).join(', ')}  ${esc(data.ctf_name)}  ${(data.created_at ?? '').slice(0, 10)}`;
        document.getElementById('modal-content').innerHTML = window.marked.parse(data.markdown_content);
        document.getElementById('detail-modal').style.display = 'block';
    }
    catch {
        alert('詳細の取得に失敗しました');
    }
}
window.openDetail = openDetail;
window.closeModal = function () {
    document.getElementById('detail-modal').style.display = 'none';
};
// --- Writeup 削除 ---
async function deleteWriteup(id) {
    if (!confirm('このWriteupを削除しますか？'))
        return;
    await fetch(`/api/writeups/${id}`, { method: 'DELETE' });
    loadWriteups();
}
window.deleteWriteup = deleteWriteup;
// --- Writeup 登録 ---
window.registerWriteup = async function () {
    const title = document.getElementById('reg-title').value.trim();
    const ctf_name = document.getElementById('reg-ctf').value.trim();
    const category = document.getElementById('reg-category').value;
    const tags = document.getElementById('reg-tags').value
        .split(',').map(t => t.trim()).filter(Boolean);
    const markdown_content = document.getElementById('reg-content').value.trim();
    const msgEl = document.getElementById('register-msg');
    if (!title || !ctf_name || !category || !markdown_content) {
        msgEl.textContent = '必須項目（タイトル・CTF名・カテゴリ・本文）を入力してください';
        return;
    }
    msgEl.textContent = '登録中...';
    try {
        const res = await fetch('/api/writeups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, ctf_name, category, tags, markdown_content }),
        });
        const data = await res.json();
        if (res.ok) {
            msgEl.textContent = `登録しました（ID: ${data.id}）`;
            ['reg-title', 'reg-ctf', 'reg-tags', 'reg-content']
                .forEach(id => { document.getElementById(id).value = ''; });
            document.getElementById('reg-category').value = '';
        }
        else {
            msgEl.textContent = `エラー: ${JSON.stringify(data)}`;
        }
    }
    catch {
        msgEl.textContent = '通信エラーが発生しました';
    }
};
// --- 検索 ---
let lastResults = [];
window.doSearch = async function () {
    const query_text = document.getElementById('search-query').value.trim();
    const notes = document.getElementById('search-notes').value.trim();
    const resultsEl = document.getElementById('search-results');
    const hintEl = document.getElementById('hint-area');
    if (!query_text) {
        resultsEl.textContent = '問題文を入力してください';
        return;
    }
    resultsEl.innerHTML = '<p>検索中...</p>';
    hintEl.innerHTML = '';
    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query_text, notes }),
        });
        const data = await res.json();
        lastResults = data.results ?? [];
        renderSearchResults(lastResults);
    }
    catch {
        resultsEl.textContent = '検索エラーが発生しました';
    }
};
function renderSearchResults(results) {
    const el = document.getElementById('search-results');
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
async function generateHint() {
    const query_text = document.getElementById('search-query').value.trim();
    const notes = document.getElementById('search-notes').value.trim();
    const retrieved_ids = lastResults.map(r => r.id);
    const hintEl = document.getElementById('hint-area');
    hintEl.innerHTML = '<p>ヒント生成中...</p>';
    try {
        const res = await fetch('/api/hint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query_text, notes, retrieved_ids }),
        });
        const hint = await res.json();
        renderHint(hint);
    }
    catch {
        hintEl.textContent = 'ヒント生成エラーが発生しました';
    }
}
window.generateHint = generateHint;
function renderHint(hint) {
    const toList = (items) => '<ul>' + (items ?? []).map(s => `<li>${esc(s)}</li>`).join('') + '</ul>';
    document.getElementById('hint-area').innerHTML = `
    <h2>ヒント</h2>
    <h3>共通点</h3>${toList(hint.common_points)}
    <h3>疑うべき手法</h3>${toList(hint.suspicious_methods)}
    <h3>次に試すこと</h3>${toList(hint.next_actions)}`;
}
// --- ユーティリティ ---
function esc(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
// --- 初期ロード ---
document.addEventListener('DOMContentLoaded', () => {
    loadWriteups();
});
