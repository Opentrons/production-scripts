<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">V</div>
        <div>
          <strong>Productions</strong>
          <span>Versions</span>
        </div>
      </div>

      <nav class="main-nav" aria-label="主导航">
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'workflows' }"
          type="button"
          @click="activeModule = 'workflows'"
        >
          <el-icon><Connection /></el-icon>
          工作流
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'sop' }"
          type="button"
          @click="activeModule = 'sop'"
        >
          <el-icon><FolderOpened /></el-icon>
          SOP
        </button>
        <div class="nav-submenu" :class="{ 'is-open': activeModule === 'sop' }">
          <button
            class="nav-subitem"
            :class="{ 'is-active': activeModule === 'sop' }"
            type="button"
            @click="activeModule = 'sop'"
          >
            <span></span>
            SOP 总览
          </button>
        </div>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'duro' }"
          type="button"
          @click="activeModule = 'duro'"
        >
          <el-icon><Box /></el-icon>
          Duro
        </button>
        <div class="nav-submenu" :class="{ 'is-open': activeModule === 'duro' }">
          <button
            class="nav-subitem"
            :class="{ 'is-active': activeModule === 'duro' }"
            type="button"
            @click="activeModule = 'duro'"
          >
            <span></span>
            产品总览
          </button>
        </div>
        <button class="nav-item" type="button" disabled>
          <el-icon><Clock /></el-icon>
          运行记录
          <span class="soon-label">Soon</span>
        </button>
        <button class="nav-item" type="button" disabled>
          <el-icon><Setting /></el-icon>
          集成配置
          <span class="soon-label">Soon</span>
        </button>
      </nav>

      <div class="sidebar-note">
        <span class="status-dot is-ready"></span>
        <div>
          <strong>数据源已接入</strong>
          <span>SOP / Duro API</span>
        </div>
      </div>
    </aside>

    <main v-if="activeModule === 'workflows'" class="main-content">
      <header class="topbar">
        <div>
          <p class="eyebrow">VERSION AUTOMATION</p>
          <h1>版本检测工作流</h1>
          <p>创建、编排并运行产品版本与 BOM 核对流程。</p>
        </div>
        <div class="topbar-actions">
          <el-button :icon="Refresh" :loading="loading" @click="loadWorkflows">刷新</el-button>
        </div>
      </header>

      <section class="metric-grid">
        <article class="metric-card">
          <span>工作流总数</span>
          <strong>{{ workflows.length }}</strong>
          <small>{{ activeWorkflowCount }} 个已启用</small>
        </article>
        <article class="metric-card">
          <span>定时任务</span>
          <strong>{{ scheduledWorkflowCount }}</strong>
          <small>按配置自动触发</small>
        </article>
        <article class="metric-card">
          <span>最近运行</span>
          <strong>{{ latestRunStatus }}</strong>
          <small>{{ latestRunTime }}</small>
        </article>
        <article class="metric-card is-accent">
          <span>Duro BOM</span>
          <strong>Ready</strong>
          <small>工作流骨架已初始化</small>
        </article>
      </section>

      <section class="workspace">
        <aside class="workflow-list-panel">
          <div class="panel-heading">
            <div>
              <span>WORKFLOWS</span>
              <strong>工作流列表</strong>
            </div>
          </div>

          <el-button class="workflow-create-button" type="primary" :icon="Plus" @click="createDialogVisible = true">
            新建工作流
          </el-button>

          <div class="workflow-list-scroll">
            <div v-if="loading && !workflows.length" class="list-state">正在加载工作流…</div>
            <div v-else-if="!workflows.length" class="list-state">还没有工作流</div>
            <button
              v-for="workflow in workflows"
              :key="workflow.id"
              class="workflow-list-item"
              :class="{ 'is-selected': workflow.id === selectedWorkflowId }"
              type="button"
              @click="selectWorkflow(workflow.id)"
            >
              <span class="workflow-type-icon" :class="`is-${workflow.kind}`">
                <el-icon><Files v-if="workflow.kind === 'duro_bom_check'" /><Connection v-else /></el-icon>
              </span>
              <span class="workflow-list-copy">
                <strong>{{ workflow.name }}</strong>
                <small>{{ workflow.steps.length }} 个步骤 · {{ scheduleText(workflow) }}</small>
              </span>
              <span class="workflow-status" :class="`is-${workflow.status}`">{{ statusText[workflow.status] }}</span>
            </button>
          </div>
        </aside>

        <section v-if="selectedWorkflow && editForm" class="builder-panel">
          <header class="builder-header">
            <div class="builder-title">
              <span class="builder-icon"><el-icon><Files /></el-icon></span>
              <div>
                <div class="title-row">
                  <h2>{{ editForm.name }}</h2>
                  <span class="kind-pill">{{ kindText[editForm.kind] }}</span>
                </div>
                <p>{{ editForm.description || '暂无描述' }}</p>
              </div>
            </div>
            <div class="builder-actions">
              <el-button :icon="Delete" @click="deleteSelectedWorkflow">删除</el-button>
              <el-button :icon="VideoPlay" :loading="triggering" @click="triggerSelectedWorkflow">手动运行</el-button>
              <el-button type="primary" :icon="Check" :loading="saving" @click="saveSelectedWorkflow">保存</el-button>
            </div>
          </header>

          <nav class="builder-navigation" aria-label="工作流详情导航">
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'editor' }"
              @click="builderTab = 'editor'"
            >
              编辑工作流
            </button>
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'history' }"
              @click="builderTab = 'history'"
            >
              历史运行
              <span>{{ workflowRuns.length }}</span>
            </button>
          </nav>

          <div class="builder-body">
            <template v-if="builderTab === 'editor'">
              <section class="configuration-strip">
                <label class="config-field is-wide">
                  <span>工作流名称</span>
                  <el-input v-model="editForm.name" />
                </label>
                <label class="config-field">
                  <span>状态</span>
                  <el-select v-model="editForm.status">
                    <el-option label="草稿" value="draft" />
                    <el-option label="启用" value="active" />
                    <el-option label="暂停" value="paused" />
                  </el-select>
                </label>
                <label class="config-field schedule-field">
                  <span>定时触发</span>
                  <div class="schedule-control">
                    <el-switch v-model="editForm.schedule.enabled" />
                    <el-input-number
                      v-model="editForm.schedule.interval_minutes"
                      :disabled="!editForm.schedule.enabled"
                      :min="1"
                      :max="10080"
                      controls-position="right"
                    />
                    <em>分钟</em>
                  </div>
                </label>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-source-grid">
                <article class="workflow-source-card is-sop">
                  <header>
                    <div class="section-label">
                      <span>SOP SOURCE</span>
                      <strong>Include Assembly 产品</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="sopSourcesLoading"
                      @click="loadSopSources(true)"
                    >刷新</el-button>
                  </header>
                  <p>仅显示 Process 包含 Assembly 且不包含 QC 的 SOP；核对只使用全文料号引用，不读取物料清单页。</p>
                  <el-select
                    v-model="sourceConfiguration.sop_drive_file_ids"
                    filterable
                    clearable
                    multiple
                    collapse-tags
                    :max-collapse-tags="2"
                    :loading="sopSourcesLoading"
                    placeholder="选择一个或多个 Include Assembly SOP"
                    @change="handleSopSourceChange"
                  >
                    <el-option
                      v-for="entry in includeAssemblySopOptions"
                      :key="`${entry.row_number}-${entry.drive_file_id}`"
                      :label="sopOptionLabel(entry)"
                      :value="entry.drive_file_id || ''"
                    >
                      <div class="source-option">
                        <strong>{{ entry.project || '未分类产品' }}</strong>
                        <span>{{ entry.process }} · {{ entry.issue_date || '无日期' }}</span>
                      </div>
                    </el-option>
                  </el-select>
                  <el-alert v-if="sopSourcesError" type="warning" :closable="false" show-icon>
                    {{ sopSourcesError }}
                  </el-alert>
                  <div v-if="selectedSopEntries.length" class="source-selection-list">
                    <div v-for="entry in selectedSopEntries" :key="entry.drive_file_id || entry.row_number">
                      <strong>{{ entry.project || '未分类产品' }}</strong>
                      <span>{{ entry.process }} · {{ entry.issue_date || '无日期' }}</span>
                    </div>
                  </div>
                </article>

                <article class="workflow-source-card is-duro">
                  <header>
                    <div class="section-label">
                      <span>DURO SOURCE</span>
                      <strong>Duro 产品</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="duroProductsLoading"
                      @click="loadDuroProducts(true)"
                    >刷新</el-button>
                  </header>
                  <p>通过当前 Duro 产品 API 加载产品、料号及当前 Revision。</p>
                  <el-select
                    v-model="sourceConfiguration.duro_product_id"
                    filterable
                    clearable
                    :loading="duroProductsLoading"
                    placeholder="选择 Duro 产品"
                    @change="handleDuroProductChange"
                  >
                    <el-option
                      v-for="product in duroProductOptions"
                      :key="product._id"
                      :label="duroProductLabel(product)"
                      :value="product._id"
                    >
                      <div class="source-option">
                        <strong>{{ product.cpn || product.name || product._id }}</strong>
                        <span>{{ product.name }} · {{ product.revision || '无 Revision' }}</span>
                      </div>
                    </el-option>
                  </el-select>
                  <el-alert v-if="duroProductsError" type="warning" :closable="false" show-icon>
                    {{ duroProductsError }}
                  </el-alert>
                  <label class="source-revision-field">
                    <span>目标 Revision</span>
                    <el-input v-model="sourceConfiguration.target_revision" placeholder="选择产品后自动带入，可手动修改" />
                  </label>
                  <div v-if="selectedDuroProduct" class="source-selection-summary">
                    <span>产品：{{ selectedDuroProduct.name || '—' }}</span>
                    <span>料号：{{ selectedDuroProduct.cpn || '—' }}</span>
                    <span>当前 Revision：{{ selectedDuroProduct.revision || '—' }}</span>
                  </div>
                </article>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-filter-panel">
                <div class="section-label">
                  <span>BOM PART FILTER</span>
                  <strong>忽略 BOM 料号</strong>
                </div>

                <el-input-tag
                  v-model="sourceConfiguration.ignored_part_numbers"
                  clearable
                  trigger="Enter"
                  :save-on-blur="true"
                  placeholder="输入料号后按 Enter，例如 100-00001"
                  @change="normalizeIgnoredPartNumbers"
                />
                <div class="workflow-filter-summary">
                  已配置 {{ sourceConfiguration.ignored_part_numbers?.length || 0 }} 个忽略料号；
                  执行时会同时从 SOP 与 Duro BOM 中排除。
                </div>
              </section>

              <section class="flow-section">
                <div class="section-heading-row">
                  <div class="section-label">
                    <span>BOM CHECK FLOW</span>
                    <strong>核对流程</strong>
                  </div>
                </div>

                <div class="flow-canvas is-compact">
                  <template v-for="(step, index) in editForm.steps" :key="step.id">
                    <div v-if="index > 0" class="flow-connector"><span></span></div>
                    <article class="flow-node">
                      <div class="node-order">{{ String(index + 1).padStart(2, '0') }}</div>
                      <div class="node-icon"><el-icon><component :is="stepIcon(step.kind)" /></el-icon></div>
                      <div class="node-copy">
                        <span>{{ stepKindText[step.kind] }}</span>
                        <strong>{{ step.name }}</strong>
                        <small>{{ step.description || '暂无步骤说明' }}</small>
                      </div>
                    </article>
                  </template>
                </div>
              </section>
            </template>

            <section v-else class="run-section is-history-tab">
              <div class="section-heading-row">
                <div class="section-label">
                  <span>EXECUTION HISTORY</span>
                  <strong>历史运行</strong>
                </div>
                <div class="history-actions">
                  <span class="next-run-text">下次运行：{{ formatDate(selectedWorkflow.next_run_at) }}</span>
                  <el-button :icon="Refresh" @click="loadRuns(selectedWorkflow.id)">刷新记录</el-button>
                </div>
              </div>
              <div v-if="!workflowRuns.length" class="empty-runs">还没有运行记录，点击“手动运行”验证触发链路。</div>
              <el-collapse v-else class="run-history-collapse">
                <el-collapse-item v-for="run in workflowRuns" :key="run.id" :name="run.id">
                  <template #title>
                    <div class="run-history-title" :class="{ 'has-warning': runHasWarnings(run) }">
                      <span class="run-status-icon" :class="runStatusClass(run)"></span>
                      <div>
                        <span class="run-primary-status" :class="runStatusClass(run)">
                          {{ runStatusText[run.status] }}
                        </span>
                        <small>{{ run.message || '工作流正在运行' }}</small>
                      </div>
                      <div class="run-warning-summary" :class="{ 'is-warning': runHasWarnings(run), 'is-clear': runSucceededWithoutWarnings(run) }">
                        <template v-if="runHasWarnings(run) && run.report">
                          <strong>警告 {{ runWarningCount(run) }}</strong>
                          <span v-if="run.report.missing_in_duro_count">缺失 {{ run.report.missing_in_duro_count }}</span>
                          <span v-if="run.report.extra_in_duro_count">冗余 {{ run.report.extra_in_duro_count }}</span>
                          <span v-if="run.report.quantity_mismatch_count">数量 {{ run.report.quantity_mismatch_count }}</span>
                          <span v-if="run.report.quantity_unknown_count">未知 {{ run.report.quantity_unknown_count }}</span>
                        </template>
                        <span v-else-if="runSucceededWithoutWarnings(run)">无警告</span>
                        <span v-else>—</span>
                      </div>
                      <span class="run-trigger-type">{{ run.trigger_type === 'manual' ? '手动' : '定时' }}</span>
                      <time>{{ formatDate(run.created_at) }}</time>
                    </div>
                  </template>

                  <div v-if="run.report" class="bom-report">
                    <div class="bom-report-metrics">
                      <article><span>SOP 源</span><strong>{{ run.report.sop_source_count }}</strong></article>
                      <article><span>全文引用料号</span><strong>{{ run.report.sop_material_count }}</strong></article>
                      <article><span>Duro 料号</span><strong>{{ run.report.duro_material_count }}</strong></article>
                      <article><span>一致</span><strong>{{ run.report.matched_count }}</strong></article>
                      <article class="is-danger"><span>缺失</span><strong>{{ run.report.missing_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>冗余</span><strong>{{ run.report.extra_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>数量差异</span><strong>{{ run.report.quantity_mismatch_count }}</strong></article>
                      <article><span>数量未知</span><strong>{{ run.report.quantity_unknown_count }}</strong></article>
                    </div>
                    <div class="bom-report-toolbar">
                      <div>
                        <strong>差异明细</strong>
                        <span>
                          显示 {{ filteredReportDifferences(run).length }} / {{ run.report.differences.length }} 项
                        </span>
                      </div>
                      <el-select
                        :model-value="reportFilter(run.id)"
                        class="difference-filter-select"
                        @change="setReportFilter(run.id, $event)"
                      >
                        <el-option label="全部差异" value="all" />
                        <el-option label="不看数量差异" value="structure" />
                        <el-option label="只看 Duro 缺失" value="missing_in_duro" />
                        <el-option label="只看 Duro 冗余" value="extra_in_duro" />
                        <el-option label="只看数量差异" value="quantity_mismatch" />
                        <el-option label="只看数量未知" value="quantity_unknown" />
                      </el-select>
                    </div>
                    <el-table
                      :data="filteredReportDifferences(run)"
                      :row-class-name="differenceRowClassName"
                      max-height="520"
                      border
                      empty-text="SOP BOM 与 Duro BOM 一致"
                    >
                      <el-table-column label="差异类型" width="125">
                        <template #default="{ row }">
                          <span class="difference-status" :class="`is-${row.status}`">
                            {{ differenceLabel(row.status) }}
                          </span>
                        </template>
                      </el-table-column>
                      <el-table-column prop="part_number" label="料号" width="130" />
                      <el-table-column prop="name" label="物料名称" min-width="260" show-overflow-tooltip />
                      <el-table-column label="SOP 数量" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.sop_quantity) }}</template>
                      </el-table-column>
                      <el-table-column label="Duro 数量" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.duro_quantity) }}</template>
                      </el-table-column>
                      <el-table-column label="差值" width="90" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.quantity_delta) }}</template>
                      </el-table-column>
                      <el-table-column label="SOP 位置" min-width="260" show-overflow-tooltip>
                        <template #default="{ row }">{{ row.sop_locations.join('；') || '—' }}</template>
                      </el-table-column>
                      <el-table-column label="Duro 路径" min-width="300" show-overflow-tooltip>
                        <template #default="{ row }">{{ row.duro_paths.join('；') || '—' }}</template>
                      </el-table-column>
                    </el-table>
                  </div>
                  <el-alert
                    v-else-if="run.status === 'running' || run.status === 'queued'"
                    title="正在读取并核对 BOM，请稍后刷新运行记录"
                    type="info"
                    :closable="false"
                    show-icon
                  />
                  <div v-else class="run-log-list">
                    <span v-for="(log, index) in run.logs" :key="index">{{ log }}</span>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </section>
          </div>
        </section>

        <section v-else class="builder-empty">
          <el-icon><Connection /></el-icon>
          <strong>选择一个工作流开始编辑</strong>
        </section>
      </section>
    </main>
    <SopOverviewPanel v-else-if="activeModule === 'sop'" />
    <DuroProductsPanel v-else />

    <el-dialog v-model="createDialogVisible" title="新建工作流" width="520px">
      <div class="dialog-form">
        <label>
          <span>工作流名称</span>
          <el-input v-model="createForm.name" placeholder="输入工作流名称" />
        </label>
        <label>
          <span>模板</span>
          <el-radio-group v-model="createForm.template">
            <el-radio-button value="duro">Duro BOM 核对</el-radio-button>
            <el-radio-button value="blank">空白工作流</el-radio-button>
          </el-radio-group>
        </label>
        <label>
          <span>描述</span>
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </label>
      </div>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createWorkflow">创建</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Box,
  Check,
  Clock,
  Connection,
  DataAnalysis,
  Delete,
  DocumentChecked,
  Files,
  FolderOpened,
  Plus,
  Refresh,
  Setting,
  VideoPlay
} from '@element-plus/icons-vue'
import DuroProductsPanel from '@/views/DuroProductsPanel.vue'
import SopOverviewPanel from '@/views/SopOverviewPanel.vue'
import { duroApi, type DuroProduct } from '@/api/duro'
import { sopApi, type SopCatalogEntry } from '@/api/sop'
import {
  workflowApi,
  type WorkflowBomDifferenceStatus,
  type Workflow,
  type WorkflowKind,
  type WorkflowPayload,
  type WorkflowRun,
  type WorkflowRunStatus,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowStepKind
} from '@/api/workflows'


