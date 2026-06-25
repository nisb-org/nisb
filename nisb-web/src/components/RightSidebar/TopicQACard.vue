<!-- /opt/mcp-gateway/nisb-web/src/components/RightSidebar/TopicQACard.vue -->
<template>
  <div class="qa-card" :class="{ expanded: expanded }">
    <div class="qa-title-row">
      <div class="qa-title">{{ t('rightSidebar.topicQA.title') }}</div>
      <div class="qa-actions">
        <button class="mini-btn ghost" :disabled="!ctxReady" @click="toggleExpand()">
          {{ expanded ? t('rightSidebar.topicQA.actions.collapse') : t('rightSidebar.topicQA.actions.expand') }}
        </button>
        <button
          class="mini-btn ghost"
          :disabled="qaLoading || !ctxReady || !qaIndex.rootIds.length"
          @click="expandedRootSet.size > 0 ? collapseAllRoots() : expandAllRoots()"
        >
          {{ expandedRootSet.size > 0
            ? t('rightSidebar.topicQA.actions.collapseAll')
            : t('rightSidebar.topicQA.actions.expandAll') }}
        </button>
        <button class="mini-btn" :disabled="qaLoading || !ctxReady" @click="refreshQA()">
          {{ t('rightSidebar.topicQA.actions.refresh') }}
        </button>
      </div>
    </div>

    <div v-if="!ctxReady" class="muted">
      {{ t('rightSidebar.topicQA.hints.contextRequired') }}
    </div>

    <div v-else class="qa-ask-row">
      <div
        class="scope-seg"
        :title="t('rightSidebar.topicQA.scope.segmentTitle')"
      >
        <button class="seg-btn" :class="{ active: qaScope === 'doc' }" @click="setScope('doc')">
          {{ t('rightSidebar.topicQA.scope.doc') }}
        </button>
        <button class="seg-btn" :class="{ active: qaScope === 'library' }" @click="setScope('library')">
          {{ t('rightSidebar.topicQA.scope.library') }}
        </button>
        <button class="seg-btn" :class="{ active: qaScope === 'global' }" @click="setScope('global')">
          {{ t('rightSidebar.topicQA.scope.global') }}
        </button>
      </div>

      <input v-model="qaQuestion" class="qa-input" :placeholder="askPlaceholder" @keydown.enter.prevent="askQA()" />
      <button class="mini-btn" :disabled="qaLoading || !qaQuestion.trim()" @click="askQA()">
        {{ qaLoading ? t('rightSidebar.topicQA.actions.processing') : t('rightSidebar.topicQA.actions.ask') }}
      </button>
    </div>

    <div v-if="qaScope !== 'doc' && ctxReady" class="muted qa-scope-hint">
      {{ t('rightSidebar.topicQA.hints.scopeWindow', { scope: qaScope }) }}
    </div>

    <div v-if="ctxReady && qaScope !== 'doc'" class="muted qa-scope-hint qa-scope-stats">
      {{ t('rightSidebar.topicQA.hints.loadedStats', { count: qaListLimit, scanned: qaSegScanned, total: qaSegTotal }) }} ·
      <button class="mini-btn ghost" :disabled="qaLoading" @click="resetHistoryWindow()">
        {{ t('rightSidebar.topicQA.actions.backToRecent') }}
      </button>
    </div>

    <div v-if="qaError" class="muted qa-error">{{ qaError }}</div>

    <div v-if="qaIndex.visibleItems.length" class="qa-list">
      <div
        v-for="view in qaIndex.visibleItems"
        :key="view.qa_id"
        class="qa-item"
        :class="{
          reply: !view.isRoot,
          root: view.isRoot,
          collapsed: view.isRoot && !isRootExpanded(view.qa_id)
        }"
        :style="{ marginLeft: indentPx(view.depth) }"
        :data-qa-id="view.qa_id"
      >
        <div class="qa-q-row">
          <div class="qa-q">
            <button
              v-if="view.isRoot"
              class="qa-caret"
              :title="isRootExpanded(view.qa_id) ? t('rightSidebar.topicQA.actions.collapseThread') : t('rightSidebar.topicQA.actions.expandThread')"
              @click.stop="toggleRoot(view.qa_id)"
            >
              {{ isRootExpanded(view.qa_id) ? '▼' : '▶' }}
            </button>

            <span v-if="!view.isRoot" class="reply-tag muted">{{ t('rightSidebar.topicQA.labels.followUpTag') }}</span>

            <span
              v-if="view.isRoot"
              class="root-meta muted"
              :title="t('rightSidebar.topicQA.meta.threadTitle', { value: String(view.node?.thread_id || '') })"
            >
              {{ t('rightSidebar.topicQA.meta.threadSummary', { count: countReplies(view.qa_id) }) }}
            </span>

            {{ view.node.question || view.node.response || '' }}
          </div>

          <div class="qa-q-actions">
            <button
              class="qa-del"
              :title="t('rightSidebar.topicQA.actions.delete')"
              :disabled="qaLoading"
              @click="deleteQA(view.node)"
            >
              ×
            </button>
          </div>
        </div>

        <div
          class="qa-a"
          v-show="!view.isRoot || isRootExpanded(view.qa_id)"
        >{{ view.node.answer || view.node.response || '' }}</div>

        <div
          class="qa-meta muted"
          v-if="(view.node?.params || view.node?.llm) && (!view.isRoot || isRootExpanded(view.qa_id))"
        >
          <span class="qa-badge" :class="badgeClass(view.node)">{{ badgeText(view.node) }}</span>

          <span class="qa-meta-text">
            {{ t('rightSidebar.topicQA.meta.mode', { value: String(view.node?.params?.answer_mode || view.node?.mode_used || "unknown") }) }}
            · {{ t('rightSidebar.topicQA.meta.model', { value: String(view.node?.params?.model || view.node?.llm?.model || "unknown") }) }}
            · {{ t('rightSidebar.topicQA.meta.llmOk', { value: String(view.node?.llm?.ok) }) }}
          </span>

          <span v-if="view.node?.params?.search_query || view.node?.evidence_query" class="qa-meta-text">
            · {{ t('rightSidebar.topicQA.meta.search', { value: String(view.node?.params?.search_query_used || view.node?.evidence_query || '') }) }}
          </span>

          <span v-if="view.node?.params?.store_scope" class="qa-meta-text">
            · {{ t('rightSidebar.topicQA.meta.storeScope', { value: String(view.node?.params?.store_scope) }) }}
          </span>

          <span v-if="view.node?.params?.evidence_scope || view.node?.rag_mode" class="qa-meta-text">
            · {{ t('rightSidebar.topicQA.meta.evidenceScope', { value: String(view.node?.params?.evidence_scope || view.node?.rag_mode || '') }) }}
          </span>

          <template v-if="view.isRoot && getLinkedFrom(view.node)">
            <span class="qa-meta-text">
              · {{ t('rightSidebar.topicQA.meta.linkedFrom', { value: String(getLinkedFrom(view.node)?.from_store_scope || '') }) }}
            </span>
            <button class="mini-btn ghost" :disabled="qaLoading" @click="goToLinkedFrom(view.node)">
              {{ t('rightSidebar.topicQA.actions.traceSource') }}
            </button>
          </template>

          <button class="mini-btn ghost" :disabled="qaLoading" @click="openFollowUp(view.node)">
            {{ t('rightSidebar.topicQA.actions.followUp') }}
          </button>

          <button
            v-if="view.isRoot && qaScope === 'doc'"
            class="mini-btn ghost"
            :disabled="qaLoading"
            @click="handoffElevate('library', view.node)"
          >
            {{ t('rightSidebar.topicQA.actions.elevateToLibrary') }}
          </button>

          <button
            v-if="view.isRoot && (qaScope === 'doc' || qaScope === 'library')"
            class="mini-btn ghost"
            :disabled="qaLoading"
            @click="handoffElevate('global', view.node)"
          >
            {{ t('rightSidebar.topicQA.actions.elevateToGlobal') }}
          </button>

          <button class="mini-btn ghost" :disabled="qaLoading || !hasEvidence(view.node)" @click="toggleEvidence(view.qa_id)">
            {{ evidenceOpenId === view.qa_id ? t('rightSidebar.topicQA.actions.collapseEvidence') : t('rightSidebar.topicQA.actions.evidence') }}
          </button>

          <button
            v-if="(view.node?.llm && view.node.llm.ok === false) || view.node?.params?.search_query || view.node?.evidence_query"
            class="mini-btn ghost"
            @click="toggleDebug(view.qa_id)"
          >
            {{ debugOpenId === view.qa_id ? t('rightSidebar.topicQA.actions.collapse') : t('rightSidebar.topicQA.actions.details') }}
          </button>

          <button
            v-if="(view.node?.llm && view.node.llm.ok === false) || view.node?.params?.search_query || view.node?.evidence_query"
            class="mini-btn ghost"
            @click="copyDebug(view.node)"
          >
            {{ t('rightSidebar.topicQA.actions.copy') }}
          </button>
        </div>

        <div v-if="followUpOpenId === view.qa_id" class="qa-followup">
          <input
            v-model="followUpText"
            class="qa-input"
            :placeholder="t('rightSidebar.topicQA.followUp.placeholder')"
            @keydown.enter.prevent="askFollowUp(view.qa_id)"
          />
          <button class="mini-btn" :disabled="qaLoading || !followUpText.trim()" @click="askFollowUp(view.qa_id)">
            {{ qaLoading ? t('rightSidebar.topicQA.actions.processing') : t('rightSidebar.topicQA.actions.send') }}
          </button>
          <button class="mini-btn ghost" :disabled="qaLoading" @click="closeFollowUp()">
            {{ t('rightSidebar.topicQA.actions.cancel') }}
          </button>
        </div>

        <div v-if="evidenceOpenId === view.qa_id" class="qa-evidence">
          <div class="qa-evidence-title muted">{{ t('rightSidebar.topicQA.evidence.title') }}</div>

          <div v-if="!hasEvidence(view.node)" class="muted">
            {{ t('rightSidebar.topicQA.evidence.empty') }}
          </div>

          <div v-else class="qa-evidence-list">
            <div
              v-for="(ev, idx) in (view.node.evidence || [])"
              :key="view.qa_id + ':ev:' + idx"
              class="qa-evidence-item"
            >
              <div class="qa-evidence-meta muted">
                <span class="pill">{{ formatRel(ev) }}</span>
                <span class="muted">{{ t('rightSidebar.topicQA.evidence.libraryShort') }} {{ shortId(ev?.library_id) }}</span>
                <span class="muted">{{ t('rightSidebar.topicQA.evidence.docShort') }} {{ shortId(ev?.doc_id) }}</span>
                <span class="muted">{{ t('rightSidebar.topicQA.evidence.spanShort') }} {{ normalizeSpanIndex(ev) ?? '?' }}</span>
                <span v-if="ev?.doc_title" class="muted">· {{ String(ev.doc_title) }}</span>
              </div>

              <div class="qa-evidence-text">{{ String(ev?.excerpt || '') }}</div>

              <div class="qa-evidence-actions">
                <button
                  class="mini-btn ghost"
                  :disabled="normalizeSpanIndex(ev) === null"
                  @click="jumpToSpan(normalizeSpanIndex(ev), ev?.library_id, ev?.doc_id)"
                >
                  {{ t('rightSidebar.topicQA.actions.jump') }}
                </button>

                <button class="mini-btn ghost" :disabled="!String(ev?.excerpt || '').trim()" @click="copyText(ev?.excerpt)">
                  {{ t('rightSidebar.topicQA.actions.copy') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="debugOpenId === view.qa_id" class="qa-debug">
          <div v-if="view.node?.params?.search_query || view.node?.evidence_query" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.searchQuery') }}</div>
            <div class="qa-debug-v">{{ safeJson(view.node?.params?.search_query || view.node?.evidence_query) }}</div>
          </div>

          <div v-if="view.node?.thread_id || view.node?.group_id" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.threadId') }}</div>
            <div class="qa-debug-v">{{ String(view.node.thread_id || view.node.group_id || '') }}</div>
          </div>

          <div v-if="view.node?.parent_qa_id" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.parentQaId') }}</div>
            <div class="qa-debug-v">{{ String(view.node.parent_qa_id) }}</div>
          </div>

          <div v-if="view.node?.depth !== undefined" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.depth') }}</div>
            <div class="qa-debug-v">{{ String(view.node.depth) }}</div>
          </div>

          <div v-if="view.node?.debug?.query_dbg" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.queryDbg') }}</div>
            <div class="qa-debug-v">{{ safeJson(view.node.debug.query_dbg) }}</div>
          </div>

          <div v-if="view.node?.debug?.followup_dbg" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.followupDbg') }}</div>
            <div class="qa-debug-v">{{ safeJson(view.node.debug.followup_dbg) }}</div>
          </div>

          <div v-if="view.node?.llm?.error" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.llmError') }}</div>
            <div class="qa-debug-v">{{ String(view.node.llm.error) }}</div>
          </div>

          <div v-if="view.node?.llm?.raw_preview" class="qa-debug-row">
            <div class="qa-debug-k">{{ t('rightSidebar.topicQA.debug.rawPreview') }}</div>
            <div class="qa-debug-v pre">{{ String(view.node.llm.raw_preview) }}</div>
          </div>
        </div>

        <div v-if="Array.isArray(view.node.citations) && view.node.citations.length && (!view.isRoot || isRootExpanded(view.qa_id))" class="qa-ev">
          <div class="qa-ev-title muted">{{ t('rightSidebar.topicQA.citations.title') }}</div>
          <div class="qa-ev-list">
            <button
              v-for="(c, idx) in view.node.citations"
              :key="view.qa_id + ':c:' + idx"
              class="qa-ev-btn"
              :disabled="normalizeCitation(c).spanIndex === null"
              @click="jumpToCitation(c)"
              :title="citationTitle(c)"
            >
              <template v-if="normalizeCitation(c).spanIndex === null">
                {{ t('rightSidebar.topicQA.citations.jumpUnknownSpan') }}
              </template>
              <template v-else>
                <span v-if="normalizeCitation(c).libraryId && normalizeCitation(c).docId">
                  {{
                    t('rightSidebar.topicQA.citations.jumpWithIds', {
                      libraryId: shortId(normalizeCitation(c).libraryId),
                      docId: shortId(normalizeCitation(c).docId),
                      spanIndex: normalizeCitation(c).spanIndex
                    })
                  }}
                </span>
                <span v-else>
                  {{ t('rightSidebar.topicQA.citations.jumpSpan', { spanIndex: normalizeCitation(c).spanIndex }) }}
                </span>
              </template>
            </button>
          </div>
        </div>
      </div>

      <div v-if="ctxReady && qaScope !== 'doc' && qaHasMoreSegments" class="qa-loadmore-row">
        <button class="mini-btn" :disabled="qaLoading" @click="loadMoreHistory()">
          {{ qaLoading ? t('rightSidebar.topicQA.actions.loading') : t('rightSidebar.topicQA.actions.loadMoreHistory') }}
        </button>
      </div>

      <div v-else-if="ctxReady && qaScope !== 'doc' && !qaHasMoreSegments" class="muted qa-history-end">
        {{ t('rightSidebar.topicQA.hints.historyReachedEarliest') }}
      </div>
    </div>

    <div v-else-if="ctxReady" class="muted qa-empty">
      {{ t('rightSidebar.topicQA.hints.empty') }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLibrarySearchStore } from '../../stores/librarySearch'
import { useMCP } from '../../composables/useMCP'

const props = defineProps({ expanded: { type: Boolean, default: false } })
const emit = defineEmits(['toggleExpand'])

const { t } = useI18n()
const librarySearch = useLibrarySearchStore()
const { callTool } = useMCP()

const ANSWER_LANG_SETTINGS_LS_KEY = 'nisb_settings_v2'

function normalizeAnswerLangFromLocale(input) {
  const raw = String(input || '').trim().toLowerCase()
  if (!raw) return ''
  if (raw === 'zh' || raw === 'zh-cn' || raw === 'zh_hans') return 'zh'
  if (raw === 'en' || raw === 'en-us' || raw === 'en_us') return 'en'
  return ''
}

function detectQuestionAnswerLang(question) {
  const text = String(question || '').trim()
  if (!text) return ''

  const hasCJK = /[\u4e00-\u9fff]/.test(text)
  const hasKana = /[\u3040-\u30ff]/.test(text)
  const hasLatin = /[A-Za-z]/.test(text)

  if (hasLatin && !hasCJK && !hasKana) return 'en'
  if (hasCJK) return 'zh'

  return ''
}

function resolvePreferredAnswerLang(question) {
  const fromQuestion = detectQuestionAnswerLang(question)
  if (fromQuestion) return fromQuestion

  try {
    const saved = JSON.parse(localStorage.getItem(ANSWER_LANG_SETTINGS_LS_KEY) || '{}')
    const fromLocale = normalizeAnswerLangFromLocale(saved?.locale)
    if (fromLocale) return fromLocale
  } catch {}

  return 'zh'
}

function getGlobalReader() {
  return window.nisbReaderState || window.__nisbReaderState || null
}

async function callToolCompat(primaryName, legacyName, args, opts) {
  try {
    return await callTool(primaryName, args, opts)
  } catch (e) {
    const msg = String(e?.message || e || '')
    if (legacyName && /not found|unknown tool|tool/i.test(msg)) return await callTool(legacyName, args, opts)
    throw e
  }
}

function normalizeSpanIndex(c) {
  if (!c || typeof c !== 'object') return null
  const v = c.span_index ?? c.spanIndex ?? c.span_id ?? c.spanId ?? c.spanindex ?? c.span ?? null
  const n = v === null || v === undefined ? null : Number(v)
  return Number.isFinite(n) ? n : null
}

function normalizeCitation(c) {
  const spanIndex = normalizeSpanIndex(c)
  const lib = c?.library_id ?? c?.libraryId ?? c?.library ?? null
  const doc = c?.doc_id ?? c?.docId ?? c?.doc ?? null
  const libraryId = lib ? String(lib) : null
  const docId = doc ? String(doc) : null
  return { libraryId, docId, spanIndex }
}

function shortId(s) {
  const t0 = String(s || '')
  if (!t0) return ''
  if (t0.length <= 10) return t0
  return t0.slice(0, 5) + '\u2026' + t0.slice(-3)
}

function citationTitle(c) {
  const x = normalizeCitation(c)
  const quote = String(c?.quote || '').trim()
  const note = String(c?.note || '').trim()
  const parts = []
  if (x.libraryId) parts.push(`lib=${x.libraryId}`)
  if (x.docId) parts.push(`doc=${x.docId}`)
  if (Number.isFinite(x.spanIndex)) parts.push(`span=${x.spanIndex}`)
  if (quote) parts.push(`quote=${quote.slice(0, 80)}`)
  if (note) parts.push(`note=${note.slice(0, 80)}`)
  return parts.join(' | ')
}

const qaLoading = ref(false)
const qaError = ref('')
const qaQuestion = ref('')
const qaRawItems = ref([])
const expandedRootSet = ref(new Set())
const debugOpenId = ref('')
const followUpOpenId = ref('')
const followUpText = ref('')
const evidenceOpenId = ref('')

const qaScope = ref('doc')

const qaListLimit = ref(120)
const qaListMaxSegments = ref(12)
const qaHasMoreSegments = ref(false)
const qaSegTotal = ref(0)
const qaSegScanned = ref(0)

const askPlaceholder = computed(() => {
  if (qaScope.value === 'doc') return t('rightSidebar.topicQA.placeholders.askDoc')
  if (qaScope.value === 'library') return t('rightSidebar.topicQA.placeholders.askLibrary')
  return t('rightSidebar.topicQA.placeholders.askGlobal')
})

function getLibraryId() {
  return (
    librarySearch?.libraryId?.value ||
    librarySearch?.libraryId ||
    librarySearch?.context?.libraryId ||
    librarySearch?.context?.library_id ||
    ''
  )
}

function getDocId() {
  return (
    librarySearch?.docId?.value ||
    librarySearch?.docId ||
    librarySearch?.context?.docId ||
    librarySearch?.context?.doc_id ||
    ''
  )
}

const ctxReady = computed(() => {
  const lib = String(getLibraryId() || '').trim()
  const doc = String(getDocId() || '').trim()
  if (qaScope.value === 'doc') return !!(lib && doc)
  if (qaScope.value === 'library') return !!lib
  return true
})

function currentCtxSnake() {
  const lib = String(getLibraryId() || '').trim()
  const doc = String(getDocId() || '').trim()
  return { library_id: lib, doc_id: doc }
}

function currentStoreArgs() {
  const c = currentCtxSnake()
  if (qaScope.value === 'doc') return { store_scope: 'doc', library_id: c.library_id, doc_id: c.doc_id }
  if (qaScope.value === 'library') return { store_scope: 'library', library_id: c.library_id }
  return { store_scope: 'global' }
}

function toggleExpand() {
  emit('toggleExpand', !props.expanded)
}

function toggleDebug(qaId) {
  debugOpenId.value = debugOpenId.value === qaId ? '' : qaId
}

function toggleEvidence(qaId) {
  evidenceOpenId.value = evidenceOpenId.value === qaId ? '' : qaId
}

function safeJson(v) {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function badgeText(it) {
  const ok = it?.llm?.ok
  if (ok === true) return t('rightSidebar.topicQA.badges.llm')
  if (ok === false) return t('rightSidebar.topicQA.badges.fallback')
  return t('rightSidebar.topicQA.badges.qa')
}

function badgeClass(it) {
  const ok = it?.llm?.ok
  if (ok === true) return 'ok'
  if (ok === false) return 'bad'
  return 'neutral'
}

function indentPx(depth) {
  const d = Number(depth || 0)
  if (!Number.isFinite(d) || d <= 0) return '0px'
  return `${Math.min(d, 8) * 12}px`
}

function isRootExpanded(rootQaId) {
  const id = String(rootQaId || '')
  return !!id && expandedRootSet.value.has(id)
}

function toggleRoot(rootQaId) {
  const id = String(rootQaId || '')
  if (!id) return
  const next = new Set(expandedRootSet.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedRootSet.value = next
}

function collapseAllRoots() {
  expandedRootSet.value = new Set()
}

function expandAllRoots() {
  expandedRootSet.value = new Set(qaIndex.value.rootIds)
}

function resetHistoryWindow() {
  qaListLimit.value = 120
  qaListMaxSegments.value = 12
  refreshQA()
}

function loadMoreHistory() {
  qaListLimit.value = Math.min(qaListLimit.value + 120, 5000)
  qaListMaxSegments.value = Math.min(qaListMaxSegments.value + 6, 200)
  refreshQA()
}

function setScope(s) {
  if (s !== 'doc' && s !== 'library' && s !== 'global') return
  if (qaScope.value === s) return
  qaScope.value = s
  qaError.value = ''
  qaQuestion.value = ''
  debugOpenId.value = ''
  followUpOpenId.value = ''
  followUpText.value = ''
  evidenceOpenId.value = ''
  collapseAllRoots()

  if (qaScope.value !== 'doc') resetHistoryWindow()
  else refreshQA()
}

function _normalizeQaNode(raw) {
  const node = raw && typeof raw === 'object' ? { ...raw } : {}

  const qaId = String(node?.qa_id || node?.qaid || '').trim()
  const groupId = String(node?.group_id || node?.thread_id || node?.threadid || qaId || '').trim()

  const responseText = String(node?.response || node?.answer || '').trim()
  const questionText = String(node?.question || '').trim()

  const evidenceResult = node?.evidence_result && typeof node.evidence_result === 'object' ? node.evidence_result : {}
  const recordMeta = evidenceResult?.record_meta && typeof evidenceResult.record_meta === 'object' ? evidenceResult.record_meta : {}

  return {
    ...node,
    qa_id: qaId,
    group_id: groupId || null,
    thread_id: String(node?.thread_id || node?.group_id || node?.threadid || qaId || '').trim() || null,
    question: questionText,
    answer: String(node?.answer || responseText || '').trim(),
    response: responseText,
    citations: Array.isArray(node?.citations) ? node.citations : [],
    evidence: Array.isArray(node?.evidence)
      ? node.evidence
      : (Array.isArray(evidenceResult?.evidence) ? evidenceResult.evidence : []),
    library_id: node?.library_id || recordMeta?.library_id || null,
    doc_id: node?.doc_id || recordMeta?.doc_id || null,
    parent_qa_id: node?.parent_qa_id || recordMeta?.parent_qa_id || null,
    depth: node?.depth ?? recordMeta?.depth ?? 0,
    created_at: node?.created_at || recordMeta?.created_at || '',
    params: (node?.params && typeof node.params === 'object') ? node.params : {},
    llm: (node?.llm && typeof node.llm === 'object') ? node.llm : {},
    debug: (node?.debug && typeof node.debug === 'object') ? node.debug : {}
  }
}

function _extractQaRows(res) {
  const records = res?.evidence_result?.records
  if (Array.isArray(records)) return records.map(_normalizeQaNode)

  const legacyRows = res?.qas
  if (Array.isArray(legacyRows)) return legacyRows.map(_normalizeQaNode)

  const stdItems = res?.response?.items
  if (Array.isArray(stdItems)) return stdItems.map(_normalizeQaNode)

  return []
}

function _extractQaSegmentsMeta(res) {
  const er = (res?.evidence_result && typeof res.evidence_result === 'object') ? res.evidence_result : {}
  return {
    hasMore: !!(er?.has_more_segments ?? res?.has_more_segments ?? false),
    total: Number(er?.segments_total ?? res?.segments_total ?? 0),
    scanned: Number(er?.segments_scanned ?? res?.segments_scanned ?? 0)
  }
}

const qaIndex = computed(() => {
  const rows = Array.isArray(qaRawItems.value) ? qaRawItems.value : []
  const nodes = new Map()

  for (const r of rows) {
    const qaId = String(r?.qa_id || r?.qaid || '').trim()
    if (!qaId) continue
    nodes.set(qaId, { ...r, qa_id: qaId, children: [] })
  }

  const roots = []
  for (const n of nodes.values()) {
    const parentId = String(n?.parent_qa_id || n?.parentqaid || '').trim()
    if (parentId && nodes.has(parentId)) nodes.get(parentId).children.push(n)
    else roots.push(n)
  }

  const timeKey = (x) => String(x?.created_at || x?.createdat || '')
  const sortTree = (node) => {
    node.children.sort((a, b) => timeKey(a).localeCompare(timeKey(b)))
    node.children.forEach(sortTree)
  }
  roots.sort((a, b) => timeKey(b).localeCompare(timeKey(a)))
  roots.forEach(sortTree)

  const threadMap = new Map()
  for (const r of roots) {
    const threadId = String(r?.thread_id || r?.threadid || r?.group_id || r?.qa_id || '').trim() || String(r?.qa_id || '')
    if (!threadMap.has(threadId)) threadMap.set(threadId, { threadId, roots: [] })
    threadMap.get(threadId).roots.push(r)
  }
  const threads = Array.from(threadMap.values())
  threads.sort((a, b) => {
    const aMax = a.roots.reduce((m, x) => (timeKey(x) > m ? timeKey(x) : m), '')
    const bMax = b.roots.reduce((m, x) => (timeKey(x) > m ? timeKey(x) : m), '')
    return bMax.localeCompare(aMax)
  })

  const rootByQaId = {}
  const rootIds = []
  const replyCountByRoot = {}

  const mark = (root, node) => {
    rootByQaId[String(node.qa_id)] = String(root.qa_id)
    if (String(node.qa_id) !== String(root.qa_id)) {
      replyCountByRoot[String(root.qa_id)] = (replyCountByRoot[String(root.qa_id)] || 0) + 1
    }
    for (const ch of node.children) mark(root, ch)
  }

  for (const t of threads) {
    for (const r of t.roots) {
      rootIds.push(String(r.qa_id))
      replyCountByRoot[String(r.qa_id)] = replyCountByRoot[String(r.qa_id)] || 0
      mark(r, r)
    }
  }

  const visibleItems = []
  const pushNode = (root, node, depth) => {
    const rootId = String(root.qa_id)
    const qaId = String(node.qa_id)
    const isRoot = qaId === rootId

    visibleItems.push({ qa_id: qaId, isRoot, depth, rootId, node })

    if (isRoot && !expandedRootSet.value.has(rootId)) return
    for (const ch of node.children) pushNode(root, ch, depth + 1)
  }
  for (const t of threads) for (const r of t.roots) pushNode(r, r, 0)

  return { threads, roots, rootIds, rootByQaId, replyCountByRoot, visibleItems }
})

function countReplies(rootQaId) {
  const id = String(rootQaId || '')
  return Number(qaIndex.value.replyCountByRoot?.[id] || 0)
}

function pruneExpandedRoots(nextRootIds) {
  const allowed = new Set((nextRootIds || []).map((x) => String(x)))
  const next = new Set()
  for (const id of expandedRootSet.value) if (allowed.has(String(id))) next.add(String(id))
  expandedRootSet.value = next
}

function hasEvidence(node) {
  return Array.isArray(node?.evidence) && node.evidence.length > 0
}

function formatRel(ev) {
  const r = Number(ev?.relevance)
  if (!Number.isFinite(r)) return '\u2014'
  return `${(r * 100).toFixed(1)}%`
}

async function copyText(text) {
  const t0 = String(text || '')
  if (!t0.trim()) return
  try {
    await navigator.clipboard.writeText(t0)
  } catch {
    qaError.value = t('rightSidebar.topicQA.errors.copyClipboardDenied')
  }
}

async function copyDebug(it) {
  const payload = {
    qa_id: it?.qa_id,
    thread_id: it?.thread_id || it?.group_id,
    parent_qa_id: it?.parent_qa_id,
    depth: it?.depth,
    question: it?.question,
    response: it?.response || it?.answer,
    params: it?.params,
    llm: it?.llm,
    debug: it?.debug,
    evidence: it?.evidence,
    citations: it?.citations,
    linked_from: it?.linked_from
  }
  await copyText(safeJson(payload))
}

function ensureRootExpandedByQaId(qaId) {
  const id = String(qaId || '')
  if (!id) return
  const rootId = qaIndex.value.rootByQaId?.[id] || id
  if (!expandedRootSet.value.has(String(rootId))) {
    const next = new Set(expandedRootSet.value)
    next.add(String(rootId))
    expandedRootSet.value = next
  }
}

function openFollowUp(it) {
  const qaId = String(it?.qa_id || it?.qaid || '')
  if (!qaId) return
  ensureRootExpandedByQaId(qaId)
  followUpOpenId.value = qaId
  followUpText.value = ''
  debugOpenId.value = ''
  evidenceOpenId.value = ''
}

function closeFollowUp() {
  followUpOpenId.value = ''
  followUpText.value = ''
}

function getLinkedFrom(node) {
  const a = node?.linked_from
  const b = node?.params?.linked_from
  const lf = a && typeof a === 'object' ? a : (b && typeof b === 'object' ? b : null)
  if (!lf) return null
  const from_store_scope = String(lf?.from_store_scope || '').trim()
  if (!from_store_scope) return null
  return {
    from_store_scope,
    from_library_id: lf?.from_library_id ? String(lf.from_library_id) : null,
    from_doc_id: lf?.from_doc_id ? String(lf.from_doc_id) : null,
    from_qa_id: lf?.from_qa_id ? String(lf.from_qa_id) : null
  }
}

async function scrollToQaId(qaId) {
  const id = String(qaId || '').trim()
  if (!id) return
  await nextTick()
  const el = document.querySelector(`[data-qa-id="${CSS.escape(id)}"]`)
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

async function goToLinkedFrom(node) {
  const lf = getLinkedFrom(node)
  if (!lf) return

  const targetScope = lf.from_store_scope
  if (targetScope !== 'doc' && targetScope !== 'library' && targetScope !== 'global') return

  if (targetScope === 'doc') {
    if (!lf.from_library_id || !lf.from_doc_id) {
      window.alert(t('rightSidebar.topicQA.errors.traceDocMissing'))
      return
    }
    window.dispatchEvent(
      new CustomEvent('nisb-open-library-doc', {
        detail: { libraryId: lf.from_library_id, docId: lf.from_doc_id, spanIndex: 0, reader: getGlobalReader() }
      })
    )
  }

  setScope(targetScope)
  await refreshQA()

  if (lf.from_qa_id) {
    ensureRootExpandedByQaId(lf.from_qa_id)
    await refreshQA()
    await scrollToQaId(lf.from_qa_id)
  }
}

async function refreshQA() {
  qaError.value = ''
  if (!ctxReady.value) return

  qaLoading.value = true
  try {
    const args = { ...currentStoreArgs() }

    if (qaScope.value !== 'doc') {
      args.limit = qaListLimit.value
      args.max_segments = qaListMaxSegments.value
    } else {
      args.limit = 120
    }

    const res = await callToolCompat('nisb_qa_scope_list', null, args, { trackLoading: false })

    const rows = res?.status === 'success' ? _extractQaRows(res) : []
    qaRawItems.value = Array.isArray(rows) ? rows : []

    if (res?.status !== 'success') {
      qaError.value = res?.message ? String(res.message) : t('rightSidebar.topicQA.errors.qaScopeListNonSuccess')
    }

    const segMeta = _extractQaSegmentsMeta(res)
    qaHasMoreSegments.value = segMeta.hasMore
    qaSegTotal.value = Number.isFinite(segMeta.total) ? segMeta.total : 0
    qaSegScanned.value = Number.isFinite(segMeta.scanned) ? segMeta.scanned : 0

    pruneExpandedRoots(qaIndex.value.rootIds)
  } catch (e) {
    qaRawItems.value = []
    qaError.value = String(e?.message || e)
    qaHasMoreSegments.value = false
    qaSegTotal.value = 0
    qaSegScanned.value = 0
    pruneExpandedRoots([])
  } finally {
    qaLoading.value = false
  }
}

function buildAskParams(question, extra = {}) {
  const ctx = currentCtxSnake()
  const safeExtra = extra && typeof extra === 'object' ? extra : {}
  const { max_chars: _ignoredMaxChars, ...restExtra } = safeExtra
  const answer_lang = resolvePreferredAnswerLang(question)

  const base = {
    ...currentStoreArgs(),
    evidence_scope: qaScope.value,
    question,

    answer_lang,
    answer_mode: 'llm_rich',

    top_k: 18,
    max_evidence: 14,

    memory_turns: 10,
    memory_max_chars: 6000,

    min_citations: 4,
    max_citations: 12,

    max_output_tokens: 2200,

    ...restExtra,

    max_chars: 8000
  }

  if (qaScope.value === 'doc') {
    base.library_id = ctx.library_id
    base.doc_id = ctx.doc_id
  }
  if (qaScope.value === 'library') {
    base.library_id = ctx.library_id
  }

  return base
}

function buildHandoffContext(fromScope, node) {
  const q = String(node?.question || '').trim()
  const a = String(node?.answer || node?.response || '').trim()
  const claims = Array.isArray(node?.claims) ? node.claims : []
  const ev = Array.isArray(node?.evidence) ? node.evidence : []
  const cites = Array.isArray(node?.citations) ? node.citations : []

  const topClaims = claims.slice(0, 8).map((x) => `- ${String(x)}`)
  const topEv = ev.slice(0, 4).map((e) => {
    const lib = String(e?.library_id || '')
    const doc = String(e?.doc_id || '')
    const span = e?.span_index ?? e?.spanIndex ?? e?.span ?? '?'
    const title = String(e?.doc_title || '')
    const ex = String(e?.excerpt || '').slice(0, 220)
    return `- [${title || 'doc'}] lib=${lib} doc=${doc} span=${span}\n  ${ex}`
  })
  const topCites = cites.slice(0, 8).map((c) => {
    const lib = String(c?.library_id || c?.libraryId || '')
    const doc = String(c?.doc_id || c?.docId || '')
    const span = c?.span_index ?? c?.spanIndex ?? c?.span ?? '?'
    const quote = String(c?.quote || '').slice(0, 160)
    return `- cite lib=${lib} doc=${doc} span=${span} ${quote ? `| ${quote}` : ''}`
  })

  const parts = []
  parts.push(`[Handoff From] scope=${fromScope}`)
  if (q) parts.push(`[Question]\n${q}`)
  if (topClaims.length) parts.push(`[Key Points]\n${topClaims.join('\n')}`)
  if (a) parts.push(`[Answer (excerpt)]\n${a.slice(0, 1200)}`)
  if (topEv.length) parts.push(`[Top Evidence]\n${topEv.join('\n')}`)
  if (topCites.length) parts.push(`[Top Citations]\n${topCites.join('\n')}`)
  return parts.join('\n\n').trim()
}

async function handoffElevate(targetScope, node) {
  if (targetScope !== 'library' && targetScope !== 'global') return
  if (qaLoading.value) return

  const fromScope = qaScope.value
  const ctx = currentCtxSnake()

  const fromLibraryId = String(node?.library_id || ctx.library_id || '').trim()
  const fromDocId = String(node?.doc_id || ctx.doc_id || '').trim()
  const fromQaId = String(node?.qa_id || '').trim()

  const handoff_context = buildHandoffContext(fromScope, node)
  const linked_from = {
    from_store_scope: fromScope,
    from_library_id: fromLibraryId || null,
    from_doc_id: fromDocId || null,
    from_qa_id: fromQaId || null
  }

  const question = String(node?.question || qaQuestion.value || '').trim()
  if (!question) return

  const answer_lang = resolvePreferredAnswerLang(question)

  qaLoading.value = true
  qaError.value = ''
  try {
    const askArgs = {
      store_scope: targetScope,
      evidence_scope: targetScope,
      question,
      handoff_context,
      linked_from,

      answer_lang,
      answer_mode: 'llm_rich',
      top_k: 18,
      max_evidence: 14,

      memory_turns: 10,
      memory_max_chars: 6000,

      min_citations: 4,
      max_citations: 12,
      max_output_tokens: 2200,

      max_chars: 8000
    }

    if (targetScope === 'library') askArgs.library_id = ctx.library_id

    const res = await callToolCompat('nisb_qa_scope_ask', null, askArgs, { trackLoading: false })
    if (res?.status !== 'success') {
      qaError.value = res?.message ? String(res.message) : t('rightSidebar.topicQA.errors.handoffNonSuccess')
      return
    }

    setScope(targetScope)
    await refreshQA()
    expandAllRoots()
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
  } catch (e) {
    qaError.value = String(e?.message || e)
  } finally {
    qaLoading.value = false
  }
}

async function askQA() {
  qaError.value = ''
  const q = String(qaQuestion.value || '').trim()
  if (!q) return
  if (!ctxReady.value) return

  qaLoading.value = true
  try {
    const res = await callToolCompat('nisb_qa_scope_ask', null, buildAskParams(q), { trackLoading: false })
    if (res?.status === 'success') {
      qaQuestion.value = ''
      await refreshQA()
      const newest = qaIndex.value.rootIds[0]
      if (newest) ensureRootExpandedByQaId(newest)
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      qaError.value = res?.message ? String(res.message) : t('rightSidebar.topicQA.errors.qaAskNonSuccess')
    }
  } catch (e) {
    qaError.value = String(e?.message || e)
  } finally {
    qaLoading.value = false
  }
}

async function askFollowUp(parentQaId) {
  qaError.value = ''
  const q = String(followUpText.value || '').trim()
  if (!q) return
  if (!ctxReady.value) return

  qaLoading.value = true
  try {
    const res = await callToolCompat(
      'nisb_qa_scope_ask',
      null,
      buildAskParams(q, { parent_qa_id: String(parentQaId || '') }),
      { trackLoading: false }
    )

    if (res?.status === 'success') {
      const pid = String(parentQaId || '')
      closeFollowUp()
      await refreshQA()
      if (pid) ensureRootExpandedByQaId(pid)
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      qaError.value = res?.message ? String(res.message) : t('rightSidebar.topicQA.errors.followupNonSuccess')
    }
  } catch (e) {
    qaError.value = String(e?.message || e)
  } finally {
    qaLoading.value = false
  }
}

async function deleteQA(it) {
  const qaId = String(it?.qa_id || it?.qaid || '')
  if (!qaId) return
  if (!ctxReady.value) return

  const msg = it?.parent_qa_id
    ? t('rightSidebar.topicQA.confirm.deleteReply')
    : t('rightSidebar.topicQA.confirm.deleteRoot')
  if (!window.confirm(msg)) return

  qaLoading.value = true
  qaError.value = ''
  try {
    const base = currentStoreArgs()
    const delArgs = { ...base, action: 'delete', qa_id: qaId, scope: 'auto' }
    const res = await callToolCompat('nisb_qa_scope_ask', null, delArgs, { trackLoading: false })

    if (res?.status === 'success') {
      if (debugOpenId.value === qaId) debugOpenId.value = ''
      if (followUpOpenId.value === qaId) closeFollowUp()
      if (evidenceOpenId.value === qaId) evidenceOpenId.value = ''
      await refreshQA()
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      qaError.value = res?.message ? String(res.message) : t('rightSidebar.topicQA.errors.deleteNonSuccess')
    }
  } catch (e) {
    qaError.value = String(e?.message || e)
  } finally {
    qaLoading.value = false
  }
}

function jumpToSpan(spanIndex, libId = null, docId = null) {
  const ctx = currentCtxSnake()
  const fallbackLib = qaScope.value === 'doc' ? ctx.library_id : ''
  const fallbackDoc = qaScope.value === 'doc' ? ctx.doc_id : ''

  const library_id = String(libId || fallbackLib || '').trim()
  const doc_id = String(docId || fallbackDoc || '').trim()

  const n = Number(spanIndex)
  if (!Number.isFinite(n)) return
  if (!library_id || !doc_id) return

  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: { libraryId: library_id, docId: doc_id, spanIndex: n, reader: getGlobalReader() }
    })
  )
}

function jumpToCitation(c) {
  const x = normalizeCitation(c)
  if (x.spanIndex === null) return
  jumpToSpan(x.spanIndex, x.libraryId, x.docId)
}

watch(
  () => `${getLibraryId()}::${getDocId()}`,
  () => {
    if (qaScope.value !== 'doc') return
    debugOpenId.value = ''
    closeFollowUp()
    evidenceOpenId.value = ''
    collapseAllRoots()
    refreshQA()
  },
  { immediate: true }
)

watch(
  () => qaScope.value,
  () => {
    refreshQA()
  }
)
</script>

<style scoped>
.qa-card {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin: 0.55rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 7%, transparent), transparent 44%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.8rem;
  line-height: 1.45;
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.045);
  overflow: hidden;
}

