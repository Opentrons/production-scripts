<template>
  <section class="code-flash-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty :description="t('devices.selectOne')" />
    </div>

    <template v-else>
      <div class="flash-intro">
        <div>
          <div class="section-title">{{ t('devices.codeFlash.title') }}</div>
          <div class="section-description">{{ t('devices.codeFlash.description') }}</div>
        </div>
        <el-tag :type="repositoryAvailable ? 'success' : 'danger'" effect="plain">
          {{ repositoryAvailable ? repositoryPath : t('devices.codeFlash.repositoryUnavailable') }}
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
          <span>{{ t('devices.codeFlash.branch') }}</span>
          <div class="branch-select-row">
            <el-select
              v-model="selectedBranch"
              filterable
              :placeholder="t('devices.codeFlash.branchPlaceholder')"
            >
              <el-option
                v-for="branch in branches"
                :key="branch.name"
                :label="branch.name"
                :value="branch.name"
              >
                <div class="branch-option">
                  <strong>{{ branch.name }}</strong>
                  <el-tag v-if="branch.current" size="small" type="success">{{ t('devices.codeFlash.current') }}</el-tag>
                  <el-tag v-if="branch.local" size="small" type="info">{{ t('devices.codeFlash.local') }}</el-tag>
                  <el-tag v-if="branch.remote" size="small" effect="plain">{{ t('devices.codeFlash.remote') }}</el-tag>
                </div>
              </el-option>
            </el-select>
            <el-tooltip :content="t('devices.codeFlash.refreshRepository')" placement="top">
              <el-button :icon="Refresh" :loading="loadingPresets" circle @click.prevent="loadPresets" />
            </el-tooltip>
          </div>
        </label>

        <div class="pull-field">
          <span>{{ t('devices.codeFlash.remoteSync') }}</span>
          <el-checkbox v-model="pullBeforeFlash">{{ t('devices.codeFlash.pullAfterSwitch') }}</el-checkbox>
        </div>

        <label class="flash-field preset-field">
          <span>{{ t('devices.codeFlash.preset') }}</span>
          <el-select
            v-model="selectedPresetId"
            clearable
            filterable
            :placeholder="t('devices.codeFlash.presetPlaceholder')"
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
          <span>{{ t('devices.codeFlash.makeCommand') }}</span>
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
          <span>{{ t('devices.codeFlash.timeout') }}</span>
          <el-input-number
            v-model="timeoutSeconds"
            :min="30"
            :max="7200"
            :step="60"
            controls-position="right"
          />
        </label>

        <div class="target-summary">
          <span>{{ t('devices.codeFlash.target') }}</span>
          <strong>{{ ip }}</strong>
        </div>
      </div>

      <el-alert
        v-if="!repositoryClean"
        type="warning"
        :closable="false"
        :title="t('devices.codeFlash.dirtyWorkspace')"
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
          {{ t('devices.codeFlash.start') }}
        </el-button>
        <span class="command-safety-note">
          {{ pullBeforeFlash
            ? t('devices.codeFlash.safetyWithPull', { branch: selectedBranch || '-', ip })
            : t('devices.codeFlash.safetyWithoutPull', { branch: selectedBranch || '-', ip }) }}
        </span>
      </div>

      <section v-if="task" class="flash-result" :class="`is-${task.status}`">
        <div class="flash-result-header">
          <div>
            <div class="section-title">{{ t('devices.codeFlash.task') }}</div>
            <div class="flash-command">{{ task.command }}</div>
          </div>
          <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
        </div>

        <el-descriptions :column="3" border size="small" class="flash-meta">
          <el-descriptions-item :label="t('devices.codeFlash.device')">{{ task.ip }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.codeFlash.branch')">{{ task.branch }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.codeFlash.pull')">{{ task.pull ? 'Pull' : t('devices.codeFlash.skipped') }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.codeFlash.exitCode')">{{ task.exit_code ?? '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.codeFlash.duration')">{{ formatDuration(task.duration_ms) }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.codeFlash.result')">{{ task.message }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse v-model="expandedSections" class="flash-log-collapse">
          <el-collapse-item name="logs">
            <template #title>
              <span class="flash-log-title">
                {{ t('devices.codeFlash.executionLog') }}
                <el-tag v-if="isRunning" size="small" type="warning">{{ t('devices.codeFlash.liveOutput') }}</el-tag>
                <small>{{ t('devices.codeFlash.lines', { count: task.logs.length }) }}</small>
              </span>
            </template>
            <div ref="logConsoleRef" class="flash-log-console">
              <pre>{{ task.logs.length ? task.logs.join('\n') : t('devices.codeFlash.waitingOutput') }}</pre>
            </div>
            <div v-if="task.output_truncated" class="flash-log-truncated">{{ t('devices.codeFlash.logTruncated') }}</div>
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
import { useAppLocale } from '@/i18n'

const { t } = useAppLocale()

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
  if (task.value?.status === 'queued') return t('devices.codeFlash.statuses.queued')
  if (task.value?.status === 'running') return t('devices.codeFlash.statuses.running')
  if (task.value?.status === 'success') return t('devices.codeFlash.statuses.success')
  return t('devices.codeFlash.statuses.failed')
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
    || t('errors.unknown')
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
    repositoryError.value = t('devices.codeFlash.loadFailed', { error: normalizeError(error) })
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
    if (showError) ElMessage.error(t('devices.codeFlash.progressFailed', { error: normalizeError(error) }))
    pollTimer = setTimeout(() => pollTask(taskId), 3000)
  }
}

async function startFlash() {
  const ip = props.ip
  if (!ip || !canStart.value) return
  try {
    await ElMessageBox.confirm(
      t('devices.codeFlash.confirm', {
        path: repositoryPath.value,
        branch: selectedBranch.value,
        pull: pullBeforeFlash.value ? t('devices.codeFlash.pullRemote') : '',
        ip,
      }),
      t('devices.codeFlash.confirmTitle'),
      {
        confirmButtonText: t('devices.codeFlash.start'),
        cancelButtonText: t('common.actions.cancel'),
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
    ElMessage.success(t('devices.codeFlash.started'))
    await pollTask(response.data.task_id, true)
  } catch (error: any) {
    ElMessage.error(t('devices.codeFlash.startFailed', { error: normalizeError(error) }))
  } finally {
    starting.value = false
  }
}

function formatDuration(durationMs: number) {
  if (!durationMs) return '-'
  if (durationMs < 1000) return `${durationMs} ms`
  const seconds = Math.round(durationMs / 1000)
  if (seconds < 60) return t('devices.codeFlash.seconds', { count: seconds })
  return t('devices.codeFlash.minutesSeconds', { minutes: Math.floor(seconds / 60), seconds: seconds % 60 })
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
