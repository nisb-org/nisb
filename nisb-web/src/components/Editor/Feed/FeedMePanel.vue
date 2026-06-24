<template>
  <div ref="wrapRef" class="me-wrap" :class="`mode-${panelMode}`">
    <div class="me-top">
      <div class="title-stack">
        <div class="me-title">{{ t("feed.mePanel.title") }}</div>
        <div class="me-subtitle">{{ t("feed.mePanel.subtitle") }}</div>

        <div class="state-row">
          <span class="state-chip">{{ t("feed.mePanel.tabs.bookmarks") }} · {{ bookmarks.length }}</span>
          <span class="state-chip">{{ t("feed.mePanel.tabs.following") }} · {{ following.length }}</span>
          <span class="state-chip">{{ t("feed.mePanel.tabs.followers") }} · {{ followers.length }}</span>
        </div>
      </div>

      <button class="btn" type="button" @click="refresh" :disabled="loading || saving || uploading">
        {{ loading ? t("feed.mePanel.actions.loading") : t("feed.mePanel.actions.refresh") }}
      </button>
    </div>

    <div class="tabs" role="tablist" :aria-label="t('feed.mePanel.tabs.ariaLabel')">
      <button
        v-for="def in tabDefs"
        :key="def.id"
        class="tab"
        :class="{ active: tab === def.id }"
        type="button"
        role="tab"
        :aria-selected="tab === def.id"
        :title="def.label"
        @click="tab = def.id"
      >
        <span class="tab-icon">{{ def.icon }}</span>
        <span v-if="panelMode !== 'minimal'" class="tab-label">{{ def.label }}</span>
        <span v-if="panelMode === 'full' && def.count !== null" class="tab-count">{{ def.count }}</span>
      </button>
    </div>

    <div v-if="loading && !hasLoaded" class="state-list" aria-busy="true">
      <div v-for="n in 4" :key="n" class="skeleton-card">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line title"></div>
        <div class="skeleton-line body"></div>
      </div>
    </div>

    <div v-else-if="error && !hasAnyData" class="state-card error">
      <div class="state-title">{{ t("feed.mePanel.toast.refreshFailed") }}</div>
      <div class="state-desc">{{ error }}</div>
      <button class="btn" type="button" @click="refresh" :disabled="loading">
        {{ loading ? t("feed.mePanel.actions.loading") : t("feed.mePanel.actions.refresh") }}
      </button>
    </div>

    <template v-else>
      <div v-if="error" class="inline-error">
        <span>{{ error }}</span>
        <button class="btn mini" type="button" @click="refresh" :disabled="loading">
          {{ loading ? t("feed.mePanel.actions.loading") : t("feed.mePanel.actions.refresh") }}
        </button>
      </div>

      <section v-if="tab === 'profile'" class="card profile-card">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t("feed.mePanel.profile.title") }}</div>
            <div class="section-desc">{{ t("feed.mePanel.profile.desc") }}</div>
          </div>
          <span v-if="profile.updated_at" class="meta-chip" :title="profile.updated_at">
            {{ profile.updated_at }}
          </span>
        </div>

        <div class="profile-grid">
          <div class="row" :class="{ compact: panelMode !== 'full' }">
            <div class="label">{{ t("feed.mePanel.labels.userId") }}</div>
            <div class="value mono">{{ profile.user_id || "—" }}</div>
          </div>

          <div class="row avatar-row-wrap" :class="{ compact: panelMode !== 'full' }">
            <div class="label">{{ t("feed.mePanel.labels.avatar") }}</div>
            <div class="avatar-row">
              <img
                v-if="draftAvatarUrl"
                class="big-av"
                :src="draftAvatarUrl"
                :alt="t('feed.mePanel.avatar.alt')"
              />
              <div v-else class="avatar-placeholder" aria-hidden="true">👤</div>

              <div class="avatar-actions">
                <input
                  ref="fileRef"
                  class="file"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  :aria-label="t('feed.mePanel.avatar.inputLabel')"
                  @change="onPickFile"
                />

                <button class="btn" type="button" @click="triggerPick" :disabled="uploading || saving">
                  {{ uploading ? t("feed.mePanel.actions.uploading") : t("feed.mePanel.actions.uploadAvatar") }}
                </button>

                <button class="btn" type="button" @click="clearAvatar" :disabled="saving || uploading || !draftAvatarUrl">
                  {{ t("feed.mePanel.actions.clear") }}
                </button>
              </div>
            </div>
          </div>

          <div class="row" :class="{ compact: panelMode !== 'full' }">
            <div class="label">{{ t("feed.mePanel.labels.displayName") }}</div>
            <input
              v-model="draftDisplayName"
              class="input"
              :placeholder="t('feed.mePanel.placeholders.displayName')"
              :disabled="saving || uploading"
            />
          </div>

          <div class="row" :class="{ compact: panelMode !== 'full' }">
            <div class="label">{{ t("feed.mePanel.labels.bio") }}</div>
            <textarea
              v-model="draftBio"
              class="ta"
              rows="4"
              :placeholder="t('feed.mePanel.placeholders.bio')"
              :disabled="saving || uploading"
            ></textarea>
          </div>
        </div>

        <div class="actions">
          <button class="btn primary" type="button" @click="save" :disabled="saving || uploading">
            {{ saving ? t("feed.mePanel.actions.saving") : t("feed.mePanel.actions.save") }}
          </button>
        </div>

        <div class="hint">
          {{ t("feed.mePanel.profile.hint") }}
        </div>
      </section>

      <section v-else-if="tab === 'bookmarks'" class="list-section">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t("feed.mePanel.bookmarks.title") }}</div>
            <div class="section-desc">{{ t("feed.mePanel.bookmarks.desc") }}</div>
          </div>
          <span class="meta-chip">{{ bookmarks.length }}</span>
        </div>

        <div v-if="bookmarks.length === 0 && !loading" class="state-card empty">
          <div class="state-title">{{ t("feed.mePanel.states.noBookmarks") }}</div>
        </div>

        <div v-else class="item-list">
          <div v-for="it in bookmarks" :key="bookmarkKey(it)" class="bm-item">
            <button class="bm-main" type="button" @click="openFeed(it)">
              <div class="li-title">{{ bookmarkTitle(it) }}</div>
              <div class="li-sub">
                <span class="mono">{{ bookmarkKey(it) }}</span>
                <span v-if="bookmarkTime(it)" class="dot">·</span>
                <span v-if="bookmarkTime(it)">{{ bookmarkTime(it) }}</span>
              </div>
            </button>

            <button
              class="bm-x"
              type="button"
              :title="t('feed.mePanel.actions.removeBookmark')"
              @click="removeBookmark(it)"
              :disabled="busyBookmarkId === bookmarkKey(it)"
            >
              {{ busyBookmarkId === bookmarkKey(it) ? "…" : "×" }}
            </button>
          </div>
        </div>
      </section>

      <section v-else-if="tab === 'following'" class="list-section">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t("feed.mePanel.following.title") }}</div>
            <div class="section-desc">{{ t("feed.mePanel.following.desc") }}</div>
          </div>
          <span class="meta-chip">{{ filteredFollowing.length }} / {{ following.length }}</span>
        </div>

        <div class="search-row">
          <input
            v-model="qFollowing"
            class="input"
            :placeholder="t('feed.mePanel.placeholders.searchFollowing')"
          />
        </div>

        <div v-if="filteredFollowing.length === 0 && !loading" class="state-card empty">
          <div class="state-title">{{ t("feed.mePanel.states.noFollowing") }}</div>
        </div>

        <div v-else class="item-list">
          <div v-for="u in filteredFollowing" :key="u.user_id" class="user-row">
            <img v-if="u.avatar_url" class="av" :src="u.avatar_url" :alt="t('feed.mePanel.avatar.alt')" />
            <div v-else class="av fallback" aria-hidden="true">👤</div>

            <div class="u-text">
              <div class="u-name" :title="u.user_id">{{ userLabel(u) }}</div>
              <div class="u-id mono">{{ u.user_id }}</div>
            </div>

            <button
              class="btn mini danger"
              type="button"
              :title="t('feed.mePanel.actions.unfollow')"
              @click="unfollow(u.user_id)"
              :disabled="busyUserId === u.user_id"
            >
              {{ busyUserId === u.user_id ? t("feed.mePanel.actions.working") : compactAction("unfollow") }}
            </button>
          </div>
        </div>
      </section>

      <section v-else class="list-section">
        <div class="section-head">
          <div>
            <div class="section-title">{{ t("feed.mePanel.followers.title") }}</div>
            <div class="section-desc">{{ t("feed.mePanel.followers.desc") }}</div>
          </div>
          <span class="meta-chip">{{ filteredFollowers.length }} / {{ followers.length }}</span>
        </div>

        <div class="search-row">
          <input
            v-model="qFollowers"
            class="input"
            :placeholder="t('feed.mePanel.placeholders.searchFollowers')"
          />
        </div>

        <div v-if="filteredFollowers.length === 0 && !loading" class="state-card empty">
          <div class="state-title">{{ t("feed.mePanel.states.noFollowers") }}</div>
        </div>

        <div v-else class="item-list">
          <div v-for="u in filteredFollowers" :key="u.user_id" class="user-row">
            <img v-if="u.avatar_url" class="av" :src="u.avatar_url" :alt="t('feed.mePanel.avatar.alt')" />
            <div v-else class="av fallback" aria-hidden="true">👤</div>

            <div class="u-text">
              <div class="u-name" :title="u.user_id">{{ userLabel(u) }}</div>
              <div class="u-id mono">{{ u.user_id }}</div>
            </div>

            <button
              v-if="u.user_id && u.user_id !== profile.user_id"
              class="btn mini"
              type="button"
              :title="isFollowing(u.user_id) ? t('feed.mePanel.actions.unfollow') : t('feed.mePanel.actions.followBack')"
              @click="toggleFollowBack(u.user_id)"
              :disabled="busyUserId === u.user_id"
            >
              <template v-if="busyUserId === u.user_id">
                {{ t("feed.mePanel.actions.working") }}
              </template>
              <template v-else>
                {{ compactAction(isFollowing(u.user_id) ? "unfollow" : "followBack") }}
              </template>
            </button>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue"
