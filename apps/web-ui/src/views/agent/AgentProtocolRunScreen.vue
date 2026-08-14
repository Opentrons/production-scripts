<template>
  <div class="run-shell" :class="{ 'is-expanded': expanded }">
    <!-- Running -->
    <div v-if="phase === 'running'" class="run-running">
      <div class="run-meter" aria-hidden="true">
        <i :style="{ width: `${progressPercent}%` }" />
      </div>
      <header class="run-running-header">
        <div>
          <strong>{{ statusLabel }}</strong>
          <p>{{ protocolName }}</p>
        </div>
        <div class="run-running-meta">
          <strong>{{ formattedTimer }}</strong>
          <span>{{ t('agent.protocol.runStep', { current: Math.min(stepIndex + 1, totalSteps), total: totalSteps }) }}</span>
        </div>
      </header>

      <div class="run-controls">
        <button type="button" class="run-round is-stop" :title="t('agent.protocol.runStop')" @click="stopRun">
          <X :size="expanded ? 22 : 14" />
        </button>
        <button
          type="button"
          class="run-round is-play"
          :title="paused ? t('agent.protocol.runResume') : t('agent.protocol.runPause')"
          @click="togglePause"
        >
          <Play v-if="paused" :size="expanded ? 22 : 14" fill="currentColor" />
          <Pause v-else :size="expanded ? 22 : 14" fill="currentColor" />
        </button>
      </div>

      <div class="run-command-pill">
        {{ currentCommandText }}
      </div>
    </div>

    <!-- Splash -->
    <button
      v-else-if="phase === 'splash'"
      type="button"
      class="run-splash"
      :class="outcome === 'succeeded' ? 'is-success' : 'is-fail'"
      @click="phase = 'summary'"
    >
      <CircleCheck v-if="outcome === 'succeeded'" :size="expanded ? 48 : 28" />
      <CircleAlert v-else :size="expanded ? 48 : 28" />
      <strong>{{ splashTitle }}</strong>
      <span>{{ protocolName }}</span>
      <small>{{ t('agent.protocol.runTapContinue') }}</small>
    </button>

    <!-- Summary -->
    <div v-else class="run-summary">
      <header class="run-summary-header">
        <CircleCheck v-if="outcome === 'succeeded'" class="is-success" :size="expanded ? 28 : 18" />
        <CircleAlert v-else class="is-fail" :size="expanded ? 28 : 18" />
        <div>
          <strong>{{ splashTitle }}</strong>
          <p>{{ protocolName }}</p>
        </div>
      </header>

      <div class="run-chips">
        <span>{{ t('agent.protocol.runChipStatus', { status: statusLabel }) }}</span>
        <span>{{ t('agent.protocol.runChipDuration', { time: formattedTimer }) }}</span>
        <span>{{ t('agent.protocol.runChipSteps', { count: completedSteps }) }}</span>
      </div>

      <div v-if="outcome !== 'succeeded' && errorDetail" class="run-error" role="alert">
        <strong>{{ t('agent.protocol.errors') }}</strong>
        <p>{{ errorDetail }}</p>
      </div>

      <footer class="run-summary-actions">
        <button type="button" class="run-btn is-secondary" @click="$emit('dashboard')">
          {{ t('agent.protocol.runReturn') }}
        </button>
        <button type="button" class="run-btn is-primary" @click="restart">
          {{ t('agent.protocol.runAgain') }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleAlert, CircleCheck, Pause, Play, X } from '@lucide/vue'

type RunOutcome = 'succeeded' | 'failed' | 'stopped'
type RunPhase = 'running' | 'splash' | 'summary'

const props = defineProps<{
  protocolName: string
  commands: Array<Record<string, unknown>>
  analysisOk: boolean
  errorDetail?: string
  expanded?: boolean
}>()

defineEmits<{
  dashboard: []
}>()

const { t } = useI18n()

const phase = ref<RunPhase>('running')
const outcome = ref<RunOutcome>(props.analysisOk ? 'succeeded' : 'failed')
const stepIndex = ref(0)
const paused = ref(false)
const elapsedMs = ref(0)
const completedSteps = ref(0)

let stepTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const totalSteps = computed(() => Math.max(props.commands.length, 1))

const progressPercent = computed(() => {
  if (phase.value !== 'running') return 100
  return Math.min(100, Math.round(((stepIndex.value + 1) / totalSteps.value) * 100))
})

const formattedTimer = computed(() => {
  const totalSeconds = Math.floor(elapsedMs.value / 1000)
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
})

const statusLabel = computed(() => {
  if (phase.value === 'running') {
    return paused.value ? t('agent.protocol.runStatusPaused') : t('agent.protocol.runStatusRunning')
  }
  if (outcome.value === 'succeeded') return t('agent.protocol.runStatusSucceeded')
  if (outcome.value === 'stopped') return t('agent.protocol.runStatusStopped')
  return t('agent.protocol.runStatusFailed')
})

const splashTitle = computed(() => {
  if (outcome.value === 'succeeded') return t('agent.protocol.runCompletedSplash')
  if (outcome.value === 'stopped') return t('agent.protocol.runCanceledSplash')
  return t('agent.protocol.runFailedSplash')
})

const currentCommandText = computed(() => {
  const command = props.commands[stepIndex.value]
  if (!command) return t('agent.protocol.runWaiting')
  return formatCommand(command)
})

function formatCommand(command: Record<string, unknown>): string {
  const type = String(command.commandType || 'command')
  const params = (command.params || {}) as Record<string, unknown>
  const location = params.location as Record<string, unknown> | undefined
  const slot = location?.slotName || location?.addressableAreaName
  if (type === 'loadLabware') return `Load ${params.loadName || 'labware'}${slot ? ` → ${slot}` : ''}`
  if (type === 'loadPipette') return `Load pipette ${params.pipetteName || ''}`.trim()
  if (type === 'loadModule') return `Load module ${params.model || params.moduleType || ''}`.trim()
  if (type === 'pickUpTip') return 'Pick up tip'
  if (type === 'dropTip' || type === 'dropTipInPlace') return 'Drop tip'
  if (type === 'aspirate') return `Aspirate ${params.volume ?? ''} µL`.trim()
  if (type === 'dispense') return `Dispense ${params.volume ?? ''} µL`.trim()
  if (type === 'moveToWell' || type === 'moveToAddressableArea') return `Move to ${slot || params.wellName || 'position'}`
  if (type === 'home') return 'Home'
  if (type === 'waitForDuration') return `Wait ${params.seconds ?? ''}s`.trim()
  return type.replace(/([a-z])([A-Z])/g, '$1 $2')
}

function clearTimers() {
  if (stepTimer) clearInterval(stepTimer)
  if (clockTimer) clearInterval(clockTimer)
  stepTimer = null
  clockTimer = null
}

function finish(next: RunOutcome) {
  clearTimers()
  outcome.value = next
  completedSteps.value = Math.min(stepIndex.value + 1, totalSteps.value)
  phase.value = next === 'stopped' ? 'summary' : 'splash'
}

function advanceStep() {
  if (paused.value || phase.value !== 'running') return
  const command = props.commands[stepIndex.value]
  if (command && String(command.status || '') === 'failed') {
    finish('failed')
    return
  }
  if (stepIndex.value >= totalSteps.value - 1) {
    finish(props.analysisOk ? 'succeeded' : 'failed')
    return
  }
  stepIndex.value += 1
}

function stepIntervalMs() {
  const n = totalSteps.value
  // Keep the whole sim roughly 8–20s regardless of command count.
  if (n <= 1) return 1200
  if (n <= 12) return 900
  if (n <= 40) return 450
  if (n <= 120) return 220
  return Math.max(80, Math.floor(16000 / n))
}

function startTimers() {
  clearTimers()
  clockTimer = setInterval(() => {
    if (!paused.value && phase.value === 'running') elapsedMs.value += 250
  }, 250)
  stepTimer = setInterval(advanceStep, stepIntervalMs())
}

function togglePause() {
  if (phase.value !== 'running') return
  paused.value = !paused.value
}

function stopRun() {
  if (phase.value !== 'running') return
  finish('stopped')
}

