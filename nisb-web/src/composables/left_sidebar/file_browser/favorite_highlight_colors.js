export const FAVORITE_HIGHLIGHT_COLORS = [
  { key: 'amber', hex: '#d97706' },
  { key: 'blue', hex: '#2563eb' },
  { key: 'emerald', hex: '#16a34a' },
  { key: 'violet', hex: '#7c3aed' },
  { key: 'rose', hex: '#e11d48' },
  { key: 'cyan', hex: '#0891b2' },
  { key: 'slate', hex: '#64748b' }
]

export const FAVORITE_HIGHLIGHT_COLOR_KEYS = new Set(
  FAVORITE_HIGHLIGHT_COLORS.map((item) => item.key)
)

export function normalize_favorite_highlight_color(value) {
  const key = String(value || '').trim().toLowerCase()
  return FAVORITE_HIGHLIGHT_COLOR_KEYS.has(key) ? key : ''
}

export function get_favorite_highlight_hex(value) {
  const key = normalize_favorite_highlight_color(value)
  if (!key) return ''
  return FAVORITE_HIGHLIGHT_COLORS.find((item) => item.key === key)?.hex || ''
}

export function favorite_highlight_style(value) {
  const hex = get_favorite_highlight_hex(value)
  return hex ? { '--favorite-highlight-color': hex } : {}
}
