<template>
  <main class="defect-search-page">
    <header class="defect-search-topbar">
      <a class="defect-search-brand" href="/" aria-label="Productions">
        <img :src="productionsLogo" alt="Productions" />
        <span>{{ copy.platform }}</span>
      </a>
      <div class="defect-search-account">
        <LocaleSwitcher />
        <AuthUserMenu />
      </div>
    </header>

    <div class="defect-search-content">
      <nav class="defect-search-breadcrumb" aria-label="breadcrumb">
        <a href="/">{{ copy.home }}</a>
        <span>/</span>
        <a href="/#modules">{{ copy.modules }}</a>
        <span>/</span>
        <span>{{ copy.title }}</span>
      </nav>

      <section class="defect-search-heading">
        <div>
          <p class="defect-search-eyebrow">{{ copy.eyebrow }}</p>
          <h1>{{ copy.title }}</h1>
          <p class="defect-search-intro">{{ copy.intro }}</p>
        </div>
        <div class="defect-search-badge"><Search :size="17" />{{ searchModeLabel }}</div>
      </section>

      <section class="defect-search-stats" :aria-label="copy.summaryLabel">
        <article class="defect-stat-card">
          <span>{{ copy.caseCount }}</span>
          <strong>{{ summary.total_cases.toLocaleString() }}</strong>
          <small>{{ copy.caseCountNote }}</small>
        </article>
        <article class="defect-stat-card is-highlight">
          <span>{{ copy.capacityFailure }}</span>
          <strong>{{ summary.capacity_cases.toLocaleString() }}</strong>
          <small>{{ copy.capacityRetestNote(summary.capacity_retest_cases) }}</small>
        </article>
        <article class="defect-stat-card">
          <span>{{ copy.rootCause }}</span>
          <strong>{{ summary.root_cause_cases.toLocaleString() }}</strong>
          <small>{{ copy.rootCauseNote }}</small>
        </article>
      </section>

      <section class="defect-query-card" aria-labelledby="defect-query-title">
        <div class="defect-query-heading">
          <div>
            <h2 id="defect-query-title">{{ copy.queryTitle }}</h2>
            <p>{{ copy.queryDescription }}</p>
            <small class="defect-model-note">{{ copy.modelNote }}</small>
          </div>
          <span class="defect-data-count">{{ copy.dataCount(summary.total_cases) }}</span>
        </div>

        <form ref="queryForm" class="defect-query-form" @submit.prevent="search(true)">
          <label class="defect-query-main">
            <span>{{ copy.symptomLabel }}</span>
            <div class="defect-input-wrap">
              <Search :size="18" aria-hidden="true" />
              <input
                ref="queryInput"
                v-model="query"
                type="search"
                :placeholder="copy.queryPlaceholder"
                autocomplete="off"
              />
            </div>
          </label>
          <label>
            <span>{{ copy.productLabel }}</span>
            <select v-model="filters.product">
              <option value="">{{ copy.allProducts }}</option>
              <option v-if="filters.product && !options.product.includes(filters.product)" :value="filters.product">{{ filters.product }}</option>
              <option v-for="product in options.product" :key="product" :value="product">{{ product }}</option>
            </select>
          </label>
          <label>
            <span>{{ copy.stationLabel }}</span>
            <select v-model="filters.station">
              <option value="">{{ copy.allStations }}</option>
              <option v-for="station in options.station" :key="station" :value="station">{{ station }}</option>
            </select>
          </label>
          <label>
            <span>{{ copy.codeLabel }}</span>
            <select v-model="filters.defect_code">
              <option value="">{{ copy.allCodes }}</option>
              <option v-for="code in options.defect_code" :key="code" :value="code">{{ code }}</option>
            </select>
          </label>
          <div class="defect-query-actions">
            <button class="defect-search-button" type="submit" :disabled="loading">
              <Search :size="17" />{{ loading ? copy.searching : copy.searchButton }}
            </button>
            <button class="defect-reset-button" type="button" :disabled="loading" @click="resetSearch">{{ copy.reset }}</button>
            <button v-if="loading" class="defect-reset-button" type="button" @click="cancelSearch">{{ copy.cancel }}</button>
          </div>
          <label class="defect-query-action-filter">
            <span>{{ copy.actionFilter }}</span>
            <div class="defect-input-wrap"><input v-model="actionQuery" type="search" :placeholder="copy.actionPlaceholder" autocomplete="off" /></div>
          </label>
        </form>

        <p v-if="loading" class="defect-search-progress" role="status">{{ copy.waiting(elapsedSeconds) }}</p>
        <p v-else-if="cancelled" class="defect-search-progress" role="status">{{ copy.cancelled }}</p>
        <p v-if="optionsError" class="defect-inline-error" role="alert">{{ optionsError }} <button type="button" class="defect-text-button" @click="loadOptions">{{ copy.retry }}</button></p>

        <div class="defect-quick-searches">
          <span>{{ copy.quickSearch }}</span>
          <button type="button" :disabled="loading" @click="applyQuickSearch(copy.capacityQuick)">{{ copy.capacityQuick }}</button>
          <button type="button" :disabled="loading" @click="applyQuickSearch(copy.gripperQuick)">{{ copy.gripperQuick }}</button>
          <button type="button" :disabled="loading" @click="applyQuickSearch(copy.leakQuick)">{{ copy.leakQuick }}</button>
          <button type="button" :disabled="loading" @click="applyQuickSearch(copy.latchQuick)">{{ copy.latchQuick }}</button>
        </div>
      </section>

      <section v-if="firstStep" class="defect-first-action" aria-live="polite" aria-labelledby="defect-first-step-title">
        <div class="first-action-icon">
          <RotateCcw v-if="firstStep.kind === 'retest'" :size="26" />
          <ClipboardCheck v-else :size="26" />
        </div>
        <div class="first-action-copy">
          <h2 id="defect-first-step-title" class="first-action-heading">{{ copy.firstStep }}</h2>
          <strong class="first-action-title">{{ firstStepTitle }}</strong>
          <p v-if="firstStep.attempted_action" class="defect-attempted-action">{{ copy.attemptedAction(firstStep.attempted_action) }}</p>
          <p>{{ firstStepDescription }}</p>
          <div v-if="firstStep.conditions?.length" class="defect-advice-conditions first-action-sources">
            <h3>{{ copy.applicableConditions }}</h3>
            <ul><li v-for="condition in firstStep.conditions" :key="condition">{{ condition }}</li></ul>
          </div>
          <div v-if="firstStep.evidence_level && !['none', 'policy'].includes(firstStep.evidence_level)" class="defect-evidence-meta first-action-sources">
            <span>{{ evidenceLabel(firstStep.evidence_level) }}</span>
            <span>{{ copy.verifiedCases(firstStep.verified_cases ?? 0) }}</span>
            <span v-if="firstStep.latest_date">{{ copy.latestDate }} {{ firstStep.latest_date }}</span>
          </div>
          <div v-if="firstStep.sources.length" class="defect-recommendation-sources first-action-sources">
            <a
              v-for="source in firstStep.sources.slice(0, 3)"
              :key="source.local_id || `${source.source}-${source.source_row}`"
              :href="source.source_url"
              :title="source.defect_description"
              target="_blank"
              rel="noopener noreferrer"
              @click="openSource($event, source.local_id)"
            ><ExternalLink :size="14" />{{ source.source }} · {{ copy.rowLabel }} {{ source.source_row }}</a>
          </div>
          <div v-if="adviceOptions.length" class="defect-advice-options first-action-sources">
            <h3>{{ adviceOptions.some(option => option.description) ? copy.scenarioAdvice : firstStep.kind === 'select_product' ? copy.modelAdvice : copy.actionOptions }}</h3>
            <article v-for="option in adviceOptions" :key="`${option.product}-${option.description || ''}-${option.stations.join(',')}-${option.defect_codes.join(',')}-${option.action}`">
              <div><b>{{ option.product || copy.unknownProduct }}</b><span>{{ copy.actionAdoptions(option.count, option.matched_cases) }}</span></div>
              <p v-if="option.description" class="defect-advice-symptom">{{ option.description }}</p>
              <p>{{ option.action }}</p>
              <small>{{ option.stations.join(' / ') || '—' }} · {{ option.defect_codes.join(' / ') || '—' }}</small>
              <details v-if="option.sources?.length" class="defect-advice-option-sources"><summary>{{ copy.viewEvidence }}</summary><div class="defect-recommendation-sources"><a v-for="source in option.sources.slice(0, 3)" :key="source.local_id" :href="source.source_url" :title="source.defect_description" target="_blank" rel="noopener noreferrer" @click="openSource($event, source.local_id)"><ExternalLink :size="14" />{{ source.source }} · {{ copy.rowLabel }} {{ source.source_row }}</a></div></details>
              <button v-if="option.description" type="button" class="defect-reset-button" :disabled="loading" @click="selectAdviceScenario(option)">{{ copy.useScenario }}</button>
              <button v-else-if="firstStep.kind === 'select_product' && option.product" type="button" class="defect-reset-button" :disabled="loading" @click="narrowSearch('product', option.product)">{{ copy.useModel(option.product) }}</button>
            </article>
          </div>
          <div v-if="productCandidates.length || stationCandidates.length || codeCandidates.length" class="defect-first-candidates first-action-sources">
            <div v-if="productCandidates.length"><span>{{ copy.productLabel }}</span><button v-for="product in productCandidates" :key="product" type="button" :disabled="loading" @click="narrowSearch('product', product)">{{ product }}</button></div>
            <div v-if="stationCandidates.length"><span>{{ copy.stationLabel }}</span><button v-for="station in stationCandidates" :key="station" type="button" :disabled="loading" @click="narrowSearch('station', station)">{{ station }}</button></div>
            <div v-if="codeCandidates.length"><span>{{ copy.codeLabel }}</span><button v-for="code in codeCandidates" :key="code" type="button" :disabled="loading" @click="narrowSearch('defect_code', code)">{{ code }}</button></div>
          </div>
          <div class="defect-advice-refine first-action-sources">
            <p>{{ copy.continueAnalysisNote }}</p>
            <button type="button" class="defect-reset-button" :disabled="loading" @click="continueAnalysis">{{ copy.continueAnalysis }}</button>
          </div>
        </div>
        <span class="first-action-label">{{ firstStep.kind === 'retest' ? copy.firstStepPolicy : firstStep.kind === 'historical' ? copy.historicalAction : firstStep.kind === 'reference' ? copy.conditionalReference : copy.firstStepCheck }}</span>
      </section>

      <section class="defect-results-section" aria-labelledby="defect-results-title">
        <div class="defect-results-heading">
          <div>
            <p class="defect-search-eyebrow">{{ copy.matchingCases }}</p>
            <h2 id="defect-results-title">{{ copy.resultsTitle }}</h2>
          </div>
          <span class="defect-result-count">{{ copy.resultCount(total) }}</span>
        </div>

        <p v-if="hasPendingChanges" class="defect-pending-search" role="status">
          <CircleAlert :size="17" />{{ copy.pendingSearch }}
        </p>
        <p v-if="recognizedConditions && !hasPendingChanges" class="defect-recognized-conditions">{{ copy.recognized }} {{ recognizedConditions }}</p>

        <section v-if="recommendations.length" class="defect-recommendations" aria-labelledby="defect-recommendations-title">
          <div class="defect-recommendations-heading">
            <h3 id="defect-recommendations-title"><ClipboardCheck :size="20" />{{ copy.recommendationsTitle }}</h3>
            <p>{{ copy.recommendationsNote }}</p>
            <p v-if="result?.recommendation_basis === 'similar'" class="defect-recommendations-caution">
              <CircleAlert :size="16" />{{ copy.similarRecommendationNote }}
            </p>
            <p v-else-if="result?.recommendation_basis === 'filtered'" class="defect-recommendations-basis">{{ copy.filteredRecommendationNote }}</p>
          </div>
          <div class="defect-recommendation-grid">
            <article v-for="profile in recommendations" :key="profile.product" class="defect-recommendation-card">
              <div class="defect-recommendation-topline">
                <h4>{{ profile.product || copy.unknownProduct }}</h4>
                <span>{{ copy.recommendationSamples(profile.matched_cases) }}</span>
              </div>
              <p class="defect-recommendation-scope">{{ copy.stationLabel }}: {{ profile.stations.join(' / ') || '—' }} · {{ copy.codeLabel }}: {{ profile.defect_codes.join(' / ') || '—' }}</p>
              <ol v-if="profile.actions.length" class="defect-recommendation-actions">
                <li v-for="action in profile.actions.slice(0, 3)" :key="action.action">
                  <div class="defect-recommendation-action">
                    <p>{{ action.action }}</p>
                    <span>{{ copy.actionAdoptions(action.count, profile.matched_cases) }}</span>
                  </div>
                  <div class="defect-evidence-meta">
                    <span>{{ evidenceLabel(action.evidence_level ?? (action.count > 1 ? 'multiple' : 'single')) }}</span>
                    <span>{{ copy.verifiedCases(action.verified_cases ?? 0) }}</span>
                    <span v-if="action.latest_date">{{ copy.latestDate }} {{ action.latest_date }}</span>
                  </div>
                  <p v-if="action.components?.length || action.versions?.length || action.positions?.length" class="defect-action-context"><span v-if="action.components?.length">{{ copy.replacedParts }}: {{ action.components.join(' / ') }} </span><span v-if="action.versions?.length">{{ copy.hardwareVersion }}: {{ action.versions.join(' / ') }} </span><span v-if="action.positions?.length">{{ copy.position }}: {{ action.positions.join(' / ') }}</span></p>
                  <div v-if="action.sources.length" class="defect-recommendation-sources">
                    <a
                      v-for="source in action.sources.slice(0, 3)"
                      :key="source.local_id || `${source.source}-${source.source_row}`"
                      :href="source.source_url"
                      :title="source.defect_description"
                      target="_blank"
                      rel="noopener noreferrer"
                      @click="openSource($event, source.local_id)"
                    ><ExternalLink :size="14" />{{ source.source }} · {{ copy.rowLabel }} {{ source.source_row }}</a>
                  </div>
                  <details v-if="action.sources.some(source => source.original_action)" class="defect-original-actions"><summary>{{ copy.originalActions }}</summary><p v-for="source in action.sources.filter(source => source.original_action)" :key="source.local_id">{{ source.source }} · {{ source.source_row }}：{{ source.original_action }}</p></details>
                </li>
              </ol>
              <p v-else class="defect-recommendation-missing"><CircleAlert :size="16" />{{ copy.noProductActions }}</p>
              <p v-if="profile.actions.length && profile.missing_action_cases" class="defect-recommendation-coverage">
                {{ copy.missingActions(profile.missing_action_cases) }}
              </p>
            </article>
          </div>
        </section>
        <p v-else-if="showRecommendations && total > 0 && appliedSearch?.q" class="defect-recommendation-empty">
          <ClipboardCheck :size="18" />{{ copy.noRecommendations }}
        </p>

        <div v-if="error" class="defect-state defect-error" role="alert">
          <CircleAlert :size="18" />
          <span>{{ error }}</span>
          <button type="button" @click="search(true)">{{ copy.retry }}</button>
        </div>
        <div v-else-if="loading && cases.length === 0" class="defect-state">{{ copy.loading }}</div>
        <div v-else-if="cases.length === 0" class="defect-state defect-empty">
          <Search :size="23" />
          <strong>{{ copy.emptyTitle }}</strong>
          <span>{{ copy.emptyDescription }}</span>
        </div>
        <div v-else class="defect-case-list">
          <article v-for="item in cases" :key="`${item.source}-${item.source_row}`" class="defect-case-card">
            <div class="defect-case-topline">
              <div class="defect-case-tags">
                <span class="case-category">{{ item.symptom_category || item.problem_type_normalized }}</span>
                <span class="case-code">{{ item.defect_code || copy.noCode }}</span>
                <span v-if="appliedSearch?.q" class="match-score">{{ copy.matchScore }} {{ item.match_score }}%</span>
                <span v-if="item.match_reason && item.match_reason !== 'browse'" class="defect-match-reason">{{ copy.matchReasons[item.match_reason] }}</span>
              </div>
              <time>{{ item.date || copy.unknownDate }}</time>
            </div>

            <div class="defect-case-title-row">
              <h3>{{ item.defect_description || item.symptom_normalized || copy.noDescription }}</h3>
              <a class="source-link" :href="sourceLink(item)" target="_blank" rel="noopener noreferrer" @click="openSource($event, item.local_id)">
                <ExternalLink :size="15" />{{ copy.viewSource }}
              </a>
            </div>

            <div class="defect-case-meta">
              <span><b>{{ copy.productLabel }}:</b> {{ item.product || '—' }}</span>
              <span><b>{{ copy.stationLabel }}:</b> {{ item.station || '—' }}</span>
              <span><b>SN:</b> {{ item.serial_number || '—' }}</span>
              <span><b>{{ copy.ownerLabel }}:</b> {{ item.responsible_department || '—' }}</span>
            </div>

            <div class="defect-case-details">
              <div v-if="item.containment_action" class="case-detail-block is-action">
                <span>{{ copy.historicalAction }}</span>
                <p>{{ item.containment_action }}</p>
              </div>
              <div v-if="item.exchange_component && item.exchange_component.toLowerCase() !== 'na'" class="case-detail-block">
                <span>{{ copy.replacedParts }}</span>
                <p>{{ item.exchange_component }}</p>
              </div>
              <div v-if="item.cause_analysis || item.root_cause" class="case-detail-block">
                <span>{{ copy.causeNotes }}</span>
                <p>{{ item.root_cause || item.cause_analysis }}</p>
              </div>
              <div v-if="item.exchange_verification" class="case-detail-block">
                <span>{{ copy.verification }}</span>
                <p>{{ item.exchange_verification }}</p>
              </div>
              <div v-if="item.long_term_action_qe || item.long_term_action_engineering" class="case-detail-block">
                <span>{{ copy.longTermAction }}</span>
                <p>{{ item.long_term_action_engineering || item.long_term_action_qe }}</p>
              </div>
            </div>

            <div class="defect-case-footer">
              <span class="knowledge-status" :class="{ 'is-open': !item.root_cause || !item.exchange_verification }">
                <CircleCheck v-if="item.root_cause && item.exchange_verification" :size="14" />
                <CircleAlert v-else :size="14" />
                {{ item.knowledge_status || copy.needsReview }}
              </span>
              <button type="button" class="defect-text-button" @click="openFeedback(item)">{{ copy.recordFeedback }}</button>
              <span>{{ item.source }} · {{ item.source_sheet }} · {{ copy.rowLabel }} {{ item.source_row }}</span>
            </div>
          </article>
        </div>

        <div v-if="!error && cases.length < total" class="defect-load-more">
          <button type="button" :disabled="loading || hasPendingChanges" @click="loadMore">{{ loading ? copy.loading : copy.loadMore }}</button>
        </div>
      </section>

      <DefectMaintenance v-if="authStore.user?.role === 'admin'" :english="isEnglish" @imported="refreshKnowledge" />
      <p class="defect-search-disclaimer"><CircleAlert :size="15" />{{ copy.disclaimer }}</p>
    </div>
    <DefectLocalDialog :record-id="dialogRecordId" :mode="dialogMode" :query="appliedSearch?.q ?? ''" :initial-action="dialogInitialAction" :repair-session="dialogSession" :english="isEnglish" @close="dialogRecordId = null" @source="openSourceId" @session="saveRepairSession" />
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import {
  CircleAlert,
  CircleCheck,
  ClipboardCheck,
  ExternalLink,
  RotateCcw,
  Search,
} from '@lucide/vue'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'
import DefectLocalDialog from './DefectLocalDialog.vue'
import DefectMaintenance from './DefectMaintenance.vue'
import productionsLogo from '@/assets/dashboard/productions-logo.svg'
import { useAppLocale } from '@/i18n'
import { chineseCopy, englishCopy, failedActionQuery } from '@/i18n/locales/defectSearch'
import { useAuthStore } from '@/scripts/stores/auth'
import { defectSearchApi, type DefectAdviceOption, type DefectRepairSession, type DefectSearchCase, type DefectSearchOptions, type DefectSearchResponse } from '@/scripts/api'
import '@/styles/dashboard/defect-search.css'

