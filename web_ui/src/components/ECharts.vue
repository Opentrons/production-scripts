<template>
  <div ref="chartEl" :style="{ width: width, height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  options: Object,
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '300px'
  }
})

const chartEl = ref(null)
let chartInstance = null

const initChart = () => {
  if (!chartEl.value) return
  chartInstance = echarts.init(chartEl.value)
  chartInstance.setOption(props.options)
}

const updateChart = () => {
  if (chartInstance) {
    chartInstance.setOption(props.options)
  }
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chartInstance?.resize())
})

watch(() => props.options, updateChart, { deep: true })

onBeforeUnmount(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', () => chartInstance?.resize())
})
</script>