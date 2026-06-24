const FS_READ_TOOLS = new Set([
  'nisb_file_read',
  'nisb_dir_list',
  'nisb_dir_tree',
  'nisb_fs_snapshot',
  'nisb_fs_trash_list',
  'nisb_file_list_allowed_directories'
])

const FS_WRITE_TOOLS = new Set([
  'nisb_file_create',
  'nisb_file_update',
  'nisb_file_write_base64',
  'nisb_file_write_base64_chunk',
  'nisb_file_delete',
  'nisb_dir_create',
  'nisb_dir_delete',
  'nisb_file_move_path',
  'nisb_dir_move_path',
  'nisb_file_rename',
  'nisb_fs_bulk_restore',
  'nisb_fs_trash_restore'
])

const FS_DANGEROUS_TOOLS = new Set([
  'nisb_dir_delete_recursive',
  'nisb_fs_bulk_delete'
])

const FS_TOOLS = new Set([
  ...FS_READ_TOOLS,
  ...FS_WRITE_TOOLS,
  ...FS_DANGEROUS_TOOLS
])

const DEFAULT_FS_READ_SCOPE = 'user_ro'
const DEFAULT_FS_WRITE_SCOPE = 'agent_files'
const DEFAULT_FS_DANGEROUS_ENABLED = false
const DEFAULT_UI_LOCALE = 'en'

let fsGateDefaultsEnsured = false

function getUserId() {
  return localStorage.getItem('nisb_user_id') || 'nisb_default_user'
}

function _ls_get_first(keys, fallback = '') {
  for (const k of keys) {
    try {
      const v = localStorage.getItem(k)
      if (v !== null && String(v).trim() !== '') return String(v)
    } catch {}
  }
  return String(fallback || '')
}

function _ls_set_safe(key, value) {
  try {
    localStorage.setItem(String(key || ''), String(value ?? ''))
  } catch {}
}

function _ls_set_all_safe(keys, value) {
  for (const k of keys) _ls_set_safe(k, value)
}

function normalizeUiLocale(value) {
  const raw = String(value || '').trim().replace('_', '-')
  const lowered = raw.toLowerCase()

  if (lowered === 'zh' || lowered === 'zh-cn' || lowered === 'zh-hans') return 'zh-CN'
  if (lowered.startsWith('zh-')) return 'zh-CN'
  if (lowered === 'en' || lowered === 'en-us' || lowered === 'en-gb') return 'en'
  if (lowered.startsWith('en-')) return 'en'

  return DEFAULT_UI_LOCALE
}

function getCurrentUiLocale() {
  const fromWindow = (() => {
    try {
      const direct =
        window?.__nisb_locale ||
        window?.__nisb_ui_locale ||
        window?.__NISB_LOCALE__ ||
        window?.__NISB_UI_LOCALE__
      if (direct) return String(direct)
    } catch {}
    return ''
  })()

  const fromDocument = (() => {
    try {
      return document?.documentElement?.getAttribute('lang') || ''
    } catch {
      return ''
    }
  })()

  const fromStorage = _ls_get_first(
    [
      'nisb_locale',
      'nisb_ui_locale',
      'nisb_language',
      'nisb_settings_locale',
      'locale',
      'ui_locale',
      'language'
    ],
    ''
  )

  return normalizeUiLocale(fromWindow || fromStorage || fromDocument || DEFAULT_UI_LOCALE)
}

function shouldInjectLocale(tool) {
  const name = String(tool || '').trim()
  return name.startsWith('nisb_')
}

function normalizeFsReadScope(v) {
  const s = String(v || DEFAULT_FS_READ_SCOPE).trim().toLowerCase()
  if (s === 'minimal') return 'minimal'
  return 'user_ro'
}

function normalizeFsWriteScope(v) {
  const s = String(v ?? '').trim().toLowerCase()
  if (!s) return DEFAULT_FS_WRITE_SCOPE
  if (s === 'agent_files' || s === 'agentfiles') return 'agent_files'
  if (s === 'none') return 'none'
  return DEFAULT_FS_WRITE_SCOPE
}

function normalizeFsDangerousEnabled(v) {
  if (typeof v === 'boolean') return v
  const s = String(v || '').trim().toLowerCase()
  return s === 'true' || s === '1' || s === 'yes' || s === 'on'
}

