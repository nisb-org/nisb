<template>
  <transition name="readopt-fade">
    <div
      v-if="modelValue"
      class="readopt-overlay"
      @mousedown.self="emitClose"
      @touchstart.self="emitClose"
    >
      <div class="readopt-panel" role="dialog" aria-modal="true" :aria-labelledby="dialogTitleId">
        <div class="readopt-top">
          <div class="readopt-heading">
            <div :id="dialogTitleId" class="readopt-title">
              {{ t('rightSidebar.readingOptimizer.title') }}
            </div>
            <div class="readopt-subline">
              <span class="readopt-mode-chip">
                {{ modeLabel }}
              </span>
              <span class="readopt-cap-chip" :class="{ full: customLimitReached }">
                {{ customPresets.length }}/{{ MAX_CUSTOM_PRESETS }}
              </span>
            </div>
          </div>

          <button
            class="readopt-close"
            @click="emitClose"
            :title="t('rightSidebar.readingOptimizer.actions.close')"
            :aria-label="t('rightSidebar.readingOptimizer.actions.close')"
            type="button"
          >
            ×
          </button>
        </div>

        <div class="readopt-body">
          <div class="readopt-card">
            <div class="readopt-card-head">
              <div class="readopt-section-title">
                {{ t('rightSidebar.readingOptimizer.sections.professionalPresets') }}
              </div>
              <div v-if="mode === 'standard'" class="readopt-inline-hint">
                {{ t('rightSidebar.readingOptimizer.hints.standard') }}
              </div>
            </div>

            <div class="readopt-presets">
              <button
                v-for="preset in professionalPresets"
                :key="preset.id"
                class="preset-btn"
                :class="{ active: mode === preset.id }"
                type="button"
                @click="emitPreset(preset.id)"
              >
                {{ t(preset.labelKey) }}
              </button>
            </div>
          </div>

          <div class="readopt-card">
            <div class="readopt-card-head">
              <div class="readopt-section-title">
                {{ t('rightSidebar.readingOptimizer.modes.custom') }}
              </div>
              <div class="readopt-inline-hint">
                {{ t('rightSidebar.readingOptimizer.status.applied') }}
              </div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.brightness') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="70"
                max="110"
                step="1"
                v-model.number="draft.brightness"
                @input="emitApply"
              />
              <div class="readopt-value">{{ draft.brightness }}%</div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.fontSize') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="13"
                max="22"
                step="1"
                v-model.number="draft.fontSize"
                @input="emitApply"
              />
              <div class="readopt-value">{{ draft.fontSize }}px</div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.lineHeight') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="1.2"
                max="2.2"
                step="0.05"
                v-model.number="draft.lineHeight"
                @input="emitApply"
              />
              <div class="readopt-value">{{ draft.lineHeight.toFixed(2) }}</div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.padding') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="0"
                max="36"
                step="1"
                v-model.number="draft.padding"
                @input="emitApply"
              />
              <div class="readopt-value">{{ draft.padding }}px</div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.warmth') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="0"
                max="100"
                step="1"
                v-model.number="draft.warmth"
                @input="emitApply"
              />
              <div class="readopt-value">{{ warmthLabel }}</div>
            </div>

            <div class="readopt-row">
              <div class="readopt-label">
                {{ t('rightSidebar.readingOptimizer.labels.smooth') }}
              </div>
              <input
                class="readopt-range"
                type="range"
                min="0"
                max="100"
                step="1"
                v-model.number="draft.smooth"
                @input="emitApply"
              />
              <div class="readopt-value">{{ smoothLabel }}</div>
            </div>
          </div>

          <div class="readopt-card">
            <div class="readopt-card-head">
              <div class="readopt-section-title">
                {{ t('rightSidebar.readingOptimizer.sections.customPresets') }}
              </div>
              <div class="readopt-cap-chip" :class="{ full: customLimitReached }">
                {{ customPresets.length }}/{{ MAX_CUSTOM_PRESETS }}
              </div>
            </div>

            <div class="custom-actions">
              <button
                class="mini-btn primary"
                type="button"
                @click="openNamePrompt"
                :disabled="saving || customLimitReached"
              >
                {{ t('rightSidebar.readingOptimizer.actions.saveCurrentAsPreset') }}
              </button>
            </div>

            <div v-if="showNamePrompt" class="name-prompt">
              <input
                class="name-input"
                v-model.trim="presetName"
                :placeholder="t('rightSidebar.readingOptimizer.custom.namePlaceholder')"
                maxlength="18"
                @keydown.enter.prevent="confirmSavePreset"
              />

              <div class="name-actions">
                <button
                  class="mini-btn primary"
                  type="button"
                  @click="confirmSavePreset"
                  :disabled="saving"
                >
                  {{
                    saving
                      ? t('rightSidebar.readingOptimizer.status.saving')
                      : t('rightSidebar.readingOptimizer.actions.save')
                  }}
                </button>
                <button class="mini-btn" type="button" @click="cancelSavePreset" :disabled="saving">
                  {{ t('rightSidebar.readingOptimizer.actions.cancel') }}
                </button>
              </div>

              <div v-if="nameError" class="name-error">{{ nameError }}</div>
            </div>

            <div v-if="customPresets.length === 0" class="custom-empty">
              {{ t('rightSidebar.readingOptimizer.custom.empty') }}
            </div>

            <div v-else class="custom-list" role="list">
              <div v-for="p in customPresets" :key="p.id" class="custom-item" role="listitem">
                <div class="custom-item-main">
                  <button class="custom-chip" type="button" @click="applyCustomPreset(p)" :title="p.name">
                    <span class="custom-name">{{ p.name }}</span>
                    <span v-if="isDefaultPreset(p)" class="default-badge">
                      {{ t('rightSidebar.readingOptimizer.custom.defaultBadge') }}
                    </span>
                  </button>
                </div>

                <div class="custom-item-actions">
                  <button
                    v-if="!isDefaultPreset(p)"
                    class="mini-btn"
                    type="button"
                    @click="setDefaultOnServer(p)"
                    :title="t('rightSidebar.readingOptimizer.actions.setDefault')"
                  >
                    {{ t('rightSidebar.readingOptimizer.actions.setDefault') }}
                  </button>
                  <button
                    v-else
                    class="mini-btn danger"
                    type="button"
                    @click="clearDefaultOnServer"
                    :title="t('rightSidebar.readingOptimizer.actions.clearDefault')"
                  >
                    {{ t('rightSidebar.readingOptimizer.actions.clearDefault') }}
                  </button>
                  <button
                    class="custom-del"
                    type="button"
                    @click="deleteCustomPreset(p.id)"
                    :title="t('rightSidebar.readingOptimizer.actions.deletePreset')"
                    :aria-label="t('rightSidebar.readingOptimizer.actions.deletePreset')"
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>

            <div v-if="statusMsg" class="status-msg">{{ statusMsg }}</div>
          </div>
        </div>

        <div class="readopt-footer">
          <button class="footer-btn primary" type="button" @click="onSaveClick">
            {{ t('rightSidebar.readingOptimizer.actions.save') }}
          </button>
          <button class="footer-btn" type="button" @click="onResetClick">
            {{ t('rightSidebar.readingOptimizer.actions.reset') }}
          </button>
          <button
            class="footer-btn danger"
            type="button"
            :disabled="mode === 'standard'"
            @click="onDisableClick"
          >
            {{ disableButtonText }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import useMCP from '../../composables/useMCP'

const { callTool } = useMCP()
const { t } = useI18n()

const MAX_CUSTOM_PRESETS = 6
const dialogTitleId = 'right-sidebar-reading-optimizer-title'

const professionalPresets = [
  { id: 'standard', labelKey: 'rightSidebar.readingOptimizer.presets.standard' },
  { id: 'eye', labelKey: 'rightSidebar.readingOptimizer.presets.eye' },
  { id: 'novel', labelKey: 'rightSidebar.readingOptimizer.presets.novel' },
  { id: 'academic', labelKey: 'rightSidebar.readingOptimizer.presets.academic' },
  { id: 'code', labelKey: 'rightSidebar.readingOptimizer.presets.code' }
]

const modeLabelKeys = {
  standard: 'rightSidebar.readingOptimizer.modes.standard',
  custom: 'rightSidebar.readingOptimizer.modes.custom',
  eye: 'rightSidebar.readingOptimizer.modes.eye',
  novel: 'rightSidebar.readingOptimizer.modes.novel',
  academic: 'rightSidebar.readingOptimizer.modes.academic',
  code: 'rightSidebar.readingOptimizer.modes.code'
}

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mode: { type: String, default: 'standard' },
  prefs: {
    type: Object,
    default: () => ({
      brightness: 100,
      fontSize: 16,
      lineHeight: 1.6,
      padding: 0,
      warmth: 0,
      smooth: 0
    })
  }
})

