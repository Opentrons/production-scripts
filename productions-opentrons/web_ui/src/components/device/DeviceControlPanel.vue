<template>
  <div class="device-control-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <section class="control-console">
        <div class="section-header">
          <div>
            <div class="section-title">设备控制</div>
            <div class="section-subtitle">常用设备动作</div>
          </div>
        </div>

        <div class="control-actions">
          <el-button
            type="primary"
            :loading="actionLoading === 'home'"
            :disabled="Boolean(jogSessionRunId)"
            @click="handleHome"
          >
            Home 全部轴
          </el-button>
          <div class="reset-control">
            <el-select
              v-model="resetAxis"
              class="reset-axis-select"
              placeholder="选择复位目标"
              :disabled="Boolean(jogSessionRunId)"
            >
              <el-option-group
                v-for="group in resetAxisGroups"
                :key="group.label"
                :label="group.label"
              >
                <el-option
                  v-for="option in group.options"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-option-group>
            </el-select>
            <el-button
              :loading="actionLoading === 'reset'"
              :disabled="Boolean(jogSessionRunId)"
              @click="handleReset"
            >
              复位
            </el-button>
          </div>
          <el-button type="danger" :loading="actionLoading === 'reboot'" @click="handleReboot">
            重启
          </el-button>
        </div>

        <div class="jog-console">
          <div class="jog-header">
            <div>
              <div class="section-title">Jog 设备</div>
              <div class="section-subtitle">创建 Maintenance Run 后控制 X / Y / Mount Z 轴相对移动</div>
            </div>
            <div class="jog-session-actions">
              <el-tag v-if="jogSessionRunId" size="small" type="success">
                Jog 已开始
              </el-tag>
              <el-button
                :type="jogSessionRunId ? 'danger' : 'primary'"
                :loading="jogSessionRunId ? jogReleaseLoading : jogStartLoading"
                :disabled="jogSessionRunId
                  ? Boolean(activeJogDirection) || Boolean(activeGripperAction) || activeDropTip
                  : jogBusy || Boolean(actionLoading)"
                @click="handleJogSessionToggle"
              >
                {{ jogSessionRunId ? '释放 Jog' : '开始 Jog' }}
              </el-button>
            </div>
          </div>

          <div class="jog-settings">
            <label class="jog-mount-field">
              <span class="field-label">Mount</span>
              <el-segmented
                v-model="jogMount"
                :options="jogMountOptions"
                :disabled="jogBusy"
              />
            </label>
            <div class="jog-shortcut-toggle">
              <el-checkbox v-model="jogShortcutEnabled">
                启用快捷键
              </el-checkbox>
            </div>
            <div
              class="jog-step-settings"
              :class="{ 'is-single': jogMount === 'gripper' }"
            >
              <label class="jog-step-field">
                <span class="field-label">XYZ 步进</span>
                <el-input-number
                  v-model="jogStep"
                  :min="0.1"
                  :max="100"
                  :step="1"
                  :precision="1"
                  controls-position="right"
                  :disabled="jogBusy"
                />
                <span class="jog-step-unit">mm</span>
              </label>
              <label v-if="jogMount !== 'gripper'" class="jog-step-field">
                <span class="field-label">Plunger 步进</span>
                <el-input-number
                  v-model="jogPlungerStep"
                  :min="0.1"
                  :max="10"
                  :step="0.1"
                  :precision="1"
                  controls-position="right"
                  :disabled="jogBusy"
                />
                <span class="jog-step-unit">mm</span>
              </label>
            </div>
          </div>

          <div class="jog-body">
            <div class="jog-pad" aria-label="Jog 方向控制">
              <el-button
                class="jog-button jog-up"
                :loading="activeJogDirection === 'up'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'up')"
                aria-label="向上移动 Y 正方向"
                @click="handleJog('up')"
              >
                <el-icon><ArrowUp /></el-icon>
                <span>Y+</span>
              </el-button>
              <el-button
                class="jog-button jog-left"
                :loading="activeJogDirection === 'left'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'left')"
                aria-label="向左移动 X 负方向"
                @click="handleJog('left')"
              >
                <el-icon><ArrowLeft /></el-icon>
                <span>X−</span>
              </el-button>
              <div class="jog-center">Jog</div>
              <el-button
                class="jog-button jog-right"
                :loading="activeJogDirection === 'right'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'right')"
                aria-label="向右移动 X 正方向"
                @click="handleJog('right')"
              >
                <el-icon><ArrowRight /></el-icon>
                <span>X+</span>
              </el-button>
              <el-button
                class="jog-button jog-down"
                :loading="activeJogDirection === 'down'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'down')"
                aria-label="向下移动 Y 负方向"
                @click="handleJog('down')"
              >
                <el-icon><ArrowDown /></el-icon>
                <span>Y−</span>
              </el-button>
            </div>

            <div class="jog-z-group">
              <div class="jog-z-control">
                <el-button
                  class="jog-button jog-z-button"
                  :loading="activeJogDirection === 'z_up'"
                  :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'z_up')"
                  aria-label="Mount Z 正方向移动"
                  @click="handleJog('z_up')"
                >
                  <el-icon><ArrowUp /></el-icon>
                  <span>Z+</span>
                </el-button>
                <div class="jog-z-center">
                  {{ jogZLabel }}
                </div>
                <el-button
                  class="jog-button jog-z-button"
                  :loading="activeJogDirection === 'z_down'"
                  :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'z_down')"
                  aria-label="Mount Z 负方向移动"
                  @click="handleJog('z_down')"
                >
                  <el-icon><ArrowDown /></el-icon>
                  <span>Z−</span>
                </el-button>
              </div>
              <div v-if="jogMount === 'gripper'" class="jog-gripper-actions">
                <el-button
                  :loading="activeGripperAction === 'grip'"
                  :disabled="!jogSessionRunId || (jogBusy && activeGripperAction !== 'grip')"
                  @click="handleGripperAction('grip')"
                >
                  Grip
                </el-button>
                <el-button
                  :loading="activeGripperAction === 'ungrip'"
                  :disabled="!jogSessionRunId || (jogBusy && activeGripperAction !== 'ungrip')"
                  @click="handleGripperAction('ungrip')"
                >
                  Ungrip
                </el-button>
              </div>
            </div>

            <div v-if="jogMount !== 'gripper'" class="jog-plunger-group">
              <div class="jog-plunger-control">
                <el-button
                  class="jog-button"
                  :loading="activeJogDirection === 'plunger_up'"
                  :disabled="!jogSessionRunId || !selectedJogPipette || (jogBusy && activeJogDirection !== 'plunger_up')"
                  aria-label="Pipette Plunger 正方向移动"
                  @click="handleJog('plunger_up')"
                >
                  <el-icon><ArrowUp /></el-icon>
                  <span>P+</span>
                </el-button>
                <div class="jog-plunger-center">
                  {{ selectedJogMountLabel }}
                </div>
                <el-button
                  class="jog-button"
                  :loading="activeJogDirection === 'plunger_down'"
                  :disabled="!jogSessionRunId || !selectedJogPipette || (jogBusy && activeJogDirection !== 'plunger_down')"
                  aria-label="Pipette Plunger 负方向移动"
                  @click="handleJog('plunger_down')"
                >
                  <el-icon><ArrowDown /></el-icon>
                  <span>P−</span>
                </el-button>
              </div>
              <el-button
                class="drop-tip-button"
                :loading="activeDropTip"
                :disabled="!jogSessionRunId || !selectedJogPipette || (jogBusy && !activeDropTip)"
                @click="handleDropTip"
              >
                Drop Tip
              </el-button>
            </div>

            <div class="jog-description">
              <span>XYZ 每次移动 {{ jogStep.toFixed(1) }} mm</span>
              <span>上 / 下：Y±，左 / 右：X±</span>
              <span>Z±：{{ jogZAxis }}</span>
              <span v-if="jogMount === 'gripper'">夹爪：Grip / Ungrip</span>
              <span v-else>Plunger±：{{ jogPlungerAxis }} · 每次 {{ jogPlungerStep.toFixed(1) }} mm</span>
              <span v-if="jogMount !== 'gripper' && selectedJogPipette">
                Pipette：{{ selectedJogPipette.name }}
              </span>
              <span v-else-if="jogMount !== 'gripper'">当前 Mount 未加载移液器</span>
              <span v-if="jogShortcutEnabled" class="jog-shortcut-hint">
                快捷键：W/S = Y± · A/D = X± · I/K = Z± ·
                O/L = {{ jogMount === 'gripper' ? 'Grip/Ungrip' : 'Plunger±' }}
              </span>
              <span v-if="jogSessionRunId" class="jog-run-id">Run：{{ jogSessionRunId }}</span>
              <span v-else>请先点击“开始 Jog”创建 Maintenance Run</span>
            </div>
          </div>
        </div>
      </section>
    </template>

  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from '@element-plus/icons-vue'