function _ls_get_first_bool(keys, fallback = false) {
  const raw = _ls_get_first(keys, '')
  if (!raw) return !!fallback
  return normalizeFsDangerousEnabled(raw)
}

function _get_stored_fs_write_scope() {
  const raw = _ls_get_first(['nisb_mcp_fs_write_scope', 'nisbmcpfswritescope'], '')
  const userSet = _ls_get_first_bool(
    ['nisb_mcp_fs_write_scope_user_set', 'nisbmcpfswritescopeuserset'],
    false
  )

  const normalized = normalizeFsWriteScope(raw)

  if (!raw) return DEFAULT_FS_WRITE_SCOPE
  if (!userSet && normalized === 'none') return DEFAULT_FS_WRITE_SCOPE

  return normalized
}

export function ensureFsCapabilityGateDefaults() {
  if (fsGateDefaultsEnsured) return
  fsGateDefaultsEnsured = true

  const fsReadScope = normalizeFsReadScope(
    _ls_get_first(['nisb_mcp_fs_read_scope', 'nisbmcpfsreadscope'], DEFAULT_FS_READ_SCOPE)
  )
  const fsWriteScope = _get_stored_fs_write_scope()
  const fsDangerousEnabled =
    fsWriteScope === 'none'
      ? false
      : normalizeFsDangerousEnabled(
        _ls_get_first(
          ['nisb_mcp_fs_dangerous_enabled', 'nisbmcpfsdangerousenabled'],
          String(DEFAULT_FS_DANGEROUS_ENABLED)
        )
      )

  _ls_set_all_safe(['nisb_mcp_fs_read_scope', 'nisbmcpfsreadscope'], fsReadScope)
  _ls_set_all_safe(['nisb_mcp_fs_write_scope', 'nisbmcpfswritescope'], fsWriteScope)
  _ls_set_all_safe(['nisb_mcp_fs_dangerous_enabled', 'nisbmcpfsdangerousenabled'], String(fsDangerousEnabled))

  if (fsWriteScope !== 'none') {
    _ls_set_all_safe(['nisb_mcp_fs_write_scope_user_set', 'nisbmcpfswritescopeuserset'], 'false')
  }
}

function _norm_rel_path(p) {
  let s = String(p || '').trim()
  if (!s) return ''
  s = s.replace(/\\/g, '/')
  while (s.startsWith('/')) s = s.slice(1)
  s = s.replace(/\/+/g, '/')
  if (s === '.' || s === './') return ''
  return s
}

function _as_agent_files_rel(p) {
  const rel = _norm_rel_path(p)
  if (!rel) return ''
  if (rel === 'agent_files') return 'agent_files'
  if (rel.startsWith('agent_files/')) return rel
  if (rel === 'storage' || rel.startsWith('storage/')) return rel
  return `agent_files/${rel}`
}

function _dirname_agent_rel(p) {
  const rel = _as_agent_files_rel(p)
  if (!rel) return ''
  const parts = rel.split('/').filter(Boolean)
  if (parts.length <= 1) return rel || 'agent_files'
  parts.pop()
  return parts.join('/') || 'agent_files'
}

function _get_current_workspace_id() {
  return _ls_get_first(
    ['nisb_current_workspace', 'nisb_current_workspace_id', 'nisb_workspace_id'],
    'workspace_work'
  )
}

function _get_workspace_focus_root_from_local_storage() {
  const ws = _get_current_workspace_id()
  const raw = _ls_get_first(
    [
      `nisb_fs_focus_root_${ws}`,
      `nisb_fs_focused_root_${ws}`,
      'nisb_fs_focus_root'
    ],
    ''
  )
  return raw ? _as_agent_files_rel(raw) : ''
}

function _is_fs_tool(tool) {
  return FS_TOOLS.has(String(tool || '').trim())
}

function _is_fs_read_tool(tool) {
  return FS_READ_TOOLS.has(String(tool || '').trim())
}

function _is_fs_write_tool(tool) {
  return FS_WRITE_TOOLS.has(String(tool || '').trim())
}

function _is_fs_dangerous_tool(tool) {
  return FS_DANGEROUS_TOOLS.has(String(tool || '').trim())
}

function _is_move_path_tool(tool) {
  const name = String(tool || '').trim()
  return name === 'nisb_file_move_path' || name === 'nisb_dir_move_path'
}

function _is_rename_path_tool(tool) {
  return String(tool || '').trim() === 'nisb_file_rename'
}

