<template>
  <div class="room-runtime-stack" :class="{ collapsed: !expanded }">
    <div class="room-runtime-toolbar">
      <button
        type="button"
        class="room-runtime-toggle"
        @click="$emit('toggle')"
      >
        <span class="room-runtime-toggle-icon">
          {{ expanded ? '▾' : '▸' }}
        </span>
        <span class="room-runtime-toggle-text">运行结果</span>
      </button>

      <div class="room-runtime-toolbar-right">
        <span class="room-runtime-state-chip" :class="{ live: live && normalized_view_mode === 'current', error: !!error }">
          {{ display_status_text }}
        </span>

        <span class="room-runtime-state-chip" :class="{ replay: normalized_view_mode === 'replay' }">
          {{ normalized_view_mode === 'replay' ? '回放' : '当前' }}
        </span>

        <span v-if="display_run_id" class="room-runtime-state-chip mono">
          {{ display_run_id }}
        </span>

        <button
          type="button"
          class="room-runtime-refresh-btn"
          :disabled="loading"
          @click="$emit('refresh')"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="expanded" class="room-runtime-panel room-runtime-result-panel">
      <div class="room-runtime-panel-head">
        <div class="room-runtime-viewbar">
          <div class="room-runtime-view-switch">
            <button
              type="button"
              class="room-runtime-view-btn"
              :class="{ active: normalized_view_mode === 'current' }"
              @click="$emit('switch-mode', 'current')"
            >
              当前
            </button>

            <button
              type="button"
              class="room-runtime-view-btn"
              :class="{ active: normalized_view_mode === 'replay' }"
              :disabled="!can_select_replay"
              @click="$emit('switch-mode', 'replay')"
            >
              回放
            </button>
          </div>

          <div class="room-runtime-run-picker">
            <select
              class="room-runtime-run-select"
              :disabled="!display_run_options.length"
              :value="selected_run_value"
              @change="handle_run_change"
            >
              <option value="">
                {{ display_run_options.length ? '选择 run 回放' : '暂无可回放 run' }}
              </option>
              <option
                v-for="option in display_run_options"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>
        </div>

        <div class="room-runtime-panel-title">运行结果</div>
        <div class="room-runtime-panel-subtitle">
          {{ result_panel_subtitle }}
        </div>

        <div v-if="runtime_headline" class="room-runtime-panel-meta">
          {{ runtime_headline }}
        </div>

        <div v-if="runtime_badge_summary" class="room-runtime-panel-meta">
          {{ runtime_badge_summary }}
        </div>

        <div
          v-if="p6_probe_badge_text"
          class="room-runtime-test-probe-banner"
          :class="p6_probe_badge_class"
        >
          <div class="room-runtime-test-probe-title">
            P6 测试控制面
          </div>
          <div class="room-runtime-test-probe-text">
            {{ p6_probe_badge_text }}
          </div>
        </div>
      </div>

      <div v-if="error" class="room-runtime-empty error">
        {{ error }}
      </div>

      <template v-else-if="result_entry">
        <div class="room-runtime-result-meta">
          <span class="room-runtime-result-type">
            {{ result_entry.badge }}
          </span>

          <span v-if="result_entry.actor" class="room-runtime-result-actor">
            {{ result_entry.actor }}
          </span>

          <span class="room-runtime-result-time">
            {{ result_entry.timeText }}
          </span>
        </div>

        <div v-if="result_entry.metaChips.length" class="room-runtime-chip-row result">
          <span
            v-for="(chip, chip_idx) in result_entry.metaChips"
            :key="`result-chip-${chip_idx}`"
            class="room-runtime-chip"
          >
            {{ chip }}
          </span>
        </div>

        <div
          v-if="result_text_display"
          class="room-runtime-result-markdown message-markdown"
          v-html="render_markdown(result_text_display)"
        ></div>

        <div v-else class="room-runtime-empty">
          暂无最终结果正文
        </div>

        <div
          v-if="runtime_audit_cards.length"
          class="room-runtime-audit-panel"
        >
          <div class="room-runtime-audit-title">
            运行审计摘要
          </div>

          <div class="room-runtime-audit-grid">
            <div
              v-for="card in runtime_audit_cards"
              :key="card.key"
              class="room-runtime-audit-card"
            >
              <div class="room-runtime-audit-card-head">
                <div class="room-runtime-audit-card-title">
                  {{ card.title }}
                </div>

                <span class="tool-status" :class="card.statusClass">
                  {{ card.statusText }}
                </span>
              </div>

              <div v-if="card.message" class="room-runtime-audit-card-message">
                {{ card.message }}
              </div>

              <div v-if="card.path" class="room-runtime-audit-card-path mono">
                {{ card.path }}
              </div>

              <div v-if="card.metaChips.length" class="room-runtime-chip-row audit">
                <span
                  v-for="(chip, chip_idx) in card.metaChips"
                  :key="`${card.key}-chip-${chip_idx}`"
                  class="room-runtime-chip"
                >
                  {{ chip }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="show_skill_panel"
          class="room-runtime-skill-panel"
        >
          <div class="room-runtime-skill-title">
            Supervisor Skills
          </div>

          <div
            v-if="runtime_skill_summary.has_skills"
            class="room-runtime-skill-summary-card"
          >
            <div class="room-runtime-skill-summary-head">
              <div class="room-runtime-skill-summary-name">
                Skills 摘要
              </div>

              <span class="tool-status" :class="runtime_skill_summary.statusClass">
                {{ runtime_skill_summary.status_text }}
              </span>
            </div>

            <div
              v-if="runtime_skill_summary.summary_text"
              class="room-runtime-skill-card-message"
            >
              {{ runtime_skill_summary.summary_text }}
            </div>

            <div v-if="skill_summary_chips.length" class="room-runtime-chip-row audit">
              <span
                v-for="(chip, chip_idx) in skill_summary_chips"
                :key="`skill-summary-chip-${chip_idx}`"
                class="room-runtime-chip"
              >
                {{ chip }}
              </span>
            </div>
          </div>

          <div
            v-if="runtime_skill_cards.length"
            class="room-runtime-skill-grid"
          >
            <div
              v-for="card in runtime_skill_cards"
              :key="card.key"
              class="room-runtime-skill-card"
            >
              <div class="room-runtime-skill-card-head">
                <div class="room-runtime-skill-card-title">
                  {{ card.name }}
                </div>

                <span class="tool-status" :class="get_skill_status_class(card)">
                  {{ card.status_text }}
                </span>
              </div>

              <div v-if="card.summary" class="room-runtime-skill-card-message">
                {{ card.summary }}
              </div>

              <div v-if="card.path" class="room-runtime-audit-card-path mono">
                {{ card.path }}
              </div>

              <div v-if="build_skill_card_chips(card).length" class="room-runtime-chip-row audit">
                <span
                  v-for="(chip, chip_idx) in build_skill_card_chips(card)"
                  :key="`${card.key}-skill-chip-${chip_idx}`"
                  class="room-runtime-chip"
                >
                  {{ chip }}
                </span>
              </div>
            </div>
          </div>

          <div
            v-if="runtime_skill_activity_rows.length"
            class="room-runtime-skill-activity"
          >
            <div class="room-runtime-skill-subtitle">
              Skill 活动记录
            </div>

            <div
              v-for="row in runtime_skill_activity_rows"
              :key="row.key"
              class="tool-call-card"
            >
              <div class="tool-call-head">
                <span class="tool-badge skill">skill</span>
                <span class="tool-name">
                  {{ row.name }}
                </span>
                <span class="tool-status" :class="get_skill_status_class(row)">
                  {{ row.status_text }}
                </span>
              </div>

              <div v-if="build_skill_card_chips(row).length" class="room-runtime-chip-row audit">
                <span
                  v-for="(chip, chip_idx) in build_skill_card_chips(row)"
                  :key="`${row.key}-activity-chip-${chip_idx}`"
                  class="room-runtime-chip"
                >
                  {{ chip }}
                </span>
              </div>

              <pre v-if="row.preview" class="tool-json">{{ row.preview }}</pre>
            </div>
          </div>
        </div>

        <div v-if="show_tool_activity" class="tool-activity-panel room-runtime-tool-panel">
          <div class="tool-activity-title">
            工具执行记录
          </div>

          <div
            v-for="tool_call in tool_call_rows"
            :key="tool_call.key"
            class="tool-call-card"
          >
            <div class="tool-call-head">
              <span class="tool-badge">tool_call</span>
              <span class="tool-name">
                {{ tool_call.name }}
              </span>
              <span class="tool-status" :class="tool_call.statusClass">
                {{ tool_call.statusText }}
              </span>
            </div>

            <pre v-if="tool_call.preview" class="tool-json">{{ tool_call.preview }}</pre>
          </div>

          <div
            v-for="tool_result in tool_result_rows"
            :key="tool_result.key"
            class="tool-result-card"
          >
            <div class="tool-call-head">
              <span class="tool-badge success">tool_result</span>
              <span class="tool-name">
                {{ tool_result.name }}
              </span>
              <span class="tool-status" :class="tool_result.statusClass">
                {{ tool_result.statusText }}
              </span>
            </div>

            <pre v-if="tool_result.preview" class="tool-json">{{ tool_result.preview }}</pre>
          </div>
        </div>

        <CitationList
          v-if="result_citations.length"
          :citations="result_citations"
        />
      </template>

      <div v-else class="room-runtime-empty">
        {{ normalized_view_mode === 'replay' ? '暂无回放结果' : '暂无结果事件' }}
      </div>

      <div
        v-if="timeline_entries.length"
        class="room-runtime-panel room-runtime-process-panel"
      >
        <div class="room-runtime-panel-head nested">
          <div class="room-runtime-panel-title">过程轨迹</div>
          <div class="room-runtime-panel-subtitle">
            {{ normalized_view_mode === 'replay' ? '展示该 run 的回放过程' : '展示当前 run 的过程事件' }}
          </div>
        </div>

        <div class="room-runtime-timeline">
          <div
            v-for="entry in timeline_entries"
            :key="entry.key"
            class="room-runtime-timeline-item"
            :class="entry.kindClass"
          >
            <div class="room-runtime-timeline-bullet"></div>

            <div class="room-runtime-timeline-body">
              <div class="room-runtime-timeline-head">
                <span class="room-runtime-timeline-badge">
                  {{ entry.badge }}
                </span>

                <span v-if="entry.actor" class="room-runtime-timeline-actor">
                  {{ entry.actor }}
                </span>

                <span class="room-runtime-timeline-time">
                  {{ entry.timeText }}
                </span>
              </div>

              <div v-if="entry.summary" class="room-runtime-timeline-summary">
                {{ entry.summary }}
              </div>

              <div v-if="entry.metaChips.length" class="room-runtime-chip-row">
                <span
                  v-for="(chip, chip_idx) in entry.metaChips"
                  :key="`${entry.key}-chip-${chip_idx}`"
                  class="room-runtime-chip"
                >
                  {{ chip }}
                </span>
              </div>

              <pre v-if="entry.preview" class="room-runtime-timeline-preview">{{ entry.preview }}</pre>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else-if="!error && !loading"
        class="room-runtime-panel room-runtime-process-panel"
      >
        <div class="room-runtime-panel-head nested">
          <div class="room-runtime-panel-title">过程轨迹</div>
          <div class="room-runtime-panel-subtitle">
            暂无过程事件
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CitationList from '../Chat/CitationList.vue'
import {
  normalize_room_runtime_display_bundle,
  normalize_runtime_view_mode,
} from '../../../stores/room/room_normalizers'

const props = defineProps({
  expanded: { type: Boolean, default: true },
  loading: { type: Boolean, default: false },
  live: { type: Boolean, default: false },
  error: { type: String, default: '' },
  status_text: { type: String, default: '' },
  run_id: { type: String, default: '' },
  process_items: { type: Array, default: () => [] },
  result_event: { type: Object, default: null },
  result_payload: { type: Object, default: () => ({}) },
  result_text: { type: String, default: '' },
  view_mode: { type: String, default: 'current' },
  run_options: { type: Array, default: () => [] },
  selected_run_id: { type: String, default: '' },
  runtime_supervisor_skills: { type: Object, default: () => ({}) },
  runtime_supervisor_skills_summary: { type: Object, default: () => ({}) },
})

const emit = defineEmits([
  'toggle',
  'refresh',
  'switch-mode',
  'select-run',
])

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function safeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function safeString(value) {
  return value === null || value === undefined ? '' : String(value)
}

function safeNumber(value, fallback = 0) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

function escapeHtml(value) {
  return safeString(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function render_markdown(value) {
  const text = safeString(value)
  if (!text.trim()) return ''

  const escaped = escapeHtml(text)
  return escaped
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}

function normalizeCount(value) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function shortenText(value, max = 220) {
  const text = safeString(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= max) return text
  return `${text.slice(0, max - 1)}…`
}

function normalizeFormalSkillStrategy(value) {
  const token = safeString(value).trim().toLowerCase()
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
  if (token === 'builtin_plus_custom') return 'builtin + custom'
  if (token === 'custom_only') return 'custom only'
  if (token === 'builtin_only') return 'builtin only'
  return safeString(value).trim()
}

function normalizeProbeActor(value, fallback = 'off') {
  const s = safeString(value).trim().toLowerCase()
  if (s === 'supervisor') return 'supervisor'
  if (s === 'worker') return 'worker'
  if (s === 'skill') return 'skill'
  if (s === 'off') return 'off'
  return fallback
}

function normalizeSkillStatusText(status, fallback = '') {
  const token = safeString(status || fallback).trim().toLowerCase()
  if (!token) return 'idle'
  if (token === 'success') return 'success'
  if (token === 'applied') return 'applied'
  if (token === 'applied_prompt') return 'applied_prompt'
  if (token === 'enabled') return 'enabled'
  if (token === 'available_not_enabled') return 'available_not_enabled'
  if (token === 'missing') return 'missing'
  if (token === 'skipped') return 'skipped'
  if (token === 'warning') return 'warning'
  if (token === 'error' || token === 'failed') return 'error'
  return token
}

function buildSkillSummaryChips(summary = {}) {
  const src = safeObject(summary)
  const chips = []

  if (safeString(src.strategy).trim()) chips.push(`strategy: ${safeString(src.strategy).trim()}`)
  if (safeNumber(src.enabled_count, 0) > 0) chips.push(`enabled: ${safeNumber(src.enabled_count, 0)}`)
  if (safeNumber(src.applied_count, 0) > 0) chips.push(`applied: ${safeNumber(src.applied_count, 0)}`)
  if (safeNumber(src.resolved_items_count, 0) > 0) chips.push(`resolved: ${safeNumber(src.resolved_items_count, 0)}`)
  if (safeNumber(src.step_count, 0) > 0) chips.push(`steps: ${safeNumber(src.step_count, 0)}`)
  if (src.has_applied_prompt) chips.push('applied_prompt')
  if (src.has_available_not_enabled) chips.push('available_not_enabled')
  if (src.has_missing) chips.push('missing')
  if (src.has_skipped) chips.push('skipped')
  if (safeString(src.source_type).trim()) chips.push(`source: ${safeString(src.source_type).trim()}`)
  if (safeString(src.source_event_type).trim()) chips.push(`event: ${safeString(src.source_event_type).trim()}`)

  return chips
}

function buildSkillCardChips(card = {}) {
  const src = safeObject(card)
  const chips = []

  if (safeString(src.kind).trim()) chips.push(safeString(src.kind).trim())
  if (safeString(src.source).trim()) chips.push(`source: ${safeString(src.source).trim()}`)
  if (safeString(src.strategy_effect).trim()) chips.push(`effect: ${safeString(src.strategy_effect).trim()}`)
  if (src.enabled) chips.push('enabled')
  if (src.applied) chips.push('applied')
  if (src.available_not_enabled) chips.push('available_not_enabled')
  if (src.missing) chips.push('missing')
  if (src.skipped) chips.push('skipped')

  return chips
}

function getSkillStatusClass(value = {}) {
  const src = safeObject(value)
  if (src.applied === true) return 'applied'
  if (src.enabled === true) return 'enabled'
  if (src.available_not_enabled === true) return 'warning'
  if (src.missing === true) return 'error'
  if (src.skipped === true) return 'idle'

  const status = safeString(src.status).trim().toLowerCase()
  if (status === 'success' || status === 'applied' || status === 'applied_prompt') return 'applied'
  if (status === 'enabled') return 'enabled'
  if (status === 'available_not_enabled' || status === 'warning') return 'warning'
  if (status === 'missing' || status === 'error' || status === 'failed') return 'error'
  if (status === 'skipped' || status === 'idle') return 'idle'
  return 'idle'
}

function stringifyPreview(value) {
  const src = value && typeof value === 'object' ? value : null
  if (!src) return ''
  try {
    return JSON.stringify(src, null, 2)
  } catch {
    return ''
  }
}

function normalizeSkillStepRow(row, index = 0) {
  const src = safeObject(row)
  const status = normalizeSkillStatusText(
    src.status ||
    src.step_status ||
    src.stepStatus ||
    src.result ||
    src.state
  )

  return {
    key: safeString(src.key || src.skill_id || src.skillId || src.id || index).trim() || `skill-step-${index + 1}`,
    name: safeString(
      src.label ||
      src.title ||
      src.name ||
      src.skill_name ||
      src.skillName ||
      src.skill_id ||
      src.skillId ||
      src.id ||
      `skill ${index + 1}`
    ).trim(),
    summary: shortenText(
      src.message ||
      src.reason ||
      src.note ||
      src.detail ||
      ''
    ),
    path: safeString(src.path || src.relative_path || src.relativePath).trim(),
    kind: safeString(src.kind || src.skill_kind || src.skillKind).trim(),
    source: safeString(src.source).trim(),
    strategy_effect: safeString(src.strategy_effect || src.strategyEffect).trim(),
    status,
    status_text: status,
    enabled: status === 'enabled',
    applied: status === 'applied' || status === 'applied_prompt' || status === 'success',
    available_not_enabled: status === 'available_not_enabled',
    missing: status === 'missing',
    skipped: status === 'skipped',
    raw: src,
  }
}

function normalizeDirectSkillSummary(bundle = {}, summary = {}) {
  const src = safeObject(bundle)
  const sum = safeObject(summary)

  const strategy = formatSkillStrategyLabel(
    sum.strategy ||
    src.strategy ||
    src.supervisor_skill_strategy
  )

  const status = normalizeSkillStatusText(
    sum.status ||
    src.status,
    'idle'
  )

  const enabled_count = safeNumber(
    sum.enabled_count ?? src.enabled_count,
    0
  )

  const applied_count = safeNumber(
    sum.applied_count ?? src.applied_count,
    0
  )

  const resolved_items_count = safeNumber(
    sum.resolved_items_count ?? src.resolved_items_count,
    0
  )

  const step_count = safeNumber(
    sum.step_count ?? src.step_count,
    safeArray(src.step_rows).length
  )

  const summary_text = safeString(
    sum.summary_text ||
    src.summary_text ||
    src.message ||
    ''
  ).trim()

  const has_skills = !!(
    sum.has_skills ||
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
    status,
    status_text: status,
    statusClass: getSkillStatusClass({ status }),
    message: safeString(sum.message || src.message).trim(),
    summary_text,
    enabled_count,
    applied_count,
    resolved_items_count,
    step_count,
    has_applied_prompt: !!(sum.has_applied_prompt || src.has_applied_prompt),
    has_available_not_enabled: !!(sum.has_available_not_enabled || src.has_available_not_enabled),
    has_missing: !!(sum.has_missing || src.has_missing),
    has_skipped: !!(sum.has_skipped || src.has_skipped),
    source_type: safeString(sum.source_type || src.source_type).trim(),
    source_event_type: safeString(sum.source_event_type || src.source_event_type).trim(),
    source_run_id: safeString(sum.source_run_id || src.source_run_id).trim(),
  }
}

function normalizeDirectSkillCards(bundle = {}) {
  const src = safeObject(bundle)
  const rows = safeArray(src.step_rows).map((row, index) => normalizeSkillStepRow(row, index))

  return rows.filter((row) => {
    return !!(
      row.name ||
      row.summary ||
      row.path ||
      row.kind ||
      row.status
    )
  })
}

function normalizeDirectSkillActivityRows(bundle = {}) {
  const src = safeObject(bundle)

  return normalizeDirectSkillCards(src).map((row) => {
    return {
      ...row,
      preview: stringifyPreview(row.raw),
    }
  })
}

const normalized_view_mode = computed(() => {
  return normalize_runtime_view_mode(props.view_mode, 'current')
})

const runtime_display_bundle = computed(() => {
  return normalize_room_runtime_display_bundle({
    view_mode: normalized_view_mode.value,
    run_id: props.run_id,
    status_text: props.status_text,
    process_items: props.process_items,
    result_event: props.result_event,
    result_payload: props.result_payload,
    result_text: props.result_text,
    run_options: props.run_options,
    selected_run_id: props.selected_run_id,
    error: props.error,
    loading: props.loading,
    live: props.live,
    replay_items: normalized_view_mode.value === 'replay' ? props.process_items : [],
    replay_result_text: normalized_view_mode.value === 'replay' ? props.result_text : '',
    runtime_supervisor_skills: props.runtime_supervisor_skills,
    runtime_supervisor_skills_summary: props.runtime_supervisor_skills_summary,
  })
})

const direct_runtime_skill_summary = computed(() => {
  return normalizeDirectSkillSummary(
    props.runtime_supervisor_skills,
    props.runtime_supervisor_skills_summary
  )
})

const direct_runtime_skill_cards = computed(() => {
  return normalizeDirectSkillCards(props.runtime_supervisor_skills)
})

const direct_runtime_skill_activity_rows = computed(() => {
  return normalizeDirectSkillActivityRows(props.runtime_supervisor_skills)
})

const display_status_text = computed(() => {
  const text = safeString(runtime_display_bundle.value.status_text).trim()
  if (text) return text
  if (props.error) return props.error
  if (props.loading) return '加载中'
  if (normalized_view_mode.value === 'replay') return '回放可查看'
  if (props.live) return '运行中'
  if (props.run_id) return '已加载'
  return '暂无运行'
})

const display_run_id = computed(() => {
  return safeString(runtime_display_bundle.value.run_id || props.run_id).trim()
})

const display_run_options = computed(() => {
  return safeArray(runtime_display_bundle.value.run_options)
})

const can_select_replay = computed(() => {
  return display_run_options.value.length > 0
})

const selected_run_value = computed(() => {
  const explicit = safeString(runtime_display_bundle.value.selected_run_id || props.selected_run_id).trim()
  if (explicit) return explicit

  if (normalized_view_mode.value === 'replay') {
    const currentRunId = safeString(display_run_id.value).trim()
    if (currentRunId) return currentRunId
  }

  return ''
})

const result_entry = computed(() => {
  const row = safeObject(runtime_display_bundle.value.result_entry)
  return Object.keys(row).length ? row : null
})

const result_text_display = computed(() => {
  return safeString(runtime_display_bundle.value.result_text).trim()
})

const result_citations = computed(() => {
  return safeArray(runtime_display_bundle.value.result_citations)
})

const runtime_headline = computed(() => {
  return safeString(runtime_display_bundle.value.headline).trim()
})

const runtime_badge_summary = computed(() => {
  return safeString(runtime_display_bundle.value.badge_summary).trim()
})

const runtime_audit_cards = computed(() => {
  return safeArray(runtime_display_bundle.value.audit_cards)
})

const runtime_skill_summary = computed(() => {
  const bundleSummary = safeObject(runtime_display_bundle.value.skill_summary)
  const hasBundleSummary = !!(
    bundleSummary.has_skills ||
    safeString(bundleSummary.summary_text).trim() ||
    safeNumber(bundleSummary.enabled_count, 0) > 0 ||
    safeNumber(bundleSummary.applied_count, 0) > 0 ||
    safeNumber(bundleSummary.step_count, 0) > 0
  )

  if (hasBundleSummary) {
    return {
      ...normalizeDirectSkillSummary({}, bundleSummary),
      ...bundleSummary,
      status_text: safeString(bundleSummary.status_text || bundleSummary.status || 'idle').trim() || 'idle',
      statusClass: getSkillStatusClass({
        status: bundleSummary.status_text || bundleSummary.status,
      }),
      summary_text: safeString(bundleSummary.summary_text).trim(),
    }
  }

  return direct_runtime_skill_summary.value
})

const runtime_skill_cards = computed(() => {
  const bundleCards = safeArray(runtime_display_bundle.value.skill_cards)
  if (bundleCards.length > 0) return bundleCards
  return direct_runtime_skill_cards.value
})

const runtime_skill_activity_rows = computed(() => {
  const bundleRows = safeArray(runtime_display_bundle.value.skill_activity_rows)
  if (bundleRows.length > 0) return bundleRows
  return direct_runtime_skill_activity_rows.value
})

const skill_summary_chips = computed(() => {
  return buildSkillSummaryChips(runtime_skill_summary.value)
})

const show_skill_panel = computed(() => {
  if (runtime_display_bundle.value.show_skill_panel) return true

  return !!(
    runtime_skill_summary.value.has_skills ||
    runtime_skill_cards.value.length > 0 ||
    runtime_skill_activity_rows.value.length > 0
  )
})

const tool_call_rows = computed(() => {
  return safeArray(runtime_display_bundle.value.tool_call_rows)
})

const tool_result_rows = computed(() => {
  return safeArray(runtime_display_bundle.value.tool_result_rows)
})

const show_tool_activity = computed(() => {
  return !!runtime_display_bundle.value.show_tool_activity
})

const timeline_entries = computed(() => {
  return safeArray(runtime_display_bundle.value.timeline_entries)
})

const result_panel_subtitle = computed(() => {
  if (normalized_view_mode.value === 'replay') {
    return selected_run_value.value
      ? `当前查看 ${selected_run_value.value} 的回放结果`
      : '当前查看历史 run 回放'
  }

  return display_run_id.value
    ? `当前 run: ${display_run_id.value}`
    : '当前尚未关联 run'
})

const p6_test_control = computed(() => {
  const payload = safeObject(props.result_payload)
  const nested = safeObject(payload.p6_test_control)
  const actor = normalizeProbeActor(
    nested.notebook_probe_actor ||
    payload.p6_notebook_probe_actor ||
    '',
    'off'
  )

  return {
    enabled: !!(nested.enabled || nested.panel_enabled || payload.p6_test_panel_enabled),
    notebook_probe_actor: actor,
  }
})

const p6_probe_badge_text = computed(() => {
  if (!p6_test_control.value.enabled) return ''

  if (p6_test_control.value.notebook_probe_actor === 'supervisor') {
    return '当前结果带有 supervisor notebook probe，可用来核对 success path 终态与 supervisor notebook allowed path。'
  }

  if (p6_test_control.value.notebook_probe_actor === 'worker') {
    return '当前结果带有 worker notebook probe，可用来稳定核对 worker notebook write deny。'
  }

  if (p6_test_control.value.notebook_probe_actor === 'skill') {
    return '当前结果带有 skill notebook probe，可用来稳定核对 skill notebook write deny。'
  }

  return '当前已启用 P6 测试控制面，但未指定 notebook probe actor。'
})

const p6_probe_badge_class = computed(() => {
  const actor = p6_test_control.value.notebook_probe_actor
  if (actor === 'supervisor') return 'probe-supervisor'
  if (actor === 'worker') return 'probe-worker'
  if (actor === 'skill') return 'probe-skill'
  return 'probe-neutral'
})

function handle_run_change(event) {
  const runId = safeString(event?.target?.value).trim()
  if (!runId) return
  emit('select-run', runId)
  emit('switch-mode', 'replay')
}

function build_skill_card_chips(card) {
  return buildSkillCardChips(card)
}

function get_skill_status_class(row) {
  return getSkillStatusClass(row)
}
</script>

<script>
export default {
  name: 'RoomRuntimePanel',
}
</script>

<style scoped>
.room-runtime-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.room-runtime-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.room-runtime-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--color-text-primary, #e5e7eb);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.room-runtime-toggle:hover {
  color: var(--color-primary, #60a5fa);
}

.room-runtime-toggle-icon {
  width: 14px;
  text-align: center;
  color: var(--color-text-muted, #94a3b8);
}

.room-runtime-toggle-text {
  letter-spacing: 0.02em;
}

.room-runtime-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.room-runtime-state-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(15, 23, 42, 0.36);
  color: var(--color-text-muted, #94a3b8);
  font-size: 12px;
  font-weight: 600;
}

.room-runtime-state-chip.live {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.26);
  background: rgba(34, 197, 94, 0.10);
}

.room-runtime-state-chip.error {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.26);
  background: rgba(248, 113, 113, 0.10);
}

.room-runtime-state-chip.replay {
  color: #c084fc;
  border-color: rgba(192, 132, 252, 0.28);
  background: rgba(192, 132, 252, 0.10);
}

.room-runtime-state-chip.mono,
.room-runtime-audit-card-path.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  font-size: 11px;
}

.room-runtime-refresh-btn {
  min-height: 28px;
  padding: 0 12px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 8px;
  background: rgba(96, 165, 250, 0.10);
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.room-runtime-refresh-btn:hover:not(:disabled) {
  background: rgba(96, 165, 250, 0.16);
  border-color: rgba(96, 165, 250, 0.40);
  transform: translateY(-1px);
}

.room-runtime-refresh-btn:disabled {
  opacity: 0.6;
  cursor: default;
  transform: none;
}

.room-runtime-panel {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.34);
  backdrop-filter: blur(10px);
  overflow: hidden;
}

.room-runtime-result-panel {
  display: flex;
  flex-direction: column;
}

.room-runtime-process-panel {
  margin-top: 10px;
}

.room-runtime-panel-head {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  background: linear-gradient(180deg, rgba(30, 41, 59, 0.34), rgba(15, 23, 42, 0.14));
}

.room-runtime-panel-head.nested {
  border-bottom: 1px solid rgba(148, 163, 184, 0.10);
}

.room-runtime-viewbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.room-runtime-view-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.room-runtime-view-btn {
  min-height: 30px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-muted, #94a3b8);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease;
}

.room-runtime-view-btn.active {
  background: rgba(96, 165, 250, 0.16);
  color: #dbeafe;
}

.room-runtime-view-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.room-runtime-run-picker {
  display: flex;
  align-items: center;
}

.room-runtime-run-select {
  min-width: 220px;
  min-height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.50);
  color: var(--color-text-primary, #e5e7eb);
  font-size: 12px;
  outline: none;
}

.room-runtime-run-select:focus {
  border-color: rgba(96, 165, 250, 0.40);
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.12);
}

