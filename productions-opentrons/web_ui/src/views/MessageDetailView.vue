<template>
  <div class="message-detail-view">
    <el-card class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button text @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <span class="header-title">消息详情</span>
        </div>
      </template>
      
      <div v-if="message" class="message-detail">
        <div class="detail-row">
          <span class="label">标题:</span>
          <span class="status-dot" :class="messageDotClass(message)"></span>
          <span class="value title">{{ formatTitle(message) }}</span>
        </div>
        
        <div class="detail-row">
          <span class="label">状态:</span>
          <el-tag :type="message.new === true ? 'danger' : 'success'" size="small">
            {{ message.new === true ? '未读' : '已读' }}
          </el-tag>
        </div>
        
        <div class="detail-row">
          <span class="label">时间:</span>
          <span class="value">{{ formatTime(message.created_at) }}</span>
        </div>
        
        <el-divider />
        
        <div class="content-section">
          <div class="content-label">消息内容:</div>
          <div class="content-text">{{ message.content || '无内容' }}</div>
        </div>
      </div>
      
      <el-empty v-else description="消息不存在" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessageStore } from '@/stores/message'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const messageStore = useMessageStore()

const messageId = computed(() => route.params.id as string)

const message = computed(() => {
  return messageStore.messages.find(m => m._id === messageId.value)
})

const isErrorMessage = (message: any) => {
  const text = `${message?.title || ''} ${message?.content || ''} ${message?.error || ''}`.toLowerCase()
  return text.includes('failed') || text.includes('fail') || text.includes('error') || text.includes('报错') || text.includes('失败')
}

const messageDotClass = (message: any) => {
  return isErrorMessage(message) ? 'error-dot' : 'success-dot'
}

const formatTitle = (message: any) => {
  if (message?.title === 'Upload Successful') return '数据上传成功'
  if (message?.title === 'Upload Failed') return '数据上传失败'
  return message?.title || '无标题'
}

const formatTime = (time: string | undefined): string => {
  if (!time) return ''
  try {
    const date = new Date(time)
    return date.toLocaleString('zh-CN', {
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

onMounted(async () => {
  if (messageStore.messages.length === 0) {
    await messageStore.fetchMessages()
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
