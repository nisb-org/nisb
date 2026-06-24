<template>
  <div class="rag-wrapper" ref="wrapRef">
    <button
      ref="btnRef"
      type="button"
      class="rag-btn"
      :class="{ active: mode !== 'off', open }"
      @click.stop="toggleMenu"
      :title="btnLabel"
      :aria-label="t('chat.ragMenu.button.ariaLabel')"
      aria-haspopup="menu"
      :aria-expanded="open ? 'true' : 'false'"
    >
      <span class="btn-icon" aria-hidden="true">R</span>
      <span class="btn-text" :title="btnLabel">{{ btnLabel }}</span>
      <span class="btn-caret" aria-hidden="true">▾</span>
    </button>

    <div
      v-if="open"
      class="rag-popover-scrim"
      aria-hidden="true"
      @click.stop="closeAll"
    ></div>

    <div
      v-if="open"
      class="rag-menu"
      :style="menuStyle"
      role="menu"
      :aria-label="t('chat.ragMenu.button.ariaLabel')"
      @click.stop
    >
      <div class="rag-menu-head">
        <div class="rag-menu-title">{{ t('chat.ragMenu.sections.retrievalMode') }}</div>
        <div class="rag-status-row">
          <span class="status-chip primary">{{ _modeLabel(mode) }}</span>
          <span v-if="mode === 'cite' || mode === 'ground'" class="status-chip">
            {{ ctxGroup ? t('chat.ragMenu.scope.groupedInline') : _scopeLabel(scope) }}
          </span>
          <span class="status-chip" :class="{ active: docTimeEnabled }">{{ docTimeHintInline }}</span>
          <span class="status-chip" :class="{ active: agentEnabled }">
            {{ t('chat.ragMenu.sections.agent') }} · {{ agentEnabled ? t('chat.ragMenu.common.on') : t('chat.ragMenu.common.off') }}
          </span>
        </div>
      </div>

      <div class="rag-section-title">{{ t('chat.ragMenu.sections.retrievalMode') }}</div>

      <div class="rag-item" @click="setModeAndClose('off')">
        <span class="dot" :class="{ on: mode === 'off' }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.modes.off') }}</span>
          <span class="mini-hint">{{ t('chat.ragMenu.items.offHint') }}</span>
        </span>
      </div>

      <div class="rag-item" @click="setModeAndClose('auto')">
        <span class="dot" :class="{ on: mode === 'auto' }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.modes.auto') }}</span>
          <span class="mini-hint">{{ t('chat.ragMenu.items.autoHint') }}</span>
        </span>
      </div>

      <div class="sep"></div>

      <div class="rag-item" :class="{ hoverActive: ctxOpen && ctxMode === 'cite' }" @click="handleModeClick('cite')">
        <span class="dot" :class="{ on: mode === 'cite' }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.modes.cite') }}</span>
          <span class="mini-hint">{{ t('chat.ragMenu.items.citeHint', { scope: scopeHintInline }) }}</span>
        </span>
      </div>

      <div v-if="ctxOpen && ctxMode === 'cite'" class="rag-subpanel">
        <RagContextCard variant="menu" mode="cite" :applyModeOnSelect="true" @close="closeAll" />
      </div>

      <div class="rag-item" :class="{ hoverActive: ctxOpen && ctxMode === 'ground' }" @click="handleModeClick('ground')">
        <span class="dot" :class="{ on: mode === 'ground' }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.modes.ground') }}</span>
          <span class="mini-hint">{{ t('chat.ragMenu.items.groundHint', { scope: scopeHintInline }) }}</span>
        </span>
      </div>

      <div v-if="ctxOpen && ctxMode === 'ground'" class="rag-subpanel">
        <RagContextCard variant="menu" mode="ground" :applyModeOnSelect="true" @close="closeAll" />
      </div>

      <div class="sep"></div>

      <div class="rag-section-title">{{ t('chat.ragMenu.sections.docTime') }}</div>

      <div class="rag-item" @click.stop="toggleDocTimeEnabled">
        <span class="dot" :class="{ on: docTimeEnabled }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.docTime.toggleLabel') }}</span>
          <span class="mini-hint">{{ docTimeHintInline }}</span>
        </span>
      </div>

      <div v-if="docTimeEnabled" class="doc-time-panel" @click.stop>
        <div class="doc-time-mode-switch">
          <button
            type="button"
            class="doc-mode-chip"
            :class="{ active: docTimeMode === 'days' }"
            @click.stop="setDocTimeModeOnly('days')"
          >
            {{ t('chat.ragMenu.docTime.mode.days') }}
          </button>
          <button
            type="button"
            class="doc-mode-chip"
            :class="{ active: docTimeMode === 'relative' }"
            @click.stop="setDocTimeModeOnly('relative')"
          >
            {{ t('chat.ragMenu.docTime.mode.relative') }}
          </button>
        </div>

        <template v-if="docTimeMode === 'days'">
          <div class="doc-time-row">
            <span class="doc-label">{{ t('chat.ragMenu.docTime.quick') }}</span>
            <div class="doc-chip-list">
              <button
                v-for="n in [1, 3, 7, 30]"
                :key="`days-${n}`"
                type="button"
                class="doc-chip"
                :class="{ active: Number(docTimeDays) === n }"
                @click.stop="pickDocTimeDays(n)"
              >
                {{ n }}d
              </button>
            </div>
          </div>

          <div class="doc-time-row doc-time-inline-row">
            <span class="doc-label">{{ t('chat.ragMenu.docTime.custom') }}</span>
            <input
              v-model.number="draftDocDays"
              type="number"
              min="0"
              max="3650"
              step="1"
              class="doc-input doc-input-sm"
              inputmode="numeric"
              @change="applyDocTimeDays()"
              @blur="applyDocTimeDays()"
            />
            <span class="doc-suffix">{{ t('chat.ragMenu.docTime.daysUnit') }}</span>
          </div>
        </template>

        <template v-else>
          <div class="doc-time-grid">
            <label class="doc-field">
              <span class="doc-field-label">{{ t('chat.ragMenu.docTime.relativeLabels.older') }}</span>
              <div class="doc-field-input-wrap">
                <input
                  v-model.number="draftOlderDaysAgo"
                  type="number"
                  min="0"
                  max="3650"
                  step="1"
                  class="doc-input"
                  inputmode="numeric"
                  @change="applyDocTimeRelative()"
                  @blur="applyDocTimeRelative()"
                />
                <span class="doc-suffix">{{ t('chat.ragMenu.docTime.daysAgoUnit') }}</span>
              </div>
            </label>

            <label class="doc-field">
              <span class="doc-field-label">{{ t('chat.ragMenu.docTime.relativeLabels.newer') }}</span>
              <div class="doc-field-input-wrap">
                <input
                  v-model.number="draftNewerDaysAgo"
                  type="number"
                  min="0"
                  max="3650"
                  step="1"
                  class="doc-input"
                  inputmode="numeric"
                  @change="applyDocTimeRelative()"
                  @blur="applyDocTimeRelative()"
                />
                <span class="doc-suffix">{{ t('chat.ragMenu.docTime.daysAgoUnit') }}</span>
              </div>
            </label>
          </div>

          <div class="doc-time-row">
            <span class="doc-label">{{ t('chat.ragMenu.docTime.quick') }}</span>
            <div class="doc-chip-list">
              <button type="button" class="doc-chip" @click.stop="setDocTimeRelativePreset(14, 7)">14~7</button>
              <button type="button" class="doc-chip" @click.stop="setDocTimeRelativePreset(21, 14)">21~14</button>
              <button type="button" class="doc-chip" @click.stop="setDocTimeRelativePreset(30, 21)">30~21</button>
              <button type="button" class="doc-chip" @click.stop="setDocTimeRelativePreset(60, 30)">60~30</button>
            </div>
          </div>
        </template>

        <div class="doc-time-summary">{{ docTimeSummary }}</div>
        <div class="doc-time-help">{{ docTimeEffectiveHint }}</div>
      </div>

      <div class="sep"></div>

      <div class="rag-item" @click="setModeAndClose('web')">
        <span class="dot" :class="{ on: mode === 'web' }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.modes.web') }}</span>
          <span class="mini-hint">{{ t('chat.ragMenu.items.webHint') }}</span>
        </span>
      </div>

      <div class="sep"></div>

      <div class="rag-section-title">{{ t('chat.ragMenu.sections.agent') }}</div>

      <div class="rag-item" @click.stop="toggleAgentEnabled">
        <span class="dot" :class="{ on: agentEnabled }" />
        <span class="rag-row">
          <span class="rag-main">{{ t('chat.ragMenu.agent.tools') }}</span>
          <span class="mini-hint">{{ agentEnabled ? t('chat.ragMenu.common.on') : t('chat.ragMenu.common.off') }}</span>
        </span>
      </div>

      <div v-if="agentEnabled" class="agent-panel" @click.stop>
        <div class="agent-row">
          <span class="agent-label">{{ t('chat.ragMenu.agent.planner') }}</span>

          <select v-model="agentPlannerModel" class="agent-select" @change="syncPlannerProviderFromModel">
            <template v-if="plannerProviders.length > 0">
              <optgroup v-for="p in plannerProviders" :key="p.key" :label="p.name">
                <option v-for="m in p.models" :key="m.value" :value="m.value">
                  {{ m.label }}{{ m.badge ? ` · ${m.badge}` : '' }}
                </option>
              </optgroup>
            </template>

            <template v-else>
              <option value="gpt-4o-mini">gpt-4o-mini</option>
              <option value="gpt-4o">gpt-4o</option>
            </template>
          </select>
        </div>

        <div class="agent-row">
          <span class="agent-label">{{ t('chat.ragMenu.agent.steps') }}</span>
          <input v-model.number="agentMaxSteps" type="number" min="0" max="8" class="agent-input" />
        </div>

        <label class="agent-check">
          <input v-model="agentDebug" type="checkbox" />
          {{ t('chat.ragMenu.agent.returnDebugTrace') }}
        </label>

        <label class="agent-check">
          <input v-model="agentAnswerUsePlanner" type="checkbox" />
          {{ t('chat.ragMenu.agent.usePlannerForAnswer') }}
        </label>

        <div v-if="plannerLoadError" class="agent-warn">
          {{ t('chat.ragMenu.agent.loadFailed', { error: plannerLoadError }) }}
        </div>
      </div>

      <div class="hint">
        {{ t('chat.ragMenu.hint') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useChatConfigStore } from '../../../../stores/chatConfig'
import { useAgentConfigStore } from '../../../../stores/agentConfig'
import { useMCP } from '../../../../composables/useMCP'
import RagContextCard from '../../../RightSidebar/RagContextCard.vue'

const { t } = useI18n()
const { callTool } = useMCP()

const store = useChatConfigStore()
if (typeof store.hydrate === 'function') store.hydrate()

const agentCfg = useAgentConfigStore()
if (typeof agentCfg.hydrate === 'function') agentCfg.hydrate()

const { rag } = storeToRefs(store)
const { enabled, plannerModel, maxSteps, debug, answerUsePlanner } = storeToRefs(agentCfg)

const wrapRef = ref(null)
const btnRef = ref(null)

const open = ref(false)
const ctxOpen = ref(false)
const ctxMode = ref('cite')

const menuStyle = ref({ left: '0px', top: '0px', width: '620px' })

const draftDocDays = ref(3)
const draftOlderDaysAgo = ref(30)
const draftNewerDaysAgo = ref(21)

const mode = computed(() => rag.value?.mode || 'off')
const scope = computed(() => String(rag.value?.storeScope || 'global').toLowerCase())
const ctxLib = computed(() => rag.value?.context?.libraryId || null)
const ctxDoc = computed(() => rag.value?.context?.docId || null)
const ctxGroup = computed(() => rag.value?.context?.group_id || null)

const docTimeEnabled = computed({
  get: () => !!rag.value?.docTime?.enabled,
  set: (v) => store.setDocTimeEnabled(!!v),
})

const docTimeMode = computed({
  get: () => String(rag.value?.docTime?.mode || 'days'),
  set: (v) => store.setDocTimeMode(String(v || 'days')),
})

const docTimeDays = computed(() => Number(rag.value?.docTime?.days ?? 3))
const docTimeRelative = computed(() => ({
  olderDaysAgo: Number(rag.value?.docTime?.relative?.olderDaysAgo ?? 30),
  newerDaysAgo: Number(rag.value?.docTime?.relative?.newerDaysAgo ?? 21),
}))

const agentEnabled = computed({
  get: () => !!enabled.value,
  set: (v) => agentCfg.setEnabled(!!v),
})
const agentPlannerModel = computed({
  get: () => String(plannerModel.value || 'gpt-4o-mini'),
  set: (v) => agentCfg.setPlannerModel(String(v || 'gpt-4o-mini')),
})
const agentMaxSteps = computed({
  get: () => Number(maxSteps.value || 0),
  set: (v) => agentCfg.setMaxSteps(v),
})
const agentDebug = computed({
  get: () => !!debug.value,
  set: (v) => agentCfg.setDebug(!!v),
})
const agentAnswerUsePlanner = computed({
  get: () => !!answerUsePlanner.value,
  set: (v) => agentCfg.setAnswerUsePlanner(!!v),
})

function toggleAgentEnabled() {
  agentCfg.setEnabled(!agentEnabled.value)
}

function _modeLabel(m) {
  if (m === 'auto') return t('chat.ragMenu.modes.auto')
  if (m === 'cite') return t('chat.ragMenu.modes.cite')
  if (m === 'ground') return t('chat.ragMenu.modes.ground')
  if (m === 'web') return t('chat.ragMenu.modes.web')
  return t('chat.ragMenu.modes.off')
}

function _scopeLabel(s) {
  if (s === 'doc') return t('chat.ragMenu.scope.doc')
  if (s === 'library') return t('chat.ragMenu.scope.library')
  return t('chat.ragMenu.scope.global')
}

function _shortId(x, n = 10) {
  const v = String(x || '')
  if (!v) return ''
  return v.length > n ? `${v.slice(0, n)}…` : v
}

function safeObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) ? v : {}
}

