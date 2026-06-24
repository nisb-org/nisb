import {
  safe_array,
  safe_object,
  safe_string,
  is_plain_object,
} from './room_shared'
import {
  normalize_tool_results,
  unwrap_tool_result,
  pick_first_tool_result,
} from './room_protocol'
import {
  normalize_room_state,
  normalize_room_items_bundle_payload,
  normalize_room_runtime_bundle_payload,
  normalize_room_runtime_replay_bundle_payload,
} from './room_normalizers'

const RUNTIME_LIST_KEYS = [
  'items',
  'events',
  'process_items',
  'processItems',
  'timeline_items',
  'timelineItems',
  'timeline',
]

const SUPERVISOR_SKILLS_EVENT_TYPES = new Set([
  'room.plan',
  'room.supervisor',
  'room.final',
])

const SUPERVISOR_MEMORY_EVENT_TYPES = new Set([
  'room.plan',
  'room.supervisor',
  'room.final',
])

const SUPERVISOR_MEMORY_TOOL_TYPES = new Set([
  'supervisor_memory_read',
  'supervisor_memory_resume',
  'supervisor_memory_write',
])

function payload_candidates(row) {
  return [
    safe_object(row),
    safe_object(row.data),
    safe_object(row.result),
    safe_object(row.payload),
    safe_object(row.value),
  ]
}

function has_runtime_list(payload) {
  return RUNTIME_LIST_KEYS.some((key) => Array.isArray(payload?.[key]))
}

function has_runtime_bundle_markers(payload) {
  const src = safe_object(payload)

  return (
    has_runtime_list(src) ||
    src.run_id !== undefined ||
    src.runId !== undefined ||
    src.latest_event_id !== undefined ||
    src.latestEventId !== undefined ||
    src.tail_event_id !== undefined ||
    src.tailEventId !== undefined ||
    src.after_event_found !== undefined ||
    src.afterEventFound !== undefined ||
    src.include_all_runs !== undefined ||
    src.includeAllRuns !== undefined ||
    src.message !== undefined ||
    src.loaded_at !== undefined ||
    src.loadedAt !== undefined
  )
}

function has_runtime_replay_bundle_markers(payload) {
  const src = safe_object(payload)

  return (
    has_runtime_list(src) ||
    Array.isArray(src?.phases) ||
    Array.isArray(src?.stage_items) ||
    Array.isArray(src?.stageItems) ||
    src.result_event !== undefined ||
    src.resultEvent !== undefined ||
    src.final_event !== undefined ||
    src.finalEvent !== undefined ||
    src.result_payload !== undefined ||
    src.resultPayload !== undefined ||
    src.final_payload !== undefined ||
    src.finalPayload !== undefined ||
    src.result_text !== undefined ||
    src.resultText !== undefined ||
    src.tail_event_id !== undefined ||
    src.tailEventId !== undefined ||
    src.latest_event_id !== undefined ||
    src.latestEventId !== undefined ||
    src.audit !== undefined ||
    src.summary !== undefined ||
    src.headline !== undefined ||
    src.badge_summary !== undefined ||
    src.badgeSummary !== undefined ||
    src.run_id !== undefined ||
    src.runId !== undefined
  )
}

function to_int(value, fallback = 0) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function compact_string_list(...values) {
  const out = []
  const seen = new Set()

  for (const value of values) {
    for (const item of safe_array(value)) {
      const token = safe_string(item).trim()
      if (!token || seen.has(token)) continue
      seen.add(token)
      out.push(token)
    }
  }

  return out
}

function get_runtime_payload(item) {
  const src = safe_object(item)
  return safe_object(
    src.payload ||
    src.data ||
    src.result ||
    src.value
  )
}

function get_runtime_type(item) {
  return safe_string(item?.type).trim()
}

function looks_like_supervisor_skills_payload(payload) {
  const src = safe_object(payload)
  if (!Object.keys(src).length) return false

  const type = safe_string(src.type).trim()
  if (type === 'supervisor_skills') return true
  if (is_plain_object(src.supervisor_skills)) return true

  return (
    src.strategy !== undefined ||
    src.supervisor_skill_strategy !== undefined ||
    src.enabled_skill_ids !== undefined ||
    src.enabledSkillIds !== undefined ||
    src.applied_skill_ids !== undefined ||
    src.appliedSkillIds !== undefined ||
    src.applied_prompt_skill_ids !== undefined ||
    src.appliedPromptSkillIds !== undefined ||
    src.step_rows !== undefined ||
    src.stepRows !== undefined ||
    src.resolved_items_count !== undefined ||
    src.resolvedItemsCount !== undefined ||
    src.prompt_block_chars !== undefined ||
    src.promptBlockChars !== undefined
  )
}