.room-runtime-panel-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--color-text-primary, #e5e7eb);
}

.room-runtime-panel-subtitle {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}

.room-runtime-panel-meta {
  font-size: 12px;
  color: #cbd5e1;
}

.room-runtime-test-probe-banner {
  margin-top: 6px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.28);
}

.room-runtime-test-probe-title {
  color: #f8fafc;
  font-size: 12px;
  font-weight: 800;
}

.room-runtime-test-probe-text {
  margin-top: 4px;
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.55;
}

.room-runtime-test-probe-banner.probe-supervisor {
  border-color: rgba(34, 197, 94, 0.28);
  background: rgba(34, 197, 94, 0.10);
}

.room-runtime-test-probe-banner.probe-worker {
  border-color: rgba(245, 158, 11, 0.28);
  background: rgba(245, 158, 11, 0.10);
}

.room-runtime-test-probe-banner.probe-skill {
  border-color: rgba(168, 85, 247, 0.28);
  background: rgba(168, 85, 247, 0.10);
}

.room-runtime-test-probe-banner.probe-neutral {
  border-color: rgba(148, 163, 184, 0.18);
  background: rgba(148, 163, 184, 0.08);
}

.room-runtime-empty {
  padding: 18px 16px;
  color: var(--color-text-muted, #94a3b8);
  font-size: 13px;
}

.room-runtime-empty.error {
  color: #fca5a5;
}

.room-runtime-result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 14px 16px 0;
}

