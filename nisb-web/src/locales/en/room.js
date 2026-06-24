export default {
  header: {
    fallbackTitle: 'Room',

    actions: {
      exitRoom: 'Exit room',
      workspace: 'Workspace',
      workspaceShort: 'Space',
      refresh: 'Refresh',
      roles: 'Roles',
      settings: 'Settings',
      menu: 'Menu'
    },

    stats: {
      users: 'Users',
      roles: 'Roles',
      active: 'Active',
      usersCount: 'Users {count}',
      rolesCount: 'Roles {count}',
      activeCount: 'Active {count}',
      running: 'Running',
      inheritWorkspaceContext: 'Inherit context',
      inheritFocusRoot: 'Inherit focus'
    },

    badges: {
      room: 'ROOM',
      roomCompact: 'R',
      supervisor: 'SUPERVISOR',
      supervisorCompact: 'SUP'
    },

    bindings: {
      openWorkspace: 'Open workspace',
      workspace: 'Workspace',
      workspaceShort: 'Space',
      focus: 'Focus root',
      focusShort: 'Focus',
      focusTitleWorkspaceAndRoot: 'Open workspace and restore file snapshot: {workspace} · {root}',
      focusTitleWorkspace: 'Open workspace and restore file snapshot: {workspace}',
      focusTitleRoot: 'Jump to the left sidebar focus root: {root}',
      focusTitleFallback: 'Open workspace or jump to the focus root'
    },

    plan: {
      latest: 'Latest plan',
      short: 'Plan'
    },

    messages: {
      workspaceNotBound: 'The current room is not bound to a workspace_id yet. Please save workspace_context in room settings first.',
      noWorkspaceOrFocus: 'The current room has no available workspace or focus_root.',
      openingWorkspaceWithState: 'Opening workspace and restoring file state: {workspace}',
      openingFocusRoot: 'Expanding the left sidebar and jumping to the focus root: {root}',
      restoringWorkspaceState: 'Restoring workspace file state: {workspace}',
      jumpedToFocusRoot: 'Jumped to focus root: {root}'
    }
  },

  settingsModal: {
    title: 'Room settings',
    kicker: 'Room console',
    description: 'Explicitly configure the title, summary, Supervisor, default reply role, active roles, and the workspace / focus_root bound to the room. You can also use the minimal P6 test control panel in orchestration settings to build stable notebook probe scenarios for supervisor / worker / skill.',

    actions: {
      close: 'Close',
      cancel: 'Cancel',
      save: 'Save',
      saving: 'Saving...'
    },

    common: {
      defaultProvider: 'openai',
      systemDefault: 'System default',
      on: 'on',
      off: 'off'
    },

    footer: {
      p6Supervisor: 'Current test entry: supervisor probe. After saving, you can more reliably verify the success-path final state and the supervisor notebook allowed path.',
      p6Worker: 'Current test entry: worker probe. After saving, you can more reliably verify worker notebook write deny.',
      p6Skill: 'Current test entry: skill probe. After saving, you can more reliably verify skill notebook write deny.',
      supervisorMode: 'After saving, Supervisor orchestration will be used first; provider={provider}, model={model}, fs_read={fsRead}, notebook={notebook}.',
      defaultRole: 'Default reply role after saving: {role}',
      fallback: 'After saving, execution follows active_roles / supervisor_enabled.'
    }
  },

  externalMcpPublish: {
    defaultClientLabel: 'External MCP client',

    loadStatusFailed: 'Failed to load external MCP publish status',

    missingRoomIdEnable: 'Missing room_id, unable to enable external MCP publishing',
    enableFailed: 'Failed to enable external MCP publishing',
    enableSuccess: 'External MCP publishing is enabled. The token will only be shown once.',

    missingRoomIdRevoke: 'Missing room_id, unable to revoke external MCP publishing',
    revokeFailed: 'Failed to revoke external MCP publishing',
    revokeSuccess: 'External MCP publishing has been revoked.',

    missingRoomIdRegenerate: 'Missing room_id, unable to regenerate the token',
    regenerateFailed: 'Failed to regenerate the external MCP token',
    regenerateSuccess: 'A new external MCP token has been generated. The old token should stop working immediately.',

    noConfigToCopy: 'There is no MCP configuration to copy',
    clipboardUnsupported: 'This environment does not support copying to the clipboard',
    copyLibrechatSuccess: 'MCP client configuration copied.',
    copyGenericSuccess: 'Generic MCP configuration copied.',
    copyConfigFailed: 'Failed to copy MCP configuration',

    noPlaintextTokenToCopy: 'There is no plaintext token to copy. After refresh, the token will not be shown again.',
    copyTokenSuccess: 'External MCP token copied.',
    copyTokenFailed: 'Failed to copy token'
  },

  chatRuntime: {
    stream: {
      toolCall: 'Calling tool...',
      toolResult: 'Tool returned. Preparing the answer...',
      final: 'Finishing output...',
      meta: 'Preparing request...',
      roomRuntime: 'Room is running...',
      default: 'Streaming response...'
    },

    status: {
      pauseRequested: 'pause requested',
      waitingCheckpoint: 'waiting checkpoint',
      interrupted: 'interrupted',
      resumed: 'resumed',
      completedAfterResume: 'completed after resume',
      completed: 'completed',
      budgetExhausted: 'budget exhausted',
      roomRuntimeActive: 'room runtime active',
      roomRuntimeDetached: 'room runtime detached',
      roomRuntimeIdle: 'room runtime idle',
      aborted: 'aborted',
      error: 'error'
    },

    control: {
      pauseRequested: 'Pause requested. Waiting for a safe checkpoint.',
      waitingCheckpoint: 'A safe checkpoint is pending. New prompts are temporarily blocked.',
      resumeReady: 'The current run is interrupted. Resume from the checkpoint first.',
      interrupted: 'The current run is interrupted. New prompts are temporarily blocked.',
      running: 'The current run is still active. New prompts are temporarily blocked.',
      budgetExhausted: 'The step budget is exhausted. Sending is temporarily unavailable.',
      resumeBlockedError: 'A blocking resume error is present. New prompts are temporarily blocked.'
    },

    messages: {
      stopped: 'Stopped.'
    },

    errors: {
      roomIdMissing: 'room_id missing in room mode'
    }
  },
  
  settingsBasicCard: {
    title: 'Basic settings',
    eyebrow: 'Room identity',
    subtitle: 'Set the visible Room identity, summarize MCP capability state, and manage federation access from the owner cockpit.',

    chips: {
      providerOn: 'MCP provider on',
      providerOff: 'MCP provider off',
      sharedOn: 'Shared auto reply on',
      sharedOff: 'Shared auto reply off',
      federationManageable: 'Federation manageable',
      federationReadonly: 'Federation read-only'
    },

    sections: {
      identity: {
        title: 'Room profile',
        subtitle: 'These fields define how the Room is presented across workspace panels, summaries, and capability surfaces.'
      }
    },

    fields: {
      title: {
        label: 'Title',
        placeholder: 'Room title'
      },
      summary: {
        label: 'Summary',
        placeholder: 'Describe what this Room is for'
      },
      scratchpad: {
        label: 'Scratchpad',
        placeholder: 'Private notes for this Room'
      }
    },

    values: {
      emptyDash: '-',
      ready: 'ready',
      missing: 'missing',
      yes: 'yes',
      no: 'no'
    },

    roomMcpSummary: {
      title: 'Room MCP publish summary',
      hint: 'This shows the saved publish-state summary for the current Room. The published object should only represent the room-configured shared capability.',

      cards: {
        publishStatus: 'Publish status',
        providerName: 'Provider display name',
        providerSummary: 'Provider summary',
        sharedSemantic: 'Shared semantic summary',
        sharedBoundary: 'Shared boundary summary'
      },

      values: {
        providerNameUnset: 'Not set. A default display name will be used after saving.',
        providerSummaryUnset: 'Not set. It is recommended to summarize reply_mode, active workers / skills, workspace / focus root, and shared boundary.',
        notPublished: 'Not published',
        published: 'Published',
        sharedBoundaryEnabled: 'Shared Auto Reply is enabled. Members and federated members consume the owner-saved room-configured shared reply semantics by default.',
        sharedBoundaryDisabled: 'Shared Auto Reply is currently disabled. Non-owners default back to manual.',
        workspaceUnbound: 'workspace=not bound',
        focusRootUnset: 'focus_root=not set',
        boundaryTemplate: '{base} {workspace}; {focus}; owner ambient private workspace / fs / memory is not included.'
      },

      notices: {
        providerOnSharedOff: 'Room MCP publish is enabled, but Shared Auto Reply is still disabled. Future provider calls should preserve formal-first results instead of implicitly enabling shared reply.',
        providerOnSharedOn: 'The current publish should only reuse the shared capability explicitly saved by the owner in room settings. It should not automatically expose private workspace, fs, or memory global capabilities.'
      }
    },

    federation: {
      eyebrow: 'Federation',
      title: 'Cross-VPS Federation',
      hint: 'Member access only. This area makes invite state, owner user_id, and minimal revocation controls visible.',

      state: {
        ownerManage: 'Owner manage',
        readonly: 'Read-only',
        invites: 'invites: {count}',
        members: 'members: {count}',
        handler: 'handler: {state}',
        loading: 'loading: {state}'
      },

      issue: {
        title: 'Issue federation invite'
      },

      fields: {
        targetPeer: {
          label: 'Target peer',
          emptyOption: 'Select a peer'
        },
        inviteTtl: {
          label: 'Invite TTL'
        }
      },

      ttl: {
        oneDay: '1 day',
        sevenDays: '7 days'
      },

      actions: {
        issueInvite: 'Issue invite',
        issuing: 'Issuing...',
        refreshInvites: 'Refresh invites',
        refreshInvitesTitle: 'Refresh current room invites',
        refreshMembers: 'Refresh members',
        refreshing: 'Refreshing...',
        extending: 'Extending...',
        extendOneDay: 'Extend +1d',
        extendSevenDays: 'Extend +7d',
        revoking: 'Revoking...',
        revoke: 'Revoke',
        revokeAccess: 'Revoke Access'
      },

      disabledReasons: {
        ownerOnly: 'owner only',
        refreshHandlerMissing: 'refresh handler missing',
        inviteListLoading: 'invite list loading stuck or running'
      },

      notices: {
        readonly: 'This Room contains federation information, but you are not the owner. Invite and revoke management actions are unavailable.'
      },

      summary: {
        title: 'Federation summary',
        cards: {
          activeInvites: 'Active invites',
          usedInvites: 'Used invites',
          revokedInvites: 'Revoked invites',
          expiredInvites: 'Expired invites',
          joinedMembers: 'Joined members',
          revokedMembers: 'Revoked members'
        }
      },

      latestInvite: {
        title: 'Latest invite',
        fields: {
          id: 'ID',
          status: 'Status',
          roomId: 'Room ID',
          ownerUser: 'Owner user',
          peer: 'Peer',
          token: 'Token',
          created: 'Created',
          expires: 'Expires',
          usedAt: 'Used at',
          usedBy: 'Used by'
        },
        helperPrefix: 'Send',
        helperSuffix: 'to the remote side. The remote side still accepts it from FedMenu.'
      },

      history: {
        title: 'Invite history',
        empty: 'No invites yet.',
        filters: {
          all: 'All',
          active: 'Active',
          used: 'Used',
          revoked: 'Revoked',
          expired: 'Expired'
        },
        meta: {
          room: 'room',
          owner: 'owner',
          peer: 'peer',
          created: 'created',
          expires: 'expires',
          token: 'token'
        }
      },

      joinedMembers: {
        title: 'Joined Members',
        loading: 'Loading joined members...',
        empty: 'No joined members yet.',
        meta: {
          peer: 'peer'
        }
      }
    }
  },

  settingsOrchestrationCard: {
    title: 'Orchestration settings',
    eyebrow: 'Room runtime',
    subtitle: 'Control how this Room authorizes shared auto reply, exposes MCP capabilities, routes replies, and delegates supervisor work.',

    chips: {
      sharedAutoReplyOn: 'Shared auto reply on',
      sharedAutoReplyOff: 'Shared auto reply off',
      supervisorOn: 'Supervisor on',
      supervisorOff: 'Supervisor off',
      workerConcurrency: 'Workers: {value}'
    },

    sections: {
      roomBehavior: {
        title: 'Room behavior',
        subtitle: 'Define whether joined and federated members can use shared room-level auto reply semantics.'
      },
      mcpCapabilities: {
        title: 'MCP capabilities',
        subtitle: 'Manage Room MCP sharing, federation-facing grants, and external MCP publish from one capability block.'
      },
      replyRouting: {
        title: 'Reply routing',
        subtitle: 'Choose whether replies stay manual, go to a default role, or pass through the supervisor runtime.'
      }
    },

    common: {
      emptyOption: 'Empty',
      emptyValue: '—',
      trueValue: 'true',
      falseValue: 'false',
      defaultProvider: 'openai',
      defaultModel: 'Use system default',
      defaultSkillStrategy: 'builtin_plus_custom',
      defaultStepBudget: '0',
      defaultScope: 'minimal'
    },

    toggles: {
      supervisorEnabled: {
        title: 'supervisor_enabled',
        description: 'Supervisor capability switch. When enabled, Supervisor can be configured and used; whether it participates in automatic replies is still determined by reply_mode.'
      },
      inheritWorkspaceContext: {
        title: 'inherit_workspace_context',
        description: 'Let the room keep inheriting the workspace binding.'
      },
      inheritFocusRoot: {
        title: 'inherit_focus_root',
        description: 'Let the room keep inheriting the focus_root path.'
      },
      applyAfterSave: {
        title: 'Apply to the left sidebar immediately after save',
        description: 'After saving the room configuration, sync workspace_context to the left workspace UI immediately.'
      },

      sharedAutoReply: {
        title: 'Room-level Shared Auto Reply',
        description: 'When enabled, joined members and federated members enter room-level auto-reply authorization semantics. When disabled, non-owners default to manual behavior.'
      }
    },

    fields: {
      replyMode: {
        label: 'reply_mode',
        options: {
          manual: 'manual (silent conversation)',
          directRole: 'direct_role (default role replies directly)',
          supervisorDirect: 'supervisor_direct (Supervisor replies directly)',
          supervisor: 'supervisor (multi-role orchestration)'
        }
      },

      orchestrationSummary: {
        label: 'Current orchestration summary'
      },

      workerConcurrency: {
        label: 'Worker concurrency',
        hint: 'Controls how many room workers may run at the same time. Use 1 for the safest low-resource mode; 2 is recommended for RAG-heavy rooms.',
        options: {
          option1: '1 · safest',
          option2: '2 · recommended',
          option3: '3 · advanced',
          option4: '4 · experimental'
        }
      },

      workerConcurrencySummary: {
        label: 'Worker concurrency summary',
        safest: '{value} worker at a time. Safest for low-resource VPS instances.',
        recommended: '{value} workers at a time. Recommended for RAG-heavy rooms.',
        faster: '{value} workers at a time. Advanced option for API-bound workflows.',
        experimental: '{value} workers at a time. Experimental.'
      },

      defaultReplyRole: {
        label: 'default_reply_role_id',
        emptyOption: 'Empty'
      },

      defaultReplyRoleSummary: {
        label: 'Current description',
        withRole: 'Default reply role: {role}',
        withoutRole: 'No default reply role is currently selected.'
      },

      stepBudget: {
        label: 'Step budget',
        placeholder: '0',
        hint: 'Limit how many steps Supervisor can advance in a single run. When the budget is exhausted, execution stops at a resumable point. Set 0 for unlimited steps, subject to the backend contract.'
      },

      stepBudgetSummary: {
        label: 'Current budget summary',
        current: 'Current step budget: {value}.',
        unlimited: '0 means unlimited steps, subject to the backend contract.',
        limited: 'Supervisor will be limited to at most {value} steps in a single run.'
      },

      supervisorSkillStrategy: {
        label: 'supervisor_skill_strategy',
        hint: 'This only determines the skill composition strategy of the Supervisor prompt. It does not automatically change worker, filesystem, MCP, or writeback permissions.',
        options: {
          builtinPlusCustom: 'builtin_plus_custom (built-in baseline + Workspace Skills)',
          builtinOnly: 'builtin_only (built-in baseline only)',
          customOnly: 'custom_only (Workspace Skills only)'
        }
      },

      supervisorProvider: {
        label: 'supervisor_provider'
      },

      supervisorModel: {
        label: 'supervisor_model',
        hint: 'The shared model catalog is used here. If you switch provider, the model from the previous provider is cleared automatically.'
      },

      supervisorTemperature: {
        label: 'supervisor_temperature',
        placeholder: 'Optional, for example 0.2'
      },

      supervisorMaxTokens: {
        label: 'supervisor_max_tokens',
        placeholder: 'Optional, for example 4096'
      },

      fsReadScope: {
        label: 'mcp_overrides.fs_read_scope'
      },

      workspaceFocusPreview: {
        label: 'Current workspace / focus_root',
        withFocus: 'workspace={workspace}, focus_root={root}',
        withoutFocus: 'There is no available focus_root yet; enabling fs_read / notebook_write still does not imply privilege escalation.'
      },

      notebookDir: {
        label: 'mcp_overrides.notebook_dir',
        placeholder: '_room_supervisor_notebooks'
      },

      notebookFilename: {
        label: 'mcp_overrides.notebook_filename',
        placeholder: 'supervisor.md'
      },

      notebookTitle: {
        label: 'mcp_overrides.notebook_title',
        placeholder: 'Supervisor notebook'
      },

      notebookSectionTitle: {
        label: 'mcp_overrides.notebook_section_title',
        placeholder: 'latest'
      },

      p6ProbeActor: {
        label: 'p6_test_control.notebook_probe_actor',
        hint: 'This only stabilizes test intent construction. Whether writing is actually allowed still depends on the formal backend permission chain.',
        options: {
          off: 'off (keep the entry only, do not inject probe)',
          supervisor: 'supervisor (validate allowed path / final success alignment)',
          worker: 'worker (validate notebook write deny)',
          skill: 'skill (validate skill notebook write deny)'
        }
      },

      p6ProbeSummary: {
        label: 'Current test intent'
      }
    },

    helpers: {
      replyModeGuide: 'Recommended interpretation: manual = user-only conversation, no automatic reply; direct_role = default role replies directly; supervisor_direct = Supervisor answers directly; supervisor = Supervisor coordinates multiple roles.',
      currentSupervisorState: 'Current strategy: {strategy}, current provider: {provider}, current model: {model}, current step budget: {budget}.',
      defaultRoleSync: 'Note: on save, default_reply_role_id is automatically ensured to belong to active_roles.'
    },

    supervisorModelSection: {
      title: 'Supervisor model',
      subtitle: 'Supervisor is the room-level orchestrator / direct-answer runtime, not a normal role member. Its model and controlled capabilities are configured here together.'
    },

    strategyInfo: 'builtin_only keeps only the built-in Supervisor baseline; custom_only uses only currently enabled workspace skills; builtin_plus_custom combines the stable baseline with workspace skills.',

    supervisorCapabilitySection: {
      title: 'Supervisor controlled capabilities',
      subtitle: 'This configures only the room-level capabilities of Supervisor. It does not automatically grant fs or notebook permissions to normal roles.'
    },

    supervisorCapabilities: {
      fsReadEnabled: {
        title: 'mcp_overrides.fs_read_enabled',
        description: 'Allow Supervisor to perform controlled read-only directory probing on the room focus_root before answering.'
      },
      notebookWriteEnabled: {
        title: 'mcp_overrides.notebook_write_enabled',
        description: 'Allow Supervisor to write the current-round summary into a controlled notebook. The write path is still constrained by workspace / focus_root.'
      }
    },

    notebookInfo: 'Supervisor notebook is a room-level notebook, not a role notebook. It is best used only for high-level summaries such as plans, conclusions, TODOs, and risks.',

    p6TestControlSection: {
      title: 'P6 test control panel',
      subtitle: 'Used only for final P6-V1 verification to help stably construct notebook write allow / deny scenarios. It does not replace formal permission checks.',
      panelEnabled: {
        title: 'p6_test_control.panel_enabled',
        description: 'Show the minimal test entry. When disabled, no extra test request_args are injected.'
      }
    },

    p6ProbeSummary: {
      disabled: 'The P6 test control panel is currently disabled.',
      supervisor: 'The test is currently constructed as a supervisor probe, suitable for validating the success-path final state and the notebook allowed path.',
      worker: 'The test is currently constructed as a worker probe, suitable for stably reproducing worker notebook write deny.',
      skill: 'The test is currently constructed as a skill probe, suitable for stably reproducing skill notebook write deny.',
      off: 'The test entry is currently shown, but no notebook probe actor is injected.'
    },

    warnings: {
      strategyInfo: 'builtin_only keeps only the built-in Supervisor baseline; custom_only uses only currently enabled workspace skills; builtin_plus_custom combines the stable baseline with workspace skills.',
      notebookInfo: 'Supervisor notebook is a room-level notebook, not a role notebook. It is best used only for high-level summaries such as plans, conclusions, TODOs, and risks.',
      p6TemporaryUse: 'It is recommended to enable this only temporarily when validating reply_mode=supervisor or supervisor_direct. After verification, switch notebook_probe_actor back to off or disable the entry directly.',
      replyModeManual: "Current reply_mode=manual. Normal user messages do not automatically trigger a worker or Supervisor. If you explicitly use {'@'}role or {'@'}ai, a single reply can still be triggered.",
      replyModeSupervisorDirect: 'Current reply_mode=supervisor_direct. Normal user messages are answered directly by Supervisor without entering multi-role delegation. Even if active_roles or default_reply_role_id is still set, they are not automatically triggered.',
      replyModeSupervisor: 'Current reply_mode=supervisor. Even if default_reply_role_id is set, the default role is not used as an implicit direct-answer entry. The default role is mainly retained for configuration continuity or future switching.',
      replyModeDirectRole: 'Current reply_mode=direct_role, but default_reply_role_id is not set yet. It is recommended to choose a default role first, otherwise ordinary messages will not hit the default direct-reply role.'
    },

    audit: {
      fs: {
        title: 'Supervisor FS audit',
        fields: {
          enabled: 'enabled',
          status: 'status',
          reason: 'reason',
          focusRoot: 'focus_root',
          scope: 'scope',
          updatedAt: 'updated_at',
          toolCalls: 'tool_calls',
          toolResults: 'tool_results'
        }
      },

      notebook: {
        title: 'Supervisor Notebook audit',
        fields: {
          status: 'status',
          message: 'message',
          relativePath: 'relative_path',
          updatedAt: 'updated_at',
          toolCalls: 'tool_calls',
          toolResults: 'tool_results'
        }
      }
    }
  },

  externalMcp: {
    eyebrow: 'Federated capability',
    title: 'Room MCP external publish',
    subtitle: 'Publish this Room as a room-scoped MCP capability for external clients. This is separate from federation grants and the global provider catalog.',

    defaults: {
      clientLabel: 'External MCP client'
    },

    fields: {
      status: 'Publish status',
      providerId: 'Provider ID',
      sourceRoomId: 'Source Room ID',
      resultView: 'Result View',
      expiresAt: 'Expires at',
      lastUsed: 'Last used',
      usedCount: 'Used count',
      clientLabel: 'Client label',
      expiresInDays: 'Expiry in days',
      maxCalls: 'Max successful room calls',
      clientLabelInput: 'Client label',
      endpoint: 'MCP Endpoint'
    },

    config: {
      title: 'Access policy',
      subtitle: 'Set the token lifetime, successful-call limit, client label, and endpoint before enabling or regenerating access.'
    },

    placeholders: {
      expiresInDays: 'Example: 30 or 0.0417',
      maxCalls: 'Leave empty for unlimited, for example: 1',
      clientLabel: 'Example: team knowledge base / external support assistant',
      endpoint: 'Example: https://mcp.nisb.me/nisb/mcp'
    },

    hints: {
      expiresInDays: 'Minimum 1 hour, maximum 30 days. Decimal days are supported; 0.0417 is about 1 hour.',
      maxCalls: 'Only successful room questions are counted. Connections, tool lists, and provider_list do not consume calls.',
      clientLabel: 'Only used by the owner to identify who this external publish was issued for.',
      endpoint: 'When empty, the frontend derives the endpoint from the current site. Production deployments should use the official MCP domain.'
    },

    states: {
      loading: 'Loading',
      active: 'Published',
      revoked: 'Revoked',
      expired: 'Expired',
      notPublished: 'Not published'
    },

    values: {
      none: 'None',
      neverUsed: 'Never used'
    },

    token: {
      onceTitle: 'Plaintext token is shown only once',
      onceSubtitle: 'Copy it now and store it in the external client. Refreshing this page will hide the plaintext token.'
    },

    actions: {
      refresh: 'Refresh status',
      refreshing: 'Refreshing…',
      enableTitle: 'Enable Room MCP external publish',
      enableHelp: 'Generate a dedicated token and config for third-party MCP clients.',
      enable: 'Enable publish',
      enabling: 'Enabling…',
      reenableTitle: 'Re-enable external MCP publish',
      reenableHelp: 'Re-enabling generates a new external_mcp_publish token. Old tokens should not recover.',
      reenable: 'Re-enable',
      regenerateTitle: 'Regenerate token',
      regenerateHelp: 'After a new token is generated, the old token should fail immediately. The new token is still shown only once.',
      regenerate: 'Regenerate',
      regenerateToken: 'Regenerate token',
      regenerating: 'Generating…',
      revokeTitle: 'Revoke external access',
      revokeHelp: 'After revocation, external clients using the old token should fail immediately. Existing room MCP and federation behavior is not changed.',
      revoke: 'Revoke',
      revoking: 'Revoking…',
      copyLibreChatTitle: 'Copy MCP client config',
      copyLibreChatTemplateTitle: 'Copy MCP client config template',
      copyGenericTitle: 'Copy generic MCP config',
      copyGenericTemplateTitle: 'Copy generic MCP config template',
      copyWithTokenHelp: 'The current config includes the newly generated token. Save it into the external client now; it will not be shown again after refresh.',
      copyTemplateHelp: 'The current config will not include a plaintext token. Regenerate a token if you need a complete config.',
      copyGenericHelp: 'Copy a streamable HTTP config that generic MCP clients can use as a reference.',
      copy: 'Copy',
      copying: 'Copying…',
      copyToken: 'Copy token'
    },

    notices: {
      notPublished: 'This room has not enabled external MCP publishing. No external_mcp_publish token is generated, and no third-party client is authorized.',
      activeNoToken: 'This room is published for external MCP clients. For security, the plaintext token is not shown after refresh. Regenerate the token if you need a complete config with token.',
      expired: 'This external MCP publish has expired. External clients should no longer be able to use the old token. Regenerate access if needed.',
      revoked: 'This external MCP publish has been revoked. External clients should no longer be able to use the old token. Re-enable publishing if needed.'
    }
  },

  roomMcpPanel: {
    eyebrow: 'Room MCP',
    title: 'Publish as MCP Provider',
    subtitle: 'Publish the explicitly saved shared capability in this Room as a reusable MCP capability object. This does not expose the owner ambient private scope.',

    chips: {
      providerOn: 'Provider enabled',
      providerOff: 'Provider disabled',
      sharedOn: 'Shared capability on',
      sharedOff: 'Shared capability off'
    },

    sections: {
      provider: {
        title: 'Provider configuration',
        subtitle: 'Define how this Room capability appears to other workers and MCP consumers.'
      },
      publication: {
        title: 'Publication Record',
        subtitle: 'This is the current formal publication record for the source Room. It is provider metadata, not automatic consumer authorization.'
      },
      shareRef: {
        title: 'Grant Artifact / Share Ref',
        subtitle: 'The owner generates a grant-backed artifact. The familiar share-ref interaction is preserved, but the backend semantics should be verifiable and revocable.'
      },
      grants: {
        title: 'Grant management',
        subtitle: 'Review owner-visible grants, check active / revoked / expired state, and revoke active grants when needed.'
      }
    },

    toggles: {
      providerEnabled: {
        title: 'Enable Room MCP publish',
        description: 'When enabled, this Room can appear as a standard MCP provider for other workers to bind and consume.'
      }
    },

    fields: {
      providerName: {
        label: 'Provider display name',
        placeholder: 'Example: Room Shared Capability / Release Candidate',
        hint: 'Used in frontend lists and summaries. When empty, the backend or default summary can provide a fallback.'
      },
      providerSummary: {
        label: 'Provider summary',
        placeholder: 'Example: Execute shared reply capability from current room settings',
        hint: 'Describe the reply semantics, enabled workers / skills, and sharing boundary.'
      },
      publishStatus: {
        label: 'Current publish status'
      },
      boundarySummary: {
        label: 'Shared boundary summary'
      },
      publicationState: {
        label: 'Publication State'
      },
      providerId: {
        label: 'Provider ID'
      },
      visibilityMode: {
        label: 'Visibility Mode'
      },
      boundaryHint: {
        label: 'Boundary Hint'
      },
      publishedAt: {
        label: 'Published At'
      },
      updatedAt: {
        label: 'Updated At'
      },
      shareRefPreview: {
        label: 'Artifact / Share Ref preview',
        hint: 'This is the minimal shareable artifact descriptor. It represents the room-configured shared capability and does not include owner private workspace / fs / memory / notebook global capabilities.'
      },
      shareRefStatus: {
        label: 'Current grant status'
      },
      issuedAt: {
        label: 'Last issued at'
      },
      consumerBoundary: {
        label: 'Consumer boundary hint'
      },
      grantId: {
        label: 'Grant ID'
      },
      artifactId: {
        label: 'Artifact ID'
      },
      grantTotal: {
        label: 'Total grants'
      },
      grantActive: {
        label: 'Active'
      },
      grantRevoked: {
        label: 'Revoked'
      },
      grantExpired: {
        label: 'Expired'
      }
    },

    helpers: {
      providerBoundary: 'The published object should only wrap the room-configured shared capability explicitly saved in room settings. It should not automatically expose private workspace, private fs, or private memory global capabilities.',
      publicationBoundary: 'Publication controls whether this Room capability can be published, discovered, and described. Actual consumption by an external consumer still requires a grant or artifact.',
      shareRefBoundary: 'At this stage, the owner side focuses on generating, copying, reviewing, and revoking grant-backed artifacts. Consumer-side import and binding are not claimed by this component.'
    },

    publishStatus: {
      notPublished: 'Not published. This Room capability will not appear as an MCP provider in selectable provider lists.',
      publishedWithNameSummary: 'Published. Display name: {name}. Summary: {summary}',
      publishedWithName: 'Published. Display name: {name}. Summary is not set.',
      publishedWithSummary: 'Published. Summary: {summary}',
      publishedDefault: 'Published. Default display metadata is currently used.',
      pendingSaveOrRefresh: 'Enabled, but no formal publication echo is available yet. Save settings and refresh if needed.'
    },

    boundary: {
      sharedOff: 'Shared Auto Reply is currently disabled. Even if the provider is bound, calls should fall back to formal-first behavior instead of exposing owner private scope.',
      sharedOn: 'The shared boundary is fixed to the room-configured shared capability. reply_mode={replyMode}. owner ambient private workspace / fs / memory is not included.'
    },

    shareRefPreview: {
      providerDisabled: 'Not generated. Enable Room MCP publish first.',
      notGenerated: 'Not generated. After saving, the owner can generate a copyable artifact / share ref.'
    },

    shareRefStatus: {
      loading: 'Generating or refreshing artifact.',
      readyWithCode: 'Ready. Status: {code}',
      ready: 'Ready. It can be copied and imported by the consumer side.',
      notGenerated: 'Not generated. This panel only shows the owner-side artifact entry and does not claim consumer paste flow completion.'
    },

    shareRefBoundary: {
      generatedHint: 'source room remains the single source of truth; reply_mode={replyMode}; shared_room_config={sharedEnabled}; shared_supervisor={supervisorEnabled}; owner_private_scope_exposed=false'
    },

    actions: {
      generateArtifact: {
        title: 'Generate / refresh artifact',
        description: 'Recommended after saving room settings. Trial generation before saving is allowed, but the backend should still decide from the source Room fact state.',
        buttonGenerate: 'Generate artifact',
        buttonRefresh: 'Refresh artifact',
        generating: 'Generating…'
      },
      copyArtifact: {
        title: 'Copy artifact / share ref',
        description: 'Copy it for the consumer side to paste and import. Copying itself does not complete authorization; server validation remains authoritative.',
        copy: 'Copy artifact',
        copied: 'Copied'
      },
      refreshGrants: {
        title: 'Refresh grant list',
        description: 'Reload grant states issued by the current source Room to verify active / revoked / expired results.',
        refresh: 'Refresh grants',
        refreshing: 'Refreshing…'
      },
      revokeGrant: {
        revoke: 'Revoke grant',
        revoking: 'Revoking…',
        unavailable: 'Not revocable'
      }
    },

    grant: {
      untitled: 'Unnamed grant'
    },

    values: {
      none: 'None',
      unknown: 'unknown',
      unspecified: 'Unspecified'
    },

    notices: {
      providerDisabled: 'Room MCP publish is not enabled yet. When the publish switch is off, consumable room MCP artifacts / share refs should not be issued externally.',
      sharedAutoReplyDisabled: 'Shared Auto Reply is still disabled. Even if an artifact is generated, the consumer side should continue to formal-first behavior and may receive no-auto-reply / manual semantics.',
      artifactReady: 'The current artifact only represents the shared capability published by the source Room. The consumer receives consumption rights, not edit rights to source Room settings or internal observation rights.',
      noGrants: 'No grant records yet. Save settings, generate an artifact, then refresh the grant list.',
      providerEnabledSharedOff: 'Room MCP publish is enabled, but Shared Auto Reply is still disabled. After saving, the provider may be visible, but the actual call chain should still fall back to formal-first and may return no-auto-reply / manual semantics.',
      providerEnabledSharedOn: 'The current publish boundary is the room-configured shared capability. Members, federated members, and granted consumers receive consumption rights, not settings rights.'
    }
  },

  settingsWorkspaceCard: {
    workspaceContext: {
      title: 'workspace_context',
      description: 'Select the workspace by clicking. The UI shows the user-defined workspace name, while the saved value remains the corresponding workspace_id. focus_root and focus_label follow the selected workspace snapshot automatically and no longer need manual input.'
    },

    fields: {
      workspace: {
        label: 'workspace',
        unboundOption: 'Do not bind a workspace',
        hint: 'The UI currently shows the workspace name to the user, but saving still writes the formal binding value workspace_id.'
      },
      workspaceId: {
        label: 'workspace_id'
      },
      workspaceName: {
        label: 'workspace_name'
      },
      focusRoot: {
        label: 'focus_root',
        unbound: 'No workspace is bound yet, or the selected workspace does not have a focused directory snapshot yet.',
        hint: 'The snapshot of the selected workspace is read automatically, using saved.focused_root_path first and falling back to current.focused_root_path when it is unavailable.'
      },
      focusLabel: {
        label: 'focus_label',
        unbound: 'Generated automatically from workspace / focus_root'
      }
    },

    actions: {
      applyToSidebarPreview: 'Apply to the left sidebar (preview only)',
      clearFocusRootOnly: 'Clear focus root',
      clearWorkspaceContextAll: 'Clear workspace_context',
      refreshSkills: 'Refresh skills'
    },

    loading: {
      workspaceOptions: 'Loading the workspace list and snapshot...',
      supervisorSkills: 'Reading workspace-bound supervisor skills...',
      refresh: 'Refreshing...'
    },

    supervisorSkills: {
      title: 'supervisor_skills',
      description: 'This controls which workspace-bound supervisor skills are enabled for the current Room. saved means the value already stored in backend Room state; local means the current checked value inside this modal.',
      noRoomId: 'There is no room_id yet, so skills discovery cannot be tested.',
      noWorkspace: 'Bind a workspace first, then test skills directory discovery.',
      noFocusRoot: 'The current workspace does not have a focus_root yet, so skills directory discovery cannot be tested for now.',
      empty: 'Discovery has completed, but the current skills directory is empty or has not been created yet.'
    },

    stats: {
      enabledCount: 'enabled_count',
      itemsCount: 'items_count',
      skillsRoot: 'skills_root'
    },

    skillCard: {
      untitled: 'untitled',
      saved: 'saved={value}',
      local: 'local={value}',
      meta: 'skill_id={skillId}; size={size}; updated_at={updatedAt}'
    },

    common: {
      unbound: 'Unbound',
      dash: '—',
      trueValue: 'true',
      falseValue: 'false'
    }
  },

  settingsForm: {
    defaults: {
      newRoomTitle: 'New Room',
      roleFallback: 'role'
    },

    workspace: {
      currentBoundDisplayName: '{name} (current binding)'
    },

    errors: {
      actionFailed: 'Operation failed',
      permissionDenied: 'The current account cannot save room settings.',
      noRoomIdForSupervisorSkills: 'There is no room_id, so supervisor skills cannot be loaded.',
      bindWorkspaceFirst: 'Bind a workspace first.',
      noFocusRootForSupervisorSkills: 'The current workspace does not have a focus_root yet.',
      loadSupervisorSkillsFailed: 'Failed to load supervisor skills',
      loadWorkspaceListFailed: 'Failed to load the workspace list',
      loadWorkspaceSnapshotFailed: 'Failed to load the workspace snapshot'
    },

    summaries: {
      manualWithSupervisor: 'Current mode is manual conversation: ordinary user messages are only recorded in the room and do not automatically trigger a worker / Supervisor. Supervisor capability is still retained, so you can switch back to supervisor or supervisor_direct at any time.',
      manual: 'Current mode is manual conversation: ordinary user messages are only recorded in the room and do not automatically trigger a worker / Supervisor. This is suitable for direct multi-user conversation.',
      supervisorDirect: 'Current mode is Supervisor direct reply: ordinary user messages are answered directly by Supervisor without multi-role delegation; provider={provider}, model={model}, strategy={strategy}.',
      supervisor: 'Current mode is Supervisor orchestration: ordinary user messages enter the room orchestration chain and coordinate active_roles; provider={provider}, model={model}, strategy={strategy}.',
      directRoleWithRole: 'Current mode is default-role direct reply: “{role}” replies first; if no explicit role is hit and the default role is unavailable, execution falls back to the existing room runtime chain.',
      directRoleWithoutRole: 'Current mode is default-role direct reply, but no default role is selected yet, so ordinary messages cannot hit the default direct-reply role.',
      unknown: 'The current runtime mode is unrecognized and has been treated as manual conversation.',
      workerConcurrencySuffix: 'Worker concurrency: {value}.'
    },

    toasts: {
      settingsSaved: 'Room settings saved',
      saveFailed: 'Save failed: {message}',
      unknownError: 'Unknown error'
    }
  },

  roleNotebookPanel: {
    title: 'Role notebook',
    warningNoWorkspace: 'The current room has not resolved a workspace_id yet, so notebook writing is unavailable for now.',

    fields: {
      title: {
        label: 'title'
      },
      sectionTitle: {
        label: 'section_title',
        placeholder: 'For example: latest / weekly_review'
      },
      filename: {
        label: 'filename'
      },
      notebookDir: {
        label: 'notebook_dir',
        placeholder: '_room_notebooks'
      },
      summaryMd: {
        label: 'summary_md',
        placeholder: 'Enter the markdown content to write into this role notebook'
      }
    },

    actions: {
      fillTemplate: 'Fill role summary template',
      submit: 'Write notebook',
      submitting: 'Writing...'
    }
  },

  workspaceDrawer: {
    common: {
      unbound: 'Unbound',
      dash: '—',
      rootDir: 'Root directory',
      rootDirBracketed: '(Root directory)'
    },

    header: {
      eyebrow: 'ROOM WORKBENCH',
      title: 'Room workbench',
      description: 'The left sidebar continues to own the global file space. This drawer only carries room-scoped suggested entries, quick actions, recent locations, and files related to the current room.',
      chips: {
        workspace: 'workspace: {value}',
        focus: 'focus: {value}',
        ready: 'Workbench ready',
        notReady: 'Workspace not bound'
      }
    },

    actions: {
      refresh: 'Refresh',
      refreshing: 'Refreshing...',
      close: 'Close',
      closeSymbol: '×'
    },

    snapshot: {
      title: 'Workbench snapshot',
      subtitle: 'Displays the resolved workspace / focus_root binding, suggested entry points, and actionable state for the current room.',
      meta: {
        workspaceId: 'workspace_id',
        workspaceName: 'workspace_name',
        focusRoot: 'focus_root',
        scope: 'scope',
        topLevelDirectories: 'Top-level directories',
        topLevelFiles: 'Top-level files'
      },
      values: {
        scopeReady: 'Ready',
        scopeNotReady: 'Not ready'
      },
      suggested: {
        roomNote: 'room_note',
        agentNotebook: 'agent_notebook'
      }
    },

    content: {
      title: 'Workbench content',
      subtitle: 'The left side provides quick-save and suggested actions, while the right side provides room-related file browsing and location.'
    },

    footer: {
      dirty: 'There is unsaved content in the current workbench; closing will ask for confirmation again.',
      ready: 'The workbench is bound to the current room workspace / focus_root. Refresh will sync the latest snapshot and file location.',
      notReady: 'The current room has not bound a workspace_id yet, so the workbench only shows read-only placeholder information.'
    },

    messages: {
      operationFailed: 'Operation failed',
      noWorkspaceId: 'There is no available workspace_id for the current room.',
      refreshed: 'Workbench refreshed',
      refreshFailed: 'Refresh failed',
      located: 'Located: {path}',
      locatedTo: 'Located to: {path}',
      closeConfirm: 'The current file has not been saved yet. Close anyway?'
    }
  },

  settingsRolesCard: {
    title: 'Active roles',
    subtitle: 'You no longer need to type comma-separated role_id values manually. Just check the roles you want.',
    summary: 'Currently activated {active} / {total} roles.',

    actions: {
      selectAll: 'Select all',
      clear: 'Clear',
      keepOnlyDefault: 'Keep only the default role',
      setDefault: 'Set as default',
      defaultCurrent: 'Default'
    },

    empty: 'There are no roles in the current room yet. Please create roles in the “Roles” drawer first.',

    tags: {
      defaultReply: 'Default reply',
      active: 'Active',
      disabled: 'Role disabled'
    },

    role: {
      fallbackName: 'role',
      emptyPrompt: 'No system_prompt has been filled in yet'
    }
  },

  workspaceExplorer: {
    common: {
      rootDir: 'Root directory',
      dash: '—',
      path: 'path'
    },

    header: {
      title: 'Room entry index',
      subtitle: 'This panel only collects suggested entries, recent locations, and manual relative-path jumps for the current Room. Full file browsing remains in the left sidebar.',
      badges: {
        workspaceReady: 'Workspace bound',
        workspaceNotReady: 'Workspace not bound'
      }
    },

    sections: {
      recommended: 'Recommended entries',
      manualOpen: 'Open relative path manually',
      recent: 'Recent locations',
      context: 'Room context'
    },

    actions: {
      open: 'Open'
    },

    manual: {
      placeholder: 'Enter a relative path, for example notes/room.md',
      helper: 'Use this to jump quickly to a relative path in the current room workspace. To browse all files, use the left sidebar file space.'
    },

    empty: {
      noWorkspace: 'The current room has not bound a workspace yet, so the room entry index cannot be generated.',
      noRecommended: 'There are currently no recommended entries in this snapshot.',
      noRecent: 'There are no recent location records yet.'
    },

    facts: {
      workspaceId: 'workspace_id',
      focusRoot: 'focus_root',
      entryCount: 'Current entry count',
      recentCount: 'Recent location count'
    },

    recentLabels: {
      manual: 'manual',
      event: 'event',
      recent: 'recent'
    },

    messages: {
      emptyPath: 'The relative path is empty and cannot be opened.',
      opening: 'Opening: {path}',
      located: 'Located: {path}'
    }
  },

  rolesDrawer: {
    title: 'Room roles',
    description: 'Manage roles, prompts, knowledge bindings, MCP providers, and role notebooks.',

    actions: {
      workspace: 'Workspace',
      openWorkspace: 'Open workspace',
      refreshStatus: 'Refresh status',
      refreshStatusTitle: 'Only refresh the provider capability catalog and availability state without triggering execution.',
      refresh: 'Refresh',
      close: 'Close',
      createRole: 'Create role',
      creating: 'Submitting...',
      reset: 'Reset',
      notebook: 'Notebook',
      collapseNotebook: 'Collapse notebook',
      edit: 'Edit',
      delete: 'Delete',
      save: 'Save',
      cancel: 'Cancel',
      useForCreate: 'Use for new role',
      selectedForCreate: 'Selected for new role'
    },

    sections: {
      currentWorkspace: 'Current workspace',
      providerCatalog: 'Provider capability catalog',
      createRole: 'Create role',
      existingRoles: 'Existing roles'
    },

    workspaceFields: {
      workspaceId: 'workspace_id',
      workspaceName: 'workspace_name',
      focusRoot: 'focus_root',
      focusLabel: 'focus_label',
      rootDirectory: '(root directory)'
    },

    providerSummary: {
      total: '{count} providers',
      available: '{count} available',
      unavailable: '{count} unavailable',
      authRequired: '{count} auth required',
      authMissing: '{count} auth missing'
    },

    providerCatalog: {
      readonlyHint: 'This is a read-only capability catalog. It shows the provider label, availability, auth type, auth status, and boundary capabilities; “Use for new role” only writes into the form and does not define backend execution semantics.',
      empty: 'No providers yet.',
      available: 'Available',
      unavailable: 'Unavailable',
      authReady: 'Auth ready',
      authMissing: 'Auth missing',
      supportsWorkspace: 'workspace',
      supportsFocusRoot: 'focus_root',
      unavailableDefault: 'This provider is currently unavailable.',
      loadedDefault: 'Provider metadata loaded.',
      authTypes: {
        serviceManaged: 'Service-managed auth',
        apiKey: 'API Key',
        oauth2: 'OAuth2',
        none: 'No auth required',
        unknown: 'Auth status unknown'
      }
    },

    providerSection: {
      workspace: {
        subtitle: 'This binding decides which workspace and focus root a Room role can use when it writes notebooks, resolves files, or calls workspace-aware providers.'
      },

      catalog: {
        subtitle: 'Choose from local registry providers, imported remote providers, and granted-visible Room MCP capabilities.'
      },

      summary: {
        localRegistry: 'Local registry {count}',
        pasteImported: 'Paste imported {count}',
        grantedVisible: 'Granted visible {count}',
        finalOnly: 'Final only {count}'
      },

      import: {
        title: 'Paste remote Room MCP share',
        subtitle: 'Paste a share ref or provider descriptor generated by the owner side. After import, it becomes an imported provider in the catalog below and reuses the existing create / edit / save role binding flow.',
        placeholder: 'Paste a share ref or provider descriptor JSON here',
        helper: 'In the minimum closed-loop stage, an imported provider does not need to appear in the default registry list. As long as the share ref can be parsed into a stable snapshot, it should enter the role binding save flow. If the provider comes from granted-visible access, the consumer receives consumption permission, not observation access to the source Room execution process.',
        importedProviderFallback: 'Imported remote provider.'
      },

      actions: {
        importing: 'Importing...',
        importShareRef: 'Import share ref',
        clearInput: 'Clear input',
        clearImportedProviders: 'Clear imported providers',
        useForCreateShort: 'Use for create',
        remove: 'Remove'
      },

      badges: {
        roomMcp: 'Room MCP',
        importedRemote: 'Imported remote',
        grantedVisible: 'Granted visible',
        roomVisible: 'Room visible',
        finalOnly: 'Final only',
        noSourceObserve: 'No source observe'
      },

      grantStates: {
        active: 'Grant active',
        revoked: 'Grant revoked',
        expired: 'Grant expired',
        unknown: 'Grant {state}'
      }
    },

    createRole: {
      hint: 'Slug can be left empty and generated automatically; if it duplicates an existing role, the backend will append a -2 / -3 suffix automatically.'
    },

    existingRoles: {
      empty: 'No roles yet',
      editHint: 'If the slug duplicates another role during editing, the backend will also append a suffix automatically to avoid a direct error.'
    },

    roleSummary: {
      prompt: 'Prompt',
      binding: 'Binding',
      time: 'Time',
      tools: 'Tools',
      mcp: 'MCP'
    },

    footer: {
      editing: 'You are editing the role configuration. After saving, the room role information will be refreshed.',
      notebook: 'You are working on the role notebook. Writing to the workspace notebook does not change the formal Room protocol.',
      default: 'Manage roles, knowledge bindings, and provider configuration here. It does not change Room’s formal external fields.'
    },

    binding: {
      library: 'library',
      group: 'group',
      doc: 'doc',
      store: 'store',
      evidence: 'evidence'
    },

    toolLabels: {
      rag: 'RAG',
      web: 'Web',
      code: 'Code',
      fsRead: 'FS Read',
      fsWrite: 'FS Write',
      mcp: 'MCP'
    },

    mcpSummary: {
      onNoProvider: 'on · No provider selected',
      tool: 'tool={tool}',
      inheritWorkspace: 'Inherit workspace',
      inheritFocusRoot: 'Inherit focus_root',
      currentUnavailable: 'Currently unavailable'
    },

    notebook: {
      defaultTitle: '{name} notebook',
      template: {
        headingRole: '## {name}',
        roleId: '- role_id: {value}',
        slug: '- slug: {value}',
        enabled: '- enabled: {value}',
        systemPrompt: '### System Prompt',
        knowledgeBinding: '### Knowledge Binding',
        tools: '### Tools',
        mcp: '### MCP'
      }
    },

    messages: {
      providerSelected: 'Provider selected: {provider}',
      loadProviderRegistryFailed: 'Failed to load provider catalog',
      refreshRolesFailed: 'Failed to refresh roles',
      createRoleFailed: 'Failed to create role',
      roleCreated: 'Role created: {name}',
      roleCreatedWithSlug: "Role created: {name} ({'@'}{slug})",
      updateRoleFailed: 'Failed to update role',
      roleUpdated: 'Role updated: {name}',
      roleUpdatedWithSlug: "Role updated: {name} ({'@'}{slug})",
      deleteConfirm: 'Delete role: {name}?',
      deleteRoleFailed: 'Failed to delete role',
      roleDeleted: 'Role deleted: {name}',
      notebookMissingWorkspace: 'workspace_id is missing, so the notebook cannot be written.',
      notebookEmptySummary: 'summary_md cannot be empty.',
      notebookWriteFailed: 'Write failed',
      notebookWriteSuccess: 'Write succeeded: {path}'
    },

    common: {
      dash: '—',
      none: 'none',
      off: 'off',
      role: 'role',
      noProviderSelected: 'No provider selected',
      trueValue: 'true',
      falseValue: 'false'
    }
  },

  roleFormFields: {
    fields: {
      name: {
        label: 'Name',
        placeholder: 'For example: psychologist / strategy_agent'
      },
      slug: {
        label: 'slug',
        placeholder: 'Leave empty to generate automatically'
      },
      avatar: {
        label: 'Avatar',
        placeholder: '🤖'
      },
      enabled: {
        label: 'Enabled'
      },
      systemPrompt: {
        label: 'system_prompt',
        placeholder: 'Enter the role prompt'
      },
      libraryId: {
        label: 'library_id',
        placeholder: 'Optional'
      },
      groupId: {
        label: 'group_id',
        placeholder: 'Optional'
      },
      docId: {
        label: 'doc_id',
        placeholder: 'Optional'
      },
      storeScope: {
        label: 'store_scope'
      },
      evidenceScope: {
        label: 'evidence_scope'
      }
    },

    scopeOptions: {
      doc: 'doc',
      library: 'library',
      global: 'global'
    },

    time: {
      title: 'RAG time range',
      hintBefore: 'Reuse the Chat interaction style, but the formal Room role payload still only sends ',
      hintMiddle: ' or ',
      hintAfter: '.',
      modeDays: 'Last N days',
      modeRange: 'Relative / absolute range',
      clear: 'Clear',
      quick: 'Quick',
      shortcutDays: '{count}d',
      timeFilterDays: 'time_filter_days',
      timeFilterDaysPlaceholder: 'For example: 7 / 30',
      descriptionLabel: 'Description',
      daysReadonlyBefore: 'Days mode clears ',
      daysReadonlyMiddle: ' / ',
      daysReadonlyAfter: '.',
      relativeQuick: 'Relative range presets',
      relativePreset: '{older} ~ {newer} days ago',
      olderDaysAgoLabel: 'olderDaysAgo (older)',
      olderDaysAgoPlaceholder: 'For example: 30',
      newerDaysAgoLabel: 'newerDaysAgo (newer)',
      newerDaysAgoPlaceholder: 'For example: 21',
      timeStart: 'time_start',
      timeStartPlaceholder: 'For example: 2026-03-01T00:00:00Z',
      timeEnd: 'time_end',
      timeEndPlaceholder: 'For example: 2026-04-01T00:00:00Z',
      currentRangeDays: 'Current range: last {count} days.',
      currentRangeInterval: 'Current interval: {start} ~ {end}',
      currentRangeEmpty: 'No document time range is currently set.',
      effectiveHint: 'The Room form only expresses the intent; on submit the formal payload still maps to time_filter_days / time_start / time_end.'
    },

    toolPolicy: {
      labels: {
        rag: 'RAG',
        web: 'Web',
        mcp: 'MCP',
        code: 'Code',
        fsRead: 'FS Read',
        fsWrite: 'FS Write'
      },
      pendingBadge: 'Planned',
      pendingTitle: 'This feature is under development and cannot be enabled yet.',
      pendingNotice: '{feature} is under development and has been automatically disabled.'
    },

    provider: {
      title: 'MCP capability',
      description: 'Enable mcp first, then choose a provider for the role. Parameters, boundaries, and advanced options change automatically based on provider metadata.',
      stateOn: 'Enabled',
      stateOff: 'Disabled',
      providerLabel: 'Provider',
      providerPlaceholder: 'Please choose a provider',
      toolLabel: 'Capability',
      selectedDefault: 'Provider selected.',
      available: 'Available',
      unavailable: 'Unavailable',
      authReady: 'Auth ready',
      authMissing: 'Auth missing',
      authNone: 'No auth required',
      unavailableDefault: 'This provider is currently unavailable.',
      boundaryTitle: 'Boundary inheritance',
      boundaryDefault: 'workspace / focus_root inheritance must remain user-controlled. Only explicit switches are submitted here and no backend execution semantics are defined.',
      inheritWorkspace: 'Inherit workspace context',
      inheritFocusRoot: 'Inherit focus_root',
      typeRoomProvider: 'Room provider',
      typePresetProvider: 'Preset provider',
      importedRemote: 'Imported remote',
      snapshotFallback: 'Snapshot fallback',
      originValue: 'origin: {value}',
      sourceRoomValue: 'source room: {value}',
      sharedAutoReplyValue: 'shared auto reply: {state}',
      ownerPrivateScopeValue: 'owner private scope: {state}',
      unknown: 'unknown',
      on: 'on',
      off: 'off',
      exposed: 'exposed',
      closed: 'closed',
      present: 'present',
      roomProviderSummaryTitle: 'Room provider summary',
      roomProviderConsumerBoundaryHint: 'The selected provider is a Room provider. Execution boundaries are decided by the source Room saved shared capability; the consumer workspace / focus should not expand authority here.',
      importedSnapshotHint: 'The selected provider comes from an imported snapshot. Reopen echo should prefer the snapshot instead of requiring the provider to still be enumerable in the registry.',
      advancedSharedBoundaryOnly: 'room-configured shared capability only; owner ambient private scope should remain closed.',
      snapshotFallbackActive: 'reopen fallback active',
      snapshotCatalogBacked: 'catalog backed',
      pendingBadge: 'Planned',
      pendingBoundaryTitle: 'This feature is under development and cannot be enabled yet.',
      pendingBoundaryNotice: '{feature} is under development and has been automatically disabled.',
      workspaceIdValue: 'workspace_id: {value}',
      focusRootValue: 'focus_root: {value}',
      rootDirectory: '(root directory)',
      advanced: 'Advanced settings',
      advancedLabels: {
        providerId: 'provider_id',
        providerType: 'provider_type',
        toolName: 'tool_name',
        sourceRoom: 'source room',
        sharedBoundary: 'shared boundary'
      }
    },

    common: {
      dash: '—',
      ellipsis: '...'
    }
  },

  workspaceQuickSaveCard: {
    header: {
      title: 'Quick actions',
      subtitle: 'This area does not duplicate the general browsing capabilities of the left sidebar. It only provides lightweight room-related entry points and context helpers.',
      ready: 'READY',
      unbound: 'UNBOUND'
    },

    empty: {
      noWorkspace: 'No workspace is currently bound. Please choose workspace_context in room settings first.'
    },

    sections: {
      recommendedActions: 'Suggested entries',
      recommendedPaths: 'Suggested paths',
      draft: 'Room context draft',
      roomInfo: 'Room info'
    },

    actions: {
      openRoomNote: 'Open room_note',
      openAgentNotebook: 'Open agent_notebook',
      copyFocusRoot: 'Copy focus_root',
      copyWorkspaceId: 'Copy workspace_id',
      copyDraft: 'Copy draft',
      openRoomNotePaste: 'Open room_note and paste manually',
      clear: 'Clear'
    },

    fields: {
      draftPlaceholder: 'Temporarily store a room summary, TODOs, or path notes here; copy it first, then paste it into the center notes panel.'
    },

    paths: {
      roomNote: 'room_note',
      agentNotebook: 'agent_notebook',
      focusRoot: 'focus_root'
    },

    facts: {
      roomId: 'room_id',
      defaultAgent: 'default_agent',
      activeRoles: 'active_roles',
      replyMode: 'reply_mode'
    },

    replyModes: {
      manual: 'manual',
      directRole: 'direct_role',
      supervisorDirect: 'supervisor_direct',
      supervisor: 'supervisor'
    },

    pathLabels: {
      roomNote: 'room_note',
      agentNotebook: 'agent_notebook',
      path: 'path'
    },

    status: {
      copied: 'Copied',
      copiedFocusRoot: 'Copied focus_root',
      copiedWorkspaceId: 'Copied workspace_id',
      copiedDraft: 'Copied room context draft',
      noContent: 'There is no content to copy.',
      copyFailed: 'Copy failed. Please check browser permissions.',
      pathEmpty: 'The path is empty and cannot be opened.',
      draftCleared: 'Draft cleared.',
      savedPathMessage: 'Located {label}: {path}'
    },

    common: {
      dash: '—',
      defaultAgentFallback: 'agent'
    }
  }
}
