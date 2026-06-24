<template>
  <div class="panel">
    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.keywords') }}</div>
      <div class="row">
        <input
          class="inp"
          v-model="gate.state.query"
          :placeholder="t('rss.center.gate.params.placeholders.queryExample')"
          @keydown.enter.prevent="gate.actions.runSearch(true)"
        />
        <button
          class="btn"
          type="button"
          :disabled="!gate.state.query.trim()"
          @click="gate.actions.addFavoriteKeyword(gate.state.query)"
        >
          {{ t('rss.center.gate.params.actions.favoriteKeyword') }}
        </button>
      </div>

      <div v-if="gate.state.favoriteKeywords.length" class="chips">
        <div
          v-for="k in gate.state.favoriteKeywords"
          :key="k"
          class="chip_wrap"
          :class="{ active: active_keyword === k }"
          @mouseenter="on_keyword_hover(k)"
          @mouseleave="on_keyword_hover('')"
          @touchstart.stop="on_keyword_touch(k)"
        >
          <button
            class="chip"
            type="button"
            :title="k"
            @click="on_keyword_click(k)"
          >
            {{ k }}
          </button>

          <button
            class="chip_x"
            type="button"
            :aria-label="t('rss.center.gate.params.actions.removeKeyword')"
            :title="t('rss.center.gate.params.actions.removeKeyword')"
            @click.stop="remove_favorite_keyword(k)"
            @touchstart.stop.prevent="remove_favorite_keyword(k)"
          >
            ×
          </button>
        </div>

        <button
          class="chip danger"
          type="button"
          :title="t('rss.center.gate.params.actions.clearFavoriteKeywords')"
          @click="gate.actions.clearFavoriteKeywords"
        >
          {{ t('rss.center.gate.params.actions.clearFavoriteKeywords') }}
        </button>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.feedScope') }}</div>
      <div class="row">
        <label class="radio">
          <input type="radio" value="all" v-model="gate.state.feedScope" />
          {{ t('rss.center.gate.params.options.allFeeds') }}
        </label>
        <label class="radio">
          <input type="radio" value="selected" v-model="gate.state.feedScope" />
          {{ t('rss.center.gate.params.options.selectedFeeds') }}
        </label>
      </div>

      <div v-if="gate.state.feedScope === 'selected'" class="box">
        <div class="row">
          <input
            class="inp small"
            v-model="gate.state.feedFilter"
            :placeholder="t('rss.center.gate.params.placeholders.feedFilter')"
          />
          <button class="btn" type="button" @click="gate.actions.selectAllFeeds">
            {{ t('rss.center.gate.params.actions.selectAll') }}
          </button>
          <button class="btn" type="button" @click="gate.actions.clearFeeds">
            {{ t('rss.center.gate.params.actions.clear') }}
          </button>
        </div>

        <div class="list">
          <label v-for="f in gate.filteredFeeds" :key="f.feed_id" class="list-row">
            <input type="checkbox" :value="f.feed_id" v-model="gate.state.selectedFeedIds" />
            <span class="list-name">{{ f.title || f.url || f.feed_id }}</span>
          </label>
        </div>

        <div class="row">
          <button
            class="btn"
            type="button"
            :class="{ ok: gate.state.confirmedFeedIds.length > 0, pulse: gate.state.confirmPulse }"
            @click="gate.actions.confirmFeeds"
          >
            {{ t('rss.center.gate.params.actions.confirmSelection', { count: gate.state.selectedFeedIds.length }) }}
          </button>
          <div class="muted">
            {{ t('rss.center.gate.params.status.confirmedFeedsCount', { count: gate.state.confirmedFeedIds.length }) }}
          </div>
        </div>

        <div class="row">
          <input
            class="inp small"
            v-model="gate.state.groupName"
            :placeholder="t('rss.center.gate.params.placeholders.groupName')"
          />
          <button
            class="btn"
            type="button"
            :disabled="!gate.state.groupName.trim() || !gate.state.confirmedFeedIds.length"
            @click="gate.actions.saveGroup"
          >
            {{ t('rss.center.gate.params.actions.saveGroup') }}
          </button>
        </div>

        <div v-if="gate.state.subscribeGroups.length" class="chips">
          <button
            v-for="g in gate.state.subscribeGroups"
            :key="g.group_id"
            class="chip"
            type="button"
            :title="t('rss.center.gate.params.titles.loadGroup', { name: g.group_name, count: (g.feed_ids || []).length })"
            @click="gate.actions.applyGroup(g.group_id)"
          >
            {{ g.group_name }} ({{ (g.feed_ids || []).length }})
          </button>
          <button
            class="chip danger"
            type="button"
            :title="t('rss.center.gate.params.titles.clearAllGroups')"
            @click="gate.actions.clearGroups"
          >
            {{ t('rss.center.gate.params.actions.clearGroups') }}
          </button>
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.searchParams') }}</div>
      <div class="kv">
        <div class="k">{{ t('rss.center.gate.params.fields.days') }}</div>
        <select class="sel" v-model="gate.state.days">
          <option value="0">0</option>
          <option value="1">1</option>
          <option value="3">3</option>
          <option value="7">7</option>
          <option value="14">14</option>
          <option value="30">30</option>
          <option value="90">90</option>
        </select>

        <div class="k">{{ t('rss.center.gate.params.fields.startDate') }}</div>
        <input class="inp small" type="date" v-model="gate.state.startDate" />

        <div class="k">{{ t('rss.center.gate.params.fields.endDate') }}</div>
        <input class="inp small" type="date" v-model="gate.state.endDate" />

        <div class="k">{{ t('rss.center.gate.params.fields.limit') }}</div>
        <select class="sel" v-model="gate.state.limit">
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="80">80</option>
          <option value="200">200</option>
        </select>

        <div class="k">{{ t('rss.center.gate.params.fields.minScore') }}</div>
        <input class="inp small mono" type="number" step="0.01" min="0" max="1" v-model="gate.state.minScore" />

        <div class="k">{{ t('rss.center.gate.params.fields.strictLexical') }}</div>
        <label class="check">
          <input type="checkbox" v-model="gate.state.strictLexical" />
          {{ t('rss.center.gate.params.fields.strictLexicalLabel') }}
        </label>
      </div>

      <label class="check inline">
        <input type="checkbox" v-model="gate.state.onlyUnimported" />
        {{ t('rss.center.gate.params.fields.onlyUnimported') }}
      </label>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.targetLibrary') }}</div>
      <div class="row">
        <input
          class="inp mono"
          v-model="gate.state.libraryId"
          :placeholder="t('rss.center.gate.params.placeholders.libraryId')"
        />
      </div>

      <div class="row">
        <button class="btn" type="button" @click="gate.actions.loadLibraries">
          {{ t('rss.center.gate.params.actions.refreshLibraries') }}
        </button>
        <select
          class="sel"
          v-model="gate.state.libraryId"
          :title="t('rss.center.gate.params.options.chooseLibraryFromList')"
        >
          <option value="">{{ t('rss.center.gate.params.options.selectLibraryOptional') }}</option>
          <option v-for="l in gate.state.libraries" :key="l.library_id" :value="l.library_id">
            {{ l.library_name || l.library_id }} · {{ l.library_id }}
          </option>
        </select>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.importActions') }}</div>
      <div class="row">
        <button
          class="btn"
          type="button"
          :disabled="gate.state.importWorking || !gate.state.libraryId || !gate.selectedResults.length"
          @click="gate.actions.importSelected"
        >
          {{
            gate.state.importWorking
              ? t('rss.center.gate.params.actions.importing')
              : t('rss.center.gate.params.actions.importSelected', { count: gate.selectedResults.length })
          }}
        </button>
        <button class="btn" type="button" :disabled="!gate.displayResults.length" @click="gate.actions.toggleAllLoaded">
          {{
            gate.state.selectedKeys.length === gate.displayResults.length
              ? t('rss.center.gate.params.actions.unselectAllLoaded')
              : t('rss.center.gate.params.actions.selectAllLoaded', { count: gate.displayResults.length })
          }}
        </button>
      </div>

      <div v-if="gate.state.lastImportReport" class="report">
        <div>
          {{
            t('rss.center.gate.params.status.importDone', {
              imported: gate.state.lastImportReport.imported,
              skipped: gate.state.lastImportReport.skipped,
              failed: gate.state.lastImportReport.failed
            })
          }}
        </div>
        <div v-if="gate.state.lastImportReport.first_error" class="muted">
          {{
            t('rss.center.gate.params.status.firstImportError', {
              error: gate.state.lastImportReport.first_error
            })
          }}
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.hardDelete') }}</div>
      <div class="row">
        <button class="btn danger" type="button" :disabled="!gate.selectedResults.length" @click="gate.actions.deleteSelected">
          {{ t('rss.center.gate.params.actions.deleteSelected', { count: gate.selectedResults.length }) }}
        </button>
        <button class="btn danger" type="button" :disabled="!gate.displayResults.length" @click="gate.actions.deleteAllResults">
          {{ t('rss.center.gate.params.actions.deleteAllResults', { count: gate.displayResults.length }) }}
        </button>
      </div>

      <div v-if="gate.state.lastDeleteReport" class="report">
        <div>
          {{
            t('rss.center.gate.params.status.deleteDone', {
              deleted: gate.state.lastDeleteReport.deleted,
              skipped: gate.state.lastDeleteReport.skipped,
              failed: gate.state.lastDeleteReport.failed
            })
          }}
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.manualFetchDue') }}</div>
      <div class="row">
        <input class="inp small mono" type="number" min="0" max="43200" v-model="gate.state.autoFetchIntervalMinutes" />
        <button class="btn" type="button" :disabled="gate.state.fetchDueWorking" @click="gate.actions.fetchDueNow">
          {{
            gate.state.fetchDueWorking
              ? t('rss.center.gate.params.actions.fetching')
              : t('rss.center.gate.params.actions.fetchDueNow')
          }}
        </button>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.rssAutoFetch') }}</div>
      <label class="check">
        <input type="checkbox" v-model="gate.state.rssAutoFetchEnabled" />
        {{ t('rss.center.gate.params.actions.enableRssAutoFetch') }}
      </label>
      <div class="kv">
        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoFetchIntervalMinutes') }}</div>
        <input class="inp small mono" type="number" min="1" max="43200" v-model="gate.state.rssAutoFetchIntervalMinutes" />

        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoFetchLimitEntries') }}</div>
        <input class="inp small mono" type="number" min="1" max="200" v-model="gate.state.rssAutoFetchLimitEntries" />
      </div>
      <div class="row">
        <button class="btn" type="button" :disabled="gate.state.rssAutoFetchWorking" @click="gate.actions.saveRssAutoFetchConfig">
          {{ t('rss.center.gate.params.actions.save') }}
        </button>
        <button class="btn" type="button" :disabled="gate.state.rssAutoFetchWorking" @click="gate.actions.runRssAutoFetchNow">
          {{ t('rss.center.gate.params.actions.runNow') }}
        </button>
        <button class="btn" type="button" :disabled="gate.state.rssAutoFetchWorking" @click="gate.actions.loadRssAutoFetchConfig">
          {{ t('rss.center.gate.params.actions.refreshStatus') }}
        </button>
        <button class="btn danger" type="button" :disabled="gate.state.rssAutoFetchWorking" @click="gate.actions.deleteRssAutoFetchConfig">
          {{ t('rss.center.gate.params.actions.delete') }}
        </button>
      </div>
      <div v-if="gate.state.rssAutoFetchStatus" class="report">
        <div class="muted">
          {{
            t('rss.center.gate.params.status.rssAutoFetchStatus', {
              enabled: gate.state.rssAutoFetchStatus.enabled
                ? t('rss.center.gate.params.status.on')
                : t('rss.center.gate.params.status.off'),
              interval: gate.state.rssAutoFetchStatus.interval_minutes,
              limit: gate.state.rssAutoFetchStatus.limit_entries
            })
          }}
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="h">{{ t('rss.center.gate.params.sections.rssAutoCleanup') }}</div>
      <label class="check">
        <input type="checkbox" v-model="gate.state.rssAutoCleanupEnabled" />
        {{ t('rss.center.gate.params.actions.enableRssAutoCleanup') }}
      </label>

      <div class="kv">
        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoCleanupKeepDays') }}</div>
        <input class="inp small mono" type="number" min="1" max="365" v-model="gate.state.rssAutoCleanupKeepDays" />

        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoCleanupIntervalHours') }}</div>
        <input class="inp small mono" type="number" min="1" max="168" v-model="gate.state.rssAutoCleanupIntervalHours" />

        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoCleanupRebuildIndex') }}</div>
        <label class="check">
          <input type="checkbox" v-model="gate.state.rssAutoCleanupRebuildIndex" />
          {{ t('rss.center.gate.params.fields.rebuildEmbeddings') }}
        </label>

        <div class="k">{{ t('rss.center.gate.params.fields.rssAutoCleanupDeleteLogsBeforeDays') }}</div>
        <input class="inp small mono" type="number" min="0" max="3650" v-model="gate.state.rssAutoCleanupDeleteLogsBeforeDays" />
      </div>

      <div class="row">
        <button class="btn" type="button" :disabled="gate.state.rssAutoCleanupWorking" @click="gate.actions.saveRssAutoCleanupConfig">
          {{ t('rss.center.gate.params.actions.save') }}
        </button>
        <button class="btn" type="button" :disabled="gate.state.rssAutoCleanupWorking" @click="gate.actions.runRssAutoCleanupNow">
          {{ t('rss.center.gate.params.actions.runNow') }}
        </button>
        <button class="btn" type="button" :disabled="gate.state.rssAutoCleanupWorking" @click="gate.actions.loadRssAutoCleanupConfig">
          {{ t('rss.center.gate.params.actions.refreshStatus') }}
        </button>
        <button class="btn danger" type="button" :disabled="gate.state.rssAutoCleanupWorking" @click="gate.actions.deleteRssAutoCleanupConfig">
          {{ t('rss.center.gate.params.actions.delete') }}
        </button>
      </div>

      <div v-if="gate.state.rssAutoCleanupStatus" class="report">
        <div class="muted">
          {{
            t('rss.center.gate.params.status.rssAutoCleanupStatus', {
              enabled: gate.state.rssAutoCleanupStatus.enabled
                ? t('rss.center.gate.params.status.on')
                : t('rss.center.gate.params.status.off'),
              keepDays: gate.state.rssAutoCleanupStatus.keep_days,
              intervalHours: gate.state.rssAutoCleanupStatus.interval_hours,
              rebuildIndex: gate.state.rssAutoCleanupStatus.rebuild_index
                ? t('rss.center.gate.params.status.on')
                : t('rss.center.gate.params.status.off'),
              nextRunAt: String(gate.state.rssAutoCleanupStatus.next_run_at || '')
            })
          }}
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <div class="row row-between">
        <div class="h">{{ t('rss.center.gate.params.sections.spamRules') }}</div>
        <div v-if="spamRulesCount > 0" class="muted smalltext">
          {{ t('rss.center.gate.params.status.spamRulesCount', { count: spamRulesCount }) }}
        </div>
      </div>

      <div class="row">
        <button class="btn" type="button" :disabled="gate.state.spamWorking" @click="gate.actions.loadSpamRules">
          {{
            gate.state.spamWorking
              ? t('rss.center.gate.params.actions.loading')
              : t('rss.center.gate.params.actions.loadSpamRules')
          }}
        </button>

        <button v-if="spamRulesCount > 0" class="btn" type="button" @click="toggleSpamRulesOpen">
          {{
            spamRulesOpen
              ? t('rss.center.gate.params.actions.collapseList')
              : t('rss.center.gate.params.actions.expandList')
          }}
        </button>
      </div>

      <div v-if="spamRulesCount > 0 && !spamRulesOpen" class="muted smallhint">
        {{ t('rss.center.gate.params.status.spamRulesLoadedHint', { count: spamRulesCount }) }}
      </div>

      <div v-if="spamRulesCount > 0 && spamRulesOpen" class="report rulesbox">
        <div v-for="r in gate.state.spamRules" :key="r.rule_id || r.ruleid" class="rule-row">
          <span class="mono">{{ String(r.scope || '') }}</span>
          <span class="mono">{{ String(r.domain || r.url || r.feed_id || r.feedid || '') }}</span>
          <button class="btn mini danger" type="button" @click="gate.actions.deleteSpamRule(r.rule_id || r.ruleid)">
            {{ t('rss.center.gate.params.actions.delete') }}
          </button>
        </div>
      </div>
    </div>

    <div class="hr"></div>

    <div class="section">
      <RssAutoRules
        v-bind="{
          query: String(gate.state.query || ''),
          feed_ids: Array.isArray(gate.state.confirmedFeedIds) ? gate.state.confirmedFeedIds : [],
          days: Number(gate.state.days),
          start_date: String(gate.state.startDate || ''),
          end_date: String(gate.state.endDate || ''),
          limit: Number(gate.state.limit),
          min_score: Number(gate.state.minScore),
          strict_lexical: !!gate.state.strictLexical,
          library_id: String(gate.state.libraryId || ''),
          callTool: gate.callTool
        }"
        @toast="(x) => gate.toast(x?.message || String(x || ''), x?.type || 'info')"
        @refresh="gate.actions.onAutoRulesRefresh"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import RssAutoRules from '../RssAutoRules.vue'

