<template>
  <main class="dashboard-shell">
    <section v-if="isDownloadsView" class="downloads-page">
      <header class="dashboard-topbar page-dashboard-topbar" :aria-label="copy.navigationAria">
        <a class="brand" href="/" :aria-label="copy.brandAria">
          <img class="brand-logo" :src="productionsLogo" alt="Productions" />
        </a>
        <div class="topbar-actions">
          <nav class="top-links" :aria-label="copy.navigationAria">
            <div class="top-dropdown" :class="{ 'is-open': openNavigationMenu === 'product-tests' }">
              <button
                class="top-link top-dropdown-trigger"
                type="button"
                :aria-expanded="openNavigationMenu === 'product-tests'"
                @click.stop="toggleNavigationMenu('product-tests')"
              >
                <Factory class="top-menu-icon" :size="16" aria-hidden="true" />
                <span>{{ copy.nav.productLineTests }}</span>
                <ChevronDown class="top-dropdown-chevron" :size="14" aria-hidden="true" />
              </button>
              <div class="top-dropdown-menu" role="menu" @click.stop>
                <a href="/data/uploads" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                  {{ copy.nav.dataAutomationUpload }}
                </a>
                <div class="top-dropdown-dual" role="group" :aria-label="copy.nav.deviceAndTestManagement">
                  <a href="/devices" target="_blank" rel="noopener noreferrer" @click="closeNavigationMenu">{{ copy.nav.deviceManagement }}</a>
                  <span>&amp;</span>
                  <a href="/test-cases" target="_blank" rel="noopener noreferrer" @click="closeNavigationMenu">{{ copy.nav.testManagement }}</a>
                </div>
                <a href="/data" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                  {{ copy.nav.dataManagement }}
                </a>
              </div>
            </div>
            <div class="top-dropdown" :class="{ 'is-open': openNavigationMenu === 'version-checks' }">
              <button
                class="top-link top-dropdown-trigger"
                type="button"
                :aria-expanded="openNavigationMenu === 'version-checks'"
                @click.stop="toggleNavigationMenu('version-checks')"
              >
                <PackageCheck class="top-menu-icon" :size="16" aria-hidden="true" />
                <span>{{ copy.nav.versionChecks }}</span>
                <ChevronDown class="top-dropdown-chevron" :size="14" aria-hidden="true" />
              </button>
              <div class="top-dropdown-menu is-right" role="menu" @click.stop>
                <a href="/versions?module=sop-duro" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                  {{ copy.nav.sopDuroCheck }}
                </a>
                <a href="/versions?module=ecn" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                  {{ copy.nav.ecnCheck }}
                </a>
              </div>
            </div>
            <a class="top-link" :href="productionAgentBaseUrl" target="_blank" rel="noopener noreferrer">
              <Bot class="top-menu-icon" :size="16" aria-hidden="true" />
              <span>{{ copy.nav.productionAgent }}</span>
            </a>
            <a class="top-link is-active" href="/downloads">
              <Download class="top-menu-icon" :size="16" aria-hidden="true" />
              <span>{{ copy.nav.downloads }}</span>
            </a>
          </nav>
          <div class="language-switcher" role="group" :aria-label="copy.languageLabel">
            <button type="button" :class="{ 'is-active': locale === 'zh' }" :aria-pressed="locale === 'zh'" @click="setLocale('zh')">中文</button>
            <button type="button" :class="{ 'is-active': locale === 'en' }" :aria-pressed="locale === 'en'" @click="setLocale('en')">EN</button>
          </div>
        </div>
      </header>

      <section class="downloads-shell" aria-labelledby="downloads-title">
        <div class="downloads-heading resource-page-heading">
          <div>
            <p class="eyebrow">{{ copy.downloads.eyebrow }}</p>
            <h1 id="downloads-title">{{ copy.downloads.title }}</h1>
            <p class="downloads-copy">{{ copy.downloads.introduction }}</p>
          </div>
          <button class="new-upload-button" type="button" @click="openUploadForm">
            <Plus :size="18" aria-hidden="true" />
            {{ copy.downloads.newUpload }}
          </button>
        </div>

        <p v-if="notice.message" class="resource-notice" :class="`is-${notice.type}`" role="status">
          {{ notice.message }}
        </p>

        <div class="project-toolbar">
          <div class="project-count">
            <FolderKanban :size="19" aria-hidden="true" />
            <span>{{ copy.downloads.projectCount(projects.length) }}</span>
          </div>
          <button class="refresh-button" type="button" :disabled="isLoading" @click="loadProjects">
            <RefreshCw :size="16" :class="{ 'is-spinning': isLoading }" aria-hidden="true" />
            {{ copy.downloads.refresh }}
          </button>
        </div>

        <div v-if="isLoading && !projects.length" class="project-state">
          <RefreshCw class="is-spinning" :size="25" aria-hidden="true" />
          <span>{{ copy.downloads.loading }}</span>
        </div>
        <div v-else-if="loadError" class="project-state is-error">
          <CircleAlert :size="25" aria-hidden="true" />
          <strong>{{ copy.downloads.loadFailed }}</strong>
          <span>{{ loadError }}</span>
          <button type="button" @click="loadProjects">{{ copy.downloads.retry }}</button>
        </div>
        <div v-else-if="!projects.length" class="project-state empty-project-state">
          <FolderPlus :size="32" aria-hidden="true" />
          <strong>{{ copy.downloads.emptyTitle }}</strong>
          <span>{{ copy.downloads.emptyDescription }}</span>
          <button type="button" @click="openUploadForm">{{ copy.downloads.createProject }}</button>
        </div>
        <div v-else class="project-list">
          <article v-for="project in projects" :key="project.id" class="project-card">
            <button class="project-card-header" type="button" @click="toggleProject(project.id)">
              <span class="project-folder-icon"><Folder :size="23" aria-hidden="true" /></span>
              <span class="project-card-copy">
                <span class="project-name-row">
                  <strong>{{ project.name }}</strong>
                  <span>{{ copy.downloads.versionCount(project.version_count) }}</span>
                </span>
                <span class="project-description">{{ project.description || copy.downloads.noProjectDescription }}</span>
              </span>
              <ChevronDown
                :size="20"
                class="project-chevron"
                :class="{ 'is-expanded': expandedProjectIds.has(project.id) }"
                aria-hidden="true"
              />
            </button>

            <div v-if="expandedProjectIds.has(project.id)" class="version-list">
              <div v-if="!project.versions.length" class="empty-version-state">{{ copy.downloads.noVersions }}</div>
              <div v-for="resourceVersion in project.versions" :key="resourceVersion.id" class="version-row">
                <div class="version-marker"><Package :size="18" aria-hidden="true" /></div>
                <div class="version-main">
                  <div class="version-title-row">
                    <strong>v{{ resourceVersion.version }}</strong>
                    <span>{{ resourceVersion.filename }}</span>
                  </div>
                  <p>{{ resourceVersion.version_notes || copy.downloads.noVersionNotes }}</p>
                  <div class="version-meta">
                    <span>{{ formatBytes(resourceVersion.file_size) }}</span>
                    <span>{{ formatDate(resourceVersion.updated_at || resourceVersion.created_at) }}</span>
                  </div>
                </div>
                <div class="version-actions" @click.stop>
                  <button
                    class="more-button"
                    type="button"
                    :aria-label="copy.downloads.manageVersion(resourceVersion.version)"
                    :aria-expanded="openMenuVersionId === resourceVersion.id"
                    @click.stop="toggleVersionMenu(resourceVersion.id)"
                  >
                    <MoreHorizontal :size="20" aria-hidden="true" />
                  </button>
                  <div v-if="openMenuVersionId === resourceVersion.id" class="version-menu" role="menu" @click.stop>
                    <a :href="versionDownloadUrl(resourceVersion.id)" role="menuitem" @click="closeVersionMenu">
                      <Download :size="16" aria-hidden="true" />
                      {{ copy.downloads.downloadFile }}
                    </a>
                    <button type="button" role="menuitem" @click="openEditForm(resourceVersion)">
                      <Pencil :size="16" aria-hidden="true" />
                      {{ copy.downloads.editVersion }}
                    </button>
                    <button class="is-danger" type="button" role="menuitem" @click="deleteVersion(resourceVersion)">
                      <Trash2 :size="16" aria-hidden="true" />
                      {{ copy.downloads.deleteVersion }}
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
              <p class="eyebrow">{{ formMode === 'upload' ? copy.downloads.newVersionEyebrow : copy.downloads.editVersionEyebrow }}</p>
              <h2 :id="formMode === 'upload' ? 'upload-form-title' : 'edit-form-title'">
                {{ formMode === 'upload' ? copy.downloads.uploadTitle : copy.downloads.editTitle }}
              </h2>
            </div>
            <button class="dialog-close-button" type="button" :aria-label="copy.downloads.closeForm" @click="closeForm">
              <X :size="20" aria-hidden="true" />
            </button>
          </header>

          <form class="resource-form" @submit.prevent="submitForm">
            <template v-if="formMode === 'upload'">
              <label class="form-field">
                <span>{{ copy.downloads.projectName }} <em>*</em></span>
                <input
                  v-model="form.projectName"
                  list="resource-project-options"
                  maxlength="120"
                  :placeholder="copy.downloads.projectNamePlaceholder"
                  autocomplete="off"
                  required
                  @input="matchExistingProject"
                />
                <datalist id="resource-project-options">
                  <option v-for="project in projects" :key="project.id" :value="project.name" />
                </datalist>
                <small>{{ copy.downloads.projectNameHelp }}</small>
              </label>

              <label class="form-field">
                <span>{{ copy.downloads.projectDescription }}</span>
                <textarea v-model="form.projectDescription" maxlength="2000" rows="3" :placeholder="copy.downloads.projectDescriptionPlaceholder"></textarea>
              </label>
            </template>

            <div class="form-grid">
              <label class="form-field">
                <span>{{ copy.downloads.version }} <em>*</em></span>
                <input v-model="form.version" maxlength="80" :placeholder="copy.downloads.versionPlaceholder" required />
              </label>
              <label v-if="formMode === 'upload'" class="form-field">
                <span>{{ copy.downloads.selectFile }} <em>*</em></span>
                <input ref="formFileInput" class="native-file-input" type="file" required @change="selectFormFile" />
              </label>
            </div>

            <label class="form-field">
              <span>{{ copy.downloads.versionNotes }}</span>
              <textarea v-model="form.versionNotes" maxlength="4000" rows="4" :placeholder="copy.downloads.versionNotesPlaceholder"></textarea>
            </label>

            <div v-if="formMode === 'upload' && selectedFile" class="selected-file-card">
              <FileArchive :size="20" aria-hidden="true" />
              <div>
                <strong>{{ selectedFile.name }}</strong>
                <span>{{ formatBytes(selectedFile.size) }}</span>
              </div>
              <button type="button" :aria-label="copy.downloads.removeSelectedFile" @click="clearSelectedFile"><X :size="16" /></button>
            </div>

            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>

            <div v-if="isSubmitting" class="form-upload-progress">
              <span><i :style="{ width: `${uploadProgress}%` }"></i></span>
              <small>{{ formMode === 'upload' ? copy.downloads.uploading(uploadProgress) : copy.downloads.saving }}</small>
            </div>

            <footer class="form-actions">
              <button class="cancel-button" type="button" :disabled="isSubmitting" @click="closeForm">{{ copy.downloads.cancel }}</button>
              <button class="submit-button" type="submit" :disabled="isSubmitting">
                <Upload v-if="formMode === 'upload'" :size="16" aria-hidden="true" />
                <Save v-else :size="16" aria-hidden="true" />
                {{ isSubmitting ? copy.downloads.processing : formMode === 'upload' ? copy.downloads.uploadAndCreate : copy.downloads.saveChanges }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </section>

    <template v-else>
      <section class="hero">
        <header class="dashboard-topbar" :aria-label="copy.navigationAria">
          <a class="brand" href="/" :aria-label="copy.brandAria">
            <img class="brand-logo" :src="productionsLogo" alt="Productions" />
          </a>
          <div class="topbar-actions">
            <nav class="top-links" :aria-label="copy.navigationAria">
              <div class="top-dropdown" :class="{ 'is-open': openNavigationMenu === 'product-tests' }">
                <button
                  class="top-link top-dropdown-trigger"
                  type="button"
                  :aria-expanded="openNavigationMenu === 'product-tests'"
                  @click.stop="toggleNavigationMenu('product-tests')"
                >
                  <Factory class="top-menu-icon" :size="16" aria-hidden="true" />
                  <span>{{ copy.nav.productLineTests }}</span>
                  <ChevronDown class="top-dropdown-chevron" :size="14" aria-hidden="true" />
                </button>
                <div class="top-dropdown-menu" role="menu" @click.stop>
                  <a href="/data/uploads" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                    {{ copy.nav.dataAutomationUpload }}
                  </a>
                  <div class="top-dropdown-dual" role="group" :aria-label="copy.nav.deviceAndTestManagement">
                    <a href="/devices" target="_blank" rel="noopener noreferrer" @click="closeNavigationMenu">{{ copy.nav.deviceManagement }}</a>
                    <span>&amp;</span>
                    <a href="/test-cases" target="_blank" rel="noopener noreferrer" @click="closeNavigationMenu">{{ copy.nav.testManagement }}</a>
                  </div>
                  <a href="/data" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                    {{ copy.nav.dataManagement }}
                  </a>
                </div>
              </div>
              <div class="top-dropdown" :class="{ 'is-open': openNavigationMenu === 'version-checks' }">
                <button
                  class="top-link top-dropdown-trigger"
                  type="button"
                  :aria-expanded="openNavigationMenu === 'version-checks'"
                  @click.stop="toggleNavigationMenu('version-checks')"
                >
                  <PackageCheck class="top-menu-icon" :size="16" aria-hidden="true" />
                  <span>{{ copy.nav.versionChecks }}</span>
                  <ChevronDown class="top-dropdown-chevron" :size="14" aria-hidden="true" />
                </button>
                <div class="top-dropdown-menu is-right" role="menu" @click.stop>
                  <a href="/versions?module=sop-duro" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                    {{ copy.nav.sopDuroCheck }}
                  </a>
                  <a href="/versions?module=ecn" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeNavigationMenu">
                    {{ copy.nav.ecnCheck }}
                  </a>
                </div>
              </div>
              <a class="top-link" :href="productionAgentBaseUrl" target="_blank" rel="noopener noreferrer">
                <Bot class="top-menu-icon" :size="16" aria-hidden="true" />
                <span>{{ copy.nav.productionAgent }}</span>
              </a>
              <a class="top-link" href="/downloads">
                <Download class="top-menu-icon" :size="16" aria-hidden="true" />
                <span>{{ copy.nav.downloads }}</span>
              </a>
            </nav>
            <div class="language-switcher" role="group" :aria-label="copy.languageLabel">
              <button type="button" :class="{ 'is-active': locale === 'zh' }" :aria-pressed="locale === 'zh'" @click="setLocale('zh')">中文</button>
              <button type="button" :class="{ 'is-active': locale === 'en' }" :aria-pressed="locale === 'en'" @click="setLocale('en')">EN</button>
            </div>
          </div>
        </header>

        <div class="hero-stage">
          <div class="hero-content">
            <p class="eyebrow">{{ copy.dashboard.eyebrow }}</p>
            <h1>{{ copy.dashboard.title }}</h1>
            <p class="hero-copy">{{ copy.dashboard.introduction }}</p>
            <div class="hero-actions">
              <a class="primary-action" :href="operationsBaseUrl" target="_blank" rel="noopener noreferrer">
                <span>{{ copy.dashboard.openOperations }}</span>
                <ArrowRight :size="18" aria-hidden="true" />
              </a>
              <a class="secondary-action" href="#modules">
                <span>{{ copy.dashboard.viewModules }}</span>
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
            <p class="eyebrow">{{ copy.dashboard.modulesEyebrow }}</p>
            <h2 id="modules-title">{{ copy.dashboard.modulesTitle }}</h2>
          </div>
        </div>

        <div class="module-grid">
          <article
            v-for="module in modules"
            :key="module.name"
            class="module-card"
            :class="{ 'is-muted': module.statusClass === 'status-planned' }"
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
            <a
              v-if="module.href"
              class="module-action"
              :href="module.href"
              :target="module.openInNewTab ? '_blank' : undefined"
              :rel="module.openInNewTab ? 'noopener noreferrer' : undefined"
              :aria-label="copy.dashboard.openModule(module.name)"
            >
              <ExternalLink :size="18" aria-hidden="true" />
            </a>
            <button v-else class="module-action is-disabled" type="button" disabled :aria-label="copy.dashboard.comingSoon">
              <Wrench :size="18" aria-hidden="true" />
            </button>
          </article>
        </div>
      </section>

      <section class="routes-section" aria-labelledby="routes-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ copy.dashboard.operationsEyebrow }}</p>
            <h2 id="routes-title">{{ copy.dashboard.operationsTitle }}</h2>
          </div>
        </div>

        <div class="route-grid">
          <a
            v-for="route in productionRoutes"
            :key="route.label"
            class="route-tile"
            :href="route.href"
            target="_blank"
            rel="noopener noreferrer"
          >
            <component :is="route.icon" :size="20" aria-hidden="true" />
            <span>{{ route.label }}</span>
            <ArrowRight :size="16" aria-hidden="true" />
          </a>
        </div>
      </section>

      <section class="developer-section" aria-labelledby="developer-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">{{ copy.dashboard.developerEyebrow }}</p>
            <h2 id="developer-title">{{ copy.dashboard.developerTitle }}</h2>
          </div>
        </div>

        <div class="developer-option">
          <div class="developer-option-name">
            <span class="developer-option-icon" aria-hidden="true">
              <Wrench :size="19" />
            </span>
            <div>
              <h3>{{ copy.simulatingLabel }}</h3>
              <p v-if="simulatingHint" role="status">{{ simulatingHint }}</p>
            </div>
          </div>
          <button
            class="simulating-toggle"
            :class="{ 'is-on': simulatingEnabled }"
            type="button"
            role="switch"
            :aria-checked="simulatingEnabled"
            :aria-label="copy.simulatingLabel"
            :title="simulatingHint || copy.simulatingLabel"
            :disabled="simulatingSaving"
            @click="toggleSimulating"
          >
            <span class="simulating-toggle-track" aria-hidden="true"><i></i></span>
            <span>{{ simulatingEnabled ? copy.simulatingOn : copy.simulatingOff }}</span>
          </button>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
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
import flexImage from '@/assets/dashboard/flex.png'
import productionsLogo from '@/assets/dashboard/productions-logo.svg'
import { settingsApi } from '@/scripts/api'
import {
  DASHBOARD_LANGUAGE_STORAGE_KEY,
  dashboardMessages,
  type DashboardLocale,
} from '@/scripts/dashboard/i18n'
import '@/styles/dashboard/dashboard.css'

const props = withDefaults(defineProps<{ mode?: 'dashboard' | 'downloads' }>(), {
  mode: 'dashboard',
})

function readInitialLocale(): DashboardLocale {
  if (typeof window === 'undefined') return 'zh'
  try {
    return window.localStorage.getItem(DASHBOARD_LANGUAGE_STORAGE_KEY) === 'en' ? 'en' : 'zh'
  } catch {
    return 'zh'
  }
}

const locale = ref<DashboardLocale>(readInitialLocale())
const copy = computed(() => dashboardMessages[locale.value])

function applyLocale(nextLocale: DashboardLocale): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = nextLocale === 'zh' ? 'zh-CN' : 'en'
}

