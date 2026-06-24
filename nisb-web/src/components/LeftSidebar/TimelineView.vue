<template>
  <div class="timeline-container">
    <div class="heatmap-section" ref="heatmapHost">
      <HeatmapCalendar :key="heatmapRenderKey" :data="heatmapData" />
    </div>

    <div class="timeline-toolbar">
      <div class="toolbar-left"></div>

      <div
        class="toolbar-right"
        ref="toolbarRowRef"
        @mouseenter="on_toolbar_enter"
        @mouseleave="on_toolbar_leave"
        @mousemove="on_toolbar_mouse_move"
        @scroll="on_toolbar_scroll"
      >
        <select
          class="toolbar-select"
          v-model.number="days"
          :disabled="loading"
          :title="t('timeline.toolbar.daysTitle')"
        >
          <option :value="7">{{ t('timeline.toolbar.daysOption', { count: 7 }) }}</option>
          <option :value="14">{{ t('timeline.toolbar.daysOption', { count: 14 }) }}</option>
          <option :value="30">{{ t('timeline.toolbar.daysOption', { count: 30 }) }}</option>
        </select>

        <button
          class="toolbar-btn"
          :disabled="loading"
          @click="refreshAll"
          :title="t('timeline.toolbar.refreshTitle')"
        >
          {{ loading ? t('timeline.toolbar.loading') : t('timeline.toolbar.refresh') }}
        </button>

        <button
          v-if="!selectMode"
          class="toolbar-btn"
          :disabled="loading"
          @click="enterSelectMode"
          :title="t('timeline.toolbar.selectTitle')"
        >
          {{ t('timeline.toolbar.select') }}
        </button>

        <button
          v-else
          class="toolbar-btn danger"
          :disabled="loading || selectedCount === 0"
          @click="deleteSelected"
          :title="
            selectedCount
              ? t('timeline.toolbar.removeSelectedTitle', { count: selectedCount })
              : t('timeline.toolbar.removeSelectedEmptyTitle')
          "
        >
          {{ t('timeline.toolbar.removeSelected', { count: selectedCount }) }}
        </button>

        <button
          v-if="selectMode"
          class="toolbar-btn"
          :disabled="loading"
          @click="exitSelectMode"
          :title="t('timeline.toolbar.cancelTitle')"
        >
          {{ t('timeline.toolbar.cancel') }}
        </button>

        <button
          class="toolbar-btn"
          :disabled="loading"
          @click="pruneMissing"
          :title="t('timeline.toolbar.pruneMissingTitle')"
        >
          {{ t('timeline.toolbar.pruneMissing') }}
        </button>

        <button
          class="toolbar-btn"
          :disabled="loading"
          @click="compactActivityLog"
          :title="t('timeline.toolbar.compactTitle')"
        >
          {{ t('timeline.toolbar.compact') }}
        </button>

        <input
          class="toolbar-input"
          v-model.trim="hardDeletePattern"
          :disabled="loading"
          :placeholder="t('timeline.toolbar.patternPlaceholder')"
          :title="t('timeline.toolbar.patternTitle')"
          @keydown.enter.prevent="hardDeleteByPattern"
        />

        <button
          class="toolbar-btn danger"
          :disabled="loading || !hardDeletePattern"
          @click="hardDeleteByPattern"
          :title="t('timeline.toolbar.hardDeleteTitle')"
        >
          {{ t('timeline.toolbar.hardDelete') }}
        </button>
      </div>
    </div>

    <div class="activity-list">
      <RoomRuntimeSummaryCard
        :visible="show_room_runtime_section"
        :live="room_runtime_live"
        :error="room_runtime_error"
        :status-text="room_runtime_status_text"
        :room-id="room_runtime_room_id"
        :headline="room_runtime_headline"
        :badge-summary="room_runtime_badge_summary"
        :has-terminal-result="room_runtime_has_terminal_result"
        :latest-stage="room_runtime_latest_stage"
        :summary-text="room_runtime_summary_text"
        :result-entry="room_runtime_result_entry"
        :recent-entries="room_runtime_recent_entries"
        :view-mode="room_runtime_view_mode"
        :selected-run-id="room_runtime_selected_run_id"
        :run-options="room_runtime_run_options"
        :loading="room_runtime_loading"
        :runtime-skill-summary="room_runtime_skill_summary"
        :runtime-state="room_runtime_runtime_state"
        :runtime-phase="room_runtime_runtime_phase"
        :can-accept-new-prompt="room_runtime_can_accept_new_prompt"
        :control-block-reason="room_runtime_control_block_reason"
        :continuation-mode="room_runtime_continuation_mode"
        :continuation-status="room_runtime_continuation_status"
        :pause-requested="room_runtime_pause_requested"
        :pause-request-accepted="room_runtime_pause_request_accepted"
        :pause-reason="room_runtime_pause_reason"
        :pause-requested-at="room_runtime_pause_requested_at"
        :pause-effective="room_runtime_pause_effective"
        :paused-at="room_runtime_paused_at"
        :pause-effective-at="room_runtime_pause_effective_at"
        :interruption-reason="room_runtime_interruption_reason"
        :resume-ready="room_runtime_resume_ready"
        :resume-from-checkpoint="room_runtime_resume_from_checkpoint"
        :can-resume-from-checkpoint="room_runtime_can_resume_from_checkpoint"
        :resume-checkpoint-ref="room_runtime_resume_checkpoint_ref"
        :resume-token="room_runtime_resume_token"
        :resume-reason="room_runtime_resume_reason"
        :error-blocking-resume="room_runtime_error_blocking_resume"
        :resumed-from-run-id="room_runtime_resumed_from_run_id"
        :resumed-from-event-id="room_runtime_resumed_from_event_id"
        :resumed-from-stage="room_runtime_resumed_from_stage"
        :checkpoint-stage="room_runtime_checkpoint_stage"
        :checkpoint-summary="room_runtime_checkpoint_summary"
        :last-completed-step="room_runtime_last_completed_step"
        :skipped-effects="room_runtime_skipped_effects"
        :effect-dispositions="room_runtime_effect_dispositions"
        :step-budget-total="room_runtime_step_budget_total"
        :step-budget-used="room_runtime_step_budget_used"
        :step-budget-remaining="room_runtime_step_budget_remaining"
        :budget-status="room_runtime_budget_status"
        :budget-exhausted="room_runtime_budget_exhausted"
        :can-pause-current="room_runtime_can_pause_current"
        :can-resume="room_runtime_can_resume"
        :show-pause-action="room_runtime_show_pause_action"
        :pause-disabled="room_runtime_pause_disabled"
        :pause-text="room_runtime_pause_text"
        :show-resume-action="room_runtime_show_resume_action"
        :resume-disabled="room_runtime_resume_disabled"
        :resume-text="room_runtime_resume_text"
        :control-hint="room_runtime_control_hint"
        @switch-mode="handleRuntimeSwitchMode"
        @refresh="handleRuntimeRefresh"
        @select-run="handleRuntimeSelectRun"
        @pause-current="handleRuntimePauseCurrent"
        @resume-from-checkpoint="handleRuntimeResumeFromCheckpoint"
      />

      <div v-if="loading" class="empty-tip">{{ t('timeline.empty.loadingActivities') }}</div>
      <div v-else-if="!hasActivities" class="empty-tip">{{ t('timeline.empty.noActivities') }}</div>

      <template v-else>
        <ActivitySection
          v-if="activities.today?.length"
          :title="t('timeline.sections.today')"
          section-key="today"
          :items="activities.today"
          :expanded="expandedSections.today"
          :max-items="MAX_ITEMS_PER_SECTION"
          :active-key="activeKey"
          :select-mode="selectMode"
          :selected-event-ids="selectedEventIds"
          @toggle-expand="toggleSection('today')"
          @item-click="handleActivityClick"
          @toggle-select="toggleSelect"
          @delete-one="deleteOne"
          @show-tip="showTip"
          @move-tip="moveTip"
          @hide-tip="hideTip"
        />

        <ActivitySection
          v-if="activities.yesterday?.length"
          :title="t('timeline.sections.yesterday')"
          section-key="yesterday"
          :items="activities.yesterday"
          :expanded="expandedSections.yesterday"
          :max-items="MAX_ITEMS_PER_SECTION"
          :active-key="activeKey"
          :select-mode="selectMode"
          :selected-event-ids="selectedEventIds"
          @toggle-expand="toggleSection('yesterday')"
          @item-click="handleActivityClick"
          @toggle-select="toggleSelect"
          @delete-one="deleteOne"
          @show-tip="showTip"
          @move-tip="moveTip"
          @hide-tip="hideTip"
        />

        <ActivitySection
          v-if="activities.this_week?.length"
          :title="t('timeline.sections.thisWeek')"
          section-key="week"
          :items="activities.this_week"
          :expanded="expandedSections.week"
          :max-items="MAX_ITEMS_PER_SECTION"
          :active-key="activeKey"
          :select-mode="selectMode"
          :selected-event-ids="selectedEventIds"
          @toggle-expand="toggleSection('week')"
          @item-click="handleActivityClick"
          @toggle-select="toggleSelect"
          @delete-one="deleteOne"
          @show-tip="showTip"
          @move-tip="moveTip"
          @hide-tip="hideTip"
        />

        <ActivitySection
          v-if="activities.older?.length"
          :title="t('timeline.sections.older')"
          section-key="older"
          :items="activities.older"
          :expanded="expandedSections.older"
          :max-items="MAX_ITEMS_PER_SECTION"
          :active-key="activeKey"
          :strong-title="true"
          :select-mode="selectMode"
          :selected-event-ids="selectedEventIds"
          @toggle-expand="toggleSection('older')"
          @item-click="handleActivityClick"
          @toggle-select="toggleSelect"
          @delete-one="deleteOne"
          @show-tip="showTip"
          @move-tip="moveTip"
          @hide-tip="hideTip"
        />
      </template>

      <div
        v-if="tip.visible"
        class="path-tooltip"
        :style="{ left: tip.x + 'px', top: tip.y + 'px' }"
      >
        {{ tip.text }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'
import { useHoverScroll } from '../../composables/useHoverScroll'
import { useRoomStore } from '../../stores/room'
import { use_timeline_room_runtime } from '../../composables/left_sidebar/use_timeline_room_runtime'
import HeatmapCalendar from './HeatmapCalendar.vue'
import RoomRuntimeSummaryCard from './RoomRuntimeSummaryCard.vue'
import {
  normalizeToolResponse,
  pickDataValue,
  pickDataArray
} from '../../composables/left_sidebar/actions/response_normalizer'

const { callTool } = useMCP()
const roomStore = useRoomStore()
const { t } = useI18n()

function tr(key, params = {}) {
  return String(t(key, params) || '').replace(/\\n/g, '\n')
}

const loading = ref(false)
const days = ref(30)

const activities = ref({
  today: [],
  yesterday: [],
  this_week: [],
  older: []
})

const heatmapData = ref({})
const activeKey = ref(null)

const MAX_ITEMS_PER_SECTION = 60

const expandedSections = ref({
  today: true,
  yesterday: false,
  week: false,
  older: false
})

const selectMode = ref(false)
const selectedEventIds = ref(new Set())

const hardDeletePattern = ref('')

const selectedCount = computed(() => selectedEventIds.value.size)

const hasActivities = computed(() => {
  return (
    activities.value.today.length > 0 ||
    activities.value.yesterday.length > 0 ||
    activities.value.this_week.length > 0 ||
    activities.value.older.length > 0
  )
})

const allActivitiesFlat = computed(() => {
  return [
    ...(activities.value.today || []),
    ...(activities.value.yesterday || []),
    ...(activities.value.this_week || []),
    ...(activities.value.older || [])
  ]
})

function _request_idle(cb, { timeout = 1000 } = {}) {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    return window.requestIdleCallback(cb, { timeout })
  }
  return window.setTimeout(() => cb({ didTimeout: true, timeRemaining: () => 0 }), 0)
}

