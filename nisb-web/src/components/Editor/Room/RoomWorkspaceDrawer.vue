<template>
  <div v-if="visible" class="modal_mask" @click="close_drawer">
    <div class="modal_panel" @click.stop>
      <div class="modal_header">
        <div class="workspace_title_wrap">
          <div class="workspace_eyebrow">{{ t('room.workspaceDrawer.header.eyebrow') }}</div>
          <h3>{{ t('room.workspaceDrawer.header.title') }}</h3>
          <p class="workspace_desc">
            {{ t('room.workspaceDrawer.header.description') }}
          </p>

          <div class="workspace_head_chips">
            <span class="head_chip">
              {{
                t('room.workspaceDrawer.header.chips.workspace', {
                  value: effective_workspace_name || effective_workspace_id || t('room.workspaceDrawer.common.unbound'),
                })
              }}
            </span>
            <span class="head_chip">
              {{
                t('room.workspaceDrawer.header.chips.focus', {
                  value: visible_effective_focus_root || t('room.workspaceDrawer.common.rootDir'),
                })
              }}
            </span>
            <span class="head_chip" :class="{ ready: workspace_ready }">
              {{
                workspace_ready
                  ? t('room.workspaceDrawer.header.chips.ready')
                  : t('room.workspaceDrawer.header.chips.notReady')
              }}
            </span>
          </div>
        </div>

        <div class="modal_actions">
          <button class="ghost_btn" type="button" @click="refresh_all" :disabled="busy">
            {{
              busy
                ? t('room.workspaceDrawer.actions.refreshing')
                : t('room.workspaceDrawer.actions.refresh')
            }}
          </button>
          <button class="close_btn" type="button" @click="close_drawer">
            {{ t('room.workspaceDrawer.actions.closeSymbol') }}
          </button>
        </div>
      </div>

      <div class="modal_body">
        <section class="section_card workspace_meta_card">
          <div class="section_head">
            <div>
              <div class="section_title">{{ t('room.workspaceDrawer.snapshot.title') }}</div>
              <div class="section_subtitle">
                {{ t('room.workspaceDrawer.snapshot.subtitle') }}
              </div>
            </div>
          </div>

          <div class="meta_grid top_gap">
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.workspaceId') }}</span>
              <strong>{{ effective_workspace_id || t('room.workspaceDrawer.common.dash') }}</strong>
            </div>
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.workspaceName') }}</span>
              <strong>
                {{ snapshot.workspace_name || effective_workspace_name || t('room.workspaceDrawer.common.dash') }}
              </strong>
            </div>
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.focusRoot') }}</span>
              <strong>
                {{ visible_snapshot_focus_root || visible_effective_focus_root || t('room.workspaceDrawer.common.rootDirBracketed') }}
              </strong>
            </div>
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.scope') }}</span>
              <strong>
                {{
                  snapshot.scope_exists
                    ? t('room.workspaceDrawer.snapshot.values.scopeReady')
                    : t('room.workspaceDrawer.snapshot.values.scopeNotReady')
                }}
              </strong>
            </div>
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.topLevelDirectories') }}</span>
              <strong>{{ snapshot.top_level_directories ?? 0 }}</strong>
            </div>
            <div class="meta_item">
              <span class="meta_label">{{ t('room.workspaceDrawer.snapshot.meta.topLevelFiles') }}</span>
              <strong>{{ snapshot.top_level_files ?? 0 }}</strong>
            </div>
          </div>

          <div class="suggest_row">
            <div class="suggest_chip">
              <span class="suggest_label">{{ t('room.workspaceDrawer.snapshot.suggested.roomNote') }}</span>
              <span class="suggest_value">
                {{ snapshot.suggested_room_note_relative_path || t('room.workspaceDrawer.common.dash') }}
              </span>
            </div>
            <div class="suggest_chip">
              <span class="suggest_label">{{ t('room.workspaceDrawer.snapshot.suggested.agentNotebook') }}</span>
              <span class="suggest_value">
                {{ snapshot.suggested_agent_notebook_relative_path || t('room.workspaceDrawer.common.dash') }}
              </span>
            </div>
          </div>

          <div v-if="visible_status_message" class="status_line" :class="{ error: !!status_error }">
            {{ visible_status_message }}
          </div>
        </section>

        <section class="section_card workspace_content_card">
          <div class="section_head">
            <div>
              <div class="section_title">{{ t('room.workspaceDrawer.content.title') }}</div>
              <div class="section_subtitle">
                {{ t('room.workspaceDrawer.content.subtitle') }}
              </div>
            </div>
          </div>

          <div class="workspace_body_grid top_gap">
            <aside class="workspace_sidebar">
              <RoomWorkspaceQuickSaveCard
                :workspace_ready="workspace_ready"
                :workspace_id="effective_workspace_id"
                :focus_root="effective_focus_root"
                :room_id="room_id"
                :room_state="effective_room_state"
                :snapshot="snapshot"
                :default_agent_id="default_agent_id"
                @saved="handle_saved"
                @status="handle_status"
                @open_relative_path="handle_open_relative_path"
              />
            </aside>

            <main class="workspace_main">
              <RoomWorkspaceExplorer
                :workspace_ready="workspace_ready"
                :workspace_id="effective_workspace_id"
                :focus_root="effective_focus_root"
                :reload_seq="reload_seq"
                :open_relative_path="open_relative_path"
                :open_seq="open_seq"
                @status="handle_status"
                @dirty_change="explorer_dirty = !!$event"
              />
            </main>
          </div>
        </section>
      </div>

      <div class="modal_footer">
        <div class="footer_hint">
          <span v-if="explorer_dirty">
            {{ t('room.workspaceDrawer.footer.dirty') }}
          </span>
          <span v-else-if="workspace_ready">
            {{ t('room.workspaceDrawer.footer.ready') }}
          </span>
          <span v-else>
            {{ t('room.workspaceDrawer.footer.notReady') }}
          </span>
        </div>

        <div class="footer_actions">
          <button class="ghost_btn" type="button" @click="close_drawer">
            {{ t('room.workspaceDrawer.actions.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../composables/useMCP'
import { useRoomStore } from '../../../stores/room'
import { to_user_visible_path } from '../../../composables/left_sidebar/file_browser/file_path_display'
import RoomWorkspaceQuickSaveCard from './RoomWorkspaceQuickSaveCard.vue'
import RoomWorkspaceExplorer from './RoomWorkspaceExplorer.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  room_id: { type: String, default: '' },
  room_state: { type: Object, default: () => ({}) },
  workspace_id: { type: String, default: '' },
  workspace_name: { type: String, default: '' },
  focus_root: { type: String, default: '' },
  focus_label: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const { callTool } = useMCP()
const room_store = useRoomStore()

const busy = ref(false)
const snapshot = ref({})
const status_message = ref('')
const status_error = ref('')
const reload_seq = ref(0)
const open_seq = ref(0)
const open_relative_path = ref('')
const explorer_dirty = ref(false)
const pending_saved_relative_path = ref('')

function display_path(path) {
  const raw = String(path || '').trim()
  if (!raw) return ''
  const visible = String(to_user_visible_path(raw) || '').trim()
  return visible || raw
}

function display_text(text) {
  return String(text || '').replace(/(^|[\s"'`(])agent_files(?=\/|$)/g, '$1user')
}

const effective_room_state = computed(() => {
  if (props.room_state && typeof props.room_state === 'object' && Object.keys(props.room_state).length) {
    return props.room_state
  }
  if (room_store.roomState && typeof room_store.roomState === 'object') {
    return room_store.roomState
  }
  if (room_store.room_state && typeof room_store.room_state === 'object') {
    return room_store.room_state
  }
  return {}
})

const resolved_workspace = computed(() => {
  const room_state = effective_room_state.value || {}
  const room_info =
    room_store.roomInfo ||
    room_store.currentRoom ||
    room_store.activeRoom ||
    room_store.room ||
    {}

  const workspace_context =
    room_state.workspace_context ||
    room_info.workspace_context ||
    room_info.workspace_binding ||
    room_info.workspace ||
    {}

  return {
    workspace_id: String(
      props.workspace_id ||
      workspace_context.workspace_id ||
      room_state.workspace_id ||
      room_info.workspace_id ||
      ''
    ).trim(),
    workspace_name: String(
      props.workspace_name ||
      workspace_context.workspace_name ||
      room_state.workspace_name ||
      room_info.workspace_name ||
      ''
    ).trim(),
    focus_root: String(
      props.focus_root ||
      workspace_context.focus_root ||
      room_state.focus_root ||
      room_info.focus_root ||
      ''
    ).trim(),
    focus_label: String(
      props.focus_label ||
      workspace_context.focus_label ||
      room_state.focus_label ||
      room_info.focus_label ||
      ''
    ).trim(),
  }
})

const effective_workspace_id = computed(() => String(resolved_workspace.value.workspace_id || '').trim())
const effective_workspace_name = computed(() => String(resolved_workspace.value.workspace_name || '').trim())
const effective_focus_root = computed(() => String(resolved_workspace.value.focus_root || '').trim())
const effective_focus_label = computed(() => String(resolved_workspace.value.focus_label || '').trim())

const visible_effective_focus_root = computed(() => display_path(effective_focus_root.value))
const visible_snapshot_focus_root = computed(() => display_path(snapshot.value?.focus_root))
const visible_status_message = computed(() => display_text(status_message.value))

const workspace_ready = computed(() => !!effective_workspace_id.value)

const default_agent_id = computed(() => {
  const room_state = effective_room_state.value || {}
  const direct = String(room_state.default_reply_role_id || '').trim()
  if (direct) return direct

  const active_roles = Array.isArray(room_state.active_roles) ? room_state.active_roles : []
  const first_role = String(active_roles[0] || '').trim()
  if (first_role) return first_role

  return 'agent'
})

function normalize_tool_result(res) {
  if (res && typeof res === 'object' && res.result && typeof res.result === 'object') return res.result
  return res || {}
}

function assert_tool_success(res) {
  const data = normalize_tool_result(res)
  if (data?.status && data.status !== 'success') {
    throw new Error(String(data.message || t('room.workspaceDrawer.messages.operationFailed')))
  }
  if (data?.success === false) {
    throw new Error(String(data.message || t('room.workspaceDrawer.messages.operationFailed')))
  }
  return data
}

function set_status(message, is_error = false) {
  status_message.value = String(message || '')
  status_error.value = is_error ? String(message || 'error') : ''
}

async function load_snapshot() {
  if (!workspace_ready.value) {
    snapshot.value = {}
    return
  }

  const data = assert_tool_success(await callTool('nisb_workspace_snapshot_get', {
    room_id: String(props.room_id || '').trim(),
    workspace_id: effective_workspace_id.value,
    workspace_name: effective_workspace_name.value,
    focus_root: effective_focus_root.value,
    focus_label: effective_focus_label.value,
    agent_id: default_agent_id.value,
  }))

  snapshot.value = data || {}
}

async function refresh_all() {
  if (!workspace_ready.value) {
    set_status(t('room.workspaceDrawer.messages.noWorkspaceId'), true)
    return
  }

  busy.value = true
  try {
    await load_snapshot()
    reload_seq.value += 1
    set_status(t('room.workspaceDrawer.messages.refreshed'), false)
  } catch (e) {
    set_status(String(e?.message || t('room.workspaceDrawer.messages.refreshFailed')), true)
  } finally {
    busy.value = false
  }
}

function handle_status(detail) {
  set_status(String(detail?.message || ''), !!detail?.is_error)
}

async function handle_saved(detail) {
  if (detail?.relative_path) {
    open_relative_path.value = String(detail.relative_path || '')
    open_seq.value += 1
  }

  reload_seq.value += 1
  await load_snapshot()
  set_status(
    String(
      detail?.message ||
        t('room.workspaceDrawer.messages.located', {
          path: detail?.relative_path || '',
        })
    ),
    false
  )
}

function handle_open_relative_path(relative_path) {
  open_relative_path.value = String(relative_path || '').trim()
  open_seq.value += 1
}

function handle_room_workspace_saved(evt) {
  const d = evt?.detail || {}
  const event_workspace_id = String(d.workspace_id || '').trim()
  const relative_path = String(d.relative_path || '').trim()

  if (!relative_path) return
  if (event_workspace_id && effective_workspace_id.value && event_workspace_id !== effective_workspace_id.value) return

  pending_saved_relative_path.value = relative_path

  if (!props.visible) return

  reload_seq.value += 1
  open_relative_path.value = relative_path
  open_seq.value += 1
  void load_snapshot()
  set_status(
    String(
      d.message ||
        t('room.workspaceDrawer.messages.locatedTo', {
          path: relative_path,
        })
    ),
    false
  )
}

function close_drawer() {
  if (explorer_dirty.value) {
    const ok = window.confirm(t('room.workspaceDrawer.messages.closeConfirm'))
    if (!ok) return
  }
  emit('close')
}

onMounted(() => {
  window.addEventListener('nisb-room-workspace-saved', handle_room_workspace_saved)
})

onUnmounted(() => {
  window.removeEventListener('nisb-room-workspace-saved', handle_room_workspace_saved)
})

watch(
  () => props.visible,
  async (v) => {
    if (!v) return
    await load_snapshot()
    reload_seq.value += 1

    if (pending_saved_relative_path.value) {
      open_relative_path.value = String(pending_saved_relative_path.value || '')
      open_seq.value += 1
      pending_saved_relative_path.value = ''
    }
  },
  { immediate: true }
)

watch(
  () => [effective_workspace_id.value, effective_focus_root.value],
  async () => {
    if (!props.visible) return
    await load_snapshot()
    reload_seq.value += 1
  }
)
</script>

<style scoped>
.modal_mask {
  position: fixed;
  inset: 0;
  z-index: 2147482600;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 1rem;
  background:
    radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--selected) 10%, transparent), transparent 42%),
    rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(18px) saturate(1.08);
  -webkit-backdrop-filter: blur(18px) saturate(1.08);
}

.modal_panel {
  position: relative;
  width: min(1360px, 96vw);
  max-height: 92vh;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, var(--editor-bg)),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 24px 70px rgba(0, 0, 0, 0.28);
}

.modal_header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1rem 0.9rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  flex-shrink: 0;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 46%),
    color-mix(in srgb, var(--sidebar-bg) 92%, transparent);
}

