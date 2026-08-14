<template>
  <section class="protocol-panel">
    <div class="protocol-mode-switch" role="tablist" :aria-label="t('agent.protocol.modeLabel')">
      <button
        type="button"
        role="tab"
        class="protocol-mode-btn"
        :class="{ 'is-active': panelMode === 'simulate' }"
        :aria-selected="panelMode === 'simulate'"
        @click="setPanelMode('simulate')"
      >
        {{ t('agent.protocol.modeSimulate') }}
      </button>
      <button
        type="button"
        role="tab"
        class="protocol-mode-btn"
        :class="{ 'is-active': panelMode === 'remote' }"
        :aria-selected="panelMode === 'remote'"
        @click="setPanelMode('remote')"
      >
        {{ t('agent.protocol.modeRemote') }}
      </button>
    </div>

    <div class="protocol-hero">
      <div class="flex-stage">
        <div class="flex-frame">
          <img class="flex-photo" src="/agent/flex-p2.png" alt="Opentrons Flex" draggable="false">
          <Teleport to="body" :disabled="!screenExpanded">
            <div
              v-if="screenExpanded"
              class="flex-screen-backdrop"
              @click="screenExpanded = false"
            />
            <div
              class="flex-screen"
              :class="{ 'is-expanded': screenExpanded }"
              role="region"
              :aria-label="t('agent.protocol.screenAria')"
            >
              <div class="odd-shell" :class="{ 'is-expanded': screenExpanded, 'is-remote': panelMode === 'remote' }">
                  <template v-if="panelMode === 'remote'">
                    <AgentProtocolOddRemote
                      v-if="remoteOdd"
                      :ip="remoteOdd.ip"
                      :port="remoteOdd.odd_devtools_port"
                      :name="remoteOdd.name"
                      :expanded="screenExpanded"
                      @toggle-expand="toggleScreenExpanded"
                    />
                    <div v-else class="odd-idle">
                      <header class="odd-mini-toolbar">
                        <button
                          type="button"
                          class="odd-zoom-btn"
                          :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          @click="toggleScreenExpanded"
                        >
                          <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                          <Maximize2 v-else :size="14" />
                        </button>
                      </header>
                      <strong>{{ t('agent.oddRemote.idleTitle') }}</strong>
                      <span>{{ t('agent.oddRemote.idleHint') }}</span>
                    </div>
                  </template>

                  <AgentProtocolOddHome
                    v-else-if="view === 'home'"
                    :expanded="screenExpanded"
                    :robot-name="t('agent.protocol.robotName')"
                    :version-label="selectedVersion || environment?.default_version || '—'"
                    @upload="openProtocolPicker"
                    @toggle-expand="toggleScreenExpanded"
                  />

                  <div v-else-if="view === 'analyzing'" class="odd-analyzing">
                    <header class="odd-mini-toolbar">
                      <button
                        type="button"
                        class="odd-zoom-btn"
                        :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        @click="toggleScreenExpanded"
                      >
                        <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                        <Maximize2 v-else :size="14" />
                      </button>
                    </header>
                    <LoaderCircle class="odd-spin" :size="screenExpanded ? 42 : 28" aria-hidden="true" />
                    <strong>{{ t('agent.protocol.analyzing') }}</strong>
                    <span>{{ protocolName || t('agent.protocol.untitled') }}</span>
                  </div>

                  <div v-else-if="view === 'number' && activeParameter" class="odd-detail">
                    <header class="odd-detail-header">
                      <button type="button" class="odd-back" @click="view = 'setup'">
                        <ChevronLeft :size="screenExpanded ? 22 : 16" />
                      </button>
                      <div class="odd-detail-copy">
                        <h3>{{ activeParameter.displayName || activeParameter.variableName }}</h3>
                        <p>{{ activeParameter.description || '' }}</p>
                      </div>
                      <button
                        type="button"
                        class="odd-zoom-btn"
                        :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        @click="toggleScreenExpanded"
                      >
                        <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                        <Maximize2 v-else :size="14" />
                      </button>
                    </header>
                    <label class="odd-number-field">
                      <span>{{ t('agent.protocol.value') }}</span>
                      <input
                        v-model.number="draftNumber"
                        type="number"
                        :min="activeParameter.minimum"
                        :max="activeParameter.maximum"
                        @keydown.enter.prevent="confirmNumber"
                      >
                      <small v-if="activeParameter.unit">{{ activeParameter.unit }}</small>
                    </label>
                    <button type="button" class="odd-primary-btn" @click="confirmNumber">{{ t('agent.protocol.confirm') }}</button>
                  </div>

                  <div v-else-if="view === 'choice' && activeParameter" class="odd-detail">
                    <header class="odd-detail-header">
                      <button type="button" class="odd-back" @click="view = 'setup'">
                        <ChevronLeft :size="screenExpanded ? 22 : 16" />
                      </button>
                      <div class="odd-detail-copy">
                        <h3>{{ activeParameter.displayName || activeParameter.variableName }}</h3>
                        <p>{{ activeParameter.description || '' }}</p>
                      </div>
                      <button
                        type="button"
                        class="odd-zoom-btn"
                        :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        @click="toggleScreenExpanded"
                      >
                        <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                        <Maximize2 v-else :size="14" />
                      </button>
                    </header>
                    <div class="odd-choice-list">
                      <button
                        v-for="choice in choiceOptions(activeParameter)"
                        :key="String(choice.value)"
                        type="button"
                        class="odd-row"
                        :class="{ 'is-ready': values[activeParameter.variableName] === choice.value }"
                        @click="setChoice(choice.value)"
                      >
                        <span>{{ choice.displayName }}</span>
                        <Check v-if="values[activeParameter.variableName] === choice.value" :size="screenExpanded ? 18 : 14" />
                      </button>
                    </div>
                  </div>

                  <div v-else-if="view === 'csv' && activeParameter" class="odd-detail">
                    <header class="odd-detail-header">
                      <button type="button" class="odd-back" @click="view = 'setup'">
                        <ChevronLeft :size="screenExpanded ? 22 : 16" />
                      </button>
                      <div class="odd-detail-copy">
                        <h3>{{ activeParameter.displayName || activeParameter.variableName }}</h3>
                        <p>{{ activeParameter.description || t('agent.protocol.csvHint') }}</p>
                      </div>
                      <button
                        type="button"
                        class="odd-zoom-btn"
                        :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                        @click="toggleScreenExpanded"
                      >
                        <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                        <Maximize2 v-else :size="14" />
                      </button>
                    </header>
                    <label class="odd-primary-btn odd-file-label">
                      {{ csvFiles[activeParameter.variableName]?.name || t('agent.protocol.chooseCsv') }}
                      <input
                        class="agent-file-input"
                        type="file"
                        accept=".csv,text/csv"
                        @change="onCsvSelected($event, activeParameter.variableName)"
                      >
                    </label>
                    <p v-if="csvFiles[activeParameter.variableName]" class="odd-file-meta">
                      {{ csvFiles[activeParameter.variableName]?.name }}
                    </p>
                  </div>

                  <div v-else-if="view === 'prepare' && analysis" class="odd-prepare-host">
                    <AgentProtocolPrepareScreen
                      :analysis="analysis"
                      :protocol-name="protocolName || t('agent.protocol.untitled')"
                      :protocol-file="protocolFiles[0] || null"
                      :expanded="screenExpanded"
                      @start-run="view = 'running'"
                    >
                      <template #actions>
                        <button
                          type="button"
                          class="odd-zoom-btn"
                          :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          @click="toggleScreenExpanded"
                        >
                          <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                          <Maximize2 v-else :size="14" />
                        </button>
                        <button type="button" class="odd-circle is-cancel" :title="t('agent.protocol.reset')" @click="resetAll">
                          <X :size="screenExpanded ? 18 : 13" />
                        </button>
                        <button type="button" class="odd-circle is-start" :title="t('agent.protocol.backToSetup')" @click="view = 'setup'">
                          <ChevronLeft :size="screenExpanded ? 18 : 13" />
                        </button>
                      </template>
                    </AgentProtocolPrepareScreen>
                  </div>

                  <div v-else-if="view === 'running' && analysis" class="odd-run-host">
                    <button
                      type="button"
                      class="odd-zoom-btn odd-zoom-float"
                      :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                      :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                      @click="toggleScreenExpanded"
                    >
                      <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                      <Maximize2 v-else :size="14" />
                    </button>
                    <AgentProtocolRunScreen
                      :protocol-name="protocolName || t('agent.protocol.untitled')"
                      :commands="runCommands"
                      :analysis-ok="analysis.result === 'ok'"
                      :error-detail="runErrorDetail"
                      :expanded="screenExpanded"
                      @dashboard="view = 'prepare'"
                    />
                  </div>

                  <div v-else class="odd-setup">
                    <header class="odd-setup-header">
                      <div>
                        <h3>{{ t('agent.protocol.parametersTitle') }}</h3>
                        <p>{{ protocolName || t('agent.protocol.untitled') }}</p>
                      </div>
                      <div class="odd-header-actions">
                        <button
                          type="button"
                          class="odd-zoom-btn"
                          :title="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          :aria-label="screenExpanded ? t('agent.protocol.collapseScreen') : t('agent.protocol.expandScreen')"
                          @click="toggleScreenExpanded"
                        >
                          <Minimize2 v-if="screenExpanded" :size="screenExpanded ? 18 : 14" />
                          <Maximize2 v-else :size="14" />
                        </button>
                        <button type="button" class="odd-circle is-cancel" :title="t('agent.protocol.reset')" :disabled="busy" @click="resetAll">
                          <X :size="screenExpanded ? 18 : 13" />
                        </button>
                        <button
                          type="button"
                          class="odd-circle is-start"
                          :title="t('agent.protocol.startAnalysis')"
                          :disabled="busy || !canAnalyze"
                          @click="runAnalysis(false)"
                        >
                          <Play :size="screenExpanded ? 18 : 13" fill="currentColor" />
                        </button>
                      </div>
                    </header>

                    <div class="odd-rows">
                      <div v-if="error && parameters.length" class="odd-error-box" role="alert">
                        <strong>{{ t('agent.protocol.errors') }}</strong>
                        <p>{{ error }}</p>
                      </div>
                      <button
                        v-for="parameter in parameters"
                        :key="parameter.variableName"
                        type="button"
                        class="odd-row"
                        :class="parameterRowClass(parameter)"
                        @click="openParameter(parameter)"
                      >
                        <span class="odd-row-main">
                          <i v-if="isParameterReady(parameter)" class="odd-check" aria-hidden="true">
                            <Check :size="screenExpanded ? 14 : 11" />
                          </i>
                          <strong>{{ parameter.displayName || parameter.variableName }}</strong>
                        </span>
                        <span class="odd-row-meta">
                          {{ parameterSummary(parameter) }}
                          <ChevronRight :size="screenExpanded ? 18 : 13" aria-hidden="true" />
                        </span>
                      </button>

                      <div v-if="!parameters.length" class="odd-empty-params">
                        {{ t('agent.protocol.noParameters') }}
                      </div>
                    </div>

                    <footer class="odd-setup-footer">
                      <button type="button" class="odd-primary-btn" :disabled="busy || !canAnalyze" @click="runAnalysis(false)">
                        {{ t('agent.protocol.startAnalysis') }}
                      </button>
                    </footer>
                  </div>
                </div>
              </div>
          </Teleport>
        </div>
      </div>

      <aside class="protocol-copy" :class="{ 'is-remote': panelMode === 'remote' }">
        <template v-if="panelMode === 'remote'">
          <h2>{{ t('agent.oddRemote.title') }}</h2>
          <p class="protocol-lead">{{ t('agent.oddRemote.subtitle') }}</p>

          <div class="remote-panel">
            <div class="remote-subnav" role="tablist" :aria-label="t('agent.oddRemote.subnavLabel')">
              <button
                type="button"
                role="tab"
                class="remote-subnav-btn"
                :class="{ 'is-active': remoteSubTab === 'connect' }"
                :aria-selected="remoteSubTab === 'connect'"
                @click="remoteSubTab = 'connect'"
              >
                {{ t('agent.oddRemote.tabConnect') }}
              </button>
              <button
                type="button"
                role="tab"
                class="remote-subnav-btn"
                :class="{ 'is-active': remoteSubTab === 'upload' }"
                :aria-selected="remoteSubTab === 'upload'"
                @click="remoteSubTab = 'upload'"
              >
                {{ t('agent.oddRemote.tabUpload') }}
              </button>
            </div>

            <div v-if="remoteSubTab === 'connect'" class="remote-tab-pane">
              <label class="protocol-version-field remote-field">
                <span class="remote-field-label">
                  {{ t('agent.protocol.oddSelectDevice') }}
                  <button type="button" class="protocol-inline-link" :disabled="oddLoading" @click="loadOddDevices">
                    {{ oddLoading ? t('agent.protocol.oddLoading') : t('agent.protocol.oddRefresh') }}
                  </button>
                </span>
                <select v-model="selectedOddIp" :disabled="oddLoading || !oddDevices.length">
                  <option value="">{{ t('agent.protocol.oddSelectPlaceholder') }}</option>
                  <option
                    v-for="device in oddDevices"
                    :key="device.ip"
                    :value="device.ip"
                  >
                    {{ device.name || device.ip }}
                    ({{ device.ip }}){{ device.odd_available ? '' : ` — ${t('agent.protocol.oddNotReady')}` }}
                  </option>
                </select>
                <small>{{ t('agent.protocol.oddConnectHint', { port: oddDevtoolsPort }) }}</small>
              </label>

              <div class="remote-actions">
                <button
                  type="button"
                  class="protocol-upload-btn protocol-odd-btn"
                  :disabled="!selectedOddIp || oddLoading || !selectedOddDevice?.odd_available"
                  @click="connectOddDevice"
                >
                  {{ remoteOdd ? t('agent.protocol.oddReconnect') : t('agent.protocol.oddConnect') }}
                </button>
                <button
                  v-if="remoteOdd"
                  type="button"
                  class="protocol-inline-link"
                  @click="disconnectOddDevice"
                >
                  {{ t('agent.protocol.oddDisconnect') }}
                </button>
              </div>
              <p v-if="remoteOdd" class="protocol-odd-live">
                {{ t('agent.protocol.oddLive', { name: remoteOdd.name || remoteOdd.ip, port: remoteOdd.odd_devtools_port }) }}
              </p>
              <p v-if="oddError" class="agent-panel-error">{{ oddError }}</p>
            </div>

            <div v-else class="remote-tab-pane">
              <input
                ref="remoteLabwareInput"
                class="agent-file-input"
                type="file"
                accept=".json,application/json"
                multiple
                :disabled="remoteUploading || !remoteTargetIp"
                @change="onRemoteLabwareSelected"
              >

              <p class="protocol-lead">
                {{ t('agent.oddRemote.uploadHintBefore') }}
                <button
                  type="button"
                  class="protocol-inline-link"
                  :disabled="remoteUploading || !remoteTargetIp"
                  @click="remoteLabwareInput?.click()"
                >{{ t('agent.oddRemote.uploadHintLink') }}</button>{{ t('agent.oddRemote.uploadHintAfter') }}
              </p>
              <p v-if="remoteLabwareFiles.length" class="protocol-labware-meta">
                <span>{{ t('agent.protocol.labwareUploaded', { name: remoteLabwareFiles.map((file) => file.name).join(', ') }) }}</span>
                <button type="button" class="protocol-inline-link" :disabled="remoteUploading" @click="clearRemoteLabware">
                  {{ t('agent.protocol.labwareClear') }}
                </button>
              </p>

              <label class="protocol-upload-btn" :class="{ 'is-disabled': remoteUploading || !remoteTargetIp }">
                <Upload :size="16" aria-hidden="true" />
                {{ remoteUploading ? t('agent.oddRemote.uploading') : t('agent.oddRemote.uploadAction') }}
                <input
                  ref="remoteProtocolInput"
                  class="agent-file-input"
                  type="file"
                  accept=".py,.json,.zip,text/x-python,application/json"
                  :disabled="remoteUploading || !remoteTargetIp"
                  @change="onRemoteProtocolSelected"
                >
              </label>
              <p v-if="remoteUploadMessage" class="protocol-odd-live">{{ remoteUploadMessage }}</p>
              <p v-if="remoteUploadError" class="agent-panel-error">{{ remoteUploadError }}</p>

              <div class="remote-divider" role="separator" />

              <p class="remote-section-title">{{ t('agent.oddRemote.csvTitle') }}</p>
              <p class="protocol-odd-hint">{{ t('agent.oddRemote.csvHint') }}</p>

              <input
                ref="remoteCsvInput"
                class="agent-file-input"
                type="file"
                accept=".csv,text/csv"
                multiple
                :disabled="remoteCsvBusy || !remoteTargetIp"
                @change="onRemoteCsvSelected"
              >

              <div class="remote-actions">
                <button
                  type="button"
                  class="protocol-upload-btn protocol-odd-btn"
                  :disabled="remoteCsvBusy || !remoteTargetIp"
                  @click="remoteCsvInput?.click()"
                >
                  {{ remoteCsvBusy ? t('agent.oddRemote.csvUploading') : t('agent.oddRemote.csvUpload') }}
                </button>
                <button
                  type="button"
                  class="protocol-inline-link"
                  :disabled="remoteCsvBusy || !remoteTargetIp"
                  @click="loadRemoteDataFiles"
                >
                  {{ t('agent.oddRemote.csvRefresh') }}
                </button>
              </div>

              <label v-if="remoteDataFiles.length" class="protocol-version-field remote-field">
                <span>{{ t('agent.oddRemote.csvOnRobot') }}</span>
                <select v-model="remoteSelectedCsvId" :disabled="remoteCsvBusy">
                  <option value="">{{ t('agent.oddRemote.csvSelectPlaceholder') }}</option>
                  <option
                    v-for="file in remoteDataFiles"
                    :key="file.id"
                    :value="file.id"
                  >
                    {{ file.name }} ({{ file.id.slice(0, 8) }})
                  </option>
                </select>
                <small>{{ t('agent.oddRemote.csvCatalogHint') }}</small>
              </label>
              <p v-else-if="remoteTargetIp && !remoteCsvBusy" class="protocol-odd-hint">
                {{ t('agent.oddRemote.csvEmpty') }}
              </p>

              <div v-if="remoteCsvParams.length" class="remote-csv-bind">
                <p class="remote-section-title">{{ t('agent.oddRemote.csvBindTitle') }}</p>
                <p class="protocol-odd-hint">{{ t('agent.oddRemote.csvBindHint') }}</p>
                <label
                  v-for="param in remoteCsvParams"
                  :key="param.variableName"
                  class="protocol-version-field remote-field"
                >
                  <span>{{ param.displayName || param.variableName }}</span>
                  <select v-model="remoteCsvBindings[param.variableName]" :disabled="remoteCsvBusy">
                    <option value="">{{ t('agent.oddRemote.csvSelectPlaceholder') }}</option>
                    <option
                      v-for="file in remoteDataFiles"
                      :key="`${param.variableName}-${file.id}`"
                      :value="file.id"
                    >
                      {{ file.name }}
                    </option>
                  </select>
                </label>
                <div class="remote-actions">
                  <button
                    type="button"
                    class="protocol-upload-btn protocol-odd-btn"
                    :disabled="!canRemoteAnalyzeWithCsv"
                    @click="analyzeRemoteWithCsv"
                  >
                    {{ remoteCsvBusy ? t('agent.oddRemote.csvAnalyzing') : t('agent.oddRemote.csvAnalyze') }}
                  </button>
                </div>
              </div>
              <p v-if="remoteCsvMessage" class="protocol-odd-live">{{ remoteCsvMessage }}</p>
              <p v-if="remoteCsvError" class="agent-panel-error">{{ remoteCsvError }}</p>
            </div>
          </div>
        </template>

        <template v-else>
          <h2>{{ t('agent.protocol.title') }}</h2>
          <p class="protocol-lead">
            {{ t('agent.protocol.subtitle') }}
            <button
              type="button"
              class="protocol-inline-link"
              :disabled="busy"
              @click="openLabwarePicker"
            >{{ t('agent.protocol.subtitleUpload') }}</button>{{ t('agent.protocol.subtitleEnd') }}
          </p>

          <input
            ref="labwareInput"
            class="agent-file-input"
            type="file"
            accept=".json,application/json"
            multiple
            :disabled="busy"
            @change="onLabwareSelected"
          >
          <p v-if="labwareFiles.length" class="protocol-labware-meta">
            <span>{{ t('agent.protocol.labwareUploaded', { name: labwareFiles.map((file) => file.name).join(', ') }) }}</span>
            <button type="button" class="protocol-inline-link" :disabled="busy" @click="clearLabware">{{ t('agent.protocol.labwareClear') }}</button>
          </p>
          <label class="protocol-version-field">
            <span>{{ t('agent.protocol.version') }}</span>
            <select v-model="selectedVersion" :disabled="busy || !versionOptions.length">
              <option v-for="version in versionOptions" :key="version" :value="version">
                {{ version }}{{ version === environment?.default_version ? ` (${t('agent.protocol.versionLatest')})` : '' }}
              </option>
            </select>
            <small>{{ t('agent.protocol.versionHint') }}</small>
          </label>
          <label class="protocol-upload-btn">
            <Upload :size="16" aria-hidden="true" />
            {{ t('agent.protocol.upload') }}
            <input
              ref="protocolInput"
              class="agent-file-input"
              type="file"
              accept=".py,.json,.zip,text/x-python,application/json"
              :disabled="busy"
              @change="onProtocolSelected"
            >
          </label>
          <p v-if="environment && !environment.available" class="protocol-env is-bad">
            <span class="protocol-env-dot" aria-hidden="true" />
            <span>{{ environment.detail }}</span>
          </p>
          <p v-if="error" class="agent-panel-error">{{ error }}</p>
        </template>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  Maximize2,
  Minimize2,
  Play,
  Upload,
  X,
} from '@lucide/vue'
import AgentProtocolOddHome from '@/views/agent/AgentProtocolOddHome.vue'
import AgentProtocolOddRemote from '@/views/agent/AgentProtocolOddRemote.vue'
import AgentProtocolPrepareScreen from '@/views/agent/AgentProtocolPrepareScreen.vue'
import AgentProtocolRunScreen from '@/views/agent/AgentProtocolRunScreen.vue'
import {
  agentProtocolAnalysisApi,
  type OddRemoteDevice,
  type ProtocolAnalysisEnvironment,
  type ProtocolAnalysisResult,
  type ProtocolRuntimeParameter,
} from '@/scripts/modules/agent/agentWorkspaceApi'
import { robotApi } from '@/scripts/api'