const { locale } = useAppLocale()
const authStore = useAuthStore()
const isEnglish = computed(() => locale.value === 'en-US')
const copy = computed(() => isEnglish.value ? englishCopy : chineseCopy)
const query = ref('')
const queryForm = ref<HTMLFormElement | null>(null)
const queryInput = ref<HTMLInputElement | null>(null)
const actionQuery = ref('')
const filters = reactive({ product: '', station: '', defect_code: '' })
type SearchCriteria = { q: string; product: string; station: string; defect_code: string; action: string }
const appliedSearch = ref<SearchCriteria | null>(null)
const options = reactive<DefectSearchOptions>({ product: [], station: [], defect_code: [] })
const cases = ref<DefectSearchCase[]>([])
const result = ref<DefectSearchResponse | null>(null)
const loading = ref(false)
const error = ref('')
const optionsError = ref('')
const cancelled = ref(false)
const elapsedSeconds = ref(0)
const dialogRecordId = ref<number | null>(null)
const dialogMode = ref<'source' | 'feedback'>('source')
const dialogInitialAction = ref('')
const repairSessions = reactive(new Map<number, DefectRepairSession>())
const dialogSession = computed(() => dialogRecordId.value ? repairSessions.get(dialogRecordId.value) : undefined)
let searchController: AbortController | null = null
let searchVersion = 0
let progressTimer: ReturnType<typeof setInterval> | null = null
const total = computed(() => result.value?.total ?? 0)
const summary = ref<DefectSearchResponse['summary']>({
  total_cases: 0,
  capacity_cases: 0,
  capacity_retest_cases: 0,
  root_cause_cases: 0,
})
const hasPendingChanges = computed(() => {
  const applied = appliedSearch.value
  if (!applied) return false
  return applied.q !== query.value.trim() || applied.product !== filters.product
    || applied.station !== filters.station || applied.defect_code !== filters.defect_code || applied.action !== actionQuery.value.trim()
})
const showRecommendations = computed(() => Boolean(result.value && !loading.value && !error.value && !hasPendingChanges.value))
const recommendations = computed(() => showRecommendations.value ? result.value?.recommendations ?? [] : [])
const firstStep = computed(() => showRecommendations.value ? result.value?.first_step ?? null : null)
const adviceOptions = computed(() => {
  const step = firstStep.value
  if (step?.options?.length) return step.options
  return step && ['select_product', 'confirm_symptom', 'compare_actions'].includes(step.kind) ? step.alternatives ?? [] : []
})
const productCandidates = computed(() => appliedSearch.value?.product || (firstStep.value?.kind === 'select_product' && adviceOptions.value.length) ? [] : [...new Set([...(firstStep.value?.products ?? []), ...recommendations.value.map(profile => profile.product)].filter(Boolean))].slice(0, 12))
const stationCandidates = computed(() => appliedSearch.value?.station ? [] : [...new Set(recommendations.value.flatMap(profile => profile.stations).filter(Boolean))].slice(0, 10))
const codeCandidates = computed(() => appliedSearch.value?.defect_code ? [] : [...new Set(recommendations.value.flatMap(profile => profile.defect_codes).filter(Boolean))].slice(0, 10))
const recognizedConditions = computed(() => {
  const values = result.value?.applied_constraints
  if (!values) return ''
  return [...values.products, ...(values.stations ?? []), ...values.duration_seconds.map(value => `${value}${copy.value.secondsUnit}`), ...values.channels.map(value => `${copy.value.channelLabel} ${value}`), ...(values.serials ?? []).map(value => `SN: ${value}`), values.action ? `${copy.value.actionFilter}: ${values.action}` : '', values.attempted_action ? copy.value.attemptedAction(values.attempted_action) : ''].filter(Boolean).join(' · ')
})
const firstStepConfirmation = computed(() => {
  const step = firstStep.value
  if (step?.kind !== 'confirm_symptom') return null
  const product = step.product || appliedSearch.value?.product || ''
  switch (step.reason) {
    case 'multiple_stations':
      return { title: copy.value.firstStepConfirmTitles.multiple_stations, description: copy.value.confirmStations(product, step.stations ?? []) }
    case 'multiple_codes':
      return { title: copy.value.firstStepConfirmTitles.multiple_codes, description: copy.value.confirmCodes(product, step.defect_codes ?? []) }
    case 'broad_symptom':
      return { title: copy.value.firstStepConfirmTitles.broad_symptom, description: copy.value.confirmBroadSymptom(product) }
    case 'similar_only':
      return { title: copy.value.firstStepConfirmTitles.similar_only, description: copy.value.confirmSimilarCases(product) }
    case 'mixed_symptoms':
      return { title: copy.value.firstStepConfirmTitles.mixed_symptoms, description: copy.value.confirmMixedSymptoms(product) }
    default:
      return null
  }
})
const firstStepTitle = computed(() => {
  const step = firstStep.value
  if (!step) return ''
  if (firstStepConfirmation.value) return firstStepConfirmation.value.title
  return ['historical', 'reference'].includes(step.kind) ? step.action : copy.value.firstStepTitles[step.kind as keyof typeof chineseCopy.firstStepTitles]
})
const firstStepDescription = computed(() => {
  const step = firstStep.value
  if (!step) return ''
  if (firstStepConfirmation.value) return firstStepConfirmation.value.description
  if (step.kind === 'select_product' && step.products?.length) return copy.value.confirmProducts(step.products)
  if (step.kind === 'historical') return copy.value.firstStepEvidence(step.product, step.count, step.matched_cases)
  if (step.kind === 'reference') return `${copy.value.referenceNote} ${copy.value.firstStepEvidence(step.product, step.count, step.matched_cases)}`
  const note = copy.value.firstStepNotes[step.kind]
  return step.basis === 'similar' ? `${note} ${copy.value.firstStepSimilarNote}` : note
})
const searchModeLabel = computed(() => {
  if (result.value?.search_mode === 'exact') return copy.value.exactMode
  if (result.value?.search_mode === 'semantic') return copy.value.semanticMode
  if (result.value?.search_mode === 'fuzzy_fallback') return copy.value.fallbackMode
  return copy.value.historyBadge
})
const PAGE_SIZE = 20


