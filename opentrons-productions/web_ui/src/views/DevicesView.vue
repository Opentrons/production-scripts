<template>
  <div class="devices-view">
    <div class="page-header">
      <span class="page-title">设备管理</span>
      <div class="header-tools">
        <el-input-number
          v-model="scanPort"
          class="scan-port-input"
          :min="1"
          :max="65535"
          :controls="false"
          size="small"
        />
        <el-button type="primary" size="small" @click="handleScan" :loading="scanning">
          <el-icon><Search /></el-icon>
          扫描设备
        </el-button>
      </div>
    </div>

    <section class="gateway-config">
      <div class="gateway-editor">
        <el-input
          v-model="newGateway"
          class="gateway-input"
          clearable
          size="small"
          placeholder="扫描网关，如 192.168.6.1"
          @keyup.enter="handleAddGateway"
        />
        <el-button
          size="small"
          :loading="gatewaySaving"
          :disabled="!newGateway.trim()"
          @click="handleAddGateway"
        >
          添加网关
        </el-button>
      </div>
      <div class="gateway-list" v-loading="gatewaysLoading">
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
          未配置时使用服务器当前网段
        </span>
      </div>
    </section>

    <div class="stats-info" v-if="scanResult">
      <span class="stat-item">
        <span class="stat-label">扫描网段:</span>
        <span class="stat-value">{{ scanResult.scan_network }}</span>
      </span>
      <span v-if="scanResult.scan_gateways?.length" class="stat-item">
        <span class="stat-label">扫描网关:</span>
        <span class="stat-value">{{ scanResult.scan_gateways.join(', ') }}</span>
      </span>
      <span class="stat-item">
        <span class="stat-label">服务器:</span>
        <span class="stat-value">{{ scanResult.server_ip || scanResult.gateway }}</span>
      </span>
      <span class="stat-item online">
        <span class="stat-label">在线:</span>
        <span class="stat-value">{{ scannedDeviceCount }}</span>
      </span>
      <span class="stat-item offline">
        <span class="stat-label">离线:</span>
        <span class="stat-value">{{ offlineDeviceCount }}</span>
      </span>
      <span class="stat-item abnormal">
        <span class="stat-label">异常:</span>
        <span class="stat-value">{{ abnormalDeviceCount }}</span>
      </span>
    </div>

    <el-empty
      v-if="!scanResult && !scanning"
      description="请点击扫描按钮搜索设备"
    />

    <div v-else-if="scanResult?.online_robots.length" class="device-list">
      <template v-for="robot in scanResult.online_robots" :key="robot.ip">
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
          <el-tooltip content="设备信息" placement="top">
            <button
              class="device-icon-action"
              type="button"
              aria-label="设备信息"
              @click.stop="handleShowInfo(robot)"
            >
              <el-icon><InfoFilled /></el-icon>
            </button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="(command: DeviceMenuCommand) => handleDeviceMenu(command, robot)">
            <button
              class="device-icon-action"
              type="button"
              aria-label="设备操作菜单"
              @click.stop
            >
              <el-icon><MoreFilled /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="info">设备信息</el-dropdown-item>
                <el-dropdown-item command="control">进入设备操作</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </div>

    <el-empty
      v-else-if="scanResult && scanResult.online_robots.length === 0"
      description="未发现在线设备"
    />

    <el-dialog
      v-model="infoDialogVisible"
      :title="`设备信息 - ${infoRobot?.ip || ''}`"
      width="640px"
    >
      <div v-loading="infoLoading">
        <RobotInfoTable v-if="infoRobot" :robot="infoRobot" />
      </div>
      <template #footer>
        <el-button @click="infoDialogVisible = false">关闭</el-button>
        <el-button
          v-if="infoRobot"
          type="primary"
          @click="handleOpenControl(infoRobot)"
        >
          进入设备操作
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { robotApi, type RobotInfo, type RobotScanGateway } from '@/api'
import { InfoFilled, MoreFilled, Search, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import RobotInfoTable from '@/components/RobotInfoTable.vue'
import { useRobotScanStore } from '@/stores/robotScan'

type DeviceMenuCommand = 'info' | 'control'

const router = useRouter()
const robotScanStore = useRobotScanStore()
const { scanResult, scanning } = storeToRefs(robotScanStore)
const infoDialogVisible = ref(false)
const infoLoading = ref(false)
const infoRobot = ref<RobotInfo | null>(null)
const scanPort = ref(31950)
const scanGateways = ref<RobotScanGateway[]>([])
const newGateway = ref('')
const gatewaysLoading = ref(false)
const gatewaySaving = ref(false)

function displayDeviceName(robot: RobotInfo): string {
  const name = robot.name?.trim()
  return name || '未命名设备'
}

function isServiceAbnormal(robot: RobotInfo): boolean {
  return robot.service_status !== 'normal'
}

function formatServiceStatus(status: RobotInfo['service_status']) {
  const statusMap: Record<RobotInfo['service_status'], string> = {
    normal: '正常',
    error: '异常',
    unknown: '未知'
  }
  return statusMap[status] || '未知'
}

function extractHealthHttpStatus(error: string | undefined): number | null {
  if (!error) return null
  const match = error.match(/HTTP\s+(\d{3})/i)
  return match ? Number(match[1]) : null
}

function getServiceAlertText(robot: RobotInfo): string {
  const statusCode = extractHealthHttpStatus(robot.error)
  if (statusCode !== null) {
    return `Flex server error, getting health Http status ${statusCode}`
  }
  return 'Flex server error, getting health Http status unknown'
}

function handleDeviceMenu(command: DeviceMenuCommand, robot: RobotInfo) {
  if (command === 'info') {
    handleShowInfo(robot)
    return
  }
  handleOpenControl(robot)
}

const handleScan = async () => {
  try {
    const result = await robotScanStore.refreshScan({
      silent: false,
      params: {
        port: scanPort.value
      }
    })
    if (result) {
      ElMessage.success(`扫描完成，发现 ${result.online_robots.length} 台在线设备`)
    }
  } catch (error: any) {
    ElMessage.error('扫描失败: ' + (error.message || '未知错误'))
  }
}

const fetchScanGateways = async () => {
  gatewaysLoading.value = true
  try {
    const response = await robotApi.listScanGateways()
    scanGateways.value = response.data.gateways
  } catch (error: any) {
    ElMessage.error('读取扫描网关失败: ' + normalizeApiError(error))
  } finally {
    gatewaysLoading.value = false
  }
}

function normalizeApiError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

const handleAddGateway = async () => {
  const gateway = newGateway.value.trim()
  if (!gateway) return

  gatewaySaving.value = true
  try {
    await robotApi.addScanGateway(gateway)
    newGateway.value = ''
    await fetchScanGateways()
    ElMessage.success('扫描网关已保存')
  } catch (error: any) {
    ElMessage.error('保存扫描网关失败: ' + normalizeApiError(error))
  } finally {
    gatewaySaving.value = false
  }
}

const handleDeleteGateway = async (gateway: string) => {
  try {
    await ElMessageBox.confirm(`删除扫描网关 ${gateway}？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  gatewaySaving.value = true
  try {
    await robotApi.deleteScanGateway(gateway)
    await fetchScanGateways()
    ElMessage.success('扫描网关已删除')
    void robotScanStore.refreshScan({ silent: true, params: { port: scanPort.value } })
  } catch (error: any) {
    ElMessage.error('删除扫描网关失败: ' + normalizeApiError(error))
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
      error: error.message || '获取设备信息失败'
    }
    ElMessage.error('获取设备信息失败')
  } finally {
    infoLoading.value = false
  }
}

const handleOpenControl = (robot: RobotInfo) => {
  infoDialogVisible.value = false
  router.push({ name: 'DeviceControl', query: { ip: robot.ip } })
}

const scannedDeviceCount = computed(() => scanResult.value?.online_robots.length ?? 0)
const offlineDeviceCount = computed(() => {
  if (!scanResult.value) return 0
  return scanResult.value.offline_count
    ?? scanResult.value.offline_robots.length
})
const abnormalDeviceCount = computed(() => {
  if (!scanResult.value) return 0
  return scanResult.value.abnormal_count
    ?? scanResult.value.online_robots.filter(robot => robot.service_status !== 'normal').length
})

onMounted(async () => {
  const hasCache = robotScanStore.loadFromCache()
  scanPort.value = robotScanStore.lastScanParams.port ?? 31950
  await fetchScanGateways()
  robotScanStore.startAutoRefresh()

  if (hasCache) {
    void robotScanStore.refreshScan({ silent: true })
    return
  }

  try {
    await robotScanStore.refreshScan({ silent: false })
  } catch (error: any) {
    ElMessage.error('扫描失败: ' + (error.message || '未知错误'))
  }
})

onUnmounted(() => {
  robotScanStore.stopAutoRefresh()
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

.header-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.scan-port-input {
  width: 86px;
}

.gateway-config {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-top: 14px;
  padding: 12px 0;
  border-top: 1px solid var(--console-border);
}

.gateway-editor {
  display: flex;
  flex: 0 0 340px;
  gap: 8px;
}

.gateway-input {
  min-width: 0;
}

.gateway-list {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
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
  flex-wrap: wrap;
  gap: 18px;
  margin: 0;
  padding: 12px 0;
  border-bottom: 1px solid var(--console-border);
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

.stat-item.offline .stat-value {
  color: #64748b;
}

.stat-item.abnormal .stat-value {
  color: #c24141;
}

.device-list {
  display: grid;
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
  .gateway-config,
  .gateway-editor {
    align-items: stretch;
    flex-direction: column;
  }

  .gateway-editor {
    flex-basis: auto;
  }

  .scan-port-input,
  .gateway-input {
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