function pickPayload(res) {
  const root = safeObject(res)
  const candidates = [safeObject(root.data), safeObject(root.result), safeObject(root.payload), root]
  for (const item of candidates) {
    if (Object.keys(item).length > 0) return item
  }
  return {}
}

function normalizeStatus(value) {
  const s = String(value || '').trim().toLowerCase()
  if (!s) return ''
  if (['ok', 'success', 'succeeded'].includes(s)) return 'success'
  if (['warning', 'partial_success', 'partial_error'].includes(s)) return 'warning'
  if (['error', 'failed', 'fail'].includes(s)) return 'error'
  return s
}

function isSuccessLike(res) {
  const root = safeObject(res)
  const payload = pickPayload(res)
  return normalizeStatus(root.status) === 'success' ||
    normalizeStatus(payload.status) === 'success' ||
    root.success === true ||
    payload.success === true
}

function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max)
}

function clampDayNumber(value, fallback = 0) {
  let n = parseInt(value, 10)
  if (Number.isNaN(n)) n = fallback
  return Math.max(0, Math.min(3650, n))
}

function syncDocTimeDrafts() {
  draftDocDays.value = Number(docTimeDays.value || 3)
  draftOlderDaysAgo.value = Number(docTimeRelative.value.olderDaysAgo || 30)
  draftNewerDaysAgo.value = Number(docTimeRelative.value.newerDaysAgo || 21)
}

