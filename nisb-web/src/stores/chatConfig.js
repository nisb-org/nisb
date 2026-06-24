// /opt/mcp-gateway/nisb-web/src/stores/chatConfig.js
import { defineStore } from 'pinia'

const LS_CHAT_MODE_KEYS = ['nisb_chat_mode', 'nisbchatmode']
const LS_CHAT_ROOM_KEYS = ['nisb_chat_room_id', 'nisbchatroomid', 'nisb_chatroomid']
const LS_CHAT_CONVERSATION_MODEL = 'nisb_chat_conversation_model'

const LS_MCP_FS_READ_SCOPE_KEYS = ['nisb_mcp_fs_read_scope', 'nisbmcpfsreadscope']
const LS_MCP_FS_WRITE_SCOPE_KEYS = ['nisb_mcp_fs_write_scope', 'nisbmcpfswritescope']
const LS_MCP_FS_DANGEROUS_ENABLED_KEYS = ['nisb_mcp_fs_dangerous_enabled', 'nisbmcpfsdangerousenabled']
const LS_MCP_FS_WRITE_SCOPE_USER_SET_KEYS = [
  'nisb_mcp_fs_write_scope_user_set',
  'nisbmcpfswritescopeuserset'
]

const LS_RSS_ENABLED_USER_SET_KEYS = [
  'nisb_rss_enabled_user_set',
  'nisbrssenableduserset'
]

const DEFAULT_MCP_FS_READ_SCOPE = 'user_ro'
const DEFAULT_MCP_FS_WRITE_SCOPE = 'agent_files'
const DEFAULT_MCP_FS_DANGEROUS_ENABLED = false

function ls_get_first(keys) {
  for (const k of keys) {
    const v = localStorage.getItem(k)
    if (v !== null && String(v).trim() !== '') return String(v)
  }
  return null
}

function ls_set_all(keys, val) {
  for (const k of keys) localStorage.setItem(k, String(val ?? ''))
}

function normalize_scope(v) {
  const s = String(v || 'global').trim().toLowerCase()
  return s === 'doc' || s === 'library' ? s : 'global'
}

function normalize_nullable_id(v) {
  const s = String(v || '').trim()
  return s || null
}

function normalize_fs_read_scope(v) {
  const s = String(v || DEFAULT_MCP_FS_READ_SCOPE).trim().toLowerCase()
  if (s === 'minimal') return 'minimal'
  return 'user_ro'
}

function normalize_fs_write_scope(v) {
  const s = String(v ?? '').trim().toLowerCase()
  if (!s) return DEFAULT_MCP_FS_WRITE_SCOPE
  if (s === 'agent_files' || s === 'agentfiles') return 'agent_files'
  if (s === 'none') return 'none'
  return DEFAULT_MCP_FS_WRITE_SCOPE
}

function normalize_bool_string(v, fallback = false) {
  if (typeof v === 'boolean') return v
  const s = String(v ?? '').trim().toLowerCase()
  if (!s) return !!fallback
  return s === 'true' || s === '1' || s === 'yes' || s === 'on'
}

function normalize_doc_time_mode(v) {
  const s = String(v || 'days').trim().toLowerCase()
  return s === 'relative' ? 'relative' : 'days'
}

function normalize_nullable_non_negative_int(v, fallback = null) {
  if (v === null || v === undefined) return fallback
  const s = String(v).trim()
  if (!s) return fallback

  let n = parseInt(s, 10)
  if (Number.isNaN(n)) return fallback
  n = Math.max(0, Math.min(3650, n))
  return n
}

function normalize_bounded_int(v, fallback, min, max) {
  let n = parseInt(v, 10)
  if (Number.isNaN(n)) n = fallback
  return Math.max(min, Math.min(max, n))
}

function normalize_rss_min_score(v, fallback = 0.28) {
  let x = Number(v)
  if (Number.isNaN(x)) x = fallback
  x = Math.max(0.0, Math.min(1.0, x))
  return Math.round(x * 100) / 100
}

function default_doc_time() {
  return {
    enabled: false,
    mode: 'days',
    days: 3,
    relative: {
      olderDaysAgo: 30,
      newerDaysAgo: 21,
    },
  }
}