import { useI18n } from "vue-i18n"
import useMCP from "../../../composables/useMCP"

const emit = defineEmits(["open-feed"])
const { t } = useI18n()
const { callTool } = useMCP()

const wrapRef = ref(null)
const panelWidth = ref(0)
let ro = null
let cleanupRO = null
let requestSeq = 0

const tab = ref("profile")
const loading = ref(false)
const saving = ref(false)
const error = ref("")
const hasLoaded = ref(false)

const uploading = ref(false)
const fileRef = ref(null)

const profile = ref({ user_id: "", display_name: "", bio: "", avatar_url: "", updated_at: "" })
const draftDisplayName = ref("")
const draftBio = ref("")
const draftAvatarUrl = ref("")

const bookmarks = ref([])
const following = ref([])
const followers = ref([])
const qFollowing = ref("")
const qFollowers = ref("")
const busyUserId = ref("")
const busyBookmarkId = ref("")

const panelMode = computed(() => {
  const w = panelWidth.value
  if (w === 0) return "full"
  if (w >= 520) return "full"
  if (w >= 360) return "compact"
  return "minimal"
})

const tabDefs = computed(() => [
  { id: "profile", icon: "👤", label: t("feed.mePanel.tabs.profile"), count: null },
  { id: "bookmarks", icon: "⭐", label: t("feed.mePanel.tabs.bookmarks"), count: bookmarks.value.length },
  { id: "following", icon: "👥", label: t("feed.mePanel.tabs.following"), count: following.value.length },
  { id: "followers", icon: "🫂", label: t("feed.mePanel.tabs.followers"), count: followers.value.length },
])

