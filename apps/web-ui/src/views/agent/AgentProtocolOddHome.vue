<template>
  <div class="odd-home" :class="{ 'is-expanded': expanded }">
    <nav class="odd-nav">
      <div class="odd-nav-links">
        <button
          v-for="item in navItems"
          :key="item.id"
          type="button"
          class="odd-nav-link"
          :class="{ 'is-active': tab === item.id }"
          @click="tab = item.id"
        >
          <span>{{ item.label }}</span>
          <i aria-hidden="true" />
        </button>
      </div>
      <div class="odd-nav-actions">
        <button
          type="button"
          class="odd-zoom-btn"
          :title="expanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
          :aria-label="expanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
          @click="$emit('toggle-expand')"
        >
          <Minimize2 v-if="expanded" :size="expanded ? 16 : 12" />
          <Maximize2 v-else :size="12" />
        </button>
        <button
          type="button"
          class="odd-overflow"
          :aria-label="t('agent.protocol.menuOverflow')"
          @click="menuOpen = !menuOpen"
        >
          <MoreVertical :size="expanded ? 18 : 14" />
        </button>
      </div>
    </nav>

    <div v-if="menuOpen" class="odd-menu-backdrop" @click="menuOpen = false" />
    <div v-if="menuOpen" class="odd-menu" role="menu">
      <button type="button" role="menuitem" @click="onMenu('home')">
        <RotateCcw :size="expanded ? 18 : 14" />
        <span>{{ t('agent.protocol.menuHomeGantry') }}</span>
      </button>
      <button type="button" role="menuitem" @click="onMenu('restart')">
        <RefreshCw :size="expanded ? 18 : 14" />
        <span>{{ t('agent.protocol.menuRestart') }}</span>
      </button>
      <button type="button" role="menuitem" @click="onMenu('shutdown')">
        <Power :size="expanded ? 18 : 14" />
        <span>{{ t('agent.protocol.menuShutdown') }}</span>
      </button>
      <button type="button" role="menuitem" @click="onMenu('deck')">
        <LayoutGrid :size="expanded ? 18 : 14" />
        <span>{{ t('agent.protocol.menuDeckConfig') }}</span>
      </button>
      <button type="button" role="menuitem" @click="toggleLights">
        <Lightbulb :size="expanded ? 18 : 14" />
        <span>{{ lightsOn ? t('agent.protocol.menuLightsOff') : t('agent.protocol.menuLightsOn') }}</span>
      </button>
    </div>

    <!-- Dashboard -->
    <section v-if="tab === 'dashboard'" class="odd-page">
      <div class="odd-empty-card">
        <img src="/agent-media/empty_protocol_dashboard.png" alt="" draggable="false">
        <strong>{{ t('agent.protocol.homeNoRuns') }}</strong>
        <p>{{ t('agent.protocol.homeNoRunsHint') }}</p>
      </div>
    </section>

    <!-- Protocols -->
    <section v-else-if="tab === 'protocols'" class="odd-page odd-protocols">
      <div class="odd-empty-card">
        <img src="/agent-media/empty_protocol_dashboard.png" alt="" draggable="false">
        <strong>{{ t('agent.protocol.homeNoProtocols') }}</strong>
        <p>{{ t('agent.protocol.homeNoProtocolsHint') }}</p>
      </div>
      <button type="button" class="odd-fab" @click="$emit('upload')">
        <Plus :size="expanded ? 22 : 16" />
        <span>{{ t('agent.protocol.upload') }}</span>
      </button>
    </section>

    <!-- Instruments -->
    <section v-else-if="tab === 'instruments'" class="odd-page">
      <div
        v-for="mount in instrumentMounts"
        :key="mount.id"
        class="odd-instrument-row"
      >
        <span class="odd-mount-label">{{ mount.label }}</span>
        <div class="odd-instrument-copy">
          <strong>{{ t('agent.protocol.instrumentEmpty') }}</strong>
          <small>{{ t('agent.protocol.instrumentAttachHint') }}</small>
        </div>
      </div>
    </section>

    <!-- Settings -->
    <section v-else class="odd-page odd-settings">
      <button
        v-for="item in settingItems"
        :key="item.id"
        type="button"
        class="odd-setting-row"
        @click="onSetting(item.id)"
      >
        <span>{{ item.label }}</span>
        <span class="odd-setting-meta">
          <template v-if="item.id === 'lights'">{{ lightsOn ? 'On' : 'Off' }}</template>
          <template v-else-if="item.id === 'version'">{{ versionLabel }}</template>
          <ChevronRight v-else :size="expanded ? 18 : 14" />
        </span>
      </button>
    </section>

    <p v-if="toast" class="odd-toast" role="status">{{ toast }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronRight,
  LayoutGrid,
  Lightbulb,
  Maximize2,
  Minimize2,
  MoreVertical,
  Plus,
  Power,
  RefreshCw,
  RotateCcw,
} from '@lucide/vue'

