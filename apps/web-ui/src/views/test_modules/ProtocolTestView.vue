<template>
  <div class="protocol-monitor-page">
    <header class="page-head">
      <div class="page-title-group">
        <div class="title-icon" aria-hidden="true">
          <el-icon><Monitor /></el-icon>
        </div>
        <div>
          <div class="title-line">
            <h1>Protocol 监控平台</h1>
          </div>
          <span class="page-meta">{{ rooms.length }} 个房间 · {{ totalDeviceCount }} 台设备</span>
        </div>
      </div>
      <div class="page-actions">
        <el-tooltip content="刷新房间" placement="bottom">
          <el-button
            :icon="Refresh"
            circle
            aria-label="刷新房间"
            :loading="loadingRooms"
            @click="loadRooms"
          />
        </el-tooltip>
        <el-button :icon="Plus" type="primary" @click="openCreateRoom">新建房间</el-button>
      </div>
    </header>

    <el-alert
      v-if="loadError"
      class="load-alert"
      type="error"
      :closable="false"
      show-icon
      :title="loadError"
    />

    <div class="monitor-workspace">
      <aside class="room-pane">
        <div v-if="rooms.length" class="room-list">
          <button
            v-for="room in rooms"
            :key="room.id"
            class="room-row"
            :class="{ 'is-active': room.id === selectedRoomId }"
            type="button"
            @click="selectRoom(room.id)"
          >
            <span class="room-name">{{ room.name }}</span>
            <span class="room-count">{{ room.devices.length }}</span>
          </button>
        </div>
        <el-empty v-else :image-size="54" description="暂无房间" />
      </aside>

      <main v-if="selectedRoom" class="device-pane" v-loading="loadingRooms">
        <header class="room-head">
          <div>
            <h2>{{ selectedRoom.name }}</h2>
            <span>更新于 {{ formatDate(lastCheckedAt || selectedRoom.updated_at) }}</span>
          </div>
          <div class="room-actions">
            <el-tooltip content="刷新状态" placement="bottom">
              <el-button
                :icon="Refresh"
                circle
                aria-label="刷新状态"
                :loading="refreshingStatus"
                @click="refreshStatus()"
              />
            </el-tooltip>
            <el-tooltip content="重命名房间" placement="bottom">
              <el-button :icon="EditPen" circle aria-label="重命名房间" @click="openEditRoom" />
            </el-tooltip>
            <el-tooltip content="删除房间" placement="bottom">
              <el-button :icon="Delete" circle aria-label="删除房间" @click="removeRoom" />
            </el-tooltip>
            <el-button :icon="Plus" type="primary" @click="openCreateDevice">添加设备</el-button>
          </div>
        </header>

        <div class="status-summary" aria-label="设备状态统计">
          <div class="summary-item">
            <span class="status-dot is-idle"></span>
            <span>空闲</span>
            <strong>{{ statusCounts.idle }}</strong>
          </div>
          <div class="summary-item">
            <span class="status-dot is-running"></span>
            <span>运行</span>
            <strong>{{ statusCounts.running }}</strong>
          </div>
          <div class="summary-item">
            <span class="status-dot is-offline"></span>
            <span>离线</span>
            <strong>{{ statusCounts.offline }}</strong>
          </div>
        </div>

        <div v-if="selectedRoom.devices.length" class="device-grid">
          <article v-for="device in selectedRoom.devices" :key="device.id" class="device-card">
            <div class="device-card-visual">
              <img :src="flexImage" :alt="`${device.name} Flex`" />
              <span class="device-status" :class="`is-${deviceStatus(device.id).status}`">
                <span class="status-dot" :class="`is-${deviceStatus(device.id).status}`"></span>
                {{ statusText[deviceStatus(device.id).status] }}
              </span>
              <el-dropdown
                class="device-menu"
                trigger="click"
                placement="bottom-end"
                @command="handleDeviceCommand($event, device)"
              >
                <el-button :icon="MoreFilled" circle aria-label="设备操作菜单" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="details" :icon="InfoFilled">详细信息</el-dropdown-item>
                    <el-dropdown-item command="manage" :icon="Setting">设备管理</el-dropdown-item>
                    <el-dropdown-item command="edit" :icon="EditPen">编辑设备</el-dropdown-item>
                    <el-dropdown-item command="delete" :icon="Delete" divided>删除设备</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <div class="device-card-body">
              <div class="device-card-title">
                <span class="device-glyph"><el-icon><Cpu /></el-icon></span>
                <div>
                  <h3>{{ device.name }}</h3>
                  <p :class="{ 'is-empty': !device.description }">
                    {{ device.description || '暂无设备描述' }}
                  </p>
                </div>
              </div>

              <section class="device-info-section" aria-label="基本信息">
                <div class="section-label"><el-icon><InfoFilled /></el-icon><span>基本信息</span></div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Connection /></el-icon>设备地址</span>
                  <code>{{ device.ip }}</code>
                </div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Monitor /></el-icon>App Version</span>
                  <span>{{ deviceStatus(device.id).app_version || 'N/A' }}</span>
                </div>
              </section>

              <section class="device-info-section" aria-label="运行详情">
                <div class="section-label"><el-icon><DataLine /></el-icon><span>运行详情</span></div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Document /></el-icon>Protocol</span>
                  <code
                    v-if="deviceStatus(device.id).protocol_name"
                    :title="deviceStatus(device.id).protocol_name || ''"
                  >
                    {{ deviceStatus(device.id).protocol_name }}
                  </code>
                  <span v-else class="muted-text">-</span>
                </div>
                <div class="info-row">
                  <span class="info-key"><el-icon><VideoPlay /></el-icon>运行状态</span>
                  <span v-if="deviceStatus(device.id).run_status">
                    {{ deviceStatus(device.id).run_status }}
                  </span>
                  <span
                    v-else-if="deviceStatus(device.id).error"
                    class="error-text"
                    :title="deviceStatus(device.id).error || ''"
                  >
                    {{ deviceStatus(device.id).error }}
                  </span>
                  <span v-else class="muted-text">-</span>
                </div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Clock /></el-icon>查询时间</span>
                  <span class="checked-time">{{ formatDate(deviceStatus(device.id).checked_at) }}</span>
                </div>
              </section>
            </div>
          </article>
        </div>

        <div v-else class="device-empty">
          <el-empty :image-size="72" description="当前房间暂无设备">
            <el-button :icon="Plus" type="primary" @click="openCreateDevice">添加设备</el-button>
          </el-empty>
        </div>
      </main>

      <main v-else class="no-room-pane">
        <el-empty :image-size="84" description="请先新建房间">
          <el-button :icon="Plus" type="primary" @click="openCreateRoom">新建房间</el-button>
        </el-empty>
      </main>
    </div>

    <el-dialog
      v-model="roomDialogVisible"
      :title="editingRoomId ? '重命名房间' : '新建房间'"
      width="430px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="saveRoom">
        <el-form-item label="房间名称" required>
          <el-input
            v-model="roomName"
            maxlength="80"
            show-word-limit
            placeholder="输入房间名称"
            @keydown.enter.prevent="saveRoom"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roomDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRoom" @click="saveRoom">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deviceDialogVisible"
      :title="editingDeviceId ? '编辑设备' : '添加设备'"
      width="560px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="saveDevice">
        <el-form-item label="在线设备">
          <div class="scan-field">
            <el-select
              v-model="selectedRobotKey"
              filterable
              clearable
              placeholder="选择扫描到的设备"
              @change="applyScannedRobot"
            >
              <el-option
                v-for="robot in onlineRobots"
                :key="robotKey(robot)"
                :label="scannedRobotLabel(robot)"
                :value="robotKey(robot)"
              />
            </el-select>
            <el-tooltip content="扫描在线设备" placement="bottom">
              <el-button
                :icon="Search"
                circle
                aria-label="扫描在线设备"
                :loading="scanning"
                @click="scanOnlineDevices"
              />
            </el-tooltip>
          </div>
        </el-form-item>
        <div class="device-form-grid">
          <el-form-item label="设备名称" required class="name-field">
            <el-input v-model="deviceForm.name" maxlength="80" placeholder="输入设备名称" />
          </el-form-item>
          <el-form-item label="设备描述" class="description-field">
            <el-input
              v-model="deviceForm.description"
              type="textarea"
              :rows="3"
              maxlength="300"
              show-word-limit
              placeholder="输入设备用途、位置或备注"
            />
          </el-form-item>
          <el-form-item label="IP 地址" required>
            <el-input v-model="deviceForm.ip" placeholder="192.168.6.11" />
          </el-form-item>
          <el-form-item label="端口" required>
            <el-input-number
              v-model="deviceForm.port"
              :min="1"
              :max="65535"
              controls-position="right"
            />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDevice" @click="saveDevice">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="detailDrawerVisible"
      :title="detailDrawerTitle"
      direction="rtl"
      size="420px"
    >
      <DeviceInfoPanel
        v-if="detailDrawerVisible && detailDevice"
        ref="detailPanelRef"
        :ip="detailDevice.ip"
        :port="detailDevice.port"
        in-drawer
        :show-header="false"
      />
      <template #footer>
        <el-button @click="detailDrawerVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="detailRefreshing"
          @click="refreshDeviceDetails"
        >刷新</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Clock,
  Connection,
  Cpu,
  DataLine,
  Delete,
  Document,
  EditPen,
  InfoFilled,
  Monitor,
  MoreFilled,
  Plus,
  Refresh,
  Search,
  Setting,
  VideoPlay,
} from '@element-plus/icons-vue'
import flexImage from '@/assets/dashboard/flex.png'
import {
  protocolMonitorApi,
  type ProtocolMonitorDevice,
  type ProtocolMonitorDeviceStatus,
  type ProtocolMonitorRoom,
  type ProtocolMonitorStatus,
  type RobotInfo,
} from '@/scripts/api'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import DeviceInfoPanel from '@/views/devices/components/DeviceInfoPanel.vue'

