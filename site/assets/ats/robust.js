/** File-level checks for unusual PDFs: security restrictions, portfolios, text in form fields or comments,
 * very long files and text that does not read as a resume. This module is pure. */

export const I18N_EN = {
  'x.secured': 'This PDF has security restrictions (copying or printing is blocked). Some ATS cannot read secured files.',
  'x.secured.fix': 'Export it again without restrictions or a password (for example Print > Save as PDF).',
  'x.secured-ok': 'No security restrictions.',
  'x.portfolio': 'This PDF is a portfolio: your resume ({name}) is attached inside it. An ATS reads only the cover page.',
  'x.portfolio.fix': 'Upload the attached resume PDF itself.',
  'x.form-text': 'Your text is in fillable form fields or comments, which most ATS skip.',
  'x.form-text.fix': 'Flatten the PDF: open it and use Print > Save as PDF, then check the new file.',
  'x.pages-capped': 'Only the first 10 pages were checked.',
  'x.not-resume': 'This text does not read like a resume: no real words, email or phone number were found.',
  'x.not-resume.fix': 'Check that you chose the right file, and export your resume again as a text PDF.',
};

export const MAX_PAGES = 10;
const EMAIL = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/;
const PHONE = /(?:\+|\b)[\d٠-٩][\d٠-٩ ()./-]{7,}[\d٠-٩]/;

const issue = (id, level, key, weight, vars = {}, cat = 'parse') => ({ id, cat, level, key, weight, vars });

/** @param {object} doc Doc from extract(). @returns {object[]} issues */
export function robustIssues(doc) {
  const out = [];
  const text = doc.text || '';
  const words = text.match(/[\p{L}\p{N}]+/gu) || [];
  const letters = (text.match(/\p{L}/gu) || []).length;
  const fewText = words.length < 80 && letters < 400; // same threshold as the selectable-text check

  out.push(issue('secured', doc.secured ? 'warn' : 'ok', doc.secured ? 'x.secured' : 'x.secured-ok', 3));
  const attached = (doc.attachments || []).filter(n => /\.pdf$/i.test(n));
  // Sorted just above "very little selectable text" (weight 10): this is the reason for it.
  if (fewText && attached.length) out.push(issue('portfolio', 'fail', 'x.portfolio', 10.5, { name: attached[0].slice(0, 60) }));
  else if (fewText && (doc.formWords || 0) + (doc.noteWords || 0) >= 10) out.push(issue('form-text', 'fail', 'x.form-text', 10.5));
  if ((doc.pages || 0) > MAX_PAGES) out.push(issue('pages-capped', 'info', 'x.pages-capped', 0, { n: MAX_PAGES }));
  // Enough text to read, yet almost no word has three letters and there is no contact detail:
  // a page of single letters, symbols or numbers, not a resume.
  if (!fewText && words.length >= 80 && !EMAIL.test(text) && !PHONE.test(text)) {
    const real = words.filter(w => (w.match(/\p{L}/gu) || []).length >= 3).length;
    if (real / words.length < 0.3) out.push(issue('not-resume', 'fail', 'x.not-resume', 10));
  }
  return out;
}
