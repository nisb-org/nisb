export const LINE_COUNT_LIMIT = 500000

export function countLinesLimited(text, limit = LINE_COUNT_LIMIT) {
  const s = String(text || '')
  if (!s) return 0

  let n = 1
  for (let i = 0; i < s.length; i++) {
    if (s.charCodeAt(i) === 10) {
      n += 1
      if (n >= limit) return limit
    }
  }
  return n
}
