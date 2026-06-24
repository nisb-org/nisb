<template>
  <div
    v-if="visible"
    class="room-runtime-section"
  >
    <div class="room-runtime-section-head">
      <div class="room-runtime-section-title">{{ t('runtime.card.title') }}</div>
      <span
        class="room-runtime-status-chip"
        :class="statusChipClass"
      >
        {{ displayStatusText }}
      </span>
    </div>

    <div class="room-runtime-toolbar">
      <div class="room-runtime-mode-group">
        <button
          type="button"
          class="room-runtime-mode-btn"
          :class="{ active: normalizedViewMode === 'current' }"
          @click="$emit('switch-mode', 'current')"
        >
          {{ t('runtime.card.mode.current') }}
        </button>

        <button
          type="button"
          class="room-runtime-mode-btn"
          :class="{ active: normalizedViewMode === 'replay' }"
          @click="$emit('switch-mode', 'replay')"
        >
          {{ t('runtime.card.mode.replay') }}
        </button>
      </div>

      <button
        type="button"
        class="room-runtime-refresh-btn"
        :disabled="loading"
        @click="$emit('refresh')"
      >
        {{ loading ? t('runtime.card.actions.refreshing') : t('runtime.card.actions.refresh') }}
      </button>
    </div>

    <div
      v-if="isReplayMode"
      class="room-runtime-replay-row"
    >
      <div class="room-runtime-replay-label">{{ t('runtime.card.replay.label') }}</div>

      <select
        class="room-runtime-run-select"
        :value="selectedRunId"
        :disabled="loading || !runOptions.length"
        @change="$emit('select-run', $event.target.value)"
      >
        <option value="" disabled>
          {{ runOptions.length ? t('runtime.card.replay.selectRun') : t('runtime.card.replay.noRun') }}
        </option>

        <option
          v-for="option in runOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>
    </div>

    <div
      v-if="showControlRow"
      class="room-runtime-control-row"
    >
      <div class="room-runtime-control-actions">
        <button
          v-if="showPauseAction"
          type="button"
          class="room-runtime-action-btn"
          :disabled="pauseDisabled"
          @click="$emit('pause-current')"
        >
          {{ displayPauseText }}
        </button>

        <button
          v-if="showResumeAction"
          type="button"
          class="room-runtime-action-btn primary"
          :disabled="resumeDisabled"
          @click="$emit('resume-from-checkpoint')"
        >
          {{ displayResumeText }}
        </button>
      </div>

      <div
        v-if="displayControlHint"
        class="room-runtime-control-hint"
      >
        {{ displayControlHint }}
      </div>
    </div>

    <div
      class="room-runtime-brief-card"
      :class="[
        resultEntry ? `type-${resultEntry.typeClass}` : '',
        `tone-${briefTone}`
      ]"
    >
      <div class="room-runtime-brief-head">
        <span
          class="room-runtime-brief-badge"
          :class="`tone-${briefTone}`"
        >
          {{ displayBriefBadge }}
        </span>

        <span class="room-runtime-brief-title">
          {{ displayHeadline }}
        </span>

        <span
          v-if="roomId"
          class="room-runtime-brief-room"
          :title="roomId"
        >
          {{ roomId }}
        </span>
      </div>

      <div
        v-if="metaLine"
        class="room-runtime-brief-meta"
      >
        {{ metaLine }}
      </div>

      <div
        v-if="runtimeSemanticChips.length"
        class="room-runtime-chip-row"
      >
        <span
          v-for="(chip, idx) in runtimeSemanticChips"
          :key="`runtime-chip-${idx}`"
          class="room-runtime-chip"
          :class="chip.className"
        >
          {{ chip.label }}
        </span>
      </div>

      <div
        v-if="skillSummaryChips.length"
        class="room-runtime-chip-row"
      >
        <span
          v-for="(chip, idx) in skillSummaryChips"
          :key="`skill-chip-${idx}`"
          class="room-runtime-chip"
          :class="{ skill: idx === 0 }"
        >
          {{ chip }}
        </span>
      </div>

      <div
        v-if="displaySummaryText"
        class="room-runtime-brief-summary"
      >
        {{ displaySummaryText }}
      </div>

      <div
        v-else
        class="room-runtime-empty"
      >
        {{ emptyText }}
      </div>

      <div
        v-if="sendBlockedHint"
        class="room-runtime-inline-note"
      >
        {{ sendBlockedHint }}
      </div>

      <div
        v-if="checkpointSummaryText"
        class="room-runtime-inline-note"
      >
        {{ checkpointSummaryText }}
      </div>

      <div
        v-if="runtimeDetailRows.length"
        class="room-runtime-detail-list"
      >
        <div
          v-for="(row, idx) in runtimeDetailRows"
          :key="`detail-row-${idx}`"
          class="room-runtime-detail-item"
        >
          <span class="room-runtime-detail-label">{{ row.label }}</span>
          <span class="room-runtime-detail-value">{{ row.value }}</span>
        </div>
      </div>

      <div
        v-if="effectSummary.chips.length"
        class="room-runtime-chip-row room-runtime-chip-row-effects"
      >
        <span
          v-for="(chip, idx) in effectSummary.chips"
          :key="`effect-chip-${idx}`"
          class="room-runtime-chip"
          :class="chip.className"
        >
          {{ chip.label }}
        </span>
      </div>

      <div
        v-if="effectSummary.text"
        class="room-runtime-inline-note"
      >
        {{ effectSummary.text }}
      </div>
    </div>

    <div
      v-if="displayRecentEntries.length"
      class="room-runtime-mini-list"
    >
      <div
        v-for="(entry, idx) in displayRecentEntries"
        :key="entry.id || `${entry.type}-${idx}`"
        class="room-runtime-mini-item"
        :class="[
          `type-${entry.typeClass}`,
          `tone-${entryTone(entry)}`
        ]"
      >
        <span
          class="room-runtime-mini-badge"
          :class="`tone-${entryTone(entry)}`"
          :title="entry.badge"
        >
          {{ entry.badge }}
        </span>

        <span
          class="room-runtime-mini-title"
          :title="entry.title"
        >
          {{ entry.title }}
        </span>

        <span
          v-if="entry.actor"
          class="room-runtime-mini-actor"
          :title="entry.actor"
        >
          {{ entry.actor }}
        </span>

        <span
          v-if="entry.timeText"
          class="room-runtime-mini-time"
        >
          {{ entry.timeText }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  visible: { type: Boolean, default: false },
  live: { type: Boolean, default: false },
  error: { type: String, default: '' },
  statusText: { type: String, default: '' },
  roomId: { type: String, default: '' },
  headline: { type: String, default: '' },
  badgeSummary: { type: String, default: '' },
  hasTerminalResult: { type: Boolean, default: false },
  latestStage: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  resultEntry: { type: Object, default: null },
  recentEntries: { type: Array, default: () => [] },

  viewMode: { type: String, default: 'current' },
  selectedRunId: { type: String, default: '' },
  runOptions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },

  runtimeSkillSummary: { type: Object, default: () => ({}) },

  runtimeState: { type: String, default: '' },
  runtimePhase: { type: String, default: '' },
  canAcceptNewPrompt: { type: Boolean, default: false },
  controlBlockReason: { type: String, default: '' },

  continuationMode: { type: String, default: '' },
  continuationStatus: { type: String, default: '' },
  pauseRequested: { type: Boolean, default: false },
  pauseRequestAccepted: { type: Boolean, default: false },
  pauseReason: { type: String, default: '' },
  pauseRequestedAt: { type: String, default: '' },
  pauseEffective: { type: Boolean, default: false },
  pausedAt: { type: String, default: '' },
  pauseEffectiveAt: { type: String, default: '' },
  interruptionReason: { type: String, default: '' },

  resumeReady: { type: Boolean, default: false },
  resumeFromCheckpoint: { type: Boolean, default: false },
  canResumeFromCheckpoint: { type: Boolean, default: false },
  resumeCheckpointRef: { type: String, default: '' },
  resumeToken: { type: String, default: '' },
  resumeReason: { type: String, default: '' },
  errorBlockingResume: { type: Boolean, default: false },
  resumedFromRunId: { type: String, default: '' },
  resumedFromEventId: { type: String, default: '' },
  resumedFromStage: { type: String, default: '' },

  checkpointStage: { type: String, default: '' },
  checkpointSummary: { type: String, default: '' },
  lastCompletedStep: { type: String, default: '' },

  skippedEffects: { type: Array, default: () => [] },
  effectDispositions: { type: Array, default: () => [] },

  stepBudgetTotal: { type: [Number, String], default: null },
  stepBudgetUsed: { type: [Number, String], default: null },
  stepBudgetRemaining: { type: [Number, String], default: null },
  budgetStatus: { type: String, default: '' },
  budgetExhausted: { type: Boolean, default: false },

  canPauseCurrent: { type: Boolean, default: false },
  canResume: { type: Boolean, default: false },

  showPauseAction: { type: Boolean, default: false },
  pauseDisabled: { type: Boolean, default: true },
  pauseText: { type: String, default: '' },

  showResumeAction: { type: Boolean, default: false },
  resumeDisabled: { type: Boolean, default: true },
  resumeText: { type: String, default: '' },

  controlHint: { type: String, default: '' },
})

