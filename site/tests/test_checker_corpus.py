"""End-to-end regression corpus for the in-browser ATS checker."""
import pytest
import pymupdf
from playwright.sync_api import expect

from conftest import (
    CHECK_TIMEOUT,
    assert_checker_did_not_crash,
    assert_no_browser_errors,
    score_of,
    upload,
)
from corpus_gen import generate


@pytest.fixture(scope="module")
def corpus(browser, tmp_path_factory):
    return generate(tmp_path_factory.mktemp("ats-corpus"), browser)


GOOD = [
    "good_calibri",
    "good_arial",
    "good_times",
    "good_georgia_table",
    "good_student",
    "good_arabic_name",
    "good_photo",
    "good_ligatures_nbsp",
]


def test_generated_documents_have_expected_page_count_and_ligatures(corpus):
    for case, expected_pages in [
        ("good_student", 1),
        ("good_senior_two_page", 2),
        ("bad_four_page", 4),
    ]:
        with pymupdf.open(corpus[case]) as pdf:
            assert pdf.page_count == expected_pages, case

    with pymupdf.open(corpus["good_ligatures_nbsp"]) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
    assert "\ufb01" in text and "\ufb02" in text
    assert "\u00a0" in text


@pytest.mark.parametrize("case", GOOD)
def test_good_resume_has_no_false_positive_failures(page, corpus, case):
    upload(page, corpus[case])
    assert score_of(page) >= 85, case
    expect(page.locator("#chk-out .issue.fail")).to_have_count(0)
    assert_no_browser_errors(page)


def test_two_page_senior_cv_is_accepted_at_senior_level(page, corpus):
    page.locator('#chk-level input[value="senior"]').check(force=True)
    upload(page, corpus["good_senior_two_page"])
    assert score_of(page) >= 85
    expect(page.locator("#chk-out .issue.fail")).to_have_count(0)
    expect(page.locator("#chk-out .passed .issue.ok", has_text="2 page")).to_have_count(1)
    assert_no_browser_errors(page)


@pytest.mark.parametrize(
    ("case", "level", "expected_text", "experience_level"),
    [
        ("bad_two_column", "warn", "column", None),
        ("bad_positioned", "warn", "column", None),
        ("bad_icon_font", "warn", "Decorative symbols", None),
        ("bad_scanned", "fail", "selectable text", None),
        ("bad_arabic", "info", "Arabic", None),
        ("bad_four_page", "fail", "pages:", "junior"),
        ("bad_no_text", "fail", "selectable text", None),
        ("bad_15mb", "warn", "large", None),
    ],
)
def test_readable_edge_cases_report_expected_issue(
    page, corpus, case, level, expected_text, experience_level
):
    if experience_level:
        page.locator(f'#chk-level input[value="{experience_level}"]').check(force=True)
    if case == "bad_15mb":
        size = corpus[case].stat().st_size
        assert 15 * 1024 * 1024 < size < 25 * 1024 * 1024, size

    upload(page, corpus[case])
    score_of(page)
    expect(
        page.locator(f"#chk-out .issue.{level}", has_text=expected_text)
    ).to_have_count(1, timeout=CHECK_TIMEOUT)
    assert_checker_did_not_crash(page)


@pytest.mark.parametrize("case", ["bad_encrypted", "bad_truncated"])
def test_unreadable_pdf_has_clear_error_and_does_not_crash(page, corpus, case):
    upload(page, corpus[case])
    error = page.locator("#chk-out .chk-error")
    expect(error).to_be_visible(timeout=CHECK_TIMEOUT)
    expect(error).to_contain_text("Could not read this file")
    assert_checker_did_not_crash(page)


def make_text_pdf(path, lines, right_column=None):
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    for i, text in enumerate(lines):
        y = 60 + i * 15
        pdf_page.insert_text((60, y), text, fontsize=9)
        if right_column and i in right_column:
            pdf_page.insert_text((510, y), right_column[i], fontsize=9)
    doc.save(path)
    doc.close()
    return path


def test_achievement_checks_ignore_non_experience_sections(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Education", "- Responsible for completing advanced coursework every semester",
        "Certifications", "- Helped prepare cloud certification materials for colleagues",
        "Languages", "- Responsible for communicating fluently in English and Arabic",
        "Interests", "- Helped organize community events across the city",
        "Skills", "- Responsible for Python, SQL, Docker, Kubernetes and AWS",
        "- Responsible for Python, SQL, Docker, Kubernetes and AWS",
        "Experience",
        "- Designed reliable data services for 12 regional teams",
        "- Improved release workflows and reduced delays by 30%",
        "- Led platform migration for 8 production applications",
        "Projects", "- Built automated reporting tools used by 25 analysts",
    ]
    upload(page, make_text_pdf(tmp_path / "section-scope.pdf", lines))
    score_of(page)
    for text in ["Strong action verbs", "quantified impact", "unique"]:
        expect(page.locator("#chk-out .issue.ok", has_text=text)).to_have_count(1)
    expect(page.locator("#chk-out .issue", has_text="passive openers")).to_have_count(0)


