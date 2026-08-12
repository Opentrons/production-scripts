<template>
  <div class="app-container">
    <header class="app-header">
      <div class="header-left">
        <div class="header-brand" :aria-label="t('layout.brand')">
          <span class="header-brand-mark" aria-hidden="true">T</span>
          <span class="header-brand-text">Productions Testing</span>
        </div>
      </div>
      <div class="header-right">
        <div class="health-status">
          <span class="last-update">{{ t('layout.lastUpdate', { time: lastUpdateText }) }}</span>
          <div class="status-item">
            <span class="status-label">{{ t('layout.server') }}:</span>
            <span 
              class="status-indicator" 
              :class="serverStatusClass"
            ></span>
            <span class="status-text">{{ serverStatusText }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Google Drive:</span>
            <span 
              class="status-indicator" 
              :class="googleDriveStatusClass"
            ></span>
            <span class="status-text">{{ googleDriveStatusText }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Slack:</span>
            <span 
              class="status-indicator" 
              :class="slackStatusClass"
            ></span>
            <span class="status-text">{{ slackStatusText }}</span>
          </div>
          <el-button 
            :icon="Refresh" 
            circle 
            size="small" 
            @click="refreshHealth"
            :loading="healthStore.loading"
          />
          <el-badge :value="unreadMessageCount" :hidden="unreadMessageCount === 0" :max="99">
            <el-button
              :icon="Bell"
              circle
              size="small"
              :aria-label="t('layout.openMessages')"
              @click="openMessages"
            />
          </el-badge>
        </div>
        <AuthUserMenu variant="dark" />
      </div>
    </header>
    
    <div class="app-body">
      <aside class="app-sidebar" :class="{ 'is-collapsed': sidebarCollapsed }">
        <el-menu
          :default-active="activeMenu"
          class="sidebar-menu"
          :collapse="false"
          @select="handleMenuSelect"
        >
          <template v-for="item in menuItems" :key="item.id">
            <el-sub-menu v-if="item.children" :index="item.id">
              <template #title>
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.name }}</span>
              </template>
              <el-menu-item 
                v-for="child in item.children" 
                :key="child.id" 
                :index="child.id"
              >
                <el-icon><component :is="child.icon" /></el-icon>
                <span>{{ child.name }}</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="item.id">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.name }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </aside>

      <div class="sidebar-divider">
        <el-tooltip
          :content="sidebarCollapsed ? t('layout.expandSidebar') : t('layout.collapseSidebar')"
          placement="right"
        >
          <button
            class="sidebar-toggle"
            type="button"
            :aria-label="sidebarCollapsed ? t('layout.expandSidebar') : t('layout.collapseSidebar')"
            @click="toggleSidebar"
          >
            <el-icon>
              <component :is="sidebarCollapsed ? ArrowRight : ArrowLeft" />
            </el-icon>
          </button>
        </el-tooltip>
      </div>
      
      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useHealthStore } from '@/scripts/stores/health'
import { useMessageStore } from '@/scripts/stores/message'
import { Refresh, DataAnalysis, Setting, Monitor, ArrowLeft, ArrowRight, UploadFilled, Bell, Link as LinkIcon, DocumentChecked, Histogram, Tickets, Memo } from '@element-plus/icons-vue'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import { useAppLocale } from '@/i18n'

const router = useRouter()
const route = useRoute()
const healthStore = useHealthStore()
const messageStore = useMessageStore()
const { locale, t } = useAppLocale()
const sidebarCollapsed = ref(false)
const HEALTH_REFRESH_INTERVAL_MS = 10 * 60 * 1000
const MESSAGE_REFRESH_INTERVAL_MS = 30 * 1000