const hasAnyData = computed(() => {
  return (
    !!profile.value?.user_id ||
    bookmarks.value.length > 0 ||
    following.value.length > 0 ||
    followers.value.length > 0
  )
})

const followingSet = computed(() => {
  const s = new Set()
  for (const u of following.value) {
    const uid = String(u?.user_id || "").trim()
    if (uid) s.add(uid)
  }
  return s
})

const filteredFollowing = computed(() => {
  const q = qFollowing.value.trim().toLowerCase()
  if (!q) return following.value

  return following.value.filter((u) => {
    const uid = String(u?.user_id || "").toLowerCase()
    const dn = String(u?.display_name || "").toLowerCase()
    return uid.includes(q) || dn.includes(q)
  })
})

const filteredFollowers = computed(() => {
  const q = qFollowers.value.trim().toLowerCase()
  if (!q) return followers.value

  return followers.value.filter((u) => {
    const uid = String(u?.user_id || "").toLowerCase()
    const dn = String(u?.display_name || "").toLowerCase()
    return uid.includes(q) || dn.includes(q)
  })
})

function firstString(...values) {
  for (const value of values) {
    if (value === null || typeof value === "undefined") continue
    const s = String(value).trim()
    if (s) return s
  }
  return ""
}

function toast(message, type = "info") {
  window.dispatchEvent(new CustomEvent("nisb-toast", { detail: { message, type } }))
}