function setLocale(nextLocale: DashboardLocale): void {
  locale.value = nextLocale
  try {
    window.localStorage.setItem(DASHBOARD_LANGUAGE_STORAGE_KEY, nextLocale)
  } catch {
    // Language switching should still work when browser storage is unavailable.
  }
  applyLocale(nextLocale)
}

const simulatingEnabled = ref(false)
const simulatingSaving = ref(false)
const simulatingHint = ref('')

async function loadSimulatingStatus(): Promise<void> {
  try {
    const { data } = await settingsApi.getSimulatingStatus()
    simulatingEnabled.value = data.simulating
    simulatingHint.value = data.simulating ? copy.value.simulatingEnabled : copy.value.simulatingDisabled
  } catch {
    // Keep the default off state when the API is unavailable.
  }
}

async function toggleSimulating(): Promise<void> {
  if (simulatingSaving.value) return
  const nextValue = !simulatingEnabled.value
  simulatingSaving.value = true
  try {
    const { data } = await settingsApi.updateSimulatingStatus(nextValue)
    simulatingEnabled.value = data.simulating
    simulatingHint.value = data.simulating ? copy.value.simulatingEnabled : copy.value.simulatingDisabled
  } catch (error) {
    simulatingHint.value = error instanceof Error ? error.message : copy.value.simulatingUpdateFailed
  } finally {
    simulatingSaving.value = false
  }
}

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

