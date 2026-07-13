<template>
  <div class="analysis-view">
    <div class="analysis-mode-bar">
      <el-button-group class="mode-switch">
        <el-button :type="analysisMode === 'local' ? 'primary' : 'default'" @click="analysisMode = 'local'">
          本地分析
        </el-button>
        <el-button :type="analysisMode === 'online' ? 'primary' : 'default'" @click="analysisMode = 'online'">
          在线分析
        </el-button>
      </el-button-group>
      <el-tooltip content="Spec 设置" placement="bottom">
        <el-button class="spec-settings-button" :icon="Setting" circle @click="openSpecDialog" />
      </el-tooltip>
    </div>

    <section v-if="analysisMode === 'local' || activeAnalysis" class="local-analysis">
      <div v-if="!activeAnalysis && !loading" class="upload-stage">
        <div class="local-upload-panel">
          <el-upload
            ref="uploadRef"
            class="analysis-upload-large"
            drag
            multiple
            accept=".csv,text/csv"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleFileChange"
          >
            <div class="upload-empty-content">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-title">上传 CSV 文件</div>
              <div class="upload-subtitle">拖拽文件到此处，或点击选择</div>
            </div>
          </el-upload>

          <div class="local-actions">
            <div v-if="selectedFiles.length > 0" class="file-queue">
              <el-tag
                v-for="file in selectedFiles"
                :key="`${file.name}-${file.size}-${file.lastModified}`"
                closable
                @close="removeFile(file.name)"
              >
                {{ file.name }}
              </el-tag>
            </div>

            <div class="action-row">
              <div class="action-buttons">
                <el-button
                  type="primary"
                  :icon="Histogram"
                  :loading="loading"
                  :disabled="selectedFiles.length === 0"
                  @click="analyzeSelectedFiles"
                >
                  分析
                </el-button>
                <el-button :icon="Delete" :disabled="selectedFiles.length === 0 || loading" @click="clearFiles">
                  清空
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loadMessage" class="hint-line">
        {{ loadMessage }}
      </div>

      <template v-if="activeAnalysis">
        <div class="result-toolbar">
          <div class="result-title">
            <el-tooltip content="返回上传" placement="bottom">
              <el-button class="back-button" :icon="ArrowLeft" circle @click="clearFiles" />
            </el-tooltip>
            <strong>{{ activeAnalysis.file?.name || 'CSV 分析结果' }}</strong>
          </div>

          <el-select
            v-if="analyses.length > 1"
            v-model="selectedAnalysisIndex"
            class="result-select"
            :disabled="analyses.length <= 1"
          >
            <el-option
              v-for="(item, index) in analyses"
              :key="item.file?.path || item.file?.name || index"
              :label="item.file?.name || `分析 ${index + 1}`"
              :value="index"
            />
          </el-select>
        </div>

        <div class="analysis-result-card" :class="activeAnalysis.passed ? 'is-pass' : 'is-fail'">
          <div class="result-status">
            <el-icon class="result-status-icon">
              <CircleCheck v-if="activeAnalysis.passed" />
              <CircleClose v-else />
            </el-icon>
            <strong>{{ activeAnalysis.passed ? 'PASS' : 'FAIL' }}</strong>
          </div>
          <ol v-if="!activeAnalysis.passed && activeFailures.length > 0" class="failure-list">
            <li v-for="failure in activeFailures" :key="failure">
              {{ failure }}
            </li>
          </ol>
        </div>

        <div class="summary-table-section">
          <el-table :data="summaryTableRows" size="small" border>
            <el-table-column prop="label" label="" min-width="150" fixed />
            <el-table-column
              v-for="column in summaryVolumeColumns"
              :key="column.key"
              :prop="column.key"
              :label="column.label"
              min-width="150"
            />
          </el-table>
        </div>

        <div class="chart-grid">
          <section class="chart-panel">
            <div class="panel-header">
              <div class="panel-title-tools">
                <h2>
                  {{ hasChannelTrialMatrices ? '容量/Channels' : '容量 / Trial %D' }}
                </h2>
              </div>
              <div v-if="hasChannelTrialMatrices" class="trial-controls">
                <el-button-group class="chart-mode-group">
                  <el-button
                    class="chart-mode-button"
                    :type="trialChartMode === 'd' ? 'primary' : 'default'"
                    size="small"
                    @click="setTrialChartMode('d')"
                  >
                    %D
                  </el-button>
                  <el-button
                    class="chart-mode-button"
                    :type="trialChartMode === 'cv' ? 'primary' : 'default'"
                    size="small"
                    @click="setTrialChartMode('cv')"
                  >
                    %CV
                  </el-button>
                </el-button-group>
                <el-radio-group v-model="selectedTrialAction" size="small">
                  <el-radio-button label="aspirate">Aspirate</el-radio-button>
                  <el-radio-button label="dispense">Dispense</el-radio-button>
                </el-radio-group>
                <el-radio-group v-model="selectedVolume" size="small">
                  <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                    {{ formatVolume(volume) }}
                  </el-radio-button>
                </el-radio-group>
                <el-checkbox-group
                  v-if="trialChartMode === 'd'"
                  v-model="selectedTrialChannels"
                  class="channel-checkboxes"
                  size="small"
                >
                  <el-checkbox-button
                    v-for="channel in availableTrialChannels"
                    :key="channel"
                    :label="channel"
                  >
                    CH{{ channel }}
                  </el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div v-else class="trial-controls">
                <el-checkbox-group v-model="trialSeriesSelection" size="small">
                  <el-checkbox-button label="aspirate_d">Aspirate %D</el-checkbox-button>
                  <el-checkbox-button label="dispense_d">Dispense %D</el-checkbox-button>
                </el-checkbox-group>
                <el-radio-group v-model="selectedVolume" size="small">
                  <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                    {{ formatVolume(volume) }}
                  </el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div ref="trialChartRef" class="chart"></div>
          </section>

          <section class="chart-panel">
            <div class="panel-header">
              <h2>Water Remain / Trial</h2>
              <div class="trial-controls">
                <el-radio-group v-model="selectedWaterRemainVolume" size="small">
                  <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                    {{ formatVolume(volume) }}
                  </el-radio-button>
                </el-radio-group>
                <el-select v-model="selectedWaterRemainChannel" class="channel-select" size="small">
                  <el-option
                    v-for="channel in waterRemainChannelOptions"
                    :key="channel.value"
                    :label="channel.label"
                    :value="channel.value"
                  />
                </el-select>
              </div>
            </div>
            <div ref="waterRemainChartRef" class="chart"></div>
          </section>

          <section class="chart-panel">
            <div class="panel-header">
              <h2>温度变化</h2>
              <div class="trial-controls">
                <el-checkbox-group v-model="temperatureSeriesSelection" size="small">
                  <el-checkbox-button label="pipette">Pipette</el-checkbox-button>
                  <el-checkbox-button label="air">Air</el-checkbox-button>
                </el-checkbox-group>
                <el-radio-group v-model="selectedTemperatureVolume" size="small">
                  <el-radio-button label="all">全部容量</el-radio-button>
                  <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                    {{ formatVolume(volume) }}
                  </el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div ref="temperatureChartRef" class="chart"></div>
          </section>

          <section class="chart-panel">
            <div class="panel-header">
              <h2>湿度变化</h2>
              <div class="trial-controls">
                <el-checkbox-group v-model="humiditySeriesSelection" size="small">
                  <el-checkbox-button label="pipette">Pipette</el-checkbox-button>
                  <el-checkbox-button label="air">Air</el-checkbox-button>
                </el-checkbox-group>
                <el-radio-group v-model="selectedHumidityVolume" size="small">
                  <el-radio-button label="all">全部容量</el-radio-button>
                  <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                    {{ formatVolume(volume) }}
                  </el-radio-button>
                </el-radio-group>
              </div>
            </div>
            <div ref="humidityChartRef" class="chart"></div>
          </section>
        </div>

        <div v-if="hasChannelTrialMatrices" class="table-section matrix-section">
          <div class="panel-header">
            <div class="panel-title-tools">
              <h2>通道 Trial 矩阵</h2>
              <span class="matrix-context">
                {{ selectedTrialAction === 'aspirate' ? 'Aspirate' : 'Dispense' }}
              </span>
            </div>
            <div class="matrix-header-tools">
              <el-radio-group v-model="selectedVolume" size="small">
                <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                  {{ formatVolume(volume) }}
                </el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="selectedTrialAction" size="small">
                <el-radio-button label="aspirate">Aspirate</el-radio-button>
                <el-radio-button label="dispense">Dispense</el-radio-button>
              </el-radio-group>
              <div class="matrix-spec-strip">
                <span v-for="item in matrixStatisticItems" :key="item.label">
                  {{ item.label }} {{ item.value }}
                </span>
              </div>
            </div>
          </div>
          <el-table
            :data="channelTrialMatrixTableRows"
            size="small"
            border
            class="matrix-table"
            :cell-style="matrixCellStyle"
          >
            <el-table-column prop="row_label" label="" min-width="120" fixed />
            <el-table-column
              v-for="trial in selectedChannelTrialMatrix?.trials || []"
              :key="trial"
              :prop="`trial_${trial}`"
              :label="`Trial ${trial}`"
              min-width="86"
            >
              <template #default="{ row }">
                <span
                  class="matrix-cell-value"
                  :class="{ 'is-fail': row._fail_cells?.[`trial_${trial}`] }"
                >
                  {{ row[`trial_${trial}`] }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="avg" label="AVG" min-width="86" />
            <el-table-column prop="cv" label="CV%" min-width="86">
              <template #default="{ row }">
                <span
                  class="matrix-cell-value"
                  :class="{ 'is-fail': row._fail_cells?.cv }"
                >
                  {{ row.cv }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="d" label="%D" min-width="86">
              <template #default="{ row }">
                <span
                  class="matrix-cell-value"
                  :class="{ 'is-fail': row._fail_cells?.d }"
                >
                  {{ row.d }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="avg_water_remaining" label="Avg Water Remaining" min-width="150" />
          </el-table>
        </div>

        <div v-if="hasSingleChannelTrialMatrices" class="table-section matrix-section">
          <div class="panel-header">
            <div class="panel-title-tools">
              <h2>单通道 Trial 矩阵</h2>
              <span class="matrix-context">
                {{ selectedSingleChannelTrialMatrix?.label || formatVolume(selectedVolume) }}
              </span>
            </div>
            <div class="matrix-header-tools">
              <el-radio-group v-model="selectedVolume" size="small">
                <el-radio-button v-for="volume in activeVolumes" :key="volume" :label="volume">
                  {{ formatVolume(volume) }}
                </el-radio-button>
              </el-radio-group>
              <div class="matrix-spec-strip">
                <span v-for="item in matrixStatisticItems" :key="item.label">
                  {{ item.label }} {{ item.value }}
                </span>
              </div>
            </div>
          </div>
          <el-table
            :data="singleChannelTrialMatrixTableRows"
            size="small"
            border
            class="matrix-table single-channel-matrix-table"
            :row-class-name="singleChannelMatrixRowClassName"
          >
            <el-table-column prop="trial" label="Trial" min-width="86" fixed />
            <el-table-column prop="water_remaining" label="Water Remaining" min-width="140" />
            <el-table-column prop="aspirate_time_s" label="Time from Start (s)" min-width="150" />
            <el-table-column prop="aspirate" label="Aspirate" min-width="110" />
            <el-table-column prop="aspirate_d" label="Aspirate %D" min-width="120" />
            <el-table-column prop="dispense_time_s" label="Time from Start (s)" min-width="150" />
            <el-table-column prop="dispense" label="Dispense" min-width="110" />
            <el-table-column prop="dispense_d" label="Dispense %D" min-width="120" />
            <el-table-column prop="aspirate_travel" label="Aspirate Travel (mm)" min-width="160" />
          </el-table>
        </div>

        <div class="table-section">
          <div class="panel-header">
            <div class="panel-title-tools">
              <h2>Trial 明细</h2>
              <el-select v-model="trialTableVolumeFilter" class="trial-filter-select" size="small">
                <el-option label="全部容量" value="all" />
                <el-option
                  v-for="volume in activeVolumes"
                  :key="volume"
                  :label="formatVolume(volume)"
                  :value="volume"
                />
              </el-select>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="filteredTrialRows.length === 0"
              @click="openTrialDetail"
            >
              详情
            </el-button>
          </div>
          <el-table
            :data="filteredTrialRows"
            size="small"
            stripe
            border
            max-height="420"
          >
            <el-table-column prop="volume" label="容量" width="90">
              <template #default="{ row }">{{ formatVolume(row.volume) }}</template>
            </el-table-column>
            <el-table-column prop="trial" label="Trial" width="80" />
            <el-table-column prop="aspirate" label="Aspirate" min-width="110" />
            <el-table-column prop="dispense" label="Dispense" min-width="110" />
            <el-table-column prop="aspirate_d" label="Aspirate %D" min-width="120" />
            <el-table-column prop="dispense_d" label="Dispense %D" min-width="130" />
            <el-table-column prop="water_remain" label="Water Remain" min-width="130" />
            <el-table-column prop="celsius_pipette" label="移液器温度" min-width="120">
              <template #default="{ row }">{{ formatMetricValue(row.celsius_pipette) }}</template>
            </el-table-column>
            <el-table-column prop="humidity_pipette" label="移液器湿度" min-width="120">
              <template #default="{ row }">{{ formatMetricValue(row.humidity_pipette) }}</template>
            </el-table-column>
            <el-table-column prop="celsius_air" label="环境温度" min-width="110">
              <template #default="{ row }">{{ formatMetricValue(row.celsius_air) }}</template>
            </el-table-column>
            <el-table-column prop="humidity_air" label="环境湿度" min-width="110">
              <template #default="{ row }">{{ formatMetricValue(row.humidity_air) }}</template>
            </el-table-column>
            <el-table-column prop="liquid_height" label="Liquid Height" min-width="120" />
          </el-table>
        </div>
      </template>

      <div v-else-if="loading" class="loading-panel">
        <el-skeleton :rows="5" animated />
      </div>

      <el-alert
        v-if="analysisErrors.length > 0"
        class="error-list"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>
          {{ analysisErrors.map(item => `${item.file?.name || 'CSV'}: ${item.message}`).join('；') }}
        </template>
      </el-alert>
    </section>

    <section v-else class="online-analysis">
      <div class="online-panel">
        <div class="online-controls">
          <el-select
            v-model="onlineFilters.product"
            class="online-select online-product-select"
            placeholder="产品"
            filterable
            :loading="onlineProductsLoading"
            @change="handleOnlineProductChange"
          >
            <el-option
              v-for="product in onlineProductNameOptions"
              :key="product"
              :label="product"
              :value="product"
            />
          </el-select>
          <el-select
            v-model="onlineFilters.test"
            class="online-select online-test-select"
            placeholder="测试"
            filterable
            :disabled="onlineTestOptions.length === 0"
            @change="handleOnlineTestChange"
          >
            <el-option
              v-for="testType in onlineTestOptions"
              :key="testType"
              :label="formatTestType(testType)"
              :value="testType"
            />
          </el-select>
          <el-select
            v-model="onlineFilters.sn"
            class="online-select online-sn-select"
            placeholder="SN"
            filterable
            :disabled="onlineSnOptions.length === 0"
            @change="handleOnlineSnChange"
          >
            <el-option
              v-for="product in onlineSnOptions"
              :key="product.barcode"
              :label="product.barcode"
              :value="product.barcode"
            >
              <div class="online-product-option">
                <span>{{ product.barcode }}</span>
                <span>{{ formatOnlineProductUpdatedAt(product, 'short') }}</span>
              </div>
            </el-option>
          </el-select>
          <el-popover placement="bottom" trigger="click" width="420">
            <div class="csv-link-editor">
              <el-input
                v-model="onlineManualCsvLink"
                clearable
                placeholder="手动输入 Google Sheet CSV link"
              />
              <div class="csv-link-hint">为空时使用当前条码/SN 的默认 CSV link</div>
            </div>
            <template #reference>
              <el-button class="csv-link-button" :icon="EditPen" :disabled="!canEditOnlineCsvLink" />
            </template>
          </el-popover>
          <el-button
            type="primary"
            :icon="Search"
            :loading="loading"
            :disabled="!onlineFilters.product || !onlineFilters.test || !effectiveOnlineCsvLink"
            @click="analyzeOnlineSelection"
          >
            分析
          </el-button>
        </div>
        <div v-if="loadMessage" class="hint-line">
          {{ loadMessage }}
        </div>
        <el-alert
          v-if="onlineFilters.product && onlineFilters.test && !effectiveOnlineCsvLink"
          type="warning"
          :closable="false"
          show-icon
          title="当前产品和测试没有匹配的 SN CSV link，可点击编辑图标手动输入"
        />
        <el-empty v-if="!activeAnalysis && !loading" description="选择产品、测试后开始在线分析；缺少默认链接时可手动输入" />
      </div>
    </section>

    <el-drawer v-model="detailDrawerVisible" title="筛选详情" size="560px">
      <template v-if="filteredTrialRows.length > 0">
        <div class="detail-meta">
          <span>{{ detailVolumeLabel }}</span>
          <span>{{ filteredTrialRows.length }} rows</span>
        </div>

        <el-table :data="detailStatisticRows" size="small" border class="detail-stat-table">
          <el-table-column prop="metric" label="指标" min-width="150" />
          <el-table-column prop="min" label="最小" min-width="100" />
          <el-table-column prop="max" label="最大" min-width="100" />
          <el-table-column prop="avg" label="平均 / 值" min-width="110" />
        </el-table>

        <div class="raw-toolbar">
          <el-popover placement="top" trigger="hover" width="520">
            <pre class="raw-json">{{ detailRawJson }}</pre>
            <template #reference>
              <span class="raw-link">Raw</span>
            </template>
          </el-popover>
          <el-tooltip content="复制 Raw JSON" placement="top">
            <el-button link :icon="CopyDocument" @click="copyDetailRaw" />
          </el-tooltip>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="specDialogVisible" title="Spec 设置" width="760px" class="spec-dialog">
      <div class="spec-dialog-toolbar">
        <el-select
          v-model="specForm.product"
          class="spec-select"
          placeholder="产品"
          :loading="specLoading"
          @change="handleSpecProductChange"
        >
          <el-option
            v-for="product in specProducts"
            :key="product.product"
            :label="product.product_name"
            :value="product.product"
          />
        </el-select>
        <el-select v-model="specForm.test_type" class="spec-select" placeholder="测试" disabled>
          <el-option label="Gravimetric" value="gravimetric" />
        </el-select>
        <el-tag v-if="specStorageLabel" type="info">{{ specStorageLabel }}</el-tag>
      </div>

      <el-table :data="specForm.volumes" size="small" border class="spec-table">
        <el-table-column label="容量 (uL)" min-width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.volume" :min="0" :precision="3" :step="1" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="CV Spec" min-width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.cv" :min="0" :precision="4" :step="0.01" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="%D Spec" min-width="140">
          <template #default="{ row }">
            <el-input-number v-model="row.d" :min="0" :precision="4" :step="0.01" controls-position="right" />
          </template>
        </el-table-column>
        <el-table-column label="" width="72">
          <template #default="{ $index }">
            <el-button link type="danger" :icon="Delete" @click="removeSpecVolume($index)" />
          </template>
        </el-table-column>
      </el-table>

      <div class="spec-actions">
        <el-button @click="addSpecVolume">新增容量</el-button>
      </div>

      <template #footer>
        <el-button @click="specDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="specSaving" @click="saveSpecSettings">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { init, use, type ComposeOption, type EChartsCoreOption, type EChartsType } from 'echarts/core'
import { BarChart, LineChart, type BarSeriesOption, type LineSeriesOption } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  type DataZoomComponentOption,
  type GridComponentOption,
  type LegendComponentOption,
  type TitleComponentOption,
  type TooltipComponentOption
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { UploadFile, UploadInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import { ArrowLeft, CircleCheck, CircleClose, CopyDocument, Delete, EditPen, Histogram, Search, Setting, UploadFilled } from '@element-plus/icons-vue'
import { dataAnalysisApi, productManagementApi } from '@/api'
import { canonicalTestType, formatTestType, sameTestType, uniqueTestTypes } from '@/utils/testNames'
import type {
  DataAnalysisItem,
  DataAnalysisResponse,
  DataAnalysisSpecCatalogItem,
  DataAnalysisSpecItem,
  DataAnalysisSpecVolume,
  ProductManagementItem,
  ProductManagementTest
} from '@/types'

type AnalysisMode = 'local' | 'online'
type TrialSeriesKey = 'aspirate_d' | 'dispense_d'
type TrialActionKey = 'aspirate' | 'dispense'
type TrialChartMode = 'd' | 'cv'
type EnvironmentSeriesKey = 'pipette' | 'air'
type SummaryTableRow = {
  label: string
  [key: string]: string | number
}
type ChannelTrialMatrixTableRow = {
  row_label: string
  avg?: string | number
  cv?: string | number
  d?: string | number
  avg_water_remaining?: string | number
  _row_type?: 'channel' | 'summary'
  _raw_values?: Record<string, number | null>
  _fail_cells?: Record<string, boolean>
  [key: string]: any
}
type SingleChannelTrialMatrixTableRow = {
  row_type: 'trial' | 'summary'
  trial: number | string
  water_remaining: string
  aspirate_time_s: string
  aspirate: string
  aspirate_d: string
  dispense_time_s: string
  dispense: string
  dispense_d: string
  aspirate_travel: string
}
type TrialTableRow = DataAnalysisItem['trial_series'][number] & {
  celsius_pipette?: number | null
  humidity_pipette?: number | null
  celsius_air?: number | null
  humidity_air?: number | null
  environment_raw?: Record<string, any> | null
}
type DetailStatisticRow = {
  metric: string
  min: string
  max: string
  avg: string
}

type ChartOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | DataZoomComponentOption
  | GridComponentOption
  | LegendComponentOption
  | TitleComponentOption
  | TooltipComponentOption
>

use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  TitleComponent,
  DataZoomComponent,
  CanvasRenderer
])

const route = useRoute()
const router = useRouter()
const analysisMode = ref<AnalysisMode>('local')
const loading = ref(false)
const selectedFiles = ref<File[]>([])
const analyses = ref<DataAnalysisItem[]>([])
const analysisErrors = ref<DataAnalysisResponse['errors']>([])
const selectedAnalysisIndex = ref(0)
const selectedVolume = ref<number | null>(null)
const selectedWaterRemainVolume = ref<number | null>(null)
const selectedWaterRemainChannel = ref('avg')
const selectedTemperatureVolume = ref<'all' | number>('all')
const selectedHumidityVolume = ref<'all' | number>('all')
const trialTableVolumeFilter = ref<'all' | number>('all')
const trialSeriesSelection = ref<TrialSeriesKey[]>(['aspirate_d', 'dispense_d'])
const selectedTrialAction = ref<TrialActionKey>('dispense')
const trialChartMode = ref<TrialChartMode>('d')
const selectedTrialChannels = ref<string[]>([])
const temperatureSeriesSelection = ref<EnvironmentSeriesKey[]>(['pipette', 'air'])
const humiditySeriesSelection = ref<EnvironmentSeriesKey[]>(['pipette', 'air'])
const detailDrawerVisible = ref(false)
const specDialogVisible = ref(false)
const specLoading = ref(false)
const specSaving = ref(false)
const specStorage = ref('')
const specProducts = ref<DataAnalysisSpecCatalogItem[]>([])
const specItems = ref<DataAnalysisSpecItem[]>([])
const specForm = ref<DataAnalysisSpecItem>({
  product: '',
  product_name: '',
  analysis_product: '',
  test_type: 'gravimetric',
  test_name: 'Gravimetric',
  volumes: []
})
const loadMessage = ref('')
const uploadRef = ref<UploadInstance>()
const onlineFilters = ref({ product: '', test: '', sn: '' })
const onlineManualCsvLink = ref('')
const onlineProductsLoading = ref(false)
const onlineProductOptions = ref<ProductManagementItem[]>([])

const trialChartRef = ref<HTMLDivElement | null>(null)
const temperatureChartRef = ref<HTMLDivElement | null>(null)
const humidityChartRef = ref<HTMLDivElement | null>(null)
const waterRemainChartRef = ref<HTMLDivElement | null>(null)

let trialChart: EChartsType | null = null
let temperatureChart: EChartsType | null = null
let humidityChart: EChartsType | null = null
let waterRemainChart: EChartsType | null = null

const activeAnalysis = computed(() => analyses.value[selectedAnalysisIndex.value] || null)
const activeFailures = computed(() => activeAnalysis.value?.summary?.failures || [])
const activeVolumes = computed(() => {
  return Array.isArray(activeAnalysis.value?.volumes) ? activeAnalysis.value.volumes : []
})
const hasChannelTrialMatrices = computed(() => {
  return Boolean(activeAnalysis.value?.channel_trial_matrices?.length)
})
const hasSingleChannelTrialMatrices = computed(() => {
  return Boolean(activeAnalysis.value?.single_channel_trial_matrices?.length)
})
const selectedChannelTrialMatrix = computed(() => {
  if (!activeAnalysis.value || selectedVolume.value === null) return null
  return (activeAnalysis.value.channel_trial_matrices || []).find(item => {
    return Number(item.volume) === Number(selectedVolume.value) &&
      String(item.action) === selectedTrialAction.value
  }) || null
})
const selectedSingleChannelTrialMatrix = computed(() => {
  if (!activeAnalysis.value || selectedVolume.value === null) return null
  return (activeAnalysis.value.single_channel_trial_matrices || []).find(item => {
    return Number(item.volume) === Number(selectedVolume.value)
  }) || null
})
const availableTrialChannels = computed(() => {
  const matrix = selectedChannelTrialMatrix.value
  if (!matrix) return []
  return [...matrix.channels].sort((left, right) => {
    return String(left).localeCompare(String(right), 'zh-CN', { numeric: true })
  })
})
const waterRemainChannelOptions = computed(() => {
  const rows = getWaterRemainBaseRows()
  const channels = Array.from(new Set(
    rows
      .map(row => String(row.channel || ''))
      .filter(channel => channel !== '')
  )).sort((left, right) => {
    return left.localeCompare(right, 'zh-CN', { numeric: true })
  })
  return [
    { value: 'avg', label: 'channel-avg' },
    ...channels.map(channel => ({
      value: channel,
      label: `channel ${channel}`
    }))
  ]
})
const channelTrialMatrixTableRows = computed<ChannelTrialMatrixTableRow[]>(() => {
  const matrix = selectedChannelTrialMatrix.value
  if (!matrix) return []
  const rows: ChannelTrialMatrixTableRow[] = []

  matrix.rows.forEach(row => {
    const tableRow: ChannelTrialMatrixTableRow = {
      row_label: row.label || `CH${row.channel}`,
      _row_type: 'channel',
      _raw_values: {},
      _fail_cells: {},
      avg: formatMetricValue(row.average),
      cv: formatMetricValue(row.cv),
      d: formatMetricValue(row.d),
      avg_water_remaining: formatMetricValue(row.avg_water_remaining)
    }
    tableRow._fail_cells!.cv = isMatrixCvOutOfSpec(cleanMetricNumber(row.cv))
    tableRow._fail_cells!.d = isMatrixDOutOfSpec(cleanMetricNumber(row.d))
    row.trial_values.forEach(point => {
      const property = `trial_${point.trial}`
      const value = cleanMetricNumber(point.value)
      tableRow[property] = formatMetricValue(point.value)
      tableRow._raw_values![property] = value
      tableRow._fail_cells![property] = isMatrixTrialValueOutOfSpec(value)
    })
    rows.push(tableRow)
  })

  const summary = matrix.trial_summary || []
  rows.push(buildMatrixTrialSummaryRow('Trial AVG', summary, 'average'))
  rows.push(buildMatrixTrialSummaryRow('Trial CV%', summary, 'cv'))
  rows.push(buildMatrixTrialSummaryRow('Trial %D', summary, 'd'))
  return rows
})
const singleChannelTrialMatrixTableRows = computed<SingleChannelTrialMatrixTableRow[]>(() => {
  const matrix = selectedSingleChannelTrialMatrix.value
  if (!matrix) return []
  const rows: SingleChannelTrialMatrixTableRow[] = (matrix.rows || []).map(row => ({
    row_type: 'trial',
    trial: row.trial,
    water_remaining: formatMetricValue(row.water_remaining),
    aspirate_time_s: formatTimeValue(row.aspirate_time_s),
    aspirate: formatMetricValue(row.aspirate),
    aspirate_d: formatMetricValue(row.aspirate_d),
    dispense_time_s: formatTimeValue(row.dispense_time_s),
    dispense: formatMetricValue(row.dispense),
    dispense_d: formatMetricValue(row.dispense_d),
    aspirate_travel: formatMetricValue(row.aspirate_travel)
  }))
  const average = matrix.summary?.average || {}
  const cv = matrix.summary?.cv || {}
  rows.push({
    row_type: 'summary',
    trial: 'Average',
    water_remaining: formatMetricValue(average.water_remaining),
    aspirate_time_s: '',
    aspirate: formatMetricValue(average.aspirate),
    aspirate_d: formatMetricValue(average.aspirate_d),
    dispense_time_s: '',
    dispense: formatMetricValue(average.dispense),
    dispense_d: formatMetricValue(average.dispense_d),
    aspirate_travel: ''
  })
  rows.push({
    row_type: 'summary',
    trial: 'CV',
    water_remaining: '',
    aspirate_time_s: '',
    aspirate: formatMetricValue(cv.aspirate),
    aspirate_d: '',
    dispense_time_s: '',
    dispense: formatMetricValue(cv.dispense),
    dispense_d: '',
    aspirate_travel: ''
  })
  return rows
})
const matrixStatisticItems = computed(() => {
  const matrix = selectedChannelTrialMatrix.value || selectedSingleChannelTrialMatrix.value
  if (!matrix) return []
  const values = 'trial_values' in (matrix.rows?.[0] || {})
    ? (matrix.rows as any[]).flatMap(row => {
      return row.trial_values
        .map((point: any) => cleanMetricNumber(point.value))
        .filter((value: number | null): value is number => value !== null)
    })
    : (matrix.rows as any[]).flatMap(row => {
      return [row.aspirate, row.dispense]
        .map(cleanMetricNumber)
        .filter((value: number | null): value is number => value !== null)
    })
  const actualMin = values.length > 0 ? Math.min(...values) : null
  const actualMax = values.length > 0 ? Math.max(...values) : null

  return [
    { label: 'Actual Min', value: formatMetricValue(actualMin) },
    { label: 'Target', value: formatMetricValue(matrix.spec?.target) },
    { label: 'Actual Max', value: formatMetricValue(actualMax) },
    { label: 'Spec %D', value: formatMetricValue(matrix.spec?.d) }
  ].filter(item => item.value !== '')
})
const selectedVolumeTrialRows = computed(() => {
  if (!activeAnalysis.value || selectedVolume.value === null) return []
  return activeAnalysis.value.trial_series.filter(item => item.volume === selectedVolume.value)
})
const allTrialRows = computed<TrialTableRow[]>(() => {
  if (!activeAnalysis.value) return []
  return activeAnalysis.value.trial_series.map(row => {
    const environment = findTrialEnvironment(row.volume, row.trial, row.channel)
    return {
      ...row,
      celsius_pipette: cleanMetricNumber(environment?.celsius_pipette),
      humidity_pipette: cleanMetricNumber(environment?.humidity_pipette),
      celsius_air: cleanMetricNumber(environment?.celsius_air),
      humidity_air: cleanMetricNumber(environment?.humidity_air),
      environment_raw: environment || null
    }
  }).sort((left, right) => {
    const volumeDelta = Number(left.volume) - Number(right.volume)
    if (volumeDelta !== 0) return volumeDelta
    const trialDelta = Number(left.trial) - Number(right.trial)
    if (trialDelta !== 0) return trialDelta
    return String(left.channel || '').localeCompare(String(right.channel || ''), 'zh-CN', { numeric: true })
  })
})
const filteredTrialRows = computed(() => {
  if (trialTableVolumeFilter.value === 'all') return allTrialRows.value
  return allTrialRows.value.filter(row => Number(row.volume) === Number(trialTableVolumeFilter.value))
})
const detailStatisticRows = computed<DetailStatisticRow[]>(() => buildDetailStatisticRows())
const detailVolumeLabel = computed(() => {
  if (trialTableVolumeFilter.value === 'all') return '全部容量'
  return formatVolume(trialTableVolumeFilter.value)
})
const detailRawJson = computed(() => {
  if (filteredTrialRows.value.length === 0) return ''
  return JSON.stringify({
    filter: {
      volume: trialTableVolumeFilter.value === 'all' ? 'all' : Number(trialTableVolumeFilter.value),
      label: detailVolumeLabel.value
    },
    row_count: filteredTrialRows.value.length,
    statistics: detailStatisticRows.value
  }, null, 2)
})
const summaryVolumeColumns = computed(() => {
  if (!activeAnalysis.value) return []
  return activeVolumes.value.map(volume => ({
    key: summaryVolumeKey(volume),
    label: `${formatVolumeShort(volume)} %D - ${tipLabelForVolume(volume)}`
  }))
})
const summaryTableRows = computed<SummaryTableRow[]>(() => {
  if (!activeAnalysis.value) return []
  const rows: SummaryTableRow[] = [
    buildMetricSummaryRow('Aspirate %D', 'aspirate', 'd'),
    buildMetricSummaryRow('Dispense %D', 'dispense', 'd'),
    buildMetricSummaryRow('Aspirate %CV', 'aspirate', 'cv'),
    buildMetricSummaryRow('Dispense %CV', 'dispense', 'cv'),
    buildPerVolumeInfoRow('Tip Batch', getTipBatchForVolume),
    buildSingleInfoRow('Serial Number', activeAnalysis.value.sn),
    buildSingleInfoRow('Scale', getAnalysisValue('scale')),
    buildSingleInfoRow('Robot', getAnalysisValue('robot') || getAnalysisValue('test_robot_id')),
    buildSingleInfoRow('Firmware', getAnalysisValue('firmware')),
    buildSingleInfoRow('Date', formatAnalysisDate(getAnalysisValue('test_time_utc') || activeAnalysis.value.test_time_utc))
  ]
  return rows
})
const specStorageLabel = computed(() => {
  if (!specStorage.value) return ''
  if (specStorage.value === 'mongo') return 'MongoDB'
  if (specStorage.value === 'json') return 'JSON 兜底'
  return '默认配置'
})
const onlineProductNameOptions = computed(() => {
  return Array.from(new Set(
    onlineProductOptions.value
      .map(product => onlineProductName(product))
      .filter(Boolean)
  )).sort()
})
const onlineTestOptions = computed(() => {
  return uniqueTestTypes(onlineProductOptions.value.flatMap(product => (product.tests || []).map(test => test.test_type)))
})
const onlineSnOptions = computed(() => {
  return onlineProductOptions.value
    .filter(product => productMatchesOnlineFilter(product))
    .filter(product => Boolean(findOnlineTest(product)))
    .sort((left, right) => String(right.latest_date || '').localeCompare(String(left.latest_date || '')))
})
const selectedOnlineProduct = computed(() => {
  return onlineSnOptions.value.find(product => product.barcode === onlineFilters.value.sn) ||
    onlineProductOptions.value.find(product => product.barcode === onlineFilters.value.product && Boolean(findOnlineTest(product))) ||
    null
})
const selectedOnlineTest = computed(() => {
  return findOnlineTest(selectedOnlineProduct.value)
})
const canEditOnlineCsvLink = computed(() => Boolean(onlineFilters.value.product && onlineFilters.value.test))
const effectiveOnlineCsvLink = computed(() => {
  if (!canEditOnlineCsvLink.value) return ''
  return onlineManualCsvLink.value.trim() || getOnlineTestCsvLink(selectedOnlineTest.value)
})

function productMatchesOnlineFilter(product: ProductManagementItem) {
  if (!onlineFilters.value.product) return true
  return onlineProductName(product) === onlineFilters.value.product || product.barcode === onlineFilters.value.product
}

function findOnlineTest(product?: ProductManagementItem | null) {
  const matches = (product?.tests || []).filter(test => sameTestType(test.test_type, onlineFilters.value.test))
  return matches.find(test => Boolean(getOnlineTestCsvLink(test))) || matches[0] || null
}

function getOnlineTestCsvLink(test?: ProductManagementTest | null) {
  const csvLink = String(test?.csv_link || '').trim()
  if (csvLink) return csvLink
  const sourcePath = String(test?.source_csv_path || '').trim()
  return /^https?:\/\//i.test(sourcePath) ? sourcePath : ''
}

function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return
  const existingIndex = selectedFiles.value.findIndex(item => item.name === file.name)
  if (existingIndex >= 0) {
    selectedFiles.value.splice(existingIndex, 1, file)
  } else {
    selectedFiles.value.push(file)
  }
  loadMessage.value = ''
}

function removeFile(fileName: string) {
  selectedFiles.value = selectedFiles.value.filter(file => file.name !== fileName)
  if (selectedFiles.value.length === 0) {
    clearFiles()
  }
}

function clearFiles() {
  selectedFiles.value = []
  analyses.value = []
  analysisErrors.value = []
  selectedAnalysisIndex.value = 0
  selectedVolume.value = null
  selectedWaterRemainVolume.value = null
  selectedWaterRemainChannel.value = 'avg'
  trialChartMode.value = 'd'
  selectedTemperatureVolume.value = 'all'
  selectedHumidityVolume.value = 'all'
  trialTableVolumeFilter.value = 'all'
  detailDrawerVisible.value = false
  loadMessage.value = ''
  uploadRef.value?.clearFiles()
  disposeCharts()
}

async function analyzeSelectedFiles() {
  if (selectedFiles.value.length === 0) return
  loading.value = true
  try {
    const response = await dataAnalysisApi.analyzeFiles(selectedFiles.value)
    applyAnalysisResponse(response.data)
    if (analyses.value.length > 0) {
      ElMessage.success('分析完成')
    } else {
      ElMessage.warning('未生成分析结果')
    }
  } catch (error: any) {
    ElMessage.error('分析失败: ' + formatError(error))
  } finally {
    loading.value = false
  }
}

async function analyzePath(filePath: string) {
  loading.value = true
  loadMessage.value = `正在分析 ${filePath}`
  try {
    const response = await dataAnalysisApi.analyzePaths([filePath])
    applyAnalysisResponse(response.data)
    loadMessage.value = ''
  } catch (error: any) {
    loadMessage.value = ''
    ElMessage.error('分析失败: ' + formatError(error))
  } finally {
    loading.value = false
  }
}

async function analyzeOnlineSelection() {
  const product = selectedOnlineProduct.value
  const testType = canonicalTestType(onlineFilters.value.test)
  const csvLink = effectiveOnlineCsvLink.value
  if (!onlineFilters.value.product || !testType || !csvLink) return
  loading.value = true
  loadMessage.value = `正在读取 ${product?.barcode || onlineFilters.value.product} / ${formatTestType(testType)}`
  try {
    const response = await dataAnalysisApi.analyzeOnline({
      barcode: product?.barcode || '',
      product: product?.model || onlineFilters.value.product,
      test_type: testType,
      csv_link: csvLink
    })
    applyAnalysisResponse(response.data)
    loadMessage.value = ''
    if (analyses.value.length > 0) {
      ElMessage.success('在线分析完成')
    } else {
      ElMessage.warning('未生成分析结果')
    }
  } catch (error: any) {
    loadMessage.value = ''
    ElMessage.error('在线分析失败: ' + formatError(error))
  } finally {
    loading.value = false
  }
}

async function loadOnlineProducts() {
  onlineProductsLoading.value = true
  try {
    const response = await productManagementApi.getProducts({ page: 1, pageSize: 2000 })
    onlineProductOptions.value = response.data.products || []
    if (onlineFilters.value.product) {
      handleOnlineProductChange()
    }
  } catch (error: any) {
    ElMessage.error('加载在线产品失败: ' + formatError(error))
  } finally {
    onlineProductsLoading.value = false
  }
}

function handleOnlineProductChange() {
  const normalizedTest = canonicalTestType(onlineFilters.value.test)
  if (!onlineTestOptions.value.includes(normalizedTest)) {
    onlineFilters.value.test = onlineTestOptions.value[0] || ''
  } else {
    onlineFilters.value.test = normalizedTest
  }
  handleOnlineTestChange()
}

function handleOnlineTestChange() {
  if (!onlineSnOptions.value.some(product => product.barcode === onlineFilters.value.sn)) {
    onlineFilters.value.sn = onlineSnOptions.value[0]?.barcode || ''
  }
  syncManualCsvLink()
}

function handleOnlineSnChange() {
  syncManualCsvLink()
}

function syncManualCsvLink() {
  onlineManualCsvLink.value = ''
}

function applyAnalysisResponse(data: DataAnalysisResponse) {
  const unsupportedAnalyses = (data.analyses || []).filter(item => !isPipetteGravimetricAnalysis(item))
  analyses.value = (data.analyses || []).filter(isPipetteGravimetricAnalysis)
  analysisErrors.value = data.errors || []
  if (unsupportedAnalyses.length > 0 && analyses.value.length === 0) {
    analysisErrors.value = [
      ...analysisErrors.value,
      ...unsupportedAnalyses.map(item => ({
        file: item.file,
        message: `当前页面只支持移液器容量分析，请使用对应诊断分析页面打开 ${item.channel_label || item.channel || '该测试'}`
      }))
    ]
  }
  selectedAnalysisIndex.value = 0
  selectedVolume.value = activeVolumes.value[0] ?? null
  selectedWaterRemainVolume.value = activeVolumes.value[0] ?? null
  selectedWaterRemainChannel.value = 'avg'
  selectedTrialAction.value = 'dispense'
  trialChartMode.value = 'd'
  selectedTemperatureVolume.value = 'all'
  selectedHumidityVolume.value = 'all'
  trialTableVolumeFilter.value = 'all'
  detailDrawerVisible.value = false
  redirectUnsupportedAnalysis(unsupportedAnalyses)
  syncSelectedTrialChannels()
  nextTick(renderCharts)
}

function formatError(error: any) {
  return error?.response?.data?.detail || error?.message || '未知错误'
}

function isPipetteGravimetricAnalysis(item: DataAnalysisItem) {
  return item.view_key === 'pipette_gravimetric' ||
    item.channel === 'pipette_gravimetric' ||
    String(item.analyzer_key || '').startsWith('gravimetric.')
}

function isGravimetricTest(testType?: string) {
  const normalized = String(testType || '').toLowerCase().replace(/[^a-z0-9]+/g, '')
  return normalized.includes('gravimetric') || normalized.includes('volume')
}

function redirectUnsupportedAnalysis(items: DataAnalysisItem[]) {
  if (analyses.value.length > 0 || items.length === 0) return
  const diagnostic = items.find(item => item.view_key === 'pipette_assembly_qc' || item.channel === 'pipette_assembly_qc')
  const path = diagnostic?.file?.path
  if (!diagnostic || !path) return
  ElMessage.info('已识别为移液器诊断数据，正在切换到诊断分析页面')
  router.replace({
    path: '/data/analysis/pipette-assembly-qc',
    query: {
      path,
      name: diagnostic.file?.name || diagnostic.sn || ''
    }
  })
}

function onlineProductName(product: ProductManagementItem) {
  const model = String(product.model || '').trim()
  return model && model !== '-' ? model : ''
}

function formatOnlineTestLabel(test: ProductManagementTest) {
  return [
    formatTestType(test.test_type),
    test.source || test.status || '',
    formatOnlineDate(test.date)
  ].filter(Boolean).join(' ')
}

function formatOnlineProductLabel(product: ProductManagementItem) {
  const updatedAt = formatOnlineProductUpdatedAt(product)
  return [product.barcode, updatedAt].filter(Boolean).join(' ')
}

function formatOnlineProductUpdatedAt(product: ProductManagementItem, mode: 'full' | 'short' = 'full') {
  const latestDate = product.latest_date || latestTestDate(product.tests)
  const formattedDate = formatOnlineDate(latestDate)
  if (!formattedDate) return ''
  return `${mode === 'short' ? '更新' : '最后更新'} ${formattedDate}`
}

function latestTestDate(tests?: ProductManagementTest[]) {
  if (!tests?.length) return ''
  const latest = tests
    .map(test => test.date || '')
    .filter(Boolean)
    .sort((left, right) => {
      return new Date(right).getTime() - new Date(left).getTime()
    })[0]
  return latest || ''
}

function formatOnlineDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).replace(/\//g, '/')
}

