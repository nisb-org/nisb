<template>
  <div ref="chartContainer" class="heatmap-calendar"></div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({})
  }
})

const chartContainer = ref(null)
let chartInstance = null

let ro = null
let rafId = 0
let lastSize = { w: 0, h: 0 }

function ensureChart() {
  if (!chartContainer.value) return
  if (chartInstance) return

  // 使用 canvas 渲染（默认就是 canvas），容器尺寸变化时要主动 resize 重绘，避免 CSS 拉伸导致发糊
  chartInstance = echarts.init(chartContainer.value)
  updateChart()
}

function buildChartData() {
  const chartData = []
  for (const [dateStr, value] of Object.entries(props.data || {})) {
    chartData.push([dateStr, value])
  }
  return chartData
}

function buildOption() {
  const today = new Date()
  const startDate = new Date(today)
  startDate.setDate(startDate.getDate() - 84)

  const values = Object.values(props.data || {})
  const maxVal = Math.max(...values, 10)

  return {
    animation: false, // 拖动侧栏时频繁 resize，关闭动画更稳
    tooltip: {
      appendToBody: true,
      appendTo: 'body',
      confine: false,
      extraCssText: 'z-index: 9999; pointer-events: none;',
      position: function (point) {
        if (point[1] < 120) return [point[0] + 10, point[1] + 20]
        return [point[0] + 10, point[1] - 40]
      },
      formatter: (params) => {
        // 不复刻任何外部版权文本，这里只拼接数据
        return `${params.data[0]}<br/>活动数: ${params.data[1]}`
      }
    },
    visualMap: {
      show: false,
      min: 0,
      max: maxVal,
      inRange: {
        color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
      }
    },
    calendar: {
      top: 18,
      left: 18,
      right: 18,
      cellSize: ['auto', 12],
      range: [startDate, today],
      itemStyle: {
        borderWidth: 2,
        borderColor: 'var(--sidebar-bg)'
      },
      splitLine: { show: false },
      dayLabel: {
        show: true,
        firstDay: 1,
        nameMap: ['日', '一', '二', '三', '四', '五', '六'],
        fontSize: 10,
        color: 'var(--text-secondary)'
      },
      monthLabel: { show: false },
      yearLabel: { show: false }
    },
    series: [
      {
        type: 'heatmap',
        coordinateSystem: 'calendar',
        data: buildChartData()
      }
    ]
  }
}

function updateChart() {
  if (!chartInstance) return
  const option = buildOption()
  chartInstance.setOption(option, { notMerge: true })
}

function resizeChart() {
  if (!chartInstance || !chartContainer.value) return

  // 用 requestAnimationFrame 做轻量节流，拖动侧栏时更顺滑
  if (rafId) cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(() => {
    rafId = 0
    chartInstance.resize()
  })
}

function setupResizeObserver() {
  if (!chartContainer.value) return
  if (typeof ResizeObserver === 'undefined') return

  ro = new ResizeObserver((entries) => {
    const entry = entries?.[0]
    const w = Math.round(entry?.contentRect?.width || 0)
    const h = Math.round(entry?.contentRect?.height || 0)
    if (!w || !h) return

    // 尺寸变化才触发，避免无意义调用
    if (w !== lastSize.w || h !== lastSize.h) {
      lastSize = { w, h }
      resizeChart()
    }
  })

  ro.observe(chartContainer.value)
}

watch(
  () => props.data,
  () => {
    ensureChart()
    updateChart()
    // 数据变化后也做一次 resize，确保文本/布局稳定
    resizeChart()
  },
  { deep: true }
)

onMounted(() => {
  ensureChart()
  setupResizeObserver()
  // 仍保留 window.resize 作为兜底（但主力靠 ResizeObserver）
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)

  if (ro) {
    ro.disconnect()
    ro = null
  }
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.heatmap-calendar {
  width: 100%;
  height: 120px;
}
</style>

