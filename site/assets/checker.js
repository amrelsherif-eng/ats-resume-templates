/**
 * ATS check UI: reads a resume PDF in the browser (the file never leaves the device),
 * runs the extraction, layout and content checks, and renders a scored report.
 * Modules in ./ats/ were drafted by Codex and Gemini from written specs and reviewed.
 */
import { extract } from './ats/extract.js';
import { layoutIssues, I18N_EN as LAYOUT_EN } from './ats/layout.js';
import { score, band, CATS } from './ats/score.js';
import { contentIssues, I18N_EN as RULES_EN } from './ats/rules.js';
import { hiddenIssues, I18N_EN as HIDDEN_EN } from './ats/hidden.js';
import { structureIssues, I18N_EN as STRUCTURE_EN } from './ats/structure.js';
import { robustIssues, I18N_EN as ROBUST_EN } from './ats/robust.js';
import { CHECK_AR, SECTION_AR } from './ats/i18n-ar.js';

const MAX_BYTES = 25 * 1024 * 1024;
const TIMEOUT_MS = 90000;
const LEVEL_ORDER = { fail: 0, warn: 1, info: 2, ok: 3 };
const CHECK_EN = { ...LAYOUT_EN, ...RULES_EN, ...HIDDEN_EN, ...STRUCTURE_EN, ...ROBUST_EN };

const drop = document.getElementById('chk-drop');
const input = document.getElementById('chk-file');
const out = document.getElementById('chk-out');
const levels = document.getElementById('chk-level');
const levelHint = document.getElementById('chk-level-hint');

let pdfjs = null;
let pdfWorker = null; // one pdf.js worker for every file: starting a new one per check is slow on phones
let status = null;    // short screen-reader status ("Report ready: score 92...") instead of a live report
let runId = 0;        // a file dropped while another is read wins: late results of the old one are ignored
let focusNext = false; // move focus to the result once, after a new file (not on level or language change)
let lastDoc = null;
let lastError = null;
let level = 'student';

