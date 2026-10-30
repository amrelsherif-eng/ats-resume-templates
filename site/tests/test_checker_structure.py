"""Round 3 structure checks: experience order, tense, undated entries, letter-spaced words, sideways text,
a text box merged into the body, light grey text, profile links behind a word, contact details in a picture,
plus extractor cases (fake bold, soft hyphens and ligatures, tables, contact split across pages).
Every rule is checked both ways: the bad CV is caught and a close good CV stays quiet."""
import base64
import io

import pymupdf
import pytest
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect

from conftest import score_of, upload
from test_checker_languages import ar_page, assert_all_arabic, modules
from test_checker_real_cvs import bullets, cv_pdf, issue

HEAD = ("<h1>Mariam Fathy</h1><p>Cairo, Egypt | +20 100 000 0000 | mariam.fathy@example.com | "
        "linkedin.com/in/mariam-fathy</p>")
PRESENT = ["Lead month-end close for 3 entities with a team of 4 accountants.",
           "Prepare consolidated statements reviewed by the external auditor.",
           "Automate bank reconciliations, saving 12 hours a month."]
PAST1 = ["Processed 1,200 supplier invoices a month with 99% accuracy.",
         "Reduced overdue receivables by 25% through weekly follow-up calls.",
         "Trained 2 new team members on the ERP posting workflow."]
PAST2 = ["Recorded daily journal entries for 150 transactions in Oracle.",
         "Supported the annual audit by preparing 60 schedules on time.",
         "Updated the fixed-asset register for 900 items."]
MIXED1 = ["Processes 1,200 supplier invoices a month with 99% accuracy.",
          "Reduced overdue receivables by 25% through weekly follow-up calls.",
          "Coordinates onboarding for 2 new team members on the ERP workflow."]
MIXED2 = ["Recorded daily journal entries for 150 transactions in Oracle.",
          "Supports the annual audit by preparing 60 schedules on time.",
          "Updated the fixed-asset register for 900 items."]
JOBS = [("Senior Accountant, Delta Foods", "Mar 2022 – Present"), ("Accountant, Nile Trading Co.", "Jan 2019 – Feb 2022"),
        ("Junior Accountant, Sun Textiles", "Jul 2016 – Dec 2018")]
TAIL = ("<h2>Education</h2><p>B.Com, Accounting, Cairo University | 2012 – 2016</p>"
        "<h2>Skills</h2><p>Oracle Financials, SAP FI, Excel, Power Query, IFRS, Egyptian VAT, Power BI</p>")
SUMMARY = ("<h2>Summary</h2><p>Accountant with 8 years of experience in month-end close, VAT and audit support for "
           "food and trading companies in Egypt.</p>")


def experience(order=(0, 1, 2), lists=(PRESENT, PAST1, PAST2), dates=True, heading="Experience"):
    rows = "".join(f"<p><b>{JOBS[i][0]}</b>{' | ' + JOBS[i][1] if dates else ''}</p>" + bullets(lists[k])
                   for k, i in enumerate(order))
    return f"<h2>{heading}</h2>{rows}"


def cv(**kw):
    return HEAD + SUMMARY + experience(**kw) + TAIL


def report(page, browser, tmp_path, body, name="Mariam-Fathy-CV.pdf"):
    upload(page, cv_pdf(browser, tmp_path, name, body))
    return score_of(page)


def doc_of(page, path):
    """The extractor's Doc for a PDF (lines with their flags), run inside the site page."""
    data = base64.b64encode(path.read_bytes()).decode()
    return page.evaluate("""async ([d, name]) => {
      const pdfjs = await import('./assets/vendor/pdfjs/pdf.min.mjs');
      pdfjs.GlobalWorkerOptions.workerSrc = new URL('./assets/vendor/pdfjs/pdf.worker.min.mjs', location.href).href;
      const { extract } = await import('./assets/ats/extract.js');
      const bytes = Uint8Array.from(atob(d), c => c.charCodeAt(0));
      const doc = await extract(pdfjs, new File([bytes], name, { type: 'application/pdf' }));
      return { text: doc.text, lines: doc.lines.map(l => ({ text: l.text, rotated: !!l.rotated })) };
    }""", [data, path.name])


