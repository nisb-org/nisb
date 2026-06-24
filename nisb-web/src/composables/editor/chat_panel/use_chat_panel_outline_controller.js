import { onMounted, onUnmounted, watch } from 'vue'

function safe_string(value) {
  return value === null || value === undefined ? '' : String(value)
}

function safe_array(value) {
  return Array.isArray(value) ? value : []
}

function read_ref_value(value) {
  if (value && typeof value === 'object' && 'value' in value) return value.value
  return value
}

function read_message_role(msg) {
  return safe_string(msg?.role || msg?.turn_type || msg?.kind || '').trim()
}

function read_message_type(msg) {
  return safe_string(
    msg?.room_event_type ||
      msg?.event_type ||
      msg?.message_type ||
      msg?.type ||
      msg?.kind ||
      ''
  ).trim()
}

function read_message_text(msg) {
  return safe_string(
    msg?.content ||
      msg?.response ||
      msg?.text ||
      msg?.message ||
      msg?.summary ||
      ''
  )
}

function read_agent_label(msg) {
  return safe_string(
    msg?.worker_name ||
      msg?.agent_name ||
      msg?.role_name ||
      msg?.display_name ||
      msg?.name ||
      msg?.worker_id ||
      msg?.agent_id ||
      msg?.role_id ||
      ''
  ).trim()
}

function read_supervisor_label(msg) {
  return safe_string(
    msg?.supervisor_category ||
      msg?.classification ||
      msg?.category ||
      msg?.phase ||
      msg?.room_phase ||
      msg?.title ||
      msg?.section_title ||
      ''
  ).trim()
}

function first_line(value) {
  return safe_string(value).split('\n')[0].trim()
}

function truncate_text(value, max = 42) {
  const text = safe_string(value).replace(/\s+/g, ' ').trim()
  if (!text) return ''
  if (text.length <= max) return text
  return `${text.slice(0, max)}...`
}

function join_title(parts) {
  return parts.map((part) => safe_string(part).trim()).filter(Boolean).join(' · ')
}

function message_signature(msg) {
  return [
    safe_string(msg?.id || msg?.local_id || ''),
    read_message_role(msg),
    read_message_type(msg),
    first_line(read_message_text(msg)).slice(0, 48),
  ].join('|')
}

function is_worker_message(msg) {
  const role = read_message_role(msg).toLowerCase()
  const type = read_message_type(msg).toLowerCase()
  const label = read_agent_label(msg).toLowerCase()
  const token = `${role} ${type} ${label}`

  if (token.includes('worker')) return true
  if (token.includes('delegate')) return true
  if (token.includes('role_message')) return true
  if (token.includes('role-message')) return true

  return false
}

function is_supervisor_message(msg) {
  const role = read_message_role(msg).toLowerCase()
  const type = read_message_type(msg).toLowerCase()
  const label = read_agent_label(msg).toLowerCase()
  const token = `${role} ${type} ${label}`

  if (token.includes('supervisor')) return true
  if (role === 'assistant' && !is_worker_message(msg)) return true

  return false
}