function _push_path_candidate(out, v) {
  if (!v) return

  if (typeof v === 'string') {
    const s = String(v).trim()
    if (s) out.push(s)
    return
  }

  if (Array.isArray(v)) {
    for (const item of v) _push_path_candidate(out, item)
    return
  }

  if (typeof v === 'object') {
    const maybeKeys = [
      'path',
      'file_path',
      'filepath',
      'filename',
      'target_path',
      'target',
      'dst_path',
      'dest_path',
      'destination_path',
      'dest_dir',
      'destination_dir',
      'target_dir',
      'new_dir',
      'parent_path',
      'new_path',
      'old_path',
      'src_path',
      'source_path',
      'dir_path',
      'directory_path'
    ]
    for (const k of maybeKeys) {
      const val = v?.[k]
      if (typeof val === 'string' && val.trim()) out.push(val)
    }
  }
}

function _dedupe_nonempty_strings(list = []) {
  const seen = new Set()
  const out = []
  for (const raw of list) {
    const s = String(raw || '').trim()
    if (!s || seen.has(s)) continue
    seen.add(s)
    out.push(s)
  }
  return out
}

function _extract_path_candidates(args = {}) {
  const out = []

  const keys = [
    'path',
    'file_path',
    'filepath',
    'filename',
    'target_path',
    'target',
    'dst_path',
    'dest_path',
    'destination_path',
    'dest_dir',
    'destination_dir',
    'target_dir',
    'new_dir',
    'parent_path',
    'new_path',
    'old_path',
    'src_path',
    'source_path',
    'dir_path',
    'directory_path',
    'from_path',
    'to_path'
  ]

  for (const k of keys) _push_path_candidate(out, args?.[k])

  if (args?.patch && typeof args.patch === 'object') {
    for (const k of keys) _push_path_candidate(out, args.patch?.[k])
  }

  _push_path_candidate(out, args?.paths)
  _push_path_candidate(out, args?.files)
  _push_path_candidate(out, args?.items)
  _push_path_candidate(out, args?.targets)

  return _dedupe_nonempty_strings(out)
}

function _common_ancestor_agent_rel(paths = []) {
  const roots = _dedupe_nonempty_strings(
    paths
      .map((p) => _dirname_agent_rel(p))
      .filter(Boolean)
      .filter((p) => p !== 'storage' && !String(p).startsWith('storage/'))
  )

  if (!roots.length) return ''

  const splitRoots = roots.map((p) => String(p).split('/').filter(Boolean))
  const minLen = Math.min(...splitRoots.map((parts) => parts.length))
  const common = []

  for (let i = 0; i < minLen; i++) {
    const token = splitRoots[0][i]
    if (splitRoots.every((parts) => parts[i] === token)) common.push(token)
    else break
  }

  return common.join('/') || ''
}

function _common_ancestor_from_roots(roots = []) {
  const cleanRoots = _dedupe_nonempty_strings(
    roots
      .map((p) => _as_agent_files_rel(p))
      .filter(Boolean)
      .filter((p) => p !== 'storage' && !String(p).startsWith('storage/'))
  )

  if (!cleanRoots.length) return ''

  const splitRoots = cleanRoots.map((p) => String(p).split('/').filter(Boolean))
  const minLen = Math.min(...splitRoots.map((parts) => parts.length))
  const common = []

  for (let i = 0; i < minLen; i++) {
    const token = splitRoots[0][i]
    if (splitRoots.every((parts) => parts[i] === token)) common.push(token)
    else break
  }

  return common.join('/') || ''
}

function _push_focus_root_from_file(out, p) {
  const root = _dirname_agent_rel(p)
  if (root) out.push(root)
}

function _push_focus_root_from_dir(out, p) {
  const root = _as_agent_files_rel(p)
  if (root) out.push(root)
}

function _resolve_path_focus_root(args = {}) {
  const candidates = _extract_path_candidates(args)
  if (!candidates.length) return ''
  return _common_ancestor_agent_rel(candidates)
}

