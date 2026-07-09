<template>
  <div class="data-view">
    <el-card class="data-card">
      <template #header>
        <div class="card-header">
          <div class="title-group">
            <el-segmented
              v-model="activePanel"
              :options="panelOptions"
              class="data-panel-switch"
            />
          </div>
          <div class="header-tools">
            <template v-if="activePanel === 'records'">
            <el-select
              v-model="selectedCollection" 
              placeholder="选择数据集合" 
              @change="handleCollectionChange"
              style="width: 220px"
              size="small"
              :loading="collectionsLoading"
            >
              <el-option 
                v-for="col in collectionOptions" 
                :key="col.value" 
                :label="col.label" 
                :value="col.value" 
              />
            </el-select>
            <el-button type="primary" size="small" @click="handleRefresh" :loading="dataLoading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            </template>
            <template v-else>
              <el-button type="primary" size="small" plain @click="syncUnitTrackerRows" :loading="unitTrackerSyncing">
                <el-icon><Refresh /></el-icon>
                更新所有产品标准行
              </el-button>
              <el-button type="primary" size="small" @click="fetchUnitTrackerRows" :loading="unitTrackerLoading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </template>
          </div>
        </div>
      </template>

      <template v-if="activePanel === 'records'">
      <div class="table-info">
        <span class="total-count">集合: {{ selectedCollectionTitle }} | 共 {{ total }} 条记录</span>
      </div>

      <div class="filter-bar">
        <el-select
          v-model="filters.model"
          placeholder="产品型号"
          clearable
          filterable
          size="small"
          class="filter-control"
          @change="handleFilterSearch"
        >
          <el-option
            v-for="model in filterOptions.models"
            :key="model"
            :label="model"
            :value="model"
          />
        </el-select>
        <el-select
          v-model="filters.type"
          placeholder="产品类型"
          clearable
          filterable
          size="small"
          class="filter-control"
          @change="handleFilterSearch"
        >
          <el-option
            v-for="typeItem in filterOptions.types"
            :key="typeItem"
            :label="typeItem"
            :value="typeItem"
          />
        </el-select>
        <el-select
          v-model="filters.totalResult"
          placeholder="测试结果"
          clearable
          filterable
          size="small"
          class="filter-control"
          @change="handleFilterSearch"
        >
          <el-option
            v-for="result in filterOptions.total_results"
            :key="result"
            :label="result"
            :value="result"
          />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          size="small"
          class="date-filter"
          @change="handleFilterSearch"
        />
        <el-input
          v-model="filters.barcode"
          placeholder="条码 / SN"
          clearable
          size="small"
          class="barcode-filter"
          @keyup.enter="handleFilterSearch"
          @clear="handleFilterSearch"
        />
        <el-button size="small" type="primary" plain @click="handleFilterSearch" :loading="dataLoading">
          查询
        </el-button>
        <el-button size="small" @click="handleResetFilters" :disabled="!hasActiveFilters">
          重置
        </el-button>
      </div>
      
      <el-table 
        v-if="tableData.length > 0"
        :data="tableData" 
        v-loading="dataLoading"
        stripe
        style="width: 100%"
        :max-height="tableHeight"
        class="data-table"
      >
        <el-table-column 
          v-for="column in tableColumns" 
          :key="column.key"
          :prop="column.key" 
          :label="column.label" 
          :min-width="column.minWidth"
          show-overflow-tooltip
        >
          <template #default="scope">
            <template v-if="column.key === 'total_result'">
              <el-tag
                v-if="hasResult(scope.row)"
                :type="resultTagType(getTotalResult(scope.row))"
                size="small"
                effect="light"
              >
                {{ formatResultText(getTotalResult(scope.row)) }}
              </el-tag>
              <el-tooltip v-else content="当前数据不完整" placement="top">
                <span class="na-cell">N/A</span>
              </el-tooltip>
            </template>
            <template v-else-if="shouldRenderLink(column, scope.row[column.key])">
              <a 
                :href="formatHref(scope.row[column.key])" 
                target="_blank" 
                rel="noopener noreferrer"
                class="link-cell"
              >
                {{ column.linkText }}
              </a>
            </template>
            <template v-else-if="column.key === 'collection'">
              <span>{{ formatCellValue(scope.row[column.key]).toUpperCase() }}</span>
            </template>
            <template v-else-if="column.key === 'update_time'">
              <span class="time-cell">{{ formatDateTime(scope.row[column.key]) }}</span>
            </template>
            <template v-else-if="shouldRenderUnavailable(column, scope.row[column.key])">
              <el-tooltip content="当前数据不完整" placement="top">
                <span class="na-cell">N/A</span>
              </el-tooltip>
            </template>
            <template v-else>{{ formatCellValue(scope.row[column.key]) }}</template>
          </template>
        </el-table-column>
        <el-table-column label="分析" width="92" fixed="right">
          <template #default="scope">
            <el-button size="small" text type="primary" @click="openAnalysis(scope.row)">
              分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty 
        v-else-if="!dataLoading" 
        description="当前暂无数据" 
      />
      
      <div class="pagination-container" v-if="total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="20"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>
      </template>

      <template v-else>
        <div class="filter-bar unit-tracker-filter">
          <el-input
            v-model="unitTrackerFilters.barcode"
            placeholder="SN / 条码"
            clearable
            size="small"
            class="barcode-filter"
            @keyup.enter="fetchUnitTrackerRows"
            @clear="fetchUnitTrackerRows"
          />
          <el-select
            v-model="unitTrackerFilters.product"
            placeholder="产品"
            size="small"
            class="filter-control"
            @change="fetchUnitTrackerRows"
          >
            <el-option
              v-for="product in unitTrackerProductOptions"
              :key="product"
              :label="product"
              :value="product"
            />
          </el-select>
          <el-select
            v-model="unitTrackerFilters.testType"
            placeholder="测试"
            filterable
            size="small"
            class="filter-control"
            @change="fetchUnitTrackerRows"
          >
            <el-option
              v-for="testType in unitTrackerTestOptions"
              :key="testType"
              :label="testType"
              :value="testType"
            />
          </el-select>
          <el-select
            v-model="unitTrackerSelectedGroups"
            placeholder="分组"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            filterable
            size="small"
            class="group-filter"
          >
            <el-option
              v-for="group in unitTrackerGroupOptions"
              :key="group.key"
              :label="group.label"
              :value="group.key"
            />
          </el-select>
          <el-button size="small" type="primary" plain @click="fetchUnitTrackerRows" :loading="unitTrackerLoading">
            查询
          </el-button>
          <el-button size="small" @click="resetUnitTrackerFilters" :disabled="!hasUnitTrackerFilters">
            重置
          </el-button>
          <span class="unit-tracker-meta">标准行 {{ unitTrackerTotal }} 条</span>
        </div>

        <el-alert
          v-if="unitTrackerSyncResult"
          class="unit-tracker-alert"
          type="success"
          :closable="true"
          show-icon
          @close="unitTrackerSyncResult = null"
        >
          <template #title>
            扫描 {{ unitTrackerSyncResult.scanned }}，更新 {{ unitTrackerSyncResult.updated }}，跳过 {{ unitTrackerSyncResult.skipped }}
          </template>
        </el-alert>

        <el-table
          v-if="unitTrackerRows.length > 0"
          :data="unitTrackerRows"
          v-loading="unitTrackerLoading"
          stripe
          style="width: 100%"
          :max-height="unitTrackerTableHeight"
          class="data-table"
          :header-cell-class-name="unitTrackerHeaderClassName"
        >
          <el-table-column
            v-for="group in unitTrackerColumnGroups"
            :key="group.key"
            :label="group.label"
            :class-name="`unit-tracker-group-${group.key}`"
            align="center"
          >
            <el-table-column
              v-for="column in group.columns"
              :key="column.key"
              :label="column.label"
              :min-width="unitTrackerColumnWidth(column.key)"
              show-overflow-tooltip
              align="center"
            >
              <template #default="{ row }">
                <a
                  v-if="column.key === 'link' && unitTrackerCellValue(row, column.key)"
                  :href="unitTrackerCellValue(row, column.key)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="link-cell"
                >
                  打开
                </a>
                <button
                  v-else-if="column.key === 'sn' && unitTrackerAnalysisPath(row)"
                  type="button"
                  class="text-link-cell"
                  @click="openUnitTrackerAnalysis(row)"
                >
                  {{ formatCellValue(unitTrackerCellValue(row, column.key)) }}
                </button>
                <span v-else>{{ formatCellValue(unitTrackerCellValue(row, column.key)) }}</span>
              </template>
            </el-table-column>
          </el-table-column>
        </el-table>

        <el-empty v-else-if="!unitTrackerLoading" description="暂无 Unit Tracker 标准行" />

        <div class="pagination-container" v-if="unitTrackerTotal > 0">
          <el-pagination
            v-model:current-page="unitTrackerPage"
            :page-size="unitTrackerPageSize"
            :total="unitTrackerTotal"
            layout="prev, pager, next, total"
            @current-change="handleUnitTrackerPageChange"
          />
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { collectionApi, uploadRecordApi } from '@/api'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { sameTestType } from '@/utils/testNames'
import type { UnitTrackerColumn, UnitTrackerRow, UnitTrackerSyncResponse } from '@/types'

