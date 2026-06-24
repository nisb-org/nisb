# NISB RSS Backend Repair Record (2026-05-26, Incremental Update)

## 1. Background

This issue surfaced during the room MCP Python replacement work, but the actual root cause was not in the room / federation / runtime / timeline mainline, nor in the room MCP provider abstraction itself. The problem was concentrated in the NISB RSS automatic scheduling chain.

To prevent the room MCP topic from drifting further, this note records the RSS-specific investigation and repair process as a standalone engineering document that can be incrementally updated over time.

This document is suitable for:
- an internal repair record
- a release appendix
- a known-issues note
- an RSS stabilization log

However, the current version is **not suitable to present as a public statement claiming that RSS has been fully fixed**.

---

## 2. Symptoms

### 2.1 Initial symptoms

- `POST /mcp/call` kept appearing even without manual operations
- `python3 -c ...` subprocesses were repeatedly spawned with abnormal CPU / memory usage
- uvicorn / h11 reported connection-close related errors
- RSS automatic jobs kept entering delayed / retry states

### 2.2 Symptoms after the first repair stage

After replacing the following Python files:
- `api_gateway.py`
- `tools/rss/auto_import_scheduler.py`
- `tools/rss/auto_import_rules.py`
- `tools/rss/fetch_due.py`
- `tools/rss/auto_fetch_scheduler.py`

the persistent h11 connection errors were no longer observed, but the following still remained:
- `rss_auto_import_tick delayed 300s reason=error`
- a simultaneous CPU rise in one import subprocess

This indicated that:
- the HTTP / middleware layer had been largely stabilized
- the scheduler failure-semantics misjudgment had been largely fixed
- the remaining issue was inside the real RSS import execution chain

### 2.3 Symptoms after the second incremental repair stage

After further changes to:
- `tools/rss/auto_import_rules.py`
- `tools/rss/gate_candidates.py`
- `docker-compose.yml`

the issue still did not disappear completely. The current behavior is:
- `rss_auto_import_tick delayed 300s reason=error` still appears intermittently
- the `python3 -c ...` subprocess still shows intermittent high CPU usage
- the CPU peak is roughly around 40% of a 2-core allocation
- compared with the initial stage, HTTP/h11 noise has already been significantly reduced, and the problem has been narrowed down to the RSS import execution chain

This means:
- the problem has moved from “HTTP amplifier + scheduler semantics defect” to “real import execution error / real import workload”
- the full RSS chain cannot yet be declared fully repaired

---

## 3. Root cause summary

### 3.1 First-layer root cause: HTTP middleware shape amplified h11 errors

The original implementation used `@app.middleware("http")` in a BaseHTTPMiddleware-style form, which is more likely to trigger response-send timing issues during disconnects, streaming responses, and exception paths.

This layer has already been significantly mitigated after switching to pure ASGI middleware.

### 3.2 Second-layer root cause: scheduler failure semantics were not propagated correctly

The original RSS scheduling chain had the following issues:
- as long as the subprocess returned a structured object, the parent process could misclassify it as success
- partial failures inside import/fetch were only reflected in `stats.failed`
- top-level `success` often remained `True`
- the scheduler therefore continued to reschedule failed jobs as if they had succeeded

### 3.3 Third-layer root cause: source contracts were too ambiguous

The following functions had contract flaws where failures could exist while the top-level `success` still remained `True`:
- `nisb_rss_auto_import_run_due`
- `nisb_rss_fetch_due`
- `nisb_rss_auto_import_scheduler_tick_all_users`
- `nisb_rss_auto_fetch_scheduler_tick_all_users`

### 3.4 Fourth-layer root cause: the import execution chain may still be too heavy per run

After the fixes above, the remaining problem has converged onto the RSS import execution chain itself.

The high-probability areas currently include:
- `tools/rss/gate_candidates.py`
- `tools/libraries/import_rss.py`

A first conservative round of limits and observability improvements has already been applied to `gate_candidates.py`, but the intermittent error and high CPU have still not been fully removed. This suggests:
- `gate_candidates.py` may not be the only remaining cause
- the later import path in `import_rss.py` — including import, metadata patching, and SQLite patching — must now be treated as a key investigation target

---

## 4. Completed fixes

### 4.1 `api_gateway.py`

