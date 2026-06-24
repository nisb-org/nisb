# NISB Unified Search Pipeline

Release status: P3 release candidate  
Base milestone: P1 production-ready  
Hardening milestone: P1.5/P3 deep recall closeout  
Last validation baseline: 2026-06-20  
Scope: four-source unified search for chat, directories, files, and library records

## 1. Overview

NISB uses a local SQLite-backed unified search pipeline to provide fast, practical recall across four user-facing sources:

- Chat conversations
- Directory paths
- File records and file-derived content
- Library metadata and library-derived records

The pipeline is designed for small VPS deployments. It avoids external search services, heavy resident processes, and unbounded query-time content scans. The main design principle is to keep the primary result table lightweight while moving deeper recall coverage into dedicated recall-only indexes.

By P3, the pipeline has reached a release-candidate state. Chinese recall has been validated against deep Markdown body text, including phrases near the bottom of large documents. Japanese recall also performs well in manual validation. English body-text recall is acceptable for release but remains the main future improvement area.

## 2. P3 Release Summary

P3 is a closeout of the P1/P1.5 unified search work.

The release candidate includes:

- Short CJK recall hardening.
- CJK phrase expression expansion.
- Heading recall chunks.
- Code symbol recall chunks.
- Path segment recall chunks.
- Long natural-language recall widening.
- Parent evidence widening.
- Debug evidence output in smoke tooling.
- A P1.5 evaluation harness.
- A two-level DB size policy.

The most important product result is that users can now search for small Chinese fragments, short Chinese phrases, headings, code symbols, and body-text snippets without requiring an external search service.

## 3. Design Goals

The search pipeline is optimized around six goals:

- Return useful results for short, partial, mixed-language, filename-like, or body-text queries.
- Keep normal searches fast enough for an interactive UI.
- Preserve the existing API contract and frontend consumption order.
- Avoid turning every search into a raw content scan.
- Keep the system local and VPS-friendly.
- Prefer search quality over small storage savings when the index remains within the accepted local deployment budget.

The frontend-facing contract remains stable:

- `tool_results[0].data` is the business result body.
- The frontend should prefer `grouped`, then `grouped_results`, then `results/items`.
- Search result grouping and module totals remain compatible with earlier P0/P1 behavior.

## 4. Source Model

The public result groups are:

| Group | Purpose |
|---|---|
| `chat` | Conversation titles, chat metadata, and selected chat recall entries |
| `dirs` | Directory names and path segments |
| `files` | Files, filename/title matches, file content recall, and parent file results |
| `library` | Library metadata and library document records |

Internally, the pipeline also has a `doc` lane. The `doc` lane is used as an indexed retrieval lane and may contribute recall evidence, but final user-facing grouping remains centered on the four public groups.

## 5. Index Layout

The index is SQLite-based and uses separate layers for display records and recall-only records.

### 5.1 `search_entries`

`search_entries` stores lightweight searchable parent/display records. These rows are safe for grouping, ranking, and UI display.

Typical source kinds include:

- `chat_meta`
- `chat_turn`
- `dirs_dir`
- `files_file`
- `files_content`
- `doc_file`
- `doc_content`
- `library_meta`
- `library_content`
- `library_doc_json`
- `library_doc_dir`

The table is intentionally not used as a dumping ground for full file bodies.

### 5.2 `search_fts_title`

`search_fts_title` supports title and filename-style retrieval. It is used for direct title, filename, directory name, and library name matching.

### 5.3 `search_fts_content`

`search_fts_content` supports indexed content retrieval for lightweight content-bearing records.

### 5.4 `search_recall_docs`

`search_recall_docs` stores recall-only text rows. These rows are not displayed directly. Each recall row points back to a parent entity through `parent_item_key`.

Important recall fields include:

- `parent_item_key`
- `module`
- `source_kind`
- `parent_key`
- `parent_path`
- `title`
- `recall_text`
- `tier`
- `chunk_index`
- `source_mtime_ns`
- `source_size`
- `indexed_at`

