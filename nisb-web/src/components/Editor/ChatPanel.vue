<template>
  <div class="chat-mode" ref="chatRoot">
    <RoomHeader
      v-if="isRoomMode"
      :room="roomStore.room"
      :room_state="roomStore.roomState"
      :roles_count="roomStore.rolesCount"
      :participants_count="roomStore.participantsCount"
      @back-click="handleRoomBack"
      @refresh-click="handleRoomRefresh"
      @roles-click="roomStore.openRolesDrawer()"
      @settings-click="roomStore.openSettingsModal()"
    />

    <div class="chat-center-stack" :class="{ 'room-mode': isRoomMode }">
      <div class="chat-messages preview-content" ref="chatMessagesEl">
        <div
          v-if="isRoomMode && (hasMoreOlder || roomItemsPaging.loadedonce || roomItemsPaging.loaded_once)"
          class="room-older-trigger"
        >
          <button
            v-if="hasMoreOlder"
            type="button"
            class="room-older-btn"
            :disabled="loadingOlder"
            @click="handle_load_older_messages"
          >
            {{ loadingOlder ? t('chat.panel.roomOlder.loading') : t('chat.panel.roomOlder.loadMore') }}
          </button>

          <div v-else class="room-older-hint">
            {{ t('chat.panel.roomOlder.noMore') }}
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="msg.id || msg.local_id || idx"
          class="message-item"
          :id="`chat-msg-${idx}`"
          :data-chat-anchor="`chat-${idx}`"
        >
          <div class="message-role" :class="msg.role">
            {{ getRoleLabel(msg) }}
          </div>

          <div
            v-if="msg.role === 'assistant'"
            class="message-content message-markdown"
          >
            <StreamMarkdownRenderer :message="msg" />
          </div>

          <div
            v-else
            class="message-content message-markdown"
            v-html="renderMarkdown(msg.content)"
          ></div>

          <section
            v-if="msg.role === 'assistant' && has_tool_activity(msg)"
            class="tool-activity-panel"
            :class="{ 'is-expanded': is_tool_panel_expanded(msg) }"
          >
            <button
              type="button"
              class="tool-activity-head"
              :aria-expanded="is_tool_panel_expanded(msg)"
              @click="toggle_tool_panel(msg)"
            >
              <span class="tool-activity-title-stack">
                <span class="tool-activity-title">
                  {{ t('chat.toolActivity.title') }}
                </span>
                <span class="tool-activity-subtitle">
                  {{ get_tool_activity_summary_label(msg) }}
                </span>
              </span>

              <span class="tool-activity-head-right">
                <span
                  v-for="chip in get_tool_activity_panel_chips(msg)"
                  :key="chip.key"
                  class="tool-activity-panel-chip"
                  :class="chip.class"
                >
                  {{ chip.label }}
                </span>

                <span
                  v-if="msg.pending"
                  class="tool-activity-live-chip"
                >
                  <span class="tool-live-dot" aria-hidden="true"></span>
                  {{ t('chat.toolActivity.status.running') }}
                </span>

                <span class="tool-panel-expand-indicator" aria-hidden="true">
                  {{ is_tool_panel_expanded(msg) ? '−' : '+' }}
                </span>
              </span>
            </button>

            <div
              v-if="is_tool_panel_expanded(msg)"
              class="tool-record-list"
            >
              <article
                v-for="(tool_row, tool_idx) in get_tool_activity_rows(msg)"
                :key="get_tool_row_key(msg, tool_row, tool_idx)"
                class="tool-record-card"
                :class="[
                  `status-${get_tool_status_class(tool_row)}`,
                  is_tool_row_expanded(get_tool_row_key(msg, tool_row, tool_idx)) ? 'is-expanded' : '',
                ]"
              >
                <button
                  type="button"
                  class="tool-record-head"
                  :aria-expanded="is_tool_row_expanded(get_tool_row_key(msg, tool_row, tool_idx))"
                  @click="toggle_tool_row(get_tool_row_key(msg, tool_row, tool_idx))"
                >
                  <span class="tool-record-left">
                    <span class="tool-kind-chip">
                      {{ get_tool_kind_label(tool_row) }}
                    </span>

                    <span class="tool-role-chip">
                      {{ get_tool_role_label(tool_row) }}
                    </span>

                    <span class="tool-name mono">
                      {{ get_tool_display_name(tool_row) }}
                    </span>
                  </span>

                  <span class="tool-record-right">
                    <span
                      v-for="flag in get_tool_flag_chips(tool_row)"
                      :key="flag.key"
                      class="tool-flag-chip"
                      :class="flag.class"
                    >
                      {{ flag.label }}
                    </span>

                    <span
                      class="tool-status-chip"
                      :class="get_tool_status_class(tool_row)"
                    >
                      {{ get_tool_status_label(tool_row) }}
                    </span>

                    <span class="tool-expand-indicator" aria-hidden="true">
                      {{ is_tool_row_expanded(get_tool_row_key(msg, tool_row, tool_idx)) ? '−' : '+' }}
                    </span>
                  </span>
                </button>

                <div class="tool-record-summary">
                  {{ get_tool_summary(tool_row) }}
                </div>

                <div
                  v-if="is_tool_row_expanded(get_tool_row_key(msg, tool_row, tool_idx))"
                  class="tool-record-body"
                >
                  <div
                    v-if="get_tool_argument_preview(tool_row)"
                    class="tool-detail-section"
                  >
                    <div class="tool-detail-label">
                      {{ t('chat.toolActivity.arguments') }}
                    </div>
                    <pre class="tool-json">{{ get_tool_argument_preview(tool_row) }}</pre>
                  </div>

                  <div
                    v-if="get_tool_result_preview(tool_row)"
                    class="tool-detail-section"
                  >
                    <div class="tool-detail-label">
                      {{ t('chat.toolActivity.result') }}
                    </div>
                    <pre class="tool-json">{{ get_tool_result_preview(tool_row) }}</pre>
                  </div>

                  <div
                    v-if="get_tool_machine_field_rows(tool_row).length"
                    class="tool-detail-section"
                  >
                    <div class="tool-detail-label">
                      {{ t('chat.toolActivity.machineFields') }}
                    </div>

                    <div class="tool-machine-grid">
                      <div
                        v-for="field in get_tool_machine_field_rows(tool_row)"
                        :key="field.key"
                        class="tool-machine-field"
                      >
                        <span>{{ field.label }}</span>
                        <strong class="mono">{{ field.value }}</strong>
                      </div>
                    </div>
                  </div>

                  <details class="tool-raw-details">
                    <summary>{{ t('chat.toolActivity.rawPayload') }}</summary>
                    <pre class="tool-json raw">{{ format_tool_json(get_tool_raw_payload(tool_row)) }}</pre>
                  </details>
                </div>
              </article>
            </div>
          </section>

          <CitationList
            v-if="msg.role === 'assistant' && !msg.pending"
            :citations="msg.citations || []"
          />
        </div>
      </div>
    </div>

    <div v-if="selectedAttachments.length > 0 && !isRoomMode" class="attachments-preview">
      <div v-for="(att, idx) in selectedAttachments" :key="idx" class="attachment-item">
        <span>📎 {{ att.name }}</span>
        <button class="remove-attachment-btn" type="button" @click="removeAttachment(idx)">×</button>
      </div>
    </div>

    <div class="chat-input-area">
      <div v-if="stream_banner_visible" class="stream-status-bar">
        <div class="stream-status-left">
          <span class="stream-dot"></span>
          <span class="stream-text">{{ stream_banner_text }}</span>
        </div>
        <div class="stream-status-right">
          <span v-if="active_stream_state.mode_used" class="stream-chip">{{ active_stream_state.mode_used }}</span>
          <span v-if="active_stream_state.request_id" class="stream-chip mono">
            {{ active_stream_state.request_id }}
          </span>
        </div>
      </div>

      <div v-if="isRoomMode && room_save_confirm.visible" class="room-save-confirm-bar">
        <div class="room-save-confirm-main">
          <div class="room-save-confirm-title">
            {{ room_save_confirm.prompt_message || t('chat.panel.roomSaveConfirm.defaultPrompt') }}
          </div>

          <div class="room-save-confirm-meta">
            <span v-if="room_save_confirm.relative_path">
              {{ t('chat.panel.roomSaveConfirm.meta.candidatePath', { path: room_save_confirm.relative_path }) }}
            </span>
            <span v-else-if="room_save_confirm.target_kind">
              {{ t('chat.panel.roomSaveConfirm.meta.candidateKind', { kind: room_save_confirm.target_kind }) }}
            </span>
            <span v-if="room_save_confirm.last_relative_path">
              {{ t('chat.panel.roomSaveConfirm.meta.lastSaved', { path: room_save_confirm.last_relative_path }) }}
            </span>
          </div>
        </div>

        <div class="room-save-confirm-actions">
          <button
            type="button"
            class="room-save-confirm-btn primary"
            :disabled="room_save_confirm.saving || isUploading"
            @click="handle_room_save_confirm_room_note"
          >
            {{ room_save_confirm.saving ? t('chat.panel.roomSaveConfirm.actions.processing') : t('chat.panel.roomSaveConfirm.actions.saveToNote') }}
          </button>

          <button
            v-if="has_last_room_note_target"
            type="button"
            class="room-save-confirm-btn"
            :disabled="room_save_confirm.saving || isUploading"
            @click="handle_room_save_confirm_last_target"
          >
            {{ t('chat.panel.roomSaveConfirm.actions.appendLastNote') }}
          </button>

          <button
            type="button"
            class="room-save-confirm-btn ghost"
            :disabled="room_save_confirm.saving"
            @click="clear_room_save_confirm"
          >
            {{ t('chat.panel.roomSaveConfirm.actions.cancel') }}
          </button>
        </div>
      </div>

      <div class="chat-controls-shell">
        <div class="chat-controls-summary">
          <button
            type="button"
            class="control-toggle-btn"
            :class="{ active: showControlTray }"
            :disabled="isUploading"
            @click="toggleControlTray"
          >
            {{ showControlTray ? t('chat.panel.controls.collapse') : t('chat.panel.controls.features') }}
          </button>

          <div class="control-summary-chips">
            <span v-if="isRoomMode" class="summary-chip active">{{ t('chat.panel.summary.room') }}</span>
            <span v-if="!isRoomMode && selectedAttachments.length > 0" class="summary-chip">
              {{ t('chat.panel.summary.attachments', { count: selectedAttachments.length }) }}
            </span>
            <span v-if="isUploading" class="summary-chip warning">{{ t('chat.panel.summary.uploading') }}</span>
            <span v-if="isThinking" class="summary-chip info">{{ t('chat.panel.summary.thinking') }}</span>
          </div>
        </div>

        <div v-if="showControlTray" class="chat-controls-tray">
          <div class="chat-controls-row">
            <div class="attach-btn-wrapper" v-if="!isRoomMode">
              <button
                class="attach-btn"
                type="button"
                @click="toggleAttachMenu"
                :disabled="isThinking || isUploading"
                :title="isUploading ? t('chat.panel.attach.uploadingTitle') : t('chat.panel.attach.title')"
                :aria-label="t('chat.panel.attach.ariaLabel')"
              >
                {{ isUploading ? '⏳' : '📎' }}
              </button>

              <div v-if="showAttachMenu" class="attach-menu" @click.stop>
                <div class="menu-item" @click="triggerFileUpload">{{ t('chat.panel.attach.uploadLocal') }}</div>
                <div class="menu-item" @click="openFileSystemPicker">{{ t('chat.panel.attach.pickExisting') }}</div>
              </div>
            </div>

            <McpMenu />
            <FedMenu :disabled="isThinking || isUploading" />
            <RoomMenu :disabled="room_menu_disabled" />
            <RagMenu />
          </div>
        </div>
      </div>

      <div class="chat-input-row">
        <input
          v-if="!isRoomMode"
          ref="fileInput"
          type="file"
          multiple
          accept=".txt,.md,.json,.py,.js,.html,.css,.yaml,.yml,.sh,.env,.pdf,.docx,.png,.jpg,.jpeg,.gif"
          style="display: none"
          @change="handleFileUpload"
        />

        <textarea
          v-model="inputText"
          :placeholder="isRoomMode ? t('chat.panel.input.roomPlaceholder') : t('chat.panel.input.chatPlaceholder')"
          class="chat-input"
          @compositionstart="isComposing = true"
          @compositionend="isComposing = false"
          @keydown="on_chat_textarea_keydown"
        ></textarea>

        <button
          type="button"
          @click="handle_send_action"
          class="send-btn"
          :disabled="(!inputText.trim() && !isThinking) || isUploading"
          :title="isThinking ? t('chat.panel.actions.stopLocalRuntime') : t('chat.panel.actions.send')"
        >
          {{ isThinking ? '■' : '➤' }}
        </button>
      </div>
    </div>

    <ChatAttachmentModal
      v-if="showFileSystemModal && !isRoomMode"
      :search-query="fileSearchQuery"
      @update:search-query="fileSearchQuery = $event"
      :current-dir="currentDir"
      :entries="filteredEntries"
      :loading="isLoadingFiles"
      :get-file-icon="getFileIcon"
      @close="closeFileSystemModal"
      @go-parent="goParentDir"
      @enter-directory="enterDirectory"
      @select-file="selectExistingFile"
    />

    <RoomRolesDrawer
      :visible="roomStore.ui.rolesDrawerOpen"
      :room_id="roomStore.roomId"
      @close="roomStore.closeRolesDrawer()"
    />

    <RoomSettingsModal
      :visible="roomStore.ui.settingsModalOpen"
      :room_id="roomStore.roomId"
      @close="roomStore.closeSettingsModal()"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, watch, ref, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { use_chat_panel_controller } from '../../composables/editor/chat_panel/use_chat_panel_controller'
