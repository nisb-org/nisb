import { nextTick, ref } from 'vue'

export function use_library_list_scroll_anchor() {
  const library_list_el = ref(null)
  const _row_map = new Map()

  let _anchor_seq = 0
  let _anchor_id = ''
  let _t1 = null
  let _t2 = null

  let _bound = false
  let _on_transition_end = null
  let _on_wheel = null
  let _on_touchmove = null
  let _on_pointerdown = null
  let _on_scroll = null

  let _user_interrupted = false
  let _programmatic_until = 0

  function set_library_row_el(library_id, el) {
    const id = String(library_id || '')
    if (!id) return
    if (el) _row_map.set(id, el)
    else _row_map.delete(id)
  }

  function _clear_timers() {
    if (_t1) clearTimeout(_t1)
    if (_t2) clearTimeout(_t2)
    _t1 = null
    _t2 = null
  }

  function _interrupt_anchor(reason = 'unknown') {
    _user_interrupted = true
    _anchor_id = ''
    _anchor_seq++
    _clear_timers()
    void reason
  }

  function _mark_programmatic_scroll(behavior) {
    const now = Date.now()
    const extra = behavior === 'smooth' ? 900 : 220
    _programmatic_until = Math.max(_programmatic_until, now + extra)
  }

  function _do_scroll(library_id, { behavior = 'auto', offset = 6 } = {}) {
    const id = String(library_id || '')
    const list = library_list_el.value
    const row = _row_map.get(id)
    if (!id || !list || !row) return

    const list_rect = list.getBoundingClientRect()
    const row_rect = row.getBoundingClientRect()
    const delta = row_rect.top - list_rect.top
    const target = Math.max(0, list.scrollTop + delta - offset)

    _mark_programmatic_scroll(behavior)

    try {
      list.scrollTo({ top: target, behavior })
    } catch {
      list.scrollTop = target
    }
  }

  async function request_anchor_to_top(library_id, { offset = 6 } = {}) {
    const id = String(library_id || '')
    if (!id) return

    // ✅ 点击展开触发时：重新允许自动归位
    _user_interrupted = false
    _anchor_id = id
    const seq = ++_anchor_seq

    _clear_timers()

    await nextTick()
    if (seq !== _anchor_seq) return
    if (_user_interrupted) return
    _do_scroll(id, { behavior: 'smooth', offset })

    await nextTick()
    if (seq !== _anchor_seq) return
    if (_user_interrupted) return
    _do_scroll(id, { behavior: 'auto', offset })

    _t1 = setTimeout(() => {
      if (seq !== _anchor_seq) return
      if (_user_interrupted) return
      _do_scroll(id, { behavior: 'auto', offset })
    }, 180)

    _t2 = setTimeout(() => {
      if (seq !== _anchor_seq) return
      if (_user_interrupted) return
      _do_scroll(id, { behavior: 'auto', offset })
    }, 420)
  }

  function attach_transitionend_stabilizer() {
    if (_bound) return
    const list = library_list_el.value
    if (!list) return
    _bound = true

    _on_wheel = () => _interrupt_anchor('wheel')
    _on_touchmove = () => _interrupt_anchor('touchmove')
    _on_pointerdown = () => _interrupt_anchor('pointerdown')

    _on_scroll = () => {
      const now = Date.now()
      // 忽略我们自己 scrollTo 导致的滚动事件
      if (now < _programmatic_until) return
      // 用户滚动：解除后续“归位”
      if (_anchor_id) _interrupt_anchor('scroll')
    }

    _on_transition_end = (e) => {
      if (_user_interrupted) return
      if (!_anchor_id) return
      if (!e) return

      const pn = String(e.propertyName || '')
      if (pn && pn !== 'max-height' && pn !== 'height' && pn !== 'opacity') return

      _do_scroll(_anchor_id, { behavior: 'auto', offset: 6 })
    }

    // ✅ 用户输入：一旦发生，立刻解除锚定（PC + Mobile）
    list.addEventListener('wheel', _on_wheel, { passive: true })
    list.addEventListener('touchmove', _on_touchmove, { passive: true })
    list.addEventListener('pointerdown', _on_pointerdown, { passive: true })

    // ✅ 用户滚动（包括拖滚动条）：解除锚定
    list.addEventListener('scroll', _on_scroll, { passive: true })

    // ✅ 过渡结束：只有在“未被用户打断”时才补偿归位
    list.addEventListener('transitionend', _on_transition_end, true)
  }

  function detach_transitionend_stabilizer() {
    const list = library_list_el.value
    if (_bound && list) {
      if (_on_wheel) list.removeEventListener('wheel', _on_wheel)
      if (_on_touchmove) list.removeEventListener('touchmove', _on_touchmove)
      if (_on_pointerdown) list.removeEventListener('pointerdown', _on_pointerdown)
      if (_on_scroll) list.removeEventListener('scroll', _on_scroll)
      if (_on_transition_end) list.removeEventListener('transitionend', _on_transition_end, true)
    }

    _bound = false
    _on_transition_end = null
    _on_wheel = null
    _on_touchmove = null
    _on_pointerdown = null
    _on_scroll = null

    _interrupt_anchor('detach')
  }

  return {
    library_list_el,
    set_library_row_el,
    request_anchor_to_top,
    attach_transitionend_stabilizer,
    detach_transitionend_stabilizer
  }
}

