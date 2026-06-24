import {
  safeString,
  safeBool,
  safeArray,
  safeObject,
  clone,
  uniqueStrings,
  defaultToolPolicy,
  normalizeProviderOrigin,
  normalizeProviderSnapshot,
  buildProviderSnapshot,
  snapshotToProviderOption,
  extractImportedProviderOptionFromRole,
  extractProviderSnapshotFromRole,
  extractProviderShareRefFromRole,
  mergeProviderOptions,
  normalizeMcpBinding,
  defaultMcpBinding,
  getToolTemplate,
  isRoomSharedCapabilityProvider,
  isImportedRemoteProvider,
  resolveProviderForBinding,
  sanitizeParams,
} from './room_roles_provider_binding'

export function createEmptyForm(providerOptions = []) {
  return {
    name: '',
    slug: '',
    avatar: '🤖',
    enabled: true,
    system_prompt: '',
    library_id: '',
    group_id: '',
    doc_id: '',
    store_scope: 'library',
    evidence_scope: 'library',
    time_filter_days: '',
    time_start: '',
    time_end: '',
    tool_policy: defaultToolPolicy(),
    mcp_binding: defaultMcpBinding(providerOptions),
    mcp_provider_ids: [],
    mcp_provider_snapshot: {},
    mcp_share_ref: '',
  }
}

export function resetForm(target, providerOptions = []) {
  Object.assign(target, createEmptyForm(providerOptions))
}

export function normalizeKnowledgeBinding(source) {
  const row = safeObject(source)

  const rawDays = Number(row.time_filter_days)
  const timeFilterDays = Number.isFinite(rawDays) && rawDays > 0 ? Math.floor(rawDays) : ''

  let timeStart = safeString(row.time_start)
  let timeEnd = safeString(row.time_end)

  if (timeFilterDays) {
    timeStart = ''
    timeEnd = ''
  }

  return {
    library_id: safeString(row.library_id),
    group_id: safeString(row.group_id),
    doc_id: safeString(row.doc_id),
    store_scope: safeString(row.store_scope, 'library'),
    evidence_scope: safeString(row.evidence_scope, 'library'),
    time_filter_days: timeFilterDays,
    time_start: timeStart,
    time_end: timeEnd,
  }
}

export function fillFormFromRole(target, role, providerOptions = []) {
  const row = safeObject(role)
  const kb = normalizeKnowledgeBinding({
    ...(row.knowledge_binding || row.binding || row.bindings || {}),
    time_filter_days:
      row?.knowledge_binding?.time_filter_days ??
      row?.binding?.time_filter_days ??
      row?.bindings?.time_filter_days ??
      row?.time_filter_days,
    time_start:
      row?.knowledge_binding?.time_start ??
      row?.binding?.time_start ??
      row?.bindings?.time_start ??
      row?.time_start,
    time_end:
      row?.knowledge_binding?.time_end ??
      row?.binding?.time_end ??
      row?.bindings?.time_end ??
      row?.time_end,
  })

  const toolPolicy = {
    ...defaultToolPolicy(),
    ...safeObject(row.tool_policy),
  }

  const roleSnapshot = extractProviderSnapshotFromRole(row)
  const importedProviderOption = extractImportedProviderOptionFromRole(row)
  const mergedProviderOptions = mergeProviderOptions(
    providerOptions,
    importedProviderOption ? [importedProviderOption] : []
  )

  const mcpBinding = normalizeMcpBinding(
    row.mcp_binding || row.provider_binding || row.mcp || {},
    mergedProviderOptions,
    roleSnapshot
  )

  const resolvedProvider = resolveProviderForBinding(
    mergedProviderOptions,
    mcpBinding.provider_id,
    roleSnapshot
  )

  const finalSnapshot = mcpBinding.provider_id
    ? (
      roleSnapshot.provider_id
        ? roleSnapshot
        : buildProviderSnapshot(
          resolvedProvider || {},
          {
            provider_id: mcpBinding.provider_id,
            provider_type: mcpBinding.provider_type,
            provider_origin: mcpBinding.provider_origin,
            server_tool: mcpBinding.server_tool,
            tool_name: mcpBinding.tool_name,
            requested_mode: mcpBinding.requested_mode,
            mcp_share_ref: extractProviderShareRefFromRole(row),
          }
        )
    )
    : {}

  const providerIds = uniqueStrings([
    mcpBinding.provider_id,
    finalSnapshot.provider_id,
    ...safeArray(row.mcp_provider_ids || row.provider_ids),
  ])

  Object.assign(target, createEmptyForm(mergedProviderOptions), {
    name: safeString(row.name),
    slug: safeString(row.slug),
    avatar: safeString(row.avatar, '🤖'),
    enabled: safeBool(row.enabled, true),
    system_prompt: safeString(row.system_prompt),
    library_id: kb.library_id,
    group_id: kb.group_id,
    doc_id: kb.doc_id,
    store_scope: kb.store_scope,
    evidence_scope: kb.evidence_scope,
    time_filter_days: kb.time_filter_days,
    time_start: kb.time_start,
    time_end: kb.time_end,
    tool_policy: toolPolicy,
    mcp_binding: mcpBinding,
    mcp_provider_ids: providerIds,
    mcp_provider_snapshot: finalSnapshot,
    mcp_share_ref: extractProviderShareRefFromRole(row),
  })
}

