export default {
  favorites: {
    title: '★ 常用',
    emptyHint: '（暂无常用；右键文件/目录 → 设为常用）',
    directories: '目录',
    files: '文件',
    focus: '◉ 聚焦',
    unfocus: '○ 取消聚焦',
    remove: '取消常用'
  },
  highlight: {
    title: '置顶高亮',
    clear: '清除高亮',
    highlightedAs: '已高亮为：{color}',
    colors: {
      amber: '琥珀',
      blue: '蓝色',
      emerald: '翠绿',
      violet: '紫色',
      rose: '玫红',
      cyan: '青色',
      slate: '灰蓝'
    }
  },
  root: {
    userLabel: 'user',
    userTitle: 'user',
    userTitleWithSlash: 'user/'
  },
  loading: '（加载中…）',
  empty: '（目录为空）',
  actions: {
    collapseAllDirs: '折叠所有目录',
    createInCurrentDir: '在当前目录新建'
  },
  upload: {
    unknownError: '未知错误',
    chunkedDone: '分片上传完成',
    fileTooLarge: '{name}: 文件过大（限制 {limit}MB）',
    uploadedAt: '上传于 {time}',
    directoryUploadedAt: '目录上传于 {time}',
    fileSuccessLine: '成功上传 {count} 个文件',
    fileFailureBlock: '失败 {count} 个：\n{errors}',
    fileDone: '上传完成',
    directorySummary: '目录上传完成\n成功文件：{count} 个',
    directoryFailureBlock: '失败文件：{count} 个\n{errors}'
  },
  settings: {
    title: '文件空间设置',
    hoverExpand: '目录悬停自动展开',
    hoverExpandHint: '建议默认关闭：避免误触导致频繁展开 / 折叠。'
  },
  contextMenu: {
    createFile: '📄 新建文件',
    createFolder: '📁 新建目录',
    createFileHere: '📄 在此新建文件',
    createFolderHere: '📁 在此新建目录',
    sendDirectoryToLibrary: '📚 发送目录到库...',
    directoryToBrain: '🧠 目录入脑',
    deleteDirectoryRecursive: '🧨 递归删除目录',
    toggleFavorite: '⭐ 设为 / 取消常用',
    copyInternalLink: '🔗 复制内部链接',
    openBinaryNewTab: '↗ 新标签页预览（PDF/图片）',
    sendFileToLibrary: '📚 发送到库...',
    txtToStructuredMd: '📝 转换为笔记（TXT→结构化MD）',
    epubReadNewTab: '📖 新标签页阅读（EPUB）',
    pdfToNote: '📝 转换为笔记（MD+images）',
    epubToNote: '📝 转换为笔记（MD+images）',
    docToNote: '📝 转换为笔记（DOC→MD+images）',
    docxToNote: '📝 转换为笔记（DOCX→MD+images）',
    pptToNote: '📝 转换为笔记（PPT→MD+images）',
    pptxToNote: '📝 转换为笔记（PPTX→MD+images）',
    noteToBrain: '🧠 进脑',
    copyImageReference: '📋 复制图片引用',
    focusThisDirectory: '◉ 聚焦到此目录',
    clearFocus: '○ 取消聚焦',
    rename: '✏️ 重命名',
    moveTo: '📦 移动到...',
    delete: '🗑️ 删除',
    unimplementedAction: '未实现的菜单动作：{action}'
  },
  convert: {
    common: {
      unknownError: '未知错误',
      unknownErrorLower: '未知错误',
      targetPathMissing: '未找到目标路径',
      alreadyExistsOpen: '✅ 已存在：{name}（已打开）',
      overwriteConfirm: '目标已存在，是否覆盖？\n\n{message}',
      overwriteCancelled: '已取消覆盖',
      convertFailed: '❌ 转换失败：{error}',
      exception: '❌ 转换异常：{error}',
      generated: '✅ 已生成：{name}',
      generatedSplit: '✅ 已生成：{name}（split）',
      generatedImages: '✅ 已生成：{name}（images: {count}）'
    },

    pdf: {
      pathMissing: '未找到 PDF 路径',
      progress: '⏳ 正在转换 PDF → Markdown（可能需要较长时间）…',
      completed: 'PDF 转换完成',
      overwriteCompleted: 'PDF 覆盖转换完成',
      resumeCompleted: 'PDF 继续转换完成',
      busy: '⏳ 正在转换其它 PDF，请等待当前任务完成后再试',
      timeoutResumeConfirm: '转换超时（{done}/{total} 页）。是否继续从第 {next} 页开始继续转换？',
      resumeCancelled: '已取消继续转换（保留已生成的部分）',
      resumeProgress: '⏳ 正在继续转换（resume）…',
      resumeFailed: '❌ 继续转换失败：{error}',
      resumeGenerated: '✅ 已生成：{name}（resume）'
    },

    office: {
      notExpectedFile: '当前文件不是 {ext}',
      progress: '⏳ 正在转换 {kind} → Markdown…',
      busy: '⏳ 正在转换其它文档，请等待当前任务完成后再试'
    },

    epub: {
      pathMissing: '未找到 EPUB 路径',
      progress: '⏳ 正在转换 EPUB → Markdown（md_part_max_lines=2000，auto/split）…'
    },

    txt: {
      pathMissing: '未找到 TXT 路径',
      notExpectedFile: '当前文件不是 .txt',
      start: '开始转换：{name}',
      failed: '转换失败：{error}',
      successNoPath: '转换成功但未返回 md_path',
      alreadyExists: '已存在：{name}',
      completed: '转换完成：{name}'
    }
  },

  open: {
    epub: {
      pathMissing: '未找到 EPUB 路径',
      notExpectedFile: '当前文件不是 .epub',
      openFailed: 'EPUB 打开失败：{error}'
    },

    binary: {
      pathMissing: '未找到文件路径',
      unsupported: '当前文件不支持二进制预览',
      previewFailed: '预览失败：{error}'
    }
  },

  binary: {
    filenameRequired: 'filename 不能为空',
    readFailed: '读取失败',
    popupBlocked: '浏览器拦截了新窗口。请允许弹窗，或改用右键菜单操作。',
    popupBlockedShort: '浏览器拦截了新窗口。请允许弹窗。',
    epub: {
      readerTitle: 'EPUB 阅读器',
      loading: '⏳ 正在加载 EPUB…',
      prevPage: '上一页',
      nextPage: '下一页',
      close: '关闭',
      readerLoading: '正在加载 EPUB 阅读器…如果加载失败，可能是网络策略拦截了 epub.js CDN。',
      cdnFailed: 'epub.js 未加载成功。\n\n建议：确认可访问 https://unpkg.com/epubjs/dist/epub.min.js',
      readFailedPrefix: '读取 EPUB 失败：'
    }
  },

  controller: {
    messages: {
      actionCompleted: '操作完成',
      libraryStatusRefreshed: '已刷新库状态',
      directoryLoaded: '目录加载完成',
      favoritesLoaded: '已加载常用',
      favoritesUpdated: '已更新常用',
      favoritesUpdateFailed: '更新常用失败',
      highlightUpdated: '高亮已更新',
      highlightCleared: '高亮已清除',
      highlightUpdateFailed: '更新高亮失败',
      actionFailed: '操作失败',
      focusBeforeBatchAction: '请先聚焦到一个目录，再使用批量功能',
      focusBeforeBatchMove: '请先聚焦到一个目录，再使用批量移动',
      focusBeforeBatchRename: '请先聚焦到一个目录，再使用批量重命名',
      noSelection: '未选择任何文件或目录',
      batchDeleteConfirmAgain: '🗑 已选择 {count} 项：再次点击删除以确认（5 秒内）',
      batchDeleteStarted: '🧨 正在批量递归删除：{count} 项…',
      movedToTrash: '✅ 已移入回收站',
      batchDeleteFailed: '❌ 批量删除失败：{error}',
      batchDeleteException: '❌ 批量删除异常：{error}',
      unknownError: '未知错误',
      selectionNotInFocusedDir: '所选项不在当前聚焦目录内，已取消',
      destinationRequired: '目标目录不能为空',
      ignoredDescendants: '已自动忽略 {count} 个子孙项（因父目录已选中）',
      batchMoveStarted: '🚚 开始移动：{count} 项 → user/{dest}/',
      moveProgress: '🚚 移动中 {index}/{total}：{name}',
      moveCompleted: '移动完成',
      defaultMoveFailed: '移动失败',
      cannotMoveIntoSelf: '{name}: 目标目录不能在自身内部',
      moveFailed: '{name}: {error}',
      batchMoveSummaryWarning: '⚠️ 移动完成：成功 {success}，失败 {failed}',
      batchMoveSummarySuccess: '✅ 移动完成：{count} 项',
      batchRenameStarted: '✎ 开始重命名：{count} 项',
      renameProgress: '✎ 重命名中 {index}/{total}：{name}',
      renameCompleted: '重命名完成',
      defaultRenameFailed: '重命名失败',
      renameFailed: '{name}: {error}',
      batchRenameSummaryWarning: '⚠️ 重命名完成：成功 {success}，失败 {failed}',
      batchRenameSummarySuccess: '✅ 重命名完成：{count} 项',
      addedToFavorites: '已加入常用：{name}',
      removedFromFavorites: '已从常用移除：{name}',
      failJoiner: '；'
    }
  },
  batch: {
    selectedTitle: '已选 {count} 项',
    selectedLabel: '已选 {count}',
    selectAllCurrentLevel: '全选当前层',
    moveSelected: '批量移动（受控并发 + 进度 toast）',
    renameSelected: '规则批量重命名（带预览 + 进度 toast）',
    deleteSelected: '批量递归删除（双击确认，仅 toast）',
    exit: '退出批量',
    enter: '批量模式（仅聚焦目录：删除 / 移动 / 重命名）'
  },
  createEntry: {
    title: '新建',
    file: '文件',
    folder: '目录',
    fileTitle: '新建文件',
    folderTitle: '新建目录',
    location: '创建位置',
    chooseChildDir: '选择子目录',
    childDirs: '子目录',
    collapse: '收起',
    childLoading: '（加载中…）',
    childEmpty: '（当前目录下没有子目录）',
    fileName: '文件名',
    folderName: '目录名',
    filePlaceholder: 'note',
    folderPlaceholder: 'notes',
    extTitle: '扩展名（可改，可清空）',
    previewPrefix: '将创建为：',
    enterFileName: '请输入文件名。',
    enterFolderName: '请输入目录名。',
    confirm: '创建'
  },
  batchMove: {
    title: '批量移动',
    currentFocus: '当前聚焦',
    selectedCount: '已选数量',
    selectedCountValue: '已选 {count} 项',
    currentDirectory: '当前目录',
    targetDirectory: '目标目录',
    chooseChildDir: '选择子目录',
    childDirs: '子目录',
    collapse: '收起',
    childLoading: '正在加载子目录...',
    childEmpty: '当前目录下没有可选子目录',
    directoryPath: '目录路径',
    inputPlaceholder: '例如：agent_files/docs',
    hint: '说明：将把所选文件/目录移动到目标目录下（保持原名称）。如选择目录则递归移动其全部内容。',
    confirm: '移动到此处'
  },
  batchRename: {
    title: '规则批量重命名',
    selectedCountValue: '已选 {count} 项',
    applyTo: '作用对象',
    applyToAll: '文件 + 目录',
    applyToFiles: '仅文件',
    applyToDirs: '仅目录',
    prefix: '前缀',
    prefixPlaceholder: '例如：2026_',
    suffix: '后缀',
    suffixPlaceholder: '例如：_done',
    find: '查找',
    findPlaceholder: '例如：draft',
    replace: '替换',
    replacePlaceholder: '例如：final',
    numbering: '序号',
    enable: '启用',
    numberingStart: '起始',
    numberingWidth: '位宽',
    numberingDelimiter: '分隔',
    numberingDelimiterPlaceholder: '_',
    previewTitle: '预览（最多 30 项）',
    conflictWarning: '存在重名冲突，无法应用',
    hint: '说明：重命名只改变名称本身（保持原父目录不变）。文件会保留扩展名并在扩展名前应用序号。',
    confirm: '应用规则'
  },
  bulk: {
    undoSuccess: '已撤销本次递归删除',
    undoFailed: '撤销失败：{error}'
  },
  treeNode: {
    batchSelect: '批量选择',
    hebbianMarked: '已进脑',
    inLibrary: '已发送到知识库',
    inLibraries: '已发送到：{names}',
    inLibrariesMore: '已发送到：{names} 等 {extraCount} 个知识库',
    libraryCoverage: '知识库覆盖：{percent}%',
    focusHere: '◉ 聚焦',
    clearFocus: '○ 取消聚焦',
    setFavorite: '设为常用',
    unsetFavorite: '取消常用',
    loadingChildren: '（加载中…）',
    contextMenuFocusHere: '◉ 聚焦到此目录',
    contextMenuClearFocus: '○ 取消聚焦',
    messages: {
      actionCompleted: '操作完成',
      directoryLoaded: '目录加载完成',
      favoritesUpdated: '已更新常用',
      favoritesUpdateFailed: '更新常用失败',
      conversionCompleted: '转换完成',
      convertingToMarkdown: '⏳ 正在转换 {kind} → Markdown…',
      busy: '系统忙，请稍后再试',
      missingMdPath: '未返回 md_path',
      alreadyExistsOpened: '✅ 已存在，已打开',
      overwriteCanceled: '已取消覆盖',
      generated: '✅ 已生成',
      conversionFailed: '转换失败'
    }
  },
  sendToLibrary: {
    title: '发送到库',
    sourceDirectory: '源目录：',
    sourceFile: '源文件：',
    targetLibrary: '目标文档库',
    loadingLibraries: '正在加载库列表...',
    noLibraries: '暂无可用库，请先在“库”页创建',
    libraryIdMissing: '（库ID缺失）',
    mode: '发送模式',
    copyDirectory: '复制（保留源目录）',
    copyFile: '复制（保留源文件）',
    moveDirectory: '移动（发送后删除源目录中已发送文件）',
    moveFile: '移动（发送后删除源文件）',
    confirm: '发送到库',
    sending: '发送中...',
    messages: {
      loadLibrariesCompleted: '加载库列表完成',
      loadLibrariesFailed: '加载库列表失败：{error}',
      loadLibrariesException: '加载库列表异常：{error}',
      sendFailed: '发送到库失败：{error}',
      sendException: '发送到库异常：{error}',
      sendFailedGeneric: '发送失败',
      unknownError: '未知错误',
      directorySentCopy: '目录已发送到库（模式：复制）',
      directorySentMove: '目录已发送到库（模式：移动）',
      fileSentCopy: '文件已发送到库（模式：复制）',
      fileSentMove: '文件已发送到库（模式：移动）'
    }
  },
  autoSave: {
    unknownError: '未知错误',
    fileSaved: '✅ 文件已保存\n\n📁 {name}',
    saveFailed: '❌ 保存失败：{error}',
    quickNoteSaved: '✅ 已保存为快速笔记'
  },
  noteOperations: {
    unknownError: '未知错误',
    fileSaved: '✅ 文件已保存\n\n📁 {name}',
    saveFailed: '❌ 保存失败：{error}',
    unsavedPrompt: '当前内容还没有对应的文件，请输入要保存的相对路径（如 notes/my_note.md）：',
    createDescription: '创建于 {time}',
    createdAndSaved: '✅ 已创建并保存文件\n\n📁 {filename}',
    noFileOpen: '未打开任何文件',
    processingNote: '🧠 正在处理：{name}',
    justNow: '刚刚',
    noteSentToBrain: '✅ 笔记已进脑\n📁 {name}\n💡 使用图谱工具查看关系网络',
    noteToBrainFailed: '❌ 进脑失败：{error}',
    noteToBrainException: '❌ 进脑异常：{error}'
  },
  revealSavedFileFailed: '定位已保存文件失败：{error}'
}

