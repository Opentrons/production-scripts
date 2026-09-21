<template>
  <div class="pip-settings-page">
    <header class="ps-page-header">
      <a class="ps-brand" href="/" aria-label="Back to Productions">
        <img :src="productionsLogo" alt="Productions" />
      </a>
      <div class="ps-page-title">
        <div class="ps-title-icon"><Pipette :size="19" aria-hidden="true" /></div>
        <div>
          <strong>Pip Settings Review</strong>
          <small>{{ zh.appSubtitle }}</small>
        </div>
      </div>
      <div class="ps-header-actions">
        <a v-if="!isLocalPreview" class="ps-home-link" href="/">
          <ArrowLeft :size="16" aria-hidden="true" />
          <span>Back<small>{{ zh.backHome }}</small></span>
        </a>
        <LocaleSwitcher variant="surface" />
        <div v-if="isLocalPreview" class="ps-preview-badge">
          <Eye :size="16" aria-hidden="true" />
          <span><strong>Local Preview</strong><small>{{ zh.localPreview }}</small></span>
        </div>
        <AuthUserMenu v-else />
      </div>
    </header>

    <div v-if="loading" class="ps-page-state" aria-live="polite">
      <LoaderCircle class="is-spinning" :size="24" aria-hidden="true" />
      <strong>Loading configuration snapshot</strong>
      <small>{{ zh.loadingSnapshot }}</small>
    </div>
    <div v-else-if="loadError || !dataset" class="ps-page-state is-error" role="alert">
      <CircleAlert :size="24" aria-hidden="true" />
      <strong>Configuration data is unavailable</strong>
      <small>{{ loadError || zh.dataUnavailable }}</small>
      <button type="button" @click="loadSnapshot">Retry <small>{{ zh.retry }}</small></button>
    </div>

    <div v-else-if="selectedPipette && activeRevision" class="ps-workspace">
      <aside class="ps-sidebar">
        <div class="ps-sidebar-heading">
          <div>
            <span>PIPETTE LIBRARY</span>
            <h2>Pipette Types</h2>
            <small>{{ zh.pipetteTypes }}</small>
          </div>
          <b>{{ dataset.pipettes.length }}</b>
        </div>

        <label class="ps-search ps-sidebar-search">
          <Search :size="16" aria-hidden="true" />
          <input v-model="pipetteFilter" :placeholder="`Search channel or volume / ${zh.searchPipette}`" />
          <button v-if="pipetteFilter" type="button" aria-label="Clear pipette search" @click="pipetteFilter = ''">
            <X :size="14" aria-hidden="true" />
          </button>
        </label>

        <nav class="ps-pipette-list" aria-label="Pipette types">
          <button
            v-for="pipette in visiblePipettes"
            :key="pipette.id"
            type="button"
            class="ps-pipette-item"
            :class="{ 'is-active': pipette.id === selectedPipette.id }"
            @click="selectPipette(pipette.id)"
          >
            <span class="ps-channel-badge"><strong>{{ pipette.channels }}</strong><small>CH</small></span>
            <span class="ps-pipette-copy">
              <strong>{{ pipette.displayName.replace(/^Flex\s*/i, '') }}</strong>
              <span>{{ pipette.revisions.length }} revisions · {{ pipette.maxVolume }} µL max</span>
              <small>{{ pipette.revisions.length }} {{ zh.revisions }} · {{ zh.maximum }} {{ pipette.maxVolume }} µL</small>
            </span>
            <ChevronRight :size="16" aria-hidden="true" />
          </button>
          <div v-if="visiblePipettes.length === 0" class="ps-empty-list">
            No matching pipette <small>{{ zh.noPipette }}</small>
          </div>
        </nav>

        <div class="ps-branch-card" :class="{ 'is-open': branchOpen }">
          <div v-if="branchOpen" class="ps-branch-popover">
            <div class="ps-branch-heading">
              <div><strong>GitHub Branch</strong><small>{{ zh.githubBranch }}</small></div>
              <button type="button" aria-label="Close branch selector" @click="branchOpen = false"><X :size="14" /></button>
            </div>
            <label class="ps-search ps-branch-search">
              <LoaderCircle v-if="branchSearching" class="is-spinning" :size="15" />
              <Search v-else :size="15" />
              <input
                v-model="branchQuery"
                autofocus
                :placeholder="`Search branch prefix / ${zh.searchBranch}`"
                @keydown.enter="loadBranch(branchQuery)"
              />
              <button v-if="branchQuery" type="button" aria-label="Clear branch search" @click="branchQuery = ''"><X :size="13" /></button>
            </label>
            <div class="ps-branch-results" role="listbox" aria-label="GitHub branches">
              <button
                v-for="branch in branches"
                :key="branch.name"
                type="button"
                :class="{ 'is-active': branch.name === dataset.source.branch }"
                :disabled="Boolean(loadingBranch)"
                role="option"
                :aria-selected="branch.name === dataset.source.branch"
                @click="loadBranch(branch.name)"
              >
                <GitBranch :size="14" />
                <span><strong>{{ branch.name }}</strong><code>{{ branch.commit.slice(0, 10) }}</code></span>
                <Check v-if="branch.name === dataset.source.branch" :size="14" />
              </button>
              <div v-if="!branchSearching && branches.length === 0" class="ps-branch-empty">
                No matching branches <small>{{ zh.noBranches }}</small>
              </div>
            </div>
            <button
              v-if="branchQuery.trim() && !hasExactBranch"
              class="ps-load-exact"
              type="button"
              :disabled="Boolean(loadingBranch)"
              @click="loadBranch(branchQuery)"
            >
              <GitBranch :size="14" />
              <span><strong>Load “{{ branchQuery.trim() }}”</strong><small>{{ zh.loadBranch }}</small></span>
            </button>
            <div v-if="loadingBranch" class="ps-branch-status">
              <LoaderCircle class="is-spinning" :size="15" />
              <span><strong>Loading {{ loadingBranch }}</strong><small>{{ zh.loadingFiles }}</small></span>
            </div>
            <div v-if="branchError" class="ps-branch-status is-error" role="alert">{{ branchError }}</div>
          </div>
          <button
            class="ps-source-summary"
            type="button"
            :aria-expanded="isLocalPreview ? false : branchOpen"
            :disabled="isLocalPreview"
            :title="isLocalPreview ? `Sign in to switch branches / ${zh.previewSnapshot}` : undefined"
            @click="branchOpen = !branchOpen"
          >
            <span class="ps-source-icon"><Database :size="18" /></span>
            <span>
              <small>ACTIVE BRANCH · {{ zh.activeBranch }}</small>
              <strong>{{ dataset.source.branch }}</strong>
              <em v-if="isLocalPreview">Bundled snapshot · {{ zh.previewSnapshot }}</em>
              <em v-else>{{ sourceFileCount }} source files · {{ sourceFileCount }} {{ zh.sourceFiles }}</em>
              <code>{{ dataset.source.commit.slice(0, 10) }}</code>
            </span>
            <ChevronDown :size="16" />
          </button>
        </div>
      </aside>

      <main class="ps-content">
        <section class="ps-pipette-hero">
          <div class="ps-hero-copy">
            <div class="ps-hero-icon"><Pipette :size="29" stroke-width="1.8" /></div>
            <div>
              <div class="ps-hero-badges">
                <span>{{ selectedPipette.displayCategory }}</span><span>Gen3</span><span>{{ formatChannelLabel(selectedPipette) }}</span>
              </div>
              <h1>{{ selectedPipette.displayName }}</h1>
              <p>{{ selectedPipette.model.toUpperCase() }} · Max {{ selectedPipette.maxVolume }} µL · {{ selectedPipette.revisions.length }} definition revisions</p>
              <small>{{ zh.maximum }} {{ selectedPipette.maxVolume }} µL · {{ selectedPipette.revisions.length }} {{ zh.definitionRevisions }}</small>
            </div>
          </div>
          <div class="ps-revision-control">
            <div class="ps-revision-label">
              <GitCommitHorizontal :size="15" />
              <div><strong>Definition Version</strong><small>{{ zh.definitionVersion }}</small></div>
            </div>
            <div class="ps-revision-options" role="group" aria-label="Definition version">
              <button
                v-for="(revision, index) in [...selectedPipette.revisions].reverse()"
                :key="revision.version"
                type="button"
                :class="{ 'is-active': revision.version === activeRevision.version }"
                :aria-pressed="revision.version === activeRevision.version"
                @click="selectedRevision = revision.version"
              >
                <strong>{{ revision.version.replace('_', '.') }}</strong>
                <small v-if="index === 0">Latest</small>
              </button>
            </div>
          </div>
        </section>

        <section class="ps-toolbar">
          <label class="ps-search ps-field-search">
            <Filter :size="17" />
            <input v-model="fieldFilter" :placeholder="`Search fields or values / ${zh.searchFields}`" />
            <button v-if="fieldFilter" type="button" aria-label="Clear field search" @click="fieldFilter = ''"><X :size="14" /></button>
          </label>
          <div class="ps-toolbar-actions">
            <button type="button" @click="expandAll"><ChevronsUpDown :size="16" /><span><strong>Expand All</strong><small>{{ zh.expandAll }}</small></span></button>
            <button type="button" @click="collapseAll"><ChevronsDownUp :size="16" /><span><strong>Collapse All</strong><small>{{ zh.collapseAll }}</small></span></button>
          </div>
        </section>

        <section class="ps-config-stack">
          <article
            v-for="section in standardSections"
            :key="section.id"
            class="ps-definition-section"
            :class="[`is-${section.color}`, { 'is-open': sectionVisuallyOpen(section.id) }]"
          >
            <button class="ps-section-heading" type="button" :aria-expanded="sectionVisuallyOpen(section.id)" @click="toggleSection(section.id)">
              <span class="ps-section-icon"><component :is="section.icon" :size="19" /></span>
              <span class="ps-section-title">
                <em>{{ section.eyebrow }}</em><strong>{{ section.title }}</strong><small>{{ section.titleZh }}</small><span>{{ section.description }}</span>
              </span>
              <span class="ps-section-meta">
                <span>{{ documentsFor(section.id).length }} config sets <small>{{ documentsFor(section.id).length }} {{ zh.configSets }}</small></span>
                <ChevronDown :size="19" />
              </span>
            </button>
            <div v-if="sectionVisuallyOpen(section.id)" class="ps-section-body">
              <PipSettingsDocumentCard
                v-for="item in matchingDocuments(section.id)"
                :key="`${item.title}-${item.document.sourcePath}`"
                v-bind="item"
                :query="fieldFilter"
                :tree-command="treeCommand"
                :repository="dataset.source.repository"
                :commit="dataset.source.commit"
              />
              <div v-if="matchingDocuments(section.id).length === 0" class="ps-no-results">
                <Search :size="17" /><span>No matching fields <small>{{ zh.noFields }}</small></span>
              </div>
            </div>
          </article>

          <article class="ps-definition-section is-amber" :class="{ 'is-open': liquidSectionVisuallyOpen }">
            <button class="ps-section-heading" type="button" :aria-expanded="liquidSectionVisuallyOpen" @click="toggleSection('liquidClasses')">
              <span class="ps-section-icon"><Droplets :size="19" /></span>
              <span class="ps-section-title">
                <em>LIQUID CLASS</em><strong>Liquid Classes</strong><small>{{ zh.liquidClasses }}</small>
                <span>{{ zh.liquidDescription }}</span>
              </span>
              <span class="ps-section-meta">
                <span>{{ liquidGroups.length }} liquids <small>{{ liquidGroups.length }} {{ zh.liquids }}</small></span><ChevronDown :size="19" />
              </span>
            </button>
            <div v-if="liquidSectionVisuallyOpen" class="ps-section-body ps-liquid-class-list">
              <div v-for="group in visibleLiquidGroups" :key="group.id" class="ps-liquid-group">
                <div class="ps-liquid-heading">
                  <span class="ps-liquid-icon"><Droplets :size="17" /></span>
                  <div><em>{{ group.id }}</em><strong>{{ group.displayName }}</strong><p>{{ group.description }}</p></div>
                  <span>{{ group.documents.length }} versions <small>{{ group.documents.length }} {{ zh.versions }}</small></span>
                </div>
                <div class="ps-liquid-versions">
                  <PipSettingsDocumentCard
                    v-for="item in group.documents"
                    :key="item.document.sourcePath"
                    v-bind="item"
                    compact
                    :query="fieldFilter"
                    :tree-command="treeCommand"
                    :repository="dataset.source.repository"
                    :commit="dataset.source.commit"
                  />
                </div>
              </div>
              <div v-if="visibleLiquidGroups.length === 0" class="ps-no-results">
                <Search :size="17" /><span>No matching liquid classes <small>{{ zh.noLiquidClasses }}</small></span>
              </div>
            </div>
          </article>
        </section>

        <footer class="ps-content-footer">
          <span>Read-only configuration data <small>{{ zh.readOnly }}</small></span>
          <CircleDot :size="12" />
          <span>Opentrons commit {{ dataset.source.commit.slice(0, 12) }}</span>
          <a :href="dataset.source.repository" target="_blank" rel="noopener noreferrer">View Source <small>{{ zh.viewSource }}</small><ExternalLink :size="13" /></a>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, type Component } from 'vue'
