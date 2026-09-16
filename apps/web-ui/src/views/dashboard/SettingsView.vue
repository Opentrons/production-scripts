<template>
  <div class="settings-view">
    <div class="settings-tabs-wrap">
      <el-tabs v-model="activeTab" class="settings-tabs">
        <el-tab-pane :label="t('settings.upload')" name="upload">
          <div v-loading="loading" class="settings-content">
            <el-alert
              v-if="settingsError"
              :title="settingsError"
              type="warning"
              show-icon
              :closable="false"
              class="settings-alert"
            />

            <section class="settings-toolbar">
              <el-segmented
                v-model="selectedEnvironment"
                class="environment-switch"
                :options="environmentOptions"
                :disabled="loading || saving"
                @change="handleEnvironmentChange"
              />
              <el-select
                v-model="selectedModel"
                class="model-select"
                :placeholder="t('settings.product')"
                filterable
                :loading="loading"
                @change="handleModelChange"
              >
                <el-option
                  v-for="model in modelOptions"
                  :key="model"
                  :label="model"
                  :value="model"
                />
              </el-select>
              <el-select
                v-model="selectedTestType"
                class="test-select"
                :placeholder="t('settings.test')"
                filterable
                :loading="loading"
                @change="handleTestTypeChange"
              >
                <el-option
                  v-for="option in availableTestOptions"
                  :key="option.test_type"
                  :label="formatTestType(option.test_type, option.test_display_name)"
                  :value="option.test_type"
                >
                  <div class="test-option">
                    <span>{{ formatTestType(option.test_type, option.test_display_name) }}</span>
                    <small>{{ option.config_key }}</small>
                  </div>
                </el-option>
              </el-select>
              <el-select
                v-model="selectedOem"
                class="oem-select"
                :placeholder="t('settings.oem')"
                filterable
                :loading="loading"
              >
                <el-option
                  v-for="oem in availableOemOptions"
                  :key="oem"
                  :label="oem"
                  :value="oem"
                />
              </el-select>
            </section>

            <section class="setting-panel">
              <div class="setting-main">
                <div>
                  <h3>{{ t('settings.finishedGuard') }}</h3>
                  <p>{{ t('settings.finishedDescription') }}</p>
                </div>
                <el-switch
                  v-model="requireFinished"
                  :disabled="!currentSetting || saving"
                  :active-text="t('settings.requireFinished')"
                  :inactive-text="t('settings.directUpload')"
                  @change="saveCurrentSetting"
                />
              </div>

              <el-descriptions
                v-if="currentSetting"
                :column="2"
                border
                size="small"
                class="setting-desc"
              >
                <el-descriptions-item :label="t('settings.product')">{{ currentSetting.model }}</el-descriptions-item>
                <el-descriptions-item :label="t('settings.test')">
                  {{ formatTestType(currentSetting.test_type, currentSetting.test_display_name) }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('settings.config')">{{ currentSetting.config_key }}</el-descriptions-item>
                <el-descriptions-item :label="t('settings.configFile')">{{ configFileName }}</el-descriptions-item>
                <el-descriptions-item :label="t('settings.source')">
                  <el-tag :type="currentSetting.source === 'yaml' ? 'success' : 'info'" size="small">
                    {{ currentSetting.source === 'yaml' ? t('settings.yaml') : t('settings.defaultFallback') }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>

              <el-divider content-position="left">{{ t('settings.unifiedParams') }}</el-divider>
              <el-form label-position="top" class="upload-config-form unified-config-form">
                <el-form-item :label="t('settings.lastRow')">
                  <el-input
                    v-model="lastRowRange"
                    :disabled="loading || saving"
                    :placeholder="t('settings.lastRowPlaceholder')"
                  />
                  <div class="setting-help-text">{{ t('settings.lastRowDescription') }}</div>
                </el-form-item>
              </el-form>

              <template v-if="currentSetting">
              <el-divider content-position="left">{{ t('settings.rawUploadParams') }}</el-divider>
              <el-form label-position="top" class="upload-config-form">
                <el-form-item :label="t('settings.copytemplate')">
                  <el-input v-model="configForm.copytemplate" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.csvRange')">
                  <el-input v-model="configForm.csvRange" :disabled="!currentSetting || saving" />
                </el-form-item>
              </el-form>

              <el-divider content-position="left">{{ t('settings.copyResultParams') }}</el-divider>
              <el-form label-position="top" class="upload-config-form">
                <el-form-item :label="t('settings.resultCell')">
                  <el-input v-model="configForm.resultCell" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.totalResultCell')">
                  <el-input v-model="configForm.totalResultCell" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.failures')">
                  <el-input v-model="configForm.failures" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.summarySourceSheet')">
                  <el-input v-model="configForm.summarySourceSheet" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.copyRange')">
                  <el-input v-model="configForm.copyRange" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.pasteFileId')">
                  <el-input v-model="configForm.pasteFileId" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.pasteStart')">
                  <el-input v-model="configForm.pasteStart" :disabled="!currentSetting || saving" />
                </el-form-item>
                <el-form-item :label="t('settings.pasteEnd')">
                  <el-input v-model="configForm.pasteEnd" :disabled="!currentSetting || saving" />
                </el-form-item>
              </el-form>
              <div class="config-actions">
                <el-button type="primary" :loading="saving" :disabled="!currentSetting" @click="saveCurrentSetting">
                  {{ t('settings.saveConfig') }}
                </el-button>
              </div>
              </template>

              <el-empty v-else :description="t('settings.selectProductTest')" />
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>
      <div class="tabs-actions">
        <el-tooltip :content="t('common.actions.refresh')" placement="bottom">
          <el-button
            :icon="Refresh"
            :loading="loading"
            circle
            size="small"
            :aria-label="t('settings.refreshUpload')"
            @click="fetchUploadSettings"
          />
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { settingsApi } from '@/scripts/api'
import type {
  UploadFinishSettingItem,
  UploadFinishSettingOption,
} from '@/scripts/types'
import { formatTestType } from '@/scripts/utils/testNames'
import { useAppLocale } from '@/i18n'

const { t } = useAppLocale()

const activeTab = ref('upload')
const loading = ref(true)
const saving = ref(false)
const selectedModel = ref('')
const selectedTestType = ref('')
const selectedOem = ref('Opentrons')
const selectedEnvironment = ref<'production' | 'eng'>('production')
const requireFinished = ref(true)
const settingsError = ref('')
const configFileName = ref('upload_production.yaml')
const lastRowRange = ref('F:I')
const engConfigSynced = ref(false)
const uploadOptions = ref<UploadFinishSettingOption[]>([])
const uploadSettings = ref<UploadFinishSettingItem[]>([])
const environmentOptions = computed(() => [
  { label: t('settings.productionMode'), value: 'production' },
  { label: t('settings.engMode'), value: 'eng' }
])
const configForm = reactive({
  copytemplate: '', csvRange: '', resultCell: '', totalResultCell: '', failures: 'N/A',
  summarySourceSheet: '', copyRange: '', pasteFileId: '', pasteStart: '', pasteEnd: ''
})

const modelOptions = computed(() => {
  return Array.from(new Set(uploadOptions.value.map(option => option.model))).sort()
})

const availableTestOptions = computed(() => {
  return uploadOptions.value
    .filter(option => option.model === selectedModel.value)
    .sort((left, right) => formatTestType(left.test_type).localeCompare(formatTestType(right.test_type)))
})

const availableOemOptions = computed(() => {
  if (!selectedModel.value || !selectedTestType.value) return ['Opentrons']
  const options = new Set<string>(['Opentrons'])
  uploadSettings.value
    .filter(setting => setting.model === selectedModel.value && setting.test_type === selectedTestType.value)
    .forEach(setting => {
      options.add(setting.oem || 'Opentrons')
      ;(setting.oem_options || []).forEach(oem => options.add(oem))
    })
  return Array.from(options).sort((left, right) => {
    if (left === 'Opentrons') return -1
    if (right === 'Opentrons') return 1
    return left.localeCompare(right)
  })
})

const currentSetting = computed(() => {
  if (!selectedModel.value || !selectedTestType.value) return null
  return uploadSettings.value.find(setting =>
    setting.model === selectedModel.value &&
    setting.test_type === selectedTestType.value &&
    (setting.oem || 'Opentrons') === selectedOem.value
  ) || null
})

watch(availableOemOptions, options => {
  if (!options.includes(selectedOem.value)) selectedOem.value = options[0] || 'Opentrons'
}, { immediate: true })

watch(currentSetting, setting => {
  requireFinished.value = setting?.require_finished ?? true
  configForm.copytemplate = setting?.copytemplate ?? ''
  configForm.csvRange = (setting?.csv_range ?? []).join(', ')
  configForm.resultCell = setting?.result_cell ?? ''
  configForm.totalResultCell = setting?.total_result_cell ?? ''
  configForm.failures = setting?.failures ?? 'N/A'
  configForm.summarySourceSheet = setting?.summary_source_sheet_name ?? ''
  configForm.copyRange = (setting?.copy_range ?? []).join(', ')
  configForm.pasteFileId = setting?.pastefileid ?? ''
  configForm.pasteStart = setting?.paste_start ?? ''
  configForm.pasteEnd = setting?.paste_end ?? ''
}, { immediate: true })

const fetchUploadSettings = async (syncFromProduction = false) => {
  loading.value = true
  settingsError.value = ''
  try {
    const { data } = await settingsApi.getUploadFinishSettings(selectedEnvironment.value, syncFromProduction)
    uploadOptions.value = data.options || []
    uploadSettings.value = data.settings || []
    configFileName.value = data.config_file || (selectedEnvironment.value === 'eng' ? 'upload_debug.yaml' : 'upload_production.yaml')
    lastRowRange.value = data.last_row || 'F:I'
    settingsError.value = data.database_available ? '' : (data.error || t('settings.databaseDisconnected'))
    ensureSelection()
  } catch (error: any) {
    settingsError.value = error?.response?.data?.detail?.message || error?.message || t('settings.loadFailed')
    ElMessage.error(settingsError.value)
  } finally {
    loading.value = false
  }
}

const handleEnvironmentChange = () => {
  const syncFromProduction = selectedEnvironment.value === 'eng' && !engConfigSynced.value
  if (syncFromProduction) engConfigSynced.value = true
  selectedModel.value = ''
  selectedTestType.value = ''
  selectedOem.value = 'Opentrons'
  fetchUploadSettings(syncFromProduction)
}

const ensureSelection = () => {
  if (!selectedModel.value || !modelOptions.value.includes(selectedModel.value)) {
    selectedModel.value = modelOptions.value[0] || ''
  }

  const tests = availableTestOptions.value
  if (!selectedTestType.value || !tests.some(option => option.test_type === selectedTestType.value)) {
    selectedTestType.value = tests[0]?.test_type || ''
  }
}

const handleModelChange = () => {
  selectedTestType.value = availableTestOptions.value[0]?.test_type || ''
  selectedOem.value = 'Opentrons'
}

const handleTestTypeChange = () => {
  requireFinished.value = currentSetting.value?.require_finished ?? true
}

const saveCurrentSetting = async () => {
  const setting = currentSetting.value
  if (!setting) return

  saving.value = true
  try {
    const { data } = await settingsApi.updateUploadFinishSetting({
      model: setting.model,
      test_type: setting.test_type,
      environment: selectedEnvironment.value,
      oem: selectedOem.value,
      require_finished: requireFinished.value,
      copytemplate: configForm.copytemplate,
      result_cell: configForm.resultCell,
      total_result_cell: configForm.totalResultCell,
      failures: configForm.failures || 'N/A',
      csv_range: configForm.csvRange.split(',').map(item => item.trim()).filter(Boolean),
      summary_source_sheet_name: configForm.summarySourceSheet,
      copy_range: configForm.copyRange.split(',').map(item => item.trim()).filter(Boolean),
      pastefileid: configForm.pasteFileId,
      paste_start: configForm.pasteStart,
      paste_end: configForm.pasteEnd,
      last_row: lastRowRange.value
    })
    const index = uploadSettings.value.findIndex(item =>
      item.model === data.model && item.test_type === data.test_type && item.oem === data.oem
    )
    if (index >= 0) {
      uploadSettings.value.splice(index, 1, data)
    } else {
      uploadSettings.value.push(data)
    }
    settingsError.value = ''
    ElMessage.success(t('settings.saved'))
  } catch (error: any) {
    requireFinished.value = setting.require_finished
    const message = error?.response?.data?.detail?.message || error?.message || t('settings.saveFailed')
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchUploadSettings()
})
</script>

<style scoped>
.settings-view {
  height: 100%;
  padding: 0;
  background: #fff;
}

.settings-tabs-wrap {
  position: relative;
  height: 100%;
}

.settings-tabs {
  height: 100%;
  padding: 12px 16px 0;
}

.settings-tabs :deep(.el-tabs__content) {
  height: calc(100% - 48px);
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  box-sizing: border-box;
}

.settings-tabs :deep(.el-tab-pane) {
  min-height: 100%;
}

.tabs-actions {
  position: absolute;
  top: 10px;
  right: 16px;
  z-index: 2;
}

.settings-content {
  width: 100%;
  padding-top: 12px;
}

.settings-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 0 0 12px;
}

.environment-switch {
  flex: 0 0 auto;
}

.model-select {
  width: 220px;
  flex: 0 0 220px;
}

.test-select {
  width: 280px;
  flex: 0 0 280px;
}

.oem-select {
  width: 180px;
  flex: 0 0 180px;
}

.unified-config-form {
  max-width: 520px;
}

.setting-help-text {
  margin-top: 6px;
  color: #7b8794;
  font-size: 12px;
  line-height: 1.5;
}

.test-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.test-option small {
  color: #909399;
}

.settings-alert {
  margin-bottom: 12px;
}

.setting-panel {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #ebeef5;
  box-shadow: 0 6px 18px rgba(23, 33, 45, 0.08);
  background: #fff;
}

.setting-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #ebeef5;
}

.setting-main h3 {
  margin: 0;
  font-size: 16px;
  color: #17212d;
}

.setting-main p {
  margin: 6px 0 0;
  color: #606266;
  font-size: 13px;
}

.setting-desc {
  max-width: 720px;
  margin: 16px 20px 20px;
}

.upload-config-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
  padding: 0 20px;
}

.upload-config-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  padding: 4px 20px 20px;
}

@media (max-width: 700px) {
  .upload-config-form {
    grid-template-columns: 1fr;
  }
}
</style>