### 5.5 `search_fts_recall`

`search_fts_recall` is the FTS layer over `search_recall_docs.recall_text`.

Recall FTS rows are used to find candidate parent records. After a recall row matches, the pipeline joins back to `search_entries` through `parent_item_key`, scores the parent, merges duplicate evidence, and returns the parent item rather than the raw recall chunk.

### 5.6 `search_entries_tri`

`search_entries_tri` is a trigram FTS table over selected display fields.

It is useful for substring-style matching over display-safe fields. It is not a substitute for full body-text recall.

## 6. Recall Tiers

NISB uses recall tiers to separate cheap parent metadata recall from deeper body-text recall.

| Tier | Typical source | Role |
|---|---|---|
| `0` | Parent/file/dir metadata | Fast title/path/filename recall |
| `1` | Existing content rows and chat turns | Medium-depth indexed content recall |
| `2` | Deep sampled file/doc recall | Recall-only body text, heading, code, and path recall |

Tier 2 is used for files and docs, not for library-heavy enhancement. It improves body-text discovery without expanding the main display table.

## 7. P3 Recall Source Kinds

P3 introduces or preserves several recall-focused source kinds.

| Source kind | Purpose |
|---|---|
| `files_recall_tier2` | General deep sampled file recall |
| `files_recall_heading` | Markdown and structured heading recall |
| `files_recall_code` | Code symbol, component, function, and code filename recall |
| `files_recall_path` | Path segment and path-like text recall |
| `doc_recall_tier2` | General deep sampled doc recall |
| `doc_recall_heading` | Doc heading recall |
| `doc_recall_code` | Doc code symbol recall |
| `doc_recall_path` | Doc path segment recall |

These rows are recall-only. They should not appear as raw UI results.

## 8. Query Classification

Queries are classified before lanes are executed. The class affects which retrieval lanes are enabled and how much budget each lane receives.

Common query classes include:

- `keyword`
- `short_cjk`
- `filename`
- `long_nl`
- `long_phrase`
- `symbol_heavy`

Examples:

| Query | Class | Intended behavior |
|---|---|---|
| `nisb` | `keyword` | Broad title and module recall |
| `新对话` | `short_cjk` | Chat-title seed and short CJK recall |
| `拓补` | `short_cjk` | Prefix/recall FTS for short Chinese text |
| `自然语言 本体论` | `keyword` | CJK phrase and recall evidence |
| `LibraryDetail.vue` | `filename` | Exact/direct filename and title-first matching |
| `main.js` inside a longer sentence | `filename` | Code filename evidence from recall text |
| `What topics are discussed in this conversation?` | `long_nl` | Natural-language content retrieval |

The classifier is intentionally conservative. Some long mixed-language strings may be treated as filename-like when they contain code or path symbols. P3 compensates for this through recall FTS, code evidence, and score fusion rather than by relying on raw content scans.

## 9. Retrieval Pipeline

The query pipeline has four major stages.

### 9.1 Query Analysis

The query is normalized into:

- Raw query
- Normalized query
- Compact query
- Token list
- Score token list
- Query class
- Filename/path/code-family hints

This stage also identifies short CJK queries, simple keywords, natural-language queries, and filename-like queries.

### 9.2 Lane Fetching

Each source module runs a controlled set of lanes.

Typical lanes include:

- `direct_title`
- `title_fts`
- `content_fts`
- `recall_fts`
- `chat_title_seed`
- `direct_content_like`
- `relaxed_keyword`

Not every lane is active for every query. Stage guards disable expensive or low-value lanes when earlier lanes already provide enough evidence.

### 9.3 Parent Merge

Rows fetched from title/content/recall lanes are scored and merged into parent entities.

For recall rows:

1. `search_fts_recall` finds matching recall chunks.
2. `search_recall_docs` provides recall metadata and matched recall text.
3. `search_entries` provides the parent display record.
4. The scoring layer evaluates the parent using both display fields and recall evidence.
5. Multiple rows for the same parent are merged.
6. Final results are grouped and path-deduplicated.