defineEmits([
  'switch-mode',
  'select-run',
  'refresh',
  'pause-current',
  'resume-from-checkpoint',
])

const { t } = useI18n()

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

function safeNumber(value, fallback = null) {
  if (value === null || value === undefined) return fallback
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed || trimmed.toLowerCase() === 'null' || trimmed.toLowerCase() === 'undefined') {
      return fallback
    }
  }
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function normalizeToken(value) {
  return safeString(value).trim().toLowerCase()
}

function prettifyTokenText(value) {
  const text = safeString(value).trim()
  if (!text) return ''
  return text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function stripI18nPlaceholders(value) {
  return safeString(value)
    .replace(/\{[^}]+\}/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function translateKeyIfExists(key, params = {}) {
  const text = safeString(key).trim()
  if (!text || !text.includes('.')) return ''
  const translated = t(text, params)
  if (translated === text) return ''
  return stripI18nPlaceholders(translated)
}

function translateWithFallback(key, fallback, params = {}) {
  const translated = safeString(t(key, params)).trim()
  return translated && translated !== key ? translated : fallback
}

function uniqStrings(values = []) {
  const seen = new Set()
  const result = []

  for (const value of safeArray(values)) {
    const text = safeString(value).trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    result.push(text)
  }

  return result
}

function normalizeFormalSkillStrategy(value) {
  const token = normalizeToken(value)
  if (!token) return ''

  if (token === 'builtin_plus_custom') return 'builtin_plus_custom'
  if (token === 'custom_only') return 'custom_only'
  if (token === 'builtin_only') return 'builtin_only'
  if (token === 'builtin + custom' || token === 'builtin+custom') return 'builtin_plus_custom'
  if (token === 'custom only' || token === 'custom-only') return 'custom_only'
  if (token === 'builtin only' || token === 'builtin-only') return 'builtin_only'

  return ''
}

function formatSkillStrategyLabel(value) {
  const token = normalizeFormalSkillStrategy(value)
  if (token === 'builtin_plus_custom') return t('runtime.card.skillStrategy.builtinPlusCustom')
  if (token === 'custom_only') return t('runtime.card.skillStrategy.customOnly')
  if (token === 'builtin_only') return t('runtime.card.skillStrategy.builtinOnly')
  return safeString(value).trim()
}

function normalizeSkillSummary(summary = {}) {
  const src = safeObject(summary)
  const strategy = formatSkillStrategyLabel(src.strategy || src.strategy_value)
  const enabled_count = safeNumber(src.enabled_count, 0)
  const applied_count = safeNumber(src.applied_count, 0)
  const resolved_items_count = safeNumber(src.resolved_items_count, 0)
  const step_count = safeNumber(src.step_count, 0)
  const summary_text = safeString(src.summary_text).trim()
  const source_type = safeString(src.source_type).trim()
  const source_event_type = safeString(src.source_event_type).trim()

  const has_skills = !!(
    src.has_skills ||
    strategy ||
    enabled_count > 0 ||
    applied_count > 0 ||
    resolved_items_count > 0 ||
    step_count > 0 ||
    summary_text
  )

  return {
    has_skills,
    strategy,
    enabled_count,
    applied_count,
    resolved_items_count,
    step_count,
    has_applied_prompt: !!src.has_applied_prompt,
    has_available_not_enabled: !!src.has_available_not_enabled,
    has_missing: !!src.has_missing,
    has_skipped: !!src.has_skipped,
    source_type,
    source_event_type,
    summary_text,
  }
}

function normalizeContinuationMode(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (['resumed', 'resume'].includes(token)) return 'resumed'
  if (['fresh', 'new', 'initial'].includes(token)) return 'fresh'
  if (token === 'restart_fresh' || token === 'restart fresh') return 'restart_fresh'
  return token
}

function normalizeContinuationStatus(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'pause requested') return 'pause_requested'
  if (token === 'completed after resume') return 'completed_after_resume'
  if (token === 'budget exhausted') return 'budget_exhausted'
  if (token === 'step_budget_exhausted' || token === 'exhausted') return 'budget_exhausted'
  return token.replace(/\s+/g, '_')
}

function normalizeRuntimeState(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'completed after resume') return 'completed_after_resume'
  if (token === 'budget exhausted') return 'budget_exhausted'
  if (token === 'step_budget_exhausted' || token === 'exhausted') return 'budget_exhausted'
  return token.replace(/\s+/g, '_')
}

function normalizeLegalRuntimeStatus(value) {
  const token = normalizeToken(value)
  if (!token) return ''

  if (token === 'room.runtime_manual' || token === 'runtime_manual' || token === 'manual' || token.includes('人工处理')) {
    return 'manual'
  }

  if (
    token === 'room.runtime_skipped' ||
    token === 'runtime_skipped' ||
    token === 'skipped' ||
    token === 'skip' ||
    token.includes('已跳过')
  ) {
    return 'skipped'
  }

  if (
    token === 'room.runtime_denied' ||
    token === 'runtime_denied' ||
    token === 'denied' ||
    token === 'deny' ||
    token.includes('已拒绝')
  ) {
    return 'denied'
  }

  if (
    token === 'room.runtime_no_auto_reply' ||
    token === 'room.runtime_no-auto-reply' ||
    token === 'runtime_no_auto_reply' ||
    token === 'runtime_no-auto-reply' ||
    token === 'no_auto_reply' ||
    token === 'no-auto-reply' ||
    token === 'no auto reply' ||
    token.includes('未自动回复')
  ) {
    return 'no_auto_reply'
  }

  return ''
}

function buildLegalStatusLabel(status) {
  if (status === 'manual') return translateWithFallback('runtime.card.status.manual', '人工处理')
  if (status === 'skipped') return translateWithFallback('runtime.card.status.skipped', '已跳过')
  if (status === 'denied') return translateWithFallback('runtime.card.status.denied', '已拒绝')
  if (status === 'no_auto_reply') return translateWithFallback('runtime.card.status.noAutoReply', '未自动回复')
  return ''
}

function buildLegalHeadline(status) {
  if (status === 'manual') return translateWithFallback('runtime.card.headline.manual', '当前转人工处理')
  if (status === 'skipped') return translateWithFallback('runtime.card.headline.skipped', '自动回复已跳过')
  if (status === 'denied') return translateWithFallback('runtime.card.headline.denied', '自动回复已拒绝')
  if (status === 'no_auto_reply') return translateWithFallback('runtime.card.headline.noAutoReply', '未触发自动回复')
  return ''
}

function buildLegalSummary(status) {
  if (status === 'manual') return '消息已进入时间线，当前按人工处理执行。'
  if (status === 'skipped') return '消息已进入时间线，但当前未触发自动回复。'
  if (status === 'denied') return '消息已进入时间线，但当前共享能力未获授权执行。'
  if (status === 'no_auto_reply') return '消息已进入时间线，当前配置未触发自动回复。'
  return ''
}

function isLegalRuntimeStatus(status) {
  return ['manual', 'skipped', 'denied', 'no_auto_reply'].includes(status)
}

function entryHasLegalRuntimeSignal(entry = {}) {
  const row = safeObject(entry)
  const candidates = [
    row.badge,
    row.title,
    row.summary,
    row.actor,
    row.type,
    row.typeClass,
  ]

  return candidates.some((item) => isLegalRuntimeStatus(normalizeLegalRuntimeStatus(item)))
}

