<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="nisb-modal-backdrop"
      @click.self="emitClose"
    >
      <div
        class="nisb-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="t('files.sendToLibrary.title')"
      >
        <div class="modal-header">
          <div class="title">📚 {{ t('files.sendToLibrary.title') }}</div>
          <button
            class="close-btn"
            type="button"
            :aria-label="t('common.close')"
            @click="emitClose"
          >
            ✕
          </button>
        </div>

        <div class="modal-body">
          <p class="hint">
            {{ sourceLabel }}
            <span class="mono">{{ sourceName || sourcePath }}</span>
          </p>

          <div class="field">
            <label class="field-label">{{ t('files.sendToLibrary.targetLibrary') }}</label>
            <div class="field-control">
              <select
                v-model="selectedLibraryId"
                class="select"
                :disabled="loadingLibraries || !hasLibraries"
              >
                <option
                  v-if="loadingLibraries"
                  disabled
                  value=""
                >
                  {{ t('files.sendToLibrary.loadingLibraries') }}
                </option>

                <option
                  v-else-if="!hasLibraries"
                  disabled
                  value=""
                >
                  {{ t('files.sendToLibrary.noLibraries') }}
                </option>

                <option
                  v-for="lib in libraries"
                  :key="pickLibraryId(lib) || (lib.library_name || lib.name || JSON.stringify(lib))"
                  :value="pickLibraryId(lib)"
                  :disabled="!pickLibraryId(lib)"
                >
                  {{ libraryDisplayName(lib) }}
                </option>
              </select>
            </div>
          </div>

          <div class="field">
            <label class="field-label">{{ t('files.sendToLibrary.mode') }}</label>
            <div class="field-control mode-row">
              <label class="radio-label">
                <input v-model="mode" type="radio" value="copy" />
                <span class="radio-text">{{ copyModeLabel }}</span>
              </label>

              <label class="radio-label">
                <input v-model="mode" type="radio" value="move" />
                <span class="radio-text">{{ moveModeLabel }}</span>
              </label>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn secondary" type="button" @click="emitClose">
            {{ t('common.cancel') }}
          </button>

          <button
            class="btn primary"
            type="button"
            :disabled="!canSend || loading"
            @click="handleSend"
          >
            <span v-if="loading">{{ t('files.sendToLibrary.sending') }}</span>
            <span v-else>{{ t('files.sendToLibrary.confirm') }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { normalizeToolResponse } from '../../composables/left_sidebar/actions/response_normalizer'

const props = defineProps({
  visible: { type: Boolean, default: false },
  sourcePath: { type: String, default: '' },
  sourceName: { type: String, default: '' },
  sourceType: { type: String, default: 'file' }
})

const emit = defineEmits(['close', 'sent'])

const { callTool } = useMCP()
const { t } = useI18n()

const libraries = ref([])
const loadingLibraries = ref(false)
const loading = ref(false)
const selectedLibraryId = ref('')
const mode = ref('copy')

const isDirectory = computed(() => props.sourceType === 'directory')

const hasLibraries = computed(() => Array.isArray(libraries.value) && libraries.value.length > 0)

const canSend = computed(() => {
  return !!props.sourcePath && !!selectedLibraryId.value && !loading.value && hasLibraries.value
})

const sourceLabel = computed(() => {
  return isDirectory.value
    ? t('files.sendToLibrary.sourceDirectory')
    : t('files.sendToLibrary.sourceFile')
})

const copyModeLabel = computed(() => {
  return isDirectory.value
    ? t('files.sendToLibrary.copyDirectory')
    : t('files.sendToLibrary.copyFile')
})

const moveModeLabel = computed(() => {
  return isDirectory.value
    ? t('files.sendToLibrary.moveDirectory')
    : t('files.sendToLibrary.moveFile')
})

function pickLibraryId(lib) {
  if (!lib || typeof lib !== 'object') return ''
  const a = String(lib.library_id || '').trim()
  if (a) return a
  const b = String(lib.libraryId || '').trim()
  if (b) return b
  const c = String(lib.id || '').trim()
  return c
}

function libraryDisplayName(lib) {
  return lib?.name || lib?.library_name || pickLibraryId(lib) || t('files.sendToLibrary.libraryIdMissing')
}

function toast(message, type = 'info', duration = 2600) {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type, duration } }))
}

watch(
  () => props.visible,
  async (val) => {
    if (!val) return
    await loadLibraries()
  }
)

watch(
  () => props.visible,
  (val) => {
    if (!val) return
    if (!mode.value) mode.value = 'copy'
  }
)

