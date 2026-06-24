import {
  safe_array,
  safe_object,
  safe_string,
  normalize_bool,
  normalize_int,
} from '../room_shared'
import {
  get_runtime_payload,
  normalize_status_token,
  normalize_tool_activity_name,
  normalize_tool_activity_status,
  get_supervisor_audit_sections,
  flatten_supervisor_tool_activity,
  has_supervisor_audit,
  get_section_primary_message,
  get_section_primary_path,
  extract_runtime_result_text,
  extract_runtime_result_citations,
  normalize_tool_results,
  normalize_runtime_path,
} from '../room_protocol'
import {
  format_runtime_time,
  is_active_runtime_status_text,
  is_terminal_runtime_status_text,
  build_legal_runtime_status_label,
  build_legal_runtime_result_text,
  extract_legal_runtime_fact,
  resolve_effective_legal_runtime_fact,
  build_legal_runtime_result_entry,
  filter_runtime_process_items_for_run,
  has_terminal_runtime_evidence,
  get_terminal_runtime_status_label,
  pick_effective_runtime_result_event,
  pick_effective_runtime_result_payload,
  normalize_runtime_view_mode,
} from './room_runtime_formal'
import {
  compact_text,
  pretty_json,
  dedupe_tool_activity_rows,
} from './room_runtime_presenter_utils'
import {
  normalize_runtime_skill_summary,
  normalize_runtime_skill_cards,
  normalize_runtime_skill_activity_rows,
} from './room_runtime_skills'

function normalize_structured_tool_result_type(value) {
  const type = safe_string(value).trim()
  if (type === 'room_delegate_summary') return type
  if (type === 'room_supervisor_novelty_guard') return type
  if (type === 'room_supervisor_attribution') return type
  if (type === 'room_mcp_provider_execution') return type
  if (type === 'room_mcp_provider_error') return type
  if (type === 'room_role_runtime_fact') return type
  return ''
}

function normalize_provider_fact_type(value) {
  const type = safe_string(value).trim()
  if (type === 'room_mcp_provider_execution') return type
  if (type === 'room_mcp_provider_error') return type
  if (type === 'room_role_runtime_fact') return type
  return ''
}

function get_provider_fact_label(row = {}) {
  const src = safe_object(row)
  return safe_string(
    src.provider_label ||
      src.provider_name ||
      src.provider_id
  ).trim()
}

function get_provider_fact_reason(row = {}) {
  const src = safe_object(row)
  return safe_string(
    src.availability_reason ||
      src.reason ||
      src.provider_error ||
      src.error
  ).trim()
}

function build_provider_structured_name(row = {}) {
  const src = safe_object(row)
  const type = normalize_provider_fact_type(src.type)
  const providerLabel = get_provider_fact_label(src)
  const roleLabel = safe_string(src.role_name || src.role_id).trim()

  if (type === 'room_mcp_provider_execution') {
    return `provider.execution/${providerLabel || 'unknown'}`
  }
  if (type === 'room_mcp_provider_error') {
    return `provider.error/${providerLabel || 'unknown'}`
  }
  if (type === 'room_role_runtime_fact') {
    return `role.runtime/${roleLabel || 'unknown'}`
  }
  return ''
}

function get_structured_tool_result_name(row = {}) {
  const src = safe_object(row)
  const type = normalize_structured_tool_result_type(src.type)
  if (!type) return ''

  if (type === 'room_delegate_summary') return 'room_delegate_summary'
  if (type === 'room_supervisor_novelty_guard') return 'room_supervisor_novelty_guard'
  if (type === 'room_supervisor_attribution') return 'room_supervisor_attribution'
  if (
    type === 'room_mcp_provider_execution' ||
    type === 'room_mcp_provider_error' ||
    type === 'room_role_runtime_fact'
  ) {
    return build_provider_structured_name(src)
  }

  return type
}

function build_provider_fact_preview(row = {}) {
  const src = safe_object(row)
  const type = normalize_provider_fact_type(src.type)

  if (type === 'room_role_runtime_fact') {
    return pretty_json(
      {
        type,
        role_id: safe_string(src.role_id).trim(),
        role_name: safe_string(src.role_name).trim(),
        role_slug: safe_string(src.role_slug).trim(),
        requested_mode: safe_string(src.requested_mode).trim(),
        mode_used: safe_string(src.mode_used).trim(),
        status: safe_string(src.status).trim(),
        provider_id: safe_string(src.provider_id).trim(),
        provider_label: safe_string(src.provider_label).trim(),
        provider_status: safe_string(src.provider_status).trim(),
        provider_error: safe_string(src.provider_error).trim(),
        auth_type: safe_string(src.auth_type).trim(),
        availability_reason: safe_string(src.availability_reason).trim(),
        binding_ready: normalize_bool(src.binding_ready, false),
        has_citations: normalize_bool(src.has_citations, false),
        citations_count: normalize_int(src.citations_count, 0),
        response_preview: compact_text(src.response_preview, 240),
        evidence_query: safe_string(src.evidence_query).trim(),
        knowledge_scope: safe_object(src.knowledge_scope),
        tool_policy: safe_object(src.tool_policy),
      },
      1200
    )
  }

  return pretty_json(
    {
      type,
      provider_id: safe_string(src.provider_id).trim(),
      provider_label: safe_string(src.provider_label).trim(),
      status: safe_string(src.status).trim(),
      auth_type: safe_string(src.auth_type).trim(),
      auth_required: normalize_bool(src.auth_required, false),
      auth_configured: normalize_bool(src.auth_configured, false),
      availability_reason: get_provider_fact_reason(src),
      error: safe_string(src.error).trim(),
      message: compact_text(src.message || src.response || src.content, 240),
      result: src.result || src.payload || src.data || src.value || {},
    },
    1200
  )
}

