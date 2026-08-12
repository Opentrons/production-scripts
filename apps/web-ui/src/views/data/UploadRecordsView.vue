<template>
  <div class="upload-records-view">
    <el-card class="records-card">
      <template #header>
        <div class="card-header">
          <div class="title-group">
            <span class="card-title">{{ t('uploadRecords.title') }}</span>
            <span v-if="runningCount > 0" class="running-hint">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ t('uploadRecords.runningTasks', { count: runningCount }) }}
            </span>
          </div>
          <div class="header-tools">
            <el-button type="primary" size="small" @click="openManualUploadDialog">
              <el-icon><Upload /></el-icon>
              {{ t('uploadRecords.manualUpload') }}
            </el-button>
            <el-button
              type="primary"
              size="small"
              :icon="Refresh"
              @click="handleRefresh"
              :loading="loading"
            >{{ t('common.actions.refresh') }}</el-button>
          </div>
        </div>
      </template>

      <div class="filter-bar">
        <el-segmented
          v-model="filters.status"
          :options="statusOptions"
          size="small"
          @change="handleFilterChange"
        />
        <el-select
          v-model="filters.model"
          :placeholder="t('uploadRecords.product')"
          clearable
          filterable
          size="small"
          class="filter-control"
          @change="handleFilterChange"
        >
          <el-option
            v-for="model in filterOptions.models"
            :key="model"
            :label="model"
            :value="model"
          />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          :range-separator="t('uploadRecords.rangeSeparator')"
          :start-placeholder="t('uploadRecords.startDate')"
          :end-placeholder="t('uploadRecords.endDate')"
          value-format="YYYY-MM-DD"
          size="small"
          class="date-filter"
          @change="handleFilterChange"
        />
        <el-input
          v-model="filters.barcode"
          :placeholder="t('uploadRecords.searchPlaceholder')"
          clearable
          size="small"
          class="barcode-filter"
          @keyup.enter="handleFilterChange"
          @clear="handleFilterChange"
        />
        <el-button size="small" type="primary" plain @click="handleFilterChange" :loading="loading">
          {{ t('common.actions.search') }}
        </el-button>
        <el-button size="small" @click="handleResetFilters" :disabled="!hasActiveFilters">
          {{ t('uploadRecords.reset') }}
        </el-button>
      </div>

      <el-alert
        v-if="loadError"
        class="load-error-alert"
        type="error"
        :closable="false"
        show-icon
      >
        <template #title>
          <div class="load-error-content">
            <span>{{ t('uploadRecords.loadFailed', { error: loadError }) }}</span>
            <el-button size="small" type="danger" plain :loading="loading" @click="retryLoad">
              {{ t('common.actions.retry') }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <div v-if="!loadError && (!loading || records.length > 0)" class="stats-panel">
        <div class="stat-item">
          <span class="stat-label">{{ t('uploadRecords.totalSuccessRate') }}</span>
          <strong class="stat-value">{{ formatRate(stats.success_rate) }}</strong>
          <span class="stat-meta">{{ t('uploadRecords.completedCount', { success: stats.success, finished: stats.finished }) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">{{ t('uploadRecords.highestProduct') }}</span>
          <strong class="stat-value">{{ productLabel(stats.highest_product) }}</strong>
          <span class="stat-meta">{{ productMeta(stats.highest_product) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">{{ t('uploadRecords.lowestProduct') }}</span>
          <strong class="stat-value">{{ productLabel(stats.lowest_product) }}</strong>
          <span class="stat-meta">{{ productMeta(stats.lowest_product) }}</span>
        </div>
        <div class="pie-stat">
          <span class="pie-title">{{ t('uploadRecords.uploadStatus') }}</span>
          <div
            class="pie-wrap"
            @mousemove="handleSuccessPieHover"
            @mouseleave="clearSuccessPieHover"
            @click="handleSuccessPieClick"
          >
            <div class="interactive-pie" :style="successPieStyle">
              <span>{{ successPieCenterLabel }}</span>
            </div>
            <div
              v-if="activeSuccessItem && successPieTooltip.visible"
              class="pie-tooltip"
              :style="{
                left: `${successPieTooltip.x}px`,
                top: `${successPieTooltip.y}px`
              }"
            >
              <span class="pie-tooltip-name">{{ activeSuccessItem.label }}</span>
              <strong>{{ activeSuccessItem.count }}</strong>
            </div>
          </div>
        </div>
        <div class="pie-stat">
          <span class="pie-title">{{ t('uploadRecords.averageDuration') }}</span>
          <div
            class="pie-wrap"
            @mousemove="handleDurationPieHover"
            @mouseleave="clearDurationPieHover"
            @click="handleDurationPieClick"
          >
            <div class="interactive-pie" :style="durationPieStyle">
              <span>{{ durationPieCenterLabel }}</span>
            </div>
            <div
              v-if="activeDurationItem && durationPieTooltip.visible"
              class="pie-tooltip"
              :style="{
                left: `${durationPieTooltip.x}px`,
                top: `${durationPieTooltip.y}px`
              }"
            >
              <span class="pie-tooltip-name">{{ formatDurationTooltipName(activeDurationItem) }}</span>
              <strong>{{ formatDurationSeconds(activeDurationItem.avg_seconds) }}</strong>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loadError && (!loading || records.length > 0)" class="table-info">
        <span class="total-count">{{ t('uploadRecords.totalRecords', { count: total }) }}</span>
        <span v-if="isAutoRefreshing" class="auto-refresh">
          <el-icon class="is-loading"><Loading /></el-icon>
          {{ t('uploadRecords.autoRefreshing') }}
        </span>
      </div>

      <el-table
        v-if="records.length > 0 && !loadError"
        :data="records"
        v-loading="loading"
        stripe
        style="width: 100%"
        :max-height="tableHeight"
      >
        <el-table-column :label="t('uploadRecords.columns.startedAt')" min-width="170" fixed="left">
          <template #default="{ row }">
            {{ formatDateTime(row.request_started_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.status')" min-width="210" fixed="left">
          <template #default="{ row }">
            <div class="status-cell">
              <div class="status-main">
                <el-icon v-if="row.status === 'running'" class="is-loading running-icon">
                  <Loading />
                </el-icon>
                <el-tag :type="statusTagType(row.status)" size="small" effect="light">
                  {{ statusText(row.status) }}
                </el-tag>
              </div>
              <span v-if="row.progress_message" class="progress-message">
                {{ row.progress_message }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.file')" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-cell">
              <span class="file-name">{{ displayValue(row.csv_file?.name) }}</span>
              <span v-if="displayValue(row.zip_file?.name) !== '-'" class="zip-name">{{ displayValue(row.zip_file?.name) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="SN" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ displayValue(row.file_desc?.sn || row.result?.sn || row.upload_result?.sn) }}
          </template>
        </el-table-column>

        <el-table-column label="Model" min-width="100">
          <template #default="{ row }">
            {{ displayValue(row.file_desc?.model || row.result?.model || row.upload_result?.model) }}
          </template>
        </el-table-column>

        <el-table-column label="Test Type" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatTestType(row.result?.test_type || row.file_desc?.test_type || row.upload_result?.upload_config_key, '-') }}
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.upload')" min-width="95">
          <template #default="{ row }">
            <StepStatus :value="row.upload_success" :running="row.status === 'running' && row.upload_success === null" />
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.database')" min-width="95">
          <template #default="{ row }">
            <StepStatus :value="row.database_success" :running="row.status === 'running' && row.database_success === null" />
          </template>
        </el-table-column>

        <el-table-column label="Slack" min-width="95">
          <template #default="{ row }">
            <StepStatus :value="row.slack_success" :running="row.status === 'running' && row.slack_success === null" />
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.finishedAt')" min-width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.request_finished_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.duration')" min-width="100">
          <template #default="{ row }">
            {{ formatDuration(row.request_started_at, row.request_finished_at) }}
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.sheet')" min-width="95">
          <template #default="{ row }">
            <a
              v-if="getCsvLink(row)"
              :href="getCsvLink(row)"
              target="_blank"
              rel="noopener noreferrer"
              class="link-cell"
            >
              {{ t('uploadRecords.open') }}
            </a>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.masterSheet')" min-width="95">
          <template #default="{ row }">
            <a
              v-if="getUnitTrackerLink(row)"
              :href="getUnitTrackerLink(row)"
              target="_blank"
              rel="noopener noreferrer"
              class="link-cell"
            >
              {{ t('uploadRecords.open') }}
            </a>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.rawData')" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <a
              v-if="getRawDataLink(row)"
              :href="getRawDataLink(row)"
              target="_blank"
              rel="noopener noreferrer"
              class="link-cell"
            >
              {{ getRawDataName(row) || t('uploadRecords.open') }}
            </a>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column :label="t('uploadRecords.columns.error')" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'error-text': getErrorMessage(row) !== '-' }">
              {{ getErrorMessage(row) }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div v-else-if="loading && !loadError" class="records-loading-state">
        <el-icon class="is-loading records-loading-icon"><Loading /></el-icon>
        <span>{{ t('uploadRecords.loading') }}</span>
      </div>

      <el-empty v-else-if="!loading && !loadError" :description="t('uploadRecords.empty')" />

      <div class="pagination-container" v-if="!loadError && total > 0">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="handlePageChange"
        />
      </div>

      <el-dialog
        v-model="manualUploadVisible"
        :title="t('uploadRecords.manualDialog.title')"
        width="720px"
        destroy-on-close
        :close-on-click-modal="!manualDialogBusy"
        :close-on-press-escape="!manualDialogBusy"
        :show-close="!manualDialogBusy"
        @closed="resetManualUploadState"
      >
        <el-tabs v-model="manualUploadTab" class="manual-upload-tabs">
          <el-tab-pane :label="t('uploadRecords.tabs.standard')" name="standard">
            <el-form label-position="top">
              <el-form-item>
                <el-segmented
                  v-model="standardUploadMode"
                  :options="standardUploadModeOptions"
                  size="small"
                  class="standard-upload-mode"
                />
              </el-form-item>

              <template v-if="standardUploadMode === 'local'">
                <el-form-item :label="t('uploadRecords.uploadFile')">
                  <el-upload
                    class="manual-upload"
                    drag
                    :auto-upload="false"
                    :limit="1"
                    accept=".csv,text/csv"
                    :on-change="handleManualFileChange"
                    :on-remove="handleManualFileRemove"
                    :on-exceed="handleManualFileExceed"
                  >
                    <el-icon class="upload-icon"><UploadFilled /></el-icon>
                    <div class="upload-text">{{ t('uploadRecords.chooseCsv') }}</div>
                  </el-upload>
                </el-form-item>
                <el-form-item>
                  <el-checkbox v-model="includeSourceZip">{{ t('uploadRecords.includeSource') }}</el-checkbox>
                </el-form-item>
                <el-form-item v-if="includeSourceZip">
                  <el-checkbox v-model="uploadAllFiles">{{ t('uploadRecords.uploadFolder') }}</el-checkbox>
                </el-form-item>
                <el-alert
                  v-if="includeSourceZip && uploadAllFiles"
                  type="warning"
                  show-icon
                  :closable="false"
                >
                  <template #title>
                    <div class="source-warning">
                      <div>{{ t('uploadRecords.folderWarning') }}</div>
                      <div>{{ t('uploadRecords.folderLimit') }}</div>
                    </div>
                  </template>
                </el-alert>
              </template>

              <div v-else class="standard-robot-panel">
                <div class="standard-robot-toolbar">
                  <el-select
                    v-model="standardRobotIp"
                    :placeholder="t('uploadRecords.robotPlaceholder')"
                    filterable
                    allow-create
                    default-first-option
                    size="small"
                    class="standard-robot-select"
                    :loading="standardRobotScanLoading"
                    @change="handleStandardRobotChange"
                  >
                    <el-option
                      v-for="robot in onlineRobotOptions"
                      :key="robot.ip"
                      :label="formatRobotOption(robot)"
                      :value="robot.ip"
                    />
                  </el-select>
                  <el-button
                    size="small"
                    plain
                    :icon="Refresh"
                    :loading="standardRobotScanLoading"
                    @click="refreshStandardRobots"
                  >{{ t('uploadRecords.refreshDevices') }}</el-button>
                  <el-button
                    size="small"
                    type="primary"
                    plain
                    :icon="Refresh"
                    :disabled="!standardRobotIp"
                    :loading="standardRobotLoading"
                    @click="refreshStandardRobotFiles"
                  >{{ t('uploadRecords.refreshDirectory') }}</el-button>
                </div>

                <div class="standard-robot-path-row">
                  <el-button
                    size="small"
                    text
                    :disabled="!canGoUpStandardRobotPath"
                    @click="goUpStandardRobotPath"
                  >
                    {{ t('uploadRecords.parentDirectory') }}
                  </el-button>
                  <span class="standard-robot-path">{{ standardRobotPath }}</span>
                </div>

                <el-alert
                  v-if="standardRobotError"
                  class="scan-error-alert"
                  type="error"
                  :closable="false"
                  show-icon
                >
                  <template #title>
                    <div class="load-error-content">
                      <span>{{ t('uploadRecords.robotScanFailed', { error: standardRobotError }) }}</span>
                      <el-button
                        size="small"
                        type="danger"
                        plain
                        :loading="standardRobotLoading || standardRobotScanLoading"
                        @click="retryStandardRobotScan"
                      >
                        {{ t('common.actions.retry') }}
                      </el-button>
                    </div>
                  </template>
                </el-alert>

                <div v-if="standardRobotFiles.length" class="standard-robot-file-list">
                  <button
                    v-for="entry in sortedStandardRobotFiles"
                    :key="entry.path"
                    type="button"
                    class="standard-robot-file-row"
                    :class="{ 'is-selected': standardSelectedRobotFile?.path === entry.path }"
                    @click="handleStandardRobotEntryClick(entry)"
                  >
                    <el-icon>
                      <FolderOpened v-if="entry.is_dir" />
                      <DocumentIcon v-else />
                    </el-icon>
                    <span class="standard-robot-file-name">{{ entry.name }}</span>
                    <span class="standard-robot-file-path">{{ entry.path }}</span>
                    <span class="standard-robot-file-size">{{ entry.is_dir ? t('uploadRecords.directory') : formatFileSize(entry.size) }}</span>
                  </button>
                </div>
                <el-empty
                  v-else-if="standardRobotSearched && !standardRobotLoading && !standardRobotError"
                  :description="t('uploadRecords.directoryEmpty')"
                />
              </div>
            </el-form>
          </el-tab-pane>
          <el-tab-pane :label="t('uploadRecords.tabs.zStage')" name="z_stage">
            <div class="z-stage-panel">
              <div class="z-stage-fields">
                <label class="field-line">
                  <span>{{ t('uploadRecords.zStageFixture') }}</span>
                  <el-input v-model="zStageFixtureIp" placeholder="192.168.6.13" />
                </label>
                <label class="field-line">
                  <span>Robot SN</span>
                  <el-input v-model="zStageRobotSn" placeholder="FLXU..." />
                </label>
              </div>

              <el-segmented
                v-model="zStageUploadMode"
                :options="zStageUploadModeOptions"
                size="small"
                class="z-stage-mode"
              />

              <div v-if="zStageUploadMode === 'remote'" class="z-stage-section">
                <div class="remote-search-row">
                  <el-input v-model="zStageRemotePath" placeholder="/data/testing_data/z_stage_test" />
                  <el-button
                    type="primary"
                    plain
                    :loading="zStageSearching"
                    :disabled="!canSearchZStageRemote"
                    @click="searchZStageRemoteFiles"
                  >
                    {{ t('common.actions.search') }}
                  </el-button>
                </div>

                <el-alert
                  v-if="zStageSearchError"
                  class="scan-error-alert"
                  type="error"
                  :closable="false"
                  show-icon
                >
                  <template #title>
                    <div class="load-error-content">
                      <span>{{ t('uploadRecords.zStageScanFailed', { error: zStageSearchError }) }}</span>
                      <el-button size="small" type="danger" plain :loading="zStageSearching" @click="searchZStageRemoteFiles">
                        {{ t('common.actions.retry') }}
                      </el-button>
                    </div>
                  </template>
                </el-alert>

                <div v-if="zStageRemoteFiles.length" class="remote-file-panel">
                  <div class="remote-file-head">
                    <el-checkbox
                      :model-value="allZStageRemoteSelected"
                      :indeterminate="someZStageRemoteSelected && !allZStageRemoteSelected"
                      :disabled="zStageUploading"
                      @change="toggleAllZStageRemoteFiles"
                    >
                      {{ t('uploadRecords.csvFound', { count: zStageRemoteFiles.length }) }}
                    </el-checkbox>
                  </div>
                  <div class="remote-file-list">
                    <label
                      v-for="file in zStageRemoteFiles"
                      :key="file.path"
                      class="remote-file-row"
                    >
                      <el-checkbox
                        :model-value="file.selected"
                        :disabled="zStageUploading"
                        @change="toggleZStageRemoteFile(file.path, $event)"
                      />
                      <span class="remote-file-name">{{ file.name }}</span>
                      <span class="remote-file-path">{{ file.path }}</span>
                      <el-tag
                        v-if="file.status && file.status !== 'pending'"
                        :type="file.status === 'success' ? 'success' : file.status === 'failed' ? 'danger' : 'warning'"
                        size="small"
                      >
                        {{ getZStageFileStatusLabel(file.status) }}
                      </el-tag>
                    </label>
                  </div>
                </div>
                <el-empty
                  v-else-if="zStageRemoteSearched && !zStageSearching && !zStageSearchError"
                  :description="t('uploadRecords.noMatchingCsv')"
                />
              </div>

              <div v-else class="z-stage-section">
                <el-upload
                  class="manual-upload"
                  drag
                  :auto-upload="false"
                  :limit="1"
                  accept=".csv,text/csv"
                  :on-change="handleZStageLocalFileChange"
                  :on-remove="handleZStageLocalFileRemove"
                  :on-exceed="handleZStageLocalFileExceed"
                >
                  <el-icon class="upload-icon"><UploadFilled /></el-icon>
                  <div class="upload-text">{{ t('uploadRecords.chooseZStageCsv') }}</div>
                </el-upload>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane :label="t('uploadRecords.tabs.pipetteOptical')" name="pipette_optical">
            <el-empty :description="t('uploadRecords.pipetteOpticalPending')" />
          </el-tab-pane>
        </el-tabs>
        <template #footer>
          <el-button @click="manualUploadVisible = false" :disabled="manualDialogBusy">{{ t('common.actions.cancel') }}</el-button>
          <el-button
            v-if="manualUploadTab === 'standard'"
            type="primary"
            @click="submitManualUpload"
            :loading="manualUploading"
            :disabled="!canSubmitManualUpload"
          >
            {{ t('uploadRecords.submitUpload') }}
          </el-button>
          <el-button
            v-else-if="manualUploadTab === 'z_stage' && zStageUploadMode === 'remote'"
            type="primary"
            @click="submitZStageRemoteUpload"
            :loading="zStageUploading"
            :disabled="!canSubmitZStageRemote"
          >
            {{ t('uploadRecords.uploadSelected') }}
          </el-button>
          <el-button
            v-else-if="manualUploadTab === 'z_stage'"
            type="primary"
            @click="submitZStageLocalUpload"
            :loading="zStageUploading"
            :disabled="!canSubmitZStageLocal"
          >
            {{ t('uploadRecords.submitUpload') }}
          </el-button>
          <el-button v-else type="primary" disabled>{{ t('uploadRecords.submitUpload') }}</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElIcon, ElMessage, ElMessageBox, ElTag, ElTooltip } from 'element-plus'
import type { UploadFile, UploadFiles } from 'element-plus'
import { Check, Close, Document as DocumentIcon, FolderOpened, Loading, Minus, Refresh, Upload, UploadFilled } from '@element-plus/icons-vue'
import { robotApi, uploadRecordApi } from '@/scripts/api'
import type { RobotFileEntry, RobotInfo } from '@/scripts/api'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import { formatTestType } from '@/scripts/utils/testNames'
import { useAppLocale } from '@/i18n'
import type {
  UploadProductStats,
  UploadRecordItem,
  UploadRecordStatsResponse,
  UploadTestDurationStats
} from '@/scripts/types'

const DURATION_PIE_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9b59b6', '#1abc9c']
const { t } = useI18n()
const { locale } = useAppLocale()

interface PieSegment<T> {
  item: T
  color: string
  startPercent: number
  endPercent: number
}

interface SuccessPieItem {
  key: string
  label: string
  count: number
  color: string
}

type ManualUploadTab = 'standard' | 'z_stage' | 'pipette_optical'
type StandardUploadMode = 'local' | 'robot'
type ZStageUploadMode = 'remote' | 'local'
type ZStageRemoteFileStatus = 'pending' | 'uploading' | 'success' | 'failed'

interface ZStageRemoteFile {
  name: string
  path: string
  size: number
  modified_at: number | null
  selected: boolean
  status: ZStageRemoteFileStatus
  error?: string
}

const buildPieSegments = <T,>(
  items: T[],
  getValue: (item: T) => number,
  getColor: (item: T, index: number) => string
): PieSegment<T>[] => {
  const total = items.reduce((sum, item) => sum + getValue(item), 0)
  if (total <= 0) return []

  let current = 0
  return items.map((item, index) => {
    const startPercent = current
    current += (getValue(item) / total) * 100
    return {
      item,
      color: getColor(item, index),
      startPercent,
      endPercent: current
    }
  })
}

const buildConicGradientStyle = (segments: PieSegment<unknown>[]) => {
  if (!segments.length) {
    return { background: '#ebeef5' }
  }
  const stops = segments.map(
    (segment) => `${segment.color} ${segment.startPercent}% ${segment.endPercent}%`
  )
  return { background: `conic-gradient(${stops.join(', ')})` }
}

const resolvePieSegmentIndex = (
  event: MouseEvent,
  pieWrap: HTMLElement,
  segments: PieSegment<unknown>[]
) => {
  const pie = pieWrap.querySelector('.interactive-pie') as HTMLElement | null
  if (!pie || !segments.length) return -1

  const rect = pie.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  const dx = event.clientX - centerX
  const dy = event.clientY - centerY
  const distance = Math.hypot(dx, dy)
  const outerRadius = rect.width / 2
  const innerRadius = outerRadius - 10
  if (distance < innerRadius || distance > outerRadius) return -1

  let angle = (Math.atan2(dx, -dy) * 180) / Math.PI
  if (angle < 0) angle += 360
  const percent = (angle / 360) * 100

  return segments.findIndex((segment, index, allSegments) => {
    const isLast = index === allSegments.length - 1
    return (
      percent >= segment.startPercent &&
      (percent < segment.endPercent || (isLast && percent <= segment.endPercent))
    )
  })
}

const updatePieTooltip = (
  event: MouseEvent,
  index: number,
  tooltipState: { visible: boolean; x: number; y: number }
) => {
  const pieWrap = event.currentTarget as HTMLElement
  const wrapRect = pieWrap.getBoundingClientRect()
  tooltipState.visible = index >= 0
  tooltipState.x = event.clientX - wrapRect.left + 12
  tooltipState.y = event.clientY - wrapRect.top - 10
}

const AUTO_REFRESH_INTERVAL_MS = 3000
const IDLE_REFRESH_INTERVAL_MS = 10000

const records = ref<UploadRecordItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const loading = ref(true)
const loadError = ref('')
const manualUploadVisible = ref(false)
const manualUploadTab = ref<ManualUploadTab>('standard')
const standardUploadMode = ref<StandardUploadMode>('local')
const manualUploading = ref(false)
const manualFile = ref<File | null>(null)
const includeSourceZip = ref(false)
const uploadAllFiles = ref(false)
const robotScanStore = useRobotScanStore()
const standardRobotScanLoading = ref(false)
const standardRobotIp = ref('')
const standardRobotPath = ref('/data/testing_data')
const standardRobotFiles = ref<RobotFileEntry[]>([])
const standardSelectedRobotFile = ref<RobotFileEntry | null>(null)
const standardRobotLoading = ref(false)
const standardRobotSearched = ref(false)
const standardRobotError = ref('')
const standardRobotRetryMode = ref<'devices' | 'files'>('devices')
const zStageFixtureIp = ref('192.168.6.13')
const zStageRobotSn = ref('')
const zStageRemotePath = ref('/data/testing_data/z_stage_test')
const zStageUploadMode = ref<ZStageUploadMode>('remote')
const zStageSearching = ref(false)
const zStageUploading = ref(false)
const zStageRemoteSearched = ref(false)
const zStageRemoteFiles = ref<ZStageRemoteFile[]>([])
const zStageSearchError = ref('')
const zStageLocalFile = ref<File | null>(null)
const watchedRecordId = ref('')
const filterOptions = ref({
  models: [] as string[],
  statuses: [] as string[]
})
const filters = ref({
  status: '',
  model: '',
  barcode: '',
  dateRange: [] as string[]
})
const stats = ref<UploadRecordStatsResponse>({
  total: 0,
  finished: 0,
  success: 0,
  failed: 0,
  running: 0,
  success_rate: 0,
  highest_product: null,
  lowest_product: null,
  products: [],
  test_durations: []
})
let refreshTimer: ReturnType<typeof setInterval> | undefined
let refreshIntervalMs = 0

const statusOptions = computed(() => [
  { label: t('uploadRecords.status.all'), value: '' },
  { label: t('common.status.running'), value: 'running' },
  { label: t('uploadRecords.status.success'), value: 'success' },
  { label: t('common.status.error'), value: 'failed' }
])

const standardUploadModeOptions = computed(() => [
  { label: t('uploadRecords.localFile'), value: 'local' },
  { label: t('uploadRecords.onlineRobot'), value: 'robot' }
])

const zStageUploadModeOptions = computed(() => [
  { label: t('uploadRecords.fixtureSearch'), value: 'remote' },
  { label: t('uploadRecords.localCsv'), value: 'local' }
])

const onlineRobotOptions = computed<RobotInfo[]>(() => {
  return (robotScanStore.scanResult?.online_robots || [])
    .filter(robot => robot.online)
    .sort((a, b) => a.ip.localeCompare(b.ip))
})

const sortedStandardRobotFiles = computed(() => {
  return [...standardRobotFiles.value].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    return a.name.localeCompare(b.name)
  })
})

const canGoUpStandardRobotPath = computed(() => {
  return standardRobotPath.value !== '/data/testing_data'
})

const selectedZStageRemoteFiles = computed(() => zStageRemoteFiles.value.filter(file => file.selected))
const allZStageRemoteSelected = computed(
  () => zStageRemoteFiles.value.length > 0 && selectedZStageRemoteFiles.value.length === zStageRemoteFiles.value.length
)
const someZStageRemoteSelected = computed(() => selectedZStageRemoteFiles.value.length > 0)
const canSearchZStageRemote = computed(
  () => Boolean(zStageFixtureIp.value.trim() && zStageRobotSn.value.trim() && zStageRemotePath.value.trim())
)
const canSubmitZStageRemote = computed(
  () => Boolean(zStageRobotSn.value.trim() && selectedZStageRemoteFiles.value.length > 0)
)
const canSubmitZStageLocal = computed(() => Boolean(zStageRobotSn.value.trim() && zStageLocalFile.value))
const canSubmitManualUpload = computed(() => {
  if (standardUploadMode.value === 'local') return Boolean(manualFile.value)
  return Boolean(standardRobotIp.value && standardSelectedRobotFile.value && !standardSelectedRobotFile.value.is_dir)
})
const manualDialogBusy = computed(() => manualUploading.value || zStageSearching.value || zStageUploading.value || standardRobotLoading.value || standardRobotScanLoading.value)

watch(includeSourceZip, (checked) => {
  if (!checked) {
    uploadAllFiles.value = false
  }
})

watch(standardUploadMode, (mode) => {
  if (mode === 'robot') {
    ensureStandardRobotsLoaded().then(() => {
      if (standardRobotIp.value && !standardRobotFiles.value.length && !standardRobotSearched.value) {
        refreshStandardRobotFiles()
      }
    })
  }
})

const openManualUploadDialog = () => {
  manualUploadVisible.value = true
  resetManualUploadState()
}

const resetManualUploadState = () => {
  manualUploadTab.value = 'standard'
  standardUploadMode.value = 'local'
  manualFile.value = null
  includeSourceZip.value = false
  uploadAllFiles.value = false
  standardRobotIp.value = onlineRobotOptions.value[0]?.ip || ''
  standardRobotPath.value = '/data/testing_data'
  standardRobotFiles.value = []
  standardSelectedRobotFile.value = null
  standardRobotLoading.value = false
  standardRobotSearched.value = false
  standardRobotError.value = ''
  standardRobotRetryMode.value = 'devices'
  zStageFixtureIp.value = '192.168.6.13'
  zStageRobotSn.value = ''
  zStageRemotePath.value = '/data/testing_data/z_stage_test'
  zStageUploadMode.value = 'remote'
  zStageSearching.value = false
  zStageUploading.value = false
  zStageRemoteSearched.value = false
  zStageRemoteFiles.value = []
  zStageSearchError.value = ''
  zStageLocalFile.value = null
}

const normalizeUploadError = (error: any) => {
  const detail = error?.response?.data?.detail
  return detail?.message || detail?.error || error?.message || ''
}

const formatUploadResponseError = (value: unknown) => {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') {
    const detail = value as Record<string, unknown>
    return String(detail.message || detail.error || JSON.stringify(value))
  }
  return String(value || t('errors.unknown'))
}

