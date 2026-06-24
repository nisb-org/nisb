export default {
  header: {
    collapse: 'Collapse right sidebar',
    dockRestore: 'Restore: move library back to the center pane',
    dockEnter: 'Dock right: move library into the right sidebar (read on the right / chat in the center)',
    dockDisabled: 'Select a library or document first, then dock it to the right',
    lightsOn: 'Lights on (exit focus mode)',
    lightsOff: 'Lights-off reading (focus mode)',
    readingOptimizerInactive: 'Reading optimizer (inactive)',
    readingOptimizerActive: 'Reading optimizer ({mode})',
    themeToLight: 'Switch to light theme',
    themeToDark: 'Switch to dark theme',
    noteOutlineToggleAll: 'Note outline: collapse / expand all',
    insightsManagedByDock: 'In Dock mode, the right reading panel takes over',
    insightsHide: 'Hide book outline / QA',
    insightsShow: 'Show book outline / QA',
    settingsHiddenByDock: 'Settings are hidden in Dock mode',
    settingsHide: 'Hide settings',
    settingsShow: 'Show settings',
    paneSwapMobile: 'Mobile: swap center pane and right sidebar',
    outlineHoverOn: '📑 Outline hover jump: on (click to turn off)',
    outlineHoverOff: '📑 Outline hover jump: off (click to turn on)',
    dockIndicator: 'Docked library reading'
  },

  dock: {
    emptyTitle: '📚 Right-side reading',
    emptySubtitle: 'No library is currently selected. Open a library from the left side and choose a book first.'
  },

  outline: {
    hoverEnabledToast: '📑 Outline hover: enabled',
    hoverDisabledToast: '📑 Outline hover: disabled'
  },

  readingOptimizer: {
    title: '🎛️ Reading Optimizer',
    actions: {
      close: 'Close',
      saveCurrentAsPreset: '＋ Save current as preset',
      setDefault: 'Set as default',
      clearDefault: 'Clear default',
      deletePreset: 'Delete',
      save: 'Save',
      cancel: 'Cancel',
      reset: 'Reset',
      disable: 'Disable',
      disabled: 'Disabled'
    },
    labels: {
      brightness: 'Text brightness',
      fontSize: 'Font size',
      lineHeight: 'Line height',
      padding: 'Page padding',
      warmth: 'Background warmth',
      smooth: 'Scroll smoothness'
    },
    values: {
      warmthWarm: 'Warm amber',
      warmthNeutral: 'Neutral',
      warmthCool: 'Cool white',
      smoothMax: 'Ultra',
      smoothComfort: 'Comfort',
      smoothFast: 'Fast'
    },
    sections: {
      professionalPresets: '🎨 Professional presets',
      customPresets: '🧩 Custom presets (server)'
    },
    presets: {
      standard: 'Standard',
      eye: 'Eye care',
      novel: 'Novel',
      academic: 'Academic',
      code: 'Code'
    },
    custom: {
      namePlaceholder: 'Preset name',
      empty: 'No custom presets yet (saved presets are visible across browsers).',
      defaultBadge: 'Default'
    },
    hints: {
      standard: 'Zen'
    },
    status: {
      saved: 'Saved',
      reset: 'Reset',
      saving: 'Saving…',
      savedNamed: 'Saved: {name}',
      applied: 'Applied',
      defaultNamed: 'Default: {name}',
      deleted: 'Deleted',
      maxCustom: 'Up to {count}'
    },
    errors: {
      nameRequired: 'Please enter a name',
      nameTooLong: 'Up to 18 characters',
      nameExists: 'Name already exists',
      saveFailed: 'Save failed',
      setDefaultFailed: 'Failed to set default',
      clearDefaultFailed: 'Failed to clear default',
      deleteFailed: 'Delete failed'
    },
    modes: {
      standard: 'Inactive',
      custom: 'Custom',
      eye: 'Eye care',
      novel: 'Novel',
      academic: 'Academic',
      code: 'Code'
    }
  },

  rss: {
    ragSettings: {
      title: 'RSS Citation Scope',
      actions: {
        resetDefaults: 'Restore defaults'
      },
      hint: 'Affects RSS citations in Chat and the RSS evidence card on the right. It is recommended to keep strict lexical matching enabled to reduce false recall.',
      fields: {
        enabled: 'Enable RSS citations',
        days: 'Time range (days)',
        limit: 'Result limit',
        minScore: 'Similarity threshold',
        strictLexical: 'Strict lexical matching',
        strictLexicalTitle:
          'Strict keyword matching. It is less friendly to multilingual or synonym-based retrieval, but may be more precise.'
      }
    }
  },

  hebbian: {
    unknownSource: 'Unknown source',
    sourceNote: 'note',
    sourceGeneric: 'source',
    completedToast: '💡 Concepts / relations updated from {sourceLabel}\\\\\\\\n📁 {source}'
  },

  outlineTree: {
    title: 'Outline Tree',
    actions: {
      miniGenerateTitle: 'Prefer the mini model when generating the outline',
      miniGenerate: 'Mini gen',
      miniExpandTitle: 'Prefer the mini model when expanding outline nodes',
      miniExpand: 'Mini expand',
      translating: 'Translating…',
      translateZh: 'Translate ZH',
      showZhTitle: 'Show translated Chinese headings',
      showZh: 'Show ZH',
      generateRefresh: 'Generate / refresh',
      expandAll: 'Expand all',
      collapseAll: 'Collapse all'
    },
    states: {
      unavailable: 'Open a library document first to use the outline tree.',
      loading: 'Loading outline…',
      empty: '(No outline yet)'
    },
    hint: 'Supports outline jump, remote node expansion, and translated Chinese heading display.',
    errors: {
      outlineGetFailed: 'Failed to load outline.',
      outlineExpandFailed: 'Failed to expand outline node.',
      outlineTranslateFailed: 'Failed to translate outline.'
    },
    toasts: {
      alreadyExpanded: 'This node has already been expanded.',
      noHeadings: 'No additional headings were found under this node.',
      miniExpandDone: 'Mini expansion completed · estimated input tokens: {tokens}',
      alreadyTranslated: 'The outline has already been translated to Chinese.',
      translateDoneWithTokens: 'Outline translation completed · estimated input tokens: {tokens}',
      translateDone: 'Outline translation completed.'
    },
    node: {
      jump: 'Jump',
      expandFromNode: 'Expand from this node'
    }
  },

  settings: {
    indexGeneration: {
      title: 'Index Generation',
      forceMini: 'Force mini model for index-related generation',
      hint: 'Applies to index or structure generation paths that support a mini-model route.'
    },
    display: {
      title: 'Display',
      showLibraryInsights: 'Show Topic QA in the right sidebar',
      hint: 'When turned off, the right sidebar hides the Topic QA block.'
    },
    topicQa: {
      title: 'Topic QA',
      show: 'Show Topic QA in the right sidebar',
      hint: 'Controls the right-side Topic QA block. The unpublished outline generator remains hidden for this release.'
    },
    outlineMini: {
      title: 'Outline Mini-model Preference',
      generatePreferMini: 'Prefer mini model when generating outline',
      expandUseMini: 'Prefer mini model when expanding outline nodes',
      hint: 'These switches only affect outline generation / expansion requests and do not change other model chains.'
    }
  },

  evidenceCard: {
    title: 'Evidence',
    clear: 'Clear',
    actions: {
      jump: 'Jump',
      copy: 'Copy'
    },
    hint: {
      cannotJump: 'This evidence item cannot be opened because library/doc is missing or the span is empty.'
    },
    toasts: {
      copied: 'Copied',
      copyFailed: 'Copy failed'
    },
    meta: {
      libraryShort: 'lib',
      docShort: 'doc',
      chunkShort: 'chunk',
      spanShort: 'span',
      libraryTitle: 'lib {value}',
      docTitle: 'doc {value}',
      chunkTitle: 'chunk {value}',
      spanTitle: 'span {value}'
    }
  },

  evidencePanel: {
    title: 'Evidence',
    meta: {
      rssCount: 'RSS {count}',
      marketCount: 'Market {count}',
      localCount: 'Local {count}',
      localPaused: 'Local (sync paused)',
      pauseAutoLink: 'Pause local linking',
      resumeAutoLink: 'Resume local linking',
      pauseAutoLinkTitle:
        'Pause automatic linking. Local evidence will still stay in sync visually, but switching history will no longer auto-jump. In Dock mode, CitationList handles the automatic linking.',
      resumeAutoLinkTitle:
        'Resume automatic linking. In Dock mode, CitationList handles the automatic linking.'
    },
    sections: {
      rssEvidence: 'RSS Evidence',
      marketEvidence: 'Market Evidence (local / federation)',
      localEvidence: 'Local Evidence'
    },
    rss: {
      publish: 'Publish',
      publishing: '⏳ Publishing',
      publishTitle: 'Publish to local Market',
      publishDisabledTitle: 'Missing object_ref, unable to publish'
    },
    market: {
      fallbackTitle: 'Market item',
      peer: 'peer: {peerId}',
      copyRef: 'Copy ref'
    },
    local: {
      libraryShort: 'lib',
      docShort: 'doc',
      spanShort: 'span',
      libraryTitle: 'lib {value}',
      docTitle: 'doc {value}',
      spanTitle: 'span {value}',
      syncDisabledHint: '(Local evidence sync with chat history is disabled in Settings.)',
      emptyHint: '(No local evidence yet)'
    },
    publish: {
      missingObjectRef: '❌ Missing object_ref (expected format like rss:{feed_id}/{article_id})',
      success: '✅ Published',
      failedPrefix: '❌ Publish failed: '
    }
  },

  topicQA: {
    title: 'Topic QA',

    actions: {
      collapse: 'Collapse',
      expand: 'Expand',
      collapseAll: 'Collapse all',
      expandAll: 'Expand all',
      refresh: 'Refresh',
      ask: 'Ask',
      processing: 'Processing…',
      loading: 'Loading…',
      loadMoreHistory: 'Load more history',
      backToRecent: 'Back to recent',
      collapseThread: 'Collapse thread',
      expandThread: 'Expand thread',
      delete: 'Delete',
      traceSource: 'Trace source',
      followUp: 'Follow up',
      elevateToLibrary: 'Elevate to library',
      elevateToGlobal: 'Elevate to cross-library',
      evidence: 'Evidence',
      collapseEvidence: 'Hide evidence',
      details: 'Details',
      copy: 'Copy',
      send: 'Send',
      cancel: 'Cancel',
      jump: 'Jump'
    },

    scope: {
      doc: 'Doc',
      library: 'Library',
      global: 'Global',
      segmentTitle:
        'store_scope determines where QA is stored and loaded; evidence_scope determines the evidence retrieval range (here it stays aligned with store_scope).'
    },

    placeholders: {
      askDoc: 'Ask about this book (press Enter to submit)',
      askLibrary: 'Ask about this library (press Enter to submit)',
      askGlobal: 'Ask across libraries (press Enter to submit)'
    },

    hints: {
      contextRequired: '(Doc scope requires opening a book first; library scope requires selecting a library first.)',
      scopeWindow:
        'Current store_scope={scope}: only the most recent portion is shown by default. Use “Load more history” to step backward gradually. Citations and evidence can be clicked to jump to source passages.',
      loadedStats: 'Loaded: {count} items · Scanned segments: {scanned}/{total}',
      historyReachedEarliest: '(History has been loaded to the earliest point.)',
      empty: '(No QA records yet)'
    },

    labels: {
      followUpTag: '↳ Follow-up'
    },

    meta: {
      threadTitle: 'thread={value}',
      threadSummary: 'Thread · {count} follow-ups',
      mode: 'mode={value}',
      model: 'model={value}',
      llmOk: 'llm_ok={value}',
      search: 'search={value}',
      storeScope: 'store_scope={value}',
      evidenceScope: 'evidence_scope={value}',
      linkedFrom: 'source={value}'
    },

    badges: {
      llm: 'LLM',
      fallback: 'Fallback',
      qa: 'QA'
    },

    followUp: {
      placeholder: 'Ask a follow-up based on this answer (press Enter to submit)'
    },

    evidence: {
      title: 'Key evidence (jumpable):',
      empty: '(No evidence was written into this record. You can use citation jump first.)',
      libraryShort: 'lib',
      docShort: 'doc',
      spanShort: 'span'
    },

    debug: {
      searchQuery: 'search_query',
      threadId: 'thread_id',
      parentQaId: 'parent_qa_id',
      depth: 'depth',
      queryDbg: 'query_dbg',
      followupDbg: 'followup_dbg',
      llmError: 'llm_error',
      rawPreview: 'raw_preview'
    },

    citations: {
      title: 'Citations:',
      jumpUnknownSpan: 'Jump Span ?',
      jumpWithIds: 'Jump {libraryId}/{docId} · Span {spanIndex}',
      jumpSpan: 'Jump Span {spanIndex}'
    },

    confirm: {
      deleteReply: 'Delete this follow-up (and any later follow-ups under it)?',
      deleteRoot: 'Delete this root question (and every follow-up in this thread)?'
    },

    errors: {
      copyClipboardDenied: 'Copy failed: browser clipboard permission is not granted.',
      traceDocMissing: 'Tracing back to a doc requires from_library_id/from_doc_id, but this record is missing them.',
      qaScopeListNonSuccess: 'qa_scope_list returned a non-success status.',
      handoffNonSuccess: 'Handoff elevate returned a non-success status.',
      qaAskNonSuccess: 'qa_scope_ask returned a non-success status.',
      followupNonSuccess: 'Follow-up returned a non-success status.',
      deleteNonSuccess: 'Delete returned a non-success status.'
    }
  }
}

