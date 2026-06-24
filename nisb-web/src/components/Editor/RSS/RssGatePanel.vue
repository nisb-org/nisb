<template>
  <div ref="wrapEl" class="gate-wrap">
    <GateTopBar :gate="gate" @close="$emit('close')" />

    <div class="gate-body" :class="{ 'results-left': resultsPlacement === 'left' }">
      <div class="left-pane">
        <div class="left-scroll">
          <GateParamsPanel :gate="gate" />

          <div v-if="resultsPlacement === 'left'" class="left-results-sep"></div>
          <GateResultsList v-if="resultsPlacement === 'left'" :gate="gate" placement="left" />
        </div>
      </div>

      <div v-if="resultsPlacement === 'right'" class="right-pane">
        <div class="right-scroll">
          <GateResultsList :gate="gate" placement="right" />
        </div>
      </div>
    </div>

    <GateModals :gate="gate" />
  </div>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from "vue"
import useMCP from "../../../composables/useMCP"

import GateTopBar from "./Gate/GateTopBar.vue"
import GateParamsPanel from "./Gate/GateParamsPanel.vue"
import GateResultsList from "./Gate/GateResultsList.vue"
import GateModals from "./Gate/GateModals.vue"
import { useRssGateController } from "./Gate/composables/useRssGateController"

defineEmits(["close"])

const { callTool } = useMCP()

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

const gate = useRssGateController({ callTool, toast })

const wrapEl = ref(null)
const resultsPlacement = ref("right")
let ro = null

function computePlacement() {
  const wrapW = wrapEl.value?.clientWidth || 0
  const rightEl = wrapEl.value?.querySelector?.(".right-pane") || null
  const rightW = rightEl?.clientWidth || 0
  const estimatedRightW = wrapW > 0 ? Math.max(0, wrapW - 392) : 0
  const effectiveRightW = rightW > 0 ? rightW : estimatedRightW

  const forceLeftByWrap = wrapW > 0 && wrapW < 860
  const forceLeftByRight = effectiveRightW > 0 && effectiveRightW < 520
  const nextPlacement = forceLeftByWrap || forceLeftByRight ? "left" : "right"

  if (resultsPlacement.value !== nextPlacement) {
    resultsPlacement.value = nextPlacement
  }
}

onMounted(async () => {
  await gate.init()
  await nextTick()
  computePlacement()

  ro = new ResizeObserver(() => computePlacement())
  if (wrapEl.value) ro.observe(wrapEl.value)

  window.addEventListener("resize", computePlacement)
})

onUnmounted(() => {
  window.removeEventListener("resize", computePlacement)
  try {
    if (ro) ro.disconnect()
  } catch {}
  ro = null

  gate.dispose()
})
</script>

<style scoped>
.gate-wrap {
  position: relative;
  height: 100%;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 5%, transparent), transparent 38%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 98%, transparent),
      color-mix(in srgb, var(--editor-bg) 92%, var(--sidebar-bg))
    );
}

.gate-body {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  overflow: hidden;
}

.gate-body.results-left {
  grid-template-columns: minmax(0, 1fr);
}

.left-pane,
.right-pane {
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 16px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 72%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 12px 28px rgba(0, 0, 0, 0.06);
}

.left-pane {
  position: relative;
}

.left-pane::after {
  content: "";
  position: absolute;
  top: 14px;
  right: 0;
  bottom: 14px;
  width: 1px;
  pointer-events: none;
  background:
    linear-gradient(
      180deg,
      transparent,
      color-mix(in srgb, var(--selected) 16%, var(--line)),
      transparent
    );
  opacity: 0.48;
}

.gate-body.results-left .left-pane::after {
  display: none;
}

.right-pane {
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
}

.left-scroll,
.right-scroll {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.left-scroll {
  padding: 10px;
}

.right-scroll {
  padding: 10px;
}

.left-scroll::-webkit-scrollbar,
.right-scroll::-webkit-scrollbar {
  width: 8px;
}

.left-scroll::-webkit-scrollbar-thumb,
.right-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.left-results-sep {
  height: 1px;
  margin: 0.7rem 0.2rem;
  border: 0;
  background:
    linear-gradient(
      90deg,
      transparent,
      color-mix(in srgb, var(--selected) 18%, var(--line)),
      transparent
    );
  opacity: 0.78;
}

@media (max-width: 860px) {
  .gate-body {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr);
    gap: 10px;
    padding: 10px;
  }

  .left-pane,
  .right-pane {
    border-radius: 15px;
  }

  .left-pane::after {
    display: none;
  }
}

@media (max-width: 620px) {
  .gate-body {
    padding: 8px;
  }

  .left-scroll,
  .right-scroll {
    padding: 8px;
  }

  .left-pane,
  .right-pane {
    border-radius: 14px;
  }
}

@media (max-width: 420px) {
  .gate-body {
    padding: 6px;
  }

  .left-scroll,
  .right-scroll {
    padding: 6px;
  }
}
</style>
