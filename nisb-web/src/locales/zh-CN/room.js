export default {
  header: {
    fallbackTitle: '房间',

    actions: {
      exitRoom: '退出房间',
      workspace: '工作区',
      workspaceShort: '空间',
      refresh: '刷新',
      roles: '角色',
      settings: '设置',
      menu: '菜单'
    },

    stats: {
      users: '用户',
      roles: '角色',
      active: '激活',
      usersCount: '用户 {count}',
      rolesCount: '角色 {count}',
      activeCount: '激活 {count}',
      running: '运行中',
      inheritWorkspaceContext: '继承上下文',
      inheritFocusRoot: '继承焦点'
    },

    badges: {
      room: 'ROOM',
      roomCompact: 'R',
      supervisor: 'SUPERVISOR',
      supervisorCompact: 'SUP'
    },

    bindings: {
      openWorkspace: '打开工作区',
      workspace: '工作空间',
      workspaceShort: '空间',
      focus: '聚焦目录',
      focusShort: '聚焦',
      focusTitleWorkspaceAndRoot: '进入工作空间并恢复文件快照：{workspace} · {root}',
      focusTitleWorkspace: '进入工作空间并恢复文件快照：{workspace}',
      focusTitleRoot: '跳转到左侧栏聚焦目录：{root}',
      focusTitleFallback: '进入工作空间或跳转到聚焦目录'
    },

    plan: {
      latest: '最新计划',
      short: '计划'
    },

    messages: {
      workspaceNotBound: '当前 room 尚未绑定 workspace_id，请先到房间设置中保存 workspace_context。',
      noWorkspaceOrFocus: '当前 room 没有可用的 workspace 或 focus_root。',
      openingWorkspaceWithState: '正在打开工作空间并恢复文件状态：{workspace}',
      openingFocusRoot: '正在展开左侧栏并跳转到聚焦目录：{root}',
      restoringWorkspaceState: '正在恢复工作空间文件状态：{workspace}',
      jumpedToFocusRoot: '已跳转到聚焦目录：{root}'
    }
  },

  settingsModal: {
    title: '房间设置',
    kicker: 'Room 控制台',
    description: '显式配置标题、摘要、Supervisor、默认回复角色、激活角色，以及 room 绑定的 workspace / focus_root。当前也可在编排设置中使用最小 P6 测试控制面，稳定构造 supervisor / worker / skill 的 notebook probe 场景。',

    actions: {
      close: '关闭',
      cancel: '取消',
      save: '保存',
      saving: '保存中...'
    },

    common: {
      defaultProvider: 'openai',
      systemDefault: '系统默认',
      on: 'on',
      off: 'off'
    },

    footer: {
      readonlyFederation: '当前为只读视图：非房主不能保存房间设置，也不能发出 federation invite。',
      p6Supervisor: '当前测试入口：supervisor probe。保存后可更稳定核对 success path 终态与 supervisor notebook allowed path。',
      p6Worker: '当前测试入口：worker probe。保存后可更稳定核对 worker notebook write deny。',
      p6Skill: '当前测试入口：skill probe。保存后可更稳定核对 skill notebook write deny。',
      supervisorMode: '保存后优先使用 Supervisor 编排；provider={provider}，model={model}，fs_read={fsRead}，notebook={notebook}。',
      defaultRole: '保存后默认回复角色：{role}',
      fallback: '保存后将按 active_roles / supervisor_enabled 执行。'
    }
  },

  externalMcpPublish: {
    defaultClientLabel: '外部 MCP 客户端',

    loadStatusFailed: '加载外部 MCP 发布状态失败',

    missingRoomIdEnable: '缺少 room_id，无法启用外部 MCP 发布',
    enableFailed: '启用外部 MCP 发布失败',
    enableSuccess: '外部 MCP 发布已启用；token 只会显示一次。',

    missingRoomIdRevoke: '缺少 room_id，无法撤销外部 MCP 发布',
    revokeFailed: '撤销外部 MCP 发布失败',
    revokeSuccess: '外部 MCP 发布已撤销。',

    missingRoomIdRegenerate: '缺少 room_id，无法重新生成 token',
    regenerateFailed: '重新生成外部 MCP token 失败',
    regenerateSuccess: '新的外部 MCP token 已生成；旧 token 应立即失效。',

    noConfigToCopy: '当前没有可复制的 MCP 配置',
    clipboardUnsupported: '当前环境不支持复制到剪贴板',
    copyLibrechatSuccess: 'MCP 客户端配置已复制。',
    copyGenericSuccess: '通用 MCP 配置已复制。',
    copyConfigFailed: '复制 MCP 配置失败',

    noPlaintextTokenToCopy: '当前没有可复制的明文 token；刷新后 token 不会再次显示。',
    copyTokenSuccess: '外部 MCP token 已复制。',
    copyTokenFailed: '复制 token 失败'
  },

  chatRuntime: {
    stream: {
      toolCall: '正在调用工具...',
      toolResult: '工具已返回，正在组织答案...',
      final: '正在完成输出...',
      meta: '正在准备请求...',
      roomRuntime: 'Room 正在运行...',
      default: '正在流式响应...'
    },

    status: {
      pauseRequested: '已请求暂停',
      waitingCheckpoint: '等待 checkpoint',
      interrupted: '已中断',
      resumed: '已恢复',
      completedAfterResume: '恢复后已完成',
      completed: '已完成',
      budgetExhausted: '预算已耗尽',
      roomRuntimeActive: 'room runtime active',
      roomRuntimeDetached: 'room runtime detached',
      roomRuntimeIdle: 'room runtime idle',
      aborted: '已停止',
      error: '错误'
    },

    control: {
      pauseRequested: '已请求暂停，正在等待安全 checkpoint。',
      waitingCheckpoint: '当前正在等待安全 checkpoint，暂不接受新问题。',
      resumeReady: '当前运行已中断，请先从 checkpoint 恢复。',
      interrupted: '当前运行已中断，暂不接受新问题。',
      running: '当前运行中，暂不接受新问题。',
      budgetExhausted: 'step budget 已耗尽，当前不可继续发送。',
      resumeBlockedError: '当前存在阻断恢复的错误，暂不接受新问题。'
    },

    messages: {
      stopped: '已停止。'
    },

    errors: {
      roomIdMissing: 'room mode 缺少 room_id'
    }
  },
  
  settingsBasicCard: {
    title: '基础设置',
    eyebrow: 'Room identity',
    subtitle: '设置当前 Room 的可见身份、MCP capability 摘要，并在 owner cockpit 中管理 federation 接入。',

    chips: {
      providerOn: 'MCP provider 已开启',
      providerOff: 'MCP provider 未开启',
      sharedOn: 'Shared auto reply 已开启',
      sharedOff: 'Shared auto reply 已关闭',
      federationManageable: 'Federation 可管理',
      federationReadonly: 'Federation 只读'
    },

    sections: {
      identity: {
        title: 'Room profile',
        subtitle: '这些字段决定 Room 在 workspace 面板、摘要和 capability 暴露面中的展示方式。'
      }
    },

    fields: {
      title: {
        label: '标题',
        placeholder: 'Room 标题'
      },
      summary: {
        label: '摘要',
        placeholder: '描述这个 Room 的用途'
      },
      scratchpad: {
        label: 'Scratchpad',
        placeholder: '当前 Room 的私有备注'
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
      title: 'Room MCP 发布摘要',
      hint: '这里展示的是当前 Room 已保存的发布态摘要；发布对象应仅对应 room-configured shared capability。',

      cards: {
        publishStatus: '发布状态',
        providerName: 'Provider 展示名',
        providerSummary: 'Provider 摘要',
        sharedSemantic: '共享语义摘要',
        sharedBoundary: '共享边界摘要'
      },

      values: {
        providerNameUnset: '未设置，保存后使用默认展示名。',
        providerSummaryUnset: '未设置，建议补充 reply_mode、active workers / skills、workspace / focus root 与 shared boundary 摘要。',
        notPublished: '未发布',
        published: '已发布',
        sharedBoundaryEnabled: '已启用 Shared Auto Reply，member / federated member 默认消费 owner 已保存的 room-configured shared reply 语义。',
        sharedBoundaryDisabled: 'Shared Auto Reply 当前关闭，非 owner 默认回到 manual。',
        workspaceUnbound: 'workspace=未绑定',
        focusRootUnset: 'focus_root=未设置',
        boundaryTemplate: '{base} {workspace}；{focus}；不包含 owner ambient private workspace / fs / memory。'
      },

      notices: {
        providerOnSharedOff: '当前已启用 Room MCP 发布，但 Shared Auto Reply 仍关闭；后续 provider 调用链仍应保留 formal-first 结果，而不是隐式放开 shared reply。',
        providerOnSharedOn: '当前发布只应复用 owner 在 room settings 中显式保存的 shared capability，不应自动暴露 private workspace / fs / memory 全域能力。'
      }
    },

    federation: {
      eyebrow: 'Federation',
      title: 'Cross-VPS Federation',
      hint: '仅做 member 接入；当前用于 invite 状态可见、owner user_id 可见与最小回收。',

      state: {
        ownerManage: 'Owner 可管理',
        readonly: '只读',
        invites: 'invites: {count}',
        members: 'members: {count}',
        handler: 'handler: {state}',
        loading: 'loading: {state}'
      },

      issue: {
        title: '签发 federation invite'
      },

      fields: {
        targetPeer: {
          label: 'Target peer',
          emptyOption: '请选择 peer'
        },
        inviteTtl: {
          label: 'Invite TTL'
        }
      },

      ttl: {
        oneDay: '1 天',
        sevenDays: '7 天'
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
        readonly: '当前房间存在 federation 信息，但你不是该房间 owner，不能执行 invite / revoke 等管理动作。'
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
        helperPrefix: '把',
        helperSuffix: '发给远端；远端仍在 FedMenu 里执行 accept。'
      },

      history: {
        title: 'Invite history',
        empty: '暂无 invite。',
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
        loading: 'joined members 加载中...',
        empty: '暂无 joined members。',
        meta: {
          peer: 'peer'
        }
      }
    }
  },

  settingsOrchestrationCard: {
    title: '编排设置',
    eyebrow: 'Room runtime',
    subtitle: '控制当前 Room 的 shared auto reply 授权、MCP capability 暴露、回复路由和 supervisor 执行委派。',

    chips: {
      sharedAutoReplyOn: '共享自动回复已开启',
      sharedAutoReplyOff: '共享自动回复已关闭',
      supervisorOn: 'Supervisor 已开启',
      supervisorOff: 'Supervisor 已关闭',
      workerConcurrency: 'Worker：{value}'
    },

    sections: {
      roomBehavior: {
        title: 'Room 行为',
        subtitle: '定义 joined member / federated member 是否进入房间级自动回答授权语义。'
      },
      mcpCapabilities: {
        title: 'MCP capabilities',
        subtitle: '在同一个 capability 区块中管理 Room MCP 分享、面向 federation 的 grant，以及 external MCP publish。'
      },
      replyRouting: {
        title: '回复路由',
        subtitle: '选择回复保持 manual、交给默认 role，或进入 supervisor runtime。'
      }
    },

    common: {
      emptyOption: '空',
      emptyValue: '—',
      trueValue: 'true',
      falseValue: 'false',
      defaultProvider: 'openai',
      defaultModel: '使用系统默认',
      defaultSkillStrategy: 'builtin_plus_custom',
      defaultStepBudget: '0',
      defaultScope: 'minimal'
    },

    toggles: {
      supervisorEnabled: {
        title: 'supervisor_enabled',
        description: 'Supervisor 能力开关。开启后可配置并使用 Supervisor；是否自动参与回复，仍由 reply_mode 决定。'
      },
      inheritWorkspaceContext: {
        title: 'inherit_workspace_context',
        description: '让房间持续继承 workspace 绑定。'
      },
      inheritFocusRoot: {
        title: 'inherit_focus_root',
        description: '让房间持续继承 focus_root 聚焦目录。'
      },
      applyAfterSave: {
        title: '保存后立即应用到左侧栏',
        description: '保存 room 配置后，马上把 workspace_context 同步到左侧工作区 UI。'
      },

      sharedAutoReply: {
        title: '房间级 Shared Auto Reply',
        description: '开启后，joined member / federated member 才进入房间级自动回答授权语义；关闭时非 owner 默认仅 manual。'
      }
    },

    fields: {
      replyMode: {
        label: 'reply_mode',
        options: {
          manual: 'manual（静默对话）',
          directRole: 'direct_role（默认角色直答）',
          supervisorDirect: 'supervisor_direct（Supervisor 直接回答）',
          supervisor: 'supervisor（多角色编排）'
        }
      },

      orchestrationSummary: {
        label: '当前编排说明'
      },

      workerConcurrency: {
        label: 'Worker 并发数',
        hint: '控制同一轮 Room 中最多同时运行多少个 worker。低配机器选 1 最稳；RAG 较多的房间推荐 2。',
        options: {
          option1: '1 · 最稳',
          option2: '2 · 推荐',
          option3: '3 · 高级',
          option4: '4 · 实验'
        }
      },

      workerConcurrencySummary: {
        label: 'Worker 并发摘要',
        safest: '每次最多 {value} 个 worker。最适合低配 VPS。',
        recommended: '每次最多 {value} 个 worker。推荐用于 RAG 较多的房间。',
        faster: '每次最多 {value} 个 worker。高级选项，适合 API-bound 工作流。',
        experimental: '每次最多 {value} 个 worker。实验选项。'
      },

      defaultReplyRole: {
        label: 'default_reply_role_id',
        emptyOption: '空'
      },

      defaultReplyRoleSummary: {
        label: '当前说明',
        withRole: '默认回复角色：{role}',
        withoutRole: '当前未指定默认回复角色。'
      },

      stepBudget: {
        label: 'Step budget',
        placeholder: '0',
        hint: '限制 Supervisor 单次运行最多推进的步数。预算耗尽时将停在可恢复点。设为 0 表示不限步，具体以后端合同为准。'
      },

      stepBudgetSummary: {
        label: '当前预算说明',
        current: '当前 step budget：{value}。',
        unlimited: '0 表示不限步，具体以后端合同为准。',
        limited: '将限制 Supervisor 单次运行最多推进 {value} 步。'
      },

      supervisorSkillStrategy: {
        label: 'supervisor_skill_strategy',
        hint: '这里只决定 Supervisor prompt 的 skill 组合策略；不会自动改变 worker、filesystem、MCP 或 writeback 权限。',
        options: {
          builtinPlusCustom: 'builtin_plus_custom（内置基线 + Workspace Skills）',
          builtinOnly: 'builtin_only（仅内置基线）',
          customOnly: 'custom_only（仅 Workspace Skills）'
        }
      },

      supervisorProvider: {
        label: 'supervisor_provider'
      },

      supervisorModel: {
        label: 'supervisor_model',
        hint: '当前按统一模型目录选择；若切换 provider，旧 provider 的 model 会自动清空。'
      },

      supervisorTemperature: {
        label: 'supervisor_temperature',
        placeholder: '可空，例如 0.2'
      },

      supervisorMaxTokens: {
        label: 'supervisor_max_tokens',
        placeholder: '可空，例如 4096'
      },

      fsReadScope: {
        label: 'mcp_overrides.fs_read_scope'
      },

      workspaceFocusPreview: {
        label: '当前 workspace / focus_root',
        withFocus: 'workspace={workspace}，focus_root={root}',
        withoutFocus: '当前还没有可用 focus_root；开启 fs_read / notebook_write 后也不会隐式越权。'
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
        hint: '这里只负责稳定构造测试意图；真正是否允许写入，仍以后端正式权限链为准。',
        options: {
          off: 'off（仅保留入口，不注入 probe）',
          supervisor: 'supervisor（验证 allowed path / final success 对齐）',
          worker: 'worker（验证 notebook write deny）',
          skill: 'skill（验证 skill notebook write deny）'
        }
      },

      p6ProbeSummary: {
        label: '当前测试意图'
      }
    },

    helpers: {
      replyModeGuide: '推荐理解方式：manual = 仅用户交流，不自动回复；direct_role = 默认角色直答；supervisor_direct = Supervisor 单体直接回答；supervisor = Supervisor 统筹多角色执行。',
      currentSupervisorState: '当前 strategy：{strategy}，当前 provider：{provider}，当前 model：{model}，当前 step budget：{budget}。',
      defaultRoleSync: '说明：保存时会自动保证 default_reply_role_id 属于 active_roles。'
    },

    supervisorModelSection: {
      title: 'Supervisor 模型',
      subtitle: 'Supervisor 是 room 级 orchestrator / direct-answer runtime，不属于普通角色成员；它的模型与受控能力在这里统一配置。'
    },

    strategyInfo: 'builtin_only 只保留系统内置 supervisor 基线；custom_only 只使用当前 workspace 已启用 skills；builtin_plus_custom 则做稳定基线与 workspace skills 的叠加。',

    supervisorCapabilitySection: {
      title: 'Supervisor 受控能力',
      subtitle: '这里只配置 Supervisor 的 room 级能力；不会给普通角色自动加 fs 或 notebook 权限。'
    },

    supervisorCapabilities: {
      fsReadEnabled: {
        title: 'mcp_overrides.fs_read_enabled',
        description: '允许 Supervisor 在回答前对 room focus_root 做受控只读目录探测。'
      },
      notebookWriteEnabled: {
        title: 'mcp_overrides.notebook_write_enabled',
        description: '允许 Supervisor 把本轮总结写入受控 notebook；写入路径仍受 workspace / focus_root 约束。'
      }
    },

    notebookInfo: 'Supervisor notebook 是 room 级小本本，不是角色小本本；建议只保存“计划、结论、待办、风险”等高层总结。',

    p6TestControlSection: {
      title: 'P6 测试控制面',
      subtitle: '仅用于当前 P6-V1 收尾补证，帮助稳定构造 notebook write allow / deny 场景；不代替正式权限判断。',
      panelEnabled: {
        title: 'p6_test_control.panel_enabled',
        description: '显示最小测试入口。关闭时不会注入任何额外测试 request_args。'
      }
    },

    p6ProbeSummary: {
      disabled: '当前未启用 P6 测试控制面。',
      supervisor: '当前将按 supervisor probe 构造测试，适合验证 success path 终态与 notebook allowed path。',
      worker: '当前将按 worker probe 构造测试，适合稳定复现 worker notebook write deny。',
      skill: '当前将按 skill probe 构造测试，适合稳定复现 skill notebook write deny。',
      off: '当前仅显示测试入口，不注入 notebook probe actor。'
    },

    warnings: {
      strategyInfo: 'builtin_only 只保留系统内置 supervisor 基线；custom_only 只使用当前 workspace 已启用 skills；builtin_plus_custom 则做稳定基线与 workspace skills 的叠加。',
      notebookInfo: 'Supervisor notebook 是 room 级小本本，不是角色小本本；建议只保存“计划、结论、待办、风险”等高层总结。',
      p6TemporaryUse: '建议只在 reply_mode=supervisor 或 supervisor_direct 相关验证时临时开启；验完后把 notebook_probe_actor 切回 off 或直接关闭入口。',
      replyModeManual: "当前 reply_mode=manual。普通用户发言不会自动触发 worker 或 Supervisor；若显式使用 {'@'}角色 或 {'@'}ai，仍可触发单次回复。",
      replyModeSupervisorDirect: '当前 reply_mode=supervisor_direct。普通用户发言会由 Supervisor 单体直接回答，不进入多角色委派；即使保留了 active_roles 或 default_reply_role_id，也不会自动触发它们。',
      replyModeSupervisor: '当前 reply_mode=supervisor。即使设置了 default_reply_role_id，也不会把默认角色当作隐式直答入口；默认角色更多用于配置保留或后续切换。',
      replyModeDirectRole: '当前 reply_mode=direct_role，但你还没有指定 default_reply_role_id；建议先选择一个默认角色，否则普通消息不会命中默认角色直答。'
    },

    audit: {
      fs: {
        title: 'Supervisor FS 审计',
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
        title: 'Supervisor Notebook 审计',
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
    title: 'Room MCP 外部发布',
    subtitle: '将当前 Room 发布为给外部 MCP client 使用的 room-scoped MCP capability。它不是 federation grant，也不是全局 provider catalog。',

    defaults: {
      clientLabel: '外部 MCP client'
    },

    fields: {
      status: '发布状态',
      providerId: 'Provider ID',
      sourceRoomId: 'Source Room ID',
      resultView: 'Result View',
      expiresAt: '有效期至',
      lastUsed: '最近使用',
      usedCount: '使用次数',
      clientLabel: 'Client label',
      expiresInDays: '有效期（天）',
      maxCalls: '最大成功 room 提问次数',
      clientLabelInput: 'Client label',
      endpoint: 'MCP Endpoint'
    },

    config: {
      title: '访问策略',
      subtitle: '启用或重新生成前，设置 token 有效期、成功调用上限、client label 和 endpoint。'
    },

    placeholders: {
      expiresInDays: '例如：30 或 0.0417',
      maxCalls: '留空表示不限，例如：1',
      clientLabel: '例如：团队知识库 / 外部客服助手',
      endpoint: '例如：https://mcp.nisb.me/nisb/mcp'
    },

    hints: {
      expiresInDays: '最短 1 小时，最长 30 天。支持小数天数；0.0417 约等于 1 小时。',
      maxCalls: '只统计成功的 room 提问。连接、工具列表、provider_list 不消耗次数。',
      clientLabel: '仅用于 owner 识别这个外部发布给谁使用。',
      endpoint: '为空时前端会使用当前站点推导 endpoint。生产环境建议使用正式 MCP 域名。'
    },

    states: {
      loading: '加载中',
      active: '已发布',
      revoked: '已撤销',
      expired: '已过期',
      notPublished: '未发布'
    },

    values: {
      none: '暂无',
      neverUsed: '尚未使用'
    },

    token: {
      onceTitle: '明文 token 只会显示这一次',
      onceSubtitle: '请立即复制并保存到外部 client。刷新页面后不会再次显示明文 token。'
    },

    actions: {
      refresh: '刷新状态',
      refreshing: '刷新中…',
      enableTitle: '启用 Room MCP 外部发布',
      enableHelp: '为第三方 MCP client 生成专用 token 和配置。',
      enable: '启用外部发布',
      enabling: '启用中…',
      reenableTitle: '重新启用外部 MCP 发布',
      reenableHelp: '重新启用会生成新的 external_mcp_publish token；旧 token 不应恢复。',
      reenable: '重新启用',
      regenerateTitle: '重新生成 token',
      regenerateHelp: '生成新 token 后，旧 token 应立即失效；新 token 仍只显示一次。',
      regenerate: '重新生成',
      regenerateToken: '重新生成 token',
      regenerating: '生成中…',
      revokeTitle: '撤销外部访问',
      revokeHelp: '撤销后外部 client 使用旧 token 应立即失败，但不影响旧 room MCP / federation 功能。',
      revoke: '撤销',
      revoking: '撤销中…',
      copyLibreChatTitle: '复制 MCP client 配置',
      copyLibreChatTemplateTitle: '复制 MCP client 配置模板',
      copyGenericTitle: '复制通用 MCP 配置',
      copyGenericTemplateTitle: '复制通用 MCP 配置模板',
      copyWithTokenHelp: '当前配置包含刚生成的 token，请保存到外部 client；刷新后不会再次显示 token。',
      copyTemplateHelp: '当前不会包含明文 token；如需完整配置，请重新生成 token。',
      copyGenericHelp: '复制通用 MCP client 可参考的 streamable HTTP 配置。',
      copy: '复制',
      copying: '复制中…',
      copyToken: '复制 token'
    },

    notices: {
      notPublished: '当前 Room 尚未启用外部 MCP 发布；不会生成 external_mcp_publish token，也不会给第三方 client 授权。',
      activeNoToken: '当前 Room 已发布给外部 MCP client；出于安全原因，刷新后不会再次显示明文 token。如需完整带 token 配置，请重新生成 token。',
      expired: '当前外部 MCP 发布已过期；外部 client 应无法继续使用旧 token，请重新生成。',
      revoked: '当前外部 MCP 发布已撤销；外部 client 应无法继续使用旧 token，如需恢复请重新启用。'
    }
  },

  roomMcpPanel: {
    eyebrow: 'Room MCP',
    title: '发布为 MCP Provider',
    subtitle: '将当前 Room settings 中显式保存的 shared capability 发布为可复用 MCP 能力对象；这不等于开放 owner ambient private scope。',

    chips: {
      providerOn: 'Provider 已启用',
      providerOff: 'Provider 未启用',
      sharedOn: 'Shared capability 已开启',
      sharedOff: 'Shared capability 已关闭'
    },

    sections: {
      provider: {
        title: 'Provider 配置',
        subtitle: '定义当前 Room capability 如何展示给其他 worker 和 MCP consumer。'
      },
      publication: {
        title: 'Publication Record',
        subtitle: '这里展示 source Room 当前正式 publication 记录；它是 provider 元数据，不等于 consumer 已自动获得消费权。'
      },
      shareRef: {
        title: 'Grant Artifact / Share Ref',
        subtitle: 'owner 侧生成的是 grant-backed artifact；保留 share ref 交互习惯，但后端语义应视为可验证、可撤销的 artifact descriptor。'
      },
      grants: {
        title: 'Grant 管理',
        subtitle: '查看 owner 当前可见的 grant 列表，核对 active / revoked / expired 状态，并提供撤销入口。'
      }
    },

    toggles: {
      providerEnabled: {
        title: '启用 Room MCP 发布',
        description: '打开后，当前 Room 可作为标准 MCP provider 出现在 provider 列表中，供其他 worker 绑定消费。'
      }
    },

    fields: {
      providerName: {
        label: 'Provider 展示名',
        placeholder: '例如：Room Shared Capability / Release Candidate',
        hint: '用于前端列表与摘要展示；留空时由后端或默认摘要兜底。'
      },
      providerSummary: {
        label: 'Provider 摘要',
        placeholder: '例如：按当前 room settings 执行 shared reply capability',
        hint: '建议描述 reply 语义、启用 workers / skills 与共享边界。'
      },
      publishStatus: {
        label: '当前发布状态'
      },
      boundarySummary: {
        label: '共享边界摘要'
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
        label: 'Artifact / Share Ref 预览',
        hint: '这里展示的是最小可分享 artifact descriptor；它表达的是 room-configured shared capability，不包含 owner private workspace / fs / memory / notebook 全域能力。'
      },
      shareRefStatus: {
        label: '当前授权状态'
      },
      issuedAt: {
        label: '最近生成时间'
      },
      consumerBoundary: {
        label: 'consumer 侧边界提示'
      },
      grantId: {
        label: 'Grant ID'
      },
      artifactId: {
        label: 'Artifact ID'
      },
      grantTotal: {
        label: 'Grant 总数'
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
      providerBoundary: '发布对象只应封装 owner 显式保存到 room settings 的 room-configured shared capability，不应自动暴露 private workspace / private fs / private memory 全域能力。',
      publicationBoundary: 'publication 负责“可发布、可发现、边界是什么”；真正授予外部 consumer 消费权，还需要 grant / artifact。',
      shareRefBoundary: '当前阶段 owner 侧重点是生成、复制、查看、撤销 grant-backed artifact；consumer 侧是否已导入并绑定，不在这个组件内宣称完成。'
    },

    publishStatus: {
      notPublished: '未发布；当前 Room capability 不会作为 MCP provider 出现在可选列表。',
      publishedWithNameSummary: '已发布；展示名：{name}；摘要：{summary}',
      publishedWithName: '已发布；展示名：{name}；摘要待补充。',
      publishedWithSummary: '已发布；摘要：{summary}',
      publishedDefault: '已发布；当前使用默认展示信息。',
      pendingSaveOrRefresh: '已启用但尚未完成正式 publication 回显；建议先保存后刷新。'
    },

    boundary: {
      sharedOff: '当前 Shared Auto Reply 关闭；provider 即使被绑定，调用后也应落回 formal-first，而不是放开 owner private scope。',
      sharedOn: '共享边界固定为 room-configured shared capability；reply_mode={replyMode}；不含 owner ambient private workspace / fs / memory。'
    },

    shareRefPreview: {
      providerDisabled: '尚未生成；需先启用 Room MCP 发布。',
      notGenerated: '尚未生成；保存后可由 owner 生成可复制的 artifact / share ref。'
    },

    shareRefStatus: {
      loading: '正在生成或刷新 artifact。',
      readyWithCode: '已准备好；状态：{code}',
      ready: '已准备好；可复制给 consumer 侧粘贴导入。',
      notGenerated: '未生成；当前仅展示 owner 侧 artifact 入口，不宣称 consumer 粘贴链已完成。'
    },

    shareRefBoundary: {
      generatedHint: 'source room 仍是单一事实源；reply_mode={replyMode}；shared_room_config={sharedEnabled}；shared_supervisor={supervisorEnabled}；owner_private_scope_exposed=false'
    },

    actions: {
      generateArtifact: {
        title: '生成 / 刷新 artifact',
        description: '建议保存 room settings 后再生成；未保存时也允许先试生成，但后端仍应以 source Room 当前事实源裁决。',
        buttonGenerate: '生成 artifact',
        buttonRefresh: '刷新 artifact',
        generating: '生成中…'
      },
      copyArtifact: {
        title: '复制 artifact / share ref',
        description: '复制后可交给 consumer 侧粘贴导入；复制动作本身不等于授权完成，最终仍以服务端校验为准。',
        copy: '复制 artifact',
        copied: '已复制'
      },
      refreshGrants: {
        title: '刷新 grant 列表',
        description: '重新拉取当前 source Room 已发出的 grant 状态，用于核对 active / revoked / expired 结果。',
        refresh: '刷新 grant 列表',
        refreshing: '刷新中…'
      },
      revokeGrant: {
        revoke: '撤销 grant',
        revoking: '撤销中…',
        unavailable: '不可撤销'
      }
    },

    grant: {
      untitled: '未命名 grant'
    },

    values: {
      none: '暂无',
      unknown: 'unknown',
      unspecified: '未指定'
    },

    notices: {
      providerDisabled: '当前尚未启用 Room MCP 发布；在发布开关关闭时，不应对外生成可消费的 Room MCP artifact / share ref。',
      sharedAutoReplyDisabled: '当前 Shared Auto Reply 仍关闭；即使生成了 artifact，consumer 侧绑定后也应继续回到 formal-first，并可能得到 no-auto-reply / manual 语义结果。',
      artifactReady: '当前 artifact 仅表示 source Room 发布的 shared capability；consumer 侧获得的是消费权，不是 source Room settings 的编辑权，也不默认获得内部观察权。',
      noGrants: '当前还没有 grant 记录；你可以先保存 settings，再生成 artifact，随后刷新 grant 列表。',
      providerEnabledSharedOff: '当前已打开 Room MCP 发布，但 Shared Auto Reply 仍关闭；保存后即使 provider 可见，实际调用链也应继续回到 formal-first，并可能得到 no-auto-reply / manual 语义结果。',
      providerEnabledSharedOn: '当前发布将以 room-configured shared capability 为边界；member / federated member / granted consumer 获得的是消费权，不获得设置权。'
    }
  },

  settingsWorkspaceCard: {
    workspaceContext: {
      title: 'workspace_context',
      description: 'workspace 改为点击选择；界面显示用户自定义名称，内部仍保存对应的 workspace_id。focus_root / focus_label 自动跟随所选 workspace 快照，不再手工填写。'
    },

    fields: {
      workspace: {
        label: 'workspace',
        unboundOption: '不绑定 workspace',
        hint: '当前面向用户显示的是 workspace 名称；保存时仍写入正式绑定值 workspace_id。'
      },
      workspaceId: {
        label: 'workspace_id'
      },
      workspaceName: {
        label: 'workspace_name'
      },
      focusRoot: {
        label: 'focus_root',
        unbound: '未绑定 workspace，或该 workspace 尚无聚焦目录快照',
        hint: '自动读取所选 workspace 的快照，优先使用 saved.focused_root_path，没有时回退到 current.focused_root_path。'
      },
      focusLabel: {
        label: 'focus_label',
        unbound: '自动跟随 workspace / focus_root 生成'
      }
    },

    actions: {
      applyToSidebarPreview: '应用到左侧栏（仅预览）',
      clearFocusRootOnly: '清空聚焦 root',
      clearWorkspaceContextAll: '清空 workspace_context',
      refreshSkills: '刷新 skills'
    },

    loading: {
      workspaceOptions: '正在加载 workspace 列表与快照…',
      supervisorSkills: '正在读取 workspace-bound supervisor skills…',
      refresh: '正在刷新…'
    },

    supervisorSkills: {
      title: 'supervisor_skills',
      description: '这里控制当前 Room 启用哪些 workspace-bound supervisor skills。saved 表示后端 Room state 已保存值；local 表示当前弹窗里的本地勾选值。',
      noRoomId: '当前没有 room_id，无法测试 skills 发现。',
      noWorkspace: '请先绑定 workspace，再测试 skills 目录发现。',
      noFocusRoot: '当前 workspace 还没有 focus_root，暂时无法测试 skills 目录发现。',
      empty: '已完成 discover，但当前 skills 目录为空，或目录尚未创建。'
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
      meta: 'skill_id={skillId}；size={size}；updated_at={updatedAt}'
    },

    common: {
      unbound: '未绑定',
      dash: '—',
      trueValue: 'true',
      falseValue: 'false'
    }
  },

  settingsForm: {
    defaults: {
      newRoomTitle: '新房间',
      roleFallback: '角色'
    },

    workspace: {
      currentBoundDisplayName: '{name}（当前绑定）'
    },

    errors: {
      actionFailed: '操作失败',
      permissionDenied: '当前账号无权保存房间设置',
      noRoomIdForSupervisorSkills: '没有 room_id，无法加载 Supervisor skills。',
      bindWorkspaceFirst: '请先绑定 workspace',
      noFocusRootForSupervisorSkills: '当前 workspace 还没有 focus_root',
      loadSupervisorSkillsFailed: '读取 supervisor skills 失败',
      loadWorkspaceListFailed: '加载 workspace 列表失败',
      loadWorkspaceSnapshotFailed: '获取 workspace 快照失败'
    },

    summaries: {
      manualWithSupervisor: '当前为静默对话模式：普通用户发言只记录到房间，不自动触发 worker / Supervisor。Supervisor 能力已保留，可随时切回 supervisor 或 supervisor_direct 模式使用。',
      manual: '当前为静默对话模式：普通用户发言只记录到房间，不自动触发 worker / Supervisor。适合多人直接交流。',
      supervisorDirect: '当前为 Supervisor 直接回答模式：普通用户发言会由 Supervisor 单体直接回复，不进入多角色委派；provider={provider}，model={model}，strategy={strategy}。',
      supervisor: '当前为 Supervisor 编排模式：普通用户发言会进入房间编排链并统筹 active_roles；provider={provider}，model={model}，strategy={strategy}。',
      directRoleWithRole: '当前为默认角色直答模式：优先由“{role}”直接回复；若未命中显式角色且默认角色不可用，再落到现有房间运行链。',
      directRoleWithoutRole: '当前为默认角色直答模式，但还没有指定默认角色；普通消息不会命中默认角色直答。',
      unknown: '当前运行模式未识别，已按静默对话模式处理。',
      workerConcurrencySuffix: 'Worker 并发数：{value}。'
    },

    toasts: {
      settingsSaved: '房间设置已保存',
      saveFailed: '保存失败：{message}',
      unknownError: '未知错误'
    }
  },

  roleNotebookPanel: {
    title: '角色小本本',
    warningNoWorkspace: '当前 room 尚未解析到 workspace_id，暂时不能写入小本本。',

    fields: {
      title: {
        label: 'title'
      },
      sectionTitle: {
        label: 'section_title',
        placeholder: '例如 latest / weekly_review'
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
        placeholder: '请输入要写入该角色小本本的 markdown 内容'
      }
    },

    actions: {
      fillTemplate: '填入角色摘要模板',
      submit: '写入小本本',
      submitting: '写入中...'
    }
  },

  workspaceDrawer: {
    common: {
      unbound: '未绑定',
      dash: '—',
      rootDir: '根目录',
      rootDirBracketed: '（根目录）'
    },

    header: {
      eyebrow: 'ROOM WORKBENCH',
      title: '房间工作台',
      description: '左侧栏继续负责全局文件空间；这里仅承接当前房间的建议入口、快捷动作、最近定位与房间相关文件。',
      chips: {
        workspace: 'workspace：{value}',
        focus: 'focus：{value}',
        ready: '工作台已就绪',
        notReady: '未绑定工作区'
      }
    },

    actions: {
      refresh: '刷新',
      refreshing: '刷新中...',
      close: '关闭',
      closeSymbol: '×'
    },

    snapshot: {
      title: '工作台快照',
      subtitle: '展示当前 room 绑定 workspace / focus_root 的解析结果、建议入口与可操作状态。',
      meta: {
        workspaceId: 'workspace_id',
        workspaceName: 'workspace_name',
        focusRoot: 'focus_root',
        scope: 'scope',
        topLevelDirectories: '顶层目录',
        topLevelFiles: '顶层文件'
      },
      values: {
        scopeReady: '已就绪',
        scopeNotReady: '未就绪'
      },
      suggested: {
        roomNote: 'room_note',
        agentNotebook: 'agent_notebook'
      }
    },

    content: {
      title: '工作台内容',
      subtitle: '左侧是快捷写入与建议动作，右侧是房间相关文件浏览与定位。'
    },

    footer: {
      dirty: '当前工作台内有未保存内容；关闭前会再次确认。',
      ready: '工作台已绑定到当前 room 的 workspace / focus_root，刷新会同步最新快照与文件定位。',
      notReady: '当前 room 尚未绑定 workspace_id，工作台仅显示只读占位信息。'
    },

    messages: {
      operationFailed: '操作失败',
      noWorkspaceId: '当前没有可用的 workspace_id',
      refreshed: '工作台已刷新',
      refreshFailed: '刷新失败',
      located: '已定位：{path}',
      locatedTo: '已定位到：{path}',
      closeConfirm: '当前文件尚未保存，确认关闭吗？'
    }
  },

  workspaceExplorer: {
    common: {
      rootDir: '根目录',
      dash: '—',
      path: 'path'
    },

    header: {
      title: '房间入口索引',
      subtitle: '这里只收纳当前 Room 的建议入口、最近定位和手动相对路径跳转；完整文件浏览继续走左侧栏。',
      badges: {
        workspaceReady: 'workspace 已绑定',
        workspaceNotReady: '未绑定 workspace'
      }
    },

    sections: {
      recommended: '推荐入口',
      manualOpen: '手动相对路径打开',
      recent: '最近定位',
      context: '房间上下文'
    },

    actions: {
      open: '打开'
    },

    manual: {
      placeholder: '输入相对路径，例如 notes/room.md',
      helper: '这里用于快速跳转到当前房间工作区中的相对路径；若要浏览全部文件，请使用左侧栏文件空间。'
    },

    empty: {
      noWorkspace: '当前房间尚未绑定 workspace，无法生成房间入口索引。',
      noRecommended: '当前 snapshot 暂无推荐入口。',
      noRecent: '当前还没有最近定位记录。'
    },

    facts: {
      workspaceId: 'workspace_id',
      focusRoot: 'focus_root',
      entryCount: '当前入口数',
      recentCount: '最近定位数'
    },

    recentLabels: {
      manual: 'manual',
      event: 'event',
      recent: 'recent'
    },

    messages: {
      emptyPath: '相对路径为空，无法打开',
      opening: '正在打开：{path}',
      located: '已定位：{path}'
    }
  },

  settingsRolesCard: {
    title: '激活角色',
    subtitle: '不再手填逗号分隔 role_id，直接勾选即可。',
    summary: '当前已激活 {active} / {total} 个角色。',

    actions: {
      selectAll: '全选',
      clear: '清空',
      keepOnlyDefault: '仅保留默认角色',
      setDefault: '设为默认',
      defaultCurrent: '默认中'
    },

    empty: '当前房间还没有角色，请先到“角色”抽屉中创建角色。',

    tags: {
      defaultReply: '默认回复',
      active: '已激活',
      disabled: '角色已禁用'
    },

    role: {
      fallbackName: 'role',
      emptyPrompt: '未填写 system_prompt'
    }
  },

  rolesDrawer: {
    title: '房间角色',
    description: '管理角色、提示词、知识绑定、MCP provider，以及角色小本本。',

    actions: {
      workspace: '工作区',
      openWorkspace: '打开工作区',
      refreshStatus: '刷新状态',
      refreshStatusTitle: '只刷新 Provider 能力目录与可用性状态，不触发执行。',
      refresh: '刷新',
      close: '关闭',
      createRole: '创建角色',
      creating: '提交中...',
      reset: '重置',
      notebook: '小本本',
      collapseNotebook: '收起小本本',
      edit: '编辑',
      delete: '删除',
      save: '保存',
      cancel: '取消',
      useForCreate: '用于新建角色',
      selectedForCreate: '已用于新建角色'
    },

    sections: {
      currentWorkspace: '当前工作区',
      providerCatalog: 'Provider 能力目录',
      createRole: '新建角色',
      existingRoles: '已有角色'
    },

    workspaceFields: {
      workspaceId: 'workspace_id',
      workspaceName: 'workspace_name',
      focusRoot: 'focus_root',
      focusLabel: 'focus_label',
      rootDirectory: '（根目录）'
    },

    providerSummary: {
      total: '{count} 个 provider',
      available: '{count} 个可用',
      unavailable: '{count} 个不可用',
      authRequired: '{count} 个需鉴权',
      authMissing: '{count} 个缺鉴权'
    },

    providerCatalog: {
      readonlyHint: '这里是只读能力目录。展示 provider 的标签、可用性、鉴权类型、鉴权状态与边界能力；“用于新建角色”只写入表单，不定义后端执行语义。',
      empty: '暂无 provider。',
      available: '可用',
      unavailable: '不可用',
      authReady: '鉴权已就绪',
      authMissing: '缺少鉴权',
      supportsWorkspace: 'workspace',
      supportsFocusRoot: 'focus_root',
      unavailableDefault: '当前 provider 不可用。',
      loadedDefault: '已加载 provider 元数据。',
      authTypes: {
        serviceManaged: '服务托管鉴权',
        apiKey: 'API Key',
        oauth2: 'OAuth2',
        none: '无需鉴权',
        unknown: '鉴权状态未知'
      }
    },

    providerSection: {
      workspace: {
        subtitle: '该绑定决定 Room 角色在写入 notebook、解析文件或调用支持工作区的 provider 时，可以使用哪个 workspace 与 focus root。'
      },

      catalog: {
        subtitle: '可从本地 registry provider、粘贴导入的远程 provider，以及 granted-visible 的 Room MCP capability 中选择。'
      },

      summary: {
        localRegistry: '本地目录 {count}',
        pasteImported: '粘贴导入 {count}',
        grantedVisible: '授权可见 {count}',
        finalOnly: 'Final only {count}'
      },

      import: {
        title: '粘贴远程 Room MCP 分享',
        subtitle: '将 owner 侧生成的 share ref 或 provider descriptor 粘贴到这里；导入成功后会作为 imported provider 注入下方目录，并复用既有 create / edit / save 角色绑定链路。',
        placeholder: '在此粘贴 share ref 或 provider descriptor JSON',
        helper: '最小闭环阶段，imported provider 不要求出现在默认 registry list 中；只要 share ref 解析成功并形成稳定 snapshot，就应进入 role 绑定保存链。若该 provider 来自 granted-visible 授权，则 consumer 默认获得消费权，而不是 source Room 内部执行过程的观察权。',
        importedProviderFallback: '已导入的远程 provider。'
      },

      actions: {
        importing: '导入中...',
        importShareRef: '导入 share ref',
        clearInput: '清空输入',
        clearImportedProviders: '清空已导入 provider',
        useForCreateShort: '用于新建',
        remove: '移除'
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
      hint: 'slug 可留空自动生成；若与现有角色重复，后端会自动追加 -2 / -3 后缀。'
    },

    existingRoles: {
      empty: '暂无角色',
      editHint: '编辑时若 slug 与其它角色重复，后端也会自动补后缀，避免直接报错。'
    },

    roleSummary: {
      prompt: 'Prompt',
      binding: 'Binding',
      time: 'Time',
      tools: 'Tools',
      mcp: 'MCP'
    },

    footer: {
      editing: '当前正在编辑角色配置；保存后会刷新 room 角色信息。',
      notebook: '当前正在处理角色小本本；写入 workspace notebook 不会改变 Room 正式协议。',
      default: '这里管理角色、知识绑定与 provider 配置；不改变 Room 对外正式字段。'
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
      onNoProvider: 'on · 未选择 provider',
      tool: 'tool={tool}',
      inheritWorkspace: '继承 workspace',
      inheritFocusRoot: '继承 focus_root',
      currentUnavailable: '当前不可用'
    },

    notebook: {
      defaultTitle: '{name} 小本本',
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
      providerSelected: '已选择 provider：{provider}',
      loadProviderRegistryFailed: '加载 provider 目录失败',
      refreshRolesFailed: '刷新角色失败',
      createRoleFailed: '创建角色失败',
      roleCreated: '角色已创建：{name}',
      roleCreatedWithSlug: "角色已创建：{name}（{'@'}{slug}）",
      updateRoleFailed: '更新角色失败',
      roleUpdated: '角色已更新：{name}',
      roleUpdatedWithSlug: "角色已更新：{name}（{'@'}{slug}）",
      deleteConfirm: '确认删除角色：{name} ?',
      deleteRoleFailed: '删除角色失败',
      roleDeleted: '角色已删除：{name}',
      notebookMissingWorkspace: '缺少 workspace_id，无法写入。',
      notebookEmptySummary: 'summary_md 不能为空。',
      notebookWriteFailed: '写入失败',
      notebookWriteSuccess: '写入成功：{path}'
    },

    common: {
      dash: '—',
      none: 'none',
      off: 'off',
      role: '角色',
      noProviderSelected: '未选择 provider',
      trueValue: 'true',
      falseValue: 'false'
    }
  },

  roleFormFields: {
    fields: {
      name: {
        label: '名称',
        placeholder: '例如：心理学家 / strategy_agent'
      },
      slug: {
        label: 'slug',
        placeholder: '可留空自动生成'
      },
      avatar: {
        label: '头像',
        placeholder: '🤖'
      },
      enabled: {
        label: '启用'
      },
      systemPrompt: {
        label: 'system_prompt',
        placeholder: '请输入角色提示词'
      },
      libraryId: {
        label: 'library_id',
        placeholder: '可空'
      },
      groupId: {
        label: 'group_id',
        placeholder: '可空'
      },
      docId: {
        label: 'doc_id',
        placeholder: '可空'
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
      title: 'RAG 时间范围',
      hintBefore: '复用 Chat 的交互体验，但 Room 角色正式提交仍只发 ',
      hintMiddle: ' 或 ',
      hintAfter: '。',
      modeDays: '最近 N 天',
      modeRange: '相对区间 / 绝对区间',
      clear: '清空',
      quick: '快捷',
      shortcutDays: '{count}d',
      timeFilterDays: 'time_filter_days',
      timeFilterDaysPlaceholder: '例如：7 / 30',
      descriptionLabel: '说明',
      daysReadonlyBefore: 'days 模式会清空 ',
      daysReadonlyMiddle: ' / ',
      daysReadonlyAfter: '。',
      relativeQuick: '相对区间快捷',
      relativePreset: '{older} ~ {newer} 天前',
      olderDaysAgoLabel: 'olderDaysAgo（更早）',
      olderDaysAgoPlaceholder: '例如：30',
      newerDaysAgoLabel: 'newerDaysAgo（较近）',
      newerDaysAgoPlaceholder: '例如：21',
      timeStart: 'time_start',
      timeStartPlaceholder: '例如：2026-03-01T00:00:00Z',
      timeEnd: 'time_end',
      timeEndPlaceholder: '例如：2026-04-01T00:00:00Z',
      currentRangeDays: '当前范围：最近 {count} 天。',
      currentRangeInterval: '当前区间：{start} ~ {end}',
      currentRangeEmpty: '当前未设置文档时间范围。',
      effectiveHint: 'Room 表单只负责表达语义；提交时正式协议仍统一落到 time_filter_days / time_start / time_end。'
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
      pendingBadge: '待开发',
      pendingTitle: '此功能待开发，暂不可启用',
      pendingNotice: '{feature} 功能待开发，当前已自动取消勾选。'
    },

    provider: {
      title: 'MCP 能力',
      description: '先开启 mcp，再为角色选择 provider；参数、边界和高级项会根据 provider 元数据自动变化。',
      stateOn: '已开启',
      stateOff: '未开启',
      providerLabel: 'Provider',
      providerPlaceholder: '请选择 provider',
      toolLabel: '能力',
      selectedDefault: '已选择 provider。',
      available: '可用',
      unavailable: '不可用',
      authReady: '鉴权已就绪',
      authMissing: '缺少鉴权',
      authNone: '无需鉴权',
      unavailableDefault: '当前 provider 不可用',
      boundaryTitle: '边界继承',
      boundaryDefault: 'workspace / focus_root 继承必须保持用户可控；这里只提交显式开关，不定义后端执行语义。',
      inheritWorkspace: '继承 workspace 上下文',
      inheritFocusRoot: '继承 focus_root',
      typeRoomProvider: 'Room provider',
      typePresetProvider: '预设 provider',
      importedRemote: 'Imported remote',
      snapshotFallback: '快照回显',
      originValue: 'origin：{value}',
      sourceRoomValue: 'source room：{value}',
      sharedAutoReplyValue: 'shared auto reply：{state}',
      ownerPrivateScopeValue: 'owner private scope：{state}',
      unknown: 'unknown',
      on: 'on',
      off: 'off',
      exposed: 'exposed',
      closed: 'closed',
      present: 'present',
      roomProviderSummaryTitle: 'Room provider 摘要',
      roomProviderConsumerBoundaryHint: '当前选择的是 Room provider；执行边界以 source Room 已保存的 shared capability 为准，consumer 侧 workspace / focus 不应在这里扩权覆盖。',
      importedSnapshotHint: '当前 provider 来自 imported snapshot；reopen 回显应优先依赖 snapshot，而不是要求 registry 此刻仍可枚举。',
      advancedSharedBoundaryOnly: '仅限 room-configured shared capability；owner ambient private scope 应保持关闭。',
      snapshotFallbackActive: 'reopen fallback active',
      snapshotCatalogBacked: 'catalog backed',
      pendingBadge: '待开发',
      pendingBoundaryTitle: '此功能待开发，暂不可启用',
      pendingBoundaryNotice: '{feature} 功能待开发，当前已自动取消勾选。',
      workspaceIdValue: 'workspace_id：{value}',
      focusRootValue: 'focus_root：{value}',
      rootDirectory: '（根目录）',
      advanced: '高级配置',
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
      title: '快捷动作',
      subtitle: '这里不再复制左侧栏的通用浏览能力，而是提供房间相关的轻量入口与上下文辅助。',
      ready: 'READY',
      unbound: 'UNBOUND'
    },

    empty: {
      noWorkspace: '当前未绑定 workspace。请先在房间设置中选择 workspace_context。'
    },

    sections: {
      recommendedActions: '建议入口',
      recommendedPaths: '建议路径',
      draft: '房间上下文草稿',
      roomInfo: '房间信息'
    },

    actions: {
      openRoomNote: '打开 room_note',
      openAgentNotebook: '打开 agent_notebook',
      copyFocusRoot: '复制 focus_root',
      copyWorkspaceId: '复制 workspace_id',
      copyDraft: '复制草稿',
      openRoomNotePaste: '打开 room_note 后手动粘贴',
      clear: '清空'
    },

    fields: {
      draftPlaceholder: '这里可以暂存一段房间摘要、待办、路径说明；复制后再粘贴到中栏笔记。'
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
      path: '路径'
    },

    status: {
      copied: '已复制',
      copiedFocusRoot: '已复制 focus_root',
      copiedWorkspaceId: '已复制 workspace_id',
      copiedDraft: '已复制房间上下文草稿',
      noContent: '没有可复制的内容',
      copyFailed: '复制失败，请检查浏览器权限',
      pathEmpty: '路径为空，无法打开',
      draftCleared: '草稿已清空',
      savedPathMessage: '已定位到 {label}：{path}'
    },

    common: {
      dash: '—',
      defaultAgentFallback: 'agent'
    }
  }
}

