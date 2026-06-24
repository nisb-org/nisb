import {
  safe_array,
  safe_object,
  safe_string,
  normalize_bool,
} from '../room_shared'
import {
  normalize_runtime_path,
  normalize_tool_results,
} from '../room_protocol'
import {
  compact_text,
  pretty_json,
} from './room_runtime_presenter_utils'

function pick_first_non_empty_object(...values) {
  for (const value of values) {
    const obj = safe_object(value)
    if (Object.keys(obj).length > 0) return obj
  }
  return {}
}

function derive_supervisor_skills_from_state_snapshot(state = {}) {
  const src = safe_object(state)

  const enabledCustomSkillIds = safe_array(
    src.enabled_supervisor_skill_ids ||
      src.enabled_skill_ids
  )

  const appliedCustomSkillIds = safe_array(
    src.applied_supervisor_skill_ids ||
      src.applied_skill_ids
  )

  const strategy = normalize_skill_strategy(
    src.supervisor_skill_strategy ||
      src.skill_strategy,
    'builtin_plus_custom'
  )

  if (
    !enabledCustomSkillIds.length &&
    !appliedCustomSkillIds.length &&
    !safe_string(src.supervisor_skill_strategy || src.skill_strategy).trim()
  ) {
    return {}
  }

  return {
    strategy,
    enabled_custom_skill_ids: enabledCustomSkillIds,
    applied_custom_skill_ids: appliedCustomSkillIds,
  }
}

function pick_supervisor_skills_source(payload = {}) {
  const data = safe_object(payload)

  const directCandidates = [
    data.supervisor_skills,
    safe_object(data.audit).supervisor_skills,
    safe_object(data.result).supervisor_skills,
    safe_object(data.runtime).supervisor_skills,
    safe_object(data.payload).supervisor_skills,
  ]

  for (const item of directCandidates) {
    const row = safe_object(item)
    if (Object.keys(row).length) return row
  }

  const toolResultCandidates = [
    ...safe_array(normalize_tool_results(data)),
    ...safe_array(normalize_tool_results(data.result)),
    ...safe_array(normalize_tool_results(data.payload)),
  ]

  for (const item of toolResultCandidates) {
    const row = safe_object(item)
    const identity = safe_string(
      row.type ||
        row.tool_name ||
        row.name
    ).trim().toLowerCase()

    if (identity !== 'supervisor_skills') continue

    const structured = pick_first_non_empty_object(
      row.result,
      row.payload,
      row.data,
      row.value
    )

    if (Object.keys(structured).length) return structured
  }

  const stateCandidates = [
    data.room_state_snapshot,
    data.state_snapshot,
    data.room_state,
    data.state,
    safe_object(data.room).state,
    safe_object(data.audit).room_state_snapshot,
    safe_object(data.runtime).room_state_snapshot,
    safe_object(data.result).room_state_snapshot,
    safe_object(data.payload).room_state_snapshot,
  ]

  for (const item of stateCandidates) {
    const derived = derive_supervisor_skills_from_state_snapshot(item)
    if (Object.keys(derived).length) return derived
  }

  return {}
}

export function normalize_skill_strategy(
  value,
  fallback = 'builtin_plus_custom'
) {
  const s = safe_string(value).trim().toLowerCase()

  if (s === 'builtin_only') return 'builtin_only'
  if (s === 'custom_only') return 'custom_only'
  if (s === 'builtin_plus_custom') return 'builtin_plus_custom'
  if (s === 'builtin+custom') return 'builtin_plus_custom'
  if (s === 'builtin_custom') return 'builtin_plus_custom'
  if (s === 'append') return 'builtin_plus_custom'
  if (s === 'overlay') return 'builtin_plus_custom'

  return fallback
}

function build_skill_row_object(
  value,
  sourceFallback = '',
  appliedFallback = false,
  enabledFallback = true
) {
  const rawText = safe_string(value).trim()

  if (rawText) {
    return {
      skill_id: rawText,
      id: rawText,
      name: rawText,
      applied: appliedFallback,
      enabled: enabledFallback,
      source: sourceFallback,
    }
  }

  const src = safe_object(value)
  return {
    ...src,
    applied: src.applied === undefined ? appliedFallback : src.applied,
    enabled: src.enabled === undefined ? enabledFallback : src.enabled,
    source: safe_string(src.source).trim() || sourceFallback,
  }
}

