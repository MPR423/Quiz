'use strict';
/* 專科考題詳解 — static, offline-capable quiz app. Progress lives in localStorage. */

const $ = (s, el = document) => el.querySelector(s);
const LETTERS = 'ABCDE';
const K = { progress: 'bx.progress.v1', settings: 'bx.settings.v1', session: 'bx.session.v1', tipIOS: 'bx.tip.ios' };
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
};
const DEFAULTS = { banks: [], subs: [], status: 'all', onlyExp: true, order: 'seq', mode: 'quiz', theme: 'auto', fs: 17 };
const S = {
  meta: null, banks: [], qs: [], byId: {},
  progress: store.get(K.progress, {}),
  settings: Object.assign({}, DEFAULTS, store.get(K.settings, {})),
  session: store.get(K.session, null),
};
const saveProgress = () => store.set(K.progress, S.progress);
const saveSettings = () => store.set(K.settings, S.settings);
const saveSession = () => store.set(K.session, S.session);

/* ---------- utils ---------- */
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function inline(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s（(、，：])_(.+?)_(?=$|[\s）)、，。：；])/g, '$1<em>$2</em>');
}
function md(src) {
  if (!src) return '';
  const L = src.replace(/\r/g, '').split('\n');
  let html = '', i = 0;
  const isList = (l) => /^\s*([-*•]|\d+[.)])\s+/.test(l);
  const isBlockStart = (l) => isList(l) || /^\s*\|/.test(l) || /^>\s?/.test(l) || /^#{1,4}\s/.test(l);
  while (i < L.length) {
    const l = L[i];
    if (!l.trim()) { i++; continue; }
    if (/^\s*\|/.test(l)) {
      const rows = [];
      while (i < L.length && /^\s*\|/.test(L[i])) rows.push(L[i++]);
      const cells = (r) => r.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
      const head = cells(rows[0]);
      let body = rows.slice(1);
      if (body.length && /^[\s|:\-]+$/.test(body[0])) body = body.slice(1);
      html += '<div class="tbl"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('') +
        '</tr></thead><tbody>' + body.map((r) => '<tr>' + cells(r).map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') +
        '</tbody></table></div>';
      continue;
    }
    if (/^#{1,4}\s/.test(l)) { html += `<h4>${inline(l.replace(/^#{1,4}\s/, ''))}</h4>`; i++; continue; }
    if (/^>\s?/.test(l)) {
      const q = [];
      while (i < L.length && /^>\s?/.test(L[i])) q.push(L[i++].replace(/^>\s?/, ''));
      html += `<blockquote>${q.map(inline).join('<br>')}</blockquote>`;
      continue;
    }
    if (isList(l)) {
      // nested lists by indentation (2 spaces per level)
      const items = [];
      while (i < L.length && (isList(L[i]) || (L[i].trim() && /^\s{2,}/.test(L[i]) && items.length))) {
        const m = L[i].match(/^(\s*)([-*•]|\d+[.)])\s+(.*)$/);
        if (m) items.push({ lvl: Math.floor(m[1].length / 2), ord: /\d/.test(m[2]), text: m[3] });
        else items[items.length - 1].text += '\n' + L[i].trim();
        i++;
      }
      let out = '', stack = [];
      for (const it of items) {
        while (stack.length > it.lvl + 1) out += `</li></${stack.pop()}>`;
        if (stack.length < it.lvl + 1) {
          while (stack.length < it.lvl + 1) { const t = it.ord ? 'ol' : 'ul'; out += `<${t}>`; stack.push(t); }
        } else out += '</li>';
        out += '<li>' + it.text.split('\n').map(inline).join('<br>');
      }
      while (stack.length) out += `</li></${stack.pop()}>`;
      html += out;
      continue;
    }
    const para = [];
    while (i < L.length && L[i].trim() && !isBlockStart(L[i])) para.push(L[i++]);
    html += '<p>' + para.map(inline).join('<br>') + '</p>';
  }
  return html;
}
function toast(msg) {
  let t = $('.toast');
  if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 1800);
}
const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const sameSet = (a, b) => a.length === b.length && a.every((x) => b.includes(x));
const pct = (a, b) => (b ? Math.round((a / b) * 100) + '%' : '—');
const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const isStandalone = () => window.navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;

