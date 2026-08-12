<template>
  <div class="device-control-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty :description="t('devices.selectOne')" />
    </div>

    <template v-else>
      <section class="control-console">
        <div class="section-header">
          <div>
            <div class="section-title">{{ t('devices.control.title') }}</div>
            <div class="section-subtitle">{{ t('devices.control.subtitle') }}</div>
          </div>
        </div>

        <div class="control-actions">
          <el-button
            type="primary"
            :loading="actionLoading === 'home'"
            :disabled="Boolean(jogSessionRunId)"
            @click="handleHome"
          >
            {{ t('devices.control.homeAll') }}
          </el-button>
          <div class="reset-control">
            <el-select
              v-model="resetAxis"
              class="reset-axis-select"
              :placeholder="t('devices.control.resetTarget')"
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
              {{ t('devices.control.reset') }}
            </el-button>
          </div>
          <el-button type="danger" :loading="actionLoading === 'reboot'" @click="handleReboot">
            {{ t('devices.control.reboot') }}
          </el-button>
        </div>

        <div class="jog-console">
          <div class="jog-header">
            <div>
              <div class="section-title">{{ t('devices.control.jogTitle') }}</div>
              <div class="section-subtitle">{{ t('devices.control.jogSubtitle') }}</div>
            </div>
            <div class="jog-session-actions">
              <el-tag v-if="jogSessionRunId" size="small" type="success">
                {{ t('devices.control.jogStarted') }}
              </el-tag>
              <el-button
                :type="jogSessionRunId ? 'danger' : 'primary'"
                :loading="jogSessionRunId ? jogReleaseLoading : jogStartLoading"
                :disabled="jogSessionRunId
                  ? Boolean(activeJogDirection) || Boolean(activeGripperAction) || activeDropTip
                  : jogBusy || Boolean(actionLoading)"
                @click="handleJogSessionToggle"
              >
                {{ jogSessionRunId ? t('devices.control.releaseJog') : t('devices.control.startJog') }}
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
                {{ t('devices.control.enableShortcuts') }}
              </el-checkbox>
            </div>
            <div
              class="jog-step-settings"
              :class="{ 'is-single': jogMount === 'gripper' }"
            >
              <label class="jog-step-field">
                <span class="field-label">{{ t('devices.control.xyzStep') }}</span>
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
                <span class="field-label">{{ t('devices.control.plungerStep') }}</span>
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
            <div class="jog-pad" :aria-label="t('devices.control.jogPad')">
              <el-button
                class="jog-button jog-up"
                :loading="activeJogDirection === 'up'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'up')"
                :aria-label="t('devices.control.aria.yPositive')"
                @click="handleJog('up')"
              >
                <el-icon><ArrowUp /></el-icon>
                <span>Y+</span>
              </el-button>
              <el-button
                class="jog-button jog-left"
                :loading="activeJogDirection === 'left'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'left')"
                :aria-label="t('devices.control.aria.xNegative')"
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
                :aria-label="t('devices.control.aria.xPositive')"
                @click="handleJog('right')"
              >
                <el-icon><ArrowRight /></el-icon>
                <span>X+</span>
              </el-button>
              <el-button
                class="jog-button jog-down"
                :loading="activeJogDirection === 'down'"
                :disabled="!jogSessionRunId || (jogBusy && activeJogDirection !== 'down')"
                :aria-label="t('devices.control.aria.yNegative')"
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
                  :aria-label="t('devices.control.aria.zPositive')"
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
                  :aria-label="t('devices.control.aria.zNegative')"
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
                  :aria-label="t('devices.control.aria.plungerPositive')"
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
                  :aria-label="t('devices.control.aria.plungerNegative')"
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
              <span>{{ t('devices.control.xyzMove', { step: jogStep.toFixed(1) }) }}</span>
              <span>{{ t('devices.control.xyDirections') }}</span>
              <span>Z±：{{ jogZAxis }}</span>
              <span v-if="jogMount === 'gripper'">{{ t('devices.control.gripperActions') }}</span>
              <span v-else>{{ t('devices.control.plungerMove', { axis: jogPlungerAxis, step: jogPlungerStep.toFixed(1) }) }}</span>
              <span v-if="jogMount !== 'gripper' && selectedJogPipette">
                {{ t('devices.control.currentPipette', { name: selectedJogPipette.name }) }}
              </span>
              <span v-else-if="jogMount !== 'gripper'">{{ t('devices.control.noPipette') }}</span>
              <span v-if="jogShortcutEnabled" class="jog-shortcut-hint">
                {{ t('devices.control.shortcutHint', { action: jogMount === 'gripper' ? 'Grip/Ungrip' : 'Plunger±' }) }}
              </span>
              <span v-if="jogSessionRunId" class="jog-run-id">{{ t('devices.control.runId', { id: jogSessionRunId }) }}</span>
              <span v-else>{{ t('devices.control.startHint') }}</span>
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
import { useI18n } from 'vue-i18n'
import { robotApi } from '@/scripts/api'