function _cancel_idle(id) {
  try {
    if (typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
      window.cancelIdleCallback(id)
    } else {
      clearTimeout(id)
    }
  } catch {}
}

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function emptyActivityGroups() {
  return {
    today: [],
    yesterday: [],
    this_week: [],
    older: []
  }
}

function looksLikePath(s) {
  return /[\\/\\\\]/.test(String(s || ''))
}

function getBaseNameAny(s) {
  if (!s) return ''
  const parts = String(s).split(/[\\/\\\\]/g)
  return parts[parts.length - 1] || ''
}

function isInternalCommPath(s) {
  const p = String(s || '').trim()
  if (!p) return false
  if (p.startsWith('/data/users/')) return true
  if (p.startsWith('/opt/mcp-gateway/')) return true
  return false
}

function isActionableActivity(activity) {
  if (!activity) return false

  if (activity.type === 'conversation') {
    return Boolean(String(activity.id || '').trim())
  }

  if (activity.type === 'document') {
    const lib = String(activity.library_id || activity.extra?.library_id || '').trim()
    const doc = String(activity.doc_id || activity.extra?.doc_id || '').trim()
    if (lib && doc) return true

    const p = String(activity.path || '').trim()
    if (p && !isInternalCommPath(p)) return true

    return false
  }

  if (activity.type === 'hebbian') return true

  return false
}

