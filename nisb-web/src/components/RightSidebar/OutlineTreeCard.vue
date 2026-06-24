<!-- /opt/mcp-gateway/nisb-web/src/components/RightSidebar/OutlineTreeCard.vue -->
<template>
  <div class="outline-tree-card">
    <div class="outline-tree-title-row">
      <div class="outline-tree-title">{{ t('rightSidebar.outlineTree.title') }}</div>

      <div class="outline-tree-actions">
        <button
          class="mini-btn mini-toggle"
          :class="{ active: settings.outlineGenerateUseMini }"
          @click="settings.setOutlineGenerateUseMini(!settings.outlineGenerateUseMini)"
          :title="t('rightSidebar.outlineTree.actions.miniGenerateTitle')"
        >
          {{ t('rightSidebar.outlineTree.actions.miniGenerate') }}
        </button>

        <button
          class="mini-btn mini-toggle"
          :class="{ active: settings.outlineExpandUseMini }"
          @click="settings.setOutlineExpandUseMini(!settings.outlineExpandUseMini)"
          :title="t('rightSidebar.outlineTree.actions.miniExpandTitle')"
        >
          {{ t('rightSidebar.outlineTree.actions.miniExpand') }}
        </button>

        <button
          class="mini-btn"
          :disabled="outlineLoading || translateLoading || !outlineCtxReady"
          @click="translateOutlineZh()"
        >
          {{ translateLoading ? t('rightSidebar.outlineTree.actions.translating') : t('rightSidebar.outlineTree.actions.translateZh') }}
        </button>

        <button
          class="mini-btn mini-toggle"
          :class="{ active: settings.outlineShowZhTitle }"
          :disabled="outlineLoading || translateLoading"
          @click="settings.setOutlineShowZhTitle(!settings.outlineShowZhTitle)"
          :title="t('rightSidebar.outlineTree.actions.showZhTitle')"
        >
          {{ t('rightSidebar.outlineTree.actions.showZh') }}
        </button>

        <button
          class="mini-btn"
          :disabled="outlineLoading || translateLoading || !outlineCtxReady"
          @click="loadOutline(true)"
        >
          {{ t('rightSidebar.outlineTree.actions.generateRefresh') }}
        </button>

        <button
          class="mini-btn"
          :disabled="outlineLoading || translateLoading || !outlineCtxReady"
          @click="toggleOutlineAll()"
        >
          {{ outlineAllCollapsed ? t('rightSidebar.outlineTree.actions.expandAll') : t('rightSidebar.outlineTree.actions.collapseAll') }}
        </button>
      </div>
    </div>

    <div v-if="!outlineCtxReady" class="muted">{{ t('rightSidebar.outlineTree.states.unavailable') }}</div>
    <div v-else-if="outlineLoading || translateLoading" class="muted">{{ t('rightSidebar.outlineTree.states.loading') }}</div>

    <div v-else-if="outlineError" class="muted outline-error">
      <div>{{ outlineError }}</div>
      <pre v-if="outlineDebug" class="outline-debug">{{ outlineDebug }}</pre>
    </div>

    <div v-else-if="!outlineRoot" class="muted">{{ t('rightSidebar.outlineTree.states.empty') }}</div>

    <div v-else class="outline-tree">
      <OutlineNode
        :node="outlineRoot"
        :depth="0"
        :collapsedSet="outlineCollapsedSet"
        :showZh="settings.outlineShowZhTitle"
        @jump="jumpToOutlineNode"
        @toggle="toggleOutlineNode"
        @expandRemote="expandOutlineNodeRemote"
      />
    </div>

    <div class="muted outline-tree-hint" v-if="outlineCtxReady">
      {{ t('rightSidebar.outlineTree.hint') }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLibrarySearchStore } from '../../stores/librarySearch'
import { useSettingsStore } from '../../stores/settings'
import { useMCP } from '../../composables/useMCP'

const { t } = useI18n()
const librarySearch = useLibrarySearchStore()
const settings = useSettingsStore()
const { callTool } = useMCP()

function getGlobalReader() {
  return window.nisbReaderState || window.__nisbReaderState || null
}

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

const outlineLoading = ref(false)
const translateLoading = ref(false)

