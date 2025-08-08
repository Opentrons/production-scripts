import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import { useAuthStore } from './stores/auth'
import { tr } from 'element-plus/es/locales.mjs'

import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/antd.css' // 引入样式文件


const app = createApp(App)
app.use(router).use(createPinia())
.use(ElementPlus).use(Antd)
.mount('#app')

// token 保持状态
const authStore = useAuthStore()
const token = localStorage.getItem('token')
if (token) {
    authStore.isAuthenticated = true
}
