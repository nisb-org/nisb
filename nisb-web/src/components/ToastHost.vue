<template>
  <TransitionGroup
    name="toast"
    tag="div"
    class="toast-stack"
    role="status"
    aria-live="polite"
    aria-atomic="true"
  >
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">
      <div class="left">
        <span class="icon">{{ iconOf(t.type) }}</span>
        <div class="msg">{{ t.message }}</div>
      </div>

      <div class="right">
        <button
          v-if="t.actionText && t.actionEvent"
          class="btn action"
          @click="fireAction(t)"
        >
          {{ t.actionText }}
        </button>
        <button class="btn close" @click="remove(t.id)">×</button>
      </div>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const toasts = ref([])
let seq = 0

function iconOf(type) {
  if (type === 'success') return '✅'
  if (type === 'error') return '❌'
  if (type === 'warning') return '⚠️'
  return 'ℹ️'
}

function remove(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

function push(detail) {
  const id = `toast_${++seq}_${Date.now()}`
  const t = {
    id,
    message: String(detail?.message || ''),
    type: detail?.type || 'info',
    duration: typeof detail?.duration === 'number' ? detail.duration : 3500,
    actionText: String(detail?.actionText || ''),
    actionEvent: String(detail?.actionEvent || ''),
    actionDetail: detail?.actionDetail || null
  }

  if (!t.message) return

  toasts.value.push(t)

  if (t.duration > 0) {
    setTimeout(() => remove(id), t.duration)
  }
}

function onToast(evt) {
  push(evt?.detail || {})
}

function fireAction(t) {
  try {
    window.dispatchEvent(new CustomEvent(t.actionEvent, { detail: t.actionDetail }))
  } finally {
    remove(t.id)
  }
}

onMounted(() => {
  window.addEventListener('nisb-toast', onToast)
})

onUnmounted(() => {
  window.removeEventListener('nisb-toast', onToast)
})
</script>

<style scoped>
.toast-stack{
  position: fixed;
  right: 16px;
  top: 4rem;
  bottom: auto;

  display: flex;
  flex-direction: column;
  gap: 10px;

  z-index: 100000;
  width: min(520px, calc(100vw - 32px));
}

.toast{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--line, rgba(0,0,0,0.12));
  background: var(--sidebar-bg, rgba(255,255,255,0.92));
  box-shadow: 0 10px 24px rgba(0,0,0,0.18);
}

.left{ display:flex; gap:10px; align-items:flex-start; flex: 1; }
.icon{ font-size: 16px; line-height: 1.2; margin-top: 1px; }
.msg{
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  color: var(--text-main, #111);
}

.right{ display:flex; gap:8px; align-items:center; }

.btn{
  border: 1px solid var(--line, rgba(0,0,0,0.12));
  background: transparent;
  color: var(--text-secondary, #444);
  border-radius: 10px;
  padding: 6px 10px;
  cursor: pointer;
}
.btn.action{ background: rgba(0,0,0,0.04); }
.btn.close{ width: 32px; text-align: center; padding: 6px 0; }

.toast.success{ border-left: 4px solid rgba(34,197,94,0.9); }
.toast.error{ border-left: 4px solid rgba(239,68,68,0.9); }
.toast.warning{ border-left: 4px solid rgba(245,158,11,0.9); }
.toast.info{ border-left: 4px solid rgba(59,130,246,0.9); }

/* TransitionGroup：enter/leave 应用到列表项本身 [page:1] */
.toast-enter-active{ animation: toastIn 0.22s ease-out; }
.toast-leave-active{ animation: toastOut 0.18s ease-in; }

@keyframes toastIn {
  from { transform: translateX(360px); opacity: 0; }
  to   { transform: translateX(0); opacity: 1; }
}
@keyframes toastOut {
  from { transform: translateX(0); opacity: 1; }
  to   { transform: translateX(360px); opacity: 0; }
}
</style>

