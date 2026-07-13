<template>
  <div class="messages-view">
    <el-card class="message-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">消息列表</span>
          <div class="header-tools">
            <span class="total-count">共 {{ messageStore.total }} 条消息</span>
            <el-button
              size="small"
              :icon="CircleCheck"
              :disabled="messageStore.unreadCount === 0"
              :loading="markingAllRead"
              @click="handleMarkAllAsRead"
            >
              全都已读
            </el-button>
            <el-button type="primary" size="small" @click="handleRefresh" :loading="messageStore.loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-empty
        v-if="!messageStore.loading && messageStore.messages.length === 0"
        description="当前消息为空"
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
import { CircleCheck, Refresh } from '@element-plus/icons-vue'
import { useMessageStore } from '@/stores/message'
import type { MessageItem } from '@/types'

const router = useRouter()
const messageStore = useMessageStore()
const markingAllRead = ref(false)

const isErrorMessage = (message: MessageItem) => {
  const text = `${message.title || ''} ${message.content || ''} ${message.error || ''}`.toLowerCase()
  return text.includes('failed') || text.includes('fail') || text.includes('error') || text.includes('报错') || text.includes('失败')
}

const messageDotClass = (message: MessageItem) => {
  return isErrorMessage(message) ? 'error-dot' : 'success-dot'
}

const formatTitle = (message: MessageItem) => {
  if (message.title === 'Upload Successful') return '数据上传成功'
  if (message.title === 'Upload Failed') return '数据上传失败'
  return message.title || '无标题'
}

const getContentPreview = (content: string | undefined): string => {
  if (!content) return '无内容'
  const maxLength = 120
  return content.length > maxLength ? `${content.substring(0, maxLength)}...` : content
}

const formatTime = (time: string | undefined): string => {
  if (!time) return ''
  const date = new Date(time)
  if (Number.isNaN(date.getTime())) return time
  return date.toLocaleString('zh-CN', {
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
  ElMessage.success('消息已刷新')
}

const handleMarkAllAsRead = async () => {
  if (messageStore.unreadCount === 0) {
    ElMessage.info('暂无未读消息')
    return
  }
  markingAllRead.value = true
  const success = await messageStore.markAllAsRead()
  markingAllRead.value = false
  if (success) {
    ElMessage.success('全部消息已标记为已读')
  } else {
    ElMessage.error('全部已读操作失败')
  }
}

onMounted(() => {
  messageStore.fetchMessages()
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

.total-count {
  font-size: 14px;
  color: #909399;
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
