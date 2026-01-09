<template>
  <div class="chart-container">
    <div ref="chartRef" :style="{ width: width, height: height }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import Plotly from 'plotly.js/dist/plotly'

const props = defineProps({
  data: {
    type: Object,
    required: true
  },
  layout: {
    type: Object,
    default: () => ({})
  },
  config: {
    type: Object,
    default: () => ({
      responsive: true,
      displayModeBar: true
    })
  },
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '400px'
  }
})

const emit = defineEmits(['plotly-click', 'plotly-hover', 'plotly-unhover'])

const chartRef = ref(null)

onMounted(() => {
  renderChart()
})

watch(() => props.data, () => {
  renderChart()
}, { deep: true })

watch(() => props.layout, () => {
  Plotly.update(chartRef.value, {}, props.layout)
}, { deep: true })

function renderChart() {
  if (!chartRef.value || !props.data) return
  
  const defaultLayout = {
    margin: { t: 40, r: 40, b: 40, l: 60 },
    plot_bgcolor: '#f5f7fa',
    paper_bgcolor: '#ffffff',
    ...props.layout
  }
  
  Plotly.newPlot(chartRef.value, props.data, defaultLayout, props.config)
  
  chartRef.value.on('plotly_click', (data) => {
    emit('plotly-click', data)
  })
  
  chartRef.value.on('plotly_hover', (data) => {
    emit('plotly-hover', data)
  })
  
  chartRef.value.on('plotly_unhover', (data) => {
    emit('plotly-unhover', data)
  })
}

onUnmounted(() => {
  if (chartRef.value) {
    Plotly.purge(chartRef.value)
  }
})

defineExpose({
  chartRef,
  downloadChart: (format = 'png', filename = 'chart') => {
    if (chartRef.value) {
      Plotly.downloadImage(chartRef.value, {
        format: format,
        filename: filename,
        width: 1200,
        height: 600
      })
    }
  }
})
</script>

<style scoped>
.chart-container {
  width: 100%;
}
</style>