async function openSpecDialog() {
  specDialogVisible.value = true
  if (specProducts.value.length === 0) {
    await loadSpecSettings()
  }
}

async function loadSpecSettings() {
  specLoading.value = true
  try {
    const response = await dataAnalysisApi.getSpecs()
    specProducts.value = response.data.products || []
    specItems.value = response.data.specs || []
    specStorage.value = response.data.storage || ''
    const product = specForm.value.product || specProducts.value[0]?.product || ''
    if (product) {
      setSpecForm(product)
    }
    if (response.data.error) {
      ElMessage.warning(`Spec 配置使用默认值: ${response.data.error}`)
    }
  } catch (error: any) {
    ElMessage.error('加载 Spec 失败: ' + formatError(error))
  } finally {
    specLoading.value = false
  }
}

function handleSpecProductChange(product: string) {
  setSpecForm(product)
}

function setSpecForm(product: string) {
  const item = specItems.value.find(spec => spec.product === product)
  const catalogItem = specProducts.value.find(specProduct => specProduct.product === product)
  specForm.value = cloneSpecItem(item || {
    product,
    product_name: catalogItem?.product_name || product,
    analysis_product: catalogItem?.analysis_product || product,
    test_type: 'gravimetric',
    test_name: 'Gravimetric',
    volumes: []
  })
}

