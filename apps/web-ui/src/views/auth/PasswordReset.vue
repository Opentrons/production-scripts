<template>
  <el-button link @click="open = true">{{ t('accounts.reset') }}</el-button>
  <el-dialog v-model="open" :title="t('accounts.reset')" width="min(460px, 95vw)" append-to-body>
    <form class="reset-form" @submit.prevent="confirm">
      <label>{{ t('accounts.email') }}<el-input v-model.trim="email" type="email" autocomplete="username" maxlength="254" required /></label>
      <el-button :disabled="busy || !email || cooldown > 0" @click="send">{{ t('accounts.send') }} {{ cooldown > 0 ? `(${cooldown})` : '' }}</el-button>
      <label>{{ t('accounts.code') }}<el-input v-model="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required /></label>
      <label>{{ t('accounts.newPassword') }}<el-input v-model="password" type="password" autocomplete="new-password" show-password minlength="12" maxlength="256" required /></label>
      <label>{{ t('accounts.repeatPassword') }}<el-input v-model="repeat" type="password" autocomplete="new-password" show-password required /></label>
      <p v-if="message" role="status">{{ message }}</p>
      <el-button native-type="submit" type="primary" :disabled="busy || code.length !== 6 || password.length < 12 || password !== repeat">{{ t('accounts.reset') }}</el-button>
    </form>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { rawAuthTransport } from '@/scripts/api/http'
import { useAppLocale } from '@/i18n'
const { t } = useAppLocale()
const open = ref(false), busy = ref(false)
const email = ref(''), code = ref(''), password = ref(''), repeat = ref(''), message = ref('')
const cooldown = ref(0)
let timer: ReturnType<typeof setInterval> | undefined
onUnmounted(() => clearInterval(timer))
async function send() {
  busy.value = true
  try {
    await rawAuthTransport.post('/auth/password-reset/request', { email: email.value }, { timeout: 30000 })
    message.value = t('accounts.sent')
    cooldown.value = 60
    clearInterval(timer)
    timer = setInterval(() => { if (--cooldown.value <= 0) clearInterval(timer) }, 1000)
  } catch { message.value = t('accounts.sendFailed') } finally { busy.value = false }
}
async function confirm() {
  busy.value = true
  try {
    await rawAuthTransport.post('/auth/password-reset/confirm', { email: email.value, code: code.value, password: password.value })
    message.value = t('accounts.resetDone')
    password.value = ''; repeat.value = ''; code.value = ''
  } catch { message.value = t('accounts.resetFailed') } finally { busy.value = false }
}
</script>
<style scoped>
.reset-form { display: grid; gap: 16px; }
label { display: grid; gap: 8px; }
</style>
