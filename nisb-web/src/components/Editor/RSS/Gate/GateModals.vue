<template>
  <div v-if="gate.state.previewOpen" class="mask" @click.self="gate.actions.closePreview">
    <div class="modal preview-modal" role="dialog" aria-modal="true">
      <div class="head">
        <div class="title-block">
          <div class="title">
            {{
              t('rss.center.gate.modals.preview.title', {
                title: gate.state.previewTitle || t('rss.center.gate.modals.fallback.untitled')
              })
            }}
          </div>
        </div>

        <button
          class="btn mini ghost"
          type="button"
          :aria-label="t('rss.center.gate.modals.actions.close')"
          @click="gate.actions.closePreview"
        >
          {{ t('rss.center.gate.modals.actions.close') }}
        </button>
      </div>

      <div class="body">
        <div v-if="gate.state.previewLoading" class="empty">
          {{ t('rss.center.gate.modals.preview.loading') }}
        </div>

        <div v-else-if="!gate.state.previewContent" class="empty">
          {{ t('rss.center.gate.modals.preview.empty') }}
        </div>

        <pre v-else class="pre">{{ gate.state.previewContent }}</pre>
      </div>

      <div class="foot">
        <button
          class="btn primary"
          type="button"
          :disabled="!gate.state.previewFeedId || !gate.state.previewArticleId"
          @click="gate.actions.openInReader(gate.state.previewFeedId, gate.state.previewArticleId)"
        >
          {{ t('rss.center.gate.modals.preview.openInReader') }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="gate.state.overrideOpen" class="mask" @click.self="gate.actions.closeOverride">
    <div class="modal override-modal" role="dialog" aria-modal="true">
      <div class="head">
        <div class="title-block">
          <div class="title">
            {{
              t('rss.center.gate.modals.override.title', {
                title: gate.state.overrideTitle || t('rss.center.gate.modals.fallback.untitled')
              })
            }}
          </div>
          <div class="subtitle">
            {{ t('rss.center.gate.modals.override.description') }}
          </div>
        </div>

        <button
          class="btn mini ghost"
          type="button"
          :aria-label="t('rss.center.gate.modals.actions.close')"
          @click="gate.actions.closeOverride"
        >
          {{ t('rss.center.gate.modals.actions.close') }}
        </button>
      </div>

      <div class="body">
        <div class="info-box">
          {{ t('rss.center.gate.modals.override.description') }}
        </div>

        <textarea
          class="ta"
          v-model="gate.state.overrideContent"
          :placeholder="t('rss.center.gate.modals.override.placeholder')"
        ></textarea>
      </div>

      <div class="foot">
        <button class="btn" type="button" @click="gate.actions.closeOverride" :disabled="gate.state.overrideWorking">
          {{ t('rss.center.gate.modals.actions.cancel') }}
        </button>

        <button
          class="btn primary"
          type="button"
          @click="gate.actions.saveOverride"
          :disabled="gate.state.overrideWorking || !gate.state.overrideFeedId || !gate.state.overrideArticleId || !gate.state.overrideContent.trim()"
        >
          {{
            gate.state.overrideWorking
              ? t('rss.center.gate.modals.override.saving')
              : t('rss.center.gate.modals.override.save')
          }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'

defineProps({
  gate: { type: Object, required: true }
})

const { t } = useI18n()
</script>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 18px;
  overflow-y: auto;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--selected) 12%, transparent), transparent 32%),
    radial-gradient(circle at 82% 8%, color-mix(in srgb, #16a34a 8%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.3);
}

.modal {
  width: min(940px, calc(100vw - 36px));
  max-height: calc(100vh - 36px);
  min-height: min(620px, calc(100vh - 36px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--line) 86%, transparent);
  border-radius: 18px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 94%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 88%, transparent)
    );
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.28),
    0 2px 18px rgba(0, 0, 0, 0.16);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.preview-modal {
  min-height: min(640px, calc(100vh - 36px));
}

.override-modal {
  min-height: min(720px, calc(100vh - 36px));
}

