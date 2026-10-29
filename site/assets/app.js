/* ATS Resume Templates site: template cards, tabs, copy buttons, language switch. */
'use strict';
document.documentElement.classList.add('js');

const REPO = 'https://github.com/amrelsherif-eng/ats-resume-templates';
const RAW = 'https://raw.githubusercontent.com/amrelsherif-eng/ats-resume-templates/main/templates';
const ISSUE_TEMPLATE_URL = `${REPO}/issues/new?title=Template%20request%3A%20&body=Which%20career%20track%3F%0A%0AWhat%20should%20the%20template%20emphasise%3F`;
// Optional support link (for example GitHub Sponsors). Leave empty to hide the button.
const SUPPORT_URL = 'https://github.com/sponsors/amrelsherif-eng';
// Optional demo video, self-hosted under site/assets/video/. Leave src empty to hide the section.
const VIDEO = { src: '', poster: '', captionsEn: '', captionsAr: '' };

const TEMPLATES = [
  { id: 'software-web', color: '#c084fc', skills: ['NestJS', 'PostgreSQL', 'Redis', 'Docker', 'React'],
    view: 'https://www.overleaf.com/project/6ae24cbbb91643c3433bdf53/share#5c212b281201e2cd4d1433f0877a918fec537672141ba0e4' },
  { id: 'business-finance', color: '#58a6ff', skills: ['Reconciliations', 'Power BI', 'Excel', 'DCF', 'SAP'],
    view: 'https://www.overleaf.com/project/6ae24d2b537127bac7e70376/share#5cc2e5131e359736c6fb784a325e766dd439be52c846f976' },
  { id: 'network-cloud', color: '#00f0ff', skills: ['AWS', 'Terraform', 'Linux', 'BGP', 'Zabbix'],
    view: 'https://www.overleaf.com/read/wxvvcdjzxnng#d23995' },
  { id: 'embedded-ece', color: '#ffb300', skills: ['STM32', 'C', 'PID', 'LoRaWAN', 'RTOS'],
    view: 'https://www.overleaf.com/read/rjnzhhzrhffz#dd0591' },
  { id: 'mobile-apps', color: '#3fb950', skills: ['Flutter', 'Dart', 'Riverpod', 'Firebase', 'Testing'],
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

function preview(id, alt, eager, sizes = '(max-width: 600px) 92vw, 380px') {
  return el('picture', {}, [
    el('source', { type: 'image/webp', srcset: `templates/${id}/preview-400.webp 400w, templates/${id}/preview-640.webp 640w, templates/${id}/preview.webp 850w`, sizes }),
    el('img', { src: `templates/${id}/preview.png`, alt, width: '850', height: '1100', loading: eager ? 'eager' : 'lazy', decoding: 'async' })
  ]);
}

function renderCards() {
  const grid = document.getElementById('grid');
  grid.replaceChildren();
  for (const x of TEMPLATES) {
    const name = t(x.id + '.n');
    const card = el('article', { id: `tpl-${x.id}`, class: 'card', style: `--c:${x.color}` });
    card.append(
      el('a', { class: 'shot', href: `templates/${x.id}/resume.pdf`, target: '_blank', rel: 'noopener', 'aria-label': `${name} PDF` }, preview(x.id, `${name} — ${t('alt.preview')}`)),
      el('div', { class: 'body' }, [
        el('h3', { text: name }),
        el('span', { class: 'tag', text: t(x.id + '.en') }),
        el('p', { class: 'difference', text: t(x.id + '.d') }),
        el('p', { text: t(x.id + '.b') }),
        el('div', { class: 'skills' }, x.skills.map(s => el('span', { text: s }))),
        el('div', { class: 'actions' }, [
          el('a', { class: 'btn sm primary', href: overleafOpen(x.id), target: '_blank', rel: 'noopener', text: t('btn.ol') }),
          el('button', { class: 'btn sm ai', type: 'button', 'data-ai': x.id, 'aria-live': 'polite', text: t('btn.ai') }),
          el('a', { class: 'btn sm sample', href: x.view, target: '_blank', rel: 'noopener', text: t('btn.view') })
        ])
      ])
    );
    grid.append(card);
  }
  grid.append(el('article', { class: 'card request' }, [
    el('h3', { text: t('req.t') }),
    el('p', { text: t('req.p') }),
    el('a', { class: 'btn sm',     href: ISSUE_TEMPLATE_URL, target: '_blank', rel: 'noopener', text: t('req.b') })
  ]));
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

function flash(btn, ok, duration = 1800, success = t('copied')) {
  const label = btn.dataset.label || btn.textContent;
  btn.dataset.label = label;
  btn.textContent = ok ? success : t('copy.fail');
  btn.classList.toggle('done', ok);
  setTimeout(() => { btn.textContent = btn.dataset.label; btn.classList.remove('done'); delete btn.dataset.label; }, duration);
}

function updateTabIndicator(tab) {
  const tabs = document.querySelector('.tabs');
  if (!tabs || !tab) return;
  const list = [...tabs.querySelectorAll('.tab')];
  const width = tab.offsetWidth;
  const x = list.slice(0, list.indexOf(tab)).reduce((sum, item) => sum + item.offsetWidth, 0);
  tabs.style.setProperty('--tab-width', width + 'px');
  tabs.style.setProperty('--tab-x', x + 'px');
}

function selectTab(tab, focus) {
  document.querySelectorAll('.tab').forEach(x => {
    const on = x === tab;
    x.setAttribute('aria-selected', String(on));
    x.tabIndex = on ? 0 : -1;
    document.getElementById(x.getAttribute('aria-controls')).hidden = !on;
    document.getElementById(x.getAttribute('aria-controls')).classList.toggle('active', on);
  });
  const localPanel = document.getElementById('p-lc');
  const localLink = document.getElementById('local-link');
  localPanel.hidden = true;
  localPanel.classList.remove('active');
  localLink.setAttribute('aria-expanded', 'false');
  updateTabIndicator(tab);
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
  document.querySelectorAll('[data-i-aria]').forEach(e => e.setAttribute('aria-label', t(e.dataset.iAria)));
  document.title = t('meta.title');
  renderCards();
  document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
}

function buildFan() {
  const fan = document.getElementById('fan');
  ['network-cloud', 'embedded-ece', 'software-web', 'mobile-apps', 'business-finance'].forEach((id, i) => {
    const page = el('div', { class: 'page' }, preview(id, '', true, '(max-width: 900px) 200px, 260px')); // above the fold: load eagerly (LCP)
    if (i === 2) page.append(el('div', { class: 'scan' }));
    fan.append(page);
  });
  for (const [cls, key] of [['b1', 'fan.sample'], ['b2', 'fan.page'], ['b3', 'fan.readability']]) {
    fan.append(el('div', { class: 'badge ' + cls, text: t(key) }));
  }
}

function init() {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'ar' || saved === 'en') lang = saved;
    else if ((navigator.language || '').toLowerCase().startsWith('ar')) lang = 'ar';
  } catch { /* storage blocked: keep default */ }

  buildFan();

  const fan = document.getElementById('fan');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
  if ('IntersectionObserver' in window && !reduceMotion.matches) {
    // Only animate what starts below the fold: content visible on load must paint at once (LCP).
    const targets = [...document.querySelectorAll('main section, .grid .card')]
      .filter(node => node.getBoundingClientRect().top > innerHeight);
    targets.forEach((node, index) => { node.classList.add('reveal'); if (node.matches('.grid .card')) node.style.setProperty('--reveal-index', index % 5); });
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), { rootMargin: '0px 0px -6% 0px' });
    targets.forEach(node => observer.observe(node));
  }

  if (matchMedia('(hover: hover) and (pointer: fine)').matches && !reduceMotion.matches) {
    let frame = 0;
    fan.addEventListener('pointermove', e => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        const r = fan.getBoundingClientRect();
        // Layered parallax: each page moves by its own depth (--d), which reads as 3D without distortion.
        const x = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width - .5) * 2));
        const y = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height - .5) * 2));
        fan.style.setProperty('--px', (x * 10).toFixed(2) + 'px');
        fan.style.setProperty('--py', (y * 6).toFixed(2) + 'px');
        frame = 0;
      });
    });
    fan.addEventListener('pointerleave', () => { fan.style.setProperty('--px', '0px'); fan.style.setProperty('--py', '0px'); });
  }
  document.querySelectorAll('.grid').forEach(g => g.addEventListener('pointermove', e => {
    const card = e.target.closest('.card'); if (!card || reduceMotion.matches) return;
    const r = card.getBoundingClientRect(); card.style.setProperty('--mx', (e.clientX-r.left) + 'px'); card.style.setProperty('--my', (e.clientY-r.top) + 'px');
  }));

  const tabs = [...document.querySelectorAll('.tab')];
  updateTabIndicator(tabs.find(tab => tab.getAttribute('aria-selected') === 'true'));
  document.addEventListener('langchange', () => {
    const selected = tabs.find(tab => tab.getAttribute('aria-selected') === 'true');
    if (selected) updateTabIndicator(selected);
  });
  const localLink = document.getElementById('local-link');
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
  localLink.addEventListener('click', e => {
    e.preventDefault();
    for (const tab of tabs) {
      tab.setAttribute('aria-selected', 'false');
      tab.tabIndex = tab === tabs[0] ? 0 : -1;
      const panel = document.getElementById(tab.getAttribute('aria-controls'));
      panel.hidden = true;
      panel.classList.remove('active');
    }
    const panel = document.getElementById('p-lc');
    panel.hidden = false;
    panel.classList.add('active');
    localLink.setAttribute('aria-expanded', 'true');
    document.querySelector('.tabs').style.setProperty('--tab-width', '0px');
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
        flash(aiBtn, await copyText(`${prompt}\n\n--- TEMPLATE (resume.tex) ---\n${tex}`), 3000, t('copied.ai'));
      } catch {
        flash(aiBtn, false);
      } finally {
        aiBtn.disabled = false;
      }
    }
  });

  const menu = document.getElementById('menu-toggle');
  const navPanel = document.getElementById('nav-panel');
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    navPanel.classList.toggle('open', open);
  });
  navPanel.addEventListener('click', e => { if (e.target.closest('a')) { menu.setAttribute('aria-expanded','false'); navPanel.classList.remove('open'); } });

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
    video.hidden = false;
    document.getElementById('video-soon').remove();
  }

  applyLang();
}

init();
