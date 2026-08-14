<template>
  <div class="prep-shell" :class="{ 'is-expanded': expanded }">
    <!-- Prepare to run -->
    <div v-if="screen === 'home'" class="prep-home">
      <header class="prep-header">
        <div>
          <h3>{{ t('agent.protocol.prepareTitle') }}</h3>
          <p>{{ protocolName }}</p>
        </div>
        <div class="prep-header-actions">
          <slot name="actions" />
        </div>
      </header>

      <div v-if="!analysisOk && errors.length" class="prep-error" role="alert">
        <strong>{{ t('agent.protocol.errors') }}</strong>
        <p v-for="(item, index) in errors" :key="`${item}-${index}`">{{ item }}</p>
      </div>
      <div v-else class="prep-ok">
        <CircleCheck :size="expanded ? 18 : 14" />
        <span>{{ t('agent.protocol.okDetail') }}</span>
      </div>

      <div class="prep-rows">
        <button type="button" class="prep-row is-general" @click="screen = 'instruments'">
          <span class="prep-row-title">{{ t('agent.protocol.instrumentsTitle') }}</span>
          <span class="prep-row-detail">{{ instrumentsDetail }}</span>
          <ChevronRight class="prep-row-chevron" :size="expanded ? 22 : 16" />
        </button>
        <button type="button" class="prep-row is-general" @click="screen = 'deck'">
          <span class="prep-row-title">{{ t('agent.protocol.deckTitle') }}</span>
          <span class="prep-row-detail">{{ deckDetail }}</span>
          <ChevronRight class="prep-row-chevron" :size="expanded ? 22 : 16" />
        </button>
        <button type="button" class="prep-row is-general" @click="openSource">
          <span class="prep-row-title">{{ t('agent.protocol.sourceTitle') }}</span>
          <span class="prep-row-detail">{{ sourceDetail }}</span>
          <ChevronRight class="prep-row-chevron" :size="expanded ? 22 : 16" />
        </button>
      </div>

      <footer class="prep-footer">
        <button
          type="button"
          class="prep-play"
          :class="{ 'is-ready': analysisOk }"
          :disabled="!analysisOk"
          :title="analysisOk ? t('agent.protocol.startRun') : t('agent.protocol.startRunDisabled')"
          @click="$emit('start-run')"
        >
          <Play :size="expanded ? 28 : 18" fill="currentColor" />
        </button>
      </footer>
    </div>

    <!-- Instruments -->
    <div v-else-if="screen === 'instruments'" class="prep-detail">
      <header class="prep-detail-header">
        <button type="button" class="prep-back" @click="screen = 'home'">
          <ChevronLeft :size="expanded ? 22 : 16" />
        </button>
        <div>
          <h3>{{ t('agent.protocol.instrumentsTitle') }}</h3>
          <p>{{ t('agent.protocol.instrumentsHint') }}</p>
        </div>
      </header>
      <div class="prep-list">
        <div class="prep-list-head">
          <span>{{ t('agent.protocol.location') }}</span>
          <span>{{ t('agent.protocol.instrument') }}</span>
        </div>
        <div v-for="item in instruments" :key="`${item.mount}-${item.name}`" class="prep-instrument">
          <span class="prep-mount">{{ item.mountLabel }}</span>
          <div class="prep-instrument-copy">
            <strong>{{ item.displayName }}</strong>
            <small>{{ t('agent.protocol.instrumentReady') }}</small>
          </div>
        </div>
        <p v-if="!instruments.length" class="prep-empty">{{ t('agent.protocol.noInstruments') }}</p>
      </div>
    </div>

    <!-- Labware deck -->
    <div v-else-if="screen === 'deck'" class="prep-detail">
      <header class="prep-detail-header">
        <button type="button" class="prep-back" @click="screen = 'home'">
          <ChevronLeft :size="expanded ? 22 : 16" />
        </button>
        <div>
          <h3>{{ t('agent.protocol.deckTitle') }}</h3>
          <p>{{ deckDetail }}</p>
        </div>
        <div class="prep-tabs">
          <button type="button" :class="{ 'is-active': deckMode === 'map' }" @click="deckMode = 'map'">
            {{ t('agent.protocol.deckMap') }}
          </button>
          <button type="button" :class="{ 'is-active': deckMode === 'list' }" @click="deckMode = 'list'">
            {{ t('agent.protocol.deckList') }}
          </button>
        </div>
      </header>

      <div v-if="deckMode === 'map'" class="deck-map" :class="{ 'is-ot2': isOt2 }">
        <button
          v-for="slot in deckSlots"
          :key="slot.id"
          type="button"
          class="deck-slot"
          :class="{ 'is-filled': Boolean(slot.item), 'is-module': slot.item?.kind === 'module' }"
          :title="slot.item?.label || slot.id"
          @click="selectedSlot = slot.id"
        >
          <strong>{{ slot.id }}</strong>
          <span v-if="slot.item">{{ slot.item.short }}</span>
        </button>
      </div>

      <div v-else class="prep-list">
        <div class="prep-list-head">
          <span>{{ t('agent.protocol.location') }}</span>
          <span>{{ t('agent.protocol.labwareItem') }}</span>
        </div>
        <div v-for="item in deckItems" :key="`${item.slot}-${item.label}`" class="prep-list-row">
          <span class="prep-chip">{{ item.slot }}</span>
          <span>{{ item.label }}</span>
        </div>
        <p v-if="!deckItems.length" class="prep-empty">{{ t('agent.protocol.noLabware') }}</p>
      </div>

      <p v-if="deckMode === 'map' && selectedSlotItem" class="deck-selected">
        <strong>{{ selectedSlot }}</strong>
        <span>{{ selectedSlotItem.label }}</span>
      </p>
    </div>

    <!-- Source -->
    <div v-else class="prep-detail prep-source">
      <header class="prep-detail-header">
        <button type="button" class="prep-back" @click="screen = 'home'">
          <ChevronLeft :size="expanded ? 22 : 16" />
        </button>
        <div>
          <h3>{{ t('agent.protocol.sourceTitle') }}</h3>
          <p>{{ sourceFileName || t('agent.protocol.sourceUnavailable') }}</p>
        </div>
      </header>
      <pre v-if="sourceText" class="source-code"><code>{{ sourceText }}</code></pre>
      <p v-else class="prep-empty">{{ sourceLoading ? t('agent.protocol.sourceLoading') : t('agent.protocol.sourceUnavailable') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight, CircleCheck, Play } from '@lucide/vue'
import type { ProtocolAnalysisResult } from '@/scripts/modules/agent/agentWorkspaceApi'

type PrepScreen = 'home' | 'instruments' | 'deck' | 'source'
type DeckMode = 'map' | 'list'

type DeckItem = {
  slot: string
  label: string
  short: string
  kind: 'labware' | 'module'
}

const props = defineProps<{
  analysis: ProtocolAnalysisResult
  protocolName: string
  protocolFile?: File | null
  expanded?: boolean
}>()

defineEmits<{
  'start-run': []
}>()

const { t } = useI18n()

const screen = ref<PrepScreen>('home')
const deckMode = ref<DeckMode>('map')
const selectedSlot = ref('')
const sourceText = ref('')
const sourceLoading = ref(false)
const sourceFileName = ref('')

const analysisDoc = computed(() => (props.analysis.analysis || {}) as Record<string, unknown>)
const analysisOk = computed(() => props.analysis.result === 'ok')
const errors = computed(() => (props.analysis.errors || []).map((item) => item.detail).filter(Boolean))

const robotType = computed(() => String(props.analysis.robot_type || analysisDoc.value.robotType || ''))
const isOt2 = computed(() => /OT-2/i.test(robotType.value))

const instruments = computed(() => {
  const pipettes = Array.isArray(analysisDoc.value.pipettes) ? analysisDoc.value.pipettes as Array<Record<string, unknown>> : []
  const items = pipettes.map((pipette) => {
    const mount = String(pipette.mount || '')
    const name = String(pipette.pipetteName || pipette.pipetteModel || 'pipette')
    return {
      mount,
      name,
      mountLabel: mount === 'left' ? t('agent.protocol.mountLeft') : mount === 'right' ? t('agent.protocol.mountRight') : mount || '—',
      displayName: formatPipetteName(name),
    }
  })
  if (usesGripper.value) {
    items.push({
      mount: 'extension',
      name: 'gripper',
      mountLabel: t('agent.protocol.mountExtension'),
      displayName: t('agent.protocol.gripper'),
    })
  }
  return items
})

const usesGripper = computed(() => {
  const commands = Array.isArray(analysisDoc.value.commands) ? analysisDoc.value.commands as Array<Record<string, unknown>> : []
  return commands.some((command) => {
    if (String(command.commandType || '') !== 'moveLabware') return false
    const params = (command.params || {}) as Record<string, unknown>
    return params.strategy === 'usingGripper'
  })
})

const instrumentsDetail = computed(() => {
  if (!instruments.value.length) return t('agent.protocol.noInstruments')
  return t('agent.protocol.instrumentsConnected', { count: instruments.value.length })
})

const deckItems = computed(() => {
  const items: DeckItem[] = []
  const modules = Array.isArray(analysisDoc.value.modules) ? analysisDoc.value.modules as Array<Record<string, unknown>> : []
  for (const module of modules) {
    const slot = extractSlot(module.location) || '—'
    const label = String(module.model || module.moduleType || 'module')
    items.push({ slot, label, short: shorten(label, 10), kind: 'module' })
  }

  const labware = Array.isArray(analysisDoc.value.labware) ? analysisDoc.value.labware as Array<Record<string, unknown>> : []
  const byId = new Map(labware.map((item) => [String(item.id || ''), item]))
  const resolveSlot = (item: Record<string, unknown>, depth = 0): string => {
    const slot = extractSlot(item.location)
    if (slot) return slot
    if (depth > 5) return ''
    const loc = item.location as Record<string, unknown> | undefined
    const parentId = loc && typeof loc.labwareId === 'string' ? loc.labwareId : ''
    const parent = parentId ? byId.get(parentId) : undefined
    return parent ? resolveSlot(parent, depth + 1) : ''
  }

  for (const lw of labware) {
    const slot = resolveSlot(lw)
    if (!slot || slot === 'offDeck') continue
    const label = String(lw.displayName || lw.loadName || 'labware')
    // Prefer top-most item in a stack for the map short label: keep all in list via unique keys
    items.push({ slot, label, short: shorten(label, 12), kind: 'labware' })
  }

  // Fallback: loadLabware / loadModule commands
  if (!items.filter((item) => item.kind === 'labware').length) {
    const commands = Array.isArray(analysisDoc.value.commands) ? analysisDoc.value.commands as Array<Record<string, unknown>> : []
    for (const command of commands) {
      const type = String(command.commandType || '')
      const params = (command.params || {}) as Record<string, unknown>
      if (type === 'loadLabware') {
        const slot = extractSlot(params.location)
        if (!slot || slot === 'offDeck') continue
        const label = String(params.loadName || 'labware')
        items.push({ slot, label, short: shorten(label, 12), kind: 'labware' })
      }
      if (type === 'loadModule') {
        const slot = extractSlot(params.location)
        if (!slot) continue
        const label = String(params.model || params.moduleType || 'module')
        items.push({ slot, label, short: shorten(label, 10), kind: 'module' })
      }
    }
  }
  return items.sort((a, b) => a.slot.localeCompare(b.slot))
})

const deckDetail = computed(() => {
  const onDeck = new Set(deckItems.value.map((item) => item.slot)).size
  if (!deckItems.value.length) return t('agent.protocol.noLabware')
  return t('agent.protocol.onDeckLabware', { count: onDeck })
})

const deckSlots = computed(() => {
  const bySlot = new Map<string, DeckItem>()
  for (const item of deckItems.value) {
    // Keep the last (often top) labware label for a slot
    bySlot.set(item.slot, item)
  }
  const ids = isOt2.value
    ? ['10', '11', '7', '8', '9', '4', '5', '6', '1', '2', '3']
    : ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3', 'D1', 'D2', 'D3']
  return ids.map((id) => ({ id, item: bySlot.get(id) || null }))
})

const selectedSlotItem = computed(() => {
  const matches = deckItems.value.filter((item) => item.slot === selectedSlot.value)
  if (!matches.length) return null
  return {
    slot: selectedSlot.value,
    label: matches.map((item) => item.label).join(' / '),
    short: matches[matches.length - 1]?.short || '',
    kind: matches[matches.length - 1]?.kind || 'labware',
  } as DeckItem
})

const sourceDetail = computed(() => {
  if (props.protocolFile?.name) return props.protocolFile.name
  return t('agent.protocol.sourceUnavailable')
})

watch(
  () => props.analysis.session_id,
  () => {
    screen.value = 'home'
    deckMode.value = 'map'
    selectedSlot.value = ''
    sourceText.value = ''
    sourceFileName.value = ''
  },
)

async function openSource() {
  screen.value = 'source'
  if (sourceText.value || !props.protocolFile) return
  sourceLoading.value = true
  sourceFileName.value = props.protocolFile.name
  try {
    const name = props.protocolFile.name.toLowerCase()
    if (name.endsWith('.zip')) {
      sourceText.value = t('agent.protocol.sourceZipHint')
      return
    }
    sourceText.value = await props.protocolFile.text()
  } catch {
    sourceText.value = ''
  } finally {
    sourceLoading.value = false
  }
}

function extractSlot(location: unknown): string {
  if (!location || typeof location !== 'object') return ''
  const loc = location as Record<string, unknown>
  if (loc.slotName) return String(loc.slotName)
  if (loc.addressableAreaName) return String(loc.addressableAreaName)
  if (typeof loc.labwareId === 'string') return ''
  return ''
}

function formatPipetteName(name: string) {
  return name.replace(/_/g, ' ')
}

function shorten(value: string, max: number) {
  const cleaned = value.replace(/^opentrons[_-]?/i, '').replace(/_/g, ' ')
  if (cleaned.length <= max) return cleaned
  return `${cleaned.slice(0, max - 1)}…`
}
</script>

<style scoped>
.prep-shell {
  --odd-black: #16212d;
  --odd-grey60: #4a4c4e;
  --odd-grey50: #737578;
  --odd-grey35: #cbcccc;
  --odd-grey30: #dedede;
  --odd-grey20: #e9e9e9;
  --odd-grey10: #f3f3f3;
  --odd-blue50: #006cfa;
  --odd-blue35: #bfdcfd;
  --odd-green60: #03683e;
  --odd-green35: #afedd3;
  --odd-green20: #e8f7ed;
  --odd-red50: #de1b1b;
  --odd-red20: #fce9e9;
  --odd-yellow35: #ffe1a4;
  --odd-white: #ffffff;

  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--odd-white);
  color: var(--odd-black);
  font-size: 10.5px;
  line-height: 1.25;
}