const loading = ref(false)
const activeModule = ref<'workflows' | 'sop' | 'duro'>('workflows')
const saving = ref(false)
const creating = ref(false)
const triggering = ref(false)
const workflows = ref<Workflow[]>([])
const workflowRuns = ref<WorkflowRun[]>([])
const selectedWorkflowId = ref<string | null>(null)
const editForm = ref<WorkflowPayload | null>(null)
const createDialogVisible = ref(false)
const builderTab = ref<'editor' | 'history'>('editor')
const sopSourcesLoading = ref(false)
const sopSourcesError = ref('')
const sopCatalogEntries = ref<SopCatalogEntry[]>([])
const duroProductsLoading = ref(false)
const duroProductsError = ref('')
const duroProducts = ref<DuroProduct[]>([])
const reportDifferenceFilters = reactive<Record<string, ReportDifferenceFilter>>({})

type ReportDifferenceFilter = 'all' | 'structure' | WorkflowBomDifferenceStatus

interface WorkflowSopSource {
  drive_file_id: string
  project: string
  process: string
  issue_date: string
  link_url: string | null
  row_number: number
}

interface WorkflowSourceConfiguration extends Record<string, unknown> {
  sop_drive_file_ids?: string[]
  sop_sources?: WorkflowSopSource[]
  sop_drive_file_id?: string
  sop_project?: string
  sop_process?: string
  sop_issue_date?: string
  sop_link_url?: string
  sop_row_number?: number | null
  duro_product_id?: string
  duro_product_name?: string
  duro_product_cpn?: string
  duro_product_revision?: string
  target_revision?: string
  ignored_part_numbers?: string[]
}

