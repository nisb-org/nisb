<template>
  <section class="workbench_card">
    <div class="card_head">
      <div>
        <div class="card_title">{{ t('room.workspaceExplorer.header.title') }}</div>
        <div class="card_subtitle">
          {{ t('room.workspaceExplorer.header.subtitle') }}
        </div>
      </div>
      <div class="card_badges">
        <span class="mini_badge" :class="{ active: workspace_ready }">
          {{
            workspace_ready
              ? t('room.workspaceExplorer.header.badges.workspaceReady')
              : t('room.workspaceExplorer.header.badges.workspaceNotReady')
          }}
        </span>
        <span class="mini_badge">
          {{ visible_focus_root || t('room.workspaceExplorer.common.rootDir') }}
        </span>
      </div>
    </div>

    <div v-if="!workspace_ready" class="empty_block">
      {{ t('room.workspaceExplorer.empty.noWorkspace') }}
    </div>

    <template v-else>
      <div class="section_block">
        <div class="section_title">{{ t('room.workspaceExplorer.sections.recommended') }}</div>
        <div v-if="recommended_entries.length" class="entry_list">
          <button
            v-for="entry in recommended_entries"
            :key="entry.key"
            class="entry_button"
            type="button"
            @click="open_path(entry.path, entry.label)"
          >
            <span class="entry_left">
              <span class="entry_tag">{{ entry.label }}</span>
              <span class="entry_path">{{ entry.display_path || entry.path }}</span>
            </span>
            <span class="entry_action">{{ t('room.workspaceExplorer.actions.open') }}</span>
          </button>
        </div>
        <div v-else class="empty_inline">
          {{ t('room.workspaceExplorer.empty.noRecommended') }}
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">{{ t('room.workspaceExplorer.sections.manualOpen') }}</div>
        <div class="manual_open_row">
          <input
            v-model="manual_relative_path"
            class="path_input"
            type="text"
            :placeholder="t('room.workspaceExplorer.manual.placeholder')"
            @keydown.enter.prevent="submit_manual_open"
          />
          <button
            class="ghost_btn"
            type="button"
            :disabled="!manual_relative_path_trimmed"
            @click="submit_manual_open"
          >
            {{ t('room.workspaceExplorer.actions.open') }}
          </button>
        </div>
        <div class="helper_text">
          {{ t('room.workspaceExplorer.manual.helper') }}
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">{{ t('room.workspaceExplorer.sections.recent') }}</div>
        <div v-if="recent_open_entries.length" class="recent_list">
          <button
            v-for="item in recent_open_entries"
            :key="item.key"
            class="recent_item"
            type="button"
            @click="open_path(item.path, item.label)"
          >
            <span class="recent_top">
              <span class="recent_label">{{ item.label }}</span>
              <span class="recent_time">{{ item.time_text }}</span>
            </span>
            <span class="recent_path">{{ item.display_path || item.path }}</span>
          </button>
        </div>
        <div v-else class="empty_inline">
          {{ t('room.workspaceExplorer.empty.noRecent') }}
        </div>
      </div>

      <div class="section_block">
        <div class="section_title">{{ t('room.workspaceExplorer.sections.context') }}</div>
        <div class="facts_grid">
          <div class="fact_item">
            <span class="fact_label">{{ t('room.workspaceExplorer.facts.workspaceId') }}</span>
            <strong>{{ workspace_id || t('room.workspaceExplorer.common.dash') }}</strong>
          </div>
          <div class="fact_item">
            <span class="fact_label">{{ t('room.workspaceExplorer.facts.focusRoot') }}</span>
            <strong>{{ visible_focus_root || t('room.workspaceExplorer.common.rootDir') }}</strong>
          </div>
          <div class="fact_item">
            <span class="fact_label">{{ t('room.workspaceExplorer.facts.entryCount') }}</span>
            <strong>{{ recommended_entries.length }}</strong>
          </div>
          <div class="fact_item">
            <span class="fact_label">{{ t('room.workspaceExplorer.facts.recentCount') }}</span>
            <strong>{{ recent_open_entries.length }}</strong>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'

