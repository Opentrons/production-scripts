<template>
  <div class="agent-page">
    <header class="agent-header">
      <a class="agent-title-block" href="/" :aria-label="t('agent.homeAria')">
        <span class="agent-title-icon"><Bot :size="24" :stroke-width="2.2" aria-hidden="true" /></span>
        <div>
          <h1>{{ t('agent.title') }}</h1>
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
          :title="t('agent.clear')"
          :aria-label="t('agent.clear')"
          :disabled="messages.length <= 1"
          @click="clearConversation"
        >
          <Trash2 :size="18" aria-hidden="true" />
        </button>
        <AuthUserMenu />
      </div>
    </header>

    <div class="agent-workspace">
      <aside class="agent-rail" :aria-label="t('agent.quickTasks')">
        <div class="agent-rail-heading">
          <Sparkles :size="17" aria-hidden="true" />
          <h2>{{ t('agent.quickTasks') }}</h2>
        </div>
        <div
          class="agent-shortcuts"
          @scroll="hideShortcutTooltip"
        >
          <button
            v-for="prompt in quickPrompts"
            :key="prompt"
            type="button"
            :aria-label="prompt"
            :disabled="streaming || connectionState === 'unconfigured'"
            @mouseenter="showShortcutTooltip($event, prompt)"
            @mouseleave="hideShortcutTooltip"
            @focus="showShortcutTooltip($event, prompt)"
            @blur="hideShortcutTooltip"
            @click="sendMessage(prompt)"
          >
            <span>{{ truncatePrompt(prompt) }}</span>
            <ArrowUpRight :size="15" aria-hidden="true" />
          </button>
        </div>
        <div class="agent-rail-status">
          <i class="agent-status-dot" :class="`is-${connectionState}`" aria-hidden="true"></i>
          <label for="production-agent-model">{{ t('agent.currentModel') }}</label>
          <div class="agent-model-select">
            <select id="production-agent-model" v-model="selectedModel" :aria-label="t('agent.currentModel')">
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
                  <strong>{{ t(item.role === 'user' ? 'agent.you' : 'agent.assistant') }}</strong>
                  <time>{{ formatTime(item.createdAt) }}</time>
                </header>

                <details
                  v-if="item.toolActivities?.length"
                  class="agent-think"
                  :class="{ 'has-error': hasFailedTool(item.toolActivities) }"
                >
                  <summary>
                    <LoaderCircle
                      v-if="hasRunningTool(item.toolActivities)"
                      :size="14"
                      class="is-spinning"
                      aria-hidden="true"
                    />
                    <CircleAlert
                      v-else-if="hasFailedTool(item.toolActivities)"
                      :size="14"
                      aria-hidden="true"
                    />
                    <CircleCheck v-else :size="14" aria-hidden="true" />
                    <strong>{{ t('agent.thinking') }}</strong>
                    <span>{{ toolSummary(item.toolActivities) }}</span>
                    <ChevronDown :size="14" class="agent-think-chevron" aria-hidden="true" />
                  </summary>
                  <div class="agent-tool-list" :aria-label="t('agent.toolRecords')">
                    <div
                      v-for="activity in item.toolActivities"
                      :key="activity.id"
                      class="agent-tool-item"
                      :class="`is-${activity.status}`"
                    >
                      <LoaderCircle v-if="activity.status === 'running'" :size="14" class="is-spinning" aria-hidden="true" />
                      <CircleCheck v-else-if="activity.status === 'success'" :size="14" aria-hidden="true" />
                      <CircleAlert v-else :size="14" aria-hidden="true" />
                      <span class="agent-tool-name">
                        <span>{{ toolDisplayName(activity.name) }}</span>
                        <code>{{ activity.name }}</code>
                      </span>
                      <small v-if="activity.status === 'running'">{{ t('agent.running') }}</small>
                      <small v-else-if="activity.status === 'success'">{{ activity.durationMs ? `${activity.durationMs} ms` : t('agent.completed') }}</small>
                      <small v-else :title="activity.error">{{ t('agent.failed') }}</small>
                    </div>
                  </div>
                </details>

                <div
                  v-if="item.pending && !item.content && !item.toolActivities?.length"
                  class="agent-thinking"
                  :aria-label="t('agent.generating')"
                >
                  <i></i><i></i><i></i>
                </div>
                <template v-else-if="item.role === 'user'">
                  <p class="agent-user-text">{{ item.displayContent || item.content }}</p>
                  <div v-if="item.attachments?.length" class="agent-message-attachments">
                    <span
                      v-for="file in item.attachments"
                      :key="`${item.id}-${file.name}`"
                      class="agent-attachment-chip"
                      :title="file.truncated ? `${file.name} (${t('agent.truncated')})` : file.name"
                    >
                      <Paperclip :size="13" aria-hidden="true" />
                      <span>{{ file.name }}</span>
                      <small>{{ formatBytes(file.size) }}</small>
                    </span>
                  </div>
                </template>
                <div
                  v-else
                  class="agent-markdown"
                  v-html="renderMarkdown(item.content)"
                  @click="onMarkdownClick"
                ></div>

                <footer v-if="item.role === 'assistant' && item.content && !item.pending">
                  <button type="button" :title="t(copiedMessageId === item.id ? 'agent.copied' : 'agent.copyAnswer')" @click="copyMessage(item)">
                    <Check v-if="copiedMessageId === item.id" :size="14" aria-hidden="true" />
                    <Copy v-else :size="14" aria-hidden="true" />
                    <span>{{ t(copiedMessageId === item.id ? 'agent.copied' : 'agent.copy') }}</span>
                  </button>
                  <span v-if="item.stopped">{{ t('agent.stopped') }}</span>
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
          <div
            class="agent-composer"
            :class="{ 'is-focused': composerFocused, 'is-dragging': isDraggingFiles }"
            @dragenter.prevent="onComposerDragEnter"
            @dragover.prevent="onComposerDragOver"
            @dragleave.prevent="onComposerDragLeave"
            @drop.prevent="onComposerDrop"
          >
            <div v-if="pendingAttachments.length" class="agent-pending-attachments">
              <span
                v-for="file in pendingAttachments"
                :key="file.id"
                class="agent-attachment-chip is-pending"
              >
                <Paperclip :size="13" aria-hidden="true" />
                <span>{{ file.name }}</span>
                <small>{{ formatBytes(file.size) }}</small>
                <button
                  type="button"
                  :aria-label="t('agent.removeFile', { name: file.name })"
                  :disabled="streaming"
                  @click="removePendingAttachment(file.id)"
                >
                  <X :size="13" aria-hidden="true" />
                </button>
              </span>
            </div>
            <textarea
              ref="composer"
              v-model="draft"
              rows="3"
              maxlength="20000"
              :placeholder="t('agent.placeholder')"
              :disabled="streaming"
              @focus="composerFocused = true"
              @blur="composerFocused = false"
              @paste="onComposerPaste"
              @keydown.enter.exact.prevent="sendMessage()"
              @keydown.meta.enter.prevent="sendMessage()"
              @keydown.ctrl.enter.prevent="sendMessage()"
            ></textarea>
            <div class="agent-composer-actions">
              <div class="agent-composer-tools">
                <input
                  ref="fileInput"
                  class="agent-file-input"
                  type="file"
                  multiple
                  :accept="ATTACHMENT_ACCEPT"
                  @change="onFileInputChange"
                />
                <button
                  class="agent-attach-button"
                  type="button"
                  :title="t('agent.upload')"
                  :aria-label="t('agent.upload')"
                  :disabled="streaming || connectionState === 'unconfigured'"
                  @click="openFilePicker"
                >
                  <Paperclip :size="16" aria-hidden="true" />
                </button>
                <span>{{ t('agent.attachmentHint') }}</span>
              </div>
              <button
                v-if="streaming"
                class="agent-stop-button"
                type="button"
                :title="t('agent.stop')"
                :aria-label="t('agent.stop')"
                @click="stopGeneration"
              >
                <Square :size="15" fill="currentColor" aria-hidden="true" />
              </button>
              <button
                v-else
                class="agent-send-button"
                type="button"
                :title="t('agent.send')"
                :aria-label="t('agent.send')"
                :disabled="!canSend"
                @click="sendMessage()"
              >
                <Send :size="18" aria-hidden="true" />
              </button>
            </div>
          </div>
        </footer>
      </main>
    </div>
    <div
      v-if="shortcutTooltip.visible"
      class="agent-shortcut-tooltip"
      role="tooltip"
      :style="{ left: `${shortcutTooltip.x}px`, top: `${shortcutTooltip.y}px` }"
    >
      {{ shortcutTooltip.text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import {
  ArrowUpRight,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  CircleCheck,
  Copy,
  LoaderCircle,
  Paperclip,
  Send,
  Sparkles,
  Square,
  Trash2,
  User,
  X,
} from '@lucide/vue'
import {
  useProductionAgent,
  type AgentChatMessage,
  type AgentChatRole,
  type AgentToolEventData,
} from '@/scripts/modules/agent/useProductionAgent'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import { useI18n } from 'vue-i18n'
import { useAppLocale } from '@/i18n'

const { t } = useI18n()
const { locale } = useAppLocale()

interface ConversationMessage {
  id: string
  role: AgentChatRole
  content: string
  displayContent?: string
  createdAt: string
  pending?: boolean
  stopped?: boolean
  welcome?: boolean
  toolActivities?: ToolActivity[]
  attachments?: MessageAttachment[]
}

interface MessageAttachment {
  name: string
  size: number
  truncated?: boolean
}

interface PendingAttachment extends MessageAttachment {
  id: string
  text: string
}

interface ToolActivity {
  id: string
  name: string
  status: 'running' | 'success' | 'error'
  durationMs?: number
  error?: string
}

const STORAGE_KEY = 'production-agent-conversation-v1'
const MAX_STORED_MESSAGES = 30
const TYPEWRITER_INTERVAL_MS = 24
const MAX_ATTACHMENTS = 5
const MAX_ATTACHMENT_BYTES = 512 * 1024
const MAX_ATTACHMENT_CHARS = 24_000
const MAX_MESSAGE_CHARS = 100_000
const ATTACHMENT_EXTENSIONS = new Set([
  'csv', 'tsv', 'txt', 'log', 'json', 'md', 'markdown', 'xml', 'yaml', 'yml', 'ini', 'cfg', 'conf',
])
const ATTACHMENT_ACCEPT = [...ATTACHMENT_EXTENSIONS].map(ext => `.${ext}`).join(',')

const quickPrompts = computed(() => [
  t('agent.prompts.uploads'), t('agent.prompts.devices'), t('agent.prompts.quality'), t('agent.prompts.sop'),
  t('agent.prompts.checkSheet'), t('agent.prompts.editSheet'), t('agent.prompts.attachment'),
  t('agent.prompts.gripperZSpeed'), t('agent.prompts.modulesCount'),
  t('agent.prompts.flexPipettes'), t('agent.prompts.protocolLoadModule'),
  t('agent.prompts.p50mProtocol'),
])

const QUICK_PROMPT_DISPLAY_LIMIT = 30

function truncatePrompt(prompt: string): string {
  const text = prompt.trim()
  if (text.length <= QUICK_PROMPT_DISPLAY_LIMIT) return text
  return `${text.slice(0, QUICK_PROMPT_DISPLAY_LIMIT)}...`
}

const shortcutTooltip = ref({ visible: false, text: '', x: 0, y: 0 })

function showShortcutTooltip(event: FocusEvent | MouseEvent, prompt: string): void {
  const target = event.currentTarget as HTMLElement | null
  if (!target || streaming.value || connectionState.value === 'unconfigured') {
    hideShortcutTooltip()
    return
  }
  const rect = target.getBoundingClientRect()
  const tooltipWidth = Math.min(360, window.innerWidth * 0.42)
  const left = Math.min(rect.right + 10, window.innerWidth - tooltipWidth - 12)
  const top = Math.min(Math.max(rect.top + rect.height / 2, 24), window.innerHeight - 24)
  shortcutTooltip.value = { visible: true, text: prompt, x: left, y: top }
}

function hideShortcutTooltip(): void {
  if (!shortcutTooltip.value.visible) return
  shortcutTooltip.value = { visible: false, text: '', x: 0, y: 0 }
}

const TOOL_NAMES = [
  'get_current_time', 'get_platform_overview', 'query_upload_records', 'analyze_upload_records', 'query_products',
  'query_unit_tracker', 'list_data_links', 'list_test_data_collections', 'query_test_data', 'query_devices',
  'query_version_history', 'query_protocol_monitor', 'query_workflows', 'query_test_cases', 'search_sop_catalog',
  'query_platform_messages', 'query_platform_database', 'aggregate_platform_database', 'get_spreadsheet_info',
  'read_sheet_range', 'create_spreadsheet', 'add_sheet', 'update_sheet_range', 'append_sheet_rows',
  'clear_sheet_range', 'copy_sheet', 'get_opentrons_knowledge_status', 'search_opentrons_official_docs',
  'read_opentrons_official_doc', 'search_opentrons_source', 'read_opentrons_source',
  'search_knowledge', 'list_knowledge', 'save_knowledge', 'delete_knowledge',
] as const

marked.setOptions({ breaks: true, gfm: true })

const COPY_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'
const CHECK_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'
const MARKDOWN_SANITIZE = {
  ADD_TAGS: ['button', 'svg', 'path', 'rect'],
  ADD_ATTR: ['target', 'rel', 'class', 'type', 'aria-label', 'title', 'aria-hidden', 'viewBox', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'width', 'height', 'x', 'y', 'rx', 'ry', 'd'],
}

function enhanceCodeBlocks(html: string): string {
  const copyLabel = t('agent.copyCode')
  return html.replace(/<pre(\b[^>]*)>([\s\S]*?)<\/pre>/gi, (_match, attrs: string, inner: string) => (
    `<div class="agent-code-block">`
    + `<button type="button" class="agent-code-copy" title="${copyLabel}" aria-label="${copyLabel}">${COPY_ICON_SVG}</button>`
    + `<pre${attrs}>${inner}</pre>`
    + `</div>`
  ))
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  return DOMPurify.sanitize(enhanceCodeBlocks(marked.parse(content) as string), MARKDOWN_SANITIZE)
}

const { chat, getStatus, stop, streaming } = useProductionAgent()
const messages = ref<ConversationMessage[]>(loadConversation())
const draft = ref('')
const pendingAttachments = ref<PendingAttachment[]>([])
const messageList = ref<HTMLElement | null>(null)
const composer = ref<HTMLTextAreaElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const composerFocused = ref(false)
const isDraggingFiles = ref(false)
const attachmentError = ref('')
const modelName = ref('')
const selectedModel = ref('deepseek')
const connectionState = ref<'loading' | 'ready' | 'unconfigured' | 'unavailable'>('loading')
const copiedMessageId = ref('')
let copyResetTimer: ReturnType<typeof setTimeout> | undefined
let activeAssistantMessage: ConversationMessage | null = null
let cancelActiveTypewriter: (() => void) | null = null
let dragDepth = 0

const connectionLabel = computed(() => {
  if (connectionState.value === 'ready') return modelName.value || t('agent.status.connected')
  if (connectionState.value === 'unconfigured') return t('agent.status.unconfigured')
  if (connectionState.value === 'unavailable') return t('agent.status.unavailable')
  return t('agent.status.connecting')
})

const composerNotice = computed(() => {
  if (attachmentError.value) return attachmentError.value
  if (connectionState.value === 'unconfigured') return t('agent.status.missingKey')
  if (connectionState.value === 'unavailable') return t('agent.status.unavailableHint')
  return ''
})

const canSend = computed(() => (
  Boolean(draft.value.trim() || pendingAttachments.value.length)
  && !streaming.value
  && connectionState.value !== 'unconfigured'
))

function createWelcomeMessage(): ConversationMessage {
  return {
    id: 'welcome',
    role: 'assistant',
    content: t('agent.welcome'),
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
      .map(item => ({
        id: item.id,
        role: item.role,
        content: item.content,
        displayContent: item.displayContent,
        createdAt: item.createdAt,
        stopped: item.stopped,
        attachments: item.attachments,
      }))
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  } catch {
    // Conversation remains usable when browser storage is unavailable.
  }
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB']
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** unitIndex
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`
}

function fileExtension(name: string): string {
  const parts = name.toLowerCase().split('.')
  return parts.length > 1 ? parts.at(-1) || '' : ''
}

function isSupportedAttachment(file: File): boolean {
  if (ATTACHMENT_EXTENSIONS.has(fileExtension(file.name))) return true
  return Boolean(file.type && (file.type.startsWith('text/') || file.type === 'application/json'))
}

function buildMessageContent(text: string, attachments: PendingAttachment[]): string {
  const sections: string[] = []
  if (text.trim()) sections.push(text.trim())
  for (const file of attachments) {
    const note = file.truncated ? ` (${t('agent.truncated')})` : ''
    sections.push(`${t('agent.attachment.prefix')}: ${file.name}${note}\n\`\`\`\n${file.text}\n\`\`\``)
  }
  return sections.join('\n\n').slice(0, MAX_MESSAGE_CHARS)
}