type ScreenView = 'home' | 'setup' | 'number' | 'choice' | 'csv' | 'analyzing' | 'prepare' | 'running' | 'result'
type PanelMode = 'simulate' | 'remote'
type RemoteSubTab = 'connect' | 'upload'

const { t } = useI18n()

const protocolInput = ref<HTMLInputElement | null>(null)
const labwareInput = ref<HTMLInputElement | null>(null)
const environment = ref<ProtocolAnalysisEnvironment | null>(null)
const loadingEnv = ref(false)
const busy = ref(false)
const error = ref('')
const view = ref<ScreenView>('home')
const protocolFiles = ref<File[]>([])
const labwareFiles = ref<File[]>([])
const protocolName = ref('')
const parameters = ref<ProtocolRuntimeParameter[]>([])
const values = reactive<Record<string, boolean | number | string>>({})
const csvFiles = reactive<Record<string, File | undefined>>({})
const analysis = ref<ProtocolAnalysisResult | null>(null)
const activeParameter = ref<ProtocolRuntimeParameter | null>(null)
const draftNumber = ref<number>(0)
const screenExpanded = ref(false)
const selectedVersion = ref('')
const panelMode = ref<PanelMode>('simulate')
const remoteSubTab = ref<RemoteSubTab>('connect')
const oddDevices = ref<OddRemoteDevice[]>([])
const selectedOddIp = ref('')
const remoteOdd = ref<OddRemoteDevice | null>(null)
const oddLoading = ref(false)
const oddError = ref('')
const oddDevtoolsPort = ref(9223)
const remoteLabwareInput = ref<HTMLInputElement | null>(null)
const remoteProtocolInput = ref<HTMLInputElement | null>(null)
const remoteLabwareFiles = ref<File[]>([])
const remoteProtocolFiles = ref<File[]>([])
const remoteUploading = ref(false)
const remoteUploadMessage = ref('')
const remoteUploadError = ref('')
const remoteCsvInput = ref<HTMLInputElement | null>(null)
const remoteDataFiles = ref<Array<{ id: string; name: string; createdAt?: string }>>([])
const remoteSelectedCsvId = ref('')
const remoteCsvBusy = ref(false)
const remoteCsvMessage = ref('')
const remoteCsvError = ref('')
const remoteProtocolId = ref('')
const remoteCsvParams = ref<Array<{ variableName: string; displayName: string }>>([])
const remoteCsvBindings = reactive<Record<string, string>>({})