function compactAction(kind) {
  if (panelMode.value === "minimal") {
    if (kind === "unfollow") return "✖"
    if (kind === "followBack") return "➕"
  }

  if (kind === "unfollow") return t("feed.mePanel.actions.unfollow")
  if (kind === "followBack") return t("feed.mePanel.actions.followBack")
  return ""
}

function syncDraft() {
  draftDisplayName.value = String(profile.value.display_name || "")
  draftBio.value = String(profile.value.bio || "")
  draftAvatarUrl.value = String(profile.value.avatar_url || "")
}

function normalizeProfile(item) {
  const src = item && typeof item === "object" ? item : {}

  return {
    user_id: firstString(src.user_id, src.userId, src.id, profile.value.user_id),
    display_name: firstString(src.display_name, src.displayName),
    bio: String(src.bio || ""),
    avatar_url: firstString(src.avatar_url, src.avatarUrl),
    updated_at: firstString(src.updated_at, src.updatedAt),
  }
}

function normalizeUserList(arr) {
  const out = []
  if (!Array.isArray(arr)) return out

  for (const x of arr) {
    if (!x) continue

    if (typeof x === "string") {
      const uid = x.trim()
      if (uid) out.push({ user_id: uid, display_name: "", avatar_url: "" })
      continue
    }

    if (typeof x === "object") {
      const uid = firstString(x.user_id, x.userId, x.id)
      if (!uid) continue

      out.push({
        user_id: uid,
        display_name: firstString(x.display_name, x.displayName, x.name),
        avatar_url: firstString(x.avatar_url, x.avatarUrl),
      })
    }
  }

  return out
}

function normalizeBookmarks(arr) {
  if (!Array.isArray(arr)) return []
  return arr.filter((it) => it && typeof it === "object").filter((it) => bookmarkKey(it))
}

function userLabel(u) {
  const uid = String(u?.user_id || "").trim()
  const dn = String(u?.display_name || "").trim()

  if (!uid) return t("feed.mePanel.fallbacks.unknownUser")
  return dn ? `${dn} (@${uid})` : uid
}

function bookmarkKey(it) {
  return firstString(it?.id, it?.feed_id, it?.feedId, it?.target_feed_id, it?.targetFeedId)
}

function bookmarkTitle(it) {
  return firstString(it?.title, it?.name, it?.summary) || t("feed.mePanel.fallbacks.untitled")
}

function bookmarkTime(it) {
  return firstString(it?.bookmark_at, it?.bookmarkAt, it?.created_at, it?.createdAt)
}

function isFollowing(uid) {
  return followingSet.value.has(String(uid || "").trim())
}

async function callToolCompat(candidates, fallbackMessage) {
  let lastErr = null

  for (const c of candidates) {
    try {
      const res = await callTool(c.name, c.args || {})
      if (!res || res.success === false) throw new Error(res?.message || fallbackMessage)
      return res
    } catch (e) {
      lastErr = e
      const msg = String(e?.message || "").toLowerCase()
      const retryable = msg.includes("not found") || msg.includes("missing") || msg.includes("invalid")
      if (!retryable) throw e
    }
  }

  throw lastErr || new Error(fallbackMessage)
}

