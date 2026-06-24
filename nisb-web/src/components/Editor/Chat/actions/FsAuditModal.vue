<template>
  <Teleport to="body">
    <div v-if="open" class="overlay" @click="close">
      <div
        class="modal"
        role="dialog"
        aria-modal="true"
        :aria-label="t('chat.fsAuditModal.title')"
        @click.stop
      >
        <div class="header">
          <div class="title-wrap">
            <div class="title">{{ t('chat.fsAuditModal.title') }}</div>
            <div class="subtitle">{{ t('chat.fsAuditModal.subtitle') }}</div>

            <div class="status-row" aria-live="polite">
              <span class="status-chip">{{ t('chat.fsAuditModal.status.audit') }}</span>
              <span class="status-chip">{{ t('chat.fsAuditModal.status.recovery') }}</span>
              <span class="status-chip caution">{{ t('chat.fsAuditModal.status.confirmRequired') }}</span>
            </div>
          </div>

          <div class="actions">
            <button class="btn" type="button" @click="refreshActive" :disabled="busy">
              {{ t('chat.fsAuditModal.actions.refresh') }}
            </button>
            <button class="btn ghost close-btn" type="button" @click="close" :aria-label="t('chat.fsAuditModal.actions.close')">
              ×
            </button>
          </div>
        </div>

        <div class="tabs" role="tablist" :aria-label="t('chat.fsAuditModal.tabs.ariaLabel')">
          <button
            class="tab"
            type="button"
            role="tab"
            :aria-selected="tab === 'audit' ? 'true' : 'false'"
            :class="{ active: tab === 'audit' }"
            @click="tab = 'audit'"
          >
            {{ t('chat.fsAuditModal.tabs.audit') }}
          </button>
          <button
            class="tab"
            type="button"
            role="tab"
            :aria-selected="tab === 'files' ? 'true' : 'false'"
            :class="{ active: tab === 'files' }"
            @click="tab = 'files'"
          >
            {{ t('chat.fsAuditModal.tabs.files') }}
          </button>
          <button
            class="tab caution"
            type="button"
            role="tab"
            :aria-selected="tab === 'trash' ? 'true' : 'false'"
            :class="{ active: tab === 'trash' }"
            @click="tab = 'trash'"
          >
            {{ t('chat.fsAuditModal.tabs.trash') }}
          </button>
          <button
            class="tab caution"
            type="button"
            role="tab"
            :aria-selected="tab === 'batch' ? 'true' : 'false'"
            :class="{ active: tab === 'batch' }"
            @click="tab = 'batch'"
          >
            {{ t('chat.fsAuditModal.tabs.batch') }}
          </button>
        </div>

        <div v-if="tab === 'audit'" class="body">
          <div class="bar">
            <div class="field">
              <span class="label">{{ t('chat.fsAuditModal.audit.prefix') }}</span>
              <input class="input" v-model="auditPrefix" :placeholder="t('chat.fsAuditModal.audit.prefixPlaceholder')" />
            </div>
            <div class="field right">
              <span class="label">{{ t('chat.fsAuditModal.audit.limit') }}</span>
              <select class="select" v-model.number="auditLimit">
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
                <option :value="200">200</option>
              </select>
            </div>
          </div>

          <div class="bar">
            <div class="field grow">
              <span class="label">{{ t('chat.fsAuditModal.audit.backups.title') }}</span>
              <span class="muted" v-if="backupsLoading">{{ t('chat.fsAuditModal.audit.backups.loading') }}</span>
              <span class="muted" v-else>{{ backupsStatsText }}</span>
            </div>
            <div class="field right">
              <button class="btn" @click="loadBackupsStats" :disabled="busy || backupsLoading">
                {{ t('chat.fsAuditModal.audit.backups.refreshStats') }}
              </button>
              <button class="btn danger" @click="purgeAllBackups" :disabled="busy || backupsLoading">
                {{ t('chat.fsAuditModal.audit.backups.purgeAll') }}
              </button>
            </div>
          </div>

          <div class="bar">
            <div class="field grow">
              <span class="label">{{ t('chat.fsAuditModal.audit.searchLabel') }}</span>
              <input
                class="input"
                v-model="auditQuery"
                :placeholder="t('chat.fsAuditModal.audit.searchPlaceholder')"
                @keydown.enter="auditSearch(true)"
              />
            </div>
            <div class="field right">
              <button class="btn" @click="auditSearch(true)" :disabled="busy">{{ t('chat.fsAuditModal.actions.search') }}</button>
              <button class="btn" v-if="auditHasMore" @click="auditLoadMore" :disabled="busy">
                {{ t('chat.fsAuditModal.actions.loadMore') }}
              </button>
            </div>
          </div>

          <div class="bar" v-if="auditQuery.trim()">
            <div class="muted">
              {{
                t('chat.fsAuditModal.audit.filterSummary', {
                  keyword: auditQuery.trim(),
                  shown: auditEvents.length,
                  total: auditRawEvents.length
                })
              }}
            </div>
          </div>

          <div v-if="err" class="err">{{ err }}</div>
          <div v-if="busy" class="muted">{{ t('chat.fsAuditModal.common.loading') }}</div>

          <div v-else class="list">
            <div v-for="e in auditEvents" :key="auditKey(e)" class="audit-row">
              <div class="rowTop">
                <span class="op">{{ e.operation || e.event || '-' }}</span>
                <span class="id">{{ e.backup_id || '-' }}</span>
                <span class="ts">{{ e.ts || '' }}</span>
              </div>

              <div v-if="is_dir_move_path_event(e)" class="paths">
                <div class="pathLine">
                  <span class="path wrap">{{ displayFsPathText(e.metadata?.old_path) }}</span>
                  <span class="muted">→</span>
                  <span class="path wrap">{{ displayFsPathText(e.metadata?.new_path) }}</span>
                  <button
                    class="mini danger"
                    @click="restore_dir_move_path(e)"
                    :disabled="busy"
                    :title="t('chat.fsAuditModal.audit.restoreRenameTitle')"
                  >
                    {{ t('chat.fsAuditModal.actions.restoreRename') }}
                  </button>
                </div>
              </div>

              <div class="paths" v-else-if="Array.isArray(e.paths) && e.paths.length">
                <div v-for="p in e.paths.slice(0, 5)" :key="p" class="pathLine">
                  <span class="path wrap">{{ displayFsPathText(p) }}</span>

                  <button
                    v-if="e.backup_id && e.restorable !== false"
                    class="mini"
                    @click="restore_backup(e.backup_id, p)"
                    :disabled="busy"
                    :title="t('chat.fsAuditModal.audit.restoreBackupTitle')"
                  >
                    {{ t('chat.fsAuditModal.actions.restore') }}
                  </button>
                  <span v-else-if="e.backup_id && e.restorable === false" class="muted small">
                    {{ t('chat.fsAuditModal.audit.backupPurged') }}
                  </span>
                </div>
              </div>

              <details v-if="e.metadata && Object.keys(e.metadata).length" class="meta">
                <summary class="muted">{{ t('chat.fsAuditModal.audit.metadata') }}</summary>
                <pre class="pre">{{ prettyDisplay(e.metadata) }}</pre>
              </details>
            </div>

            <div v-if="auditEvents.length === 0" class="muted">{{ t('chat.fsAuditModal.audit.empty') }}</div>
          </div>

          <div class="footer muted">
            {{ t('chat.fsAuditModal.audit.footer') }}
          </div>
        </div>

        <div v-else-if="tab === 'files'" class="body">
          <div class="bar">
            <div class="field">
              <span class="label">{{ t('chat.fsAuditModal.files.depth') }}</span>
              <select class="select" v-model.number="snapDepth">
                <option :value="1">1</option>
                <option :value="2">2</option>
                <option :value="3">3</option>
                <option :value="4">4</option>
              </select>
            </div>
            <div class="field">
              <label class="chk">
                <input type="checkbox" v-model="snapIncludeHidden" />
                <span>{{ t('chat.fsAuditModal.files.includeHidden') }}</span>
              </label>
            </div>
            <div class="field right">
              <button class="btn" @click="loadSnapshot" :disabled="busy">
                {{ t('chat.fsAuditModal.files.refreshSnapshot') }}
              </button>
            </div>
          </div>

          <div v-if="err" class="err">{{ err }}</div>
          <div v-if="busy" class="muted">{{ t('chat.fsAuditModal.common.loading') }}</div>

          <div v-else class="panel">
            <div class="muted">
              {{ t('chat.fsAuditModal.files.snapshotMeta', { root: displayFsPathText(snapshot?.root || 'agent_files'), ts: snapshot?.ts || '-' }) }}
            </div>
            <pre class="pre">{{ snapshot?.tree_text ? displayFsText(snapshot.tree_text) : t('chat.fsAuditModal.files.emptyTree') }}</pre>
          </div>
        </div>

        <div v-else-if="tab === 'trash'" class="body">
          <div class="section">
            <div class="section-title">{{ t('chat.fsAuditModal.trash.batch.title') }}</div>

            <div class="bar">
              <input
                v-model="trashBatchQuery"
                class="input"
                :placeholder="t('chat.fsAuditModal.trash.batch.searchPlaceholder')"
                @keyup.enter="loadTrashBatches"
              />
              <button class="btn" @click="loadTrashBatches">{{ t('chat.fsAuditModal.actions.refresh') }}</button>
              <button class="btn danger" @click="purgeTrashAll">{{ t('chat.fsAuditModal.trash.batch.purgeAll') }}</button>
            </div>

            <div v-if="trashBatchLoading" class="muted">{{ t('chat.fsAuditModal.common.loadingAscii') }}</div>
            <div v-else-if="!trashBatches.length" class="muted">{{ t('chat.fsAuditModal.trash.batch.empty') }}</div>

            <div v-else class="list">
              <div v-for="b in trashBatches" :key="b.bulk_id" class="item">
                <div class="item-main">
                  <div class="item-line">
                    <span class="mono">{{ t('chat.fsAuditModal.trash.batch.bulkId', { id: b.bulk_id }) }}</span>
                    <span class="muted"> · {{ t('chat.fsAuditModal.trash.batch.itemsCount', { count: b.items_count }) }}</span>
                  </div>
                  <div class="muted small wrap">{{ t('chat.fsAuditModal.trash.batch.bucket', { path: displayFsPathText(b.bucket_rel) }) }}</div>

                  <div v-if="openBulkId === b.bulk_id" class="detail">
                    <div class="bar">
                      <input
                        v-model="batchDetailQuery"
                        class="input"
                        :placeholder="t('chat.fsAuditModal.trash.batch.searchInBatchPlaceholder')"
                        @keyup.enter="loadBatchDetail(0)"
                      />
                      <button class="btn" @click="loadBatchDetail(0)">{{ t('chat.fsAuditModal.actions.search') }}</button>
                    </div>

                    <div v-if="batchDetailLoading" class="muted">{{ t('chat.fsAuditModal.common.loadingAscii') }}</div>
                    <div v-else-if="!batchDetail.items.length" class="muted">{{ t('chat.fsAuditModal.trash.batch.emptyDetail') }}</div>

                    <div v-else class="list">
                      <div v-for="it in batchDetail.items" :key="it.trash_rel" class="subitem">
                        <div class="submain">
                          <div class="small">
                            <span class="mono">{{ it.type === 'directory' ? '📁' : '📄' }}</span>
                            <span class="wrap">{{ displayFsPathText(it.original_rel) }}</span>
                          </div>
                          <div class="muted small wrap">← {{ displayFsPathText(it.trash_rel) }}</div>
                        </div>
                        <div class="subactions">
                          <button class="btn" @click="restoreTrashItem(it)">{{ t('chat.fsAuditModal.actions.restoreThisItem') }}</button>
                        </div>
                      </div>
                    </div>

                    <div v-if="batchDetail.total > batchDetail.limit" class="bar">
                      <button
                        class="btn"
                        :disabled="batchDetail.offset <= 0"
                        @click="loadBatchDetail(Math.max(0, batchDetail.offset - batchDetail.limit))"
                      >
                        {{ t('chat.fsAuditModal.actions.previousPage') }}
                      </button>
                      <div class="muted small">
                        {{ t('chat.fsAuditModal.common.page', { page: Math.floor(batchDetail.offset / batchDetail.limit) + 1 }) }}
                      </div>
                      <button
                        class="btn"
                        :disabled="batchDetail.offset + batchDetail.limit >= batchDetail.total"
                        @click="loadBatchDetail(batchDetail.offset + batchDetail.limit)"
                      >
                        {{ t('chat.fsAuditModal.actions.nextPage') }}
                      </button>
                    </div>
                  </div>
                </div>

                <div class="item-actions">
                  <button class="btn" @click="toggleBatchDetail(b.bulk_id)">
                    {{ openBulkId === b.bulk_id ? t('chat.fsAuditModal.actions.collapse') : t('chat.fsAuditModal.actions.expand') }}
                  </button>
                  <button class="btn danger" @click="restoreTrashBatch(b.bulk_id)">
                    {{ t('chat.fsAuditModal.actions.restoreBatch') }}
                  </button>
                  <button class="btn danger" @click="purgeTrashBatch(b.bulk_id)">
                    {{ t('chat.fsAuditModal.actions.purgeBatch') }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-title">{{ t('chat.fsAuditModal.trash.conversation.title') }}</div>

            <div class="bar">
              <input
                v-model="convTrashBatchQuery"
                class="input"
                :placeholder="t('chat.fsAuditModal.trash.conversation.searchPlaceholder')"
                @keyup.enter="loadConvTrashBatches"
              />
              <button class="btn" @click="loadConvTrashBatches">{{ t('chat.fsAuditModal.actions.refresh') }}</button>
              <button class="btn danger" @click="purgeAllConvTrash">{{ t('chat.fsAuditModal.trash.conversation.purgeAll') }}</button>
            </div>

            <div v-if="convTrashBatchLoading" class="muted">{{ t('chat.fsAuditModal.common.loadingAscii') }}</div>
            <div v-else-if="!convTrashBatches.length" class="muted">{{ t('chat.fsAuditModal.trash.conversation.empty') }}</div>

            <div v-else class="list">
              <div v-for="b in convTrashBatches" :key="b.bulk_id" class="item">
                <div class="item-main">
                  <div class="item-line">
                    <span class="mono">{{ t('chat.fsAuditModal.trash.conversation.bulkId', { id: b.bulk_id }) }}</span>
                    <span class="muted"> · {{ t('chat.fsAuditModal.trash.conversation.itemsCount', { count: b.items_count }) }}</span>
                  </div>
                  <div class="muted small wrap">{{ t('chat.fsAuditModal.trash.conversation.displayName', { name: b.display_name || b.conv_id }) }}</div>
                  <div class="muted small wrap">{{ t('chat.fsAuditModal.trash.conversation.convId', { id: b.conv_id }) }}</div>
                  <div class="muted small wrap">{{ t('chat.fsAuditModal.trash.conversation.bucket', { path: displayFsPathText(b.bucket_rel) }) }}</div>

                  <div v-if="openConvBulkId === b.bulk_id" class="detail">
                    <div class="bar">
                      <input
                        v-model="convBatchDetailQuery"
                        class="input"
                        :placeholder="t('chat.fsAuditModal.trash.conversation.searchInBatchPlaceholder')"
                        @keyup.enter="loadConvBatchDetail(0)"
                      />
                      <button class="btn" @click="loadConvBatchDetail(0)">{{ t('chat.fsAuditModal.actions.search') }}</button>
                    </div>

                    <div v-if="convBatchDetailLoading" class="muted">{{ t('chat.fsAuditModal.common.loadingAscii') }}</div>
                    <div v-else-if="!convBatchDetail.items.length" class="muted">{{ t('chat.fsAuditModal.trash.conversation.emptyDetail') }}</div>

                    <div v-else class="list">
                      <div v-for="it in convBatchDetail.items" :key="it.trash_rel" class="subitem">
                        <div class="submain">
                          <div class="small">
                            <span class="mono">{{ it.type === 'directory' ? '📁' : '📄' }}</span>
                            <span class="wrap">{{ it.original_rel }}</span>
                          </div>
                          <div class="muted small wrap">← {{ it.trash_rel }}</div>
                        </div>
                        <div class="subactions">
                          <button class="btn" @click="restoreConvBatch(b.bulk_id)">
                            {{ t('chat.fsAuditModal.actions.restoreBatch') }}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div v-if="convBatchDetail.total > convBatchDetail.limit" class="bar">
                      <button
                        class="btn"
                        :disabled="convBatchDetail.offset <= 0"
                        @click="loadConvBatchDetail(Math.max(0, convBatchDetail.offset - convBatchDetail.limit))"
                      >
                        {{ t('chat.fsAuditModal.actions.previousPage') }}
                      </button>
                      <div class="muted small">
                        {{ t('chat.fsAuditModal.common.page', { page: Math.floor(convBatchDetail.offset / convBatchDetail.limit) + 1 }) }}
                      </div>
                      <button
                        class="btn"
                        :disabled="convBatchDetail.offset + convBatchDetail.limit >= convBatchDetail.total"
                        @click="loadConvBatchDetail(convBatchDetail.offset + convBatchDetail.limit)"
                      >
                        {{ t('chat.fsAuditModal.actions.nextPage') }}
                      </button>
                    </div>
                  </div>
                </div>

                <div class="item-actions">
                  <button class="btn" @click="toggleConvBatchDetail(b.bulk_id)">
                    {{ openConvBulkId === b.bulk_id ? t('chat.fsAuditModal.actions.collapse') : t('chat.fsAuditModal.actions.expand') }}
                  </button>
                  <button class="btn danger" @click="restoreConvBatch(b.bulk_id)">
                    {{ t('chat.fsAuditModal.actions.restoreBatch') }}
                  </button>
                  <button class="btn danger" @click="purgeConvBatch(b.bulk_id)">
                    {{ t('chat.fsAuditModal.actions.purgeBatch') }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="bar">
            <div class="field grow">
              <span class="label">{{ t('chat.fsAuditModal.trash.filter') }}</span>
              <input
                class="input"
                v-model="trashQuery"
                :placeholder="t('chat.fsAuditModal.trash.filterPlaceholder')"
                @keydown.enter="loadTrash"
              />
            </div>
            <div class="field right">
              <button class="btn" @click="loadTrash" :disabled="busy">{{ t('chat.fsAuditModal.trash.refreshTrash') }}</button>
            </div>
          </div>

          <div v-if="err" class="err">{{ err }}</div>
          <div v-if="busy" class="muted">{{ t('chat.fsAuditModal.common.loading') }}</div>

          <div v-else class="list">
            <div v-for="it in trashItems" :key="it.trash_rel" class="audit-row">
              <div class="rowTop">
                <span class="op">{{ t('chat.fsAuditModal.trash.itemType') }}</span>
                <span class="id">{{ t('chat.fsAuditModal.trash.bytes', { size: it.size ?? '-' }) }}</span>
                <span class="ts">{{ it.mtime ? new Date(it.mtime * 1000).toISOString() : '' }}</span>
              </div>

              <div class="paths">
                <div class="pathLine">
                  <span class="path wrap">{{ t('chat.fsAuditModal.trash.trashPath', { path: displayFsPathText(it.trash_rel) }) }}</span>
                  <button class="mini" @click="trashRestore(it)" :disabled="busy">{{ t('chat.fsAuditModal.actions.restore') }}</button>
                </div>
                <div class="muted wrap" v-if="it.original_rel">
                  {{ t('chat.fsAuditModal.trash.originalPathDerived', { path: displayFsPathText(it.original_rel) }) }}
                </div>
              </div>
            </div>

            <div v-if="trashItems.length === 0" class="muted">{{ t('chat.fsAuditModal.trash.emptyFiltered') }}</div>
          </div>

          <div class="footer muted">{{ t('chat.fsAuditModal.trash.footer') }}</div>
        </div>

        <div v-else class="body">
          <div class="bar">
            <div class="field">
              <label class="chk">
                <input type="checkbox" v-model="dryRun" />
                <span>{{ t('chat.fsAuditModal.batch.dryRun') }}</span>
              </label>
            </div>
            <div class="field">
              <label class="chk">
                <input type="checkbox" v-model="stopOnError" />
                <span>{{ t('chat.fsAuditModal.batch.stopOnError') }}</span>
              </label>
            </div>
            <div class="field right">
              <button class="btn" @click="runBatch" :disabled="busy">{{ t('chat.fsAuditModal.batch.run') }}</button>
            </div>
          </div>

          <div class="bar">
            <button class="btn" @click="applyTemplate('create_only')">{{ t('chat.fsAuditModal.batch.templateCreateOnly') }}</button>
            <button class="btn" @click="applyTemplate('create_update')">{{ t('chat.fsAuditModal.batch.templateCreateUpdate') }}</button>
            <button class="btn" @click="applyTemplate('demo_delete')">{{ t('chat.fsAuditModal.batch.templateDemoDelete') }}</button>
          </div>

          <textarea class="textarea" v-model="batchJson" spellcheck="false"></textarea>

          <div class="bar">
            <div class="field grow">
              <span class="label">{{ t('chat.fsAuditModal.batch.confirmLabel') }}</span>
              <input class="input" v-model="confirmText" :placeholder="t('chat.fsAuditModal.batch.confirmPlaceholder')" />
            </div>
          </div>

          <div v-if="err" class="err">{{ err }}</div>

          <div v-if="batchResult" class="panel">
            <div class="muted">
              {{ t('chat.fsAuditModal.batch.resultMeta', { batchId: batchResult.batch_id, dryRun: String(!!batchResult.dry_run) }) }}
            </div>
            <pre class="pre">{{ prettyDisplay(batchResult) }}</pre>
          </div>

          <div class="footer muted">{{ t('chat.fsAuditModal.batch.footer') }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../../../composables/useMCP'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])
const { t } = useI18n()
const { callTool } = useMCP()

const tab = ref('audit')
const busy = ref(false)
const err = ref('')

function close() { emit('close') }

function unwrap(res) {
  if (res && typeof res === 'object' && res.data && typeof res.data === 'object') return res.data
  return res
}

function pretty(x) {
  try { return JSON.stringify(x, null, 2) } catch { return String(x) }
}


function displayFsText(value) {
  const text = String(value ?? '')
  if (!text) return ''
  return text.replace(/(^|[\s"'`(（\[【{:,=]|[📁←→])\/?agent_files(?=\/|$)/g, '$1user')
}


function displayFsPathText(value) {
  return displayFsText(String(value ?? '').trim())
}


function prettyDisplay(x) {
  return displayFsText(pretty(x))
}


function fsRequestPrefix(value) {
  const text = String(value ?? '').trim()
  if (!text) return ''
  if (text === 'user') return 'agent_files'
  if (text.startsWith('user/')) return `agent_files/${text.slice(5)}`
  if (text.startsWith('/user/')) return `agent_files/${text.slice(6)}`
  return text
}

function toast(message, type = 'info') {
  window.dispatchEvent(new CustomEvent('nisb-toast', { detail: { message, type } }))
}

function isDeleteConfirmToken(token) {
  const raw = String(token || '').trim()
  const lower = raw.toLowerCase()
  const localized = String(t('chat.fsAuditModal.common.deleteConfirmToken') || '').trim().toLowerCase()
  return lower === 'delete' || (!!localized && lower === localized)
}

/* ------------------ audit ------------------ */
const auditPrefix = ref('')
const auditLimit = ref(50)
const auditQuery = ref('')
const auditCursor = ref(null)
const auditHasMore = computed(() => !!auditCursor.value)
const auditRawEvents = ref([])

const auditEvents = computed(() => {
  const raw = Array.isArray(auditRawEvents.value) ? auditRawEvents.value : []
  const q = String(auditQuery.value || '').trim()
  if (!q) return raw
  return filter_audit_events(raw, q)
})

function auditKey(e) {
  return `${e.ts || ''}::${e.backup_id || ''}::${e.operation || e.event || ''}::${(e.paths || []).join('|')}`
}

function is_dir_move_path_event(e) {
  return !!(e && e.operation === 'dir_move_path' && e.metadata && e.metadata.old_path && e.metadata.new_path)
}

function _event_to_search_text(e) {
  try {
    const op = String(e?.operation || e?.event || '')
    const bid = String(e?.backup_id || '')
    const paths = Array.isArray(e?.paths) ? e.paths.join(' ') : ''
    const md = e?.metadata ? JSON.stringify(e.metadata) : ''
    const all = JSON.stringify(e)
    const raw = `${op} ${bid} ${paths} ${md} ${all}`
    return `${raw} ${displayFsText(raw)}`
  } catch {
    const raw = String(e || '')
    return `${raw} ${displayFsText(raw)}`
  }
}

function filter_audit_events(events, keyword) {
  const k = String(keyword || '').trim().toLowerCase()
  if (!k) return events
  return events.filter((e) => _event_to_search_text(e).toLowerCase().includes(k))
}

async function auditSearch(reset) {
  err.value = ''
  busy.value = true
  try {
    const q = String(auditQuery.value || '').trim()
    if (reset) auditCursor.value = null

    if (!q) {
      const r = unwrap(await callTool('nisb_fs_audit_tail', { prefix: fsRequestPrefix(auditPrefix.value), limit: auditLimit.value }))
      const events = Array.isArray(r?.events) ? r.events : (Array.isArray(r?.data?.events) ? r.data.events : [])
      auditRawEvents.value = events
      auditCursor.value = r?.next_cursor || null
      return
    }

    const r = unwrap(await callTool('nisb_fs_audit_search', {
      prefix: fsRequestPrefix(auditPrefix.value),
      q,
      limit: auditLimit.value,
      cursor: auditCursor.value
    }))
    const events = Array.isArray(r?.events) ? r.events : []
    auditRawEvents.value = reset ? events : [...auditRawEvents.value, ...events]
    auditCursor.value = r?.next_cursor || null
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

async function auditLoadMore() {
  await auditSearch(false)
}

async function restore_backup(backup_id, path) {
  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_restore_backup', { backup_id, path }))
    if (!r?.success) err.value = r?.message || t('chat.fsAuditModal.messages.restoreFailed')
    else toast(t('chat.fsAuditModal.messages.backupRestored'), 'success')

    await refreshAfterMutation()
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

function _safe_workspace_id_from_ls() {
  try {
    const wid = String(localStorage.getItem('nisb_current_workspace_id') || '').trim()
    if (wid && wid.startsWith('workspace_')) return wid
  } catch {}
  return ''
}

function _try_update_focus_root_after_path_change(old_prefix, new_prefix) {
  try {
    const wid = _safe_workspace_id_from_ls()
    if (!wid) return

    const key = `nisb_fs_focus_root_${wid}`
    const cur = String(localStorage.getItem(key) || '').trim().replace(/^\/+/, '')
    if (!cur) return

    const oldp = String(old_prefix || '').trim().replace(/^\/+/, '')
    const newp = String(new_prefix || '').trim().replace(/^\/+/, '')
    if (!oldp || !newp) return

    let next = cur
    if (cur === oldp) next = newp
    else if (cur.startsWith(oldp + '/')) next = newp + cur.slice(oldp.length)

    if (next !== cur) {
      localStorage.setItem(key, next)
      window.dispatchEvent(new CustomEvent('nisb_file_focus_root', { detail: { path: next } }))
    }
  } catch {}
}

async function restore_dir_move_path(e) {
  const old_path = String(e?.metadata?.old_path || '').trim()
  const new_path = String(e?.metadata?.new_path || '').trim()
  if (!old_path || !new_path) return

  const ok = window.confirm(
    t('chat.fsAuditModal.prompts.restoreDirRename', {
      from: displayFsPathText(new_path),
      to: displayFsPathText(old_path)
    })
  )
  if (!ok) return

  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_dir_move_path', { old_path: new_path, new_path: old_path }))
    if (!r?.success) {
      err.value = r?.message || t('chat.fsAuditModal.messages.restoreRenameFailed')
      return
    }

    window.dispatchEvent(new CustomEvent('nisb_path_renamed', {
      detail: { old_path: new_path, new_path: old_path, type: 'directory' }
    }))
    _try_update_focus_root_after_path_change(new_path, old_path)

    toast(t('chat.fsAuditModal.messages.renameRestored'), 'success')

    await refreshAfterMutation()
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-favorites-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
  } catch (e2) {
    err.value = e2?.message || String(e2)
  } finally {
    busy.value = false
  }
}

/* ------------------ backups stats + purge ------------------ */
const backupsStats = ref(null)
const backupsLoading = ref(false)

function _formatBytes(n) {
  const x = Number(n || 0)
  if (!isFinite(x) || x <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = x
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1 }
  return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`
}

const backupsStatsText = computed(() => {
  const s = backupsStats.value
  if (!s || typeof s !== 'object') return t('chat.fsAuditModal.audit.backups.notCounted')
  const cnt = s.backups_count ?? s.backupsCount ?? 0
  const bytes = s.size_bytes ?? s.sizeBytes ?? 0
  return t('chat.fsAuditModal.audit.backups.statsText', {
    count: cnt,
    size: _formatBytes(bytes)
  })
})

async function loadBackupsStats() {
  backupsLoading.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_backups_stats', {}))
    if (r?.success === false) {
      toast(r?.message || t('chat.fsAuditModal.messages.statsFailed'), 'error')
      return
    }
    backupsStats.value = r
  } catch (e) {
    toast(e?.message || String(e), 'error')
  } finally {
    backupsLoading.value = false
  }
}

async function purgeAllBackups() {
  const token = prompt(t('chat.fsAuditModal.prompts.purgeAllBackups'), '')
  if (!token) return
  if (!isDeleteConfirmToken(token)) return

  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_backups_purge_all', { confirm_token: String(token).trim() }))
    if (!r?.success) {
      err.value = r?.message || t('chat.fsAuditModal.messages.purgeBackupsFailed')
      toast(err.value, 'error')
      return
    }
    toast(r?.message || t('chat.fsAuditModal.messages.backupsPurged'), 'success')
    await refreshAfterMutation()
  } catch (e) {
    err.value = e?.message || String(e)
    toast(err.value, 'error')
  } finally {
    busy.value = false
  }
}

/* ------------------ snapshot ------------------ */
const snapDepth = ref(2)
const snapIncludeHidden = ref(false)
const snapshot = ref(null)

async function loadSnapshot() {
  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_snapshot', {
      path: 'agent_files',
      depth: snapDepth.value,
      include_hidden: !!snapIncludeHidden.value
    }))
    snapshot.value = r
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

/* ------------------ trash ------------------ */
const trashQuery = ref('')
const trashItems = ref([])
const trashBatchQuery = ref('')
const trashBatches = ref([])
const trashBatchLoading = ref(false)
const openBulkId = ref('')
const batchDetailLoading = ref(false)
const batchDetail = ref({ total: 0, offset: 0, limit: 200, items: [] })
const batchDetailQuery = ref('')

async function loadTrash() {
  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_trash_list', { query: trashQuery.value, limit: 200 }))
    trashItems.value = Array.isArray(r.items) ? r.items : []
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

async function loadTrashBatches() {
  trashBatchLoading.value = true
  try {
    const res = await callTool('nisb_fs_trash_batches_list', {
      limit: 80,
      query: trashBatchQuery.value,
      include_items_preview: true,
      preview_limit: 8
    })
    trashBatches.value = (res && res.success && Array.isArray(res.items)) ? res.items : []
    if (openBulkId.value) {
      const exists = trashBatches.value.some(b => b.bulk_id === openBulkId.value)
      if (!exists) openBulkId.value = ''
    }
  } finally {
    trashBatchLoading.value = false
  }
}

async function toggleBatchDetail(bulkId) {
  if (openBulkId.value === bulkId) {
    openBulkId.value = ''
    return
  }
  openBulkId.value = bulkId
  batchDetailQuery.value = ''
  batchDetail.value = { total: 0, offset: 0, limit: 200, items: [] }
  await loadBatchDetail()
}

async function loadBatchDetail(offset = 0) {
  if (!openBulkId.value) return
  batchDetailLoading.value = true
  try {
    const res = await callTool('nisb_fs_trash_batch_get', {
      bulk_id: openBulkId.value,
      query: batchDetailQuery.value,
      offset,
      limit: batchDetail.value.limit || 200
    })
    if (res && res.success) {
      batchDetail.value = {
        total: res.total || 0,
        offset: res.offset || 0,
        limit: res.limit || 200,
        items: Array.isArray(res.items) ? res.items : []
      }
    } else {
      toast(
        t('chat.fsAuditModal.messages.loadBatchDetailFailed', {
          error: res?.message || t('chat.fsAuditModal.common.unknownError')
        }),
        'error'
      )
    }
  } finally {
    batchDetailLoading.value = false
  }
}

async function restoreTrashBatch(bulkId) {
  if (!bulkId) return
  const res = await callTool('nisb_fs_bulk_restore', { bulk_id: bulkId, overwrite: false })
  if (res && res.success) {
    toast(t('chat.fsAuditModal.messages.batchRestored', { id: bulkId }), 'success')
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    await loadTrashBatches()
  } else {
    toast(
      t('chat.fsAuditModal.messages.restoreFailedWithError', {
        error: res?.message || t('chat.fsAuditModal.common.unknownError')
      }),
      'error'
    )
  }
}

async function restoreTrashItem(it) {
  const trashRel = it?.trash_rel
  const restoreTo = it?.original_rel
  if (!trashRel || !restoreTo) return

  const res = await callTool('nisb_fs_trash_restore', {
    trash_rel: trashRel,
    restore_to: restoreTo,
    overwrite: false
  })
  if (res && res.success) {
    toast(t('chat.fsAuditModal.messages.itemRestored', { path: displayFsPathText(restoreTo) }), 'success')
    window.dispatchEvent(new CustomEvent('nisb-file-tree-refresh'))
    window.dispatchEvent(new CustomEvent('nisb-timeline-refresh'))
    await loadTrashBatches()
    await loadBatchDetail(batchDetail.value.offset || 0)
  } else {
    toast(
      t('chat.fsAuditModal.messages.restoreFailedWithError', {
        error: res?.message || t('chat.fsAuditModal.common.unknownError')
      }),
      'error'
    )
  }
}

async function purgeTrashBatch(bulkId) {
  if (!bulkId) return
  const token = prompt(t('chat.fsAuditModal.prompts.purgeTrashBatch', { id: bulkId }), '')
  if (!token) return
  if (!isDeleteConfirmToken(token)) return

  const res = await callTool('nisb_fs_trash_batch_purge', { bulk_id: bulkId })
  if (res && res.success) {
    toast(res.message || t('chat.fsAuditModal.messages.batchPurged', { id: bulkId }), 'success')
    if (openBulkId.value === bulkId) openBulkId.value = ''
    await loadTrashBatches()
  } else {
    toast(
      t('chat.fsAuditModal.messages.purgeFailedWithError', {
        error: res?.message || t('chat.fsAuditModal.common.unknownError')
      }),
      'error'
    )
  }
}

async function purgeTrashAll() {
  const token = prompt(t('chat.fsAuditModal.prompts.purgeTrashAll'), '')
  if (!token) return

  const res = await callTool('nisb_fs_trash_purge_all', { confirm_token: token })
  if (res && res.success) {
    toast(res.message || t('chat.fsAuditModal.messages.trashPurged'), 'success')
    openBulkId.value = ''
    await loadTrashBatches()
  } else {
    toast(res?.message || t('chat.fsAuditModal.messages.purgeFailed'), 'error')
  }
}

async function trashRestore(it) {
  err.value = ''
  busy.value = true
  try {
    const r = unwrap(await callTool('nisb_fs_trash_restore', { trash_rel: it.trash_rel }))
    if (!r?.success) err.value = r?.message || t('chat.fsAuditModal.messages.restoreFailed')
    else toast(t('chat.fsAuditModal.messages.restored'), 'success')
    await refreshAfterMutation()
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

/* ------------------ conversation trash ------------------ */
const convTrashBatchQuery = ref('')
const convTrashBatches = ref([])
const convTrashBatchLoading = ref(false)
const openConvBulkId = ref('')
const convBatchDetailLoading = ref(false)
const convBatchDetail = ref({ total: 0, offset: 0, limit: 200, items: [] })
const convBatchDetailQuery = ref('')

async function loadConvTrashBatches() {
  convTrashBatchLoading.value = true
  try {
    const res = await callTool('nisb_chat_conversation_trash_batches_list', {
      limit: 80,
      query: convTrashBatchQuery.value
    })
    convTrashBatches.value = (res && res.success && Array.isArray(res.items)) ? res.items : []
    if (openConvBulkId.value) {
      const exists = convTrashBatches.value.some(b => b.bulk_id === openConvBulkId.value)
      if (!exists) openConvBulkId.value = ''
    }
  } finally {
    convTrashBatchLoading.value = false
  }
}

async function toggleConvBatchDetail(bulkId) {
  if (openConvBulkId.value === bulkId) {
    openConvBulkId.value = ''
    return
  }
  openConvBulkId.value = bulkId
  convBatchDetailQuery.value = ''
  convBatchDetail.value = { total: 0, offset: 0, limit: 200, items: [] }
  await loadConvBatchDetail()
}

async function loadConvBatchDetail(offset = 0) {
  if (!openConvBulkId.value) return
  convBatchDetailLoading.value = true
  try {
    const res = await callTool('nisb_fs_trash_batch_get', {
      bulk_id: openConvBulkId.value,
      query: convBatchDetailQuery.value,
      offset,
      limit: convBatchDetail.value.limit || 200
    })
    if (res && res.success) {
      convBatchDetail.value = {
        total: res.total || 0,
        offset: res.offset || 0,
        limit: res.limit || 200,
        items: Array.isArray(res.items) ? res.items : []
      }
    } else {
      toast(
        t('chat.fsAuditModal.messages.loadConvBatchDetailFailed', {
          error: res?.message || t('chat.fsAuditModal.common.unknownError')
        }),
        'error'
      )
    }
  } finally {
    convBatchDetailLoading.value = false
  }
}

async function restoreConvBatch(bulkId) {
  if (!bulkId) return
  const res = await callTool('nisb_chat_conversation_trash_restore', { bulk_id: bulkId, overwrite: false })
  if (res && res.success) {
    toast(t('chat.fsAuditModal.messages.convBatchRestored', { id: bulkId }), 'success')
    window.dispatchEvent(new CustomEvent('nisb-conversations-refresh'))
    await loadConvTrashBatches()
  } else {
    toast(
      t('chat.fsAuditModal.messages.restoreFailedWithError', {
        error: res?.message || t('chat.fsAuditModal.common.unknownError')
      }),
      'error'
    )
  }
}

async function purgeConvBatch(bulkId) {
  if (!bulkId) return
  const token = prompt(t('chat.fsAuditModal.prompts.purgeConvBatch', { id: bulkId }), '')
  if (!token) return
  if (!isDeleteConfirmToken(token)) return

  const res = await callTool('nisb_chat_conversation_trash_batch_purge', { bulk_id: bulkId, confirm_token: token })
  if (res && res.success) {
    toast(res.message || t('chat.fsAuditModal.messages.convBatchPurged', { id: bulkId }), 'success')
    if (openConvBulkId.value === bulkId) openConvBulkId.value = ''
    await loadConvTrashBatches()
  } else {
    toast(
      t('chat.fsAuditModal.messages.purgeFailedWithError', {
        error: res?.message || t('chat.fsAuditModal.common.unknownError')
      }),
      'error'
    )
  }
}

async function purgeAllConvTrash() {
  const token = prompt(t('chat.fsAuditModal.prompts.purgeAllConvTrash'), '')
  if (!token) return

  const res = await callTool('nisb_chat_conversation_trash_purge_all', { confirm_token: token })
  if (res && res.success) {
    toast(res.message || t('chat.fsAuditModal.messages.convTrashPurged'), 'success')
    openConvBulkId.value = ''
    await loadConvTrashBatches()
  } else {
    toast(res?.message || t('chat.fsAuditModal.messages.purgeFailed'), 'error')
  }
}

/* ------------------ batch ------------------ */
const dryRun = ref(false)
const stopOnError = ref(true)
const confirmText = ref('')
const batchJson = ref('')
const batchResult = ref(null)

const TEMPLATES = {
  create_only: [{ op: 'file_create', filename: 'agent_files/batch_demo.txt', content: 'hi' }],
  create_update: [
    { op: 'file_create', filename: 'agent_files/batch_demo.txt', content: 'hi' },
    { op: 'file_update', filename: 'agent_files/batch_demo.txt', content: 'hi2' }
  ],
  demo_delete: [
    { op: 'file_create', filename: 'agent_files/batch_demo.txt', content: 'hi' },
    { op: 'file_delete', filename: 'agent_files/batch_demo.txt' }
  ]
}

function applyTemplate(name) {
  batchResult.value = null
  err.value = ''
  const ops = TEMPLATES[name] || []
  batchJson.value = JSON.stringify({ ops }, null, 2)
}

function parseBatchJson(text) {
  const obj = JSON.parse(text)
  if (Array.isArray(obj)) return { ops: obj }
  if (obj && Array.isArray(obj.ops)) return obj
  throw new Error(t('chat.fsAuditModal.messages.invalidBatchJson'))
}

async function runBatch() {
  err.value = ''
  batchResult.value = null

  let payload
  try {
    payload = parseBatchJson(batchJson.value)
  } catch (e) {
    err.value = e?.message || String(e)
    return
  }

  busy.value = true
  try {
    const req = { ...payload, dry_run: !!dryRun.value, stop_on_error: !!stopOnError.value }
    const c = String(confirmText.value || '').trim()
    if (c) req.confirm = c

    const r = unwrap(await callTool('nisb_fs_apply_batch', req))
    batchResult.value = r
    await refreshAfterMutation()
  } catch (e) {
    err.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

/* ------------------ shared refresh ------------------ */
async function refreshAfterMutation() {
  await Promise.allSettled([
    auditSearch(true),
    loadSnapshot(),
    loadTrash(),
    loadTrashBatches(),
    loadConvTrashBatches(),
    loadBackupsStats()
  ])
}

async function refreshActive() {
  if (tab.value === 'audit') return Promise.allSettled([auditSearch(true), loadBackupsStats()])
  if (tab.value === 'files') return loadSnapshot()
  if (tab.value === 'trash') return Promise.allSettled([loadTrash(), loadTrashBatches(), loadConvTrashBatches()])
  return refreshAfterMutation()
}

watch(() => props.open, (v) => {
  if (v) {
    tab.value = 'audit'
    auditSearch(true)
    loadBackupsStats()
    loadSnapshot()
    loadTrash()
    loadTrashBatches()
    loadConvTrashBatches()
    if (!batchJson.value) applyTemplate('create_update')
  } else {
    err.value = ''
  }
})

watch(trashBatches, (list) => {
  const cur = openBulkId.value
  if (!cur) return
  const exists = Array.isArray(list) && list.some(b => b.bulk_id === cur)
  if (!exists) {
    openBulkId.value = ''
    batchDetailQuery.value = ''
    batchDetail.value = { total: 0, offset: 0, limit: 200, items: [] }
  }
})

watch(convTrashBatches, (list) => {
  const cur = openConvBulkId.value
  if (!cur) return
  const exists = Array.isArray(list) && list.some(b => b.bulk_id === cur)
  if (!exists) {
    openConvBulkId.value = ''
    convBatchDetailQuery.value = ''
    convBatchDetail.value = { total: 0, offset: 0, limit: 200, items: [] }
  }
})
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 2147483000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  box-sizing: border-box;
  padding: 24px;
  background: color-mix(in srgb, #020617 24%, transparent);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.modal {
  width: min(1080px, 96vw);
  max-height: min(90vh, calc(100vh - 32px));
  min-height: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 18px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 8%, transparent), transparent 42%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 92%, transparent)
    );
  color: var(--text-main, #111827);
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 22px 68px rgba(0, 0, 0, 0.28);
  overflow: hidden;
}

.header {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin: 0.62rem 0.62rem 0;
  padding: 0.68rem;
  border: 1px solid color-mix(in srgb, var(--selected) 18%, var(--line));
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 26%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.title-wrap {
  flex: 1 1 auto;
  min-width: 0;
  display: grid;
  gap: 0.38rem;
}

.title {
  min-width: 0;
  color: var(--text-main, #111827);
  font-size: 0.94rem;
  font-weight: 830;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow-wrap: break-word;
}

.subtitle {
  min-width: 0;
  color: var(--text-secondary, #64748b);
  font-size: 0.76rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.status-row {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.status-chip,
.tab,
.op,
.active-chip {
  max-width: 100%;
  min-height: 23px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  padding: 0 0.52rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary, #64748b);
  font-size: 0.69rem;
  font-weight: 740;
  line-height: 1;
  white-space: normal;
  overflow-wrap: anywhere;
}

.status-chip.caution {
  border-color: color-mix(in srgb, #d97706 34%, var(--line));
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
  font-weight: 810;
}

.actions {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 0.42rem;
  flex-wrap: wrap;
  min-width: 0;
}

.tabs {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.42rem;
  margin: 0.58rem 0.62rem 0;
  padding: 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 42%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
}

.tab {
  min-height: 28px;
  cursor: pointer;
  font-family: inherit;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.14s ease;
}

.tab:hover,
.tab:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 38%, transparent);
  color: var(--selected);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
  outline: none;
}

.tab.active {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 52%, transparent);
  color: var(--selected);
  font-weight: 820;
}

.tab.caution:not(.active) {
  border-color: color-mix(in srgb, #d97706 24%, var(--line));
  color: color-mix(in srgb, #d97706 84%, var(--text-secondary));
}

.tab:active {
  transform: translateY(1px);
}

.body {
  flex: 1 1 auto;
  min-height: 0;
  display: block;
  padding: 0.62rem;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.body::-webkit-scrollbar {
  width: 8px;
}

.body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.bar {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.52rem;
  margin-bottom: 0.58rem;
  padding: 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
}

.field {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  flex: 0 0 auto;
}

.field.grow {
  flex: 1 1 320px;
  min-width: 220px;
}

.field.right {
  margin-left: auto;
}

.label {
  flex: 0 0 auto;
  color: var(--text-secondary, #64748b);
  font-size: 0.73rem;
  font-weight: 740;
  line-height: 1.35;
  white-space: nowrap;
}

.input,
.select {
  width: auto;
  min-width: 160px;
  min-height: 32px;
  box-sizing: border-box;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 11px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 62%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-main, #111827);
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 680;
  line-height: 1;
  outline: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.input::placeholder,
.textarea::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
  opacity: 0.92;
}

.input:focus,
.select:focus,
.textarea:focus {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--editor-bg) 66%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
}

.textarea {
  width: 100%;
  min-height: 220px;
  box-sizing: border-box;
  margin-bottom: 0.58rem;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 78%, transparent)
    );
  color: var(--text-main, #111827);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.76rem;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  overflow-wrap: anywhere;
}

.btn,
.mini {
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 84%, transparent)
    );
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.73rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.14s ease;
}

.btn:hover:not(:disabled),
.mini:hover:not(:disabled),
.btn:focus-visible,
.mini:focus-visible {
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

.btn:active:not(:disabled),
.mini:active:not(:disabled) {
  transform: translateY(1px);
}

.btn.ghost {
  background: color-mix(in srgb, var(--editor-bg) 30%, transparent);
}

.close-btn {
  width: 31px;
  padding: 0;
  font-size: 1rem;
  font-weight: 760;
}

.btn.danger,
.mini.danger {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.btn.danger:hover:not(:disabled),
.mini.danger:hover:not(:disabled),
.btn.danger:focus-visible,
.mini.danger:focus-visible {
  border-color: rgba(239, 68, 68, 0.46);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.08);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.list {
  min-width: 0;
  display: grid;
  gap: 0.56rem;
}

.audit-row,
.panel,
.item,
.subitem {
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 44%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.audit-row,
.panel {
  padding: 0.62rem;
}

.rowTop {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.42rem;
}

.op {
  min-height: 23px;
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, transparent);
  color: var(--selected);
  font-weight: 820;
}

.id,
.ts {
  min-width: 0;
  color: var(--text-secondary, #64748b);
  font-size: 0.72rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.id {
  flex: 1 1 240px;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

.ts {
  flex: 0 1 auto;
  margin-left: auto;
}

.paths {
  min-width: 0;
  display: grid;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.pathLine {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.48rem;
}

.path {
  flex: 1 1 360px;
  min-width: 160px;
  color: var(--text-main, #111827);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.72rem;
  line-height: 1.5;
}

.wrap {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.meta {
  min-width: 0;
  margin-top: 0.5rem;
}

.meta summary {
  cursor: pointer;
}

.pre {
  max-height: 360px;
  box-sizing: border-box;
  margin: 0.5rem 0 0;
  padding: 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 46%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-main, #111827);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.72rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
  overflow-wrap: anywhere;
  scrollbar-width: thin;
}

.panel {
  display: grid;
  gap: 0.5rem;
}

.muted {
  min-width: 0;
  color: var(--text-secondary, #64748b);
  font-size: 0.73rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.small {
  font-size: 0.72rem;
}

.err {
  margin-bottom: 0.58rem;
  padding: 0.62rem 0.68rem;
  border: 1px solid rgba(239, 68, 68, 0.32);
  border-radius: 13px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.78rem;
  font-weight: 690;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.footer {
  margin-top: 0.58rem;
  padding: 0.52rem 0.58rem;
  border: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 13px;
  background: color-mix(in srgb, var(--editor-bg) 32%, transparent);
}

.section {
  min-width: 0;
  display: grid;
  gap: 0.58rem;
  margin-bottom: 0.68rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 38%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 70%, transparent)
    );
}

.section-title {
  min-width: 0;
  color: var(--text-main, #111827);
  font-size: 0.8rem;
  font-weight: 810;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.item {
  display: flex;
  justify-content: space-between;
  gap: 0.62rem;
  padding: 0.62rem;
  flex-wrap: wrap;
}

.item-main {
  flex: 1 1 520px;
  min-width: 220px;
  display: grid;
  gap: 0.36rem;
}

.item-line {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.42rem;
}

.item-actions {
  flex: 0 1 auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 0.42rem;
  flex-wrap: wrap;
  min-width: 0;
}

.detail {
  min-width: 0;
  margin-top: 0.5rem;
  padding-top: 0.58rem;
  border-top: 1px dashed color-mix(in srgb, var(--line) 76%, transparent);
}

.subitem {
  display: flex;
  justify-content: space-between;
  gap: 0.58rem;
  padding: 0.56rem;
  flex-wrap: wrap;
}

.submain {
  flex: 1 1 520px;
  min-width: 220px;
  display: grid;
  gap: 0.26rem;
}

.subactions {
  display: flex;
  align-items: flex-start;
  gap: 0.42rem;
  flex-wrap: wrap;
}

.chk {
  min-height: 31px;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0 0.56rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
  color: var(--text-secondary, #64748b);
  cursor: pointer;
  font-size: 0.73rem;
  font-weight: 740;
  line-height: 1;
}

.chk input {
  margin: 0;
  accent-color: var(--selected);
  cursor: pointer;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 760px) {
  .overlay {
    padding: 12px;
  }

  .modal {
    width: 100%;
    max-height: calc(100vh - 24px);
    border-radius: 16px;
  }

  .header {
    flex-direction: column;
    align-items: stretch;
  }

  .actions {
    justify-content: flex-start;
  }

  .field {
    flex: 1 1 100%;
  }

  .field.grow {
    flex-basis: 100%;
    min-width: 0;
  }

  .field.right {
    margin-left: 0;
  }

  .input,
  .select {
    width: 100%;
    min-width: 0;
  }

  .ts {
    width: 100%;
    margin-left: 0;
  }

  .op {
    max-width: 100%;
  }

  .id {
    flex-basis: 100%;
    min-width: 0;
  }

  .item-actions,
  .subactions {
    justify-content: flex-start;
  }
}

@media (max-width: 560px) {
  .overlay {
    padding: 8px;
  }

  .modal {
    max-height: calc(100vh - 16px);
    border-radius: 14px;
  }

  .header,
  .tabs,
  .body {
    margin-left: 0.48rem;
    margin-right: 0.48rem;
  }

  .body {
    padding-left: 0;
    padding-right: 0;
  }

  .bar,
  .item,
  .subitem {
    align-items: stretch;
    flex-direction: column;
  }

  .btn,
  .mini,
  .tab {
    width: 100%;
  }

  .tabs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .path {
    flex-basis: 100%;
    min-width: 0;
  }

  .pathLine {
    align-items: flex-start;
  }

  .item-main,
  .submain {
    flex-basis: 100%;
    min-width: 0;
  }
}

@media (max-width: 420px) {
  .tabs {
    grid-template-columns: minmax(0, 1fr);
  }

  .actions,
  .item-actions,
  .subactions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