const createForm = reactive({
  name: 'Duro BOM 核对',
  template: 'duro' as 'duro' | 'blank',
  description: '核对 Duro 产品 BOM 的结构、料号、数量和版本差异。'
})

const statusText: Record<WorkflowStatus, string> = {
  draft: '草稿',
  active: '启用',
  paused: '暂停'
}

const kindText: Record<WorkflowKind, string> = {
  duro_bom_check: 'Duro BOM',
  custom: '自定义'
}

const stepKindText: Record<WorkflowStepKind, string> = {
  duro_bom_fetch: 'DURO SOURCE',
  bom_compare: 'BOM CHECK',
  report: 'REPORT',
  custom: 'CUSTOM STEP'
}

const runStatusText: Record<WorkflowRunStatus, string> = {
  queued: '等待执行',
  running: '执行中',
  succeeded: '执行成功',
  failed: '执行失败',
  skipped: '等待配置'
}

const differenceStatusText: Record<WorkflowBomDifferenceStatus, string> = {
  missing_in_duro: 'Duro 缺失',
  extra_in_duro: 'Duro 冗余',
  quantity_mismatch: '数量差异',
  quantity_unknown: '数量未知'
}

const selectedWorkflow = computed(() =>
  workflows.value.find((workflow) => workflow.id === selectedWorkflowId.value) ?? null
)