function applyLook() {
  const root = document.documentElement;
  if (S.settings.theme === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', S.settings.theme);
  root.style.setProperty('--fs', S.settings.fs + 'px');
}

/* ---------- data ---------- */
// Data files are scripts that register themselves on window.BXD (not fetched JSON),
// so the site also works when index.html is opened straight from disk (file://).
const isFile = location.protocol === 'file:';
function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = () => { s.remove(); resolve(); };
    s.onerror = () => { s.remove(); reject(new Error('無法載入 ' + src.split('?')[0])); };
    document.head.appendChild(s);
  });
}
async function loadData() {
  window.BXD = window.BXD || {};
  await loadScript('data/banks.js' + (isFile ? '' : '?t=' + Date.now()));
  const meta = window.BXD.banks;
  if (!meta || !Array.isArray(meta.banks)) throw new Error('data/banks.js 內容不完整');
  S.meta = meta; S.banks = meta.banks;
  const v = isFile ? '' : '?v=' + encodeURIComponent(meta.updated || '');
  await Promise.all(S.banks.map((b) => loadScript('data/' + b.file + v)));
  S.banks.forEach((b) => {
    const f = window.BXD[b.id];
    if (!f || !Array.isArray(f.questions)) throw new Error('data/' + b.file + ' 內容不完整');
    b.qs = f.questions;
    for (const q of f.questions) { q.bank = b.id; q.bankShort = b.short; S.qs.push(q); S.byId[q.id] = q; }
  });
  // drop settings/session references to ids that no longer exist
  S.settings.banks = S.settings.banks.filter((id) => S.banks.some((b) => b.id === id));
  if (S.session) {
    S.session.ids = S.session.ids.filter((id) => S.byId[id]);
    if (!S.session.ids.length) { S.session = null; store.del(K.session); }
  }
}
const prog = (id) => S.progress[id] || null;
function record(id, sel, ok) {
  const p = S.progress[id] || { n: 0, k: 0, m: false };
  p.n += 1; p.k += ok ? 1 : 0; p.l = sel.join(''); p.ok = ok; p.t = Date.now();
  if (!ok && !p.m) { p.m = true; p.mt = Date.now(); p.auto = true; }
  S.progress[id] = p; saveProgress();
}
function toggleMark(id) {
  const p = S.progress[id] || { n: 0, k: 0, m: false };
  p.m = !p.m; p.mt = Date.now(); p.auto = false;
  S.progress[id] = p; saveProgress();
  return p.m;
}

/* ---------- filtering ---------- */
function inScope(q, st = S.settings) {
  if (st.banks.length && !st.banks.includes(q.bank)) return false;
  if (st.subs.length && !st.subs.includes(q.sub)) return false;
  if (st.onlyExp && !q.exp) return false;
  return true;
}
function statusOk(q, status) {
  const p = prog(q.id);
  switch (status) {
    case 'new': return !p || !p.n;
    case 'wrong': return !!(p && p.n && p.ok === false);
    case 'marked': return !!(p && p.m);
    case 'flag': return !!q.flag;
    case 'low': return !!q.conf && q.conf !== '高';
    default: return true;
  }
}
const filtered = () => S.qs.filter((q) => inScope(q) && statusOk(q, S.settings.status));

/* ---------- routing ---------- */
const app = () => $('#app');
function go(h) { if (location.hash === h) render(); else location.hash = h; }
window.addEventListener('hashchange', render);
function render() {
  const h = location.hash || '#/';
  document.body.onkeydown = null;
  if (h.startsWith('#/quiz')) return renderQuiz();
  if (h.startsWith('#/stats')) return renderStats();
  if (h.startsWith('#/search')) return renderSearch();
  if (h.startsWith('#/settings')) return renderSettings();
  return renderHome();
}
function topBar(inner) { return `<header class="top"><div class="top-in">${inner}</div></header>`; }

