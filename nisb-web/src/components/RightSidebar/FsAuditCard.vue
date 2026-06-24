<template>
  <div class="card">
    <div class="header">
      <div class="title">{{ t('chat.fsAuditCard.title') }}</div>
      <button class="btn" @click="refresh" :disabled="loading">
        {{ t('chat.fsAuditCard.actions.refresh') }}
      </button>
    </div>

    <div v-if="loading" class="muted">{{ t('chat.fsAuditCard.states.loading') }}</div>
    <div v-else-if="events.length === 0" class="muted">{{ t('chat.fsAuditCard.states.empty') }}</div>

    <div v-else class="list">
      <div
        v-for="(e, idx) in events"
        :key="`${e.backup_id || e.id || 'event'}-${idx}`"
        class="row"
      >
        <div class="row-top">
          <span class="op">{{ e.action || e.operation || '-' }}</span>
          <span class="id">{{ e.backup_id || '-' }}</span>
        </div>

        <div class="paths">
          <div v-for="p in (e.paths || []).slice(0, 3)" :key="p" class="path">{{ p }}</div>
          <div v-if="(e.paths || []).length > 3" class="muted">
            {{ t('chat.fsAuditCard.states.more', { count: (e.paths || []).length - 3 }) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMCP } from '../../composables/useMCP'

const { t } = useI18n()
const { callTool } = useMCP()

const loading = ref(false)
const events = ref([])

function unwrap(res) {
  if (res && typeof res === 'object' && res.data && typeof res.data === 'object') {
    return res.data
  }
  return res
}

async function refresh() {
  loading.value = true
  try {
    const res = unwrap(await callTool('nisb_fs_audit_tail', { limit: 20 }))
    if (Array.isArray(res?.events)) {
      events.value = res.events
    } else {
      events.value = []
    }
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.card { padding: 0.8rem; border-top: 1px solid var(--line); }
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.6rem; }
.title { font-size: 0.9rem; color: var(--text-main); }
.btn { height: 28px; padding: 0 0.6rem; border: 1px solid var(--line); border-radius: 6px; background: transparent; color: var(--text-secondary); cursor: pointer; }
.btn:hover { background: var(--selected-bg); color: var(--selected); border-color: var(--selected); }
.muted { color: var(--text-secondary); font-size: 0.85rem; }
.list { display: flex; flex-direction: column; gap: 0.6rem; }
.row { padding: 0.6rem; border: 1px solid var(--line); border-radius: 8px; background: var(--editor-bg); }
.row-top { display: flex; gap: 0.5rem; align-items: center; }
.op { font-weight: 600; color: var(--selected); font-size: 0.85rem; }
.id { color: var(--text-secondary); font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.paths { margin-top: 0.4rem; display: flex; flex-direction: column; gap: 0.2rem; }
.path { font-family: monospace; font-size: 0.8rem; color: var(--text-main); opacity: 0.9; }
</style>
