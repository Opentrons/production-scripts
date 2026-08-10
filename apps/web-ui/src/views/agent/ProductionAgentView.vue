<template>
  <div class="agent-page">
    <header class="agent-header">
      <a class="agent-title-block" href="/" aria-label="生产助手，返回生产测试首页">
        <span class="agent-title-icon"><Bot :size="20" aria-hidden="true" /></span>
        <div>
          <h1>生产助手</h1>
          <p class="agent-model-line">
            <i class="agent-status-dot" :class="`is-${connectionState}`" aria-hidden="true"></i>
            <span>Production Agent </span>
          </p>
        </div>
      </a>

      <div class="agent-header-actions">
        <button
          class="agent-icon-button"
          type="button"
          title="清空对话"
          aria-label="清空对话"
          :disabled="messages.length <= 1"
          @click="clearConversation"
        >
          <Trash2 :size="18" aria-hidden="true" />
        </button>
      </div>
    </header>

    <div class="agent-workspace">
      <aside class="agent-rail" aria-label="快捷任务">
        <div class="agent-rail-heading">
          <Sparkles :size="17" aria-hidden="true" />
          <h2>快捷任务</h2>
        </div>
        <div class="agent-shortcuts">
          <button v-for="prompt in quickPrompts" :key="prompt" type="button" @click="selectPrompt(prompt)">
            <span>{{ prompt }}</span>
            <ArrowUpRight :size="15" aria-hidden="true" />
          </button>
        </div>
        <div class="agent-rail-status">
          <i class="agent-status-dot" :class="`is-${connectionState}`" aria-hidden="true"></i>
          <label for="production-agent-model">当前模型</label>
          <div class="agent-model-select">
            <select id="production-agent-model" v-model="selectedModel" aria-label="当前模型">
              <option value="deepseek">DeepSeek</option>
            </select>
            <ChevronDown :size="15" aria-hidden="true" />
          </div>
        </div>
      </aside>

      <main class="agent-conversation">
        <section ref="messageList" class="agent-messages" aria-live="polite">
          <div class="agent-message-list">
            <article
              v-for="item in messages"
              :key="item.id"
              class="agent-message"
              :class="`is-${item.role}`"
            >
              <div class="agent-avatar" aria-hidden="true">
                <User v-if="item.role === 'user'" :size="18" />
                <Bot v-else :size="19" />
              </div>
              <div class="agent-message-content">
                <header>
                  <strong>{{ item.role === 'user' ? '你' : '小创同学' }}</strong>
                  <time>{{ formatTime(item.createdAt) }}</time>
                </header>

                <div v-if="item.pending && !item.content" class="agent-thinking" aria-label="正在生成">
                  <i></i><i></i><i></i>
                </div>
                <p v-else-if="item.role === 'user'" class="agent-user-text">{{ item.content }}</p>
                <div v-else class="agent-markdown" v-html="renderMarkdown(item.content)"></div>

                <footer v-if="item.role === 'assistant' && item.content && !item.pending">
                  <button type="button" :title="copiedMessageId === item.id ? '已复制' : '复制回答'" @click="copyMessage(item)">
                    <Check v-if="copiedMessageId === item.id" :size="14" aria-hidden="true" />
                    <Copy v-else :size="14" aria-hidden="true" />
                    <span>{{ copiedMessageId === item.id ? '已复制' : '复制' }}</span>
                  </button>
                  <span v-if="item.stopped">已停止</span>
                </footer>
              </div>
            </article>
          </div>
        </section>

        <footer class="agent-composer-shell">
          <div v-if="composerNotice" class="agent-composer-notice" role="status">
            <CircleAlert :size="15" aria-hidden="true" />
            <span>{{ composerNotice }}</span>
          </div>
          <div class="agent-composer" :class="{ 'is-focused': composerFocused }">
            <textarea
              ref="composer"
              v-model="draft"
              rows="3"
              maxlength="20000"
              placeholder="输入生产问题..."
              :disabled="streaming"
              @focus="composerFocused = true"
              @blur="composerFocused = false"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.meta.enter.prevent="sendMessage"
              @keydown.ctrl.enter.prevent="sendMessage"
            ></textarea>
            <div class="agent-composer-actions">
              <span>Shift + Enter 换行</span>
              <button
                v-if="streaming"
                class="agent-stop-button"
                type="button"
                title="停止生成"
                aria-label="停止生成"
                @click="stopGeneration"
              >
                <Square :size="15" fill="currentColor" aria-hidden="true" />
              </button>
              <button
                v-else
                class="agent-send-button"
                type="button"
                title="发送消息"
                aria-label="发送消息"
                :disabled="!canSend"
                @click="sendMessage"
              >
                <Send :size="18" aria-hidden="true" />
              </button>
            </div>
          </div>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import {
  ArrowUpRight,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  Copy,
  Send,
  Sparkles,
  Square,
  Trash2,
  User,
} from '@lucide/vue'
import {
  useProductionAgent,
  type AgentChatMessage,
  type AgentChatRole,
} from '@/scripts/modules/agent/useProductionAgent'

