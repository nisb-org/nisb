import { ref } from 'vue'

const FEDERATION_INVITE_TTL_DEFAULT_SECONDS = 86400

const FEDERATION_INVITE_TTL_OPTIONS = [
  { label: '1 day', value: 86400 },
  { label: '3 days', value: 3 * 86400 },
  { label: '7 days', value: 7 * 86400 },
  { label: '30 days', value: 30 * 86400 },
]

const FEDERATION_INVITE_HISTORY_FILTER_OPTIONS = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Used', value: 'used' },
  { label: 'Revoked', value: 'revoked' },
  { label: 'Expired', value: 'expired' },
]

function normalize_federation_invite_ttl_seconds(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return FEDERATION_INVITE_TTL_DEFAULT_SECONDS
  return FEDERATION_INVITE_TTL_OPTIONS.some((item) => item.value === n)
    ? n
    : FEDERATION_INVITE_TTL_DEFAULT_SECONDS
}

function normalize_federation_invite_history_filter(value) {
  const s = String(value || '').trim().toLowerCase()
  return FEDERATION_INVITE_HISTORY_FILTER_OPTIONS.some((item) => item.value === s)
    ? s
    : 'all'
}

function normalize_nonnegative_integer(value, fallback = 0) {
  const n = Number(value)
  if (!Number.isFinite(n)) return fallback
  return Math.max(0, Math.trunc(n))
}