function restart() {
  phase.value = 'running'
  outcome.value = props.analysisOk ? 'succeeded' : 'failed'
  stepIndex.value = 0
  paused.value = false
  elapsedMs.value = 0
  completedSteps.value = 0
  startTimers()
}

watch(
  () => [props.commands, props.analysisOk] as const,
  () => restart(),
)

onMounted(() => {
  startTimers()
})

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<style scoped>
.run-shell {
  --odd-black: #16212d;
  --odd-grey60: #4a4c4e;
  --odd-grey50: #737578;
  --odd-grey35: #cbcccc;
  --odd-grey20: #e9e9e9;
  --odd-grey10: #f3f3f3;
  --odd-blue50: #006cfa;
  --odd-blue35: #bfdcfd;
  --odd-green50: #04aa65;
  --odd-red50: #de1b1b;
  --odd-red20: #fce9e9;
  --odd-white: #ffffff;

  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--odd-white);
  color: var(--odd-black);
  font-size: 10.5px;
  line-height: 1.25;
}

.run-shell.is-expanded {
  font-size: 14px;
  line-height: 1.35;
}

.run-running {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 0 6px;
}

.run-meter {
  height: 4px;
  background: var(--odd-grey20);
}

.run-shell.is-expanded .run-meter {
  height: 6px;
}

.run-meter i {
  display: block;
  height: 100%;
  background: var(--odd-blue50);
  transition: width 280ms ease;
}

.run-running-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px 0;
}

.run-running-header strong,
.run-running-meta strong {
  display: block;
  font-size: 1.05em;
  font-weight: 650;
}

.run-running-header p,
.run-running-meta span {
  margin: 1px 0 0;
  color: var(--odd-grey50);
  font-size: 0.9em;
}

.run-running-meta {
  text-align: right;
}

.run-controls {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.run-round {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 50%;
  color: #fff;
  display: grid;
  place-items: center;
  cursor: pointer;
}

.run-shell.is-expanded .run-round {
  width: 72px;
  height: 72px;
}

.run-round.is-stop {
  background: var(--odd-red50);
}

.run-round.is-play {
  background: var(--odd-blue50);
}

.run-command-pill {
  margin: 0 8px;
  padding: 7px 10px;
  border-radius: 10px;
  background: var(--odd-blue35);
  color: var(--odd-black);
  text-align: center;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-shell.is-expanded .run-command-pill {
  border-radius: 16px;
  padding: 12px 16px;
}

.run-splash {
  flex: 1;
  border: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #fff;
  cursor: pointer;
  padding: 14px;
  text-align: center;
}

.run-splash.is-success {
  background: var(--odd-green50);
}

.run-splash.is-fail {
  background: var(--odd-red50);
}

.run-splash strong {
  font-size: 1.3em;
  font-weight: 650;
}

.run-splash small {
  opacity: 0.9;
  font-size: 0.9em;
}

.run-summary {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}

.run-shell.is-expanded .run-summary {
  gap: 12px;
  padding: 14px 16px;
}

.run-summary-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.run-summary-header .is-success {
  color: var(--odd-green50);
}

.run-summary-header .is-fail {
  color: var(--odd-red50);
}

.run-summary-header strong {
  font-weight: 650;
}

.run-summary-header p {
  margin: 1px 0 0;
  color: var(--odd-grey50);
}

.run-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.run-chips span {
  background: var(--odd-grey20);
  border-radius: 999px;
  padding: 3px 7px;
  color: var(--odd-grey60);
  font-size: 0.88em;
  font-weight: 600;
}

.run-error {
  background: var(--odd-red20);
  color: var(--odd-red50);
  border-radius: 8px;
  padding: 7px 8px;
  overflow: auto;
  max-height: 36%;
}

.run-error p {
  margin: 4px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.run-summary-actions {
  margin-top: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.run-btn {
  border: 0;
  border-radius: 10px;
  padding: 8px;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
}

.run-shell.is-expanded .run-btn {
  border-radius: 14px;
  padding: 12px;
}

.run-btn.is-secondary {
  background: var(--odd-grey35);
  color: var(--odd-black);
}

.run-btn.is-primary {
  background: var(--odd-blue50);
  color: #fff;
}
</style>
