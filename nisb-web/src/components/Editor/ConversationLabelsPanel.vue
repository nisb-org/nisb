<template>
  <Teleport to="body">
    <div
      class="labels-panel"
      @click.stop
      ref="panelRef"
      :style="panelStyle"
    >
      <div class="labels-panel-header">
        <span>{{ t('chat.labelsPanel.title') }}</span>
        <button
          class="labels-panel-close"
          type="button"
          :aria-label="t('common.close')"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>

      <div v-if="!currentConvId" class="labels-panel-empty">
        {{ t('chat.labelsPanel.states.selectConversationFirst') }}
      </div>

      <template v-else>
        <div class="labels-panel-section">
          <div class="labels-panel-subtitle">{{ t('chat.labelsPanel.sections.current') }}</div>
          <div v-if="labelsLoading" class="labels-panel-empty">
            {{ t('chat.labelsPanel.states.loading') }}
          </div>
          <div v-else-if="!allLabels.length && !currentConvLabels.length" class="labels-panel-empty">
            {{ t('chat.labelsPanel.states.empty') }}
          </div>
          <div v-else class="labels-chip-list">
            <button
              v-for="lab in mergedLabelOptions"
              :key="lab"
              type="button"
              class="label-chip"
              :class="{ selected: currentConvLabels.includes(lab) }"
              @click="toggleLabel(lab)"
            >
              {{ lab }}
            </button>
          </div>
        </div>

        <div class="labels-panel-section">
          <div class="labels-panel-subtitle">{{ t('chat.labelsPanel.sections.create') }}</div>
          <div class="labels-input-row">
            <input
              v-model="newLabelName"
              type="text"
              class="label-input"
              :placeholder="t('chat.labelsPanel.input.placeholder')"
              @keyup.enter="createLabel"
            />
            <button
              type="button"
              class="label-add-btn"
              @click="createLabel"
              :disabled="!newLabelName.trim()"
            >
              {{ t('chat.labelsPanel.actions.add') }}
            </button>
          </div>
        </div>

        <div class="labels-panel-footer">
          <button
            v-if="currentConvLabels.length"
            type="button"
            class="labels-clear-btn"
            @click="clearAllLabels"
          >
            {{ t('chat.labelsPanel.actions.clearAll') }}
          </button>
        </div>
      </template>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'

const props = defineProps({
  currentConvId: { type: [String, Number, null], default: null }
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const { callTool } = useMCP()

const labelsLoading = ref(false)
const allLabels = ref([])
const currentConvLabels = ref([])
const newLabelName = ref('')

const panelRef = ref(null)
const panelStyle = ref({})

function updatePanelPosition() {
  // Keep the panel fixed at the top-right and avoid the header area.
  panelStyle.value = {
    position: 'fixed',
    top: '46px',
    right: '10px',
    zIndex: 10000
  }
}

const mergedLabelOptions = computed(() => {
  const set = new Set()
  currentConvLabels.value.forEach((l) => set.add(l))
  allLabels.value.forEach((l) => set.add(l))
  return Array.from(set)
})

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', {
    detail: { message, type }
  }))
}

function updateLabelsFailedMessage(error) {
  return t('chat.labelsPanel.toast.updateFailed', {
    error: error || t('common.unknownError')
  })
}

async function fetchAllLabels() {
  try {
    labelsLoading.value = true
    const res = await callTool('nisb_chat_list_labels', {})
    if (res && res.status === 'success' && Array.isArray(res.labels)) {
      allLabels.value = res.labels.map((x) => x.label)
    } else {
      allLabels.value = []
    }
  } catch (e) {
    console.error('[conversation labels] failed to fetch all labels:', e)
    allLabels.value = []
  } finally {
    labelsLoading.value = false
  }
}

async function fetchCurrentConvLabels() {
  if (!props.currentConvId) {
    currentConvLabels.value = []
    return
  }
  try {
    labelsLoading.value = true
    const res = await callTool('nisb_chat_get_labels', {
      conv_id: props.currentConvId
    })
    if (res && res.status === 'success' && Array.isArray(res.labels)) {
      currentConvLabels.value = res.labels
    } else {
      currentConvLabels.value = []
    }
  } catch (e) {
    console.error('[conversation labels] failed to fetch labels for current conversation:', e)
    currentConvLabels.value = []
  } finally {
    labelsLoading.value = false
  }
}

