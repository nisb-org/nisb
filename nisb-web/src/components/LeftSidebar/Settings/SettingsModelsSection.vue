<template>
  <div class="settings-section settings-models-section">
    <div class="settings-card is-accent">
      <div class="model-head-row">
        <div class="settings-main">
          <span class="model-row-label">{{ t('settings.models.catalog.label') }}</span>
          <span class="muted settings-hint">{{ t('settings.models.catalog.hint') }}</span>
        </div>

        <button
          class="mini-btn model-row-action"
          type="button"
          @click="$emit('load-model-catalog')"
          :disabled="busy || modelCatalogLoading"
        >
          {{
            modelCatalogLoading
              ? t('settings.models.catalog.loading')
              : t('settings.models.catalog.refresh')
          }}
        </button>
      </div>

      <div v-if="modelCatalogError" class="model-status warn">
        {{ t('settings.models.catalog.errorPrefix') }}{{ modelCatalogError }}
      </div>
    </div>

    <div class="settings-card">
      <div class="model-card-head">
        <div class="model-card-title">
          {{ t('settings.models.conversation.label') }}
        </div>
      </div>

      <div class="model-row">
        <span class="model-row-label">{{ t('settings.models.conversation.label') }}</span>
        <select class="settings-select model-row-control" v-model="conversation_model_proxy">
          <option v-if="show_current_as_custom(conversation_model_proxy)" :value="conversation_model_proxy">
            {{ conversation_model_proxy }} ({{ t('settings.models.common.currentCustom') }})
          </option>
          <template v-if="modelGroups.length">
            <optgroup v-for="group in modelGroups" :key="group.key" :label="build_group_label(group)">
              <option v-for="m in group.models" :key="`${group.key}_${m.value}`" :value="m.value">
                {{ m.label }}{{ m.badge ? ` ${m.badge}` : '' }}
              </option>
            </optgroup>
          </template>
          <template v-else>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4.1-mini">gpt-4.1-mini</option>
          </template>
        </select>
      </div>

      <div class="model-row">
        <span class="model-row-label">{{ t('settings.models.common.customModelName') }}</span>
        <input
          class="settings-input model-row-control"
          type="text"
          v-model="conversation_model_proxy"
          :placeholder="t('settings.models.conversation.placeholder')"
        />
      </div>

      <div class="muted settings-hint">{{ t('settings.models.conversation.hint') }}</div>
    </div>

    <div class="settings-card">
      <div class="model-card-head">
        <div class="model-card-title">
          {{ t('settings.models.translate.label') }}
        </div>
      </div>

      <div class="model-row">
        <span class="model-row-label">{{ t('settings.models.translate.label') }}</span>
        <select class="settings-select model-row-control" v-model="query_translate_model_proxy">
          <option v-if="show_current_as_custom(query_translate_model_proxy)" :value="query_translate_model_proxy">
            {{ query_translate_model_proxy }} ({{ t('settings.models.common.currentCustom') }})
          </option>
          <template v-if="modelGroups.length">
            <optgroup v-for="group in modelGroups" :key="group.key" :label="build_group_label(group)">
              <option v-for="m in group.models" :key="`translate_${group.key}_${m.value}`" :value="m.value">
                {{ m.label }}{{ m.badge ? ` ${m.badge}` : '' }}
              </option>
            </optgroup>
          </template>
          <template v-else>
            <option value="gpt-4o-mini">GPT-4o Mini</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4.1-mini">gpt-4.1-mini</option>
          </template>
        </select>
      </div>

      <div class="model-row">
        <span class="model-row-label">{{ t('settings.models.common.customModelName') }}</span>
        <input
          class="settings-input model-row-control"
          type="text"
          v-model="query_translate_model_proxy"
          :placeholder="t('settings.models.translate.placeholder')"
        />
      </div>

      <div class="muted settings-hint">{{ t('settings.models.translate.hint') }}</div>
    </div>

    <div class="settings-row actions">
      <button class="mini-btn primary settings-footer-btn" type="button" @click="$emit('save')">
        {{ t('settings.common.save') }}
      </button>
      <button class="mini-btn settings-footer-btn" type="button" @click="$emit('reset')">
        {{ t('settings.common.reset') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  busy: { type: Boolean, default: false },
  modelCatalogLoading: { type: Boolean, default: false },
  modelCatalogError: { type: String, default: '' },
  modelGroups: { type: Array, default: () => [] },
  conversationModel: { type: String, default: 'gpt-4o-mini' },
  queryTranslateModel: { type: String, default: 'gpt-4o-mini' }
})

const emit = defineEmits([
  'update:conversationModel',
  'update:queryTranslateModel',
  'load-model-catalog',
  'save',
  'reset'
])

const { t } = useI18n()

const conversation_model_proxy = computed({
  get: () => props.conversationModel || '',
  set: (val) => emit('update:conversationModel', String(val || ''))
})

const query_translate_model_proxy = computed({
  get: () => props.queryTranslateModel || '',
  set: (val) => emit('update:queryTranslateModel', String(val || ''))
})

function safe_string(v) {
  return v === null || v === undefined ? '' : String(v)
}

function build_group_label(group) {
  const icon = safe_string(group?.icon).trim()
  const name = safe_string(group?.name || group?.key).trim()
  return icon ? `${icon} ${name}` : name
}

function has_model_option(model_value) {
  const mv = safe_string(model_value).trim()
  if (!mv) return false

  for (const group of props.modelGroups || []) {
    for (const m of group.models || []) {
      if (safe_string(m.value).trim() === mv) return true
    }
  }

  return false
}

function show_current_as_custom(model_value) {
  const mv = safe_string(model_value).trim()
  if (!mv) return false
  return !has_model_option(mv)
}
</script>

<style scoped>
.settings-models-section {
  min-width: 0;
}

.settings-main {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.model-head-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 10px 12px;
  min-width: 0;
}

.model-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.model-card-title {
  min-width: 0;
  color: var(--text-main, var(--text));
  font-size: 0.84rem;
  font-weight: 780;
  line-height: 1.35;
  overflow-wrap: break-word;
}

.model-row {
  display: grid;
  grid-template-columns: minmax(120px, 34%) minmax(0, 1fr);
  align-items: center;
  gap: 8px 12px;
  min-width: 0;
}

.model-row-label {
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  font-weight: 720;
  line-height: 1.35;
  white-space: normal;
  overflow-wrap: break-word;
}

.model-row-action,
.model-row-control {
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.model-row-action {
  width: auto;
  justify-self: start;
  white-space: normal;
}

.model-status {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 11px;
  font-size: 0.8rem;
  line-height: 1.5;
  overflow-wrap: break-word;
}

.model-status.warn {
  border: 1px solid rgba(217, 119, 6, 0.3);
  background: rgba(217, 119, 6, 0.08);
  color: #d97706;
}

.settings-footer-btn {
  flex: 0 1 150px;
  min-width: 120px;
}

@media (max-width: 720px) {
  .model-head-row,
  .model-row {
    grid-template-columns: 1fr;
  }

  .model-row-action,
  .model-row-control {
    width: 100%;
    justify-self: stretch;
  }

  .settings-footer-btn {
    flex: 1 1 100%;
  }
}
</style>
