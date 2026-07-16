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
        <span class="status-dot"></span>
        <div>
          <strong>初始化版本</strong>
          <span>Duro 连接器待配置</span>
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
          <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">新建工作流</el-button>
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
            <el-button circle size="small" :icon="Plus" @click="createDialogVisible = true" />
          </div>

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

          <div class="builder-body">
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

            <section v-if="editForm.kind === 'duro_bom_check'" class="duro-config-panel">
              <div class="section-label">
                <span>DURO CONFIGURATION</span>
                <strong>Duro BOM 数据源</strong>
              </div>
              <label>
                <span>API 地址</span>
                <el-input v-model="duroConfiguration.duro_base_url" placeholder="后续接入 Duro API" />
              </label>
              <label>
                <span>产品 ID</span>
                <el-input v-model="duroConfiguration.duro_product_id" placeholder="例如：product-id" />
              </label>
              <label>
                <span>目标版本</span>
                <el-input v-model="duroConfiguration.target_revision" placeholder="例如：Rev A" />
              </label>
            </section>

            <section class="flow-section">
              <div class="section-heading-row">
                <div class="section-label">
                  <span>WORKFLOW BUILDER</span>
                  <strong>执行步骤</strong>
                </div>
                <el-button :icon="Plus" @click="stepDialogVisible = true">添加步骤</el-button>
              </div>

              <div class="flow-canvas">
                <div class="flow-start-node">
                  <el-icon><VideoPlay /></el-icon>
                  <span>触发</span>
                </div>
                <template v-for="(step, index) in editForm.steps" :key="step.id">
                  <div class="flow-connector"><span></span></div>
                  <article class="flow-node">
                    <div class="node-order">{{ String(index + 1).padStart(2, '0') }}</div>
                    <div class="node-icon"><el-icon><component :is="stepIcon(step.kind)" /></el-icon></div>
                    <div class="node-copy">
                      <span>{{ stepKindText[step.kind] }}</span>
                      <strong>{{ step.name }}</strong>
                      <small>{{ step.description || '暂无步骤说明' }}</small>
                    </div>
                    <div class="node-actions">
                      <el-button text :disabled="index === 0" @click="moveStep(index, -1)">前移</el-button>
                      <el-button text :disabled="index === editForm.steps.length - 1" @click="moveStep(index, 1)">后移</el-button>
                      <el-button text type="danger" @click="removeStep(index)">删除</el-button>
                    </div>
                  </article>
                </template>
                <div class="flow-connector"><span></span></div>
                <div class="flow-end-node">
                  <el-icon><CircleCheck /></el-icon>
                  <span>结束</span>
                </div>
              </div>
            </section>

            <section class="run-section">
              <div class="section-heading-row">
                <div class="section-label">
                  <span>EXECUTION HISTORY</span>
                  <strong>最近运行</strong>
                </div>
                <span class="next-run-text">下次运行：{{ formatDate(selectedWorkflow.next_run_at) }}</span>
              </div>
              <div v-if="!workflowRuns.length" class="empty-runs">还没有运行记录，点击“手动运行”验证触发链路。</div>
              <div v-else class="run-list">
                <article v-for="run in workflowRuns.slice(0, 5)" :key="run.id" class="run-row">
                  <span class="run-status-icon" :class="`is-${run.status}`"></span>
                  <div>
                    <strong>{{ runStatusText[run.status] }}</strong>
                    <small>{{ run.message || '工作流正在运行' }}</small>
                  </div>
                  <span>{{ run.trigger_type === 'manual' ? '手动' : '定时' }}</span>
                  <time>{{ formatDate(run.created_at) }}</time>
                </article>
              </div>
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

    <el-dialog v-model="stepDialogVisible" title="添加工作流步骤" width="480px">
      <div class="dialog-form">
        <label>
          <span>步骤名称</span>
          <el-input v-model="stepForm.name" placeholder="例如：校验发布版本" />
        </label>
        <label>
          <span>步骤类型</span>
          <el-select v-model="stepForm.kind">
            <el-option label="读取 Duro BOM" value="duro_bom_fetch" />
            <el-option label="BOM 差异核对" value="bom_compare" />
            <el-option label="生成报告" value="report" />
            <el-option label="自定义步骤" value="custom" />
          </el-select>
        </label>
        <label>
          <span>说明</span>
          <el-input v-model="stepForm.description" type="textarea" :rows="3" />
        </label>
      </div>
      <template #footer>
        <el-button @click="stepDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addStep">添加</el-button>
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
  CircleCheck,
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
import {
  workflowApi,
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
const stepDialogVisible = ref(false)

const createForm = reactive({
  name: 'Duro BOM 核对',
  template: 'duro' as 'duro' | 'blank',
  description: '核对 Duro 产品 BOM 的结构、料号、数量和版本差异。'
})

const stepForm = reactive({
  name: '',
  kind: 'custom' as WorkflowStepKind,
  description: ''
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

const selectedWorkflow = computed(() =>
  workflows.value.find((workflow) => workflow.id === selectedWorkflowId.value) ?? null
)

const activeWorkflowCount = computed(() => workflows.value.filter((item) => item.status === 'active').length)
const scheduledWorkflowCount = computed(() => workflows.value.filter((item) => item.schedule.enabled).length)
const latestRun = computed(() => workflowRuns.value[0] ?? null)
const latestRunStatus = computed(() => latestRun.value ? runStatusText[latestRun.value.status] : '—')
const latestRunTime = computed(() => latestRun.value ? formatDate(latestRun.value.created_at) : '暂无运行记录')
const duroConfiguration = computed(() => editForm.value?.configuration as Record<string, string>)

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
    configuration: { ...workflow.configuration }
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
        ? { duro_base_url: '', duro_product_id: '', target_revision: '' }
        : {},
      steps: isDuro ? duroTemplateSteps() : []
    }
    const response = await workflowApi.create(payload)
    workflows.value = [response.data, ...workflows.value]
    selectWorkflow(response.data.id)
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
    await workflowApi.trigger(workflow.id)
    ElMessage.success('工作流已触发')
    window.setTimeout(() => void loadRuns(workflow.id), 250)
    window.setTimeout(() => void loadRuns(workflow.id), 900)
    await loadWorkflows()
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流触发失败')
  } finally {
    triggering.value = false
  }
}

function addStep() {
  if (!editForm.value) return
  if (!stepForm.name.trim()) {
    ElMessage.warning('请输入步骤名称')
    return
  }
  editForm.value.steps.push({
    id: `step_${Date.now().toString(36)}`,
    name: stepForm.name.trim(),
    kind: stepForm.kind,
    description: stepForm.description.trim(),
    configuration: {}
  })
  stepForm.name = ''
  stepForm.kind = 'custom'
  stepForm.description = ''
  stepDialogVisible.value = false
}

function removeStep(index: number) {
  editForm.value?.steps.splice(index, 1)
}

function moveStep(index: number, offset: number) {
  if (!editForm.value) return
  const target = index + offset
  if (target < 0 || target >= editForm.value.steps.length) return
  const [step] = editForm.value.steps.splice(index, 1)
  editForm.value.steps.splice(target, 0, step)
}

function duroTemplateSteps(): WorkflowStep[] {
  return [
    createStep('读取 Duro BOM', 'duro_bom_fetch', '按产品 ID 和目标版本读取 Duro BOM。'),
    createStep('核对 BOM', 'bom_compare', '检查料号、数量、版本和层级差异。'),
    createStep('生成核对报告', 'report', '汇总缺失项、冗余项和版本不一致。')
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

onMounted(loadWorkflows)
</script>
