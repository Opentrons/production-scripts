<template>
  <div class="data-analysis-container">
    <!-- 头部导航 -->
    <el-menu
      mode="horizontal"
      background-color="#545c64"
      text-color="#fff"
      active-text-color="#ffd04b"
      @select="handleMenuSelect"
    >
      <el-sub-menu index="products">
        <template #title>产品选择</template>
        <el-menu-item 
          v-for="product in products" 
          :key="product.id" 
          :index="`product_${product.id}`"
        >
          {{ product.name }}
        </el-menu-item>
      </el-sub-menu>
      
      <el-sub-menu index="quarters">
        <template #title>季度选择</template>
        <el-menu-item 
          v-for="quarter in quarters" 
          :key="quarter" 
          :index="`quarter_${quarter}`"
        >
          Q{{ quarter }}
        </el-menu-item>
      </el-sub-menu>
    </el-menu>

    <!-- 列选择器 -->
    <el-card class="column-selector">
      <el-checkbox-group v-model="selectedColumns">
        <el-checkbox 
          v-for="column in availableColumns" 
          :key="column.prop" 
          :label="column.prop"
        >
          {{ column.label }}
        </el-checkbox>
      </el-checkbox-group>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="data-card">
      <el-table
        :data="tableData"
        style="width: 100%"
        border
      >
        <el-table-column prop="date" label="日期" width="180" fixed />
        <el-table-column 
          v-for="col in visibleColumns" 
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
        />
      </el-table>
    </el-card>

    <!-- 折线图 -->
    <el-card class="chart-card" v-if="selectedColumns.length > 0">
      <div ref="chartEl" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import * as echarts from 'echarts'

// 产品数据
const products = ref([
  { id: 1, name: '产品A' },
  { id: 2, name: '产品B' },
  { id: 3, name: '产品C' }
])

// 季度数据
const quarters = ref([1, 2, 3, 4])

// 当前选择
const currentProduct = ref(1)
const currentQuarter = ref(1)

// 可选的列配置（包含日期列）
const availableColumns = ref([
  { prop: 'date', label: '日期', fixed: true }, // 固定显示日期列
  { prop: 'sales', label: '销售额(万)' },
  { prop: 'users', label: '用户数' },
  { prop: 'conversion', label: '转化率(%)' },
  { prop: 'cost', label: '成本(万)' },
  { prop: 'profit', label: '利润(万)' }
])

// 选中的列（默认选中销售额和用户数）
const selectedColumns = ref(['sales', 'users'])

// 计算实际显示的列（排除日期列的选择）
const visibleColumns = computed(() => {
  return availableColumns.value.filter(col => 
    col.fixed || selectedColumns.value.includes(col.prop))
})

// 表格数据 (模拟数据)
const tableData = ref(generateMockData())

// 图表相关
const chartEl = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// 菜单选择处理
const handleMenuSelect = (index: string) => {
  if (index.startsWith('product_')) {
    currentProduct.value = parseInt(index.split('_')[1])
    loadData()
  } else if (index.startsWith('quarter_')) {
    currentQuarter.value = parseInt(index.split('_')[1])
    loadData()
  }
}

// 生成模拟数据
function generateMockData() {
  const data = []
  const days = 15
  const baseDate = new Date(2023, currentQuarter.value * 3 - 3, 1)
  
  for (let i = 0; i < days; i++) {
    const date = new Date(baseDate)
    date.setDate(baseDate.getDate() + i)
    
    data.push({
      date: date.toISOString().split('T')[0],
      sales: Math.round(80 + Math.random() * 70),
      users: Math.round(500 + Math.random() * 1000),
      conversion: Number((5 + Math.random() * 10).toFixed(1)),
      cost: Math.round(30 + Math.random() * 40),
      profit: Math.round(20 + Math.random() * 50)
    })
  }
  return data
}

// 模拟数据加载
const loadData = () => {
  tableData.value = generateMockData()
  updateChart()
}

// 初始化图表
const initChart = () => {
  if (chartEl.value) {
    chartInstance = echarts.init(chartEl.value)
    window.addEventListener('resize', resizeChart)
  }
}

// 更新图表
const updateChart = () => {
  if (!chartInstance || selectedColumns.value.length === 0) return

  const series = selectedColumns.value.map(prop => {
    const column = availableColumns.value.find(c => c.prop === prop)
    return {
      name: column?.label,
      type: 'line',
      data: tableData.value.map(item => item[prop]),
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: {
        width: 3
      }
    }
  })

  const option = {
    title: {
      text: `产品${currentProduct.value} Q${currentQuarter.value} 数据趋势`,
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: selectedColumns.value.map(prop => 
        availableColumns.value.find(c => c.prop === prop)?.label),
      bottom: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: tableData.value.map(item => item.date),
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value'
    },
    series: series
  }

  chartInstance.setOption(option, true)
}

// 图表自适应
const resizeChart = () => {
  chartInstance?.resize()
}

// 监听选中列变化
watch(selectedColumns, () => {
  updateChart()
})

// 初始化
onMounted(() => {
  initChart()
  updateChart()
})
</script>

<style scoped>
.data-analysis-container {
  padding: 20px;
}

.column-selector {
  margin: 20px 0;
}

.column-selector .el-checkbox {
  margin-right: 15px;
}

.data-card {
  margin-top: 20px;
}

.chart-card {
  margin-top: 20px;
}
</style>