.workspace_title_wrap {
  min-width: 0;
}

.workspace_eyebrow {
  color: var(--text-secondary);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  margin-bottom: 0.35rem;
}

.workspace_title_wrap h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.02rem;
}

.workspace_desc {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.5;
  word-break: break-word;
}

.workspace_head_chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.7rem;
}

.head_chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-secondary);
  font-size: 0.75rem;
  max-width: 100%;
}

.head_chip.ready {
  border-color: rgba(46, 139, 87, 0.3);
  color: #2e8b57;
  background: rgba(46, 139, 87, 0.08);
}

.modal_actions {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.modal_body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-gutter: stable both-edges;
  padding: 1rem;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 24%, transparent),
      transparent 38%
    );
}

.section_card {
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  border-radius: 15px;
  padding: 0.95rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.section_head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8rem;
  flex-wrap: wrap;
}

.section_title {
  color: var(--text-main);
  font-size: 0.95rem;
  font-weight: 700;
}

.section_subtitle {
  margin-top: 0.25rem;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
}

.top_gap {
  margin-top: 0.85rem;
}

.workspace_meta_card {
  margin-bottom: 1rem;
}

.meta_grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.7rem;
}

.meta_item {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.68rem 0.72rem;
  min-width: 0;
}

.meta_label {
  display: block;
  color: var(--text-secondary);
  font-size: 0.74rem;
  margin-bottom: 0.24rem;
}