const { t } = useI18n()

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
const jogDirectionLabels = computed<Record<JogDirection, string>>(() => ({
  up: t('devices.control.directions.up'),
  down: t('devices.control.directions.down'),
  left: t('devices.control.directions.left'),
  right: t('devices.control.directions.right'),
  z_up: t('devices.control.directions.zUp'),
  z_down: t('devices.control.directions.zDown'),
  plunger_up: t('devices.control.directions.plungerUp'),
  plunger_down: t('devices.control.directions.plungerDown')
}))
const resetAxisGroups = computed(() => [
  {
    label: t('devices.control.axisGroups.gantry'),
    options: [
      { value: 'x', label: t('devices.control.axes.x') },
      { value: 'y', label: t('devices.control.axes.y') }
    ]
  },
  {
    label: 'Mount',
    options: [
      { value: 'leftZ', label: t('devices.control.axes.leftZ') },
      { value: 'rightZ', label: t('devices.control.axes.rightZ') }
    ]
  },
  {
    label: 'Pipette Plunger',
    options: [
      { value: 'leftPlunger', label: t('devices.control.axes.leftPlunger') },
      { value: 'rightPlunger', label: t('devices.control.axes.rightPlunger') }
    ]
  },
  {
    label: t('devices.control.axisGroups.extension'),
    options: [
      { value: 'extensionZ', label: 'Gripper Extension Z' },
      { value: 'extensionJaw', label: 'Gripper Jaw' },
      { value: 'axis96ChannelCam', label: '96 Channel Cam' }
    ]
  }
])

const resetAxisLabel = computed(() => {
  for (const group of resetAxisGroups.value) {
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
    ElMessage.success(t('devices.control.homeSent'))
  } catch (error: any) {
    ElMessage.error(error.message || t('devices.control.homeFailed'))
  } finally {
    actionLoading.value = null
  }
}

async function handleJog(direction: JogDirection) {
  if (!props.ip || !jogSessionRunId.value) {
    ElMessage.warning(t('devices.control.startJogFirst'))
    return
  }
  const isPlungerMove = direction === 'plunger_up' || direction === 'plunger_down'
  if (isPlungerMove && !selectedJogPipette.value) {
    ElMessage.warning(t('devices.control.noPipette'))
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
    ElMessage.success(t('devices.control.moveCompleted', { direction: jogDirectionLabels.value[direction], step: step.toFixed(1) }))
  } catch (error: any) {
    ElMessage.error(normalizeError(error, t('devices.control.moveFailed')))
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
    ElMessage.warning(t('devices.control.startJogFirst'))
    return
  }
  if (!pipette) {
    ElMessage.warning(t('devices.control.noPipette'))
    return
  }

  try {
    await ElMessageBox.confirm(
      t('devices.control.dropTipConfirm', { mount: selectedJogMountLabel.value }),
      t('devices.control.dropTipTitle'),
      {
        type: 'warning',
        confirmButtonText: t('devices.control.confirmDropTip'),
        cancelButtonText: t('common.actions.cancel'),
        closeOnClickModal: false
      }
    )
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, t('devices.control.dropTipConfirmFailed')))
    }
    return
  }

  activeDropTip.value = true
  try {
    await robotApi.dropJogTip(props.ip, jogSessionRunId.value, {
      pipette_id: pipette.pipette_id
    })
    ElMessage.success(t('devices.control.dropTipCompleted'))
  } catch (error: any) {
    ElMessage.error(normalizeError(error, t('devices.control.dropTipFailed')))
  } finally {
    activeDropTip.value = false
  }
}

