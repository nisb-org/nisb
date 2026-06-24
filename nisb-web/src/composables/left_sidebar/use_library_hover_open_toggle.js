import { ref } from 'vue'

const STORAGE_KEY = 'nisb_left_sidebar_hover_open_v1'

export function use_library_hover_open_toggle() {
  const hover_open_enabled = ref(true)

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === '0') hover_open_enabled.value = false
    if (raw === '1') hover_open_enabled.value = true
  } catch {}

  function set_hover_open_enabled(v) {
    hover_open_enabled.value = !!v
    try {
      localStorage.setItem(STORAGE_KEY, hover_open_enabled.value ? '1' : '0')
    } catch {}
  }

  function toggle_hover_open_enabled() {
    set_hover_open_enabled(!hover_open_enabled.value)
  }

  return {
    hover_open_enabled,
    set_hover_open_enabled,
    toggle_hover_open_enabled
  }
}

