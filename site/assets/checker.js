/**
 * ATS check UI: reads a resume PDF in the browser (the file never leaves the device),
 * runs the extraction, layout and content checks, and renders a scored report.
 * Modules in ./ats/ were drafted by Codex and Gemini from written specs and reviewed.
 */
import { extract } from './ats/extract.js';
import { layoutIssues, I18N_EN as LAYOUT_EN } from './ats/layout.js';
import { contentIssues, I18N_EN as RULES_EN } from './ats/rules.js';
import { CHECK_AR } from './ats/i18n-ar.js';

const MAX_BYTES = 25 * 1024 * 1024;
const CATS = [
  { id: 'parse', weight: 0.4 },
  { id: 'content', weight: 0.35 },
  { id: 'contact', weight: 0.25 }
];
const LEVEL_ORDER = { fail: 0, warn: 1, info: 2, ok: 3 };
const CHECK_EN = { ...LAYOUT_EN, ...RULES_EN };

const drop = document.getElementById('chk-drop');
const input = document.getElementById('chk-file');
const out = document.getElementById('chk-out');
const levels = document.getElementById('chk-level');

let pdfjs = null;
let lastDoc = null;
let lastError = null;
let level = 'student';

/** UI strings come from the page dictionary; check messages from the module dictionaries. */
function ui(key, vars) { return fill((window.i18nT && window.i18nT(key)) || key, vars); }
function msg(key, vars) {
  const ar = document.documentElement.lang === 'ar';
  return fill((ar && CHECK_AR[key]) || CHECK_EN[key] || key, vars);
}
function fill(s, vars = {}) {
  return String(s).replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m));
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

async function loadPdfJs() {
  if (!pdfjs) {
    pdfjs = await import('./vendor/pdfjs/pdf.min.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;
  }
  return pdfjs;
}

/** 100 minus weighted penalties, per category, then a weighted overall score. */
function score(issues) {
  const per = {};
  for (const c of CATS) {
    const list = issues.filter(i => i.cat === c.id);
    const max = list.reduce((s, i) => s + i.weight, 0) || 1;
    const lost = list.reduce((s, i) => s + i.weight * (i.level === 'fail' ? 1 : i.level === 'warn' ? 0.5 : 0), 0);
    per[c.id] = Math.round(100 * (1 - lost / max));
  }
  const overall = Math.round(CATS.reduce((s, c) => s + per[c.id] * c.weight, 0));
  // A resume an ATS cannot read at all should never look "good".
  const unreadable = issues.some(i => i.id === 'selectable-text' && i.level === 'fail');
  return { per, overall: unreadable ? Math.min(overall, 25) : overall };
}

function band(n) { return n >= 85 ? 'great' : n >= 70 ? 'good' : n >= 50 ? 'fair' : 'poor'; }

function ring(value) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 120 120');
  svg.setAttribute('class', 'ring ' + band(value));
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', ui('chk.score.aria', { n: value }));
  const r = 52, c = 2 * Math.PI * r;
  for (const [cls, dash] of [['track', c], ['bar', c * value / 100]]) {
    const circle = document.createElementNS(NS, 'circle');
    circle.setAttribute('cx', '60'); circle.setAttribute('cy', '60'); circle.setAttribute('r', String(r));
    circle.setAttribute('class', cls);
    circle.setAttribute('stroke-dasharray', `${dash} ${c}`);
    svg.append(circle);
  }
  const t = document.createElementNS(NS, 'text');
  t.setAttribute('x', '60'); t.setAttribute('y', '60'); t.setAttribute('class', 'ring-n');
  t.textContent = String(value);
  svg.append(t);
  // The bar animates from 0 to the score via the registered --score property.
  requestAnimationFrame(() => requestAnimationFrame(() => svg.style.setProperty('--score', String(value))));
  return svg;
}

function issueRow(i) {
  const d = el('details', 'issue ' + i.level);
  const s = el('summary');
  s.append(el('span', 'dot'), el('span', 'issue-t', msg(i.key, i.vars)));
  d.append(s);
  const body = el('div', 'issue-b');
  if (i.fix) body.append(el('p', 'issue-fix', msg(i.fix, i.vars)));
  if (i.examples?.length) {
    body.append(el('p', 'issue-ex-h', ui('chk.examples')));
    const ul = el('ul', 'issue-ex');
    for (const e of i.examples) ul.append(el('li', '', e)); // plain text from the file: textContent only
    body.append(ul);
  }
  if (body.childNodes.length) d.append(body); else d.classList.add('flat');
  return d;
}

function aiPrompt(issues, doc) {
  const problems = issues.filter(i => i.level === 'fail' || i.level === 'warn')
    .map(i => `- ${CHECK_EN[i.key] ? fill(CHECK_EN[i.key], i.vars) : i.key}${i.examples?.length ? ` (e.g. "${i.examples[0]}")` : ''}`);
  return [
    'Improve my resume text below. Keep it truthful: do not invent numbers, tools or results; ask me for any missing numbers.',
    'Start every bullet with a strong action verb, add measurable results where I can provide them, keep it to the right length for my experience.',
    'An ATS check found these issues:',
    ...(problems.length ? problems : ['- (no major issues; polish wording only)']),
    '',
    'Return the improved bullets section by section.',
    '',
    '--- MY RESUME (extracted text) ---',
    doc.text.slice(0, 12000)
  ].join('\n');
}

