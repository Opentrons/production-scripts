<template>
  <div v-loading="loading" class="device-info-content" :class="{ 'is-drawer': inDrawer }">
    <div v-if="showHeader" class="panel-header">
      <span class="panel-title">设备信息</span>
      <el-button link type="primary" size="small" :disabled="!ip" @click="loadSummary">
        刷新
      </el-button>
    </div>

    <div v-if="!ip" class="panel-empty">
      <el-empty description="请选择设备" :image-size="64" />
    </div>

    <template v-else>
      <div class="info-block">
        <div class="info-subtitle">连接状态</div>
        <div class="info-row">
          <span>HTTP</span>
          <el-tag :type="summary?.http_connected ? 'success' : 'danger'" size="small">
            {{ summary?.http_connected ? '已连接' : '未连接' }}
          </el-tag>
        </div>
        <div class="info-row">
          <span>SSH</span>
          <el-tag :type="summary?.ssh_connected ? 'success' : 'danger'" size="small">
            {{ summary?.ssh_connected ? '已连接' : '未连接' }}
          </el-tag>
        </div>
      </div>

      <el-divider />

      <div class="info-block">
        <div class="info-subtitle">基本信息</div>
        <div class="info-row"><span>IP</span><span>{{ ip }}</span></div>
        <div class="info-row"><span>名称</span><span>{{ healthName }}</span></div>
        <div class="info-row"><span>型号</span><span>{{ healthModel }}</span></div>
        <div class="info-row"><span>序列号</span><span>{{ healthSerial }}</span></div>
        <div class="info-row"><span>API 版本</span><span>{{ healthApiVersion }}</span></div>
        <div class="info-row"><span>FW 版本</span><span>{{ healthFwVersion }}</span></div>
        <div class="info-row"><span>系统版本</span><span>{{ healthSystemVersion }}</span></div>
      </div>

      <el-alert
        v-for="(message, index) in summary?.errors ?? []"
        :key="`${message}-${index}`"
        type="warning"
        :closable="false"
        :title="message"
        class="info-alert"
      />

      <el-divider />

      <div class="info-block">
        <div class="info-subtitle-row">
          <span class="info-subtitle">Instruments</span>
          <span class="resource-count">{{ instrumentItems.length }}</span>
        </div>
        <div v-if="instrumentItems.length" class="resource-list">
          <article
            v-for="item in instrumentItems"
            :key="item.id"
            class="resource-item"
          >
            <div class="resource-main">
              <div class="resource-title-line">
                <span class="resource-title">{{ item.title }}</span>
                <el-tag
                  v-if="item.status"
                  :type="resourceStatusType(item.status)"
                  size="small"
                  effect="light"
                >
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="resource-meta">
                <span class="location-chip">
                  <span>{{ item.locationLabel }}</span>
                  {{ item.location }}
                </span>
                <span v-if="item.model">{{ item.model }}</span>
                <span v-if="item.serial">{{ item.serial }}</span>
              </div>
            </div>
            <el-popover
              trigger="hover"
              placement="left"
              :width="380"
              popper-class="raw-json-popover"
            >
              <template #reference>
                <button class="raw-tag" type="button" @click.stop="copyJson(item.rawJson)">Raw</button>
              </template>
              <div class="raw-popover-content">
                <div class="raw-popover-header">
                  <span>Raw JSON</span>
                  <button class="raw-copy-button" type="button" @click="copyJson(item.rawJson)">
                    复制 JSON
                  </button>
                </div>
                <pre>{{ item.rawJson }}</pre>
              </div>
            </el-popover>
          </article>
        </div>
        <div v-else class="resource-empty">暂无加载 Instrument</div>
      </div>

      <el-divider />

      <div class="info-block">
        <div class="info-subtitle-row">
          <span class="info-subtitle">Modules</span>
          <span class="resource-count">{{ moduleItems.length }}</span>
        </div>
        <div v-if="moduleItems.length" class="resource-list">
          <article
            v-for="item in moduleItems"
            :key="item.id"
            class="resource-item"
          >
            <div class="resource-main">
              <div class="resource-title-line">
                <span class="resource-title">{{ item.title }}</span>
                <el-tag
                  v-if="item.status"
                  :type="resourceStatusType(item.status)"
                  size="small"
                  effect="light"
                >
                  {{ item.status }}
                </el-tag>
              </div>
              <div class="resource-meta">
                <span class="location-chip">
                  <span>{{ item.locationLabel }}</span>
                  {{ item.location }}
                </span>
                <span v-if="item.model">{{ item.model }}</span>
                <span v-if="item.serial">{{ item.serial }}</span>
              </div>
            </div>
            <el-popover
              trigger="hover"
              placement="left"
              :width="380"
              popper-class="raw-json-popover"
            >
              <template #reference>
                <button class="raw-tag" type="button" @click.stop="copyJson(item.rawJson)">Raw</button>
              </template>
              <div class="raw-popover-content">
                <div class="raw-popover-header">
                  <span>Raw JSON</span>
                  <button class="raw-copy-button" type="button" @click="copyJson(item.rawJson)">
                    复制 JSON
                  </button>
                </div>
                <pre>{{ item.rawJson }}</pre>
              </div>
            </el-popover>
          </article>
        </div>
        <div v-else class="resource-empty">暂无加载 Module</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { robotApi, type RobotControlSummary } from '@/api'