function _resolve_move_focus_root(args = {}) {
  const roots = []

  _push_focus_root_from_file(roots, args?.old_path)
  _push_focus_root_from_file(roots, args?.src_path)
  _push_focus_root_from_file(roots, args?.source_path)
  _push_focus_root_from_file(roots, args?.from_path)

  _push_focus_root_from_file(roots, args?.new_path)
  _push_focus_root_from_file(roots, args?.dst_path)
  _push_focus_root_from_file(roots, args?.dest_path)
  _push_focus_root_from_file(roots, args?.destination_path)
  _push_focus_root_from_file(roots, args?.to_path)

  _push_focus_root_from_dir(roots, args?.dest_dir)
  _push_focus_root_from_dir(roots, args?.destination_dir)
  _push_focus_root_from_dir(roots, args?.target_dir)
  _push_focus_root_from_dir(roots, args?.new_dir)

  _push_path_candidate(roots, args?.paths)
  _push_path_candidate(roots, args?.files)
  _push_path_candidate(roots, args?.items)
  _push_path_candidate(roots, args?.targets)

  const normalizedRoots = roots.map((p) => {
    const rel = _as_agent_files_rel(p)
    if (!rel) return ''
    if (String(p || '').includes('.') || rel.split('/').pop()?.includes('.')) return _dirname_agent_rel(rel)
    return rel
  })

  return _common_ancestor_from_roots(normalizedRoots)
}

function _resolve_rename_focus_root(args = {}) {
  return _dirname_agent_rel(args?.old_path || args?.filename || args?.path || '')
}

function _resolve_path_focus_root_for_tool(tool, args = {}) {
  if (_is_move_path_tool(tool)) {
    return _resolve_move_focus_root(args) || _resolve_path_focus_root(args)
  }

  if (_is_rename_path_tool(tool)) {
    return _resolve_rename_focus_root(args) || _resolve_path_focus_root(args)
  }

  return _resolve_path_focus_root(args)
}

function _get_base_capability_gate_snapshot() {
  ensureFsCapabilityGateDefaults()

  const fs_read_scope = normalizeFsReadScope(
    _ls_get_first(['nisb_mcp_fs_read_scope', 'nisbmcpfsreadscope'], DEFAULT_FS_READ_SCOPE)
  )
  const fs_write_scope = _get_stored_fs_write_scope()
  const fs_dangerous_enabled =
    fs_write_scope === 'none'
      ? false
      : normalizeFsDangerousEnabled(
        _ls_get_first(
          ['nisb_mcp_fs_dangerous_enabled', 'nisbmcpfsdangerousenabled'],
          String(DEFAULT_FS_DANGEROUS_ENABLED)
        )
      )

  return {
    policy_version: 1,
    workspace_id: _get_current_workspace_id(),
    focus_root: '',
    fs_read_scope,
    fs_write_scope,
    fs_dangerous_enabled
  }
}

function _build_capability_gate_for_tool(tool, args = {}, opts = {}) {
  if (!_is_fs_tool(tool)) return null

  const gate = _get_base_capability_gate_snapshot()
  const toolName = String(tool || '').trim()

  const explicitMode = String(
    opts.capability_gate_mode || args._capability_gate_mode || ''
  ).trim()

  const explicitFocusRootRaw =
    opts.capability_focus_root ||
    args._capability_focus_root ||
    ''

  const explicitFocusRoot = explicitFocusRootRaw
    ? _as_agent_files_rel(explicitFocusRootRaw)
    : ''

  const workspaceFocusRoot = _get_workspace_focus_root_from_local_storage()
  const pathFocusRoot = _resolve_path_focus_root_for_tool(toolName, args)

  let focus_root = ''

  if (_is_move_path_tool(toolName) || _is_rename_path_tool(toolName)) {
    focus_root = pathFocusRoot || explicitFocusRoot || workspaceFocusRoot
  } else if (explicitFocusRoot) {
    focus_root = explicitFocusRoot
  } else if (explicitMode === 'none') {
    focus_root = ''
  } else if (explicitMode === 'path') {
    focus_root = pathFocusRoot
  } else if (explicitMode === 'workspace') {
    focus_root = workspaceFocusRoot
  } else if (explicitMode === 'path_or_workspace') {
    focus_root = pathFocusRoot || workspaceFocusRoot
  } else if (toolName === 'nisb_file_create' || toolName === 'nisb_file_update') {
    focus_root = pathFocusRoot || ''
  } else if (_is_fs_dangerous_tool(toolName)) {
    focus_root = pathFocusRoot || workspaceFocusRoot
  } else if (_is_fs_write_tool(toolName)) {
    focus_root = pathFocusRoot || workspaceFocusRoot
  } else if (_is_fs_read_tool(toolName)) {
    focus_root = workspaceFocusRoot
  } else {
    focus_root = workspaceFocusRoot
  }

  gate.focus_root = focus_root || ''
  gate.fs_read_scope = normalizeFsReadScope(gate.fs_read_scope)
  gate.fs_write_scope = normalizeFsWriteScope(gate.fs_write_scope)
  gate.fs_dangerous_enabled = normalizeFsDangerousEnabled(gate.fs_dangerous_enabled)
  return gate
}

