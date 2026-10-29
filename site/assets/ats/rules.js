/**
 * @file rules.js - Content quality and structure rules for ATS resume checker v2
 * Drafted by Gemini 3.8 Flash from a written spec; reviewed and adjusted
 * (MENA locations, bullet glyphs, currency codes, fewer false positives).
 */

const HEADINGS_RE = /^(?:education|academic background|academics|experience|work experience|professional experience|employment history|work history|projects|personal projects|academic projects|key projects|skills|technical skills|core competencies|skills & expertise|certifications|certificates|licenses|certifications & licenses|summary|profile|professional summary|executive summary|leadership|leadership experience|activities|extracurricular activities|volunteer|volunteering|volunteer experience|community involvement|languages|language skills|awards|honors|interests|hobbies)$/i;

const ACTION_VERBS = new Set(
  ("accelerate accelerated achieve achieved acquire acquired adapt adapted administer administered advance advanced " +
  "advise advised align aligned allocate allocated analyze analyzed apply applied appraise appraised approve approved " +
  "arrange arranged assemble assembled assess assessed audit audited author authored automate automated balance balanced " +
  "boost boosted budget budgeted build built calculate calculated capture captured champion championed clarify clarified " +
  "coach coached collaborate collaborated collect collected compose composed conduct conducted configure configured " +
  "consolidate consolidated construct constructed consult consulted convert converted coordinate coordinated correct corrected " +
  "counsel counseled create created cultivate cultivated customize customized decrease decreased define defined delegate delegated " +
  "deliver delivered deploy deployed design designed detail detailed detect detected determine determined develop developed " +
  "devise devised diagnose diagnosed direct directed discover discovered dispatch dispatched distribute distributed document documented " +
  "draft drafted drive drove earn earned edit edited educate educated eliminate eliminated enable enabled engineer engineered " +
  "enhance enhanced ensure ensured establish established estimate estimated evaluate evaluated exceed exceeded execute executed " +
  "expand expanded expedite expedited extract extracted facilitate facilitated forecast forecasted forge forged formalize formalized " +
  "formulate formulated found founded fulfill fulfilled gain gained generate generated govern governed guide guided head headed " +
  "hire hired identify identified implement implemented improve improved increase increased initiate initiated innovate innovated " +
  "inspect inspected install installed institute instituted instruct instructed integrate integrated interpret interpreted " +
  "interview interviewed introduce introduced invent invented investigate investigated launch launched lead led leverage leveraged " +
  "maintain maintained manage managed map mapped maximize maximized measure measured mediate mediated mentor mentored merge merged " +
  "migrate migrated minimize minimized model modeled modernize modernized monitor monitored motivate motivated navigate navigated " +
  "negotiate negotiated operate operated optimize optimized orchestrate orchestrated organize organized originate originated " +
  "overhaul overhauled oversee oversaw perform performed pioneer pioneered plan planned prepare prepared present presented " +
  "prioritize prioritized produce produced program programmed project projected promote promoted propose proposed publish published " +
  "quantify quantified reconcile reconciled recruit recruited redesign redesigned reduce reduced refactor refactored refine refined " +
  "reinforce reinforced remodel remodeled reorganize reorganized replace replaced research researched resolve resolved restructure restructured " +
  "revamp revamped review reviewed revise revised scale scaled schedule scheduled screen screened secure secured select selected " +
  "simplify simplified simulate simulated spearhead spearheaded standardize standardized steer steered streamline streamlined " +
  "strengthen strengthened structure structured supervise supervised survey surveyed synthesize synthesized systematize systematized " +
  "tailor tailored target targeted test tested track tracked train trained transform transformed translate translated upgrade upgraded " +
  "validate validated verify verified yield yielded " +
  // Common resume verbs added during review (missing from the first draft).
  "add added write wrote written ship shipped profile profiled solve solved run ran set setup fix fixed publish published " +
  "clean cleaned provision provisioned match matched vouch vouched check checked compare compared merge merged save saved " +
  "teach taught tutor tutored host hosted lower lowered cut raise raised win won rank ranked place placed answer answered " +
  "load-tested benchmark benchmarked containerize containerized refactor rebuilt rebuild wire wired prototype prototyped " +
  "debug debugged troubleshoot troubleshot troubleshooted patch patched secure document handle handled process processed " +
  "file filed record recorded update updated serve served sell sold close closed collect gather gathered calibrate calibrated " +
  "solder soldered measure flash flashed port ported tune tuned simulate assemble wrote led ran grew grow travel traveled cofounded co-founded").split(" ")
);

