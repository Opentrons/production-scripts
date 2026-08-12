<template>
  <div class="diagnostic-analysis-view">
    <div class="analysis-mode-bar">
      <el-button-group>
        <el-button :type="analysisMode === 'local' ? 'primary' : 'default'" @click="analysisMode = 'local'">
          {{ t('analysis.common.local') }}
        </el-button>
        <el-button :type="analysisMode === 'online' ? 'primary' : 'default'" @click="analysisMode = 'online'">
          {{ t('analysis.common.online') }}
        </el-button>
      </el-button-group>
    </div>

    <section v-if="analysisMode === 'local' || activeAnalysis" class="analysis-body">
      <div v-if="!activeAnalysis && !loading" class="upload-stage">
        <div class="upload-panel">
          <el-upload
            ref="uploadRef"
            class="analysis-upload"
            drag
            multiple
            accept=".csv,text/csv"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleFileChange"
          >
            <div class="upload-empty-content">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-title">{{ t('analysis.diagnostic.uploadTitle') }}</div>
              <div class="upload-subtitle">{{ t('analysis.diagnostic.uploadSubtitle') }}</div>
            </div>
          </el-upload>

          <div class="local-actions">
            <div v-if="selectedFiles.length" class="file-queue">
              <el-tag
                v-for="file in selectedFiles"
                :key="`${file.name}-${file.size}-${file.lastModified}`"
                closable
                @close="removeFile(file.name)"
              >
                {{ file.name }}
              </el-tag>
            </div>
            <div class="action-buttons">
              <el-button type="primary" :icon="Histogram" :loading="loading" :disabled="!selectedFiles.length" @click="analyzeSelectedFiles">
                {{ t('analysis.common.analyze') }}
              </el-button>
              <el-button :icon="Delete" :disabled="!selectedFiles.length || loading" @click="clearAnalysis">
                {{ t('analysis.common.clear') }}
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loadMessage" class="hint-line">{{ loadMessage }}</div>

      <template v-if="activeAnalysis">
        <div class="result-toolbar">
          <div class="result-title">
            <el-tooltip :content="t('analysis.common.backToUpload')" placement="bottom">
              <el-button class="back-button" :icon="ArrowLeft" circle @click="clearAnalysis" />
            </el-tooltip>
            <strong>{{ activeAnalysis.file?.name || t('analysis.diagnostic.resultTitle') }}</strong>
          </div>
          <el-select v-if="analyses.length > 1" v-model="selectedAnalysisIndex" class="result-select">
            <el-option
              v-for="(item, index) in analyses"
              :key="item.file?.path || item.file?.name || index"
              :label="item.file?.name || t('analysis.common.analysisIndex', { index: index + 1 })"
              :value="index"
            />
          </el-select>
        </div>

        <div class="result-strip" :class="activeAnalysis.passed ? 'is-pass' : 'is-fail'">
          <div class="result-status">
            <el-icon>
              <CircleCheck v-if="activeAnalysis.passed" />
              <CircleClose v-else />
            </el-icon>
            <strong>{{ activeAnalysis.passed ? 'PASS' : 'FAIL' }}</strong>
          </div>
          <ol v-if="!activeAnalysis.passed && failures.length" class="failure-list">
            <li v-for="failure in failures" :key="failure">{{ failure }}</li>
          </ol>
        </div>

        <section class="meta-section">
          <div class="section-header">
            <div class="section-title">
              <h2>Meta Data</h2>
              <el-tooltip :content="tableDescription('metadata')" placement="top" popper-class="table-info-tooltip">
                <el-icon class="table-info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </div>
          <el-table :data="metadataRows" size="small" border>
            <el-table-column prop="label" :label="t('analysis.diagnostic.field')" min-width="160" />
            <el-table-column prop="value" :label="t('analysis.diagnostic.value')" min-width="220">
              <template #default="{ row }">{{ formatCell(row.value) }}</template>
            </el-table-column>
          </el-table>
        </section>

        <section class="overview-section">
          <div class="section-header">
            <div class="section-title">
              <h2>Section Results</h2>
              <el-tooltip :content="tableDescription('section_results')" placement="top" popper-class="table-info-tooltip">
                <el-icon class="table-info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
          </div>
          <div class="section-result-table-scroll">
            <table class="section-result-table">
              <tbody>
                <tr>
                  <th v-for="section in sectionResults" :key="section.section">
                    {{ section.label || section.section }}
                  </th>
                </tr>
                <tr>
                  <td
                    v-for="section in sectionResults"
                    :key="`${section.section}-status`"
                    :class="sectionStatusClass(section.status)"
                  >
                    {{ section.status || 'N/A' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="testMatrices.length" class="matrix-section">
          <div
            v-for="matrix in testMatrices"
            :key="matrix.key"
            class="matrix-panel"
          >
            <div class="section-header">
              <div class="section-title">
                <h2>{{ matrix.title }}</h2>
                <el-tooltip :content="matrixDescription(matrix)" placement="top" popper-class="table-info-tooltip">
                  <el-icon class="table-info-icon"><InfoFilled /></el-icon>
                </el-tooltip>
              </div>
            </div>
            <div class="matrix-scroll">
              <table class="diagnostic-matrix">
                <thead>
                  <tr>
                    <th></th>
                    <th v-for="column in matrix.columns" :key="column.key">
                      {{ column.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in matrix.rows" :key="row.key">
                    <th>{{ row.label }}</th>
                    <td v-for="(cell, index) in row.values" :key="`${row.key}-${index}`">
                      <el-tag :type="statusTagType(cell.status)" effect="light">
                        {{ cell.status || 'N/A' }}
                      </el-tag>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section class="detail-section">
          <div class="section-header section-header-controls">
            <div class="section-title">
              <h2>Test Details</h2>
              <el-tooltip :content="selectedSectionDescription()" placement="top" popper-class="table-info-tooltip">
                <el-icon class="table-info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="section-header-actions">
              <el-select v-model="selectedSectionKey" size="small" class="section-select">
                <el-option
                  v-for="section in testSections"
                  :key="section.section"
                  :label="section.label || section.section"
                  :value="section.section"
                />
              </el-select>
            </div>
          </div>
          <el-table :data="selectedSectionRows" size="small" border>
            <el-table-column prop="label" label="Test" min-width="220" />
            <el-table-column prop="actual" label="Actual" min-width="100" align="center">
              <template #default="{ row }">{{ formatMetric(row.actual) }}</template>
            </el-table-column>
            <el-table-column prop="target" label="Target" min-width="100" align="center">
              <template #default="{ row }">{{ formatMetric(row.target ?? row.spec?.target) }}</template>
            </el-table-column>
            <el-table-column label="Spec" min-width="150" align="center">
              <template #default="{ row }">{{ formatSpec(row.spec) }}</template>
            </el-table-column>
            <el-table-column prop="status" label="Result" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" effect="light">
                  {{ row.status || 'N/A' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </template>

      <el-alert
        v-if="analysisErrors.length"
        class="analysis-error"
        type="error"
        :closable="false"
        show-icon
      >
        <template #title>
          {{ analysisErrors.map(item => `${item.file?.name || 'CSV'}: ${item.message}`).join('；') }}
        </template>
      </el-alert>
    </section>

    <section v-else class="online-analysis">
      <div class="online-panel">
        <div class="online-controls">
          <el-select
            v-model="onlineFilters.product"
            class="online-product-select"
            :placeholder="t('analysis.common.product')"
            filterable
            :loading="onlineProductsLoading"
            @change="handleOnlineProductChange"
          >
            <el-option
              v-for="product in onlineProductNameOptions"
              :key="product"
              :label="product"
              :value="product"
            />
          </el-select>
          <el-select
            v-model="onlineFilters.test"
            class="online-test-select"
            :placeholder="t('analysis.common.test')"
            filterable
            :disabled="!onlineTestOptions.length"
            @change="handleOnlineTestChange"
          >
            <el-option
              v-for="testType in onlineTestOptions"
              :key="testType"
              :label="formatTestType(testType)"
              :value="testType"
            />
          </el-select>
          <el-select
            v-model="onlineFilters.sn"
            class="online-sn-select"
            placeholder="SN"
            filterable
            :disabled="!onlineSnOptions.length"
            @change="handleOnlineSnChange"
          >
            <el-option
              v-for="product in onlineSnOptions"
              :key="product.barcode"
              :label="product.barcode"
              :value="product.barcode"
            >
              <div class="online-product-option">
                <span>{{ product.barcode }}</span>
                <span>{{ formatOnlineProductUpdatedAt(product, 'short') }}</span>
              </div>
            </el-option>
          </el-select>
          <el-popover placement="bottom" trigger="click" width="420">
            <div class="csv-link-editor">
              <el-input
                v-model="onlineManualCsvLink"
                clearable
                :placeholder="t('analysis.common.csvLinkPlaceholder')"
              />
              <div class="csv-link-hint">{{ t('analysis.common.csvLinkHint') }}</div>
            </div>
            <template #reference>
              <el-button class="csv-link-button" :icon="EditPen" :disabled="!canEditOnlineCsvLink" />
            </template>
          </el-popover>
          <el-button
            type="primary"
            :icon="Search"
            :loading="loading"
            :disabled="!onlineFilters.product || !onlineFilters.test || !effectiveOnlineCsvLink"
            @click="analyzeOnlineSelection"
          >
            {{ t('analysis.common.analyze') }}
          </el-button>
        </div>
        <div v-if="loadMessage" class="hint-line">{{ loadMessage }}</div>
        <el-alert
          v-if="onlineFilters.product && onlineFilters.test && !effectiveOnlineCsvLink"
          type="warning"
          :closable="false"
          show-icon
          :title="t('analysis.common.noCsvLink')"
        />
        <el-empty v-if="!loading" :description="t('analysis.common.onlineEmpty')" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import type { UploadFile, UploadInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { ArrowLeft, CircleCheck, CircleClose, Delete, EditPen, Histogram, InfoFilled, Search, UploadFilled } from '@element-plus/icons-vue'
import { dataAnalysisApi, productManagementApi } from '@/scripts/api'
import { canonicalTestType, formatTestType, sameTestType, uniqueTestTypes } from '@/scripts/utils/testNames'
import { useAppLocale } from '@/i18n'
import type {
  DataAnalysisDiagnosticSection,
  DataAnalysisItem,
  DataAnalysisResponse,
  ProductManagementItem,
  ProductManagementTest
} from '@/scripts/types'

type AnalysisMode = 'local' | 'online'

const route = useRoute()
const { t } = useI18n()
const { locale } = useAppLocale()
const analysisMode = ref<AnalysisMode>('local')
const loading = ref(false)
const selectedFiles = ref<File[]>([])
const analyses = ref<DataAnalysisItem[]>([])
const analysisErrors = ref<DataAnalysisResponse['errors']>([])
const selectedAnalysisIndex = ref(0)
const selectedSectionKey = ref('')
const loadMessage = ref('')
const uploadRef = ref<UploadInstance>()
const onlineProductsLoading = ref(false)
const onlineProductOptions = ref<ProductManagementItem[]>([])
const onlineFilters = ref({ product: '', test: '', sn: '' })
const onlineManualCsvLink = ref('')

const activeAnalysis = computed(() => analyses.value[selectedAnalysisIndex.value] || null)
const failures = computed(() => activeAnalysis.value?.summary?.failures || [])
const metadataRows = computed(() => activeAnalysis.value?.metadata_table || [])
const sectionResults = computed(() => activeAnalysis.value?.section_results || [])
const testSections = computed<DataAnalysisDiagnosticSection[]>(() => activeAnalysis.value?.test_sections || [])
const testMatrices = computed(() => activeAnalysis.value?.test_matrices || [])
const selectedSection = computed(() => {
  return testSections.value.find(section => section.section === selectedSectionKey.value) || testSections.value[0] || null
})
const selectedSectionRows = computed(() => selectedSection.value?.rows || [])
const onlineProductNameOptions = computed(() => {
  return Array.from(new Set(
    onlineProductOptions.value
      .map(product => onlineProductName(product))
      .filter(Boolean)
  )).sort()
})
const onlineTestOptions = computed(() => {
  return uniqueTestTypes(onlineProductOptions.value.flatMap(product => (product.tests || []).map(test => test.test_type)))
})
const onlineSnOptions = computed(() => {
  return onlineProductOptions.value
    .filter(product => productMatchesOnlineFilter(product))
    .filter(product => Boolean(findOnlineTest(product)))
    .sort((left, right) => String(right.latest_date || '').localeCompare(String(left.latest_date || '')))
})
const selectedOnlineProduct = computed(() => {
  return onlineSnOptions.value.find(product => product.barcode === onlineFilters.value.sn) ||
    onlineProductOptions.value.find(product => product.barcode === onlineFilters.value.product && Boolean(findOnlineTest(product))) ||
    null
})
const selectedOnlineTest = computed(() => {
  return findOnlineTest(selectedOnlineProduct.value)
})
const canEditOnlineCsvLink = computed(() => Boolean(onlineFilters.value.product && onlineFilters.value.test))
const effectiveOnlineCsvLink = computed(() => {
  if (!canEditOnlineCsvLink.value) return ''
  return onlineManualCsvLink.value.trim() || getOnlineTestCsvLink(selectedOnlineTest.value)
})

function productMatchesOnlineFilter(product: ProductManagementItem) {
  if (!onlineFilters.value.product) return true
  return onlineProductName(product) === onlineFilters.value.product || product.barcode === onlineFilters.value.product
}

function findOnlineTest(product?: ProductManagementItem | null) {
  const matches = (product?.tests || []).filter(test => sameTestType(test.test_type, onlineFilters.value.test))
  return matches.find(test => Boolean(getOnlineTestCsvLink(test))) || matches[0] || null
}

function getOnlineTestCsvLink(test?: ProductManagementTest | null) {
  const csvLink = String(test?.csv_link || '').trim()
  if (csvLink) return csvLink
  const sourcePath = String(test?.source_csv_path || '').trim()
  return /^https?:\/\//i.test(sourcePath) ? sourcePath : ''
}

const sectionDescriptionKeys: Record<string, string> = {
  PLUNGER: 'plunger', JAWS: 'jaws', CAPACITANCE: 'capacitance', PRESSURE: 'pressure',
  'ENVIRONMENT-SENSOR': 'environmentSensor', 'TIP-SENSOR': 'tipSensor', DROPLETS: 'droplets', ENCODER: 'encoder'
}

function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return
  const existingIndex = selectedFiles.value.findIndex(item => item.name === file.name)
  if (existingIndex >= 0) {
    selectedFiles.value.splice(existingIndex, 1, file)
  } else {
    selectedFiles.value.push(file)
  }
}

function removeFile(fileName: string) {
  selectedFiles.value = selectedFiles.value.filter(file => file.name !== fileName)
  if (!selectedFiles.value.length) clearAnalysis()
}

function clearAnalysis() {
  selectedFiles.value = []
  analyses.value = []
  analysisErrors.value = []
  selectedAnalysisIndex.value = 0
  selectedSectionKey.value = ''
  loadMessage.value = ''
  uploadRef.value?.clearFiles()
}

async function analyzeSelectedFiles() {
  if (!selectedFiles.value.length) return
  loading.value = true
  try {
    const response = await dataAnalysisApi.analyzeFiles(selectedFiles.value)
    applyAnalysisResponse(response.data)
    if (analyses.value.length) {
      ElMessage.success(t('analysis.messages.completed'))
    } else {
      ElMessage.warning(t('analysis.messages.noDiagnosticResult'))
    }
  } catch (error: any) {
    ElMessage.error(t('analysis.messages.failed', { error: formatError(error) }))
  } finally {
    loading.value = false
  }
}

async function analyzePath(filePath: string) {
  loading.value = true
  loadMessage.value = t('analysis.messages.analyzing', { file: filePath })
  try {
    const response = await dataAnalysisApi.analyzePaths([filePath])
    applyAnalysisResponse(response.data)
    loadMessage.value = ''
  } catch (error: any) {
    loadMessage.value = ''
    ElMessage.error(t('analysis.messages.failed', { error: formatError(error) }))
  } finally {
    loading.value = false
  }
}

async function analyzeOnlineSelection() {
  const product = selectedOnlineProduct.value
  const testType = canonicalTestType(onlineFilters.value.test)
  const csvLink = effectiveOnlineCsvLink.value
  if (!onlineFilters.value.product || !testType || !csvLink) return
  loading.value = true
  loadMessage.value = t('analysis.messages.reading', { product: product?.barcode || onlineFilters.value.product, test: formatTestType(testType) })
  try {
    const response = await dataAnalysisApi.analyzeOnline({
      barcode: product?.barcode || '',
      product: product?.model || onlineFilters.value.product,
      test_type: testType,
      csv_link: csvLink
    })
    applyAnalysisResponse(response.data)
    loadMessage.value = ''
    if (analyses.value.length) {
      ElMessage.success(t('analysis.messages.onlineCompleted'))
    } else {
      ElMessage.warning(t('analysis.messages.noDiagnosticResult'))
    }
  } catch (error: any) {
    loadMessage.value = ''
    ElMessage.error(t('analysis.messages.onlineFailed', { error: formatError(error) }))
  } finally {
    loading.value = false
  }
}

async function loadOnlineProducts() {
  onlineProductsLoading.value = true
  try {
    const response = await productManagementApi.getProducts({ page: 1, pageSize: 2000 })
    onlineProductOptions.value = response.data.products || []
    if (onlineFilters.value.product) handleOnlineProductChange()
  } catch (error: any) {
    ElMessage.error(t('analysis.messages.loadProductsFailed', { error: formatError(error) }))
  } finally {
    onlineProductsLoading.value = false
  }
}

function handleOnlineProductChange() {
  const normalizedTest = canonicalTestType(onlineFilters.value.test)
  if (!onlineTestOptions.value.includes(normalizedTest)) {
    onlineFilters.value.test = onlineTestOptions.value[0] || ''
  } else {
    onlineFilters.value.test = normalizedTest
  }
  handleOnlineTestChange()
}

function handleOnlineTestChange() {
  if (!onlineSnOptions.value.some(product => product.barcode === onlineFilters.value.sn)) {
    onlineFilters.value.sn = onlineSnOptions.value[0]?.barcode || ''
  }
  syncManualCsvLink()
}

function handleOnlineSnChange() {
  syncManualCsvLink()
}

function syncManualCsvLink() {
  onlineManualCsvLink.value = ''
}

function applyAnalysisResponse(data: DataAnalysisResponse) {
  const unsupportedAnalyses = (data.analyses || []).filter(item => !isPipetteAssemblyQcAnalysis(item))
  analyses.value = (data.analyses || []).filter(isPipetteAssemblyQcAnalysis)
  analysisErrors.value = data.errors || []
  if (unsupportedAnalyses.length > 0 && analyses.value.length === 0) {
    analysisErrors.value = [
      ...analysisErrors.value,
      ...unsupportedAnalyses.map(item => ({
        file: item.file,
        message: t('analysis.diagnostic.unsupported', { test: item.channel_label || item.channel || t('analysis.common.thisTest') })
      }))
    ]
  }
  selectedAnalysisIndex.value = 0
  selectedSectionKey.value = analyses.value[0]?.test_sections?.[0]?.section || ''
}

function isPipetteAssemblyQcAnalysis(item: DataAnalysisItem) {
  return item.view_key === 'pipette_assembly_qc' || item.channel === 'pipette_assembly_qc'
}

function tableDescription(key: 'metadata' | 'section_results') {
  if (key === 'metadata') {
    return t('analysis.diagnostic.descriptions.metadata')
  }
  return t('analysis.diagnostic.descriptions.sectionResults')
}

function matrixDescription(matrix: { section?: string; title?: string; description?: string }) {
  return matrix.description || sectionDescription(matrix.section, matrix.title)
}

function selectedSectionDescription() {
  const section = selectedSection.value
  if (!section) return t('analysis.diagnostic.descriptions.currentSection')
  return sectionDescription(section.section, section.label)
}

function sectionDescription(section?: string, label?: string) {
  const key = String(section || '').toUpperCase()
  const descriptionKey = sectionDescriptionKeys[key]
  if (descriptionKey) return t(`analysis.diagnostic.sections.${descriptionKey}`)
  const name = label || section || t('analysis.diagnostic.currentTest')
  return t('analysis.diagnostic.descriptions.generic', { name })
}

function statusTagType(status?: string | null) {
  const normalized = String(status || '').toUpperCase()
  if (normalized === 'PASS') return 'success'
  if (normalized === 'FAIL') return 'danger'
  return 'info'
}

function sectionStatusClass(status?: string | null) {
  const normalized = String(status || '').toUpperCase()
  if (normalized === 'PASS') return 'is-pass'
  if (normalized === 'FAIL') return 'is-fail'
  return 'is-na'
}

function formatMetric(value: unknown) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return ''
  return Number(numeric.toFixed(4)).toLocaleString(locale.value, { maximumFractionDigits: 4 })
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function formatSpec(spec?: Record<string, any>) {
  if (!spec) return ''
  const parts = []
  if (spec.min !== null && spec.min !== undefined) parts.push(`Min ${formatMetric(spec.min)}`)
  if (spec.max !== null && spec.max !== undefined) parts.push(`Max ${formatMetric(spec.max)}`)
  if (spec.expected !== null && spec.expected !== undefined && spec.expected !== '') parts.push(`Expected ${spec.expected}`)
  return parts.join(' / ')
}

function formatError(error: any) {
  return error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || t('errors.unknown')
}

function onlineProductName(product: ProductManagementItem) {
  const model = String(product.model || '').trim()
  return model && model !== '-' ? model : ''
}

function formatOnlineProductUpdatedAt(product: ProductManagementItem, mode: 'full' | 'short' = 'full') {
  const formattedDate = formatOnlineDate(product.latest_date || latestTestDate(product.tests))
  if (!formattedDate) return ''
  return t(mode === 'short' ? 'analysis.common.updated' : 'analysis.common.lastUpdated', { time: formattedDate })
}

function latestTestDate(tests?: ProductManagementTest[]) {
  if (!tests?.length) return ''
  return tests
    .map(test => test.date || '')
    .filter(Boolean)
    .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0] || ''
}

function formatOnlineDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleString(locale.value, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/\//g, '/')
  }
  return value
}

function isAssemblyQcTest(testType?: string) {
  const normalized = String(testType || '').toLowerCase().replace(/[^a-z0-9]+/g, '')
  return normalized.includes('assemblyqc') || normalized.includes('assembly')
}

function syncSectionSelection() {
  if (!testSections.value.length) {
    selectedSectionKey.value = ''
    return
  }
  const exists = testSections.value.some(section => section.section === selectedSectionKey.value)
  if (!exists) selectedSectionKey.value = testSections.value[0].section
}

function handleInitialRoute() {
  const path = typeof route.query.path === 'string' ? route.query.path : ''
  const barcode = typeof route.query.barcode === 'string' ? route.query.barcode : ''
  const testKey = typeof route.query.test === 'string' ? route.query.test : ''
  const csvLink = typeof route.query.csv_link === 'string' ? route.query.csv_link : ''
  if (barcode || testKey || csvLink) {
    analysisMode.value = 'online'
    loadOnlineProducts().then(() => {
      const routedProduct = onlineProductOptions.value.find(product => product.barcode === barcode)
      if (routedProduct) {
        onlineFilters.value.product = onlineProductName(routedProduct)
        const routedTest = routedProduct.tests.find(test => test.key === testKey) ||
          routedProduct.tests.find(test => sameTestType(test.test_type, testKey))
        onlineFilters.value.test = canonicalTestType(routedTest?.test_type || testKey) || onlineTestOptions.value[0] || ''
        onlineFilters.value.sn = routedProduct.barcode
      } else {
        onlineFilters.value.product = onlineProductNameOptions.value[0] || ''
        handleOnlineProductChange()
      }
      onlineManualCsvLink.value = csvLink
    })
    return
  }
  if (path) {
    analysisMode.value = 'local'
    analyzePath(path)
  }
}

watch(activeAnalysis, () => {
  syncSectionSelection()
})
watch(analysisMode, (mode) => {
  if (mode === 'online' && !onlineProductOptions.value.length) {
    loadOnlineProducts()
  }
})

onMounted(() => {
  handleInitialRoute()
})
</script>

<style scoped>
.diagnostic-analysis-view {
  min-height: 100%;
  background: #f7f9fc;
}

.analysis-mode-bar {
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 16px;
  border-bottom: 1px solid #dfe5ef;
  background: #fff;
}

.analysis-body,
.online-analysis {
  min-height: calc(100vh - 48px);
}

.upload-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 96px);
}

.upload-panel {
  width: min(460px, calc(100vw - 48px));
}

.analysis-upload {
  width: 100%;
}

.upload-empty-content {
  display: flex;
  min-height: 210px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-icon {
  color: #409eff;
  font-size: 42px;
}

.upload-title {
  margin-top: 12px;
  color: #1f2937;
  font-size: 16px;
  font-weight: 700;
}

.upload-subtitle {
  margin-top: 6px;
  color: #7b8794;
  font-size: 13px;
}

.local-actions {
  padding-top: 10px;
}

.file-queue {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.action-buttons,
.online-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hint-line {
  padding: 10px 16px;
  color: #607087;
  font-size: 13px;
}

.result-toolbar,
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  padding: 0 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.result-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.back-button {
  flex: 0 0 auto;
}

.result-select {
  width: 320px;
}

.result-strip {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.result-strip.is-pass {
  color: #16794c;
}

.result-strip.is-fail {
  color: #b42318;
}

.result-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
}

.failure-list {
  margin: 2px 0 0;
  color: #b42318;
}

.meta-section,
.overview-section,
.matrix-panel,
.detail-section {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 8px rgba(15, 23, 42, 0.05);
}

.section-result-table-scroll {
  overflow-x: auto;
  padding: 10px;
}

.section-result-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  table-layout: fixed;
}

.section-result-table th,
.section-result-table td {
  height: 40px;
  padding: 6px 8px;
  border: 1px solid #e4e7ed;
  text-align: center;
  vertical-align: middle;
}

.section-result-table th {
  background: #f7f9fc;
  color: #344054;
  font-size: 12px;
  font-weight: 700;
}

.section-result-table td {
  font-size: 13px;
  font-weight: 700;
}

.section-result-table td.is-pass {
  background: #f0faf4;
  color: #16794c;
}

.section-result-table td.is-fail {
  background: #fff5f5;
  color: #b42318;
}

.section-result-table td.is-na {
  background: #fbfcff;
  color: #667085;
}

.matrix-section {
  display: grid;
  gap: 10px;
  padding: 10px;
}

.matrix-scroll {
  overflow-x: auto;
}

.diagnostic-matrix {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  table-layout: fixed;
}

.diagnostic-matrix th,
.diagnostic-matrix td {
  height: 42px;
  padding: 6px 8px;
  border: 1px solid #e4e7ed;
  text-align: center;
  vertical-align: middle;
}

.diagnostic-matrix thead th {
  background: #f7f9fc;
  color: #344054;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
}

.diagnostic-matrix tbody th {
  width: 120px;
  background: #fbfcff;
  color: #1f2937;
  font-weight: 700;
}

.detail-section {
  margin: 10px 10px 20px;
}

.section-header h2 {
  margin: 0;
  color: #1f2937;
  font-size: 15px;
  font-weight: 700;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.section-header-controls {
  gap: 12px;
}

.section-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-select {
  width: 220px;
}

.table-info-icon {
  flex: 0 0 auto;
  color: #98a2b3;
  cursor: help;
  font-size: 16px;
  transition: color 0.15s ease;
}

.table-info-icon:hover {
  color: #409eff;
}

:global(.table-info-tooltip) {
  max-width: 320px;
  line-height: 1.5;
}

.analysis-error {
  margin: 10px;
}

.online-panel {
  padding: 10px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.online-product-select {
  width: 380px;
}

.online-test-select {
  width: 220px;
}

.online-sn-select {
  width: 300px;
}

.csv-link-editor {
  display: grid;
  gap: 8px;
}

.csv-link-hint {
  color: #667085;
  font-size: 12px;
}

.csv-link-button {
  flex: 0 0 auto;
}

.online-product-option {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.online-product-option span:first-child {
  font-weight: 700;
}

.online-product-option span:last-child {
  color: #667085;
  font-size: 12px;
}

:deep(.el-table th.el-table__cell),
:deep(.el-table td.el-table__cell) {
  text-align: center;
}

@media (max-width: 960px) {
  .online-controls {
    align-items: stretch;
    flex-direction: column;
  }

  .online-product-select,
  .online-sn-select,
  .online-test-select,
  .result-select {
    width: 100%;
  }
}
</style>
