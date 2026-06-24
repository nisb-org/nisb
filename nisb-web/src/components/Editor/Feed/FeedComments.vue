<template>
  <div class="c-wrap">
    <div class="c-top">
      <div class="title-stack">
        <div class="c-title">
          <span>{{ t("feed.comments.title") }}</span>
          <span class="c-subtle" v-if="flatItems.length">({{ flatItems.length }})</span>
        </div>

        <div class="state-line">
          <span v-if="loading" class="state-chip pending">{{ t("feed.comments.states.loading") }}</span>
          <span v-else-if="flatItems.length" class="state-chip active">{{ flatItems.length }}</span>
          <span v-else class="state-chip">{{ t("feed.comments.states.empty") }}</span>
        </div>
      </div>

      <button class="btn" type="button" @click="refresh" :disabled="loading || submitting || replySubmitting">
        {{ loading ? t("feed.comments.actions.loading") : t("feed.comments.actions.refresh") }}
      </button>
    </div>

    <div class="c-new" :class="{ pending: submitting, failed: !!submitError }">
      <textarea
        v-model="draft"
        class="ta"
        rows="3"
        :placeholder="t('feed.comments.editor.placeholder')"
        :disabled="submitting"
      ></textarea>

      <div v-if="submitError" class="inline-error">{{ submitError }}</div>

      <div class="c-new-actions">
        <span class="draft-hint" :class="{ active: draft.trim() }">{{ draftLength }}</span>

        <button class="btn primary" type="button" @click="submitRoot" :disabled="submitting || !draft.trim()">
          {{ submitting ? t("feed.comments.actions.posting") : t("feed.comments.actions.post") }}
        </button>
      </div>
    </div>

    <div v-if="loading && flatItems.length === 0" class="state-card loading">
      <div class="skeleton-line short"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line wide"></div>
    </div>

    <div v-else-if="listError && flatItems.length === 0" class="state-card error">
      <div class="state-title">{{ t("feed.comments.toast.loadFailed") }}</div>
      <div class="state-desc">{{ listError }}</div>
      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.comments.actions.loading") : t("feed.comments.actions.refresh") }}
      </button>
    </div>

    <div v-else-if="roots.length === 0" class="state-card empty">
      <div class="state-title">{{ t("feed.comments.states.empty") }}</div>
    </div>

    <div v-else class="tree">
      <div v-if="listError" class="inline-error tree-error">
        <span>{{ listError }}</span>
        <button class="btn mini" type="button" @click="refresh" :disabled="loading">
          {{ loading ? t("feed.comments.actions.loading") : t("feed.comments.actions.refresh") }}
        </button>
      </div>

      <CommentNode
        v-for="it in roots"
        :key="it.id"
        :node="it"
        :depth="0"
        :childrenMap="childrenMap"
        :replyToId="replyToId"
        v-model:replyDraft="replyDraft"
        :replySubmitting="replySubmitting"
        @delete="del"
        @open-reply="openReply"
        @cancel-reply="cancelReply"
        @submit-reply="submitReply"
        @voted="onVoted"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"
import CommentNode from "./CommentNode.vue"

const props = defineProps({ feedId: { type: String, required: true } })
const emit = defineEmits(["changed"])

const { t } = useI18n()
const { callTool } = useMCP()

const flatItems = ref([])
const loading = ref(false)
const submitting = ref(false)
const draft = ref("")
const listError = ref("")
const submitError = ref("")

const replyToId = ref("")
const replyDraft = ref("")
const replySubmitting = ref(false)

let requestSeq = 0

const draftLength = computed(() => String(draft.value || "").length)

const childrenMap = computed(() => {
  const mp = new Map()

  for (const it of flatItems.value) {
    const pid = String(it?.parent_id || it?.parentId || "").trim()
    if (!pid) continue
    if (!mp.has(pid)) mp.set(pid, [])
    mp.get(pid).push(it)
  }

  for (const [k, arr] of mp.entries()) {
    arr.sort(compareCommentTimeDesc)
    mp.set(k, arr)
  }

  return mp
})

const roots = computed(() => {
  const ids = new Set(flatItems.value.map((x) => String(x?.id || "")).filter(Boolean))
  const out = []

  for (const it of flatItems.value) {
    const pid = String(it?.parent_id || it?.parentId || "").trim()
    if (!pid || !ids.has(pid)) out.push(it)
  }

  out.sort(compareCommentTimeDesc)
  return out
})

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function getCommentTime(it) {
  return String(it?.created_at || it?.createdAt || it?.createdat || it?.updated_at || it?.updatedAt || "")
}