function build_structured_tool_result_preview(row = {}) {
  const src = safe_object(row)
  const type = normalize_structured_tool_result_type(src.type)

  if (type === 'room_delegate_summary') {
    const items = safe_array(src.items).slice(0, 4).map((item) => {
      const role = safe_object(item)
      return {
        role_name: safe_string(role.role_name).trim(),
        point_count: normalize_int(role.point_count, 0),
        primary_points: safe_array(role.primary_points).slice(0, 3),
        stance: safe_string(role.stance).trim(),
      }
    })

    return pretty_json(
      {
        type,
        question: safe_string(src.question).trim(),
        plan_summary: compact_text(src.plan_summary, 240),
        delegate_count: normalize_int(src.delegate_count, 0),
        items,
      },
      1200
    )
  }

  if (type === 'room_supervisor_novelty_guard') {
    const summary = safe_object(src.summary)
    const targetsByRole = safe_array(src.targets_by_role).slice(0, 4).map((item) => {
      const role = safe_object(item)
      return {
        role_name: safe_string(role.role_name).trim(),
        targets: safe_array(role.targets).slice(0, 2).map((target) => {
          const rowTarget = safe_object(target)
          return {
            source_kind: safe_string(rowTarget.source_kind).trim(),
            uniqueness_score: rowTarget.uniqueness_score,
            excerpt: compact_text(rowTarget.excerpt || rowTarget.text, 180),
          }
        }),
      }
    })

    return pretty_json(
      {
        type,
        question: safe_string(src.question).trim(),
        summary,
        targets_by_role: targetsByRole,
      },
      1200
    )
  }

  if (type === 'room_supervisor_attribution') {
    const summary = safe_object(src.summary)
    const roles = safe_array(src.roles).slice(0, 5).map((item) => {
      const role = safe_object(item)
      return {
        role_name: safe_string(role.role_name).trim(),
        matched_sentence_count: normalize_int(role.matched_sentence_count, 0),
        max_score: role.max_score,
        sample_supports: safe_array(role.sample_supports).slice(0, 2),
      }
    })

    return pretty_json(
      {
        type,
        question: safe_string(src.question).trim(),
        summary,
        roles,
      },
      1200
    )
  }

  if (
    type === 'room_mcp_provider_execution' ||
    type === 'room_mcp_provider_error' ||
    type === 'room_role_runtime_fact'
  ) {
    return build_provider_fact_preview(src)
  }

  return pretty_json(
    src.result ||
      src.payload ||
      src.data ||
      src.value ||
      src,
    1200
  )
}

export function get_runtime_event_badge(type) {
  const normalized = safe_string(type).trim()

  if (normalized === 'room.plan') return 'PLAN'
  if (normalized === 'room.delegate') return 'DELEGATE'
  if (normalized === 'room.supervisor') return 'SUPERVISOR'
  if (normalized === 'room.route') return 'ROUTE'
  if (normalized === 'room.message') return 'MESSAGE'
  if (normalized === 'room.final') return 'FINAL'
  if (normalized === 'room.abort') return 'ABORT'
  if (normalized === 'room.aborted') return 'ABORTED'
  if (normalized === 'room.error') return 'ERROR'
  if (normalized === 'room.runtime_manual') return 'MANUAL'
  if (normalized === 'room.runtime_skipped') return 'SKIPPED'
  if (normalized === 'room.runtime_denied') return 'DENIED'
  if (
    normalized === 'room.runtime_no_auto_reply' ||
    normalized === 'room.runtime_no-auto-reply'
  ) {
    return 'NO-AUTO-REPLY'
  }
  return normalized || 'EVENT'
}

export function get_runtime_event_kind_class(type) {
  const normalized = safe_string(type).trim()

  if (normalized === 'room.plan') return 'kind-plan'
  if (normalized === 'room.delegate') return 'kind-delegate'
  if (normalized === 'room.supervisor') return 'kind-supervisor'
  if (normalized === 'room.route') return 'kind-route'
  if (normalized === 'room.message') return 'kind-message'
  if (normalized === 'room.final') return 'kind-final'
  if (normalized === 'room.abort' || normalized === 'room.aborted') return 'kind-abort'
  if (normalized === 'room.error') return 'kind-error'
  if (
    normalized === 'room.runtime_manual' ||
    normalized === 'room.runtime_skipped' ||
    normalized === 'room.runtime_denied' ||
    normalized === 'room.runtime_no_auto_reply' ||
    normalized === 'room.runtime_no-auto-reply'
  ) {
    return 'kind-final'
  }
  return 'kind-generic'
}