function cloneSpecItem(item: DataAnalysisSpecItem): DataAnalysisSpecItem {
  return {
    product: item.product,
    product_name: item.product_name,
    analysis_product: item.analysis_product,
    test_type: item.test_type || 'gravimetric',
    test_name: item.test_name || 'Gravimetric',
    volumes: (item.volumes || []).map(row => ({
      volume: Number(row.volume),
      cv: Number(row.cv),
      d: Number(row.d)
    }))
  }
}

function addSpecVolume() {
  specForm.value.volumes.push({ volume: 0, cv: 0, d: 0 })
}

function removeSpecVolume(index: number) {
  specForm.value.volumes.splice(index, 1)
}

async function saveSpecSettings() {
  const validationError = validateSpecForm()
  if (validationError) {
    ElMessage.warning(validationError)
    return
  }

  specSaving.value = true
  try {
    const payload = normalizeSpecForm()
    const response = await dataAnalysisApi.saveGravimetricSpec(payload)
    const savedItem = response.data
    upsertSpecItem(savedItem)
    specStorage.value = savedItem.storage || savedItem.source || specStorage.value
    setSpecForm(savedItem.product)
    ElMessage.success(`Spec 已保存到 ${specStorageLabel.value || '配置'}`)
  } catch (error: any) {
    ElMessage.error('保存 Spec 失败: ' + formatError(error))
  } finally {
    specSaving.value = false
  }
}