const operationsBaseUrl = withTrailingSlash(
  import.meta.env.VITE_OPERATIONS_URL || '/home',
)
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
const productionAgentUrl = import.meta.env.VITE_PRODUCTION_AGENT_URL || ''
const productionAgentBaseUrl = productionAgentUrl ? withTrailingSlash(productionAgentUrl) : '/agent'

const projects = ref<ResourceProject[]>([])
const expandedProjectIds = ref(new Set<string>())
const openMenuVersionId = ref('')
const openNavigationMenu = ref<'' | 'product-tests' | 'version-checks'>('')
const isLoading = ref(true)
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

const isDownloadsView = computed(() => props.mode === 'downloads')

function withTrailingSlash(value: string): string {
  return value.endsWith('/') ? value : `${value}/`
}

function routeUrl(path: string): string {
  return `/${path.replace(/^\/+/, '')}`
}

function handleWindowClick(): void {
  closeVersionMenu()
  closeNavigationMenu()
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Escape') return
  if (isFormOpen.value) closeForm()
  else {
    closeVersionMenu()
    closeNavigationMenu()
  }
}

function toggleNavigationMenu(menu: 'product-tests' | 'version-checks'): void {
  openNavigationMenu.value = openNavigationMenu.value === menu ? '' : menu
}