async function handleGripperAction(action: GripperAction) {
  if (!props.ip || !jogSessionRunId.value) {
    ElMessage.warning(t('devices.control.startJogFirst'))
    return
  }
  activeGripperAction.value = action
  try {
    await robotApi.controlJogGripper(props.ip, jogSessionRunId.value, { action })
    ElMessage.success(t(action === 'grip' ? 'devices.control.gripped' : 'devices.control.ungripped'))
  } catch (error: any) {
    ElMessage.error(normalizeError(error, t(action === 'grip' ? 'devices.control.gripFailed' : 'devices.control.ungripFailed')))
  } finally {
    activeGripperAction.value = null
  }
}

async function handleStartJog() {
  if (!props.ip || jogSessionRunId.value) return
  const ip = props.ip

  try {
    await ElMessageBox.confirm(
      t('devices.control.startConfirm'),
      t('devices.control.startConfirmTitle'),
      {
        type: 'warning',
        confirmButtonText: t('devices.control.homeAndStart'),
        cancelButtonText: t('common.actions.cancel'),
        closeOnClickModal: false
      }
    )
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, t('devices.control.startConfirmFailed')))
    }
    return
  }

  if (props.ip !== ip) {
    ElMessage.warning(t('devices.control.targetChanged'))
    return
  }

  jogStartLoading.value = true
  try {
    await robotApi.homeRobot(ip, { target: 'robot' })
    const response = await robotApi.createJogRun(ip)
    const data = response.data.data
    const runId = data?.run_id
    if (typeof runId !== 'string' || !runId) {
      throw new Error(t('devices.control.missingRunId'))
    }
    const pipettes = data?.pipettes
    jogPipettes.value = pipettes && typeof pipettes === 'object'
      ? pipettes as Partial<Record<PipetteMount, JogPipetteInfo>>
      : {}
    jogSessionRunId.value = runId
    jogSessionIp.value = ip
    ElMessage.success(t('devices.control.homeAndStarted'))
    if (typeof data?.pipette_load_warning === 'string' && data.pipette_load_warning) {
      ElMessage.warning(data.pipette_load_warning)
    }
  } catch (error: any) {
    ElMessage.error(normalizeError(error, t('devices.control.homeOrStartFailed')))
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
    if (!silent) ElMessage.success(t('devices.control.released'))
  } catch (error: any) {
    if (clearOnFailure && jogSessionRunId.value === runId) {
      jogSessionRunId.value = ''
      jogSessionIp.value = ''
      jogPipettes.value = {}
    }
    if (!silent) ElMessage.error(normalizeError(error, t('devices.control.releaseFailed')))
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
      t('devices.control.resetConfirm', { axis: resetAxisLabel.value }),
      t('devices.control.resetTitle'),
      {
        type: 'warning',
        confirmButtonText: t('devices.control.confirmReset'),
        cancelButtonText: t('common.actions.cancel'),
        closeOnClickModal: false
      }
    )
    actionLoading.value = 'reset'
    await robotApi.resetRobot(props.ip, { axes: [resetAxis.value] })
    ElMessage.success(t('devices.control.resetCompleted', { axis: resetAxisLabel.value }))
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(normalizeError(error, t('devices.control.resetFailed')))
    }
  } finally {
    actionLoading.value = null
  }
}

async function handleReboot() {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm(t('devices.control.rebootConfirm'), t('devices.control.rebootTitle'), { type: 'warning' })
    actionLoading.value = 'reboot'
    await robotApi.rebootRobot(props.ip)
    ElMessage.success(t('devices.control.rebootSent'))
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || t('devices.control.rebootFailed'))
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