function setComposerFeedback(message: string): void {
  attachmentError.value = message
  if (!message) return
  window.setTimeout(() => {
    if (attachmentError.value === message) attachmentError.value = ''
  }, 4200)
}

async function readAttachment(file: File): Promise<PendingAttachment> {
  if (!isSupportedAttachment(file)) {
    throw new Error(t('agent.attachment.unsupported', { name: file.name }))
  }
  if (file.size > MAX_ATTACHMENT_BYTES) {
    throw new Error(t('agent.attachment.tooLarge', { name: file.name, size: formatBytes(MAX_ATTACHMENT_BYTES) }))
  }
  const raw = await file.text()
  const truncated = raw.length > MAX_ATTACHMENT_CHARS
  return {
    id: messageId(),
    name: file.name,
    size: file.size,
    truncated,
    text: truncated ? `${raw.slice(0, MAX_ATTACHMENT_CHARS)}\n…` : raw,
  }
}

async function addFiles(fileList: FileList | File[]): Promise<void> {
  const files = Array.from(fileList)
  if (!files.length) return
  const remaining = MAX_ATTACHMENTS - pendingAttachments.value.length
  if (remaining <= 0) {
    setComposerFeedback(t('agent.attachment.max', { count: MAX_ATTACHMENTS }))
    return
  }
  const selected = files.slice(0, remaining)
  try {
    const next = await Promise.all(selected.map(readAttachment))
    pendingAttachments.value = [...pendingAttachments.value, ...next]
    if (files.length > remaining) {
      setComposerFeedback(t('agent.attachment.extrasIgnored', { count: MAX_ATTACHMENTS }))
    }
  } catch (error) {
    setComposerFeedback(error instanceof Error ? error.message : t('agent.attachment.readFailed'))
  }
}