function validateSpecForm() {
  if (!specForm.value.product) return '请选择产品'
  if (specForm.value.volumes.length === 0) return '至少需要一个容量'
  const seenVolumes = new Set<number>()
  for (const row of specForm.value.volumes) {
    const volume = Number(row.volume)
    const cv = Number(row.cv)
    const dValue = Number(row.d)
    if (!Number.isFinite(volume) || volume <= 0) return '容量必须大于 0'
    if (!Number.isFinite(cv) || cv < 0) return 'CV Spec 不能小于 0'
    if (!Number.isFinite(dValue) || dValue < 0) return '%D Spec 不能小于 0'
    if (seenVolumes.has(volume)) return `容量 ${volume} uL 重复`
    seenVolumes.add(volume)
  }
  return ''
}

function normalizeSpecForm(): DataAnalysisSpecItem {
  const volumes = specForm.value.volumes
    .map(normalizeSpecVolume)
    .sort((left, right) => left.volume - right.volume)
  return {
    ...specForm.value,
    test_type: 'gravimetric',
    test_name: 'Gravimetric',
    volumes
  }
}

function normalizeSpecVolume(row: DataAnalysisSpecVolume): DataAnalysisSpecVolume {
  return {
    volume: Number(row.volume),
    cv: Number(row.cv),
    d: Number(row.d)
  }
}

