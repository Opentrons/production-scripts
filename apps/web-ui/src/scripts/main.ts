import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from '../views/App.vue'
import router from './router'
import { pinia } from './stores'
import { i18n } from '@/i18n'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(i18n)
app.use(router)
app.use(ElementPlus)

void router.isReady().then(() => {
  app.mount('#app')
})