/* ---------- home ---------- */
const STATUS = [['all', '全部'], ['new', '未作答'], ['wrong', '最近答錯'], ['marked', '不熟'], ['flag', '⚠️ 爭議'], ['low', '信心中／低']];
function bankStats(b) {
  let done = 0, ok = 0, marked = 0, exp = 0;
  for (const q of b.qs) {
    const p = prog(q.id);
    if (q.exp) exp++;
    if (p && p.n) { done++; if (p.ok) ok++; }
    if (p && p.m) marked++;
  }
  return { done, ok, marked, exp, total: b.qs.length };
}
function renderHome() {
  const st = S.settings;
  const groups = [];
  for (const b of S.banks) { let g = groups.find((x) => x.name === b.group); if (!g) groups.push(g = { name: b.group, banks: [] }); g.banks.push(b); }
  const scopeBanks = st.banks.length ? S.banks.filter((b) => st.banks.includes(b.id)) : S.banks;
  const subCount = {};
  for (const b of scopeBanks) for (const q of b.qs) if (!st.onlyExp || q.exp) subCount[q.sub] = (subCount[q.sub] || 0) + 1;
  const subs = Object.keys(subCount).filter((s) => s !== 'null').sort((a, b) => subRank(a) - subRank(b));
  st.subs = st.subs.filter((s) => subs.includes(s));
  const n = filtered().length;
  const markedN = S.qs.filter((q) => prog(q.id)?.m).length;
  const ss = S.session;
  const showTip = isIOS && !isStandalone() && !store.get(K.tipIOS, false);

  app().innerHTML = topBar(`<h1>專科考題詳解</h1>
      <button class="ibtn" data-go="#/search" aria-label="搜尋">🔍</button>
      <button class="ibtn" data-go="#/stats" aria-label="統計">📊</button>
      <button class="ibtn" data-go="#/settings" aria-label="設定">⚙︎</button>`) +
    `<main class="wrap">
      ${showTip ? `<div class="tip" style="margin-top:14px"><div>iPhone 提醒：用 Safari「分享 → 加入主畫面」開啟，作答紀錄才不會在一段時間沒用後被系統清除；也記得偶爾到 ⚙︎ 匯出備份。</div><button id="tipx" aria-label="關閉">×</button></div>` : ''}
      ${ss ? `<h2 class="sec">繼續上次</h2>
        <div class="card row"><div class="grow"><div style="font-weight:650">${esc(ss.title)}</div>
        <div class="small muted">第 ${ss.idx + 1} / ${ss.ids.length} 題 · ${ss.mode === 'review' ? '看答案模式' : '測驗模式'}</div></div>
        <button class="btn" style="width:auto;padding:10px 18px" data-go="#/quiz">繼續</button></div>` : ''}
      <h2 class="sec">題庫 <span class="small">（點選要練習的題庫；都不選＝全部）</span></h2>
      ${groups.map((g) => `<div class="small muted" style="margin:10px 2px 6px">${esc(g.name)}</div><div class="stack">` + g.banks.map((b) => {
        const s = bankStats(b), sel = st.banks.includes(b.id);
        return `<button class="card bank ${sel ? 'sel' : ''}" data-bank="${b.id}">
          <span class="chk">${sel ? '✓' : ''}</span>
          <span class="grow"><div class="bt">${esc(b.title)}</div>
          <div class="bm">${s.total} 題${b.type === 'multi' ? '・複選' : '・單選'} · 詳解 ${s.exp}/${s.total} · 已作答 ${s.done} · 正確率 ${pct(s.ok, s.done)} · 不熟 ${s.marked}</div>
          <div class="bar"><i style="width:${s.total ? (s.done / s.total) * 100 : 0}%"></i></div></span></button>`;
      }).join('') + '</div>').join('')}
      <h2 class="sec">篩選</h2>
      <div class="card stack">
        <div><div class="small muted" style="margin-bottom:6px">次專科</div>
          <div class="chips"><button class="chip ${st.subs.length ? '' : 'on'}" data-sub="">全部</button>
          ${subs.map((s) => `<button class="chip ${st.subs.includes(s) ? 'on' : ''}" data-sub="${esc(s)}">${esc(s)}<small>${subCount[s]}</small></button>`).join('')}</div></div>
        <div><div class="small muted" style="margin-bottom:6px">範圍</div>
          <div class="chips">${STATUS.map(([k, v]) => `<button class="chip ${st.status === k ? 'on' : ''}" data-status="${k}">${v}</button>`).join('')}</div></div>
        <label class="toggle"><input type="checkbox" id="onlyExp" ${st.onlyExp ? 'checked' : ''}>只出已有詳解的題目</label>
        <div class="row"><label>順序</label><div class="seg grow">
          <button data-order="seq" class="${st.order === 'seq' ? 'on' : ''}">依題號</button><button data-order="random" class="${st.order === 'random' ? 'on' : ''}">隨機</button></div></div>
        <div class="row"><label>模式</label><div class="seg grow">
          <button data-mode="quiz" class="${st.mode === 'quiz' ? 'on' : ''}">測驗</button><button data-mode="review" class="${st.mode === 'review' ? 'on' : ''}">直接看答案</button></div></div>
        <button class="btn" id="start" ${n ? '' : 'disabled'}>開始（${n} 題）</button>
      </div>
      <div class="btns" style="margin-top:12px">
        <button class="btn ghost" id="reviewMarked" ${markedN ? '' : 'disabled'}>複習不熟（${markedN}）</button>
        <button class="btn ghost" data-go="#/search">搜尋題目</button>
      </div>
      <div class="foot">題目與官方答案取自各學會公告的考古題／題庫；詳解由 AI 撰寫，可能有錯，標「⚠️」與信心度「中／低」的題目請自行查證。${S.meta.updated ? '<br>題庫更新：' + esc(S.meta.updated) : ''}</div>
    </main>`;

  app().onclick = (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.go) return go(t.dataset.go);
    if (t.id === 'tipx') { store.set(K.tipIOS, true); return renderHome(); }
    if (t.dataset.bank) { const id = t.dataset.bank; st.banks = st.banks.includes(id) ? st.banks.filter((x) => x !== id) : st.banks.concat(id); saveSettings(); return renderHome(); }
    if (t.dataset.sub !== undefined) { const s = t.dataset.sub; st.subs = !s ? [] : st.subs.includes(s) ? st.subs.filter((x) => x !== s) : st.subs.concat(s); saveSettings(); return renderHome(); }
    if (t.dataset.status) { st.status = t.dataset.status; saveSettings(); return renderHome(); }
    if (t.dataset.order) { st.order = t.dataset.order; saveSettings(); return renderHome(); }
    if (t.dataset.mode) { st.mode = t.dataset.mode; saveSettings(); return renderHome(); }
    if (t.id === 'start') {
      let qs = filtered();
      if (st.order === 'random') qs = shuffle(qs);
      const bt = st.banks.length ? S.banks.filter((b) => st.banks.includes(b.id)).map((b) => b.short).join('、') : '全部題庫';
      const extra = [st.subs.length ? st.subs.join('、') : '', st.status !== 'all' ? STATUS.find((x) => x[0] === st.status)[1] : ''].filter(Boolean).join(' · ');
      return startSession(qs.map((q) => q.id), bt + (extra ? ' · ' + extra : ''));
    }
    if (t.id === 'reviewMarked') {
      let qs = S.qs.filter((q) => prog(q.id)?.m);
      if (st.order === 'random') qs = shuffle(qs);
      return startSession(qs.map((q) => q.id), '複習不熟');
    }
  };
  const ox = $('#onlyExp'); if (ox) ox.onchange = () => { st.onlyExp = ox.checked; saveSettings(); renderHome(); };
}
function startSession(ids, title, idx = 0, mode = S.settings.mode) {
  if (!ids.length) return toast('沒有符合條件的題目');
  S.session = { ids, idx, title, mode, done: {}, sel: {}, res: {} };
  saveSession(); go('#/quiz');
}

