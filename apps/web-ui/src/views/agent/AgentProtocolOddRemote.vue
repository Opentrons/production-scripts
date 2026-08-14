<template>
  <div
    class="odd-remote"
    :class="{ 'is-expanded': expanded, 'is-live': Boolean(frameUrl) }"
  >
    <div class="odd-remote-layout">
      <div
        ref="stageRef"
        class="odd-remote-stage"
        tabindex="0"
        role="application"
        :aria-label="t('agent.protocol.oddInteractiveAria')"
        @pointerdown="onPointerDown"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @wheel.prevent="onWheel"
        @contextmenu.prevent
      >
        <img
          v-if="frameUrl"
          class="odd-remote-frame"
          :src="frameUrl"
          alt="Remote Flex ODD"
          draggable="false"
        >
        <div v-else class="odd-remote-placeholder">
          <LoaderCircle v-if="loading" class="odd-spin" :size="expanded ? 36 : 22" />
          <strong>{{ loading ? t('agent.protocol.oddConnecting') : t('agent.protocol.oddWaiting') }}</strong>
          <span>{{ deviceLabel }}</span>
          <small v-if="error">{{ error }}</small>
        </div>
      </div>

      <div
        class="odd-rail odd-rail-v"
        role="slider"
        :aria-label="t('agent.protocol.oddRailVertical')"
        :aria-orientation="'vertical'"
        @pointerdown.stop="onRailDown($event, 'v')"
        @pointermove.stop="onRailMove($event, 'v')"
        @pointerup.stop="onRailUp"
        @pointercancel.stop="onRailUp"
      >
        <button type="button" class="odd-rail-nudge" tabindex="-1" @click.stop="nudge('v', -1)">▲</button>
        <div class="odd-rail-track">
          <i class="odd-rail-thumb" :style="vThumbStyle" />
        </div>
        <button type="button" class="odd-rail-nudge" tabindex="-1" @click.stop="nudge('v', 1)">▼</button>
      </div>

      <div
        class="odd-rail odd-rail-h"
        role="slider"
        :aria-label="t('agent.protocol.oddRailHorizontal')"
        :aria-orientation="'horizontal'"
        @pointerdown.stop="onRailDown($event, 'h')"
        @pointermove.stop="onRailMove($event, 'h')"
        @pointerup.stop="onRailUp"
        @pointercancel.stop="onRailUp"
      >
        <button type="button" class="odd-rail-nudge" tabindex="-1" @click.stop="nudge('h', -1)">◀</button>
        <div class="odd-rail-track">
          <i class="odd-rail-thumb" :style="hThumbStyle" />
        </div>
        <button type="button" class="odd-rail-nudge" tabindex="-1" @click.stop="nudge('h', 1)">▶</button>
      </div>

      <div class="odd-rail-corner" aria-hidden="true" />
    </div>

    <div class="odd-remote-badge">
      <span class="odd-remote-dot" :class="{ 'is-live': Boolean(frameUrl) && !error }" />
      <span>{{ deviceLabel }}</span>
      <span class="odd-remote-port">:{{ port }}</span>
      <span class="odd-remote-hint">{{ liveHint }}</span>
    </div>

    <button
      type="button"
      class="odd-zoom-btn odd-remote-zoom"
      :title="expanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
      @pointerdown.stop
      @click.stop="$emit('toggle-expand')"
    >
      <Minimize2 v-if="expanded" :size="expanded ? 16 : 12" />
      <Maximize2 v-else :size="12" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { LoaderCircle, Maximize2, Minimize2 } from '@lucide/vue'
import { agentProtocolAnalysisApi } from '@/scripts/modules/agent/agentWorkspaceApi'

const props = defineProps<{
  ip: string
  port?: number
  name?: string
  expanded?: boolean
  intervalMs?: number
}>()

defineEmits<{
  'toggle-expand': []
  error: [message: string]
}>()

const { t } = useI18n()

const stageRef = ref<HTMLElement | null>(null)
const loading = ref(true)
const error = ref('')
const frameUrl = ref('')
const viewport = ref({ width: 1024, height: 600 })
const streamMode = ref<'ws' | 'http' | 'none'>('none')
const vThumb = ref(50)
const hThumb = ref(50)

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let httpTimer: ReturnType<typeof setTimeout> | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
let disposed = false
let httpInFlight = false
let pressing = false
let downPoint: { x: number; y: number } | null = null
let reconnectAttempt = 0
let lastBlobUrl = ''