const props = defineProps({
  gate: { type: Object, required: true }
})

const gate = props.gate
const { t } = useI18n()

const spamRulesOpen = ref(false)
const spamRulesCount = computed(() => (Array.isArray(gate?.state?.spamRules) ? gate.state.spamRules.length : 0))

function toggleSpamRulesOpen() {
  spamRulesOpen.value = !spamRulesOpen.value
}

const active_keyword = ref('')

function on_keyword_hover(k) {
  active_keyword.value = k || ''
}

function on_keyword_touch(k) {
  active_keyword.value = k || ''
}

function on_keyword_click(k) {
  gate.state.query = k
  active_keyword.value = k || ''
}

function _is_ok(r) {
  if (!r || typeof r !== 'object') return false
  if (r.success === true) return true
  if (String(r.status || '').toLowerCase() === 'success') return true
  return false
}

function _uniq_keep_order(arr) {
  const out = []
  const seen = new Set()
  for (const x of Array.isArray(arr) ? arr : []) {
    const s = String(x || '').trim()
    if (!s || seen.has(s)) continue
    seen.add(s)
    out.push(s)
  }
  return out
}

async function remove_favorite_keyword(k) {
  const key = String(k || '').trim()
  if (!key) return

  const cur = Array.isArray(gate?.state?.favoriteKeywords) ? gate.state.favoriteKeywords : []
  const next = _uniq_keep_order(cur.filter((x) => String(x) !== key))

  const prev = cur.slice()
  gate.state.favoriteKeywords = next
  if (active_keyword.value === key) active_keyword.value = ''

  try {
    const r = await gate.callTool('nisb_rss_gate_prefs_set', {
      favorite_keywords: next
    })
    if (!_is_ok(r)) {
      gate.state.favoriteKeywords = prev
      gate.toast?.(t('rss.center.gate.params.messages.removeKeywordFailedNoSuccess'), 'error')
      return
    }
    gate.toast?.(t('rss.center.gate.params.messages.removeKeywordSuccess', { keyword: key }), 'success')
  } catch (e) {
    gate.state.favoriteKeywords = prev
    gate.toast?.(
      t('rss.center.gate.params.messages.removeKeywordFailedWithError', {
        error: e?.message || String(e)
      }),
      'error'
    )
  }
}