function render() {
  if (lastError) {
    const p = el('p', 'chk-error', ui(lastError));
    out.replaceChildren(p);
    return;
  }
  if (!lastDoc) return;
  const doc = lastDoc;
  const issues = [...layoutIssues(doc, { level }), ...contentIssues(doc, { level })]
    .sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level] || b.weight - a.weight);
  const { per, overall } = score(issues);

  const head = el('div', 'chk-head');
  const summary = el('div', 'chk-sum');
  summary.append(el('p', 'chk-verdict', ui('chk.band.' + band(overall))));
  summary.append(el('p', 'chk-file', `${doc.fileName} · ${doc.pages} ${ui('chk.pagesWord')}`));
  const bars = el('div', 'bars');
  for (const c of CATS) {
    const row = el('div', 'barrow');
    row.append(el('span', 'bar-l', ui('chk.cat.' + c.id)));
    const track = el('span', 'bar-t');
    const fillEl = el('span', 'bar-f ' + band(per[c.id]));
    fillEl.style.setProperty('--scale', String(per[c.id] / 100));
    track.append(fillEl);
    row.append(track, el('span', 'bar-n', String(per[c.id])));
    bars.append(row);
  }
  summary.append(bars);
  head.append(ring(overall), summary);

  const problems = issues.filter(i => i.level !== 'ok');
  const passed = issues.filter(i => i.level === 'ok');
  const list = el('div', 'issues');
  list.append(el('h3', 'issues-h', problems.length ? ui(problems.length === 1 ? 'chk.toFix1' : 'chk.toFix', { n: problems.length }) : ui('chk.allGood')));
  for (const category of CATS) {
    const group = problems.filter(i => i.cat === category.id);
    if (!group.length) continue;
    const section = el('div', 'issue-group');
    section.append(el('h4', 'issue-group-h', ui('chk.cat.' + category.id)));
    for (const i of group) section.append(issueRow(i));
    list.append(section);
  }

  const ok = el('details', 'passed');
  ok.append(el('summary', '', ui(passed.length === 1 ? 'chk.passed1' : 'chk.passed', { n: passed.length })));
  for (const category of CATS) {
    const group = passed.filter(i => i.cat === category.id);
    if (!group.length) continue;
    const section = el('div', 'issue-group');
    section.append(el('h4', 'issue-group-h', ui('chk.cat.' + category.id)));
    for (const i of group) section.append(issueRow(i));
    ok.append(section);
  }

  const tools = el('div', 'chk-tools');
  const aiBtn = el('button', 'btn sm', ui('chk.ai'));
  aiBtn.type = 'button';
  aiBtn.addEventListener('click', async () => {
    let done = false;
    try { await navigator.clipboard.writeText(aiPrompt(issues, doc)); done = true; } catch { done = false; }
    aiBtn.textContent = done ? ui('copied') : ui('copy.fail');
    setTimeout(() => { aiBtn.textContent = ui('chk.ai'); }, 1800);
  });
  tools.append(aiBtn, el('span', 'chk-ai-note', ui('chk.ai.note')));

  const text = el('details', 'chk-text');
  text.append(el('summary', '', ui('chk.preview')));
  text.append(el('pre', '', doc.streamText.slice(0, 6000)));

  out.replaceChildren(head, list, ok, tools, text, el('p', 'chk-private', ui('chk.private')));
}

async function handle(file) {
  if (!file) return;
  lastError = null;
  if (file.size > MAX_BYTES) { lastError = 'chk.tooBig'; lastDoc = null; render(); return; }
  input.disabled = true;
  out.replaceChildren(el('p', 'chk-reading', ui('chk.reading')));
  try {
    lastDoc = await extract(await loadPdfJs(), file);
  } catch {
    lastDoc = null;
    lastError = 'chk.error';
  } finally {
    input.disabled = false;
    input.value = '';
  }
  render();
  out.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' });
}

function init() {
  if (!drop || !input || !out) return;
  try { level = localStorage.getItem('chk-level') || level; } catch { /* storage blocked */ }
  if (levels) {
    const current = levels.querySelector(`input[value="${level}"]`);
    if (current) current.checked = true;
    levels.addEventListener('change', e => {
      level = e.target.value;
      try { localStorage.setItem('chk-level', level); } catch { /* ignore */ }
      render();
    });
  }
  input.addEventListener('change', () => handle(input.files?.[0]));
  drop.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
  });
  let depth = 0;
  drop.addEventListener('dragenter', e => { e.preventDefault(); depth += 1; drop.classList.add('drag'); });
  drop.addEventListener('dragover', e => e.preventDefault());
  drop.addEventListener('dragleave', () => { depth -= 1; if (depth <= 0) { depth = 0; drop.classList.remove('drag'); } });
  drop.addEventListener('drop', e => {
    e.preventDefault(); depth = 0; drop.classList.remove('drag');
    handle(e.dataTransfer?.files?.[0]);
  });
  // A file dropped outside the zone should not navigate away from the page.
  window.addEventListener('dragover', e => e.preventDefault());
  window.addEventListener('drop', e => { if (!drop.contains(e.target)) e.preventDefault(); });
  document.addEventListener('langchange', render);

  // Warm up pdf.js (about 1.4 MB) in the background once the checker scrolls into view,
  // so the first check feels instant. The worker file is fetched too so it is cached.
  const warm = () => {
    loadPdfJs().catch(() => { /* retried on first check */ });
    fetch(new URL('./vendor/pdfjs/pdf.worker.min.mjs', import.meta.url)).catch(() => {});
  };
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { io.disconnect(); warm(); }
    }, { rootMargin: '600px 0px' });
    io.observe(drop);
  } else {
    warm();
  }
}

init();
