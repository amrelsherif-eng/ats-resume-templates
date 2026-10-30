"""Robustness of the checker: files that are not resumes or not PDFs, secured / portfolio / form PDFs,
very long files, accessibility of the report, determinism, security, privacy, UI state and speed.
Every fixture is built here from fake data (pymupdf, raw bytes or the browser's own PDF printer)."""
import io
import re
import time

import pymupdf
import pytest
from PIL import Image
from playwright.sync_api import expect

from conftest import CHECK_TIMEOUT, assert_checker_did_not_crash, score_of, upload
from test_checker_real_cvs import HEADER, bullets, cv_pdf
from test_site import capture_clipboard, copied_text

GOOD = (HEADER + "<h2>Experience</h2><p>Software Engineer, Example Systems, Jan 2021 - Present</p>"
        + bullets(["Built a billing service used by 40,000 customers with Python and PostgreSQL",
                   "Reduced page load time by 35% by caching product data at the edge",
                   "Automated release checks and cut failed deployments from 9 to 2 per quarter",
                   "Mentored 3 interns who all received return offers"])
        + "<h2>Education</h2><p>BSc Computer Engineering, Cairo University, 2020</p>"
        "<h2>Skills</h2><p>Python, Go, PostgreSQL, Docker, Kubernetes, AWS</p>")


@pytest.fixture(scope="module")
def good(browser, tmp_path_factory):
    return cv_pdf(browser, tmp_path_factory.mktemp("robust"), "Mariam-Fathy-CV.pdf", GOOD)


def write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def error_of(page):
    error = page.locator("#chk-out .chk-error")
    expect(error).to_be_visible(timeout=CHECK_TIMEOUT)
    return error


def problem(page, text):
    return page.locator("#chk-out .issue:not(.ok)", has_text=re.compile(text, re.I))


