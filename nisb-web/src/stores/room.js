import { defineStore } from 'pinia'

import { create_room_store_state } from './room/room_state'
import { room_getters } from './room/room_getters'
import { room_core_actions } from './room/room_actions_core'
import { room_loader_actions } from './room/room_actions_loaders'
import {
  getRoomMcpImportedProviders as room_mcp_get_imported_providers,
  setRoomMcpImportedProviders as room_mcp_set_imported_providers,
  upsertRoomMcpImportedProvider as room_mcp_upsert_imported_provider,
  removeRoomMcpImportedProvider as room_mcp_remove_imported_provider,
  clearRoomMcpImportedProviders as room_mcp_clear_imported_providers,
  hydrateImportedRoomMcpProvidersFromRoles as room_mcp_hydrate_from_roles,
  resolveRoomMcpShareRef as room_mcp_resolve_share_ref,
} from './room/room_mcp_imports'

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

function isFederatedAccessRevokedValue(value) {
  const s = safeString(value).trim().toLowerCase()
  return [
    'room_access_revoked',
    'federated_member_access_revoked',
    'member_access_revoked',
  ].includes(s)
}

function readFederatedRemoteUserId(src = {}) {
  const row = safeObject(src)
  return safeString(
    row.remote_user_id ||
    row.remoteUserId
  ).trim()
}

function readStrictFederatedRemoteUserId(src = {}) {
  const row = safeObject(src)
  return safeString(
    row.remote_user_id ||
    row.remoteUserId
  ).trim()
}

function readFederatedOwnerUserId(src = {}) {
  const row = safeObject(src)
  return safeString(
    row.local_owner_user_id ||
    row.localOwnerUserId ||
    row.owner_user_id ||
    row.ownerUserId ||
    row.remote_user_id ||
    row.remoteUserId
  ).trim()
}

function readFederatedTargetPeerId(src = {}) {
  const row = safeObject(src)
  return safeString(
    row.target_peer_id ||
    row.targetPeerId
  ).trim()
}

function readFederatedPeerId(src = {}) {
  const row = safeObject(src)
  return safeString(
    row.peer_id ||
    row.peerId ||
    row.target_peer_id ||
    row.targetPeerId
  ).trim()
}

function firstObjectArg(rest = []) {
  for (const item of rest) {
    const obj = safeObject(item)
    if (Object.keys(obj).length) return obj
  }
  return {}
}

function readFederationSessionRoomId(session = {}) {
  const src = safeObject(session)
  return safeString(
    src.room_id ||
    src.local_room_id ||
    src.localRoomId ||
    src.ui_room_id ||
    src.uiRoomId
  ).trim()
}

function readFederationOwnerRoomId(session = {}) {
  const src = safeObject(session)
  return safeString(
    src.owner_room_id ||
    src.ownerRoomId ||
    src.remote_room_id ||
    src.remoteRoomId ||
    src.upstream_room_id ||
    src.upstreamRoomId ||
    src.owner_vps_room_id ||
    src.ownerVpsRoomId
  ).trim()
}

function resolveExplicitRoomId(args = {}) {
  return safeString(
    safeObject(args).room_id ||
    safeObject(args).roomId
  ).trim()
}

function withBoundRoomId(args = {}, roomId = '') {
  const src = safeObject(args)
  const explicit = resolveExplicitRoomId(src)
  if (explicit) return src

  const rid = safeString(roomId).trim()
  if (!rid) return src

  return {
    ...src,
    room_id: rid,
  }
}

function resolveCurrentRoomId(store, args = {}) {
  const explicit = resolveExplicitRoomId(args)
  if (explicit) return explicit

  return safeString(
    store.roomId ||
    store.room?.room_id
  ).trim()
}

function resolveOutboundFederatedRoomId(store, args = {}) {
  const session = safeObject(store.federationRoomSession)
  const owner_room_id = readFederationOwnerRoomId(session)
  const current_room_id = resolveCurrentRoomId(store, args)
  const session_room_id = readFederationSessionRoomId(session)

  return owner_room_id || current_room_id || session_room_id
}

