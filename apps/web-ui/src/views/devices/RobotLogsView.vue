<template>
  <div class="robot-logs-view">
    <el-card class="logs-card" shadow="never">
      <template #header>
        <div class="logs-header">
          <div>
            <h2>{{ t('robotLogs.title') }}</h2>
            <p>{{ t('robotLogs.description') }}</p>
          </div>
        </div>
      </template>

      <div class="manual-upload-hint">
        {{ t('robotLogs.uploadHint') }}
      </div>

      <el-tabs v-model="activeTab" class="logs-tabs">
        <el-tab-pane :label="t('robotLogs.analysisRecords')" name="analysis" lazy>
          <DeviceAppLogAnalysisPanel />
        </el-tab-pane>
        <el-tab-pane :label="t('robotLogs.downloadRecords')" name="downloads" lazy>
          <DeviceLogHistoryPanel />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DeviceAppLogAnalysisPanel from '@/views/devices/components/DeviceAppLogAnalysisPanel.vue'
import DeviceLogHistoryPanel from '@/views/devices/components/DeviceLogHistoryPanel.vue'

const { t } = useI18n()
const activeTab = ref('analysis')
</script>

<style scoped>
.robot-logs-view {
  min-height: 100%;
  padding: 24px;
  box-sizing: border-box;
}

.logs-card {
  border: 1px solid #dfe6ee;
}

.logs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.logs-header h2 {
  margin: 0;
  color: #17212d;
  font-size: 20px;
}

.logs-header p {
  margin: 6px 0 0;
  color: #6b7785;
  font-size: 13px;
}

.manual-upload-hint {
  margin-bottom: 8px;
  color: #7b8794;
  font-size: 12px;
}

.logs-tabs :deep(.log-history-panel) {
  padding-top: 8px;
}

@media (max-width: 700px) {
  .robot-logs-view {
    padding: 12px;
  }

  .logs-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