function normalizeDisplayText(value) {
  const text = safeString(value).trim()
  if (!text) return ''

  if (text.includes(' · ')) {
    return text
      .split(' · ')
      .map((part) => normalizeDisplayText(part))
      .filter(Boolean)
      .join(' · ')
  }

  const directKey = translateKeyIfExists(text)
  if (directKey) return directKey

  const token = normalizeToken(text)

  if (token === 'manual' || token === 'room.runtime_manual' || token === 'runtime_manual') {
    return buildLegalStatusLabel('manual')
  }
  if (token === 'skipped' || token === 'skip' || token === 'room.runtime_skipped' || token === 'runtime_skipped') {
    return buildLegalStatusLabel('skipped')
  }
  if (token === 'denied' || token === 'deny' || token === 'room.runtime_denied' || token === 'runtime_denied') {
    return buildLegalStatusLabel('denied')
  }
  if (
    token === 'no-auto-reply' ||
    token === 'no_auto_reply' ||
    token === 'no auto reply' ||
    token === 'room.runtime_no_auto_reply' ||
    token === 'room.runtime_no-auto-reply' ||
    token === 'runtime_no_auto_reply' ||
    token === 'runtime_no-auto-reply'
  ) {
    return buildLegalStatusLabel('no_auto_reply')
  }

  if (token === 'completed after resume') return t('runtime.card.status.completedAfterResume')
  if (token === 'completed') return t('runtime.card.status.completed')
  if (token === 'running') return t('runtime.card.status.running')
  if (token === 'resumed') return t('runtime.card.status.resumed')
  if (token === 'pause requested' || token === 'pause_requested') return t('runtime.card.status.pauseRequested')
  if (token === 'interrupted') return t('runtime.card.status.interrupted')
  if (token === 'budget exhausted' || token === 'budget_exhausted') return t('runtime.card.status.budgetExhausted')
  if (token === 'failed') return t('runtime.card.status.failed')

  if (token === 'current') return t('runtime.card.badges.current')
  if (token === 'replay') return t('runtime.card.badges.replay')
  if (token === 'final') return t('runtime.timeline.badges.final')
  if (token === 'error') return t('runtime.timeline.badges.error')
  if (token === 'aborted') return t('runtime.timeline.badges.aborted')
  if (token === 'runtime') return t('runtime.timeline.badges.runtime')
  if (token === 'checkpoint') return t('runtime.timeline.badges.checkpoint')
  if (token === 'effects') return t('runtime.timeline.badges.effects')

  if (token === 'supervisor') return t('runtime.card.history.supervisor')
  if (token === 'memory') return t('runtime.card.history.memory')
  if (token === 'success') return t('runtime.card.history.success')
  if (token === 'checkpoint done') return t('runtime.card.history.checkpointDone')
  if (token === 'continue_from_checkpoint' || token === 'continue from checkpoint') {
    return t('runtime.card.history.continueFromCheckpoint')
  }
  if (token === 'unlimited') return t('runtime.card.budget.unlimited')

  if (token === 'memory 写入' || token === 'memory write') return t('runtime.card.history.memoryWrite')
  if (token === 'memory 恢复' || token === 'memory resume') return t('runtime.card.history.memoryResume')
  if (token === 'memory 读取' || token === 'memory read') return t('runtime.card.history.memoryRead')

  let m = null

  m = token.match(/^skills\s+(\d+)$/)
  if (m) return `${t('runtime.card.skillSummary.skills')} ${m[1]}`

  m = token.match(/^enabled\s+(\d+)$/)
  if (m) return t('runtime.card.skillSummary.enabled', { count: m[1] })

  m = token.match(/^applied\s+(\d+)$/)
  if (m) return t('runtime.card.skillSummary.applied', { count: m[1] })

  m = token.match(/^resolved\s+(\d+)$/)
  if (m) return t('runtime.card.skillSummary.resolved', { count: m[1] })

  m = token.match(/^steps\s+(\d+)$/)
  if (m) return t('runtime.card.skillSummary.steps', { count: m[1] })

  m = token.match(/^execute\s+(\d+)$/)
  if (m) return t('runtime.card.effects.execute', { count: m[1] })

  m = token.match(/^repair\s+(\d+)$/)
  if (m) return t('runtime.card.effects.repair', { count: m[1] })

  m = token.match(/^reused\s+(\d+)$/)
  if (m) return t('runtime.card.effects.reused', { count: m[1] })

  m = token.match(/^skipped\s+(\d+)$/)
  if (m) return t('runtime.card.effects.skipped', { count: m[1] })

  m = token.match(/^source\s+(.+)$/)
  if (m) return t('runtime.card.skillSummary.source', { value: normalizeDisplayText(m[1]) })

  m = token.match(/^event\s+(.+)$/)
  if (m) return t('runtime.card.skillSummary.event', { value: normalizeDisplayText(m[1]) })

  m = token.match(/^read\s+(.+)$/)
  if (m) return `${t('runtime.card.history.read')} ${normalizeDisplayText(m[1])}`

  m = token.match(/^write\s+(.+)$/)
  if (m) return `${t('runtime.card.history.write')} ${normalizeDisplayText(m[1])}`

  m = token.match(/^resume\s+(.+)$/)
  if (m) return `${t('runtime.card.history.resume')} ${normalizeDisplayText(m[1])}`

  m = token.match(/^phase\s+(.+)$/)
  if (m) return t('runtime.card.meta.phase', { phase: normalizeDisplayText(m[1]) })

  m = token.match(/^from\s+(.+)$/)
  if (m) return t('runtime.timeline.entry.fromStage', { stage: normalizeDisplayText(m[1]) })

  return prettifyTokenText(text)
}

function formatStageLabel(value) {
  return normalizeDisplayText(value)
}

function formatReasonLabel(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'pause_requested' || token === 'manual_pause') return t('runtime.card.reason.pauseRequested')
  if (token === 'step_budget_exhausted' || token === 'budget_exhausted') return t('runtime.card.reason.stepBudgetExhausted')
  if (token === 'new_topic_detected') return t('runtime.card.reason.newTopicDetected')
  if (token === 'checkpoint_missing') return t('runtime.card.reason.checkpointMissing')
  return normalizeDisplayText(value)
}

function formatControlBlockReasonLabel(value) {
  const token = normalizeToken(value)
  if (!token) return ''
  if (token === 'run_running') return t('runtime.card.controlBlock.runRunning')
  if (token === 'pause_requested_pending_checkpoint') return t('runtime.card.controlBlock.pauseRequestedPendingCheckpoint')
  if (token === 'resume_ready') return t('runtime.card.controlBlock.resumeReady')
  if (token === 'budget_exhausted') return t('runtime.card.controlBlock.budgetExhausted')
  if (token === 'resume_blocked_error') return t('runtime.card.controlBlock.resumeBlockedError')
  return normalizeDisplayText(value)
}

function classifyToneFromText(text = '') {
  const token = normalizeToken(text)
  if (!token) return 'neutral'

  if (
    token.includes('拒绝') ||
    token.includes('denied') ||
    token.includes('deny')
  ) {
    return 'danger'
  }

  if (
    token.includes('已跳过') ||
    token.includes('skipped') ||
    token.includes('skip') ||
    token.includes('未自动回复') ||
    token.includes('no-auto-reply') ||
    token.includes('no auto reply') ||
    token.includes('manual') ||
    token.includes('人工处理')
  ) {
    return 'accent'
  }

  if (
    token.includes('中断') ||
    token.includes('错误') ||
    token.includes('失败') ||
    token.includes('abort') ||
    token.includes('aborted') ||
    token.includes('error') ||
    token.includes('interrupted') ||
    token.includes('budget exhausted') ||
    token.includes('耗尽') ||
    token.includes('exhausted')
  ) {
    return 'danger'
  }

  if (
    token.includes('恢复') ||
    token.includes('resumed') ||
    token.includes('resume') ||
    token.includes('checkpoint') ||
    token.includes('回放') ||
    token.includes('replay')
  ) {
    return 'accent'
  }

  if (
    token.includes('完成') ||
    token.includes('completed') ||
    token.includes('success') ||
    token.includes('成功') ||
    token.includes('done')
  ) {
    return 'success'
  }

  if (
    token.includes('运行中') ||
    token.includes('running') ||
    token.includes('暂停请求') ||
    token.includes('pause')
  ) {
    return 'info'
  }

  return 'neutral'
}

function classifyToneFromTypeClass(typeClass = '') {
  const token = normalizeToken(typeClass)
  if (['error', 'abort', 'aborted'].includes(token)) return 'danger'
  if (['final'].includes(token)) return 'success'
  if (['route', 'delegate'].includes(token)) return 'accent'
  if (['plan', 'supervisor', 'message'].includes(token)) return 'info'
  return 'neutral'
}