.room-runtime-result-type {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.14);
  border: 1px solid rgba(59, 130, 246, 0.28);
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.room-runtime-result-actor {
  font-size: 12px;
  color: #cbd5e1;
}

.room-runtime-result-time {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}

.room-runtime-chip-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 16px 0;
}

.room-runtime-chip-row.result {
  padding-top: 10px;
}

.room-runtime-chip-row.audit {
  padding: 10px 0 0;
}

.room-runtime-chip {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 700;
}

.room-runtime-result-markdown {
  padding: 14px 16px 16px;
  color: var(--color-text-primary, #e5e7eb);
  font-size: 13px;
  line-height: 1.72;
}

.room-runtime-result-markdown :deep(h1),
.room-runtime-result-markdown :deep(h2),
.room-runtime-result-markdown :deep(h3) {
  margin: 0 0 10px;
  color: #f8fafc;
  line-height: 1.35;
}

.room-runtime-result-markdown :deep(p) {
  margin: 0 0 10px;
}

.room-runtime-result-markdown :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
  font-size: 12px;
}

.room-runtime-audit-panel,
.room-runtime-skill-panel,
.room-runtime-tool-panel {
  margin: 0 16px 16px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.28);
}

.room-runtime-audit-title,
.room-runtime-skill-title,
.tool-activity-title {
  margin-bottom: 12px;
  color: var(--color-text-primary, #e5e7eb);
  font-size: 13px;
  font-weight: 800;
}

.room-runtime-audit-grid,
.room-runtime-skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
}