export function buildPayload(form, providerOptions = []) {
  const toolPolicy = {
    ...defaultToolPolicy(),
    ...safeObject(form?.tool_policy),
  }

  const knowledgeBinding = normalizeKnowledgeBinding({
    library_id: form?.library_id,
    group_id: form?.group_id,
    doc_id: form?.doc_id,
    store_scope: form?.store_scope,
    evidence_scope: form?.evidence_scope,
    time_filter_days: form?.time_filter_days,
    time_start: form?.time_start,
    time_end: form?.time_end,
  })

  const rawMcp = safeObject(form?.mcp_binding)
  const rawSnapshot = normalizeProviderSnapshot(
    form?.mcp_provider_snapshot ||
    rawMcp.provider_snapshot ||
    rawMcp.mcp_provider_snapshot
  )

  const providerId = safeString(rawMcp.provider_id || rawSnapshot.provider_id).toLowerCase()
  const provider = resolveProviderForBinding(providerOptions, providerId, rawSnapshot)
  const template = getToolTemplate(provider, rawMcp.tool_name)
  const boundaryHint = safeObject(provider?.boundary_hint)
  const isRoomProvider = isRoomSharedCapabilityProvider(provider)

  const mcpBinding = {
    enabled: !!toolPolicy.mcp && !!providerId,
    provider_id: providerId,
    provider_type: safeString(
      rawMcp.provider_type || provider?.provider_type || rawSnapshot.provider_type,
      'preset'
    ),
    provider_origin: normalizeProviderOrigin(
      rawMcp.provider_origin || provider?.provider_origin || rawSnapshot.provider_origin,
      providerId ? 'local_registry' : 'local_registry'
    ),
    server_tool: safeString(
      rawMcp.server_tool || provider?.server_tool || rawSnapshot.server_tool,
      safeString(rawMcp.provider_type || provider?.provider_type || rawSnapshot.provider_type) === 'room_shared_capability'
        ? 'nisb_room_mcp_provider_call'
        : ''
    ),
    tool_name: safeString(
      rawMcp.tool_name || template?.tool_name || provider?.tool_name || rawSnapshot.tool_name,
      'search'
    ),
    requested_mode: safeString(
      rawMcp.requested_mode || template?.requested_mode || provider?.requested_mode || rawSnapshot.requested_mode,
      'mcp'
    ),
    params: sanitizeParams(rawMcp.params),
    inherit_workspace_context: isRoomProvider
      ? false
      : (
        rawMcp.inherit_workspace_context === undefined
          ? safeBool(boundaryHint.default_inherit_workspace_context, false)
          : safeBool(rawMcp.inherit_workspace_context, false)
      ),
    inherit_focus_root: isRoomProvider
      ? false
      : (
        rawMcp.inherit_focus_root === undefined
          ? safeBool(boundaryHint.default_inherit_focus_root, false)
          : safeBool(rawMcp.inherit_focus_root, false)
      ),
  }

  const mcpShareRef = mcpBinding.enabled
    ? safeString(form?.mcp_share_ref || rawMcp.mcp_share_ref || rawSnapshot.mcp_share_ref)
    : ''

  const mcpProviderSnapshot = mcpBinding.enabled
    ? buildProviderSnapshot(
      provider || snapshotToProviderOption(rawSnapshot) || {},
      {
        provider_id: mcpBinding.provider_id,
        provider_type: mcpBinding.provider_type,
        provider_origin: mcpBinding.provider_origin,
        server_tool: mcpBinding.server_tool,
        tool_name: mcpBinding.tool_name,
        requested_mode: mcpBinding.requested_mode,
        mcp_share_ref: mcpShareRef,
      }
    )
    : {}

  return {
    name: safeString(form?.name),
    slug: safeString(form?.slug),
    avatar: safeString(form?.avatar, '🤖') || '🤖',
    enabled: safeBool(form?.enabled, true),
    system_prompt: safeString(form?.system_prompt),
    knowledge_binding: knowledgeBinding,
    tool_policy: toolPolicy,
    mcp_binding: {
      ...mcpBinding,
      provider_snapshot: clone(mcpProviderSnapshot),
      mcp_share_ref: mcpShareRef,
    },
    mcp_provider_ids: uniqueStrings([
      providerId,
      mcpProviderSnapshot.provider_id,
      ...safeArray(form?.mcp_provider_ids),
    ]),
    mcp_provider_snapshot: clone(mcpProviderSnapshot),
    mcp_share_ref: mcpShareRef,
  }
}

