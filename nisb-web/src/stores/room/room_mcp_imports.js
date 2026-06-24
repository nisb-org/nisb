function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function safeString(v) {
  return v === null || v === undefined ? '' : String(v)
}

function safeBool(v, defaultValue = false) {
  if (typeof v === 'boolean') return v
  if (v === null || v === undefined) return defaultValue
  if (typeof v === 'number') return !!v
  const s = safeString(v).trim().toLowerCase()
  if (!s) return defaultValue
  return ['1', 'true', 'yes', 'on', 'y'].includes(s)
}

function safeJsonParse(v) {
  const s = safeString(v).trim()
  if (!s) return null
  try {
    return JSON.parse(s)
  } catch (_) {
    return null
  }
}

function resolveStoreRoomId(store, roomId = '') {
  return safeString(roomId || store?.roomId || store?.room?.room_id).trim()
}

function normalizeRoomMcpToolTemplates(rawTemplates, fallbackToolName = 'search') {
  const rows = safeArray(rawTemplates)
    .map((item) => {
      const row = safeObject(item)
      const tool_name = safeString(row.tool_name || row.name || fallbackToolName).trim()
      if (!tool_name) return null
      return {
        tool_name,
        label: safeString(row.label || tool_name).trim() || tool_name,
        description: safeString(row.description).trim(),
        requested_mode: safeString(row.requested_mode || 'mcp').trim() || 'mcp',
      }
    })
    .filter(Boolean)

  if (rows.length) return rows

  return [
    {
      tool_name: fallbackToolName,
      label: fallbackToolName,
      description: '',
      requested_mode: 'mcp',
    },
  ]
}

function normalizeRoomMcpRoomSource(raw = {}) {
  const row = safeObject(raw)
  const shared_boundary = safeObject(row.shared_boundary)

  return {
    room_id: safeString(row.room_id || row.source_room_id).trim(),
    owner_user_id: safeString(row.owner_user_id).trim(),
    consumer_room_id: safeString(row.consumer_room_id).trim(),
    reply_mode: safeString(row.reply_mode).trim(),
    workspace_id: safeString(row.workspace_id).trim(),
    workspace_label: safeString(row.workspace_label).trim(),
    focus_root: safeString(row.focus_root).trim(),
    focus_root_label: safeString(row.focus_root_label).trim(),
    shared_room_config_enabled: safeBool(row.shared_room_config_enabled, false),
    shared_supervisor_enabled: safeBool(row.shared_supervisor_enabled, false),
    shared_boundary: {
      owner_private_scope_exposed: safeBool(shared_boundary.owner_private_scope_exposed, false),
    },
  }
}

function normalizeRoomMcpPublication(raw = {}, fallback = {}) {
  const row = safeObject(raw)
  const fb = safeObject(fallback)

  const publish_enabled = safeBool(
    row.publish_enabled,
    safeBool(fb.publish_enabled, false)
  )
  const publish_label = safeString(row.publish_label || fb.publish_label).trim()
  const publish_summary = safeString(row.publish_summary || fb.publish_summary).trim()
  const boundary_hint = safeString(
    row.boundary_hint || fb.boundary_hint || 'room-configured shared capability only; owner private scope exposed=false'
  ).trim() || 'room-configured shared capability only; owner private scope exposed=false'
  const visibility_mode = safeString(
    row.visibility_mode || fb.visibility_mode || 'room_visible_and_grant_capable'
  ).trim() || 'room_visible_and_grant_capable'

  let publication_state = safeString(
    row.publication_state || fb.publication_state || (publish_enabled ? 'active' : 'disabled')
  ).trim().toLowerCase()
  if (!['active', 'disabled'].includes(publication_state)) {
    publication_state = publish_enabled ? 'active' : 'disabled'
  }

  return {
    provider_id: safeString(row.provider_id || fb.provider_id).trim().toLowerCase(),
    source_room_id: safeString(row.source_room_id || fb.source_room_id).trim(),
    publish_enabled,
    publish_label,
    publish_summary,
    boundary_hint,
    visibility_mode,
    publication_state,
    published_at: safeString(row.published_at || fb.published_at).trim(),
    updated_at: safeString(row.updated_at || fb.updated_at).trim(),
  }
}