function removePendingAttachment(id: string): void {
  pendingAttachments.value = pendingAttachments.value.filter(item => item.id !== id)
}

function openFilePicker(): void {
  fileInput.value?.click()
}

async function onFileInputChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  await addFiles(input.files || [])
  input.value = ''
}

async function onComposerPaste(event: ClipboardEvent): Promise<void> {
  const files = Array.from(event.clipboardData?.files || [])
  if (!files.length) return
  event.preventDefault()
  await addFiles(files)
}

function onComposerDragEnter(event: DragEvent): void {
  if (!event.dataTransfer?.types.includes('Files')) return
  dragDepth += 1
  isDraggingFiles.value = true
}

function onComposerDragOver(event: DragEvent): void {
  if (!event.dataTransfer?.types.includes('Files')) return
  isDraggingFiles.value = true
}

function onComposerDragLeave(): void {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) isDraggingFiles.value = false
}

async function onComposerDrop(event: DragEvent): Promise<void> {
  dragDepth = 0
  isDraggingFiles.value = false
  await addFiles(event.dataTransfer?.files || [])
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

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
}

async function scrollToBottom(behavior: ScrollBehavior = 'smooth'): Promise<void> {
  await nextTick()
  const element = messageList.value
  if (!element) return
  element.scrollTo({ top: element.scrollHeight, behavior })
}

