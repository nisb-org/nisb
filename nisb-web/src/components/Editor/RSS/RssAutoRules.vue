<template>
  <div class="auto_rules">
    <div class="row row_between">
      <div class="section_title muted">{{ t('rss.center.gate.rules.sectionTitle') }}</div>
      <div v-if="rules.length" class="muted smalltext">
        {{ t('rss.center.gate.rules.count', { count: rules.length }) }}
      </div>
    </div>

    <div class="form">
      <div class="kv">
        <div class="k">{{ t('rss.center.gate.rules.fields.ruleName') }}</div>
        <input
          class="inp small"
          v-model="rule_name"
          :placeholder="t('rss.center.gate.rules.placeholders.ruleName')"
          @keydown.enter="add_rule_from_current"
        />

        <div class="k">{{ t('rss.center.gate.rules.fields.excludeTerms') }}</div>
        <input
          class="inp small"
          v-model="exclude_terms"
          :placeholder="t('rss.center.gate.rules.placeholders.excludeTerms')"
        />

        <div class="k">{{ t('rss.center.gate.rules.fields.timesPerDay') }}</div>
        <select class="inp small" v-model.number="times_per_day">
          <option :value="1">1</option>
          <option :value="2">2</option>
          <option :value="3">3</option>
          <option :value="4">4</option>
          <option :value="6">6</option>
        </select>

        <div class="k">{{ t('rss.center.gate.rules.fields.startTimeUtc') }}</div>
        <input class="inp small mono" type="time" v-model="start_time_utc" />

        <div class="k">{{ t('rss.center.gate.rules.fields.timesUtc') }}</div>
        <input
          class="inp small mono"
          v-model="times_utc_text"
          :placeholder="t('rss.center.gate.rules.placeholders.timesUtc')"
        />

        <div class="k">{{ t('rss.center.gate.rules.fields.maxPerRun') }}</div>
        <input
          class="inp small mono"
          type="number"
          min="1"
          max="5000"
          v-model.number="max_per_run"
          :placeholder="t('rss.center.gate.rules.placeholders.maxPerRun')"
        />
      </div>

      <div class="muted smalltext tipline">
        {{ t('rss.center.gate.rules.tips.autoTimes') }}
      </div>
    </div>

    <div class="btn_row">
      <button
        class="btn"
        :class="{ disabled: working }"
        :aria-disabled="working ? 'true' : 'false'"
        @click="add_rule_from_current"
      >
        {{ t('rss.center.gate.rules.actions.generateFromCurrent') }}
      </button>
      <button class="btn ghost" :disabled="working" @click="run_due_now">
        {{ t('rss.center.gate.rules.actions.runDueNow') }}
      </button>
      <button class="btn ghost" :disabled="working" @click="load_rules">
        {{ t('rss.center.gate.rules.actions.refreshRules') }}
      </button>
    </div>

    <div v-if="rules.length" class="rules_list">
      <div class="list_header muted smalltext row row_between">
        <div>{{ t('rss.center.gate.rules.savedRules', { count: rules.length }) }}</div>
        <button class="btn mini ghost" type="button" :disabled="working" @click="toggle_rules_open">
          {{ rules_open ? t('rss.center.gate.rules.actions.collapseList') : t('rss.center.gate.rules.actions.expandList') }}
        </button>
      </div>

      <div v-if="!rules_open" class="muted smalltext tipline">
        {{ t('rss.center.gate.rules.tips.collapsedList') }}
      </div>

      <div v-else class="rules_box">
        <div v-for="r in rules" :key="r.rule_id" class="rule_item" :class="{ disabled: !r.enabled }">
          <div class="rule_head">
            <span class="rule_status">{{ r.enabled ? '✅' : '⏸' }}</span>
            <span class="rule_name">{{ r.name }}</span>
            <span class="rule_id mono muted">{{ r.rule_id }}</span>
          </div>

          <div class="rule_meta muted smalltext">
            <span v-if="r.query">{{ t('rss.center.gate.rules.meta.query', { value: r.query }) }}</span>
            <span v-if="r.library_id">{{ t('rss.center.gate.rules.meta.library', { value: r.library_id }) }}</span>
            <span v-if="Array.isArray(r.times_utc) && r.times_utc.length">
              {{ t('rss.center.gate.rules.meta.timesUtc', { value: r.times_utc.join(',') }) }}
            </span>
            <span v-else-if="r.interval_minutes">
              {{ t('rss.center.gate.rules.meta.legacyInterval', { minutes: r.interval_minutes }) }}
            </span>
            <span v-if="r.last_run_at">{{ t('rss.center.gate.rules.meta.lastRun', { value: format_time(r.last_run_at) }) }}</span>
            <span v-if="r.next_run_at && r.enabled">{{ t('rss.center.gate.rules.meta.nextRun', { value: format_time(r.next_run_at) }) }}</span>
          </div>

          <div class="rule_actions">
            <button class="btn mini ghost" :disabled="working" @click="open_edit_rule(r)">
              {{ t('rss.center.gate.rules.actions.edit') }}
            </button>
            <button class="btn mini" :disabled="working" @click="run_rule(r.rule_id)">
              {{ t('rss.center.gate.rules.actions.runNow') }}
            </button>
            <button class="btn mini ghost" :disabled="working" @click="toggle_rule(r.rule_id, r.enabled)">
              {{ r.enabled ? t('rss.center.gate.rules.actions.disable') : t('rss.center.gate.rules.actions.enable') }}
            </button>
            <button class="btn mini danger" :disabled="working" @click="delete_rule(r.rule_id)">
              {{ t('rss.center.gate.rules.actions.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!working" class="empty muted">
      {{ t('rss.center.gate.rules.empty') }}
    </div>

    <div v-if="last_report" class="report">
      <div class="report_title muted smalltext">{{ t('rss.center.gate.rules.report.title') }}</div>
      <div class="rline">
        <span class="mono">{{ last_report.rule_id }}</span>
        <span>{{ t('rss.center.gate.rules.report.searched', { count: last_report.report.searched_total || last_report.report.searched || 0 }) }}</span>
        <span>{{ t('rss.center.gate.rules.report.picked', { count: last_report.report.picked || 0 }) }}</span>
        <span class="ok">{{ t('rss.center.gate.rules.report.imported', { count: last_report.report.imported || 0 }) }}</span>
        <span>{{ t('rss.center.gate.rules.report.skipped', { count: last_report.report.skipped || 0 }) }}</span>
        <span v-if="last_report.report.failed" class="danger">
          {{ t('rss.center.gate.rules.report.failed', { count: last_report.report.failed }) }}
        </span>
      </div>
      <div v-if="last_report.report.first_error" class="rline danger smalltext">
        {{ last_report.report.first_error }}
      </div>
    </div>

    <div v-if="edit_open" class="modal_mask" @click.self="close_edit_rule">
      <div class="modal">
        <div class="modal_head">
          <div class="modal_title">{{ t('rss.center.gate.rules.modal.title') }}</div>
          <button class="btn mini ghost" type="button" :disabled="working" @click="close_edit_rule">
            {{ t('rss.center.gate.rules.actions.close') }}
          </button>
        </div>

        <div class="modal_body">
          <div class="kv2">
            <div class="k">{{ t('rss.center.gate.rules.fields.ruleName') }}</div>
            <input
              class="inp small"
              v-model="edit_form.name"
              :placeholder="t('rss.center.gate.rules.placeholders.editRuleName')"
            />

            <div class="k">{{ t('rss.center.gate.rules.fields.query') }}</div>
            <input
              class="inp small"
              v-model="edit_form.query"
              :placeholder="t('rss.center.gate.rules.placeholders.query')"
            />

            <div class="k">{{ t('rss.center.gate.rules.fields.expandQueries') }}</div>
            <textarea
              class="inp small area"
              v-model="edit_form.expand_queries_text"
              :placeholder="t('rss.center.gate.rules.placeholders.expandQueries')"
            ></textarea>

            <div class="k">{{ t('rss.center.gate.rules.fields.libraryId') }}</div>
            <input
              class="inp small mono"
              v-model="edit_form.library_id"
              :placeholder="t('rss.center.gate.rules.placeholders.libraryId')"
            />

            <div class="k">{{ t('rss.center.gate.rules.fields.feedScope') }}</div>
            <div class="row">
              <label class="radio">
                <input type="radio" value="all" v-model="edit_form.feed_scope" />
                {{ t('rss.center.gate.rules.scope.allFeeds') }}
              </label>
              <label class="radio">
                <input type="radio" value="selected" v-model="edit_form.feed_scope" />
                {{ t('rss.center.gate.rules.scope.selectedFeeds') }}
              </label>
              <span class="muted smalltext">{{ t('rss.center.gate.rules.scope.hint') }}</span>
            </div>

            <div class="k">{{ t('rss.center.gate.rules.fields.feedIds') }}</div>
            <textarea
              class="inp small mono area"
              v-model="edit_form.feed_ids_text"
              :disabled="edit_form.feed_scope !== 'selected'"
              :placeholder="t('rss.center.gate.rules.placeholders.feedIds')"
            ></textarea>

            <div class="k">{{ t('rss.center.gate.rules.fields.days') }}</div>
            <input class="inp small mono" type="number" min="0" max="3650" v-model.number="edit_form.days" />

            <div class="k">{{ t('rss.center.gate.rules.fields.startDate') }}</div>
            <input class="inp small" type="date" v-model="edit_form.start_date" />

            <div class="k">{{ t('rss.center.gate.rules.fields.endDate') }}</div>
            <input class="inp small" type="date" v-model="edit_form.end_date" />

            <div class="k">{{ t('rss.center.gate.rules.fields.limit') }}</div>
            <select class="inp small" v-model.number="edit_form.limit">
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="80">80</option>
              <option :value="200">200</option>
            </select>

            <div class="k">{{ t('rss.center.gate.rules.fields.minScore') }}</div>
            <input class="inp small mono" type="number" step="0.01" min="0" max="1" v-model.number="edit_form.min_score" />

            <div class="k">{{ t('rss.center.gate.rules.fields.strictLexical') }}</div>
            <label class="check">
              <input type="checkbox" v-model="edit_form.strict_lexical" />
              {{ t('rss.center.gate.rules.fields.strictLexicalHint') }}
            </label>

            <div class="k">{{ t('rss.center.gate.rules.fields.excludeTerms') }}</div>
            <input
              class="inp small"
              v-model="edit_form.exclude_terms"
              :placeholder="t('rss.center.gate.rules.placeholders.excludeTerms')"
            />

            <div class="k">{{ t('rss.center.gate.rules.fields.timesPerDay') }}</div>
            <select class="inp small" v-model.number="edit_form.times_per_day">
              <option :value="1">1</option>
              <option :value="2">2</option>
              <option :value="3">3</option>
              <option :value="4">4</option>
              <option :value="6">6</option>
            </select>

            <div class="k">{{ t('rss.center.gate.rules.fields.startTimeUtc') }}</div>
            <input class="inp small mono" type="time" v-model="edit_form.start_time_utc" />

            <div class="k">{{ t('rss.center.gate.rules.fields.timesUtc') }}</div>
            <input
              class="inp small mono"
              v-model="edit_form.times_utc_text"
              :placeholder="t('rss.center.gate.rules.placeholders.timesUtc')"
            />

            <div class="k">{{ t('rss.center.gate.rules.fields.maxPerRun') }}</div>
            <input class="inp small mono" type="number" min="1" max="5000" v-model.number="edit_form.max_per_run" />

            <div class="k">{{ t('rss.center.gate.rules.fields.enabled') }}</div>
            <label class="check">
              <input type="checkbox" v-model="edit_form.enabled" />
              {{ t('rss.center.gate.rules.fields.enabledRule') }}
            </label>
          </div>

          <div class="muted smalltext tipbox">
            {{ t('rss.center.gate.rules.tips.matchMode') }}
          </div>
        </div>

        <div class="modal_actions">
          <button class="btn ghost" type="button" :disabled="working" @click="reset_edit_to_current_search">
            {{ t('rss.center.gate.rules.actions.useCurrentSearch') }}
          </button>
          <button class="btn" type="button" :disabled="working" @click="save_edit_rule">
            {{ t('rss.center.gate.rules.actions.saveChanges') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  query: { type: String, default: '' },
  feed_ids: { type: Array, default: () => [] },
  days: { type: Number, default: 30 },
  start_date: { type: String, default: '' },
  end_date: { type: String, default: '' },
  limit: { type: Number, default: 50 },
  min_score: { type: Number, default: 0.35 },
  strict_lexical: { type: Boolean, default: true },
  library_id: { type: String, default: '' },
  callTool: { type: Function, required: true }
})

const emit = defineEmits(['refresh', 'toast'])
const { t } = useI18n()

const rules_open = ref(false)
function toggle_rules_open() { rules_open.value = !rules_open.value }

const working = ref(false)
const rules = ref([])

const rule_name = ref('')
const exclude_terms = ref('')
const times_per_day = ref(1)
const start_time_utc = ref('06:55')
const times_utc_text = ref('06:55')
const max_per_run = ref(30)

const last_report = ref(null)

const edit_open = ref(false)
const editing_rule_id = ref('')
const edit_prefilling = ref(false)

const edit_form = ref({
  rule_id: '',
  name: '',
  enabled: true,

  query: '',
  expand_queries_text: '',
  library_id: '',
  feed_scope: 'all',
  feed_ids_text: '',

  days: 30,
  start_date: '',
  end_date: '',
  limit: 50,
  min_score: 0.35,
  strict_lexical: true,

  exclude_terms: '',
  times_per_day: 1,
  start_time_utc: '06:55',
  times_utc_text: '06:55',
  max_per_run: 30
})

const normalized_quick_query = computed(() => {
  const q = String(props.query || '').trim()
  if (q) return q
  return String(rule_name.value || '').trim()
})

const can_create_rule = computed(() => {
  const quickQuery = normalized_quick_query.value
  const hasLibrary = !!String(props.library_id || '').trim()
  return !!quickQuery && hasLibrary
})

function toast(message, type = 'info') {
  emit('toast', { message, type })
}

function as_num(v, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function result_status(r) {
  if (!r || typeof r !== 'object') return ''
  const s = String(r.status || '').trim().toLowerCase()
  if (s) return s
  return r.success === true ? 'ok' : ''
}

function is_hard_error_result(r) {
  const s = result_status(r)
  return ['error', 'timeout', 'exception', 'failed', 'failure'].includes(s)
}

function has_failures(r) {
  if (!r || typeof r !== 'object') return false
  if (r.had_failures === true) return true

  const s = result_status(r)
  if (['partial_failure', 'partial_error'].includes(s)) return true

  const stats = (r.stats && typeof r.stats === 'object') ? r.stats : {}
  if (as_num(stats.failed, 0) > 0) return true
  if (as_num(stats.failed_users, 0) > 0) return true
  if (as_num(stats.failed_rules, 0) > 0) return true
  if (as_num(stats.failures, 0) > 0) return true

  return false
}

function is_ok(r) {
  if (!r || typeof r !== 'object') return false
  if (is_hard_error_result(r)) return false
  const s = result_status(r)
  if (r.success === true) return !['partial_failure', 'partial_error'].includes(s)
  return ['ok', 'success', 'saved', 'updated', 'deleted', 'ran', 'skipped'].includes(s)
}

function is_runnable_result(r) {
  if (!r || typeof r !== 'object') return false
  if (is_hard_error_result(r)) return false
  const s = result_status(r)
  if (r.success === true) return true
  return [
    'ok',
    'success',
    'saved',
    'updated',
    'deleted',
    'ran',
    'skipped',
    'partial_failure',
    'partial_error'
  ].includes(s)
}

function first_text(...vals) {
  for (const v of vals) {
    const s = String(v || '').trim()
    if (s) return s
  }
  return ''
}

function extract_error_text(r, fallback = '') {
  return first_text(
    r?.message,
    r?.error,
    r?.report?.first_error,
    fallback
  )
}

function format_time(iso_str) {
  if (!iso_str) return ''
  try {
    return String(iso_str).slice(0, 16).replace('T', ' ')
  } catch {
    return ''
  }
}

function parse_feed_ids_text(text) {
  const s = String(text || '')
  const parts = s.split(/[\r\n,]+/g).map((x) => String(x || '').trim()).filter(Boolean)
  const out = []
  const seen = new Set()
  for (const p of parts) {
    if (seen.has(p)) continue
    seen.add(p)
    out.push(p)
  }
  return out
}

function parse_expand_queries_text(text) {
  const s = String(text || '')
  const parts = s.split(/[\r\n,]+/g).map((x) => String(x || '').trim()).filter(Boolean)
  const out = []
  const seen = new Set()
  for (const p of parts) {
    if (seen.has(p)) continue
    seen.add(p)
    out.push(p)
    if (out.length >= 50) break
  }
  return out
}

function guess_feed_scope(feed_ids) {
  const arr = Array.isArray(feed_ids) ? feed_ids : []
  return arr.length ? 'selected' : 'all'
}

function parse_times_utc(text) {
  const raw = String(text || '').trim()
  if (!raw) return []
  const parts = raw.split(',').map((x) => String(x || '').trim()).filter(Boolean)

  const out = []
  const seen = new Set()
  for (const p of parts) {
    if (!p.includes(':')) continue
    const [hh, mm] = p.split(':', 2)
    const h = Number(hh)
    const m = Number(mm)
    if (!Number.isInteger(h) || !Number.isInteger(m)) continue
    if (h < 0 || h > 23 || m < 0 || m > 59) continue
    const t2 = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
    if (seen.has(t2)) continue
    seen.add(t2)
    out.push(t2)
  }
  out.sort()
  return out
}

function build_times_utc(n, start_hhmm) {
  const times = []
  const nn = Math.max(1, Math.min(6, Number(n) || 1))
  const base = parse_times_utc(String(start_hhmm || '06:55'))[0] || '06:55'
  const [hh, mm] = base.split(':')
  const start_min = Number(hh) * 60 + Number(mm)
  const step = Math.floor((24 * 60) / nn)

  for (let i = 0; i < nn; i++) {
    const x = (start_min + i * step) % (24 * 60)
    const h = Math.floor(x / 60)
    const m = x % 60
    times.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
  }
  return Array.from(new Set(times)).sort()
}

function normalize_quick_times_utc() {
  const parsed = parse_times_utc(times_utc_text.value)
  if (parsed.length) return parsed
  const built = build_times_utc(times_per_day.value || 1, start_time_utc.value || '06:55')
  times_utc_text.value = built.join(',')
  return built
}

function regenerate_times_utc_text() {
  const t2 = build_times_utc(times_per_day.value, start_time_utc.value)
  times_utc_text.value = t2.join(',')
}

watch(
  () => [times_per_day.value, start_time_utc.value],
  () => regenerate_times_utc_text(),
  { deep: false }
)

async function load_rules() {
  working.value = true
  try {
    const r = await props.callTool('nisb_rss_auto_import_rules_get', {})
    if (!is_ok(r)) {
      return toast(
        extract_error_text(r, t('rss.center.gate.rules.messages.loadRulesFailed')),
        'error'
      )
    }

    rules.value = Array.isArray(r.rules) ? r.rules : []
    if (!rules.value.length) rules_open.value = false
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.loadRulesFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function add_rule_from_current() {
  if (working.value) return

  const quick_query = normalized_quick_query.value
  const library_id = String(props.library_id || '').trim()

  if (!library_id) {
    return toast(t('rss.center.gate.rules.messages.fillQueryAndLibraryFirst'), 'info')
  }

  if (!quick_query) {
    return toast(t('rss.center.gate.rules.messages.fillQueryAndLibraryFirst'), 'info')
  }

  const times_utc = normalize_quick_times_utc()
  const final_max_per_run = Math.max(1, Number(max_per_run.value) || 30)
  const name = String(rule_name.value || '').trim() || `auto_${quick_query.slice(0, 40)}`

  const upsert = {
    name,
    enabled: true,

    query: quick_query,
    expand_queries: [],
    library_id,
    feed_ids: Array.isArray(props.feed_ids) ? props.feed_ids : [],

    days: props.days,
    start_date: props.start_date || '',
    end_date: props.end_date || '',
    limit: props.limit,
    min_score: props.min_score,
    strict_lexical: !!props.strict_lexical,
    methods: ['hybrid'],
    exclude_spam: true,

    exclude_terms: exclude_terms.value.trim(),

    times_utc,
    interval_minutes: 0,
    max_per_run: final_max_per_run,

    import_mode: 'copy',
    match_mode: 'all',
    sort_by: 'relevance'
  }

  working.value = true
  try {
    const r = await props.callTool('nisb_rss_auto_import_rules_set', { upserts: [upsert], deletes: [] })
    if (!is_ok(r)) {
      return toast(
        extract_error_text(r, t('rss.center.gate.rules.messages.saveRuleFailed')),
        'error'
      )
    }

    toast(t('rss.center.gate.rules.messages.ruleSaved'), 'success')
    rule_name.value = ''
    exclude_terms.value = ''

    await load_rules()
    if (rules.value.length) rules_open.value = true
    emit('refresh')
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.saveRuleFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function run_rule(rule_id) {
  if (!rule_id) return
  working.value = true
  last_report.value = null

  try {
    const r = await props.callTool('nisb_rss_auto_import_run_rule', { rule_id })
    if (!is_runnable_result(r)) {
      return toast(
        t('rss.center.gate.rules.messages.runFailed', {
          error: extract_error_text(r, t('rss.center.gate.rules.messages.unknownError'))
        }),
        'error'
      )
    }

    const report = (r && typeof r.report === 'object' && r.report) ? r.report : {}
    last_report.value = { rule_id, report }

    const imported = as_num(report.imported, 0)
    const failed = as_num(report.failed, 0)
    const partial = has_failures(r) || failed > 0

    if (partial) {
      const err = first_text(
        report.first_error,
        extract_error_text(r, t('rss.center.gate.rules.messages.unknownError'))
      )
      toast(
        `${t('rss.center.gate.rules.messages.runFailed', { error: err })} (imported=${imported}, failed=${failed})`,
        'error'
      )
    } else if (imported > 0) {
      toast(t('rss.center.gate.rules.messages.runFinishedImported', { count: imported }), 'success')
    } else {
      toast(t('rss.center.gate.rules.messages.runFinishedNoNew'), 'info')
    }

    await load_rules()
    emit('refresh')
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.runFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function run_due_now() {
  working.value = true
  last_report.value = null

  try {
    const r = await props.callTool('nisb_rss_auto_import_run_due', {})
    if (!is_runnable_result(r)) {
      return toast(
        t('rss.center.gate.rules.messages.runDueFailedWithError', {
          error: extract_error_text(r, t('rss.center.gate.rules.messages.unknownError'))
        }),
        'error'
      )
    }

    const stats = (r && typeof r.stats === 'object' && r.stats) ? r.stats : {}
    const ran = as_num(stats.ran, 0)
    const imported = as_num(stats.imported, 0)
    const failed = as_num(stats.failed, 0)
    const failed_rules = as_num(stats.failed_rules, 0)
    const partial = has_failures(r) || failed > 0 || failed_rules > 0

    if (ran === 0) {
      toast(t('rss.center.gate.rules.messages.noDueRules'), 'info')
    } else if (partial) {
      const extra = first_text(r?.message, r?.error)
      const suffix = extra ? `; ${extra}` : ''
      toast(
        `${t('rss.center.gate.rules.messages.ranDueRulesImported', { ran, imported })} (failed=${failed}, failed_rules=${failed_rules}${suffix})`,
        'error'
      )
    } else {
      toast(
        t('rss.center.gate.rules.messages.ranDueRulesImported', {
          ran,
          imported
        }),
        'success'
      )
    }

    await load_rules()
    emit('refresh')
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.runDueFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function toggle_rule(rule_id, current_enabled) {
  if (!rule_id) return
  const rule = rules.value.find((r) => r.rule_id === rule_id)
  if (!rule) return

  working.value = true
  try {
    const updated = { ...rule, enabled: !current_enabled }
    const r = await props.callTool('nisb_rss_auto_import_rules_set', { upserts: [updated], deletes: [] })
    if (!is_ok(r)) {
      return toast(
        extract_error_text(r, t('rss.center.gate.rules.messages.updateRuleFailed')),
        'error'
      )
    }

    toast(
      !current_enabled
        ? t('rss.center.gate.rules.messages.ruleEnabled')
        : t('rss.center.gate.rules.messages.ruleDisabled'),
      'success'
    )
    await load_rules()
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.updateRuleFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function delete_rule(rule_id) {
  if (!rule_id) return
  if (!confirm(t('rss.center.gate.rules.confirm.deleteRule'))) return

  working.value = true
  try {
    const r = await props.callTool('nisb_rss_auto_import_rules_set', { upserts: [], deletes: [rule_id] })
    if (!is_ok(r)) {
      return toast(
        extract_error_text(r, t('rss.center.gate.rules.messages.deleteRuleFailed')),
        'error'
      )
    }

    toast(t('rss.center.gate.rules.messages.ruleDeleted'), 'success')
    await load_rules()
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.deleteRuleFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

async function open_edit_rule(rule) {
  if (!rule || !rule.rule_id) return

  editing_rule_id.value = rule.rule_id
  edit_open.value = true
  edit_prefilling.value = true

  const feed_ids = Array.isArray(rule.feed_ids) ? rule.feed_ids : []
  const feed_scope = guess_feed_scope(feed_ids)
  const expand_queries = Array.isArray(rule.expand_queries) ? rule.expand_queries : []

  const times = Array.isArray(rule.times_utc) ? rule.times_utc : []
  const times_text = times.join(',')

  edit_form.value = {
    rule_id: rule.rule_id,
    name: String(rule.name || '').trim(),
    enabled: !!rule.enabled,

    query: String(rule.query || '').trim(),
    expand_queries_text: expand_queries.join('\n'),
    library_id: String(rule.library_id || '').trim(),
    feed_scope,
    feed_ids_text: feed_ids.join(', '),

    days: Number(rule.days ?? 30) || 30,
    start_date: String(rule.start_date || ''),
    end_date: String(rule.end_date || ''),
    limit: Number(rule.limit ?? 50) || 50,
    min_score: Number(rule.min_score ?? 0.35) || 0.35,
    strict_lexical: rule.strict_lexical !== false,

    exclude_terms: String(rule.exclude_terms || ''),

    times_per_day: Math.max(1, Math.min(6, times.length || 1)),
    start_time_utc: times[0] || '06:55',
    times_utc_text: times_text || '06:55',

    max_per_run: Number(rule.max_per_run ?? 30) || 30
  }

  await nextTick()
  edit_prefilling.value = false
}

function close_edit_rule() {
  edit_open.value = false
  editing_rule_id.value = ''
  edit_prefilling.value = false
}

function reset_edit_to_current_search() {
  edit_form.value.query = String(props.query || '').trim()
  edit_form.value.expand_queries_text = ''
  edit_form.value.library_id = String(props.library_id || '').trim()

  const cur = Array.isArray(props.feed_ids) ? props.feed_ids : []
  edit_form.value.feed_scope = cur.length ? 'selected' : 'all'
  edit_form.value.feed_ids_text = cur.join(', ')

  edit_form.value.days = Number(props.days ?? 30) || 30
  edit_form.value.start_date = props.start_date || ''
  edit_form.value.end_date = props.end_date || ''
  edit_form.value.limit = Number(props.limit ?? 50) || 50
  edit_form.value.min_score = Number(props.min_score ?? 0.35) || 0.35
  edit_form.value.strict_lexical = !!props.strict_lexical
}

watch(
  () => [edit_form.value.times_per_day, edit_form.value.start_time_utc],
  () => {
    if (!edit_open.value) return
    if (edit_prefilling.value) return
    const t2 = build_times_utc(edit_form.value.times_per_day, edit_form.value.start_time_utc)
    edit_form.value.times_utc_text = t2.join(',')
  },
  { deep: false }
)

async function save_edit_rule() {
  const rid = editing_rule_id.value
  if (!rid) return

  const rule = rules.value.find((x) => x.rule_id === rid)
  if (!rule) {
    toast(t('rss.center.gate.rules.messages.ruleMissing'), 'error')
    close_edit_rule()
    return
  }

  const name = String(edit_form.value.name || '').trim()
  const query = String(edit_form.value.query || '').trim()
  const library_id = String(edit_form.value.library_id || '').trim()
  if (!name) return toast(t('rss.center.gate.rules.messages.fillRuleName'), 'info')
  if (!query) return toast(t('rss.center.gate.rules.messages.fillQuery'), 'info')
  if (!library_id) return toast(t('rss.center.gate.rules.messages.fillLibrary'), 'info')

  const expand_queries = parse_expand_queries_text(edit_form.value.expand_queries_text)

  let feed_ids = []
  if (edit_form.value.feed_scope === 'selected') {
    feed_ids = parse_feed_ids_text(edit_form.value.feed_ids_text)
    if (!feed_ids.length) return toast(t('rss.center.gate.rules.messages.feedIdsRequired'), 'info')
  }

  const times_utc = parse_times_utc(edit_form.value.times_utc_text)
  if (times_utc.length === 0) return toast(t('rss.center.gate.rules.messages.fillTimesUtc'), 'info')

  const updated = {
    ...rule,
    rule_id: rid,
    name,
    enabled: !!edit_form.value.enabled,

    query,
    expand_queries,
    library_id,
    feed_ids,

    days: Number(edit_form.value.days) || 30,
    start_date: String(edit_form.value.start_date || ''),
    end_date: String(edit_form.value.end_date || ''),
    limit: Number(edit_form.value.limit) || 50,
    min_score: Number(edit_form.value.min_score) || 0.35,
    strict_lexical: !!edit_form.value.strict_lexical,

    exclude_terms: String(edit_form.value.exclude_terms || '').trim(),

    times_utc,
    interval_minutes: 0,
    max_per_run: Number(edit_form.value.max_per_run) || 30,

    methods: Array.isArray(rule.methods) && rule.methods.length ? rule.methods : ['hybrid'],
    exclude_spam: rule.exclude_spam !== false,
    import_mode: rule.import_mode || 'copy',
    match_mode: 'all',
    sort_by: rule.sort_by || 'relevance'
  }

  working.value = true
  try {
    const r = await props.callTool('nisb_rss_auto_import_rules_set', { upserts: [updated], deletes: [] })
    if (!is_ok(r)) {
      return toast(
        extract_error_text(r, t('rss.center.gate.rules.messages.saveEditFailed')),
        'error'
      )
    }

    toast(t('rss.center.gate.rules.messages.ruleUpdated'), 'success')
    close_edit_rule()
    await load_rules()
    emit('refresh')
  } catch (e) {
    toast(
      t('rss.center.gate.rules.messages.saveEditFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  } finally {
    working.value = false
  }
}

onMounted(() => {
  regenerate_times_utc_text()
  load_rules()
})

defineExpose({ load_rules, run_due_now, can_create_rule })
</script>

<style scoped>
.auto_rules { display: flex; flex-direction: column; gap: 0.75rem; }
.row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.row_between { justify-content: space-between; }
.section_title { font-size: 0.875rem; font-weight: 600; color: var(--text-main); opacity: 0.7; }
.form { display: flex; flex-direction: column; gap: 0.5rem; }
.kv { display: grid; grid-template-columns: 100px 1fr; gap: 0.5rem; align-items: center; }
.kv2 { display: grid; grid-template-columns: 110px 1fr; gap: 0.5rem; align-items: center; }
.k { font-size: 0.8125rem; color: var(--text-main); opacity: 0.7; }
.inp { padding: 0.375rem 0.5rem; border: 1px solid var(--line); border-radius: 4px; background: var(--bg); color: var(--text-main); font-size: 0.8125rem; }
.inp.small { font-size: 0.75rem; }
.inp.mono { font-family: 'Courier New', monospace; }
.inp.area { min-height: 64px; resize: vertical; white-space: pre-wrap; }
.inp:focus { outline: none; border-color: var(--link); }
.btn_row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.btn { padding: 0.375rem 0.75rem; border: 1px solid var(--line); border-radius: 4px; background: var(--bg); color: var(--text-main); font-size: 0.8125rem; cursor: pointer; transition: all 0.2s; }
.btn:hover:not(:disabled):not(.disabled) { background: var(--hover); border-color: var(--link); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.disabled { opacity: 0.5; cursor: not-allowed; }
.btn.ghost { background: transparent; border-color: transparent; }
.btn.ghost:hover:not(:disabled) { background: var(--hover); border-color: var(--line); }
.btn.mini { padding: 0.25rem 0.5rem; font-size: 0.75rem; }
.btn.danger { border-color: var(--danger); color: var(--danger); }
.btn.danger:hover:not(:disabled) { background: var(--danger); color: white; }
.rules_list { display: flex; flex-direction: column; gap: 0.5rem; }
.list_header { font-size: 0.75rem; padding: 0.25rem 0; }
.tipline { padding: 0.25rem 0; }
.rules_box { max-height: 380px; overflow: auto; overscroll-behavior: contain; padding-right: 2px; }
.rule_item { padding: 0.75rem; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); display: flex; flex-direction: column; gap: 0.5rem; transition: all 0.2s; margin-bottom: 0.5rem; }
.rule_item.disabled { opacity: 0.6; }
.rule_head { display: flex; align-items: center; gap: 0.5rem; }
.rule_status { font-size: 1rem; }
.rule_name { flex: 1; font-weight: 600; font-size: 0.875rem; color: var(--text-main); }
.rule_id { font-size: 0.75rem; opacity: 0.5; }
.rule_meta { display: flex; gap: 0.75rem; flex-wrap: wrap; font-size: 0.75rem; }
.rule_actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.empty { padding: 1rem; text-align: center; font-size: 0.875rem; opacity: 0.6; }
.report { padding: 0.75rem; border: 1px solid var(--line); border-radius: 6px; background: var(--sidebar-bg); }
.report_title { font-size: 0.75rem; margin-bottom: 0.5rem; font-weight: 600; }
.rline { display: flex; gap: 0.75rem; align-items: center; padding: 0.25rem 0; font-size: 0.8125rem; flex-wrap: wrap; }
.mono { font-family: 'Courier New', monospace; }
.muted { opacity: 0.7; }
.smalltext { font-size: 0.75rem; }
.ok { color: var(--success, #10b981); }
.danger { color: var(--danger, #ef4444); }
.modal_mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); display: flex; align-items: center; justify-content: center; z-index: 9999; }
.modal { width: min(860px, calc(100vw - 24px)); max-height: 90vh; overflow: auto; border-radius: 10px; border: 1px solid var(--line); background: var(--editor-bg); padding: 0.9rem 1rem; }
.modal_head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 0 0.65rem 0; border-bottom: 1px solid var(--line); }
.modal_title { font-size: 0.95rem; color: var(--text); font-weight: 650; }
.modal_body { margin-top: 0.7rem; padding: 0; display: flex; flex-direction: column; gap: 0.75rem; }
.modal_actions { margin-top: 0.9rem; display: flex; justify-content: flex-end; gap: 0.5rem; padding: 0; border-top: none; }
.modal .k { font-size: 0.8rem; color: var(--text-secondary); opacity: 1; }
.modal .inp { width: 100%; padding: 0.55rem 0.65rem; border-radius: 8px; border: 1px solid var(--line); outline: none; background: transparent; color: var(--text); font-size: 0.85rem; }
.modal .inp.small { font-size: 0.82rem; }
.modal .inp.mono { font-family: var(--font-mono, 'Courier New', monospace); }
.modal .inp:focus { border-color: var(--selected); box-shadow: 0 2px 10px rgba(60, 105, 188, 0.12); }
.modal .btn { padding: 0.45rem 0.8rem; border-radius: 8px; border: 1px solid var(--line); background: transparent; color: var(--text-secondary); cursor: pointer; transition: all 0.15s var(--ease-smooth); font-size: 0.85rem; }
.modal .btn:hover:not(:disabled) { background: var(--selected-bg); border-color: var(--selected); color: var(--selected); }
.modal .btn:disabled { opacity: 0.6; cursor: not-allowed; }
.modal .btn.mini { padding: 0.35rem 0.6rem; font-size: 0.8rem; }
.modal .btn.ghost { background: transparent; border-color: transparent; color: var(--text-secondary); }
.modal .btn.ghost:hover:not(:disabled) { background: var(--selected-bg); border-color: var(--line); color: var(--text); }
.tipbox { padding: 8px; border: 1px dashed var(--line); border-radius: 8px; background: transparent; }
.radio { display: inline-flex; align-items: center; gap: 6px; font-size: 0.75rem; }
.check { display: inline-flex; align-items: center; gap: 8px; font-size: 0.75rem; }
</style>