interface TableColumn {
  key: string
  label: string
  minWidth: number
  isLink?: boolean
  linkText?: string
}

const ALL_COLLECTION = '__all__'
const router = useRouter()
type ActivePanel = 'records' | 'unit_tracker'
const DEFAULT_UNIT_TRACKER_PRODUCT = 'P2HH'
const DEFAULT_UNIT_TRACKER_TEST = 'Assembly QC'

const BASE_COLUMNS: TableColumn[] = [
  { key: 'update_time', label: '更新时间', minWidth: 190 },
  { key: 'sn', label: '条码 / SN', minWidth: 170 },
  { key: 'model', label: '产品型号', minWidth: 110 },
  { key: 'type', label: '产品类型', minWidth: 120 },
  { key: 'total_result', label: '测试结果', minWidth: 120 },
  { key: 'csv_link', label: '测试数据', minWidth: 110, isLink: true, linkText: '打开' },
  { key: 'unit_tracker', label: '测试总表', minWidth: 140, isLink: true, linkText: '打开' }
]

const collections = ref<string[]>([])
const activePanel = ref<ActivePanel>('records')
const selectedCollection = ref(ALL_COLLECTION)
const tableData = ref<Record<string, any>[]>([])
const total = ref(0)
const currentPage = ref(1)
const collectionsLoading = ref(false)
const dataLoading = ref(false)
const filterOptions = ref({
  models: [] as string[],
  types: [] as string[],
  total_results: [] as string[]
})
const filters = ref({
  model: '',
  type: '',
  totalResult: '',
  barcode: '',
  dateRange: [] as string[]
})
const unitTrackerRows = ref<UnitTrackerRow[]>([])
const unitTrackerColumns = ref<UnitTrackerColumn[]>([])
const unitTrackerTotal = ref(0)
const unitTrackerPage = ref(1)
const unitTrackerPageSize = 50
const unitTrackerLoading = ref(false)
const unitTrackerSyncing = ref(false)
const unitTrackerSyncResult = ref<UnitTrackerSyncResponse | null>(null)
const unitTrackerSelectedGroups = ref<string[]>([])
const unitTrackerFilters = ref({
  product: DEFAULT_UNIT_TRACKER_PRODUCT,
  testType: DEFAULT_UNIT_TRACKER_TEST,
  barcode: ''
})