const btnLabel = computed(() => {
  const m = mode.value
  if (m !== 'cite' && m !== 'ground') {
    return t('chat.ragMenu.button.baseLabel', { mode: _modeLabel(m) })
  }

  if (ctxGroup.value) {
    return t('chat.ragMenu.button.groupedLabel', {
      mode: _modeLabel(m),
      group: _shortId(ctxGroup.value),
    })
  }

  const s = scope.value
  const base = t('chat.ragMenu.button.scopedLabel', {
    mode: _modeLabel(m),
    scope: _scopeLabel(s),
  })
  const lib = ctxLib.value ? ` ${t('chat.ragMenu.button.libraryToken', { id: _shortId(ctxLib.value) })}` : ''
  const doc = ctxDoc.value ? ` ${t('chat.ragMenu.button.docToken', { id: _shortId(ctxDoc.value) })}` : ''
  return (base + lib + doc).trim()
})

const scopeHintInline = computed(() => {
  if (mode.value !== 'cite' && mode.value !== 'ground') return ''
  if (ctxGroup.value) return t('chat.ragMenu.scope.groupedInline')
  return t('chat.ragMenu.scope.inline', { scope: _scopeLabel(scope.value) })
})

const docTimeHintInline = computed(() => {
  if (!docTimeEnabled.value) return t('chat.ragMenu.common.off')
  if (docTimeMode.value === 'relative') {
    return t('chat.ragMenu.docTime.inline.relative', {
      older: docTimeRelative.value.olderDaysAgo,
      newer: docTimeRelative.value.newerDaysAgo,
    })
  }
  return t('chat.ragMenu.docTime.inline.days', { days: docTimeDays.value })
})