function displayTitle(activity) {
  if (!activity) return t('timeline.activity.unnamed')

  const docTitle = String(
    activity.doc_title || activity.doc_name || activity.extra?.doc_title || ''
  ).trim()

  if (activity.type === 'document') {
    if (docTitle) return docTitle

    const lib = String(activity.library_id || activity.extra?.library_id || '').trim()
    const doc = String(activity.doc_id || activity.extra?.doc_id || '').trim()
    if (lib && doc) {
      const tt = String(activity.title || '').trim()
      if (tt) return looksLikePath(tt) ? getBaseNameAny(tt) : tt
      return doc || t('timeline.activity.document')
    }

    const tt = String(activity.title || '').trim()
    const p = String(activity.path || '').trim()

    if (isInternalCommPath(p) || isInternalCommPath(tt)) {
      return t('timeline.activity.filteredInternalRecord')
    }

    const candidate = tt || p
    if (!candidate) return t('timeline.activity.file')
    if (looksLikePath(candidate)) return getBaseNameAny(candidate)
    return candidate
  }

  if (activity.type === 'conversation') {
    const tt = String(activity.title || activity.name || '').trim()
    return tt || activity.id || t('timeline.activity.conversation')
  }

  if (activity.type === 'hebbian') {
    const c = activity.concepts ?? 0
    const s = activity.synapses ?? 0
    return t('timeline.activity.hebbianTitle', { concepts: c, synapses: s })
  }

  return String(activity.title || activity.name || activity.id || t('timeline.activity.activity'))
}

function isDeletable(activity) {
  return activity && String(activity.event_id || '').trim()
}

function hoverTipText(activity) {
  if (!activity) return ''

  const safeReturn = (text) => {
    const tt = String(text || '').trim()
    if (!tt) return ''
    if (isInternalCommPath(tt)) return ''
    return tt
  }

  if (activity.type === 'document') {
    const lib = String(activity.library_id || activity.extra?.library_id || '').trim()
    const doc = String(activity.doc_id || activity.extra?.doc_id || '').trim()
    if (lib && doc) return t('timeline.tooltip.libraryDoc', { lib, doc })

    const p = String(activity.path || '').trim()
    if (p) return safeReturn(p)

    const tt = String(activity.title || '').trim()
    if (tt && looksLikePath(tt)) return safeReturn(tt)

    return ''
  }

  if (activity.type === 'conversation') {
    const id = String(activity.id || '').trim()
    const tt = String(activity.title || activity.name || '').trim()
    if (id && tt) return t('timeline.tooltip.conversationWithTitle', { id, title: tt })
    if (id) return t('timeline.tooltip.conversationId', { id })
    return ''
  }

  if (activity.type === 'hebbian') return String(activity.date || '').trim()
  return safeReturn(activity.path || activity.id || '')
}

const tip = ref({ visible: false, text: '', x: 0, y: 0 })

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

function positionTip(e) {
  const margin = 12
  const offsetX = 14
  const offsetY = 18
  tip.value.x = clamp(e.clientX + offsetX, margin, window.innerWidth - margin - 40)
  tip.value.y = clamp(e.clientY + offsetY, margin, window.innerHeight - margin - 24)
}

function showTip(activity, e) {
  const text = hoverTipText(activity)
  if (!text) return
  tip.value.visible = true
  tip.value.text = text
  positionTip(e)
}

function moveTip(e) {
  if (!tip.value.visible) return
  positionTip(e)
}

function hideTip() {
  tip.value.visible = false
}

function normalizeActivity(a) {
  if (!a || typeof a !== 'object') return a

  const extra = a.extra && typeof a.extra === 'object' ? a.extra : {}
  const kind = a.kind || extra.kind || null

  const eventId = a.event_id || a.eventId || extra.event_id || extra.eventId || null
  const origin = a.origin || extra.origin || 'activity_log'

  const libraryId = a.library_id || a.libraryId || extra.library_id || extra.libraryId || null
  const docId = a.doc_id || a.docId || extra.doc_id || extra.docId || null

  const spanIndex =
    (Number.isFinite(extra?.span?.index) ? extra.span.index : null) ??
    (Number.isFinite(a?.span_index) ? a.span_index : null) ??
    (Number.isFinite(a?.spanIndex) ? a.spanIndex : null) ??
    (Number.isFinite(a?.span_id) ? a.span_id : null) ??
    (Number.isFinite(a?.spanId) ? a.spanId : null) ??
    null

  const nextExtra = {
    ...extra,
    kind: kind || extra.kind,
    span:
      extra.span && typeof extra.span === 'object'
        ? {
            ...extra.span,
            index: Number.isFinite(extra.span.index) ? extra.span.index : spanIndex
          }
        : spanIndex === null
          ? extra.span
          : { index: spanIndex }
  }

  return {
    ...a,
    event_id: eventId,
    origin,
    library_id: libraryId,
    doc_id: docId,
    extra: nextExtra
  }
}

