import library from './zh-CN/library.js'
import files from './zh-CN/files.js'
import timelineRuntime from './zh-CN/timeline-runtime.js'
import rss from './zh-CN/rss.js'
import feed from './zh-CN/feed.js'
import chat from './zh-CN/chat.js'
import room from './zh-CN/room.js'
import rightSidebar from './zh-CN/right-sidebar.js'

export default {
  common: {
    close: '关闭',
    unknownError: '未知错误'
  },

  settings: {
    title: '设置',
    common: {
      save: '立即保存并应用',
      reset: '恢复默认值'
    },
    tabs: {
      ariaLabel: '设置选项卡',
      chat: '聊天',
      models: '模型',
      performance: '性能',
      files: '文件',
      language: '语言',
      about: '关于'
    },
    about: {
      placeholder: '后续会继续在这里补充新的设置项，包括联动、性能和实验功能。'
    },
    language: {
      title: '界面语言',
      description: '切换应用界面语言。第一阶段支持简体中文与英文。',
      zhCN: '简体中文',
      en: 'English',
      immediate: '切换后立即生效，无需刷新页面。',
      fallbackHint: '如果英文翻译缺失，将自动回退到默认中文文案。'
    },
    chat: {
      autoTranslate: {
        label: '自动将提示词翻译为英文，以获得更好的检索与引用效果',
        hint: '适合纯文本提示词。引用 agent_files/... 这类文件路径或使用附件时建议关闭，避免路径和文件名被改写，导致文件 / 证据丢失。'
      },
      translateModel: {
        label: '当前翻译模型',
        goToModels: '前往模型标签编辑',
        hint: '翻译模型现在统一在模型标签下管理。'
      }
    },
    models: {
      common: {
        currentCustom: '当前自定义',
        customModelName: '自定义模型名'
      },
      catalog: {
        label: '可用模型',
        loading: '加载中...',
        refresh: '刷新模型列表',
        hint: '模型列表直接来自后端动态注册表，仅显示当前后端可用的 provider/model 条目。',
        errorPrefix: '加载失败：'
      },
      conversation: {
        label: 'AI 对话模型',
        placeholder: '例如：gpt-4.1-mini / claude-sonnet-4-5-20250929',
        hint: '这是默认的 AI 对话模型。未来 room 提示词、Supervisor 流程和角色回复也应读取这个统一值。'
      },
      translate: {
        label: '翻译模型',
        placeholder: '留空时默认使用 gpt-4o-mini',
        hint: '用于自动将提示词翻译为英文。保存时如果留空，会回退到 gpt-4o-mini。'
      }
    },
    files: {
      common: {
        listSeparator: '、'
      },
      currentWorkspace: {
        label: '当前工作空间',
        refresh: '刷新列表',
        hint: '已保存快照 = 你明确保存到工作空间的状态；当前状态 = 你在文件树里临时改出的状态。'
      },
      manage: {
        label: '工作空间管理',
        iconChoicesAria: '工作空间图标选项',
        renamePlaceholder: '重命名当前工作空间',
        rename: '重命名',
        delete: '删除',
        hint: '删除为软删除，只会把工作空间移到后端 .trash；默认工作空间不可删除。'
      },
      create: {
        label: '创建新工作空间',
        iconChoicesAria: '新工作空间图标选项',
        placeholder: '例如：Personal / Project A / Paper',
        submit: '保存并创建',
        hint: '创建后会自动刷新列表并切换到新工作空间。'
      },
      snapshotFocus: {
        label: '快照聚焦目录',
        placeholder: '例如：books 或 agent_files/docs'
      },
      snapshotFavorites: {
        label: '快照收藏',
        refreshPreview: '刷新预览',
        copyCurrentLinks: '复制当前收藏链接',
        preview: '预览（最多 8 个）：{items}',
        empty: '当前快照还没有收藏项。请先在文件树里添加收藏，再点击保存到工作空间。'
      },
      actions: {
        readCurrentFocus: '读取当前聚焦目录',
        applyToUi: '应用到 UI',
        saveToWorkspace: '保存到工作空间',
        clearWorkspaceState: '清空工作空间文件状态',
        clearHint: '清空会同时抹掉已保存快照和当前状态：focus 变为空、收藏被清除，旧的全局收藏也不会再自动回填。'
      }
    },
    performance: {
      sync: {
        label: '保持本地证据与历史对话同步',
        hint: '关闭后，右侧 Local Evidence 面板将不再随着你切换历史对话而刷新，从而减少切换开销。'
      },
      autoSelect: {
        label: '自动跳转到库 / 文档 / span，并选中第一条本地证据',
        hint: '关闭后，本地证据仍会保持同步，但不会自动跳到库。手动点击仍然可用。'
      }
    }
  },

  selectionTranslate: {
    fab: {
      title: '翻译选中文本',
      label: '译'
    },
    modal: {
      title: '划词翻译',
      version: 'v-simple-20251220-0848',
      close: '关闭'
    },
    source: {
      label: '原文'
    },
    translation: {
      label: '译文'
    },
    target: {
      label: '目标：'
    },
    actions: {
      showPhonetics: '显示音标',
      loadingPhonetics: '获取音标中…',
      speakSource: '▶ 播读原文',
      speakExample: '播读例句',
      generating: '生成中…',
      copySource: '复制原文',
      copyBoth: '复制原文+译文',
      retranslate: '重新翻译'
    },
    status: {
      translating: '⏳ 翻译中…',
      empty: '（暂无）',
      cacheHit: '命中缓存'
    },
    dict: {
      meaning: '释义',
      examples: '例句',
      notes: '说明'
    },
    mode: {
      dict: '字典风格（词 / 短语 / 短句）',
      chunks: '忠实翻译（段落 / 长句自动分段）'
    },
    toast: {
      translateFailed: '翻译失败：{error}',
      phoneticsEnglishOnly: '当前仅支持英文音标',
      phoneticsNonEnglish: '当前文本不像英文，暂不支持音标',
      phoneticsFailed: '获取音标失败：{error}',
      ttsFailed: 'TTS 失败：{error}',
      autoplayBlocked: '浏览器阻止自动播放，请点一下音频控件播放',
      sourceCopied: '已复制原文',
      translatedCopied: '已复制原文+译文'
    },
    copy: {
      sourceLabel: '【原文】',
      translationLabel: '【译文】',
      examplesLabel: '【例句】',
      notesLabel: '【说明】'
    },
    languages: {
      'zh-CN': '中文（简体）',
      'zh-TW': '中文（繁体）',
      en: 'English',
      ja: '日本語',
      ko: '한국어',
      fr: 'Français',
      de: 'Deutsch',
      es: 'Español',
      'pt-BR': 'Português (Brasil)',
      it: 'Italiano',
      ru: 'Русский',
      ar: 'العربية'
    }
  },

  sidebar: {
    tabs: {
      conversations: '对话',
      files: '文件',
      libraries: '库',
      timeline: '时间线',
      rss: 'RSS'
    },
    actions: {
      search: '搜索',
      uploadFile: '上传文件到当前目录',
      uploadDirectory: '递归上传目录并保留其层级到当前目录下',
      collapse: '收起左侧栏'
    },
    search: {
      open: '搜索',
      title: '搜索',
      placeholder: '🔍 搜索对话、目录、文件、库（含书名）...',
      loading: '⏳ 搜索中...',
      initialTitle: '💡 输入关键词搜索全部内容',
      initialHint: '支持搜索：对话标题/内容、目录名/目录路径、文件（文件名+内容）、库名/书名',
      noCategoryTitle: '🧭 请至少开启一种搜索类型',
      noCategoryHint: '可用顶部按钮控制四类结果是否纳入搜索，当前偏好仅保存在本机',
      emptyTitle: '😔 未找到相关结果',
      emptyHint: '尝试使用其他关键词；已自动进行空格归一、近似匹配与排序优化',
      normalizedQuery: '已按归一化查询搜索：{query}',
      sections: {
        chat: '💬 对话 ({count})',
        dirs: '📁 目录 ({count})',
        files: '📄 文件 ({count})',
        library: '📚 库 / 书籍 ({count})',
        global: '📈 全部展开'
      },
      actions: {
        openDebug: '打开调试面板',
        closeDebug: '关闭调试面板',
        debugOn: '调试开',
        debugOff: '调试关',
        collapse: '收起',
        expand: '展开',
        collapseDebug: '收起调试',
        expandDebug: '展开调试',
        expandChat: '📄 展开对话 +{count}',
        expandDirs: '📁 展开目录 +{count}',
        expandFiles: '📄 展开文件 +{count}',
        expandLibrary: '📄 展开库 +{count}',
        expandAll: '四类同时 +{count}'
      },
      messages: {
        completed: '搜索完成'
      },
      results: {
        newConversation: '新对话',
        messageCount: '{count} 条消息',
        unnamedFile: '未命名文件',
        unnamedDirectory: '未命名目录',
        focusToFiles: '— 聚焦到文件空间',
        unnamed: '未命名'
      },
      debug: {
        infoTitle: '调试信息',
        devObservation: '开发态搜索观测'
      },
      controls: {
        modules: {
          chat: '对话',
          dirs: '目录',
          files: '文件',
          library: '书库'
        },
        presets: {
          all: '全部',
          workspace: '文件空间',
          reset: '重置'
        },
        hint: '固定顺序：对话 / 目录 / 文件 / 书库；筛选偏好仅保存在本机'
      },
      match: {
        bases: {
          title: '标题',
          content: '内容',
          filename: '文件名',
          directory: '目录',
          directoryName: '目录名',
          directoryPath: '目录路径',
          libraryName: '库名',
          libraryDescription: '库描述',
          book: '书籍',
          hit: '命中'
        },
        reasons: {
          fuzzy: '近似',
          prefix: '前缀',
          exact: '精确',
          compact: '紧凑',
          substring: '包含',
          tokens: '分词'
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
      settings: '设置',
      operationFailed: '操作失败',
      operationCompleted: '操作完成',

      loadModelCatalogFailed: '加载模型目录失败',
      loadWorkspacesFailed: '加载工作空间失败',
      loadWorkspacesException: '加载工作空间异常：{error}',

      getCurrentStateFailed: '获取工作空间当前状态失败',
      restoreSnapshotSuccess: '已恢复工作空间快照',
      restoreSnapshotFailed: '恢复工作空间快照失败',
      restoreSnapshotException: '恢复工作空间快照异常：{error}',
      switchRestoring: '已切换工作空间：{name}（正在恢复快照）',
      invalidWorkspaceIdRestore: 'workspace_id 无效，无法恢复快照',
      invalidWorkspaceIdSwitch: 'workspace_id 无效，无法切换',
      restoreRoomWorkspaceSuccess: '已恢复房间绑定的完整工作空间文件状态',
      applyRoomFocusSuccess: '已应用房间聚焦目录到左侧栏',
      clearRoomFocusSuccess: '已清空左侧栏的房间聚焦 root',
      applyRoomContextFailed: '应用房间 workspace_context 失败：{error}',

      invalidWorkspaceId: 'workspace_id 无效',
      invalidWorkspaceIdCopy: 'workspace_id 无效，无法复制',
      invalidWorkspaceIdRefresh: 'workspace_id 无效，无法刷新',
      invalidWorkspaceIdSave: 'workspace_id 无效，无法保存',
      invalidWorkspaceIdApply: 'workspace_id 无效，无法应用',
      invalidWorkspaceIdClear: 'workspace_id 无效，无法清空',

      enterWorkspaceName: '请输入工作空间名称',
      createWorkspaceFailed: '创建工作空间失败',
      createWorkspaceNoId: '创建失败：未返回 workspace_id',
      workspaceCreated: '已创建工作空间：{id}',
      createWorkspaceException: '创建异常：{error}',

      enterNewName: '请输入新名称',
      renameWorkspaceFailed: '重命名工作空间失败',
      workspaceRenamed: '已重命名工作空间',
      renameWorkspaceException: '重命名异常：{error}',

      defaultWorkspaceDeleteDenied: '默认工作空间禁止删除',
      deleteWorkspaceConfirm: '确认删除该工作空间？\n\n删除为软删除（移动到后端 .trash）。',
      deleteWorkspaceFailed: '删除工作空间失败',
      workspaceDeleted: '已删除（已移入 .trash）',
      deleteWorkspaceException: '删除异常：{error}',

      focusRead: '已读取当前聚焦：{path}',
      focusEmpty: '当前聚焦为空',
      focusReadFailed: '读取当前聚焦失败',

      getCurrentFavoritesFailed: '获取当前常用失败',
      currentFavoritesEmpty: '当前常用为空',
      favoriteDirectoriesHeading: '## 常用目录（{count}）',
      favoriteFilesHeading: '## 常用文件（{count}）',
      copiedFavoriteLinks: '✅ 已复制当前常用内部链接：目录 {dirs} + 文件 {files}',
      clipboardDenied: '复制失败：浏览器不允许剪贴板',
      copyFailed: '复制失败：{error}',

      refreshWorkspaceFilesStateFailed: '刷新工作空间文件状态失败',
      refreshFailed: '刷新失败：{error}',

      updateCurrentStateFailed: '更新当前态失败',
      saveSnapshotFailed: '固化快照失败',
      snapshotSaved: '已保存为工作空间快照',
      saveFailed: '保存失败：{error}',

      applyWorkspaceFilesStateFailed: '应用工作空间文件状态失败',
      appliedToUi: '已恢复并应用到界面',
      applyFailed: '应用失败：{error}',

      clearWorkspaceFilesStateConfirm: '确认清空该工作空间的“快照 + 当前态”？\n\n此操作会把聚焦设为空，并清空常用列表。',
      clearWorkspaceFilesStateFailed: '清空工作空间文件状态失败',
      workspaceFilesStateCleared: '已清空工作空间文件状态',
      clearFailed: '清空失败：{error}'
    },
    conversations: {
      title: '历史对话',
      create: '新建对话',
      newConversation: '新对话',
      filterByLabel: '按标签筛选对话',
      rename: '重命名',
      delete: '删除',
      undo: '撤销',
      loading: '⏳ 加载对话...',
      empty: '（暂无对话）',
      loadMore: '更多',
      loadMoreLoading: '⏳ 加载更多…',
      reachedEarliest: '已到最早',
      turnCount: '{count} 条',
      labels: {
        title: '对话标签',
        all: '全部',
        unlabeled: '未分组',
        loading: '⏳ 加载标签...',
        empty: '暂无标签'
      },
      tooltip: {
        id: 'conv_id: {id}',
        time: '时间: {time}',
        labelsWithItems: '标签: {items}',
        labelsEmpty: '标签:（无）',
        labelSeparator: '、'
      },
      messages: {
        createFailed: '创建对话失败：{error}',
        renamePrompt: '请输入新标题:',
        renameFailed: '重命名失败：{error}',
        deleteFailed: '删除失败：{error}',
        movedToTrash: '✅ 对话已移入回收站：{name}\n批次：{bulkId}',
        undoFailed: '撤销失败：{error}',
        undoSuccess: '✅ 已撤销删除（对话已恢复）'
      }
    }
  },

  note: {
    toolbar: {
      tab: '笔记',
      expandLeftSidebar: '展开左侧栏',
      expandRightSidebar: '展开右侧栏',
      switchToEdit: '编辑',
      switchToPreview: '显示',
      goBackWithShortcut: '返回上一个打开的文件（{shortcut}）',
      goForwardWithShortcut: '前进到下一个文件（{shortcut}）',
      copyInternalLink: '复制本文档内部链接（Markdown）',
      copiedInternalLink: '已复制内部链接（Markdown）',
      addToFavorites: '设为常用',
      removeFromFavorites: '取消常用',
      focusCurrentDirectory: '聚焦当前文档所在目录',
      focusDirectoryTo: '◉ 聚焦到所在目录：{path}',
      clearDirectoryFocus: '○ 取消聚焦（回到根目录）',
      focusedDirectoryToast: '◉ 已聚焦目录：{path}',
      clearedDirectoryToast: '○ 已取消聚焦（回到根目录）',
      saveSaving: '保存中…',
      saveSaved: '已保存',
      savePending: '未保存，点击立即保存',
      newNote: '新建笔记',
      publish: '发布',
      publishing: '发布中…',
      publishCurrentNoteToFeed: '发布当前笔记到公共广场（Feed）',
      noteToBrain: '进脑',
      noteToBrainDone: '已进脑',
      noteToBrainProcessing: '处理中...',
      noteToBrainHint: '笔记进脑（概念抽取+建图）',
      noteToBrainLastTime: '上次进脑：{time}',
      defaultDocumentName: '文档'
    },
    preview: {
      pdfTitle: 'PDF 预览',
      pdfLoading: '⏳ PDF 加载中...',
      imageDefaultName: '图片'
    },
    reader: {
      lazyMarkdown: {
        loading: '继续加载中…',
        reachedEnd: '已到达文档末尾',
        renderFailed: 'Markdown 渲染失败'
      },
      virtualText: {
        wrapOnTitle: '当前：自动换行。点击改为不换行。',
        wrapOffTitle: '当前：不换行。点击改为自动换行。',
        wrapOn: '↩︎ 换行',
        wrapOff: '↔ 不换行',
        scrollHintTitle: '立即渲染当前位置',
        scrollHint: '滚动中，松手渲染当前',
        indexingTitle: '正在建立行索引，不会阻塞 UI',
        indexing: '索引中…'
      },
      epub: {
        prevPage: '上一页',
        nextPage: '下一页',
        prevPageShort: '◀ 页',
        nextPageShort: '页 ▶',
        prevChapter: '上一章',
        nextChapter: '下一章',
        prevChapterShort: '◀ 章',
        nextChapterShort: '章 ▶',
        reload: '重新加载 EPUB',
        loading: '⏳ 正在加载 EPUB…',
        empty: '请选择一个 EPUB 文件打开。',
        renderFailed: 'EPUB 渲染失败：{error}'
      }
    },
    editor: {
      foldAll: '⊟ 折叠',
      foldAllTitle: '折叠全部 (Ctrl+Shift+[)',
      unfoldAll: '⊞ 展开',
      unfoldAllTitle: '展开全部 (Ctrl+Shift+])',
      toggleLineNumbersTitle: '切换行号显示',
      showLineNumbers: '显示行号',
      hideLineNumbers: '隐藏行号',
      toggleLineWrappingTitle: '切换自动换行',
      enableLineWrapping: '启用换行',
      disableLineWrapping: '禁用换行',
      stats: {
        words: '字',
        chars: '字符',
        lines: '行'
      }
    },
    messages: {
      internalLinkResolveFailed: '内部链接无法解析。',
      epubLoading: '⏳ 正在加载 EPUB…',
      epubOpenFailed: 'EPUB 打开失败：{error}',
      imagePasteNeedsSavedNote: '请先保存笔记后再粘贴图片，这样才能确定 images/ 落盘目录。',
      imageInserted: '图片已插入。',
      pasteImageFailed: '粘贴图片失败。',
      dropImageFailed: '拖放图片失败。'
    },
    controller: {
      defaultContent: '# Zen 编辑器\n\n开始写作...',
      libraryDockedToast: '📚 库已拆到右侧栏：右侧阅读 / 中栏对话',
      libraryRestoredToast: '↩ 已复原：库回到中栏',
      modeLabels: {
        chat: '对话',
        feed: '广场',
        library: '资料库',
        note: '笔记',
        other: '其它内容'
      },
      unsavedLeaveConfirm: '当前笔记有未保存的修改，继续将放弃这些修改，是否继续？',
      newNoteTemplate: '# 新笔记 {timestamp}\n\n',
      selectConversationFirst: '请先在左侧选择一个历史对话',
      publishNoFile: '没有可发布的文件。',
      publishMarkdownOnly: '只有 Markdown 笔记可以发布。',
      publishEmptyContent: '内容为空。',
      publishSaveFailedContinue: '保存失败，仍继续发布…',
      publishFailed: '发布失败。',
      publishSuccess: '已发布到广场。',
      untitled: '未命名'
    },
    navigation: {
      restoreFederatedRoomFailed: 'Federated room 上下文恢复失败，请从 recent 重新进入。',
      restoreCurrentRoomFailed: '恢复当前房间失败。',
      defaultTargetLabel: '其它内容',
      currentNote: '当前笔记',
      unsavedNewNoteConfirm: '{name} 还没有保存为文件。\n\n继续前往“{target}”会丢失当前未保存内容。\n\n确定：放弃并继续\n取消：留在当前笔记',
      unsavedRetrySaveConfirm: '{name} 有未保存修改。\n\n确定：立即保存并继续前往“{target}”\n取消：进入放弃确认',
      saveFailedKeepUnsaved: '保存失败，仍保留未保存修改。',
      unsavedDiscardConfirm: '{name} 仍有未保存修改。\n\n确定：放弃修改并继续前往“{target}”\n取消：留在当前笔记',
      previousFile: '上一个文件',
      nextFile: '下一个文件'
    },
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