function derive_skill_display_name(row = {}) {
  const src = safe_object(row)

  const explicit = safe_string(
    src.title ||
      src.name ||
      src.skill_name ||
      src.skill_id ||
      src.id ||
      src.slug ||
      src.filename
  ).trim()
  if (explicit) return explicit

  const path = normalize_runtime_path(src.relative_path || src.path)
  if (!path) return ''

  const base = safe_string(path.split('/').slice(-1)[0]).trim()
  if (!base) return ''

  return base.toLowerCase().endsWith('.md') ? base.slice(0, -3) : base
}

function normalize_skill_item(
  value = {},
  idx = 0,
  sourceFallback = '',
  appliedFallback = false,
  enabledFallback = true
) {
  const src = build_skill_row_object(
    value,
    sourceFallback,
    appliedFallback,
    enabledFallback
  )

  const name = derive_skill_display_name(src)
  if (!name) return null

  const source = safe_string(src.source).trim() || sourceFallback || 'custom'
  const enabled = normalize_bool(src.enabled, enabledFallback)
  const applied = normalize_bool(
    src.applied ?? src.used ?? src.selected,
    appliedFallback
  )
  const path = normalize_runtime_path(
    src.path ||
      src.relative_path ||
      src.filename
  )

  const summary = compact_text(
    src.summary ||
      src.message ||
      src.description ||
      src.preview ||
      '',
    180
  )

  return {
    key: safe_string(src.key || `${source}_${name}_${idx}`).trim(),
    name,
    source,
    enabled,
    applied,
    status_text: applied ? '已应用' : (enabled ? '已启用' : '未启用'),
    strategy_effect: safe_string(
      src.strategy_effect ||
        (applied ? 'included' : (enabled ? 'available' : ''))
    ).trim(),
    path,
    summary,
    raw: src,
  }
}

export function normalize_runtime_skill_summary(payload = {}) {
  const skillRoot = pick_supervisor_skills_source(payload)
  const hasRoot = Object.keys(skillRoot).length > 0

  const strategy = normalize_skill_strategy(
    skillRoot.strategy ||
      skillRoot.policy ||
      skillRoot.composition_strategy,
    'builtin_plus_custom'
  )

  const enabledBuiltin = safe_array(
    skillRoot.enabled_builtin_skills ||
      skillRoot.builtin_enabled_skills ||
      skillRoot.enabled_builtin_skill_ids
  )

  const enabledCustom = safe_array(
    skillRoot.enabled_custom_skills ||
      skillRoot.custom_enabled_skills ||
      skillRoot.enabled_custom_skill_ids
  )

  const enabledGeneric = safe_array(
    skillRoot.enabled_skills ||
      skillRoot.enabled_skill_ids
  )

  const appliedBuiltin = safe_array(
    skillRoot.applied_builtin_skills ||
      skillRoot.used_builtin_skills ||
      skillRoot.applied_builtin_skill_ids
  )

  const appliedCustom = safe_array(
    skillRoot.applied_custom_skills ||
      skillRoot.used_custom_skills ||
      skillRoot.applied_custom_skill_ids
  )

  const appliedGeneric = safe_array(
    skillRoot.applied_skills ||
      skillRoot.used_skills ||
      skillRoot.applied_skill_ids
  )

  const enabledCount =
    enabledBuiltin.length +
    enabledCustom.length +
    enabledGeneric.length

  const appliedCount =
    appliedBuiltin.length +
    appliedCustom.length +
    appliedGeneric.length

  const builtinEnabled =
    strategy !== 'custom_only' ||
    enabledBuiltin.length > 0 ||
    appliedBuiltin.length > 0

  const customEnabled =
    strategy !== 'builtin_only' ||
    enabledCustom.length > 0 ||
    appliedCustom.length > 0 ||
    enabledGeneric.length > 0 ||
    appliedGeneric.length > 0

  const hasSkills = hasRoot || enabledCount > 0 || appliedCount > 0

  return {
    strategy,
    enabled_count: enabledCount,
    applied_count: appliedCount,
    builtin_enabled: builtinEnabled,
    custom_enabled: customEnabled,
    has_skills: hasSkills,
    status_text: hasSkills
      ? `已启用 ${enabledCount} / 实际应用 ${appliedCount}`
      : '未记录 skills',
    raw: skillRoot,
  }
}

