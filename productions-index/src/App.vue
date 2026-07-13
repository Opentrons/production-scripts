<template>
  <main class="app-shell">
    <section v-if="isDownloadsView" class="downloads-page">
      <header class="topbar page-topbar" aria-label="Productions navigation">
        <a class="brand" href="#/" aria-label="Open Productions Index">
          <span>PRODUCTIONS INDEX</span>
        </a>
        <nav class="top-links" aria-label="Primary modules">
          <a class="top-link" :href="productionsOpentronsBaseUrl">Productions Opentrons</a>
          <a class="top-link is-active" href="#/downloads">Downloads</a>
          <span class="top-link is-disabled" aria-disabled="true">Agent</span>
          <span class="top-link is-disabled" aria-disabled="true">Modules</span>
        </nav>
      </header>

      <section class="downloads-shell" aria-labelledby="downloads-title">
        <div class="downloads-heading resource-page-heading">
          <div>
            <a class="back-link" href="#/">
              <ArrowLeft :size="16" aria-hidden="true" />
              返回 Productions
            </a>
            <p class="eyebrow">FILE RESOURCE LIBRARY</p>
            <h1 id="downloads-title">Downloads</h1>
            <p class="downloads-copy">按项目和版本管理静态文件资源，所有上传信息都会保存在数据库中。</p>
          </div>
          <button class="new-upload-button" type="button" @click="openUploadForm">
            <Plus :size="18" aria-hidden="true" />
            上传新版本
          </button>
        </div>

        <p v-if="notice.message" class="resource-notice" :class="`is-${notice.type}`" role="status">
          {{ notice.message }}
        </p>

        <div class="project-toolbar">
          <div class="project-count">
            <FolderKanban :size="19" aria-hidden="true" />
            <strong>{{ projects.length }}</strong>
            <span>个资源项目</span>
          </div>
          <button class="refresh-button" type="button" :disabled="isLoading" @click="loadProjects">
            <RefreshCw :size="16" :class="{ 'is-spinning': isLoading }" aria-hidden="true" />
            刷新
          </button>
        </div>

        <div v-if="isLoading && !projects.length" class="project-state">
          <RefreshCw class="is-spinning" :size="25" aria-hidden="true" />
          <span>正在加载资源项目…</span>
        </div>
        <div v-else-if="loadError" class="project-state is-error">
          <CircleAlert :size="25" aria-hidden="true" />
          <strong>无法读取文件资源</strong>
          <span>{{ loadError }}</span>
          <button type="button" @click="loadProjects">重试</button>
        </div>
        <div v-else-if="!projects.length" class="project-state empty-project-state">
          <FolderPlus :size="32" aria-hidden="true" />
          <strong>还没有资源项目</strong>
          <span>点击右上角“上传新版本”，创建第一个项目和版本。</span>
          <button type="button" @click="openUploadForm">创建资源项目</button>
        </div>
        <div v-else class="project-list">
          <article v-for="project in projects" :key="project.id" class="project-card">
            <button class="project-card-header" type="button" @click="toggleProject(project.id)">
              <span class="project-folder-icon"><Folder :size="23" aria-hidden="true" /></span>
              <span class="project-card-copy">
                <span class="project-name-row">
                  <strong>{{ project.name }}</strong>
                  <span>{{ project.version_count }} 个版本</span>
                </span>
                <span class="project-description">{{ project.description || '暂无项目描述' }}</span>
              </span>
              <ChevronDown
                :size="20"
                class="project-chevron"
                :class="{ 'is-expanded': expandedProjectIds.has(project.id) }"
                aria-hidden="true"
              />
            </button>

            <div v-if="expandedProjectIds.has(project.id)" class="version-list">
              <div v-if="!project.versions.length" class="empty-version-state">该项目还没有版本。</div>
              <div v-for="resourceVersion in project.versions" :key="resourceVersion.id" class="version-row">
                <div class="version-marker"><Package :size="18" aria-hidden="true" /></div>
                <div class="version-main">
                  <div class="version-title-row">
                    <strong>v{{ resourceVersion.version }}</strong>
                    <span>{{ resourceVersion.filename }}</span>
                  </div>
                  <p>{{ resourceVersion.version_notes || '暂无版本说明' }}</p>
                  <div class="version-meta">
                    <span>{{ formatBytes(resourceVersion.file_size) }}</span>
                    <span>{{ formatDate(resourceVersion.updated_at || resourceVersion.created_at) }}</span>
                  </div>
                </div>
                <div class="version-actions" @click.stop>
                  <button
                    class="more-button"
                    type="button"
                    :aria-label="`管理版本 ${resourceVersion.version}`"
                    :aria-expanded="openMenuVersionId === resourceVersion.id"
                    @click.stop="toggleVersionMenu(resourceVersion.id)"
                  >
                    <MoreHorizontal :size="20" aria-hidden="true" />
                  </button>
                  <div v-if="openMenuVersionId === resourceVersion.id" class="version-menu" role="menu" @click.stop>
                    <a :href="versionDownloadUrl(resourceVersion.id)" role="menuitem" @click="closeVersionMenu">
                      <Download :size="16" aria-hidden="true" />
                      下载文件
                    </a>
                    <button type="button" role="menuitem" @click="openEditForm(resourceVersion)">
                      <Pencil :size="16" aria-hidden="true" />
                      修改版本信息
                    </button>
                    <button class="is-danger" type="button" role="menuitem" @click="deleteVersion(resourceVersion)">
                      <Trash2 :size="16" aria-hidden="true" />
                      删除版本
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div v-if="isFormOpen" class="form-backdrop" role="presentation" @mousedown.self="closeForm">
        <section class="resource-form-dialog" role="dialog" aria-modal="true" :aria-labelledby="formMode === 'upload' ? 'upload-form-title' : 'edit-form-title'">
          <header class="form-dialog-header">
            <div>
              <p class="eyebrow">{{ formMode === 'upload' ? 'NEW RESOURCE VERSION' : 'EDIT VERSION' }}</p>
              <h2 :id="formMode === 'upload' ? 'upload-form-title' : 'edit-form-title'">
                {{ formMode === 'upload' ? '上传文件资源' : '修改版本信息' }}
              </h2>
            </div>
            <button class="dialog-close-button" type="button" aria-label="关闭表单" @click="closeForm">
              <X :size="20" aria-hidden="true" />
            </button>
          </header>

          <form class="resource-form" @submit.prevent="submitForm">
            <template v-if="formMode === 'upload'">
              <label class="form-field">
                <span>项目名称 <em>*</em></span>
                <input
                  v-model="form.projectName"
                  list="resource-project-options"
                  maxlength="120"
                  placeholder="输入新项目名称，或从已有项目中选择"
                  autocomplete="off"
                  required
                  @input="matchExistingProject"
                />
                <datalist id="resource-project-options">
                  <option v-for="project in projects" :key="project.id" :value="project.name" />
                </datalist>
                <small>可自定义项目名称，也可以选择已有项目并为它创建新版本。</small>
              </label>

              <label class="form-field">
                <span>项目描述</span>
                <textarea v-model="form.projectDescription" maxlength="2000" rows="3" placeholder="简单说明项目用途和资源内容"></textarea>
              </label>
            </template>

            <div class="form-grid">
              <label class="form-field">
                <span>版本号 <em>*</em></span>
                <input v-model="form.version" maxlength="80" placeholder="例如：1.0.0" required />
              </label>
              <label v-if="formMode === 'upload'" class="form-field">
                <span>选择文件 <em>*</em></span>
                <input ref="formFileInput" class="native-file-input" type="file" required @change="selectFormFile" />
              </label>
            </div>

            <label class="form-field">
              <span>版本说明</span>
              <textarea v-model="form.versionNotes" maxlength="4000" rows="4" placeholder="记录本版本的更新内容、使用说明或注意事项"></textarea>
            </label>

            <div v-if="formMode === 'upload' && selectedFile" class="selected-file-card">
              <FileArchive :size="20" aria-hidden="true" />
              <div>
                <strong>{{ selectedFile.name }}</strong>
                <span>{{ formatBytes(selectedFile.size) }}</span>
              </div>
              <button type="button" aria-label="移除已选文件" @click="clearSelectedFile"><X :size="16" /></button>
            </div>

            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>

            <div v-if="isSubmitting" class="form-upload-progress">
              <span><i :style="{ width: `${uploadProgress}%` }"></i></span>
              <small>{{ formMode === 'upload' ? `正在上传 ${uploadProgress}%` : '正在保存…' }}</small>
            </div>

            <footer class="form-actions">
              <button class="cancel-button" type="button" :disabled="isSubmitting" @click="closeForm">取消</button>
              <button class="submit-button" type="submit" :disabled="isSubmitting">
                <Upload v-if="formMode === 'upload'" :size="16" aria-hidden="true" />
                <Save v-else :size="16" aria-hidden="true" />
                {{ isSubmitting ? '处理中…' : formMode === 'upload' ? '上传并创建版本' : '保存修改' }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </section>

    <template v-else>
      <section class="hero">
        <header class="topbar" aria-label="Productions navigation">
          <a class="brand" :href="productionsOpentronsBaseUrl" aria-label="Open Productions Opentrons">
            <span>PRODUCTIONS INDEX</span>
          </a>
          <nav class="top-links" aria-label="Primary modules">
            <a class="top-link" :href="productionsOpentronsBaseUrl">Productions Opentrons</a>
            <a class="top-link" href="#/downloads">Downloads</a>
            <span class="top-link is-disabled" aria-disabled="true">Agent</span>
            <span class="top-link is-disabled" aria-disabled="true">Modules</span>
          </nav>
        </header>

        <div class="hero-stage">
          <div class="hero-content">
            <p class="eyebrow">OPENTRONS FACTORY SYSTEMS</p>
            <h1>Productions</h1>
            <p class="hero-copy">
              Factory data, robot operations, upload records, analysis workflows, and automation entry points.
            </p>
            <div class="hero-actions">
              <a class="primary-action" :href="productionsOpentronsBaseUrl">
                <span>Open Productions Opentrons</span>
                <ArrowRight :size="18" aria-hidden="true" />
              </a>
              <a class="secondary-action" href="#modules">
                <span>View Modules</span>
                <Boxes :size="18" aria-hidden="true" />
              </a>
            </div>
          </div>

          <div class="hero-visual">
            <img class="hero-machine" :src="flexImage" alt="Opentrons Flex" />
          </div>
        </div>
      </section>

      <section id="modules" class="module-section" aria-labelledby="modules-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">SYSTEM MAP</p>
            <h2 id="modules-title">Production Modules</h2>
          </div>
        </div>

        <div class="module-grid">
          <article
            v-for="module in modules"
            :key="module.name"
            class="module-card"
            :class="{ 'is-muted': module.status === 'Planned' }"
          >
            <div class="module-icon">
              <component :is="module.icon" :size="22" aria-hidden="true" />
            </div>
            <div class="module-body">
              <div class="module-title-row">
                <h3>{{ module.name }}</h3>
                <span class="status-pill" :class="module.statusClass">{{ module.status }}</span>
              </div>
              <p>{{ module.summary }}</p>
            </div>
            <a v-if="module.href" class="module-action" :href="module.href" :aria-label="`Open ${module.name}`">
              <ExternalLink :size="18" aria-hidden="true" />
            </a>
            <button v-else class="module-action is-disabled" type="button" disabled aria-label="Coming soon">
              <Wrench :size="18" aria-hidden="true" />
            </button>
          </article>
        </div>
      </section>

      <section class="routes-section" aria-labelledby="routes-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">APPLICATION</p>
            <h2 id="routes-title">Productions Opentrons</h2>
          </div>
        </div>

        <div class="route-grid">
          <a v-for="route in productionRoutes" :key="route.label" class="route-tile" :href="route.href">
            <component :is="route.icon" :size="20" aria-hidden="true" />
            <span>{{ route.label }}</span>
            <ArrowRight :size="16" aria-hidden="true" />
          </a>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bot,
  Boxes,
  ChevronDown,
  CircleAlert,
  Database,
  Download,
  ExternalLink,
  Factory,
  FileArchive,
  Folder,
  FolderKanban,
  FolderPlus,
  MessageSquare,
  Monitor,
  MoreHorizontal,
  Package,
  PackageCheck,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Settings,
  Trash2,
  Upload,
  UploadCloud,
  Wrench,
  X,
} from '@lucide/vue'
import flexImage from './assets/flex.png'

