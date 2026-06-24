import { ref } from 'vue'
import {
  ensureFsCapabilityGateDefaults,
  mergeMcpToolArgs
} from './mcp/use_mcp_capability_gate.js'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const CHAT_CALL_TOOLS = new Set([
  'nisb_chat_send',
  'nisb_chat_orchestrate'
])

const CHAT_STREAM_TOOLS = new Set([
  'nisb_chat_send',
  'nisb_chat_orchestrate'
])

const CHAT_LEGACY_KEYS = [
  'convid',
  'requestid',
  'ragmode',
  'mcpoverrides',
  'modeused',
  'rssevidence',
  'marketevidence',
  'evidencequery',
  'evidencetools',
  'evidenceresult',
  'qaid',
  'groupid',
  'toolcalls',
  'toolresults'
]

const CHAT_ALIAS_KEYS = ['content', 'text', 'delta', 'error']

function normalizeToken(raw) {
  const t = String(raw || '').trim()
  if (!t || t === 'undefined' || t === 'null') return ''
  return t.startsWith('Bearer ') ? t : `Bearer ${t}`
}

function getTokenRaw() {
  return (
    localStorage.getItem('nisb_token') ||
    localStorage.getItem('nisb-token') ||
    localStorage.getItem('nisb_access_token') ||
    localStorage.getItem('access_token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('Authorization') ||
    ''
  )
}

function getToken() {
  return normalizeToken(getTokenRaw())
}

function _is_chat_call_tool(tool) {
  return CHAT_CALL_TOOLS.has(String(tool || '').trim())
}

function _is_chat_stream_tool(tool) {
  return CHAT_STREAM_TOOLS.has(String(tool || '').trim())
}

function _safeObj(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function _safeArr(v) {
  return Array.isArray(v) ? v : []
}

function _pickFirstText(...vals) {
  for (const v of vals) {
    const s = String(v ?? '').trim()
    if (s) return s
  }
  return ''
}

function _mergeUniqueArrays(...lists) {
  const out = []
  const seen = new Set()

  for (const list of lists) {
    const arr = Array.isArray(list) ? list : []
    for (const item of arr) {
      let key = ''
      try {
        key = JSON.stringify(item)
      } catch {
        key = String(item)
      }
      if (seen.has(key)) continue
      seen.add(key)
      out.push(item)
    }
  }

  return out
}

function _collectEvidenceSources(payload = {}) {
  const out = []

  const pushObj = (v) => {
    const obj = _safeObj(v)
    if (!Object.keys(obj).length) return
    out.push(obj)
  }

  const root = _safeObj(payload)
  pushObj(root)
  pushObj(root.data)
  pushObj(root.result)
  pushObj(root.payload)

  const toolResultBags = [
    root.tool_results,
    root.toolresults,
    root.data?.tool_results,
    root.result?.tool_results,
    root.payload?.tool_results
  ]

  for (const rows of toolResultBags) {
    for (const row of _safeArr(rows)) {
      const r = _safeObj(row)
      pushObj(r)
      pushObj(r.data)
      pushObj(r.result)
      pushObj(r.payload)
    }
  }

  return out
}

function normalizeEvidence(payload) {
  const sources = _collectEvidenceSources(payload)

  if (!sources.length) {
    return {
      conv_id: '',
      citations: [],
      rss_evidence: [],
      market_evidence: [],
      evidence_query: '',
      evidence_tools: [],
      evidence_result: {},
      qa_id: '',
      group_id: ''
    }
  }

  let conv_id = ''
  let citations = []
  let rss_evidence = []
  let market_evidence = []
  let evidence_query = ''
  let evidence_tools = []
  let evidence_result = {}
  let qa_id = ''
  let group_id = ''

  for (const src of sources) {
    if (!conv_id) {
      conv_id = _pickFirstText(src.conv_id, src.convid)
    }

    citations = _mergeUniqueArrays(citations, _safeArr(src.citations))
    rss_evidence = _mergeUniqueArrays(
      rss_evidence,
      _safeArr(src.rss_evidence),
      _safeArr(src.rssevidence)
    )
    market_evidence = _mergeUniqueArrays(
      market_evidence,
      _safeArr(src.market_evidence),
      _safeArr(src.marketevidence)
    )

    if (!evidence_query) {
      evidence_query = _pickFirstText(src.evidence_query, src.evidencequery)
    }

    evidence_tools = _mergeUniqueArrays(
      evidence_tools,
      _safeArr(src.evidence_tools),
      _safeArr(src.evidencetools)
    )

    if (!Object.keys(evidence_result).length) {
      if (src.evidence_result && typeof src.evidence_result === 'object' && !Array.isArray(src.evidence_result)) {
        evidence_result = src.evidence_result
      } else if (src.evidenceresult && typeof src.evidenceresult === 'object' && !Array.isArray(src.evidenceresult)) {
        evidence_result = src.evidenceresult
      }
    }

    if (!qa_id) {
      qa_id = _pickFirstText(src.qa_id, src.qaid)
    }

    if (!group_id) {
      group_id = _pickFirstText(src.group_id, src.groupid)
    }
  }

  return {
    conv_id,
    citations,
    rss_evidence,
    market_evidence,
    evidence_query,
    evidence_tools,
    evidence_result,
    qa_id,
    group_id
  }
}

function dispatchChatEvidence(payload) {
  const d = normalizeEvidence(payload)
  const hasAny =
    (Array.isArray(d.citations) && d.citations.length > 0) ||
    (Array.isArray(d.rss_evidence) && d.rss_evidence.length > 0) ||
    (Array.isArray(d.market_evidence) && d.market_evidence.length > 0) ||
    !!String(d.evidence_query || '').trim() ||
    (Array.isArray(d.evidence_tools) && d.evidence_tools.length > 0) ||
    (d.evidence_result && typeof d.evidence_result === 'object' && Object.keys(d.evidence_result).length > 0)

  if (!hasAny) return

  window.dispatchEvent(new CustomEvent('nisb-chat-evidence', {
    detail: {
      ...d,
      rssevidence: d.rss_evidence,
      marketevidence: d.market_evidence
    }
  }))
}

function unwrapGateway(json) {
  if (!json || typeof json !== 'object') return json

  if (
    json.data &&
    typeof json.data === 'object' &&
    (
      Object.prototype.hasOwnProperty.call(json, 'status') ||
      Object.prototype.hasOwnProperty.call(json, 'success') ||
      Object.keys(json).length <= 3
    )
  ) {
    return json.data
  }

  if (
    json.result &&
    typeof json.result === 'object' &&
    (
      Object.prototype.hasOwnProperty.call(json, 'status') ||
      Object.prototype.hasOwnProperty.call(json, 'success') ||
      Object.keys(json).length <= 3
    )
  ) {
    return json.result
  }

  return json
}

function buildHeaders(extra = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...extra }
  if (token) headers.Authorization = token
  return headers
}

function handle401() {
  localStorage.removeItem('nisb_token')
  localStorage.removeItem('nisb-token')
  localStorage.removeItem('nisb_access_token')
  localStorage.removeItem('access_token')
  localStorage.removeItem('token')
  localStorage.removeItem('Authorization')

  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message: 'Session expired. Please sign in again.', type: 'error' }
    })
  )
  window.location.href = '/login'
}

