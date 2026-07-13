<template>
  <div class="test-case-page" :style="{ '--tree-width': `${treeWidth}px` }">
    <section class="tree-pane">
      <TestCaseTree
        :products="tree.products"
        :selected-id="selectedCase?.id ?? null"
        @create-product="openProductDialog"
        @create-type="openTypeDialog"
        @create-case="openCaseDialog"
        @select-case="selectCase"
      />
    </section>

    <button
      class="tree-resizer"
      type="button"
      aria-label="调整测试管理树宽度"
      @pointerdown="startResize"
    ></button>

    <main class="editor-pane">
      <header v-if="selectedCase" class="editor-head">
        <div>
          <h1>{{ selectedCase.name }}</h1>
          <span class="case-subtitle">{{ selectedCase.product_name }} · {{ selectedCase.test_type }} · Rev {{ selectedCase.revision }}</span>
        </div>
        <div class="head-metrics">
          <div>
            <span>运行</span>
            <strong>{{ selectedCase.run_count }}</strong>
          </div>
          <div>
            <span>成功</span>
            <strong>{{ selectedCase.success_count }}</strong>
          </div>
          <div>
            <span>失败</span>
            <strong>{{ selectedCase.failed_count }}</strong>
          </div>
          <div>
            <span>超时</span>
            <strong>{{ selectedCase.timeout_seconds }}s</strong>
          </div>
        </div>
        <div class="head-actions">
          <el-tooltip content="保存" placement="bottom">
            <el-button
              :icon="Check"
              circle
              type="primary"
              :loading="saving"
              :disabled="!hasCaseChanges"
              @click="saveCase"
            />
          </el-tooltip>
          <el-tooltip content="归档" placement="bottom">
            <el-button
              :icon="Delete"
              circle
              :loading="archiving"
              @click="archiveCase"
            />
          </el-tooltip>
          <el-tooltip content="刷新" placement="bottom">
            <el-button :icon="Refresh" circle :loading="loading" @click="loadAll" />
          </el-tooltip>
        </div>
      </header>

      <section v-if="selectedCase" class="case-detail">
        <div class="editor-main">
          <section class="case-editor-section">
            <div class="section-title">
              <div class="title-with-toggle">
                <el-tooltip :content="isCaseInfoCollapsed ? '展开用例信息' : '折叠用例信息'" placement="right">
                  <button
                    class="section-toggle"
                    type="button"
                    :aria-label="isCaseInfoCollapsed ? '展开用例信息' : '折叠用例信息'"
                    @click="isCaseInfoCollapsed = !isCaseInfoCollapsed"
                  >
                    <span>{{ isCaseInfoCollapsed ? '›' : '˅' }}</span>
                  </button>
                </el-tooltip>
                <span>用例信息</span>
              </div>
              <small v-if="hasCaseChanges">未保存</small>
            </div>
            <div v-show="!isCaseInfoCollapsed" class="editor-grid">
              <label class="edit-field is-wide">
                <span>用例名称</span>
                <el-input v-model="caseDraft.name" placeholder="测试用例名称" />
              </label>
              <label class="edit-field">
                <span>状态</span>
                <el-select v-model="caseDraft.status">
                  <el-option label="草稿" value="draft" />
                  <el-option label="启用" value="active" />
                  <el-option label="归档" value="archived" />
                </el-select>
              </label>
              <label class="edit-field">
                <span>超时</span>
                <el-input-number
                  v-model="caseDraft.timeout_seconds"
                  :min="1"
                  :max="7200"
                  :step="30"
                  controls-position="right"
                />
              </label>
              <label class="edit-field is-full">
                <span>运行命令</span>
                <el-input v-model="caseDraft.command" placeholder="python -m s.ssssss.fsss" />
              </label>
              <label class="edit-field is-full">
                <span>描述</span>
                <el-input
                  v-model="caseDraft.description"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 8 }"
                  placeholder="记录测试目标、前置条件或风险点"
                />
              </label>
            </div>
          </section>

          <section class="flow-section">
            <div class="section-title">
              <span>节点画布</span>
              <div class="flow-actions">
                <el-select
                  v-model="selectedDeviceIp"
                  class="device-select"
                  placeholder="选择设备"
                  clearable
                  filterable
                  size="small"
                >
                  <el-option
                    v-if="availableRobots.length === 0"
                    label="暂无缓存设备，请刷新"
                    value=""
                    disabled
                  />
                  <el-option
                    v-for="robot in availableRobots"
                    :key="robot.ip"
                    :label="robot.name ? `${robot.name} · ${robot.ip}` : robot.ip"
                    :value="robot.ip"
                  />
                </el-select>
                <el-tooltip content="刷新设备列表" placement="bottom">
                  <el-button
                    :icon="Refresh"
                    :loading="refreshingDevices"
                    circle
                    size="small"
                    @click="refreshDeviceList"
                  />
                </el-tooltip>
                <el-checkbox v-model="isPreviewMode">预览</el-checkbox>
                <el-tooltip content="运行日志" placement="bottom">
                  <el-button :icon="Document" circle size="small" @click="logDialogVisible = true" />
                </el-tooltip>
                <el-button :icon="Plus" @click="addNode">节点</el-button>
                <el-button
                  v-if="canStopExecution"
                  :icon="Close"
                  type="danger"
                  :loading="stoppingExecution"
                  @click="stopActiveExecution"
                >
                  停止
                </el-button>
                <el-button
                  v-else
                  :icon="VideoPlay"
                  type="primary"
                  :loading="isFlowPreviewRunning"
                  @click="runFlowPreview"
                >
                  运行
                </el-button>
              </div>
            </div>
            <div class="node-canvas">
              <div
                ref="canvasSurfaceRef"
                class="node-canvas-surface"
                :class="{ 'is-connecting': Boolean(connectionDraft) }"
                :style="canvasSurfaceStyle"
              >
                <svg class="flow-edges" :viewBox="`0 0 ${canvasSize.width} ${canvasSize.height}`" aria-hidden="true">
                  <defs>
                    <marker
                      id="flow-arrow"
                      markerWidth="10"
                      markerHeight="10"
                      refX="8"
                      refY="3"
                      orient="auto"
                      markerUnits="strokeWidth"
                    >
                      <path d="M0,0 L8,3 L0,6 Z" />
                    </marker>
                    <marker
                      id="flow-arrow-complete"
                      markerWidth="10"
                      markerHeight="10"
                      refX="8"
                      refY="3"
                      orient="auto"
                      markerUnits="strokeWidth"
                    >
                      <path d="M0,0 L8,3 L0,6 Z" />
                    </marker>
                    <marker
                      id="flow-arrow-selected"
                      markerWidth="10"
                      markerHeight="10"
                      refX="8"
                      refY="3"
                      orient="auto"
                      markerUnits="strokeWidth"
                    >
                      <path d="M0,0 L8,3 L0,6 Z" />
                    </marker>
                  </defs>
                  <g v-for="edge in visibleEdges" :key="edge.id" class="flow-edge-group">
                    <path
                      class="flow-edge-hit"
                      :d="edgePath(edge)"
                      @click.stop="selectEdge(edge.id)"
                      @contextmenu.prevent="deleteEdge(edge.id)"
                    />
                    <path
                      class="flow-edge"
                      :class="{
                        'is-complete': completedNodeIds.includes(edge.source) && completedNodeIds.includes(edge.target),
                        'is-selected': selectedEdgeId === edge.id
                      }"
                      :d="edgePath(edge)"
                    />
                  </g>
                  <path
                    v-if="connectionPreviewPath"
                    class="flow-edge-preview"
                    :d="connectionPreviewPath"
                  />
                </svg>
                <div
                  v-for="node in caseDraft.nodes"
                  :key="node.id"
                  class="flow-node"
                  :class="[
                    `is-${node.kind}`,
                    {
                      'is-selected': node.id === selectedNodeId,
                      'is-running': node.id === runningNodeId,
                      'is-complete': completedNodeIds.includes(node.id),
                      'is-waiting-input': waitingInputNode?.id === node.id
                    }
                  ]"
                  role="button"
                  tabindex="0"
                  :style="{ left: `${node.position.x}px`, top: `${node.position.y}px` }"
                  @click="selectNode(node.id)"
                  @keydown.enter="selectNode(node.id)"
                  @keydown.space.prevent="selectNode(node.id)"
                  @pointerdown="startNodeDrag($event, node)"
                >
                  <span class="node-tools">
                    <button
                      class="node-tool-button"
                      type="button"
                      aria-label="编辑节点属性"
                      @click.stop="openNodeDrawer(node.id)"
                      @pointerdown.stop
                    >
                      <el-icon><EditPen /></el-icon>
                    </button>
                  </span>
                  <span class="node-kind">{{ nodeKindText[node.kind] }}</span>
                  <strong>{{ node.name }}</strong>
                <small v-if="node.expect">{{ node.expect }}</small>
                <small v-else>{{ inputKindText[node.input_kind] }}</small>
                <div
                  v-if="waitingInputNode?.id === node.id"
                  class="node-input-popover"
                  @click.stop
                  @pointerdown.stop
                >
                  <div class="node-input-title">等待输入</div>
                  <div v-if="node.input_kind === 'boolean'" class="runtime-choice-grid">
                    <el-button class="runtime-option-button" @click="submitRuntimeInput(node.input_options[0]?.value ?? 'y')">
                      是
                    </el-button>
                    <el-button class="runtime-option-button" @click="submitRuntimeInput(node.input_options[1]?.value ?? 'n')">
                      否
                    </el-button>
                  </div>
                  <div v-else-if="node.input_kind === 'radio'" class="runtime-option-list">
                    <el-button
                      v-for="(option, index) in node.input_options"
                      :key="index"
                      class="runtime-option-button"
                      @click="submitRuntimeInput(option.value)"
                    >
                      {{ option.value || `选项 ${index + 1}` }}
                    </el-button>
                  </div>
                  <div v-else class="runtime-text-input">
                    <el-input
                      v-model="runtimeInputValue"
                      placeholder="输入后发送到脚本"
                      @keydown.enter.stop.prevent="submitRuntimeInput(runtimeInputValue)"
                    />
                    <el-button type="primary" @click="submitRuntimeInput(runtimeInputValue)">
                      确认
                    </el-button>
                  </div>
                </div>
                <span
                  class="node-port is-top"
                  :data-node-id="node.id"
                  @click.stop
                  @pointerdown.stop="startConnection($event, node.id)"
                ></span>
                <span
                  class="node-port is-right"
                  :data-node-id="node.id"
                  @click.stop
                  @pointerdown.stop="startConnection($event, node.id)"
                ></span>
                <span
                  class="node-port is-bottom"
                  :data-node-id="node.id"
                  @click.stop
                  @pointerdown.stop="startConnection($event, node.id)"
                ></span>
                <span
                  class="node-port is-left"
                  :data-node-id="node.id"
                  @click.stop
                  @pointerdown.stop="startConnection($event, node.id)"
                ></span>
              </div>
              </div>
            </div>
          </section>
        </div>

        <aside v-if="selectedNode && !isNodeDrawerPinnedClosed" class="node-drawer">
          <section class="status-block">
            <div class="block-title">
              <span>节点属性</span>
              <div class="drawer-actions">
                <el-button
                  :icon="Delete"
                  size="small"
                  text
                  :disabled="selectedNode.kind !== 'expect'"
                  @click="deleteSelectedNode"
                />
                <button class="drawer-close" type="button" aria-label="关闭节点属性" @click="closeNodeDrawer">×</button>
              </div>
            </div>
            <div class="node-form">
              <label>
                <span>节点名</span>
                <el-input v-model="selectedNode.name" />
              </label>
              <label>
                <span>节点类型</span>
                <el-input :model-value="nodeKindText[selectedNode.kind]" disabled />
              </label>
              <template v-if="selectedNode.kind === 'expect'">
                <label>
                  <span>Expect</span>
                  <el-input
                    v-model="selectedNode.expect"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    placeholder="input your name:"
                  />
                </label>
                <label>
                  <span>输入方式</span>
                  <el-select
                    :model-value="selectedNode.input_kind"
                    @change="updateSelectedNodeInputKind"
                  >
                    <el-option label="无需输入" value="none" />
                    <el-option label="是/否" value="boolean" />
                    <el-option label="字符串" value="text" />
                    <el-option label="单选项" value="radio" />
                  </el-select>
                </label>
                <div v-if="selectedNode.input_kind === 'boolean'" class="boolean-grid">
                  <label>
                    <span>是</span>
                    <el-input v-model="selectedBooleanYesValue" />
                  </label>
                  <label>
                    <span>否</span>
                    <el-input v-model="selectedBooleanNoValue" />
                  </label>
                </div>
                <div v-if="selectedNode.input_kind === 'radio'" class="radio-options">
                  <div class="option-list-title">
                    <span>字符串选项</span>
                    <el-button :icon="Plus" size="small" text @click="addSelectedRadioOption">添加</el-button>
                  </div>
                  <div
                    v-for="(option, index) in selectedNode.input_options"
                    :key="index"
                    class="radio-option-row"
                  >
                    <el-input v-model="option.value" :placeholder="`选项 ${index + 1}`" />
                    <el-button
                      :icon="Delete"
                      size="small"
                      text
                      :disabled="selectedNode.input_options.length <= 1"
                      @click="removeSelectedRadioOption(index)"
                    />
                  </div>
                </div>
              </template>
              <p v-else class="muted-copy">开始和结束节点是流程边界，不支持删除。</p>
            </div>
          </section>
        </aside>
      </section>

      <section v-else class="empty-editor">
        <el-empty description="请选择测试用例" />
      </section>
    </main>

    <footer class="test-footer">
      <span>SSH</span>
      <span>{{ executionStatus?.active_ssh_sessions ?? 0 }}/{{ executionStatus?.max_sessions ?? 20 }} 连接</span>
      <span>可用 {{ executionStatus?.available_sessions ?? 20 }}</span>
      <span>运行 {{ executionStatus?.running_tests ?? 0 }}</span>
      <span>等待输入 {{ executionStatus?.waiting_input_tests ?? 0 }}</span>
      <span>队列 {{ executionStatus?.queued_tests ?? 0 }}</span>
    </footer>

    <el-dialog v-model="productDialogVisible" title="新建产品" width="460px">
      <div class="dialog-form">
        <label>
          <span>产品 ID</span>
          <el-input v-model="productForm.product_id" placeholder="如：flex" />
        </label>
        <label>
          <span>产品名称</span>
          <el-input v-model="productForm.product_name" placeholder="如：Flex" />
        </label>
      </div>
      <template #footer>
        <el-button @click="productDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createProduct">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="typeDialogVisible" title="新建测试类型" width="460px">
      <div class="dialog-form">
        <label>
          <span>所属产品</span>
          <el-input :model-value="activeProduct?.product_name || ''" disabled />
        </label>
        <label>
          <span>测试类型</span>
          <el-input v-model="typeForm.test_type" placeholder="如：smoke / regression / calibration" />
        </label>
      </div>
      <template #footer>
        <el-button @click="typeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createType">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="caseDialogVisible" title="新建测试用例" width="520px">
      <div class="dialog-form">
        <label>
          <span>所属产品</span>
          <el-input :model-value="activeProduct?.product_name || ''" disabled />
        </label>
        <label>
          <span>测试类型</span>
          <el-input v-model="caseForm.test_type" disabled />
        </label>
        <label>
          <span>用例名称</span>
          <el-input v-model="caseForm.name" placeholder="如：Flex gripper smoke test" />
        </label>
        <label>
          <span>运行命令</span>
          <el-input v-model="caseForm.command" placeholder="python -m s.ssssss.fsss" />
        </label>
      </div>
      <template #footer>
        <el-button @click="caseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createCase">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logDialogVisible" title="运行日志" width="860px" class="execution-log-dialog">
      <div class="log-dialog-meta">
        <span>{{ isPreviewMode ? '预览模式' : '正式执行' }}</span>
        <span>设备 {{ selectedDeviceIp || '-' }}</span>
        <span>Run {{ activeExecutionRun?.id || '-' }}</span>
      </div>
      <div ref="logPanelRef" class="execution-log-panel">
        <div v-if="executionLogs.length === 0" class="log-empty">暂无运行日志</div>
        <div
          v-for="entry in executionLogs"
          :key="entry.id"
          class="log-line"
          :class="`is-${entry.level}`"
        >
          <span class="log-time">{{ entry.time }}</span>
          <span class="log-level">{{ entry.level }}</span>
          <span class="log-message">{{ entry.message }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="clearExecutionLogs">清空</el-button>
        <el-button type="primary" @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Close, Delete, Document, EditPen, Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { type RobotInfo } from '@/api'
import TestCaseTree from '@/components/test_case/TestCaseTree.vue'
import { useRobotScanStore } from '@/stores/robotScan'
import {
  testCaseService,
  type ExecutionStatusResponse,
  type TestCase,
  type TestCaseEdge,
  type TestCaseInputOption,
  type TestCaseNode,
  type TestCaseStatus,
  type TestExecutionRun,
  type TestInputKind,
  type TestCaseTreeProduct,
  type TestCaseTreeResponse
} from '@/services/testCaseService'

const route = useRoute()
const robotScanStore = useRobotScanStore()

const TREE_MIN_WIDTH = 260
const TREE_MAX_WIDTH = 520
const NODE_WIDTH = 156
const NODE_HEIGHT = 84
const CANVAS_MIN_WIDTH = 1200
const CANVAS_MIN_HEIGHT = 720

const loading = ref(false)
const submitting = ref(false)
const saving = ref(false)
const archiving = ref(false)
const refreshingDevices = ref(false)
const stoppingExecution = ref(false)
const logDialogVisible = ref(false)
const treeWidth = ref(320)
const productDialogVisible = ref(false)
const typeDialogVisible = ref(false)
const caseDialogVisible = ref(false)
const selectedCase = ref<TestCase | null>(null)
const activeProduct = ref<TestCaseTreeProduct | null>(null)
const tree = ref<TestCaseTreeResponse>({ products: [], total: 0 })
const availableRobots = ref<RobotInfo[]>([])
const selectedDeviceIp = ref<string | null>(null)
const executionStatus = ref<ExecutionStatusResponse | null>(null)
const selectedNodeId = ref<string | null>(null)
const selectedEdgeId = ref<string | null>(null)
const isNodeDrawerPinnedClosed = ref(false)
const runningNodeId = ref<string | null>(null)
const completedNodeIds = ref<string[]>([])
const isFlowPreviewRunning = ref(false)
const isPreviewMode = ref(true)
const isCaseInfoCollapsed = ref(false)
const canvasSurfaceRef = ref<HTMLElement | null>(null)
const activeExecutionRun = ref<TestExecutionRun | null>(null)
const waitingInputNode = ref<TestCaseNode | null>(null)
const runtimeInputValue = ref('')
const runtimeFlowNodes = ref<TestCaseNode[]>([])
const runtimeStepIndex = ref(0)
const executionLogs = ref<ExecutionLogEntry[]>([])
const syncedRunEventKeys = ref<Set<string>>(new Set())
const logPanelRef = ref<HTMLElement | null>(null)
let flowPreviewTimer: ReturnType<typeof window.setTimeout> | null = null
let executionPollTimer: ReturnType<typeof window.setInterval> | null = null

type ExecutionLogEntry = {
  id: string
  time: string
  level: 'info' | 'input' | 'output' | 'warn' | 'error' | 'success'
  message: string
}

type CanvasPoint = {
  x: number
  y: number
}

const connectionDraft = ref<{
  sourceId: string
  pointer: CanvasPoint
} | null>(null)

const initialDeviceIp = computed(() => {
  const ip = route.query.device_ip ?? route.query.ip
  return typeof ip === 'string' ? ip : ''
})

const initialCaseId = computed(() => {
  const caseId = route.query.case_id
  return typeof caseId === 'string' ? caseId : ''
})

const canStopExecution = computed(() => {
  if (isPreviewMode.value) return false
  return activeExecutionRun.value?.status === 'running' || activeExecutionRun.value?.status === 'waiting_input'
})

const caseDraft = reactive({
  name: '',
  command: '',
  description: '',
  timeout_seconds: 300,
  status: 'draft' as TestCaseStatus,
  nodes: [] as TestCaseNode[],
  edges: [] as TestCaseEdge[]
})

const productForm = reactive({
  product_id: '',
  product_name: ''
})

const typeForm = reactive({
  test_type: ''
})

const caseForm = reactive({
  name: '',
  test_type: '',
  command: ''
})

const nodeKindText: Record<TestCaseNode['kind'], string> = {
  start: 'Start',
  expect: 'Expect',
  end: 'End'
}

const inputKindText: Record<TestCaseNode['input_kind'], string> = {
  none: '无需输入',
  boolean: '是/否输入',
  text: '字符串输入',
  radio: '单选项'
}

const hasCaseChanges = computed(() => {
  if (!selectedCase.value) return false
  return (
    caseDraft.name !== selectedCase.value.name ||
    caseDraft.command !== selectedCase.value.command ||
    caseDraft.description !== (selectedCase.value.description ?? '') ||
    caseDraft.timeout_seconds !== selectedCase.value.timeout_seconds ||
    caseDraft.status !== selectedCase.value.status ||
    JSON.stringify(caseDraft.nodes) !== JSON.stringify(selectedCase.value.nodes) ||
    JSON.stringify(caseDraft.edges) !== JSON.stringify(selectedCase.value.edges)
  )
})

const selectedNode = computed(() => {
  if (!selectedNodeId.value) return null
  return caseDraft.nodes.find((node) => node.id === selectedNodeId.value) ?? null
})

const visibleEdges = computed(() => {
  return caseDraft.edges.filter((edge) => {
    return caseDraft.nodes.some((node) => node.id === edge.source) && caseDraft.nodes.some((node) => node.id === edge.target)
  })
})

const canvasSize = computed(() => {
  const maxX = caseDraft.nodes.reduce((value, node) => Math.max(value, node.position.x + NODE_WIDTH + 160), CANVAS_MIN_WIDTH)
  const maxY = caseDraft.nodes.reduce((value, node) => Math.max(value, node.position.y + NODE_HEIGHT + 160), CANVAS_MIN_HEIGHT)
  return {
    width: maxX,
    height: maxY
  }
})

const canvasSurfaceStyle = computed(() => ({
  width: `${canvasSize.value.width}px`,
  height: `${canvasSize.value.height}px`
}))

const connectionPreviewPath = computed(() => {
  if (!connectionDraft.value) return ''
  const source = caseDraft.nodes.find((node) => node.id === connectionDraft.value?.sourceId)
  if (!source) return ''

  const start = nodeEdgePoint(source, connectionDraft.value.pointer)
  return curvePath(start, connectionDraft.value.pointer)
})

const selectedBooleanYesValue = computed({
  get() {
    return selectedNode.value?.input_options[0]?.value ?? 'y'
  },
  set(value: string) {
    if (!selectedNode.value) return
    ensureBooleanOptions(selectedNode.value)
    selectedNode.value.input_options[0].value = value
  }
})

const selectedBooleanNoValue = computed({
  get() {
    return selectedNode.value?.input_options[1]?.value ?? 'n'
  },
  set(value: string) {
    if (!selectedNode.value) return
    ensureBooleanOptions(selectedNode.value)
    selectedNode.value.input_options[1].value = value
  }
})

async function loadAll() {
  loading.value = true
  try {
    const [treeResponse, statusResponse] = await Promise.all([
      testCaseService.getTree(),
      testCaseService.getExecutionStatus()
    ])
    tree.value = treeResponse.data
    executionStatus.value = statusResponse.data

    if (selectedCase.value) {
      await selectCase(selectedCase.value.id)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('测试管理数据加载失败')
  } finally {
    loading.value = false
  }
}

function syncRobotsFromStore() {
  availableRobots.value = robotScanStore.scanResult?.online_robots ?? []
}

function ensureDeviceInList(ip: string) {
  if (!ip || availableRobots.value.some((robot) => robot.ip === ip)) return
  availableRobots.value = [
    ...availableRobots.value,
    {
      ip,
      port: 31950,
      online: true,
      service_status: 'unknown'
    }
  ]
}

async function refreshDeviceList() {
  refreshingDevices.value = true
  const currentIp = selectedDeviceIp.value
  try {
    await robotScanStore.refreshScan({ silent: false })
    syncRobotsFromStore()
    if (currentIp) {
      ensureDeviceInList(currentIp)
      selectedDeviceIp.value = currentIp
    } else {
      selectedDeviceIp.value = availableRobots.value[0]?.ip ?? null
    }
    ElMessage.success(`设备列表已刷新，发现 ${availableRobots.value.length} 台在线设备`)
  } catch (error: any) {
    ElMessage.error('刷新设备列表失败: ' + (error.message || '未知错误'))
  } finally {
    refreshingDevices.value = false
  }
}

async function selectCase(caseId: string) {
  try {
    const response = await testCaseService.getCase(caseId)
    selectedCase.value = response.data
    syncCaseDraft(response.data)
  } catch (error) {
    console.error(error)
    ElMessage.error('测试用例加载失败')
  }
}

function syncCaseDraft(testCase: TestCase) {
  caseDraft.name = testCase.name
  caseDraft.command = testCase.command
  caseDraft.description = testCase.description ?? ''
  caseDraft.timeout_seconds = testCase.timeout_seconds
  caseDraft.status = testCase.status
  caseDraft.nodes = cloneNodes(testCase.nodes)
  caseDraft.edges = cloneEdges(testCase.edges)
  selectedNodeId.value = caseDraft.nodes[0]?.id ?? null
  selectedEdgeId.value = null
  isNodeDrawerPinnedClosed.value = true
  cancelConnection()
  resetFlowPreview()
}

function openProductDialog() {
  productForm.product_id = ''
  productForm.product_name = ''
  productDialogVisible.value = true
}

function openTypeDialog(product: TestCaseTreeProduct) {
  activeProduct.value = product
  typeForm.test_type = ''
  typeDialogVisible.value = true
}

function openCaseDialog(product: TestCaseTreeProduct, testType: string) {
  activeProduct.value = product
  caseForm.name = ''
  caseForm.test_type = testType
  caseForm.command = ''
  caseDialogVisible.value = true
}

async function createProduct() {
  if (!productForm.product_id || !productForm.product_name) {
    ElMessage.warning('请填写产品 ID 和产品名称')
    return
  }

  submitting.value = true
  try {
    await testCaseService.createProduct({ ...productForm })
    productDialogVisible.value = false
    await loadAll()
    ElMessage.success('产品已创建')
  } catch (error) {
    console.error(error)
    ElMessage.error('产品创建失败')
  } finally {
    submitting.value = false
  }
}

async function createType() {
  if (!activeProduct.value || !typeForm.test_type) {
    ElMessage.warning('请填写测试类型')
    return
  }

  submitting.value = true
  try {
    await testCaseService.createType(activeProduct.value.product_id, { ...typeForm })
    typeDialogVisible.value = false
    await loadAll()
    ElMessage.success('测试类型已创建')
  } catch (error) {
    console.error(error)
    ElMessage.error('测试类型创建失败')
  } finally {
    submitting.value = false
  }
}

async function createCase() {
  if (!activeProduct.value || !caseForm.name || !caseForm.test_type || !caseForm.command) {
    ElMessage.warning('请补全用例名称和运行命令')
    return
  }

  submitting.value = true
  try {
    const response = await testCaseService.createCase({
      name: caseForm.name,
      product_id: activeProduct.value.product_id,
      product_name: activeProduct.value.product_name,
      test_type: caseForm.test_type,
      command: caseForm.command,
      timeout_seconds: 300,
      status: 'draft'
    })
    selectedCase.value = response.data
    syncCaseDraft(response.data)
    caseDialogVisible.value = false
    await loadAll()
    ElMessage.success('测试用例已创建')
  } catch (error) {
    console.error(error)
    ElMessage.error('测试用例创建失败')
  } finally {
    submitting.value = false
  }
}

async function saveCase() {
  if (!selectedCase.value) return
  if (!caseDraft.name || !caseDraft.command) {
    ElMessage.warning('请填写用例名称和运行命令')
    return
  }

  saving.value = true
  try {
    const response = await testCaseService.updateCase(selectedCase.value.id, {
      name: caseDraft.name,
      command: caseDraft.command,
      description: caseDraft.description || null,
      timeout_seconds: caseDraft.timeout_seconds,
      status: caseDraft.status,
      nodes: cloneNodes(caseDraft.nodes),
      edges: cloneEdges(caseDraft.edges)
    })
    selectedCase.value = response.data
    syncCaseDraft(response.data)
    await loadAll()
    ElMessage.success('测试用例已保存')
  } catch (error) {
    console.error(error)
    ElMessage.error('测试用例保存失败')
  } finally {
    saving.value = false
  }
}

async function archiveCase() {
  if (!selectedCase.value) return

  try {
    await ElMessageBox.confirm(
      `确认归档“${selectedCase.value.name}”？`,
      '归档测试用例',
      {
        confirmButtonText: '归档',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  archiving.value = true
  try {
    await testCaseService.archiveCase(selectedCase.value.id)
    selectedCase.value = null
    resetCaseDraft()
    await loadAll()
    ElMessage.success('测试用例已归档')
  } catch (error) {
    console.error(error)
    ElMessage.error('测试用例归档失败')
  } finally {
    archiving.value = false
  }
}

function resetCaseDraft() {
  caseDraft.name = ''
  caseDraft.command = ''
  caseDraft.description = ''
  caseDraft.timeout_seconds = 300
  caseDraft.status = 'draft'
  caseDraft.nodes = []
  caseDraft.edges = []
  selectedNodeId.value = null
  selectedEdgeId.value = null
  isNodeDrawerPinnedClosed.value = false
  cancelConnection()
  resetFlowPreview()
}

function cloneNodes(nodes: TestCaseNode[]): TestCaseNode[] {
  return nodes.map((node) => ({
    ...node,
    input_options: node.input_options.map((option) => ({ ...option })),
    position: { ...node.position }
  }))
}

function cloneEdges(edges: TestCaseEdge[]): TestCaseEdge[] {
  return edges.map((edge) => ({ ...edge }))
}

function logTimestamp(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function appendExecutionLog(level: ExecutionLogEntry['level'], message: string) {
  executionLogs.value = [
    ...executionLogs.value,
    {
      id: `log_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
      time: logTimestamp(),
      level,
      message
    }
  ]
  void nextTick(() => {
    if (logPanelRef.value) {
      logPanelRef.value.scrollTop = logPanelRef.value.scrollHeight
    }
  })
}

function clearExecutionLogs() {
  executionLogs.value = []
  syncedRunEventKeys.value = new Set()
}

function syncRunLogs(run: TestExecutionRun | null) {
  if (!run) return
  run.events.forEach((event) => {
    const key = `${event.created_at}_${event.type}_${event.node_id ?? ''}_${event.value ?? ''}_${event.message ?? ''}`
    if (syncedRunEventKeys.value.has(key)) return
    syncedRunEventKeys.value.add(key)
    const level = runEventLevel(event.type)
    const nodeText = event.node_id ? `[${event.node_id}] ` : ''
    appendExecutionLog(level, `${nodeText}${event.message || event.value || runEventText(event.type)}`)
  })
}

function runEventLevel(type: string): ExecutionLogEntry['level'] {
  if (type.includes('input')) return 'input'
  if (type.includes('output')) return 'output'
  if (type.includes('completed')) return 'success'
  if (type.includes('error') || type.includes('failed') || type.includes('timeout')) return 'error'
  if (type.includes('stopped')) return 'warn'
  if (type.includes('waiting')) return 'warn'
  return 'info'
}

function runEventText(type: string) {
  const textMap: Record<string, string> = {
    started: '运行已启动',
    ssh_connecting: '正在连接 SSH',
    ssh_connected: 'SSH 已连接',
    command_started: '命令已启动',
    ssh_output: '脚本输出',
    expect_matched: 'Expect 已命中',
    node_running: '节点开始执行',
    waiting_input: '等待用户输入',
    input_submitted: '用户输入已提交',
    ssh_stdin_sent: '输入已写入 SSH',
    ssh_session_stopped: 'SSH session 已停止',
    execution_error: '执行异常',
    stopped: '运行已停止',
    failed: '运行失败',
    timeout: '运行超时',
    error: '运行异常',
    completed: '运行结束'
  }
  return textMap[type] ?? type
}

function createId(prefix: string) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function sortNodesForFlow(nodes: TestCaseNode[]) {
  return [...nodes].sort((left, right) => {
    const kindWeight: Record<TestCaseNode['kind'], number> = { start: 0, expect: 1, end: 2 }
    const weightDiff = kindWeight[left.kind] - kindWeight[right.kind]
    if (weightDiff !== 0) return weightDiff
    return left.position.x - right.position.x
  })
}

function resolveFlowPreviewNodes() {
  const nodeMap = new Map(caseDraft.nodes.map((node) => [node.id, node]))
  const startNode = caseDraft.nodes.find((node) => node.kind === 'start') ?? sortNodesForFlow(caseDraft.nodes)[0]
  if (!startNode) return []
  if (caseDraft.edges.length === 0) return sortNodesForFlow(caseDraft.nodes)

  const orderedNodes: TestCaseNode[] = []
  const visited = new Set<string>()
  let current: TestCaseNode | undefined = startNode

  while (current && !visited.has(current.id)) {
    orderedNodes.push(current)
    visited.add(current.id)
    const nextEdge = caseDraft.edges.find((edge) => edge.source === current?.id && nodeMap.has(edge.target))
    current = nextEdge ? nodeMap.get(nextEdge.target) : undefined
  }

  const remainingNodes = sortNodesForFlow(caseDraft.nodes).filter((node) => !visited.has(node.id))
  return [...orderedNodes, ...remainingNodes]
}

function addEdge(source: string, target: string, selectCreated = true) {
  if (source === target) return
  const existing = caseDraft.edges.find((edge) => edge.source === source && edge.target === target)
  if (existing) {
    if (selectCreated) {
      selectEdge(existing.id)
    }
    return
  }
  const edge = {
    id: `edge_${source}_${target}_${Date.now().toString(36)}`,
    source,
    target,
    condition: null
  }
  caseDraft.edges.push(edge)
  if (selectCreated) {
    selectedEdgeId.value = edge.id
    selectedNodeId.value = null
    isNodeDrawerPinnedClosed.value = true
  }
  resetFlowPreview()
}

function deleteEdge(edgeId: string) {
  caseDraft.edges = caseDraft.edges.filter((edge) => edge.id !== edgeId)
  if (selectedEdgeId.value === edgeId) {
    selectedEdgeId.value = null
  }
  resetFlowPreview()
}

function selectEdge(edgeId: string) {
  selectedEdgeId.value = edgeId
  selectedNodeId.value = null
  isNodeDrawerPinnedClosed.value = true
}

function resetFlowPreview() {
  if (flowPreviewTimer) {
    window.clearTimeout(flowPreviewTimer)
    flowPreviewTimer = null
  }
  stopExecutionPolling()
  runningNodeId.value = null
  completedNodeIds.value = []
  isFlowPreviewRunning.value = false
  activeExecutionRun.value = null
  waitingInputNode.value = null
  runtimeInputValue.value = ''
  runtimeFlowNodes.value = []
  runtimeStepIndex.value = 0
  syncedRunEventKeys.value = new Set()
}

function stopExecutionPolling() {
  if (executionPollTimer) {
    window.clearInterval(executionPollTimer)
    executionPollTimer = null
  }
}

async function runFlowPreview() {
  if (caseDraft.nodes.length === 0) return
  if (!isPreviewMode.value) {
    await runBackendExecution()
    return
  }

  const previewNodes = resolveFlowPreviewNodes()
  if (previewNodes.length === 0) return
  isCaseInfoCollapsed.value = true
  resetFlowPreview()
  executionLogs.value = []
  appendExecutionLog('info', '预览运行启动')
  appendExecutionLog('info', `运行命令: ${caseDraft.command || '-'}`)
  appendExecutionLog('info', `目标设备: ${selectedDeviceIp.value || '-'}`)
  runtimeFlowNodes.value = previewNodes
  runtimeStepIndex.value = 0
  isFlowPreviewRunning.value = true
  await runNextFlowStep()
}

async function runBackendExecution() {
  if (!selectedCase.value) return
  if (!isPreviewMode.value && !selectedDeviceIp.value) {
    ElMessage.warning('请选择执行设备')
    return
  }
  isCaseInfoCollapsed.value = true
  resetFlowPreview()
  executionLogs.value = []
  appendExecutionLog('info', '正式运行启动')
  appendExecutionLog('info', `运行命令: ${caseDraft.command || '-'}`)
  appendExecutionLog('info', `目标设备: ${selectedDeviceIp.value || '-'}`)
  runtimeFlowNodes.value = resolveFlowPreviewNodes()
  runtimeStepIndex.value = 0
  isFlowPreviewRunning.value = true

  try {
    const response = await testCaseService.startExecution({
      case_id: selectedCase.value.id,
      device_ip: selectedDeviceIp.value
    })
    activeExecutionRun.value = response.data
    applyBackendRunState(response.data)
    startExecutionPolling(response.data.id)
    await refreshExecutionStatus()
  } catch (error) {
    console.error(error)
    resetFlowPreview()
    ElMessage.error('测试运行启动失败')
  }
}

async function runNextFlowStep() {
  const node = runtimeFlowNodes.value[runtimeStepIndex.value]
  if (!node) {
    await completeActiveExecution('passed', '流程执行完成')
    return
  }

  runningNodeId.value = node.id
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
  appendExecutionLog('info', `节点开始: ${node.name}`)

  const duration = node.kind === 'expect' ? 700 : 500
  flowPreviewTimer = window.setTimeout(() => {
    void handleRuntimeNodeReady(node)
  }, duration)
}

async function handleRuntimeNodeReady(node: TestCaseNode) {
  if (needsRuntimeInput(node)) {
    waitingInputNode.value = node
    runtimeInputValue.value = defaultRuntimeInputValue(node)
    appendExecutionLog('warn', `命中 Expect: ${node.expect || node.name}，等待用户输入`)
    return
  }

  completeRuntimeNode(node)
  runtimeStepIndex.value += 1
  await runNextFlowStep()
}

function needsRuntimeInput(node: TestCaseNode) {
  return node.kind === 'expect' && node.input_kind !== 'none'
}

function defaultRuntimeInputValue(node: TestCaseNode) {
  if (node.input_kind === 'boolean') return node.input_options[0]?.value ?? 'y'
  if (node.input_kind === 'radio') return node.input_options[0]?.value ?? ''
  return ''
}

function cloneInputOptions(options: TestCaseInputOption[]) {
  return options.map((option) => ({ ...option }))
}

function startExecutionPolling(runId: string) {
  stopExecutionPolling()
  executionPollTimer = window.setInterval(() => {
    void pollExecutionRun(runId)
  }, 800)
}

async function pollExecutionRun(runId = activeExecutionRun.value?.id) {
  if (!runId) return
  try {
    const response = await testCaseService.getExecutionRun(runId)
    activeExecutionRun.value = response.data
    applyBackendRunState(response.data)
    await refreshExecutionStatus()
  } catch (error) {
    console.error(error)
    stopExecutionPolling()
    isFlowPreviewRunning.value = false
    ElMessage.error('运行状态同步失败')
  }
}

function applyBackendRunState(run: TestExecutionRun) {
  syncRunLogs(run)
  const nodeMap = new Map(caseDraft.nodes.map((node) => [node.id, node]))
  const currentNode = run.current_node_id ? nodeMap.get(run.current_node_id) : null
  const waitingNode = run.waiting_node_id ? nodeMap.get(run.waiting_node_id) : null

  runningNodeId.value = isTerminalExecutionStatus(run.status) ? null : run.current_node_id ?? null
  selectedNodeId.value = run.current_node_id ?? selectedNodeId.value
  selectedEdgeId.value = null
  waitingInputNode.value = waitingNode ?? null
  if (waitingNode) {
    runtimeInputValue.value = defaultRuntimeInputValue(waitingNode)
  }

  const orderedNodes = resolveFlowPreviewNodes()
  const currentIndex = currentNode ? orderedNodes.findIndex((node) => node.id === currentNode.id) : -1
  if (currentIndex >= 0) {
    completedNodeIds.value = orderedNodes.slice(0, currentIndex).map((node) => node.id)
  }

  if (isTerminalExecutionStatus(run.status)) {
    stopExecutionPolling()
    isFlowPreviewRunning.value = false
    waitingInputNode.value = null
    if (run.status === 'passed') {
      completedNodeIds.value = orderedNodes.map((node) => node.id)
    }
  } else {
    isFlowPreviewRunning.value = true
  }
}

function isTerminalExecutionStatus(status: TestExecutionRun['status']) {
  return ['passed', 'failed', 'error', 'timeout', 'stopped'].includes(status)
}

async function submitRuntimeInput(value: string) {
  const node = waitingInputNode.value
  if (!node) return

  try {
    if (!isPreviewMode.value) {
      const run = activeExecutionRun.value
      if (!run) return
      const response = await testCaseService.submitExecutionInput(run.id, {
        node_id: node.id,
        value
      })
      activeExecutionRun.value = response.data
      syncRunLogs(response.data)
    }
    appendExecutionLog('input', `用户输入: ${value || '(空字符串)'}`)
    waitingInputNode.value = null
    runtimeInputValue.value = ''
    if (!isPreviewMode.value) {
      await refreshExecutionStatus()
      await pollExecutionRun()
      return
    }
    completeRuntimeNode(node)
    runtimeStepIndex.value += 1
    await runNextFlowStep()
  } catch (error) {
    console.error(error)
    ElMessage.error('输入发送失败')
  }
}

async function stopActiveExecution() {
  const run = activeExecutionRun.value
  if (!run || !canStopExecution.value) return

  stoppingExecution.value = true
  try {
    appendExecutionLog('warn', '正在停止 SSH session')
    const response = await testCaseService.stopExecution(run.id)
    activeExecutionRun.value = response.data
    applyBackendRunState(response.data)
    await refreshExecutionStatus()
    ElMessage.success('测试已停止')
  } catch (error) {
    console.error(error)
    ElMessage.error('停止测试失败')
  } finally {
    stoppingExecution.value = false
  }
}

function completeRuntimeNode(node: TestCaseNode) {
  if (!completedNodeIds.value.includes(node.id)) {
    completedNodeIds.value = [...completedNodeIds.value, node.id]
  }
  appendExecutionLog('success', `节点完成: ${node.name}`)
}

async function completeActiveExecution(
  status: 'passed' | 'failed' | 'error' | 'timeout' | 'stopped',
  message?: string
) {
  const run = activeExecutionRun.value
  runningNodeId.value = null
  waitingInputNode.value = null
  isFlowPreviewRunning.value = false
  appendExecutionLog(status === 'passed' ? 'success' : 'error', message ?? status)
  if (isPreviewMode.value || !run) return

  try {
    const response = await testCaseService.completeExecution(run.id, {
      status,
      message: message ?? null
    })
    activeExecutionRun.value = response.data
    syncRunLogs(response.data)
    await refreshExecutionStatus()
  } catch (error) {
    console.error(error)
  }
}

async function refreshExecutionStatus() {
  try {
    const response = await testCaseService.getExecutionStatus()
    executionStatus.value = response.data
  } catch (error) {
    console.error(error)
  }
}

function addNode() {
  const expectNodes = caseDraft.nodes.filter((node) => node.kind === 'expect')
  const lastExpect = expectNodes[expectNodes.length - 1]
  const sourceNode = lastExpect ?? caseDraft.nodes.find((node) => node.kind === 'start')
  const nextIndex = expectNodes.length + 1
  const insertX = sourceNode ? sourceNode.position.x + 220 : 330
  const insertY = sourceNode ? sourceNode.position.y + (nextIndex % 2 === 0 ? 120 : 0) : 160

  const node: TestCaseNode = {
    id: createId('expect'),
    name: `等待输出 ${expectNodes.length + 1}`,
    kind: 'expect',
    expect: '',
    input_kind: 'text',
    input_options: [{ label: '输入字符串', value: '' }],
    position: {
      x: Math.max(24, insertX),
      y: Math.max(24, insertY)
    }
  }
  caseDraft.nodes.push(node)
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
  isNodeDrawerPinnedClosed.value = true
  if (sourceNode) {
    addEdge(sourceNode.id, node.id, false)
  }
}

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
  selectedEdgeId.value = null
}

function openNodeDrawer(nodeId: string) {
  selectedNodeId.value = nodeId
  selectedEdgeId.value = null
  isNodeDrawerPinnedClosed.value = false
}

function closeNodeDrawer() {
  isNodeDrawerPinnedClosed.value = true
}

function updateSelectedNodeInputKind(value: TestInputKind) {
  if (!selectedNode.value) return
  selectedNode.value.input_kind = value
  if (value === 'boolean') {
    ensureBooleanOptions(selectedNode.value)
  } else if (value === 'text') {
    selectedNode.value.input_options = [{ label: '输入字符串', value: '' }]
  } else if (value === 'radio') {
    ensureRadioOptions(selectedNode.value)
  } else {
    selectedNode.value.input_options = []
  }
}

function ensureBooleanOptions(node: TestCaseNode) {
  const options: TestCaseInputOption[] = node.input_options.length >= 2
    ? node.input_options
    : [
        { label: '是', value: 'y' },
        { label: '否', value: 'n' }
      ]
  options[0] = { label: '是', value: options[0]?.value ?? 'y' }
  options[1] = { label: '否', value: options[1]?.value ?? 'n' }
  node.input_options = options.slice(0, 2)
}

function ensureRadioOptions(node: TestCaseNode) {
  const options = node.input_options.length > 0
    ? node.input_options
    : [{ label: '选项 1', value: '' }]

  node.input_options = options.map((option, index) => ({
    label: `选项 ${index + 1}`,
    value: option.value ?? ''
  }))
}

function addSelectedRadioOption() {
  if (!selectedNode.value) return
  ensureRadioOptions(selectedNode.value)
  selectedNode.value.input_options.push({
    label: `选项 ${selectedNode.value.input_options.length + 1}`,
    value: ''
  })
}

function removeSelectedRadioOption(index: number) {
  if (!selectedNode.value || selectedNode.value.input_options.length <= 1) return
  selectedNode.value.input_options.splice(index, 1)
  ensureRadioOptions(selectedNode.value)
}

function deleteSelectedNode() {
  if (!selectedNode.value || selectedNode.value.kind !== 'expect') return
  const deleteId = selectedNode.value.id
  caseDraft.nodes = caseDraft.nodes.filter((node) => node.id !== deleteId)
  caseDraft.edges = caseDraft.edges.filter((edge) => edge.source !== deleteId && edge.target !== deleteId)
  selectedEdgeId.value = null
  selectedNodeId.value = caseDraft.nodes.find((node) => node.kind === 'expect')?.id ?? caseDraft.nodes[0]?.id ?? null
  resetFlowPreview()
}

function startResize(event: PointerEvent) {
  event.preventDefault()
  const startX = event.clientX
  const startWidth = treeWidth.value

  const handleMove = (moveEvent: PointerEvent) => {
    const nextWidth = startWidth + moveEvent.clientX - startX
    treeWidth.value = Math.min(TREE_MAX_WIDTH, Math.max(TREE_MIN_WIDTH, nextWidth))
  }

  const stopResize = () => {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stopResize)
    document.body.classList.remove('is-resizing-test-tree')
  }

  document.body.classList.add('is-resizing-test-tree')
  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', stopResize)
}

function nodeCenter(node: TestCaseNode): CanvasPoint {
  return {
    x: node.position.x + NODE_WIDTH / 2,
    y: node.position.y + NODE_HEIGHT / 2
  }
}

function nodeEdgePoint(node: TestCaseNode, toward: CanvasPoint): CanvasPoint {
  const center = nodeCenter(node)
  const dx = toward.x - center.x
  const dy = toward.y - center.y
  const distance = Math.hypot(dx, dy) || 1
  const unit = { x: dx / distance, y: dy / distance }
  const halfWidth = NODE_WIDTH / 2
  const halfHeight = NODE_HEIGHT / 2
  const scale = Math.min(
    Math.abs(dx) > 0 ? halfWidth / Math.abs(unit.x) : Number.POSITIVE_INFINITY,
    Math.abs(dy) > 0 ? halfHeight / Math.abs(unit.y) : Number.POSITIVE_INFINITY
  )

  return {
    x: center.x + unit.x * scale,
    y: center.y + unit.y * scale
  }
}

function curvePath(start: CanvasPoint, end: CanvasPoint) {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const distance = Math.hypot(dx, dy) || 1
  const unit = { x: dx / distance, y: dy / distance }
  const curve = Math.min(180, Math.max(80, distance * 0.35))
  const controlA = {
    x: start.x + unit.x * curve,
    y: start.y + unit.y * curve
  }
  const controlB = {
    x: end.x - unit.x * curve,
    y: end.y - unit.y * curve
  }

  return `M ${start.x} ${start.y} C ${controlA.x} ${controlA.y}, ${controlB.x} ${controlB.y}, ${end.x} ${end.y}`
}

function edgePath(edge: TestCaseEdge) {
  const source = caseDraft.nodes.find((node) => node.id === edge.source)
  const target = caseDraft.nodes.find((node) => node.id === edge.target)
  if (!source || !target) return ''

  const targetCenter = nodeCenter(target)
  const sourceCenter = nodeCenter(source)
  const start = nodeEdgePoint(source, targetCenter)
  const targetEdge = nodeEdgePoint(target, sourceCenter)
  const dx = targetEdge.x - start.x
  const dy = targetEdge.y - start.y
  const distance = Math.hypot(dx, dy) || 1
  const end = {
    x: targetEdge.x - (dx / distance) * 9,
    y: targetEdge.y - (dy / distance) * 9
  }

  return curvePath(start, end)
}

function canvasPointFromEvent(event: PointerEvent): CanvasPoint {
  const surface = canvasSurfaceRef.value
  if (!surface) {
    return { x: event.offsetX, y: event.offsetY }
  }
  const rect = surface.getBoundingClientRect()
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }
}

function startConnection(event: PointerEvent, nodeId: string) {
  if (event.button !== 0) return
  event.preventDefault()
  event.stopPropagation()
  selectedNodeId.value = nodeId
  selectedEdgeId.value = null
  isNodeDrawerPinnedClosed.value = true
  connectionDraft.value = {
    sourceId: nodeId,
    pointer: canvasPointFromEvent(event)
  }

  const handleMove = (moveEvent: PointerEvent) => {
    if (!connectionDraft.value) return
    connectionDraft.value = {
      ...connectionDraft.value,
      pointer: canvasPointFromEvent(moveEvent)
    }
  }

  const stopConnection = (upEvent: PointerEvent) => {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stopConnection)
    document.body.classList.remove('is-connecting-test-edge')

    const target = (upEvent.target as HTMLElement | null)?.closest<HTMLElement>('.node-port')
    const targetNodeId = target?.dataset.nodeId
    if (targetNodeId) {
      finishConnection(targetNodeId)
      return
    }
    cancelConnection()
  }

  document.body.classList.add('is-connecting-test-edge')
  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', stopConnection)
}

function finishConnection(targetNodeId: string) {
  const sourceId = connectionDraft.value?.sourceId
  cancelConnection()
  if (!sourceId || sourceId === targetNodeId) return
  addEdge(sourceId, targetNodeId)
}

function cancelConnection() {
  connectionDraft.value = null
  document.body.classList.remove('is-connecting-test-edge')
}

function startNodeDrag(event: PointerEvent, node: TestCaseNode) {
  if (event.button !== 0) return
  event.preventDefault()
  const startX = event.clientX
  const startY = event.clientY
  const startPosition = { ...node.position }

  const handleMove = (moveEvent: PointerEvent) => {
    node.position.x = Math.max(24, startPosition.x + moveEvent.clientX - startX)
    node.position.y = Math.max(24, startPosition.y + moveEvent.clientY - startY)
  }

  const stopDrag = () => {
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stopDrag)
    document.body.classList.remove('is-dragging-test-node')
  }

  selectedNodeId.value = node.id
  selectedEdgeId.value = null
  document.body.classList.add('is-dragging-test-node')
  window.addEventListener('pointermove', handleMove)
  window.addEventListener('pointerup', stopDrag)
}

onMounted(async () => {
  robotScanStore.loadFromCache()
  syncRobotsFromStore()
  if (initialDeviceIp.value) {
    ensureDeviceInList(initialDeviceIp.value)
    selectedDeviceIp.value = initialDeviceIp.value
  } else {
    selectedDeviceIp.value = availableRobots.value[0]?.ip ?? null
  }
  await loadAll()
  if (initialCaseId.value) {
    await selectCase(initialCaseId.value)
  }
})

onBeforeUnmount(() => {
  document.body.classList.remove('is-resizing-test-tree')
  document.body.classList.remove('is-dragging-test-node')
  cancelConnection()
  resetFlowPreview()
})
</script>

<style scoped>
.test-case-page {
  --tree-width: 320px;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: var(--tree-width) 1px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) 28px;
  background: #eef2f6;
  color: #1f2937;
  text-align: left;
}

.tree-pane {
  grid-column: 1;
  grid-row: 1;
}

.tree-resizer {
  grid-column: 2;
  grid-row: 1;
}

.editor-pane {
  grid-column: 3;
  grid-row: 1;
}

.tree-pane,
.editor-pane {
  min-height: 0;
  overflow: hidden;
}

.tree-resizer {
  position: relative;
  width: 1px;
  padding: 0;
  border: 0;
  background: #dce3eb;
  cursor: col-resize;
}

.tree-resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -4px;
  width: 9px;
  background: transparent;
}

.tree-resizer:hover {
  background: #cbd6e2;
}

.editor-pane {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.editor-head {
  height: 64px;
  flex: 0 0 64px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 20px;
  padding: 0 22px;
  background: #f8fafc;
  border-bottom: 1px solid #dce3eb;
}

.editor-head h1 {
  margin: 0;
  color: #142033;
  font-size: 18px;
  font-weight: 750;
  line-height: 1.15;
}

.case-subtitle {
  display: inline-flex;
  margin-top: 3px;
  color: #687386;
  font-size: 12px;
  line-height: 1.2;
}

.head-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(54px, auto));
  gap: 12px;
  align-items: center;
  padding: 0 18px;
  border-left: 1px solid #dce3eb;
  border-right: 1px solid #dce3eb;
}

.head-metrics div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.head-metrics span {
  color: #6b778a;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.head-metrics strong {
  color: #172033;
  font-size: 14px;
  line-height: 1.1;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.case-detail {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.editor-main {
  min-height: 0;
  overflow: auto;
}

.editor-main {
  min-width: 0;
  height: 100%;
  padding: 0 20px 20px;
}

.node-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
  width: 300px;
  overflow: auto;
  border-left: 1px solid #dce3eb;
  background: #eef2f6;
  padding: 0 16px 20px;
  box-shadow: -12px 0 24px rgba(37, 54, 74, 0.06);
}

.section-title,
.block-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #172033;
  font-size: 14px;
  font-weight: 800;
}

.section-title small {
  color: #c27803;
  font-size: 12px;
  font-weight: 800;
}

.title-with-toggle {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.section-toggle {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: #7a8596;
  font: inherit;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

.section-toggle:hover {
  color: #172033;
}

.flow-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-select {
  width: 210px;
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.drawer-close {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: #7a8596;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.drawer-close:hover {
  color: #172033;
}

.case-editor-section {
  padding: 18px 0;
  border-bottom: 1px solid #dce3eb;
}

.flow-section {
  padding: 18px 0 0;
}

.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px 150px;
  gap: 12px;
  margin-top: 12px;
}

.edit-field {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #5d6879;
  font-size: 12px;
  font-weight: 800;
}

.edit-field.is-wide {
  grid-column: span 1;
}

.edit-field.is-full {
  grid-column: 1 / -1;
}

.edit-field :deep(.el-input-number) {
  width: 100%;
}

.edit-field :deep(.el-input__wrapper),
.edit-field :deep(.el-select__wrapper),
.edit-field :deep(.el-textarea__inner) {
  box-shadow: 0 0 0 1px #d9e1ea inset;
}

.node-canvas {
  position: relative;
  height: 430px;
  margin-top: 12px;
  overflow: auto;
  border: 1px solid #dce3eb;
  background: #eef3f8;
}

.node-canvas-surface {
  position: relative;
  min-width: 100%;
  min-height: 100%;
  background:
    linear-gradient(#eef3f8 1px, transparent 1px),
    linear-gradient(90deg, #eef3f8 1px, transparent 1px),
    #f8fafc;
  background-size: 24px 24px;
}

.flow-edges {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.flow-edges marker#flow-arrow path {
  fill: #8da0b6;
}

.flow-edges marker#flow-arrow-complete path {
  fill: #2f9e73;
}

.flow-edges marker#flow-arrow-selected path {
  fill: #276fbf;
}

.flow-edge-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 16;
  pointer-events: stroke;
  cursor: context-menu;
}

.flow-edge {
  fill: none;
  stroke: #8da0b6;
  stroke-width: 2;
  marker-end: url('#flow-arrow');
  transition: stroke 0.2s ease;
  pointer-events: none;
}

.flow-edge.is-complete {
  stroke: #2f9e73;
  marker-end: url('#flow-arrow-complete');
}

.flow-edge.is-selected {
  stroke: #276fbf;
  stroke-width: 3;
  marker-end: url('#flow-arrow-selected');
}

.flow-edge-preview {
  fill: none;
  stroke: #276fbf;
  stroke-width: 2;
  stroke-dasharray: 6 6;
  pointer-events: none;
}

.flow-node {
  position: absolute;
  width: 156px;
  min-height: 84px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 5px;
  padding: 12px;
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  background: #ffffff;
  color: #172033;
  box-shadow: 0 8px 18px rgba(37, 54, 74, 0.08);
  cursor: grab;
}

.node-canvas-surface.is-connecting .flow-node {
  cursor: crosshair;
}

.flow-node.is-start {
  border-color: #83c7ad;
}

.flow-node.is-expect {
  border-color: #8fb3d9;
}

.flow-node.is-end {
  border-color: #c9ced8;
}

.flow-node.is-selected {
  border-color: #276fbf;
  box-shadow: 0 0 0 3px rgba(39, 111, 191, 0.12), 0 8px 18px rgba(37, 54, 74, 0.08);
}

.flow-node.is-running {
  border-color: #276fbf;
  box-shadow: 0 0 0 4px rgba(39, 111, 191, 0.16), 0 10px 22px rgba(37, 54, 74, 0.12);
}

.flow-node.is-waiting-input {
  z-index: 4;
}

.flow-node.is-running::after {
  content: '';
  position: absolute;
  inset: -6px;
  border: 1px solid rgba(39, 111, 191, 0.32);
  animation: nodePulse 1s ease-out infinite;
  pointer-events: none;
}

.flow-node.is-complete {
  border-color: #2f9e73;
}

.node-tools {
  position: absolute;
  top: 8px;
  right: 8px;
}

.node-tool-button {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #7b8798;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: background 0.16s ease, color 0.16s ease, opacity 0.16s ease;
}

.flow-node:hover .node-tool-button,
.flow-node.is-selected .node-tool-button {
  opacity: 1;
}

.node-tool-button:hover {
  background: #edf3fa;
  color: #276fbf;
}

.node-input-popover {
  position: absolute;
  left: 50%;
  top: calc(100% + 10px);
  z-index: 5;
  width: 240px;
  padding: 0;
  overflow: hidden;
  border: 1px solid #cad6e4;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 12px 28px rgba(37, 54, 74, 0.14);
  transform: translateX(-50%);
  cursor: default;
}

.node-input-popover::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  width: 10px;
  height: 10px;
  border-top: 1px solid #cad6e4;
  border-left: 1px solid #cad6e4;
  background: #ffffff;
  transform: translateX(-50%) rotate(45deg);
}

.node-input-title {
  padding: 9px 10px;
  border-bottom: 1px solid #e4ebf3;
  background: #f8fafc;
  color: #172033;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
}

.runtime-choice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
}

.runtime-option-list,
.runtime-text-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.runtime-option-button {
  width: 100%;
  justify-content: flex-start;
  margin-left: 0 !important;
  padding: 0 10px;
}

.runtime-choice-grid .runtime-option-button {
  justify-content: center;
}

.runtime-option-button :deep(span) {
  min-width: 0;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-port {
  position: absolute;
  z-index: 2;
  width: 10px;
  height: 10px;
  border: 2px solid #ffffff;
  border-radius: 50%;
  background: #8aa0b8;
  box-shadow: 0 1px 3px rgba(23, 32, 51, 0.24);
  opacity: 0;
  transition: opacity 0.16s ease, background 0.16s ease, transform 0.16s ease;
  cursor: crosshair;
}

.flow-node:hover .node-port,
.flow-node.is-selected .node-port,
.node-canvas-surface.is-connecting .node-port {
  opacity: 1;
}

.node-port:hover {
  background: #276fbf;
}

.node-port.is-top {
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
}

.node-port.is-right {
  top: 50%;
  right: -6px;
  transform: translateY(-50%);
}

.node-port.is-bottom {
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
}

.node-port.is-left {
  top: 50%;
  left: -6px;
  transform: translateY(-50%);
}

.node-port.is-top:hover,
.node-port.is-bottom:hover {
  transform: translateX(-50%) scale(1.18);
}

.node-port.is-right:hover,
.node-port.is-left:hover {
  transform: translateY(-50%) scale(1.18);
}

@keyframes nodePulse {
  from {
    opacity: 0.9;
    transform: scale(0.98);
  }

  to {
    opacity: 0;
    transform: scale(1.08);
  }
}

.node-kind {
  color: #6d7a8d;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  text-transform: uppercase;
}

.flow-node strong,
.flow-node small {
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flow-node strong {
  color: #162033;
  font-size: 14px;
  line-height: 1.2;
}

.flow-node small {
  color: #657386;
  font-size: 12px;
  line-height: 1.25;
}

.status-block {
  padding: 18px 0;
  border-bottom: 1px solid #dce3eb;
}

.status-block + .status-block {
  margin-top: 0;
}

.block-title small {
  color: #6b778a;
  font-size: 12px;
  font-weight: 700;
}

.session-meter {
  height: 8px;
  overflow: hidden;
  margin: 14px 0;
  border-radius: 999px;
  background: #e4eaf1;
}

.session-meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #2f9e73;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.status-grid div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-grid strong {
  color: #172033;
  font-size: 20px;
  line-height: 1.1;
}

.status-grid span {
  color: #6b778a;
  font-size: 12px;
  line-height: 1.35;
}

.node-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.node-form label,
.boolean-grid label {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #5d6879;
  font-size: 12px;
  font-weight: 800;
}

.node-form :deep(.el-input__wrapper),
.node-form :deep(.el-select__wrapper),
.node-form :deep(.el-textarea__inner) {
  box-shadow: 0 0 0 1px #d9e1ea inset;
}

.boolean-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.radio-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-list-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #5d6879;
  font-size: 12px;
  font-weight: 800;
}

.radio-option-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 6px;
}

.muted-copy {
  margin: 12px 0 0;
  color: #6b778a;
  font-size: 12px;
  line-height: 1.4;
}

.empty-editor {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  background: #eef2f6;
}

.test-footer {
  grid-column: 1 / -1;
  grid-row: 2;
  min-width: 0;
  height: 28px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 14px;
  border-top: 1px solid #dce3eb;
  background: #f8fafc;
  color: #6b778a;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
}

.test-footer span:first-child {
  color: #172033;
  font-weight: 800;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dialog-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #4b5563;
  font-size: 13px;
  font-weight: 700;
}

.log-dialog-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: -4px 0 10px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.execution-log-panel {
  height: 520px;
  overflow: auto;
  padding: 12px;
  border: 1px solid #dce3eb;
  border-radius: 6px;
  background: #0f1720;
  color: #d7e1ee;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
}

.log-empty {
  height: 100%;
  display: grid;
  place-items: center;
  color: #75849a;
}

.log-line {
  display: grid;
  grid-template-columns: 76px 58px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-height: 20px;
}

.log-time {
  color: #7f8ea3;
}

.log-level {
  color: #9fb1c8;
  font-weight: 800;
  text-transform: uppercase;
}

.log-message {
  min-width: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-line.is-input .log-level,
.log-line.is-input .log-message {
  color: #8bd3ff;
}

.log-line.is-output .log-level,
.log-line.is-output .log-message {
  color: #d7e1ee;
}

.log-line.is-warn .log-level,
.log-line.is-warn .log-message {
  color: #facc6b;
}

.log-line.is-error .log-level,
.log-line.is-error .log-message {
  color: #ff9a9a;
}

.log-line.is-success .log-level,
.log-line.is-success .log-message {
  color: #8de0b5;
}

@media (max-width: 1120px) {
  .editor-head {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .head-metrics {
    display: none;
  }

  .node-drawer {
    width: min(300px, 86vw);
  }
}
</style>

<style>
body.is-resizing-test-tree {
  cursor: col-resize;
  user-select: none;
}

body.is-dragging-test-node {
  cursor: grabbing;
  user-select: none;
}
</style>