const BUZZWORDS = [
  { name: 'hard-working', re: /\bhard[- ]working\b/i },
  { name: 'team player', re: /\bteam[- ]player\b/i },
  { name: 'detail-oriented', re: /\bdetail[- ]oriented\b/i },
  { name: 'go-getter', re: /\bgo[- ]getter\b/i },
  { name: 'synergy', re: /\bsynerg(?:y|ies)\b/i },
  { name: 'think outside the box', re: /\bthink(?:ing)?\s+outside\s+the\s+box\b/i },
  { name: 'results-driven', re: /\bresults?[- ]driven\b/i },
  { name: 'self-motivated', re: /\bself[- ]motivated\b/i },
  { name: 'passionate', re: /\bpassionate\b/i },
  { name: 'dynamic', re: /\bdynamic\b/i },
  { name: 'rockstar', re: /\brockstar\b/i },
  { name: 'ninja', re: /\bninja\b/i },
  { name: 'guru', re: /\bguru\b/i },
  { name: 'proven track record', re: /\bproven\s+track\s+record\b/i },
  { name: 'excellent communication skills', re: /\bexcellent\s+communication\s+skills\b/i },
  { name: 'fast learner', re: /\bfast[- ]learner\b/i }
];

function detectHeading(text) {
  const clean = text.trim().replace(/^[\d.\s•–—\-\*|:]+/, '').replace(/[:\-_—|]+$/, '').trim();
  if (!clean || clean.length > 35 || clean.split(/\s+/).length > 4) return null;
  if (!HEADINGS_RE.test(clean)) return null;
  const lower = clean.toLowerCase();
  if (lower.includes('education') || lower.includes('academic')) return 'edu';
  if (lower.includes('experience') || lower.includes('employment') || lower.includes('work history')) return 'exp';
  if (lower.includes('project')) return 'proj';
  if (lower.includes('skill') || lower.includes('competenc')) return 'skills';
  if (lower.includes('leadership') || lower.includes('activit') || lower.includes('volunteer') || lower.includes('community')) return 'leadership';
  if (lower.includes('education') || lower.includes('academic')) return 'edu';
  return 'other';
}

function trimEx(str) {
  const s = String(str || '').trim().replace(/\s+/g, ' ');
  return s.length > 90 ? s.slice(0, 87) + '...' : s;
}

/** Upper word counts by experience level (about 650 words fill one page, 1100 fill two). */
const WORD_LIMITS = { student: 700, junior: 750, mid: 1200, senior: 1300, academic: Infinity };