/* ---------- quiz ---------- */
function optState(q, L, revealed, sel) {
  const correct = q.answer.includes(L), picked = sel.includes(L);
  if (!revealed) return picked ? 'pick' : '';
  if (!sel.length) return correct ? 'ok' : 'dim';               // review mode
  if (correct && picked) return 'ok';
  if (correct && !picked) return q.type === 'multi' ? 'miss' : 'ok';
  if (!correct && picked) return 'bad';
  return 'dim';
}
const subRank = (s) => { const i = (S.meta.subOrder || []).indexOf(s); return i < 0 ? 999 : i; };
function renderQuiz() {
  const ss = S.session;
  if (!ss || !ss.ids.length) return go('#/');
  if (ss.idx >= ss.ids.length) return renderSummary();
  ss.idx = Math.max(0, ss.idx);
  const q = S.byId[ss.ids[ss.idx]];
  if (!q) { ss.ids.splice(ss.idx, 1); saveSession(); return renderQuiz(); }
  const review = ss.mode === 'review';
  const revealed = review || !!ss.done[q.id];
  const sel = ss.sel[q.id] || [];
  const p = prog(q.id);
  const multi = q.type === 'multi';
  const bank = S.banks.find((b) => b.id === q.bank);

  let resultHtml = '';
  if (revealed && !review) {
    const ok = ss.res[q.id];
    resultHtml = `<div class="result ${ok ? 'ok' : 'bad'}">${ok ? '✓ 答對' : '✗ 答錯'}　正解 ${q.answer.join('')}${ok ? '' : '　你選 ' + (sel.join('') || '—')}
      <button class="redo" id="redo">重做</button></div>`;
  } else if (review) {
    resultHtml = `<div class="result neutral">正解 ${q.answer.join('')}${p && p.n ? `<span class="small muted" style="font-weight:500">　過去作答 ${p.n} 次・最近${p.ok ? '答對' : '答錯'}</span>` : ''}</div>`;
  }
  const expHtml = !revealed ? '' : q.exp ? `<section class="exp card">
      <div class="exp-meta"><span>信心度 <b class="conf c-${esc(q.conf)}">${esc(q.conf || '—')}</b></span><span>${esc(q.sub || '')}</span></div>
      ${q.flag ? `<div class="flag"><b>⚠️ 答案爭議</b>　${inline(q.flag)}</div>` : ''}
      <div class="md">${md(q.exp)}</div>
      ${q.src ? `<div class="src">出處：${inline(q.src)}</div>` : ''}
      ${q.ref ? `<div class="src" style="border:0;margin-top:2px;padding-top:0">官方出題參考：${esc(q.ref)}</div>` : ''}
    </section>` : `<section class="exp card pending">詳解製作中。官方答案：<b>${q.answer.join('')}</b>${q.ref ? `<div class="src">官方出題參考：${esc(q.ref)}</div>` : ''}</section>`;

  app().innerHTML = topBar(`<button class="ibtn" data-go="#/" aria-label="回首頁">‹</button>
      <div class="pos">${esc(ss.title)}　${ss.idx + 1} / ${ss.ids.length}</div>
      <button class="ibtn ${review ? 'on' : ''}" id="modeBtn" title="切換模式">${review ? '看答案' : '測驗'}</button>`) +
    `<main class="wrap" id="qwrap">
      <div class="qmeta"><span class="tag">${esc(bank ? bank.short : '')} 第 ${q.no} 題</span>${q.sub ? `<span class="tag">${esc(q.sub)}</span>` : ''}${multi ? `<span class="tag multi">複選</span>` : ''}${p && p.n ? `<span class="tag">作答 ${p.n} 次</span>` : ''}</div>
      <div class="stem">${esc(q.stem)}</div>
      ${q.images && q.images.length ? `<div class="imgs ${q.images.length > 1 ? 'n2' : ''}">${q.images.map((s) => `<img src="${esc(s)}" alt="題目附圖" loading="lazy">`).join('')}<div class="cap">點圖可放大</div></div>` : ''}
      <div class="opts">${q.options.map((o, i) => {
        const L = LETTERS[i], stt = optState(q, L, revealed, sel);
        const mark = revealed && sel.length ? (stt === 'ok' ? (sel.includes(L) ? '✓' : '正解') : stt === 'bad' ? '✗' : stt === 'miss' ? '漏選' : '') : '';
        return `<button class="opt ${stt}" data-opt="${L}" ${revealed ? 'disabled' : ''}><span class="ol">${L}</span><span class="ot">${esc(o)}</span>${mark ? `<span class="om">${mark}</span>` : ''}</button>`;
      }).join('')}</div>
      ${!revealed && multi ? `<div class="hint">複選題：選完所有正確選項後按「送出」。</div><div style="margin-top:10px"><button class="btn" id="submit" ${sel.length ? '' : 'disabled'}>送出（已選 ${sel.join('') || '—'}）</button></div>` : ''}
      ${resultHtml}
      ${expHtml}
    </main>
    <nav class="bnav"><div class="bnav-in">
      <button class="btn ghost" id="prev" ${ss.idx === 0 ? 'disabled' : ''}>‹ 上一題</button>
      <button class="mark ${p && p.m ? 'on' : ''}" id="markBtn">${p && p.m ? '🚩 不熟' : '🏳 標不熟'}</button>
      <button class="btn" id="next">${ss.idx === ss.ids.length - 1 ? '完成' : '下一題 ›'}</button>
    </div></nav>`;
  window.scrollTo(0, 0);

  const submit = (picks) => {
    const ok = sameSet(picks, q.answer);
    ss.sel[q.id] = picks; ss.done[q.id] = true; ss.res[q.id] = ok;
    record(q.id, picks, ok); saveSession(); renderQuiz();
    const r = $('.result'); if (r) setTimeout(() => r.scrollIntoView({ behavior: 'smooth', block: 'center' }), 30);
  };
  const move = (d) => { ss.idx += d; saveSession(); renderQuiz(); };
  app().onclick = (e) => {
    const img = e.target.closest('.imgs img'); if (img) return openImg(img.getAttribute('src'));
    const t = e.target.closest('button'); if (!t || t.disabled) return;
    if (t.dataset.go) return go(t.dataset.go);
    if (t.dataset.opt) {
      const L = t.dataset.opt;
      if (multi) { ss.sel[q.id] = sel.includes(L) ? sel.filter((x) => x !== L) : sel.concat(L).sort(); saveSession(); return renderQuizKeepScroll(); }
      return submit([L]);
    }
    if (t.id === 'submit') return submit(sel);
    if (t.id === 'redo') { delete ss.done[q.id]; delete ss.sel[q.id]; delete ss.res[q.id]; saveSession(); return renderQuiz(); }
    if (t.id === 'prev') return move(-1);
    if (t.id === 'next') return move(1);
    if (t.id === 'markBtn') { const m = toggleMark(q.id); toast(m ? '已標記為不熟' : '已取消不熟'); return renderQuizKeepScroll(); }
    if (t.id === 'modeBtn') { ss.mode = review ? 'quiz' : 'review'; saveSession(); return renderQuiz(); }
  };
  document.body.onkeydown = (e) => {
    if (e.target.matches('input, textarea')) return;
    const k = e.key.toUpperCase();
    const idx = LETTERS.indexOf(k) >= 0 ? LETTERS.indexOf(k) : '12345'.indexOf(e.key);
    if (!revealed && idx >= 0 && idx < q.options.length) { $(`[data-opt="${LETTERS[idx]}"]`)?.click(); }
    else if (e.key === 'Enter' && !revealed && multi && sel.length) submit(sel);
    else if (e.key === 'ArrowRight') move(1);
    else if (e.key === 'ArrowLeft' && ss.idx > 0) move(-1);
    else if (k === 'M') $('#markBtn')?.click();
  };
  attachSwipe(move);
}
function renderQuizKeepScroll() { const y = window.scrollY; renderQuiz(); window.scrollTo(0, y); }
function attachSwipe(move) {
  const el = $('#qwrap'); if (!el) return;
  let x0 = null, y0 = null, blocked = false;
  el.ontouchstart = (e) => { const t = e.touches[0]; x0 = t.clientX; y0 = t.clientY; blocked = !!e.target.closest('.tbl, .imgs') || e.touches.length > 1; };
  el.ontouchend = (e) => {
    if (x0 === null || blocked) return;
    const t = e.changedTouches[0], dx = t.clientX - x0, dy = t.clientY - y0; x0 = null;
    if (Math.abs(dx) > 70 && Math.abs(dy) < 45) { if (dx < 0) move(1); else if (S.session.idx > 0) move(-1); }
  };
}
function renderSummary() {
  const ss = S.session;
  const done = Object.keys(ss.done).length, ok = Object.values(ss.res).filter(Boolean).length;
  app().innerHTML = topBar(`<button class="ibtn" data-go="#/" aria-label="回首頁">‹</button><div class="pos">${esc(ss.title)}</div>`) +
    `<main class="wrap"><div class="card summary" style="margin-top:18px">
      <div class="muted">本次練習完成</div>
      ${ss.mode === 'review' && !done ? `<div class="big">${ss.ids.length} 題</div><div class="muted">看答案模式不計分</div>` : `<div class="big">${ok} / ${done}</div><div class="muted">答對 / 作答題數（${pct(ok, done)}）</div>`}
      <div class="btns" style="margin-top:20px"><button class="btn ghost" id="again">從頭再看一次</button><button class="btn" id="home">回首頁</button></div>
    </div></main>`;
  app().onclick = (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.go) return go(t.dataset.go);
    if (t.id === 'again') { ss.idx = 0; ss.done = {}; ss.sel = {}; ss.res = {}; saveSession(); return renderQuiz(); }
    if (t.id === 'home') { S.session = null; store.del(K.session); return go('#/'); }
  };
}
function openImg(src) {
  const o = document.createElement('div');
  o.className = 'overlay';
  o.innerHTML = `<img src="${esc(src)}" alt=""><button class="x" aria-label="關閉">×</button><div class="zh">點圖片切換原尺寸／可雙指縮放</div>`;
  o.onclick = (e) => {
    if (e.target.closest('.x')) return o.remove();
    if (e.target.tagName === 'IMG') { o.classList.toggle('zoom'); return; }
    o.remove();
  };
  document.body.appendChild(o);
}

