/* ATS Resume Templates site: template cards, tabs, copy buttons, language switch. */
'use strict';

const REPO = 'https://github.com/amrelsherif-eng/ats-resume-templates';
const RAW = 'https://raw.githubusercontent.com/amrelsherif-eng/ats-resume-templates/main/templates';
// Optional support link (for example GitHub Sponsors). Leave empty to hide the button.
const SUPPORT_URL = '';
// Optional demo video, self-hosted under site/assets/video/. Leave src empty to hide the section.
const VIDEO = { src: '', poster: '', captionsEn: '', captionsAr: '' };

const TEMPLATES = [
  { id: 'software-web', group: 'sw', color: '#c084fc', skills: ['NestJS', 'PostgreSQL', 'Redis', 'Docker', 'React'],
    view: 'https://www.overleaf.com/project/6ae24cbbb91643c3433bdf53/share#5c212b281201e2cd4d1433f0877a918fec537672141ba0e4' },
  { id: 'business-finance', group: 'biz', color: '#58a6ff', skills: ['Reconciliations', 'Power BI', 'Excel', 'DCF', 'SAP'],
    view: 'https://www.overleaf.com/project/6ae24d2b537127bac7e70376/share#5cc2e5131e359736c6fb784a325e766dd439be52c846f976' },
  { id: 'network-cloud', group: 'eng', color: '#00f0ff', skills: ['AWS', 'Terraform', 'Linux', 'BGP', 'Zabbix'],
    view: 'https://www.overleaf.com/read/wxvvcdjzxnng#d23995' },
  { id: 'embedded-ece', group: 'eng', color: '#ffb300', skills: ['STM32', 'C', 'PID', 'LoRaWAN', 'RTOS'],
    view: 'https://www.overleaf.com/read/rjnzhhzrhffz#dd0591' },
  { id: 'mobile-apps', group: 'sw', color: '#3fb950', skills: ['Flutter', 'Dart', 'Riverpod', 'Firebase', 'Testing'],
    view: 'https://www.overleaf.com/read/ytqxjshntmfb#335363' }
];

const STRINGS = { en: EN, ar: AR };
let lang = 'en';

/** Translate a key for the current language, falling back to English. */
function t(key) {
  return (STRINGS[lang] && STRINGS[lang][key]) || EN[key] || key;
}
window.i18nT = t;

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'text') node.textContent = v;
    else if (k === 'class') node.className = v;
    // CSP blocks style attributes; CSSOM properties are allowed.
    else if (k === 'style') for (const d of v.split(';')) { const [p, val] = d.split(':'); if (p) node.style.setProperty(p.trim(), val.trim()); }
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c) node.append(c);
  return node;
}

function overleafOpen(id) {
  return 'https://www.overleaf.com/docs?snip_uri=' + encodeURIComponent(`${RAW}/${id}/resume.tex`);
}

function preview(id, alt, eager) {
  return el('picture', {}, [
    el('source', { type: 'image/webp', srcset: `templates/${id}/preview-640.webp 640w, templates/${id}/preview.webp 850w`, sizes: '(max-width: 600px) 92vw, 360px' }),
    el('img', { src: `templates/${id}/preview.png`, alt, width: '850', height: '1100', loading: eager ? 'eager' : 'lazy', decoding: 'async' })
  ]);
}

function renderCards() {
  const grid = document.getElementById('grid');
  grid.replaceChildren();
  for (const x of TEMPLATES) {
    const name = t(x.id + '.n');
    const card = el('article', { class: 'card', 'data-g': x.group, style: `--c:${x.color}` });
    card.append(
      el('a', { class: 'shot', href: `templates/${x.id}/resume.pdf`, target: '_blank', rel: 'noopener', 'aria-label': `${name} PDF` }, preview(x.id, `${name} — ${t('alt.preview')}`)),
      el('div', { class: 'body' }, [
        el('span', { class: 'tag', text: x.id }),
        el('h3', { text: name }),
        el('p', { text: t(x.id + '.b') }),
        el('div', { class: 'skills' }, x.skills.map(s => el('span', { text: s }))),
        el('div', { class: 'actions' }, [
          el('a', { class: 'btn sm primary', href: overleafOpen(x.id), target: '_blank', rel: 'noopener', text: t('btn.ol') }),
          el('a', { class: 'btn sm', href: x.view, target: '_blank', rel: 'noopener', text: t('btn.view') }),
          el('a', { class: 'btn sm', href: `templates/${x.id}/resume.pdf`, target: '_blank', rel: 'noopener', text: 'PDF' }),
          el('button', { class: 'btn sm ai', type: 'button', 'data-ai': x.id, text: t('btn.ai') })
        ])
      ])
    );
    grid.append(card);
  }
  grid.append(el('article', { class: 'card request', 'data-g': 'all' }, [
    el('h3', { text: t('req.t') }),
    el('p', { text: t('req.p') }),
    el('a', { class: 'btn sm', href: `${REPO}/issues/new`, target: '_blank', rel: 'noopener', text: t('req.b') })
  ]));
  applyFilter(document.querySelector('.chip[aria-pressed="true"]').dataset.f);
}