This prevents chunk-level duplication in the UI.

### 9.4 Final Grouping

Final results are grouped by public module. For files, path folding prevents duplicate file paths from appearing as separate items.

The frontend receives stable grouped results, while internal recall details remain implementation details unless debug tooling exposes them.

## 10. Short CJK Recall

P0 introduced targeted short CJK recall. P3 closes it out as release-ready.

The short CJK path improves queries such as:

- `病毒`
- `尼帕病毒`
- `拓补`
- `新对话`
- `有趣短文`
- `前端接线`
- `四源搜索`

Key behavior:

- Short CJK prefix recall is enabled.
- CJK phrase expansion improves compact multi-character phrases.
- Chat can receive a small recall budget when direct chat title hits are empty.
- Library recall remains disabled in heavy recall lanes.
- If the first query pass already has enough results, expensive fallback lanes are skipped.

The practical result is that Chinese fragments and short Chinese phrases can retrieve deep body-text content with fast response times.

## 11. Japanese Recall

Manual validation shows that Japanese text benefits from the same CJK recall path.

Japanese recall is not currently split into a separate product track. It is treated as a positive side effect of the CJK-safe indexing and query expression strategy.

Future work may add explicit Japanese smoke queries, but the current release does not require separate Japanese-specific logic.

## 12. English Recall Limitation

English body-text recall is currently weaker than Chinese/Japanese recall in some scenarios.

This is a known, accepted P3 limitation. It is likely related to tokenization, English phrase segmentation, token selection, and natural-language query expression behavior.

This limitation does not block the current release because the P0/P1.5 objective was to close the CJK and deep recall gap. English recall should become a future improvement track after the release candidate is frozen.

## 13. Heading Recall

P3 heading recall improves discovery of section-level content.

Heading recall chunks are generated from patterns such as:

- Markdown headings.
- Chinese chapter or section headings.
- Numbered headings.
- Bracketed headings.

A heading recall row includes title/path/heading/nearby context and joins back to the parent file or doc. The raw heading chunk is not displayed as a separate UI item.

## 14. Code Recall

P3 code recall improves discovery of code symbols and code-like text.

Examples include:

- `defineProps`
- `RoomRolesDrawer.vue`
- `LibraryDetail.vue`
- `main.js`
- `src/main.js`
- Vue component names
- Function-like or prop-like symbols

The scorer can recognize strong code evidence inside recall text. This helps relevant implementation documents outrank weak filename-only matches.

## 15. Path Recall

P3 path recall improves retrieval for path segments and path-like text.

This is useful when documentation contains references to source paths, component paths, room paths, import paths, or generated IDs. Path recall remains recall-only and joins back to parent display records.

## 16. Long Natural-Language Recall

P3 widens long natural-language recall expressions without increasing raw scan behavior.

The long query path now has more resilient recall expressions, such as strict token combinations followed by narrower fallback combinations. This improves retrieval for questions like:

- `What topics are discussed in this conversation?`
- `how to fix rss import cpu qos issue`
- `what is the current search recall architecture`

The widening is bounded by existing recall limits and stage guards.

## 17. Parent Evidence Widening

P3 improves evidence preservation during parent merge.

Merged parent results can preserve fields such as:

- `matched_source_kind`
- `recall_tier`
- `recall_chunk_index`
- `recall_evidence`
- `match_type`
- `match_reason`
- `matched_terms`
- `fts_rank`
- `best_fts_rank`
- `snippet_head`

This improves debugging and explainability. It does not change the frontend contract and does not expose raw recall chunks as UI rows.

## 18. Score Fusion

The ranking layer combines several evidence types:

- Exact title or filename match
- Prefix match
- Substring match
- Compact match
- All-token match
- Token coverage
- FTS rank
- Recall tier
- Matched recall source kind
- Parent hit count
- Title/content combined evidence
- Path folding role

Direct and exact title/filename matches remain strongest. Recall content can outrank weak tier 0 filename recall when the content evidence is more specific.