function normalize_step_row(row, index = 0) {
  const src = safe_object(row)

  const status = safe_string(
    src.status ||
    src.step_status ||
    src.stepStatus ||
    src.result ||
    src.state
  ).trim()

  const skill_id = safe_string(
    src.skill_id ||
    src.skillId ||
    src.id ||
    src.slug ||
    src.key ||
    src.name
  ).trim()

  const label = safe_string(
    src.label ||
    src.title ||
    src.name ||
    src.skill_name ||
    src.skillName ||
    skill_id
  ).trim()

  const kind = safe_string(
    src.kind ||
    src.skill_kind ||
    src.skillKind
  ).trim()

  const message = safe_string(
    src.message ||
    src.reason ||
    src.note ||
    src.detail
  ).trim()

  const path = safe_string(
    src.path ||
    src.relative_path ||
    src.relativePath
  ).trim()

  return {
    index: to_int(src.index, index + 1),
    skill_id,
    label,
    kind,
    status,
    message,
    path,
  }
}

function normalize_supervisor_skills_bundle(payload, meta = {}) {
  const src = safe_object(payload)
  const embedded = is_plain_object(src.supervisor_skills) ? safe_object(src.supervisor_skills) : null
  const base = embedded || src

  const enabled_skill_ids = compact_string_list(
    base.enabled_skill_ids,
    base.enabledSkillIds
  )

  const applied_skill_ids = compact_string_list(
    base.applied_skill_ids,
    base.appliedSkillIds
  )

  const applied_prompt_skill_ids = compact_string_list(
    base.applied_prompt_skill_ids,
    base.appliedPromptSkillIds
  )

  const step_rows = safe_array(base.step_rows || base.stepRows)
    .map((row, index) => normalize_step_row(row, index))
    .filter((row) => {
      return !!(
        row.skill_id ||
        row.label ||
        row.status ||
        row.message ||
        row.kind ||
        row.path
      )
    })

  const strategy = safe_string(
    base.strategy ||
    base.supervisor_skill_strategy ||
    base.supervisorSkillStrategy
  ).trim()

  const status = safe_string(
    base.status ||
    base.state
  ).trim()

  const message = safe_string(
    base.message ||
    base.summary ||
    base.note
  ).trim()

  const skills_root = safe_string(
    base.skills_root ||
    base.skillsRoot
  ).trim()

  const focus_root = safe_string(
    base.focus_root ||
    base.focusRoot
  ).trim()

  const resolved_items_count = to_int(
    base.resolved_items_count ??
    base.resolvedItemsCount ??
    safe_array(base.resolved_items || base.resolvedItems || base.items).length,
    0
  )

  const step_count = to_int(
    base.step_count ??
    base.stepCount ??
    step_rows.length,
    step_rows.length
  )

  const prompt_block_chars = to_int(
    base.prompt_block_chars ??
    base.promptBlockChars,
    0
  )

  const enabled_count = to_int(
    base.enabled_count ??
    base.enabledCount ??
    enabled_skill_ids.length,
    enabled_skill_ids.length
  )

  const applied_count = to_int(
    base.applied_count ??
    base.appliedCount ??
    applied_skill_ids.length,
    applied_skill_ids.length
  )

  const has_skills = !!(
    strategy ||
    status ||
    message ||
    enabled_skill_ids.length ||
    applied_skill_ids.length ||
    applied_prompt_skill_ids.length ||
    resolved_items_count > 0 ||
    step_rows.length > 0 ||
    prompt_block_chars > 0
  )

  return {
    type: 'supervisor_skills',
    has_skills,
    source_type: safe_string(meta.source_type).trim(),
    source_event_type: safe_string(meta.source_event_type).trim(),
    source_path: safe_string(meta.source_path).trim(),
    source_run_id: safe_string(meta.source_run_id).trim(),
    strategy,
    status,
    message,
    enabled_skill_ids,
    applied_skill_ids,
    applied_prompt_skill_ids,
    enabled_count,
    applied_count,
    resolved_items_count,
    step_count,
    step_rows,
    skills_root,
    focus_root,
    prompt_block_chars,
  }
}

function score_supervisor_skills_bundle(bundle) {
  const src = safe_object(bundle)
  if (!src.has_skills) return -1

  let score = 0

  if (src.source_event_type === 'room.final') score += 80
  else if (src.source_event_type === 'room.supervisor') score += 60
  else if (src.source_event_type === 'room.plan') score += 40

  if (src.source_type === 'event.payload.supervisor_skills') score += 30
  if (src.source_type === 'payload.supervisor_skills') score += 24
  if (src.source_type === 'tool_result.supervisor_skills') score += 16
  if (src.source_type === 'phase.payload.supervisor_skills') score += 14
  if (src.source_type === 'phase.tool_result.supervisor_skills') score += 12

  score += src.applied_prompt_skill_ids.length * 10
  score += src.applied_skill_ids.length * 6
  score += src.enabled_skill_ids.length * 4
  score += src.step_rows.length * 3
  score += src.resolved_items_count > 0 ? 2 : 0
  score += src.prompt_block_chars > 0 ? 2 : 0
  score += src.status ? 1 : 0
  score += src.strategy ? 1 : 0

  return score
}

