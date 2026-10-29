"""Build the GitHub Pages site into _site/.

Copies the static site, the five templates (PDF, .tex, previews), creates WebP
previews, and vendors pdf.js from node_modules (npm ci in site/ first).
Usage: python site/build.py [out_dir] [base_path]
base_path is where the site is served from: "/" on Cloudflare Pages (default),
"/ats-resume-templates/" on GitHub Pages. It is used by 404.html, which can be
served from any URL depth and so needs absolute paths.
"""
import re
import shutil
import subprocess
import sys
import html
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
BASE = sys.argv[2] if len(sys.argv) > 2 else "/"
TEMPLATES = ["software-web", "business-finance", "network-cloud", "embedded-ece", "mobile-apps"]
PDFJS = SITE / "node_modules" / "pdfjs-dist" / "build"
FONTSOURCE = SITE / "node_modules" / "@fontsource"
# Self-hosted fonts (no third-party requests): package -> CSS files to include.
FONTS = {
    "space-grotesk": ["latin-400", "latin-500", "latin-700"],
    "jetbrains-mono": ["latin-400", "latin-500"],
    "ibm-plex-sans-arabic": ["arabic-400", "arabic-500", "arabic-700"],
}


ARABIC_RANGE = "U+0600-06FF, U+0750-077F, U+0870-08FF, U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, U+FE70-FE74, U+FE76-FEFC"
SITE_URL = "https://amrelsherif-eng.github.io/ats-resume-templates/"