import {
  ArrowLeft, Check, ChevronDown, ChevronRight, ChevronsDownUp, ChevronsUpDown,
  CircleAlert, CircleDot, Database, Droplets, ExternalLink, Eye, Filter, Gauge, GitBranch,
  GitCommitHorizontal, LoaderCircle, Pipette, Ruler, Search, SlidersHorizontal, X,
} from '@lucide/vue'
import { useRoute } from 'vue-router'
import productionsLogo from '@/assets/dashboard/productions-logo.svg'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'
import { pipSettingsZh as zh } from '@/i18n/locales/pipSettings'
import { pipSettingsApi } from '@/scripts/api/pipSettings'
import { isLocalPipSettingsPreview } from '@/scripts/router/pipSettingsPreview'
import PipSettingsDocumentCard from './pip-settings/PipSettingsDocumentCard.vue'
import { formatChannelLabel, humanize, normalize, valueMatches } from './pip-settings/helpers'
import type {
  DocumentDescriptor, GitHubBranch, JsonObject, LiquidClassDefinition, PipetteDefinition,
  PipSettingsDataset, TreeCommand,
} from './pip-settings/types'
import '@/styles/tools/pip-settings-review.css'

type StandardSectionId = 'general' | 'geometry' | 'liquid'
type SectionId = StandardSectionId | 'liquidClasses'
interface SectionInfo {
  id: StandardSectionId
  title: string
  titleZh: string
  eyebrow: string
  description: string
  color: string
  icon: Component
}