type HomeTab = 'dashboard' | 'protocols' | 'instruments' | 'settings'

const props = defineProps<{
  expanded?: boolean
  robotName?: string
  versionLabel?: string
}>()

const emit = defineEmits<{
  upload: []
  'toggle-expand': []
}>()

const { t } = useI18n()

const tab = ref<HomeTab>('dashboard')
const menuOpen = ref(false)
const lightsOn = ref(true)
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

const navItems = computed(() => [
  { id: 'dashboard' as const, label: props.robotName || t('agent.protocol.robotName') },
  { id: 'protocols' as const, label: t('agent.protocol.navProtocols') },
  { id: 'instruments' as const, label: t('agent.protocol.navInstruments') },
  { id: 'settings' as const, label: t('agent.protocol.navSettings') },
])

const instrumentMounts = computed(() => [
  { id: 'left', label: t('agent.protocol.mountLeft') },
  { id: 'right', label: t('agent.protocol.mountRight') },
  { id: 'extension', label: t('agent.protocol.mountExtension') },
])

const settingItems = computed(() => [
  { id: 'network', label: t('agent.protocol.settingsNetwork') },
  { id: 'robot-name', label: t('agent.protocol.settingsRobotName') },
  { id: 'lights', label: t('agent.protocol.settingsLights') },
  { id: 'deck', label: t('agent.protocol.menuDeckConfig') },
  { id: 'version', label: t('agent.protocol.settingsVersion') },
])

function showToast(message: string) {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
  }, 1800)
}

function onMenu(action: string) {
  menuOpen.value = false
  if (action === 'home') showToast(t('agent.protocol.menuHomeGantryDone'))
  else if (action === 'restart') showToast(t('agent.protocol.menuSimulated'))
  else if (action === 'shutdown') showToast(t('agent.protocol.menuSimulated'))
  else if (action === 'deck') {
    tab.value = 'settings'
    showToast(t('agent.protocol.menuDeckConfig'))
  }
}

function toggleLights() {
  lightsOn.value = !lightsOn.value
  menuOpen.value = false
  showToast(lightsOn.value ? t('agent.protocol.menuLightsOn') : t('agent.protocol.menuLightsOff'))
}

function onSetting(id: string) {
  if (id === 'lights') {
    lightsOn.value = !lightsOn.value
    return
  }
  if (id === 'protocols-upload') {
    emit('upload')
    return
  }
  showToast(t('agent.protocol.menuSimulated'))
}

defineExpose({
  openProtocols() {
    tab.value = 'protocols'
  },
})
</script>

<style scoped>
.odd-home {
  --odd-black: #16212d;
  --odd-grey60: #4a4c4e;
  --odd-grey50: #737578;
  --odd-grey35: #cbcccc;
  --odd-grey30: #dedede;
  --odd-grey20: #e9e9e9;
  --odd-blue50: #006cfa;
  --odd-purple50: #893ba4;
  --odd-yellow35: #ffe1a4;
  --odd-white: #ffffff;

  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--odd-white);
  color: var(--odd-black);
  font-size: 10.5px;
  line-height: 1.25;
  overflow: hidden;
}

.odd-home.is-expanded {
  font-size: 14px;
  line-height: 1.35;
}

.odd-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 4px 6px 2px;
  flex: 0 0 auto;
  background: var(--odd-white);
}

.odd-home.is-expanded .odd-nav {
  padding: 10px 14px 6px;
  gap: 10px;
}

.odd-nav-links {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
  overflow-x: auto;
  flex: 1;
  scrollbar-width: none;
}

.odd-nav-links::-webkit-scrollbar {
  display: none;
}

.odd-home.is-expanded .odd-nav-links {
  gap: 18px;
}

.odd-nav-link {
  border: 0;
  background: transparent;
  color: var(--odd-grey50);
  font: inherit;
  font-weight: 650;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
  cursor: pointer;
}