P3 inspected the score fusion layer and intentionally avoided further micro-tuning. The current ranking behavior is stable enough for release, and extra source-kind bonuses would risk unnecessary ranking churn.

## 19. Noise Control

The pipeline includes several noise controls:

- `.trash` and `.history` paths are filtered or demoted.
- Duplicate file paths are folded.
- Raw recall chunks are not displayed as separate user-facing rows.
- Library does not receive heavy recall expansion.
- Stage guards prevent unnecessary fallback lanes.
- Filename queries preserve exact/direct filename priority.
- Recall evidence is merged into parent items rather than duplicating results.

The result is higher recall without flooding top results with low-value artifacts.

## 20. P3 Performance Profile

The current P3 validation was run against the active local index.

Observed database state:

| Metric | Value |
|---|---:|
| SQLite main DB size | `1498542080` bytes |
| Approximate file size | `1.4G` |
| `search_entries` rows | `127937` |
| `search_recall_docs` rows | `107951` |
| `search_fts_recall` rows | `107951` |
| `search_fts_content` rows | `127937` |
| `search_fts_title` rows | `127937` |

Observed recall source counts:

| Module | Tier | Source kind | Rows | Recall chars |
|---|---:|---|---:|---:|
| `chat` | 1 | `chat_turn` | 3938 | 791703 |
| `dirs` | 0 | `dirs_dir` | 28857 | 5020145 |
| `doc` | 0 | `doc_file` | 4 | 944 |
| `doc` | 1 | `doc_content` | 22 | 8475 |
| `doc` | 2 | `doc_recall_code` | 41 | 24272 |
| `doc` | 2 | `doc_recall_heading` | 31 | 13520 |
| `doc` | 2 | `doc_recall_path` | 4 | 926 |
| `doc` | 2 | `doc_recall_tier2` | 34 | 68755 |
| `files` | 0 | `files_file` | 6377 | 1578026 |
| `files` | 1 | `files_content` | 11000 | 3854056 |
| `files` | 2 | `files_recall_code` | 23351 | 13575170 |
| `files` | 2 | `files_recall_heading` | 14891 | 7923577 |
| `files` | 2 | `files_recall_path` | 6194 | 1771730 |
| `files` | 2 | `files_recall_tier2` | 13207 | 26723945 |

## 21. DB Size Policy

The earlier P1 target used 1.4GB as a hard guardrail. P3 changes this into a two-level policy.

| Threshold | Meaning |
|---|---|
| 1.4GB | Soft warning |
| 1.6GB | Hard failure |

The current DB size is above the soft warning threshold but below the hard failure threshold. This is accepted because search quality must not be reduced only to save a small amount of storage.

Do not remove recall chunks, trigram support, or recall FTS data only to satisfy the old 1.4GB target unless a separate quality-neutral compaction plan exists.

## 22. P3 Evaluation Baseline

The P3 evaluation harness covers 21 queries.

Latest evaluation summary:

| Metric | Value |
|---|---:|
| Queries | 21 |
| Per-query failures | 0 |
| Warnings | 1 |
| Warning query | `搜索闸门` |
| Ordinary queries | 12 |
| Ordinary queries under 300ms | 11 |
| Ordinary under-300ms ratio | `0.9167` |
| Maximum observed latency | `934ms` |
| DB status | Soft warning |
| Release blocker | None |

The `搜索闸门` warning is accepted because the phrase was not found in recall text during offline inspection. It should remain a known warning sample rather than a release blocker.

## 23. Representative Validation Queries

The following query set should remain part of release validation:

| Query | Purpose |
|---|---|
| `nisb` | General keyword recall |
| `新对话` | Short CJK chat/title behavior |
| `有趣短文` | Rare short CJK phrase |
| `LibraryDetail.vue` | Filename/title exact behavior |
| `RoomRolesDrawer.vue` | Code filename and content evidence |
| `拓补` | Short CJK recall |
| `病毒` | Short CJK body recall |
| `尼帕病毒` | Short CJK chat/file recall |
| `四源搜索` | Short CJK file/dir recall |
| `前端接线` | Short CJK title/file recall |
| `从自然语言到本体论的转化` | Deep CJK body phrase recall |
| `自然语言 本体论` | CJK phrase and heading recall |
| `可以，现在已经形成一个足够小的可执行闭环：先把 main.js` | Long mixed query with code filename |
| `Add Explain in context button.` | English/code-like phrase recall |
| `nisb_room_shared_delete` | Symbol/code recall |
| `What topics are discussed in this conversation?` | Long natural-language recall |
| `how to fix rss import cpu qos issue` | English natural-language recall |
| `what is the current search recall architecture` | English natural-language recall |
| `defineProps` | Code symbol recall |
| `rss_import_0812fb36edee283d` | Filename/ID-like recall |

## 24. Evaluation Harness

P3 adds a dedicated evaluation harness:

```bash
python3 tools/search/search_eval_p15.py \
  --base-path /opt/nisb-data/users/nisb_ceebc6ebbe009f09 \
  --out /tmp/nisb_p15_eval.jsonl \
  --print-summary
```

Optional strict comparison:

```bash
python3 tools/search/search_eval_p15.py \
  --base-path /opt/nisb-data/users/nisb_ceebc6ebbe009f09 \
  --out /tmp/nisb_p15_after.jsonl \
  --compare /tmp/nisb_p15_before.jsonl \
  --print-summary \
  --strict
```

The harness records:

- Query
- Total result count
- Module totals
- Query class
- Latency
- Lane counts
- Skipped lanes
- Duplicate path status
- Top result titles
- Top evidence
- DB size
- Recall table counts
- Evaluation failures and warnings

## 25. Debug Evidence

`search_smoke.py` supports debug evidence output.

The debug evidence path is intended for development and release validation. It does not alter the runtime API contract.

Important evidence fields include:

- `module`
- `source_kind`
- `matched_source_kind`
- `recall_tier`
- `recall_chunk_index`
- `recall_evidence`
- `match_type`
- `match_reason`
- `matched_terms`
- `score`
- `priority`
- `fts_rank`
- `title`
- `path`
- `snippet_head`
- `item_key`
- `parent_key`

This makes it easier to understand why a parent result was returned.

## 26. Operational Rules

Production search should follow these rules:

- Do not run full sync before every query.
- Do not use unbounded raw body `LIKE` as the primary search mechanism.
- Do not put full file bodies into `search_entries.snippet`.
- Do not add unlimited content rows to `search_entries`.
- Do not enable heavy library recall expansion.
- Do not introduce external search services for the default local pipeline.
- Do not add heavy resident search daemons.
- Keep recall improvements index-time or FTS-based whenever possible.
- Keep raw recall chunks out of UI result lists.
- Keep parent merge and path folding active.

Diagnostic SQL may use `LIKE` for offline inspection, but the runtime query pipeline should remain FTS/index based.

## 27. Key Implementation Files

Important files under `tools/search/`:

| File | Role |
|---|---|
| `common.py` | Query analysis, normalization, token scoring helpers |
| `index_query.py` | Main indexed query orchestration |
| `index_query_fetchers.py` | SQL fetchers for title/content/recall lanes |
| `index_query_scoring.py` | Row scoring, parent merge, score fusion, final sorting |
| `cross_module.py` | Cross-module search entry point |
| `cross_module_pipeline.py` | Cross-module pipeline coordination |
| `cross_module_helpers.py` | Cross-module ranking and grouping helpers |
| `index_db.py` | SQLite schema creation |
| `index_store.py` | Insert/update helpers for index rows |
| `index_sync.py` | Index synchronization orchestration |
| `index_sync_fs.py` | Filesystem indexing |
| `index_sync_chat.py` | Chat indexing |
| `index_sync_library.py` | Library indexing |
| `backfill_recall_content.py` | Recall metadata/content backfill |
| `backfill_recall_metadata.py` | Recall metadata backfill |
| `backfill_recall_tier2_fs.py` | Deep file/doc recall backfill |
| `search_smoke.py` | Smoke validation CLI |
| `search_eval_p15.py` | P1.5/P3 evaluation harness |