.qa-card.expanded {
  flex: 1 1 auto;
}

.qa-title-row {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.58rem;
  padding-bottom: 0.48rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 58%, transparent);
}

.qa-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.qa-actions {
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.32rem;
  flex-wrap: wrap;
}

.qa-ask-row {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  margin-top: 0.58rem;
}

.scope-seg {
  flex: 0 0 auto;
  min-height: 30px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 2px;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 12px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  overflow: hidden;
}

.seg-btn {
  min-height: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.52rem;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 720;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    font-weight 0.15s ease;
}

.seg-btn:hover,
.seg-btn:focus-visible {
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
  outline: none;
}

.seg-btn.active {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 68%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
  font-weight: 840;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
}

.qa-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 32px;
  box-sizing: border-box;
  padding: 0 0.62rem;
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
  font-weight: 680;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    color 0.15s ease;
}

.qa-input::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 70%, transparent);
}

.qa-input:hover,
.qa-input:focus {
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

.qa-scope-hint {
  flex: 0 0 auto;
  margin-top: 0.42rem;
  padding: 0.42rem 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 64%, transparent);
  border-radius: 11px;
  background: color-mix(in srgb, var(--editor-bg) 36%, transparent);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.qa-scope-stats {
  margin-top: 0.28rem;
}

.qa-error {
  flex: 0 0 auto;
  margin-top: 0.45rem;
  padding: 0.5rem 0.58rem;
  border: 1px solid rgba(239, 68, 68, 0.34);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: color-mix(in srgb, #ef4444 86%, var(--text-main, var(--text)));
  font-size: 0.76rem;
  font-weight: 690;
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.qa-list {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.52rem;
  margin-top: 0.58rem;
  max-height: 390px;
  padding-right: 0.16rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.qa-list::-webkit-scrollbar {
  width: 8px;
}

.qa-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.qa-card.expanded .qa-list {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
}

.qa-item {
  position: relative;
  min-width: 0;
  box-sizing: border-box;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 44%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 6px 14px rgba(0, 0, 0, 0.035);
  overflow: hidden;
}

.qa-item::before {
  content: "";
  position: absolute;
  left: 0.36rem;
  top: 0.62rem;
  bottom: 0.62rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--selected) 32%, var(--line));
  opacity: 0.76;
}

.qa-item.root {
  border-color: color-mix(in srgb, var(--selected) 18%, var(--line));
}

.qa-item.reply {
  border-color: color-mix(in srgb, var(--selected) 16%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 18%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
}

.qa-item.reply::before {
  background: color-mix(in srgb, var(--selected) 42%, var(--line));
  opacity: 0.52;
}

.qa-item:hover {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 7%, transparent),
    0 9px 20px rgba(0, 0, 0, 0.06);
}

/* collapsed root: clamp question to one line */
.qa-item.collapsed .qa-q {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
}

.qa-q-row {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.58rem;
  padding-left: 0.38rem;
}

.qa-q {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  font-weight: 790;
  line-height: 1.42;
  overflow-wrap: break-word;
}

.qa-q-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.32rem;
  flex-wrap: wrap;
}

.qa-caret {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  min-width: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.34rem;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--editor-bg) 54%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
  font-weight: 800;
  line-height: 1;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.qa-caret:hover,
.qa-caret:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.qa-caret:active {
  transform: translateY(1px);
}

.reply-tag,
.root-meta {
  display: inline-flex;
  align-items: center;
  min-height: 21px;
  margin-right: 0.34rem;
  padding: 0 0.44rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 720;
  line-height: 1;
  vertical-align: middle;
}

.qa-a {
  min-width: 0;
  margin-top: 0.42rem;
  padding-left: 0.38rem;
  color: var(--text-main, var(--text));
  font-size: 0.78rem;
  line-height: 1.52;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  opacity: 0.92;
}

.qa-meta {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.32rem;
  margin-top: 0.46rem;
  padding-left: 0.38rem;
  color: var(--text-secondary);
  font-size: 0.7rem;
  line-height: 1.35;
}

.qa-meta-text {
  max-width: 100%;
  opacity: 0.88;
  overflow-wrap: anywhere;
}

.qa-badge,
.pill {
  min-height: 22px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.qa-badge.ok {
  border-color: color-mix(in srgb, #16a34a 34%, var(--line));
  background: rgba(22, 163, 74, 0.09);
  color: #16a34a;
}

.qa-badge.bad {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.09);
  color: #ef4444;
}

.qa-badge.neutral {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.qa-followup {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 22%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
}

.qa-debug,
.qa-evidence,
.qa-ev {
  min-width: 0;
  margin-top: 0.5rem;
  padding: 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
}

.qa-debug {
  color: var(--text-main, var(--text));
  font-size: 0.7rem;
  line-height: 1.42;
}

.qa-debug-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(86px, 0.34fr) minmax(0, 1fr);
  gap: 0.46rem;
  margin-top: 0.38rem;
}

.qa-debug-row:first-child {
  margin-top: 0;
}

.qa-debug-k {
  color: var(--text-secondary);
  font-weight: 760;
  overflow-wrap: break-word;
}

.qa-debug-v {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  opacity: 0.92;
}

.qa-debug-v.pre {
  opacity: 0.9;
}

.qa-ev-title,
.qa-evidence-title {
  color: var(--text-secondary);
  font-size: 0.71rem;
  font-weight: 780;
  line-height: 1.25;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.qa-ev-list {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  margin-top: 0.38rem;
}

.qa-ev-btn {
  max-width: 100%;
  min-height: 25px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 52%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.71rem;
  font-weight: 720;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.qa-ev-btn:hover:not(:disabled),
.qa-ev-btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 44%, var(--editor-bg));
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent);
  outline: none;
}

.qa-ev-btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.qa-evidence-list {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.42rem;
}

.qa-evidence-item {
  min-width: 0;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 44%, transparent);
}