function normalizeRoomMcpGrantScope(raw = {}) {
  const row = safeObject(raw)
  let result_view = safeString(row.result_view || 'final_result_only').trim()
  if (!['final_result_only', 'full_result'].includes(result_view)) {
    result_view = 'final_result_only'
  }

  return {
    result_view,
    bind_as_worker: safeBool(row.bind_as_worker, true),
    observe_source_room: safeBool(row.observe_source_room, false),
  }
}

export function normalizeRoomMcpProvider(raw = {}) {
  const row = safeObject(raw)
  const snapshot = safeObject(
    row.provider_snapshot ||
    row.imported_provider ||
    row.provider ||
    row.provider_descriptor
  )

  const source = Object.keys(snapshot).length
    ? {
        ...snapshot,
        ...row,
        room_source:
          row.room_source ||
          row.source_room ||
          snapshot.room_source ||
          snapshot.source_room,
        boundary_hint: row.boundary_hint || snapshot.boundary_hint,
        auth_state: row.auth_state || snapshot.auth_state,
        availability: row.availability || snapshot.availability,
        params_defaults: row.params_defaults || snapshot.params_defaults,
        params_schema: row.params_schema || snapshot.params_schema,
        tool_templates: row.tool_templates || snapshot.tool_templates,
        publication: row.publication || snapshot.publication,
        grant_scope: row.grant_scope || snapshot.grant_scope || row.scope || snapshot.scope,
      }
    : row

  const room_source = normalizeRoomMcpRoomSource(
    source.room_source || source.source_room || source.source || {}
  )

  let provider_id = safeString(source.provider_id || source.id).trim().toLowerCase()
  if (!provider_id && room_source.room_id) {
    provider_id = `imported__room_provider__${room_source.room_id.toLowerCase()}`
  }
  if (!provider_id) return null

  const tool_templates = normalizeRoomMcpToolTemplates(
    source.tool_templates,
    safeString(source.tool_name || source.tool || 'search').trim() || 'search'
  )
  const first_tool = tool_templates[0] || { tool_name: 'search' }

  const share_ref = safeString(source.share_ref || row.share_ref).trim()
  const inferred_origin = (
    safeString(source.provider_origin).trim() ||
    safeString(row.provider_origin).trim() ||
    (share_ref ? 'imported_remote' : 'registry_local')
  )

  const publication = normalizeRoomMcpPublication(
    source.publication || row.publication,
    {
      provider_id,
      source_room_id: room_source.room_id,
      publish_enabled: true,
      publish_label: safeString(source.label || source.provider_label || source.name || provider_id).trim(),
      publish_summary: safeString(source.description).trim(),
      boundary_hint: safeString(
        safeObject(source.boundary_hint).message ||
        row.boundary_hint_message ||
        'room-configured shared capability only; owner private scope exposed=false'
      ).trim(),
      visibility_mode: 'room_visible_and_grant_capable',
      publication_state: 'active',
    }
  )

  const grant_scope = normalizeRoomMcpGrantScope(
    source.grant_scope || row.grant_scope || source.scope || {}
  )

  const visibility_source = safeString(
    source.visibility_source ||
    row.visibility_source ||
    ''
  ).trim() || (share_ref ? 'granted_visible' : '')

  const external_result_view = safeString(
    source.external_result_view ||
    row.external_result_view ||
    grant_scope.result_view
  ).trim() || grant_scope.result_view

  const source_observation_allowed = safeBool(
    source.source_observation_allowed,
    safeBool(row.source_observation_allowed, grant_scope.observe_source_room)
  )

  return {
    provider_id,
    provider_type: safeString(source.provider_type || source.type || 'room_shared_capability').trim() || 'room_shared_capability',
    provider_origin: inferred_origin,
    label: safeString(source.label || source.provider_label || source.name || provider_id).trim() || provider_id,
    description: safeString(source.description).trim(),
    tool_templates,
    tool_name: safeString(first_tool.tool_name || source.tool_name || 'search').trim() || 'search',
    params_defaults: safeObject(source.params_defaults || source.default_params),
    params_schema: safeObject(source.params_schema || source.param_schema),
    auth_state: {
      required: safeBool(safeObject(source.auth_state).required, false),
      configured: safeBool(safeObject(source.auth_state).configured, true),
      type: safeString(safeObject(source.auth_state).type || 'none').trim() || 'none',
      message: safeString(safeObject(source.auth_state).message).trim(),
    },
    availability: {
      available: safeBool(safeObject(source.availability).available, true),
      reason: safeString(safeObject(source.availability).reason).trim(),
      message: safeString(safeObject(source.availability).message).trim(),
    },
    boundary_hint: {
      supports_workspace_context: safeBool(safeObject(source.boundary_hint).supports_workspace_context, false),
      supports_focus_root: safeBool(safeObject(source.boundary_hint).supports_focus_root, false),
      default_inherit_workspace_context: safeBool(safeObject(source.boundary_hint).default_inherit_workspace_context, false),
      default_inherit_focus_root: safeBool(safeObject(source.boundary_hint).default_inherit_focus_root, false),
      message: safeString(
        safeObject(source.boundary_hint).message ||
        publication.boundary_hint
      ).trim(),
    },
    room_source,
    share_ref,
    descriptor_version: safeString(source.descriptor_version || source.version).trim(),
    visibility_source,
    publication,
    grant_id: safeString(source.grant_id || row.grant_id).trim(),
    artifact_id: safeString(source.artifact_id || row.artifact_id).trim(),
    grant_state: safeString(source.grant_state || row.grant_state).trim(),
    discovery_mode: safeString(source.discovery_mode || row.discovery_mode).trim(),
    grant_scope,
    external_result_view,
    source_observation_allowed,
    granted_visible:
      visibility_source === 'granted_visible' ||
      safeBool(source.granted_visible, false) ||
      safeBool(row.granted_visible, false),
    provider_snapshot: null,
  }
}