export function use_chat_panel_outline_controller({ chat_root, messages }) {
  let room_mode_ref = null
  let active_room_id_ref = null
  let stop_room_context_watch = null

  function is_room_mode_active() {
    return !!read_ref_value(room_mode_ref)
  }

  function active_room_id() {
    return safe_string(read_ref_value(active_room_id_ref)).trim()
  }

  function dispatch_outline_mode(mode) {
    window.dispatchEvent(new CustomEvent('nisb-outline-mode-changed', { detail: { mode } }))
  }

  function build_chat_outline() {
    const outline = []
    safe_array(messages.value).forEach((msg, idx) => {
      if (read_message_role(msg) !== 'user') return

      const title = truncate_text(first_line(read_message_text(msg)) || `#${idx + 1}`, 42)

      outline.push({
        id: `chat:${idx}`,
        level: 2,
        text: title,
        anchor: `chat-${idx}`,
        collapsed: false,
        hidden: false,
        hasChildren: false,
        color: 'var(--h2)',
      })
    })
    return outline
  }

  function build_room_outline() {
    const outline = []

    safe_array(messages.value).forEach((msg, idx) => {
      const role = read_message_role(msg)
      const text = truncate_text(first_line(read_message_text(msg)), 44)
      const agent_label = truncate_text(read_agent_label(msg), 28)
      const supervisor_label = truncate_text(read_supervisor_label(msg), 28)

      let level = 2
      let title = ''

      if (role === 'user') {
        title = text || `#${idx + 1}`
        level = 2
      } else if (is_worker_message(msg)) {
        title = join_title([agent_label || role, text])
        level = 3
      } else if (is_supervisor_message(msg)) {
        title = join_title([supervisor_label || agent_label || role, text])
        level = 2
      }

      title = truncate_text(title, 58)
      if (!title) return

      outline.push({
        id: `room:${active_room_id() || 'active'}:${idx}`,
        level,
        text: title,
        anchor: `chat-${idx}`,
        collapsed: false,
        hidden: false,
        hasChildren: false,
        color: level >= 3 ? 'var(--h3)' : 'var(--h2)',
      })
    })

    return outline
  }

  function emit_room_outline_update() {
    const headings = build_room_outline()
    window.dispatchEvent(
      new CustomEvent('nisb-room-outline-update', {
        detail: {
          room_id: active_room_id(),
          headings,
        },
      })
    )
  }

  function emit_chat_outline_update() {
    if (is_room_mode_active()) {
      emit_room_outline_update()
      return
    }

    const headings = build_chat_outline()
    window.dispatchEvent(new CustomEvent('nisb-chat-outline-update', { detail: { headings } }))
  }

  function emit_active_outline_update() {
    if (is_room_mode_active()) {
      dispatch_outline_mode('room')
      emit_room_outline_update()
      return
    }

    dispatch_outline_mode('chat')
    emit_chat_outline_update()
  }

  function set_room_outline_context(ctx = {}) {
    room_mode_ref = ctx.is_room_mode || ctx.isRoomMode || null
    active_room_id_ref = ctx.active_room_id || ctx.activeRoomId || null

    if (typeof stop_room_context_watch === 'function') {
      stop_room_context_watch()
      stop_room_context_watch = null
    }

    stop_room_context_watch = watch(
      () => {
        const list = safe_array(messages.value)
        const last = list.length ? list[list.length - 1] : null

        return {
          is_room_mode: is_room_mode_active(),
          room_id: active_room_id(),
          length: list.length,
          last_signature: last ? message_signature(last) : '',
        }
      },
      (next, prev) => {
        const next_mode = next?.is_room_mode ? 'room' : 'chat'
        const prev_mode = prev?.is_room_mode ? 'room' : 'chat'

        if (!prev || next_mode !== prev_mode) {
          dispatch_outline_mode(next_mode)
        }

        if (next?.is_room_mode) {
          emit_room_outline_update()
          return
        }

        emit_chat_outline_update()
      },
      { flush: 'post' }
    )
  }

  function handle_outline_jump_for_chat(e) {
    const { anchor } = e?.detail || {}
    if (!anchor || !String(anchor).startsWith('chat-')) return

    const root = chat_root?.value
    if (!root) return

    const target =
      root.querySelector(`[data-chat-anchor="${anchor}"]`) ||
      root.querySelector(`#${anchor}`)

    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  onMounted(() => {
    window.addEventListener('nisb-outline-jump', handle_outline_jump_for_chat)
    emit_active_outline_update()
  })

  onUnmounted(() => {
    if (typeof stop_room_context_watch === 'function') {
      stop_room_context_watch()
      stop_room_context_watch = null
    }

    window.removeEventListener('nisb-outline-jump', handle_outline_jump_for_chat)
    window.dispatchEvent(new CustomEvent('nisb-outline-mode-changed', { detail: { mode: 'note' } }))
  })

  return {
    build_chat_outline,
    build_room_outline,
    emit_chat_outline_update,
    emit_room_outline_update,
    emit_active_outline_update,
    set_room_outline_context,
    handle_outline_jump_for_chat,
  }
}

export default use_chat_panel_outline_controller