async function loadOptions(): Promise<void> {
  optionsError.value = ''
  try {
    const response = await defectSearchApi.getOptions()
    Object.assign(options, response.data)
  } catch {
    optionsError.value = copy.value.optionsFailed
  }
}

async function search(reset = true): Promise<void> {
  if (!reset && loading.value) return
  if (!reset && (hasPendingChanges.value || !result.value || !appliedSearch.value)) return
  const criteria = reset ? {
    q: query.value.trim(),
    product: filters.product,
    station: filters.station,
    defect_code: filters.defect_code,
    action: actionQuery.value.trim(),
  } : { ...appliedSearch.value! }
  const page = reset ? 1 : result.value!.page + 1
  searchController?.abort()
  stopProgress()
  const version = ++searchVersion
  const controller = new AbortController()
  searchController = controller
  if (reset) writeUrl(criteria)
  loading.value = true
  error.value = ''
  cancelled.value = false
  elapsedSeconds.value = 0
  const started = Date.now()
  progressTimer = setInterval(() => { elapsedSeconds.value = Math.floor((Date.now() - started) / 1000) }, 1000)
  try {
    const response = await defectSearchApi.search({
      ...criteria,
      page,
      page_size: PAGE_SIZE,
    }, controller.signal)
    if (controller.signal.aborted || version !== searchVersion) return
    result.value = response.data
    appliedSearch.value = criteria
    summary.value = response.data.summary
    cases.value = reset ? response.data.cases : [...cases.value, ...response.data.cases]
  } catch (value) {
    if (controller.signal.aborted || version !== searchVersion || axios.isCancel(value)) return
    error.value = axios.isAxiosError(value) && value.code === 'ECONNABORTED' ? copy.value.searchTimedOut : copy.value.searchFailed
  } finally {
    if (version === searchVersion) { loading.value = false; stopProgress() }
  }
}