import { use_room_natural_save } from '../../composables/room/use_room_natural_save'
import { use_chat_panel_tool_activity_presenter } from '../../composables/editor/chat_panel/use_chat_panel_tool_activity_presenter'
import { useChatConfigStore } from '../../stores/chatConfig'
import { useRoomStore } from '../../stores/room'

import McpMenu from './Chat/actions/McpMenu.vue'
import RagMenu from './Chat/actions/RagMenu.vue'
import FedMenu from './Chat/actions/FedMenu.vue'
import RoomMenu from './Chat/actions/RoomMenu.vue'
import CitationList from './Chat/CitationList.vue'
import StreamMarkdownRenderer from './Chat/StreamMarkdownRenderer.vue'
import ChatAttachmentModal from './Chat/ChatAttachmentModal.vue'
import RoomHeader from './Room/RoomHeader.vue'
import RoomRolesDrawer from './Room/RoomRolesDrawer.vue'
import RoomSettingsModal from './Room/RoomSettingsModal.vue'

import {
  push_message,
} from '../../composables/editor/chat_panel/use_chat_panel_message_writer'

const props = defineProps({
  model: { type: String, required: true },
  convId: { type: [String, Number, null], default: null },
})

const emit = defineEmits(['update-conv-id', 'open-lightbox', 'stream-state', 'stream-final'])