const props = defineProps({
  workspace_ready: { type: Boolean, default: false },
  workspace_id: { type: String, default: '' },
  focus_root: { type: String, default: '' },
  reload_seq: { type: Number, default: 0 },
  open_relative_path: { type: String, default: '' },
  open_seq: { type: Number, default: 0 },
})

const emit = defineEmits(['status', 'dirty_change'])

const { t, locale } = useI18n()

const manual_relative_path = ref('')
const recent_open_list = ref([])

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function safe_array(v) {
  return Array.isArray(v) ? v : []
}

function normalize_relative_path(value) {
  let s = safe_string(value).trim().replace(/\\+/g, '/')
  while (s.includes('//')) s = s.replace(/\/+/g, '/')
  s = s.replace(/^\/+|\/+$/g, '')
  const parts = s
    .split('/')
    .map((item) => safe_string(item).trim())
    .filter((item) => item && item !== '.' && item !== '..')
  return parts.join('/')
}

function display_path(path) {
  const raw = safe_string(path).trim()
  if (!raw) return ''
  const visible = safe_string(to_user_visible_path(raw)).trim()
  return visible || raw
}

function pretty_time(date) {
  try {
    const time_locale = String(locale.value || '').trim() === 'zh-CN' ? 'zh-CN' : 'en-US'
    return new Intl.DateTimeFormat(time_locale, {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  } catch {
    return ''
  }
}

const visible_focus_root = computed(() => {
  return display_path(props.focus_root)
})

const snapshot_path_entries = computed(() => {
  const rows = []
  const source = window.__NISB_ROOM_WORKSPACE_SNAPSHOT__ || null
  const snapshot = source && typeof source === 'object' ? source : null
  if (!snapshot) return rows

  for (const [key, raw] of Object.entries(snapshot)) {
    if (typeof raw === 'string' && key.endsWith('_relative_path')) {
      const path = normalize_relative_path(raw)
      if (!path) continue
      rows.push({
        key,
        label: key.replace(/_relative_path$/, ''),
        path,
      })
    }

    if (Array.isArray(raw) && key.endsWith('_relative_paths')) {
      for (const item of raw) {
        const path = normalize_relative_path(item)
        if (!path) continue
        rows.push({
          key: `${key}:${path}`,
          label: key.replace(/_relative_paths$/, ''),
          path,
        })
      }
    }
  }

  return dedupe_entries(rows)
})

const recommended_entries = computed(() => {
  return snapshot_path_entries.value
})

const recent_open_entries = computed(() => {
  return recent_open_list.value
})

const manual_relative_path_trimmed = computed(() => normalize_relative_path(manual_relative_path.value))

function dedupe_entries(list) {
  const seen = new Set()
  const out = []
  for (const item of safe_array(list)) {
    const path = normalize_relative_path(item?.path)
    if (!path || seen.has(path)) continue
    seen.add(path)
    out.push({
      key: safe_string(item?.key || path),
      label: safe_string(item?.label || t('room.workspaceExplorer.common.path')),
      path,
      display_path: display_path(path),
    })
  }
  return out
}

function push_recent(path, label = '') {
  const normalized = normalize_relative_path(path)
  if (!normalized) return

  const next = [
    {
      key: `${Date.now()}-${normalized}`,
      label: safe_string(label || t('room.workspaceExplorer.recentLabels.recent')),
      path: normalized,
      display_path: display_path(normalized),
      time_text: pretty_time(new Date()),
    },
    ...recent_open_list.value.filter((item) => normalize_relative_path(item?.path) !== normalized),
  ].slice(0, 8)

  recent_open_list.value = next
}

function open_path(path, label = '') {
  const normalized = normalize_relative_path(path)
  if (!normalized) {
    emit('status', {
      message: t('room.workspaceExplorer.messages.emptyPath'),
      is_error: true,
    })
    return
  }

  push_recent(normalized, label || t('room.workspaceExplorer.common.path'))
  emit('status', {
    message: t('room.workspaceExplorer.messages.opening', { path: display_path(normalized) }),
    is_error: false,
  })
  window.dispatchEvent(new CustomEvent('nisb-room-workspace-open-relative-path', {
    detail: {
      path: normalized,
      workspace_id: safe_string(props.workspace_id).trim(),
      focus_root: safe_string(props.focus_root).trim(),
    },
  }))
}

function submit_manual_open() {
  open_path(manual_relative_path_trimmed.value, t('room.workspaceExplorer.recentLabels.manual'))
  manual_relative_path.value = ''
}

watch(
  () => props.open_seq,
  () => {
    const normalized = normalize_relative_path(props.open_relative_path)
    if (!normalized) return
    push_recent(normalized, t('room.workspaceExplorer.recentLabels.event'))
    emit('status', {
      message: t('room.workspaceExplorer.messages.located', { path: display_path(normalized) }),
      is_error: false,
    })
  }
)

watch(
  () => props.reload_seq,
  () => {
    emit('dirty_change', false)
  }
)

watch(
  () => props.workspace_id,
  () => {
    recent_open_list.value = []
    manual_relative_path.value = ''
    emit('dirty_change', false)
  }
)

onMounted(() => {
  emit('dirty_change', false)
})
</script>

<style scoped>
.workbench_card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  padding: 0.95rem;
  min-width: 0;
}

.card_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.card_title {
  color: var(--text-main);
  font-size: 0.95rem;
  font-weight: 700;
}

.card_subtitle {
  margin-top: 0.24rem;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
}

.card_badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.mini_badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--sidebar-bg);
  color: var(--text-secondary);
  font-size: 0.74rem;
}