const docTimeSummary = computed(() => {
  if (!docTimeEnabled.value) return t('chat.ragMenu.docTime.summary.disabled')
  if (docTimeMode.value === 'relative') {
    return t('chat.ragMenu.docTime.summary.relative', {
      older: docTimeRelative.value.olderDaysAgo,
      newer: docTimeRelative.value.newerDaysAgo,
    })
  }
  return t('chat.ragMenu.docTime.summary.days', { days: docTimeDays.value })
})

const docTimeEffectiveHint = computed(() => {
  if (mode.value === 'cite' || mode.value === 'ground') {
    return t('chat.ragMenu.docTime.effective.localMode', { mode: _modeLabel(mode.value) })
  }
  return t('chat.ragMenu.docTime.effective.savedOnly')
})

function _availableScopes() {
  if (ctxGroup.value) return ['global']
  const scopes = ['global']
  if (ctxLib.value) scopes.push('library')
  if (ctxDoc.value) scopes.push('doc')
  return scopes
}

function _cycleScope() {
  const scopes = _availableScopes()
  const cur = scope.value
  const idx = scopes.indexOf(cur)
  const next = scopes[(idx + 1) % scopes.length] || 'global'
  store.setRagScopes({ storeScope: next, evidenceScope: next })
}

function positionMenu() {
  const el = btnRef.value
  if (!el) return

  const rect = el.getBoundingClientRect()
  const gap = 8
  const vw = window.innerWidth || 1280
  const vh = window.innerHeight || 800

  const isMobile = vw <= 640
  const isWide = vw >= 1024

  const targetWidth = isMobile
    ? Math.min(vw - gap * 2, 420)
    : Math.min(vw - gap * 2, 620)

  menuStyle.value = {
    left: `${gap}px`,
    top: `${Math.max(gap, rect.bottom + gap)}px`,
    width: `${targetWidth}px`,
  }

  nextTick(() => {
    const menu = wrapRef.value?.querySelector('.rag-menu')
    if (!menu) return

    const mw = Math.min(menu.offsetWidth || targetWidth, vw - gap * 2)
    const mh = menu.offsetHeight || 0

    const anchorCenter = rect.left + rect.width / 2

    let left
    if (isMobile) {
      left = clamp(rect.left, gap, Math.max(gap, vw - gap - mw))
    } else if (isWide) {
      left = clamp(
        Math.round(anchorCenter - mw / 2),
        gap,
        Math.max(gap, vw - gap - mw)
      )
    } else {
      left = clamp(
        Math.round(rect.right - mw),
        gap,
        Math.max(gap, vw - gap - mw)
      )
    }

    let top = rect.top - mh - gap
    if (top < gap) top = rect.bottom + gap
    if (top + mh > vh - gap) top = Math.max(gap, vh - gap - mh)

    menuStyle.value = {
      left: `${left}px`,
      top: `${top}px`,
      width: `${mw}px`,
    }
  })
}

