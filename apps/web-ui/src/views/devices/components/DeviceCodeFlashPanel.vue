<template>
  <section class="code-flash-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <div class="flash-intro">
        <div>
          <div class="section-title">烧录当前设备代码</div>
          <div class="section-description">服务器在 Opentrons 源码目录执行 make，并将 host 固定为当前设备。</div>
        </div>
        <el-tag :type="repositoryAvailable ? 'success' : 'danger'" effect="plain">
          {{ repositoryAvailable ? repositoryPath : '源码目录不可用' }}
        </el-tag>
      </div>

      <el-alert
        v-if="repositoryError"
        type="error"
        :closable="false"
        :title="repositoryError"
        class="flash-alert"
      />

      <div class="flash-form-grid">
        <label class="flash-field branch-field">
          <span>Git 分支</span>
          <div class="branch-select-row">
            <el-select
              v-model="selectedBranch"
              filterable
              placeholder="选择服务器源码分支"
            >
              <el-option
                v-for="branch in branches"
                :key="branch.name"
                :label="branch.name"
                :value="branch.name"
              >
                <div class="branch-option">
                  <strong>{{ branch.name }}</strong>
                  <el-tag v-if="branch.current" size="small" type="success">当前</el-tag>
                  <el-tag v-if="branch.local" size="small" type="info">本地</el-tag>
                  <el-tag v-if="branch.remote" size="small" effect="plain">远程</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-tooltip content="刷新分支与工作区状态" placement="top">
              <el-button :icon="Refresh" :loading="loadingPresets" circle @click.prevent="loadPresets" />
            </el-tooltip>
          </div>
        </label>

        <div class="pull-field">
          <span>远程同步</span>
          <el-checkbox v-model="pullBeforeFlash">切换分支后 Pull</el-checkbox>
        </div>

        <label class="flash-field preset-field">
          <span>预设命令</span>
          <el-select
            v-model="selectedPresetId"
            clearable
            filterable
            placeholder="选择预设，或直接编辑下方 make 命令"
            @change="applyPreset"
          >
            <el-option
              v-for="preset in presets"
              :key="preset.id"
              :label="preset.name"
              :value="preset.id"
            >
              <div class="preset-option">
                <strong>{{ preset.name }}</strong>
                <small>{{ preset.description }}</small>
              </div>
            </el-option>
          </el-select>
        </label>

        <label class="flash-field command-field">
          <span>Make 命令</span>
          <el-input
            v-model="makeCommand"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            placeholder="make push-ot3 host={robot_ip}"
          />
        </label>

        <label class="flash-field timeout-field">
          <span>超时（秒）</span>
          <el-input-number
            v-model="timeoutSeconds"
            :min="30"
            :max="7200"
            :step="60"
            controls-position="right"
          />
        </label>

        <div class="target-summary">
          <span>目标设备</span>
          <strong>{{ ip }}</strong>
        </div>
      </div>

      <el-alert
        v-if="!repositoryClean"
        type="warning"
        :closable="false"
        title="服务器 Git 工作区当前不干净，任务启动后会停止烧录。"
        class="flash-alert"
      >
        <template #default>
          <div class="dirty-file-list">
            <code v-for="file in dirtyFiles.slice(0, 5)" :key="file">{{ file }}</code>
          </div>
        </template>
      </el-alert>

      <div class="flash-actions">
        <el-button
          type="primary"
          :loading="starting || isRunning"
          :disabled="!canStart"
          @click="startFlash"
        >
          开始烧录
        </el-button>
        <span class="command-safety-note">
          先切换 {{ selectedBranch || '-' }}{{ pullBeforeFlash ? ' 并 Pull' : '' }}，再执行 make；host={{ ip }}
        </span>
      </div>

      <section v-if="task" class="flash-result" :class="`is-${task.status}`">
        <div class="flash-result-header">
          <div>
            <div class="section-title">烧录任务</div>
            <div class="flash-command">{{ task.command }}</div>
          </div>
          <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
        </div>

        <el-descriptions :column="3" border size="small" class="flash-meta">
          <el-descriptions-item label="设备">{{ task.ip }}</el-descriptions-item>
          <el-descriptions-item label="分支">{{ task.branch }}</el-descriptions-item>
          <el-descriptions-item label="远程同步">{{ task.pull ? 'Pull' : '跳过' }}</el-descriptions-item>
          <el-descriptions-item label="退出码">{{ task.exit_code ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(task.duration_ms) }}</el-descriptions-item>
          <el-descriptions-item label="结果">{{ task.message }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse v-model="expandedSections" class="flash-log-collapse">
          <el-collapse-item name="logs">
            <template #title>
              <span class="flash-log-title">
                执行 Log
                <el-tag v-if="isRunning" size="small" type="warning">实时输出</el-tag>
                <small>{{ task.logs.length }} 行</small>
              </span>
            </template>
            <div ref="logConsoleRef" class="flash-log-console">
              <pre>{{ task.logs.length ? task.logs.join('\n') : '等待 make 输出...' }}</pre>
            </div>
            <div v-if="task.output_truncated" class="flash-log-truncated">日志已达到平台长度限制，后续输出未显示。</div>
          </el-collapse-item>
        </el-collapse>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  robotApi,
  type RobotCodeFlashBranch,
  type RobotCodeFlashPreset,
  type RobotCodeFlashTask
} from '@/scripts/api'

