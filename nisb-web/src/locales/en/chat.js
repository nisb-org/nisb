export default {
  toolbar: {
    labels: 'Labels',
    labelsSeparator: ', ',
    manageLabels: 'Manage labels for the current conversation',
    selectConversationFirst: 'Select a conversation before setting labels',
    expandLeftSidebar: 'Expand left sidebar',
    expandRightSidebar: 'Expand right sidebar'
  },

  labelsPanel: {
    title: 'Conversation labels',
    sections: {
      current: 'Current labels',
      create: 'Create label'
    },
    states: {
      selectConversationFirst: 'Select a conversation before setting labels.',
      loading: '⏳ Loading...',
      empty: 'No labels yet. You can create one below.'
    },
    input: {
      placeholder: 'Type a label name and press Enter...'
    },
    actions: {
      add: 'Add',
      clearAll: 'Clear all labels from this conversation'
    },
    confirm: {
      clearAll: 'Clear all labels from this conversation?'
    },
    toast: {
      updateFailed: 'Update labels failed: {error}'
    }
  },

  attachments: {
    common: {
      unknownError: 'Unknown error'
    },

    upload: {
      fileTooLarge: '{name}: File is too large (limit 5 MB)',
      description: 'Chat attachment uploaded at {time}',
      itemFailed: '{name}: {error}',
      mixedAlert: '✅ Succeeded: {successCount}\n❌ Failed: {failCount}\n{errors}',
      failedAlert: '❌ Upload failed:\n{errors}',
      reused: 'Reused {count} existing attachments',
      added: 'Added {count} attachments'
    },

    picker: {
      selected: 'Selected attachment: {name}'
    }
  },

  citations: {
    title: 'Sources',
    sourceCount: '{count} sources',
    chipsAria: 'Citation sources',
    expandDetails: 'Show sources',
    collapseDetails: 'Hide sources',

    kind: {
      web: 'Web',
      local: 'Local'
    },

    fields: {
      library: 'Library',
      document: 'Document',
      span: 'Span',
      chunk: 'Chunk',
      page: 'Page',
      section: 'Section',
      rank: 'Rank',
      relevance: 'Relevance',
      url: 'URL',
      host: 'Host',
      title: 'Title',
      libraryId: 'library_id',
      docId: 'doc_id',
      spanIndex: 'span_index',
      chunkId: 'chunk_id',
      score: 'score'
    },

    unavailable: 'Unavailable',
    openSource: 'Open source',
    openWeb: 'Open link',
    openDocument: 'Open document',
    openSpan: 'Locate span',

    webFallbackHost: 'Web source',
    defaultDocumentId: 'Document',
    rawMetadata: 'Raw metadata',
    rawUnavailable: 'No raw metadata available',

    sourceFallback: 'Source {index}',
    webSource: 'Web source',
    localSource: 'Local document',
    quoteTitle: 'Quoted excerpt',
    moreSources: '{count} more sources',

    libraryLabel: 'Library {libraryId}',
    documentLabel: 'Document {docId}',
    spanLabel: 'Span {spanIndex}',
    chunkLabel: 'Chunk {chunkId}',
    pageLabel: 'Page {page}',
    sectionLabel: 'Section {section}',
    scoreLabel: 'Score {score}',
    rankLabel: 'Rank {rank}',

    pageShort: 'p. {page}',
    relevanceShort: 'rel. {relevance}',

    sourceTypes: {
      web: 'Web',
      library: 'Library',
      document: 'Document',
      local: 'Local',
      unknown: 'Source'
    },

    status: {
      stale: 'May be stale',
      unavailable: 'Source unavailable',
      localEvidenceOff: 'Local evidence is off'
    }
  },

  panel: {
    roomOlder: {
      loading: 'Loading...',
      loadMore: 'Load older messages',
      noMore: 'No older messages'
    },
    toolActivity: {
      processing: 'Tools running',
      records: 'Tool execution log'
    },
    roomSaveConfirm: {
      defaultPrompt: 'Please confirm the save target',
      fallbackTarget: 'target file',
      meta: {
        candidatePath: 'Candidate path: {path}',
        candidateKind: 'Candidate type: {kind}',
        lastSaved: 'Last saved: {path}'
      },
      actions: {
        processing: 'Processing...',
        saveToNote: 'Save to notes',
        appendLastNote: 'Append to last notes',
        cancel: 'Cancel'
      },
      savedToTarget: 'Saved to `{path}` ({targetKind}, {mode}).'
    },
    controls: {
      collapse: 'Collapse',
      features: 'Tools'
    },
    markdown: {
      thinking: 'Thinking...'
    },
    codeBlock: {
      fallbackLanguage: 'code',
      streaming: 'Streaming',
      copy: 'Copy',
      copied: 'Copied',
      copyFailed: 'Failed',
      copyAria: 'Copy {lang} code block'
    },
    summary: {
      room: 'Room',
      attachments: '{count} attachments',
      uploading: 'Uploading',
      thinking: 'Processing'
    },
    attach: {
      title: 'Add attachment',
      uploadingTitle: 'Uploading...',
      ariaLabel: 'Add attachment',
      uploadLocal: '📤 Upload local file',
      pickExisting: '📁 Choose existing file'
    },
    input: {
      roomPlaceholder: 'Enter a room message... (If it should be recorded to the notebook, tell the Supervisor explicitly.)',
      chatPlaceholder: 'Enter a message... (Ctrl+Enter / ⌘+Enter to send)'
    },
    actions: {
      stopLocalRuntime: 'Stop local runtime',
      send: 'Send'
    },
    filePicker: {
      title: '📁 Choose existing file',
      currentDir: 'Current directory:',
      goParent: 'Go to parent directory',
      searchPlaceholder: '🔍 Search current directory...',
      loading: '⏳ Loading...',
      empty: 'No files',
      kind: {
        directory: 'Folder',
        file: 'File',
      },
    },
    toast: {
      loadOlderFailed: 'Failed to load older messages: {error}',
      refreshRoomFailed: 'Failed to refresh room: {error}'
    }
  },

  toolActivity: {
    title: 'Tool activity',
    empty: 'No tool activity',
    summaryFallback: 'No preview available',
    expand: 'Show details',
    collapse: 'Hide details',
    rawPayload: 'Raw payload',
    arguments: 'Arguments',
    result: 'Result',
    machineFields: 'Runtime fields',

    kind: {
      call: 'Call',
      result: 'Result'
    },

    role: {
      supervisor: 'Supervisor',
      worker: 'Worker',
      provider: 'Provider',
      room: 'Room',
      assistant: 'Assistant',
      tool: 'Tool'
    },

    status: {
      running: 'Running',
      done: 'Done',
      warning: 'Partial',
      error: 'Failed',
      cancelled: 'Cancelled'
    },

    flags: {
      warning: 'Warning',
      error: 'Error',
      citations: 'Citations',
      sources: 'Sources',
      artifacts: 'Artifacts',
      externalView: 'External view',
      trace: 'Trace'
    },

    fields: {
      provider_id: 'provider_id',
      artifact_id: 'artifact_id',
      source_room_id: 'source_room_id',
      request_id: 'request_id',
      trace_id: 'trace_id',
      call_id: 'call_id',
      grant_id: 'grant_id',
      share_ref: 'share_ref'
    }
  },

  mcpMenu: {
    panel: {
      title: 'MCP tools',
      subtitle: 'Lightweight tools for this chat. Room MCP publish and federated MCP are managed from Room settings.',
      hint: 'Only the release-ready chat-side tool surface is shown here. Advanced runtime and filesystem permissions stay hidden for V1.'
    },
    status: {
      serperOn: 'Web search on',
      serperOff: 'Web search off',
      auditOnly: 'File audit shortcut'
    },
    sections: {
      webSearch: 'Web search',
      fileAudit: 'File audit'
    },
    fileAudit: {
      hint: 'Review file-operation records from the integrated file tools. This shortcut does not enable write permissions.'
    },
    button: {
      title: 'MCP tool toggles',
      ariaLabel: 'MCP tool toggles'
    },
    items: {
      serperSearch: 'Serper search',
      serperHint: 'Allow this chat to request web search evidence through the MCP tool bridge.',
      codeNetwork: '🌐 Code network',
      dangerousOps: '🧨 Dangerous operations (recursive directory delete)'
    },
    readScope: {
      label: '📖 Read scope',
      options: {
        userRo: 'User directory (read-only)',
        minimal: 'agent_files only'
      }
    },
    writeScope: {
      label: '✍️ Write permission',
      options: {
        none: 'Disable write',
        agentFiles: 'agent_files only'
      }
    },
    hint: 'Write access is disabled by default; when enabled, operations are still limited to agent_files.',
    actions: {
      openAudit: '🧾 File operations (audit / restore / batch)'
    }
  },

  attachFromFilesAction: {
    button: {
      ariaLabel: 'Insert file attachment placeholder',
      tooltip: 'Insert attachment placeholder'
    },
    placeholder: {
      pendingUpload: 'attachment pending upload: finish upload from the file sidebar'
    }
  },

  mcpSerperToggleAction: {
    button: {
      ariaLabel: 'Toggle Serper web search',
      tooltip: 'Allow this chat to request web search through the MCP tool bridge',
      label: 'Serper {state}'
    },
    state: {
      on: 'On',
      off: 'Off'
    }
  },

  roomMenu: {
    status: {
      localRoom: 'Local Room',
      federatedRoom: 'Federated · {label}',
      noActiveRoom: 'LLM chat',
      activeRun: 'run active'
    },
    boundary: {
      title: 'Capability boundary',
      roomRuntime: 'Room runtime',
      roles: 'roles',
      supervisor: 'supervisor',
      federationSnapshot: 'federation snapshot',
      hint: 'This menu enters and creates Rooms for chat. Room external MCP publish, tokens, revoke, expiry, and final-only answer settings stay in Room settings.'
    },
    button: {
      title: 'Room',
      ariaLabel: 'Room menu',
      activeTitle: 'Room · {title}',
      text: 'Room',
      on: 'ON'
    },
    header: {
      title: 'Rooms',
      currentMode: 'Current mode: '
    },
    modes: {
      room: 'room',
      llm: 'llm'
    },
    actions: {
      refresh: 'Refresh',
      refreshing: 'Refreshing...',
      syncCurrent: 'Sync current room',
      syncingCurrent: 'Syncing...',
      exit: 'Exit',
      refreshDetails: 'Refresh details',
      createAndEnter: 'Create and enter',
      processing: 'Processing...',
      joinAndEnter: 'Join and enter',
      enter: 'Enter',
      copyRoomId: 'Copy room_id',
      copyJoinKey: 'Copy join_key',
      copyKey: 'Copy key'
    },
    sections: {
      current: 'Current room',
      create: 'Create room',
      join: 'Join room',
      recent: 'Recent rooms'
    },
    current: {
      fallbackTitle: 'Current Room',
      federatedLabel: 'Federated · {label}',
      participants: '👥 {count}',
      roles: '🎭 {count}',
      activeRoles: '🧠 {count} active',
      supervisorEnabled: 'Supervisor enabled',
      inheritWorkspaceContext: 'Inherit context',
      inheritFocusRoot: 'Inherit focus',
      defaultRole: 'Default role: {name}',
      runId: 'run_id',
      latestPlan: 'Latest plan'
    },
    create: {
      titleLabel: 'title',
      titlePlaceholder: 'For example: New room',
      participantsLabel: 'participants (comma-separated, optional)',
      participantsPlaceholder: 'user_a,user_b',
      defaults: {
        title: 'New room'
      },
      createdRoomId: 'room_id',
      createdJoinKey: 'join_key',
      emptyValue: '—'
    },
    join: {
      roomIdLabel: 'room_id',
      roomIdPlaceholder: 'room_xxx',
      joinKeyLabel: 'join_key',
      joinKeyPlaceholder: 'Enter join_key'
    },
    recent: {
      loading: 'Loading rooms...',
      empty: 'No rooms yet.',
      federatedLabel: 'Federated · {label}',
      peerLabel: 'peer_id · {id}',
      peerFallback: 'peer',
      currentBadge: 'Current',
      id: 'ID: {id}',
      participants: '👥 {count}'
    },
    footer: {
      closeHint: 'Press Esc to close the menu; clicking outside also closes it.'
    },
    errors: {
      operationFailed: 'Operation failed',
      loadRoomsFailed: 'Load rooms failed',
      createRoomFailed: 'Create room failed',
      joinRoomFailed: 'Join room failed',
      joinFieldsRequired: 'room_id and join_key are required'
    }
  },

  ragMenu: {
    button: {
      ariaLabel: 'RAG menu',
      baseLabel: 'RAG {mode}',
      groupedLabel: 'RAG {mode} · Group G:{group}',
      scopedLabel: 'RAG {mode} · {scope}',
      libraryToken: 'L:{id}',
      docToken: 'D:{id}'
    },
    common: {
      on: 'On',
      off: 'Off'
    },
    sections: {
      retrievalMode: 'Retrieval mode',
      docTime: 'Document time range',
      agent: 'Agent'
    },
    modes: {
      off: 'Off',
      auto: 'Auto',
      cite: 'Cite',
      ground: 'Ground',
      web: 'Web'
    },
    scope: {
      global: 'All libraries',
      library: 'Library',
      doc: 'Document',
      groupedInline: '(Grouped)',
      inline: '({scope})'
    },
    items: {
      offHint: 'Plain chat',
      autoHint: 'Automatically choose Web or Off',
      citeHint: 'Local knowledge base + light citations {scope}',
      groundHint: 'Local knowledge base + strong evidence {scope}',
      webHint: 'Search the web and return real links'
    },
    docTime: {
      toggleLabel: 'Doc Time',
      quick: 'Quick',
      custom: 'Custom',
      daysUnit: 'days',
      daysAgoUnit: 'days ago',
      mode: {
        days: 'Last N days',
        relative: 'Relative range'
      },
      relativeLabels: {
        older: 'Start (older)',
        newer: 'End (more recent)'
      },
      inline: {
        days: 'Last {days} days',
        relative: '{older}~{newer} days ago'
      },
      summary: {
        disabled: 'Document time range is currently disabled.',
        days: 'Current range: last {days} days.',
        relative: 'Current range: {older} days ago ~ {newer} days ago.'
      },
      effective: {
        localMode: 'This currently applies to {mode} local retrieval.',
        savedOnly: 'The time setting is saved now and will take effect after switching to Cite / Ground.'
      }
    },
    agent: {
      tools: 'Agent tools',
      planner: 'Planner',
      steps: 'Steps',
      returnDebugTrace: 'Return debug trace (agent_trace)',
      usePlannerForAnswer: 'Use the Planner model for the final answer (Off/Web/Auto only)',
      loadFailed: '⚠️ Failed to load Planner model list: {error}'
    },
    hint: 'Click Cite / Ground once to open the context selector; click again to switch retrieval scope across all libraries / library / document. Document time range only applies to local library retrieval.'
  },

  ragContextCard: {
    title: 'RAG context',
    modeLabel: '({mode})',
    mode: {
      cite: 'Cite',
      ground: 'Ground'
    },
    common: {
      true: 'true',
      false: 'false',
      all: 'All',
      emptyMark: '—'
    },
    scopes: {
      global: 'global',
      library: 'library',
      doc: 'doc'
    },
    docTimeModes: {
      days: 'days',
      relative: 'relative'
    },
    relativeRangeLabel: '{older}d ~ {newer}d ago',
    search: {
      libraryPlaceholder: 'Filter libraries...',
      groupPlaceholder: 'Filter groups...',
      docPlaceholder: 'Filter documents...'
    },
    actions: {
      setGlobalTitle: 'Switch back to global (clear selected library / document / group)',
      clearContextTitle: 'Clear context (library / doc / group → global)',
      closeTitle: 'Close',
      useThisLibraryTitle: 'Use the current library as the RAG context',
      useThisLibrary: 'Use this library',
      clearGroupOnlyTitle: 'Clear group_id only (keep the current library / document selection)',
      clearGroupOnly: 'Clear group only'
    },
    states: {
      loadingLibraries: '⏳ Loading libraries...',
      emptyLibraries: '(No libraries)',
      loadingGroups: '⏳ Loading groups...',
      emptyGroups: '(No groups)',
      noLibrarySelected: '(No library selected)',
      loadingDocuments: '⏳ Loading documents...',
      emptyDocuments: '(No documents in this library)',
      docLoadFailed: '❌ Load failed: {error}'
    },
    library: {
      untitled: 'Untitled library'
    },
    group: {
      title: 'Groups (group_id)',
      hint: 'Note: after selecting a group, the library / document selection is cleared and scope switches to global; later retrieval will be filtered to members of that group.'
    },
    docs: {
      title: 'Documents',
      clickToSelectAndClose: 'Click a document to select it and close',
      selectLibraryFirst: 'Select a library on the left first',
      defaultFiletype: 'txt'
    },
    current: {
      title: 'Current context',
      store: 'store: {scope}',
      evidence: 'evidence: {scope}',
      groupId: 'group_id: {value}',
      libraryId: 'library_id: {value}',
      docId: 'doc_id: {value}'
    },
    summary: {
      docTimeTitle: 'Doc retrieval time range',
      rssTitle: 'RSS reference scope',
      readOnlySub: 'read-only summary',
      readOnlyLabel: '({value})',
      enabled: 'enabled: {value}',
      mode: 'mode: {value}',
      days: 'days: {value}',
      range: 'range: {value}',
      limit: 'limit: {value}',
      minScore: 'minScore: {value}',
      strictLexical: 'strictLexical: {value}',
      docTimeHint: 'This only shows the current Doc-RAG retrieval time range; use the top Doc Time controls for formal editing.',
      rssHint: 'This is the RSS live reference / display summary, not the Doc-RAG retrieval time range.'
    },
    footerHint: 'Note: all libraries = global (ignores the selected library / document); library / document mode requires selecting the corresponding library / document first. Groups further filter within global / library scope.',
    errors: {
      docStatsFailed: 'nisb_doc_stats returned failure'
    },
    toast: {
      librarySelected: '✅ Library selected: {id}',
      docSelected: '✅ Document selected: {id}',
      groupSelected: '✅ Group selected: {id}',
      groupCleared: '🧹 group_id cleared',
      switchedGlobal: '🌐 Switched back to global (all libraries)',
      contextCleared: '🧹 Context cleared'
    }
  },

  fedMenu: {
    status: {
      marketOn: 'Federation evidence on',
      marketOff: 'Federation evidence off',
      enabledPeers: '{count} enabled peer(s)',
      importedInvites: '{count} imported invite(s)'
    },
    boundary: {
      title: 'Capability boundary',
      importedRemote: 'imported_remote',
      shareRef: 'share_ref',
      sourceRoomId: 'source_room_id',
      finalOnly: 'final-only',
      sourceObservation: 'source observation boundary',
      hint: 'Consumer rooms can use final federated results, but cannot observe the source room internal execution trace.'
    },
    button: {
      text: 'Federation',
      title: 'Federation settings',
      ariaLabel: 'Federation settings'
    },
    panel: {
      title: 'Federation cockpit',
      subtitle: 'Import peer info, manage federation peers, and accept Room invites from another VPS.'
    },
    market: {
      enableEvidence: 'Enable marketplace evidence',
      hint: 'Marketplace evidence can be included in the conversation context when federation is enabled.'
    },
    peers: {
      title: 'Peers',
      disabled: 'disabled',
      tokenMissing: 'token missing',
      tokenSet: 'token set',
      use: 'Use',
      check: 'Check',
      checkPeer: 'Check peer',
      checkThisPeer: 'Check this peer',
      checking: 'Checking…',
      editHint: 'Use only fills the saved peer into this form for editing or overwrite-save. To share this device federation info, use Copy My Info in the paste/import section above.'
    },
    paste: {
      title: 'Paste federation info',
      pasteClipboard: 'Paste clipboard',
      pasting: 'Pasting…',
      import: 'Import',
      importing: 'Importing…',
      textareaPlaceholder: 'Supports JSON, key:value lines, or raw network header text. Paste the owner-provided content as-is when possible.',
      ownerHint: 'Paste federation info from the Room owner to import a peer or invite draft. To share this device with a remote side, copy your local federation info.',
      copyMyInfo: 'Copy my info',
      copying: 'Copying…',
      copyMyInfoTitle: 'Copy this device federation info to share with a remote peer',
      recommend: 'Recommended owner payload: peer_id, base_url, and token. If room_id and invite_token are included, an Accept Invite draft can be created automatically.',
      draftsTitle: 'Imported invite drafts',
      unknownPeer: 'peer?',
      roomPrefix: 'room:',
      invitePrefix: 'invite:',
      use: 'Use',
      remove: 'Remove'
    },
    accept: {
      title: 'Accept Room invite',
      peerPlaceholder: 'Select the peer that points to the Room owner VPS',
      roomIdPlaceholder: 'room_id',
      inviteTokenPlaceholder: 'invite_token',
      remoteUserPlaceholder: 'remote_user_id / user_id',
      remoteLabelPlaceholder: 'remote_label (optional)',
      targetPeerPlaceholder: 'target_peer_id (optional; usually auto-filled from paste import)',
      accepting: 'Accepting…',
      submit: 'Accept invite & enter Room',
      retry: 'Retry last accept',
      notePeer: 'Select the local peer_id that points to the Room owner VPS, not the target_peer_id written by the owner when creating the invite.',
      noteTarget: 'If the owner-provided structured text contains target_peer_id, paste import will usually fill it automatically.',
      joinedNote: 'The joined federated Room is saved to the recent area at the bottom of the Room menu, so you can re-enter it later.',
      exitNote: 'NISB will continue entering this Room now. If you exit later, only the current Room is cleared; the recent record remains.'
    },
    form: {
      title: 'Add peer',
      peerIdPlaceholder: 'peer_id (for example: vps-b)',
      baseUrlPlaceholder: 'base_url (for example: https://b.example.com)',
      tokenPlaceholder: 'token (optional)',
      labelPlaceholder: 'label (optional)'
    },
    actions: {
      refresh: 'Refresh',
      loadingShort: '⏳',
      save: 'Save',
      saving: '⏳ Saving'
    },
    states: {
      loading: 'Loading...',
      emptyPeers: 'No peers yet. Add one below or import federation info above.'
    },
    messages: {
      requiredFields: 'peer_id / base_url cannot be empty',
      saved: '✅ Saved',
      saveFailed: 'Save failed'
    },
    runtime: {
      copyEmptyText: 'Nothing to copy.',
      copyFailed: 'Copy failed.',
      copyMissingPeerId: 'Enter the current owner peer_id before copying. NISB can reuse the current page token and origin after that.',
      copyMissingBaseUrl: 'Could not read the current page base_url.',
      copyMissingToken: 'Could not read the current login token. Confirm that you are signed in, or temporarily enter a token in the form first.',
      copyInfoOk: 'Federation info copied from the current page context.',
      requiredPeerBaseUrl: 'peer_id / base_url are required.',
      savePeerFailed: 'Save peer failed.',
      peerSaved: 'Peer saved.',
      peerSavedRetryReady: 'Peer saved. Token updated; you can retry Accept directly.',
      clipboardNotSupported: 'This environment cannot read the clipboard directly. Paste into the text box manually.',
      clipboardEmpty: 'The clipboard is empty.',
      clipboardReadFailed: 'Could not read the clipboard. Paste manually instead.',
      pasteRequired: 'Paste federation info first.',
      noImportableFields: 'No importable fields were recognized. Check the text format.',
      peerSavedUpdated: 'peer {peerId} saved/updated',
      inviteDraftImported: 'invite draft imported and filled into Accept Invite',
      peerFormFilled: 'peer form parsed and filled',
      inviteFormFilled: 'invite form filled as much as possible',
      federationInfoParsed: 'federation info parsed',
      messageSeparator: '; ',
      missingPeerIdHint: 'base_url and token were recognized, but peer_id is missing. Add a local peer_id to save this owner.',
      peerInviteReadyWithTarget: 'peer updated and invite filled. target_peer_id was also included; you can Accept now.',
      peerInviteReadyMissingTarget: 'peer updated and invite filled. target_peer_id is empty; verify the owner-provided invite text.',
      peerReadyAwaitInvite: 'peer is ready. If the owner sends room_id / invite_token later, paste the new text as-is to complete the invite.',
      inviteReadyWithTarget: 'invite imported and target_peer_id filled.',
      inviteReadyMissingTarget: 'invite imported, but target_peer_id was not recognized. Verify the owner text.',
      peerHealthOk: 'Peer {peerId} health ok.',
      peerHealthFailed: 'Peer {peerId} health check failed.',
      missingRoomId: 'missing room_id',
      requiredInviteFields: 'peer_id / room_id / invite_token / remote_user_id are required.',
      acceptRoomMissingRoomId: 'accept ok but room_id missing'
    },
    inviteErrors: {
      tokenInvalid: 'The peer token is invalid or expired. Update the token first.',
      ownerUnreachable: 'The owner VPS is currently unreachable. Check base_url and service status.',
      permissionDenied: 'The current token does not have permission to access this invite or Room.',
      roomNotFound: 'The Room was not found on the owner VPS.',
      inviteExpired: 'The invite has expired. Ask the owner to issue a new one.',
      inviteNotActive: 'The invite is no longer active or has already been used.',
      peerMismatch: 'The current peer does not match the invite. Check peer_id and target_peer_id.',
      inviteNotFound: 'The invite does not exist or does not match the current peer.',
      peerNotFound: 'The peer does not exist or is disabled.',
      acceptFailed: 'Accept invite failed.'
    },
    inviteHints: {
      tokenInvalid: 'After updating this peer token, click Retry Last Accept directly. You do not need to recreate the invite.',
      ownerUnreachable: 'This is not a permission issue. Retry after the owner VPS service is restored.',
      inviteExpired: 'This cannot be fixed by retrying. The owner must issue a new invite.',
      inviteNotActive: 'This cannot be fixed by retrying. The owner must issue a new invite.',
      peerMismatch: 'Focus on the selected peer_id and the target_peer_id included in the owner text.'
    },
    health: {
      ok: 'ok',
      tokenInvalid: 'token invalid',
      ownerUnreachable: 'unreachable',
      permissionDenied: 'permission denied',
      peerNotFound: 'peer missing',
      checking: 'checking',
      unknown: 'unknown'
    },
    success: {
      acceptedRoomInvite: 'Room invite accepted. Entering federated Room.'
    },
    hint: 'Checked peers are passed to orchestrate with each conversation. Federation does not expose the source Room internal execution process.'
  },

  fsAuditModal: {
    title: 'File operations',
    subtitle: 'File audit and recovery tools opened from the chat-side MCP shortcut.',
    status: {
      audit: 'Audit trail',
      recovery: 'Recovery tools',
      confirmRequired: 'Destructive actions require confirmation'
    },
    actions: {
      refresh: 'Refresh',
      close: 'Close',
      search: 'Search',
      loadMore: 'Load more',
      restore: 'Restore',
      restoreThisItem: 'Restore this item',
      restoreBatch: 'Restore batch',
      purgeBatch: 'Purge batch',
      restoreRename: 'Restore name',
      expand: 'Expand',
      collapse: 'Collapse',
      previousPage: 'Previous page',
      nextPage: 'Next page'
    },
    tabs: {
      ariaLabel: 'File tools sections',
      audit: 'Audit',
      files: 'Current files',
      trash: 'Trash',
      batch: 'Batch run'
    },
    common: {
      deleteConfirmToken: 'delete',
      loading: 'Loading...',
      loadingAscii: 'Loading...',
      page: 'Page {page}',
      unknownError: 'Unknown error'
    },
    audit: {
      prefix: 'Prefix',
      prefixPlaceholder: 'For example: agent_files/notes (optional)',
      limit: 'Limit',
      searchLabel: 'Search',
      searchPlaceholder: 'Keyword (matches operation/paths/metadata), empty = tail',
      filterSummary: 'Filter: keyword="{keyword}", showing {shown} / raw {total}',
      metadata: 'Metadata',
      empty: 'No records yet (or no matches)',
      footer: 'Note: this shows audit events, not whether a file currently exists; use the Current files / Trash tabs to inspect the current state.',
      restoreRenameTitle: 'Rename new_path back to old_path (and refresh tree / favorites / focus root)',
      restoreBackupTitle: 'Restore this path from backup',
      backupPurged: '(Backup already purged)',
      backups: {
        title: 'Backups (.backups)',
        loading: 'Counting…',
        notCounted: 'Not counted',
        statsText: '{count} items, about {size}',
        refreshStats: 'Refresh stats',
        purgeAll: 'Purge restorable backups'
      }
    },
    files: {
      depth: 'Depth',
      includeHidden: 'Include hidden (.trash)',
      refreshSnapshot: 'Refresh snapshot',
      snapshotMeta: 'root={root} ts={ts}',
      emptyTree: '(Empty)'
    },
    trash: {
      bytes: '{size} bytes',
      filter: 'Filter',
      filterPlaceholder: 'Filter by file name or path',
      refreshTrash: 'Refresh trash',
      itemType: 'trash',
      trashPath: 'trash: {path}',
      originalPathDerived: 'Derived original path: {path}',
      emptyFiltered: 'Trash is empty or no items matched',
      footer: 'Note: deletion defaults to soft delete into trash, so deleted files do not remain in the agent_files root.',
      batch: {
        title: '🧺 Batch trash (directories / multiple items)',
        searchPlaceholder: 'Search bulk_id / path keyword',
        purgeAll: 'Clear trash',
        empty: '(No batch deletion records)',
        bulkId: 'bulk_id: {id}',
        itemsCount: '{count} items',
        bucket: 'bucket: {path}',
        searchInBatchPlaceholder: 'Search paths in this batch',
        emptyDetail: '(No matching items)'
      },
      conversation: {
        title: '💬 Conversation trash',
        searchPlaceholder: 'Search name / bulk_id / conv_id',
        purgeAll: 'Clear trash',
        empty: '(No conversation batches)',
        bulkId: 'bulk_id: {id}',
        itemsCount: '{count} items',
        displayName: 'Name: {name}',
        convId: 'conv_id: {id}',
        bucket: 'bucket: {path}',
        searchInBatchPlaceholder: 'Search paths in this batch',
        emptyDetail: '(No matching items)'
      }
    },
    batch: {
      dryRun: 'dry-run (validate only, do not write)',
      stopOnError: 'Stop on error',
      run: 'Run',
      templateCreateOnly: 'Template: create only',
      templateCreateUpdate: 'Template: create + update',
      templateDemoDelete: 'Template: demo delete to trash',
      confirmLabel: 'confirm (optional)',
      confirmPlaceholder: 'For example: DELETE (dangerous operations only)',
      resultMeta: 'batch_id={batchId} dry_run={dryRun}',
      footer: 'Hint: after running, Current files / Trash / Audit are refreshed automatically so changes are visible.'
    },
    prompts: {
      restoreDirRename:
        'Restore the directory name?\\n\\nThis will rename:\\n{from}\\nback to:\\n{to}\\n\\n(Tree / favorites / focus root will also refresh.)',
      purgeAllBackups:
        'Type delete to permanently purge ALL restorable backups.\\n\\n(You may also enter: 删除)',
      purgeTrashBatch:
        'Type delete to permanently purge batch {id}.\\n\\n(You may also enter: 删除)',
      purgeTrashAll:
        'Type delete to permanently clear the trash.\\n\\n(You may also enter: 删除)',
      purgeConvBatch:
        'Type delete to permanently purge conversation batch {id}.\\n\\n(You may also enter: 删除)',
      purgeAllConvTrash:
        'Type delete to permanently clear all conversation trash.\\n\\n(You may also enter: 删除)'
    },
    messages: {
      restoreFailed: 'Restore failed',
      restoreFailedWithError: 'Restore failed: {error}',
      purgeFailed: 'Purge failed',
      purgeFailedWithError: 'Purge failed: {error}',
      backupRestored: '✅ Backup restored',
      renameRestored: '✅ Directory name restored',
      restoreRenameFailed: 'Restore rename failed',
      statsFailed: 'Stats failed',
      purgeBackupsFailed: 'Purge backups failed',
      backupsPurged: '🧹 Restorable backups purged',
      loadBatchDetailFailed: 'Failed to load batch details: {error}',
      batchRestored: '✅ Batch restored: {id}',
      itemRestored: '✅ Restored: {path}',
      batchPurged: '🧹 Batch purged: {id}',
      restored: '✅ Restored',
      loadConvBatchDetailFailed: 'Failed to load conversation batch details: {error}',
      convBatchRestored: '✅ Conversation batch restored: {id}',
      convBatchPurged: '🧹 Conversation batch purged: {id}',
      convTrashPurged: '🧹 Conversation trash cleared',
      trashPurged: '🧹 Trash cleared',
      invalidBatchJson: 'Input JSON must be an ops array, or { "ops": [...] }'
    }
  },

  fsAuditCard: {
    title: 'File operations',

    actions: {
      refresh: 'Refresh'
    },

    states: {
      loading: 'Loading...',
      empty: 'No records yet',
      more: '…{count} more'
    }
  }
}
