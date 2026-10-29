"""Checker judgments on realistic CVs from many fields, printed to PDF by the browser (like online builders).
Each case is a GOOD CV that used to get a wrong warning, plus the weak cases that must still be caught."""
import re

import pytest
from playwright.sync_api import expect

from conftest import score_of, upload

STYLE = """<style>@page{size:A4;margin:14mm} body{font:10pt/1.4 Arial,sans-serif;margin:0}
h1{font-size:20pt;margin:0} h2{font-size:11pt;margin:12px 0 4px;text-transform:uppercase}
p{margin:2px 0} .b{padding-left:14px;text-indent:-10px;margin:2px 0}</style>"""


def cv_pdf(browser, tmp_path, name, body, lang="en"):
    page = browser.new_page()
    direction = "rtl" if lang == "ar" else "ltr"
    page.set_content(f'<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">{STYLE}</head><body>{body}</body></html>')
    path = tmp_path / name
    page.pdf(path=str(path), format="A4", print_background=True)
    page.close()
    return path


def bullets(lines):
    return "".join(f'<p class="b">• {line}</p>' for line in lines)


HEADER = ("<h1>Mariam Fathy</h1><p>Cairo, Egypt | +20 100 000 0000 | mariam.fathy@example.com | "
          "linkedin.com/in/mariam-fathy</p>")


def issue(page, text):
    """A reported problem (not a passed check) whose title matches text."""
    return page.locator("#chk-out .issue:not(.ok)", has_text=re.compile(text, re.I))


def test_arabic_cv_reads_in_order_and_is_not_flagged(page, browser, tmp_path):
    body = ("<h1>أحمد محمود عبدالسلام</h1><p>الإسكندرية، مصر | ٠١٠٠٠٠٠٠٠٠٠ | ahmed.mahmoud@example.com</p>"
            "<h2>الخبرات العملية</h2><p>مهندس موقع، شركة دلتا للمقاولات</p><p>مايو ٢٠٢٢ – حتى الآن | الإسكندرية</p>"
            + bullets(["أشرف على تنفيذ مبنى إداري من ٨ طوابق ونسق الأعمال اليومية بين ٤ مقاولين متخصصين",
                       "راجع الرسومات التنفيذية وحصر الكميات قبل بدء الأعمال مما خفض إعادة التنفيذ بنسبة ١٨٪",
                       "أعد تقارير أسبوعية عن نسب الإنجاز والمخاطر وناقشها مع مدير المشروع والاستشاري"] * 2)
            + "<h2>التعليم</h2><p>بكالوريوس الهندسة المدنية، جامعة الإسكندرية، ٢٠٢٠</p>"
            "<h2>المهارات</h2><p>أوتوكاد، بريمافيرا، إدارة المواقع، حصر الكميات، ضبط الجودة، السلامة المهنية</p>"
            "<h2>الدورات التدريبية</h2><p>إدارة المشروعات الاحترافية، السلامة والصحة المهنية في مواقع البناء</p>")
    upload(page, cv_pdf(browser, tmp_path, "Ahmed-Mahmoud-CV.pdf", body, lang="ar"))
    assert score_of(page) >= 90
    # Right-aligned Arabic lines are one column, its headings are sections, its city and phone are found.
    expect(issue(page, "multiple columns")).to_have_count(0)
    expect(issue(page, "Missing standard sections")).to_have_count(0)
    expect(issue(page, "No city or region")).to_have_count(0)
    expect(issue(page, "No phone number")).to_have_count(0)
    # "The text an ATS sees" is real Arabic in reading order, not reversed letter shapes.
    seen = page.locator("#chk-out .chk-text pre").text_content()
    assert "الخبرات العملية" in seen and "أحمد محمود عبدالسلام" in seen
    assert not re.search(r"[ﭐ-﷿ﹰ-﻿]", seen)