def ar_page(page, site_url):
    page.goto(site_url + "/ar.html", wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("lang", "ar")


def png_bytes():
    out = io.BytesIO()
    Image.new("RGB", (300, 400), "white").save(out, "PNG")
    return out.getvalue()


def jpg_bytes():
    out = io.BytesIO()
    Image.new("RGB", (300, 400), "white").save(out, "JPEG")
    return out.getvalue()


def text_pdf(path, pages):
    """pages: list of lists of lines (fast pymupdf text PDF)."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        rc = page.insert_textbox(pymupdf.Rect(40, 40, 570, 810), "\n".join(lines), fontsize=7)
        assert rc >= 0, "fixture text does not fit the page"
    doc.save(path)
    doc.close()
    return path


# ---------- Error paths: one clear message per cause, never a stuck UI ----------

NOT_PDF = [
    ("empty.pdf", lambda: b"", "This file is empty"),
    ("photo.pdf", png_bytes, "This is an image, not a PDF"),
    ("scan.pdf", jpg_bytes, "This is an image, not a PDF"),
    ("word.pdf", lambda: b"PK\x03\x04" + bytes(range(256)) * 8, "Word or other document"),
    ("old-word.pdf", lambda: b"\xd0\xcf\x11\xe0" + bytes(range(256)) * 8, "Word or other document"),
    ("page.pdf", lambda: b"<!doctype html><html><body><h1>CV</h1></body></html>", "web page or text file"),
    ("notes.pdf", lambda: b"Name: Test Person\nThis is plain text.\n", "web page or text file"),
    ("binary.pdf", lambda: bytes([0, 1, 2, 3, 250, 251]) * 100, "This file is not a PDF"),
    ("garbage.pdf", lambda: b"%PDF-1.7\n" + bytes(range(256)) * 200, "damaged or incomplete"),
]


@pytest.mark.parametrize("name,make,message", NOT_PDF, ids=[c[0] for c in NOT_PDF])
def test_wrong_file_gets_its_own_clear_message(page, tmp_path, name, make, message):
    upload(page, write(tmp_path, name, make()))
    error = error_of(page)
    expect(error).to_contain_text(message)
    expect(error).to_have_attribute("role", "alert")
    expect(page.locator("#chk-out .ring-n")).to_have_count(0)
    assert page.locator("#chk-file").is_enabled()
    assert_checker_did_not_crash(page)


def test_password_and_truncated_pdf(page, good, tmp_path):
    doc = pymupdf.open(good)
    locked = tmp_path / "locked.pdf"
    doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner-x", user_pw="reader-x")
    doc.close()
    upload(page, locked)
    expect(error_of(page)).to_contain_text("password-protected")
    upload(page, write(tmp_path, "half.pdf", good.read_bytes()[: good.stat().st_size // 2]))
    expect(error_of(page)).to_contain_text("damaged or incomplete")
    assert_checker_did_not_crash(page)


@pytest.mark.parametrize("name,make", [("empty.pdf", lambda: b""), ("photo.pdf", png_bytes), ("notes.pdf", lambda: b"plain text")])
def test_arabic_error_messages_are_specific(page, site_url, tmp_path, name, make):
    ar_page(page, site_url)
    upload(page, write(tmp_path, name, make()))
    text = error_of(page).text_content()
    assert re.search(r"[؀-ۿ]", text) and "تعذّرت" not in text, text  # a specific message, not the fallback


def test_error_after_report_replaces_it_and_focus_moves_to_it(page, good, tmp_path):
    upload(page, good)
    score_of(page)
    upload(page, write(tmp_path, good.name, b"%PDF-1.4\n" + b"x" * 200))  # same name, broken file
    error_of(page)
    expect(page.locator("#chk-out .ring-n, #chk-out .chk-tools, #chk-out .chk-text")).to_have_count(0)
    assert page.evaluate("document.activeElement.classList.contains('chk-error')")


# ---------- PDFs with comments, forms, attachments, restrictions, many pages ----------

def resaved(good, tmp_path):
    """The good CV saved again by pymupdf: the baseline for edits made with pymupdf."""
    doc = pymupdf.open(good)
    path = tmp_path / "resaved.pdf"
    doc.save(path)
    doc.close()
    return path


def test_comments_on_a_good_cv_are_not_hidden_text(page, good, tmp_path):
    upload(page, resaved(good, tmp_path))
    plain = score_of(page)
    doc = pymupdf.open(good)
    doc[0].add_freetext_annot(pymupdf.Rect(300, 20, 580, 60), "Reviewer note: looks good to me", fontsize=9)
    doc[0].add_text_annot((20, 20), "sticky note from a reviewer")
    noted = tmp_path / "noted.pdf"
    doc.save(noted)
    doc.close()
    upload(page, noted)
    expect(page.locator("#chk-out .chk-file")).to_contain_text("noted.pdf")
    assert score_of(page) == plain
    expect(problem(page, "Hidden text")).to_have_count(0)
    expect(page.locator("#chk-out .chk-alert")).to_have_count(0)


def test_text_only_in_form_fields_or_comments(page, tmp_path):
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    values = [("Name", "Test Person"), ("Email", "test.person@example.com"),
              ("Experience", "Software Engineer at Example Company from 2020 to the present day building web services")]
    for i, (label, value) in enumerate(values):
        widget = pymupdf.Widget()
        widget.field_name, widget.field_type = label, pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.rect, widget.field_value = pymupdf.Rect(60, 60 + i * 40, 540, 90 + i * 40), value
        pdf_page.add_widget(widget)
    form = tmp_path / "form.pdf"
    doc.save(form)
    doc.close()
    upload(page, form)
    assert score_of(page) <= 25
    expect(problem(page, "fillable form fields or comments")).to_have_count(1)
    expect(problem(page, "Hidden text")).to_have_count(0)


def test_portfolio_says_the_resume_is_attached(page, good, tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Portfolio: open the attached file.", fontsize=12)
    doc.embfile_add("Mariam-Fathy-CV.pdf", good.read_bytes(), filename="Mariam-Fathy-CV.pdf")
    path = tmp_path / "portfolio.pdf"
    doc.save(path)
    doc.close()
    upload(page, path)
    assert score_of(page) <= 25
    expect(problem(page, r"portfolio: your resume \(Mariam-Fathy-CV\.pdf\)")).to_have_count(1)


def test_restricted_pdf_gets_a_warning(page, good, tmp_path):
    upload(page, resaved(good, tmp_path))
    plain = score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="No security restrictions")).to_have_count(1)
    doc = pymupdf.open(good)
    locked = tmp_path / "restricted.pdf"
    doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner-x", permissions=pymupdf.PDF_PERM_ACCESSIBILITY)
    doc.close()
    upload(page, locked)
    assert plain - 3 <= score_of(page) <= plain
    expect(page.locator("#chk-out .issue.warn", has_text="security restrictions")).to_have_count(1)


def test_very_long_file_is_capped_and_says_only_ten_pages(page, good, tmp_path):
    doc, src = pymupdf.open(good), pymupdf.open(good)
    while doc.page_count < 14:
        doc.insert_pdf(src)
    path = tmp_path / "long.pdf"
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    upload(page, path)
    assert score_of(page) <= 60
    expect(page.locator("#chk-out .issue.info", has_text="Only the first 10 pages were checked")).to_have_count(1)


def test_academic_cv_is_not_capped_for_length(page, good, tmp_path):
    page.locator('#chk-level input[value="academic"]').check(force=True)
    doc, src = pymupdf.open(good), pymupdf.open(good)
    while doc.page_count < 8:
        doc.insert_pdf(src)
    path = tmp_path / "academic.pdf"
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    upload(page, path)
    assert score_of(page) > 60


def test_page_of_single_letters_is_not_a_resume(page, tmp_path):
    rows = [" ".join("abcdefghij"[(r + c) % 10] for c in range(60)) for r in range(55)]
    upload(page, text_pdf(tmp_path / "letters.pdf", [rows]))
    assert score_of(page) <= 40
    expect(problem(page, "does not read like a resume")).to_have_count(1)


# ---------- Accessibility of the report ----------

def test_keyboard_one_tab_stop_visible_focus_and_focus_on_result(page, good):
    assert page.locator("#chk-drop").get_attribute("tabindex") is None
    page.locator("#chk-file").focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "chk-file"
    assert page.evaluate("getComputedStyle(document.getElementById('chk-drop')).outlineStyle") == "solid"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") != "chk-drop", "the drop zone is not a second tab stop"
    # Enter on a native file input opens the browser's chooser (not reliable to drive headless): pick the file directly.
    upload(page, good)
    score = score_of(page)
    expect(page.locator("#chk-out .chk-verdict")).to_be_focused()
    expect(page.locator("#chk-status")).to_have_text(re.compile(rf"Report ready: score {score} out of 100"))
    assert page.locator("#chk-out").get_attribute("aria-live") is None
    assert page.locator("#chk-out").get_attribute("aria-busy") is None


def test_level_change_does_not_steal_focus(page, good):
    upload(page, good)
    score_of(page)
    page.locator('#chk-level input[value="senior"]').focus()
    page.locator('#chk-level input[value="senior"]').check(force=True)
    page.wait_for_timeout(200)
    assert page.evaluate("document.activeElement.value") == "senior"


def test_severity_is_spoken_and_icons_are_real_characters(page, site_url, good):
    upload(page, good)
    score_of(page)
    first = page.locator("#chk-out .issue summary").first
    assert re.match(r"(Must fix|Worth fixing|Tip|Passed): ", first.locator(".sr-only").text_content())
    assert page.locator("#chk-out .issue .dot").first.get_attribute("aria-hidden") == "true"
    icons = page.evaluate("""() => ['ok', 'fail'].map(level => {
      const d = document.createElement('details'); d.className = 'issue ' + level;
      const s = document.createElement('span'); s.className = 'dot'; d.append(s); document.body.append(d);
      const c = getComputedStyle(s, '::before').content; d.remove(); return c; })""")
    assert icons == ['"✓"', '"✕"'], icons
    css = page.request.get(site_url + "/assets/styles.css").text()
    assert "�" not in css


# ---------- Determinism, metamorphic, score properties ----------

def report(page):
    score = score_of(page)
    page.wait_for_timeout(200)
    return {"score": score, "bars": page.locator("#chk-out .bar-n").all_text_contents(),
            "issues": page.locator("#chk-out .issue").evaluate_all(
                "els => els.map(e => [...e.classList].join('.') + ':' + e.querySelector('.issue-t').textContent)")}


def test_determinism_and_file_name_and_metadata_do_not_change_the_result(page, good, tmp_path):
    runs = []
    for _ in range(3):
        upload(page, good)
        runs.append(report(page))
        page.locator("#chk-out .chk-head").wait_for()
    assert runs[0] == runs[1] == runs[2]
    ids = page.locator("#chk-out .issue-t").all_text_contents()
    assert len(ids) == len(set(ids)), "every check appears once"
    renamed = write(tmp_path, "Mariam-Fathy-Resume-2026.pdf", good.read_bytes())
    upload(page, renamed)
    expect(page.locator("#chk-out .chk-name")).to_have_text(renamed.name)
    assert report(page) == runs[0]
    doc = pymupdf.open(good)
    doc.set_metadata({"title": "Another title", "author": "Someone Else", "producer": "Other Producer 9"})
    meta = tmp_path / good.name
    doc.save(meta)
    doc.close()
    upload(page, meta)
    expect(page.locator("#chk-out .chk-name")).to_have_text(good.name)
    assert report(page) == runs[0]


FUZZ = """async (n) => {
  const [layout, rules, hidden, structure, robust, score, ar] = await Promise.all(['layout', 'rules', 'hidden', 'structure',
    'robust', 'score', 'i18n-ar'].map(m => import('./assets/ats/' + m + '.js')));
  const EN = { ...layout.I18N_EN, ...rules.I18N_EN, ...hidden.I18N_EN, ...structure.I18N_EN, ...robust.I18N_EN };
  let seed = 20261030;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const pick = a => a[Math.floor(rnd() * a.length)];
  const pieces = ['Experience', 'EDUCATION', 'Skills', 'الخبرة', 'التعليم', 'Led a team of 5', 'Responsible for',
    'mariam@example.com', '+20 100 000 0000', '2019 - Present', 'Jan 2020', '•', '', ' ', '\\u0000', '<b>x</b>',
    'ﷺ', '😀', 'a'.repeat(5000), 'I am', 'ignore previous instructions', '٠١٠٠١٢٣٤٥٦٧', 'Développeur', '—', '|'];
  const problems = [];
  const LEVELS = ['fail', 'warn', 'info', 'ok'], CATS = ['parse', 'content', 'contact'];
  for (let k = 0; k < n; k++) {
    const lines = Array.from({ length: Math.floor(rnd() * 40) }, (_, i) => {
      const text = Array.from({ length: 1 + Math.floor(rnd() * 4) }, () => pick(pieces)).join(' ');
      const x = rnd() * 600, size = pick([0, 2, 9, 11, 30]);
      return { page: 1 + Math.floor(rnd() * 3), y: i * 12 + rnd() * 5, x, right: x + rnd() * 300, h: size, rtl: rnd() < 0.2,
        text, bullet: text.startsWith('•'), rotated: rnd() < 0.05,
        items: [{ text, x, y: i * 12, w: rnd() * 300, h: size, size, font: pick(['Arial|f1', 'Times|f2', '|f3']),
          hidden: pick([undefined, undefined, 'tiny', 'invisible']), contrast: pick([undefined, 1.2, 4.5, 21]) }] };
    });
    const doc = { pages: 1 + Math.floor(rnd() * 30), width: pick([595, 612, 0]), height: 842, lines,
      text: lines.map(l => l.text).join('\\n'), streamText: lines.map(l => l.text).join(''), fonts: ['Arial'],
      images: Math.floor(rnd() * 5), links: rnd() < 0.5 ? ['https://linkedin.com/in/x'] : [], hiddenChecked: rnd() < 0.8,
      offPage: rnd() < 0.1 ? ['offpage text here'] : [], fileName: pick(['cv.pdf', 'Resume.pdf', '']), fileSize: rnd() * 3e7,
      meta: {}, secured: rnd() < 0.2, attachments: rnd() < 0.1 ? ['cv.pdf'] : [], formWords: Math.floor(rnd() * 30), noteWords: 0 };
    const level = pick(['student', 'junior', 'mid', 'senior', 'academic']);
    let issues;
    try {
      issues = [...layout.layoutIssues(doc, { level }), ...rules.contentIssues(doc, { level }), ...hidden.hiddenIssues(doc),
        ...structure.structureIssues(doc), ...robust.robustIssues(doc)];
    } catch (e) { problems.push('throw: ' + e.message); continue; }
    const ids = issues.map(i => i.id);
    if (new Set(ids).size !== ids.length) problems.push('duplicate id: ' + ids.join());
    for (const i of issues) {
      if (!LEVELS.includes(i.level) || !CATS.includes(i.cat) || !Number.isFinite(i.weight) || i.weight < 0) problems.push('bad issue ' + JSON.stringify(i).slice(0, 120));
      if (!EN[i.key] || !ar.CHECK_AR[i.key]) problems.push('missing message ' + i.key);
    }
    const base = score.score(issues, doc, level);
    const nums = [base.overall, ...Object.values(base.per)];
    if (!nums.every(v => Number.isInteger(v) && v >= 0 && v <= 100)) problems.push('score out of range ' + nums);
    // Monotonicity: making any one issue worse never raises a category or the overall score.
    issues.forEach((i, j) => {
      const worse = LEVELS.indexOf(i.level) > 0 ? LEVELS[LEVELS.indexOf(i.level) === 3 ? 1 : 0] : null;
      if (!worse || i.level === 'info') return;
      const s = score.score(issues.map((x, m) => (m === j ? { ...x, level: worse } : x)), doc, level);
      if (s.overall > base.overall || s.per[i.cat] > base.per[i.cat]) problems.push(`not monotonic: ${i.id} ${i.level}->${worse}`);
    });
  }
  return problems.slice(0, 10);
}"""


def test_rule_engine_totality_score_bounds_and_monotonicity(page):
    assert page.evaluate(FUZZ, 300) == []


# ---------- Security and privacy ----------

def test_markup_in_pdf_text_and_file_name_stays_text(page, tmp_path):
    lines = ["Test Person", "test.person@example.com +20 100 000 0000", "Experience",
             '<img src=x onerror="window.__xss=1">', "<script>window.__xss=2</script>", '"><svg onload=window.__xss=3>'] + \
            ["Built a service used by 5,000 people with Python and SQL"] * 30
    path = text_pdf(tmp_path / "markup.pdf", [lines])
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.locator("#chk-file").set_input_files({"name": '"><svg onload=window.__xss=4>.pdf', "mimeType": "application/pdf",
                                               "buffer": path.read_bytes()})
    score_of(page)
    expect(page.locator("#chk-out .chk-name")).to_contain_text("<svg onload")
    page.locator("#chk-out .chk-text summary").click()
    expect(page.locator("#chk-out .chk-text pre")).to_contain_text("<script>")
    assert page.evaluate("window.__xss") is None and not dialogs
    assert page.locator("#chk-out img, #chk-out script, #chk-out svg:not(.ring), #chk-out iframe").count() == 0


def test_pdf_links_never_navigate_or_open_pages(page, tmp_path):
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    pdf_page.insert_textbox(pymupdf.Rect(50, 50, 560, 800), "\n".join(
        ["Test Person", "test.person@example.com", "Experience"] + ["Built a service used by 5,000 people"] * 30), fontsize=9)
    pdf_page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(0, 0, 600, 400), "uri": "https://example.com/track"})
    pdf_page.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(0, 400, 600, 800), "uri": "javascript:window.__nav=1"})
    path = tmp_path / "links.pdf"
    doc.save(path)
    doc.close()
    url = page.url
    popups = []
    page.context.on("page", lambda p: popups.append(p))
    upload(page, path)
    score_of(page)
    page.locator("#chk-out .chk-head").click()
    page.locator("#chk-out .chk-text summary").click()
    page.wait_for_timeout(300)
    assert page.url == url and not popups and page.evaluate("window.__nav") is None
    assert not [u for u in page._blocked_hosts if "example.com" in u]


def test_no_requests_no_csp_violations_and_no_leak_during_checks(page, tmp_path):
    page.evaluate("window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective))")
    sentinel = "SENTINEL-7f3a"
    lines = ["Test Person " + sentinel, "test.person@example.com", "Experience"] + ["Built a service used by 5,000 people"] * 30
    path = text_pdf(tmp_path / f"cv-{sentinel}.pdf", [lines])
    doc = pymupdf.open(path)
    doc.set_metadata({"title": sentinel, "author": sentinel})
    doc.saveIncr()
    doc.close()
    upload(page, path)  # first check: pdf.js and its worker load
    score_of(page)
    requests = []
    # Lazy page images may load as the report scrolls into view; they carry nothing from the file.
    page.on("request", lambda r: r.resource_type == "image" or requests.append((r.url, r.post_data or "", str(r.headers))))
    for _ in range(3):
        upload(page, path)
        score_of(page)
        page.wait_for_timeout(200)
    assert [r[0] for r in requests if not r[0].startswith(("blob:", "data:"))] == []
    assert not [r for r in requests if sentinel in "".join(r)]
    assert page.evaluate("window.__csp") == []


# ---------- UI state ----------

def test_two_files_in_a_row_leave_nothing_of_the_first(page, good, tmp_path):
    upload(page, good)
    score_of(page)
    other = text_pdf(tmp_path / "Other-Person-CV.pdf", [["Other Person", "other@example.com", "Experience"]
                                                        + ["Designed bridges for 12 cities"] * 30])
    upload(page, other)
    expect(page.locator("#chk-out .chk-name")).to_have_text("Other-Person-CV.pdf")
    page.locator("#chk-out .chk-text summary").click()
    text = page.locator("#chk-out").inner_text()
    assert "Mariam" not in text and "Mariam-Fathy-CV" not in text


def test_level_change_only_changes_length_rows(page, good, tmp_path):
    doc, src = pymupdf.open(good), pymupdf.open(good)
    doc.insert_pdf(src)
    two = tmp_path / "two-pages.pdf"
    doc.save(two)
    doc.close()
    upload(page, two)
    before = report(page)
    page.locator('#chk-level input[value="senior"]').check(force=True)
    page.wait_for_timeout(300)
    after = report(page)
    changed = {a for a in set(before["issues"]) ^ set(after["issues"])}
    assert changed and all(re.search(r"page|words|long|short", c, re.I) for c in changed), changed


def test_copy_prompt_and_preview_caps(page, tmp_path):
    long_line = "I was responsible for helping users and teams with various tasks every day"
    pages = [["Test Person", "test.person@example.com", "Experience"] + [f'"{long_line}" <b>{p}-{i}</b>' for i in range(60)]
             for p in range(10)]
    upload(page, text_pdf(tmp_path / "dense.pdf", pages))
    score_of(page)
    capture_clipboard(page)
    page.locator("#chk-out .chk-tools button").click()
    prompt = copied_text(page, "MY RESUME")
    assert "Keep it truthful" in prompt
    resume = prompt.split("--- MY RESUME (extracted text) ---\n", 1)[1]
    assert 11000 < len(resume) <= 12000
    assert "file name" not in prompt and "pages:" not in prompt  # only issues an AI can fix by rewriting
    assert len(page.locator("#chk-out .chk-text pre").text_content()) <= 6000
    words = int(re.search(r"\((\d[\d,]*) words\)", page.locator("#chk-out .issue", has_text="Selectable text found").text_content()).group(1).replace(",", ""))
    assert words > 6000 / 6  # findings use the full text, not the preview


# ---------- Performance budget (Chromium CPU throttling, like a low-end phone) ----------

# Generous bounds for shared CI machines: this guards against freezes and large regressions. Measured on a
# quiet laptop at 4x: about 2 s for one page; prep notes in promo/checker-rounds/round4-robustness.md.
@pytest.mark.parametrize("pages,budget", [(1, 15.0), (10, 60.0)])
def test_performance_budget_on_a_slow_phone(page, good, tmp_path, pages, budget):
    doc, src = pymupdf.open(good), pymupdf.open(good)
    while doc.page_count < pages:
        doc.insert_pdf(src)
    path = tmp_path / f"p{pages}.pdf"
    doc.save(path)
    doc.close()
    page.locator("#chk-drop").scroll_into_view_if_needed()
    page.wait_for_load_state("networkidle")
    upload(page, path)  # warm-up: pdf.js and its worker
    score_of(page)
    page.evaluate("window.__lt = []; new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(e.duration))).observe({type: 'longtask'})")
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    start = time.perf_counter()
    upload(page, path)
    expect(page.locator("#chk-out .chk-file")).to_contain_text(f"{pages} ", timeout=60_000)
    score_of(page)
    elapsed = time.perf_counter() - start
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    longest = max(page.evaluate("window.__lt") or [0])
    heap = page.evaluate("performance.memory ? performance.memory.usedJSHeapSize : 0") / 1e6
    assert elapsed < budget, f"{elapsed:.1f} s"
    assert longest < 3000, f"long task {longest:.0f} ms"
    assert heap < 150, f"{heap:.0f} MB"
