import { createWebHistory, createRouter } from 'vue-router'


const routes = [

    { path: '/', name: 'root', component: () => import('../views/login.vue') },
    { path: '/login', name: 'login', redirect: '/' },
    { path: "/index", name: "Index", redirect: "/index/home"},
    { path: '/index', name: "index", component: () => import('../views/index.vue'),
      children: [
        {path: 'home', name: "Home", meta: {"title": "Opentrons-SZ测试平台"}, component: () => import('../views/home/home.vue')},
        {path: 'file_handler', name: "FileHandler", component: () => import('../views/files/file_upload_download.vue')},
        {path: "document", name: "Document", component:() => import("../views/document/document.vue")},
        {path: "device/status", name: "device status", component:() => import("../views/device/device_status.vue")},
        {path: "device/control", name: "device control", component:() => import("../views/device/device_control.vue")},
        {path: "test_managment/status", name: "test status", component:() => import("../views/test_manage/test_status.vue")},
        {path: "test_managment/test/ot3", name: "test ot3", component:() => import("../views/test_manage/start_test/ot3.vue")},
        {path: "test_managment/test/pipette", name: "test pipette", component:() => import("../views/test_manage/start_test/pipette_1_8 .vue")},
        {path: "test_managment/test/pipette/96ch", name: "test 96 pipette", component:() => import("../views/test_manage/start_test/pipette_96.vue")}
      ]
    },
 
]

const router = createRouter({
    history: createWebHistory(),
    routes

})

export default router