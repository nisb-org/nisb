import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 响应式断点检测
 * @returns {Object} { isMobile, isTablet, isDesktop }
 */
export function useResponsive() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(true)
  
  const breakpoints = {
    mobile: 768,   // < 768px 为移动端
    tablet: 1024   // 768-1024px 为平板
  }
  
  const updateResponsive = () => {
    const width = window.innerWidth
    isMobile.value = width < breakpoints.mobile
    isTablet.value = width >= breakpoints.mobile && width < breakpoints.tablet
    isDesktop.value = width >= breakpoints.tablet
  }
  
  onMounted(() => {
    updateResponsive()
    window.addEventListener('resize', updateResponsive)
  })
  
  onUnmounted(() => {
    window.removeEventListener('resize', updateResponsive)
  })
  
  return { isMobile, isTablet, isDesktop }
}