.head {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 15px 16px 13px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--sidebar-bg) 82%, transparent),
      color-mix(in srgb, var(--editor-bg) 56%, transparent)
    );
}

.title-block {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.96rem;
  font-weight: 820;
  line-height: 1.35;
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.body {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px;
  scrollbar-width: thin;
}

.body::-webkit-scrollbar {
  width: 8px;
}

.body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: color-mix(in srgb, var(--line) 70%, transparent);
}

.foot {
  flex: 0 0 auto;
  min-width: 0;
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 12px;
  border-top: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  background: color-mix(in srgb, var(--editor-bg) 84%, transparent);
}

.btn {
  min-height: 34px;
  box-sizing: border-box;
  padding: 0 0.72rem;
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
  font-size: 0.78rem;
  font-weight: 740;
  line-height: 1;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 0 color-mix(in srgb, white 8%, transparent) inset;
  transition:
    background 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease,
    opacity 0.16s ease,
    transform 0.12s ease;
}

.btn:hover:not(:disabled),
.btn:focus-visible:not(:disabled) {
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

.btn:active:not(:disabled) {
  transform: translateY(1px);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.btn.mini {
  min-height: 31px;
  padding: 0 0.62rem;
  font-size: 0.74rem;
}

.btn.ghost {
  background: color-mix(in srgb, var(--editor-bg) 30%, transparent);
}

.btn.primary {
  border-color: color-mix(in srgb, var(--selected) 42%, var(--line));
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--selected-bg) 72%, transparent),
      color-mix(in srgb, var(--editor-bg) 42%, transparent)
    );
  color: var(--selected);
}

.empty,
.info-box {
  padding: 0.9rem 0.85rem;
  border: 1px dashed color-mix(in srgb, var(--line) 84%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--editor-bg) 50%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 72%, transparent)
    );
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.empty {
  text-align: center;
}

.info-box {
  border-style: solid;
}

.pre {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  margin: 0;
  padding: 0.95rem;
  border: 1px solid color-mix(in srgb, var(--line) 78%, transparent);
  border-radius: 14px;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 72%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 58%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.84rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: break-word;
  overflow-x: hidden;
  box-shadow: inset 0 1px 0 color-mix(in srgb, white 5%, transparent);
}

.ta {
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 420px;
  box-sizing: border-box;
  padding: 0.9rem;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 14px;
  outline: none;
  resize: vertical;
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 76%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 60%, transparent)
    );
  color: var(--text-main, var(--text));
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 0.84rem;
  line-height: 1.6;
  overflow-wrap: break-word;
  box-shadow: inset 0 1px 0 color-mix(in srgb, white 5%, transparent);
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    box-shadow 0.16s ease;
}

.ta::placeholder {
  color: color-mix(in srgb, var(--text-secondary) 72%, transparent);
}

.ta:focus {
  border-color: color-mix(in srgb, var(--selected) 48%, var(--line));
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--editor-bg) 86%, transparent),
      color-mix(in srgb, var(--sidebar-bg) 58%, transparent)
    );
  box-shadow:
    0 0 0 3px color-mix(in srgb, var(--selected-bg) 54%, transparent),
    inset 0 1px 0 color-mix(in srgb, white 5%, transparent);
}

@media (max-width: 768px) {
  .mask {
    align-items: stretch;
    padding: 0;
  }

  .modal,
  .preview-modal,
  .override-modal {
    width: 100%;
    max-height: 100vh;
    min-height: 100vh;
    border-radius: 0;
  }

  .head,
  .foot {
    display: grid;
    grid-template-columns: 1fr;
  }

  .head .btn {
    justify-self: end;
  }

  .foot {
    justify-content: stretch;
  }

  .foot .btn {
    width: 100%;
  }

  .title {
    white-space: normal;
    overflow-wrap: break-word;
  }

  .ta {
    min-height: 52vh;
  }
}

@media (max-width: 420px) {
  .head,
  .body,
  .foot {
    padding: 10px;
  }

  .btn {
    width: 100%;
    white-space: normal;
  }
}
</style>