export function build_runtime_actor(payload = {}, fallbackType = '') {
  const src = safe_object(payload)
  const senderType = safe_string(src.sender_type || fallbackType).trim()
  const sender = safe_string(src.sender).trim()
  const roleName = safe_string(src.role_name || src.target_role_name).trim()
  const roleId = safe_string(src.role_id || src.target_role_id).trim()

  if (senderType === 'role') return roleName || sender || roleId || 'Role'
  if (senderType === 'supervisor') return roleName || sender || 'Supervisor'
  if (senderType === 'user') return sender || 'User'
  if (sender) return sender
  if (roleName) return roleName
  if (roleId) return roleId
  return ''
}

function build_audit_meta_chips(section = {}, kind = '') {
  const src = safe_object(section)
  const chips = []

  const focusRoot = normalize_runtime_path(src.focus_root)
  const scope = safe_string(src.scope).trim()
  const toolCallsLen = safe_array(src.tool_calls).length
  const toolResultsLen = safe_array(src.tool_results).length
  const updatedAt = format_runtime_time(src.updated_at || src.recorded_at || src.at)

  if (focusRoot) chips.push(`focus_root: ${focusRoot}`)
  if (scope) chips.push(`scope: ${scope}`)
  if (toolCallsLen) chips.push(`tool_call: ${toolCallsLen}`)
  if (toolResultsLen) chips.push(`tool_result: ${toolResultsLen}`)
  if (updatedAt) chips.push(`at: ${updatedAt}`)
  if (kind === 'notebook_write' && get_section_primary_path(src)) chips.push('writeback')
  if (kind === 'fs_read' && focusRoot) chips.push('grounding')

  return chips
}

function collect_provider_fact_rows(payload = {}) {
  const rows = normalize_tool_results(payload)
  const providerRows = []
  const runtimeFacts = []

  for (const item of safe_array(rows)) {
    const row = safe_object(item)
    const type = normalize_provider_fact_type(row.type)
    if (!type) continue

    if (
      type === 'room_mcp_provider_execution' ||
      type === 'room_mcp_provider_error'
    ) {
      providerRows.push(row)
      continue
    }

    if (type === 'room_role_runtime_fact') {
      runtimeFacts.push(row)
    }
  }

  return {
    provider_rows: dedupe_tool_activity_rows(
      providerRows,
      'provider_fact',
      get_structured_tool_result_name
    ),
    runtime_facts: dedupe_tool_activity_rows(
      runtimeFacts,
      'role_runtime_fact',
      get_structured_tool_result_name
    ),
  }
}

function find_runtime_fact_for_provider(runtimeFacts = [], providerRow = {}) {
  const providerId = safe_string(providerRow.provider_id).trim()
  if (!providerId) return {}

  return (
    safe_array(runtimeFacts).find((item) => {
      const row = safe_object(item)
      return safe_string(row.provider_id).trim() === providerId
    }) ||
    {}
  )
}

