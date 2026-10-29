/** Extract searchable text and basic structure from a PDF in the browser.
 * Drafted by Codex from a written spec; reviewed and extended with streamText. */

/** @typedef {{text:string,x:number,y:number,w:number,h:number,font:string,size:number}} Item */
/** @typedef {{page:number,y:number,x:number,text:string,items:Item[],bullet:boolean}} Line */
/** @typedef {{pages:number,width:number,height:number,lines:Line[],text:string,fonts:string[],images:number,links:string[],fileName:string,fileSize:number,meta:{title?:string,author?:string,producer?:string,creator?:string}}} Doc */

/**
 * Extract up to ten pages. Lines are returned in visual order: page number,
 * then top-to-bottom y, then left-to-right x (pdf.js coordinates converted
 * to points from the top of each page).
 * @param {typeof import('pdfjs-dist')} pdfjs The caller-configured pdf.js module.
 * @param {File|Blob} file PDF bytes and file metadata.
 * @returns {Promise<Doc>}
 */
import { markHidden, offPageRuns } from './hidden.js';

const MAX_ITEMS_PER_PAGE = 3000;

export async function extract(pdfjs, file) {
  const data = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data, isEvalSupported: false }).promise;
  try {
    const lines = [];
    const stream = []; // text in content-stream order: roughly the order an ATS parser reads
    const fonts = new Set();
    const links = new Set();
    let images = 0;
    let hiddenChecked = true;
    const offPage = [];
    let width = 0;
    let height = 0;
    const pageLimit = Math.min(pdf.numPages, 10);

    for (let pageNumber = 1; pageNumber <= pageLimit; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1 });
      if (pageNumber === 1) ({ width, height } = viewport);
      const content = await page.getTextContent();
      const pageItems = [];
      // A real resume page has a few hundred text runs; cap crafted PDFs so the tab never freezes.
      for (const item of content.items.slice(0, MAX_ITEMS_PER_PAGE)) {
        if (typeof item.str !== 'string') continue; // marked-content items carry no text
        const str = cleanText(item.str);
        if (str) stream.push(str + (item.hasEOL ? '\n' : ''));
        if (!str || !str.trim()) {
          // Word writes some spaces as their own runs ("Mar 2022", " ", "–", " ", "Present"): keep the
          // space on the run before it, on the same baseline (left-to-right text; Arabic gaps are measured).
          const prev = pageItems[pageItems.length - 1];
          if (str && prev && !/\s$/.test(prev.text) && !hasArabic(prev.text) &&
              Math.abs(prev.baseline - (viewport.height - item.transform[5])) < 1) prev.text += ' ';
          continue;
        }
        const transform = item.transform;
        const size = Math.round(Math.abs(transform[3]) * 10) / 10;
        const h = item.height || size;
        const family = content.styles[item.fontName]?.fontFamily || '';
        const font = `${family}|${item.fontName}`;
        if (family) fonts.add(family);
        pageItems.push({
          text: str, x: transform[4], y: viewport.height - transform[5] - h,
          w: item.width, h, font, size,
          baseline: viewport.height - transform[5],
          em: Math.hypot(transform[2], transform[3]), t: transform,
        });
      }
      try {
        if (!(await markHidden(page, viewport, pageItems))) hiddenChecked = false;
      } catch {
        hiddenChecked = false; // a page pdf.js cannot draw: skip the hidden-text check, never the whole file
      }

      // Greedily place each text run on the closest compatible baseline.
      const pageLines = [];
      for (const item of pageItems) {
        const tolerance = 0.45 * item.size;
        let target = null;
        let distance = Infinity;
        for (const line of pageLines) {
          const delta = Math.abs(line.baseline - item.baseline);
          if (delta <= tolerance && delta < distance) {
            target = line;
            distance = delta;
          }
        }
        if (!target) {
          target = { page: pageNumber, baseline: item.baseline, items: [], sum: 0 };
          pageLines.push(target);
        }
        target.items.push(item);
        target.sum += item.baseline;
        target.baseline = target.sum / target.items.length;
      }

      // On a mostly Arabic page, every line with Arabic in it is a right-to-left paragraph
      // (a contact line with an email and a phone included).
      const pageRtl = isRtl(pageItems);
      for (const line of pageLines) {
        line.items.sort((a, b) => a.x - b.x);
        const rtl = isRtl(line.items) || (pageRtl && line.items.some(i => hasArabic(i.text)));
        const ordered = rtl ? logicalRtlOrder(line.items) : logicalLtrOrder(line.items);
        let text = '';
        ordered.forEach((item, i) => {
          const previous = ordered[i - 1];
          // Gap between neighbours on the page (right-to-left runs read from the right).
          const gap = previous && (previous.x > item.x ? previous.x - (item.x + item.w) : item.x - (previous.x + previous.w));
          // Never put a space before a diacritic (shadda, tanween) that some PDF makers write as its own run.
          if (previous && gap > 0.25 * item.size && !/\s$/.test(text) && !/^[\s\p{M}]/u.test(item.text)) text += ' ';
          text += item.text;
        });
        const first = ordered[0];
        const bullet = /^(?:[•●▪◦‣–—\-*·−])\s/.test(text) ||
          (first.text.length === 1 && !/[\p{L}\p{N}\s]/u.test(first.text));
        const right = Math.max(...line.items.map(part => part.x + part.w));
        lines.push({
          page: pageNumber, y: Math.min(...line.items.map(part => part.y)),
          h: Math.max(...line.items.map(part => part.h || 0)),
          x: line.items[0].x, right, rtl, text, items: line.items.map(({ baseline, t, ...part }) => part), bullet,
        });
      }

      const operators = await page.getOperatorList();
      // Skipped on crafted pages over the item cap: their visible text past the cap is not in `content` here.
      if (pdfjs.OPS.showText !== undefined && content.items.length <= MAX_ITEMS_PER_PAGE) offPage.push(...offPageRuns(operators, pdfjs.OPS, content.items));
      for (const name of ['paintImageXObject', 'paintInlineImageXObject', 'paintImageMaskXObject']) {
        const op = pdfjs.OPS[name];
        if (op !== undefined) images += operators.fnArray.filter(fn => fn === op).length;
      }
      for (const annotation of await page.getAnnotations()) {
        if (annotation.url) links.add(annotation.url);
      }
    }

    lines.sort((a, b) => a.page - b.page || a.y - b.y || a.x - b.x);
    const metadata = await pdf.getMetadata();
    const info = metadata.info || {};
    const meta = {};
    for (const [key, source] of [['title', 'Title'], ['author', 'Author'], ['producer', 'Producer'], ['creator', 'Creator']]) {
      const value = info[source];
      if (typeof value === 'string' && value) meta[key] = value;
    }
    return {
      pages: pdf.numPages, width, height, lines, text: linesToText(lines), streamText: stream.join(''),
      fonts: [...fonts].sort(), images, links: [...links], hiddenChecked, offPage,
      fileName: file.name || '', fileSize: file.size, meta,
    };
  } finally {
    await pdf.destroy();
  }
}