const throwOnUploadResponseError = (response: any) => {
  const message = response?.data?.error
  if (message) {
    throw new Error(formatUploadResponseError(message))
  }
}

const getCsvRawFile = (file: UploadFile | File | undefined) => {
  const rawFile = file instanceof File ? file : file?.raw
  if (!rawFile) return null
  if (!rawFile.name.toLowerCase().endsWith('.csv')) {
    ElMessage.error(t('uploadRecords.messages.csvOnly'))
    return null
  }
  return rawFile
}

const handleManualFileChange = (file: UploadFile) => {
  const rawFile = getCsvRawFile(file)
  if (!rawFile) {
    manualFile.value = null
    return
  }
  manualFile.value = rawFile
}

const handleManualFileRemove = () => {
  manualFile.value = null
}

const handleManualFileExceed = (files: File[], uploadFiles: UploadFiles) => {
  uploadFiles.splice(0, uploadFiles.length)
  const rawFile = getCsvRawFile(files[0])
  if (!rawFile) {
    manualFile.value = null
    return
  }
  manualFile.value = rawFile
  ElMessage.warning(t('uploadRecords.messages.csvReplaced'))
}

const formatRobotOption = (robot: RobotInfo) => {
  const sn = robot.serial_number || robot.name || robot.robot_type || ''
  return sn ? `${robot.ip} · ${sn}` : robot.ip
}