function build_provider_audit_cards(payload = {}) {
  const facts = collect_provider_fact_rows(payload)
  const providerRows = safe_array(facts.provider_rows)
  const runtimeFacts = safe_array(facts.runtime_facts)
  const cards = []
  const seen = new Set()

  for (const item of providerRows) {
    const row = safe_object(item)
    const runtimeFact = safe_object(find_runtime_fact_for_provider(runtimeFacts, row))
    const status = normalize_tool_activity_status(row, true)

    const providerId = safe_string(row.provider_id || runtimeFact.provider_id).trim()
    const providerLabel =
      get_provider_fact_label(row) ||
      get_provider_fact_label(runtimeFact) ||
      providerId
    const availabilityReason =
      get_provider_fact_reason(row) ||
      safe_string(runtimeFact.availability_reason).trim()
    const roleLabel = safe_string(runtimeFact.role_name || runtimeFact.role_id).trim()
    const modeLabel = safe_string(runtimeFact.mode_used || runtimeFact.requested_mode).trim()
    const providerStatus = safe_string(row.status || runtimeFact.provider_status).trim()
    const authType = safe_string(row.auth_type || runtimeFact.auth_type).trim()
    const citationsCount = normalize_int(runtimeFact.citations_count, 0)

    const key = `provider_${providerId || providerLabel || cards.length}`
    if (seen.has(key)) continue
    seen.add(key)

    cards.push({
      key,
      title: `Provider 审计 · ${providerLabel || 'unknown'}`,
      statusText: status.statusText,
      statusClass: status.statusClass,
      message: compact_text(
        get_provider_fact_reason(row) ||
          safe_string(row.error || row.message || row.response || row.content).trim() ||
          safe_string(
            runtimeFact.provider_error ||
            runtimeFact.response_preview ||
            runtimeFact.evidence_query
          ).trim(),
        220
      ),
      path: '',
      metaChips: [
        providerId ? `provider: ${providerId}` : '',
        providerStatus ? `provider_status: ${providerStatus}` : '',
        authType ? `auth: ${authType}` : '',
        availabilityReason ? `availability: ${availabilityReason}` : '',
        roleLabel ? `role: ${roleLabel}` : '',
        modeLabel ? `mode: ${modeLabel}` : '',
        citationsCount ? `citations: ${citationsCount}` : '',
      ].filter(Boolean),
    })
  }

  for (const item of runtimeFacts) {
    const row = safe_object(item)
    const providerId = safe_string(row.provider_id).trim()
    const providerLabel = get_provider_fact_label(row) || providerId
    const key = `provider_${providerId || providerLabel || cards.length}`
    if (!providerId || seen.has(key)) continue
    seen.add(key)

    const status = normalize_tool_activity_status(
      {
        status: row.provider_status || row.status,
        availability_reason: row.availability_reason,
        error: row.provider_error,
      },
      true
    )

    cards.push({
      key,
      title: `Provider 审计 · ${providerLabel || 'unknown'}`,
      statusText: status.statusText,
      statusClass: status.statusClass,
      message: compact_text(
        safe_string(row.provider_error || row.response_preview || row.evidence_query).trim(),
        220
      ),
      path: '',
      metaChips: [
        providerId ? `provider: ${providerId}` : '',
        safe_string(row.provider_status).trim()
          ? `provider_status: ${safe_string(row.provider_status).trim()}`
          : '',
        safe_string(row.auth_type).trim()
          ? `auth: ${safe_string(row.auth_type).trim()}`
          : '',
        safe_string(row.availability_reason).trim()
          ? `availability: ${safe_string(row.availability_reason).trim()}`
          : '',
        safe_string(row.role_name || row.role_id).trim()
          ? `role: ${safe_string(row.role_name || row.role_id).trim()}`
          : '',
        safe_string(row.mode_used || row.requested_mode).trim()
          ? `mode: ${safe_string(row.mode_used || row.requested_mode).trim()}`
          : '',
        normalize_int(row.citations_count, 0)
          ? `citations: ${normalize_int(row.citations_count, 0)}`
          : '',
      ].filter(Boolean),
    })
  }

  return cards
}

function build_provider_timeline_preview(payload = {}) {
  const facts = collect_provider_fact_rows(payload)
  const providerRows = safe_array(facts.provider_rows).map((item) => {
    const row = safe_object(item)
    return {
      type: safe_string(row.type).trim(),
      provider_id: safe_string(row.provider_id).trim(),
      provider_label: safe_string(row.provider_label).trim(),
      status: safe_string(row.status).trim(),
      auth_type: safe_string(row.auth_type).trim(),
      availability_reason: get_provider_fact_reason(row),
      error: safe_string(row.error).trim(),
      message: compact_text(row.message || row.response || row.content, 180),
    }
  })

  const runtimeFacts = safe_array(facts.runtime_facts).map((item) => {
    const row = safe_object(item)
    return {
      type: safe_string(row.type).trim(),
      role_name: safe_string(row.role_name || row.role_id).trim(),
      requested_mode: safe_string(row.requested_mode).trim(),
      mode_used: safe_string(row.mode_used).trim(),
      status: safe_string(row.status).trim(),
      provider_id: safe_string(row.provider_id).trim(),
      provider_status: safe_string(row.provider_status).trim(),
      auth_type: safe_string(row.auth_type).trim(),
      availability_reason: safe_string(row.availability_reason).trim(),
      citations_count: normalize_int(row.citations_count, 0),
      response_preview: compact_text(row.response_preview, 180),
    }
  })

  if (!providerRows.length && !runtimeFacts.length) return ''
  return pretty_json(
    {
      provider_tool_results: providerRows,
      role_runtime_facts: runtimeFacts,
    },
    900
  )
}

export function normalize_room_runtime_audit_cards(payload = {}) {
  const sections = get_supervisor_audit_sections(payload)
  const cards = []

  if (Object.keys(sections.supervisor_fs_read).length > 0) {
    const row = safe_object(sections.supervisor_fs_read)
    const status = normalize_tool_activity_status({ status: row.status }, true)

    cards.push({
      key: 'supervisor_fs_read',
      title: 'Supervisor FS 审计',
      statusText: status.statusText,
      statusClass: status.statusClass,
      message: get_section_primary_message(row),
      path: normalize_runtime_path(row.focus_root),
      metaChips: build_audit_meta_chips(row, 'fs_read'),
    })
  }

  if (Object.keys(sections.supervisor_notebook_read).length > 0) {
    const row = safe_object(sections.supervisor_notebook_read)
    const status = normalize_tool_activity_status({ status: row.status }, true)

    cards.push({
      key: 'supervisor_notebook_read',
      title: 'Supervisor Notebook Read 审计',
      statusText: status.statusText,
      statusClass: status.statusClass,
      message: get_section_primary_message(row),
      path: get_section_primary_path(row),
      metaChips: build_audit_meta_chips(row, 'notebook_read'),
    })
  }

  if (Object.keys(sections.supervisor_notebook_write).length > 0) {
    const row = safe_object(sections.supervisor_notebook_write)
    const status = normalize_tool_activity_status({ status: row.status }, true)

    cards.push({
      key: 'supervisor_notebook_write',
      title: 'Supervisor Notebook Write 审计',
      statusText: status.statusText,
      statusClass: status.statusClass,
      message: get_section_primary_message(row),
      path: get_section_primary_path(row),
      metaChips: build_audit_meta_chips(row, 'notebook_write'),
    })
  }

  cards.push(...build_provider_audit_cards(payload))
  return cards
}

