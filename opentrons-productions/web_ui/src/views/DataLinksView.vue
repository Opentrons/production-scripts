<template>
  <div class="data-links-view">
    <el-card class="links-card">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span class="card-title">数据链接</span>
            <span class="meta-text">{{ metaText }}</span>
          </div>
          <div class="header-tools">
            <el-select
              v-model="filters.product"
              placeholder="产品型号"
              clearable
              filterable
              size="small"
              class="filter-control"
            >
              <el-option
                v-for="product in productOptions"
                :key="product"
                :label="product"
                :value="product"
              />
            </el-select>
            <el-select
              v-model="filters.testType"
              placeholder="测试类型"
              clearable
              filterable
              size="small"
              class="filter-control"
            >
              <el-option
                v-for="testType in testTypeOptions"
                :key="testType"
                :label="formatTestType(testType)"
                :value="testType"
              />
            </el-select>
            <el-button size="small" @click="resetFilters" :disabled="!hasActiveFilters">
              重置
            </el-button>
            <el-button type="primary" size="small" @click="fetchDataLinks" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="table-info">
        <span class="total-count">共 {{ filteredLinks.length }} 条链接配置</span>
        <el-tag v-if="dataLinks?.current_month" size="small" type="info">
          原数据: {{ dataLinks.current_month }} 月
        </el-tag>
      </div>

      <el-alert
        v-if="dataLinks?.error"
        :title="dataLinks.error"
        type="error"
        show-icon
        :closable="false"
        class="status-alert"
      />
      <el-alert
        v-else-if="dataLinks?.warnings?.length"
        :title="dataLinks.warnings.join('；')"
        type="warning"
        show-icon
        :closable="false"
        class="status-alert"
      />

      <el-table
        :data="filteredLinks"
        v-loading="loading"
        stripe
        style="width: 100%"
        :max-height="tableHeight"
        class="data-links-table"
      >
        <el-table-column prop="product" label="产品型号" min-width="110" fixed="left" />
        <el-table-column label="测试类型" min-width="210">
          <template #default="{ row }">
            <span class="test-type-text">{{ formatTestType(row.test_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模版链接" min-width="170">
          <template #default="{ row }">
            <div v-if="availableLinks(row.templates).length" class="compact-link-cell">
              <el-tooltip
                :content="primaryLink(row.templates)?.note || primaryLink(row.templates)?.label"
                placement="top"
              >
                <a
                  :href="primaryLink(row.templates)?.url || '#'"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="link-chip"
                >
                  <el-icon><Document /></el-icon>
                  <span>{{ primaryLink(row.templates)?.label }}</span>
                </a>
              </el-tooltip>
              <el-popover
                v-if="extraLinks(row.templates).length"
                trigger="hover"
                placement="top"
                width="220"
                popper-class="data-links-popover"
              >
                <template #reference>
                  <button class="more-chip" type="button" aria-label="OEM 模版链接">
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                </template>
                <div class="popover-panel">
                  <div class="popover-title">OEM 模版</div>
                  <a
                    v-for="link in extraLinks(row.templates)"
                    :key="`${row.config_key}-template-extra-${link.label}-${link.file_id}`"
                    :href="link.url || '#'"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="popover-link"
                  >
                    <span>{{ link.label }}</span>
                    <small v-if="link.note">{{ link.note }}</small>
                  </a>
                </div>
              </el-popover>
            </div>
            <UnavailableCell v-else text="当前 YAML 未配置模版链接" />
          </template>
        </el-table-column>
        <el-table-column label="测试总表" min-width="220">
          <template #default="{ row }">
            <div v-if="availableLinks(row.trackers).length" class="compact-link-cell">
              <el-tooltip
                :content="primaryLink(row.trackers)?.note || primaryLink(row.trackers)?.label"
                placement="top"
              >
                <a
                  :href="primaryLink(row.trackers)?.url || '#'"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="link-chip"
                >
                  <el-icon><LinkIcon /></el-icon>
                  <span>{{ primaryLink(row.trackers)?.label }}</span>
                </a>
              </el-tooltip>
              <el-popover
                v-if="extraLinks(row.trackers).length"
                trigger="hover"
                placement="top"
                width="220"
                popper-class="data-links-popover"
              >
                <template #reference>
                  <button class="more-chip" type="button" aria-label="OEM 测试总表链接">
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                </template>
                <div class="popover-panel">
                  <div class="popover-title">OEM 测试总表</div>
                  <a
                    v-for="link in extraLinks(row.trackers)"
                    :key="`${row.config_key}-tracker-extra-${link.label}-${link.file_id}`"
                    :href="link.url || '#'"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="popover-link"
                  >
                    <span>{{ link.label }}</span>
                    <small v-if="link.note">{{ link.note }}</small>
                  </a>
                </div>
              </el-popover>
            </div>
            <UnavailableCell v-else text="当前 YAML 未配置测试总表链接" />
          </template>
        </el-table-column>
        <el-table-column label="原数据文件夹" min-width="230">
          <template #default="{ row }">
            <div v-if="rawFolderLinks(row).length" class="link-list">
              <el-tooltip
                v-for="link in rawFolderLinks(row)"
                :key="`${row.config_key}-raw-${link.label}-${link.file_id}`"
                :content="link.note || link.label"
                placement="top"
              >
                <a
                  :href="link.url || '#'"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="link-chip"
                >
                  <el-icon><FolderOpened /></el-icon>
                  <span>{{ link.label }}</span>
                </a>
              </el-tooltip>
            </div>
            <UnavailableCell v-else :text="row.raw_data_folder?.note || '当前 YAML 未配置当月原数据文件夹'" />
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && filteredLinks.length === 0"
        description="暂无数据链接"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { dataLinksApi } from '@/api'
import type { DataLinkEntry, DataLinkItem, DataLinksResponse } from '@/types'
import { Document, FolderOpened, Link as LinkIcon, MoreFilled, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElTooltip } from 'element-plus'
import { formatTestType, sameTestType, uniqueTestTypes } from '@/utils/testNames'

const UnavailableCell = defineComponent({
  props: {
    text: {
      type: String,
      default: '当前数据不完整'
    }
  },
  setup(props) {
    return () =>
      h(
        ElTooltip,
        { content: props.text, placement: 'top' },
        {
          default: () => h('span', { class: 'na-cell' }, 'N/A')
        }
      )
  }
})

const dataLinks = ref<DataLinksResponse | null>(null)
const loading = ref(false)
const filters = ref({
  product: '',
  testType: ''
})

const links = computed(() => dataLinks.value?.links || [])

const filteredLinks = computed(() => {
  return links.value.filter((item) => {
    if (filters.value.product && item.product !== filters.value.product) return false
    if (filters.value.testType && !sameTestType(item.test_type, filters.value.testType)) return false
    return true
  })
})

const productOptions = computed(() => {
  return Array.from(new Set(links.value.map((item) => item.product))).sort()
})

const testTypeOptions = computed(() => {
  return uniqueTestTypes(links.value.map((item) => item.test_type))
})

const hasActiveFilters = computed(() => {
  return Boolean(filters.value.product || filters.value.testType)
})

const tableHeight = computed(() => {
  return window.innerHeight - 260
})

const metaText = computed(() => {
  if (!dataLinks.value) return '读取中'
  const environment = dataLinks.value.environment || '-'
  const configFile = dataLinks.value.config_file || '-'
  const currentDate = dataLinks.value.current_date || '-'
  return `环境: ${environment} | 配置: ${configFile} | 日期: ${currentDate}`
})

const availableLinks = (items?: DataLinkItem[] | null) => {
  return (items || []).filter((item) => item.available && item.url)
}

const primaryLink = (items?: DataLinkItem[] | null) => {
  const links = availableLinks(items)
  return links.find((item) => item.label.includes('默认')) || links[0] || null
}

const extraLinks = (items?: DataLinkItem[] | null) => {
  const primary = primaryLink(items)
  return availableLinks(items).filter((item) => item !== primary)
}

const rawFolderLinks = (row: DataLinkEntry) => {
  return availableLinks(row.raw_data_folder ? [row.raw_data_folder] : [])
}

const resetFilters = () => {
  filters.value = {
    product: '',
    testType: ''
  }
}

const fetchDataLinks = async () => {
  loading.value = true
  try {
    const response = await dataLinksApi.getDataLinks()
    dataLinks.value = response.data
    if (response.data.error) {
      ElMessage.error('获取数据链接失败: ' + response.data.error)
    }
  } catch (e: any) {
    ElMessage.error('获取数据链接失败: ' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDataLinks()
})
</script>

<style scoped>
.data-links-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.links-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  border-radius: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.meta-text {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.filter-control {
  width: 150px;
}

.table-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.total-count {
  font-size: 14px;
  color: #909399;
}

.status-alert {
  margin-bottom: 12px;
}

.data-links-table {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.data-links-table :deep(.el-table__header th) {
  background: #f8fafc;
  color: #606266;
  font-weight: 600;
}

.data-links-table :deep(.el-table__cell) {
  padding: 8px 0;
}

.test-type-text {
  color: #303133;
  font-weight: 500;
}

.link-list,
.compact-link-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.compact-link-cell {
  flex-wrap: nowrap;
}

.link-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 70px;
  max-width: 170px;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  line-height: 24px;
  text-decoration: none;
  white-space: nowrap;
}

.link-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-chip:hover {
  border-color: #409eff;
  background: #e6f1fc;
}

.more-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  padding: 0;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  cursor: pointer;
}

.more-chip:hover {
  border-color: #409eff;
  color: #409eff;
  background: #f5fbff;
}

.popover-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.popover-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.popover-link {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 8px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  color: #409eff;
  text-decoration: none;
}

.popover-link:hover {
  border-color: #409eff;
  background: #f5fbff;
}

.popover-link span {
  font-size: 13px;
  line-height: 18px;
}

.popover-link small {
  color: #909399;
  font-size: 11px;
  line-height: 16px;
}

.na-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 24px;
  padding: 0 9px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #f4f4f5;
  color: #909399;
  font-size: 12px;
  line-height: 22px;
  text-align: center;
  white-space: nowrap;
  cursor: help;
}

@media (max-width: 900px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-tools,
  .filter-control {
    width: 100%;
  }

  .meta-text {
    white-space: normal;
  }
}
</style>