const refreshStandardRobots = async () => {
  standardRobotScanLoading.value = true
  standardRobotError.value = ''
  standardRobotRetryMode.value = 'devices'
  try {
    const result = await robotScanStore.refreshScan({ silent: false })
    if (!standardRobotIp.value && result?.online_robots?.length) {
      standardRobotIp.value = result.online_robots[0].ip
    }
    ElMessage.success(t('uploadRecords.messages.devicesFound', { count: result?.online_robots?.length || 0 }))
  } catch (error: any) {
    standardRobotError.value = normalizeUploadError(error) || t('errors.unknown')
  } finally {
    standardRobotScanLoading.value = false
  }
}

const ensureStandardRobotsLoaded = async () => {
  if (!robotScanStore.scanResult) {
    try {
      await robotScanStore.loadCachedScan()
    } catch {
      robotScanStore.loadFromCache()
    }
  }
  if (!standardRobotIp.value) {
    standardRobotIp.value = onlineRobotOptions.value[0]?.ip || ''
  }
}

const handleStandardRobotChange = () => {
  standardRobotPath.value = '/data/testing_data'
  standardRobotFiles.value = []
  standardSelectedRobotFile.value = null
  standardRobotSearched.value = false
  standardRobotError.value = ''
  refreshStandardRobotFiles()
}

