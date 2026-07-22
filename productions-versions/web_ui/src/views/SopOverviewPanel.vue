<template>
  <main class="main-content sop-main-content">
    <header class="topbar">
      <div>
        <p class="eyebrow">STANDARD OPERATING PROCEDURES</p>
        <h1>SOP 总览</h1>
        <p>读取 Google SOP 总表，分析 PDF 中的 BOM 物料和数量。</p>
      </div>
      <div class="topbar-actions">
        <el-button :icon="Link" tag="a" :href="catalog?.source_url" target="_blank">打开总表</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadCatalog(true)">刷新总表</el-button>
      </div>
    </header>

    <section class="metric-grid sop-metric-grid">
      <article class="metric-card">
        <span>SOP 总数</span>
        <strong>{{ catalog?.total_rows ?? 0 }}</strong>
        <small>{{ catalog?.sheet_title || 'All Project SOP' }}</small>
      </article>
      <article class="metric-card">
        <span>可分析 PDF</span>
        <strong>{{ catalog?.linked_file_count ?? 0 }}</strong>
        <small>已解析 Google Drive 文件 ID</small>
      </article>
      <article class="metric-card">
        <span>产品项目</span>
        <strong>{{ projectOptions.length }}</strong>
        <small>按合并单元格自动归类</small>
      </article>
      <article class="metric-card is-accent">
        <span>当前筛选</span>
        <strong>{{ filteredEntries.length }}</strong>
        <small>{{ catalog?.cached ? '来自五分钟缓存' : '来自 Google Sheets' }}</small>
      </article>
    </section>

    <section class="sop-catalog-card">
      <div class="sop-toolbar">
        <div class="section-label">
          <span>SOP CATALOG</span>
          <strong>标准作业指导书</strong>
        </div>
        <div class="sop-filter-row">
          <el-input
            v-model="searchText"
            :prefix-icon="Search"
            clearable
            placeholder="搜索项目、工序或日期"
          />
          <el-select v-model="selectedProject" clearable placeholder="全部项目">
            <el-option v-for="project in projectOptions" :key="project" :label="project" :value="project" />
          </el-select>
          <el-select v-model="selectedProcess" clearable filterable placeholder="全部 Process">
            <el-option label="Include Assembly" :value="DEFAULT_PROCESS_FILTER" />
            <el-option v-for="process in processOptions" :key="process" :label="process" :value="process" />
          </el-select>
          <el-select v-model="selectedStatus" clearable placeholder="全部状态">
            <el-option v-for="status in statusOptions" :key="status" :label="status" :value="status" />
          </el-select>
        </div>
      </div>

      <div v-if="loading && !catalog" class="sop-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在读取 Google SOP 总表…</span>
      </div>
      <el-table
        v-else
        :data="filteredEntries"
        height="610"
        row-class-name="sop-table-row"
        empty-text="没有符合条件的 SOP"
        @row-click="openAnalysis"
      >
        <el-table-column prop="project" label="项目" min-width="170" show-overflow-tooltip />
        <el-table-column prop="process" label="工序 / SOP" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="process-cell">
              <strong>{{ row.process || '未命名 SOP' }}</strong>
              <span>第 {{ row.row_number }} 行</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="issue_date" label="发行日期" width="130" />
        <el-table-column prop="status" label="阶段" width="90">
          <template #default="{ row }">
            <span class="sop-status-pill" :class="`is-${row.status.toLowerCase()}`">{{ row.status || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="PDF" width="100" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.drive_file_id" class="pdf-ready-icon"><DocumentChecked /></el-icon>
            <span v-else class="missing-link">无链接</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <el-button text type="primary" :disabled="!row.drive_file_id" @click.stop="openAnalysis(row)">
              分析 BOM
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <footer class="catalog-footer">
        <span>显示 {{ filteredEntries.length }} / {{ catalog?.total_rows ?? 0 }} 条</span>
        <span>更新时间：{{ formatDate(catalog?.fetched_at ?? null) }}</span>
      </footer>
    </section>

    <el-drawer
      v-model="analysisDrawerVisible"
      size="76%"
      class="sop-analysis-drawer"
      destroy-on-close
    >
      <template #header>
        <div class="analysis-drawer-title">
          <span class="analysis-file-icon"><el-icon><Document /></el-icon></span>
          <div>
            <span>{{ selectedEntry?.project }}</span>
            <strong>{{ selectedEntry?.process || 'SOP 分析' }}</strong>
          </div>
        </div>
      </template>

      <div v-if="analysisLoading" class="analysis-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <strong>正在下载并分析 SOP PDF</strong>
        <span>大文件可能需要几十秒，完成后会显示 BOM 料耗。</span>
      </div>
      <el-result
        v-else-if="analysisError"
        icon="error"
        title="SOP 分析失败"
        :sub-title="analysisError"
      >
        <template #extra>
          <el-button type="primary" @click="retryAnalysis">重试</el-button>
        </template>
      </el-result>
      <div v-else-if="analysis" class="analysis-content">
        <section class="analysis-summary">
          <div class="analysis-file-copy">
            <strong>{{ analysis.filename }}</strong>
            <span>{{ formatBytes(analysis.size) }} · {{ analysis.page_count }} 页 · {{ analysis.cached ? '缓存结果' : '最新分析' }}</span>
          </div>
          <a v-if="selectedEntry?.link_url" :href="selectedEntry.link_url" target="_blank" rel="noreferrer">
            <el-icon><Link /></el-icon>
            查看原始 PDF
          </a>
        </section>

        <section class="analysis-metrics">
          <article>
            <span>唯一料号</span>
            <strong>{{ analysis.bom_material_count }}</strong>
          </article>
          <article>
            <span>物料行数</span>
            <strong>{{ analysis.bom_occurrence_count }}</strong>
          </article>
          <article>
            <span>提取文本</span>
            <strong>{{ analysis.text_length.toLocaleString() }}</strong>
          </article>
        </section>

        <el-alert
          v-if="!analysis.bom_detected"
          title="该 SOP 中没有识别到“物料清单 / Material List”表格"
          type="warning"
          :closable="false"
          show-icon
        />

        <el-tabs v-model="analysisTab" class="analysis-tabs">
          <el-tab-pane label="BOM 物料汇总" name="summary">
            <div class="bom-toolbar">
              <el-input v-model="bomSearchText" :prefix-icon="Search" clearable placeholder="搜索料号或物料名称" />
              <span>同一料号多次出现时，数量为累计值</span>
            </div>
            <el-table :data="filteredBomMaterials" height="520" border>
              <el-table-column prop="part_number" label="料号" width="130" fixed />
              <el-table-column prop="name" label="物料名称" min-width="330" show-overflow-tooltip />
              <el-table-column label="料耗数量" width="110" align="right">
                <template #default="{ row }">
                  <strong>{{ formatQuantity(row.quantity) }}</strong>
                  <el-tooltip v-if="!row.quantity_complete" content="部分物料行未识别到数量">
                    <el-icon class="quantity-warning"><Warning /></el-icon>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column prop="occurrences" label="出现次数" width="90" align="center" />
              <el-table-column label="页码" width="110">
                <template #default="{ row }">{{ row.pages.join(', ') }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="全文料号引用" name="references">
            <div class="bom-toolbar">
              <el-input
                v-model="referenceSearchText"
                :prefix-icon="Search"
                clearable
                placeholder="搜索全文料号或物料名称"
              />
              <span>
                已排除物料清单页 · {{ analysis.full_text_material_count }} 个料号，
                共 {{ analysis.full_text_occurrence_count }} 次引用
              </span>
            </div>
            <el-table
              :data="filteredFullTextReferences"
              height="520"
              border
              empty-text="除物料清单页外，没有识别到料号引用"
            >
              <el-table-column prop="part_number" label="料号" width="140" fixed />
              <el-table-column label="物料名称" min-width="330" show-overflow-tooltip>
                <template #default="{ row }">{{ row.name || '未识别' }}</template>
              </el-table-column>
              <el-table-column prop="occurrences" label="出现次数" width="110" align="center" />
              <el-table-column prop="quantity" label="当前物料数量" width="130" align="center" />
              <el-table-column label="出现页码" min-width="160">
                <template #default="{ row }">{{ row.pages.join(', ') }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="PDF 原文" name="text">
            <el-collapse class="pdf-page-collapse">
              <el-collapse-item v-for="page in analysis.pages" :key="page.page_number" :name="page.page_number">
                <template #title>
                  <div class="section-collapse-title">
                    <strong>第 {{ page.page_number }} 页</strong>
                    <span>仅显示包含物料的原文行</span>
                  </div>
                </template>
                <pre>{{ page.text }}</pre>
              </el-collapse-item>
            </el-collapse>
            <el-empty v-if="analysis.pages.length === 0" description="PDF 中没有识别到包含物料的原文行" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document,
  DocumentChecked,
  Link,
  Loading,
  Refresh,
  Search,
  Warning
} from '@element-plus/icons-vue'
import { sopApi, type SopBomMaterial, type SopCatalogEntry, type SopMasterSheet, type SopPdfAnalysis } from '@/api/sop'


const loading = ref(false)
const catalog = ref<SopMasterSheet | null>(null)
const searchText = ref('')
const selectedProject = ref('')
const DEFAULT_PROCESS_FILTER = '__assembly_without_qc__'
const selectedProcess = ref(DEFAULT_PROCESS_FILTER)
const selectedStatus = ref('')
const analysisDrawerVisible = ref(false)
const analysisLoading = ref(false)
const analysisError = ref('')
const analysis = ref<SopPdfAnalysis | null>(null)
const selectedEntry = ref<SopCatalogEntry | null>(null)
const analysisTab = ref('summary')
const bomSearchText = ref('')
const referenceSearchText = ref('')

const projectOptions = computed(() =>
  [...new Set((catalog.value?.entries ?? []).map((entry) => entry.project).filter(Boolean))].sort()
)

const processOptions = computed(() =>
  [...new Set((catalog.value?.entries ?? []).map((entry) => entry.process).filter(Boolean))].sort()
)

const statusOptions = computed(() => Object.keys(catalog.value?.status_counts ?? {}).sort())

const filteredEntries = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  return (catalog.value?.entries ?? []).filter((entry) => {
    if (selectedProject.value && entry.project !== selectedProject.value) return false
    if (selectedProcess.value === DEFAULT_PROCESS_FILTER) {
      const process = entry.process.toLowerCase()
      if (!process.includes('assembly') || process.includes('qc')) return false
    } else if (selectedProcess.value && entry.process !== selectedProcess.value) {
      return false
    }
    if (selectedStatus.value && entry.status !== selectedStatus.value) return false
    if (!keyword) return true
    return [entry.project, entry.process, entry.issue_date, entry.status, entry.note]
      .some((value) => value.toLowerCase().includes(keyword))
  })
})