function sanitizeActivityForUI(raw) {
  const a = normalizeActivity(raw)
  if (!a || typeof a !== 'object') return null

  const type = String(a.type || '').trim()

  if (!['document', 'conversation', 'hebbian'].includes(type)) return null

  if (type === 'document') {
    const lib = String(a.library_id || a.extra?.library_id || '').trim()
    const doc = String(a.doc_id || a.extra?.doc_id || '').trim()
    const p = String(a.path || '').trim()
    const tt = String(a.title || '').trim()

    if (lib && !doc) return null

    if (isInternalCommPath(p) || isInternalCommPath(tt)) {
      if (lib && doc) {
        const next = { ...a }
        if (isInternalCommPath(next.path)) delete next.path
        if (isInternalCommPath(next.title)) delete next.title
        return next
      }
      return null
    }

    if (!lib || !doc) {
      if (!p) return null
      if (isInternalCommPath(p)) return null
    }
  }

  if (type === 'conversation') {
    const id = String(a.id || '').trim()
    if (!id) return null
  }

  if (!isActionableActivity(a)) return null

  return a
}

function pickActivityGroups(res) {
  const raw = pickDataValue(res, 'activities', null)
  if (!raw || typeof raw !== 'object') return emptyActivityGroups()
  return {
    today: Array.isArray(raw.today) ? raw.today : [],
    yesterday: Array.isArray(raw.yesterday) ? raw.yesterday : [],
    this_week: Array.isArray(raw.this_week) ? raw.this_week : [],
    older: Array.isArray(raw.older) ? raw.older : []
  }
}

function pickHeatmapObject(res) {
  const raw = pickDataValue(res, 'heatmap', {})
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
}

function mapAndFilterActivities(arr) {
  return safeArray(arr)
    .map(sanitizeActivityForUI)
    .filter(Boolean)
}

async function fetchActivitiesSnapshot() {
  const result = await callTool('nisb_timeline_recent_activities', { days: days.value })
  const info = normalizeToolResponse(result, t('timeline.messages.activitiesLoaded'))

  if (!info.success) return emptyActivityGroups()

  const raw = pickActivityGroups(result)
  return {
    today: mapAndFilterActivities(raw.today),
    yesterday: mapAndFilterActivities(raw.yesterday),
    this_week: mapAndFilterActivities(raw.this_week),
    older: mapAndFilterActivities(raw.older)
  }
}

async function fetchHeatmapSnapshot() {
  const result = await callTool('nisb_timeline_heatmap_data', {
    year: new Date().getFullYear()
  })
  const info = normalizeToolResponse(result, t('timeline.messages.heatmapLoaded'))

  if (!info.success) return {}
  return pickHeatmapObject(result)
}

let __refresh_timer = null
let __refresh_idle_id = null
let __refresh_inflight = false
let __refresh_queued = false
let __refresh_run_seq = 0

function _clear_scheduled_refresh() {
  if (__refresh_timer) {
    clearTimeout(__refresh_timer)
    __refresh_timer = null
  }
  if (__refresh_idle_id !== null) {
    _cancel_idle(__refresh_idle_id)
    __refresh_idle_id = null
  }
}

function scheduleRefreshAll(reason = 'external', { delay = 80, idle = false } = {}) {
  _clear_scheduled_refresh()

  const runner = () => {
    if (__refresh_inflight) {
      __refresh_queued = true
      return
    }
    void refreshAllNow(reason)
  }

  const runWithDelay = () => {
    if (delay > 0) {
      __refresh_timer = setTimeout(() => {
        __refresh_timer = null
        runner()
      }, delay)
    } else {
      runner()
    }
  }

  if (idle) {
    __refresh_idle_id = _request_idle(
      () => {
        __refresh_idle_id = null
        runWithDelay()
      },
      { timeout: 1000 }
    )
    return
  }

  runWithDelay()
}

async function refreshAllNow(reason = 'manual') {
  if (__refresh_inflight) {
    __refresh_queued = true
    return
  }

  const seq = ++__refresh_run_seq
  __refresh_inflight = true
  loading.value = true

  try {
    const [activitiesResult, heatmapResult, runtimeResult] = await Promise.allSettled([
      fetchActivitiesSnapshot(),
      fetchHeatmapSnapshot(),
      Promise.resolve(handleRuntimeRefresh())
    ])

    if (seq !== __refresh_run_seq) return

    if (activitiesResult.status === 'fulfilled') {
      activities.value = activitiesResult.value
    }

    if (heatmapResult.status === 'fulfilled') {
      heatmapData.value = heatmapResult.value
    }

    if (runtimeResult.status === 'rejected') {
      console.error(`[timeline] runtime refresh failed (${reason}):`, runtimeResult.reason)
    }
  } catch (e) {
    console.error(`[timeline] refresh failed (${reason}):`, e)
  } finally {
    if (seq === __refresh_run_seq) {
      loading.value = false
    }
    __refresh_inflight = false

    if (__refresh_queued) {
      __refresh_queued = false
      scheduleRefreshAll('queued-rerun', { delay: 100, idle: true })
    }
  }
}

async function refreshAll() {
  await refreshAllNow('manual')
}

async function compactActivityLog() {
  if (!confirm(tr('timeline.messages.compactConfirm'))) return

  loading.value = true
  try {
    const res = await callTool('nisb_timeline_compact_activity_log', { days: 3650 })
    const info = normalizeToolResponse(res, t('timeline.messages.compactDone'))

    if (info.success) {
      await refreshAllNow('compact-activity-log')
      const kept = Number(pickDataValue(res, 'kept', 0) ?? 0)
      const removed = Number(pickDataValue(res, 'removed', 0) ?? 0)
      const rss = Number(pickDataValue(res, 'rss_import_skipped', 0) ?? 0)
      alert(tr('timeline.messages.compactSuccess', { kept, removed, rss }))
    } else {
      alert(`${t('timeline.messages.compactFailed', { text: '' })}${info.text || t('timeline.messages.unknownError')}`.replace(/: $/, ': '))
    }
  } catch (e) {
    alert(t('timeline.messages.compactFailed', { text: e?.message || e || t('timeline.messages.unknownError') }))
  } finally {
    loading.value = false
  }
}

