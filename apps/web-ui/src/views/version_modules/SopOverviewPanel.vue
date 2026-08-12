<template>
  <main class="main-content sop-main-content">
    <header class="versions-topbar">
      <div>
        <p class="eyebrow">STANDARD OPERATING PROCEDURES</p>
        <h1>{{ t('versions.sop.title') }}</h1>
        <p>{{ t('versions.sop.subtitle') }}</p>
      </div>
      <div class="versions-topbar-actions">
        <el-button :icon="Link" tag="a" :href="catalog?.source_url" target="_blank">{{ t('versions.sop.openMaster') }}</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadCatalog(true)">{{ t('versions.sop.refreshMaster') }}</el-button>
      </div>
    </header>

    <section class="sop-catalog-card">
      <div class="sop-toolbar">
        <div class="section-label">
          <span>SOP CATALOG</span>
          <strong>{{ t('versions.sop.catalog') }}</strong>
        </div>
        <div class="sop-filter-row">
          <el-input
            v-model="searchText"
            :prefix-icon="Search"
            clearable
            :placeholder="t('versions.sop.searchPlaceholder')"
          />
          <el-select v-model="selectedProject" clearable :placeholder="t('versions.sop.allProjects')">
            <el-option v-for="project in projectOptions" :key="project" :label="project" :value="project" />
          </el-select>
          <el-select v-model="selectedProcess" clearable filterable :placeholder="t('versions.sop.allProcesses')">
            <el-option v-if="!selectedProject" label="Include Assembly" :value="DEFAULT_PROCESS_FILTER" />
            <el-option v-for="process in processOptions" :key="process" :label="process" :value="process" />
          </el-select>
          <el-select v-model="selectedStatus" clearable :placeholder="t('versions.duro.allStatuses')">
            <el-option v-for="status in statusOptions" :key="status" :label="status" :value="status" />
          </el-select>
        </div>
      </div>

      <div v-if="loading && !catalog" class="sop-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>{{ t('versions.sop.loading') }}</span>
      </div>
      <el-table
        v-else
        :data="filteredEntries"
        height="clamp(360px, calc(100vh - 300px), 760px)"
        row-class-name="sop-table-row"
        :empty-text="t('versions.sop.empty')"
        @row-click="openAnalysis"
      >
        <el-table-column prop="project" :label="t('versions.sop.project')" min-width="170" align="center" header-align="center" show-overflow-tooltip />
        <el-table-column prop="process" :label="t('versions.sop.process')" min-width="260" align="center" header-align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="process-cell">
              <strong>{{ row.process || t('versions.sop.unnamed') }}</strong>
              <span>{{ t('versions.sop.rowNumber', { number: row.row_number }) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="issue_date" :label="t('versions.sop.issueDate')" width="130" align="center" header-align="center" />
        <el-table-column prop="status" :label="t('versions.sop.stage')" width="90" align="center" header-align="center">
          <template #default="{ row }">
            <span class="sop-status-pill" :class="`is-${row.status.toLowerCase()}`">{{ row.status || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="PDF" width="100" align="center" header-align="center">
          <template #default="{ row }">
            <a
              v-if="row.drive_file_id"
              class="pdf-source-link"
              :href="sourcePdfUrl(row)"
              target="_blank"
              rel="noopener noreferrer"
              :title="t('versions.sop.openSourcePdf')"
              :aria-label="t('versions.sop.openSourcePdf')"
              @click.stop
            >
              <el-icon class="pdf-ready-icon"><DocumentChecked /></el-icon>
            </a>
            <span v-else class="missing-link">{{ t('versions.sop.noLink') }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('versions.common.actions')" width="130" align="center" header-align="center">
          <template #default="{ row }">
            <el-button text type="primary" :disabled="!row.drive_file_id" @click.stop="openAnalysis(row)">
              {{ t('versions.sop.analyzeBom') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <footer class="catalog-footer">
        <span>{{ t('versions.sop.showing', { shown: filteredEntries.length, total: catalog?.total_rows ?? 0 }) }}</span>
        <span>{{ t('versions.common.updatedAt', { time: formatDate(catalog?.fetched_at ?? null) }) }}</span>
      </footer>
    </section>

    <footer class="sop-board-footer" :aria-label="t('versions.sop.boardAria')">
      <span>SOP <strong>{{ catalog?.total_rows ?? 0 }}</strong></span>
      <span>{{ t('versions.sop.analyzablePdf') }} <strong>{{ catalog?.linked_file_count ?? 0 }}</strong></span>
      <span>{{ t('versions.sop.productProjects') }} <strong>{{ projectOptions.length }}</strong></span>
      <span>{{ t('versions.sop.currentFilter') }} <strong>{{ filteredEntries.length }}</strong></span>
      <span class="sop-cache-state">{{ catalog?.cached ? t('versions.common.sqliteCache') : 'Google Sheets' }}</span>
    </footer>

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
            <strong>{{ selectedEntry?.process || t('versions.sop.analysis') }}</strong>
          </div>
        </div>
      </template>

      <div v-if="analysisLoading" class="analysis-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <strong>{{ t('versions.sop.analyzing') }}</strong>
        <span>{{ t('versions.sop.analyzingHint') }}</span>
      </div>
      <el-result
        v-else-if="analysisError"
        icon="error"
        :title="t('versions.sop.analysisFailed')"
        :sub-title="analysisError"
      >
        <template #extra>
          <el-button type="primary" @click="retryAnalysis">{{ t('common.actions.retry') }}</el-button>
        </template>
      </el-result>
      <div v-else-if="analysis" class="analysis-content">
        <section class="analysis-summary">
          <div class="analysis-file-copy">
            <strong>{{ analysis.filename }}</strong>
            <span>{{ t('versions.sop.fileMeta', { size: formatBytes(analysis.size), pages: analysis.page_count, state: analysis.cached ? t('versions.sop.cachedResult') : t('versions.sop.latestAnalysis') }) }}</span>
          </div>
          <div class="analysis-summary-actions">
            <el-button
              circle
              :icon="Refresh"
              :loading="analysisLoading"
              :aria-label="t('versions.sop.refreshAnalysis')"
              :title="t('versions.sop.refreshAnalysis')"
              @click="refreshAnalysis"
            />
            <a v-if="selectedEntry?.link_url" :href="selectedEntry.link_url" target="_blank" rel="noreferrer">
              <el-icon><Link /></el-icon>
              {{ t('versions.sop.viewOriginal') }}
            </a>
          </div>
        </section>

        <el-alert
          v-if="analysis.ai_used"
          :title="t('versions.sop.aiUsed')"
          type="success"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="analysis.ai_fallback"
          :title="t('versions.sop.aiFallback', { error: analysis.ai_error || t('errors.unknown') })"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="analysis.ai_error"
          :title="analysis.ai_error"
          type="info"
          :closable="false"
          show-icon
        />

        <section class="analysis-metrics">
          <article>
            <span>{{ t('versions.sop.uniqueParts') }}</span>
            <strong>{{ analysis.bom_material_count }}</strong>
          </article>
          <article>
            <span>{{ t('versions.sop.materialRows') }}</span>
            <strong>{{ analysis.bom_occurrence_count }}</strong>
          </article>
          <article>
            <span>{{ t('versions.sop.extractedText') }}</span>
            <strong>{{ analysis.text_length.toLocaleString() }}</strong>
          </article>
        </section>

        <el-alert
          v-if="!analysis.bom_detected"
          :title="t('versions.sop.noMaterialList')"
          type="warning"
          :closable="false"
          show-icon
        />

        <el-tabs v-model="analysisTab" class="analysis-tabs">
          <el-tab-pane :label="t('versions.sop.bomSummary')" name="summary">
            <div class="bom-toolbar">
              <el-input v-model="bomSearchText" :prefix-icon="Search" clearable :placeholder="t('versions.sop.searchPart')" />
              <span>{{ t('versions.sop.quantityAccumulated') }}</span>
            </div>
            <el-table :data="filteredBomMaterials" height="calc(100vh - 300px)" border>
              <el-table-column prop="part_number" :label="t('versions.sop.partNumber')" width="130" fixed />
              <el-table-column prop="name" :label="t('versions.sop.materialName')" min-width="330" show-overflow-tooltip />
              <el-table-column :label="t('versions.sop.consumptionQuantity')" width="110" align="right">
                <template #default="{ row }">
                  <strong>{{ formatQuantity(row.quantity) }}</strong>
                  <el-tooltip v-if="!row.quantity_complete" :content="t('versions.sop.incompleteQuantity')">
                    <el-icon class="quantity-warning"><Warning /></el-icon>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column prop="occurrences" :label="t('versions.sop.occurrences')" width="90" align="center" />
              <el-table-column :label="t('versions.sop.pages')" width="110">
                <template #default="{ row }">{{ row.pages.join(', ') }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="t('versions.sop.fullTextReferences')" name="references">
            <div class="bom-toolbar">
              <el-input
                v-model="referenceSearchText"
                :prefix-icon="Search"
                clearable
                :placeholder="t('versions.sop.searchFullText')"
              />
              <span>
                {{ t('versions.sop.referenceMeta', { materials: analysis.full_text_material_count, occurrences: analysis.full_text_occurrence_count }) }}
              </span>
            </div>
            <el-table
              :data="filteredFullTextReferences"
              height="calc(100vh - 300px)"
              border
              :empty-text="t('versions.sop.noReferences')"
            >
              <el-table-column type="expand" width="48">
                <template #default="{ row }">
                  <div class="semantic-audit-panel">
                    <div v-if="row.quantity_explanation" class="semantic-audit-summary">
                      <strong>{{ t('versions.sop.quantityExplanation') }}</strong>
                      <p>{{ row.quantity_explanation }}</p>
                    </div>
                    <article
                      v-for="(decision, decisionIndex) in row.quantity_decisions || []"
                      :key="`${decision.event_id}-${decisionIndex}`"
                      class="semantic-decision-item"
                    >
                      <span class="semantic-decision-badge" :class="decision.accumulate ? 'is-added' : 'is-skipped'">
                        {{ decision.accumulate ? t('versions.sop.accumulate', { quantity: formatQuantity(decision.quantity_delta) }) : t('versions.sop.doNotAccumulate') }}
                      </span>
                      <div>
                        <strong>{{ decision.action || t('versions.sop.semanticDecision') }}</strong>
                        <small>
                          <template v-if="decision.page_numbers?.length">{{ t('versions.sop.pageNumbers', { pages: decision.page_numbers.join(', ') }) }}</template>
                          <template v-if="decision.target"> · {{ t('versions.sop.target', { target: decision.target }) }}</template>
                          <template v-if="decision.location"> · {{ t('versions.sop.location', { location: decision.location }) }}</template>
                        </small>
                        <p>{{ decision.reason || '—' }}</p>
                        <blockquote v-if="decision.evidence">{{ decision.evidence }}</blockquote>
                      </div>
                    </article>
                    <el-empty v-if="!row.quantity_explanation && !row.quantity_decisions?.length" :description="t('versions.sop.noSemanticExplanation')" :image-size="42" />
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="part_number" :label="t('versions.sop.partNumber')" width="140" fixed />
              <el-table-column :label="t('versions.sop.materialName')" min-width="330" show-overflow-tooltip>
                <template #default="{ row }">{{ row.name || t('versions.sop.unrecognized') }}</template>
              </el-table-column>
              <el-table-column prop="occurrences" :label="t('versions.sop.occurrences')" width="110" align="center" />
              <el-table-column prop="quantity" :label="t('versions.sop.currentQuantity')" width="130" align="center" />
              <el-table-column :label="t('versions.sop.occurrencePages')" min-width="160">
                <template #default="{ row }">{{ row.pages.join(', ') }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="t('versions.sop.pdfText')" name="text">
            <el-collapse class="pdf-page-collapse">
              <el-collapse-item v-for="page in analysis.pages" :key="page.page_number" :name="page.page_number">
                <template #title>
                  <div class="section-collapse-title">
                    <strong>{{ t('versions.sop.pageNumber', { number: page.page_number }) }}</strong>
                    <span>{{ sopPageCategoryText[page.category] }} · {{ t('versions.sop.materialLinesOnly') }}</span>
                  </div>
                </template>
                <pre>{{ page.text }}</pre>
              </el-collapse-item>
            </el-collapse>
            <el-empty v-if="analysis.pages.length === 0" :description="t('versions.sop.noMaterialLines')" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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
import { sopApi, type SopBomMaterial, type SopCatalogEntry, type SopMasterSheet, type SopPdfAnalysis } from '@/scripts/modules/version_modules/api/sop'
import { useAppLocale } from '@/i18n'

const { t } = useI18n()
const { locale } = useAppLocale()
const loading = ref(true)
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
const sopPageCategoryText = computed<Record<string, string>>(() => ({
  instruction: t('versions.sop.categories.instruction'),
  material_list: t('versions.sop.categories.materialList'),
  tool_list: t('versions.sop.categories.toolList')
}))

const projectOptions = computed(() =>
  [...new Set((catalog.value?.entries ?? []).map((entry) => entry.project).filter(Boolean))].sort()
)

const processOptions = computed(() =>
  [...new Set(
    (catalog.value?.entries ?? [])
      .filter((entry) => !selectedProject.value || entry.project === selectedProject.value)
      .map((entry) => entry.process)
      .filter(Boolean)
  )]
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

watch(selectedProject, (project) => {
  if (project && !processOptions.value.includes(selectedProcess.value)) {
    selectedProcess.value = ''
  }
})

async function loadCatalog(refresh = false) {
  loading.value = true
  try {
    const response = await sopApi.masterSheet(refresh)
    catalog.value = response.data
    if (refresh) ElMessage.success(t('versions.sop.messages.masterRefreshed'))
  } catch (error) {
    console.error(error)
    ElMessage.error(t('versions.sop.messages.masterFailed'))
  } finally {
    loading.value = false
  }
}

async function openAnalysis(entry: SopCatalogEntry) {
  if (!entry.drive_file_id) {
    ElMessage.warning(t('versions.sop.messages.noPdfLink'))
    return
  }
  selectedEntry.value = entry
  analysis.value = null
  analysisError.value = ''
  analysisTab.value = 'summary'
  bomSearchText.value = ''
  referenceSearchText.value = ''
  analysisDrawerVisible.value = true
  await loadSelectedAnalysis(false)
}

async function loadSelectedAnalysis(refresh = false) {
  const fileId = selectedEntry.value?.drive_file_id
  if (!fileId) return
  analysisLoading.value = true
  analysisError.value = ''
  try {
    const response = await sopApi.analyze(fileId, refresh)
    analysis.value = response.data
    if (refresh) ElMessage.success(t('versions.sop.messages.analysisRefreshed'))
  } catch (error: any) {
    console.error(error)
    analysisError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || t('versions.sop.messages.pdfFailed')
  } finally {
    analysisLoading.value = false
  }
}

function retryAnalysis() {
  void loadSelectedAnalysis(true)
}

function refreshAnalysis() {
  void loadSelectedAnalysis(true)
}

function sourcePdfUrl(entry: SopCatalogEntry) {
  if (entry.link_url) return entry.link_url
  return entry.drive_file_id
    ? `https://drive.google.com/file/d/${encodeURIComponent(entry.drive_file_id)}/view`
    : '#'
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString(locale.value, { hour12: false })
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatQuantity(value: number | null) {
  if (value === null) return t('versions.sop.unrecognized')
  return Number.isInteger(value) ? value.toString() : value.toFixed(2)
}

onMounted(() => loadCatalog())
</script>

<style scoped>
.sop-main-content {
  min-width: 0;
}

.sop-catalog-card {
  margin-top: 24px;
  overflow: hidden;
  border: 1px solid #d9e0e5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(18, 33, 47, 0.06);
}

.sop-board-footer {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 22px;
  margin-top: 8px;
  padding: 0 12px;
  border-top: 1px solid #e2e7ea;
  color: #7d8993;
  font-size: 10px;
}

.sop-board-footer span {
  white-space: nowrap;
}

.sop-board-footer strong {
  margin-left: 4px;
  color: #23313d;
  font-size: 12px;
}

.sop-board-footer .sop-cache-state {
  color: #29957e;
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
  height: clamp(360px, calc(100vh - 300px), 760px);
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

.pdf-source-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  transition: background-color 0.18s ease, transform 0.18s ease;
}

.pdf-source-link:hover {
  background: #e9f6f2;
  transform: translateY(-1px);
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

.analysis-summary-actions {
  display: flex;
  align-items: center;
  gap: 10px;
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

@media (max-width: 900px) {
  .sop-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .sop-filter-row {
    width: 100%;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .sop-board-footer,
  .catalog-footer {
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 8px 16px;
  }
}

@media (max-width: 560px) {
  .sop-filter-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
