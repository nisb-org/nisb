<template>
  <div class="wrap" :class="{ embedded: placement === 'left' }">
    <div class="head">
      <div class="title-block">
        <div class="h">{{ t('rss.center.gate.results.title', { count: gate.displayResults.length }) }}</div>
        <div class="head-meta">
          <span class="meta-chip mono">{{ gate.displayResults.length }}</span>
          <span v-if="gate.state.searchWorking" class="status-chip active">
            {{ t('rss.center.gate.results.status.searching') }}
          </span>
        </div>
      </div>

      <div class="right">
        <div class="sort" role="group">
          <button
            class="sbtn"
            type="button"
            :class="{ active: gate.state.sortMode === 'score_desc' }"
            @click="gate.actions.setSortMode('score_desc')"
            :title="t('rss.center.gate.results.sort.scoreTitle')"
          >
            {{ t('rss.center.gate.results.sort.score') }}
          </button>
          <button
            class="sbtn"
            type="button"
            :class="{ active: gate.state.sortMode === 'time_desc' }"
            @click="gate.actions.setSortMode('time_desc')"
            :title="t('rss.center.gate.results.sort.timeDescTitle')"
          >
            {{ t('rss.center.gate.results.sort.timeDesc') }}
          </button>
          <button
            class="sbtn"
            type="button"
            :class="{ active: gate.state.sortMode === 'time_asc' }"
            @click="gate.actions.setSortMode('time_asc')"
            :title="t('rss.center.gate.results.sort.timeAscTitle')"
          >
            {{ t('rss.center.gate.results.sort.timeAsc') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="!gate.displayResults.length" class="empty">
      {{ t('rss.center.gate.results.empty') }}
    </div>

    <div v-else class="list">
      <div
        v-for="it in gate.displayResults"
        :key="it.__key"
        class="card"
        :class="{ active: gate.state.selectedKeys.includes(it.__key) }"
      >
        <label class="pick" @click.stop>
          <input
            type="checkbox"
            :value="it.__key"
            v-model="gate.state.selectedKeys"
            :aria-label="it.title || it.url || t('rss.center.gate.results.fallback.untitled')"
          />
        </label>

        <div class="main" @click="gate.actions.previewArticle(it.feed_id, it.article_id, it.title)">
          <div class="title" :title="it.title || it.url || t('rss.center.gate.results.fallback.untitled')">
            {{ it.title || it.url || t('rss.center.gate.results.fallback.untitled') }}
          </div>

          <div class="badges">
            <span v-if="gate.actions.isImported(it.url)" class="badge ok">
              {{ t('rss.center.gate.results.badges.imported') }}
            </span>
            <span v-if="gate.actions.isDeleted(it.url)" class="badge danger">
              {{ t('rss.center.gate.results.badges.deleted') }}
            </span>
            <span v-if="gate.actions.isBlocked(it.url)" class="badge blocked">
              {{ t('rss.center.gate.results.badges.blocked') }}
            </span>
          </div>

          <div class="meta-row">
            <span v-if="it.published_at">
              {{ t('rss.center.gate.results.meta.publishedAt', { value: String(it.published_at).slice(0, 19) }) }}
            </span>
            <span v-if="typeof it.score === 'number'">
              {{ t('rss.center.gate.results.meta.score', { value: Number(it.score).toFixed(3) }) }}
            </span>
            <span v-if="it.feed_id" class="mono">
              {{ t('rss.center.gate.results.meta.feed', { value: it.feed_id }) }}
            </span>
            <span v-if="it.method_hit && it.method_hit.length">
              {{ t('rss.center.gate.results.meta.method', { value: it.method_hit.join('+') }) }}
            </span>
          </div>

          <div v-if="it.excerpt" class="excerpt">{{ it.excerpt }}</div>
        </div>

        <div class="actions" @click.stop>
          <a v-if="it.url" class="alink" :href="it.url" target="_blank" rel="noreferrer">
            {{ t('rss.center.gate.results.actions.openLink') }}
          </a>

          <button
            class="btn mini"
            type="button"
            :disabled="!it.feed_id || !it.article_id"
            @click="gate.actions.previewArticle(it.feed_id, it.article_id, it.title)"
          >
            {{ t('rss.center.gate.results.actions.quickPreview') }}
          </button>

          <button
            class="btn mini"
            type="button"
            :disabled="!it.feed_id || !it.article_id"
            @click="gate.actions.openOverrideModal(it)"
          >
            {{ t('rss.center.gate.results.actions.pasteFullText') }}
          </button>

          <button class="btn mini danger" type="button" @click="gate.actions.toggleBlock(it.url)">
            {{
              gate.actions.isBlocked(it.url)
                ? t('rss.center.gate.results.actions.unblock')
                : t('rss.center.gate.results.actions.block')
            }}
          </button>

          <button class="btn mini danger" type="button" @click="gate.actions.deleteArticleLocal(it)">
            {{ t('rss.center.gate.results.actions.delete') }}
          </button>

          <button
            class="btn mini danger"
            type="button"
            :disabled="!it.feed_id || !it.article_id"
            @click="gate.actions.deleteArticleData(it)"
          >
            {{ t('rss.center.gate.results.actions.deleteData') }}
          </button>

          <button class="btn mini danger" type="button" @click="gate.actions.addSpamDomain(it.url)">
            {{ t('rss.center.gate.results.actions.markSpamDomain') }}
          </button>

          <button
            class="btn mini danger"
            type="button"
            :disabled="!it.feed_id || !it.article_id"
            @click="gate.actions.addSpamArticle(it)"
          >
            {{ t('rss.center.gate.results.actions.markSpamArticle') }}
          </button>
        </div>
      </div>
    </div>

    <div class="foot">
      {{ t('rss.center.gate.results.note') }}
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  gate: { type: Object, required: true },
  placement: { type: String, default: 'right' }
})