function build_runtime_meta_chips(item, payload = {}) {
  const src = safe_object(item)
  const data = safe_object(payload)
  const chips = []

  const runId = safe_string(src.run_id || data.run_id).trim()
  const delegateIndex = safe_string(data.delegate_index).trim()
  const delegateTotal = safe_string(data.delegate_total).trim()
  const roleName = safe_string(data.role_name || data.target_role_name).trim()
  const phase = safe_string(data.phase).trim()
  const status = safe_string(data.status).trim()
  const citationsLen = extract_runtime_result_citations(data).length

  const nestedActivity = flatten_supervisor_tool_activity(data)
  const mergedToolCalls = dedupe_tool_activity_rows(
    [
      ...safe_array(data.tool_calls),
      ...safe_array(nestedActivity.tool_calls),
    ],
    'tool_call',
    get_structured_tool_result_name
  )
  const mergedToolResults = dedupe_tool_activity_rows(
    [
      ...safe_array(data.tool_results),
      ...safe_array(nestedActivity.tool_results),
    ],
    'tool_result',
    get_structured_tool_result_name
  )

  const fsReadStatus = safe_string(data.supervisor_fs_read?.status).trim()
  const notebookReadStatus = safe_string(data.supervisor_notebook_read?.status).trim()
  const notebookWriteStatus = safe_string(data.supervisor_notebook_write?.status).trim()

  const providerFacts = collect_provider_fact_rows(data)
  const providerRow = safe_object(providerFacts.provider_rows[0])
  const runtimeFact = safe_object(providerFacts.runtime_facts[0])

  const providerLabel =
    get_provider_fact_label(providerRow) ||
    get_provider_fact_label(runtimeFact)

  const providerStatus = safe_string(
    providerRow.status ||
      runtimeFact.provider_status
  ).trim()

  const authType = safe_string(
    providerRow.auth_type ||
      runtimeFact.auth_type
  ).trim()

  const availabilityReason =
    get_provider_fact_reason(providerRow) ||
    safe_string(runtimeFact.availability_reason).trim()

  if (runId) chips.push(`run: ${runId}`)
  if (roleName && safe_string(src.type).trim() !== 'room.message') chips.push(`role: ${roleName}`)
  if (delegateIndex || delegateTotal) chips.push(`delegate: ${delegateIndex || '0'}/${delegateTotal || '0'}`)
  if (phase) chips.push(`phase: ${phase}`)
  if (status) chips.push(`status: ${status}`)
  if (providerLabel) chips.push(`provider: ${providerLabel}`)
  if (providerStatus) chips.push(`provider_status: ${providerStatus}`)
  if (authType) chips.push(`auth: ${authType}`)
  if (availabilityReason) chips.push(`availability: ${availabilityReason}`)
  if (fsReadStatus) chips.push(`fs_read: ${fsReadStatus}`)
  if (notebookReadStatus) chips.push(`notebook_read: ${notebookReadStatus}`)
  if (notebookWriteStatus) chips.push(`notebook_write: ${notebookWriteStatus}`)
  if (mergedToolCalls.length) chips.push(`tool_call: ${mergedToolCalls.length}`)
  if (mergedToolResults.length) chips.push(`tool_result: ${mergedToolResults.length}`)
  if (citationsLen) chips.push(`citations: ${citationsLen}`)

  return chips
}