async function updateConvLabels(labelsArr) {
  if (!props.currentConvId) return
  try {
    const res = await callTool('nisb_chat_update_labels', {
      conv_id: props.currentConvId,
      labels: labelsArr
    })

    if (res && res.status === 'success') {
      currentConvLabels.value = res.labels || labelsArr
      window.dispatchEvent(
        new CustomEvent('nisb-chat-labels-updated', {
          detail: {
            convId: props.currentConvId,
            labels: currentConvLabels.value
          }
        })
      )
    } else {
      toast(updateLabelsFailedMessage(res && res.message ? res.message : ''), 'error')
    }
  } catch (e) {
    toast(updateLabelsFailedMessage(e?.message), 'error')
  }
}

function toggleLabel(label) {
  const exists = currentConvLabels.value.includes(label)
  const next = exists
    ? currentConvLabels.value.filter((l) => l !== label)
    : [...currentConvLabels.value, label]
  updateConvLabels(next)
}

function createLabel() {
  const name = newLabelName.value.trim()
  if (!name || !props.currentConvId) return
  if (currentConvLabels.value.includes(name)) {
    newLabelName.value = ''
    return
  }

  const next = [...currentConvLabels.value, name]
  updateConvLabels(next)

  if (!allLabels.value.includes(name)) {
    allLabels.value = [...allLabels.value, name]
  }

  newLabelName.value = ''
}

function clearAllLabels() {
  if (!props.currentConvId) return
  if (!currentConvLabels.value.length) return
  if (!window.confirm(t('chat.labelsPanel.confirm.clearAll'))) return
  updateConvLabels([])
}

watch(
  () => props.currentConvId,
  (val) => {
    currentConvLabels.value = []
    if (val) {
      fetchAllLabels()
      fetchCurrentConvLabels()
    }
  },
  { immediate: true }
)

onMounted(() => {
  nextTick(() => updatePanelPosition())
  window.addEventListener('resize', updatePanelPosition)
  window.addEventListener('scroll', updatePanelPosition, true)
})

onUnmounted(() => {
  window.removeEventListener('resize', updatePanelPosition)
  window.removeEventListener('scroll', updatePanelPosition, true)
})

defineExpose({ currentConvLabels })
</script>

<style scoped>
.labels-panel {
  width: min(320px, calc(100vw - 20px));
  min-width: 260px;
  max-width: 320px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 0.58rem;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 18px 42px rgba(0, 0, 0, 0.22),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow: hidden;
}

.labels-panel-header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  padding-bottom: 0.42rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 810;
  line-height: 1.35;
}

.labels-panel-header > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.labels-panel-close {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  min-width: 30px;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 760;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.labels-panel-close:hover,
.labels-panel-close:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.labels-panel-close:active {
  transform: translateY(1px);
}

.labels-panel-section {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
}

.labels-panel-subtitle {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.73rem;
  font-weight: 780;
  line-height: 1.25;
  letter-spacing: 0.035em;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.labels-chip-list {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  max-height: 150px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
  scrollbar-width: thin;
}

.labels-chip-list::-webkit-scrollbar {
  width: 8px;
}

.labels-chip-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.labels-panel-empty {
  padding: 0.72rem 0.62rem;
  border: 1px dashed color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.label-chip {
  max-width: 100%;
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.28rem;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 730;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    font-weight 0.15s ease;
}

.label-chip:hover,
.label-chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  font-weight: 790;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.label-chip.selected {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 74%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  font-weight: 840;
  letter-spacing: -0.01em;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent);
}

.labels-input-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
}

.label-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 31px;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 64%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 690;
  line-height: 1;
  padding: 0 0.58rem;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.label-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.label-input:hover,
.label-input:focus {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 34%, transparent),
      color-mix(in srgb, var(--editor-bg) 64%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.label-add-btn {
  flex: 0 0 auto;
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.label-add-btn:hover:not(:disabled),
.label-add-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.label-add-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.label-add-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.labels-panel-footer {
  min-width: 0;
  display: flex;
  justify-content: flex-end;
  margin-top: -0.08rem;
}

.labels-clear-btn {
  min-height: 26px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.58rem;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.06);
  color: color-mix(in srgb, #ef4444 82%, var(--text-secondary));
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  text-decoration: none;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.labels-clear-btn:hover,
.labels-clear-btn:focus-visible {
  border-color: rgba(239, 68, 68, 0.56);
  background: rgba(239, 68, 68, 0.11);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 6px 14px rgba(239, 68, 68, 0.08);
  outline: none;
}

.labels-clear-btn:active {
  transform: translateY(1px);
}

@media (max-width: 520px) {
  .labels-panel {
    width: calc(100vw - 18px);
    min-width: 0;
    max-width: none;
    right: 9px !important;
  }

  .labels-input-row {
    align-items: stretch;
    flex-direction: column;
  }

  .label-add-btn {
    width: 100%;
  }

  .labels-clear-btn {
    width: 100%;
  }
}
</style>

