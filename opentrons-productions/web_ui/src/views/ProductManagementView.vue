<template>
  <div class="product-management-view">
    <section class="product-toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="filters.barcode"
          class="barcode-input"
          placeholder="条码 / SN / 文件名"
          clearable
          :prefix-icon="Search"
          @keyup.enter="fetchProducts"
          @clear="fetchProducts"
        />
        <el-select
          v-model="filters.model"
          class="filter-select"
          placeholder="产品类型"
          clearable
          filterable
          @change="fetchProducts"
        >
          <el-option v-for="model in filterOptions.models" :key="model" :label="model" :value="model" />
        </el-select>
        <el-select
          v-model="filters.testType"
          class="filter-select"
          placeholder="测试产品"
          clearable
          filterable
          @change="handleTestTypeFilterChange"
        >
          <el-option v-for="testType in testTypeOptions" :key="testType" :label="formatTestType(testType)" :value="testType" />
        </el-select>
        <el-select
          v-model="filters.status"
          class="filter-select"
          placeholder="状态"
          clearable
          filterable
          @change="fetchProducts"
        >
          <el-option v-for="status in productStatusOptions" :key="status" :label="status" :value="status" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="fetchProducts">
          查询
        </el-button>
        <el-button :disabled="!hasFilters" @click="resetFilters">
          重置
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-tooltip content="手动新增产品" placement="top">
          <el-button
            :icon="Plus"
            circle
            aria-label="手动新增产品"
            @click="openManualDialog"
          />
        </el-tooltip>
        <el-tooltip content="同步产品" placement="top">
          <el-button
            :icon="Refresh"
            :loading="syncing"
            circle
            aria-label="同步产品"
            @click="syncProducts"
          />
        </el-tooltip>
      </div>
    </section>

    <el-table
      :data="pagedProducts"
      v-loading="loading"
      stripe
      border
      class="product-table"
      height="calc(100vh - 182px)"
    >
      <el-table-column label="条码" width="220" fixed="left" show-overflow-tooltip>
        <template #default="{ row }">
          <strong>{{ row.barcode }}</strong>
        </template>
      </el-table-column>

      <el-table-column label="Status" width="150">
        <template #default="{ row }">
          <div class="status-cell">
            <el-tag :type="productStatusTagType(row.status)" effect="light">
              {{ row.status }}
            </el-tag>
            <el-dropdown
              trigger="click"
              @command="handleStatusCommand(row, $event)"
            >
              <button class="status-menu-button" type="button" :disabled="statusUpdatingBarcode === row.barcode">
                <el-icon><ArrowDown /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="status in productStatusOptions"
                    :key="status"
                    :command="status"
                    :disabled="status === row.status"
                  >
                    {{ status }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="Productions" width="130">
        <template #default="{ row }">
          {{ row.model }}
        </template>
      </el-table-column>

      <el-table-column label="Type" width="170">
        <template #default="{ row }">
          {{ row.oem }}
        </template>
      </el-table-column>

      <el-table-column label="Test Data" width="190">
        <template #default="{ row }">
          <el-select
            :model-value="row.selectedTestKey"
            class="test-data-select"
            size="small"
            filterable
            @change="handleRowTestChange(row, $event)"
          >
            <el-option
              v-for="test in row.tests"
              :key="test.key"
              :label="formatTestType(test.test_type)"
              :value="test.key"
            >
              <div class="test-option">
                <span>{{ formatTestType(test.test_type) }}</span>
                <el-tag :type="statusTagType(test.status)" size="small" effect="light">
                  {{ test.status }}
                </el-tag>
                <span>{{ formatDateTime(test.date) }}</span>
              </div>
            </el-option>
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="原数据 CSV" min-width="150">
        <template #default="{ row }">
          <a v-if="selectedTest(row)?.csv_link" :href="selectedTest(row)?.csv_link" target="_blank" rel="noopener noreferrer" class="link-button">
            打开
          </a>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column label="数据分析" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            :disabled="!selectedTest(row)?.csv_link && !selectedTest(row)?.source_csv_path"
            @click="openAnalysis(row)"
          >
            分析
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="product-footer">
      <span>产品 {{ filteredProducts.length }} / 上传记录 {{ uploadRecordCount }}</span>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredProducts.length"
        layout="prev, pager, next, total"
      />
    </div>

    <el-dialog v-model="manualDialogVisible" title="手动新增产品" width="520px">
      <el-form
        ref="manualFormRef"
        :model="manualForm"
        :rules="manualRules"
        label-width="112px"
        class="manual-product-form"
      >
        <el-form-item label="条码" prop="barcode">
          <el-input v-model="manualForm.barcode" clearable placeholder="Serial Number / Barcode" />
        </el-form-item>
        <el-form-item label="Status" prop="status">
          <el-select v-model="manualForm.status" class="manual-field" filterable>
            <el-option v-for="status in productStatusOptions" :key="status" :label="status" :value="status" />
          </el-select>
        </el-form-item>
        <el-form-item label="Productions" prop="model">
          <el-select
            v-model="manualForm.model"
            class="manual-field"
            allow-create
            clearable
            default-first-option
            filterable
            placeholder="选择或输入产品"
          >
            <el-option v-for="model in manualModelOptions" :key="model" :label="model" :value="model" />
          </el-select>
        </el-form-item>
        <el-form-item label="Type" prop="oem">
          <el-select
            v-model="manualForm.oem"
            class="manual-field"
            allow-create
            clearable
            default-first-option
            filterable
            placeholder="选择或输入类型"
          >
            <el-option v-for="type in manualTypeOptions" :key="type" :label="type" :value="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="Test Data" prop="test_type">
          <el-select
            v-model="manualForm.test_type"
            class="manual-field"
            allow-create
            clearable
            default-first-option
            filterable
            placeholder="选择或输入测试"
          >
            <el-option v-for="testType in testTypeOptions" :key="testType" :label="formatTestType(testType)" :value="testType" />
          </el-select>
        </el-form-item>
        <el-form-item label="CSV link" prop="csv_link">
          <el-input v-model="manualForm.csv_link" clearable placeholder="https://..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="manualSaving" @click="submitManualProduct">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { productManagementApi } from '@/api'
import { canonicalTestType, formatTestType, sameTestType, uniqueTestTypes } from '@/utils/testNames'
import type { ProductManagementFilterOptionsResponse, ProductManagementItem, ProductManagementTest } from '@/types'

type ProductTest = ProductManagementTest

type ProductRow = {
  barcode: string
  status: string
  model: string
  oem: string
  tests: ProductTest[]
  selectedTestKey: string
  latestDate?: string
  uploadRecordCount?: number
}

const router = useRouter()
const products = ref<ProductRow[]>([])
const loading = ref(false)
const syncing = ref(false)
const manualSaving = ref(false)
const statusUpdatingBarcode = ref('')
const total = ref(0)
const uploadRecordCount = ref(0)
const currentPage = ref(1)
const pageSize = 100
const productPageSize = 2000
const selectedTestKeys = ref<Record<string, string>>({})
const filterOptions = ref<ProductManagementFilterOptionsResponse>({ models: [], statuses: [], test_types: [] })
const filters = ref({
  barcode: '',
  model: '',
  testType: '',
  status: ''
})
const defaultProductStatuses = ['Testing', 'Eng', 'ProductionLine', 'Shipped', 'Scrapped']
const manualDialogVisible = ref(false)
const manualFormRef = ref<FormInstance>()
const manualForm = ref({
  barcode: '',
  status: 'Testing',
  model: '',
  oem: '',
  test_type: '',
  csv_link: ''
})
const manualRules: FormRules = {
  barcode: [{ required: true, message: '请输入条码', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  model: [{ required: true, message: '请输入 Productions', trigger: 'change' }],
  oem: [{ required: true, message: '请输入 Type', trigger: 'change' }],
  test_type: [{ required: true, message: '请输入 Test Data', trigger: 'change' }]
}

const hasFilters = computed(() => Boolean(filters.value.barcode || filters.value.model || filters.value.testType || filters.value.status))
const testTypeOptions = computed(() => uniqueTestTypes(filterOptions.value.test_types?.length
  ? filterOptions.value.test_types
  : products.value.flatMap(product => product.tests.map(test => test.test_type))))
const productStatusOptions = computed(() => filterOptions.value.statuses?.length ? filterOptions.value.statuses : defaultProductStatuses)
const manualModelOptions = computed(() => {
  return Array.from(new Set([
    ...(filterOptions.value.models || []),
    ...products.value.map(product => product.model).filter(value => value && value !== '-')
  ])).sort()
})
const manualTypeOptions = computed(() => {
  return Array.from(new Set(products.value.map(product => product.oem).filter(value => value && value !== '-'))).sort()
})
const filteredProducts = computed(() => {
  return products.value
})
const pagedProducts = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredProducts.value.slice(start, start + pageSize)
})

async function fetchProducts() {
  loading.value = true
  try {
    currentPage.value = 1
    const firstPage = await fetchProductPage(1)
    const nextProducts = (firstPage.products || []).map(buildProductRow)
    total.value = firstPage.total || 0
    if (firstPage.error) {
      ElMessage.warning(firstPage.error)
    }
    const pageCount = Math.ceil((firstPage.total || 0) / productPageSize)
    for (let page = 2; page <= pageCount; page += 1) {
      const pageData = await fetchProductPage(page)
      nextProducts.push(...(pageData.products || []).map(buildProductRow))
      if (pageData.error) {
        ElMessage.warning(pageData.error)
      }
    }
    products.value = nextProducts
    uploadRecordCount.value = nextProducts.reduce((sum, product) => sum + (product.uploadRecordCount || product.tests.length), 0)
  } catch (error: any) {
    ElMessage.error('加载产品数据失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function fetchProductPage(page: number) {
  const response = await productManagementApi.getProducts({
    page,
    pageSize: productPageSize,
    barcode: filters.value.barcode || undefined,
    model: filters.value.model || undefined,
    testType: filters.value.testType || undefined,
    status: filters.value.status || undefined
  })
  return response.data
}

async function fetchFilterOptions() {
  try {
    const response = await productManagementApi.getFilterOptions()
    filterOptions.value = response.data
  } catch (error) {
    filterOptions.value = { models: [], statuses: defaultProductStatuses, test_types: [] }
  }
}

function resetFilters() {
  filters.value = { barcode: '', model: '', testType: '', status: '' }
  currentPage.value = 1
  fetchProducts()
}

function handleTestTypeFilterChange() {
  currentPage.value = 1
  const nextSelected: Record<string, string> = { ...selectedTestKeys.value }
  for (const product of products.value) {
    const selected = filters.value.testType
      ? product.tests.find(test => sameTestType(test.test_type, filters.value.testType))
      : product.tests[0]
    if (selected) {
      nextSelected[product.barcode] = selected.key
    }
  }
  selectedTestKeys.value = nextSelected
  fetchProducts()
}

function buildProductRow(product: ProductManagementItem): ProductRow {
  const row = {
    barcode: displayValue(product.barcode),
    status: displayValue(product.status || 'Testing'),
    model: displayValue(product.model),
    oem: displayValue(product.oem),
    tests: (product.tests || [])
      .map(test => ({
        ...test,
        test_type: canonicalTestType(test.test_type),
        key: String(test.key || test.upload_record_id || `${test.test_type}-${test.date}`),
        csv_link: normalizeLink(test.csv_link),
        source_csv_path: normalizePath(test.source_csv_path)
      }))
      .filter(test => Boolean(test.test_type)),
    selectedTestKey: '',
    latestDate: String(product.latest_date || ''),
    uploadRecordCount: Number(product.upload_record_count || product.tests?.length || 0)
  }
  row.tests.sort((left, right) => String(right.date || '').localeCompare(String(left.date || '')))
  row.selectedTestKey = resolveInitialSelectedTestKey(row)
  return row
}

function openAnalysis(row: ProductRow) {
  const test = selectedTest(row)
  if (!test?.csv_link && !test?.source_csv_path) return
  const analysisPath = getAnalysisPath(test.test_type)
  router.push({
    path: analysisPath,
    query: {
      ...(test.csv_link
        ? {
            barcode: row.barcode,
            test: test.key,
            csv_link: test.csv_link
          }
        : { path: test.source_csv_path }),
      name: row.barcode
    }
  })
}

function getAnalysisPath(testType?: string) {
  if (sameTestType(testType, 'Assembly QC')) {
    return '/data/analysis/pipette-assembly-qc'
  }
  return '/data/analysis'
}

function selectedTest(row: ProductRow) {
  return row.tests.find(test => test.key === row.selectedTestKey) || row.tests[0] || null
}

function handleRowTestChange(row: ProductRow, value: unknown) {
  const key = String(value)
  row.selectedTestKey = key
  selectedTestKeys.value = {
    ...selectedTestKeys.value,
    [row.barcode]: key
  }
}

async function syncProducts() {
  syncing.value = true
  try {
    const response = await productManagementApi.syncProducts()
    const data = response.data
    ElMessage.success(`同步完成：产品 ${data.total_products}，来源记录 ${data.source_records}`)
    await fetchFilterOptions()
    await fetchProducts()
  } catch (error: any) {
    ElMessage.error('同步产品失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
  } finally {
    syncing.value = false
  }
}

async function updateProductStatus(row: ProductRow, status: string) {
  if (!status || status === row.status) return
  const previous = row.status
  row.status = status
  statusUpdatingBarcode.value = row.barcode
  try {
    const response = await productManagementApi.updateStatus(row.barcode, status)
    if (!response.data.success) {
      throw new Error(response.data.error || '状态更新失败')
    }
    ElMessage.success('状态已更新')
  } catch (error: any) {
    row.status = previous
    ElMessage.error('更新状态失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
  } finally {
    statusUpdatingBarcode.value = ''
  }
}

function openManualDialog() {
  manualForm.value = {
    barcode: '',
    status: 'Testing',
    model: '',
    oem: '',
    test_type: '',
    csv_link: ''
  }
  manualDialogVisible.value = true
}

async function submitManualProduct() {
  if (!manualFormRef.value) return
  await manualFormRef.value.validate(async valid => {
    if (!valid) return
    manualSaving.value = true
    try {
      const payload = {
        barcode: manualForm.value.barcode.trim(),
        status: manualForm.value.status,
        model: manualForm.value.model.trim(),
        oem: manualForm.value.oem.trim(),
        test_type: canonicalTestType(manualForm.value.test_type),
        csv_link: manualForm.value.csv_link.trim() || undefined,
        source_csv_path: manualForm.value.csv_link.trim() || undefined
      }
      const response = await productManagementApi.addManual(payload)
      ElMessage.success(response.data.created_product ? '产品已新增' : '测试数据已新增')
      manualDialogVisible.value = false
      await fetchFilterOptions()
      await fetchProducts()
    } catch (error: any) {
      ElMessage.error('手动新增失败: ' + (error?.response?.data?.detail || error?.message || '未知错误'))
    } finally {
      manualSaving.value = false
    }
  })
}

function handleStatusCommand(row: ProductRow, value: unknown) {
  updateProductStatus(row, String(value))
}

function resolveInitialSelectedTestKey(row: ProductRow) {
  const persisted = selectedTestKeys.value[row.barcode]
  if (persisted && row.tests.some(test => test.key === persisted)) {
    return persisted
  }
  if (filters.value.testType) {
    const matched = row.tests.find(test => sameTestType(test.test_type, filters.value.testType))
    if (matched) return matched.key
  }
  return row.selectedTestKey || row.tests[0]?.key || ''
}

function statusTagType(status: string) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

function productStatusTagType(status: string) {
  if (status === 'Testing') return 'warning'
  if (status === 'Shipped') return 'success'
  if (status === 'Scrapped') return 'danger'
  if (status === 'ProductionLine') return 'primary'
  if (status === 'Eng') return 'info'
  return 'info'
}

function formatDateTime(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function displayValue(value: unknown) {
  const text = String(value ?? '').trim()
  if (!text || text.toUpperCase() === 'N/A' || text.toUpperCase() === 'NA' || text === 'None') return '-'
  return text
}

function normalizeLink(value: unknown) {
  const text = displayValue(value)
  return text === '-' ? '' : text
}

function normalizePath(value: unknown) {
  const text = displayValue(value)
  return text === '-' ? '' : text
}

onMounted(() => {
  fetchFilterOptions()
  fetchProducts()
})

watch(filteredProducts, () => {
  const maxPage = Math.max(1, Math.ceil(filteredProducts.value.length / pageSize))
  if (currentPage.value > maxPage) {
    currentPage.value = maxPage
  }
})
</script>

<style scoped>
.product-management-view {
  height: 100%;
  overflow: hidden;
  background: #f8fafc;
}

.product-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #dfe5ee;
  background: #fff;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0;
}

.toolbar-left > * + *,
.toolbar-right > * + * {
  margin-left: 10px;
}

.barcode-input {
  width: 260px;
}

.filter-select {
  width: 180px;
}

.product-table :deep(.el-table__cell .cell) {
  text-align: center;
}

.status-cell {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.status-menu-button {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 11px;
}

.status-menu-button:hover {
  color: #2563eb;
}

.status-menu-button:disabled {
  color: #cbd5e1;
  cursor: wait;
}

.manual-product-form {
  padding-right: 8px;
}

.manual-field {
  width: 100%;
}

.test-data-select {
  width: 100%;
}

.test-data-select :deep(.el-select__selected-item),
.test-data-select :deep(.el-select__placeholder),
.test-data-select :deep(.el-input__inner) {
  text-align: center;
}

.test-option {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 72px 138px;
  align-items: center;
  gap: 8px;
  text-align: center;
  color: #334155;
  font-size: 12px;
}

.test-option span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-button {
  color: #2563eb;
  font-size: 13px;
  text-decoration: none;
}

.link-button:hover {
  text-decoration: underline;
}

.product-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 0;
  border-top: 1px solid #dfe5ee;
  background: #fff;
  color: #64748b;
  font-size: 13px;
}
</style>