async function refresh() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ""

  try {
    const p = await callTool("nisb_feed_get_profile", {})
    if (!p || p.success === false) throw new Error(p?.message || t("feed.mePanel.toast.loadProfileFailed"))
    if (seq !== requestSeq) return

    profile.value = normalizeProfile(p.item || {})
    syncDraft()

    const bm = await callTool("nisb_feed_list_bookmarks", { limit: 200 })
    if (seq !== requestSeq) return
    bookmarks.value = normalizeBookmarks(bm?.items || [])

    const fg = await callToolCompat(
      [
        { name: "nisb_feed_following_list_v2", args: {} },
        { name: "nisb_feed_following_list", args: {} },
      ],
      t("feed.mePanel.toast.refreshFailed")
    )
    if (seq !== requestSeq) return
    following.value = normalizeUserList(fg?.items || [])

    const fr = await callToolCompat(
      [
        { name: "nisb_feed_followers_list_v2", args: {} },
        { name: "nisb_feed_followers_list", args: {} },
      ],
      t("feed.mePanel.toast.refreshFailed")
    )
    if (seq !== requestSeq) return
    followers.value = normalizeUserList(fr?.items || [])

    hasLoaded.value = true
  } catch (e) {
    if (seq !== requestSeq) return
    error.value = e?.message || t("feed.mePanel.toast.refreshFailed")
    toast(error.value, "error")
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function save() {
  if (saving.value) return

  saving.value = true
  error.value = ""

  try {
    const res = await callTool("nisb_feed_update_profile", {
      display_name: draftDisplayName.value,
      bio: draftBio.value,
      avatar_url: draftAvatarUrl.value,
    })

    if (!res || res.success === false) throw new Error(res?.message || t("feed.mePanel.toast.saveFailed"))

    profile.value = normalizeProfile(res.item || {
      ...profile.value,
      display_name: draftDisplayName.value,
      bio: draftBio.value,
      avatar_url: draftAvatarUrl.value,
    })

    syncDraft()
    toast(t("feed.mePanel.toast.saved"), "success")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))
  } catch (e) {
    toast(e?.message || t("feed.mePanel.toast.saveFailed"), "error")
  } finally {
    saving.value = false
  }
}

function openFeed(it) {
  emit("open-feed", it)
}

async function removeBookmark(it) {
  const id = bookmarkKey(it)
  if (!id || busyBookmarkId.value) return

  busyBookmarkId.value = id

  try {
    const res = await callTool("nisb_feed_vote", { feed_id: id, vote_type: "unbookmark" })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.mePanel.toast.removeBookmarkFailed"))

    toast(t("feed.mePanel.toast.bookmarkRemoved"), "success")
    window.dispatchEvent(new CustomEvent("nisb-feed-refresh"))

    try {
      await callTool("nisb_feed_compact", {})
    } catch {}

    await refresh()
  } catch (e) {
    toast(e?.message || t("feed.mePanel.toast.removeBookmarkFailed"), "error")
  } finally {
    busyBookmarkId.value = ""
  }
}

async function unfollow(uid) {
  const id = String(uid || "").trim()
  if (!id || busyUserId.value) return

  busyUserId.value = id

  try {
    const res = await callTool("nisb_feed_unfollow", { target_user_id: id })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.mePanel.toast.unfollowFailed"))

    try {
      await callTool("nisb_feed_compact", {})
    } catch {}

    await refresh()
  } catch (e) {
    toast(e?.message || t("feed.mePanel.toast.unfollowFailed"), "error")
  } finally {
    busyUserId.value = ""
  }
}

async function follow(uid) {
  const id = String(uid || "").trim()
  if (!id || busyUserId.value) return

  busyUserId.value = id

  try {
    const res = await callTool("nisb_feed_follow", { target_user_id: id })
    if (!res || res.success === false) throw new Error(res?.message || t("feed.mePanel.toast.followFailed"))

    try {
      await callTool("nisb_feed_compact", {})
    } catch {}

    await refresh()
  } catch (e) {
    toast(e?.message || t("feed.mePanel.toast.followFailed"), "error")
  } finally {
    busyUserId.value = ""
  }
}

