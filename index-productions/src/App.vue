<template>
  <main class="app-shell">
    <section class="hero">
      <header class="topbar" aria-label="Productions navigation">
        <a class="brand" :href="opentronsBaseUrl" aria-label="Open Opentrons Productions">
          <span>PRODUCTIONS INDEX</span>
        </a>
        <nav class="top-links" aria-label="Primary modules">
          <a class="top-link" :href="opentronsBaseUrl">Opentrons Productions</a>
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
            <a class="primary-action" :href="opentronsBaseUrl">
              <span>Open Opentrons Productions</span>
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
        <p class="eyebrow">SYSTEM MAP</p>
        <h2 id="modules-title">Production Modules</h2>
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
          <a
            v-if="module.href"
            class="module-action"
            :href="module.href"
            :aria-label="`Open ${module.name}`"
          >
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
        <p class="eyebrow">APPLICATION</p>
        <h2 id="routes-title">Opentrons Productions</h2>
      </div>

      <div class="route-grid">
        <a v-for="route in productionRoutes" :key="route.label" class="route-tile" :href="route.href">
          <component :is="route.icon" :size="20" aria-hidden="true" />
          <span>{{ route.label }}</span>
          <ArrowRight :size="16" aria-hidden="true" />
        </a>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import {
  ArrowRight,
  BarChart3,
  Bot,
  Boxes,
  Database,
  ExternalLink,
  Factory,
  MessageSquare,
  Monitor,
  PackageCheck,
  Settings,
  UploadCloud,
  Wrench,
} from '@lucide/vue'
import flexImage from './assets/flex.png'

const opentronsBaseUrl = withTrailingSlash(
  import.meta.env.VITE_OPENTRONS_PRODUCTIONS_URL || '/opentrons-productions/',
)
const productionAgentUrl = import.meta.env.VITE_PRODUCTION_AGENT_URL || ''
const productionAgentBaseUrl = productionAgentUrl ? withTrailingSlash(productionAgentUrl) : ''

function withTrailingSlash(value: string): string {
  return value.endsWith('/') ? value : `${value}/`
}

function routeUrl(path: string): string {
  return `${opentronsBaseUrl}${path.replace(/^\/+/, '')}`
}

const modules = [
  {
    name: 'Opentrons Productions',
    status: 'Active',
    statusClass: 'status-active',
    summary: 'Production web app for uploads, robot operations, analysis, messages, and product tracking.',
    href: opentronsBaseUrl,
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