function countEffectDispositions(items = []) {
  const counts = {
    skipped: 0,
    execute: 0,
    reused: 0,
    repaired: 0,
    other: 0,
  }

  for (const item of safeArray(items)) {
    if (typeof item === 'string') {
      const token = normalizeToken(item)
      if (!token) continue
      if (token.includes('skip')) counts.skipped += 1
      else if (token.includes('reuse')) counts.reused += 1
      else if (token.includes('repair') || token.includes('reconcile')) counts.repaired += 1
      else if (token.includes('execute')) counts.execute += 1
      else counts.other += 1
      continue
    }

    const row = safeObject(item)
    const merged = normalizeToken(
      [
        row.disposition,
        row.status,
        row.action,
        row.effect_disposition,
        row.mode,
        row.result,
        row.type,
      ]
        .filter(Boolean)
        .join(' ')
    )

    if (!merged) {
      counts.other += 1
      continue
    }

    if (merged.includes('skip')) counts.skipped += 1
    else if (merged.includes('reuse')) counts.reused += 1
    else if (merged.includes('repair') || merged.includes('reconcile')) counts.repaired += 1
    else if (merged.includes('execute')) counts.execute += 1
    else counts.other += 1
  }

  if (!safeArray(items).length && safeArray(props.skippedEffects).length) {
    counts.skipped = safeArray(props.skippedEffects).length
  }

  return counts
}

function formatBudgetSummary(total, used, remaining, exhausted, status) {
  const parts = []
  const totalNum = safeNumber(total, null)
  const usedNum = safeNumber(used, null)
  const remainingNum = safeNumber(remaining, null)

  const allZeroish =
    (totalNum === null || totalNum === 0) &&
    (usedNum === null || usedNum === 0) &&
    (remainingNum === null || remainingNum === 0)

  if (!allZeroish) {
    if (Number.isFinite(usedNum) && Number.isFinite(totalNum)) {
      parts.push(t('runtime.card.budget.usedOfTotal', { used: usedNum, total: totalNum }))
    } else if (Number.isFinite(usedNum)) {
      parts.push(t('runtime.card.budget.used', { count: usedNum }))
    } else if (Number.isFinite(totalNum)) {
      parts.push(t('runtime.card.budget.total', { count: totalNum }))
    }

    if (Number.isFinite(remainingNum)) {
      parts.push(t('runtime.card.budget.remaining', { count: remainingNum }))
    }
  }

  const normalizedStatus = normalizeContinuationStatus(status)
  if (normalizedStatus === 'budget_exhausted') {
    parts.push(t('runtime.card.budget.exhausted'))
  } else if (!allZeroish) {
    const statusLabel = normalizeDisplayText(status)
    if (statusLabel) parts.push(statusLabel)
  }

  if (exhausted) {
    parts.push(t('runtime.card.budget.exhausted'))
  }

  return uniqStrings(parts).join(' · ')
}