const props = defineProps<{
  ip: string | null
}>()

const presets = ref<RobotCodeFlashPreset[]>([])
const branches = ref<RobotCodeFlashBranch[]>([])
const selectedBranch = ref('')
const pullBeforeFlash = ref(false)
const selectedPresetId = ref('all-flex-services')
const makeCommand = ref('')
const timeoutSeconds = ref(1800)
const repositoryPath = ref('/opentrons')
const repositoryAvailable = ref(false)
const repositoryError = ref('')
const repositoryClean = ref(true)
const dirtyFiles = ref<string[]>([])
const loadingPresets = ref(false)
const starting = ref(false)
const task = ref<RobotCodeFlashTask | null>(null)
const expandedSections = ref<string[]>([])
const logConsoleRef = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const isRunning = computed(() => ['queued', 'running'].includes(task.value?.status || ''))
const canStart = computed(() => Boolean(
  props.ip
  && repositoryAvailable.value
  && repositoryClean.value
  && selectedBranch.value
  && makeCommand.value.trim()
  && !loadingPresets.value
  && !starting.value
  && !isRunning.value
))

const statusLabel = computed(() => {
  if (task.value?.status === 'queued') return '等待中'
  if (task.value?.status === 'running') return '烧录中'
  if (task.value?.status === 'success') return '烧录成功'
  return '烧录失败'
})

const statusTagType = computed(() => {
  if (task.value?.status === 'success') return 'success'
  if (task.value?.status === 'failed') return 'danger'
  if (task.value?.status === 'running') return 'warning'
  return 'info'
})

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

function applyPreset(presetId: string) {
  const preset = presets.value.find(item => item.id === presetId)
  if (preset) makeCommand.value = preset.command
}

async function loadPresets() {
  if (loadingPresets.value) return
  loadingPresets.value = true
  try {
    const response = await robotApi.getCodeFlashPresets()
    presets.value = response.data.presets
    repositoryPath.value = response.data.workdir
    repositoryAvailable.value = response.data.available
    repositoryError.value = response.data.error || ''
    branches.value = response.data.branches || []
    selectedBranch.value = response.data.current_branch || response.data.branches?.[0]?.name || ''
    repositoryClean.value = response.data.clean
    dirtyFiles.value = response.data.dirty_files || []
    if (!makeCommand.value.trim()) {
      applyPreset(selectedPresetId.value)
    }
  } catch (error: any) {
    repositoryAvailable.value = false
    repositoryError.value = '加载烧录配置失败: ' + normalizeError(error)
  } finally {
    loadingPresets.value = false
  }
}

function clearPollTimer() {
  if (!pollTimer) return
  clearTimeout(pollTimer)
  pollTimer = null
}

async function scrollLogToBottom() {
  await nextTick()
  if (logConsoleRef.value && expandedSections.value.includes('logs')) {
    logConsoleRef.value.scrollTop = logConsoleRef.value.scrollHeight
  }
}

async function pollTask(taskId: string, showError = false) {
  clearPollTimer()
  try {
    const response = await robotApi.getCodeFlashTask(taskId)
    task.value = response.data
    await scrollLogToBottom()
    if (['queued', 'running'].includes(response.data.status)) {
      pollTimer = setTimeout(() => pollTask(taskId), 1000)
      return
    }
    if (response.data.success) {
      ElMessage.success(response.data.message)
    } else {
      ElMessage.error(response.data.message)
    }
  } catch (error: any) {
    if (showError) ElMessage.error('读取烧录进度失败: ' + normalizeError(error))
    pollTimer = setTimeout(() => pollTask(taskId), 3000)
  }
}