function build_runtime_summary(item, payload = {}) {
  const type = safe_string(item?.type).trim()
  const data = safe_object(payload)

  if (type === 'room.plan') {
    return compact_text(
      data.plan_summary ||
        data.summary ||
        data.message ||
        data.response
    )
  }

  if (type === 'room.delegate') {
    const roleName = safe_string(data.role_name || data.target_role_name).trim()
    const roleId = safe_string(data.role_id || data.target_role_id).trim()
    const index = safe_string(data.delegate_index).trim()
    const total = safe_string(data.delegate_total).trim()
    const summary = compact_text(data.message || data.summary || data.response)

    const prefix = [
      roleName || roleId ? `委派给 ${roleName || roleId}` : '',
      index || total ? `(${index || '0'}/${total || '0'})` : '',
    ].filter(Boolean).join(' ')

    return [prefix, summary].filter(Boolean).join(' · ')
  }

  if (type === 'room.supervisor') {
    const phase = safe_string(data.phase).trim()
    const notebookWriteMessage = get_section_primary_message(data.supervisor_notebook_write)
    const notebookReadMessage = get_section_primary_message(data.supervisor_notebook_read)
    const fsMessage = get_section_primary_message(data.supervisor_fs_read)

    return compact_text(
      data.message ||
        data.summary ||
        data.response ||
        notebookWriteMessage ||
        notebookReadMessage ||
        fsMessage ||
        (phase ? `Supervisor ${phase}` : '')
    )
  }

  if (type === 'room.route') {
    return compact_text(
      data.message ||
        data.summary
    )
  }

  if (type === 'room.message') {
    return compact_text(
      data.message ||
        data.response ||
        data.content
    )
  }

  if (type === 'room.final') {
    const notebookWriteMessage = get_section_primary_message(data.supervisor_notebook_write)
    const notebookReadMessage = get_section_primary_message(data.supervisor_notebook_read)
    const fsMessage = get_section_primary_message(data.supervisor_fs_read)

    return compact_text(
      data.message ||
        data.plan_summary ||
        data.response ||
        data.content ||
        notebookWriteMessage ||
        notebookReadMessage ||
        fsMessage
    )
  }

  if (
    type === 'room.runtime_manual' ||
    type === 'room.runtime_skipped' ||
    type === 'room.runtime_denied' ||
    type === 'room.runtime_no_auto_reply' ||
    type === 'room.runtime_no-auto-reply'
  ) {
    const legalFact = extract_legal_runtime_fact(data, safe_string(type).trim())
    return build_legal_runtime_result_text(legalFact)
  }

  if (type === 'room.abort' || type === 'room.aborted' || type === 'room.error') {
    return compact_text(
      data.message ||
        data.response ||
        data.content
    )
  }

  return compact_text(
    data.message ||
      data.summary ||
      data.response ||
      data.content
  )
}

function build_runtime_timeline_preview(item, payload = {}) {
  const type = safe_string(item?.type).trim()
  const data = safe_object(payload)

  if (type === 'room.plan') {
    return ''
  }

  if ((type === 'room.supervisor' || type === 'room.final') && has_supervisor_audit(data)) {
    const sections = get_supervisor_audit_sections(data)

    const previewSource = {
      phase: safe_string(data.phase).trim(),
      supervisor_fs_read: Object.keys(sections.supervisor_fs_read).length
        ? {
            status: safe_string(sections.supervisor_fs_read.status).trim(),
            message: get_section_primary_message(sections.supervisor_fs_read),
            focus_root: normalize_runtime_path(sections.supervisor_fs_read.focus_root),
            scope: safe_string(sections.supervisor_fs_read.scope).trim(),
          }
        : undefined,
      supervisor_notebook_read: Object.keys(sections.supervisor_notebook_read).length
        ? {
            status: safe_string(sections.supervisor_notebook_read.status).trim(),
            message: get_section_primary_message(sections.supervisor_notebook_read),
            relative_path: get_section_primary_path(sections.supervisor_notebook_read),
          }
        : undefined,
      supervisor_notebook_write: Object.keys(sections.supervisor_notebook_write).length
        ? {
            status: safe_string(sections.supervisor_notebook_write.status).trim(),
            message: get_section_primary_message(sections.supervisor_notebook_write),
            relative_path: get_section_primary_path(sections.supervisor_notebook_write),
          }
        : undefined,
    }

    return pretty_json(previewSource, 900)
  }

  const providerPreview = build_provider_timeline_preview(data)
  if (providerPreview) return providerPreview

  const previewSource =
    data.tool_calls?.length || data.tool_results?.length
      ? {
          tool_calls: data.tool_calls,
          tool_results: data.tool_results,
        }
      : (
          data.args ||
          data.input ||
          data.data ||
          data.result ||
          data.value ||
          data.extra ||
          null
        )

  if (!previewSource) return ''
  return pretty_json(previewSource, 900)
}

export function normalize_room_runtime_tool_activity(payload = {}) {
  const data = safe_object(payload)
  const nested = flatten_supervisor_tool_activity(data)

  const toolCalls = dedupe_tool_activity_rows(
    [
      ...safe_array(data.tool_calls),
      ...safe_array(nested.tool_calls),
    ],
    'tool_call',
    get_structured_tool_result_name
  )

  const toolResults = dedupe_tool_activity_rows(
    [
      ...safe_array(data.tool_results),
      ...safe_array(nested.tool_results),
    ],
    'tool_result',
    get_structured_tool_result_name
  )

  return {
    tool_calls: toolCalls.map((item, idx) => {
      const row = safe_object(item)
      const status = normalize_tool_activity_status(row, false)

      return {
        key: `tool_call_${idx}_${normalize_tool_activity_name(row)}_${safe_string(
          row.tool_call_id || row.call_id || row.id
        ).trim()}`,
        name: normalize_tool_activity_name(row),
        statusText: status.statusText,
        statusClass: status.statusClass,
        preview: pretty_json(
          row.args ||
            row.arguments ||
            row.input ||
            row.payload ||
            row.data ||
            row,
          1200
        ),
      }
    }),

    tool_results: toolResults.map((item, idx) => {
      const row = safe_object(item)
      const status = normalize_tool_activity_status(row, true)
      const structuredName = get_structured_tool_result_name(row)

      return {
        key: `tool_result_${idx}_${structuredName || normalize_tool_activity_name(row)}_${safe_string(
          row.tool_call_id || row.call_id || row.id || row.type
        ).trim()}`,
        name: structuredName || normalize_tool_activity_name(row),
        statusText: status.statusText,
        statusClass: status.statusClass,
        preview: structuredName
          ? build_structured_tool_result_preview(row)
          : pretty_json(
              row.result ||
                row.payload ||
                row.data ||
                row.value ||
                row,
              1200
            ),
      }
    }),
  }
}

