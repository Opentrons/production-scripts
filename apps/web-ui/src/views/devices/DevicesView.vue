<template>
  <div class="devices-view">
    <div class="page-header">
      <span class="page-title">{{ t('devices.title') }}</span>
      <div class="header-tools">
        <el-input-number
          v-model="scanPort"
          class="scan-port-input"
          :min="1"
          :max="65535"
          :controls="false"
          size="small"
          :aria-label="t('devices.scanPort')"
        />
        <el-button
          type="primary"
          size="small"
          :icon="Search"
          @click="handleScan"
          :loading="scanning"
        >{{ t('devices.refresh') }}</el-button>
      </div>
    </div>

    <section class="device-toolbar">
      <el-input
        v-model="deviceSearchQuery"
        class="device-search-input"
        clearable
        :prefix-icon="Search"
        :placeholder="t('devices.searchPlaceholder')"
      />
      <el-button type="primary" plain :icon="Plus" @click="gatewayDialogVisible = true">
        {{ t('devices.addGateway') }}
      </el-button>
    </section>

    <div v-if="scanResult || !gatewaysLoading" class="stats-info">
      <div v-if="scanResult" class="scan-stats">
        <span class="stat-item online">
          <span class="stat-label">{{ t('devices.stats.online') }}</span>
          <span class="stat-value">{{ scannedDeviceCount }}</span>
        </span>
        <span class="stat-item abnormal">
          <span class="stat-label">{{ t('devices.stats.abnormal') }}</span>
          <span class="stat-value">{{ abnormalDeviceCount }}</span>
        </span>
        <span v-if="scanResult.cached_at" class="stat-item">
          <span class="stat-label">{{ t('devices.stats.cacheUpdated') }}</span>
          <span class="stat-value cache-time">{{ formatCacheTime(scanResult.cached_at) }}</span>
        </span>
        <span v-if="scanResult.refreshing" class="stat-item">
          <span class="stat-label">{{ t('devices.stats.scanning') }}</span>
        </span>
      </div>
      <div class="gateway-list">
        <el-tag
          v-for="gateway in scanGateways"
          :key="gateway.gateway"
          class="gateway-tag"
          closable
          :disable-transitions="true"
          @close="handleDeleteGateway(gateway.gateway)"
        >
          {{ gateway.gateway }} · {{ gateway.scan_range }}
        </el-tag>
        <span v-if="!gatewaysLoading && scanGateways.length === 0" class="gateway-empty">
          {{ t('devices.gateway.notConfigured') }}
        </span>
      </div>
    </div>

    <el-alert
      v-if="scanError"
      class="scan-error-alert"
      type="error"
      :closable="false"
      show-icon
    >
      <template #title>
        <div class="scan-error-content">
          <span>{{ t('devices.scan.failed', { error: scanError }) }}</span>
          <el-button size="small" type="danger" plain :loading="scanning" @click="handleScan">
            {{ t('devices.scan.retry') }}
          </el-button>
        </div>
      </template>
    </el-alert>

    <div
      v-if="initialLoading || (scanning && !scanResult)"
      class="devices-loading-state"
    >
      <el-icon class="is-loading devices-loading-icon"><Loading /></el-icon>
      <span>{{ t('devices.scan.loading') }}</span>
    </div>

    <el-empty
      v-else-if="!scanResult && !scanning && !scanError"
      :description="t('devices.scan.noCache')"
    />

    <div v-else-if="filteredOnlineRobots.length" class="device-list">
      <template v-for="robot in filteredOnlineRobots" :key="robot.ip">
        <div class="device-row" @click="handleOpenControl(robot)">
          <div class="device-thumb">
            <img src="@/assets/FLEX-MDypp_Sf.png" alt="Robot" />
          </div>
          <div class="device-content">
            <div class="device-title-row">
              <span class="device-name">{{ displayDeviceName(robot) }}</span>
              <span class="device-status-text" :class="robot.service_status">
                {{ formatServiceStatus(robot.service_status) }}
              </span>
            </div>
            <div class="device-ip">{{ robot.ip }}</div>
            <div v-if="isServiceAbnormal(robot)" class="service-alert">
              <el-icon class="service-alert-icon"><WarningFilled /></el-icon>
              <span class="service-alert-text">{{ getServiceAlertText(robot) }}</span>
            </div>
          </div>
          <el-tooltip :content="t('devices.info')" placement="top">
            <button
              class="device-icon-action"
              type="button"
              :aria-label="t('devices.info')"
              @click.stop="handleShowInfo(robot)"
            >
              <el-icon><InfoFilled /></el-icon>
            </button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="(command: DeviceMenuCommand) => handleDeviceMenu(command, robot)">
            <button
              class="device-icon-action"
              type="button"
              :aria-label="t('devices.actionMenu')"
              @click.stop
            >
              <el-icon><MoreFilled /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="info">{{ t('devices.info') }}</el-dropdown-item>
                <el-dropdown-item command="control">{{ t('devices.enterControl') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </div>

    <el-empty v-else-if="scanResult" :description="emptyDeviceDescription" />

    <el-dialog
      v-model="gatewayDialogVisible"
      :title="t('devices.gateway.dialogTitle')"
      width="420px"
      destroy-on-close
      @closed="resetGatewayForm"
    >
      <el-form
        ref="gatewayFormRef"
        :model="gatewayForm"
        :rules="gatewayRules"
        label-position="top"
        @submit.prevent
      >
        <el-form-item :label="t('devices.gateway.ip')" prop="gateway">
          <el-input
            v-model="gatewayForm.gateway"
            clearable
            autofocus
            :placeholder="t('devices.gateway.placeholder')"
            @keyup.enter="handleAddGateway"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="gatewaySaving" @click="gatewayDialogVisible = false">
          {{ t('common.actions.cancel') }}
        </el-button>
        <el-button type="primary" :loading="gatewaySaving" @click="handleAddGateway">
          {{ t('common.actions.save') }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="infoDialogVisible"
      :title="t('devices.infoTitle', { ip: infoRobot?.ip || '' })"
      width="640px"
    >
      <div v-loading="infoLoading">
        <RobotInfoTable v-if="infoRobot" :robot="infoRobot" />
      </div>
      <template #footer>
        <el-button @click="infoDialogVisible = false">{{ t('common.actions.close') }}</el-button>
        <el-button
          v-if="infoRobot"
          type="primary"
          @click="handleOpenControl(infoRobot)"
        >
          {{ t('devices.enterControl') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { robotApi, type RobotInfo, type RobotScanGateway } from '@/scripts/api'
import { InfoFilled, Loading, MoreFilled, Plus, Search, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import RobotInfoTable from '@/views/devices/components/RobotInfoTable.vue'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import { useAppLocale } from '@/i18n'

type DeviceMenuCommand = 'info' | 'control'

const router = useRouter()
const robotScanStore = useRobotScanStore()
const { scanResult, scanning } = storeToRefs(robotScanStore)
const { locale, t } = useAppLocale()
const infoDialogVisible = ref(false)
const infoLoading = ref(false)
const infoRobot = ref<RobotInfo | null>(null)
const scanPort = ref(31950)
const scanGateways = ref<RobotScanGateway[]>([])
const deviceSearchQuery = ref('')
const gatewayDialogVisible = ref(false)
const gatewayFormRef = ref<FormInstance>()
const gatewayForm = ref({ gateway: '' })
const gatewayRules = computed<FormRules>(() => ({
  gateway: [
    { required: true, whitespace: true, message: t('devices.gateway.required'), trigger: ['blur', 'change'] }
  ]
}))
const gatewaysLoading = ref(true)
const gatewaySaving = ref(false)
const initialLoading = ref(true)
const scanError = ref('')

function displayDeviceName(robot: RobotInfo): string {
  const name = robot.name?.trim()
  return name || t('devices.unnamed')
}

function formatCacheTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(locale.value)
}

function isServiceAbnormal(robot: RobotInfo): boolean {
  return robot.service_status !== 'normal'
}

function formatServiceStatus(status: RobotInfo['service_status']) {
  const statusMap: Record<RobotInfo['service_status'], string> = {
    normal: t('common.status.healthy'),
    error: t('common.status.abnormal'),
    unknown: t('common.status.unknown')
  }
  return statusMap[status] || t('common.status.unknown')
}

function extractHealthHttpStatus(error: string | undefined): number | null {
  if (!error) return null
  const match = error.match(/HTTP\s+(\d{3})/i)
  return match ? Number(match[1]) : null
}

function getServiceAlertText(robot: RobotInfo): string {
  const statusCode = extractHealthHttpStatus(robot.error)
  if (statusCode !== null) {
    return t('devices.serviceError', { status: statusCode })
  }
  return t('devices.serviceError', { status: t('common.status.unknown') })
}

function handleDeviceMenu(command: DeviceMenuCommand, robot: RobotInfo) {
  if (command === 'info') {
    handleShowInfo(robot)
    return
  }
  handleOpenControl(robot)
}

const handleScan = async () => {
  scanError.value = ''
  try {
    const result = await robotScanStore.refreshScan({
      silent: false,
      params: {
        port: scanPort.value
      }
    })
    if (result) {
      ElMessage.success(t('devices.scan.completed', { count: result.online_robots.length }))
    }
  } catch (error: any) {
    scanError.value = normalizeApiError(error)
  }
}

const fetchScanGateways = async () => {
  gatewaysLoading.value = true
  try {
    const response = await robotApi.listScanGateways()
    scanGateways.value = response.data.gateways
  } catch (error: any) {
    // MongoDB/gateway lookup failure should not block scanning; backend falls
    // back to the server's current network segment.
    scanGateways.value = []
    ElMessage.warning(t('devices.gateway.readFailed', { error: normalizeApiError(error) }))
  } finally {
    gatewaysLoading.value = false
  }
}

function normalizeApiError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || t('errors.unknown')
}

const handleAddGateway = async () => {
  if (!gatewayFormRef.value || gatewaySaving.value) return

  const valid = await gatewayFormRef.value.validate().catch(() => false)
  if (!valid) return

  const gateway = gatewayForm.value.gateway.trim()

  gatewaySaving.value = true
  try {
    await robotApi.addScanGateway(gateway)
    await fetchScanGateways()
    gatewayDialogVisible.value = false
    ElMessage.success(t('devices.gateway.saved'))
  } catch (error: any) {
    ElMessage.error(t('devices.gateway.saveFailed', { error: normalizeApiError(error) }))
  } finally {
    gatewaySaving.value = false
  }
}

const resetGatewayForm = () => {
  gatewayForm.value.gateway = ''
  gatewayFormRef.value?.clearValidate()
}

const handleDeleteGateway = async (gateway: string) => {
  try {
    await ElMessageBox.confirm(t('devices.gateway.deleteConfirm', { gateway }), t('devices.gateway.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.actions.delete'),
      cancelButtonText: t('common.actions.cancel')
    })
  } catch {
    return
  }

  gatewaySaving.value = true
  try {
    await robotApi.deleteScanGateway(gateway)
    await fetchScanGateways()
    ElMessage.success(t('devices.gateway.deleted'))
  } catch (error: any) {
    ElMessage.error(t('devices.gateway.deleteFailed', { error: normalizeApiError(error) }))
  } finally {
    gatewaySaving.value = false
  }
}

const handleShowInfo = async (robot: RobotInfo) => {
  infoDialogVisible.value = true
  infoLoading.value = true
  infoRobot.value = { ...robot }
  try {
    const response = await robotApi.getRobotDetail(robot.ip, robot.port)
    infoRobot.value = response.data
  } catch (error: any) {
    infoRobot.value = {
      ...robot,
      health_fetch_failed: true,
      service_status: 'error',
      error: error.message || t('devices.infoLoadFailed')
    }
    ElMessage.error(t('devices.infoLoadFailed'))
  } finally {
    infoLoading.value = false
  }
}

const handleOpenControl = (robot: RobotInfo) => {
  infoDialogVisible.value = false
  router.push({ name: 'DeviceControl', query: { ip: robot.ip } })
}

const scannedDeviceCount = computed(() => scanResult.value?.online_robots.length ?? 0)
const filteredOnlineRobots = computed(() => {
  const robots = scanResult.value?.online_robots ?? []
  const query = deviceSearchQuery.value.trim().toLocaleLowerCase()
  if (!query) return robots

  return robots.filter((robot) => {
    const name = robot.name?.trim().toLocaleLowerCase() ?? ''
    return robot.ip.toLocaleLowerCase().includes(query) || name.includes(query)
  })
})
const emptyDeviceDescription = computed(() => (
  deviceSearchQuery.value.trim() ? t('devices.scan.noMatches') : t('devices.scan.noOnline')
))
const abnormalDeviceCount = computed(() => {
  if (!scanResult.value) return 0
  return scanResult.value.abnormal_count
    ?? scanResult.value.online_robots.filter(robot => robot.service_status !== 'normal').length
})

onMounted(async () => {
  scanPort.value = robotScanStore.lastScanParams.port ?? 31950
  try {
    await Promise.all([
      fetchScanGateways(),
      robotScanStore.loadCachedScan({ port: scanPort.value })
    ])
  } catch (error: any) {
    scanError.value = normalizeApiError(error)
  } finally {
    initialLoading.value = false
  }
})
</script>

<style scoped>
.devices-view {
  --console-text: #1f2a37;
  --console-muted: #6b7280;
  --console-border: #e6ebf2;
  --console-bg: #fff;
  --console-active: #f7f9fc;
  height: 100%;
  padding: 16px 20px;
  background: var(--console-bg);
  color: var(--console-text);
  text-align: left;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  font-size: 16px;
  font-weight: 650;
  color: var(--console-text);
}

.devices-loading-state {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--console-muted);
  font-size: 14px;
}

.devices-loading-icon {
  color: #409eff;
  font-size: 22px;
}

.scan-error-alert {
  margin: 14px 0;
}

.scan-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.scan-port-input {
  width: 86px;
}

.device-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--console-border);
}

