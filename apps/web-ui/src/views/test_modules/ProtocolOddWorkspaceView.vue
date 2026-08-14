<template>
  <div class="protocol-odd-workspace">
    <header class="workspace-header">
      <button type="button" class="workspace-back" @click="goBack">
        <ArrowLeft :size="16" aria-hidden="true" />
        {{ t('protocolMonitor.oddWorkspaceBack') }}
      </button>
      <div class="workspace-title-block">
        <h1>{{ pageTitle }}</h1>
        <p v-if="deviceLabel" class="workspace-device">{{ deviceLabel }}</p>
      </div>
    </header>

    <AgentProtocolPanel
      :key="panelKey"
      :initial-mode="mode"
      :initial-ip="deviceIp"
      :initial-name="deviceName"
      :initial-api-port="devicePort"
      :auto-connect-remote="mode === 'remote' && Boolean(deviceIp)"
      :show-mode-switch="true"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft } from '@lucide/vue'
import AgentProtocolPanel from '@/views/agent/AgentProtocolPanel.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const mode = computed<'simulate' | 'remote'>(() => (
  String(route.query.mode || '').toLowerCase() === 'remote' ? 'remote' : 'simulate'
))

const deviceIp = computed(() => String(route.query.ip || '').trim())
const deviceName = computed(() => String(route.query.name || '').trim())
const devicePort = computed(() => {
  const raw = Number(route.query.port)
  return Number.isFinite(raw) && raw > 0 ? raw : 31950
})

const pageTitle = computed(() => t('protocolMonitor.oddWorkspaceTitle'))

const deviceLabel = computed(() => {
  if (!deviceIp.value && !deviceName.value) return ''
  if (deviceName.value && deviceIp.value) return `${deviceName.value} · ${deviceIp.value}`
  return deviceName.value || deviceIp.value
})

const panelKey = computed(() => (
  `${mode.value}:${deviceIp.value}:${devicePort.value}`
))

function goBack() {
  void router.push({ name: 'ProtocolTests' })
}
</script>

<style scoped>
.protocol-odd-workspace {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  height: 100%;
  background: #fff;
}

.workspace-header {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 16px 32px 0;
}

.workspace-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #0069da;
  font: inherit;
  font-size: 0.92rem;
  font-weight: 650;
  cursor: pointer;
}

.workspace-back:hover {
  text-decoration: underline;
  text-underline-offset: 2px;
}

.workspace-title-block h1 {
  margin: 0;
  color: #16212d;
  font-size: clamp(1.35rem, 1.8vw, 1.7rem);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.workspace-device {
  margin: 4px 0 0;
  color: #6a7380;
  font-size: 0.95rem;
}

.protocol-odd-workspace :deep(.protocol-panel) {
  flex: 1 1 auto;
  min-height: 0;
  padding-top: 12px;
}
</style>
