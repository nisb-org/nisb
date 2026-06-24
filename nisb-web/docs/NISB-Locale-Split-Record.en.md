# Filename: NISB-Locale-Split-Record.en.md

# NISB Locale Split Record (Batch 1)

## Purpose

This document records the first production locale split completed on 2026-05-09 for NISB.  
It serves as the baseline reference for future multilingual expansion, rollback, troubleshooting, and full-file replacement collaboration.

This split keeps the top-level locale entry files while moving large sections into statically imported module files.  
That approach remains compatible with Vue I18n locale message objects and fits Vite’s ESM-based hot-update workflow.[cite:37]

## Scope

The following files were included in this split:

- `src/locales/zh-CN.js`
- `src/locales/en.js`
- `src/locales/zh-CN/library.js`
- `src/locales/en/library.js`
- `src/locales/zh-CN/files.js`
- `src/locales/en/files.js`
- `src/locales/zh-CN/timeline-runtime.js`
- `src/locales/en/timeline-runtime.js`
- `src/locales/zh-CN/rss.js`
- `src/locales/en/rss.js`

The following main-chain files were intentionally left unchanged:

- `src/main.js`
- `src/i18n/index.js`
- `src/stores/settings.js`

## Split Strategy

This rollout followed five rules:

1. Keep top-level entry files: `src/locales/zh-CN.js` and `src/locales/en.js` remain the aggregation exits.  
2. Use static imports only: no directory auto-scan, no dynamic aggregation, no build-time magic.  
3. Split by system module, not by component: namespaces may stay fine-grained, but files stay at module level.  
4. Avoid main-chain refactors: locale splitting must not alter the i18n main chain or business runtime chains.  
5. Preserve immediate verification: the result must stay easy to hot-update and validate in Vite dev mode.

## Current Structure

The current locale structure now includes:

- Top-level aggregators:
  - `src/locales/zh-CN.js`
  - `src/locales/en.js`
- Extracted module files:
  - `library.js`
  - `files.js`
  - `timeline-runtime.js`
  - `rss.js`

Because the top-level files still export a single nested locale messages object, existing `t('...')` key paths continue to work as long as the paths themselves are not renamed.

## Module Notes

### library.js

`library.js` is treated as a system-level module rather than a single-panel locale file.  
In this batch, `library.left.*` was extracted first, while leaving room for future `library.center.*` and other library-linked text to be added into the same module file.

### files.js

`files.js` now centralizes file-space text such as favorites, context menus, batch operations, create-entry flows, batch move, batch rename, tree node feedback, and send-to-library actions.  
This reduces pressure on the oversized top-level locale entry files and makes future maintenance more readable.

### timeline-runtime.js

`timeline-runtime.js` groups both `timeline.*` and `runtime.*`.  
This matches the actual usage relationship between the Timeline view and runtime-related summaries, while keeping pause, resume, replay, and side-effect texts inside one explicit maintenance unit.

### rss.js

`rss.js` is the dedicated RSS system module file.  
In this batch it already hosts `rss.left.*`, and it can later absorb `rss.center.*` without changing the top-level aggregation pattern.

## Verified Outcome

After this split, the following goals were achieved:

- The Chinese and English locale entry files still work as the final aggregated exports.  
- Static submodule imports do not break the existing locale message object shape.  
- Vite development flow remains suitable for hot-update verification.  
- Existing component-side `t('...')` usage stays compatible.  
- Timeline dialog and feedback strings were further corrected so multiline text renders as real line breaks instead of literal backslashes.

## Timeline Message Fix Note

A follow-up fix was applied inside `timeline-runtime.js` for confirmation dialogs and feedback messages.  
The problem came from double-escaped newline text, which caused literal backslashes to appear in the UI instead of actual line breaks.

The repair was to replace the over-escaped form with real `\n` newline escapes in JavaScript strings.  
Under JavaScript string escaping rules, that is what produces actual multiline runtime text instead of visible slash characters.

## Rollback Plan

If rollback is ever needed, use the following steps:

1. Remove the newly added locale submodule files.  
2. Restore `src/locales/zh-CN.js` and `src/locales/en.js` to their pre-split single-file versions.  
3. Keep `src/i18n/index.js`, `src/main.js`, and `src/stores/settings.js` unchanged.  

Since this rollout did not modify the i18n main chain or the application runtime chain, rollback remains localized to the locale layer only.

## Next Candidates

The next possible split candidates are:

- `chat.js`
- `room.js`
- `rightbar.js`

The decision rule should remain practical rather than theoretical.  
A module should be split when its size starts hurting full-file collaboration, hot-update verification speed, or long-term maintainability, while continuing to prefer static imports plus explicit top-level aggregation for readability and stable HMR behavior.

## Acceptance Checklist

- Vite hot updates work.  
- Chinese and English switching work.  
- No white screen appears.  
- No import errors appear.  
- No key path is broken.  
- Existing `t('...')` calls still work.  
- Timeline, Runtime, Files, Library, and RSS remain functional in the already activated scope.  

This record documents Batch 1 of the locale split.  
Future split batches should append new records rather than overwrite the baseline history.