type RailAxis = 'v' | 'h'
let railAxis: RailAxis | null = null
let railLastPos = 0
let railPending = 0
let railPointerId: number | null = null

const port = computed(() => props.port || 9223)
const deviceLabel = computed(() => props.name || props.ip)
const streamQuality = computed(() => (props.expanded ? 52 : 40))
const pollMs = computed(() => {
  if (props.intervalMs) return props.intervalMs
  return props.expanded ? 550 : 850
})
const vThumbStyle = computed(() => ({ top: `${vThumb.value}%` }))
const hThumbStyle = computed(() => ({ left: `${hThumb.value}%` }))
const liveHint = computed(() => {
  if (frameUrl.value && streamMode.value !== 'none') return 'live'
  if (streamMode.value === 'ws') return t('agent.protocol.oddConnecting')
  return t('agent.protocol.oddClickHint')
})

const SWIPE_FLUSH_PX = 18
const SWIPE_SCALE = 2.4
const NUDGE_PX = 140

function clearReconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function clearHttpPoll() {
  if (httpTimer) {
    clearTimeout(httpTimer)
    httpTimer = null
  }
}

function clearPing() {
  if (pingTimer) {
    clearInterval(pingTimer)
    pingTimer = null
  }
}

function closeSocket() {
  clearPing()
  if (socket) {
    socket.onopen = null
    socket.onmessage = null
    socket.onerror = null
    socket.onclose = null
    try {
      socket.close()
    } catch {
      // ignore
    }
    socket = null
  }
}

function revokeFrame() {
  if (lastBlobUrl) {
    URL.revokeObjectURL(lastBlobUrl)
    lastBlobUrl = ''
  }
  frameUrl.value = ''
}

function applyJpegBytes(bytes: ArrayBuffer | Uint8Array, width?: number, height?: number) {
  if (width && height && width > 0 && height > 0) {
    viewport.value = { width, height }
  }
  const blob = new Blob([bytes], { type: 'image/jpeg' })
  const next = URL.createObjectURL(blob)
  const prev = lastBlobUrl
  lastBlobUrl = next
  frameUrl.value = next
  if (prev) URL.revokeObjectURL(prev)
}

function applyJpegBase64(b64: string) {
  try {
    const binary = atob(b64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
    applyJpegBytes(bytes)
  } catch {
    frameUrl.value = `data:image/jpeg;base64,${b64}`
  }
}

function mapPoint(event: PointerEvent | WheelEvent) {
  const el = stageRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const ratioX = (event.clientX - rect.left) / rect.width
  const ratioY = (event.clientY - rect.top) / rect.height
  const x = Math.max(0, Math.min(1, ratioX)) * viewport.value.width
  const y = Math.max(0, Math.min(1, ratioY)) * viewport.value.height
  return { x, y }
}

function swipeOrigin() {
  return {
    x: viewport.value.width * 0.5,
    y: viewport.value.height * 0.52,
  }
}

function sendInput(partial: {
  type: string
  x: number
  y: number
  button?: string
  clickCount?: number
  deltaX?: number
  deltaY?: number
  steps?: number
}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({
      type: 'input',
      eventType: partial.type,
      x: partial.x,
      y: partial.y,
      button: partial.button || 'left',
      clickCount: partial.clickCount || 1,
      deltaX: partial.deltaX || 0,
      deltaY: partial.deltaY || 0,
      steps: partial.steps || 8,
    }))
    return
  }
  void agentProtocolAnalysisApi.oddInput({
    ip: props.ip,
    port: port.value,
    ...partial,
  }).then((result) => {
    if (result.width && result.height) {
      viewport.value = { width: result.width, height: result.height }
    }
    error.value = ''
  }).catch((err) => {
    error.value = err instanceof Error ? err.message : t('agent.protocol.oddInputFailed')
  })
}

