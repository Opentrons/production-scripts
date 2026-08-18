<template>
  <div class="protocol-monitor-page">
    <header class="page-head">
      <div class="page-title-group">
        <div class="title-icon" aria-hidden="true">
          <el-icon><Monitor /></el-icon>
        </div>
        <div>
          <div class="title-line">
            <h1>{{ t('protocolMonitor.title') }}</h1>
          </div>
          <span class="page-meta">{{ t('protocolMonitor.meta', { rooms: rooms.length, devices: totalDeviceCount }) }}</span>
        </div>
      </div>
      <div class="page-actions">
        <el-select
          v-if="rooms.length"
          :model-value="selectedRoomId"
          class="room-select"
          filterable
          fit-input-width
          :placeholder="t('protocolMonitor.selectRoomPlaceholder')"
          @change="selectRoom"
        >
          <el-option
            v-for="room in rooms"
            :key="room.id"
            :label="room.name"
            :value="room.id"
          />
        </el-select>
        <el-tooltip :content="t('protocolMonitor.refreshRooms')" placement="bottom">
          <el-button
            :icon="Refresh"
            circle
            :aria-label="t('protocolMonitor.refreshRooms')"
            :loading="loadingRooms"
            @click="loadRooms"
          />
        </el-tooltip>
        <el-button :icon="Plus" type="primary" @click="openCreateRoom">{{ t('protocolMonitor.createRoom') }}</el-button>
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
      <main v-if="selectedRoom" class="device-pane" v-loading="loadingRooms">
        <header class="room-head">
          <div class="room-head-main">
            <span class="room-updated">{{ t('protocolMonitor.updatedAt', { time: formatDate(lastCheckedAt || selectedRoom.updated_at) }) }}</span>
          </div>
          <div class="room-actions">
            <el-tooltip :content="t('protocolMonitor.refreshStatus')" placement="bottom">
              <el-button
                :icon="Refresh"
                circle
                :aria-label="t('protocolMonitor.refreshStatus')"
                :loading="refreshingStatus"
                @click="refreshStatus()"
              />
            </el-tooltip>
            <el-tooltip :content="t('protocolMonitor.renameRoom')" placement="bottom">
              <el-button :icon="EditPen" circle :aria-label="t('protocolMonitor.renameRoom')" @click="openEditRoom" />
            </el-tooltip>
            <el-tooltip :content="t('protocolMonitor.deleteRoom')" placement="bottom">
              <el-button :icon="Delete" circle :aria-label="t('protocolMonitor.deleteRoom')" @click="removeRoom" />
            </el-tooltip>
            <el-button :icon="Plus" type="primary" @click="openCreateDevice">{{ t('protocolMonitor.addDevice') }}</el-button>
          </div>
        </header>

        <div class="status-summary" :aria-label="t('protocolMonitor.statusSummary')">
          <div class="summary-stats">
            <div class="summary-item">
              <span class="status-dot is-idle"></span>
              <span>{{ t('protocolMonitor.statuses.idle') }}</span>
              <strong>{{ statusCounts.idle }}</strong>
            </div>
            <div class="summary-item">
              <span class="status-dot is-running"></span>
              <span>{{ t('protocolMonitor.statuses.running') }}</span>
              <strong>{{ statusCounts.running }}</strong>
            </div>
            <div class="summary-item">
              <span class="status-dot is-offline"></span>
              <span>{{ t('protocolMonitor.statuses.offline') }}</span>
              <strong>{{ statusCounts.offline }}</strong>
            </div>
          </div>
          <div class="view-toggle" role="group" :aria-label="t('protocolMonitor.viewMode')">
            <el-tooltip :content="t('protocolMonitor.viewCard')" placement="bottom">
              <el-button
                :type="deviceViewMode === 'card' ? 'primary' : 'default'"
                :icon="Grid"
                circle
                :aria-pressed="deviceViewMode === 'card'"
                :aria-label="t('protocolMonitor.viewCard')"
                @click="setDeviceViewMode('card')"
              />
            </el-tooltip>
            <el-tooltip :content="t('protocolMonitor.viewList')" placement="bottom">
              <el-button
                :type="deviceViewMode === 'list' ? 'primary' : 'default'"
                :icon="List"
                circle
                :aria-pressed="deviceViewMode === 'list'"
                :aria-label="t('protocolMonitor.viewList')"
                @click="setDeviceViewMode('list')"
              />
            </el-tooltip>
          </div>
        </div>

        <div v-if="selectedRoom.devices.length && deviceViewMode === 'card'" class="device-grid">
          <article v-for="device in selectedRoom.devices" :key="device.id" class="device-card">
            <div class="device-card-visual">
              <DeviceCameraMedia
                :room-id="selectedRoom.id"
                :device-id="device.id"
                :device-name="device.name"
                :image-src="flexImage"
              >
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
                  <el-button :icon="MoreFilled" circle :aria-label="t('protocolMonitor.deviceMenu')" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="details" :icon="InfoFilled">{{ t('protocolMonitor.details') }}</el-dropdown-item>
                      <el-dropdown-item command="manage" :icon="Setting">{{ t('protocolMonitor.manage') }}</el-dropdown-item>
                      <el-dropdown-item command="connect-odd" :icon="Monitor">{{ t('protocolMonitor.openConnectOdd') }}</el-dropdown-item>
                      <el-dropdown-item command="edit" :icon="EditPen">{{ t('protocolMonitor.editDevice') }}</el-dropdown-item>
                      <el-dropdown-item command="delete" :icon="Delete" divided>{{ t('protocolMonitor.deleteDevice') }}</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </DeviceCameraMedia>
            </div>

            <div class="device-card-body">
              <div class="device-card-title">
                <span class="device-glyph"><el-icon><Cpu /></el-icon></span>
                <div>
                  <h3>{{ device.name }}</h3>
                  <p :class="{ 'is-empty': !device.description }">
                    {{ device.description || t('protocolMonitor.noDescription') }}
                  </p>
                </div>
              </div>

              <section class="device-info-section" :aria-label="t('protocolMonitor.basicInfo')">
                <div class="section-label"><el-icon><InfoFilled /></el-icon><span>{{ t('protocolMonitor.basicInfo') }}</span></div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Connection /></el-icon>{{ t('protocolMonitor.deviceAddress') }}</span>
                  <code>{{ device.ip }}</code>
                </div>
                <div class="info-row">
                  <span class="info-key"><el-icon><Monitor /></el-icon>App Version</span>
                  <span>{{ deviceStatus(device.id).app_version || 'N/A' }}</span>
                </div>
              </section>

              <section class="device-info-section" :aria-label="t('protocolMonitor.runDetails')">
                <div class="section-label"><el-icon><DataLine /></el-icon><span>{{ t('protocolMonitor.runDetails') }}</span></div>
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
                  <span class="info-key"><el-icon><VideoPlay /></el-icon>{{ t('protocolMonitor.runStatus') }}</span>
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
                  <span class="info-key"><el-icon><Clock /></el-icon>{{ t('protocolMonitor.checkedAt') }}</span>
                  <span class="checked-time">{{ formatDate(deviceStatus(device.id).checked_at) }}</span>
                </div>
              </section>
            </div>
          </article>
        </div>

        <div v-else-if="selectedRoom.devices.length" class="device-list">
          <div class="device-list-head" aria-hidden="true">
            <span>{{ t('protocolMonitor.statusColumn') }}</span>
            <span>{{ t('protocolMonitor.deviceName') }}</span>
            <span>{{ t('protocolMonitor.deviceAddress') }}</span>
            <span>Protocol</span>
            <span>{{ t('protocolMonitor.checkedAt') }}</span>
            <span></span>
          </div>
          <article
            v-for="device in selectedRoom.devices"
            :key="device.id"
            class="device-list-row"
          >
            <span class="device-status is-inline" :class="`is-${deviceStatus(device.id).status}`">
              <span class="status-dot" :class="`is-${deviceStatus(device.id).status}`"></span>
              {{ statusText[deviceStatus(device.id).status] }}
            </span>
            <div class="device-list-name">
              <strong>{{ device.name }}</strong>
              <small :class="{ 'is-empty': !device.description }">
                {{ device.description || t('protocolMonitor.noDescription') }}
              </small>
            </div>
            <code class="device-list-ip">{{ device.ip }}</code>
            <div class="device-list-protocol">
              <span
                v-if="deviceStatus(device.id).protocol_name"
                class="protocol-text"
                :title="deviceStatus(device.id).protocol_name || ''"
              >
                {{ deviceStatus(device.id).protocol_name }}
              </span>
              <span v-else-if="deviceStatus(device.id).run_status">{{ deviceStatus(device.id).run_status }}</span>
              <span
                v-else-if="deviceStatus(device.id).error"
                class="error-text"
                :title="deviceStatus(device.id).error || ''"
              >
                {{ deviceStatus(device.id).error }}
              </span>
              <span v-else class="muted-text">-</span>
            </div>
            <span class="checked-time">{{ formatDate(deviceStatus(device.id).checked_at) }}</span>
            <el-dropdown
              class="device-list-menu"
              trigger="click"
              placement="bottom-end"
              @command="handleDeviceCommand($event, device)"
            >
              <el-button :icon="MoreFilled" circle :aria-label="t('protocolMonitor.deviceMenu')" />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="details" :icon="InfoFilled">{{ t('protocolMonitor.details') }}</el-dropdown-item>
                  <el-dropdown-item command="manage" :icon="Setting">{{ t('protocolMonitor.manage') }}</el-dropdown-item>
                  <el-dropdown-item command="connect-odd" :icon="Monitor">{{ t('protocolMonitor.openConnectOdd') }}</el-dropdown-item>
                  <el-dropdown-item command="edit" :icon="EditPen">{{ t('protocolMonitor.editDevice') }}</el-dropdown-item>
                  <el-dropdown-item command="delete" :icon="Delete" divided>{{ t('protocolMonitor.deleteDevice') }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </article>
        </div>

        <div v-else class="device-empty">
          <el-empty :image-size="72" :description="t('protocolMonitor.noDevices')">
            <el-button :icon="Plus" type="primary" @click="openCreateDevice">{{ t('protocolMonitor.addDevice') }}</el-button>
          </el-empty>
        </div>
      </main>

      <main v-else class="no-room-pane">
        <el-empty :image-size="84" :description="t('protocolMonitor.createRoomFirst')">
          <el-button :icon="Plus" type="primary" @click="openCreateRoom">{{ t('protocolMonitor.createRoom') }}</el-button>
        </el-empty>
      </main>
    </div>

    <el-dialog
      v-model="roomDialogVisible"
      :title="t(editingRoomId ? 'protocolMonitor.renameRoom' : 'protocolMonitor.createRoom')"
      width="430px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="saveRoom">
        <el-form-item :label="t('protocolMonitor.roomName')" required>
          <el-input
            v-model="roomName"
            maxlength="80"
            show-word-limit
            :placeholder="t('protocolMonitor.roomNamePlaceholder')"
            @keydown.enter.prevent="saveRoom"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roomDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="savingRoom" @click="saveRoom">{{ t('common.actions.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deviceDialogVisible"
      :title="t(editingDeviceId ? 'protocolMonitor.addOrEditDevice.edit' : 'protocolMonitor.addOrEditDevice.add')"
      width="560px"
      destroy-on-close
    >
      <el-form label-position="top" @submit.prevent="saveDevice">
        <el-form-item :label="t('protocolMonitor.onlineDevice')">
          <div class="scan-field">
            <el-select
              v-model="selectedRobotKey"
              filterable
              clearable
              :placeholder="t('protocolMonitor.selectScanned')"
              @change="applyScannedRobot"
            >
              <el-option
                v-for="robot in onlineRobots"
                :key="robotKey(robot)"
                :label="scannedRobotLabel(robot)"
                :value="robotKey(robot)"
              />
            </el-select>
            <el-tooltip :content="t('protocolMonitor.scanOnline')" placement="bottom">
              <el-button
                :icon="Search"
                circle
                :aria-label="t('protocolMonitor.scanOnline')"
                :loading="scanning"
                @click="scanOnlineDevices"
              />
            </el-tooltip>
          </div>
        </el-form-item>
        <div class="device-form-grid">
          <el-form-item :label="t('protocolMonitor.deviceName')" required class="name-field">
            <el-input v-model="deviceForm.name" maxlength="80" :placeholder="t('protocolMonitor.deviceNamePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('protocolMonitor.deviceDescription')" class="description-field">
            <el-input
              v-model="deviceForm.description"
              type="textarea"
              :rows="3"
              maxlength="300"
              show-word-limit
              :placeholder="t('protocolMonitor.descriptionPlaceholder')"
            />
          </el-form-item>
          <el-form-item :label="t('protocolMonitor.ipAddress')" required>
            <el-input v-model="deviceForm.ip" placeholder="192.168.6.11" />
          </el-form-item>
          <el-form-item :label="t('protocolMonitor.port')" required>
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
        <el-button @click="deviceDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="savingDevice" @click="saveDevice">{{ t('common.actions.save') }}</el-button>
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
        <el-button @click="detailDrawerVisible = false">{{ t('common.actions.close') }}</el-button>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="detailRefreshing"
          @click="refreshDeviceDetails"
        >{{ t('common.actions.refresh') }}</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
  Grid,
  InfoFilled,
  List,
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
import DeviceCameraMedia from '@/views/test_modules/components/DeviceCameraMedia.vue'
import { useI18n } from 'vue-i18n'
import { useAppLocale } from '@/i18n'

const DEVICE_VIEW_MODE_KEY = 'protocol-monitor-device-view-mode'
type DeviceViewMode = 'card' | 'list'

function readDeviceViewMode(): DeviceViewMode {
  try {
    const value = localStorage.getItem(DEVICE_VIEW_MODE_KEY)
    return value === 'list' ? 'list' : 'card'
  } catch {
    return 'card'
  }
}

const { t } = useI18n()
const { locale } = useAppLocale()
const router = useRouter()
const statusText = computed<Record<ProtocolMonitorStatus, string>>(() => ({
  idle: t('protocolMonitor.statuses.idle'),
  offline: t('protocolMonitor.statuses.offline'),
  running: t('protocolMonitor.statuses.running'),
}))

const rooms = ref<ProtocolMonitorRoom[]>([])
const selectedRoomId = ref('')
const storage = ref<'mongodb' | 'sqlite' | ''>('')
const loadingRooms = ref(false)
const refreshingStatus = ref(false)
const loadError = ref('')
const lastCheckedAt = ref('')
const statusByDevice = ref<Record<string, ProtocolMonitorDeviceStatus>>({})
const deviceViewMode = ref<DeviceViewMode>(readDeviceViewMode())

function setDeviceViewMode(mode: DeviceViewMode) {
  deviceViewMode.value = mode
  try {
    localStorage.setItem(DEVICE_VIEW_MODE_KEY, mode)
  } catch {
    // ignore quota / private mode failures
  }
}
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
  if (!detailDevice.value) return t('protocolMonitor.detailTitle')
  return t('protocolMonitor.detailNamed', { name: detailDevice.value.name })
})

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
  return date.toLocaleString(locale.value, { hour12: false })
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
    loadError.value = normalizeError(error, t('protocolMonitor.errors.loadRooms'))
  } finally {
    loadingRooms.value = false
  }
}