const { t } = useI18n()
const { callTool, callToolStream } = useMCP()
const chatCfg = useChatConfigStore()
const roomStore = useRoomStore()

const {
  chatRoot,
  chatMessagesEl,
  messages,
  inputText,
  isThinking,
  isComposing,

  selectedAttachments,
  fileInput,
  isUploading,
  showAttachMenu,

  showFileSystemModal,
  isLoadingFiles,
  currentDir,
  fileSearchQuery,
  filteredEntries,

  renderMarkdown,
  getRoleLabel,
  getFileIcon,

  isRoomMode,
  hasMoreOlder,
  loadingOlder,
  roomItemsPaging,
  loadRoomMessages,
  loadOlderRoomMessages,

  roomRuntimeResultEvent,
  roomRuntimeResultPayload,

  toggleAttachMenu,
  triggerFileUpload,
  openFileSystemPicker,
  closeFileSystemModal,
  goParentDir,
  enterDirectory,
  selectExistingFile,
  handleFileUpload,
  removeAttachment,

  onTextareaKeydown,
  stopStreaming,
  finishRoomRuntime,
  sendChatMessage,
  active_stream_state,
  stream_banner_visible,
  stream_banner_text,

  refreshRoomRuntime,
  nudgeRoomRuntimePolling,
  resetRoomRuntimeLane,
} = use_chat_panel_controller({
  props,
  emit,
  call_tool: callTool,
  call_tool_stream: callToolStream,
})

const {
  has_tool_activity: presenter_has_tool_activity,
  get_tool_call_rows: presenter_get_tool_call_rows,
  get_tool_result_rows: presenter_get_tool_result_rows,
  get_tool_display_name: presenter_get_tool_display_name,
  get_tool_preview: presenter_get_tool_preview,
  get_tool_summary: presenter_get_tool_summary,
  get_tool_status_i18n_key: presenter_get_tool_status_i18n_key,
  get_tool_role_i18n_key: presenter_get_tool_role_i18n_key,
  get_tool_kind_i18n_key: presenter_get_tool_kind_i18n_key,
  get_tool_status_class: presenter_get_tool_status_class,
  get_tool_machine_fields: presenter_get_tool_machine_fields,
  get_tool_flags: presenter_get_tool_flags,
  get_tool_raw_payload: presenter_get_tool_raw_payload,
} = use_chat_panel_tool_activity_presenter()

const showControlTray = ref(false)
const expanded_tool_rows = ref(new Set())
const expanded_tool_panels = ref(new Set())

const room_menu_disabled = computed(() => {
  return !!isUploading.value
})

function toggleControlTray() {
  showControlTray.value = !showControlTray.value
}

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function resolve_error_text(error) {
  const text = safe_string(error?.message || error).trim()
  return text || t('common.unknownError')
}

