/** Structure checks (round 3): experience order, tense, undated entries, letter-spaced words, sideways text,
 * a text box merged into the body, light grey text and profile links hidden behind a word.
 * Every check here reports only when it finds something (no "ok" rows), and each was measured on the
 * test corpora first: zero hits on good CVs and on the site's own templates. Pure: reads only the Doc. */
import { ACTION_VERBS, NOT_VERBS, detectHeading, otherLanguage } from './rules.js';

export const I18N_EN = {
  's.chrono': 'Your experience is not listed newest first.',
  's.chrono.fix': 'Most recruiters and ATS expect your most recent role at the top. Reorder the entries if that was not on purpose.',
  's.tense': 'Some past roles mix tenses.',
  's.tense.fix': 'Use the past tense for roles you have left (Managed, Built) and keep one tense within each role.',
  's.dates': '{n} of {of} experience entries have no dates.',
  's.dates.fix': 'Add a start and end month and year to every role; many ATS work out your years of experience from them.',
  's.spaced': 'Some words are spaced out letter by letter.',
  's.spaced.fix': 'Some ATS read these as separate letters, so a heading like E X P E R I E N C E is missed. Remove the extra letter spacing and type the words normally.',
  's.rotated': 'Some text is turned sideways.',
  's.rotated.fix': 'Some ATS skip sideways text or read it letter by letter. Keep anything important horizontal.',
  's.sidebox': 'A text box beside your main text gets mixed into your sentences.',
  's.sidebox.fix': "Many ATS read straight across the page, so the box's lines land inside your paragraphs. Move its content into the main text, then export the PDF again.",
  's.contrast': 'Much of the text is light grey ({pct}% of letters).',
  's.contrast.fix': 'Use dark text (black or dark grey) on a white background so it stays readable when printed, scanned or read by OCR.',
  's.link': 'Your profile link is hidden behind a word.',
  's.link.fix': 'Many ATS keep only the visible text, so they see "LinkedIn" but not the address. Write the address itself, for example linkedin.com/in/your-name.',
};

const AD = s => s.replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 0x6F0));
const snippet = s => { const t = String(s).replace(/\s+/g, ' ').trim(); return t.length > 90 ? t.slice(0, 87) + '...' : t; };
const issue = (id, cat, level, key, weight, extra = {}) => ({ id, cat, level, key, fix: `${key}.fix`, weight, ...extra });

// ---------- dates ----------
const MONTH_NO = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
  'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'مايو': 5, 'يونيو': 6, 'يوليو': 7, 'أغسطس': 8, 'اغسطس': 8,
  'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12 };
const MON = String.raw`(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\.?`;
const TOK = String.raw`(?:${MON}\s*(?:19|20)\d{2}|(?:0?[1-9]|1[0-2])[/.](?:19|20)\d{2}|(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])(?!\d)|(?:19|20)\d{2})`;
const NOW = String.raw`(?:present|current|now|today|ongoing|حتى\s+ال[آا]ن|ال[آا]ن|حاليا|حالياً)`;
const RANGE = new RegExp(String.raw`(${TOK})\s*(?:-|–|—|to|until|إلى|الى|حتى(?!\s+ال[آا]ن))\s*(${TOK}|${NOW})`, 'i');
const NOW_RE = new RegExp('^' + NOW + '$', 'i');
const MON_YEAR = new RegExp('^(' + MON + ')\\s*((?:19|20)\\d{2})$', 'i');

function toMonths(tok) {
  const t = AD(tok).trim();
  if (NOW_RE.test(t)) return Infinity;
  let m = t.match(MON_YEAR);
  if (m) { const k = m[1].replace(/\.$/, ''); return +m[2] * 12 + (MONTH_NO[k.toLowerCase().slice(0, 3)] || MONTH_NO[k] || 6); }
  if ((m = t.match(/^(\d{1,2})[/.](\d{4})$/))) return +m[2] * 12 + +m[1];
  if ((m = t.match(/^(\d{4})[-/.](\d{1,2})$/))) return +m[1] * 12 + +m[2];
  if ((m = t.match(/^(\d{4})$/))) return +m[1] * 12 + 6;
  return NaN;
}
/** {start, end, raw} in months (end = Infinity for "Present"), or null. Exported for tests. */
export function parseRange(text) {
  const m = AD(text).match(RANGE);
  if (!m) return null;
  const start = toMonths(m[1]), end = toMonths(m[2]);
  return Number.isFinite(start) && (Number.isFinite(end) || end === Infinity) && end >= start ? { start, end, raw: m[0] } : null;
}

const leftX = l => (l.rtl ? -(l.right ?? l.x) : l.x); // right-to-left lines line up on the right
const YEAR = /(?:19|20)\d{2}/;

