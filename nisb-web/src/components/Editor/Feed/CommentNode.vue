<template>
  <div
    ref="nodeRef"
    class="node"
    :class="[
      `mode-${nodeMode}`,
      {
        nested: depthLevel > 0,
        replying: isReplyingHere,
        pending: nodeStatus === 'pending',
        failed: nodeStatus === 'failed',
        deleted: nodeStatus === 'deleted',
      },
    ]"
    :style="{ '--depth-pad': pad + 'px' }"
  >
    <div class="c-item" :aria-busy="voting || replySubmitting">
      <div class="c-head">
        <div class="c-meta">
          <div class="author" :title="authorLabel">
            <img v-if="avatar" class="av" :src="avatar" :alt="t('feed.commentNode.author.avatarAlt')" />
            <span v-if="nodeMode !== 'minimal'" class="u">{{ authorDisplayText }}</span>
          </div>

          <span v-if="sourceLabel && nodeMode !== 'minimal'" class="source-chip" :title="sourceTooltip">
            {{ sourceLabel }}
          </span>

          <span v-if="displayTime" class="t" :title="when">{{ displayTime }}</span>

          <span v-if="statusLabel" class="status-chip" :class="nodeStatus">
            {{ statusLabel }}
          </span>
        </div>

        <div class="acts">
          <button
            class="chip"
            type="button"
            @click="vote('like')"
            :disabled="voting"
            :title="t('feed.commentNode.vote.like')"
          >
            <span v-if="nodeMode === 'full'">{{ t("feed.commentNode.vote.like") }} {{ likeCount }}</span>
            <span v-else-if="nodeMode === 'compact'">👍 {{ likeCount }}</span>
            <span v-else>👍</span>
          </button>

          <button
            class="chip"
            type="button"
            @click="vote('downvote')"
            :disabled="voting"
            :title="t('feed.commentNode.vote.downvote')"
          >
            <span v-if="nodeMode === 'full'">{{ t("feed.commentNode.vote.downvote") }} {{ downCount }}</span>
            <span v-else-if="nodeMode === 'compact'">👎 {{ downCount }}</span>
            <span v-else>👎</span>
          </button>

          <button
            class="chip danger"
            type="button"
            @click="vote('spam')"
            :disabled="voting"
            :title="t('feed.commentNode.vote.spam')"
          >
            <span v-if="nodeMode === 'full'">{{ t("feed.commentNode.vote.spam") }} {{ spamCount }}</span>
            <span v-else-if="nodeMode === 'compact'">🚫 {{ spamCount }}</span>
            <span v-else>🚫</span>
          </button>

          <button
            class="link"
            type="button"
            @click="openReply"
            :disabled="replySubmitting"
            :title="t('feed.commentNode.actions.reply')"
          >
            {{ nodeMode === "minimal" ? "↩" : t("feed.commentNode.actions.reply") }}
          </button>

          <button
            class="link danger"
            type="button"
            @click="deleteNode"
            :disabled="replySubmitting"
            :title="t('feed.commentNode.actions.delete')"
          >
            {{ nodeMode === "minimal" ? "🗑" : t("feed.commentNode.actions.delete") }}
          </button>
        </div>
      </div>

      <div class="c-body">{{ bodyText }}</div>

      <div v-if="isReplyingHere" class="reply-box" :class="{ pending: replySubmitting }">
        <textarea
          class="ta"
          rows="3"
          :placeholder="t('feed.commentNode.editor.replyPlaceholder')"
          :value="replyDraft"
          :disabled="replySubmitting"
          @input="onInputDraft"
        ></textarea>

        <div class="reply-actions">
          <span class="reply-hint" :class="{ active: replyDraftTrimmed }">{{ replyDraftLength }}</span>

          <div class="reply-buttons">
            <button
              class="btn primary"
              type="button"
              @click="$emit('submit-reply', node.id)"
              :disabled="replySubmitting || !replyDraftTrimmed"
            >
              {{ replySubmitting ? t("feed.commentNode.actions.posting") : t("feed.commentNode.actions.post") }}
            </button>

            <button class="btn" type="button" @click="$emit('cancel-reply')" :disabled="replySubmitting">
              {{ t("feed.commentNode.actions.cancel") }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="kids.length" class="children">
      <CommentNode
        v-for="ch in kids"
        :key="ch.id"
        :node="ch"
        :depth="depth + 1"
        :childrenMap="childrenMap"
        :replyToId="replyToId"
        :replyDraft="replyDraft"
        :replySubmitting="replySubmitting"
        @update:replyDraft="forwardUpdateDraft"
        @delete="$emit('delete', $event)"
        @open-reply="$emit('open-reply', $event)"
        @cancel-reply="$emit('cancel-reply')"
        @submit-reply="$emit('submit-reply', $event)"
        @voted="$emit('voted')"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

defineOptions({ name: "CommentNode" })

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  childrenMap: { type: null, required: true },
  replyToId: { type: String, default: "" },
  replyDraft: { type: String, default: "" },
  replySubmitting: { type: Boolean, default: false },
})

