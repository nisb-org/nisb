import {
  toolPolicyKeys,
  fallbackProviderOptions,
  safeString,
  safeBool,
  safeArray,
  safeObject,
  clone,
  normalizeProviderOption,
  normalizeImportedProviderOption,
  normalizeProviderSnapshot,
  buildProviderSnapshot,
  snapshotToProviderOption,
  extractImportedProviderOptionFromRole,
  extractImportedProviderOptionsFromRoles,
  extractProviderSnapshotFromRole,
  extractProviderShareRefFromRole,
  mergeProviderOptions,
  normalizeMcpBinding,
  defaultMcpBinding,
  getProviderOption,
  getToolTemplate,
  isRoomSharedCapabilityProvider,
  isImportedRemoteProvider,
} from './room_roles_provider_binding'

import {
  createEmptyForm,
  resetForm,
  fillFormFromRole,
  buildPayload,
  validateRolePayload,
} from './room_roles_form_persistence'

export function useRoomRolesDrawerForm() {
  function normalizeToolResult(res) {
    if (res && typeof res === 'object' && res.result && typeof res.result === 'object') {
      return res.result
    }
    return res || {}
  }

  function assertToolSuccess(res) {
    const data = normalizeToolResult(res)
    if (data?.status && data.status !== 'success') {
      throw new Error(String(data.message || '操作失败'))
    }
    if (data?.success === false) {
      throw new Error(String(data.message || '操作失败'))
    }
    return data
  }

  function pickToolResult(data, typeNames) {
    const wanted = safeArray(typeNames)
    const rows = safeArray(data?.tool_results)
    return rows.find((item) => item && typeof item === 'object' && wanted.includes(item.type)) || null
  }

  function extractRoleFromResult(data) {
    const row = pickToolResult(data, ['room_role'])
    if (row?.role && typeof row.role === 'object') return row.role
    if (data?.role && typeof data.role === 'object') return data.role
    return null
  }

  function extractProviderOptions(data) {
    let providers = []

    if (Array.isArray(data?.providers)) {
      providers = data.providers
    }

    const toolRow = pickToolResult(data, [
      'room_mcp_provider_registry',
      'room_mcp_provider_list',
      'room_mcp_providers',
    ])

    if (!providers.length && Array.isArray(toolRow?.providers)) {
      providers = toolRow.providers
    }

    const normalized = providers
      .map((item) => normalizeProviderOption(item) || normalizeImportedProviderOption(item))
      .filter(Boolean)

    if (normalized.length) return normalized
    return fallbackProviderOptions.map((item) => clone(item))
  }

  async function fetchProviderOptions(callTool) {
    try {
      const data = normalizeToolResult(await callTool('nisb_room_mcp_provider_list', {}))
      return extractProviderOptions(data)
    } catch (_) {
      return fallbackProviderOptions.map((item) => clone(item))
    }
  }

  return {
    toolPolicyKeys,
    fallbackProviderOptions,
    createEmptyForm,
    resetForm,
    fillFormFromRole,
    buildPayload,
    validateRolePayload,
    normalizeToolResult,
    assertToolSuccess,
    extractRoleFromResult,
    fetchProviderOptions,
    getProviderOption,
    getToolTemplate,
    isRoomSharedCapabilityProvider,
    isImportedRemoteProvider,
    normalizeProviderOption,
    normalizeImportedProviderOption,
    normalizeProviderSnapshot,
    buildProviderSnapshot,
    snapshotToProviderOption,
    extractImportedProviderOptionFromRole,
    extractImportedProviderOptionsFromRoles,
    extractProviderSnapshotFromRole,
    extractProviderShareRefFromRole,
    mergeProviderOptions,
    normalizeMcpBinding,
    defaultMcpBinding,
    safeString,
    safeBool,
    safeArray,
    safeObject,
  }
}
