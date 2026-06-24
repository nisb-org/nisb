<template>
  <div class="topbar">
    <div class="left">
      <button class="btn ghost" type="button" @click="$emit('close')">
        {{ t('rss.center.gate.topbar.back') }}
      </button>

      <div class="title-block">
        <div class="title">{{ t('rss.center.gate.topbar.title') }}</div>
        <div class="status-row">
          <span class="status-chip" :class="{ active: gate.state.searchWorking }">
            {{ gate.state.searchWorking ? t('rss.center.gate.topbar.searching') : t('rss.center.gate.topbar.search') }}
          </span>
        </div>
      </div>
    </div>

    <div class="spacer"></div>

    <div class="actions">
      <button
        class="btn"
        :class="{ busy: busyCache }"
        type="button"
        :disabled="gate.state.searchWorking || busyAny"
        @click="clear_backend_rss_caches"
        :title="t('rss.center.gate.topbar.clearCacheTitle')"
      >
        {{ busyCache ? t('rss.center.gate.topbar.clearing') : t('rss.center.gate.topbar.clearCache') }}
      </button>

      <button
        class="btn"
        :class="{ busy: busyCleanup }"
        type="button"
        :disabled="gate.state.searchWorking || busyAny"
        @click="run_manual_cleanup"
        :title="t('rss.center.gate.topbar.cleanupTitle')"
      >
        {{ busyCleanup ? t('rss.center.gate.topbar.cleaning') : t('rss.center.gate.topbar.cleanupOldData') }}
      </button>

      <button
        class="btn"
        :class="{ busy: busyAuto }"
        type="button"
        :disabled="gate.state.searchWorking || busyAny"
        @click="open_auto_cleanup_settings"
        :title="t('rss.center.gate.topbar.autoCleanupTitle')"
      >
        {{ busyAuto ? t('rss.center.gate.topbar.setting') : t('rss.center.gate.topbar.autoCleanup') }}
      </button>

      <button
        class="btn primary"
        type="button"
        :disabled="gate.state.searchWorking || busyAny"
        @click="gate.actions.runSearch(true)"
      >
        {{ gate.state.searchWorking ? t('rss.center.gate.topbar.searching') : t('rss.center.gate.topbar.search') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"
import { useI18n } from "vue-i18n"
import { useMCP } from "../../../../composables/useMCP"

defineEmits(["close"])
defineProps({
  gate: { type: Object, required: true },
})

const { t } = useI18n()
const { callTool } = useMCP()

const busyCache = ref(false)
const busyCleanup = ref(false)
const busyAuto = ref(false)
const busyAny = computed(() => busyCache.value || busyCleanup.value || busyAuto.value)

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function is_ok(r) {
  return !!(r && (r.success === true || r.status === "success"))
}

function toMB(bytes) {
  const n = Number(bytes || 0)
  return (n / 1024 / 1024).toFixed(1)
}

function clampInt(v, minV, maxV, defV) {
  const n = Number.parseInt(String(v ?? ""), 10)
  if (!Number.isFinite(n)) return defV
  return Math.max(minV, Math.min(maxV, n))
}

async function clear_backend_rss_caches() {
  const ok = window.confirm(t("rss.center.gate.confirm.clearCache"))
  if (!ok) return

  busyCache.value = true
  try {
    const r = await callTool("nisb_rss_cache_clear", { gc_collect: true })
    if (is_ok(r)) {
      toast(t("rss.center.gate.messages.clearCacheSuccess"), "success")
      try {
        await callTool("nisb_rss_cache_stats", {})
      } catch {}
    } else {
      toast(
        t("rss.center.gate.messages.clearCacheFailed", {
          error: String(r?.message || r?.detail || t("rss.center.gate.messages.unknownError")),
        }),
        "error"
      )
    }
  } catch (e) {
    toast(
      t("rss.center.gate.messages.clearCacheError", {
        error: e?.message || String(e),
      }),
      "error"
    )
  } finally {
    busyCache.value = false
  }
}

async function run_manual_cleanup() {
  const prev = window.localStorage.getItem("nisb_rss_cleanup_keep_days") || "7"
  const keepDaysStr = window.prompt(t("rss.center.gate.prompts.keepDays"), prev)
  if (keepDaysStr == null) return
  const keep_days = clampInt(keepDaysStr, 1, 365, 7)
  window.localStorage.setItem("nisb_rss_cleanup_keep_days", String(keep_days))

  const rebuildOk = window.confirm(t("rss.center.gate.confirm.rebuildIndex"))
  const rebuild_index = !!rebuildOk

  const dryRunOk = window.confirm(t("rss.center.gate.confirm.dryRunFirst"))
  const dry_run = !!dryRunOk

  busyCleanup.value = true
  try {
    const r1 = await callTool("nisb_rss_data_cleanup", {
      keep_days,
      dry_run,
      rebuild_index,
      delete_logs_before_days: 0,
    })

    const data1 = r1?.data || r1
    if (!is_ok(r1) || !data1?.success) {
      toast(
        t("rss.center.gate.messages.cleanupFailed", {
          error: String(data1?.message || r1?.message || r1?.detail || t("rss.center.gate.messages.unknownError")),
        }),
        "error"
      )
      return
    }

    toast(
      t("rss.center.gate.messages.cleanupStatsDone", {
        before: toMB(data1.before_bytes),
        after: toMB(data1.after_bytes),
        deleted_dirs: data1.deleted_dirs || 0,
        rebuild: String(data1.rebuild_index),
      }),
      "success"
    )

    if (dry_run) {
      const go = window.confirm(t("rss.center.gate.confirm.executeCleanup"))
      if (!go) return

      const r2 = await callTool("nisb_rss_data_cleanup", {
        keep_days,
        dry_run: false,
        rebuild_index,
        delete_logs_before_days: 0,
      })
      const data2 = r2?.data || r2
      if (!is_ok(r2) || !data2?.success) {
        toast(
          t("rss.center.gate.messages.cleanupExecuteFailed", {
            error: String(data2?.message || r2?.message || r2?.detail || t("rss.center.gate.messages.unknownError")),
          }),
          "error"
        )
        return
      }

      toast(
        t("rss.center.gate.messages.cleanupDone", {
          before: toMB(data2.before_bytes),
          after: toMB(data2.after_bytes),
          deleted_dirs: data2.deleted_dirs || 0,
        }),
        "success"
      )
    }

    try {
      await callTool("nisb_rss_cache_clear", { gc_collect: true })
    } catch {}
  } catch (e) {
    toast(
      t("rss.center.gate.messages.cleanupError", {
        error: e?.message || String(e),
      }),
      "error"
    )
  } finally {
    busyCleanup.value = false
  }
}

async function open_auto_cleanup_settings() {
  busyAuto.value = true
  try {
    let cur = null
    try {
      const r = await callTool("nisb_rss_auto_cleanup_config_get", {})
      cur = r?.data || r
    } catch {
      cur = null
    }

    const enabledNow = !!cur?.enabled
    const keepDaysNow = clampInt(cur?.keep_days, 1, 365, 7)
    const intervalHoursNow = clampInt(cur?.interval_hours, 1, 168, 24)

    const enableStr = window.prompt(
      t("rss.center.gate.prompts.enableAutoCleanup"),
      enabledNow ? "1" : "0"
    )
    if (enableStr == null) return
    const enabled = String(enableStr).trim() !== "0"

    if (!enabled) {
      const ok = window.confirm(t("rss.center.gate.confirm.disableAutoCleanup"))
      if (!ok) return

      const rDel = await callTool("nisb_rss_auto_cleanup_config_delete", {})
      if (is_ok(rDel)) {
        toast(t("rss.center.gate.messages.autoCleanupDisabled"), "success")
      } else {
        toast(
          t("rss.center.gate.messages.disableAutoCleanupFailed", {
            error: String(rDel?.message || rDel?.detail || t("rss.center.gate.messages.unknownError")),
          }),
          "error"
        )
      }
      return
    }

    const keepDaysStr = window.prompt(
      t("rss.center.gate.prompts.autoCleanupKeepDays"),
      String(keepDaysNow)
    )
    if (keepDaysStr == null) return
    const keep_days = clampInt(keepDaysStr, 1, 365, keepDaysNow)

    const intervalStr = window.prompt(
      t("rss.center.gate.prompts.autoCleanupIntervalHours"),
      String(intervalHoursNow)
    )
    if (intervalStr == null) return
    const interval_hours = clampInt(intervalStr, 1, 168, intervalHoursNow)

    const rebuildOk = window.confirm(t("rss.center.gate.confirm.autoCleanupRebuildIndex"))
    const rebuild_index = !!rebuildOk

    const rSet = await callTool("nisb_rss_auto_cleanup_config_set", {
      enabled: true,
      keep_days,
      interval_hours,
      rebuild_index,
      delete_logs_before_days: 0,
    })
    const dataSet = rSet?.data || rSet
    if (is_ok(rSet) && dataSet?.success) {
      toast(
        t("rss.center.gate.messages.autoCleanupSaved", {
          keep_days: dataSet.keep_days,
          interval_hours: dataSet.interval_hours,
          next_run_at: dataSet.next_run_at || "",
        }),
        "success"
      )
    } else {
      toast(
        t("rss.center.gate.messages.saveAutoCleanupFailed", {
          error: String(dataSet?.message || rSet?.message || rSet?.detail || t("rss.center.gate.messages.unknownError")),
        }),
        "error"
      )
      return
    }

    const runNow = window.confirm(t("rss.center.gate.confirm.runAutoCleanupNow"))
    if (runNow) {
      const rNow = await callTool("nisb_rss_auto_cleanup_run_now", {})
      const dNow = rNow?.data || rNow
      if (is_ok(rNow) && dNow?.success) {
        toast(
          t("rss.center.gate.messages.autoCleanupRunNowDone", {
            before: toMB(dNow.before_bytes),
            after: toMB(dNow.after_bytes),
          }),
          "success"
        )
      } else {
        toast(
          t("rss.center.gate.messages.runAutoCleanupNowFailed", {
            error: String(dNow?.message || rNow?.message || rNow?.detail || t("rss.center.gate.messages.unknownError")),
          }),
          "error"
        )
      }
    }
  } catch (e) {
    toast(
      t("rss.center.gate.messages.autoCleanupError", {
        error: e?.message || String(e),
      }),
      "error"
    )
  } finally {
    busyAuto.value = false
  }
}
</script>

<style scoped>
.topbar {
  --nisb-gate-bar-height: 52px;

  position: relative;
  z-index: 3;
  flex: 0 0 auto;
  min-width: 0;
  min-height: var(--nisb-gate-bar-height);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.48rem 0.7rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 96%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 10px 24px rgba(0, 0, 0, 0.04);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.topbar::-webkit-scrollbar {
  display: none;
}

.topbar::after {
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 18%, var(--line)),
      transparent
    );
  opacity: 0.62;
}

.left {
  flex: 1 1 auto;
  min-width: 220px;
  display: inline-flex;
  align-items: center;
  gap: 0.7rem;
}

.title-block {
  min-width: 0;
  display: grid;
  gap: 0.14rem;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.9rem;
  font-weight: 820;
  line-height: 1.25;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.32rem;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 21px;
  box-sizing: border-box;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
}

.status-chip.active {
  border-color: color-mix(in srgb, var(--selected) 30%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
}

.spacer {
  flex: 0 0 0;
}

.actions {
  flex: 0 0 auto;
  min-width: max-content;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.42rem;
}

.btn {
  min-height: 31px;
  box-sizing: border-box;
  padding: 0 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 90%, transparent);
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
  font-weight: 760;
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

.btn.ghost {
  background: color-mix(in srgb, var(--editor-bg) 30%, transparent);
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.btn.busy {
  border-color: color-mix(in srgb, var(--selected) 34%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
}

@media (max-width: 900px) {
  .topbar {
    align-items: stretch;
    flex-wrap: wrap;
    overflow-x: hidden;
    overflow-y: visible;
  }

  .left {
    flex: 1 1 100%;
    min-width: 0;
  }

  .actions {
    flex: 1 1 100%;
    min-width: 0;
    overflow-x: auto;
    overflow-y: hidden;
    padding-bottom: 1px;
    scrollbar-width: none;
  }

  .actions::-webkit-scrollbar {
    display: none;
  }
}

@media (max-width: 520px) {
  .topbar {
    padding: 0.45rem;
  }

  .left {
    align-items: stretch;
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.45rem;
  }

  .btn {
    width: 100%;
    white-space: normal;
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