.room-runtime-audit-card,
.room-runtime-skill-card,
.room-runtime-skill-summary-card {
  padding: 12px;
  border-radius: 10px;
  background: rgba(2, 6, 23, 0.28);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.room-runtime-audit-card-head,
.room-runtime-skill-card-head,
.room-runtime-skill-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.room-runtime-audit-card-title,
.room-runtime-skill-card-title,
.room-runtime-skill-summary-name {
  color: var(--color-text-primary, #e5e7eb);
  font-size: 12px;
  font-weight: 800;
}

.room-runtime-audit-card-message,
.room-runtime-skill-card-message {
  margin-top: 10px;
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.room-runtime-audit-card-path {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.44);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #bfdbfe;
  line-height: 1.5;
  word-break: break-all;
}

.room-runtime-skill-summary-card {
  margin-bottom: 10px;
}

.room-runtime-skill-activity {
  margin-top: 12px;
}

.room-runtime-skill-subtitle {
  margin-bottom: 10px;
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 700;
}

.tool-call-card,
.tool-result-card {
  padding: 12px;
  border-radius: 10px;
  background: rgba(2, 6, 23, 0.28);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.tool-call-card + .tool-call-card,
.tool-result-card + .tool-result-card,
.tool-call-card + .tool-result-card,
.tool-result-card + .tool-call-card {
  margin-top: 10px;
}

.tool-call-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.12);
  border: 1px solid rgba(96, 165, 250, 0.24);
  color: #bfdbfe;
  font-size: 11px;
  font-weight: 800;
}

.tool-badge.success {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.24);
  color: #bbf7d0;
}