function stopProgress(): void { if (progressTimer) clearInterval(progressTimer); progressTimer = null }
function cancelSearch(): void {
  searchController?.abort(); searchVersion += 1; loading.value = false; cancelled.value = true; stopProgress()
}
function writeUrl(criteria: SearchCriteria): void {
  const url = new URL(window.location.href)
  const values = { q: criteria.q, product: criteria.product, station: criteria.station, code: criteria.defect_code, action: criteria.action }
  Object.entries(values).forEach(([key, value]) => { if (value) url.searchParams.set(key, value); else url.searchParams.delete(key) })
  url.searchParams.delete('defect_code')
  window.history.replaceState(window.history.state, '', url)
}
function restoreUrl(): void {
  const values = new URL(window.location.href).searchParams
  query.value = values.get('q') || ''; actionQuery.value = values.get('action') || ''
  filters.product = values.get('product') || ''; filters.station = values.get('station') || ''; filters.defect_code = values.get('code') || values.get('defect_code') || ''
}
function narrowSearch(key: keyof typeof filters, value: string): void {
  const applied = appliedSearch.value
  if (!applied) return
  query.value = applied.q; actionQuery.value = applied.action
  filters.product = applied.product; filters.station = applied.station; filters.defect_code = applied.defect_code
  filters[key] = value
  void search(true)
}
async function continueAnalysis(): Promise<void> {
  actionQuery.value = ''
  await nextTick()
  queryForm.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  queryInput.value?.focus({ preventScroll: true })
  queryInput.value?.setSelectionRange(query.value.length, query.value.length)
}
function selectAdviceScenario(option: DefectAdviceOption): void {
  if (!option.description) return
  const attemptedAction = result.value?.applied_constraints?.attempted_action || firstStep.value?.attempted_action
  query.value = failedActionQuery(option.description, attemptedAction)
  actionQuery.value = ''
  filters.product = option.product
  filters.station = option.stations.length === 1 ? option.stations[0] : ''
  filters.defect_code = option.defect_codes.length === 1 ? option.defect_codes[0] : ''
  void search(true)
}
function evidenceLabel(level: string): string { return copy.value.evidenceLevels[level as keyof typeof chineseCopy.evidenceLevels] || copy.value.evidenceLevels.none }
function openSource(event: MouseEvent, id: string): void {
  const value = Number(id)
  if (!Number.isInteger(value) || value < 1) return
  event.preventDefault(); openSourceId(value)
}
function openSourceId(id: number): void { dialogMode.value = 'source'; dialogInitialAction.value = ''; dialogRecordId.value = id }
function openFeedback(item: DefectSearchCase): void {
  const id = Number(item.local_id)
  if (!Number.isInteger(id) || id < 1) return
  dialogInitialAction.value = item.containment_action || ''; dialogMode.value = 'feedback'; dialogRecordId.value = id
}
function saveRepairSession(caseId: number, session: DefectRepairSession | null): void {
  if (session) repairSessions.set(caseId, session)
  else repairSessions.delete(caseId)
}
function refreshKnowledge(): void { void loadOptions(); void search(true) }

function resetSearch(): void {
  query.value = ''
  filters.product = ''
  filters.station = ''
  filters.defect_code = ''
  actionQuery.value = ''
  void search(true)
}

function applyQuickSearch(value: string): void {
  query.value = value
  void search(true)
}

function loadMore(): void {
  void search(false)
}

function sourceLink(item: DefectSearchCase): string {
  return item.source_url
}

onMounted(() => {
  restoreUrl()
  void loadOptions()
  void search(true)
})
onBeforeUnmount(() => { searchController?.abort(); searchVersion += 1; stopProgress() })
</script>
