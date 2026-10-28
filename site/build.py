"""Build the GitHub Pages site into _site/.

Copies the static site, the five templates (PDF, .tex, previews), creates WebP
previews, and vendors pdf.js from node_modules (npm ci in site/ first).
Usage: python site/build.py [out_dir]
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
TEMPLATES = ["software-web", "business-finance", "network-cloud", "embedded-ece", "mobile-apps"]
PDFJS = SITE / "node_modules" / "pdfjs-dist" / "build"


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
        img.resize((640, round(640 * img.height / img.width)), Image.LANCZOS).save(
            dst / "preview-640.webp", "WEBP", quality=80, method=6)
    vendor = OUT / "assets" / "vendor" / "pdfjs"
    vendor.mkdir(parents=True)
    for name in ("pdf.min.mjs", "pdf.worker.min.mjs"):
        shutil.copy2(PDFJS / name, vendor / name)
    (OUT / ".nojekyll").write_text("")
    print(f"built {OUT}")


if __name__ == "__main__":
    main()