const filteredBomMaterials = computed(() => {
  const keyword = bomSearchText.value.trim().toLowerCase()
  if (!keyword) return analysis.value?.bom_materials ?? []
  return (analysis.value?.bom_materials ?? []).filter((material) =>
    material.part_number.toLowerCase().includes(keyword) || material.name.toLowerCase().includes(keyword)
  )
})

const filteredFullTextReferences = computed(() => {
  const keyword = referenceSearchText.value.trim().toLowerCase()
  if (!keyword) return analysis.value?.full_text_references ?? []
  return (analysis.value?.full_text_references ?? []).filter((reference) =>
    reference.part_number.toLowerCase().includes(keyword) || reference.name.toLowerCase().includes(keyword)
  )
})

async function loadCatalog(refresh = false) {
  loading.value = true
  try {
    const response = await sopApi.masterSheet(refresh)
    catalog.value = response.data
    if (refresh) ElMessage.success('SOP 总表已刷新')
  } catch (error) {
    console.error(error)
    ElMessage.error('SOP 总表读取失败')
  } finally {
    loading.value = false
  }
}

async function openAnalysis(entry: SopCatalogEntry) {
  if (!entry.drive_file_id) {
    ElMessage.warning('该 SOP 没有可解析的 Google Drive PDF 链接')
    return
  }
  selectedEntry.value = entry
  analysis.value = null
  analysisError.value = ''
  analysisTab.value = 'summary'
  bomSearchText.value = ''
  referenceSearchText.value = ''
  analysisDrawerVisible.value = true
  analysisLoading.value = true
  try {
    const response = await sopApi.analyze(entry.drive_file_id)
    analysis.value = response.data
  } catch (error: any) {
    console.error(error)
    analysisError.value = error?.response?.data?.detail || error?.message || 'PDF 下载或分析失败'
  } finally {
    analysisLoading.value = false
  }
}