/** Lines of each Experience-type section, ended by the next heading or by a short undated line at the
 * heading's own indent (a heading the vocabulary does not know, such as "Projects & Case Competitions"). */
function expSections(lines) {
  const out = [];
  let cur = null;
  for (const line of lines) {
    if (line.rotated) continue;
    const h = detectHeading(line.text);
    if (h) { cur = h === 'exp' ? { hx: leftX(line), lines: [] } : null; if (cur) out.push(cur); continue; }
    if (!cur) continue;
    // Only where the section's content is indented: otherwise entry titles sit at the heading's indent too.
    if (cur.lines.length && leftX(cur.lines[0]) > cur.hx + 2 && !line.bullet && Math.abs(leftX(line) - cur.hx) <= 2 &&
        !YEAR.test(AD(line.text)) && line.text.trim().split(/\s+/).length <= 6) { cur = null; continue; }
    cur.lines.push(line);
  }
  return out;
}

/** Entries (a line with a date range, then its bullets) of each Experience section. */
function entries(sections, glyphs) {
  return sections.map(sec => {
    const list = [];
    for (const line of sec.lines) {
      const range = !line.bullet && parseRange(line.text);
      if (range) { list.push({ range, bullets: [] }); continue; }
      const e = list[list.length - 1];
      // A bullet: a glyph line or, when bullets are drawn as shapes (browser PDFs), a capitalised line of 4+ words.
      if (e && (line.bullet || (!glyphs && /^[A-Z]/.test(line.text.trim()) && line.text.trim().split(/\s+/).length >= 4))) e.bullets.push(line.text);
    }
    return list;
  });
}

// ---------- tense ----------
const IRREGULAR_PAST = new Set(('led built ran grew won wrote made took gave held kept brought taught sold cut set drove began ' +
  'spoke oversaw drew rebuilt troubleshot found').split(' '));
function tenseOf(word) {
  if (!word) return null;
  if (IRREGULAR_PAST.has(word) || (/^[a-z]{3,}ed$/.test(word) && !NOT_VERBS.has(word))) return 'past';
  if (/^[a-z]{3,}s$/.test(word) && !/(?:ss|us|is)$/.test(word)) {
    const stems = [word.slice(0, -1), word.slice(0, -2), word.endsWith('ies') ? word.slice(0, -3) + 'y' : ''];
    if (stems.some(s => s && ACTION_VERBS.has(s))) return 'present';
  }
  return ACTION_VERBS.has(word) && !word.endsWith('ed') ? 'present' : null;
}
const firstWord = b => (b.replace(/^[^A-Za-z]+/, '').split(/\s+/)[0] || '').toLowerCase().replace(/[^a-z]/g, '');