const activeWorkflowCount = computed(() => workflows.value.filter((item) => item.status === 'active').length)
const scheduledWorkflowCount = computed(() => workflows.value.filter((item) => item.schedule.enabled).length)
const latestRun = computed(() => workflowRuns.value[0] ?? null)
const latestRunStatus = computed(() => latestRun.value ? runStatusText[latestRun.value.status] : '—')
const latestRunTime = computed(() => latestRun.value ? formatDate(latestRun.value.created_at) : '暂无运行记录')
const sourceConfiguration = computed(
  () => editForm.value?.configuration as WorkflowSourceConfiguration
)
const includeAssemblySopOptions = computed(() =>
  sopCatalogEntries.value
    .filter((entry) => {
      const process = entry.process.toLowerCase()
      return process.includes('assembly') && !process.includes('qc') && Boolean(entry.drive_file_id)
    })
    .sort((left, right) =>
      `${left.project}\u0000${left.process}\u0000${left.issue_date}`.localeCompare(
        `${right.project}\u0000${right.process}\u0000${right.issue_date}`
      )
    )
)
const duroProductOptions = computed(() =>
  [...duroProducts.value].sort((left, right) =>
    (left.cpn || left.name || left._id).localeCompare(right.cpn || right.name || right._id)
  )
)
const selectedSopEntries = computed(() => {
  const fileIds = new Set(sourceConfiguration.value?.sop_drive_file_ids ?? [])
  return includeAssemblySopOptions.value.filter((entry) => entry.drive_file_id && fileIds.has(entry.drive_file_id))
})
const selectedDuroProduct = computed(() => {
  const productId = sourceConfiguration.value?.duro_product_id
  return duroProducts.value.find((product) => product._id === productId) ?? null
})