const plannerProviders = ref([])
const plannerLoadError = ref('')
const plannerLoaded = ref(false)

function _filterPlannerModels(models) {
  const arr = Array.isArray(models) ? models : []
  return arr.filter((m) => m?.capabilities?.tool_planner === true)
}

async function loadPlannerModelsOnce() {
  if (plannerLoaded.value) return
  plannerLoaded.value = true
  plannerLoadError.value = ''

  try {
    const result = await callTool('nisb_chat_models', {})
    const payload = pickPayload(result)

    if (!isSuccessLike(result)) {
      plannerLoadError.value = payload?.message || result?.message || 'nisb_chat_models failed'
      return
    }

    const providersRoot = safeObject(payload.providers || result?.providers)
    const keys = Object.keys(providersRoot)

    const out = keys.map((key) => {
      const entry = providersRoot[key] || {}
      const models = _filterPlannerModels(entry.models || [])
      return {
        key,
        icon: entry.icon || '',
        name: entry.name || key,
        models,
      }
    }).filter((x) => x.models.length > 0)

    plannerProviders.value = out
  } catch (e) {
    plannerLoadError.value = e?.message || String(e)
  }
}

function _findProviderByModelValue(modelValue) {
  const mv = String(modelValue || '')
  for (const p of plannerProviders.value || []) {
    for (const m of p.models || []) {
      if (String(m.value || '') === mv) return p.key
    }
  }
  return ''
}