const versionOptions = computed(() => environment.value?.versions || [])
const selectedOddDevice = computed(
  () => oddDevices.value.find((item) => item.ip === selectedOddIp.value) || null,
)
const remoteTargetIp = computed(() => remoteOdd.value?.ip || selectedOddIp.value || '')
const remoteTargetPort = computed(
  () => remoteOdd.value?.api_port || selectedOddDevice.value?.api_port || 31950,
)
const canRemoteAnalyzeWithCsv = computed(() => {
  if (!remoteProtocolId.value || remoteCsvBusy.value || !remoteCsvParams.value.length) return false
  return remoteCsvParams.value.every((param) => Boolean(remoteCsvBindings[param.variableName]))
})

const canAnalyze = computed(() => protocolFiles.value.length > 0 && Boolean(environment.value?.available))

const runCommands = computed(() => {
  const commands = analysis.value?.analysis?.commands
  return Array.isArray(commands) ? commands as Array<Record<string, unknown>> : []
})

const runErrorDetail = computed(() => {
  const first = analysis.value?.errors?.[0]?.detail
  return first || ''
})

function choiceOptions(parameter: ProtocolRuntimeParameter) {
  if (parameter.choices?.length) return parameter.choices
  if (parameter.type === 'bool') {
    return [
      { displayName: t('agent.protocol.boolTrue'), value: true },
      { displayName: t('agent.protocol.boolFalse'), value: false },
    ]
  }
  return []
}