function _is_plain_object(v) {
  return v && typeof v === 'object' && !Array.isArray(v)
}

function _normalize_existing_capability_gate(raw = {}) {
  if (!_is_plain_object(raw)) return null

  const focusRoot = raw.focus_root ? _as_agent_files_rel(raw.focus_root) : ''

  return {
    policy_version: Number(raw.policy_version || 1) || 1,
    workspace_id: String(raw.workspace_id || _get_current_workspace_id()).trim() || _get_current_workspace_id(),
    focus_root: focusRoot,
    fs_read_scope: normalizeFsReadScope(raw.fs_read_scope),
    fs_write_scope: normalizeFsWriteScope(raw.fs_write_scope),
    fs_dangerous_enabled: normalizeFsDangerousEnabled(raw.fs_dangerous_enabled)
  }
}

function _merge_capability_gate_for_send(injectedGate, callerGate, tool = '') {
  const base = _normalize_existing_capability_gate(injectedGate) || null
  const caller = _normalize_existing_capability_gate(callerGate) || null
  const toolName = String(tool || '').trim()
  const baseFocusWins =
    !!base?.focus_root &&
    (_is_fs_write_tool(toolName) || _is_fs_dangerous_tool(toolName) || _is_move_path_tool(toolName) || _is_rename_path_tool(toolName))

  if (!base && !caller) return null
  if (!caller) return base
  if (!base) return caller

  const callerWriteScope = normalizeFsWriteScope(caller.fs_write_scope)
  const baseWriteScope = normalizeFsWriteScope(base.fs_write_scope)
  const fsWriteScope =
    callerWriteScope === 'none' && baseWriteScope !== 'none'
      ? baseWriteScope
      : callerWriteScope || baseWriteScope || DEFAULT_FS_WRITE_SCOPE

  return {
    ...base,
    ...caller,
    policy_version: Number(caller.policy_version || base.policy_version || 1) || 1,
    workspace_id: String(caller.workspace_id || base.workspace_id || _get_current_workspace_id()).trim() || _get_current_workspace_id(),
    focus_root: baseFocusWins ? base.focus_root : (caller.focus_root || base.focus_root || ''),
    fs_read_scope: caller.fs_read_scope || base.fs_read_scope || DEFAULT_FS_READ_SCOPE,
    fs_write_scope: fsWriteScope,
    fs_dangerous_enabled: !!caller.fs_dangerous_enabled || !!base.fs_dangerous_enabled
  }
}

function getInjectedArgs(tool, args = {}, opts = {}) {
  const uid = getUserId()
  const user_base_path = `/data/users/${uid}`

  const injected = {
    user_id: uid,
    base_path: user_base_path
  }

  if (shouldInjectLocale(tool)) {
    injected.locale = getCurrentUiLocale()
  }

  const gate = _build_capability_gate_for_tool(tool, args, opts)
  if (gate) injected.capability_gate = gate

  return injected
}

export function mergeMcpToolArgs(tool, args = {}, opts = {}) {
  const safeArgs = _is_plain_object(args) ? args : {}
  const injected = getInjectedArgs(tool, safeArgs, opts)
  const callerGate = _is_plain_object(safeArgs.capability_gate) ? safeArgs.capability_gate : null
  const mergedGate = _merge_capability_gate_for_send(injected.capability_gate, callerGate, tool)

  const merged = { ...safeArgs }

  delete merged.user_id
  delete merged.base_path
  delete merged.capability_gate
  delete merged._capability_gate_mode
  delete merged._capability_focus_root

  merged.user_id = injected.user_id
  merged.base_path = injected.base_path

  if (!String(merged.locale || '').trim() && String(injected.locale || '').trim()) {
    merged.locale = injected.locale
  }

  if (mergedGate) {
    merged.capability_gate = mergedGate
  }

  return merged
}