def test_labeled_numeric_opener_is_excluded_from_verb_rate(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Experience",
        "- Backend: 30% increase in throughput across 4 regions",
        "- Designed secure services for 12 business teams",
        "- Led migration of 8 production applications",
    ]
    upload(page, make_text_pdf(tmp_path / "labeled-number.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="Strong action verbs start 100%")).to_have_count(1)


def test_british_action_verb_spellings_are_accepted(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Experience", "- Analysed 12 datasets for monthly planning",
        "- Organised 8 teams around the quarterly release",
        "- Optimised 30 workflows for faster reporting",
        "- Modelled 25 scenarios for capacity planning",
        "- Travelled to 6 offices to lead implementation",
    ]
    upload(page, make_text_pdf(tmp_path / "british-verbs.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="Strong action verbs start 100%")).to_have_count(1)


def test_fallback_ignores_job_metadata_lines(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Experience", "Senior Software Engineer | Example Systems | 06/22 - 08/24",
        "Product Engineer | Acme Labs | Remote",
        "Backend Engineer, Example Co, 2022-06 - 2024-08",
        "Designed reliable services for 12 regional teams every quarter",
        "Improved release workflows and reduced delays by 30%",
        "Led platform migration for 8 production applications",
        "Skills", "Python SQL Docker AWS Kubernetes Linux",
    ]
    upload(page, make_text_pdf(tmp_path / "fallback-metadata.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="Strong action verbs start 100%")).to_have_count(1)


def test_numeric_right_aligned_date_ranges_are_not_column_content(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Designed reliable services for regional teams",
        "Led migration projects across production systems",
        "Built reporting tools for business operations",
        "Improved release workflows for engineering teams",
    ]
    dates = {2: "06/22", 3: "06/2022", 4: "2022-06", 5: "06/22 - 09/24"}
    upload(page, make_text_pdf(tmp_path / "numeric-date-column.pdf", lines, dates))
    score_of(page)
    expect(page.locator("#chk-out .issue.warn", has_text="column")).to_have_count(0)
    expect(page.locator("#chk-out .issue.ok", has_text="Single-column layout")).to_have_count(1)


def test_duplicate_checks_ignore_labels_and_short_lines(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Experience",
        "- Tech stack: Python SQL Git AWS Docker Kubernetes",
        "- Tech stack: Python SQL Git AWS Docker Kubernetes",
        "- Built useful tools",
        "- Built useful tools",
        "- Designed secure services for 12 teams",
        "- Improved release workflows by 30%",
    ]
    upload(page, make_text_pdf(tmp_path / "duplicate-exclusions.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="Every bullet point is unique")).to_have_count(1)


def test_weak_openers_are_warning_only(page, tmp_path):
    lines = [
        "Sara Ahmed", "sara@example.com | +20 100 123 4567 | Cairo, Egypt",
        "Experience",
        "- Responsible for supporting 12 regional teams each month",
        "- Responsible for maintaining 8 production applications",
        "- Responsible for coordinating 6 quarterly releases",
    ]
    upload(page, make_text_pdf(tmp_path / "weak-openers.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.warn", has_text="passive openers")).to_have_count(1)
    expect(page.locator("#chk-out .issue.fail", has_text="passive openers")).to_have_count(0)


@pytest.mark.parametrize(
    "phone",
    [
        "+20 100 123 4567",
        "+201001234567",
        "010-1234-5678",
        "01012345678",
        "(+20) 10 1234 5678",
    ],
)
def test_egyptian_mobile_phone_formats_are_detected(page, tmp_path, phone):
    lines = [
        "Sara Ahmed", f"sara@example.com | {phone} | Cairo, Egypt",
        "Experience", "- Designed reliable services for 12 regional teams",
    ]
    upload(page, make_text_pdf(tmp_path / "egyptian-phone.pdf", lines))
    score_of(page)
    expect(page.locator("#chk-out .issue.ok", has_text="Phone number detected")).to_have_count(1)
    expect(page.locator("#chk-out .issue.warn", has_text="No phone number detected")).to_have_count(0)


def test_unrecognised_section_heading_still_checks_bullets(page, tmp_path):
    # "Internships" is not a known heading: weak bullets under it must still be flagged.
    from test_site import make_pdf
    lines = ["Omar Hassan", "omar@example.com | +20 111 222 3333 | Giza, Egypt", "Internships"] + [
        f"- Responsible for helping users with printer problem number {n} in the office" for n in range(6)
    ] + ["Education", "BSc, Example University, 2025"]
    upload(page, make_pdf(tmp_path / "internships.pdf", 1, lines))
    score_of(page)
    expect(page.locator("#chk-out .issue", has_text="passive openers").first).to_be_visible()