onMounted(async () => {
  try {
    await gate.actions.loadRssAutoCleanupConfig()
  } catch {}
})
</script>

<style scoped>
.panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
  padding: 0;
  color: var(--text-main, var(--text));
  overflow-x: hidden;
}

.section {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.56rem;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.04);
}

.section:hover {
  border-color: color-mix(in srgb, var(--selected) 18%, var(--line));
}

.h {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.82rem;
  font-weight: 810;
  line-height: 1.35;
  letter-spacing: -0.005em;
  overflow-wrap: break-word;
}

.hr {
  display: none;
}

.row {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.46rem;
}

.row-between {
  justify-content: space-between;
}

.smalltext,
.smallhint {
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.kv {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(88px, 0.45fr) minmax(0, 1fr);
  gap: 0.48rem 0.62rem;
  align-items: center;
}

.k {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 720;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.inp,
.sel {
  width: 100%;
  min-width: 0;
  min-height: 33px;
  box-sizing: border-box;
  padding: 0.48rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  outline: none;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: inherit;
  font-size: 0.8rem;
  line-height: 1.35;
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease;
}

.inp.small {
  min-height: 33px;
  font-size: 0.8rem;
}

.inp::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.inp:focus,
.sel:focus {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 84%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.07);
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

.btn {
  min-height: 31px;
  box-sizing: border-box;
  padding: 0 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled) {
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

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.btn.mini {
  min-height: 27px;
  padding: 0 0.52rem;
  border-radius: 9px;
  font-size: 0.72rem;
}

.btn.ok,
.ok {
  border-color: rgba(22, 163, 74, 0.4);
  background: rgba(22, 163, 74, 0.08);
  color: #16a34a;
}

.btn.danger,
.chip.danger {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.btn.danger:hover:not(:disabled),
.chip.danger:hover {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.chips {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.38rem;
}

.chip_wrap {
  position: relative;
  min-width: 0;
  display: inline-flex;
  align-items: center;
}

.chip {
  max-width: 190px;
  min-height: 25px;
  box-sizing: border-box;
  padding: 0 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 730;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.chip:hover,
.chip_wrap.active .chip {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
}

.chip_x {
  position: absolute;
  top: -7px;
  right: -7px;
  width: 17px;
  height: 17px;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, rgba(0, 0, 0, 0.34)),
      color-mix(in srgb, var(--sidebar-bg) 72%, rgba(0, 0, 0, 0.42))
    );
  color: var(--text-main, var(--text));
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  line-height: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transform: scale(0.92);
  transition:
    opacity 0.15s ease,
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.chip_wrap:hover .chip_x,
.chip_wrap.active .chip_x {
  opacity: 1;
  pointer-events: auto;
  transform: scale(1);
}

.chip_x:hover {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.18);
  color: #ef4444;
}

.radio,
.check {
  min-width: 0;
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.34rem 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--editor-bg) 50%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.78rem;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.radio:hover,
.check:hover {
  border-color: color-mix(in srgb, var(--selected) 26%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, var(--editor-bg));
  color: var(--selected);
}

.radio input,
.check input {
  flex: 0 0 auto;
  accent-color: var(--selected);
}

.check.inline {
  align-self: flex-start;
}

.box {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.62rem;
  padding: 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
}

.list {
  min-width: 0;
  max-height: 230px;
  display: grid;
  align-content: start;
  gap: 0.26rem;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.38rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 50%, transparent);
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.list-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.48rem;
  padding: 0.42rem 0.48rem;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.list-row:hover {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, var(--editor-bg));
  color: var(--selected);
}

.list-row input {
  flex: 0 0 auto;
  accent-color: var(--selected);
}

.list-name {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.79rem;
  font-weight: 680;
  line-height: 1.32;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pulse {
  animation: pulse 0.62s ease-out;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.035);
  }
}

.report {
  min-width: 0;
  padding: 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-main, var(--text));
  font-size: 0.79rem;
  line-height: 1.48;
  overflow-wrap: break-word;
}

.muted {
  color: var(--text-secondary);
  line-height: 1.45;
  overflow-wrap: break-word;
}

.rule-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(72px, 0.34fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.48rem;
  padding: 0.36rem 0;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
}

.rule-row:last-child {
  border-bottom: 0;
}

.rule-row > span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.rulesbox {
  max-height: 170px;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.list::-webkit-scrollbar,
.rulesbox::-webkit-scrollbar {
  width: 8px;
}

.list::-webkit-scrollbar-thumb,
.rulesbox::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.list::-webkit-scrollbar-thumb:hover,
.rulesbox::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--text-secondary) 62%, transparent);
}

@media (max-width: 760px) {
  .section {
    padding: 0.66rem;
    border-radius: 14px;
  }

  .kv {
    grid-template-columns: 1fr;
    gap: 0.34rem;
  }

  .k {
    margin-top: 0.16rem;
  }

  .row {
    align-items: stretch;
  }

  .row > .inp,
  .row > .sel {
    flex: 1 1 100%;
  }

  .row > .btn {
    flex: 1 1 auto;
  }

  .rule-row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .rule-row .btn {
    width: 100%;
  }
}

@media (max-width: 520px) {
  .panel {
    gap: 0.58rem;
  }

  .section {
    padding: 0.58rem;
    border-radius: 13px;
  }

  .row,
  .chips {
    align-items: stretch;
  }

  .btn,
  .chip,
  .radio,
  .check {
    width: 100%;
    white-space: normal;
  }

  .chip_wrap {
    width: 100%;
  }

  .chip {
    max-width: none;
  }

  .chip_x {
    opacity: 1;
    pointer-events: auto;
    transform: scale(1);
  }
}
</style>