function push_supervisor_skills_candidate(target, payload, meta = {}) {
  const normalized = normalize_supervisor_skills_bundle(payload, meta)
  if (!normalized.has_skills) return
  target.push(normalized)
}

function collect_supervisor_skills_from_tool_results(target, rows, meta = {}) {
  for (const row of safe_array(rows)) {
    for (const payload of payload_candidates(row)) {
      if (!looks_like_supervisor_skills_payload(payload)) continue

      const type = safe_string(payload.type).trim()
      if (type === 'supervisor_skills') {
        push_supervisor_skills_candidate(
          target,
          payload,
          {
            ...meta,
            source_type: meta.source_type || 'tool_result.supervisor_skills',
          }
        )
      } else if (is_plain_object(payload.supervisor_skills)) {
        push_supervisor_skills_candidate(
          target,
          payload.supervisor_skills,
          {
            ...meta,
            source_type: meta.source_type || 'payload.supervisor_skills',
          }
        )
      }
    }
  }
}

function collect_supervisor_skills_from_event(target, event, meta = {}) {
  const evt = safe_object(event)
  const event_type = get_runtime_type(evt)
  if (!SUPERVISOR_SKILLS_EVENT_TYPES.has(event_type)) return

  const payload = get_runtime_payload(evt)
  const run_id = safe_string(evt.run_id || payload.run_id).trim()

  if (is_plain_object(payload.supervisor_skills)) {
    push_supervisor_skills_candidate(
      target,
      payload.supervisor_skills,
      {
        ...meta,
        source_type: meta.source_type || 'event.payload.supervisor_skills',
        source_event_type: event_type,
        source_run_id: run_id,
      }
    )
  }

  collect_supervisor_skills_from_tool_results(
    target,
    payload.tool_results,
    {
      ...meta,
      source_type: meta.source_type || 'tool_result.supervisor_skills',
      source_event_type: event_type,
      source_run_id: run_id,
    }
  )
}

function collect_supervisor_skills_from_runtime_like_payload(target, payload, meta = {}) {
  const src = safe_object(payload)

  for (const key of RUNTIME_LIST_KEYS) {
    for (const item of safe_array(src[key])) {
      collect_supervisor_skills_from_event(target, item, meta)
    }
  }

  for (const phase of safe_array(src.phases)) {
    const phase_type = safe_string(phase?.type).trim()
    const phase_payload = safe_object(phase?.payload)

    if (is_plain_object(phase_payload.supervisor_skills)) {
      push_supervisor_skills_candidate(
        target,
        phase_payload.supervisor_skills,
        {
          ...meta,
          source_type: 'phase.payload.supervisor_skills',
          source_event_type: phase_type,
          source_run_id: safe_string(phase?.run_id || phase_payload?.run_id).trim(),
        }
      )
    }

    collect_supervisor_skills_from_tool_results(
      target,
      phase_payload.tool_results,
      {
        ...meta,
        source_type: 'phase.tool_result.supervisor_skills',
        source_event_type: phase_type,
        source_run_id: safe_string(phase?.run_id || phase_payload?.run_id).trim(),
      }
    )
  }

  if (is_plain_object(src.result_event)) {
    collect_supervisor_skills_from_event(target, src.result_event, meta)
  }

  if (is_plain_object(src.final_event)) {
    collect_supervisor_skills_from_event(target, src.final_event, meta)
  }

  if (is_plain_object(src.result_payload)) {
    const result_payload = safe_object(src.result_payload)

    if (is_plain_object(result_payload.supervisor_skills)) {
      push_supervisor_skills_candidate(
        target,
        result_payload.supervisor_skills,
        {
          ...meta,
          source_type: 'result_payload.supervisor_skills',
          source_event_type: 'room.final',
          source_run_id: safe_string(result_payload.run_id).trim(),
        }
      )
    }

    collect_supervisor_skills_from_tool_results(
      target,
      result_payload.tool_results,
      {
        ...meta,
        source_type: 'result_payload.tool_result.supervisor_skills',
        source_event_type: 'room.final',
        source_run_id: safe_string(result_payload.run_id).trim(),
      }
    )
  }

  if (is_plain_object(src.final_payload)) {
    const final_payload = safe_object(src.final_payload)

    if (is_plain_object(final_payload.supervisor_skills)) {
      push_supervisor_skills_candidate(
        target,
        final_payload.supervisor_skills,
        {
          ...meta,
          source_type: 'final_payload.supervisor_skills',
          source_event_type: 'room.final',
          source_run_id: safe_string(final_payload.run_id).trim(),
        }
      )
    }

    collect_supervisor_skills_from_tool_results(
      target,
      final_payload.tool_results,
      {
        ...meta,
        source_type: 'final_payload.tool_result.supervisor_skills',
        source_event_type: 'room.final',
        source_run_id: safe_string(final_payload.run_id).trim(),
      }
    )
  }
}