.prep-shell.is-expanded {
  font-size: 14px;
  line-height: 1.35;
}

.prep-home,
.prep-detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 7px 7px;
}

.prep-shell.is-expanded .prep-home,
.prep-shell.is-expanded .prep-detail {
  gap: 10px;
  padding: 14px 16px 16px;
}

.prep-header,
.prep-detail-header {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.prep-header {
  justify-content: space-between;
  padding-bottom: 2px;
}

.prep-header h3,
.prep-detail-header h3 {
  margin: 0;
  font-size: 1.08em;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.prep-header p,
.prep-detail-header p {
  margin: 1px 0 0;
  color: var(--odd-grey50);
  font-size: 0.9em;
  font-weight: 500;
}

.prep-header-actions {
  display: flex;
  align-items: center;
  gap: 5px;
}

.prep-back {
  border: 0;
  background: transparent;
  color: var(--odd-black);
  width: 24px;
  height: 24px;
  border-radius: 0;
  display: grid;
  place-items: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}

.prep-shell.is-expanded .prep-back {
  width: 36px;
  height: 36px;
}

.prep-ok,
.prep-error {
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 0.92em;
}

.prep-shell.is-expanded .prep-ok,
.prep-shell.is-expanded .prep-error {
  border-radius: 12px;
  padding: 10px 12px;
}

.prep-ok {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--odd-green20);
  color: var(--odd-green60);
}

.prep-error {
  background: var(--odd-red20);
  color: var(--odd-red50);
  max-height: 28%;
  overflow: auto;
}

.prep-error strong,
.prep-error p {
  display: block;
  margin: 0;
}

.prep-error p + p {
  margin-top: 3px;
}

.prep-rows {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 1px;
}

.prep-shell.is-expanded .prep-rows {
  gap: 8px;
}

.prep-row {
  border: 0;
  border-radius: 10px;
  background: var(--odd-grey35);
  color: inherit;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.prep-row.is-general {
  background: var(--odd-blue35);
}

.prep-shell.is-expanded .prep-row {
  border-radius: 16px;
  padding: 14px 16px;
  gap: 12px;
}

.prep-row-title {
  font-weight: 650;
  color: var(--odd-black);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prep-row-detail {
  justify-self: end;
  text-align: right;
  color: var(--odd-black);
  font-weight: 650;
  font-size: 0.92em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.prep-row-chevron {
  color: var(--odd-black);
  flex-shrink: 0;
  opacity: 0.9;
}

.prep-footer {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  padding-top: 2px;
}

.prep-play {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  background: var(--odd-grey35);
  color: var(--odd-grey50);
  display: grid;
  place-items: center;
  cursor: pointer;
  padding: 0;
}

.prep-play.is-ready {
  background: var(--odd-blue50);
  color: var(--odd-white);
}

.prep-play:disabled {
  cursor: not-allowed;
}

.prep-shell.is-expanded .prep-play {
  width: 64px;
  height: 64px;
}

.prep-tabs {
  margin-left: auto;
  display: flex;
  gap: 3px;
}

.prep-tabs button {
  border: 0;
  border-radius: 999px;
  background: var(--odd-grey20);
  color: var(--odd-grey60);
  font: inherit;
  font-size: 0.85em;
  font-weight: 600;
  padding: 3px 8px;
  cursor: pointer;
}

.prep-tabs button.is-active {
  background: var(--odd-black);
  color: var(--odd-white);
}

.prep-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prep-shell.is-expanded .prep-list {
  gap: 8px;
}

.prep-list-head {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  padding: 0 4px 2px;
  color: var(--odd-grey60);
  font-size: 0.82em;
  font-weight: 650;
}

.prep-shell.is-expanded .prep-list-head {
  grid-template-columns: 110px 1fr;
  padding: 0 8px 4px;
}

.prep-instrument {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: var(--odd-green35);
  border-radius: 8px;
  padding: 7px 8px;
}

.prep-shell.is-expanded .prep-instrument {
  border-radius: 12px;
  padding: 12px 14px;
  gap: 12px;
}

.prep-mount {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  border-radius: 4px;
  background: var(--odd-black);
  color: var(--odd-white);
  font-size: 0.78em;
  font-weight: 700;
  padding: 2px 5px;
  line-height: 1.2;
}

.prep-instrument-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.prep-instrument-copy strong {
  font-weight: 650;
}

.prep-instrument-copy small {
  color: var(--odd-green60);
  font-size: 0.88em;
  font-weight: 600;
}

.prep-list-row {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 8px;
  align-items: center;
  background: var(--odd-grey20);
  border-radius: 8px;
  padding: 6px 8px;
}

.prep-shell.is-expanded .prep-list-row {
  grid-template-columns: 72px 1fr;
  border-radius: 12px;
  padding: 10px 12px;
}

.prep-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  border-radius: 4px;
  background: var(--odd-black);
  color: var(--odd-white);
  font-size: 0.82em;
  font-weight: 700;
  padding: 2px 5px;
}

.prep-empty {
  margin: 10px 4px;
  color: var(--odd-grey50);
}

.deck-map {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  flex: 1;
  min-height: 0;
  align-content: start;
  background: var(--odd-grey10);
  border-radius: 8px;
  padding: 5px;
}

.prep-shell.is-expanded .deck-map {
  gap: 8px;
  border-radius: 12px;
  padding: 10px;
}

.deck-slot {
  border: 1px solid var(--odd-grey30);
  border-radius: 6px;
  background: var(--odd-white);
  min-height: 34px;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font: inherit;
}

.prep-shell.is-expanded .deck-slot {
  min-height: 58px;
  border-radius: 10px;
  padding: 8px;
}

.deck-slot strong {
  font-size: 0.78em;
  color: var(--odd-grey50);
  font-weight: 700;
}

.deck-slot span {
  font-size: 0.72em;
  line-height: 1.15;
  color: var(--odd-black);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.deck-slot.is-filled {
  background: var(--odd-blue35);
  border-color: #7eb6ef;
}

.deck-slot.is-module {
  background: #dbbce7;
  border-color: #cea4df;
}

.deck-selected {
  margin: 0;
  border-radius: 8px;
  background: var(--odd-grey20);
  padding: 6px 8px;
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 0.92em;
}

.prep-source {
  min-height: 0;
}

.source-code {
  flex: 1;
  min-height: 0;
  margin: 0;
  overflow: auto;
  border-radius: 8px;
  background: var(--odd-black);
  color: var(--odd-grey10);
  padding: 8px;
  font-size: 0.74em;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}

.prep-shell.is-expanded .source-code {
  border-radius: 12px;
  padding: 12px;
  font-size: 0.82em;
}
</style>
