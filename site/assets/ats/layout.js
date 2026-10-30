/** Layout and extraction checks for the ATS Doc model. This module is pure.
 * Drafted by Codex from a written spec; reviewed (separate ok messages, stream-order check). */
const fix = {
  'l.pages-2': 'Consider fitting the resume to one page when your experience allows.',
  'l.pages-many': 'Remove less relevant details and keep the resume concise.',
  'l.no-text': 'Use a text based PDF; scanned pages and outlined text cannot be read reliably.',
  'l.columns': 'Use a single column so resume text is read in the intended order.',
  'l.icons': 'Replace decorative icons with plain text labels.',
  'l.garbled': 'Export the PDF again with embedded fonts and selectable text.',
  'l.images': 'Keep important information as text; photos are not needed for most roles.',
  'l.contact-edge': 'Move your email and phone into the main page content.',
  'l.fonts': 'Use no more than four font families for a consistent resume.',
  'l.table': 'Replace table-like rows with simple text and clear section headings.',
  'l.order': 'Place your name and contact details at the beginning of the document.',
  'l.filename': 'Use a clear file name such as FirstName-LastName-CV.pdf.',
  'l.size': 'Compress the PDF while keeping text clear.'
};

export const I18N_EN = {
  'l.pages-ok': '{n} page(s): right length for your experience level.',
  'l.pages-2': '{n} pages: longer than the usual {max} for your experience level.',
  'l.pages-many': '{n} pages: much longer than the usual {max} for your experience level.',
  'l.text-ok': 'Selectable text found ({n} words).', 'l.no-text': 'Very little selectable text was found.',
  'l.columns': 'This page may use multiple columns.', 'l.icons': 'Decorative symbols found ({n}).',
  'l.garbled': 'Some extracted text appears garbled.', 'l.images': 'Images found ({n}).',
  'l.contact-edge': 'Contact details appear only in a page header or footer.',
  'l.fonts': 'Many font families found ({n}).', 'l.table': 'Table-like rows may disrupt text reading.',
  'l.order': 'The largest text may appear late in the document.',
  'l.filename': 'This file name is generic.', 'l.filename-ok': 'Your file name is descriptive.',
  'l.size': 'This PDF is large ({mb} MB).', 'l.size-ok': 'Your PDF file size is reasonable.',
  'l.columns-ok': 'Single-column layout: text reads in the right order.',
  'l.icons-ok': 'No icon fonts or emoji that an ATS would drop.',
  'l.garbled-ok': 'Text extracts as real characters.',
  'l.images-ok': 'No images: everything is real text.',
  'l.contact-edge-ok': 'Contact details are in the page body.',
  'l.fonts-ok': 'Consistent fonts.',
  'l.table-ok': 'No table-style rows.',
  'l.order-ok': 'Your name is read first, as it should be.',
  'l.pages-2.fix': fix['l.pages-2'], 'l.pages-many.fix': fix['l.pages-many'],
  'l.no-text.fix': fix['l.no-text'], 'l.columns.fix': fix['l.columns'], 'l.icons.fix': fix['l.icons'],
  'l.garbled.fix': fix['l.garbled'], 'l.images.fix': fix['l.images'],
  'l.contact-edge.fix': fix['l.contact-edge'], 'l.fonts.fix': fix['l.fonts'],
  'l.table.fix': fix['l.table'], 'l.order.fix': fix['l.order'], 'l.filename.fix': fix['l.filename'],
  'l.size.fix': fix['l.size']
};

const words = s => (s.match(/[\p{L}\p{N}]+(?:['’][\p{L}\p{N}]+)*/gu) || []).length;
/** Arabic-Indic digits as ASCII, so "٠١٠٠..." reads as a phone number or a year. */
const asciiDigits = s => s.replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x660)).replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 0x6F0));
/** Right-to-left lines start at the right margin: mirror them so the column checks read them like left-to-right lines. */
const mirror = (line, W) => !line.rtl ? line : {
  ...line, x: W - (line.right ?? line.x), items: (line.items || []).map(it => ({ ...it, x: W - it.x - it.w }))
};
/** Arabic in a right-to-left document lines up on the right; Arabic typed into a left-to-right document
 * (Word or DesignCraft without RTL paragraphs) lines up on the left. Mirror only right-aligned Arabic. */
