import { computed, watch } from 'vue'

const FALLBACK_PROVIDER_OPTIONS = [
  {
    provider_id: 'serper',
    provider_type: 'preset',
    provider_origin: 'local_registry',
    label: 'Serper Search',
    provider_label: 'Serper Search',
    description: '受控网页搜索 provider；适合 Room / worker 的 web search 场景。',
    tool_templates: [
      {
        tool_name: 'search',
        label: '网页搜索',
        description: '执行受控搜索并返回搜索结果摘要。',
      },
    ],
    params_defaults: {
      query: '{{user_query}}',
      num: 8,
    },
    params_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', title: '搜索词' },
        num: { type: 'integer', title: '结果数量', minimum: 1, maximum: 10 },
      },
      required: ['query'],
    },
    auth_state: {
      required: false,
      configured: true,
      message: '当前 provider 由服务端统一配置。',
    },
    availability: {
      available: true,
      reason: '',
    },
    boundary_hint: {
      supports_workspace_context: true,
      supports_focus_root: true,
      default_inherit_workspace_context: false,
      default_inherit_focus_root: false,
      message: '可显式继承当前 Room 的 workspace / focus_root 边界；默认关闭。',
    },
    room_source: {},
    mcp_share_ref: '',
    descriptor_version: '',
    share_ref_version: '',
  },
]

function safeString(value, fallback = '') {
  if (value === null || value === undefined) return fallback
  const out = String(value).trim()
  return out || fallback
}

function safeBool(value, fallback = false) {
  if (typeof value === 'boolean') return value
  if (value === 'true') return true
  if (value === 'false') return false
  if (typeof value === 'number') return !!value
  return fallback
}

function safeObject(value, fallback = {}) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : fallback
}

function safeArray(value, fallback = []) {
  return Array.isArray(value) ? value : fallback
}

function clone(value) {
  try {
    return JSON.parse(JSON.stringify(value))
  } catch (_) {
    return value
  }
}

function normalizeBoundaryHint(value, providerType = 'preset') {
  const hint = safeObject(value)

  if (providerType === 'room_shared_capability') {
    return {
      supports_workspace_context: false,
      supports_focus_root: false,
      default_inherit_workspace_context: false,
      default_inherit_focus_root: false,
      message: safeString(
        hint.message,
        'room shared capability 在 consumer 侧不允许继承 workspace_context / focus_root。'
      ),
    }
  }

  return {
    supports_workspace_context: safeBool(hint.supports_workspace_context, true),
    supports_focus_root: safeBool(hint.supports_focus_root, true),
    default_inherit_workspace_context: safeBool(hint.default_inherit_workspace_context, false),
    default_inherit_focus_root: safeBool(hint.default_inherit_focus_root, false),
    message: safeString(hint.message, ''),
  }
}

function normalizeRoomSource(value) {
  const source = safeObject(value)
  const sharedBoundary = safeObject(source.shared_boundary)

  return {
    room_id: safeString(source.room_id, ''),
    owner_user_id: safeString(source.owner_user_id, ''),
    reply_mode: safeString(source.reply_mode, ''),
    workspace_id: safeString(source.workspace_id, ''),
    workspace_label: safeString(source.workspace_label, ''),
    focus_root: safeString(source.focus_root, ''),
    focus_root_label: safeString(source.focus_root_label, ''),
    shared_room_config_enabled: safeBool(source.shared_room_config_enabled, false),
    shared_supervisor_enabled: safeBool(source.shared_supervisor_enabled, false),
    shared_boundary: {
      owner_private_scope_exposed: safeBool(sharedBoundary.owner_private_scope_exposed, false),
    },
  }
}

function isRoomSharedCapabilityProvider(provider) {
  return safeString(provider?.provider_type, 'preset') === 'room_shared_capability'
}

function isImportedRemoteProvider(provider) {
  return safeString(provider?.provider_origin, '') === 'imported_remote'
}