interface ResourceVersion {
  id: string
  project_id: string
  version: string
  version_notes: string
  filename: string
  file_size: number
  content_type: string
  created_at: string
  updated_at: string
  download_url: string
}

interface ResourceProject {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
  version_count: number
  versions: ResourceVersion[]
}

const productionsOpentronsBaseUrl = withTrailingSlash(
  import.meta.env.VITE_PRODUCTIONS_OPENTRONS_URL || '/productions-opentrons/',
)
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
const productionAgentUrl = import.meta.env.VITE_PRODUCTION_AGENT_URL || ''
const productionAgentBaseUrl = productionAgentUrl ? withTrailingSlash(productionAgentUrl) : ''

const currentHash = ref(window.location.hash)
const projects = ref<ResourceProject[]>([])
const expandedProjectIds = ref(new Set<string>())
const openMenuVersionId = ref('')
const isLoading = ref(false)
const isFormOpen = ref(false)
const isSubmitting = ref(false)
const formMode = ref<'upload' | 'edit'>('upload')
const editingVersionId = ref('')
const selectedFile = ref<File | null>(null)
const formFileInput = ref<HTMLInputElement | null>(null)
const uploadProgress = ref(0)
const loadError = ref('')
const formError = ref('')
const notice = reactive<{ message: string; type: 'success' | 'error' }>({ message: '', type: 'success' })
const form = reactive({
  projectId: '',
  projectName: '',
  projectDescription: '',
  version: '',
  versionNotes: '',
})

