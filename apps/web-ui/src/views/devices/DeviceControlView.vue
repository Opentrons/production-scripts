<template>
  <div class="device-control-view">
    <section class="device-context" :class="{ 'is-batch': isBatchMode }">
      <template v-if="isBatchMode">
        <div class="device-identity">
          <div class="device-copy">
            <span class="device-name">{{ t('devices.workbench.batchProcessing') }}</span>
            <span class="device-ip">{{ t('devices.workbench.selectedDevices', { selected: selectedIps.length, total: availableRobots.length }) }}</span>
          </div>
        </div>

        <div class="device-meta">
          <span class="status-pill">{{ t('devices.workbench.multiSelect') }}</span>
          <span class="meta-item">{{ t('devices.workbench.availableDevices', { count: availableRobots.length }) }}</span>
        </div>
      </template>

      <template v-else>
        <div class="device-identity">
          <el-tooltip :content="t('devices.workbench.back')" placement="bottom">
            <el-button
              class="device-back-button"
              :icon="ArrowLeft"
              circle
              :aria-label="t('devices.workbench.back')"
              @click="returnToDeviceList"
            />
          </el-tooltip>
          <div class="device-copy">
            <span class="device-name">{{ currentDeviceName }}</span>
            <span class="device-address">
              <span class="inline-status" :class="currentServiceStatus">
                {{ formatServiceStatus(currentServiceStatus) }}
              </span>
              <span class="device-ip">{{ selectedIp || t('devices.workbench.noDeviceSelected') }}</span>
            </span>
          </div>
        </div>

        <div class="device-meta">
          <el-tooltip :content="t('devices.info')" placement="left">
            <el-button
              :icon="Tickets"
              circle
              :disabled="!selectedIp"
              @click="openInfoDrawer"
            />
          </el-tooltip>
          <el-tooltip :content="t('devices.refreshStatus')" placement="left">
            <el-button
              :icon="Refresh"
              :loading="refreshing"
              circle
              @click="refreshRobots"
            />
          </el-tooltip>
        </div>
      </template>
    </section>

    <div v-if="initialScanLoading" class="initial-device-loading">
      <el-icon class="is-loading initial-device-loading-icon"><Loading /></el-icon>
      <span>{{ t('devices.workbench.loadingScan') }}</span>
    </div>

    <section v-else class="workbench">
      <el-tabs
        v-model="activeTab"
        class="workbench-tabs"
        :before-leave="beforeTabLeave"
        @tab-change="handleTabChange"
      >
        <el-tab-pane :label="t('devices.workbench.tabs.control')" name="control" lazy>
          <DeviceControlPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.barcode')" name="barcode" lazy>
          <DeviceBarcodeProvisionPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="Protocol" name="protocol">
          <DeviceProtocolsPanel :ip="selectedIp" standalone />
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.files')" name="files">
          <DeviceFilesPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.testingData')" name="testing-data">
          <DeviceTestingDataPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.command')" name="command">
          <el-tabs v-model="singleCommandMode" class="command-mode-tabs" @tab-change="handleCommandModeChange">
            <el-tab-pane label="HTTP API" name="http">
              <section class="command-console">
                <div v-if="!selectedIp" class="panel-empty">
                  <el-empty :description="t('devices.selectOne')" />
                </div>

                <template v-else>
                  <div class="command-form-grid">
                    <label class="command-field http-command-preset-field">
                      <span>{{ t('devices.workbench.command.preset') }}</span>
                      <el-select
                        v-model="singleHttpCommandPresetId"
                        clearable
                        filterable
                        :placeholder="t('devices.workbench.command.presetPlaceholder')"
                        @change="applySingleHttpCommandPreset"
                      >
                        <el-option
                          v-for="preset in HTTP_COMMAND_PRESETS"
                          :key="preset.id"
                          :label="preset.name"
                          :value="preset.id"
                        />
                      </el-select>
                    </label>
                    <label class="command-field">
                      <span>{{ t('devices.workbench.command.method') }}</span>
                      <el-select v-model="singleCommandMethod">
                        <el-option label="GET" value="GET" />
                        <el-option label="POST" value="POST" />
                        <el-option label="PUT" value="PUT" />
                        <el-option label="DELETE" value="DELETE" />
                      </el-select>
                    </label>
                    <label class="command-field">
                      <span>OpenAPI Path</span>
                      <el-input v-model="singleCommandPath" placeholder="/health" />
                    </label>
                  </div>

                  <label class="command-field">
                    <span>Body JSON</span>
                    <el-input
                      v-model="singleCommandBody"
                      type="textarea"
                      :rows="8"
                      placeholder='{"data": {}}'
                    />
                  </label>

                  <div class="command-actions-row">
                    <el-button
                      type="primary"
                      :loading="singleCommandRunning"
                      :disabled="!canRunSingleCommand"
                      @click="runSingleCommand"
                    >
                      {{ t('devices.workbench.command.execute') }}
                    </el-button>
                    <el-button
                      v-if="singleCommandResult"
                      :disabled="singleCommandRunning"
                      @click="singleCommandResult = null"
                    >
                      {{ t('devices.workbench.command.clearResult') }}
                    </el-button>
                  </div>

                  <div
                    v-if="singleCommandResult"
                    class="command-result"
                    :class="{ 'is-error': !singleCommandResult.success }"
                  >
                    <div class="command-result-header">
                      <span>{{ singleCommandResult.method }} {{ singleCommandResult.path }}</span>
                      <el-tag size="small" :type="singleCommandResult.success ? 'success' : 'danger'">
                        {{ t(singleCommandResult.success ? 'common.status.completed' : 'common.status.error') }}
                      </el-tag>
                    </div>
                    <pre class="command-result-body">{{ singleCommandResultText }}</pre>
                  </div>
                </template>
              </section>
            </el-tab-pane>

            <el-tab-pane label="SSH COMMAND" name="ssh">
              <section class="ssh-command-workspace">
                <div v-if="!selectedIp" class="panel-empty">
                  <el-empty :description="t('devices.selectOne')" />
                </div>

                <template v-else>
                  <el-alert
                    v-if="sshCommandDatabaseError"
                    class="ssh-command-alert"
                    type="warning"
                    :closable="false"
                    :title="t('devices.workbench.command.unavailable', { error: sshCommandDatabaseError })"
                  />

                  <div class="ssh-command-settings">
                    <label class="command-field">
                      <span>{{ t('devices.workbench.command.commonCustom') }}</span>
                      <el-select
                        v-model="selectedSshCommandId"
                        class="ssh-command-preset-select"
                        filterable
                        clearable
                        :loading="sshCommandsLoading"
                        popper-class="ssh-command-select-popper"
                        :placeholder="t('devices.workbench.command.commandPlaceholder')"
                        @change="applySelectedSshCommand"
                      >
                        <el-option-group :label="t('devices.workbench.command.builtin')">
                          <el-option
                            v-for="item in builtinSshCommands"
                            :key="item.id"
                            :label="item.name"
                            :value="item.id"
                          >
                            <div class="ssh-command-option">
                              <span class="ssh-command-option-name">{{ item.name }}</span>
                              <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                {{ item.tag }}
                              </el-tag>
                            </div>
                          </el-option>
                        </el-option-group>
                        <el-option-group v-if="customSshCommands.length" :label="t('devices.workbench.command.custom')">
                          <el-option
                            v-for="item in customSshCommands"
                            :key="item.id"
                            :label="item.name"
                            :value="item.id"
                          >
                            <div class="ssh-command-option">
                              <span class="ssh-command-option-name">{{ item.name }}</span>
                              <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                {{ item.tag }}
                              </el-tag>
                            </div>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </label>
                    <label class="command-field ssh-timeout-field">
                      <span>{{ t('devices.workbench.command.timeout') }}</span>
                      <el-input-number v-model="sshCommandTimeout" :min="1" :max="300" controls-position="right" />
                    </label>
                  </div>

                  <label class="command-field">
                    <span class="command-field-title">
                      {{ t('devices.workbench.command.ssh') }}
                      <small>{{ t('devices.workbench.command.sshHint') }}</small>
                    </span>
                    <el-input
                      v-model="sshCommandText"
                      type="textarea"
                      :rows="5"
                      :placeholder="t('devices.workbench.command.sshPlaceholder')"
                      @keydown.ctrl.enter.prevent="runSshCommand"
                    />
                  </label>

                  <div class="command-actions-row">
                    <el-button
                      type="primary"
                      :loading="sshCommandRunning"
                      :disabled="!canRunSshCommand"
                      @click="runSshCommand"
                    >
                      {{ t('devices.workbench.command.executeSsh') }}
                    </el-button>
                    <el-button
                      v-if="sshCommandResult || sshCommandExecutionError"
                      :disabled="sshCommandRunning"
                      @click="clearSshCommandOutput"
                    >
                      {{ t('devices.workbench.command.clearOutput') }}
                    </el-button>
                    <span class="command-shortcut">{{ t('devices.workbench.command.shortcut') }}</span>
                  </div>

                  <div
                    v-if="sshCommandResult"
                    class="command-result ssh-command-result"
                    :class="{ 'is-error': !sshCommandResult.success }"
                  >
                    <div class="command-result-header">
                      <div class="ssh-result-heading">
                        <span>{{ sshCommandResult.ip }} ·</span>
                        <el-tooltip
                          :content="sshCommandResult.command"
                          placement="top"
                          popper-class="ssh-command-full-tooltip"
                          :show-after="400"
                        >
                          <span class="ssh-result-command">{{ sshCommandResult.command }}</span>
                        </el-tooltip>
                      </div>
                      <el-tag size="small" :type="sshCommandResult.success ? 'success' : 'danger'">
                        {{ sshCommandResult.success ? t('devices.workbench.command.executeSuccess') : t('devices.workbench.command.exitCode', { code: sshCommandResult.exit_code }) }}
                      </el-tag>
                    </div>
                    <div class="ssh-result-meta">
                      <span>{{ t('devices.workbench.command.exitCode', { code: sshCommandResult.exit_code }) }}</span>
                      <span>{{ t('devices.workbench.command.duration', { duration: sshCommandResult.duration_ms }) }}</span>
                      <span>{{ t('devices.workbench.command.completedAt', { time: formatLogDate(sshCommandResult.finished_at) }) }}</span>
                      <span>
                        {{ t('devices.workbench.command.serverDate', { date: sshCommandResult.environment?.DATE }) }}
                        <template v-if="sshCommandResult.environment?.DATE_TIMEZONE">
                          （{{ sshCommandResult.environment.DATE_TIMEZONE }}）
                        </template>
                      </span>
                      <span v-if="sshCommandResult.output_truncated">{{ t('devices.workbench.command.truncated') }}</span>
                    </div>
                    <div class="ssh-output-section">
                      <div class="ssh-output-title">{{ t('devices.workbench.command.stdout') }}</div>
                      <pre class="command-result-body">{{ sshCommandResult.stdout || t('devices.workbench.command.noOutput') }}</pre>
                    </div>
                    <div v-if="sshCommandResult.stderr" class="ssh-output-section is-stderr">
                      <div class="ssh-output-title">{{ t('devices.workbench.command.stderr') }}</div>
                      <pre class="command-result-body">{{ sshCommandResult.stderr }}</pre>
                    </div>
                  </div>
                  <div v-else-if="sshCommandExecutionError" class="command-result is-error">
                    <div class="command-result-header">
                      <div class="ssh-result-heading">
                        <span>{{ selectedIp }} ·</span>
                        <el-tooltip
                          :content="sshCommandText"
                          placement="top"
                          popper-class="ssh-command-full-tooltip"
                          :show-after="400"
                        >
                          <span class="ssh-result-command">{{ sshCommandText }}</span>
                        </el-tooltip>
                      </div>
                      <el-tag size="small" type="danger">{{ t('devices.workbench.command.connectionFailed') }}</el-tag>
                    </div>
                    <pre class="command-result-body">{{ sshCommandExecutionError }}</pre>
                  </div>

                  <section class="custom-command-section">
                    <div class="custom-command-header">
                      <div>
                        <h3>{{ t('devices.workbench.command.custom') }}</h3>
                        <p>{{ t('devices.workbench.command.customDescription') }}</p>
                      </div>
                      <el-button
                        type="primary"
                        plain
                        :disabled="Boolean(sshCommandDatabaseError)"
                        @click="openCreateSshCommand"
                      >
                        {{ t('devices.workbench.command.addCommand') }}
                      </el-button>
                    </div>

                    <el-table
                      v-loading="sshCommandsLoading"
                      :data="customSshCommands"
                      border
                      :empty-text="t('devices.workbench.command.noCustom')"
                    >
                      <el-table-column prop="name" :label="t('devices.workbench.command.name')" min-width="150" />
                      <el-table-column :label="t('devices.workbench.command.property')" width="90">
                        <template #default="scope">
                          <el-tag size="small" :type="scope.row.tag === 'risk' ? 'danger' : 'info'">
                            {{ scope.row.tag }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="command" :label="t('devices.workbench.command.command')" min-width="260" show-overflow-tooltip />
                      <el-table-column prop="description" :label="t('devices.workbench.command.description')" min-width="180" show-overflow-tooltip />
                      <el-table-column :label="t('devices.workbench.command.updatedAt')" width="180">
                        <template #default="scope">
                          {{ formatLogDate(scope.row.updated_at) }}
                        </template>
                      </el-table-column>
                      <el-table-column :label="t('devices.workbench.command.action')" width="130" fixed="right">
                        <template #default="scope">
                          <el-button link type="primary" @click="openEditSshCommand(scope.row)">{{ t('common.actions.edit') }}</el-button>
                          <el-button link type="danger" @click="removeSshCommand(scope.row)">{{ t('common.actions.delete') }}</el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </section>
                </template>
              </section>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.versions')" name="versions">
          <el-tabs
            v-model="versionQueryTab"
            class="version-query-tabs"
            @tab-change="handleVersionQueryTabChange"
          >
            <el-tab-pane :label="t('devices.workbench.tabs.subsystems')" name="subsystems">
              <section class="subsystem-version-workspace">
            <div v-if="!selectedIp" class="panel-empty">
              <el-empty :description="t('devices.selectOne')" />
            </div>

            <template v-else>
              <div class="subsystem-version-toolbar">
                <div class="subsystem-version-heading">
                  <span>{{ t('devices.workbench.versions.testVersion') }}</span>
                  <span class="subsystem-version-separator" aria-hidden="true">.</span>
                  <el-tooltip
                    :content="subsystemTestVersion"
                    :disabled="subsystemTestVersionLabel === subsystemTestVersion"
                    placement="top"
                  >
                    <code class="subsystem-test-version">{{ subsystemTestVersionLabel }}</code>
                  </el-tooltip>
                </div>
                <div class="subsystem-version-actions">
                  <el-button
                    type="primary"
                    :icon="Plus"
                    @click="openVersionCaptureDialog"
                  >{{ t('devices.workbench.versions.add') }}</el-button>
                  <el-button
                    type="primary"
                    plain
                    :icon="Refresh"
                    :loading="subsystemVersionsLoading"
                    @click="loadSubsystemVersions"
                  >{{ t('common.actions.refresh') }}</el-button>
                </div>
              </div>

              <el-alert
                v-if="subsystemVersionsError"
                type="error"
                :closable="false"
                :title="subsystemVersionsError"
                class="subsystem-version-alert"
              />

              <el-table
                v-loading="subsystemVersionsLoading"
                :data="subsystemVersionRows"
                border
                stripe
                :empty-text="t('devices.workbench.versions.noSubsystems')"
              >
                <el-table-column prop="name" :label="t('devices.workbench.versions.subsystem')" min-width="150" />
                <el-table-column prop="currentVersion" :label="t('devices.workbench.versions.current')" min-width="120" />
                <el-table-column prop="nextVersion" :label="t('devices.workbench.versions.target')" min-width="120" />
                <el-table-column prop="revision" label="Revision" min-width="110" />
                <el-table-column :label="t('devices.workbench.versions.status')" width="100">
                  <template #default="scope">
                    <el-tag size="small" :type="subsystemStatusType(scope.row.ok)">
                      {{ subsystemStatusLabel(scope.row.ok) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="t('devices.workbench.versions.firmwareUpdate')" width="120">
                  <template #default="scope">
                    <el-tag size="small" :type="subsystemUpdateType(scope.row.updateNeeded)">
                      {{ subsystemUpdateLabel(scope.row.updateNeeded) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column :label="t('devices.workbench.versions.queriedAt')" min-width="180">
                  <template #default="scope">
                    {{ formatLogDate(scope.row.queriedAt) }}
                  </template>
                </el-table-column>
              </el-table>
            </template>
              </section>
            </el-tab-pane>

            <el-tab-pane :label="t('devices.workbench.tabs.history')" name="history">
              <section class="version-history-workspace">
            <div class="subsystem-version-toolbar">
              <div class="subsystem-version-heading">
                <h2>{{ t('devices.workbench.versions.historyTitle') }}</h2>
                <span>{{ t('devices.workbench.versions.productCount', { count: versionHistoryTotal }) }}</span>
              </div>
              <el-button
                type="primary"
                plain
                :icon="Refresh"
                :loading="versionHistoryLoading"
                @click="loadVersionHistory"
              >{{ t('common.actions.refresh') }}</el-button>
            </div>

            <el-alert
              v-if="versionHistoryError"
              type="error"
              :closable="false"
              :title="versionHistoryError"
              class="subsystem-version-alert"
            />

            <el-table
              v-loading="versionHistoryLoading"
              :data="versionHistoryRows"
              border
              stripe
              :empty-text="t('devices.workbench.versions.noHistory')"
            >
              <el-table-column prop="productName" :label="t('devices.workbench.versions.product')" min-width="210" show-overflow-tooltip />
              <el-table-column prop="barcode" :label="t('devices.workbench.versions.barcode')" min-width="180" show-overflow-tooltip />
              <el-table-column prop="testName" :label="t('devices.workbench.versions.testProcess')" min-width="280" show-overflow-tooltip />
              <el-table-column prop="testVersion" :label="t('devices.workbench.versions.testVersion')" min-width="150" show-overflow-tooltip />
              <el-table-column prop="versionSummary" :label="t('devices.workbench.versions.versionInfo')" min-width="320" show-overflow-tooltip />
              <el-table-column prop="robotIp" :label="t('devices.workbench.versions.deviceIp')" width="140" />
              <el-table-column :label="t('devices.workbench.versions.queriedAt')" width="180">
                <template #default="scope">
                  {{ formatLogDate(scope.row.queriedAt) }}
                </template>
              </el-table-column>
            </el-table>
              </section>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.codeFlash')" name="code-flash" lazy>
          <DeviceCodeFlashPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.logs')" name="device-logs">
          <section class="single-operation-panel">
            <div v-if="!selectedIp" class="panel-empty">
              <el-empty :description="t('devices.selectOne')" />
            </div>

            <template v-else>
              <el-tabs v-model="singleLogViewTab" class="log-view-tabs">
                <el-tab-pane :label="t('devices.workbench.logs.select')" name="select">
              <div class="log-download-intro">
                <div>
                  <div class="log-section-title">{{ t('devices.workbench.logs.currentTitle') }}</div>
                  <div class="log-section-description">
                    {{ t('devices.workbench.logs.description') }}
                  </div>
                </div>
                <div v-if="logDownloadRoot" class="log-root-path">{{ logDownloadRoot }}</div>
              </div>

              <div v-loading="logOptionsLoading" class="log-option-section">
                <div class="log-option-heading">
                  <span>{{ t('devices.workbench.logs.selectFolders') }}</span>
                  <el-button size="small" text @click="toggleAllLogFolders">
                    {{ t(areAllLogFoldersSelected ? 'devices.workbench.logs.clearAll' : 'devices.workbench.logs.selectAll') }}
                  </el-button>
                </div>
                <el-checkbox-group v-model="selectedLogFolderKeys" class="log-folder-grid">
                  <el-checkbox
                    v-for="folder in logFolderOptions"
                    :key="`single-log-${folder.key}`"
                    :value="folder.key"
                    class="log-folder-option"
                  >
                    <span class="log-folder-copy">
                      <strong>{{ folder.label }}</strong>
                      <small>{{ folder.description }}</small>
                    </span>
                  </el-checkbox>
                </el-checkbox-group>
              </div>

              <div class="log-run-settings">
                <div class="log-thread-summary">
                  <span>{{ currentDeviceName }}</span>
                  <span>{{ selectedIp }}</span>
                </div>
                <el-button
                  type="primary"
                  :loading="singleLogTaskStarting"
                  :disabled="!canStartSingleLogDownload"
                  @click="startSingleLogDownload"
                >
                  {{ t('devices.workbench.logs.start') }}
                </el-button>
              </div>

              <section v-if="singleActiveLogTask" class="log-progress-panel">
                <div class="log-progress-header">
                  <div>
                    <div class="log-section-title">{{ t('devices.workbench.logs.progress') }}</div>
                    <div class="log-section-description">
                      {{ t('devices.workbench.logs.completed', { completed: singleActiveLogTask.completed_devices, total: singleActiveLogTask.total_devices }) }}
                    </div>
                  </div>
                  <el-tag :type="getLogStatusTagType(singleActiveLogTask.status)">
                    {{ getLogStatusLabel(singleActiveLogTask.status) }}
                  </el-tag>
                </div>
                <el-progress
                  :percentage="singleActiveLogTask.progress"
                  :status="getLogTaskProgressStatus(singleActiveLogTask)"
                  :stroke-width="12"
                />
                <div class="log-task-stats">
                  <span>{{ t('devices.workbench.logs.success', { count: singleActiveLogTask.successful_devices }) }}</span>
                  <span>{{ t('devices.workbench.logs.warning', { count: singleActiveLogTask.warning_devices || 0 }) }}</span>
                  <span>{{ t('devices.workbench.logs.failed', { count: singleActiveLogTask.failed_devices }) }}</span>
                </div>

                <div class="log-device-progress-list">
                  <article
                    v-for="device in singleActiveLogTask.devices"
                    :key="`single-${device._id}`"
                    class="log-device-progress-item"
                  >
                    <div class="log-device-progress-head">
                      <div>
                        <strong>{{ device.device_name }}</strong>
                        <small>{{ device.robot_ip }}</small>
                      </div>
                      <el-tag size="small" :type="getLogStatusTagType(device.status)">
                        {{ getLogStatusLabel(device.status) }}
                      </el-tag>
                    </div>
                    <el-progress
                      :percentage="device.progress"
                      :status="getRecordProgressStatus(device)"
                      :stroke-width="8"
                    />
                    <div
                      class="log-device-step"
                      :class="{
                        'is-error': device.status === 'failed',
                        'is-warning': device.status === 'warning'
                      }"
                    >
                      {{ device.error || device.cleanup_error || device.current_step }}
                    </div>
                    <div v-if="device.command_logs?.length" class="log-command-console">
                      <div class="log-command-console-title">{{ t('devices.workbench.logs.liveCommands') }}</div>
                      <article
                        v-for="commandLog in getDisplayCommandLogs(device.command_logs)"
                        :key="`single-${commandLog.id}`"
                        class="log-command-entry"
                      >
                        <div class="log-command-meta">
                          <span>{{ formatCommandTime(commandLog.started_at) }} · {{ commandLog.label }}</span>
                          <el-tag size="small" :type="getCommandStatusTagType(commandLog.status)">
                            {{ getCommandStatusLabel(commandLog.status) }}
                          </el-tag>
                        </div>
                        <pre class="log-command-content">{{ commandLog.command }}</pre>
                        <pre v-if="commandLog.output" class="log-command-output">{{ commandLog.output }}</pre>
                        <pre v-if="commandLog.error" class="log-command-output is-error">{{ commandLog.error }}</pre>
                      </article>
                    </div>
                  </article>
                </div>
              </section>
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.logs.records')" name="records" lazy>
                  <DeviceLogHistoryPanel :robot-ip="selectedIp" />
                </el-tab-pane>
              </el-tabs>
            </template>
          </section>
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.sshKeys')" name="ssh-keys">
          <section class="single-operation-panel">
            <div v-if="!selectedIp" class="panel-empty">
              <el-empty :description="t('devices.selectOne')" />
            </div>

            <template v-else>
              <div class="ssh-key-install-intro">
                <div>
                  <div class="log-section-title">{{ t('devices.workbench.sshKeys.currentTitle') }}</div>
                  <div class="log-section-description">
                    {{ t('devices.workbench.sshKeys.currentDescription', { ip: selectedIp }) }}
                  </div>
                </div>
                <el-tag type="warning" effect="plain">{{ t('devices.workbench.sshKeys.usbRequired') }}</el-tag>
              </div>

              <div class="ssh-key-install-settings is-single">
                <label class="batch-field">
                  <span>{{ t('devices.workbench.sshKeys.timeout') }}</span>
                  <el-input-number
                    v-model="singleSshKeyInstallTimeout"
                    :min="1"
                    :max="300"
                    controls-position="right"
                  />
                </label>
                <div class="ssh-key-install-summary">
                  <strong>{{ currentDeviceName }}</strong>
                  <span>{{ selectedIp }}</span>
                </div>
              </div>

              <div class="batch-actions-row">
                <el-button
                  type="primary"
                  :loading="singleSshKeyInstallRunning"
                  :disabled="!canInstallSingleSshKey"
                  @click="runSingleSshKeyInstall"
                >
                  {{ t('devices.workbench.sshKeys.install') }}
                </el-button>
                <el-button
                  v-if="singleSshKeyInstallResult"
                  :disabled="singleSshKeyInstallRunning"
                  @click="singleSshKeyInstallResult = null"
                >
                  {{ t('devices.workbench.command.clearResult') }}
                </el-button>
              </div>

              <article
                v-if="singleSshKeyInstallResult"
                class="command-result batch-ssh-result single-ssh-key-result"
                :class="{ 'is-error': !singleSshKeyInstallResult.success }"
              >
                <div class="command-result-header">
                  <div class="batch-ssh-device-heading">
                    <span>{{ getRobotDisplayName(singleSshKeyInstallResult.ip) }}</span>
                    <span>{{ singleSshKeyInstallResult.ip }}</span>
                  </div>
                  <el-tag size="small" :type="singleSshKeyInstallResult.success ? 'success' : 'danger'">
                    {{ t(singleSshKeyInstallResult.success ? 'devices.workbench.sshKeys.installed' : 'devices.workbench.sshKeys.failed') }}
                  </el-tag>
                </div>
                <div
                  class="ssh-key-result-message"
                  :class="{ 'is-error': !singleSshKeyInstallResult.success }"
                >
                  {{ singleSshKeyInstallResult.message }}
                </div>
                <div class="ssh-result-meta">
                  <span>{{ t('devices.workbench.command.exitCode', { code: singleSshKeyInstallResult.exit_code ?? '-' }) }}</span>
                  <span>{{ t('devices.workbench.command.duration', { duration: singleSshKeyInstallResult.duration_ms }) }}</span>
                </div>
                <div v-if="singleSshKeyInstallResult.stdout" class="ssh-output-section">
                  <div class="ssh-output-title">{{ t('devices.workbench.sshKeys.scriptOutput') }}</div>
                  <pre class="command-result-body">{{ singleSshKeyInstallResult.stdout }}</pre>
                </div>
                <div v-if="singleSshKeyInstallResult.stderr" class="ssh-output-section is-stderr">
                  <div class="ssh-output-title">{{ t('devices.workbench.sshKeys.errorOutput') }}</div>
                  <pre class="command-result-body">{{ singleSshKeyInstallResult.stderr }}</pre>
                </div>
              </article>
            </template>
          </section>
        </el-tab-pane>

        <el-tab-pane :label="t('devices.workbench.tabs.batch')" name="batch">
          <div class="batch-workspace">
            <aside class="batch-device-panel">
              <div class="batch-panel-header">
                <span class="panel-title">{{ t('devices.workbench.batch.targets') }}</span>
                <span class="device-count">{{ availableRobots.length }}</span>
                <el-button
                  type="primary"
                  size="small"
                  link
                  @click="toggleSelectAll"
                >
                  {{ t(isAllSelected ? 'devices.workbench.logs.clearAll' : 'devices.workbench.logs.selectAll') }}
                </el-button>
              </div>

              <div class="manual-ip">
                <el-input
                  v-model="manualIpInput"
                  :placeholder="t('devices.workbench.batch.ipPlaceholder')"
                  size="small"
                  @keyup.enter="addManualIp"
                />
                <el-button size="small" type="primary" @click="addManualIp">{{ t('common.actions.add') }}</el-button>
              </div>

              <el-checkbox-group
                v-if="availableRobots.length"
                v-model="selectedIps"
                class="batch-device-list"
              >
                <el-checkbox
                  v-for="robot in availableRobots"
                  :key="robot.ip"
                  :value="robot.ip"
                  class="batch-device-option"
                >
                  <span class="batch-device-name">{{ robot.name || t('devices.unnamed') }}</span>
                  <span class="batch-device-ip">{{ robot.ip }}</span>
                  <span class="batch-device-status" :class="robot.service_status">
                    {{ formatServiceStatus(robot.service_status) }}
                  </span>
                </el-checkbox>
              </el-checkbox-group>

              <el-empty v-else :description="t('common.empty')" :image-size="72" />
            </aside>

            <section class="batch-command-panel">
              <div class="batch-topbar">
                <div class="batch-summary">
                  <span class="summary-value">{{ selectedIps.length }}</span>
                  <span class="summary-label">{{ t('devices.workbench.batch.selected') }}</span>
                </div>
                <el-button
                  v-if="batchResults.length"
                  size="small"
                  text
                  @click="batchResults = []"
                >
                  {{ t('devices.workbench.command.clearResult') }}
                </el-button>
              </div>

              <el-tabs v-model="batchActionTab" class="batch-action-tabs">
                <el-tab-pane :label="t('devices.workbench.batch.editFile')" name="edit">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.batch.reference') }}</span>
                      <el-select v-model="batchReferenceIp" :placeholder="t('devices.workbench.batch.selectReference')">
                        <el-option
                          v-for="robot in selectedRobots"
                          :key="`ref-${robot.ip}`"
                          :label="`${robot.name || robot.ip} · ${robot.ip}`"
                          :value="robot.ip"
                        />
                      </el-select>
                    </label>
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.batch.filePath') }}</span>
                      <el-input v-model="batchEditPath" placeholder="/data/file.json" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button :loading="batchReading" :disabled="!canReadBatchFile" @click="readBatchFile">
                      {{ t('devices.workbench.batch.openFile') }}
                    </el-button>
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canWriteBatchFile"
                      @click="runBatchEditReplace"
                    >
                      {{ t('devices.workbench.batch.saveReplace') }}
                    </el-button>
                  </div>
                  <el-input
                    v-model="batchEditContent"
                    class="batch-editor"
                    type="textarea"
                    :rows="14"
                    :placeholder="t('devices.workbench.batch.editorPlaceholder')"
                  />
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.batch.uploadFile')" name="upload">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.batch.targetPath') }}</span>
                      <el-input v-model="batchUploadPath" placeholder="/data/config.json" />
                    </label>
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.batch.localFile') }}</span>
                      <input class="native-file-input" type="file" @change="handleBatchUploadFileChange" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchUpload"
                      @click="runBatchUpload"
                    >
                      {{ t('devices.workbench.batch.batchUpload') }}
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.batch.downloadFile')" name="download">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.batch.remotePath') }}</span>
                      <el-input v-model="batchDownloadPath" placeholder="/data or /data/file.csv" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchDownload"
                      @click="runBatchDownload"
                    >
                      {{ t('devices.workbench.batch.batchDownload') }}
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.tabs.logs')" name="logs">
                  <el-tabs v-model="logViewTab" class="log-view-tabs">
                    <el-tab-pane :label="t('devices.workbench.logs.select')" name="select">
                      <div class="log-download-intro">
                        <div>
                          <div class="log-section-title">{{ t('devices.workbench.logs.batchTitle') }}</div>
                          <div class="log-section-description">
                            {{ t('devices.workbench.logs.description') }}
                          </div>
                        </div>
                        <div v-if="logDownloadRoot" class="log-root-path">{{ logDownloadRoot }}</div>
                      </div>

                      <div v-loading="logOptionsLoading" class="log-option-section">
                        <div class="log-option-heading">
                          <span>{{ t('devices.workbench.logs.selectFolders') }}</span>
                          <el-button size="small" text @click="toggleAllLogFolders">
                            {{ t(areAllLogFoldersSelected ? 'devices.workbench.logs.clearAll' : 'devices.workbench.logs.selectAll') }}
                          </el-button>
                        </div>
                        <el-checkbox-group v-model="selectedLogFolderKeys" class="log-folder-grid">
                          <el-checkbox
                            v-for="folder in logFolderOptions"
                            :key="folder.key"
                            :value="folder.key"
                            class="log-folder-option"
                          >
                            <span class="log-folder-copy">
                              <strong>{{ folder.label }}</strong>
                              <small>{{ folder.description }}</small>
                            </span>
                          </el-checkbox>
                        </el-checkbox-group>
                      </div>

                      <div class="log-run-settings">
                        <label class="batch-field">
                          <span>{{ t('devices.workbench.logs.concurrency') }}</span>
                          <el-input-number
                            v-model="logConcurrency"
                            :min="1"
                            :max="logMaxConcurrency"
                            controls-position="right"
                          />
                        </label>
                        <div class="log-thread-summary">
                          <span>{{ t('devices.workbench.logs.deviceCount', { count: selectedIps.length }) }}</span>
                          <span>{{ t('devices.workbench.logs.maxThreads', { count: effectiveLogConcurrency }) }}</span>
                        </div>
                        <el-button
                          type="primary"
                          :loading="logTaskStarting"
                          :disabled="!canStartLogDownload"
                          @click="startLogDownload"
                        >
                          {{ t('devices.workbench.logs.start') }}
                        </el-button>
                      </div>

                      <section v-if="activeLogTask" class="log-progress-panel">
                        <div class="log-progress-header">
                          <div>
                            <div class="log-section-title">{{ t('devices.workbench.logs.batchProgress') }}</div>
                            <div class="log-section-description">
                              {{ t('devices.workbench.logs.runningThreads', { completed: activeLogTask.completed_devices, total: activeLogTask.total_devices, workers: activeLogTask.active_workers }) }}
                            </div>
                          </div>
                          <el-tag :type="getLogStatusTagType(activeLogTask.status)">
                            {{ getLogStatusLabel(activeLogTask.status) }}
                          </el-tag>
                        </div>
                        <el-progress
                          :percentage="activeLogTask.progress"
                          :status="getLogTaskProgressStatus(activeLogTask)"
                          :stroke-width="12"
                        />
                        <div class="log-task-stats">
                          <span>{{ t('devices.workbench.logs.success', { count: activeLogTask.successful_devices }) }}</span>
                          <span>{{ t('devices.workbench.logs.warning', { count: activeLogTask.warning_devices || 0 }) }}</span>
                          <span>{{ t('devices.workbench.logs.failed', { count: activeLogTask.failed_devices }) }}</span>
                          <span>{{ t('devices.workbench.logs.concurrent', { count: activeLogTask.concurrency || '-' }) }}</span>
                        </div>

                        <div class="log-device-progress-list">
                          <article
                            v-for="device in activeLogTask.devices"
                            :key="device._id"
                            class="log-device-progress-item"
                          >
                            <div class="log-device-progress-head">
                              <div>
                                <strong>{{ device.device_name }}</strong>
                                <small>{{ device.robot_ip }}</small>
                              </div>
                              <el-tag size="small" :type="getLogStatusTagType(device.status)">
                                {{ getLogStatusLabel(device.status) }}
                              </el-tag>
                            </div>
                            <el-progress
                              :percentage="device.progress"
                              :status="getRecordProgressStatus(device)"
                              :stroke-width="8"
                            />
                            <div
                              class="log-device-step"
                              :class="{
                                'is-error': device.status === 'failed',
                                'is-warning': device.status === 'warning'
                              }"
                            >
                              {{ device.error || device.cleanup_error || device.current_step }}
                            </div>
                            <div v-if="device.command_logs?.length" class="log-command-console">
                              <div class="log-command-console-title">{{ t('devices.workbench.logs.liveCommands') }}</div>
                              <article
                                v-for="commandLog in getDisplayCommandLogs(device.command_logs)"
                                :key="commandLog.id"
                                class="log-command-entry"
                              >
                                <div class="log-command-meta">
                                  <span>{{ formatCommandTime(commandLog.started_at) }} · {{ commandLog.label }}</span>
                                  <el-tag size="small" :type="getCommandStatusTagType(commandLog.status)">
                                    {{ getCommandStatusLabel(commandLog.status) }}
                                  </el-tag>
                                </div>
                                <pre class="log-command-content">{{ commandLog.command }}</pre>
                                <pre v-if="commandLog.output" class="log-command-output">{{ commandLog.output }}</pre>
                                <pre v-if="commandLog.error" class="log-command-output is-error">{{ commandLog.error }}</pre>
                              </article>
                            </div>
                          </article>
                        </div>
                      </section>
                    </el-tab-pane>

                    <el-tab-pane :label="t('devices.workbench.logs.records')" name="records" lazy>
                      <DeviceLogHistoryPanel />
                    </el-tab-pane>
                  </el-tabs>
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.tabs.command')" name="command">
                  <el-tabs
                    v-model="batchCommandMode"
                    class="batch-command-mode-tabs"
                    @tab-change="handleBatchCommandModeChange"
                  >
                    <el-tab-pane label="HTTP API" name="http">
                      <div class="batch-form-grid">
                        <label class="batch-field http-command-preset-field">
                          <span>{{ t('devices.workbench.command.preset') }}</span>
                          <el-select
                            v-model="batchHttpCommandPresetId"
                            clearable
                            filterable
                            :placeholder="t('devices.workbench.command.presetPlaceholder')"
                            @change="applyBatchHttpCommandPreset"
                          >
                            <el-option
                              v-for="preset in HTTP_COMMAND_PRESETS"
                              :key="preset.id"
                              :label="preset.name"
                              :value="preset.id"
                            />
                          </el-select>
                        </label>
                        <label class="batch-field">
                          <span>{{ t('devices.workbench.command.method') }}</span>
                          <el-select v-model="batchCommandMethod">
                            <el-option label="GET" value="GET" />
                            <el-option label="POST" value="POST" />
                            <el-option label="PUT" value="PUT" />
                            <el-option label="DELETE" value="DELETE" />
                          </el-select>
                        </label>
                        <label class="batch-field">
                          <span>OpenAPI Path</span>
                          <el-input v-model="batchCommandPath" placeholder="/health" />
                        </label>
                      </div>
                      <label class="batch-field">
                        <span>Body JSON</span>
                        <el-input
                          v-model="batchCommandBody"
                          type="textarea"
                          :rows="8"
                          placeholder='{"data": {}}'
                        />
                      </label>
                      <div class="batch-actions-row">
                        <el-button
                          type="primary"
                          :loading="batchRunning"
                          :disabled="!canBatchCommand"
                          @click="runBatchCommand"
                        >
                          {{ t('devices.workbench.batch.executeHttp') }}
                        </el-button>
                      </div>
                    </el-tab-pane>

                    <el-tab-pane label="SSH COMMAND" name="ssh">
                      <el-alert
                        v-if="sshCommandDatabaseError"
                        class="ssh-command-alert"
                        type="warning"
                        :closable="false"
                        :title="t('devices.workbench.command.unavailable', { error: sshCommandDatabaseError })"
                      />

                      <div class="batch-ssh-settings">
                        <label class="batch-field batch-ssh-command-select">
                          <span>{{ t('devices.workbench.command.commonCustom') }}</span>
                          <el-select
                            v-model="batchSshSelectedCommandId"
                            class="ssh-command-preset-select"
                            filterable
                            clearable
                            :loading="sshCommandsLoading"
                            popper-class="ssh-command-select-popper"
                            :placeholder="t('devices.workbench.command.commandPlaceholder')"
                            @change="applySelectedBatchSshCommand"
                          >
                            <el-option-group :label="t('devices.workbench.command.builtin')">
                              <el-option
                                v-for="item in builtinSshCommands"
                                :key="item.id"
                                :label="item.name"
                                :value="item.id"
                              >
                                <div class="ssh-command-option">
                                  <span class="ssh-command-option-name">{{ item.name }}</span>
                                  <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                    {{ item.tag }}
                                  </el-tag>
                                </div>
                              </el-option>
                            </el-option-group>
                            <el-option-group v-if="customSshCommands.length" :label="t('devices.workbench.command.custom')">
                              <el-option
                                v-for="item in customSshCommands"
                                :key="item.id"
                                :label="item.name"
                                :value="item.id"
                              >
                                <div class="ssh-command-option">
                                  <span class="ssh-command-option-name">{{ item.name }}</span>
                                  <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                    {{ item.tag }}
                                  </el-tag>
                                </div>
                              </el-option>
                            </el-option-group>
                          </el-select>
                        </label>
                        <label class="batch-field">
                          <span>{{ t('devices.workbench.sshKeys.timeout') }}</span>
                          <el-input-number v-model="batchSshTimeout" :min="1" :max="300" controls-position="right" />
                        </label>
                        <label class="batch-field">
                          <span>{{ t('devices.workbench.sshKeys.concurrency') }}</span>
                          <el-input-number v-model="batchSshConcurrency" :min="1" :max="20" controls-position="right" />
                        </label>
                      </div>

                      <label class="batch-field">
                        <span class="command-field-title">
                          {{ t('devices.workbench.command.ssh') }}
                          <small>{{ t('devices.workbench.command.batchHint', { count: selectedIps.length }) }}</small>
                        </span>
                        <el-input
                          v-model="batchSshCommandText"
                          type="textarea"
                          :rows="6"
                          :placeholder="t('devices.workbench.command.batchPlaceholder')"
                          @keydown.ctrl.enter.prevent="runBatchSshCommand"
                        />
                      </label>

                      <div class="batch-actions-row">
                        <el-button
                          type="primary"
                          :loading="batchSshRunning"
                          :disabled="!canRunBatchSshCommand"
                          @click="runBatchSshCommand"
                        >
                          {{ t('devices.workbench.batch.executeSsh') }}
                        </el-button>
                        <el-button
                          v-if="batchSshResults.length"
                          :disabled="batchSshRunning"
                          @click="batchSshResults = []"
                        >
                          {{ t('devices.workbench.command.clearOutput') }}
                        </el-button>
                        <span class="command-shortcut">{{ t('devices.workbench.command.shortcut') }}</span>
                      </div>

                      <div v-if="batchSshResults.length" class="batch-ssh-results">
                        <div class="batch-ssh-result-summary">
                          <span>{{ t('devices.workbench.batch.total', { count: batchSshResults.length }) }}</span>
                          <span class="is-success">{{ t('devices.workbench.batch.successTotal', { count: batchSshSuccessCount }) }}</span>
                          <span class="is-failed">{{ t('devices.workbench.batch.failedTotal', { count: batchSshFailedCount }) }}</span>
                        </div>

                        <article
                          v-for="result in batchSshResults"
                          :key="result.ip"
                          class="command-result batch-ssh-result"
                          :class="{ 'is-error': !result.success }"
                        >
                          <div class="command-result-header">
                            <div class="batch-ssh-device-heading">
                              <span>{{ getRobotDisplayName(result.ip) }}</span>
                              <span>{{ result.ip }}</span>
                            </div>
                            <el-tag size="small" :type="result.success ? 'success' : 'danger'">
                              {{ result.success ? t('devices.workbench.command.executeSuccess') : (result.exit_code === null ? t('devices.workbench.command.connectedFailed') : t('devices.workbench.command.exitCode', { code: result.exit_code })) }}
                            </el-tag>
                          </div>
                          <div class="ssh-result-meta">
                            <span>{{ t('devices.workbench.command.exitCode', { code: result.exit_code ?? '-' }) }}</span>
                            <span>{{ t('devices.workbench.command.duration', { duration: result.duration_ms }) }}</span>
                            <span v-if="result.environment?.DATE">
                              DATE：{{ result.environment.DATE }}
                              <template v-if="result.environment.DATE_TIMEZONE">
                                （{{ result.environment.DATE_TIMEZONE }}）
                              </template>
                            </span>
                          </div>
                          <div v-if="result.error" class="batch-ssh-error">{{ result.error }}</div>
                          <div class="ssh-output-section">
                            <div class="ssh-output-title">{{ t('devices.workbench.command.stdout') }}</div>
                            <pre class="command-result-body">{{ result.stdout || t('devices.workbench.command.noOutput') }}</pre>
                          </div>
                          <div v-if="result.stderr" class="ssh-output-section is-stderr">
                            <div class="ssh-output-title">{{ t('devices.workbench.command.stderr') }}</div>
                            <pre class="command-result-body">{{ result.stderr }}</pre>
                          </div>
                        </article>
                      </div>
                    </el-tab-pane>
                  </el-tabs>
                </el-tab-pane>

                <el-tab-pane :label="t('devices.workbench.tabs.sshKeys')" name="ssh-keys">
                  <div class="ssh-key-install-intro">
                    <div>
                      <div class="log-section-title">{{ t('devices.workbench.sshKeys.batchTitle') }}</div>
                      <div class="log-section-description">
                        {{ t('devices.workbench.sshKeys.batchDescription') }}
                      </div>
                    </div>
                    <el-tag type="warning" effect="plain">{{ t('devices.workbench.sshKeys.usbRequired') }}</el-tag>
                  </div>

                  <div class="ssh-key-install-settings">
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.sshKeys.timeout') }}</span>
                      <el-input-number
                        v-model="sshKeyInstallTimeout"
                        :min="1"
                        :max="300"
                        controls-position="right"
                      />
                    </label>
                    <label class="batch-field">
                      <span>{{ t('devices.workbench.sshKeys.concurrency') }}</span>
                      <el-input-number
                        v-model="sshKeyInstallConcurrency"
                        :min="1"
                        :max="10"
                        controls-position="right"
                      />
                    </label>
                    <div class="ssh-key-install-summary">
                      <strong>{{ selectedIps.length }}</strong>
                      <span>{{ t('devices.workbench.sshKeys.pending') }}</span>
                    </div>
                  </div>

                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="sshKeyInstallRunning"
                      :disabled="!canInstallSshKeys"
                      @click="runSshKeyInstall"
                    >
                      {{ t('devices.workbench.sshKeys.install') }}
                    </el-button>
                    <el-button
                      v-if="sshKeyInstallResults.length"
                      :disabled="sshKeyInstallRunning"
                      @click="sshKeyInstallResults = []"
                    >
                      {{ t('devices.workbench.command.clearResult') }}
                    </el-button>
                  </div>

                  <div v-if="sshKeyInstallResults.length" class="batch-ssh-results">
                    <div class="batch-ssh-result-summary">
                      <span>{{ t('devices.workbench.sshKeys.total', { count: sshKeyInstallResults.length }) }}</span>
                      <span class="is-success">{{ t('devices.workbench.sshKeys.successTotal', { count: sshKeyInstallSuccessCount }) }}</span>
                      <span class="is-failed">{{ t('devices.workbench.sshKeys.failedTotal', { count: sshKeyInstallFailedCount }) }}</span>
                    </div>

                    <article
                      v-for="result in sshKeyInstallResults"
                      :key="`ssh-key-${result.ip}`"
                      class="command-result batch-ssh-result"
                      :class="{ 'is-error': !result.success }"
                    >
                      <div class="command-result-header">
                        <div class="batch-ssh-device-heading">
                          <span>{{ getRobotDisplayName(result.ip) }}</span>
                          <span>{{ result.ip }}</span>
                        </div>
                        <el-tag size="small" :type="result.success ? 'success' : 'danger'">
                          {{ t(result.success ? 'devices.workbench.sshKeys.installed' : 'devices.workbench.sshKeys.failed') }}
                        </el-tag>
                      </div>
                      <div class="ssh-key-result-message" :class="{ 'is-error': !result.success }">
                        {{ result.message }}
                      </div>
                      <div class="ssh-result-meta">
                        <span>{{ t('devices.workbench.command.exitCode', { code: result.exit_code ?? '-' }) }}</span>
                        <span>{{ t('devices.workbench.command.duration', { duration: result.duration_ms }) }}</span>
                      </div>
                      <div v-if="result.stdout" class="ssh-output-section">
                        <div class="ssh-output-title">{{ t('devices.workbench.sshKeys.scriptOutput') }}</div>
                        <pre class="command-result-body">{{ result.stdout }}</pre>
                      </div>
                      <div v-if="result.stderr" class="ssh-output-section is-stderr">
                        <div class="ssh-output-title">{{ t('devices.workbench.sshKeys.errorOutput') }}</div>
                        <pre class="command-result-body">{{ result.stderr }}</pre>
                      </div>
                    </article>
                  </div>
                </el-tab-pane>
              </el-tabs>

              <div
                v-if="batchResults.length && batchActionTab !== 'ssh-keys' && !(batchActionTab === 'command' && batchCommandMode === 'ssh')"
                class="batch-result-list"
              >
                <article
                  v-for="result in batchResults"
                  :key="`${result.startedAt}-${result.ip}-${result.action}`"
                  class="batch-result-item"
                  :class="result.status"
                >
                  <div>
                    <div class="result-title">{{ result.ip }} · {{ result.action }}</div>
                    <div class="result-message">{{ result.message }}</div>
                  </div>
                  <el-tag size="small" :type="getBatchResultTagType(result.status)">
                    {{ getBatchResultStatusLabel(result.status) }}
                  </el-tag>
                </article>
              </div>
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog
      v-model="sshCommandDialogVisible"
      :title="t(editingSshCommandId ? 'devices.workbench.command.editCustom' : 'devices.workbench.command.addCustom')"
      width="620px"
      destroy-on-close
    >
      <div class="ssh-command-dialog-form">
        <label class="command-field">
          <span>{{ t('devices.workbench.command.commandName') }}</span>
          <el-input v-model="sshCommandForm.name" maxlength="80" show-word-limit :placeholder="t('devices.workbench.command.namePlaceholder')" />
        </label>
        <label class="command-field">
          <span>{{ t('devices.workbench.command.commandProperty') }}</span>
          <el-select v-model="sshCommandForm.tag">
            <el-option :label="t('devices.workbench.command.general')" value="general" />
            <el-option :label="t('devices.workbench.command.risk')" value="risk" />
          </el-select>
        </label>
        <label class="command-field">
          <span class="command-field-title">
            {{ t('devices.workbench.command.content') }}
            <small>{{ t('devices.workbench.command.contentHint') }}</small>
          </span>
          <el-input v-model="sshCommandForm.command" type="textarea" :rows="8" maxlength="20000" show-word-limit />
        </label>
        <label class="command-field">
          <span>{{ t('devices.workbench.command.description') }}</span>
          <el-input v-model="sshCommandForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </label>
      </div>
      <template #footer>
        <el-button @click="sshCommandDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="sshCommandSaving" @click="saveSshCommand">{{ t('common.actions.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="versionCaptureDialogVisible"
      :title="t('devices.workbench.versions.add')"
      width="min(760px, calc(100vw - 32px))"
      destroy-on-close
    >
      <div v-loading="versionProductsLoading" class="version-capture-form">
        <label class="command-field">
          <span>{{ t('devices.workbench.versions.currentDevice') }}</span>
          <el-input :model-value="selectedIp || ''" readonly />
        </label>
        <label class="command-field">
          <span>{{ t('devices.workbench.versions.product') }}</span>
          <el-select v-model="versionCaptureProductType" :placeholder="t('devices.workbench.versions.selectProduct')">
            <el-option
              v-for="product in versionProducts"
              :key="product.key"
              :label="product.label"
              :value="product.key"
            />
          </el-select>
        </label>
        <label class="command-field version-capture-test-field">
          <span>{{ t('devices.workbench.versions.testProcess') }}</span>
          <el-select
            v-model="versionCaptureTestName"
            filterable
            :placeholder="t('devices.workbench.versions.selectTest')"
          >
            <el-option
              v-for="testName in versionCaptureTestOptions"
              :key="testName"
              :label="testName"
              :value="testName"
            />
          </el-select>
        </label>
      </div>

      <el-alert
        v-if="versionCaptureError"
        type="error"
        :closable="false"
        :title="versionCaptureError"
        class="version-capture-alert"
      />

      <template v-if="versionCaptureResult">
        <el-divider />
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="t('devices.workbench.versions.barcode')">{{ versionCaptureResult.test.sn }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.workbench.versions.testVersion')">{{ versionCaptureResult.test.test_version }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.workbench.versions.storage')">
            {{ versionCaptureResult.storage === 'sqlite' ? 'SQLite' : 'MongoDB' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.workbench.versions.queriedAt')">
            {{ formatLogDate(versionCaptureResult.test.queried_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-table
          :data="versionCapturePreviewRows"
          border
          size="small"
          class="version-capture-preview"
        >
          <el-table-column prop="name" :label="t('devices.workbench.versions.name')" min-width="150" />
          <el-table-column prop="firmwareVersion" :label="t('devices.workbench.versions.firmware')" min-width="120" />
          <el-table-column prop="nextVersion" :label="t('devices.workbench.versions.target')" min-width="120" />
          <el-table-column prop="revision" label="Revision" min-width="110" />
          <el-table-column :label="t('devices.workbench.versions.status')" width="90">
            <template #default="scope">
              <el-tag size="small" :type="subsystemStatusType(scope.row.ok)">
                {{ subsystemStatusLabel(scope.row.ok) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template #footer>
        <el-button @click="versionCaptureDialogVisible = false">{{ t('common.actions.close') }}</el-button>
        <el-button
          type="primary"
          :loading="versionCaptureLoading"
          :disabled="!canCaptureVersion"
          @click="captureVersion"
        >{{ t('devices.workbench.versions.read') }}</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="infoDrawerVisible"
      :title="infoDrawerTitle"
      direction="rtl"
      size="420px"
    >
      <DeviceInfoPanel
        v-if="infoDrawerVisible"
        ref="infoPanelRef"
        :ip="selectedIp"
        in-drawer
        :show-header="false"
      />
      <template #footer>
        <el-button @click="infoDrawerVisible = false">{{ t('common.actions.close') }}</el-button>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="infoRefreshing"
          @click="refreshDeviceInfo"
        >{{ t('common.actions.refresh') }}</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loading, Plus, Refresh, Tickets } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAppLocale } from '@/i18n'
import {
  robotApi,
  type RobotInfo,
  type RobotLogCommandEntry,
  type RobotLogDownloadStatus,
  type RobotLogDownloadTask,
  type RobotLogFolderOption,
  type RobotSshCommand,
  type RobotSshCommandExecuteResult,
  type RobotSshKeyInstallResult,
  type RobotVersionCaptureResponse,
  type RobotVersionHistoryRecord,
  type RobotVersionProduct,
  type RobotVersionProductType,
  type RobotVersionTestEntry
} from '@/scripts/api'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import { useAuthStore } from '@/scripts/stores/auth'

const { t } = useI18n()
const { locale } = useAppLocale()
import DeviceControlPanel from '@/views/devices/components/DeviceControlPanel.vue'
import DeviceBarcodeProvisionPanel from '@/views/devices/components/DeviceBarcodeProvisionPanel.vue'
import DeviceProtocolsPanel from '@/views/devices/components/DeviceProtocolsPanel.vue'
import DeviceFilesPanel from '@/views/devices/components/DeviceFilesPanel.vue'
import DeviceTestingDataPanel from '@/views/devices/components/DeviceTestingDataPanel.vue'
import DeviceInfoPanel from '@/views/devices/components/DeviceInfoPanel.vue'
import DeviceLogHistoryPanel from '@/views/devices/components/DeviceLogHistoryPanel.vue'
import DeviceCodeFlashPanel from '@/views/devices/components/DeviceCodeFlashPanel.vue'

const route = useRoute()
const router = useRouter()
const robotScanStore = useRobotScanStore()
const authStore = useAuthStore()

const isDeviceOperator = computed(() => authStore.user?.role === 'device_operator')
const activeTab = ref(isDeviceOperator.value ? 'barcode' : 'control')
const versionQueryTab = ref('subsystems')
const manualIpInput = ref('')
const selectedIp = ref<string | null>(null)
const selectedIps = ref<string[]>([])
const availableRobots = ref<RobotInfo[]>([])
const initialScanLoading = ref(true)
const refreshing = ref(false)
const infoDrawerVisible = ref(false)
const infoPanelRef = ref<InstanceType<typeof DeviceInfoPanel> | null>(null)
const infoRefreshing = ref(false)
const batchActionTab = ref('edit')
const batchReferenceIp = ref('')
const batchEditPath = ref('')
const batchEditContent = ref('')
const batchReading = ref(false)
const batchRunning = ref(false)
const batchUploadPath = ref('')
const batchUploadFile = ref<File | null>(null)
const batchDownloadPath = ref('')
const batchHttpCommandPresetId = ref('')
const batchCommandMethod = ref('GET')
const batchCommandPath = ref('/health')
const batchCommandBody = ref('')
const batchCommandMode = ref('http')
const batchSshSelectedCommandId = ref('')
const batchSshCommandText = ref('')
const batchSshTimeout = ref(30)
const batchSshConcurrency = ref(8)
const batchSshRunning = ref(false)
const batchSshResults = ref<RobotSshCommandExecuteResult[]>([])
const sshKeyInstallTimeout = ref(30)
const sshKeyInstallConcurrency = ref(4)
const sshKeyInstallRunning = ref(false)
const sshKeyInstallResults = ref<RobotSshKeyInstallResult[]>([])
const singleSshKeyInstallTimeout = ref(30)
const singleSshKeyInstallRunning = ref(false)
const singleSshKeyInstallResult = ref<RobotSshKeyInstallResult | null>(null)
const batchResults = ref<BatchOperationResult[]>([])
const logViewTab = ref('select')
const singleLogViewTab = ref('select')
const logFolderOptions = ref<RobotLogFolderOption[]>([])
const selectedLogFolderKeys = ref<string[]>([])
const logOptionsLoading = ref(false)
const logDownloadRoot = ref('')
const logMaxConcurrency = ref(8)
const logConcurrency = ref(4)
const logTaskStarting = ref(false)
const activeLogTask = ref<RobotLogDownloadTask | null>(null)
const singleLogTaskStarting = ref(false)
const singleActiveLogTask = ref<RobotLogDownloadTask | null>(null)
let logPollTimer: ReturnType<typeof setTimeout> | null = null
let singleLogPollTimer: ReturnType<typeof setTimeout> | null = null
const singleHttpCommandPresetId = ref('')
const singleCommandMethod = ref('GET')
const singleCommandPath = ref('/health')
const singleCommandBody = ref('')
const singleCommandRunning = ref(false)
const singleCommandResult = ref<SingleCommandResult | null>(null)
const singleCommandMode = ref('http')
const subsystemVersionRows = ref<SubsystemVersionRow[]>([])
const subsystemVersionsLoading = ref(false)
const subsystemVersionsError = ref('')
const subsystemTestVersion = ref('N/A')
const subsystemTestVersionLabel = computed(() => {
  const normalized = subsystemTestVersion.value.trim()
  return normalized.match(/(?:^|-)([0-9a-f]{7,40})(?=-|$)/i)?.[1] ?? normalized
})
const versionCaptureDialogVisible = ref(false)
const versionCaptureProductType = ref<RobotVersionProductType>('robot')
const versionCaptureTestName = ref('')
const versionCaptureLoading = ref(false)
const versionCaptureError = ref('')
const versionCaptureResult = ref<RobotVersionCaptureResponse | null>(null)
const versionProducts = ref<RobotVersionProduct[]>([])
const versionProductsLoading = ref(false)
const versionHistoryRecords = ref<RobotVersionHistoryRecord[]>([])
const versionHistoryLoading = ref(false)
const versionHistoryError = ref('')
const versionHistoryTotal = ref(0)
const builtinSshCommands = ref<RobotSshCommand[]>([])
const customSshCommands = ref<RobotSshCommand[]>([])
const sshCommandsLoading = ref(false)
const sshCommandDatabaseError = ref('')
const selectedSshCommandId = ref('')
const sshCommandText = ref('')
const sshCommandTimeout = ref(30)
const sshCommandRunning = ref(false)
const sshCommandResult = ref<RobotSshCommandExecuteResult | null>(null)
const sshCommandExecutionError = ref('')
const sshCommandDialogVisible = ref(false)
const sshCommandSaving = ref(false)
const editingSshCommandId = ref('')
const sshCommandForm = ref({
  name: '',
  command: '',
  description: '',
  tag: 'general' as RobotSshCommand['tag']
})

const RISK_COMMAND_WARNING = computed(() => t('devices.workbench.command.riskWarning'))

const HTTP_COMMAND_PRESETS = computed(() => [
  { id: 'subsystems', name: t('devices.workbench.command.presets.all'), path: '/subsystems/status' },
  { id: 'gantry-x', name: t('devices.workbench.command.presets.x'), path: '/subsystems/status/gantry_x' },
  { id: 'gantry-y', name: t('devices.workbench.command.presets.y'), path: '/subsystems/status/gantry_y' },
  { id: 'head', name: t('devices.workbench.command.presets.head'), path: '/subsystems/status/head' },
  { id: 'rear-panel', name: t('devices.workbench.command.presets.rear'), path: '/subsystems/status/rear_panel' }
])

interface BatchOperationResult {
  ip: string
  action: string
  status: 'success' | 'failed' | 'skipped'
  message: string
  startedAt: number
}

type BatchOperationStatus = BatchOperationResult['status']

interface SingleCommandResult {
  method: string
  path: string
  success: boolean
  statusCode?: number
  response?: unknown
  error?: string
}

interface SubsystemVersionRow {
  name: string
  currentVersion: string
  nextVersion: string
  revision: string
  ok: boolean | null
  updateNeeded: boolean | null
  queriedAt: string
}

interface VersionPreviewRow {
  name: string
  firmwareVersion: string
  nextVersion: string
  revision: string
  ok: boolean | null
}

interface VersionHistoryRow {
  id: string
  productName: string
  barcode: string
  testName: string
  testVersion: string
  versionSummary: string
  robotIp: string
  queriedAt: string
}

const isBatchMode = computed(() => activeTab.value === 'batch')

const isAllSelected = computed(() => {
  if (availableRobots.value.length === 0) return false
  return availableRobots.value.every(robot => selectedIps.value.includes(robot.ip))
})

const initialIp = computed(() => {
  const ip = route.query.ip
  return typeof ip === 'string' ? ip : ''
})

const initialMode = computed(() => {
  const mode = route.query.mode
  return typeof mode === 'string' ? mode : ''
})

const currentDevice = computed(() => {
  if (!selectedIp.value) return null
  return availableRobots.value.find(robot => robot.ip === selectedIp.value) ?? null
})

const currentDeviceName = computed(() => {
  return currentDevice.value?.name?.trim() || t('devices.unnamed')
})

const currentServiceStatus = computed<RobotInfo['service_status']>(() => {
  return currentDevice.value?.service_status ?? 'unknown'
})

const selectedRobots = computed(() => {
  return selectedIps.value.map(ip => availableRobots.value.find(robot => robot.ip === ip) ?? {
    ip,
    port: 31950,
    online: true,
    service_status: 'unknown' as const
  })
})

const selectedVersionProduct = computed(() => (
  versionProducts.value.find(product => product.key === versionCaptureProductType.value) ?? null
))

const versionCaptureTestOptions = computed(() => selectedVersionProduct.value?.test_names ?? [])

const canCaptureVersion = computed(() => Boolean(
  selectedIp.value
  && versionCaptureProductType.value
  && versionCaptureTestName.value
  && !versionCaptureLoading.value
))

const versionCapturePreviewRows = computed<VersionPreviewRow[]>(() => {
  const test = versionCaptureResult.value?.test
  if (!test) return []
  if (test.subsystems?.length) {
    return test.subsystems.map(subsystem => ({
      name: subsystem.name,
      firmwareVersion: subsystem.firmware_version,
      nextVersion: subsystem.next_firmware_version,
      revision: subsystem.revision,
      ok: subsystem.ok
    }))
  }
  if (test.instrument) {
    return [{
      name: test.instrument.name || test.instrument.model,
      firmwareVersion: test.instrument.firmware_version,
      nextVersion: 'N/A',
      revision: 'N/A',
      ok: test.instrument.ok
    }]
  }
  return []
})

const versionHistoryRows = computed<VersionHistoryRow[]>(() => (
  versionHistoryRecords.value.flatMap(record => (
    Object.entries(record.tests || {}).map(([testKey, test]) => ({
      id: `${record._id}-${testKey}`,
      productName: record.product_name,
      barcode: record.barcode,
      testName: test.test_name,
      testVersion: test.test_version || 'N/A',
      versionSummary: summarizeVersionTest(test),
      robotIp: test.robot_ip || record.robot_ip,
      queriedAt: test.queried_at
    }))
  ))
))

const canReadBatchFile = computed(() => Boolean(batchReferenceIp.value && batchEditPath.value.trim()))
const canWriteBatchFile = computed(() => selectedIps.value.length > 0 && Boolean(batchEditPath.value.trim()))
const canBatchUpload = computed(() => selectedIps.value.length > 0 && Boolean(batchUploadPath.value.trim() && batchUploadFile.value))
const canBatchDownload = computed(() => selectedIps.value.length > 0 && Boolean(batchDownloadPath.value.trim()))
const canBatchCommand = computed(() => selectedIps.value.length > 0 && Boolean(batchCommandMethod.value && batchCommandPath.value.trim()))
const canRunBatchSshCommand = computed(() => (
  selectedIps.value.length > 0
  && Boolean(batchSshCommandText.value.trim())
  && !batchSshRunning.value
))
const batchSshSuccessCount = computed(() => batchSshResults.value.filter(result => result.success).length)
const batchSshFailedCount = computed(() => batchSshResults.value.length - batchSshSuccessCount.value)
const canInstallSshKeys = computed(() => selectedIps.value.length > 0 && !sshKeyInstallRunning.value)
const canInstallSingleSshKey = computed(() => Boolean(selectedIp.value && !singleSshKeyInstallRunning.value))
const sshKeyInstallSuccessCount = computed(() => sshKeyInstallResults.value.filter(result => result.success).length)
const sshKeyInstallFailedCount = computed(() => sshKeyInstallResults.value.length - sshKeyInstallSuccessCount.value)
const canStartLogDownload = computed(() => (
  selectedIps.value.length > 0
  && selectedLogFolderKeys.value.length > 0
  && !isLogTaskRunning.value
  && !logTaskStarting.value
))
const areAllLogFoldersSelected = computed(() => (
  logFolderOptions.value.length > 0
  && logFolderOptions.value.every(folder => selectedLogFolderKeys.value.includes(folder.key))
))
const effectiveLogConcurrency = computed(() => Math.min(logConcurrency.value, Math.max(1, selectedIps.value.length)))
const isLogTaskRunning = computed(() => ['queued', 'running'].includes(activeLogTask.value?.status || ''))
const isSingleLogTaskRunning = computed(() => ['queued', 'running'].includes(singleActiveLogTask.value?.status || ''))
const canStartSingleLogDownload = computed(() => Boolean(
  selectedIp.value
  && selectedLogFolderKeys.value.length > 0
  && !isSingleLogTaskRunning.value
  && !singleLogTaskStarting.value
))
const canRunSingleCommand = computed(() => Boolean(selectedIp.value && singleCommandMethod.value && singleCommandPath.value.trim()))
const canRunSshCommand = computed(() => Boolean(selectedIp.value && sshCommandText.value.trim()))

const singleCommandResultText = computed(() => {
  if (!singleCommandResult.value) return ''
  return JSON.stringify({
    status_code: singleCommandResult.value.statusCode,
    error: singleCommandResult.value.error,
    response: singleCommandResult.value.response
  }, null, 2)
})

const infoDrawerTitle = computed(() => {
  return selectedIp.value ? t('devices.infoTitle', { ip: selectedIp.value }) : t('devices.info')
})

function syncRobotsFromStore() {
  const robots = robotScanStore.scanResult?.online_robots ?? []
  if (robots.length) {
    const manualOnly = availableRobots.value.filter(robot => {
      return !robots.some(scannedRobot => scannedRobot.ip === robot.ip)
    })
    availableRobots.value = [...robots, ...manualOnly]
  }
}

async function loadScanCache() {
  if (!robotScanStore.scanResult) {
    try {
      await robotScanStore.loadCachedScan()
    } catch {
      robotScanStore.loadFromCache()
    }
  }
  syncRobotsFromStore()
}

function ensureRobotInList(ip: string) {
  if (!availableRobots.value.some(robot => robot.ip === ip)) {
    availableRobots.value.push({
      ip,
      port: 31950,
      online: true,
      service_status: 'unknown'
    })
  }
}

function selectFallbackDevice() {
  if (selectedIp.value && availableRobots.value.some(robot => robot.ip === selectedIp.value)) return
  selectedIp.value = availableRobots.value[0]?.ip ?? null
}

function addManualIp() {
  const ip = manualIpInput.value.trim()
  if (!ip) return
  ensureRobotInList(ip)
  if (isBatchMode.value && !selectedIps.value.includes(ip)) {
    selectedIps.value.push(ip)
  }
  selectedIp.value = ip
  manualIpInput.value = ''
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIps.value = []
    return
  }
  selectedIps.value = availableRobots.value.map(robot => robot.ip)
}

function recordBatchResult(result: Omit<BatchOperationResult, 'startedAt'>) {
  batchResults.value.unshift({
    ...result,
    startedAt: Date.now()
  })
}

function getBatchResultTagType(status: BatchOperationStatus) {
  if (status === 'success') return 'success'
  if (status === 'skipped') return 'info'
  return 'danger'
}

function getBatchResultStatusLabel(status: BatchOperationStatus) {
  if (status === 'success') return t('common.status.completed')
  if (status === 'skipped') return t('devices.workbench.batch.skipped')
  return t('common.status.error')
}

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail?.error
    || error?.response?.data?.message
    || error?.message
    || t('errors.unknown')
}

async function runForSelectedDevices(action: string, runner: (ip: string) => Promise<string>) {
  if (selectedIps.value.length === 0) {
    ElMessage.warning(t('devices.workbench.batch.selectDevice'))
    return
  }
  batchRunning.value = true
  let success = 0
  let failed = 0
  let skipped = 0
  try {
    for (const ip of selectedIps.value) {
      try {
        const message = await runner(ip)
        success += 1
        recordBatchResult({ ip, action, status: 'success', message })
      } catch (error: any) {
        if (error?.skipped) {
          skipped += 1
          recordBatchResult({ ip, action, status: 'skipped', message: error.message })
          continue
        }
        failed += 1
        recordBatchResult({ ip, action, status: 'failed', message: normalizeError(error) })
      }
    }
    if (failed > 0) {
      ElMessage.warning(t('devices.workbench.batch.resultAll', { action, success, skipped, failed }))
    } else if (skipped > 0) {
      ElMessage.warning(t('devices.workbench.batch.resultSkipped', { action, success, skipped }))
    } else {
      ElMessage.success(t('devices.workbench.batch.resultSuccess', { action, success }))
    }
  } finally {
    batchRunning.value = false
  }
}

function buildSkippedBatchOperation(message: string) {
  const error = new Error(message) as Error & { skipped: true }
  error.skipped = true
  return error
}

async function readBatchFile() {
  if (!canReadBatchFile.value) return
  batchReading.value = true
  try {
    const response = await robotApi.readFile(batchReferenceIp.value, batchEditPath.value.trim())
    batchEditContent.value = response.data.content
    ElMessage.success(t('devices.workbench.batch.fileOpened'))
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.batch.openFailed', { error: normalizeError(error) }))
  } finally {
    batchReading.value = false
  }
}

async function runBatchEditReplace() {
  const path = batchEditPath.value.trim()
  if (!path) return
  await runForSelectedDevices(t('devices.workbench.batch.replaceAction'), async (ip) => {
    const response = await robotApi.writeFile(ip, path, batchEditContent.value, { createIfMissing: false })
    if (response.data.data?.skipped) {
      throw buildSkippedBatchOperation(t('devices.workbench.batch.missingFile', { path }))
    }
    return t('devices.workbench.batch.written', { path })
  })
}

function handleBatchUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  batchUploadFile.value = input.files?.[0] ?? null
}

async function runBatchUpload() {
  const file = batchUploadFile.value
  const path = batchUploadPath.value.trim()
  if (!file || !path) return
  await runForSelectedDevices(t('devices.workbench.batch.uploadAction'), async (ip) => {
    await robotApi.uploadFile(ip, path, file)
    return t('devices.workbench.batch.uploaded', { path })
  })
}

function parseDownloadFilename(contentDisposition: string | undefined, fallbackName: string): string {
  if (!contentDisposition) return fallbackName
  const match = contentDisposition.match(/filename="([^"]+)"/i)
  return match?.[1] ?? fallbackName
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function basename(path: string): string {
  return path.replace(/\/+$/, '').split('/').filter(Boolean).pop() || 'download'
}

async function runBatchDownload() {
  const path = batchDownloadPath.value.trim()
  if (!path) return
  await runForSelectedDevices(t('devices.workbench.batch.downloadAction'), async (ip) => {
    const response = await robotApi.downloadFile(ip, path)
    const fallbackName = `${ip.replace(/\./g, '-')}-${basename(path)}`
    const filename = parseDownloadFilename(response.headers['content-disposition'], fallbackName)
    saveBlob(response.data, filename)
    return t('devices.workbench.batch.downloaded', { path })
  })
}

function getLogStatusLabel(status: RobotLogDownloadStatus) {
  const labels: Record<RobotLogDownloadStatus, string> = {
    queued: t('devices.workbench.logs.statuses.queued'),
    running: t('devices.workbench.logs.statuses.running'),
    success: t('devices.workbench.logs.statuses.success'),
    warning: t('devices.workbench.logs.statuses.warning'),
    failed: t('devices.workbench.logs.statuses.failed'),
    completed: t('devices.workbench.logs.statuses.completed'),
    completed_with_warnings: t('devices.workbench.logs.statuses.warnings'),
    completed_with_errors: t('devices.workbench.logs.statuses.errors')
  }
  return labels[status] || status
}

function getLogStatusTagType(status: RobotLogDownloadStatus) {
  if (status === 'success' || status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'warning' || status === 'completed_with_warnings' || status === 'completed_with_errors') return 'warning'
  if (status === 'queued') return 'info'
  return undefined
}

function formatLogDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

function getRecordProgressStatus(record: { status: RobotLogDownloadStatus }) {
  if (record.status === 'failed') return 'exception'
  if (record.status === 'warning') return 'warning'
  if (record.status === 'success') return 'success'
  return undefined
}

function getLogTaskProgressStatus(task: RobotLogDownloadTask) {
  if (task.failed_devices) return 'exception'
  if (task.warning_devices) return 'warning'
  if (task.status === 'completed') return 'success'
  return undefined
}

function formatCommandTime(value?: string | null) {
  if (!value) return '--:--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale.value, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

function getDisplayCommandLogs(commandLogs?: RobotLogCommandEntry[]) {
  return [...(commandLogs || [])].reverse()
}

function getCommandStatusLabel(status: RobotLogCommandEntry['status']) {
  if (status === 'running') return t('devices.workbench.logs.statuses.commandRunning')
  if (status === 'success') return t('devices.workbench.logs.statuses.success')
  return t('devices.workbench.logs.statuses.failed')
}

function getCommandStatusTagType(status: RobotLogCommandEntry['status']) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

async function loadLogFolderOptions() {
  if (logFolderOptions.value.length || logOptionsLoading.value) return
  logOptionsLoading.value = true
  try {
    const response = await robotApi.getLogDownloadFolders()
    logFolderOptions.value = response.data.folders
    selectedLogFolderKeys.value = response.data.folders
      .filter(folder => folder.default_selected)
      .map(folder => folder.key)
    logDownloadRoot.value = response.data.download_root
    logMaxConcurrency.value = response.data.max_concurrency
    logConcurrency.value = Math.min(logConcurrency.value, response.data.max_concurrency)
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.logs.loadFoldersFailed', { error: normalizeError(error) }))
  } finally {
    logOptionsLoading.value = false
  }
}

function toggleAllLogFolders() {
  selectedLogFolderKeys.value = areAllLogFoldersSelected.value
    ? []
    : logFolderOptions.value.map(folder => folder.key)
}

function clearLogPollTimer() {
  if (logPollTimer) {
    clearTimeout(logPollTimer)
    logPollTimer = null
  }
}

function clearSingleLogPollTimer() {
  if (singleLogPollTimer) {
    clearTimeout(singleLogPollTimer)
    singleLogPollTimer = null
  }
}

async function pollLogTask(taskId: string, showError = false) {
  clearLogPollTimer()
  try {
    const response = await robotApi.getLogDownloadTask(taskId)
    activeLogTask.value = response.data
    if (['queued', 'running'].includes(response.data.status)) {
      logPollTimer = setTimeout(() => pollLogTask(taskId), 1000)
      return
    }
    if (response.data.failed_devices > 0) {
      ElMessage.warning(
        t('devices.workbench.logs.completedSummary', { success: response.data.successful_devices, warnings: response.data.warning_devices, failed: response.data.failed_devices })
      )
    } else if (response.data.warning_devices > 0) {
      ElMessage.warning(t('devices.workbench.logs.completedWarnings', { success: response.data.successful_devices, warnings: response.data.warning_devices }))
    } else {
      ElMessage.success(t('devices.workbench.logs.completedSuccess', { success: response.data.successful_devices }))
    }
  } catch (error: any) {
    if (showError) ElMessage.error(t('devices.workbench.logs.progressFailed', { error: normalizeError(error) }))
    logPollTimer = setTimeout(() => pollLogTask(taskId), 3000)
  }
}

async function startLogDownload() {
  if (!canStartLogDownload.value) return
  logTaskStarting.value = true
  try {
    const response = await robotApi.createLogDownloadTask({
      devices: selectedRobots.value.map(robot => ({
        ip: robot.ip,
        name: robot.name?.trim() || robot.ip
      })),
      folder_keys: selectedLogFolderKeys.value,
      concurrency: effectiveLogConcurrency.value
    })
    activeLogTask.value = response.data
    ElMessage.success(t('devices.workbench.logs.taskStarted'))
    await pollLogTask(response.data.task_id, true)
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.logs.startFailed', { error: normalizeError(error) }))
  } finally {
    logTaskStarting.value = false
  }
}

async function pollSingleLogTask(taskId: string, showError = false) {
  clearSingleLogPollTimer()
  try {
    const response = await robotApi.getLogDownloadTask(taskId)
    singleActiveLogTask.value = response.data
    if (['queued', 'running'].includes(response.data.status)) {
      singleLogPollTimer = setTimeout(() => pollSingleLogTask(taskId), 1000)
      return
    }
    if (response.data.failed_devices > 0) {
      ElMessage.error(t('devices.workbench.logs.currentFailed'))
    } else if (response.data.warning_devices > 0) {
      ElMessage.warning(t('devices.workbench.logs.currentWarning'))
    } else {
      ElMessage.success(t('devices.workbench.logs.currentSuccess'))
    }
  } catch (error: any) {
    if (showError) ElMessage.error(t('devices.workbench.logs.progressFailed', { error: normalizeError(error) }))
    singleLogPollTimer = setTimeout(() => pollSingleLogTask(taskId), 3000)
  }
}

async function startSingleLogDownload() {
  const ip = selectedIp.value
  if (!ip || !canStartSingleLogDownload.value) return
  const deviceName = currentDevice.value?.name?.trim() || ip

  singleLogTaskStarting.value = true
  try {
    const response = await robotApi.createLogDownloadTask({
      devices: [{ ip, name: deviceName }],
      folder_keys: selectedLogFolderKeys.value,
      concurrency: 1
    })
    singleActiveLogTask.value = response.data
    ElMessage.success(t('devices.workbench.logs.deviceStarted', { ip }))
    await pollSingleLogTask(response.data.task_id, true)
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.logs.startFailed', { error: normalizeError(error) }))
  } finally {
    singleLogTaskStarting.value = false
  }
}

function parseCommandBody(text: string): Record<string, unknown> | undefined {
  const trimmed = text.trim()
  if (!trimmed) return undefined
  const parsed = JSON.parse(trimmed)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(t('devices.workbench.command.bodyObject'))
  }
  return parsed as Record<string, unknown>
}

function findHttpCommandPreset(presetId: string) {
  return HTTP_COMMAND_PRESETS.value.find(preset => preset.id === presetId)
}

function applySingleHttpCommandPreset(presetId: string) {
  const preset = findHttpCommandPreset(presetId)
  if (!preset) return
  singleCommandMethod.value = 'GET'
  singleCommandPath.value = preset.path
}

function applyBatchHttpCommandPreset(presetId: string) {
  const preset = findHttpCommandPreset(presetId)
  if (!preset) return
  batchCommandMethod.value = 'GET'
  batchCommandPath.value = preset.path
}

function subsystemStatusLabel(ok: boolean | null): string {
  if (ok === true) return t('devices.workbench.versions.healthy')
  if (ok === false) return t('devices.workbench.versions.abnormal')
  return t('devices.workbench.versions.unknown')
}

function subsystemStatusType(ok: boolean | null) {
  if (ok === true) return 'success'
  if (ok === false) return 'danger'
  return 'info'
}

function subsystemUpdateLabel(updateNeeded: boolean | null): string {
  if (updateNeeded === true) return t('devices.workbench.versions.updateNeeded')
  if (updateNeeded === false) return t('devices.workbench.versions.currentLatest')
  return t('devices.workbench.versions.unknown')
}

function subsystemUpdateType(updateNeeded: boolean | null) {
  if (updateNeeded === true) return 'warning'
  if (updateNeeded === false) return 'success'
  return 'info'
}

function summarizeVersionTest(test: RobotVersionTestEntry): string {
  if (test.subsystems?.length) {
    return test.subsystems
      .map(subsystem => `${subsystem.name}: FW ${subsystem.firmware_version}, Rev ${subsystem.revision}`)
      .join('；')
  }
  if (test.instrument) {
    const name = test.instrument.name || test.instrument.model
    return `${name}: FW ${test.instrument.firmware_version}`
  }
  return 'N/A'
}

async function loadVersionProducts() {
  if (versionProducts.value.length || versionProductsLoading.value) return
  versionProductsLoading.value = true
  versionCaptureError.value = ''
  try {
    const response = await robotApi.getVersionProducts()
    versionProducts.value = response.data.products
    if (!versionProducts.value.some(product => product.key === versionCaptureProductType.value)) {
      versionCaptureProductType.value = 'robot'
    }
    versionCaptureTestName.value = selectedVersionProduct.value?.test_names[0] || ''
  } catch (error: any) {
    versionCaptureError.value = t('devices.workbench.versions.loadOptionsFailed', { error: normalizeError(error) })
  } finally {
    versionProductsLoading.value = false
  }
}

async function openVersionCaptureDialog() {
  if (!selectedIp.value) return
  versionCaptureProductType.value = 'robot'
  versionCaptureTestName.value = ''
  versionCaptureResult.value = null
  versionCaptureError.value = ''
  versionCaptureDialogVisible.value = true
  await loadVersionProducts()
  versionCaptureTestName.value = selectedVersionProduct.value?.test_names[0] || ''
}

async function captureVersion() {
  if (!canCaptureVersion.value || !selectedIp.value) return
  versionCaptureLoading.value = true
  versionCaptureError.value = ''
  versionCaptureResult.value = null
  try {
    const response = await robotApi.captureVersion({
      ip: selectedIp.value,
      port: currentDevice.value?.port ?? 31950,
      product_type: versionCaptureProductType.value,
      test_name: versionCaptureTestName.value
    })
    versionCaptureResult.value = response.data
    subsystemTestVersion.value = response.data.test.test_version || 'N/A'
    await loadVersionHistory()
    ElMessage.success(t('devices.workbench.versions.saved'))
  } catch (error: any) {
    versionCaptureError.value = t('devices.workbench.versions.readFailed', { error: normalizeError(error) })
  } finally {
    versionCaptureLoading.value = false
  }
}

async function loadVersionHistory() {
  if (versionHistoryLoading.value) return
  versionHistoryLoading.value = true
  versionHistoryError.value = ''
  try {
    const response = await robotApi.getVersionHistory({ page: 1, page_size: 200 })
    versionHistoryRecords.value = response.data.records
    versionHistoryTotal.value = response.data.total
  } catch (error: any) {
    versionHistoryRecords.value = []
    versionHistoryTotal.value = 0
    versionHistoryError.value = t('devices.workbench.versions.historyFailed', { error: normalizeError(error) })
  } finally {
    versionHistoryLoading.value = false
  }
}

async function loadSubsystemVersions() {
  if (!selectedIp.value || subsystemVersionsLoading.value) return
  const requestIp = selectedIp.value
  subsystemVersionsLoading.value = true
  subsystemVersionsError.value = ''
  try {
    const response = await robotApi.getCurrentVersions(requestIp, currentDevice.value?.port ?? 31950)
    const queriedAt = response.data.queried_at
    const rows = response.data.subsystems.map(subsystem => ({
      name: subsystem.name,
      currentVersion: subsystem.firmware_version,
      nextVersion: subsystem.next_firmware_version,
      revision: subsystem.revision,
      ok: subsystem.ok,
      updateNeeded: subsystem.fw_update_needed,
      queriedAt
    }))
    if (!rows.length) {
      throw new Error(t('devices.workbench.versions.noSubsystemResponse'))
    }
    if (selectedIp.value === requestIp) {
      subsystemVersionRows.value = rows
      subsystemTestVersion.value = response.data.test_version || 'N/A'
    }
  } catch (error: any) {
    if (selectedIp.value === requestIp) {
      subsystemVersionRows.value = []
      subsystemTestVersion.value = 'N/A'
      subsystemVersionsError.value = t('devices.workbench.versions.queryFailed', { error: normalizeError(error) })
    }
  } finally {
    subsystemVersionsLoading.value = false
  }
}

async function runSingleCommand() {
  if (!selectedIp.value) return
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(singleCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || t('devices.workbench.command.bodyInvalid'))
    return
  }

  const method = singleCommandMethod.value
  const path = singleCommandPath.value.trim()
  singleCommandRunning.value = true
  singleCommandResult.value = null
  try {
    const response = await robotApi.executeCommands({
      ips: [selectedIp.value],
      method,
      path,
      body,
      timeout: 30
    })
    const result = response.data.results?.[0]
    singleCommandResult.value = {
      method,
      path,
      success: Boolean(result?.success),
      statusCode: result?.status_code,
      response: result?.response,
      error: result?.error
    }
    if (result?.success) {
      ElMessage.success(t('devices.workbench.command.runSuccess'))
    } else {
      ElMessage.error(result?.error || t('devices.workbench.command.runFailed'))
    }
  } catch (error: any) {
    singleCommandResult.value = {
      method,
      path,
      success: false,
      error: normalizeError(error)
    }
    ElMessage.error(t('devices.workbench.command.runFailedWithError', { error: normalizeError(error) }))
  } finally {
    singleCommandRunning.value = false
  }
}

async function loadSshCommands(showError = true) {
  sshCommandsLoading.value = true
  try {
    const response = await robotApi.getSshCommands()
    builtinSshCommands.value = response.data.builtin_commands || []
    customSshCommands.value = response.data.custom_commands || []
    sshCommandDatabaseError.value = response.data.database_available
      ? ''
      : (response.data.error || t('devices.workbench.command.mongoFailed'))

    const allCommands = [...builtinSshCommands.value, ...customSshCommands.value]
    const selectedExists = allCommands.some(item => item.id === selectedSshCommandId.value)
    if (!selectedExists) {
      selectedSshCommandId.value = allCommands.find(item => item.command === 'date')?.id || allCommands[0]?.id || ''
      applySelectedSshCommand()
    }
  } catch (error: any) {
    sshCommandDatabaseError.value = normalizeError(error)
    if (showError) ElMessage.error(t('devices.workbench.command.loadFailed', { error: sshCommandDatabaseError.value }))
  } finally {
    sshCommandsLoading.value = false
  }
}

function applySelectedSshCommand() {
  const command = [...builtinSshCommands.value, ...customSshCommands.value]
    .find(item => item.id === selectedSshCommandId.value)
  if (command) sshCommandText.value = command.command
}

function ensureBatchSshCommandSelection() {
  const allCommands = [...builtinSshCommands.value, ...customSshCommands.value]
  const selectedExists = allCommands.some(item => item.id === batchSshSelectedCommandId.value)
  if (selectedExists) return
  batchSshSelectedCommandId.value = allCommands.find(item => item.command === 'date')?.id || allCommands[0]?.id || ''
  applySelectedBatchSshCommand()
}

function applySelectedBatchSshCommand() {
  const command = [...builtinSshCommands.value, ...customSshCommands.value]
    .find(item => item.id === batchSshSelectedCommandId.value)
  if (command) batchSshCommandText.value = command.command
}

function isRiskSshCommand(selectedCommandId: string, commandText: string) {
  const allCommands = [...builtinSshCommands.value, ...customSshCommands.value]
  const selectedCommand = allCommands.find(item => item.id === selectedCommandId)
  if (selectedCommand?.tag === 'risk') return true
  const normalizedCommand = commandText.trim()
  return allCommands.some(item => item.tag === 'risk' && item.command.trim() === normalizedCommand)
}

async function confirmRiskSshCommand() {
  try {
    await ElMessageBox.confirm(
      RISK_COMMAND_WARNING.value,
      t('devices.workbench.command.riskTitle'),
      {
        type: 'warning',
        confirmButtonText: t('devices.workbench.command.confirmExecute'),
        cancelButtonText: t('common.actions.cancel'),
        closeOnClickModal: false
      }
    )
    return true
  } catch {
    return false
  }
}

async function handleCommandModeChange(tabName: string | number) {
  if (tabName === 'ssh' && builtinSshCommands.value.length === 0) {
    await loadSshCommands()
  }
}

async function handleBatchCommandModeChange(tabName: string | number) {
  if (tabName !== 'ssh') return
  if (builtinSshCommands.value.length === 0) await loadSshCommands()
  ensureBatchSshCommandSelection()
}

function clearSshCommandOutput() {
  sshCommandResult.value = null
  sshCommandExecutionError.value = ''
}

async function runSshCommand() {
  if (!selectedIp.value || !sshCommandText.value.trim()) return
  if (
    isRiskSshCommand(selectedSshCommandId.value, sshCommandText.value)
    && !(await confirmRiskSshCommand())
  ) return
  sshCommandRunning.value = true
  clearSshCommandOutput()
  try {
    const response = await robotApi.executeSshCommand({
      ip: selectedIp.value,
      command: sshCommandText.value.trim(),
      timeout: sshCommandTimeout.value
    })
    sshCommandResult.value = response.data
    if (response.data.success) {
      ElMessage.success(t('devices.workbench.command.sshSuccess'))
    } else {
      ElMessage.warning(t('devices.workbench.command.sshExit', { code: response.data.exit_code }))
    }
  } catch (error: any) {
    sshCommandExecutionError.value = normalizeError(error)
    ElMessage.error(t('devices.workbench.command.sshFailed', { error: sshCommandExecutionError.value }))
  } finally {
    sshCommandRunning.value = false
  }
}

function openCreateSshCommand() {
  editingSshCommandId.value = ''
  sshCommandForm.value = { name: '', command: '', description: '', tag: 'general' }
  sshCommandDialogVisible.value = true
}

function openEditSshCommand(command: RobotSshCommand) {
  editingSshCommandId.value = command.id
  sshCommandForm.value = {
    name: command.name,
    command: command.command,
    description: command.description || '',
    tag: command.tag || 'general'
  }
  sshCommandDialogVisible.value = true
}

async function saveSshCommand() {
  const payload = {
    name: sshCommandForm.value.name.trim(),
    command: sshCommandForm.value.command.trim(),
    description: sshCommandForm.value.description.trim(),
    tag: sshCommandForm.value.tag
  }
  if (!payload.name) {
    ElMessage.warning(t('devices.workbench.command.enterName'))
    return
  }
  if (!payload.command) {
    ElMessage.warning(t('devices.workbench.command.enterContent'))
    return
  }

  sshCommandSaving.value = true
  try {
    const response = editingSshCommandId.value
      ? await robotApi.updateSshCommand(editingSshCommandId.value, payload)
      : await robotApi.createSshCommand(payload)
    sshCommandDialogVisible.value = false
    await loadSshCommands(false)
    selectedSshCommandId.value = response.data.id
    sshCommandText.value = response.data.command
    ElMessage.success(t(editingSshCommandId.value ? 'devices.workbench.command.updated' : 'devices.workbench.command.added'))
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.command.saveFailed', { error: normalizeError(error) }))
  } finally {
    sshCommandSaving.value = false
  }
}

async function removeSshCommand(command: RobotSshCommand) {
  try {
    await ElMessageBox.confirm(
      t('devices.workbench.command.deleteConfirm', { name: command.name }),
      t('devices.workbench.command.deleteTitle'),
      { type: 'warning', confirmButtonText: t('common.actions.delete'), cancelButtonText: t('common.actions.cancel') }
    )
    await robotApi.deleteSshCommand(command.id)
    if (selectedSshCommandId.value === command.id) {
      selectedSshCommandId.value = ''
    }
    await loadSshCommands(false)
    ElMessage.success(t('devices.workbench.command.deleted'))
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(t('devices.workbench.command.deleteFailed', { error: normalizeError(error) }))
  }
}

async function runBatchCommand() {
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(batchCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || t('devices.workbench.command.bodyInvalid'))
    return
  }

  const path = batchCommandPath.value.trim()
  await runForSelectedDevices(t('devices.workbench.command.batchAction'), async (ip) => {
    const response = await robotApi.executeCommands({
      ips: [ip],
      method: batchCommandMethod.value,
      path,
      body,
      timeout: 30
    })
    const result = response.data.results?.[0]
    if (!result?.success) {
      throw new Error(result?.error || `HTTP ${result?.status_code || t('devices.workbench.command.httpFailed')}`)
    }
    return t('devices.workbench.command.executed', { method: batchCommandMethod.value, path })
  })
}