function normalizeProviderOption(value, overrides = {}) {
  const raw = safeObject(value)
  const merged = {
    ...raw,
    ...safeObject(overrides),
  }

  const providerId = safeString(merged.provider_id || merged.id, '').toLowerCase()
  if (!providerId) return null

  const providerType = safeString(merged.provider_type, 'preset')
  const templates = safeArray(merged.tool_templates)
    .map((item) => {
      const row = safeObject(item)
      const toolName = safeString(row.tool_name || row.name || merged.tool_name || 'search', 'search')
      if (!toolName) return null
      return {
        tool_name: toolName,
        label: safeString(row.label || toolName, toolName),
        description: safeString(row.description, ''),
      }
    })
    .filter(Boolean)

  const normalizedTemplates = templates.length
    ? templates
    : [
        {
          tool_name: safeString(merged.tool_name, 'search'),
          label: safeString(merged.tool_name, 'search'),
          description: '',
        },
      ]

  const firstTemplate = normalizedTemplates[0] || {
    tool_name: 'search',
    label: 'search',
    description: '',
  }

  return {
    ...merged,
    provider_id: providerId,
    provider_type: providerType,
    provider_origin: safeString(merged.provider_origin, 'local_registry'),
    label: safeString(merged.label || merged.provider_label || providerId, providerId),
    provider_label: safeString(merged.provider_label || merged.label || providerId, providerId),
    description: safeString(merged.description, ''),
    tool_name: safeString(merged.tool_name || firstTemplate.tool_name, 'search'),
    tool_templates: normalizedTemplates,
    params_schema: clone(safeObject(merged.params_schema, {})),
    params_defaults: clone(safeObject(merged.params_defaults, {})),
    boundary_hint: normalizeBoundaryHint(merged.boundary_hint, providerType),
    room_source: normalizeRoomSource(merged.room_source),
    availability: clone(safeObject(merged.availability, {})),
    auth_state: clone(safeObject(merged.auth_state, {})),
    descriptor_version: safeString(merged.descriptor_version, ''),
    share_ref_version: safeString(merged.share_ref_version, ''),
    share_ref: safeString(merged.share_ref || merged.mcp_share_ref, ''),
    mcp_share_ref: safeString(merged.mcp_share_ref || merged.share_ref, ''),
  }
}

function buildProviderSnapshot(value, overrides = {}) {
  const provider = normalizeProviderOption(value, overrides)
  if (!provider) return {}

  return {
    provider_id: provider.provider_id,
    provider_type: provider.provider_type,
    provider_origin: provider.provider_origin,
    provider_label: provider.provider_label,
    label: provider.label,
    description: provider.description,
    tool_name: provider.tool_name,
    tool_templates: clone(provider.tool_templates),
    params_schema: clone(provider.params_schema),
    params_defaults: clone(provider.params_defaults),
    boundary_hint: clone(provider.boundary_hint),
    room_source: clone(provider.room_source),
    availability: clone(provider.availability),
    auth_state: clone(provider.auth_state),
    descriptor_version: provider.descriptor_version,
    share_ref_version: provider.share_ref_version,
    share_ref: provider.share_ref,
    mcp_share_ref: provider.mcp_share_ref,
  }
}

function normalizeProviderSnapshot(value, overrides = {}) {
  const normalized = normalizeProviderOption(value, overrides)
  if (!normalized) return null
  return buildProviderSnapshot(normalized, overrides)
}

