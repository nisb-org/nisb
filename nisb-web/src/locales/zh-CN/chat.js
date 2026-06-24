export default {
  toolbar: {
    labels: '标签',
    labelsSeparator: '，',
    manageLabels: '管理当前对话的标签',
    selectConversationFirst: '请选择一个对话后再设置标签',
    expandLeftSidebar: '展开左侧栏',
    expandRightSidebar: '展开右侧栏'
  },

  labelsPanel: {
    title: '对话标签',
    sections: {
      current: '当前标签',
      create: '新建标签'
    },
    states: {
      selectConversationFirst: '请选择一个对话后再设置标签。',
      loading: '⏳ 加载中...',
      empty: '暂无标签，下面可以新建。'
    },
    input: {
      placeholder: '输入标签名后回车...'
    },
    actions: {
      add: '添加',
      clearAll: '清除当前对话的所有标签'
    },
    confirm: {
      clearAll: '确定要清除当前对话的所有标签吗？'
    },
    toast: {
      updateFailed: '更新标签失败：{error}'
    }
  },

  attachments: {
    common: {
      unknownError: '未知错误'
    },

    upload: {
      fileTooLarge: '{name}: 文件过大（限制 5MB）',
      description: '对话附件，上传于 {time}',
      itemFailed: '{name}: {error}',
      mixedAlert: '✅ 成功 {successCount} 个\n❌ 失败 {failCount} 个：\n{errors}',
      failedAlert: '❌ 上传失败：\n{errors}',
      reused: '已复用 {count} 个已存在附件',
      added: '已添加 {count} 个附件'
    },

    picker: {
      selected: '已选择附件：{name}'
    }
  },

  citations: {
    title: '引用',
    sourceCount: '{count} 个来源',
    chipsAria: '引用来源',
    expandDetails: '显示来源',
    collapseDetails: '隐藏来源',

    kind: {
      web: '网页',
      local: '本地'
    },

    fields: {
      library: '库',
      document: '文档',
      span: '片段',
      chunk: '分块',
      page: '页码',
      section: '章节',
      rank: '排序',
      relevance: '相关度',
      url: 'url',
      host: 'host',
      title: 'title',
      libraryId: 'library_id',
      docId: 'doc_id',
      spanIndex: 'span_index',
      chunkId: 'chunk_id',
      score: 'score'
    },

    unavailable: '不可用',
    openSource: '打开来源',
    openWeb: '打开链接',
    openDocument: '打开文档',
    openSpan: '定位片段',

    webFallbackHost: '网页来源',
    defaultDocumentId: '文档',
    rawMetadata: '原始元数据',
    rawUnavailable: '暂无可展示的原始元数据',

    sourceFallback: '来源 {index}',
    webSource: '网页来源',
    localSource: '本地文档',
    quoteTitle: '引用摘录',
    moreSources: '还有 {count} 个来源',

    libraryLabel: '库 {libraryId}',
    documentLabel: '文档 {docId}',
    spanLabel: '片段 {spanIndex}',
    chunkLabel: '分块 {chunkId}',
    pageLabel: '页码 {page}',
    sectionLabel: '章节 {section}',
    scoreLabel: '相关度 {score}',
    rankLabel: '排序 {rank}',

    pageShort: '第 {page} 页',
    relevanceShort: '相关度 {relevance}',

    sourceTypes: {
      web: '网页',
      library: '知识库',
      document: '文档',
      local: '本地',
      unknown: '来源'
    },

    status: {
      stale: '可能已过期',
      unavailable: '来源不可用',
      localEvidenceOff: '本地证据已关闭'
    },
    expandDetails: '展开细节',
    collapseDetails: '收起细节'
  },

  panel: {
    roomOlder: {
      loading: '加载中...',
      loadMore: '加载更早消息',
      noMore: '已无更早消息'
    },
    toolActivity: {
      processing: '工具处理中',
      records: '工具执行记录'
    },
    roomSaveConfirm: {
      defaultPrompt: '请确认保存目标',
      fallbackTarget: '目标文件',
      meta: {
        candidatePath: '候选路径：{path}',
        candidateKind: '候选类型：{kind}',
        lastSaved: '上次保存：{path}'
      },
      actions: {
        processing: '处理中...',
        saveToNote: '存到纪要',
        appendLastNote: '追加到上次纪要',
        cancel: '取消'
      },
      savedToTarget: '已保存到 `{path}`（{targetKind}，{mode}）。'
    },
    controls: {
      collapse: '收起',
      features: '功能'
    },
    summary: {
      room: '房间',
      attachments: '{count} 附件',
      uploading: '上传中',
      thinking: '处理中'
    },
    attach: {
      title: '添加附件',
      uploadingTitle: '上传中...',
      ariaLabel: '添加附件',
      uploadLocal: '📤 上传本地文件',
      pickExisting: '📁 选择已有文件'
    },
    input: {
      roomPlaceholder: '输入房间消息...（如需记录到 notebook，请直接明确告诉 Supervisor）',
      chatPlaceholder: '输入消息... (Ctrl+Enter / ⌘+Enter 发送)'
    },
    actions: {
      stopLocalRuntime: '停止本地运行态',
      send: '发送'
    },
    filePicker: {
      title: '📁 选择已有文件',
      currentDir: '当前目录：',
      goParent: '返回上级目录',
      searchPlaceholder: '🔍 搜索当前目录...',
      loading: '⏳ 加载中...',
      empty: '暂无文件',
      kind: {
        directory: '文件夹',
        file: '文件',
      },
    },
    toast: {
      loadOlderFailed: '加载更早消息失败：{error}',
      refreshRoomFailed: '刷新房间失败：{error}'
    },
    docPanel: {
      returnToReading: '返回连续阅读'
    }
  },

  toolActivity: {
    title: '工具执行',
    empty: '暂无工具执行记录',
    summaryFallback: '暂无预览',
    expand: '展开详情',
    collapse: '收起详情',
    rawPayload: '原始载荷',
    arguments: '参数',
    result: '结果',
    machineFields: '运行字段',

    kind: {
      call: '调用',
      result: '结果'
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
      running: '处理中',
      done: '完成',
      warning: '部分完成',
      error: '失败',
      cancelled: '已取消'
    },

    flags: {
      warning: '警告',
      error: '错误',
      citations: '引用',
      sources: '来源',
      artifacts: '产物',
      externalView: '外部视图',
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
      title: 'MCP 工具',
      subtitle: '当前普通对话的轻量工具入口。Room MCP publish 和 federated MCP 请在 Room 设置中管理。',
      hint: '这里仅展示 V1 已收口的普通对话工具面。高级 runtime 与文件系统权限暂时隐藏。'
    },
    status: {
      serperOn: 'Web search 已开启',
      serperOff: 'Web search 已关闭',
      auditOnly: '文件审计快捷入口'
    },
    sections: {
      webSearch: 'Web search',
      fileAudit: '文件审计'
    },
    fileAudit: {
      hint: '查看集成文件工具产生的操作记录。这个快捷入口不会开启写入权限。'
    },
    button: {
      title: 'MCP 工具开关',
      ariaLabel: 'MCP 工具开关'
    },
    items: {
      serperSearch: 'Serper 搜索',
      serperHint: '允许当前对话通过 MCP 工具桥请求 Web search evidence。',
      codeNetwork: '🌐 代码联网',
      dangerousOps: '🧨 危险操作（递归删目录）'
    },
    readScope: {
      label: '📖 读取范围',
      options: {
        userRo: '用户目录（只读）',
        minimal: '仅 agent_files'
      }
    },
    writeScope: {
      label: '✍️ 写入权限',
      options: {
        none: '关闭写入',
        agentFiles: '仅 agent_files'
      }
    },
    hint: '写入默认关闭；开启后仍只允许在 agent_files 内操作。',
    actions: {
      openAudit: '🧾 文件操作（审计/恢复/批量）'
    }
  },

  attachFromFilesAction: {
    button: {
      ariaLabel: '插入附件占位符',
      tooltip: '插入附件占位符'
    },
    placeholder: {
      pendingUpload: '附件待上传：请在文件侧栏完成上传'
    }
  },

  mcpSerperToggleAction: {
    button: {
      ariaLabel: '切换 Serper 网页搜索',
      tooltip: '允许当前对话通过 MCP 工具桥请求网页搜索',
      label: 'Serper {state}'
    },
    state: {
      on: '开',
      off: '关'
    }
  },

  roomMenu: {
    status: {
      localRoom: '本地 Room',
      federatedRoom: 'Federated · {label}',
      noActiveRoom: 'LLM 对话',
      activeRun: 'run active'
    },
    boundary: {
      title: '能力边界',
      roomRuntime: 'Room runtime',
      roles: 'roles',
      supervisor: 'supervisor',
      federationSnapshot: 'federation snapshot',
      hint: '这里用于进入和创建普通对话中的 Room。Room external MCP publish、token、revoke、expiry、final-only answer 等设置仍在 Room 设置中管理。'
    },
    button: {
      title: 'Room',
      ariaLabel: 'Room 菜单',
      activeTitle: 'Room · {title}',
      text: 'Room',
      on: 'ON'
    },
    header: {
      title: '房间',
      currentMode: '当前模式：'
    },
    modes: {
      room: 'room',
      llm: 'llm'
    },
    actions: {
      refresh: '刷新',
      refreshing: '刷新中...',
      syncCurrent: '同步当前房间',
      syncingCurrent: '同步中...',
      exit: '退出',
      refreshDetails: '刷新详情',
      createAndEnter: '创建并进入',
      processing: '处理中...',
      joinAndEnter: '加入并进入',
      enter: '进入',
      copyRoomId: '复制 room_id',
      copyJoinKey: '复制 join_key',
      copyKey: '复制 key'
    },
    sections: {
      current: '当前房间',
      create: '新建房间',
      join: '加入房间',
      recent: '最近房间'
    },
    current: {
      fallbackTitle: '当前房间',
      federatedLabel: 'Federated · {label}',
      participants: '👥 {count}',
      roles: '🎭 {count}',
      activeRoles: '🧠 {count} 激活',
      supervisorEnabled: 'Supervisor 已开启',
      inheritWorkspaceContext: '继承上下文',
      inheritFocusRoot: '继承焦点',
      defaultRole: '默认角色：{name}',
      runId: 'run_id',
      latestPlan: '最新计划'
    },
    create: {
      titleLabel: 'title',
      titlePlaceholder: '例如：新房间',
      participantsLabel: 'participants（逗号分隔，可空）',
      participantsPlaceholder: 'user_a,user_b',
      defaults: {
        title: '新房间'
      },
      createdRoomId: 'room_id',
      createdJoinKey: 'join_key',
      emptyValue: '—'
    },
    join: {
      roomIdLabel: 'room_id',
      roomIdPlaceholder: 'room_xxx',
      joinKeyLabel: 'join_key',
      joinKeyPlaceholder: '请输入 join_key'
    },
    recent: {
      loading: '正在加载房间...',
      empty: '暂无最近房间。',
      federatedLabel: 'Federated · {label}',
      peerLabel: 'peer_id · {id}',
      peerFallback: 'peer',
      currentBadge: '当前',
      id: 'ID: {id}',
      participants: '👥 {count}'
    },
    footer: {
      closeHint: 'Esc 可关闭菜单；点击空白处也可关闭。'
    },
    errors: {
      operationFailed: '操作失败',
      loadRoomsFailed: '加载房间失败',
      createRoomFailed: '创建房间失败',
      joinRoomFailed: '加入房间失败',
      joinFieldsRequired: 'room_id 和 join_key 不能为空'
    }
  },

  ragMenu: {
    button: {
      ariaLabel: 'RAG 菜单',
      baseLabel: 'RAG {mode}',
      groupedLabel: 'RAG {mode} · 编组 G:{group}',
      scopedLabel: 'RAG {mode} · {scope}',
      libraryToken: 'L:{id}',
      docToken: 'D:{id}'
    },
    common: {
      on: 'On',
      off: 'Off'
    },
    sections: {
      retrievalMode: '检索模式',
      docTime: '文档时间范围',
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
      global: '跨库',
      library: '库',
      doc: '文档',
      groupedInline: '（编组）',
      inline: '（{scope}）'
    },
    items: {
      offHint: '纯对话',
      autoHint: '自动选择 Web 或 Off',
      citeHint: '本地知识库 + 少量引用 {scope}',
      groundHint: '本地知识库 + 强证据 {scope}',
      webHint: '联网搜索，返回真实链接'
    },
    docTime: {
      toggleLabel: 'Doc Time',
      quick: '快捷',
      custom: '自定义',
      daysUnit: '天',
      daysAgoUnit: '天前',
      mode: {
        days: '最近 N 天',
        relative: '相对区间'
      },
      relativeLabels: {
        older: '起点（更早）',
        newer: '终点（较近）'
      },
      inline: {
        days: '最近 {days} 天',
        relative: '{older}~{newer} 天前'
      },
      summary: {
        disabled: '当前未启用文档时间范围。',
        days: '当前范围：最近 {days} 天。',
        relative: '当前区间：{older} 天前 ~ {newer} 天前。'
      },
      effective: {
        localMode: '当前会作用于 {mode} 的本地库检索。',
        savedOnly: '当前仅保存时间设置；切换到 Cite / Ground 后生效。'
      }
    },
    agent: {
      tools: 'Agent 工具',
      planner: 'Planner',
      steps: 'Steps',
      returnDebugTrace: '返回调试轨迹（agent_trace）',
      usePlannerForAnswer: '使用 Planner 模型生成最终回答（仅 Off/Web/Auto）',
      loadFailed: '⚠️ Planner 模型列表加载失败：{error}'
    },
    hint: '点击 Cite / Ground 第一次展开上下文选择器；再次点击可切换“跨库 / 库 / 文档”检索范围。文档时间范围仅作用于本地库检索。'
  },

  ragContextCard: {
    title: 'RAG 上下文',
    modeLabel: '（{mode}）',
    mode: {
      cite: 'Cite',
      ground: 'Ground'
    },
    common: {
      true: 'true',
      false: 'false',
      all: '全部',
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
    relativeRangeLabel: '{older} 天前 ~ {newer} 天前',
    search: {
      libraryPlaceholder: '筛选库...',
      groupPlaceholder: '筛选编组...',
      docPlaceholder: '筛选文档...'
    },
    actions: {
      setGlobalTitle: '切回 global（清空已选库 / 文档 / 编组）',
      clearContextTitle: '清空上下文（library / doc / group → global）',
      closeTitle: '关闭',
      useThisLibraryTitle: '将当前库作为 RAG 上下文',
      useThisLibrary: '使用此库',
      clearGroupOnlyTitle: '仅清空 group_id（保留当前库 / 文档选择）',
      clearGroupOnly: '仅清编组'
    },
    states: {
      loadingLibraries: '⏳ 加载库...',
      emptyLibraries: '（暂无库）',
      loadingGroups: '⏳ 加载编组...',
      emptyGroups: '（暂无编组）',
      noLibrarySelected: '（未选择库）',
      loadingDocuments: '⏳ 加载文档...',
      emptyDocuments: '（该库暂无文档）',
      docLoadFailed: '❌ 加载失败：{error}'
    },
    library: {
      untitled: '未命名库'
    },
    group: {
      title: '编组（group_id）',
      hint: '说明：选择编组后，会清空库 / 文档选择并切到 global；后续检索会在该编组成员范围内过滤。'
    },
    docs: {
      title: '文档',
      clickToSelectAndClose: '点击文档可直接选中并关闭',
      selectLibraryFirst: '先点击左侧一个库',
      defaultFiletype: 'txt'
    },
    current: {
      title: '当前上下文',
      store: 'store: {scope}',
      evidence: 'evidence: {scope}',
      groupId: 'group_id: {value}',
      libraryId: 'library_id: {value}',
      docId: 'doc_id: {value}'
    },
    summary: {
      docTimeTitle: 'Doc 检索时间范围',
      rssTitle: 'RSS 引用范围',
      readOnlySub: '只读',
      readOnlyLabel: '（{value}）',
      enabled: 'enabled: {value}',
      mode: 'mode: {value}',
      days: 'days: {value}',
      range: 'range: {value}',
      limit: 'limit: {value}',
      minScore: 'minScore: {value}',
      strictLexical: 'strictLexical: {value}',
      docTimeHint: '这里只展示当前 Doc-RAG 检索时间范围；正式编辑入口请使用顶部 Doc Time 控制区。',
      rssHint: '这是 RSS live 引用 / 展示范围摘要，不等于 Doc-RAG 检索时间范围。'
    },
    footerHint: '说明：跨库 = global（忽略已选库 / 文档）；库 / 文档模式需要先选中对应库 / 文档。编组会在 global / library 范围内进一步过滤。',
    errors: {
      docStatsFailed: 'nisb_doc_stats 返回失败'
    },
    toast: {
      librarySelected: '✅ 已选择库：{id}',
      docSelected: '✅ 已选择文档：{id}',
      groupSelected: '✅ 已选择编组：{id}',
      groupCleared: '🧹 已清空 group_id',
      switchedGlobal: '🌐 已切回 global（跨库）',
      contextCleared: '🧹 已清空上下文'
    }
  },

  fedMenu: {
    status: {
      marketOn: 'Federation evidence 已开启',
      marketOff: 'Federation evidence 已关闭',
      enabledPeers: '已启用 {count} 个 peer',
      importedInvites: '已导入 {count} 个 invite'
    },
    boundary: {
      title: '能力边界',
      importedRemote: 'imported_remote',
      shareRef: 'share_ref',
      sourceRoomId: 'source_room_id',
      finalOnly: 'final-only',
      sourceObservation: 'source observation boundary',
      hint: 'Consumer room 只能使用 federated final result，不能观察 source room 内部执行过程。'
    },
    button: {
      text: '联邦',
      title: '联邦设置',
      ariaLabel: '联邦设置'
    },
    panel: {
      title: '联邦控制台',
      subtitle: '导入 peer 信息、管理联邦 peers，并接受来自另一台 VPS 的 Room 邀请。'
    },
    market: {
      enableEvidence: '启用市集证据',
      hint: '启用联邦时，可将市集证据纳入对话上下文。'
    },
    peers: {
      title: '联邦 peers',
      disabled: '已禁用',
      tokenMissing: '缺少 token',
      tokenSet: 'token 已设置',
      use: '使用',
      check: '检查',
      checkPeer: '检查 peer',
      checkThisPeer: '检查当前 peer',
      checking: '检查中…',
      editHint: '“使用”只会把已保存 peer 回填到当前表单，用于编辑或覆盖保存。要分享本机 federation info，请使用上方导入区的“复制本机信息”。'
    },
    paste: {
      title: '粘贴联邦信息',
      pasteClipboard: '粘贴剪贴板',
      pasting: '粘贴中…',
      import: '导入',
      importing: '导入中…',
      textareaPlaceholder: '支持 JSON、key:value 多行或原始 Network Header 文本。建议尽量直接粘贴 owner 原样复制的内容。',
      ownerHint: '粘贴 Room owner 发来的 federation info，可导入 peer 或生成邀请草稿。要发给 remote，请复制本机 federation info。',
      copyMyInfo: '复制本机信息',
      copying: '复制中…',
      copyMyInfoTitle: '复制本机 federation info，用于分享给远端 peer',
      recommend: '推荐 owner 复制内容至少包含 peer_id、base_url、token；若同时包含 room_id 和 invite_token，可自动形成 Accept Invite 草稿。',
      draftsTitle: '已导入的邀请草稿',
      unknownPeer: 'peer?',
      roomPrefix: 'room:',
      invitePrefix: 'invite:',
      use: '使用',
      remove: '移除'
    },
    accept: {
      title: '接受 Room 邀请',
      peerPlaceholder: '选择指向 Room owner VPS 的 peer',
      roomIdPlaceholder: 'room_id',
      inviteTokenPlaceholder: 'invite_token',
      remoteUserPlaceholder: 'remote_user_id / user_id',
      remoteLabelPlaceholder: 'remote_label（可选）',
      targetPeerPlaceholder: 'target_peer_id（可选，粘贴导入时通常自动带入）',
      accepting: '接受中…',
      submit: '接受邀请并进入 Room',
      retry: '重试上次接受',
      notePeer: '这里选择的是本机指向 Room owner VPS 的 peer_id，不是 owner 创建 invite 时写入的 target_peer_id。',
      noteTarget: '如果 owner 发来的结构化文本包含 target_peer_id，粘贴导入后通常会自动回填。',
      joinedNote: '已加入的 federated Room 会写入 Room 菜单底部的 recent 区块，后续可直接从列表重进。',
      exitNote: '当前会继续自动进入该 Room；如果之后执行 exit room，只会清除 current，不会移除 recent 记录。'
    },
    form: {
      title: '新增 peer',
      peerIdPlaceholder: 'peer_id（例如 vps-b）',
      baseUrlPlaceholder: 'base_url（例如 https://b.example.com）',
      tokenPlaceholder: 'token（可空）',
      labelPlaceholder: 'label（可空）'
    },
    actions: {
      refresh: '刷新',
      loadingShort: '⏳',
      save: '保存',
      saving: '⏳ 保存中'
    },
    states: {
      loading: '加载中...',
      emptyPeers: '暂无 peers。可在下方新增，或从上方导入 federation info。'
    },
    messages: {
      requiredFields: 'peer_id / base_url 不能为空',
      saved: '✅ 已保存',
      saveFailed: '保存失败'
    },
    runtime: {
      copyEmptyText: '没有可复制的内容。',
      copyFailed: '复制失败。',
      copyMissingPeerId: '复制前请先填写当前 owner 的 peer_id；后续可直接复用当前页 token 与 origin。',
      copyMissingBaseUrl: '当前页面 base_url 读取失败。',
      copyMissingToken: '当前登录 token 读取失败；请确认已登录，或先在表单中临时填入 token。',
      copyInfoOk: '已从当前页面上下文复制 federation info。',
      requiredPeerBaseUrl: 'peer_id / base_url 必填。',
      savePeerFailed: '保存 peer 失败。',
      peerSaved: 'Peer 已保存。',
      peerSavedRetryReady: 'Peer 已保存。token 已更新，可直接重试 Accept。',
      clipboardNotSupported: '当前环境不支持直接读取剪贴板，请手动粘贴到文本框。',
      clipboardEmpty: '剪贴板当前为空。',
      clipboardReadFailed: '读取剪贴板失败，请手动粘贴。',
      pasteRequired: '请先粘贴 federation info。',
      noImportableFields: '未识别到可导入字段，请检查文本格式。',
      peerSavedUpdated: 'peer {peerId} 已保存/更新',
      inviteDraftImported: 'invite draft 已导入并自动回填到 Accept Invite',
      peerFormFilled: '已解析并回填 peer 表单',
      inviteFormFilled: '已尽量回填 invite 表单',
      federationInfoParsed: '已解析 federation info',
      messageSeparator: '；',
      missingPeerIdHint: '已识别 base_url 与 token，但缺少 peer_id；请补一个本机用于保存该 owner 的 peer_id。',
      peerInviteReadyWithTarget: 'peer 已更新，invite 已回填；target_peer_id 也已带入，现在可直接 Accept。',
      peerInviteReadyMissingTarget: 'peer 已更新，invite 已回填；target_peer_id 为空，请核对 owner 发来的 invite 文本。',
      peerReadyAwaitInvite: 'peer 已可用；若房主随后再发 room_id / invite_token，继续原样粘贴即可覆盖并补全。',
      inviteReadyWithTarget: 'invite 已导入；target_peer_id 也已回填。',
      inviteReadyMissingTarget: 'invite 已导入；但未识别到 target_peer_id，请核对 owner 文本。',
      peerHealthOk: 'Peer {peerId} health ok。',
      peerHealthFailed: 'Peer {peerId} health check failed。',
      missingRoomId: '缺少 room_id',
      requiredInviteFields: 'peer_id / room_id / invite_token / remote_user_id 必填。',
      acceptRoomMissingRoomId: 'accept 成功，但缺少 room_id'
    },
    inviteErrors: {
      tokenInvalid: 'peer token 无效或已过期，请先更新 token。',
      ownerUnreachable: 'owner VPS 当前不可达，请检查 base_url / 服务状态。',
      permissionDenied: '当前 token 权限不足，无法访问该 invite 或房间。',
      roomNotFound: 'owner VPS 上未找到该房间。',
      inviteExpired: 'invite 已过期，需要房主重新签发。',
      inviteNotActive: 'invite 已失效或已被使用。',
      peerMismatch: '当前 peer 与 invite 不匹配，请核对 peer_id / target_peer_id。',
      inviteNotFound: 'invite 不存在或当前 peer 不匹配。',
      peerNotFound: 'peer 不存在或已禁用。',
      acceptFailed: 'accept invite failed'
    },
    inviteHints: {
      tokenInvalid: '更新当前 peer 的 token 后，直接点 Retry Last Accept 即可，无需重建 invite。',
      ownerUnreachable: '这不是权限问题；owner VPS 服务恢复后可直接重试。',
      inviteExpired: '这类错误不能靠重试修复，需要房主重新签发 invite。',
      inviteNotActive: '这类错误不能靠重试修复，需要房主重新签发 invite。',
      peerMismatch: '重点核对当前选择的 peer_id，以及 owner 文本里携带的 target_peer_id。'
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
      acceptedRoomInvite: '已接受房间邀请，正在进入 federated room。'
    },
    hint: '已勾选的 peers 会随每次对话传给 orchestrate。Federation 不会暴露 source Room 的内部执行过程。'
  },

  fsAuditModal: {
    title: '文件操作',
    subtitle: '从普通对话 MCP 快捷入口打开的文件审计与恢复工具。',
    status: {
      audit: '审计记录',
      recovery: '恢复工具',
      confirmRequired: '危险操作需要确认'
    },
    actions: {
      refresh: '刷新',
      close: '关闭',
      search: '搜索',
      loadMore: '加载更多',
      restore: '恢复',
      restoreThisItem: '恢复此项',
      restoreBatch: '恢复本批次',
      purgeBatch: '清空批次',
      restoreRename: '恢复命名',
      expand: '展开',
      collapse: '收起',
      previousPage: '上一页',
      nextPage: '下一页'
    },
    tabs: {
      ariaLabel: '文件工具分区',
      audit: '审计记录',
      files: '当前文件',
      trash: '回收站',
      batch: '批量执行'
    },
    common: {
      deleteConfirmToken: '删除',
      loading: '加载中...',
      loadingAscii: '加载中...',
      page: '第 {page} 页',
      unknownError: '未知错误'
    },
    audit: {
      prefix: '前缀',
      prefixPlaceholder: '例如 agent_files/notes（可空）',
      limit: '条数',
      searchLabel: '搜索',
      searchPlaceholder: '关键字（命中 operation/paths/metadata），留空=tail',
      filterSummary: '过滤：keyword="{keyword}"，显示 {shown} / 原始 {total}',
      metadata: '元数据',
      empty: '暂无记录（或无匹配）',
      footer: '说明：这里是“审计事件”，不等价于当前文件是否存在；请用“当前文件/回收站”Tab 查看现状。',
      restoreRenameTitle: '将 new_path 改回 old_path（同时刷新常用/目录树/聚焦目录）',
      restoreBackupTitle: '从备份恢复该路径',
      backupPurged: '（备份已清理）',
      backups: {
        title: '备份(.backups)',
        loading: '统计中…',
        notCounted: '未统计',
        statsText: '{count} 个，约 {size}',
        refreshStats: '刷新统计',
        purgeAll: '清空可恢复备份'
      }
    },
    files: {
      depth: '深度',
      includeHidden: '包含隐藏(.trash)',
      refreshSnapshot: '刷新快照',
      snapshotMeta: 'root={root} ts={ts}',
      emptyTree: '（空）'
    },
    trash: {
      bytes: '{size} bytes',
      filter: '筛选',
      filterPlaceholder: '输入文件名/路径子串',
      refreshTrash: '刷新回收站',
      itemType: 'trash',
      trashPath: 'trash: {path}',
      originalPathDerived: '原路径推导：{path}',
      emptyFiltered: '回收站为空或无匹配项',
      footer: '说明：删除默认是“软删除→回收站”，所以删除后文件不会出现在 agent_files 根目录里。',
      batch: {
        title: '🧺 批次回收站（目录/多项）',
        searchPlaceholder: '搜索 bulk_id / 路径关键字',
        purgeAll: '清空回收站',
        empty: '（暂无批次删除记录）',
        bulkId: 'bulk_id: {id}',
        itemsCount: '{count} 项',
        bucket: 'bucket: {path}',
        searchInBatchPlaceholder: '在本批次内搜索路径',
        emptyDetail: '（无匹配条目）'
      },
      conversation: {
        title: '💬 对话回收站',
        searchPlaceholder: '搜索 名称 / bulk_id / conv_id',
        purgeAll: '清空回收站',
        empty: '（暂无对话批次）',
        bulkId: 'bulk_id: {id}',
        itemsCount: '{count} 项',
        displayName: '名称：{name}',
        convId: 'conv_id：{id}',
        bucket: 'bucket：{path}',
        searchInBatchPlaceholder: '在本批次内搜索路径',
        emptyDetail: '（无匹配条目）'
      }
    },
    batch: {
      dryRun: 'dry-run（只校验不落盘）',
      stopOnError: '遇错停止',
      run: '执行',
      templateCreateOnly: '模板：只创建',
      templateCreateUpdate: '模板：创建+更新',
      templateDemoDelete: '模板：演示删除进回收站',
      confirmLabel: 'confirm（可选）',
      confirmPlaceholder: '例如 DELETE（仅危险操作时）',
      resultMeta: 'batch_id={batchId} dry_run={dryRun}',
      footer: '提示：执行后会自动刷新“当前文件/回收站/审计”，避免“看不到变化”。'
    },
    prompts: {
      restoreDirRename:
        '恢复目录命名？\\n\\n将把：\\n{from}\\n改回：\\n{to}\\n\\n（会同步刷新目录树/常用/聚焦目录）',
      purgeAllBackups:
        'Type delete to permanently purge ALL restorable backups.\\n\\n（也可输入：删除）',
      purgeTrashBatch:
        'Type delete to permanently purge batch {id}.\\n\\n（也可输入：删除）',
      purgeTrashAll:
        'Type delete to permanently clear the trash.\\n\\n（也可输入：删除）',
      purgeConvBatch:
        'Type delete to permanently purge conversation batch {id}.\\n\\n（也可输入：删除）',
      purgeAllConvTrash:
        'Type delete to permanently clear all conversation trash.\\n\\n（也可输入：删除）'
    },
    messages: {
      restoreFailed: '恢复失败',
      restoreFailedWithError: '恢复失败：{error}',
      purgeFailed: '清空失败',
      purgeFailedWithError: '清空失败：{error}',
      backupRestored: '✅ 已恢复备份',
      renameRestored: '✅ 已恢复目录命名',
      restoreRenameFailed: '恢复命名失败',
      statsFailed: '统计失败',
      purgeBackupsFailed: '清空备份失败',
      backupsPurged: '🧹 已清空可恢复备份',
      loadBatchDetailFailed: '加载批次详情失败：{error}',
      batchRestored: '✅ 已恢复批次：{id}',
      itemRestored: '✅ 已恢复：{path}',
      batchPurged: '🧹 已清空批次：{id}',
      restored: '✅ 已恢复',
      loadConvBatchDetailFailed: '加载对话批次详情失败：{error}',
      convBatchRestored: '✅ 已恢复对话批次：{id}',
      convBatchPurged: '🧹 已清空对话批次：{id}',
      convTrashPurged: '🧹 已清空对话回收站',
      trashPurged: '🧹 已清空回收站',
      invalidBatchJson: '输入 JSON 必须是数组 ops，或 { "ops": [...] }'
    }
  },

  fsAuditCard: {
    title: '文件操作',

    actions: {
      refresh: '刷新'
    },

    states: {
      loading: '加载中...',
      empty: '暂无记录',
      more: '…还有 {count} 项'
    }
  }
}