function toolDisplayName(name: string): string {
  return (TOOL_NAMES as readonly string[]).includes(name) ? t(`agent.tools.${name}`) : name
}

function hasRunningTool(activities: ToolActivity[]): boolean {
  return activities.some(activity => activity.status === 'running')
}

function hasFailedTool(activities: ToolActivity[]): boolean {
  return activities.some(activity => activity.status === 'error')
}

function toolSummary(activities: ToolActivity[]): string {
  const running = [...activities].reverse().find(activity => activity.status === 'running')
  if (running) return t('agent.toolSummary.running', { name: toolDisplayName(running.name) })
  const failures = activities.filter(activity => activity.status === 'error').length
  if (failures) return t('agent.toolSummary.failures', { total: activities.length, failures })
  return t('agent.toolSummary.total', { count: activities.length })
}

function wait(milliseconds: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, milliseconds))
}

function createTypewriter(message: ConversationMessage) {
  const queue: string[] = []
  let cancelled = false
  let pumpPromise: Promise<void> | null = null
  let renderCount = 0

  async function pump(): Promise<void> {
    while (!cancelled && queue.length) {
      const batchSize = queue.length > 480 ? 6 : queue.length > 240 ? 4 : queue.length > 80 ? 2 : 1
      message.content += queue.splice(0, batchSize).join('')
      renderCount += 1
      await nextTick()
      if (renderCount % 2 === 0 || queue.length === 0) await scrollToBottom('auto')
      await wait(TYPEWRITER_INTERVAL_MS)
    }
  }

  function start(): void {
    if (cancelled || pumpPromise || queue.length === 0) return
    pumpPromise = pump().finally(() => {
      pumpPromise = null
      if (!cancelled && queue.length) start()
    })
  }

  return {
    enqueue(content: string): void {
      if (!content || cancelled) return
      queue.push(...Array.from(content))
      start()
    },
    async drain(): Promise<void> {
      while (!cancelled && (pumpPromise || queue.length)) {
        start()
        if (pumpPromise) await pumpPromise
      }
    },
    cancel(): void {
      cancelled = true
      queue.length = 0
    },
  }
}