function upsertSpecItem(item: DataAnalysisSpecItem) {
  const index = specItems.value.findIndex(spec => spec.product === item.product)
  if (index >= 0) {
    specItems.value.splice(index, 1, item)
  } else {
    specItems.value.push(item)
  }
}

function formatVolume(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return `${Number(value).toLocaleString('zh-CN')} uL`
}

function formatVolumeShort(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '-'
  return `${Number(value).toLocaleString('zh-CN')}ul`
}

function formatMetricValue(value: unknown) {
  const numeric = cleanMetricNumber(value)
  if (numeric === null || !Number.isFinite(numeric)) return ''
  return Number(numeric.toFixed(2)).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  })
}

function formatTimeValue(value: unknown) {
  const numeric = cleanMetricNumber(value)
  if (numeric === null || !Number.isFinite(numeric)) return ''
  return Number(numeric.toFixed(1)).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1
  })
}

function cleanMetricNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function summaryVolumeKey(volume: number) {
  return `volume_${String(volume).replace(/\./g, '_')}`
}

function tipLabelForVolume(volume: number) {
  if (volume <= 50) return 'T50'
  if (volume <= 200) return 'T200'
  return 'T1000'
}

function buildMetricSummaryRow(label: string, action: string, key: 'cv' | 'd'): SummaryTableRow {
  const row: SummaryTableRow = { label }
  activeVolumes.value.forEach(volume => {
    const metric = (activeAnalysis.value?.volume_metrics || []).find(item => {
      return item.scope_id === 'all' && item.action === action && Number(item.volume) === Number(volume)
    })
    row[summaryVolumeKey(volume)] = formatMetricValue(metric?.[key])
  })
  return row
}