const emit = defineEmits(['update:modelValue', 'apply', 'preset', 'save', 'reset'])

const draft = reactive({
  brightness: 100,
  fontSize: 16,
  lineHeight: 1.6,
  padding: 0,
  warmth: 0,
  smooth: 0
})

const customPresets = ref([])
const showNamePrompt = ref(false)
const presetName = ref('')
const nameError = ref('')
const statusMsg = ref('')
const serverDefault = ref(null)
const saving = ref(false)

const warmthLabel = computed(() => {
  if (draft.warmth >= 70) return t('rightSidebar.readingOptimizer.values.warmthWarm')
  if (draft.warmth >= 20) return t('rightSidebar.readingOptimizer.values.warmthNeutral')
  return t('rightSidebar.readingOptimizer.values.warmthCool')
})

const smoothLabel = computed(() => {
  if (draft.smooth >= 85) return t('rightSidebar.readingOptimizer.values.smoothMax')
  if (draft.smooth >= 60) return t('rightSidebar.readingOptimizer.values.smoothComfort')
  return t('rightSidebar.readingOptimizer.values.smoothFast')
})

const disableButtonText = computed(() =>
  props.mode === 'standard'
    ? t('rightSidebar.readingOptimizer.actions.disabled')
    : t('rightSidebar.readingOptimizer.actions.disable')
)