function normalize_token(value) {
  return safe_string(value).trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function normalize_continuation_status(value) {
  const token = normalize_token(value)

  if (
    [
      'running',
      'pause_requested',
      'interrupted',
      'resumed',
      'completed',
      'completed_after_resume',
      'budget_exhausted',
    ].includes(token)
  ) {
    return token
  }

  if (token === 'step_budget_exhausted' || token === 'exhausted') {
    return 'budget_exhausted'
  }

  return ''
}

function is_terminal_continuation_status(value) {
  return ['interrupted', 'completed', 'completed_after_resume', 'budget_exhausted'].includes(
    normalize_continuation_status(value)
  )
}

function scroll_to_bottom() {
  nextTick(() => {
    try {
      const el = chatMessagesEl.value
      if (el) el.scrollTop = el.scrollHeight
    } catch {}
  })
}

function dispatch_toast(message, type = 'success') {
  window.dispatchEvent(
    new CustomEvent('nisb-toast', {
      detail: { message, type },
    })
  )
}

function append_local_assistant_message(content) {
  const text = String(content || '').trim()
  if (!text) return

  push_message(messages, {
    id: `local_room_save_${Date.now()}`,
    role: 'assistant',
    content: text,
    response: text,
    pending: false,
    citations: [],
    tool_calls: [],
    tool_results: [],
  })
  scroll_to_bottom()
}

function create_empty_confirm_state() {
  return {
    visible: false,
    saving: false,
    raw_input: '',
    prompt_message: '',
    target_kind: '',
    relative_path: '',
    scoped_path: '',
    agent_id: '',
    mode: '',
    title: '',
    section_title: '',
    last_target_kind: '',
    last_relative_path: '',
    last_scoped_path: '',
    last_agent_id: '',
  }
}

const room_save_confirm = ref(create_empty_confirm_state())

function clear_room_save_confirm() {
  room_save_confirm.value = create_empty_confirm_state()
}

function open_room_save_confirm(detail, raw_input) {
  room_save_confirm.value = {
    ...create_empty_confirm_state(),
    visible: true,
    raw_input: String(raw_input || ''),
    prompt_message: String(
      detail?.prompt_message || detail?.promptMessage || t('chat.panel.roomSaveConfirm.defaultPrompt')
    ),
    target_kind: String(detail?.target_kind || detail?.targetKind || ''),
    relative_path: String(detail?.relative_path || detail?.relativePath || ''),
    scoped_path: String(detail?.scoped_path || detail?.scopedPath || ''),
    agent_id: '',
    mode: String(detail?.mode || ''),
    title: String(detail?.title || ''),
    section_title: String(detail?.section_title || detail?.sectionTitle || ''),
    last_target_kind: String(
      detail?.last_target_kind || detail?.lastTargetKind || ''
    ),
    last_relative_path: String(
      detail?.last_relative_path || detail?.lastRelativePath || ''
    ),
    last_scoped_path: String(
      detail?.last_scoped_path || detail?.lastScopedPath || ''
    ),
    last_agent_id: '',
  }
}

const has_last_room_note_target = computed(() => {
  const last_kind = String(room_save_confirm.value.last_target_kind || '').trim()
  const last_rel = String(
    room_save_confirm.value.last_relative_path ||
    room_save_confirm.value.last_scoped_path ||
    ''
  ).trim()

  if (!last_rel) return false
  return !last_kind || last_kind === 'room_note'
})

function build_local_save_message(detail) {
  const path =
    detail?.relative_path ||
    detail?.scoped_path ||
    detail?.relativePath ||
    detail?.scopedPath ||
    t('chat.panel.roomSaveConfirm.fallbackTarget')

  const targetKind = detail?.target_kind || detail?.targetKind || 'room_note'
  const mode = detail?.mode || 'append'

  return t('chat.panel.roomSaveConfirm.savedToTarget', {
    path,
    targetKind,
    mode,
  })
}

const { maybe_handle_room_save_intent, confirm_room_save_intent } =
  use_room_natural_save({
    room_store: roomStore,
    call_tool: callTool,
    on_status: (message, is_error = false) => {
      dispatch_toast(String(message || ''), is_error ? 'error' : 'success')
    },
  })

async function execute_confirm_save(overrides = {}) {
  if (room_save_confirm.value.saving) return

  room_save_confirm.value = {
    ...room_save_confirm.value,
    saving: true,
  }

  try {
    const raw = String(room_save_confirm.value.raw_input || '').trim()
    if (!raw) {
      clear_room_save_confirm()
      return
    }

    const result = await confirm_room_save_intent(raw, overrides)

    if (result?.success && result?.detail) {
      append_local_assistant_message(build_local_save_message(result.detail))
      inputText.value = ''
      clear_room_save_confirm()
      return
    }

    room_save_confirm.value = {
      ...room_save_confirm.value,
      saving: false,
    }
  } catch {
    room_save_confirm.value = {
      ...room_save_confirm.value,
      saving: false,
    }
  }
}

async function handle_room_save_confirm_room_note() {
  await execute_confirm_save({
    target_kind: 'room_note',
    mode: 'append',
  })
}

async function handle_room_save_confirm_last_target() {
  await execute_confirm_save({
    target_kind: 'room_note',
    relative_path: room_save_confirm.value.last_relative_path || '',
    scoped_path: room_save_confirm.value.last_scoped_path || '',
    mode: 'append',
  })
}

function is_terminal_room_event_name(value) {
  const normalized = safe_string(value).trim().toLowerCase()
  return (
    normalized === 'room.final' ||
    normalized === 'room.error' ||
    normalized === 'room.aborted' ||
    normalized === 'room.abort' ||
    normalized === 'final' ||
    normalized === 'error' ||
    normalized === 'aborted' ||
    normalized === 'abort'
  )
}

function is_terminal_room_status(value) {
  const normalized = safe_string(value).trim().toLowerCase()
  return (
    normalized === 'error' ||
    normalized === 'aborted' ||
    normalized === 'abort' ||
    normalized === 'cancelled' ||
    normalized === 'canceled' ||
    normalized === 'failed' ||
    normalized === 'terminated' ||
    normalized === 'timed_out' ||
    normalized === 'timeout' ||
    normalized === 'done' ||
    normalized === 'finished' ||
    normalized === 'completed'
  )
}

function read_room_runtime_event_name(event_obj = {}) {
  return safe_string(
    event_obj?.type ||
    event_obj?.event_name ||
    event_obj?.name
  ).trim()
}

function read_room_runtime_request_id(event_obj = {}, payload = {}) {
  return safe_string(
    payload?.request_id ||
    payload?.requestId ||
    event_obj?.request_id ||
    event_obj?.requestId ||
    event_obj?.payload?.request_id ||
    event_obj?.payload?.requestId
  ).trim()
}

function read_room_runtime_status(event_obj = {}, payload = {}) {
  return safe_string(
    payload?.status ||
    payload?.continuation_status ||
    event_obj?.status ||
    event_obj?.payload?.status ||
    event_obj?.payload?.continuation_status
  ).trim()
}

function read_room_runtime_message(event_obj = {}, payload = {}) {
  return safe_string(
    payload?.message ||
    event_obj?.message ||
    event_obj?.payload?.message
  ).trim()
}

watch(
  () => {
    if (!isRoomMode.value) return ''

    const event_obj = roomRuntimeResultEvent?.value || {}
    const payload = roomRuntimeResultPayload?.value || {}
    const active_request_id = safe_string(active_stream_state?.value?.request_id).trim()

    return JSON.stringify({
      active_request_id,
      result_request_id: read_room_runtime_request_id(event_obj, payload),
      event_name: read_room_runtime_event_name(event_obj),
      status: read_room_runtime_status(event_obj, payload),
      message: read_room_runtime_message(event_obj, payload),
    })
  },
  (signature, prevSignature) => {
    if (!signature || signature === prevSignature) return
    if (!isRoomMode.value) return
    if (!isThinking.value) return

    let parsed = null
    try {
      parsed = JSON.parse(signature)
    } catch {
      parsed = null
    }
    if (!parsed) return

    const active_request_id = safe_string(parsed.active_request_id).trim()
    const result_request_id = safe_string(parsed.result_request_id).trim()
    const event_name = safe_string(parsed.event_name).trim()
    const status = safe_string(parsed.status).trim()

    const terminal_by_event = is_terminal_room_event_name(event_name)
    const terminal_by_status = !event_name && is_terminal_room_status(status)

    if (!terminal_by_event && !terminal_by_status) return

    const event_obj = roomRuntimeResultEvent?.value || {}
    const payload = roomRuntimeResultPayload?.value || {}

    if (active_request_id && result_request_id && active_request_id !== result_request_id) {
      return
    }

    finishRoomRuntime({
      ...payload,
      request_id: result_request_id || active_request_id,
      status:
        status ||
        payload?.status ||
        payload?.continuation_status ||
        event_obj?.status ||
        event_obj?.payload?.status ||
        event_obj?.payload?.continuation_status ||
        (event_name === 'room.error' || event_name === 'error'
          ? 'error'
          : event_name === 'room.aborted' || event_name === 'room.abort' || event_name === 'aborted' || event_name === 'abort'
            ? 'aborted'
            : 'success'),
      message:
        payload?.message ||
        event_obj?.message ||
        event_obj?.payload?.message ||
        '',
      response:
        payload?.response ||
        payload?.content ||
        event_obj?.payload?.response ||
        event_obj?.payload?.content ||
        '',
    })
  }
)

watch(
  () => {
    if (!isRoomMode.value) return ''

    const payload = roomRuntimeResultPayload?.value || {}
    const event_obj = roomRuntimeResultEvent?.value || {}

    return JSON.stringify({
      continuation_status: normalize_continuation_status(
        payload?.continuation_status ||
        event_obj?.payload?.continuation_status ||
        roomStore.roomState?.continuation_status ||
        roomStore.currentRunStatus
      ),
      current_run_id: safe_string(
        payload?.run_id ||
        event_obj?.run_id ||
        roomStore.roomState?.current_run_id ||
        roomStore.currentRunId
      ).trim(),
      runtime_live: !!roomStore.runtimeLive,
    })
  },
  (signature, prevSignature) => {
    if (!signature || signature === prevSignature) return
    if (!isRoomMode.value) return
    if (!isThinking.value) return

    let parsed = null
    try {
      parsed = JSON.parse(signature)
    } catch {
      parsed = null
    }
    if (!parsed) return

    const continuation_status = normalize_continuation_status(parsed.continuation_status)

    if (!is_terminal_continuation_status(continuation_status)) return

    finishRoomRuntime({
      request_id: safe_string(active_stream_state?.value?.request_id).trim(),
      status: continuation_status,
      message: continuation_status,
    })
  }
)

async function handle_send_action() {
  if (isThinking.value) {
    stopStreaming()
    return
  }

  const raw = String(inputText.value || '').trim()
  if (!raw) return

  if (isRoomMode.value) {
    const handled = await maybe_handle_room_save_intent(raw)

    if (handled?.handled) {
      if (handled?.need_confirm) {
        open_room_save_confirm(handled.detail || {}, raw)
        return
      }

      clear_room_save_confirm()

      if (handled?.success && handled?.detail) {
        append_local_assistant_message(build_local_save_message(handled.detail))
        inputText.value = ''
      }
      return
    }
  }

  clear_room_save_confirm()
  await sendChatMessage()

  if (isRoomMode.value) {
    await nextTick()
    nudgeRoomRuntimePolling(250)
  }
}

function on_chat_textarea_keydown(event) {
  const is_submit =
    event.key === 'Enter' &&
    !event.shiftKey &&
    (event.ctrlKey || event.metaKey)

  if (is_submit && !isComposing.value) {
    event.preventDefault()
    void handle_send_action()
    return
  }

  onTextareaKeydown(event)
}

async function handle_load_older_messages() {
  if (!isRoomMode.value) return
  if (loadingOlder.value) return

  const el = chatMessagesEl.value
  const prevScrollHeight = el ? el.scrollHeight : 0
  const prevScrollTop = el ? el.scrollTop : 0

  try {
    await loadOlderRoomMessages()
    await nextTick()
    await nextTick()

    if (el) {
      const nextScrollHeight = el.scrollHeight
      const delta = Math.max(0, nextScrollHeight - prevScrollHeight)
      el.scrollTop = prevScrollTop + delta
    }
  } catch (error) {
    dispatch_toast(
      t('chat.panel.toast.loadOlderFailed', { error: resolve_error_text(error) }),
      'error'
    )
  }
}

async function handleRoomRefresh() {
  const rid = String(chatCfg.chat?.roomId || '').trim()
  if (!rid) return

  try {
    await loadRoomMessages(rid, {
      force_abort: true,
      scroll_to_bottom: true,
    })
    await refreshRoomRuntime({ reset: true, silent: false })
  } catch (error) {
    dispatch_toast(
      t('chat.panel.toast.refreshRoomFailed', { error: resolve_error_text(error) }),
      'error'
    )
  }
}

function handleRoomBack() {
  clear_room_save_confirm()
  stopStreaming()
  resetRoomRuntimeLane()
  roomStore.closeAllOverlays()
  roomStore.resetRoom()
  chatCfg.exitRoomHard()
}

function has_tool_activity(source) {
  return presenter_has_tool_activity(source)
}


function get_tool_call_rows(source) {
  return presenter_get_tool_call_rows(source)
}


function get_tool_result_rows(source) {
  return presenter_get_tool_result_rows(source)
}


function get_tool_activity_rows(source) {
  return [
    ...get_tool_call_rows(source),
    ...get_tool_result_rows(source),
  ]
}


function get_tool_panel_key(message) {
  return safe_string(
    message?.id ||
    message?.local_id ||
    message?.request_id ||
    message?.created_at ||
    message?.createdAt ||
    ''
  ).trim() || `message:${messages.value.indexOf(message)}`
}


function is_tool_panel_expanded(message) {
  const key = get_tool_panel_key(message)
  return expanded_tool_panels.value.has(key)
}


function toggle_tool_panel(message) {
  const key = get_tool_panel_key(message)
  if (!key) return

  const next = new Set(expanded_tool_panels.value)

  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }

  expanded_tool_panels.value = next
}