const STATUS_REFRESH_INTERVAL_MS = 10_000
const router = useRouter()
const statusText: Record<ProtocolMonitorStatus, string> = {
  idle: '空闲',
  offline: '离线',
  running: '运行',
}

const rooms = ref<ProtocolMonitorRoom[]>([])
const selectedRoomId = ref('')
const storage = ref<'mongodb' | 'sqlite' | ''>('')
const loadingRooms = ref(false)
const refreshingStatus = ref(false)
const loadError = ref('')
const lastCheckedAt = ref('')
const statusByDevice = ref<Record<string, ProtocolMonitorDeviceStatus>>({})

const roomDialogVisible = ref(false)
const editingRoomId = ref('')
const roomName = ref('')
const savingRoom = ref(false)

const deviceDialogVisible = ref(false)
const editingDeviceId = ref('')
const savingDevice = ref(false)
const selectedRobotKey = ref('')
const deviceForm = reactive({ name: '', description: '', ip: '', port: 31950 })
const detailDrawerVisible = ref(false)
const detailDevice = ref<ProtocolMonitorDevice | null>(null)
const detailRefreshing = ref(false)
const detailPanelRef = ref<InstanceType<typeof DeviceInfoPanel> | null>(null)

const robotScanStore = useRobotScanStore()
const scanning = computed(() => robotScanStore.scanning)
const onlineRobots = computed(() => robotScanStore.scanResult?.online_robots ?? [])
const selectedRoom = computed(() => rooms.value.find(room => room.id === selectedRoomId.value) ?? null)
const totalDeviceCount = computed(() => rooms.value.reduce((total, room) => total + room.devices.length, 0))
const statusCounts = computed(() => {
  const counts = { idle: 0, running: 0, offline: 0 }
  for (const device of selectedRoom.value?.devices ?? []) {
    counts[deviceStatus(device.id).status] += 1
  }
  return counts
})
const detailDrawerTitle = computed(() => {
  if (!detailDevice.value) return '设备详细信息'
  return `设备详细信息 - ${detailDevice.value.name}`
})

