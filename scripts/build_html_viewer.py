"""Generate BASIC_OVERVIEW.html — interactive single-day viewer with audio.

Layout:
  - sticky top nav (brand + search)
  - sticky left sidebar (30-day list)
  - main pane shows the selected day only
  - URL hash routes (#day-N), arrow keys step between days
"""

from __future__ import annotations
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "1-basic" / "all.json"
DST = ROOT / "BASIC_OVERVIEW.html"
AUDIO_TEMPLATE = "https://s3.tutorabc.com/nebo/toeic/1-basic/basic_Day{day:02d}.mp3"


def main() -> None:
    data = json.loads(SRC.read_text())
    days = data["days"]

    # Embed audio URLs into the data so the client doesn't need to know the template.
    payload = []
    for d in days:
        payload.append({
            "day": d["day"],
            "theme": d.get("theme", ""),
            "category": d.get("category", ""),
            "page": d.get("page", ""),
            "audio_url": AUDIO_TEMPLATE.format(day=d["day"]),
            "vocab": [
                {"word": v["word"], "meaning_zh": v.get("meaning_zh", [])}
                for v in d.get("vocab", [])
            ],
        })

    total_words = sum(len(d["vocab"]) for d in payload)
    embedded = json.dumps(payload, ensure_ascii=False)

    page = HTML_TEMPLATE.format(
        total_words=f"{total_words:,}",
        total_days=len(payload),
        embedded_data=embedded,
    )
    DST.write_text(page)
    print(f"wrote {DST.relative_to(ROOT)} ({DST.stat().st_size:,} bytes)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hackers TOEIC — Basic Vocabulary</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Serif+TC:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --canvas: #f7f7f4;
    --canvas-soft: #fafaf7;
    --surface-card: #ffffff;
    --surface-strong: #e6e5e0;
    --ink: #26251e;
    --body: #5a5852;
    --body-strong: #26251e;
    --muted: #807d72;
    --muted-soft: #a09c92;
    --primary: #f54e00;
    --primary-active: #d04200;
    --on-primary: #ffffff;
    --hairline: #e6e5e0;
    --hairline-soft: #efeee8;
    --hairline-strong: #cfcdc4;
    --accent-mark: #fff0b2;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    background: var(--canvas);
    color: var(--ink);
    font-family: 'Inter', system-ui, "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-weight: 400;
    line-height: 1.5;
    letter-spacing: -0.005em;
  }}
  :lang(zh-Hant), .zh {{
    font-family: 'Noto Serif TC', 'Inter', system-ui, sans-serif;
  }}

  /* ----- Top nav ----- */
  .top-nav {{
    position: sticky; top: 0; z-index: 20;
    background: var(--canvas);
    border-bottom: 1px solid var(--hairline);
    height: 64px;
  }}
  .top-nav .inner {{
    max-width: 1280px; margin: 0 auto; padding: 0 24px;
    height: 100%; display: flex; align-items: center; gap: 24px;
  }}
  .brand {{
    font-size: 18px; font-weight: 500; letter-spacing: -0.02em;
    text-decoration: none; color: var(--ink);
    flex-shrink: 0;
  }}
  .brand .accent {{ color: var(--primary); }}
  .search-wrap {{ flex: 1; max-width: 480px; position: relative; }}
  .search-input {{
    width: 100%; height: 40px; padding: 8px 14px 8px 38px;
    border: 1px solid var(--hairline-strong);
    border-radius: 8px; background: var(--surface-card);
    color: var(--ink); font: inherit; font-size: 14px;
    transition: border-color 120ms ease;
  }}
  .search-input::placeholder {{ color: var(--muted-soft); }}
  .search-input:focus {{
    outline: none; border-color: var(--ink);
  }}
  .search-icon {{
    position: absolute; top: 50%; left: 12px; transform: translateY(-50%);
    width: 16px; height: 16px; color: var(--muted);
    pointer-events: none;
  }}
  .nav-meta {{
    margin-left: auto; font-size: 13px; color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0;
  }}

  /* ----- Layout ----- */
  .layout {{
    max-width: 1280px; margin: 0 auto; padding: 0 24px;
    display: grid; grid-template-columns: 280px 1fr; gap: 32px;
    align-items: start;
  }}
  .sidebar {{
    position: sticky; top: 88px;
    height: calc(100vh - 112px);
    overflow: hidden;
    display: flex; flex-direction: column;
    padding: 24px 0;
  }}
  .sidebar-header {{
    margin-bottom: 16px;
  }}
  .sidebar-header .label {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
  }}
  .sidebar-header .title {{
    font-size: 22px; font-weight: 400; letter-spacing: -0.011em;
    margin: 4px 0 0;
  }}
  .day-list {{
    flex: 1; overflow-y: auto;
    margin: 0; padding: 0; list-style: none;
    border-top: 1px solid var(--hairline-soft);
  }}
  .day-list li {{ border-bottom: 1px solid var(--hairline-soft); }}
  .day-link {{
    display: grid; grid-template-columns: 32px 1fr auto; gap: 10px;
    align-items: baseline;
    padding: 12px 12px 12px 14px;
    text-decoration: none; color: var(--ink);
    cursor: pointer;
    transition: background 120ms ease;
  }}
  .day-link:hover {{ background: var(--surface-strong); }}
  .day-link.active {{
    background: var(--canvas-soft);
    border-left: 2px solid var(--primary);
    padding-left: 12px;
  }}
  .day-link.dim {{ opacity: 0.35; }}
  .day-link .num {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; font-weight: 500; color: var(--muted);
    letter-spacing: 0;
  }}
  .day-link .theme {{
    font-size: 14px; font-weight: 500;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .day-link.active .theme {{ color: var(--ink); }}
  .day-link .count {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: var(--muted);
  }}
  .day-link .match-count {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: var(--primary); font-weight: 500;
  }}

  /* ----- Main pane ----- */
  .main {{ padding: 48px 0 96px; min-width: 0; }}
  .day-header .label {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
  }}
  .day-header h1 {{
    font-size: 56px; font-weight: 400; letter-spacing: -0.024em;
    line-height: 1.1; margin: 8px 0 16px;
  }}
  .day-header .meta-row {{
    display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
  }}
  .badge {{
    display: inline-flex; align-items: center;
    background: var(--surface-strong); color: var(--ink);
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; padding: 4px 10px;
    border-radius: 9999px;
  }}
  .meta-text {{ font-size: 14px; color: var(--muted); }}

  .audio-card {{
    margin: 32px 0 16px;
    background: var(--surface-card);
    border: 1px solid var(--hairline);
    border-radius: 12px;
    padding: 16px 20px;
    display: flex; align-items: center; gap: 16px;
  }}
  .audio-label {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
    flex-shrink: 0;
  }}
  audio {{ flex: 1; min-width: 0; height: 36px; }}

  /* ----- Practice toolbar ----- */
  .practice-bar {{
    display: flex; align-items: center; gap: 8px;
    margin: 0 0 16px;
    flex-wrap: wrap;
  }}
  .practice-label {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
    margin-right: 4px;
  }}
  .practice-btn {{
    background: var(--surface-card);
    border: 1px solid var(--hairline-strong);
    color: var(--ink);
    font: inherit; font-size: 13px; font-weight: 500;
    padding: 6px 14px;
    border-radius: 9999px;
    cursor: pointer;
    transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
  }}
  .practice-btn:hover {{ background: var(--surface-strong); }}
  .practice-btn.active {{
    background: var(--ink); color: var(--canvas);
    border-color: var(--ink);
  }}
  .practice-hint {{
    font-size: 12px; color: var(--muted);
    margin-left: 4px;
  }}

  .vocab-card {{
    background: var(--surface-card);
    border: 1px solid var(--hairline);
    border-radius: 12px;
    overflow: hidden;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
    background: var(--canvas-soft);
    text-align: left;
    padding: 14px 20px;
    border-bottom: 1px solid var(--hairline);
  }}
  tbody td {{
    padding: 14px 20px;
    border-bottom: 1px solid var(--hairline-soft);
    vertical-align: top;
  }}
  tbody tr:last-child td {{ border-bottom: 0; }}
  tbody tr.match {{ background: var(--canvas-soft); }}
  tbody tr.dim {{ opacity: 0.35; }}
  td.idx {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; color: var(--muted);
    width: 48px;
  }}
  td.word {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px; font-weight: 500;
    width: 38%;
    word-break: break-word;
  }}
  td.gloss {{
    color: var(--body);
    font-size: 16px;
    font-family: 'Noto Serif TC', 'Inter', system-ui, sans-serif;
  }}

  /* Practice masking — applied to the vocab-card */
  .vocab-card.hide-en td.word,
  .vocab-card.hide-zh td.gloss {{
    cursor: pointer;
    user-select: none;
  }}
  .vocab-card.hide-en td.word .content,
  .vocab-card.hide-zh td.gloss .content {{
    visibility: hidden;
  }}
  .vocab-card.hide-en td.word::after,
  .vocab-card.hide-zh td.gloss::after {{
    content: '— tap to reveal —';
    position: absolute;
    left: 20px; top: 50%; transform: translateY(-50%);
    color: var(--muted-soft);
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 12px; font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    pointer-events: none;
  }}
  .vocab-card.hide-en td.word.revealed .content,
  .vocab-card.hide-zh td.gloss.revealed .content {{
    visibility: visible;
  }}
  .vocab-card.hide-en td.word.revealed::after,
  .vocab-card.hide-zh td.gloss.revealed::after {{
    display: none;
  }}
  .vocab-card.hide-en td.word,
  .vocab-card.hide-zh td.gloss {{
    position: relative;
  }}
  mark {{
    background: var(--accent-mark);
    color: var(--ink);
    padding: 0 2px;
    border-radius: 2px;
  }}

  /* ----- Footer pager ----- */
  .pager {{
    margin-top: 48px;
    display: flex; justify-content: space-between; gap: 16px;
    border-top: 1px solid var(--hairline-soft);
    padding-top: 24px;
  }}
  .pager a {{
    flex: 1; padding: 16px;
    background: var(--surface-card);
    border: 1px solid var(--hairline);
    border-radius: 12px;
    text-decoration: none; color: var(--ink);
    transition: border-color 120ms ease;
  }}
  .pager a:hover {{ border-color: var(--hairline-strong); }}
  .pager a.next {{ text-align: right; }}
  .pager .label {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted);
  }}
  .pager .theme {{
    margin-top: 4px; font-size: 18px;
  }}
  .pager a.disabled {{
    opacity: 0.35; pointer-events: none;
  }}

  /* ----- Empty state ----- */
  .empty {{
    padding: 64px 24px; text-align: center;
    color: var(--muted);
    border: 1px dashed var(--hairline-strong);
    border-radius: 12px;
    background: var(--canvas-soft);
  }}

  /* ----- Footer ----- */
  .site-footer {{
    border-top: 1px solid var(--hairline);
    padding: 32px 0;
    margin-top: 48px;
  }}
  .site-footer .inner {{
    max-width: 1280px; margin: 0 auto; padding: 0 24px;
    display: flex; flex-wrap: wrap; gap: 24px; justify-content: space-between;
    font-size: 13px; color: var(--muted);
  }}
  .site-footer code {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: var(--body);
  }}

  /* ----- Responsive ----- */
  @media (max-width: 960px) {{
    .layout {{ grid-template-columns: 1fr; }}
    .sidebar {{
      position: static; height: auto; max-height: 360px;
      padding-top: 0;
    }}
    .day-header h1 {{ font-size: 36px; }}
    .pager .theme {{ font-size: 14px; }}
  }}
  @media (max-width: 640px) {{
    .top-nav .inner {{ gap: 12px; padding: 0 16px; }}
    .nav-meta {{ display: none; }}
    .layout {{ padding: 0 16px; }}
    .day-header h1 {{ font-size: 28px; }}
    td.word {{ font-size: 14px; }}
    td.gloss {{ font-size: 14px; }}
    th, td {{ padding: 10px 12px !important; }}
  }}

  /* ----- Reduced motion ----- */
  @media (prefers-reduced-motion: reduce) {{
    html {{ scroll-behavior: auto; }}
    * {{ transition: none !important; }}
  }}