async function hardDeleteByPattern() {
  const pattern = String(hardDeletePattern.value || '').trim()
  if (!pattern) {
    alert(t('timeline.messages.patternInputRequired'))
    return
  }

  loading.value = true
  try {
    const preview = await callTool('nisb_timeline_hard_delete_by_pattern', {
      pattern,
      days: 3650,
      dry_run: true,
      case_insensitive: true,
      match_fields: ['title', 'path', 'doc_id', 'library_id']
    })
    const previewInfo = normalizeToolResponse(preview, t('timeline.messages.previewDone'))

    if (!previewInfo.success) {
      alert(t('timeline.messages.previewFailed', { text: previewInfo.text || t('timeline.messages.unknownError') }))
      return
    }

    const matched = Number(pickDataValue(preview, 'matched', 0) ?? 0)
    if (matched <= 0) {
      alert(t('timeline.messages.noMatchedRecords'))
      return
    }

    const sampleLines = pickDataArray(preview, 'samples', [])
      .slice(0, 8)
      .map((x) => {
        const tt = String(x?.title || '').trim()
        const p = String(x?.path || '').trim()
        const d = String(x?.doc_id || '').trim()
        return `- ${tt || d || p || x?.event_id || t('timeline.messages.untitledSample')}`
      })
      .join('\n')

    const ok = confirm(
      tr('timeline.messages.patternDeleteConfirm', {
        matched,
        pattern,
        samples: sampleLines || t('timeline.messages.noSamples')
      })
    )
    if (!ok) return

    const run = await callTool('nisb_timeline_hard_delete_by_pattern', {
      pattern,
      days: 3650,
      dry_run: false,
      case_insensitive: true,
      match_fields: ['title', 'path', 'doc_id', 'library_id']
    })
    const runInfo = normalizeToolResponse(run, t('timeline.messages.patternDeleteDone'))

    if (runInfo.success) {
      await refreshAllNow('hard-delete-by-pattern')
      const removed = pickDataValue(run, 'removed', matched)
      const remaining = pickDataValue(run, 'remaining', t('timeline.messages.unknown'))
      alert(tr('timeline.messages.patternDeleteSuccess', { removed, remaining }))
    } else {
      alert(t('timeline.messages.patternDeleteFailed', { text: runInfo.text || t('timeline.messages.unknownError') }))
    }
  } catch (e) {
    alert(t('timeline.messages.patternDeleteFailed', { text: e?.message || e || t('timeline.messages.unknownError') }))
  } finally {
    loading.value = false
  }
}

function enterSelectMode() {
  selectMode.value = true
  selectedEventIds.value = new Set()
}

function exitSelectMode() {
  selectMode.value = false
  selectedEventIds.value = new Set()
}

function toggleSelect(activity) {
  if (!activity) return
  if (!isDeletable(activity)) return
  const eid = String(activity.event_id || '').trim()
  if (!eid) return

  const next = new Set(selectedEventIds.value)
  if (next.has(eid)) next.delete(eid)
  else next.add(eid)
  selectedEventIds.value = next
}

async function deleteOne(activity) {
  if (!activity || !isDeletable(activity)) return
  const title = displayTitle(activity)
  const isHardDelete = activity.origin === 'activity_log'
  const tipText = isHardDelete
    ? t('timeline.messages.deleteOneHardTip')
    : t('timeline.messages.deleteOneSoftTip')

  if (!confirm(tr('timeline.messages.deleteOneConfirm', { title, tip: tipText }))) return

  loading.value = true
  try {
    const res = await callTool('nisb_timeline_delete_items', { items: [activity] })
    const info = normalizeToolResponse(res, t('timeline.messages.deleteOneDone'))

    if (info.success) {
      await refreshAllNow('delete-one')
      const eid = String(activity.event_id || '').trim()
      if (eid) {
        const next = new Set(selectedEventIds.value)
        next.delete(eid)
        selectedEventIds.value = next
      }
    } else {
      alert(t('timeline.messages.deleteOneFailed', { text: info.text || t('timeline.messages.unknownError') }))
    }
  } catch (e) {
    alert(t('timeline.messages.deleteOneFailed', { text: e?.message || e || t('timeline.messages.unknownError') }))
  } finally {
    loading.value = false
  }
}

async function deleteSelected() {
  const ids = selectedEventIds.value
  if (!ids || ids.size === 0) return

  const deletableItems = allActivitiesFlat.value.filter(
    (a) => isDeletable(a) && ids.has(String(a.event_id || '').trim())
  )
  if (!deletableItems.length) return

  if (
    !confirm(
      tr('timeline.messages.deleteSelectedConfirm', {
        count: deletableItems.length
      })
    )
  ) return

  loading.value = true
  try {
    const res = await callTool('nisb_timeline_delete_items', { items: deletableItems })
    const info = normalizeToolResponse(res, t('timeline.messages.deleteSelectedDone'))

    if (info.success) {
      await refreshAllNow('delete-selected')
      exitSelectMode()
    } else {
      alert(t('timeline.messages.deleteSelectedFailed', { text: info.text || t('timeline.messages.unknownError') }))
    }
  } catch (e) {
    alert(t('timeline.messages.deleteSelectedFailed', { text: e?.message || e || t('timeline.messages.unknownError') }))
  } finally {
    loading.value = false
  }
}

async function pruneMissing() {
  if (!confirm(tr('timeline.messages.pruneConfirm'))) return

  loading.value = true
  try {
    const res = await callTool('nisb_timeline_prune_missing_documents', { days: 3650 })
    const info = normalizeToolResponse(res, t('timeline.messages.pruneDone'))

    if (info.success) {
      await refreshAllNow('prune-missing')
      const removed = pickDataValue(res, 'removed', 0)
      alert(t('timeline.messages.pruneSuccess', { removed: removed || 0 }))
    } else {
      alert(t('timeline.messages.pruneFailed', { text: info.text || t('timeline.messages.unknownError') }))
    }
  } catch (e) {
    alert(t('timeline.messages.pruneFailed', { text: e?.message || e || t('timeline.messages.unknownError') }))
  } finally {
    loading.value = false
  }
}

let __open_dispatch_timer = null
let __open_dispatch_seq = 0

function _clear_pending_open_dispatch() {
  if (__open_dispatch_timer) {
    clearTimeout(__open_dispatch_timer)
    __open_dispatch_timer = null
  }
}