function formatDateTimeText(value) {
  const text = safeString(value).trim()
  if (!text) return ''
  try {
    const d = new Date(text)
    if (Number.isNaN(d.getTime())) return text
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch {
    return text
  }
}

const normalizedViewMode = computed(() => {
  return normalizeToken(props.viewMode) === 'replay' ? 'replay' : 'current'
})

const isCurrentMode = computed(() => normalizedViewMode.value === 'current')
const isReplayMode = computed(() => normalizedViewMode.value === 'replay')

const normalizedSkillSummary = computed(() => {
  return normalizeSkillSummary(props.runtimeSkillSummary)
})

const normalizedContinuationModeValue = computed(() => {
  return normalizeContinuationMode(props.continuationMode)
})

const normalizedContinuationStatusValue = computed(() => {
  const direct = normalizeContinuationStatus(props.continuationStatus)
  if (direct) return direct
  if (props.budgetExhausted) return 'budget_exhausted'
  if (props.pauseRequested) return 'pause_requested'
  return ''
})

const normalizedRuntimeStateValue = computed(() => {
  const direct = normalizeRuntimeState(props.runtimeState)
  if (direct) return direct
  return normalizedContinuationStatusValue.value
})

const formalLegalStatusToken = computed(() => {
  if (!isCurrentMode.value) return ''

  const candidates = [
    props.statusText,
    props.resultEntry?.badge,
    props.headline,
    props.summaryText,
    props.badgeSummary,
  ]

  for (const candidate of candidates) {
    const normalized = normalizeLegalRuntimeStatus(candidate)
    if (normalized) return normalized
  }

  return ''
})

const hasFormalLegalStatus = computed(() => {
  return isCurrentMode.value && !!formalLegalStatusToken.value
})

const effectiveStatusToken = computed(() => {
  if (formalLegalStatusToken.value) return formalLegalStatusToken.value
  return normalizedRuntimeStateValue.value || normalizedContinuationStatusValue.value
})

const modeBadge = computed(() => {
  return isReplayMode.value
    ? t('runtime.card.badges.replay')
    : t('runtime.card.badges.current')
})

const hasResumedLineage = computed(() => {
  return !!(
    normalizedContinuationModeValue.value === 'resumed' ||
    normalizedContinuationStatusValue.value === 'resumed' ||
    normalizedContinuationStatusValue.value === 'completed_after_resume' ||
    safeString(props.resumedFromRunId).trim() ||
    safeString(props.resumedFromEventId).trim() ||
    safeString(props.resumedFromStage).trim()
  )
})

const hasResumableCheckpoint = computed(() => {
  if (!isCurrentMode.value || hasFormalLegalStatus.value) return false
  if (props.budgetExhausted || normalizeContinuationStatus(props.budgetStatus) === 'budget_exhausted') {
    return false
  }
  return props.canResume === true
})

const runtimeStatusLabel = computed(() => {
  if (!isCurrentMode.value) return ''
  const status = effectiveStatusToken.value

  if (status === 'manual') return buildLegalStatusLabel('manual')
  if (status === 'skipped') return buildLegalStatusLabel('skipped')
  if (status === 'denied') return buildLegalStatusLabel('denied')
  if (status === 'no_auto_reply') return buildLegalStatusLabel('no_auto_reply')

  if (status === 'pause_requested') return t('runtime.card.status.pauseRequested')
  if (status === 'interrupted') return t('runtime.card.status.interrupted')
  if (status === 'resumed') return t('runtime.card.status.resumed')
  if (status === 'completed_after_resume') return t('runtime.card.status.completedAfterResume')
  if (status === 'completed') return t('runtime.card.status.completed')
  if (status === 'running') return t('runtime.card.status.running')
  if (status === 'budget_exhausted') return t('runtime.card.status.budgetExhausted')
  if (status === 'failed') return t('runtime.card.status.failed')
  return ''
})

const runtimeBadgeText = computed(() => {
  if (!isCurrentMode.value) return ''
  if (runtimeStatusLabel.value) return runtimeStatusLabel.value
  if (normalizedContinuationModeValue.value === 'resumed') return t('runtime.card.badges.resumed')
  if (normalizedContinuationModeValue.value === 'restart_fresh') return t('runtime.card.badges.restartFresh')
  if (normalizedContinuationModeValue.value === 'fresh') return t('runtime.card.badges.fresh')
  return ''
})

const derivedHeadline = computed(() => {
  if (isReplayMode.value) return ''

  const status = effectiveStatusToken.value
  const mode = normalizedContinuationModeValue.value

  if (status === 'manual') return buildLegalHeadline('manual')
  if (status === 'skipped') return buildLegalHeadline('skipped')
  if (status === 'denied') return buildLegalHeadline('denied')
  if (status === 'no_auto_reply') return buildLegalHeadline('no_auto_reply')

  if (status === 'budget_exhausted') return t('runtime.card.headline.budgetExhausted')
  if (status === 'pause_requested') return t('runtime.card.headline.pauseRequested')
  if (status === 'interrupted') return t('runtime.card.headline.interrupted')
  if (status === 'completed_after_resume') return t('runtime.card.headline.completedAfterResume')
  if (status === 'resumed') return t('runtime.card.headline.resumed')
  if (status === 'completed' && mode === 'resumed') return t('runtime.card.headline.completedAfterResume')
  if (status === 'completed') return t('runtime.card.headline.completed')
  if (status === 'running' && mode === 'resumed') return t('runtime.card.headline.runningResumed')
  if (status === 'running') return t('runtime.card.headline.running')
  if (mode === 'resumed') return t('runtime.card.headline.lineageResumed')
  if (mode === 'restart_fresh') return t('runtime.card.headline.restartFresh')
  if (mode === 'fresh') return t('runtime.card.headline.fresh')
  return ''
})

const defaultHeadline = computed(() => {
  if (isReplayMode.value) {
    return props.selectedRunId
      ? t('runtime.card.defaultHeadline.replayWithId', { id: props.selectedRunId })
      : t('runtime.card.defaultHeadline.replay')
  }
  return t('runtime.card.defaultHeadline.current')
})

const metaLine = computed(() => {
  const parts = []

  if (props.badgeSummary) parts.push(normalizeDisplayText(props.badgeSummary))

  if (isReplayMode.value && props.selectedRunId) {
    parts.push(t('runtime.card.meta.viewingRun', { id: props.selectedRunId }))
  }

  const phaseLabel = formatStageLabel(props.runtimePhase || props.latestStage)
  if (isCurrentMode.value && phaseLabel && !hasFormalLegalStatus.value) {
    parts.push(t('runtime.card.meta.phase', { phase: phaseLabel }))
  }

  if (isCurrentMode.value && hasResumedLineage.value && props.resumedFromRunId && !hasFormalLegalStatus.value) {
    const from = [t('runtime.card.meta.resumedFromRun', { runId: props.resumedFromRunId })]
    if (props.resumedFromStage) from.push(formatStageLabel(props.resumedFromStage))
    parts.push(from.join(' · '))
  }

  return uniqStrings(parts).join(' · ')
})

const runtimeSemanticChips = computed(() => {
  const chips = []
  if (!isCurrentMode.value) return chips

  if (hasFormalLegalStatus.value) {
    const legalLabel = buildLegalStatusLabel(formalLegalStatusToken.value)
    if (legalLabel) {
      chips.push({
        label: legalLabel,
        className: formalLegalStatusToken.value === 'denied' ? 'state-danger' : 'state-accent',
      })
    }

    if (props.canAcceptNewPrompt) {
      chips.push({ label: t('runtime.card.badges.canSendNewPrompt'), className: 'state-success' })
    }

    return chips
  }

  if (normalizedContinuationModeValue.value === 'resumed') {
    chips.push({ label: t('runtime.card.badges.resumed'), className: 'state-accent' })
  } else if (normalizedContinuationModeValue.value === 'restart_fresh') {
    chips.push({ label: t('runtime.card.badges.restartFresh'), className: 'state-neutral' })
  } else if (normalizedContinuationModeValue.value === 'fresh') {
    chips.push({ label: t('runtime.card.badges.fresh'), className: 'state-neutral' })
  }

  if (runtimeStatusLabel.value) {
    const tone =
      runtimeStatusLabel.value === t('runtime.card.status.completed') ? 'state-success'
      : runtimeStatusLabel.value === t('runtime.card.status.completedAfterResume') ? 'state-success'
      : runtimeStatusLabel.value === t('runtime.card.status.interrupted') ? 'state-danger'
      : runtimeStatusLabel.value === t('runtime.card.status.failed') ? 'state-danger'
      : runtimeStatusLabel.value === t('runtime.card.status.budgetExhausted') ? 'state-danger'
      : runtimeStatusLabel.value === t('runtime.card.status.pauseRequested') ? 'state-info'
      : runtimeStatusLabel.value === t('runtime.card.status.running') ? 'state-info'
      : runtimeStatusLabel.value === t('runtime.card.status.resumed') ? 'state-accent'
      : 'state-neutral'

    chips.push({
      label: runtimeStatusLabel.value,
      className: tone,
    })
  }

  if (props.pauseEffective) {
    chips.push({ label: t('runtime.card.badges.pausedAtCheckpoint'), className: 'state-accent' })
  }

  if (hasResumableCheckpoint.value) {
    chips.push({ label: t('runtime.card.badges.resumable'), className: 'state-accent' })
  }

  if (props.canAcceptNewPrompt) {
    chips.push({ label: t('runtime.card.badges.canSendNewPrompt'), className: 'state-success' })
  } else if (safeString(props.controlBlockReason).trim()) {
    chips.push({
      label: formatControlBlockReasonLabel(props.controlBlockReason),
      className:
        normalizeToken(props.controlBlockReason) === 'pause_requested_pending_checkpoint'
          ? 'state-info'
          : normalizeToken(props.controlBlockReason) === 'resume_ready'
            ? 'state-accent'
            : 'state-danger',
    })
  }

  if (props.errorBlockingResume) {
    chips.push({ label: t('runtime.card.badges.resumeBlocked'), className: 'state-danger' })
  }

  if (props.budgetExhausted) {
    chips.push({ label: t('runtime.card.badges.budgetExhausted'), className: 'state-danger' })
  }

  return chips
})

const skillSummaryChips = computed(() => {
  if (!isCurrentMode.value) return []

  const src = normalizedSkillSummary.value
  if (!src.has_skills) return []

  const chips = [t('runtime.card.skillSummary.skills')]

  if (src.strategy) chips.push(src.strategy)
  if (src.enabled_count > 0) chips.push(t('runtime.card.skillSummary.enabled', { count: src.enabled_count }))
  if (src.applied_count > 0) chips.push(t('runtime.card.skillSummary.applied', { count: src.applied_count }))
  if (src.resolved_items_count > 0) chips.push(t('runtime.card.skillSummary.resolved', { count: src.resolved_items_count }))
  if (src.step_count > 0) chips.push(t('runtime.card.skillSummary.steps', { count: src.step_count }))
  if (src.has_applied_prompt) chips.push(t('runtime.card.skillSummary.appliedPrompt'))
  if (src.has_available_not_enabled) chips.push(t('runtime.card.skillSummary.availableNotEnabled'))
  if (src.has_missing) chips.push(t('runtime.card.skillSummary.missing'))
  if (src.has_skipped) chips.push(t('runtime.card.skillSummary.skipped'))
  if (src.source_type) chips.push(t('runtime.card.skillSummary.source', { value: normalizeDisplayText(src.source_type) }))
  if (src.source_event_type) chips.push(t('runtime.card.skillSummary.event', { value: normalizeDisplayText(src.source_event_type) }))

  return chips
})

const displaySummaryText = computed(() => {
  const text = safeString(props.summaryText).trim()
  if (text) return normalizeDisplayText(text)

  const fallback = safeString(props.resultEntry?.summary).trim()
  if (fallback) return normalizeDisplayText(fallback)

  if (isReplayMode.value) return ''

  if (hasFormalLegalStatus.value) {
    const legal = buildLegalSummary(formalLegalStatusToken.value)
    if (legal) return legal
  }

  const checkpointFallback = safeString(props.checkpointSummary).trim()
  if (checkpointFallback) return normalizeDisplayText(checkpointFallback)

  const skillFallback = normalizedSkillSummary.value.summary_text
  if (skillFallback) return normalizeDisplayText(skillFallback)

  const status = effectiveStatusToken.value
  const checkpointStage = formatStageLabel(props.checkpointStage || props.runtimePhase)
  const resumedStage = formatStageLabel(props.resumedFromStage)
  const blockReason = normalizeToken(props.controlBlockReason)

  if (status === 'budget_exhausted') {
    if (checkpointStage) {
      return t('runtime.card.summary.budgetExhaustedAtStage', { stage: checkpointStage })
    }
    return t('runtime.card.summary.budgetExhausted')
  }

  if (status === 'pause_requested') {
    if (checkpointStage) return t('runtime.card.summary.pauseRequestedAtStage', { stage: checkpointStage })
    return t('runtime.card.summary.pauseRequested')
  }

  if (status === 'interrupted') {
    if (checkpointStage) return t('runtime.card.summary.interruptedAtStage', { stage: checkpointStage })
    return t('runtime.card.summary.interrupted')
  }

  if (status === 'resumed') {
    if (resumedStage) return t('runtime.card.summary.resumedAtStage', { stage: resumedStage })
    return t('runtime.card.summary.resumed')
  }

  if (status === 'completed_after_resume') {
    return t('runtime.card.summary.completedAfterResume')
  }

  if (status === 'completed' && normalizedContinuationModeValue.value === 'resumed') {
    return t('runtime.card.summary.completedResumed')
  }

  if (blockReason === 'pause_requested_pending_checkpoint') {
    return checkpointStage
      ? t('runtime.card.summary.waitingCheckpointAtStage', { stage: checkpointStage })
      : t('runtime.card.summary.waitingCheckpoint')
  }

  if (blockReason === 'resume_ready') {
    return checkpointStage
      ? t('runtime.card.summary.resumeReadyAtStage', { stage: checkpointStage })
      : t('runtime.card.summary.resumeReady')
  }

  if (blockReason === 'run_running') {
    return t('runtime.card.summary.runRunning')
  }

  return ''
})

const sendBlockedHint = computed(() => {
  if (!isCurrentMode.value || hasFormalLegalStatus.value) return ''
  if (props.canAcceptNewPrompt !== false) return ''

  const text = formatControlBlockReasonLabel(props.controlBlockReason)
  if (!text) return ''

  const controlHintText = normalizeDisplayText(props.controlHint)
  if (controlHintText && controlHintText === text) return ''

  return text
})

const checkpointSummaryText = computed(() => {
  if (!isCurrentMode.value || hasFormalLegalStatus.value) return ''
  const text = safeString(props.checkpointSummary).trim()
  if (!text) return ''
  const normalized = normalizeDisplayText(text)
  if (displaySummaryText.value === normalized) return ''
  return normalized
})

const runtimeDetailRows = computed(() => {
  if (!isCurrentMode.value) return []

  const rows = []

  if (hasFormalLegalStatus.value) {
    rows.push({
      label: t('runtime.card.detail.runtime'),
      value: buildLegalStatusLabel(formalLegalStatusToken.value),
    })

    const budgetSummary = formatBudgetSummary(
      props.stepBudgetTotal,
      props.stepBudgetUsed,
      props.stepBudgetRemaining,
      props.budgetExhausted,
      props.budgetStatus
    )

    if (budgetSummary) {
      rows.push({ label: t('runtime.card.detail.stepBudget'), value: budgetSummary })
    }

    return rows.slice(0, 5)
  }

  const runtimeStateLabel = normalizeDisplayText(props.runtimeState)
  const runtimePhaseLabel = formatStageLabel(props.runtimePhase)
  const checkpointStage = formatStageLabel(props.checkpointStage)
  const checkpointRef = safeString(props.resumeCheckpointRef).trim()
  const interruptionReason = formatReasonLabel(props.interruptionReason)
  const pauseReason = formatReasonLabel(props.pauseReason)
  const blockReason = formatControlBlockReasonLabel(props.controlBlockReason)
  const resumedFromRunId = safeString(props.resumedFromRunId).trim()
  const resumedFromEventId = safeString(props.resumedFromEventId).trim()
  const resumedFromStage = formatStageLabel(props.resumedFromStage)
  const lastCompletedStep = formatStageLabel(props.lastCompletedStep)
  const pauseAtText = formatDateTimeText(props.pausedAt || props.pauseEffectiveAt)
  const pauseRequestedAtText = formatDateTimeText(props.pauseRequestedAt)
  const budgetSummary = formatBudgetSummary(
    props.stepBudgetTotal,
    props.stepBudgetUsed,
    props.stepBudgetRemaining,
    props.budgetExhausted,
    props.budgetStatus
  )

  if (runtimeStateLabel || runtimePhaseLabel) {
    const parts = []
    if (runtimeStateLabel) parts.push(runtimeStateLabel)
    if (runtimePhaseLabel) parts.push(runtimePhaseLabel)
    rows.push({ label: t('runtime.card.detail.runtime'), value: parts.join(' · ') })
  }

  if (checkpointStage) {
    const label =
      effectiveStatusToken.value === 'resumed' ||
      effectiveStatusToken.value === 'completed_after_resume' ||
      hasResumedLineage.value
        ? t('runtime.card.detail.resumePoint')
        : t('runtime.card.detail.checkpoint')
    rows.push({ label, value: checkpointStage })
  } else if (checkpointRef) {
    rows.push({ label: t('runtime.card.detail.checkpointRef'), value: checkpointRef })
  }

  if (interruptionReason) {
    rows.push({ label: t('runtime.card.detail.stopReason'), value: interruptionReason })
  } else if (pauseReason && (props.pauseRequested || effectiveStatusToken.value === 'pause_requested')) {
    rows.push({ label: t('runtime.card.detail.pauseReason'), value: pauseReason })
  } else if (blockReason) {
    rows.push({ label: t('runtime.card.detail.controlBlock'), value: blockReason })
  }

  if (props.pauseEffective && pauseAtText) {
    rows.push({ label: t('runtime.card.detail.pausedAt'), value: pauseAtText })
  } else if (props.pauseRequestAccepted && pauseRequestedAtText) {
    rows.push({ label: t('runtime.card.detail.pauseRequestedAt'), value: pauseRequestedAtText })
  }

  if (resumedFromRunId) {
    const parts = [resumedFromRunId]
    if (resumedFromStage) parts.push(resumedFromStage)
    if (resumedFromEventId) parts.push(resumedFromEventId)
    rows.push({ label: t('runtime.card.detail.resumedFrom'), value: parts.join(' · ') })
  } else if (props.resumeReason) {
    rows.push({ label: t('runtime.card.detail.resumeReason'), value: formatReasonLabel(props.resumeReason) })
  } else if (lastCompletedStep) {
    rows.push({ label: t('runtime.card.detail.lastCompleted'), value: lastCompletedStep })
  }

  if (budgetSummary) {
    rows.push({ label: t('runtime.card.detail.stepBudget'), value: budgetSummary })
  }

  if (hasResumableCheckpoint.value && !hasResumedLineage.value) {
    rows.push({ label: t('runtime.card.detail.resumeCapability'), value: t('runtime.card.detailValue.canResumeFromCheckpoint') })
  }

  if (rows.length < 4 && props.canAcceptNewPrompt) {
    rows.push({ label: t('runtime.card.detail.newPrompt'), value: t('runtime.card.detailValue.canStartFreshSend') })
  }

  return rows.slice(0, 5)
})

const effectSummary = computed(() => {
  if (!isCurrentMode.value || hasFormalLegalStatus.value) return { chips: [], text: '' }

  const dispositionCounts = countEffectDispositions(props.effectDispositions)
  const skippedEffectsCount = safeArray(props.skippedEffects).length
  const skippedCount = Math.max(dispositionCounts.skipped, skippedEffectsCount)
  const chips = []

  if (skippedCount > 0) {
    chips.push({ label: t('runtime.card.effects.skipped', { count: skippedCount }), className: 'state-accent' })
  }
  if (dispositionCounts.reused > 0) {
    chips.push({ label: t('runtime.card.effects.reused', { count: dispositionCounts.reused }), className: 'state-accent' })
  }
  if (dispositionCounts.execute > 0) {
    chips.push({ label: t('runtime.card.effects.execute', { count: dispositionCounts.execute }), className: 'state-info' })
  }
  if (dispositionCounts.repaired > 0) {
    chips.push({ label: t('runtime.card.effects.repair', { count: dispositionCounts.repaired }), className: 'state-danger' })
  }

  let text = ''
  if (skippedCount > 0 || dispositionCounts.reused > 0) {
    text = t('runtime.card.effects.summaryReuse')
  } else if (dispositionCounts.repaired > 0) {
    text = t('runtime.card.effects.summaryRepair')
  }

  return { chips, text }
})

const displayRecentEntries = computed(() => {
  const normalized = safeArray(props.recentEntries).map((entry) => {
    const row = safeObject(entry)
    return {
      ...row,
      badge: normalizeDisplayText(row.badge),
      title: normalizeDisplayText(row.title),
      actor: normalizeDisplayText(row.actor),
      summary: normalizeDisplayText(row.summary),
    }
  })

  if (!hasFormalLegalStatus.value) return normalized
  return normalized.filter((entry) => entryHasLegalRuntimeSignal(entry))
})

const showControlRow = computed(() => {
  return isCurrentMode.value && !hasFormalLegalStatus.value && !!(
    props.showPauseAction ||
    props.showResumeAction ||
    props.controlHint
  )
})

const emptyText = computed(() => {
  if (props.loading) {
    return isReplayMode.value
      ? t('runtime.card.empty.loadingReplay')
      : t('runtime.card.empty.loadingCurrent')
  }

  if (props.error) {
    return props.error
  }

  if (isReplayMode.value) {
    return props.selectedRunId
      ? t('runtime.card.empty.noReplayResult')
      : t('runtime.card.empty.chooseReplay')
  }

  if (hasFormalLegalStatus.value) {
    return buildLegalSummary(formalLegalStatusToken.value)
  }

  if (safeString(props.controlBlockReason).trim()) {
    return formatControlBlockReasonLabel(props.controlBlockReason)
  }

  return t('runtime.card.empty.noResult')
})

const displayStatusText = computed(() => {
  return normalizeDisplayText(props.statusText) || runtimeStatusLabel.value || t('runtime.card.status.noRun')
})

const displayPauseText = computed(() => {
  return normalizeDisplayText(props.pauseText) || t('runtime.card.actions.pauseCurrent')
})

const displayResumeText = computed(() => {
  return normalizeDisplayText(props.resumeText) || t('runtime.card.actions.resumeFromCheckpoint')
})

const displayControlHint = computed(() => {
  return normalizeDisplayText(props.controlHint)
})

const displayBriefBadge = computed(() => {
  const explicitBadge = normalizeDisplayText(props.resultEntry?.badge)
  if (explicitBadge) return explicitBadge

  const explicitStatus = normalizeDisplayText(props.statusText)
  if (explicitStatus) return explicitStatus

  if (isReplayMode.value) {
    return normalizeDisplayText(props.latestStage || modeBadge.value)
  }

  return normalizeDisplayText(runtimeBadgeText.value || modeBadge.value)
})

const displayHeadline = computed(() => {
  const explicitHeadline = normalizeDisplayText(props.headline)
  if (explicitHeadline) return explicitHeadline

  if (isCurrentMode.value && runtimeStatusLabel.value) {
    return runtimeStatusLabel.value
  }

  return derivedHeadline.value || defaultHeadline.value
})

const briefTone = computed(() => {
  if (isCurrentMode.value && props.budgetExhausted && !hasFormalLegalStatus.value) return 'danger'

  const fromRuntimeState = classifyToneFromText(runtimeStatusLabel.value)
  if (fromRuntimeState !== 'neutral') return fromRuntimeState

  const fromBadge = classifyToneFromText(displayBriefBadge.value)
  if (fromBadge !== 'neutral') return fromBadge

  const fromTitle = classifyToneFromText(displayHeadline.value)
  if (fromTitle !== 'neutral') return fromTitle

  const fromTypeClass = classifyToneFromTypeClass(props.resultEntry?.typeClass || '')
  if (fromTypeClass !== 'neutral') return fromTypeClass

  const fromStatus = classifyToneFromText(displayStatusText.value)
  if (fromStatus !== 'neutral') return fromStatus

  if (props.live) return 'info'
  return 'neutral'
})

const statusChipClass = computed(() => {
  return {
    live: props.live && !props.error && briefTone.value === 'info',
    error: briefTone.value === 'danger' || !!props.error,
    done: briefTone.value === 'success',
    accent: briefTone.value === 'accent',
    info: briefTone.value === 'info' && !props.live,
  }
})

function entryTone(entry) {
  const row = safeObject(entry)

  const fromBadge = classifyToneFromText(row.badge)
  if (fromBadge !== 'neutral') return fromBadge

  const fromTitle = classifyToneFromText(row.title)
  if (fromTitle !== 'neutral') return fromTitle

  const fromActor = classifyToneFromText(row.actor)
  if (fromActor !== 'neutral') return fromActor

  const fromTypeClass = classifyToneFromTypeClass(row.typeClass)
  if (fromTypeClass !== 'neutral') return fromTypeClass

  return 'neutral'
}
</script>

<style scoped>
.room-runtime-section {
  margin-bottom: 0.9rem;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sidebar-bg) 90%, transparent);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.room-runtime-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.62rem;
}