function applyFilter(f) {
  document.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.f === f)));
  document.querySelectorAll('#grid .card').forEach(c => {
    c.hidden = !(f === 'all' || c.dataset.g === f || c.dataset.g === 'all');
  });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = el('textarea', { class: 'sr-only', readonly: '' });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}

function flash(btn, ok) {
  const label = btn.dataset.label || btn.textContent;
  btn.dataset.label = label;
  btn.textContent = ok ? t('copied') : t('copy.fail');
  btn.classList.toggle('done', ok);
  setTimeout(() => { btn.textContent = btn.dataset.label; btn.classList.remove('done'); delete btn.dataset.label; }, 1800);
}

function selectTab(tab, focus) {
  document.querySelectorAll('.tab').forEach(x => {
    const on = x === tab;
    x.setAttribute('aria-selected', String(on));
    x.tabIndex = on ? 0 : -1;
    document.getElementById(x.getAttribute('aria-controls')).hidden = !on;
    document.getElementById(x.getAttribute('aria-controls')).classList.toggle('active', on);
  });
  if (focus) tab.focus();
}

function applyLang() {
  const root = document.documentElement;
  root.lang = lang;
  root.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.querySelectorAll('[data-i]').forEach(e => {
    const v = t(e.dataset.i);
    // Only our own translation strings contain markup (<b>, <a>); never user data.
    if (/[<>]/.test(v)) e.innerHTML = v; else e.textContent = v;
  });
  const btn = document.getElementById('lang');
  btn.textContent = lang === 'ar' ? 'English' : 'عربي';
  btn.lang = lang === 'ar' ? 'en' : 'ar';
  btn.setAttribute('aria-label', lang === 'ar' ? 'Switch to English' : 'التبديل إلى العربية');
  document.title = t('meta.title');
  renderCards();
  document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
}

function buildFan() {
  const fan = document.getElementById('fan');
  ['network-cloud', 'embedded-ece', 'software-web', 'mobile-apps', 'business-finance'].forEach((id, i) => {
    const page = el('div', { class: 'page' }, preview(id, '', i === 2));
    if (i === 2) page.append(el('div', { class: 'scan' }));
    fan.append(page);
  });
  // Real results for these templates (see the checker and CI), not marketing numbers.
  for (const [cls, mark, text] of [['b1', '✓', '1 page'], ['b2', '100', '/ 100 ATS check'], ['b3', '✓', 'text extracts cleanly']]) {
    const b = el('div', { class: 'badge ' + cls });
    b.append(el('b', { text: mark }), ' ' + text);
    fan.append(b);
  }
}

function init() {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'ar' || saved === 'en') lang = saved;
    else if ((navigator.language || '').toLowerCase().startsWith('ar')) lang = 'ar';
  } catch { /* storage blocked: keep default */ }

  buildFan();

  document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => applyFilter(c.dataset.f)));

  const tabs = [...document.querySelectorAll('.tab')];
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', e => {
      const rtl = document.documentElement.dir === 'rtl';
      const next = { ArrowRight: rtl ? -1 : 1, ArrowLeft: rtl ? 1 : -1, Home: -i, End: tabs.length - 1 - i }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      selectTab(tabs[(i + next + tabs.length) % tabs.length], true);
    });
  });

  document.addEventListener('click', async e => {
    const copyBtn = e.target.closest('[data-copy]');
    if (copyBtn) {
      flash(copyBtn, await copyText(document.getElementById(copyBtn.dataset.copy).innerText));
      return;
    }
    const aiBtn = e.target.closest('[data-ai]');
    if (aiBtn) {
      aiBtn.disabled = true;
      try {
        const res = await fetch(`templates/${aiBtn.dataset.ai}/resume.tex`);
        if (!res.ok) throw new Error(res.status);
        const tex = await res.text();
        const prompt = document.getElementById('prompt').innerText;
        flash(aiBtn, await copyText(`${prompt}\n\n--- TEMPLATE (resume.tex) ---\n${tex}`));
      } catch {
        flash(aiBtn, false);
      } finally {
        aiBtn.disabled = false;
      }
    }
  });

  document.getElementById('lang').addEventListener('click', () => {
    lang = lang === 'ar' ? 'en' : 'ar';
    try { localStorage.setItem('lang', lang); } catch { /* ignore */ }
    applyLang();
  });

  const support = document.getElementById('support');
  if (SUPPORT_URL) { support.href = SUPPORT_URL; support.hidden = false; }

  if (VIDEO.src) {
    const video = document.getElementById('demo-video');
    if (VIDEO.poster) video.poster = VIDEO.poster;
    video.append(el('source', { src: VIDEO.src, type: 'video/mp4' }));
    for (const [src, code, label] of [[VIDEO.captionsEn, 'en', 'English'], [VIDEO.captionsAr, 'ar', 'العربية']]) {
      if (src) video.append(el('track', { kind: 'captions', src, srclang: code, label }));
    }
    document.getElementById('video').hidden = false;
  }

  applyLang();
}

init();