function extractJoinedFederatedRooms(raw) {
  if (Array.isArray(raw)) return raw

  const root = safeObject(raw)
  const data = safeObject(root.data)
  const result = safeObject(root.result)
  const payload = safeObject(root.payload)

  const candidates = [
    root.items,
    root.rooms,
    root.joined_rooms,
    root.joinedRooms,
    data.items,
    data.rooms,
    data.joined_rooms,
    data.joinedRooms,
    result.items,
    result.rooms,
    result.joined_rooms,
    result.joinedRooms,
    payload.items,
    payload.rooms,
    payload.joined_rooms,
    payload.joinedRooms,
  ]

  for (const item of candidates) {
    if (Array.isArray(item)) return item
  }

  return []
}

function normalizeJoinedFederatedRoomRow(row = {}) {
  const src = safeObject(row)

  const remote_user_id = readStrictFederatedRemoteUserId(src)
  const local_owner_user_id = readFederatedOwnerUserId(src)
  const target_peer_id = readFederatedTargetPeerId(src)

  return {
    peer_id: readFederatedPeerId(src),
    target_peer_id,
    room_id: safeString(
      src.room_id ||
      src.local_room_id ||
      src.localRoomId ||
      src.ui_room_id ||
      src.uiRoomId
    ).trim(),
    owner_room_id: safeString(
      src.owner_room_id ||
      src.ownerRoomId ||
      src.remote_room_id ||
      src.remoteRoomId ||
      src.upstream_room_id ||
      src.upstreamRoomId ||
      src.owner_vps_room_id ||
      src.ownerVpsRoomId
    ).trim(),
    remote_user_id,
    local_owner_user_id,
    owner_user_id: local_owner_user_id,
    remote_label: safeString(src.remote_label || src.title || src.label).trim(),
    title: safeString(src.title || src.label).trim(),
    enabled: src.enabled !== false,
  }
}

function readNestedFederatedResult(raw = {}) {
  return safeObject(safeObject(raw).result)
}

function isExplicitFailureLike(value = {}) {
  const src = safeObject(value)
  if (src.success === false) return true
  const status = safeString(src.status).trim().toLowerCase()
  return status === 'error' || status === 'failed' || status === 'fail'
}

function pickFederationErrorValue(chain = [], keys = []) {
  for (const row of safeArray(chain)) {
    const src = safeObject(row)
    for (const key of keys) {
      const value = safeString(src[key]).trim()
      if (value) return value
    }
  }
  return ''
}

function pickFederationRetryable(chain = []) {
  for (const row of safeArray(chain)) {
    const src = safeObject(row)
    if (typeof src.retryable === 'boolean') return src.retryable
  }
  return false
}

function buildFederatedRoomToolError(raw = {}, tool = '', args = {}) {
  const root = safeObject(raw)
  const result = readNestedFederatedResult(root)
  const upstream = safeObject(root.upstream)
  const chain = [result, root, upstream]

  const error_code =
    pickFederationErrorValue(chain, ['error_code', 'code']) ||
    'federated_room_tool_failed'

  const error_kind =
    pickFederationErrorValue(chain, ['error_kind']) ||
    'federated_room_tool_failed'

  const user_message =
    pickFederationErrorValue(chain, ['user_message', 'message', 'error', 'detail']) ||
    'Federated room request failed'

  const status_code = Number(
    pickFederationErrorValue(chain, ['status_code']) || 0
  ) || 0

  const retryable = pickFederationRetryable(chain)

  const peer_id = pickFederationErrorValue(
    [root, result, upstream, args],
    ['peer_id', '_federation_peer_id']
  )

  const room_id = (
    resolveExplicitRoomId(args) ||
    pickFederationErrorValue(
      [root, result, upstream, args],
      ['room_id', '_federation_owner_room_id', '_federation_origin_room_id']
    )
  )

  const normalizedTool = safeString(tool).trim()

  const is_access_revoked =
    isFederatedAccessRevokedValue(error_code) ||
    isFederatedAccessRevokedValue(error_kind)

  const err = new Error(user_message)
  err.name = 'FederatedRoomToolError'

  err.code = error_code
  err.error_code = error_code
  err.error_kind = error_kind
  err.user_message = user_message
  err.retryable = retryable
  err.status_code = status_code
  err.peer_id = peer_id
  err.room_id = room_id
  err.tool = normalizedTool
  err.is_access_revoked = is_access_revoked
  err.is_room_access_revoked = is_access_revoked

  err.federation = {
    error_code,
    error_kind,
    user_message,
    retryable,
    status_code,
    peer_id,
    room_id,
    tool: normalizedTool,
    is_access_revoked,
  }

  err.raw = raw
  return err
}

