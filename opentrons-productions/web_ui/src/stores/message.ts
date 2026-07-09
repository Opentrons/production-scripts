import { defineStore } from 'pinia'
import { ref } from 'vue'
import { messageApi } from '@/api'
import type { MessageItem, MessagesResponse } from '@/types'

export const useMessageStore = defineStore('message', () => {
  const messages = ref<MessageItem[]>([])
  const total = ref(0)
  const unreadCount = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const syncUnreadCountFromMessages = () => {
    unreadCount.value = messages.value.filter((message) => message.new === true).length
  }

  const fetchMessages = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await messageApi.getMessages()
      messages.value = response.data.messages || []
      total.value = response.data.total || 0
      if (typeof response.data.unread_count === 'number') {
        unreadCount.value = response.data.unread_count
      } else {
        syncUnreadCountFromMessages()
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch messages'
    } finally {
      loading.value = false
    }
  }

  const markAsRead = async (messageId: string) => {
    try {
      const message = messages.value.find(m => m._id === messageId)
      const wasUnread = message?.new === true
      await messageApi.markAsRead(messageId)
      if (message) {
        message.new = false
      }
      if (wasUnread) {
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch (e: any) {
      console.error('Failed to mark as read:', e)
    }
  }

  const markAllAsRead = async () => {
    try {
      const response = await messageApi.markAllAsRead()
      if (response.data?.success === false) {
        throw new Error(response.data.error || response.data.message || 'Failed to mark all messages as read')
      }
      messages.value.forEach((message) => {
        message.new = false
      })
      unreadCount.value = 0
      return true
    } catch (e: any) {
      console.error('Failed to mark all messages as read:', e)
      return false
    }
  }

  return {
    messages,
    total,
    unreadCount,
    loading,
    error,
    fetchMessages,
    markAsRead,
    markAllAsRead
  }
})
