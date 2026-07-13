<template>
  <div class="app-container">
    <header class="app-header">
      <div class="header-left">
        <img src="@/assets/logo.png" alt="Productions Opentrons" class="header-logo" />
        <span class="header-brand-text">Productions Opentrons</span>
      </div>
      <div class="header-right">
        <div class="health-status">
          <span class="last-update">更新: {{ lastUpdateText }}</span>
          <div class="status-item">
            <span class="status-label">Server:</span>
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
              @click="openMessages"
            />
          </el-badge>
        </div>
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
          :content="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
          placement="right"
        >
          <button
            class="sidebar-toggle"
            type="button"
            :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
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
import { useHealthStore } from '@/stores/health'
import { useMessageStore } from '@/stores/message'
import { Refresh, HomeFilled, DataAnalysis, Setting, Monitor, ArrowLeft, ArrowRight, UploadFilled, Bell, Link as LinkIcon, DocumentChecked, Histogram, Goods } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const healthStore = useHealthStore()
const messageStore = useMessageStore()
const sidebarCollapsed = ref(false)
const HEALTH_REFRESH_INTERVAL_MS = 10 * 60 * 1000
const MESSAGE_REFRESH_INTERVAL_MS = 30 * 1000

const menuItems = ref([
  {
    id: 'menu-home',
    name: '首页',
    icon: HomeFilled,
    path: '/home'
  },
  {
    id: 'menu-devices',
    name: '设备管理',
    icon: Monitor,
    path: '/devices'
  },
  {
    id: 'menu-test-cases',
    name: '测试管理',
    icon: DocumentChecked,
    children: [
      { id: 'menu-terminal-tests', name: '终端测试', icon: DocumentChecked, path: '/test-cases' },
      { id: 'menu-protocol-tests', name: 'Protocol测试', icon: DocumentChecked, path: '/test-cases/protocol' }
    ]
  },
  {
    id: 'menu-products',
    name: '产品管理',
    icon: Goods,
    path: '/data/products'
  },
  {
    id: 'menu-data',
    name: '数据管理',
    icon: DataAnalysis,
    children: [
      { id: 'menu-data-list', name: '测试数据', icon: DataAnalysis, path: '/data' },
      { id: 'menu-data-uploads', name: '数据上传', icon: UploadFilled, path: '/data/uploads' },
      { id: 'menu-data-analysis', name: '数据分析', icon: Histogram, path: '/data/analysis' },
      { id: 'menu-data-links', name: '数据链接', icon: LinkIcon, path: '/data/links' }
    ]
  },
  {
    id: 'menu-settings',
    name: '系统设置',
    icon: Setting,
    path: '/settings'
  }
])

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/home') return 'menu-home'
  if (path === '/devices' || path === '/devices/control') return 'menu-devices'
  if (path === '/test-cases') return 'menu-terminal-tests'
  if (path === '/test-cases/protocol') return 'menu-protocol-tests'
  if (path === '/data/products') return 'menu-products'
  if (path === '/data') return 'menu-data-list'
  if (path === '/data/uploads') return 'menu-data-uploads'
  if (path === '/data/analysis') return 'menu-data-analysis'
  if (path === '/data/links') return 'menu-data-links'
  if (path === '/settings') return 'menu-settings'
  return 'menu-home'
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
  if (!healthStore.healthData?.services?.system_service) return '未知'
  const status = healthStore.healthData.services.system_service.status
  const statusMap: Record<string, string> = {
    'running': '运行中',
    'stopped': '已停止',
    'failed': '失败',
    'healthy': '正常',
    'unhealthy': '异常',
    'unknown': '未知'
  }
  return statusMap[status] || '未知'
})

const googleDriveStatusClass = computed(() => {
  if (!healthStore.healthData?.services?.google_drive) return 'unknown'
  return healthStore.healthData.services.google_drive.status
})

const googleDriveStatusText = computed(() => {
  if (!healthStore.healthData?.services?.google_drive) return '未知'
  return healthStore.healthData.services.google_drive.status === 'healthy' ? '正常' : '异常'
})

const slackStatusClass = computed(() => {
  if (!healthStore.healthData?.services?.slack) return 'unknown'
  return healthStore.healthData.services.slack.status
})

const slackStatusText = computed(() => {
  if (!healthStore.healthData?.services?.slack) return '未知'
  return healthStore.healthData.services.slack.status === 'healthy' ? '正常' : '异常'
})

const lastUpdateText = computed(() => {
  if (!healthStore.lastUpdateTime) return '未更新'
  return healthStore.lastUpdateTime.toLocaleString('zh-CN', { 
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

.header-logo {
  width: 30px;
  height: 34px;
  object-fit: contain;
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
