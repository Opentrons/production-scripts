import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

async function clearLegacyFrontendCaches() {
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations()
    await Promise.all(registrations.map((registration) => registration.unregister()))
  }

  if ('caches' in window) {
    const cacheNames = await caches.keys()
    await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)))
  }
}

clearLegacyFrontendCaches().catch(() => undefined)

createApp(App).mount('#app')