let statusTimer: number | null = null
let statusRequestSequence = 0

function normalizeError(error: any, fallback: string) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return detail?.message || detail?.error || error?.message || fallback
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function offlineStatus(deviceId: string): ProtocolMonitorDeviceStatus {
  return {
    device_id: deviceId,
    status: 'offline',
    checked_at: '',
  }
}

function deviceStatus(deviceId: string) {
  return statusByDevice.value[deviceId] ?? offlineStatus(deviceId)
}

function replaceRoom(updated: ProtocolMonitorRoom) {
  const index = rooms.value.findIndex(room => room.id === updated.id)
  if (index >= 0) rooms.value.splice(index, 1, updated)
  else rooms.value.push(updated)
}

async function loadRooms() {
  loadingRooms.value = true
  loadError.value = ''
  try {
    const response = await protocolMonitorApi.listRooms()
    rooms.value = response.data.rooms
    storage.value = response.data.storage
    if (!rooms.value.some(room => room.id === selectedRoomId.value)) {
      selectedRoomId.value = rooms.value[0]?.id ?? ''
      statusByDevice.value = {}
    }
    if (selectedRoomId.value) await refreshStatus(true)
  } catch (error) {
    loadError.value = normalizeError(error, '加载监控房间失败')
  } finally {
    loadingRooms.value = false
  }
}

