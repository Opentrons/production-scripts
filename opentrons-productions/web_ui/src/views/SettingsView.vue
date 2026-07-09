<template>
  <div class="settings-view">
    <div class="settings-tabs-wrap">
      <el-tabs v-model="activeTab" class="settings-tabs">
        <el-tab-pane label="数据上传" name="upload">
          <div class="settings-content">
            <el-alert
              v-if="settingsError"
              :title="settingsError"
              type="warning"
              show-icon
              :closable="false"
              class="settings-alert"
            />

            <section class="settings-toolbar">
              <el-select
                v-model="selectedModel"
                class="model-select"
                placeholder="产品"
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
                placeholder="测试"
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
            </section>

            <section class="setting-panel">
              <div class="setting-main">
                <div>
                  <h3>Finished 上传拦截</h3>
                  <p>控制当前产品和测试上传时，是否必须先通过 CSV finished 检查。</p>
                </div>
                <el-switch
                  v-model="requireFinished"
                  :disabled="!currentSetting || saving"
                  active-text="需要 Finished"
                  inactive-text="直接上传"
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
                <el-descriptions-item label="产品">{{ currentSetting.model }}</el-descriptions-item>
                <el-descriptions-item label="测试">
                  {{ formatTestType(currentSetting.test_type, currentSetting.test_display_name) }}
                </el-descriptions-item>
                <el-descriptions-item label="配置">{{ currentSetting.config_key }}</el-descriptions-item>
                <el-descriptions-item label="来源">
                  <el-tag :type="currentSetting.source === 'database' ? 'success' : 'info'" size="small">
                    {{ currentSetting.source === 'database' ? '数据库' : '默认兜底' }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>

              <el-empty v-else description="请选择产品和测试" />
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>
      <div class="tabs-actions">
        <el-tooltip content="刷新" placement="bottom">
          <el-button
            :icon="Refresh"
            :loading="loading"
            circle
            size="small"
            aria-label="刷新上传设置"
            @click="fetchUploadSettings"
          />
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { settingsApi } from '@/api'
import type {
  UploadFinishSettingItem,
  UploadFinishSettingOption,
} from '@/types'
import { formatTestType } from '@/utils/testNames'

const activeTab = ref('upload')
const loading = ref(false)
const saving = ref(false)
const selectedModel = ref('')
const selectedTestType = ref('')
const requireFinished = ref(true)
const settingsError = ref('')
const uploadOptions = ref<UploadFinishSettingOption[]>([])
const uploadSettings = ref<UploadFinishSettingItem[]>([])

const modelOptions = computed(() => {
  return Array.from(new Set(uploadOptions.value.map(option => option.model))).sort()
})

const availableTestOptions = computed(() => {
  return uploadOptions.value
    .filter(option => option.model === selectedModel.value)
    .sort((left, right) => formatTestType(left.test_type).localeCompare(formatTestType(right.test_type)))
})

const currentSetting = computed(() => {
  if (!selectedModel.value || !selectedTestType.value) return null
  return uploadSettings.value.find(setting =>
    setting.model === selectedModel.value && setting.test_type === selectedTestType.value
  ) || null
})

watch(currentSetting, setting => {
  requireFinished.value = setting?.require_finished ?? true
}, { immediate: true })

const fetchUploadSettings = async () => {
  loading.value = true
  settingsError.value = ''
  try {
    const { data } = await settingsApi.getUploadFinishSettings()
    uploadOptions.value = data.options || []
    uploadSettings.value = data.settings || []
    settingsError.value = data.database_available ? '' : (data.error || '数据库未连接')
    ensureSelection()
  } catch (error: any) {
    settingsError.value = error?.response?.data?.detail?.message || error?.message || '加载上传设置失败'
    ElMessage.error(settingsError.value)
  } finally {
    loading.value = false
  }
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
      require_finished: requireFinished.value
    })
    const index = uploadSettings.value.findIndex(item =>
      item.model === data.model && item.test_type === data.test_type
    )
    if (index >= 0) {
      uploadSettings.value.splice(index, 1, data)
    } else {
      uploadSettings.value.push(data)
    }
    settingsError.value = ''
    ElMessage.success('上传设置已保存')
  } catch (error: any) {
    requireFinished.value = setting.require_finished
    const message = error?.response?.data?.detail?.message || error?.message || '保存上传设置失败'
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
  gap: 10px;
  padding: 0 0 12px;
}

.model-select {
  width: 220px;
  flex: 0 0 220px;
}

.test-select {
  width: 280px;
  flex: 0 0 280px;
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
  width: min(760px, 100%);
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
</style>
