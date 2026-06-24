function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms) || 0)))
}

function normalized_status(r) {
  const raw = String(r?.status || "").trim().toLowerCase()
  if (raw) return raw
  if (r?.success === true) return "success"
  if (r?.success === false) return "error"
  return ""
}

function is_ok(r) {
  const s = normalized_status(r)
  if (s) return s === "success"
  if (!r || typeof r !== "object") return false
  if (r.success === false) return false
  return true
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

function pick_text(r, fallback = "") {
  const response = String(r?.response || "").trim()
  if (response) return response
  const message = String(r?.message || "").trim()
  if (message) return message
  const detail = String(r?.detail || "").trim()
  if (detail) return detail
  return String(fallback || "").trim()
}

function extract_gate_candidates_result(r) {
  const row =
    first_tool_result(
      r,
      (x) => x.type === "rss_gate_candidates" && (Array.isArray(x.items) || (x.data && Array.isArray(x.data.items)))
    ) || {}

  const row_data = row?.data && typeof row.data === "object" ? row.data : {}

  const items = Array.isArray(row.items)
    ? row.items
    : Array.isArray(row_data.items)
      ? row_data.items
      : pick_array(r, ["items", "results", "data"])

  return {
    ok: is_ok(r),
    text: pick_text(r, row.response || row.message || row_data.response || row_data.message || ""),
    items: Array.isArray(items) ? items : [],
    total: Number(row.total ?? row_data.total ?? r?.total ?? 0) || 0,
    next_cursor: String(row.next_cursor ?? row_data.next_cursor ?? r?.next_cursor ?? ""),
    sort_by: String(row.sort_by ?? row_data.sort_by ?? r?.sort_by ?? ""),
    match_mode: String(row.match_mode ?? row_data.match_mode ?? r?.match_mode ?? ""),
    groups_count: Number(row.groups_count ?? row_data.groups_count ?? r?.groups_count ?? 0) || 0,
    scan_mode: String(row.scan_mode ?? row_data.scan_mode ?? r?.scan_mode ?? ""),
    partial: row.partial === true || row_data.partial === true || r?.partial === true,
    methods: Array.isArray(row.methods)
      ? row.methods
      : Array.isArray(row_data.methods)
        ? row_data.methods
        : Array.isArray(r?.methods)
          ? r.methods
          : [],
    source_stats: Array.isArray(row.source_stats)
      ? row.source_stats
      : Array.isArray(row_data.source_stats)
        ? row_data.source_stats
        : Array.isArray(r?.source_stats)
          ? r.source_stats
          : [],
    took_ms: Number(row.took_ms ?? row_data.took_ms ?? r?.took_ms ?? 0) || 0,
  }
}

function parse_published_at(v) {
  const raw = String(v || "").trim()
  if (!raw) return null
  const s = raw.includes("T") ? raw : raw.replace(" ", "T")
  const t = Date.parse(s)
  if (!Number.isFinite(t)) return null
  return t
}

function make_key(obj, idx, normalizeUrl) {
  const feed_id = String(obj?.feed_id || "").trim()
  const article_id = String(obj?.article_id || "").trim()
  const url_norm = normalizeUrl(obj?.url || "")
  if (feed_id || article_id || url_norm) return `${feed_id}::${article_id}::${url_norm}`
  const title = String(obj?.title || "").trim()
  return `rss_gate_row::${title || idx}`
}

function normalize_result(x, idx, normalizeUrl) {
  if (!x || typeof x !== "object") return null
  const feed_id = String(x?.feed_id || x?.feedId || x?.feedid || "").trim()
  const article_id = String(x?.article_id || x?.articleId || x?.articleid || "").trim()
  const url = String(x?.url || x?.link || "").trim()
  const title = String(x?.title || x?.name || "").trim()
  const published_at = String(x?.published_at || x?.publishedAt || "").trim()
  const excerpt = String(x?.excerpt || x?.snippet || x?.description || "").trim()

  let score = 0
  try {
    score = Number(x?.score) || 0
  } catch {
    score = 0
  }

  const method_hit = Array.isArray(x?.method_hit)
    ? x.method_hit.map((v) => String(v || "").trim()).filter(Boolean)
    : []

  const obj = {
    feed_id,
    article_id,
    url,
    url_norm: normalizeUrl(url),
    title,
    published_at,
    excerpt,
    score,
    method_hit,
    keyword_score: Number(x?.keyword_score || 0) || 0,
    semantic_score: Number(x?.semantic_score || 0) || 0,
    source_hits: Array.isArray(x?.source_hits) ? x.source_hits.map((v) => String(v || "").trim()).filter(Boolean) : [],
  }
  obj.__key = make_key(obj, idx, normalizeUrl)
  return obj
}

function infer_methods_from_lane(lane_id) {
  if (lane_id === "fast_keyword_strict" || lane_id === "keyword_relaxed") return ["keyword"]
  if (lane_id === "hybrid") return ["keyword", "semantic"]
  if (lane_id === "semantic") return ["semantic"]
  return []
}

function create_gate_t(inputT) {
  return function tt(key, params = {}) {
    try {
      if (typeof inputT === "function") return inputT(key, params)
    } catch {}
    return key
  }
}

export function createRssGateSearch({ state, callTool, toast, loadGatePrefsFromBackend, normalizeUrl, t: inputT }) {
  let search_seq = 0
  let search_deadline_timer = null
  const tt = create_gate_t(inputT)

  function hard_limit() {
    return Math.max(1, Number(state.limit) || 50)
  }

  function build_gate_payload() {
    const feed_ids = state.feedScope === "selected" ? (state.confirmedFeedIds || []).filter(Boolean) : []
    return {
      query: String(state.query || "").trim(),
      feed_ids,
      days: Number(state.days),
      start_date: String(state.startDate || ""),
      end_date: String(state.endDate || ""),
      limit: Math.max(20, Number(state.limit) || 50),
      min_score: Number(state.minScore),
      strict_lexical: !!state.strictLexical,
      exclude_spam: true,
    }
  }

  function build_search_lanes(base_payload) {
    const hardLimit = Math.max(20, Number(base_payload.limit) || 50)
    const fastLimit = Math.max(12, Math.min(30, Math.ceil(hardLimit * 0.35)))
    const mediumLimit = Math.max(fastLimit, Math.min(80, hardLimit))
    const fullLimit = hardLimit

    return [
      {
        id: "fast_keyword_strict",
        label: "fast_keyword_strict",
        stage: "fast",
        delay_ms: 0,
        priority: 1.0,
        payload: {
          ...base_payload,
          methods: ["keyword"],
          strict_lexical: true,
          limit: fastLimit,
          fast_mode: true,
          scan_cap: Math.max(600, fastLimit * 40),
          candidate_cap: Math.max(80, fastLimit * 6),
        },
      },
      {
        id: "keyword_relaxed",
        label: "keyword_relaxed",
        stage: "background",
        delay_ms: 120,
        priority: 0.95,
        payload: {
          ...base_payload,
          methods: ["keyword"],
          strict_lexical: false,
          limit: fullLimit,
          fast_mode: false,
          scan_cap: Math.max(3000, fullLimit * 60),
          candidate_cap: Math.max(200, fullLimit * 10),
          min_score: Math.max(0, Number(state.minScore) - 0.06),
        },
      },
      {
        id: "hybrid",
        label: "hybrid",
        stage: "background",
        delay_ms: 320,
        priority: 0.99,
        payload: {
          ...base_payload,
          methods: ["hybrid"],
          strict_lexical: !!state.strictLexical,
          limit: fullLimit,
          fast_mode: false,
          candidate_cap: Math.max(300, fullLimit * 12),
        },
      },
      {
        id: "semantic",
        label: "semantic",
        stage: "late_background",
        delay_ms: 0,
        priority: 0.9,
        payload: {
          ...base_payload,
          methods: ["semantic"],
          strict_lexical: false,
          limit: mediumLimit,
          fast_mode: false,
          candidate_cap: Math.max(240, mediumLimit * 10),
        },
      },
    ]
  }

  function merge_lane_results(lanes, lane_results_map) {
    const map = new Map()
    let idx = 0

    for (const lane of lanes) {
      const lane_res = lane_results_map.get(lane.id)
      const arr = Array.isArray(lane_res?.items) ? lane_res.items : []
      for (const raw of arr) {
        const item = normalize_result(raw, idx++, normalizeUrl)
        if (!item || !item.url) continue

        const key = item.url_norm || item.__key
        const laneMethods = infer_methods_from_lane(lane.id)
        const mergedMethods = Array.from(new Set([...(item.method_hit || []), ...laneMethods])).filter(Boolean)
        const adjustedScore = Math.max(0, Number(item.score) || 0) * Number(lane.priority || 1)
        const publishedTs = parse_published_at(item.published_at) || 0

        if (!map.has(key)) {
          map.set(key, {
            ...item,
            score: adjustedScore,
            raw_score: Number(item.score) || 0,
            method_hit: mergedMethods,
            source_hits: Array.from(new Set([...(item.source_hits || []), lane.id])),
            _published_ts: publishedTs,
            _source_priority: Number(lane.priority || 0),
          })
          continue
        }

        const prev = map.get(key)
        prev.score = Math.max(Number(prev.score) || 0, adjustedScore)
        prev.raw_score = Math.max(Number(prev.raw_score) || 0, Number(item.score) || 0)
        prev.keyword_score = Math.max(Number(prev.keyword_score) || 0, Number(item.keyword_score) || 0)
        prev.semantic_score = Math.max(Number(prev.semantic_score) || 0, Number(item.semantic_score) || 0)
        prev.method_hit = Array.from(new Set([...(prev.method_hit || []), ...mergedMethods])).filter(Boolean)
        prev.source_hits = Array.from(new Set([...(prev.source_hits || []), ...(item.source_hits || []), lane.id])).filter(Boolean)
        prev._source_priority = Math.max(Number(prev._source_priority) || 0, Number(lane.priority || 0))

        if (!prev.title && item.title) prev.title = item.title
        if ((!prev.excerpt || prev.excerpt.length < item.excerpt.length) && item.excerpt) prev.excerpt = item.excerpt
        if (!prev.feed_id && item.feed_id) prev.feed_id = item.feed_id
        if (!prev.article_id && item.article_id) prev.article_id = item.article_id
        if (!prev.url && item.url) prev.url = item.url
        if (!prev.published_at && item.published_at) prev.published_at = item.published_at

        const prevTs = Number(prev._published_ts) || 0
        if (publishedTs > prevTs) prev._published_ts = publishedTs
      }
    }

    const merged = Array.from(map.values())
    merged.sort((a, b) => {
      const sb = Number(b?.score) || 0
      const sa = Number(a?.score) || 0
      if (sb !== sa) return sb - sa

      const tb = Number(b?._published_ts) || 0
      const ta = Number(a?._published_ts) || 0
      if (tb !== ta) return tb - ta

      return String(a?.__key || "").localeCompare(String(b?.__key || ""))
    })

    const page = merged.slice(0, hard_limit())
    for (const it of page) {
      delete it._published_ts
      delete it._source_priority
    }
    return page
  }

  function commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt }) {
    if (seq !== search_seq) return

    const doneIds = []
    const failedIds = []
    const skippedIds = []

    for (const lane of lanes) {
      if (laneResults.has(lane.id)) doneIds.push(lane.id)
      else if (laneErrors.has(lane.id)) failedIds.push(lane.id)
      else if (laneSkipped.has(lane.id)) skippedIds.push(lane.id)
    }

    const pendingIds = lanes
      .map((x) => x.id)
      .filter((id) => !doneIds.includes(id) && !failedIds.includes(id) && !skippedIds.includes(id))

    const merged = merge_lane_results(lanes, laneResults)

    state.results = merged
    state.selectedKeys = state.selectedKeys.filter((k) => merged.some((x) => x.__key === k))
    state.searchTookMs = Math.max(0, Date.now() - startedAt)
    state.searchSourcesDone = doneIds
    state.searchSourcesFailed = failedIds
    state.searchSourcesSkipped = skippedIds
    state.searchSourcesPending = pendingIds
    state.searchSourceStats = lanes.map((lane) => {
      const okRow = laneResults.get(lane.id)
      const errRow = laneErrors.get(lane.id)
      const skipReason = laneSkipped.get(lane.id) || ""
      return {
        source: lane.id,
        status: okRow ? "success" : errRow ? "error" : skipReason ? "skipped" : "pending",
        count: Number(okRow?.items?.length || 0),
        total: Number(okRow?.total || okRow?.items?.length || 0),
        took_ms: Number(okRow?.took_ms || 0),
        partial: !!okRow?.partial,
        error: String(errRow || skipReason || ""),
      }
    })

    if (merged.length === 0 && pendingIds.length > 0) {
      state.searchMessage = tt("rss.center.gate.search.status.warmingRemaining", { pending: pendingIds.length })
      return
    }

    if (pendingIds.length > 0) {
      state.searchMessage = tt("rss.center.gate.search.status.partialRemaining", {
        count: merged.length,
        pending: pendingIds.length,
      })
    } else if (failedIds.length > 0) {
      state.searchMessage = tt("rss.center.gate.search.status.doneWithFailed", {
        count: merged.length,
        failed: failedIds.length,
      })
    } else if (skippedIds.length > 0) {
      state.searchMessage = tt("rss.center.gate.search.status.doneWithSkipped", {
        count: merged.length,
        skipped: skippedIds.length,
      })
    } else {
      state.searchMessage = tt("rss.center.gate.search.status.done", { count: merged.length })
    }
  }

  function semantic_skip_reason({ laneResults, lanes }) {
    const semanticFreeLanes = lanes.filter((x) => x.id !== "semantic")
    const merged = merge_lane_results(semanticFreeLanes, laneResults)
    const limit = hard_limit()
    if (merged.length >= limit) return `limit_reached:${limit}`
    return ""
  }

  async function run_search(reset_selection = false) {
    const q = String(state.query || "").trim()
    if (!q) return toast(tt("rss.center.gate.search.toast.enterKeyword"), "info")

    try {
      await loadGatePrefsFromBackend()
    } catch {}

    const feed_ids = state.feedScope === "selected" ? (state.confirmedFeedIds || []).filter(Boolean) : []
    if (state.feedScope === "selected" && !feed_ids.length) {
      toast(tt("rss.center.gate.search.toast.confirmFeedScopeFirst"), "info")
      return
    }

    search_seq += 1
    const seq = search_seq
    const startedAt = Date.now()

    if (search_deadline_timer) clearTimeout(search_deadline_timer)
    search_deadline_timer = null

    state.searchWorking = true
    state.searchSessionId = `rss_gate_${Date.now().toString(36)}_${seq}`
    state.searchPhase = "running"
    state.searchPartial = false
    state.searchDeadlineHit = false
    state.searchStartedAt = startedAt
    state.searchTookMs = 0
    state.searchMessage = tt("rss.center.gate.search.status.searching")
    state.searchSourcesDone = []
    state.searchSourcesFailed = []
    state.searchSourcesSkipped = []
    state.searchSourcesPending = []
    state.searchSourceStats = []
    state.lastImportReport = null
    state.lastDeleteReport = null
    state.results = []
    if (reset_selection) state.selectedKeys = []

    const basePayload = build_gate_payload()
    const lanes = build_search_lanes(basePayload)
    state.searchSourcesPending = lanes.map((x) => x.id)

    const laneResults = new Map()
    const laneErrors = new Map()
    const laneSkipped = new Map()
    const lanePromises = new Map()
    let partialToastSent = false

    const start_lane = (lane) => {
      if (!lane || laneSkipped.has(lane.id)) return Promise.resolve(null)
      if (lanePromises.has(lane.id)) return lanePromises.get(lane.id)

      const p = (async () => {
        if (lane.delay_ms > 0) await sleep(lane.delay_ms)
        if (seq !== search_seq) return null

        const laneStarted = Date.now()
        try {
          const r = await callTool("nisb_rss_gate_candidates", lane.payload)
          const parsed = extract_gate_candidates_result(r)

          if (seq !== search_seq) return parsed

          if (parsed.ok) {
            laneResults.set(lane.id, { ...parsed, took_ms: Date.now() - laneStarted })
          } else {
            laneErrors.set(
              lane.id,
              parsed.text || tt("rss.center.gate.search.errors.sourceFailed", { source: lane.id })
            )
          }

          commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt })
          return parsed
        } catch (e) {
          if (seq !== search_seq) return null
          laneErrors.set(
            lane.id,
            e?.message || String(e) || tt("rss.center.gate.search.errors.sourceFailed", { source: lane.id })
          )
          commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt })
          return null
        }
      })()

      lanePromises.set(lane.id, p)
      return p
    }

    const fastLane = lanes.find((x) => x.id === "fast_keyword_strict") || lanes[0]
    const semanticLane = lanes.find((x) => x.id === "semantic") || null
    const nonSemanticLanes = lanes.filter((x) => x.id !== "semantic")

    const fastPromise = start_lane(fastLane)
    const eagerPromises = nonSemanticLanes.map((lane) => start_lane(lane))

    const semanticTriggerPromise = semanticLane
      ? (async () => {
          await Promise.race([Promise.allSettled(eagerPromises), sleep(2200)])
          if (seq !== search_seq) return null

          const skipReason = semantic_skip_reason({ laneResults, lanes })
          if (skipReason) {
            laneSkipped.set(semanticLane.id, skipReason)
            commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt })
            return { skipped: true, reason: skipReason }
          }

          return await start_lane(semanticLane)
        })()
      : Promise.resolve(null)

    const allDonePromise = Promise.allSettled([...eagerPromises, semanticTriggerPromise])
    const deadlineMs = Math.max(300, Number(state.searchDeadlineMs) || 1000)

    const firstPhase = await Promise.race([
      fastPromise.then(() => "fast_done").catch(() => "fast_done"),
      new Promise((resolve) => {
        search_deadline_timer = setTimeout(() => resolve("deadline"), deadlineMs)
      }),
    ])

    if (seq !== search_seq) return
    commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt })

    if (firstPhase === "deadline") {
      state.searchDeadlineHit = true
      if (state.results.length > 0 && state.searchSourcesPending.length > 0) {
        state.searchPartial = true
        state.searchPhase = "partial"
        partialToastSent = true
        toast(
          "⏱️ " +
            tt("rss.center.gate.search.toast.partialDeadline", {
              count: state.results.length,
              pending: state.searchSourcesPending.length,
            }),
          "info"
        )
      } else if (state.results.length === 0 && state.searchSourcesPending.length > 0) {
        state.searchPartial = true
        state.searchPhase = "warming"
        state.searchMessage = tt("rss.center.gate.search.status.warmingRemaining", {
          pending: state.searchSourcesPending.length,
        })
      }
    } else if (state.results.length > 0 && state.searchSourcesPending.length > 0) {
      state.searchPartial = true
      state.searchPhase = "partial"
      partialToastSent = true
      toast(
        "⚡ " +
          tt("rss.center.gate.search.toast.partialFast", {
            count: state.results.length,
          }),
        "success"
      )
    }

    await allDonePromise

    if (search_deadline_timer) clearTimeout(search_deadline_timer)
    search_deadline_timer = null

    if (seq !== search_seq) return
    commit_search_snapshot({ seq, lanes, laneResults, laneErrors, laneSkipped, startedAt })

    state.searchWorking = false
    state.searchPartial = false

    if (laneResults.size === 0) {
      state.searchPhase = "error"
      state.results = []
      const firstError =
        Array.from(laneErrors.values())[0] || tt("rss.center.gate.search.errors.unknown")
      state.searchMessage = tt("rss.center.gate.search.status.failed", { error: firstError })
      toast("❌ " + tt("rss.center.gate.search.toast.failed", { error: firstError }), "error")
      return
    }

    state.searchPhase = "done"

    if (laneErrors.size > 0) {
      toast(
        "✅ " +
          tt("rss.center.gate.search.toast.doneWithFailed", {
            count: state.results.length,
            failed: laneErrors.size,
          }),
        "info"
      )
    } else if (!partialToastSent) {
      toast(
        "✅ " +
          tt("rss.center.gate.search.toast.done", {
            count: state.results.length,
          }),
        "success"
      )
    } else {
      const skipped = state.searchSourcesSkipped.length
      if (skipped > 0) {
        toast(
          "✅ " +
            tt("rss.center.gate.search.toast.completedWithSkipped", {
              count: state.results.length,
              skipped,
            }),
          "success"
        )
      } else {
        toast(
          "✅ " +
            tt("rss.center.gate.search.toast.completed", {
              count: state.results.length,
            }),
          "success"
        )
      }
    }
  }

  function toggle_all_loaded(displayResults) {
    const rows = Array.isArray(displayResults) ? displayResults : []
    if (!rows.length) return
    if (state.selectedKeys.length === rows.length) state.selectedKeys = []
    else state.selectedKeys = rows.map((x) => x.__key)
  }

  function dispose() {
    search_seq += 1
    if (search_deadline_timer) clearTimeout(search_deadline_timer)
    search_deadline_timer = null
  }

  return {
    runSearch: run_search,
    toggleAllLoaded: toggle_all_loaded,
    dispose,
  }
}