const { t } = useI18n()
</script>

<style scoped>
.wrap {
  min-width: 0;
  padding: 0;
  color: var(--text-main, var(--text));
  overflow-x: hidden;
}

.wrap.embedded {
  padding: 0;
}

.head {
  position: sticky;
  top: 0;
  z-index: 2;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.72rem;
  margin-bottom: 0.72rem;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 80%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.title-block {
  min-width: 0;
  display: grid;
  gap: 0.32rem;
}

.h {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.86rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.005em;
  overflow-wrap: break-word;
}

.head-meta {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.right {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.55rem;
}

.sort {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.36rem;
  flex-wrap: wrap;
}

.sbtn,
.btn,
.alink {
  min-height: 29px;
  box-sizing: border-box;
  padding: 0 0.62rem;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 10px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 52%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 86%, transparent)
    );
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.74rem;
  font-weight: 750;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease;
}

.sbtn:hover:not(:disabled),
.sbtn:focus-visible:not(:disabled),
.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled),
.alink:hover,
.alink:focus-visible {
  border-color: color-mix(in srgb, var(--selected) 38%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 58%, transparent),
      color-mix(in srgb, var(--editor-bg) 46%, transparent)
    );
  color: var(--selected);
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 10%, transparent),
    0 8px 18px rgba(0, 0, 0, 0.08);
  outline: none;
}

.sbtn:active:not(:disabled),
.btn:active:not(:disabled),
.alink:active {
  transform: translateY(1px);
}

.sbtn.active {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  color: var(--selected);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.btn.mini {
  min-height: 27px;
  padding: 0 0.54rem;
  border-radius: 9px;
  font-size: 0.72rem;
}

.btn.danger {
  border-color: rgba(239, 68, 68, 0.34);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.btn.danger:hover:not(:disabled),
.btn.danger:focus-visible:not(:disabled) {
  border-color: rgba(239, 68, 68, 0.58);
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}

.alink {
  color: var(--selected);
}

.meta-chip,
.status-chip,
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  box-sizing: border-box;
  padding: 0 0.5rem;
  border: 1px solid color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--editor-bg) 66%, transparent);
  color: var(--text-secondary);
  font-size: 0.68rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  max-width: 100%;
}

.meta-chip,
.status-chip.active {
  border-color: color-mix(in srgb, var(--selected) 24%, var(--line));
  background: color-mix(in srgb, var(--selected-bg) 42%, var(--editor-bg));
  color: var(--selected);
}