interface ConversationMessage {
  id: string
  role: AgentChatRole
  content: string
  createdAt: string
  pending?: boolean
  stopped?: boolean
  welcome?: boolean
}

const STORAGE_KEY = 'production-agent-conversation-v1'
const MAX_STORED_MESSAGES = 30
const quickPrompts = [
  '排查数据上传失败',
  '梳理机器人连接故障',
  '分析 SOP 与 BOM 差异',
  '制定测试异常检查清单',
]

marked.setOptions({ breaks: true, gfm: true })

const { chat, getStatus, stop, streaming } = useProductionAgent()
const messages = ref<ConversationMessage[]>(loadConversation())
const draft = ref('')
const messageList = ref<HTMLElement | null>(null)
const composer = ref<HTMLTextAreaElement | null>(null)
const composerFocused = ref(false)
const modelName = ref('')
const selectedModel = ref('deepseek')
const connectionState = ref<'loading' | 'ready' | 'unconfigured' | 'unavailable'>('loading')
const copiedMessageId = ref('')
let copyResetTimer: ReturnType<typeof setTimeout> | undefined
let activeAssistantMessage: ConversationMessage | null = null

const connectionLabel = computed(() => {
  if (connectionState.value === 'ready') return modelName.value || '已连接'
  if (connectionState.value === 'unconfigured') return '模型未配置'
  if (connectionState.value === 'unavailable') return '服务不可用'
  return '连接中'
})

const composerNotice = computed(() => {
  if (connectionState.value === 'unconfigured') return '后端未配置 PRODUCTION_PLATFORM_LLM_API_KEY'
  if (connectionState.value === 'unavailable') return '暂时无法读取助手状态，仍可尝试发送消息'
  return ''
})

const canSend = computed(() => (
  Boolean(draft.value.trim())
  && !streaming.value
  && connectionState.value !== 'unconfigured'
))

function createWelcomeMessage(): ConversationMessage {
  return {
    id: 'welcome',
    role: 'assistant',
    content: '你好，我是小创同学。今天需要处理哪项生产问题？',
    createdAt: new Date().toISOString(),
    welcome: true,
  }
}

function loadConversation(): ConversationMessage[] {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return [createWelcomeMessage()]
    const stored = JSON.parse(raw) as ConversationMessage[]
    const valid = stored.filter(item => (
      (item.role === 'user' || item.role === 'assistant')
      && typeof item.content === 'string'
      && typeof item.createdAt === 'string'
    ))
    return valid.length ? [createWelcomeMessage(), ...valid.slice(-MAX_STORED_MESSAGES)] : [createWelcomeMessage()]
  } catch {
    return [createWelcomeMessage()]
  }
}