export function buildRoomMcpProviderSnapshot(raw = {}) {
  const provider = normalizeRoomMcpProvider(raw)
  if (!provider) return {}

  return {
    provider_id: provider.provider_id,
    provider_type: provider.provider_type,
    provider_origin: provider.provider_origin,
    provider_label: provider.label,
    label: provider.label,
    description: provider.description,
    tool_templates: safeArray(provider.tool_templates),
    tool_name: provider.tool_name,
    params_defaults: safeObject(provider.params_defaults),
    params_schema: safeObject(provider.params_schema),
    auth_state: safeObject(provider.auth_state),
    availability: safeObject(provider.availability),
    boundary_hint: safeObject(provider.boundary_hint),
    room_source: safeObject(provider.room_source),
    share_ref: provider.share_ref,
    descriptor_version: provider.descriptor_version,
    visibility_source: provider.visibility_source,
    publication: safeObject(provider.publication),
    grant_id: provider.grant_id,
    artifact_id: provider.artifact_id,
    grant_state: provider.grant_state,
    discovery_mode: provider.discovery_mode,
    grant_scope: safeObject(provider.grant_scope),
    external_result_view: provider.external_result_view,
    source_observation_allowed: provider.source_observation_allowed,
    granted_visible: provider.granted_visible,
  }
}

export function mergeRoomMcpProviders(...groups) {
  const out = new Map()

  for (const group of groups) {
    for (const item of safeArray(group)) {
      const normalized = normalizeRoomMcpProvider(item)
      if (!normalized) continue
      normalized.provider_snapshot = buildRoomMcpProviderSnapshot(normalized)
      out.set(normalized.provider_id, normalized)
    }
  }

  return Array.from(out.values())
}

export function collectImportedRoomMcpProvidersFromRoles(roles = []) {
  const collected = []

  for (const item of safeArray(roles)) {
    const role = safeObject(item)
    const binding = safeObject(role.mcp_binding || role.provider_binding || role.mcp || {})
    const snapshot = safeObject(
      role.mcp_provider_snapshot ||
      binding.provider_snapshot ||
      binding.imported_provider ||
      role.provider_snapshot ||
      role.imported_provider
    )

    const share_ref = safeString(
      role.mcp_share_ref ||
      binding.share_ref ||
      snapshot.share_ref
    ).trim()

    const provider_origin = safeString(
      binding.provider_origin ||
      snapshot.provider_origin ||
      (share_ref ? 'imported_remote' : '')
    ).trim()

    const normalized = normalizeRoomMcpProvider({
      ...snapshot,
      provider_id: binding.provider_id || snapshot.provider_id,
      provider_type: binding.provider_type || snapshot.provider_type,
      provider_origin,
      share_ref,
      room_source: binding.room_source || snapshot.room_source,
      tool_name: binding.tool_name || snapshot.tool_name,
      params_defaults: binding.params || snapshot.params_defaults,
      visibility_source: binding.visibility_source || snapshot.visibility_source,
      publication: binding.publication || snapshot.publication,
      grant_id: binding.grant_id || snapshot.grant_id,
      artifact_id: binding.artifact_id || snapshot.artifact_id,
      grant_state: binding.grant_state || snapshot.grant_state,
      discovery_mode: binding.discovery_mode || snapshot.discovery_mode,
      grant_scope: binding.grant_scope || snapshot.grant_scope,
      external_result_view: binding.external_result_view || snapshot.external_result_view,
      source_observation_allowed:
        typeof binding.source_observation_allowed === 'boolean'
          ? binding.source_observation_allowed
          : snapshot.source_observation_allowed,
      granted_visible:
        typeof binding.granted_visible === 'boolean'
          ? binding.granted_visible
          : snapshot.granted_visible,
    })

    if (!normalized) continue
    if (safeString(normalized.provider_origin).trim() !== 'imported_remote') continue

    normalized.provider_snapshot = buildRoomMcpProviderSnapshot(normalized)
    collected.push(normalized)
  }

  return mergeRoomMcpProviders(collected)
}