const customLimitReached = computed(() => customPresets.value.length >= MAX_CUSTOM_PRESETS)

const modeLabel = computed(() => {
  const key = modeLabelKeys[props.mode] || modeLabelKeys.custom
  return t(key)
})

function setStatus(msg) {
  const next = String(msg || '')
  statusMsg.value = next
  if (!next) return
  window.setTimeout(() => {
    if (statusMsg.value === next) statusMsg.value = ''
  }, 1800)
}

function applyPrefsToDraft(prefs = {}) {
  draft.brightness = Number(prefs.brightness ?? 100)
  draft.fontSize = Number(prefs.fontSize ?? 16)
  draft.lineHeight = Number(prefs.lineHeight ?? 1.6)
  draft.padding = Number(prefs.padding ?? 0)
  draft.warmth = Number(prefs.warmth ?? 0)
  draft.smooth = Number(prefs.smooth ?? 0)
}

function syncDraftFromProps() {
  applyPrefsToDraft(props.prefs || {})
}

function emitClose() {
  emit('update:modelValue', false)
}

function emitApply() {
  emit('apply', {
    brightness: draft.brightness,
    fontSize: draft.fontSize,
    lineHeight: draft.lineHeight,
    padding: draft.padding,
    warmth: draft.warmth,
    smooth: draft.smooth
  })
}

function emitPreset(id) {
  emit('preset', id)
}

function onSaveClick() {
  emit('save')
  setStatus(t('rightSidebar.readingOptimizer.status.saved'))
}