const allMenuItems = computed(() => [
  {
    id: 'menu-devices',
    name: t('layout.nav.devices'),
    icon: Monitor,
    path: '/devices'
  },
  {
    id: 'menu-test-cases',
    name: t('layout.nav.tests'),
    icon: DocumentChecked,
    children: [
      { id: 'menu-terminal-tests', name: t('layout.nav.terminalTests'), icon: Tickets, path: '/test-cases' },
      { id: 'menu-protocol-tests', name: t('layout.nav.protocolTests'), icon: Memo, path: '/test-cases/protocol' }
    ]
  },
  {
    id: 'menu-data-uploads',
    name: t('layout.nav.uploads'),
    icon: UploadFilled,
    path: '/data/uploads'
  },
  {
    id: 'menu-data',
    name: t('layout.nav.data'),
    icon: DataAnalysis,
    children: [
      { id: 'menu-data-list', name: t('layout.nav.testData'), icon: DataAnalysis, path: '/data' },
      { id: 'menu-data-analysis', name: t('layout.nav.analysis'), icon: Histogram, path: '/data/analysis' },
      { id: 'menu-data-links', name: t('layout.nav.links'), icon: LinkIcon, path: '/data/links' }
    ]
  },
  {
    id: 'menu-settings',
    name: t('layout.nav.settings'),
    icon: Setting,
    path: '/settings'
  }
])

const menuItems = computed(() => allMenuItems.value)

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/devices' || path === '/devices/control') return 'menu-devices'
  if (path === '/test-cases') return 'menu-terminal-tests'
  if (path === '/test-cases/protocol') return 'menu-protocol-tests'
  if (path === '/data/uploads') return 'menu-data-uploads'
  if (path === '/data') return 'menu-data-list'
  if (path === '/data/analysis') return 'menu-data-analysis'
  if (path === '/data/links') return 'menu-data-links'
  if (path === '/settings') return 'menu-settings'
  return ''
})

const unreadMessageCount = computed(() => {
  return messageStore.unreadCount
})

const serverStatusClass = computed(() => {
  if (!healthStore.healthData?.services?.system_service) return 'unknown'
  const status = healthStore.healthData.services.system_service.status
  if (status === 'running' || status === 'healthy') return 'healthy'
  if (status === 'failed') return 'failed'
  if (status === 'stopped') return 'stopped'
  return 'unknown'
})

const serverStatusText = computed(() => {
  if (!healthStore.healthData?.services?.system_service) return t('common.status.unknown')
  const status = healthStore.healthData.services.system_service.status
  const statusMap: Record<string, string> = {
    'running': t('common.status.running'),
    'stopped': t('common.status.stopped'),
    'failed': t('common.status.error'),
    'healthy': t('common.status.healthy'),
    'unhealthy': t('common.status.abnormal'),
    'unknown': t('common.status.unknown')
  }
  return statusMap[status] || t('common.status.unknown')
})

const googleDriveStatusClass = computed(() => {
  if (!healthStore.healthData?.services?.google_drive) return 'unknown'
  return healthStore.healthData.services.google_drive.status
})

const googleDriveStatusText = computed(() => {
  if (!healthStore.healthData?.services?.google_drive) return t('common.status.unknown')
  return healthStore.healthData.services.google_drive.status === 'healthy'
    ? t('common.status.healthy')
    : t('common.status.abnormal')
})

const slackStatusClass = computed(() => {
  if (!healthStore.healthData?.services?.slack) return 'unknown'
  return healthStore.healthData.services.slack.status
})

const slackStatusText = computed(() => {
  if (!healthStore.healthData?.services?.slack) return t('common.status.unknown')
  return healthStore.healthData.services.slack.status === 'healthy'
    ? t('common.status.healthy')
    : t('common.status.abnormal')
})

const lastUpdateText = computed(() => {
  if (!healthStore.lastUpdateTime) return t('layout.notUpdated')
  return healthStore.lastUpdateTime.toLocaleString(locale.value, {
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit',
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit' 
  })
})

const refreshHealth = () => {
  healthStore.fetchHealth()
}