function get_tool_activity_summary_label(source) {
  const rows = get_tool_activity_rows(source)
  const count = rows.length
  const statusCounts = rows.reduce(
    (acc, row) => {
      const status = get_tool_status_class(row)
      acc[status] = (acc[status] || 0) + 1
      return acc
    },
    {}
  )

  if (count <= 0) return t('chat.toolActivity.empty')

  const parts = [String(count)]

  if (statusCounts.error) {
    parts.push(`${t('chat.toolActivity.status.error')} ${statusCounts.error}`)
  }

  if (statusCounts.warning) {
    parts.push(`${t('chat.toolActivity.status.warning')} ${statusCounts.warning}`)
  }

  if (statusCounts.running) {
    parts.push(`${t('chat.toolActivity.status.running')} ${statusCounts.running}`)
  }

  if (!statusCounts.error && !statusCounts.warning && !statusCounts.running && statusCounts.done) {
    parts.push(t('chat.toolActivity.status.done'))
  }

  return parts.join(' · ')
}


function get_tool_activity_panel_chips(source) {
  const rows = get_tool_activity_rows(source)
  const chips = []

  let hasError = false
  let hasWarning = false
  let hasRunning = false
  let hasCitations = false
  let hasSources = false
  let hasArtifacts = false
  let hasTrace = false

  for (const row of rows) {
    const status = get_tool_status_class(row)
    const flags = presenter_get_tool_flags(row)

    if (status === 'error' || flags.has_error) hasError = true
    if (status === 'warning' || flags.has_warning) hasWarning = true
    if (status === 'running') hasRunning = true
    if (flags.has_citations) hasCitations = true
    if (flags.has_sources) hasSources = true
    if (flags.has_artifacts) hasArtifacts = true
    if (flags.has_trace) hasTrace = true
  }

  if (hasError) {
    chips.push({
      key: 'error',
      label: t('chat.toolActivity.flags.error'),
      class: 'error',
    })
  }

  if (hasWarning && !hasError) {
    chips.push({
      key: 'warning',
      label: t('chat.toolActivity.flags.warning'),
      class: 'warning',
    })
  }

  if (hasRunning) {
    chips.push({
      key: 'running',
      label: t('chat.toolActivity.status.running'),
      class: 'running',
    })
  }

  if (hasCitations) {
    chips.push({
      key: 'citations',
      label: t('chat.toolActivity.flags.citations'),
      class: 'info',
    })
  }

  if (hasSources) {
    chips.push({
      key: 'sources',
      label: t('chat.toolActivity.flags.sources'),
      class: 'info',
    })
  }

  if (hasArtifacts) {
    chips.push({
      key: 'artifacts',
      label: t('chat.toolActivity.flags.artifacts'),
      class: 'info',
    })
  }

  if (hasTrace) {
    chips.push({
      key: 'trace',
      label: t('chat.toolActivity.flags.trace'),
      class: 'muted',
    })
  }

  return chips
}