const isDownloadsView = computed(() => currentHash.value.replace(/^#/, '').startsWith('/downloads'))

function withTrailingSlash(value: string): string {
  return value.endsWith('/') ? value : `${value}/`
}

function routeUrl(path: string): string {
  return `${productionsOpentronsBaseUrl}${path.replace(/^\/+/, '')}`
}

function handleHashChange(): void {
  currentHash.value = window.location.hash
  if (isDownloadsView.value) void loadProjects()
}

function handleWindowClick(): void {
  closeVersionMenu()
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  if (isFormOpen.value) closeForm()
  else closeVersionMenu()
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** unitIndex
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return payload.detail || payload.message || `请求失败 (${response.status})`
  } catch {
    return `请求失败 (${response.status})`
  }
}

async function loadProjects(): Promise<void> {
  if (!isDownloadsView.value || isLoading.value) return
  isLoading.value = true
  loadError.value = ''
  try {
    const response = await fetch(`${apiBaseUrl}/file-resources/projects`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await parseError(response))
    const payload = (await response.json()) as { projects: ResourceProject[] }
    projects.value = Array.isArray(payload.projects) ? payload.projects : []
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '未知服务器错误'
  } finally {
    isLoading.value = false
  }
}

function toggleProject(projectId: string): void {
  if (expandedProjectIds.value.has(projectId)) expandedProjectIds.value.delete(projectId)
  else expandedProjectIds.value.add(projectId)
}

function toggleVersionMenu(versionId: string): void {
  openMenuVersionId.value = openMenuVersionId.value === versionId ? '' : versionId
}

function closeVersionMenu(): void {
  openMenuVersionId.value = ''
}

function resetForm(): void {
  form.projectId = ''
  form.projectName = ''
  form.projectDescription = ''
  form.version = ''
  form.versionNotes = ''
  selectedFile.value = null
  editingVersionId.value = ''
  formError.value = ''
  uploadProgress.value = 0
  if (formFileInput.value) formFileInput.value.value = ''
}

function openUploadForm(): void {
  resetForm()
  formMode.value = 'upload'
  isFormOpen.value = true
}

function openEditForm(resourceVersion: ResourceVersion): void {
  closeVersionMenu()
  resetForm()
  formMode.value = 'edit'
  editingVersionId.value = resourceVersion.id
  form.version = resourceVersion.version
  form.versionNotes = resourceVersion.version_notes
  isFormOpen.value = true
}

function closeForm(): void {
  if (isSubmitting.value) return
  isFormOpen.value = false
  resetForm()
}

function matchExistingProject(): void {
  const match = projects.value.find((project) => project.name.trim().toLocaleLowerCase() === form.projectName.trim().toLocaleLowerCase())
  form.projectId = match?.id || ''
  if (match) form.projectDescription = match.description
}

function selectFormFile(event: Event): void {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function clearSelectedFile(): void {
  selectedFile.value = null
  if (formFileInput.value) formFileInput.value.value = ''
}

function versionDownloadUrl(versionId: string): string {
  return `${apiBaseUrl}/file-resources/versions/${encodeURIComponent(versionId)}/download`
}

async function submitForm(): Promise<void> {
  formError.value = ''
  if (!form.version.trim()) {
    formError.value = '请填写版本号。'
    return
  }
  if (formMode.value === 'upload') {
    if (!form.projectName.trim()) {
      formError.value = '请填写或选择项目名称。'
      return
    }
    if (!selectedFile.value) {
      formError.value = '请选择需要上传的文件。'
      return
    }
    await createVersion()
  } else {
    await updateVersion()
  }
}

async function createVersion(): Promise<void> {
  if (!selectedFile.value) return
  isSubmitting.value = true
  uploadProgress.value = 0
  const body = new FormData()
  if (form.projectId) body.append('project_id', form.projectId)
  body.append('project_name', form.projectName.trim())
  body.append('project_description', form.projectDescription.trim())
  body.append('version', form.version.trim())
  body.append('version_notes', form.versionNotes.trim())
  body.append('file', selectedFile.value)

  try {
    const created = await uploadFormData(`${apiBaseUrl}/file-resources/versions`, body)
    const projectId = created.version?.project_id || form.projectId
    isFormOpen.value = false
    notice.type = 'success'
    notice.message = `版本 ${form.version.trim()} 已上传并保存。`
    resetForm()
    await loadProjects()
    if (projectId) expandedProjectIds.value.add(projectId)
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '文件上传失败。'
  } finally {
    isSubmitting.value = false
  }
}

function uploadFormData(url: string, body: FormData): Promise<{ version?: ResourceVersion }> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', url)
    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) uploadProgress.value = Math.min(99, Math.round((event.loaded / event.total) * 100))
    })
    request.addEventListener('load', () => {
      let payload: { detail?: string; version?: ResourceVersion } = {}
      try {
        payload = JSON.parse(request.responseText) as typeof payload
      } catch {
        payload = {}
      }
      if (request.status >= 200 && request.status < 300) {
        uploadProgress.value = 100
        resolve(payload)
      } else reject(new Error(payload.detail || `上传失败 (${request.status})`))
    })
    request.addEventListener('error', () => reject(new Error('无法连接文件资源服务。')))
    request.send(body)
  })
}