def build_arabic_page():
    """Render Arabic strings into a copy of the built English document."""
    script = ("const fs=require('fs'),vm=require('vm'); const c={}; "
              "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8')+"
              "'\\nglobalThis.__translations=JSON.stringify({EN,AR});',c); "
              "process.stdout.write(c.__translations);")
    result = subprocess.run(["node", "-e", script, str(OUT / "assets" / "i18n.js")],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    ar = json.loads(result.stdout)["AR"]
    source = (OUT / "index.html").read_text(encoding="utf-8")

    # Preserve the original markup and replace only inner content on elements whose source is text-only.
    pattern = re.compile(r'(<([A-Za-z][\w:-]*)\b[^>]*\bdata-i="([^"]+)"[^>]*>)(.*?)(</\2\s*>)', re.S)
    def replace_text(m):
        key = m.group(3)
        if key not in ar:
            raise ValueError(f"Missing Arabic translation for data-i key: {key}")
        value = ar[key]
        return m.group(1) + (value if "<" in value or ">" in value else html.escape(value)) + m.group(5)
    source = pattern.sub(replace_text, source)

    def replace_attr(match):
        tag, key = match.group(0), match.group(1)
        if key not in ar:
            raise ValueError(f"Missing Arabic translation for data-i-aria key: {key}")
        label = html.escape(ar[key], quote=True)
        return re.sub(r'\baria-label="[^"]*"', f'aria-label="{label}"', tag)
    source = re.sub(r'<[^>]*\bdata-i-aria="([^"]+)"[^>]*>', replace_attr, source)
    source = source.replace('<html lang="en" dir="ltr">', '<html lang="ar" dir="rtl" data-prerendered="ar">')
    # Arabic text is visible at first paint here, so fetch its font with the page (no swap, no layout shift).
    preload = "".join(
        f'<link rel="preload" href="assets/fonts/ibm-plex-sans-arabic-arabic-{w}-normal.woff2" as="font" type="font/woff2" crossorigin>' + "\n"
        for w in ("400", "500", "700"))
    source = source.replace('<link rel="stylesheet" href="assets/fonts.css">', preload + '<link rel="stylesheet" href="assets/fonts.css">', 1)
    source = re.sub(r'<title>.*?</title>', f'<title>{html.escape(ar["meta.title"])}</title>', source, count=1, flags=re.S)
    source = re.sub(r'(<meta name="description" content=")[^"]*(">)', r'\g<1>' + html.escape(ar["meta.desc"], quote=True) + r'\2', source, count=1)
    source = re.sub(r'(<meta property="og:title" content=")[^"]*(">)', r'\g<1>' + html.escape(ar["meta.title"], quote=True) + r'\2', source, count=1)
    source = re.sub(r'(<meta property="og:description" content=")[^"]*(">)', r'\g<1>' + html.escape(ar["meta.desc"], quote=True) + r'\2', source, count=1)
    source = source.replace('<meta property="og:type"', '<meta property="og:locale" content="ar_EG">\n<meta property="og:type"', 1)
    source = source.replace(f'<link rel="canonical" href="{SITE_URL}">',
                            f'<link rel="canonical" href="{SITE_URL}ar.html">')
    source = source.replace(f'<meta property="og:url" content="{SITE_URL}">',
                            f'<meta property="og:url" content="{SITE_URL}ar.html">')
    source = re.sub(r'<button\b[^>]*\bid="lang"[^>]*>.*?</button>',
                    '<button class="btn sm lang" id="lang" type="button" lang="en" aria-label="Switch to English">English</button>',
                    source, count=1, flags=re.S)
    (OUT / "ar.html").write_text(source, encoding="utf-8")


def add_english_alternates():
    page = OUT / "index.html"
    source = page.read_text(encoding="utf-8")
    alternates = (f'<link rel="alternate" hreflang="en" href="{SITE_URL}">\n'
                  f'<link rel="alternate" hreflang="ar" href="{SITE_URL}ar.html">\n'
                  f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}">')
    source = source.replace(f'<link rel="canonical" href="{SITE_URL}">',
                            f'<link rel="canonical" href="{SITE_URL}">\n{alternates}', 1)
    page.write_text(source, encoding="utf-8")


def update_sitemap():
    path = OUT / "sitemap.xml"
    source = path.read_text(encoding="utf-8")
    entry = f'  <url><loc>{SITE_URL}ar.html</loc><changefreq>monthly</changefreq></url>\n'
    source = source.replace('</urlset>', entry + '</urlset>')
    path.write_text(source, encoding="utf-8")


def build_fonts():
    """Copy the WOFF2 files and write assets/fonts.css pointing at them."""
    out_dir = OUT / "assets" / "fonts"
    out_dir.mkdir(parents=True)
    css = ["/* Generated by build.py from @fontsource packages (OFL licensed). */"]
    for pkg, subsets in FONTS.items():
        for subset in subsets:
            rule = (FONTSOURCE / pkg / f"{subset}.css").read_text(encoding="utf-8")
            woff2 = re.search(r"url\(\./files/([^)]+\.woff2)\)", rule).group(1)
            shutil.copy2(FONTSOURCE / pkg / "files" / woff2, out_dir / woff2)
            rule = re.sub(r"src:[^;]+;", f"src: url(fonts/{woff2}) format('woff2');", rule)
            if "arabic" in woff2 and "unicode-range" not in rule:
                # Without a range, symbols missing from Space Grotesk (✓ · ↗) pull this font on English pages.
                rule = rule.replace("font-display:", f"unicode-range: {ARABIC_RANGE};\n  font-display:", 1)
            css.append(rule.strip())
    (OUT / "assets" / "fonts.css").write_text("\n".join(css) + "\n", encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT, ignore=shutil.ignore_patterns(
        "node_modules", "tests", "build.py", "package*.json", "__pycache__", ".gitignore"))
    for t in TEMPLATES:
        src, dst = ROOT / "templates" / t, OUT / "templates" / t
        dst.mkdir(parents=True)
        for name in ("resume.pdf", "resume.tex", "preview.png"):
            shutil.copy2(src / name, dst / name)
        img = Image.open(src / "preview.png").convert("RGB")
        img.save(dst / "preview.webp", "WEBP", quality=82, method=6)
        img.resize((400, round(400 * img.height / img.width)), Image.LANCZOS).save(
            dst / "preview-400.webp", "WEBP", quality=78, method=6)
        img.resize((640, round(640 * img.height / img.width)), Image.LANCZOS).save(
            dst / "preview-640.webp", "WEBP", quality=80, method=6)
    vendor = OUT / "assets" / "vendor" / "pdfjs"
    vendor.mkdir(parents=True)
    for name in ("pdf.min.mjs", "pdf.worker.min.mjs"):
        shutil.copy2(PDFJS / name, vendor / name)
    build_fonts()
    add_english_alternates()
    build_arabic_page()
    update_sitemap()
    page = OUT / "404.html"
    page.write_text(page.read_text(encoding="utf-8").replace("{{BASE}}", BASE), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
