<template>
  <div
    class="device-camera-media"
    :class="{ 'is-streaming': mediaMode === 'stream' }"
  >
    <img
      v-if="mediaMode === 'image'"
      class="device-media-image"
      :src="imageSrc"
      :alt="imageAlt"
    />
    <video
      v-else
      ref="cardVideoRef"
      class="device-media-video"
      autoplay
      muted
      playsinline
    />

    <div v-if="streamLoading" class="media-state-overlay" aria-live="polite">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <button
      v-if="mediaMode === 'stream' && streamError"
      class="media-state-overlay is-error"
      type="button"
      :aria-label="t('protocolMonitor.camera.retryStream')"
      @click.stop="retryStream"
    >
      <el-icon><WarningFilled /></el-icon>
      <span>{{ streamError }}</span>
    </button>

    <slot />

    <div class="media-actions">
      <el-tooltip
        :content="t(mediaMode === 'image' ? 'protocolMonitor.camera.showStream' : 'protocolMonitor.camera.showImage')"
        placement="top"
      >
        <el-button
          :icon="mediaMode === 'image' ? VideoCamera : Picture"
          circle
          size="small"
          :loading="enablingStream"
          :aria-label="t(mediaMode === 'image' ? 'protocolMonitor.camera.showStream' : 'protocolMonitor.camera.showImage')"
          @click.stop="toggleMedia"
        />
      </el-tooltip>
      <el-tooltip :content="t('protocolMonitor.camera.enlarge')" placement="top">
        <el-button
          :icon="FullScreen"
          circle
          size="small"
          :aria-label="t('protocolMonitor.camera.enlarge')"
          @click.stop="previewVisible = true"
        />
      </el-tooltip>
    </div>

    <el-dialog
      v-model="previewVisible"
      class="device-camera-dialog"
      width="min(1100px, 92vw)"
      append-to-body
      destroy-on-close
      :title="deviceName"
    >
      <div class="device-camera-preview" :class="{ 'is-streaming': mediaMode === 'stream' }">
        <img
          v-if="mediaMode === 'image'"
          :src="imageSrc"
          :alt="imageAlt"
        />
        <video
          v-else
          ref="previewVideoRef"
          autoplay
          muted
          playsinline
          controls
        />
        <div v-if="mediaMode === 'stream' && streamLoading" class="media-state-overlay" aria-live="polite">
          <el-icon class="is-loading"><Loading /></el-icon>
        </div>
        <button
          v-if="mediaMode === 'stream' && streamError"
          class="media-state-overlay is-error"
          type="button"
          :aria-label="t('protocolMonitor.camera.retryStream')"
          @click="retryStream"
        >
          <el-icon><WarningFilled /></el-icon>
          <span>{{ streamError }}</span>
        </button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type HlsInstance from 'hls.js'
import { ElMessage } from 'element-plus'
import {
  FullScreen,
  Loading,
  Picture,
  VideoCamera,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { protocolMonitorApi } from '@/scripts/api'

const props = defineProps<{
  roomId: string
  deviceId: string
  deviceName: string
  imageSrc: string
}>()

const { t } = useI18n()
const mediaMode = ref<'image' | 'stream'>('image')
const enablingStream = ref(false)
const streamLoading = ref(false)
const streamError = ref('')
const previewVisible = ref(false)
const cardVideoRef = ref<HTMLVideoElement | null>(null)
const previewVideoRef = ref<HTMLVideoElement | null>(null)
let hls: HlsInstance | null = null

const imageAlt = computed(() => `${props.deviceName} Flex`)

function normalizeError(error: any): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return error?.message || t('protocolMonitor.camera.streamUnavailable')
}

function activeVideoElement(): HTMLVideoElement | null {
  return previewVisible.value ? previewVideoRef.value : cardVideoRef.value
}

function clearVideoElements(): void {
  for (const video of [cardVideoRef.value, previewVideoRef.value]) {
    if (!video) continue
    video.pause()
    video.removeAttribute('src')
    video.load()
  }
}

function destroyStream(): void {
  hls?.destroy()
  hls = null
  clearVideoElements()
}

function markStreamReady(video: HTMLVideoElement): void {
  streamLoading.value = false
  streamError.value = ''
  void video.play().catch(() => {
    streamError.value = t('protocolMonitor.camera.playFailed')
  })
}