function get_tool_activity_count_label(source) {
  return get_tool_activity_summary_label(source)
}


function get_tool_message_scope(message) {
  return safe_string(message?.id || message?.local_id || message?.request_id || '').trim()
}


function get_tool_row_key(message, item, index) {
  const messageKey = get_tool_message_scope(message) || 'message'
  const rowKey = safe_string(
    item?._key ||
    item?.id ||
    item?.tool_call_id ||
    item?.toolCallId ||
    item?.call_id ||
    item?.callId ||
    item?.request_id ||
    item?.requestId ||
    index
  ).trim()

  return `${messageKey}::${rowKey || index}`
}


function is_tool_row_expanded(key) {
  return expanded_tool_rows.value.has(String(key || ''))
}


function toggle_tool_row(key) {
  const normalized = String(key || '')
  if (!normalized) return

  const next = new Set(expanded_tool_rows.value)
  if (next.has(normalized)) {
    next.delete(normalized)
  } else {
    next.add(normalized)
  }

  expanded_tool_rows.value = next
}


function get_tool_display_name(item) {
  return presenter_get_tool_display_name(item)
}


function get_tool_preview(item) {
  return presenter_get_tool_preview(item)
}


function get_tool_summary(item) {
  return (
    presenter_get_tool_summary(item) ||
    get_tool_preview(item) ||
    t('chat.toolActivity.summaryFallback')
  )
}


function get_tool_argument_preview(item) {
  return safe_string(item?._argument_preview_text || '').trim()
}


function get_tool_result_preview(item) {
  return safe_string(item?._result_preview_text || '').trim()
}


function get_tool_status_class(item) {
  return presenter_get_tool_status_class(item)
}


function get_tool_status_label(item) {
  return t(presenter_get_tool_status_i18n_key(item))
}


function get_tool_role_label(item) {
  return t(presenter_get_tool_role_i18n_key(item))
}


function get_tool_kind_label(item) {
  return t(presenter_get_tool_kind_i18n_key(item))
}


function get_tool_flag_chips(item) {
  const flags = presenter_get_tool_flags(item)
  const chips = []

  if (flags.has_error) {
    chips.push({
      key: 'error',
      label: t('chat.toolActivity.flags.error'),
      class: 'error',
    })
  }

  if (flags.has_warning && !flags.has_error) {
    chips.push({
      key: 'warning',
      label: t('chat.toolActivity.flags.warning'),
      class: 'warning',
    })
  }

  if (flags.has_citations) {
    chips.push({
      key: 'citations',
      label: t('chat.toolActivity.flags.citations'),
      class: 'info',
    })
  }

  if (flags.has_sources) {
    chips.push({
      key: 'sources',
      label: t('chat.toolActivity.flags.sources'),
      class: 'info',
    })
  }

  if (flags.has_artifacts) {
    chips.push({
      key: 'artifacts',
      label: t('chat.toolActivity.flags.artifacts'),
      class: 'info',
    })
  }

  if (flags.has_external_result_view) {
    chips.push({
      key: 'externalView',
      label: t('chat.toolActivity.flags.externalView'),
      class: 'info',
    })
  }

  if (flags.has_trace) {
    chips.push({
      key: 'trace',
      label: t('chat.toolActivity.flags.trace'),
      class: 'muted',
    })
  }

  return chips
}


function get_tool_machine_field_rows(item) {
  const fields = presenter_get_tool_machine_fields(item)

  return Object.entries(fields)
    .filter(([, value]) => safe_string(value).trim())
    .map(([key, value]) => ({
      key,
      label: t(`chat.toolActivity.fields.${key}`),
      value: safe_string(value).trim(),
    }))
}


function get_tool_raw_payload(item) {
  return presenter_get_tool_raw_payload(item)
}


function format_tool_json(value) {
  try {
    return JSON.stringify(value ?? null, null, 2)
  } catch {
    return safe_string(value)
  }
}

watch(
  () => props.model,
  () => {
    stopStreaming()
  }
)

watch(
  () => props.convId,
  (newVal, oldVal) => {
    const next_id = String(newVal || '').trim()
    const prev_id = String(oldVal || '').trim()

    if (!next_id || !prev_id || next_id === prev_id) return
    stopStreaming()
  }
)

watch(
  () => isRoomMode.value,
  (enabled) => {
    if (!enabled) {
      clear_room_save_confirm()
    }
    showControlTray.value = false
  }
)

watch(
  () => isThinking.value,
  (thinking) => {
    if (thinking) {
      showControlTray.value = false
    }
  }
)

onBeforeUnmount(() => {
  stopStreaming()
})
</script>

<style scoped>
.chat-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-center-stack {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-center-stack.room-mode {
  background: var(--editor-bg);
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--editor-bg);
  padding: 2.5rem 2.5rem 3rem;
  color: var(--text-main);
  line-height: var(--text-line-height);
  word-wrap: break-word;
  cursor: text;
  max-width: 100%;
  margin: 0;
  content-visibility: auto;
  contain-intrinsic-size: 1000px 2000px;
}

.room-older-trigger {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 0 0 1.1rem;
}

.room-older-btn {
  height: 34px;
  padding: 0 0.95rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--sidebar-bg);
  color: var(--text-main);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.84rem;
  transition: all var(--transition-normal);
}

.room-older-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.room-older-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.room-older-hint {
  font-size: 0.82rem;
  color: var(--text-secondary);
  opacity: 0.85;
}

.message-item {
  margin-bottom: 2rem;
  width: 100%;
}

.message-role {
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  opacity: 0.7;
}

.message-role.user {
  color: var(--selected);
}

.message-role.assistant {
  color: var(--text-secondary);
}

.message-content {
  width: 100%;
  line-height: 1.9;
  color: var(--text-main);
}

.streaming-plain {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-markdown {
  padding: 0;
  background: transparent;
}

.tool-activity-panel {
  min-width: 0;
  margin-top: 0.92rem;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 86%, transparent)
    );
  color: var(--text-main);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}


.tool-activity-head {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}


.tool-activity-head:hover .tool-activity-title,
.tool-activity-head:focus-visible .tool-activity-title {
  color: var(--selected);
}


.tool-activity-head:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--selected) 42%, transparent);
  outline-offset: 4px;
  border-radius: 12px;
}


.tool-activity-head-right {
  min-width: 0;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.42rem;
  flex-wrap: wrap;
}


.tool-activity-title-stack {
  min-width: 0;
  flex: 1 1 auto;
  display: grid;
  gap: 0.16rem;
}


.tool-activity-title {
  color: var(--text-main);
  font-size: 0.82rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}


.tool-activity-subtitle {
  margin-top: 0.16rem;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 680;
  line-height: 1.4;
}


.tool-activity-live-chip {
  flex: 0 0 auto;
  min-height: 26px;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 9%, transparent);
  color: var(--selected);
  font-size: 0.72rem;
  font-weight: 780;
  white-space: nowrap;
}


