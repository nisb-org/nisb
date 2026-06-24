# P0 short CJK recall closeout

## Changed files

- tools/search/index_query_fetchers.py
- tools/search/index_query.py
- tools/search/cross_module.py

## Changes

- Add prefix recall FTS expressions for short CJK queries.
- Enable a small chat recall budget for short CJK queries when chat title/direct hits are empty.
- Keep library recall disabled for this lane.
- Skip short CJK content retry when the first query pass already has total results.

## Schema

- No schema change.
- No new table.
- No new FTS table.
- No index rebuild required.
- No full sync required.

## Validation queries

- 病毒
- 尼帕病毒
- Nipah病毒
- 伊朗
- 新对话
- 有趣短文
- 拓补

## Final observed baseline

- 尼帕病毒: total=1, chat=1, chat.recall_fts=1, sync_mode=reuse_existing_index
- 病毒: total=3, chat=1, files=2, chat.recall_fts=1, files.recall_fts=2
- 有趣短文: total=1, chat recall blocked by stage guard
- 拓补: total=6, files.recall_fts=6, duplicate file paths=0

## DB baseline

- db_size_bytes=771764224
- search_entries=97820
- search_recall_docs=50044
- search_fts_recall=50044
- search_fts_content=97820
- search_fts_title=97820

## Rollback

Restore the backed up files or revert the commit.