function makeRequestId() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  } catch {}
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function stableStringify(obj) {
  try {
    if (!obj || typeof obj !== 'object') return String(obj ?? '')
    const keys = Object.keys(obj).sort()
    const out = {}
    for (const k of keys) out[k] = obj[k]
    return JSON.stringify(out)
  } catch {
    return ''
  }
}

function isChatTool(tool) {
  const name = String(tool || '').trim()
  return _is_chat_call_tool(name) || _is_chat_stream_tool(name)
}

function buildChatLightweightDedupeKey(tool, args = {}) {
  const convId = String(args?.conv_id || args?.convid || '').trim()
  const requestId = String(args?.request_id || args?.requestid || '').trim()
  const modeUsed = String(args?.mode_used || args?.modeused || '').trim()
  const ragMode = String(args?.rag_mode || args?.ragmode || '').trim()

  return [
    String(tool || '').trim(),
    convId,
    requestId,
    modeUsed,
    ragMode
  ].join('|')
}

function shouldBypassDedupe(tool, opts = {}) {
  if (opts.dedupe === true) return false
  if (opts.dedupe === false) return true
  return isChatTool(tool)
}

function defaultDedupeKey(tool, args) {
  if (isChatTool(tool)) {
    return buildChatLightweightDedupeKey(tool, args)
  }
  return `${String(tool)}|${stableStringify(args || {})}`
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

function shouldRetryHttp(status) {
  return status === 502 || status === 503 || status === 504
}

async function safeReadJson(res) {
  try {
    return await res.json()
  } catch {
    return {}
  }
}

async function safeReadText(res) {
  try {
    return await res.text()
  } catch {
    return ''
  }
}

function makeAbortError(message) {
  const e = new Error(message || 'Aborted')
  e.name = 'AbortError'
  return e
}

function mergeSignals(a, b) {
  if (!a && !b) return null
  const ac = new AbortController()

  const onAbort = () => {
    if (!ac.signal.aborted) ac.abort()
  }

  if (a) {
    if (a.aborted) onAbort()
    else a.addEventListener('abort', onAbort, { once: true })
  }

  if (b) {
    if (b.aborted) onAbort()
    else b.addEventListener('abort', onAbort, { once: true })
  }

  return ac.signal
}

function normalizeEventName(eventName, payload = {}) {
  const raw = String(
    eventName ||
    payload?.event ||
    payload?.type ||
    'message'
  ).trim().toLowerCase()

  if (raw === 'toolcall') return 'tool_call'
  if (raw === 'toolresult') return 'tool_result'
  if (raw === 'status') return 'meta'
  return raw
}

function hasChatPayload(payload = {}) {
  if (!payload || typeof payload !== 'object') return false

  const keys = [
    'conv_id',
    'convid',
    'request_id',
    'requestid',
    'rag_mode',
    'ragmode',
    'mcp_overrides',
    'mcpoverrides',
    'mode_used',
    'modeused',
    'tool_calls',
    'toolcalls',
    'tool_results',
    'toolresults',
    'citations',
    'rss_evidence',
    'rssevidence',
    'market_evidence',
    'marketevidence',
    'evidence_query',
    'evidencequery',
    'evidence_tools',
    'evidencetools',
    'evidence_result',
    'evidenceresult',
    'qa_id',
    'qaid',
    'group_id',
    'groupid',
    'response'
  ]

  const sources = [
    payload,
    payload?.data,
    payload?.result,
    payload?.payload
  ]

  return sources.some((src) => {
    return src && typeof src === 'object' && keys.some((k) => k in src)
  })
}

function stripChatAliases(obj = {}) {
  const out = { ...obj }
  for (const k of CHAT_LEGACY_KEYS) delete out[k]
  for (const k of CHAT_ALIAS_KEYS) delete out[k]
  return out
}

function normalizeChatPayload(payload = {}) {
  if (!payload || typeof payload !== 'object' || !hasChatPayload(payload)) {
    return payload
  }

  const obj = stripChatAliases(payload)

  obj.request_id = String(payload.request_id || payload.requestid || '')
  obj.conv_id = String(payload.conv_id || payload.convid || '')
  obj.rag_mode = String(payload.rag_mode || payload.ragmode || '')
  obj.mode_used = String(payload.mode_used || payload.modeused || '')
  obj.status = String(payload.status || '')
  obj.message = String(payload.message || payload.error || '')

  obj.mcp_overrides =
    payload.mcp_overrides && typeof payload.mcp_overrides === 'object'
      ? payload.mcp_overrides
      : payload.mcpoverrides && typeof payload.mcpoverrides === 'object'
        ? payload.mcpoverrides
        : {}

  obj.tool_calls = Array.isArray(payload.tool_calls)
    ? payload.tool_calls
    : Array.isArray(payload.toolcalls)
      ? payload.toolcalls
      : []

  obj.tool_results = Array.isArray(payload.tool_results)
    ? payload.tool_results
    : Array.isArray(payload.toolresults)
      ? payload.toolresults
      : []

  obj.citations = Array.isArray(payload.citations) ? payload.citations : []
  obj.rss_evidence = Array.isArray(payload.rss_evidence)
    ? payload.rss_evidence
    : Array.isArray(payload.rssevidence)
      ? payload.rssevidence
      : []
  obj.market_evidence = Array.isArray(payload.market_evidence)
    ? payload.market_evidence
    : Array.isArray(payload.marketevidence)
      ? payload.marketevidence
      : []
  obj.evidence_query = String(payload.evidence_query || payload.evidencequery || '')
  obj.evidence_tools = Array.isArray(payload.evidence_tools)
    ? payload.evidence_tools
    : Array.isArray(payload.evidencetools)
      ? payload.evidencetools
      : []
  obj.evidence_result =
    payload.evidence_result && typeof payload.evidence_result === 'object'
      ? payload.evidence_result
      : payload.evidenceresult && typeof payload.evidenceresult === 'object'
        ? payload.evidenceresult
        : {}
  obj.qa_id = String(payload.qa_id || payload.qaid || '')
  obj.group_id = String(payload.group_id || payload.groupid || '')
  obj.response = String(payload.response || payload.content || payload.text || '')

  return obj
}

function shouldNormalizeChatCall(tool, opts = {}) {
  if (opts.normalize_chat_payload === true) return true
  if (opts.normalize_chat_payload === false) return false
  return _is_chat_call_tool(tool)
}

const inflight = new Map()

function cancelInflight(key, reason = 'canceled') {
  const ent = inflight.get(key)
  if (!ent) return false
  try {
    ent.controller?.abort(reason)
  } catch {}
  inflight.delete(key)
  return true
}

function normalizeStreamPayload(eventName, payload = {}) {
  const obj = payload && typeof payload === 'object' ? payload : {}
  const out = normalizeChatPayload(obj)

  if (!out || typeof out !== 'object') {
    return {
      request_id: '',
      conv_id: '',
      rag_mode: '',
      mcp_overrides: {},
      mode_used: '',
      status: '',
      message: '',
      tool_calls: [],
      tool_results: [],
      citations: [],
      rss_evidence: [],
      market_evidence: [],
      evidence_query: '',
      evidence_tools: [],
      evidence_result: {},
      qa_id: '',
      group_id: '',
      response: ''
    }
  }

  if (eventName === 'delta') {
    out.response = String(obj.response || obj.text || obj.delta || obj.content || '')
  }

  if (eventName === 'error') {
    out.message = String(obj.message || obj.error || 'stream error')
  }

  if (eventName !== 'delta' && eventName !== 'final' && eventName !== 'done' && eventName !== 'meta') {
    delete out.citations
    delete out.rss_evidence
    delete out.market_evidence
    delete out.evidence_query
    delete out.evidence_tools
    delete out.evidence_result
    delete out.qa_id
    delete out.group_id
  }

  return out
}

async function callToolRaw(tool, args = {}, opts = {}) {
  const requestId = makeRequestId()
  const injected = mergeMcpToolArgs(tool, args, opts)
  injected.request_id = requestId

  const body = { tool, arguments: injected }
  const headers = buildHeaders({ 'X-Request-Id': requestId })

  const timeoutMs = Number.isFinite(opts.timeout_ms) ? Number(opts.timeout_ms) : 0
  const retry = Number.isFinite(opts.retry) ? Number(opts.retry) : 2
  const retryBaseMs = Number.isFinite(opts.retry_base_ms) ? Number(opts.retry_base_ms) : 500

  const externalSignal = opts.signal || null

  let mergedSignal = externalSignal
  let timeoutTimer = null
  let timeoutController = null

  if (timeoutMs > 0) {
    timeoutController = new AbortController()
    timeoutTimer = setTimeout(() => {
      try {
        timeoutController.abort('timeout')
      } catch {}
    }, Math.max(1000, timeoutMs))
    mergedSignal = mergeSignals(externalSignal, timeoutController.signal)
  }

  try {
    for (let attempt = 0; attempt <= retry; attempt++) {
      const res = await fetch(`${API_BASE}/mcp/call`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: mergedSignal
      })

      const json = await safeReadJson(res)

      if (res.ok) {
        const payload = unwrapGateway(json)
        const shouldNormalize = shouldNormalizeChatCall(tool, opts)
        const normalized = shouldNormalize ? normalizeChatPayload(payload) : payload

        if (hasChatPayload(normalized)) {
          dispatchChatEvidence(normalized)
        }

        return normalized
      }

      if (res.status === 401) handle401()

      const msg =
        json && (json.detail || json.message)
          ? (json.detail || json.message)
          : `HTTP ${res.status}`

      if (shouldRetryHttp(res.status) && attempt < retry) {
        const jitter = Math.floor(Math.random() * 200)
        const backoff = retryBaseMs * Math.pow(2, attempt) + jitter
        await sleep(backoff)
        continue
      }

      const err = new Error(msg)
      err.http_status = res.status
      err.request_id = requestId
      throw err
    }

    throw new Error('Unexpected retry loop exit')
  } catch (e) {
    if (String(e?.name || '') === 'AbortError') {
      const err = makeAbortError(`Request was canceled or timed out (${tool}).`)
      err.request_id = requestId
      throw err
    }
    throw e
  } finally {
    if (timeoutTimer) clearTimeout(timeoutTimer)
  }
}