async function runBatchSshCommand() {
  if (!canRunBatchSshCommand.value) return
  if (
    isRiskSshCommand(batchSshSelectedCommandId.value, batchSshCommandText.value)
    && !(await confirmRiskSshCommand())
  ) return
  batchSshRunning.value = true
  batchSshResults.value = []
  try {
    const response = await robotApi.executeBatchSshCommands({
      ips: [...selectedIps.value],
      command: batchSshCommandText.value.trim(),
      timeout: batchSshTimeout.value,
      concurrency: batchSshConcurrency.value
    })
    batchSshResults.value = response.data.results || []
    if (response.data.failed_count > 0) {
      ElMessage.warning(t('devices.workbench.command.batchSshCompleted', { success: response.data.success_count, failed: response.data.failed_count }))
    } else {
      ElMessage.success(t('devices.workbench.command.batchSshSuccess', { count: response.data.success_count }))
    }
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.command.batchSshFailed', { error: normalizeError(error) }))
  } finally {
    batchSshRunning.value = false
  }
}

async function runSshKeyInstall() {
  if (!canInstallSshKeys.value) return
  try {
    await ElMessageBox.confirm(
      t('devices.workbench.sshKeys.batchConfirm', { count: selectedIps.value.length }),
      t('devices.workbench.sshKeys.confirmTitle'),
      {
        confirmButtonText: t('devices.workbench.sshKeys.startInstall'),
        cancelButtonText: t('common.actions.cancel'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  sshKeyInstallRunning.value = true
  sshKeyInstallResults.value = []
  try {
    const response = await robotApi.installSshKeys({
      ips: [...selectedIps.value],
      timeout: sshKeyInstallTimeout.value,
      concurrency: sshKeyInstallConcurrency.value
    })
    sshKeyInstallResults.value = response.data.results || []
    if (response.data.failed_count > 0) {
      ElMessage.warning(t('devices.workbench.sshKeys.batchCompleted', { success: response.data.success_count, failed: response.data.failed_count }))
    } else {
      ElMessage.success(t('devices.workbench.sshKeys.batchSuccess', { count: response.data.success_count }))
    }
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.sshKeys.installFailed', { error: normalizeError(error) }))
  } finally {
    sshKeyInstallRunning.value = false
  }
}

async function runSingleSshKeyInstall() {
  const ip = selectedIp.value
  if (!ip || !canInstallSingleSshKey.value) return
  try {
    await ElMessageBox.confirm(
      t('devices.workbench.sshKeys.singleConfirm', { name: currentDeviceName.value, ip }),
      t('devices.workbench.sshKeys.confirmTitle'),
      {
        confirmButtonText: t('devices.workbench.sshKeys.startInstall'),
        cancelButtonText: t('common.actions.cancel'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  singleSshKeyInstallRunning.value = true
  singleSshKeyInstallResult.value = null
  try {
    const response = await robotApi.installSshKeys({
      ips: [ip],
      timeout: singleSshKeyInstallTimeout.value,
      concurrency: 1
    })
    const result = response.data.results?.[0]
    if (!result) throw new Error(t('devices.workbench.sshKeys.missingResult'))
    singleSshKeyInstallResult.value = result
    if (result.success) {
      ElMessage.success(t('devices.workbench.sshKeys.deviceSuccess', { ip }))
    } else {
      ElMessage.error(t('devices.workbench.sshKeys.deviceFailed', { ip, error: result.message }))
    }
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.sshKeys.installFailed', { error: normalizeError(error) }))
  } finally {
    singleSshKeyInstallRunning.value = false
  }
}

async function refreshRobots() {
  refreshing.value = true
  try {
    await robotScanStore.refreshScan({ silent: false })
    syncRobotsFromStore()
    selectFallbackDevice()
  } catch (error: any) {
    ElMessage.error(t('devices.workbench.refreshFailed', { error: error.message || t('errors.unknown') }))
  } finally {
    refreshing.value = false
  }
}

function returnToDeviceList() {
  router.push({ name: 'Devices' })
}

function openInfoDrawer() {
  if (!selectedIp.value) return
  infoDrawerVisible.value = true
}

function beforeTabLeave(nextTab: string | number): boolean {
  if (nextTab !== 'control' || !isDeviceOperator.value) return true
  void ElMessageBox.alert(
    t('devices.workbench.permissionMessage'),
    t('devices.workbench.permissionTitle'),
    {
      confirmButtonText: t('devices.workbench.understood'),
      type: 'warning',
      closeOnClickModal: false,
      showClose: false,
    },
  )
  return false
}

async function refreshDeviceInfo() {
  if (infoRefreshing.value) return
  infoRefreshing.value = true
  try {
    await infoPanelRef.value?.refresh()
  } finally {
    infoRefreshing.value = false
  }
}

async function handleTabChange(tabName: string | number) {
  if (tabName === 'batch') {
    if (selectedIp.value && !selectedIps.value.includes(selectedIp.value)) {
      selectedIps.value = [selectedIp.value]
    }
    if (!batchReferenceIp.value) {
      batchReferenceIp.value = selectedIps.value[0] ?? ''
    }
    return
  }

  if (!selectedIp.value) {
    selectedIp.value = selectedIps.value[0] ?? availableRobots.value[0]?.ip ?? null
  }

  if (tabName === 'device-logs') {
    await loadLogFolderOptions()
  }

  if (tabName === 'versions') {
    if (versionQueryTab.value === 'history') {
      await loadVersionHistory()
    } else {
      await loadSubsystemVersions()
    }
  }
}

async function handleVersionQueryTabChange(tabName: string | number) {
  if (tabName === 'history') {
    await loadVersionHistory()
    return
  }
  if (tabName === 'subsystems') {
    await loadSubsystemVersions()
  }
}

function formatServiceStatus(status: RobotInfo['service_status']) {
  const statusMap: Record<RobotInfo['service_status'], string> = {
    normal: t('common.status.healthy'),
    error: t('common.status.abnormal'),
    unknown: t('common.status.unknown')
  }
  return statusMap[status] || t('common.status.unknown')
}

function getRobotDisplayName(ip: string) {
  return availableRobots.value.find(robot => robot.ip === ip)?.name?.trim() || t('devices.unnamed')
}

watch(selectedIp, (ip) => {
  if (ip && selectedIps.value.length === 0) {
    selectedIps.value = [ip]
  }
})

watch(selectedIps, (ips) => {
  if (!ips.includes(batchReferenceIp.value)) {
    batchReferenceIp.value = ips[0] ?? ''
  }
})

watch(versionCaptureProductType, () => {
  versionCaptureTestName.value = selectedVersionProduct.value?.test_names[0] || ''
  versionCaptureResult.value = null
  versionCaptureError.value = ''
})

watch(batchActionTab, async (tabName) => {
  if (tabName === 'logs') {
    await loadLogFolderOptions()
  }
  if (tabName === 'command' && batchCommandMode.value === 'ssh') {
    if (builtinSshCommands.value.length === 0) await loadSshCommands()
    ensureBatchSshCommandSelection()
  }
})

onBeforeUnmount(() => {
  clearLogPollTimer()
  clearSingleLogPollTimer()
})

onMounted(async () => {
  try {
    await loadScanCache()
    if (initialMode.value === 'batch') {
      activeTab.value = 'batch'
    }
    if (initialIp.value) {
      ensureRobotInList(initialIp.value)
      selectedIp.value = initialIp.value
    } else {
      selectFallbackDevice()
    }

    if (selectedIp.value && selectedIps.value.length === 0) {
      selectedIps.value = [selectedIp.value]
    }
  } finally {
    initialScanLoading.value = false
  }
})
</script>

<style scoped>
.device-control-view {
  --console-text: #1f2a37;
  --console-muted: #6b7280;
  --console-border: #e6ebf2;
  --console-soft: #f7f9fc;
  --console-active: #f2f7ff;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0 20px 0;
  background: #fff;
  color: var(--console-text);
  text-align: left;
}

.initial-device-loading {
  flex: 1;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #6b7280;
  font-size: 14px;
}

.initial-device-loading-icon {
  color: #409eff;
  font-size: 22px;
}

.device-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 64px;
  padding: 10px 0;
  border-bottom: 1px solid var(--console-border);
}

.device-context.is-batch {
  background: linear-gradient(180deg, rgba(247, 249, 252, 0.68), rgba(255, 255, 255, 0));
}

.device-identity,
.device-meta {
  display: flex;
  align-items: center;
  min-width: 0;
}

.device-identity {
  gap: 12px;
}

.device-back-button {
  flex: none;
  width: 32px;
  height: 32px;
}

.device-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.device-name {
  overflow: hidden;
  color: var(--console-text);
  font-size: 15px;
  font-weight: 650;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-address,
.device-ip,
.meta-item {
  color: var(--console-muted);
  font-size: 12px;
  line-height: 1.3;
}

.device-address {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.device-ip {
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-meta {
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.inline-status {
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.3;
}

.inline-status.normal {
  color: #16803c;
}

.inline-status.error {
  color: #c24141;
}

.status-pill,
.device-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
}

.status-pill.normal {
  background: #ecfdf3;
  color: #16803c;
}

.status-pill.error {
  background: #fef2f2;
  color: #c24141;
}

.workbench {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.workbench-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.workbench-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-top: 14px;
}

.workbench-tabs :deep(.el-tab-pane) {
  min-height: 100%;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.subsystem-version-workspace,
.version-history-workspace {
  min-width: 0;
}

.version-query-tabs :deep(> .el-tabs__header) {
  margin-bottom: 16px;
}

.subsystem-version-toolbar {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.subsystem-version-heading {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.subsystem-version-heading h2 {
  margin: 0;
  color: var(--console-text);
  font-size: 16px;
  font-weight: 650;
  letter-spacing: 0;
}

.subsystem-version-heading span {
  overflow: hidden;
  color: var(--console-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subsystem-version-heading .subsystem-version-separator {
  color: #9ca3af;
}

.subsystem-version-heading .subsystem-test-version {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 7px;
  overflow: hidden;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #f3f4f6;
  color: #1f2937;
  cursor: help;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subsystem-version-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.subsystem-version-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.subsystem-version-alert {
  margin-bottom: 14px;
}

.command-console {
  max-width: 860px;
}

.command-mode-tabs {
  min-height: 500px;
}

.command-mode-tabs :deep(> .el-tabs__header) {
  margin-bottom: 20px;
}

.command-form-grid {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.http-command-preset-field {
  grid-column: 1 / -1;
}

.command-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 600;
}

.command-field-title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
}

.command-field-title small {
  color: #9aa3b2;
  font-size: 11px;
  font-weight: 400;
}

.command-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.command-result {
  margin-top: 16px;
  border: 1px solid #d9eadf;
  border-radius: 6px;
  background: #f7fcf9;
  overflow: hidden;
}

.command-result.is-error {
  border-color: #f4cccc;
  background: #fff8f8;
}

.command-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #e6ebf2;
  color: var(--console-text);
  font-size: 13px;
  font-weight: 650;
}

.command-result-body {
  max-height: 420px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: #1f2a37;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.ssh-command-workspace {
  max-width: 1120px;
}

.ssh-command-alert {
  margin-bottom: 14px;
}

.ssh-command-settings {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 12px;
  margin-bottom: 12px;
}

.ssh-command-preset-select :deep(.el-select__wrapper),
.ssh-command-preset-select :deep(.el-select__selection),
.ssh-command-preset-select :deep(.el-select__selected-item),
.ssh-command-preset-select :deep(.el-select__placeholder) {
  min-width: 0;
}

.ssh-command-preset-select :deep(.el-select__selected-item),
.ssh-command-preset-select :deep(.el-select__placeholder) {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:global(.ssh-command-select-popper .el-select-dropdown__item) {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

:global(.ssh-command-select-popper) {
  width: min(860px, calc(100vw - 32px)) !important;
  min-width: min(860px, calc(100vw - 32px)) !important;
  max-width: min(860px, calc(100vw - 32px)) !important;
}

:global(.ssh-command-select-popper .el-select-dropdown),
:global(.ssh-command-select-popper .el-select-dropdown__wrap),
:global(.ssh-command-select-popper .el-select-dropdown__list) {
  width: 100%;
  max-width: 100%;
}

.ssh-command-option {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
}

.ssh-command-option-name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: #1f2a37;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ssh-command-option :deep(.el-tag) {
  flex: none;
}

:global(.ssh-command-full-tooltip) {
  max-width: min(720px, calc(100vw - 32px));
  white-space: pre-wrap;
  word-break: break-word;
}

.ssh-timeout-field :deep(.el-input-number) {
  width: 100%;
}

.command-shortcut {
  align-self: center;
  color: var(--console-muted);
  font-size: 12px;
}

.ssh-command-result {
  margin-bottom: 24px;
}

.ssh-result-heading {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
}

.ssh-result-heading > span:first-child {
  flex: none;
}

.ssh-result-command {
  display: block;
  min-width: 0;
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ssh-command-result .command-result-header :deep(.el-tag),
.command-result.is-error .command-result-header :deep(.el-tag) {
  flex: none;
}

.ssh-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  padding: 9px 12px;
  border-bottom: 1px solid #e6ebf2;
  color: var(--console-muted);
  font-size: 12px;
}

.ssh-output-section + .ssh-output-section {
  border-top: 1px solid #e6ebf2;
}

.ssh-output-section.is-stderr {
  background: #fff8f8;
}

.ssh-output-title {
  padding: 8px 12px 0;
  color: var(--console-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.custom-command-section {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--console-border);
}

.custom-command-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.custom-command-header h3 {
  margin: 0;
  color: var(--console-text);
  font-size: 15px;
}

.custom-command-header p {
  margin: 5px 0 0;
  color: var(--console-muted);
  font-size: 12px;
}

.ssh-command-dialog-form {
  display: grid;
  gap: 16px;
}

.version-capture-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.version-capture-test-field {
  grid-column: 1 / -1;
}

.version-capture-alert,
.version-capture-preview {
  margin-top: 16px;
}

.batch-workspace {
  min-height: 520px;
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  border-top: 1px solid var(--console-border);
}

.batch-device-panel {
  height: clamp(460px, calc(100vh - 270px), 640px);
  min-width: 0;
  align-self: start;
  display: flex;
  flex-direction: column;
  padding: 14px 14px 14px 0;
  border-right: 1px solid var(--console-border);
  overflow: hidden;
}

.batch-command-panel {
  min-width: 0;
  padding: 14px 0 14px 18px;
}

.batch-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.batch-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-title {
  color: var(--console-text);
  font-size: 14px;
  font-weight: 650;
}

.device-count {
  margin-left: auto;
}

.manual-ip {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.batch-device-list {
  min-height: 0;
  flex: 1;
  display: grid;
  align-content: start;
  gap: 4px;
  width: 100%;
  padding-right: 4px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.batch-device-panel :deep(.el-empty) {
  flex: 1;
}

.batch-device-list :deep(.el-checkbox) {
  width: 100%;
  height: auto;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  transition: background-color 0.18s ease, border-color 0.18s ease;
}

.batch-device-list :deep(.el-checkbox:hover),
.batch-device-list :deep(.el-checkbox.is-checked) {
  border-color: #d7e6fb;
  background: var(--console-active);
}

.batch-device-list :deep(.el-checkbox__label) {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 10px;
  padding-left: 8px;
}

.batch-device-name {
  overflow: hidden;
  color: var(--console-text);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-device-ip {
  grid-column: 1 / 2;
  overflow: hidden;
  color: var(--console-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-device-status {
  grid-row: 1 / 3;
  grid-column: 2 / 3;
  align-self: center;
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  font-size: 12px;
}

.batch-device-status.normal {
  background: #ecfdf3;
  color: #16803c;
}

.batch-device-status.error {
  background: #fef2f2;
  color: #c24141;
}

.batch-summary {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 18px;
}

.summary-value {
  color: var(--console-text);
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.summary-label {
  color: var(--console-muted);
  font-size: 13px;
}

.batch-action-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.batch-command-mode-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.batch-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.batch-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 600;
}

.batch-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.batch-ssh-settings {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px 150px;
  gap: 12px;
  margin-bottom: 12px;
}

.batch-ssh-settings :deep(.el-input-number) {
  width: 100%;
}

.batch-ssh-command-select {
  min-width: 0;
}

.batch-ssh-results {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.batch-ssh-result-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 10px 12px;
  border: 1px solid var(--console-border);
  border-radius: 6px;
  background: var(--console-soft);
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 600;
}

.batch-ssh-result-summary .is-success {
  color: #2f855a;
}

.batch-ssh-result-summary .is-failed {
  color: #c24141;
}

.batch-ssh-result {
  margin-top: 0;
}

.batch-ssh-device-heading {
  min-width: 0;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px 8px;
}

.batch-ssh-device-heading span:last-child {
  color: var(--console-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
}

.batch-ssh-error {
  padding: 10px 12px;
  border-bottom: 1px solid #f4cccc;
  color: #b42318;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.batch-ssh-result .command-result-body {
  max-height: 260px;
}

.ssh-key-install-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.ssh-key-install-settings {
  display: grid;
  grid-template-columns: 180px 180px minmax(180px, 1fr);
  gap: 12px;
  align-items: end;
}

.ssh-key-install-settings :deep(.el-input-number) {
  width: 100%;
}

.ssh-key-install-settings.is-single {
  grid-template-columns: 180px minmax(220px, 1fr);
}

.ssh-key-install-summary {
  display: flex;
  align-items: baseline;
  gap: 7px;
  min-height: 32px;
  padding: 7px 10px;
  border: 1px solid var(--console-border);
  border-radius: 6px;
  background: var(--console-soft);
  color: var(--console-muted);
  font-size: 12px;
}

.ssh-key-install-summary strong {
  color: var(--console-text);
  font-size: 18px;
}

.ssh-key-install-settings.is-single .ssh-key-install-summary strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.single-operation-panel {
  min-height: 320px;
  padding: 8px 2px 24px;
}

.single-ssh-key-result {
  margin-top: 18px;
}

.ssh-key-result-message {
  padding: 10px 12px;
  border-bottom: 1px solid var(--console-border);
  color: #2f855a;
  font-size: 13px;
  font-weight: 600;
}

.ssh-key-result-message.is-error {
  color: #b42318;
}

.batch-editor {
  margin-top: 8px;
}

.log-view-tabs {
  min-width: 0;
}

.log-view-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.log-download-intro,
.log-record-toolbar,
.log-progress-header,
.log-run-settings {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.log-section-title {
  color: var(--console-text);
  font-size: 14px;
  font-weight: 650;
}

.log-section-description {
  margin-top: 4px;
  color: var(--console-muted);
  font-size: 12px;
}

.log-root-path {
  max-width: 52%;
  overflow: hidden;
  padding: 7px 10px;
  border: 1px solid var(--console-border);
  border-radius: 5px;
  background: var(--console-soft);
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-option-section {
  min-height: 150px;
  margin-top: 18px;
}

.log-option-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 9px;
  color: var(--console-text);
  font-size: 13px;
  font-weight: 650;
}

.log-folder-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.log-folder-grid :deep(.el-checkbox) {
  width: 100%;
  height: auto;
  min-height: 66px;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--console-border);
  border-radius: 6px;
  transition: border-color 0.18s ease, background-color 0.18s ease;
}

.log-folder-grid :deep(.el-checkbox:hover),
.log-folder-grid :deep(.el-checkbox.is-checked) {
  border-color: #bed6f7;
  background: var(--console-active);
}

.log-folder-grid :deep(.el-checkbox__label) {
  min-width: 0;
  white-space: normal;
}

.log-folder-copy {
  display: grid;
  gap: 4px;
}

.log-folder-copy strong {
  color: var(--console-text);
  font-size: 13px;
}

.log-folder-copy small {
  color: var(--console-muted);
  font-size: 12px;
  line-height: 1.45;
}

.log-run-settings {
  justify-content: flex-start;
  margin-top: 16px;
  padding: 14px 0;
  border-top: 1px solid var(--console-border);
}

.log-run-settings .batch-field {
  width: 150px;
}

.log-thread-summary {
  display: grid;
  gap: 3px;
  margin-right: auto;
  color: var(--console-muted);
  font-size: 12px;
}

.log-progress-panel {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--console-border);
}

.log-progress-panel > :deep(.el-progress) {
  margin-top: 14px;
}

.log-task-stats {
  display: flex;
  gap: 18px;
  margin-top: 8px;
  color: var(--console-muted);
  font-size: 12px;
}

.log-device-progress-list {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 9px;
  margin-top: 15px;
}

.log-device-progress-item {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--console-border);
  border-radius: 6px;
}

.log-device-progress-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 9px;
}

.log-device-progress-head > div {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.log-device-progress-head strong {
  overflow: hidden;
  color: var(--console-text);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-device-progress-head small,
.log-device-step {
  color: var(--console-muted);
  font-size: 12px;
}

.log-device-step {
  overflow: hidden;
  margin-top: 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-device-step.is-error {
  color: #c24141;
}

.log-device-step.is-warning {
  color: #b7791f;
}

.log-command-console {
  max-height: 360px;
  margin-top: 12px;
  overflow: auto;
  border: 1px solid #253244;
  border-radius: 6px;
  background: #111827;
  color: #dbeafe;
}

.log-command-console.is-record {
  max-height: 520px;
}

.log-command-console-title {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 8px 10px;
  border-bottom: 1px solid #253244;
  background: #182233;
  color: #f8fafc;
  font-size: 12px;
  font-weight: 650;
}

.log-command-entry {
  padding: 10px;
  border-bottom: 1px solid #253244;
}

.log-command-entry:last-child {
  border-bottom: 0;
}

.log-command-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 7px;
  color: #93c5fd;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.log-command-content,
.log-command-output {
  margin: 0;
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-command-output {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px dashed #334155;
  color: #86efac;
}

.log-command-output.is-error {
  color: #fca5a5;
}

.log-record-command-detail {
  padding: 8px 18px 18px 58px;
  text-align: left;
}

.log-record-toolbar {
  margin-bottom: 14px;
}

.log-record-table {
  width: 100%;
}

.log-record-folders {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-record-folders :deep(.el-tag + .el-tag) {
  margin-left: 4px;
}

.log-record-folder-tooltip {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 360px;
}

.log-record-path {
  display: block;
  overflow: hidden;
  color: #475569;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-record-pagination {
  justify-content: flex-end;
  margin-top: 14px;
}

.log-record-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.log-record-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.native-file-input {
  min-height: 32px;
  padding: 4px 0;
  color: var(--console-muted);
  font-size: 13px;
}

.batch-result-list {
  display: grid;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--console-border);
}

.batch-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
}

.batch-result-item:last-child {
  border-bottom: 0;
}

.result-title {
  color: var(--console-text);
  font-size: 13px;
  font-weight: 650;
}

.result-message {
  margin-top: 3px;
  color: var(--console-muted);
  font-size: 12px;
  word-break: break-word;
}

@media (max-width: 900px) {
  .device-control-view {
    padding: 0 14px;
  }

  .device-context {
    align-items: flex-start;
    flex-direction: column;
  }

  .device-meta {
    justify-content: flex-start;
  }

  .subsystem-version-toolbar,
  .subsystem-version-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .subsystem-version-actions {
    width: 100%;
  }

  .subsystem-version-actions :deep(.el-button) {
    flex: 1;
  }

  .version-capture-form {
    grid-template-columns: 1fr;
  }

  .batch-workspace {
    grid-template-columns: 1fr;
  }

  .batch-device-panel {
    height: clamp(320px, 45vh, 420px);
    padding-right: 0;
    border-right: none;
    border-bottom: 1px solid var(--console-border);
  }

  .batch-command-panel {
    padding-left: 0;
  }

  .batch-form-grid {
    grid-template-columns: 1fr;
  }

  .batch-ssh-settings {
    grid-template-columns: 1fr;
  }

  .ssh-key-install-settings {
    grid-template-columns: 1fr;
  }

  .log-download-intro,
  .log-run-settings,
  .log-progress-header,
  .log-record-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .log-root-path {
    max-width: 100%;
    width: 100%;
  }

  .log-folder-grid,
  .log-device-progress-list {
    grid-template-columns: 1fr;
  }

  .log-run-settings .batch-field {
    width: 100%;
  }

  .command-form-grid {
    grid-template-columns: 1fr;
  }

  .ssh-command-settings {
    grid-template-columns: 1fr;
  }

  .custom-command-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
