import { ref } from 'vue'

const STORAGE_KEY = 'nisb_file_space_settings_v1'

function load_settings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) || {}
  } catch {
    return {}
  }
}

function save_settings(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data || {}))
  } catch {}
}

const _loaded = load_settings()

// 默认：关闭“悬停展开/折叠”（更符合你说的“应该取消”，但用户可在齿轮里重新开启）
const hover_expand_enabled = ref(
  typeof _loaded.hover_expand_enabled === 'boolean' ? _loaded.hover_expand_enabled : false
)

export function use_file_space_settings() {
  function persist() {
    save_settings({
      hover_expand_enabled: hover_expand_enabled.value
    })
  }

  function set_hover_expand_enabled(v) {
    hover_expand_enabled.value = !!v
    persist()
  }

  return {
    hover_expand_enabled,
    set_hover_expand_enabled
  }
}

