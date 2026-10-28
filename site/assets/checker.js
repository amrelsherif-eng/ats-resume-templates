/**
 * ATS Resume Checker — client-side PDF inspection using self-hosted pdf.js.
 * Strictly in-browser: files never leave the client.
 * Drafted by Gemini 3.8 Flash from a written spec; reviewed and adjusted.
 */

const dropZone = document.getElementById('chk-drop');
const fileInput = document.getElementById('chk-file');
const outEl = document.getElementById('chk-out');

let pdfjsLib = null;
let lastState = null;

const SECTION_DEFS = [
  // Headings are matched at the start of a line, so body text like "5 years of experience" does not count.
  { name: 'Education', re: /^\s*education\b/im, expected: true },
  { name: 'Experience', re: /^\s*(?:work\s+|professional\s+)?experience\b/im, expected: true },
  { name: 'Skills', re: /^\s*(?:technical\s+)?skills\b/im, expected: true },
  { name: 'Projects', re: /^\s*projects\b/im, expected: false },
  { name: 'Certifications', re: /^\s*certifications?\b/im, expected: false }
];

function t(key, vars = {}) {
  let str = (typeof window.i18nT === 'function' ? window.i18nT(key) : '') || key;
  for (const [k, v] of Object.entries(vars)) {
    str = str.replaceAll(`{${k}}`, v);
  }
  return str;
}

async function getPdfJs() {
  if (!pdfjsLib) {
    const pdfjs = await import('./vendor/pdfjs/pdf.min.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      './vendor/pdfjs/pdf.worker.min.mjs',
      import.meta.url
    ).href;
    pdfjsLib = pdfjs;
  }
  return pdfjsLib;
}

function evaluateResume(file, numPages, text) {
  const checks = [];

  // 1. Pages
  if (numPages === 1) {
    checks.push({ status: 'ok', key: 'chk.pages.ok', vars: { n: numPages } });
  } else if (numPages === 2) {
    checks.push({ status: 'warn', key: 'chk.pages.warn', vars: { n: numPages } });
  } else {
    checks.push({ status: 'fail', key: 'chk.pages.fail', vars: { n: numPages } });
  }

  // 2. Words
  const words = (text.match(/[\p{L}\p{N}][\p{L}\p{N}'’.-]*/gu) || []).length;
  if (words < 80) {
    checks.push({ status: 'fail', key: 'chk.words.low', vars: { n: words } });
  } else if (words > 900) {
    checks.push({ status: 'warn', key: 'chk.words.high', vars: { n: words } });
  } else {
    checks.push({ status: 'ok', key: 'chk.words.ok', vars: { n: words } });
  }

  // 3. Contact details
  const hasEmail = /[\w.+-]+@[\w-]+\.[\w.-]+/.test(text);
  checks.push(hasEmail ? { status: 'ok', key: 'chk.email.ok' } : { status: 'warn', key: 'chk.email.miss' });

  const hasPhone = /\+?\d[\d\s().-]{7,}\d/.test(text);
  checks.push(hasPhone ? { status: 'ok', key: 'chk.phone.ok' } : { status: 'warn', key: 'chk.phone.miss' });

  const hasLi = /linkedin\.com\/in\//i.test(text);
  checks.push(hasLi ? { status: 'ok', key: 'chk.li.ok' } : { status: 'warn', key: 'chk.li.miss' });

  // 4. Headings
  const foundSecs = SECTION_DEFS.filter(s => s.re.test(text)).map(s => s.name);
  const missingExp = SECTION_DEFS.filter(s => s.expected && !s.re.test(text)).map(s => s.name);
  if (missingExp.length > 0) {
    checks.push({ status: 'warn', key: 'chk.sec.miss', vars: { list: missingExp.join(', ') } });
  } else {
    checks.push({ status: 'ok', key: 'chk.sec.ok', vars: { list: foundSecs.join(', ') } });
  }

  // 5. Garbled text
  const garbledCount = (text.match(/\(cid:|\uFFFD/g) || []).length;
  checks.push(
    garbledCount > 3 ? { status: 'fail', key: 'chk.garble.fail' } : { status: 'ok', key: 'chk.garble.ok' }
  );

  // 6. File size
  const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
  if (file.size > 2 * 1024 * 1024) {
    checks.push({ status: 'warn', key: 'chk.size.warn', vars: { n: sizeMB } });
  } else {
    checks.push({ status: 'ok', key: 'chk.size.ok', vars: { n: sizeMB } });
  }

  return { type: 'result', checks, text };
}

function render(state) {
  if (!outEl || !state) return;

  if (state.type === 'error') {
    const ul = document.createElement('ul');
    ul.className = 'chk-list';
    const li = document.createElement('li');
    li.className = 'fail';
    li.textContent = t(state.key);
    ul.appendChild(li);
    outEl.replaceChildren(ul);
    return;
  }

  const passed = state.checks.filter(c => c.status === 'ok').length;
  const total = state.checks.length;

  const scoreEl = document.createElement('p');
  scoreEl.className = 'chk-score';
  scoreEl.textContent = t('chk.score', { n: passed, t: total });

  const ul = document.createElement('ul');
  ul.className = 'chk-list';
  for (const c of state.checks) {
    const li = document.createElement('li');
    li.className = c.status;
    li.textContent = t(c.key, c.vars);
    ul.appendChild(li);
  }

  const details = document.createElement('details');
  details.className = 'chk-text';
  const summary = document.createElement('summary');
  summary.textContent = t('chk.preview');
  const pre = document.createElement('pre');
  pre.textContent = state.text.slice(0, 3000);
  details.append(summary, pre);

  const priv = document.createElement('p');
  priv.className = 'chk-private';
  priv.textContent = t('chk.private');

  outEl.replaceChildren(scoreEl, ul, details, priv);
}

async function handleFile(file) {
  if (!file) return;

  if (file.size > 25 * 1024 * 1024) {
    lastState = { type: 'error', key: 'chk.tooBig' };
    render(lastState);
    return;
  }

  if (fileInput) fileInput.disabled = true;

  if (outEl) {
    const loading = document.createElement('p');
    loading.className = 'chk-reading';
    loading.textContent = t('chk.reading');
    outEl.replaceChildren(loading);
  }

  try {
    const pdfjs = await getPdfJs();
    const buffer = await file.arrayBuffer();
    // isEvalSupported: false keeps pdf.js inside the page CSP (no eval).
    const pdf = await pdfjs.getDocument({ data: buffer, isEvalSupported: false }).promise;

    let fullText = '';
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const content = await page.getTextContent();
      for (const item of content.items) {
        if (typeof item.str === 'string') {
          fullText += item.str + (item.hasEOL ? '\n' : ' ');
        }
      }
    }

    lastState = evaluateResume(file, pdf.numPages, fullText);
    pdf.destroy();
    render(lastState);
  } catch {
    lastState = { type: 'error', key: 'chk.error' };
    render(lastState);
  } finally {
    if (fileInput) {
      fileInput.disabled = false;
      fileInput.value = '';
    }
  }
}

function init() {
  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    if (file) handleFile(file);
  });

  let dragDepth = 0;
  dropZone.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragDepth++;
    dropZone.classList.add('drag');
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
  });

  dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragDepth--;
    if (dragDepth <= 0) {
      dragDepth = 0;
      dropZone.classList.remove('drag');
    }
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDepth = 0;
    dropZone.classList.remove('drag');
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  });

  // A file dropped outside the zone should not make the browser leave the page.
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => { if (!dropZone.contains(e.target)) e.preventDefault(); });

  document.addEventListener('langchange', () => {
    if (lastState) render(lastState);
  });
}

init();