function cloneWorkflowPayload(workflow: Workflow): WorkflowPayload {
  return {
    name: workflow.name,
    description: workflow.description,
    kind: workflow.kind,
    status: workflow.status,
    schedule: { ...workflow.schedule },
    steps: workflow.steps.map((step) => ({
      ...step,
      configuration: { ...step.configuration }
    })),
    configuration: normalizeWorkflowConfiguration(workflow.configuration)
  }
}

function normalizeWorkflowConfiguration(configuration: Record<string, unknown>): WorkflowSourceConfiguration {
  const legacyFileId = typeof configuration.sop_drive_file_id === 'string'
    ? configuration.sop_drive_file_id.trim()
    : ''
  const configuredFileIds = Array.isArray(configuration.sop_drive_file_ids)
    ? configuration.sop_drive_file_ids.map(String).filter(Boolean)
    : []
  const fileIds = configuredFileIds.length ? configuredFileIds : (legacyFileId ? [legacyFileId] : [])
  const configuredSources = Array.isArray(configuration.sop_sources)
    ? configuration.sop_sources.filter((item): item is WorkflowSopSource => Boolean(item && typeof item === 'object'))
    : []
  const ignoredPartNumbers = Array.isArray(configuration.ignored_part_numbers)
    ? [...new Set(configuration.ignored_part_numbers.map((value) => String(value).trim().toUpperCase()).filter(Boolean))]
    : []
  return {
    sop_drive_file_id: '',
    sop_project: '',
    sop_process: '',
    sop_issue_date: '',
    sop_link_url: '',
    sop_row_number: null,
    duro_product_id: '',
    duro_product_name: '',
    duro_product_cpn: '',
    duro_product_revision: '',
    target_revision: '',
    ...configuration,
    sop_drive_file_ids: fileIds,
    sop_sources: configuredSources,
    ignored_part_numbers: ignoredPartNumbers
  }
}

