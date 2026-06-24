export default {
  timeline: {
    toolbar: {
      daysTitle: 'Switch the loaded date range (up to 30 days)',
      daysOption: '{count} days',
      refresh: 'Refresh',
      loading: 'Loading…',
      refreshTitle: 'Refresh timeline',
      select: 'Select',
      selectTitle: 'Enter batch selection mode (any entry can be removed; explicit activity records will be deleted, others will only be hidden)',
      removeSelected: 'Remove ({count})',
      removeSelectedTitle: 'Remove selected ({count})',
      removeSelectedEmptyTitle: 'No removable items selected',
      cancel: 'Cancel',
      cancelTitle: 'Exit selection mode',
      pruneMissing: 'Clean invalid items',
      pruneMissingTitle: 'Clean explicit activity records that point to missing files',
      compact: 'Compact timeline',
      compactTitle: 'Compact activities.jsonl (dedupe / filter / atomic rewrite). Note: this physically rewrites the log file.',
      patternPlaceholder: 'Pattern delete: for example doc_20260129*',
      patternTitle: 'Batch hard-delete from activities.jsonl by pattern (glob supported: * ?). Compact the timeline first if possible.',
      hardDelete: 'Hard delete by pattern',
      hardDeleteTitle: 'Batch hard-delete by pattern (preview matches first, then confirm)'
    },
    empty: {
      loadingActivities: '⏳ Loading activities...',
      noActivities: '(No activities yet)'
    },
    sections: {
      today: 'Today',
      yesterday: 'Yesterday',
      thisWeek: 'This week',
      older: 'Older',
      collapse: 'Collapse ({count})',
      expandMore: 'Show more ({count})'
    },
    activity: {
      unnamed: '(Untitled)',
      document: '(Document)',
      file: '(File)',
      conversation: '(Conversation)',
      activity: '(Activity)',
      filteredInternalRecord: '(Filtered internal record)',
      hebbianTitle: 'Hebbian: {concepts} concepts · {synapses} synapses',
      selectToggle: 'Select / unselect',
      notRemovable: 'This item cannot be removed',
      removeOneTitle: 'Remove this record from the timeline'
    },
    tooltip: {
      libraryDoc: 'Library: {lib} · Document: {doc}',
      conversationWithTitle: 'conv_id: {id} · {title}',
      conversationId: 'conv_id: {id}'
    },
    messages: {
      activitiesLoaded: 'Activities loaded',
      heatmapLoaded: 'Heatmap loaded',
      compactConfirm:
        'Compact the timeline activity log (activities.jsonl)?\n\nThis action will:\n- dedupe: keep only the latest record for the same resource\n- filter: remove tombstone / missing-file / rss_import noise\n- atomically rewrite activities.jsonl\n\nContinue?',
      compactDone: 'Timeline compacted',
      compactSuccess: '✅ Timeline compacted\nKept: {kept}\nRemoved: {removed}\nFiltered rss_import: {rss}',
      compactFailed: 'Compact failed: {text}',
      previewDone: 'Preview completed',
      previewFailed: 'Preview failed: {text}',
      patternInputRequired: 'Please enter a pattern, for example doc_20260129*',
      noMatchedRecords: 'No matching records found',
      untitledSample: '(Untitled)',
      noSamples: '(No samples)',
      patternDeleteConfirm:
        'This will permanently delete {matched} records from activities.jsonl.\n\nPattern: {pattern}\n\nSamples:\n{samples}\n\nContinue?',
      patternDeleteDone: 'Pattern delete completed',
      patternDeleteSuccess: '✅ Deleted {removed} records, {remaining} remaining',
      patternDeleteFailed: 'Delete failed: {text}',
      deleteOneHardTip: 'This will delete the record from the timeline activity log.',
      deleteOneSoftTip: 'This only hides the item from the timeline and does not delete source data.',
      deleteOneConfirm: 'Remove this timeline record?\n\n{title}\n\n{tip}',
      deleteOneDone: 'Timeline record removed',
      deleteOneFailed: 'Remove failed: {text}',
      deleteSelectedConfirm:
        'Remove the selected {count} timeline records?\n\nExplicit activity records will be deleted from the log. Other items will only be hidden from the timeline.',
      deleteSelectedDone: 'Selected timeline records removed',
      deleteSelectedFailed: 'Batch remove failed: {text}',
      pruneConfirm:
        'Clean residual records left by deleted files?\n\nThis will rewrite activities.jsonl (explicit activity log records only).',
      pruneDone: 'Invalid records cleaned',
      pruneSuccess: '✅ Cleaned {removed} invalid records',
      pruneFailed: 'Clean failed: {text}',
      unknownError: 'Unknown error',
      unknown: 'Unknown'
    }
  },

  runtime: {
    card: {
      title: 'Room Runtime',
      mode: {
        current: 'Current',
        replay: 'Replay'
      },
      actions: {
        refresh: 'Refresh',
        refreshing: 'Refreshing…',
        pauseCurrent: 'Pause current run',
        resumeFromCheckpoint: 'Resume from checkpoint'
      },
      replay: {
        label: 'Replay runs',
        selectRun: 'Select a replay run',
        noRun: 'No replay runs'
      },
      badges: {
        current: 'Current',
        replay: 'Replay',
        resumed: 'Resumed',
        restartFresh: 'Restart fresh',
        fresh: 'Fresh',
        pausedAtCheckpoint: 'Paused at checkpoint',
        resumable: 'Can resume from checkpoint',
        canSendNewPrompt: 'Can send new prompt',
        resumeBlocked: 'Resume blocked',
        budgetExhausted: 'Budget exhausted'
      },
      skillStrategy: {
        builtinPlusCustom: 'Builtin + custom',
        customOnly: 'Custom only',
        builtinOnly: 'Builtin only'
      },
      skillSummary: {
        skills: 'Skills',
        enabled: '{count} enabled',
        applied: '{count} applied',
        resolved: '{count} resolved',
        steps: '{count} steps',
        appliedPrompt: 'Prompt applied',
        availableNotEnabled: 'Available but not enabled',
        missing: 'Missing',
        skipped: 'Skipped',
        source: 'Source {value}',
        event: 'Event {value}'
      },
      reason: {
        pauseRequested: 'Pause requested',
        stepBudgetExhausted: 'Step budget limit reached',
        newTopicDetected: 'New topic detected',
        checkpointMissing: 'Missing resumable checkpoint'
      },
      controlBlock: {
        runRunning: 'A run is currently in progress',
        pauseRequestedPendingCheckpoint: 'Pause has been requested and is waiting for a safe checkpoint',
        resumeReady: 'This run can resume from a checkpoint',
        budgetExhausted: 'Step budget has been exhausted',
        resumeBlockedError: 'Resume is blocked by an error'
      },
      status: {
        pauseRequested: 'Pause requested',
        interrupted: 'Interrupted',
        resumed: 'Resumed',
        completedAfterResume: 'Completed after resume',
        completed: 'Completed',
        running: 'Running',
        budgetExhausted: 'Budget exhausted',
        failed: 'Failed',
        noRun: 'No active run'
      },
      headline: {
        budgetExhausted: 'This run has reached the step budget limit',
        pauseRequested: 'The current run has received a pause request',
        interrupted: 'The run was interrupted at a checkpoint',
        completedAfterResume: 'The resumed run has completed',
        resumed: 'The run has resumed from a checkpoint',
        completed: 'The run has completed',
        runningResumed: 'Continuing the resumed run',
        running: 'Run in progress',
        lineageResumed: 'This run resumed from the previous checkpoint',
        restartFresh: 'This run restarted in fresh mode',
        fresh: 'This is a fresh run'
      },
      defaultHeadline: {
        replay: 'Run replay',
        replayWithId: 'Replay {id}',
        current: 'Run process'
      },
      meta: {
        viewingRun: 'Viewing {id}',
        phase: 'Phase {phase}',
        resumedFromRun: 'Resumed from {runId}'
      },
      summary: {
        budgetExhaustedAtStage: 'The current run stopped at stage {stage} because the step budget was exhausted.',
        budgetExhausted: 'The current run has reached the step budget limit.',
        pauseRequestedAtStage: 'Pause has been requested. The run will stop at a safe checkpoint in stage {stage}.',
        pauseRequested: 'Pause has been requested. The run will become interruptible after it reaches a safe checkpoint boundary.',
        interruptedAtStage: 'The run was interrupted at the checkpoint corresponding to {stage}.',
        interrupted: 'The run was interrupted at the latest valid checkpoint.',
        resumedAtStage: 'The current run resumed from the checkpoint corresponding to {stage} and continues along the existing lineage.',
        resumed: 'The current run resumed from the latest valid checkpoint and continues along the existing lineage.',
        completedAfterResume: 'This run completed after resuming and avoided re-executing completed side effects whenever possible.',
        completedResumed: 'This run completed after resuming and preserved the resume semantics of the previous run.',
        waitingCheckpointAtStage: 'Pause has been requested. Waiting for a safe checkpoint in stage {stage}.',
        waitingCheckpoint: 'Pause has been requested. Waiting for a safe checkpoint.',
        resumeReadyAtStage: 'The run was interrupted and can resume from {stage}.',
        resumeReady: 'The run was interrupted and can resume from a checkpoint.',
        runRunning: 'A run is currently in progress, so new prompts are not accepted for now.'
      },
      detail: {
        runtime: 'Runtime',
        resumePoint: 'Resume point',
        checkpoint: 'Checkpoint',
        checkpointRef: 'Checkpoint ref',
        stopReason: 'Stop reason',
        pauseReason: 'Pause reason',
        controlBlock: 'Control block',
        pausedAt: 'Paused at',
        pauseRequestedAt: 'Pause requested at',
        resumedFrom: 'Resumed from',
        resumeReason: 'Resume reason',
        lastCompleted: 'Last completed',
        stepBudget: 'Step budget',
        resumeCapability: 'Resume capability',
        newPrompt: 'New prompt'
      },
      detailValue: {
        canResumeFromCheckpoint: 'Can resume from the latest valid checkpoint',
        canStartFreshSend: 'Currently allowed to start a fresh send'
      },
      budget: {
        usedOfTotal: '{used}/{total}',
        used: '{count} used',
        total: '{count} total',
        remaining: '{count} remaining',
        exhausted: 'Exhausted',
        unlimited: 'Unlimited'
      },
      effects: {
        skipped: 'Skipped {count}',
        reused: 'Reused {count}',
        execute: 'Executed {count}',
        repair: 'Repaired {count}',
        summaryReuse: 'During resume, side effects that were already completed or reusable are skipped or reused to avoid duplicate execution.',
        summaryRepair: 'Some side effects are marked as repair, meaning they are not part of the completed and reusable set.'
      },
      history: {
        supervisor: 'Supervisor',
        memory: 'Memory',
        memoryRead: 'Memory read',
        memoryWrite: 'Memory write',
        memoryResume: 'Memory resume',
        read: 'Read',
        write: 'Write',
        resume: 'Resume',
        success: 'Success',
        checkpointDone: 'Checkpoint completed',
        continueFromCheckpoint: 'Continue from checkpoint'
      },
      empty: {
        loadingReplay: 'Loading replay…',
        loadingCurrent: 'Loading run result…',
        noReplayResult: 'No replay result yet',
        chooseReplay: 'Please select a replay run',
        noResult: 'No run result yet'
      }
    },

    timeline: {
      mode: {
        resumed: 'Resumed',
        restartFresh: 'Restart fresh',
        fresh: 'Fresh'
      },
      badges: {
        waitingCheckpoint: 'Waiting for checkpoint',
        resumable: 'Resumable',
        fromStage: 'From {stage}',
        checkpointStage: 'Checkpoint {stage}',
        skippedEffects: 'Skipped {count} side effects',
        budgetExhausted: 'Budget exhausted',
        runtime: 'Runtime',
        checkpoint: 'Checkpoint',
        effects: 'Effects',
        final: 'Final',
        error: 'Error',
        aborted: 'Aborted'
      },
      status: {
        waitingCheckpoint: 'Waiting for safe checkpoint',
        replayLoading: 'Loading replay…',
        replayReady: 'Replay ready',
        noReplayResult: 'No replay result',
        selectReplay: 'Select a replay run',
        noReplay: 'No replay available',
        viewable: 'Viewable',
        noRuntime: 'No runtime'
      },
      headline: {
        waitingCheckpoint: 'Pause requested, waiting for safe checkpoint'
      },
      summary: {
        interruptedAtStageWithReason: 'This run was interrupted at stage {stage}. Reason: {reason}.',
        interruptedAtStage: 'This run was interrupted at stage {stage}.',
        interruptedWithReason: 'This run was interrupted. Reason: {reason}.',
        interrupted: 'This run was interrupted.',
        canResume: 'It can currently resume from a checkpoint.',
        budgetStoppedAtStage: 'This run stopped at stage {stage} because the step budget was exhausted.',
        budgetStopped: 'This run stopped because the step budget was exhausted.',
        pauseWaitingStage: 'Pause has been requested. Waiting for a safe checkpoint in stage {stage}.',
        pauseWaiting: 'Pause has been requested. Waiting for a safe checkpoint.',
        pauseWillStopAtStage: 'Pause has been requested. This run will stop at a safe point in stage {stage}.',
        pauseWillStop: 'Pause has been requested. This run will stop at a safe point.',
        pauseReason: 'Pause reason: {reason}.',
        completedAfterResumeFromStage: 'This run has completed after resuming from {stage}.',
        completedAfterResume: 'This run has completed after resuming from a checkpoint.',
        completedFresh: 'This fresh run has completed.',
        completed: 'This run has completed.',
        resumedFromStage: 'The run is continuing from {stage}.',
        resumed: 'The run is continuing from a checkpoint.',
        runningAtStage: 'This run is currently at {stage}.',
        running: 'This run is in progress.',
        lineageResumed: 'This run comes from a previous checkpoint lineage.',
        restartFresh: 'This run restarted in fresh mode and does not reuse previous checkpoints.'
      },
      entry: {
        waitingCheckpoint: 'Waiting for safe checkpoint',
        status: 'Status {value}',
        mode: 'Mode {value}',
        fromStage: 'From {stage}',
        checkpoint: 'Checkpoint'
      },
      hint: {
        pauseWaitingStage: 'Pause has been requested. Waiting for a safe checkpoint in stage {stage}.',
        pauseWaiting: 'Pause has been requested. Waiting for a safe checkpoint.',
        resumeFromStage: 'Can resume from {stage}.',
        resumeFromRecent: 'Can resume from the most recent checkpoint.',
        runRunning: 'A run is currently in progress, so new prompts cannot be accepted for now.',
        budgetExhausted: 'The step budget has been exhausted; this run cannot resume.',
        resumeBlockedError: 'Resume is currently blocked by an error.',
        errorBlockingResume: 'There is currently an error blocking resume.',
        resumedFromStage: 'The run is continuing from {stage}.',
        resumed: 'The run is continuing from a checkpoint.'
      },
      actions: {
        requesting: 'Requesting…',
        pauseRequested: 'Pause requested',
        resuming: 'Resuming…'
      },
      effects: {
        allSkipped: '{count} completed side effects were skipped during resume',
        skipCount: 'Skip {count}',
        reuseCount: 'Reuse {count}',
        executeCount: 'Execute {count}',
        repairCount: 'Repair {count}',
        summaryDisposition: 'Side effect handling: {items}',
        recorded: '{count} side effect handling results recorded'
      },
      errors: {
        pauseNotAccepted: 'Pause operation was not accepted',
        pauseFailed: 'Pause operation failed',
        resumeNotAccepted: 'Resume operation was not accepted',
        resumeFailed: 'Resume operation failed'
      }
    }
  }
}