function scheduleWindowEvent(name, detail, { delay = 16 } = {}) {
  const seq = ++__open_dispatch_seq
  _clear_pending_open_dispatch()

  __open_dispatch_timer = setTimeout(() => {
    __open_dispatch_timer = null
    if (seq !== __open_dispatch_seq) return
    window.dispatchEvent(new CustomEvent(name, { detail }))
  }, delay)
}

function handleActivityClick(key, activity) {
  if (selectMode.value) {
    toggleSelect(activity)
    return
  }

  if (!isActionableActivity(activity)) return

  activeKey.value = key

  if (activity.type === 'conversation') {
    scheduleWindowEvent('nisb-open-conversation', {
      convId: activity.id,
      title: activity.title
    })
    return
  }

  if (activity.type === 'document') {
    const libraryId = activity.library_id || activity.extra?.library_id
    const docId = activity.doc_id || activity.extra?.doc_id

    if (libraryId && docId) {
      const reader = activity.extra?.reader || null
      const spanIndex = Number.isFinite(activity.extra?.span?.index)
        ? activity.extra.span.index
        : null

      scheduleWindowEvent('nisb-open-library-doc', {
        libraryId,
        docId,
        reader,
        spanIndex
      })
      return
    }

    const p = String(activity.path || '').trim()
    if (!p || isInternalCommPath(p)) return

    scheduleWindowEvent('nisb-open-file', {
      path: p,
      name: displayTitle(activity)
    })
  }
}

function toggleSection(section) {
  expandedSections.value = {
    ...expandedSections.value,
    [section]: !expandedSections.value[section]
  }
}

function handleTimelineRefresh() {
  scheduleRefreshAll('external-event', { delay: 120, idle: true })
}

const heatmapHost = ref(null)
const heatmapRenderKey = ref(0)
let ro = null
let lastWidth = 0
let __heatmap_resize_timer = null

function queueHeatmapRerender() {
  if (__heatmap_resize_timer) clearTimeout(__heatmap_resize_timer)
  __heatmap_resize_timer = setTimeout(() => {
    __heatmap_resize_timer = null
    heatmapRenderKey.value += 1
  }, 80)
}

function setupHeatmapResizeObserver() {
  if (!heatmapHost.value) return
  if (typeof ResizeObserver === 'undefined') return

  ro = new ResizeObserver((entries) => {
    const entry = entries?.[0]
    const w = Math.round(entry?.contentRect?.width || 0)
    if (!w) return
    if (Math.abs(w - lastWidth) >= 8) {
      lastWidth = w
      queueHeatmapRerender()
    }
  })

  ro.observe(heatmapHost.value)
}

const {
  show_room_runtime_section,
  room_runtime_room_id,
  room_runtime_live,
  room_runtime_error,
  room_runtime_status_text,
  room_runtime_headline,
  room_runtime_badge_summary,
  room_runtime_has_terminal_result,
  room_runtime_latest_stage,
  room_runtime_summary_text,
  room_runtime_result_entry,
  room_runtime_recent_entries,
  room_runtime_view_mode,
  room_runtime_selected_run_id,
  room_runtime_run_options,
  room_runtime_loading,
  room_runtime_skill_summary,
  room_runtime_runtime_state,
  room_runtime_runtime_phase,
  room_runtime_can_accept_new_prompt,
  room_runtime_control_block_reason,
  room_runtime_continuation_mode,
  room_runtime_continuation_status,
  room_runtime_pause_requested,
  room_runtime_pause_request_accepted,
  room_runtime_pause_reason,
  room_runtime_pause_requested_at,
  room_runtime_pause_effective,
  room_runtime_paused_at,
  room_runtime_pause_effective_at,
  room_runtime_interruption_reason,
  room_runtime_resume_ready,
  room_runtime_resume_from_checkpoint,
  room_runtime_can_resume_from_checkpoint,
  room_runtime_resume_checkpoint_ref,
  room_runtime_resume_token,
  room_runtime_resume_reason,
  room_runtime_error_blocking_resume,
  room_runtime_resumed_from_run_id,
  room_runtime_resumed_from_event_id,
  room_runtime_resumed_from_stage,
  room_runtime_checkpoint_stage,
  room_runtime_checkpoint_summary,
  room_runtime_last_completed_step,
  room_runtime_skipped_effects,
  room_runtime_effect_dispositions,
  room_runtime_step_budget_total,
  room_runtime_step_budget_used,
  room_runtime_step_budget_remaining,
  room_runtime_budget_status,
  room_runtime_budget_exhausted,
  room_runtime_can_pause_current,
  room_runtime_can_resume,
  room_runtime_show_pause_action,
  room_runtime_pause_disabled,
  room_runtime_pause_text,
  room_runtime_show_resume_action,
  room_runtime_resume_disabled,
  room_runtime_resume_text,
  room_runtime_control_hint,
  handleRuntimeRefresh,
  handleRuntimeSwitchMode,
  handleRuntimeSelectRun,
  handleRuntimePauseCurrent,
  handleRuntimeResumeFromCheckpoint
} = use_timeline_room_runtime({
  roomStore,
  callTool
})

const toolbarRowRef = ref(null)
const {
  onRowEnter: on_toolbar_enter,
  onRowLeave: on_toolbar_leave,
  onScroll: on_toolbar_scroll,
  onMouseMove: on_toolbar_mouse_move
} = useHoverScroll(toolbarRowRef, { activeHeight: 10 })

onMounted(() => {
  scheduleRefreshAll('mounted', { delay: 0, idle: true })
  window.addEventListener('nisb-timeline-refresh', handleTimelineRefresh)
  setupHeatmapResizeObserver()
})

onUnmounted(() => {
  window.removeEventListener('nisb-timeline-refresh', handleTimelineRefresh)

  _clear_scheduled_refresh()
  _clear_pending_open_dispatch()

  if (__heatmap_resize_timer) {
    clearTimeout(__heatmap_resize_timer)
    __heatmap_resize_timer = null
  }

  if (ro) {
    ro.disconnect()
    ro = null
  }
})

watch(days, () => {
  if (days.value > 30) {
    days.value = 30
    return
  }
  scheduleRefreshAll('days-changed', { delay: 80, idle: true })
})