.mini_badge.active {
  border-color: rgba(46, 139, 87, 0.3);
  color: #2e8b57;
  background: rgba(46, 139, 87, 0.08);
}

.section_block {
  margin-top: 0.95rem;
  padding-top: 0.95rem;
  border-top: 1px solid var(--line);
}

.section_title {
  color: var(--text-main);
  font-size: 0.88rem;
  font-weight: 700;
  margin-bottom: 0.65rem;
}

.entry_list,
.recent_list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.entry_button,
.recent_item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  color: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}

.entry_button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.72rem 0.8rem;
}

.entry_button:hover,
.recent_item:hover {
  border-color: var(--selected);
  background: var(--selected-bg);
}

.entry_left {
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
  min-width: 0;
}

.entry_tag,
.recent_label {
  color: var(--text-secondary);
  font-size: 0.74rem;
}

.entry_path,
.recent_path {
  color: var(--text-main);
  font-size: 0.84rem;
  word-break: break-all;
}

.entry_action {
  color: var(--selected);
  font-size: 0.8rem;
  flex-shrink: 0;
}

.manual_open_row {
  display: flex;
  align-items: stretch;
  gap: 0.6rem;
}

.path_input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--sidebar-bg);
  color: var(--text-main);
  padding: 0.7rem 0.75rem;
  font-family: inherit;
  outline: none;
}

.path_input:focus {
  border-color: var(--selected);
}

.ghost_btn {
  height: 38px;
  padding: 0 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost_btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.ghost_btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.recent_item {
  padding: 0.72rem 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
}

.recent_top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}

.recent_time {
  color: var(--text-secondary);
  font-size: 0.74rem;
  flex-shrink: 0;
}

.facts_grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.fact_item {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.68rem 0.72rem;
  min-width: 0;
}

.fact_label {
  display: block;
  color: var(--text-secondary);
  font-size: 0.74rem;
  margin-bottom: 0.2rem;
}

.fact_item strong {
  display: block;
  color: var(--text-main);
  font-size: 0.84rem;
  word-break: break-word;
}

.helper_text,
.empty_inline,
.empty_block {
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.55;
}

.empty_block {
  margin-top: 0.95rem;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.9rem;
}

@media (max-width: 720px) {
  .manual_open_row {
    flex-direction: column;
  }

  .facts_grid {
    grid-template-columns: 1fr;
  }

  .entry_button {
    flex-direction: column;
    align-items: stretch;
  }

  .entry_action {
    align-self: flex-end;
  }

  .recent_top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

