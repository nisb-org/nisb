# NISB Markdown Outline Pipeline Operations Manual
Version: v2026-05-r2
Scope: NISB frontend note / chat / epub / left sidebar / timeline / workspace stability pipelines related to Markdown preview, outline navigation, fast switching, and workspace snapshot restore

## 1. Purpose

This manual explains how to maintain the NISB frontend stability chain around:

- Markdown preview
- right-sidebar outline generation
- LazyMarkdown
- outline jumping
- timeline rapid switching
- workspace snapshot apply / restore
- file tree and favorites refresh stability
- Firefox freeze-risk reduction

This is an operations and maintenance manual, not a feature overview. Its goal is to help future maintainers tune thresholds, repair regressions, reduce sync blocking, and keep the system production-usable without breaking the five primary contracts of note / chat / epub / library / workspace.

---

## 2. Current Practical Conclusions

### 2.1 Markdown Outline Conclusion

The stable long-Markdown path has already been proven fast and reliable in real use, including very long Markdown files.

The current problem is not that the strong path is slow. The real problem is that the old threshold left many medium-large Markdown files in the weak gray zone, where outline generation could be incomplete, first-open synchronization could drift, and jump behavior could become unstable.

### 2.2 Recommended Threshold

The current recommended threshold for the stable outline path is:

- **2000 lines**

A temporary intermediate landing at 3000 lines is acceptable only if the surrounding preview chain has not yet been fully aligned, but the long-term recommendation remains 2000 lines.

### 2.3 Timeline / Workspace Conclusion

After the second-round hardening on the left sidebar, file browser controller, and workspace switching path, Firefox stress testing showed a major improvement in practical stability.

Under repeated manual stress tests involving rapid switching among txt / epub / pdf / md, intermittent workspace switching, repeated returns to file space and timeline, and continued rapid clicking, the tab did not reproduce the previous freeze behavior in the observed runs.

### 2.4 What This Means

This does **not** mean the system should now be treated as infinitely safe under all future stress conditions.

It means the current implementation has likely removed one or more important sync-blocking amplification points, and future investigation should focus on rare cumulative freeze scenarios rather than rolling back the current stabilization direction.

---

## 3. Recommended Documentation Strategy

Do **not** create a separate “round-two manual.”

The first and second rounds now belong to the same stability chain:

- Markdown outline stability
- fast-switch correctness
- stale-task suppression
- workspace apply ordering
- file tree / favorites refresh ordering
- Firefox blocking-risk control

Therefore this document should remain the single maintenance source of truth, upgraded by version rather than split by round.

---

## 4. Contracts That Must Not Be Broken

### 4.1 Unique Anchor Contract

Each heading must follow:

- `base = slug(clean(heading_text))`
- `occ = occurrence index among identical bases, starting from 1`
- `anchor_key = ${base}--${occ}`
- if `base` is empty: `anchor_key = h--${occ}`

This is the root contract behind stable outline jumping.

### 4.2 Preview DOM Contract

Every rendered heading in the preview DOM must include all of the following:

- `id="heading-${anchor_key}"`
- `data-heading-key="${anchor_key}"`
- `data-heading-anchor="${base}"`

Right-sidebar click jumps, hover preview jumps, duplicate-heading disambiguation, and LazyMarkdown progressive loading all depend on these attributes.

### 4.3 Sidebar Event Contract

The following event names must remain compatible:

- `nisb-outline-context`
- `nisb-outline-jump`
- `nisb-outline-mode-changed`
- `nisb-chat-outline-update`
- `nisb-epub-outline-update`
- `nisb-outline-hover-enabled-changed`

### 4.4 Multi-Source `NoteOutlinePanel` Contract

`NoteOutlinePanel.vue` serves:

- note
- chat
- epub

A note-side fix must never silently override chat or epub outline sources.

### 4.5 LazyMarkdown Contract

`LazyMarkdown.vue` must continue to support:

- chunk-based lazy rendering
- heading anchor indexing
- `jumpTo({ anchor_key, base_anchor, occ, text })` or equivalent
- progressive loading toward not-yet-rendered regions
- escalation to full content and index rebuild when needed

### 4.6 Workspace `files_state v3` Contract

Workspace state must continue to preserve the distinction between:

- `saved`
- `current`

Operational meaning:

- switching workspace must apply `saved -> current`
- only the workspace save action may rewrite `saved`
- favorites remain managed by the favorites tools
- `focused_root_path` persist should only update `current`

### 4.7 Local Storage Contract

The following local storage keys are auxiliary only:

- `nisb_current_workspace_id`
- `nisb_fs_focus_root_{workspace_id}`
- `nisb_fs_state_{workspace_id}`

They are convenience cache only, not authority state.

---

## 5. Stability Rules

### 5.1 Latest-Only Everywhere

All high-frequency paths must be treated as latest-only paths:

- file open
- file read
- markdown parse
- outline full-read
- outline cache landing
- timeline document switching
- workspace apply
- favorites refresh
- file tree refresh
- focus-root restore
- preview jump execution

The rule is simple:

- create a new `seq` or `runId` for each new operation
- check it at every critical stage
- check again before landing results into UI

### 5.2 Stale Is Better Than Wrong

During switching pressure, a brief stale state is acceptable.

A wrong outline, wrong file tree state, or old workspace state landing onto the new target is not acceptable.

### 5.3 No Heavy Work in the Same Event Chain

Do not stack the following into the same synchronous event chain:

- workspace apply
- `nisb_file_focus_root` / clear
- favorites refresh
- file tree refresh
- timeline open chain
- large localStorage writes

Where possible, sequence them into separated ticks.

### 5.4 Idle Work Must Use Timeout

Any low-priority idle write must include timeout protection.

This especially applies to auxiliary cache and UI state persistence.

### 5.5 localStorage / sessionStorage Rules

Storage must remain:

- small
- low-frequency
- disposable
- regenerable

Do not grow it into a large, high-frequency authority path.

---

## 6. Key Files

### 6.1 Markdown / Outline Files

- `/src/components/RightSidebar/NoteOutlinePanel.vue`
- `/src/components/LazyMarkdown.vue`
- `/src/composables/editor/useEditorController.js`
- `/src/composables/editor/modules/useEditorOutlineBridge.js`
- `/src/composables/editor/modules/useEditorMarkdownPreview.js`
- `/src/composables/editor/modules/useEditorNavigationEvents.js`
- `/src/components/Editor/NotePane.vue`
- `/src/utils/storage_safe.js`

### 6.2 Left Sidebar / Workspace Files

- `/src/components/LeftSidebar.vue`
- `/src/components/LeftSidebar/TimelineView.vue`
- `/src/components/LeftSidebar/FileBrowser.vue`
- `/src/composables/left_sidebar/file_browser/use_file_browser_controller.js`
- `/src/composables/left_sidebar/use_left_sidebar_workspaces.js`

### 6.3 Backend Files When Needed

- `/tools/workspace/__init__.py`
- favorites tool implementation file in the backend

---

## 7. Current Baseline After Round Two

### 7.1 Outline Path Baseline

The stable Markdown outline path should now be preferred earlier, with the practical recommendation centered around 2000 lines.

The strong path is preferred because it has already proven faster and more reliable than keeping medium-large Markdown files on the weaker normal path.

### 7.2 Left Sidebar Baseline

The left sidebar stabilization should preserve the following engineering direction:

- latest-only load and refresh behavior
- reduced synchronous event stacking
- delayed or separated refresh emission where appropriate
- no high-frequency synchronous storage writes
- workspace switching treated as a stateful operation, not just a single click event

### 7.3 Workspace Switching Baseline

Workspace apply should be understood as a multi-step orchestration, not a single atomic front-end tick:

1. apply current workspace snapshot
2. restore focused root state
3. refresh favorites
4. refresh file tree
5. update auxiliary current-workspace cache
6. persist backend current workspace

These stages should avoid old-task landing and avoid unnecessary same-tick heavy stacking.

### 7.4 Firefox Baseline

Current practical testing indicates the system is now close to production-usable under aggressive manual switching.

Future hardening should focus on rare cumulative edge cases, not on reverting the now-working stabilization direction.

---

## 8. Tuning Principles

### 8.1 When to Lower the Threshold

Lower the threshold first if:

- 2000–5000 line Markdown files stay on the weak path
- outlines are incomplete
- first-open synchronization drifts
- the same files are already stable on the strong path
- the strong path is known to be fast

### 8.2 When the Threshold Is Not the Main Problem

Do not blame the threshold first when:

- outline exists but jump fails
- duplicate headings jump to the wrong target
- chat or epub gets overwritten by note state
- Firefox freezes during workspace and timeline interaction
- file tree and workspace states cross-contaminate

Those are usually latest-only, DOM contract, jump bridge, sync blocking, or orchestration problems.

### 8.3 Suggested Tuning Order

If more tuning is needed, the recommended order is:

1. `NoteOutlinePanel.vue`
2. `useEditorController.js` / `useEditorOutlineBridge.js`
3. `LazyMarkdown.vue` / `useEditorMarkdownPreview.js`
4. `FileBrowser.vue`
5. `use_file_browser_controller.js`
6. `use_left_sidebar_workspaces.js`
7. `LeftSidebar.vue`
8. backend workspace tools if front-end apply semantics still disagree with the authority source

---

## 9. Shortest Troubleshooting Paths

### 9.1 Symptom: First Open Shows Previous Outline

Check in this order:

1. whether `nisb-outline-context` includes `content_text`
2. whether the context is re-emitted after the Vue flush boundary
3. whether `NoteOutlinePanel.vue` prefers incoming content over old cache
4. whether stale state is being preserved correctly instead of old state being reused incorrectly
5. whether preview and sidebar are targeting the same document

### 9.2 Symptom: Outline Exists but Jump Fails

Check in this order:

1. `anchor_key = base--occ`
2. preview DOM attributes
3. `nisb-outline-jump` payload
4. LazyMarkdown `jumpTo()`
5. normal-preview fallback lookup path

### 9.3 Symptom: App Slows Down After Repeated Switching

Check in this order:

1. sync localStorage writes
2. stale tasks still landing
3. repeated full parse spikes
4. repeated refresh loops
5. idle tasks without timeout
6. timeline and workspace refresh chains amplifying each other

### 9.4 Symptom: Firefox Tab Becomes Unresponsive

Check in this order:

1. sync storage writes
2. missing latest-only gates
3. heavy work stacked into one synchronous event chain
4. workspace apply and timeline open overlapping without cancellation
5. old file-tree or favorites refresh still landing after a newer switch
6. accidental fallback into eager full rendering

---

## 10. i18n Requirements

This subsystem is now in a bilingual transition phase.

Rules:

- new UI text should go through i18n keys first
- do not keep scattering new hard-coded strings
- purely functional fixes do not require immediate refactor of old strings
- any new status labels, warnings, degrade notices, or debug notices must be added to both locale files

---

## 11. Minimum Regression Checklist

### 11.1 Note Normal Markdown

- files below 1000 lines still generate outline correctly
- first open is synchronized
- previous-file outline does not remain visible

### 11.2 Note Medium / Large Markdown

- 2000–3000 line files must enter the stable path
- 3000–7000 line files remain stable
- click and hover jumping work correctly

### 11.3 Very Long Markdown

- the 70k-line path does not regress
- outline remains complete
- duplicate headings remain uniquely targetable

### 11.4 chat / epub

- chat outline source remains correct
- epub outline source remains correct
- neither is overwritten by note logic

### 11.5 Timeline / Workspace Stress

- rapid switching among txt / epub / pdf / md
- repeated return between timeline and file space
- workspace switching inserted between rapid document switching
- no obvious stale-state landing
- no obvious cumulative slowdown
- Firefox tab should not enter a long unresponsive state in normal stress use

### 11.6 Left Sidebar

- workspace apply restores `saved -> current`
- favorites refresh remains correct
- file tree refresh remains correct
- focus-root restore remains correct
- no workspace cross-state contamination

### 11.7 Top Controls

- collapse all / expand all works
- hover toggle works
- stale state blocks interaction briefly when necessary and recovers after ready

---

## 12. Operational Conclusion

The current practical conclusions are:

1. the stable long-Markdown pipeline should cover more files, not fewer
2. 2000 lines is the preferred operational threshold
3. the second-round left-sidebar / workspace stabilization produced a very large practical improvement in Firefox stress testing
4. the current direction should be continued, not rolled back
5. future hardening should focus on rare cumulative edge cases and maintaining contract discipline

---

## 13. One-Line Rule for Maintainers

Prefer the stable path over the weak gray zone, prefer stale over wrong, prefer latest-only over accidental old-task landing, and prefer conservative cache / scheduling behavior over reintroducing synchronous blocking risk.