const props = withDefaults(
  defineProps<{
    ip: string | null
    inDrawer?: boolean
    showHeader?: boolean
  }>(),
  {
    inDrawer: false,
    showHeader: true
  }
)

const loading = ref(false)
const summary = ref<RobotControlSummary | null>(null)

const healthName = computed(() => stringField(summary.value?.health?.name))
const healthModel = computed(() => stringField(summary.value?.health?.robot_model))
const healthSerial = computed(() => stringField(summary.value?.health?.robot_serial))
const healthApiVersion = computed(() => stringField(summary.value?.health?.api_version))
const healthFwVersion = computed(() => stringField(summary.value?.health?.fw_version))
const healthSystemVersion = computed(() => stringField(summary.value?.health?.system_version))
const instrumentItems = computed(() => normalizeResources(summary.value?.instruments, 'instrument'))
const moduleItems = computed(() => normalizeResources(summary.value?.modules, 'module'))

type ResourceKind = 'instrument' | 'module'

interface ResourceItem {
  id: string
  title: string
  model: string
  serial: string
  status: string
  location: string
  locationLabel: string
  rawJson: string
}

type UnknownRecord = Record<string, unknown>

function stringField(value: unknown): string {
  if (value === null || value === undefined || String(value).trim() === '') return 'N/A'
  return String(value)
}

function formatJson(value: unknown): string {
  if (value === null || value === undefined) return 'N/A'
  return JSON.stringify(value, null, 2)
}

function asRecord(value: unknown): UnknownRecord | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as UnknownRecord
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (value === null || value === undefined) continue
    const text = String(value).trim()
    if (text && text !== 'null' && text !== 'undefined' && text !== 'None') return text
  }
  return ''
}

function nestedValue(record: UnknownRecord, path: string): unknown {
  return path.split('.').reduce<unknown>((current, key) => {
    const currentRecord = asRecord(current)
    return currentRecord ? currentRecord[key] : undefined
  }, record)
}

function firstNestedString(record: UnknownRecord, paths: string[]): string {
  return firstString(...paths.map((path) => nestedValue(record, path)))
}

function isResourceLike(record: UnknownRecord, kind: ResourceKind): boolean {
  const identityKeys = [
    'id',
    'name',
    'displayName',
    'instrumentName',
    'instrumentModel',
    'pipetteName',
    'pipetteModel',
    'moduleModel',
    'moduleType',
    'serialNumber'
  ]
  const locationKeys = kind === 'instrument'
    ? ['mount', 'pipetteMount']
    : ['location', 'slot', 'slotName', 'deckSlot', 'mount']
  return [...identityKeys, ...locationKeys].some((key) => key in record)
}

function collectResourceRecords(
  value: unknown,
  kind: ResourceKind,
  fallbackKey = ''
): Array<{ key: string; raw: UnknownRecord }> {
  if (Array.isArray(value)) {
    return value.flatMap((entry, index) => collectResourceRecords(entry, kind, String(index)))
  }

  const record = asRecord(value)
  if (!record) return []

  if (isResourceLike(record, kind)) {
    return [{ key: fallbackKey, raw: record }]
  }

  for (const wrapperKey of ['data', 'instruments', 'pipettes', 'modules']) {
    if (wrapperKey in record) {
      return collectResourceRecords(record[wrapperKey], kind, fallbackKey)
    }
  }

  return Object.entries(record).flatMap(([key, entry]) => collectResourceRecords(entry, kind, key))
}

function normalizeResources(value: unknown, kind: ResourceKind): ResourceItem[] {
  return collectResourceRecords(value, kind)
    .map(({ key, raw }, index) => {
      const location = resolveLocation(raw, kind, key)
      const model = resolveModel(raw, kind)
      const title = resolveTitle(raw, kind, model, key)
      return {
        id: firstString(raw.id, raw.serialNumber, `${kind}-${key || index}`),
        title,
        model: model !== title ? model : '',
        serial: resolveSerial(raw),
        status: resolveStatus(raw),
        location: location.value,
        locationLabel: location.label,
        rawJson: formatJson(raw)
      }
    })
    .filter((item) => item.title || item.model || item.serial || item.location !== 'N/A')
}

function resolveTitle(record: UnknownRecord, kind: ResourceKind, model: string, fallbackKey: string): string {
  const title = kind === 'instrument'
    ? firstNestedString(record, ['displayName', 'instrumentName', 'pipetteName', 'name'])
    : firstNestedString(record, ['displayName', 'moduleType', 'moduleModel', 'name'])
  return title || model || fallbackKey || 'Unknown'
}

