# Security Policy

Security matters should be reported privately.

Please do not report security vulnerabilities through public GitHub issues.

---

## Supported versions

During the early open-source stage, only the latest public release of NISB is actively supported for security review.

Older versions may not receive backported fixes.

Security fixes may be released as patches, commits, documentation updates, configuration guidance, or deployment recommendations depending on the issue.

---

## Reporting a vulnerability

Please report security vulnerabilities privately.

Preferred contact:

```text
security@nisb.me
```

If GitHub private vulnerability reporting is enabled for the repository, you may also use GitHub's private vulnerability reporting flow.

Please include:

- Affected version or commit.
- Deployment method.
- Operating system and Docker version, if relevant.
- Clear reproduction steps.
- Potential impact.
- Whether the issue affects authentication, authorization, filesystem access, MCP invocation, federation, Room permissions, document parsing, deployment secrets, or private data exposure.
- Any relevant logs with secrets removed.
- Whether the issue reproduces on a fresh deployment or only with existing private data.

Please do not include:

- Real API keys.
- Bearer tokens.
- Private SSH keys.
- Passwords.
- Cloudflare credentials.
- Model provider credentials.
- Production database dumps.
- Private user documents.
- Private RAG libraries.
- Private Room histories.
- Customer data.
- Any secret that cannot be safely rotated.

If sensitive material is required to reproduce the issue, coordinate first through `security@nisb.me`.

---

## Response expectations

NISB is currently maintained by an independent maintainer.

Security reports will be reviewed on a best-effort basis.

Critical issues affecting authentication, authorization, filesystem access, remote execution, private data exposure, deployment secrets, MCP capability exposure, federation grants, or private workspace access will be prioritized.

The maintainer may ask for additional reproduction details, a reduced test case, affected commit information, or deployment context.

---

## Scope

Security-sensitive areas include:

- Authentication.
- Authorization.
- Room permissions.
- Workspace access controls.
- MCP provider invocation.
- Room-as-MCP publishing.
- Bearer token handling.
- Federation and remote capability paths.
- Grant revoke / expiry behavior.
- Filesystem access.
- Interpreter or code execution tools.
- Document upload and parsing.
- RAG ingestion and retrieval paths.
- RSS ingestion paths.
- API gateway behavior.
- Docker and deployment configuration.
- Caddy / reverse proxy configuration.
- Secret handling.
- Private workspace data.
- Private Room histories.
- Private RAG libraries.
- Private MCP endpoints.
- Logs that may expose sensitive data.

---

## Out of scope

The following are generally out of scope unless they demonstrate a concrete exploit or meaningful security impact:

- Reports without reproduction steps.
- Social engineering.
- Physical attacks.
- Denial-of-service against demo instances.
- Missing headers without practical impact.
- Rate-limit concerns without demonstrated abuse path.
- Vulnerabilities in unsupported forks or heavily modified deployments.
- Issues caused by exposed credentials outside NISB.
- Issues caused by users intentionally publishing `.env`, tokens, private keys, or runtime data.
- Scanner-only reports without a working proof of impact.
- Dependency CVE reports without showing whether NISB is actually affected.

---

## Public disclosure

Please do not publicly disclose unresolved vulnerabilities before the maintainer has had a reasonable opportunity to review and address them.

Coordinated disclosure is appreciated.

If a report is accepted, public credit may be provided if requested, unless the reporter prefers to remain anonymous.

---

## Security best practices for operators

Operators should:

- Keep NISB updated.
- Keep Docker, system packages, and reverse proxy components updated.
- Use HTTPS.
- Use strong secrets.
- Rotate API keys and bearer tokens if exposure is suspected.
- Keep `.env` private.
- Keep `/opt/nisb-data` private.
- Avoid uploading production secrets into notes, documents, Room messages, or RAG libraries.
- Avoid exposing private MCP endpoints publicly.
- Review federation grants and revoke unused grants.
- Review published Room MCP capabilities and token expiry settings.
- Back up persistent data securely.
- Test restore procedures before relying on backups.

---

## Contact

Security reports:

```text
security@nisb.me
```

General project contact:

```text
contact@nisb.me
```

Commercial licensing:

```text
license@nisb.me
```

Remote Install:

```text
install@nisb.me
```