.room-runtime-section-title {
  font-size: 0.78rem;
  font-weight: 800;
  color: var(--text-main);
  letter-spacing: 0.2px;
}

.room-runtime-status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 22px;
  max-width: 100%;
  padding: 0 0.48rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 94%, transparent);
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-runtime-status-chip.live,
.room-runtime-status-chip.info {
  border-color: rgba(74, 118, 255, 0.24);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-status-chip.done {
  border-color: rgba(31, 155, 85, 0.2);
  background: rgba(31, 155, 85, 0.1);
  color: #1f9b55;
}

.room-runtime-status-chip.error {
  border-color: rgba(208, 95, 95, 0.24);
  background: rgba(208, 95, 95, 0.1);
  color: #d05f5f;
}

.room-runtime-status-chip.accent {
  border-color: rgba(122, 102, 255, 0.24);
  background: rgba(122, 102, 255, 0.1);
  color: #8b7cff;
}

.room-runtime-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  margin-bottom: 0.6rem;
}

.room-runtime-mode-group {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-width: 0;
}

.room-runtime-mode-btn {
  height: 28px;
  padding: 0 0.68rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.room-runtime-mode-btn:hover:not(:disabled) {
  border-color: var(--selected);
  color: var(--selected);
  background: var(--selected-bg);
}

.room-runtime-mode-btn:focus-visible {
  outline: none;
  border-color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 20%, transparent);
}

