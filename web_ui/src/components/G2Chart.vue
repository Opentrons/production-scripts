<template>
  <div ref="chartContainer" class="chart-container"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import { Pie, Bar, Line } from '@antv/g2plot';

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['pie', 'bar', 'line'].includes(value)
  },
  data: {
    type: Array,
    required: true
  },
  options: {
    type: Object,
    default: () => ({})
  },
  theme: {
    type: String,
    default: 'light'
  }
});

const chartContainer = ref(null);
let chartInstance = null;

const renderChart = () => {
  if (!chartContainer.value) return;
  
  if (chartInstance) {
    chartInstance.destroy();
  }

  const config = {
    data: props.data,
    theme: props.theme,
    ...props.options
  };

  switch (props.type) {
    case 'pie':
      config.angleField = config.angleField || 'value';
      config.colorField = config.colorField || 'type';
      config.radius = config.radius || 0.8;
      chartInstance = new Pie(chartContainer.value, config);
      break;
    case 'bar':
      config.xField = config.xField || 'type';
      config.yField = config.yField || 'value';
      chartInstance = new Bar(chartContainer.value, config);
      break;
    case 'line':
      config.xField = config.xField || 'date';
      config.yField = config.yField || 'value';
      chartInstance = new Line(chartContainer.value, config);
      break;
  }

  chartInstance.render();
};

onMounted(renderChart);
watch(() => [props.data, props.type, props.options], renderChart, { deep: true });
onBeforeUnmount(() => {
  chartInstance?.destroy();
});
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 100%;
  min-height: 300px;
}
</style>