function syncPlannerProviderFromModel() {
  const provider = _findProviderByModelValue(agentPlannerModel.value)
  if (!provider) return
  if (typeof agentCfg.setPlannerProvider === 'function') agentCfg.setPlannerProvider(provider)
}

function toggleDocTimeEnabled() {
  docTimeEnabled.value = !docTimeEnabled.value
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

function setDocTimeModeOnly(nextMode) {
  docTimeMode.value = nextMode === 'relative' ? 'relative' : 'days'
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

function pickDocTimeDays(days) {
  setDocTimeModeOnly('days')
  const fixed = clampDayNumber(days, 3)
  draftDocDays.value = fixed
  store.setDocTimeDays(fixed)
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

function applyDocTimeDays() {
  const fixed = clampDayNumber(draftDocDays.value, 3)
  draftDocDays.value = fixed
  store.setDocTimeDays(fixed)
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

function applyDocTimeRelative() {
  const olderDaysAgo = clampDayNumber(draftOlderDaysAgo.value, 30)
  const newerDaysAgo = clampDayNumber(draftNewerDaysAgo.value, 21)
  store.setDocTimeRelativeRange({ olderDaysAgo, newerDaysAgo })
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

function setDocTimeRelativePreset(olderDaysAgo, newerDaysAgo) {
  setDocTimeModeOnly('relative')
  store.setDocTimeRelativeRange({ olderDaysAgo, newerDaysAgo })
  nextTick(() => {
    syncDocTimeDrafts()
    if (open.value) positionMenu()
  })
}

watch(plannerProviders, () => {
  syncPlannerProviderFromModel()
})

watch(
  () => rag.value?.docTime,
  () => {
    syncDocTimeDrafts()
  },
  { deep: true, immediate: true }
)

function toggleMenu() {
  open.value = !open.value
  if (open.value) {
    syncDocTimeDrafts()
    positionMenu()
    loadPlannerModelsOnce()
  } else {
    closeCtx()
  }
}

function closeAll() {
  open.value = false
  closeCtx()
}

function closeCtx() {
  ctxOpen.value = false
}

function setModeAndClose(m) {
  store.setRagMode(m)
  open.value = false
  closeCtx()
}

function handleModeClick(m) {
  if (!ctxOpen.value || ctxMode.value !== m) {
    store.setRagMode(m)
    ctxMode.value = m === 'ground' ? 'ground' : 'cite'
    ctxOpen.value = true
    positionMenu()
    return
  }
  _cycleScope()
}

function handleGlobalClick(e) {
  const target = e?.target
  const root = target?.closest?.('.rag-wrapper')
  if (!root) closeAll()
}

function handleResize() {
  if (open.value) positionMenu()
}

function handleKeydown(e) {
  if (e.key === 'Escape') {
    closeAll()
  }
}

onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener('resize', handleResize)
  window.addEventListener('scroll', handleResize, true)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('scroll', handleResize, true)
})
</script>

<style scoped>
.rag-wrapper {
  position: relative;
  flex: 0 1 224px;
  min-width: 0;
  max-width: 224px;
}

.rag-btn {
  width: 100%;
  min-width: 0;
  height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.46rem;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 720;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.rag-btn:hover,
.rag-btn:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 7px 16px rgba(0, 0, 0, 0.06);
  outline: none;
}

.rag-btn:active {
  transform: translateY(1px);
}

.rag-btn.active,
.rag-btn.open {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 64%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.btn-icon {
  flex: 0 0 20px;
  width: 20px;
  height: 20px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--selected) 28%, var(--line));
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--selected) 16%, transparent), transparent 56%),
    color-mix(in srgb, var(--selected-bg) 38%, transparent);
  color: var(--selected);
  font-size: 0.7rem;
  font-weight: 840;
  line-height: 1;
}

