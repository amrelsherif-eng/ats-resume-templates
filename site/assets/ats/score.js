/** Scoring: 100 minus weighted penalties per category, then a weighted overall score with caps.
 * Pure: the report UI and the tests use the same function. */
import { PAGE_NORMS } from './layout.js';

export const CATS = [
  { id: 'parse', weight: 0.4 },
  { id: 'content', weight: 0.35 },
  { id: 'contact', weight: 0.25 }
];

const failed = (issues, ids) => issues.some(i => ids.includes(i.id) && i.level === 'fail');

/**
 * @param {{id:string,cat:string,level:string,weight:number}[]} issues
 * @param {{pages?:number}} [doc]
 * @param {string} [level] experience level (page norms)
 * @returns {{per: Record<string, number>, overall: number}}
 */
export function score(issues, doc = {}, level = 'student') {
  const per = {};
  for (const c of CATS) {
    const list = issues.filter(i => i.cat === c.id);
    const max = list.reduce((s, i) => s + i.weight, 0) || 1;
    const lost = list.reduce((s, i) => s + i.weight * (i.level === 'fail' ? 1 : i.level === 'warn' ? 0.5 : 0), 0);
    per[c.id] = Math.round(100 * (1 - lost / max));
  }
  let overall = Math.round(CATS.reduce((s, c) => s + per[c.id] * c.weight, 0));
  // Clean formatting cannot make weak content look "excellent": keep the total near the content score.
  if (per.content < 70) overall = Math.min(overall, per.content + 10);
  // A layout that can scramble the reading order (columns, out-of-order blocks) is never "Excellent".
  if (issues.some(i => (i.id === 'columns' || i.id === 'reading-order' || i.id === 'side-box') && i.level !== 'ok')) overall = Math.min(overall, 84);
  // Hidden text or instructions aimed at AI screeners can get an application rejected outright.
  if (failed(issues, ['hidden-text', 'prompt-injection'])) overall = Math.min(overall, 40);
  // Text that is not a resume (a page of single letters or symbols) is not "good" either.
  if (failed(issues, ['not-resume'])) overall = Math.min(overall, 40);
  // Far longer than any norm (a 60- or 200-page file): not a resume an ATS will treat as one.
  const norm = PAGE_NORMS[level] || PAGE_NORMS.student;
  if ((doc.pages || 0) > 2 * norm.warn) overall = Math.min(overall, 60);
  // A resume an ATS cannot read at all should never look "good".
  if (failed(issues, ['selectable-text'])) overall = Math.min(overall, 25);
  return { per, overall };
}

export function band(n) { return n >= 85 ? 'great' : n >= 70 ? 'good' : n >= 50 ? 'fair' : 'poor'; }
