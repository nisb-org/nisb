export function normalizeLibraryReader(readerRaw) {
  const r = readerRaw && typeof readerRaw === 'object' ? readerRaw : {}

  const smart =
    typeof r.smartPretranslate === 'boolean'
      ? r.smartPretranslate
      : typeof r.smart_pretranslate === 'boolean'
        ? r.smart_pretranslate
        : false

  const showTrans =
    typeof r.showTranslation === 'boolean'
      ? r.showTranslation
      : typeof r.show_translation === 'boolean'
        ? r.show_translation
        : false

  const cont = typeof r.continuous === 'boolean' ? r.continuous : false
  const lang = r.lang || r.targetLanguage || r.target_language || 'zh-CN'
  const spans = Number.isFinite(r.pretranslateSpans)
    ? Number(r.pretranslateSpans)
    : Number.isFinite(r.pretranslate_spans)
      ? Number(r.pretranslate_spans)
      : 2

  return {
    continuous: !!cont,
    showTranslation: !!showTrans,
    smartPretranslate: !!smart,
    pretranslateSpans: spans,
    lang
  }
}