const refreshStandardRobotFiles = async () => {
  if (!standardRobotIp.value) {
    ElMessage.warning(t('uploadRecords.messages.selectRobot'))
    return
  }
  standardRobotLoading.value = true
  standardRobotSearched.value = false
  standardSelectedRobotFile.value = null
  standardRobotError.value = ''
  standardRobotRetryMode.value = 'files'
  try {
    const response = await robotApi.listFiles(standardRobotIp.value, normalizeRemotePath(standardRobotPath.value))
    standardRobotFiles.value = response.data.entries || []
    standardRobotPath.value = response.data.path || standardRobotPath.value
    standardRobotSearched.value = true
  } catch (error: any) {
    standardRobotSearched.value = true
    standardRobotFiles.value = []
    standardRobotError.value = normalizeUploadError(error) || t('errors.unknown')
  } finally {
    standardRobotLoading.value = false
  }
}

const retryStandardRobotScan = () => {
  if (standardRobotRetryMode.value === 'files') {
    refreshStandardRobotFiles()
    return
  }
  refreshStandardRobots()
}

const handleStandardRobotEntryClick = (entry: RobotFileEntry) => {
  if (entry.is_dir) {
    standardRobotPath.value = entry.path
    refreshStandardRobotFiles()
    return
  }
  if (!entry.name.toLowerCase().endsWith('.csv')) {
    ElMessage.warning(t('uploadRecords.messages.selectCsv'))
    return
  }
  standardSelectedRobotFile.value = entry
}