const panelOptions = [
  { label: '测试数据', value: 'records' },
  { label: 'Unit Tracker', value: 'unit_tracker' }
]
const unitTrackerProductOptions = [DEFAULT_UNIT_TRACKER_PRODUCT]
const unitTrackerTestOptions = [DEFAULT_UNIT_TRACKER_TEST]

const tableColumns = computed(() => {
  if (selectedCollection.value === ALL_COLLECTION) {
    return [
      { key: 'collection', label: '数据集合', minWidth: 180 },
      ...BASE_COLUMNS
    ]
  }
  return BASE_COLUMNS
})

const unitTrackerAllColumnGroups = computed(() => {
  const groups: Array<{ key: string; label: string; columns: UnitTrackerColumn[] }> = []
  unitTrackerColumns.value.forEach((column) => {
    const groupLabel = column.group || 'Others'
    const groupKey = column.group_key || groupLabel
    const current = groups[groups.length - 1]
    if (current && current.key === groupKey) {
      current.columns.push(column)
      return
    }
    groups.push({
      key: groupKey,
      label: groupLabel,
      columns: [column]
    })
  })
  return groups
})

const unitTrackerGroupOptions = computed(() => {
  return unitTrackerAllColumnGroups.value
    .filter((group) => group.key !== 'info')
    .map((group) => ({ key: group.key, label: group.label }))
})

const unitTrackerColumnGroups = computed(() => {
  if (!unitTrackerSelectedGroups.value.length) {
    return unitTrackerAllColumnGroups.value
  }
  const selected = new Set(unitTrackerSelectedGroups.value)
  return unitTrackerAllColumnGroups.value.filter((group) => group.key === 'info' || selected.has(group.key))
})