function isCsv(parameter: ProtocolRuntimeParameter) {
  return parameter.type === 'csv_file'
}

function isParameterReady(parameter: ProtocolRuntimeParameter) {
  if (isCsv(parameter)) return Boolean(csvFiles[parameter.variableName])
  const current = values[parameter.variableName]
  return current !== undefined && current !== null && current !== ''
}

function parameterRowClass(parameter: ProtocolRuntimeParameter) {
  return {
    'is-ready': isParameterReady(parameter),
    'is-missing': isCsv(parameter) && !csvFiles[parameter.variableName],
  }
}

function parameterSummary(parameter: ProtocolRuntimeParameter) {
  if (isCsv(parameter)) {
    return csvFiles[parameter.variableName]?.name || t('agent.protocol.csvRequired')
  }
  const current = values[parameter.variableName]
  if (parameter.choices?.length) {
    const match = parameter.choices.find((item) => item.value === current)
    return match?.displayName || String(current ?? '')
  }
  if (parameter.type === 'bool') {
    return current ? t('agent.protocol.boolTrue') : t('agent.protocol.boolFalse')
  }
  const unit = parameter.unit ? ` ${parameter.unit}` : ''
  return `${current ?? ''}${unit}`
}

async function loadEnvironment() {
  loadingEnv.value = true
  error.value = ''
  try {
    environment.value = await agentProtocolAnalysisApi.environment()
    if (!selectedVersion.value) {
      selectedVersion.value = environment.value.default_version
        || environment.value.selected_version
        || environment.value.versions?.[0]
        || ''
    } else if (
      environment.value.versions?.length
      && !environment.value.versions.includes(selectedVersion.value)
    ) {
      selectedVersion.value = environment.value.default_version || environment.value.versions[0] || ''
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('agent.protocol.envFailed')
  } finally {
    loadingEnv.value = false
  }
}

function seedParameters(list: ProtocolRuntimeParameter[], resetValues = true) {
  parameters.value = list
  if (!resetValues) return
  for (const key of Object.keys(values)) delete values[key]
  for (const key of Object.keys(csvFiles)) delete csvFiles[key]
  for (const parameter of list) {
    if (isCsv(parameter)) continue
    const initial = parameter.value ?? parameter.default
    if (initial !== undefined && initial !== null) {
      values[parameter.variableName] = initial as boolean | number | string
    }
  }
}

function resetAll() {
  protocolFiles.value = []
  labwareFiles.value = []
  protocolName.value = ''
  parameters.value = []
  analysis.value = null
  activeParameter.value = null
  error.value = ''
  for (const key of Object.keys(values)) delete values[key]
  for (const key of Object.keys(csvFiles)) delete csvFiles[key]
  view.value = 'home'
  screenExpanded.value = false
  if (protocolInput.value) protocolInput.value.value = ''
  if (labwareInput.value) labwareInput.value.value = ''
}

function openProtocolPicker() {
  protocolInput.value?.click()
}

function setPanelMode(mode: PanelMode) {
  if (panelMode.value === mode) return
  if (mode === 'simulate') {
    remoteOdd.value = null
  } else {
    remoteSubTab.value = 'connect'
    void loadOddDevices()
    if (remoteTargetIp.value) void loadRemoteDataFiles()
  }
  panelMode.value = mode
}

async function loadOddDevices() {
  oddLoading.value = true
  oddError.value = ''
  try {
    const result = await agentProtocolAnalysisApi.listOddDevices()
    oddDevices.value = result.devices || []
    oddDevtoolsPort.value = result.devtools_port || 9223
    if (selectedOddIp.value && !oddDevices.value.some((item) => item.ip === selectedOddIp.value)) {
      selectedOddIp.value = ''
    }
    if (!selectedOddIp.value) {
      const ready = oddDevices.value.find((item) => item.odd_available)
      if (ready) selectedOddIp.value = ready.ip
    }
  } catch (err) {
    oddError.value = err instanceof Error ? err.message : t('agent.protocol.oddLoadFailed')
  } finally {
    oddLoading.value = false
  }
}

async function connectOddDevice() {
  const device = oddDevices.value.find((item) => item.ip === selectedOddIp.value)
  if (!device) {
    oddError.value = t('agent.protocol.oddSelectPlaceholder')
    return
  }
  if (!device.odd_available) {
    oddError.value = device.odd_detail || t('agent.protocol.oddNotReady')
    return
  }
  oddError.value = ''
  try {
    // Probe over HTTP /json only — do not open a CDP debugger before screencast,
    // or Chromium will kick the live stream and the screen stays black.
    const probe = await agentProtocolAnalysisApi.oddProbe(device.ip, device.odd_devtools_port)
    if (!probe.available) {
      oddError.value = probe.detail || t('agent.protocol.oddNotReady')
      remoteOdd.value = null
      return
    }
    // Remount stream cleanly if reconnecting the same device.
    if (remoteOdd.value?.ip === device.ip) {
      remoteOdd.value = null
      await nextTick()
    }
    remoteOdd.value = device
    void loadRemoteDataFiles()
  } catch (err) {
    oddError.value = err instanceof Error ? err.message : t('agent.protocol.oddConnectFailed')
    remoteOdd.value = null
  }
}

function disconnectOddDevice() {
  remoteOdd.value = null
}

function onRemoteLabwareSelected(event: Event) {
  const input = event.target as HTMLInputElement
  remoteLabwareFiles.value = Array.from(input.files || [])
  remoteUploadError.value = ''
  remoteUploadMessage.value = ''
}

async function onRemoteProtocolSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  remoteProtocolFiles.value = files
  remoteUploadError.value = ''
  remoteUploadMessage.value = ''
  await uploadToRobot()
}