- Replaced `@app.middleware("http")` with pure ASGI middleware
- Fixed `_run_tick_in_subprocess()` so subprocess failure states are propagated correctly
- Fixed `_run_rss_auto_import_tick()` / `_run_rss_auto_fetch_tick()` so failures enter backoff and are no longer overridden by the completed path
- Recommended failure-log enrichment so that logs include:
  - `status`
  - `error`
  - `stderr_tail`
  - `stdout_tail`
  - `elapsed_s`
  - `stats`

### 4.2 `tools/rss/auto_import_scheduler.py`

- Fixed the overall success decision for import ticks
- Added `status / message / had_failures`
- Correctly consumed `partial_failure` from `run_due`
- Fixed environment-variable reading for `NISB_RSS_AUTO_IMPORT_MAX_USERS_SCAN_FOR_TICK`

### 4.3 `tools/rss/auto_import_rules.py`

- Added the following fields to `nisb_rss_auto_import_run_due()`:
  - `status`
  - `had_failures`
  - `failed_rules`
  - `message`
- Preserved compatibility with existing callers instead of breaking the basic `success` structure
- Added conservative gate search parameters when auto import calls `gate_candidates`

### 4.4 `tools/rss/fetch_due.py`

- Added the following fields to `nisb_rss_fetch_due()`:
  - `status`
  - `had_failures`
- Promoted partial failure from `stats.failed` to the top-level status

### 4.5 `tools/rss/auto_fetch_scheduler.py`

- Correctly consumes `status / had_failures` from `fetch_due`
- Prevents fetch partial failures from being treated as normal success runs

### 4.6 `tools/rss/gate_candidates.py`

- Added conservative defaults for `scan_cap / candidate_cap`
- Added a semantic candidate limit
- Added final diagnostic statistics:
  - `rows_examined`
  - `local_rows`
  - `merged`
- Improved observability on the import search path, though the intermittent error and high CPU are not yet fully eliminated

### 4.7 `docker-compose.yml`

- Added explicit RSS-related environment variables
- `init: true` may be added to improve subprocess reaping stability
- These changes are conservative runtime hardening and do not change business behavior

---

## 5. Current status assessment

### 5.1 Areas considered largely closed

The following issues have already been significantly reduced or are largely closed:

- h11 / BaseHTTPMiddleware amplifier issues
- subprocess result misjudgment in the RSS scheduler
- the main contract flaws around fetch / import partial failures
- HTTP-layer error noise during idle periods

### 5.2 Areas still open

The following issues are still open:

- the real execution error inside RSS auto import
- the actual source behind `rss_auto_import_tick delayed 300s reason=error`
- the real reason for the high CPU cost of a single import run
- the final boundary between responsibilities in `gate_candidates` and `import_rss`

### 5.3 Current conclusion

The current state is best described as:

- **first-stage repair completed**
- **second-stage stabilization still in progress**
- **real RSS import errors still under investigation**

It should not be misreported as “RSS fully closed and repaired.”

---

## 6. Current minimum executable plan

1. Keep the current Python fixes in place without rollback
2. Ensure `api_gateway.py` exposes sufficiently detailed failure logs
3. Keep the conservative limits and diagnostic output in `gate_candidates.py`
4. Focus the next round of inspection on:
   - `api_gateway.py`
   - `tools/libraries/import_rss.py`
5. Use real traceback / stderr_tail / stdout_tail evidence before deciding whether to further reduce per-run import workload

---

## 7. Release guidance

### 7.1 Suitable release positioning

This document is suitable to be published with NISB as one of the following:

- an internal release note
- an engineering appendix
- a known-issues note
- a stabilization record

### 7.2 Unsuitable release positioning

At the current stage, this document should not be published as:

- “RSS fully fixed”
- “RSS closure complete”
- a version note claiming that the issue has been completely resolved

### 7.3 Recommended external wording

If an external-facing wording is needed, a more accurate phrasing would be:

- the HTTP/middleware amplification issue in the RSS scheduling chain has been fixed
- scheduler handling of partial failures has been corrected
- RSS import stabilization is still being refined
- the current version significantly reduces noise, while additional hardening of the import execution chain remains planned

---

## 8. Future update method

Whenever a new RSS issue appears, this record should be incrementally updated with:

- new symptoms
- new root causes
- newly modified files
- new validation results
- updated release wording

This keeps RSS-specific troubleshooting decoupled from the room MCP mainline.
