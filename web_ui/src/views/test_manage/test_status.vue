<template>
  <div class="dashboard-container">
    <!-- 顶部统计和添加按钮 -->
    <div class="dashboard-header">
      <a-space size="large">
        <a-statistic title="总产品数" :value="products.length" />
        <a-statistic title="总测试项" :value="totalTests" />
        <a-statistic title="平均通过率" :value="`${averagePassRate}%`" />
        
        <a-popover placement="bottomRight" trigger="click">
          <template #content>
            <a-menu>
              <a-menu-item @click="showProductModal">新建产品</a-menu-item>
              <a-menu-item @click="showTestModal">新建测试项</a-menu-item>
            </a-menu>
          </template>
          <a-button type="primary" shape="circle" size="large">
            <template #icon><plus-outlined /></template>
          </a-button>
        </a-popover>
      </a-space>
    </div>

    <!-- 产品卡片网格 -->
    <a-row :gutter="[16, 16]" class="product-grid">
      <a-col 
        v-for="product in products" 
        :key="product.id"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <a-card hoverable class="product-card">
          <template #cover>
            <h3 style="padding: 10px;">{{ product.name }}</h3>
            <div class="card-cover">
              <ECharts 
                :options="getBarOptions(product)"
                height="240px"
              />
            </div>
          </template>
          
          <a-card-meta>
            <template #description>
              <div class="card-footer">
                <ECharts 
                  :options="getPieOptions(product)"
                  height="160px"
                />
                
                <div class="version-links">
                  <a-popover 
                    v-for="test in product.tests" 
                    :key="test.type"
                    placement="right"
                  >
                    <template #content>
                      <div>
                        <p>版本: {{ test.version }}</p>
                        <a :href="test.link" target="_blank">查看测试数据 <link-outlined /></a>
                      </div>
                    </template>
                    <a-tag :color="getTagColor(test.passRate)">
                      {{ test.type }} ({{ test.passRate }}%)
                    </a-tag>
                  </a-popover>
                </div>
              </div>
            </template>
          </a-card-meta>
        </a-card>
      </a-col>
    </a-row>

    <!-- 新建产品模态框 -->
    <a-modal
      v-model:visible="productModalVisible"
      title="新建产品"
      @ok="handleProductOk"
      @cancel="productModalVisible = false"
    >
      <a-form :model="newProduct" layout="vertical">
        <a-form-item label="产品名称" required>
          <a-input v-model:value="newProduct.name" />
        </a-form-item>
        <a-form-item label="产品类型" required>
          <a-select v-model:value="newProduct.type">
            <a-select-option value="pipette">移液器</a-select-option>
            <a-select-option value="handler">液体工作站</a-select-option>
            <a-select-option value="module">模块</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 新建测试模态框 -->
    <a-modal
      v-model:visible="testModalVisible"
      title="新建测试项"
      @ok="handleTestOk"
      @cancel="testModalVisible = false"
    >
      <a-form :model="newTest" layout="vertical">
        <a-form-item label="选择产品" required>
          <a-select v-model:value="newTest.productId">
            <a-select-option 
              v-for="p in products" 
              :key="p.id" 
              :value="p.id"
            >
              {{ p.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="测试类型" required>
          <a-select v-model:value="newTest.type">
            <a-select-option value="diagnostic">诊断测试</a-select-option>
            <a-select-option value="volume">容量测试</a-select-option>
            <a-select-option value="protocol">协议测试</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="版本号" required>
          <a-input v-model:value="newTest.version" placeholder="例如: v1.0" />
        </a-form-item>
        <a-form-item label="通过率(%)" required>
          <a-input-number 
            v-model:value="newTest.passRate" 
            :min="0" 
            :max="100" 
          />
        </a-form-item>
        <a-form-item label="数据链接">
          <a-input v-model:value="newTest.link" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { 
  PlusOutlined, 
  LinkOutlined 
} from '@ant-design/icons-vue';
import ECharts from '@/components/ECharts.vue';

// 产品数据
const products = ref([
  {
    id: 'ot3',
    name: 'OT3液体工作站',
    type: 'handler',
    tests: [
      { type: '诊断测试', version: 'v8.1.0', passRate: 92, link: '/tests/ot3/diag' },
      { type: '容量测试', version: 'v1.8', passRate: 88, link: '/tests/ot3/vol' },
      { type: '协议测试', version: 'v3.2', passRate: 95, link: '/tests/ot3/proto' }
    ]
  },
  {
    id: 'single-channel',
    name: '单通道移液器',
    type: 'pipette',
    tests: [
      { type: '精度测试', version: 'v8.1.0', passRate: 98, link: '/tests/single/precision' },
      { type: '容量测试', version: 'v1.3', passRate: 97, link: '/tests/single/vol' }
    ]
  },
  {
    id: '8-channel',
    name: '8通道移液器',
    type: 'pipette',
    tests: [
      { type: '平行性测试', version: 'v8.1.0', passRate: 96, link: '/tests/8ch/parallel' },
      { type: '容量测试', version: 'v1.4', passRate: 95, link: '/tests/8ch/vol' }
    ]
  },
  {
    id: '96ch-low',
    name: '低精度96CH',
    type: 'pipette',
    tests: [
      { type: '批量测试', version: 'v2.0', passRate: 90, link: '/tests/96low/batch' },
      { type: '校准测试', version: 'v1.9', passRate: 89, link: '/tests/96low/calib' }
    ]
  },
  {
    id: '96ch-high',
    name: '高精度96CH',
    type: 'pipette',
    tests: [
      { type: '精度测试', version: 'v2.2', passRate: 94, link: '/tests/96high/precision' },
      { type: '稳定性测试', version: 'v2.1', passRate: 96, link: '/tests/96high/stability' }
    ]
  },
  {
    id: 'module1',
    name: '模块1',
    type: 'module',
    tests: [
      { type: '功能测试', version: 'v1.2', passRate: 91, link: '/tests/module1/function' },
      { type: '压力测试', version: 'v1.1', passRate: 93, link: '/tests/module1/stress' }
    ]
  },
  {
    id: 'module2',
    name: '模块2',
    type: 'module',
    tests: [
      { type: '兼容性测试', version: 'v1.3', passRate: 95, link: '/tests/module2/compat' },
      { type: '性能测试', version: 'v1.4', passRate: 97, link: '/tests/module2/perf' }
    ]
  }
]);

// 计算统计值
const totalTests = computed(() => {
  return products.value.reduce((sum, p) => sum + p.tests.length, 0);
});

const averagePassRate = computed(() => {
  const total = products.value.flatMap(p => p.tests).reduce((sum, t) => sum + t.passRate, 0);
  return (total / totalTests.value).toFixed(1);
});

// 获取柱状图配置
const getBarOptions = (product) => {
  const testTypes = [...new Set(product.tests.map(t => t.type))];
  const versions = [...new Set(product.tests.map(t => t.version))];

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: params => {
        return `${params[0].axisValueLabel}<br/>
                ${params[0].marker} ${params[0].seriesName}: ${params[0].value}%`
      }
    },
    legend: {
      data: versions,
      bottom: 0,
      itemWidth: 14,
      itemHeight: 14,
      textStyle: {
        fontSize: 10
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '3%',
      containLabel: true
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      },
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    xAxis: {
      type: 'category',
      data: testTypes,
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: versions.map(version => {
      const versionTests = product.tests.filter(t => t.version === version);
      return {
        name: version,
        type: 'bar',
        barWidth: 30,
        barGap: '1%',
        barCategoryGap: '1%',
        data: testTypes.map(type => {
          const test = versionTests.find(t => t.type === type);
          return test ? test.passRate : 0;
        }),
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: getVersionColor(version)
        },
        label: {
          show: false,
          position: 'right',
          formatter: '{c}%',
          color: '#666'
        }
      }
    })
  };
};

// 获取饼图配置
const getPieOptions = (product) => {
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c}% ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        fontSize: 10
      }
    },
    series: [
      {
        name: '测试分布',
        type: 'pie',
        radius: ['50%', '70%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 1
        },
        label: {
          show: true,
          formatter: '{b}: {c}%',
          fontSize: 10
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        labelLine: {
          length: 2,
          length2: 4
        },
        data: product.tests.map(test => ({
          value: test.passRate,
          name: test.type,
          itemStyle: { color: getTestColor(test.type) }
        }))
      }
    ]
  };
};