const outlineRoot = ref(null)
const outlineError = ref('')
const outlineDebug = ref('')
const outlineReqKey = ref('')

const outlineCollapsedSet = ref(new Set())
const outlineAllCollapsed = ref(false)

const outlineCtxReady = computed(() => {
  const lib =
    librarySearch?.libraryId?.value ||
    librarySearch?.libraryId ||
    librarySearch?.context?.libraryId ||
    librarySearch?.context?.library_id ||
    null
  const doc =
    librarySearch?.docId?.value ||
    librarySearch?.docId ||
    librarySearch?.context?.docId ||
    librarySearch?.context?.doc_id ||
    null
  return !!(lib && doc)
})

function currentCtxSnake() {
  const lib =
    librarySearch?.libraryId?.value ||
    librarySearch?.libraryId ||
    librarySearch?.context?.libraryId ||
    librarySearch?.context?.library_id ||
    ''
  const doc =
    librarySearch?.docId?.value ||
    librarySearch?.docId ||
    librarySearch?.context?.docId ||
    librarySearch?.context?.doc_id ||
    ''
  return { library_id: lib, doc_id: doc }
}

function collectNodeIds(root) {
  const ids = []
  function walk(n) {
    if (!n || typeof n !== 'object') return
    if (n.node_id) ids.push(String(n.node_id))
    const ch = Array.isArray(n.children) ? n.children : []
    ch.forEach(walk)
  }
  walk(root)
  return ids
}

function toggleOutlineAll() {
  const root = outlineRoot.value
  if (!root) return
  outlineAllCollapsed.value = !outlineAllCollapsed.value

  const ids = collectNodeIds(root)
  const next = new Set(outlineCollapsedSet.value)

  if (outlineAllCollapsed.value) {
    ids.forEach((id) => next.add(id))
    next.delete(String(root.node_id || 'root'))
  } else {
    ids.forEach((id) => next.delete(id))
  }
  outlineCollapsedSet.value = next
}