## 28. Release Smoke Command

Example release smoke command:

```bash
BASE_PATH=/opt/nisb-data/users/nisb_ceebc6ebbe009f09

for q in \
  "nisb" \
  "新对话" \
  "有趣短文" \
  "LibraryDetail.vue" \
  "RoomRolesDrawer.vue" \
  "拓补" \
  "病毒" \
  "尼帕病毒" \
  "四源搜索" \
  "前端接线" \
  "从自然语言到本体论的转化" \
  "自然语言 本体论" \
  "可以，现在已经形成一个足够小的可执行闭环：先把 main.js" \
  "Add Explain in context button." \
  "nisb_room_shared_delete" \
  "What topics are discussed in this conversation?" \
  "how to fix rss import cpu qos issue" \
  "what is the current search recall architecture" \
  "defineProps" \
  "rss_import_0812fb36edee283d"
do
  echo "===== $q ====="
  python3 tools/search/search_smoke.py --base-path "$BASE_PATH" --query "$q" --json --debug-evidence
done
```

## 29. DB Health Check

Example DB health check:

```bash
DB_PATH="/opt/nisb-data/users/nisb_ceebc6ebbe009f09/.nisb_cache/search_index_v1.sqlite3"

sqlite3 "$DB_PATH" <<'SQL'
.headers on
.mode column

SELECT page_count * page_size AS db_size_bytes
FROM pragma_page_count(), pragma_page_size();

SELECT module, source_kind, COUNT(*) AS rows
FROM search_entries
GROUP BY module, source_kind
ORDER BY module, source_kind;

SELECT module, tier, source_kind, COUNT(*) AS rows
FROM search_recall_docs
GROUP BY module, tier, source_kind
ORDER BY module, tier, source_kind;

SELECT
  name,
  sum(pgsize) AS bytes,
  count(*) AS pages
FROM dbstat
GROUP BY name
ORDER BY bytes DESC
LIMIT 40;

PRAGMA wal_checkpoint(TRUNCATE);
SQL

ls -lh "$DB_PATH" "$DB_PATH-wal" "$DB_PATH-shm" 2>/dev/null || true
```

## 30. Rollback

Search pipeline changes are code-first and SQLite-index compatible unless a migration explicitly states otherwise.

For code-only ranking/fetch changes:

1. Revert the relevant commit.
2. Restart the API/gateway process if it is long-running.
3. Do not rebuild the index unless the change modified schema or index-time generated rows.

For tier 2 recall backfill changes:

1. Revert the backfill code.
2. Delete or rebuild the affected tier 2 recall rows if needed.
3. Keep parent `search_entries` intact unless schema changed.

For evaluation harness changes:

1. Revert the harness script.
2. Keep the search index unchanged.
3. Re-run smoke validation if policy thresholds changed.

## 31. Release Notes Summary

P3 finalizes the unified search recall hardening work for the upcoming NISB release.

Notable improvements:

- Short Chinese recall is release-ready.
- Chinese body-text fragments can retrieve deep Markdown content.
- Japanese recall is strong in manual validation.
- Heading recall improves section-level discovery.
- Code symbol recall improves implementation-note discovery.
- Path recall improves path-like text retrieval.
- Long natural-language recall is more resilient.
- Parent evidence is easier to debug.
- Duplicate file paths remain folded.
- `.trash` and `.history` noise stays out of top results.
- The pipeline remains local, SQLite-based, and VPS-friendly.

Known non-blocking limitation:

- English body-text recall is weaker than Chinese/Japanese recall and should be improved in a future post-release track.

Final P3 decision:

```text
Search quality: pass
CJK recall: pass
Japanese recall: pass by manual validation
English recall: accepted future work
Latency: pass
Duplicate paths: pass
Noise control: pass
DB size: soft warning, below hard limit
Release blocker: none
```