.empty {
  padding: 1rem 0.9rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 48%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.84rem;
  line-height: 1.5;
  text-align: center;
  overflow-wrap: break-word;
}

.list {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 0.72rem;
}

.card {
  position: relative;
  width: min(900px, 100%);
  min-width: 0;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.62rem;
  margin: 0 auto;
  padding: 0.78rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 58%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 80%, transparent)
    );
  color: var(--text-main, var(--text));
  box-shadow:
    0 1px 0 color-mix(in srgb, white 6%, transparent) inset,
    0 8px 18px rgba(0, 0, 0, 0.04);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.wrap.embedded .card {
  width: 100%;
  margin: 0;
}

.card:hover {
  border-color: color-mix(in srgb, var(--selected) 28%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 42%, transparent),
      color-mix(in srgb, var(--editor-bg) 48%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 8%, transparent),
    0 12px 26px rgba(0, 0, 0, 0.07);
}

.card.active {
  border-color: color-mix(in srgb, var(--selected) 44%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 70%, transparent),
      color-mix(in srgb, var(--editor-bg) 44%, transparent)
    );
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--selected) 12%, transparent),
    0 14px 30px rgba(0, 0, 0, 0.09);
}

.card::before {
  content: "";
  position: absolute;
  left: 0.42rem;
  top: 0.82rem;
  bottom: 0.82rem;
  width: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 80%, transparent);
  opacity: 0.9;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.card:hover::before,
.card.active::before {
  background: var(--selected);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--selected) 10%, transparent);
}

.pick {
  position: relative;
  z-index: 1;
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  min-height: 28px;
  margin-left: 0.2rem;
  cursor: pointer;
}

.pick input {
  accent-color: var(--selected);
}

.main {
  min-width: 0;
  display: grid;
  gap: 0.42rem;
  cursor: pointer;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.92rem;
  font-weight: 790;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow-wrap: break-word;
}

.card:hover .title,
.card.active .title {
  color: var(--selected);
}

.badges {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.34rem;
}

.badge.ok {
  border-color: rgba(22, 163, 74, 0.36);
  background: rgba(22, 163, 74, 0.08);
  color: #16a34a;
}

.badge.danger {
  border-color: rgba(239, 68, 68, 0.36);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.badge.blocked {
  border-color: color-mix(in srgb, var(--line) 86%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 56%, transparent);
  color: var(--text-secondary);
  opacity: 0.82;
}

.meta-row {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.38rem 0.58rem;
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.45;
}

.meta-row span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.excerpt {
  min-width: 0;
  color: color-mix(in srgb, var(--text-main, var(--text)) 88%, var(--text-secondary));
  font-size: 0.82rem;
  line-height: 1.52;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.actions {
  grid-column: 2;
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.42rem;
  padding-top: 0.62rem;
  margin-top: 0.14rem;
  border-top: 1px solid color-mix(in srgb, var(--line) 68%, transparent);
}

.foot {
  margin-top: 0.72rem;
  padding: 0.72rem;
  border: 1px solid color-mix(in srgb, var(--line) 76%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--editor-bg) 48%, transparent);
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.mono {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .head {
    align-items: stretch;
    flex-direction: column;
  }

  .right,
  .sort {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 620px) {
  .head {
    padding: 0.62rem;
    border-radius: 14px;
  }

  .sort {
    display: grid;
    grid-template-columns: 1fr;
  }

  .sbtn,
  .btn,
  .alink {
    width: 100%;
    white-space: normal;
  }

  .card {
    grid-template-columns: 1fr;
    gap: 0.48rem;
    padding: 0.68rem;
    border-radius: 14px;
  }

  .card::before {
    left: 0.68rem;
    right: 0.68rem;
    top: 0;
    bottom: auto;
    width: auto;
    height: 3px;
  }

  .pick {
    justify-content: flex-start;
    margin-left: 0;
  }

  .actions {
    grid-column: 1;
    display: grid;
    grid-template-columns: 1fr;
  }

  .foot {
    padding: 0.62rem;
  }
}
</style>
