# Third-Party Notices

_Last updated: 2026-06-21_

NISB is built with the help of many open-source projects.

This file provides high-level notices for third-party software used by NISB. It is not a complete dependency license report and is not legal advice.

---

## Important notice

NISB itself is licensed under the GNU Affero General Public License v3.0 for open-source use, with commercial licensing available separately.

Third-party dependencies are not owned by the NISB copyright holder.

Their original authors, copyright notices, license texts, and terms remain in effect.

A NISB commercial license does not automatically grant commercial, proprietary, hosted, embedded, SaaS, redistribution, patent, trademark, API, model-provider, infrastructure, or other special rights for third-party dependencies or third-party services.

Users and organizations are responsible for reviewing third-party dependency licenses for their own use cases.

---

## Python dependencies

NISB may use Python packages including, but not limited to:

- `requests`
- `python-dateutil`
- `jieba`
- `newspaper3k`
- `httpx`
- `lxml`
- `lxml_html_clean`
- `beautifulsoup4`
- `openai`
- `anthropic`
- `numpy`
- `pandas`
- `networkx`
- `RestrictedPython`
- `jupyter-client`
- `psutil`
- `matplotlib`
- `pdfplumber`
- `pypdf`
- `pymupdf4llm`
- `reportlab`
- `python-docx`
- `mammoth`
- `html2text`
- `pptx2md`
- `pyyaml`
- `faiss-cpu`
- `fastapi`
- `uvicorn`
- `pydantic`
- `feedparser`
- `apscheduler`

Please refer to the corresponding package metadata and upstream repositories for exact license terms.

---

## JavaScript / frontend dependencies

NISB Web may use JavaScript packages including, but not limited to:

- `@codemirror/commands`
- `@codemirror/lang-markdown`
- `@codemirror/language`
- `@codemirror/state`
- `@codemirror/view`
- `codemirror`
- `dompurify`
- `echarts`
- `epubjs`
- `jszip`
- `marked`
- `pinia`
- `vue`
- `vue-i18n`
- `vue-router`
- `@vitejs/plugin-vue`
- `@vue/test-utils`
- `jsdom`
- `terser`
- `vite`
- `vitest`

Please refer to the corresponding package metadata and upstream repositories for exact license terms.

---

## System packages

NISB Docker images or deployment environments may include system packages such as:

- Debian or Ubuntu base packages
- Python runtime packages
- Node.js runtime packages
- LibreOffice components
- Font packages
- OpenBLAS or BLAS-related libraries
- Docker Engine or container runtime components
- XML, image, compression, and build libraries

These packages are distributed under their respective upstream licenses.

---

## API and service dependencies

NISB may integrate with external APIs or services, depending on user configuration, including:

- OpenAI
- Anthropic
- DeepSeek
- Serper
- Exa
- arXiv
- Crossref
- Open Library
- Wikidata
- Wikipedia
- News APIs
- Pexels
- Pixabay
- NASA APIs
- Semantic Scholar

Use of external services is subject to their own terms, policies, API limits, data-processing rules, and licensing requirements.

Using NISB does not grant access to third-party services beyond the providers' own terms.

---

## Special licensing attention

Some dependencies may have stronger license obligations or commercial licensing considerations.

### PyMuPDF / MuPDF / pymupdf4llm

PyMuPDF / MuPDF and pymupdf4llm require special attention.

They are commonly distributed under a dual licensing model:

1. AGPL for open-source use.
2. Upstream commercial licensing for commercial or proprietary use cases.

The AGPLv3 open-source version of NISB may use these dependencies under their open-source license terms.

However, commercial, proprietary, closed-source, SaaS, hosted, embedded, or redistributed versions of NISB that include PyMuPDF / MuPDF / pymupdf4llm functionality may require a separate upstream commercial license or another compliant packaging strategy.

A NISB commercial license does not automatically grant commercial rights to PyMuPDF, MuPDF, pymupdf4llm, Artifex software, or any other third-party dependency.

See `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`.

### html2text

NISB may use `html2text` for HTML-to-text or HTML-to-Markdown conversion workflows.

`html2text` is commonly distributed under GPL-3.0-or-later terms.

The AGPLv3 open-source version of NISB may use GPLv3-compatible dependencies when the applicable license obligations are met.

However, commercial, proprietary, closed-source, SaaS, hosted, embedded, or redistributed versions of NISB that include `html2text` functionality may require a compliant packaging strategy, such as disabling the feature, replacing the dependency, or requiring the end user to install and comply with the dependency separately.

A NISB commercial license does not automatically relicense `html2text` or grant non-GPL commercial rights for it.

See `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`.

### DOMPurify

NISB Web may use DOMPurify for sanitizing HTML content.

DOMPurify has its own license terms and notices.

Frontend redistributions should preserve applicable notices from the package metadata and upstream project.

### Document processing packages

NISB may use multiple document-processing packages for PDF, DOCX, Office, EPUB, Markdown, HTML, and text conversion workflows.

Commercial users should review the licenses of all document-processing packages used in their deployment, especially where documents are processed as part of a hosted service, redistributed product, embedded product, or closed-source integration.

---

## Generated license reports

For release builds, maintainers should generate dependency license reports where possible.

Suggested output files:

- `THIRD_PARTY_LICENSES_PYTHON.md`
- `THIRD_PARTY_LICENSES_NPM.md`
- `THIRD_PARTY_LICENSES_SYSTEM.md`

These generated reports may be updated from time to time and should be treated as informational compliance aids, not as a replacement for upstream license texts.

### Python dependencies

For Python dependencies, you may use `pip-licenses`:

```bash
python -m pip install pip-licenses
pip-licenses --format=markdown --with-authors --with-urls > THIRD_PARTY_LICENSES_PYTHON.md
```

### npm dependencies

For npm dependencies, you may use `license-checker`:

```bash
cd nisb-web
npx license-checker --production --markdown > ../THIRD_PARTY_LICENSES_NPM.md
```

Review generated output manually before publishing.

---

## Thanks

NISB exists because of the open-source ecosystem.

Thank you to the maintainers and contributors of all upstream projects that make self-hosted AI, document processing, web applications, and developer tooling possible.

---

## No legal advice

This file is provided for project transparency.

It is not legal advice.