function closeNavigationMenu(): void {
  openNavigationMenu.value = ''
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
  return new Intl.DateTimeFormat(locale.value === 'zh' ? 'zh-CN' : 'en-US', {
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
    return payload.detail || payload.message || copy.value.downloads.requestFailed(response.status)
  } catch {
    return copy.value.downloads.requestFailed(response.status)
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
    loadError.value = error instanceof Error ? error.message : copy.value.downloads.unknownServerError
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
    formError.value = copy.value.downloads.versionRequired
    return
  }
  if (formMode.value === 'upload') {
    if (!form.projectName.trim()) {
      formError.value = copy.value.downloads.projectRequired
      return
    }
    if (!selectedFile.value) {
      formError.value = copy.value.downloads.fileRequired
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
    notice.message = copy.value.downloads.uploadSucceeded(form.version.trim())
    resetForm()
    await loadProjects()
    if (projectId) expandedProjectIds.value.add(projectId)
  } catch (error) {
    formError.value = error instanceof Error ? error.message : copy.value.downloads.uploadFailed
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
      } else reject(new Error(payload.detail || copy.value.downloads.uploadRequestFailed(request.status)))
    })
    request.addEventListener('error', () => reject(new Error(copy.value.downloads.resourceServiceUnavailable)))
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
    notice.message = copy.value.downloads.updateSucceeded
    resetForm()
    await loadProjects()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : copy.value.downloads.updateFailed
  } finally {
    isSubmitting.value = false
  }
}