function resolveModel(record: UnknownRecord, kind: ResourceKind): string {
  if (kind === 'instrument') {
    return firstNestedString(record, ['instrumentModel', 'pipetteModel', 'model', 'instrumentName', 'pipetteName'])
  }
  return firstNestedString(record, ['moduleModel', 'moduleType', 'model'])
}

function resolveSerial(record: UnknownRecord): string {
  const serial = firstNestedString(record, ['serialNumber', 'serial', 'id'])
  return serial ? `SN ${serial}` : ''
}

function resolveStatus(record: UnknownRecord): string {
  const status = firstNestedString(record, ['status', 'state', 'ok', 'connected', 'hasInstrument', 'attached'])
  if (!status) return ''
  if (status === 'true') return 'connected'
  if (status === 'false') return 'disconnected'
  return status
}

function resolveLocation(record: UnknownRecord, kind: ResourceKind, fallbackKey: string): { label: string; value: string } {
  if (kind === 'instrument') {
    const mount = firstNestedString(record, ['mount', 'pipetteMount']) || fallbackKey
    return { label: 'mount', value: mount || 'N/A' }
  }

  const mount = firstNestedString(record, ['mount'])
  if (mount) return { label: 'mount', value: mount }

  const slot = firstNestedString(record, [
    'location.slotName',
    'location.slot',
    'location.logicalSlotName',
    'slotName',
    'slot',
    'deckSlot'
  ]) || fallbackKey
  return { label: 'slot', value: slot || 'N/A' }
}

function resourceStatusType(status: string) {
  const normalized = status.toLowerCase()
  if (['connected', 'idle', 'ready', 'succeeded', 'success', 'ok', 'true'].includes(normalized)) return 'success'
  if (['error', 'failed', 'failure', 'disconnected', 'offline', 'false'].includes(normalized)) return 'danger'
  if (['running', 'busy', 'moving', 'updating'].includes(normalized)) return 'warning'
  return 'info'
}

async function copyJson(text: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    ElMessage.success('JSON 已复制')
  } catch {
    ElMessage.error('复制 JSON 失败')
  }
}

async function loadSummary() {
  if (!props.ip) {
    summary.value = null
    return
  }
  loading.value = true
  try {
    const response = await robotApi.getControlSummary(props.ip)
    summary.value = response.data
  } catch (error: any) {
    ElMessage.error('加载设备信息失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.ip,
  () => {
    void loadSummary()
  },
  { immediate: true }
)

defineExpose({ refresh: loadSummary })
</script>

<style scoped>
.device-info-content {
  text-align: left;
}

.device-info-content.is-drawer {
  padding: 0 4px 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-title,
.info-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.info-subtitle {
  margin-bottom: 12px;
}

.info-subtitle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.info-subtitle-row .info-subtitle {
  margin-bottom: 0;
}

.resource-count {
  min-width: 22px;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: #606266;
  font-size: 12px;
  line-height: 20px;
  text-align: center;
}

.info-block {
  padding: 4px 0 8px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #606266;
}

.info-row span:last-child {
  text-align: right;
  word-break: break-all;
}

.info-alert {
  margin: 12px 0;
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.resource-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.resource-item:last-child {
  border-bottom: 0;
}

.resource-main {
  min-width: 0;
  flex: 1;
}

.resource-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.resource-title {
  min-width: 0;
  overflow: hidden;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 20px;
}

.location-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 20px;
  padding: 0 7px;
  border-radius: 4px;
  background: #f5f7fa;
  color: #606266;
  font-weight: 600;
}

.location-chip span {
  color: #909399;
  font-weight: 500;
}

.resource-empty {
  padding: 12px 0;
  color: #909399;
  font-size: 13px;
}

.raw-tag {
  flex: 0 0 auto;
  height: 24px;
  padding: 0 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  cursor: pointer;
  font-size: 12px;
  line-height: 22px;
}

.raw-tag:hover {
  border-color: #409eff;
  color: #409eff;
}

.json-block {
  margin: 0;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  overflow: auto;
  max-height: 280px;
}

.is-drawer .json-block {
  max-height: 360px;
}

.device-info-content :deep(.el-divider) {
  margin: 16px 0;
}

:global(.raw-json-popover) {
  padding: 0;
}

:global(.raw-popover-content) {
  max-height: 360px;
  overflow: hidden;
}

:global(.raw-popover-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #ebeef5;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
}

:global(.raw-copy-button) {
  height: 24px;
  padding: 0 8px;
  border: 0;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  cursor: pointer;
  font-size: 12px;
}

:global(.raw-copy-button:hover) {
  background: #d9ecff;
}

:global(.raw-popover-content pre) {
  max-height: 300px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  background: #f8fafc;
  color: #303133;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
