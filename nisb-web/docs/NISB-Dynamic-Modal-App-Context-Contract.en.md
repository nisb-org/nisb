# NISB Dynamic Modal App Context Contract

## 1. Document Goal
- Explain why NISB needs a unified app-context wiring contract for dynamic modals.
- Clarify that this contract serves bilingual support, future multilingual release work, and long-term dynamic modal governance.
- Formalize the current path choice: dynamic modals may keep a minimal fallback safety net, while ordinary components must not continue spreading fallback messages.

## 2. Scope
- LeftSidebar file-space dynamic modals
- Library dynamic modals in the left and center areas
- Room / workspace related dynamic modals
- Any other local UI mounted dynamically via `createApp()` or an equivalent mechanism

## 3. Verified Facts
- The main app creates and installs i18n in `src/main.js`.
- `src/i18n/index.js` currently uses a factory-function pattern.
- A dynamic modal mounted with `createApp()` does not automatically inherit the main app context.
- Directly calling `useI18n()` inside a dynamic modal can cause silent failure.
- `CreateEntryModal.vue` has already been restored through the shared composable + runtime i18n + fallback approach.
- `src/composables/use_dynamic_modal_i18n.js` is the currently verified base file for dynamic modal i18n.
- `BatchMoveModal.vue` and `BatchRenameModal.vue` are already lit up and should be treated as recovered assets that must be protected.
- Ordinary left-sidebar components such as `FileTreeNode.vue` should follow the “formal locale + useI18n()” path and should not continue spreading fallback messages.

## 4. Root Cause Definition
- A dynamic modal becomes detached from the main app context.
- The problem is not limited to i18n; it may also affect Pinia, provide/inject, global properties, directives, and related context-dependent capabilities.
- Typical UI symptoms include: modal not opening, full-page overlay, frozen clicks, and silent failure.
- Therefore, the core risk of a dynamic modal is not simply “missing locale strings”, but “incomplete context during dynamic mounting”.

## 5. Formal Design Principles
- Do not break the main application chain.
- Do not change behavior protocols for internationalization.
- Dynamic modals should prioritize sharing main-app context capabilities.
- When context is missing, the component must still have a minimal safety net.
- Formal copy must always come from locale files; fallback messages must never become the formal source of truth.
- Use a unified abstraction; do not let each modal invent its own i18n wiring pattern.
- Ordinary components and dynamic modals must be governed separately; they must not share one over-expanded fallback strategy.

## 6. Dynamic Modal Layering Rules

### 6.1 Service Layer Responsibilities
- Create the host
- Mount / unmount
- Resolve / reject / cancel
- Do not own business translation logic
- Do not pretend to be the root app container
- Do not hardcode Chinese or English strings
- Do not change payloads, event names, or tool-call protocols for bilingual support

### 6.2 Modal Component Responsibilities
- Handle presentation and interaction only
- Obtain `t()` through the shared composable
- In high-risk dynamic chains, allow minimal fallback messages only as a safety net
- Do not directly couple to the main app root structure
- Do not write large language if/else branches in templates
- Do not modify file tree, uploads, batch move, library grouping, or other core behavior logic for i18n purposes

### 6.3 Shared Composable Responsibilities
- Read runtime i18n first
- Fall back to fallback messages only when runtime i18n cannot be obtained reliably
- Provide unified locale detection and simple interpolation
- Offer a reusable and minimal i18n safety layer for dynamic modals
- Do not replace the formal locale chain

## 7. When to Use It, and When Not to

### 7.1 Cases Where This Contract Must Be Used
This contract must be applied when:

1. A component is mounted dynamically through `createApp()` or an equivalent mechanism.
2. The component belongs to a dynamic modal chain in the left sidebar, file space, library, or room/workspace areas.
3. The component has app-context detachment risk if it relies only on direct `useI18n()`.
4. Real failures have already occurred in history, such as:
   - modal not opening
   - full-page overlay
   - frozen clicks
   - silent failure
5. The current stage requires preserving feature stability first, then gradually converging back to the formal locale chain.

### 7.2 Cases Where the Fallback Path Should Not Be Used
Component-level fallback messages should not continue to be used in:

1. Ordinary left-sidebar components
2. File tree nodes / file tree containers
3. Left-sidebar list components
4. Left-sidebar search components
5. The left-sidebar workspace bar
6. Any non-dynamic-modal Vue component
7. Any normal presentation component that can inherit the main app context and use `useI18n()` directly

The formal path for these components should be:
- first add formal keys to `src/locales/zh-CN.js`
- then add formal keys to `src/locales/en.js`
- then connect the component directly through `useI18n()` / `t()`
- do not add component-level `FALLBACK_MESSAGES`

### 7.3 Areas Where Fallback Is Currently Allowed
Fallback is currently allowed only in:

- `src/composables/use_dynamic_modal_i18n.js`
- dynamic modal chain files such as:
  - `CreateEntryModal.vue`
  - `BatchMoveModal.vue`
  - `BatchRenameModal.vue`
  - future Rename-related dynamic modals, if they belong to the same chain

### 7.4 Areas Where Fallback Must Not Continue to Spread
Fallback must not continue spreading into, including but not limited to:

- `FileTreeNode.vue`
- `FileBrowser.vue`
- `LibraryList.vue`
- `RssPanel.vue`
- `SearchPanel.vue`
- `SearchPanelControls.vue`
- `LeftSidebarWorkspaceBar.vue`
- other ordinary left-sidebar components

## 8. Current Formal Path Choice
The current formal path choice for dynamic modal i18n in NISB is:

### 8.1 Formal Copy Source
The formal source of UI copy must always be:
- `src/locales/zh-CN.js`
- `src/locales/en.js`

Future multilingual expansion must continue to follow the locale chain.  
Fallback messages must never become the formal source of multilingual content.

### 8.2 Safety Path for Dynamic Modals
For dynamic `createApp()` modals:
- first try to read runtime i18n through the shared composable
- if runtime i18n cannot be obtained reliably, allow fallback as a safety net
- the role of fallback is risk control, not long-term formal content ownership

### 8.3 Formal Path for Ordinary Components
For ordinary components:
- first add formal locale keys
- then connect the component through `useI18n()`
- do not add new component-level fallback messages
- if fallback already exists in an ordinary component, gradually clean it up and move it back into the formal locale chain

## 9. Formal Prohibitions
- Do not write large locale if/else branches in templates.
- Do not hardcode Chinese or English inside service files.
- Do not add root layout classes such as `.app` to modal hosts.
- Do not modify payloads, event names, or runtime protocols for bilingual support.
- Do not perform grep-style bulk replacement across dynamic modal logic.
- Do not spread the dynamic-modal fallback pattern into ordinary components as a default engineering practice.
- Do not treat fallback messages as the formal multilingual source.

## 10. Left-Side File-Space Priority Migration List
- `CreateEntryModal.vue`
- `BatchMoveModal.vue`
- `BatchRenameModal.vue`
- Rename-related dialogs
- `FileSpaceSettingsPopover.vue` (if it later becomes dynamically mounted)

## 11. Progressive Migration Strategy
- Step 1: extract the shared i18n composable
- Step 2: migrate `CreateEntryModal.vue`
- Step 3: migrate `BatchMoveModal.vue` / Rename / `BatchRenameModal.vue`
- Step 4: evaluate whether a unified modal-mount infrastructure is needed
- Step 5: after dynamic modals are stable, keep ordinary components on the “locale + useI18n()” path without spreading fallback
- Step 6: if conditions become mature later, evaluate whether fallback inside dynamic modals can be reduced further

## 12. Acceptance Criteria
- Dynamic modals display correctly under Chinese/English switching.
- Feature chains remain intact.
- No full-page overlay, frozen clicks, or silent failures occur.
- No large template-level language branching is required.
- Dynamic modals can reuse a unified shared composable.
- Ordinary components continue to use locale files as the only formal source of UI copy.
- Fallback has not continued to spread into ordinary components.
- Future modules can reuse the same contract.

## 13. Current Execution Conclusion
- The core problem of dynamic modals is not simply missing strings, but app-context detachment.
- Therefore, keeping “shared composable + minimal fallback” at the current stage is both reasonable and necessary.
- However, this strategy must remain limited to high-risk dynamic modal chains.
- Ordinary components must return to the standard path of “formal locale + useI18n()”.
- This split-governance strategy is the current formal engineering agreement for NISB left-sidebar bilingual work and future multilingual release work.