function sendSwipe(deltaX: number, deltaY: number) {
  if (!deltaX && !deltaY) return
  const origin = swipeOrigin()
  // Clamp so the finger stays on-screen.
  const maxX = Math.min(Math.abs(deltaX), origin.x - 8, viewport.value.width - origin.x - 8)
  const maxY = Math.min(Math.abs(deltaY), origin.y - 8, viewport.value.height - origin.y - 8)
  const dx = Math.sign(deltaX) * maxX
  const dy = Math.sign(deltaY) * maxY
  if (!dx && !dy) return
  const distance = Math.hypot(dx, dy)
  const steps = Math.max(4, Math.min(12, Math.round(distance / 28)))
  sendInput({
    type: 'swipe',
    x: origin.x,
    y: origin.y,
    deltaX: dx,
    deltaY: dy,
    steps,
  })
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  const point = mapPoint(event)
  if (!point) return
  pressing = true
  downPoint = point
  stageRef.value?.setPointerCapture(event.pointerId)
  stageRef.value?.focus()
}

function onPointerUp(event: PointerEvent) {
  if (!pressing) return
  pressing = false
  try {
    stageRef.value?.releasePointerCapture(event.pointerId)
  } catch {
    // ignore
  }
  const point = mapPoint(event) || downPoint
  downPoint = null
  if (!point) return
  // Screen is tap-only; use rails for scrolling to avoid laggy drag streams.
  sendInput({ type: 'click', x: point.x, y: point.y, button: 'left', clickCount: 1 })
}

function onWheel(event: WheelEvent) {
  const point = mapPoint(event) || swipeOrigin()
  sendInput({
    type: 'wheel',
    x: point.x,
    y: point.y,
    deltaX: event.deltaX,
    deltaY: event.deltaY,
  })
}

function onRailDown(event: PointerEvent, axis: RailAxis) {
  if (event.button !== 0) return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  railAxis = axis
  railPointerId = event.pointerId
  railPending = 0
  railLastPos = axis === 'v' ? event.clientY : event.clientX
}

function onRailMove(event: PointerEvent, axis: RailAxis) {
  if (railAxis !== axis || railPointerId !== event.pointerId) return
  const pos = axis === 'v' ? event.clientY : event.clientX
  const delta = pos - railLastPos
  railLastPos = pos
  railPending += delta

  if (axis === 'v') {
    vThumb.value = Math.max(8, Math.min(92, vThumb.value + delta * 0.35))
  } else {
    hThumb.value = Math.max(8, Math.min(92, hThumb.value + delta * 0.35))
  }

  if (Math.abs(railPending) < SWIPE_FLUSH_PX) return
  const amount = railPending * SWIPE_SCALE
  railPending = 0
  if (axis === 'v') sendSwipe(0, amount)
  else sendSwipe(amount, 0)
}

function onRailUp(event: PointerEvent) {
  if (railPointerId !== null && event.pointerId !== railPointerId) return
  if (railAxis && Math.abs(railPending) >= 8) {
    const amount = railPending * SWIPE_SCALE
    if (railAxis === 'v') sendSwipe(0, amount)
    else sendSwipe(amount, 0)
  }
  railAxis = null
  railPointerId = null
  railPending = 0
  // Ease thumb back toward center after scrub.
  vThumb.value = 50
  hThumb.value = 50
}

function nudge(axis: RailAxis, direction: -1 | 1) {
  if (axis === 'v') {
    vThumb.value = direction < 0 ? 28 : 72
    sendSwipe(0, direction * NUDGE_PX)
    window.setTimeout(() => { vThumb.value = 50 }, 180)
  } else {
    hThumb.value = direction < 0 ? 28 : 72
    sendSwipe(direction * NUDGE_PX, 0)
    window.setTimeout(() => { hThumb.value = 50 }, 180)
  }
}

function scheduleHttpPull(delay = pollMs.value) {
  clearHttpPoll()
  if (streamMode.value === 'ws') return
  httpTimer = setTimeout(() => {
    void pullHttpFrame()
  }, delay)
}

function isWebSocketStreamActive(): boolean {
  return streamMode.value === 'ws'
}