function retryAnalysis() {
  if (selectedEntry.value) void openAnalysis(selectedEntry.value)
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatQuantity(value: number | null) {
  if (value === null) return '未识别'
  return Number.isInteger(value) ? value.toString() : value.toFixed(2)
}

onMounted(() => loadCatalog())
</script>

<style scoped>
.sop-main-content {
  min-width: 0;
}

.sop-catalog-card {
  overflow: hidden;
  border: 1px solid #d9e0e5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(18, 33, 47, 0.06);
}

.sop-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 17px 20px;
  border-bottom: 1px solid #e4e9ec;
}

.sop-filter-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 150px 220px 120px;
  gap: 10px;
  width: min(900px, 78%);
}

.sop-loading-state,
.analysis-loading-state {
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  color: #7d8992;
}

.sop-loading-state {
  height: 610px;
}

.sop-loading-state .el-icon,
.analysis-loading-state .el-icon {
  color: #29957e;
  font-size: 30px;
}

.process-cell strong,
.process-cell span {
  display: block;
}

.process-cell strong {
  color: #26343d;
  font-size: 12px;
}

.process-cell span {
  margin-top: 4px;
  color: #9aa4ac;
  font-size: 9px;
}

.sop-status-pill {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 10px;
  background: #e8edf0;
  color: #667580;
  font-size: 9px;
  font-weight: 850;
}

