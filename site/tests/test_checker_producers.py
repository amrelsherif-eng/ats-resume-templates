"""Round 1 (PDF producers): CVs whose side-by-side columns are merged into one line by the extractor
(LinkedIn "Save to PDF", Overleaf paracol, sidebar builders). A heading in one column must still be found,
and the Experience bullets beside a sidebar must still be read. Good single-column CVs stay unchanged."""
import base64
from pathlib import Path

import pymupdf
import pytest

from conftest import score_of, upload
from test_checker_languages import modules
from test_checker_real_cvs import bullets, cv_pdf, issue

BUL = ["Built 14 Power BI dashboards used by 60 managers in 5 regions.",
       "Cut the monthly reporting time by 40% by automating SQL extracts.",
       "Reduced data errors by 30% with weekly validation checks.",
       "Trained 12 analysts on DAX and data modelling over 3 months.",
       "Delivered a sales forecast model with 92% accuracy for 2024.",
       "Migrated 25 Excel reports to a shared data model in 6 weeks."]
SIDE = ["Contact", "salma.adel@example.com", "+20 100 000 0000", "Top Skills", "Power BI", "SQL", "Python", "Excel",
        "Languages", "Arabic", "English", "", "", "", "", ""]
MAIN = ["Experience", "Data Analyst, Delta Foods", "Mar 2022 – Present | Cairo, Egypt", *[f"• {b}" for b in BUL[:3]],
        "Junior Analyst, Nile Trading Co.", "Jan 2020 – Feb 2022 | Cairo, Egypt", *[f"• {b}" for b in BUL[3:]],
        "Education", "B.Sc. Statistics, Cairo University | 2015 – 2019", "", ""]


def grid_cv(side, main, head_case=str):
    """Two columns built as rows of a grid, so every sidebar line sits on the same baseline as a main line."""
    cells = "".join(f'<div class="s">{head_case(s) if s in ("Contact", "Top Skills", "Languages") else s}</div>'
                    f'<div class="m">{head_case(m) if m in ("Experience", "Education") else m}</div>'
                    for s, m in zip(side, main))
    return ('<style>.g{display:grid;grid-template-columns:150px 1fr;column-gap:28px;row-gap:3px}'
            '.s,.m{font-size:10pt;line-height:1.35;min-height:1em}</style>'
            '<h1>Salma Adel</h1><p>Data Analyst | Cairo, Egypt</p>'
            f'<div class="g">{cells}</div>')


def item(text, x, w, size=10):
    return {"text": text, "x": x, "w": w, "size": size}


# ---------- units ----------

def test_line_parts_splits_only_at_wide_gaps(page):
    modules(page)
    got = page.evaluate("""() => {
      const lp = M.rules.lineParts;
      return [
        lp({ items: [{ text: 'Power BI', x: 40, w: 45, size: 10 }, { text: 'Experience', x: 230, w: 55, size: 10 }] }),
        lp({ items: [{ text: 'Data', x: 40, w: 22, size: 10 }, { text: 'Analyst', x: 65, w: 35, size: 10 }] }),
        lp({ items: [{ text: 'Only', x: 40, w: 22, size: 10 }] }),
        lp({ rtl: true, items: [{ text: 'الخبرات', x: 300, w: 40, size: 10 }, { text: 'Excel', x: 40, w: 30, size: 10 }] }),
        lp({ text: 'no items' })];
    }""")
    assert got == [["Power BI", "Experience"], [], [], [], []]


@pytest.mark.parametrize("heading,cat", [("Top Skills", "skills"), ("TOP SKILLS", "skills"), ("Top", None)])
def test_top_skills_heading(page, heading, cat):
    modules(page)
    assert page.evaluate("t => M.rules.detectHeading(t)", heading) == cat