.tool-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--selected) 12%, transparent);
}


.tool-record-list {
  min-width: 0;
  display: grid;
  gap: 0.58rem;
  margin-top: 0.66rem;
}


.tool-record-card {
  min-width: 0;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 46%, transparent)
    );
  overflow: hidden;
}


.tool-record-card.status-running {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
}


.tool-record-card.status-done {
  border-color: color-mix(in srgb, #16a34a 26%, var(--line));
}


.tool-record-card.status-warning {
  border-color: color-mix(in srgb, #d97706 34%, var(--line));
}


.tool-record-card.status-error {
  border-color: color-mix(in srgb, #ef4444 36%, var(--line));
}


.tool-record-card.status-cancelled {
  border-color: color-mix(in srgb, #8b5cf6 30%, var(--line));
}


.tool-record-head {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.72rem;
  padding: 0.62rem 0.68rem;
  border: none;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}


.tool-record-head:hover,
.tool-record-head:focus-visible {
  background: color-mix(in srgb, var(--selected-bg) 30%, transparent);
  outline: none;
}


.tool-record-left,
.tool-record-right {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex-wrap: wrap;
}


.tool-record-left {
  flex: 1 1 auto;
}


.tool-record-right {
  flex: 0 0 auto;
  justify-content: flex-end;
}


.tool-kind-chip,
.tool-role-chip,
.tool-status-chip,
.tool-flag-chip {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.46rem;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}


.tool-kind-chip {
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected) 8%, transparent);
  color: var(--selected);
}


.tool-role-chip {
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
}


.tool-name {
  min-width: 0;
  max-width: min(52vw, 520px);
  color: var(--text-main);
  font-size: 0.8rem;
  font-weight: 820;
  line-height: 1.3;
  overflow-wrap: anywhere;
}


.tool-status-chip.running {
  border: 1px solid color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected) 9%, transparent);
  color: var(--selected);
}


.tool-status-chip.done {
  border: 1px solid color-mix(in srgb, #16a34a 30%, var(--line));
  background: color-mix(in srgb, #16a34a 9%, transparent);
  color: #16a34a;
}


.tool-status-chip.warning {
  border: 1px solid color-mix(in srgb, #d97706 36%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
}


.tool-status-chip.error {
  border: 1px solid color-mix(in srgb, #ef4444 38%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: #ef4444;
}


.tool-status-chip.cancelled {
  border: 1px solid color-mix(in srgb, #8b5cf6 34%, var(--line));
  background: color-mix(in srgb, #8b5cf6 10%, transparent);
  color: #8b5cf6;
}


.tool-flag-chip {
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
}


.tool-flag-chip.error {
  border-color: color-mix(in srgb, #ef4444 38%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: #ef4444;
}


.tool-flag-chip.warning {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
}


.tool-flag-chip.info {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  color: var(--selected);
}


.tool-expand-indicator {
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 999px;
  color: var(--text-secondary);
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1;
}


.tool-record-summary {
  min-width: 0;
  padding: 0.54rem 0.68rem;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}


.tool-record-body {
  min-width: 0;
  display: grid;
  gap: 0.62rem;
  padding: 0 0.68rem 0.68rem;
}


.tool-detail-section {
  min-width: 0;
  display: grid;
  gap: 0.36rem;
}


.tool-detail-label {
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 820;
  letter-spacing: 0.01em;
}


.tool-machine-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.42rem;
}


.tool-machine-field {
  min-width: 0;
  display: grid;
  gap: 0.18rem;
  padding: 0.46rem 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 62%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 40%, transparent);
}


.tool-machine-field span {
  color: var(--text-secondary);
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1.25;
}


.tool-machine-field strong {
  min-width: 0;
  color: var(--text-main);
  font-size: 0.72rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: anywhere;
}


.tool-raw-details {
  min-width: 0;
  border-top: 1px dashed color-mix(in srgb, var(--line) 70%, transparent);
  padding-top: 0.48rem;
}


.tool-raw-details summary {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1.35;
}


.tool-raw-details summary:hover {
  color: var(--selected);
}


.tool-json {
  max-width: 100%;
  margin: 0;
  padding: 0.62rem;
  overflow: auto;
  border: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  color: var(--text-main);
  font-size: 0.72rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 74%, transparent) transparent;
}


.tool-json.raw {
  margin-top: 0.48rem;
}


.tool-json::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}


.tool-json::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}


.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);
}

.attachments-preview {
  padding: 0.4rem 1rem;
  background: var(--sidebar-bg);
  border-top: 1px solid var(--line);
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.2rem 0.5rem;
  background: var(--editor-bg);
  border-radius: 4px;
  border: 1px solid var(--line);
  font-size: 0.85rem;
}

.remove-attachment-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}

.remove-attachment-btn:hover {
  color: var(--text-main);
}

.chat-input-area {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.5rem 1rem 1rem;
  background: var(--sidebar-bg);
  flex-shrink: 0;
  border-top: 1px solid var(--line);
}

.stream-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.6rem 0.8rem;
  border: 1px solid rgba(74, 118, 255, 0.18);
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(74, 118, 255, 0.08) 0%, rgba(74, 118, 255, 0.03) 100%);
}

.stream-status-left,
.stream-status-right {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.stream-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--selected);
  box-shadow: 0 0 0 4px rgba(74, 118, 255, 0.12);
}

.stream-text {
  font-size: 0.85rem;
  color: var(--text-main);
}

.stream-chip {
  padding: 0.18rem 0.46rem;
  border-radius: 999px;
  background: var(--editor-bg);
  border: 1px solid var(--line);
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.stream-chip.mono {
  font-family: var(--font-mono, monospace);
}

.room-save-confirm-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.8rem;
  padding: 0.65rem 0.8rem;
  border: 1px solid rgba(60, 105, 188, 0.24);
  background: linear-gradient(135deg, rgba(60, 105, 188, 0.08) 0%, rgba(60, 105, 188, 0.03) 100%);
  border-radius: 10px;
}

.room-save-confirm-main {
  min-width: 0;
  flex: 1;
}

.room-save-confirm-title {
  color: var(--text-main);
  font-size: 0.9rem;
  font-weight: 600;
}

.room-save-confirm-meta {
  margin-top: 0.18rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.room-save-confirm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  flex-shrink: 0;
}

.room-save-confirm-btn {
  height: 32px;
  padding: 0 0.8rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-main);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.84rem;
  transition: all 0.18s ease;
}

.room-save-confirm-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
}

.room-save-confirm-btn.primary {
  background: var(--selected);
  border-color: var(--selected);
  color: #fff;
}

.room-save-confirm-btn.primary:hover:not(:disabled) {
  opacity: 0.92;
}

.room-save-confirm-btn.ghost {
  background: transparent;
  color: var(--text-secondary);
}

.room-save-confirm-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.chat-controls-shell {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.chat-controls-summary {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
}

.control-toggle-btn {
  height: 34px;
  padding: 0 0.9rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-secondary);
  font-family: inherit;
  font-size: 0.84rem;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.18s ease;
}

