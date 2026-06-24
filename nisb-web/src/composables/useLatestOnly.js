// /opt/mcp-gateway/nisb-web/src/composables/useLatestOnly.js
import { ref } from 'vue'

export function useLatestOnly() {
  const seq = ref(0)
  const controller = ref(null)

  function begin() {
    seq.value += 1
    const id = seq.value

    if (controller.value) {
      try { controller.value.abort() } catch {}
    }
    controller.value = new AbortController()

    return {
      id,
      signal: controller.value.signal,
      isStale: () => id !== seq.value,
      abort: () => { try { controller.value.abort() } catch {} },
    }
  }

  return { begin }
}