function findTrialEnvironment(volume: number, trial: number, channel?: string) {
  const rows = activeAnalysis.value?.environment_series || []
  const matches = rows.filter(item => {
    return Number(item.volume) === Number(volume) &&
      Number(item.trial) === Number(trial) &&
      (!channel || String(item.channel) === String(channel))
  })
  return matches.find(item => String(item.action || '').toUpperCase() === 'DISPENSE') ||
    matches.find(item => String(item.action || '').toUpperCase() === 'ASPIRATE') ||
    matches[0]
}

function openTrialDetail() {
  detailDrawerVisible.value = true
}

function buildDetailStatisticRows() {
  const rows = filteredTrialRows.value
  const statistics: DetailStatisticRow[] = []
  const singleVolume = getSingleFilteredVolume(rows)

  if (singleVolume !== null) {
    statistics.push(
      buildAggregateStatistic('Aspirate CV', calculateCv(rows.map(row => row.aspirate))),
      buildAggregateStatistic('Dispense CV', calculateCv(rows.map(row => row.dispense))),
      buildRangeStatistic('Aspirate %D', rows.map(row => row.aspirate_d)),
      buildRangeStatistic('Dispense %D', rows.map(row => row.dispense_d))
    )
  }

  statistics.push(
    buildRangeStatistic('移液器温度', rows.map(row => row.celsius_pipette)),
    buildRangeStatistic('环境温度', rows.map(row => row.celsius_air)),
    buildRangeStatistic('移液器湿度', rows.map(row => row.humidity_pipette)),
    buildRangeStatistic('环境湿度', rows.map(row => row.humidity_air)),
    buildRangeStatistic('Water Remain', rows.map(row => row.water_remain))
  )

  return statistics
}

function getSingleFilteredVolume(rows: TrialTableRow[]) {
  if (trialTableVolumeFilter.value !== 'all') return Number(trialTableVolumeFilter.value)
  const volumes = new Set(rows.map(row => Number(row.volume)))
  return volumes.size === 1 ? Array.from(volumes)[0] : null
}

function buildAggregateStatistic(metric: string, value: number | null): DetailStatisticRow {
  return {
    metric,
    min: 'N/A',
    max: 'N/A',
    avg: formatMetricValue(value)
  }
}

function buildRangeStatistic(metric: string, values: unknown[]): DetailStatisticRow {
  const numbers = values.map(cleanMetricNumber).filter((value): value is number => value !== null)
  if (numbers.length === 0) {
    return { metric, min: '', max: '', avg: '' }
  }
  return {
    metric,
    min: formatMetricValue(Math.min(...numbers)),
    max: formatMetricValue(Math.max(...numbers)),
    avg: formatMetricValue(averageNumber(numbers))
  }
}

function calculateCv(values: unknown[]) {
  const numbers = values.map(cleanMetricNumber).filter((value): value is number => value !== null)
  if (numbers.length < 2) return null
  const avg = averageNumber(numbers)
  if (avg === null || avg === 0) return null
  const variance = numbers.reduce((sum, value) => sum + (value - avg) ** 2, 0) / (numbers.length - 1)
  return Math.sqrt(variance) / Math.abs(avg) * 100
}

function averageNumber(values: unknown[]) {
  const numbers = values.map(cleanMetricNumber).filter((value): value is number => value !== null)
  if (numbers.length === 0) return null
  return numbers.reduce((sum, value) => sum + value, 0) / numbers.length
}

async function copyDetailRaw() {
  if (!detailRawJson.value) return
  try {
    await navigator.clipboard.writeText(detailRawJson.value)
    ElMessage.success('已复制 Raw JSON')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

function buildPerVolumeInfoRow(label: string, getValue: (volume: number) => unknown): SummaryTableRow {
  const row: SummaryTableRow = { label }
  activeVolumes.value.forEach(volume => {
    row[summaryVolumeKey(volume)] = formatInfoValue(getValue(volume))
  })
  return row
}

function buildSingleInfoRow(label: string, value: unknown): SummaryTableRow {
  const row: SummaryTableRow = { label }
  activeVolumes.value.forEach((volume, index) => {
    row[summaryVolumeKey(volume)] = index === 0 ? formatInfoValue(value) : ''
  })
  return row
}

function getTipBatchForVolume(volume: number) {
  const serialNumbers = activeAnalysis.value?.serial_numbers || {}
  if (volume <= 50) return serialNumbers.tips_50ul
  if (volume <= 200) return serialNumbers.tips_200ul
  return serialNumbers.tips_1000ul
}

function getAnalysisValue(key: string) {
  if (!activeAnalysis.value) return ''
  const serialNumbers = activeAnalysis.value.serial_numbers || {}
  const metadata = activeAnalysis.value.metadata || {}
  const config = activeAnalysis.value.config || {}
  return serialNumbers[key] ?? metadata[key] ?? config[key] ?? ''
}

function formatAnalysisDate(value: unknown) {
  const text = formatInfoValue(value)
  if (!text) return ''
  return text.split('-')[0]
}

function formatInfoValue(value: unknown) {
  if (value === null || value === undefined || value === 'None') return ''
  return String(value)
}

function setTrialChartMode(mode: TrialChartMode) {
  trialChartMode.value = mode
}

function buildMatrixTrialSummaryRow(
  label: string,
  summary: NonNullable<DataAnalysisItem['channel_trial_matrices']>[number]['trial_summary'] = [],
  key: 'average' | 'cv' | 'd'
): ChannelTrialMatrixTableRow {
  const row: ChannelTrialMatrixTableRow = {
    row_label: label,
    _row_type: 'summary'
  }
  summary.forEach(item => {
    row[`trial_${item.trial}`] = formatMetricValue(item[key])
  })
  return row
}

function matrixCellStyle({ row, column }: { row: ChannelTrialMatrixTableRow; column: { property?: string } }) {
  const property = column.property || ''
  if (row._row_type !== 'channel' || !property.startsWith('trial_')) return {}

  const value = row._raw_values?.[property]
  const target = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.target)
  if (typeof value !== 'number' || target === null || target === 0) return {}

  const specD = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.d)
  const deviationPercent = Math.abs(value - target) / Math.abs(target) * 100
  const limit = specD && specD > 0 ? specD : 10
  const level = Math.min(deviationPercent / limit, 1.5)
  const alpha = Math.min(0.12 + level * 0.28, 0.5)
  const textColor = level >= 1 ? '#7f1d1d' : '#334155'

  return {
    backgroundColor: `rgba(220, 38, 38, ${alpha})`,
    color: textColor,
    fontWeight: level >= 1 ? 700 : 500
  }
}

function singleChannelMatrixRowClassName({ row }: { row: { row_type?: string } }) {
  return row.row_type === 'summary' ? 'matrix-summary-row' : ''
}

function isMatrixTrialValueOutOfSpec(value: number | null) {
  const target = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.target)
  const specD = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.d)
  if (value === null || target === null || target === 0 || specD === null) return false
  const deviationPercent = Math.abs(value - target) / Math.abs(target) * 100
  return deviationPercent > specD
}

function isMatrixCvOutOfSpec(value: number | null) {
  const specCv = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.cv)
  return value !== null && specCv !== null && value > specCv
}

function isMatrixDOutOfSpec(value: number | null) {
  const specD = cleanMetricNumber(selectedChannelTrialMatrix.value?.spec?.d)
  return value !== null && specD !== null && Math.abs(value) > specD
}

function getChart(instance: EChartsType | null, element: HTMLDivElement | null) {
  if (!element) return null
  return instance || init(element)
}

function renderCharts() {
  if (!activeAnalysis.value) return
  renderTrialChart()
  renderTemperatureChart()
  renderHumidityChart()
  renderWaterRemainChart()
  nextTick(resizeCharts)
}

