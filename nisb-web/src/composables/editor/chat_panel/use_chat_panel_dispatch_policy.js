import {
  arrayify,
  compact_object,
  pick_first,
} from './use_chat_panel_message_writer'

function normalize_scope(v) {
  const s = String(v || 'global').trim().toLowerCase()
  return s === 'doc' || s === 'library' ? s : 'global'
}

function normalize_id(v) {
  const s = String(v || '').trim()
  return s || undefined
}

function normalize_bool(v, fallback = false) {
  if (typeof v === 'boolean') return v
  const s = String(v ?? '').trim().toLowerCase()
  if (!s) return !!fallback
  return s === 'true' || s === '1' || s === 'yes' || s === 'on'
}

function normalize_rag_mode(v) {
  const s = String(v || 'off').trim().toLowerCase()
  return ['off', 'cite', 'ground', 'web', 'auto'].includes(s) ? s : 'off'
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

function crop_context_by_scope({ store_scope, evidence_scope, library_id, doc_id, group_id }) {
  const filter_scope = max_scope(store_scope, evidence_scope)

  const lib = normalize_id(library_id)
  const doc = normalize_id(doc_id)
  const gid = normalize_id(group_id)

  if (filter_scope === 'doc') {
    return {
      library_id: lib,
      doc_id: doc,
      group_id: undefined,
    }
  }

  if (filter_scope === 'library') {
    return {
      library_id: lib,
      doc_id: undefined,
      group_id: gid,
    }
  }

  return {
    library_id: undefined,
    doc_id: undefined,
    group_id: gid,
  }
}

function build_mcp_overrides({ mcp = {}, chat = {} } = {}) {
  return compact_object({
    serper_enabled: normalize_bool(
      pick_first(
        mcp?.serper_enabled,
        mcp?.serperEnabled,
        chat?.serper_enabled,
        chat?.serperEnabled,
        false
      ),
      false
    ),
    code_network_enabled: normalize_bool(
      pick_first(
        mcp?.code_network_enabled,
        mcp?.codeNetworkEnabled,
        chat?.code_network_enabled,
        chat?.codeNetworkEnabled,
        false
      ),
      false
    ),
    fs_read_scope: pick_first(
      mcp?.fs_read_scope,
      mcp?.fsReadScope,
      chat?.fs_read_scope,
      chat?.fsReadScope,
      'user_ro'
    ),
    fs_write_scope: pick_first(
      mcp?.fs_write_scope,
      mcp?.fsWriteScope,
      chat?.fs_write_scope,
      chat?.fsWriteScope,
      'agent_files'
    ),
    fs_dangerous_enabled: normalize_bool(
      pick_first(
        mcp?.fs_dangerous_enabled,
        mcp?.fsDangerousEnabled,
        chat?.fs_dangerous_enabled,
        chat?.fsDangerousEnabled,
        false
      ),
      false
    ),
  })
}

function resolve_requested_mode({ rag_mode, mcp_overrides }) {
  const normalized_rag_mode = normalize_rag_mode(rag_mode)
  const serper_enabled = !!mcp_overrides?.serper_enabled

  if (normalized_rag_mode === 'web') return 'web'
  if (serper_enabled) return 'web'
  return ''
}

function has_doc_or_library_context(payload = {}) {
  return !!(
    String(payload?.library_id || '').trim() ||
    String(payload?.doc_id || '').trim()
  )
}

function has_explicit_web_need({ requested_mode, mcp_overrides }) {
  if (String(requested_mode || '').trim() === 'web') return true
  if (!!mcp_overrides?.serper_enabled) return true
  return false
}

// 关键修正：
// RSS / market 是补充侧链配置，不是 dispatch 主路由信号。
// auto 是否需要走 evidence/orchestrate，只由正式 RAG 语义决定：
// - doc/library 上下文
// - 显式 web 需求
function has_auto_evidence_need({
  payload,
  requested_mode,
  mcp_overrides,
}) {
  if (has_doc_or_library_context(payload)) return true
  if (has_explicit_web_need({ requested_mode, mcp_overrides })) return true
  return false
}

function has_evidence_orchestrate_need({
  payload,
  rag_mode,
  requested_mode,
  mcp_overrides,
}) {
  const normalized_rag_mode = normalize_rag_mode(rag_mode)

  if (normalized_rag_mode === 'cite') return true
  if (normalized_rag_mode === 'ground') return true
  if (normalized_rag_mode === 'web') return true

  if (normalized_rag_mode === 'auto') {
    return has_auto_evidence_need({
      payload,
      requested_mode,
      mcp_overrides,
    })
  }

  if (has_explicit_web_need({ requested_mode, mcp_overrides })) return true

  return false
}

function is_retrieval_dispatch_kind(kind) {
  const v = String(kind || '').trim()
  return v === 'rag_qa' || v === 'rag_web' || v === 'rag_auto' || v === 'mcp_web'
}

function resolve_dispatch_kind({
  payload,
  rag_mode,
  requested_mode,
  mcp_overrides,
  agent_enabled,
}) {
  const normalized_rag_mode = normalize_rag_mode(rag_mode)

  if (normalized_rag_mode === 'cite' || normalized_rag_mode === 'ground') return 'rag_qa'
  if (normalized_rag_mode === 'web') return 'rag_web'

  if (normalized_rag_mode === 'auto') {
    const auto_need = has_auto_evidence_need({
      payload,
      requested_mode,
      mcp_overrides,
    })
    if (auto_need) return 'rag_auto'
  }

  if (requested_mode === 'web' && !!mcp_overrides?.serper_enabled) return 'mcp_web'

  if (normalize_bool(agent_enabled, false)) return 'agent'

  return 'chat'
}

function resolve_dispatch_transport({
  payload,
  dispatch_kind,
  rag_mode,
  requested_mode,
  mcp_overrides,
}) {
  if (dispatch_kind === 'agent') {
    return {
      tool_name: 'nisb_chat_orchestrate',
      use_stream: true,
    }
  }

  if (dispatch_kind === 'chat') {
    return {
      tool_name: 'nisb_chat_send',
      use_stream: true,
    }
  }

  if (has_evidence_orchestrate_need({
    payload,
    rag_mode,
    requested_mode,
    mcp_overrides,
  })) {
    return {
      tool_name: 'nisb_chat_orchestrate',
      use_stream: false,
    }
  }

  return {
    tool_name: 'nisb_chat_send',
    use_stream: true,
  }
}

const ANSWER_LANG_SETTINGS_LS_KEY = 'nisb_settings_v2'

function normalize_answer_lang_locale(input) {
  const raw = String(input || '').trim().toLowerCase()
  if (!raw) return ''
  if (raw === 'zh' || raw === 'zh-cn' || raw === 'zh_hans') return 'zh'
  if (raw === 'en' || raw === 'en-us' || raw === 'en_us') return 'en'
  return ''
}

function detect_input_answer_lang(input) {
  const text = String(input || '').trim()
  if (!text) return ''

  const hasCJK = /[\u4e00-\u9fff]/.test(text)
  const hasKana = /[\u3040-\u30ff]/.test(text)
  const hasLatin = /[A-Za-z]/.test(text)

  if (hasLatin && !hasCJK && !hasKana) return 'en'
  if (hasCJK) return 'zh'

  return ''
}

function resolve_chat_answer_lang({ raw_input, settings = {} } = {}) {
  const fromInput = detect_input_answer_lang(raw_input)
  if (fromInput) return fromInput

  const fromSettings = normalize_answer_lang_locale(
    pick_first(settings?.locale, settings?.uiLocale, settings?.ui_locale)
  )
  if (fromSettings) return fromSettings

  try {
    const saved = JSON.parse(localStorage.getItem(ANSWER_LANG_SETTINGS_LS_KEY) || '{}')
    const fromStorage = normalize_answer_lang_locale(saved?.locale)
    if (fromStorage) return fromStorage
  } catch {}

  return 'zh'
}

export function build_chat_arguments({
  raw_input,
  request_id,
  model,
  conv_id,
  chat_cfg,
  selected_attachments = [],
  settings = {},
  agent_cfg = {},
}) {
  const chat = chat_cfg?.chat || {}
  const rag = chat_cfg?.rag || chat_cfg?.rag_config || {}
  const rag_context = rag?.context || {}
  const mcp = chat_cfg?.mcp || chat_cfg?.mcp_config || {}
  const fed = chat_cfg?.fed || chat_cfg?.fed_config || rag?.external || {}
  const rss = chat_cfg?.rss || rag?.rssReference || rag?.rss || {}
  const qa_answer_lang = resolve_chat_answer_lang({ raw_input, settings })

  const attachments = Array.isArray(selected_attachments)
    ? selected_attachments.map((att) => ({
        name: att?.name || '',
        path: att?.path || att?.relative_path || att?.relativePath || '',
        type: att?.type || '',
        size: att?.size || 0,
      }))
    : []

  const store_scope = normalize_scope(
    pick_first(
      rag?.store_scope,
      rag?.storeScope,
      chat?.qa_store_scope,
      chat?.qaStoreScope,
      'global'
    )
  )

  const evidence_scope = normalize_scope(
    pick_first(
      rag?.evidence_scope,
      rag?.evidenceScope,
      chat?.qa_evidence_scope,
      chat?.qaEvidenceScope,
      store_scope
    )
  )

  const raw_library_id = pick_first(
    rag_context?.library_id,
    rag_context?.libraryId,
    rag?.library_id,
    rag?.libraryId,
    chat?.library_id,
    chat?.libraryId
  )

  const raw_doc_id = pick_first(
    rag_context?.doc_id,
    rag_context?.docId,
    rag?.doc_id,
    rag?.docId,
    chat?.doc_id,
    chat?.docId
  )

  const raw_group_id = pick_first(
    rag_context?.group_id,
    rag_context?.groupId,
    rag?.group_id,
    rag?.groupId,
    chat?.group_id,
    chat?.groupId
  )

  const scoped_context = crop_context_by_scope({
    store_scope,
    evidence_scope,
    library_id: raw_library_id,
    doc_id: raw_doc_id,
    group_id: raw_group_id,
  })

  const rag_mode = normalize_rag_mode(
    pick_first(
      chat?.rag_mode,
      chat?.ragMode,
      rag?.mode,
      rag?.rag_mode,
      'off'
    )
  )

  const mcp_overrides = build_mcp_overrides({ mcp, chat })
  const requested_mode = resolve_requested_mode({ rag_mode, mcp_overrides })

  return compact_object({
    content: String(raw_input || '').trim(),
    model: String(model || '').trim(),
    conv_id: String(conv_id || '').trim(),
    request_id: String(request_id || '').trim(),

    rag_mode,

    store_scope,
    evidence_scope,

    qa_store_scope: store_scope,
    qa_evidence_scope: evidence_scope,
    qa_answer_lang,

    library_id: scoped_context.library_id,
    doc_id: scoped_context.doc_id,
    group_id: scoped_context.group_id,

    requested_mode: requested_mode || undefined,

    index_use_mini_forced: !!pick_first(settings?.indexUseMiniForced, false),

    agent_enabled: !!pick_first(
      mcp?.agent_enabled,
      mcp?.agentEnabled,
      chat?.agent_enabled,
      chat?.agentEnabled,
      agent_cfg?.enabled,
      false
    ),

    agent_answer_use_planner: !!pick_first(
      mcp?.agent_answer_use_planner,
      mcp?.agentAnswerUsePlanner,
      chat?.agent_answer_use_planner,
      chat?.agentAnswerUsePlanner,
      agent_cfg?.answerUsePlanner,
      false
    ),

    agent_debug: !!pick_first(
      mcp?.agent_debug,
      mcp?.agentDebug,
      chat?.agent_debug,
      chat?.agentDebug,
      agent_cfg?.debug,
      false
    ),

    agent_max_steps: pick_first(
      mcp?.agent_max_steps,
      mcp?.agentMaxSteps,
      chat?.agent_max_steps,
      chat?.agentMaxSteps,
      agent_cfg?.maxSteps
    ),

    agent_planner_model: pick_first(
      mcp?.agent_planner_model,
      mcp?.agentPlannerModel,
      chat?.agent_planner_model,
      chat?.agentPlannerModel,
      agent_cfg?.plannerModel
    ),

    agent_planner_provider: pick_first(
      mcp?.agent_planner_provider,
      mcp?.agentPlannerProvider,
      chat?.agent_planner_provider,
      chat?.agentPlannerProvider,
      agent_cfg?.plannerProvider
    ),

    market_enabled: !!pick_first(
      fed?.market_enabled,
      fed?.marketEnabled,
      chat?.market_enabled,
      chat?.marketEnabled,
      false
    ),

    market_max_evidence: pick_first(
      fed?.market_max_evidence,
      fed?.marketMaxEvidence,
      chat?.market_max_evidence,
      chat?.marketMaxEvidence
    ),

    peer_targets: arrayify(
      pick_first(
        fed?.peer_targets,
        fed?.peerTargets,
        chat?.peer_targets,
        chat?.peerTargets
      )
    ),

    rss_enabled: !!pick_first(
      rss?.enabled,
      chat?.rss_enabled,
      chat?.rssEnabled,
      rag?.rss_enabled,
      rag?.rssEnabled,
      false
    ),

    rss_feed_ids: arrayify(
      pick_first(
        rss?.feed_ids,
        rss?.feedIds,
        chat?.rss_feed_ids,
        chat?.rssFeedIds,
        rag?.rss_feed_ids,
        rag?.rssFeedIds
      )
    ),

    rss_max_citations: pick_first(
      rss?.limit,
      chat?.rss_max_citations,
      chat?.rssMaxCitations,
      rag?.rss_max_citations,
      rag?.rssMaxCitations,
      8
    ),

    rss: typeof rss === 'object' && rss ? rss : undefined,
    mcp_overrides,
    attachments,
  })
}

export function resolve_chat_dispatch_policy(args) {
  const payload = build_chat_arguments(args)
  const rag_mode = normalize_rag_mode(payload?.rag_mode)
  const requested_mode = String(payload?.requested_mode || '').trim()
  const mcp_overrides = payload?.mcp_overrides || {}
  const agent_enabled = !!payload?.agent_enabled

  const dispatch_kind = resolve_dispatch_kind({
    payload,
    rag_mode,
    requested_mode,
    mcp_overrides,
    agent_enabled,
  })

  if (is_retrieval_dispatch_kind(dispatch_kind)) {
    payload.agent_enabled = false
    payload.agent_answer_use_planner = false
  }

  const transport = resolve_dispatch_transport({
    payload,
    dispatch_kind,
    rag_mode,
    requested_mode,
    mcp_overrides,
  })

  return {
    payload,
    tool_name: transport.tool_name,
    use_stream: transport.use_stream,
    dispatch_kind,
    requested_mode,
  }
}

export default resolve_chat_dispatch_policy