async function pullHttpFrame() {
  if (disposed || httpInFlight || !props.ip || isWebSocketStreamActive()) return
  httpInFlight = true
  try {
    const blob = await agentProtocolAnalysisApi.fetchOddScreenshot(
      props.ip,
      port.value,
      streamQuality.value,
    )
    if (disposed || isWebSocketStreamActive()) return
    const next = URL.createObjectURL(blob)
    const prev = lastBlobUrl
    lastBlobUrl = next
    frameUrl.value = next
    if (prev) URL.revokeObjectURL(prev)
    error.value = ''
    loading.value = false
    streamMode.value = 'http'
  } catch (err) {
    if (disposed) return
    error.value = err instanceof Error ? err.message : t('agent.protocol.oddCaptureFailed')
    loading.value = false
  } finally {
    httpInFlight = false
    if (!disposed && !isWebSocketStreamActive()) scheduleHttpPull()
  }
}

function scheduleReconnect() {
  clearReconnect()
  if (disposed) return
  const delay = Math.min(8000, 400 + reconnectAttempt * 600)
  reconnectAttempt += 1
  if (reconnectAttempt >= 3) scheduleHttpPull(80)
  reconnectTimer = setTimeout(() => {
    void connectStream()
  }, delay)
}

function connectStream() {
  if (disposed || !props.ip) return
  clearReconnect()
  closeSocket()
  loading.value = !frameUrl.value
  const url = agentProtocolAnalysisApi.oddStreamUrl(props.ip, port.value, streamQuality.value)
  const ws = new WebSocket(url)
  socket = ws

  ws.binaryType = 'arraybuffer'
  ws.onopen = () => {
    reconnectAttempt = 0
    streamMode.value = 'ws'
    clearHttpPoll()
    clearPing()
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
    }, 15000)
  }

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      const buf = new Uint8Array(event.data)
      if (buf.length > 8 && buf[0] === 0x4f && buf[1] === 0x4a && buf[2] === 0x50 && buf[3] === 0x47) {
        const width = (buf[4] << 8) | buf[5]
        const height = (buf[6] << 8) | buf[7]
        applyJpegBytes(buf.subarray(8), width, height)
        error.value = ''
        loading.value = false
        streamMode.value = 'ws'
        clearHttpPoll()
      }
      return
    }
    let payload: Record<string, unknown>
    try {
      payload = JSON.parse(String(event.data)) as Record<string, unknown>
    } catch {
      return
    }
    const type = String(payload.type || '')
    if (type === 'ready') {
      const width = Number(payload.width || 0)
      const height = Number(payload.height || 0)
      if (width > 0 && height > 0) viewport.value = { width, height }
      error.value = ''
      // Keep loading until the first JPEG frame — "ready" only means CDP is up.
      loading.value = !frameUrl.value
      streamMode.value = 'ws'
      clearHttpPoll()
      return
    }
    if (type === 'frame') {
      const data = String(payload.data || '')
      if (!data) return
      const width = Number(payload.width || 0)
      const height = Number(payload.height || 0)
      if (width > 0 && height > 0) viewport.value = { width, height }
      applyJpegBase64(data)
      error.value = ''
      loading.value = false
      streamMode.value = 'ws'
      clearHttpPoll()
      return
    }
    if (type === 'input_ok') {
      const width = Number(payload.width || 0)
      const height = Number(payload.height || 0)
      if (width > 0 && height > 0) viewport.value = { width, height }
      return
    }
    if (type === 'input_error' || type === 'error') {
      error.value = String(payload.message || t('agent.protocol.oddCaptureFailed'))
    }
  }

  ws.onerror = () => {
    // onclose handles reconnect / fallback
  }

  ws.onclose = () => {
    clearPing()
    if (socket === ws) socket = null
    if (disposed) return
    if (streamMode.value === 'ws') streamMode.value = 'none'
    scheduleReconnect()
  }
}

function restart() {
  clearReconnect()
  clearHttpPoll()
  closeSocket()
  reconnectAttempt = 0
  streamMode.value = 'none'
  loading.value = true
  error.value = ''
  connectStream()
}

watch(
  () => [props.ip, props.port, props.expanded] as const,
  () => {
    restart()
  },
)

onMounted(() => {
  restart()
})

onBeforeUnmount(() => {
  disposed = true
  clearReconnect()
  clearHttpPoll()
  closeSocket()
  revokeFrame()
})
</script>

<style scoped>
.odd-remote {
  --odd-rail-size: 26px;
  --odd-rail-gap: 6px;
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex: 1 1 auto;
  align-self: stretch;
  background: #111;
  overflow: visible;
  border-radius: inherit;
}