function persistConversation(): void {
  try {
    const stored = messages.value
      .filter(item => !item.welcome && !item.pending && item.content.trim())
      .slice(-MAX_STORED_MESSAGES)
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  } catch {
    // Conversation remains usable when browser storage is unavailable.
  }
}

function messageId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function buildHistory(): AgentChatMessage[] {
  return messages.value
    .filter(item => !item.welcome && !item.pending && item.content.trim())
    .slice(-30)
    .map(item => ({ role: item.role, content: item.content }))
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  return DOMPurify.sanitize(marked.parse(content) as string)
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

async function scrollToBottom(behavior: ScrollBehavior = 'smooth'): Promise<void> {
  await nextTick()
  const element = messageList.value
  if (!element) return
  element.scrollTo({ top: element.scrollHeight, behavior })
}

function waitNextFrame(): Promise<void> {
  return new Promise(resolve => requestAnimationFrame(() => resolve()))
}

function selectPrompt(prompt: string): void {
  draft.value = prompt
  void nextTick(() => composer.value?.focus())
}

function clearConversation(): void {
  if (streaming.value) stopGeneration()
  messages.value = [createWelcomeMessage()]
  draft.value = ''
  persistConversation()
}

async function copyMessage(item: ConversationMessage): Promise<void> {
  try {
    await navigator.clipboard.writeText(item.content)
    copiedMessageId.value = item.id
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => { copiedMessageId.value = '' }, 1600)
  } catch {
    copiedMessageId.value = ''
  }
}

function stopGeneration(): void {
  stop()
  if (activeAssistantMessage) {
    activeAssistantMessage.pending = false
    activeAssistantMessage.stopped = true
    if (!activeAssistantMessage.content) activeAssistantMessage.content = '已停止生成。'
  }
  persistConversation()
}

