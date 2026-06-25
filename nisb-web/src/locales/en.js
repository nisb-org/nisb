import library from './en/library.js'
import files from './en/files.js'
import timelineRuntime from './en/timeline-runtime.js'
import rss from './en/rss.js'
import feed from './en/feed.js'
import chat from './en/chat.js'
import room from './en/room.js'
import rightSidebar from './en/right-sidebar.js'

export default {
  common: {
    close: 'Close',
    unknownError: 'Unknown error'
  },

  settings: {
    title: 'Settings',
    common: {
      save: 'Save and apply now',
      reset: 'Restore defaults'
    },
    tabs: {
      ariaLabel: 'Settings tabs',
      chat: 'Chat',
      models: 'Models',
      performance: 'Performance',
      files: 'Files',
      language: 'Language',
      about: 'About'
    },
    about: {
      placeholder: 'More settings will be added here later, including linkage, performance, and experimental features.'
    },
    language: {
      title: 'Interface language',
      description: 'Switch the app interface language. The first phase supports Simplified Chinese and English.',
      zhCN: '简体中文',
      en: 'English',
      immediate: 'Changes take effect immediately without refreshing the page.',
      fallbackHint: 'If a translation is missing, the UI falls back to English.'
    },
    chat: {
      autoTranslate: {
        label: 'Automatically translate prompts into English for better retrieval and citation results',
        hint: 'Best for plain-text prompts. It is recommended to turn this off when referencing paths like agent_files/... or using attachments, so paths and filenames are not rewritten and cause missing files / evidence.'
      },
      translateModel: {
        label: 'Current translation model',
        goToModels: 'Go to Models tab to edit',
        hint: 'Translation models are now managed uniformly under the Models tab.'
      }
    },
    models: {
      common: {
        currentCustom: 'Current custom',
        customModelName: 'Custom model name'
      },
      catalog: {
        label: 'Available models',
        loading: 'Loading...',
        refresh: 'Refresh model list',
        hint: 'The model list comes directly from the backend dynamic registry and only shows provider/model entries currently available on the backend.',
        errorPrefix: 'Load failed: '
      },
      conversation: {
        label: 'AI conversation model',
        placeholder: 'For example: gpt-4.1-mini / claude-sonnet-4-5-20250929',
        hint: 'This is the default AI conversation model. In the future, room prompts, Supervisor flows, and role replies should also read from this unified value.'
      },
      translate: {
        label: 'Translation model',
        placeholder: 'Defaults to gpt-4o-mini when left blank',
        hint: 'Used to automatically translate prompts into English. If left blank when saving, it falls back to gpt-4o-mini.'
      }
    },
    files: {
      common: {
        listSeparator: ', '
      },
      currentWorkspace: {
        label: 'Current workspace',
        refresh: 'Refresh list',
        hint: 'Saved snapshot = the state you explicitly saved to the workspace; Current state = the temporary state you changed in the file tree.'
      },
      manage: {
        label: 'Workspace management',
        iconChoicesAria: 'Workspace icon options',
        renamePlaceholder: 'Rename current workspace',
        rename: 'Rename',
        delete: 'Delete',
        hint: 'Deletion is soft-delete only. The workspace is moved to backend .trash; the default workspace cannot be deleted.'
      },
      create: {
        label: 'Create new workspace',
        iconChoicesAria: 'New workspace icon options',
        placeholder: 'For example: Personal / Project A / Paper',
        submit: 'Save and create',
        hint: 'After creation, the list refreshes automatically and switches to the new workspace.'
      },
      snapshotFocus: {
        label: 'Snapshot focus directory',
        placeholder: 'For example: books or agent_files/docs'
      },
      snapshotFavorites: {
        label: 'Snapshot favorites',
        refreshPreview: 'Refresh preview',
        copyCurrentLinks: 'Copy current favorite links',
        preview: 'Preview (up to 8): {items}',
        empty: 'There are no favorite items in the current snapshot yet. Add favorites in the file tree first, then click save to workspace.',
        clearedUnsaved: 'Favorites cleared (unsaved) — click "Save to workspace" to persist, or "Apply to UI" to restore.'
      },
      actions: {
        readCurrentFocus: 'Read current focus directory',
        applyToUi: 'Apply to UI',
        saveToWorkspace: 'Save to workspace',
        clearFavorites: 'Clear favorites'
      }
    },
    performance: {
      sync: {
        label: 'Keep local evidence synced with conversation history',
        hint: 'When turned off, the Local Evidence panel on the right will no longer refresh as you switch conversation history, reducing switching overhead.'
      },
      autoSelect: {
        label: 'Auto-jump to library / document / span and select the first local evidence item',
        hint: 'When turned off, local evidence still stays in sync, but it will not auto-jump to the library. Manual clicks still work.'
      }
    }
  },

  selectionTranslate: {
    fab: {
      title: 'Translate selected text',
      label: 'T'
    },
    modal: {
      title: 'Selection translation',
      version: 'v-simple-20251220-0848',
      close: 'Close'
    },
    source: {
      label: 'Source'
    },
    translation: {
      label: 'Translation'
    },
    target: {
      label: 'Target:'
    },
    actions: {
      showPhonetics: 'Show phonetics',
      loadingPhonetics: 'Loading phonetics…',
      speakSource: '▶ Read source',
      speakExample: 'Read example',
      generating: 'Generating…',
      copySource: 'Copy source',
      copyBoth: 'Copy source + translation',
      retranslate: 'Retranslate'
    },
    status: {
      translating: '⏳ Translating…',
      empty: '(None yet)',
      cacheHit: 'Cache hit'
    },
    dict: {
      meaning: 'Meaning',
      examples: 'Examples',
      notes: 'Notes'
    },
    mode: {
      dict: 'Dictionary style (word / phrase / short sentence)',
      chunks: 'Faithful translation (paragraphs / long sentences split automatically)'
    },
    toast: {
      translateFailed: 'Translation failed: {error}',
      phoneticsEnglishOnly: 'Phonetics currently supports English text only.',
      phoneticsNonEnglish: 'This text does not look like English, so phonetics is unavailable.',
      phoneticsFailed: 'Failed to load phonetics: {error}',
      ttsFailed: 'TTS failed: {error}',
      autoplayBlocked: 'The browser blocked autoplay. Please click the audio control to play.',
      sourceCopied: 'Source copied',
      translatedCopied: 'Source and translation copied'
    },
    copy: {
      sourceLabel: '[Source]',
      translationLabel: '[Translation]',
      examplesLabel: '[Examples]',
      notesLabel: '[Notes]'
    },
    languages: {
      'zh-CN': 'Simplified Chinese',
      'zh-TW': 'Traditional Chinese',
      en: 'English',
      ja: 'Japanese',
      ko: 'Korean',
      fr: 'French',
      de: 'German',
      es: 'Spanish',
      'pt-BR': 'Portuguese (Brazil)',
      it: 'Italian',
      ru: 'Russian',
      ar: 'Arabic'
    }
  },

  sidebar: {
    tabs: {
      conversations: 'Conversations',
      files: 'Files',
      libraries: 'Library',
      timeline: 'Timeline',
      rss: 'RSS'
    },
    actions: {
      search: 'Search',
      uploadFile: 'Upload file to current directory',
      uploadDirectory: 'Recursively upload a directory and preserve its hierarchy under the current directory',
      collapse: 'Collapse left sidebar'
    },
    search: {
      open: 'Search',
      title: 'Search',
      placeholder: '🔍 Search conversations, directories, files, and libraries (including book titles)...',
      loading: '⏳ Searching...',
      initialTitle: '💡 Enter keywords to search everything',
      initialHint: 'Supported search targets: conversation titles/content, directory names/paths, files (filename + content), library names/book titles',
      noCategoryTitle: '🧭 Please enable at least one search type',
      noCategoryHint: 'Use the top buttons to control whether the four result categories are included in search. This preference is only stored locally.',
      emptyTitle: '😔 No related results found',
      emptyHint: 'Try other keywords; whitespace normalization, fuzzy matching, and ranking optimization have already been applied automatically',
      normalizedQuery: 'Searched with normalized query: {query}',
      sections: {
        chat: '💬 Conversations ({count})',
        dirs: '📁 Directories ({count})',
        files: '📄 Files ({count})',
        library: '📚 Libraries / Books ({count})',
        global: '📈 Expand all'
      },
      actions: {
        openDebug: 'Open debug panel',
        closeDebug: 'Close debug panel',
        debugOn: 'Debug on',
        debugOff: 'Debug off',
        collapse: 'Collapse',
        expand: 'Expand',
        collapseDebug: 'Collapse debug',
        expandDebug: 'Expand debug',
        expandChat: '📄 Expand conversations +{count}',
        expandDirs: '📁 Expand directories +{count}',
        expandFiles: '📄 Expand files +{count}',
        expandLibrary: '📄 Expand libraries +{count}',
        expandAll: 'All four categories +{count}'
      },
      messages: {
        completed: 'Search completed'
      },
      results: {
        newConversation: 'New conversation',
        messageCount: '{count} messages',
        unnamedFile: 'Untitled file',
        unnamedDirectory: 'Untitled directory',
        focusToFiles: '— Focus to Files space',
        unnamed: 'Untitled'
      },
      debug: {
        infoTitle: 'Debug info',
        devObservation: 'Dev-mode search observation'
      },
      controls: {
        modules: {
          chat: 'Chat',
          dirs: 'Directories',
          files: 'Files',
          library: 'Library'
        },
        presets: {
          all: 'All',
          workspace: 'Files space',
          reset: 'Reset'
        },
        hint: 'Fixed order: chat / directories / files / library; filter preferences are only stored locally'
      },
      match: {
        bases: {
          title: 'Title',
          content: 'Content',
          filename: 'Filename',
          directory: 'Directory',
          directoryName: 'Directory name',
          directoryPath: 'Directory path',
          libraryName: 'Library name',
          libraryDescription: 'Library description',
          book: 'Book',
          hit: 'Hit'
        },
        reasons: {
          fuzzy: 'Fuzzy',
          prefix: 'Prefix',
          exact: 'Exact',
          compact: 'Compact',
          substring: 'Substring',
          tokens: 'Tokens'
        }
      },
      source: {
        files: 'files',
        chat: 'chat',
        dirs: 'dirs',
        library: 'library'
      }
    },
    workspace: {
      current: 'workspace',
      settings: 'Settings',
      operationFailed: 'Operation failed',
      operationCompleted: 'Operation completed',

      loadModelCatalogFailed: 'Failed to load model catalog',
      loadWorkspacesFailed: 'Failed to load workspaces',
      loadWorkspacesException: 'Failed to load workspaces: {error}',

      getCurrentStateFailed: 'Failed to get the current workspace state',
      restoreSnapshotSuccess: 'Workspace snapshot restored',
      restoreSnapshotFailed: 'Failed to restore workspace snapshot',
      restoreSnapshotException: 'Workspace snapshot restore failed: {error}',
      switchRestoring: 'Switched workspace: {name} (restoring snapshot)',
      invalidWorkspaceIdRestore: 'Invalid workspace_id, unable to restore snapshot',
      invalidWorkspaceIdSwitch: 'Invalid workspace_id, unable to switch workspace',
      restoreRoomWorkspaceSuccess: 'Restored the full workspace file state bound to the room',
      applyRoomFocusSuccess: 'Applied the room focus directory to the left sidebar',
      clearRoomFocusSuccess: 'Cleared the room focus root in the left sidebar',
      applyRoomContextFailed: 'Failed to apply room workspace_context: {error}',

      invalidWorkspaceId: 'Invalid workspace_id',
      invalidWorkspaceIdCopy: 'Invalid workspace_id, unable to copy',
      invalidWorkspaceIdRefresh: 'Invalid workspace_id, unable to refresh',
      invalidWorkspaceIdSave: 'Invalid workspace_id, unable to save',
      invalidWorkspaceIdApply: 'Invalid workspace_id, unable to apply',
      invalidWorkspaceIdClear: 'Invalid workspace_id, unable to clear',

      enterWorkspaceName: 'Please enter a workspace name',
      createWorkspaceFailed: 'Failed to create workspace',
      createWorkspaceNoId: 'Failed to create workspace: workspace_id was not returned',
      workspaceCreated: 'Workspace created: {id}',
      createWorkspaceException: 'Create failed: {error}',

      enterNewName: 'Please enter a new name',
      renameWorkspaceFailed: 'Failed to rename workspace',
      workspaceRenamed: 'Workspace renamed',
      renameWorkspaceException: 'Rename failed: {error}',

      defaultWorkspaceDeleteDenied: 'Default workspaces cannot be deleted',
      deleteWorkspaceConfirm: 'Delete this workspace?\n\nDeletion is soft delete. The workspace will be moved to backend .trash.',
      deleteWorkspaceFailed: 'Failed to delete workspace',
      workspaceDeleted: 'Deleted and moved to .trash',
      deleteWorkspaceException: 'Delete failed: {error}',

      focusRead: 'Current focus read: {path}',
      focusEmpty: 'Current focus is empty',
      focusReadFailed: 'Failed to read current focus',

      getCurrentFavoritesFailed: 'Failed to get current favorites',
      currentFavoritesEmpty: 'Current favorites are empty',
      favoriteDirectoriesHeading: '## Favorite directories ({count})',
      favoriteFilesHeading: '## Favorite files ({count})',
      copiedFavoriteLinks: '✅ Copied current favorite internal links: directories {dirs} + files {files}',
      clipboardDenied: 'Copy failed: the browser blocked clipboard access',
      copyFailed: 'Copy failed: {error}',

      refreshWorkspaceFilesStateFailed: 'Failed to refresh workspace file state',
      refreshFailed: 'Refresh failed: {error}',

      updateCurrentStateFailed: 'Failed to update current state',
      saveSnapshotFailed: 'Failed to save snapshot',
      snapshotSaved: 'Saved as workspace snapshot',
      saveFailed: 'Save failed: {error}',

      applyWorkspaceFilesStateFailed: 'Failed to apply workspace file state',
      appliedToUi: 'Restored and applied to the UI',
      applyFailed: 'Apply failed: {error}',

      clearWorkspaceFilesStateFailed: 'Failed to clear workspace file state',
      workspaceFilesStateCleared: 'Workspace file state cleared',
      clearFailed: 'Clear failed: {error}',
      favoritesLocalCleared: 'Favorites cleared (unsaved). Click "Save to workspace" to persist, or "Apply to UI" to restore.'
    },
    conversations: {
      title: 'Conversation history',
      create: 'New conversation',
      newConversation: 'New conversation',
      filterByLabel: 'Filter conversations by label',
      rename: 'Rename',
      delete: 'Delete',
      undo: 'Undo',
      loading: '⏳ Loading conversations...',
      empty: '(No conversations yet)',
      loadMore: 'More',
      loadMoreLoading: '⏳ Loading more…',
      reachedEarliest: 'Reached the earliest',
      turnCount: '{count} items',
      labels: {
        title: 'Conversation labels',
        all: 'All',
        unlabeled: 'Ungrouped',
        loading: '⏳ Loading labels...',
        empty: 'No labels'
      },
      tooltip: {
        id: 'conv_id: {id}',
        time: 'Time: {time}',
        labelsWithItems: 'Labels: {items}',
        labelsEmpty: 'Labels: (none)',
        labelSeparator: ', '
      },
      messages: {
        createFailed: 'Failed to create conversation: {error}',
        renamePrompt: 'Please enter a new title:',
        renameFailed: 'Rename failed: {error}',
        deleteFailed: 'Delete failed: {error}',
        movedToTrash: '✅ Conversation moved to trash: {name}\nBatch: {bulkId}',
        undoFailed: 'Undo failed: {error}',
        undoSuccess: '✅ Delete undone (conversation restored)'
      }
    }
  },

  note: {
    toolbar: {
      tab: 'Note',
      expandLeftSidebar: 'Expand left sidebar',
      expandRightSidebar: 'Expand right sidebar',
      switchToEdit: 'Edit',
      switchToPreview: 'Preview',
      goBackWithShortcut: 'Go back to the previous file ({shortcut})',
      goForwardWithShortcut: 'Go forward to the next file ({shortcut})',
      copyInternalLink: 'Copy internal link to this document (Markdown)',
      copiedInternalLink: 'Internal link copied (Markdown)',
      addToFavorites: 'Add to favorites',
      removeFromFavorites: 'Remove from favorites',
      focusCurrentDirectory: 'Focus the directory of the current document',
      focusDirectoryTo: '◉ Focus directory: {path}',
      clearDirectoryFocus: '○ Clear focus (back to root)',
      focusedDirectoryToast: '◉ Focused directory: {path}',
      clearedDirectoryToast: '○ Focus cleared (back to root)',
      saveSaving: 'Saving…',
      saveSaved: 'Saved',
      savePending: 'Unsaved, click to save now',
      newNote: 'New Note',
      publish: 'Publish',
      publishing: 'Publishing…',
      publishCurrentNoteToFeed: 'Publish the current note to Feed',
      noteToBrain: 'To Brain',
      noteToBrainDone: 'Brained',
      noteToBrainProcessing: 'Processing...',
      noteToBrainHint: 'Send note to brain (concept extraction + graph build)',
      noteToBrainLastTime: 'Last brained: {time}',
      defaultDocumentName: 'document'
    },
    preview: {
      pdfTitle: 'PDF Preview',
      pdfLoading: '⏳ Loading PDF...',
      imageDefaultName: 'Image'
    },
    reader: {
      lazyMarkdown: {
        loading: 'Loading more…',
        reachedEnd: 'Reached the end',
        renderFailed: 'Markdown render failed'
      },
      virtualText: {
        wrapOnTitle: 'Current: wrapping enabled. Click to disable wrapping.',
        wrapOffTitle: 'Current: wrapping disabled. Click to enable wrapping.',
        wrapOn: '↩︎ Wrap',
        wrapOff: '↔ No wrap',
        scrollHintTitle: 'Render the current position now',
        scrollHint: 'Scrolling; release to render current view',
        indexingTitle: 'Building the line index without blocking the UI',
        indexing: 'Indexing…'
      },
      epub: {
        prevPage: 'Previous page',
        nextPage: 'Next page',
        prevPageShort: '◀ Page',
        nextPageShort: 'Page ▶',
        prevChapter: 'Previous chapter',
        nextChapter: 'Next chapter',
        prevChapterShort: '◀ Chapter',
        nextChapterShort: 'Chapter ▶',
        reload: 'Reload EPUB',
        loading: '⏳ Loading EPUB…',
        empty: 'Choose an EPUB file to open.',
        renderFailed: 'EPUB render failed: {error}'
      }
    },
    editor: {
      foldAll: '⊟ Fold',
      foldAllTitle: 'Fold all (Ctrl+Shift+[)',
      unfoldAll: '⊞ Unfold',
      unfoldAllTitle: 'Unfold all (Ctrl+Shift+])',
      toggleLineNumbersTitle: 'Toggle line numbers',
      showLineNumbers: 'Show line numbers',
      hideLineNumbers: 'Hide line numbers',
      toggleLineWrappingTitle: 'Toggle line wrapping',
      enableLineWrapping: 'Enable wrapping',
      disableLineWrapping: 'Disable wrapping',
      stats: {
        words: 'words',
        chars: 'chars',
        lines: 'lines'
      }
    },
    messages: {
      internalLinkResolveFailed: 'Unable to resolve internal link.',
      epubLoading: '⏳ Loading EPUB…',
      epubOpenFailed: 'Failed to open EPUB: {error}',
      imagePasteNeedsSavedNote: 'Save the note before pasting images so NISB can choose the images/ folder.',
      imageInserted: 'Image inserted.',
      pasteImageFailed: 'Paste image failed.',
      dropImageFailed: 'Drop image failed.'
    },
    controller: {
      defaultContent: '# Zen Editor\n\nStart writing...',
      libraryDockedToast: '📚 Library docked to the right sidebar: read on the right / chat in the center',
      libraryRestoredToast: '↩ Restored: library is back in the center',
      modeLabels: {
        chat: 'Chat',
        feed: 'Feed',
        library: 'Library',
        note: 'Notes',
        other: 'Other content'
      },
      unsavedLeaveConfirm: 'The current note has unsaved changes. Continuing will discard those changes. Continue?',
      newNoteTemplate: '# New note {timestamp}\n\n',
      selectConversationFirst: 'Please select a conversation history item on the left first',
      publishNoFile: 'No file to publish.',
      publishMarkdownOnly: 'Only Markdown notes can be published.',
      publishEmptyContent: 'Empty content.',
      publishSaveFailedContinue: 'Save failed, still publishing…',
      publishFailed: 'Publish failed.',
      publishSuccess: 'Published to Feed.',
      untitled: 'Untitled'
    },
    navigation: {
      restoreFederatedRoomFailed: 'Failed to restore federated room context. Please re-enter from Recent.',
      restoreCurrentRoomFailed: 'Failed to restore the current room.',
      defaultTargetLabel: 'Other content',
      currentNote: 'Current note',
      unsavedNewNoteConfirm: '{name} has not been saved as a file.\n\nContinuing to “{target}” will discard the current unsaved content.\n\nOK: discard and continue\nCancel: stay on the current note',
      unsavedRetrySaveConfirm: '{name} has unsaved changes.\n\nOK: save now and continue to “{target}”\nCancel: go to discard confirmation',
      saveFailedKeepUnsaved: 'Save failed. Unsaved changes are still kept.',
      unsavedDiscardConfirm: '{name} still has unsaved changes.\n\nOK: discard changes and continue to “{target}”\nCancel: stay on the current note',
      previousFile: 'Previous file',
      nextFile: 'Next file'
    }
  },

  chat,
  room,
  feed,
  rightSidebar,

  files,
  library,
  ...timelineRuntime,
  rss
}