.control-toggle-btn:hover:not(:disabled),
.control-toggle-btn.active {
  background: var(--selected-bg);
  border-color: var(--selected);
  color: var(--selected);
}

.control-summary-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  min-width: 0;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 0.6rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-secondary);
  font-size: 0.74rem;
}

.summary-chip.active {
  border-color: rgba(74, 118, 255, 0.18);
  color: var(--selected);
}

.summary-chip.warning {
  color: #d39b2a;
}

.summary-chip.info {
  color: #5e84ff;
}

.chat-controls-tray {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  padding: 0.65rem;
}

.chat-controls-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.attach-btn-wrapper {
  position: relative;
  flex-shrink: 0;
}

.attach-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: transparent;
  cursor: pointer;
  font-size: 0.95rem;
  transition: all var(--transition-normal);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.attach-btn:hover:not(:disabled) {
  background: var(--sidebar-bg);
  border-color: var(--selected);
}

.attach-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.attach-menu {
  position: absolute;
  bottom: calc(100% + 0.35rem);
  left: 0;
  background: var(--sidebar-bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 160px;
  z-index: 100;
  animation: fadeInUp var(--transition-fast) ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.attach-menu .menu-item {
  padding: 0.6rem 1rem;
  cursor: pointer;
  transition: background var(--transition-fast);
  font-size: 0.9rem;
  color: var(--text-main);
  white-space: nowrap;
}

.attach-menu .menu-item:hover {
  background: var(--selected-bg);
  color: var(--selected);
}

.chat-controls-row :deep(.mcp-wrapper),
.chat-controls-row :deep(.rag-wrapper) {
  margin-top: 0 !important;
}

.chat-input-row {
  display: flex;
  gap: 0.6rem;
  align-items: flex-end;
  min-width: 0;
}

.chat-input {
  flex: 1 1 0;
  min-width: 0;
  font-family: monospace;
  font-size: 14px;
  padding: 0.85rem 0.9rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--editor-bg);
  color: var(--text-main);
  resize: none;
  min-height: 54px;
  max-height: 180px;
  outline: none;
  box-sizing: border-box;
}

.chat-input:focus {
  border-color: var(--selected);
}

.send-btn {
  width: 48px;
  height: 48px;
  padding: 0;
  background: var(--selected);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-family: inherit;
  font-size: 1.05rem;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 960px) {
  .room-save-confirm-bar,
  .stream-status-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .room-save-confirm-actions {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .chat-messages {
    padding: 1.2rem 1rem 1.5rem;
  }

  .tool-record-head {
    align-items: stretch;
    flex-direction: column;
  }


  .tool-record-right {
    width: 100%;
    justify-content: flex-start;
  }


  .tool-machine-grid {
    grid-template-columns: 1fr;
  }

  .chat-input-area {
    padding: 0.5rem 0.75rem calc(0.75rem + env(safe-area-inset-bottom, 0px));
  }

  .room-save-confirm-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .chat-input-row {
    align-items: stretch;
  }

  .send-btn {
    width: 44px;
    height: auto;
    min-height: 54px;
    border-radius: 12px;
  }
}

@media (max-width: 640px) {

  .tool-activity-head {
    align-items: stretch;
    flex-direction: column;
  }


  .tool-activity-head-right {
    width: 100%;
    justify-content: flex-start;
  }


  .tool-activity-live-chip {
    justify-content: center;
    width: 100%;
  }


.tool-activity-panel-chip,
.tool-panel-expand-indicator {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 820;
  line-height: 1;
  white-space: nowrap;
}


.tool-activity-panel-chip {
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
}


.tool-activity-panel-chip.running {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected) 9%, transparent);
  color: var(--selected);
}


.tool-activity-panel-chip.error {
  border-color: color-mix(in srgb, #ef4444 38%, var(--line));
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: #ef4444;
}


.tool-activity-panel-chip.warning {
  border-color: color-mix(in srgb, #d97706 36%, var(--line));
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
}


.tool-activity-panel-chip.info {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  color: var(--selected);
}


.tool-activity-panel-chip.muted {
  color: var(--text-secondary);
  opacity: 0.86;
}


.tool-activity-panel:not(.is-expanded) {
  padding: 0.72rem 0.78rem;
}


.tool-activity-panel:not(.is-expanded) .tool-activity-subtitle {
  color: color-mix(in srgb, var(--text-secondary) 88%, transparent);
}


.tool-panel-expand-indicator {
  width: 26px;
  height: 26px;
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  font-size: 0.92rem;
}


  .tool-name {
    max-width: 100%;
  }
  
  .chat-controls-summary {
    align-items: flex-start;
    flex-direction: column;
  }

  .control-summary-chips {
    width: 100%;
  }

  .chat-controls-tray {
    padding: 0.55rem;
  }

  .chat-controls-row {
    gap: 0.45rem;
  }

  .chat-input-row {
    gap: 0.5rem;
  }

  .chat-input {
    min-height: 50px;
    padding: 0.75rem 0.8rem;
  }

  .send-btn {
    width: 42px;
    min-height: 50px;
    font-size: 0.98rem;
  }
}

/* nisb room composer mobile summary one-line patch */
@media (max-width: 640px) {
  .chat-controls-summary {
    min-width: 0 !important;
    display: flex !important;
    align-items: center !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.42rem !important;
    overflow: hidden !important;
  }

  .control-toggle-btn {
    height: 30px !important;
    min-height: 30px !important;
    max-width: 8rem !important;
    padding: 0 0.72rem !important;
    font-size: 0.8rem !important;
    line-height: 1 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }

  .control-summary-chips {
    width: auto !important;
    min-width: 0 !important;
    flex: 1 1 auto !important;
    display: flex !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
    gap: 0.32rem !important;
    overflow: hidden !important;
  }

  .summary-chip {
    min-width: 0 !important;
    min-height: 22px !important;
    flex: 0 1 auto !important;
    padding: 0 0.48rem !important;
    font-size: 0.7rem !important;
    line-height: 1 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }

  .summary-chip.active {
    flex: 0 0 auto !important;
    max-width: 6.2rem !important;
  }
}

@media (max-width: 420px) {
  .chat-controls-summary {
    gap: 0.34rem !important;
  }

  .control-toggle-btn {
    height: 29px !important;
    min-height: 29px !important;
    max-width: 6.4rem !important;
    padding: 0 0.58rem !important;
    font-size: 0.76rem !important;
  }

  .control-summary-chips {
    gap: 0.26rem !important;
  }

  .summary-chip {
    min-height: 21px !important;
    padding: 0 0.42rem !important;
    font-size: 0.67rem !important;
  }

  .summary-chip.active {
    max-width: 5.2rem !important;
  }
}

@media (max-width: 360px) {
  .control-toggle-btn {
    max-width: 5.4rem !important;
    padding: 0 0.5rem !important;
  }

  .summary-chip {
    padding: 0 0.36rem !important;
  }
}
/* end nisb room composer mobile summary one-line patch */
</style>