function clearRemoteLabware() {
  remoteLabwareFiles.value = []
  if (remoteLabwareInput.value) remoteLabwareInput.value.value = ''
}

function apiErrorDetail(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { detail?: unknown; message?: unknown } } }).response?.data
    if (typeof data?.detail === 'string') return data.detail
    if (typeof data?.message === 'string') return data.message
  }
  if (err instanceof Error && err.message) return err.message
  return t('errors.unknown')
}

async function loadRemoteDataFiles() {
  const ip = remoteTargetIp.value
  if (!ip) return
  remoteCsvBusy.value = true
  remoteCsvError.value = ''
  try {
    const response = await robotApi.listDataFiles(ip, remoteTargetPort.value)
    const files = ((response.data?.data as { files?: unknown[] } | undefined)?.files || []) as Array<Record<string, unknown>>
    remoteDataFiles.value = files
      .map((item) => ({
        id: String(item.id || ''),
        name: String(item.name || item.id || 'csv'),
        createdAt: item.createdAt ? String(item.createdAt) : undefined,
      }))
      .filter((item) => item.id)
      .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
    if (remoteSelectedCsvId.value && !remoteDataFiles.value.some((item) => item.id === remoteSelectedCsvId.value)) {
      remoteSelectedCsvId.value = ''
    }
  } catch (err) {
    remoteCsvError.value = t('agent.oddRemote.csvLoadFailed', { error: apiErrorDetail(err) })
  } finally {
    remoteCsvBusy.value = false
  }
}

async function onRemoteCsvSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  const ip = remoteTargetIp.value
  if (!ip || !files.length) return
  remoteCsvBusy.value = true
  remoteCsvError.value = ''
  remoteCsvMessage.value = ''
  try {
    let lastId = ''
    for (const file of files) {
      const response = await robotApi.uploadDataFile(ip, file, remoteTargetPort.value)
      const data = (response.data?.data || {}) as Record<string, unknown>
      lastId = String(data.id || lastId)
    }
    await loadRemoteDataFiles()
    if (lastId) remoteSelectedCsvId.value = lastId
    remoteCsvMessage.value = t('agent.oddRemote.csvUploadSuccess', { count: files.length })
  } catch (err) {
    remoteCsvError.value = t('agent.oddRemote.csvUploadFailed', { error: apiErrorDetail(err) })
  } finally {
    remoteCsvBusy.value = false
  }
}

function extractCsvParams(analyses: unknown[]): Array<{ variableName: string; displayName: string }> {
  const found = new Map<string, { variableName: string; displayName: string }>()
  for (const item of analyses) {
    if (!item || typeof item !== 'object') continue
    const params = (item as { runTimeParameters?: unknown[] }).runTimeParameters
    if (!Array.isArray(params)) continue
    for (const param of params) {
      if (!param || typeof param !== 'object') continue
      const record = param as Record<string, unknown>
      if (String(record.type || '') !== 'csv_file') continue
      const variableName = String(record.variableName || '').trim()
      if (!variableName) continue
      found.set(variableName, {
        variableName,
        displayName: String(record.displayName || variableName),
      })
    }
  }
  return Array.from(found.values())
}