async function selectRoom(roomId: string) {
  if (roomId === selectedRoomId.value) return
  selectedRoomId.value = roomId
  statusByDevice.value = {}
  lastCheckedAt.value = ''
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
    if (!silent) ElMessage.error(normalizeError(error, t('protocolMonitor.errors.refreshStatus')))
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
    ElMessage.warning(t('protocolMonitor.enterRoomName'))
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
    ElMessage.success(t(editingRoomId.value ? 'protocolMonitor.roomUpdated' : 'protocolMonitor.roomCreated'))
    await refreshStatus(true)
  } catch (error) {
    ElMessage.error(normalizeError(error, t('protocolMonitor.errors.saveRoom')))
  } finally {
    savingRoom.value = false
  }
}

async function removeRoom() {
  const room = selectedRoom.value
  if (!room) return
  try {
    await ElMessageBox.confirm(t('protocolMonitor.roomDeleteConfirm', { name: room.name }), t('protocolMonitor.deleteRoom'), { type: 'warning' })
    await protocolMonitorApi.deleteRoom(room.id)
    rooms.value = rooms.value.filter(item => item.id !== room.id)
    selectedRoomId.value = rooms.value[0]?.id ?? ''
    statusByDevice.value = {}
    lastCheckedAt.value = ''
    ElMessage.success(t('protocolMonitor.roomDeleted'))
    if (selectedRoomId.value) await refreshStatus(true)
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(normalizeError(error, t('protocolMonitor.errors.deleteRoom')))
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
    ElMessage.success(t('protocolMonitor.devicesFound', { count: result?.online_robots.length ?? 0 }))
  } catch (error) {
    ElMessage.error(normalizeError(error, t('protocolMonitor.errors.scan')))
  }
}

