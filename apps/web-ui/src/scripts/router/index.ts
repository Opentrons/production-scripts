import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Platform',
    component: () => import('@/views/dashboard/DashboardView.vue'),
    props: { mode: 'dashboard' },
    meta: { standalone: true },
  },
  {
    path: '/downloads',
    name: 'Downloads',
    component: () => import('@/views/dashboard/DashboardView.vue'),
    props: { mode: 'downloads' },
    meta: { standalone: true },
  },
  {
    path: '/versions',
    name: 'Versions',
    component: () => import('@/views/version_modules/WorkflowManagementView.vue'),
    meta: { standalone: true },
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/dashboard/HomeView.vue'),
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/devices/DevicesView.vue'),
  },
  {
    path: '/devices/control',
    name: 'DeviceControl',
    component: () => import('@/views/devices/DeviceControlView.vue'),
  },
  {
    path: '/test-cases',
    name: 'TestCases',
    component: () => import('@/views/test_modules/TestCaseManagementView.vue'),
  },
  {
    path: '/test-cases/protocol',
    name: 'ProtocolTests',
    component: () => import('@/views/test_modules/ProtocolTestView.vue'),
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/views/data/DataView.vue'),
  },
  {
    path: '/data/uploads',
    name: 'UploadRecords',
    component: () => import('@/views/data/UploadRecordsView.vue'),
  },
  {
    path: '/data/products',
    name: 'ProductManagement',
    component: () => import('@/views/data/ProductManagementView.vue'),
  },
  {
    path: '/data/analysis',
    name: 'DataAnalysis',
    component: () => import('@/views/data/PipetteGravAnalysisView.vue'),
  },
  {
    path: '/data/analysis/pipette-assembly-qc',
    name: 'PipetteAssemblyQcAnalysis',
    component: () => import('@/views/data/PipetteAssemblyQcAnalysisView.vue'),
  },
  {
    path: '/data/analysis/robot-assembly-qc',
    name: 'RobotAssemblyQcAnalysis',
    component: () => import('@/views/data/RobotAssemblyQcAnalysisView.vue'),
  },
  {
    path: '/data/links',
    name: 'DataLinks',
    component: () => import('@/views/data/DataLinksView.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/dashboard/SettingsView.vue'),
  },
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('@/views/dashboard/MessagesView.vue'),
  },
  {
    path: '/message/:id',
    name: 'MessageDetail',
    component: () => import('@/views/dashboard/MessageDetailView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

export default router