const ActivityItem = defineComponent({
  name: 'ActivityItem',
  props: {
    activity: { type: Object, required: true },
    rowKey: { type: String, required: true },
    active: { type: Boolean, default: false },
    selected: { type: Boolean, default: false },
    selectMode: { type: Boolean, default: false },
    deletable: { type: Boolean, default: false },
    titleText: { type: String, required: true },
    timeText: { type: String, default: '' }
  },
  emits: ['row-click', 'show-tip', 'move-tip', 'hide-tip', 'toggle-select', 'delete-one'],
  setup(props, { emit }) {
    const getIcon = () => {
      switch (props.activity.type) {
        case 'conversation':
          return '💬'
        case 'document':
          return '📄'
        case 'hebbian':
          return '🧠'
        default:
          return '•'
      }
    }

    const onRowClick = () => {
      emit('row-click', props.rowKey, props.activity)
    }

    const onToggleSelectClick = (e) => {
      e.stopPropagation()
      emit('toggle-select', props.activity)
    }

    const onDeleteClick = (e) => {
      e.stopPropagation()
      emit('delete-one', props.activity)
    }

    return () =>
      h(
        'div',
        {
          class: [
            'activity-item',
            props.active && 'active',
            props.selectMode && 'select-mode',
            props.selected && 'selected'
          ],
          onClick: onRowClick,
          onMouseenter: (e) => emit('show-tip', props.activity, e),
          onMousemove: (e) => emit('move-tip', e),
          onMouseleave: () => emit('hide-tip')
        },
        [
          props.selectMode
            ? h('span', {
                class: [
                  'select-dot',
                  props.deletable ? 'can-select' : 'disabled',
                  props.selected && 'on'
                ],
                title: props.deletable
                  ? t('timeline.activity.selectToggle')
                  : t('timeline.activity.notRemovable'),
                onClick: props.deletable
                  ? onToggleSelectClick
                  : (e) => e.stopPropagation()
              })
            : null,

          h('div', { class: 'activity-icon' }, getIcon()),

          h('div', { class: 'activity-content' }, [
            h('div', { class: 'activity-title' }, props.titleText),
            h('div', { class: 'activity-time' }, props.timeText)
          ]),

          props.deletable
            ? h(
                'button',
                {
                  class: 'item-del-btn',
                  title: t('timeline.activity.removeOneTitle'),
                  onClick: onDeleteClick
                },
                '✕'
              )
            : null
        ]
      )
  }
})

const ActivitySection = defineComponent({
  name: 'ActivitySection',
  props: {
    title: { type: String, required: true },
    sectionKey: { type: String, required: true },
    items: { type: Array, required: true },
    expanded: { type: Boolean, default: false },
    maxItems: { type: Number, default: 60 },
    activeKey: { type: String, default: null },
    strongTitle: { type: Boolean, default: false },
    selectMode: { type: Boolean, default: false },
    selectedEventIds: { type: Object, required: true }
  },
  emits: ['toggle-expand', 'item-click', 'show-tip', 'move-tip', 'hide-tip', 'toggle-select', 'delete-one'],
  setup(props, { emit }) {
    function makeKey(idx, activity) {
      const tt = String(activity?.type || 'x')
      const id = String(activity?.event_id || activity?.id || activity?.path || idx)
      const d = String(activity?.date || '')
      return `${props.sectionKey}-${tt}-${id}-${d}-${idx}`
    }

    function getTime(activity) {
      if (!activity?.date) return ''
      try {
        const date = new Date(activity.date)
        return date.toTimeString().slice(0, 5)
      } catch {
        return ''
      }
    }

    function isDel(activity) {
      return activity && String(activity.event_id || '').trim()
    }

    function isSelected(activity) {
      const eid = String(activity?.event_id || '').trim()
      if (!eid) return false
      return props.selectedEventIds.has(eid)
    }

    return () => {
      const all = Array.isArray(props.items) ? props.items : []
      const visible = props.expanded ? all : all.slice(0, props.maxItems)
      const canExpand = all.length > props.maxItems

      return h('div', { class: 'activity-section' }, [
        h('div', { class: 'section-head' }, [
          h(
            'div',
            { class: ['section-title', props.strongTitle && 'section-title-strong'] },
            props.title
          ),
          canExpand
            ? h(
                'button',
                { class: 'section-more', onClick: () => emit('toggle-expand') },
                props.expanded
                  ? t('timeline.sections.collapse', { count: all.length })
                  : t('timeline.sections.expandMore', { count: all.length })
              )
            : null
        ]),

        ...visible.map((activity, idx) => {
          const rowKey = makeKey(idx, activity)
          const titleText = displayTitle(activity)
          const timeText = getTime(activity)
          const deletable = isDel(activity)

          return h(ActivityItem, {
            key: rowKey,
            rowKey,
            activity,
            active: props.activeKey === rowKey,
            selected: isSelected(activity),
            selectMode: props.selectMode,
            deletable,
            titleText,
            timeText,
            onRowClick: (k, a) => emit('item-click', k, a),
            onShowTip: (act, e) => emit('show-tip', act, e),
            onMoveTip: (e) => emit('move-tip', e),
            onHideTip: () => emit('hide-tip'),
            onToggleSelect: (act) => emit('toggle-select', act),
            onDeleteOne: (act) => emit('delete-one', act)
          })
        })
      ])
    }
  }
})
</script>

<style scoped>
.timeline-container {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 74%, transparent)
    );
}

.heatmap-section {
  flex: 0 0 auto;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 0.55rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  overflow: hidden;
}

.heatmap-section :deep(*) {
  max-width: 100%;
}

.timeline-toolbar {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem;
  padding: 0.48rem 0.55rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  overflow: hidden;
}

.toolbar-left {
  display: none;
}