async function saveDevice() {
  const room = selectedRoom.value
  if (!room) return
  if (!deviceForm.name.trim() || !deviceForm.ip.trim()) {
    ElMessage.warning(t('protocolMonitor.enterDevice'))
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
    ElMessage.success(t(editingDeviceId.value ? 'protocolMonitor.deviceUpdated' : 'protocolMonitor.deviceAdded'))
    await refreshStatus(true)
  } catch (error) {
    ElMessage.error(normalizeError(error, t('protocolMonitor.errors.saveDevice')))
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
  if (command === 'connect-odd') {
    void router.push({
      name: 'ProtocolOddWorkspace',
      query: {
        mode: 'remote',
        ip: device.ip,
        name: device.name,
        port: String(device.port || 31950),
      },
    })
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
    await ElMessageBox.confirm(t('protocolMonitor.deviceDeleteConfirm', { name: device.name }), t('protocolMonitor.deleteDevice'), { type: 'warning' })
    const response = await protocolMonitorApi.deleteDevice(room.id, device.id)
    replaceRoom(response.data)
    const nextStatuses = { ...statusByDevice.value }
    delete nextStatuses[device.id]
    statusByDevice.value = nextStatuses
    ElMessage.success(t('protocolMonitor.deviceDeleted'))
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(normalizeError(error, t('protocolMonitor.errors.deleteDevice')))
  }
}

onMounted(() => {
  void loadRooms()
})
</script>

<style scoped>
.protocol-monitor-page {
  --monitor-border: #dce3eb;
  --monitor-text: #172033;
  --monitor-muted: #6b778a;
  --monitor-accent: #276fbf;
  --monitor-accent-soft: #edf3fa;
  display: flex;
  min-height: 100%;
  flex-direction: column;
  background: #eef2f6;
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
  border: 1px solid #cfd8e3;
  border-radius: 6px;
  background: var(--monitor-accent-soft);
  color: var(--monitor-accent);
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
.room-updated,
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
  grid-template-columns: minmax(0, 1fr);
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

.room-head-main {
  display: grid;
  min-width: 0;
}

.room-select {
  width: 240px;
  max-width: 240px;
  flex: 0 0 240px;
}

.room-select :deep(.el-select__wrapper) {
  width: 100%;
}

.room-select :deep(.el-select__selected-item),
.room-select :deep(.el-select__placeholder) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-summary {
  min-height: 48px;
  justify-content: space-between;
  gap: 16px;
  padding: 0 18px;
  border-bottom: 1px solid var(--monitor-border);
  background: #f8fafc;
}

.summary-stats {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 26px;
}

.view-toggle {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 6px;
}

.summary-item {
  gap: 7px;
  color: #5d6879;
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
  background: #8aa0b8;
}

.status-dot.is-idle {
  background: #2f9e73;
}

.status-dot.is-running {
  background: #c27803;
  box-shadow: 0 0 0 3px rgba(194, 120, 3, 0.14);
}

.status-dot.is-offline {
  background: #8aa0b8;
}

.device-grid {
  display: grid;
  min-width: 0;
  min-height: 0;
  align-content: start;
  justify-content: start;
  grid-template-columns: repeat(auto-fill, minmax(250px, 280px));
  gap: 14px;
  overflow-y: auto;
  padding: 14px;
}

.device-list {
  display: grid;
  min-width: 0;
  min-height: 0;
  align-content: start;
  gap: 0;
  overflow: auto;
  padding: 8px 14px 14px;
}

.device-list-head,
.device-list-row {
  display: grid;
  min-width: 760px;
  grid-template-columns: 88px minmax(140px, 1.2fr) minmax(110px, 0.8fr) minmax(160px, 1.4fr) 150px 44px;
  align-items: center;
  gap: 12px;
}

.device-list-head {
  padding: 8px 12px;
  color: #7a8596;
  font-size: 12px;
  font-weight: 650;
}

.device-list-row {
  min-height: 64px;
  padding: 10px 12px;
  border: 1px solid #e4ebf3;
  border-radius: 6px;
  background: #ffffff;
}

.device-list-row + .device-list-row {
  margin-top: 8px;
}

.device-list-name {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.device-list-name strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-name small {
  overflow: hidden;
  color: #5d6879;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-name small.is-empty {
  color: #8aa0b8;
}

.device-list-ip,
.protocol-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-protocol {
  min-width: 0;
  font-size: 13px;
}

.device-status.is-inline {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid #e4ebf3;
  border-radius: 5px;
  background: #f8fafc;
  font-size: 12px;
  white-space: nowrap;
}

.device-list-menu :deep(.el-button .el-icon) {
  transform: rotate(90deg);
}

.device-card {
  width: 100%;
  max-width: 280px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dce3eb;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 2px 7px rgba(23, 32, 51, 0.05);
}

.device-card-visual {
  position: relative;
  display: grid;
  height: 140px;
  place-items: center;
  overflow: hidden;
  border-bottom: 1px solid #e4ebf3;
  background: #eef2f6;
}

.device-card-visual img {
  display: block;
  width: auto;
  max-width: calc(100% - 32px);
  max-height: 126px;
  height: auto;
  object-fit: contain;
  filter: drop-shadow(0 9px 10px rgba(23, 32, 51, 0.14));
}

.device-card-visual .device-status {
  position: absolute;
  top: 10px;
  left: 10px;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid rgba(220, 227, 235, 0.95);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.94);
}

.device-menu {
  position: absolute;
  top: 8px;
  right: 8px;
}

.device-menu :deep(.el-button) {
  border-color: rgba(220, 227, 235, 0.95);
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
  color: #5d6879;
  font-size: 12px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.device-card-title p.is-empty {
  color: #8aa0b8;
}

.device-glyph {
  display: grid;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  place-items: center;
  border: 1px solid #cad6e4;
  border-radius: 4px;
  background: #f8fafc;
  color: #5d6879;
}

code {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  padding: 2px 5px;
  border: 1px solid #d9e1ea;
  border-radius: 3px;
  background: #f8fafc;
  color: #172033;
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
  color: #2f9e73;
}

.device-status.is-running {
  color: #c27803;
}

.device-status.is-offline,
.error-text {
  color: #7a8596;
}

.device-info-section {
  display: grid;
  gap: 6px;
}

.device-info-section + .device-info-section {
  padding-top: 10px;
  border-top: 1px solid #e4ebf3;
}

.section-label {
  gap: 6px;
  color: #172033;
  font-size: 12px;
  font-weight: 700;
}

.section-label .el-icon {
  color: var(--monitor-accent);
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
  color: #6b778a;
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
    grid-template-columns: minmax(0, 1fr);
  }

  .room-actions,
  .page-actions {
    width: 100%;
  }

  .page-actions {
    flex-wrap: wrap;
  }

  .status-summary {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
    padding: 10px 18px;
  }

  .summary-stats {
    flex-wrap: wrap;
    gap: 16px;
  }
}

@media (max-width: 640px) {
  .room-select {
    width: 100%;
    max-width: none;
    flex: 1 1 auto;
  }

  .device-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }

  .device-card {
    max-width: none;
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