async function refreshRemoteCsvParams(protocolId: string) {
  const ip = remoteTargetIp.value
  if (!ip || !protocolId) return
  try {
    const response = await robotApi.getProtocolAnalyses(ip, protocolId, remoteTargetPort.value)
    const analyses = ((response.data?.data as { analyses?: unknown[] } | undefined)?.analyses || []) as unknown[]
    remoteCsvParams.value = extractCsvParams(analyses)
    for (const param of remoteCsvParams.value) {
      if (!remoteCsvBindings[param.variableName]) {
        remoteCsvBindings[param.variableName] = remoteSelectedCsvId.value || ''
      }
    }
  } catch {
    // Keep upload success even if analysis params are not ready yet.
  }
}

async function analyzeRemoteWithCsv() {
  const ip = remoteTargetIp.value
  const protocolId = remoteProtocolId.value
  if (!ip || !protocolId || !canRemoteAnalyzeWithCsv.value) return
  remoteCsvBusy.value = true
  remoteCsvError.value = ''
  remoteCsvMessage.value = ''
  try {
    const runTimeParameterFiles: Record<string, string> = {}
    for (const param of remoteCsvParams.value) {
      const fileId = remoteCsvBindings[param.variableName]
      if (fileId) runTimeParameterFiles[param.variableName] = fileId
    }
    await robotApi.analyzeProtocol(
      ip,
      protocolId,
      {
        runTimeParameterValues: {},
        runTimeParameterFiles,
        forceReAnalyze: true,
      },
      remoteTargetPort.value,
    )
    remoteCsvMessage.value = t('agent.oddRemote.csvAnalyzeSuccess')
    await refreshRemoteCsvParams(protocolId)
  } catch (err) {
    remoteCsvError.value = t('agent.oddRemote.csvAnalyzeFailed', { error: apiErrorDetail(err) })
  } finally {
    remoteCsvBusy.value = false
  }
}

async function uploadToRobot() {
  const ip = remoteTargetIp.value
  if (!ip || !remoteProtocolFiles.value.length) {
    remoteUploadError.value = t('agent.oddRemote.needDeviceAndProtocol')
    return
  }
  remoteUploading.value = true
  remoteUploadError.value = ''
  remoteUploadMessage.value = ''
  remoteCsvError.value = ''
  remoteCsvMessage.value = ''
  try {
    const files = [...remoteProtocolFiles.value, ...remoteLabwareFiles.value]
    const response = await robotApi.uploadProtocol(ip, files, { port: remoteTargetPort.value })
    const data = (response.data?.data || {}) as Record<string, unknown>
    const protocolId = String(data.id || '')
    const meta = (data.metadata || {}) as Record<string, unknown>
    const uploadedName = String(meta.protocolName || meta.protocol_name || remoteProtocolFiles.value[0]?.name || protocolId)
    remoteProtocolId.value = protocolId
    const runTimeParameterFiles: Record<string, string> = {}
    for (const [variableName, fileId] of Object.entries(remoteCsvBindings)) {
      if (fileId) runTimeParameterFiles[variableName] = fileId
    }
    if (protocolId) {
      try {
        await robotApi.analyzeProtocol(
          ip,
          protocolId,
          {
            runTimeParameterValues: {},
            runTimeParameterFiles,
            forceReAnalyze: true,
          },
          remoteTargetPort.value,
        )
      } catch {
        // Upload already succeeded; analysis may already be running on-robot.
      }
      await loadRemoteDataFiles()
      await refreshRemoteCsvParams(protocolId)
    }
    remoteUploadMessage.value = protocolId
      ? t('agent.oddRemote.uploadSuccess', { name: uploadedName, id: protocolId })
      : t('agent.oddRemote.uploadSuccessSimple', { name: uploadedName })
  } catch (err) {
    remoteUploadError.value = t('agent.oddRemote.uploadFailed', { error: apiErrorDetail(err) })
  } finally {
    remoteUploading.value = false
  }
}

function toggleScreenExpanded() {
  screenExpanded.value = !screenExpanded.value
}

function onScreenKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && screenExpanded.value) {
    screenExpanded.value = false
  }
}

async function onProtocolSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  protocolFiles.value = [file]
  protocolName.value = file.name
  await runAnalysis(true)
}

function openLabwarePicker() {
  labwareInput.value?.click()
}

function clearLabware() {
  labwareFiles.value = []
  if (labwareInput.value) labwareInput.value.value = ''
}

async function onLabwareSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  labwareFiles.value = files
  if (protocolFiles.value.length) {
    await runAnalysis(true)
  }
}

async function runAnalysis(discoverOnly: boolean) {
  if (!protocolFiles.value.length) {
    error.value = t('agent.protocol.needProtocol')
    return
  }
  if (!environment.value?.available) {
    error.value = environment.value?.detail || t('agent.protocol.envFailed')
    return
  }

  busy.value = true
  error.value = ''
  view.value = 'analyzing'
  try {
    const csvPayload = Object.entries(csvFiles)
      .filter((entry): entry is [string, File] => Boolean(entry[1]))
      .map(([variableName, file]) => ({ variableName, file }))

    const rtpValues = discoverOnly ? {} : { ...values }
    const result = await agentProtocolAnalysisApi.analyze({
      protocolFiles: protocolFiles.value,
      labwareFiles: labwareFiles.value,
      rtpValues,
      csvFiles: discoverOnly ? [] : csvPayload,
      opentronsVersion: selectedVersion.value || undefined,
    })
    analysis.value = result
    protocolName.value = result.protocol_name || protocolName.value
    seedParameters(result.run_time_parameters || [], discoverOnly)

    if (discoverOnly) {
      // Empty RTP + analysis error means load failed before parameters were collected
      // (not "protocol has no parameters" / not "defaults skipped the form").
      if (!parameters.value.length && result.errors?.length) {
        error.value = result.errors[0]?.detail || t('agent.protocol.analyzeFailed')
        view.value = 'prepare'
        return
      }
      if (result.errors?.length && result.result !== 'ok') {
        error.value = result.errors[0]?.detail || ''
      }
      view.value = 'setup'
      return
    }

    if (result.result === 'parameter-value-required') {
      view.value = 'setup'
      error.value = result.errors?.[0]?.detail || t('agent.protocol.resultNeedParams')
      return
    }
    // Analysis finished → Prepare to run (instruments / deck / source). Run is separate.
    error.value = ''
    view.value = 'prepare'
  } catch (err) {
    error.value = err instanceof Error ? err.message : t('agent.protocol.analyzeFailed')
    view.value = parameters.value.length ? 'setup' : 'home'
  } finally {
    busy.value = false
  }
}

function openParameter(parameter: ProtocolRuntimeParameter) {
  activeParameter.value = parameter
  if (isCsv(parameter)) {
    view.value = 'csv'
    return
  }
  if (parameter.choices?.length || parameter.type === 'bool') {
    view.value = 'choice'
    return
  }
  draftNumber.value = Number(values[parameter.variableName] ?? parameter.default ?? 0)
  view.value = 'number'
}