async function toggleFollowBack(uid) {
  if (isFollowing(uid)) return unfollow(uid)
  return follow(uid)
}

function triggerPick() {
  fileRef.value?.click?.()
}

function clearAvatar() {
  draftAvatarUrl.value = ""
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(String(fr.result || ""))
    fr.onerror = reject
    fr.readAsDataURL(file)
  })
}

async function onPickFile(e) {
  const file = e?.target?.files?.[0]
  if (!file) return

  uploading.value = true

  try {
    const dataUrl = await readFileAsDataURL(file)
    const up = await callTool("nisb_feed_avatar_upload", { image_base64: dataUrl })

    if (!up || up.success === false) throw new Error(up?.message || t("feed.mePanel.toast.uploadFailed"))

    draftAvatarUrl.value = String(up.avatar_url || "")
    await save()
  } catch (err) {
    toast(err?.message || t("feed.mePanel.toast.uploadFailed"), "error")
  } finally {
    uploading.value = false

    try {
      e.target.value = ""
    } catch {}
  }
}

function setupWidthObserver() {
  const el = wrapRef.value
  if (!el) return () => {}

  const apply = () => {
    panelWidth.value = Math.round(el.getBoundingClientRect().width || 0)
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
  refresh()
})

onUnmounted(() => {
  requestSeq += 1

  cleanupRO && cleanupRO()
  cleanupRO = null
})

defineExpose({ refresh })
</script>

<style scoped>
.me-wrap {
  position: relative;
  height: 100%;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.9rem;
  color: var(--text, var(--text-main));
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line) 72%, transparent) transparent;
}

.me-wrap::-webkit-scrollbar {
  width: 8px;
}

.me-wrap::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 72%, transparent);
}

.me-top {
  position: sticky;
  top: -0.9rem;
  z-index: 5;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin: -0.9rem -0.9rem 0;
  padding: 0.78rem 0.9rem 0.68rem;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent),
      color-mix(in srgb, var(--editor-bg) 64%, transparent)
    );
  backdrop-filter: blur(14px) saturate(1.05);
  -webkit-backdrop-filter: blur(14px) saturate(1.05);
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.title-stack {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.34rem;
}

.me-title {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.94rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.me-subtitle {
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 680;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.state-row {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.state-chip,
.meta-chip,
.tab-count {
  min-width: 0;
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 0.48rem;
  border: 1px solid color-mix(in srgb, var(--line) 74%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.tabs {
  position: sticky;
  top: 3.9rem;
  z-index: 4;
  min-width: 0;
  display: flex;
  gap: 0.38rem;
  margin: 0 -0.9rem 0.78rem;
  padding: 0.62rem 0.9rem;
  overflow-x: auto;
  overflow-y: hidden;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 66%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 76%, transparent);
  backdrop-filter: blur(12px) saturate(1.04);
  -webkit-backdrop-filter: blur(12px) saturate(1.04);
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tab {
  flex: 0 0 auto;
  min-height: 31px;
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  padding: 0 0.68rem;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.76rem;
  font-weight: 760;
  line-height: 1;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

.tab:hover,
.tab:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 22%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 34%, transparent);
  color: var(--selected);
  outline: none;
}

.tab.active {
  border-color: color-mix(in srgb, var(--selected) 36%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 54%, transparent)
    );
  color: var(--selected);
  font-weight: 830;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent);
}

.tab-icon {
  line-height: 1;
}

.tab-count {
  min-height: 20px;
  padding: 0 0.38rem;
  font-size: 0.64rem;
}

.card,
.list-section,
.state-card,
.skeleton-card {
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--selected) 4%, transparent), transparent 34%),
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 78%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 42%, transparent)
    );
  box-shadow: 0 1px 0 color-mix(in srgb, white 6%, transparent) inset;
}

.card,
.list-section {
  padding: 0.86rem;
}