.device-search-input {
  width: min(360px, 100%);
}

.gateway-list {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-height: 28px;
}

.gateway-tag {
  max-width: 100%;
}

.gateway-empty {
  color: var(--console-muted);
  font-size: 12px;
  line-height: 24px;
}

.stats-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--console-border);
}

.scan-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 18px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat-label {
  color: var(--console-muted);
  font-size: 12px;
}

.stat-value {
  color: var(--console-text);
  font-weight: 650;
  font-size: 14px;
}

.stat-item.online .stat-value {
  color: #16803c;
}

.stat-item.abnormal .stat-value {
  color: #c24141;
}

.stat-value.cache-time {
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 500;
}

.device-list {
  display: grid;
  width: 100%;
  max-width: 960px;
  margin-top: 10px;
  border-top: 1px solid var(--console-border);
  background: var(--console-bg);
}

.device-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 16px;
  min-height: 88px;
  padding: 12px 4px;
  border-bottom: 1px solid var(--console-border);
  background: var(--console-bg);
  cursor: pointer;
  transition: background-color 0.18s ease;
}

.device-row:hover {
  background: var(--console-active);
}

.device-thumb {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.device-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.device-content {
  min-width: 0;
}

.device-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.device-name {
  overflow: hidden;
  color: var(--console-text);
  font-size: 15px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-status-text {
  font-size: 12px;
  font-weight: 650;
  color: #64748b;
}

.device-status-text.normal {
  color: #16803c;
}

.device-status-text.error {
  color: #c24141;
}

.device-ip {
  color: var(--console-muted);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.service-alert {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  margin-top: 6px;
  color: #c24141;
  font-size: 12px;
  line-height: 1.4;
}

.service-alert-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.service-alert-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-icon-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.2s, color 0.2s;
}

.device-icon-action:hover {
  background: var(--console-active);
  color: var(--console-text);
}

@media (max-width: 760px) {
  .page-header,
  .header-tools,
  .device-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .scan-port-input,
  .device-search-input {
    width: 100%;
  }

  .device-row {
    grid-template-columns: 56px minmax(0, 1fr) auto auto;
    gap: 10px;
  }

  .device-thumb {
    width: 56px;
    height: 56px;
  }
}
</style>