/* ---------- search ---------- */
function renderSearch() {
  const term = decodeURIComponent((location.hash.split('?q=')[1] || ''));
  app().innerHTML = topBar(`<button class="ibtn" data-go="#/" aria-label="回首頁">‹</button><h1>搜尋</h1>`) +
    `<main class="wrap"><div style="margin-top:14px"><input type="search" id="q" placeholder="關鍵字，例如 Le Fort、hyperkalemia、蛇咬" value="${esc(term)}" autocomplete="off"></div>
     <div id="res" style="margin-top:12px"></div></main>`;
  const inp = $('#q'), res = $('#res');
  const run = () => {
    const v = inp.value.trim().toLowerCase();
    if (!v) { res.innerHTML = '<div class="muted small center" style="margin-top:20px">搜尋範圍：題目、選項、詳解、出處</div>'; return; }
    const terms = v.split(/\s+/);
    const hits = S.qs.filter((q) => {
      const hay = q._hay || (q._hay = [q.stem, q.options.join(' '), q.exp || '', q.ref || '', q.src || '', q.sub || ''].join(' ').toLowerCase());
      return terms.every((t) => hay.includes(t));
    });
    res.innerHTML = `<div class="small muted" style="margin:0 2px 8px">${hits.length} 題</div>` + (hits.length ? `<div class="list-wrap list">${hits.slice(0, 200).map((q, i) =>
      `<button class="li" data-i="${i}"><div class="lt">${esc(q.bankShort)} 第 ${q.no} 題 · ${esc(q.sub || '')}${prog(q.id)?.m ? ' · 🚩' : ''}</div><div class="ls">${esc(q.stem)}</div></button>`).join('')}</div>` : '');
    res.onclick = (e) => { const t = e.target.closest('.li'); if (!t) return; startSession(hits.slice(0, 200).map((q) => q.id), `搜尋「${inp.value.trim()}」`, +t.dataset.i); };
  };
  let timer; inp.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { history.replaceState(null, '', '#/search?q=' + encodeURIComponent(inp.value)); run(); }, 200); };
  app().onclick = (e) => { const t = e.target.closest('button[data-go]'); if (t) go(t.dataset.go); };
  run(); if (!term) inp.focus();
}