function normalize_doc_time_relative(raw = {}) {
  let olderDaysAgo = normalize_nullable_non_negative_int(raw?.olderDaysAgo, 30)
  let newerDaysAgo = normalize_nullable_non_negative_int(raw?.newerDaysAgo, 21)

  if (olderDaysAgo === null && newerDaysAgo === null) {
    olderDaysAgo = 30
    newerDaysAgo = 21
  }

  if (
    olderDaysAgo !== null &&
    newerDaysAgo !== null &&
    olderDaysAgo < newerDaysAgo
  ) {
    const tmp = olderDaysAgo
    olderDaysAgo = newerDaysAgo
    newerDaysAgo = tmp
  }

  return {
    olderDaysAgo,
    newerDaysAgo,
  }
}

function default_rss_reference() {
  return {
    enabled: false,
    days: 7,
    limit: 8,
    minScore: 0.28,
    strictLexical: true,
  }
}

function normalize_rss_reference(raw = {}) {
  return {
    enabled: normalize_bool_string(raw?.enabled, false),
    days: normalize_bounded_int(raw?.days, 7, 0, 3650),
    limit: normalize_bounded_int(raw?.limit, 8, 1, 20),
    minScore: normalize_rss_min_score(raw?.minScore, 0.28),
    strictLexical: normalize_bool_string(raw?.strictLexical, true),
  }
}

function scope_rank(v) {
  const s = normalize_scope(v)
  if (s === 'doc') return 2
  if (s === 'library') return 1
  return 0
}

function max_scope(a, b) {
  return scope_rank(a) >= scope_rank(b) ? normalize_scope(a) : normalize_scope(b)
}

function infer_scope_from_context({ libraryId, docId, group_id } = {}) {
  const lib = normalize_nullable_id(libraryId)
  const doc = normalize_nullable_id(docId)
  const gid = normalize_nullable_id(group_id)

  if (lib && doc) return 'doc'
  if (lib) return 'library'
  if (gid) return 'global'
  return 'global'
}

function sanitize_rag_state({
  storeScope,
  evidenceScope,
  context,
} = {}) {
  let ss = normalize_scope(storeScope)
  let es = normalize_scope(evidenceScope)

  let libraryId = normalize_nullable_id(context?.libraryId)
  let docId = normalize_nullable_id(context?.docId)
  let group_id = normalize_nullable_id(context?.group_id)

  const requestedScope = max_scope(ss, es)

  if (requestedScope === 'doc') {
    if (libraryId && docId) {
      group_id = null
      return {
        storeScope: ss,
        evidenceScope: es,
        context: {
          libraryId,
          docId,
          group_id: null,
        },
      }
    }

    const fallback = infer_scope_from_context({ libraryId, docId, group_id })
    ss = ss === 'doc' ? fallback : ss
    es = es === 'doc' ? fallback : es
  }

  if (max_scope(ss, es) === 'library') {
    docId = null

    if (!libraryId && !group_id) {
      ss = ss === 'library' ? 'global' : ss
      es = es === 'library' ? 'global' : es
    }

    return {
      storeScope: normalize_scope(ss),
      evidenceScope: normalize_scope(es),
      context: {
        libraryId,
        docId: null,
        group_id,
      },
    }
  }

  return {
    storeScope: normalize_scope(ss),
    evidenceScope: normalize_scope(es),
    context: {
      libraryId: null,
      docId: null,
      group_id,
    },
  }
}