.btn-text {
  flex: 1 1 auto;
  min-width: 0;
  color: inherit;
  font-weight: 760;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-caret {
  flex: 0 0 auto;
  color: inherit;
  font-size: 0.72rem;
  line-height: 1;
  opacity: 0.84;
}

.rag-popover-scrim {
  position: fixed;
  inset: 0;
  z-index: 2147482999;
  background: color-mix(in srgb, #020617 22%, transparent);
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  animation: ragScrimIn 0.14s ease-out;
}

.rag-menu {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 2147483000;
  width: min(620px, calc(100vw - 16px));
  max-width: calc(100vw - 16px);
  max-height: min(76vh, 740px);
  box-sizing: border-box;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 76%, transparent)
    );
  color: var(--text-secondary);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 24px 72px rgba(0, 0, 0, 0.28),
    0 2px 14px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(24px) saturate(1.12);
  -webkit-backdrop-filter: blur(24px) saturate(1.12);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  isolation: isolate;
  animation: ragMenuGlassIn 0.16s ease-out;
}

.rag-menu::-webkit-scrollbar {
  width: 8px;
}

.rag-menu::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.rag-menu-head {
  min-width: 0;
  margin-bottom: 0.46rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 26%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.rag-menu-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.86rem;
  font-weight: 830;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.rag-status-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  margin-top: 0.42rem;
}

.status-chip {
  max-width: 100%;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 44%, transparent);
  color: var(--text-secondary);
  font-size: 0.69rem;
  font-weight: 740;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.status-chip.primary,
.status-chip.active {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 810;
}

.rag-section-title {
  padding: 0.44rem 0.42rem 0.34rem;
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 810;
  letter-spacing: 0.055em;
  line-height: 1.2;
  text-transform: uppercase;
  opacity: 0.86;
}

.rag-item {
  min-width: 0;
  min-height: 42px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.58rem;
  padding: 0.5rem 0.56rem;
  border: 1px solid transparent;
  border-radius: 13px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1.35;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.rag-item:hover,
.rag-item:focus-within {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 40%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.rag-item:active {
  transform: translateY(1px);
}

.rag-item.hoverActive {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 54%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
}

.rag-row {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, auto);
  align-items: baseline;
  gap: 0.7rem;
}

.rag-main {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 790;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.mini-hint {
  min-width: 0;
  max-width: 280px;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 690;
  line-height: 1.35;
  text-align: right;
  white-space: normal;
  overflow-wrap: break-word;
  opacity: 0.9;
}

.sep {
  height: 1px;
  margin: 0.42rem 0.22rem;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--line) 82%, transparent),
    transparent
  );
}

.rag-subpanel {
  min-width: 0;
  margin: 0.22rem 0.16rem 0.62rem 0.74rem;
  padding-left: 0.58rem;
  border-left: 2px solid color-mix(in srgb, var(--selected) 32%, var(--line));
  overflow: hidden;
}

.doc-time-panel,
.agent-panel {
  min-width: 0;
  margin: 0.22rem 0.16rem 0.44rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.doc-time-mode-switch {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.36rem;
  margin-bottom: 0.56rem;
}

.doc-mode-chip,
.doc-chip {
  min-height: 27px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.doc-mode-chip:hover,
.doc-mode-chip:focus-visible,
.doc-chip:hover,
.doc-chip:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.doc-mode-chip:active,
.doc-chip:active {
  transform: translateY(1px);
}

.doc-mode-chip.active,
.doc-chip.active {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 60%, transparent);
  color: var(--selected);
  font-weight: 820;
}

.doc-time-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.58rem;
  margin-top: 0.52rem;
}