// ---------- the checks ----------
/** @param {object} doc @returns {object[]} only the checks that found something */
export function structureIssues(doc) {
  const lines = doc.lines || [];
  const text = doc.text || '';
  const out = [];
  const letters = (text.match(/\p{L}/gu) || []).length;
  const arabic = letters > 20 && (text.match(/[؀-ۿ]/g) || []).length / letters > 0.4;
  const sections = expSections(lines);
  const ents = entries(sections, lines.some(l => l.bullet));

  // Newest first: a lower entry that both started AND ended later than the one above it (overlapping
  // and ongoing roles never count).
  const order = [];
  for (const list of ents) {
    for (let i = 1; i < list.length; i += 1) {
      const a = list[i - 1].range, b = list[i].range;
      if (b.start > a.start && b.end > a.end) order.push(`${a.raw.trim()} → ${b.raw.trim()}`);
    }
  }
  if (order.length) out.push(issue('chrono-order', 'content', 'info', 's.chrono', 0, { examples: order.slice(0, 3) }));

  // Tense: roles that have ended, English only. Mixed means 2+ past AND 2+ present openings.
  if (!arabic && !otherLanguage(text)) {
    const past = [], now = [];
    for (const list of ents) for (const e of list) {
      if (e.range.end === Infinity) continue; // the current role may use the present tense
      for (const b of e.bullets) { const t = tenseOf(firstWord(b)); if (t === 'past') past.push(b); else if (t) now.push(b); }
    }
    if (past.length >= 2 && now.length >= 2) out.push(issue('tense', 'content', 'info', 's.tense', 0, { examples: now.slice(0, 3).map(snippet) }));
  }

  // Undated entries: only where indentation tells entries apart (headers at the section's left edge,
  // details indented). Wrapped sentence ends, lower-case starts and short all-caps OCR noise are not headers.
  let groups = 0;
  const undated = [];
  for (const sec of sections) {
    if (!sec.lines.length) continue;
    const minX = Math.min(...sec.lines.map(leftX));
    const head = l => {
      const t = l.text.trim();
      return !l.bullet && !/^[a-z]/.test(t) && !/[.;,]$/.test(t) && !/^[A-Z\s]{1,20}$/.test(t) && (leftX(l) <= minX + 2 || !!parseRange(t));
    };
    if (sec.lines.every(head)) continue;
    let block = [], inBody = false;
    const flush = () => {
      if (!block.length) return;
      groups += 1;
      if (!block.some(l => YEAR.test(AD(l.text)))) undated.push(block.map(l => l.text.trim()).join(' / '));
      block = [];
    };
    for (const l of sec.lines) {
      if (head(l)) { if (inBody) { flush(); inBody = false; } block.push(l); } else inBody = true;
    }
    if (inBody) flush();
  }
  if (undated.length && groups >= 2) {
    out.push(issue('entry-dates', 'content', 'info', 's.dates', 0, { vars: { n: undated.length, of: groups }, examples: undated.slice(0, 3).map(snippet) }));
  }

  // Letter-spaced words: 5+ single capitals (or 6+ single small letters) in a row, not on sideways lines.
  const spaced = lines.filter(l => !l.rotated && (/(?:^|\s)(?:\p{Lu}\s){4,}\p{Lu}(?:\s|$)/u.test(l.text) || /(?:^|\s)(?:\p{Ll}\s){5,}\p{Ll}(?:\s|$)/u.test(l.text)));
  if (spaced.length) out.push(issue('spaced-letters', 'parse', 'warn', 's.spaced', 3, { examples: spaced.slice(0, 3).map(l => snippet(l.text)) }));

  const rotated = lines.filter(l => l.rotated && (l.text.match(/\p{L}/gu) || []).length >= 4);
  if (rotated.length) out.push(issue('rotated-text', 'parse', 'info', 's.rotated', 0, { examples: rotated.slice(0, 3).map(l => snippet(l.text)) }));

  // A box beside running text: 2+ consecutive lines that split at the same x after a wide gap, with
  // 4+ words on the left and something other than a date or place on the right.
  const W = doc.width || 612;
  const DATEISH = /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\b|\b(?:19|20)\d{2}\b|\b(?:present|remote|expected)\b/i;
  const split = lines.map(l => {
    if (l.rtl || l.rotated) return null;
    const items = [...(l.items || [])].sort((a, b) => a.x - b.x);
    for (let i = 1; i < items.length; i += 1) {
      const gap = items[i].x - (items[i - 1].x + items[i - 1].w);
      if (gap < 0.04 * W || items[i].x < 0.35 * W) continue;
      const left = items.slice(0, i).map(t => t.text).join(' ').trim();
      const right = items.slice(i).map(t => t.text).join(' ').trim();
      if (left.split(/\s+/).length >= 4 && !DATEISH.test(right)) return { line: l, rx: items[i].x };
    }
    return null;
  });
  const merged = [];
  for (let i = 1; i < split.length; i += 1) {
    const a = split[i - 1], b = split[i];
    if (a && b && a.line.page === b.line.page && Math.abs(a.rx - b.rx) <= 3) merged.push(snippet(b.line.text));
  }
  if (merged.length) out.push(issue('side-box', 'parse', 'warn', 's.sidebox', 4, { examples: merged.slice(0, 3) }));

  // Light grey text: 30%+ of the checked letters below 3:1 against their background (set by hidden.js).
  let checked = 0, low = 0;
  const lowEx = [];
  for (const l of lines) for (const it of l.items || []) {
    if (typeof it.contrast !== 'number') continue;
    const n = (it.text.match(/\p{L}/gu) || []).length;
    checked += n;
    if (it.contrast < 3) { low += n; if (lowEx.length < 3 && it.text.trim().length > 3) lowEx.push(snippet(it.text)); }
  }
  if (checked >= 200 && low / checked >= 0.3) {
    out.push(issue('low-contrast', 'parse', 'info', 's.contrast', 0, { vars: { pct: Math.round(100 * low / checked) }, examples: lowEx }));
  }

  // A profile link (linkedin.com/in/x, github.com/x, ...) whose address is not in the visible text.
  const flat = text.toLowerCase().replace(/\s+/g, '');
  const hidden = (doc.links || []).filter(u => /^https?:\/\/(?:[a-z]+\.)?(?:linkedin\.com\/in\/[^/?#]+|(?:github\.com|gitlab\.com|behance\.net|dribbble\.com)\/[^/?#]+)\/?(?:[?#].*)?$/i.test(u))
    .filter(u => !flat.includes(u.replace(/^https?:\/\/(?:www\.)?/i, '').replace(/[?#].*$/, '').replace(/\/$/, '').toLowerCase()));
  if (hidden.length) out.push(issue('contact-link-word', 'contact', 'info', 's.link', 0, { examples: [...new Set(hidden)].slice(0, 3) }));
  return out;
}