async function updateVersion(): Promise<void> {
  isSubmitting.value = true
  try {
    const response = await fetch(`${apiBaseUrl}/file-resources/versions/${encodeURIComponent(editingVersionId.value)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: form.version.trim(), version_notes: form.versionNotes.trim() }),
    })
    if (!response.ok) throw new Error(await parseError(response))
    isFormOpen.value = false
    notice.type = 'success'
    notice.message = '版本信息已更新。'
    resetForm()
    await loadProjects()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '版本信息更新失败。'
  } finally {
    isSubmitting.value = false
  }
}

async function deleteVersion(resourceVersion: ResourceVersion): Promise<void> {
  closeVersionMenu()
  if (!window.confirm(`确定删除版本 ${resourceVersion.version} 和对应文件吗？此操作无法撤销。`)) return
  try {
    const response = await fetch(`${apiBaseUrl}/file-resources/versions/${encodeURIComponent(resourceVersion.id)}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error(await parseError(response))
    notice.type = 'success'
    notice.message = `版本 ${resourceVersion.version} 已删除。`
    await loadProjects()
  } catch (error) {
    notice.type = 'error'
    notice.message = error instanceof Error ? error.message : '删除版本失败。'
  }
}

onMounted(() => {
  window.addEventListener('hashchange', handleHashChange)
  window.addEventListener('click', handleWindowClick)
  window.addEventListener('keydown', handleKeydown)
  if (isDownloadsView.value) void loadProjects()
})

onBeforeUnmount(() => {
  window.removeEventListener('hashchange', handleHashChange)
  window.removeEventListener('click', handleWindowClick)
  window.removeEventListener('keydown', handleKeydown)
})

const modules = [
  {
    name: 'Productions Opentrons',
    status: 'Active',
    statusClass: 'status-active',
    summary: 'Production web app for uploads, robot operations, analysis, messages, and product tracking.',
    href: productionsOpentronsBaseUrl,
    icon: Factory,
  },
  {
    name: 'Production Agent',
    status: productionAgentBaseUrl ? 'Ready' : 'Planned',
    statusClass: productionAgentBaseUrl ? 'status-active' : 'status-planned',
    summary: 'Agent workspace for production automation, assisted operations, and queue-based workflows.',
    href: productionAgentBaseUrl || undefined,
    icon: Bot,
  },
]

const productionRoutes = [
  { label: 'Devices', href: routeUrl('devices'), icon: Monitor },
  { label: 'Test Cases', href: routeUrl('test-cases'), icon: PackageCheck },
  { label: 'Data', href: routeUrl('data'), icon: Database },
  { label: 'Upload Records', href: routeUrl('data/uploads'), icon: UploadCloud },
  { label: 'Product Management', href: routeUrl('data/products'), icon: Boxes },
  { label: 'Analysis', href: routeUrl('data/analysis'), icon: BarChart3 },
  { label: 'Messages', href: routeUrl('messages'), icon: MessageSquare },
  { label: 'Settings', href: routeUrl('settings'), icon: Settings },
]
</script>