import { robotApi } from '@/api'

const props = defineProps<{
  ip: string | null
}>()

type JogDirection =
  | 'up'
  | 'down'
  | 'left'
  | 'right'
  | 'z_up'
  | 'z_down'
  | 'plunger_up'
  | 'plunger_down'
type JogMount = 'left' | 'right' | 'gripper'
type GripperAction = 'grip' | 'ungrip'
type PipetteMount = Exclude<JogMount, 'gripper'>
type JogPipetteInfo = {
  pipette_id: string
  name: string
  model?: string | null
  tip_detected?: boolean | null
}

const actionLoading = ref<'home' | 'reset' | 'reboot' | null>(null)
const activeJogDirection = ref<JogDirection | null>(null)
const activeGripperAction = ref<GripperAction | null>(null)
const activeDropTip = ref(false)
const jogSessionRunId = ref('')
const jogSessionIp = ref('')
const jogStartLoading = ref(false)
const jogReleaseLoading = ref(false)
const jogStep = ref(10)
const jogPlungerStep = ref(1)
const jogMount = ref<JogMount>('left')
const jogShortcutEnabled = ref(false)
const jogPipettes = ref<Partial<Record<PipetteMount, JogPipetteInfo>>>({})
const resetAxis = ref('x')
const jogMountOptions = [
  { label: 'Left', value: 'left' },
  { label: 'Right', value: 'right' },
  { label: 'Gripper', value: 'gripper' }
]
const jogDirectionLabels: Record<JogDirection, string> = {
  up: '向上',
  down: '向下',
  left: '向左',
  right: '向右',
  z_up: 'Z 正方向',
  z_down: 'Z 负方向',
  plunger_up: 'Plunger 正方向',
  plunger_down: 'Plunger 负方向'
}
const resetAxisGroups = [
  {
    label: 'Gantry 轴',
    options: [
      { value: 'x', label: 'X 轴' },
      { value: 'y', label: 'Y 轴' }
    ]
  },
  {
    label: 'Mount',
    options: [
      { value: 'leftZ', label: '左 Mount Z 轴' },
      { value: 'rightZ', label: '右 Mount Z 轴' }
    ]
  },
  {
    label: 'Pipette Plunger',
    options: [
      { value: 'leftPlunger', label: '左 Pipette Plunger' },
      { value: 'rightPlunger', label: '右 Pipette Plunger' }
    ]
  },
  {
    label: '扩展轴',
    options: [
      { value: 'extensionZ', label: 'Gripper Extension Z' },
      { value: 'extensionJaw', label: 'Gripper Jaw' },
      { value: 'axis96ChannelCam', label: '96 Channel Cam' }
    ]
  }
]

