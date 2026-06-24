export function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

export function safeArray(v) {
  return Array.isArray(v) ? v : []
}

export function safeString(v) {
  return v === null || v === undefined ? '' : String(v)
}

function translate(t, key, params = {}) {
  if (typeof t !== 'function') return key
  const value = t(key, params)
  return value || key
}

export function stripCodeFence(text = '') {
  return safeString(text)
    .replace(/^```[a-zA-Z0-9_-]*\s*/g, '')
    .replace(/```$/g, '')
    .trim()
}

export function pickPayload(res) {
  const root = safeObject(res)
  const candidates = [safeObject(root.data), safeObject(root.result), safeObject(root.payload), root]
  for (const item of candidates) {
    if (Object.keys(item).length > 0) return item
  }
  return {}
}

export function normalizeStatus(value) {
  const s = String(value || '').trim().toLowerCase()
  if (!s) return ''
  if (['ok', 'success', 'succeeded'].includes(s)) return 'success'
  if (['warning', 'partial_success', 'partial_error'].includes(s)) return 'warning'
  if (['error', 'failed', 'fail'].includes(s)) return 'error'
  return s
}

export function isSuccessLike(res) {
  const root = safeObject(res)
  const payload = pickPayload(res)
  return normalizeStatus(root.status) === 'success' ||
    normalizeStatus(payload.status) === 'success' ||
    root.success === true ||
    payload.success === true
}

export function normalizeFedErrorMeta(raw) {
  const root = safeObject(raw)
  const payload = pickPayload(raw)
  const upstream = safeObject(payload.upstream || root.upstream)
  const result = safeObject(payload.result || root.result)
  const federation = safeObject(root.federation)

  const error_code = String(
    federation.error_code ||
    payload.error_code ||
    root.error_code ||
    result.error_code ||
    upstream.error_code ||
    root.code ||
    ''
  ).trim()

  const user_message = String(
    federation.user_message ||
    payload.user_message ||
    root.user_message ||
    result.user_message ||
    upstream.user_message ||
    payload.message ||
    root.message ||
    result.message ||
    upstream.message ||
    ''
  ).trim()

  const retryable = !!(
    federation.retryable ??
    payload.retryable ??
    root.retryable ??
    result.retryable ??
    upstream.retryable
  )

  return {
    error_code,
    user_message,
    retryable,
  }
}

export function buildInviteErrorMessage(raw, t) {
  const meta = normalizeFedErrorMeta(raw)
  const code = String(meta.error_code || '').trim()
  if (meta.user_message) return meta.user_message

  const keyMap = {
    token_invalid: 'chat.fedMenu.inviteErrors.tokenInvalid',
    owner_unreachable: 'chat.fedMenu.inviteErrors.ownerUnreachable',
    permission_denied: 'chat.fedMenu.inviteErrors.permissionDenied',
    room_not_found: 'chat.fedMenu.inviteErrors.roomNotFound',
    invite_expired: 'chat.fedMenu.inviteErrors.inviteExpired',
    invite_not_active: 'chat.fedMenu.inviteErrors.inviteNotActive',
    peer_mismatch: 'chat.fedMenu.inviteErrors.peerMismatch',
    invite_not_found: 'chat.fedMenu.inviteErrors.inviteNotFound',
    peer_not_found: 'chat.fedMenu.inviteErrors.peerNotFound',
  }

  return translate(t, keyMap[code] || 'chat.fedMenu.inviteErrors.acceptFailed')
}

export function buildInviteHint(raw, t) {
  const meta = normalizeFedErrorMeta(raw)
  const keyMap = {
    token_invalid: 'chat.fedMenu.inviteHints.tokenInvalid',
    owner_unreachable: 'chat.fedMenu.inviteHints.ownerUnreachable',
    invite_expired: 'chat.fedMenu.inviteHints.inviteExpired',
    invite_not_active: 'chat.fedMenu.inviteHints.inviteNotActive',
    peer_mismatch: 'chat.fedMenu.inviteHints.peerMismatch',
  }

  const key = keyMap[meta.error_code]
  return key ? translate(t, key) : ''
}