/** UI strings come from the page dictionary; check messages from the module dictionaries. */
function ui(key, vars) { return fill((window.i18nT && window.i18nT(key)) || key, vars); }
function updateLevelHint() {
  const key = level === 'student' || level === 'junior' ? 'student' : level;
  if (levelHint) levelHint.textContent = ui('chk.hint.' + key);
}
function msg(key, vars) {
  const ar = document.documentElement.lang === 'ar';
  if (ar && vars?.sections) vars = { ...vars, list: vars.sections.map(s => SECTION_AR[s] || s).join('، ') };
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
  const dot = el('span', 'dot');
  dot.setAttribute('aria-hidden', 'true');
  // The coloured icon shows the level to sighted users; screen readers hear it as words.
  s.append(dot, el('span', 'sr-only', ui('chk.sev.' + i.level) + ' '), el('span', 'issue-t', msg(i.key, i.vars)));
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

// Issues an AI can fix by rewriting the text. Not file-level ones (the 'parse' group: file name,
// size, scan, layout) and not missing contact details (email, phone, links): only you can add those.
const textIssues = issues => issues.filter(i => i.level !== 'ok' && i.cat !== 'parse' && !i.id.startsWith('contact-'));

function aiPrompt(issues, doc) {
  const problems = textIssues(issues)
    .map(i => `- ${CHECK_EN[i.key] ? fill(CHECK_EN[i.key], i.vars) : i.key}${i.examples?.length ? ` (e.g. "${i.examples[0]}")` : ''}`);
  return [
    'Improve my resume text below. Keep it truthful: do not invent numbers, tools or results; ask me for any missing numbers.',
    'Start every bullet with a strong action verb, add measurable results where I can provide them, keep it to the right length for my experience.',
    'An ATS check found these issues:',
    ...problems,
    '',
    'Return the improved bullets section by section.',
    '',
    '--- MY RESUME (extracted text) ---',
    doc.text.slice(0, 12000)
  ].join('\n');
}

/** A calm notice above the report when text is hidden or aimed at AI tools: it assumes good intent,
 * quotes what was found and says how to fix it. */
function hiddenAlert(issues) {
  const found = id => issues.find(i => i.id === id && i.level === 'fail');
  const hidden = found('hidden-text'), inject = found('prompt-injection');
  if (!hidden && !inject) return null;
  const box = el('section', 'chk-alert');
  const h = el('h3', 'chk-alert-h', ui(hidden ? 'chk.alert.hidden' : 'chk.alert.inject'));
  h.id = 'chk-alert-h';
  box.setAttribute('aria-labelledby', h.id);
  box.append(h, el('p', 'chk-alert-why', ui('chk.alert.why')), el('p', 'chk-alert-found', ui('chk.alert.found')));
  const ul = el('ul', 'chk-alert-q');
  // An instruction that is itself hidden is already quoted with the hidden text: show it once.
  const flat = q => q.replace(/^"|…?"$/g, '').toLowerCase();
  const hiddenText = (hidden?.examples || []).map(flat).join(' ');
  const quotes = [...(hidden?.examples || []), ...(inject?.examples || []).filter(q => !hiddenText.includes(flat(q).slice(0, 30)))];
  for (const q of quotes.slice(0, 4)) {
    const li = el('li', '', q); // plain text from the file: textContent only
    li.dir = 'auto'; // each quote reads in its own direction (Arabic or English)
    ul.append(li);
  }
  box.append(ul, el('p', 'chk-alert-fix', ui('chk.alert.fix')));
  return box;
}

function render() {
  out.removeAttribute('aria-busy');
  if (lastError) {
    const p = el('p', 'chk-error', ui(lastError));
    p.setAttribute('role', 'alert');
    p.tabIndex = -1;
    out.replaceChildren(p);
    if (status) status.textContent = '';
    showResult(p);
    return;
  }
  if (!lastDoc) return;
  const doc = lastDoc;
  const issues = [...layoutIssues(doc, { level }), ...contentIssues(doc, { level }), ...hiddenIssues(doc), ...structureIssues(doc),
    ...robustIssues(doc)]
    .sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level] || b.weight - a.weight);
  const { per, overall } = score(issues, doc, level);

  const head = el('div', 'chk-head');
  const summary = el('div', 'chk-sum');
  const verdict = el('h3', 'chk-verdict', ui('chk.band.' + band(overall)));
  verdict.tabIndex = -1; // focus target after a check
  summary.append(verdict);
  // The file name is user-controlled: isolate it and keep it short so it cannot pose as report text.
  const name = doc.fileName.length > 60 ? doc.fileName.slice(0, 57) + '…' : doc.fileName;
  const fileLine = el('p', 'chk-file');
  fileLine.append(el('bdi', 'chk-name', name), ` · ${doc.pages} ${ui('chk.pagesWord')}`);
  summary.append(fileLine);
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
  // Only small tips (info) left: say so, instead of "things to improve" under a top score.
  const onlyTips = problems.length && problems.every(i => i.level === 'info');
  const heading = !problems.length ? ui('chk.allGood')
    : ui((onlyTips ? 'chk.tips' : 'chk.toFix') + (problems.length === 1 ? '1' : ''), { n: problems.length });
  list.append(el('h3', 'issues-h', heading));
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
  // The raw content stream shows reading-order problems in left-to-right CVs. Right-to-left text is
  // often stored letter by letter in page order, so for an Arabic CV show the rebuilt lines instead.
  const rtlLines = doc.lines.filter(l => l.rtl).length;
  const shown = rtlLines > doc.lines.length / 2 ? doc.text : doc.streamText;
  const pre = el('pre', '', shown.slice(0, 6000));
  if (shown === doc.text) pre.style.unicodeBidi = 'plaintext'; // each line takes its own direction
  text.append(pre);

  // The fix-it prompt only makes sense when there is text for an AI to fix.
  const alert = hiddenAlert(issues);
  const parts = [head, ...(alert ? [alert] : []), list, ok, ...(textIssues(issues).length ? [tools] : []), text];
  out.replaceChildren(...parts, el('p', 'chk-private', ui('chk.private')));
  if (status) status.textContent = ui('chk.status', { n: overall, k: problems.filter(i => i.level !== 'info').length });
  showResult(verdict);
}