function confirmNumber() {
  if (!activeParameter.value) return
  values[activeParameter.value.variableName] = draftNumber.value
  view.value = 'setup'
}

function setChoice(value: boolean | number | string) {
  if (!activeParameter.value) return
  values[activeParameter.value.variableName] = value
  view.value = 'setup'
}

function onCsvSelected(event: Event, variableName: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  csvFiles[variableName] = file
  view.value = 'setup'
}

watch(
  () => [panelMode.value, remoteTargetIp.value] as const,
  ([mode, ip]) => {
    if (mode === 'remote' && ip) void loadRemoteDataFiles()
  },
)

onMounted(() => {
  void loadEnvironment()
  window.addEventListener('keydown', onScreenKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onScreenKeydown)
})
</script>

<style scoped>
.protocol-panel {
  min-height: 0;
  height: 100%;
  overflow: auto;
  padding: 16px 32px 40px;
  background: #fff;
}

.protocol-mode-switch {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  margin: 0 0 16px;
  border-radius: 999px;
  background: #eef2f5;
}

.protocol-mode-btn {
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #4a5560;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 650;
  padding: 8px 14px;
  cursor: pointer;
}

.protocol-mode-btn.is-active {
  background: #fff;
  color: #16212d;
  box-shadow: 0 1px 3px rgba(22, 33, 45, 0.12);
}

.protocol-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(240px, 0.7fr);
  gap: clamp(24px, 4vw, 56px);
  align-items: start;
  max-width: 1180px;
}

.protocol-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
  max-width: 360px;
  width: 100%;
  min-height: 0;
}

.protocol-copy.is-remote {
  gap: 16px;
}

.protocol-copy h2 {
  margin: 0;
  color: #16212d;
  font-size: clamp(1.55rem, 2vw, 1.9rem);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
}

.protocol-lead,
.protocol-odd-hint {
  margin: 0;
  color: #6a7380;
  font-size: 1.05rem;
  line-height: 1.55;
  font-weight: 400;
}

.protocol-inline-link {
  border: 0;
  padding: 0;
  margin: 0;
  background: transparent;
  color: #0069da;
  font: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}

.protocol-inline-link:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.protocol-labware-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: -4px 0 0;
  color: #1f6b45;
  font-size: 0.9rem;
}

.protocol-odd-connect {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  margin: 0;
  padding: 12px;
  border: 1px solid #d7dde3;
  border-radius: 12px;
  background: #f7f9fb;
}

.protocol-odd-connect-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.protocol-odd-connect-head strong {
  font-size: 0.95rem;
}

.protocol-odd-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.protocol-odd-btn {
  margin-top: 0;
  padding: 12px 18px;
  font-size: inherit;
}

.protocol-odd-live {
  margin: 0;
  color: #1f6b45;
  font-size: 0.86rem;
  font-weight: 650;
}

.remote-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
  width: 100%;
}

.remote-subnav {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  width: 100%;
  padding: 3px;
  border-radius: 10px;
  background: #eef2f5;
}

.remote-subnav-btn {
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #4a5560;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 650;
  padding: 7px 8px;
  cursor: pointer;
}

.remote-subnav-btn.is-active {
  background: #fff;
  color: #16212d;
  box-shadow: 0 1px 2px rgba(22, 33, 45, 0.1);
}

.remote-tab-pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.remote-field {
  width: 100%;
  max-width: none;
}

.remote-field-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.remote-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.remote-divider {
  width: 100%;
  height: 1px;
  margin: 2px 0;
  background: #e2e7eb;
}

.remote-section-title {
  margin: 0;
  color: #16212d;
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.35;
}

.remote-file-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.remote-file-btn {
  display: grid;
  gap: 2px;
  width: 100%;
  border: 1px solid #cfd9dd;
  border-radius: 8px;
  background: #fff;
  color: #16212d;
  text-align: left;
  padding: 9px 11px;
  font: inherit;
  font-size: 0.92rem;
  cursor: pointer;
}

.remote-file-btn:hover:not(:disabled) {
  border-color: #0069da;
}

.remote-file-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.remote-file-btn span {
  font-size: 0.92rem;
  font-weight: 650;
}

.remote-file-btn strong {
  color: #1f6b45;
  font-size: 0.86rem;
  font-weight: 600;
  word-break: break-all;
}

.remote-file-btn em {
  color: #8a939c;
  font-size: 0.82rem;
  font-style: normal;
}

.remote-clear {
  align-self: flex-start;
  margin-top: -2px;
}