export function buildPeerHealthLabel(code = '', t) {
  const v = safeString(code).trim()
  if (v === 'ok') return { status: 'ok', label: translate(t, 'chat.fedMenu.health.ok') }
  if (v === 'token_invalid') return { status: 'bad', label: translate(t, 'chat.fedMenu.health.tokenInvalid') }
  if (v === 'owner_unreachable') return { status: 'bad', label: translate(t, 'chat.fedMenu.health.ownerUnreachable') }
  if (v === 'permission_denied') return { status: 'warn', label: translate(t, 'chat.fedMenu.health.permissionDenied') }
  if (v === 'peer_not_found') return { status: 'warn', label: translate(t, 'chat.fedMenu.health.peerNotFound') }
  if (v === 'checking') return { status: 'unknown', label: translate(t, 'chat.fedMenu.health.checking') }
  if (v) return { status: 'warn', label: v }
  return { status: 'unknown', label: translate(t, 'chat.fedMenu.health.unknown') }
}

export function buildAcceptSuccessMessage(roomId, peerId, t) {
  const rid = safeString(roomId).trim()
  const pid = safeString(peerId).trim()
  const parts = [translate(t, 'chat.fedMenu.success.acceptedRoomInvite')]
  if (rid) parts.push(`Room ID: ${rid}`)
  if (pid) parts.push(`Peer: ${pid}`)
  return parts.join(' ')
}

export function maskInviteToken(token = '') {
  const t = safeString(token).trim()
  if (!t) return ''
  if (t.length <= 12) return t
  return `${t.slice(0, 8)}...${t.slice(-4)}`
}

export function unwrapMarkdownLinkUrl(value = '') {
  const raw = safeString(value).trim()
  if (!raw) return ''

  const exactMd = raw.match(/^\[[^\]]*]\((https?:\/\/[^)\s]+)\)$/i)
  if (exactMd?.[1]) return exactMd[1].trim()

  const inlineMd = raw.match(/\((https?:\/\/[^)\s]+)\)/i)
  if (inlineMd?.[1]) return inlineMd[1].trim()

  return raw
}

export function normalizeBaseUrl(value = '') {
  const raw0 = safeString(value).trim()
  if (!raw0) return ''

  const raw = unwrapMarkdownLinkUrl(raw0)

  try {
    const u = new URL(raw)
    return `${u.origin}`.replace(/\/$/, '')
  } catch (_) {
    // Ignore invalid direct URL and try extraction patterns below.
  }

  const mcpUrlMatch = raw.match(/(https?:\/\/[^\s)\]]+\/api\/mcp\/call)\b/i)
  if (mcpUrlMatch?.[1]) {
    try {
      return new URL(mcpUrlMatch[1]).origin.replace(/\/$/, '')
    } catch (_) {
      // Ignore invalid MCP URL match and continue.
    }
  }

  const urlMatch = raw.match(/https?:\/\/[^\s)\]]+/i)
  if (urlMatch?.[0]) {
    try {
      return new URL(urlMatch[0]).origin.replace(/\/$/, '')
    } catch (_) {
      return urlMatch[0].replace(/\/+$/, '')
    }
  }

  return raw.replace(/\/+$/, '')
}

export function buildDraftKey(row = {}) {
  const src = safeObject(row)
  return [
    safeString(src.peer_id).trim(),
    safeString(src.room_id).trim(),
    safeString(src.invite_token).trim(),
    safeString(src.remote_user_id).trim(),
    safeString(src.target_peer_id).trim(),
  ].join('::')
}

export function normalizeInfoKey(key = '') {
  return safeString(key).trim().toLowerCase().replace(/[^a-z0-9]/g, '')
}