.sop-status-pill.is-mp {
  background: #dff3eb;
  color: #218469;
}

.sop-status-pill.is-evt {
  background: #e5effb;
  color: #3979b4;
}

.sop-status-pill.is-dvt {
  background: #fff0d8;
  color: #af761b;
}

.pdf-ready-icon {
  color: #29957e;
  font-size: 18px;
}

.missing-link {
  color: #a4adb4;
  font-size: 10px;
}

.catalog-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 18px;
  border-top: 1px solid #e7ebee;
  color: #87939b;
  font-size: 10px;
}

:deep(.sop-table-row) {
  cursor: pointer;
}

.analysis-drawer-title {
  display: flex;
  align-items: center;
  gap: 11px;
}

.analysis-file-icon {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: #dff3ee;
  color: #258c75;
}

.analysis-drawer-title span,
.analysis-drawer-title strong {
  display: block;
}

.analysis-drawer-title div > span {
  color: #86929b;
  font-size: 10px;
}

.analysis-drawer-title strong {
  margin-top: 3px;
  color: #1d2a34;
  font-size: 16px;
}

.analysis-loading-state {
  min-height: 480px;
}

.analysis-loading-state strong {
  color: #27353f;
  font-size: 15px;
}

.analysis-loading-state span {
  font-size: 11px;
}

.analysis-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 16px;
  border: 1px solid #dfe6e9;
  border-radius: 10px;
  background: #f8fafb;
}

.analysis-file-copy strong,
.analysis-file-copy span {
  display: block;
}

.analysis-file-copy strong {
  color: #26343e;
  font-size: 13px;
}

.analysis-file-copy span {
  margin-top: 5px;
  color: #84919a;
  font-size: 10px;
}

.analysis-summary a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #258d76;
  font-size: 11px;
  font-weight: 750;
  text-decoration: none;
}

.analysis-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin: 13px 0;
}

.analysis-metrics article {
  padding: 14px;
  border: 1px solid #e0e6e9;
  border-radius: 9px;
}

.analysis-metrics span,
.analysis-metrics strong {
  display: block;
}

.analysis-metrics span {
  color: #89949d;
  font-size: 9px;
}

.analysis-metrics strong {
  margin-top: 5px;
  color: #20303a;
  font-size: 21px;
}

.analysis-tabs {
  margin-top: 14px;
}

.bom-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.bom-toolbar .el-input {
  width: 340px;
}

.bom-toolbar span {
  color: #8a959d;
  font-size: 10px;
}

.quantity-warning {
  margin-left: 4px;
  color: #e0a637;
}

.section-collapse-title {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-right: 18px;
}

.section-collapse-title strong {
  color: #293740;
  font-size: 12px;
}

.section-collapse-title span {
  color: #8c979f;
  font-size: 10px;
}

.pdf-page-collapse pre {
  max-height: 420px;
  overflow: auto;
  margin: 0;
  padding: 14px;
  border-radius: 7px;
  background: #111a21;
  color: #dce6ec;
  font: 11px/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap;
}

@media (max-width: 1350px) {
  .sop-filter-row {
    grid-template-columns: minmax(190px, 1fr) 130px 180px 100px;
  }
}
</style>