function pickToolResults(raw = {}) {
  const root = safeObject(raw)
  const result = safeObject(root.result)
  const data = safeObject(root.data)
  const payload = safeObject(root.payload)

  return [
    ...safeArray(root.tool_results),
    ...safeArray(result.tool_results),
    ...safeArray(data.tool_results),
    ...safeArray(payload.tool_results),
  ]
}

export function extractResolvedRoomMcpProvider(raw = {}) {
  const root = safeObject(raw)
  const result = safeObject(root.result)
  const data = safeObject(root.data)
  const payload = safeObject(root.payload)

  const directCandidates = [
    root.provider,
    root.provider_snapshot,
    root.imported_provider,
    root.provider_descriptor,
    result.provider,
    result.provider_snapshot,
    result.imported_provider,
    result.provider_descriptor,
    data.provider,
    data.provider_snapshot,
    data.imported_provider,
    data.provider_descriptor,
    payload.provider,
    payload.provider_snapshot,
    payload.imported_provider,
    payload.provider_descriptor,
  ]

  for (const candidate of directCandidates) {
    const normalized = normalizeRoomMcpProvider(candidate)
    if (normalized) {
      normalized.provider_snapshot = buildRoomMcpProviderSnapshot(normalized)
      return normalized
    }
  }

  for (const item of pickToolResults(raw)) {
    const row = safeObject(item)
    const type = safeString(row.type).trim()

    if (
      type === 'room_mcp_provider' ||
      type === 'room_mcp_provider_resolved' ||
      type === 'room_mcp_provider_imported' ||
      type === 'room_mcp_share_ref'
    ) {
      const normalized = normalizeRoomMcpProvider(
        row.provider ||
        row.provider_snapshot ||
        row.imported_provider ||
        row.provider_descriptor ||
        row
      )
      if (normalized) {
        normalized.provider_snapshot = buildRoomMcpProviderSnapshot(normalized)
        return normalized
      }
    }
  }

  return null
}

export function getRoomMcpImportedProviders(store, roomId = '') {
  const rid = resolveStoreRoomId(store, roomId)
  if (!rid) return []

  const rows = safeArray(safeObject(store?.roomMcpImportedProvidersByRoom)[rid])
  return mergeRoomMcpProviders(rows)
}

export function setRoomMcpImportedProviders(store, roomId = '', providers = []) {
  const rid = resolveStoreRoomId(store, roomId)
  if (!rid) return []

  const next = mergeRoomMcpProviders(providers)
  store.roomMcpImportedProvidersByRoom = {
    ...safeObject(store.roomMcpImportedProvidersByRoom),
    [rid]: next,
  }
  return next
}

export function upsertRoomMcpImportedProvider(store, roomId = '', provider = {}) {
  const rid = resolveStoreRoomId(store, roomId)
  if (!rid) return null

  const normalized = normalizeRoomMcpProvider(provider)
  if (!normalized) return null

  normalized.provider_snapshot = buildRoomMcpProviderSnapshot(normalized)

  const existing = getRoomMcpImportedProviders(store, rid)
  const merged = mergeRoomMcpProviders(existing, [normalized])
  store.roomMcpImportedProvidersByRoom = {
    ...safeObject(store.roomMcpImportedProvidersByRoom),
    [rid]: merged,
  }
  store.roomMcpLastResolvedProvider = normalized
  return normalized
}

