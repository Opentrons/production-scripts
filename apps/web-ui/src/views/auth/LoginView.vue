<template>
  <main class="login-page">
    <LocaleSwitcher class="login-locale-switcher" variant="surface" />
    <section class="login-visual" aria-hidden="true">
      <img class="login-wordmark" :src="productionsLogo" alt="" />
      <p>Production Testing · Productions Versions</p>
    </section>

    <section class="login-panel">
      <div class="login-form-wrap">
        <img class="login-mobile-wordmark" :src="productionsLogo" alt="Productions" />
        <div class="login-heading">
          <span class="login-heading-icon"><ShieldCheck :size="20" aria-hidden="true" /></span>
          <div>
            <p>{{ t('auth.login.secureAccess') }}</p>
            <h1>{{ t('auth.login.title') }}</h1>
          </div>
        </div>

        <form class="login-form" @submit.prevent="submit">
          <label>
            <span>{{ t('auth.login.account') }}</span>
            <div class="login-input">
              <UserRound :size="18" aria-hidden="true" />
              <input
                ref="usernameInput"
                v-model.trim="username"
                name="username"
                autocomplete="username"
                maxlength="64"
                :placeholder="t('auth.login.accountPlaceholder')"
                :disabled="submitting"
                required
              />
            </div>
          </label>

          <label>
            <span>{{ t('auth.login.password') }}</span>
            <div class="login-input">
              <LockKeyhole :size="18" aria-hidden="true" />
              <input
                v-model="password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                maxlength="256"
                :placeholder="t('auth.login.passwordPlaceholder')"
                :disabled="submitting"
                required
              />
              <button type="button" :aria-label="showPassword ? t('auth.login.hidePassword') : t('auth.login.showPassword')" @click="showPassword = !showPassword">
                <EyeOff v-if="showPassword" :size="17" aria-hidden="true" />
                <Eye v-else :size="17" aria-hidden="true" />
              </button>
            </div>
          </label>

          <p v-if="errorMessage" class="login-error" role="alert">
            <CircleAlert :size="16" aria-hidden="true" />
            <span>{{ errorMessage }}</span>
          </p>

          <button class="login-submit" type="submit" :disabled="submitting || !username || !password">
            <LoaderCircle v-if="submitting" class="is-spinning" :size="18" aria-hidden="true" />
            <LogIn v-else :size="18" aria-hidden="true" />
            {{ submitting ? t('auth.login.submitting') : t('auth.login.submit') }}
          </button>
        </form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import axios from 'axios'
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CircleAlert,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  LogIn,
  ShieldCheck,
  UserRound,
} from '@lucide/vue'
import productionsLogo from '@/assets/dashboard/productions-logo.svg'
import { useAuthStore } from '@/scripts/stores/auth'
import { useAppLocale } from '@/i18n'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { t } = useAppLocale()
const usernameInput = ref<HTMLInputElement | null>(null)
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

function safeRedirect(value: unknown): string {
  const defaultPath = '/'
  const path = typeof value === 'string' ? value : defaultPath
  return path.startsWith('/') && !path.startsWith('//') && path !== '/login' ? path : defaultPath
}

async function submit(): Promise<void> {
  if (submitting.value || !username.value || !password.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await authStore.login(username.value, password.value)
    await router.replace(safeRedirect(route.query.redirect))
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined
    if (status === 429) errorMessage.value = t('auth.login.tooManyAttempts')
    else if (status === 503) errorMessage.value = t('auth.login.serviceUnavailable')
    else errorMessage.value = t('auth.login.invalidCredentials')
    password.value = ''
    await nextTick()
  } finally {
    submitting.value = false
  }
}

onMounted(() => usernameInput.value?.focus())
</script>

<style scoped>
.login-page { position: relative; min-height: 100vh; overflow: hidden; display: grid; place-items: center; background: #e9f1f3; color: #182126; }
.login-locale-switcher { position: absolute; z-index: 3; top: 24px; right: 24px; }
.login-visual { position: absolute; inset: 0; overflow: hidden; padding: 42px 54px 34px; pointer-events: none; }
.login-wordmark { width: 215px; height: auto; position: relative; z-index: 2; }
.login-visual > p { position: absolute; bottom: 34px; left: 54px; margin: 0; color: #607078; font-size: 12px; font-weight: 650; }
.login-panel { position: relative; z-index: 2; width: 100%; min-height: 100vh; display: grid; place-items: center; padding: 40px 24px; }
.login-form-wrap { width: min(100%, 410px); padding: 36px; border: 1px solid #d5dfe2; border-radius: 8px; background: rgba(255,255,255,.97); box-shadow: 0 20px 54px rgba(47,66,73,.13); }
.login-mobile-wordmark { display: none; }
.login-heading { display: flex; align-items: center; gap: 13px; margin-bottom: 34px; }
.login-heading-icon { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 6px; background: #e9f4f6; color: #087b91; }
.login-heading p { margin: 0 0 5px; color: #07809a; font-size: 10px; font-weight: 800; }
.login-heading h1 { margin: 0; font-size: 25px; line-height: 1.2; letter-spacing: 0; }
.login-form { display: grid; gap: 21px; }
.login-form label { display: grid; gap: 8px; color: #354249; font-size: 12px; font-weight: 700; }
.login-input { height: 46px; display: flex; align-items: center; gap: 10px; padding: 0 13px; border: 1px solid #cfd9dd; border-radius: 6px; background: #fff; color: #738188; transition: border-color .18s, box-shadow .18s; }
.login-input:focus-within { border-color: #07809a; box-shadow: 0 0 0 3px rgba(7,128,154,.11); color: #07809a; }
.login-input input { min-width: 0; flex: 1; height: 100%; border: 0; outline: 0; background: transparent; color: #182126; font: inherit; font-weight: 500; }
.login-input input::placeholder { color: #a0aaaf; }
.login-input button { width: 30px; height: 30px; display: grid; place-items: center; border: 0; border-radius: 4px; background: transparent; color: #76848a; cursor: pointer; }
.login-input button:hover { background: #eef3f4; color: #334149; }
.login-error { min-width: 0; display: flex; align-items: flex-start; gap: 8px; margin: -3px 0 0; padding: 10px 12px; border-left: 3px solid #c63f3f; background: #fff3f3; color: #9c2f2f; font-size: 12px; line-height: 1.5; }
.login-error svg { flex: 0 0 auto; margin-top: 1px; }
.login-submit { height: 46px; display: flex; align-items: center; justify-content: center; gap: 8px; border: 0; border-radius: 6px; background: #087f96; color: #fff; font-size: 13px; font-weight: 750; cursor: pointer; }
.login-submit:hover:not(:disabled) { background: #066e82; }
.login-submit:disabled { opacity: .58; cursor: not-allowed; }
.is-spinning { animation: login-spin 1s linear infinite; }
@keyframes login-spin { to { transform: rotate(360deg); } }
@media (max-width: 820px) {
  .login-page { display: block; background: #fff; }
  .login-visual { display: none; }
  .login-panel { min-height: 100vh; padding: 32px 24px; align-items: center; }
  .login-form-wrap { padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; }
  .login-mobile-wordmark { display: block; width: 185px; margin-bottom: 48px; }
}
@media (max-width: 420px) { .login-panel { padding: 28px 20px; } .login-heading h1 { font-size: 22px; } }
</style>