function clearConversation(): void {
  if (streaming.value) stopGeneration()
  messages.value = [createWelcomeMessage()]
  draft.value = ''
  pendingAttachments.value = []
  attachmentError.value = ''
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

async function onMarkdownClick(event: MouseEvent): Promise<void> {
  const target = event.target as HTMLElement | null
  const button = target?.closest('.agent-code-copy') as HTMLButtonElement | null
  if (!button) return
  event.preventDefault()
  const block = button.closest('.agent-code-block')
  const code = block?.querySelector('pre')?.textContent || ''
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    button.classList.add('is-copied')
    button.innerHTML = CHECK_ICON_SVG
    button.title = t('agent.codeCopied')
    button.setAttribute('aria-label', t('agent.codeCopied'))
    window.setTimeout(() => {
      if (!button.isConnected) return
      button.classList.remove('is-copied')
      button.innerHTML = COPY_ICON_SVG
      button.title = t('agent.copyCode')
      button.setAttribute('aria-label', t('agent.copyCode'))
    }, 1600)
  } catch {
    // Clipboard can be unavailable in insecure contexts; keep the UI quiet.
  }
}

function stopGeneration(): void {
  stop()
  cancelActiveTypewriter?.()
  cancelActiveTypewriter = null
  if (activeAssistantMessage) {
    activeAssistantMessage.pending = false
    activeAssistantMessage.stopped = true
    if (!activeAssistantMessage.content) activeAssistantMessage.content = t('agent.stoppedMessage')
  }
  persistConversation()
}