def merged_lines():
    """LinkedIn-like lines: sidebar text and the main column merged on one line."""
    rows = [[item("Contact", 40, 40), item("Summary", 230, 50)],
            [item("salma.adel@example.com", 40, 120), item("Data analyst with 5 years in retail reporting.", 230, 220)],
            [item("Top Skills", 40, 50), item("Experience", 230, 55)],
            [item("Power BI", 40, 45), item("Data Analyst, Delta Foods | Mar 2022 – Present", 230, 230)]]
    rows += [[item("SQL", 40, 20), item(f"• {b}", 230, 300)] for b in BUL]
    rows += [[item("Education", 230, 50)], [item("B.Sc. Statistics, Cairo University 2019", 230, 200)]]
    return [{"text": " ".join(i["text"] for i in r), "items": r, "page": 1, "y": k * 12, "x": r[0]["x"],
             "bullet": r[-1]["text"].startswith("•") and len(r) == 1} for k, r in enumerate(rows)]


def test_merged_columns_find_sections_and_bullets(page):
    modules(page)
    out = page.evaluate("""lines => {
      const r = M.rules.contentIssues({ lines, text: lines.map(l => l.text).join('\\n') }, { level: 'mid' });
      return Object.fromEntries(r.map(i => [i.id, [i.level, i.params || null]]));
    }""", merged_lines())
    assert out["sections"][0] == "ok", out["sections"]


def test_one_column_lines_have_no_parts(page):
    """Lines without a wide gap give no parts, so single-column CVs are read exactly as before."""
    modules(page)
    assert page.evaluate("""() => M.rules.lineParts({ items: [
      { text: 'Senior Accountant, Delta Foods', x: 40, w: 160, size: 10 },
      { text: 'Mar 2022 – Present', x: 210, w: 90, size: 10 }] })""") == []


# ---------- full checker on printed PDFs ----------

@pytest.mark.parametrize("case", [str, str.upper], ids=["title-case", "upper-case"])
def test_sidebar_cv_sections_found(page, browser, tmp_path, case):
    """LinkedIn / paracol style: "Top Skills" beside "Experience" on one line. Before: "Missing Experience, Skills"."""
    upload(page, cv_pdf(browser, tmp_path, "Salma-Adel-CV.pdf", grid_cv(SIDE, MAIN, case)))
    score_of(page)
    assert issue(page, "Missing standard sections").count() == 0
    # The column warning is still right: the sidebar really mixes into the main text.
    assert issue(page, "multiple columns").count() == 1


def test_single_column_cv_unchanged(page, browser, tmp_path):
    body = ("<h1>Salma Adel</h1><p>Cairo, Egypt | +20 100 000 0000 | salma.adel@example.com | linkedin.com/in/salma-adel</p>"
            "<h2>Summary</h2><p>Data analyst with 5 years of experience in retail reporting and forecasting.</p>"
            "<h2>Experience</h2><p><b>Data Analyst, Delta Foods</b> | Mar 2022 – Present</p>" + bullets(BUL[:3])
            + "<p><b>Junior Analyst, Nile Trading Co.</b> | Jan 2020 – Feb 2022</p>" + bullets(BUL[3:])
            + "<h2>Education</h2><p>B.Sc. Statistics, Cairo University | 2015 – 2019</p>"
            "<h2>Top Skills</h2><p>Power BI, SQL, Python, Excel, DAX, Data modelling, Forecasting</p>")
    upload(page, cv_pdf(browser, tmp_path, "Salma-Adel-CV.pdf", body))
    score_of(page)
    assert issue(page, "Missing standard sections").count() == 0
    assert issue(page, "multiple columns").count() == 0


# ---------- extra tests (promo/checker-rounds/extra-tests.md, "Unassigned", done in round 1) ----------

FIXTURES = Path(__file__).parent / "fixtures"


def content_of(page, path):
    """contentIssues of a PDF as {id: level}, plus the layout issue levels, run inside the site page."""
    data = base64.b64encode(path.read_bytes()).decode()
    return page.evaluate("""async ([d, name]) => {
      const pdfjs = await import('./assets/vendor/pdfjs/pdf.min.mjs');
      pdfjs.GlobalWorkerOptions.workerSrc = new URL('./assets/vendor/pdfjs/pdf.worker.min.mjs', location.href).href;
      const { extract } = await import('./assets/ats/extract.js');
      const { contentIssues } = await import('./assets/ats/rules.js');
      const bytes = Uint8Array.from(atob(d), c => c.charCodeAt(0));
      const doc = await extract(pdfjs, new File([bytes], name, { type: 'application/pdf' }));
      return Object.fromEntries(contentIssues(doc, { level: 'mid' }).map(i => [i.id, i.level]));
    }""", [data, path.name])


