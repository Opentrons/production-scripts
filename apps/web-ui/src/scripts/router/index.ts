import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { pinia } from '@/scripts/stores'
import { useAuthStore } from '@/scripts/stores/auth'
import { i18n } from '@/i18n'

const DEFAULT_FAVICON = '/favicon.png'
const AGENT_FAVICON = '/agent-favicon.svg'
const TESTING_FAVICON = '/testing-favicon.svg'
const VERSION_FAVICON = '/versions-favicon.svg'
const productionTestingMeta = {
  titleKey: 'titles.testing',
  favicon: TESTING_FAVICON,
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { standalone: true, public: true, titleKey: 'titles.login', favicon: DEFAULT_FAVICON },
  },
  {
    path: '/',
    name: 'Platform',
    component: () => import('@/views/dashboard/DashboardView.vue'),
    props: { mode: 'dashboard' },
    meta: { standalone: true, titleKey: 'titles.platform', favicon: DEFAULT_FAVICON },
  },
  {
    path: '/downloads',
    name: 'Downloads',
    component: () => import('@/views/dashboard/DashboardView.vue'),
    props: { mode: 'downloads' },
    meta: { standalone: true, titleKey: 'titles.downloads', favicon: DEFAULT_FAVICON },
  },
  {
    path: '/versions',
    name: 'Versions',
    component: () => import('@/views/version_modules/WorkflowManagementView.vue'),
    meta: { standalone: true, titleKey: 'titles.versions', favicon: VERSION_FAVICON },
  },
  {
    path: '/agent',
    name: 'ProductionAgent',
    component: () => import('@/views/agent/ProductionAgentView.vue'),
    meta: { standalone: true, titleKey: 'titles.agent', favicon: AGENT_FAVICON },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/dashboard/HomeView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/devices/DevicesView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/devices/control',
    name: 'DeviceControl',
    component: () => import('@/views/devices/DeviceControlView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/test-cases',
    name: 'TestCases',
    component: () => import('@/views/test_modules/TestCaseManagementView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/test-cases/protocol',
    name: 'ProtocolTests',
    component: () => import('@/views/test_modules/ProtocolTestView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/test-cases/protocol/odd',
    name: 'ProtocolOddWorkspace',
    component: () => import('@/views/test_modules/ProtocolOddWorkspaceView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/views/data/DataView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/uploads',
    name: 'UploadRecords',
    component: () => import('@/views/data/UploadRecordsView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/products',
    name: 'ProductManagement',
    component: () => import('@/views/data/ProductManagementView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/analysis',
    name: 'DataAnalysis',
    component: () => import('@/views/data/PipetteGravAnalysisView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/analysis/pipette-assembly-qc',
    name: 'PipetteAssemblyQcAnalysis',
    component: () => import('@/views/data/PipetteAssemblyQcAnalysisView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/analysis/robot-assembly-qc',
    name: 'RobotAssemblyQcAnalysis',
    component: () => import('@/views/data/RobotAssemblyQcAnalysisView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/data/links',
    name: 'DataLinks',
    component: () => import('@/views/data/DataLinksView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/information/ecn',
    name: 'InformationEcn',
    component: () => import('@/views/information/InformationView.vue'),
    props: { kind: 'ecn' },
    meta: productionTestingMeta,
  },
  {
    path: '/information/contact-letters',
    name: 'InformationContactLetters',
    component: () => import('@/views/information/InformationView.vue'),
    props: { kind: 'contact' },
    meta: productionTestingMeta,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/dashboard/SettingsView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('@/views/dashboard/MessagesView.vue'),
    meta: productionTestingMeta,
  },
  {
    path: '/message/:id',
    name: 'MessageDetail',
    component: () => import('@/views/dashboard/MessageDetailView.vue'),
    meta: productionTestingMeta,
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

function defaultAuthenticatedPath(): string {
  return '/'
}

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)

  // The login screen must remain usable while the backend is starting or unavailable.
  // An existing in-memory session is still handled by the normal restore path.
  if (to.name === 'Login' && !authStore.initialized) return true

  await authStore.restore()
  if (to.meta.public) {
    if (to.name === 'Login' && authStore.authenticated) {
      const defaultPath = defaultAuthenticatedPath()
      const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : defaultPath
      return redirect.startsWith('/') && !redirect.startsWith('//') && redirect !== '/login' ? redirect : defaultPath
    }
    return true
  }
  if (!authStore.authenticated) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }
  return true
})

function updateDocumentMetadata(to: typeof router.currentRoute.value): void {
  const titleKey = typeof to.meta.titleKey === 'string' ? to.meta.titleKey : 'titles.platform'
  const title = String(i18n.global.t(titleKey))
  const favicon = typeof to.meta.favicon === 'string' ? to.meta.favicon : DEFAULT_FAVICON
  document.title = title

  let faviconLink = document.querySelector<HTMLLinkElement>('#app-favicon')
  if (!faviconLink) {
    faviconLink = document.createElement('link')
    faviconLink.id = 'app-favicon'
    faviconLink.rel = 'icon'
    document.head.appendChild(faviconLink)
  }
  faviconLink.type = favicon.endsWith('.svg') ? 'image/svg+xml' : 'image/png'
  faviconLink.href = favicon
}

router.afterEach((to) => {
  updateDocumentMetadata(to)
})

if (typeof window !== 'undefined') {
  window.addEventListener('production-platform-locale-change', () => {
    updateDocumentMetadata(router.currentRoute.value)
  })
}

export default router