const goUpStandardRobotPath = () => {
  const normalized = normalizeRemotePath(standardRobotPath.value)
  if (normalized === '/data/testing_data') return
  const parent = normalized.split('/').slice(0, -1).join('/') || '/'
  standardRobotPath.value = parent.startsWith('/data/testing_data') ? parent : '/data/testing_data'
  refreshStandardRobotFiles()
}

const formatFileSize = (size?: number) => {
  const value = Number(size || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

const handleZStageLocalFileChange = (file: UploadFile) => {
  const rawFile = getCsvRawFile(file)
  if (!rawFile) {
    zStageLocalFile.value = null
    return
  }
  zStageLocalFile.value = rawFile
}

const handleZStageLocalFileRemove = () => {
  zStageLocalFile.value = null
}

const handleZStageLocalFileExceed = (files: File[], uploadFiles: UploadFiles) => {
  uploadFiles.splice(0, uploadFiles.length)
  const rawFile = getCsvRawFile(files[0])
  if (!rawFile) {
    zStageLocalFile.value = null
    return
  }
  zStageLocalFile.value = rawFile
  ElMessage.warning(t('uploadRecords.messages.csvReplaced'))
}

const getZStageMeta = () => {
  const sn = zStageRobotSn.value.trim()
  return {
    test_tag: sn,
    test_device_id: sn,
    'serial-number': sn,
    test_type: 'z_stage_test'
  }
}

const getZStageFileStatusLabel = (status: ZStageRemoteFileStatus) => {
  if (status === 'uploading') return t('uploadRecords.status.uploading')
  if (status === 'success') return t('uploadRecords.status.success')
  if (status === 'failed') return t('common.status.error')
  return t('uploadRecords.status.pending')
}

const normalizeRemotePath = (path: string) => {
  const normalized = path.trim().replace(/\/+$/, '')
  return normalized || '/'
}

const isSnMatchedCsv = (entry: RobotFileEntry, sn: string) => {
  return !entry.is_dir && entry.name.toLowerCase().endsWith('.csv') && entry.name.includes(sn)
}

const searchRemoteCsvFiles = async (
  ip: string,
  rootPath: string,
  sn: string,
  maxDirectories = 80
): Promise<ZStageRemoteFile[]> => {
  const queue = [rootPath]
  const matched = new Map<string, ZStageRemoteFile>()
  let scanned = 0

  while (queue.length && scanned < maxDirectories) {
    const currentPath = queue.shift() as string
    scanned += 1
    const response = await robotApi.listFiles(ip, currentPath)
    for (const entry of response.data.entries || []) {
      if (entry.is_dir) {
        queue.push(entry.path)
      } else if (isSnMatchedCsv(entry, sn)) {
        matched.set(entry.path, {
          name: entry.name,
          path: entry.path,
          size: entry.size,
          modified_at: entry.modified_at,
          selected: true,
          status: 'pending'
        })
      }
    }
  }

  if (queue.length) {
    ElMessage.warning(t('uploadRecords.messages.directoryLimit', { count: maxDirectories }))
  }
  return Array.from(matched.values()).sort((a, b) => a.path.localeCompare(b.path))
}

const searchZStageRemoteFiles = async () => {
  if (!canSearchZStageRemote.value) {
    ElMessage.warning(t('uploadRecords.messages.fillZStageIdentity'))
    return
  }

  zStageSearching.value = true
  zStageRemoteSearched.value = false
  zStageRemoteFiles.value = []
  zStageSearchError.value = ''
  try {
    zStageRemoteFiles.value = await searchRemoteCsvFiles(
      zStageFixtureIp.value.trim(),
      normalizeRemotePath(zStageRemotePath.value),
      zStageRobotSn.value.trim()
    )
    zStageRemoteSearched.value = true
    if (zStageRemoteFiles.value.length) {
      ElMessage.success(t('uploadRecords.messages.csvFound', { count: zStageRemoteFiles.value.length }))
    }
  } catch (error: any) {
    zStageRemoteSearched.value = true
    zStageSearchError.value = normalizeUploadError(error) || t('errors.unknown')
  } finally {
    zStageSearching.value = false
  }
}

const toggleAllZStageRemoteFiles = (checked: boolean) => {
  zStageRemoteFiles.value = zStageRemoteFiles.value.map(file => ({
    ...file,
    selected: checked
  }))
}

const toggleZStageRemoteFile = (path: string, checked: boolean) => {
  const file = zStageRemoteFiles.value.find(item => item.path === path)
  if (file) {
    file.selected = checked
  }
}

const blobToCsvFile = (blob: Blob, filename: string) => {
  return new File([blob], filename, { type: 'text/csv' })
}

const afterUploadSubmitted = async (recordId?: string | null) => {
  currentPage.value = 1
  filters.value.status = ''
  watchedRecordId.value = recordId || ''
  startAutoRefresh(AUTO_REFRESH_INTERVAL_MS)
  await fetchRecords(true)
}

const uploadZStageFile = async (file: File) => {
  return uploadRecordApi.uploadManualData(file, false, false, getZStageMeta())
}

const StepStatus = defineComponent({
  name: 'StepStatus',
  props: {
    value: {
      type: [Boolean, null],
      default: null
    },
    running: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    return () => {
      if (props.running) {
        return h('span', { class: 'step-status pending' }, [
          h(ElIcon, { class: 'is-loading' }, () => h(Loading)),
          h('span', t('common.status.running'))
        ])
      }
      if (props.value === true) {
        return h(ElTag, { type: 'success', size: 'small', effect: 'light' }, () => [
          h(ElIcon, null, () => h(Check)),
          h('span', t('uploadRecords.status.success'))
        ])
      }
      if (props.value === false) {
        return h(ElTag, { type: 'danger', size: 'small', effect: 'light' }, () => [
          h(ElIcon, null, () => h(Close)),
          h('span', t('common.status.error'))
        ])
      }
      return h(ElTag, { type: 'info', size: 'small', effect: 'plain' }, () => [
        h(ElIcon, null, () => h(Minus)),
        h('span', '-')
      ])
    }
  }
})

const runningCount = computed(() => records.value.filter((item) => item.status === 'running').length)
const isAutoRefreshing = computed(() => runningCount.value > 0 || filters.value.status === 'running')
const hasActiveFilters = computed(() => {
  return Boolean(
    filters.value.status ||
    filters.value.model ||
    filters.value.barcode ||
    filters.value.dateRange?.length
  )
})

const tableHeight = computed(() => {
  return window.innerHeight - 430
})

const durationPieColors = DURATION_PIE_COLORS
const activeSuccessIndex = ref(-1)
const activeDurationIndex = ref(-1)
const successPieTooltip = ref({
  visible: false,
  x: 0,
  y: 0
})
const durationPieTooltip = ref({
  visible: false,
  x: 0,
  y: 0
})

const successPieItems = computed<SuccessPieItem[]>(() => {
  return [
    { key: 'success', label: t('uploadRecords.status.success'), count: stats.value.success, color: '#67c23a' },
    { key: 'failed', label: t('common.status.error'), count: stats.value.failed, color: '#f56c6c' },
    { key: 'running', label: t('common.status.running'), count: stats.value.running, color: '#e6a23c' }
  ].filter((item) => item.count > 0)
})

const successPieSegments = computed(() => {
  return buildPieSegments(
    successPieItems.value,
    (item) => item.count,
    (item) => item.color
  )
})

const successPieStyle = computed(() => buildConicGradientStyle(successPieSegments.value))

const activeSuccessItem = computed(() => {
  if (activeSuccessIndex.value < 0) return null
  return successPieItems.value[activeSuccessIndex.value] || null
})

const successPieCenterLabel = computed(() => {
  if (activeSuccessItem.value) {
    return String(activeSuccessItem.value.count)
  }
  return formatRate(stats.value.success_rate)
})

const durationPieItems = computed<UploadTestDurationStats[]>(() => {
  return (stats.value.test_durations || []).filter((item) => item.avg_seconds > 0)
})

const durationPieSegments = computed(() => {
  return buildPieSegments(
    durationPieItems.value,
    (item) => item.avg_seconds,
    (_item, index) => durationPieColors[index % durationPieColors.length]
  )
})

const durationPieStyle = computed(() => buildConicGradientStyle(durationPieSegments.value))

const activeDurationItem = computed(() => {
  if (activeDurationIndex.value < 0) return null
  return durationPieItems.value[activeDurationIndex.value] || null
})

const overallAvgDurationLabel = computed(() => {
  const items = durationPieItems.value
  if (!items.length) return '-'
  const totalSeconds = items.reduce((sum, item) => sum + item.avg_seconds, 0)
  return formatDurationSeconds(totalSeconds / items.length)
})

const durationPieCenterLabel = computed(() => {
  if (activeDurationItem.value) {
    return formatDurationSeconds(activeDurationItem.value.avg_seconds)
  }
  return overallAvgDurationLabel.value
})

const handleSuccessPieHover = (event: MouseEvent) => {
  const index = resolvePieSegmentIndex(
    event,
    event.currentTarget as HTMLElement,
    successPieSegments.value
  )
  activeSuccessIndex.value = index
  updatePieTooltip(event, index, successPieTooltip.value)
}

const handleSuccessPieClick = (event: MouseEvent) => {
  const index = resolvePieSegmentIndex(
    event,
    event.currentTarget as HTMLElement,
    successPieSegments.value
  )
  activeSuccessIndex.value = index
  updatePieTooltip(event, index, successPieTooltip.value)
}

const clearSuccessPieHover = () => {
  activeSuccessIndex.value = -1
  successPieTooltip.value.visible = false
}

const handleDurationPieHover = (event: MouseEvent) => {
  const index = resolvePieSegmentIndex(
    event,
    event.currentTarget as HTMLElement,
    durationPieSegments.value
  )
  activeDurationIndex.value = index
  updatePieTooltip(event, index, durationPieTooltip.value)
}

const handleDurationPieClick = (event: MouseEvent) => {
  const index = resolvePieSegmentIndex(
    event,
    event.currentTarget as HTMLElement,
    durationPieSegments.value
  )
  activeDurationIndex.value = index
  updatePieTooltip(event, index, durationPieTooltip.value)
}

const clearDurationPieHover = () => {
  activeDurationIndex.value = -1
  durationPieTooltip.value.visible = false
}

const getFilterParams = () => {
  const [startDate, endDate] = filters.value.dateRange || []
  return {
    status: filters.value.status || undefined,
    model: filters.value.model || undefined,
    barcode: filters.value.barcode?.trim() || undefined,
    startDate,
    endDate
  }
}

const statusText = (status: string) => {
  const statusMap: Record<string, string> = {
    running: t('common.status.running'),
    success: t('uploadRecords.status.success'),
    failed: t('common.status.error')
  }
  return statusMap[status] || status || '-'
}

const statusTagType = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  return 'info'
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatDurationSeconds = (value?: number) => {
  const seconds = Math.max(0, Math.round(Number(value || 0)))
  if (!seconds) return '0s'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s`
}

const formatDuration = (start?: string | null, end?: string | null) => {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date()
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return '-'
  return formatDurationSeconds((endDate.getTime() - startDate.getTime()) / 1000)
}

const formatTestTypeLabel = (value: string) => {
  return formatTestType(value, '-')
}

const formatDurationTooltipName = (item: UploadTestDurationStats) => {
  return `${item.model} · ${formatTestTypeLabel(item.test_type)}`
}

const displayValue = (value: unknown) => {
  const text = String(value ?? '').trim()
  if (!text || text.toUpperCase() === 'N/A' || text.toUpperCase() === 'NA') {
    return '-'
  }
  return text
}

const getErrorMessage = (record: UploadRecordItem) => {
  return displayValue(record.error || record.result?.error || record.upload_result?.error)
}

const normalizeLink = (value: unknown) => {
  const text = String(value ?? '').trim()
  return displayValue(text) === '-' ? '' : text
}

const getCsvLink = (record: UploadRecordItem) => {
  return normalizeLink(record.result?.csv_link || record.upload_result?.csv_link)
}

const getUnitTrackerLink = (record: UploadRecordItem) => {
  return normalizeLink(record.result?.unit_tracker || record.upload_result?.unit_tracker)
}

const getRawDataLink = (record: UploadRecordItem) => {
  return normalizeLink(record.result?.raw_data || record.upload_result?.raw_data)
}

const getRawDataName = (record: UploadRecordItem) => {
  const name = record.result?.raw_data_name || record.upload_result?.raw_data_name || ''
  return String(name).trim()
}

const formatRate = (value?: number) => {
  return `${Number(value || 0).toFixed(1)}%`
}

const productLabel = (product?: UploadProductStats | null) => {
  return product?.model || '-'
}

const productMeta = (product?: UploadProductStats | null) => {
  if (!product) return t('common.empty')
  return `${formatRate(product.success_rate)} · ${product.success}/${product.finished}`
}

const fetchFilterOptions = async () => {
  try {
    const response = await uploadRecordApi.getUploadRecordFilterOptions()
    throwOnUploadResponseError(response)
    filterOptions.value = {
      models: response.data.models || [],
      statuses: response.data.statuses || []
    }
    return true
  } catch (e: any) {
    filterOptions.value = { models: [], statuses: [] }
    loadError.value = normalizeUploadError(e) || t('errors.unknown')
    return false
  }
}

const fetchStats = async () => {
  try {
    const response = await uploadRecordApi.getUploadRecordStats(getFilterParams())
    throwOnUploadResponseError(response)
    stats.value = response.data
    return true
  } catch (e: any) {
    loadError.value = normalizeUploadError(e) || t('errors.unknown')
    return false
  }
}

const clearAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = undefined
    refreshIntervalMs = 0
  }
}

const currentRefreshInterval = () => {
  return isAutoRefreshing.value ? AUTO_REFRESH_INTERVAL_MS : IDLE_REFRESH_INTERVAL_MS
}

const startAutoRefresh = (intervalMs = currentRefreshInterval()) => {
  if (refreshTimer && refreshIntervalMs === intervalMs) return
  clearAutoRefresh()
  refreshIntervalMs = intervalMs
  refreshTimer = setInterval(() => {
    fetchRecords(true)
  }, intervalMs)
}

const fetchRecords = async (silent = false) => {
  if (!silent) loading.value = true
  if (!silent) loadError.value = ''
  try {
    const response = await uploadRecordApi.getUploadRecords({
      page: currentPage.value,
      pageSize,
      ...getFilterParams()
    })
    throwOnUploadResponseError(response)
    records.value = response.data.records || []
    total.value = response.data.total || 0
    await mergeWatchedRecord()
    const statsLoaded = await fetchStats()
    if (statsLoaded) {
      loadError.value = ''
    }
  } catch (e: any) {
    loadError.value = normalizeUploadError(e) || t('errors.unknown')
  } finally {
    syncAutoRefresh()
    if (!silent) loading.value = false
  }
}

const mergeWatchedRecord = async () => {
  if (!watchedRecordId.value) return

  const existingIndex = records.value.findIndex((record) => record._id === watchedRecordId.value)
  const existingRecord = existingIndex >= 0 ? records.value[existingIndex] : null
  if (existingRecord && existingRecord.status !== 'running') {
    watchedRecordId.value = ''
    return
  }

  try {
    const response = await uploadRecordApi.getUploadRecords({
      page: 1,
      pageSize: 1,
      recordId: watchedRecordId.value
    })
    const watchedRecord = response.data.records?.[0]
    if (!watchedRecord) return

    if (existingIndex >= 0) {
      records.value.splice(existingIndex, 1, watchedRecord)
    } else {
      records.value = [watchedRecord, ...records.value].slice(0, pageSize)
    }

    if (watchedRecord.status !== 'running') {
      watchedRecordId.value = ''
    }
  } catch (e: any) {
    loadError.value = normalizeUploadError(e) || t('errors.unknown')
  }
}

const syncAutoRefresh = () => {
  startAutoRefresh()
}

const handleFilterChange = () => {
  currentPage.value = 1
  syncAutoRefresh()
  fetchRecords()
}

const resetFilters = () => {
  filters.value = {
    status: '',
    model: '',
    barcode: '',
    dateRange: []
  }
}

const handleResetFilters = () => {
  resetFilters()
  handleFilterChange()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchRecords()
}

const handleRefresh = () => {
  fetchRecords()
}

const retryLoad = async () => {
  loadError.value = ''
  loading.value = true
  if (await fetchFilterOptions()) {
    await fetchRecords()
  } else {
    loading.value = false
  }
}

const submitManualUpload = async () => {
  if (standardUploadMode.value === 'robot') {
    await submitStandardRobotUpload()
    return
  }

  if (!manualFile.value) {
    ElMessage.warning(t('uploadRecords.messages.selectCsv'))
    return
  }

  if (includeSourceZip.value && uploadAllFiles.value) {
    try {
      await ElMessageBox.confirm(
        t('uploadRecords.folderConfirmBody'),
        t('uploadRecords.folderConfirmTitle'),
        {
          confirmButtonText: t('uploadRecords.continueUpload'),
          cancelButtonText: t('common.actions.cancel'),
          type: 'warning'
        }
      )
    } catch {
      return
    }
  }

  manualUploading.value = true
  try {
    const response = await uploadRecordApi.uploadManualData(
      manualFile.value,
      includeSourceZip.value,
      uploadAllFiles.value
    )
    ElMessage.success(t('uploadRecords.messages.submitted'))
    manualUploadVisible.value = false
    await afterUploadSubmitted(response.data.record_id)
  } catch (e: any) {
    const message = normalizeUploadError(e)
    ElMessage.error(message ? t('uploadRecords.messages.manualFailedWithReason', { error: message }) : t('uploadRecords.messages.manualFailed'))
  } finally {
    manualUploading.value = false
  }
}

const submitStandardRobotUpload = async () => {
  if (!standardRobotIp.value || !standardSelectedRobotFile.value) {
    ElMessage.warning(t('uploadRecords.messages.selectRobotCsv'))
    return
  }

  manualUploading.value = true
  try {
    const response = await robotApi.downloadFile(standardRobotIp.value, standardSelectedRobotFile.value.path)
    const csvFile = blobToCsvFile(response.data, standardSelectedRobotFile.value.name)
    const uploadResponse = await uploadRecordApi.uploadManualData(csvFile, false, false)
    ElMessage.success(t('uploadRecords.messages.submitted'))
    manualUploadVisible.value = false
    await afterUploadSubmitted(uploadResponse.data.record_id)
  } catch (error: any) {
    const message = normalizeUploadError(error)
    ElMessage.error(message ? t('uploadRecords.messages.robotFailedWithReason', { error: message }) : t('uploadRecords.messages.robotFailed'))
  } finally {
    manualUploading.value = false
  }
}

const submitZStageLocalUpload = async () => {
  if (!zStageRobotSn.value.trim()) {
    ElMessage.warning(t('uploadRecords.messages.fillRobotSn'))
    return
  }
  if (!zStageLocalFile.value) {
    ElMessage.warning(t('uploadRecords.messages.selectCsv'))
    return
  }

  zStageUploading.value = true
  try {
    const response = await uploadZStageFile(zStageLocalFile.value)
    ElMessage.success(t('uploadRecords.messages.zStageSubmitted'))
    manualUploadVisible.value = false
    await afterUploadSubmitted(response.data.record_id)
  } catch (error: any) {
    const message = normalizeUploadError(error)
    ElMessage.error(message ? t('uploadRecords.messages.zStageFailedWithReason', { error: message }) : t('uploadRecords.messages.zStageFailed'))
  } finally {
    zStageUploading.value = false
  }
}

const submitZStageRemoteUpload = async () => {
  if (!canSubmitZStageRemote.value) {
    ElMessage.warning(t('uploadRecords.messages.selectCsvToUpload'))
    return
  }

  zStageUploading.value = true
  let successCount = 0
  let failedCount = 0
  let lastRecordId = ''

  for (const file of selectedZStageRemoteFiles.value) {
    file.status = 'uploading'
    file.error = ''
    try {
      const response = await robotApi.downloadFile(zStageFixtureIp.value.trim(), file.path)
      const csvFile = blobToCsvFile(response.data, file.name)
      const uploadResponse = await uploadZStageFile(csvFile)
      file.status = 'success'
      successCount += 1
      lastRecordId = uploadResponse.data.record_id || lastRecordId
    } catch (error: any) {
      file.status = 'failed'
      file.error = normalizeUploadError(error)
      failedCount += 1
    }
  }

  zStageUploading.value = false
  if (successCount > 0) {
    ElMessage.success(failedCount
      ? t('uploadRecords.messages.zStageBatchPartial', { success: successCount, failed: failedCount })
      : t('uploadRecords.messages.zStageBatchSuccess', { count: successCount }))
    await afterUploadSubmitted(lastRecordId)
  } else {
    ElMessage.error(t('uploadRecords.messages.zStageFailed'))
  }
}

onMounted(() => {
  retryLoad()
})

onUnmounted(() => {
  clearAutoRefresh()
})
</script>

<style scoped>
.upload-records-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.records-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0;
  border-radius: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.title-group,
.header-tools,
.status-cell,
.link-actions,
.step-status,
.filter-bar {
  display: flex;
  align-items: center;
}

.title-group {
  gap: 12px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.running-hint,
.auto-refresh {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #e6a23c;
}

.header-tools {
  gap: 12px;
}

.load-error-alert {
  margin-bottom: 14px;
}

.scan-error-alert {
  margin: 2px 0;
}

.load-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.records-loading-state {
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #606266;
  font-size: 14px;
}

.records-loading-icon {
  color: #409eff;
  font-size: 22px;
}

.manual-upload {
  width: 100%;
}

.manual-upload-tabs {
  min-height: 360px;
}

.z-stage-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.z-stage-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field-line {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}

.z-stage-mode {
  align-self: flex-start;
}

.standard-upload-mode {
  align-self: flex-start;
}

.standard-robot-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.standard-robot-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 10px;
}

.standard-robot-select {
  width: 100%;
}

.standard-robot-path-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 30px;
  border-bottom: 1px solid #ebeef5;
}

.standard-robot-path {
  min-width: 0;
  overflow: hidden;
  color: #606266;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.standard-robot-file-list {
  max-height: 260px;
  overflow: auto;
  border-top: 1px solid #ebeef5;
}

.standard-robot-file-row {
  display: grid;
  grid-template-columns: 24px minmax(160px, 0.85fr) minmax(220px, 1.15fr) 76px;
  align-items: start;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 8px 0;
  border: 0;
  border-bottom: 1px solid #f2f3f5;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.standard-robot-file-row:hover {
  background: #f5f9ff;
}

.standard-robot-file-row.is-selected {
  background: #ecf5ff;
}

.standard-robot-file-name,
.standard-robot-file-path {
  min-width: 0;
  overflow: visible;
  white-space: normal;
  word-break: break-all;
}

.standard-robot-file-name {
  color: #303133;
  font-weight: 500;
}

.standard-robot-file-path {
  color: #909399;
  font-size: 12px;
}

.standard-robot-file-size {
  color: #909399;
  font-size: 12px;
  text-align: right;
  white-space: nowrap;
}

.z-stage-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.remote-search-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.remote-file-panel {
  border-top: 1px solid #ebeef5;
}

.remote-file-head {
  padding: 10px 0;
}

.remote-file-list {
  max-height: 220px;
  overflow: auto;
  border-top: 1px solid #ebeef5;
}

.remote-file-row {
  display: grid;
  grid-template-columns: 24px minmax(120px, 0.7fr) minmax(180px, 1.3fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 6px 0;
  border-bottom: 1px solid #f2f3f5;
}

.remote-file-name,
.remote-file-path {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remote-file-name {
  color: #303133;
  font-weight: 500;
}

.remote-file-path {
  color: #909399;
  font-size: 12px;
}

.upload-icon {
  margin-top: 8px;
  font-size: 28px;
  color: #909399;
}

.upload-text {
  margin: 8px 0 12px;
  color: #606266;
}

.source-warning {
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.45;
}

.filter-bar {
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.filter-control {
  width: 150px;
}

.date-filter {
  width: 260px;
}

.barcode-filter {
  width: 190px;
}

.stats-panel {
  display: grid;
  grid-template-columns:
    minmax(150px, 1fr)
    minmax(170px, 1fr)
    minmax(170px, 1fr)
    minmax(110px, 0.75fr)
    minmax(110px, 0.75fr);
  gap: 12px;
  margin-bottom: 12px;
}

.stat-item,
.pie-stat {
  min-height: 92px;
  padding: 12px 14px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  box-sizing: border-box;
}

.stat-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 22px;
  line-height: 1.15;
  color: #303133;
}

.stat-meta {
  font-size: 12px;
  color: #606266;
}

.pie-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.pie-title {
  font-size: 13px;
  color: #909399;
  line-height: 1.2;
}

.pie-wrap {
  position: relative;
  flex: 0 0 72px;
  width: 72px;
  height: 72px;
  cursor: pointer;
}

.interactive-pie {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  position: relative;
}

.interactive-pie::after {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 50%;
  background: #fff;
}

.interactive-pie span {
  position: relative;
  z-index: 1;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.pie-tooltip {
  position: absolute;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 220px;
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(48, 49, 51, 0.92);
  color: #fff;
  font-size: 12px;
  line-height: 1.3;
  pointer-events: none;
  transform: translateY(-100%);
  white-space: nowrap;
}

.pie-tooltip-name {
  color: #e5eaf3;
}

.pie-tooltip strong {
  font-size: 13px;
  font-weight: 600;
}

.table-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 24px;
  margin-bottom: 12px;
}

.total-count {
  font-size: 14px;
  color: #909399;
}

.status-cell,
.status-main,
.step-status {
  gap: 6px;
}

.status-cell {
  flex-direction: column;
  align-items: flex-start;
}

.status-main {
  display: flex;
  align-items: center;
}

.progress-message {
  max-width: 190px;
  color: #909399;
  font-size: 12px;
  line-height: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.running-icon {
  color: #e6a23c;
}

.file-cell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.file-name {
  color: #303133;
}

.zip-name {
  color: #909399;
  font-size: 12px;
}

.link-actions {
  gap: 10px;
}

.link-cell {
  color: #409eff;
  text-decoration: none;
}

.link-cell:hover {
  text-decoration: underline;
}

.error-text {
  color: #f56c6c;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

@media (max-width: 1280px) {
  .stats-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