// Word exports list bullets from the Symbol/Wingdings fonts as Private Use Area characters.
// These are bullets, not icons: map them to "•". Other PUA characters (icon fonts) stay as they are.
const PUA_BULLETS = /[]/g;

/** Typographic ligatures (ﬁ, ﬂ) and Arabic presentation forms (the joined letter shapes some
 * PDF makers write) become plain letters, so words read as words. */
export function cleanText(s) {
  let t = s.replace(PUA_BULLETS, '•');
  if (/[ﬀ-﷿ﹰ-﻿]/.test(t)) {
    // Some fonts map Arabic yeh, heh and kaf shapes to their Persian code points (ی ھ ک): use the Arabic letters.
    t = t.normalize('NFKC').replace(/ی/g, 'ي').replace(/ھ/g, 'ه').replace(/ک/g, 'ك');
  }
  return t;
}

const ARABIC = /[؀-ۿݐ-ݿࢠ-ࣿ]/g; // global: used with match() only
const LATIN_OR_DIGIT = /[A-Za-z0-9]/g;

/** A line is right-to-left when it has more Arabic letters than Latin letters and digits. */
export function isRtl(items) {
  const text = items.map(i => i.text).join('');
  return (text.match(ARABIC) || []).length > (text.match(LATIN_OR_DIGIT) || []).length;
}

/** Items of a right-to-left line, sorted by x, put into reading order: right to left, with runs of
 * left-to-right text (emails, numbers, English words) kept in their own left-to-right order. */
export function logicalRtlOrder(itemsByX) {
  const rev = [...itemsByX].reverse();
  const out = [];
  for (let i = 0; i < rev.length;) {
    if (!ltrStrong(rev[i].text)) { out.push(rev[i]); i += 1; continue; }
    // Collect a left-to-right run; spaces and punctuation inside it belong to it.
    let j = i;
    while (j < rev.length && !hasArabic(rev[j].text)) j += 1;
    let end = j;
    while (end > i && !ltrStrong(rev[end - 1].text)) end -= 1; // trailing neutrals stay outside
    out.push(...rev.slice(i, end).reverse(), ...rev.slice(end, j));
    i = j;
  }
  return out;
}
const ltrStrong = s => /[A-Za-z0-9@]/.test(s) && !hasArabic(s);

/** Items of a left-to-right line, sorted by x: an Arabic name or phrase inside it is written right to
 * left on the page, so reverse each Arabic run (spaces between Arabic words belong to the run). */
export function logicalLtrOrder(itemsByX) {
  const out = [];
  for (let i = 0; i < itemsByX.length;) {
    if (!hasArabic(itemsByX[i].text)) { out.push(itemsByX[i]); i += 1; continue; }
    let j = i;
    while (j < itemsByX.length && !ltrStrong(itemsByX[j].text)) j += 1;
    let end = j;
    while (end > i && !hasArabic(itemsByX[end - 1].text)) end -= 1; // trailing neutrals stay outside
    out.push(...itemsByX.slice(i, end).reverse(), ...itemsByX.slice(end, j));
    i = j;
  }
  return out;
}
const hasArabic = s => /[؀-ۿݐ-ݿࢠ-ࣿ]/.test(s);

/** Join extracted line text in document visual order. @param {Line[]} lines */
export function linesToText(lines) {
  return lines.map(line => line.text).join('\n');
}