const standardSections: SectionInfo[] = [
  { id: 'general', title: 'General & Hardware', titleZh: zh.generalTitle, eyebrow: 'GENERAL', description: zh.generalDescription, color: 'teal', icon: SlidersHorizontal },
  { id: 'geometry', title: 'Geometry & Spatial', titleZh: zh.geometryTitle, eyebrow: 'GEOMETRY', description: zh.geometryDescription, color: 'blue', icon: Ruler },
  { id: 'liquid', title: 'Liquid Performance', titleZh: zh.liquidTitle, eyebrow: 'LIQUID', description: zh.liquidPerformanceDescription, color: 'violet', icon: Gauge },
]

const route = useRoute()
const isLocalPreview = computed(() => isLocalPipSettingsPreview(route))
const dataset = ref<PipSettingsDataset | null>(null)
const loading = ref(true)
const loadError = ref('')
const pipetteFilter = ref('')
const fieldFilter = ref('')
const selectedPipetteId = ref('')
const selectedRevision = ref('')
const openSections = ref<Set<SectionId>>(new Set(['general']))
const treeCommand = ref<TreeCommand>({ action: 'auto', token: 0 })
const branchOpen = ref(false)
const branchQuery = ref('')
const branches = ref<GitHubBranch[]>([])
const branchSearching = ref(false)
const loadingBranch = ref('')
const branchError = ref('')

