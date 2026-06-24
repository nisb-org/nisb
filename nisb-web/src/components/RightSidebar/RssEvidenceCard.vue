<template>
  <div v-if="items.length" class="card">
    <div class="head">
      <div class="title">RSS 证据</div>
      <div class="meta">{{ items.length }} 条</div>
    </div>

    <div class="list">
      <a v-for="(it, i) in items" :key="it.object_ref || it.url || i" class="row" :href="it.url" target="_blank" rel="noreferrer">
        <div class="t">{{ it.title || it.url }}</div>
        <div class="q">{{ it.quote || it.excerpt || '' }}</div>
        <div class="sub">
          <span class="muted">{{ (it.published_at || '').slice(0, 19) }}</span>
          <span class="muted" v-if="typeof it.relevance === 'number'">· rel {{ it.relevance.toFixed(2) }}</span>
          <span class="muted" v-if="it.feed_id">· {{ it.feed_id }}</span>
        </div>
      </a>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] }
})
</script>

<style scoped>
.card {
  background: var(--sidebar-bg);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.65rem 0.7rem;
  display: grid;
  gap: 0.5rem;
}
.head { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; }
.title { font-size: 0.9rem; color: var(--text-main); }
.meta { font-size: 0.75rem; opacity: 0.7; }
.list { display: grid; gap: 0.45rem; }
.row {
  display: block;
  text-decoration: none;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.55rem 0.6rem;
  background: transparent;
  color: inherit;
}
.row:hover { background: var(--selected-bg); border-color: var(--selected); }
.t { font-size: 0.85rem; color: var(--text-main); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.q { margin-top: 0.25rem; font-size: 0.78rem; opacity: 0.85; line-height: 1.35; max-height: 3.9em; overflow: hidden; }
.sub { margin-top: 0.25rem; font-size: 0.72rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }
.muted { opacity: 0.7; }
</style>