const collectionOptions = computed(() => {
  return [
    { value: ALL_COLLECTION, label: 'ALL' },
    ...collections.value.map((collection) => ({
      value: collection,
      label: collection.toUpperCase()
    }))
  ]
})

const selectedCollectionTitle = computed(() => {
  if (selectedCollection.value === ALL_COLLECTION) {
    return '全部测试数据'
  }
  return selectedCollection.value ? selectedCollection.value.toUpperCase() : ''
})

const tableHeight = computed(() => {
  return window.innerHeight - 300
})

const unitTrackerTableHeight = computed(() => {
  return window.innerHeight - 250
})

const hasActiveFilters = computed(() => {
  return Boolean(
    filters.value.model ||
    filters.value.type ||
    filters.value.totalResult ||
    filters.value.barcode ||
    filters.value.dateRange?.length
  )
})

const hasUnitTrackerFilters = computed(() => Boolean(
  unitTrackerFilters.value.product ||
  unitTrackerFilters.value.testType ||
  unitTrackerFilters.value.barcode
))

watch(activePanel, (panel) => {
  if (panel === 'unit_tracker' && !unitTrackerRows.value.length) {
    fetchUnitTrackerRows()
  }
})

const sortCollections = (items: string[]) => {
  return [...items].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
}

const formatHref = (value: unknown) => {
  return String(value || '')
}

const isUnavailableValue = (value: unknown) => {
  const normalized = String(value ?? '').trim().toUpperCase()
  return !normalized || normalized === 'N/A'
}

const shouldRenderLink = (column: TableColumn, value: unknown) => {
  return Boolean(column.isLink && value && !isUnavailableValue(value))
}

const shouldRenderUnavailable = (column: TableColumn, value: unknown) => {
  return Boolean(column.isLink && isUnavailableValue(value))
}

const formatCellValue = (value: unknown) => {
  if (value === undefined || value === null || value === '') return '-'
  return String(value)
}

