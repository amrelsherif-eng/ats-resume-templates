"""Build browser-exported ATS corpus PDFs in a pytest temporary directory."""
from __future__ import annotations

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image


BASE_BULLETS = [
    "Designed a reporting pipeline that reconciled 42,000 monthly records with 99.8% accuracy",
    "Automated invoice review and reduced quarterly close time by 31% across 6 teams",
    "Led migration of 18 services to a monitored cloud platform with 99.95% availability",
    "Built forecasting dashboards used by 24 managers to plan $2.4M in annual spending",
    "Improved onboarding workflow and cut average customer setup from 9 days to 4 days",
    "Analyzed 3 years of usage data and identified $180K in annual operating savings",
    "Implemented access controls for 12 applications and closed 27 audit findings",
    "Mentored 5 analysts and delivered 14 executive reviews on schedule each quarter",
]

# Page 2 of multi-page CVs gets its own lines: a real CV never repeats page 1 word for word.
PROJECT_BULLETS = [
    "Shipped an open-source log parser that processes 2 GB per minute on a single core",
    "Cut CI pipeline time from 22 to 9 minutes by caching builds across 40 repositories",
    "Wrote a capacity model that kept 3 data centers under 70% load through peak season",
    "Presented 6 internal talks on observability, attended by 300+ engineers in total",
    "Rebuilt the billing export in Go and lowered memory use by 64% at the same throughput",
    "Coordinated a 4-team incident review program that reduced repeat outages by 45%",
    "Designed an on-call handbook adopted by 11 teams within one quarter of release",
    "Prototyped a search service that answered 95% of queries in under 120 ms",
]


def _html(name="Sara Ahmed", heading="Work Experience", font="Arial", pages=1,
          bullet="•", table=False, photo=False, columns=False, positioned=False,
          arabic=False, ligatures=False, student=False, icon_font=False):
    if arabic:
        name = "سارة أحمد"
        contact = "sara@example.com | +20 100 000 0000 | القاهرة، مصر | linkedin.com/in/sara"
        headings = ["الخبرة المهنية", "التعليم", "المهارات"]
        content = [
            "مهندسة برمجيات أولى، شركة المثال، 2020 حتى الآن",
            *["• طورت أنظمة لخدمة آلاف العملاء وتحسين الأداء والجودة" for _ in range(9)],
        ]
    else:
        contact = "sara.ahmed@example.com | +20 100 000 0000 | Cairo, Egypt | linkedin.com/in/sara-ahmed | github.com/sara"
        if student:
            headings = ["Projects", "Education", "Technical Skills"]
            content = ["Software Engineering Student, Example University, 2026"] + [
                f"{bullet} {line}" for line in BASE_BULLETS
            ]
        else:
            headings = [heading, "Education", "Technical Skills"]
            content = ["Senior Software Engineer, Example Systems, Jan 2020 - Present"] + [
                f"{bullet} {line}" for line in BASE_BULLETS
            ]

    if ligatures:
        content[1] = content[1].replace("Designed", "Designed ﬁle ﬂow").replace(
            "monthly", "monthly\u00a0records"
        )

    if icon_font:
        contact_block = (
            # A Windows icon-font glyph plus common Canva-style symbols that Linux CI fonts can render too.
            '<p><span style="font-family:\'Segoe MDL2 Assets\'">&#xE700;</span> &#x2709; &#x260E; &#x2605; | '
            f"{contact}</p>"
        )
    elif table:
        contact_block = f"<table><tr><td>{contact}</td></tr></table>"
    else:
        contact_block = f"<p>{contact}</p>"

    if positioned:
        entries = [name, contact, *headings, *content]
        body = '<div class="positioned">' + "".join(
            f'<div style="left:{(i % 3) * 170}px;top:{(i // 3) * 48}px">{text}</div>'
            for i, text in enumerate(entries)
        ) + "</div>"
    elif columns:
        body = (
            f"<header><h1>{name}</h1><p>{contact}</p></header>"
            '<div class="grid"><aside><h2>Contact</h2>'
            f"<p>{contact}</p><h2>Technical Skills</h2><p>Python SQL AWS Linux</p></aside>"
            f"<main><h2>{heading}</h2>{''.join(f'<p>{b}</p>' for b in content[1:])}"
            "<h2>Education</h2><p>BSc Example University</p></main></div>"
        )
    else:
        photo_tag = (
            '<img class="photo" src="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' '
            'width=\'48\' height=\'48\'%3E%3Ccircle cx=\'24\' cy=\'24\' r=\'24\' fill=\'%23abc\'/%3E%3C/svg%3E">'
            if photo else ""
        )
        sections = (
            f"<h2>{headings[0]}</h2>{''.join(f'<p>{line}</p>' for line in content)}"
            f"<h2>{headings[1]}</h2><p>BSc Example University, 2016 - 2020</p>"
            f"<h2>{headings[2]}</h2><p>Python · TypeScript · SQL · AWS · Docker · Linux</p>"
        )
        body = f"<header>{photo_tag}<h1>{name}</h1>{contact_block}</header>{sections}"

    extra_pages = "".join(
        '<div style="break-before:page"><h2>Selected Projects</h2>'
        + "".join(f"<p>{bullet} {line}</p>" for line in PROJECT_BULLETS)
        + "</div>"
        for _ in range(max(0, pages - 1))
    )
    direction = ' lang="ar" dir="rtl"' if arabic else ' lang="en"'
    return f"""<!doctype html><html{direction}><head><meta charset="utf-8"><style>
      @page {{ size:A4; margin:17mm 19mm }} * {{ box-sizing:border-box }}
      body {{ font:10pt {font}, sans-serif; color:#17212b; line-height:1.32 }}
      h1 {{font-size:22pt;margin:0 0 5px}}
      h2 {{font-size:12pt;margin:14px 0 4px;border-bottom:1px solid #789;padding-bottom:2px}}
      p {{margin:3px 0}} table {{width:100%;border-collapse:collapse}} td {{padding:2px}}
      .photo {{width:48px;height:48px;float:right}}
      .grid {{display:grid;grid-template-columns:28% 68%;gap:4%}} aside {{background:#eee;padding:10px}}
      .positioned {{position:relative;height:950px}}
      .positioned > div {{position:absolute;width:150px}}
    </style></head><body>{body}{extra_pages}</body></html>"""


