import { createWebHistory, createRouter, RouteRecordRaw} from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes : RouteRecordRaw[] = [

    // { path: '/', name: 'root', meta: {"title": "Opentrons-SZ测试平台"},component: () => import('../views/home/home.vue') },
    // { path: '/login', name: 'login', redirect: '/' },
    // { path: "/index", name: "Index", redirect: "/index/home"},
    {path: '/login', name: "Login", component: () => import('../views/login/LoginView.vue')},
    {path: '/register', name: "Register", component: () => import('../views/login/RegisterView.vue')},
     // 重定向到home
    { 
      path: '/', 
      redirect: '/home'  // 单独的重定向路由
    },
    { 
      path: '/', name: "index", component: () => import('../views/index.vue'), meta: {requiresAuth: true},
      children: [
        {path: 'home', name: "Home", meta: {"title": "Opentrons-SZ测试平台"}, component: () => import('../views/home/home.vue')},
        {path: 'file_handler', name: "FileHandler", component: () => import('../views/files/file_upload_download.vue')},
        {path: "document", name: "Document", component:() => import("../views/document/document.vue")},
        {path: "device/status", name: "device status", component:() => import("../views/device/device_status.vue")},
        {path: "device/online", name: "device online", component:() => import("../views/device/device_online.vue")},
        {path: "/device/control", name: "device control", component:() => import("../views/device/device_control.vue")},
        {path: "test_managment/status", name: "test status", component:() => import("../views/test_manage/test_status.vue")},
        {path: "test_managment/plan", name: "test plan", component:() => import("../views/test_manage/test_plan.vue")},
        {path: "test_managment/test/ot3", name: "test ot3", component:() => import("../views/test_manage/start_test/ot3.vue")},
        {path: "test_managment/test/pipette", name: "test pipette", component:() => import("../views/test_manage/start_test/pipette_1_8 .vue")},
        {path: "test_managment/test/pipette/96ch", name: "test 96 pipette", component:() => import("../views/test_manage/start_test/pipette_96.vue")},
        {path: 'data_analysis', name: "Data Ana", component: () => import('../views/files/data_analysis.vue')},
        {path: '/test_data', name: "Data", component: () => import('../views/test_data/raw_data.vue')},
        


        {path: 'document_detail', name: "Document Detail", component: () => import('../views/document/document_detail.vue')},
        {path: 'data_summary', name: "Data Summary", component: () => import('../views/files/data_summary.vue')},

      ]
    },
 
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router