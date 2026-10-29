import mimetypes
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_IDS = ["software-web", "business-finance", "network-cloud", "embedded-ece", "mobile-apps"]
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
LIVE_URL = os.environ.get("SITE_URL", "").rstrip("/")
if LIVE_URL:
    ALLOWED_HOSTS.add(urlparse(LIVE_URL).hostname)
CHECK_TIMEOUT = 30_000
NO_OVERFLOW = "document.documentElement.scrollWidth <= document.documentElement.clientWidth && Math.abs(window.scrollX) < 1"


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

        # Byte ranges, like GitHub Pages: browsers need them to seek in a video without downloading all of it.
        def send_head(self):
            rng = self.headers.get("Range", "")
            path = Path(self.translate_path(self.path))
            if not rng.startswith("bytes=") or not path.is_file():
                return super().send_head()
            size = path.stat().st_size
            first, _, last = rng[6:].split(",")[0].partition("-")
            try:
                start = int(first) if first else max(0, size - int(last))
                end = min(int(last), size - 1) if first and last else size - 1
            except ValueError:
                return super().send_head()
            if start >= size or start > end:
                self.send_error(416)
                return None
            f = path.open("rb")
            f.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self._range_left = end - start + 1
            return f

        def copyfile(self, source, outputfile):
            left = getattr(self, "_range_left", None)
            if left is None:
                return super().copyfile(source, outputfile)
            self._range_left = None
            while left > 0:
                chunk = source.read(min(64 * 1024, left))
                if not chunk:
                    break
                outputfile.write(chunk)
                left -= len(chunk)

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
    # Reduced motion keeps clicks deterministic (scroll reveals move sections for ~0.6 s).
    page = browser.new_page(reduced_motion="reduce")
    if LIVE_URL:
        page.set_default_timeout(20_000)
    errors = []
    page_errors = []
    blocked_hosts = []

    def record(message):
        text = str(message)
        if "Content Security Policy" in text or "Refused" in text or "error" in text.lower():
            errors.append(text)

    page.on("console", lambda message: record(message.text) if message.type == "error" or "Content Security Policy" in message.text or "Refused" in message.text else None)
    page.on("pageerror", lambda error: (record(error), page_errors.append(str(error))))

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
    page._site_page_errors = page_errors
    page._blocked_hosts = blocked_hosts
    yield page
    page.close()


def assert_no_browser_errors(page):
    assert not page._blocked_hosts, f"Requests to disallowed hosts: {page._blocked_hosts}"
    assert not page._site_errors, "Browser errors: " + "\n".join(page._site_errors)


def assert_checker_did_not_crash(page):
    assert not page._blocked_hosts, f"Requests to disallowed hosts: {page._blocked_hosts}"
    assert not page._site_page_errors, "Uncaught browser errors: " + "\n".join(page._site_page_errors)


def upload(page, file_path):
    page.locator("#chk-file").set_input_files(str(file_path))


def score_of(page):
    expect(page.locator("#chk-out .ring-n")).to_be_visible(timeout=CHECK_TIMEOUT)
    return int(page.locator("#chk-out .ring-n").text_content())