.meta_item strong {
  display: block;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.86rem;
}

.suggest_row {
  margin-top: 0.75rem;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
}

.suggest_chip {
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: var(--sidebar-bg);
  padding: 0.62rem 0.72rem;
  min-width: 0;
}

.suggest_label {
  display: block;
  color: var(--text-secondary);
  font-size: 0.74rem;
  margin-bottom: 0.24rem;
}

.suggest_value {
  display: block;
  color: var(--text-main);
  font-size: 0.84rem;
  word-break: break-all;
}

.status_line {
  margin-top: 0.7rem;
  color: #2e8b57;
  font-size: 0.84rem;
  line-height: 1.5;
}

.status_line.error {
  color: #d55;
}

.workspace_content_card {
  min-height: 0;
}

.workspace_body_grid {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 1rem;
  min-height: 0;
  align-items: start;
}

.workspace_sidebar,
.workspace_main {
  min-width: 0;
}

.ghost_btn,
.close_btn {
  height: 34px;
  padding: 0 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text-secondary);
}

.ghost_btn:hover:not(:disabled),
.close_btn:hover:not(:disabled) {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.close_btn {
  width: 34px;
  padding: 0;
}

.modal_footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.9rem;
  padding: 0.9rem 1rem 1rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  flex-shrink: 0;
  background: color-mix(in srgb, var(--sidebar-bg) 88%, transparent);
}

.footer_hint {
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.45;
}

.footer_actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 1240px) {
  .meta_grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .workspace_body_grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1024px) {
  .meta_grid,
  .suggest_row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .modal_panel {
    width: min(100vw, 100vw);
    max-height: 100vh;
    border-radius: 0;
  }

  .modal_header,
  .modal_footer {
    flex-direction: column;
    align-items: stretch;
  }

  .modal_actions,
  .footer_actions {
    justify-content: flex-end;
  }

  .modal_body {
    padding: 0.8rem;
  }

  .meta_item strong {
    white-space: normal;
    word-break: break-word;
  }
}
</style>