const resetAxisLabel = computed(() => {
  for (const group of resetAxisGroups) {
    const option = group.options.find(item => item.value === resetAxis.value)
    if (option) return option.label
  }
  return resetAxis.value
})

const jogZAxis = computed(() => ({
  left: 'leftZ',
  right: 'rightZ',
  gripper: 'extensionZ'
})[jogMount.value])

const jogZLabel = computed(() => ({
  left: 'Left',
  right: 'Right',
  gripper: 'Gripper Z'
})[jogMount.value])

const selectedJogMountLabel = computed(() => ({
  left: 'Left',
  right: 'Right',
  gripper: 'Gripper'
})[jogMount.value])

const selectedJogPipette = computed(() => (
  jogMount.value === 'gripper' ? null : jogPipettes.value[jogMount.value]
))

const jogPlungerAxis = computed(() => (
  jogMount.value === 'right' ? 'rightPlunger' : 'leftPlunger'
))

const jogBusy = computed(() => (
  jogStartLoading.value
  || jogReleaseLoading.value
  || Boolean(activeJogDirection.value)
  || Boolean(activeGripperAction.value)
  || activeDropTip.value
))

function normalizeError(error: any, fallback: string): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.message
    || error?.message
    || fallback
}

async function handleHome() {
  if (!props.ip) return
  actionLoading.value = 'home'
  try {
    await robotApi.homeRobot(props.ip, { target: 'robot' })
    ElMessage.success('Home 命令已发送')
  } catch (error: any) {
    ElMessage.error(error.message || 'Home 失败')
  } finally {
    actionLoading.value = null
  }
}