.doc-time-inline-row {
  align-items: center;
}

.doc-label,
.agent-label {
  flex: 0 0 auto;
  width: 64px;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 760;
  line-height: 1.35;
  opacity: 0.9;
}

.doc-chip-list {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.36rem;
}

.doc-time-grid {
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.52rem;
  margin-top: 0.1rem;
}

.doc-field {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
}

.doc-field-label {
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 750;
  line-height: 1.35;
  opacity: 0.9;
  overflow-wrap: break-word;
}

.doc-field-input-wrap {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.doc-input,
.agent-select,
.agent-input {
  width: 100%;
  min-width: 0;
  height: 31px;
  box-sizing: border-box;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 60%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    color 0.15s ease;
}

.doc-input-sm {
  flex: 0 0 86px;
  width: 86px;
}

.doc-input:hover,
.doc-input:focus,
.agent-select:hover,
.agent-select:focus,
.agent-input:hover,
.agent-input:focus {
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

.doc-suffix {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
}

.doc-time-summary,
.doc-time-help,
.hint,
.agent-warn {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.doc-time-summary {
  margin-top: 0.62rem;
  color: var(--text-main, var(--text));
  font-weight: 730;
}

.doc-time-help {
  margin-top: 0.28rem;
  opacity: 0.9;
}

.hint {
  margin: 0.48rem 0.16rem 0.08rem;
  padding: 0.52rem 0.56rem;
  border: 1px dashed color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
  opacity: 0.92;
}

.dot {
  flex: 0 0 auto;
  width: 11px;
  height: 11px;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.dot.on {
  border-color: color-mix(in srgb, var(--selected) 58%, var(--line));
  background: var(--selected);
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 12%, transparent),
    0 1px 0 color-mix(in srgb, white 12%, transparent) inset;
}

.agent-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.52rem;
  margin-top: 0.46rem;
}

.agent-row:first-child {
  margin-top: 0;
}

.agent-select {
  flex: 1 1 auto;
}

.agent-input {
  flex: 1 1 auto;
  font-variant-numeric: tabular-nums;
}

.agent-check {
  min-width: 0;
  min-height: 32px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.46rem;
  padding: 0.38rem 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 34%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.74rem;
  font-weight: 710;
  line-height: 1.35;
  user-select: none;
  overflow-wrap: break-word;
}

.agent-check:hover,
.agent-check:focus-within {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.agent-check input {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--selected);
}

.agent-warn {
  margin-top: 0.52rem;
  padding: 0.48rem 0.54rem;
  border: 1px solid color-mix(in srgb, #d97706 36%, var(--line));
  border-radius: 12px;
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
  font-weight: 700;
}

@keyframes ragScrimIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes ragMenuGlassIn {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.985);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 640px) {
  .rag-wrapper {
    flex: 0 1 182px;
    max-width: 182px;
  }

  .rag-btn {
    padding: 0 0.5rem;
  }

  .rag-popover-scrim {
    background: color-mix(in srgb, #020617 24%, transparent);
    backdrop-filter: blur(10px) saturate(1.12);
    -webkit-backdrop-filter: blur(10px) saturate(1.12);
  }

  .rag-menu {
    width: calc(100vw - 16px);
    max-width: calc(100vw - 16px);
    max-height: min(84vh, calc(100vh - 16px));
    border-radius: 16px;
  }

  .rag-row {
    grid-template-columns: minmax(0, 1fr);
    align-items: flex-start;
    gap: 0.16rem;
  }

  .mini-hint {
    max-width: 100%;
    text-align: left;
  }

  .rag-subpanel {
    margin-left: 0.18rem;
    padding-left: 0.52rem;
  }

  .doc-time-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .doc-time-row,
  .doc-time-inline-row,
  .agent-row {
    align-items: stretch;
    flex-direction: column;
  }

  .doc-label,
  .agent-label {
    width: auto;
  }

  .doc-input-sm {
    width: 100%;
    flex: 1 1 auto;
  }

  .doc-field-input-wrap {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