async function callTool(tool, args = {}, opts = {}) {
  const bypassDedupe = shouldBypassDedupe(tool, opts)

  if (bypassDedupe) {
    return await callToolRaw(tool, args, { ...opts, dedupe: false })
  }

  const dedupeKey = String(opts.dedupe_key || defaultDedupeKey(tool, args))
  const existing = inflight.get(dedupeKey)
  if (existing?.promise) return await existing.promise

  const controller = new AbortController()
  const mergedSignal = mergeSignals(opts.signal || null, controller.signal)

  const p = (async () => {
    try {
      return await callToolRaw(tool, args, { ...opts, signal: mergedSignal })
    } finally {
      inflight.delete(dedupeKey)
    }
  })()

  inflight.set(dedupeKey, { promise: p, controller, startedAt: Date.now() })
  return await p
}

async function callToolStream(tool, args = {}, opts = {}) {
  const onEvent = typeof opts.onEvent === 'function' ? opts.onEvent : null
  const onMeta = typeof opts.onMeta === 'function' ? opts.onMeta : null
  const onDelta = typeof opts.onDelta === 'function' ? opts.onDelta : null
  const onFinal = typeof opts.onFinal === 'function' ? opts.onFinal : null
  const onDone = typeof opts.onDone === 'function' ? opts.onDone : null
  const onError = typeof opts.onError === 'function' ? opts.onError : null

  const requestId = makeRequestId()
  const injected = mergeMcpToolArgs(tool, args, opts)
  injected.request_id = requestId

  const body = { tool, arguments: injected }
  const headers = buildHeaders({ 'X-Request-Id': requestId })

  const bypassDedupe = shouldBypassDedupe(tool, opts)
  const dedupeKey = String(opts.dedupe_key || defaultDedupeKey(`stream:${tool}`, args))

  if (!bypassDedupe) {
    const existing = inflight.get(dedupeKey)
    if (existing?.promise) return await existing.promise
  }

  const controller = new AbortController()
  const mergedSignal = mergeSignals(opts.signal || null, controller.signal)

  const timeoutMs = Number.isFinite(opts.timeout_ms) ? Number(opts.timeout_ms) : 180000
  let timeoutTimer = null

  const p = (async () => {
    if (timeoutMs > 0) {
      timeoutTimer = setTimeout(() => {
        try {
          controller.abort('stream_timeout')
        } catch {}
      }, Math.max(1000, timeoutMs))
    }

    const res = await fetch(`${API_BASE}/mcp/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: mergedSignal
    })

    if (!res.ok || !res.body) {
      if (res.status === 401) handle401()
      const text = await safeReadText(res)
      const err = new Error(`Stream HTTP ${res.status}: ${text}`)
      err.http_status = res.status
      err.request_id = requestId
      throw err
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let buf = ''
    let curEvent = 'message'
    let curDataLines = []

    let collectedText = ''
    let finalPayload = null
    let streamError = null
    let shouldStop = false

    let lastMeta = {
      request_id: requestId,
      conv_id: '',
      rag_mode: '',
      mcp_overrides: {},
      mode_used: '',
      tool_calls: [],
      tool_results: [],
      citations: [],
      rss_evidence: [],
      market_evidence: [],
      evidence_query: '',
      evidence_tools: [],
      evidence_result: {},
      qa_id: '',
      group_id: ''
    }

    const pushEvent = (ev, normalized) => {
      if (normalized.request_id) lastMeta.request_id = normalized.request_id
      if (normalized.conv_id) lastMeta.conv_id = normalized.conv_id
      if (normalized.rag_mode) lastMeta.rag_mode = normalized.rag_mode
      if (normalized.mode_used) lastMeta.mode_used = normalized.mode_used
      if (normalized.mcp_overrides && typeof normalized.mcp_overrides === 'object') {
        lastMeta.mcp_overrides = normalized.mcp_overrides
      }

      if (Array.isArray(normalized.tool_calls)) lastMeta.tool_calls = normalized.tool_calls
      if (Array.isArray(normalized.tool_results)) lastMeta.tool_results = normalized.tool_results

      const extractedEvidence = normalizeEvidence(normalized)

      if (extractedEvidence.conv_id) lastMeta.conv_id = extractedEvidence.conv_id
      if (Array.isArray(extractedEvidence.citations) && extractedEvidence.citations.length > 0) {
        lastMeta.citations = extractedEvidence.citations
      }
      if (Array.isArray(extractedEvidence.rss_evidence) && extractedEvidence.rss_evidence.length > 0) {
        lastMeta.rss_evidence = extractedEvidence.rss_evidence
      }
      if (Array.isArray(extractedEvidence.market_evidence) && extractedEvidence.market_evidence.length > 0) {
        lastMeta.market_evidence = extractedEvidence.market_evidence
      }
      if (typeof extractedEvidence.evidence_query === 'string' && extractedEvidence.evidence_query) {
        lastMeta.evidence_query = extractedEvidence.evidence_query
      }
      if (Array.isArray(extractedEvidence.evidence_tools) && extractedEvidence.evidence_tools.length > 0) {
        lastMeta.evidence_tools = extractedEvidence.evidence_tools
      }
      if (
        extractedEvidence.evidence_result &&
        typeof extractedEvidence.evidence_result === 'object' &&
        Object.keys(extractedEvidence.evidence_result).length > 0
      ) {
        lastMeta.evidence_result = extractedEvidence.evidence_result
      }
      if (typeof extractedEvidence.qa_id === 'string' && extractedEvidence.qa_id) {
        lastMeta.qa_id = extractedEvidence.qa_id
      }
      if (typeof extractedEvidence.group_id === 'string' && extractedEvidence.group_id) {
        lastMeta.group_id = extractedEvidence.group_id
      }

      dispatchChatEvidence(normalized)

      if (onEvent) onEvent(ev, normalized)
      if (ev === 'meta' && onMeta) onMeta(normalized)
      if (ev === 'delta' && onDelta) onDelta(normalized)
      if (ev === 'final' && onFinal) onFinal(normalized)
      if (ev === 'done' && onDone) onDone(normalized)
      if (ev === 'error' && onError) onError(normalized)
    }

    const emit = () => {
      if (!curDataLines.length) return

      const raw = curDataLines.join('\n')
      curDataLines = []

      let dataObj = null
      try {
        dataObj = JSON.parse(raw)
      } catch {
        dataObj = { response: raw }
      }

      const rawEvent =
        curEvent !== 'message'
          ? curEvent
          : String(dataObj?.event || dataObj?.type || 'message')

      const ev = normalizeEventName(rawEvent, dataObj)
      const normalized = normalizeStreamPayload(ev, dataObj)

      if (ev === 'delta') {
        collectedText += String(normalized.response || '')
      } else if (ev === 'final') {
        finalPayload = normalized
        shouldStop = true
      } else if (ev === 'done') {
        shouldStop = true
      } else if (ev === 'error') {
        const err = new Error(normalized.message || 'stream error')
        err.request_id = normalized.request_id || requestId
        err.conv_id = normalized.conv_id || ''
        streamError = err
        shouldStop = true
      }

      pushEvent(ev, normalized)
    }

    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })

        while (true) {
          const idx = buf.indexOf('\n')
          if (idx === -1) break

          const line = buf.slice(0, idx)
          buf = buf.slice(idx + 1)

          const l = line.replace(/\r$/, '')
          if (l === '') {
            emit()
            curEvent = 'message'
            if (shouldStop) break
            continue
          }

          if (l.startsWith('event:')) {
            curEvent = l.slice(6).trim() || 'message'
            continue
          }

          if (l.startsWith('data:')) {
            curDataLines.push(l.slice(5).trimStart())
            continue
          }
        }

        if (shouldStop) {
          try {
            await reader.cancel()
          } catch {}
          break
        }
      }

      if (!shouldStop && buf.trim()) {
        const lines = buf.split('\n')
        for (const rawLine of lines) {
          const l = rawLine.replace(/\r$/, '')
          if (!l) {
            emit()
            curEvent = 'message'
            if (shouldStop) break
            continue
          }
          if (l.startsWith('event:')) {
            curEvent = l.slice(6).trim() || 'message'
            continue
          }
          if (l.startsWith('data:')) {
            curDataLines.push(l.slice(5).trimStart())
            continue
          }
        }
      }

      emit()
    } finally {
      if (timeoutTimer) clearTimeout(timeoutTimer)
    }

    if (streamError) {
      throw streamError
    }

    if (finalPayload && typeof finalPayload === 'object') {
      if (!String(finalPayload.response || '').trim() && collectedText) {
        finalPayload.response = collectedText
      }
      if (!String(finalPayload.request_id || '').trim()) {
        finalPayload.request_id = lastMeta.request_id || requestId
      }
      if (!String(finalPayload.conv_id || '').trim()) {
        finalPayload.conv_id = lastMeta.conv_id || ''
      }
      if (!String(finalPayload.rag_mode || '').trim()) {
        finalPayload.rag_mode = lastMeta.rag_mode || ''
      }
      if (!String(finalPayload.mode_used || '').trim()) {
        finalPayload.mode_used = lastMeta.mode_used || ''
      }
      if (!finalPayload.mcp_overrides || typeof finalPayload.mcp_overrides !== 'object') {
        finalPayload.mcp_overrides = lastMeta.mcp_overrides || {}
      }
      if (!Array.isArray(finalPayload.tool_calls)) {
        finalPayload.tool_calls = lastMeta.tool_calls || []
      }
      if (!Array.isArray(finalPayload.tool_results)) {
        finalPayload.tool_results = lastMeta.tool_results || []
      }

      const extractedFinalEvidence = normalizeEvidence(finalPayload)

      if (!Array.isArray(finalPayload.citations) || finalPayload.citations.length === 0) {
        finalPayload.citations = extractedFinalEvidence.citations?.length
          ? extractedFinalEvidence.citations
          : (lastMeta.citations || [])
      }
      if (!Array.isArray(finalPayload.rss_evidence) || finalPayload.rss_evidence.length === 0) {
        finalPayload.rss_evidence = extractedFinalEvidence.rss_evidence?.length
          ? extractedFinalEvidence.rss_evidence
          : (lastMeta.rss_evidence || [])
      }
      if (!Array.isArray(finalPayload.market_evidence) || finalPayload.market_evidence.length === 0) {
        finalPayload.market_evidence = extractedFinalEvidence.market_evidence?.length
          ? extractedFinalEvidence.market_evidence
          : (lastMeta.market_evidence || [])
      }
      if (!String(finalPayload.evidence_query || '').trim()) {
        finalPayload.evidence_query = extractedFinalEvidence.evidence_query || lastMeta.evidence_query || ''
      }
      if (!Array.isArray(finalPayload.evidence_tools) || finalPayload.evidence_tools.length === 0) {
        finalPayload.evidence_tools = extractedFinalEvidence.evidence_tools?.length
          ? extractedFinalEvidence.evidence_tools
          : (lastMeta.evidence_tools || [])
      }
      if (
        !finalPayload.evidence_result ||
        typeof finalPayload.evidence_result !== 'object' ||
        Object.keys(finalPayload.evidence_result).length === 0
      ) {
        finalPayload.evidence_result =
          (
            extractedFinalEvidence.evidence_result &&
            typeof extractedFinalEvidence.evidence_result === 'object' &&
            Object.keys(extractedFinalEvidence.evidence_result).length > 0
          )
            ? extractedFinalEvidence.evidence_result
            : (lastMeta.evidence_result || {})
      }
      if (!String(finalPayload.qa_id || '').trim()) {
        finalPayload.qa_id = extractedFinalEvidence.qa_id || lastMeta.qa_id || ''
      }
      if (!String(finalPayload.group_id || '').trim()) {
        finalPayload.group_id = extractedFinalEvidence.group_id || lastMeta.group_id || ''
      }

      return finalPayload
    }

    return {
      status: 'success',
      request_id: lastMeta.request_id || requestId,
      conv_id: lastMeta.conv_id || '',
      rag_mode: lastMeta.rag_mode || '',
      mcp_overrides: lastMeta.mcp_overrides || {},
      response: collectedText,
      message: '',
      mode_used: lastMeta.mode_used || '',
      tool_calls: lastMeta.tool_calls || [],
      tool_results: lastMeta.tool_results || [],
      citations: lastMeta.citations || [],
      rss_evidence: lastMeta.rss_evidence || [],
      market_evidence: lastMeta.market_evidence || [],
      evidence_query: lastMeta.evidence_query || '',
      evidence_tools: lastMeta.evidence_tools || [],
      evidence_result: lastMeta.evidence_result || {},
      qa_id: lastMeta.qa_id || '',
      group_id: lastMeta.group_id || ''
    }
  })()

  if (!bypassDedupe) {
    inflight.set(dedupeKey, { promise: p, controller, startedAt: Date.now() })
  }

  try {
    return await p
  } catch (e) {
    if (String(e?.name || '') === 'AbortError') {
      const err = makeAbortError(`Stream request was canceled or timed out (${tool}).`)
      err.request_id = requestId
      throw err
    }
    throw e
  } finally {
    if (timeoutTimer) clearTimeout(timeoutTimer)
    if (!bypassDedupe) inflight.delete(dedupeKey)
  }
}

export function useMCP() {
  const isStreaming = ref(false)

  ensureFsCapabilityGateDefaults()

  const wrappedCallTool = async (tool, args = {}, opts = {}) => {
    isStreaming.value = false
    return await callTool(tool, args, opts)
  }

  const wrappedCallToolStream = async (tool, args = {}, opts = {}) => {
    isStreaming.value = true
    try {
      return await callToolStream(tool, args, opts)
    } finally {
      isStreaming.value = false
    }
  }

  const cancelByDedupeKey = (dedupe_key) => cancelInflight(String(dedupe_key || ''))

  return {
    callTool: wrappedCallTool,
    callToolStream: wrappedCallToolStream,
    isStreaming,
    cancelByDedupeKey
  }
}

export default useMCP