</style>
</head>
<body>

<header class="top-nav">
  <div class="inner">
    <a href="#" class="brand" id="brand-link">Hackers TOEIC <span class="accent">Basic</span></a>
    <div class="search-wrap">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="7"></circle>
        <line x1="20" y1="20" x2="16.65" y2="16.65"></line>
      </svg>
      <input id="search" class="search-input" type="search" placeholder="Search words or 中文 glosses…" autocomplete="off">
    </div>
    <div class="nav-meta">{total_words} · {total_days} days</div>
  </div>
</header>

<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="label">Index</div>
      <div class="title">30 Days</div>
    </div>
    <ul class="day-list" id="day-list"></ul>
  </aside>

  <main class="main" id="main"></main>
</div>

<footer class="site-footer">
  <div class="inner">
    <div>Generated from <code>data/1-basic/all.json</code> · Audio at <code>nebo/toeic/1-basic/</code></div>
    <div>Use <code>←</code> / <code>→</code> to step days · <code>R</code> to cycle practice mode · <code>/</code> to focus search</div>
  </div>
</footer>

<script id="data" type="application/json">{embedded_data}</script>
<script>
(function() {{
  const DAYS = JSON.parse(document.getElementById('data').textContent);
  const byDay = Object.fromEntries(DAYS.map(d => [d.day, d]));
  const dayList = document.getElementById('day-list');
  const main = document.getElementById('main');
  const search = document.getElementById('search');
  const brandLink = document.getElementById('brand-link');

  let activeDay = 1;
  let query = '';
  let practiceMode = 'all'; // 'all' | 'hide-en' | 'hide-zh'

  function escapeHtml(s) {{
    return String(s).replace(/[&<>"']/g, c => ({{
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }})[c]);
  }}

  function highlight(text, q) {{
    const t = escapeHtml(text);
    if (!q) return t;
    const i = text.toLowerCase().indexOf(q);
    if (i < 0) return t;
    return escapeHtml(text.slice(0, i))
      + '<mark>' + escapeHtml(text.slice(i, i + q.length)) + '</mark>'
      + escapeHtml(text.slice(i + q.length));
  }}

  function dayMatches(d, q) {{
    if (!q) return d.vocab.length;
    let count = 0;
    for (const v of d.vocab) {{
      if (v.word.toLowerCase().includes(q)) {{ count++; continue; }}
      if (v.meaning_zh.some(g => g.toLowerCase().includes(q))) count++;
    }}
    return count;
  }}

  function renderSidebar() {{
    const q = query;
    dayList.innerHTML = DAYS.map(d => {{
      const matches = q ? dayMatches(d, q) : d.vocab.length;
      const dim = q && matches === 0;
      const active = d.day === activeDay;
      const cls = ['day-link'];
      if (active) cls.push('active');
      if (dim) cls.push('dim');
      const right = q
        ? (matches > 0 ? '<span class="match-count">' + matches + '</span>' : '<span class="count">0</span>')
        : '<span class="count">' + d.vocab.length + '</span>';
      return '<li><a class="' + cls.join(' ') + '" href="#day-' + d.day + '" data-day="' + d.day + '">'
        + '<span class="num">' + String(d.day).padStart(2, '0') + '</span>'
        + '<span class="theme zh">' + escapeHtml(d.theme) + '</span>'
        + right
        + '</a></li>';
    }}).join('');
  }}

  function renderDay(dayNum) {{
    const d = byDay[dayNum];
    if (!d) {{
      main.innerHTML = '<div class="empty">Day not found.</div>';
      return;
    }}
    const q = query;
    const prev = byDay[dayNum - 1];
    const next = byDay[dayNum + 1];

    const rows = d.vocab.map((v, i) => {{
      const wordMatch = q && v.word.toLowerCase().includes(q);
      const glossMatch = q && v.meaning_zh.some(g => g.toLowerCase().includes(q));
      const matched = wordMatch || glossMatch;
      const dim = q && !matched;
      const cls = [];
      if (matched) cls.push('match');
      if (dim) cls.push('dim');
      const wordHtml = wordMatch ? highlight(v.word, q) : escapeHtml(v.word);
      const glossHtml = v.meaning_zh.map(g => {{
        return (q && g.toLowerCase().includes(q)) ? highlight(g, q) : escapeHtml(g);
      }}).join(', ');
      return '<tr' + (cls.length ? ' class="' + cls.join(' ') + '"' : '') + '>'
        + '<td class="idx">' + (i + 1) + '</td>'
        + '<td class="word"><span class="content">' + wordHtml + '</span></td>'
        + '<td class="gloss zh"><span class="content">' + glossHtml + '</span></td>'
        + '</tr>';
    }}).join('');

    const cardClass = practiceMode === 'hide-en' ? 'vocab-card hide-en'
                    : practiceMode === 'hide-zh' ? 'vocab-card hide-zh'
                    : 'vocab-card';
    const btn = (mode, label) => '<button class="practice-btn' + (practiceMode === mode ? ' active' : '') + '" data-mode="' + mode + '">' + label + '</button>';
    const showHint = practiceMode !== 'all';

    main.innerHTML = ''
      + '<div class="day-header">'
      +   '<div class="label">Day ' + d.day + ' / 30</div>'
      +   '<h1 class="zh">' + escapeHtml(d.theme) + '</h1>'
      +   '<div class="meta-row">'
      +     '<span class="badge zh">' + escapeHtml(d.category) + '</span>'
      +     '<span class="meta-text">Page ' + escapeHtml(String(d.page)) + ' · ' + d.vocab.length + ' words</span>'
      +   '</div>'
      + '</div>'
      + '<div class="audio-card">'
      +   '<span class="audio-label">Audio</span>'
      +   '<audio controls preload="none" src="' + d.audio_url + '"></audio>'
      + '</div>'
      + '<div class="practice-bar">'
      +   '<span class="practice-label">Practice</span>'
      +   btn('all', 'Show all')
      +   btn('hide-en', 'Hide English')
      +   btn('hide-zh', 'Hide 中文')
      +   (showHint ? '<span class="practice-hint">tap a cell to reveal · press <code style="font-family:\'JetBrains Mono\',monospace">R</code> to flip mode</span>' : '')
      + '</div>'
      + '<div class="' + cardClass + '"><table>'
      +   '<thead><tr><th>#</th><th>Word</th><th>中文</th></tr></thead>'
      +   '<tbody>' + rows + '</tbody>'
      + '</table></div>'
      + '<nav class="pager">'
      +   (prev
            ? '<a class="prev" href="#day-' + prev.day + '" data-day="' + prev.day + '"><div class="label">← Day ' + prev.day + '</div><div class="theme zh">' + escapeHtml(prev.theme) + '</div></a>'
            : '<a class="prev disabled"><div class="label">Start</div><div class="theme">—</div></a>')
      +   (next
            ? '<a class="next" href="#day-' + next.day + '" data-day="' + next.day + '"><div class="label">Day ' + next.day + ' →</div><div class="theme zh">' + escapeHtml(next.theme) + '</div></a>'
            : '<a class="next disabled"><div class="label">End</div><div class="theme">—</div></a>')
      + '</nav>';
  }}

  function setDay(dayNum, push) {{
    if (!byDay[dayNum]) return;
    activeDay = dayNum;
    if (push) {{
      const target = '#day-' + dayNum;
      if (location.hash !== target) history.replaceState(null, '', target);
    }}
    renderSidebar();
    renderDay(dayNum);
    main.scrollIntoView({{ behavior: 'auto', block: 'start' }});
  }}

  // Routing: clicks
  document.addEventListener('click', e => {{
    const a = e.target.closest('a[data-day]');
    if (!a) return;
    e.preventDefault();
    setDay(parseInt(a.dataset.day, 10), true);
  }});

  // Practice mode buttons
  main.addEventListener('click', e => {{
    const btn = e.target.closest('.practice-btn');
    if (!btn) return;
    practiceMode = btn.dataset.mode;
    renderDay(activeDay);
  }});

  // Click-to-reveal masked cells
  main.addEventListener('click', e => {{
    const td = e.target.closest('td.word, td.gloss');
    if (!td) return;
    const card = td.closest('.vocab-card');
    if (!card) return;
    const isHiddenEn = card.classList.contains('hide-en') && td.classList.contains('word');
    const isHiddenZh = card.classList.contains('hide-zh') && td.classList.contains('gloss');
    if (isHiddenEn || isHiddenZh) td.classList.toggle('revealed');
  }});

  brandLink.addEventListener('click', e => {{
    e.preventDefault();
    setDay(1, true);
    search.value = ''; query = ''; renderSidebar(); renderDay(activeDay);
  }});

  // Routing: hash on load + popstate
  function dayFromHash() {{
    const m = location.hash.match(/^#day-(\d+)$/);
    return m ? parseInt(m[1], 10) : 1;
  }}
  window.addEventListener('hashchange', () => setDay(dayFromHash(), false));

  // Search
  let searchT;
  search.addEventListener('input', () => {{
    clearTimeout(searchT);
    searchT = setTimeout(() => {{
      query = search.value.trim().toLowerCase();
      renderSidebar();
      renderDay(activeDay);
    }}, 80);
  }});

  // Keyboard nav
  document.addEventListener('keydown', e => {{
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
      if (e.key === 'Escape') {{ search.value = ''; query = ''; renderSidebar(); renderDay(activeDay); search.blur(); }}
      return;
    }}
    if (e.key === '/') {{ e.preventDefault(); search.focus(); return; }}
    if (e.key === 'ArrowLeft' && byDay[activeDay - 1]) setDay(activeDay - 1, true);
    if (e.key === 'ArrowRight' && byDay[activeDay + 1]) setDay(activeDay + 1, true);
    if (e.key === 'r' || e.key === 'R') {{
      practiceMode = practiceMode === 'all' ? 'hide-en'
                   : practiceMode === 'hide-en' ? 'hide-zh'
                   : 'all';
      renderDay(activeDay);
    }}
  }});

  // Initial paint
  setDay(dayFromHash(), false);
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
