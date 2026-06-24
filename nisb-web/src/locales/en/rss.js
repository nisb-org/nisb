export default {
  left: {
    title: 'RSS',
    actions: {
      openGate: 'Gate',
      openGateTitle: 'Open the RSS ingestion gate',
      refresh: 'Refresh',
      refreshTitle: 'Refresh feed list'
    },
    addPlaceholder: 'Add RSS URL',
    add: 'Add',
    loading: '⏳ Loading RSS feeds...',
    empty: '(No RSS feeds yet)',
    untitledFeed: 'untitled feed',
    noTags: '(No tags)',
    messages: {
      refreshSuccess: '✅ RSS refresh completed',
      refreshFailed: '❌ RSS refresh failed: {error}',
      addSuccess: '✅ Feed added',
      addFailed: '❌ Add failed: {error}',
      unknownError: 'Unknown error'
    },
    contextMenu: {
      rename: '✏️ Rename',
      editTags: '🏷️ Edit tags',
      delete: '🗑️ Delete subscription'
    }
  },

  center: {
    reader: {
      topbar: {
        back: '← Back',
        title: 'RSS',
        starTitle: 'Star',
        unstarTitle: 'Unstar',
        star: '☆ Star',
        starred: '★ Starred',
        archiveTitle: 'Archive',
        unarchiveTitle: 'Unarchive',
        archive: '🗄 Archive',
        archived: '↩ Archived',
        fetch: 'Fetch'
      },
      sections: {
        tags: 'Tags',
        feeds: 'Feeds',
        articles: 'Articles'
      },
      selects: {
        allTags: '(All)',
        chooseFeed: '(Select a feed)'
      },
      fallbacks: {
        untitledFeed: 'untitled feed',
        untitledArticle: 'untitled'
      },
      badges: {
        read: 'Read'
      },
      states: {
        loading: 'Loading…',
        selectArticle: 'Select an article'
      },
      messages: {
        chooseFeedFirst: 'Please select a feed',
        loadFeedsFailed: 'Failed to load RSS feeds: {error}',
        loadTagsFailed: 'Failed to load RSS tags: {error}',
        loadArticlesFailed: 'Failed to load RSS article list: {error}',
        fetchSuccess: 'Fetch completed: {count} new',
        fetchFailed: 'Fetch failed',
        setStateFailed: 'Failed to update state'
      }
    },

    gate: {
      topbar: {
        back: '← Back',
        title: 'RSS Ingestion Gate',
        clearCacheTitle: 'Clear in-memory RSS search caches without deleting any data files',
        clearCache: 'Clear Cache',
        clearing: 'Clearing…',
        cleanupTitle: 'Delete local RSS article data older than keep_days, with optional embeddings index rebuild (slower but cleaner)',
        cleanupOldData: 'Clean Old Data',
        cleaning: 'Cleaning…',
        autoCleanupTitle: 'Configure automatic cleanup; after saving it runs on schedule like RSS auto updates',
        autoCleanup: 'Auto Cleanup',
        setting: 'Setting…',
        search: 'Search',
        searching: 'Searching…'
      },

      params: {
        sections: {
          keywords: 'Keywords',
          feedScope: 'Feed Scope',
          searchParams: 'Search Parameters',
          targetLibrary: 'Target Library',
          importActions: 'Import Actions',
          hardDelete: 'Trash Cleanup (Hard Delete)',
          manualFetchDue: 'Manual Refresh (fetch_due)',
          rssAutoFetch: 'Auto Refresh RSS (Scheduled Task)',
          rssAutoCleanup: 'Auto Cleanup RSS (Scheduled Task)',
          spamRules: 'Spam Rules'
        },
        fields: {
          days: 'Days',
          startDate: 'Start',
          endDate: 'End',
          limit: 'limit',
          minScore: 'min_score',
          strictLexical: 'strict_lexical',
          strictLexicalLabel: 'Strict lexical match',
          onlyUnimported: 'Only show not-yet-imported',
          rssAutoFetchIntervalMinutes: 'Interval (min)',
          rssAutoFetchLimitEntries: 'Entries per feed',
          rssAutoCleanupKeepDays: 'Keep (days)',
          rssAutoCleanupIntervalHours: 'Interval (h)',
          rssAutoCleanupRebuildIndex: 'Rebuild index',
          rssAutoCleanupDeleteLogsBeforeDays: 'Delete logs before (days)',
          rebuildEmbeddings: 'rebuild embeddings'
        },
        placeholders: {
          queryExample: 'For example: Venezuela Trump / AI development trends / Venezuela',
          feedFilter: 'Filter feeds…',
          groupName: 'Name this feed group (e.g. AI_zh_en / Venezuela)',
          libraryId: 'For example: lib_xxx (manual input allowed)'
        },
        actions: {
          favoriteKeyword: 'Favorite',
          removeKeyword: 'Remove this keyword',
          clearFavoriteKeywords: 'Clear favorite keywords',
          selectAll: 'Select all',
          clear: 'Clear',
          confirmSelection: 'Confirm Selection ({count})',
          saveGroup: 'Save Feed Group',
          clearGroups: 'Clear Groups',
          refreshLibraries: 'Refresh Library List',
          importing: 'Importing…',
          importSelected: 'Import Selected ({count})',
          selectAllLoaded: 'Select All (Loaded)',
          unselectAllLoaded: 'Unselect All',
          deleteSelected: 'Delete Selected ({count})',
          deleteAllResults: 'Delete All Results ({count})',
          fetching: 'Refreshing…',
          fetchDueNow: 'Refresh Due RSS',
          save: 'Save',
          runNow: 'Run Now',
          refreshStatus: 'Refresh Status',
          delete: 'Delete',
          enableRssAutoFetch: 'Automatically run fetch_due',
          enableRssAutoCleanup: 'Automatically clean local RSS data older than N days',
          loadSpamRules: 'Refresh Rules',
          loading: 'Loading…',
          expandList: 'Expand List',
          collapseList: 'Collapse List'
        },
        options: {
          allFeeds: 'All feeds',
          selectedFeeds: 'Search selected feeds only',
          selectLibraryOptional: '(Choose from list, optional)',
          chooseLibraryFromList: 'Choose from list (optional)'
        },
        titles: {
          loadGroup: 'Load feed group: {name} ({count})',
          clearAllGroups: 'Clear all feed groups'
        },
        status: {
          confirmedFeedsCount: 'Confirmed: {count}',
          importDone: '✅ Import finished: imported {imported}, skipped {skipped}, failed {failed}',
          firstImportError: 'First failure reason: {error}',
          deleteDone: '✅ Delete finished: deleted {deleted}, skipped {skipped}, failed {failed}',
          rssAutoFetchStatus: 'enabled {enabled}, interval {interval}min, limit {limit}',
          rssAutoCleanupStatus: 'enabled {enabled}, keep_days {keepDays}, interval_hours {intervalHours}, rebuild_index {rebuildIndex}, next_run_at {nextRunAt}',
          spamRulesCount: '{count} rules total',
          spamRulesLoadedHint: '{count} rules loaded. Click "Expand List" to view them (the expanded list shows up to about 4 rows in height and can scroll).',
          on: 'on',
          off: 'off'
        },
        messages: {
          enterGroupName: 'Please enter a feed group name',
          removeKeywordFailedNoSuccess: 'Delete failed: backend did not return success',
          removeKeywordSuccess: '✅ Keyword removed: {keyword}',
          removeKeywordFailedWithError: 'Delete failed: {error}'
        }
      },

      search: {
        status: {
          searching: 'Searching...',
          warmingRemaining: 'Search is warming up, {pending} source(s) still completing',
          partialRemaining: '{count} result(s) returned first, {pending} source(s) still completing',
          done: 'Search complete: {count} result(s)',
          doneWithFailed: 'Search complete: {count} result(s), {failed} source(s) failed',
          doneWithSkipped: 'Search complete: {count} result(s), {skipped} slow source(s) skipped',
          failed: 'Search failed: {error}'
        },
        toast: {
          enterKeyword: 'Please enter keywords',
          confirmFeedScopeFirst: 'Please confirm the selected subscriptions first.',
          partialDeadline: '{count} result(s) returned first, {pending} source(s) still completing',
          partialFast: '{count} result(s) returned first, background completion is still running',
          failed: 'Search failed: {error}',
          done: 'Search complete: {count} result(s)',
          doneWithFailed: 'Search complete: {count} result(s), {failed} source(s) failed',
          completed: 'Search completion finished: {count} result(s)',
          completedWithSkipped: 'Search completion finished: {count} result(s), {skipped} slow source(s) skipped'
        },
        errors: {
          unknown: 'Unknown error',
          sourceFailed: 'Source {source} failed'
        }
      },

      results: {
        title: 'Search Results ({count})',
        sort: {
          score: 'Score',
          scoreTitle: 'Sort by similarity score',
          timeDesc: 'Time↓',
          timeDescTitle: 'Sort by published time descending',
          timeAsc: 'Time↑',
          timeAscTitle: 'Sort by published time ascending'
        },
        status: {
          searching: 'Searching…'
        },
        empty: 'No results yet: enter keywords and run a search.',
        fallback: {
          untitled: 'untitled'
        },
        badges: {
          imported: 'Imported',
          deleted: 'Deleted',
          blocked: 'Blocked'
        },
        meta: {
          publishedAt: '🕒 {value}',
          score: 'score {value}',
          feed: 'feed {value}',
          method: 'method {value}'
        },
        actions: {
          openLink: 'Open Link',
          quickPreview: 'Quick Preview',
          pasteFullText: 'Paste Full Text',
          block: 'Block',
          unblock: 'Unblock',
          delete: 'Delete',
          deleteData: 'Delete Data',
          markSpamDomain: 'Spam Domain',
          markSpamArticle: 'Spam Article'
        },
        messages: {
          blockedSuccess: '✅ Blocked'
        },
        note: 'Note: results come from gate_candidates (strict_lexical/min_score/days/start_date/end_date). Delete Data and batch hard delete will physically remove article directory data.'
      },

      modals: {
        fallback: {
          untitled: 'untitled'
        },
        actions: {
          close: 'Close',
          cancel: 'Cancel'
        },
        preview: {
          title: 'Preview: {title}',
          loading: 'Loading…',
          empty: 'No content',
          openInReader: 'Open full article in RSSReader'
        },
        override: {
          title: 'Paste Full Text: {title}',
          description: 'Paste the full article text below. After saving, it will overwrite this RSS article’s title, summary, and body.',
          placeholder: 'Paste the full article content here (plain text / Markdown supported)',
          saving: 'Saving…',
          save: 'Save Override'
        }
      },

      prompts: {
        keepDays: 'Keep RSS data from the most recent N days (1-365)',
        enableAutoCleanup: 'Enable automatic cleanup? Enter 1 to enable, 0 to disable',
        autoCleanupKeepDays: 'Auto cleanup: keep the most recent N days (1-365)',
        autoCleanupIntervalHours: 'Auto cleanup: run interval in hours (1-168)'
      },

      confirm: {
        clearCache: 'Clear backend RSS search caches?\\n\\nThis will not delete any data files, but the next search may need to reload indexes/rules.',
        rebuildIndex: 'Rebuild the embeddings index?\\n\\nYes: slower but cleaner.\\nNo: faster, only data deletion and jsonl compaction.',
        dryRunFirst: 'Run a dry run first before execution?\\n\\nYes: collect stats first without writing, then confirm the real execution.',
        executeCleanup: 'Start the real cleanup now? (This will delete old data files)',
        disableAutoCleanup: 'Disable automatic cleanup? (This will remove the auto cleanup config)',
        autoCleanupRebuildIndex: 'Rebuild the embeddings index during automatic cleanup?\\n\\nYes: slower but cleaner; No: faster.',
        runAutoCleanupNow: 'Run automatic cleanup once right now?'
      },

      messages: {
        unknownError: 'Unknown error',
        clearCacheSuccess: '✅ Backend RSS cache cleared (recommended: wait 1-2 seconds before searching again)',
        clearCacheFailed: 'Clear failed: {error}',
        clearCacheError: 'Clear error: {error}',
        cleanupFailed: 'Cleanup failed: {error}',
        cleanupStatsDone: '✅ Cleanup stats done: before {before}MB → after {after}MB, deleted_dirs={deleted_dirs}, rebuild={rebuild}',
        cleanupExecuteFailed: 'Execution failed: {error}',
        cleanupDone: '✅ Cleanup done: before {before}MB → after {after}MB, deleted_dirs={deleted_dirs}',
        cleanupError: 'Cleanup error: {error}',
        autoCleanupDisabled: '✅ Automatic cleanup disabled',
        disableAutoCleanupFailed: 'Disable failed: {error}',
        autoCleanupSaved: '✅ Automatic cleanup saved: keep_days={keep_days} interval_hours={interval_hours} next_run_at={next_run_at}',
        saveAutoCleanupFailed: 'Save failed: {error}',
        autoCleanupRunNowDone: '✅ Executed: before {before}MB → after {after}MB',
        runAutoCleanupNowFailed: 'Execution failed: {error}',
        autoCleanupError: 'Settings error: {error}'
      },

      rules: {
        sectionTitle: 'Auto Import Rules',
        count: '{count} total',
        savedRules: 'Saved Rules ({count})',
        empty: 'No automatic rules yet: fill in the fields and click "Generate Rule from Current Conditions".',

        fields: {
          ruleName: 'Rule Name',
          excludeTerms: 'Exclude Terms',
          timesPerDay: 'Times per Day',
          startTimeUtc: 'Start Time (UTC)',
          timesUtc: 'times_utc',
          maxPerRun: 'Max per Run',
          query: 'Query',
          expandQueries: 'Expanded Queries',
          libraryId: 'Target Library',
          feedScope: 'Feed Scope',
          feedIds: 'Selected Feeds (feed_ids)',
          days: 'Days',
          startDate: 'Start Date',
          endDate: 'End Date',
          limit: 'limit',
          minScore: 'min_score',
          strictLexical: 'strict_lexical',
          strictLexicalHint: 'Strict lexical match (more conservative)',
          enabled: 'Enabled',
          enabledRule: 'Enable this rule'
        },

        placeholders: {
          ruleName: 'e.g. iran_rss_ai',
          excludeTerms: 'noise1, noise2 (comma separated)',
          timesUtc: 'e.g. 06:55 or 06:55,18:05 (UTC)',
          maxPerRun: '30',
          editRuleName: 'e.g. china_japan',
          query: 'e.g. China Japan',
          expandQueries: 'One per line, e.g.\\nChinese GDP\\nChina inflation',
          libraryId: 'e.g. china_japan',
          feedIds: 'One per line or comma separated, e.g. 25c310...,72b628...'
        },

        tips: {
          autoTimes: 'Recommended: first choose "Times per Day + Start Time", and the system will auto-generate times_utc; you can also enter times_utc manually for exact control (comma-separated HH:MM, UTC).',
          collapsedList: 'Collapsed. After expanding, about five rows of height are shown at once, and you can scroll to view all rules (no rules are hidden).',
          matchMode: 'Tip: multi-keyword queries (such as "China Japan") use intersection filtering (AND) by default.'
        },

        actions: {
          generateFromCurrent: 'Generate Rule from Current Conditions',
          runDueNow: 'Run Due Rules Now',
          refreshRules: 'Refresh Rules',
          collapseList: 'Collapse List',
          expandList: 'Expand List',
          edit: 'Edit',
          runNow: 'Run Now',
          disable: 'Disable',
          enable: 'Enable',
          delete: 'Delete',
          close: 'Close',
          useCurrentSearch: 'Overwrite with Current Search',
          saveChanges: 'Save Changes'
        },

        meta: {
          query: 'Query: {value}',
          library: 'Library: {value}',
          timesUtc: 'times_utc: {value}',
          legacyInterval: 'legacy_interval: {minutes}min',
          lastRun: 'Last: {value}',
          nextRun: 'Next: {value}'
        },

        scope: {
          allFeeds: 'All Feeds',
          selectedFeeds: 'Selected Feeds Only',
          hint: '(selected feeds are stored as a feed_id list)'
        },

        report: {
          title: 'Latest Run Report',
          searched: 'Searched {count}',
          picked: 'Picked {count}',
          imported: 'Imported {count}',
          skipped: 'Skipped {count}',
          failed: 'Failed {count}'
        },

        modal: {
          title: 'Edit Rule'
        },

        confirm: {
          deleteRule: 'Delete this rule?'
        },

        messages: {
          unknownError: 'Unknown error',
          loadRulesFailed: 'Failed to load rules',
          loadRulesFailedWithError: 'Failed to load rules: {error}',
          fillQueryAndLibraryFirst: 'Please fill in both the query and target library first',
          fillTimesUtc: 'Please enter times_utc, for example: 06:55 or 06:55,18:05 (UTC)',
          saveRuleFailed: 'Failed to save rule',
          saveRuleFailedWithError: 'Failed to save rule: {error}',
          ruleSaved: 'Rule saved',
          runFailed: 'Run failed: {error}',
          runFailedWithError: 'Run failed: {error}',
          runFinishedImported: 'Run finished: imported {count} items',
          runFinishedNoNew: 'Run finished: no new content',
          runDueFailed: 'Failed to run due rules',
          runDueFailedWithError: 'Failed to run due rules: {error}',
          noDueRules: 'No rules are due',
          ranDueRulesImported: 'Ran {ran} rules and imported {imported} items',
          updateRuleFailed: 'Failed to update rule',
          updateRuleFailedWithError: 'Failed to update rule: {error}',
          ruleEnabled: 'Rule enabled',
          ruleDisabled: 'Rule disabled',
          deleteRuleFailed: 'Failed to delete rule',
          deleteRuleFailedWithError: 'Failed to delete rule: {error}',
          ruleDeleted: 'Rule deleted',
          ruleMissing: 'The rule does not exist and may have been deleted',
          fillRuleName: 'Please enter a rule name',
          fillQuery: 'Please enter a query',
          fillLibrary: 'Please select or enter a target library',
          feedIdsRequired: 'When feed scope is "Selected Feeds Only", feed_ids cannot be empty',
          saveEditFailed: 'Failed to save changes',
          saveEditFailedWithError: 'Failed to save changes: {error}',
          ruleUpdated: 'Rule updated'
        }
      }
    }
  }
}