async function sendMessage(): Promise<void> {
  const content = draft.value.trim()
  if (!content || !canSend.value) return

  messages.value.push({
    id: messageId(),
    role: 'user',
    content,
    createdAt: new Date().toISOString(),
  })
  draft.value = ''

  const assistantMessage: ConversationMessage = {
    id: messageId(),
    role: 'assistant',
    content: '',
    createdAt: new Date().toISOString(),
    pending: true,
  }
  messages.value.push(assistantMessage)
  activeAssistantMessage = assistantMessage
  await scrollToBottom()

  let streamingText = ''
  let finalContent = ''
  let streamError = ''
  await chat(
    buildHistory(),
    '当前页面：生产助手',
    {
      async onChunk(chunk) {
        streamingText += chunk
        assistantMessage.content = streamingText
        await nextTick()
        await waitNextFrame()
        await scrollToBottom('auto')
      },
      async onDone(content) {
        finalContent = content || streamingText
        if (!assistantMessage.stopped && finalContent) {
          assistantMessage.content = finalContent
          assistantMessage.pending = false
          await nextTick()
          await waitNextFrame()
          await scrollToBottom('auto')
        }
      },
      onError(message) {
        streamError = message
      },
    },
  )

  if (streamError) {
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n> 请求中断：${streamError}`
      : `请求失败：${streamError}`
  } else if (!assistantMessage.stopped) {
    assistantMessage.content = finalContent || streamingText
  }

  if (activeAssistantMessage === assistantMessage) activeAssistantMessage = null
  assistantMessage.pending = false
  if (!assistantMessage.content) assistantMessage.content = '模型未返回内容。'
  persistConversation()
  await scrollToBottom()
}

async function loadAgentStatus(): Promise<void> {
  connectionState.value = 'loading'
  try {
    const status = await getStatus()
    modelName.value = status.model
    connectionState.value = status.configured ? 'ready' : 'unconfigured'
  } catch {
    connectionState.value = 'unavailable'
  }
}

onMounted(() => {
  void loadAgentStatus()
  void scrollToBottom('auto')
})

onBeforeUnmount(() => {
  if (streaming.value) stop()
  if (copyResetTimer) clearTimeout(copyResetTimer)
})
</script>

<style scoped>
.agent-page {
  --agent-ink: #19211f;
  --agent-muted: #63706c;
  --agent-line: #dce4df;
  --agent-green: #176b5f;
  --agent-amber: #b96f18;
  display: flex;
  min-width: 0;
  height: 100vh;
  flex-direction: column;
  overflow: hidden;
  color: var(--agent-ink);
  background: #f3f6f4;
}

.agent-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  min-height: 64px;
  padding: 0 22px;
  border-bottom: 1px solid var(--agent-line);
  background: rgba(255, 255, 255, 0.96);
}

.agent-title-block {
  display: flex;
  width: fit-content;
  align-items: center;
  gap: 10px;
  color: inherit;
  text-decoration: none;
}

.agent-title-block:hover h1 { color: var(--agent-green); }

.agent-title-icon {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid #acd0c7;
  border-radius: 8px;
  color: var(--agent-green);
  background: #e3f0ec;
}

.agent-title-block h1 {
  margin: 0;
  color: var(--agent-ink);
  font-size: 16px;
  line-height: 1.25;
  font-weight: 760;
  letter-spacing: 0;
}

.agent-model-line {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
  margin: 2px 0 0;
  color: #7a8682;
  font-size: 11px;
  letter-spacing: 0;
  white-space: nowrap;
}

.agent-status-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: #9aa5a1;
}

.agent-status-dot.is-ready { background: #28a071; }
.agent-status-dot.is-unconfigured { background: var(--agent-amber); }
.agent-status-dot.is-unavailable { background: #c34d4d; }
.agent-status-dot.is-loading { animation: agent-pulse 1.2s ease-in-out infinite; }

.agent-header-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}

.agent-icon-button,
.agent-send-button,
.agent-stop-button {
  display: inline-grid;
  place-items: center;
  border: 0;
  cursor: pointer;
}

.agent-icon-button {
  width: 34px;
  height: 34px;
  border: 1px solid var(--agent-line);
  border-radius: 6px;
  color: #65736f;
  background: #ffffff;
}

.agent-icon-button:hover { color: #a43f3f; border-color: #deb9b9; }
.agent-icon-button:disabled { opacity: 0.38; cursor: default; }

.agent-workspace {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  grid-template-columns: 248px minmax(0, 1fr);
}

.agent-rail {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: 24px 16px 18px;
  border-right: 1px solid var(--agent-line);
  background: #edf2ef;
}

.agent-rail-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px 12px;
  color: var(--agent-green);
}

.agent-rail-heading h2 {
  margin: 0;
  color: #32413d;
  font-size: 13px;
  font-weight: 760;
  letter-spacing: 0;
}

.agent-shortcuts {
  display: grid;
  gap: 6px;
}

.agent-shortcuts button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 16px;
  align-items: center;
  gap: 8px;
  min-height: 46px;
  padding: 9px 10px 9px 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #3d4b47;
  background: transparent;
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}

.agent-shortcuts button:hover,
.agent-shortcuts button:focus-visible {
  outline: none;
  border-color: #bed3cc;
  color: #104f47;
  background: #ffffff;
}

.agent-shortcuts button svg { color: #87938f; }

.agent-rail-status {
  display: grid;
  grid-template-columns: 6px minmax(0, 1fr);
  align-items: center;
  column-gap: 6px;
  row-gap: 6px;
  margin-top: auto;
  padding: 14px 8px 0;
  border-top: 1px solid #d7e0db;
}

.agent-rail-status > .agent-status-dot {
  grid-column: 1;
}

.agent-rail-status label {
  grid-column: 2;
  min-width: 0;
  color: #7c8985;
  font-size: 11px;
  white-space: nowrap;
}

.agent-model-select {
  position: relative;
  grid-column: 1 / -1;
  min-width: 0;
}

.agent-model-select select {
  width: 100%;
  height: 36px;
  appearance: none;
  padding: 0 32px 0 10px;
  border: 1px solid #cbd7d1;
  border-radius: 6px;
  outline: none;
  color: #33413d;
  background: #ffffff;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.agent-model-select select:focus {
  border-color: #6ba89b;
  box-shadow: 0 0 0 3px rgba(23, 107, 95, 0.09);
}

.agent-model-select svg {
  position: absolute;
  top: 50%;
  right: 10px;
  color: #74827e;
  pointer-events: none;
  transform: translateY(-50%);
}

.agent-conversation {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: minmax(0, 1fr) auto;
  background: #f7f9f8;
}

.agent-messages {
  min-height: 0;
  overflow-y: auto;
  padding: 30px 28px 22px;
}

.agent-message-list {
  display: grid;
  width: min(900px, 100%);
  margin: 0 auto;
  gap: 26px;
}

.agent-message {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
}

.agent-message.is-user {
  width: min(720px, 88%);
  margin-left: auto;
  grid-template-columns: minmax(0, 1fr) 36px;
}

.agent-message.is-user .agent-avatar { grid-column: 2; color: #ffffff; background: #2d4558; }
.agent-message.is-user .agent-message-content { grid-column: 1; grid-row: 1; }

.agent-avatar {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid #acd0c7;
  border-radius: 8px;
  color: var(--agent-green);
  background: #e2f0eb;
}

.agent-message-content {
  min-width: 0;
}

.agent-message-content > header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-height: 22px;
}

.agent-message-content > header strong { color: #34413e; font-size: 13px; }
.agent-message-content > header time { color: #929c99; font-size: 10px; }
.agent-message.is-user .agent-message-content > header { justify-content: flex-end; }

.agent-markdown,
.agent-user-text {
  margin: 0;
  color: #25302d;
  font-size: 14px;
  line-height: 1.75;
  letter-spacing: 0;
}

.agent-user-text {
  padding: 11px 14px;
  border: 1px solid #cad9df;
  border-radius: 8px 2px 8px 8px;
  color: #26363c;
  background: #e8f0f3;
  white-space: pre-wrap;
}

.agent-markdown :deep(h1),
.agent-markdown :deep(h2),
.agent-markdown :deep(h3) {
  margin: 16px 0 8px;
  color: #17211e;
  font-weight: 760;
  letter-spacing: 0;
}

.agent-markdown :deep(h1) { font-size: 20px; }
.agent-markdown :deep(h2) { font-size: 17px; }
.agent-markdown :deep(h3) { font-size: 15px; }
.agent-markdown :deep(p) { margin: 0 0 10px; }
.agent-markdown :deep(ul), .agent-markdown :deep(ol) { margin: 8px 0 12px; padding-left: 22px; }
.agent-markdown :deep(li) { margin-bottom: 4px; }
.agent-markdown :deep(a) { color: #0f6d83; }
.agent-markdown :deep(strong) { color: #17211e; }
.agent-markdown :deep(code) { padding: 2px 5px; border-radius: 4px; color: #934c16; background: #f5e9dc; font-size: 0.92em; }
.agent-markdown :deep(pre) { overflow-x: auto; margin: 10px 0; padding: 12px; border-radius: 6px; color: #eaf0ed; background: #202a31; }
.agent-markdown :deep(pre code) { padding: 0; color: inherit; background: transparent; }
.agent-markdown :deep(blockquote) { margin: 10px 0; padding: 7px 12px; border-left: 3px solid #d59a4d; color: #5d6865; background: #fbf6ec; }
.agent-markdown :deep(table) { width: 100%; margin: 10px 0; border-collapse: collapse; }
.agent-markdown :deep(th), .agent-markdown :deep(td) { padding: 8px 10px; border: 1px solid #d6dfda; text-align: left; vertical-align: top; }
.agent-markdown :deep(th) { background: #eaf0ed; }

.agent-message-content > footer {
  display: flex;
  min-height: 26px;
  align-items: center;
  gap: 10px;
  margin-top: 5px;
  color: #8b5a28;
  font-size: 11px;
}

.agent-message-content > footer button {
  display: inline-flex;
  min-height: 26px;
  align-items: center;
  gap: 5px;
  padding: 0 7px;
  border: 0;
  border-radius: 4px;
  color: #77827f;
  background: transparent;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.agent-message-content > footer button:hover { color: var(--agent-green); background: #e8f0ed; }

.agent-thinking {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 5px;
}

.agent-thinking i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--agent-green);
  animation: agent-thinking 1s ease-in-out infinite;
}

.agent-thinking i:nth-child(2) { animation-delay: 0.14s; }
.agent-thinking i:nth-child(3) { animation-delay: 0.28s; }

.agent-composer-shell {
  min-width: 0;
  padding: 12px 28px 22px;
  border-top: 1px solid #e2e8e4;
  background: #ffffff;
}

.agent-composer,
.agent-composer-notice {
  width: min(900px, 100%);
  margin: 0 auto;
}

.agent-composer-notice {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  padding: 0 2px 8px;
  color: #995b19;
  font-size: 12px;
}

.agent-composer-notice span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.agent-composer {
  display: grid;
  min-height: 104px;
  grid-template-rows: minmax(58px, auto) 34px;
  border: 1px solid #cbd7d1;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(29, 48, 42, 0.08);
}

.agent-composer.is-focused {
  border-color: #6ba89b;
  box-shadow: 0 0 0 3px rgba(23, 107, 95, 0.09), 0 8px 24px rgba(29, 48, 42, 0.08);
}

.agent-composer textarea {
  width: 100%;
  min-height: 58px;
  resize: none;
  padding: 13px 14px 5px;
  border: 0;
  outline: 0;
  color: #1f2926;
  background: transparent;
  font: inherit;
  font-size: 14px;
  line-height: 1.5;
}

.agent-composer textarea::placeholder { color: #98a29f; }
.agent-composer textarea:disabled { cursor: wait; }

.agent-composer-actions {
  display: flex;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  padding: 0 7px 7px 14px;
}

.agent-composer-actions > span { color: #929c99; font-size: 10px; }

.agent-send-button,
.agent-stop-button {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: #ffffff;
}

.agent-send-button { background: var(--agent-green); }
.agent-send-button:hover { background: #10594f; }
.agent-send-button:disabled { color: #8e9a96; background: #e2e8e5; cursor: default; }
.agent-stop-button { background: #a84747; }
.agent-stop-button:hover { background: #8e3737; }

@keyframes agent-thinking {
  0%, 60%, 100% { opacity: 0.28; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}

@keyframes agent-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

@media (max-width: 760px) {
  .agent-header {
    grid-template-columns: minmax(0, 1fr) auto;
    min-height: 58px;
    padding: 0 12px;
  }

  .agent-title-block { justify-self: start; }
  .agent-title-icon { width: 34px; height: 34px; }
  .agent-model-line span { max-width: 205px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .agent-icon-button { display: none; }

  .agent-workspace {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .agent-rail {
    padding: 8px 10px;
    border-right: 0;
    border-bottom: 1px solid var(--agent-line);
  }

  .agent-rail-heading,
  .agent-rail-status { display: none; }

  .agent-shortcuts {
    display: flex;
    min-width: 0;
    max-width: 100%;
    gap: 7px;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .agent-shortcuts::-webkit-scrollbar { display: none; }
  .agent-shortcuts button { min-width: 190px; min-height: 38px; padding: 7px 9px 7px 11px; background: #ffffff; }
  .agent-messages { padding: 20px 14px 18px; }
  .agent-message-list { gap: 20px; }
  .agent-message.is-user { width: 94%; }
  .agent-composer-shell { padding: 9px 10px 12px; }
  .agent-composer { min-height: 94px; }
  .agent-composer-actions > span { display: none; }
  .agent-composer-actions { justify-content: flex-end; }
  .agent-markdown, .agent-user-text { font-size: 13px; }
}
</style>
