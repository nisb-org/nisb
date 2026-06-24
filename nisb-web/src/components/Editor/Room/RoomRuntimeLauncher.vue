<template>
  <div
    v-if="visible"
    class="room-runtime-launcher"
    :class="{
      live,
      error: !!error,
    }"
  >
    <div class="room-runtime-launcher-main">
      <span class="room-runtime-launcher-icon">●</span>

      <span class="room-runtime-launcher-title">
        运行摘要
      </span>

      <span
        v-if="process_count > 0"
        class="room-runtime-launcher-chip"
      >
        {{ process_count }} 事件
      </span>

      <span
        v-if="last_stage_text"
        class="room-runtime-launcher-chip subtle"
      >
        {{ last_stage_text }}
      </span>

      <span
        v-if="run_id"
        class="room-runtime-launcher-chip mono"
      >
        {{ short_run_id }}
      </span>
    </div>

    <div class="room-runtime-launcher-right">
      <span
        class="room-runtime-launcher-state"
        :class="{
          live,
          error: !!error,
        }"
      >
        {{ computed_status_text }}
      </span>

      <button
        type="button"
        class="room-runtime-launcher-refresh"
        :disabled="loading"
        @click="$emit('refresh')"
      >
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: true },
  loading: { type: Boolean, default: false },
  live: { type: Boolean, default: false },
  error: { type: String, default: '' },
  status_text: { type: String, default: '' },
  run_id: { type: String, default: '' },
  process_count: { type: Number, default: 0 },
  last_stage_text: { type: String, default: '' },
})

defineEmits(['refresh'])
</script>

<style scoped>
.room-runtime-launcher {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 1rem 0.55rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent) 0%,
      color-mix(in srgb, var(--editor-bg) 98%, transparent) 100%
    );
}

.room-runtime-launcher-main {
  min-width: 0;
  flex: 1 1 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.room-runtime-launcher-icon {
  color: var(--selected);
  font-size: 0.72rem;
  line-height: 1;
}

.room-runtime-launcher-title {
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--text-main);
}

.room-runtime-launcher-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-secondary);
  font-size: 0.72rem;
  white-space: nowrap;
}

.room-runtime-launcher-chip.subtle {
  background: color-mix(in srgb, var(--sidebar-bg) 86%, transparent);
}

.room-runtime-launcher-chip.mono {
  font-family: var(--font-mono, monospace);
}

.room-runtime-launcher-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.room-runtime-launcher-state {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 0.62rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: color-mix(in srgb, var(--editor-bg) 96%, transparent);
  color: var(--text-secondary);
  font-size: 0.74rem;
  white-space: nowrap;
}

.room-runtime-launcher-state.live {
  border-color: rgba(74, 118, 255, 0.22);
  background: rgba(74, 118, 255, 0.1);
  color: #5e84ff;
}

.room-runtime-launcher-state.error {
  border-color: rgba(208, 95, 95, 0.25);
  background: rgba(208, 95, 95, 0.1);
  color: #d05f5f;
}

.room-runtime-launcher-refresh {
  height: 30px;
  padding: 0 0.78rem;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--editor-bg);
  color: var(--text-main);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  transition: all var(--transition-normal);
}

.room-runtime-launcher-refresh:hover:not(:disabled) {
  border-color: var(--selected);
  background: var(--selected-bg);
}

.room-runtime-launcher-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 980px) {
  .room-runtime-launcher {
    flex-direction: column;
    align-items: stretch;
    padding: 0.65rem 0.75rem 0.55rem;
  }

  .room-runtime-launcher-right {
    justify-content: space-between;
  }
}

@media (max-width: 720px) {
  .room-runtime-launcher-main {
    flex-wrap: wrap;
  }

  .room-runtime-launcher-right {
    width: 100%;
  }
}
</style>