/* ---------- stats ---------- */
function renderStats() {
  const rows = (qs) => { let done = 0, ok = 0, m = 0; for (const q of qs) { const p = prog(q.id); if (p && p.n) { done++; if (p.ok) ok++; } if (p && p.m) m++; } return { n: qs.length, done, ok, m }; };
  const tr = (name, r, cls = '') => `<tr class="${cls}"><td>${esc(name)}</td><td>${r.n}</td><td>${r.done}</td><td>${pct(r.ok, r.done)}</td><td>${r.m}</td></tr>`;
  const bankBlocks = S.banks.map((b) => {
    const bySub = {};
    for (const q of b.qs) { const k = q.sub || '未分類'; (bySub[k] = bySub[k] || []).push(q); }
    const subs = Object.keys(bySub).sort((x, y) => subRank(x) - subRank(y));
    return `<h2 class="sec">${esc(b.title)}</h2><div class="card"><table class="stats"><thead><tr><th>次專科</th><th>題數</th><th>已作答</th><th>最近正確率</th><th>不熟</th></tr></thead><tbody>
      ${subs.length > 1 ? subs.map((s) => tr(s, rows(bySub[s]))).join('') : ''}${tr('合計', rows(b.qs), 'tot')}</tbody></table></div>`;
  }).join('');
  app().innerHTML = topBar(`<button class="ibtn" data-go="#/" aria-label="回首頁">‹</button><h1>統計</h1>`) +
    `<main class="wrap">${bankBlocks}<div class="foot">「最近正確率」以每題最近一次作答計算。</div></main>`;
  app().onclick = (e) => { const t = e.target.closest('button[data-go]'); if (t) go(t.dataset.go); };
}

