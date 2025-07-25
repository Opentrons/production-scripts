<template>
  <div class="data-analysis-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>（折线图）</span>
            </div>
          </template>
          <div ref="lineChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>柱状图）</span>
            </div>
          </template>
          <div ref="barChart" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>（散点图）</span>
            </div>
          </template>
          <div ref="scatterChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>(饼图)</span>
            </div>
          </template>
          <div ref="pieChart" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import * as echarts from 'echarts';
import { onMounted, ref } from 'vue';

export default {
  name: 'DataAnalysis',
  setup() {
    const lineChart = ref(null);
    const barChart = ref(null);
    const scatterChart = ref(null);
    const pieChart = ref(null);

    // 虚拟数据
    const virtualData = {
      months: ['1月', '2月', '3月', '4月', '5月', '6月'],
      products: ['产品A', '产品B', '产品C', '产品D'],
      sales: [120, 200, 150, 80, 70, 110],
      productSales: {
        '产品A': 432,
        '产品B': 765,
        '产品C': 289,
        '产品D': 530
      },
      priceSales: [
        [10, 120],
        [15, 200],
        [8, 150],
        [12, 80],
        [20, 70],
        [18, 110]
      ],
      marketShare: [
        { value: 1048, name: '搜索引擎' },
        { value: 735, name: '直接访问' },
        { value: 580, name: '邮件营销' },
        { value: 484, name: '联盟广告' },
        { value: 300, name: '视频广告' }
      ]
    };

    // 初始化图表
    const initCharts = () => {
      // 1. 折线图
      const lineChartInstance = echarts.init(lineChart.value);
      lineChartInstance.setOption({
        tooltip: {
          trigger: 'axis'
        },
        legend: {
          data: ['销量']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: virtualData.months
        },
        yAxis: {
          type: 'value'
        },
        series: [
          {
            name: '销量',
            type: 'line',
            data: virtualData.sales,
            smooth: true,
            itemStyle: {
              color: '#409EFF'
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(64, 158, 255, 0.5)' },
                { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
              ])
            }
          }
        ]
      });

      // 2. 柱状图
      const barChartInstance = echarts.init(barChart.value);
      barChartInstance.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        xAxis: {
          type: 'category',
          data: virtualData.products
        },
        yAxis: {
          type: 'value'
        },
        series: [
          {
            name: '销量',
            type: 'bar',
            data: Object.values(virtualData.productSales),
            itemStyle: {
              color: function(params) {
                const colorList = ['#67C23A', '#E6A23C', '#F56C6C', '#909399'];
                return colorList[params.dataIndex];
              }
            }
          }
        ]
      });

      // 3. 散点图
      const scatterChartInstance = echarts.init(scatterChart.value);
      scatterChartInstance.setOption({
        tooltip: {
          formatter: '价格: {c0}<br/>销量: {c1}'
        },
        xAxis: {
          name: '价格',
          type: 'value'
        },
        yAxis: {
          name: '销量',
          type: 'value'
        },
        series: [
          {
            symbolSize: 20,
            data: virtualData.priceSales,
            type: 'scatter',
            itemStyle: {
              color: '#F56C6C'
            }
          }
        ]
      });

      // 4. 饼图
      const pieChartInstance = echarts.init(pieChart.value);
      pieChartInstance.setOption({
        tooltip: {
          trigger: 'item'
        },
        legend: {
          orient: 'vertical',
          left: 'left'
        },
        series: [
          {
            name: '访问来源',
            type: 'pie',
            radius: '50%',
            data: virtualData.marketShare,
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            },
            itemStyle: {
              borderRadius: 10,
              borderColor: '#fff',
              borderWidth: 2
            }
          }
        ]
      });

      // 窗口大小变化时重新调整图表大小
      window.addEventListener('resize', function() {
        lineChartInstance.resize();
        barChartInstance.resize();
        scatterChartInstance.resize();
        pieChartInstance.resize();
      });
    };

    onMounted(() => {
      initCharts();
    });

    return {
      lineChart,
      barChart,
      scatterChart,
      pieChart
    };
  }
};
</script>

<style scoped>
.data-analysis-container {
  padding: 20px;
}

.chart-card {
  margin-bottom: 20px;
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}

.chart {
  height: 400px;
}

.el-row {
  margin-bottom: 20px;
}
</style>