function rtlRightAligned(lines) {
  const rtl = lines.filter(l => l.rtl && Number.isFinite(l.right) && Number.isFinite(l.x));
  if (rtl.length < 3) return true;
  const maxRight = Math.max(...rtl.map(l => l.right)), minX = Math.min(...rtl.map(l => l.x));
  const onRight = rtl.filter(l => maxRight - l.right <= 3).length, onLeft = rtl.filter(l => l.x - minX <= 3).length;
  return onRight >= onLeft;
}
// Arabic dates (months, "حتى الآن") and short Arabic place names on the far side of a line are fine.
const AR_DATE = /(?:يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر|الآن|حاليا|حالياً)/;
function arabicDateOrPlace(s) {
  const t = asciiDigits(s).trim();
  if (!/[؀-ۿ]/.test(t)) return false;
  return AR_DATE.test(t) || /(?:19|20)\d{2}/.test(t) || t.split(/\s+/).length <= 3;
}
const snippet = s => s.replace(/\s+/g, ' ').trim().slice(0, 90);
const issue = (id, level, key, weight, vars, examples) => ({
  id, cat: 'parse', level, key, ...(vars && { vars }), ...(fix[key] && level !== 'ok' && { fix: `${key}.fix` }),
  ...(examples?.length && { examples: examples.slice(0, 3) }), weight
});

/**
 * Page-count norms by experience level (career-center and recruiter guidance, 2026):
 * students and juniors: 1 page; 3-9 years: 1-2; 10+ years: 2 is normal; academic CVs: no limit.
 * @type {Record<string, {ok:number, warn:number}>} ok = max pages that pass, warn = max pages that only warn
 */
export const PAGE_NORMS = {
  student: { ok: 1, warn: 2 }, junior: { ok: 1, warn: 2 }, mid: { ok: 2, warn: 3 },
  senior: { ok: 2, warn: 3 }, academic: { ok: Infinity, warn: Infinity }
};

/** Return one scored issue for each layout check; never reads files or browser state.
 * @param {object} doc
 * @param {{level?: keyof PAGE_NORMS}} [opts] */