const selectedPipette = computed<PipetteDefinition | undefined>(() => dataset.value?.pipettes.find(
  pipette => pipette.id === selectedPipetteId.value,
) ?? dataset.value?.pipettes[0])
const activeRevision = computed(() => selectedPipette.value?.revisions.find(
  revision => revision.version === selectedRevision.value,
) ?? selectedPipette.value?.revisions.at(-1))
const visiblePipettes = computed(() => {
  if (!dataset.value) return []
  const query = normalize(pipetteFilter.value)
  if (!query) return dataset.value.pipettes
  return dataset.value.pipettes.filter(pipette => normalize(
    `${pipette.displayName} ${pipette.channelLabel} ${pipette.model}`,
  ).includes(query))
})
const sourceFileCount = computed(() => dataset.value
  ? dataset.value.stats.pipetteDefinitionFiles + dataset.value.stats.liquidClassDefinitionFiles : 0)
const hasExactBranch = computed(() => branches.value.some(branch => branch.name === branchQuery.value.trim()))

watch(selectedPipette, pipette => {
  if (!pipette) return
  if (!pipette.revisions.some(revision => revision.version === selectedRevision.value)) {
    selectedRevision.value = pipette.revisions.at(-1)?.version ?? ''
  }
}, { immediate: true })

let searchTimer = 0
watch([branchOpen, branchQuery], ([open]) => {
  window.clearTimeout(searchTimer)
  if (!open || !dataset.value) return
  searchTimer = window.setTimeout(async () => {
    branchSearching.value = true
    branchError.value = ''
    try {
      const results = await pipSettingsApi.searchBranches(branchQuery.value)
      const current = { name: dataset.value!.source.branch, commit: dataset.value!.source.commit }
      branches.value = [current, ...results.filter(result => result.name !== current.name)]
    } catch (error) {
      branchError.value = readErrorMessage(error)
    } finally {
      branchSearching.value = false
    }
  }, 320)
})