function toggleOutlineNode(node) {
  if (!node?.node_id) return
  const id = String(node.node_id)
  const hasChildren = Array.isArray(node.children) && node.children.length > 0
  if (!hasChildren) return

  const next = new Set(outlineCollapsedSet.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  outlineCollapsedSet.value = next
}

async function loadOutline(ensure = false, opts = {}) {
  const lib =
    opts.libraryId ||
    opts.library_id ||
    librarySearch?.libraryId?.value ||
    librarySearch?.libraryId ||
    null
  const doc =
    opts.docId ||
    opts.doc_id ||
    librarySearch?.docId?.value ||
    librarySearch?.docId ||
    null
  if (!lib || !doc) return

  const myKey = `${lib}::${doc}::${ensure ? 1 : 0}::${Date.now()}`
  outlineReqKey.value = myKey

  outlineLoading.value = true
  outlineError.value = ''
  outlineDebug.value = ''

  try {
    const res = await callTool('nisb_doc_outline_get', {
      library_id: lib,
      doc_id: doc,
      ensure: ensure ? 1 : 0,
      mode: settings.outlineGenerateUseMini ? 'llm' : 'headings',
      model: settings.outlineGenerateUseMini ? 'gpt-4o-mini' : undefined,
      force_llm: settings.outlineGenerateUseMini ? 1 : 0
    })

    if (outlineReqKey.value !== myKey) return

    if (res && res.status === 'success') {
      outlineRoot.value = res?.latest?.tree?.root || null
      outlineDebug.value = res?.debug ? JSON.stringify(res.debug, null, 2) : ''
      outlineCollapsedSet.value = new Set()
      outlineAllCollapsed.value = false
      if (!outlineRoot.value) outlineError.value = res?.message ? String(res.message) : ''
    } else {
      outlineRoot.value = null
      outlineError.value = res?.message ? String(res.message) : t('rightSidebar.outlineTree.errors.outlineGetFailed')
      outlineDebug.value = res?.debug ? JSON.stringify(res.debug, null, 2) : ''
    }
  } catch (e) {
    if (outlineReqKey.value !== myKey) return
    outlineRoot.value = null
    outlineError.value = String(e?.message || e)
    outlineDebug.value = ''
  } finally {
    if (outlineReqKey.value === myKey) outlineLoading.value = false
  }
}

function jumpToOutlineNode(node) {
  if (!node) return
  const ctx = currentCtxSnake()
  if (!ctx.library_id || !ctx.doc_id) return

  const hint = node?.span_hint || {}

  const spanIndexRaw = hint?.span_index
  const spanIndexParsed = spanIndexRaw === null || spanIndexRaw === undefined ? null : Number(spanIndexRaw)

  const startOffset = Number(hint?.start_offset ?? 0)
  const fallbackSpanIndex = Math.max(0, Math.floor(startOffset / 8000))

  const spanIndex = Number.isFinite(spanIndexParsed) ? spanIndexParsed : fallbackSpanIndex

  window.dispatchEvent(
    new CustomEvent('nisb-open-library-doc', {
      detail: {
        libraryId: ctx.library_id,
        docId: ctx.doc_id,
        spanIndex,
        reader: getGlobalReader()
      }
    })
  )
}

async function expandOutlineNodeRemote(node) {
  if (!outlineCtxReady.value) return
  if (!node?.node_id) return

  outlineLoading.value = true
  outlineError.value = ''
  outlineDebug.value = ''

  const ctx = currentCtxSnake()
  const useMini = !!settings.outlineExpandUseMini

  try {
    const res = await callTool('nisb_doc_outline_expand', {
      library_id: ctx.library_id,
      doc_id: ctx.doc_id,
      node_id: String(node.node_id),
      mode: useMini ? 'llm' : 'headings',
      model: useMini ? 'gpt-4o-mini' : undefined
    })

    if (res && res.status === 'success') {
      outlineRoot.value = res?.latest?.tree?.root || outlineRoot.value
      outlineDebug.value = res?.debug ? JSON.stringify(res.debug, null, 2) : ''

      const msg = String(res?.message || '')
      const llm = res?.latest?.llm || null
      const tokenEst = llm && typeof llm === 'object' ? llm.input_tokens_est : null

      if (msg.includes('already expanded')) {
        toast(t('rightSidebar.outlineTree.toasts.alreadyExpanded'), 'info')
      } else if (msg.includes('no headings')) {
        toast(t('rightSidebar.outlineTree.toasts.noHeadings'), 'info')
      } else if (useMini && tokenEst) {
        toast(t('rightSidebar.outlineTree.toasts.miniExpandDone', { tokens: tokenEst }), 'info')
      }

      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      outlineError.value = res?.message ? String(res.message) : t('rightSidebar.outlineTree.errors.outlineExpandFailed')
      outlineDebug.value = res?.debug ? JSON.stringify(res.debug, null, 2) : ''
    }
  } catch (e) {
    outlineError.value = String(e?.message || e)
    outlineDebug.value = ''
  } finally {
    outlineLoading.value = false
  }
}

async function translateOutlineZh() {
  if (!outlineCtxReady.value) return
  if (translateLoading.value) return

  const ctx = currentCtxSnake()
  translateLoading.value = true
  outlineError.value = ''
  outlineDebug.value = ''

  try {
    const res = await callTool('nisb_doc_outline_translate', {
      library_id: ctx.library_id,
      doc_id: ctx.doc_id,
      target_lang: 'zh',
      model: 'gpt-4o-mini',
      force_rebuild: 0
    })

    if (res && res.status === 'success') {
      const msg = String(res?.message || '')
      const latestRoot = res?.latest?.tree?.root || null
      if (latestRoot) outlineRoot.value = latestRoot

      if (msg.includes('already translated')) {
        toast(t('rightSidebar.outlineTree.toasts.alreadyTranslated'), 'info')
      } else {
        const est = res?.latest?.llm?.input_tokens_est_total || null
        if (est) toast(t('rightSidebar.outlineTree.toasts.translateDoneWithTokens', { tokens: est }), 'info')
        else toast(t('rightSidebar.outlineTree.toasts.translateDone'), 'info')
      }

      if (!settings.outlineShowZhTitle) settings.setOutlineShowZhTitle(true)
      window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    } else {
      outlineError.value = res?.message ? String(res.message) : t('rightSidebar.outlineTree.errors.outlineTranslateFailed')
      outlineDebug.value = res?.debug ? JSON.stringify(res.debug, null, 2) : ''
    }
  } catch (e) {
    outlineError.value = String(e?.message || e)
    outlineDebug.value = ''
  } finally {
    translateLoading.value = false
  }
}

const OutlineNode = defineComponent({
  name: 'OutlineNode',
  props: {
    node: { type: Object, required: true },
    depth: { type: Number, required: true },
    collapsedSet: { type: Object, required: true },
    showZh: { type: Boolean, required: true }
  },
  emits: ['jump', 'toggle', 'expandRemote'],
  setup(props, { emit }) {
    return () => {
      const n = props.node || {}
      const rawTitle = String(n.title || n.node_id || '')
      const zhTitle = String(n.title_zh || '').trim()
      const title = props.showZh ? (zhTitle || rawTitle) : rawTitle

      const children = Array.isArray(n.children) ? n.children : []
      const nodeId = String(n.node_id || '')
      const hasChildren = children.length > 0
      const isCollapsed = nodeId && props.collapsedSet?.has?.(nodeId)

      return h('div', { class: 'ot-node' }, [
        h(
          'div',
          {
            class: 'ot-row',
            style: { paddingLeft: `${props.depth * 10}px` },
            onClick: () => emit('toggle', n)
          },
          [
            h('div', { class: 'ot-caret' }, hasChildren ? (isCollapsed ? '▶' : '▼') : ''),
            h('div', { class: 'ot-title', title }, title),
            h('div', { class: 'ot-actions' }, [
              h(
                'button',
                {
                  class: 'ot-btn',
                  title: t('rightSidebar.outlineTree.node.jump'),
                  onClick: (e) => {
                    e.stopPropagation()
                    emit('jump', n)
                  }
                },
                t('rightSidebar.outlineTree.node.jump')
              ),
              h(
                'button',
                {
                  class: 'ot-btn',
                  title: t('rightSidebar.outlineTree.node.expandFromNode'),
                  onClick: (e) => {
                    e.stopPropagation()
                    emit('expandRemote', n)
                  }
                },
                '+'
              )
            ])
          ]
        ),
        ...(hasChildren && !isCollapsed
          ? children.map((ch) =>
              h(OutlineNode, {
                node: ch,
                depth: props.depth + 1,
                collapsedSet: props.collapsedSet,
                showZh: props.showZh,
                onJump: (x) => emit('jump', x),
                onToggle: (x) => emit('toggle', x),
                onExpandRemote: (x) => emit('expandRemote', x)
              })
            )
          : [])
      ])
    }
  }
})

watch(
  () => {
    const c = currentCtxSnake()
    return `${c.library_id}::${c.doc_id}`
  },
  (k) => {
    if (!k || k === '::') return
    loadOutline(true)
  },
  { immediate: true }
)
</script>

<style scoped>
.outline-tree-card {
  padding: 0.7rem 0.8rem;
  border-bottom: 1px solid var(--line);
  background: var(--sidebar-bg);
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.outline-tree-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 0.45rem;
}

.outline-tree-title {
  font-weight: 600;
  color: var(--text-main);
}

.outline-tree-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.mini-btn {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
  font-size: 12px;
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mini-toggle.active {
  border-color: rgba(120, 160, 255, 0.55);
  background: rgba(120, 160, 255, 0.10);
  color: var(--text-main);
}

.muted {
  opacity: 0.75;
}

.outline-tree {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ot-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 10px;
  cursor: pointer;
  user-select: none;
}
.ot-row:hover {
  background: var(--selected-bg);
}

.ot-caret {
  width: 14px;
  flex: 0 0 14px;
  opacity: 0.65;
  font-size: 12px;
  line-height: 1;
}

.ot-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.92;
}

.ot-actions {
  display: flex;
  gap: 6px;
  opacity: 0;
  pointer-events: none;
}
.ot-row:hover .ot-actions {
  opacity: 1;
  pointer-events: auto;
}

.ot-btn {
  padding: 4px 8px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
  font-size: 12px;
}

.outline-tree-hint {
  margin-top: 0.45rem;
  font-size: 0.74rem;
}

.outline-error {
  color: var(--text-main);
  opacity: 0.85;
  white-space: pre-wrap;
  line-height: 1.35;
}

.outline-debug {
  margin-top: 8px;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  font-size: 12px;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  line-height: 1.35;
}
</style>