# ---------- units ----------

@pytest.mark.parametrize("text,start,end", [
    ("Mar 2022 – Present", 2022 * 12 + 3, None), ("January 2019 - February 2022", 2019 * 12 + 1, 2022 * 12 + 2),
    ("Sept. 2020 to June 2021", 2020 * 12 + 9, 2021 * 12 + 6), ("03/2018 – 11/2019", 2018 * 12 + 3, 2019 * 12 + 11),
    ("2017-04 – 2018-02", 2017 * 12 + 4, 2018 * 12 + 2), ("2016 – 2019", 2016 * 12 + 6, 2019 * 12 + 6),
    ("مايو ٢٠٢٢ – حتى الآن", 2022 * 12 + 5, None), ("يناير 2019 – فبراير 2022", 2019 * 12 + 1, 2022 * 12 + 2),
])
def test_date_ranges(page, text, start, end):
    modules(page)
    got = page.evaluate("t => { const r = M.structure.parseRange(t); return r && [r.start, r.end === Infinity ? null : r.end]; }", text)
    assert got == [start, end]


@pytest.mark.parametrize("text", ["Promoted in 2021", "Jan 2022 – Mar 2020", "Room 2019-2"])
def test_not_date_ranges(page, text):
    modules(page)
    assert page.evaluate("t => M.structure.parseRange(t)", text) is None


@pytest.mark.parametrize("heading,cat", [("E X P E R I E N C E", "exp"), ("W O R K E X P E R I E N C E", "exp"),
                                         ("S K I L L S", "skills"), ("E D U C A T I O N", "edu")])
def test_letter_spaced_headings_are_still_headings(page, heading, cat):
    modules(page)
    assert page.evaluate("h => M.rules.detectHeading(h)", heading) == cat


def test_quiet_on_an_empty_doc(page):
    modules(page)
    assert page.evaluate("() => M.structure.structureIssues({ lines: [], text: '' })") == []


# ---------- experience order, tense, dates ----------

def test_oldest_first_is_noted(page, browser, tmp_path):
    report(page, browser, tmp_path, cv(order=(2, 1, 0), lists=(PAST2, PAST1, PRESENT)))
    expect(issue(page, "not listed newest first")).to_have_count(1)


def test_overlapping_and_ongoing_roles_are_fine(page, browser, tmp_path):
    body = (HEAD + "<h2>Experience</h2>" + "<p><b>Senior Accountant, Delta Foods</b> | Mar 2022 – Present</p>" + bullets(PRESENT)
            + "<p><b>Freelance Bookkeeper</b> | 2018 – Present</p>" + bullets(["Keep the books for 6 small clinics each month."])
            + "<p><b>Part-time Tutor, Cairo University</b> | Sep 2023 – Present</p>" + bullets(["Teach weekly sections to 60 students."])
            + "<p><b>Accountant, Nile Trading Co.</b> | Jan 2019 – Feb 2022</p>" + bullets(PAST1) + TAIL)
    report(page, browser, tmp_path, body)
    expect(issue(page, "newest first")).to_have_count(0)


def test_separate_sections_are_judged_apart(page, browser, tmp_path):
    body = (HEAD + "<h2>Relevant Experience</h2><p><b>Accountant, Nile Trading Co.</b> | Jan 2019 – Feb 2022</p>" + bullets(PAST1)
            + "<h2>Other Experience</h2><p><b>Barista, Coffee Lab</b> | Mar 2022 – Present</p>"
            + bullets(["Serve 200 customers a day and train 3 new baristas."]) + TAIL)
    report(page, browser, tmp_path, body)
    expect(issue(page, "newest first")).to_have_count(0)