// 根据通过率获取标签颜色
const getTagColor = (rate) => {
  if (rate >= 95) return 'green';
  if (rate >= 85) return 'blue';
  if (rate >= 75) return 'orange';
  return 'red';
};

// 版本颜色映射
const getVersionColor = (version) => {
  const colors = ['#1890ff', '#13c2c2', '#722ed1', '#f5222d', '#fa8c16', '#52c41a'];
  const index = version.charCodeAt(1) % colors.length;
  return colors[index];
};

// 测试类型颜色映射
const getTestColor = (type) => {
  const colors = {
    '诊断测试': '#1890ff',
    '容量测试': '#13c2c2',
    '协议测试': '#722ed1',
    '精度测试': '#f5222d',
    '平行性测试': '#fa8c16',
    '批量测试': '#52c41a',
    '校准测试': '#eb2f96'
  };
  return colors[type] || '#d9d9d9';
};

// 新建产品相关
const productModalVisible = ref(false);
const newProduct = ref({
  name: '',
  type: ''
});

const showProductModal = () => {
  newProduct.value = { name: '', type: '' };
  productModalVisible.value = true;
};

const handleProductOk = () => {
  products.value.push({
    id: `product-${Date.now()}`,
    name: newProduct.value.name,
    type: newProduct.value.type,
    tests: []
  });
  productModalVisible.value = false;
};

// 新建测试相关
const testModalVisible = ref(false);
const newTest = ref({
  productId: '',
  type: '',
  version: '',
  passRate: 90,
  link: ''
});

const showTestModal = () => {
  newTest.value = {
    productId: products.value[0]?.id || '',
    type: 'diagnostic',
    version: '',
    passRate: 90,
    link: ''
  };
  testModalVisible.value = true;
};

const handleTestOk = () => {
  const product = products.value.find(p => p.id === newTest.value.productId);
  if (product) {
    product.tests.push({
      type: newTest.value.type === 'diagnostic' ? '诊断测试' : 
            newTest.value.type === 'volume' ? '容量测试' : '协议测试',
      version: newTest.value.version,
      passRate: newTest.value.passRate,
      link: newTest.value.link || '#'
    });
  }
  testModalVisible.value = false;
};
</script>

<style scoped>
.dashboard-container {
  padding: 24px;
}

.dashboard-header {
  margin-bottom: 24px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 8px 2px 8px rgba(0,0,0,0.1);
  border: 2px;
}

.product-grid {
  margin-top: 16px;
}

.product-card {
  height: 100%;
  transition: all 0.3s;
  border-radius: 8px;
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.1);
  border: 30px;
}

.card-cover {
  padding: 16px;
  height: 280px;
}

.card-footer {
  margin-top: 16px;
  position: relative;
}

.version-links {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.ant-tag) {
  cursor: pointer;
  margin-bottom: 0;
}
</style>