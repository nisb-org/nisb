## NISB-Frontend-I18N-Pipeline.md

```
docs/
├── NISB-I18N-Contract.en.md              # This document: overall i18n contract for the web UI
├── NISB-I18N-Contract.zh-CN.md           # Chinese version of the i18n contract
└── NISB-Dynamic-Modal-App-Context-Contract.en.md  # Dynamic modal / app-context contract (English)

src/
├── i18n/
│   └── index.js
│       - Creates and exports the Vue i18n instance.
│       - Loads `zh-CN` and `en` locale trees from `src/locales/`.
│       - Sets the initial locale from settings/store, with a safe default.
│       - Exposes the `$t` translation function to the whole app.
│
├── locales/
│   ├── zh-CN.js
│   │   - Root zh-CN locale aggregator.
│   │   - Imports and merges module-level zh-CN files:
│   │       * ./zh-CN/chat.js
│   │       * ./zh-CN/feed.js
│   │       * ./zh-CN/files.js
│   │       * ./zh-CN/library.js
│   │       * ./zh-CN/right-sidebar.js
│   │       * ./zh-CN/room.js
│   │       * ./zh-CN/rss.js
│   │       * ./zh-CN/timeline-runtime.js
│   │   - Exports a single zh-CN locale object for `i18n/index.js`.
│   │
│   ├── en.js
│   │   - Root en locale aggregator.
│   │   - Imports and merges module-level en files:
│   │       * ./en/chat.js
│   │       * ./en/feed.js
│   │       * ./en/files.js
│   │       * ./en/library.js
│   │       * ./en/right-sidebar.js
│   │       * ./en/room.js
│   │       * ./en/rss.js
│   │       * ./en/timeline-runtime.js
│   │   - Exports a single en locale object for `i18n/index.js`.
│   │
│   ├── zh-CN/
│   │   ├── chat.js             # Chinese strings for chat panel and message UI
│   │   ├── feed.js             # Chinese strings for feed / notifications
│   │   ├── files.js            # Chinese strings for file browser & file actions
│   │   ├── library.js          # Chinese strings for library views and document list
│   │   ├── right-sidebar.js    # Chinese strings for right sidebar (QA, evidence, settings)
│   │   ├── room.js             # Chinese strings for Room runtime & Room settings
│   │   ├── rss.js              # Chinese strings for RSS features
│   │   └── timeline-runtime.js # Chinese strings for timeline & runtime history
│   │
│   └── en/
│       ├── chat.js             # English strings for chat panel and message UI
│       ├── feed.js             # English strings for feed / notifications
│       ├── files.js            # English strings for file browser & file actions
│       ├── library.js          # English strings for library views and document list
│       ├── right-sidebar.js    # English strings for right sidebar (QA, evidence, settings)
│       ├── room.js             # English strings for Room runtime & Room settings
│       ├── rss.js              # English strings for RSS features
│       └── timeline-runtime.js # English strings for timeline & runtime history
│
├── composables/
│   ├── use_dynamic_modal_i18n.js
│   │   - Small helper for dynamic modals.
│   │   - Bridges app-level i18n into dynamic modal content.
│   │   - Ensures modal titles / buttons use the same locale as the main UI.
│   │
│   └── left_sidebar/
│       ├── actions/
│       │   └── create_entry_modal_service.js
│       │       - Service layer for "create entry" modals in the file browser.
│       │       - Uses `$t(...)` keys defined in `locales/*/files.js`.
│       │       - No hard-coded text: all user-visible strings come from i18n.
│       └── ...
│
└── components/
    ├── LeftSidebar/
    │   ├── file_browser/
    │   │   ├── CreateEntryModal.vue
    │   │   │   - UI component for creating files / folders.
    │   │   │   - Uses i18n keys (from `files.js`) for labels, hints, and buttons.
    │   │   │
    │   │   ├── BatchMoveModal.vue
    │   │   │   - UI for batch move operations in the file browser.
    │   │   │   - Uses i18n keys for titles, confirmation texts, and actions.
    │   │   │
    │   │   ├── BatchRenameModal.vue
    │   │   │   - UI for batch rename operations in the file browser.
    │   │   │   - Uses i18n keys for form labels and button texts.
    │   │   │
    │   │   └── FileTreeNode.vue
    │   │       - Single file/folder node in the tree.
    │   │       - Uses i18n keys for context menu labels and tooltips.
    │   │
    │   ├── SettingsModal.vue
    │   │   - Main settings dialog, including language selection.
    │   │   - Reads and writes locale through the settings store.
    │   │   - Uses i18n keys from `locales/*/chat.js` / `locales/*/room.js` / etc.
    │   │
    │   ├── TimelineView.vue
    │   │   - Timeline & runtime history view.
    │   │   - Uses i18n keys from `locales/*/timeline-runtime.js`.
    │   │
    │   └── RoomRuntimeSummaryCard.vue
    │       - Summary card for Room runtime status in the left sidebar.
    │       - Uses i18n keys from `locales/*/room.js`.
    │
    └── ... (other components)
        - All user-visible labels/texts should use `$t('...')` keys
          defined under `src/locales/`, never hard-coded strings.
```


