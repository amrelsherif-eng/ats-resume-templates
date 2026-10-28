import mimetypes
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_IDS = ["software-web", "business-finance", "network-cloud", "embedded-ece", "mobile-apps"]
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "fonts.googleapis.com", "fonts.gstatic.com"}
# Set SITE_URL (e.g. https://ats-resume-templates.pages.dev) to run the same suite against the live site.
LIVE_URL = os.environ.get("SITE_URL", "").rstrip("/")
if LIVE_URL:
    ALLOWED_HOSTS.add(urlparse(LIVE_URL).hostname)


@pytest.fixture(scope="session")
def site_url():
    if LIVE_URL:
        yield LIVE_URL
        return
    mimetypes.add_type("text/javascript", ".mjs")
    site_dir = Path(os.environ.get("SITE_DIR", "_site"))
    if not site_dir.is_absolute():
        site_dir = ROOT / site_dir

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()
    server.server_close()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL") or None)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, site_url):
    page = browser.new_page()
    if LIVE_URL:  # real networks are slower than the local server
        page.set_default_timeout(20_000)
    errors = []
    blocked_hosts = []

    def record(message):
        text = str(message)
        if "Content Security Policy" in text or "Refused" in text or "error" in text.lower():
            errors.append(text)

    page.on("console", lambda message: record(message.text) if message.type == "error" or "Content Security Policy" in message.text or "Refused" in message.text else None)
    page.on("pageerror", record)

    def restrict(route):
        host = (urlparse(route.request.url).hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            blocked_hosts.append(route.request.url)
            route.abort()
        else:
            route.continue_()

    page.route("**/*", restrict)
    page.goto(site_url, wait_until="networkidle", timeout=60_000 if LIVE_URL else 30_000)
    page._site_errors = errors
    page._blocked_hosts = blocked_hosts
    yield page
    page.close()


def assert_no_browser_errors(page):
    assert not page._blocked_hosts, f"Requests to disallowed hosts: {page._blocked_hosts}"
    assert not page._site_errors, "Browser errors: " + "\n".join(page._site_errors)


# clientWidth, not innerWidth: innerWidth grows with the overflow it should catch.
NO_OVERFLOW = "document.documentElement.scrollWidth <= document.documentElement.clientWidth && Math.abs(window.scrollX) < 1"


def test_loads_without_errors(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    expect(page).to_have_title(re.compile("ATS Resume Templates"))
    page.wait_for_load_state("networkidle")
    assert_no_browser_errors(page)


@pytest.mark.parametrize("width", [320, 375, 768, 1024, 1440])
def test_no_horizontal_overflow(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    assert page.evaluate(NO_OVERFLOW)
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    assert page.evaluate(NO_OVERFLOW)


def test_template_cards(page):
    cards = page.locator("#grid .card:not(.request)")
    expect(cards).to_have_count(5)
    for template_id in TEMPLATE_IDS:
        card = page.locator(f'#grid .card[data-g]:has(.tag:text-is("{template_id}"))')
        overleaf = card.get_by_role("link", name="Open in Overleaf")
        href = overleaf.get_attribute("href")
        raw_path = f"https://raw.githubusercontent.com/amrelsherif-eng/ats-resume-templates/main/templates/{template_id}/resume.tex"
        assert href.startswith("https://www.overleaf.com/docs?snip_uri=")
        assert quote(raw_path, safe="") in href
        expect(card.get_by_role("link", name="Preview")).to_have_attribute("href", re.compile("overleaf.com"))
        pdf = card.get_by_role("link", name="PDF", exact=True)
        response = page.request.get(f"{page.url.rsplit('/', 1)[0]}/{pdf.get_attribute('href')}")
        assert response.status == 200


def test_filters(page):
    for group, expected in [("biz", 1), ("eng", 2), ("sw", 2), ("all", 5)]:
        page.locator(f'.chip[data-f="{group}"]').click()
        expect(page.locator("#grid .card:not(.request):visible")).to_have_count(expected)
        expect(page.locator("#grid .card.request:visible")).to_have_count(1)


def test_language_switch(page):
    heading = page.locator("h1")
    english = heading.inner_text()
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    expect(page.locator("html")).to_have_attribute("lang", "ar")
    arabic = heading.inner_text()
    assert arabic != english and re.search(r"[\u0600-\u06ff]", arabic)
    page.reload(wait_until="networkidle")
    expect(page.locator("html")).to_have_attribute("lang", "ar")
    page.locator("#lang").click()
    expect(page.locator("html")).to_have_attribute("dir", "ltr")
    expect(page.locator("html")).to_have_attribute("lang", "en")


def test_tabs_keyboard(page):
    tabs = page.locator(".tab")
    tabs.first.focus()
    page.keyboard.press("ArrowRight")
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#p-ol")).to_be_visible()
    expect(page.locator("#p-ai")).to_be_hidden()
    expect(page.locator("#p-lc")).to_be_hidden()


def test_copy_prompt(page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("navigator.clipboard.writeText('')")  # the clipboard is shared between tests
    page.locator('#p-ai [data-copy="prompt"]').click()
    page.wait_for_function("navigator.clipboard.readText().then(t => t.startsWith('Fill this'))")
    assert page.evaluate("navigator.clipboard.readText()").startswith("Fill this LaTeX resume template")


def test_copy_for_ai(page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("navigator.clipboard.writeText('')")  # the clipboard is shared between tests
    page.locator('[data-ai="software-web"]').click()
    page.wait_for_function("navigator.clipboard.readText().then(t => t.includes('documentclass'))", timeout=15000)
    copied = page.evaluate("navigator.clipboard.readText()")
    assert "Fill this LaTeX resume template" in copied
    assert "\\documentclass" in copied


def upload(page, file_path):
    page.locator("#chk-file").set_input_files(str(file_path))


CHECK_TIMEOUT = 30_000  # the first check downloads pdf.js; allow for real networks


def score_of(page):
    expect(page.locator("#chk-out .ring-n")).to_be_visible(timeout=CHECK_TIMEOUT)
    return int(page.locator("#chk-out .ring-n").text_content())


def make_pdf(path, pages, lines_per_page):
    import pymupdf

    doc = pymupdf.open()
    for _ in range(pages):
        pdf_page = doc.new_page()
        for i, text in enumerate(lines_per_page):
            pdf_page.insert_text((60, 60 + i * 16), text, fontsize=10)
    doc.save(path)
    doc.close()
    return path


GOOD_LINES = [
    "Sara Ahmed", "sara@example.com | +20 100 000 0000 | Cairo, Egypt | linkedin.com/in/sara",
    "Education", "B.Com, Example University, Jun 2026",
    "Experience", "Finance Intern, Acme Co, Jun 2025 - Aug 2025",
] + [f"- Reconciled {n} bank accounts each month and cleared {n + 3} open items before close" for n in range(2, 20)] + [
    "Skills", "Excel, Power BI, SQL, SAP",
]


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_checker_scores_every_template_high(page, template_id):
    upload(page, ROOT / f"templates/{template_id}/resume.pdf")
    assert score_of(page) >= 90
    expect(page.locator("#chk-out .issue.fail")).to_have_count(0)
    page.locator("#chk-out details.chk-text").evaluate("d => d.open = true")
    expect(page.locator("#chk-out .chk-text pre")).to_contain_text("Your Name")
    assert_no_browser_errors(page)


def test_checker_page_rule_follows_experience(page, tmp_path):
    path = make_pdf(tmp_path / "two-pages.pdf", 2, GOOD_LINES)
    upload(page, path)
    score_of(page)
    pages_row = page.locator("#chk-out .issue", has_text=re.compile(r"\b2 pages"))
    expect(pages_row.first).to_have_class(re.compile(r"\bwarn\b"))
    page.locator('#chk-level input[value="senior"]').check(force=True)
    expect(page.locator("#chk-out .passed .issue.ok", has_text=re.compile(r"\b2 page"))).to_have_count(1)
    page.locator('#chk-level input[value="student"]').check(force=True)


def test_checker_scanned_like(page, tmp_path):
    import pymupdf

    path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    pdf_page.draw_rect(pymupdf.Rect(72, 72, 300, 300))
    doc.save(path)
    doc.close()
    upload(page, path)
    assert score_of(page) <= 25
    expect(page.locator("#chk-out .issue.fail").first).to_be_visible()


def test_checker_two_columns(page, tmp_path):
    import pymupdf

    path = tmp_path / "columns.pdf"
    doc = pymupdf.open()
    pdf_page = doc.new_page()
    left = ["CONTACT", "sara@example.com", "+20 100 000 0000", "Cairo, Egypt", "SKILLS", "Python", "SQL", "Excel"] * 3
    right = [f"- Built {n} Power BI dashboards for the regional sales team" for n in range(1, 25)]
    for i, t in enumerate(left):
        pdf_page.insert_text((40, 60 + i * 14), t, fontsize=9)
    for i, t in enumerate(right):
        pdf_page.insert_text((230, 60 + i * 14), t, fontsize=9)
    doc.save(path)
    doc.close()
    upload(page, path)
    score_of(page)
    expect(page.locator("#chk-out .issue.warn", has_text=re.compile("column", re.I))).to_have_count(1)


def test_checker_weak_content(page, tmp_path):
    lines = ["Omar Hassan", "omar@example.com | +20 111 222 3333 | Giza, Egypt", "Experience"] + [
        "- Responsible for helping users with computer problems in the office every day" for _ in range(8)
    ] + ["- I am a hard-working team player", "Education", "BSc, Example University", "Skills", "Windows"]
    upload(page, make_pdf(tmp_path / "weak.pdf", 1, lines))
    score_of(page)
    for pattern in ["passive openers", "pronouns", "buzzwords"]:
        expect(page.locator("#chk-out .issue", has_text=re.compile(pattern, re.I)).first).to_be_visible()


def test_checker_arabic_report(page):
    page.locator("#lang").click()
    upload(page, ROOT / "templates/network-cloud/resume.pdf")
    score_of(page)
    assert re.search(r"[؀-ۿ]", page.locator("#chk-out .chk-verdict").text_content())
    assert re.search(r"[؀-ۿ]", page.locator("#chk-out .passed .issue-t").first.text_content())


def test_checker_ai_prompt(page):
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    upload(page, ROOT / "templates/mobile-apps/resume.pdf")
    score_of(page)
    page.evaluate("navigator.clipboard.writeText('')")
    page.locator("#chk-out .chk-tools button").click()
    page.wait_for_function("navigator.clipboard.readText().then(t => t.includes('MY RESUME'))")


def test_checker_not_pdf(page, tmp_path):
    path = tmp_path / "not-really.pdf"
    path.write_text("this is plain text, not a PDF", encoding="utf-8")
    upload(page, path)
    expect(page.locator("#chk-out .chk-error")).to_be_visible(timeout=CHECK_TIMEOUT)
    assert not [e for e in page._site_errors if "Invalid PDF" not in e], page._site_errors


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_accessibility_axe(browser, site_url, lang):
    axe_path = os.environ.get("AXE_PATH")
    if not axe_path or not Path(axe_path).is_file():
        pytest.skip("Set AXE_PATH to axe.min.js to run the accessibility check")
    # axe is injected inline, so this check runs in its own context with CSP bypassed.
    context = browser.new_context(bypass_csp=True)
    page = context.new_page()
    page.goto(site_url, wait_until="networkidle", timeout=60_000 if LIVE_URL else 30_000)
    if lang == "ar":
        page.locator("#lang").click()
    page.add_script_tag(path=axe_path)
    violations = page.evaluate("""async () => {
      const result = await axe.run(document, {runOnly: ['wcag2a', 'wcag2aa']});
      return result.violations.filter(v => ['critical', 'serious'].includes(v.impact));
    }""")
    context.close()
    details = "\n".join(
        f"{v['id']}: {v['help']} ({len(v['nodes'])} nodes) e.g. {v['nodes'][0]['target']}" for v in violations)
    assert not violations, f"Serious accessibility violations:\n{details}"


def test_security_headers_meta(page):
    csp = page.locator('meta[http-equiv="Content-Security-Policy"]')
    expect(csp).to_have_count(1)
    content = csp.get_attribute("content")
    assert "script-src 'self'" in content
    assert "unsafe-inline" not in content and "unsafe-eval" not in content
    for link in page.locator('a[target="_blank"]').all():
        assert "noopener" in (link.get_attribute("rel") or "").split()



@pytest.mark.skipif(not LIVE_URL, reason="only meaningful against the deployed site")
def test_live_security_headers(page):
    headers = page.request.get(LIVE_URL + "/").headers
    for name in ["content-security-policy", "x-content-type-options", "x-frame-options",
                 "strict-transport-security", "referrer-policy", "permissions-policy"]:
        assert name in headers, f"missing header {name}"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_unknown_path_is_404(page, site_url):
    response = page.request.get(site_url + "/no-such-page-xyz")
    assert response.status == 404


def test_unconfigured_features_stay_hidden(page):
    # The support button and demo video show only when configured in app.js.
    expect(page.locator("#support")).to_be_hidden()
    expect(page.locator("#video")).to_be_hidden()
    assert page.locator("footer nav").first.evaluate("n => getComputedStyle(n).position") == "static"