/* ---------- settings / backup ---------- */
function renderSettings() {
  const st = S.settings;
  const nRec = Object.keys(S.progress).length;
  app().innerHTML = topBar(`<button class="ibtn" data-go="#/" aria-label="回首頁">‹</button><h1>設定與備份</h1>`) +
    `<main class="wrap">
      <h2 class="sec">外觀</h2>
      <div class="card stack">
        <div class="row"><label>主題</label><div class="seg grow">${[['auto', '自動'], ['light', '淺色'], ['dark', '深色']].map(([k, v]) => `<button data-theme="${k}" class="${st.theme === k ? 'on' : ''}">${v}</button>`).join('')}</div></div>
        <div class="row"><label>字級</label><div class="seg grow">${[[15, '小'], [17, '中'], [19, '大'], [21, '特大']].map(([k, v]) => `<button data-fs="${k}" class="${st.fs === k ? 'on' : ''}">${v}</button>`).join('')}</div></div>
      </div>
      <h2 class="sec">備份作答紀錄（目前 ${nRec} 題有紀錄）</h2>
      <div class="card stack">
        <div class="small muted">紀錄只存在這台裝置的瀏覽器裡。換手機、清除瀏覽器資料前請先匯出；匯入時同一題以較新的紀錄為準。</div>
        <div class="btns"><button class="btn ghost" id="exp">下載備份檔</button><button class="btn ghost" id="copy">複製備份文字</button></div>
        <div class="btns"><button class="btn ghost" id="imp">從檔案匯入</button><button class="btn ghost" id="pasteToggle">貼上文字匯入</button></div>
        <input type="file" id="file" accept="application/json,.json" hidden>
        <div id="pasteBox" hidden><textarea id="pasteTxt" placeholder="把備份文字貼在這裡"></textarea><button class="btn" id="pasteGo" style="margin-top:8px">匯入</button></div>
      </div>
      <h2 class="sec">重設</h2>
      <div class="card stack">
        <button class="btn warn" id="resetMarks">清除所有「不熟」標記</button>
        <button class="btn warn" id="resetAll">清除全部作答紀錄</button>
      </div>
      <div class="foot">資料版本：${esc(S.meta.updated || '')}</div>
    </main>`;
  app().onclick = async (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.go) return go(t.dataset.go);
    if (t.dataset.theme) { st.theme = t.dataset.theme; saveSettings(); applyLook(); return renderSettings(); }
    if (t.dataset.fs) { st.fs = +t.dataset.fs; saveSettings(); applyLook(); return renderSettings(); }
    if (t.id === 'exp') return exportFile();
    if (t.id === 'copy') { try { await navigator.clipboard.writeText(backupText()); toast('已複製，可貼到備忘錄保存'); } catch (err) { toast('無法複製，請改用下載'); } return; }
    if (t.id === 'imp') return $('#file').click();
    if (t.id === 'pasteToggle') { $('#pasteBox').hidden = !$('#pasteBox').hidden; return; }
    if (t.id === 'pasteGo') return importText($('#pasteTxt').value);
    if (t.id === 'resetMarks' && confirm('確定清除所有「不熟」標記？')) { for (const p of Object.values(S.progress)) { p.m = false; p.mt = Date.now(); } saveProgress(); toast('已清除'); return renderSettings(); }
    if (t.id === 'resetAll' && confirm('確定清除全部作答紀錄？建議先匯出備份。')) { S.progress = {}; saveProgress(); S.session = null; store.del(K.session); toast('已清除'); return renderSettings(); }
  };
  $('#file').onchange = async (e) => { const f = e.target.files[0]; if (f) importText(await f.text()); e.target.value = ''; };
}
const backupText = () => JSON.stringify({ app: 'board-exam', v: 1, exported: new Date().toISOString(), progress: S.progress });
function exportFile() {
  const blob = new Blob([backupText()], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `考題作答紀錄-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 3000);
}
function importText(txt) {
  let inc;
  try { const d = JSON.parse(txt); inc = d.progress || d; if (typeof inc !== 'object') throw 0; } catch (e) { return toast('格式錯誤，無法匯入'); }
  let n = 0;
  const ts = (r) => Math.max(r?.t || 0, r?.mt || 0);
  for (const [id, r] of Object.entries(inc)) {
    if (!r || typeof r !== 'object') continue;
    const cur = S.progress[id];
    if (!cur) { S.progress[id] = r; n++; continue; }
    // keep attempt counters from the busier record, flags/last-answer from the newer one
    const newer = ts(r) >= ts(cur) ? r : cur;
    S.progress[id] = Object.assign({}, newer, { n: Math.max(cur.n || 0, r.n || 0), k: Math.max(cur.k || 0, r.k || 0) });
    n++;
  }
  saveProgress(); toast(`已匯入 ${n} 題的紀錄`); render();
}

/* ---------- boot ---------- */
(async function boot() {
  applyLook();
  app().innerHTML = '<div class="loading">載入題庫中…</div>';
  try { await loadData(); } catch (e) {
    console.error(e);
    const hint = isFile
      ? '請確認 zip 已<b>完整解壓縮</b>，而且 index.html 旁邊有 data、img 兩個資料夾。'
      : '請確認網路後重新整理；剛上傳到 GitHub 的話，等 1–2 分鐘部署完成再試。';
    app().innerHTML = `<div class="loading">題庫載入失敗：${esc(e.message || String(e))}<br><br>${hint}</div>`;
    return;
  }
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
  render();
})();
