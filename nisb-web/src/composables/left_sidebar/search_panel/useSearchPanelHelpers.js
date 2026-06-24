import { useI18n } from 'vue-i18n'

export function toSafeArray(value) {
  return Array.isArray(value) ? value : []
}

export function isPlainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

export function normalizeDisplayText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

export function normalizePathValue(value) {
  return String(value || '')
    .trim()
    .replace(/\\\\/g, '/')
    .replace(/\/+/g, '/')
    .replace(/^\.\//, '')
    .replace(/^\/+/, '')
}

export function pathTail(path, depth = 2) {
  const parts = normalizePathValue(path).split('/').filter(Boolean)
  return parts.slice(-depth).join('/')
}

export function normalizeQueryClient(value) {
  return String(value || '')
    .normalize('NFKC')
    .replace(/\u3000/g, ' ')
    .replace(/[_/\\|:;,.，。；、()[\]{}<>《》“”"'`~!@#$%^&*+=?-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function normalizeLogicalModule(value) {
  const key = String(value || '').trim().toLowerCase()
  if (!key) return ''
  if (key === 'chat') return 'chat'
  if (key === 'dirs') return 'dirs'
  if (key === 'doc' || key === 'documents' || key === 'files' || key === 'agent_files') return 'files'
  if (key === 'library') return 'library'
  return key
}

export function calcReasonRank(reason) {
  switch (String(reason || '').trim()) {
    case 'exact':
      return 6
    case 'prefix':
      return 5
    case 'substring':
      return 4
    case 'compact':
      return 3
    case 'tokens':
    case 'all_tokens':
      return 2
    case 'fuzzy':
      return 1
    default:
      return 0
  }
}

export function pickBetterItem(prev, next) {
  if (!prev) return next
  if (!next) return prev

  const scoreDiff = Number(next?.score || 0) - Number(prev?.score || 0)
  if (scoreDiff !== 0) return scoreDiff > 0 ? next : prev

  const reasonDiff = calcReasonRank(next?.match_reason) - calcReasonRank(prev?.match_reason)
  if (reasonDiff !== 0) return reasonDiff > 0 ? next : prev

  const hitCountDiff = Number(next?.hit_count || 0) - Number(prev?.hit_count || 0)
  if (hitCountDiff !== 0) return hitCountDiff > 0 ? next : prev

  const snippetLenDiff = String(next?.snippet || '').length - String(prev?.snippet || '').length
  if (snippetLenDiff !== 0) return snippetLenDiff > 0 ? next : prev

  const timePrev = String(prev?.created_at || '')
  const timeNext = String(next?.created_at || '')
  if (timeNext !== timePrev) {
    return timeNext.localeCompare(timePrev) > 0 ? next : prev
  }

  return prev
}

export function sortResultItems(list) {
  return [...toSafeArray(list)].sort((a, b) => {
    const scoreDiff = Number(b?.score || 0) - Number(a?.score || 0)
    if (scoreDiff !== 0) return scoreDiff

    const reasonDiff = calcReasonRank(b?.match_reason) - calcReasonRank(a?.match_reason)
    if (reasonDiff !== 0) return reasonDiff

    const hitCountDiff = Number(b?.hit_count || 0) - Number(a?.hit_count || 0)
    if (hitCountDiff !== 0) return hitCountDiff

    const snippetLenDiff = String(b?.snippet || '').length - String(a?.snippet || '').length
    if (snippetLenDiff !== 0) return snippetLenDiff

    const timeA = String(a?.created_at || '')
    const timeB = String(b?.created_at || '')
    return timeB.localeCompare(timeA)
  })
}

export function formatDate(isoDate) {
  if (!isoDate) return ''
  const date = new Date(isoDate)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()
  if (isToday) return date.toTimeString().slice(0, 5)
  return `${date.getMonth() + 1}-${date.getDate()} ${date.toTimeString().slice(0, 5)}`
}

export function getBasename(path) {
  const p = normalizePathValue(path).replace(/\/+$/, '')
  if (!p) return ''
  const parts = p.split('/').filter(Boolean)
  return parts[parts.length - 1] || ''
}

export function getPathShort(path) {
  return pathTail(path, 2)
}

function translateMatchReason(reason, t) {
  const r = String(reason || '').trim()
  if (!r) return ''

  if (r === 'fuzzy') return t('sidebar.search.match.reasons.fuzzy')
  if (r === 'prefix') return t('sidebar.search.match.reasons.prefix')
  if (r === 'exact') return t('sidebar.search.match.reasons.exact')
  if (r === 'compact') return t('sidebar.search.match.reasons.compact')
  if (r === 'substring') return t('sidebar.search.match.reasons.substring')
  if (r === 'tokens' || r === 'all_tokens') return t('sidebar.search.match.reasons.tokens')

  return r
}

export function sourceLabel(source, t) {
  const logical = normalizeLogicalModule(source)
  if (logical === 'files') return t ? t('sidebar.search.source.files') : 'files'
  if (logical === 'chat') return t ? t('sidebar.search.source.chat') : 'chat'
  if (logical === 'dirs') return t ? t('sidebar.search.source.dirs') : 'dirs'
  if (logical === 'library') return t ? t('sidebar.search.source.library') : 'library'
  return logical || ''
}

export function withReasonLabel(base, reason, t) {
  const reasonText = t ? translateMatchReason(reason, t) : String(reason || '').trim()
  if (!reasonText) return base
  return `${base} · ${reasonText}`
}

export function chatMatchLabel(item, t) {
  const base = item?.match_type === 'title'
    ? (t ? t('sidebar.search.match.bases.title') : '标题')
    : (t ? t('sidebar.search.match.bases.content') : '内容')
  return withReasonLabel(base, item?.match_reason, t)
}

export function fileMatchLabel(item, t) {
  const mt = String(item?.match_type || '').trim()
  const base = mt === 'filename'
    ? (t ? t('sidebar.search.match.bases.filename') : '文件名')
    : (t ? t('sidebar.search.match.bases.content') : '内容')
  return withReasonLabel(base, item?.match_reason, t)
}

export function dirMatchLabel(item, t) {
  const mt = String(item?.match_type || '').trim()
  if (mt === 'dirname') {
    return withReasonLabel(t ? t('sidebar.search.match.bases.directoryName') : '目录名', item?.match_reason, t)
  }
  if (mt === 'dirpath') {
    return withReasonLabel(t ? t('sidebar.search.match.bases.directoryPath') : '目录路径', item?.match_reason, t)
  }
  return withReasonLabel(mt || (t ? t('sidebar.search.match.bases.directory') : '目录'), item?.match_reason, t)
}

export function libraryMatchLabel(item, t) {
  const mt = String(item?.match_type || '').trim()
  if (mt === 'library_name') {
    return withReasonLabel(t ? t('sidebar.search.match.bases.libraryName') : '库名', item?.match_reason, t)
  }
  if (mt === 'library_description') {
    return withReasonLabel(t ? t('sidebar.search.match.bases.libraryDescription') : '库描述', item?.match_reason, t)
  }
  if (mt === 'library_doc') {
    return withReasonLabel(t ? t('sidebar.search.match.bases.book') : '书籍', item?.match_reason, t)
  }
  return withReasonLabel(mt || (t ? t('sidebar.search.match.bases.hit') : '命中'), item?.match_reason, t)
}

export function isLibraryDocHit(item) {
  return Boolean(item?.doc_id || item?.docId || item?.match_type === 'library_doc' || item?.title)
}

export function libraryKey(item) {
  const lid = item?.library_id || item?.libraryId || ''
  const did = item?.doc_id || item?.docId || ''
  const parentKey = String(item?.parent_key || item?.key || '').trim()
  return parentKey || `${lid}:${did || (item?.match_type || '')}:${item?.title || item?.library_name || ''}`
}

export function useSearchPanelHelpers() {
  const { t } = useI18n()

  return {
    toSafeArray,
    isPlainObject,
    normalizeDisplayText,
    normalizePathValue,
    pathTail,
    normalizeQueryClient,
    normalizeLogicalModule,
    calcReasonRank,
    pickBetterItem,
    sortResultItems,
    formatDate,
    getBasename,
    getPathShort,
    sourceLabel: (source) => sourceLabel(source, t),
    withReasonLabel: (base, reason) => withReasonLabel(base, reason, t),
    chatMatchLabel: (item) => chatMatchLabel(item, t),
    fileMatchLabel: (item) => fileMatchLabel(item, t),
    dirMatchLabel: (item) => dirMatchLabel(item, t),
    libraryMatchLabel: (item) => libraryMatchLabel(item, t),
    isLibraryDocHit,
    libraryKey
  }
}

export default useSearchPanelHelpers

