<template>
  <div class="data-links-view">
    <el-card class="links-card">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span class="card-title">{{ t('dataLinks.title') }}</span>
            <span class="meta-text">{{ metaText }}</span>
          </div>
          <div class="header-tools">
            <el-select
              v-model="filters.product"
              :placeholder="t('dataLinks.product')"
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
              :placeholder="t('dataLinks.testType')"
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
              {{ t('dataLinks.reset') }}
            </el-button>
            <el-button
              type="primary"
              size="small"
              :icon="Refresh"
              @click="fetchDataLinks"
              :loading="loading"
            >{{ t('common.actions.refresh') }}</el-button>
          </div>
        </div>
      </template>

      <div v-if="!loading && !loadError && !dataLinks?.error" class="table-info">
        <span class="total-count">{{ t('dataLinks.total', { count: filteredLinks.length }) }}</span>
        <el-tag v-if="dataLinks?.current_month" size="small" type="info">
          {{ t('dataLinks.rawMonth', { month: dataLinks.current_month }) }}
        </el-tag>
      </div>

      <el-alert
        v-if="loadError || dataLinks?.error"
        type="error"
        show-icon
        :closable="false"
        class="status-alert"
      >
        <template #title>
          <div class="load-error-content">
            <span>{{ loadError || dataLinks?.error }}</span>
            <el-button size="small" type="danger" plain :loading="loading" @click="fetchDataLinks">
              {{ t('common.actions.retry') }}
            </el-button>
          </div>
        </template>
      </el-alert>
      <el-alert
        v-else-if="dataLinks?.warnings?.length"
        :title="dataLinks.warnings.join('；')"
        type="warning"
        show-icon
        :closable="false"
        class="status-alert"
      />

      <div v-if="loading" class="links-loading-state">
        <el-icon class="is-loading links-loading-icon"><Loading /></el-icon>
        <span>{{ t('dataLinks.loading') }}</span>
      </div>

      <el-table
        v-else-if="!loadError && !dataLinks?.error && filteredLinks.length > 0"
        :data="pagedLinks"
        v-loading="loading"
        stripe
        style="width: 100%"
        :max-height="tableHeight"
        class="data-links-table"
      >
        <el-table-column prop="product" :label="t('dataLinks.product')" min-width="110" fixed="left" />
        <el-table-column :label="t('dataLinks.testType')" min-width="210">
          <template #default="{ row }">
            <span class="test-type-text">{{ formatTestType(row.test_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('dataLinks.template')" min-width="170">
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
                  <button class="more-chip" type="button" :aria-label="t('dataLinks.oemTemplates')">
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                </template>
                <div class="popover-panel">
                  <div class="popover-title">{{ t('dataLinks.oemTemplateTitle') }}</div>
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
            <UnavailableCell v-else :text="t('dataLinks.noTemplate')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('dataLinks.tracker')" min-width="220">
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
                  <button class="more-chip" type="button" :aria-label="t('dataLinks.oemTrackers')">
                    <el-icon><MoreFilled /></el-icon>
                  </button>
                </template>
                <div class="popover-panel">
                  <div class="popover-title">{{ t('dataLinks.oemTrackerTitle') }}</div>
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
            <UnavailableCell v-else :text="t('dataLinks.noTracker')" />
          </template>
        </el-table-column>
        <el-table-column :label="t('dataLinks.rawFolder')" min-width="230">
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
            <UnavailableCell v-else :text="row.raw_data_folder?.note || t('dataLinks.noRawFolder')" />
          </template>
        </el-table-column>
      </el-table>

      <div
        v-if="!loading && !loadError && !dataLinks?.error && filteredLinks.length > 0"
        class="pagination-container"
      >
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredLinks.length"
          layout="total, prev, pager, next"
        />
      </div>

      <el-empty
        v-else-if="!loading && !loadError && !dataLinks?.error && filteredLinks.length === 0"
        :description="t('dataLinks.empty')"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { dataLinksApi } from '@/scripts/api'
import type { DataLinkEntry, DataLinkItem, DataLinksResponse } from '@/scripts/types'
import { Document, FolderOpened, Link as LinkIcon, Loading, MoreFilled, Refresh } from '@element-plus/icons-vue'
import { ElTooltip } from 'element-plus'
import { formatTestType, sameTestType, uniqueTestTypes } from '@/scripts/utils/testNames'
import { useAppLocale } from '@/i18n'

const { t } = useAppLocale()

const UnavailableCell = defineComponent({
  props: {
    text: {
      type: String,
      default: ''
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
const loading = ref(true)
const loadError = ref('')
const currentPage = ref(1)
const pageSize = 10
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

const pagedLinks = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredLinks.value.slice(start, start + pageSize)
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
  if (!dataLinks.value) return t('dataLinks.reading')
  const environment = dataLinks.value.environment || '-'
  const configFile = dataLinks.value.config_file || '-'
  const currentDate = dataLinks.value.current_date || '-'
  return t('dataLinks.meta', { environment, config: configFile, date: currentDate })
})

const availableLinks = (items?: DataLinkItem[] | null) => {
  return (items || []).filter((item) => item.available && item.url)
}

const primaryLink = (items?: DataLinkItem[] | null) => {
  const links = availableLinks(items)
  return links.find((item) => /(?:\u9ed8\u8ba4|default)/i.test(item.label)) || links[0] || null
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
  currentPage.value = 1
  loading.value = true
  loadError.value = ''
  try {
    const response = await dataLinksApi.getDataLinks()
    dataLinks.value = response.data
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail?.message || e?.response?.data?.detail || e?.message || t('errors.unknown')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDataLinks()
})

watch(
  () => [filters.value.product, filters.value.testType],
  () => {
    currentPage.value = 1
  }
)

watch(filteredLinks, () => {
  const maxPage = Math.max(1, Math.ceil(filteredLinks.value.length / pageSize))
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage
  }
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

.load-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.links-loading-state {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #606266;
  font-size: 14px;
}

.links-loading-icon {
  color: #409eff;
  font-size: 22px;
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

.pagination-container {
  display: flex;
  justify-content: center;
  padding-top: 16px;
  overflow-x: auto;
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
