import {
  safe_array,
  safe_object,
  safe_string,
} from './room_shared'
import {
  derive_reply_mode_from_state,
  normalize_room_mcp_overrides,
  normalize_runtime_state,
  normalize_room_items_cursor,
  normalize_room_runtime_replay_bundle_payload,
} from './room_normalizers'
import {
  sort_runtime_events,
  get_runtime_process_items_from_list,
  get_runtime_result_event_from_list,
} from './room_event_helpers'
import {
  DEFAULT_ITEMS_PAGING,
} from './room_state'
import {
  extract_room_supervisor_skills_bundle,
  extract_room_supervisor_memory_bundle,
} from './room_extractors'


function get_runtime_payload(item) {
  const src = safe_object(item)
  return safe_object(
    src.payload ||
    src.data ||
    src.result ||
    src.value
  )
}


function get_runtime_run_id(item) {
  const src = safe_object(item)
  const payload = get_runtime_payload(src)
  return safe_string(src.run_id || payload.run_id).trim()
}


function get_runtime_ts(item) {
  const src = safe_object(item)
  return safe_string(src.ts).trim()
}


function is_runtime_terminal_event(item) {
  const type = safe_string(item?.type).trim()
  return type === 'room.final' || type === 'room.abort' || type === 'room.aborted' || type === 'room.error'
}


function normalize_runtime_status(value) {
  return safe_string(value).trim().toLowerCase()
}


function is_runtime_terminal_status(value) {
  const token = normalize_runtime_status(value)
  if (!token) return false


  return [
    'completed',
    'complete',
    'done',
    'finished',
    'failed',
    'error',
    'aborted',
    'abort',
    'cancelled',
    'canceled',
    'terminated',
    'timed_out',
    'timed out',
    'success',
    'successful',
    '已完成',
    '已结束',
    '完成',
    '失败',
    '错误',
    '已中止',
    '中止',
    '已取消',
    '取消',
  ].some((item) => token.includes(item))
}


function terminal_label_from_status(value) {
  const token = normalize_runtime_status(value)
  if (!token) return ''


  if (token.includes('error') || token.includes('failed') || token.includes('失败') || token.includes('错误')) {
    return '运行失败'
  }


  if (
    token.includes('aborted') ||
    token.includes('abort') ||
    token.includes('cancelled') ||
    token.includes('canceled') ||
    token.includes('terminated') ||
    token.includes('已中止') ||
    token.includes('中止') ||
    token.includes('已取消') ||
    token.includes('取消')
  ) {
    return '已中止'
  }


  if (
    token.includes('completed') ||
    token.includes('complete') ||
    token.includes('done') ||
    token.includes('finished') ||
    token.includes('success') ||
    token.includes('已完成') ||
    token.includes('已结束') ||
    token.includes('完成')
  ) {
    return '已完成'
  }


  return ''
}


function terminal_label_from_event(item) {
  const type = safe_string(item?.type).trim()
  if (type === 'room.final') return '已完成'
  if (type === 'room.error') return '运行失败'
  if (type === 'room.abort' || type === 'room.aborted') return '已中止'
  return ''
}


function build_runtime_run_options_from_lists(lists = [], currentRunId = '', currentRunStatus = '') {
  const map = new Map()
  const current_status = safe_string(currentRunStatus).trim()


  for (const list of lists) {
    for (const item of sort_runtime_events(list)) {
      const run_id = get_runtime_run_id(item)
      if (!run_id) continue


      const prev = map.get(run_id) || {
        run_id,
        label: run_id,
        last_ts: '',
        completed: false,
        has_final: false,
        is_current: false,
        source: 'runtime',
      }


      const next_ts = get_runtime_ts(item)
      const type = safe_string(item?.type).trim()


      map.set(run_id, {
        ...prev,
        last_ts: next_ts || prev.last_ts,
        completed: prev.completed || is_runtime_terminal_event(item),
        has_final: prev.has_final || type === 'room.final',
        is_current: prev.is_current || run_id === currentRunId,
      })
    }
  }


  const explicit_current = safe_string(currentRunId).trim()
  if (explicit_current && !map.has(explicit_current)) {
    map.set(explicit_current, {
      run_id: explicit_current,
      label: explicit_current,
      last_ts: '',
      completed: is_runtime_terminal_status(current_status),
      has_final: false,
      is_current: true,
      source: 'room_state',
    })
  }


  return Array.from(map.values()).sort((a, b) => {
    const ta = safe_string(a.last_ts).trim()
    const tb = safe_string(b.last_ts).trim()
    if (ta && tb && ta !== tb) return ta > tb ? -1 : 1
    if (a.completed !== b.completed) return a.completed ? -1 : 1
    return safe_string(a.run_id).trim() < safe_string(b.run_id).trim() ? 1 : -1
  })
}


function current_runtime_target_run_id(state) {
  return safe_string(
    state.roomState?.current_run_id ||
    state.runtime?.run_id
  ).trim()
}


function current_runtime_has_target(state) {
  return !!current_runtime_target_run_id(state)
}


function filter_runtime_items_for_run(list, runId = '') {
  const rows = sort_runtime_events(list)
  const target_run_id = safe_string(runId).trim()


  if (!target_run_id) return rows


  return rows.filter((item) => {
    const item_run_id = get_runtime_run_id(item)
    return item_run_id && item_run_id === target_run_id
  })
}


