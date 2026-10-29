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