async function handleJog(direction: JogDirection) {
  if (!props.ip || !jogSessionRunId.value) {
    ElMessage.warning('请先开始 Jog')
    return
  }
  const isPlungerMove = direction === 'plunger_up' || direction === 'plunger_down'
  if (isPlungerMove && !selectedJogPipette.value) {
    ElMessage.warning('当前 Mount 未加载移液器')
    return
  }
  const step = isPlungerMove ? jogPlungerStep.value : jogStep.value
  activeJogDirection.value = direction
  try {
    await robotApi.moveJogRobot(props.ip, jogSessionRunId.value, {
      direction,
      step_mm: step,
      mount: jogMount.value
    })
    ElMessage.success(`${jogDirectionLabels[direction]}移动 ${step.toFixed(1)} mm 完成`)
  } catch (error: any) {
    ElMessage.error(normalizeError(error, 'Jog 移动失败'))
  } finally {
    activeJogDirection.value = null
  }
}

function handleJogShortcut(event: KeyboardEvent) {
  if (
    !jogShortcutEnabled.value
    || event.repeat
    || event.ctrlKey
    || event.metaKey
    || event.altKey
  ) return

  const target = event.target
  if (
    target instanceof HTMLElement
    && (
      target.isContentEditable
      || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
    )
  ) return
  if (document.querySelector('.el-message-box')) return

  const key = event.key.toLowerCase()
  if (!['w', 'a', 's', 'd', 'i', 'k', 'o', 'l'].includes(key)) return
  event.preventDefault()
  if (jogBusy.value) return

  if (key === 'w') void handleJog('up')
  if (key === 'a') void handleJog('left')
  if (key === 's') void handleJog('down')
  if (key === 'd') void handleJog('right')
  if (key === 'i') void handleJog('z_up')
  if (key === 'k') void handleJog('z_down')
  if (key === 'o') {
    if (jogMount.value === 'gripper') void handleGripperAction('grip')
    else void handleJog('plunger_up')
  }
  if (key === 'l') {
    if (jogMount.value === 'gripper') void handleGripperAction('ungrip')
    else void handleJog('plunger_down')
  }
}