const emit = defineEmits([
  "delete",
  "open-reply",
  "cancel-reply",
  "submit-reply",
  "update:replyDraft",
  "voted",
])

const { t, locale } = useI18n()
const { callTool } = useMCP()

const nodeRef = ref(null)
const nodeWidth = ref(0)
const voting = ref(false)

let ro = null
let cleanupRO = null

const nodeMode = computed(() => {
  const w = nodeWidth.value
  if (w === 0) return "full"
  if (w >= 440) return "full"
  if (w >= 300) return "compact"
  return "minimal"
})

const depthLevel = computed(() => Math.min(6, Math.max(0, Number(props.depth) || 0)))

const pad = computed(() => {
  if (depthLevel.value <= 0) return 0
  if (nodeMode.value === "minimal") return 6
  if (nodeMode.value === "compact") return 8
  return 10
})

const uid = computed(() => {
  const author = props.node?.author
  if (!author) return ""
  if (typeof author === "string") return author.trim()
  return String(author.user_id || author.userId || author.id || "").trim()
})

const authorDisplayName = computed(() => {
  return String(props.node?.author_display_name || props.node?.author?.display_name || "").trim()
})

const authorLabel = computed(() => {
  const u = uid.value
  const dn = authorDisplayName.value
  return dn ? `${dn} (@${u})` : (u || t("feed.commentNode.fallbacks.unknownAuthor"))
})

const authorDisplayText = computed(() => {
  if (nodeMode.value === "full") return authorLabel.value
  return authorDisplayName.value || uid.value || t("feed.commentNode.fallbacks.unknownAuthor")
})

const avatar = computed(() => String(props.node?.author_avatar_url || props.node?.author?.avatar_url || "").trim())

const sourceLabel = computed(() => {
  return firstString(
    props.node?.source_display_name,
    props.node?.source_name,
    props.node?.source?.display_name,
    props.node?.source?.name,
    props.node?.source_type,
    props.node?.provider,
    props.node?.origin
  )
})

const sourceTooltip = computed(() => {
  const sourceType = firstString(props.node?.source_type, props.node?.source?.type)
  const sourceId = firstString(props.node?.source_id, props.node?.source?.id, props.node?.source_ref)
  const parts = [sourceLabel.value]
  if (sourceType && sourceType !== sourceLabel.value) parts.push(sourceType)
  if (sourceId && sourceId !== sourceLabel.value) parts.push(sourceId)
  return parts.filter(Boolean).join(" · ")
})

const when = computed(() => String(props.node?.created_at || props.node?.createdAt || props.node?.createdat || ""))

const displayTime = computed(() => {
  const raw = when.value
  if (!raw) return ""

  if (nodeMode.value === "full") return raw
  if (nodeMode.value === "compact") return raw.replace(/:\d{2}Z?$/, "")

  return formatRelativeTimeShort(raw)
})

const bodyText = computed(() => {
  return String(props.node?.content_md || props.node?.contentmd || props.node?.body || props.node?.text || "")
})

const nodeStatus = computed(() => {
  const raw = String(props.node?.status || props.node?.state || "").trim().toLowerCase()

  if (props.node?.pending === true || raw === "pending" || raw === "posting" || raw === "saving") return "pending"
  if (props.node?.failed === true || raw === "failed" || raw === "error") return "failed"
  if (props.node?.deleted === true || raw === "deleted") return "deleted"

  return ""
})

const statusLabel = computed(() => {
  if (nodeStatus.value === "pending") return t("feed.commentNode.status.pending")
  if (nodeStatus.value === "failed") return t("feed.commentNode.status.failed")
  if (nodeStatus.value === "deleted") return t("feed.commentNode.status.deleted")
  return ""
})

const kids = computed(() => {
  const id = String(props.node?.id || "")
  const map = props.childrenMap

  if (!id || !map) return []
  if (typeof map.get === "function") {
    const arr = map.get(id) || []
    return Array.isArray(arr) ? arr : []
  }

  const arr = map[id] || []
  return Array.isArray(arr) ? arr : []
})

const isReplyingHere = computed(() => String(props.replyToId || "") === String(props.node?.id || ""))
const replyDraftTrimmed = computed(() => String(props.replyDraft || "").trim().length > 0)
const replyDraftLength = computed(() => String(props.replyDraft || "").length)

const likeCount = computed(() => numberFrom(props.node?.counts?.like, props.node?.like_count, 0))
const downCount = computed(() => numberFrom(props.node?.counts?.downvote_24h, props.node?.downvote_count, 0))
const spamCount = computed(() => numberFrom(props.node?.counts?.spam_7d, props.node?.spam_count, 0))