.remote-csv-bind {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.odd-idle {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  text-align: center;
  color: #e9e9e9;
  font-size: 12px;
  position: relative;
  background: var(--odd-black, #16212d);
}

.odd-idle strong {
  font-size: 14px;
}

.odd-idle span {
  opacity: 0.75;
  max-width: 90%;
  line-height: 1.4;
}

.protocol-version-field {
  display: grid;
  gap: 6px;
  width: min(100%, 280px);
  color: #354249;
  font-size: 0.92rem;
  font-weight: 650;
}

.protocol-version-field select {
  height: 40px;
  border: 1px solid #cfd9dd;
  border-radius: 8px;
  padding: 0 10px;
  background: #fff;
  color: #16212d;
  font: inherit;
}

.protocol-version-field small {
  color: #6a7380;
  font-weight: 500;
  line-height: 1.35;
}

.protocol-upload-btn {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  width: fit-content;
  max-width: 100%;
  gap: 8px;
  margin-top: 4px;
  border: 0;
  border-radius: 999px;
  background: #0069da;
  color: #fff;
  font: inherit;
  font-weight: 650;
  padding: 12px 18px;
  cursor: pointer;
}

.protocol-upload-btn:disabled,
.protocol-upload-btn:has(input:disabled),
.protocol-upload-btn.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.protocol-env {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 4px 0 0;
  padding: 0;
  background: transparent;
  color: #6a7380;
  font-size: 0.88rem;
  line-height: 1.4;
}

.protocol-env.is-ready { color: #1f6b45; }
.protocol-env.is-bad { color: #8a2424; }

.protocol-env-dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: currentColor;
  flex: 0 0 auto;
}

.flex-stage { width: 100%; }

.flex-frame {
  position: relative;
  width: 100%;
  border-radius: 16px;
  /* Always visible so remote rails can sit outside the screen without mode-switch jump. */
  overflow: visible;
  background: transparent;
}

.flex-photo {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 16px;
  user-select: none;
  pointer-events: none;
}

.flex-screen-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(16, 24, 32, 0.42);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.flex-screen {
  position: absolute;
  left: 20.5%;
  top: 27.5%;
  width: 71%;
  height: 43%;
  border: 0;
  padding: 0;
  z-index: 2;
  border-radius: 14px;
  overflow: visible;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.55),
    0 10px 28px rgba(0, 0, 0, 0.35);
}

.odd-shell.is-remote {
  overflow: visible;
  background: #111;
  border-radius: 14px;
}

.odd-shell.is-remote :deep(.odd-remote) {
  flex: 1 1 auto;
  align-self: stretch;
  min-height: 0;
  width: 100%;
  height: 100%;
}

.flex-screen.is-expanded {
  /* Match Flex ODD native 1024×600 landscape; avoid the old tall 760×640 squash. */
  --odd-expanded-max-w: min(1280px, calc(100vw - 40px));
  --odd-expanded-max-h: calc(100vh - 48px);
  position: fixed;
  left: 50%;
  top: 50%;
  width: min(var(--odd-expanded-max-w), calc(var(--odd-expanded-max-h) * 1024 / 600));
  height: min(var(--odd-expanded-max-h), calc(var(--odd-expanded-max-w) * 600 / 1024));
  aspect-ratio: 1024 / 600;
  transform: translate(-50%, -50%);
  z-index: 1210;
  border-radius: 18px;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.7),
    0 24px 64px rgba(0, 0, 0, 0.35);
}

.odd-shell {
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
  --odd-green50: #04aa65;
  --odd-green35: #afedd3;
  --odd-green20: #e8f7ed;
  --odd-red50: #de1b1b;
  --odd-red20: #fce9e9;
  --odd-yellow35: #ffe1a4;
  --odd-white: #ffffff;

  width: 100%;
  height: 100%;
  background: var(--odd-white);
  color: var(--odd-black);
  font-family: "Public Sans", "IBM Plex Sans", "Segoe UI", sans-serif;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: inherit;
  font-size: 10.5px;
  line-height: 1.25;
}

.odd-shell.is-expanded {
  font-size: 14px;
  line-height: 1.35;
}

.odd-analyzing {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  text-align: center;
  position: relative;
}

.odd-mini-toolbar {
  position: absolute;
  top: 6px;
  right: 6px;
}

.odd-setup-header h3,
.odd-detail-header h3,
.odd-result h3 {
  margin: 0;
  font-size: 1.08em;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.odd-shell.is-expanded .odd-setup-header h3,
.odd-shell.is-expanded .odd-detail-header h3,
.odd-shell.is-expanded .odd-result h3 {
  font-size: 1.15rem;
}

.odd-setup-header p,
.odd-detail-header p {
  margin: 1px 0 0;
  color: var(--odd-grey50);
  font-size: 0.9em;
  font-weight: 500;
}

.odd-spin {
  animation: odd-spin 1s linear infinite;
  color: var(--odd-blue50);
}

@keyframes odd-spin {
  to { transform: rotate(360deg); }
}

.odd-setup,
.odd-detail,
.odd-result {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 6px 7px 7px;
  gap: 5px;
}

.odd-shell.is-expanded .odd-setup,
.odd-shell.is-expanded .odd-detail,
.odd-shell.is-expanded .odd-result {
  padding: 14px 16px 16px;
  gap: 10px;
}

.odd-setup-header,
.odd-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
}

.odd-detail-copy {
  flex: 1;
  min-width: 0;
}

.odd-header-actions {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
}

.odd-zoom-btn {
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: var(--odd-grey20);
  color: var(--odd-grey60);
  cursor: pointer;
  padding: 0;
}

.odd-shell.is-expanded .odd-zoom-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.odd-zoom-btn:hover {
  background: var(--odd-grey30);
}

.odd-circle {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 0;
  display: grid;
  place-items: center;
  color: #fff;
  cursor: pointer;
  padding: 0;
}

.odd-shell.is-expanded .odd-circle {
  width: 40px;
  height: 40px;
}

.odd-circle:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.odd-circle.is-cancel { background: var(--odd-red50); }
.odd-circle.is-start { background: var(--odd-blue50); }

.odd-rows,
.odd-choice-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: auto;
  min-height: 0;
  flex: 1;
}

.odd-shell.is-expanded .odd-rows,
.odd-shell.is-expanded .odd-choice-list {
  gap: 8px;
}

.odd-row {
  width: 100%;
  border: 0;
  border-radius: 10px;
  background: var(--odd-blue35);
  color: inherit;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 7px 8px;
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.odd-shell.is-expanded .odd-row {
  border-radius: 16px;
  padding: 14px 16px;
  gap: 10px;
}

.odd-row.is-ready { background: var(--odd-green35); }
.odd-row.is-missing { background: var(--odd-yellow35); }

.odd-row-main {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.odd-row-main strong {
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.odd-row-meta {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--odd-black);
  font-size: 0.9em;
  font-weight: 650;
  white-space: nowrap;
  max-width: 46%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.odd-check {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--odd-green50);
  color: #fff;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
}

.odd-shell.is-expanded .odd-check {
  width: 20px;
  height: 20px;
}

.odd-setup-footer {
  display: flex;
  justify-content: flex-end;
}

.odd-primary-btn,
.odd-file-label {
  border: 0;
  border-radius: 999px;
  background: var(--odd-blue50);
  color: #fff;
  font: inherit;
  font-weight: 650;
  padding: 5px 10px;
  cursor: pointer;
  text-align: center;
}

.odd-shell.is-expanded .odd-primary-btn,
.odd-shell.is-expanded .odd-file-label {
  padding: 10px 16px;
}

.odd-primary-btn:disabled {
  background: var(--odd-grey35);
  color: var(--odd-grey50);
  cursor: not-allowed;
  opacity: 1;
}

.odd-back {
  border: 0;
  background: transparent;
  color: var(--odd-black);
  padding: 0;
  margin-right: 2px;
  cursor: pointer;
}

.odd-number-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--odd-grey10);
  border-radius: 8px;
  padding: 8px;
}

.odd-shell.is-expanded .odd-number-field {
  gap: 8px;
  border-radius: 12px;
  padding: 14px;
}

.odd-number-field input {
  border: 1px solid var(--odd-grey30);
  border-radius: 8px;
  padding: 6px 8px;
  font: inherit;
  font-size: 1.15em;
  background: var(--odd-white);
  color: var(--odd-black);
}

.odd-empty-params,
.odd-file-meta {
  color: var(--odd-grey50);
  font-size: 0.95em;
}

.odd-error-box {
  background: var(--odd-red20);
  color: var(--odd-red50);
  border-radius: 8px;
  padding: 6px 8px;
  overflow: auto;
  max-height: 34%;
  font-size: 0.95em;
}

.odd-shell.is-expanded .odd-error-box {
  border-radius: 12px;
  padding: 12px 14px;
  max-height: 45%;
}

.odd-error-box p {
  margin: 4px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.odd-ok-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--odd-green20);
  color: var(--odd-green60);
  border-radius: 8px;
  padding: 6px 8px;
}

.odd-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.odd-stats span {
  background: var(--odd-grey20);
  border-radius: 999px;
  padding: 3px 7px;
  color: var(--odd-grey60);
  font-size: 0.88em;
  font-weight: 600;
}

.odd-shell.is-expanded .odd-stats {
  gap: 8px;
}

.odd-shell.is-expanded .odd-stats span {
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 0.9rem;
}

.odd-prepare-host,
.odd-run-host {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.odd-zoom-float {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 3;
}

.agent-file-input { display: none; }

@media (max-width: 960px) {
  .protocol-hero {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .protocol-copy { max-width: none; }

  .flex-screen:not(.is-expanded) {
    left: 20%;
    top: 27%;
    width: 72%;
    height: 44%;
  }
}
</style>