function buildLocalFederatedRoomSessionError(message = '', tool = '', args = {}) {
  const user_message = safeString(message).trim() || 'Federated room session is invalid'
  const err = new Error(user_message)

  err.name = 'FederatedRoomSessionError'
  err.code = 'federation_session_invalid'
  err.error_code = 'federation_session_invalid'
  err.error_kind = 'federation_session'
  err.user_message = user_message
  err.retryable = false
  err.status_code = 0
  err.peer_id = ''
  err.room_id = resolveExplicitRoomId(args)
  err.tool = safeString(tool).trim()

  err.federation = {
    error_code: err.error_code,
    error_kind: err.error_kind,
    user_message,
    retryable: false,
    status_code: 0,
    peer_id: '',
    room_id: err.room_id,
    tool: err.tool,
  }

  err.raw = {
    success: false,
    status: 'error',
    message: user_message,
    error_code: err.error_code,
    error_kind: err.error_kind,
    room_id: err.room_id,
    tool: err.tool,
  }

  return err
}

function assertFederatedRoomSessionReady(store, tool = '', args = {}) {
  const session = safeObject(store.federationRoomSession)

  const peer_id = safeString(session.peer_id).trim()
  const owner_room_id = readFederationOwnerRoomId(session)
  const remote_user_id = readStrictFederatedRemoteUserId(session)

  if (!session.enabled) {
    throw buildLocalFederatedRoomSessionError(
      'Federated room session is disabled',
      tool,
      args
    )
  }

  if (!peer_id) {
    throw buildLocalFederatedRoomSessionError(
      'Federated room session missing peer_id',
      tool,
      args
    )
  }

  if (!owner_room_id) {
    throw buildLocalFederatedRoomSessionError(
      'Federated room session missing owner_room_id',
      tool,
      args
    )
  }

  if (!remote_user_id) {
    throw buildLocalFederatedRoomSessionError(
      'Federated room session missing remote_user_id',
      tool,
      args
    )
  }

  return {
    session,
    peer_id,
    owner_room_id,
    remote_user_id,
  }
}

function assertFederatedRoomCallOk(raw = {}, tool = '', args = {}) {
  const root = safeObject(raw)
  const result = readNestedFederatedResult(root)
  const upstream = safeObject(root.upstream)

  if (isExplicitFailureLike(root)) {
    throw buildFederatedRoomToolError(root, tool, args)
  }

  if (Object.keys(result).length && isExplicitFailureLike(result)) {
    throw buildFederatedRoomToolError(root, tool, args)
  }

  if (Object.keys(upstream).length && isExplicitFailureLike(upstream)) {
    throw buildFederatedRoomToolError(root, tool, args)
  }

  return raw
}

async function build_federated_room_call(callTool, store, tool, args = {}) {
  const {
    session,
    peer_id: owner_peer_id,
    owner_room_id,
    remote_user_id,
  } = assertFederatedRoomSessionReady(store, tool, args)

  const target_peer_id = readFederatedTargetPeerId(session)
  const federation_peer_id = target_peer_id || owner_peer_id
  const owner_user_id = readFederatedOwnerUserId(session)
  const remote_label = safeString(session.remote_label).trim()

  const original_room_id =
    resolveCurrentRoomId(store, args) || readFederationSessionRoomId(session)
  const outbound_room_id = resolveOutboundFederatedRoomId(store, args)

  const next_tool_args = {
    ...safeObject(args),
    _federation_peer_id: federation_peer_id,
    _federation_remote_user_id: remote_user_id,
    _federation_target_peer_id: target_peer_id || federation_peer_id,
    _federation_remote_label: remote_label,
  }

  if (owner_user_id) {
    next_tool_args._federation_owner_user_id = owner_user_id
    next_tool_args._federation_local_owner_user_id = owner_user_id
  }

  if (original_room_id) {
    next_tool_args._federation_origin_room_id = original_room_id
  }

  if (owner_room_id) {
    next_tool_args._federation_owner_room_id = owner_room_id
  }

  if (outbound_room_id) {
    next_tool_args.room_id = outbound_room_id
  }

  const raw = await callTool('nisb_fed_call', {
    peer_id: owner_peer_id,
    tool,
    tool_args: next_tool_args,
  })

  return assertFederatedRoomCallOk(raw, tool, next_tool_args)
}