async function selectRoom(roomId: string) {
  if (roomId === selectedRoomId.value) return
  selectedRoomId.value = roomId
  statusByDevice.value = {}
  lastCheckedAt.value = ''
  await refreshStatus(true)
}

async function refreshStatus(silent = false) {
  const roomId = selectedRoomId.value
  if (!roomId) return
  const requestSequence = ++statusRequestSequence
  refreshingStatus.value = true
  try {
    const response = await protocolMonitorApi.refreshRoomStatus(roomId)
    if (selectedRoomId.value !== roomId || requestSequence !== statusRequestSequence) return
    statusByDevice.value = Object.fromEntries(
      response.data.statuses.map(status => [status.device_id, status])
    )
    lastCheckedAt.value = response.data.checked_at
  } catch (error) {
    if (!silent) ElMessage.error(normalizeError(error, '刷新设备状态失败'))
  } finally {
    if (requestSequence === statusRequestSequence) refreshingStatus.value = false
  }
}

function openCreateRoom() {
  editingRoomId.value = ''
  roomName.value = ''
  roomDialogVisible.value = true
}

function openEditRoom() {
  if (!selectedRoom.value) return
  editingRoomId.value = selectedRoom.value.id
  roomName.value = selectedRoom.value.name
  roomDialogVisible.value = true
}

async function saveRoom() {
  const name = roomName.value.trim()
  if (!name) {
    ElMessage.warning('请输入房间名称')
    return
  }
  savingRoom.value = true
  try {
    const response = editingRoomId.value
      ? await protocolMonitorApi.updateRoom(editingRoomId.value, name)
      : await protocolMonitorApi.createRoom(name)
    replaceRoom(response.data)
    selectedRoomId.value = response.data.id
    roomDialogVisible.value = false
    ElMessage.success(editingRoomId.value ? '房间已更新' : '房间已创建')
    await refreshStatus(true)
  } catch (error) {
    ElMessage.error(normalizeError(error, '保存房间失败'))
  } finally {
    savingRoom.value = false
  }
}

async function removeRoom() {
  const room = selectedRoom.value
  if (!room) return
  try {
    await ElMessageBox.confirm(`确认删除房间“${room.name}”？`, '删除房间', { type: 'warning' })
    await protocolMonitorApi.deleteRoom(room.id)
    rooms.value = rooms.value.filter(item => item.id !== room.id)
    selectedRoomId.value = rooms.value[0]?.id ?? ''
    statusByDevice.value = {}
    lastCheckedAt.value = ''
    ElMessage.success('房间已删除')
    if (selectedRoomId.value) await refreshStatus(true)
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(normalizeError(error, '删除房间失败'))
  }
}

