import { ref } from 'vue'
import { authenticatedFetch } from '@/scripts/api/http'
import { i18n } from '@/i18n'

export type AgentChatRole = 'user' | 'assistant'

export interface AgentChatMessage {
  role: AgentChatRole
  content: string
}

export interface AgentStatus {
  configured: boolean
  model: string
  tool_count: number
  knowledge_count: number
  max_tool_rounds: number
}

export interface AgentToolEventData {
  call_id: string
  name: string
  arguments?: Record<string, unknown>
  ok?: boolean
  duration_ms?: number
  error?: string
}

interface AgentStreamEvent {
  type: 'chunk' | 'done' | 'error' | 'tool_start' | 'tool_result'
  content?: string
  data?: AgentToolEventData
}

interface ChatCallbacks {
  onChunk?: (content: string) => void | Promise<void>
  onDone?: (content: string) => void | Promise<void>
  onError?: (message: string) => void | Promise<void>
  onToolStart?: (data: AgentToolEventData) => void | Promise<void>
  onToolResult?: (data: AgentToolEventData) => void | Promise<void>
}

const AGENT_API_BASE = '/api/agent'

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string | { message?: string }; message?: string }
    return (typeof payload.detail === 'string' ? payload.detail : payload.detail?.message)
      || payload.message
      || i18n.global.t('agent.httpFailed', { status: response.status })
  } catch {
    return i18n.global.t('agent.httpFailed', { status: response.status })
  }
}

export function useProductionAgent() {
  const streaming = ref(false)
  const abortController = ref<AbortController | null>(null)

  async function getStatus(): Promise<AgentStatus> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/status`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as AgentStatus
  }

  async function chat(
    messages: AgentChatMessage[],
    context: string,
    callbacks: ChatCallbacks,
  ): Promise<void> {
    if (streaming.value) return

    const controller = new AbortController()
    abortController.value = controller
    streaming.value = true

    try {
      const response = await authenticatedFetch(`${AGENT_API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages, context }),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error(await responseError(response))
      if (!response.body) throw new Error(i18n.global.t('agent.streamUnsupported'))

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const handleEvent = async (rawEvent: string): Promise<void> => {
        const dataLine = rawEvent
          .split('\n')
          .find(line => line.startsWith('data:'))
        if (!dataLine) return

        let event: AgentStreamEvent
        try {
          event = JSON.parse(dataLine.slice(5).trim()) as AgentStreamEvent
        } catch {
          // Ignore malformed provider events without interrupting the stream.
          return
        }

        if (event.type === 'chunk') await callbacks.onChunk?.(event.content || '')
        else if (event.type === 'done') await callbacks.onDone?.(event.content || '')
        else if (event.type === 'error') await callbacks.onError?.(event.content || i18n.global.t('agent.callFailed'))
        else if (event.type === 'tool_start' && event.data) await callbacks.onToolStart?.(event.data)
        else if (event.type === 'tool_result' && event.data) await callbacks.onToolResult?.(event.data)
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true }).replace(/\r/g, '')

        let eventEnd = buffer.indexOf('\n\n')
        while (eventEnd !== -1) {
          await handleEvent(buffer.slice(0, eventEnd).trim())
          buffer = buffer.slice(eventEnd + 2)
          eventEnd = buffer.indexOf('\n\n')
        }
      }

      buffer += decoder.decode().replace(/\r/g, '')
      const tail = buffer.trim()
      if (tail) await handleEvent(tail)
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        callbacks.onError?.(error instanceof Error ? error.message : i18n.global.t('agent.callFailed'))
      }
    } finally {
      if (abortController.value === controller) {
        streaming.value = false
        abortController.value = null
      }
    }
  }

  function stop(): void {
    abortController.value?.abort()
    abortController.value = null
    streaming.value = false
  }

  return { chat, getStatus, stop, streaming }
}
