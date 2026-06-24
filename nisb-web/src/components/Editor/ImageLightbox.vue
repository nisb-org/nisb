<!-- /opt/mcp-gateway/nisb-web/src/components/Editor/ImageLightbox.vue -->
<template>
  <Teleport to="body">
    <div class="image-lightbox" role="dialog" aria-modal="true" @click="handleBackdropClick">
      <button class="lightbox-close" type="button" @click.stop="close">✕</button>

      <img class="lightbox-image" :src="src" :alt="alt || ''" @click.stop />

      <div v-if="alt" class="lightbox-info" @click.stop>{{ alt }}</div>
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: '' },
})

const emit = defineEmits(['close'])

function close() {
  emit('close')
}

function onKeydown(e) {
  if (e.key === 'Escape') close()
}

function handleBackdropClick() {
  close()
}

function lockBodyScroll() {
  // 防止 lightbox 打开时背景滚动穿透
  document.documentElement.style.overflow = 'hidden'
  document.body.style.overflow = 'hidden'
}

function unlockBodyScroll() {
  document.documentElement.style.overflow = ''
  document.body.style.overflow = ''
}

onMounted(() => {
  lockBodyScroll()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  unlockBodyScroll()
})
</script>

<style scoped>
.image-lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
  animation: fadeIn var(--transition-normal);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.lightbox-image {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  cursor: default;
}

.lightbox-close {
  position: absolute;
  top: 2rem;
  right: 2rem;
  width: 48px;
  height: 48px;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  color: white;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-normal);
}

.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
}

.lightbox-info {
  position: absolute;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  max-width: min(90%, 900px);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.85rem;
  backdrop-filter: blur(10px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