function resetDeviceForm() {
  deviceForm.name = ''
  deviceForm.description = ''
  deviceForm.ip = ''
  deviceForm.port = 31950
  selectedRobotKey.value = ''
}

async function loadCachedRobots() {
  try {
    await robotScanStore.loadCachedScan({ port: deviceForm.port })
  } catch {
    // The dialog still supports manual IP entry when no scan cache exists.
  }
}

function openCreateDevice() {
  editingDeviceId.value = ''
  resetDeviceForm()
  deviceDialogVisible.value = true
  void loadCachedRobots()
}

function openEditDevice(device: ProtocolMonitorDevice) {
  editingDeviceId.value = device.id
  deviceForm.name = device.name
  deviceForm.description = device.description || ''
  deviceForm.ip = device.ip
  deviceForm.port = device.port
  selectedRobotKey.value = `${device.ip}:${device.port}`
  deviceDialogVisible.value = true
  void loadCachedRobots()
}

function robotKey(robot: RobotInfo) {
  return `${robot.ip}:${robot.port || 31950}`
}

function scannedRobotLabel(robot: RobotInfo) {
  const name = robot.name || robot.serial_number || 'Robot'
  return `${name} · ${robot.ip}:${robot.port || 31950}`
}

function applyScannedRobot(key: string) {
  const robot = onlineRobots.value.find(item => robotKey(item) === key)
  if (!robot) return
  deviceForm.ip = robot.ip
  deviceForm.port = robot.port || 31950
  if (!deviceForm.name.trim()) {
    deviceForm.name = robot.name || robot.serial_number || robot.ip
  }
}

async function scanOnlineDevices() {
  try {
    const result = await robotScanStore.refreshScan({ params: { port: deviceForm.port } })
    ElMessage.success(`发现 ${result?.online_robots.length ?? 0} 台在线设备`)
  } catch (error) {
    ElMessage.error(normalizeError(error, '扫描设备失败'))
  }
}

async function saveDevice() {
  const room = selectedRoom.value
  if (!room) return
  if (!deviceForm.name.trim() || !deviceForm.ip.trim()) {
    ElMessage.warning('请填写设备名称和 IP 地址')
    return
  }
  savingDevice.value = true
  try {
    const payload = {
      name: deviceForm.name.trim(),
      description: deviceForm.description.trim(),
      ip: deviceForm.ip.trim(),
      port: deviceForm.port,
    }
    const response = editingDeviceId.value
      ? await protocolMonitorApi.updateDevice(room.id, editingDeviceId.value, payload)
      : await protocolMonitorApi.addDevice(room.id, payload)
    replaceRoom(response.data)
    deviceDialogVisible.value = false
    ElMessage.success(editingDeviceId.value ? '设备已更新' : '设备已添加')
    await refreshStatus(true)
  } catch (error) {
    ElMessage.error(normalizeError(error, '保存设备失败'))
  } finally {
    savingDevice.value = false
  }
}

function handleDeviceCommand(command: string, device: ProtocolMonitorDevice) {
  if (command === 'details') {
    detailDevice.value = device
    detailDrawerVisible.value = true
    return
  }
  if (command === 'manage') {
    void router.push({ name: 'DeviceControl', query: { ip: device.ip } })
    return
  }
  if (command === 'edit') openEditDevice(device)
  if (command === 'delete') void removeDevice(device)
}

async function refreshDeviceDetails() {
  detailRefreshing.value = true
  try {
    await detailPanelRef.value?.refresh()
  } finally {
    detailRefreshing.value = false
  }
}

async function removeDevice(device: ProtocolMonitorDevice) {
  const room = selectedRoom.value
  if (!room) return
  try {
    await ElMessageBox.confirm(`确认删除设备“${device.name}”？`, '删除设备', { type: 'warning' })
    const response = await protocolMonitorApi.deleteDevice(room.id, device.id)
    replaceRoom(response.data)
    const nextStatuses = { ...statusByDevice.value }
    delete nextStatuses[device.id]
    statusByDevice.value = nextStatuses
    ElMessage.success('设备已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(normalizeError(error, '删除设备失败'))
  }
}

onMounted(() => {
  void loadRooms()
  statusTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void refreshStatus(true)
  }, STATUS_REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (statusTimer !== null) window.clearInterval(statusTimer)
})
</script>