export function normalize_runtime_skill_cards(payload = {}) {
  const skillRoot = pick_supervisor_skills_source(payload)
  const cards = []
  const seen = new Set()

  const groups = [
    {
      list: safe_array(
        skillRoot.enabled_builtin_skills ||
        skillRoot.builtin_enabled_skills ||
        skillRoot.enabled_builtin_skill_ids
      ),
      source: 'builtin',
      applied: false,
      enabled: true,
    },
    {
      list: safe_array(
        skillRoot.enabled_custom_skills ||
        skillRoot.custom_enabled_skills ||
        skillRoot.enabled_custom_skill_ids
      ),
      source: 'custom',
      applied: false,
      enabled: true,
    },
    {
      list: safe_array(
        skillRoot.applied_builtin_skills ||
        skillRoot.used_builtin_skills ||
        skillRoot.applied_builtin_skill_ids
      ),
      source: 'builtin',
      applied: true,
      enabled: true,
    },
    {
      list: safe_array(
        skillRoot.applied_custom_skills ||
        skillRoot.used_custom_skills ||
        skillRoot.applied_custom_skill_ids
      ),
      source: 'custom',
      applied: true,
      enabled: true,
    },
    {
      list: safe_array(
        skillRoot.enabled_skills ||
        skillRoot.enabled_skill_ids
      ),
      source: '',
      applied: false,
      enabled: true,
    },
    {
      list: safe_array(
        skillRoot.applied_skills ||
        skillRoot.used_skills ||
        skillRoot.applied_skill_ids
      ),
      source: '',
      applied: true,
      enabled: true,
    },
  ]

  for (const group of groups) {
    for (const item of group.list) {
      const card = normalize_skill_item(
        item,
        cards.length,
        group.source,
        group.applied,
        group.enabled
      )
      if (!card) continue

      const dedupeKey = `${card.source}::${card.name}::${card.path || ''}`

      if (seen.has(dedupeKey)) {
        const idx = cards.findIndex(
          (x) => `${x.source}::${x.name}::${x.path || ''}` === dedupeKey
        )
        if (idx >= 0) {
          cards[idx] = {
            ...cards[idx],
            ...card,
            enabled: cards[idx].enabled || card.enabled,
            applied: cards[idx].applied || card.applied,
            status_text:
              (cards[idx].applied || card.applied)
                ? '已应用'
                : ((cards[idx].enabled || card.enabled) ? '已启用' : '未启用'),
          }
        }
        continue
      }

      seen.add(dedupeKey)
      cards.push(card)
    }
  }

  return cards
}

export function normalize_runtime_skill_activity_rows(payload = {}) {
  const summary = normalize_runtime_skill_summary(payload)
  const cards = normalize_runtime_skill_cards(payload)
  const rows = []

  if (summary.has_skills) {
    rows.push({
      key: 'skill_strategy',
      name: 'Skill 组合策略',
      kind: 'strategy',
      status: 'success',
      status_text: summary.status_text,
      preview: pretty_json(
        {
          strategy: summary.strategy,
          enabled_count: summary.enabled_count,
          applied_count: summary.applied_count,
          builtin_enabled: summary.builtin_enabled,
          custom_enabled: summary.custom_enabled,
        },
        600
      ),
      raw: summary.raw,
    })
  }

  cards.forEach((card, idx) => {
    rows.push({
      key: card.key || `skill_${idx}`,
      name: card.name,
      kind: card.source || 'skill',
      status: card.applied ? 'applied' : (card.enabled ? 'enabled' : 'idle'),
      status_text: card.status_text,
      preview: pretty_json(
        {
          source: card.source,
          enabled: card.enabled,
          applied: card.applied,
          strategy_effect: card.strategy_effect,
          path: card.path,
          summary: card.summary,
        },
        600
      ),
      raw: card.raw,
    })
  })

  return rows
}

