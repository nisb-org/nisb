import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../useMCP'
import { useRoomStore } from '../../../stores/room'
import { use_room_settings_federation } from './use_room_settings_federation'
import { use_room_settings_workspace_binding } from './use_room_settings_workspace_binding'
import { use_room_settings_form_derived } from './room_settings_form_derived'
import { use_room_settings_form_opening } from './use_room_settings_form_opening'
import { use_room_settings_form_submit } from './use_room_settings_form_submit'
import { use_room_settings_room_mcp } from './use_room_settings_room_mcp'
import { use_room_settings_external_mcp_publish } from './use_room_settings_external_mcp_publish'

const ROOM_WORKER_CONCURRENCY_MIN = 1
const ROOM_WORKER_CONCURRENCY_MAX = 4
const ROOM_WORKER_CONCURRENCY_DEFAULT = 2

function create_default_form() {
  return {
    title: '',
    summary: '',
    scratchpad: '',
    active_roles: [],
    enabled_supervisor_skill_ids: [],
    supervisor_skill_strategy: 'builtin_plus_custom',
    inherit_workspace_context: true,
    inherit_focus_root: true,
    default_reply_role_id: '',
    supervisor_enabled: false,
    reply_mode: 'manual',
    max_worker_concurrency: ROOM_WORKER_CONCURRENCY_DEFAULT,
    shared_room_config_enabled: false,
    shared_role_ids: [],
    shared_supervisor_enabled: false,
    shared_sync_from_reply_mode: true,

    room_mcp_provider_enabled: false,
    room_mcp_provider_name: '',
    room_mcp_provider_summary: '',

    supervisor_provider: 'openai',
    supervisor_model: '',
    supervisor_temperature: '',
    supervisor_max_tokens: '',
    supervisor_step_budget_total: '0',
    supervisor_fs_read_enabled: false,
    supervisor_fs_read_scope: 'minimal',
    supervisor_notebook_write_enabled: false,
    supervisor_notebook_dir: '_room_supervisor_notebooks',
    supervisor_notebook_filename: 'supervisor.md',
    supervisor_notebook_title: 'Supervisor notebook',
    supervisor_notebook_section_title: 'latest',
    p6_test_panel_enabled: false,
    p6_notebook_probe_actor: 'off',
    workspace_id: '',
    workspace_name: '',
    focus_root: '',
    focus_label: '',
    apply_after_save: true,
  }
}

