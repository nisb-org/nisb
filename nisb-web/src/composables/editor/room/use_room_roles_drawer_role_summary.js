export function useRoomRolesDrawerRoleSummary(options = {}) {
  const {
    t,
    providerOptions,
    getProviderOption,
    extractImportedProviderOptionFromRole,
    normalizeProviderSnapshot,
    normalizeImportedProviderOption,
    safeString,
    safeObject,
    providerLabel,
    providerIsAvailable,
    isRoomSharedProvider,
    isImportedProvider,
  } = options

  function formatBinding(role) {
    const kb = role?.knowledge_binding || {}
    const parts = [
      kb.library_id ? `${t('room.rolesDrawer.binding.library')}=${kb.library_id}` : '',
      kb.group_id ? `${t('room.rolesDrawer.binding.group')}=${kb.group_id}` : '',
      kb.doc_id ? `${t('room.rolesDrawer.binding.doc')}=${kb.doc_id}` : '',
      kb.store_scope ? `${t('room.rolesDrawer.binding.store')}=${kb.store_scope}` : '',
      kb.evidence_scope ? `${t('room.rolesDrawer.binding.evidence')}=${kb.evidence_scope}` : '',
    ].filter(Boolean)
    return parts.length ? parts.join(' · ') : t('room.rolesDrawer.common.dash')
  }

  function formatDocTime(role) {
    const kb = role?.knowledge_binding || role?.binding || role?.bindings || {}
    const rawDays = Number(kb?.time_filter_days ?? role?.time_filter_days)
    const days = Number.isFinite(rawDays) && rawDays > 0 ? Math.floor(rawDays) : 0
    const start = safeString(kb?.time_start ?? role?.time_start)
    const end = safeString(kb?.time_end ?? role?.time_end)

    if (days > 0) return `${days}d`
    if (start || end) return `${start || '...'} ~ ${end || '...'}`
    return t('room.rolesDrawer.common.dash')
  }

  function resolveRoleProvider(role) {
    const binding = safeObject(role?.mcp_binding || role?.provider_binding || role?.mcp)
    const providerId = safeString(binding.provider_id).toLowerCase()
    const fromCatalog = getProviderOption(providerOptions.value, providerId)
    if (fromCatalog) return fromCatalog

    const importedFromRole = extractImportedProviderOptionFromRole(role)
    if (importedFromRole) return importedFromRole

    const snapshot = normalizeProviderSnapshot(
      role?.mcp_provider_snapshot ||
      role?.provider_snapshot ||
      binding?.provider_snapshot ||
      binding?.mcp_provider_snapshot
    )
    if (snapshot?.provider_id) {
      return normalizeImportedProviderOption({
        ...snapshot,
        provider_origin: safeString(snapshot.provider_origin, 'imported_remote'),
        mcp_share_ref: safeString(role?.mcp_share_ref || binding?.mcp_share_ref || snapshot.mcp_share_ref),
      })
    }

    return null
  }

  function formatTools(role) {
    const tp = role?.tool_policy || {}
    const labels = []

    if (tp.rag) labels.push(t('room.rolesDrawer.toolLabels.rag'))
    if (tp.web) labels.push(t('room.rolesDrawer.toolLabels.web'))
    if (tp.code) labels.push(t('room.rolesDrawer.toolLabels.code'))
    if (tp.fs_read) labels.push(t('room.rolesDrawer.toolLabels.fsRead'))
    if (tp.fs_write) labels.push(t('room.rolesDrawer.toolLabels.fsWrite'))

    if (tp.mcp) {
      const binding = safeObject(role?.mcp_binding || role?.provider_binding || role?.mcp)
      const provider = resolveRoleProvider(role)
      const providerId = safeString(binding.provider_id || provider?.provider_id)
      labels.push(`${t('room.rolesDrawer.toolLabels.mcp')}(${providerLabel(providerId, provider)})`)
    }

    return labels.length ? labels.join(' · ') : t('room.rolesDrawer.common.none')
  }

  function formatMcp(role) {
    const tp = role?.tool_policy || {}
    if (!tp.mcp) return t('room.rolesDrawer.common.off')

    const binding = safeObject(role?.mcp_binding || role?.provider_binding || role?.mcp)
    const providerId = safeString(binding.provider_id).toLowerCase()
    const provider = resolveRoleProvider(role)

    if (!providerId) return t('room.rolesDrawer.mcpSummary.onNoProvider')

    const parts = [
      provider?.label || providerId,
      t('room.rolesDrawer.mcpSummary.tool', {
        tool: safeString(binding.tool_name || provider?.tool_name, 'search'),
      }),
    ]

    if (isImportedProvider(provider)) {
      parts.push('imported_remote')
    }

    if (isRoomSharedProvider(provider)) {
      const sourceRoomId = safeString(provider?.room_source?.room_id)
      if (sourceRoomId) parts.push(`source_room=${sourceRoomId}`)
    }

    if (binding.inherit_workspace_context) parts.push(t('room.rolesDrawer.mcpSummary.inheritWorkspace'))
    if (binding.inherit_focus_root) parts.push(t('room.rolesDrawer.mcpSummary.inheritFocusRoot'))
    if (provider && !providerIsAvailable(provider)) parts.push(t('room.rolesDrawer.mcpSummary.currentUnavailable'))

    return parts.join(' · ')
  }

  function defaultNotebookFilename(role) {
    const base = String(role?.slug || role?.role_id || 'agent').trim() || 'agent'
    return `${base}.md`
  }

  function defaultNotebookTitle(role) {
    return t('room.rolesDrawer.notebook.defaultTitle', {
      name: String(role?.name || role?.slug || role?.role_id || t('room.rolesDrawer.common.role')).trim(),
    })
  }

  function defaultNotebookSummary(role) {
    return [
      t('room.rolesDrawer.notebook.template.headingRole', {
        name: String(role?.name || role?.slug || role?.role_id || t('room.rolesDrawer.common.role')).trim(),
      }),
      '',
      t('room.rolesDrawer.notebook.template.roleId', {
        value: String(role?.role_id || '').trim() || t('room.rolesDrawer.common.dash'),
      }),
      t('room.rolesDrawer.notebook.template.slug', {
        value: String(role?.slug || '').trim() || t('room.rolesDrawer.common.dash'),
      }),
      t('room.rolesDrawer.notebook.template.enabled', {
        value: role?.enabled
          ? t('room.rolesDrawer.common.trueValue')
          : t('room.rolesDrawer.common.falseValue'),
      }),
      '',
      t('room.rolesDrawer.notebook.template.systemPrompt'),
      String(role?.system_prompt || '').trim() || t('room.rolesDrawer.common.dash'),
      '',
      t('room.rolesDrawer.notebook.template.knowledgeBinding'),
      formatBinding(role),
      '',
      t('room.rolesDrawer.notebook.template.tools'),
      formatTools(role),
      '',
      t('room.rolesDrawer.notebook.template.mcp'),
      formatMcp(role),
    ].join('\n')
  }

  return {
    formatBinding,
    formatDocTime,
    resolveRoleProvider,
    formatTools,
    formatMcp,
    defaultNotebookFilename,
    defaultNotebookTitle,
    defaultNotebookSummary,
  }
}