function onResetClick() {
  emit('reset')
  setStatus(t('rightSidebar.readingOptimizer.status.reset'))
}

function onDisableClick() {
  emit('reset')
  setStatus(t('rightSidebar.readingOptimizer.hints.standard'))
}

async function fetchServerDefault() {
  try {
    const res = await callTool('nisb_readopt_get_default_preset', {})
    if (res && res.hasdefault && res.preset) {
      serverDefault.value = {
        presetid: String(res.preset.presetid),
        name: String(res.preset.name),
        prefs: res.preset.prefs || null
      }
    } else {
      serverDefault.value = null
    }
  } catch {
    serverDefault.value = null
  }
}

async function fetchServerCustomPresets() {
  try {
    const res = await callTool('nisb_readopt_get_custom_presets', {})
    if (res && res.ok && Array.isArray(res.presets)) {
      customPresets.value = res.presets
        .filter(
          (x) =>
            x &&
            typeof x === 'object' &&
            typeof x.id === 'string' &&
            typeof x.name === 'string' &&
            x.prefs &&
            typeof x.prefs === 'object'
        )
        .slice(0, MAX_CUSTOM_PRESETS)
    } else {
      customPresets.value = []
    }
  } catch {
    customPresets.value = []
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    syncDraftFromProps()
    showNamePrompt.value = false
    presetName.value = ''
    nameError.value = ''
    statusMsg.value = ''
    saving.value = false
    await fetchServerDefault()
    await fetchServerCustomPresets()
  },
  { immediate: true }
)

watch(
  () => props.prefs,
  () => {
    if (props.modelValue) syncDraftFromProps()
  },
  { deep: true }
)

function openNamePrompt() {
  if (customLimitReached.value) {
    setStatus(t('rightSidebar.readingOptimizer.status.maxCustom', { count: MAX_CUSTOM_PRESETS }))
    return
  }
  showNamePrompt.value = true
  presetName.value = ''
  nameError.value = ''
}

function cancelSavePreset() {
  if (saving.value) return
  showNamePrompt.value = false
  presetName.value = ''
  nameError.value = ''
}

function normalizeName(s) {
  return String(s || '').trim().replace(/\s+/g, ' ')
}