.tool-badge.skill {
  background: rgba(168, 85, 247, 0.12);
  border-color: rgba(168, 85, 247, 0.24);
  color: #e9d5ff;
}

.tool-name {
  color: var(--color-text-primary, #e5e7eb);
  font-size: 12px;
  font-weight: 700;
  word-break: break-all;
}

.tool-status {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: lowercase;
}

.tool-status.success {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.10);
  border: 1px solid rgba(34, 197, 94, 0.22);
}

.tool-status.warning {
  color: #fde68a;
  background: rgba(245, 158, 11, 0.10);
  border: 1px solid rgba(245, 158, 11, 0.22);
}

.tool-status.error {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.10);
  border: 1px solid rgba(239, 68, 68, 0.22);
}

.tool-status.running {
  color: #bfdbfe;
  background: rgba(59, 130, 246, 0.10);
  border: 1px solid rgba(59, 130, 246, 0.22);
}

.tool-status.applied {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.10);
  border: 1px solid rgba(34, 197, 94, 0.22);
}

.tool-status.enabled {
  color: #bfdbfe;
  background: rgba(59, 130, 246, 0.10);
  border: 1px solid rgba(59, 130, 246, 0.22);
}

.tool-status.idle {
  color: #cbd5e1;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.tool-json {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.room-runtime-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 8px 16px 16px;
}