export function normalize_room_runtime_result_entry(
  result_event,
  result_payload = {},
  fallback_run_id = ''
) {
  const item = safe_object(result_event)
  const payload = safe_object(result_payload)

  const legalFact = resolve_effective_legal_runtime_fact({
    result_event: item,
    result_payload: payload,
    status_text: safe_string(item.type).trim(),
  })

  if (!Object.keys(item).length && !Object.keys(payload).length && !legalFact) {
    return null
  }

  if (legalFact) {
    return build_legal_runtime_result_entry(legalFact, fallback_run_id, payload)
  }

  const type = safe_string(item.type).trim() || 'room.final'
  return {
    key: safe_string(item.id || item.ts || fallback_run_id || 'result'),
    badge: get_runtime_event_badge(type),
    actor: build_runtime_actor(payload, safe_string(payload.sender_type || 'supervisor')),
    timeText: format_runtime_time(item.ts || payload.ts || ''),
    metaChips: build_runtime_meta_chips(item, payload),
  }
}

export function normalize_room_runtime_timeline_entries(items = []) {
  return safe_array(items)
    .map((item, idx) => {
      const src = safe_object(item)
      const payload = get_runtime_payload(src)
      const type = safe_string(src.type).trim()

      if (!type) return null

      return {
        key: safe_string(src.id || `${type}_${src.ts || idx}`),
        badge: get_runtime_event_badge(type),
        kindClass: get_runtime_event_kind_class(type),
        actor: build_runtime_actor(payload, safe_string(payload.sender_type).trim()),
        timeText: format_runtime_time(src.ts),
        summary: build_runtime_summary(src, payload),
        metaChips: build_runtime_meta_chips(src, payload),
        preview: build_runtime_timeline_preview(src, payload),
      }
    })
    .filter(Boolean)
}

export function normalize_room_runtime_run_options(run_options = []) {
  return safe_array(run_options)
    .map((item) => {
      const row = safe_object(item)
      const runId = safe_string(row.run_id || row.value).trim()
      if (!runId) return null

      const lastTs = safe_string(row.last_ts).trim()
      const completed = !!row.completed
      const current = !!row.is_current

      const suffix = [
        current ? '当前' : '',
        completed ? '已完成' : '',
        lastTs ? format_runtime_time(lastTs) : '',
      ].filter(Boolean).join(' · ')

      return {
        value: runId,
        label: suffix ? `${runId} · ${suffix}` : runId,
      }
    })
    .filter(Boolean)
}

export function normalize_room_runtime_status_text({
  view_mode = 'current',
  status_text = '',
  error = '',
  loading = false,
  live = false,
  run_id = '',
  process_items = [],
  result_event = null,
  result_payload = {},
  selected_run_id = '',
  replay_items = [],
  replay_result_text = '',
} = {}) {
  const mode = normalize_runtime_view_mode(view_mode, 'current')
  const explicitStatus = safe_string(status_text).trim()
  const normalizedError = safe_string(error).trim()

  const effectiveLegalFact = resolve_effective_legal_runtime_fact({
    result_event,
    result_payload,
    status_text: explicitStatus,
  })

  const legalLabel = build_legal_runtime_status_label(
    safe_string(effectiveLegalFact?.kind).trim()
  )

  const terminalLabel = get_terminal_runtime_status_label(
    result_event,
    process_items,
    explicitStatus
  )

  if (mode === 'replay') {
    if (normalizedError) return normalizedError
    if (loading) return '加载运行回放...'
    if (terminalLabel) return terminalLabel
    if (legalLabel) return legalLabel
    if (safe_array(replay_items).length || result_event || safe_string(replay_result_text).trim()) {
      return '回放可查看'
    }
    if (safe_string(selected_run_id).trim()) return '回放待加载'
    return '暂无运行回放'
  }

  if (normalizedError) return normalizedError
  if (loading) return '加载运行过程...'
  if (terminalLabel) return terminalLabel
  if (legalLabel) return legalLabel

  if (live || is_active_runtime_status_text(explicitStatus)) {
    return explicitStatus || '运行中'
  }
  if (explicitStatus && !is_terminal_runtime_status_text(explicitStatus)) {
    return explicitStatus
  }
  if (safe_array(process_items).length > 0 || result_event) return '已完成'
  if (safe_string(run_id).trim()) return '已加载'
  return '暂无运行过程'
}

