# Commercial Third-Party Dependencies

NISB is available under AGPLv3 for open-source use, with commercial licensing available separately.

This document explains how third-party dependencies are handled in commercial licensing.

---

## Important Principle

A NISB commercial license only covers rights that the NISB maintainer owns or is legally able to license.

A NISB commercial license does not automatically grant commercial, proprietary, closed-source, SaaS, redistribution, patent, trademark, API, model-provider, infrastructure, or other special rights for third-party software, services, models, providers, or platforms.

Third-party dependencies remain governed by their own licenses.

Third-party services remain governed by their own terms.

Commercial users are responsible for reviewing third-party dependency licenses and third-party service terms for their own deployment, redistribution, hosted service, embedded product, proprietary integration, or enterprise use case.

---

## High-Attention Dependency: PyMuPDF / pymupdf4llm

NISB may use PyMuPDF, MuPDF, and/or pymupdf4llm for PDF, document-processing, RAG, or LLM-oriented document conversion workflows.

PyMuPDF / MuPDF and pymupdf4llm require special attention because they are commonly distributed under an AGPL/commercial licensing model.

This means that PyMuPDF / MuPDF / pymupdf4llm may be compatible with the AGPLv3 open-source version of NISB, but may require separate upstream commercial licensing or another compliant packaging strategy for proprietary, closed-source, hosted, embedded, SaaS, or commercial redistribution scenarios.

A NISB commercial license does not automatically grant commercial rights to PyMuPDF, MuPDF, pymupdf4llm, Artifex software, or any other third-party dependency.

---

## What This Means for PyMuPDF / pymupdf4llm Users

If your commercial use of NISB includes PyMuPDF / MuPDF / pymupdf4llm functionality, you are responsible for ensuring that your use of those dependencies complies with their upstream licenses.

Depending on your use case, this may require:

- Using NISB under AGPLv3-compatible terms.
- Obtaining a commercial license from Artifex or the relevant upstream rights holder.
- Disabling PyMuPDF / MuPDF / pymupdf4llm-based features.
- Replacing PyMuPDF / MuPDF / pymupdf4llm with an alternative dependency.
- Using a deployment where the relevant dependency is installed and licensed separately by the end user.
- Using a separate commercial packaging strategy that excludes the relevant dependency.

---

## High-Attention Dependency: html2text

NISB may use `html2text` for HTML-to-text or HTML-to-Markdown conversion workflows.

`html2text` is commonly distributed under GPL-3.0-or-later terms.

This may be compatible with the AGPLv3 open-source version of NISB when the applicable license obligations are met.

However, a NISB commercial license does not automatically grant non-GPL commercial, proprietary, closed-source, SaaS, hosted, embedded, or redistribution rights for `html2text`.

If a commercial deployment or commercial distribution includes `html2text` functionality, the customer, distributor, or operator is responsible for ensuring compliance with the applicable upstream license terms.

Depending on the use case, this may require:

- Using NISB under AGPLv3-compatible terms.
- Disabling `html2text`-based features.
- Replacing `html2text` with a permissively licensed alternative.
- Requiring the customer or end user to install and comply with `html2text` separately.
- Using a separate commercial packaging strategy that excludes GPL-only or GPL-family dependencies where necessary.

---

## Commercial License Scope

Unless explicitly stated in a separate written agreement, a NISB commercial license does not include:

- Artifex commercial licenses.
- PyMuPDF commercial licenses.
- pymupdf4llm commercial licenses.
- MuPDF commercial licenses.
- Commercial rights for `html2text`.
- Commercial rights for any third-party dependency.
- API provider subscriptions.
- Model provider subscriptions.
- Cloud infrastructure fees.
- Patent licenses from third parties.
- Trademark rights from third parties.
- Rights to third-party names, logos, marks, APIs, datasets, models, or hosted services.

---

## Optional Packaging Strategy

Commercial NISB distributions may choose one of several approaches:

1. Include only dependencies that are compatible with the intended commercial distribution.
2. Make high-attention dependencies optional.
3. Disable features that require high-attention dependencies.
4. Require the customer to install and license specific dependencies separately.
5. Replace high-attention dependencies with alternatives.
6. Provide a separate commercial agreement that explicitly addresses third-party licensing.
7. Provide a separate commercial build profile that excludes GPL-only, AGPL, or other strong-copyleft dependencies where necessary.

---

## External API and Service Dependencies

NISB may integrate with external APIs or services depending on user configuration.

Examples may include OpenAI, Anthropic, DeepSeek, Serper, Exa, arXiv, Crossref, Open Library, Wikidata, Wikipedia, news providers, Pexels, Pixabay, NASA APIs, and Semantic Scholar.

A NISB commercial license does not include subscriptions, credits, API keys, usage rights, data rights, model rights, scraping rights, redistribution rights, or commercial permissions for third-party services.

Commercial users must comply with each provider's own terms, acceptable-use policies, rate limits, data-processing rules, and licensing requirements.

---

## Other Third-Party Dependencies

Other dependencies may also have license, notice, attribution, patent, trademark, export-control, data-use, service-use, or commercial-use terms.

NISB users and commercial customers are responsible for reviewing the license terms of all third-party dependencies used in their deployment.

See:

- `THIRD_PARTY_NOTICES.md`
- `THIRD_PARTY_LICENSES_PYTHON.md`
- `THIRD_PARTY_LICENSES_NPM.md`

---

## No Legal Advice

This document is provided for project transparency.

It is not legal advice.

Commercial users should review third-party license obligations with their own legal counsel before redistribution, hosted service operation, proprietary integration, enterprise deployment, or commercial product use.
