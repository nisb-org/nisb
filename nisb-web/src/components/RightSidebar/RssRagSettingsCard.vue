<template>
  <div class="card">
    <div class="row">
      <div class="title">{{ t('rightSidebar.rss.ragSettings.title') }}</div>
      <button class="btn" type="button" @click="reset" :title="t('rightSidebar.rss.ragSettings.actions.resetDefaults')">
        {{ t('rightSidebar.rss.ragSettings.actions.resetDefaults') }}
      </button>
    </div>

    <div class="hint">
      {{ t('rightSidebar.rss.ragSettings.hint') }}
    </div>

    <div class="form">
      <label class="field">
        <span class="lab">{{ t('rightSidebar.rss.ragSettings.fields.enabled') }}</span>
        <input type="checkbox" :checked="rss.enabled" @change="onEnabled($event)" />
      </label>

      <label class="field">
        <span class="lab">{{ t('rightSidebar.rss.ragSettings.fields.days') }}</span>
        <select class="ctl" :value="rss.days" @change="onDays($event)">
          <option value="0">0</option>
          <option value="1">1</option>
          <option value="3">3</option>
          <option value="7">7</option>
          <option value="14">14</option>
          <option value="30">30</option>
          <option value="90">90</option>
        </select>
      </label>

      <label class="field">
        <span class="lab">{{ t('rightSidebar.rss.ragSettings.fields.limit') }}</span>
        <select class="ctl" :value="rss.limit" @change="onLimit($event)">
          <option value="3">3</option>
          <option value="5">5</option>
          <option value="8">8</option>
          <option value="12">12</option>
          <option value="20">20</option>
        </select>
      </label>

      <label class="field">
        <span class="lab">{{ t('rightSidebar.rss.ragSettings.fields.minScore') }}</span>
        <input
          class="ctl num"
          type="number"
          step="0.01"
          min="0"
          max="1"
          :value="rss.minScore"
          @input="onMinScore($event)"
        />
      </label>

      <label class="field">
        <span class="lab" :title="t('rightSidebar.rss.ragSettings.fields.strictLexicalTitle')">
          {{ t('rightSidebar.rss.ragSettings.fields.strictLexical') }}
        </span>
        <input type="checkbox" :checked="rss.strictLexical" @change="onStrict($event)" />
      </label>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatConfigStore } from '../../stores/chatConfig'

const chatCfg = useChatConfigStore()
const { t } = useI18n()

const rss = computed(() => chatCfg.rag.rss)

function onEnabled(e) {
  chatCfg.setRssEnabled(!!e?.target?.checked)
}
function onDays(e) {
  chatCfg.setRssDays(e?.target?.value)
}
function onLimit(e) {
  chatCfg.setRssLimit(e?.target?.value)
}
function onMinScore(e) {
  chatCfg.setRssMinScore(e?.target?.value)
}
function onStrict(e) {
  chatCfg.setRssStrictLexical(!!e?.target?.checked)
}
function reset() {
  chatCfg.resetRssDefaults()
}
</script>

<style scoped>
.card {
  padding: 12px 12px;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.03);
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  opacity: 0.9;
}

.btn {
  border: none;
  background: rgba(0, 0, 0, 0.06);
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:hover {
  background: rgba(0, 0, 0, 0.1);
}

.hint {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.75;
  line-height: 1.4;
}

.form {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

/* Two-column layout to avoid controls crowding the previous item on narrow screens. */
.field {
  display: grid;
  grid-template-columns: 1fr 140px;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.lab {
  opacity: 0.85;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ctl {
  border: none;
  background: rgba(0, 0, 0, 0.06);
  padding: 6px 8px;
  border-radius: 10px;
  outline: none;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.num {
  font-variant-numeric: tabular-nums;
}
</style>

