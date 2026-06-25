<template>
  <div v-if="open" class="nisb-modal-mask" @click.self="emit_close">
    <div
      class="nisb-modal nisb-modal-wide"
      role="dialog"
      aria-modal="true"
      :aria-label="t('settings.title')"
    >
      <div class="nisb-modal-header">
        <div class="nisb-modal-title">{{ t('settings.title') }}</div>

        <div class="settings-tabs" role="tablist" :aria-label="t('settings.tabs.ariaLabel')">
          <button
            class="tab"
            :class="{ active: tab === 'models' }"
            :aria-selected="tab === 'models'"
            @click="open_models_tab"
            role="tab"
            type="button"
          >
            {{ t('settings.tabs.models') }}
          </button>

          <button
            class="tab"
            :class="{ active: tab === 'performance' }"
            :aria-selected="tab === 'performance'"
            @click="tab = 'performance'"
            role="tab"
            type="button"
          >
            {{ t('settings.tabs.performance') }}
          </button>

          <button
            class="tab"
            :class="{ active: tab === 'files' }"
            :aria-selected="tab === 'files'"
            @click="tab = 'files'"
            role="tab"
            type="button"
          >
            {{ t('settings.tabs.files') }}
          </button>

          <button
            class="tab"
            :class="{ active: tab === 'language' }"
            :aria-selected="tab === 'language'"
            @click="tab = 'language'"
            role="tab"
            type="button"
          >
            {{ t('settings.tabs.language') }}
          </button>

          <button
            class="tab"
            :class="{ active: tab === 'about' }"
            :aria-selected="tab === 'about'"
            @click="tab = 'about'"
            role="tab"
            type="button"
          >
            {{ t('settings.tabs.about') }}
          </button>
        </div>
      </div>

      <div class="nisb-modal-body">
        <SettingsModelsSection
          v-if="tab === 'models'"
          :busy="busy"
          :model-catalog-loading="model_catalog_loading"
          :model-catalog-error="model_catalog_error"
          :model-groups="model_groups"
          v-model:conversation-model="conversation_model"
          v-model:query-translate-model="query_translate_model"
          @load-model-catalog="load_model_catalog"
          @save="save"
          @reset="reset"
        />

        <SettingsPerformanceSection
          v-else-if="tab === 'performance'"
          v-model:local_evidence_sync="local_evidence_sync"
          v-model:local_evidence_auto_select="local_evidence_auto_select"
          @save="save"
          @reset="reset"
        />

        <SettingsFilesSection
          v-else-if="tab === 'files'"
          :busy="busy"
          :workspaces="workspaces"
          :icon-choices="ICON_CHOICES"
          :workspace-id-safe="workspace_id_safe"
          :is-default-workspace="is_default_workspace"
          :saved-favorites-count="saved_favorites_count"
          :saved-favorites-preview="saved_favorites_preview"
          :local-favorites-cleared="local_favorites_cleared"
          v-model:selected-workspace-id="selected_workspace_id"
          v-model:new-ws-icon="new_ws_icon"
          v-model:new-ws-name="new_ws_name"
          v-model:rename-ws-icon="rename_ws_icon"
          v-model:rename-ws-name="rename_ws_name"
          v-model:saved-focused-preview="saved_focused_preview"
          @load-workspaces="load_workspaces"
          @workspace-select-changed="on_workspace_select_changed"
          @rename-workspace="rename_workspace"
          @delete-workspace="delete_workspace"
          @create-workspace="create_workspace"
          @refresh-workspace-files-state="refresh_workspace_files_state"
          @copy-current-favorites-internal-links="copy_current_favorites_internal_links"
          @read-focus-from-local="read_focus_from_local"
          @apply-workspace-files-state-to-ui="apply_workspace_files_state_to_ui"
          @save-workspace-snapshot-from-current="save_workspace_snapshot_from_current"
          @clear-workspace-favorites-local="clear_workspace_favorites_local"
        />

        <SettingsLanguageSection v-else-if="tab === 'language'" />

        <div v-else class="settings-section">
          <div class="muted">{{ t('settings.about.placeholder') }}</div>
        </div>
      </div>

      <div class="nisb-modal-actions">
        <button class="modal-btn" type="button" @click="emit_close">
          {{ t('common.close') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { useChatConfigStore } from '../../stores/chatConfig'
import { useSettingsStore } from '../../stores/settings'
import { readLocalEvidenceSettings, writeLocalEvidenceSettings } from '../../composables/useNisbSettings'

import SettingsPerformanceSection from './SettingsPerformanceSection.vue'
import SettingsModelsSection from './Settings/SettingsModelsSection.vue'
import SettingsFilesSection from './Settings/SettingsFilesSection.vue'
import SettingsLanguageSection from './Settings/SettingsLanguageSection.vue'

const { t, locale } = useI18n()

const props = defineProps({
  open: { type: Boolean, default: false },
  workspaceId: { type: String, default: '' },
  workspaceName: { type: String, default: '' }
})

const emit = defineEmits(['close'])

const { callTool } = useMCP()
const chat_cfg = useChatConfigStore()
const settings = useSettingsStore()
if (typeof chat_cfg.hydrate === 'function') chat_cfg.hydrate()

const tab = ref('files')
const busy = ref(false)

const local_evidence_sync = ref(true)
const local_evidence_auto_select = ref(true)

const LS_QUERY_TRANSLATE_ENABLED = 'nisb_chat_query_translate_enabled'
const LS_QUERY_TRANSLATE_MODEL = 'nisb_chat_query_translate_model'
const LS_CURRENT_WORKSPACE_ID = 'nisb_current_workspace_id'

const query_translate_enabled = ref(false)
const query_translate_model = ref('gpt-4o-mini')
const conversation_model = ref(chat_cfg.models?.conversationModel || 'gpt-4o-mini')

const model_groups = ref([])
const model_catalog_loading = ref(false)
const model_catalog_error = ref('')

const workspaces = ref([])
const selected_workspace_id = ref('')

const ICON_CHOICES = ['🧩', '💼', '📚', '🎨', '🧪', '🧠', '🗂️', '📝', '📦', '🔬', '🏗️', '🚀', '🌿', '📌']
const new_ws_icon = ref('🧩')
const new_ws_name = ref('')

const rename_ws_icon = ref('🧩')
const rename_ws_name = ref('')

const saved_focused_preview = ref('')
const saved_favorites_count = ref(0)
const saved_favorites_preview = ref([])

// 本地内存态：记录当前 current.favorites（从后端读取），用于清空比对
const local_current_favorites = ref([])
// 标记用户已在本 session 内清空常用（未保存），用于 UI 提示
const local_favorites_cleared = ref(false)

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function safe_array(v) {
  return Array.isArray(v) ? v : []
}

function safe_object(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function current_locale() {
  const raw = safe_string(settings?.locale || locale?.value || 'en').trim()
  if (raw.toLowerCase().startsWith('zh')) return 'zh-CN'
  return 'en'
}

function tr(key, vars = {}) {
  const out = t(key, vars)
  return safe_string(out || key)
}

function has_cjk(text) {
  return /[\u3400-\u9fff]/.test(safe_string(text))
}

function unwrap_result(res) {
  if (res && typeof res === 'object' && res.result && typeof res.result === 'object') {
    return res.result
  }
  return res || {}
}

function localized_args(base = {}) {
  return {
    ...base,
    locale: current_locale()
  }
}

function normalized_status(data) {
  const raw = safe_string(data?.status).trim().toLowerCase()
  if (raw) return raw
  if (data?.success === false) return 'error'
  if (data?.success === true) return 'success'
  return ''
}

function is_tool_success(data) {
  const status = normalized_status(data)
  if (status) return status === 'success'
  if (data?.success === false) return false
  return true
}

function visible_error(value, fallback_key = 'workspace.operationFailed', fallback_vars = {}) {
  const data = unwrap_result(value)
  const raw = safe_string(data?.message || data?.error || data?.detail || value?.message).trim()

  if (raw && !(current_locale() !== 'zh-CN' && has_cjk(raw))) {
    return raw
  }

  return tr(fallback_key, fallback_vars)
}

function assert_tool_success(res, fallback_key = 'workspace.operationFailed', fallback_vars = {}) {
  const data = unwrap_result(res)
  if (!is_tool_success(data)) {
    throw new Error(visible_error(data, fallback_key, fallback_vars))
  }
  return data
}

function first_tool_result(data, matcher) {
  const rows = safe_array(data?.tool_results)
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    if (matcher(row)) return row
  }
  return null
}

function get_display_text(data, fallback_key = 'workspace.operationCompleted', fallback_vars = {}) {
  const raw = safe_string(data?.response || data?.message).trim()

  if (raw && !(current_locale() !== 'zh-CN' && has_cjk(raw))) {
    return raw
  }

  return tr(fallback_key, fallback_vars)
}

function is_workspace_id_safe(wid) {
  return safe_string(wid).trim().startsWith('workspace_')
}

const workspace_id_safe = computed(() => is_workspace_id_safe(selected_workspace_id.value))

const is_default_workspace = computed(() => {
  const wid = safe_string(selected_workspace_id.value).trim()
  return wid === 'workspace_work' || wid === 'workspace_study' || wid === 'workspace_creative'
})

function split_display_name(display_name) {
  const s = safe_string(display_name).trim()
  if (!s) return { icon: '', name: '' }

  const m = s.match(/^(\S+)\s+(.*)$/)
  if (!m) return { icon: '', name: s }

  const icon = safe_string(m[1]).trim()
  const name = safe_string(m[2]).trim()

  if (ICON_CHOICES.includes(icon) && name) {
    return { icon, name }
  }

  return { icon: '', name: s }
}

function normalize_provider_payload(result) {
  const providers = result?.providers && typeof result.providers === 'object' ? result.providers : {}
  return Object.keys(providers)
    .map((key) => {
      const entry = providers[key] || {}
      const models = Array.isArray(entry.models)
        ? entry.models
            .map((m) => ({
              value: safe_string(m?.value).trim(),
              label: safe_string(m?.label || m?.value).trim(),
              badge: safe_string(m?.badge).trim()
            }))
            .filter((m) => m.value)
        : []

      return {
        key,
        icon: safe_string(entry?.icon).trim(),
        name: safe_string(entry?.name || key).trim(),
        models
      }
    })
    .filter((g) => Array.isArray(g.models) && g.models.length > 0)
}

function extract_workspace_list(data) {
  const row = first_tool_result(
    data,
    (x) => x.type === 'workspace_list' && Array.isArray(x.workspaces)
  )
  if (row) return safe_array(row.workspaces)
  return safe_array(data?.workspaces)
}

function extract_workspace_info(data) {
  const row = first_tool_result(
    data,
    (x) => x.type === 'workspace_info' && x.workspace && typeof x.workspace === 'object'
  )

  const workspace =
    row?.workspace && typeof row.workspace === 'object'
      ? row.workspace
      : data?.workspace && typeof data.workspace === 'object'
        ? data.workspace
        : null

  return {
    workspace_id: safe_string(workspace?.id || data?.workspace_id).trim(),
    workspace: workspace && typeof workspace === 'object' ? workspace : {},
    state:
      row?.state && typeof row.state === 'object'
        ? row.state
        : data?.state && typeof data.state === 'object'
          ? data.state
          : {}
  }
}

function extract_workspace_files_state(data) {
  const row = first_tool_result(
    data,
    (x) => x.type === 'workspace_files_state' && x.files_state && typeof x.files_state === 'object'
  )

  if (row) {
    return {
      workspace_id: safe_string(row.workspace_id).trim(),
      files_state: safe_object(row.files_state),
      last_updated: safe_string(row.last_updated).trim(),
      migrate_stats: safe_object(row.migrate_stats)
    }
  }

  return {
    workspace_id: safe_string(data?.workspace_id).trim(),
    files_state: safe_object(data?.files_state),
    last_updated: safe_string(data?.last_updated).trim(),
    migrate_stats: safe_object(data?.migrate_stats)
  }
}

function sync_rename_fields_from_selected() {
  const wid = safe_string(selected_workspace_id.value).trim()
  const ws = safe_array(workspaces.value).find((w) => safe_string(w?.id) === wid)
  const display = safe_string(ws?.name || props.workspaceName).trim()
  const { icon, name } = split_display_name(display)

  rename_ws_icon.value = icon || '🧩'
  rename_ws_name.value = name || display || ''
}

async function load_model_catalog() {
  model_catalog_loading.value = true
  model_catalog_error.value = ''

  try {
    const data = assert_tool_success(
      await callTool('nisb_chat_models', localized_args()),
      'workspace.loadModelCatalogFailed'
    )
    model_groups.value = normalize_provider_payload(data)
  } catch (e) {
    model_catalog_error.value = visible_error(e, 'workspace.loadModelCatalogFailed')
  } finally {
    model_catalog_loading.value = false
  }
}

function open_models_tab() {
  tab.value = 'models'
  if (!model_groups.value.length && !model_catalog_loading.value) {
    load_model_catalog()
  }
}

async function load_workspaces() {
  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_list', localized_args()),
      'workspace.loadWorkspacesFailed'
    )
    workspaces.value = extract_workspace_list(data)
  } catch (e) {
    toast(tr('workspace.loadWorkspacesException', { error: visible_error(e, 'workspace.loadWorkspacesFailed') }), 'error')
  } finally {
    busy.value = false
  }

  const ids = new Set(safe_array(workspaces.value).map((w) => safe_string(w.id)))
  if (!ids.has(selected_workspace_id.value)) {
    const p = safe_string(props.workspaceId).trim()
    if (ids.has(p)) selected_workspace_id.value = p
    else if (ids.has('workspace_work')) selected_workspace_id.value = 'workspace_work'
    else selected_workspace_id.value = safe_string(workspaces.value?.[0]?.id)
  }

  sync_rename_fields_from_selected()
}