async function handleDropTip() {
  const pipette = selectedJogPipette.value
  if (!props.ip || !jogSessionRunId.value) {
    ElMessage.warning('请先开始 Jog')
    return
  }
  if (!pipette) {
    ElMessage.warning('当前 Mount 未加载移液器')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认从 ${selectedJogMountLabel.value} Mount 执行 Drop Tip？请确保移液器位于安全的退 Tip 位置。`,
      'Drop Tip 确认',
      {
        type: 'warning',
        confirmButtonText: '确认 Drop Tip',
        cancelButtonText: '取消',
        closeOnClickModal: false
      }
    )
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, '无法确认 Drop Tip'))
    }
    return
  }

  activeDropTip.value = true
  try {
    await robotApi.dropJogTip(props.ip, jogSessionRunId.value, {
      pipette_id: pipette.pipette_id
    })
    ElMessage.success('Drop Tip 完成')
  } catch (error: any) {
    ElMessage.error(normalizeError(error, 'Drop Tip 失败'))
  } finally {
    activeDropTip.value = false
  }
}

async function handleGripperAction(action: GripperAction) {
  if (!props.ip || !jogSessionRunId.value) {
    ElMessage.warning('请先开始 Jog')
    return
  }
  activeGripperAction.value = action
  try {
    await robotApi.controlJogGripper(props.ip, jogSessionRunId.value, { action })
    ElMessage.success(action === 'grip' ? 'Gripper 已夹紧' : 'Gripper 已松开')
  } catch (error: any) {
    ElMessage.error(normalizeError(error, action === 'grip' ? 'Grip 失败' : 'Ungrip 失败'))
  } finally {
    activeGripperAction.value = null
  }
}

async function handleStartJog() {
  if (!props.ip || jogSessionRunId.value) return
  const ip = props.ip

  try {
    await ElMessageBox.confirm(
      '继续 Jog 前需要复位所有轴。确认后将先执行 Home 全部轴，再开始 Jog。是否继续？',
      '开始 Jog 前复位',
      {
        type: 'warning',
        confirmButtonText: '复位并开始 Jog',
        cancelButtonText: '取消',
        closeOnClickModal: false
      }
    )
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, '无法确认开始 Jog'))
    }
    return
  }

  if (props.ip !== ip) {
    ElMessage.warning('目标设备已变更，请重新开始 Jog')
    return
  }

  jogStartLoading.value = true
  try {
    await robotApi.homeRobot(ip, { target: 'robot' })
    const response = await robotApi.createJogRun(ip)
    const data = response.data.data
    const runId = data?.run_id
    if (typeof runId !== 'string' || !runId) {
      throw new Error('创建 Jog Run 后未返回 run_id')
    }
    const pipettes = data?.pipettes
    jogPipettes.value = pipettes && typeof pipettes === 'object'
      ? pipettes as Partial<Record<PipetteMount, JogPipetteInfo>>
      : {}
    jogSessionRunId.value = runId
    jogSessionIp.value = ip
    ElMessage.success('全部轴 Home 完成，Jog 已开始')
    if (typeof data?.pipette_load_warning === 'string' && data.pipette_load_warning) {
      ElMessage.warning(data.pipette_load_warning)
    }
  } catch (error: any) {
    ElMessage.error(normalizeError(error, 'Home 全部轴或开始 Jog 失败'))
  } finally {
    jogStartLoading.value = false
  }
}

async function releaseJogSession(silent = false, clearOnFailure = false) {
  const runId = jogSessionRunId.value
  const ip = jogSessionIp.value || props.ip
  if (!ip || !runId) return
  jogReleaseLoading.value = true
  try {
    await robotApi.releaseJogRun(ip, runId)
    if (jogSessionRunId.value === runId) {
      jogSessionRunId.value = ''
      jogSessionIp.value = ''
      jogPipettes.value = {}
    }
    if (!silent) ElMessage.success('Jog 已释放')
  } catch (error: any) {
    if (clearOnFailure && jogSessionRunId.value === runId) {
      jogSessionRunId.value = ''
      jogSessionIp.value = ''
      jogPipettes.value = {}
    }
    if (!silent) ElMessage.error(normalizeError(error, '释放 Jog 失败'))
  } finally {
    jogReleaseLoading.value = false
  }
}

function handleJogSessionToggle() {
  if (jogSessionRunId.value) {
    void releaseJogSession(false)
  } else {
    void handleStartJog()
  }
}

async function handleReset() {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm(
      `确认复位 ${resetAxisLabel.value}？设备对应轴将执行归零动作。`,
      '复位确认',
      {
        type: 'warning',
        confirmButtonText: '确认复位',
        cancelButtonText: '取消',
        closeOnClickModal: false
      }
    )
    actionLoading.value = 'reset'
    await robotApi.resetRobot(props.ip, { axes: [resetAxis.value] })
    ElMessage.success(`${resetAxisLabel.value} 复位完成`)
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, '复位失败'))
    }
  } finally {
    actionLoading.value = null
  }
}

async function handleReboot() {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm('确认重启设备？', '重启确认', { type: 'warning' })
    actionLoading.value = 'reboot'
    await robotApi.rebootRobot(props.ip)
    ElMessage.success('重启命令已发送')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '重启失败')
    }
  } finally {
    actionLoading.value = null
  }
}

watch(
  () => props.ip,
  (ip) => {
    if (jogSessionRunId.value && jogSessionIp.value && jogSessionIp.value !== ip) {
      void releaseJogSession(true, true)
    }
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleJogShortcut)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleJogShortcut)
  if (jogSessionRunId.value) void releaseJogSession(true, true)
})
</script>

<style scoped>
.device-control-panel {
  min-height: 240px;
  color: #1f2a37;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-console {
  max-width: 840px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 650;
  color: #1f2a37;
}

.section-subtitle {
  margin-top: 3px;
  color: #7b8797;
  font-size: 12px;
}

.control-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.reset-control {
  display: flex;
  align-items: center;
}

.reset-axis-select {
  width: 210px;
}

.reset-control :deep(.el-select__wrapper) {
  border-radius: 4px 0 0 4px;
}

.reset-control :deep(.el-button) {
  margin-left: -1px;
  border-radius: 0 4px 4px 0;
}

.jog-console {
  display: grid;
  gap: 20px;
  padding-top: 18px;
  border-top: 1px solid #eef2f7;
}

.jog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.jog-session-actions,
.jog-settings {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.jog-session-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.jog-settings {
  gap: 22px;
}

.field-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.jog-mount-field,
.jog-step-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.jog-shortcut-toggle {
  display: flex;
  align-items: center;
}

.jog-step-settings {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 22px;
}

.jog-step-settings.is-single {
  display: contents;
}

.jog-step-field :deep(.el-input-number) {
  width: 132px;
}

.jog-step-unit {
  color: #64748b;
  font-size: 12px;
}

.jog-body {
  display: flex;
  align-items: flex-start;
  gap: 26px;
}

.jog-pad {
  display: grid;
  grid-template-areas:
    ". up ."
    "left center right"
    ". down .";
  grid-template-columns: repeat(3, 76px);
  grid-template-rows: repeat(3, 58px);
  gap: 8px;
}

.jog-button {
  width: 76px;
  height: 58px;
  margin: 0;
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  font-weight: 650;
}

.jog-button :deep(.el-icon) {
  font-size: 18px;
}

.jog-up {
  grid-area: up;
}

.jog-down {
  grid-area: down;
}

.jog-left {
  grid-area: left;
}

.jog-right {
  grid-area: right;
}

.jog-center {
  grid-area: center;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
}

.jog-z-control,
.jog-plunger-control {
  display: grid;
  justify-items: center;
  gap: 8px;
}

.jog-z-group,
.jog-plunger-group {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.jog-z-center,
.jog-plunger-center {
  width: 76px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.drop-tip-button {
  min-width: 76px;
  margin: 0;
}

.jog-gripper-actions {
  display: flex;
  gap: 12px;
}

.jog-gripper-actions :deep(.el-button) {
  min-width: 76px;
  margin: 0;
}

.jog-description {
  display: grid;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.jog-shortcut-hint {
  color: #16803c;
}

.jog-run-id {
  max-width: 280px;
  overflow: hidden;
  color: #16803c;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .jog-header,
  .jog-body {
    align-items: flex-start;
    flex-direction: column;
  }

  .jog-session-actions,
  .jog-settings {
    width: 100%;
  }

  .jog-step-settings {
    width: 100%;
    overflow-x: auto;
  }

  .jog-step-settings .jog-step-field {
    flex: 0 0 auto;
  }
}
</style>