async function sendMessage(quickPrompt?: string): Promise<void> {
  const typed = (quickPrompt ?? draft.value).trim()
  const attachments = [...pendingAttachments.value]
  if ((!typed && !attachments.length) || streaming.value || connectionState.value === 'unconfigured') return

  const displayContent = typed || (attachments.length ? t('agent.attachment.analyze') : '')
  const content = buildMessageContent(displayContent, attachments)
  messages.value.push({
    id: messageId(),
    role: 'user',
    content,
    displayContent,
    createdAt: new Date().toISOString(),
    attachments: attachments.map(file => ({
      name: file.name,
      size: file.size,
      truncated: file.truncated,
    })),
  })
  if (quickPrompt === undefined) draft.value = ''
  pendingAttachments.value = []
  attachmentError.value = ''

  messages.value.push({
    id: messageId(),
    role: 'assistant',
    content: '',
    createdAt: new Date().toISOString(),
    pending: true,
    toolActivities: [],
  })
  const assistantMessage = messages.value[messages.value.length - 1]
  activeAssistantMessage = assistantMessage
  const typewriter = createTypewriter(assistantMessage)
  cancelActiveTypewriter = typewriter.cancel
  await scrollToBottom()

  let receivedText = ''
  let finalContent = ''
  let streamError = ''
  await chat(
    buildHistory(),
    t('agent.pageContext'),
    {
      async onChunk(chunk) {
        receivedText += chunk
        typewriter.enqueue(chunk)
      },
      async onDone(content) {
        finalContent = content || receivedText
        if (!assistantMessage.stopped && finalContent.startsWith(receivedText)) {
          typewriter.enqueue(finalContent.slice(receivedText.length))
        }
        await typewriter.drain()
        if (!assistantMessage.stopped && finalContent && assistantMessage.content !== finalContent) {
          assistantMessage.content = finalContent
        }
        assistantMessage.pending = false
        await scrollToBottom('auto')
      },
      onError(message) {
        streamError = message
      },
      async onToolStart(data: AgentToolEventData) {
        const activities = assistantMessage.toolActivities || (assistantMessage.toolActivities = [])
        activities.push({ id: data.call_id, name: data.name, status: 'running' })
        await nextTick()
        await scrollToBottom('auto')
      },
      async onToolResult(data: AgentToolEventData) {
        const activities = assistantMessage.toolActivities || (assistantMessage.toolActivities = [])
        let activity = activities.find(item => item.id === data.call_id)
        if (!activity) {
          activity = { id: data.call_id, name: data.name, status: data.ok ? 'success' : 'error' }
          activities.push(activity)
        }
        if (activity) {
          activity.status = data.ok ? 'success' : 'error'
          activity.durationMs = data.duration_ms
          activity.error = data.error
        }
        await nextTick()
        await scrollToBottom('auto')
      },
    },
  )

  await typewriter.drain()
  if (streamError) {
    assistantMessage.content = assistantMessage.content
      ? `${assistantMessage.content}\n\n> ${t('agent.interrupted', { error: streamError })}`
      : t('agent.requestFailed', { error: streamError })
  } else if (!assistantMessage.stopped) {
    assistantMessage.content = finalContent || receivedText
  }

  if (cancelActiveTypewriter === typewriter.cancel) cancelActiveTypewriter = null
  if (activeAssistantMessage === assistantMessage) activeAssistantMessage = null
  assistantMessage.pending = false
  if (!assistantMessage.content) assistantMessage.content = t('agent.noContent')
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

watch(locale, () => {
  const welcome = messages.value.find(message => message.welcome)
  if (welcome) welcome.content = t('agent.welcome')
})

onBeforeUnmount(() => {
  hideShortcutTooltip()
  if (streaming.value) stop()
  cancelActiveTypewriter?.()
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
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  place-items: center;
  border-radius: 8px;
  color: #155e52;
  background: #c8f0e4;
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
  flex: 0 0 auto;
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
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding-right: 2px;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.agent-shortcuts button {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 16px;
  align-items: center;
  gap: 8px;
  height: 36px;
  min-height: 36px;
  max-height: 36px;
  flex: 0 0 36px;
  padding: 0 8px 0 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #3d4b47;
  background: transparent;
  font: inherit;
  font-size: 13px;
  line-height: 1.25;
  text-align: left;
  cursor: pointer;
}

.agent-shortcuts button > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-shortcut-tooltip {
  position: fixed;
  z-index: 1200;
  width: max-content;
  max-width: min(360px, 42vw);
  padding: 8px 10px;
  border: 1px solid #c5d4ce;
  border-radius: 8px;
  color: #24332f;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(24, 40, 34, 0.16);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  white-space: normal;
  pointer-events: none;
  transform: translateY(-50%);
}

.agent-shortcuts button:hover,
.agent-shortcuts button:focus-visible {
  outline: none;
  border-color: #bed3cc;
  color: #104f47;
  background: #ffffff;
}

.agent-shortcuts button:disabled {
  opacity: 0.45;
  cursor: default;
}

.agent-shortcuts button svg { color: #87938f; }

.agent-think {
  width: min(100%, 520px);
  margin: 2px 0 10px;
  border: 1px solid #d7e1dc;
  border-radius: 6px;
  color: #53615d;
  background: #f7faf8;
}

.agent-think summary {
  display: grid;
  min-height: 34px;
  grid-template-columns: 16px auto minmax(0, 1fr) 16px;
  align-items: center;
  gap: 7px;
  padding: 6px 9px;
  list-style: none;
  cursor: pointer;
  user-select: none;
}

.agent-think summary::-webkit-details-marker { display: none; }
.agent-think summary:hover { background: #eef5f1; }
.agent-think summary:focus-visible { outline: 2px solid #6ba89b; outline-offset: 2px; }
.agent-think summary strong { color: #34433f; font-size: 12px; letter-spacing: 0; }
.agent-think summary span { min-width: 0; overflow: hidden; color: #74817d; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.agent-think summary > svg:first-child { color: var(--agent-green); }
.agent-think.has-error summary > svg:first-child { color: #a43f3f; }

.agent-think-chevron {
  color: #87938f;
  transition: transform 160ms ease;
}

.agent-think[open] .agent-think-chevron { transform: rotate(180deg); }

.agent-tool-list {
  display: grid;
  padding: 2px 9px 7px 32px;
  border-top: 1px solid #e2e9e5;
}

.agent-tool-item {
  display: grid;
  min-width: 0;
  min-height: 38px;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  padding: 5px 0;
  border-bottom: 1px solid #e4ebe7;
  color: #53615d;
  font-size: 12px;
}

.agent-tool-item:last-child { border-bottom: 0; }
.agent-tool-item.is-success > svg { color: #176b5f; }
.agent-tool-item.is-error > svg { color: #a43f3f; }
.agent-tool-item small { color: #87938f; font-size: 10px; white-space: nowrap; }

.agent-tool-name {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.agent-tool-name > span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-tool-name code { overflow: hidden; color: #8b9692; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }

.is-spinning { animation: agent-spin 0.9s linear infinite; }

@keyframes agent-spin {
  to { transform: rotate(360deg); }
}

.agent-rail-status {
  display: grid;
  flex: 0 0 auto;
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
  padding: 11px 14px;
  border: 1px solid #cad9df;
  border-radius: 8px 2px 8px 8px;
  color: #26363c;
  background: #e8f0f3;
  font-size: 14px;
  line-height: 1.58;
  letter-spacing: 0;
}

.agent-markdown {
  white-space: normal;
}

.agent-user-text {
  white-space: pre-wrap;
}

.agent-message-attachments,
.agent-pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-message-attachments {
  margin-top: 8px;
}

.agent-pending-attachments {
  padding: 8px 12px 0;
}

.agent-composer:has(.agent-pending-attachments) textarea {
  padding-top: 6px;
}

.agent-attachment-chip {
  display: inline-flex;
  max-width: 100%;
  min-height: 28px;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid #c9d8d2;
  border-radius: 6px;
  color: #35534c;
  background: #f3f8f6;
  font-size: 12px;
}

.agent-attachment-chip span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-attachment-chip small {
  color: #7d8b86;
  white-space: nowrap;
}

.agent-attachment-chip.is-pending button {
  display: inline-grid;
  width: 18px;
  height: 18px;
  place-items: center;
  margin-left: 2px;
  border: 0;
  border-radius: 4px;
  color: #6d7a76;
  background: transparent;
  cursor: pointer;
}

.agent-attachment-chip.is-pending button:hover {
  color: #a43f3f;
  background: #f4e4e4;
}

.agent-markdown :deep(h1),
.agent-markdown :deep(h2),
.agent-markdown :deep(h3) {
  margin: 12px 0 5px;
  color: #17211e;
  font-weight: 760;
  line-height: 1.35;
  letter-spacing: 0;
}

.agent-markdown :deep(:first-child) { margin-top: 0; }
.agent-markdown :deep(:last-child) { margin-bottom: 0; }
.agent-markdown :deep(h1) { font-size: 20px; }
.agent-markdown :deep(h2) { font-size: 17px; }
.agent-markdown :deep(h3) { font-size: 15px; }
.agent-markdown :deep(p) { margin: 0 0 5px; }
.agent-markdown :deep(ul), .agent-markdown :deep(ol) { margin: 4px 0 7px; padding-left: 22px; }
.agent-markdown :deep(li) { margin-bottom: 2px; }
.agent-markdown :deep(li:last-child) { margin-bottom: 0; }
.agent-markdown :deep(a) { color: #0f6d83; }
.agent-markdown :deep(strong) { color: #17211e; }
.agent-markdown :deep(code) { padding: 2px 5px; border-radius: 4px; color: #934c16; background: #f5e9dc; font-size: 0.92em; }
.agent-markdown :deep(.agent-code-block) {
  position: relative;
  margin: 7px 0;
}
.agent-markdown :deep(pre) {
  overflow-x: auto;
  margin: 0;
  padding: 12px 40px 12px 12px;
  border-radius: 6px;
  color: #eaf0ed;
  background: #202a31;
  line-height: 1.5;
}
.agent-markdown :deep(pre code) { padding: 0; color: inherit; background: transparent; }
.agent-markdown :deep(.agent-code-copy) {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  display: inline-grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid rgba(234, 240, 237, 0.16);
  border-radius: 6px;
  color: #c5d0cb;
  background: rgba(20, 28, 33, 0.72);
  cursor: pointer;
}
.agent-markdown :deep(.agent-code-copy:hover),
.agent-markdown :deep(.agent-code-copy:focus-visible) {
  color: #ffffff;
  border-color: rgba(234, 240, 237, 0.28);
  background: rgba(36, 48, 55, 0.92);
  outline: none;
}
.agent-markdown :deep(.agent-code-copy.is-copied) {
  color: #7ddea8;
  border-color: rgba(125, 222, 168, 0.35);
}
.agent-markdown :deep(blockquote) { margin: 7px 0; padding: 6px 11px; border-left: 3px solid #d59a4d; color: #5d6865; background: #fbf6ec; }
.agent-markdown :deep(table) { width: 100%; margin: 7px 0; border-collapse: collapse; }
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
  display: flex;
  flex-direction: column;
  min-height: 104px;
  border: 1px solid #cbd7d1;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(29, 48, 42, 0.08);
}

.agent-composer.is-focused {
  border-color: #6ba89b;
  box-shadow: 0 0 0 3px rgba(23, 107, 95, 0.09), 0 8px 24px rgba(29, 48, 42, 0.08);
}

.agent-composer.is-dragging {
  border-color: #6ba89b;
  background: #f4fbf8;
  box-shadow: 0 0 0 3px rgba(23, 107, 95, 0.12), 0 8px 24px rgba(29, 48, 42, 0.08);
}

.agent-composer textarea {
  width: 100%;
  min-height: 58px;
  flex: 1 1 auto;
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
  flex: 0 0 auto;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 7px 7px 8px;
}

.agent-composer-tools {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.agent-composer-tools > span {
  min-width: 0;
  overflow: hidden;
  color: #929c99;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-file-input {
  display: none;
}

.agent-attach-button {
  display: inline-grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border: 1px solid #d2ddd8;
  border-radius: 6px;
  color: #5f6f6a;
  background: #f7faf8;
  cursor: pointer;
}

.agent-attach-button:hover {
  color: var(--agent-green);
  border-color: #9fc4bb;
  background: #eef7f4;
}

.agent-attach-button:disabled {
  opacity: 0.45;
  cursor: default;
}

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
  .agent-title-icon { width: 36px; height: 36px; flex-basis: 36px; }
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
    flex: 0 0 auto;
    flex-direction: row;
    min-width: 0;
    max-width: 100%;
    gap: 7px;
    overflow-x: auto;
    overflow-y: hidden;
    padding-right: 0;
    scrollbar-width: none;
  }

  .agent-shortcuts::-webkit-scrollbar { display: none; }
  .agent-shortcuts button {
    width: 190px;
    min-width: 190px;
    max-width: 190px;
    height: 34px;
    min-height: 34px;
    max-height: 34px;
    flex: 0 0 190px;
    padding: 0 9px 0 11px;
    background: #ffffff;
  }
  .agent-messages { padding: 20px 14px 18px; }
  .agent-message-list { gap: 20px; }
  .agent-message.is-user { width: 94%; }
  .agent-composer-shell { padding: 9px 10px 12px; }
  .agent-composer { min-height: 94px; }
  .agent-composer-tools > span { display: none; }
  .agent-composer-actions { justify-content: space-between; }
  .agent-markdown, .agent-user-text { font-size: 13px; }
}
</style>