.toolbar-right {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.36rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0.02rem 0.02rem 0.04rem;
  -webkit-overflow-scrolling: touch;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.toolbar-right::-webkit-scrollbar {
  display: none;
}

.toolbar-right > * {
  flex: 0 0 auto;
}

.toolbar-select,
.toolbar-input {
  min-height: 30px;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 64%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  color: var(--text-secondary);
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 690;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.toolbar-select {
  padding: 0 0.48rem;
  cursor: pointer;
}

.toolbar-input {
  width: 210px;
  padding: 0 0.58rem;
}

.toolbar-select:hover:not(:disabled),
.toolbar-select:focus-visible:not(:disabled),
.toolbar-input:hover:not(:disabled),
.toolbar-input:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 34%, transparent),
      color-mix(in srgb, var(--editor-bg) 64%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.toolbar-select:disabled,
.toolbar-input:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.toolbar-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.toolbar-btn {
  min-height: 30px;
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
  font-size: 0.76rem;
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

.toolbar-btn:hover:not(:disabled),
.toolbar-btn:focus-visible:not(:disabled) {
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

.toolbar-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.toolbar-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.toolbar-btn.danger {
  border-color: rgba(239, 68, 68, 0.34);
  color: color-mix(in srgb, #ef4444 84%, var(--text-secondary));
}

.toolbar-btn.danger:hover:not(:disabled),
.toolbar-btn.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.56);
  background:
    linear-gradient(
      135deg,
      rgba(239, 68, 68, 0.13),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 8px 18px rgba(239, 68, 68, 0.08);
}

.activity-list {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.55rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.activity-list::-webkit-scrollbar {
  width: 8px;
}

.activity-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.activity-section {
  min-width: 0;
  margin-bottom: 0.05rem;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
}

:deep(.section-head) {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  padding: 0 0.08rem 0.42rem;
  margin-bottom: 0.18rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 56%, transparent);
}

:deep(.section-title) {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 780;
  line-height: 1.25;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.section-title-strong) {
  color: var(--text-main, var(--text));
  font-weight: 850;
}

:deep(.section-more) {
  flex: 0 0 auto;
  min-height: 25px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 730;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

:deep(.section-more:hover),
:deep(.section-more:focus-visible) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

:deep(.activity-item) {
  position: relative;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.5rem 0.52rem;
  border: 1px solid transparent;
  border-radius: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.25;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

:deep(.activity-item + .activity-item) {
  margin-top: 0.28rem;
}

:deep(.activity-item::before) {
  content: "";
  position: absolute;
  left: 0.3rem;
  top: 0.56rem;
  bottom: 0.56rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 82%, transparent);
  opacity: 0;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

:deep(.activity-item:hover),
:deep(.activity-item:focus-within) {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 36%, transparent)
    );
  color: var(--selected);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06);
}

:deep(.activity-item.active) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 10px 22px rgba(0, 0, 0, 0.08);
}

:deep(.activity-item.selected) {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 60%, transparent),
      color-mix(in srgb, var(--editor-bg) 38%, transparent)
    );
}

:deep(.activity-item:hover::before),
:deep(.activity-item.active::before),
:deep(.activity-item.selected::before) {
  opacity: 1;
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

:deep(.activity-item.select-mode) {
  padding-left: 0.52rem;
}

:deep(.select-dot) {
  flex: 0 0 auto;
  width: 15px;
  height: 15px;
  box-sizing: border-box;
  margin-top: 0.38rem;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

:deep(.select-dot.can-select) {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
}

:deep(.select-dot.can-select:hover) {
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

:deep(.select-dot.can-select.on) {
  border-color: var(--selected);
  background: var(--selected);
  box-shadow:
    inset 0 0 0 3px color-mix(in srgb, var(--editor-bg) 92%, transparent),
    0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

:deep(.select-dot.disabled) {
  opacity: 0.34;
  cursor: not-allowed;
}

:deep(.activity-icon) {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  margin-left: 0.14rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--sidebar-bg) 72%, transparent);
  font-size: 0.9rem;
  line-height: 1;
}

:deep(.activity-item:hover .activity-icon),
:deep(.activity-item.active .activity-icon),
:deep(.activity-item.selected .activity-icon) {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
}

:deep(.activity-content) {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.2rem;
}

:deep(.activity-title) {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.8rem;
  font-weight: 750;
  line-height: 1.32;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.activity-time) {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.69rem;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.activity-item:hover .activity-title) {
  color: var(--selected);
  font-weight: 790;
}

:deep(.activity-item.active .activity-title),
:deep(.activity-item.selected .activity-title) {
  color: var(--selected);
  font-weight: 840;
  letter-spacing: -0.01em;
}

:deep(.activity-item:hover .activity-time),
:deep(.activity-item.active .activity-time),
:deep(.activity-item.selected .activity-time) {
  color: color-mix(in srgb, var(--selected) 72%, var(--text-secondary));
  font-weight: 710;
}

:deep(.item-del-btn) {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  min-width: 24px;
  box-sizing: border-box;
  margin-top: 0.16rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 800;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  opacity: 0;
  pointer-events: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

:deep(.activity-item:hover .item-del-btn),
:deep(.activity-item:focus-within .item-del-btn),
:deep(.activity-item.selected .item-del-btn) {
  opacity: 1;
  pointer-events: auto;
}

:deep(.item-del-btn:hover),
:deep(.item-del-btn:focus-visible) {
  border-color: rgba(239, 68, 68, 0.56);
  background: rgba(239, 68, 68, 0.11);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 6px 14px rgba(239, 68, 68, 0.08);
  outline: none;
}

:deep(.item-del-btn:active) {
  transform: translateY(1px);
}

.empty-tip {
  padding: 0.9rem 0.76rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.path-tooltip {
  position: fixed;
  z-index: 20000;
  max-width: min(560px, calc(100vw - 24px));
  padding: 0.5rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 96%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.42;
  pointer-events: none;
  box-shadow:
    0 16px 34px rgba(0, 0, 0, 0.18),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  white-space: normal;
  overflow-wrap: anywhere;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

@media (max-width: 520px) {
  .heatmap-section {
    padding: 0.45rem;
  }

  .timeline-toolbar {
    padding: 0.44rem;
  }

  .toolbar-input {
    width: 180px;
  }

  .activity-list {
    padding: 0.45rem;
  }

  .activity-section {
    padding: 0.44rem;
  }

  :deep(.section-head) {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.34rem;
  }

  :deep(.section-more) {
    width: 100%;
  }

  :deep(.activity-item) {
    padding: 0.52rem;
  }

  :deep(.activity-content) {
    gap: 0.18rem;
  }

  :deep(.item-del-btn) {
    opacity: 1;
    pointer-events: auto;
  }
}
</style>