export function removeRoomMcpImportedProvider(store, roomId = '', providerId = '') {
  const rid = resolveStoreRoomId(store, roomId)
  const pid = safeString(providerId).trim().toLowerCase()
  if (!rid || !pid) return []

  const rows = getRoomMcpImportedProviders(store, rid)
    .filter((item) => safeString(item.provider_id).trim().toLowerCase() !== pid)

  store.roomMcpImportedProvidersByRoom = {
    ...safeObject(store.roomMcpImportedProvidersByRoom),
    [rid]: rows,
  }
  return rows
}

export function clearRoomMcpImportedProviders(store, roomId = '') {
  const rid = resolveStoreRoomId(store, roomId)
  if (!rid) {
    store.roomMcpImportedProvidersByRoom = {}
    return []
  }

  const next = { ...safeObject(store.roomMcpImportedProvidersByRoom) }
  delete next[rid]
  store.roomMcpImportedProvidersByRoom = next
  return []
}

export function hydrateImportedRoomMcpProvidersFromRoles(store, roomId = '', roles = []) {
  const rid = resolveStoreRoomId(store, roomId)
  if (!rid) return []

  const existing = getRoomMcpImportedProviders(store, rid)
  const imported = collectImportedRoomMcpProvidersFromRoles(roles)
  const merged = mergeRoomMcpProviders(existing, imported)

  store.roomMcpImportedProvidersByRoom = {
    ...safeObject(store.roomMcpImportedProvidersByRoom),
    [rid]: merged,
  }

  return merged
}

export async function resolveRoomMcpShareRef(store, callTool, shareRef, opts = {}) {
  const rawRef = safeString(shareRef).trim()
  if (!rawRef) {
    throw new Error('share ref 不能为空')
  }

  const rid = safeString(
    safeObject(opts).room_id ||
    safeObject(opts).roomId ||
    store?.roomId ||
    store?.room?.room_id
  ).trim()

  store.roomMcpLastResolvedShareRef = rawRef

  const parsed = safeJsonParse(rawRef)
  if (parsed && typeof parsed === 'object') {
    const localProvider = normalizeRoomMcpProvider({
      ...safeObject(parsed),
      provider_origin: safeString(
        safeObject(parsed).provider_origin || 'imported_remote'
      ).trim() || 'imported_remote',
      share_ref: safeString(
        safeObject(parsed).share_ref || rawRef
      ).trim() || rawRef,
    })

    if (localProvider) {
      localProvider.provider_snapshot = buildRoomMcpProviderSnapshot(localProvider)
      if (rid && opts.cache !== false) {
        upsertRoomMcpImportedProvider(store, rid, localProvider)
      } else {
        store.roomMcpLastResolvedProvider = localProvider
      }
      return {
        ok: true,
        source: 'local_json',
        provider: localProvider,
      }
    }
  }

  if (typeof callTool !== 'function') {
    throw new Error('当前 share ref 不是 JSON，且未提供后端 resolve 入口')
  }

  const candidateTools = safeArray(opts.resolve_tools).length
    ? safeArray(opts.resolve_tools)
    : [
        'nisb_room_mcp_share_ref_resolve',
        'nisb_room_mcp_provider_share_ref_resolve',
        'nisb_room_mcp_provider_import_resolve',
      ]

  let lastError = null

  for (const tool of candidateTools) {
    const toolName = safeString(tool).trim()
    if (!toolName) continue

    try {
      const args = {
        room_id: rid,
        share_ref: rawRef,
        ref: rawRef,
      }

      const raw = toolName.startsWith('nisb_room_') && typeof store?.callRoomTool === 'function'
        ? await store.callRoomTool(callTool, toolName, args, rid)
        : await callTool(toolName, args)

      const provider = extractResolvedRoomMcpProvider(raw)
      if (!provider) continue

      provider.provider_snapshot = buildRoomMcpProviderSnapshot(provider)

      if (rid && opts.cache !== false) {
        upsertRoomMcpImportedProvider(store, rid, provider)
      } else {
        store.roomMcpLastResolvedProvider = provider
      }

      return {
        ok: true,
        source: 'remote_tool',
        tool: toolName,
        provider,
        raw,
      }
    } catch (e) {
      lastError = e
    }
  }

  throw (
    lastError ||
    new Error('当前后端尚未提供可用的 room MCP share ref resolve tool')
  )
}