/** @param {object} doc @param {{level?: string}} [opts] */
export function contentIssues(doc, opts = {}) {
  const wordLimit = WORD_LIMITS[opts.level] || WORD_LIMITS.student;
  const issues = [];
  const lines = doc.lines || [];
  const text = doc.text || lines.map(l => l.text).join('\n');
  const links = doc.links || [];

  // Arabic language detection
  const letters = text.match(/\p{L}/gu) || [];
  const arabicLetters = text.match(/[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/g) || [];
  const isArabic = letters.length > 20 && (arabicLetters.length / letters.length > 0.4);

  // 1. Sections
  const sectionsSeen = new Set();
  for (const l of lines) {
    const h = detectHeading(l.text);
    if (h) sectionsSeen.add(h);
  }
  const missingSec = [];
  if (!sectionsSeen.has('edu')) missingSec.push('Education');
  if (!sectionsSeen.has('exp') && !sectionsSeen.has('proj')) missingSec.push('Experience');
  if (!sectionsSeen.has('skills')) missingSec.push('Skills');

  if (missingSec.length > 0) {
    issues.push({ id: 'sections', cat: 'contact', level: 'warn', key: 'r.sec-missing', vars: { list: missingSec.join(', ') }, fix: 'r.sec-missing.fix', weight: 6 });
  } else {
    const foundSec = ['Education', sectionsSeen.has('exp') ? 'Experience' : 'Projects', 'Skills'];
    issues.push({ id: 'sections', cat: 'contact', level: 'ok', key: 'r.sec-ok', vars: { list: foundSec.join(', ') }, weight: 6 });
  }

  // 2. Contact info
  const emailMatch = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  issues.push(emailMatch
    ? { id: 'contact-email', cat: 'contact', level: 'ok', key: 'r.email-ok', weight: 5 }
    : { id: 'contact-email', cat: 'contact', level: 'warn', key: 'r.email-miss', fix: 'r.email-miss.fix', weight: 5 });

  const phoneMatch = text.match(/(?:\(\+20\)|\+20)\s*1[0125](?:[\s.-]?\d){8}(?!\d)|\b01[0125](?:[\s.-]?\d){8}\b|(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b(?:\+\d{1,3}[-.\s]?)?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,5}\b/);
  issues.push(phoneMatch
    ? { id: 'contact-phone', cat: 'contact', level: 'ok', key: 'r.phone-ok', weight: 4 }
    : { id: 'contact-phone', cat: 'contact', level: 'warn', key: 'r.phone-miss', fix: 'r.phone-miss.fix', weight: 4 });

  const linkedInMatch = /linkedin\.com\/in\/[a-zA-Z0-9_-]+/i.test(text) || links.some(l => /linkedin\.com\/in\//i.test(l));
  issues.push(linkedInMatch
    ? { id: 'contact-linkedin', cat: 'contact', level: 'ok', key: 'r.linkedin-ok', weight: 3 }
    : { id: 'contact-linkedin', cat: 'contact', level: 'warn', key: 'r.linkedin-miss', fix: 'r.linkedin-miss.fix', weight: 3 });

  const topText = lines.slice(0, 15).map(l => l.text).join('\n');
  const locRe = /\b(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?),\s*(?:[A-Z]{2}\b|[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)|(?:[A-Z][a-zA-Z]+,\s*(?:USA|UK|UAE|Canada|Germany|France|India|Australia|Singapore|Netherlands|Egypt|KSA|Saudi Arabia|Qatar|Kuwait|Jordan|Oman|Bahrain|Morocco|Tunisia|Lebanon|Country))\b|\b(?:New York|San Francisco|London|Seattle|Austin|Boston|Chicago|Toronto|Vancouver|Berlin|Paris|Amsterdam|Singapore|Sydney|Melbourne|Remote|Cairo|Giza|Alexandria|Mansoura|Tanta|Zagazig|Assiut|Aswan|Luxor|Ismailia|Suez|Port Said|Damanhour|Minya|Sohag|Hurghada|6th of October|Riyadh|Jeddah|Dammam|Dubai|Abu Dhabi|Sharjah|Doha|Amman|Muscat|Manama|Casablanca|Tunis|Beirut|Egypt)\b/i;
  issues.push(locRe.test(topText)
    ? { id: 'contact-location', cat: 'contact', level: 'ok', key: 'r.location-ok', weight: 2 }
    : { id: 'contact-location', cat: 'contact', level: 'warn', key: 'r.location-miss', fix: 'r.location-miss.fix', weight: 2 });

  const portfolioMatch = /(?:github\.com|gitlab\.com|bitbucket\.org|behance\.net|dribbble\.com)\/[a-zA-Z0-9_-]+/i.test(text) || links.some(l => /(?:github|gitlab|behance|dribbble|portfolio)/i.test(l));
  issues.push(portfolioMatch
    ? { id: 'contact-portfolio', cat: 'contact', level: 'ok', key: 'r.portfolio-ok', weight: 1 }
    : { id: 'contact-portfolio', cat: 'contact', level: 'info', key: 'r.portfolio-miss', fix: 'r.portfolio-miss.fix', weight: 1 });

  // 12. Personal data check (evaluated early for Arabic fallback)
  const personalRules = [
    /\b(?:date\s+of\s+birth|d\.?o\.?b\.?|birth\s*date)\b/i,
    /\b(?:marital\s+status|civil\s+status)\b/i, // bare "single" would flag "single page"
    /\b(?:religion|religious\s+affiliation)\b/i,
    /\b(?:nationality|citizenship)\b/i,
    /\b(?:national\s+id|ssn|social\s+security|passport\s*(?:no|number)?)\b/i
  ];
  const personalEx = [];
  for (const re of personalRules) {
    for (const l of lines) {
      if (re.test(l.text)) {
        personalEx.push(l.text);
        break;
      }
    }
  }
  const personalIssue = personalEx.length > 0
    ? { id: 'personal-data', cat: 'contact', level: 'info', key: 'r.personal', fix: 'r.personal.fix', examples: personalEx.slice(0, 3).map(trimEx), weight: 2 }
    : { id: 'personal-data', cat: 'contact', level: 'ok', key: 'r.personal-ok', weight: 2 };

  if (isArabic) {
    return [
      { id: 'arabic-lang', cat: 'content', level: 'info', key: 'r.arabic', fix: 'r.arabic.fix', weight: 0 },
      ...issues,
      personalIssue
    ];
  }

  // Extract bullets for content checks
  const cleanBullet = b => b.replace(/^[\s•–—\-\*\u2022\u2212\u25E6\u2023\u25AA\u25BA\u27A4\u2713]+/, '').replace(/^\d+[.)]\s*/, '').trim();
  const hasGlyphs = lines.some(l => l.bullet);
  let bullets = [];
  const achievementBullets = [];
  const dateToken = String.raw`(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?\.?)\s+(?:19|20)\d{2}|\d{1,2}[/.]\d{2,4}|(?:19|20)\d{2}[-/.]\d{1,2}`;
  const dateRange = new RegExp(String.raw`\b${dateToken}\b\s*(?:-|–|—|to)\s*(?:\b${dateToken}\b|present|current|now)\b`, 'i');
  let section = 'other';
  for (const line of lines) {
    const heading = detectHeading(line.text);
    if (heading) {
      section = heading;
      continue;
    }
    const achievementSection = section === 'exp' || section === 'proj' || section === 'leadership';
    const clean = cleanBullet(line.text);
    if (hasGlyphs) {
      if (!line.bullet || !clean) continue;
      if (!/^(?:relevant\s+)?(?:coursework|courses|skills|tools|technologies|languages)\s*:/i.test(clean)) bullets.push(clean);
      if (achievementSection) achievementBullets.push(clean);
    } else if (achievementSection) {
      const wordCount = line.text.trim().split(/\s+/).filter(Boolean).length;
      const metadata = dateRange.test(line.text) || (line.text.match(/ \| /g) || []).length >= 2;
      if (wordCount >= 6 && !metadata && clean) {
        bullets.push(clean);
        achievementBullets.push(clean);
      }
    }
  }
  // Safety net: if no Experience/Projects heading was recognised (e.g. "Internships", "Research"),
  // judge every bulleted line rather than letting weak content pass unchecked.
  if (!achievementBullets.length && bullets.length) achievementBullets.push(...bullets);

  // 3. Action verbs
  let verbCount = 0;
  const nonVerbEx = [];
  const stripLabel = b => b.replace(/^(?:[\p{L}\p{N}][\p{L}\p{N}+.#&/-]*(?:\s+[\p{L}\p{N}][\p{L}\p{N}+.#&/-]*){0,3}):\s*/u, '');
  const openingText = b => stripLabel(b).trim();
  const normalizeVerb = word => word
    .replace(/isation$/, 'ization').replace(/ising$/, 'izing').replace(/ised$/, 'ized')
    .replace(/ysing$/, 'yzing').replace(/ysed$/, 'yzed').replace(/lling$/, 'ling').replace(/lled$/, 'led');
  const openingWord = b => normalizeVerb((openingText(b).replace(/^[^a-zA-Z]+/, '').split(/\s+/)[0] || '').toLowerCase().replace(/[^a-z]/g, ''));
  const verbBullets = achievementBullets.filter(b => !/^[+−-]?(?:\d|%)/.test(openingText(b)));
  for (const b of verbBullets) {
    const first = openingWord(b);
    if (ACTION_VERBS.has(first)) {
      verbCount++;
    } else {
      nonVerbEx.push(b);
    }
  }
  const verbPct = verbBullets.length ? Math.round((verbCount / verbBullets.length) * 100) : 100;
  issues.push(verbPct < 60
    ? { id: 'action-verbs', cat: 'content', level: verbPct < 25 && verbBullets.length >= 3 ? 'fail' : 'warn', key: 'r.verbs', vars: { pct: verbPct }, fix: 'r.verbs.fix', examples: nonVerbEx.slice(0, 3).map(trimEx), weight: 7 }
    : { id: 'action-verbs', cat: 'content', level: 'ok', key: 'r.verbs-ok', vars: { pct: verbPct }, weight: 7 });

  // 4. Weak openers
  const weakRe = /^(?:responsible for|worked on|helped(?:\s+with)?|assisted(?:\s+with)?|participated in|involved in|duties included|tasked with)\b/i;
  const weakEx = achievementBullets.filter(b => weakRe.test(openingText(b).replace(/^[^a-zA-Z]+/, '')));
  issues.push(weakEx.length > 0
    ? { id: 'weak-openers', cat: 'content', level: 'warn', key: 'r.weak', vars: { n: weakEx.length }, fix: 'r.weak.fix', examples: weakEx.slice(0, 3).map(trimEx), weight: 6 }
    : { id: 'weak-openers', cat: 'content', level: 'ok', key: 'r.weak-ok', weight: 6 });

  // 5. Quantified impact
  const numRe = /(?:\b(?:EGP|SAR|AED|USD|EUR)\b|[\$€£¥₹]\s*\d+|\d+[\d,.]*\s*(?:%|k\b|m\b|b\b|x\b)?|\b\d+\b|%|[\$€£¥₹]|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|billion)\b|\b(?:hours?|days?|weeks?|months?|years?|seconds?|minutes?|quarterly|annually)\b)/i;
  let numCount = 0;
  const nonNumEx = [];
  for (const b of achievementBullets) {
    if (numRe.test(b)) numCount++;
    else nonNumEx.push(b);
  }
  const numPct = achievementBullets.length ? Math.round((numCount / achievementBullets.length) * 100) : 0;
  issues.push(numPct < 40
    ? { id: 'quantified-impact', cat: 'content', level: 'warn', key: 'r.numbers', vars: { pct: numPct }, fix: 'r.numbers.fix', examples: nonNumEx.slice(0, 3).map(trimEx), weight: 7 }
    : { id: 'quantified-impact', cat: 'content', level: 'ok', key: 'r.numbers-ok', vars: { pct: numPct }, weight: 7 });

  // 6. Bullet length
  const countWords = s => s.trim().split(/\s+/).filter(Boolean).length;
  const longBullets = bullets.filter(b => countWords(b) > 32);
  const shortBullets = bullets.filter(b => countWords(b) < 5);
  if (longBullets.length > 0) {
    issues.push({ id: 'bullet-long', cat: 'content', level: 'warn', key: 'r.long', vars: { n: longBullets.length }, fix: 'r.long.fix', examples: longBullets.slice(0, 3).map(trimEx), weight: 4 });
  }
  if (shortBullets.length > 0) {
    issues.push({ id: 'bullet-short', cat: 'content', level: 'info', key: 'r.short', vars: { n: shortBullets.length }, fix: 'r.short.fix', examples: shortBullets.slice(0, 3).map(trimEx), weight: 4 });
  }
  if (!longBullets.length && !shortBullets.length) {
    issues.push({ id: 'bullet-length', cat: 'content', level: 'ok', key: 'r.length-ok', weight: 4 });
  }

  // 7. First-person pronouns
  const pronounRe = /\b(?:I|me|my|we|our|myself|ourselves)\b/i;
  const pronounEx = bullets.filter(b => pronounRe.test(b));
  issues.push(pronounEx.length > 0
    ? { id: 'pronouns', cat: 'content', level: 'warn', key: 'r.pronouns', vars: { n: pronounEx.length }, fix: 'r.pronouns.fix', examples: pronounEx.slice(0, 3).map(trimEx), weight: 3 }
    : { id: 'pronouns', cat: 'content', level: 'ok', key: 'r.pronouns-ok', weight: 3 });

  // 8. Buzzwords
  const foundBuzz = [];
  const buzzEx = [];
  for (const item of BUZZWORDS) {
    if (item.re.test(text)) {
      foundBuzz.push(item.name);
      const matchLine = lines.find(l => item.re.test(l.text));
      if (matchLine && buzzEx.length < 3) buzzEx.push(matchLine.text);
    }
  }
  issues.push(foundBuzz.length > 0
    ? { id: 'buzzwords', cat: 'content', level: 'info', key: 'r.buzz', vars: { list: foundBuzz.join(', ') }, fix: 'r.buzz.fix', examples: buzzEx.slice(0, 3).map(trimEx), weight: 3 }
    : { id: 'buzzwords', cat: 'content', level: 'ok', key: 'r.buzz-ok', weight: 3 });

  // 9. Repeated opening verbs
  const verbTally = {};
  const verbExMap = {};
  for (const b of achievementBullets) {
    const first = openingWord(b);
    if (first.length >= 3 && ACTION_VERBS.has(first)) {
      verbTally[first] = (verbTally[first] || 0) + 1;
      if (!verbExMap[first]) verbExMap[first] = [];
      verbExMap[first].push(b);
    }
  }
  let maxVerb = null;
  let maxCount = 0;
  for (const [v, count] of Object.entries(verbTally)) {
    if (count >= 3 && count > maxCount) {
      maxVerb = v;
      maxCount = count;
    }
  }
  // 9b. Copy-pasted bullets: the same line twice adds nothing and reads as filler.
  const seenBullets = new Map();
  for (const b of achievementBullets) {
    if (/^(?:[\p{L}\p{N}][\p{L}\p{N}+.#&/-]*(?:\s+[\p{L}\p{N}][\p{L}\p{N}+.#&/-]*){0,3}):\s*/u.test(b)) continue;
    const k = b.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    if (k.split(' ').length >= 6) seenBullets.set(k, (seenBullets.get(k) || []).concat(b));
  }
  const dupes = [...seenBullets.values()].filter(list => list.length > 1);
  const dupCount = dupes.reduce((s, list) => s + list.length - 1, 0);
  issues.push(dupCount
    ? { id: 'duplicate-bullets', cat: 'content', level: dupCount >= 3 ? 'fail' : 'warn', key: 'r.dupe', vars: { n: dupCount }, fix: 'r.dupe.fix', examples: dupes.slice(0, 3).map(list => trimEx(list[0])), weight: 5 }
    : { id: 'duplicate-bullets', cat: 'content', level: 'ok', key: 'r.dupe-ok', weight: 5 });

  issues.push(maxVerb
    ? { id: 'repeated-verbs', cat: 'content', level: 'info', key: 'r.repeat', vars: { verb: maxVerb.charAt(0).toUpperCase() + maxVerb.slice(1), n: maxCount }, fix: 'r.repeat.fix', examples: (verbExMap[maxVerb] || []).slice(0, 3).map(trimEx), weight: 2 }
    : { id: 'repeated-verbs', cat: 'content', level: 'ok', key: 'r.repeat-ok', weight: 2 });

  // 10. Date formats
  const datePatterns = [
    /\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(?:19|20)\d{2}\b/gi,
    /\b(?:January|February|March|April|June|July|August|September|October|November|December)\s+(?:19|20)\d{2}\b/gi,
    /\b(?:0?[1-9]|1[0-2])[\/.](?:19|20)\d{2}\b/g,
    /\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\b/g
  ];
  const dateEx = [];
  let distinctFormats = 0;
  for (const re of datePatterns) {
    const m = text.match(re);
    if (m && m.length > 0) {
      distinctFormats++;
      dateEx.push(m[0]);
    }
  }
  issues.push(distinctFormats >= 2
    ? { id: 'date-formats', cat: 'content', level: 'warn', key: 'r.dates', fix: 'r.dates.fix', examples: dateEx.slice(0, 3).map(trimEx), weight: 3 }
    : { id: 'date-formats', cat: 'content', level: 'ok', key: 'r.dates-ok', weight: 3 });

  // 11. Word count length
  const totalWords = text.trim().split(/\s+/).filter(Boolean).length;
  if (totalWords > wordLimit) {
    issues.push({ id: 'resume-length', cat: 'content', level: 'warn', key: 'r.wordy', vars: { n: totalWords }, fix: 'r.wordy.fix', weight: 3 });
  } else if (totalWords < 200) {
    issues.push({ id: 'resume-length', cat: 'content', level: 'warn', key: 'r.thin', vars: { n: totalWords }, fix: 'r.thin.fix', weight: 3 });
  } else {
    issues.push({ id: 'resume-length', cat: 'content', level: 'ok', key: 'r.words-ok', vars: { n: totalWords }, weight: 3 });
  }

  // 12. Personal data
  issues.push(personalIssue);

  return issues;
}

export const I18N_EN = {
  'r.arabic': 'Resume appears to be primarily in Arabic.',
  'r.arabic.fix': 'Content quality checks are optimized for English. Section and contact checks are still applied.',
  'r.sec-missing': 'Missing standard sections: {list}.',
  'r.sec-missing.fix': 'Add standard headings for Education, Experience, and Skills so ATS parsers can categorize your background.',
  'r.sec-ok': 'Standard sections present ({list}).',
  'r.email-miss': 'No email address detected.',
  'r.email-miss.fix': 'Add a professional email address near the top of your resume.',
  'r.email-ok': 'Email address detected.',
  'r.phone-miss': 'No phone number detected.',
  'r.phone-miss.fix': 'Include a reachable phone number with country/area code in your header.',
  'r.phone-ok': 'Phone number detected.',
  'r.linkedin-miss': 'No LinkedIn profile URL found.',
  'r.linkedin-miss.fix': 'Add your customized LinkedIn profile link (e.g. linkedin.com/in/yourname).',
  'r.linkedin-ok': 'LinkedIn profile detected.',
  'r.location-miss': 'No city or region detected near the top.',
  'r.location-miss.fix': 'Add your general location (e.g. "Seattle, WA" or "London, UK") to help recruiters filter candidates.',
  'r.location-ok': 'Location detected near the top.',
  'r.portfolio-miss': 'No GitHub or portfolio link detected.',
  'r.portfolio-miss.fix': 'Consider linking your GitHub, portfolio, or personal website to showcase practical work.',
  'r.portfolio-ok': 'Portfolio or code repository link detected.',
  'r.verbs': 'Only {pct}% of bullet points begin with an action verb.',
  'r.verbs.fix': 'Start each bullet with an active verb (e.g. Designed, Implemented, Streamlined, Led) to highlight ownership.',
  'r.verbs-ok': 'Strong action verbs start {pct}% of your bullet points.',
  'r.weak': '{n} bullet point(s) start with passive openers.',
  'r.weak.fix': 'Replace phrases like "Responsible for" or "Worked on" with strong action verbs like Spearheaded or Executed.',
  'r.weak-ok': 'No weak opening phrases found in bullet points.',
  'r.numbers': 'Only {pct}% of bullet points contain quantifiable metrics.',
  'r.numbers.fix': 'Include numbers, percentages, dollar amounts, or timeframes (e.g. "reduced latency by 35%") to show impact.',
  'r.numbers-ok': '{pct}% of bullet points feature quantified impact.',
  'r.long': '{n} bullet point(s) exceed 32 words.',
  'r.long.fix': 'Aim for 15–25 words per bullet point. Split long sentences into distinct achievements.',
  'r.short': '{n} bullet point(s) have fewer than 5 words.',
  'r.short.fix': 'Expand brief bullets to explain what you did, how you did it, and the measured outcome.',
  'r.length-ok': 'Bullet points are concise and well-proportioned.',
  'r.pronouns': '{n} bullet point(s) contain first-person pronouns.',
  'r.pronouns.fix': 'Remove personal pronouns (I, me, my, we, our). Use direct action-oriented bullet phrasing instead.',
  'r.pronouns-ok': 'No first-person pronouns found in bullet points.',
  'r.buzz': 'Found buzzwords: {list}.',
  'r.buzz.fix': 'Replace generic buzzwords like "team player" or "hard-working" with tangible examples and achievements.',
  'r.buzz-ok': 'No overused buzzwords detected.',
  'r.repeat': 'The verb "{verb}" starts {n} bullet points.',
  'r.repeat.fix': 'Vary your opening vocabulary with synonyms (e.g. alternate Managed with Directed, Coordinated, or Guided).',
  'r.repeat-ok': 'Good variety of opening action verbs.',
  'r.dates': 'Mixed date formats detected across your resume.',
  'r.dates.fix': 'Standardize all dates to a single consistent format (e.g. "Jan 2024" or "01/2024").',
  'r.dates-ok': 'Date formats are consistent.',
  'r.wordy': 'Resume is quite long ({n} words).',
  'r.wordy.fix': 'Aim for 400–750 words to keep your resume skimmable and focused on your highest-impact work.',
  'r.thin': 'Resume is very short ({n} words).',
  'r.dupe': '{n} bullet point(s) repeat another bullet word for word.',
  'r.dupe.fix': 'Give every bullet its own result: what you did, how, and the outcome. Delete copies.',
  'r.dupe-ok': 'Every bullet point is unique.',
  'r.thin.fix': 'Aim for at least 250–400 words detailing your specific accomplishments, projects, and skills.',
  'r.words-ok': 'Resume length is well balanced ({n} words).',
  'r.personal': 'Personal demographic data detected (DOB, marital status, nationality, etc.).',
  'r.personal.fix': 'Unless required locally, remove marital status, nationality, DOB, or national IDs to minimize bias.',
  'r.personal-ok': 'No unnecessary personal or demographic data detected.'
};