function looks_like_supervisor_memory_payload(payload) {
  const src = safe_object(payload)
  if (!Object.keys(src).length) return false

  const type = safe_string(src.type).trim()
  if (SUPERVISOR_MEMORY_TOOL_TYPES.has(type) || type === 'supervisor_memory') return true
  if (is_plain_object(src.supervisor_memory)) return true
  if (is_plain_object(src.supervisor_memory_read)) return true
  if (is_plain_object(src.supervisor_memory_resume)) return true
  if (is_plain_object(src.supervisor_memory_write)) return true

  return (
    src.read_status !== undefined ||
    src.read_message !== undefined ||
    src.read_reason_code !== undefined ||
    src.resume_decision !== undefined ||
    src.resume_reason !== undefined ||
    src.resume_ready !== undefined ||
    src.write_status !== undefined ||
    src.write_message !== undefined ||
    src.write_reason_code !== undefined ||
    src.relative_path !== undefined ||
    src.source_kind !== undefined ||
    src.checkpoint_stage !== undefined ||
    src.checkpoint_summary !== undefined ||
    src.recovery_hint !== undefined ||
    src.bytes_written !== undefined
  )
}

function extract_supervisor_memory_fragment(payload, kind) {
  const src = safe_object(payload)
  const embedded = is_plain_object(src.supervisor_memory) ? safe_object(src.supervisor_memory) : {}
  const type = safe_string(src.type).trim()

  if (kind === 'read') {
    if (type === 'supervisor_memory_read') return src
    if (is_plain_object(src.supervisor_memory_read)) return safe_object(src.supervisor_memory_read)
    if (is_plain_object(embedded.read)) return safe_object(embedded.read)
    if (is_plain_object(embedded.memory_read)) return safe_object(embedded.memory_read)
    if (is_plain_object(embedded.supervisor_memory_read)) return safe_object(embedded.supervisor_memory_read)
  }

  if (kind === 'resume') {
    if (type === 'supervisor_memory_resume') return src
    if (is_plain_object(src.supervisor_memory_resume)) return safe_object(src.supervisor_memory_resume)
    if (is_plain_object(embedded.resume)) return safe_object(embedded.resume)
    if (is_plain_object(embedded.memory_resume)) return safe_object(embedded.memory_resume)
    if (is_plain_object(embedded.supervisor_memory_resume)) return safe_object(embedded.supervisor_memory_resume)
  }

  if (kind === 'write') {
    if (type === 'supervisor_memory_write') return src
    if (is_plain_object(src.supervisor_memory_write)) return safe_object(src.supervisor_memory_write)
    if (is_plain_object(embedded.write)) return safe_object(embedded.write)
    if (is_plain_object(embedded.memory_write)) return safe_object(embedded.memory_write)
    if (is_plain_object(embedded.supervisor_memory_write)) return safe_object(embedded.supervisor_memory_write)
  }

  return {}
}

function merge_supervisor_memory_payload(target, payload) {
  const out = safe_object(target)
  const src = safe_object(payload)
  const type = safe_string(src.type).trim()

  if (type === 'supervisor_memory_read') out.supervisor_memory_read = src
  if (type === 'supervisor_memory_resume') out.supervisor_memory_resume = src
  if (type === 'supervisor_memory_write') out.supervisor_memory_write = src

  if (is_plain_object(src.supervisor_memory_read)) {
    out.supervisor_memory_read = safe_object(src.supervisor_memory_read)
  }
  if (is_plain_object(src.supervisor_memory_resume)) {
    out.supervisor_memory_resume = safe_object(src.supervisor_memory_resume)
  }
  if (is_plain_object(src.supervisor_memory_write)) {
    out.supervisor_memory_write = safe_object(src.supervisor_memory_write)
  }

  const embedded = is_plain_object(src.supervisor_memory) ? safe_object(src.supervisor_memory) : {}

  if (is_plain_object(embedded.read)) out.supervisor_memory_read = safe_object(embedded.read)
  if (is_plain_object(embedded.memory_read)) out.supervisor_memory_read = safe_object(embedded.memory_read)
  if (is_plain_object(embedded.supervisor_memory_read)) {
    out.supervisor_memory_read = safe_object(embedded.supervisor_memory_read)
  }

  if (is_plain_object(embedded.resume)) out.supervisor_memory_resume = safe_object(embedded.resume)
  if (is_plain_object(embedded.memory_resume)) out.supervisor_memory_resume = safe_object(embedded.memory_resume)
  if (is_plain_object(embedded.supervisor_memory_resume)) {
    out.supervisor_memory_resume = safe_object(embedded.supervisor_memory_resume)
  }

  if (is_plain_object(embedded.write)) out.supervisor_memory_write = safe_object(embedded.write)
  if (is_plain_object(embedded.memory_write)) out.supervisor_memory_write = safe_object(embedded.memory_write)
  if (is_plain_object(embedded.supervisor_memory_write)) {
    out.supervisor_memory_write = safe_object(embedded.supervisor_memory_write)
  }

  return out
}