function local_string(value) {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function is_federated_participant_uid(value) {
  return local_string(value).startsWith('fed__')
}

function parse_federated_participant_uid(value) {
  const participant_uid = local_string(value)
  if (!participant_uid || !participant_uid.startsWith('fed__')) {
    return {
      participant_uid,
      type: 'local',
      peer_id: '',
      remote_user_id: '',
    }
  }

  const parts = participant_uid.split('__')
  return {
    participant_uid,
    type: 'federated',
    peer_id: local_string(parts[1]),
    remote_user_id: local_string(parts[2]),
  }
}

function normalize_joined_member_item(item) {
  const row = item && typeof item === 'object' ? item : {}

  const participant_uid = local_string(row.participant_uid || row.uid)
  const parsed = parse_federated_participant_uid(participant_uid)

  const rawType = local_string(row.type).toLowerCase()
  const type = rawType === 'federated' || parsed.type === 'federated'
    ? 'federated'
    : 'local'

  const access_status = local_string(row.access_status).toLowerCase() === 'revoked'
    ? 'revoked'
    : 'active'

  return {
    ...row,
    participant_uid,
    uid: participant_uid,
    type,
    peer_id: local_string(row.peer_id || parsed.peer_id),
    remote_user_id: local_string(row.remote_user_id || parsed.remote_user_id),
    joined_at: local_string(row.joined_at),
    last_seen: local_string(row.last_seen),
    access_status,
    is_owner: !!row.is_owner,
    can_revoke_access: !!row.can_revoke_access && type === 'federated' && access_status !== 'revoked',
    is_access_revoked: !!row.is_access_revoked || access_status === 'revoked',
  }
}

export function use_room_settings_federation({
  room_store,
  callTool,
  call_room_tool,
  room_id_value,
  current_user_id_value,
  room_owner_user_id_value,
  can_issue_federation_invite,
  safe_string,
  safe_array,
  safe_object,
  pick_payload,
  is_success_like,
  read_first_nonempty_string,
}) {
  const federation_peers = ref([])
  const federation_peers_loading = ref(false)
  const federation_invite_busy = ref(false)
  const federation_invite_error = ref('')
  const federation_last_invite = ref(null)
  const federation_target_peer_id = ref('')
  const federation_invite_ttl_seconds = ref(FEDERATION_INVITE_TTL_DEFAULT_SECONDS)
  const federation_invite_history_filter = ref('all')
  const current_room_join_key = ref('')
  const federation_invites = ref([])
  const federation_invites_loading = ref(false)
  const federation_invites_error = ref('')
  const federation_revoke_busy_invite_id = ref('')
  const federation_extend_busy_invite_id = ref('')

  const federation_joined_members = ref([])
  const federation_joined_members_loading = ref(false)
  const federation_joined_members_error = ref('')
  const federation_revoke_member_busy_uid = ref('')

  function set_federation_invite_ttl_seconds(value) {
    federation_invite_ttl_seconds.value = normalize_federation_invite_ttl_seconds(value)
    return federation_invite_ttl_seconds.value
  }

  function set_federation_invite_history_filter(value) {
    federation_invite_history_filter.value = normalize_federation_invite_history_filter(value)
    return federation_invite_history_filter.value
  }

  function read_join_key_from_store() {
    return read_first_nonempty_string([
      room_store.room?.join_key,
      room_store.roomInfo?.join_key,
      room_store.roomState?.join_key,
      room_store.room?.meta?.join_key,
    ])
  }

  function sync_room_join_key_from_store(options = {}) {
    const { preserve_if_empty = false } = safe_object(options)
    const next = read_join_key_from_store()

    if (next || !preserve_if_empty) {
      current_room_join_key.value = next
    }

    return current_room_join_key.value
  }

  function read_joined_members_from_store() {
    const candidates = [
      room_store.room?.joined_members,
      room_store.roomInfo?.joined_members,
      room_store.room?.meta?.joined_members,
      room_store.roomInfo?.room?.joined_members,
    ]

    for (const rows of candidates) {
      if (Array.isArray(rows)) {
        return rows
          .map((item) => normalize_joined_member_item(item))
          .filter((item) => !!item.participant_uid)
      }
    }

    return []
  }

  function sync_federation_joined_members_from_store(options = {}) {
    const { preserve_if_empty = false } = safe_object(options)
    const next = read_joined_members_from_store()

    if (next.length || !preserve_if_empty) {
      federation_joined_members.value = next
    }

    return federation_joined_members.value
  }

  function reset_federation_state({ clear_join_key = false, clear_peers = false } = {}) {
    federation_last_invite.value = null
    federation_invite_error.value = ''
    federation_invites.value = []
    federation_invites_error.value = ''
    federation_revoke_busy_invite_id.value = ''
    federation_extend_busy_invite_id.value = ''
    federation_invite_ttl_seconds.value = FEDERATION_INVITE_TTL_DEFAULT_SECONDS
    federation_invite_history_filter.value = 'all'

    federation_joined_members.value = []
    federation_joined_members_error.value = ''
    federation_revoke_member_busy_uid.value = ''

    if (clear_join_key) {
      current_room_join_key.value = ''
    }

    if (clear_peers) {
      federation_peers.value = []
      federation_target_peer_id.value = ''
    }
  }

  async function ensure_room_join_key() {
    const cached = read_join_key_from_store()
    if (cached) {
      current_room_join_key.value = cached
      return cached
    }

    if (!room_id_value.value) {
      current_room_join_key.value = ''
      throw new Error('room_id missing')
    }

    const res = await call_room_tool('nisb_room_get_info', {
      room_id: room_id_value.value,
    })
    const payload = pick_payload(res)
    const roomInfoRow = extract_room_info_tool_result(res, payload)

    const token = read_first_nonempty_string([
      payload.join_key,
      payload.room?.join_key,
      payload.info?.join_key,
      payload.meta?.join_key,

      roomInfoRow.join_key,
      roomInfoRow.room?.join_key,
      roomInfoRow.info?.join_key,
      roomInfoRow.meta?.join_key,
    ])

    if (!token) {
      current_room_join_key.value = ''
      throw new Error('room join_key missing')
    }

    current_room_join_key.value = token
    return token
  }

  function normalize_peer_item(item) {
    const row = safe_object(item)
    return {
      ...row,
      peer_id: safe_string(row.peer_id).trim(),
      label: safe_string(row.label || row.peer_id).trim(),
      base_url: safe_string(row.base_url).trim(),
    }
  }

  function normalize_invite_status_client(value) {
    const s = safe_string(value).trim().toLowerCase()
    if (s === 'used') return 'used'
    if (s === 'expired') return 'expired'
    if (s === 'revoked') return 'revoked'
    return 'active'
  }

  function is_invite_expired_client(invite = {}) {
    const expires_at = safe_string(invite?.expires_at).trim()
    if (!expires_at) return false
    const ts = Date.parse(expires_at)
    if (!Number.isFinite(ts)) return false
    return ts <= Date.now()
  }

  function normalize_invite_item(item) {
    const row = safe_object(item)
    const normalized = {
      ...row,
      invite_id: safe_string(row.invite_id).trim(),
      room_id: safe_string(row.room_id).trim(),
      invite_token: safe_string(row.invite_token).trim(),
      target_peer_id: safe_string(row.target_peer_id).trim(),
      local_owner_user_id: safe_string(
        row.local_owner_user_id || row.user_id || ''
      ).trim(),
      status: normalize_invite_status_client(row.status),
      created_at: safe_string(row.created_at).trim(),
      expires_at: safe_string(row.expires_at).trim(),
      expires_in_seconds: normalize_nonnegative_integer(row.expires_in_seconds, 0),
      used_at: safe_string(row.used_at).trim(),
      used_by_remote_user_id: safe_string(row.used_by_remote_user_id).trim(),
      extended_at: safe_string(row.extended_at).trim(),
      extend_count: normalize_nonnegative_integer(row.extend_count, 0),
    }

    if (normalized.status === 'active' && is_invite_expired_client(normalized)) {
      normalized.status = 'expired'
    }

    normalized.is_active = normalized.status === 'active'
    normalized.is_used = normalized.status === 'used'
    normalized.is_expired = normalized.status === 'expired'
    normalized.is_revoked = normalized.status === 'revoked'
    normalized.status_label = normalized.status
    normalized.token_preview = normalized.invite_token
      ? `${normalized.invite_token.slice(0, 10)}...${normalized.invite_token.slice(-6)}`
      : ''

    return normalized
  }

  function extract_room_info_tool_result(raw = {}, payload = {}) {
    const candidates = [
      safe_object(raw),
      safe_object(payload),
      safe_object(safe_object(raw).result),
      safe_object(safe_object(raw).data),
      safe_object(safe_object(raw).payload),
    ]

    for (const candidate of candidates) {
      const rows = safe_array(candidate.tool_results)
      for (const row of rows) {
        const item = safe_object(row)
        if (local_string(item.type).toLowerCase() === 'room_info') {
          return item
        }
      }
    }

    return {}
  }

  function extract_federation_invites(payload) {
    const root = safe_object(payload)
    const result = safe_object(root.result)
    const data = safe_object(root.data)
    const innerPayload = safe_object(root.payload)

    const candidates = [
      root.invites,
      root.items,
      result.invites,
      result.items,
      data.invites,
      data.items,
      innerPayload.invites,
      innerPayload.items,
    ]

    for (const rows of candidates) {
      if (Array.isArray(rows)) {
        return rows
          .map((item) => normalize_invite_item(item))
          .filter((item) => !!item.invite_id)
      }
    }

    return []
  }

  function extract_federation_joined_members(raw = {}, payload = {}) {
    const root = safe_object(raw)
    const picked = safe_object(payload)

    const rootRoom = safe_object(root.room)
    const pickedRoom = safe_object(picked.room)

    const result = safe_object(root.result)
    const resultRoom = safe_object(result.room)

    const data = safe_object(root.data)
    const dataRoom = safe_object(data.room)

    const innerPayload = safe_object(root.payload)
    const innerPayloadRoom = safe_object(innerPayload.room)

    const roomInfoRow = extract_room_info_tool_result(root, picked)
    const roomInfoRoom = safe_object(roomInfoRow.room)

    const candidates = [
      root.joined_members,
      rootRoom.joined_members,

      picked.joined_members,
      pickedRoom.joined_members,

      result.joined_members,
      resultRoom.joined_members,

      data.joined_members,
      dataRoom.joined_members,

      innerPayload.joined_members,
      innerPayloadRoom.joined_members,

      roomInfoRow.joined_members,
      roomInfoRoom.joined_members,
    ]

    for (const rows of candidates) {
      if (Array.isArray(rows)) {
        return rows
          .map((item) => normalize_joined_member_item(item))
          .filter((item) => !!item.participant_uid)
      }
    }

    return []
  }

  function upsert_joined_members(rows = []) {
    federation_joined_members.value = safe_array(rows)
      .map((item) => normalize_joined_member_item(item))
      .filter((item) => !!item.participant_uid)
    return federation_joined_members.value
  }

  function mark_joined_member_revoked(participant_uid = '') {
    const normalized_uid = safe_string(participant_uid).trim()
    if (!normalized_uid) return federation_joined_members.value

    federation_joined_members.value = safe_array(federation_joined_members.value).map((item) => {
      if (safe_string(item?.participant_uid).trim() !== normalized_uid) return item
      return {
        ...item,
        access_status: 'revoked',
        is_access_revoked: true,
        can_revoke_access: false,
      }
    })

    return federation_joined_members.value
  }

  async function refresh_federation_peers() {
    if (!can_issue_federation_invite.value) {
      federation_peers.value = []
      federation_target_peer_id.value = ''
      federation_invite_error.value = ''
      return
    }

    federation_peers_loading.value = true
    federation_invite_error.value = ''

    try {
      const res = await callTool('nisb_fed_list_peers', {})
      const payload = pick_payload(res)
      const rows = safe_array(payload.peers || payload.items || payload.result?.peers)
        .map((item) => normalize_peer_item(item))
        .filter((item) => !!item.peer_id)

      federation_peers.value = rows

      const current = safe_string(federation_target_peer_id.value).trim()
      const still_exists = rows.some((item) => item.peer_id === current)
      if (!still_exists) {
        federation_target_peer_id.value = rows.length ? rows[0].peer_id : ''
      }
    } catch (error) {
      federation_peers.value = []
      federation_target_peer_id.value = ''
      federation_invite_error.value = safe_string(
        error?.message || error || 'load federation peers failed'
      )
    } finally {
      federation_peers_loading.value = false
    }
  }

  async function refresh_federation_room_invites() {
    const room_id = safe_string(room_id_value.value).trim()

    if (!can_issue_federation_invite.value || !room_id) {
      federation_invites.value = []
      federation_invites_error.value = ''
      return []
    }

    federation_invites_loading.value = true
    federation_invites_error.value = ''

    try {
      const res = await callTool('nisb_fed_list_room_invites', { room_id })
      const payload = pick_payload(res)

      if (!is_success_like(res)) {
        throw new Error(
          safe_string(payload?.message || res?.message || 'load federation invites failed')
            || 'load federation invites failed'
        )
      }

      const invites = extract_federation_invites(payload)
        .filter((item) => item.room_id === room_id)
        .sort((a, b) => {
          const ta = Date.parse(a.created_at || '') || 0
          const tb = Date.parse(b.created_at || '') || 0
          return tb - ta
        })

      federation_invites.value = invites
      federation_last_invite.value = invites[0] || null
      return invites
    } catch (error) {
      federation_invites.value = []
      federation_invites_error.value = safe_string(
        error?.message || error || 'load federation invites failed'
      )
      throw error
    } finally {
      federation_invites_loading.value = false
    }
  }

  async function refresh_federation_joined_members() {
    const room_id = safe_string(room_id_value.value).trim()

    if (!can_issue_federation_invite.value || !room_id) {
      federation_joined_members.value = []
      federation_joined_members_error.value = ''
      return []
    }

    federation_joined_members_loading.value = true
    federation_joined_members_error.value = ''

    try {
      const res = await call_room_tool('nisb_room_get_info', { room_id })
      const payload = pick_payload(res)
      const roomInfoRow = extract_room_info_tool_result(res, payload)

      if (!is_success_like(res)) {
        throw new Error(
          read_first_nonempty_string([
            payload?.user_message,
            payload?.message,
            res?.user_message,
            res?.message,
            'load federation joined members failed',
          ]) || 'load federation joined members failed'
        )
      }

      const join_key = read_first_nonempty_string([
        payload.join_key,
        payload.room?.join_key,
        payload.info?.join_key,
        payload.meta?.join_key,

        roomInfoRow.join_key,
        roomInfoRow.room?.join_key,
        roomInfoRow.info?.join_key,
        roomInfoRow.meta?.join_key,
      ])

      if (join_key) {
        current_room_join_key.value = join_key
      }

      const members = extract_federation_joined_members(res, payload)
      upsert_joined_members(members)
      return federation_joined_members.value
    } catch (error) {
      federation_joined_members.value = []
      federation_joined_members_error.value = safe_string(
        error?.message || error || 'load federation joined members failed'
      )
      throw error
    } finally {
      federation_joined_members_loading.value = false
    }
  }

  async function revoke_federation_room_invite(invite_id = '') {
    if (!can_issue_federation_invite.value) {
      throw new Error('当前账号无权撤销联邦房间邀请')
    }

    const room_id = safe_string(room_id_value.value).trim()
    const normalized_invite_id = safe_string(invite_id).trim()

    if (!room_id) throw new Error('room_id missing')
    if (!normalized_invite_id) throw new Error('invite_id missing')

    federation_revoke_busy_invite_id.value = normalized_invite_id
    federation_invite_error.value = ''
    federation_invites_error.value = ''

    try {
      const res = await callTool('nisb_fed_revoke_room_invite', {
        room_id,
        invite_id: normalized_invite_id,
      })
      const payload = pick_payload(res)

      if (!is_success_like(res)) {
        throw new Error(
          safe_string(payload?.message || res?.message || 'revoke federation invite failed')
            || 'revoke federation invite failed'
        )
      }

      try {
        await refresh_federation_room_invites()
      } catch {
        // 不阻断 revoke 成功主链
      }

      const revoked = normalize_invite_item(
        safe_object(payload.invite || payload.revoked_invite || {})
      )
      return revoked.invite_id ? revoked : { invite_id: normalized_invite_id, status: 'revoked' }
    } catch (error) {
      federation_invite_error.value = safe_string(
        error?.message || error || 'revoke federation invite failed'
      )
      throw error
    } finally {
      federation_revoke_busy_invite_id.value = ''
    }
  }

  async function revoke_federated_member_access(participant_uid = '') {
    if (!can_issue_federation_invite.value) {
      throw new Error('当前账号无权撤销 federated member access')
    }

    const room_id = safe_string(room_id_value.value).trim()
    const normalized_participant_uid = safe_string(participant_uid).trim()

    if (!room_id) throw new Error('room_id missing')
    if (!normalized_participant_uid) throw new Error('participant_uid missing')
    if (!is_federated_participant_uid(normalized_participant_uid)) {
      throw new Error('participant_uid invalid')
    }

    federation_revoke_member_busy_uid.value = normalized_participant_uid
    federation_joined_members_error.value = ''

    try {
      const res = await call_room_tool('nisb_room_revoke_federated_member_access', {
        room_id,
        participant_uid: normalized_participant_uid,
      })
      const payload = pick_payload(res)

      if (!is_success_like(res)) {
        throw new Error(
          read_first_nonempty_string([
            payload?.user_message,
            payload?.message,
            res?.user_message,
            res?.message,
            'revoke federated member access failed',
          ]) || 'revoke federated member access failed'
        )
      }

      const members = extract_federation_joined_members(payload)
      if (members.length) {
        upsert_joined_members(members)
      } else {
        mark_joined_member_revoked(normalized_participant_uid)
      }

      const matched = federation_joined_members.value.find(
        (item) => safe_string(item?.participant_uid).trim() === normalized_participant_uid
      )

      return matched || {
        participant_uid: normalized_participant_uid,
        access_status: 'revoked',
        is_access_revoked: true,
        can_revoke_access: false,
      }
    } catch (error) {
      federation_joined_members_error.value = safe_string(
        error?.message || error || 'revoke federated member access failed'
      )
      throw error
    } finally {
      federation_revoke_member_busy_uid.value = ''
    }
  }

  async function extend_federation_room_invite(invite_id = '', extend_seconds = 0) {
    if (!can_issue_federation_invite.value) {
      throw new Error('当前账号无权延期联邦房间邀请')
    }

    const room_id = safe_string(room_id_value.value).trim()
    const normalized_invite_id = safe_string(invite_id).trim()
    const normalized_extend_seconds = Number(extend_seconds)

    if (!room_id) throw new Error('room_id missing')
    if (!normalized_invite_id) throw new Error('invite_id missing')
    if (![86400, 604800].includes(normalized_extend_seconds)) {
      throw new Error('extend_seconds invalid')
    }

    federation_extend_busy_invite_id.value = normalized_invite_id
    federation_invite_error.value = ''
    federation_invites_error.value = ''

    try {
      const res = await callTool('nisb_fed_extend_room_invite', {
        room_id,
        invite_id: normalized_invite_id,
        extend_seconds: normalized_extend_seconds,
      })
      const payload = pick_payload(res)

      if (!is_success_like(res)) {
        throw new Error(
          safe_string(payload?.message || res?.message || 'extend federation invite failed')
            || 'extend federation invite failed'
        )
      }

      try {
        const invites = await refresh_federation_room_invites()
        const matched = Array.isArray(invites)
          ? invites.find((item) => item.invite_id === normalized_invite_id)
          : null
        if (matched) {
          federation_last_invite.value = matched
        }
      } catch {
        const extended = normalize_invite_item(
          safe_object(payload.invite || payload.extended_invite || {})
        )
        if (extended.invite_id) {
          federation_last_invite.value = extended
        }
      }

      const extended = normalize_invite_item(
        safe_object(payload.invite || payload.extended_invite || {})
      )
      return extended.invite_id
        ? extended
        : {
            invite_id: normalized_invite_id,
            extend_seconds: normalized_extend_seconds,
          }
    } catch (error) {
      federation_invite_error.value = safe_string(
        error?.message || error || 'extend federation invite failed'
      )
      throw error
    } finally {
      federation_extend_busy_invite_id.value = ''
    }
  }

  async function issue_federation_room_invite(target_peer_id = '') {
    if (!can_issue_federation_invite.value) {
      throw new Error('当前账号无权发出联邦房间邀请')
    }

    const room_id = safe_string(room_id_value.value).trim()
    if (!room_id) {
      throw new Error('room_id missing')
    }

    const target_peer = safe_string(target_peer_id || federation_target_peer_id.value).trim()
    if (!target_peer) {
      throw new Error('target_peer_id missing')
    }

    federation_invite_busy.value = true
    federation_invite_error.value = ''

    try {
      const join_key = await ensure_room_join_key()
      const owner_user_id = read_first_nonempty_string([
        room_owner_user_id_value.value,
        current_user_id_value.value,
        room_store.room?.owner_user_id,
      ])

      const res = await callTool('nisb_fed_issue_room_invite', {
        room_id,
        join_key,
        target_peer_id: target_peer,
        expires_in_seconds: federation_invite_ttl_seconds.value,
        local_owner_user_id: owner_user_id,
        user_id: owner_user_id,
      })

      if (!is_success_like(res)) {
        const payload = pick_payload(res)
        throw new Error(
          safe_string(payload?.message || res?.message || 'issue federation invite failed')
            || 'issue federation invite failed'
        )
      }

      const payload = pick_payload(res)
      const invite = safe_object(payload.invite)

      federation_last_invite.value = normalize_invite_item(
        Object.keys(invite).length ? invite : payload
      )
      federation_target_peer_id.value = target_peer

      try {
        await refresh_federation_room_invites()
      } catch {
        // 不阻断 issue 成功主链
      }

      return federation_last_invite.value
    } catch (error) {
      federation_invite_error.value = safe_string(
        error?.message || error || 'issue federation invite failed'
      )
      throw error
    } finally {
      federation_invite_busy.value = false
    }
  }

  return {
    current_room_join_key,
    federation_peers,
    federation_peers_loading,
    federation_target_peer_id,
    federation_invite_ttl_seconds,
    federation_invite_ttl_options: FEDERATION_INVITE_TTL_OPTIONS,
    federation_invite_history_filter,
    federation_invite_history_filter_options: FEDERATION_INVITE_HISTORY_FILTER_OPTIONS,
    federation_invite_busy,
    federation_invite_error,
    federation_last_invite,
    federation_invites,
    federation_invites_loading,
    federation_invites_error,
    federation_revoke_busy_invite_id,
    federation_extend_busy_invite_id,

    federation_joined_members,
    federation_joined_members_loading,
    federation_joined_members_error,
    federation_revoke_member_busy_uid,

    set_federation_invite_ttl_seconds,
    set_federation_invite_history_filter,
    sync_room_join_key_from_store,
    sync_federation_joined_members_from_store,
    reset_federation_state,
    ensure_room_join_key,
    refresh_federation_room_invites,
    refresh_federation_joined_members,
    revoke_federation_room_invite,
    revoke_federated_member_access,
    extend_federation_room_invite,
    refresh_federation_peers,
    issue_federation_room_invite,
  }
}