<style scoped>
.protocol-monitor-page {
  --monitor-border: #dfe5e2;
  --monitor-text: #20272c;
  --monitor-muted: #68747c;
  display: flex;
  min-height: 100%;
  flex-direction: column;
  background: #f5f7f6;
  color: var(--monitor-text);
}

.page-head,
.room-head,
.title-line,
.page-title-group,
.page-actions,
.room-actions,
.status-summary,
.summary-item,
.device-card-title,
.device-status,
.section-label,
.info-key,
.scan-field {
  display: flex;
  align-items: center;
}

.page-head {
  min-height: 76px;
  justify-content: space-between;
  gap: 20px;
  padding: 14px 22px;
  border-bottom: 1px solid var(--monitor-border);
  background: #ffffff;
}

.page-title-group {
  min-width: 0;
  gap: 12px;
}

.title-icon {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid #bdd4cb;
  border-radius: 6px;
  background: #edf6f2;
  color: #176b5f;
  font-size: 20px;
}

.title-line {
  gap: 10px;
}

h1,
h2,
h3 {
  margin: 0;
  letter-spacing: 0;
}

h1 {
  font-size: 20px;
  line-height: 1.3;
}

h2 {
  font-size: 18px;
}

h3 {
  font-size: 16px;
  line-height: 1.35;
}

.page-meta,
.room-head span,
.checked-time,
.muted-text {
  color: var(--monitor-muted);
  font-size: 12px;
}

.page-actions,
.room-actions {
  flex-shrink: 0;
  gap: 8px;
}

.load-alert {
  border-radius: 0;
}

.monitor-workspace {
  display: grid;
  min-height: 520px;
  flex: 1;
  grid-template-columns: 240px minmax(0, 1fr);
}

.room-pane {
  min-width: 0;
  border-right: 1px solid var(--monitor-border);
  background: #fbfcfb;
}

.room-list {
  display: grid;
}

.room-row {
  display: grid;
  min-width: 0;
  min-height: 48px;
  padding: 0 14px 0 16px;
  border: 0;
  border-bottom: 1px solid #e8ecea;
  border-left: 3px solid transparent;
  background: transparent;
  color: var(--monitor-text);
  cursor: pointer;
  font: inherit;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  text-align: left;
}

.room-row:hover {
  background: #f1f5f3;
}

.room-row.is-active {
  border-left-color: #176b5f;
  background: #e9f2ee;
  color: #124f47;
}

.room-name {
  overflow: hidden;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.room-count {
  color: #7a858b;
  font-size: 12px;
}

.device-pane,
.no-room-pane {
  min-width: 0;
  min-height: 0;
  background: #ffffff;
}

.device-pane {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
}

.no-room-pane,
.device-empty {
  display: grid;
  place-items: center;
}

.room-head {
  min-height: 68px;
  justify-content: space-between;
  gap: 20px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--monitor-border);
}

.room-head > div:first-child {
  display: grid;
  gap: 4px;
}

.status-summary {
  min-height: 48px;
  gap: 26px;
  padding: 0 18px;
  border-bottom: 1px solid var(--monitor-border);
  background: #fafbfa;
}

.summary-item {
  gap: 7px;
  color: #536069;
  font-size: 12px;
}

.summary-item strong {
  color: var(--monitor-text);
  font-size: 14px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: #9aa3a8;
}

.status-dot.is-idle {
  background: #28a36a;
}

.status-dot.is-running {
  background: #d68a16;
  box-shadow: 0 0 0 3px rgba(214, 138, 22, 0.14);
}

.status-dot.is-offline {
  background: #9aa3a8;
}