export function layoutIssues(doc, opts = {}) {
  const lines = doc.lines || [], first = lines.filter(l => l.page === 1), text = doc.text || '';
  const out = [];
  const norm = PAGE_NORMS[opts.level] || PAGE_NORMS.student;
  const pagesLevel = doc.pages <= norm.ok ? 'ok' : doc.pages <= norm.warn ? 'warn' : 'fail';
  out.push(issue('pages', pagesLevel,
    pagesLevel === 'ok' ? 'l.pages-ok' : pagesLevel === 'warn' ? 'l.pages-2' : 'l.pages-many', 8,
    { n: doc.pages, max: norm.ok }));
  const wc = words(text);
  // Some PDF makers write Arabic without space characters, so the words run together: count letters too.
  const noText = wc < 80 && (text.match(/\p{L}/gu) || []).length < 400;
  out.push(issue('selectable-text', noText ? 'fail' : 'ok', noText ? 'l.no-text' : 'l.text-ok', 10, { n: wc }));

  // Columns: the extractor merges side-by-side text into one line, so look for a wide gap inside
  // a line (or a line that starts mid-page) whose right part is real content, not a date or place.
  const mirrorRtl = rtlRightAligned(first);
  const body = first.filter(l => l.text?.trim()).map(l => (mirrorRtl ? mirror(l, doc.width || 612) : l));
  const W = doc.width || 612;
  const dateOrPlace = s => arabicDateOrPlace(s) || /\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|Present|Remote|Expected)\b|\b(?:19|20)\d{2}\b|\b(?:0?[1-9]|1[0-2])[/.](?:\d{2}|(?:19|20)\d{2})\b|\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])\b/i.test(s) ||
    (s.length < 32 && /^[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*(?:,\s*[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)?$/.test(s));
  const overlaps = body.filter(line => {
    const items = [...(line.items || [])].sort((a, b) => a.x - b.x);
    for (let i = 1; i < items.length; i += 1) {
      const gap = items[i].x - (items[i - 1].x + items[i - 1].w);
      if (gap < 0.08 * W || items[i].x < 0.25 * W) continue;
      const rightText = items.slice(i).map(it => it.text).join(' ').trim();
      if (!dateOrPlace(rightText)) return true;
    }
    // A content line that starts mid-page while other lines start at the left margin.
    const last = items[items.length - 1] || { x: line.x, w: 0 };
    const centered = Math.abs((line.x + last.x + last.w) / 2 - W / 2) < 0.06 * W; // centered headers are fine
    return !centered && line.x > 0.3 * W && !dateOrPlace(line.text.trim()) && line.text.trim().split(/\s+/).length >= 4 &&
      body.some(l => l !== line && l.x < 0.2 * W);
  });
  const multi = body.length > 0 && overlaps.length / body.length >= .2;
  out.push(issue('columns', multi ? 'warn' : 'ok', multi ? 'l.columns' : 'l.columns-ok', 8, undefined, overlaps.map(l => snippet(l.text))));

  const symbolRe = /[\uE000-\uF8FF\u2600-\u27BF]|[\u{1F300}-\u{1FAFF}]/gu;
  // A symbol used as a line's bullet (\u2713 \u27A4 \u2756) is a bullet, not an icon that hides information.
  const symText = lines.map(l => (l.bullet ? l.text.replace(/^\s*\S/u, '') : l.text)).join('\n');
  const symMatches = [...symText.matchAll(symbolRe)];
  out.push(issue('icons', symMatches.length ? 'warn' : 'ok', symMatches.length ? 'l.icons' : 'l.icons-ok', 5, { n: symMatches.length }, symMatches.slice(0, 3).map(m => snippet(symText.slice(Math.max(0, m.index - 25), m.index + 35)))));

  // Runs of 4+ symbols look like broken text, except divider lines (\u2500\u2500\u2500\u2500 ---- ....) and "://".
  const symbolRuns = (text.match(/(?:[^\p{L}\p{N}\s]){4,}/gu) || [])
    .filter(m => !/^[-_=.\u00B7\u2022*~\u2500\u2501\u2550\u2014\u2013|]+$/u.test(m) && !/^[^:]*:\/\/[^:]*$/u.test(m));
  // A font with no Unicode map (subset font, no ToUnicode) gives shifted letters with no spaces:
  // "6DOPD$GHO" for "Salma Adel". Real Latin-script text has about 12-20% spaces and few 20+ letter runs.
  const latin = (text.match(/[A-Za-z]/g) || []).length;
  const arabic = (text.match(/[\u0600-\u06FF]/g) || []).length;
  const tokens = text.split(/\s+/).filter(w => /[A-Za-z]/.test(w));
  const runOn = tokens.filter(w => w.length >= 20 && !/[@/.]/.test(w)).length;
  const noUnicodeMap = latin >= 150 && latin > 2 * arabic &&
    ((text.match(/ /g) || []).length / text.length < 0.03 || runOn / tokens.length > 0.2);
  const bad = (text.match(/\(cid:/gi) || []).length + (text.match(/\uFFFD/g) || []).length + symbolRuns.length +
    (noUnicodeMap ? 4 : 0);
  out.push(issue('garbled-text', bad > 3 ? 'fail' : 'ok', bad > 3 ? 'l.garbled' : 'l.garbled-ok', 9));
  out.push(issue('images', doc.images > 0 ? 'info' : 'ok', doc.images > 0 ? 'l.images' : 'l.images-ok', 3, { n: doc.images }));

  const contact = /[\w.+-]+@[\w.-]+\.[A-Z]{2,}|(?:\+?\d[\d().\s-]{7,}\d)/i;
  const hasMain = first.some(l => contact.test(asciiDigits(l.text || '')) && l.y > doc.height * .04 && l.y + (l.h || 0) < doc.height * .96);
  const edge = !hasMain && lines.some(l => contact.test(asciiDigits(l.text || '')) && (l.y <= doc.height * .04 || l.y + (l.h || 0) >= doc.height * .96));
  out.push(issue('contact-edge', edge ? 'warn' : 'ok', edge ? 'l.contact-edge' : 'l.contact-edge-ok', 4));
  const fontCount = (doc.fonts || []).filter(Boolean).length;
  out.push(issue('fonts', fontCount > 4 ? 'info' : 'ok', fontCount > 4 ? 'l.fonts' : 'l.fonts-ok', 2, { n: fontCount }));

  const tableRows = first.filter(l => {
    const items = l.items || []; if (items.length < 3) return false;
    const sorted = [...items].sort((a, b) => a.x - b.x);
    return sorted.slice(1).filter((it, i) => it.x - (sorted[i].x + sorted[i].w) > 3 * (it.size || 10)).length >= 2;
  });
  out.push(issue('table-rows', tableRows.length >= 6 ? 'warn' : 'ok', tableRows.length >= 6 ? 'l.table' : 'l.table-ok', 4, undefined, tableRows.map(l => snippet(l.text))));

  const largest = first.reduce((best, l) => Math.max(best, ...(l.items || []).map(i => i.size || 0), 0), 0);
  const nameLine = first.find(l => (l.items || []).some(i => (i.size || 0) === largest) && largest > 0);
  // Visual order always puts the name first; the content stream shows what an ATS actually reads first.
  const stream = (doc.streamText || text).replace(/\s+/g, ' ');
  const nameText = nameLine ? nameLine.text.replace(/\s+/g, ' ').trim() : '';
  const namePos = nameText ? stream.indexOf(nameText) : 0;
  const late = !!nameLine && namePos >= stream.length * .15;
  out.push(issue('reading-order', late ? 'warn' : 'ok', late ? 'l.order' : 'l.order-ok', 6));
  const generic = /^(resume|cv|document|untitled|final|my[\W_]?cv)[\W_]*\d*\.pdf$/i.test(doc.fileName || '');
  out.push(issue('file-name', generic ? 'info' : 'ok', generic ? 'l.filename' : 'l.filename-ok', 1));
  const mb = (doc.fileSize || 0) / (1024 * 1024), large = mb > 2;
  out.push(issue('file-size', large ? 'warn' : 'ok', large ? 'l.size' : 'l.size-ok', 2, { mb: Number(mb.toFixed(1)) }));
  return out;
}
