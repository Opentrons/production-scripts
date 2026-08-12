<template>
  <div class="message-detail-view">
    <el-card class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button text @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            {{ t('messages.detail.back') }}
          </el-button>
          <span class="header-title">{{ t('messages.detail.title') }}</span>
        </div>
      </template>
      
      <div v-if="initialLoading || messageStore.loading" class="message-detail-loading">
        <el-icon class="is-loading message-detail-loading-icon"><Loading /></el-icon>
        <span>{{ t('messages.detail.loading') }}</span>
      </div>

      <el-alert
        v-else-if="messageStore.error"
        type="error"
        :closable="false"
        show-icon
        class="message-detail-error"
      >
        <template #title>
          <div class="message-detail-error-content">
            <span>{{ t('messages.detail.loadFailed', { error: messageStore.error }) }}</span>
            <el-button size="small" type="danger" plain :loading="messageStore.loading" @click="retryLoad">
              {{ t('common.actions.retry') }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <div v-else-if="message" class="message-detail">
        <div class="detail-row">
          <span class="label">{{ t('messages.detail.fields.title') }}</span>
          <span class="status-dot" :class="messageDotClass(message)"></span>
          <span class="value title">{{ formatTitle(message) }}</span>
        </div>
        
        <div class="detail-row">
          <span class="label">{{ t('messages.detail.fields.status') }}</span>
          <el-tag :type="message.new === true ? 'danger' : 'success'" size="small">
            {{ message.new === true ? t('messages.detail.unread') : t('messages.detail.read') }}
          </el-tag>
        </div>
        
        <div class="detail-row">
          <span class="label">{{ t('messages.detail.fields.time') }}</span>
          <span class="value">{{ formatTime(message.created_at) }}</span>
        </div>
        
        <el-divider />
        
        <div class="content-section">
          <div class="content-label">{{ t('messages.detail.fields.content') }}</div>
          <div class="content-text">{{ message.content || t('messages.list.noContent') }}</div>
        </div>
      </div>
      
      <el-empty v-else :description="t('messages.detail.missing')" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessageStore } from '@/scripts/stores/message'
import { ArrowLeft, Loading } from '@element-plus/icons-vue'
import { useAppLocale } from '@/i18n'

const route = useRoute()
const router = useRouter()
const messageStore = useMessageStore()
const { locale, t } = useAppLocale()
const initialLoading = ref(true)

const messageId = computed(() => route.params.id as string)

const message = computed(() => {
  return messageStore.messages.find(m => m._id === messageId.value)
})

const isErrorMessage = (message: any) => {
  const text = `${message?.title || ''} ${message?.content || ''} ${message?.error || ''}`.toLowerCase()
  return text.includes('failed') || text.includes('fail') || text.includes('error') || /\u62a5\u9519|\u5931\u8d25/.test(text)
}

const messageDotClass = (message: any) => {
  return isErrorMessage(message) ? 'error-dot' : 'success-dot'
}

const formatTitle = (message: any) => {
  if (message?.title === 'Upload Successful') return t('messages.titles.uploadSuccessful')
  if (message?.title === 'Upload Failed') return t('messages.titles.uploadFailed')
  return message?.title || t('messages.list.untitled')
}

const formatTime = (time: string | undefined): string => {
  if (!time) return ''
  try {
    const date = new Date(time)
    return date.toLocaleString(locale.value, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return time
  }
}

const markAsRead = async () => {
  if (message.value && message.value.new === true) {
    await messageStore.markAsRead(messageId.value)
    message.value.new = false
  }
}

const goBack = async () => {
  await markAsRead()
  router.push('/messages')
}

async function retryLoad() {
  initialLoading.value = true
  try {
    await messageStore.fetchMessages()
  } finally {
    initialLoading.value = false
  }
}

onMounted(async () => {
  try {
    if (messageStore.messages.length === 0) {
      await messageStore.fetchMessages()
    }
  } finally {
    initialLoading.value = false
  }
})
</script>

<style scoped>
.message-detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.detail-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  border-radius: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
}

.message-detail {
  padding: 20px;
}

.message-detail-loading {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #606266;
  font-size: 14px;
}

.message-detail-loading-icon {
  color: #409eff;
  font-size: 22px;
}

.message-detail-error {
  margin: 14px;
}

.message-detail-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.label {
  font-weight: 600;
  color: #606266;
  min-width: 60px;
}

.value {
  color: #303133;
}

.value.title {
  font-size: 18px;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
}

.success-dot {
  background: #67c23a;
}

.error-dot {
  background: #f56c6c;
}

.content-section {
  margin-top: 20px;
}

.content-label {
  font-weight: 600;
  color: #606266;
  margin-bottom: 12px;
}

.content-text {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.8;
  color: #303133;
  font-size: 14px;
}
</style>