function compareCommentTimeDesc(a, b) {
  return getCommentTime(b).localeCompare(getCommentTime(a))
}

function normalizeComments(items) {
  if (!Array.isArray(items)) return []

  return items
    .filter((it) => it && typeof it === "object")
    .filter((it) => String(it.id || "").trim())
}

async function callToolCompat(candidates) {
  let lastErr = null

  for (const c of candidates) {
    try {
      const res = await callTool(c.name, c.args)
      if (!res || res.success === false) throw new Error(res?.message || t("feed.comments.errors.toolFailed"))
      return res
    } catch (e) {
      lastErr = e
      const msg = String(e?.message || "")
      const retryable =
        msg.toLowerCase().includes("not found") ||
        msg.toLowerCase().includes("missing") ||
        msg.toLowerCase().includes("invalid")
      if (!retryable) throw e
    }
  }

  throw lastErr || new Error(t("feed.comments.errors.allToolCandidatesFailed"))
}

async function refresh() {
  const feedId = String(props.feedId || "").trim()
  if (!feedId) return

  const seq = ++requestSeq
  loading.value = true
  listError.value = ""

  try {
    const res = await callToolCompat([
      { name: "nisb_feed_comment_list", args: { feed_id: feedId, limit: 300 } },
      { name: "nisb_feed_comment_list", args: { feedId, limit: 300 } },
    ])

    if (seq !== requestSeq) return
    flatItems.value = normalizeComments(res.items)
  } catch (e) {
    if (seq !== requestSeq) return
    listError.value = e?.message || t("feed.comments.toast.loadFailed")
    toast(listError.value, "error")
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function submitRoot() {
  const feedId = String(props.feedId || "").trim()
  const content = String(draft.value || "").trim()

  if (!feedId || !content) return

  submitting.value = true
  submitError.value = ""

  try {
    await callToolCompat([
      { name: "nisb_feed_comment_add", args: { feed_id: feedId, content_md: content } },
      { name: "nisb_feed_comment_add", args: { feedId, contentmd: content } },
    ])

    draft.value = ""

    try {
      await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
    } catch {}

    await refresh()
    emit("changed")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    submitError.value = e?.message || t("feed.comments.toast.postFailed")
    toast(submitError.value, "error")
  } finally {
    submitting.value = false
  }
}

function openReply(id) {
  replyToId.value = String(id || "")
  replyDraft.value = ""
}

function cancelReply() {
  replyToId.value = ""
  replyDraft.value = ""
}

async function submitReply(parentId) {
  const feedId = String(props.feedId || "").trim()
  const pid = String(parentId || "").trim()
  const content = String(replyDraft.value || "").trim()

  if (!feedId || !pid) return

  if (!content) {
    toast(t("feed.comments.toast.replyEmpty"), "error")
    return
  }

  replySubmitting.value = true

  try {
    await callToolCompat([
      { name: "nisb_feed_comment_add", args: { feed_id: feedId, content_md: content, parent_id: pid } },
      { name: "nisb_feed_comment_add", args: { feedId, contentmd: content, parentId: pid } },
    ])

    replyToId.value = ""
    replyDraft.value = ""

    try {
      await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
    } catch {}

    await refresh()
    emit("changed")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    toast(e?.message || t("feed.comments.toast.replyFailed"), "error")
  } finally {
    replySubmitting.value = false
  }
}

async function del(it) {
  if (!it?.id) return

  try {
    await callToolCompat([
      { name: "nisb_feed_comment_delete", args: { comment_id: String(it.id) } },
      { name: "nisb_feed_comment_delete", args: { commentId: String(it.id) } },
    ])

    try {
      await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
    } catch {}

    await refresh()
    emit("changed")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    toast(e?.message || t("feed.comments.toast.deleteFailed"), "error")
  }
}

async function onVoted() {
  try {
    await callToolCompat([{ name: "nisb_feed_compact", args: {} }])
  } catch {}

  await refresh()
  window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
}

watch(
  () => props.feedId,
  () => {
    requestSeq += 1
    flatItems.value = []
    listError.value = ""
    submitError.value = ""
    replyToId.value = ""
    replyDraft.value = ""
    refresh()
  },
  { immediate: true }
)

onUnmounted(() => {
  requestSeq += 1
})
</script>

<style scoped>
.c-wrap {
  min-width: 0;
  box-sizing: border-box;
  padding: 0.76rem 0.9rem 0.9rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  color: var(--text, var(--text-main));
}

.c-top {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
}

.title-stack {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
}

.c-title {
  min-width: 0;
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.3;
  overflow-wrap: break-word;
}

.c-subtle {
  color: var(--text-secondary);
  font-size: 0.74rem;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
}

.state-line {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.state-chip {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
}

.state-chip.active {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
}

.state-chip.pending {
  border-color: rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
}

.c-new {
  min-width: 0;
  margin-top: 0.68rem;
  padding: 0.58rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 36%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.c-new.pending {
  border-color: rgba(217, 119, 6, 0.28);
}

.c-new.failed {
  border-color: rgba(239, 68, 68, 0.3);
  background:
    radial-gradient(circle at 0% 0%, rgba(239, 68, 68, 0.07), transparent 36%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.ta {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  resize: vertical;
  min-height: 76px;
  max-height: 220px;
  padding: 0.58rem 0.64rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  outline: none;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text, var(--text-main));
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.5;
  overflow-wrap: break-word;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

.ta::placeholder {
  color: var(--text-secondary);
  opacity: 0.72;
}

.ta:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent);
}

.ta:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.c-new-actions {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  margin-top: 0.48rem;
}

.draft-hint {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.draft-hint.active {
  color: var(--selected);
}

.tree {
  min-width: 0;
  margin-top: 0.72rem;
}

.state-card {
  min-width: 0;
  box-sizing: border-box;
  margin-top: 0.72rem;
  padding: 0.86rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 74%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  color: var(--text-secondary);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.state-card.empty {
  text-align: center;
}

.state-card.error {
  border-color: rgba(239, 68, 68, 0.28);
  background:
    radial-gradient(circle at 0% 0%, rgba(239, 68, 68, 0.08), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.state-title {
  color: var(--text, var(--text-main));
  font-size: 0.82rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.state-card.error .state-title {
  color: #ef4444;
}

.state-desc {
  margin-top: 0.42rem;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.55;
  overflow-wrap: break-word;
}

.state-card .btn {
  margin-top: 0.7rem;
}

.inline-error {
  min-width: 0;
  box-sizing: border-box;
  margin-top: 0.46rem;
  padding: 0.5rem 0.58rem;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 11px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  font-size: 0.74rem;
  font-weight: 720;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.tree-error {
  margin: 0 0 0.72rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
}

.tree-error span {
  min-width: 0;
  overflow-wrap: break-word;
}

.skeleton-line {
  display: block;
  height: 12px;
  margin-top: 0.58rem;
  border-radius: 999px;
  background:
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--line) 42%, transparent),
      color-mix(in srgb, var(--selected-bg) 28%, transparent),
      color-mix(in srgb, var(--line) 42%, transparent)
    );
  background-size: 220% 100%;
  animation: shimmer 1.3s ease-in-out infinite;
}

.skeleton-line:first-child {
  margin-top: 0;
}

.skeleton-line.short {
  width: 38%;
}

.skeleton-line.wide {
  width: 86%;
}

@keyframes shimmer {
  0% {
    background-position: 120% 0;
  }

  100% {
    background-position: -120% 0;
  }
}

.btn {
  flex: 0 0 auto;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 74%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  box-shadow: 0 1px 0 color-mix(in srgb, white 7%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.btn.mini {
  min-height: 28px;
  padding: 0 0.58rem;
  font-size: 0.72rem;
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 52%, transparent),
      color-mix(in srgb, var(--editor-bg) 60%, transparent)
    );
  color: var(--selected);
  font-weight: 820;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 46%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .c-wrap {
    padding: 0.68rem 0.66rem 0.8rem;
  }

  .c-top {
    gap: 0.56rem;
  }

  .c-new {
    padding: 0.52rem;
  }

  .tree-error {
    align-items: stretch;
    flex-direction: column;
  }

  .tree-error .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .c-wrap {
    padding: 0.62rem 0.52rem 0.72rem;
  }

  .c-top {
    align-items: stretch;
    flex-direction: column;
  }

  .c-top > .btn {
    width: 100%;
  }

  .c-new-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .c-new-actions .btn {
    width: 100%;
  }

  .draft-hint {
    align-self: flex-end;
  }

  .ta {
    min-height: 90px;
  }
}
</style>