function current_runtime_event_items(state) {
  const target_run_id = current_runtime_target_run_id(state)


  const runtime_items = filter_runtime_items_for_run(state.runtime?.items, target_run_id)
  if (runtime_items.length > 0) return runtime_items


  const item_fallback = filter_runtime_items_for_run(state.items, target_run_id)
  if (item_fallback.length > 0) return item_fallback


  if (target_run_id) return []


  const raw_runtime_items = sort_runtime_events(state.runtime?.items)
  if (raw_runtime_items.length > 0) return raw_runtime_items


  return sort_runtime_events(state.items)
}


function current_runtime_process_items(state) {
  return get_runtime_process_items_from_list(current_runtime_event_items(state))
}


function current_runtime_result_event(state) {
  return get_runtime_result_event_from_list(current_runtime_event_items(state))
}


function current_runtime_terminal_evidence(state) {
  const explicit_status = safe_string(state.roomState?.current_run_status).trim()
  if (is_runtime_terminal_status(explicit_status)) {
    return {
      terminal: true,
      label: terminal_label_from_status(explicit_status) || '已完成',
    }
  }


  const result_event = current_runtime_result_event(state)
  if (result_event && is_runtime_terminal_event(result_event)) {
    return {
      terminal: true,
      label: terminal_label_from_event(result_event) || '已完成',
    }
  }


  const process_items = current_runtime_process_items(state)
  for (let idx = process_items.length - 1; idx >= 0; idx -= 1) {
    const item = process_items[idx]
    if (!is_runtime_terminal_event(item)) continue
    return {
      terminal: true,
      label: terminal_label_from_event(item) || '已完成',
    }
  }


  return {
    terminal: false,
    label: '',
  }
}