export function setParsedValue(dst, key, value) {
  const v = safeString(value).trim()
  if (!v) return

  const k = normalizeInfoKey(key)
  if (!k) return

  if (['peerid', 'ownerpeerid'].includes(k)) dst.peer_id = v
  else if (['baseurl', 'ownerbaseurl', 'origin', 'url'].includes(k)) dst.base_url = normalizeBaseUrl(v)
  else if (['token', 'bearer', 'authorization'].includes(k)) {
    const m = v.match(/bearer\s+([^\s]+)/i)
    dst.token = m ? m[1] : v
  }
  else if (['label', 'peerlabel'].includes(k)) dst.label = v
  else if ([
    'remoteuserid',
    'userid',
    'owneruserid',
    'localowneruserid',
  ].includes(k)) dst.remote_user_id = v
  else if (['remotelabel', 'name', 'displayname', 'ownername'].includes(k)) dst.remote_label = v
  else if (['roomid'].includes(k)) dst.room_id = v
  else if (['invitetoken'].includes(k)) dst.invite_token = v
  else if (['targetpeerid'].includes(k)) dst.target_peer_id = v
}

export function parseFederationInfo(raw = '') {
  const text = stripCodeFence(raw)
  const out = {
    peer_id: '',
    base_url: '',
    token: '',
    label: '',
    remote_user_id: '',
    remote_label: '',
    room_id: '',
    invite_token: '',
    target_peer_id: '',
  }

  if (!text) return out

  try {
    const maybeJson = JSON.parse(text)
    const src = safeObject(maybeJson)
    const bags = [
      src,
      safeObject(src.peer),
      safeObject(src.invite),
      safeObject(src.owner),
    ]

    for (const bag of bags) {
      setParsedValue(out, 'peer_id', bag.peer_id || bag.owner_peer_id)
      setParsedValue(out, 'base_url', bag.base_url || bag.owner_base_url || bag.origin || bag.url)
      setParsedValue(out, 'token', bag.token || bag.authorization)
      setParsedValue(out, 'label', bag.label || bag.peer_label)
      setParsedValue(
        out,
        'remote_user_id',
        bag.remote_user_id || bag.user_id || bag.owner_user_id || bag.local_owner_user_id
      )
      setParsedValue(out, 'remote_label', bag.remote_label || bag.name || bag.owner_name)
      setParsedValue(out, 'room_id', bag.room_id)
      setParsedValue(out, 'invite_token', bag.invite_token)
      setParsedValue(out, 'target_peer_id', bag.target_peer_id)
    }
  } catch (_) {
    // Ignore invalid JSON and fall back to line-based parsing.
  }

  const lines = text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
  for (const line of lines) {
    const kv = line.match(/^([A-Za-z0-9_. -]+)\s*[:=]\s*(.+)$/)
    if (kv) {
      setParsedValue(out, kv[1], kv[2])
      continue
    }

    if (/^authorization\b/i.test(line)) {
      setParsedValue(out, 'authorization', line)
      continue
    }

    if (/^bearer\s+/i.test(line)) {
      setParsedValue(out, 'token', line)
      continue
    }
  }

  if (!out.token) {
    const tokenMatch = text.match(/Bearer\s+([A-Za-z0-9._-]+)/i)
    if (tokenMatch?.[1]) out.token = tokenMatch[1]
  }

  if (!out.invite_token) {
    const inviteMatch = text.match(/\bfedrt_[A-Za-z0-9]+\b/i)
    if (inviteMatch?.[0]) out.invite_token = inviteMatch[0]
  }

  if (!out.room_id) {
    const roomMatch = text.match(/\broom_[A-Za-z0-9_]+\b/i)
    if (roomMatch?.[0]) out.room_id = roomMatch[0]
  }

  if (!out.base_url) {
    const urlMatch = text.match(/https?:\/\/[^\s)\]]+/i)
    if (urlMatch?.[0]) {
      try {
        out.base_url = new URL(urlMatch[0]).origin
      } catch (_) {
        out.base_url = normalizeBaseUrl(urlMatch[0])
      }
    }
  }

  if (!out.base_url) {
    const postMatch = text.match(/POST[\s\S]*?(https?:\/\/[^\s)\]]+\/api\/mcp\/call)/i)
    if (postMatch?.[1]) {
      try {
        out.base_url = new URL(postMatch[1]).origin
      } catch (_) {
        // Ignore invalid POST URL match.
      }
    }
  }

  if (!out.base_url) {
    const originMatch = text.match(/\bOrigin\b[\s:]+(https?:\/\/[^\s)\]]+)/i)
    if (originMatch?.[1]) out.base_url = normalizeBaseUrl(originMatch[1])
  }

  return out
}