function normalize_supervisor_memory_bundle(payload, meta = {}) {
  const src = safe_object(payload)
  const read = extract_supervisor_memory_fragment(src, 'read')
  const resume = extract_supervisor_memory_fragment(src, 'resume')
  const write = extract_supervisor_memory_fragment(src, 'write')
  const checkpoint = safe_object(read.checkpoint)
  const resume_from_read = safe_object(read.resume)

  const read_status = safe_string(
    read.status ||
    read.read_status ||
    src.read_status
  ).trim()

  const read_message = safe_string(
    read.message ||
    read.read_message ||
    src.read_message
  ).trim()

  const read_reason_code = safe_string(
    read.reason_code ||
    read.read_reason_code ||
    src.read_reason_code
  ).trim()

  const resume_decision = safe_string(
    resume.decision ||
    resume.resume_decision ||
    src.resume_decision
  ).trim()

  const resume_reason = safe_string(
    resume.reason ||
    resume.resume_reason ||
    src.resume_reason
  ).trim()

  const resume_ready = Boolean(
    resume.resume_ready ??
    resume_from_read.resume_ready ??
    src.resume_ready
  )

  const checkpoint_stage = safe_string(
    write.checkpoint_stage ||
    resume.checkpoint_stage ||
    checkpoint.stage ||
    src.checkpoint_stage
  ).trim()

  const checkpoint_summary = safe_string(
    write.checkpoint_summary ||
    resume.checkpoint_summary ||
    checkpoint.summary ||
    src.checkpoint_summary
  ).trim()

  const recovery_hint = safe_string(
    resume.recovery_hint ||
    checkpoint.recovery_hint ||
    src.recovery_hint
  ).trim()

  const write_status = safe_string(
    write.status ||
    write.write_status ||
    src.write_status
  ).trim()

  const write_message = safe_string(
    write.message ||
    write.write_message ||
    src.write_message
  ).trim()

  const write_reason_code = safe_string(
    write.reason_code ||
    write.write_reason_code ||
    src.write_reason_code
  ).trim()

  const relative_path = safe_string(
    write.relative_path ||
    resume.relative_path ||
    read.relative_path ||
    src.relative_path
  ).trim()

  const source_kind = safe_string(
    write.source_kind ||
    read.source_kind ||
    src.source_kind
  ).trim()

  const bytes_written = to_int(
    write.bytes_written ?? src.bytes_written,
    0
  )

  const has_memory = !!(
    Object.keys(read).length ||
    Object.keys(resume).length ||
    Object.keys(write).length ||
    read_status ||
    resume_decision ||
    resume_reason ||
    write_status ||
    relative_path ||
    checkpoint_stage ||
    checkpoint_summary ||
    recovery_hint ||
    bytes_written > 0
  )

  return {
    type: 'supervisor_memory',
    has_memory,
    source_type: safe_string(meta.source_type).trim(),
    source_event_type: safe_string(meta.source_event_type).trim(),
    source_path: safe_string(meta.source_path).trim(),
    source_run_id: safe_string(meta.source_run_id).trim(),

    read_status,
    read_message,
    read_reason_code,

    resume_decision,
    resume_reason,
    resume_ready,

    checkpoint_stage,
    checkpoint_summary,
    recovery_hint,

    write_status,
    write_message,
    write_reason_code,

    relative_path,
    source_kind,
    bytes_written,
  }
}

function score_supervisor_memory_bundle(bundle) {
  const src = safe_object(bundle)
  if (!src.has_memory) return -1

  let score = 0

  if (src.source_event_type === 'room.final') score += 80
  else if (src.source_event_type === 'room.supervisor') score += 60
  else if (src.source_event_type === 'room.plan') score += 40

  if (src.source_type === 'event.payload.supervisor_memory') score += 30
  if (src.source_type === 'payload.supervisor_memory') score += 24
  if (src.source_type === 'tool_result.supervisor_memory') score += 18
  if (src.source_type === 'phase.payload.supervisor_memory') score += 14
  if (src.source_type === 'phase.tool_result.supervisor_memory') score += 12
  if (src.source_type === 'result_payload.supervisor_memory') score += 10
  if (src.source_type === 'final_payload.supervisor_memory') score += 10

  score += src.write_status ? 12 : 0
  score += src.resume_decision ? 10 : 0
  score += src.read_status ? 8 : 0
  score += src.checkpoint_stage ? 6 : 0
  score += src.relative_path ? 4 : 0
  score += src.bytes_written > 0 ? 3 : 0
  score += src.resume_reason ? 2 : 0
  score += src.checkpoint_summary ? 1 : 0

  return score
}

function push_supervisor_memory_candidate(target, payload, meta = {}) {
  const normalized = normalize_supervisor_memory_bundle(payload, meta)
  if (!normalized.has_memory) return
  target.push(normalized)
}

