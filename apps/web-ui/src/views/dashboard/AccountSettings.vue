<template>
  <section v-loading="busy" class="accounts">
    <h3>{{ t('accounts.title') }}</h3>
    <p>{{ t('accounts.initialPassword') }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <form @submit.prevent="create">
      <el-input v-model.trim="email" type="email" :placeholder="t('accounts.email')" maxlength="254" required />
      <el-select v-model="role" :aria-label="t('accounts.role')">
        <el-option v-for="r in roles" :key="r" :value="r" :label="t(`accounts.${r}`)" />
      </el-select>
      <el-button native-type="submit" type="primary" :disabled="busy || !email">{{ t('accounts.add') }}</el-button>
    </form>
    <el-table :data="users">
      <el-table-column prop="username" :label="t('accounts.email')" />
      <el-table-column :label="t('accounts.role')">
        <template #default="{ row }">
          <el-select :model-value="row.role" :disabled="busy" @change="(value: string) => changeRole(row, value)">
            <el-option v-if="!roles.includes(row.role)" :value="row.role" :label="row.role" />
            <el-option v-for="r in roles" :key="r" :value="r" :label="t(`accounts.${r}`)" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { createApiClient } from '@/scripts/api/http'
import { useAppLocale } from '@/i18n'
import type { AuthUser } from '@/scripts/api/auth'
const { t } = useAppLocale()
const api = createApiClient()
const roles = ['admin', 'engineer', 'operator', 'guest']
const users = ref<AuthUser[]>([])
const email = ref('')
const role = ref('operator')
const busy = ref(false)
const error = ref('')
async function run(action: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try { await action() } catch { error.value = t('accounts.failed') }
  finally { busy.value = false }
}
async function load() { users.value = (await api.get<AuthUser[]>('/auth/accounts')).data }
async function create() {
  await run(async () => { await api.post('/auth/accounts', { email: email.value, role: role.value }); email.value = ''; await load() })
}
async function changeRole(user: AuthUser, value: string) {
  try { await ElMessageBox.confirm(t('accounts.roleWarning'), t('accounts.role')) } catch { return }
  await run(async () => { await api.patch(`/auth/accounts/${user.id}`, { role: value }); await load() })
}
onMounted(() => run(load))
</script>
<style scoped>
.accounts { padding: 24px; }
form { display: flex; gap: 12px; margin: 20px 0; flex-wrap: wrap; }
form .el-input { max-width: 360px; }
.el-select { width: 180px; }
p { color: #606266; }
</style>