function should_proxy_room_tool(store, tool, args = {}) {
  if (!tool || typeof tool !== 'string') return false
  if (tool === 'nisb_fed_call') return false
  if (!tool.startsWith('nisb_room_')) return false

  const session = safeObject(store.federationRoomSession)
  if (!session.enabled) return false

  const target_room_id = resolveCurrentRoomId(store, args)
  const session_room_id = readFederationSessionRoomId(session)
  const owner_room_id = readFederationOwnerRoomId(session)

  if (!target_room_id) return false

  if (session_room_id && target_room_id === session_room_id) return true
  if (owner_room_id && target_room_id === owner_room_id) return true

  return false
}

function isFederationSessionMatchedRoom(session = {}, roomId = '') {
  const rid = safeString(roomId).trim()
  if (!rid) return false

  const session_room_id = readFederationSessionRoomId(session)
  const owner_room_id = readFederationOwnerRoomId(session)

  if (session_room_id && rid === session_room_id) return true
  if (owner_room_id && rid === owner_room_id) return true
  return false
}

function hasMinimalFederationSession(session = {}) {
  const src = safeObject(session)
  if (!src.enabled) return false

  return !!(
    readFederatedPeerId(src) &&
    readFederationOwnerRoomId(src) &&
    readStrictFederatedRemoteUserId(src)
  )
}

function hasHydratedFederationSession(session = {}) {
  const src = safeObject(session)
  if (!hasMinimalFederationSession(src)) return false

  return !!(
    readFederatedTargetPeerId(src) &&
    readFederatedOwnerUserId(src)
  )
}

function isSameFederationSessionRoom(a = {}, b = {}) {
  const left = [
    readFederationSessionRoomId(a),
    readFederationOwnerRoomId(a),
  ].filter(Boolean)

  const right = [
    readFederationSessionRoomId(b),
    readFederationOwnerRoomId(b),
  ].filter(Boolean)

  if (!left.length || !right.length) return false
  return left.some((id) => right.includes(id))
}

async function ensureFederationSessionForRoomToolCall(store, callTool, tool, args = {}) {
  if (typeof callTool !== 'function') return
  if (!tool || typeof tool !== 'string') return
  if (tool === 'nisb_fed_call') return
  if (!tool.startsWith('nisb_room_')) return

  const rid = resolveCurrentRoomId(store, args)
  if (!rid) return

  if (typeof store?.ensureFederationContextForRoomId === 'function') {
    await store.ensureFederationContextForRoomId(callTool, rid, { clearLocal: true })
  }
}