function collect_supervisor_memory_from_tool_results(target, rows, meta = {}) {
  const merged = {}

  for (const row of safe_array(rows)) {
    for (const payload of payload_candidates(row)) {
      merge_supervisor_memory_payload(merged, payload)
    }
  }

  if (looks_like_supervisor_memory_payload(merged)) {
    push_supervisor_memory_candidate(
      target,
      merged,
      {
        ...meta,
        source_type: meta.source_type || 'tool_result.supervisor_memory',
      }
    )
  }
}

function collect_supervisor_memory_from_event(target, event, meta = {}) {
  const evt = safe_object(event)
  const event_type = get_runtime_type(evt)
  if (!SUPERVISOR_MEMORY_EVENT_TYPES.has(event_type)) return

  const payload = get_runtime_payload(evt)
  const run_id = safe_string(evt.run_id || payload.run_id).trim()

  if (looks_like_supervisor_memory_payload(payload)) {
    push_supervisor_memory_candidate(
      target,
      payload,
      {
        ...meta,
        source_type: meta.source_type || 'event.payload.supervisor_memory',
        source_event_type: event_type,
        source_run_id: run_id,
      }
    )
  }

  collect_supervisor_memory_from_tool_results(
    target,
    payload.tool_results,
    {
      ...meta,
      source_type: meta.source_type || 'tool_result.supervisor_memory',
      source_event_type: event_type,
      source_run_id: run_id,
    }
  )
}

function collect_supervisor_memory_from_runtime_like_payload(target, payload, meta = {}) {
  const src = safe_object(payload)

  for (const key of RUNTIME_LIST_KEYS) {
    for (const item of safe_array(src[key])) {
      collect_supervisor_memory_from_event(target, item, meta)
    }
  }

  for (const phase of safe_array(src.phases)) {
    const phase_type = safe_string(phase?.type).trim()
    const phase_payload = safe_object(phase?.payload)

    if (looks_like_supervisor_memory_payload(phase_payload)) {
      push_supervisor_memory_candidate(
        target,
        phase_payload,
        {
          ...meta,
          source_type: 'phase.payload.supervisor_memory',
          source_event_type: phase_type,
          source_run_id: safe_string(phase?.run_id || phase_payload?.run_id).trim(),
        }
      )
    }

    collect_supervisor_memory_from_tool_results(
      target,
      phase_payload.tool_results,
      {
        ...meta,
        source_type: 'phase.tool_result.supervisor_memory',
        source_event_type: phase_type,
        source_run_id: safe_string(phase?.run_id || phase_payload?.run_id).trim(),
      }
    )
  }

  if (is_plain_object(src.result_event)) {
    collect_supervisor_memory_from_event(target, src.result_event, meta)
  }

  if (is_plain_object(src.final_event)) {
    collect_supervisor_memory_from_event(target, src.final_event, meta)
  }

  if (is_plain_object(src.result_payload)) {
    const result_payload = safe_object(src.result_payload)

    if (looks_like_supervisor_memory_payload(result_payload)) {
      push_supervisor_memory_candidate(
        target,
        result_payload,
        {
          ...meta,
          source_type: 'result_payload.supervisor_memory',
          source_event_type: 'room.final',
          source_run_id: safe_string(result_payload.run_id).trim(),
        }
      )
    }

    collect_supervisor_memory_from_tool_results(
      target,
      result_payload.tool_results,
      {
        ...meta,
        source_type: 'result_payload.tool_result.supervisor_memory',
        source_event_type: 'room.final',
        source_run_id: safe_string(result_payload.run_id).trim(),
      }
    )
  }

  if (is_plain_object(src.final_payload)) {
    const final_payload = safe_object(src.final_payload)

    if (looks_like_supervisor_memory_payload(final_payload)) {
      push_supervisor_memory_candidate(
        target,
        final_payload,
        {
          ...meta,
          source_type: 'final_payload.supervisor_memory',
          source_event_type: 'room.final',
          source_run_id: safe_string(final_payload.run_id).trim(),
        }
      )
    }

    collect_supervisor_memory_from_tool_results(
      target,
      final_payload.tool_results,
      {
        ...meta,
        source_type: 'final_payload.tool_result.supervisor_memory',
        source_event_type: 'room.final',
        source_run_id: safe_string(final_payload.run_id).trim(),
      }
    )
  }
}

export function extract_room_items_bundle(data) {
  const rows = normalize_tool_results(data)

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (safe_string(payload.type).trim() === 'room_items' && Array.isArray(payload.items)) {
        return normalize_room_items_bundle_payload(payload)
      }
    }
  }

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (Array.isArray(payload.items)) {
        return normalize_room_items_bundle_payload(payload)
      }
    }
  }

  const top = unwrap_tool_result(data)
  if (Array.isArray(top.items)) {
    return normalize_room_items_bundle_payload(top)
  }

  return normalize_room_items_bundle_payload({})
}

export function extract_room_items(data) {
  return extract_room_items_bundle(data).items
}