export function use_room_settings_form(props) {
  const { t } = useI18n({ useScope: 'global' })
  const { callTool } = useMCP()
  const room_store = useRoomStore()

  async function call_room_tool(tool, args = {}) {
    if (typeof room_store?.callRoomTool === 'function') {
      return await room_store.callRoomTool(callTool, tool, args)
    }
    return await callTool(tool, args)
  }

  const busy = ref(false)
  const form = reactive(create_default_form())

  const workspace_options = ref([])
  const workspace_options_loading = ref(false)
  const workspace_focus_loading = ref(false)
  const workspace_options_error = ref('')

  const supervisor_skills_loading = ref(false)
  const supervisor_skills_error = ref('')
  const supervisor_skills_result = ref({})

  const room_id_value = computed(() => String(props.room_id || room_store.roomId || '').trim())
  const roles = computed(() => (Array.isArray(room_store.roles) ? room_store.roles : []))

  const supervisor_fs_audit = computed(() => room_store.supervisorFsAudit || {
    at: '',
    enabled: false,
    status: '',
    reason: '',
    focus_root: '',
    scope: 'minimal',
    tool_calls: [],
    tool_results: [],
  })

  const supervisor_notebook_audit = computed(() => room_store.supervisorNotebookAudit || {
    at: '',
    status: '',
    message: '',
    relative_path: '',
    tool_calls: [],
    tool_results: [],
  })

  const fs_tool_call_count = computed(() => (
    Array.isArray(supervisor_fs_audit.value?.tool_calls) ? supervisor_fs_audit.value.tool_calls.length : 0
  ))
  const fs_tool_result_count = computed(() => (
    Array.isArray(supervisor_fs_audit.value?.tool_results) ? supervisor_fs_audit.value.tool_results.length : 0
  ))
  const notebook_tool_call_count = computed(() => (
    Array.isArray(supervisor_notebook_audit.value?.tool_calls) ? supervisor_notebook_audit.value.tool_calls.length : 0
  ))
  const notebook_tool_result_count = computed(() => (
    Array.isArray(supervisor_notebook_audit.value?.tool_results) ? supervisor_notebook_audit.value.tool_results.length : 0
  ))

  function safe_string(v) {
    return v === null || v === undefined ? '' : String(v)
  }

  function safe_array(v) {
    return Array.isArray(v) ? v : []
  }

  function safe_object(v) {
    return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
  }

  function unwrap_result(res) {
    if (res && typeof res === 'object' && res.result && typeof res.result === 'object') {
      return res.result
    }
    return res || {}
  }

  function pick_payload(res) {
    const root = safe_object(res)
    const cands = [
      safe_object(root.result),
      safe_object(root.data),
      safe_object(root.payload),
      root,
    ]
    for (const item of cands) {
      if (Object.keys(item).length) return item
    }
    return {}
  }

  function normalized_status(data) {
    const raw = safe_string(data?.status).trim().toLowerCase()
    if (raw) return raw
    if (data?.success === false) return 'error'
    if (data?.success === true) return 'success'
    return ''
  }

  function is_success_like(res) {
    const payload = pick_payload(res)
    const status = normalized_status(payload)
    if (status) return status === 'success'
    if (payload?.success === false || res?.success === false) return false
    if (payload?.success === true || res?.success === true) return true
    return true
  }

  function assert_tool_success(
    res,
    fallback_message = t('room.settingsForm.errors.actionFailed')
  ) {
    const data = unwrap_result(res)
    const status = normalized_status(data)

    if (status && status !== 'success') {
      throw new Error(safe_string(data?.message || fallback_message) || fallback_message)
    }
    if (data?.success === false) {
      throw new Error(safe_string(data?.message || fallback_message) || fallback_message)
    }

    return data
  }

  function pick_first_tool_result(data, matcher) {
    const rows = safe_array(data?.tool_results)

    function parse_text_payload(value) {
      const text = safe_string(value).trim()
      if (!text) return null

      try {
        const parsed = JSON.parse(text)
        return parsed && typeof parsed === 'object' ? parsed : null
      } catch (_) {
        return null
      }
    }

    function candidate_rows(row) {
      if (!row || typeof row !== 'object') return []

      const candidates = [row]

      const nested_keys = [
        'result',
        'payload',
        'data',
        'item',
        'record',
        'publish',
        'external_mcp_publish',
        'room_mcp_external_publish',
      ]

      for (const key of nested_keys) {
        const value = row[key]
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          candidates.push(value)
        }
      }

      const content_rows = safe_array(row.content)
      for (const item of content_rows) {
        if (!item || typeof item !== 'object') continue
        candidates.push(item)

        const parsed = parse_text_payload(item.text)
        if (parsed) candidates.push(parsed)
      }

      const parsed_text = parse_text_payload(row.text)
      if (parsed_text) candidates.push(parsed_text)

      return candidates
    }

    for (const row of rows) {
      for (const candidate of candidate_rows(row)) {
        if (!candidate || typeof candidate !== 'object') continue
        if (matcher(candidate)) return candidate
      }
    }

    return null
  }

  function extract_workspace_list(data) {
    const row = pick_first_tool_result(
      data,
      (x) => x.type === 'workspace_list' && Array.isArray(x.workspaces)
    )
    if (row) return safe_array(row.workspaces)
    return safe_array(data?.workspaces)
  }

  function extract_workspace_files_state(data) {
    const row = pick_first_tool_result(
      data,
      (x) => x.type === 'workspace_files_state' && x.files_state && typeof x.files_state === 'object'
    )

    if (row) {
      return {
        workspace_id: safe_string(row.workspace_id).trim(),
        files_state: safe_object(row.files_state),
        last_updated: safe_string(row.last_updated).trim(),
        migrate_stats: safe_object(row.migrate_stats),
      }
    }

    return {
      workspace_id: safe_string(data?.workspace_id).trim(),
      files_state: safe_object(data?.files_state),
      last_updated: safe_string(data?.last_updated).trim(),
      migrate_stats: safe_object(data?.migrate_stats),
    }
  }

  function normalize_focus_root_client(value) {
    let s = String(value || '').trim().replace(/\\/g, '/')
    while (s.includes('//')) s = s.replace(/\/\//g, '/')
    s = s.replace(/^\/+|\/+$/g, '')
    const parts = s
      .split('/')
      .map((x) => String(x || '').trim())
      .filter((x) => x && x !== '.' && x !== '..')
    return parts.join('/')
  }

  function normalize_relative_path_client(value, fallback = '') {
    const out = normalize_focus_root_client(value)
    return out || fallback
  }

  function normalize_filename_client(value, fallback = 'supervisor.md') {
    const raw = String(value || '').trim().replace(/\\/g, '/')
    if (!raw) return fallback
    const parts = raw
      .split('/')
      .map((x) => String(x || '').trim())
      .filter(Boolean)
    const base = parts.length ? parts[parts.length - 1] : ''
    if (!base || base === '.' || base === '..') return fallback
    return base.toLowerCase().endsWith('.md') ? base : `${base}.md`
  }

  function normalize_role_ids(list) {
    const uniq = new Set()
    const out = []
    for (const item of Array.isArray(list) ? list : []) {
      const role_id = String(item || '').trim()
      if (!role_id || uniq.has(role_id)) continue
      uniq.add(role_id)
      out.push(role_id)
    }
    return out
  }

  function normalize_skill_id_client(value) {
    let s = normalize_focus_root_client(value)
    if (!s) return ''
    if (s === '_room_supervisor_skills') return ''
    if (s.startsWith('_room_supervisor_skills/')) {
      s = s.slice('_room_supervisor_skills/'.length)
    }
    if (s.toLowerCase().endsWith('.md')) {
      s = s.slice(0, -3)
    }
    return normalize_focus_root_client(s)
  }

  function normalize_skill_ids_client(list) {
    const uniq = new Set()
    const out = []
    for (const item of Array.isArray(list) ? list : []) {
      const skillId = normalize_skill_id_client(item)
      if (!skillId || uniq.has(skillId)) continue
      uniq.add(skillId)
      out.push(skillId)
    }
    return out
  }

  function normalize_supervisor_skill_strategy_client(value, fallback = 'builtin_plus_custom') {
    const s = String(value || '').trim().toLowerCase()

    if (s === 'builtin_only') return 'builtin_only'
    if (s === 'custom_only') return 'custom_only'
    if (s === 'builtin_plus_custom') return 'builtin_plus_custom'

    return fallback
  }

  function normalize_p6_probe_actor_client(value, fallback = 'off') {
    const s = String(value || '').trim().toLowerCase()
    if (s === 'supervisor') return 'supervisor'
    if (s === 'worker') return 'worker'
    if (s === 'skill') return 'skill'
    if (s === 'off') return 'off'
    return fallback
  }

  const P6_TEST_CONTROL_SESSION_KEY_PREFIX = 'nisb_room_p6_test_control:'

  function get_p6_test_control_session_key(roomId = '') {
    const rid = safe_string(roomId).trim()
    return rid ? `${P6_TEST_CONTROL_SESSION_KEY_PREFIX}${rid}` : ''
  }

  function read_p6_test_control_session(roomId = '') {
    try {
      const key = get_p6_test_control_session_key(roomId)
      if (!key || typeof window === 'undefined' || !window.sessionStorage) {
        return {}
      }

      const raw = window.sessionStorage.getItem(key)
      if (!raw) return {}

      const parsed = safe_object(JSON.parse(raw))
      return {
        panel_enabled: !!parsed.panel_enabled,
        notebook_probe_actor: normalize_p6_probe_actor_client(
          parsed.notebook_probe_actor || 'off',
          'off'
        ),
      }
    } catch {
      return {}
    }
  }

  function write_p6_test_control_session(roomId = '', control = {}) {
    try {
      const key = get_p6_test_control_session_key(roomId)
      if (!key || typeof window === 'undefined' || !window.sessionStorage) {
        return
      }

      const src = safe_object(control)
      const normalized = {
        panel_enabled: !!src.panel_enabled,
        notebook_probe_actor: normalize_p6_probe_actor_client(
          src.notebook_probe_actor || 'off',
          'off'
        ),
      }

      window.sessionStorage.setItem(key, JSON.stringify(normalized))
    } catch {
      // noop
    }
  }

  function apply_p6_test_control_to_room_store(roomId = '', control = {}) {
    const src = safe_object(control)
    const normalized = {
      panel_enabled: !!src.panel_enabled,
      notebook_probe_actor: normalize_p6_probe_actor_client(
        src.notebook_probe_actor || 'off',
        'off'
      ),
    }

    write_p6_test_control_session(roomId, normalized)

    const currentRoomState = safe_object(room_store.roomState)
    room_store.roomState = {
      ...currentRoomState,
      p6_test_control: normalized,
      p6_test_panel_enabled: normalized.panel_enabled,
      p6_notebook_probe_actor: normalized.notebook_probe_actor,
    }
  }

  function normalize_supervisor_skill_item_client(item) {
    const row = safe_object(item)
    const skill_id = normalize_skill_id_client(
      row.skill_id || row.relative_path || row.filename || row.name || ''
    )
    if (!skill_id) return null

    const base_name = skill_id.split('/').filter(Boolean).slice(-1)[0] || skill_id

    return {
      ...row,
      skill_id,
      name: safe_string(row.name).trim() || base_name,
      filename: safe_string(row.filename).trim() || `${base_name}.md`,
      relative_path: safe_string(row.relative_path).trim() || `_room_supervisor_skills/${skill_id}.md`,
      title: safe_string(row.title).trim() || base_name,
      enabled_by_room: !!row.enabled_by_room,
      size: Number.isFinite(Number(row.size)) ? Number(row.size) : 0,
      updated_at: safe_string(row.updated_at).trim(),
    }
  }

  function normalize_supervisor_skills_result_client(data) {
    const row = safe_object(data)
    const items = safe_array(row.items)
      .map((item) => normalize_supervisor_skill_item_client(item))
      .filter(Boolean)

    return {
      ...row,
      status: safe_string(row.status).trim() || 'success',
      enabled: row.enabled === undefined ? true : !!row.enabled,
      message: safe_string(row.message).trim(),
      skills_root: safe_string(row.skills_root).trim(),
      items_count: items.length,
      items,
    }
  }

  function get_saved_enabled_supervisor_skill_ids_from_result(result) {
    const items = safe_array(result?.items)

    return normalize_skill_ids_client(
      items
        .filter((item) => !!safe_object(item).enabled_by_room)
        .map((item) => (
          safe_object(item).skill_id ||
          safe_object(item).relative_path ||
          safe_object(item).filename ||
          ''
        ))
    )
  }

  function sync_local_supervisor_skills_from_saved_result(result, { force = false } = {}) {
    const next_ids = get_saved_enabled_supervisor_skill_ids_from_result(result)
    const current_ids = normalize_skill_ids_client(form.enabled_supervisor_skill_ids)

    if (!force && current_ids.length > 0) {
      return
    }

    form.enabled_supervisor_skill_ids = next_ids
  }

  function is_supervisor_skill_enabled_locally(skill_id) {
    const normalized = normalize_skill_id_client(skill_id)
    if (!normalized) return false
    return normalize_skill_ids_client(form.enabled_supervisor_skill_ids).includes(normalized)
  }

  function get_saved_supervisor_skill_enabled(skill) {
    return !!safe_object(skill).enabled_by_room
  }

  function toggle_supervisor_skill(skill_id) {
    const normalized = normalize_skill_id_client(skill_id)
    if (!normalized) return

    const current = new Set(normalize_skill_ids_client(form.enabled_supervisor_skill_ids))
    if (current.has(normalized)) {
      current.delete(normalized)
    } else {
      current.add(normalized)
    }

    form.enabled_supervisor_skill_ids = Array.from(current)
  }

  async function refresh_supervisor_skills(options = {}) {
    const {
      sync_local_from_saved = false,
      force_sync_local = false,
    } = safe_object(options)

    supervisor_skills_loading.value = true
    supervisor_skills_error.value = ''

    try {
      const room_id = safe_string(room_id_value.value).trim()
      const workspace_id = safe_string(form.workspace_id).trim()
      const workspace_name = safe_string(form.workspace_name).trim()
      const focus_root = normalize_focus_root_client(form.focus_root)

      if (!room_id) {
        throw new Error(t('room.settingsForm.errors.noRoomIdForSupervisorSkills'))
      }
      if (!workspace_id) {
        throw new Error(t('room.settingsForm.errors.bindWorkspaceFirst'))
      }
      if (!focus_root) {
        throw new Error(t('room.settingsForm.errors.noFocusRootForSupervisorSkills'))
      }

      const data = assert_tool_success(
        await callTool('nisb_room_supervisor_skills_list', {
          room_id,
          workspace_id,
          workspace_name,
          focus_root,
          focused_root_path: focus_root,
        }),
        t('room.settingsForm.errors.loadSupervisorSkillsFailed')
      )

      const normalized = normalize_supervisor_skills_result_client(data)
      supervisor_skills_result.value = normalized

      if (sync_local_from_saved) {
        sync_local_supervisor_skills_from_saved_result(normalized, {
          force: !!force_sync_local,
        })
      }
    } catch (error) {
      supervisor_skills_result.value = {}
      supervisor_skills_error.value = safe_string(
        error?.message || error || t('room.settingsForm.errors.loadSupervisorSkillsFailed')
      )
    } finally {
      supervisor_skills_loading.value = false
    }
  }

  function normalize_reply_mode_client(value, fallback = 'manual') {
    const s = String(value || '').trim().toLowerCase()
    if (s === 'manual') return 'manual'
    if (s === 'supervisor') return 'supervisor'
    if (s === 'supervisor_direct') return 'supervisor_direct'
    if (s === 'direct_role') return 'direct_role'
    return fallback
  }

  function derive_reply_mode_from_state_client(roomState) {
    const explicit = normalize_reply_mode_client(roomState?.reply_mode, '')
    if (explicit) return explicit
    if (roomState?.supervisor_enabled) return 'supervisor'
    if (String(roomState?.default_reply_role_id || '').trim()) return 'direct_role'
    return 'manual'
  }

  function normalize_worker_concurrency_client(value, fallback = ROOM_WORKER_CONCURRENCY_DEFAULT) {
    const fallback_num = Number(fallback)
    const safe_fallback = Number.isFinite(fallback_num)
      ? Math.trunc(fallback_num)
      : ROOM_WORKER_CONCURRENCY_DEFAULT
    const raw = Number(value)

    if (!Number.isFinite(raw)) {
      return Math.min(
        ROOM_WORKER_CONCURRENCY_MAX,
        Math.max(ROOM_WORKER_CONCURRENCY_MIN, safe_fallback)
      )
    }

    return Math.min(
      ROOM_WORKER_CONCURRENCY_MAX,
      Math.max(ROOM_WORKER_CONCURRENCY_MIN, Math.trunc(raw))
    )
  }

  function pick_worker_concurrency_from_state(roomState = {}) {
    const orchestration = safe_object(roomState?.orchestration)

    if (roomState?.max_worker_concurrency !== undefined) {
      return roomState.max_worker_concurrency
    }
    if (orchestration?.max_worker_concurrency !== undefined) {
      return orchestration.max_worker_concurrency
    }
    if (roomState?.worker_concurrency !== undefined) {
      return roomState.worker_concurrency
    }
    if (orchestration?.worker_concurrency !== undefined) {
      return orchestration.worker_concurrency
    }

    return ROOM_WORKER_CONCURRENCY_DEFAULT
  }

  function derive_shared_mapping_from_form(src = {}) {
    const reply_mode = normalize_reply_mode_client(src.reply_mode, 'manual')
    const shared_room_enabled = !!src.shared_room_config_enabled
    const default_reply_role_id = safe_string(src.default_reply_role_id).trim()
    const active_roles = normalize_role_ids(src.active_roles)
    const existing_shared_role_ids = normalize_role_ids(src.shared_role_ids)
    const existing_shared_supervisor_enabled = !!src.shared_supervisor_enabled

    if (!shared_room_enabled) {
      return {
        shared_role_ids: [],
        shared_supervisor_enabled: false,
      }
    }

    if (reply_mode === 'direct_role') {
      return {
        shared_role_ids: default_reply_role_id ? [default_reply_role_id] : [],
        shared_supervisor_enabled: false,
      }
    }

    if (reply_mode === 'supervisor') {
      return {
        shared_role_ids: active_roles,
        shared_supervisor_enabled: active_roles.length > 0,
      }
    }

    if (reply_mode === 'manual') {
      return {
        shared_role_ids: [],
        shared_supervisor_enabled: false,
      }
    }

    return {
      shared_role_ids: existing_shared_role_ids,
      shared_supervisor_enabled: existing_shared_supervisor_enabled,
    }
  }

  function sync_shared_mapping_from_current_reply_config() {
    if (!form.shared_sync_from_reply_mode) return

    const derived = derive_shared_mapping_from_form(form)
    form.shared_role_ids = normalize_role_ids(derived.shared_role_ids || [])
    form.shared_supervisor_enabled = !!derived.shared_supervisor_enabled
  }

  function normalize_supervisor_provider_client(value) {
    const s = String(value || '').trim().toLowerCase()
    if (s === 'anthropic') return 'anthropic'
    return 'openai'
  }

  function normalize_fs_read_scope_client(value) {
    const s = String(value || '').trim().toLowerCase()
    if (s === 'user_ro') return 'user_ro'
    return 'minimal'
  }

  function normalize_optional_number_string(value, { integer = false } = {}) {
    const raw = String(value ?? '').trim()
    if (!raw) return ''
    const n = Number(raw)
    if (!Number.isFinite(n)) return ''
    if (integer) return String(Math.max(0, Math.trunc(n)))
    return String(n)
  }

  function normalize_step_budget_total_client(value, fallback = '0') {
    const raw = String(value ?? '').trim()
    if (!raw) return fallback

    const n = Number(raw)
    if (!Number.isFinite(n)) return fallback

    return String(Math.max(0, Math.trunc(n)))
  }

  function infer_provider_from_model_id(modelId) {
    const s = String(modelId || '').trim().toLowerCase()
    if (!s) return ''
    if (s.startsWith('claude-')) return 'anthropic'
    if (s.startsWith('gpt-') || s.startsWith('o1') || s.startsWith('o3') || s.startsWith('o4')) return 'openai'
    return ''
  }

  function is_workspace_id_safe(value) {
    const s = safe_string(value).trim()
    return s.startsWith('workspace_')
  }

  function normalize_workspace_option(item) {
    const meta = safe_object(item?.meta)
    const id = safe_string(item?.id).trim()
    const name = safe_string(item?.name).trim() || id
    const description = safe_string(item?.description).trim()
    const icon = safe_string(meta?.icon).trim()

    return {
      id,
      name,
      description,
      icon,
      display_name: `${icon ? `${icon} ` : ''}${name}`.trim() || id,
    }
  }

  function get_workspace_option_by_id(workspaceId) {
    const id = safe_string(workspaceId).trim()
    return safe_array(workspace_options.value).find((item) => safe_string(item?.id).trim() === id) || null
  }

  function derive_focus_root_from_files_state(info) {
    const saved = normalize_focus_root_client(info?.files_state?.saved?.focused_root_path || '')
    if (saved) return saved

    const current = normalize_focus_root_client(info?.files_state?.current?.focused_root_path || '')
    if (current) return current

    return ''
  }

  function derive_focus_label_from_binding(workspaceId, focusRoot) {
    const option = get_workspace_option_by_id(workspaceId)
    const workspaceName = safe_string(option?.name || form.workspace_name).trim()
    if (workspaceName) return workspaceName

    const parts = normalize_focus_root_client(focusRoot).split('/').filter(Boolean)
    return parts.length ? parts[parts.length - 1] : ''
  }

  function sync_workspace_identity_from_selection() {
    const wid = safe_string(form.workspace_id).trim()

    if (!wid) {
      form.workspace_name = ''
      return null
    }

    const option = get_workspace_option_by_id(wid)
    if (option) {
      form.workspace_id = option.id
      form.workspace_name = option.name || option.id
      return option
    }

    if (!safe_string(form.workspace_name).trim()) {
      form.workspace_name = wid
    }
    return null
  }

  function read_first_nonempty_string(cands = []) {
    for (const item of cands) {
      const value = safe_string(item).trim()
      if (value) return value
    }
    return ''
  }

  const current_user_id_value = computed(() => read_first_nonempty_string([
    room_store.currentUser?.user_id,
    room_store.currentUser?.id,
    room_store.current_user_id,
    room_store.currentUserId,
    room_store.user?.user_id,
    room_store.user?.id,
    room_store.me?.user_id,
    room_store.me?.id,
    room_store.profile?.user_id,
    room_store.profile?.id,
    room_store.session?.user_id,
    room_store.session?.id,
    room_store.roomState?.current_user_id,
    room_store.roomState?.user_id,
  ]))

  const room_owner_user_id_value = computed(() => read_first_nonempty_string([
    room_store.room?.owner_user_id,
    room_store.roomInfo?.owner_user_id,
    room_store.roomState?.owner_user_id,
    room_store.room?.meta?.owner_user_id,
  ]))

  const room_member_role_value = computed(() => read_first_nonempty_string([
    room_store.room?.room_member_role,
    room_store.room?.member_role,
    room_store.roomInfo?.room_member_role,
    room_store.roomInfo?.member_role,
    room_store.roomState?.room_member_role,
    room_store.roomState?.member_role,
    room_store.room?.meta?.room_member_role,
  ]).toLowerCase())

  const owner_resolution_state = computed(() => {
    const explicit_role = room_member_role_value.value

    if (explicit_role === 'owner') return 'owner'
    if (['member', 'guest', 'readonly', 'viewer'].includes(explicit_role)) return 'member'

    const owner_user_id = room_owner_user_id_value.value
    const current_user_id = current_user_id_value.value
    if (owner_user_id && current_user_id) {
      return owner_user_id === current_user_id ? 'owner' : 'member'
    }

    return 'unknown'
  })

  const is_room_owner = computed(() => owner_resolution_state.value === 'owner')
  const is_explicit_member_readonly = computed(() => owner_resolution_state.value === 'member')

  const can_edit_room_state = computed(() => !is_explicit_member_readonly.value)
  const can_manage_room_roles = computed(() => !is_explicit_member_readonly.value)

  function has_owner_federation_visibility_signal() {
    if (safe_string(current_room_join_key?.value).trim()) return true
    if (safe_string(room_store.room?.join_key).trim()) return true
    if (safe_string(room_store.roomInfo?.join_key).trim()) return true
    return false
  }

  function has_owner_federation_manage_signal() {
    if (safe_string(current_room_join_key?.value).trim()) return true
    if (safe_string(room_store.room?.join_key).trim()) return true
    if (safe_string(room_store.roomInfo?.join_key).trim()) return true
    return false
  }

  const can_manage_federation = computed(() => {
    if (is_room_owner.value) return true
    if (is_explicit_member_readonly.value) return false
    return has_owner_federation_manage_signal()
  })

  const show_federation_section = computed(() => {
    if (can_manage_federation.value) return true
    if (is_explicit_member_readonly.value) return false
    return has_owner_federation_visibility_signal()
  })

  const can_issue_federation_invite = computed(() => can_manage_federation.value)

  const shared_role_ids_set = computed(() => {
    const ids = normalize_role_ids([
      ...safe_array(room_store.room?.shared_role_ids),
      ...safe_array(room_store.roomInfo?.shared_role_ids),
      ...safe_array(room_store.roomState?.shared_role_ids),
      ...safe_array(room_store.room?.meta?.shared_role_ids),
    ])
    return new Set(ids)
  })

  const is_supervisor_shared = computed(() => {
    const cands = [
      room_store.room?.shared_supervisor_enabled,
      room_store.roomInfo?.shared_supervisor_enabled,
      room_store.roomState?.shared_supervisor_enabled,
      room_store.room?.meta?.shared_supervisor_enabled,
    ]
    return cands.some((item) => item === true)
  })

  const {
    current_room_join_key,
    federation_peers,
    federation_peers_loading,
    federation_target_peer_id,
    federation_invite_ttl_seconds,
    federation_invite_ttl_options,
    federation_invite_history_filter,
    federation_invite_history_filter_options,
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
    set_federation_invite_history_filter,
  } = use_room_settings_federation({
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
  })

  function normalize_federation_invite_status(value) {
    const s = safe_string(value).trim().toLowerCase()
    if (s === 'active') return 'active'
    if (s === 'used') return 'used'
    if (s === 'revoked') return 'revoked'
    if (s === 'expired') return 'expired'
    return 'unknown'
  }

  function normalize_federation_member_summary_row(item) {
    const row = safe_object(item)
    const participant_uid = safe_string(row.participant_uid || row.uid).trim()
    const type_raw = safe_string(row.type).trim().toLowerCase()
    const is_federated = type_raw === 'federated' || participant_uid.startsWith('fed__')
    const access_status = safe_string(row.access_status).trim().toLowerCase() === 'revoked'
      ? 'revoked'
      : 'active'

    return {
      participant_uid,
      type: is_federated ? 'federated' : 'local',
      access_status,
      is_access_revoked: !!row.is_access_revoked || access_status === 'revoked',
    }
  }

  const federation_summary_counts = computed(() => {
    const counts = {
      active_invites: 0,
      used_invites: 0,
      revoked_invites: 0,
      expired_invites: 0,
      joined_federated_members: 0,
      revoked_federated_members: 0,
    }

    for (const item of safe_array(federation_invites.value)) {
      const status = normalize_federation_invite_status(item?.status)
      if (status === 'active') counts.active_invites += 1
      else if (status === 'used') counts.used_invites += 1
      else if (status === 'revoked') counts.revoked_invites += 1
      else if (status === 'expired') counts.expired_invites += 1
    }

    for (const item of safe_array(federation_joined_members.value)) {
      const row = normalize_federation_member_summary_row(item)
      if (row.type !== 'federated') continue

      counts.joined_federated_members += 1
      if (row.is_access_revoked) {
        counts.revoked_federated_members += 1
      }
    }

    return counts
  })

  const federation_summary_notes = computed(() => ([
    'invite 已 used，不代表 member 仍 active。',
    'member 已 revoked，不等于 invite 被回收。',
  ]))

  async function load_workspace_options() {
    workspace_options_loading.value = true
    workspace_options_error.value = ''

    try {
      const data = assert_tool_success(
        await callTool('nisb_workspace_list', {}),
        t('room.settingsForm.errors.loadWorkspaceListFailed')
      )

      workspace_options.value = extract_workspace_list(data)
        .map((item) => normalize_workspace_option(item))
        .filter((item) => is_workspace_id_safe(item.id))

      sync_workspace_identity_from_selection()
    } catch (error) {
      workspace_options.value = []
      workspace_options_error.value = safe_string(
        error?.message || error || t('room.settingsForm.errors.loadWorkspaceListFailed')
      )
    } finally {
      workspace_options_loading.value = false
    }
  }

  async function hydrate_workspace_snapshot_for_form(workspaceId = '') {
    const wid = safe_string(workspaceId || form.workspace_id).trim()

    if (!is_workspace_id_safe(wid)) {
      if (!wid) {
        form.focus_root = ''
        form.focus_label = ''
      }
      return
    }

    workspace_focus_loading.value = true
    workspace_options_error.value = ''

    try {
      const data = assert_tool_success(
        await callTool('nisb_workspace_files_state_get', { workspace_id: wid }),
        t('room.settingsForm.errors.loadWorkspaceSnapshotFailed')
      )

      const info = extract_workspace_files_state(data)
      const next_focus_root = derive_focus_root_from_files_state(info)

      form.focus_root = next_focus_root
      form.focus_label = derive_focus_label_from_binding(wid, next_focus_root)
    } catch (error) {
      form.focus_root = ''
      form.focus_label = derive_focus_label_from_binding(wid, '')
      workspace_options_error.value = safe_string(
        error?.message || error || t('room.settingsForm.errors.loadWorkspaceSnapshotFailed')
      )
    } finally {
      workspace_focus_loading.value = false
    }
  }

  async function handle_workspace_selection_change(nextWorkspaceId = '') {
    form.workspace_id = safe_string(nextWorkspaceId).trim()
    workspace_options_error.value = ''
    supervisor_skills_error.value = ''
    supervisor_skills_result.value = {}

    if (!form.workspace_id) {
      form.workspace_name = ''
      form.focus_root = ''
      form.focus_label = ''
      form.enabled_supervisor_skill_ids = []
      return
    }

    form.enabled_supervisor_skill_ids = []
    sync_workspace_identity_from_selection()
    await hydrate_workspace_snapshot_for_form(form.workspace_id)
  }

  function is_role_active(role_id) {
    const id = String(role_id || '').trim()
    return form.active_roles.includes(id)
  }

  function set_default_role(role_id) {
    const id = String(role_id || '').trim()
    form.default_reply_role_id = id
    if (id && !form.active_roles.includes(id)) {
      form.active_roles = normalize_role_ids([...form.active_roles, id])
    }
    sync_shared_mapping_from_current_reply_config()
  }

  function handle_default_role_change() {
    const id = String(form.default_reply_role_id || '').trim()
    if (!id) {
      if (form.reply_mode === 'direct_role') {
        form.reply_mode = 'manual'
      }
      sync_shared_mapping_from_current_reply_config()
      return
    }
    if (!form.active_roles.includes(id)) {
      form.active_roles = normalize_role_ids([...form.active_roles, id])
    }
    sync_shared_mapping_from_current_reply_config()
  }

  function handle_reply_mode_change() {
    form.reply_mode = normalize_reply_mode_client(form.reply_mode)

    if (form.reply_mode === 'supervisor' || form.reply_mode === 'supervisor_direct') {
      form.supervisor_enabled = true
      form.supervisor_provider = normalize_supervisor_provider_client(form.supervisor_provider)
      sync_shared_mapping_from_current_reply_config()
      return
    }

    if (form.reply_mode === 'direct_role' && form.default_reply_role_id) {
      if (!form.active_roles.includes(form.default_reply_role_id)) {
        form.active_roles = normalize_role_ids([...form.active_roles, form.default_reply_role_id])
      }
      sync_shared_mapping_from_current_reply_config()
      return
    }

    if (form.reply_mode === 'manual') {
      sync_shared_mapping_from_current_reply_config()
      return
    }

    sync_shared_mapping_from_current_reply_config()
  }

  function handle_supervisor_provider_change() {
    const nextProvider = normalize_supervisor_provider_client(form.supervisor_provider)
    const currentModelProvider = infer_provider_from_model_id(form.supervisor_model)

    form.supervisor_provider = nextProvider

    if (form.supervisor_model && currentModelProvider && currentModelProvider !== nextProvider) {
      form.supervisor_model = ''
    }
  }

  function toggle_active_role(role_id) {
    const id = String(role_id || '').trim()
    if (!id) return

    if (form.active_roles.includes(id)) {
      form.active_roles = form.active_roles.filter((item) => item !== id)
      if (form.default_reply_role_id === id) {
        form.default_reply_role_id = ''
        if (form.reply_mode === 'direct_role') {
          form.reply_mode = 'manual'
        }
      }
      sync_shared_mapping_from_current_reply_config()
      return
    }

    form.active_roles = normalize_role_ids([...form.active_roles, id])
    sync_shared_mapping_from_current_reply_config()
  }

  function select_all_roles() {
    form.active_roles = normalize_role_ids(roles.value.map((item) => String(item?.role_id || '')))
    if (form.default_reply_role_id && !form.active_roles.includes(form.default_reply_role_id)) {
      form.active_roles.push(form.default_reply_role_id)
    }
    form.active_roles = normalize_role_ids(form.active_roles)
    sync_shared_mapping_from_current_reply_config()
  }

  function clear_active_roles() {
    form.active_roles = []
    form.default_reply_role_id = ''
    if (form.reply_mode === 'direct_role') {
      form.reply_mode = 'manual'
    }
    sync_shared_mapping_from_current_reply_config()
  }

  function keep_only_default_role() {
    const id = String(form.default_reply_role_id || '').trim()
    if (!id) return
    form.active_roles = [id]
    sync_shared_mapping_from_current_reply_config()
  }

  function sanitize_role_state_against_current_roles() {
    const existing_ids = new Set(
      roles.value
        .map((item) => String(item?.role_id || '').trim())
        .filter(Boolean)
    )

    form.active_roles = normalize_role_ids(form.active_roles.filter((id) => existing_ids.has(id)))
    form.shared_role_ids = normalize_role_ids(form.shared_role_ids.filter((id) => existing_ids.has(id)))

    if (form.default_reply_role_id && !existing_ids.has(form.default_reply_role_id)) {
      form.default_reply_role_id = ''
    }

    if (form.default_reply_role_id && !form.active_roles.includes(form.default_reply_role_id)) {
      form.active_roles = normalize_role_ids([...form.active_roles, form.default_reply_role_id])
    }

    if (form.reply_mode === 'direct_role' && !form.default_reply_role_id) {
      form.reply_mode = 'manual'
    }

    if (form.shared_supervisor_enabled && form.shared_role_ids.length === 0) {
      form.shared_supervisor_enabled = false
    }

    form.reply_mode = normalize_reply_mode_client(form.reply_mode)
    form.max_worker_concurrency = normalize_worker_concurrency_client(form.max_worker_concurrency)
    sync_shared_mapping_from_current_reply_config()
  }

  function fill_form_from_store() {
    const room = safe_object(room_store.room)
    const roomInfo = safe_object(room_store.roomInfo)
    const roomMeta = safe_object(room.meta)
    const roomState = safe_object(room_store.roomState)
    const mcp = safe_object(roomState.mcp_overrides)
    const persisted_p6 = safe_object(roomState.p6_test_control)
    const cached_p6 = read_p6_test_control_session(room_id_value.value)
    const p6 = Object.keys(persisted_p6).length ? persisted_p6 : cached_p6

    const sharedRoomConfigValue =
      room.shared_room_config_enabled !== undefined
        ? room.shared_room_config_enabled
        : roomInfo.shared_room_config_enabled !== undefined
          ? roomInfo.shared_room_config_enabled
          : roomMeta.shared_room_config_enabled

    const sharedRoleIdsValue = normalize_role_ids([
      ...safe_array(room.shared_role_ids),
      ...safe_array(roomInfo.shared_role_ids),
      ...safe_array(roomState.shared_role_ids),
      ...safe_array(roomMeta.shared_role_ids),
    ])

    const sharedSupervisorEnabledValue = [
      room.shared_supervisor_enabled,
      roomInfo.shared_supervisor_enabled,
      roomState.shared_supervisor_enabled,
      roomMeta.shared_supervisor_enabled,
    ].some((item) => item === true)

    const roomMcpProviderEnabledValue =
      room.room_mcp_provider_enabled !== undefined
        ? room.room_mcp_provider_enabled
        : roomInfo.room_mcp_provider_enabled !== undefined
          ? roomInfo.room_mcp_provider_enabled
          : roomMeta.room_mcp_provider_enabled

    const roomMcpProviderNameValue =
      room.room_mcp_provider_name !== undefined && room.room_mcp_provider_name !== null
        ? room.room_mcp_provider_name
        : roomInfo.room_mcp_provider_name !== undefined && roomInfo.room_mcp_provider_name !== null
          ? roomInfo.room_mcp_provider_name
          : roomMeta.room_mcp_provider_name

    const roomMcpProviderSummaryValue =
      room.room_mcp_provider_summary !== undefined && room.room_mcp_provider_summary !== null
        ? room.room_mcp_provider_summary
        : roomInfo.room_mcp_provider_summary !== undefined && roomInfo.room_mcp_provider_summary !== null
          ? roomInfo.room_mcp_provider_summary
          : roomMeta.room_mcp_provider_summary

    form.title = String(room.title || roomInfo.title || '')
    form.shared_room_config_enabled = !!sharedRoomConfigValue
    form.shared_role_ids = sharedRoleIdsValue
    form.shared_supervisor_enabled = !!sharedSupervisorEnabledValue
    form.shared_sync_from_reply_mode = true

    form.room_mcp_provider_enabled = !!roomMcpProviderEnabledValue
    form.room_mcp_provider_name = String(roomMcpProviderNameValue || '').trim()
    form.room_mcp_provider_summary = String(roomMcpProviderSummaryValue || '').trim()

    reset_room_mcp_share_ref_state()
    reset_room_mcp_publication_state({ keep_form_fallback: true })
    reset_room_mcp_grants_state()
    reset_external_mcp_publish_state()

    form.summary = String(roomState.summary || '')
    form.scratchpad = String(roomState.scratchpad || '')
    form.active_roles = normalize_role_ids(roomState.active_roles || [])
    form.enabled_supervisor_skill_ids = normalize_skill_ids_client(roomState.enabled_supervisor_skill_ids || [])
    form.supervisor_skill_strategy = normalize_supervisor_skill_strategy_client(
      roomState.supervisor_skill_strategy,
      'builtin_plus_custom'
    )
    form.inherit_workspace_context = roomState.inherit_workspace_context === undefined ? true : !!roomState.inherit_workspace_context
    form.inherit_focus_root = roomState.inherit_focus_root === undefined ? true : !!roomState.inherit_focus_root
    form.default_reply_role_id = String(roomState.default_reply_role_id || '').trim()
    form.supervisor_enabled = !!roomState.supervisor_enabled
    form.reply_mode = derive_reply_mode_from_state_client(roomState)
    form.max_worker_concurrency = normalize_worker_concurrency_client(
      pick_worker_concurrency_from_state(roomState),
      ROOM_WORKER_CONCURRENCY_DEFAULT
    )
    form.supervisor_provider = normalize_supervisor_provider_client(roomState.supervisor_provider || 'openai')
    form.supervisor_model = String(roomState.supervisor_model || '').trim()
    form.supervisor_temperature = normalize_optional_number_string(roomState.supervisor_temperature)
    form.supervisor_max_tokens = normalize_optional_number_string(roomState.supervisor_max_tokens, { integer: true })
    form.supervisor_step_budget_total = normalize_step_budget_total_client(
      roomState.supervisor_step_budget_total,
      '0'
    )

    form.supervisor_fs_read_enabled = !!mcp.fs_read_enabled
    form.supervisor_fs_read_scope = normalize_fs_read_scope_client(mcp.fs_read_scope || 'minimal')
    form.supervisor_notebook_write_enabled = !!mcp.notebook_write_enabled
    form.supervisor_notebook_dir = normalize_relative_path_client(mcp.notebook_dir, '_room_supervisor_notebooks') || '_room_supervisor_notebooks'
    form.supervisor_notebook_filename = normalize_filename_client(mcp.notebook_filename, 'supervisor.md')
    form.supervisor_notebook_title = String(mcp.notebook_title || 'Supervisor notebook').trim() || 'Supervisor notebook'
    form.supervisor_notebook_section_title = String(mcp.notebook_section_title || 'latest').trim() || 'latest'

    form.p6_test_panel_enabled = p6.panel_enabled === undefined
      ? !!roomState.p6_test_panel_enabled
      : !!p6.panel_enabled
    form.p6_notebook_probe_actor = normalize_p6_probe_actor_client(
      p6.notebook_probe_actor || roomState.p6_notebook_probe_actor || 'off',
      'off'
    )

    form.workspace_id = String(roomState.workspace_id || '').trim()
    form.workspace_name = String(roomState.workspace_name || '').trim()
    form.focus_root = normalize_focus_root_client(roomState.focus_root || '')
    form.focus_label = String(roomState.focus_label || '').trim()
    form.apply_after_save = true

    const inferredProvider = infer_provider_from_model_id(form.supervisor_model)
    if (inferredProvider === 'anthropic' || inferredProvider === 'openai') {
      form.supervisor_provider = inferredProvider
    }

    sync_room_join_key_from_store()
    sync_federation_joined_members_from_store()
    reset_federation_state()
    sync_room_join_key_from_store({ preserve_if_empty: true })
    sync_federation_joined_members_from_store({ preserve_if_empty: true })

    sanitize_role_state_against_current_roles()
    sync_workspace_identity_from_selection()
    sync_room_mcp_publication_ui_fallback()
  }

  const {
    dispatch_toast,
    build_workspace_context_detail,
    apply_context_to_sidebar,
    clear_focus_root_only,
    clear_workspace_context_all,
  } = use_room_settings_workspace_binding({
    form,
    busy,
    room_id_value,
    callTool,
    room_store,
    normalize_focus_root_client,
    fill_form_from_store,
  })

  const {
    room_mcp_publication,
    room_mcp_share_ref_preview,
    room_mcp_share_ref_loading,
    room_mcp_share_ref_error,
    room_mcp_share_ref_last_issued_at,
    room_mcp_share_ref_status,
    room_mcp_grants,
    room_mcp_grants_loading,
    room_mcp_grants_status,
    room_mcp_grant_revoke_loading_id,
    reset_room_mcp_publication_state,
    reset_room_mcp_share_ref_state,
    reset_room_mcp_grants_state,
    sync_room_mcp_publication_ui_fallback,
    load_room_mcp_publication,
    handle_room_mcp_grant_list_refresh,
    handle_room_mcp_share_ref_generate,
    handle_room_mcp_share_ref_copy,
    handle_room_mcp_grant_revoke,
    refresh_room_mcp_owner_state,
  } = use_room_settings_room_mcp({
    form,
    room_id_value,
    call_room_tool,
    dispatch_toast,
    safe_string,
    safe_array,
    safe_object,
    assert_tool_success,
    pick_first_tool_result,
    normalize_reply_mode_client,
  })

  const {
    external_mcp_publish_status,
    external_mcp_publish_record,
    external_mcp_publish_state,
    external_mcp_publish_loading,
    external_mcp_publish_error,
    external_mcp_publish_plaintext_token,
    external_mcp_publish_last_config_kind,
    external_mcp_publish_last_config_text,
    external_mcp_publish_copy_loading_kind,
    external_mcp_publish_enable_loading,
    external_mcp_publish_revoke_loading,
    external_mcp_publish_regenerate_loading,
    external_mcp_publish_expires_in_days,
    external_mcp_publish_client_label,
    external_mcp_publish_endpoint_url,
    reset_external_mcp_publish_state,
    load_external_mcp_publish,
    refresh_external_mcp_publish,
    handle_external_mcp_publish_enable,
    handle_external_mcp_publish_revoke,
    handle_external_mcp_publish_regenerate,
    handle_external_mcp_publish_copy_config,
    handle_external_mcp_publish_copy_token,
    resolve_external_mcp_publish_config_text,
  } = use_room_settings_external_mcp_publish({
    room_id_value,
    call_room_tool,
    dispatch_toast,
    safe_string,
    safe_array,
    safe_object,
    assert_tool_success,
    pick_first_tool_result,
  })

  const {
    open_room_settings_form,
  } = use_room_settings_form_opening({
    props,
    callTool,
    room_store,
    room_id_value,
    form,
    show_federation_section,
    can_manage_federation,
    can_issue_federation_invite,
    workspace_options_error,
    supervisor_skills_error,
    supervisor_skills_result,
    current_room_join_key,
    reset_federation_state,
    apply_p6_test_control_to_room_store,
    read_p6_test_control_session,
    fill_form_from_store,
    load_workspace_options,
    hydrate_workspace_snapshot_for_form,
    refresh_supervisor_skills,
    ensure_room_join_key,
    refresh_federation_peers,
    refresh_federation_room_invites,
    refresh_federation_joined_members,
  })

  const {
    submit_save: submit_save_inner,
  } = use_room_settings_form_submit({
    t,
    form,
    busy,
    room_id_value,
    can_edit_room_state,
    call_room_tool,
    callTool,
    room_store,
    dispatch_toast,
    build_workspace_context_detail,
    apply_p6_test_control_to_room_store,
    write_p6_test_control_session,
    sync_room_join_key_from_store,
    refresh_supervisor_skills,
    normalize_role_ids,
    normalize_skill_ids_client,
    normalize_supervisor_skill_strategy_client,
    normalize_reply_mode_client,
    normalize_worker_concurrency_client,
    normalize_supervisor_provider_client,
    normalize_optional_number_string,
    normalize_step_budget_total_client,
    normalize_fs_read_scope_client,
    normalize_relative_path_client,
    normalize_filename_client,
    normalize_p6_probe_actor_client,
    assert_tool_success,
  })

  async function submit_save(options = {}) {
    const { on_success } = safe_object(options)

    await submit_save_inner()

    if (safe_string(room_id_value.value).trim()) {
      await refresh_room_mcp_owner_state({ silent: true })
      await load_external_mcp_publish({ silent: true })
    }

    if (typeof on_success === 'function') {
      on_success()
    }
  }

  const {
    workspace_options_for_select,
    selected_workspace_display_name,
    normalized_workspace_id_preview,
    normalized_focus_root_preview,
    enabled_supervisor_skill_count,
    role_label,
    default_role_label,
    show_supervisor_settings,
    reply_mode_supervisor_warning,
    reply_mode_supervisor_direct_warning,
    reply_mode_direct_role_warning,
    worker_concurrency_value,
    orchestration_summary,
  } = use_room_settings_form_derived({
    t,
    form,
    roles,
    workspace_options,
    safe_array,
    safe_string,
    normalize_focus_root_client,
    normalize_skill_ids_client,
    normalize_supervisor_skill_strategy_client,
    normalize_worker_concurrency_client,
  })

  watch(
    () => props.visible,
    async (visible) => {
      if (!visible) return

      await open_room_settings_form()

      if (!safe_string(room_id_value.value).trim()) return

      await refresh_room_mcp_owner_state({ silent: true })
      await load_external_mcp_publish({ silent: true })
    },
    { immediate: true }
  )

  watch(
    () => roles.value,
    () => {
      sanitize_role_state_against_current_roles()
    },
    { deep: true }
  )

  watch(
    () => form.reply_mode,
    (value) => {
      const normalized = normalize_reply_mode_client(value)
      if (normalized !== value) {
        form.reply_mode = normalized
        return
      }

      if (normalized === 'supervisor' || normalized === 'supervisor_direct') {
        form.supervisor_enabled = true
        form.supervisor_provider = normalize_supervisor_provider_client(form.supervisor_provider)
      }
    }
  )

  watch(
    () => form.supervisor_enabled,
    (enabled) => {
      if (!enabled && (form.reply_mode === 'supervisor' || form.reply_mode === 'supervisor_direct')) {
        form.reply_mode = 'manual'
      }
    }
  )

  watch(
    () => form.max_worker_concurrency,
    (value) => {
      const normalized = normalize_worker_concurrency_client(value)
      if (normalized !== value) {
        form.max_worker_concurrency = normalized
      }
    },
    { immediate: true }
  )

  watch(
    () => [
      !!form.shared_room_config_enabled,
      normalize_reply_mode_client(form.reply_mode, 'manual'),
      safe_string(form.default_reply_role_id).trim(),
      JSON.stringify(normalize_role_ids(form.active_roles)),
      !!form.shared_sync_from_reply_mode,
    ],
    () => {
      sync_shared_mapping_from_current_reply_config()
      sync_room_mcp_publication_ui_fallback()
    },
    { immediate: true }
  )

  watch(
    () => [
      !!form.room_mcp_provider_enabled,
      safe_string(form.room_mcp_provider_name).trim(),
      safe_string(form.room_mcp_provider_summary).trim(),
    ],
    () => {
      sync_room_mcp_publication_ui_fallback()
    },
    { immediate: true }
  )

  watch(
    () => form.supervisor_model,
    (value) => {
      const inferred = infer_provider_from_model_id(value)
      if (inferred === 'anthropic' || inferred === 'openai') {
        form.supervisor_provider = inferred
      }
    }
  )

  watch(
    () => [room_id_value.value, form.p6_test_panel_enabled, form.p6_notebook_probe_actor],
    ([roomId, panelEnabled, probeActor]) => {
      write_p6_test_control_session(roomId, {
        panel_enabled: !!panelEnabled,
        notebook_probe_actor: normalize_p6_probe_actor_client(probeActor, 'off'),
      })
    },
    { immediate: true }
  )

  watch(
    () => room_id_value.value,
    async () => {
      sync_room_join_key_from_store()
      sync_federation_joined_members_from_store()
      reset_federation_state()
      sync_room_join_key_from_store({ preserve_if_empty: true })
      sync_federation_joined_members_from_store({ preserve_if_empty: true })

      if (!props.visible) return
      if (!safe_string(room_id_value.value).trim()) return

      if (show_federation_section.value) {
        try {
          await refresh_federation_joined_members()
        } catch {
          // noop
        }
      }

      if (can_manage_federation.value) {
        try {
          await refresh_federation_peers()
        } catch {
          // noop
        }
        try {
          await refresh_federation_room_invites()
        } catch {
          // noop
        }
      }

      await refresh_room_mcp_owner_state({ silent: true })
      await load_external_mcp_publish({ silent: true })
    }
  )

  return {
    busy,
    form,
    room_id_value,
    roles,

    current_user_id_value,
    room_owner_user_id_value,
    room_member_role_value,
    owner_resolution_state,
    is_room_owner,
    is_explicit_member_readonly,
    can_edit_room_state,
    can_manage_room_roles,
    show_federation_section,
    can_manage_federation,
    can_issue_federation_invite,

    shared_role_ids_set,
    is_supervisor_shared,

    current_room_join_key,
    federation_peers,
    federation_peers_loading,
    federation_target_peer_id,
    federation_invite_ttl_seconds,
    federation_invite_ttl_options,
    federation_invite_history_filter,
    federation_invite_history_filter_options,
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
    federation_summary_counts,
    federation_summary_notes,
    set_federation_invite_history_filter,
    refresh_federation_room_invites,
    refresh_federation_joined_members,
    revoke_federation_room_invite,
    revoke_federated_member_access,
    extend_federation_room_invite,
    refresh_federation_peers,
    issue_federation_room_invite,

    supervisor_fs_audit,
    supervisor_notebook_audit,
    fs_tool_call_count,
    fs_tool_result_count,
    notebook_tool_call_count,
    notebook_tool_result_count,
    normalized_workspace_id_preview,
    normalized_focus_root_preview,
    default_role_label,
    show_supervisor_settings,
    reply_mode_supervisor_warning,
    reply_mode_supervisor_direct_warning,
    reply_mode_direct_role_warning,
    worker_concurrency_value,
    orchestration_summary,

    room_mcp_publication,

    room_mcp_share_ref_preview,
    room_mcp_share_ref_loading,
    room_mcp_share_ref_error,
    room_mcp_share_ref_last_issued_at,
    room_mcp_share_ref_status,

    room_mcp_grants,
    room_mcp_grants_loading,
    room_mcp_grants_status,
    room_mcp_grant_revoke_loading_id,

    external_mcp_publish_status,
    external_mcp_publish_record,
    external_mcp_publish_state,
    external_mcp_publish_loading,
    external_mcp_publish_error,
    external_mcp_publish_plaintext_token,
    external_mcp_publish_last_config_kind,
    external_mcp_publish_last_config_text,
    external_mcp_publish_copy_loading_kind,
    external_mcp_publish_enable_loading,
    external_mcp_publish_revoke_loading,
    external_mcp_publish_regenerate_loading,
    external_mcp_publish_expires_in_days,
    external_mcp_publish_client_label,
    external_mcp_publish_endpoint_url,

    reset_external_mcp_publish_state,
    load_external_mcp_publish,
    refresh_external_mcp_publish,
    handle_external_mcp_publish_enable,
    handle_external_mcp_publish_revoke,
    handle_external_mcp_publish_regenerate,
    handle_external_mcp_publish_copy_config,
    handle_external_mcp_publish_copy_token,
    resolve_external_mcp_publish_config_text,

    handle_room_mcp_share_ref_generate,
    handle_room_mcp_share_ref_copy,
    handle_room_mcp_grant_list_refresh,
    handle_room_mcp_grant_revoke,

    role_label,
    is_role_active,
    set_default_role,
    handle_default_role_change,
    handle_reply_mode_change,
    handle_supervisor_provider_change,
    toggle_active_role,
    select_all_roles,
    clear_active_roles,
    keep_only_default_role,

    workspace_options: workspace_options_for_select,
    workspace_options_loading,
    workspace_focus_loading,
    workspace_options_error,
    selected_workspace_display_name,
    handle_workspace_selection_change,
    apply_context_to_sidebar,
    clear_focus_root_only,
    clear_workspace_context_all,

    supervisor_skills_loading,
    supervisor_skills_error,
    supervisor_skills_result,
    enabled_supervisor_skill_count,
    refresh_supervisor_skills,
    toggle_supervisor_skill,
    is_supervisor_skill_enabled_locally,
    get_saved_supervisor_skill_enabled,

    submit_save,
  }
}