async function confirmSavePreset() {
  if (saving.value) return

  const name = normalizeName(presetName.value)
  if (!name) {
    nameError.value = t('rightSidebar.readingOptimizer.errors.nameRequired')
    return
  }
  if (name.length > 18) {
    nameError.value = t('rightSidebar.readingOptimizer.errors.nameTooLong')
    return
  }
  const exists = customPresets.value.some((x) => String(x?.name || '').toLowerCase() === name.toLowerCase())
  if (exists) {
    nameError.value = t('rightSidebar.readingOptimizer.errors.nameExists')
    return
  }

  const item = {
    id: `cp_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    name,
    prefs: {
      brightness: Number(draft.brightness),
      fontSize: Number(draft.fontSize),
      lineHeight: Number(draft.lineHeight),
      padding: Number(draft.padding),
      warmth: Number(draft.warmth),
      smooth: Number(draft.smooth)
    }
  }

  saving.value = true
  setStatus(t('rightSidebar.readingOptimizer.status.saving'))

  try {
    const res = await callTool('nisb_readopt_save_custom_preset', {
      presetid: item.id,
      name: item.name,
      prefs: item.prefs
    })

    if (res && res.ok) {
      customPresets.value = [item, ...customPresets.value].slice(0, MAX_CUSTOM_PRESETS)
      showNamePrompt.value = false
      presetName.value = ''
      nameError.value = ''
      setStatus(t('rightSidebar.readingOptimizer.status.savedNamed', { name }))
      await fetchServerCustomPresets()
      await fetchServerDefault()
      return
    }

    setStatus(t('rightSidebar.readingOptimizer.errors.saveFailed'))
  } catch {
    setStatus(t('rightSidebar.readingOptimizer.errors.saveFailed'))
  } finally {
    saving.value = false
  }
}

function applyCustomPreset(p) {
  const prefs = p?.prefs
  if (!prefs || typeof prefs !== 'object') return
  applyPrefsToDraft(prefs)
  emitApply()
  setStatus(p?.name || t('rightSidebar.readingOptimizer.status.applied'))
}

function isDefaultPreset(p) {
  return !!(serverDefault.value && p && String(p.id) === String(serverDefault.value.presetid))
}

async function setDefaultOnServer(p) {
  try {
    await callTool('nisb_readopt_set_default_preset', { presetid: p.id, name: p.name, prefs: p.prefs })
    await fetchServerDefault()
    setStatus(t('rightSidebar.readingOptimizer.status.defaultNamed', { name: p.name }))
  } catch {
    setStatus(t('rightSidebar.readingOptimizer.errors.setDefaultFailed'))
  }
}

async function clearDefaultOnServer() {
  try {
    await callTool('nisb_readopt_clear_default_preset', {})
    serverDefault.value = null
    emit('reset')
    setStatus(t('rightSidebar.readingOptimizer.hints.standard'))
  } catch {
    setStatus(t('rightSidebar.readingOptimizer.errors.clearDefaultFailed'))
  }
}

async function deleteCustomPreset(id) {
  try {
    const res = await callTool('nisb_readopt_delete_custom_preset', { presetid: id })
    if (res && res.ok) {
      await fetchServerCustomPresets()
      await fetchServerDefault()
      setStatus(t('rightSidebar.readingOptimizer.status.deleted'))
    } else {
      setStatus(t('rightSidebar.readingOptimizer.errors.deleteFailed'))
    }
  } catch {
    setStatus(t('rightSidebar.readingOptimizer.errors.deleteFailed'))
  }
}
</script>

<style scoped>
.readopt-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 64px 16px 16px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--selected) 10%, transparent), transparent 34%),
    rgba(0, 0, 0, 0.18);
}

.readopt-panel {
  width: min(460px, calc(100vw - 32px));
  max-height: calc(100vh - 80px);
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 94%, transparent),
      color-mix(in srgb, var(--editor-bg) 88%, transparent)
    );
  box-shadow:
    0 22px 70px rgba(0, 0, 0, 0.26),
    0 2px 14px rgba(0, 0, 0, 0.16);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(14px);
}

.readopt-top {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: calc(14px + env(safe-area-inset-top)) 14px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
}

.readopt-heading {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.readopt-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.96rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.readopt-subline {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  min-width: 0;
}

.readopt-mode-chip,
.readopt-cap-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 32%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 58%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.readopt-cap-chip {
  border-color: color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  color: var(--text-secondary);
}

.readopt-cap-chip.full {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.readopt-close {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.readopt-close:hover {
  background: color-mix(in srgb, var(--selected-bg) 48%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.readopt-close:active {
  transform: translateY(1px);
}

.readopt-body {
  flex: 1 1 auto;
  min-height: 0;
  padding: 12px;
  display: grid;
  gap: 12px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}

.readopt-card {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow: inset 0 1px 0 color-mix(in srgb, #fff 4%, transparent);
}

.readopt-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.readopt-section-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.readopt-inline-hint {
  flex: 0 1 auto;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.readopt-row {
  display: grid;
  grid-template-columns: minmax(82px, 0.86fr) minmax(120px, 1.45fr) minmax(58px, 0.55fr);
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.readopt-label {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.readopt-range {
  width: 100%;
  min-width: 0;
  accent-color: var(--selected);
}

.readopt-value {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.75rem;
  font-weight: 720;
  line-height: 1.35;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.readopt-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.preset-btn,
.mini-btn,
.footer-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 0 0.74rem;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 72%, transparent);
  color: var(--text-secondary);
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    opacity 0.16s ease,
    transform 0.16s ease;
}

.preset-btn:hover,
.mini-btn:hover,
.footer-btn:hover {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.preset-btn:active,
.mini-btn:active,
.footer-btn:active {
  transform: translateY(1px);
}

.preset-btn.active {
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 72%, var(--editor-bg));
  color: var(--selected);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, #fff 4%, transparent);
}

.custom-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mini-btn.primary,
.footer-btn.primary {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--selected) 88%, #1f2937);
  color: #fff;
}

.mini-btn.danger,
.footer-btn.danger {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.mini-btn.danger:hover,
.footer-btn.danger:hover {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.mini-btn:disabled,
.footer-btn:disabled {
  opacity: 0.56;
  cursor: not-allowed;
  transform: none;
}

.name-prompt {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
}

.name-input {
  width: 100%;
  min-width: 0;
  height: 34px;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 82%, transparent);
  color: var(--text-main, var(--text));
  padding: 0 0.72rem;
  font-family: inherit;
  font-size: 0.82rem;
  outline: none;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.name-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.name-input:focus {
  border-color: color-mix(in srgb, var(--selected) 46%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 92%, transparent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected-bg) 56%, transparent);
}

.name-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.name-error {
  padding: 8px 9px;
  border: 1px solid rgba(239, 68, 68, 0.32);
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.custom-empty {
  padding: 10px;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 60%, transparent);
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.custom-list {
  display: grid;
  gap: 8px;
  max-height: 220px;
  overflow: auto;
  padding-right: 2px;
  scrollbar-width: thin;
}

.custom-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 74%, transparent);
}

.custom-item-main {
  min-width: 0;
}

.custom-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--sidebar-bg) 80%, transparent);
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  cursor: pointer;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.custom-chip:hover {
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  color: var(--selected);
}

.custom-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.default-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  padding: 0 7px;
  border: 1px solid color-mix(in srgb, var(--selected) 34%, var(--line));
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected-bg) 62%, var(--editor-bg));
  color: var(--selected);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
}

.custom-item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.custom-del {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 31px;
  height: 31px;
  border-radius: 999px;
  border: 1px solid rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease;
}

.custom-del:hover {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.12);
}

.custom-del:active {
  transform: translateY(1px);
}

.status-msg {
  padding: 8px 9px;
  border: 1px solid color-mix(in srgb, var(--selected) 24%, var(--line));
  border-radius: 11px;
  background: color-mix(in srgb, var(--selected-bg) 34%, var(--editor-bg));
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.readopt-footer {
  flex: 0 0 auto;
  display: flex;
  gap: 10px;
  padding: 12px;
  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

.footer-btn {
  flex: 1 1 0;
  min-height: 36px;
}

.readopt-fade-enter-active,
.readopt-fade-leave-active {
  transition: opacity 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.readopt-fade-enter-from,
.readopt-fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .readopt-overlay {
    padding: 0;
    align-items: stretch;
    justify-content: stretch;
    background: rgba(0, 0, 0, 0.18);
  }

  .readopt-panel {
    width: 100%;
    height: 100%;
    max-height: 100%;
    border-radius: 0;
    box-shadow: none;
  }

  .readopt-row {
    grid-template-columns: minmax(92px, 0.9fr) minmax(120px, 1.35fr) minmax(60px, 0.55fr);
  }
}

@media (max-width: 560px) {
  .readopt-card-head,
  .custom-item {
    grid-template-columns: 1fr;
  }

  .readopt-card-head {
    display: grid;
  }

  .readopt-row {
    grid-template-columns: 1fr;
    gap: 7px;
  }

  .readopt-value {
    text-align: left;
  }

  .readopt-presets,
  .name-actions,
  .custom-actions,
  .custom-item-actions,
  .readopt-footer {
    display: grid;
    grid-template-columns: 1fr;
  }

  .preset-btn,
  .mini-btn,
  .footer-btn {
    width: 100%;
    white-space: normal;
  }

  .custom-chip {
    width: 100%;
    justify-content: flex-start;
  }

  .custom-item-actions {
    width: 100%;
  }
}
</style>
