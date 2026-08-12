<template>
  <div class="messages-view">
    <el-card class="message-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">{{ t('messages.list.title') }}</span>
          <div class="header-tools">
            <span class="total-count">{{ t('messages.list.total', { count: messageStore.total }) }}</span>
            <el-button
              size="small"
              :icon="CircleCheck"
              :disabled="messageStore.unreadCount === 0"
              :loading="markingAllRead"
              @click="handleMarkAllAsRead"
            >
              {{ t('messages.list.markAllRead') }}
            </el-button>
            <el-button
              type="primary"
              size="small"
              :icon="Refresh"
              @click="handleRefresh"
              :loading="messageStore.loading"
            >{{ t('messages.list.refresh') }}</el-button>
            <el-tooltip :content="t('messages.list.close')" placement="bottom">
              <button
                class="close-messages-button"
                type="button"
                :aria-label="t('messages.list.close')"
                @click="handleClose"
              >
                <el-icon><Close /></el-icon>
              </button>
            </el-tooltip>
          </div>
        </div>
      </template>

      <div v-if="initialLoading || messageStore.loading" class="messages-loading-state">
        <el-icon class="is-loading messages-loading-icon"><Loading /></el-icon>
        <span>{{ t('messages.list.loading') }}</span>
      </div>

      <el-alert
        v-else-if="messageStore.error"
        type="error"
        :closable="false"
        show-icon
        class="messages-error-alert"
      >
        <template #title>
          <div class="messages-error-content">
            <span>{{ t('messages.list.loadFailed', { error: messageStore.error }) }}</span>
            <el-button size="small" type="danger" plain :loading="messageStore.loading" @click="handleRefresh">
              {{ t('common.actions.retry') }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <el-empty
        v-else-if="messageStore.messages.length === 0"
        :description="t('messages.list.empty')"
      />

      <el-scrollbar v-else height="calc(100vh - 150px)">
        <div class="message-list">
          <div
            v-for="message in messageStore.messages"
            :key="message._id"
            class="message-item"
            :class="{ 'message-read': message.new === false }"
            @click="handleMessageClick(message)"
          >
            <div class="message-header">
              <span class="status-dot" :class="messageDotClass(message)"></span>
              <span class="message-title">{{ formatTitle(message) }}</span>
              <span class="message-time">{{ formatTime(message.created_at) }}</span>
            </div>
            <div class="message-content-preview">
              {{ getContentPreview(message.content) }}
            </div>
          </div>
        </div>
      </el-scrollbar>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Close, Loading, Refresh } from '@element-plus/icons-vue'
import { useMessageStore } from '@/scripts/stores/message'
import type { MessageItem } from '@/scripts/types'
import { useAppLocale } from '@/i18n'

const router = useRouter()
const messageStore = useMessageStore()
const { locale, t } = useAppLocale()
const markingAllRead = ref(false)
const initialLoading = ref(true)

const isErrorMessage = (message: MessageItem) => {
  const text = `${message.title || ''} ${message.content || ''} ${message.error || ''}`.toLowerCase()
  return text.includes('failed') || text.includes('fail') || text.includes('error') || /\u62a5\u9519|\u5931\u8d25/.test(text)
}

const messageDotClass = (message: MessageItem) => {
  return isErrorMessage(message) ? 'error-dot' : 'success-dot'
}

const formatTitle = (message: MessageItem) => {
  if (message.title === 'Upload Successful') return t('messages.titles.uploadSuccessful')
  if (message.title === 'Upload Failed') return t('messages.titles.uploadFailed')
  return message.title || t('messages.list.untitled')
}

const getContentPreview = (content: string | undefined): string => {
  if (!content) return t('messages.list.noContent')
  const maxLength = 120
  return content.length > maxLength ? `${content.substring(0, maxLength)}...` : content
}

const formatTime = (time: string | undefined): string => {
  if (!time) return ''
  const date = new Date(time)
  if (Number.isNaN(date.getTime())) return time
  return date.toLocaleString(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const handleMessageClick = (message: MessageItem) => {
  router.push(`/message/${message._id}`)
}

const handleRefresh = () => {
  messageStore.fetchMessages()
  ElMessage.success(t('messages.list.refreshed'))
}

const handleClose = () => {
  if (window.history.state?.back) {
    router.back()
    return
  }
  router.push('/')
}

const handleMarkAllAsRead = async () => {
  if (messageStore.unreadCount === 0) {
    ElMessage.info(t('messages.list.noUnread'))
    return
  }
  markingAllRead.value = true
  const success = await messageStore.markAllAsRead()
  markingAllRead.value = false
  if (success) {
    ElMessage.success(t('messages.list.markedAllRead'))
  } else {
    ElMessage.error(t('messages.list.markAllReadFailed'))
  }
}

onMounted(async () => {
  try {
    await messageStore.fetchMessages()
  } finally {
    initialLoading.value = false
  }
})
</script>

<style scoped>
.messages-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.message-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  border-radius: 0;
}

.card-header,
.header-tools,
.message-header {
  display: flex;
  align-items: center;
}

.card-header {
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.header-tools {
  gap: 12px;
}

.close-messages-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #606266;
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.close-messages-button:hover {
  background: #f2f3f5;
  color: #303133;
}

.total-count {
  font-size: 14px;
  color: #909399;
}

.messages-loading-state {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #606266;
  font-size: 14px;
}

.messages-loading-icon {
  color: #409eff;
  font-size: 22px;
}

.messages-error-alert {
  margin: 14px;
}

.messages-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.message-list {
  padding: 8px;
}

.message-item {
  padding: 14px 16px;
  margin-bottom: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  cursor: pointer;
}

.message-item:hover {
  border-color: #c6e2ff;
  background: #f5faff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.08);
}

.message-item.message-read {
  background: #f4f4f5;
}

.message-item.message-read:hover {
  background: #eeeeef;
}

.message-header {
  gap: 8px;
  margin-bottom: 8px;
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

.message-title {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}

.message-time {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
}

.message-content-preview {
  padding-left: 16px;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