def test_mixed_tense_in_past_roles_is_noted(page, browser, tmp_path):
    report(page, browser, tmp_path, cv(lists=(PRESENT, MIXED1, MIXED2)))
    expect(issue(page, "mix tenses")).to_have_count(1)


@pytest.mark.parametrize("lists", [(PRESENT, PAST1, PAST2),
                                   ([b.replace("Lead", "Led").replace("Prepare", "Prepared").replace("Automate", "Automated") for b in PRESENT], PAST1, PAST2),
                                   (PRESENT, [b.replace("Processed", "Process").replace("Reduced", "Reduce").replace("Trained", "Train") for b in PAST1],
                                    [b.replace("Recorded", "Record").replace("Supported", "Support").replace("Updated", "Update") for b in PAST2])])
def test_consistent_tense_is_fine(page, browser, tmp_path, lists):
    report(page, browser, tmp_path, cv(lists=lists))
    expect(issue(page, "mix tenses")).to_have_count(0)


def test_undated_entries_are_noted(page, browser, tmp_path):
    report(page, browser, tmp_path, cv(dates=False))
    expect(issue(page, "have no dates")).to_have_count(1)


def test_date_on_its_own_line_counts(page, browser, tmp_path):
    body = (HEAD + "<h2>Experience</h2><p><b>Delta Foods, Cairo</b></p><p style='text-align:right'>Mar 2022 – Present</p>"
            "<p>Senior Accountant</p>" + bullets(PRESENT) + "<p><b>Nile Trading Co., Giza</b></p>"
            "<p style='text-align:right'>Jan 2019 – Feb 2022</p><p>Accountant</p>" + bullets(PAST1) + TAIL)
    report(page, browser, tmp_path, body)
    expect(issue(page, "have no dates")).to_have_count(0)


# ---------- layout: spaced letters, sideways text, side boxes, contrast ----------

def test_letter_spaced_headings_are_noted_but_sections_found(page, browser, tmp_path):
    body = "<style>h2{letter-spacing:5px}</style>" + cv()
    report(page, browser, tmp_path, body)
    expect(issue(page, "spaced out letter by letter")).to_have_count(1)
    expect(issue(page, "Missing standard sections")).to_have_count(0)


def test_slight_letter_spacing_is_fine(page, browser, tmp_path):
    report(page, browser, tmp_path, "<style>h2{letter-spacing:1.2px}</style>" + cv())
    expect(issue(page, "spaced out")).to_have_count(0)


def test_sideways_text_is_noted_not_mixed_into_the_body(page, browser, tmp_path):
    side = ("<div style='position:absolute;left:-30mm;top:120mm;transform:rotate(-90deg);font-size:14pt;color:#555'>"
            "PORTFOLIO · ACCOUNTING · 2026</div>")
    path = cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", side + "<div style='margin-left:12mm'>" + cv() + "</div>")
    doc = doc_of(page, path)
    rotated = [l["text"] for l in doc["lines"] if l["rotated"]]
    assert rotated and all("Accountant" not in t for t in rotated)
    assert not any("PORT" in l["text"] for l in doc["lines"] if not l["rotated"])
    upload(page, path)
    score_of(page)
    expect(issue(page, "turned sideways")).to_have_count(1)
    expect(issue(page, "spaced out")).to_have_count(0)


def test_box_beside_the_text_is_flagged(page, browser, tmp_path):
    box = ("<div style='float:right;width:55mm;border:2px solid #2a6;padding:6px;margin:6px 0 6px 10px'>"
           "<b>Key results</b><br>Closed books 3 days faster.<br>Zero VAT penalties in 3 years.</div>")
    assert report(page, browser, tmp_path, HEAD + box + SUMMARY + experience() + TAIL) <= 84
    expect(issue(page, "text box beside your main text")).to_have_count(1)


