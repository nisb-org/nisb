import { reactive, computed, watch } from "vue"
import { useI18n } from "vue-i18n"
import { createRssGateSearch } from "./useRssGateSearch"

export function useRssGateController({ callTool, toast }) {
  const { t } = useI18n()
  const tr = (key, params = {}) => t(`rss.center.gate.controller.${key}`, params)

  const LS_BLOCKED_URLS = "nisb_rss_gate_blocked_urls"
  const LS_DELETED_URLS = "nisb_rss_deleted_urls"
  const LS_IMPORTED_URLS = "nisb_rss_imported_urls"
  const LS_SUBSCRIBE_GROUPS = "nisb_rss_subscribe_groups"
  const LS_FAVORITE_KEYWORDS = "nisb_rss_favorite_keywords"
  const LS_LAST_LIBRARY_ID = "nisb_last_library_id"

  function err_msg(e) {
    return e?.message || String(e)
  }

  function normalize_url(u) {
    const s = String(u || "").trim()
    if (!s) return ""
    const no_frag = s.split("#")[0]
    if (no_frag.length > 1 && no_frag.endsWith("/")) return no_frag.slice(0, -1)
    return no_frag
  }

  function normalized_status(r) {
    const raw = String(r?.status || "").trim().toLowerCase()
    if (raw) return raw
    if (r?.success === true) return "success"
    if (r?.success === false) return "error"
    return ""
  }

  function is_ok(r) {
    if (!r || typeof r !== "object") return false

    const s = normalized_status(r)

    if (s) {
      if (
        s === "error" ||
        s === "failed" ||
        s === "failure" ||
        s === "exception" ||
        s === "timeout" ||
        s === "partial_failure" ||
        s === "partial_error"
      ) {
        return false
      }

      if (
        s === "success" ||
        s === "ok" ||
        s === "ran" ||
        s === "skipped" ||
        s === "done" ||
        s === "completed"
      ) {
        return true
      }
    }

    if (r.success === false) return false
    if (r.success === true) return true

    return false
  }

  function tool_results_of(r) {
    return Array.isArray(r?.tool_results) ? r.tool_results : []
  }

  function first_tool_result(r, matcher) {
    const rows = tool_results_of(r)
    for (const row of rows) {
      if (!row || typeof row !== "object") continue
      if (matcher(row)) return row
    }
    return null
  }

  function pick_array(r, keys) {
    if (!r || typeof r !== "object") return []

    const rows = tool_results_of(r)
    for (const row of rows) {
      if (!row || typeof row !== "object") continue
      for (const k of keys) {
        if (Array.isArray(row[k])) return row[k]
      }
      const data = row.data
      if (data && typeof data === "object") {
        for (const k of keys) {
          if (Array.isArray(data[k])) return data[k]
        }
      }
    }

    for (const k of keys) {
      if (Array.isArray(r[k])) return r[k]
    }

    const d = r.data
    if (d && typeof d === "object") {
      for (const k of keys) {
        if (Array.isArray(d[k])) return d[k]
      }
    }

    return []
  }

  function pick_object(r, keys) {
    if (!r || typeof r !== "object") return {}

    const rows = tool_results_of(r)
    for (const row of rows) {
      if (!row || typeof row !== "object") continue
      for (const k of keys) {
        if (row[k] && typeof row[k] === "object" && !Array.isArray(row[k])) return row[k]
      }
      const data = row.data
      if (data && typeof data === "object") {
        for (const k of keys) {
          if (data[k] && typeof data[k] === "object" && !Array.isArray(data[k])) return data[k]
        }
      }
    }

    for (const k of keys) {
      if (r[k] && typeof r[k] === "object" && !Array.isArray(r[k])) return r[k]
    }

    const d = r.data
    if (d && typeof d === "object") {
      for (const k of keys) {
        if (d[k] && typeof d[k] === "object" && !Array.isArray(d[k])) return d[k]
      }
    }

    return {}
  }

  function pick_text(r, fallback = "") {
    const response = String(r?.response || "").trim()
    if (response) return response
    const message = String(r?.message || "").trim()
    if (message) return message
    const detail = String(r?.detail || "").trim()
    if (detail) return detail
    return String(fallback || "").trim()
  }

  function ls_read_json(key, fallback) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return fallback
      return JSON.parse(raw)
    } catch {
      return fallback
    }
  }

  function ls_write_json(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {}
  }

  function clamp_int(v, minV, maxV, defV) {
    const n = Number.parseInt(String(v ?? ""), 10)
    if (!Number.isFinite(n)) return defV
    return Math.max(minV, Math.min(maxV, n))
  }

  function parse_published_at(v) {
    const raw = String(v || "").trim()
    if (!raw) return null
    const s = raw.includes("T") ? raw : raw.replace(" ", "T")
    const t = Date.parse(s)
    if (!Number.isFinite(t)) return null
    return t
  }

  const state = reactive({
    query: "",
    days: "30",
    startDate: "",
    endDate: "",
    limit: "50",
    minScore: "0.35",
    strictLexical: true,
    onlyUnimported: false,

    sortMode: "score_desc",

    feeds: [],
    feedFilter: "",
    feedScope: "all",
    selectedFeedIds: [],
    confirmedFeedIds: [],

    groupName: "",
    subscribeGroups: [],

    libraries: [],
    libraryId: "",

    searchWorking: false,
    searchSessionId: "",
    searchPhase: "idle",
    searchPartial: false,
    searchDeadlineMs: 1000,
    searchDeadlineHit: false,
    searchStartedAt: 0,
    searchTookMs: 0,
    searchMessage: "",
    searchSourcesDone: [],
    searchSourcesPending: [],
    searchSourcesFailed: [],
    searchSourcesSkipped: [],
    searchSourceStats: [],

    importWorking: false,
    fetchDueWorking: false,
    spamWorking: false,

    rssAutoFetchWorking: false,
    rssAutoFetchEnabled: false,
    rssAutoFetchIntervalMinutes: 60,
    rssAutoFetchLimitEntries: 50,
    rssAutoFetchStatus: null,

    rssAutoCleanupEnabled: false,
    rssAutoCleanupKeepDays: 7,
    rssAutoCleanupIntervalHours: 24,
    rssAutoCleanupRebuildIndex: true,
    rssAutoCleanupDeleteLogsBeforeDays: 0,
    rssAutoCleanupWorking: false,
    rssAutoCleanupStatus: null,

    results: [],
    selectedKeys: [],
    lastImportReport: null,
    lastDeleteReport: null,

    blockedUrls: new Set(),
    deletedUrls: new Set(),
    importedUrls: new Set(),
    favoriteKeywords: [],

    autoFetchIntervalMinutes: 60,
    spamRules: [],

    confirmPulse: false,

    previewOpen: false,
    previewLoading: false,
    previewContent: "",
    previewTitle: "",
    previewFeedId: "",
    previewArticleId: "",

    overrideOpen: false,
    overrideWorking: false,
    overrideFeedId: "",
    overrideArticleId: "",
    overrideUrl: "",
    overrideTitle: "",
    overrideContent: "",
  })

  let confirm_pulse_timer = null
  let gate_prefs_loaded = false
  let gate_prefs_save_timer = null

  function load_sets() {
    const blocked = ls_read_json(LS_BLOCKED_URLS, [])
    const deleted = ls_read_json(LS_DELETED_URLS, [])
    const imported = ls_read_json(LS_IMPORTED_URLS, [])

    state.blockedUrls = new Set((blocked || []).map(normalize_url).filter(Boolean))
    state.deletedUrls = new Set((deleted || []).map(normalize_url).filter(Boolean))
    state.importedUrls = new Set((imported || []).map(normalize_url).filter(Boolean))
    state.favoriteKeywords = ls_read_json(LS_FAVORITE_KEYWORDS, [])
    state.subscribeGroups = ls_read_json(LS_SUBSCRIBE_GROUPS, [])

    try {
      const last = localStorage.getItem(LS_LAST_LIBRARY_ID)
      if (last) state.libraryId = String(last)
    } catch {}
  }

  function persist_blocked() {
    ls_write_json(LS_BLOCKED_URLS, Array.from(state.blockedUrls))
  }
  function persist_deleted() {
    ls_write_json(LS_DELETED_URLS, Array.from(state.deletedUrls))
  }
  function persist_imported() {
    ls_write_json(LS_IMPORTED_URLS, Array.from(state.importedUrls))
  }
  function persist_favorite_keywords() {
    ls_write_json(LS_FAVORITE_KEYWORDS, state.favoriteKeywords)
  }
  function persist_groups() {
    ls_write_json(LS_SUBSCRIBE_GROUPS, state.subscribeGroups)
  }

  function gate_prefs_payload() {
    return {
      subscribe_groups: state.subscribeGroups,
      favorite_keywords: state.favoriteKeywords,
      blocked_urls: Array.from(state.blockedUrls),
      deleted_urls: Array.from(state.deletedUrls),
      imported_urls: Array.from(state.importedUrls),
      last_library_id: String(state.libraryId || ""),
      auto_fetch_interval_minutes: Number(state.autoFetchIntervalMinutes || 0),
    }
  }

  function schedule_gate_prefs_save() {
    if (!gate_prefs_loaded) return
    if (gate_prefs_save_timer) clearTimeout(gate_prefs_save_timer)
    gate_prefs_save_timer = setTimeout(async () => {
      try {
        await callTool("nisb_rss_gate_prefs_set", gate_prefs_payload())
      } catch {}
    }, 800)
  }

  async function load_gate_prefs_from_backend() {
    try {
      const r = await callTool("nisb_rss_gate_prefs_get", {})
      if (!is_ok(r)) {
        gate_prefs_loaded = true
        return
      }

      const prefs_row =
        first_tool_result(r, (x) => x.type === "rss_gate_prefs" || x.type === "rss_gate_preferences") || {}
      const prefs =
        (prefs_row.prefs && typeof prefs_row.prefs === "object" ? prefs_row.prefs : null) ||
        (prefs_row.data && typeof prefs_row.data === "object" ? prefs_row.data : null) ||
        pick_object(r, ["prefs", "config", "data"])

      if (Array.isArray(prefs.subscribe_groups)) state.subscribeGroups = prefs.subscribe_groups
      if (Array.isArray(prefs.favorite_keywords)) state.favoriteKeywords = prefs.favorite_keywords
      if (Array.isArray(prefs.blocked_urls)) state.blockedUrls = new Set(prefs.blocked_urls.map(normalize_url).filter(Boolean))
      if (Array.isArray(prefs.deleted_urls)) state.deletedUrls = new Set(prefs.deleted_urls.map(normalize_url).filter(Boolean))
      if (Array.isArray(prefs.imported_urls)) state.importedUrls = new Set(prefs.imported_urls.map(normalize_url).filter(Boolean))
      if (prefs.last_library_id) state.libraryId = String(prefs.last_library_id)
      if (typeof prefs.auto_fetch_interval_minutes === "number") state.autoFetchIntervalMinutes = prefs.auto_fetch_interval_minutes

      persist_groups()
      persist_favorite_keywords()
      persist_blocked()
      persist_deleted()
      persist_imported()
    } catch {
    } finally {
      gate_prefs_loaded = true
    }
  }

  const filtered_feeds = computed(() => {
    const q = String(state.feedFilter || "").trim().toLowerCase()
    const arr = state.feeds || []
    if (!q) return arr
    return arr.filter((f) => `${f.title || ""} ${f.url || ""} ${f.feed_id || ""}`.toLowerCase().includes(q))
  })

  function is_blocked(url) {
    return state.blockedUrls.has(normalize_url(url))
  }
  function is_deleted(url) {
    return state.deletedUrls.has(normalize_url(url))
  }
  function is_imported(url) {
    return state.importedUrls.has(normalize_url(url))
  }

  function set_sort_mode(mode) {
    const m = String(mode || "").trim()
    if (m === "score_desc" || m === "time_desc" || m === "time_asc") {
      state.sortMode = m
      return
    }
    state.sortMode = "score_desc"
  }

  const display_results = computed(() => {
    let arr = Array.isArray(state.results) ? [...state.results] : []
    arr = arr.filter((x) => !is_blocked(x.url) && !is_deleted(x.url))
    if (state.onlyUnimported) arr = arr.filter((x) => !is_imported(x.url))

    const mode = String(state.sortMode || "score_desc")

    if (mode === "time_desc" || mode === "time_asc") {
      const dir = mode === "time_desc" ? -1 : 1
      arr.sort((a, b) => {
        const ta = parse_published_at(a?.published_at)
        const tb = parse_published_at(b?.published_at)
        const a_missing = ta === null
        const b_missing = tb === null

        if (a_missing && !b_missing) return 1
        if (!a_missing && b_missing) return -1
        if (!a_missing && !b_missing && ta !== tb) return (ta - tb) * dir

        const sa = Number(a?.score) || 0
        const sb = Number(b?.score) || 0
        if (sb !== sa) return sb - sa

        return String(a?.__key || "").localeCompare(String(b?.__key || ""))
      })
      return arr
    }

    arr.sort((a, b) => {
      const sb = Number(b?.score) || 0
      const sa = Number(a?.score) || 0
      if (sb !== sa) return sb - sa

      const ta = parse_published_at(a?.published_at)
      const tb = parse_published_at(b?.published_at)
      const a_missing = ta === null
      const b_missing = tb === null
      if (a_missing && !b_missing) return 1
      if (!a_missing && b_missing) return -1
      if (!a_missing && !b_missing && tb !== ta) return tb - ta

      return String(a?.__key || "").localeCompare(String(b?.__key || ""))
    })
    return arr
  })

  const selected_results = computed(() => {
    const key_set = new Set(state.selectedKeys)
    return display_results.value.filter((x) => key_set.has(x.__key))
  })

  function select_all_feeds() {
    state.selectedFeedIds = filtered_feeds.value.map((f) => f.feed_id).filter(Boolean)
  }

  function clear_feeds() {
    state.selectedFeedIds = []
  }

  function confirm_feeds() {
    state.confirmedFeedIds = Array.from(new Set((state.selectedFeedIds || []).filter(Boolean)))
    if (confirm_pulse_timer) clearTimeout(confirm_pulse_timer)
    state.confirmPulse = true
    confirm_pulse_timer = setTimeout(() => (state.confirmPulse = false), 1200)
  }

  function save_group() {
    const name = String(state.groupName || "").trim()
    if (!name) return toast(tr("groups.enterName"), "info")
    if (!state.confirmedFeedIds.length) return toast(tr("groups.confirmFeedsFirst"), "info")

    const now = Date.now()
    const group_id = `group_${now.toString(36)}`
    const item = { group_id, group_name: name, feed_ids: [...state.confirmedFeedIds], created_at: now }
    state.subscribeGroups = [item, ...(state.subscribeGroups || [])].slice(0, 50)
    persist_groups()
    schedule_gate_prefs_save()
    toast(tr("groups.saved"), "success")
    state.groupName = ""
  }

  function apply_group(group_id) {
    const g = (state.subscribeGroups || []).find((x) => x.group_id === group_id)
    if (!g) return
    state.selectedFeedIds = [...(g.feed_ids || [])]
    state.confirmedFeedIds = [...(g.feed_ids || [])]
    toast(
      tr("groups.loaded", {
        name: g.group_name,
        count: (g.feed_ids || []).length,
      }),
      "success"
    )
  }

  function clear_groups() {
    if (!confirm(tr("groups.clearConfirm"))) return
    state.subscribeGroups = []
    persist_groups()
    schedule_gate_prefs_save()
    toast(tr("groups.cleared"), "success")
  }

  function add_favorite_keyword(k) {
    const kw = String(k || "").trim()
    if (!kw) return
    if ((state.favoriteKeywords || []).includes(kw)) return
    state.favoriteKeywords = [kw, ...(state.favoriteKeywords || [])].slice(0, 50)
    persist_favorite_keywords()
    schedule_gate_prefs_save()
    toast(tr("favorite.added"), "success")
  }

  function clear_favorite_keywords() {
    if (!confirm(tr("favorite.clearConfirm"))) return
    state.favoriteKeywords = []
    persist_favorite_keywords()
    schedule_gate_prefs_save()
    toast(tr("favorite.cleared"), "success")
  }

  function toggle_block(url) {
    const u = normalize_url(url)
    if (!u) return
    if (state.blockedUrls.has(u)) {
      state.blockedUrls.delete(u)
      toast(tr("block.removed"), "success")
    } else {
      state.blockedUrls.add(u)
      toast(tr("block.added"), "success")
    }
    persist_blocked()
    schedule_gate_prefs_save()
  }

  async function load_libraries() {
    try {
      const r = await callTool("nisb_library_list", {})
      state.libraries = pick_array(r, ["libraries", "items", "data"])
    } catch {}
  }

  async function load_feeds() {
    try {
      const r = await callTool("nisb_rss_list_feeds", {})
      state.feeds = pick_array(r, ["feeds", "items", "data"])
    } catch {}
  }

  async function load_spam_rules() {
    state.spamWorking = true
    try {
      const r = await callTool("nisb_rss_spam_list", {})
      state.spamRules = pick_array(r, ["rules", "items", "data"])
    } catch {
    } finally {
      state.spamWorking = false
    }
  }

  async function add_spam_domain(url) {
    const u = String(url || "").trim()
    if (!u) return
    if (!confirm(tr("spam.confirmDomain", { url: u }))) return

    state.spamWorking = true
    try {
      const r = await callTool("nisb_rss_spam_add", { scope: "domain", url: u })
      if (!is_ok(r)) return toast(pick_text(r, tr("spam.addFailed")), "error")
      toast(tr("spam.domainAdded"), "success")
      await load_spam_rules()
    } catch (e) {
      toast(tr("spam.addFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.spamWorking = false
    }
  }

  async function add_spam_article(it) {
    const feed_id = String(it?.feed_id || "").trim()
    const article_id = String(it?.article_id || "").trim()
    const url = String(it?.url || "").trim()
    if (!feed_id || !article_id) return
    if (!confirm(tr("spam.confirmArticle", { title: it?.title || url }))) return

    state.spamWorking = true
    try {
      const r = await callTool("nisb_rss_spam_add", { scope: "article", feed_id, article_id, url })
      if (!is_ok(r)) return toast(pick_text(r, tr("spam.addFailed")), "error")
      toast(tr("spam.articleAdded"), "success")
      await load_spam_rules()
    } catch (e) {
      toast(tr("spam.addFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.spamWorking = false
    }
  }

  async function delete_spam_rule(rule_id) {
    if (!rule_id) return
    if (!confirm(tr("spam.deleteRuleConfirm"))) return

    state.spamWorking = true
    try {
      const r = await callTool("nisb_rss_spam_delete", { rule_id })
      if (!is_ok(r)) return toast(pick_text(r, tr("spam.deleteRuleFailed")), "error")
      toast(tr("spam.ruleDeleted"), "success")
      await load_spam_rules()
    } catch (e) {
      toast(tr("spam.deleteRuleFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.spamWorking = false
    }
  }

  async function fetch_due_now() {
    state.fetchDueWorking = true
    try {
      const r = await callTool("nisb_rss_fetch_due", {
        default_interval_minutes: Number(state.autoFetchIntervalMinutes) || 0,
        limit_entries: 50,
      })
      if (!is_ok(r)) return toast(pick_text(r, tr("fetch.dueFailed")), "error")

      const stats = pick_object(r, ["stats", "data"])
      const due = Number(stats.due || 0)
      const total_new = Number(stats.total_new || 0)
      const failed = Number(stats.failed || 0)

      if (failed > 0) toast(tr("fetch.doneWithFailed", { due, total_new, failed }), "info")
      else if (due === 0) toast(tr("fetch.noDue"), "info")
      else toast(tr("fetch.done", { due, total_new }), "success")
    } catch (e) {
      toast(tr("fetch.failedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.fetchDueWorking = false
    }
  }

  async function load_rss_auto_fetch_config() {
    state.rssAutoFetchWorking = true
    try {
      const r = await callTool("nisb_rss_auto_fetch_config_get", {})
      if (!is_ok(r)) return toast(pick_text(r, tr("autoFetch.loadFailed")), "error")

      const cfg = pick_object(r, ["config", "data"])
      state.rssAutoFetchStatus = cfg
      state.rssAutoFetchEnabled = !!cfg.enabled
      state.rssAutoFetchIntervalMinutes = clamp_int(cfg.interval_minutes, 1, 43200, 60)
      state.rssAutoFetchLimitEntries = clamp_int(cfg.limit_entries, 1, 200, 50)
    } catch (e) {
      toast(tr("autoFetch.loadFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoFetchWorking = false
    }
  }

  async function save_rss_auto_fetch_config() {
    state.rssAutoFetchWorking = true
    try {
      const payload = {
        enabled: !!state.rssAutoFetchEnabled,
        interval_minutes: clamp_int(state.rssAutoFetchIntervalMinutes, 1, 43200, 60),
        limit_entries: clamp_int(state.rssAutoFetchLimitEntries, 1, 200, 50),
      }
      const r = await callTool("nisb_rss_auto_fetch_config_set", payload)
      if (!is_ok(r)) return toast(pick_text(r, tr("autoFetch.saveFailed")), "error")
      state.rssAutoFetchStatus = pick_object(r, ["config", "data"])
      toast(tr("autoFetch.saved"), "success")
    } catch (e) {
      toast(tr("autoFetch.saveFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoFetchWorking = false
    }
  }

  async function run_rss_auto_fetch_now() {
    state.rssAutoFetchWorking = true
    try {
      const r = await callTool("nisb_rss_auto_fetch_run_now", {})
      if (!is_ok(r)) return toast(pick_text(r, tr("autoFetch.runNowFailed")), "error")
      const cfg = pick_object(r, ["config", "data"])
      if (cfg && Object.keys(cfg).length) state.rssAutoFetchStatus = cfg
      toast(tr("autoFetch.runNowDone", { status: normalized_status(r) || "" }).trim(), "success")
      await load_feeds()
    } catch (e) {
      toast(tr("autoFetch.runNowFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoFetchWorking = false
    }
  }

  async function delete_rss_auto_fetch_config() {
    if (!confirm(tr("autoFetch.deleteConfirm"))) return
    state.rssAutoFetchWorking = true
    try {
      const r = await callTool("nisb_rss_auto_fetch_config_delete", {})
      if (!is_ok(r)) return toast(pick_text(r, tr("autoFetch.deleteFailed")), "error")

      state.rssAutoFetchEnabled = false
      state.rssAutoFetchIntervalMinutes = 60
      state.rssAutoFetchLimitEntries = 50
      state.rssAutoFetchStatus = null
      toast(tr("autoFetch.deleted"), "success")
    } catch (e) {
      toast(tr("autoFetch.deleteFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoFetchWorking = false
    }
  }

  function normalize_rss_auto_cleanup_config_response(r) {
    const d = pick_object(r, ["config", "data"])
    if (d && Object.keys(d).length > 0) return d
    if (r && typeof r === "object") return r
    return {}
  }

  async function load_rss_auto_cleanup_config() {
    state.rssAutoCleanupWorking = true
    try {
      const r = await callTool("nisb_rss_auto_cleanup_config_get", {})
      if (!is_ok(r)) {
        toast(pick_text(r, tr("autoCleanup.loadFailed")), "error")
        return
      }

      const d = normalize_rss_auto_cleanup_config_response(r)
      state.rssAutoCleanupEnabled = !!d.enabled
      state.rssAutoCleanupKeepDays = clamp_int(d.keep_days, 1, 365, 7)
      state.rssAutoCleanupIntervalHours = clamp_int(d.interval_hours, 1, 168, 24)
      state.rssAutoCleanupRebuildIndex = d.rebuild_index !== false
      state.rssAutoCleanupDeleteLogsBeforeDays = clamp_int(d.delete_logs_before_days, 0, 3650, 0)
      state.rssAutoCleanupStatus = d
    } catch (e) {
      toast(tr("autoCleanup.loadFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoCleanupWorking = false
    }
  }

  async function save_rss_auto_cleanup_config() {
    state.rssAutoCleanupWorking = true
    try {
      const payload = {
        enabled: !!state.rssAutoCleanupEnabled,
        keep_days: clamp_int(state.rssAutoCleanupKeepDays, 1, 365, 7),
        interval_hours: clamp_int(state.rssAutoCleanupIntervalHours, 1, 168, 24),
        rebuild_index: !!state.rssAutoCleanupRebuildIndex,
        delete_logs_before_days: clamp_int(state.rssAutoCleanupDeleteLogsBeforeDays, 0, 3650, 0),
      }

      const r = await callTool("nisb_rss_auto_cleanup_config_set", payload)
      if (!is_ok(r)) return toast(pick_text(r, tr("autoCleanup.saveFailed")), "error")

      const d = normalize_rss_auto_cleanup_config_response(r)
      state.rssAutoCleanupEnabled = !!d.enabled
      state.rssAutoCleanupKeepDays = clamp_int(d.keep_days, 1, 365, payload.keep_days)
      state.rssAutoCleanupIntervalHours = clamp_int(d.interval_hours, 1, 168, payload.interval_hours)
      state.rssAutoCleanupRebuildIndex = d.rebuild_index !== false
      state.rssAutoCleanupDeleteLogsBeforeDays = clamp_int(d.delete_logs_before_days, 0, 3650, payload.delete_logs_before_days)
      state.rssAutoCleanupStatus = d

      toast(tr("autoCleanup.saved"), "success")
    } catch (e) {
      toast(tr("autoCleanup.saveFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoCleanupWorking = false
    }
  }

  async function run_rss_auto_cleanup_now() {
    if (!confirm(tr("autoCleanup.runNowConfirm"))) return
    state.rssAutoCleanupWorking = true
    try {
      const r = await callTool("nisb_rss_auto_cleanup_run_now", {})
      if (!is_ok(r)) return toast(pick_text(r, tr("autoCleanup.runNowFailed")), "error")

      const d = normalize_rss_auto_cleanup_config_response(r)
      const beforeBytes = Number(d.before_bytes || 0)
      const afterBytes = Number(d.after_bytes || 0)
      toast(tr("autoCleanup.runNowDone", { beforeBytes, afterBytes }), "success")
      await load_rss_auto_cleanup_config()
    } catch (e) {
      toast(tr("autoCleanup.runNowFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoCleanupWorking = false
    }
  }

  async function delete_rss_auto_cleanup_config() {
    if (!confirm(tr("autoCleanup.deleteConfirm"))) return
    state.rssAutoCleanupWorking = true
    try {
      const r = await callTool("nisb_rss_auto_cleanup_config_delete", {})
      if (!is_ok(r)) return toast(pick_text(r, tr("autoCleanup.deleteFailed")), "error")

      state.rssAutoCleanupEnabled = false
      state.rssAutoCleanupKeepDays = 7
      state.rssAutoCleanupIntervalHours = 24
      state.rssAutoCleanupRebuildIndex = true
      state.rssAutoCleanupDeleteLogsBeforeDays = 0
      state.rssAutoCleanupStatus = null
      toast(tr("autoCleanup.deleted"), "success")
    } catch (e) {
      toast(tr("autoCleanup.deleteFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.rssAutoCleanupWorking = false
    }
  }

  function open_in_reader(feed_id, article_id) {
    window.dispatchEvent(new CustomEvent("nisb_open_rss_article", { detail: { feed_id, article_id } }))
  }

  async function preview_article(feed_id, article_id, title) {
    state.previewOpen = true
    state.previewLoading = true
    state.previewContent = ""
    state.previewTitle = String(title || "")
    state.previewFeedId = String(feed_id || "")
    state.previewArticleId = String(article_id || "")

    try {
      const r = await callTool("nisb_rss_get_article", { feed_id, article_id })
      const article_row =
        first_tool_result(r, (x) => x.type === "rss_article" || x.type === "rss_get_article") || {}
      const md =
        String(
          article_row.content_md ||
            article_row.contentmd ||
            article_row.content ||
            article_row.data?.content_md ||
            article_row.data?.content ||
            r?.content_md ||
            r?.contentmd ||
            r?.content ||
            ""
        )
      state.previewContent = md.slice(0, 6000)
    } catch (e) {
      state.previewContent = tr("preview.failedWithError", { error: err_msg(e) })
    } finally {
      state.previewLoading = false
    }
  }

  function close_preview() {
    state.previewOpen = false
    state.previewLoading = false
    state.previewContent = ""
    state.previewTitle = ""
    state.previewFeedId = ""
    state.previewArticleId = ""
  }

  function open_override_modal(it) {
    state.overrideOpen = true
    state.overrideWorking = false
    state.overrideFeedId = String(it?.feed_id || "").trim()
    state.overrideArticleId = String(it?.article_id || "").trim()
    state.overrideUrl = String(it?.url || "").trim()
    state.overrideTitle = String(it?.title || "").trim()
    state.overrideContent = ""
  }

  function close_override() {
    state.overrideOpen = false
    state.overrideWorking = false
    state.overrideFeedId = ""
    state.overrideArticleId = ""
    state.overrideUrl = ""
    state.overrideTitle = ""
    state.overrideContent = ""
  }

  async function save_override() {
    const feed_id = String(state.overrideFeedId || "").trim()
    const article_id = String(state.overrideArticleId || "").trim()
    const url = String(state.overrideUrl || "").trim()
    const title = String(state.overrideTitle || "").trim()
    const content_md = String(state.overrideContent || "").trim()
    if (!feed_id || !article_id || !content_md) return

    state.overrideWorking = true
    try {
      const r = await callTool("nisb_rss_override_article", { feed_id, article_id, url, title, content_md })
      if (!is_ok(r)) return toast(pick_text(r, tr("override.saveFailed")), "error")

      const idx = (state.results || []).findIndex((x) => x.feed_id === feed_id && x.article_id === article_id)
      if (idx >= 0) {
        const next = { ...state.results[idx] }
        const row = first_tool_result(r, (x) => x.type === "rss_override_article") || {}
        const next_title = row?.title || row?.data?.title || r?.title
        const next_excerpt = row?.excerpt || row?.data?.excerpt || r?.excerpt
        if (next_title) next.title = next_title
        if (next_excerpt) next.excerpt = next_excerpt
        state.results[idx] = next
      }

      toast(tr("override.saved"), "success")
      close_override()
    } catch (e) {
      toast(tr("override.saveFailedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.overrideWorking = false
    }
  }

  async function import_selected() {
    if (!state.libraryId) return toast(tr("import.selectLibraryFirst"), "info")
    if (!selected_results.value.length) return toast(tr("import.selectResultsFirst"), "info")

    state.importWorking = true
    try {
      const items = selected_results.value.map((x) => ({
        feed_id: x.feed_id,
        article_id: x.article_id,
        url: x.url,
        title: x.title,
        published_at: x.published_at,
      }))

      const r = await callTool("nisb_library_import_rss", {
        library_id: String(state.libraryId),
        items,
      })

      const imported = Number(r?.imported ?? r?.imported_count ?? 0)
      const skipped = Number(r?.skipped ?? r?.skipped_count ?? 0)
      const failed = Number(r?.failed ?? r?.failed_count ?? 0)
      const first_error =
        (Array.isArray(r?.failures) && (r.failures[0]?.reason || r.failures[0]?.message)) ||
        r?.message ||
        r?.detail ||
        ""

      state.lastImportReport = { imported, skipped, failed, first_error: String(first_error || "") }

      for (const it of selected_results.value) {
        const u = normalize_url(it.url)
        if (u) state.importedUrls.add(u)
      }
      persist_imported()
      schedule_gate_prefs_save()

      toast(tr("import.done", { imported, skipped, failed }), failed > 0 ? "info" : "success")
    } catch (e) {
      toast(tr("import.failedWithError", { error: err_msg(e) }), "error")
    } finally {
      state.importWorking = false
    }
  }

  function delete_article_local(it) {
    const u = normalize_url(it?.url)
    if (!u) return
    state.deletedUrls.add(u)
    persist_deleted()
    schedule_gate_prefs_save()
    toast(tr("delete.localMarked"), "success")
  }

  async function delete_article_data(it) {
    const feed_id = String(it?.feed_id || "").trim()
    const article_id = String(it?.article_id || "").trim()
    if (!feed_id || !article_id) return
    if (!confirm(tr("delete.dataConfirm", { title: it?.title || it?.url }))) return

    try {
      const r = await callTool("nisb_rss_delete_article", { feed_id, article_id })
      if (!is_ok(r)) return toast(pick_text(r, tr("delete.failed")), "error")
      const u = normalize_url(it?.url)
      if (u) {
        state.deletedUrls.add(u)
        persist_deleted()
        schedule_gate_prefs_save()
      }
      toast(tr("delete.dataDeleted"), "success")
    } catch (e) {
      toast(tr("delete.failedWithError", { error: err_msg(e) }), "error")
    }
  }

  async function delete_selected() {
    if (!selected_results.value.length) return
    if (!confirm(tr("delete.selectedConfirm", { count: selected_results.value.length }))) return

    const items = selected_results.value.map((x) => ({
      feed_id: x.feed_id,
      article_id: x.article_id,
    }))

    try {
      const r = await callTool("nisb_rss_gate_bulk_delete", { items, delete_files: true })
      const stats = pick_object(r, ["stats", "data"])
      const deleted = Number(stats.deleted || 0)
      const skipped = Number(stats.skipped || 0)
      const failed = Number(stats.failed || 0)
      state.lastDeleteReport = { deleted, skipped, failed, first_error: "" }

      for (const it of selected_results.value) {
        const u = normalize_url(it?.url)
        if (u) state.deletedUrls.add(u)
      }
      persist_deleted()
      schedule_gate_prefs_save()

      toast(tr("delete.done", { deleted, skipped, failed }), "success")
      state.selectedKeys = []
    } catch (e) {
      toast(tr("delete.failedWithError", { error: err_msg(e) }), "error")
    }
  }

  async function delete_all_results() {
    if (!display_results.value.length) return
    if (!confirm(tr("delete.allConfirm", { count: display_results.value.length }))) return

    const items = display_results.value.map((x) => ({
      feed_id: x.feed_id,
      article_id: x.article_id,
    }))

    try {
      const r = await callTool("nisb_rss_gate_bulk_delete", { items, delete_files: true })
      const stats = pick_object(r, ["stats", "data"])
      const deleted = Number(stats.deleted || 0)
      const skipped = Number(stats.skipped || 0)
      const failed = Number(stats.failed || 0)
      state.lastDeleteReport = { deleted, skipped, failed, first_error: "" }

      for (const it of display_results.value) {
        const u = normalize_url(it?.url)
        if (u) state.deletedUrls.add(u)
      }
      persist_deleted()
      schedule_gate_prefs_save()

      toast(tr("delete.done", { deleted, skipped, failed }), "success")
      state.results = []
      state.selectedKeys = []
    } catch (e) {
      toast(tr("delete.failedWithError", { error: err_msg(e) }), "error")
    }
  }

  function on_auto_rules_refresh() {}

  const search = createRssGateSearch({
    state,
    callTool,
    toast,
    loadGatePrefsFromBackend: load_gate_prefs_from_backend,
    normalizeUrl: normalize_url,
    t,
  })

  watch(
    () => state.feedScope,
    (v) => {
      if (v === "all") state.confirmedFeedIds = []
    }
  )

  watch(
    () => [state.subscribeGroups, state.favoriteKeywords, state.libraryId, state.autoFetchIntervalMinutes],
    () => schedule_gate_prefs_save(),
    { deep: false }
  )

  function dispose() {
    search.dispose()

    try {
      if (confirm_pulse_timer) clearTimeout(confirm_pulse_timer)
    } catch {}
    confirm_pulse_timer = null

    try {
      if (gate_prefs_save_timer) clearTimeout(gate_prefs_save_timer)
    } catch {}
    gate_prefs_save_timer = null
  }

  async function init() {
    load_sets()
    await load_feeds()
    await load_libraries()
    await load_gate_prefs_from_backend()
    await load_spam_rules()
    await load_rss_auto_fetch_config()
    await load_rss_auto_cleanup_config()
  }

  const api = {
    callTool,
    toast,
    state,

    get filteredFeeds() {
      return filtered_feeds.value
    },
    get displayResults() {
      return display_results.value
    },
    get selectedResults() {
      return selected_results.value
    },

    actions: {
      init,
      dispose,

      runSearch: search.runSearch,
      toggleAllLoaded: () => search.toggleAllLoaded(display_results.value),

      setSortMode: set_sort_mode,

      selectAllFeeds: select_all_feeds,
      clearFeeds: clear_feeds,
      confirmFeeds: confirm_feeds,

      saveGroup: save_group,
      applyGroup: apply_group,
      clearGroups: clear_groups,

      addFavoriteKeyword: add_favorite_keyword,
      clearFavoriteKeywords: clear_favorite_keywords,

      isBlocked: is_blocked,
      isDeleted: is_deleted,
      isImported: is_imported,
      toggleBlock: toggle_block,

      loadLibraries: load_libraries,
      loadFeeds: load_feeds,

      loadSpamRules: load_spam_rules,
      addSpamDomain: add_spam_domain,
      addSpamArticle: add_spam_article,
      deleteSpamRule: delete_spam_rule,

      fetchDueNow: fetch_due_now,

      loadRssAutoFetchConfig: load_rss_auto_fetch_config,
      saveRssAutoFetchConfig: save_rss_auto_fetch_config,
      runRssAutoFetchNow: run_rss_auto_fetch_now,
      deleteRssAutoFetchConfig: delete_rss_auto_fetch_config,

      loadRssAutoCleanupConfig: load_rss_auto_cleanup_config,
      saveRssAutoCleanupConfig: save_rss_auto_cleanup_config,
      runRssAutoCleanupNow: run_rss_auto_cleanup_now,
      deleteRssAutoCleanupConfig: delete_rss_auto_cleanup_config,

      openInReader: open_in_reader,
      previewArticle: preview_article,
      closePreview: close_preview,

      openOverrideModal: open_override_modal,
      closeOverride: close_override,
      saveOverride: save_override,

      importSelected: import_selected,
      deleteArticleLocal: delete_article_local,
      deleteArticleData: delete_article_data,
      deleteSelected: delete_selected,
      deleteAllResults: delete_all_results,

      onAutoRulesRefresh: on_auto_rules_refresh,
    },

    init,
    dispose,
  }

  return api
}

