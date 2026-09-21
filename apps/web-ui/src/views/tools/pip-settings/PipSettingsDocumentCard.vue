<template>
  <div class="ps-document" :class="{ 'is-compact': compact }">
    <div class="ps-document-heading">
      <button class="ps-document-toggle" type="button" :aria-expanded="visuallyOpen" @click="open = !open">
        <ChevronDown v-if="visuallyOpen" :size="17" aria-hidden="true" />
        <ChevronRight v-else :size="17" aria-hidden="true" />
        <span>
          <strong>{{ title }}</strong>
          <small v-if="titleZh">{{ titleZh }}</small>
          <em v-if="subtitle">{{ subtitle }}</em>
        </span>
      </button>
      <div class="ps-document-actions">
        <button type="button" :title="`Copy raw JSON / ${zh.copyRawJson}`" @click="copyDocument">
          <Check v-if="copied" :size="15" aria-hidden="true" />
          <Copy v-else :size="15" aria-hidden="true" />
          <span>{{ copied ? 'Copied' : 'Copy JSON' }}<small>{{ copied ? zh.copied : zh.copyJson }}</small></span>
        </button>
        <a :href="sourceUrl" target="_blank" rel="noopener noreferrer" :title="`View on GitHub / ${zh.viewOnGithub}`">
          <ExternalLink :size="15" aria-hidden="true" />
          <span>Source<small>{{ zh.source }}</small></span>
        </a>
      </div>
    </div>

    <div v-if="visuallyOpen" class="ps-document-content">
      <div class="ps-source-path">
        <FileJson2 :size="13" aria-hidden="true" />
        <code>{{ document.sourcePath }}</code>
      </div>
      <div class="ps-json-tree">
        <PipSettingsTreeNode
          v-for="([key, value]) in visibleEntries"
          :key="key"
          :name="key"
          :value="value"
          :path="key"
          :depth="0"
          :query="query"
          :tree-command="treeCommand"
        />
        <div v-if="visibleEntries.length === 0" class="ps-no-results">
          <Search :size="17" aria-hidden="true" />
          <span>No matching fields <small>{{ zh.noFields }}</small></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ChevronDown, ChevronRight, Copy, ExternalLink, FileJson2, Search } from '@lucide/vue'
import { pipSettingsZh as zh } from '@/i18n/locales/pipSettings'
import { keyMatches, valueMatches } from './helpers'
import PipSettingsTreeNode from './PipSettingsTreeNode.vue'
import type { SourceDocument, TreeCommand } from './types'

const props = withDefaults(defineProps<{
  title: string
  titleZh?: string
  subtitle?: string
  document: SourceDocument
  query: string
  treeCommand: TreeCommand
  repository: string
  commit: string
  compact?: boolean
}>(), { titleZh: '', subtitle: '', compact: false })

const open = ref(!props.compact)
const copied = ref(false)
const searchActive = computed(() => Boolean(props.query.trim()))
const visuallyOpen = computed(() => open.value || searchActive.value)
const sourceUrl = computed(() => `${props.repository}/blob/${props.commit}/${props.document.sourcePath}`)
const visibleEntries = computed(() => Object.entries(props.document.data).filter(
  ([key, value]) => !searchActive.value || keyMatches(key, props.query) || valueMatches(value, props.query),
))

watch(() => props.treeCommand.token, () => {
  if (props.treeCommand.action === 'expand') open.value = true
  else if (props.treeCommand.action === 'collapse') open.value = false
  else open.value = !props.compact
})

async function copyDocument(): Promise<void> {
  await navigator.clipboard.writeText(JSON.stringify(props.document.data, null, 2))
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1400)
}
</script>