def generate(tmp_path: Path, browser) -> dict[str, Path]:
    """Generate all fixtures; HTML resumes are printed by the configured browser."""
    paths: dict[str, Path] = {}

    def export(key, **opts):
        path = tmp_path / f"{key}.pdf"
        page = browser.new_page()
        try:
            page.set_content(_html(**opts), wait_until="load")
            page.pdf(path=str(path), format="A4", print_background=True)
        finally:
            page.close()
        paths[key] = path

    export("good_calibri", font="Calibri")
    export("good_arial", font="Arial", heading="Work History", bullet="–")
    export("good_times", font="'Times New Roman'", heading="Professional Experience", bullet="-")
    export("good_georgia_table", font="Georgia", heading="Employment History", table=True, bullet="▪")
    export("good_student", name="Mina Hassan", student=True, bullet="➢")
    export("good_arabic_name", name="يوسف محمود", heading="Experience")
    export("good_photo", name="Nadia Saleh", photo=True)
    export("good_senior_two_page", name="Layla Morgan", pages=2)
    export("good_ligatures_nbsp", name="Noor Rahman", ligatures=True)
    export("bad_two_column", columns=True)
    export("bad_positioned", positioned=True)
    export("bad_icon_font", name="Icon Font Candidate", icon_font=True)
    export("bad_arabic", arabic=True)
    export("bad_four_page", name="Junior Candidate", pages=4)

    source = pymupdf.open(paths["good_calibri"])
    image = source[0].get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6), alpha=False)
    scanned = pymupdf.open()
    scanned_page = scanned.new_page(width=595, height=842)
    scanned_page.insert_image(scanned_page.rect, stream=image.tobytes("png"))
    out = tmp_path / "bad_scanned.pdf"
    scanned.save(out)
    scanned.close()
    source.close()
    paths["bad_scanned"] = out

    no_text = tmp_path / "bad_no_text.pdf"
    empty = pymupdf.open()
    empty.new_page()
    empty.save(no_text)
    empty.close()
    paths["bad_no_text"] = no_text

    encrypted = tmp_path / "bad_encrypted.pdf"
    protected = pymupdf.open()
    protected_page = protected.new_page()
    protected_page.insert_text((60, 60), "Confidential resume text " * 30)
    protected.save(
        encrypted,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="reader-secret",
    )
    protected.close()
    paths["bad_encrypted"] = encrypted

    raw = random.Random(731).randbytes(2600 * 2100 * 3)
    image = Image.frombytes("RGB", (2600, 2100), raw)
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=0)
    large = tmp_path / "bad_15mb.pdf"
    large_doc = pymupdf.open()
    large_page = large_doc.new_page()
    large_page.insert_image(large_page.rect, stream=stream.getvalue())
    large_page.insert_text((60, 60), "A large resume PDF.")
    large_doc.save(large, garbage=0, deflate=False)
    large_doc.close()
    paths["bad_15mb"] = large

    corrupt = tmp_path / "bad_truncated.pdf"
    corrupt.write_bytes(paths["good_calibri"].read_bytes()[:180])
    paths["bad_truncated"] = corrupt
    return paths
