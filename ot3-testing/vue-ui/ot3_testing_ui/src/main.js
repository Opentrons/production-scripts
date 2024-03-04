import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import elementIcon from "./plugins/icons";


const app = createApp(App)
app.use(ElementPlus).use(store).use(router).use(elementIcon)
app.mount('#app')