onMounted(loadSnapshot)

async function loadSnapshot(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const base = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`
    const response = await fetch(`${base}data/pip-settings/opentrons-gen3.json`)
    if (!response.ok) throw new Error(`Snapshot request failed (${response.status})`)
    applyDataset(await response.json() as PipSettingsDataset)
  } catch (error) {
    loadError.value = readErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function applyDataset(nextDataset: PipSettingsDataset): void {
  const currentId = selectedPipetteId.value
  dataset.value = nextDataset
  selectedPipetteId.value = nextDataset.pipettes.some(pipette => pipette.id === currentId)
    ? currentId : (nextDataset.pipettes[0]?.id ?? '')
  selectedRevision.value = ''
  pipetteFilter.value = ''
  fieldFilter.value = ''
  openSections.value = new Set(['general'])
  treeCommand.value = { action: 'auto', token: treeCommand.value.token + 1 }
}

function selectPipette(id: string): void {
  selectedPipetteId.value = id
  fieldFilter.value = ''
  treeCommand.value = { action: 'auto', token: treeCommand.value.token + 1 }
}

function toggleSection(id: SectionId): void {
  const next = new Set(openSections.value)
  next.has(id) ? next.delete(id) : next.add(id)
  openSections.value = next
}

function expandAll(): void {
  openSections.value = new Set<SectionId>(['general', 'geometry', 'liquid', 'liquidClasses'])
  treeCommand.value = { action: 'expand', token: treeCommand.value.token + 1 }
}

function collapseAll(): void {
  openSections.value = new Set()
  treeCommand.value = { action: 'collapse', token: treeCommand.value.token + 1 }
}

function documentsFor(id: StandardSectionId): DocumentDescriptor[] {
  const revision = activeRevision.value
  if (!revision) return []
  if (id === 'general') return revision.general
    ? [{ title: 'General Definition', titleZh: zh.generalDefinition, document: revision.general }] : []
  if (id === 'geometry') return revision.geometry
    ? [{ title: 'Geometry Definition', titleZh: zh.geometryDefinition, document: revision.geometry }] : []
  return Object.entries(revision.liquid).map(([profile, document]) => ({
    title: profile === 'default' ? 'Default Liquid Profile' : humanize(profile),
    titleZh: profile === 'default' ? zh.defaultLiquidProfile : zh.liquidProfile,
    subtitle: `Profile: ${profile} / ${zh.profile}: ${profile}`,
    document,
  }))
}

function matchingDocuments(id: StandardSectionId): DocumentDescriptor[] {
  return documentsFor(id).filter(item => !fieldFilter.value.trim()
    || normalize(`${item.title} ${item.titleZh ?? ''}`).includes(normalize(fieldFilter.value))
    || valueMatches(item.document.data, fieldFilter.value))
}

function sectionVisuallyOpen(id: StandardSectionId): boolean {
  return openSections.value.has(id) || Boolean(fieldFilter.value.trim() && matchingDocuments(id).length)
}

function liquidDocument(definition: LiquidClassDefinition): DocumentDescriptor | null {
  const model = selectedPipette.value?.liquidClassModel
  if (!model) return null
  const selected = definition.byPipette.find(item => item.pipetteModel === model)
  if (!selected) return null
  return {
    title: `Version ${definition.version}`,
    titleZh: `${zh.version} ${definition.version}`,
    subtitle: `Schema ${definition.schemaVersion} · ${selected.byTipType.length} tip types / ${selected.byTipType.length} ${zh.tipTypes}`,
    document: {
      sourcePath: definition.sourcePath,
      data: {
        liquidClassName: definition.liquidClassName,
        displayName: definition.displayName,
        description: definition.description,
        schemaVersion: definition.schemaVersion,
        version: definition.version,
        namespace: definition.namespace,
        pipetteModel: selected.pipetteModel,
        byTipType: selected.byTipType,
      } as JsonObject,
    },
  }
}

const liquidGroups = computed(() => {
  const groups = new Map<string, LiquidClassDefinition[]>()
  const model = selectedPipette.value?.liquidClassModel
  for (const definition of dataset.value?.liquidClasses ?? []) {
    if (!model || !definition.byPipette.some(item => item.pipetteModel === model)) continue
    groups.set(definition.liquidClassName, [...(groups.get(definition.liquidClassName) ?? []), definition])
  }
  return [...groups.entries()].map(([id, definitions]) => ({
    id,
    displayName: definitions[0]?.displayName ?? id,
    description: definitions[0]?.description ?? '',
    documents: definitions.map(liquidDocument).filter((item): item is DocumentDescriptor => item !== null),
  }))
})
const visibleLiquidGroups = computed(() => liquidGroups.value.map(group => ({
  ...group,
  documents: group.documents.filter(item => !fieldFilter.value.trim()
    || normalize(`${group.id} ${group.displayName}`).includes(normalize(fieldFilter.value))
    || valueMatches(item.document.data, fieldFilter.value)),
})).filter(group => group.documents.length > 0))
const liquidSectionVisuallyOpen = computed(() => openSections.value.has('liquidClasses')
  || Boolean(fieldFilter.value.trim() && visibleLiquidGroups.value.length))

async function loadBranch(branch: string): Promise<void> {
  const normalized = branch.trim()
  if (!normalized || !dataset.value) return
  if (normalized === dataset.value.source.branch) {
    branchOpen.value = false
    branchQuery.value = ''
    return
  }
  loadingBranch.value = normalized
  branchError.value = ''
  try {
    applyDataset(await pipSettingsApi.loadBranch(normalized))
    branchOpen.value = false
    branchQuery.value = ''
  } catch (error) {
    branchError.value = readErrorMessage(error)
  } finally {
    loadingBranch.value = ''
  }
}

function readErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: string } } }).response
    if (response?.data?.detail) return response.data.detail
  }
  return error instanceof Error ? error.message : String(error)
}
</script>