.room-runtime-timeline-item {
  position: relative;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 12px;
  padding: 12px 0;
}

.room-runtime-timeline-item:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 30px;
  left: 8px;
  bottom: -8px;
  width: 1px;
  background: rgba(148, 163, 184, 0.16);
}

.room-runtime-timeline-bullet {
  position: relative;
  top: 4px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid rgba(148, 163, 184, 0.30);
  background: rgba(15, 23, 42, 0.92);
}

.room-runtime-timeline-item.kind-plan .room-runtime-timeline-bullet {
  border-color: rgba(59, 130, 246, 0.60);
}

.room-runtime-timeline-item.kind-delegate .room-runtime-timeline-bullet {
  border-color: rgba(245, 158, 11, 0.60);
}

.room-runtime-timeline-item.kind-supervisor .room-runtime-timeline-bullet {
  border-color: rgba(168, 85, 247, 0.60);
}

.room-runtime-timeline-item.kind-route .room-runtime-timeline-bullet {
  border-color: rgba(14, 165, 233, 0.60);
}

.room-runtime-timeline-item.kind-message .room-runtime-timeline-bullet {
  border-color: rgba(34, 197, 94, 0.60);
}

.room-runtime-timeline-item.kind-final .room-runtime-timeline-bullet {
  border-color: rgba(16, 185, 129, 0.70);
}