export const useRoomStore = defineStore('room', {
  state: () => ({
    ...create_room_store_state(),
    federationRoomSession: null,
    roomMcpImportedProvidersByRoom: {},
    roomMcpLastResolvedShareRef: '',
    roomMcpLastResolvedProvider: null,
  }),

  getters: room_getters,

  actions: {
    ...room_core_actions,
    ...room_loader_actions,

    getRoomMcpImportedProviders(roomId = '') {
      return room_mcp_get_imported_providers(this, roomId)
    },

    setRoomMcpImportedProviders(roomId = '', providers = []) {
      return room_mcp_set_imported_providers(this, roomId, providers)
    },

    upsertRoomMcpImportedProvider(roomId = '', provider = {}) {
      return room_mcp_upsert_imported_provider(this, roomId, provider)
    },

    removeRoomMcpImportedProvider(roomId = '', providerId = '') {
      return room_mcp_remove_imported_provider(this, roomId, providerId)
    },

    clearRoomMcpImportedProviders(roomId = '') {
      return room_mcp_clear_imported_providers(this, roomId)
    },

    hydrateImportedRoomMcpProvidersFromRoles(roomId = '', roles = []) {
      return room_mcp_hydrate_from_roles(this, roomId, roles)
    },

    async resolveRoomMcpShareRef(callTool, shareRef, opts = {}) {
      return await room_mcp_resolve_share_ref(this, callTool, shareRef, opts)
    },

    async listJoinedFederatedRooms(callTool) {
      if (typeof callTool !== 'function') return []

      const raw = await callTool('nisb_fed_list_joined_rooms', {})
      return extractJoinedFederatedRooms(raw)
        .map((row) => normalizeJoinedFederatedRoomRow(row))
        .filter((row) => row.room_id || row.owner_room_id)
    },

    async ensureFederationContextForRoomId(callTool, roomId, opts = {}) {
      const rid = safeString(roomId).trim()
      if (!rid) {
        return {
          ok: false,
          code: 'room_id_required',
          message: 'room_id is required',
        }
      }

      const currentSession = safeObject(this.federationRoomSession)
      const currentRoomId = readFederationSessionRoomId(currentSession)
      const currentOwnerRoomId = readFederationOwnerRoomId(currentSession)
      const currentMatched =
        currentSession.enabled &&
        (currentRoomId === rid || currentOwnerRoomId === rid)

      if (currentMatched && hasHydratedFederationSession(currentSession)) {
        return {
          ok: true,
          kind: 'federated',
          reused: true,
          hydrated: true,
          session: currentSession,
        }
      }

      let joined = []
      try {
        joined = await this.listJoinedFederatedRooms(callTool)
      } catch (e) {
        if (currentMatched && hasMinimalFederationSession(currentSession)) {
          return {
            ok: true,
            kind: 'federated',
            reused: true,
            hydrated: false,
            degraded: true,
            session: currentSession,
          }
        }

        return {
          ok: false,
          code: 'joined_rooms_load_failed',
          message: e?.message || 'failed to load joined federated rooms',
        }
      }

      const hit = safeArray(joined).find((row) => {
        const item = normalizeJoinedFederatedRoomRow(row)
        return item.room_id === rid || item.owner_room_id === rid
      })

      if (!hit) {
        if (currentMatched && hasMinimalFederationSession(currentSession)) {
          return {
            ok: true,
            kind: 'federated',
            reused: true,
            hydrated: false,
            degraded: true,
            session: currentSession,
          }
        }

        if (opts.clearLocal === true || opts.clear_local === true) {
          this.clearFederationRoomSession()
        }
        return {
          ok: true,
          kind: 'local',
          federated: false,
        }
      }

      const row = normalizeJoinedFederatedRoomRow(hit)
      if (!row.peer_id || !row.owner_room_id || !row.remote_user_id) {
        if (currentMatched && hasMinimalFederationSession(currentSession)) {
          return {
            ok: true,
            kind: 'federated',
            reused: true,
            hydrated: false,
            degraded: true,
            session: currentSession,
          }
        }

        return {
          ok: false,
          code: 'invalid_joined_room',
          message: 'joined federated room record is invalid: missing peer_id / owner_room_id / remote_user_id',
        }
      }

      const session = this.setFederationRoomSession({
        enabled: row.enabled !== false,
        peer_id: row.peer_id,
        target_peer_id: row.target_peer_id,
        room_id: row.room_id || rid,
        owner_room_id: row.owner_room_id,
        remote_user_id: row.remote_user_id,
        local_owner_user_id: row.local_owner_user_id,
        owner_user_id: row.owner_user_id || row.local_owner_user_id,
        remote_label: row.remote_label,
      })

      return {
        ok: true,
        kind: 'federated',
        federated: true,
        restored: true,
        hydrated: hasHydratedFederationSession(session),
        session,
      }
    },

    syncFederationSessionWithRoomId(roomId = '') {
      const rid = safeString(roomId || this.roomId || this.room?.room_id).trim()
      const session = safeObject(this.federationRoomSession)

      if (!session.enabled) {
        return {
          ok: true,
          federated: false,
          cleared: false,
        }
      }

      if (!rid) {
        return {
          ok: true,
          federated: true,
          cleared: false,
          session,
        }
      }

      if (isFederationSessionMatchedRoom(session, rid)) {
        return {
          ok: true,
          federated: true,
          cleared: false,
          session,
        }
      }

      this.clearFederationRoomSession()
      return {
        ok: true,
        federated: false,
        cleared: true,
      }
    },

    setRoomId(roomId, ...rest) {
      const rid = safeString(roomId).trim()

      if (typeof room_core_actions.setRoomId === 'function') {
        const result = room_core_actions.setRoomId.call(this, rid, ...rest)

        if (result && typeof result.then === 'function') {
          return result.finally(() => {
            this.syncFederationSessionWithRoomId(rid)
          })
        }

        this.syncFederationSessionWithRoomId(rid)
        return result
      }

      this.roomId = rid
      this.syncFederationSessionWithRoomId(rid)
      return rid
    },

    setFederationRoomSession(session = {}) {
      const src = safeObject(session)
      const prev = safeObject(this.federationRoomSession)

      const nextDraft = {
        enabled: src.enabled !== false,
        peer_id: readFederatedPeerId(src),
        target_peer_id: readFederatedTargetPeerId(src),
        room_id: safeString(
          src.room_id ||
          src.local_room_id ||
          src.localRoomId ||
          src.ui_room_id ||
          src.uiRoomId
        ).trim(),
        owner_room_id: safeString(
          src.owner_room_id ||
          src.ownerRoomId ||
          src.remote_room_id ||
          src.remoteRoomId ||
          src.upstream_room_id ||
          src.upstreamRoomId ||
          src.owner_vps_room_id ||
          src.ownerVpsRoomId
        ).trim(),
        remote_user_id: readStrictFederatedRemoteUserId(src),
        local_owner_user_id: readFederatedOwnerUserId(src),
        remote_label: safeString(src.remote_label).trim(),
      }

      const sameRoom = isSameFederationSessionRoom(prev, nextDraft)

      const merged_peer_id =
        nextDraft.peer_id ||
        (sameRoom ? readFederatedPeerId(prev) : '')

      const merged_target_peer_id =
        nextDraft.target_peer_id ||
        (sameRoom ? readFederatedTargetPeerId(prev) : '')

      const merged_room_id =
        nextDraft.room_id ||
        (sameRoom ? readFederationSessionRoomId(prev) : '')

      const merged_owner_room_id =
        nextDraft.owner_room_id ||
        (sameRoom ? readFederationOwnerRoomId(prev) : '')

      const merged_remote_user_id =
        nextDraft.remote_user_id ||
        (sameRoom ? readStrictFederatedRemoteUserId(prev) : '')

      const merged_local_owner_user_id =
        nextDraft.local_owner_user_id ||
        (sameRoom ? readFederatedOwnerUserId(prev) : '')

      const merged_remote_label =
        nextDraft.remote_label ||
        (sameRoom ? safeString(prev.remote_label).trim() : '')

      this.federationRoomSession = {
        enabled: nextDraft.enabled,
        peer_id: merged_peer_id,
        target_peer_id: merged_target_peer_id,
        room_id: merged_room_id,
        owner_room_id: merged_owner_room_id,
        remote_user_id: merged_remote_user_id,
        local_owner_user_id: merged_local_owner_user_id,
        owner_user_id: merged_local_owner_user_id,
        remote_label: merged_remote_label,
      }

      return this.federationRoomSession
    },

    clearFederationRoomSession() {
      this.federationRoomSession = null
    },

    isFederatedRoom(roomId = '') {
      const session = safeObject(this.federationRoomSession)
      if (!session.enabled) return false

      const rid = safeString(roomId || this.roomId || this.room?.room_id).trim()
      if (!rid) return false

      return isFederationSessionMatchedRoom(session, rid)
    },

    async callRoomTool(callTool, tool, args = {}, boundRoomId = '') {
      const nextArgs = withBoundRoomId(args, boundRoomId)

      const localOnlyTools = new Set([
        'nisb_room_mcp_share_ref_resolve',
        'nisb_room_mcp_provider_share_ref_resolve',
        'nisb_room_mcp_provider_import_resolve',
      ])

      if (localOnlyTools.has(safeString(tool).trim())) {
        return await callTool(tool, nextArgs)
      }

      await ensureFederationSessionForRoomToolCall(this, callTool, tool, nextArgs)

      if (!should_proxy_room_tool(this, tool, nextArgs)) {
        return await callTool(tool, nextArgs)
      }

      return await build_federated_room_call(callTool, this, tool, nextArgs)
    },

    buildRoomToolProxy(callTool, boundRoomId = '') {
      return async (tool, args = {}) => {
        const nextArgs = withBoundRoomId(args, boundRoomId)
        await ensureFederationSessionForRoomToolCall(this, callTool, tool, nextArgs)

        if (should_proxy_room_tool(this, tool, nextArgs)) {
          return await build_federated_room_call(callTool, this, tool, nextArgs)
        }
        return await callTool(tool, nextArgs)
      }
    },

    async refreshRoomInfo(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      let result

      if (typeof room_loader_actions.refreshRoomInfo === 'function') {
        result = await room_loader_actions.refreshRoomInfo.call(this, proxiedCallTool, rid, ...rest)
      } else {
        result = await proxiedCallTool('nisb_room_get_info', {
          room_id: rid,
          ...firstObjectArg(rest),
        })
      }

      this.hydrateImportedRoomMcpProvidersFromRoles(rid, this.roles)
      return result
    },

    async loadRoomBundle(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)

      if (typeof room_loader_actions.loadRoomBundle === 'function') {
        const result = await room_loader_actions.loadRoomBundle.call(this, proxiedCallTool, rid, ...rest)
        this.hydrateImportedRoomMcpProvidersFromRoles(rid, this.roles)
        return result
      }

      await this.refreshRoomInfo(proxiedCallTool, rid)
      if (typeof this.loadRoomState === 'function') {
        await this.loadRoomState(proxiedCallTool, rid)
      }
      if (typeof this.loadRoomRoles === 'function') {
        await this.loadRoomRoles(proxiedCallTool, rid)
      }
      if (typeof this.loadRoomItems === 'function') {
        await this.loadRoomItems(proxiedCallTool, rid)
      }

      this.hydrateImportedRoomMcpProvidersFromRoles(rid, this.roles)
      return true
    },

    async refreshRoomItems(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.refreshRoomItems === 'function') {
        return await room_loader_actions.refreshRoomItems.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_shared_recent', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },

    async loadOlderRoomItems(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.loadOlderRoomItems === 'function') {
        return await room_loader_actions.loadOlderRoomItems.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_shared_recent', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },

    async refreshRuntimeEvents(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.refreshRuntimeEvents === 'function') {
        return await room_loader_actions.refreshRuntimeEvents.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_events_recent', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },

    async refreshRuntimeReplay(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.refreshRuntimeReplay === 'function') {
        return await room_loader_actions.refreshRuntimeReplay.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_events_replay', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },

    async loadRoomState(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.loadRoomState === 'function') {
        return await room_loader_actions.loadRoomState.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_get_state', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },

    async loadRoomRoles(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      let result

      if (typeof room_loader_actions.loadRoomRoles === 'function') {
        result = await room_loader_actions.loadRoomRoles.call(this, proxiedCallTool, rid, ...rest)
      } else {
        result = await proxiedCallTool('nisb_room_role_list', {
          room_id: rid,
          ...firstObjectArg(rest),
        })
      }

      this.hydrateImportedRoomMcpProvidersFromRoles(rid, this.roles)
      return result
    },

    async loadRoomItems(callTool, roomId, ...rest) {
      const rid = safeString(roomId).trim()
      const proxiedCallTool = this.buildRoomToolProxy(callTool, rid)
      if (typeof room_loader_actions.loadRoomItems === 'function') {
        return await room_loader_actions.loadRoomItems.call(this, proxiedCallTool, rid, ...rest)
      }
      return await proxiedCallTool('nisb_room_items_list', {
        room_id: rid,
        ...firstObjectArg(rest),
      })
    },
  },
})
