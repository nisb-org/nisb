export function is_non_english(text) {
  const t = String(text || '').trim()
  if (!t) return false
  // 中文：4e00-9fff，日文：3040-30ff，韩文：ac00-d7af，阿拉伯文：0600-06ff，西里尔文：0400-04ff
  const non_english_re = /[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0600-\u06ff\u0400-\u04ff]/
  return non_english_re.test(t)
}

export function detect_language(text) {
  const t = String(text || '').trim()
  if (!t) return 'en'

  if (/[\u4e00-\u9fff]/.test(t)) return 'zh'
  if (/[\u3040-\u30ff]/.test(t)) return 'ja'
  if (/[\uac00-\ud7af]/.test(t)) return 'ko'
  if (/[\u0600-\u06ff]/.test(t)) return 'ar'
  if (/[\u0400-\u04ff]/.test(t)) return 'ru'
  return 'en'
}

export function is_text_file_by_name(filename) {
  return /\.(txt|md|json|js|py|html|css|yaml|yml|sh|env)$/i.test(String(filename || ''))
}

export function get_file_icon(filename) {
  const name = String(filename || '')
  if (/\.(md|txt)$/i.test(name)) return '📝'
  if (/\.(py|js|ts|java|cpp|c)$/i.test(name)) return '💻'
  if (/\.(json|yaml|yml|xml)$/i.test(name)) return '⚙️'
  if (/\.(png|jpg|jpeg|gif|svg)$/i.test(name)) return '🖼️'
  if (/\.(pdf|docx|doc)$/i.test(name)) return '📄'
  return '📁'
}