.room-runtime-timeline-item.kind-abort .room-runtime-timeline-bullet,
.room-runtime-timeline-item.kind-error .room-runtime-timeline-bullet {
  border-color: rgba(239, 68, 68, 0.70);
}

.room-runtime-timeline-body {
  min-width: 0;
}

.room-runtime-timeline-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.room-runtime-timeline-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.room-runtime-timeline-actor {
  font-size: 12px;
  color: #cbd5e1;
}

.room-runtime-timeline-time {
  font-size: 12px;
  color: var(--color-text-muted, #94a3b8);
}

.room-runtime-timeline-summary {
  margin-top: 8px;
  color: var(--color-text-primary, #e5e7eb);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.room-runtime-timeline-preview {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(2, 6, 23, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

@media (max-width: 768px) {
  .room-runtime-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .room-runtime-toolbar-right {
    width: 100%;
  }

  .room-runtime-viewbar {
    flex-direction: column;
    align-items: stretch;
  }

  .room-runtime-run-picker {
    width: 100%;
  }

  .room-runtime-run-select {
    width: 100%;
    min-width: 0;
  }

  .room-runtime-result-meta,
  .room-runtime-chip-row,
  .room-runtime-result-markdown {
    padding-left: 14px;
    padding-right: 14px;
  }

  .room-runtime-audit-panel,
  .room-runtime-skill-panel,
  .room-runtime-tool-panel {
    margin-left: 14px;
    margin-right: 14px;
  }

  .room-runtime-timeline {
    padding-left: 14px;
    padding-right: 14px;
  }

  .room-runtime-audit-grid,
  .room-runtime-skill-grid {
    grid-template-columns: 1fr;
  }
}
</style>
