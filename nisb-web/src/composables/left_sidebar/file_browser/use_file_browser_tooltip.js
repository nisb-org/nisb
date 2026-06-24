import { ref } from 'vue'
import { clamp } from './file_browser_utils'
import { to_user_visible_path } from './file_path_display'

export function use_file_browser_tooltip() {
  const path_tip = ref({ visible: false, text: '', x: 0, y: 0 })

  function position_tip_from_event(e) {
    const margin = 12
    const offset_x = 14
    const offset_y = 18
    path_tip.value.x = clamp(e.clientX + offset_x, margin, window.innerWidth - margin - 40)
    path_tip.value.y = clamp(e.clientY + offset_y, margin, window.innerHeight - margin - 24)
  }

  function on_fav_enter(fav, e) {
    const real_path = String(fav?.path || '').trim()
    const text = to_user_visible_path(real_path)
    if (!text) return
    path_tip.value.visible = true
    path_tip.value.text = text
    position_tip_from_event(e)
  }

  function on_fav_move(e) {
    if (!path_tip.value.visible) return
    position_tip_from_event(e)
  }

  function on_fav_leave() {
    path_tip.value.visible = false
  }

  return {
    path_tip,
    on_fav_enter,
    on_fav_move,
    on_fav_leave
  }
}