.odd-nav-link i {
  width: 14px;
  height: 2px;
  border-radius: 2px;
  background: transparent;
}

.odd-home.is-expanded .odd-nav-link i {
  width: 22px;
  height: 3px;
}

.odd-nav-link.is-active {
  color: var(--odd-black);
}

.odd-nav-link.is-active i {
  background: var(--odd-purple50);
}

.odd-nav-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.odd-zoom-btn,
.odd-overflow {
  border: 0;
  background: transparent;
  color: var(--odd-grey60);
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  cursor: pointer;
  padding: 0;
}

.odd-home.is-expanded .odd-zoom-btn,
.odd-home.is-expanded .odd-overflow {
  width: 32px;
  height: 32px;
}

.odd-overflow:hover,
.odd-zoom-btn:hover {
  background: var(--odd-grey20);
}

.odd-menu-backdrop {
  position: absolute;
  inset: 0;
  z-index: 4;
  background: transparent;
}

.odd-menu {
  position: absolute;
  top: 28px;
  right: 6px;
  z-index: 5;
  min-width: 148px;
  background: var(--odd-white);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(22, 33, 45, 0.22);
  padding: 4px;
  display: flex;
  flex-direction: column;
}

.odd-home.is-expanded .odd-menu {
  top: 48px;
  right: 14px;
  min-width: 220px;
  border-radius: 14px;
  padding: 6px;
}

.odd-menu button {
  border: 0;
  background: transparent;
  color: var(--odd-black);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  font: inherit;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}

.odd-menu button:hover {
  background: var(--odd-grey20);
}

.odd-page {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 4px 6px 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.odd-home.is-expanded .odd-page {
  padding: 8px 16px 16px;
  gap: 10px;
}

.odd-empty-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 4px;
  background: var(--odd-grey35);
  border-radius: 10px;
  padding: 10px 8px;
}

.odd-home.is-expanded .odd-empty-card {
  border-radius: 16px;
  gap: 8px;
  padding: 24px;
}

.odd-empty-card img {
  width: min(42%, 120px);
  height: auto;
  margin-bottom: 2px;
  user-select: none;
  pointer-events: none;
}

.odd-home.is-expanded .odd-empty-card img {
  width: min(36%, 220px);
}

.odd-empty-card strong {
  font-weight: 700;
}

.odd-empty-card p {
  margin: 0;
  color: var(--odd-grey60);
  font-size: 0.9em;
  max-width: 28em;
}

.odd-protocols {
  position: relative;
}

.odd-fab {
  position: absolute;
  right: 8px;
  bottom: 8px;
  border: 0;
  border-radius: 999px;
  background: var(--odd-blue50);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  font: inherit;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 108, 250, 0.28);
}

.odd-home.is-expanded .odd-fab {
  right: 18px;
  bottom: 18px;
  padding: 12px 16px;
  gap: 8px;
}

.odd-instrument-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: var(--odd-yellow35);
  border-radius: 8px;
  padding: 7px 8px;
}

.odd-home.is-expanded .odd-instrument-row {
  border-radius: 12px;
  padding: 12px 14px;
  gap: 12px;
}

.odd-mount-label {
  min-width: 42px;
  border-radius: 4px;
  background: var(--odd-black);
  color: #fff;
  font-size: 0.78em;
  font-weight: 700;
  padding: 2px 5px;
  text-align: center;
}

.odd-instrument-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.odd-instrument-copy strong {
  font-weight: 650;
}

.odd-instrument-copy small {
  color: var(--odd-grey60);
  font-size: 0.88em;
}

.odd-settings {
  gap: 4px;
}

.odd-setting-row {
  border: 0;
  border-radius: 10px;
  background: var(--odd-grey20);
  color: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  font: inherit;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}

.odd-home.is-expanded .odd-setting-row {
  border-radius: 14px;
  padding: 14px 16px;
}

.odd-setting-meta {
  color: var(--odd-grey60);
  display: inline-flex;
  align-items: center;
  font-size: 0.92em;
}

.odd-toast {
  position: absolute;
  left: 50%;
  bottom: 10px;
  transform: translateX(-50%);
  margin: 0;
  background: var(--odd-black);
  color: #fff;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 0.88em;
  font-weight: 650;
  white-space: nowrap;
  z-index: 6;
  pointer-events: none;
}
</style>
