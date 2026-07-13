import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/HomeView.vue')
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/DevicesView.vue')
  },
  {
    path: '/devices/control',
    name: 'DeviceControl',
    component: () => import('@/views/DeviceControlView.vue')
  },
  {
    path: '/test-cases',
    name: 'TestCases',
    component: () => import('@/views/TestCaseManagementView.vue')
  },
  {
    path: '/test-cases/protocol',
    name: 'ProtocolTests',
    component: () => import('@/views/ProtocolTestView.vue')
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/views/DataView.vue')
  },
  {
    path: '/data/uploads',
    name: 'UploadRecords',
    component: () => import('@/views/UploadRecordsView.vue')
  },
  {
    path: '/data/products',
    name: 'ProductManagement',
    component: () => import('@/views/ProductManagementView.vue')
  },
  {
    path: '/data/analysis',
    name: 'DataAnalysis',
    component: () => import('@/views/PipetteGravAnalysisView.vue')
  },
  {
    path: '/data/analysis/pipette-assembly-qc',
    name: 'PipetteAssemblyQcAnalysis',
    component: () => import('@/views/PipetteAssemblyQcAnalysisView.vue')
  },
  {
    path: '/data/analysis/robot-assembly-qc',
    name: 'RobotAssemblyQcAnalysis',
    component: () => import('@/views/RobotAssemblyQcAnalysisView.vue')
  },
  {
    path: '/data/links',
    name: 'DataLinks',
    component: () => import('@/views/DataLinksView.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue')
  },
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('@/views/MessagesView.vue')
  },
  {
    path: '/message/:id',
    name: 'MessageDetail',
    component: () => import('@/views/MessageDetailView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