def test_teacher_cv_with_teaching_experience_heading(page, browser, tmp_path):
    body = (HEADER + "<h2>Teaching Experience</h2><p>English Teacher, Nile International School</p>"
            "<p>Sept 2021 – Present | Cairo, Egypt</p>"
            + bullets(["Teach 5 classes of grade 10 students and raised the pass rate from 78% to 91%",
                       "Design weekly lesson plans for 140 students using reading circles and short quizzes",
                       "Mentor 3 new teachers through monthly class visits and written feedback"])
            + "<h2>Education</h2><p>BA in English Literature, Cairo University, June 2019</p>"
            "<h2>Certifications</h2><p>CELTA, Cambridge English, 2020</p><h2>Skills</h2>"
            "<p>Classroom management, curriculum design, Google Classroom, assessment design, parent communication</p>")
    upload(page, cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", body))
    assert score_of(page) >= 95
    expect(issue(page, "Missing standard sections")).to_have_count(0)
    expect(page.locator("#chk-out .issue.ok", has_text="quantified impact")).to_have_count(1)
    expect(page.locator("#chk-out .issue.ok", has_text="Strong action verbs start")).to_have_count(1)
    # AP style (Sept, June) is one date style, not a mix.
    expect(issue(page, "Mixed date formats")).to_have_count(0)


@pytest.mark.parametrize("heading", ["Clinical Experience", "Internships", "Graduation Project", "PROFESSIONAL EXPERIENCE"])
def test_common_section_headings_are_recognised(page, browser, tmp_path, heading):
    body = (HEADER + f"<h2>{heading}</h2><p>Nursing Intern, Kasr Al Ainy Hospital</p><p>Jan 2024 – Dec 2024</p>"
            + bullets(["Provided bedside care to 12 patients per shift in a 30-bed surgical ward",
                       "Supported the charge nurse with medication rounds for 2 wards each day",
                       "Educated 40 families on wound care before discharge with printed guides"])
            + "<h2>Education</h2><p>BSc in Nursing, Cairo University, 2024</p>"
            "<h2>Licenses &amp; Certifications</h2><p>Registered Nurse, Egyptian Nursing Syndicate</p>"
            "<h2>Skills</h2><p>Patient assessment, IV therapy, infection control, vital signs, Arabic and English</p>")
    upload(page, cv_pdf(browser, tmp_path, "Mariam-Fathy-CV.pdf", body))
    score_of(page)
    expect(issue(page, "Missing standard sections")).to_have_count(0)
    # Nursing verbs (Provided, Supported, Educated) are action verbs.
    expect(page.locator("#chk-out .issue.ok", has_text="Strong action verbs start")).to_have_count(1)


def test_technical_terms_are_not_pronouns_or_buzzwords(page, browser, tmp_path):
    body = (HEADER + "<h2>Experience</h2><p>Embedded Engineer, Delta Devices</p><p>Mar 2022 – Present</p>"
            + bullets(["Integrated I/O expansion boards over SPI and I2C for 3 industrial controllers",
                       "Practiced dynamic programming and graph problems, solving 300 contest problems",
                       "Cut boot time of the GPIO driver from 900 ms to 350 ms on 2 product lines",
                       "Led ME & Africa field tests with 4 distributors and 12 pilot sites"])
            + "<h2>Education</h2><p>BSc Electronics and Communications, Ain Shams University, 2021</p>"
            "<h2>Skills</h2><p>C, C++, FreeRTOS, UART, SPI, I2C, oscilloscopes, logic analyzers, Git</p>")
    upload(page, cv_pdf(browser, tmp_path, "Hany-Atef-CV.pdf", body))
    score_of(page)
    expect(issue(page, "first-person pronouns")).to_have_count(0)
    expect(issue(page, "buzzwords")).to_have_count(0)


def test_wrapped_bullet_line_and_divider_are_read_correctly(page, browser, tmp_path):
    long = ("Streamlined the month-end close across the finance team by rebuilding the reconciliation workbook "
            "and checklists, which cut the close from 8 working days to 5")
    body = (HEADER + "<p>────────────────────────────</p><h2>Experience</h2><p>Senior Accountant, Delta Trading</p>"
            "<p>Mar 2022 – Present</p>" + bullets([long, "Reconciled 14 bank accounts every month with zero open items"])
            + "<h2>Education</h2><p>BCom, Cairo University, 2019</p><h2>Skills</h2><p>Excel, SAP, Power BI, IFRS</p>")
    upload(page, cv_pdf(browser, tmp_path, "Omar-Nabil-CV.pdf", body))
    score_of(page)
    # The number is on the wrapped second line: it still counts for that bullet.
    expect(page.locator("#chk-out .issue.ok", has_text="100% of bullet points feature quantified")).to_have_count(1)
    # A divider line is not garbled text.
    expect(issue(page, "garbled")).to_have_count(0)


def test_weak_cv_is_still_caught(page, browser, tmp_path):
    body = (HEADER + "<h2>Experience</h2><p>Office Assistant, Example Co</p><p>Jan 2023 – Present</p>"
            + bullets(["Responsible for answering calls and helping visitors at the front desk",
                       "Worked on filing papers and making copies for the office team",
                       "I helped the office manager with different tasks when needed"])
            + "<h2>Education</h2><p>Diploma of Commerce, 2022</p><h2>Skills</h2><p>Hard-working team player, MS Office</p>")
    upload(page, cv_pdf(browser, tmp_path, "Peter-Sameh-CV.pdf", body))
    assert score_of(page) < 80
    for text in ["passive openers", "first-person pronouns", "buzzwords", "begin with an action verb"]:
        expect(issue(page, text).first).to_be_visible()
