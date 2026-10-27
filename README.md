<div align="center">

```
╔════════════════════════════════════════════════════════╗
║  ██████╗ ███████╗███████╗██╗   ██╗███╗   ███╗███████╗  ║
║  ██╔══██╗██╔════╝██╔════╝██║   ██║████╗ ████║██╔════╝  ║
║  ██████╔╝█████╗  ███████╗██║   ██║██╔████╔██║█████╗    ║
║  ██╔══██╗██╔══╝  ╚════██║██║   ██║██║╚██╔╝██║██╔══╝    ║
║  ██║  ██║███████╗███████║╚██████╔╝██║ ╚═╝ ██║███████╗  ║
║  ╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝  ║
╚════════════════════════════════════════════════════════╝
```

# ⚡ Software Engineer Resume Template

**Minimalist · ATS-Optimized · One-Page · LaTeX**  
*Built for Software Engineers · Mobile Developers · Tech Juniors*

---

[![License: MIT](https://img.shields.io/badge/License-MIT-cyan?style=for-the-badge&logo=opensourceinitiative&logoColor=black)](https://opensource.org/licenses/MIT)
[![Language: LaTeX](https://img.shields.io/badge/Language-LaTeX-blueviolet?style=for-the-badge&logo=latex&logoColor=white)](https://www.latex-project.org/)
[![ATS Friendly](https://img.shields.io/badge/ATS-Friendly%20✓-00ffcc?style=for-the-badge&logo=checkmarx&logoColor=black)](https://github.com/amrelsherif-eng/software-engineer-resume-template)
[![One Page](https://img.shields.io/badge/Layout-One--Page-ff79c6?style=for-the-badge&logo=readthedocs&logoColor=black)](https://github.com/amrelsherif-eng/software-engineer-resume-template)

</div>

---

## 🧠 Why This Template?

> The average recruiter spends **6 seconds** scanning a resume. Most templates fail tech juniors before they get a callback.

| Challenge | This Template's Solution |
|:---|:---|
| 📄 Resume too long | Strict one-page layout with calibrated margins |
| 🤖 ATS fails to parse it | `pdfgentounicode=1` + `hidelinks` hyperref config |
| 🔍 Low keyword density | Section order optimized for technical keyword prominence |
| 🎨 Overdesigned layouts | Clean typographic hierarchy — no columns, no icons, no noise |
| 🧩 Hard to customize | Modular macro system — swap content without touching structure |

---

## ☁️ Option A — Online Setup · `Zero-Config` · *Recommended*

> **No installation. No compiler. No setup.** Edit and compile entirely in your browser via Overleaf.

<div align="center">

[![Open in Overleaf](https://img.shields.io/badge/Open%20in%20Overleaf-%E2%86%92%20View%20Template-47A141?style=for-the-badge&logo=overleaf&logoColor=white)](https://www.overleaf.com/read/wxvvcdjzxnng#d23995)

</div>

> ⚠️ **The link above is READ-ONLY.** You cannot edit my project directly. Follow one of the two steps below to get your own editable copy.

---

### ✅ Method 1 — Copy Project (Fastest)

> **Prerequisite:** You must have a free [Overleaf account](https://www.overleaf.com/register) and be **logged in** before opening the link.

1. **Open** the Overleaf link above.
2. In the **top-left menu bar**, click **`File`**.
3. Select **`Make a copy`** from the dropdown.
4. A **"Copy project"** dialog will appear — rename the project if you like, then click the green **`Copy`** button.
5. Overleaf clones the full template into your account. Hit **Recompile** and start editing `resume.tex`. ✓

---

### ✅ Method 2 — Blank Project + Paste

1. Create a **New Blank Project** on [overleaf.com](https://www.overleaf.com).
2. Open [`resume.tex`](./resume.tex) in this repository and **copy the full raw source**.
3. **Paste** it into the `main.tex` file of your blank Overleaf project.
4. Hit **Recompile** — done. ✓

---

> [!TIP]
> **Don't know LaTeX? Let AI do the heavy lifting.**
>
> Copy the full contents of `resume.tex`, then paste it into **Gemini**, **ChatGPT**, or **Claude** with a prompt like:
>
> *"Update this LaTeX resume template with my information: [paste your details here]"*
>
> The AI will instantly fill in your name, experience, skills, and projects — no LaTeX knowledge required. Just paste the output back into Overleaf and recompile.

---

## ✨ Key Features

- **`[01]` One-Page Layout** — Margins, spacing, and padding are mathematically tuned to maximize content density on exactly one page.
- **`[02]` Flawless ATS Parsing** — `\pdfgentounicode=1` ensures machine-readable glyphs. Single-column flow is parseable by Greenhouse, Lever, Workday, and all major ATS engines.
- **`[03]` Clean Code Architecture** — Reusable macros (`\resumeItem`, `\resumeSubheading`, `\resumeProjectHeading`), annotated section markers, zero redundant packages.
- **`[04]` Easy Customization** — Content lives in clearly labeled blocks. Swap your info without touching the structure.

```
%-----------HEADING-----------     ← Name, title, contacts
%-----------SUMMARY-----------     ← Professional summary
%-----------TECHNICAL SKILLS---    ← Skills
%-----------PROJECTS-----------    ← Projects
%-----------WORK EXPERIENCE----    ← Experience
%-----------EDUCATION----------    ← Degree(s)
%-----------CERTIFICATIONS-----    ← Certs & courses
%-----------LEADERSHIP---------    ← Volunteering
%-----------SOFT SKILLS--------    ← Soft skills & languages
```

---

## 🖥️ Option B — Local Setup · `Advanced`

For offline editing with full IDE features (IntelliSense, SyncTeX, live PDF preview).

### Prerequisites

| Tool | Purpose |
|:---|:---|
| [VS Code](https://code.visualstudio.com/) | Editor / IDE |
| [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) | VS Code extension — build, preview, SyncTeX |
| [MiKTeX](https://miktex.org/download) | LaTeX compiler + auto package manager |
| [Strawberry Perl](https://strawberryperl.com/) | Required by the `latexmk` build tool |

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/amrelsherif-eng/software-engineer-resume-template.git
cd software-engineer-resume-template

# 2. Open in VS Code
code .
```

- Install **MiKTeX** → during setup, set missing packages to **"Install on-the-fly → Always"**
- Install **Strawberry Perl** → verify with `perl --version`
- Install the **LaTeX Workshop** extension in VS Code

```
Ctrl+Alt+B  →  Build PDF
Ctrl+Alt+V  →  Open PDF preview
```

> On first build, MiKTeX auto-downloads any missing packages. Requires an internet connection.

### Recommended `settings.json`

```jsonc
{
  "latex-workshop.view.pdf.viewer": "tab",
  "latex-workshop.latex.autoBuild.run": "onSave"
}
```

---

## 📁 Project Structure

```
software-engineer-resume-template/
├── resume.tex     ← Source file (edit this)
├── resume.pdf     ← Compiled output
├── .gitignore     ← Ignores LaTeX aux files
└── README.md
```

---

## 📜 License & Credits

Released under the **MIT License** — free to use, modify, and distribute.

```
MIT License © 2026 Amr Fathy Elsherif
```

> This template is **heavily customized and optimized** by **Amr Fathy Elsherif**, built upon the original open-source base by [**sb2nov**](https://github.com/sb2nov/resume) (MIT License).

---

<div align="center">

**Amr Fathy Elsherif** · Network & Cloud Infrastructure

[![GitHub](https://img.shields.io/badge/GitHub-amrelsherif--eng-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/amrelsherif-eng)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-amrelsherif--eng-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/amrelsherif-eng)
[![Portfolio](https://img.shields.io/badge/Portfolio-amrelsherif--eng.vercel.app-0e7490?style=for-the-badge&logo=vercel&logoColor=white)](https://amrelsherif-eng.vercel.app)

*If this template helped you, a ⭐ on the repo helps others find it.*

</div>
