export default {
  left: {
    title: 'RSS',
    actions: {
      openGate: '闸门',
      openGateTitle: '打开 RSS 入库闸门',
      refresh: '刷新',
      refreshTitle: '刷新订阅列表'
    },
    addPlaceholder: '添加 RSS URL',
    add: '添加',
    loading: '⏳ 加载 RSS 订阅...',
    empty: '（暂无 RSS 订阅）',
    untitledFeed: '未命名订阅',
    noTags: '（无标签）',
    messages: {
      refreshSuccess: '✅ RSS 刷新完成',
      refreshFailed: '❌ RSS 刷新失败：{error}',
      addSuccess: '✅ 已添加订阅',
      addFailed: '❌ 添加失败：{error}',
      unknownError: '未知错误'
    },
    contextMenu: {
      rename: '✏️ 重命名',
      editTags: '🏷️ 编辑标签',
      delete: '🗑️ 删除订阅'
    }
  },

  center: {
    reader: {
      topbar: {
        back: '← 返回',
        title: 'RSS',
        starTitle: '收藏',
        unstarTitle: '取消收藏',
        star: '☆ 收藏',
        starred: '★ 已收藏',
        archiveTitle: '归档',
        unarchiveTitle: '取消归档',
        archive: '🗄 归档',
        archived: '↩ 已归档',
        fetch: '抓取'
      },
      sections: {
        tags: '标签',
        feeds: '订阅',
        articles: '文章'
      },
      selects: {
        allTags: '（全部）',
        chooseFeed: '（请选择订阅）'
      },
      fallbacks: {
        untitledFeed: '未命名订阅',
        untitledArticle: '未命名文章'
      },
      badges: {
        read: '已读'
      },
      states: {
        loading: '加载中…',
        selectArticle: '请选择文章'
      },
      messages: {
        chooseFeedFirst: '请选择订阅',
        loadFeedsFailed: 'RSS 订阅加载失败：{error}',
        loadTagsFailed: 'RSS 标签加载失败：{error}',
        loadArticlesFailed: 'RSS 文章列表加载失败：{error}',
        fetchSuccess: '抓取完成：新增 {count}',
        fetchFailed: '抓取失败',
        setStateFailed: '设置失败'
      }
    },

    gate: {
      topbar: {
        back: '← 返回',
        title: 'RSS 入库闸门',
        clearCacheTitle: '清理 RSS 搜索相关的进程内缓存（不删除任何数据文件）',
        clearCache: '清理缓存',
        clearing: '清理中…',
        cleanupTitle: '删除 keep_days 以前的 RSS 本地文章数据，并可选重建 embeddings 索引（重建更慢但更干净）',
        cleanupOldData: '清理旧数据',
        cleaning: '清理中…',
        autoCleanupTitle: '设置自动清理：保存后会像自动更新 RSS 一样按计划执行',
        autoCleanup: '自动清理',
        setting: '设置中…',
        search: '搜索',
        searching: '搜索中…'
      },

      params: {
        sections: {
          keywords: '关键词',
          feedScope: '订阅范围',
          searchParams: '搜索参数',
          targetLibrary: '入库目标库',
          importActions: '入库操作',
          hardDelete: '垃圾治理（硬删除）',
          manualFetchDue: '手动更新（fetch_due）',
          rssAutoFetch: '自动更新 RSS（计划任务）',
          rssAutoCleanup: '自动清理 RSS（计划任务）',
          spamRules: '垃圾规则'
        },
        fields: {
          days: '天数',
          startDate: '开始',
          endDate: '结束',
          limit: 'limit',
          minScore: 'min_score',
          strictLexical: 'strict_lexical',
          strictLexicalLabel: '严格词面',
          onlyUnimported: '只看未入库',
          rssAutoFetchIntervalMinutes: '间隔(min)',
          rssAutoFetchLimitEntries: '每源条数',
          rssAutoCleanupKeepDays: '保留(days)',
          rssAutoCleanupIntervalHours: '间隔(h)',
          rssAutoCleanupRebuildIndex: '重建索引',
          rssAutoCleanupDeleteLogsBeforeDays: '删日志(days)',
          rebuildEmbeddings: 'rebuild embeddings'
        },
        placeholders: {
          queryExample: '例如：Venezuela Trump / AI development trends / 委内瑞拉',
          feedFilter: '过滤订阅…',
          groupName: '订阅组命名（例如：AI_zh_en / Venezuela）',
          libraryId: '例如：lib_xxx（可手填）'
        },
        actions: {
          favoriteKeyword: '收藏',
          removeKeyword: '删除该关键词',
          clearFavoriteKeywords: '清空常用关键词',
          selectAll: '全选',
          clear: '清空',
          confirmSelection: '确认选择（{count}）',
          saveGroup: '保存订阅组',
          clearGroups: '清空组',
          refreshLibraries: '刷新库列表',
          importing: '入库中…',
          importSelected: '入库选中（{count}）',
          selectAllLoaded: '全选（已加载）',
          unselectAllLoaded: '取消全选',
          deleteSelected: '删除选中（{count}）',
          deleteAllResults: '删除全部结果（{count}）',
          fetching: '更新中…',
          fetchDueNow: '更新到期RSS',
          save: '保存',
          runNow: '立即执行',
          refreshStatus: '刷新状态',
          delete: '删除',
          enableRssAutoFetch: '自动执行 fetch_due',
          enableRssAutoCleanup: '自动清除 N 天以前的 RSS 本地数据',
          loadSpamRules: '刷新规则',
          loading: '加载中…',
          expandList: '展开列表',
          collapseList: '收起列表'
        },
        options: {
          allFeeds: '全部订阅',
          selectedFeeds: '只搜选中订阅',
          selectLibraryOptional: '（从列表选择，可选）',
          chooseLibraryFromList: '从列表选择（可选）'
        },
        titles: {
          loadGroup: '加载订阅组：{name}（{count}）',
          clearAllGroups: '清空所有订阅组'
        },
        status: {
          confirmedFeedsCount: '已确认：{count} 个',
          importDone: '✅ 入库完成：导入 {imported}，跳过 {skipped}，失败 {failed}',
          firstImportError: '首个失败原因：{error}',
          deleteDone: '✅ 删除完成：deleted {deleted}，skipped {skipped}，failed {failed}',
          rssAutoFetchStatus: 'enabled {enabled}, interval {interval}min, limit {limit}',
          rssAutoCleanupStatus: 'enabled {enabled}, keep_days {keepDays}, interval_hours {intervalHours}, rebuild_index {rebuildIndex}, next_run_at {nextRunAt}',
          spamRulesCount: '共 {count} 条',
          spamRulesLoadedHint: '已加载 {count} 条规则，点击“展开列表”查看（展开后最多显示 4 条高度，可滚动）。',
          on: 'on',
          off: 'off'
        },
        messages: {
          enterGroupName: '请输入订阅组名称',
          removeKeywordFailedNoSuccess: '删除失败：后端未返回 success',
          removeKeywordSuccess: '✅ 已删除关键词：{keyword}',
          removeKeywordFailedWithError: '删除失败：{error}'
        }
      },

      search: {
        status: {
          searching: '搜索中...',
          warmingRemaining: '搜索准备中，剩余 {pending} 个源补全中',
          partialRemaining: '已先返回 {count} 条，剩余 {pending} 个源补全中',
          done: '搜索完成：{count} 条',
          doneWithFailed: '搜索完成：{count} 条，{failed} 个源失败',
          doneWithSkipped: '搜索完成：{count} 条，{skipped} 个慢源已跳过',
          failed: '搜索失败：{error}'
        },
        toast: {
          enterKeyword: '请输入关键词',
          confirmFeedScopeFirst: '请先"确认选择"要限定的订阅范围。',
          partialDeadline: '已先返回 {count} 条，剩余 {pending} 个源补全中',
          partialFast: '已先返回 {count} 条，后台继续补全中',
          failed: '搜索失败：{error}',
          done: '搜索完成：{count} 条',
          doneWithFailed: '搜索完成：{count} 条，{failed} 个源失败',
          completed: '搜索补全完成：{count} 条',
          completedWithSkipped: '搜索补全完成：{count} 条，{skipped} 个慢源已跳过'
        },
        errors: {
          unknown: '未知错误',
          sourceFailed: '来源 {source} 失败'
        }
      },

      results: {
        title: '搜索结果（{count}）',
        sort: {
          score: '相似度',
          scoreTitle: '按相似度（score）排序',
          timeDesc: '时间↓',
          timeDescTitle: '按发布时间倒序',
          timeAsc: '时间↑',
          timeAscTitle: '按发布时间正序'
        },
        status: {
          searching: '搜索中…'
        },
        empty: '还没有结果：输入关键词后搜索。',
        fallback: {
          untitled: 'untitled'
        },
        badges: {
          imported: '已入库',
          deleted: '已删除',
          blocked: '已拉黑'
        },
        meta: {
          publishedAt: '🕒 {value}',
          score: 'score {value}',
          feed: 'feed {value}',
          method: 'method {value}'
        },
        actions: {
          openLink: '打开链接',
          quickPreview: '快速预览',
          pasteFullText: '粘贴全文',
          block: '拉黑',
          unblock: '取消拉黑',
          delete: '删除',
          deleteData: '删除数据',
          markSpamDomain: '垃圾域名',
          markSpamArticle: '垃圾文章'
        },
        messages: {
          blockedSuccess: '✅ 已拉黑'
        },
        note: '说明：结果来自 gate_candidates（strict_lexical/min_score/days/start_date/end_date）。删除数据/批量硬删除会物理删除文章目录数据。'
      },

      modals: {
        fallback: {
          untitled: 'untitled'
        },
        actions: {
          close: '关闭',
          cancel: '取消'
        },
        preview: {
          title: '预览：{title}',
          loading: '加载中…',
          empty: '无内容',
          openInReader: '在 RSSReader 打开全文'
        },
        override: {
          title: '粘贴全文：{title}',
          description: '说明：把你复制的完整文章全文粘贴到下方，保存后会覆盖该 RSS 文章的标题/简介/正文。',
          placeholder: '在此粘贴完整文章内容（支持纯文本/Markdown）',
          saving: '保存中…',
          save: '保存覆盖'
        }
      },

      prompts: {
        keepDays: '保留最近 N 天的 RSS 数据（1-365）',
        enableAutoCleanup: '启用自动清理？输入 1 启用，输入 0 关闭',
        autoCleanupKeepDays: '自动清理：保留最近 N 天（1-365）',
        autoCleanupIntervalHours: '自动清理：执行间隔（小时，1-168）'
      },

      confirm: {
        clearCache: '确定清理后端 RSS 搜索缓存？\\n\\n这不会删除任何数据文件，但下一次搜索可能会重新加载索引/规则。',
        rebuildIndex: '是否重建 embeddings 索引？\\n\\n是：更慢，但更干净。\\n否：更快，仅做数据删除与 jsonl 压缩。',
        dryRunFirst: '先 dry_run 统计一遍再执行吗？\\n\\n是：先统计（不落盘），再让你确认是否真执行。',
        executeCleanup: '要开始真正执行清理吗？（这会删除旧数据文件）',
        disableAutoCleanup: '确定关闭自动清理？（会删除自动清理配置）',
        autoCleanupRebuildIndex: '自动清理时是否重建 embeddings 索引？\\n\\n是：更慢但更干净；否：更快。',
        runAutoCleanupNow: '要立刻执行一次自动清理吗？'
      },

      messages: {
        unknownError: '未知错误',
        clearCacheSuccess: '✅ 已清理后端 RSS 缓存（建议稍等 1-2 秒再搜索）',
        clearCacheFailed: '清理失败：{error}',
        clearCacheError: '清理异常：{error}',
        cleanupFailed: '清理失败：{error}',
        cleanupStatsDone: '✅ 清理统计完成：before {before}MB → after {after}MB，deleted_dirs={deleted_dirs}，rebuild={rebuild}',
        cleanupExecuteFailed: '执行失败：{error}',
        cleanupDone: '✅ 清理完成：before {before}MB → after {after}MB，deleted_dirs={deleted_dirs}',
        cleanupError: '清理异常：{error}',
        autoCleanupDisabled: '✅ 已关闭自动清理',
        disableAutoCleanupFailed: '关闭失败：{error}',
        autoCleanupSaved: '✅ 已保存自动清理：keep_days={keep_days} interval_hours={interval_hours} next_run_at={next_run_at}',
        saveAutoCleanupFailed: '保存失败：{error}',
        autoCleanupRunNowDone: '✅ 已执行：before {before}MB → after {after}MB',
        runAutoCleanupNowFailed: '执行失败：{error}',
        autoCleanupError: '设置异常：{error}'
      },

      rules: {
        sectionTitle: '自动入库规则',
        count: '共 {count} 条',
        savedRules: '已保存规则（{count}）',
        empty: '还没有自动规则：填写参数后点击“用当前条件生成规则”。',

        fields: {
          ruleName: '规则命名',
          excludeTerms: '排除词',
          timesPerDay: '每天几次',
          startTimeUtc: '开始时间(UTC)',
          timesUtc: 'times_utc',
          maxPerRun: '每次上限',
          query: '关键词',
          expandQueries: '扩展关键词',
          libraryId: '入库目标库',
          feedScope: '订阅范围',
          feedIds: '选中订阅(feed_ids)',
          days: '天数',
          startDate: '开始日期',
          endDate: '结束日期',
          limit: 'limit',
          minScore: 'min_score',
          strictLexical: 'strict_lexical',
          strictLexicalHint: '严格词面（更保守）',
          enabled: '启用',
          enabledRule: '启用该规则'
        },

        placeholders: {
          ruleName: '例如：iran_rss_ai',
          excludeTerms: '垃圾词1, 垃圾词2（逗号分隔）',
          timesUtc: '例如：06:55 或 06:55,18:05（UTC）',
          maxPerRun: '30',
          editRuleName: '例如：china_japan',
          query: '例如：China Japan',
          expandQueries: '一行一个，例如：Chinese GDP\\nChina inflation',
          libraryId: '例如：china_japan',
          feedIds: '一行一个或逗号分隔，例如：25c310...,72b628...'
        },

        tips: {
          autoTimes: '推荐：先选“每天几次 + 开始时间”，系统会自动生成 times_utc；也可以手填 times_utc 精确控制（逗号分隔 HH:MM，UTC）。',
          collapsedList: '已折叠。展开后最多显示约 5 条高度，可滚动查看全部规则（不会隐藏规则）。',
          matchMode: '建议：多关键词（如 “China Japan”）默认按交集过滤（AND）。'
        },

        actions: {
          generateFromCurrent: '用当前条件生成规则',
          runDueNow: '手动运行到期规则',
          refreshRules: '刷新规则',
          collapseList: '收起列表',
          expandList: '展开列表',
          edit: '编辑',
          runNow: '立即运行',
          disable: '停用',
          enable: '启用',
          delete: '删除',
          close: '关闭',
          useCurrentSearch: '用当前搜索条件覆盖',
          saveChanges: '保存修改'
        },

        meta: {
          query: '关键词：{value}',
          library: '库：{value}',
          timesUtc: 'times_utc：{value}',
          legacyInterval: 'legacy_interval：{minutes}min',
          lastRun: '上次：{value}',
          nextRun: '下次：{value}'
        },

        scope: {
          allFeeds: '全部订阅',
          selectedFeeds: '仅选中订阅',
          hint: '（选中订阅用 feed_id 列表保存）'
        },

        report: {
          title: '最近运行报告',
          searched: '搜索 {count}',
          picked: '筛选 {count}',
          imported: '入库 {count}',
          skipped: '跳过 {count}',
          failed: '失败 {count}'
        },

        modal: {
          title: '编辑规则'
        },

        confirm: {
          deleteRule: '确定删除该规则？'
        },

        messages: {
          unknownError: '未知错误',
          loadRulesFailed: '加载规则失败',
          loadRulesFailedWithError: '加载规则失败：{error}',
          fillQueryAndLibraryFirst: '请先填写关键词和目标库',
          fillTimesUtc: '请填写 times_utc，例如：06:55 或 06:55,18:05（UTC）',
          saveRuleFailed: '保存规则失败',
          saveRuleFailedWithError: '保存规则失败：{error}',
          ruleSaved: '规则已保存',
          runFailed: '运行失败：{error}',
          runFailedWithError: '运行失败：{error}',
          runFinishedImported: '运行完成：入库 {count} 条',
          runFinishedNoNew: '运行完成：无新内容',
          runDueFailed: '运行到期规则失败',
          runDueFailedWithError: '运行到期规则失败：{error}',
          noDueRules: '没有到期的规则',
          ranDueRulesImported: '运行了 {ran} 个规则，入库 {imported} 条',
          updateRuleFailed: '更新规则失败',
          updateRuleFailedWithError: '更新规则失败：{error}',
          ruleEnabled: '规则已启用',
          ruleDisabled: '规则已停用',
          deleteRuleFailed: '删除规则失败',
          deleteRuleFailedWithError: '删除规则失败：{error}',
          ruleDeleted: '规则已删除',
          ruleMissing: '规则不存在，可能已被删除',
          fillRuleName: '请填写规则命名',
          fillQuery: '请填写关键词',
          fillLibrary: '请选择/填写目标库',
          feedIdsRequired: '订阅范围选“仅选中订阅”时，feed_ids 不能为空',
          saveEditFailed: '保存修改失败',
          saveEditFailedWithError: '保存修改失败：{error}',
          ruleUpdated: '规则已更新'
        }
      }
    }
  }
}
