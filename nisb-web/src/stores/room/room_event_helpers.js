import {
  safe_array,
  safe_object,
  safe_string,
  is_plain_object,
} from './room_shared'

export function normalize_room_event_key(item) {
  const src = safe_object(item)
  const id = safe_string(src.id).trim()
  if (id) return `id:${id}`

  const local_id = safe_string(src.local_id).trim()
  if (local_id) return `local:${local_id}`

  const ts = safe_string(src.ts).trim()
  const type = safe_string(src.type || src.room_event_type).trim()
  const sender = safe_string(src.sender).trim()
  const sender_type = safe_string(src.sender_type).trim()
  const response = safe_string(src.response || src.content).trim()
  return `fallback:${ts}|${type}|${sender}|${sender_type}|${response}`
}

export function room_event_sort_key(item) {
  const src = safe_object(item)
  return `${safe_string(src.ts)}|${safe_string(src.id || src.local_id)}`
}

export function sort_room_items(items) {
  return safe_array(items)
    .slice()
    .sort((a, b) => {
      const ka = room_event_sort_key(a)
      const kb = room_event_sort_key(b)
      if (ka < kb) return -1
      if (ka > kb) return 1
      return 0
    })
}

export function merge_room_items(existing, incoming, mode = 'replace') {
  const incoming_list = sort_room_items(incoming)

  if (mode !== 'prepend') {
    const map = new Map()
    for (const item of incoming_list) {
      const key = normalize_room_event_key(item)
      map.set(key, { ...safe_object(map.get(key)), ...safe_object(item) })
    }
    return sort_room_items(Array.from(map.values()))
  }

  const merged = new Map()
  for (const item of safe_array(existing)) {
    const key = normalize_room_event_key(item)
    merged.set(key, safe_object(item))
  }
  for (const item of incoming_list) {
    const key = normalize_room_event_key(item)
    merged.set(key, { ...safe_object(item), ...safe_object(merged.get(key)) })
  }
  return sort_room_items(Array.from(merged.values()))
}

export function normalize_room_runtime_event(item) {
  const src = safe_object(item)
  const payload =
    is_plain_object(src.payload)
      ? src.payload
      : is_plain_object(src.data)
        ? src.data
        : is_plain_object(src.result)
          ? src.result
          : is_plain_object(src.value)
            ? src.value
            : {}

  return {
    ...src,
    id: safe_string(src.id).trim(),
    local_id: safe_string(src.local_id).trim(),
    type: safe_string(src.type || src.room_event_type).trim(),
    ts: safe_string(src.ts).trim(),
    run_id: safe_string(src.run_id).trim(),
    request_id: safe_string(src.request_id).trim(),
    trigger_event_id: safe_string(src.trigger_event_id).trim(),
    payload,
  }
}

export function normalize_runtime_event_key(item) {
  const src = normalize_room_runtime_event(item)
  if (src.id) return `id:${src.id}`
  if (src.local_id) return `local:${src.local_id}`
  return `fallback:${src.ts}|${src.type}|${src.run_id}|${src.request_id}|${src.trigger_event_id}`
}

export function runtime_event_sort_key(item) {
  const src = normalize_room_runtime_event(item)
  return `${safe_string(src.ts)}|${safe_string(src.id || src.local_id)}`
}

export function sort_runtime_events(items) {
  return safe_array(items)
    .map((item) => normalize_room_runtime_event(item))
    .sort((a, b) => {
      const ka = runtime_event_sort_key(a)
      const kb = runtime_event_sort_key(b)
      if (ka < kb) return -1
      if (ka > kb) return 1
      return 0
    })
}

export function merge_runtime_events(existing, incoming, mode = 'merge') {
  const incoming_list = sort_runtime_events(incoming)

  if (mode === 'replace') {
    const map = new Map()
    for (const item of incoming_list) {
      const key = normalize_runtime_event_key(item)
      map.set(key, { ...safe_object(map.get(key)), ...safe_object(item) })
    }
    return sort_runtime_events(Array.from(map.values()))
  }

  const merged = new Map()
  for (const item of safe_array(existing)) {
    const normalized = normalize_room_runtime_event(item)
    const key = normalize_runtime_event_key(normalized)
    merged.set(key, normalized)
  }
  for (const item of incoming_list) {
    const normalized = normalize_room_runtime_event(item)
    const key = normalize_runtime_event_key(normalized)
    merged.set(key, { ...safe_object(merged.get(key)), ...normalized })
  }
  return sort_runtime_events(Array.from(merged.values()))
}

export function get_runtime_result_event_from_list(items) {
  const rows = sort_runtime_events(items)
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (safe_string(rows[i]?.type).trim() === 'room.final') {
      return rows[i]
    }
  }
  return rows.length ? rows[rows.length - 1] : null
}

export function get_runtime_process_items_from_list(items) {
  return sort_runtime_events(items).filter((item) => safe_string(item?.type).trim() !== 'room.final')
}