export function normalize_room_runtime_display_bundle({
  view_mode = 'current',
  run_id = '',
  status_text = '',
  process_items = [],
  result_event = null,
  result_payload = {},
  result_text = '',
  formal_runtime_packet = {},
  runtime_control_snapshot = {},
  formal_runtime_status = '',
  latest_formal_runtime_packet_at = '',
  run_options = [],
  selected_run_id = '',
  error = '',
  loading = false,
  live = false,
  replay_items = [],
  replay_result_text = '',
} = {}) {
  const normalizedViewMode = normalize_runtime_view_mode(view_mode, 'current')
  const normalizedRunId = safe_string(run_id).trim()
  const explicitStatus = safe_string(status_text).trim()

  const scopedProcessItems = filter_runtime_process_items_for_run(
    process_items,
    normalizedRunId,
    normalizedViewMode
  )

  const effectiveResultEvent = pick_effective_runtime_result_event({
    view_mode: normalizedViewMode,
    run_id: normalizedRunId,
    process_items: scopedProcessItems,
    result_event,
  })

  const payload = {
    ...safe_object(runtime_control_snapshot),
    ...safe_object(formal_runtime_packet),
    ...safe_object(
      pick_effective_runtime_result_payload({
        view_mode: normalizedViewMode,
        run_id: normalizedRunId,
        result_event: effectiveResultEvent,
        result_payload,
      })
    ),
    formal_runtime_packet: safe_object(formal_runtime_packet),
    runtime_control_snapshot: safe_object(runtime_control_snapshot),
    formal_runtime_status: safe_string(formal_runtime_status).trim(),
    latest_formal_runtime_packet_at: safe_string(latest_formal_runtime_packet_at).trim(),
  }

  const legalFact = resolve_effective_legal_runtime_fact({
    result_event: effectiveResultEvent,
    result_payload: payload,
    status_text: explicitStatus,
  })

  const effectiveLive = normalizedViewMode === 'replay'
    ? false
    : !has_terminal_runtime_evidence(scopedProcessItems, effectiveResultEvent, explicitStatus) && !!live

  const normalizedResultText =
    safe_string(result_text).trim() ||
    extract_runtime_result_text(payload) ||
    build_legal_runtime_result_text(legalFact)

  const citations = extract_runtime_result_citations(payload)
  const toolActivity = normalize_room_runtime_tool_activity(payload)

  const skillSummary = normalize_runtime_skill_summary(payload)
  const skillCards = normalize_runtime_skill_cards(payload)
  const skillActivityRows = normalize_runtime_skill_activity_rows(payload)
  const showSkillPanel =
    !!skillSummary.has_skills ||
    safe_array(skillCards).length > 0 ||
    safe_array(skillActivityRows).length > 0

  const legalLabel = build_legal_runtime_status_label(safe_string(legalFact?.kind).trim())
  const legalBadgeSummary = [
    legalLabel,
    safe_string(legalFact?.reasonCode).trim() ? `reason: ${safe_string(legalFact?.reasonCode).trim()}` : '',
    safe_string(legalFact?.path).trim() ? `path: ${safe_string(legalFact?.path).trim()}` : '',
  ].filter(Boolean).join(' · ')

  const terminalLabel = get_terminal_runtime_status_label(
    effectiveResultEvent,
    scopedProcessItems,
    explicitStatus
  )

  return {
    view_mode: normalizedViewMode,
    run_id: normalizedRunId,
    status_text: normalize_room_runtime_status_text({
      view_mode: normalizedViewMode,
      status_text: explicitStatus,
      error,
      loading,
      live: effectiveLive,
      run_id: normalizedRunId,
      process_items: scopedProcessItems,
      result_event: effectiveResultEvent,
      result_payload: payload,
      selected_run_id,
      replay_items,
      replay_result_text,
    }),
    selected_run_id: safe_string(selected_run_id).trim(),
    run_options: normalize_room_runtime_run_options(run_options),
    result_event: safe_object(effectiveResultEvent),
    result_payload: payload,
    result_text: normalizedResultText,
    result_citations: citations,
    result_entry: normalize_room_runtime_result_entry(
      effectiveResultEvent,
      payload,
      normalizedRunId
    ),
    headline:
      safe_string(payload.headline || payload.title || payload.summary_title).trim() ||
      (terminalLabel === '已完成' ? '已完成' : legalLabel),
    badge_summary:
      safe_string(payload.badge_summary || payload.plan_summary || payload.summary).trim() ||
      (terminalLabel === '已完成' ? '运行已完成' : legalBadgeSummary),

    audit_cards: normalize_room_runtime_audit_cards(payload),

    skill_summary: skillSummary,
    skill_cards: safe_array(skillCards),
    skill_activity_rows: safe_array(skillActivityRows),
    show_skill_panel: showSkillPanel,

    tool_call_rows: safe_array(toolActivity.tool_calls),
    tool_result_rows: safe_array(toolActivity.tool_results),
    timeline_entries: normalize_room_runtime_timeline_entries(scopedProcessItems),
    show_tool_activity:
      safe_array(toolActivity.tool_calls).length > 0 ||
      safe_array(toolActivity.tool_results).length > 0,
  }
}