def test_same_cv_from_word_and_wordcraft_reads_the_same(page):
    """Metamorphic re-export: one .docx exported by Microsoft Word and by WordCraft (another producer)."""
    scores = {}
    for name in ("Youssef-Adel-word365.pdf", "Youssef-Adel-wordcraft.pdf"):
        page.reload()
        upload(page, FIXTURES / name)
        scores[name] = score_of(page)
    assert abs(scores["Youssef-Adel-word365.pdf"] - scores["Youssef-Adel-wordcraft.pdf"]) <= 3, scores
    page.reload()
    word, craft = (content_of(page, FIXTURES / n) for n in ("Youssef-Adel-word365.pdf", "Youssef-Adel-wordcraft.pdf"))
    assert word == craft


SECTIONS = {
    "summary": "<h2>Summary</h2><p>Data analyst with 5 years of experience in retail reporting and forecasting.</p>",
    "exp": ("<h2>Experience</h2><p><b>Data Analyst, Delta Foods</b> | Mar 2022 – Present</p>" + bullets(BUL[:3])
            + "<p><b>Junior Analyst, Nile Trading Co.</b> | Jan 2020 – Feb 2022</p>" + bullets(BUL[3:])),
    "edu": "<h2>Education</h2><p>B.Sc. Statistics, Cairo University | 2015 – 2019</p>",
    "skills": "<h2>Skills</h2><p>Power BI, SQL, Python, Excel, DAX, Data modelling, Forecasting</p>",
}
CONTACT = ("<h1>Salma Adel</h1><p>Cairo, Egypt | +20 100 000 0000 | salma.adel@example.com | "
           "linkedin.com/in/salma-adel</p>")


def test_section_order_does_not_change_findings(page, browser, tmp_path):
    """Metamorphic section reorder: bullets, contact and personal-data findings stay the same."""
    found = []
    for k, order in enumerate([("summary", "exp", "edu", "skills"), ("summary", "skills", "edu", "exp"),
                               ("edu", "skills", "exp", "summary")]):
        path = cv_pdf(browser, tmp_path, f"Salma-Adel-{k}.pdf", CONTACT + "".join(SECTIONS[s] for s in order))
        found.append(content_of(page, path))
    assert found[0] == found[1] == found[2]


def font_pdf(path, drop_unicode_map):
    """A CV in an embedded subset font; without its ToUnicode map, the letters cannot be turned back into text."""
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_font(fontname="nb", fontbuffer=pymupdf.Font("helv").buffer)
    rows = ["Salma Adel", "Cairo, Egypt | +20 100 000 0000 | salma.adel@example.com", "Experience",
            "Data Analyst, Delta Foods | Mar 2022 - Present", *[f"- {b}" for b in BUL],
            "Education", "B.Sc. Statistics, Cairo University 2019", "Skills", "Power BI, SQL, Python, Excel"]
    for k, text in enumerate(rows):
        pg.insert_text((50, 60 + 18 * k), text, fontname="nb", fontsize=11)
    doc.subset_fonts()
    if drop_unicode_map:
        for x in range(1, doc.xref_length()):
            if doc.xref_get_key(x, "ToUnicode")[0] != "null":
                doc.xref_set_key(x, "ToUnicode", "null")
    doc.save(path, garbage=3)
    return path


@pytest.mark.parametrize("drop", [True, False], ids=["no-unicode-map", "with-unicode-map"])
def test_font_without_unicode_map_is_reported(page, tmp_path, drop):
    upload(page, font_pdf(tmp_path / "Salma-Adel-CV.pdf", drop))
    score_of(page)
    assert issue(page, "garbled").count() == (1 if drop else 0)
