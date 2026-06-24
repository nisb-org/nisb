export const toolPolicyKeys = ['rag', 'web', 'mcp', 'code', 'fs_read', 'fs_write']

export const fallbackProviderOptions = [
  {
    provider_id: 'serper',
    provider_type: 'preset',
    provider_origin: 'local_registry',
    label: 'Serper Search',
    provider_label: 'Serper Search',
    description: '受控网页搜索 provider；适合 Room / worker 的 web search 场景。',
    server_tool: '',
    requested_mode: 'mcp',
    tool_templates: [
      {
        tool_name: 'search',
        label: '网页搜索',
        description: '执行受控搜索并返回搜索结果摘要。',
        requested_mode: 'mcp',
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
        num: { type: 'integer', title: '结果数量', default: 8, minimum: 1, maximum: 10 },
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

export function safeString(value, defaultValue = '') {
  if (value == null) return defaultValue
  const out = String(value).trim()
  return out || defaultValue
}

export function safeBool(value, defaultValue = false) {
  if (typeof value === 'boolean') return value
  if (value == null) return defaultValue
  if (typeof value === 'number') return !!value
  const s = String(value).trim().toLowerCase()
  if (!s) return defaultValue
  return ['1', 'true', 'yes', 'on', 'y'].includes(s)
}

export function safeArray(value) {
  return Array.isArray(value) ? value : []
}

export function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

export function clone(value) {
  try {
    return JSON.parse(JSON.stringify(value))
  } catch (_) {
    return value
  }
}

export function uniqueStrings(values) {
  const out = []
  const seen = new Set()

  for (const item of safeArray(values)) {
    const text = safeString(item).toLowerCase()
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }

  return out
}

export function defaultToolPolicy() {
  return {
    rag: true,
    web: false,
    mcp: false,
    code: false,
    fs_read: false,
    fs_write: false,
  }
}

export function normalizeProviderOrigin(value, defaultValue = 'local_registry') {
  const raw = safeString(value, defaultValue).toLowerCase()
  return raw || defaultValue
}

export function normalizeToolTemplates(rawTemplates, fallbackToolName = 'search', fallbackRequestedMode = 'mcp') {
  const rows = safeArray(rawTemplates)
    .map((item) => {
      const row = safeObject(item)
      const toolName = safeString(row.tool_name || row.name || fallbackToolName, fallbackToolName)
      if (!toolName) return null

      return {
        tool_name: toolName,
        label: safeString(row.label || toolName, toolName),
        description: safeString(row.description),
        requested_mode: safeString(row.requested_mode || fallbackRequestedMode, fallbackRequestedMode),
      }
    })
    .filter(Boolean)

  if (rows.length) return rows

  return [
    {
      tool_name: fallbackToolName,
      label: fallbackToolName,
      description: '',
      requested_mode: fallbackRequestedMode,
    },
  ]
}

export function normalizeRoomSource(rawRoomSource) {
  const row = safeObject(rawRoomSource)
  const sharedBoundary = safeObject(row.shared_boundary)

  return {
    room_id: safeString(row.room_id),
    owner_user_id: safeString(row.owner_user_id),
    reply_mode: safeString(row.reply_mode),
    workspace_id: safeString(row.workspace_id),
    workspace_label: safeString(row.workspace_label),
    focus_root: safeString(row.focus_root),
    focus_root_label: safeString(row.focus_root_label),
    shared_room_config_enabled: safeBool(row.shared_room_config_enabled, false),
    shared_supervisor_enabled: safeBool(row.shared_supervisor_enabled, false),
    shared_boundary: {
      owner_private_scope_exposed: safeBool(sharedBoundary.owner_private_scope_exposed, false),
    },
  }
}

export function normalizeBoundaryHint(rawBoundaryHint, providerType = 'preset') {
  const row = safeObject(rawBoundaryHint)
  const isRoomProvider = safeString(providerType) === 'room_shared_capability'

  if (isRoomProvider) {
    return {
      supports_workspace_context: false,
      supports_focus_root: false,
      default_inherit_workspace_context: false,
      default_inherit_focus_root: false,
      message: safeString(
        row.message,
        'room shared capability 在 consumer 侧不允许继承 workspace_context / focus_root。'
      ),
    }
  }

  return {
    supports_workspace_context: safeBool(row.supports_workspace_context, true),
    supports_focus_root: safeBool(row.supports_focus_root, true),
    default_inherit_workspace_context: safeBool(row.default_inherit_workspace_context, false),
    default_inherit_focus_root: safeBool(row.default_inherit_focus_root, false),
    message: safeString(row.message),
  }
}

function normalizeProviderOptionBase(raw, opts = {}) {
  const row = safeObject(raw)
  const providerId = safeString(row.provider_id || row.id).toLowerCase()
  if (!providerId) return null

  const providerType = safeString(row.provider_type || row.type, 'preset')
  const toolTemplates = normalizeToolTemplates(
    row.tool_templates,
    safeString(row.tool_name || row.tool || 'search', 'search'),
    safeString(row.requested_mode || 'mcp', 'mcp')
  )
  const firstTemplate = toolTemplates[0] || {
    tool_name: 'search',
    requested_mode: 'mcp',
  }

  const providerOrigin = normalizeProviderOrigin(
    row.provider_origin || opts.provider_origin,
    opts.provider_origin || 'local_registry'
  )

  return {
    provider_id: providerId,
    provider_type: providerType,
    provider_origin: providerOrigin,
    label: safeString(row.label || row.provider_label || row.name || providerId, providerId),
    provider_label: safeString(row.provider_label || row.label || row.name || providerId, providerId),
    description: safeString(row.description),
    server_tool: safeString(
      row.server_tool,
      providerType === 'room_shared_capability' ? 'nisb_room_mcp_provider_call' : ''
    ),
    requested_mode: safeString(row.requested_mode || firstTemplate.requested_mode, 'mcp'),
    tool_templates: toolTemplates,
    params_defaults: clone(safeObject(row.params_defaults || row.default_params)),
    params_schema: clone(safeObject(row.params_schema || row.param_schema)),
    auth_state: {
      required: safeBool(row?.auth_state?.required, false),
      configured: safeBool(row?.auth_state?.configured, true),
      message: safeString(row?.auth_state?.message),
    },
    availability: {
      available: row?.availability?.available === undefined
        ? true
        : safeBool(row?.availability?.available, true),
      reason: safeString(row?.availability?.reason),
    },
    boundary_hint: normalizeBoundaryHint(row.boundary_hint, providerType),
    room_source: normalizeRoomSource(row.room_source),
    tool_name: safeString(firstTemplate.tool_name, 'search'),
    mcp_share_ref: safeString(row.mcp_share_ref || row.share_ref),
    descriptor_version: safeString(row.descriptor_version),
    share_ref_version: safeString(row.share_ref_version),
  }
}

export function normalizeProviderOption(raw) {
  return normalizeProviderOptionBase(raw, { provider_origin: 'local_registry' })
}

export function normalizeImportedProviderOption(raw) {
  const root = safeObject(raw)
  const row = safeObject(
    root.provider ||
    root.provider_snapshot ||
    root.imported_provider ||
    root.mcp_provider_snapshot ||
    root
  )

  const normalized = normalizeProviderOptionBase(
    {
      ...row,
      mcp_share_ref: row.mcp_share_ref || root.mcp_share_ref || root.share_ref,
      descriptor_version: row.descriptor_version || root.descriptor_version,
      share_ref_version: row.share_ref_version || root.share_ref_version,
      provider_origin: row.provider_origin || root.provider_origin || 'imported_remote',
    },
    { provider_origin: 'imported_remote' }
  )

  if (!normalized) return null
  return normalized
}

export function mergeToolTemplates(leftTemplates = [], rightTemplates = []) {
  const merged = []
  const seen = new Set()

  for (const item of [...safeArray(leftTemplates), ...safeArray(rightTemplates)]) {
    const row = safeObject(item)
    const toolName = safeString(row.tool_name)
    if (!toolName) continue
    if (seen.has(toolName)) continue
    seen.add(toolName)
    merged.push({
      tool_name: toolName,
      label: safeString(row.label || toolName, toolName),
      description: safeString(row.description),
      requested_mode: safeString(row.requested_mode || 'mcp', 'mcp'),
    })
  }

  return merged
}

export function mergeProviderOptionPair(left, right) {
  const a = safeObject(left)
  const b = safeObject(right)
  if (!Object.keys(a).length) return clone(b)
  if (!Object.keys(b).length) return clone(a)

  const providerType = safeString(b.provider_type || a.provider_type, 'preset')
  const mergedTemplates = mergeToolTemplates(a.tool_templates, b.tool_templates)
  const firstTemplate = mergedTemplates[0] || { tool_name: 'search', requested_mode: 'mcp' }

  const originA = normalizeProviderOrigin(a.provider_origin, 'local_registry')
  const originB = normalizeProviderOrigin(b.provider_origin, 'local_registry')
  const preferred = originB === 'imported_remote' ? b : a
  const secondary = preferred === b ? a : b

  return {
    provider_id: safeString(preferred.provider_id || secondary.provider_id).toLowerCase(),
    provider_type: providerType,
    provider_origin: normalizeProviderOrigin(preferred.provider_origin || secondary.provider_origin, 'local_registry'),
    label: safeString(preferred.label || secondary.label || preferred.provider_label || secondary.provider_label),
    provider_label: safeString(preferred.provider_label || preferred.label || secondary.provider_label || secondary.label),
    description: safeString(preferred.description || secondary.description),
    server_tool: safeString(
      preferred.server_tool || secondary.server_tool,
      providerType === 'room_shared_capability' ? 'nisb_room_mcp_provider_call' : ''
    ),
    requested_mode: safeString(
      preferred.requested_mode || secondary.requested_mode || firstTemplate.requested_mode,
      'mcp'
    ),
    tool_templates: mergedTemplates.length ? mergedTemplates : normalizeToolTemplates([], 'search', 'mcp'),
    params_defaults: {
      ...clone(safeObject(a.params_defaults)),
      ...clone(safeObject(b.params_defaults)),
    },
    params_schema: Object.keys(safeObject(b.params_schema)).length
      ? clone(safeObject(b.params_schema))
      : clone(safeObject(a.params_schema)),
    auth_state: {
      ...clone(safeObject(a.auth_state)),
      ...clone(safeObject(b.auth_state)),
    },
    availability: {
      ...clone(safeObject(a.availability)),
      ...clone(safeObject(b.availability)),
    },
    boundary_hint: normalizeBoundaryHint(
      {
        ...clone(safeObject(a.boundary_hint)),
        ...clone(safeObject(b.boundary_hint)),
      },
      providerType
    ),
    room_source: normalizeRoomSource({
      ...clone(safeObject(a.room_source)),
      ...clone(safeObject(b.room_source)),
    }),
    tool_name: safeString(preferred.tool_name || secondary.tool_name || firstTemplate.tool_name, 'search'),
    mcp_share_ref: safeString(preferred.mcp_share_ref || secondary.mcp_share_ref),
    descriptor_version: safeString(preferred.descriptor_version || secondary.descriptor_version),
    share_ref_version: safeString(preferred.share_ref_version || secondary.share_ref_version),
    _merged_from: [originA, originB],
  }
}

export function mergeProviderOptions(localProviders = [], importedProviders = []) {
  const merged = []
  const indexById = new Map()

  for (const item of safeArray(localProviders)) {
    const normalized = normalizeProviderOption(item) || normalizeImportedProviderOption(item)
    if (!normalized) continue
    const pid = safeString(normalized.provider_id).toLowerCase()
    if (!pid) continue
    indexById.set(pid, merged.length)
    merged.push(normalized)
  }

  for (const item of safeArray(importedProviders)) {
    const normalized = normalizeImportedProviderOption(item) || normalizeProviderOption(item)
    if (!normalized) continue
    const pid = safeString(normalized.provider_id).toLowerCase()
    if (!pid) continue

    if (!indexById.has(pid)) {
      indexById.set(pid, merged.length)
      merged.push(normalized)
      continue
    }

    const idx = indexById.get(pid)
    merged[idx] = mergeProviderOptionPair(merged[idx], normalized)
  }

  return merged
}

export function buildProviderSnapshot(provider = {}, overrides = {}) {
  const opt = safeObject(provider)
  const row = safeObject(overrides)

  const providerId = safeString(row.provider_id || opt.provider_id).toLowerCase()
  if (!providerId) return {}

  const providerType = safeString(row.provider_type || opt.provider_type, 'preset')
  const providerOrigin = normalizeProviderOrigin(
    row.provider_origin || opt.provider_origin,
    row.provider_origin || opt.provider_origin || 'local_registry'
  )

  const toolTemplates = mergeToolTemplates(
    safeArray(opt.tool_templates),
    safeArray(row.tool_templates)
  )

  const firstTemplate = toolTemplates[0] || {
    tool_name: safeString(row.tool_name || opt.tool_name, 'search'),
    requested_mode: safeString(row.requested_mode || opt.requested_mode, 'mcp'),
  }

  return {
    provider_id: providerId,
    provider_type: providerType,
    provider_origin: providerOrigin,
    provider_label: safeString(
      row.provider_label || row.label || opt.provider_label || opt.label || providerId,
      providerId
    ),
    label: safeString(
      row.label || row.provider_label || opt.label || opt.provider_label || providerId,
      providerId
    ),
    description: safeString(row.description || opt.description),
    server_tool: safeString(
      row.server_tool || opt.server_tool,
      providerType === 'room_shared_capability' ? 'nisb_room_mcp_provider_call' : ''
    ),
    tool_name: safeString(
      row.tool_name || opt.tool_name || firstTemplate.tool_name,
      'search'
    ),
    requested_mode: safeString(
      row.requested_mode || opt.requested_mode || firstTemplate.requested_mode,
      'mcp'
    ),
    tool_templates: toolTemplates.length
      ? toolTemplates
      : normalizeToolTemplates([], 'search', 'mcp'),
    params_defaults: clone({
      ...safeObject(opt.params_defaults),
      ...safeObject(row.params_defaults),
    }),
    params_schema: Object.keys(safeObject(row.params_schema)).length
      ? clone(safeObject(row.params_schema))
      : clone(safeObject(opt.params_schema)),
    auth_state: clone({
      ...safeObject(opt.auth_state),
      ...safeObject(row.auth_state),
    }),
    availability: clone({
      available: row?.availability?.available === undefined
        ? (
          opt?.availability?.available === undefined
            ? true
            : safeBool(opt?.availability?.available, true)
        )
        : safeBool(row?.availability?.available, true),
      reason: safeString(row?.availability?.reason || opt?.availability?.reason),
    }),
    boundary_hint: normalizeBoundaryHint(
      {
        ...safeObject(opt.boundary_hint),
        ...safeObject(row.boundary_hint),
      },
      providerType
    ),
    room_source: normalizeRoomSource({
      ...safeObject(opt.room_source),
      ...safeObject(row.room_source),
    }),
    mcp_share_ref: safeString(row.mcp_share_ref || row.share_ref || opt.mcp_share_ref),
    descriptor_version: safeString(row.descriptor_version || opt.descriptor_version),
    share_ref_version: safeString(row.share_ref_version || opt.share_ref_version),
  }
}

export function snapshotToProviderOption(snapshot = {}) {
  const row = safeObject(snapshot)
  if (!Object.keys(row).length) return null

  return normalizeImportedProviderOption({
    provider_id: row.provider_id,
    provider_type: row.provider_type,
    provider_origin: row.provider_origin || 'imported_remote',
    provider_label: row.provider_label,
    label: row.label || row.provider_label,
    description: row.description,
    server_tool: row.server_tool,
    tool_name: row.tool_name,
    requested_mode: row.requested_mode,
    tool_templates: row.tool_templates,
    params_defaults: row.params_defaults,
    params_schema: row.params_schema,
    auth_state: row.auth_state,
    availability: row.availability,
    boundary_hint: row.boundary_hint,
    room_source: row.room_source,
    mcp_share_ref: row.mcp_share_ref,
    descriptor_version: row.descriptor_version,
    share_ref_version: row.share_ref_version,
  })
}

export function normalizeProviderSnapshot(raw) {
  const imported = normalizeImportedProviderOption(raw)
  if (imported) {
    return buildProviderSnapshot(imported, raw)
  }

  const local = normalizeProviderOption(raw)
  if (local) {
    return buildProviderSnapshot(local, raw)
  }

  return {}
}

export function getProviderOption(providerOptions, providerId) {
  const pid = safeString(providerId).toLowerCase()
  if (!pid) return null
  const list = safeArray(providerOptions)
  return list.find((item) => safeString(item.provider_id).toLowerCase() === pid) || null
}

export function getToolTemplate(provider, toolName = '') {
  const templates = safeArray(provider?.tool_templates)
  const wanted = safeString(toolName)
  if (!templates.length) return null
  if (!wanted) return templates[0] || null
  return templates.find((item) => safeString(item.tool_name) === wanted) || templates[0] || null
}

export function isRoomSharedCapabilityProvider(provider) {
  return safeString(provider?.provider_type) === 'room_shared_capability'
}

export function isImportedRemoteProvider(provider) {
  return normalizeProviderOrigin(provider?.provider_origin, '') === 'imported_remote'
}

export function resolveProviderForBinding(providerOptions = [], providerId = '', providerSnapshot = {}) {
  const provider = getProviderOption(providerOptions, providerId)
  if (provider) return provider

  const fromSnapshot = snapshotToProviderOption(providerSnapshot)
  if (fromSnapshot && safeString(fromSnapshot.provider_id).toLowerCase() === safeString(providerId).toLowerCase()) {
    return fromSnapshot
  }

  return null
}

export function defaultMcpBinding(providerOptions = [], providerId = '') {
  const provider = getProviderOption(providerOptions, providerId)
  const template = getToolTemplate(provider)
  const boundaryHint = safeObject(provider?.boundary_hint)
  const isRoomProvider = isRoomSharedCapabilityProvider(provider)

  return {
    enabled: false,
    provider_id: safeString(providerId).toLowerCase(),
    provider_type: safeString(provider?.provider_type, 'preset'),
    provider_origin: normalizeProviderOrigin(provider?.provider_origin, 'local_registry'),
    server_tool: safeString(provider?.server_tool),
    tool_name: safeString(template?.tool_name, 'search'),
    requested_mode: safeString(template?.requested_mode || provider?.requested_mode, 'mcp'),
    params: clone(safeObject(provider?.params_defaults)),
    inherit_workspace_context: isRoomProvider
      ? false
      : safeBool(boundaryHint.default_inherit_workspace_context, false),
    inherit_focus_root: isRoomProvider
      ? false
      : safeBool(boundaryHint.default_inherit_focus_root, false),
  }
}

export function sanitizeParams(rawParams) {
  const out = {}
  const params = safeObject(rawParams)

  for (const [key, value] of Object.entries(params)) {
    const name = safeString(key)
    if (!name) continue

    if (typeof value === 'number' || typeof value === 'boolean') {
      out[name] = value
      continue
    }

    if (value == null) continue
    out[name] = String(value)
  }

  return out
}

export function normalizeMcpBinding(source, providerOptions = [], fallbackSnapshot = {}) {
  const row = safeObject(source)
  const snapshot = normalizeProviderSnapshot(
    row.provider_snapshot ||
    row.mcp_provider_snapshot ||
    fallbackSnapshot
  )

  const providerId = safeString(row.provider_id || row.id || snapshot.provider_id).toLowerCase()
  const provider = resolveProviderForBinding(providerOptions, providerId, snapshot)
  const template = getToolTemplate(provider, row.tool_name || row.toolName)
  const boundaryHint = safeObject(provider?.boundary_hint)
  const defaultParams = clone(safeObject(provider?.params_defaults))
  const mergedParams = {
    ...defaultParams,
    ...sanitizeParams(row.params),
  }
  const isRoomProvider = isRoomSharedCapabilityProvider(provider)

  return {
    enabled: safeBool(row.enabled, false),
    provider_id: providerId,
    provider_type: safeString(row.provider_type || provider?.provider_type || snapshot.provider_type, 'preset'),
    provider_origin: normalizeProviderOrigin(
      row.provider_origin || provider?.provider_origin || snapshot.provider_origin,
      providerId ? 'local_registry' : 'local_registry'
    ),
    server_tool: safeString(
      row.server_tool || provider?.server_tool || snapshot.server_tool,
      safeString(row.provider_type || provider?.provider_type || snapshot.provider_type) === 'room_shared_capability'
        ? 'nisb_room_mcp_provider_call'
        : ''
    ),
    tool_name: safeString(row.tool_name || template?.tool_name || provider?.tool_name || snapshot.tool_name, 'search'),
    requested_mode: safeString(
      row.requested_mode || template?.requested_mode || provider?.requested_mode || snapshot.requested_mode,
      'mcp'
    ),
    params: mergedParams,
    inherit_workspace_context: isRoomProvider
      ? false
      : (
        row.inherit_workspace_context === undefined
          ? safeBool(boundaryHint.default_inherit_workspace_context, false)
          : safeBool(row.inherit_workspace_context, false)
      ),
    inherit_focus_root: isRoomProvider
      ? false
      : (
        row.inherit_focus_root === undefined
          ? safeBool(boundaryHint.default_inherit_focus_root, false)
          : safeBool(row.inherit_focus_root, false)
      ),
  }
}

export function extractProviderSnapshotFromRole(role) {
  const row = safeObject(role)
  const binding = safeObject(row.mcp_binding || row.provider_binding || row.mcp)

  return normalizeProviderSnapshot(
    row.mcp_provider_snapshot ||
    row.provider_snapshot ||
    row.imported_provider ||
    binding.provider_snapshot ||
    binding.mcp_provider_snapshot
  )
}

export function extractProviderShareRefFromRole(role) {
  const row = safeObject(role)
  const binding = safeObject(row.mcp_binding || row.provider_binding || row.mcp)

  return safeString(
    row.mcp_share_ref ||
    row.share_ref ||
    binding.mcp_share_ref ||
    binding.share_ref
  )
}

export function extractImportedProviderOptionFromRole(role) {
  const row = safeObject(role)
  const binding = safeObject(row.mcp_binding || row.provider_binding || row.mcp)
  const snapshot = extractProviderSnapshotFromRole(row)
  const shareRef = extractProviderShareRefFromRole(row)

  if (!snapshot.provider_id) return null

  const providerOrigin = normalizeProviderOrigin(
    binding.provider_origin || snapshot.provider_origin,
    ''
  )

  if (providerOrigin !== 'imported_remote' && !shareRef) return null

  return snapshotToProviderOption({
    ...snapshot,
    mcp_share_ref: shareRef || snapshot.mcp_share_ref,
    provider_origin: providerOrigin || 'imported_remote',
  })
}

export function extractImportedProviderOptionsFromRoles(roles = []) {
  return mergeProviderOptions(
    [],
    safeArray(roles)
      .map((role) => extractImportedProviderOptionFromRole(role))
      .filter(Boolean)
  )
}