.section-head {
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin-bottom: 0.76rem;
}

.section-title {
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  font-weight: 820;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.section-desc {
  margin-top: 0.22rem;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.profile-grid {
  min-width: 0;
  display: grid;
  gap: 0.64rem;
}

.row {
  min-width: 0;
  display: grid;
  grid-template-columns: 116px minmax(0, 1fr);
  gap: 0.72rem;
  align-items: center;
}

.row.compact {
  grid-template-columns: 94px minmax(0, 1fr);
  gap: 0.56rem;
}

.label {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 740;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.value {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  overflow-wrap: anywhere;
}

.input,
.ta {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 62%, transparent);
  color: var(--text, var(--text-main));
  outline: none;
  font-family: inherit;
  font-size: 0.82rem;
  line-height: 1.5;
  padding: 0.58rem 0.64rem;
  overflow-wrap: break-word;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease;
}

.ta {
  resize: vertical;
  min-height: 92px;
  max-height: 240px;
}

.input::placeholder,
.ta::placeholder {
  color: var(--text-secondary);
  opacity: 0.72;
}

.input:focus,
.ta:focus {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background: color-mix(in srgb, var(--editor-bg) 78%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent);
}

.input:disabled,
.ta:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.avatar-row {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.72rem;
  flex-wrap: wrap;
}

.big-av,
.avatar-placeholder {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
}

.big-av {
  object-fit: cover;
}

.avatar-placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--selected-bg) 26%, transparent);
  color: var(--text-secondary);
  font-size: 1.25rem;
}

.avatar-actions {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.46rem;
  flex-wrap: wrap;
}

.file {
  display: none;
}

.actions {
  margin-top: 0.82rem;
  display: flex;
  justify-content: flex-end;
}

.hint {
  margin-top: 0.76rem;
  padding: 0.62rem 0.68rem;
  border: 1px solid color-mix(in srgb, var(--line) 70%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--editor-bg) 42%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.search-row {
  margin-bottom: 0.66rem;
}

.item-list {
  min-width: 0;
  display: grid;
  gap: 0.58rem;
}

.bm-item,
.user-row {
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 13px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--editor-bg) 70%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 38%, transparent)
    );
}

.bm-item {
  position: relative;
  overflow: hidden;
}

.bm-main {
  width: 100%;
  min-width: 0;
  display: block;
  padding: 0.72rem 2.4rem 0.72rem 0.74rem;
  border: none;
  border-radius: 13px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.bm-main:hover,
.bm-main:focus-visible {
  background: color-mix(in srgb, var(--selected-bg) 36%, transparent);
  outline: none;
}

.bm-x {
  position: absolute;
  top: 0.52rem;
  right: 0.52rem;
  width: 25px;
  height: 25px;
  border: 1px solid rgba(239, 68, 68, 0.28);
  border-radius: 9px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 820;
  line-height: 1;
  opacity: 0.78;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    transform 0.12s ease;
}

.bm-x:hover:not(:disabled),
.bm-x:focus-visible:not(:disabled) {
  opacity: 1;
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(239, 68, 68, 0.44);
  outline: none;
}

.bm-x:active:not(:disabled) {
  transform: translateY(1px);
}

.bm-x:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.li-title {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.38;
  overflow-wrap: break-word;
}

.li-sub {
  min-width: 0;
  margin-top: 0.3rem;
  color: var(--text-secondary);
  display: flex;
  gap: 0.4rem;
  align-items: center;
  flex-wrap: wrap;
  font-size: 0.74rem;
  line-height: 1.35;
}

.dot {
  opacity: 0.7;
}

.user-row {
  display: flex;
  align-items: center;
  gap: 0.62rem;
  padding: 0.62rem;
  overflow: hidden;
}

.av {
  flex: 0 0 auto;
  width: 1.34rem;
  height: 1.34rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 999px;
  object-fit: cover;
}

.av.fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--selected-bg) 26%, transparent);
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.u-text {
  min-width: 0;
  flex: 1 1 auto;
}

