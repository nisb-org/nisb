import { computed, unref } from 'vue'

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

function safeNumber(value, fallback = 0) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function shortenText(value, max = 180) {
  const text = safeString(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}…`
}

function normalizeChipList(list) {
  return safeArray(list)
    .map((item) => safeString(item).trim())
    .filter(Boolean)
}

function normalizeStringList(list) {
  return Array.from(
    new Set(
      safeArray(list)
        .map((item) => safeString(item).trim())
        .filter(Boolean)
    )
  )
}

function firstNonEmptyArray(...candidates) {
  for (const candidate of candidates) {
    const list = normalizeStringList(candidate)
    if (list.length) return list
  }
  return []
}

function getRuntimePayload(item, fallback = null) {
  const candidates = [
    fallback,
    item?.payload,
    item?.data,
    item?.result,
    item?.value,
    item,
  ]

  for (const candidate of candidates) {
    const obj = safeObject(candidate)
    if (Object.keys(obj).length > 0) return obj
  }

  return {}
}

function getRuntimeEventType(item) {
  return safeString(item?.type).trim()
}

function getRuntimeTypeClass(type) {
  return safeString(type).replace(/^room\./, '').replace(/\./g, '-').trim() || 'event'
}

function getRuntimeBadge(type) {
  if (type === 'room.manual') return 'manual'
  if (type === 'room.skipped') return 'skipped'
  if (type === 'room.denied') return 'denied'
  if (type === 'room.no_auto_reply') return 'no-auto-reply'
  if (type === 'room.plan') return 'plan'
  if (type === 'room.delegate') return 'delegate'
  if (type === 'room.supervisor') return 'supervisor'
  if (type === 'room.route') return 'route'
  if (type === 'room.message') return 'worker'
  if (type === 'room.final') return 'final'
  if (type === 'room.abort' || type === 'room.aborted') return 'abort'
  if (type === 'room.error') return 'error'
  return type || 'event'
}

function getRuntimeTitle(type, payload) {
  if (type === 'room.manual') return '已转人工处理'
  if (type === 'room.skipped') return '自动回复已跳过'
  if (type === 'room.denied') return '自动回复已拒绝'
  if (type === 'room.no_auto_reply') return '未触发自动回复'
  if (type === 'room.plan') return 'Supervisor 规划'
  if (type === 'room.delegate') return '角色委派'
  if (type === 'room.supervisor') return 'Supervisor 运行'
  if (type === 'room.route') return '路由选择'
  if (type === 'room.final') return '最终结果'
  if (type === 'room.message') {
    return safeString(payload.role_name || payload.sender || '角色回复').trim() || '角色回复'
  }
  if (type === 'room.abort' || type === 'room.aborted') return '运行中断'
  if (type === 'room.error') return '运行错误'
  return type || '运行事件'
}

function getRuntimeActor(type, payload) {
  if (type === 'room.plan') {
    return safeString(payload.role_name || payload.sender || 'Supervisor').trim()
  }

  if (type === 'room.delegate') {
    return safeString(
      payload.target_role_name ||
      payload.role_name ||
      payload.target_role_id ||
      payload.role_id
    ).trim()
  }

  if (type === 'room.supervisor' || type === 'room.final') {
    return safeString(
      payload.role_name ||
      payload.sender ||
      'Supervisor'
    ).trim()
  }

  if (type === 'room.route') {
    return safeString(
      payload.target_role_name ||
      payload.target_role_id ||
      payload.route_target
    ).trim()
  }

  if (type === 'room.message') {
    return safeString(
      payload.role_name ||
      payload.sender ||
      payload.role_id
    ).trim()
  }

  return safeString(
    payload.sender ||
    payload.role_name ||
    payload.role_id
  ).trim()
}

function getRuntimeSummary(type, payload) {
  if (
    type === 'room.manual' ||
    type === 'room.skipped' ||
    type === 'room.denied' ||
    type === 'room.no_auto_reply'
  ) {
    return shortenText(
      payload.message ||
      payload.summary ||
      payload.reason ||
      payload.reason_code ||
      payload.content ||
      payload.response
    )
  }
  if (type === 'room.plan') {
    return shortenText(
      payload.plan_summary ||
      payload.summary ||
      payload.plan ||
      payload.response ||
      payload.content
    )
  }

  if (type === 'room.delegate') {
    const idx = payload.delegate_index ?? payload.current_delegate_index
    const total = payload.delegate_total ?? payload.current_delegate_total
    const roleName = safeString(
      payload.target_role_name ||
      payload.role_name ||
      payload.target_role_id ||
      payload.role_id
    ).trim()
    const summary = safeString(
      payload.summary ||
      payload.delegate_summary ||
      payload.reason
    ).trim()

    const prefix =
      idx !== undefined && total !== undefined
        ? `第 ${Number(idx) + 1} / ${Number(total)} 步`
        : roleName
          ? `委派给 ${roleName}`
          : '已委派角色'

    return shortenText(summary ? `${prefix} · ${summary}` : prefix)
  }

  if (type === 'room.supervisor') {
    return shortenText(
      payload.plan_summary ||
      payload.summary ||
      payload.response ||
      payload.content
    )
  }

  if (type === 'room.route') {
    const routeMode = safeString(payload.route_mode || payload.reply_mode).trim()
    const target = safeString(
      payload.target_role_name ||
      payload.target_role_id ||
      payload.route_target
    ).trim()
    return shortenText([routeMode, target].filter(Boolean).join(' · '))
  }

  if (type === 'room.message' || type === 'room.final') {
    return shortenText(
      payload.response ||
      payload.content
    )
  }

  if (type === 'room.abort' || type === 'room.aborted' || type === 'room.error') {
    return shortenText(
      payload.reason ||
      payload.error ||
      payload.message
    )
  }

  return shortenText(
    payload.summary ||
    payload.message ||
    payload.content ||
    payload.response
  )
}

function getRuntimeMetaChips(item, payload) {
  const chips = []

  const modeUsed = safeString(payload.mode_used).trim()
  const model = safeString(payload.model).trim()
  const roleId = safeString(payload.role_id || payload.target_role_id).trim()
  const runId = safeString(item?.run_id || payload.run_id).trim()
  const requestId = safeString(item?.request_id || payload.request_id).trim()
  const triggerEventId = safeString(item?.trigger_event_id || payload.trigger_event_id).trim()

  if (modeUsed) chips.push(modeUsed)
  if (model) chips.push(model)
  if (roleId) chips.push(roleId)
  if (runId) chips.push(runId)
  if (requestId) chips.push(requestId)
  if (triggerEventId) chips.push(`trigger:${triggerEventId.slice(0, 12)}`)

  return normalizeChipList(chips).slice(0, 6)
}

function formatRuntimeEventTime(item) {
  const raw = safeString(item?.ts).trim()
  if (!raw) return ''

  try {
    const date = new Date(raw)
    if (Number.isNaN(date.getTime())) return raw
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return raw
  }
}

function buildRuntimeEntry(item, payloadOverride = null) {
  const raw = safeObject(item)
  if (!Object.keys(raw).length) return null

  const type = getRuntimeEventType(raw)
  const payload = getRuntimePayload(raw, payloadOverride)

  return {
    id: safeString(raw.id || raw.event_id || raw.eventId).trim(),
    type,
    typeClass: getRuntimeTypeClass(type),
    badge: getRuntimeBadge(type),
    title: getRuntimeTitle(type, payload),
    actor: getRuntimeActor(type, payload),
    summary: getRuntimeSummary(type, payload),
    metaChips: getRuntimeMetaChips(raw, payload),
    timeText: formatRuntimeEventTime(raw),
    raw,
    payload,
  }
}

function normalizeLegalRuntimeKind(value) {
  const token = safeString(value).trim().toLowerCase()
  if (!token) return ''
  if (token.includes('manual')) return 'manual'
  if (token.includes('denied') || token.includes('deny')) return 'denied'
  if (token.includes('skipped') || token.includes('skip')) return 'skipped'
  if (
    token.includes('no-auto-reply') ||
    token.includes('no_auto_reply') ||
    token.includes('no auto reply')
  ) return 'no_auto_reply'
  return ''
}

function findLegalRuntimeStateFact(payload = {}) {
  const src = safeObject(payload)
  const containers = [
    src,
    safeObject(src.formal_runtime_packet),
    safeObject(src.runtime_control_snapshot),
  ]

  for (const row of containers) {
    const candidate = [
      row.type,
      row.status,
      row.status_text,
      row.runtime_status,
      row.formal_runtime_status,
      row.disposition,
      row.outcome,
    ]
      .map((item) => safeString(item).trim())
      .find(Boolean)

    const kind = normalizeLegalRuntimeKind(candidate)
    if (!kind) continue

    return {
      kind,
      reason_code: safeString(
        row.reason_code ||
        row.skip_reason_code ||
        row.deny_reason_code
      ).trim(),
      message: safeString(
        row.message ||
        row.summary ||
        row.response ||
        row.content
      ).trim(),
      ts: safeString(
        row.latest_formal_runtime_packet_at ||
        row.updated_at ||
        row.ts
      ).trim(),
    }
  }

  return null
}

function buildLegalRuntimeSyntheticEntry(payload = {}) {
  const fact = findLegalRuntimeStateFact(payload)
  if (!fact) return null

  const type =
    fact.kind === 'no_auto_reply'
      ? 'room.no_auto_reply'
      : `room.${fact.kind}`

  return buildRuntimeEntry(
    {
      id: `legal-${fact.kind}`,
      type,
      ts: fact.ts,
      payload: {
        ...safeObject(payload),
        reason_code: fact.reason_code,
        message: fact.message,
      },
    },
    {
      ...safeObject(payload),
      reason_code: fact.reason_code,
      message: fact.message,
    }
  )
}

function normalizeFormalSkillStrategy(value) {
  const token = safeString(value).trim().toLowerCase()
  if (!token) return ''

  if (token === 'builtin_plus_custom') return 'builtin_plus_custom'
  if (token === 'custom_only') return 'custom_only'
  if (token === 'builtin_only') return 'builtin_only'

  if (token === 'builtin + custom' || token === 'builtin+custom') return 'builtin_plus_custom'
  if (token === 'custom only' || token === 'custom-only') return 'custom_only'
  if (token === 'builtin only' || token === 'builtin-only') return 'builtin_only'

  return ''
}

function formatSkillStrategyLabel(value) {
  const token = normalizeFormalSkillStrategy(value)
  if (!token) return ''
  if (token === 'builtin_plus_custom') return 'builtin + custom'
  if (token === 'custom_only') return 'custom only'
  if (token === 'builtin_only') return 'builtin only'
  return safeString(value).trim()
}

function normalizeSkillSource(value, fallback = '') {
  const token = safeString(value || fallback).trim().toLowerCase()

  if (!token) return ''
  if (token.includes('builtin') || token.includes('system')) return 'builtin'
  if (token.includes('custom') || token.includes('workspace')) return 'custom'
  return safeString(value || fallback).trim()
}

function normalizeSkillItem(item, sourceHint = '') {
  if (typeof item === 'string') {
    const name = safeString(item).trim()
    if (!name) return null

    return {
      id: name,
      name,
      source: normalizeSkillSource(sourceHint),
      relativePath: '',
      title: '',
      summary: '',
      raw: item,
    }
  }

  const src = safeObject(item)
  if (!Object.keys(src).length) return null

  const name = safeString(
    src.name ||
    src.skill_name ||
    src.skillName ||
    src.title ||
    src.id ||
    src.slug ||
    src.relative_path ||
    src.relativePath
  ).trim()

  if (!name) return null

  return {
    id: safeString(src.id || name).trim(),
    name,
    source: normalizeSkillSource(
      src.source ||
      src.origin ||
      src.kind ||
      src.scope ||
      src.type,
      sourceHint
    ),
    relativePath: safeString(src.relative_path || src.relativePath || src.path).trim(),
    title: safeString(src.title).trim(),
    summary: safeString(src.summary || src.description || src.prompt_summary).trim(),
    raw: src,
  }
}

function appendNormalizedSkills(target, list, sourceHint = '') {
  safeArray(list).forEach((item) => {
    const normalized = normalizeSkillItem(item, sourceHint)
    if (normalized) target.push(normalized)
  })
}

function appendSkillNames(target, list, sourceHint = '') {
  normalizeStringList(list).forEach((name) => {
    const normalized = normalizeSkillItem(name, sourceHint)
    if (normalized) target.push(normalized)
  })
}

function dedupeSkills(list) {
  const seen = new Set()
  const output = []

  safeArray(list).forEach((item) => {
    const normalized = normalizeSkillItem(item, item?.source || '')
    if (!normalized) return

    const key = [
      safeString(normalized.name).trim().toLowerCase(),
      safeString(normalized.source).trim().toLowerCase(),
      safeString(normalized.relativePath).trim().toLowerCase(),
    ].join('::')

    if (seen.has(key)) return
    seen.add(key)
    output.push(normalized)
  })

  return output
}

function normalizeSupervisorSkillStepRow(row, index = 0) {
  const src = safeObject(row)

  return {
    index: safeNumber(src.index, index + 1),
    skill_id: safeString(
      src.skill_id ||
      src.skillId ||
      src.id ||
      src.slug ||
      src.key ||
      src.name
    ).trim(),
    label: safeString(
      src.label ||
      src.title ||
      src.name ||
      src.skill_name ||
      src.skillName
    ).trim(),
    kind: safeString(
      src.kind ||
      src.skill_kind ||
      src.skillKind
    ).trim(),
    status: safeString(
      src.status ||
      src.step_status ||
      src.stepStatus ||
      src.result ||
      src.state
    ).trim(),
    message: safeString(
      src.message ||
      src.reason ||
      src.note ||
      src.detail
    ).trim(),
    path: safeString(
      src.path ||
      src.relative_path ||
      src.relativePath
    ).trim(),
    raw: src,
  }
}

function normalizeRuntimeDisplaySupervisorSkills(bundle, summary = null) {
  const src = safeObject(bundle)
  const sum = safeObject(summary)

  const strategyValue = normalizeFormalSkillStrategy(
    src.strategy ||
    src.supervisor_skill_strategy ||
    sum.strategy
  )

  const strategy = formatSkillStrategyLabel(
    sum.strategy ||
    src.strategy ||
    strategyValue
  )

  const stepRows = safeArray(src.step_rows)
    .map((row, index) => normalizeSupervisorSkillStepRow(row, index))
    .filter((row) => {
      return !!(
        row.skill_id ||
        row.label ||
        row.kind ||
        row.status ||
        row.message ||
        row.path
      )
    })

  const enabledIds = firstNonEmptyArray(
    src.enabled_skill_ids,
    sum.enabled_skill_ids
  )

  const appliedIds = firstNonEmptyArray(
    src.applied_skill_ids,
    sum.applied_skill_ids
  )

  const enabledCount = safeNumber(
    sum.enabled_count ?? src.enabled_count,
    enabledIds.length
  )

  const appliedCount = safeNumber(
    sum.applied_count ?? src.applied_count,
    appliedIds.length
  )

  const resolvedItemsCount = safeNumber(
    sum.resolved_items_count ?? src.resolved_items_count,
    0
  )

  const stepCount = safeNumber(
    sum.step_count ?? src.step_count,
    stepRows.length
  )

  const status = safeString(sum.status || src.status).trim()
  const message = safeString(sum.message || src.message).trim()
  const sourceType = safeString(sum.source_type || src.source_type).trim()
  const sourceEventType = safeString(sum.source_event_type || src.source_event_type).trim()
  const sourceRunId = safeString(sum.source_run_id || src.source_run_id).trim()
  const promptLen = safeNumber(sum.prompt_block_chars ?? src.prompt_block_chars, 0)
  const summaryText = safeString(sum.summary_text || src.summary_text).trim()

  const totalCount = safeNumber(
    resolvedItemsCount || stepCount || enabledCount || appliedCount,
    0
  )

  const hasAppliedPrompt = !!(sum.has_applied_prompt || src.has_applied_prompt)
  const hasAvailableNotEnabled = !!(sum.has_available_not_enabled || src.has_available_not_enabled)
  const hasMissing = !!(sum.has_missing || src.has_missing)
  const hasSkipped = !!(sum.has_skipped || src.has_skipped)
  const hasSkills = !!(
    src.has_skills ||
    sum.has_skills ||
    strategyValue ||
    strategy ||
    status ||
    message ||
    totalCount > 0 ||
    stepRows.length > 0 ||
    enabledCount > 0 ||
    appliedCount > 0 ||
    promptLen > 0
  )

  return {
    raw: src,
    strategy,
    strategyValue,
    status,
    message,
    promptLen,
    items: [],
    totalCount,
    builtinCount: 0,
    customCount: 0,
    enabledIds,
    appliedIds,
    enabledCount,
    appliedCount,
    resolvedItemsCount,
    stepCount,
    stepRows,
    hasSkills,
    hasAppliedPrompt,
    hasAvailableNotEnabled,
    hasMissing,
    hasSkipped,
    sourceType,
    sourceEventType,
    sourceRunId,
    summaryText,
  }
}

function hasRuntimeSkillsInfo(info) {
  const src = safeObject(info)
  return !!(
    src.hasSkills ||
    safeString(src.strategyValue).trim() ||
    safeString(src.strategy).trim() ||
    safeString(src.status).trim() ||
    safeString(src.message).trim() ||
    safeNumber(src.totalCount, 0) > 0 ||
    safeNumber(src.enabledCount, 0) > 0 ||
    safeNumber(src.appliedCount, 0) > 0 ||
    safeArray(src.stepRows).length > 0 ||
    safeNumber(src.promptLen, 0) > 0
  )
}

function readSupervisorSkillsContainer(payload) {
  const src = safeObject(payload)

  const container = safeObject(
    src.supervisor_skills ||
    src.supervisorSkills ||
    src.supervisor_skill_state ||
    src.supervisorSkillState
  )

  if (Object.keys(container).length) return container
  return {}
}

function readSupervisorSkillsAudit(payload) {
  const src = safeObject(payload)
  return safeObject(src.synthesis_audit || src.synthesisAudit)
}

function readRoomStateSnapshot(payload) {
  const src = safeObject(payload)

  return safeObject(
    src.room_state_snapshot ||
    src.roomStateSnapshot ||
    src.state_snapshot ||
    src.stateSnapshot ||
    src.room_state ||
    src.roomState ||
    src.state
  )
}

function findSupervisorSkillsToolResult(payload) {
  const toolResults = safeArray(
    payload?.tool_results || payload?.toolResults
  )

  for (const row of toolResults) {
    const item = safeObject(row)
    const type = safeString(item.type).trim().toLowerCase()
    const name = safeString(item.name || item.tool_name || item.toolName).trim().toLowerCase()

    if (type === 'supervisor_skills') return item
    if (name === 'supervisor_skills') return item
    if (name.includes('supervisor_skill')) return item
  }

  return {}
}

function normalizeSupervisorSkillsInfo(payload) {
  const src = safeObject(payload)
  if (!Object.keys(src).length) return null

  const container = readSupervisorSkillsContainer(src)
  const audit = readSupervisorSkillsAudit(src)
  const toolRow = findSupervisorSkillsToolResult(src)
  const roomStateSnapshot = readRoomStateSnapshot(src)

  const collected = []

  appendNormalizedSkills(collected, container.enabled_skills || container.enabledSkills)
  appendNormalizedSkills(collected, container.skills)
  appendNormalizedSkills(collected, container.items)
  appendNormalizedSkills(collected, container.applied_skills || container.appliedSkills)

  appendNormalizedSkills(collected, container.builtin_skills || container.builtinSkills, 'builtin')
  appendNormalizedSkills(collected, container.custom_skills || container.customSkills, 'custom')
  appendNormalizedSkills(collected, container.workspace_skills || container.workspaceSkills, 'custom')

  appendSkillNames(collected, container.builtin_skill_names || container.builtinSkillNames, 'builtin')
  appendSkillNames(collected, container.custom_skill_names || container.customSkillNames, 'custom')
  appendSkillNames(collected, container.workspace_skill_names || container.workspaceSkillNames, 'custom')

  const enabledIds = firstNonEmptyArray(
    container.enabled_skill_ids,
    container.enabled_ids,
    container.enabled_skill_names,
    container.enabledSkills,
    audit.supervisor_skills_enabled_ids,
    audit.supervisor_skills_enabled_names,
    toolRow.enabled_skill_ids,
    toolRow.enabled_ids,
    toolRow.enabled_skill_names,
    roomStateSnapshot.enabled_supervisor_skill_ids
  )

  const appliedIds = firstNonEmptyArray(
    container.applied_skill_ids,
    container.applied_ids,
    container.applied_skill_names,
    container.appliedSkills,
    audit.supervisor_skills_applied_ids,
    audit.supervisor_skills_applied_names,
    toolRow.applied_skill_ids,
    toolRow.applied_ids,
    toolRow.applied_skill_names
  )

  const items = dedupeSkills(collected)

  const strategyValue = normalizeFormalSkillStrategy(
    container.strategy ||
    container.mode ||
    container.composition_strategy ||
    container.compositionStrategy ||
    audit.supervisor_skills_strategy ||
    toolRow.strategy ||
    toolRow.mode ||
    roomStateSnapshot.supervisor_skill_strategy
  )

  const strategy = formatSkillStrategyLabel(strategyValue)

  const status = safeString(
    container.status ||
    audit.supervisor_skills_status ||
    toolRow.status
  ).trim()

  const promptLen = safeNumber(
    container.prompt_len ||
    container.promptLen ||
    audit.supervisor_skills_prompt_len ||
    toolRow.prompt_len ||
    toolRow.promptLen ||
    0
  )

  const totalCount = items.length || enabledIds.length || appliedIds.length

  if (
    !Object.keys(container).length &&
    !Object.keys(audit).length &&
    !Object.keys(toolRow).length &&
    !Object.keys(roomStateSnapshot).length &&
    !totalCount &&
    !strategyValue &&
    !status
  ) {
    return null
  }

  return {
    raw: {
      container,
      audit,
      tool_result: toolRow,
      room_state_snapshot: roomStateSnapshot,
    },
    strategy,
    strategyValue,
    status,
    promptLen,
    items,
    totalCount,
    builtinCount: 0,
    customCount: 0,
    enabledIds,
    appliedIds,
    enabledCount: enabledIds.length,
    appliedCount: appliedIds.length,
    resolvedItemsCount: totalCount,
    stepCount: 0,
    stepRows: [],
    hasSkills: !!(totalCount || enabledIds.length || appliedIds.length || strategyValue || status),
    hasAppliedPrompt: false,
    hasAvailableNotEnabled: false,
    hasMissing: false,
    hasSkipped: false,
    sourceType: '',
    sourceEventType: '',
    sourceRunId: '',
    summaryText: '',
    message: '',
  }
}

function findRuntimeSkillsInfo(resultPayload, resultEvent, processItems) {
  const candidates = [
    safeObject(resultPayload),
    safeObject(resultEvent?.payload),
    safeObject(resultEvent),
    ...safeArray(processItems)
      .slice()
      .reverse()
      .map((item) => getRuntimePayload(item)),
  ]

  for (const candidate of candidates) {
    const info = normalizeSupervisorSkillsInfo(candidate)
    if (!info) continue

    if (hasRuntimeSkillsInfo(info)) {
      return info
    }
  }

  return {
    raw: {},
    strategy: '',
    strategyValue: '',
    status: '',
    message: '',
    promptLen: 0,
    items: [],
    totalCount: 0,
    builtinCount: 0,
    customCount: 0,
    enabledIds: [],
    appliedIds: [],
    enabledCount: 0,
    appliedCount: 0,
    resolvedItemsCount: 0,
    stepCount: 0,
    stepRows: [],
    hasSkills: false,
    hasAppliedPrompt: false,
    hasAvailableNotEnabled: false,
    hasMissing: false,
    hasSkipped: false,
    sourceType: '',
    sourceEventType: '',
    sourceRunId: '',
    summaryText: '',
  }
}

function buildRuntimeSkillSummary(info) {
  const src = safeObject(info)
  const explicit = safeString(src.summaryText || src.summary_text).trim()
  if (explicit) return explicit

  const totalCount = safeNumber(
    src.totalCount || src.resolvedItemsCount || src.stepCount,
    0
  )
  const enabledCount = safeNumber(src.enabledCount, 0)
  const appliedCount = safeNumber(src.appliedCount, 0)
  const strategy = safeString(src.strategy).trim()
  const status = safeString(src.status).trim()

  const parts = []

  if (totalCount > 0) parts.push(`skills ${totalCount}`)
  if (enabledCount > 0) parts.push(`enabled ${enabledCount}`)
  if (appliedCount > 0) parts.push(`applied ${appliedCount}`)
  if (strategy) parts.push(strategy)

  if (!parts.length && status) {
    parts.push(status)
  }

  return parts.join(' · ')
}

function buildRuntimeSkillEntries(info, timeText = '') {
  const src = safeObject(info)
  const stepRows = safeArray(src.stepRows)
  const items = safeArray(src.items)
  const totalCount = safeNumber(src.totalCount || src.resolvedItemsCount || src.stepCount, 0)
  const enabledCount = safeNumber(src.enabledCount, 0)
  const appliedCount = safeNumber(src.appliedCount, 0)
  const strategy = safeString(src.strategy).trim()
  const status = safeString(src.status).trim()
  const message = safeString(src.message).trim()
  const summaryText = buildRuntimeSkillSummary(src)
  const normalizedTime = safeString(timeText).trim()

  if (!hasRuntimeSkillsInfo(src)) return []

  const entries = []

  entries.push({
    id: `runtime-skills-summary-${safeString(src.strategyValue || strategy || status || totalCount || 0).trim()}`,
    type: 'room.supervisor',
    typeClass: 'supervisor',
    badge: 'skill',
    title:
      appliedCount > 0
        ? `已应用 ${appliedCount} 个 skill`
        : enabledCount > 0
          ? `已启用 ${enabledCount} 个 skill`
          : totalCount > 0
            ? `发现 ${totalCount} 个 skill`
            : 'skill 配置',
    actor: strategy || status,
    summary: summaryText || message,
    metaChips: normalizeChipList([
      strategy,
      status,
      src.hasAvailableNotEnabled ? 'available_not_enabled' : '',
      src.hasAppliedPrompt ? 'applied_prompt' : '',
      src.sourceEventType,
    ]),
    timeText: normalizedTime,
    raw: src.raw,
    payload: { supervisor_skills: src.raw || src },
  })

  if (stepRows.length > 0) {
    stepRows.slice(0, 3).forEach((row, idx) => {
      const title = safeString(row.label || row.skill_id).trim()
      const actor = safeString(row.kind).trim()
      const summary = shortenText(
        [row.status, row.message, row.path].filter(Boolean).join(' · ')
      )

      entries.push({
        id: `runtime-skill-step-${idx}-${safeString(row.skill_id || row.label || idx).trim()}`,
        type: 'room.supervisor',
        typeClass: 'supervisor',
        badge: 'skill',
        title: title || `skill ${idx + 1}`,
        actor,
        summary,
        metaChips: normalizeChipList([actor, row.status, row.path]),
        timeText: normalizedTime,
        raw: row.raw,
        payload: { supervisor_skill_step: row.raw },
      })
    })

    return entries
  }

  items.slice(0, 3).forEach((item, idx) => {
    const source = safeString(item.source).trim()
    const actor =
      source === 'builtin'
        ? 'builtin'
        : source === 'custom'
          ? 'workspace'
          : ''

    const detail = shortenText(
      item.summary ||
      item.title ||
      item.relativePath ||
      ''
    )

    entries.push({
      id: `runtime-skill-${idx}-${safeString(item.id || item.name).trim()}`,
      type: 'room.supervisor',
      typeClass: 'supervisor',
      badge: 'skill',
      title: safeString(item.name).trim(),
      actor,
      summary: detail,
      metaChips: normalizeChipList([actor, item.relativePath]),
      timeText: normalizedTime,
      raw: item.raw,
      payload: { supervisor_skill: item.raw },
    })
  })

  return entries
}

function readSupervisorMemoryContainer(payload) {
  const src = safeObject(payload)

  const direct = safeObject(
    src.supervisor_memory ||
    src.supervisorMemory ||
    src.supervisor_memory_state ||
    src.supervisorMemoryState
  )

  const merged = {}

  if (Object.keys(direct).length) {
    Object.assign(merged, direct)
  }

  const read = safeObject(src.supervisor_memory_read || src.supervisorMemoryRead)
  const resume = safeObject(src.supervisor_memory_resume || src.supervisorMemoryResume)
  const write = safeObject(src.supervisor_memory_write || src.supervisorMemoryWrite)

  if (Object.keys(read).length) merged.read = read
  if (Object.keys(resume).length) merged.resume = resume
  if (Object.keys(write).length) merged.write = write

  return merged
}

function readSupervisorMemoryAudit(payload) {
  const src = safeObject(payload)
  return safeObject(src.synthesis_audit || src.synthesisAudit)
}

function findSupervisorMemoryToolResults(payload) {
  const toolResults = safeArray(
    payload?.tool_results || payload?.toolResults
  )

  const found = {
    read: {},
    resume: {},
    write: {},
  }

  toolResults.forEach((row) => {
    const item = safeObject(row)
    const type = safeString(item.type).trim().toLowerCase()
    const name = safeString(item.name || item.tool_name || item.toolName).trim().toLowerCase()

    if (type === 'supervisor_memory_read' || name === 'supervisor_memory_read') {
      found.read = item
    } else if (type === 'supervisor_memory_resume' || name === 'supervisor_memory_resume') {
      found.resume = item
    } else if (type === 'supervisor_memory_write' || name === 'supervisor_memory_write') {
      found.write = item
    }
  })

  return found
}

function normalizeRuntimeDisplaySupervisorMemory(bundle, summary = null) {
  const src = safeObject(bundle)
  const sum = safeObject(summary)

  const readStatus = safeString(src.read_status || sum.read_status).trim()
  const readMessage = safeString(src.read_message || sum.read_message).trim()
  const readReasonCode = safeString(src.read_reason_code || sum.read_reason_code).trim()

  const resumeDecision = safeString(src.resume_decision || sum.resume_decision).trim()
  const resumeReason = safeString(src.resume_reason || sum.resume_reason).trim()
  const resumeReady = !!(
    src.resume_ready !== undefined
      ? src.resume_ready
      : sum.resume_ready
  )

  const checkpointStage = safeString(src.checkpoint_stage || sum.checkpoint_stage).trim()
  const checkpointSummary = safeString(src.checkpoint_summary || sum.checkpoint_summary).trim()
  const recoveryHint = safeString(src.recovery_hint || sum.recovery_hint).trim()

  const writeStatus = safeString(src.write_status || sum.write_status).trim()
  const writeMessage = safeString(src.write_message || sum.write_message).trim()
  const writeReasonCode = safeString(src.write_reason_code || sum.write_reason_code).trim()

  const relativePath = safeString(src.relative_path || sum.relative_path).trim()
  const sourceKind = safeString(src.source_kind || sum.source_kind).trim()
  const bytesWritten = safeNumber(src.bytes_written ?? sum.bytes_written, 0)

  const sourceType = safeString(src.source_type || sum.source_type).trim()
  const sourceEventType = safeString(src.source_event_type || sum.source_event_type).trim()
  const sourceRunId = safeString(src.source_run_id || sum.source_run_id).trim()
  const summaryText = safeString(src.summary_text || sum.summary_text).trim()

  const hasResume = !!(
    src.has_resume ||
    sum.has_resume ||
    resumeDecision ||
    resumeReason ||
    resumeReady
  )

  const hasWrite = !!(
    src.has_write ||
    sum.has_write ||
    writeStatus ||
    writeMessage ||
    writeReasonCode ||
    bytesWritten > 0
  )

  const hasCheckpoint = !!(
    src.has_checkpoint ||
    sum.has_checkpoint ||
    checkpointStage ||
    checkpointSummary ||
    recoveryHint
  )

  const hasMemory = !!(
    src.has_memory ||
    sum.has_memory ||
    readStatus ||
    readMessage ||
    readReasonCode ||
    resumeDecision ||
    resumeReason ||
    resumeReady ||
    checkpointStage ||
    checkpointSummary ||
    recoveryHint ||
    writeStatus ||
    writeMessage ||
    writeReasonCode ||
    relativePath ||
    sourceKind ||
    bytesWritten > 0
  )

  return {
    raw: src,
    hasMemory,
    readStatus,
    readMessage,
    readReasonCode,
    resumeDecision,
    resumeReason,
    resumeReady,
    checkpointStage,
    checkpointSummary,
    recoveryHint,
    writeStatus,
    writeMessage,
    writeReasonCode,
    relativePath,
    sourceKind,
    bytesWritten,
    hasResume,
    hasWrite,
    hasCheckpoint,
    sourceType,
    sourceEventType,
    sourceRunId,
    summaryText,
  }
}

function hasRuntimeMemoryInfo(info) {
  const src = safeObject(info)
  return !!(
    src.hasMemory ||
    safeString(src.readStatus).trim() ||
    safeString(src.readMessage).trim() ||
    safeString(src.readReasonCode).trim() ||
    safeString(src.resumeDecision).trim() ||
    safeString(src.resumeReason).trim() ||
    !!src.resumeReady ||
    safeString(src.checkpointStage).trim() ||
    safeString(src.checkpointSummary).trim() ||
    safeString(src.recoveryHint).trim() ||
    safeString(src.writeStatus).trim() ||
    safeString(src.writeMessage).trim() ||
    safeString(src.writeReasonCode).trim() ||
    safeString(src.relativePath).trim() ||
    safeString(src.sourceKind).trim() ||
    safeNumber(src.bytesWritten, 0) > 0
  )
}

function normalizeSupervisorMemoryInfo(payload) {
  const src = safeObject(payload)
  if (!Object.keys(src).length) return null

  const container = readSupervisorMemoryContainer(src)
  const audit = readSupervisorMemoryAudit(src)
  const toolRows = findSupervisorMemoryToolResults(src)
  const roomStateSnapshot = readRoomStateSnapshot(src)

  const read = safeObject(
    container.read ||
    container.memory_read ||
    container.supervisor_memory_read ||
    src.supervisor_memory_read ||
    toolRows.read
  )

  const resume = safeObject(
    container.resume ||
    container.memory_resume ||
    container.supervisor_memory_resume ||
    src.supervisor_memory_resume ||
    toolRows.resume
  )

  const write = safeObject(
    container.write ||
    container.memory_write ||
    container.supervisor_memory_write ||
    src.supervisor_memory_write ||
    toolRows.write
  )

  const readStatus = safeString(
    read.status ||
    audit.memory_read_status ||
    roomStateSnapshot.last_supervisor_memory_read_status ||
    roomStateSnapshot.supervisor_memory_read_status
  ).trim()

  const readMessage = safeString(
    read.message ||
    roomStateSnapshot.last_supervisor_memory_read_message ||
    roomStateSnapshot.supervisor_memory_read_message
  ).trim()

  const readReasonCode = safeString(
    read.reason_code ||
    roomStateSnapshot.last_supervisor_memory_read_reason_code ||
    roomStateSnapshot.supervisor_memory_read_reason_code
  ).trim()

  const resumeDecision = safeString(
    resume.decision ||
    resume.resume_decision ||
    audit.memory_resume_decision ||
    roomStateSnapshot.last_supervisor_memory_resume_decision ||
    roomStateSnapshot.supervisor_memory_resume_decision
  ).trim()

  const resumeReason = safeString(
    resume.reason ||
    audit.memory_resume_reason ||
    roomStateSnapshot.last_supervisor_memory_resume_reason ||
    roomStateSnapshot.supervisor_memory_resume_reason
  ).trim()

  const resumeReady = !!(
    resume.resume_ready ||
    roomStateSnapshot.last_supervisor_memory_resume_ready ||
    roomStateSnapshot.supervisor_memory_resume_ready
  )

  const checkpointStage = safeString(
    write.checkpoint_stage ||
    resume.checkpoint_stage ||
    audit.memory_checkpoint_stage ||
    roomStateSnapshot.last_supervisor_memory_write_checkpoint_stage ||
    roomStateSnapshot.last_supervisor_memory_resume_checkpoint_stage ||
    roomStateSnapshot.supervisor_memory_checkpoint_stage
  ).trim()

  const checkpointSummary = safeString(
    write.checkpoint_summary ||
    resume.checkpoint_summary ||
    roomStateSnapshot.last_supervisor_memory_write_checkpoint_summary ||
    roomStateSnapshot.last_supervisor_memory_resume_checkpoint_summary ||
    roomStateSnapshot.supervisor_memory_checkpoint_summary
  ).trim()

  const recoveryHint = safeString(
    resume.recovery_hint ||
    roomStateSnapshot.last_supervisor_memory_resume_recovery_hint ||
    roomStateSnapshot.supervisor_memory_recovery_hint
  ).trim()

  const writeStatus = safeString(
    write.status ||
    roomStateSnapshot.last_supervisor_memory_write_status ||
    roomStateSnapshot.supervisor_memory_write_status
  ).trim()

  const writeMessage = safeString(
    write.message ||
    roomStateSnapshot.last_supervisor_memory_write_message ||
    roomStateSnapshot.supervisor_memory_write_message
  ).trim()

  const writeReasonCode = safeString(
    write.reason_code ||
    roomStateSnapshot.last_supervisor_memory_write_reason_code ||
    roomStateSnapshot.supervisor_memory_write_reason_code
  ).trim()

  const relativePath = safeString(
    write.relative_path ||
    resume.relative_path ||
    read.relative_path ||
    roomStateSnapshot.last_supervisor_memory_write_relative_path ||
    roomStateSnapshot.last_supervisor_memory_resume_relative_path ||
    roomStateSnapshot.last_supervisor_memory_read_relative_path ||
    roomStateSnapshot.supervisor_memory_relative_path
  ).trim()

  const sourceKind = safeString(
    write.source_kind ||
    read.source_kind ||
    roomStateSnapshot.last_supervisor_memory_write_source_kind ||
    roomStateSnapshot.last_supervisor_memory_read_source_kind ||
    roomStateSnapshot.supervisor_memory_source_kind
  ).trim()

  const bytesWritten = safeNumber(
    write.bytes_written ||
    roomStateSnapshot.last_supervisor_memory_write_bytes_written ||
    roomStateSnapshot.supervisor_memory_write_bytes_written,
    0
  )

  const hasResume = !!(resumeDecision || resumeReason || resumeReady)
  const hasWrite = !!(writeStatus || writeMessage || writeReasonCode || bytesWritten > 0)
  const hasCheckpoint = !!(checkpointStage || checkpointSummary || recoveryHint)

  const hasMemory = !!(
    readStatus ||
    readMessage ||
    readReasonCode ||
    resumeDecision ||
    resumeReason ||
    resumeReady ||
    checkpointStage ||
    checkpointSummary ||
    recoveryHint ||
    writeStatus ||
    writeMessage ||
    writeReasonCode ||
    relativePath ||
    sourceKind ||
    bytesWritten > 0
  )

  if (
    !Object.keys(container).length &&
    !Object.keys(audit).length &&
    !Object.keys(toolRows.read).length &&
    !Object.keys(toolRows.resume).length &&
    !Object.keys(toolRows.write).length &&
    !Object.keys(roomStateSnapshot).length &&
    !hasMemory
  ) {
    return null
  }

  return {
    raw: {
      container,
      audit,
      tool_results: toolRows,
      room_state_snapshot: roomStateSnapshot,
    },
    hasMemory,
    readStatus,
    readMessage,
    readReasonCode,
    resumeDecision,
    resumeReason,
    resumeReady,
    checkpointStage,
    checkpointSummary,
    recoveryHint,
    writeStatus,
    writeMessage,
    writeReasonCode,
    relativePath,
    sourceKind,
    bytesWritten,
    hasResume,
    hasWrite,
    hasCheckpoint,
    sourceType: '',
    sourceEventType: '',
    sourceRunId: '',
    summaryText: '',
  }
}

function findRuntimeMemoryInfo(resultPayload, resultEvent, processItems) {
  const candidates = [
    safeObject(resultPayload),
    safeObject(resultEvent?.payload),
    safeObject(resultEvent),
    ...safeArray(processItems)
      .slice()
      .reverse()
      .map((item) => getRuntimePayload(item)),
  ]

  for (const candidate of candidates) {
    const info = normalizeSupervisorMemoryInfo(candidate)
    if (!info) continue

    if (hasRuntimeMemoryInfo(info)) {
      return info
    }
  }

  return {
    raw: {},
    hasMemory: false,
    readStatus: '',
    readMessage: '',
    readReasonCode: '',
    resumeDecision: '',
    resumeReason: '',
    resumeReady: false,
    checkpointStage: '',
    checkpointSummary: '',
    recoveryHint: '',
    writeStatus: '',
    writeMessage: '',
    writeReasonCode: '',
    relativePath: '',
    sourceKind: '',
    bytesWritten: 0,
    hasResume: false,
    hasWrite: false,
    hasCheckpoint: false,
    sourceType: '',
    sourceEventType: '',
    sourceRunId: '',
    summaryText: '',
  }
}

function buildRuntimeMemorySummary(info) {
  const src = safeObject(info)
  const explicit = safeString(src.summaryText || src.summary_text).trim()
  if (explicit) return explicit

  const parts = []

  if (safeString(src.readStatus).trim()) parts.push(`read ${safeString(src.readStatus).trim()}`)
  if (safeString(src.resumeDecision).trim()) parts.push(`resume ${safeString(src.resumeDecision).trim()}`)
  if (safeString(src.writeStatus).trim()) parts.push(`write ${safeString(src.writeStatus).trim()}`)
  if (safeString(src.checkpointStage).trim()) parts.push(`checkpoint ${safeString(src.checkpointStage).trim()}`)

  if (!parts.length && safeString(src.resumeReason).trim()) {
    parts.push(safeString(src.resumeReason).trim())
  }

  return parts.join(' · ')
}

function buildRuntimeMemoryEntries(info, timeText = '') {
  const src = safeObject(info)
  const normalizedTime = safeString(timeText).trim()

  if (!hasRuntimeMemoryInfo(src)) return []

  const entries = []

  entries.push({
    id: `runtime-memory-summary-${safeString(src.resumeDecision || src.writeStatus || src.readStatus || src.checkpointStage || 0).trim()}`,
    type: 'room.supervisor',
    typeClass: 'supervisor',
    badge: 'memory',
    title: 'Supervisor memory',
    actor: safeString(src.resumeDecision || src.writeStatus || src.readStatus).trim(),
    summary: buildRuntimeMemorySummary(src),
    metaChips: normalizeChipList([
      src.readStatus ? `read:${src.readStatus}` : '',
      src.resumeDecision ? `resume:${src.resumeDecision}` : '',
      src.writeStatus ? `write:${src.writeStatus}` : '',
      src.checkpointStage ? `checkpoint:${src.checkpointStage}` : '',
    ]),
    timeText: normalizedTime,
    raw: src.raw,
    payload: { supervisor_memory: src.raw || src },
  })

  if (safeString(src.readStatus).trim() || safeString(src.readMessage).trim() || safeString(src.readReasonCode).trim()) {
    entries.push({
      id: `runtime-memory-read-${safeString(src.readStatus || 'none').trim()}`,
      type: 'room.supervisor',
      typeClass: 'supervisor',
      badge: 'memory',
      title: 'Memory 读取',
      actor: safeString(src.readStatus).trim(),
      summary: shortenText(
        [src.readMessage, src.readReasonCode, src.relativePath].filter(Boolean).join(' · ')
      ),
      metaChips: normalizeChipList([
        src.readStatus,
        src.readReasonCode,
        src.sourceKind,
      ]),
      timeText: normalizedTime,
      raw: src.raw,
      payload: { supervisor_memory_read: src.raw || src },
    })
  }

  if (safeString(src.resumeDecision).trim() || safeString(src.resumeReason).trim() || src.resumeReady) {
    entries.push({
      id: `runtime-memory-resume-${safeString(src.resumeDecision || 'none').trim()}`,
      type: 'room.supervisor',
      typeClass: 'supervisor',
      badge: 'memory',
      title: 'Memory 恢复',
      actor: safeString(src.resumeDecision).trim(),
      summary: shortenText(
        [src.resumeReason, src.checkpointSummary, src.recoveryHint].filter(Boolean).join(' · ')
      ),
      metaChips: normalizeChipList([
        src.resumeDecision,
        src.resumeReady ? 'resume_ready' : '',
        src.checkpointStage,
      ]),
      timeText: normalizedTime,
      raw: src.raw,
      payload: { supervisor_memory_resume: src.raw || src },
    })
  }

  if (safeString(src.writeStatus).trim() || safeString(src.writeMessage).trim() || safeNumber(src.bytesWritten, 0) > 0) {
    entries.push({
      id: `runtime-memory-write-${safeString(src.writeStatus || 'none').trim()}`,
      type: 'room.supervisor',
      typeClass: 'supervisor',
      badge: 'memory',
      title: 'Memory 写入',
      actor: safeString(src.writeStatus).trim(),
      summary: shortenText(
        [
          src.writeMessage,
          src.relativePath,
          safeNumber(src.bytesWritten, 0) > 0 ? `${safeNumber(src.bytesWritten, 0)} bytes` : '',
        ].filter(Boolean).join(' · ')
      ),
      metaChips: normalizeChipList([
        src.writeStatus,
        src.sourceKind,
        src.checkpointStage,
      ]),
      timeText: normalizedTime,
      raw: src.raw,
      payload: { supervisor_memory_write: src.raw || src },
    })
  }

  return entries.slice(0, 4)
}

export function use_chat_panel_room_runtime_view_model({
  process_items,
  result_event,
  result_payload,
  result_text,
  runtime_supervisor_skills,
  runtime_supervisor_skills_summary,
  runtime_supervisor_memory,
  runtime_supervisor_memory_summary,
}) {
  const normalizedResultEvent = computed(() => safeObject(unref(result_event)))

  const normalizedResultPayload = computed(() => {
    const explicit = safeObject(unref(result_payload))
    if (Object.keys(explicit).length > 0) return explicit
    return getRuntimePayload(normalizedResultEvent.value)
  })

  const processEntries = computed(() => {
    return safeArray(unref(process_items))
      .map((item) => buildRuntimeEntry(item))
      .filter(Boolean)
  })

  const resultEntry = computed(() => {
    if (Object.keys(normalizedResultEvent.value).length) {
      return buildRuntimeEntry(normalizedResultEvent.value, normalizedResultPayload.value)
    }
    return buildLegalRuntimeSyntheticEntry(normalizedResultPayload.value)
  })

  const resultTextDisplay = computed(() => {
    const explicit = safeString(unref(result_text)).trim()
    if (explicit) return explicit

    return safeString(
      normalizedResultPayload.value.response ||
      normalizedResultPayload.value.content ||
      normalizedResultPayload.value.message
    ).trim()
  })

  const resultCitations = computed(() => {
    return safeArray(normalizedResultPayload.value.citations)
  })

  const hasTerminalResult = computed(() => {
    const entry = resultEntry.value
    if (!entry) return false
    return [
      'room.final',
      'room.error',
      'room.abort',
      'room.aborted',
      'room.manual',
      'room.skipped',
      'room.denied',
      'room.no_auto_reply',
    ].includes(entry.type)
  })

  const latestProcessStage = computed(() => {
    const list = processEntries.value
    const last = list.length ? list[list.length - 1] : null
    return safeString(last?.badge).trim()
  })

  const latestProcessActor = computed(() => {
    const list = processEntries.value
    const last = list.length ? list[list.length - 1] : null
    return safeString(last?.actor).trim()
  })

  const latestProcessTime = computed(() => {
    const list = processEntries.value
    const last = list.length ? list[list.length - 1] : null
    return safeString(last?.timeText).trim()
  })

  const runtimeSupervisorSkills = computed(() => {
    return normalizeRuntimeDisplaySupervisorSkills(
      unref(runtime_supervisor_skills),
      unref(runtime_supervisor_skills_summary)
    )
  })

  const runtimeSkillsInfo = computed(() => {
    if (hasRuntimeSkillsInfo(runtimeSupervisorSkills.value)) {
      return runtimeSupervisorSkills.value
    }

    return findRuntimeSkillsInfo(
      normalizedResultPayload.value,
      normalizedResultEvent.value,
      safeArray(unref(process_items))
    )
  })

  const runtimeSkillSummary = computed(() => {
    return buildRuntimeSkillSummary(runtimeSkillsInfo.value)
  })

  const runtimeSupervisorSkillsSummary = computed(() => {
    const src = safeObject(runtimeSkillsInfo.value)

    return {
      has_skills: hasRuntimeSkillsInfo(src),
      strategy: safeString(src.strategy).trim(),
      strategy_value: safeString(src.strategyValue).trim(),
      status: safeString(src.status).trim(),
      message: safeString(src.message).trim(),
      enabled_count: safeNumber(src.enabledCount, 0),
      applied_count: safeNumber(src.appliedCount, 0),
      resolved_items_count: safeNumber(src.resolvedItemsCount || src.totalCount, 0),
      step_count: safeNumber(src.stepCount, safeArray(src.stepRows).length),
      has_applied_prompt: !!src.hasAppliedPrompt,
      has_available_not_enabled: !!src.hasAvailableNotEnabled,
      has_missing: !!src.hasMissing,
      has_skipped: !!src.hasSkipped,
      source_type: safeString(src.sourceType).trim(),
      source_event_type: safeString(src.sourceEventType).trim(),
      source_run_id: safeString(src.sourceRunId).trim(),
      summary_text: buildRuntimeSkillSummary(src),
    }
  })

  const runtimeSkillEntries = computed(() => {
    const fallbackTime =
      latestProcessTime.value ||
      safeString(resultEntry.value?.timeText).trim()

    return buildRuntimeSkillEntries(runtimeSkillsInfo.value, fallbackTime)
  })

  const runtimeSupervisorMemory = computed(() => {
    return normalizeRuntimeDisplaySupervisorMemory(
      unref(runtime_supervisor_memory),
      unref(runtime_supervisor_memory_summary)
    )
  })

  const runtimeMemoryInfo = computed(() => {
    if (hasRuntimeMemoryInfo(runtimeSupervisorMemory.value)) {
      return runtimeSupervisorMemory.value
    }

    return findRuntimeMemoryInfo(
      normalizedResultPayload.value,
      normalizedResultEvent.value,
      safeArray(unref(process_items))
    )
  })

  const runtimeMemorySummary = computed(() => {
    return buildRuntimeMemorySummary(runtimeMemoryInfo.value)
  })

  const runtimeSupervisorMemorySummary = computed(() => {
    const src = safeObject(runtimeMemoryInfo.value)

    return {
      has_memory: hasRuntimeMemoryInfo(src),
      read_status: safeString(src.readStatus).trim(),
      read_message: safeString(src.readMessage).trim(),
      read_reason_code: safeString(src.readReasonCode).trim(),
      resume_decision: safeString(src.resumeDecision).trim(),
      resume_reason: safeString(src.resumeReason).trim(),
      resume_ready: !!src.resumeReady,
      checkpoint_stage: safeString(src.checkpointStage).trim(),
      checkpoint_summary: safeString(src.checkpointSummary).trim(),
      recovery_hint: safeString(src.recoveryHint).trim(),
      write_status: safeString(src.writeStatus).trim(),
      write_message: safeString(src.writeMessage).trim(),
      write_reason_code: safeString(src.writeReasonCode).trim(),
      relative_path: safeString(src.relativePath).trim(),
      source_kind: safeString(src.sourceKind).trim(),
      bytes_written: safeNumber(src.bytesWritten, 0),
      has_resume: !!src.hasResume,
      has_write: !!src.hasWrite,
      has_checkpoint: !!src.hasCheckpoint,
      source_type: safeString(src.sourceType).trim(),
      source_event_type: safeString(src.sourceEventType).trim(),
      source_run_id: safeString(src.sourceRunId).trim(),
      summary_text: buildRuntimeMemorySummary(src),
    }
  })

  const runtimeMemoryEntries = computed(() => {
    const fallbackTime =
      latestProcessTime.value ||
      safeString(resultEntry.value?.timeText).trim()

    return buildRuntimeMemoryEntries(runtimeMemoryInfo.value, fallbackTime)
  })

  const runtimeHeadline = computed(() => {
    if (resultEntry.value?.title) return resultEntry.value.title
    if (latestProcessStage.value) return `当前阶段：${latestProcessStage.value}`
    return '运行过程'
  })

  const runtimeBadgeSummary = computed(() => {
    const parts = [
      latestProcessStage.value,
      latestProcessActor.value,
      latestProcessTime.value,
    ].filter(Boolean)

    return parts.join(' · ')
  })

  return {
    processEntries,
    resultEntry,
    resultTextDisplay,
    resultCitations,
    runtimeHeadline,
    runtimeBadgeSummary,
    hasTerminalResult,
    latestProcessStage,
    latestProcessActor,
    latestProcessTime,
    runtimeSupervisorSkills,
    runtimeSupervisorSkillsSummary,
    runtimeSkillsInfo,
    runtimeSkillSummary,
    runtimeSkillEntries,
    runtimeSupervisorMemory,
    runtimeSupervisorMemorySummary,
    runtimeMemoryInfo,
    runtimeMemorySummary,
    runtimeMemoryEntries,
  }
}

export default use_chat_panel_room_runtime_view_model