.qa-evidence-meta {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.34rem;
  color: var(--text-secondary);
  font-size: 0.7rem;
  line-height: 1.35;
}

.qa-evidence-text {
  min-width: 0;
  margin-top: 0.42rem;
  color: var(--text-main, var(--text));
  font-size: 0.76rem;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  opacity: 0.92;
}

.qa-evidence-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
  margin-top: 0.44rem;
}

.qa-loadmore-row {
  flex: 0 0 auto;
  display: flex;
  justify-content: center;
  margin-top: 0.5rem;
}

.qa-history-end,
.qa-empty {
  margin-top: 0.5rem;
  padding: 0.62rem;
  border: 1px dashed color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.mini-btn {
  min-height: 28px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 10px;
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
    opacity 0.15s ease,
    transform 0.12s ease;
}

.mini-btn:hover:not(:disabled),
.mini-btn:focus-visible:not(:disabled) {
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
    0 6px 14px rgba(0, 0, 0, 0.06);
  outline: none;
}

.mini-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mini-btn:disabled {
  opacity: 0.52;
  cursor: not-allowed;
  transform: none;
}

.mini-btn.ghost {
  min-height: 24px;
  padding: 0 0.52rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  font-size: 0.69rem;
  font-weight: 720;
}

.qa-del {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  min-width: 24px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 1rem;
  font-weight: 760;
  line-height: 1;
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

.qa-item:hover .qa-del,
.qa-item:focus-within .qa-del {
  opacity: 1;
  pointer-events: auto;
}

.qa-del:hover:not(:disabled),
.qa-del:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.56);
  background: rgba(239, 68, 68, 0.11);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 6px 14px rgba(239, 68, 68, 0.08);
  outline: none;
}

.qa-del:active:not(:disabled) {
  transform: translateY(1px);
}

.qa-del:disabled {
  opacity: 0.34;
  cursor: not-allowed;
  pointer-events: none;
}

.muted {
  color: var(--text-secondary);
  opacity: 0.82;
}

@media (max-width: 520px) {
  .qa-card {
    margin: 0.45rem;
    padding: 0.5rem;
  }

  .qa-title-row {
    flex-direction: column;
    align-items: stretch;
    gap: 0.46rem;
  }

  .qa-actions {
    justify-content: flex-start;
  }

  .qa-ask-row,
  .qa-followup {
    align-items: stretch;
    flex-direction: column;
  }

  .scope-seg {
    width: 100%;
  }

  .seg-btn {
    flex: 1 1 0;
  }

  .mini-btn {
    width: 100%;
  }

  .qa-q-row {
    flex-direction: column;
    gap: 0.42rem;
  }

  .qa-q-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .qa-debug-row {
    grid-template-columns: 1fr;
  }

  .qa-del {
    opacity: 1;
    pointer-events: auto;
  }
}
</style>