.odd-remote.is-expanded {
  --odd-rail-size: 32px;
  --odd-rail-gap: 8px;
}

.odd-remote-layout {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow: visible;
}

.odd-remote-stage {
  position: absolute;
  inset: 0;
  z-index: 1;
  min-width: 0;
  min-height: 0;
  border-radius: inherit;
  overflow: hidden;
  background: #111;
  cursor: pointer;
  touch-action: none;
  outline: none;
  user-select: none;
}

.odd-remote-frame {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: fill;
  object-position: center;
  background: #111;
  pointer-events: none;
}

.odd-remote-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  text-align: center;
  color: #e9e9e9;
  font-size: 11px;
}

.odd-remote.is-expanded .odd-remote-placeholder {
  font-size: 14px;
  gap: 10px;
}

.odd-remote-placeholder small {
  color: #f8c8c9;
  max-width: 90%;
}

.odd-spin {
  animation: odd-remote-spin 1s linear infinite;
  color: #006cfa;
}

@keyframes odd-remote-spin {
  to { transform: rotate(360deg); }
}

.odd-rail {
  display: flex;
  align-items: stretch;
  gap: 2px;
  background: rgba(22, 33, 45, 0.94);
  border-radius: 10px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
  user-select: none;
  touch-action: none;
  z-index: 6;
}

.odd-rail-v {
  position: absolute;
  top: 0;
  bottom: 0;
  left: calc(100% + var(--odd-rail-gap));
  width: var(--odd-rail-size);
  flex-direction: column;
  padding: 3px;
}

.odd-rail-h {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + var(--odd-rail-gap));
  height: var(--odd-rail-size);
  flex-direction: row;
  padding: 3px;
}

.odd-rail-corner {
  position: absolute;
  top: calc(100% + var(--odd-rail-gap));
  left: calc(100% + var(--odd-rail-gap));
  width: var(--odd-rail-size);
  height: var(--odd-rail-size);
  border-radius: 10px;
  background: rgba(22, 33, 45, 0.94);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
  z-index: 6;
}

.odd-rail-nudge {
  flex: 0 0 auto;
  border: 0;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #e9e9e9;
  font-size: 9px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  min-width: 18px;
  min-height: 18px;
}

.odd-remote.is-expanded .odd-rail-nudge {
  min-width: 24px;
  min-height: 24px;
  font-size: 11px;
}

.odd-rail-nudge:hover {
  background: rgba(0, 108, 250, 0.55);
}

.odd-rail-track {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  cursor: grab;
}

.odd-rail-track:active {
  cursor: grabbing;
}

.odd-rail-thumb {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #006cfa;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.35);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.odd-rail-v .odd-rail-thumb {
  left: 50%;
}

.odd-rail-h .odd-rail-thumb {
  top: 50%;
}

.odd-remote.is-expanded .odd-rail-thumb {
  width: 18px;
  height: 18px;
}

.odd-remote-badge {
  position: absolute;
  left: 0;
  bottom: calc(100% + var(--odd-rail-gap));
  z-index: 6;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  background: rgba(22, 33, 45, 0.92);
  color: #fff;
  font-size: 10px;
  font-weight: 650;
  padding: 3px 8px;
  pointer-events: none;
  max-width: min(100%, 280px);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
}

.odd-remote.is-expanded .odd-remote-badge {
  left: 0;
  bottom: calc(100% + var(--odd-rail-gap));
  font-size: 12px;
  padding: 5px 10px;
  max-width: min(100%, 360px);
}

.odd-remote-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #737578;
  flex: 0 0 auto;
}

.odd-remote-dot.is-live {
  background: #04aa65;
  box-shadow: 0 0 0 3px rgba(4, 170, 101, 0.25);
}

.odd-remote-port,
.odd-remote-hint {
  opacity: 0.75;
}

.odd-remote-zoom {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 5;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: rgba(233, 233, 233, 0.92);
  color: #4a4c4e;
  cursor: pointer;
  padding: 0;
}

.odd-remote.is-expanded .odd-remote-zoom {
  top: 10px;
  right: 10px;
  width: 32px;
  height: 32px;
}
</style>