export function validateRolePayload(payload, providerOptions = []) {
  if (!safeString(payload?.name)) return '角色名称不能为空'

  const kb = safeObject(payload?.knowledge_binding)
  const rawDays = Number(kb.time_filter_days)
  const hasDays = Number.isFinite(rawDays) && rawDays > 0
  const hasStart = !!safeString(kb.time_start)
  const hasEnd = !!safeString(kb.time_end)

  if (hasDays && (hasStart || hasEnd)) {
    return '时间范围只能二选一：time_filter_days 或 time_start/time_end'
  }

  if (!hasDays && (hasStart || hasEnd) && !(hasStart && hasEnd)) {
    return '区间模式必须同时填写 time_start 和 time_end'
  }

  if (!hasDays && hasStart && hasEnd) {
    const startMs = Date.parse(kb.time_start)
    const endMs = Date.parse(kb.time_end)
    if (Number.isFinite(startMs) && Number.isFinite(endMs) && startMs > endMs) {
      return 'time_start 不能晚于 time_end'
    }
  }

  if (safeBool(payload?.tool_policy?.mcp, false)) {
    const providerId = safeString(payload?.mcp_binding?.provider_id).toLowerCase()
    if (!providerId) return '开启 MCP 后必须选择 provider'

    const snapshot = normalizeProviderSnapshot(
      payload?.mcp_provider_snapshot ||
      payload?.mcp_binding?.provider_snapshot
    )

    const provider = resolveProviderForBinding(providerOptions, providerId, snapshot)
    if (!provider) {
      return '当前 provider 未进入本地目录，且缺少 imported provider snapshot，当前不能保存'
    }

    const available = provider?.availability?.available
    if (available === false) {
      return safeString(provider?.availability?.reason, '当前 provider 不可用')
    }

    if (isImportedRemoteProvider(provider)) {
      if (!snapshot.provider_id || !snapshot.provider_type) {
        return 'imported provider 缺少稳定 snapshot，当前不能保存'
      }

      if (!safeString(snapshot.room_source?.room_id) && safeString(snapshot.provider_type) === 'room_shared_capability') {
        return 'imported room provider 缺少 source_room_id，当前不能保存'
      }
    }

    if (isRoomSharedCapabilityProvider(provider)) {
      const roomSource = safeObject(provider?.room_source || snapshot?.room_source)
      const sharedBoundary = safeObject(roomSource?.shared_boundary)

      if (!safeString(roomSource.room_id)) {
        return 'room provider 缺少 source_room_id，当前不能保存'
      }

      if (safeBool(sharedBoundary.owner_private_scope_exposed, false)) {
        return 'room provider boundary 非法：owner private scope 不应暴露'
      }

      if (safeBool(payload?.mcp_binding?.inherit_workspace_context, false)) {
        return 'room provider 不允许在 consumer 侧启用 inherit_workspace_context'
      }

      if (safeBool(payload?.mcp_binding?.inherit_focus_root, false)) {
        return 'room provider 不允许在 consumer 侧启用 inherit_focus_root'
      }
    }
  }

  return ''
}