.room-runtime-mode-btn.active {
  border-color: rgba(74, 118, 255, 0.24);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-refresh-btn {
  flex-shrink: 0;
  height: 28px;
  padding: 0 0.72rem;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-main);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.room-runtime-refresh-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.room-runtime-refresh-btn:focus-visible {
  outline: none;
  border-color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 20%, transparent);
}

.room-runtime-refresh-btn:disabled,
.room-runtime-refresh-btn[disabled] {
  opacity: 0.62;
  cursor: default !important;
}

.room-runtime-refresh-btn:disabled:hover,
.room-runtime-refresh-btn[disabled]:hover {
  cursor: default !important;
  border-color: color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-main);
  transform: none;
}

.room-runtime-replay-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.6rem;
}

.room-runtime-replay-label {
  flex-shrink: 0;
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-weight: 700;
}

.room-runtime-run-select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  height: 30px;
  padding: 0 0.68rem;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-main);
  font-size: 0.74rem;
  outline: none;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.room-runtime-run-select:focus {
  border-color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 18%, transparent);
}

.room-runtime-control-row {
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  margin-bottom: 0.62rem;
  padding: 0.06rem 0 0;
}

.room-runtime-control-actions {
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex-wrap: wrap;
}

.room-runtime-action-btn {
  min-height: 30px;
  padding: 0 0.8rem;
  border-radius: 8px;
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-main);
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.room-runtime-action-btn:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
  color: var(--selected);
}

.room-runtime-action-btn:focus-visible {
  outline: none;
  border-color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 18%, transparent);
}