def test_light_grey_text_is_noted(page, browser, tmp_path):
    report(page, browser, tmp_path, "<style>body{color:#999}</style>" + cv())
    expect(issue(page, "light grey")).to_have_count(1)


@pytest.mark.parametrize("css", ["p{color:#666}", "body{color:#444}",
                                 "body{margin:0}.side{background:#1d3557;color:#fff;padding:8px}"])
def test_dark_or_inverted_text_is_fine(page, browser, tmp_path, css):
    report(page, browser, tmp_path, f"<style>{css}</style><div class='side'>{HEAD}</div>" + SUMMARY + experience() + TAIL)
    expect(issue(page, "light grey")).to_have_count(0)


# ---------- contact ----------

def test_profile_link_behind_a_word_is_noted(page, browser, tmp_path):
    head = ("<h1>Mariam Fathy</h1><p>Cairo, Egypt | +20 100 000 0000 | mariam.fathy@example.com | "
            "<a href='https://www.linkedin.com/in/mariam-fathy'>LinkedIn</a></p>")
    report(page, browser, tmp_path, head + SUMMARY + experience() + TAIL)
    expect(issue(page, "hidden behind a word")).to_have_count(1)


def test_project_links_and_visible_profile_links_are_fine(page, browser, tmp_path):
    head = ("<h1>Mariam Fathy</h1><p>Cairo, Egypt | +20 100 000 0000 | mariam.fathy@example.com | "
            "<a href='https://www.linkedin.com/in/mariam-fathy'>linkedin.com/in/mariam-fathy</a></p>")
    proj = "<h2>Projects</h2><p><a href='https://github.com/mariam-fathy/cash-flow-model'>Cash-flow model</a> | 2023</p>"
    report(page, browser, tmp_path, head + SUMMARY + experience() + proj + TAIL)
    expect(issue(page, "hidden behind a word")).to_have_count(0)


def picture(text):
    im = Image.new("RGB", (420, 26), "white")
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(im).text((2, 3), text, fill=(30, 30, 30), font=font)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_contact_in_a_picture_is_explained(page, browser, tmp_path):
    head = (f"<h1>Mariam Fathy</h1><p>Cairo, Egypt</p><img src='{picture('mariam.fathy@example.com | +20 100 000 0000')}' "
            "style='height:16pt'>")
    report(page, browser, tmp_path, head + SUMMARY + experience() + TAIL)
    expect(issue(page, "email address in the text. If it is in a picture")).to_have_count(1)
    expect(issue(page, "phone number in the text. If it is in a picture")).to_have_count(1)


def test_a_photo_next_to_text_contact_is_fine(page, browser, tmp_path):
    report(page, browser, tmp_path, f"<img src='{picture('')}' style='width:60px'>" + cv())
    expect(issue(page, "in a picture")).to_have_count(0)
    expect(issue(page, "No email")).to_have_count(0)


def test_contact_split_across_pages(page, browser, tmp_path):
    body = ("<h1>Mariam Fathy</h1><p>Cairo, Egypt | mariam.fathy@example.com | linkedin.com/in/mariam-fathy</p>"
            + SUMMARY + experience() + "<div style='break-before:page'></div>" + TAIL + "<h2>Contact</h2><p>Phone: +20 100 123 4567</p>")
    report(page, browser, tmp_path, body)
    expect(issue(page, "phone number")).to_have_count(0)
    expect(issue(page, "email address")).to_have_count(0)


# ---------- extractor cases ----------