export function useRoomRoleProviderBindingPanel(props, t) {
  function ensureShape() {
    if (!props.form.tool_policy || typeof props.form.tool_policy !== 'object') {
      props.form.tool_policy = {
        rag: true,
        web: false,
        mcp: false,
        code: false,
        fs_read: false,
        fs_write: false,
      }
    }

    if (!props.form.mcp_binding || typeof props.form.mcp_binding !== 'object') {
      props.form.mcp_binding = {
        enabled: false,
        provider_id: '',
        provider_type: 'preset',
        provider_origin: '',
        provider_label: '',
        tool_name: 'search',
        params: {},
        inherit_workspace_context: false,
        inherit_focus_root: false,
        share_ref: '',
        room_source: {},
        provider_snapshot: {},
      }
    }

    if (!props.form.mcp_binding.params || typeof props.form.mcp_binding.params !== 'object') {
      props.form.mcp_binding.params = {}
    }

    if (!props.form.mcp_binding.room_source || typeof props.form.mcp_binding.room_source !== 'object') {
      props.form.mcp_binding.room_source = {}
    }

    if (!props.form.mcp_binding.provider_snapshot || typeof props.form.mcp_binding.provider_snapshot !== 'object') {
      props.form.mcp_binding.provider_snapshot = {}
    }

    if (!Array.isArray(props.form.mcp_provider_ids)) {
      props.form.mcp_provider_ids = []
    }

    if (!props.form.mcp_provider_snapshot || typeof props.form.mcp_provider_snapshot !== 'object') {
      props.form.mcp_provider_snapshot = {}
    }

    if (props.form.mcp_share_ref === undefined) {
      props.form.mcp_share_ref = ''
    }
  }

  const normalizedProviderOptions = computed(() => {
    const incoming = safeArray(props.providerOptions)
      .map((item) => normalizeProviderOption(item))
      .filter((item) => !!item?.provider_id)

    return (incoming.length ? incoming : FALLBACK_PROVIDER_OPTIONS)
      .map((item) => normalizeProviderOption(item))
      .filter((item) => !!item?.provider_id)
  })

  function providerOptionLabel(provider) {
    const label = safeString(provider?.label) || safeString(provider?.provider_id)
    const type = safeString(provider?.provider_type, 'preset')
    const roomId = safeString(provider?.room_source?.room_id)
    const imported = safeString(provider?.provider_origin) === 'imported_remote'

    if (type === 'room_shared_capability') {
      if (imported) return roomId ? `${label} · imported · room:${roomId}` : `${label} · imported`
      return roomId ? `${label} · room:${roomId}` : `${label} · room`
    }

    return imported ? `${label} · imported` : label
  }

  function extractProviderSnapshotFromForm() {
    ensureShape()

    const binding = safeObject(props.form.mcp_binding)
    const candidates = [
      props.form.mcp_provider_snapshot,
      binding.provider_snapshot,
      binding.imported_provider,
      binding.provider_descriptor,
    ]

    for (const candidate of candidates) {
      const normalized = normalizeProviderSnapshot(candidate, {
        provider_id: binding.provider_id,
        provider_type: binding.provider_type,
        provider_origin: binding.provider_origin,
        provider_label: binding.provider_label,
        share_ref: props.form.mcp_share_ref || binding.share_ref,
        room_source: binding.room_source,
      })
      if (normalized && normalized.provider_id) return normalized
    }

    if (safeString(binding.provider_id)) {
      return normalizeProviderSnapshot(
        {
          provider_id: binding.provider_id,
          provider_type: binding.provider_type,
          provider_origin: binding.provider_origin,
          provider_label: binding.provider_label,
          tool_name: binding.tool_name,
          room_source: binding.room_source,
          mcp_share_ref: props.form.mcp_share_ref || binding.share_ref,
        },
        {
          share_ref: props.form.mcp_share_ref || binding.share_ref,
        }
      )
    }

    return null
  }

  const selectedProviderId = computed(() => {
    return safeString(props.form?.mcp_binding?.provider_id).toLowerCase()
  })

  const selectedProviderCatalogEntry = computed(() => {
    return normalizedProviderOptions.value.find((item) => item.provider_id === selectedProviderId.value) || null
  })

  const selectedProviderSnapshot = computed(() => extractProviderSnapshotFromForm())

  const selectedProviderResolvedFromSnapshot = computed(() => {
    return !!selectedProviderId.value && !selectedProviderCatalogEntry.value && !!selectedProviderSnapshot.value
  })

  const selectedProvider = computed(() => {
    if (selectedProviderCatalogEntry.value && selectedProviderSnapshot.value) {
      return normalizeProviderOption({
        ...selectedProviderCatalogEntry.value,
        ...selectedProviderSnapshot.value,
        room_source: {
          ...safeObject(selectedProviderCatalogEntry.value.room_source),
          ...safeObject(selectedProviderSnapshot.value.room_source),
        },
        boundary_hint: {
          ...safeObject(selectedProviderCatalogEntry.value.boundary_hint),
          ...safeObject(selectedProviderSnapshot.value.boundary_hint),
        },
        availability: {
          ...safeObject(selectedProviderCatalogEntry.value.availability),
          ...safeObject(selectedProviderSnapshot.value.availability),
        },
        auth_state: {
          ...safeObject(selectedProviderCatalogEntry.value.auth_state),
          ...safeObject(selectedProviderSnapshot.value.auth_state),
        },
      })
    }

    if (selectedProviderCatalogEntry.value) return selectedProviderCatalogEntry.value
    if (selectedProviderSnapshot.value) return selectedProviderSnapshot.value
    return null
  })

  const selectedProviderIsRoomProvider = computed(() => {
    return isRoomSharedCapabilityProvider(selectedProvider.value)
  })

  const selectedProviderIsImported = computed(() => {
    return isImportedRemoteProvider(selectedProvider.value)
  })

  const selectedProviderOriginLabel = computed(() => {
    const origin = safeString(selectedProvider.value?.provider_origin)
    if (!origin) return ''
    if (origin === 'local_registry') return 'local_registry'
    if (origin === 'imported_remote') return 'imported_remote'
    return origin
  })

  const selectedRoomSource = computed(() => normalizeRoomSource(selectedProvider.value?.room_source))
  const selectedRoomBoundary = computed(() => safeObject(selectedRoomSource.value?.shared_boundary))

  const toolTemplateOptions = computed(() => {
    const provider = selectedProvider.value
    const templates = safeArray(provider?.tool_templates)

    const normalizedTemplates = templates
      .map((item) => {
        const tool = safeObject(item)
        const toolName = safeString(tool.tool_name)
        if (!toolName) return null
        return {
          ...tool,
          tool_name: toolName,
          label: safeString(tool.label || toolName),
          description: safeString(tool.description),
        }
      })
      .filter(Boolean)

    const currentToolName = safeString(props.form?.mcp_binding?.tool_name)

    if (!normalizedTemplates.length) {
      return [
        {
          tool_name: currentToolName || safeString(provider?.tool_name, 'search'),
          label: currentToolName || safeString(provider?.tool_name, 'search'),
          description: '',
        },
      ]
    }

    if (currentToolName && !normalizedTemplates.some((item) => item.tool_name === currentToolName)) {
      return [
        ...normalizedTemplates,
        {
          tool_name: currentToolName,
          label: currentToolName,
          description: '',
        },
      ]
    }

    return normalizedTemplates
  })

  const selectedToolTemplate = computed(() => {
    const wanted = safeString(props.form?.mcp_binding?.tool_name)
    return toolTemplateOptions.value.find((item) => safeString(item.tool_name) === wanted) || toolTemplateOptions.value[0] || null
  })

  const providerFields = computed(() => {
    const provider = selectedProvider.value
    if (!provider) return []

    const schemaProps = safeObject(provider?.params_schema?.properties)
    const defaultParams = safeObject(provider?.params_defaults)
    const keys = Array.from(new Set([
      ...Object.keys(defaultParams),
      ...Object.keys(schemaProps),
    ]))

    return keys.map((key) => {
      const schema = safeObject(schemaProps[key])
      const defaultValue = defaultParams[key]
      return {
        key,
        label: schema.title || key,
        description: schema.description || '',
        type:
          schema.type ||
          (typeof defaultValue === 'number'
            ? 'number'
            : typeof defaultValue === 'boolean'
              ? 'boolean'
              : 'string'),
        minimum: schema.minimum,
        maximum: schema.maximum,
        placeholder: typeof defaultValue === 'string' ? defaultValue : '',
      }
    })
  })

  const providerAvailable = computed(() => safeBool(selectedProvider.value?.availability?.available, true))
  const authRequired = computed(() => safeBool(selectedProvider.value?.auth_state?.required, false))
  const authConfigured = computed(() => safeBool(selectedProvider.value?.auth_state?.configured, !authRequired.value))

  const providerStatusText = computed(() => {
    if (!selectedProvider.value) return ''

    if (!providerAvailable.value) {
      return safeString(
        selectedProvider.value?.availability?.reason,
        t('room.roleFormFields.provider.unavailableDefault')
      )
    }

    if (selectedProviderResolvedFromSnapshot.value) {
      return '当前 provider 未出现在本地 registry 列表，正在使用已保存 snapshot 回显；保存链必须保留 snapshot 才能 reopen 不丢。'
    }

    if (selectedProviderIsRoomProvider.value) {
      if (!selectedRoomSource.value.shared_room_config_enabled) {
        return 'source room 当前未开启 Shared Auto Reply；即使 provider 可绑定，真实调用链仍应回到 formal-first 结果。'
      }
      if (selectedRoomBoundary.value.owner_private_scope_exposed) {
        return '警告：source room boundary 显示 owner private scope 已暴露；这不符合当前第一版安全边界，应立即拦截。'
      }
      return safeString(
        selectedProvider.value?.auth_state?.message || selectedToolTemplate.value?.description || '',
        '该 provider 将桥回 source room 的既有 runtime 主链执行。'
      )
    }

    return safeString(
      selectedProvider.value?.auth_state?.message || selectedToolTemplate.value?.description || '',
      ''
    )
  })

  const supportsWorkspaceContext = computed(() => {
    if (selectedProviderIsRoomProvider.value) return false
    return safeBool(normalizeBoundaryHint(selectedProvider.value?.boundary_hint).supports_workspace_context, true)
  })

  const supportsFocusRoot = computed(() => {
    if (selectedProviderIsRoomProvider.value) return false
    return safeBool(normalizeBoundaryHint(selectedProvider.value?.boundary_hint).supports_focus_root, true)
  })

  const boundaryMessage = computed(() => {
    if (selectedProviderIsRoomProvider.value) {
      const roomId = selectedRoomSource.value.room_id || 'unknown'
      const replyMode = selectedRoomSource.value.reply_mode || 'manual'
      const providerOrigin = selectedProvider.value?.provider_origin || 'local_registry'
      return `当前选择的是 room provider，source room=${roomId}，reply_mode=${replyMode}，origin=${providerOrigin}；执行边界应固定为 source room 已保存的 room-configured shared capability，不应在 consumer 侧放开 owner ambient private scope。`
    }

    return safeString(
      selectedProvider.value?.boundary_hint?.message,
      t('room.roleFormFields.provider.boundaryDefault')
    )
  })

  const roomProviderBoundaryNote = computed(() => {
    const source = selectedRoomSource.value
    const boundary = selectedRoomBoundary.value
    const sharedEnabled = source.shared_room_config_enabled ? 'on' : 'off'
    const supervisorEnabled = source.shared_supervisor_enabled ? 'on' : 'off'
    const privateScopeExposed = boundary.owner_private_scope_exposed ? 'true' : 'false'
    return `shared_auto_reply=${sharedEnabled}；shared_supervisor=${supervisorEnabled}；owner_private_scope_exposed=${privateScopeExposed}。`
  })

  function addProviderId(providerId) {
    const pid = safeString(providerId).toLowerCase()
    if (!pid) return
    if (!props.form.mcp_provider_ids.includes(pid)) {
      props.form.mcp_provider_ids = [...props.form.mcp_provider_ids, pid]
    }
  }

  function applyProviderDefaults(provider) {
    if (!provider) return
    ensureShape()

    const templates = safeArray(provider.tool_templates)
    const firstTemplate = templates[0] || { tool_name: safeString(provider.tool_name, 'search') }
    const boundaryHint = normalizeBoundaryHint(provider.boundary_hint, provider.provider_type)
    const providerType = safeString(provider.provider_type, 'preset')
    const snapshot = buildProviderSnapshot(
      {
        ...provider,
        mcp_share_ref: props.form.mcp_share_ref || provider.mcp_share_ref || provider.share_ref,
      },
      {
        share_ref: props.form.mcp_share_ref || provider.mcp_share_ref || provider.share_ref,
      }
    )

    props.form.mcp_binding.provider_id = safeString(provider.provider_id).toLowerCase()
    props.form.mcp_binding.provider_type = providerType
    props.form.mcp_binding.provider_origin = safeString(provider.provider_origin)
    props.form.mcp_binding.provider_label = safeString(provider.label || provider.provider_id)
    props.form.mcp_binding.share_ref = safeString(props.form.mcp_share_ref || provider.mcp_share_ref || provider.share_ref)
    props.form.mcp_binding.room_source = normalizeRoomSource(provider.room_source)
    props.form.mcp_binding.provider_snapshot = snapshot
    props.form.mcp_provider_snapshot = snapshot
    props.form.mcp_share_ref = safeString(snapshot.mcp_share_ref || props.form.mcp_share_ref)

    if (!safeString(props.form.mcp_binding.tool_name)) {
      props.form.mcp_binding.tool_name = safeString(firstTemplate.tool_name, 'search')
    }

    props.form.mcp_binding.params = {
      ...(provider.params_defaults || {}),
      ...(props.form.mcp_binding.params || {}),
    }

    if (providerType === 'room_shared_capability') {
      props.form.mcp_binding.inherit_workspace_context = false
      props.form.mcp_binding.inherit_focus_root = false
    } else {
      if (props.form.mcp_binding.inherit_workspace_context === undefined) {
        props.form.mcp_binding.inherit_workspace_context = safeBool(boundaryHint.default_inherit_workspace_context, false)
      }
      if (props.form.mcp_binding.inherit_focus_root === undefined) {
        props.form.mcp_binding.inherit_focus_root = safeBool(boundaryHint.default_inherit_focus_root, false)
      }
    }

    addProviderId(provider.provider_id)
  }

  ensureShape()

  watch(
    () => props.form?.tool_policy?.mcp,
    (enabled) => {
      ensureShape()
      props.form.mcp_binding.enabled = !!enabled
    },
    { immediate: true }
  )

  watch(
    () => props.form?.mcp_binding?.provider_id,
    () => {
      ensureShape()
      const provider = selectedProvider.value
      if (!provider) {
        props.form.mcp_binding.provider_type = safeString(props.form.mcp_binding.provider_type, 'preset')
        props.form.mcp_binding.provider_origin = safeString(props.form.mcp_binding.provider_origin)
        if (!safeString(props.form.mcp_binding.tool_name)) {
          props.form.mcp_binding.tool_name = 'search'
        }
        props.form.mcp_binding.inherit_workspace_context = false
        props.form.mcp_binding.inherit_focus_root = false
        return
      }
      applyProviderDefaults(provider)
    },
    { immediate: true }
  )

  watch(
    () => props.form?.mcp_binding?.tool_name,
    (toolName) => {
      ensureShape()
      if (!safeString(toolName) && selectedToolTemplate.value) {
        props.form.mcp_binding.tool_name = safeString(selectedToolTemplate.value.tool_name, 'search')
      }
    },
    { immediate: true }
  )

  watch(
    () => selectedProviderIsRoomProvider.value,
    (isRoomProvider) => {
      ensureShape()
      if (isRoomProvider) {
        props.form.mcp_binding.inherit_workspace_context = false
        props.form.mcp_binding.inherit_focus_root = false
      }
    },
    { immediate: true }
  )

  watch(
    () => props.form?.mcp_binding?.provider_id,
    (providerId) => {
      ensureShape()
      if (safeString(providerId) && !props.form.tool_policy.mcp) {
        props.form.tool_policy.mcp = true
      }
    },
    { immediate: true }
  )

  watch(
    () => props.providerOptions,
    () => {
      ensureShape()
      if (selectedProvider.value) {
        const snapshot = buildProviderSnapshot(
          {
            ...selectedProvider.value,
            mcp_share_ref: props.form.mcp_share_ref || selectedProvider.value.mcp_share_ref || selectedProvider.value.share_ref,
          },
          {
            share_ref: props.form.mcp_share_ref || selectedProvider.value.mcp_share_ref || selectedProvider.value.share_ref,
          }
        )
        props.form.mcp_binding.provider_snapshot = snapshot
        props.form.mcp_provider_snapshot = snapshot
        props.form.mcp_share_ref = safeString(snapshot.mcp_share_ref || props.form.mcp_share_ref)
      }
    },
    { immediate: true, deep: true }
  )

  return {
    normalizedProviderOptions,
    providerOptionLabel,
    toolTemplateOptions,
    selectedProvider,
    selectedProviderIsRoomProvider,
    selectedProviderIsImported,
    selectedProviderResolvedFromSnapshot,
    selectedProviderOriginLabel,
    selectedRoomSource,
    selectedRoomBoundary,
    providerFields,
    providerAvailable,
    authRequired,
    authConfigured,
    providerStatusText,
    supportsWorkspaceContext,
    supportsFocusRoot,
    boundaryMessage,
    roomProviderBoundaryNote,
  }
}