.room-runtime-action-btn.primary {
  border-color: rgba(74, 118, 255, 0.24);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-action-btn.primary:hover:not(:disabled) {
  border-color: #5e84ff;
  background: rgba(74, 118, 255, 0.16);
  color: #5e84ff;
}

.room-runtime-action-btn:disabled,
.room-runtime-action-btn[disabled] {
  opacity: 0.62;
  cursor: default !important;
}

.room-runtime-action-btn:disabled:hover,
.room-runtime-action-btn[disabled]:hover {
  cursor: default !important;
  transform: none;
  box-shadow: none;
  border-color: color-mix(in srgb, var(--line) 92%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-main);
}

.room-runtime-action-btn.primary:disabled,
.room-runtime-action-btn.primary[disabled] {
  border-color: rgba(74, 118, 255, 0.24);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-action-btn.primary:disabled:hover,
.room-runtime-action-btn.primary[disabled]:hover {
  border-color: rgba(74, 118, 255, 0.24);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-control-hint {
  font-size: 0.72rem;
  line-height: 1.45;
  color: var(--text-secondary);
  overflow: hidden;
  word-break: break-word;
}

.room-runtime-brief-card {
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 98%, transparent);
  padding: 0.72rem 0.76rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  overflow: hidden;
}

.room-runtime-brief-card.type-plan,
.room-runtime-brief-card.type-delegate,
.room-runtime-brief-card.type-supervisor,
.room-runtime-brief-card.type-route,
.room-runtime-brief-card.type-message,
.room-runtime-brief-card.type-final,
.room-runtime-brief-card.type-error,
.room-runtime-brief-card.type-abort,
.room-runtime-brief-card.type-aborted {
  border-left-width: 3px;
}

.room-runtime-brief-card.type-plan {
  border-left-color: #5e84ff;
}

.room-runtime-brief-card.type-delegate {
  border-left-color: #a56eff;
}

.room-runtime-brief-card.type-supervisor {
  border-left-color: #17a57a;
}

.room-runtime-brief-card.type-route {
  border-left-color: #6da9ff;
}

.room-runtime-brief-card.type-message {
  border-left-color: #e0aa2f;
}

.room-runtime-brief-card.type-final {
  border-left-color: #1f9b55;
}

.room-runtime-brief-card.type-error,
.room-runtime-brief-card.type-abort,
.room-runtime-brief-card.type-aborted {
  border-left-color: #d05f5f;
}

.room-runtime-brief-card.tone-danger {
  background: color-mix(in srgb, var(--editor-bg) 94%, rgba(208, 95, 95, 0.08));
  border-color: color-mix(in srgb, var(--line) 82%, rgba(208, 95, 95, 0.22));
}

.room-runtime-brief-card.tone-success {
  background: color-mix(in srgb, var(--editor-bg) 94%, rgba(31, 155, 85, 0.08));
  border-color: color-mix(in srgb, var(--line) 82%, rgba(31, 155, 85, 0.2));
}

.room-runtime-brief-card.tone-accent {
  background: color-mix(in srgb, var(--editor-bg) 94%, rgba(122, 102, 255, 0.08));
  border-color: color-mix(in srgb, var(--line) 82%, rgba(122, 102, 255, 0.22));
}

.room-runtime-brief-card.tone-info {
  background: color-mix(in srgb, var(--editor-bg) 94%, rgba(74, 118, 255, 0.08));
  border-color: color-mix(in srgb, var(--line) 82%, rgba(74, 118, 255, 0.2));
}

.room-runtime-brief-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  min-width: 0;
  overflow: hidden;
}

.room-runtime-brief-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 20px;
  max-width: 100%;
  padding: 0 0.44rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.room-runtime-brief-badge.tone-info {
  background: rgba(74, 118, 255, 0.12);
  border-color: rgba(74, 118, 255, 0.18);
  color: #5e84ff;
}

.room-runtime-brief-badge.tone-success {
  background: rgba(31, 155, 85, 0.12);
  border-color: rgba(31, 155, 85, 0.18);
  color: #1f9b55;
}

.room-runtime-brief-badge.tone-danger {
  background: rgba(208, 95, 95, 0.12);
  border-color: rgba(208, 95, 95, 0.18);
  color: #d05f5f;
}

.room-runtime-brief-badge.tone-accent {
  background: rgba(122, 102, 255, 0.12);
  border-color: rgba(122, 102, 255, 0.18);
  color: #8b7cff;
}

.room-runtime-brief-title {
  min-width: 0;
  flex: 1 1 auto;
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-runtime-brief-room {
  margin-left: auto;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.68rem;
  color: var(--text-secondary);
  font-family: var(--font-mono, monospace);
}

.room-runtime-brief-meta {
  margin-top: 0.36rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: hidden;
}

.room-runtime-chip-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
  margin-top: 0.44rem;
  min-width: 0;
}

.room-runtime-chip-row-effects {
  margin-top: 0.5rem;
}

.room-runtime-chip {
  display: inline-flex;
  align-items: center;
  min-height: 20px;
  max-width: 100%;
  padding: 0 0.44rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-runtime-chip.skill {
  background: rgba(168, 85, 247, 0.12);
  border-color: rgba(168, 85, 247, 0.22);
  color: #b78cff;
}

.room-runtime-chip.state-neutral {
  background: rgba(148, 163, 184, 0.1);
  border-color: rgba(148, 163, 184, 0.16);
  color: var(--text-secondary);
}

.room-runtime-chip.state-info {
  background: rgba(74, 118, 255, 0.12);
  border-color: rgba(74, 118, 255, 0.18);
  color: #5e84ff;
}

.room-runtime-chip.state-success {
  background: rgba(31, 155, 85, 0.12);
  border-color: rgba(31, 155, 85, 0.18);
  color: #1f9b55;
}

.room-runtime-chip.state-danger {
  background: rgba(208, 95, 95, 0.12);
  border-color: rgba(208, 95, 95, 0.18);
  color: #d05f5f;
}

.room-runtime-chip.state-accent {
  background: rgba(122, 102, 255, 0.12);
  border-color: rgba(122, 102, 255, 0.18);
  color: #8b7cff;
}

.room-runtime-brief-summary {
  margin-top: 0.44rem;
  font-size: 0.78rem;
  line-height: 1.56;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  overflow: hidden;
}

.room-runtime-inline-note {
  margin-top: 0.42rem;
  font-size: 0.74rem;
  line-height: 1.5;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  overflow: hidden;
}

.room-runtime-detail-list {
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
  margin-top: 0.52rem;
  padding-top: 0.5rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
}

.room-runtime-detail-item {
  display: flex;
  gap: 0.45rem;
  align-items: flex-start;
  font-size: 0.72rem;
  line-height: 1.45;
  min-width: 0;
}

.room-runtime-detail-label {
  flex-shrink: 0;
  min-width: 68px;
  color: var(--text-secondary);
  font-weight: 700;
}

.room-runtime-detail-value {
  min-width: 0;
  color: var(--text-main);
  word-break: break-word;
  overflow: hidden;
}

.room-runtime-empty {
  margin-top: 0.44rem;
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--text-secondary);
  overflow: hidden;
  word-break: break-word;
}

.room-runtime-mini-list {
  margin-top: 0.66rem;
  display: flex;
  flex-direction: column;
  gap: 0.36rem;
  min-width: 0;
}

.room-runtime-mini-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
  max-width: 100%;
  padding: 0.4rem 0.48rem;
  border-radius: 8px;
  background: color-mix(in srgb, var(--editor-bg) 97%, transparent);
  border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
  overflow: hidden;
}

.room-runtime-mini-item.type-plan,
.room-runtime-mini-item.type-delegate,
.room-runtime-mini-item.type-supervisor,
.room-runtime-mini-item.type-route,
.room-runtime-mini-item.type-message,
.room-runtime-mini-item.type-final,
.room-runtime-mini-item.type-error,
.room-runtime-mini-item.type-abort,
.room-runtime-mini-item.type-aborted {
  border-left-width: 3px;
}

.room-runtime-mini-item.type-plan {
  border-left-color: #5e84ff;
}

.room-runtime-mini-item.type-delegate {
  border-left-color: #a56eff;
}

.room-runtime-mini-item.type-supervisor {
  border-left-color: #17a57a;
}

.room-runtime-mini-item.type-route {
  border-left-color: #6da9ff;
}

.room-runtime-mini-item.type-message {
  border-left-color: #e0aa2f;
}

.room-runtime-mini-item.type-final {
  border-left-color: #1f9b55;
}

.room-runtime-mini-item.type-error,
.room-runtime-mini-item.type-abort,
.room-runtime-mini-item.type-aborted {
  border-left-color: #d05f5f;
}

.room-runtime-mini-item.tone-danger {
  background: color-mix(in srgb, var(--editor-bg) 95%, rgba(208, 95, 95, 0.06));
}

.room-runtime-mini-item.tone-success {
  background: color-mix(in srgb, var(--editor-bg) 95%, rgba(31, 155, 85, 0.06));
}

.room-runtime-mini-item.tone-accent {
  background: color-mix(in srgb, var(--editor-bg) 95%, rgba(122, 102, 255, 0.06));
}

.room-runtime-mini-item.tone-info {
  background: color-mix(in srgb, var(--editor-bg) 95%, rgba(74, 118, 255, 0.06));
}

.room-runtime-mini-badge {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 40%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 18px;
  font-size: 0.66rem;
  line-height: 1;
  padding: 0.16rem 0.36rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-secondary);
  border: 1px solid rgba(148, 163, 184, 0.18);
  text-transform: uppercase;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.room-runtime-mini-badge.tone-info {
  background: rgba(74, 118, 255, 0.12);
  border-color: rgba(74, 118, 255, 0.18);
  color: #5e84ff;
}

.room-runtime-mini-badge.tone-success {
  background: rgba(31, 155, 85, 0.12);
  border-color: rgba(31, 155, 85, 0.18);
  color: #1f9b55;
}

.room-runtime-mini-badge.tone-danger {
  background: rgba(208, 95, 95, 0.12);
  border-color: rgba(208, 95, 95, 0.18);
  color: #d05f5f;
}

.room-runtime-mini-badge.tone-accent {
  background: rgba(122, 102, 255, 0.12);
  border-color: rgba(122, 102, 255, 0.18);
  color: #8b7cff;
}

.room-runtime-mini-title {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
  font-size: 0.74rem;
  font-weight: 600;
}

.room-runtime-mini-actor {
  min-width: 0;
  flex: 0 1 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--selected);
  font-size: 0.7rem;
}

.room-runtime-mini-time {
  flex-shrink: 0;
  color: var(--text-muted);
  font-size: 0.68rem;
}

@media (max-width: 520px) {
  .room-runtime-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .room-runtime-mode-group {
    width: 100%;
  }

  .room-runtime-mode-btn {
    flex: 1 1 0;
    justify-content: center;
  }

  .room-runtime-refresh-btn {
    width: 100%;
  }

  .room-runtime-replay-row {
    align-items: stretch;
    flex-direction: column;
  }

  .room-runtime-brief-room {
    margin-left: 0;
    max-width: 100%;
  }

  .room-runtime-detail-item {
    flex-direction: column;
    gap: 0.15rem;
  }

  .room-runtime-detail-label {
    min-width: 0;
  }

  .room-runtime-mini-item {
    flex-wrap: wrap;
  }

  .room-runtime-mini-badge,
  .room-runtime-mini-title,
  .room-runtime-mini-actor {
    max-width: 100%;
    width: 100%;
    white-space: normal;
  }
}
</style>