export function extract_room_info(data) {
  const row = pick_first_tool_result(
    data,
    (x) =>
      is_plain_object(x.room) ||
      is_plain_object(x.data?.room) ||
      is_plain_object(x.result?.room) ||
      is_plain_object(x.payload?.room) ||
      is_plain_object(x.value?.room) ||
      Array.isArray(x.roles) ||
      Array.isArray(x.data?.roles) ||
      Array.isArray(x.result?.roles) ||
      Array.isArray(x.payload?.roles) ||
      Array.isArray(x.value?.roles) ||
      is_plain_object(x.state) ||
      is_plain_object(x.data?.state) ||
      is_plain_object(x.result?.state) ||
      is_plain_object(x.payload?.state) ||
      is_plain_object(x.value?.state)
  )

  if (row) {
    for (const payload of payload_candidates(row)) {
      const has_room = is_plain_object(payload.room)
      const has_roles = Array.isArray(payload.roles)
      const has_state = is_plain_object(payload.state)

      if (has_room || has_roles || has_state) {
        return {
          room: has_room ? payload.room : null,
          roles: safe_array(payload.roles),
          state: normalize_room_state(payload.state),
        }
      }
    }
  }

  const top = unwrap_tool_result(data)
  return {
    room: is_plain_object(top.room) ? top.room : null,
    roles: safe_array(top.roles),
    state: normalize_room_state(top.state),
  }
}

export function extract_whoami(data) {
  const row = pick_first_tool_result(
    data,
    (x) =>
      !!safe_string(x.uid || x.user_id).trim() ||
      !!safe_string(x.data?.uid || x.data?.user_id).trim() ||
      !!safe_string(x.result?.uid || x.result?.user_id).trim() ||
      !!safe_string(x.payload?.uid || x.payload?.user_id).trim() ||
      !!safe_string(x.value?.uid || x.value?.user_id).trim()
  )

  if (row) {
    for (const payload of payload_candidates(row)) {
      const uid = safe_string(payload.uid || payload.user_id).trim()
      const basepath = safe_string(payload.basepath || payload.base_path).trim()
      if (uid || basepath) {
        return { uid, basepath }
      }
    }
  }

  const top = unwrap_tool_result(data)
  return {
    uid: safe_string(top.uid || top.user_id).trim(),
    basepath: safe_string(top.basepath || top.base_path).trim(),
  }
}

export function extract_room_runtime_bundle(data) {
  const rows = normalize_tool_results(data)
  const runtimeTypes = new Set([
    'room_runtime_events',
    'room_events_recent',
    'room_runtime',
  ])

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      const type = safe_string(payload.type).trim()
      if (runtimeTypes.has(type) && has_runtime_bundle_markers(payload)) {
        return normalize_room_runtime_bundle_payload(payload)
      }
    }
  }

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (has_runtime_bundle_markers(payload)) {
        return normalize_room_runtime_bundle_payload(payload)
      }
    }
  }

  const top = unwrap_tool_result(data)
  if (has_runtime_bundle_markers(top)) {
    return normalize_room_runtime_bundle_payload(top)
  }

  return normalize_room_runtime_bundle_payload({})
}

export function extract_room_runtime_replay_bundle(data) {
  const rows = normalize_tool_results(data)

  const replayTypes = new Set([
    'room_runtime_replay',
    'room_runtime_events_replay',
    'room_replay',
    'room_events_replay',
  ])

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      const type = safe_string(payload.type).trim()
      if (replayTypes.has(type) && has_runtime_replay_bundle_markers(payload)) {
        return normalize_room_runtime_replay_bundle_payload(payload)
      }
    }
  }

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (has_runtime_replay_bundle_markers(payload)) {
        return normalize_room_runtime_replay_bundle_payload(payload)
      }
    }
  }

  const top = unwrap_tool_result(data)
  if (has_runtime_replay_bundle_markers(top)) {
    return normalize_room_runtime_replay_bundle_payload(top)
  }

  return normalize_room_runtime_replay_bundle_payload({})
}