function baseGridOption(): EChartsCoreOption {
  return {
    color: ['#2563eb', '#16a34a', '#dc2626', '#f59e0b', '#7c3aed', '#0891b2'],
    tooltip: { trigger: 'axis', confine: true },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    grid: { top: 42, right: 24, bottom: 36, left: 48, containLabel: true },
    xAxis: { type: 'category', axisTick: { alignWithLabel: true } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef2f7' } } }
  }
}

function renderTrialChart() {
  trialChart = getChart(trialChart, trialChartRef.value)
  if (!trialChart || !activeAnalysis.value) return
  if (hasChannelTrialMatrices.value) {
    renderChannelTrialChart()
    return
  }

  const rows = selectedVolumeTrialRows.value
  const labels = buildTrialLabels(rows)
  const rowByTrial = new Map(rows.map(item => [item.trial, item]))
  const selectedSeries = new Set(trialSeriesSelection.value)
  const volumeSpecD = getSelectedVolumeSpecD()
  const series: LineSeriesOption[] = []

  if (selectedSeries.has('aspirate_d')) {
    series.push({
      name: 'Aspirate %D',
      type: 'line',
      smooth: true,
      data: labels.map((_, index) => rowByTrial.get(index + 1)?.aspirate_d ?? null)
    })
  }

  if (selectedSeries.has('dispense_d')) {
    series.push({
      name: 'Dispense %D',
      type: 'line',
      smooth: true,
      data: labels.map((_, index) => rowByTrial.get(index + 1)?.dispense_d ?? null)
    })
  }

  if (volumeSpecD !== null) {
    series.push({
      name: '+ Spec %D',
      type: 'line',
      symbol: 'none',
      lineStyle: { color: '#eab308', width: 2 },
      data: labels.map(() => volumeSpecD)
    })
    series.push({
      name: '- Spec %D',
      type: 'line',
      symbol: 'none',
      lineStyle: { color: '#eab308', width: 2 },
      data: labels.map(() => -volumeSpecD)
    })
  }

  trialChart.setOption({
    ...baseGridOption(),
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: '%D', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series
  } satisfies ChartOption, true)
}

function renderChannelTrialChart() {
  if (!trialChart) return
  if (trialChartMode.value === 'cv') {
    renderChannelCvChart()
    return
  }

  const matrix = selectedChannelTrialMatrix.value
  const labels = (matrix?.trials || []).map(trial => `T${trial}`)
  const selectedChannels = new Set(selectedTrialChannels.value)
  const series: LineSeriesOption[] = []

  ;(matrix?.rows || []).forEach(row => {
    if (!selectedChannels.has(String(row.channel))) return
    const pointByTrial = new Map(row.trial_values.map(point => [point.trial, point]))
    series.push({
      name: row.label || `CH${row.channel}`,
      type: 'line',
      smooth: true,
      data: (matrix?.trials || []).map(trial => pointByTrial.get(trial)?.d ?? null)
    })
  })

  const specD = cleanMetricNumber(matrix?.spec?.d)
  if (specD !== null && labels.length > 0) {
    series.push({
      name: '+ Spec %D',
      type: 'line',
      symbol: 'none',
      lineStyle: { color: '#eab308', width: 2 },
      data: labels.map(() => specD)
    })
    series.push({
      name: '- Spec %D',
      type: 'line',
      symbol: 'none',
      lineStyle: { color: '#eab308', width: 2 },
      data: labels.map(() => -specD)
    })
  }

  trialChart.setOption({
    ...baseGridOption(),
    legend: { top: 0, type: 'scroll', textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: '%D', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series
  } satisfies ChartOption, true)
}

function renderChannelCvChart() {
  if (!trialChart) return
  const matrix = selectedChannelTrialMatrix.value
  const rows = matrix?.rows || []
  const labels = rows.map(row => row.label || `CH${row.channel}`)
  const specCv = cleanMetricNumber(matrix?.spec?.cv)
  const series: Array<BarSeriesOption | LineSeriesOption> = [
    {
      name: 'CV%',
      type: 'bar',
      data: rows.map(row => cleanMetricNumber(row.cv))
    }
  ]

  if (specCv !== null && labels.length > 0) {
    series.push({
      name: 'Spec CV',
      type: 'line',
      symbol: 'none',
      lineStyle: { color: '#eab308', width: 2 },
      data: labels.map(() => specCv)
    })
  }

  trialChart.setOption({
    ...baseGridOption(),
    legend: { top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: 'CV%', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series
  } satisfies ChartOption, true)
}

function getSelectedVolumeSpecD() {
  if (!activeAnalysis.value || selectedVolume.value === null) return null
  const volumeResults = Array.isArray(activeAnalysis.value.summary?.volume_results)
    ? activeAnalysis.value.summary.volume_results
    : []
  const result = volumeResults.find((item: any) => Number(item?.volume) === Number(selectedVolume.value))
  const specD = Number(result?.spec?.d)
  return Number.isFinite(specD) ? specD : null
}

function renderTemperatureChart() {
  temperatureChart = getChart(temperatureChart, temperatureChartRef.value)
  if (!temperatureChart || !activeAnalysis.value) return
  const rows = getEnvironmentChartRows(selectedTemperatureVolume.value)
  const labels = rows.map(formatEnvironmentLabel)
  const selectedSeries = new Set(temperatureSeriesSelection.value)
  const series: LineSeriesOption[] = []

  if (selectedSeries.has('pipette')) {
    series.push({
      name: '移液器温度',
      type: 'line',
      smooth: true,
      data: rows.map(item => normalizeEnvironmentTemp(item.celsius_pipette))
    })
  }

  if (selectedSeries.has('air')) {
    series.push({
      name: '环境温度',
      type: 'line',
      smooth: true,
      data: rows.map(item => normalizeEnvironmentTemp(item.celsius_air))
    })
  }

  temperatureChart.setOption({
    ...baseGridOption(),
    tooltip: { trigger: 'axis', confine: true },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: 'C', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series
  } satisfies ChartOption, true)
}

function renderHumidityChart() {
  humidityChart = getChart(humidityChart, humidityChartRef.value)
  if (!humidityChart || !activeAnalysis.value) return
  const rows = getEnvironmentChartRows(selectedHumidityVolume.value)
  const labels = rows.map(formatEnvironmentLabel)
  const selectedSeries = new Set(humiditySeriesSelection.value)
  const series: LineSeriesOption[] = []

  if (selectedSeries.has('pipette')) {
    series.push({
      name: '移液器湿度',
      type: 'line',
      smooth: true,
      data: rows.map(item => item.humidity_pipette)
    })
  }

  if (selectedSeries.has('air')) {
    series.push({
      name: '环境湿度',
      type: 'line',
      smooth: true,
      data: rows.map(item => item.humidity_air)
    })
  }

  humidityChart.setOption({
    ...baseGridOption(),
    tooltip: { trigger: 'axis', confine: true },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: '%RH', splitLine: { lineStyle: { color: '#eef2f7' } } },
    series
  } satisfies ChartOption, true)
}

function getEnvironmentChartRows(volumeFilter: 'all' | number) {
  const rows = volumeFilter === 'all'
    ? activeAnalysis.value?.environment_series || []
    : (activeAnalysis.value?.environment_series || []).filter(item => {
        return Number(item.volume) === Number(volumeFilter)
      })
  const dispenseRows = rows.filter(item => String(item.action || '').toUpperCase() === 'DISPENSE')
  return dispenseRows.length > 0 ? dispenseRows : rows
}

function formatEnvironmentLabel(item: { volume: number; trial: number; action?: string }) {
  const action = String(item.action || '').toUpperCase()
  return action && action !== 'DISPENSE'
    ? `${formatVolume(item.volume)} T${item.trial} ${action}`
    : `${formatVolume(item.volume)} T${item.trial}`
}

function normalizeEnvironmentTemp(value: number | null | undefined) {
  if (value === null || value === undefined || value < -20) return null
  return value
}

function renderWaterRemainChart() {
  waterRemainChart = getChart(waterRemainChart, waterRemainChartRef.value)
  if (!waterRemainChart || !activeAnalysis.value) return
  const rows = getWaterRemainChartRows()
  const labels = buildTrialLabels(rows)
  const waterRemainByTrial = buildAverageByTrial(rows, 'water_remain')
  const series: BarSeriesOption[] = [
    {
      name: 'Water Remain',
      type: 'bar',
      data: labels.map((_, index) => waterRemainByTrial.get(index + 1) ?? null)
    }
  ]
  waterRemainChart.setOption({
    ...baseGridOption(),
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', name: 'uL' },
    series
  } satisfies ChartOption, true)
}

function getWaterRemainBaseRows() {
  if (!activeAnalysis.value || selectedWaterRemainVolume.value === null) return []
  return activeAnalysis.value.trial_series.filter(item => {
    return Number(item.volume) === Number(selectedWaterRemainVolume.value)
  })
}

function getWaterRemainChartRows() {
  const rows = getWaterRemainBaseRows()
  if (selectedWaterRemainChannel.value === 'avg') return rows
  return rows.filter(item => String(item.channel) === selectedWaterRemainChannel.value)
}

function buildTrialLabels(rows: Array<{ trial: number }>) {
  const maxTrial = Math.max(0, ...rows.map(item => Number(item.trial) || 0))
  return Array.from({ length: maxTrial || 1 }, (_, index) => `T${index + 1}`)
}

function buildAverageByTrial(rows: Array<Record<string, any>>, key: string) {
  const grouped = new Map<number, number[]>()
  rows.forEach(row => {
    const trial = Number(row.trial)
    const value = cleanMetricNumber(row[key])
    if (!Number.isFinite(trial) || value === null) return
    const values = grouped.get(trial) || []
    values.push(value)
    grouped.set(trial, values)
  })
  const averages = new Map<number, number>()
  grouped.forEach((values, trial) => {
    const avg = averageNumber(values)
    if (avg !== null) averages.set(trial, avg)
  })
  return averages
}

function syncSelectedTrialChannels() {
  const available = availableTrialChannels.value
  if (available.length === 0) {
    selectedTrialChannels.value = []
    return
  }
  const availableSet = new Set(available)
  const nextSelection = selectedTrialChannels.value.filter(channel => availableSet.has(channel))
  selectedTrialChannels.value = nextSelection.length > 0 ? nextSelection : [...available]
}

function syncSelectedWaterRemainChannel() {
  const available = new Set(waterRemainChannelOptions.value.map(item => item.value))
  if (!available.has(selectedWaterRemainChannel.value)) {
    selectedWaterRemainChannel.value = 'avg'
  }
}

function disposeCharts() {
  ;[trialChart, temperatureChart, humidityChart, waterRemainChart].forEach(chart => chart?.dispose())
  trialChart = null
  temperatureChart = null
  humidityChart = null
  waterRemainChart = null
}

function resizeCharts() {
  ;[trialChart, temperatureChart, humidityChart, waterRemainChart].forEach(chart => chart?.resize())
}

function initializeFromQuery() {
  const path = typeof route.query.path === 'string' ? route.query.path : ''
  const name = typeof route.query.name === 'string' ? route.query.name : ''
  const barcode = typeof route.query.barcode === 'string' ? route.query.barcode : ''
  const testKey = typeof route.query.test === 'string' ? route.query.test : ''
  const csvLink = typeof route.query.csv_link === 'string' ? route.query.csv_link : ''
  if (csvLink || barcode || testKey) {
    analysisMode.value = 'online'
    loadOnlineProducts().then(() => {
      const routedProduct = onlineProductOptions.value.find(product => product.barcode === barcode)
      if (routedProduct) {
        onlineFilters.value.product = onlineProductName(routedProduct)
        const routedTest = routedProduct.tests.find(test => test.key === testKey) ||
          routedProduct.tests.find(test => sameTestType(test.test_type, testKey))
        onlineFilters.value.test = canonicalTestType(routedTest?.test_type || testKey) || onlineTestOptions.value[0] || ''
        onlineFilters.value.sn = routedProduct.barcode
      } else {
        onlineFilters.value.product = onlineProductNameOptions.value[0] || ''
        handleOnlineProductChange()
      }
      onlineManualCsvLink.value = csvLink
    })
    return
  }
  if (path) {
    analysisMode.value = 'local'
    analyzePath(path)
    return
  }
  if (name) {
    analysisMode.value = 'local'
    loadMessage.value = `已选择 ${name}，请上传本地原始 CSV 后分析`
  }
}

watch(activeAnalysis, (analysis) => {
  const volumes = Array.isArray(analysis?.volumes) ? analysis.volumes : []
  selectedVolume.value = volumes[0] ?? null
  selectedWaterRemainVolume.value = volumes[0] ?? null
  selectedWaterRemainChannel.value = 'avg'
  selectedTrialAction.value = 'dispense'
  trialChartMode.value = 'd'
  selectedTemperatureVolume.value = 'all'
  selectedHumidityVolume.value = 'all'
  syncSelectedTrialChannels()
  nextTick(renderCharts)
})

watch(selectedVolume, () => {
  syncSelectedTrialChannels()
  nextTick(renderTrialChart)
})

watch(selectedTrialAction, () => {
  syncSelectedTrialChannels()
  nextTick(renderTrialChart)
})

watch(selectedTrialChannels, () => {
  nextTick(renderTrialChart)
}, { deep: true })

watch(trialChartMode, () => {
  nextTick(renderTrialChart)
})

watch(selectedWaterRemainVolume, () => {
  syncSelectedWaterRemainChannel()
  nextTick(renderWaterRemainChart)
})

watch(selectedWaterRemainChannel, () => {
  nextTick(renderWaterRemainChart)
})

watch(selectedTemperatureVolume, () => {
  nextTick(renderTemperatureChart)
})

watch(selectedHumidityVolume, () => {
  nextTick(renderHumidityChart)
})

watch(trialSeriesSelection, () => {
  nextTick(renderTrialChart)
}, { deep: true })

watch(temperatureSeriesSelection, () => {
  nextTick(renderTemperatureChart)
}, { deep: true })

watch(humiditySeriesSelection, () => {
  nextTick(renderHumidityChart)
}, { deep: true })

watch(analysisMode, (mode) => {
  if (mode === 'local') {
    nextTick(renderCharts)
  } else {
    if (onlineProductOptions.value.length === 0) {
      loadOnlineProducts()
    }
    nextTick(renderCharts)
  }
})

onMounted(() => {
  initializeFromQuery()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
})
</script>

<style scoped>
.analysis-view {
  height: 100%;
  overflow-y: auto;
  background: #f8fafc;
}

.analysis-mode-bar {
  position: sticky;
  top: 0;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
}

.mode-switch :deep(.el-button) {
  min-width: 92px;
}

.spec-settings-button {
  flex: 0 0 auto;
}

.local-analysis {
  padding: 10px 12px 14px;
}

.online-analysis {
  padding: 0;
}

.upload-stage {
  min-height: calc(100vh - 74px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 8vh;
}

.local-upload-panel {
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: #ffffff;
}

.summary-table-section,
.table-section {
  border-top: 1px solid #dfe5ee;
  background: #ffffff;
}

.chart-panel {
  overflow: hidden;
  border: 1px solid #e6ebf2;
  border-radius: 3px;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.local-upload-panel {
  width: min(720px, 100%);
  padding: 14px;
}

.analysis-upload-large {
  display: block;
  width: 100%;
}

.analysis-upload-large :deep(.el-upload) {
  width: 100%;
}

.analysis-upload-large :deep(.el-upload-dragger) {
  width: 100%;
  height: clamp(190px, 28vh, 280px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.upload-empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: #606266;
}

.upload-icon {
  color: #2563eb;
  font-size: 34px;
}

.upload-title {
  color: #303133;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0;
}

.upload-subtitle {
  color: #909399;
  font-size: 13px;
}

.local-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.file-queue {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.result-select {
  width: min(360px, 100%);
}

.hint-line,
.error-list,
.loading-panel,
.analysis-result-card,
.result-toolbar,
  .summary-table-section,
  .chart-grid,
  .table-section {
  margin-top: 10px;
}

.hint-line {
  color: #606266;
  font-size: 13px;
}

.loading-panel {
  padding: 12px;
  border-top: 1px solid #dfe5ee;
  background: #ffffff;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 0 10px;
  border-bottom: 1px solid #dfe5ee;
  background: #ffffff;
}

.result-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-title strong {
  overflow: hidden;
  color: #111827;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.back-button {
  flex: 0 0 auto;
}

.analysis-result-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border-left: 3px solid #16a34a;
  border-top: 1px solid #dfe5ee;
  background: #f0fdf4;
}

.analysis-result-card.is-fail {
  border-left-color: #dc2626;
  background: #fef2f2;
}

.result-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #15803d;
  font-size: 16px;
  line-height: 1.2;
}

.analysis-result-card.is-fail .result-status {
  color: #dc2626;
}

.result-status-icon {
  font-size: 22px;
}

.failure-list {
  margin: 0;
  padding-left: 22px;
  color: #7f1d1d;
  font-size: 13px;
  line-height: 1.7;
}

.summary-table-section {
  overflow: hidden;
}

.summary-table-section :deep(.el-table__header th) {
  background: #f8fafc;
  color: #111827;
  font-weight: 600;
}

.summary-table-section :deep(.el-table__body td:first-child) {
  background: #fbfdff;
  color: #475569;
  font-weight: 600;
}

.summary-table-section :deep(.el-table__cell) {
  padding: 8px 0;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.chart-panel-wide {
  grid-column: span 2;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid #dfe5ee;
}

.panel-header h2 {
  margin: 0;
  color: #303133;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0;
  white-space: nowrap;
}

.panel-title-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.panel-title-tools > * + * {
  margin-left: 0;
}

.trial-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.trial-controls > * + * {
  margin-left: 0;
}

.chart-mode-group {
  flex: 0 0 auto;
}

.chart-mode-button {
  min-width: 52px;
  padding-right: 10px;
  padding-left: 10px;
}

.trial-filter-select {
  width: 150px;
}

.channel-select {
  width: 132px;
}

.matrix-header-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.matrix-context {
  color: #64748b;
  font-size: 12px;
}

.matrix-spec-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.matrix-spec-strip span {
  padding: 3px 7px;
  border: 1px solid #dbe4f0;
  border-radius: 4px;
  color: #475569;
  background: #f8fafc;
  font-size: 12px;
  line-height: 1.2;
}

.matrix-table :deep(.el-table__cell) {
  transition: background-color 0.16s ease, color 0.16s ease;
}

.matrix-table :deep(.el-table__body td:first-child) {
  background: #fbfdff;
  color: #334155;
  font-weight: 600;
}

.single-channel-matrix-table :deep(.matrix-summary-row td) {
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
}

.matrix-cell-value {
  position: relative;
  z-index: 0;
  display: inline-flex;
  width: 100%;
  min-height: 20px;
  align-items: center;
  justify-content: center;
}

.matrix-cell-value.is-fail::before,
.matrix-cell-value.is-fail::after {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 52px;
  border-top: 1.5px dashed #991b1b;
  content: "";
  pointer-events: none;
  transform-origin: center;
}

.matrix-cell-value.is-fail::before {
  transform: translate(-50%, -50%) rotate(38deg);
}

.matrix-cell-value.is-fail::after {
  transform: translate(-50%, -50%) rotate(-38deg);
}

.chart {
  width: 100%;
  height: 300px;
}

.table-section :deep(.el-table__header th) {
  background: #f8fafc;
  color: #606266;
  font-weight: 600;
}

.table-section :deep(.el-table__cell .cell) {
  text-align: center;
}

.online-panel {
  min-height: calc(100vh - 58px);
  padding: 0;
  background: #ffffff;
}

.online-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #dfe5ee;
  margin-bottom: 0;
}

.online-select {
  width: 240px;
}

.online-product-select {
  width: 380px;
}

.online-test-select {
  width: 220px;
}

.online-sn-select {
  width: 300px;
}

.csv-link-editor {
  display: grid;
  gap: 8px;
}

.csv-link-hint {
  color: #667085;
  font-size: 12px;
}

.csv-link-button {
  flex: 0 0 auto;
}

.online-select :deep(.el-select__selected-item) {
  max-width: calc(100% - 28px);
}

.online-select :deep(.el-select__selected-item span) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.online-product-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.online-product-option span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
  color: #111827;
}

.online-product-option span:last-child {
  flex: 0 0 auto;
  color: #6b7280;
  font-size: 12px;
}

.spec-dialog-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.spec-select {
  width: 220px;
}

.spec-table :deep(.el-table__cell .cell) {
  text-align: center;
}

.spec-table :deep(.el-input-number) {
  width: 128px;
}

.spec-actions {
  margin-top: 10px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-meta span {
  padding: 4px 8px;
  border: 1px solid #dbe4f0;
  border-radius: 6px;
  color: #334155;
  background: #f8fafc;
  font-size: 12px;
}

.detail-stat-table {
  margin-bottom: 14px;
}

.detail-stat-table :deep(.el-table__cell .cell) {
  text-align: center;
}

.raw-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.raw-link {
  color: #2563eb;
  cursor: default;
  font-size: 13px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.raw-json {
  max-height: 420px;
  margin: 0;
  overflow: auto;
  color: #111827;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .upload-stage {
    min-height: calc(100vh - 96px);
    align-items: center;
    padding-bottom: 4vh;
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }

  .chart-panel-wide {
    grid-column: span 1;
  }

  .action-row {
    align-items: stretch;
    flex-direction: column;
  }

  .result-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .panel-header {
    align-items: stretch;
    flex-direction: column;
  }

  .panel-title-tools {
    align-items: stretch;
    flex-direction: column;
  }

  .trial-controls {
    justify-content: flex-start;
  }

  .action-buttons {
    width: 100%;
    justify-content: flex-start;
    margin-left: 0;
  }

  .result-select,
  .trial-filter-select,
  .online-select {
    width: 100%;
  }
}
</style>