.device-grid {
  display: grid;
  min-width: 0;
  min-height: 0;
  align-content: start;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  overflow-y: auto;
  padding: 14px;
}

.device-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dfe5e2;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 2px 7px rgba(32, 39, 44, 0.05);
}

.device-card-visual {
  position: relative;
  display: grid;
  height: 152px;
  place-items: center;
  overflow: hidden;
  border-bottom: 1px solid #e4e9e6;
  background: #f0f3f2;
}

.device-card-visual img {
  display: block;
  width: auto;
  max-width: calc(100% - 36px);
  height: 138px;
  object-fit: contain;
  filter: drop-shadow(0 9px 10px rgba(35, 43, 47, 0.15));
}

.device-card-visual .device-status {
  position: absolute;
  top: 10px;
  left: 10px;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid rgba(223, 229, 226, 0.92);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.94);
}

.device-menu {
  position: absolute;
  top: 8px;
  right: 8px;
}

.device-menu :deep(.el-button) {
  border-color: rgba(223, 229, 226, 0.92);
  background: rgba(255, 255, 255, 0.94);
}

.device-menu :deep(.el-button .el-icon) {
  transform: rotate(90deg);
}

.device-card-body {
  display: grid;
  gap: 11px;
  padding: 13px 14px 14px;
}

.device-card-title {
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
}

.device-card-title > div {
  min-width: 0;
}

.device-card-title h3 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-card-title p {
  display: -webkit-box;
  min-height: 18px;
  margin: 2px 0 0;
  overflow: hidden;
  color: #58646b;
  font-size: 12px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.device-card-title p.is-empty {
  color: #98a1a6;
}

.device-glyph {
  display: grid;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  place-items: center;
  border: 1px solid #d9e1dd;
  border-radius: 4px;
  background: #f6f8f7;
  color: #52615b;
}

code {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  padding: 2px 5px;
  border: 1px solid #e0e5e3;
  border-radius: 3px;
  background: #f5f7f6;
  color: #344149;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}

.device-status {
  gap: 7px;
  font-size: 13px;
  font-weight: 650;
}

.device-status.is-idle {
  color: #168052;
}

.device-status.is-running {
  color: #a9650b;
}

.device-status.is-offline,
.error-text {
  color: #7a858b;
}

.device-info-section {
  display: grid;
  gap: 6px;
}

.device-info-section + .device-info-section {
  padding-top: 10px;
  border-top: 1px solid #edf0ee;
}

.section-label {
  gap: 6px;
  color: #37434a;
  font-size: 12px;
  font-weight: 700;
}

.section-label .el-icon {
  color: #176b5f;
}

.info-row {
  display: grid;
  min-width: 0;
  grid-template-columns: 104px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  color: #414d54;
  font-size: 12px;
  line-height: 1.4;
}

.info-row > :last-child {
  min-width: 0;
  justify-self: end;
  text-align: right;
}

.info-key {
  gap: 6px;
  color: #748087;
  white-space: nowrap;
}

.info-key .el-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.error-text {
  display: block;
  max-width: 100%;
  overflow: hidden;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  gap: 0 14px;
}

.name-field,
.description-field {
  grid-column: 1 / -1;
}

.scan-field {
  width: 100%;
  gap: 8px;
}

.scan-field .el-select {
  min-width: 0;
  flex: 1;
}

@media (max-width: 900px) {
  .page-head,
  .room-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .monitor-workspace {
    grid-template-columns: 180px minmax(0, 1fr);
  }

  .room-actions,
  .page-actions {
    width: 100%;
  }

  .status-summary {
    gap: 16px;
  }
}

@media (max-width: 640px) {
  .monitor-workspace {
    grid-template-columns: 1fr;
  }

  .room-pane {
    border-right: 0;
    border-bottom: 1px solid var(--monitor-border);
  }

  .room-list {
    max-height: 180px;
    overflow-y: auto;
  }

  .device-form-grid {
    grid-template-columns: 1fr;
  }

  .name-field,
  .description-field {
    grid-column: auto;
  }
}
</style>