async function attachStream(): Promise<void> {
  const video = activeVideoElement()
  if (!video || mediaMode.value !== 'stream') return
  destroyStream()
  streamLoading.value = true
  streamError.value = ''
  const streamUrl = protocolMonitorApi.deviceLivestreamUrl(props.roomId, props.deviceId)

  const { default: Hls } = await import('hls.js')
  if (mediaMode.value !== 'stream' || activeVideoElement() !== video) return

  if (Hls.isSupported()) {
    const instance = new Hls({
      backBufferLength: 0,
      liveSyncDuration: 2,
      liveMaxLatencyDuration: 5,
      manifestLoadingMaxRetry: 8,
      manifestLoadingRetryDelay: 1000,
      levelLoadingMaxRetry: 8,
      fragLoadingMaxRetry: 8,
      xhrSetup: xhr => {
        xhr.withCredentials = true
      },
    })
    hls = instance
    instance.loadSource(streamUrl)
    instance.attachMedia(video)
    instance.on(Hls.Events.MANIFEST_PARSED, () => {
      if (hls === instance) markStreamReady(video)
    })
    instance.on(Hls.Events.ERROR, (_event, data) => {
      if (!data.fatal || hls !== instance) return
      streamLoading.value = false
      streamError.value = t('protocolMonitor.camera.streamUnavailable')
    })
    return
  }

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = streamUrl
    video.onloadedmetadata = () => markStreamReady(video)
    video.onerror = () => {
      streamLoading.value = false
      streamError.value = t('protocolMonitor.camera.streamUnavailable')
    }
    return
  }

  streamLoading.value = false
  streamError.value = t('protocolMonitor.camera.unsupported')
}

async function showStream(): Promise<void> {
  enablingStream.value = true
  try {
    await protocolMonitorApi.enableDeviceLivestream(props.roomId, props.deviceId)
    mediaMode.value = 'stream'
    await nextTick()
    await attachStream()
  } catch (error) {
    const message = normalizeError(error)
    streamError.value = message
    ElMessage.error(message)
  } finally {
    enablingStream.value = false
  }
}

function showImage(): void {
  destroyStream()
  mediaMode.value = 'image'
  streamLoading.value = false
  streamError.value = ''
}

function toggleMedia(): void {
  if (mediaMode.value === 'stream') showImage()
  else void showStream()
}

async function retryStream(): Promise<void> {
  await nextTick()
  await attachStream()
}

watch(previewVisible, async () => {
  if (mediaMode.value !== 'stream') return
  await nextTick()
  await attachStream()
})

onBeforeUnmount(destroyStream)
</script>

<style scoped>
.device-camera-media {
  position: relative;
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  overflow: hidden;
}

.device-media-image {
  display: block;
  width: auto;
  max-width: calc(100% - 36px);
  height: 138px;
  object-fit: contain;
  filter: drop-shadow(0 9px 10px rgba(23, 32, 51, 0.14));
}

.device-media-video {
  display: block;
  width: 100%;
  height: 100%;
  background: #10141a;
  object-fit: cover;
}

.media-actions {
  position: absolute;
  right: 8px;
  bottom: 8px;
  z-index: 4;
  display: flex;
  gap: 6px;
  opacity: 0;
  transform: translateY(3px);
  transition: opacity 150ms ease, transform 150ms ease;
}

.device-camera-media:hover .media-actions,
.device-camera-media:focus-within .media-actions,
.device-camera-media.is-streaming .media-actions {
  opacity: 1;
  transform: translateY(0);
}

.media-actions :deep(.el-button) {
  margin: 0;
  border-color: rgba(220, 227, 235, 0.95);
  background: rgba(255, 255, 255, 0.94);
  color: #172033;
  box-shadow: 0 2px 7px rgba(23, 32, 51, 0.16);
}

.media-state-overlay {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: grid;
  place-content: center;
  background: rgba(16, 20, 26, 0.42);
  color: #ffffff;
  font-size: 24px;
}

.media-state-overlay.is-error {
  width: 100%;
  border: 0;
  cursor: pointer;
  font: inherit;
  gap: 8px;
}

.media-state-overlay.is-error span {
  max-width: min(80%, 420px);
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
}

.device-camera-preview {
  position: relative;
  display: grid;
  width: 100%;
  min-height: 320px;
  max-height: 74vh;
  place-items: center;
  overflow: hidden;
  background: #eef2f6;
  aspect-ratio: 16 / 9;
}

.device-camera-preview.is-streaming {
  background: #10141a;
}

.device-camera-preview img,
.device-camera-preview video {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 74vh;
  object-fit: contain;
}

:global(.device-camera-dialog .el-dialog__body) {
  padding: 0;
}

@media (hover: none) {
  .media-actions {
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 640px) {
  .device-camera-preview {
    min-height: 220px;
  }
}
</style>