/** After a new file: focus the result (keyboard and screen-reader users land on it) and bring it into view. */
function showResult(target) {
  if (!focusNext) return;
  focusNext = false;
  target.focus({ preventScroll: true });
  const top = out.getBoundingClientRect().top;
  if (top < 0 || top > innerHeight * 0.75) {
    out.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'nearest' });
  }
}

/** Let the browser paint and handle input between steps (slow phones). */
const nextTask = () => (globalThis.scheduler?.yield ? globalThis.scheduler.yield() : new Promise(r => setTimeout(r, 0)));

/** What a file that is not a PDF most likely is, from its first bytes, so the message can say what to do. */
async function sniff(file) {
  const b = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
  const head = String.fromCharCode(...b);
  if (head.includes('%PDF-')) return null;
  const hex = [...b.slice(0, 4)].map(x => x.toString(16).padStart(2, '0')).join('');
  if (hex === '89504e47' || hex.startsWith('ffd8ff') || head.startsWith('GIF8') || hex === '49492a00' || hex === '4d4d002a' ||
      (head.startsWith('RIFF') && head.slice(8, 12) === 'WEBP') || /^[\s\S]{4}ftyp(?:hei|hev|mif|avi)/.test(head)) return 'chk.err.image';
  if (hex === '504b0304' || hex === 'd0cf11e0' || head.startsWith('{\\rtf')) return 'chk.err.doc';
  if (!b.some(x => x < 9 || (x > 13 && x < 32))) return 'chk.err.text';
  return 'chk.err.notpdf';
}

async function handle(file) {
  if (!file) return;
  lastError = null;
  const run = ++runId;
  focusNext = true;
  const fail = key => { lastError = key; lastDoc = null; input.disabled = false; input.value = ''; render(); };
  if (file.size > MAX_BYTES) return fail('chk.tooBig');
  if (file.size === 0) return fail('chk.err.empty');
  input.disabled = true;
  const reading = el('p', 'chk-reading', ui('chk.reading'));
  out.replaceChildren(reading);
  out.setAttribute('aria-busy', 'true');
  if (status) status.textContent = ui('chk.reading');
  try {
    const notPdf = await sniff(file);
    if (notPdf) throw Object.assign(new Error(notPdf), { key: notPdf });
    const lib = await loadPdfJs();
    if (!pdfWorker || pdfWorker.destroyed) pdfWorker = new lib.PDFWorker();
    // A file that never finishes (a stuck worker, a crafted PDF) ends with a message, not an endless spinner.
    let timer, doc;
    const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('timeout')), TIMEOUT_MS); });
    try {
      doc = await Promise.race([timeout, extract(lib, file, {
        worker: pdfWorker,
        yieldFn: nextTask,
        // Long files: show which page is being read (visual only; the status says when the report is ready).
        onProgress: (n, total) => { if (total > 2) reading.textContent = ui('chk.progress', { n, t: total }); },
      })]);
    } finally {
      clearTimeout(timer);
    }
    await nextTask();
    if (run !== runId) return;
    lastDoc = doc;
  } catch (e) {
    if (run !== runId) return;
    lastDoc = null;
    const known = e?.key || (e?.name === 'PasswordException' ? 'chk.err.password'
      : e?.name === 'InvalidPDFException' ? 'chk.err.damaged' : null);
    lastError = known || 'chk.error';
    // An unexpected failure may have broken the worker: start a fresh one next time.
    if (!known) {
      try { pdfWorker?.destroy(); } catch { /* ignore */ }
      pdfWorker = null;
    }
  } finally {
    if (run === runId) { input.disabled = false; input.value = ''; }
  }
  render();
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
      updateLevelHint();
      render();
    });
  }
  updateLevelHint();
  status = el('p', 'sr-only');
  status.id = 'chk-status';
  status.setAttribute('role', 'status');
  out.after(status);
  input.addEventListener('change', () => handle(input.files?.[0]));
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
  document.addEventListener('langchange', () => { updateLevelHint(); render(); });

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