const openMessages = () => {
  router.push('/messages')
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const handleMenuSelect = (index: string) => {
  const findPath = (items: any[]): string | null => {
    for (const item of items) {
      if (item.id === index && item.path) {
        return item.path
      }
      if (item.children) {
        const path = findPath(item.children)
        if (path) return path
      }
    }
    return null
  }
  
  const path = findPath(menuItems.value)
  if (path) {
    router.push(path)
  }
}

let healthInterval: ReturnType<typeof setInterval>
let messageInterval: ReturnType<typeof setInterval>

onMounted(() => {
  healthStore.fetchHealth()
  messageStore.fetchMessages()
  healthInterval = setInterval(() => {
    healthStore.fetchHealth()
  }, HEALTH_REFRESH_INTERVAL_MS)
  messageInterval = setInterval(() => {
    messageStore.fetchMessages()
  }, MESSAGE_REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (healthInterval) {
    clearInterval(healthInterval)
  }
  if (messageInterval) {
    clearInterval(messageInterval)
  }
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f7fa;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 60px;
  padding: 0 20px;
  background-color: #17212d;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.2);
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: inherit;
}

.header-brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 8px;
  background: #409eff;
  color: #071525;
  font-size: 25px;
  font-weight: 900;
  line-height: 1;
}

.header-brand-text {
  color: #f3f7fb;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.health-status {
  display: flex;
  align-items: center;
  gap: 20px;
}

.health-status :deep(.el-button.is-circle) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.14);
  color: #d7e2ee;
}

.health-status :deep(.el-button.is-circle:hover) {
  background: rgba(64, 158, 255, 0.18);
  border-color: rgba(64, 158, 255, 0.45);
  color: #ffffff;
}

.last-update {
  font-size: 12px;
  color: #8fa2b7;
  margin-right: 10px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  font-size: 14px;
  color: #aebdcb;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-indicator.healthy, .status-indicator.running {
  background-color: #67c23a;
  box-shadow: 0 0 6px #67c23a;
}

.status-indicator.unhealthy, .status-indicator.stopped {
  background-color: #f56c6c;
  box-shadow: 0 0 6px #f56c6c;
}

.status-indicator.failed {
  background-color: #e6a23c;
  box-shadow: 0 0 6px #e6a23c;
}

.status-indicator.unknown {
  background-color: #909399;
  box-shadow: 0 0 6px #909399;
}

.status-text {
  font-size: 13px;
  color: #d7e2ee;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-sidebar {
  width: 220px;
  flex: 0 0 220px;
  background-color: #17212d;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  overflow-y: auto;
  transition: width 0.2s ease, flex-basis 0.2s ease, border-color 0.2s ease;
}

.app-sidebar.is-collapsed {
  width: 0;
  flex-basis: 0;
  border-right-color: transparent;
  overflow: hidden;
}

.sidebar-menu {
  border-right: none;
  height: 100%;
  width: 220px;
  min-width: 220px;
  background-color: transparent;
}

.sidebar-menu :deep(.el-menu) {
  background-color: transparent;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: #aebdcb;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.06);
  color: #f3f7fb;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background-color: rgba(64, 158, 255, 0.18);
  color: #8cc7ff;
}

.sidebar-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #f3f7fb;
}

.sidebar-menu :deep(.el-sub-menu__icon-arrow) {
  color: #8fa2b7;
}

.sidebar-divider {
  position: relative;
  flex: 0 0 1px;
  background-color: rgba(23, 33, 45, 0.35);
}

.sidebar-divider::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -8px;
  width: 17px;
  background-color: transparent;
}

.sidebar-toggle {
  position: absolute;
  top: 50%;
  left: 0;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 38px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 0 0 1px rgba(220, 223, 230, 0.85);
  color: #a8abb2;
  cursor: pointer;
  transform: translate(-50%, -50%);
  transition: color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.sidebar-toggle:hover {
  color: #409eff;
  background-color: #fff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.55), 0 2px 8px rgba(64, 158, 255, 0.12);
}

.sidebar-toggle .el-icon {
  font-size: 10px;
}

.app-main {
  flex: 1;
  padding: 0;
  overflow-y: auto;
  background-color: #f5f7fa;
}
</style>