const formatDateTime = (value: unknown) => {
  if (!value) return '-'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const getTotalResult = (row: Record<string, any>) => {
  return row.total_result || row.total_qc_result || ''
}

const hasResult = (row: Record<string, any>) => {
  return !isUnavailableValue(getTotalResult(row))
}

const normalizeResult = (value: unknown) => {
  return String(value || '').trim().toLowerCase()
}

const resultTagType = (value: unknown) => {
  const normalized = normalizeResult(value)
  if (normalized === 'pass' || normalized === 'passed') return 'success'
  if (normalized === 'fail' || normalized === 'failed') return 'danger'
  return 'info'
}

const formatResultText = (value: unknown) => {
  const normalized = normalizeResult(value)
  if (normalized === 'pass' || normalized === 'passed') return 'PASS'
  if (normalized === 'fail' || normalized === 'failed') return 'FAIL'
  return 'N/A'
}

const resolveAnalysisPath = (row: Record<string, any>) => {
  return String(
    row.source_csv_path ||
    row.csv_file_path ||
    row.file_path ||
    row.local_csv_path ||
    row.raw_csv_path ||
    ''
  ).trim()
}

const resolveAnalysisName = (row: Record<string, any>) => {
  return String(
    row.sn ||
    row.serial_number ||
    row.barcode ||
    row.test_tag ||
    row.csv_name ||
    row.csv_link ||
    ''
  ).trim()
}

const openAnalysis = (row: Record<string, any>) => {
  const path = resolveAnalysisPath(row)
  const name = resolveAnalysisName(row)
  router.push({
    path: resolveAnalysisRoute(row),
    query: {
      ...(path ? { path } : {}),
      ...(name ? { name } : {})
    }
  })
}

const resolveAnalysisRoute = (row: Record<string, any>) => {
  const testType = row.test_type || row.test_name || row.upload_config_key || ''
  if (sameTestType(testType, 'Assembly QC')) {
    return '/data/analysis/pipette-assembly-qc'
  }
  return '/data/analysis'
}

const fetchCollections = async () => {
  collectionsLoading.value = true
  try {
    const response = await collectionApi.getCollections()
    collections.value = sortCollections(response.data.collections || [])
    currentPage.value = 1
    await fetchFilterOptions()
    await fetchCollectionData()
  } catch (e: any) {
    ElMessage.error('获取集合列表失败: ' + (e.message || ''))
  } finally {
    collectionsLoading.value = false
  }
}

const fetchFilterOptions = async () => {
  try {
    const response = await collectionApi.getCollectionFilterOptions(selectedCollection.value)
    filterOptions.value = {
      models: response.data.models || [],
      types: response.data.types || [],
      total_results: response.data.total_results || []
    }
  } catch (e: any) {
    filterOptions.value = { models: [], types: [], total_results: [] }
    ElMessage.error('获取筛选项失败: ' + (e.message || ''))
  }
}

const getFilterParams = () => {
  const [startDate, endDate] = filters.value.dateRange || []
  return {
    model: filters.value.model || undefined,
    type: filters.value.type || undefined,
    totalResult: filters.value.totalResult || undefined,
    barcode: filters.value.barcode?.trim() || undefined,
    startDate,
    endDate
  }
}

const fetchCollectionData = async () => {
  dataLoading.value = true
  try {
    const response = await collectionApi.getCollectionData(
      selectedCollection.value, 
      currentPage.value, 
      20,
      getFilterParams()
    )
    tableData.value = response.data.data || []
    total.value = response.data.total || 0
  } catch (e: any) {
    ElMessage.error('获取数据失败: ' + (e.message || ''))
  } finally {
    dataLoading.value = false
  }
}

const resetFilters = () => {
  filters.value = {
    model: '',
    type: '',
    totalResult: '',
    barcode: '',
    dateRange: []
  }
}

const handleCollectionChange = async () => {
  currentPage.value = 1
  resetFilters()
  await fetchFilterOptions()
  fetchCollectionData()
}

const handleFilterSearch = () => {
  currentPage.value = 1
  fetchCollectionData()
}

const handleResetFilters = () => {
  resetFilters()
  handleFilterSearch()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchCollectionData()
}

const handleRefresh = () => {
  fetchCollectionData()
  ElMessage.success('数据已刷新')
}

const fetchUnitTrackerRows = async () => {
  unitTrackerLoading.value = true
  try {
    const response = await uploadRecordApi.getUnitTrackerRows({
      page: unitTrackerPage.value,
      pageSize: unitTrackerPageSize,
      product: unitTrackerFilters.value.product.trim() || undefined,
      testType: unitTrackerFilters.value.testType || undefined,
      barcode: unitTrackerFilters.value.barcode.trim() || undefined
    })
    unitTrackerColumns.value = response.data.columns || []
    unitTrackerRows.value = response.data.rows || []
    unitTrackerTotal.value = response.data.total || 0
    if (response.data.error) {
      ElMessage.warning(response.data.error)
    }
  } catch (error: any) {
    ElMessage.error('获取 Unit Tracker 标准行失败: ' + (error?.message || ''))
  } finally {
    unitTrackerLoading.value = false
  }
}

const syncUnitTrackerRows = async () => {
  unitTrackerSyncing.value = true
  try {
    const response = await uploadRecordApi.syncUnitTrackerRows()
    unitTrackerSyncResult.value = response.data
    ElMessage.success(`标准行更新完成：更新 ${response.data.updated}，跳过 ${response.data.skipped}`)
    unitTrackerPage.value = 1
    await fetchUnitTrackerRows()
  } catch (error: any) {
    const detail = error?.response?.data?.detail
    ElMessage.error('更新 Unit Tracker 标准行失败: ' + (detail?.message || detail || error?.message || ''))
  } finally {
    unitTrackerSyncing.value = false
  }
}

const resetUnitTrackerFilters = () => {
  unitTrackerFilters.value = {
    product: DEFAULT_UNIT_TRACKER_PRODUCT,
    testType: DEFAULT_UNIT_TRACKER_TEST,
    barcode: ''
  }
  unitTrackerSelectedGroups.value = []
  unitTrackerPage.value = 1
  fetchUnitTrackerRows()
}

const handleUnitTrackerPageChange = (page: number) => {
  unitTrackerPage.value = page
  fetchUnitTrackerRows()
}

const unitTrackerCellValue = (row: UnitTrackerRow, key: string) => {
  if (key === 'file_path') return row.file_path || row.row?.file_path
  if (key === 'link') return row.row?.link || row.csv_link
  return row.row?.[key]
}

const unitTrackerAnalysisPath = (row: UnitTrackerRow) => {
  return String(row.file_path || row.row?.file_path || '').trim()
}

const openUnitTrackerAnalysis = (row: UnitTrackerRow) => {
  const path = unitTrackerAnalysisPath(row)
  if (!path) {
    ElMessage.warning('当前标准行没有本地 CSV 缓存路径')
    return
  }
  router.push({
    path: resolveAnalysisRoute({
      test_type: row.test_type,
      source_csv_path: path
    }),
    query: {
      path,
      name: row.sn || row.row?.sn || '',
      barcode: row.sn || row.row?.sn || ''
    }
  })
}

const unitTrackerColumnWidth = (key: string) => {
  if (key === 'file_path') return 260
  if (key === 'link') return 90
  if (key === 'sn') return 180
  if (key === 'operator_name') return 140
  if (key.includes('plunger') || key.includes('jaws')) return 150
  return 110
}

const unitTrackerHeaderClassName = ({ rowIndex, column }: { rowIndex: number; column: any }) => {
  if (rowIndex !== 0) return 'unit-tracker-header unit-tracker-sub-header'
  const className = String(column.className || '')
  const groupClass = className
    .split(/\s+/)
    .find((item) => item.startsWith('unit-tracker-group-'))
  return ['unit-tracker-header', 'unit-tracker-group-header', groupClass].filter(Boolean).join(' ')
}

onMounted(() => {
  fetchCollections()
})
</script>

<style scoped>
.data-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.data-card {
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
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.data-panel-switch {
  --el-border-radius-base: 12px;
  min-height: 34px;
}

.data-panel-switch :deep(.el-segmented__group) {
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
}

.data-panel-switch :deep(.el-segmented__item) {
  min-width: 122px;
  height: 26px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
}

.table-info {
  margin-bottom: 12px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.filter-control {
  width: 140px;
}

.date-filter {
  width: 260px;
}

.barcode-filter {
  width: 170px;
}

.group-filter {
  width: 180px;
}

.unit-tracker-filter {
  margin-top: 0;
}

.unit-tracker-meta {
  color: #606266;
  font-size: 13px;
}

.unit-tracker-alert {
  margin-bottom: 10px;
}

.total-count {
  font-size: 14px;
  color: #909399;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.data-table {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.data-table :deep(.el-table__header th) {
  background: #f8fafc;
  color: #606266;
  font-weight: 600;
}

.data-table :deep(.unit-tracker-header .cell) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-table :deep(.unit-tracker-group-header) {
  color: #1f2937;
}

.data-table :deep(.unit-tracker-sub-header) {
  background: #f8fafc;
  color: #4b5563;
}

.data-table :deep(.unit-tracker-group-info) {
  background: #e8f3ff;
}

.data-table :deep(.unit-tracker-group-sections) {
  background: #ecfdf3;
}

.data-table :deep(.unit-tracker-group-plunger_current_speed) {
  background: #fff4de;
}

.data-table :deep(.unit-tracker-group-jaws_current_speed) {
  background: #fef0f0;
}

.data-table :deep(.unit-tracker-group-capacitance_primary),
.data-table :deep(.unit-tracker-group-capacitance_secondary) {
  background: #f2edff;
}

.data-table :deep(.unit-tracker-group-pressure_primary),
.data-table :deep(.unit-tracker-group-pressure_secondary) {
  background: #e8fbfa;
}

.data-table :deep(.unit-tracker-group-environment_s0),
.data-table :deep(.unit-tracker-group-environment_s1) {
  background: #f0f9e8;
}

.data-table :deep(.unit-tracker-group-tip_sensor) {
  background: #fff7ed;
}

.data-table :deep(.unit-tracker-group-droplets) {
  background: #edf2ff;
}

.data-table :deep(.unit-tracker-group-others) {
  background: #f3f4f6;
}

.data-table :deep(.el-table__cell) {
  padding: 8px 0;
}

.time-cell {
  color: #606266;
  font-variant-numeric: tabular-nums;
}

.link-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  height: 24px;
  padding: 0 9px;
  border: 1px solid #d9ecff;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  line-height: 22px;
  text-decoration: none;
  white-space: nowrap;
}

.link-cell:hover {
  border-color: #409eff;
  background: #e6f1fc;
}

.text-link-cell {
  display: inline-flex;
  max-width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: #409eff;
  font: inherit;
  line-height: inherit;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-link-cell:hover {
  color: #1f6fbd;
  text-decoration: underline;
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
  .date-filter,
  .barcode-filter,
  .filter-control {
    width: 100%;
  }
}
</style>