export function extract_room_supervisor_skills_candidates(data) {
  const candidates = []
  const rows = normalize_tool_results(data)

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (is_plain_object(payload.supervisor_skills)) {
        push_supervisor_skills_candidate(
          candidates,
          payload.supervisor_skills,
          {
            source_type: 'payload.supervisor_skills',
            source_path: 'payload.supervisor_skills',
          }
        )
      }

      collect_supervisor_skills_from_tool_results(
        candidates,
        payload.tool_results,
        {
          source_type: 'tool_result.supervisor_skills',
          source_path: 'payload.tool_results',
        }
      )

      if (has_runtime_bundle_markers(payload) || has_runtime_replay_bundle_markers(payload)) {
        collect_supervisor_skills_from_runtime_like_payload(
          candidates,
          payload,
          {
            source_path: 'runtime_like_payload',
          }
        )
      }

      if (looks_like_supervisor_skills_payload(payload)) {
        const type = safe_string(payload.type).trim()
        if (type === 'supervisor_skills') {
          push_supervisor_skills_candidate(
            candidates,
            payload,
            {
              source_type: 'tool_result.supervisor_skills',
              source_path: 'payload',
            }
          )
        }
      }
    }
  }

  const top = unwrap_tool_result(data)

  if (is_plain_object(top.supervisor_skills)) {
    push_supervisor_skills_candidate(
      candidates,
      top.supervisor_skills,
      {
        source_type: 'payload.supervisor_skills',
        source_path: 'top.supervisor_skills',
      }
    )
  }

  collect_supervisor_skills_from_tool_results(
    candidates,
    top.tool_results,
    {
      source_type: 'tool_result.supervisor_skills',
      source_path: 'top.tool_results',
    }
  )

  if (has_runtime_bundle_markers(top) || has_runtime_replay_bundle_markers(top)) {
    collect_supervisor_skills_from_runtime_like_payload(
      candidates,
      top,
      {
        source_path: 'top.runtime_like_payload',
      }
    )
  }

  const ordered = [...candidates].sort((a, b) => score_supervisor_skills_bundle(b) - score_supervisor_skills_bundle(a))
  const deduped = []
  const seen = new Set()

  for (const item of ordered) {
    const key = JSON.stringify({
      source_type: item.source_type,
      source_event_type: item.source_event_type,
      source_run_id: item.source_run_id,
      strategy: item.strategy,
      status: item.status,
      enabled_skill_ids: item.enabled_skill_ids,
      applied_skill_ids: item.applied_skill_ids,
      applied_prompt_skill_ids: item.applied_prompt_skill_ids,
      step_rows: item.step_rows,
      resolved_items_count: item.resolved_items_count,
      prompt_block_chars: item.prompt_block_chars,
    })
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
  }

  return deduped
}

export function extract_room_supervisor_skills_bundle(data) {
  const candidates = extract_room_supervisor_skills_candidates(data)
  if (candidates.length > 0) return candidates[0]

  return normalize_supervisor_skills_bundle({}, {
    source_type: '',
    source_event_type: '',
    source_path: '',
    source_run_id: '',
  })
}

export function extract_room_supervisor_memory_candidates(data) {
  const candidates = []
  const rows = normalize_tool_results(data)

  for (const row of rows) {
    for (const payload of payload_candidates(row)) {
      if (looks_like_supervisor_memory_payload(payload)) {
        push_supervisor_memory_candidate(
          candidates,
          payload,
          {
            source_type: 'payload.supervisor_memory',
            source_path: 'payload',
          }
        )
      }

      collect_supervisor_memory_from_tool_results(
        candidates,
        payload.tool_results,
        {
          source_type: 'tool_result.supervisor_memory',
          source_path: 'payload.tool_results',
        }
      )

      if (has_runtime_bundle_markers(payload) || has_runtime_replay_bundle_markers(payload)) {
        collect_supervisor_memory_from_runtime_like_payload(
          candidates,
          payload,
          {
            source_path: 'runtime_like_payload',
          }
        )
      }
    }
  }

  const top = unwrap_tool_result(data)

  if (looks_like_supervisor_memory_payload(top)) {
    push_supervisor_memory_candidate(
      candidates,
      top,
      {
        source_type: 'payload.supervisor_memory',
        source_path: 'top',
      }
    )
  }

  collect_supervisor_memory_from_tool_results(
    candidates,
    top.tool_results,
    {
      source_type: 'tool_result.supervisor_memory',
      source_path: 'top.tool_results',
    }
  )

  if (has_runtime_bundle_markers(top) || has_runtime_replay_bundle_markers(top)) {
    collect_supervisor_memory_from_runtime_like_payload(
      candidates,
      top,
      {
        source_path: 'top.runtime_like_payload',
      }
    )
  }

  const ordered = [...candidates].sort((a, b) => score_supervisor_memory_bundle(b) - score_supervisor_memory_bundle(a))
  const deduped = []
  const seen = new Set()

  for (const item of ordered) {
    const key = JSON.stringify({
      source_type: item.source_type,
      source_event_type: item.source_event_type,
      source_run_id: item.source_run_id,
      read_status: item.read_status,
      read_message: item.read_message,
      read_reason_code: item.read_reason_code,
      resume_decision: item.resume_decision,
      resume_reason: item.resume_reason,
      resume_ready: item.resume_ready,
      checkpoint_stage: item.checkpoint_stage,
      checkpoint_summary: item.checkpoint_summary,
      recovery_hint: item.recovery_hint,
      write_status: item.write_status,
      write_message: item.write_message,
      write_reason_code: item.write_reason_code,
      relative_path: item.relative_path,
      source_kind: item.source_kind,
      bytes_written: item.bytes_written,
    })
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
  }

  return deduped
}

export function extract_room_supervisor_memory_bundle(data) {
  const candidates = extract_room_supervisor_memory_candidates(data)
  if (candidates.length > 0) return candidates[0]

  return normalize_supervisor_memory_bundle({}, {
    source_type: '',
    source_event_type: '',
    source_path: '',
    source_run_id: '',
  })
}
