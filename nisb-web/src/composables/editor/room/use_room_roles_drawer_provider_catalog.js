import { computed, ref } from 'vue'
import { useSettingsStore } from '../../../stores/settings'

const LOCALIZABLE_FIELDS = new Set([
  'label',
  'description',
  'title',
  'message',
  'badge',
  'name',
  'placeholder',
  'help',
])

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function normalizeUiLocale(value) {
  const raw = String(value || '').trim().replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return 'en'
}

function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback
  const text = String(value).trim()
  return text || fallback
}

function formatFallback(text, params = {}) {
  let out = safeText(text)
  for (const [key, value] of Object.entries(params || {})) {
    out = out.replaceAll(`{${key}}`, safeText(value))
  }
  return out
}

export function useRoomRolesDrawerProviderCatalog(options = {}) {
  const {
    t,
    callTool,
    room_store,
    roomId,
    roles,
    createForm,
    editForm,
    errorText,
    successText,
    clearFeedback,
    dispatchToast,
    resetCreateForm,
    resetEditForm,

    fetchProviderOptions,
    assertToolSuccess,
    getProviderOption,
    normalizeProviderOption,
    normalizeImportedProviderOption,
    buildProviderSnapshot,
    extractImportedProviderOptionsFromRoles,
    mergeProviderOptions,
    isRoomSharedCapabilityProvider,
    isImportedRemoteProvider,
    safeString,
    safeBool,
    safeArray,
    safeObject,
  } = options

  const settings = useSettingsStore()

  const providerRegistryOptions = ref([])
  const importedProviderOptions = ref([])
  const providerRegistrySummary = ref({
    total: 0,
    available: 0,
    unavailable: 0,
    auth_required: 0,
    auth_configured: 0,
    auth_missing: 0,
  })

  const importedShareRefInput = ref('')
  const importedProviderBusy = ref(false)
  const importedProviderStatusText = ref('')
  const importedProviderErrorText = ref('')

  function currentLocale() {
    return normalizeUiLocale(settings.locale || 'en')
  }

  function tr(key, fallback, params = {}) {
    if (typeof t !== 'function') return formatFallback(fallback, params)

    const translated = safeText(t(key, params))
    if (!translated || translated === key) return formatFallback(fallback, params)

    return translated
  }

  function pickI18n(value, fallback = '') {
    if (!isPlainObject(value)) return safeText(value, fallback)

    const locale = currentLocale()
    return safeText(
      value[locale] ||
        value.en ||
        value['zh-CN'] ||
        fallback
    )
  }

  function localizeI18nFields(value) {
    if (Array.isArray(value)) {
      return value.map((item) => localizeI18nFields(item))
    }

    if (!isPlainObject(value)) {
      return value
    }

    const out = {}

    for (const [key, item] of Object.entries(value)) {
      if (key.endsWith('_i18n')) {
        out[key] = item
        continue
      }

      const i18nKey = `${key}_i18n`
      if (LOCALIZABLE_FIELDS.has(key) && isPlainObject(value[i18nKey])) {
        out[key] = pickI18n(value[i18nKey], item)
        continue
      }

      out[key] = localizeI18nFields(item)
    }

    for (const [key, item] of Object.entries(value)) {
      if (!key.endsWith('_i18n') || !isPlainObject(item)) continue

      const baseKey = key.slice(0, -5)
      if (!LOCALIZABLE_FIELDS.has(baseKey)) continue
      if (out[baseKey] !== undefined && safeText(out[baseKey])) continue

      out[baseKey] = pickI18n(item)
    }

    return out
  }

  function localizeProviderOption(provider) {
    const localized = localizeI18nFields(provider)
    return localized && typeof localized === 'object' ? localized : provider
  }

  function normalizeAndLocalizeProviderOption(item) {
    const localizedRaw = localizeI18nFields(item)
    const normalized = normalizeProviderOption(localizedRaw)
    return normalized ? localizeProviderOption(normalized) : null
  }

  function normalizeAndLocalizeImportedProviderOption(item) {
    const localizedRaw = localizeI18nFields(item)
    const normalized = normalizeImportedProviderOption(localizedRaw)
    return normalized ? localizeProviderOption(normalized) : null
  }

  function localizeProviderList(list) {
    return safeArray(list)
      .map((item) => localizeProviderOption(item))
      .filter(Boolean)
  }

  const providerOptions = computed(() => {
    return mergeProviderOptions(providerRegistryOptions.value, importedProviderOptions.value)
  })

  const registryProviderCount = computed(() => {
    return safeArray(providerRegistryOptions.value).length
  })

  const importedProviderCount = computed(() => {
    return safeArray(importedProviderOptions.value).length
  })

  function isRoomSharedProvider(provider) {
    return isRoomSharedCapabilityProvider(provider)
  }

  function isImportedProvider(provider) {
    return isImportedRemoteProvider(provider)
  }

  function providerIsAvailable(provider) {
    return safeBool(provider?.availability?.available, true)
  }

  function providerNeedsAuth(provider) {
    return safeBool(provider?.auth_state?.required, false)
  }

  function providerAuthConfigured(provider) {
    if (!providerNeedsAuth(provider)) return true
    return safeBool(provider?.auth_state?.configured, false)
  }

  function providerSupportsWorkspace(provider) {
    if (isRoomSharedProvider(provider)) return false
    return safeBool(provider?.boundary_hint?.supports_workspace_context, false)
  }

  function providerSupportsFocusRoot(provider) {
    if (isRoomSharedProvider(provider)) return false
    return safeBool(provider?.boundary_hint?.supports_focus_root, false)
  }

  function providerAvailabilityReason(provider) {
    return safeString(provider?.availability?.reason)
  }

  function providerAuthType(provider) {
    return safeString(provider?.auth_state?.type).toLowerCase()
  }

  function providerAuthTypeLabel(provider) {
    const kind = providerAuthType(provider)
    if (kind === 'service_managed') return t('room.rolesDrawer.providerCatalog.authTypes.serviceManaged')
    if (kind === 'api_key') return t('room.rolesDrawer.providerCatalog.authTypes.apiKey')
    if (kind === 'oauth2') return t('room.rolesDrawer.providerCatalog.authTypes.oauth2')
    if (kind === 'none') return t('room.rolesDrawer.providerCatalog.authTypes.none')
    return t('room.rolesDrawer.providerCatalog.authTypes.unknown')
  }

  function providerRoomSourceText(provider) {
    if (!isRoomSharedProvider(provider)) return ''
    const roomSource = safeObject(provider?.room_source)
    const sharedBoundary = safeObject(roomSource?.shared_boundary)

    const parts = []
    if (safeString(roomSource.room_id)) parts.push(`source_room=${safeString(roomSource.room_id)}`)
    if (safeString(roomSource.reply_mode)) parts.push(`reply_mode=${safeString(roomSource.reply_mode)}`)
    parts.push(`shared_room_config=${safeBool(roomSource.shared_room_config_enabled, false) ? 'on' : 'off'}`)
    parts.push(`shared_supervisor=${safeBool(roomSource.shared_supervisor_enabled, false) ? 'on' : 'off'}`)
    parts.push(`owner_private_scope_exposed=${safeBool(sharedBoundary.owner_private_scope_exposed, false) ? 'true' : 'false'}`)

    if (isImportedProvider(provider)) {
      parts.unshift('provider_origin=imported_remote')
    }

    return parts.join(' · ')
  }

  function providerStatusText(provider) {
    if (!provider) return ''

    if (!providerIsAvailable(provider)) {
      return (
        safeString(provider?.availability?.message) ||
        safeString(provider?.availability?.reason) ||
        safeString(provider?.auth_state?.message) ||
        t('room.rolesDrawer.providerCatalog.unavailableDefault')
      )
    }

    if (isRoomSharedProvider(provider) && isImportedProvider(provider)) {
      return (
        safeString(provider?.boundary_hint?.message) ||
        tr(
          'room.rolesDrawer.providerCatalog.importedSharedStatus',
          'This provider was imported from a share ref. The consumer only receives the room-configured shared capability and does not gain workspace or focus-root privileges.'
        )
      )
    }

    if (isRoomSharedProvider(provider)) {
      return (
        safeString(provider?.boundary_hint?.message) ||
        tr(
          'room.rolesDrawer.providerCatalog.localSharedStatus',
          'This provider reuses the saved shared capability from the source room. The consumer does not gain workspace or focus-root privileges.'
        )
      )
    }

    if (isImportedProvider(provider)) {
      return (
        safeString(provider?.auth_state?.message) ||
        safeString(provider?.boundary_hint?.message) ||
        tr(
          'room.rolesDrawer.providerCatalog.importedProviderStatus',
          'This provider was imported from a pasted descriptor. Saving will rely on the imported snapshot instead of default registry discovery.'
        )
      )
    }

    return (
      safeString(provider?.auth_state?.message) ||
      safeString(provider?.boundary_hint?.message) ||
      safeString(provider?.availability?.message) ||
      safeString(provider?.description) ||
      t('room.rolesDrawer.providerCatalog.loadedDefault')
    )
  }

  function providerLabel(providerId, fallbackProvider = null) {
    const provider = getProviderOption(providerOptions.value, providerId) || fallbackProvider
    return safeString(provider?.label || providerId || t('room.rolesDrawer.common.noProviderSelected'))
  }

  function isSelectedForCreate(providerId) {
    return safeString(createForm?.mcp_binding?.provider_id).toLowerCase() === safeString(providerId).toLowerCase()
  }

  function clearImportedFeedback() {
    importedProviderStatusText.value = ''
    importedProviderErrorText.value = ''
  }

  function normalizeImportedProviderList(list) {
    return safeArray(list)
      .map((item) => normalizeAndLocalizeImportedProviderOption(item))
      .filter(Boolean)
  }

  function readImportedProvidersFromStore() {
    try {
      if (!roomId.value) return normalizeImportedProviderList(importedProviderOptions.value)

      if (typeof room_store.getRoomMcpImportedProviders === 'function') {
        return normalizeImportedProviderList(room_store.getRoomMcpImportedProviders(roomId.value))
      }

      const rawMap = safeObject(room_store.roomMcpImportedProvidersByRoom)
      return normalizeImportedProviderList(rawMap[roomId.value])
    } catch (_) {
      return normalizeImportedProviderList(importedProviderOptions.value)
    }
  }

  function writeImportedProvidersToStore(list) {
    const normalized = normalizeImportedProviderList(list)

    if (!roomId.value) return normalized

    try {
      if (typeof room_store.setRoomMcpImportedProviders === 'function') {
        room_store.setRoomMcpImportedProviders(roomId.value, normalized)
        return normalized
      }

      if (!safeObject(room_store.roomMcpImportedProvidersByRoom)[roomId.value]) {
        room_store.roomMcpImportedProvidersByRoom = {
          ...safeObject(room_store.roomMcpImportedProvidersByRoom),
          [roomId.value]: normalized,
        }
        return normalized
      }

      room_store.roomMcpImportedProvidersByRoom[roomId.value] = normalized
    } catch (_) {}

    return normalized
  }

  function syncImportedProviders(nextList) {
    importedProviderOptions.value = normalizeImportedProviderList(nextList)
    writeImportedProvidersToStore(importedProviderOptions.value)
    return importedProviderOptions.value
  }

  function hydrateImportedProvidersFromRoles(roleList = []) {
    const roleImported = extractImportedProviderOptionsFromRoles(roleList)
    const cachedImported = readImportedProvidersFromStore()
    const merged = mergeProviderOptions(
      cachedImported,
      mergeProviderOptions(importedProviderOptions.value, roleImported)
    )
    return syncImportedProviders(merged)
  }

  function readProviderSnapshot(provider) {
    return safeObject(provider?.provider_snapshot)
  }

  function readProviderInvokeContract(provider) {
    const snapshot = readProviderSnapshot(provider)
    return safeObject(
      provider?.invoke_contract ||
      snapshot?.invoke_contract
    )
  }

  function readProviderToolTemplates(provider, invokeContract = {}) {
    const snapshot = readProviderSnapshot(provider)
    const direct = safeArray(provider?.tool_templates)
    if (direct.length) return direct

    const contractRows = safeArray(invokeContract?.tool_templates)
    if (contractRows.length) return contractRows

    return safeArray(snapshot?.tool_templates)
  }

  function firstToolTemplate(provider, invokeContract = {}) {
    const rows = readProviderToolTemplates(provider, invokeContract)
    return rows.length ? safeObject(rows[0]) : {}
  }

  function resolveProviderBindingFields(provider) {
    const snapshot = readProviderSnapshot(provider)
    const invokeContract = readProviderInvokeContract(provider)
    const firstTool = firstToolTemplate(provider, invokeContract)

    const providerId = safeString(
      provider?.provider_id ||
      snapshot?.provider_id
    ).toLowerCase()

    const providerType = safeString(
      provider?.provider_type ||
      provider?.provider_kind ||
      snapshot?.provider_type ||
      snapshot?.provider_kind ||
      invokeContract?.provider_kind
    )

    const providerOrigin = safeString(
      provider?.provider_origin ||
      snapshot?.provider_origin
    )

    const descriptorVersion = safeString(
      provider?.descriptor_version ||
      snapshot?.descriptor_version ||
      invokeContract?.descriptor_version
    )

    const serverTool = safeString(
      provider?.server_tool ||
      snapshot?.server_tool ||
      invokeContract?.server_tool ||
      firstTool?.server_tool
    )

    const toolName = safeString(
      provider?.tool_name ||
      snapshot?.tool_name ||
      invokeContract?.tool_name ||
      firstTool?.tool_name ||
      firstTool?.name
    )

    const requestedMode = safeString(
      provider?.requested_mode ||
      snapshot?.requested_mode ||
      invokeContract?.requested_mode ||
      firstTool?.requested_mode,
      'mcp'
    )

    const mcpShareRef = safeString(
      provider?.mcp_share_ref ||
      snapshot?.mcp_share_ref ||
      provider?.share_ref
    )

    return {
      provider_id: providerId,
      provider_type: providerType,
      provider_origin: providerOrigin,
      descriptor_version: descriptorVersion,
      server_tool: serverTool,
      tool_name: toolName,
      requested_mode: requestedMode,
      mcp_share_ref: mcpShareRef,
      invoke_contract: invokeContract,
      tool_templates: readProviderToolTemplates(provider, invokeContract),
    }
  }

  function applyProviderToForm(targetForm, provider) {
    if (!provider || !targetForm) return

    const binding = resolveProviderBindingFields(provider)
    if (!binding.provider_id) return

    const snapshot = buildProviderSnapshot(provider, {
      provider_id: binding.provider_id,
      provider_type: binding.provider_type,
      provider_origin: binding.provider_origin,
      descriptor_version: binding.descriptor_version,
      server_tool: binding.server_tool,
      tool_name: binding.tool_name,
      requested_mode: binding.requested_mode,
      mcp_share_ref: binding.mcp_share_ref,
      invoke_contract: binding.invoke_contract,
      tool_templates: binding.tool_templates,
    })

    targetForm.tool_policy.mcp = true
    targetForm.mcp_binding.enabled = true
    targetForm.mcp_binding.provider_id = binding.provider_id
    targetForm.mcp_binding.provider_type = binding.provider_type
    targetForm.mcp_binding.provider_origin = binding.provider_origin
    targetForm.mcp_binding.server_tool = binding.server_tool
    targetForm.mcp_binding.tool_name = binding.tool_name
    targetForm.mcp_binding.requested_mode = binding.requested_mode
    targetForm.mcp_binding.params = {
      ...(provider.params_defaults || {}),
    }

    if (isRoomSharedProvider(provider)) {
      targetForm.mcp_binding.inherit_workspace_context = false
      targetForm.mcp_binding.inherit_focus_root = false
    } else {
      targetForm.mcp_binding.inherit_workspace_context = safeBool(
        provider?.boundary_hint?.default_inherit_workspace_context,
        false
      )
      targetForm.mcp_binding.inherit_focus_root = safeBool(
        provider?.boundary_hint?.default_inherit_focus_root,
        false
      )
    }

    const providerIds = Array.isArray(targetForm.mcp_provider_ids) ? targetForm.mcp_provider_ids : []
    targetForm.mcp_provider_ids = Array.from(new Set([...providerIds, binding.provider_id]))
    targetForm.mcp_provider_snapshot = snapshot
    targetForm.mcp_share_ref = binding.mcp_share_ref
  }

  function useProviderForCreate(providerId) {
    const provider = getProviderOption(providerOptions.value, providerId)
    if (!provider) return

    clearFeedback()
    applyProviderToForm(createForm, provider)

    successText.value = t('room.rolesDrawer.messages.providerSelected', {
      provider: provider.label || provider.provider_id,
    })
  }

  function extractProviderRegistryResult(data) {
    const root = data && typeof data === 'object' ? data : {}

    if (Array.isArray(root.providers)) {
      return root
    }

    const toolResults = Array.isArray(root.tool_results) ? root.tool_results : []
    for (const item of toolResults) {
      const type = safeString(item?.type)
      if (
        type === 'room_mcp_provider_registry' ||
        type === 'room_mcp_provider_list' ||
        type === 'room_mcp_providers'
      ) {
        return item
      }
    }

    const nestedResult = root.result && typeof root.result === 'object' ? root.result : {}
    if (Array.isArray(nestedResult.providers)) {
      return nestedResult
    }

    const nestedToolResults = Array.isArray(nestedResult.tool_results) ? nestedResult.tool_results : []
    for (const item of nestedToolResults) {
      const type = safeString(item?.type)
      if (
        type === 'room_mcp_provider_registry' ||
        type === 'room_mcp_provider_list' ||
        type === 'room_mcp_providers'
      ) {
        return item
      }
    }

    return {}
  }

  function normalizeProviderSummary(summary, providers) {
    const raw = summary && typeof summary === 'object' ? summary : {}
    const rows = Array.isArray(providers) ? providers : []

    if (
      raw.total != null ||
      raw.available != null ||
      raw.unavailable != null ||
      raw.auth_required != null ||
      raw.auth_configured != null ||
      raw.auth_missing != null
    ) {
      return {
        total: Number(raw.total || 0),
        available: Number(raw.available || 0),
        unavailable: Number(raw.unavailable || 0),
        auth_required: Number(raw.auth_required || 0),
        auth_configured: Number(raw.auth_configured || 0),
        auth_missing: Number(raw.auth_missing || 0),
      }
    }

    let available = 0
    let unavailable = 0
    let auth_required = 0
    let auth_configured = 0
    let auth_missing = 0

    for (const item of rows) {
      if (providerIsAvailable(item)) available += 1
      else unavailable += 1

      if (providerNeedsAuth(item)) {
        auth_required += 1
        if (providerAuthConfigured(item)) auth_configured += 1
        else auth_missing += 1
      }
    }

    return {
      total: rows.length,
      available,
      unavailable,
      auth_required,
      auth_configured,
      auth_missing,
    }
  }

  const providerSummary = computed(() => {
    return normalizeProviderSummary({}, providerOptions.value)
  })

  function tryParseJson(text) {
    const raw = safeString(text)
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch (_) {
      return null
    }
  }

  function unwrapResolvedImportedProvider(raw, shareRef = '') {
    const candidates = []
    const pushCandidate = (value) => {
      if (value && typeof value === 'object') {
        candidates.push(value)
      }
    }

    const root = safeObject(raw)
    const nestedResult = safeObject(root.result)
    const payload = safeObject(root.payload)

    pushCandidate(root.provider)
    pushCandidate(root.provider_snapshot)
    pushCandidate(root.imported_provider)
    pushCandidate(root.mcp_provider_snapshot)
    pushCandidate(root.resolved_provider)
    pushCandidate(root.resolved)
    pushCandidate(root.item)
    pushCandidate(root)

    pushCandidate(nestedResult.provider)
    pushCandidate(nestedResult.provider_snapshot)
    pushCandidate(nestedResult.imported_provider)
    pushCandidate(nestedResult.mcp_provider_snapshot)
    pushCandidate(nestedResult.resolved_provider)
    pushCandidate(nestedResult.resolved)
    pushCandidate(nestedResult.item)
    pushCandidate(nestedResult)

    pushCandidate(payload.provider)
    pushCandidate(payload.provider_snapshot)
    pushCandidate(payload.imported_provider)
    pushCandidate(payload.mcp_provider_snapshot)
    pushCandidate(payload)

    for (const item of [...safeArray(root.tool_results), ...safeArray(nestedResult.tool_results)]) {
      const row = safeObject(item)
      pushCandidate(row.provider)
      pushCandidate(row.provider_snapshot)
      pushCandidate(row.imported_provider)
      pushCandidate(row.mcp_provider_snapshot)
      pushCandidate(row.resolved_provider)
      pushCandidate(row.resolved)
      pushCandidate(row)
    }

    for (const candidate of candidates) {
      const localizedCandidate = localizeI18nFields(candidate)

      const normalized =
        normalizeAndLocalizeImportedProviderOption({
          ...safeObject(localizedCandidate),
          mcp_share_ref: safeString(
            localizedCandidate?.mcp_share_ref ||
            localizedCandidate?.share_ref ||
            shareRef
          ),
        }) ||
        normalizeAndLocalizeImportedProviderOption({
          provider_snapshot: localizedCandidate,
          mcp_share_ref: shareRef,
        })

      if (normalized) return normalized
    }

    return null
  }

  async function resolveImportedProviderFromText(text) {
    const shareRef = safeString(text)
    if (!shareRef) {
      throw new Error(
        tr(
          'room.rolesDrawer.messages.pasteShareRefFirst',
          'Paste a share ref or provider descriptor first.'
        )
      )
    }

    let lastError = null

    if (typeof room_store.resolveRoomMcpShareRef === 'function') {
      try {
        const resolved = await room_store.resolveRoomMcpShareRef(callTool, shareRef, {
          room_id: roomId.value || '',
          locale: settings.locale || 'en',
        })
        const normalized = unwrapResolvedImportedProvider(resolved, shareRef)
        if (normalized) return normalized
      } catch (e) {
        lastError = e
      }
    }

    const parsed = tryParseJson(shareRef)
    if (parsed && typeof parsed === 'object') {
      const localNormalized = unwrapResolvedImportedProvider(parsed, shareRef)
      if (localNormalized) return localNormalized
    }

    for (const toolName of ['nisb_room_mcp_share_ref_resolve', 'nisb_room_mcp_provider_share_ref_resolve']) {
      try {
        const data = assertToolSuccess(await callTool(toolName, {
          room_id: roomId.value || '',
          share_ref: shareRef,
          locale: settings.locale || 'en',
        }))
        const normalized = unwrapResolvedImportedProvider(data, shareRef)
        if (normalized) return normalized
      } catch (e) {
        lastError = e
      }
    }

    throw lastError || new Error(
      tr(
        'room.rolesDrawer.messages.shareRefResolveFailed',
        'The current share ref cannot be resolved as an imported provider.'
      )
    )
  }

  function addImportedProvider(provider) {
    const normalized = normalizeAndLocalizeImportedProviderOption(provider)
    if (!normalized) return null

    const merged = mergeProviderOptions(importedProviderOptions.value, [normalized])
    syncImportedProviders(merged)
    return getProviderOption(importedProviderOptions.value, normalized.provider_id) || normalized
  }

  function removeImportedProvider(providerId) {
    const pid = safeString(providerId).toLowerCase()
    if (!pid) return

    syncImportedProviders(
      safeArray(importedProviderOptions.value).filter(
        (item) => safeString(item?.provider_id).toLowerCase() !== pid
      )
    )

    if (
      safeString(createForm?.mcp_binding?.provider_id).toLowerCase() === pid &&
      !getProviderOption(providerRegistryOptions.value, pid)
    ) {
      resetCreateForm()
    }

    if (
      safeString(editForm?.mcp_binding?.provider_id).toLowerCase() === pid &&
      !getProviderOption(providerRegistryOptions.value, pid)
    ) {
      resetEditForm()
    }

    clearImportedFeedback()
    importedProviderStatusText.value = tr(
      'room.rolesDrawer.messages.importedProviderRemoved',
      'Removed this provider from the local imported provider list.'
    )
  }

  function clearImportedProviders() {
    syncImportedProviders([])
    clearImportedFeedback()
    importedProviderStatusText.value = tr(
      'room.rolesDrawer.messages.importedProvidersCleared',
      'Cleared the imported provider list for the current room.'
    )
  }

  function clearImportedProviderInput() {
    importedShareRefInput.value = ''
    clearImportedFeedback()
  }

  async function importRemoteProviderFromPaste() {
    const text = safeString(importedShareRefInput.value)
    if (!text) {
      importedProviderErrorText.value = tr(
        'room.rolesDrawer.messages.pasteShareRefFirst',
        'Paste a share ref or provider descriptor first.'
      )
      return
    }

    importedProviderBusy.value = true
    clearImportedFeedback()
    clearFeedback()

    try {
      const provider = await resolveImportedProviderFromText(text)
      const imported = addImportedProvider(provider)
      if (!imported) {
        throw new Error(
          tr(
            'room.rolesDrawer.messages.importedProviderInvalid',
            'The share ref was resolved, but no valid imported provider was produced.'
          )
        )
      }

      applyProviderToForm(createForm, imported)

      importedProviderStatusText.value = tr(
        'room.rolesDrawer.messages.importedProviderImported',
        'Imported provider: {provider}',
        { provider: safeString(imported.label || imported.provider_id) }
      )
      successText.value = tr(
        'room.rolesDrawer.messages.importedProviderSelectedForCreate',
        'Imported provider was added to the catalog and selected for role creation: {provider}',
        { provider: safeString(imported.label || imported.provider_id) }
      )
      dispatchToast(successText.value, 'success')
    } catch (e) {
      importedProviderErrorText.value = String(
        e?.message ||
          e ||
          tr('room.rolesDrawer.messages.importShareRefFailed', 'Failed to import share ref.')
      )
      dispatchToast(importedProviderErrorText.value, 'error')
    } finally {
      importedProviderBusy.value = false
    }
  }

  async function refreshProviderRegistry() {
    clearFeedback()
    clearImportedFeedback()

    try {
      const data = assertToolSuccess(await callTool('nisb_room_mcp_provider_list', {
        room_id: roomId.value || '',
        locale: settings.locale || 'en',
      }))

      const registry = extractProviderRegistryResult(data)
      const rawProviders = Array.isArray(registry?.providers) ? registry.providers : []

      let normalizedProviders = rawProviders
        .map((item) => normalizeAndLocalizeProviderOption(item))
        .filter(Boolean)

      if (!normalizedProviders.length) {
        normalizedProviders = localizeProviderList(await fetchProviderOptions(callTool))
      }

      providerRegistryOptions.value = normalizedProviders
      providerRegistrySummary.value = normalizeProviderSummary(registry?.summary, normalizedProviders)

      const cachedImported = readImportedProvidersFromStore()
      const roleImported = extractImportedProviderOptionsFromRoles(roles.value)
      syncImportedProviders(
        mergeProviderOptions(
          cachedImported,
          mergeProviderOptions(importedProviderOptions.value, roleImported)
        )
      )

      if (!providerOptions.value.length) {
        successText.value = ''
      }
    } catch (e) {
      try {
        const fallbackProviders = localizeProviderList(await fetchProviderOptions(callTool))
        providerRegistryOptions.value = fallbackProviders
        providerRegistrySummary.value = normalizeProviderSummary({}, fallbackProviders)

        const cachedImported = readImportedProvidersFromStore()
        const roleImported = extractImportedProviderOptionsFromRoles(roles.value)
        syncImportedProviders(
          mergeProviderOptions(
            cachedImported,
            mergeProviderOptions(importedProviderOptions.value, roleImported)
          )
        )

        errorText.value = String(e?.message || e || t('room.rolesDrawer.messages.loadProviderRegistryFailed'))
        dispatchToast(errorText.value, 'error')
      } catch (inner) {
        providerRegistryOptions.value = []
        syncImportedProviders(importedProviderOptions.value)
        providerRegistrySummary.value = {
          total: 0,
          available: 0,
          unavailable: 0,
          auth_required: 0,
          auth_configured: 0,
          auth_missing: 0,
        }
        errorText.value = String(inner?.message || e || t('room.rolesDrawer.messages.loadProviderRegistryFailed'))
        dispatchToast(errorText.value, 'error')
      }
    }
  }

  return {
    providerRegistryOptions,
    importedProviderOptions,
    providerRegistrySummary,
    importedShareRefInput,
    importedProviderBusy,
    importedProviderStatusText,
    importedProviderErrorText,
    providerOptions,
    registryProviderCount,
    importedProviderCount,
    providerSummary,

    clearImportedFeedback,
    readImportedProvidersFromStore,
    syncImportedProviders,
    hydrateImportedProvidersFromRoles,

    isRoomSharedProvider,
    isImportedProvider,
    providerIsAvailable,
    providerNeedsAuth,
    providerAuthConfigured,
    providerSupportsWorkspace,
    providerSupportsFocusRoot,
    providerAvailabilityReason,
    providerAuthTypeLabel,
    providerRoomSourceText,
    providerStatusText,
    providerLabel,
    isSelectedForCreate,
    applyProviderToForm,

    removeImportedProvider,
    clearImportedProviders,
    clearImportedProviderInput,
    importRemoteProviderFromPaste,
    refreshProviderRegistry,
    useProviderForCreate,
  }
}
