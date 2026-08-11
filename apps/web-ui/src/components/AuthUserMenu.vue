<template>
  <div ref="menuRoot" class="auth-user-menu" :class="`is-${variant}`">
    <button
      class="auth-user-trigger"
      type="button"
      :aria-expanded="open"
      aria-label="账户菜单"
      @click.stop="open = !open"
    >
      <span class="auth-user-avatar"><UserRound :size="15" aria-hidden="true" /></span>
      <span class="auth-user-copy">
        <strong>{{ authStore.user?.display_name || authStore.user?.username }}</strong>
      </span>
      <ChevronDown :size="14" aria-hidden="true" />
    </button>
    <div v-if="open" class="auth-user-dropdown" role="menu">
      <div class="auth-user-identity">
        <strong>{{ authStore.user?.display_name || authStore.user?.username }}</strong>
        <span>{{ authStore.user?.username }} · {{ roleLabel }}</span>
      </div>
      <button type="button" role="menuitem" :disabled="loggingOut" @click="logout">
        <LogOut :size="15" aria-hidden="true" />
        {{ loggingOut ? '正在退出' : '退出登录' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, LogOut, UserRound } from '@lucide/vue'
import { useAuthStore } from '@/scripts/stores/auth'

withDefaults(defineProps<{ variant?: 'light' | 'dark' }>(), { variant: 'light' })

const router = useRouter()
const authStore = useAuthStore()
const menuRoot = ref<HTMLElement | null>(null)
const open = ref(false)
const loggingOut = ref(false)

const roleLabel = computed(() => ({
  admin: '管理员',
  operator: '操作员',
  viewer: '访客',
}[authStore.user?.role || 'viewer']))

function closeOnOutsideClick(event: MouseEvent): void {
  if (!menuRoot.value?.contains(event.target as Node)) open.value = false
}

async function logout(): Promise<void> {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await authStore.logout()
    await router.replace({ name: 'Login' })
  } finally {
    loggingOut.value = false
    open.value = false
  }
}

onMounted(() => window.addEventListener('click', closeOnOutsideClick))
onBeforeUnmount(() => window.removeEventListener('click', closeOnOutsideClick))
</script>

<style scoped>
.auth-user-menu { position: relative; flex: 0 0 auto; font-family: inherit; }
.auth-user-trigger { height: 36px; max-width: 190px; display: flex; align-items: center; gap: 7px; padding: 3px 7px 3px 3px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: #243039; cursor: pointer; transition: background .16s, border-color .16s; }
.auth-user-trigger:hover, .auth-user-trigger[aria-expanded="true"] { border-color: #dbe3e6; background: rgba(238,243,245,.9); }
.auth-user-trigger > svg { flex: 0 0 auto; color: #849198; transition: transform .16s; }
.auth-user-trigger[aria-expanded="true"] > svg { transform: rotate(180deg); }
.auth-user-avatar { width: 28px; height: 28px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid #d4e3e8; border-radius: 50%; background: #edf5f7; color: #08789b; }
.auth-user-copy { min-width: 0; display: flex; align-items: center; text-align: left; }
.auth-user-copy strong { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 700; }
.auth-user-dropdown { position: absolute; z-index: 1200; top: calc(100% + 7px); right: 0; width: 190px; padding: 7px; border: 1px solid #d9e0e4; border-radius: 6px; background: #fff; box-shadow: 0 14px 34px rgba(24,38,46,.14); }
.auth-user-identity { display: grid; gap: 3px; padding: 7px 8px 10px; border-bottom: 1px solid #edf0f2; }
.auth-user-identity strong { overflow: hidden; text-overflow: ellipsis; font-size: 12px; }
.auth-user-identity span { overflow: hidden; text-overflow: ellipsis; color: #7a858b; font-size: 10px; }
.auth-user-dropdown button { width: 100%; height: 34px; display: flex; align-items: center; gap: 8px; margin-top: 5px; padding: 0 8px; border: 0; border-radius: 4px; background: transparent; color: #a53232; font-size: 12px; cursor: pointer; }
.auth-user-dropdown button:hover { background: #fff1f1; }
.auth-user-dropdown button:disabled { opacity: .55; cursor: wait; }
.auth-user-menu.is-dark .auth-user-trigger { color: #fff; }
.auth-user-menu.is-dark .auth-user-trigger:hover, .auth-user-menu.is-dark .auth-user-trigger[aria-expanded="true"] { border-color: rgba(255,255,255,.18); background: rgba(255,255,255,.11); }
.auth-user-menu.is-dark .auth-user-trigger > svg { color: rgba(255,255,255,.68); }
.auth-user-menu.is-dark .auth-user-avatar { border-color: rgba(255,255,255,.2); background: rgba(255,255,255,.14); color: #fff; }
@media (max-width: 720px) { .auth-user-copy { display: none; } .auth-user-trigger { width: 38px; padding: 5px; justify-content: center; } .auth-user-trigger > svg { display: none; } }
</style>