async function deleteVersion(resourceVersion: ResourceVersion): Promise<void> {
  closeVersionMenu()
  if (!window.confirm(copy.value.downloads.deleteConfirmation(resourceVersion.version))) return
  try {
    const response = await fetch(`${apiBaseUrl}/file-resources/versions/${encodeURIComponent(resourceVersion.id)}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error(await parseError(response))
    notice.type = 'success'
    notice.message = copy.value.downloads.deleteSucceeded(resourceVersion.version)
    await loadProjects()
  } catch (error) {
    notice.type = 'error'
    notice.message = error instanceof Error ? error.message : copy.value.downloads.deleteFailed
  }
}

onMounted(() => {
  applyLocale(locale.value)
  window.addEventListener('click', handleWindowClick)
  window.addEventListener('keydown', handleKeydown)
  void loadSimulatingStatus()
  if (isDownloadsView.value) void loadProjects()
})

onBeforeUnmount(() => {
  window.removeEventListener('click', handleWindowClick)
  window.removeEventListener('keydown', handleKeydown)
})

const modules = computed(() => [
  {
    ...copy.value.dashboard.modules.operations,
    status: copy.value.status.active,
    statusClass: 'status-active',
    href: operationsBaseUrl,
    openInNewTab: true,
    icon: Factory,
  },
  {
    ...copy.value.dashboard.modules.versions,
    status: copy.value.status.active,
    statusClass: 'status-active',
    href: '/versions',
    openInNewTab: true,
    icon: Package,
  },
  {
    ...copy.value.dashboard.modules.downloads,
    status: copy.value.status.active,
    statusClass: 'status-active',
    href: '/downloads',
    openInNewTab: false,
    icon: Download,
  },
  {
    ...copy.value.dashboard.modules.agent,
    status: copy.value.status.ready,
    statusClass: 'status-active',
    href: productionAgentBaseUrl,
    openInNewTab: true,
    icon: Bot,
  },
])

const productionRoutes = computed(() => [
  { label: copy.value.dashboard.routes.devices, href: routeUrl('devices'), icon: Monitor },
  { label: copy.value.dashboard.routes.testCases, href: routeUrl('test-cases'), icon: PackageCheck },
  { label: copy.value.dashboard.routes.data, href: routeUrl('data'), icon: Database },
  { label: copy.value.dashboard.routes.uploadRecords, href: routeUrl('data/uploads'), icon: UploadCloud },
  { label: copy.value.dashboard.routes.productManagement, href: routeUrl('data/products'), icon: Boxes },
  { label: copy.value.dashboard.routes.analysis, href: routeUrl('data/analysis'), icon: BarChart3 },
  { label: copy.value.dashboard.routes.messages, href: routeUrl('messages'), icon: MessageSquare },
  { label: copy.value.dashboard.routes.settings, href: routeUrl('settings'), icon: Settings },
])
</script>