def test_fake_bold_is_read_once(page, tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page(width=595, height=842)
    y = 60
    rows = [("Mariam Fathy", 18), ("Cairo, Egypt | mariam.fathy@example.com | +20 100 123 4567", 10), ("Experience", 12),
            ("Senior Accountant, Delta Foods, Cairo  Mar 2022 - Present", 10)] + [("- " + b, 10) for b in PRESENT] + \
           [("Education", 12), ("B.Com, Accounting, Cairo University  2012 - 2016", 10), ("Skills", 12), ("Oracle, SAP FI, Excel", 10)]
    for text, size in rows:
        for dx in ((0, 0.35) if size >= 12 else (0,)):
            pg.insert_text((50 + dx, y), text, fontsize=size, fontname="helv")
        y += size * 1.6
    path = tmp_path / "Mariam-Fathy-CV.pdf"
    doc.save(path)
    text = doc_of(page, path)["text"]
    assert "ExperienceExperience" not in text and text.count("Mariam Fathy") == 1 and "\nEducation\n" in text
    upload(page, path)
    score_of(page)
    expect(issue(page, "Missing standard sections")).to_have_count(0)


def test_ligatures_and_soft_hyphens(page, browser, tmp_path):
    summary = ("<h2>Summary</h2><p style='width:250px'>Accoun&shy;tant, certiﬁed, ofﬁce workﬂow, "
               "recon&shy;cili&shy;ation and con&shy;sol&shy;i&shy;da&shy;tion for trad&shy;ing com&shy;pa&shy;nies.</p>")
    path = cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", HEAD + summary + experience() + TAIL)
    text = doc_of(page, path)["text"]
    assert "certified" in text and "office" in text and "workflow" in text and "­" not in text
    upload(page, path)
    score_of(page)
    expect(issue(page, "garbled")).to_have_count(0)


def test_skills_cloud_is_not_a_long_bullet(page, browser, tmp_path):
    cloud = ", ".join(f"Skill {chr(65 + i % 26)}{i}" for i in range(45))
    report(page, browser, tmp_path, HEAD + SUMMARY + experience() + TAIL.replace("Oracle Financials", cloud + ", Oracle Financials"))
    expect(issue(page, "Missing standard sections")).to_have_count(0)
    expect(issue(page, "exceed 32 words")).to_have_count(0)


def test_same_bullet_under_two_roles_is_flagged(page, browser, tmp_path):
    report(page, browser, tmp_path, cv(lists=(PRESENT, PAST1, [PAST1[0]] + PAST2[1:])))
    expect(issue(page, "repeat another bullet")).to_have_count(1)


def test_table_keeps_dates_with_their_role(page, browser, tmp_path):
    rows = "".join(f"<tr><td style='width:28%;vertical-align:top'>{d}</td><td><b>{t}</b>{bullets(PAST1)}</td></tr>" for t, d in JOBS)
    path = cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", HEAD + "<h2>Experience</h2><table>" + rows + "</table>" + TAIL)
    lines = [l["text"] for l in doc_of(page, path)["lines"]]
    for title, dates in JOBS:
        assert any(title in l and dates in l for l in lines), (title, lines)


# ---------- the plain CV and the Arabic report ----------

def test_plain_cv_gets_none_of_the_new_notes(page, browser, tmp_path):
    report(page, browser, tmp_path, cv())
    for text in ("newest first", "mix tenses", "no dates", "spaced out", "sideways", "text box", "light grey", "behind a word", "in a picture"):
        expect(issue(page, text)).to_have_count(0)


def test_new_notes_in_arabic(page, browser, site_url, tmp_path):
    ar_page(page, site_url)
    box = ("<div style='float:right;width:55mm;border:2px solid #2a6;padding:6px;margin:6px 0 6px 10px'>"
           "<b>Key results</b><br>Closed books 3 days faster.<br>Zero VAT penalties in 3 years.</div>")
    body = "<style>h2{letter-spacing:5px}</style>" + HEAD + box + SUMMARY + experience(order=(2, 1, 0), lists=(MIXED2, MIXED1, PRESENT)) + TAIL
    upload(page, cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", body))
    score_of(page)
    assert_all_arabic(page)
    titles = " ".join(page.locator("#chk-out .issue-t").all_text_contents())
    for text in ("الأحدث إلى الأقدم", "تخلط بين الأزمنة", "حروف متباعدة", "مربع نص"):
        assert text in titles, text
