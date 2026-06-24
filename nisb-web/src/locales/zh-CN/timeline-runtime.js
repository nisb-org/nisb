export default {
  timeline: {
    toolbar: {
      daysTitle: '切换加载的日期范围（最多 30 天）',
      daysOption: '{count} 天',
      refresh: '刷新',
      loading: '加载中…',
      refreshTitle: '刷新时间线',
      select: '选择',
      selectTitle: '进入批量选择模式（任何条目都可以移除；显式活动记录会被删除，其它仅会被隐藏）',
      removeSelected: '移除 ({count})',
      removeSelectedTitle: '移除已选 ({count})',
      removeSelectedEmptyTitle: '没有选中可移除项',
      cancel: '取消',
      cancelTitle: '退出选择模式',
      pruneMissing: '清理无效项',
      pruneMissingTitle: '清理指向缺失文件的显式活动记录',
      compact: '压缩时间线',
      compactTitle: '压缩 activities.jsonl（去重 / 过滤 / 原子重写）。注意：这会物理重写日志文件。',
      patternPlaceholder: '模式删除：例如 doc_20260129*',
      patternTitle: '按模式批量从 activities.jsonl 硬删除（支持 glob：* ?）。如可行请先压缩时间线。',
      hardDelete: '按模式硬删除',
      hardDeleteTitle: '按模式批量硬删除（先预览匹配，再确认）'
    },
    empty: {
      loadingActivities: '⏳ 加载活动中...',
      noActivities: '（暂无活动）'
    },
    sections: {
      today: '今天',
      yesterday: '昨天',
      thisWeek: '本周',
      older: '更早',
      collapse: '收起 ({count})',
      expandMore: '显示更多 ({count})'
    },
    activity: {
      unnamed: '(未命名)',
      document: '(文档)',
      file: '(文件)',
      conversation: '(对话)',
      activity: '(活动)',
      filteredInternalRecord: '(已过滤内部记录)',
      hebbianTitle: 'Hebbian：{concepts} 个概念 · {synapses} 条突触',
      selectToggle: '选择 / 取消选择',
      notRemovable: '该项不可移除',
      removeOneTitle: '从时间线移除此记录'
    },
    tooltip: {
      libraryDoc: '库: {lib} · 文档: {doc}',
      conversationWithTitle: 'conv_id: {id} · {title}',
      conversationId: 'conv_id: {id}'
    },
    messages: {
      activitiesLoaded: '活动已加载',
      heatmapLoaded: '热力图已加载',
      compactConfirm:
        '压缩时间线活动日志（activities.jsonl）？\n\n此操作将：\n- dedupe：同一资源仅保留最新一条记录\n- filter：移除 tombstone / missing-file / rss_import 噪声\n- 原子重写 activities.jsonl\n\n是否继续？',
      compactDone: '时间线已压缩',
      compactSuccess: '✅ 时间线已压缩\n保留：{kept}\n移除：{removed}\n过滤 rss_import：{rss}',
      compactFailed: '压缩失败：{text}',
      previewDone: '预览完成',
      previewFailed: '预览失败：{text}',
      patternInputRequired: '请输入模式，例如 doc_20260129*',
      noMatchedRecords: '没有匹配到记录',
      untitledSample: '(未命名)',
      noSamples: '(无示例)',
      patternDeleteConfirm:
        '这将从 activities.jsonl 中永久删除 {matched} 条记录。\n\n模式：{pattern}\n\n示例：\n{samples}\n\n是否继续？',
      patternDeleteDone: '模式删除完成',
      patternDeleteSuccess: '✅ 已删除 {removed} 条记录，剩余 {remaining} 条',
      patternDeleteFailed: '删除失败：{text}',
      deleteOneHardTip: '这将从时间线活动日志中删除该记录。',
      deleteOneSoftTip: '这只会把该项从时间线隐藏，不会删除源数据。',
      deleteOneConfirm: '移除此时间线记录？\n\n{title}\n\n{tip}',
      deleteOneDone: '时间线记录已移除',
      deleteOneFailed: '移除失败：{text}',
      deleteSelectedConfirm:
        '移除所选的 {count} 条时间线记录？\n\n显式活动记录会从日志中删除，其它项目只会从时间线中隐藏。',
      deleteSelectedDone: '已移除所选时间线记录',
      deleteSelectedFailed: '批量移除失败：{text}',
      pruneConfirm:
        '清理已删除文件留下的残余记录？\n\n这将重写 activities.jsonl（仅显式活动日志记录）。',
      pruneDone: '无效记录已清理',
      pruneSuccess: '✅ 已清理 {removed} 条无效记录',
      pruneFailed: '清理失败：{text}',
      unknownError: '未知错误',
      unknown: '未知'
    }
  },

  runtime: {
    card: {
      title: 'Room Runtime',
      mode: {
        current: '当前',
        replay: '回放'
      },
      actions: {
        refresh: '刷新',
        refreshing: '刷新中…',
        pauseCurrent: '暂停当前运行',
        resumeFromCheckpoint: '从检查点恢复'
      },
      replay: {
        label: '回放运行',
        selectRun: '选择一个回放运行',
        noRun: '暂无回放运行'
      },
      badges: {
        current: '当前',
        replay: '回放',
        resumed: '已恢复',
        restartFresh: '全新重启',
        fresh: '全新',
        pausedAtCheckpoint: '在检查点暂停',
        resumable: '可从检查点恢复',
        canSendNewPrompt: '可发送新提示词',
        resumeBlocked: '恢复受阻',
        budgetExhausted: '预算耗尽'
      },
      skillStrategy: {
        builtinPlusCustom: '内置 + 自定义',
        customOnly: '仅自定义',
        builtinOnly: '仅内置'
      },
      skillSummary: {
        skills: '技能',
        enabled: '已启用 {count}',
        applied: '已应用 {count}',
        resolved: '已解析 {count}',
        steps: '步骤 {count}',
        appliedPrompt: '已应用提示词',
        availableNotEnabled: '可用但未启用',
        missing: '缺失',
        skipped: '跳过',
        source: '来源 {value}',
        event: '事件 {value}'
      },
      reason: {
        pauseRequested: '已请求暂停',
        stepBudgetExhausted: '达到步骤预算上限',
        newTopicDetected: '检测到新话题',
        checkpointMissing: '缺少可恢复检查点'
      },
      controlBlock: {
        runRunning: '当前有运行正在进行',
        pauseRequestedPendingCheckpoint: '已请求暂停，正在等待安全检查点',
        resumeReady: '该运行可从检查点恢复',
        budgetExhausted: '步骤预算已耗尽',
        resumeBlockedError: '恢复被错误阻止'
      },
      status: {
        pauseRequested: '已请求暂停',
        interrupted: '已中断',
        resumed: '已恢复',
        completedAfterResume: '恢复后已完成',
        completed: '已完成',
        running: '运行中',
        budgetExhausted: '预算耗尽',
        failed: '失败',
        noRun: '无活动运行'
      },
      headline: {
        budgetExhausted: '该运行已达到步骤预算上限',
        pauseRequested: '当前运行已收到暂停请求',
        interrupted: '运行在检查点处被中断',
        completedAfterResume: '恢复后的运行已完成',
        resumed: '运行已从检查点恢复',
        completed: '运行已完成',
        runningResumed: '继续执行已恢复的运行',
        running: '运行进行中',
        lineageResumed: '该运行从上一个检查点恢复',
        restartFresh: '该运行以全新模式重新开始',
        fresh: '这是一次全新运行'
      },
      defaultHeadline: {
        replay: '运行回放',
        replayWithId: '回放 {id}',
        current: '运行过程'
      },
      meta: {
        viewingRun: '查看 {id}',
        phase: '阶段 {phase}',
        resumedFromRun: '从 {runId} 恢复'
      },
      summary: {
        budgetExhaustedAtStage: '当前运行在 {stage} 阶段因步骤预算耗尽而停止。',
        budgetExhausted: '当前运行已达到步骤预算上限。',
        pauseRequestedAtStage: '已请求暂停，运行将在 {stage} 阶段的安全检查点处停止。',
        pauseRequested: '已请求暂停。运行到达安全检查点边界后将变为可中断。',
        interruptedAtStage: '运行在与 {stage} 对应的检查点处被中断。',
        interrupted: '运行在最新的有效检查点处被中断。',
        resumedAtStage: '当前运行已从与 {stage} 对应的检查点恢复，并沿现有 lineage 继续。',
        resumed: '当前运行已从最新的有效检查点恢复，并沿现有 lineage 继续。',
        completedAfterResume: '该运行在恢复后完成，并尽可能避免重复执行已完成的副作用。',
        completedResumed: '该运行在恢复后完成，并保留了上一次运行的恢复语义。',
        waitingCheckpointAtStage: '已请求暂停。正在等待 {stage} 阶段的安全检查点。',
        waitingCheckpoint: '已请求暂停。正在等待安全检查点。',
        resumeReadyAtStage: '运行已中断，可从 {stage} 恢复。',
        resumeReady: '运行已中断，可从检查点恢复。',
        runRunning: '当前有运行正在进行，因此暂不接受新提示词。'
      },
      detail: {
        runtime: '运行时',
        resumePoint: '恢复点',
        checkpoint: '检查点',
        checkpointRef: '检查点引用',
        stopReason: '停止原因',
        pauseReason: '暂停原因',
        controlBlock: '控制阻塞',
        pausedAt: '暂停于',
        pauseRequestedAt: '请求暂停于',
        resumedFrom: '恢复自',
        resumeReason: '恢复原因',
        lastCompleted: '最后完成',
        stepBudget: '步骤预算',
        resumeCapability: '恢复能力',
        newPrompt: '新提示词'
      },
      detailValue: {
        canResumeFromCheckpoint: '可从最新有效检查点恢复',
        canStartFreshSend: '当前允许发起一次全新发送'
      },
      budget: {
        usedOfTotal: '{used}/{total}',
        used: '已用 {count}',
        total: '总计 {count}',
        remaining: '剩余 {count}',
        exhausted: '已耗尽',
        unlimited: '无限制'
      },
      effects: {
        skipped: '跳过 {count}',
        reused: '复用 {count}',
        execute: '执行 {count}',
        repair: '修复 {count}',
        summaryReuse: '恢复过程中，已经完成或可复用的副作用会被跳过或复用，以避免重复执行。',
        summaryRepair: '有些副作用被标记为 repair，这意味着它们不属于已完成且可复用的集合。'
      },
      history: {
        supervisor: 'Supervisor',
        memory: 'Memory',
        memoryRead: '记忆读取',
        memoryWrite: '记忆写入',
        memoryResume: '记忆恢复',
        read: '读取',
        write: '写入',
        resume: '恢复',
        success: '成功',
        checkpointDone: '检查点完成',
        continueFromCheckpoint: '从检查点继续'
      },
      empty: {
        loadingReplay: '加载回放中…',
        loadingCurrent: '加载运行结果中…',
        noReplayResult: '暂无回放结果',
        chooseReplay: '请选择一个回放运行',
        noResult: '暂无运行结果'
      }
    },

    timeline: {
      mode: {
        resumed: '已恢复',
        restartFresh: '全新重启',
        fresh: '全新'
      },
      badges: {
        waitingCheckpoint: '等待检查点',
        resumable: '可恢复',
        fromStage: '从 {stage}',
        checkpointStage: '检查点 {stage}',
        skippedEffects: '跳过 {count} 个副作用',
        budgetExhausted: '预算耗尽',
        runtime: '运行时',
        checkpoint: '检查点',
        effects: '副作用',
        final: '最终',
        error: '错误',
        aborted: '已中止'
      },
      status: {
        waitingCheckpoint: '等待安全检查点',
        replayLoading: '加载回放中…',
        replayReady: '回放已就绪',
        noReplayResult: '无回放结果',
        selectReplay: '选择一个回放运行',
        noReplay: '无可用回放',
        viewable: '可查看',
        noRuntime: '无运行时'
      },
      headline: {
        waitingCheckpoint: '已请求暂停，正在等待安全检查点'
      },
      summary: {
        interruptedAtStageWithReason: '该运行在 {stage} 阶段被中断。原因：{reason}。',
        interruptedAtStage: '该运行在 {stage} 阶段被中断。',
        interruptedWithReason: '该运行已中断。原因：{reason}。',
        interrupted: '该运行已中断。',
        canResume: '当前可以从检查点恢复。',
        budgetStoppedAtStage: '该运行在 {stage} 阶段因步骤预算耗尽而停止。',
        budgetStopped: '该运行因步骤预算耗尽而停止。',
        pauseWaitingStage: '已请求暂停。正在等待 {stage} 阶段的安全检查点。',
        pauseWaiting: '已请求暂停。正在等待安全检查点。',
        pauseWillStopAtStage: '已请求暂停。该运行将在 {stage} 阶段的安全点停止。',
        pauseWillStop: '已请求暂停。该运行将在安全点停止。',
        pauseReason: '暂停原因：{reason}。',
        completedAfterResumeFromStage: '该运行在从 {stage} 恢复后已完成。',
        completedAfterResume: '该运行在从检查点恢复后已完成。',
        completedFresh: '这次全新运行已完成。',
        completed: '该运行已完成。',
        resumedFromStage: '运行正在从 {stage} 继续。',
        resumed: '运行正在从检查点继续。',
        runningAtStage: '该运行当前位于 {stage}。',
        running: '该运行正在进行中。',
        lineageResumed: '该运行来自前一个检查点 lineage。',
        restartFresh: '该运行以全新模式重新开始，不复用先前的检查点。'
      },
      entry: {
        waitingCheckpoint: '等待安全检查点',
        status: '状态 {value}',
        mode: '模式 {value}',
        fromStage: '从 {stage}',
        checkpoint: '检查点'
      },
      hint: {
        pauseWaitingStage: '已请求暂停。正在等待 {stage} 阶段的安全检查点。',
        pauseWaiting: '已请求暂停。正在等待安全检查点。',
        resumeFromStage: '可从 {stage} 恢复。',
        resumeFromRecent: '可从最近的检查点恢复。',
        runRunning: '当前有运行正在进行，暂时无法接受新的提示词。',
        budgetExhausted: '步骤预算已耗尽；该运行无法恢复。',
        resumeBlockedError: '恢复当前被错误阻止。',
        errorBlockingResume: '当前存在阻止恢复的错误。',
        resumedFromStage: '运行正在从 {stage} 继续。',
        resumed: '运行正在从检查点继续。'
      },
      actions: {
        requesting: '请求中…',
        pauseRequested: '已请求暂停',
        resuming: '恢复中…'
      },
      effects: {
        allSkipped: '恢复过程中跳过了 {count} 个已完成的副作用',
        skipCount: '跳过 {count}',
        reuseCount: '复用 {count}',
        executeCount: '执行 {count}',
        repairCount: '修复 {count}',
        summaryDisposition: '副作用处理：{items}',
        recorded: '已记录 {count} 条副作用处理结果'
      },
      errors: {
        pauseNotAccepted: '暂停操作未被接受',
        pauseFailed: '暂停操作失败',
        resumeNotAccepted: '恢复操作未被接受',
        resumeFailed: '恢复操作失败'
      }
    }
  }
}
