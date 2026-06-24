export default {
  header: {
    collapse: '收起右侧栏',
    dockRestore: '复原：库回到中栏',
    dockEnter: '右切换：库拆到右侧栏（右侧阅读 / 中栏对话）',
    dockDisabled: '请先选择一个库或文档后再右切换',
    lightsOn: '开灯（退出专注）',
    lightsOff: '关灯阅读（专注模式）',
    readingOptimizerInactive: '阅读优化器（未启用）',
    readingOptimizerActive: '阅读优化器（{mode}）',
    themeToLight: '切换到亮色',
    themeToDark: '切换到暗色',
    noteOutlineToggleAll: '笔记大纲：全部折叠 / 展开',
    insightsManagedByDock: 'Dock 模式下由右侧阅读面板接管',
    insightsHide: '收起书籍大纲 / QA',
    insightsShow: '展开书籍大纲 / QA',
    settingsHiddenByDock: 'Dock 模式下隐藏设置区',
    settingsHide: '隐藏设置',
    settingsShow: '显示设置',
    paneSwapMobile: '手机：中栏 / 右栏交换',
    outlineHoverOn: '📑 大纲悬停跳转：开启（点击关闭）',
    outlineHoverOff: '📑 大纲悬停跳转：关闭（点击开启）',
    dockIndicator: 'Dock 阅读中'
  },

  dock: {
    emptyTitle: '📚 右侧阅读',
    emptySubtitle: '当前未选择库，请先从左侧进入一个库并选择一本书。'
  },

  outline: {
    hoverEnabledToast: '📑 大纲悬停：已开启',
    hoverDisabledToast: '📑 大纲悬停：已关闭'
  },

  readingOptimizer: {
    title: '🎛️ 阅读优化器',
    actions: {
      close: '关闭',
      saveCurrentAsPreset: '＋ 保存当前为预设',
      setDefault: '设为默认',
      clearDefault: '取消默认',
      deletePreset: '删除',
      save: '保存',
      cancel: '取消',
      reset: '重置',
      disable: '禁用',
      disabled: '已禁用'
    },
    labels: {
      brightness: '字体亮度',
      fontSize: '字体大小',
      lineHeight: '行距',
      padding: '页面留白',
      warmth: '背景暖度',
      smooth: '滚动平滑'
    },
    values: {
      warmthWarm: '暖黄',
      warmthNeutral: '中性',
      warmthCool: '冷白',
      smoothMax: '极致',
      smoothComfort: '舒适',
      smoothFast: '快速'
    },
    sections: {
      professionalPresets: '🎨 专业预设',
      customPresets: '🧩 自定义预设（服务端）'
    },
    presets: {
      standard: '标准',
      eye: '护眼',
      novel: '小说',
      academic: '学术',
      code: '代码'
    },
    custom: {
      namePlaceholder: '预设名称',
      empty: '暂无自定义预设（保存后跨浏览器可见）。',
      defaultBadge: '默认'
    },
    hints: {
      standard: 'Zen'
    },
    status: {
      saved: '已保存',
      reset: '已重置',
      saving: '保存中…',
      savedNamed: '已保存：{name}',
      applied: '已应用',
      defaultNamed: '默认：{name}',
      deleted: '已删除',
      maxCustom: '最多 {count} 个'
    },
    errors: {
      nameRequired: '请输入名称',
      nameTooLong: '最多 18 字',
      nameExists: '名称已存在',
      saveFailed: '保存失败',
      setDefaultFailed: '设置失败',
      clearDefaultFailed: '清除失败',
      deleteFailed: '删除失败'
    },
    modes: {
      standard: '未启用',
      custom: '自定义',
      eye: '护眼',
      novel: '小说',
      academic: '学术',
      code: '代码'
    }
  },

  rss: {
    ragSettings: {
      title: 'RSS 引用范围',
      actions: {
        resetDefaults: '恢复默认'
      },
      hint: '影响 Chat 的 RSS citations / 右侧 RSS 证据卡片；建议保持“严格词面”开启以减少误召回。',
      fields: {
        enabled: '启用 RSS 引用',
        days: '时间范围（天）',
        limit: '条数上限',
        minScore: '相似度阈值',
        strictLexical: '严格词面',
        strictLexicalTitle: '严格关键词匹配；对多语种 / 同义词不友好，但可能更精确。'
      }
    }
  },

  hebbian: {
    unknownSource: '未知来源',
    sourceNote: '笔记',
    sourceGeneric: '来源',
    completedToast: '💡 已根据{sourceLabel}更新概念 / 关系\\\\\\\\n📁 {source}'
  },

  outlineTree: {
    title: '大纲树',
    actions: {
      miniGenerateTitle: '生成大纲时优先使用 mini 模型',
      miniGenerate: 'Mini 生成',
      miniExpandTitle: '展开节点时优先使用 mini 模型',
      miniExpand: 'Mini 展开',
      translating: '翻译中…',
      translateZh: '翻译中文',
      showZhTitle: '显示中文译名标题',
      showZh: '显示中文',
      generateRefresh: '生成 / 刷新',
      expandAll: '全部展开',
      collapseAll: '全部折叠'
    },
    states: {
      unavailable: '请先打开一个库文档后再使用大纲树。',
      loading: '大纲加载中…',
      empty: '（暂无大纲）'
    },
    hint: '支持大纲跳转、远程展开节点与显示中文译名标题。',
    errors: {
      outlineGetFailed: '获取大纲失败。',
      outlineExpandFailed: '展开大纲节点失败。',
      outlineTranslateFailed: '翻译大纲失败。'
    },
    toasts: {
      alreadyExpanded: '该节点已经展开过了。',
      noHeadings: '该节点下没有发现更多标题。',
      miniExpandDone: 'Mini 展开完成 · 预估输入 tokens：{tokens}',
      alreadyTranslated: '该大纲已经翻译为中文。',
      translateDoneWithTokens: '大纲翻译完成 · 预估输入 tokens：{tokens}',
      translateDone: '大纲翻译完成。'
    },
    node: {
      jump: '跳转',
      expandFromNode: '从此节点展开'
    }
  },

  settings: {
    indexGeneration: {
      title: '索引生成',
      forceMini: '索引相关生成强制使用 mini 模型',
      hint: '用于支持 mini 路径的索引或结构生成流程。'
    },
    display: {
      title: '显示',
      showLibraryInsights: '在右侧栏显示 Topic QA',
      hint: '关闭后，右侧栏将隐藏 Topic QA 区块。'
    },
    topicQa: {
      title: 'Topic QA',
      show: '在右侧栏显示 Topic QA',
      hint: '控制右侧栏的 Topic QA 区块。未发布的大纲生成能力在本版本中保持隐藏。'
    },
    outlineMini: {
      title: '大纲 Mini 模型偏好',
      generatePreferMini: '生成大纲时优先使用 mini 模型',
      expandUseMini: '展开大纲节点时优先使用 mini 模型',
      hint: '这些开关只影响大纲生成 / 展开请求，不改动其他模型链路。'
    }
  },

  evidenceCard: {
    title: 'Evidence',
    clear: '清空',
    actions: {
      jump: '跳转',
      copy: '复制'
    },
    hint: {
      cannotJump: '该条 evidence 无法跳转（缺少 library/doc 或 span 为空）。'
    },
    toasts: {
      copied: '已复制',
      copyFailed: '复制失败'
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
    title: '证据',
    meta: {
      rssCount: 'RSS {count}',
      marketCount: 'Market {count}',
      localCount: '本地 {count}',
      localPaused: '本地（已暂停同步）',
      pauseAutoLink: '暂停本地联动',
      resumeAutoLink: '恢复本地联动',
      pauseAutoLinkTitle:
        '暂停：仍会同步展示本地证据，但切换历史对话时不再自动联动跳转（Dock 到右栏时由 CitationList 负责自动联动）',
      resumeAutoLinkTitle:
        '恢复：允许自动联动（Dock 到右栏时由 CitationList 负责自动联动）'
    },
    sections: {
      rssEvidence: 'RSS 证据',
      marketEvidence: '市集证据（本机 / 联邦）',
      localEvidence: '本地证据'
    },
    rss: {
      publish: '上架',
      publishing: '⏳ 上架中',
      publishTitle: '上架到本机 Market',
      publishDisabledTitle: '缺少 object_ref，无法上架'
    },
    market: {
      fallbackTitle: 'Market item',
      peer: 'peer: {peerId}',
      copyRef: '复制 ref'
    },
    local: {
      libraryShort: 'lib',
      docShort: 'doc',
      spanShort: 'span',
      libraryTitle: 'lib {value}',
      docTitle: 'doc {value}',
      spanTitle: 'span {value}',
      syncDisabledHint: '（已在设置中关闭“本地证据随历史对话同步展示”）',
      emptyHint: '（暂无本地证据）'
    },
    publish: {
      missingObjectRef: '❌ 缺少 object_ref（需要形如 rss:{feed_id}/{article_id}）',
      success: '✅ 已上架',
      failedPrefix: '❌ 上架失败：'
    }
  },

  topicQA: {
    title: 'Topic QA',

    actions: {
      collapse: '收起',
      expand: '展开',
      collapseAll: '全部折叠',
      expandAll: '全部展开',
      refresh: '刷新',
      ask: '提问',
      processing: '处理中…',
      loading: '加载中…',
      loadMoreHistory: '加载更多历史',
      backToRecent: '回到最近',
      collapseThread: '收起该线程',
      expandThread: '展开该线程',
      delete: '删除',
      traceSource: '回溯来源',
      followUp: '追问',
      elevateToLibrary: '升维到库',
      elevateToGlobal: '升维到跨库',
      evidence: '证据',
      collapseEvidence: '收起证据',
      details: '详情',
      copy: '复制',
      send: '发送',
      cancel: '取消',
      jump: '跳转'
    },

    scope: {
      doc: 'doc',
      library: 'library',
      global: 'global',
      segmentTitle:
        'store_scope：决定 QA 写入 / 读取位置；evidence_scope：决定证据检索范围（这里保持与 store_scope 一致）'
    },

    placeholders: {
      askDoc: '对这本书提问（Enter 提交）',
      askLibrary: '对本库提问（Enter 提交）',
      askGlobal: '跨库提问（Enter 提交）'
    },

    hints: {
      contextRequired: '（doc scope 需要先打开一本书；library scope 需要先选中一个库）',
      scopeWindow:
        '当前为 store_scope={scope}：默认只显示“最近一部分”；可点“加载更多历史”逐步回看历史；引用 / 证据可点击跳转到来源书段落。',
      loadedStats: '当前已加载：{count} 条 · 扫描 segments：{scanned}/{total}',
      historyReachedEarliest: '（历史已加载到最早）',
      empty: '（暂无问答记录）'
    },

    labels: {
      followUpTag: '↳ 追问'
    },

    meta: {
      threadTitle: 'thread={value}',
      threadSummary: 'Thread · {count} 追问',
      mode: 'mode={value}',
      model: 'model={value}',
      llmOk: 'llm_ok={value}',
      search: 'search={value}',
      storeScope: 'store_scope={value}',
      evidenceScope: 'evidence_scope={value}',
      linkedFrom: '来源={value}'
    },

    badges: {
      llm: 'LLM',
      fallback: 'Fallback',
      qa: 'QA'
    },

    followUp: {
      placeholder: '基于这条回答继续追问（Enter 提交）'
    },

    evidence: {
      title: '关键证据（可跳转）：',
      empty: '（本条记录没有写入 evidence；可先用“引用跳转”。）',
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
      title: '引用：',
      jumpUnknownSpan: '跳转 Span ?',
      jumpWithIds: '跳转 {libraryId}/{docId} · Span {spanIndex}',
      jumpSpan: '跳转 Span {spanIndex}'
    },

    confirm: {
      deleteReply: '删除这条追问（以及它后续的追问）？',
      deleteRoot: '删除这条根问题（以及本线程所有追问）？'
    },

    errors: {
      copyClipboardDenied: '复制失败：浏览器未授权剪贴板权限',
      traceDocMissing: '回溯 doc 需要 from_library_id/from_doc_id，但该记录缺失。',
      qaScopeListNonSuccess: 'qa_scope_list 返回非 success',
      handoffNonSuccess: 'handoff elevate 返回非 success',
      qaAskNonSuccess: 'qa_scope_ask 返回非 success',
      followupNonSuccess: 'followup 返回非 success',
      deleteNonSuccess: 'delete 返回非 success'
    }
  }
}

