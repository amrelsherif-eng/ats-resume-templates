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
        if (item.str) stream.push(item.str + (item.hasEOL ? '\n' : ''));
        if (!item.str || !item.str.trim()) continue;
        const transform = item.transform;
        const size = Math.round(Math.abs(transform[3]) * 10) / 10;
        const h = item.height || size;
        const family = content.styles[item.fontName]?.fontFamily || '';
        const font = `${family}|${item.fontName}`;
        if (family) fonts.add(family);
        pageItems.push({
          text: item.str, x: transform[4], y: viewport.height - transform[5] - h,
          w: item.width, h, font, size,
          baseline: viewport.height - transform[5],
        });
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

      for (const line of pageLines) {
        line.items.sort((a, b) => a.x - b.x);
        const first = line.items[0];
        let text = '';
        for (const item of line.items) {
          const previous = line.items[line.items.indexOf(item) - 1];
          if (previous && item.x - (previous.x + previous.w) > 0.25 * item.size &&
              !/\s$/.test(text) && !/^\s/.test(item.text)) text += ' ';
          text += item.text;
        }
        const bullet = /^(?:[•●▪◦‣–—\-*·−])\s/.test(text) ||
          (first.text.length === 1 && !/[\p{L}\p{N}\s]/u.test(first.text));
        lines.push({
          page: pageNumber, y: Math.min(...line.items.map(part => part.y)),
          x: first.x, text, items: line.items.map(({ baseline, ...part }) => part), bullet,
        });
      }

      const operators = await page.getOperatorList();
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
      fonts: [...fonts].sort(), images, links: [...links],
      fileName: file.name || '', fileSize: file.size, meta,
    };
  } finally {
    await pdf.destroy();
  }
}

/** Join extracted line text in document visual order. @param {Line[]} lines */
export function linesToText(lines) {
  return lines.map(line => line.text).join('\n');
}