.u-name {
  min-width: 0;
  color: var(--text, var(--text-main));
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.u-id {
  margin-top: 0.14rem;
  color: var(--text-secondary);
  font-size: 0.7rem;
  line-height: 1.35;
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

.btn.danger:hover:not(:disabled),
.btn.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.46);
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  box-shadow:
    0 0 0 2px rgba(239, 68, 68, 0.1),
    0 8px 18px rgba(0, 0, 0, 0.08);
}

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.state-list {
  display: grid;
  gap: 0.72rem;
}

.skeleton-card {
  padding: 0.78rem;
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

.skeleton-line.title {
  width: 72%;
}

.skeleton-line.body {
  width: 88%;
}

@keyframes shimmer {
  0% {
    background-position: 120% 0;
  }

  100% {
    background-position: -120% 0;
  }
}

.state-card {
  padding: 0.9rem;
  color: var(--text-secondary);
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
  font-size: 0.84rem;
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
  margin-top: 0.72rem;
}

.inline-error {
  min-width: 0;
  margin-bottom: 0.72rem;
  padding: 0.58rem 0.66rem;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.58rem;
  box-sizing: border-box;
}

.inline-error span {
  min-width: 0;
  font-size: 0.74rem;
  font-weight: 720;
  line-height: 1.45;
  overflow-wrap: break-word;
}

.mode-compact .row {
  grid-template-columns: 1fr;
  gap: 0.3rem;
  align-items: stretch;
}

.mode-compact .section-head {
  flex-direction: column;
  gap: 0.5rem;
}

.mode-minimal .me-top {
  flex-direction: column;
  align-items: stretch;
}

.mode-minimal .me-top > .btn {
  width: 100%;
}

.mode-minimal .tabs {
  top: 8.4rem;
}

.mode-minimal .tab {
  min-width: 36px;
  justify-content: center;
  padding: 0 0.58rem;
}

.mode-minimal .row {
  grid-template-columns: 1fr;
  gap: 0.28rem;
  align-items: stretch;
}

.mode-minimal .avatar-actions {
  width: 100%;
}

.mode-minimal .avatar-actions .btn {
  flex: 1 1 0;
}

.mode-minimal .user-row {
  align-items: flex-start;
  flex-wrap: wrap;
}

.mode-minimal .user-row .btn {
  width: 100%;
}

@media (max-width: 720px) {
  .me-wrap {
    padding: 0.74rem 0.64rem;
  }

  .me-top {
    top: -0.74rem;
    margin: -0.74rem -0.64rem 0;
    padding: 0.68rem 0.64rem 0.62rem;
  }

  .tabs {
    top: 3.65rem;
    margin: 0 -0.64rem 0.68rem;
    padding: 0.56rem 0.64rem;
  }

  .row {
    grid-template-columns: 1fr;
    gap: 0.3rem;
    align-items: stretch;
  }

  .section-head {
    flex-direction: column;
    gap: 0.5rem;
  }

  .inline-error {
    align-items: stretch;
    flex-direction: column;
  }

  .inline-error .btn {
    width: 100%;
  }
}

@media (max-width: 520px) {
  .me-top {
    flex-direction: column;
    align-items: stretch;
  }

  .me-top > .btn {
    width: 100%;
  }

  .tabs {
    top: 8.1rem;
  }

  .avatar-actions {
    width: 100%;
  }

  .avatar-actions .btn {
    flex: 1 1 0;
  }

  .actions .btn {
    width: 100%;
  }
}

@media (max-width: 420px) {
  .me-wrap {
    padding: 0.64rem 0.52rem;
  }

  .me-top {
    top: -0.64rem;
    margin: -0.64rem -0.52rem 0;
    padding: 0.62rem 0.52rem 0.58rem;
  }

  .tabs {
    margin: 0 -0.52rem 0.62rem;
    padding: 0.5rem 0.52rem;
  }

  .card,
  .list-section,
  .state-card {
    border-radius: 14px;
    padding: 0.72rem;
  }

  .avatar-actions {
    flex-direction: column;
  }

  .avatar-actions .btn {
    width: 100%;
  }

  .user-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .user-row .btn {
    width: 100%;
  }

  .btn {
    min-height: 31px;
  }
}
</style>