async function loadWorkflows() {
  loading.value = true
  try {
    const response = await workflowApi.list()
    workflows.value = response.data
    const currentId = selectedWorkflowId.value
    const nextSelection = response.data.find((item) => item.id === currentId) ?? response.data[0] ?? null
    if (nextSelection) {
      selectWorkflow(nextSelection.id)
    } else {
      selectedWorkflowId.value = null
      editForm.value = null
      workflowRuns.value = []
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流加载失败，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

function selectWorkflow(workflowId: string) {
  const workflow = workflows.value.find((item) => item.id === workflowId)
  if (!workflow) return
  selectedWorkflowId.value = workflowId
  editForm.value = cloneWorkflowPayload(workflow)
  void loadRuns(workflowId)
}

async function loadSopSources(refresh = false) {
  sopSourcesLoading.value = true
  sopSourcesError.value = ''
  try {
    const response = await sopApi.masterSheet(refresh)
    sopCatalogEntries.value = response.data.entries
  } catch (error: any) {
    console.error(error)
    sopSourcesError.value = error?.response?.data?.detail || error?.message || 'SOP 数据源加载失败'
  } finally {
    sopSourcesLoading.value = false
  }
}

async function loadDuroProducts(refresh = false) {
  duroProductsLoading.value = true
  duroProductsError.value = ''
  try {
    const response = await duroApi.products(refresh)
    duroProducts.value = response.data.products
  } catch (error: any) {
    console.error(error)
    duroProductsError.value = error?.response?.data?.detail || error?.message || 'Duro 产品加载失败'
  } finally {
    duroProductsLoading.value = false
  }
}

function handleSopSourceChange(fileIds: string[]) {
  if (!editForm.value) return
  const configuration = sourceConfiguration.value
  const selected = includeAssemblySopOptions.value.filter(
    (entry) => entry.drive_file_id && fileIds.includes(entry.drive_file_id)
  )
  configuration.sop_drive_file_ids = selected.map((entry) => entry.drive_file_id || '').filter(Boolean)
  configuration.sop_sources = selected.map((entry) => ({
    drive_file_id: entry.drive_file_id || '',
    project: entry.project,
    process: entry.process,
    issue_date: entry.issue_date,
    link_url: entry.link_url,
    row_number: entry.row_number
  }))
  const first = selected[0]
  configuration.sop_drive_file_id = first?.drive_file_id || ''
  configuration.sop_project = first?.project || ''
  configuration.sop_process = first?.process || ''
  configuration.sop_issue_date = first?.issue_date || ''
  configuration.sop_link_url = first?.link_url || ''
  configuration.sop_row_number = first?.row_number ?? null
}

function handleDuroProductChange(productId: string) {
  if (!editForm.value) return
  const configuration = sourceConfiguration.value
  const product = duroProducts.value.find((item) => item._id === productId)
  configuration.duro_product_id = product?._id || ''
  configuration.duro_product_name = product?.name || ''
  configuration.duro_product_cpn = product?.cpn || ''
  configuration.duro_product_revision = product?.revision || ''
  configuration.target_revision = product?.revision || ''
}

function normalizeIgnoredPartNumbers(values?: string[]) {
  sourceConfiguration.value.ignored_part_numbers = [
    ...new Set((values ?? []).map((value) => value.trim().toUpperCase()).filter(Boolean))
  ]
}

function sopOptionLabel(entry: SopCatalogEntry) {
  return `${entry.project || '未分类产品'} · ${entry.process}${entry.issue_date ? ` · ${entry.issue_date}` : ''}`
}

function duroProductLabel(product: DuroProduct) {
  const identity = product.cpn || product.name || product._id
  const revision = product.revision ? ` · ${product.revision}` : ''
  return `${identity}${product.name && product.name !== identity ? ` · ${product.name}` : ''}${revision}`
}

async function loadRuns(workflowId: string) {
  try {
    const response = await workflowApi.runs(workflowId)
    if (selectedWorkflowId.value === workflowId) {
      workflowRuns.value = response.data
    }
  } catch (error) {
    console.error(error)
  }
}

async function saveSelectedWorkflow() {
  if (!selectedWorkflowId.value || !editForm.value) return
  if (!editForm.value.name.trim()) {
    ElMessage.warning('请输入工作流名称')
    return
  }
  saving.value = true
  try {
    const response = await workflowApi.update(selectedWorkflowId.value, editForm.value)
    const index = workflows.value.findIndex((item) => item.id === response.data.id)
    if (index >= 0) workflows.value[index] = response.data
    editForm.value = cloneWorkflowPayload(response.data)
    ElMessage.success('工作流已保存')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流保存失败')
  } finally {
    saving.value = false
  }
}

async function createWorkflow() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入工作流名称')
    return
  }
  creating.value = true
  try {
    const isDuro = createForm.template === 'duro'
    const payload: WorkflowPayload = {
      name: createForm.name.trim(),
      description: createForm.description.trim(),
      kind: isDuro ? 'duro_bom_check' : 'custom',
      status: 'draft',
      schedule: { enabled: false, interval_minutes: 60 },
      configuration: isDuro
        ? normalizeWorkflowConfiguration({})
        : {},
      steps: isDuro ? duroTemplateSteps() : []
    }
    const response = await workflowApi.create(payload)
    workflows.value = [response.data, ...workflows.value]
    selectWorkflow(response.data.id)
    builderTab.value = 'editor'
    createDialogVisible.value = false
    ElMessage.success('工作流已创建')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流创建失败')
  } finally {
    creating.value = false
  }
}

async function deleteSelectedWorkflow() {
  const workflow = selectedWorkflow.value
  if (!workflow) return
  try {
    await ElMessageBox.confirm(`确认删除“${workflow.name}”？`, '删除工作流', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await workflowApi.remove(workflow.id)
    workflows.value = workflows.value.filter((item) => item.id !== workflow.id)
    const next = workflows.value[0]
    if (next) selectWorkflow(next.id)
    else {
      selectedWorkflowId.value = null
      editForm.value = null
      workflowRuns.value = []
    }
    ElMessage.success('工作流已删除')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流删除失败')
  }
}

async function triggerSelectedWorkflow() {
  const workflow = selectedWorkflow.value
  if (!workflow) return
  triggering.value = true
  try {
    const response = await workflowApi.trigger(workflow.id)
    ElMessage.success('工作流已触发')
    builderTab.value = 'history'
    void pollWorkflowRun(workflow.id, response.data.id)
    await loadWorkflows()
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流触发失败')
  } finally {
    triggering.value = false
  }
}

async function pollWorkflowRun(workflowId: string, runId: string, attempt = 0) {
  await loadRuns(workflowId)
  const run = workflowRuns.value.find((item) => item.id === runId)
  if (!run || !['queued', 'running'].includes(run.status) || attempt >= 120) return
  window.setTimeout(() => void pollWorkflowRun(workflowId, runId, attempt + 1), 1000)
}

function duroTemplateSteps(): WorkflowStep[] {
  return [
    createStep('核对 Duro BOM', 'bom_compare', '汇总所选 Assembly SOP 的全文料号引用，并与 Duro BOM 核对料号和出现次数。'),
    createStep('核对报告', 'report', '输出缺失料号、冗余料号、数量差异和无法比较项。')
  ]
}

function createStep(name: string, kind: WorkflowStepKind, description: string): WorkflowStep {
  return {
    id: `step_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    name,
    kind,
    description,
    configuration: {}
  }
}

function stepIcon(kind: WorkflowStepKind) {
  if (kind === 'duro_bom_fetch') return Files
  if (kind === 'bom_compare') return DataAnalysis
  if (kind === 'report') return DocumentChecked
  return Connection
}

function scheduleText(workflow: Workflow) {
  return workflow.schedule.enabled ? `每 ${workflow.schedule.interval_minutes} 分钟` : '仅手动'
}

function formatDate(value: string | null) {
  if (!value) return '未安排'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatReportQuantity(value: number | null) {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? value.toString() : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
}

function differenceLabel(status: string) {
  return differenceStatusText[status as WorkflowBomDifferenceStatus] || status
}

function runWarningCount(run: WorkflowRun) {
  return run.report?.differences.length ?? 0
}

function runHasWarnings(run: WorkflowRun) {
  return run.status === 'succeeded' && runWarningCount(run) > 0
}

function runSucceededWithoutWarnings(run: WorkflowRun) {
  return run.status === 'succeeded' && runWarningCount(run) === 0
}

function runStatusClass(run: WorkflowRun) {
  return runHasWarnings(run) ? 'is-warning' : `is-${run.status}`
}

function reportFilter(runId: string): ReportDifferenceFilter {
  return reportDifferenceFilters[runId] || 'all'
}

function setReportFilter(runId: string, value: string) {
  reportDifferenceFilters[runId] = value as ReportDifferenceFilter
}

function filteredReportDifferences(run: WorkflowRun) {
  const differences = run.report?.differences ?? []
  const filter = reportFilter(run.id)
  if (filter === 'all') return differences
  if (filter === 'structure') {
    return differences.filter((item) => ['missing_in_duro', 'extra_in_duro'].includes(item.status))
  }
  return differences.filter((item) => item.status === filter)
}

function differenceRowClassName({ row }: { row: { status: WorkflowBomDifferenceStatus } }) {
  return `difference-row is-${row.status}`
}

onMounted(() => {
  void loadWorkflows()
  void loadSopSources()
  void loadDuroProducts()
})
</script>