export const useChatConfigStore = defineStore('chatConfig', {
  state: () => ({
    mcp: {
      serperEnabled: false,
      codeNetworkEnabled: false,
      fsReadScope: DEFAULT_MCP_FS_READ_SCOPE,
      fsWriteScope: DEFAULT_MCP_FS_WRITE_SCOPE,
      fsDangerousEnabled: DEFAULT_MCP_FS_DANGEROUS_ENABLED
    },

    rag: {
      mode: 'off',
      storeScope: 'global',
      evidenceScope: 'global',
      context: {
        libraryId: null,
        docId: null,
        group_id: null
      },
      external: {
        marketEnabled: false,
        peerTargets: []
      },

      // 正式：Doc-RAG 检索时间范围
      docTime: default_doc_time(),

      // 正式：RSS 引用范围 / 展示范围
      rssReference: default_rss_reference(),

      // 兼容：历史调用仍可读 rag.rss
      rss: default_rss_reference(),
    },

    chat: {
      mode: 'llm',
      roomId: ''
    },

    models: {
      conversationModel: 'gpt-4o-mini'
    }
  }),

  actions: {
    _persistRagContext() {
      localStorage.setItem('nisb_rag_context', JSON.stringify(this.rag.context))
      localStorage.setItem('nisbragcontext', JSON.stringify(this.rag.context))
    },

    _persistRagScopes() {
      localStorage.setItem('nisb_rag_store_scope', this.rag.storeScope)
      localStorage.setItem('nisb_rag_evidence_scope', this.rag.evidenceScope)
      localStorage.setItem('nisbragstorescope', this.rag.storeScope)
      localStorage.setItem('nisbragevidencescope', this.rag.evidenceScope)
    },

    _persistMcpFsScopes(opts = {}) {
      const markWriteScopeUserSet = !!opts.markWriteScopeUserSet

      this.mcp.fsReadScope = normalize_fs_read_scope(this.mcp.fsReadScope)
      this.mcp.fsWriteScope = normalize_fs_write_scope(this.mcp.fsWriteScope)

      if (this.mcp.fsWriteScope === 'none') {
        this.mcp.fsDangerousEnabled = false
      } else {
        this.mcp.fsDangerousEnabled = !!this.mcp.fsDangerousEnabled
      }

      ls_set_all(LS_MCP_FS_READ_SCOPE_KEYS, this.mcp.fsReadScope)
      ls_set_all(LS_MCP_FS_WRITE_SCOPE_KEYS, this.mcp.fsWriteScope)
      ls_set_all(LS_MCP_FS_DANGEROUS_ENABLED_KEYS, String(this.mcp.fsDangerousEnabled))

      if (markWriteScopeUserSet) {
        ls_set_all(LS_MCP_FS_WRITE_SCOPE_USER_SET_KEYS, 'true')
      }
    },

    _applySanitizedRagState({ storeScope, evidenceScope, context }) {
      const fixed = sanitize_rag_state({
        storeScope,
        evidenceScope,
        context,
      })

      this.rag.storeScope = fixed.storeScope
      this.rag.evidenceScope = fixed.evidenceScope
      this.rag.context = {
        libraryId: fixed.context.libraryId,
        docId: fixed.context.docId,
        group_id: fixed.context.group_id,
      }

      this._persistRagContext()
      this._persistRagScopes()
    },

    _syncRssReferenceCompat() {
      const fixed = normalize_rss_reference(this.rag.rssReference || {})
      this.rag.rssReference = { ...fixed }
      this.rag.rss = { ...fixed }
    },

    _persistRssReference(opts = {}) {
      const markEnabledUserSet = !!opts.markEnabledUserSet

      this._syncRssReferenceCompat()

      localStorage.setItem('nisb_rss_enabled', String(this.rag.rssReference.enabled))
      localStorage.setItem('nisb_rss_days', String(this.rag.rssReference.days))
      localStorage.setItem('nisb_rss_limit', String(this.rag.rssReference.limit))
      localStorage.setItem('nisb_rss_min_score', String(this.rag.rssReference.minScore))
      localStorage.setItem('nisb_rss_strict_lexical', String(this.rag.rssReference.strictLexical))

      localStorage.setItem('nisbrssenabled', String(this.rag.rssReference.enabled))
      localStorage.setItem('nisbrssdays', String(this.rag.rssReference.days))
      localStorage.setItem('nisbrsslimit', String(this.rag.rssReference.limit))
      localStorage.setItem('nisbrssminscore', String(this.rag.rssReference.minScore))
      localStorage.setItem('nisbrssstrictlexical', String(this.rag.rssReference.strictLexical))

      if (markEnabledUserSet) {
        ls_set_all(LS_RSS_ENABLED_USER_SET_KEYS, 'true')
      }
    },

    _setRssReferenceState(raw, { persist = true, markEnabledUserSet = false } = {}) {
      this.rag.rssReference = normalize_rss_reference(raw || {})
      this._syncRssReferenceCompat()
      if (persist) this._persistRssReference({ markEnabledUserSet })
    },

    setConversationModel(model) {
      const v = String(model || '').trim() || 'gpt-4o-mini'
      this.models.conversationModel = v
      localStorage.setItem(LS_CHAT_CONVERSATION_MODEL, v)
    },

    setSerperEnabled(val) {
      this.mcp.serperEnabled = !!val
      localStorage.setItem('nisb_mcp_serper_enabled', String(this.mcp.serperEnabled))
      localStorage.setItem('nisbmcpserperenabled', String(this.mcp.serperEnabled))
    },

    setCodeNetworkEnabled(val) {
      this.mcp.codeNetworkEnabled = !!val
      localStorage.setItem('nisb_mcp_code_network_enabled', String(this.mcp.codeNetworkEnabled))
      localStorage.setItem('nisbmcpcodenetworkenabled', String(this.mcp.codeNetworkEnabled))
    },

    setFsReadScope(val) {
      this.mcp.fsReadScope = normalize_fs_read_scope(val)
      this._persistMcpFsScopes()
    },

    setFsWriteScope(val) {
      this.mcp.fsWriteScope = normalize_fs_write_scope(val)
      if (this.mcp.fsWriteScope === 'none') this.mcp.fsDangerousEnabled = false
      this._persistMcpFsScopes({ markWriteScopeUserSet: true })
    },

    setFsDangerousEnabled(val) {
      this.mcp.fsDangerousEnabled = !!val
      if (this.mcp.fsWriteScope === 'none') this.mcp.fsDangerousEnabled = false
      this._persistMcpFsScopes()
    },

    setRagMode(mode) {
      const m = String(mode || 'off').trim().toLowerCase()
      this.rag.mode = ['off', 'cite', 'ground', 'web', 'auto'].includes(m) ? m : 'off'
      localStorage.setItem('nisb_rag_mode', this.rag.mode)
      localStorage.setItem('nisbragmode', this.rag.mode)
    },

    setRagScopes({ storeScope, evidenceScope }) {
      this._applySanitizedRagState({
        storeScope: storeScope ?? this.rag.storeScope,
        evidenceScope: evidenceScope ?? this.rag.evidenceScope,
        context: this.rag.context,
      })
    },

    setRagContext({ libraryId, docId, group_id, storeScope, evidenceScope }) {
      const explicitStoreScope = storeScope ? normalize_scope(storeScope) : null
      const explicitEvidenceScope = evidenceScope ? normalize_scope(evidenceScope) : null

      const rawContext = {
        libraryId: normalize_nullable_id(libraryId),
        docId: normalize_nullable_id(docId),
        group_id: normalize_nullable_id(group_id),
      }

      const inferredScope = infer_scope_from_context(rawContext)
      const nextStoreScope = explicitStoreScope || inferredScope
      const nextEvidenceScope = explicitEvidenceScope || nextStoreScope

      this._applySanitizedRagState({
        storeScope: nextStoreScope,
        evidenceScope: nextEvidenceScope,
        context: rawContext,
      })
    },

    clearRagContext() {
      this._applySanitizedRagState({
        storeScope: 'global',
        evidenceScope: 'global',
        context: {
          libraryId: null,
          docId: null,
          group_id: null,
        },
      })
    },

    setMarketEnabled(val) {
      this.rag.external.marketEnabled = !!val
      localStorage.setItem('nisb_external_market_enabled', String(this.rag.external.marketEnabled))
      localStorage.setItem('nisbexternalmarketenabled', String(this.rag.external.marketEnabled))
    },

    setPeerTargets(list) {
      const arr = Array.isArray(list)
        ? list.map((s) => String(s || '').trim()).filter(Boolean)
        : []
      this.rag.external.peerTargets = Array.from(new Set(arr))
      localStorage.setItem('nisb_external_peer_targets', JSON.stringify(this.rag.external.peerTargets))
      localStorage.setItem('nisbexternalpeertargets', JSON.stringify(this.rag.external.peerTargets))
    },

    togglePeerTarget(peerId) {
      const id = String(peerId || '').trim()
      if (!id) return
      const s = new Set(Array.isArray(this.rag.external.peerTargets) ? this.rag.external.peerTargets : [])
      if (s.has(id)) s.delete(id)
      else s.add(id)
      this.setPeerTargets(Array.from(s))
    },

    // Doc-RAG 正式时间范围
    setDocTimeEnabled(val) {
      this.rag.docTime.enabled = !!val
      localStorage.setItem('nisb_doc_time_enabled', String(this.rag.docTime.enabled))
      localStorage.setItem('nisbdoctimeenabled', String(this.rag.docTime.enabled))
    },

    setDocTimeMode(mode) {
      this.rag.docTime.mode = normalize_doc_time_mode(mode)
      localStorage.setItem('nisb_doc_time_mode', this.rag.docTime.mode)
      localStorage.setItem('nisbdoctimemode', String(this.rag.docTime.mode))
    },

    setDocTimeDays(days) {
      let n = parseInt(days, 10)
      if (Number.isNaN(n)) n = 3
      n = Math.max(0, Math.min(3650, n))
      this.rag.docTime.days = n
      localStorage.setItem('nisb_doc_time_days', String(this.rag.docTime.days))
      localStorage.setItem('nisbdoctimedays', String(this.rag.docTime.days))
    },

    setDocTimeRelativeRange({ olderDaysAgo, newerDaysAgo }) {
      const fixed = normalize_doc_time_relative({ olderDaysAgo, newerDaysAgo })
      this.rag.docTime.relative = {
        olderDaysAgo: fixed.olderDaysAgo,
        newerDaysAgo: fixed.newerDaysAgo,
      }
      localStorage.setItem('nisb_doc_time_relative', JSON.stringify(this.rag.docTime.relative))
      localStorage.setItem('nisbdoctimerelative', JSON.stringify(this.rag.docTime.relative))
    },

    resetDocTimeDefaults() {
      this.rag.docTime = default_doc_time()

      localStorage.setItem('nisb_doc_time_enabled', 'false')
      localStorage.setItem('nisb_doc_time_mode', 'days')
      localStorage.setItem('nisb_doc_time_days', '3')
      localStorage.setItem('nisb_doc_time_relative', JSON.stringify(this.rag.docTime.relative))

      localStorage.setItem('nisbdoctimeenabled', 'false')
      localStorage.setItem('nisbdoctimemode', 'days')
      localStorage.setItem('nisbdoctimedays', '3')
      localStorage.setItem('nisbdoctimerelative', JSON.stringify(this.rag.docTime.relative))
    },

    // RSS 引用范围（正式命名）
    setRssReferenceEnabled(val) {
      this._setRssReferenceState(
        {
          ...this.rag.rssReference,
          enabled: !!val,
        },
        { markEnabledUserSet: true }
      )
    },

    setRssReferenceDays(days) {
      this._setRssReferenceState({
        ...this.rag.rssReference,
        days: normalize_bounded_int(days, 7, 0, 3650),
      })
    },

    setRssReferenceLimit(limit) {
      this._setRssReferenceState({
        ...this.rag.rssReference,
        limit: normalize_bounded_int(limit, 8, 1, 20),
      })
    },

    setRssReferenceMinScore(v) {
      this._setRssReferenceState({
        ...this.rag.rssReference,
        minScore: normalize_rss_min_score(v, 0.28),
      })
    },

    setRssReferenceStrictLexical(val) {
      this._setRssReferenceState({
        ...this.rag.rssReference,
        strictLexical: !!val,
      })
    },

    resetRssReferenceDefaults() {
      this._setRssReferenceState(default_rss_reference(), {
        markEnabledUserSet: true,
      })
    },

    // 兼容旧调用
    setRssEnabled(val) {
      this.setRssReferenceEnabled(val)
    },

    setRssDays(days) {
      this.setRssReferenceDays(days)
    },

    setRssLimit(limit) {
      this.setRssReferenceLimit(limit)
    },

    setRssMinScore(v) {
      this.setRssReferenceMinScore(v)
    },

    setRssStrictLexical(val) {
      this.setRssReferenceStrictLexical(val)
    },

    resetRssDefaults() {
      this.resetRssReferenceDefaults()
    },

    setChatMode(mode) {
      const m = String(mode || 'llm').trim().toLowerCase()
      this.chat.mode = m === 'room' ? 'room' : 'llm'
      ls_set_all(LS_CHAT_MODE_KEYS, this.chat.mode)
      if (this.chat.mode !== 'room') {
        this.chat.roomId = ''
        ls_set_all(LS_CHAT_ROOM_KEYS, '')
      }
    },

    setRoomId(roomId) {
      this.chat.roomId = String(roomId || '').trim()
      ls_set_all(LS_CHAT_ROOM_KEYS, this.chat.roomId)
    },

    enterRoom(roomId) {
      const rid = String(roomId || '').trim()
      if (!rid) return
      this.chat.mode = 'room'
      this.chat.roomId = rid
      ls_set_all(LS_CHAT_MODE_KEYS, 'room')
      ls_set_all(LS_CHAT_ROOM_KEYS, rid)
    },

    exitRoomHard() {
      this.chat.mode = 'llm'
      this.chat.roomId = ''
      ls_set_all(LS_CHAT_MODE_KEYS, 'llm')
      ls_set_all(LS_CHAT_ROOM_KEYS, '')
    },

    hydrate() {
      const cm = localStorage.getItem(LS_CHAT_CONVERSATION_MODEL)
      if (cm !== null && String(cm).trim()) {
        this.models.conversationModel = String(cm).trim()
      } else {
        this.models.conversationModel = 'gpt-4o-mini'
      }

      const v = localStorage.getItem('nisb_mcp_serper_enabled') ?? localStorage.getItem('nisbmcpserperenabled')
      if (v !== null) this.mcp.serperEnabled = (v === 'true')

      const v2 = localStorage.getItem('nisb_mcp_code_network_enabled') ?? localStorage.getItem('nisbmcpcodenetworkenabled')
      if (v2 !== null) this.mcp.codeNetworkEnabled = (v2 === 'true')

      const r = ls_get_first(LS_MCP_FS_READ_SCOPE_KEYS)
      this.mcp.fsReadScope = normalize_fs_read_scope(r)

      const w = ls_get_first(LS_MCP_FS_WRITE_SCOPE_KEYS)
      const writeScopeUserSet = ls_get_first(LS_MCP_FS_WRITE_SCOPE_USER_SET_KEYS) === 'true'
      const normalizedWrite = normalize_fs_write_scope(w)

      if (w === null) {
        this.mcp.fsWriteScope = DEFAULT_MCP_FS_WRITE_SCOPE
      } else if (!writeScopeUserSet && normalizedWrite === 'none') {
        this.mcp.fsWriteScope = DEFAULT_MCP_FS_WRITE_SCOPE
      } else {
        this.mcp.fsWriteScope = normalizedWrite
      }

      const d = ls_get_first(LS_MCP_FS_DANGEROUS_ENABLED_KEYS)
      this.mcp.fsDangerousEnabled = normalize_bool_string(d, DEFAULT_MCP_FS_DANGEROUS_ENABLED)

      if (this.mcp.fsWriteScope === 'none') this.mcp.fsDangerousEnabled = false
      this._persistMcpFsScopes({ markWriteScopeUserSet: writeScopeUserSet })

      const rm = localStorage.getItem('nisb_rag_mode') ?? localStorage.getItem('nisbragmode')
      if (['off', 'cite', 'ground', 'web', 'auto'].includes(String(rm || ''))) this.rag.mode = String(rm)

      const ss = localStorage.getItem('nisb_rag_store_scope') ?? localStorage.getItem('nisbragstorescope')
      if (['doc', 'library', 'global'].includes(String(ss || ''))) this.rag.storeScope = String(ss)
      else this.rag.storeScope = 'global'

      const es = localStorage.getItem('nisb_rag_evidence_scope') ?? localStorage.getItem('nisbragevidencescope')
      if (['doc', 'library', 'global'].includes(String(es || ''))) this.rag.evidenceScope = String(es)
      else this.rag.evidenceScope = 'global'

      const ctxRaw = localStorage.getItem('nisb_rag_context') ?? localStorage.getItem('nisbragcontext')
      if (ctxRaw) {
        try {
          const ctx = JSON.parse(ctxRaw)
          this.rag.context = {
            libraryId: normalize_nullable_id(ctx?.libraryId),
            docId: normalize_nullable_id(ctx?.docId),
            group_id: normalize_nullable_id(ctx?.group_id)
          }
        } catch {
          this.rag.context = { libraryId: null, docId: null, group_id: null }
        }
      } else {
        this.rag.context = { libraryId: null, docId: null, group_id: null }
      }

      this._applySanitizedRagState({
        storeScope: this.rag.storeScope,
        evidenceScope: this.rag.evidenceScope,
        context: this.rag.context,
      })

      const me = localStorage.getItem('nisb_external_market_enabled') ?? localStorage.getItem('nisbexternalmarketenabled')
      if (me !== null) this.rag.external.marketEnabled = (me === 'true')

      const pt = localStorage.getItem('nisb_external_peer_targets') ?? localStorage.getItem('nisbexternalpeertargets')
      if (pt) {
        try {
          this.rag.external.peerTargets = JSON.parse(pt)
        } catch {
          this.rag.external.peerTargets = []
        }
        if (!Array.isArray(this.rag.external.peerTargets)) this.rag.external.peerTargets = []
      }

      const dte = localStorage.getItem('nisb_doc_time_enabled') ?? localStorage.getItem('nisbdoctimeenabled')
      if (dte !== null) this.rag.docTime.enabled = (dte === 'true')

      const dtm = localStorage.getItem('nisb_doc_time_mode') ?? localStorage.getItem('nisbdoctimemode')
      if (dtm !== null) {
        this.rag.docTime.mode = normalize_doc_time_mode(dtm)
      } else {
        this.rag.docTime.mode = 'days'
      }

      const dtd = localStorage.getItem('nisb_doc_time_days') ?? localStorage.getItem('nisbdoctimedays')
      if (dtd !== null) this.setDocTimeDays(dtd)

      const dtr = localStorage.getItem('nisb_doc_time_relative') ?? localStorage.getItem('nisbdoctimerelative')
      if (dtr) {
        try {
          this.rag.docTime.relative = normalize_doc_time_relative(JSON.parse(dtr))
        } catch {
          this.rag.docTime.relative = default_doc_time().relative
        }
      } else {
        this.rag.docTime.relative = default_doc_time().relative
      }

      const rssEnabledUserSet = ls_get_first(LS_RSS_ENABLED_USER_SET_KEYS) === 'true'

      const re = localStorage.getItem('nisb_rss_enabled') ?? localStorage.getItem('nisbrssenabled')
      const rd = localStorage.getItem('nisb_rss_days') ?? localStorage.getItem('nisbrssdays')
      const rl = localStorage.getItem('nisb_rss_limit') ?? localStorage.getItem('nisbrsslimit')
      const rs = localStorage.getItem('nisb_rss_min_score') ?? localStorage.getItem('nisbrssminscore')
      const rsl = localStorage.getItem('nisb_rss_strict_lexical') ?? localStorage.getItem('nisbrssstrictlexical')

      this._setRssReferenceState(
        {
          enabled: rssEnabledUserSet
            ? (re !== null ? (re === 'true') : false)
            : false,
          days: rd !== null ? rd : 7,
          limit: rl !== null ? rl : 8,
          minScore: rs !== null ? rs : 0.28,
          strictLexical: rsl !== null ? (rsl === 'true') : true,
        },
        { persist: false }
      )
      this._persistRssReference({ markEnabledUserSet: rssEnabledUserSet })

      const chatMode = ls_get_first(LS_CHAT_MODE_KEYS)
      const roomId = ls_get_first(LS_CHAT_ROOM_KEYS)
      if (chatMode === 'room') {
        this.chat.mode = 'room'
        this.chat.roomId = roomId ? String(roomId) : ''
      } else {
        this.chat.mode = 'llm'
        this.chat.roomId = ''
      }
    }
  }
})