async function startFlash() {
  const ip = props.ip
  if (!ip || !canStart.value) return
  try {
    await ElMessageBox.confirm(
      `即将在服务器 ${repositoryPath.value} 切换到 ${selectedBranch.value}${pullBeforeFlash.value ? '、拉取远程更新' : ''}，然后为 ${ip} 执行烧录。烧录期间请勿断电或断网。`,
      '确认烧录代码',
      {
        confirmButtonText: '开始烧录',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  starting.value = true
  task.value = null
  expandedSections.value = ['logs']
  try {
    const response = await robotApi.createCodeFlashTask({
      ip,
      command: makeCommand.value.trim(),
      timeout: timeoutSeconds.value,
      branch: selectedBranch.value,
      pull: pullBeforeFlash.value
    })
    task.value = response.data
    ElMessage.success('烧录任务已启动')
    await pollTask(response.data.task_id, true)
  } catch (error: any) {
    ElMessage.error('启动烧录失败: ' + normalizeError(error))
  } finally {
    starting.value = false
  }
}

function formatDuration(durationMs: number) {
  if (!durationMs) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  const seconds = Math.round(durationMs / 1000)
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}

watch(() => props.ip, () => {
  clearPollTimer()
  task.value = null
})

onMounted(loadPresets)
onBeforeUnmount(clearPollTimer)
</script>

<style scoped>
.code-flash-panel {
  min-height: 420px;
  padding: 8px 2px 28px;
  color: #1f2a37;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.flash-intro,
.flash-result-header,
.flash-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.flash-intro :deep(.el-tag) {
  max-width: 50%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-title {
  color: #1f2a37;
  font-size: 14px;
  font-weight: 650;
}

.section-description {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

.flash-alert {
  margin-top: 14px;
}

.flash-form-grid {
  max-width: 900px;
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 220px;
  gap: 14px;
  margin-top: 20px;
}

.flash-field {
  min-width: 0;
  display: grid;
  gap: 7px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.preset-field,
.command-field {
  grid-column: 1 / -1;
}

.branch-option {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.branch-select-row {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.branch-option strong {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pull-field {
  display: grid;
  align-content: start;
  gap: 7px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.pull-field :deep(.el-checkbox) {
  min-height: 32px;
  margin: 0;
}

.dirty-file-list {
  display: grid;
  gap: 3px;
  margin-top: 6px;
}

.dirty-file-list code {
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeout-field :deep(.el-input-number) {
  width: 100%;
}

.preset-option {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.preset-option strong {
  flex: none;
}

.preset-option small {
  overflow: hidden;
  color: #8491a3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.target-summary {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  border: 1px solid #e6ebf2;
  border-radius: 6px;
  background: #f7f9fc;
  color: #6b7280;
  font-size: 12px;
}

.target-summary strong {
  color: #1f2a37;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.flash-actions {
  justify-content: flex-start;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e6ebf2;
}

.command-safety-note {
  color: #8491a3;
  font-size: 12px;
}

.flash-result {
  margin-top: 22px;
  padding-top: 18px;
  border-top: 1px solid #e6ebf2;
}

.flash-command {
  max-width: min(760px, calc(100vw - 240px));
  margin-top: 5px;
  overflow: hidden;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.flash-meta {
  margin-top: 14px;
}

.flash-log-collapse {
  margin-top: 16px;
}

.flash-log-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
}

.flash-log-title small {
  color: #8491a3;
  font-size: 12px;
  font-weight: 500;
}

.flash-log-console {
  height: clamp(260px, 42vh, 520px);
  overflow: auto;
  border: 1px solid #253244;
  border-radius: 6px;
  background: #111827;
}

.flash-log-console pre {
  min-height: 100%;
  margin: 0;
  padding: 14px;
  color: #dbeafe;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.flash-log-truncated {
  margin-top: 8px;
  color: #b7791f;
  font-size: 12px;
}

@media (max-width: 760px) {
  .flash-intro,
  .flash-result-header,
  .flash-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .flash-intro :deep(.el-tag) {
    max-width: 100%;
  }

  .flash-form-grid {
    grid-template-columns: 1fr;
  }

  .preset-field,
  .command-field {
    grid-column: auto;
  }

  .flash-command {
    max-width: calc(100vw - 64px);
  }
}
</style>