async function loadLibraries() {
  loadingLibraries.value = true
  try {
    const res = await callTool('nisb_library_list', {})
    const info = normalizeToolResponse(res, t('files.sendToLibrary.messages.loadLibrariesCompleted'))
    if (!info.success) {
      toast(
        t('files.sendToLibrary.messages.loadLibrariesFailed', {
          error: info.text || t('files.sendToLibrary.messages.unknownError')
        }),
        'error',
        3200
      )
      libraries.value = []
      selectedLibraryId.value = ''
      return
    }

    libraries.value = Array.isArray(res?.libraries) ? res.libraries : []

    if (!selectedLibraryId.value && libraries.value.length > 0) {
      const firstValid = libraries.value.find((x) => !!pickLibraryId(x))
      if (firstValid) {
        selectedLibraryId.value = pickLibraryId(firstValid)
      }
    }

    if (selectedLibraryId.value) return
    selectedLibraryId.value = ''
  } catch (e) {
    libraries.value = []
    selectedLibraryId.value = ''
    toast(
      t('files.sendToLibrary.messages.loadLibrariesException', {
        error: e?.message || String(e)
      }),
      'error',
      3200
    )
  } finally {
    loadingLibraries.value = false
  }
}

function buildDefaultSuccessText() {
  if (isDirectory.value) {
    return mode.value === 'move'
      ? t('files.sendToLibrary.messages.directorySentMove')
      : t('files.sendToLibrary.messages.directorySentCopy')
  }

  return mode.value === 'move'
    ? t('files.sendToLibrary.messages.fileSentMove')
    : t('files.sendToLibrary.messages.fileSentCopy')
}

async function handleSend() {
  if (!canSend.value) return

  loading.value = true
  try {
    const isDir = isDirectory.value
    const toolName = isDir ? 'nisb_fs_send_dir_to_library' : 'nisb_fs_send_to_library'

    const payload = {
      library_id: selectedLibraryId.value,
      mode: mode.value
    }

    if (isDir) payload.source_dir = props.sourcePath
    else payload.source_path = props.sourcePath

    const res = await callTool(toolName, payload)

    const defaultText = buildDefaultSuccessText()
    const info = normalizeToolResponse(res, defaultText)

    if (!info.success) {
      toast(
        t('files.sendToLibrary.messages.sendFailed', {
          error: info.text || t('files.sendToLibrary.messages.sendFailedGeneric')
        }),
        'error',
        3600
      )
      return
    }

    toast(info.text || defaultText, info.isWarning ? 'warning' : 'success', 2600)

    emit('sent', {
      message: info.text || defaultText,
      result: res,
      normalized: info
    })

    if (mode.value === 'move') {
      window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    }

    emitClose()
  } catch (e) {
    toast(
      t('files.sendToLibrary.messages.sendException', {
        error: e?.message || String(e)
      }),
      'error',
      3600
    )
  } finally {
    loading.value = false
  }
}

function emitClose() {
  emit('close')
}
</script>

<style scoped>
.nisb-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.35);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 40;
}

.nisb-modal {
  width: 360px;
  max-width: 90vw;
  background: var(--editor-bg);
  border-radius: 12px;
  padding: 0.9rem 1rem 0.8rem;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
  color: var(--text-main);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.title {
  font-size: 0.95rem;
  font-weight: 600;
}

.close-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.1rem 0.2rem;
  border-radius: 999px;
  transition: all var(--transition-normal) var(--ease-smooth);
}

.close-btn:hover {
  background: var(--selected-bg);
  color: var(--selected);
}

.modal-body {
  font-size: 0.8rem;
  margin-top: 0.1rem;
}

.hint {
  margin: 0 0 0.6rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    'Liberation Mono', 'Courier New', monospace;
  color: var(--text-main);
}

.field {
  margin-bottom: 0.6rem;
}

.field-label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.field-control {
  display: flex;
  align-items: center;
}

.select {
  width: 100%;
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--sidebar-bg);
  color: var(--text-main);
  font-size: 0.8rem;
  outline: none;
  transition: all var(--transition-normal) var(--ease-smooth);
}

.select:focus {
  border-color: var(--selected);
  box-shadow: 0 0 0 1px rgba(60, 105, 188, 0.18);
}

.mode-row {
  gap: 0.6rem;
  justify-content: flex-start;
}

.radio-label {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.radio-text {
  white-space: nowrap;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  margin-top: 0.4rem;
}

.btn {
  min-width: 70px;
  padding: 0.32rem 0.6rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-normal) var(--ease-smooth);
}

.btn.secondary {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--line);
}

.btn.secondary:hover {
  background: var(--sidebar-bg);
}

.btn.primary {
  background: var(--selected);
  color: #fff;
  border-color: transparent;
}

.btn.primary:hover {
  filter: brightness(1.05);
}

.btn.primary:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