function firstString(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined") continue
    const s = String(value).trim()
    if (s) return s
  }
  return ""
}

function numberFrom(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined" || value === "") continue
    const n = Number(value)
    if (Number.isFinite(n)) return Math.max(0, n)
  }
  return 0
}

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function formatRelativeTimeShort(raw) {
  try {
    const date = new Date(raw)
    const now = new Date()
    const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000)
    const cutoffs = [60, 3600, 86400, 86400 * 7, 86400 * 30, 86400 * 365, Infinity]
    const units = ["second", "minute", "hour", "day", "week", "month", "year"]
    const unitIndex = cutoffs.findIndex((cutoff) => cutoff > Math.abs(diffSeconds))
    const divisor = unitIndex ? cutoffs[unitIndex - 1] : 1
    const value = Math.round(diffSeconds / divisor)
    const rtf = new Intl.RelativeTimeFormat(locale.value || "en", { numeric: "auto", style: "short" })
    return rtf.format(value, units[unitIndex])
  } catch {
    return raw
  }
}

function onInputDraft(e) {
  emit("update:replyDraft", String(e?.target?.value || ""))
}

function forwardUpdateDraft(v) {
  emit("update:replyDraft", String(v || ""))
}

function openReply() {
  emit("open-reply", props.node?.id)
}

function deleteNode() {
  emit("delete", props.node)
}