function current_runtime_is_live(state) {
  const terminal = current_runtime_terminal_evidence(state)
  if (terminal.terminal) return false


  const status = safe_string(state.roomState?.current_run_status).trim().toLowerCase()
  if (status === 'running') return true


  if (current_runtime_has_target(state)) return true
  if (current_runtime_process_items(state).length > 0) return true


  return !!state.runtime?.live_hint
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


function normalize_supervisor_skill_step_row(row, index = 0) {
  const src = safe_object(row)

  return {
    index: to_int(src.index, index + 1),
    skill_id: safe_string(
      src.skill_id ||
      src.skillId ||
      src.id ||
      src.slug ||
      src.key ||
      src.name
    ).trim(),
    label: safe_string(
      src.label ||
      src.title ||
      src.name ||
      src.skill_name ||
      src.skillName
    ).trim(),
    kind: safe_string(
      src.kind ||
      src.skill_kind ||
      src.skillKind
    ).trim(),
    status: safe_string(
      src.status ||
      src.step_status ||
      src.stepStatus ||
      src.result ||
      src.state
    ).trim(),
    message: safe_string(
      src.message ||
      src.reason ||
      src.note ||
      src.detail
    ).trim(),
    path: safe_string(
      src.path ||
      src.relative_path ||
      src.relativePath
    ).trim(),
  }
}


function build_supervisor_skills_state_fallback(state) {
  const room_state = safe_object(state?.roomState)

  const strategy = safe_string(
    room_state.supervisor_skill_strategy ||
    room_state.supervisorSkillsStrategy
  ).trim()

  const enabled_skill_ids = compact_string_list(
    room_state.enabled_supervisor_skill_ids,
    room_state.enabled_skill_ids,
    room_state.enabledSkillIds
  )

  const applied_skill_ids = compact_string_list(
    room_state.applied_supervisor_skill_ids,
    room_state.applied_skill_ids,
    room_state.appliedSkillIds
  )

  const applied_prompt_skill_ids = compact_string_list(
    room_state.applied_prompt_supervisor_skill_ids,
    room_state.applied_prompt_skill_ids,
    room_state.appliedPromptSkillIds
  )

  const has_state_hint = !!(
    strategy ||
    enabled_skill_ids.length ||
    applied_skill_ids.length ||
    applied_prompt_skill_ids.length
  )

  return {
    type: 'supervisor_skills',
    has_skills: has_state_hint,
    has_state_hint,
    source_type: has_state_hint ? 'room_state' : '',
    source_event_type: '',
    source_path: has_state_hint ? 'roomState' : '',
    source_run_id: safe_string(room_state.current_run_id).trim(),
    strategy,
    status: has_state_hint ? 'state_hint' : '',
    message: '',
    enabled_skill_ids,
    applied_skill_ids,
    applied_prompt_skill_ids,
    enabled_count: enabled_skill_ids.length,
    applied_count: applied_skill_ids.length,
    resolved_items_count: 0,
    step_count: 0,
    step_rows: [],
    skills_root: safe_string(room_state.skills_root).trim(),
    focus_root: safe_string(
      room_state.focus_root ||
      room_state.last_supervisor_fs_read_focus_root
    ).trim(),
    prompt_block_chars: 0,
  }
}


function normalize_supervisor_skills_view(bundle, fallback = {}) {
  const src = safe_object(bundle)
  const fb = safe_object(fallback)

  const strategy = safe_string(src.strategy || fb.strategy).trim()
  const status = safe_string(src.status || fb.status).trim()
  const message = safe_string(src.message || fb.message).trim()

  const enabled_skill_ids = compact_string_list(
    src.enabled_skill_ids,
    fb.enabled_skill_ids
  )

  const applied_skill_ids = compact_string_list(
    src.applied_skill_ids,
    fb.applied_skill_ids
  )

  const applied_prompt_skill_ids = compact_string_list(
    src.applied_prompt_skill_ids,
    fb.applied_prompt_skill_ids
  )

  const raw_step_rows = safe_array(
    safe_array(src.step_rows).length ? src.step_rows : fb.step_rows
  )

  const step_rows = raw_step_rows
    .map((row, index) => normalize_supervisor_skill_step_row(row, index))
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

  const enabled_count = to_int(
    src.enabled_count,
    enabled_skill_ids.length
  )

  const applied_count = to_int(
    src.applied_count,
    applied_skill_ids.length
  )

  const resolved_items_count = to_int(
    src.resolved_items_count,
    to_int(fb.resolved_items_count, 0)
  )

  const step_count = to_int(
    src.step_count,
    step_rows.length
  )

  const prompt_block_chars = to_int(
    src.prompt_block_chars,
    to_int(fb.prompt_block_chars, 0)
  )

  const source_type = safe_string(src.source_type || fb.source_type).trim()
  const source_event_type = safe_string(src.source_event_type || fb.source_event_type).trim()
  const source_path = safe_string(src.source_path || fb.source_path).trim()
  const source_run_id = safe_string(src.source_run_id || fb.source_run_id).trim()
  const skills_root = safe_string(src.skills_root || fb.skills_root).trim()
  const focus_root = safe_string(src.focus_root || fb.focus_root).trim()

  const has_available_not_enabled = step_rows.some((row) => row.status === 'available_not_enabled')
  const has_applied_prompt = applied_prompt_skill_ids.length > 0 || step_rows.some((row) => row.status === 'applied_prompt')
  const has_missing = step_rows.some((row) => row.status === 'missing')
  const has_skipped = step_rows.some((row) => row.status === 'skipped')
  const has_custom = strategy === 'custom_only' || strategy === 'builtin_plus_custom'

  const has_skills = !!(
    src.has_skills ||
    fb.has_skills ||
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

  const summary_bits = []
  if (strategy) summary_bits.push(strategy)
  if (enabled_count > 0 || applied_count > 0) {
    summary_bits.push(`enabled ${enabled_count}`)
    summary_bits.push(`applied ${applied_count}`)
  }
  if (has_available_not_enabled) summary_bits.push('available_not_enabled')
  else if (has_applied_prompt) summary_bits.push('applied_prompt')
  else if (has_missing) summary_bits.push('missing')

  return {
    type: 'supervisor_skills',
    has_skills,
    has_state_hint: !!fb.has_state_hint,
    source_type,
    source_event_type,
    source_path,
    source_run_id,
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
    has_custom,
    has_applied_prompt,
    has_available_not_enabled,
    has_missing,
    has_skipped,
    summary_text: summary_bits.join(' · ').trim(),
  }
}


function build_supervisor_memory_state_fallback(state) {
  const room_state = safe_object(state?.roomState)

  const read_status = safe_string(
    room_state.last_supervisor_memory_read_status ||
    room_state.supervisor_memory_read_status
  ).trim()

  const read_message = safe_string(
    room_state.last_supervisor_memory_read_message ||
    room_state.supervisor_memory_read_message
  ).trim()

  const read_reason_code = safe_string(
    room_state.last_supervisor_memory_read_reason_code ||
    room_state.supervisor_memory_read_reason_code
  ).trim()

  const resume_decision = safe_string(
    room_state.last_supervisor_memory_resume_decision ||
    room_state.supervisor_memory_resume_decision
  ).trim()

  const resume_reason = safe_string(
    room_state.last_supervisor_memory_resume_reason ||
    room_state.supervisor_memory_resume_reason
  ).trim()

  const resume_ready = !!(
    room_state.last_supervisor_memory_resume_ready ||
    room_state.supervisor_memory_resume_ready
  )

  const checkpoint_stage = safe_string(
    room_state.last_supervisor_memory_write_checkpoint_stage ||
    room_state.last_supervisor_memory_resume_checkpoint_stage ||
    room_state.last_supervisor_memory_checkpoint_stage ||
    room_state.supervisor_memory_checkpoint_stage
  ).trim()

  const checkpoint_summary = safe_string(
    room_state.last_supervisor_memory_write_checkpoint_summary ||
    room_state.last_supervisor_memory_resume_checkpoint_summary ||
    room_state.last_supervisor_memory_checkpoint_summary ||
    room_state.supervisor_memory_checkpoint_summary
  ).trim()

  const recovery_hint = safe_string(
    room_state.last_supervisor_memory_resume_recovery_hint ||
    room_state.last_supervisor_memory_recovery_hint ||
    room_state.supervisor_memory_recovery_hint
  ).trim()

  const write_status = safe_string(
    room_state.last_supervisor_memory_write_status ||
    room_state.supervisor_memory_write_status
  ).trim()

  const write_message = safe_string(
    room_state.last_supervisor_memory_write_message ||
    room_state.supervisor_memory_write_message
  ).trim()

  const write_reason_code = safe_string(
    room_state.last_supervisor_memory_write_reason_code ||
    room_state.supervisor_memory_write_reason_code
  ).trim()

  const relative_path = safe_string(
    room_state.last_supervisor_memory_write_relative_path ||
    room_state.last_supervisor_memory_resume_relative_path ||
    room_state.last_supervisor_memory_read_relative_path ||
    room_state.last_supervisor_memory_relative_path ||
    room_state.supervisor_memory_relative_path
  ).trim()

  const source_kind = safe_string(
    room_state.last_supervisor_memory_write_source_kind ||
    room_state.last_supervisor_memory_read_source_kind ||
    room_state.last_supervisor_memory_source_kind ||
    room_state.supervisor_memory_source_kind
  ).trim()

  const bytes_written = to_int(
    room_state.last_supervisor_memory_write_bytes_written ||
    room_state.supervisor_memory_write_bytes_written,
    0
  )

  const has_state_hint = !!(
    read_status ||
    read_message ||
    read_reason_code ||
    resume_decision ||
    resume_reason ||
    resume_ready ||
    checkpoint_stage ||
    checkpoint_summary ||
    recovery_hint ||
    write_status ||
    write_message ||
    write_reason_code ||
    relative_path ||
    source_kind ||
    bytes_written > 0
  )

  return {
    type: 'supervisor_memory',
    has_memory: has_state_hint,
    has_state_hint,
    source_type: has_state_hint ? 'room_state' : '',
    source_event_type: '',
    source_path: has_state_hint ? 'roomState' : '',
    source_run_id: safe_string(room_state.current_run_id).trim(),

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


function normalize_supervisor_memory_view(bundle, fallback = {}) {
  const src = safe_object(bundle)
  const fb = safe_object(fallback)

  const read_status = safe_string(src.read_status || fb.read_status).trim()
  const read_message = safe_string(src.read_message || fb.read_message).trim()
  const read_reason_code = safe_string(src.read_reason_code || fb.read_reason_code).trim()

  const resume_decision = safe_string(src.resume_decision || fb.resume_decision).trim()
  const resume_reason = safe_string(src.resume_reason || fb.resume_reason).trim()
  const resume_ready = Boolean(
    src.resume_ready !== undefined
      ? src.resume_ready
      : fb.resume_ready
  )

  const checkpoint_stage = safe_string(src.checkpoint_stage || fb.checkpoint_stage).trim()
  const checkpoint_summary = safe_string(src.checkpoint_summary || fb.checkpoint_summary).trim()
  const recovery_hint = safe_string(src.recovery_hint || fb.recovery_hint).trim()

  const write_status = safe_string(src.write_status || fb.write_status).trim()
  const write_message = safe_string(src.write_message || fb.write_message).trim()
  const write_reason_code = safe_string(src.write_reason_code || fb.write_reason_code).trim()

  const relative_path = safe_string(src.relative_path || fb.relative_path).trim()
  const source_kind = safe_string(src.source_kind || fb.source_kind).trim()
  const bytes_written = to_int(src.bytes_written, to_int(fb.bytes_written, 0))

  const source_type = safe_string(src.source_type || fb.source_type).trim()
  const source_event_type = safe_string(src.source_event_type || fb.source_event_type).trim()
  const source_path = safe_string(src.source_path || fb.source_path).trim()
  const source_run_id = safe_string(src.source_run_id || fb.source_run_id).trim()

  const has_memory = !!(
    src.has_memory ||
    fb.has_memory ||
    read_status ||
    read_message ||
    read_reason_code ||
    resume_decision ||
    resume_reason ||
    resume_ready ||
    checkpoint_stage ||
    checkpoint_summary ||
    recovery_hint ||
    write_status ||
    write_message ||
    write_reason_code ||
    relative_path ||
    source_kind ||
    bytes_written > 0
  )

  const has_resume = !!(resume_decision || resume_reason || resume_ready)
  const has_write = !!(write_status || write_message || write_reason_code || bytes_written > 0)
  const has_checkpoint = !!(checkpoint_stage || checkpoint_summary || recovery_hint)

  const summary_bits = []
  if (read_status) summary_bits.push(`read ${read_status}`)
  if (resume_decision) summary_bits.push(`resume ${resume_decision}`)
  if (write_status) summary_bits.push(`write ${write_status}`)
  if (checkpoint_stage) summary_bits.push(`checkpoint ${checkpoint_stage}`)

  return {
    type: 'supervisor_memory',
    has_memory,
    has_state_hint: !!fb.has_state_hint,

    source_type,
    source_event_type,
    source_path,
    source_run_id,

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

    has_resume,
    has_write,
    has_checkpoint,
    summary_text: summary_bits.join(' · ').trim(),
  }
}


function build_current_runtime_supervisor_skills_source(state) {
  const result_event = current_runtime_result_event(state)
  const result_payload = safe_object(result_event?.payload || result_event)

  return {
    type: 'room_runtime',
    items: current_runtime_event_items(state),
    result_event: result_event || null,
    result_payload,
    run_id: safe_string(
      state.roomState?.current_run_id ||
      state.runtime?.run_id ||
      result_event?.run_id ||
      result_payload?.run_id
    ).trim(),
    latest_event_id: safe_string(
      state.runtime?.latest_event_id ||
      state.runtime?.tail_event_id
    ).trim(),
  }
}


function build_current_runtime_supervisor_memory_source(state) {
  const result_event = current_runtime_result_event(state)
  const result_payload = safe_object(result_event?.payload || result_event)

  return {
    type: 'room_runtime',
    items: current_runtime_event_items(state),
    result_event: result_event || null,
    result_payload,
    run_id: safe_string(
      state.roomState?.current_run_id ||
      state.runtime?.run_id ||
      result_event?.run_id ||
      result_payload?.run_id
    ).trim(),
    latest_event_id: safe_string(
      state.runtime?.latest_event_id ||
      state.runtime?.tail_event_id
    ).trim(),
  }
}


function build_replay_supervisor_skills_source(state) {
  return normalize_room_runtime_replay_bundle_payload(state.runtime?.replay_bundle)
}


function build_replay_supervisor_memory_source(state) {
  return normalize_room_runtime_replay_bundle_payload(state.runtime?.replay_bundle)
}


export const room_getters = {
  participantsCount(state) {
    return Array.isArray(state.room?.participants) ? state.room.participants.length : 0
  },


  rolesCount(state) {
    return Array.isArray(state.roles) ? state.roles.length : 0
  },


  activeTitle(state) {
    return String(state.room?.title || 'Room')
  },


  activeRolesMap(state) {
    const map = {}
    for (const role of safe_array(state.roles)) {
      const id = String(role?.role_id || '')
      if (!id) continue
      map[id] = role
    }
    return map
  },


  supervisorEnabled(state) {
    return !!state.roomState?.supervisor_enabled
  },


  replyMode(state) {
    return derive_reply_mode_from_state(state.roomState, 'manual')
  },


  supervisorProvider(state) {
    const s = safe_string(state.roomState?.supervisor_provider).trim().toLowerCase()
    return s || 'openai'
  },


  supervisorModel(state) {
    return safe_string(state.roomState?.supervisor_model).trim()
  },


  supervisorMcpOverrides(state) {
    return normalize_room_mcp_overrides(state.roomState?.mcp_overrides)
  },


  supervisorFsReadEnabled() {
    return !!this.supervisorMcpOverrides.fs_read_enabled
  },


  supervisorNotebookWriteEnabled() {
    return !!this.supervisorMcpOverrides.notebook_write_enabled
  },


  supervisorNotebookConfig() {
    return {
      notebook_dir: safe_string(this.supervisorMcpOverrides?.notebook_dir).trim() || '_room_supervisor_notebooks',
      notebook_filename: safe_string(this.supervisorMcpOverrides?.notebook_filename).trim() || 'supervisor.md',
      notebook_title: safe_string(this.supervisorMcpOverrides?.notebook_title).trim() || 'Supervisor notebook',
      notebook_section_title: safe_string(this.supervisorMcpOverrides?.notebook_section_title).trim() || 'latest',
    }
  },


  supervisorFsAudit(state) {
    return {
      at: safe_string(state.roomState?.last_supervisor_fs_read_at).trim(),
      enabled: !!state.roomState?.last_supervisor_fs_read_enabled,
      status: safe_string(state.roomState?.last_supervisor_fs_read_status).trim(),
      reason: safe_string(state.roomState?.last_supervisor_fs_read_reason).trim(),
      focus_root: safe_string(state.roomState?.last_supervisor_fs_read_focus_root).trim(),
      scope: safe_string(state.roomState?.last_supervisor_fs_read_scope).trim() || 'minimal',
      tool_calls: safe_array(state.roomState?.last_supervisor_tool_calls),
      tool_results: safe_array(state.roomState?.last_supervisor_tool_results),
    }
  },


  supervisorNotebookAudit(state) {
    return {
      at: safe_string(state.roomState?.last_supervisor_notebook_write_at).trim(),
      status: safe_string(state.roomState?.last_supervisor_notebook_write_status).trim(),
      message: safe_string(state.roomState?.last_supervisor_notebook_write_message).trim(),
      relative_path: safe_string(state.roomState?.last_supervisor_notebook_relative_path).trim(),
      tool_calls: safe_array(state.roomState?.last_supervisor_notebook_tool_calls),
      tool_results: safe_array(state.roomState?.last_supervisor_notebook_tool_results),
    }
  },


  supervisorMemoryStateBundle(state) {
    return normalize_supervisor_memory_view(
      {},
      build_supervisor_memory_state_fallback(state)
    )
  },


  supervisorSkillsStateBundle(state) {
    return normalize_supervisor_skills_view(
      {},
      build_supervisor_skills_state_fallback(state)
    )
  },


  currentRunId(state) {
    return String(state.roomState?.current_run_id || '').trim()
  },


  currentRunStatus(state) {
    return String(state.roomState?.current_run_status || '').trim()
  },


  isRunning(state) {
    return current_runtime_is_live(state)
  },


  activeRolesCount(state) {
    return Array.isArray(state.roomState?.active_roles)
      ? state.roomState.active_roles.length
      : 0
  },


  runtimeState(state) {
    return normalize_runtime_state(state.runtime)
  },


  runtimeItems(state) {
    return current_runtime_event_items(state)
  },


  runtimeRunId(state) {
    const target_run_id = current_runtime_target_run_id(state)
    const result_run_id = get_runtime_run_id(current_runtime_result_event(state))
    return String(target_run_id || result_run_id || state.runtime?.run_id || '').trim()
  },


  runtimeLatestEventId(state) {
    return String(state.runtime?.latest_event_id || '').trim()
  },


  runtimeViewMode(state) {
    return safe_string(state.runtime?.view_mode).trim() === 'replay' ? 'replay' : 'current'
  },


  runtimeSelectedReplayRunId(state) {
    const selected = safe_string(state.runtime?.selected_run_id).trim()
    if (selected) return selected
    return safe_string(state.runtime?.replay_bundle?.run_id).trim()
  },


  runtimeReplayBundle(state) {
    return normalize_room_runtime_replay_bundle_payload(state.runtime?.replay_bundle)
  },


  runtimeReplayItems() {
    return sort_runtime_events(this.runtimeReplayBundle?.items)
  },


  runtimeReplayPhases() {
    return safe_array(this.runtimeReplayBundle?.phases)
  },


  runtimeTailEventId(state) {
    const replay_tail = safe_string(
      state.runtime?.replay_bundle?.tail_event_id ||
      state.runtime?.replay_bundle?.latest_event_id
    ).trim()


    if (this.runtimeViewMode === 'replay' && replay_tail) return replay_tail


    return safe_string(state.runtime?.tail_event_id || state.runtime?.latest_event_id).trim()
  },


  latestCompletedRunId(state) {
    const candidates = [
      ...sort_runtime_events(state.runtime?.items),
      ...sort_runtime_events(state.items),
      ...sort_runtime_events(state.runtime?.replay_bundle?.items),
    ]


    for (let idx = candidates.length - 1; idx >= 0; idx -= 1) {
      const item = candidates[idx]
      if (!is_runtime_terminal_event(item)) continue
      const run_id = get_runtime_run_id(item)
      if (run_id) return run_id
    }


    return ''
  },


  runtimeRunOptions(state) {
    return build_runtime_run_options_from_lists(
      [
        state.runtime?.items,
        state.items,
        state.runtime?.replay_bundle?.items,
      ],
      safe_string(state.roomState?.current_run_id).trim(),
      safe_string(state.roomState?.current_run_status).trim()
    )
  },


  runtimeLive(state) {
    return current_runtime_is_live(state)
  },


  runtimeVisible(state) {
    if (this.runtimeViewMode === 'replay') {
      return !!(
        state.runtime?.replay_loading ||
        safe_string(state.runtime?.replay_error).trim() ||
        safe_array(state.runtime?.replay_bundle?.items).length ||
        state.runtime?.replay_loaded_once ||
        safe_string(state.runtime?.selected_run_id).trim() ||
        state.runtime?.replay_bundle?.result_event ||
        safe_string(state.runtime?.replay_bundle?.result_text).trim()
      )
    }


    const scoped_items = current_runtime_event_items(state)
    const process_items = current_runtime_process_items(state)
    const current_run_id = safe_string(state.roomState?.current_run_id).trim()
    const current_run_status = safe_string(state.roomState?.current_run_status).trim()


    return !!(
      state.runtime?.loading ||
      safe_string(state.runtime?.error).trim() ||
      scoped_items.length ||
      process_items.length ||
      current_run_id ||
      current_run_status ||
      state.runtime?.loaded_once
    )
  },


  runtimeProcessItems(state) {
    return current_runtime_process_items(state)
  },


  runtimeResultEvent(state) {
    return current_runtime_result_event(state)
  },


  runtimeResultPayload() {
    return safe_object(this.runtimeResultEvent?.payload || this.runtimeResultEvent)
  },


  runtimeResultText() {
    return safe_string(
      this.runtimeResultPayload?.response ||
      this.runtimeResultPayload?.content ||
      this.runtimeResultPayload?.message
    ).trim()
  },


  runtimeDisplayItems() {
    if (this.runtimeViewMode === 'replay' && this.runtimeReplayItems.length) {
      return this.runtimeReplayItems
    }


    return this.runtimeItems
  },


  runtimeDisplayProcessItems() {
    if (this.runtimeViewMode === 'replay' && this.runtimeReplayItems.length) {
      return get_runtime_process_items_from_list(this.runtimeReplayItems)
    }
    return this.runtimeProcessItems
  },


  runtimeDisplayResultEvent() {
    if (this.runtimeViewMode === 'replay') {
      if (this.runtimeReplayBundle?.result_event) return this.runtimeReplayBundle.result_event
      if (this.runtimeReplayItems.length) return get_runtime_result_event_from_list(this.runtimeReplayItems)
    }
    return this.runtimeResultEvent
  },


  runtimeDisplayResultPayload() {
    if (this.runtimeViewMode === 'replay') {
      const explicit = safe_object(this.runtimeReplayBundle?.result_payload)
      if (Object.keys(explicit).length > 0) return explicit
    }
    return safe_object(this.runtimeDisplayResultEvent?.payload || this.runtimeDisplayResultEvent)
  },


  runtimeDisplayResultText() {
    const explicitReplayText = safe_string(this.runtimeReplayBundle?.result_text).trim()
    const payload = safe_object(this.runtimeDisplayResultPayload)


    return safe_string(
      explicitReplayText ||
      payload.response ||
      payload.content ||
      payload.message
    ).trim()
  },


  runtimeDisplayRunId() {
    if (this.runtimeViewMode === 'replay') {
      return safe_string(
        this.runtimeSelectedReplayRunId ||
        this.runtimeReplayBundle?.run_id
      ).trim()
    }
    return this.runtimeRunId
  },


  runtimeSupervisorSkillsCurrent(state) {
    const extracted = extract_room_supervisor_skills_bundle(
      build_current_runtime_supervisor_skills_source(state)
    )
    return normalize_supervisor_skills_view(
      extracted,
      build_supervisor_skills_state_fallback(state)
    )
  },


  runtimeSupervisorSkillsReplay(state) {
    const extracted = extract_room_supervisor_skills_bundle(
      build_replay_supervisor_skills_source(state)
    )
    return normalize_supervisor_skills_view(extracted, {})
  },


  runtimeDisplaySupervisorSkills(state) {
    if (this.runtimeViewMode === 'replay') {
      const replay_bundle = this.runtimeSupervisorSkillsReplay
      if (replay_bundle?.has_skills) return replay_bundle
    }
    return this.runtimeSupervisorSkillsCurrent
  },


  runtimeDisplaySupervisorSkillsSummary() {
    const bundle = safe_object(this.runtimeDisplaySupervisorSkills)
    return {
      has_skills: !!bundle.has_skills,
      strategy: safe_string(bundle.strategy).trim(),
      status: safe_string(bundle.status).trim(),
      message: safe_string(bundle.message).trim(),
      enabled_count: to_int(bundle.enabled_count, 0),
      applied_count: to_int(bundle.applied_count, 0),
      resolved_items_count: to_int(bundle.resolved_items_count, 0),
      step_count: to_int(bundle.step_count, safe_array(bundle.step_rows).length),
      has_applied_prompt: !!bundle.has_applied_prompt,
      has_available_not_enabled: !!bundle.has_available_not_enabled,
      has_missing: !!bundle.has_missing,
      summary_text: safe_string(bundle.summary_text).trim(),
      source_type: safe_string(bundle.source_type).trim(),
      source_event_type: safe_string(bundle.source_event_type).trim(),
      source_run_id: safe_string(bundle.source_run_id).trim(),
    }
  },


  runtimeSupervisorMemoryCurrent(state) {
    const extracted = extract_room_supervisor_memory_bundle(
      build_current_runtime_supervisor_memory_source(state)
    )
    return normalize_supervisor_memory_view(
      extracted,
      build_supervisor_memory_state_fallback(state)
    )
  },


  runtimeSupervisorMemoryReplay(state) {
    const extracted = extract_room_supervisor_memory_bundle(
      build_replay_supervisor_memory_source(state)
    )
    return normalize_supervisor_memory_view(extracted, {})
  },


  runtimeDisplaySupervisorMemory(state) {
    if (this.runtimeViewMode === 'replay') {
      const replay_bundle = this.runtimeSupervisorMemoryReplay
      if (replay_bundle?.has_memory) return replay_bundle
    }
    return this.runtimeSupervisorMemoryCurrent
  },


  runtimeDisplaySupervisorMemorySummary() {
    const bundle = safe_object(this.runtimeDisplaySupervisorMemory)
    return {
      has_memory: !!bundle.has_memory,
      read_status: safe_string(bundle.read_status).trim(),
      read_message: safe_string(bundle.read_message).trim(),
      read_reason_code: safe_string(bundle.read_reason_code).trim(),
      resume_decision: safe_string(bundle.resume_decision).trim(),
      resume_reason: safe_string(bundle.resume_reason).trim(),
      resume_ready: !!bundle.resume_ready,
      checkpoint_stage: safe_string(bundle.checkpoint_stage).trim(),
      checkpoint_summary: safe_string(bundle.checkpoint_summary).trim(),
      recovery_hint: safe_string(bundle.recovery_hint).trim(),
      write_status: safe_string(bundle.write_status).trim(),
      write_message: safe_string(bundle.write_message).trim(),
      write_reason_code: safe_string(bundle.write_reason_code).trim(),
      relative_path: safe_string(bundle.relative_path).trim(),
      source_kind: safe_string(bundle.source_kind).trim(),
      bytes_written: to_int(bundle.bytes_written, 0),
      has_resume: !!bundle.has_resume,
      has_write: !!bundle.has_write,
      has_checkpoint: !!bundle.has_checkpoint,
      summary_text: safe_string(bundle.summary_text).trim(),
      source_type: safe_string(bundle.source_type).trim(),
      source_event_type: safe_string(bundle.source_event_type).trim(),
      source_run_id: safe_string(bundle.source_run_id).trim(),
    }
  },


  runtimeStatusText(state) {
    if (this.runtimeViewMode === 'replay') {
      if (safe_string(state.runtime?.replay_error).trim()) return safe_string(state.runtime.replay_error).trim()
      if (state.runtime?.replay_loading && !state.runtime?.replay_loaded_once) return '加载运行回放...'
      if (
        safe_array(state.runtime?.replay_bundle?.items).length > 0 ||
        state.runtime?.replay_bundle?.result_event ||
        safe_string(state.runtime?.replay_bundle?.result_text).trim()
      ) {
        return '回放可查看'
      }
      if (safe_string(state.runtime?.selected_run_id).trim()) return '回放待加载'
      return '暂无运行回放'
    }


    if (safe_string(state.runtime?.error).trim()) return safe_string(state.runtime.error).trim()
    if (state.runtime?.loading && !state.runtime?.loaded_once) return '加载运行过程...'


    const terminal = current_runtime_terminal_evidence(state)
    if (terminal.terminal) return terminal.label || '已完成'


    if (this.runtimeLive || this.runtimeProcessItems.length > 0) return '运行中'
    if (this.runtimeResultEvent) return '已完成'
    return '暂无运行过程'
  },


  lastPlanEvent(state) {
    const plan_events = current_runtime_event_items(state).filter((e) => e?.type === 'room.plan')
    return plan_events.length > 0 ? plan_events[plan_events.length - 1] : null
  },


  lastFinalEvent(state) {
    const final_events = current_runtime_event_items(state).filter((e) => e?.type === 'room.final')
    return final_events.length > 0 ? final_events[final_events.length - 1] : null
  },


  runGroups(state) {
    const source_items = state.runtime?.include_all_runs
      ? (
          safe_array(state.runtime?.items).length > 0
            ? safe_array(state.runtime?.items)
            : safe_array(state.items)
        )
      : current_runtime_event_items(state)


    const groups = {}
    for (const evt of source_items) {
      const run_id = String(evt?.run_id || '').trim()
      if (!run_id) continue
      if (!groups[run_id]) {
        groups[run_id] = {
          plan: null,
          routes: [],
          delegates: [],
          supervisors: [],
          messages: [],
          final: null,
          aborts: [],
          errors: [],
          terminal: null,
        }
      }
      const g = groups[run_id]
      if (evt.type === 'room.plan') g.plan = evt
      else if (evt.type === 'room.route') g.routes.push(evt)
      else if (evt.type === 'room.delegate') g.delegates.push(evt)
      else if (evt.type === 'room.supervisor') g.supervisors.push(evt)
      else if (evt.type === 'room.message') g.messages.push(evt)
      else if (evt.type === 'room.final') {
        g.final = evt
        g.terminal = evt
      } else if (evt.type === 'room.abort' || evt.type === 'room.aborted') {
        g.aborts.push(evt)
        g.terminal = evt
      } else if (evt.type === 'room.error') {
        g.errors.push(evt)
        g.terminal = evt
      }
    }
    return groups
  },


  activeRoleObjects(state) {
    const ids = new Set(safe_array(state.roomState?.active_roles).map((x) => String(x || '')))
    return safe_array(state.roles).filter((r) => ids.has(String(r?.role_id || '')))
  },


  roomWorkspaceContext(state) {
    return {
      workspace_id: String(state.roomState?.workspace_id || '').trim(),
      workspace_name: String(state.roomState?.workspace_name || '').trim(),
      focus_root: String(state.roomState?.focus_root || '').trim(),
      focus_label: String(state.roomState?.focus_label || '').trim(),
      inherit_workspace_context: !!state.roomState?.inherit_workspace_context,
      inherit_focus_root: !!state.roomState?.inherit_focus_root,
    }
  },


  roomSupervisorContext(state) {
    return {
      supervisor_enabled: !!state.roomState?.supervisor_enabled,
      reply_mode: safe_string(state.roomState?.reply_mode).trim(),
      provider: safe_string(state.roomState?.supervisor_provider).trim() || 'openai',
      model: safe_string(state.roomState?.supervisor_model).trim(),
      temperature: state.roomState?.supervisor_temperature ?? '',
      max_tokens: state.roomState?.supervisor_max_tokens ?? '',
      mcp_overrides: normalize_room_mcp_overrides(state.roomState?.mcp_overrides),
      fs_audit: {
        at: safe_string(state.roomState?.last_supervisor_fs_read_at).trim(),
        enabled: !!state.roomState?.last_supervisor_fs_read_enabled,
        status: safe_string(state.roomState?.last_supervisor_fs_read_status).trim(),
        reason: safe_string(state.roomState?.last_supervisor_fs_read_reason).trim(),
        focus_root: safe_string(state.roomState?.last_supervisor_fs_read_focus_root).trim(),
        scope: safe_string(state.roomState?.last_supervisor_fs_read_scope).trim() || 'minimal',
        tool_calls: safe_array(state.roomState?.last_supervisor_tool_calls),
        tool_results: safe_array(state.roomState?.last_supervisor_tool_results),
      },
      notebook_audit: {
        at: safe_string(state.roomState?.last_supervisor_notebook_write_at).trim(),
        status: safe_string(state.roomState?.last_supervisor_notebook_write_status).trim(),
        message: safe_string(state.roomState?.last_supervisor_notebook_write_message).trim(),
        relative_path: safe_string(state.roomState?.last_supervisor_notebook_relative_path).trim(),
        tool_calls: safe_array(state.roomState?.last_supervisor_notebook_tool_calls),
        tool_results: safe_array(state.roomState?.last_supervisor_notebook_tool_results),
      },
      memory: this.runtimeSupervisorMemoryCurrent,
      skills: this.runtimeSupervisorSkillsCurrent,
    }
  },


  hasMoreOlder(state) {
    return !!state.itemsPaging?.has_more
  },


  loadingOlder(state) {
    return !!state.itemsPaging?.loading_older
  },


  itemsNextCursor(state) {
    return normalize_room_items_cursor(state.itemsPaging?.next_cursor)
  },


  itemsPagingState(state) {
    return {
      ...DEFAULT_ITEMS_PAGING(),
      ...safe_object(state.itemsPaging),
      next_cursor: normalize_room_items_cursor(state.itemsPaging?.next_cursor),
    }
  },
}
