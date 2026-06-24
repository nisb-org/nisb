import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../../../composables/useMCP'
import { useChatConfigStore } from '../../../../../stores/chatConfig'
import { useRoomStore } from '../../../../../stores/room'
import {
  safeObject,
  safeArray,
  safeString,
  pickPayload,
  isSuccessLike,
  normalizeFedErrorMeta,
  buildInviteErrorMessage,
  buildInviteHint,
  buildPeerHealthLabel,
  buildAcceptSuccessMessage,
  maskInviteToken,
  normalizeBaseUrl,
  parseFederationInfo,
  buildDraftKey,
  stripCodeFence,
} from './fedMenuShared'

export function useFedMenu(props = {}) {
  const { t } = useI18n()
  const { callTool } = useMCP()
  const chatCfg = useChatConfigStore()
  const roomStore = useRoomStore()

  const wrapRef = ref(null)
  const btnRef = ref(null)

  const open = ref(false)
  const panelStyle = ref({ left: '0px', top: '0px' })

  const loadingPeers = ref(false)
  const peers = ref([])

  const saving = ref(false)
  const copyingFederationInfo = ref(false)
  const err = ref('')
  const ok = ref('')
  const form = ref({ peer_id: '', base_url: '', token: '', label: '' })

  const pasteText = ref('')
  const pasteErr = ref('')
  const pasteOk = ref('')
  const pasteHint = ref('')
  const importingPaste = ref(false)
  const importedInviteEntries = ref([])

  const checkingHealth = ref(false)
  const peerHealthMap = ref({})

  const acceptingInvite = ref(false)
  const inviteErr = ref('')
  const inviteOk = ref('')
  const inviteHint = ref('')
  const closePanelTimer = ref(null)
  const lastInviteAttempt = ref(null)
  const inviteForm = ref({
    peer_id: '',
    room_id: '',
    invite_token: '',
    remote_user_id: '',
    remote_label: '',
    target_peer_id: '',
  })

  const marketEnabled = computed(() => !!chatCfg?.rag?.external?.marketEnabled)
  const enabledPeers = computed(() => peers.value.filter((p) => p && p.enabled !== false))
  const canRetryInvite = computed(() => !!safeObject(lastInviteAttempt.value).peer_id)

  function clearClosePanelTimer() {
    if (closePanelTimer.value) {
      window.clearTimeout(closePanelTimer.value)
      closePanelTimer.value = null
    }
  }

  function scheduleClosePanel(delay = 1800) {
    clearClosePanelTimer()
    closePanelTimer.value = window.setTimeout(() => {
      closePanel()
    }, Math.max(0, Number(delay) || 0))
  }

  function positionPanel() {
    const el = btnRef.value
    if (!el) return

    const rect = el.getBoundingClientRect()

    panelStyle.value = {
      left: `${Math.max(8, rect.left)}px`,
      top: `${Math.max(8, rect.bottom + 8)}px`,
    }

    nextTick(() => {
      const panel = wrapRef.value?.querySelector('.fed-panel')
      if (!panel) return

      const gap = 8
      const vw = window.innerWidth || 1280
      const vh = window.innerHeight || 800
      const pw = panel.offsetWidth || 340
      const ph = panel.offsetHeight || 360

      let left = rect.left
      if (left + pw > vw - gap) left = Math.max(gap, vw - gap - pw)
      if (left < gap) left = gap

      let top = rect.top - ph - 8
      if (top < gap) top = rect.bottom + 8
      if (top + ph > vh - gap) top = Math.max(gap, vh - gap - ph)

      panelStyle.value = {
        left: `${left}px`,
        top: `${top}px`,
      }
    })
  }

  function toggle() {
    if (props.disabled) return
    open.value = !open.value
    if (open.value) {
      positionPanel()
      if (peers.value.length === 0) loadPeers()
    } else {
      clearClosePanelTimer()
    }
  }

  function closePanel() {
    clearClosePanelTimer()
    open.value = false
  }

  function onGlobalClick(e) {
    const target = e?.target
    const root = target?.closest?.('.fed-wrapper')
    if (!root) closePanel()
  }

  function onResize() {
    if (open.value) positionPanel()
  }

  function onKeydown(e) {
    if (e.key === 'Escape') closePanel()
  }

  function onToggleMarket(e) {
    chatCfg.setMarketEnabled(!!e.target.checked)
  }

  function peerSelected(peerId) {
    const list = Array.isArray(chatCfg?.rag?.external?.peerTargets) ? chatCfg.rag.external.peerTargets : []
    return list.includes(peerId)
  }

  function togglePeer(peerId) {
    chatCfg.togglePeerTarget(peerId)
  }

  function setPeerHealth(peerId, code, message = '') {
    const pid = safeString(peerId).trim()
    if (!pid) return
    const meta = buildPeerHealthLabel(code, t)
    peerHealthMap.value = {
      ...peerHealthMap.value,
      [pid]: {
        status: meta.status,
        label: meta.label,
        message: message || '',
        error_code: code || '',
        updated_at: Date.now(),
      },
    }
  }

  function normalizeInviteDraft(row = {}) {
    const src = safeObject(row)
    return {
      _draft_key: buildDraftKey(src),
      peer_id: safeString(src.peer_id).trim(),
      room_id: safeString(src.room_id).trim(),
      invite_token: safeString(src.invite_token).trim(),
      remote_user_id: safeString(src.remote_user_id).trim(),
      remote_label: safeString(src.remote_label).trim(),
      target_peer_id: safeString(src.target_peer_id).trim(),
    }
  }

  function findImportedInviteMatch(roomId = '', inviteToken = '') {
    const rid = safeString(roomId).trim()
    const token = safeString(inviteToken).trim()
    if (!rid && !token) return {}

    return safeArray(importedInviteEntries.value).find((item) => {
      const row = safeObject(item)
      const sameRoom = !rid || safeString(row.room_id).trim() === rid
      const sameToken = !token || safeString(row.invite_token).trim() === token
      return sameRoom && sameToken
    }) || {}
  }

  function resolveInviteTargetPeerId() {
    const current = safeString(inviteForm.value.target_peer_id).trim()
    if (current) return current

    const matchedImported = safeObject(
      findImportedInviteMatch(inviteForm.value.room_id, inviteForm.value.invite_token)
    )
    const importedTarget = safeString(matchedImported.target_peer_id).trim()
    if (importedTarget) return importedTarget

    const latestImported = safeObject(safeArray(importedInviteEntries.value)[0])
    const latestImportedTarget = safeString(latestImported.target_peer_id).trim()
    if (latestImportedTarget) return latestImportedTarget

    const last = safeObject(lastInviteAttempt.value)
    const lastTarget = safeString(last.target_peer_id).trim()
    if (lastTarget) return lastTarget

    return ''
  }

  function ensureInvitePeerId(candidate = '') {
    const normalizedCandidate = safeString(candidate).trim()
    if (normalizedCandidate) {
      inviteForm.value.peer_id = normalizedCandidate
      return normalizedCandidate
    }

    const current = safeString(inviteForm.value.peer_id).trim()
    if (current) return current

    const formPeerId = safeString(form.value.peer_id).trim()
    if (formPeerId) {
      inviteForm.value.peer_id = formPeerId
      return formPeerId
    }

    const firstEnabled = safeArray(peers.value).find((p) => p && p.enabled !== false && safeString(p.peer_id).trim())
    if (firstEnabled?.peer_id) {
      inviteForm.value.peer_id = safeString(firstEnabled.peer_id).trim()
      return inviteForm.value.peer_id
    }

    return ''
  }

  function applyPeerToForm(peer) {
    const row = safeObject(peer)
    const peerId = safeString(row.peer_id).trim()

    form.value.peer_id = peerId
    form.value.base_url = safeString(row.base_url)
    form.value.token = safeString(row.token)
    form.value.label = safeString(row.label)

    ensureInvitePeerId(peerId)
  }

  function applyParsedToForms(parsed = {}) {
    const row = safeObject(parsed)

    if (row.peer_id) form.value.peer_id = safeString(row.peer_id)
    if (row.base_url) form.value.base_url = normalizeBaseUrl(row.base_url)
    if (row.token) form.value.token = safeString(row.token)
    if (row.label || row.remote_label) form.value.label = safeString(row.label || row.remote_label)

    if (row.peer_id) inviteForm.value.peer_id = safeString(row.peer_id)
    if (row.room_id) inviteForm.value.room_id = safeString(row.room_id)
    if (row.invite_token) inviteForm.value.invite_token = safeString(row.invite_token)
    if (row.remote_user_id) inviteForm.value.remote_user_id = safeString(row.remote_user_id)
    if (row.remote_label) inviteForm.value.remote_label = safeString(row.remote_label)
    if (row.target_peer_id) inviteForm.value.target_peer_id = safeString(row.target_peer_id)

    ensureInvitePeerId(row.peer_id)
  }

  function upsertImportedInvite(row = {}) {
    const next = normalizeInviteDraft(row)
    if (!next.room_id && !next.invite_token) return
    if (!next.peer_id) {
      next.peer_id = ensureInvitePeerId('')
    }
    const list = safeArray(importedInviteEntries.value).filter((item) => item && item._draft_key !== next._draft_key)
    importedInviteEntries.value = [next, ...list].slice(0, 8)
  }

  function removeImportedInvite(key = '') {
    const k = safeString(key).trim()
    importedInviteEntries.value = safeArray(importedInviteEntries.value).filter((item) => item?._draft_key !== k)
  }

  function applyImportedInvite(row = {}) {
    const src = normalizeInviteDraft(row)
    if (src.peer_id) inviteForm.value.peer_id = src.peer_id
    if (src.room_id) inviteForm.value.room_id = src.room_id
    if (src.invite_token) inviteForm.value.invite_token = src.invite_token
    if (src.remote_user_id) inviteForm.value.remote_user_id = src.remote_user_id
    if (src.remote_label) inviteForm.value.remote_label = src.remote_label
    if (src.target_peer_id) inviteForm.value.target_peer_id = src.target_peer_id
    ensureInvitePeerId(src.peer_id)
  }

  function readStorageItem(storage, key) {
    try {
      return safeString(storage?.getItem?.(key)).trim()
    } catch (_) {
      return ''
    }
  }

  function extractTokenFromUnknown(value, depth = 0) {
    if (depth > 4) return ''

    if (typeof value === 'string') {
      const raw = safeString(value).trim()
      if (!raw || raw === 'undefined' || raw === 'null') return ''

      const bearer = raw.match(/Bearer\s+([A-Za-z0-9._-]+)/i)
      if (bearer?.[1]) return bearer[1].trim()

      const direct = raw.match(/\bnisb_[A-Za-z0-9._-]+\b/)
      if (direct?.[0]) return direct[0].trim()

      if ((raw.startsWith('{') && raw.endsWith('}')) || (raw.startsWith('[') && raw.endsWith(']'))) {
        try {
          return extractTokenFromUnknown(JSON.parse(raw), depth + 1)
        } catch (_) {
          return ''
        }
      }

      return ''
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        const hit = extractTokenFromUnknown(item, depth + 1)
        if (hit) return hit
      }
      return ''
    }

    if (value && typeof value === 'object') {
      const src = value
      const directKeys = [
        'token',
        'access_token',
        'accessToken',
        'auth_token',
        'authToken',
        'authorization',
        'Authorization',
        'bearer',
      ]
      for (const key of directKeys) {
        const hit = extractTokenFromUnknown(src[key], depth + 1)
        if (hit) return hit
      }
      for (const item of Object.values(src)) {
        const hit = extractTokenFromUnknown(item, depth + 1)
        if (hit) return hit
      }
    }

    return ''
  }

  function readAuthTokenFromStorage(storage) {
    const directKeys = [
      'nisb_token',
      'nisb-token',
      'nisb_access_token',
      'access_token',
      'accessToken',
      'token',
      'Authorization',
      'authorization',
      'auth',
      'user',
      'session',
      'nisb_auth',
      'nisb_user',
    ]

    for (const key of directKeys) {
      const value = readStorageItem(storage, key)
      const token = extractTokenFromUnknown(value)
      if (token) return token
    }

    try {
      const len = Number(storage?.length || 0)
      for (let i = 0; i < len; i += 1) {
        const key = storage.key(i)
        const value = readStorageItem(storage, key)
        const token = extractTokenFromUnknown(value)
        if (token) return token
      }
    } catch (_) {
      // Ignore storage enumeration errors.
    }

    return ''
  }

  function readLocalAuthToken() {
    return (
      readAuthTokenFromStorage(window?.localStorage) ||
      readAuthTokenFromStorage(window?.sessionStorage) ||
      ''
    )
  }

  function readPeerIdFromStorage(storage) {
    const directKeys = [
      'nisb_peer_id',
      'peer_id',
      'local_peer_id',
      'owner_peer_id',
      'nisb_owner_peer_id',
    ]

    for (const key of directKeys) {
      const value = readStorageItem(storage, key)
      if (value && value !== 'undefined' && value !== 'null') return value
    }

    return ''
  }

  function readLocalPeerId() {
    return (
      safeString(form.value.peer_id).trim() ||
      readPeerIdFromStorage(window?.localStorage) ||
      readPeerIdFromStorage(window?.sessionStorage) ||
      ''
    )
  }

  function readCurrentBaseUrl() {
    return normalizeBaseUrl(
      window?.location?.origin ||
      form.value.base_url ||
      ''
    )
  }

  function resolveInviteCopyContext() {
    const current = safeObject(inviteForm.value)
    const imported = safeObject(
      findImportedInviteMatch(current.room_id, current.invite_token)
    )
    const latestImported = safeObject(safeArray(importedInviteEntries.value)[0])
    const last = safeObject(lastInviteAttempt.value)

    return {
      room_id: safeString(current.room_id || imported.room_id || latestImported.room_id || last.room_id).trim(),
      invite_token: safeString(current.invite_token || imported.invite_token || latestImported.invite_token || last.invite_token).trim(),
      remote_user_id: safeString(current.remote_user_id || imported.remote_user_id || latestImported.remote_user_id || last.remote_user_id).trim(),
      remote_label: safeString(current.remote_label || imported.remote_label || latestImported.remote_label || last.remote_label).trim(),
      target_peer_id: safeString(
        current.target_peer_id ||
        imported.target_peer_id ||
        latestImported.target_peer_id ||
        last.target_peer_id
      ).trim(),
    }
  }

  async function copyTextToClipboard(text = '') {
    const value = safeString(text)
    if (!value) throw new Error(t('chat.fedMenu.runtime.copyEmptyText'))

    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return
    }

    const ta = document.createElement('textarea')
    ta.value = value
    ta.setAttribute('readonly', 'readonly')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    ta.style.pointerEvents = 'none'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()

    try {
      const ok = document.execCommand('copy')
      if (!ok) throw new Error(t('chat.fedMenu.runtime.copyFailed'))
    } finally {
      document.body.removeChild(ta)
    }
  }

  function buildFederationInfoText() {
    const peer_id = readLocalPeerId()
    const base_url = readCurrentBaseUrl()
    const token = readLocalAuthToken() || safeString(form.value.token).trim()
    const label = safeString(form.value.label).trim()

    const inviteCtx = resolveInviteCopyContext()
    const room_id = inviteCtx.room_id
    const invite_token = inviteCtx.invite_token
    const remote_user_id = inviteCtx.remote_user_id
    const remote_label = inviteCtx.remote_label
    const target_peer_id = inviteCtx.target_peer_id

    if (!peer_id) {
      throw new Error(t('chat.fedMenu.runtime.copyMissingPeerId'))
    }

    if (!base_url) {
      throw new Error(t('chat.fedMenu.runtime.copyMissingBaseUrl'))
    }

    if (!token) {
      throw new Error(t('chat.fedMenu.runtime.copyMissingToken'))
    }

    form.value.peer_id = peer_id
    form.value.base_url = base_url
    if (!safeString(form.value.token).trim() && token) {
      form.value.token = token
    }

    const lines = [
      `peer_id: ${peer_id}`,
      `base_url: ${base_url}`,
      `token: ${token}`,
    ]

    if (label) lines.push(`label: ${label}`)
    if (remote_user_id) {
      lines.push(`remote_user_id: ${remote_user_id}`)
      lines.push(`owner_user_id: ${remote_user_id}`)
    }
    if (remote_label) lines.push(`remote_label: ${remote_label}`)
    if (room_id) lines.push(`room_id: ${room_id}`)
    if (invite_token) lines.push(`invite_token: ${invite_token}`)
    if (target_peer_id) lines.push(`target_peer_id: ${target_peer_id}`)

    return lines.join('\n')
  }

  async function copyFederationInfo() {
    err.value = ''
    ok.value = ''
    copyingFederationInfo.value = true
    try {
      const text = buildFederationInfoText()
      await copyTextToClipboard(text)
      ok.value = t('chat.fedMenu.runtime.copyInfoOk')
    } catch (e) {
      err.value = e?.message || String(e)
    } finally {
      copyingFederationInfo.value = false
      if (open.value) positionPanel()
    }
  }

  async function loadPeers() {
    loadingPeers.value = true
    err.value = ''
    inviteErr.value = ''
    inviteHint.value = ''
    try {
      const res = await callTool('nisb_fed_list_peers', {})
      const payload = pickPayload(res)
      peers.value = Array.isArray(payload?.peers) ? payload.peers : Array.isArray(res?.peers) ? res.peers : []
      ensureInvitePeerId('')
    } catch (e) {
      err.value = e?.message || String(e)
      peers.value = []
    } finally {
      loadingPeers.value = false
      if (open.value) positionPanel()
    }
  }

  async function savePeerPayload(payload = {}) {
    const src = safeObject(payload)
    const peer_id = safeString(src.peer_id).trim()
    const base_url = normalizeBaseUrl(src.base_url)
    const token = safeString(src.token).trim()
    const label = safeString(src.label).trim()

    if (!peer_id || !base_url) {
      throw new Error(t('chat.fedMenu.runtime.requiredPeerBaseUrl'))
    }

    const res = await callTool('nisb_fed_add_peer', {
      peer_id,
      base_url,
      peer_token: token,
      enabled: true,
      label,
    })

    const body = pickPayload(res)
    if (!isSuccessLike(res)) {
      throw new Error(body?.message || res?.message || t('chat.fedMenu.runtime.savePeerFailed'))
    }

    await loadPeers()
    ensureInvitePeerId(peer_id)
    return { res, peer_id, base_url, token, label }
  }

  async function savePeer() {
    err.value = ''
    ok.value = ''

    const peer_id = safeString(form.value.peer_id).trim()
    const base_url = safeString(form.value.base_url).trim()
    const token = safeString(form.value.token).trim()
    const label = safeString(form.value.label).trim()

    if (!peer_id || !base_url) {
      err.value = t('chat.fedMenu.runtime.requiredPeerBaseUrl')
      return
    }

    saving.value = true
    try {
      await savePeerPayload({ peer_id, base_url, token, label })
      const savedPeerId = peer_id
      ok.value = t('chat.fedMenu.runtime.peerSaved')
      form.value = { peer_id: '', base_url: '', token: '', label: '' }
      ensureInvitePeerId(savedPeerId)
      if (safeObject(lastInviteAttempt.value).peer_id === savedPeerId) {
        ok.value = t('chat.fedMenu.runtime.peerSavedRetryReady')
      }
    } catch (e) {
      err.value = e?.message || String(e)
    } finally {
      saving.value = false
      if (open.value) positionPanel()
    }
  }

  async function pasteFromClipboard() {
    pasteErr.value = ''
    pasteOk.value = ''
    pasteHint.value = ''

    if (!navigator?.clipboard?.readText) {
      pasteErr.value = t('chat.fedMenu.runtime.clipboardNotSupported')
      return
    }

    importingPaste.value = true
    try {
      const text = await navigator.clipboard.readText()
      pasteText.value = safeString(text)
      if (!pasteText.value.trim()) {
        pasteErr.value = t('chat.fedMenu.runtime.clipboardEmpty')
        return
      }
      await importFederationInfo()
    } catch (e) {
      pasteErr.value = e?.message || t('chat.fedMenu.runtime.clipboardReadFailed')
    } finally {
      importingPaste.value = false
      if (open.value) positionPanel()
    }
  }

  async function importFederationInfo() {
    pasteErr.value = ''
    pasteOk.value = ''
    pasteHint.value = ''
    err.value = ''
    ok.value = ''
    inviteErr.value = ''
    inviteOk.value = ''
    inviteHint.value = ''

    const raw = stripCodeFence(pasteText.value)
    if (!raw) {
      pasteErr.value = t('chat.fedMenu.runtime.pasteRequired')
      return
    }

    importingPaste.value = true
    try {
      const parsed = safeObject(parseFederationInfo(raw))
      const parsedPeerId = safeString(parsed.peer_id).trim()
      const parsedBaseUrl = normalizeBaseUrl(parsed.base_url)
      const parsedToken = safeString(parsed.token).trim()
      const parsedLabel = safeString(parsed.label || parsed.remote_label).trim()
      const parsedRoomId = safeString(parsed.room_id).trim()
      const parsedInviteToken = safeString(parsed.invite_token).trim()
      const parsedRemoteUserId = safeString(parsed.remote_user_id).trim()
      const parsedRemoteLabel = safeString(parsed.remote_label).trim()
      const parsedTargetPeerId = safeString(parsed.target_peer_id).trim()

      const hasPeerCore = !!(parsedPeerId && parsedBaseUrl)
      const hasInviteCore = !!(parsedRoomId && parsedInviteToken)
      const hasAnyUseful = !!(
        parsedPeerId ||
        parsedBaseUrl ||
        parsedToken ||
        parsedLabel ||
        parsedRoomId ||
        parsedInviteToken ||
        parsedRemoteUserId ||
        parsedRemoteLabel ||
        parsedTargetPeerId
      )

      if (!hasAnyUseful) {
        pasteErr.value = t('chat.fedMenu.runtime.noImportableFields')
        return
      }

      applyParsedToForms({
        peer_id: parsedPeerId,
        base_url: parsedBaseUrl,
        token: parsedToken,
        label: parsedLabel,
        room_id: parsedRoomId,
        invite_token: parsedInviteToken,
        remote_user_id: parsedRemoteUserId,
        remote_label: parsedRemoteLabel,
        target_peer_id: parsedTargetPeerId,
      })

      let savedPeer = false
      if (hasPeerCore) {
        await savePeerPayload({
          peer_id: parsedPeerId,
          base_url: parsedBaseUrl,
          token: parsedToken,
          label: parsedLabel,
        })
        savedPeer = true
      }

      const effectivePeerId = ensureInvitePeerId(parsedPeerId)

      if (hasInviteCore) {
        const draft = {
          peer_id: effectivePeerId,
          room_id: parsedRoomId,
          invite_token: parsedInviteToken,
          remote_user_id: parsedRemoteUserId,
          remote_label: parsedRemoteLabel,
          target_peer_id: parsedTargetPeerId,
        }
        upsertImportedInvite(draft)
        applyImportedInvite(draft)
      }

      const messages = []
      if (savedPeer) messages.push(t('chat.fedMenu.runtime.peerSavedUpdated', { peerId: parsedPeerId }))
      if (hasInviteCore) messages.push(t('chat.fedMenu.runtime.inviteDraftImported'))
      if (!savedPeer && (parsedPeerId || parsedBaseUrl || parsedToken || parsedLabel)) {
        messages.push(t('chat.fedMenu.runtime.peerFormFilled'))
      }
      if (!hasInviteCore && (parsedRoomId || parsedInviteToken || parsedRemoteUserId || parsedRemoteLabel || parsedTargetPeerId)) {
        messages.push(t('chat.fedMenu.runtime.inviteFormFilled'))
      }
      if (!messages.length) messages.push(t('chat.fedMenu.runtime.federationInfoParsed'))

      pasteOk.value = messages.join(t('chat.fedMenu.runtime.messageSeparator'))

      if (!parsedPeerId && parsedBaseUrl && parsedToken) {
        pasteHint.value = t('chat.fedMenu.runtime.missingPeerIdHint')
      } else if (savedPeer && hasInviteCore) {
        pasteHint.value = parsedTargetPeerId
          ? t('chat.fedMenu.runtime.peerInviteReadyWithTarget')
          : t('chat.fedMenu.runtime.peerInviteReadyMissingTarget')
      } else if (savedPeer) {
        pasteHint.value = t('chat.fedMenu.runtime.peerReadyAwaitInvite')
      } else if (hasInviteCore) {
        pasteHint.value = parsedTargetPeerId
          ? t('chat.fedMenu.runtime.inviteReadyWithTarget')
          : t('chat.fedMenu.runtime.inviteReadyMissingTarget')
      }
    } catch (e) {
      pasteErr.value = e?.message || String(e)
    } finally {
      importingPaste.value = false
      if (open.value) positionPanel()
    }
  }

  async function checkPeerHealth(peerIdInput) {
    const peer_id = safeString(peerIdInput).trim()
    if (!peer_id) return

    checkingHealth.value = true
    inviteErr.value = ''
    inviteHint.value = ''
    err.value = ''
    ok.value = ''

    setPeerHealth(peer_id, 'checking', t('chat.fedMenu.health.checking'))

    try {
      const res = await callTool('nisb_fed_peer_health_check', {
        peer_id,
        timeout_ms: 5000,
      })

      if (isSuccessLike(res)) {
        setPeerHealth(peer_id, 'ok', t('chat.fedMenu.health.ok'))
        ok.value = t('chat.fedMenu.runtime.peerHealthOk', { peerId: peer_id })
        return
      }

      const meta = normalizeFedErrorMeta(res)
      setPeerHealth(peer_id, meta.error_code || 'unknown', meta.user_message || '')
      err.value = meta.user_message || t('chat.fedMenu.runtime.peerHealthFailed', { peerId: peer_id })
    } catch (e) {
      const meta = normalizeFedErrorMeta(e)
      setPeerHealth(peer_id, meta.error_code || 'unknown', meta.user_message || '')
      err.value = meta.user_message || e?.message || t('chat.fedMenu.runtime.peerHealthFailed', { peerId: peer_id })
    } finally {
      checkingHealth.value = false
      if (open.value) positionPanel()
    }
  }

  async function enterRoomAfterFederationAccept(roomId, peerId, remoteUserId, remoteLabel, ownerRoomId = '') {
    const rid = safeString(roomId).trim()
    if (!rid) throw new Error(t('chat.fedMenu.runtime.missingRoomId'))

    const ownerRid = safeString(ownerRoomId).trim()

    roomStore.setFederationRoomSession({
      enabled: true,
      peer_id: safeString(peerId).trim(),
      room_id: rid,
      owner_room_id: ownerRid || rid,
      remote_user_id: safeString(remoteUserId).trim(),
      remote_label: safeString(remoteLabel).trim(),
    })

    chatCfg.enterRoom(rid)
    roomStore.setRoomId(rid)
    await roomStore.loadRoomBundle(callTool, rid)
  }

  async function acceptRoomInvite() {
    inviteErr.value = ''
    inviteOk.value = ''
    inviteHint.value = ''
    clearClosePanelTimer()

    const peer_id = safeString(inviteForm.value.peer_id).trim()
    const room_id = safeString(inviteForm.value.room_id).trim()
    const invite_token = safeString(inviteForm.value.invite_token).trim()
    const remote_user_id = safeString(inviteForm.value.remote_user_id).trim()
    const remote_label = safeString(inviteForm.value.remote_label).trim()
    const resolvedTargetPeerId = resolveInviteTargetPeerId()

    if (!peer_id || !room_id || !invite_token || !remote_user_id) {
      inviteErr.value = t('chat.fedMenu.runtime.requiredInviteFields')
      return
    }

    lastInviteAttempt.value = {
      peer_id,
      room_id,
      invite_token,
      remote_user_id,
      remote_label,
      target_peer_id: resolvedTargetPeerId,
    }

    acceptingInvite.value = true
    try {
      const payload = {
        peer_id,
        room_id,
        invite_token,
        remote_user_id,
        user_id: remote_user_id,
        remote_label,
      }

      if (resolvedTargetPeerId) {
        payload.target_peer_id = resolvedTargetPeerId
      }

      const res = await callTool('nisb_fed_accept_room_invite', payload)

      const body = pickPayload(res)
      if (!isSuccessLike(res)) {
        inviteErr.value = buildInviteErrorMessage(res, t)
        inviteHint.value = buildInviteHint(res, t)
        return
      }

      const result = safeObject(body.result)
      const joinResult = safeObject(result.join_result)

      const finalRoomId = safeString(
        body.room_id ||
        result.room_id ||
        room_id
      ).trim()

      const ownerRoomId = safeString(
        body.owner_room_id ||
        result.owner_room_id ||
        joinResult.room_id ||
        finalRoomId
      ).trim()

      if (!finalRoomId) {
        throw new Error(t('chat.fedMenu.runtime.acceptRoomMissingRoomId'))
      }

      await enterRoomAfterFederationAccept(
        finalRoomId,
        peer_id,
        remote_user_id,
        remote_label,
        ownerRoomId
      )

      inviteOk.value = buildAcceptSuccessMessage(finalRoomId, peer_id, t)
      inviteHint.value = ''
      scheduleClosePanel(1800)
    } catch (e) {
      inviteErr.value = buildInviteErrorMessage(e, t)
      inviteHint.value = buildInviteHint(e, t)
    } finally {
      acceptingInvite.value = false
      if (open.value) positionPanel()
    }
  }

  async function retryLastAccept() {
    const last = safeObject(lastInviteAttempt.value)
    if (!last.peer_id) return
    inviteForm.value = {
      peer_id: safeString(last.peer_id),
      room_id: safeString(last.room_id),
      invite_token: safeString(last.invite_token),
      remote_user_id: safeString(last.remote_user_id),
      remote_label: safeString(last.remote_label),
      target_peer_id: safeString(last.target_peer_id),
    }
    await acceptRoomInvite()
  }

  onMounted(() => {
    document.addEventListener('click', onGlobalClick)
    document.addEventListener('keydown', onKeydown)
    window.addEventListener('resize', onResize)
    window.addEventListener('scroll', onResize, true)
  })

  onUnmounted(() => {
    clearClosePanelTimer()
    document.removeEventListener('click', onGlobalClick)
    document.removeEventListener('keydown', onKeydown)
    window.removeEventListener('resize', onResize)
    window.removeEventListener('scroll', onResize, true)
  })

  return {
    wrapRef,
    btnRef,
    open,
    panelStyle,
    marketEnabled,
    loadingPeers,
    peers,
    saving,
    copyingFederationInfo,
    err,
    ok,
    form,
    pasteText,
    pasteErr,
    pasteOk,
    pasteHint,
    importingPaste,
    importedInviteEntries,
    checkingHealth,
    peerHealthMap,
    acceptingInvite,
    inviteErr,
    inviteOk,
    inviteHint,
    inviteForm,
    enabledPeers,
    canRetryInvite,
    toggle,
    onToggleMarket,
    peerSelected,
    togglePeer,
    loadPeers,
    savePeer,
    copyFederationInfo,
    pasteFromClipboard,
    importFederationInfo,
    maskInviteToken,
    applyPeerToForm,
    applyImportedInvite,
    removeImportedInvite,
    checkPeerHealth,
    acceptRoomInvite,
    retryLastAccept,
  }
}
