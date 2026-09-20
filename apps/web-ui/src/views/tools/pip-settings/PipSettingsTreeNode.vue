<template>
  <div v-if="visible" class="ps-tree-node">
    <div v-if="leaf" class="ps-json-leaf">
      <div class="ps-json-key">
        <strong>{{ title }}</strong>
        <small v-if="subtitle">{{ subtitle }}</small>
        <code v-if="technicalName && technicalName !== title">{{ technicalName }}</code>
      </div>
      <div class="ps-json-value">
        <div v-if="Array.isArray(value)" class="ps-primitive-list">
          <template v-for="(item, index) in value" :key="index">
            <span v-if="item === null" class="is-null">Not set <small>{{ zh.notSet }}</small></span>
            <span v-else-if="typeof item === 'boolean'" class="ps-boolean" :class="item ? 'is-yes' : 'is-no'">
              {{ item ? 'Yes' : 'No' }} <small>{{ item ? zh.yes : zh.no }}</small>
            </span>
            <span v-else-if="typeof item === 'number'" class="ps-number">
              {{ formatPrimitive(item) }}<small v-if="unit">{{ unit }}</small>
            </span>
            <span v-else class="ps-string">{{ item || `Empty string / ${zh.emptyString}` }}</span>
          </template>
        </div>
        <span v-else-if="value === null" class="is-null">Not set <small>{{ zh.notSet }}</small></span>
        <span v-else-if="typeof value === 'boolean'" class="ps-boolean" :class="value ? 'is-yes' : 'is-no'">
          {{ value ? 'Yes' : 'No' }} <small>{{ value ? zh.yes : zh.no }}</small>
        </span>
        <span v-else-if="typeof value === 'number'" class="ps-number">
          {{ formatPrimitive(value) }}<small v-if="unit">{{ unit }}</small>
        </span>
        <span v-else class="ps-string">{{ value || `Empty string / ${zh.emptyString}` }}</span>
      </div>
    </div>

    <div v-else class="ps-json-branch" :class="`is-depth-${Math.min(depth, 4)}`">
      <button class="ps-json-branch-heading" type="button" :aria-expanded="visuallyOpen" @click="open = !open">
        <ChevronDown v-if="visuallyOpen" :size="15" aria-hidden="true" />
        <ChevronRight v-else :size="15" aria-hidden="true" />
        <span class="ps-field-copy">
          <strong>{{ title }}</strong>
          <small v-if="subtitle">{{ subtitle }}</small>
        </span>
        <code v-if="technicalName && technicalName !== title">{{ technicalName }}</code>
        <span v-else></span>
        <span class="ps-item-count">{{ childCount }} items <small>{{ childCount }} {{ zh.items }}</small></span>
      </button>

      <div v-if="visuallyOpen" class="ps-json-branch-body">
        <div v-if="matrix" class="ps-matrix-wrap">
          <table class="ps-matrix-table">
            <thead>
              <tr>
                <th>#</th>
                <th v-for="index in matrixColumnCount" :key="index">Value {{ index }} <small>{{ zh.value }} {{ index }}</small></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in matrixRows" :key="rowIndex">
                <td>{{ rowIndex + 1 }}</td>
                <td v-for="columnIndex in matrixColumnCount" :key="columnIndex">
                  {{ formatPrimitive(row[columnIndex - 1] ?? null) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <template v-else-if="Array.isArray(value)">
          <PipSettingsTreeNode
            v-for="(item, index) in value"
            :key="`${path}.${index}`"
            :name="`[${index + 1}]`"
            :value="item"
            :path="`${path}.${index}`"
            :depth="depth + 1"
            :query="query"
            :tree-command="treeCommand"
            :presentation="getArrayItemPresentation(name, item, index)"
          />
        </template>
        <template v-else>
          <PipSettingsTreeNode
            v-for="([key, item]) in objectEntries"
            :key="`${path}.${key}`"
            :name="key"
            :value="item"
            :path="`${path}.${key}`"
            :depth="depth + 1"
            :query="query"
            :tree-command="treeCommand"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronRight } from '@lucide/vue'
import { pipSettingsZh as zh } from '@/i18n/locales/pipSettings'
import {
  fieldLabelEn,
  fieldLabelZh,
  formatPrimitive,
  getArrayItemPresentation,
  isContainer,
  isPrimitiveArray,
  isPrimitiveMatrix,
  keyMatches,
  normalize,
  unitForKey,
  valueMatches,
} from './helpers'
import type { JsonObject, JsonPrimitive, JsonValue, NodePresentation, TreeCommand } from './types'

const props = defineProps<{
  name: string
  value: JsonValue
  path: string
  depth: number
  query: string
  treeCommand: TreeCommand
  presentation?: NodePresentation
}>()

const open = ref(props.depth === 0)
const title = computed(() => props.presentation?.title ?? fieldLabelEn(props.name))
const subtitle = computed(() => props.presentation?.subtitle ?? fieldLabelZh(props.name))
const technicalName = computed(() => props.presentation?.technicalName ?? props.name)
const searchActive = computed(() => Boolean(props.query.trim()))
const visible = computed(() => !searchActive.value || keyMatches(props.name, props.query)
  || normalize(`${title.value} ${subtitle.value} ${technicalName.value}`).includes(normalize(props.query))
  || valueMatches(props.value, props.query))
const leaf = computed(() => !isContainer(props.value) || isPrimitiveArray(props.value))
const matrix = computed(() => isPrimitiveMatrix(props.value))
const visuallyOpen = computed(() => open.value || searchActive.value)
const objectEntries = computed<[string, JsonValue][]>(() => {
  if (Array.isArray(props.value) || !isContainer(props.value)) return []
  const omitted = props.presentation?.omitKeys ?? []
  return Object.entries(props.value as JsonObject).filter(([key]) => !omitted.includes(key))
})
const childCount = computed(() => Array.isArray(props.value) ? props.value.length : objectEntries.value.length)
const matrixRows = computed(() => props.value as JsonPrimitive[][])
const matrixColumnCount = computed(() => Math.max(0, ...matrixRows.value.map(row => row.length)))
const unit = computed(() => unitForKey(props.path.split('.').at(-1) ?? props.name))

watch(() => props.treeCommand.token, () => {
  if (props.treeCommand.action === 'expand') open.value = true
  else if (props.treeCommand.action === 'collapse') open.value = false
  else open.value = props.depth === 0
})
</script>
