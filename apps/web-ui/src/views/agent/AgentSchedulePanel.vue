<template>
  <section class="agent-panel">
    <header class="agent-panel-header">
      <div>
        <h2>{{ t('agent.schedules.title') }}</h2>
        <p>{{ t('agent.schedules.subtitle') }}</p>
      </div>
      <div class="agent-panel-actions">
        <button type="button" class="agent-panel-button" :disabled="loading" @click="refresh">
          <RefreshCw :size="15" aria-hidden="true" />
          {{ t('common.actions.refresh') }}
        </button>
        <button type="button" class="agent-panel-button is-primary" @click="openCreate">
          <Plus :size="15" aria-hidden="true" />
          {{ t('agent.schedules.create') }}
        </button>
      </div>
    </header>

    <p v-if="error" class="agent-panel-error">{{ error }}</p>
    <p v-else-if="!loading && !schedules.length" class="agent-panel-empty">{{ t('agent.schedules.empty') }}</p>

    <div v-loading="loading" class="agent-schedule-list">
      <article v-for="item in schedules" :key="item.id" class="agent-schedule-card">
        <header>
          <div>
            <strong>{{ item.name }}</strong>
            <span>
              {{ scheduleSummary(item) }}
              ·
              {{ item.enabled ? t('agent.schedules.enabled') : t('agent.schedules.disabled') }}
            </span>
          </div>
          <el-switch
            :model-value="item.enabled"
            @change="(value: string | number | boolean) => toggleEnabled(item, Boolean(value))"
          />
        </header>
        <p class="agent-schedule-desc">{{ item.description }}</p>
        <div class="agent-schedule-meta">
          <span>{{ t('agent.schedules.nextRun') }}：{{ formatTime(item.next_run_at) }}</span>
          <span>{{ t('agent.schedules.lastRun') }}：{{ formatTime(item.last_run_at) }}</span>
          <span v-if="item.last_status">{{ t('agent.schedules.lastStatus') }}：{{ statusLabel(item.last_status) }}</span>
        </div>
        <p v-if="item.last_result_preview" class="agent-schedule-preview">{{ item.last_result_preview }}</p>
        <footer class="agent-panel-actions">
          <button type="button" class="agent-panel-button" @click="editSchedule(item)">{{ t('common.actions.edit') }}</button>
          <button type="button" class="agent-panel-button" :disabled="runningId === item.id" @click="runNow(item)">
            {{ t('agent.schedules.runNow') }}
          </button>
          <button type="button" class="agent-panel-button" @click="loadRuns(item.id)">{{ t('agent.schedules.runs') }}</button>
          <button type="button" class="agent-panel-button is-danger" @click="removeSchedule(item)">{{ t('common.actions.delete') }}</button>
        </footer>
      </article>
    </div>

    <section v-if="runs.length" class="agent-schedule-runs">
      <h3>{{ t('agent.schedules.recentRuns') }}</h3>
      <article v-for="run in runs" :key="run.id" class="agent-schedule-run">
        <header>
          <strong>{{ run.schedule_name }}</strong>
          <span>{{ statusLabel(run.status) }} · {{ formatTime(run.started_at) }}</span>
        </header>
        <p>{{ run.error || run.result || t('agent.schedules.noResult') }}</p>
      </article>
    </section>

    <el-dialog
      v-model="editorVisible"
      :title="editingId ? t('agent.schedules.editTitle') : t('agent.schedules.createTitle')"
      width="640px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('agent.schedules.formName')">
          <el-input v-model="form.name" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('agent.schedules.formDescription')">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="8"
            maxlength="8000"
            show-word-limit
            :placeholder="t('agent.schedules.descriptionHint')"
          />
        </el-form-item>
        <el-form-item :label="t('agent.schedules.formKind')">
          <el-radio-group v-model="form.schedule_kind">
            <el-radio-button value="interval">{{ t('agent.schedules.kindInterval') }}</el-radio-button>
            <el-radio-button value="daily">{{ t('agent.schedules.kindDaily') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.schedule_kind === 'interval'" :label="t('agent.schedules.formInterval')">
          <el-input-number v-model="form.interval_minutes" :min="1" :max="10080" />
          <span class="agent-inline-hint">{{ t('agent.schedules.minutesUnit') }}</span>
        </el-form-item>
        <el-form-item v-else :label="t('agent.schedules.formDailyTime')">
          <el-time-select
            v-model="form.daily_time"
            start="00:00"
            step="00:15"
            end="23:45"
            :placeholder="t('agent.schedules.dailyTimePlaceholder')"
          />
          <span class="agent-inline-hint">{{ t('agent.schedules.dailyTimeHint') }}</span>
        </el-form-item>
        <el-form-item :label="t('agent.schedules.formEnabled')">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveSchedule">{{ t('common.actions.save') }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, RefreshCw } from '@lucide/vue'
import {
  agentScheduleApi,
  type AgentSchedule,
  type AgentScheduleRun,
} from '@/scripts/modules/agent/agentWorkspaceApi'

const { t, locale } = useI18n()
const loading = ref(false)
const saving = ref(false)
const runningId = ref('')
const error = ref('')
const schedules = ref<AgentSchedule[]>([])
const runs = ref<AgentScheduleRun[]>([])
const editorVisible = ref(false)
const editingId = ref('')
const form = reactive({
  name: '',
  description: '',
  enabled: true,
  schedule_kind: 'interval' as 'interval' | 'daily',
  interval_minutes: 60,
  daily_time: '09:00',
})

function scheduleSummary(item: AgentSchedule) {
  if (item.schedule_kind === 'daily') {
    return t('agent.schedules.everyDayAt', { time: item.daily_time || '--:--' })
  }
  return t('agent.schedules.everyMinutes', { minutes: item.interval_minutes })
}

function buildPayload() {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    enabled: form.enabled,
    schedule_kind: form.schedule_kind,
    interval_minutes: form.interval_minutes,
    daily_time: form.schedule_kind === 'daily' ? form.daily_time : null,
  }
}

function formatTime(value: string | null) {
  if (!value) return t('agent.schedules.never')
  try {
    return new Intl.DateTimeFormat(locale.value === 'zh-CN' ? 'zh-CN' : 'en-US', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function statusLabel(status: string) {
  if (status === 'success') return t('agent.schedules.statusSuccess')
  if (status === 'failed') return t('agent.schedules.statusFailed')
  if (status === 'running') return t('agent.schedules.statusRunning')
  return status
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const response = await agentScheduleApi.list()
    schedules.value = response.items
  } catch (err: any) {
    error.value = err?.message || t('agent.schedules.loadFailed')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = ''
  form.name = ''
  form.description = ''
  form.enabled = true
  form.schedule_kind = 'interval'
  form.interval_minutes = 60
  form.daily_time = '09:00'
  editorVisible.value = true
}

function editSchedule(item: AgentSchedule) {
  editingId.value = item.id
  form.name = item.name
  form.description = item.description
  form.enabled = item.enabled
  form.schedule_kind = item.schedule_kind || 'interval'
  form.interval_minutes = item.interval_minutes
  form.daily_time = item.daily_time || '09:00'
  editorVisible.value = true
}

async function saveSchedule() {
  if (!form.name.trim() || !form.description.trim()) {
    ElMessage.warning(t('agent.schedules.required'))
    return
  }
  if (form.schedule_kind === 'daily' && !form.daily_time) {
    ElMessage.warning(t('agent.schedules.dailyTimeRequired'))
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) await agentScheduleApi.update(editingId.value, payload)
    else await agentScheduleApi.create(payload)
    editorVisible.value = false
    ElMessage.success(t('agent.schedules.saved'))
    await refresh()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.schedules.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(item: AgentSchedule, enabled: boolean) {
  try {
    await agentScheduleApi.update(item.id, {
      name: item.name,
      description: item.description,
      schedule_kind: item.schedule_kind || 'interval',
      interval_minutes: item.interval_minutes,
      daily_time: item.daily_time,
      enabled,
    })
    await refresh()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.schedules.saveFailed'))
  }
}

async function runNow(item: AgentSchedule) {
  runningId.value = item.id
  try {
    const run = await agentScheduleApi.runNow(item.id)
    ElMessage.success(run.status === 'success' ? t('agent.schedules.runSuccess') : t('agent.schedules.runFailed'))
    await refresh()
    await loadRuns(item.id)
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.schedules.runFailed'))
  } finally {
    runningId.value = ''
  }
}

async function loadRuns(scheduleId: string) {
  try {
    const response = await agentScheduleApi.listRuns(scheduleId)
    runs.value = response.items
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.schedules.runsFailed'))
  }
}

async function removeSchedule(item: AgentSchedule) {
  try {
    await ElMessageBox.confirm(t('agent.schedules.deleteConfirm', { name: item.name }), t('common.actions.delete'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await agentScheduleApi.remove(item.id)
    ElMessage.success(t('agent.schedules.deleted'))
    await refresh()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.schedules.deleteFailed'))
  }
}

onMounted(() => {
  void refresh()
})
</script>

<style scoped>
.agent-panel {
  --agent-green: #176b5f;
  --agent-line: #dce4df;
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 24px 28px 32px;
  overflow: auto;
  background: #f7faf8;
}

.agent-panel-header,
.agent-panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-panel-header {
  justify-content: space-between;
}

.agent-panel-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}

.agent-panel-header p,
.agent-panel-empty,
.agent-inline-hint {
  margin: 0;
  color: #6b7874;
  font-size: 13px;
}

.agent-panel-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--agent-line);
  border-radius: 8px;
  color: #40514c;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.agent-panel-button.is-primary {
  color: #fff;
  border-color: var(--agent-green);
  background: var(--agent-green);
}

.agent-panel-button.is-danger {
  color: #a43f3f;
  border-color: #efc8c8;
}

.agent-panel-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.agent-panel-error {
  margin: 0;
  color: #a43f3f;
}

.agent-schedule-list,
.agent-schedule-runs {
  display: grid;
  gap: 12px;
}

.agent-schedule-card,
.agent-schedule-run {
  padding: 16px;
  border: 1px solid var(--agent-line);
  border-radius: 12px;
  background: #fff;
}

.agent-schedule-card header,
.agent-schedule-run header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.agent-schedule-card strong,
.agent-schedule-run strong {
  display: block;
  margin-bottom: 4px;
}

.agent-schedule-card header span,
.agent-schedule-run header span,
.agent-schedule-meta {
  color: #74827d;
  font-size: 12px;
}

.agent-schedule-desc,
.agent-schedule-preview,
.agent-schedule-run p {
  margin: 0;
  color: #42514c;
  line-height: 1.55;
  white-space: pre-wrap;
}

.agent-schedule-meta,
.agent-panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.agent-schedule-runs h3 {
  margin: 8px 0 0;
  font-size: 15px;
}

.agent-inline-hint {
  margin-left: 10px;
}
</style>