function on_workspace_select_changed() {
  const wid = safe_string(selected_workspace_id.value).trim()
  if (!is_workspace_id_safe(wid)) {
    toast(tr('workspace.invalidWorkspaceId'), 'error')
    return
  }

  sync_rename_fields_from_selected()

  window.dispatchEvent(
    new CustomEvent('nisb_workspace_switch_request', {
      detail: { workspace_id: wid }
    })
  )

  refresh_workspace_files_state()
}

async function create_workspace() {
  const name = safe_string(new_ws_name.value).trim()
  const icon = safe_string(new_ws_icon.value).trim()

  if (!name) {
    toast(tr('workspace.enterWorkspaceName'), 'info')
    return
  }

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_create', localized_args({ workspace_name: name, icon })),
      'workspace.createWorkspaceFailed'
    )

    const info = extract_workspace_info(data)
    const wid = safe_string(info.workspace_id).trim()

    if (!wid) {
      toast(tr('workspace.createWorkspaceNoId'), 'error')
      return
    }

    toast(get_display_text(data, 'workspace.workspaceCreated', { id: wid }), 'success')
    new_ws_name.value = ''

    window.dispatchEvent(new CustomEvent('nisb_workspaces_refresh', { detail: {} }))
    window.dispatchEvent(
      new CustomEvent('nisb_workspace_switch_request', {
        detail: { workspace_id: wid }
      })
    )

    selected_workspace_id.value = wid
    await load_workspaces()
    await refresh_workspace_files_state()
  } catch (e) {
    toast(tr('workspace.createWorkspaceException', { error: visible_error(e, 'workspace.createWorkspaceFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

async function rename_workspace() {
  const wid = safe_string(selected_workspace_id.value).trim()
  if (!is_workspace_id_safe(wid)) {
    toast(tr('workspace.invalidWorkspaceId'), 'error')
    return
  }

  const new_name = safe_string(rename_ws_name.value).trim()
  const icon = safe_string(rename_ws_icon.value).trim()

  if (!new_name) {
    toast(tr('workspace.enterNewName'), 'info')
    return
  }

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_rename', localized_args({
        workspace_id: wid,
        new_workspace_name: new_name,
        icon
      })),
      'workspace.renameWorkspaceFailed'
    )

    toast(get_display_text(data, 'workspace.workspaceRenamed'), 'success')
    window.dispatchEvent(new CustomEvent('nisb_workspaces_refresh', { detail: {} }))
    await load_workspaces()
  } catch (e) {
    toast(tr('workspace.renameWorkspaceException', { error: visible_error(e, 'workspace.renameWorkspaceFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

async function delete_workspace() {
  const wid = safe_string(selected_workspace_id.value).trim()
  if (!is_workspace_id_safe(wid)) {
    toast(tr('workspace.invalidWorkspaceId'), 'error')
    return
  }

  if (is_default_workspace.value) {
    toast(tr('workspace.defaultWorkspaceDeleteDenied'), 'info')
    return
  }

  const ok = window.confirm(tr('workspace.deleteWorkspaceConfirm'))
  if (!ok) return

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_delete', localized_args({ workspace_id: wid })),
      'workspace.deleteWorkspaceFailed'
    )

    toast(get_display_text(data, 'workspace.workspaceDeleted'), 'success')

    await load_workspaces()

    let fallback = 'workspace_work'
    const ids = new Set(safe_array(workspaces.value).map((w) => safe_string(w.id)))
    if (!ids.has(fallback)) fallback = safe_string(workspaces.value?.[0]?.id)

    if (fallback) {
      selected_workspace_id.value = fallback

      window.dispatchEvent(new CustomEvent('nisb_workspaces_refresh', { detail: {} }))
      window.dispatchEvent(
        new CustomEvent('nisb_workspace_switch_request', {
          detail: { workspace_id: fallback }
        })
      )

      await refresh_workspace_files_state()
    } else {
      window.dispatchEvent(new CustomEvent('nisb_workspaces_refresh', { detail: {} }))
    }
  } catch (e) {
    toast(tr('workspace.deleteWorkspaceException', { error: visible_error(e, 'workspace.deleteWorkspaceFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

function load_local_evidence_from_storage() {
  const s = readLocalEvidenceSettings()
  local_evidence_sync.value = !!s.sync
  local_evidence_auto_select.value = !!s.autoselect

  if (!local_evidence_sync.value) {
    local_evidence_auto_select.value = false
  }
}

function load_chat_translate_from_storage() {
  query_translate_enabled.value = false

  try {
    localStorage.setItem(LS_QUERY_TRANSLATE_ENABLED, 'false')
  } catch {}

  const m = localStorage.getItem(LS_QUERY_TRANSLATE_MODEL)
  if (m !== null && safe_string(m).trim()) {
    query_translate_model.value = safe_string(m).trim()
  }

  if (!query_translate_model.value) {
    query_translate_model.value = 'gpt-4o-mini'
  }
}

function load_conversation_model_from_store() {
  conversation_model.value =
    safe_string(chat_cfg.models?.conversationModel || 'gpt-4o-mini').trim() || 'gpt-4o-mini'
}

function load_from_storage_all() {
  load_local_evidence_from_storage()
  load_chat_translate_from_storage()
  load_conversation_model_from_store()
}

function get_focus_storage_key(workspace_id) {
  const ws = safe_string(workspace_id).trim() || 'default'
  return `nisb_fs_focus_root_${ws}`
}

function read_focus_from_local() {
  try {
    const wid = safe_string(selected_workspace_id.value).trim()
    if (!is_workspace_id_safe(wid)) {
      toast(tr('workspace.invalidWorkspaceId'), 'error')
      return
    }

    const key = get_focus_storage_key(wid)
    const v = safe_string(localStorage.getItem(key)).trim()
    saved_focused_preview.value = v

    toast(v ? tr('workspace.focusRead', { path: v }) : tr('workspace.focusEmpty'), 'info')
  } catch {
    toast(tr('workspace.focusReadFailed'), 'error')
  }
}

function normalize_path(p) {
  return safe_string(p)
    .trim()
    .replace(/\\\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\/+/, '')
}

function get_base_name(p) {
  const s = normalize_path(p)
  if (!s) return ''
  const parts = s.split('/').filter(Boolean)
  return parts[parts.length - 1] || s
}

function escape_markdown_link_text(name) {
  return safe_string(name).replace(/[\[\]]/g, '\\$&')
}

function build_nisb_file_url({ path, type = 'file', ws = '' }) {
  const u = new URL('nisb://file')
  if (ws) u.searchParams.set('ws', ws)
  u.searchParams.set('type', type)
  u.searchParams.set('path', normalize_path(path))
  return u.toString()
}

async function copy_text_safe(text) {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {}

  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return !!ok
  } catch {
    return false
  }
}

async function copy_current_favorites_internal_links() {
  if (!workspace_id_safe.value) {
    toast(tr('workspace.invalidWorkspaceIdCopy'), 'error')
    return
  }

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_favorites_list_files', localized_args({ workspace_id: selected_workspace_id.value })),
      'workspace.getCurrentFavoritesFailed'
    )

    const items = safe_array(data.items)
    if (!items.length) {
      toast(tr('workspace.currentFavoritesEmpty'), 'info')
      return
    }

    const ws = selected_workspace_id.value
    const dir_items = []
    const file_items = []

    for (const it of items) {
      const raw_path = safe_string(it?.path).trim()
      if (!raw_path) continue

      const type =
        safe_string(it?.type || 'file').toLowerCase().trim() === 'directory'
          ? 'directory'
          : 'file'

      const path = normalize_path(raw_path)
      if (!path) continue

      const base = get_base_name(path)
      const name = escape_markdown_link_text(base || path)
      const url = build_nisb_file_url({ path, type, ws })

      if (type === 'directory') dir_items.push({ name, url })
      else file_items.push({ name, url })
    }

    const lines = []

    if (dir_items.length) {
      lines.push(tr('workspace.favoriteDirectoriesHeading', { count: dir_items.length }))
      for (const d of dir_items) lines.push(`- [${d.name}/](${d.url})`)
      lines.push('')
    }

    if (file_items.length) {
      lines.push(tr('workspace.favoriteFilesHeading', { count: file_items.length }))
      for (const f of file_items) lines.push(`- [${f.name}](${f.url})`)
    }

    const text = lines.join('\n').trim()
    const ok = await copy_text_safe(text)

    toast(
      ok
        ? tr('workspace.copiedFavoriteLinks', { dirs: dir_items.length, files: file_items.length })
        : tr('workspace.clipboardDenied'),
      ok ? 'success' : 'error'
    )
  } catch (e) {
    toast(tr('workspace.copyFailed', { error: visible_error(e, 'workspace.getCurrentFavoritesFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

async function refresh_workspace_files_state() {
  if (!workspace_id_safe.value) {
    toast(tr('workspace.invalidWorkspaceIdRefresh'), 'error')
    return
  }

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_files_state_get', localized_args({
        workspace_id: selected_workspace_id.value
      })),
      'workspace.refreshWorkspaceFilesStateFailed'
    )

    const info = extract_workspace_files_state(data)
    const saved = safe_object(info.files_state?.saved)
    const current = safe_object(info.files_state?.current)
    const focused = safe_string(saved.focused_root_path).trim()
    const favs = safe_array(saved.favorites)

    saved_focused_preview.value = focused
    saved_favorites_count.value = favs.length
    saved_favorites_preview.value = favs
      .slice(0, 8)
      .map((x) => safe_string(x?.path).trim())
      .filter(Boolean)

    // 同步后端 current.favorites 到本地内存态（刷新时重置清空标记）
    local_current_favorites.value = safe_array(current.favorites)
    local_favorites_cleared.value = false
  } catch (e) {
    toast(tr('workspace.refreshFailed', { error: visible_error(e, 'workspace.refreshWorkspaceFilesStateFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

async function save_workspace_snapshot_from_current() {
  if (!workspace_id_safe.value) {
    toast(tr('workspace.invalidWorkspaceIdSave'), 'error')
    return
  }

  busy.value = true

  try {
    const wid = selected_workspace_id.value
    const path = safe_string(saved_focused_preview.value).trim().replace(/^\/+/, '')

    // 若本地标记了清空常用，需先批量 toggle 取消后端 current.favorites
    if (local_favorites_cleared.value && local_current_favorites.value.length > 0) {
      for (const item of local_current_favorites.value) {
        const item_path = safe_string(item?.path || item).trim()
        const item_type = safe_string(item?.type || 'file').trim()
        if (!item_path) continue
        try {
          await callTool('nisb_favorites_toggle_file', localized_args({
            path: item_path,
            type: item_type,
            workspace_id: wid
          }))
        } catch {}
      }
    }

    assert_tool_success(
      await callTool('nisb_workspace_files_state_set', localized_args({
        workspace_id: wid,
        focused_root_path: path
      })),
      'workspace.updateCurrentStateFailed'
    )

    const data = assert_tool_success(
      await callTool('nisb_workspace_files_state_save', localized_args({
        workspace_id: wid
      })),
      'workspace.saveSnapshotFailed'
    )

    toast(get_display_text(data, 'workspace.snapshotSaved'), 'success')
    await refresh_workspace_files_state()
    // 保存成功后立即刷新左侧栏常用区
    window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
  } catch (e) {
    toast(tr('workspace.saveFailed', { error: visible_error(e, 'workspace.saveSnapshotFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

async function apply_workspace_files_state_to_ui() {
  if (!workspace_id_safe.value) {
    toast(tr('workspace.invalidWorkspaceIdApply'), 'error')
    return
  }

  busy.value = true

  try {
    const data = assert_tool_success(
      await callTool('nisb_workspace_files_state_apply', localized_args({
        workspace_id: selected_workspace_id.value
      })),
      'workspace.applyWorkspaceFilesStateFailed'
    )

    const info = extract_workspace_files_state(data)
    const cur = safe_object(info.files_state?.current)
    const focused = safe_string(cur.focused_root_path).trim()

    window.dispatchEvent(
      new CustomEvent('nisb-left-sidebar-switch-tab', {
        detail: { tab: 'files' }
      })
    )

    if (focused) {
      window.dispatchEvent(
        new CustomEvent('nisb_file_focus_root', {
          detail: { path: focused }
        })
      )
    } else {
      window.dispatchEvent(new CustomEvent('nisb_file_clear_focus_root', { detail: {} }))
    }

    window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))

    toast(get_display_text(data, 'workspace.appliedToUi'), 'success')
    await refresh_workspace_files_state()
  } catch (e) {
    toast(tr('workspace.applyFailed', { error: visible_error(e, 'workspace.applyWorkspaceFilesStateFailed') }), 'error')
  } finally {
    busy.value = false
  }
}

// 清空常用：仅清本地内存态，不调后端，不影响聚焦目录
// 保存时才会通过批量 toggle 持久化到后端
function clear_workspace_favorites_local() {
  if (!workspace_id_safe.value) {
    toast(tr('workspace.invalidWorkspaceIdClear'), 'error')
    return
  }

  local_favorites_cleared.value = true
  toast(tr('workspace.favoritesLocalCleared'), 'info')
}

function emit_local_evidence_settings_updated() {
  window.dispatchEvent(
    new CustomEvent('nisb-local-evidence-settings-updated', {
      detail: {
        sync: !!local_evidence_sync.value,
        autoselect: !!local_evidence_auto_select.value
      }
    })
  )
}

watch(
  () => props.open,
  async (v) => {
    if (v) {
      tab.value = 'files'
      load_from_storage_all()

      const p = safe_string(props.workspaceId).trim()
      if (is_workspace_id_safe(p)) {
        selected_workspace_id.value = p
      } else {
        try {
          const saved = safe_string(localStorage.getItem(LS_CURRENT_WORKSPACE_ID)).trim()
          if (is_workspace_id_safe(saved)) selected_workspace_id.value = saved
          else selected_workspace_id.value = 'workspace_work'
        } catch {
          selected_workspace_id.value = 'workspace_work'
        }
      }

      await load_workspaces()

      saved_favorites_count.value = 0
      saved_favorites_preview.value = []
      saved_focused_preview.value = ''
      local_current_favorites.value = []
      local_favorites_cleared.value = false

      if (workspace_id_safe.value) {
        await refresh_workspace_files_state()
      }
    }
  },
  { immediate: true }
)

watch(
  () => settings.locale,
  async () => {
    model_catalog_error.value = ''

    if (props.open && tab.value === 'models') {
      await load_model_catalog()
    }
  }
)

watch(
  () => props.workspaceId,
  async (v) => {
    const wid = safe_string(v).trim()
    if (!props.open) return
    if (!is_workspace_id_safe(wid)) return
    if (wid === selected_workspace_id.value) return

    selected_workspace_id.value = wid
    sync_rename_fields_from_selected()
    await refresh_workspace_files_state()
  }
)

watch(
  () => local_evidence_sync.value,
  (v) => {
    if (!v) {
      local_evidence_auto_select.value = false
    }
  }
)

function emit_close() {
  emit('close')
}

function save() {
  writeLocalEvidenceSettings({
    sync: !!local_evidence_sync.value,
    autoselect: !!local_evidence_auto_select.value
  })

  emit_local_evidence_settings_updated()

  query_translate_enabled.value = false
  localStorage.setItem(LS_QUERY_TRANSLATE_ENABLED, 'false')

  const translate_model = safe_string(query_translate_model.value).trim() || 'gpt-4o-mini'
  query_translate_model.value = translate_model
  localStorage.setItem(LS_QUERY_TRANSLATE_MODEL, translate_model)

  const conversation_model_value =
    safe_string(conversation_model.value).trim() || 'gpt-4o-mini'
  conversation_model.value = conversation_model_value

  if (typeof chat_cfg.setConversationModel === 'function') {
    chat_cfg.setConversationModel(conversation_model_value)
  }

  emit_close()
}

function reset() {
  local_evidence_sync.value = true
  local_evidence_auto_select.value = true
  query_translate_enabled.value = false
  query_translate_model.value = 'gpt-4o-mini'
  conversation_model.value = 'gpt-4o-mini'
  save()
}
</script>

<style src="./Settings/settings-modal.css"></style>

<style scoped>
.nisb-modal-mask {
  backdrop-filter: blur(8px);
}
</style>


