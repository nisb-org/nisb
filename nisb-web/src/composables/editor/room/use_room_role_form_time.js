import { computed, ref, watch } from 'vue'

export function useRoomRoleFormTime(form, t) {
  const timeUiMode = ref('days')
  const draftDocDays = ref(30)
  const draftOlderDaysAgo = ref(30)
  const draftNewerDaysAgo = ref(21)

  function ensureShape() {
    if (!form.tool_policy || typeof form.tool_policy !== 'object') {
      form.tool_policy = {
        rag: true,
        web: false,
        mcp: false,
        code: false,
        fs_read: false,
        fs_write: false,
      }
    }

    if (form.time_filter_days === undefined) form.time_filter_days = ''
    if (form.time_start === undefined) form.time_start = ''
    if (form.time_end === undefined) form.time_end = ''
  }

  function safeString(value, defaultValue = '') {
    if (value == null) return defaultValue
    const out = String(value).trim()
    return out || defaultValue
  }

  function clampDayNumber(value, fallback = 0) {
    let n = parseInt(value, 10)
    if (Number.isNaN(n)) n = fallback
    return Math.max(0, Math.min(3650, n))
  }

  function utcStartOfToday() {
    const now = new Date()
    return new Date(Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      0, 0, 0, 0
    ))
  }

  function toIsoStartFromDaysAgo(daysAgo) {
    const d = utcStartOfToday()
    d.setUTCDate(d.getUTCDate() - clampDayNumber(daysAgo, 0))
    return d.toISOString()
  }

  function toIsoEndFromDaysAgo(daysAgo) {
    const d = utcStartOfToday()
    d.setUTCDate(d.getUTCDate() - clampDayNumber(daysAgo, 0))
    d.setUTCHours(23, 59, 59, 999)
    return d.toISOString()
  }

  function daysAgoFromIso(value) {
    const ms = Date.parse(value)
    if (!Number.isFinite(ms)) return null

    const d = new Date(ms)
    const target = new Date(Date.UTC(
      d.getUTCFullYear(),
      d.getUTCMonth(),
      d.getUTCDate(),
      0, 0, 0, 0
    ))
    const today = utcStartOfToday()
    const diff = Math.round((today.getTime() - target.getTime()) / 86400000)
    return Math.max(0, diff)
  }

  function syncTimeDraftsFromForm() {
    ensureShape()

    const rawDays = Number(form.time_filter_days)
    const hasDays = Number.isFinite(rawDays) && rawDays > 0
    const start = safeString(form.time_start)
    const end = safeString(form.time_end)

    if (hasDays) {
      timeUiMode.value = 'days'
      draftDocDays.value = Math.floor(rawDays)
      return
    }

    if (start || end) {
      timeUiMode.value = 'range'
      const older = daysAgoFromIso(start)
      const newer = daysAgoFromIso(end)
      if (older != null) draftOlderDaysAgo.value = older
      if (newer != null) draftNewerDaysAgo.value = newer
      return
    }

    timeUiMode.value = 'days'
  }

  function switchToDaysMode() {
    ensureShape()
    timeUiMode.value = 'days'
    if (!(Number(form.time_filter_days) > 0)) {
      const fixed = clampDayNumber(draftDocDays.value, 30) || 30
      form.time_filter_days = fixed
    }
    form.time_start = ''
    form.time_end = ''
    syncTimeDraftsFromForm()
  }

  function switchToRangeMode() {
    ensureShape()
    timeUiMode.value = 'range'
    form.time_filter_days = ''
    if (!safeString(form.time_start) && !safeString(form.time_end)) {
      setRelativePreset(draftOlderDaysAgo.value, draftNewerDaysAgo.value)
    } else {
      syncTimeDraftsFromForm()
    }
  }

  function clearTimeRange() {
    ensureShape()
    form.time_filter_days = ''
    form.time_start = ''
    form.time_end = ''
    timeUiMode.value = 'days'
  }

  function pickDocTimeDays(days) {
    ensureShape()
    timeUiMode.value = 'days'
    const fixed = clampDayNumber(days, 30) || 30
    draftDocDays.value = fixed
    form.time_filter_days = fixed
    form.time_start = ''
    form.time_end = ''
  }

  function applyDocTimeDays() {
    ensureShape()
    timeUiMode.value = 'days'
    const fixed = clampDayNumber(draftDocDays.value, 30) || 30
    draftDocDays.value = fixed
    form.time_filter_days = fixed
    form.time_start = ''
    form.time_end = ''
  }

  function setRelativePreset(olderDaysAgo, newerDaysAgo) {
    ensureShape()
    timeUiMode.value = 'range'

    let older = clampDayNumber(olderDaysAgo, 30)
    let newer = clampDayNumber(newerDaysAgo, 21)

    if (older < newer) {
      const tmp = older
      older = newer
      newer = tmp
    }

    draftOlderDaysAgo.value = older
    draftNewerDaysAgo.value = newer

    form.time_filter_days = ''
    form.time_start = toIsoStartFromDaysAgo(older)
    form.time_end = toIsoEndFromDaysAgo(newer)
  }

  function applyRelativeDrafts() {
    setRelativePreset(draftOlderDaysAgo.value, draftNewerDaysAgo.value)
  }

  const timeSummary = computed(() => {
    const rawDays = Number(form?.time_filter_days)
    const hasDays = Number.isFinite(rawDays) && rawDays > 0
    const start = safeString(form?.time_start)
    const end = safeString(form?.time_end)

    if (hasDays) {
      return t('room.roleFormFields.time.currentRangeDays', {
        count: Math.floor(rawDays),
      })
    }
    if (start || end) {
      return t('room.roleFormFields.time.currentRangeInterval', {
        start: start || t('room.roleFormFields.common.ellipsis'),
        end: end || t('room.roleFormFields.common.ellipsis'),
      })
    }
    return t('room.roleFormFields.time.currentRangeEmpty')
  })

  const timeEffectiveHint = computed(() => t('room.roleFormFields.time.effectiveHint'))

  ensureShape()
  syncTimeDraftsFromForm()

  watch(
    () => [form?.time_filter_days, form?.time_start, form?.time_end],
    ([days, start, end]) => {
      ensureShape()

      const rawDays = Number(days)
      const hasDays = Number.isFinite(rawDays) && rawDays > 0
      const hasStart = !!safeString(start)
      const hasEnd = !!safeString(end)

      if (hasDays) {
        form.time_filter_days = Math.floor(rawDays)
        if (hasStart || hasEnd) {
          form.time_start = ''
          form.time_end = ''
        }
        timeUiMode.value = 'days'
        draftDocDays.value = Math.floor(rawDays)
        return
      }

      if (hasStart || hasEnd) {
        form.time_filter_days = ''
        timeUiMode.value = 'range'

        const older = daysAgoFromIso(start)
        const newer = daysAgoFromIso(end)
        if (older != null) draftOlderDaysAgo.value = older
        if (newer != null) draftNewerDaysAgo.value = newer
        return
      }

      timeUiMode.value = 'days'
    },
    { immediate: true }
  )

  return {
    timeUiMode,
    draftDocDays,
    draftOlderDaysAgo,
    draftNewerDaysAgo,
    switchToDaysMode,
    switchToRangeMode,
    clearTimeRange,
    pickDocTimeDays,
    applyDocTimeDays,
    setRelativePreset,
    applyRelativeDrafts,
    timeSummary,
    timeEffectiveHint,
  }
}