async function callToolCompat(candidates) {
  let lastErr = null

  for (const c of candidates) {
    try {
      const res = await callTool(c.name, c.args)
      if (!res || res.success === false) throw new Error(res?.message || t("feed.commentNode.toast.voteFailed"))
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

  throw lastErr || new Error(t("feed.commentNode.toast.voteFailed"))
}

async function vote(vote_type) {
  const cid = String(props.node?.id || "").trim()
  if (!cid || voting.value) return

  voting.value = true
  try {
    await callToolCompat([
      { name: "nisb_feed_comment_vote", args: { comment_id: cid, vote_type } },
      { name: "nisb_feed_comment_vote", args: { commentId: cid, vote_type } },
    ])
    emit("voted")
  } catch (e) {
    toast(e?.message || t("feed.commentNode.toast.voteFailed"), "error")
  } finally {
    voting.value = false
  }
}

function setupWidthObserver() {
  const el = nodeRef.value
  if (!el) return () => {}

  const apply = () => {
    nodeWidth.value = Math.round(el.getBoundingClientRect().width || 0)
  }

  apply()

  if (typeof ResizeObserver === "undefined") return () => {}

  ro = new ResizeObserver(() => apply())
  ro.observe(el)

  return () => {
    try {
      ro && ro.disconnect()
    } catch {}
    ro = null
  }
}

onMounted(() => {
  cleanupRO = setupWidthObserver()
})

onUnmounted(() => {
  cleanupRO && cleanupRO()
  cleanupRO = null
})
</script>

<style scoped>
.node {
  position: relative;
  min-width: 0;
  margin-top: 0.56rem;
  margin-left: var(--depth-pad);
  color: var(--text, var(--text-main));
  font-size: inherit;
  line-height: inherit;
}

.node.nested::before {
  content: "";
  position: absolute;
  left: calc(var(--depth-pad) * -0.5);
  top: 0.24rem;
  bottom: 0.24rem;
  width: 2px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
  pointer-events: none;
}

.node.replying::before {
  background: color-mix(in srgb, var(--selected) 58%, transparent);
}

.c-item {
  min-width: 0;
  box-sizing: border-box;
  padding: 0.62rem 0.66rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.node.replying .c-item {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 7%, transparent) inset,
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
}

.node.pending .c-item {
  border-color: rgba(217, 119, 6, 0.3);
}

.node.failed .c-item {
  border-color: rgba(239, 68, 68, 0.3);
  background:
    radial-gradient(circle at 0% 0%, rgba(239, 68, 68, 0.07), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
}

.node.deleted .c-item {
  opacity: 0.78;
}

.c-head {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.58rem;
}

.c-meta {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.35;
}

.author {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.34rem;
  flex: 0 1 auto;
}

.av {
  flex: 0 0 auto;
  width: 1.34rem;
  height: 1.34rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  object-fit: cover;
}

.u {
  min-width: 0;
  max-width: min(260px, 42vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 760;
}

.t {
  flex: 0 0 auto;
  color: var(--text-secondary);
  white-space: nowrap;
  font-size: 0.72rem;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}

.source-chip,
.status-chip {
  flex: 0 1 auto;
  min-width: 0;
  max-width: min(220px, 38vw);
  min-height: 21px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.44rem;
  border: 1px solid color-mix(in srgb, var(--line) 72%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 46%, transparent);
  color: var(--text-secondary);
  font-size: 0.66rem;
  font-weight: 760;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-chip.pending {
  border-color: rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.09);
  color: #d97706;
}

.status-chip.failed,
.status-chip.deleted {
  border-color: rgba(239, 68, 68, 0.26);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.acts {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.32rem;
  flex-wrap: wrap;
}

.chip {
  flex: 0 0 auto;
  min-height: 27px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.54rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 999px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 54%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 68%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.7rem;
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

.chip:hover:not(:disabled),
.chip:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 9%, transparent),
    0 8px 16px rgba(0, 0, 0, 0.07);
  outline: none;
}

.chip.danger:hover:not(:disabled),
.chip.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.48);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 8px 16px rgba(0, 0, 0, 0.07);
}

.chip:active:not(:disabled) {
  transform: translateY(1px);
}

.chip:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.link {
  flex: 0 0 auto;
  min-height: 27px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.36rem;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    opacity 0.15s ease;
}

.link:hover:not(:disabled),
.link:focus-visible:not(:disabled) {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
  outline: none;
}

.link.danger:hover:not(:disabled),
.link.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.link:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.c-body {
  min-width: 0;
  margin-top: 0.56rem;
  color: var(--text, var(--text-main));
  font-size: 0.82rem;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.reply-box {
  min-width: 0;
  margin-top: 0.68rem;
  padding-top: 0.66rem;
  border-top: 1px dashed color-mix(in srgb, var(--line) 72%, transparent);
}

.reply-box.pending {
  opacity: 0.78;
}

.ta {
  width: 100%;
  min-width: 0;
  min-height: 76px;
  max-height: 220px;
  box-sizing: border-box;
  resize: vertical;
  padding: 0.56rem 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  outline: none;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text, var(--text-main));
  font-family: inherit;
  font-size: 0.8rem;
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

.reply-actions {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  margin-top: 0.48rem;
}

.reply-hint {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.reply-hint.active {
  color: var(--selected);
}

.reply-buttons {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.42rem;
}

.btn {
  flex: 0 0 auto;
  min-height: 29px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.66rem;
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
  font-size: 0.74rem;
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

.children {
  min-width: 0;
  margin-top: 0.46rem;
}

.mode-compact .c-item {
  padding: 0.58rem 0.6rem;
}

.mode-compact .c-head {
  gap: 0.46rem;
}

.mode-compact .u {
  max-width: min(210px, 40vw);
}

.mode-compact .source-chip {
  max-width: min(170px, 34vw);
}

.mode-compact .c-body {
  font-size: 0.8rem;
}

.mode-minimal .c-item {
  padding: 0.54rem 0.56rem;
  border-radius: 13px;
}

.mode-minimal .c-head {
  flex-wrap: wrap;
  gap: 0.42rem;
}

.mode-minimal .c-meta {
  flex: 1 1 100%;
  gap: 0.32rem;
}

.mode-minimal .acts {
  flex: 1 1 100%;
  justify-content: flex-start;
  gap: 0.3rem;
}

.mode-minimal .chip,
.mode-minimal .link {
  min-height: 28px;
}

.mode-minimal .chip {
  min-width: 30px;
  padding: 0 0.42rem;
  font-size: 0.82rem;
}

.mode-minimal .link {
  min-width: 30px;
  padding: 0 0.38rem;
  font-size: 0.82rem;
}

.mode-minimal .c-body {
  margin-top: 0.5rem;
  font-size: 0.78rem;
  line-height: 1.55;
}

@media (max-width: 720px) {
  .node {
    margin-left: min(var(--depth-pad), 8px);
  }

  .node.nested::before {
    left: -5px;
  }

  .c-head {
    flex-wrap: wrap;
  }

  .c-meta {
    flex: 1 1 100%;
    overflow: visible;
  }

  .acts {
    flex: 1 1 100%;
    justify-content: flex-start;
  }

  .u {
    max-width: 54vw;
  }

  .reply-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .reply-hint {
    align-self: flex-end;
  }

  .reply-buttons {
    width: 100%;
    justify-content: stretch;
  }

  .reply-buttons .btn {
    flex: 1 1 0;
  }
}

@media (max-width: 420px) {
  .node {
    margin-left: min(var(--depth-pad), 6px);
  }

  .c-item {
    padding: 0.52rem;
  }

  .av {
    width: 1.22rem;
    height: 1.22rem;
  }

  .t,
  .status-chip,
  .source-chip {
    font-size: 0.64rem;
  }

  .reply-buttons {
    flex-direction: column;
  }

  .reply-buttons .btn {
    width: 100%;
  }

  .ta {
    min-height: 90px;
  }
}
</style>
