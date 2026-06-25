# Release Checklist

Use this checklist before publishing NISB to GitHub.

## Repository Safety

- [ ] Do not publish `/opt/mcp-gateway` directly.
- [ ] Create a clean release directory.
- [ ] Remove `backups/`.
- [ ] Remove `logs/`.
- [ ] Remove `__pycache__/`.
- [ ] Remove `.pyc` files.
- [ ] Remove `.env` files.
- [ ] Remove real API keys.
- [ ] Remove tokens.
- [ ] Remove private domain names if needed.
- [ ] Remove user data.
- [ ] Remove uploaded private documents.
- [ ] Remove generated caches.
- [ ] Remove temporary files.
- [ ] Remove old manual backups.

## Required Files

- [ ] `README.md`
- [ ] `LICENSE`
- [ ] `DUAL-LICENSE.md`
- [ ] `COMMERCIAL-LICENSE.md`
- [ ] `CONTRIBUTING.md`
- [ ] `CLA.md`
- [ ] `SECURITY.md`
- [ ] `SUPPORT.md`
- [ ] `THIRD_PARTY_NOTICES.md`
- [ ] `ACKNOWLEDGEMENTS.md`
- [ ] `NOTICE`
- [ ] `.gitignore`

## GitHub Files

- [ ] `.github/pull_request_template.md`
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] `.github/ISSUE_TEMPLATE/question.md`
- [ ] `.github/ISSUE_TEMPLATE/config.yml`

## License and Dependency Review

- [ ] Confirm AGPLv3 license text is present.
- [ ] Confirm dual licensing is described.
- [ ] Confirm contribution terms are described.
- [ ] Confirm third-party notices are present.
- [ ] Generate Python dependency license report if possible.
- [ ] Generate npm dependency license report if possible.
- [ ] Review PyMuPDF / MuPDF licensing implications.
- [ ] Review Docker image and system package notices.

## MCP Claims

- [ ] If MCP standardization is complete, document exact supported flows.
- [ ] If MCP standardization is incomplete, mark it as roadmap.
- [ ] Do not describe federation/share-ref compatibility as completed standard MCP unless verified.

## Final Smoke Test

- [ ] Fresh clone works.
- [ ] Docker build works.
- [ ] Backend starts.
- [ ] Frontend starts.
- [ ] Login works.
- [ ] Basic chat works.
- [ ] Room creation works.
- [ ] Library upload works.
- [ ] RAG query works.
- [ ] Existing stable features are not broken.

