<template>
  <div class="device-control-view">
    <section class="device-context" :class="{ 'is-batch': isBatchMode }">
      <template v-if="isBatchMode">
        <div class="device-identity">
          <div class="device-copy">
            <span class="device-name">批量处理</span>
            <span class="device-ip">{{ selectedIps.length }} / {{ availableRobots.length }} 台设备已选择</span>
          </div>
        </div>

        <div class="device-meta">
          <span class="status-pill">多选模式</span>
          <span class="meta-item">{{ availableRobots.length }} 台可选设备</span>
        </div>
      </template>

      <template v-else>
        <div class="device-identity">
          <div class="device-copy">
            <span class="device-name">{{ currentDeviceName }}</span>
            <span class="device-address">
              <span class="inline-status" :class="currentServiceStatus">
                {{ formatServiceStatus(currentServiceStatus) }}
              </span>
              <span class="device-ip">{{ selectedIp || '未选择设备' }}</span>
            </span>
          </div>
        </div>

        <div class="device-meta">
          <el-tooltip content="设备信息" placement="left">
            <el-button
              :icon="Tickets"
              circle
              :disabled="!selectedIp"
              @click="openInfoDrawer"
            />
          </el-tooltip>
          <el-tooltip content="刷新状态" placement="left">
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
      <span>正在加载设备扫描结果...</span>
    </div>

    <section v-else class="workbench">
      <el-tabs v-model="activeTab" class="workbench-tabs" @tab-change="handleTabChange">
        <el-tab-pane label="设备控制" name="control">
          <DeviceControlPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="Protocol" name="protocol">
          <DeviceProtocolsPanel :ip="selectedIp" standalone />
        </el-tab-pane>

        <el-tab-pane label="文件管理" name="files">
          <DeviceFilesPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="测试数据" name="testing-data">
          <DeviceTestingDataPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="执行命令" name="command">
          <el-tabs v-model="singleCommandMode" class="command-mode-tabs" @tab-change="handleCommandModeChange">
            <el-tab-pane label="HTTP API" name="http">
              <section class="command-console">
                <div v-if="!selectedIp" class="panel-empty">
                  <el-empty description="请先选择一台设备" />
                </div>

                <template v-else>
                  <div class="command-form-grid">
                    <label class="command-field">
                      <span>方法</span>
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
                      执行
                    </el-button>
                    <el-button
                      v-if="singleCommandResult"
                      :disabled="singleCommandRunning"
                      @click="singleCommandResult = null"
                    >
                      清空结果
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
                        {{ singleCommandResult.success ? '成功' : '失败' }}
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
                  <el-empty description="请先选择一台设备" />
                </div>

                <template v-else>
                  <el-alert
                    v-if="sshCommandDatabaseError"
                    class="ssh-command-alert"
                    type="warning"
                    :closable="false"
                    :title="`自定义命令暂时不可用：${sshCommandDatabaseError}`"
                  />

                  <div class="ssh-command-settings">
                    <label class="command-field">
                      <span>常用 / 自定义命令</span>
                      <el-select
                        v-model="selectedSshCommandId"
                        class="ssh-command-preset-select"
                        filterable
                        clearable
                        :loading="sshCommandsLoading"
                        popper-class="ssh-command-select-popper"
                        placeholder="选择命令后自动填入"
                        @change="applySelectedSshCommand"
                      >
                        <el-option-group label="常用命令">
                          <el-option
                            v-for="item in builtinSshCommands"
                            :key="item.id"
                            :label="`[${item.tag}] ${item.name} · ${item.command}`"
                            :value="item.id"
                          >
                            <el-tooltip
                              :content="item.command"
                              placement="right"
                              popper-class="ssh-command-full-tooltip"
                              :show-after="400"
                            >
                              <div class="ssh-command-option">
                                <span class="ssh-command-option-name">{{ item.name }}</span>
                                <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                  {{ item.tag }}
                                </el-tag>
                                <span class="ssh-command-option-value">{{ item.command }}</span>
                              </div>
                            </el-tooltip>
                          </el-option>
                        </el-option-group>
                        <el-option-group v-if="customSshCommands.length" label="自定义命令">
                          <el-option
                            v-for="item in customSshCommands"
                            :key="item.id"
                            :label="`[${item.tag}] ${item.name} · ${item.command}`"
                            :value="item.id"
                          >
                            <el-tooltip
                              :content="item.command"
                              placement="right"
                              popper-class="ssh-command-full-tooltip"
                              :show-after="400"
                            >
                              <div class="ssh-command-option">
                                <span class="ssh-command-option-name">{{ item.name }}</span>
                                <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                  {{ item.tag }}
                                </el-tag>
                                <span class="ssh-command-option-value">{{ item.command }}</span>
                              </div>
                            </el-tooltip>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </label>
                    <label class="command-field ssh-timeout-field">
                      <span>超时时间（秒）</span>
                      <el-input-number v-model="sshCommandTimeout" :min="1" :max="300" controls-position="right" />
                    </label>
                  </div>

                  <label class="command-field">
                    <span class="command-field-title">
                      SSH 命令
                      <small>支持多条命令，可使用服务器变量 $DATE、$DATE_EPOCH</small>
                    </span>
                    <el-input
                      v-model="sshCommandText"
                      type="textarea"
                      :rows="5"
                      placeholder="例如：mount -o remount,rw /; timedatectl set-ntp false; ..."
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
                      执行 SSH 命令
                    </el-button>
                    <el-button
                      v-if="sshCommandResult || sshCommandExecutionError"
                      :disabled="sshCommandRunning"
                      @click="clearSshCommandOutput"
                    >
                      清空输出
                    </el-button>
                    <span class="command-shortcut">Ctrl + Enter 执行</span>
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
                        {{ sshCommandResult.success ? '执行成功' : `退出码 ${sshCommandResult.exit_code}` }}
                      </el-tag>
                    </div>
                    <div class="ssh-result-meta">
                      <span>退出码：{{ sshCommandResult.exit_code }}</span>
                      <span>耗时：{{ sshCommandResult.duration_ms }} ms</span>
                      <span>完成时间：{{ formatLogDate(sshCommandResult.finished_at) }}</span>
                      <span>
                        服务器 DATE：{{ sshCommandResult.environment?.DATE }}
                        <template v-if="sshCommandResult.environment?.DATE_TIMEZONE">
                          （{{ sshCommandResult.environment.DATE_TIMEZONE }}）
                        </template>
                      </span>
                      <span v-if="sshCommandResult.output_truncated">输出已截断</span>
                    </div>
                    <div class="ssh-output-section">
                      <div class="ssh-output-title">标准输出 stdout</div>
                      <pre class="command-result-body">{{ sshCommandResult.stdout || '(无输出)' }}</pre>
                    </div>
                    <div v-if="sshCommandResult.stderr" class="ssh-output-section is-stderr">
                      <div class="ssh-output-title">错误输出 stderr</div>
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
                      <el-tag size="small" type="danger">连接或执行失败</el-tag>
                    </div>
                    <pre class="command-result-body">{{ sshCommandExecutionError }}</pre>
                  </div>

                  <section class="custom-command-section">
                    <div class="custom-command-header">
                      <div>
                        <h3>自定义命令</h3>
                        <p>保存到 MongoDB，所有用户共享。</p>
                      </div>
                      <el-button
                        type="primary"
                        plain
                        :disabled="Boolean(sshCommandDatabaseError)"
                        @click="openCreateSshCommand"
                      >
                        新增命令
                      </el-button>
                    </div>

                    <el-table
                      v-loading="sshCommandsLoading"
                      :data="customSshCommands"
                      border
                      empty-text="暂无自定义命令"
                    >
                      <el-table-column prop="name" label="名称" min-width="150" />
                      <el-table-column label="属性" width="90">
                        <template #default="scope">
                          <el-tag size="small" :type="scope.row.tag === 'risk' ? 'danger' : 'info'">
                            {{ scope.row.tag }}
                          </el-tag>
                        </template>
                      </el-table-column>
                      <el-table-column prop="command" label="命令" min-width="260" show-overflow-tooltip />
                      <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
                      <el-table-column label="更新时间" width="180">
                        <template #default="scope">
                          {{ formatLogDate(scope.row.updated_at) }}
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="130" fixed="right">
                        <template #default="scope">
                          <el-button link type="primary" @click="openEditSshCommand(scope.row)">编辑</el-button>
                          <el-button link type="danger" @click="removeSshCommand(scope.row)">删除</el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </section>
                </template>
              </section>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane label="批量处理" name="batch">
          <div class="batch-workspace">
            <aside class="batch-device-panel">
              <div class="batch-panel-header">
                <span class="panel-title">目标设备</span>
                <span class="device-count">{{ availableRobots.length }}</span>
                <el-button
                  type="primary"
                  size="small"
                  link
                  @click="toggleSelectAll"
                >
                  {{ isAllSelected ? '取消全选' : '全选' }}
                </el-button>
              </div>

              <div class="manual-ip">
                <el-input
                  v-model="manualIpInput"
                  placeholder="输入 IP 后回车"
                  size="small"
                  @keyup.enter="addManualIp"
                />
                <el-button size="small" type="primary" @click="addManualIp">添加</el-button>
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
                  <span class="batch-device-name">{{ robot.name || '未命名设备' }}</span>
                  <span class="batch-device-ip">{{ robot.ip }}</span>
                  <span class="batch-device-status" :class="robot.service_status">
                    {{ formatServiceStatus(robot.service_status) }}
                  </span>
                </el-checkbox>
              </el-checkbox-group>

              <el-empty v-else description="暂无设备" :image-size="72" />
            </aside>

            <section class="batch-command-panel">
              <div class="batch-topbar">
                <div class="batch-summary">
                  <span class="summary-value">{{ selectedIps.length }}</span>
                  <span class="summary-label">台设备已选择</span>
                </div>
                <el-button
                  v-if="batchResults.length"
                  size="small"
                  text
                  @click="batchResults = []"
                >
                  清空结果
                </el-button>
              </div>

              <el-tabs v-model="batchActionTab" class="batch-action-tabs">
                <el-tab-pane label="改文件" name="edit">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>参考设备</span>
                      <el-select v-model="batchReferenceIp" placeholder="选择要读取的设备">
                        <el-option
                          v-for="robot in selectedRobots"
                          :key="`ref-${robot.ip}`"
                          :label="`${robot.name || robot.ip} · ${robot.ip}`"
                          :value="robot.ip"
                        />
                      </el-select>
                    </label>
                    <label class="batch-field">
                      <span>文件路径</span>
                      <el-input v-model="batchEditPath" placeholder="/data/file.json" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button :loading="batchReading" :disabled="!canReadBatchFile" @click="readBatchFile">
                      打开文件
                    </el-button>
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canWriteBatchFile"
                      @click="runBatchEditReplace"
                    >
                      保存并批量替换
                    </el-button>
                  </div>
                  <el-input
                    v-model="batchEditContent"
                    class="batch-editor"
                    type="textarea"
                    :rows="14"
                    placeholder="先从参考设备打开文件，编辑后保存到选中的设备"
                  />
                </el-tab-pane>

                <el-tab-pane label="传文件" name="upload">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>目标路径</span>
                      <el-input v-model="batchUploadPath" placeholder="/data/config.json" />
                    </label>
                    <label class="batch-field">
                      <span>本地文件</span>
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
                      批量上传
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane label="下载文件" name="download">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>远程路径</span>
                      <el-input v-model="batchDownloadPath" placeholder="/data 或 /data/file.csv" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchDownload"
                      @click="runBatchDownload"
                    >
                      批量下载
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane label="下载 Log" name="logs">
                  <el-tabs v-model="logViewTab" class="log-view-tabs" @tab-change="handleLogViewChange">
                    <el-tab-pane label="选择下载" name="select">
                      <div class="log-download-intro">
                        <div>
                          <div class="log-section-title">诊断 Log 下载到服务器</div>
                          <div class="log-section-description">
                            按 flex_diagnostics.sh 的收集方式在设备端打包，再保存到服务器目录。
                          </div>
                        </div>
                        <div v-if="logDownloadRoot" class="log-root-path">{{ logDownloadRoot }}</div>
                      </div>

                      <div v-loading="logOptionsLoading" class="log-option-section">
                        <div class="log-option-heading">
                          <span>选择 Log 文件夹</span>
                          <el-button size="small" text @click="toggleAllLogFolders">
                            {{ areAllLogFoldersSelected ? '取消全选' : '全选' }}
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
                          <span>并发线程数</span>
                          <el-input-number
                            v-model="logConcurrency"
                            :min="1"
                            :max="logMaxConcurrency"
                            controls-position="right"
                          />
                        </label>
                        <div class="log-thread-summary">
                          <span>{{ selectedIps.length }} 台设备</span>
                          <span>最多 {{ effectiveLogConcurrency }} 个线程同时下载</span>
                        </div>
                        <el-button
                          type="primary"
                          :loading="logTaskStarting"
                          :disabled="!canStartLogDownload"
                          @click="startLogDownload"
                        >
                          开始下载 Log
                        </el-button>
                      </div>

                      <section v-if="activeLogTask" class="log-progress-panel">
                        <div class="log-progress-header">
                          <div>
                            <div class="log-section-title">批量下载进度</div>
                            <div class="log-section-description">
                              {{ activeLogTask.completed_devices }} / {{ activeLogTask.total_devices }} 台完成，
                              {{ activeLogTask.active_workers }} 个线程运行中
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
                          <span>成功 {{ activeLogTask.successful_devices }}</span>
                          <span>警告 {{ activeLogTask.warning_devices || 0 }}</span>
                          <span>失败 {{ activeLogTask.failed_devices }}</span>
                          <span>并发 {{ activeLogTask.concurrency || '-' }}</span>
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
                              <div class="log-command-console-title">实时执行命令</div>
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

                    <el-tab-pane label="下载记录" name="records">
                      <div class="log-record-toolbar">
                        <div>
                          <div class="log-section-title">服务器下载记录</div>
                          <div class="log-section-description">记录保存正在下载和已经下载的Logs记录。</div>
                        </div>
                        <el-button :icon="Refresh" :loading="logRecordsLoading" @click="loadLogRecords">
                          刷新
                        </el-button>
                      </div>

                      <el-table
                        v-loading="logRecordsLoading"
                        :data="logRecords"
                        :cell-style="getLogRecordTableCellStyle"
                        :header-cell-style="getLogRecordTableCellStyle"
                        class="log-record-table"
                        empty-text="暂无下载记录"
                      >
                        <el-table-column type="expand" width="48">
                          <template #default="scope">
                            <div class="log-record-command-detail">
                              <div class="log-section-title">执行命令记录</div>
                              <div v-if="scope.row.command_logs?.length" class="log-command-console is-record">
                                <article
                                  v-for="commandLog in getDisplayCommandLogs(scope.row.command_logs)"
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
                              <el-empty v-else description="暂无命令记录" :image-size="48" />
                            </div>
                          </template>
                        </el-table-column>
                        <el-table-column label="设备名" prop="device_name" min-width="150" />
                        <el-table-column label="IP" prop="robot_ip" width="132" />
                        <el-table-column label="Log 文件夹" min-width="220" align="left" header-align="left">
                          <template #default="scope">
                            <el-tooltip placement="top" :show-after="300">
                              <template #content>
                                <div class="log-record-folder-tooltip">
                                  <el-tag
                                    v-for="folder in scope.row.selected_folders"
                                    :key="`${scope.row._id}-tooltip-${folder.key}`"
                                    size="small"
                                    type="info"
                                  >
                                    {{ folder.label }}
                                  </el-tag>
                                </div>
                              </template>
                              <div class="log-record-folders">
                                <el-tag
                                  v-for="folder in scope.row.selected_folders"
                                  :key="`${scope.row._id}-${folder.key}`"
                                  size="small"
                                  type="info"
                                >
                                  {{ folder.label }}
                                </el-tag>
                              </div>
                            </el-tooltip>
                          </template>
                        </el-table-column>
                        <el-table-column label="服务器文件目录" min-width="320">
                          <template #default="scope">
                            <el-tooltip :content="scope.row.archive_path || scope.row.server_directory" placement="top">
                              <span class="log-record-path">{{ scope.row.archive_path || scope.row.server_directory }}</span>
                            </el-tooltip>
                          </template>
                        </el-table-column>
                        <el-table-column label="文件大小" width="110">
                          <template #default="scope">{{ formatBytes(scope.row.archive_size) }}</template>
                        </el-table-column>
                        <el-table-column label="进度" width="150">
                          <template #default="scope">
                            <el-progress
                              :percentage="scope.row.progress"
                              :status="getRecordProgressStatus(scope.row)"
                              :stroke-width="16"
                              :text-inside="true"
                            />
                          </template>
                        </el-table-column>
                        <el-table-column label="状态" width="100">
                          <template #default="scope">
                            <el-tag v-if="scope.row.file_deleted_at" size="small" type="info">已删除</el-tag>
                            <el-tooltip
                              v-else-if="scope.row.status === 'warning'"
                              :content="scope.row.cleanup_error || scope.row.current_step"
                              placement="top"
                            >
                              <el-tag size="small" type="warning">清理警告</el-tag>
                            </el-tooltip>
                            <el-tooltip v-else-if="scope.row.error" :content="scope.row.error" placement="top">
                              <el-tag size="small" :type="getLogStatusTagType(scope.row.status)">
                                {{ getLogStatusLabel(scope.row.status) }}
                              </el-tag>
                            </el-tooltip>
                            <el-tag v-else size="small" :type="getLogStatusTagType(scope.row.status)">
                              {{ getLogStatusLabel(scope.row.status) }}
                            </el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column label="下载时间" width="180">
                          <template #default="scope">
                            {{ formatLogDate(scope.row.downloaded_at || scope.row.finished_at || scope.row.started_at) }}
                          </template>
                        </el-table-column>
                        <el-table-column label="操作" width="128" fixed="right">
                          <template #default="scope">
                            <div class="log-record-actions">
                              <el-button
                                type="primary"
                                link
                                :disabled="!scope.row.file_available"
                                @click="downloadServerLog(scope.row)"
                              >
                                下载
                              </el-button>
                              <el-button
                                type="danger"
                                link
                                :loading="deletingLogRecordId === scope.row._id"
                                :disabled="!scope.row.file_available"
                                @click="deleteServerLog(scope.row)"
                              >
                                删除
                              </el-button>
                            </div>
                          </template>
                        </el-table-column>
                      </el-table>

                      <el-pagination
                        v-if="logRecordTotal > logRecordPageSize"
                        v-model:current-page="logRecordPage"
                        :page-size="logRecordPageSize"
                        :total="logRecordTotal"
                        layout="prev, pager, next, total"
                        class="log-record-pagination"
                        @current-change="loadLogRecords"
                      />
                    </el-tab-pane>
                  </el-tabs>
                </el-tab-pane>

                <el-tab-pane label="执行命令" name="command">
                  <el-tabs
                    v-model="batchCommandMode"
                    class="batch-command-mode-tabs"
                    @tab-change="handleBatchCommandModeChange"
                  >
                    <el-tab-pane label="HTTP API" name="http">
                      <div class="batch-form-grid">
                        <label class="batch-field">
                          <span>方法</span>
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
                          批量执行 HTTP API
                        </el-button>
                      </div>
                    </el-tab-pane>

                    <el-tab-pane label="SSH COMMAND" name="ssh">
                      <el-alert
                        v-if="sshCommandDatabaseError"
                        class="ssh-command-alert"
                        type="warning"
                        :closable="false"
                        :title="`自定义命令暂时不可用：${sshCommandDatabaseError}`"
                      />

                      <div class="batch-ssh-settings">
                        <label class="batch-field batch-ssh-command-select">
                          <span>常用 / 自定义命令</span>
                          <el-select
                            v-model="batchSshSelectedCommandId"
                            class="ssh-command-preset-select"
                            filterable
                            clearable
                            :loading="sshCommandsLoading"
                            popper-class="ssh-command-select-popper"
                            placeholder="选择命令后自动填入"
                            @change="applySelectedBatchSshCommand"
                          >
                            <el-option-group label="常用命令">
                              <el-option
                                v-for="item in builtinSshCommands"
                                :key="item.id"
                                :label="`[${item.tag}] ${item.name} · ${item.command}`"
                                :value="item.id"
                              >
                                <el-tooltip
                                  :content="item.command"
                                  placement="right"
                                  popper-class="ssh-command-full-tooltip"
                                  :show-after="400"
                                >
                                  <div class="ssh-command-option">
                                    <span class="ssh-command-option-name">{{ item.name }}</span>
                                    <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                      {{ item.tag }}
                                    </el-tag>
                                    <span class="ssh-command-option-value">{{ item.command }}</span>
                                  </div>
                                </el-tooltip>
                              </el-option>
                            </el-option-group>
                            <el-option-group v-if="customSshCommands.length" label="自定义命令">
                              <el-option
                                v-for="item in customSshCommands"
                                :key="item.id"
                                :label="`[${item.tag}] ${item.name} · ${item.command}`"
                                :value="item.id"
                              >
                                <el-tooltip
                                  :content="item.command"
                                  placement="right"
                                  popper-class="ssh-command-full-tooltip"
                                  :show-after="400"
                                >
                                  <div class="ssh-command-option">
                                    <span class="ssh-command-option-name">{{ item.name }}</span>
                                    <el-tag size="small" :type="item.tag === 'risk' ? 'danger' : 'info'">
                                      {{ item.tag }}
                                    </el-tag>
                                    <span class="ssh-command-option-value">{{ item.command }}</span>
                                  </div>
                                </el-tooltip>
                              </el-option>
                            </el-option-group>
                          </el-select>
                        </label>
                        <label class="batch-field">
                          <span>超时（秒）</span>
                          <el-input-number v-model="batchSshTimeout" :min="1" :max="300" controls-position="right" />
                        </label>
                        <label class="batch-field">
                          <span>并发设备数</span>
                          <el-input-number v-model="batchSshConcurrency" :min="1" :max="20" controls-position="right" />
                        </label>
                      </div>

                      <label class="batch-field">
                        <span class="command-field-title">
                          SSH 命令
                          <small>对 {{ selectedIps.length }} 台已选设备执行，可使用 $DATE、$DATE_EPOCH</small>
                        </span>
                        <el-input
                          v-model="batchSshCommandText"
                          type="textarea"
                          :rows="6"
                          placeholder="例如：date"
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
                          批量执行 SSH 命令
                        </el-button>
                        <el-button
                          v-if="batchSshResults.length"
                          :disabled="batchSshRunning"
                          @click="batchSshResults = []"
                        >
                          清空输出
                        </el-button>
                        <span class="command-shortcut">Ctrl + Enter 执行</span>
                      </div>

                      <div v-if="batchSshResults.length" class="batch-ssh-results">
                        <div class="batch-ssh-result-summary">
                          <span>共 {{ batchSshResults.length }} 台</span>
                          <span class="is-success">成功 {{ batchSshSuccessCount }} 台</span>
                          <span class="is-failed">失败 {{ batchSshFailedCount }} 台</span>
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
                              {{ result.success ? '执行成功' : (result.exit_code === null ? '连接失败' : `退出码 ${result.exit_code}`) }}
                            </el-tag>
                          </div>
                          <div class="ssh-result-meta">
                            <span>退出码：{{ result.exit_code ?? '-' }}</span>
                            <span>耗时：{{ result.duration_ms }} ms</span>
                            <span v-if="result.environment?.DATE">
                              DATE：{{ result.environment.DATE }}
                              <template v-if="result.environment.DATE_TIMEZONE">
                                （{{ result.environment.DATE_TIMEZONE }}）
                              </template>
                            </span>
                          </div>
                          <div v-if="result.error" class="batch-ssh-error">{{ result.error }}</div>
                          <div class="ssh-output-section">
                            <div class="ssh-output-title">标准输出 stdout</div>
                            <pre class="command-result-body">{{ result.stdout || '(无输出)' }}</pre>
                          </div>
                          <div v-if="result.stderr" class="ssh-output-section is-stderr">
                            <div class="ssh-output-title">错误输出 stderr</div>
                            <pre class="command-result-body">{{ result.stderr }}</pre>
                          </div>
                        </article>
                      </div>
                    </el-tab-pane>
                  </el-tabs>
                </el-tab-pane>
              </el-tabs>

              <div
                v-if="batchResults.length && !(batchActionTab === 'command' && batchCommandMode === 'ssh')"
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
      :title="editingSshCommandId ? '编辑自定义命令' : '新增自定义命令'"
      width="620px"
      destroy-on-close
    >
      <div class="ssh-command-dialog-form">
        <label class="command-field">
          <span>命令名称</span>
          <el-input v-model="sshCommandForm.name" maxlength="80" show-word-limit placeholder="例如：查看 Robot Server 日志" />
        </label>
        <label class="command-field">
          <span>命令属性</span>
          <el-select v-model="sshCommandForm.tag">
            <el-option label="general（普通命令）" value="general" />
            <el-option label="risk（风险命令）" value="risk" />
          </el-select>
        </label>
        <label class="command-field">
          <span class="command-field-title">
            命令内容
            <small>支持多行命令或使用 ; 串联执行</small>
          </span>
          <el-input v-model="sshCommandForm.command" type="textarea" :rows="8" maxlength="20000" show-word-limit />
        </label>
        <label class="command-field">
          <span>说明</span>
          <el-input v-model="sshCommandForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </label>
      </div>
      <template #footer>
        <el-button @click="sshCommandDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sshCommandSaving" @click="saveSshCommand">保存</el-button>
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
        <el-button @click="infoDrawerVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="infoRefreshing"
          @click="refreshDeviceInfo"
        >刷新</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loading, Refresh, Tickets } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  robotApi,
  type RobotInfo,
  type RobotLogCommandEntry,
  type RobotLogDownloadRecord,
  type RobotLogDownloadStatus,
  type RobotLogDownloadTask,
  type RobotLogFolderOption,
  type RobotSshCommand,
  type RobotSshCommandExecuteResult
} from '@/scripts/api'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import DeviceControlPanel from '@/views/devices/components/DeviceControlPanel.vue'
import DeviceProtocolsPanel from '@/views/devices/components/DeviceProtocolsPanel.vue'
import DeviceFilesPanel from '@/views/devices/components/DeviceFilesPanel.vue'
import DeviceTestingDataPanel from '@/views/devices/components/DeviceTestingDataPanel.vue'
import DeviceInfoPanel from '@/views/devices/components/DeviceInfoPanel.vue'

const route = useRoute()
const router = useRouter()
const robotScanStore = useRobotScanStore()

const activeTab = ref('control')
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
const batchResults = ref<BatchOperationResult[]>([])
const logViewTab = ref('select')
const logFolderOptions = ref<RobotLogFolderOption[]>([])
const selectedLogFolderKeys = ref<string[]>([])
const logOptionsLoading = ref(false)
const logDownloadRoot = ref('')
const logMaxConcurrency = ref(8)
const logConcurrency = ref(4)
const logTaskStarting = ref(false)
const activeLogTask = ref<RobotLogDownloadTask | null>(null)
const logRecords = ref<RobotLogDownloadRecord[]>([])
const logRecordsLoading = ref(false)
const logRecordPage = ref(1)
const logRecordPageSize = 20
const logRecordTotal = ref(0)
const deletingLogRecordId = ref('')
let logPollTimer: ReturnType<typeof setTimeout> | null = null
let logRecordPollTimer: ReturnType<typeof setTimeout> | null = null
const singleCommandMethod = ref('GET')
const singleCommandPath = ref('/health')
const singleCommandBody = ref('')
const singleCommandRunning = ref(false)
const singleCommandResult = ref<SingleCommandResult | null>(null)
const singleCommandMode = ref('http')
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

const RISK_COMMAND_WARNING = '该命令存在风险，请确保执行设备为测试工装！'

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
  return currentDevice.value?.name?.trim() || '未命名设备'
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
  return selectedIp.value ? `设备信息 - ${selectedIp.value}` : '设备信息'
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
  if (status === 'success') return '成功'
  if (status === 'skipped') return '跳过'
  return '失败'
}

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail?.error
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

async function runForSelectedDevices(action: string, runner: (ip: string) => Promise<string>) {
  if (selectedIps.value.length === 0) {
    ElMessage.warning('请先选择设备')
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
      ElMessage.warning(`${action} 完成：成功 ${success}，跳过 ${skipped}，失败 ${failed}`)
    } else if (skipped > 0) {
      ElMessage.warning(`${action} 完成：成功 ${success}，跳过 ${skipped}`)
    } else {
      ElMessage.success(`${action} 完成：成功 ${success}`)
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
    ElMessage.success('文件已打开')
  } catch (error: any) {
    ElMessage.error('打开文件失败: ' + normalizeError(error))
  } finally {
    batchReading.value = false
  }
}

async function runBatchEditReplace() {
  const path = batchEditPath.value.trim()
  if (!path) return
  await runForSelectedDevices('批量替换文件', async (ip) => {
    const response = await robotApi.writeFile(ip, path, batchEditContent.value, { createIfMissing: false })
    if (response.data.data?.skipped) {
      throw buildSkippedBatchOperation(`目标文件不存在，已跳过 ${path}`)
    }
    return `已写入 ${path}`
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
  await runForSelectedDevices('批量上传文件', async (ip) => {
    await robotApi.uploadFile(ip, path, file)
    return `已上传到 ${path}`
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
  await runForSelectedDevices('批量下载文件', async (ip) => {
    const response = await robotApi.downloadFile(ip, path)
    const fallbackName = `${ip.replace(/\./g, '-')}-${basename(path)}`
    const filename = parseDownloadFilename(response.headers['content-disposition'], fallbackName)
    saveBlob(response.data, filename)
    return `已下载 ${path}`
  })
}

function getLogStatusLabel(status: RobotLogDownloadStatus) {
  const labels: Record<RobotLogDownloadStatus, string> = {
    queued: '等待中',
    running: '下载中',
    success: '成功',
    warning: '清理警告',
    failed: '失败',
    completed: '已完成',
    completed_with_warnings: '完成有警告',
    completed_with_errors: '部分失败'
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
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

function formatBytes(value?: number | null) {
  const bytes = Number(value || 0)
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const amount = bytes / Math.pow(1024, unitIndex)
  return `${amount.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function getRecordProgressStatus(record: RobotLogDownloadRecord) {
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

function getLogRecordTableCellStyle({ column }: { column: { label?: string } }) {
  return { textAlign: column.label === 'Log 文件夹' ? 'left' : 'center' }
}

function formatCommandTime(value?: string | null) {
  if (!value) return '--:--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
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
  if (status === 'running') return '执行中'
  if (status === 'success') return '成功'
  return '失败'
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
    ElMessage.error('加载 Log 目录失败: ' + normalizeError(error))
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

async function pollLogTask(taskId: string, showError = false) {
  clearLogPollTimer()
  try {
    const response = await robotApi.getLogDownloadTask(taskId)
    activeLogTask.value = response.data
    mergeLogTaskIntoRecords(response.data)
    if (['queued', 'running'].includes(response.data.status)) {
      logPollTimer = setTimeout(() => pollLogTask(taskId), 1000)
      return
    }
    if (response.data.failed_devices > 0) {
      ElMessage.warning(
        `Log 下载完成：成功 ${response.data.successful_devices}，警告 ${response.data.warning_devices}，失败 ${response.data.failed_devices}`
      )
    } else if (response.data.warning_devices > 0) {
      ElMessage.warning(`Log 下载完成：成功 ${response.data.successful_devices}，清理警告 ${response.data.warning_devices}`)
    } else {
      ElMessage.success(`Log 下载完成：成功 ${response.data.successful_devices}`)
    }
  } catch (error: any) {
    if (showError) ElMessage.error('获取 Log 下载进度失败: ' + normalizeError(error))
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
    ElMessage.success('Log 下载任务已启动')
    await pollLogTask(response.data.task_id, true)
  } catch (error: any) {
    ElMessage.error('启动 Log 下载失败: ' + normalizeError(error))
  } finally {
    logTaskStarting.value = false
  }
}

async function loadLogRecords() {
  if (logRecordsLoading.value) return
  clearLogRecordPollTimer()
  logRecordsLoading.value = true
  try {
    const response = await robotApi.getLogDownloadRecords({
      page: logRecordPage.value,
      pageSize: logRecordPageSize
    })
    logRecords.value = response.data.records
    logRecordTotal.value = response.data.total
  } catch (error: any) {
    ElMessage.error('加载 Log 下载记录失败: ' + normalizeError(error))
  } finally {
    logRecordsLoading.value = false
    scheduleLogRecordPolling()
  }
}

async function handleLogViewChange(tabName: string | number) {
  if (tabName === 'records') {
    await loadLogRecords()
    return
  }
  clearLogRecordPollTimer()
}

function clearLogRecordPollTimer() {
  if (logRecordPollTimer) {
    clearTimeout(logRecordPollTimer)
    logRecordPollTimer = null
  }
}

function scheduleLogRecordPolling() {
  clearLogRecordPollTimer()
  if (batchActionTab.value !== 'logs' || logViewTab.value !== 'records') return

  const activeTaskId = ['queued', 'running'].includes(activeLogTask.value?.status || '')
    ? activeLogTask.value?.task_id
    : ''
  const hasIndependentRunningTask = logRecords.value.some(record => (
    ['queued', 'running'].includes(record.status) && record.task_id !== activeTaskId
  ))
  if (hasIndependentRunningTask) {
    logRecordPollTimer = setTimeout(() => pollVisibleLogRecordTasks(), 1000)
  }
}

function mergeLogTaskIntoRecords(task: RobotLogDownloadTask) {
  const recordsById = new Map(logRecords.value.map(record => [record._id, record]))
  for (const device of task.devices) {
    const existingRecord = recordsById.get(device._id)
    if (existingRecord) Object.assign(existingRecord, device)
  }
}

async function pollVisibleLogRecordTasks() {
  clearLogRecordPollTimer()
  if (batchActionTab.value !== 'logs' || logViewTab.value !== 'records') return

  const activeTaskId = ['queued', 'running'].includes(activeLogTask.value?.status || '')
    ? activeLogTask.value?.task_id
    : ''
  const taskIds = Array.from(new Set(
    logRecords.value
      .filter(record => ['queued', 'running'].includes(record.status) && record.task_id !== activeTaskId)
      .map(record => record.task_id)
  ))
  if (!taskIds.length) return

  const results = await Promise.allSettled(taskIds.map(taskId => robotApi.getLogDownloadTask(taskId)))
  for (const result of results) {
    if (result.status === 'fulfilled') mergeLogTaskIntoRecords(result.value.data)
  }
  scheduleLogRecordPolling()
}

function downloadServerLog(record: RobotLogDownloadRecord) {
  if (!record.file_available) return
  const anchor = document.createElement('a')
  anchor.href = robotApi.getServerLogDownloadUrl(record._id)
  anchor.download = record.archive_name || 'diagnostics.tar.gz'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

async function deleteServerLog(record: RobotLogDownloadRecord) {
  if (!record.file_available) return
  try {
    await ElMessageBox.confirm(
      `确认删除服务器上的 ${record.archive_name || 'Log 文件'}？下载记录会保留。`,
      '删除服务器 Log',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  deletingLogRecordId.value = record._id
  try {
    const response = await robotApi.deleteServerLog(record._id)
    record.file_available = false
    record.file_deleted_at = response.data.file_deleted_at
    const activeRecord = activeLogTask.value?.devices.find(device => device._id === record._id)
    if (activeRecord) {
      activeRecord.file_available = false
      activeRecord.file_deleted_at = response.data.file_deleted_at
    }
    ElMessage.success('服务器 Log 已删除，下载记录已保留')
  } catch (error: any) {
    ElMessage.error('删除服务器 Log 失败: ' + normalizeError(error))
  } finally {
    deletingLogRecordId.value = ''
  }
}

function parseCommandBody(text: string): Record<string, unknown> | undefined {
  const trimmed = text.trim()
  if (!trimmed) return undefined
  const parsed = JSON.parse(trimmed)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Body JSON 必须是对象')
  }
  return parsed as Record<string, unknown>
}

async function runSingleCommand() {
  if (!selectedIp.value) return
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(singleCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || 'Body JSON 格式错误')
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
      ElMessage.success('命令执行成功')
    } else {
      ElMessage.error(result?.error || '命令执行失败')
    }
  } catch (error: any) {
    singleCommandResult.value = {
      method,
      path,
      success: false,
      error: normalizeError(error)
    }
    ElMessage.error('命令执行失败: ' + normalizeError(error))
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
      : (response.data.error || 'MongoDB 连接失败')

    const allCommands = [...builtinSshCommands.value, ...customSshCommands.value]
    const selectedExists = allCommands.some(item => item.id === selectedSshCommandId.value)
    if (!selectedExists) {
      selectedSshCommandId.value = allCommands.find(item => item.command === 'date')?.id || allCommands[0]?.id || ''
      applySelectedSshCommand()
    }
  } catch (error: any) {
    sshCommandDatabaseError.value = normalizeError(error)
    if (showError) ElMessage.error('加载 SSH 命令失败: ' + sshCommandDatabaseError.value)
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
      RISK_COMMAND_WARNING,
      '风险命令提醒',
      {
        type: 'warning',
        confirmButtonText: '确认执行',
        cancelButtonText: '取消',
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
      ElMessage.success('SSH 命令执行成功')
    } else {
      ElMessage.warning(`SSH 命令已结束，退出码 ${response.data.exit_code}`)
    }
  } catch (error: any) {
    sshCommandExecutionError.value = normalizeError(error)
    ElMessage.error('SSH 命令执行失败: ' + sshCommandExecutionError.value)
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
    ElMessage.warning('请输入命令名称')
    return
  }
  if (!payload.command) {
    ElMessage.warning('请输入命令内容')
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
    ElMessage.success(editingSshCommandId.value ? '自定义命令已更新' : '自定义命令已新增')
  } catch (error: any) {
    ElMessage.error('保存自定义命令失败: ' + normalizeError(error))
  } finally {
    sshCommandSaving.value = false
  }
}

async function removeSshCommand(command: RobotSshCommand) {
  try {
    await ElMessageBox.confirm(
      `确定删除自定义命令“${command.name}”吗？`,
      '删除自定义命令',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await robotApi.deleteSshCommand(command.id)
    if (selectedSshCommandId.value === command.id) {
      selectedSshCommandId.value = ''
    }
    await loadSshCommands(false)
    ElMessage.success('自定义命令已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除自定义命令失败: ' + normalizeError(error))
  }
}

async function runBatchCommand() {
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(batchCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || 'Body JSON 格式错误')
    return
  }

  const path = batchCommandPath.value.trim()
  await runForSelectedDevices('批量执行命令', async (ip) => {
    const response = await robotApi.executeCommands({
      ips: [ip],
      method: batchCommandMethod.value,
      path,
      body,
      timeout: 30
    })
    const result = response.data.results?.[0]
    if (!result?.success) {
      throw new Error(result?.error || `HTTP ${result?.status_code || '失败'}`)
    }
    return `命令已执行 ${batchCommandMethod.value} ${path}`
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
      ElMessage.warning(`批量 SSH 执行完成：成功 ${response.data.success_count} 台，失败 ${response.data.failed_count} 台`)
    } else {
      ElMessage.success(`批量 SSH 执行成功：${response.data.success_count} 台设备`)
    }
  } catch (error: any) {
    ElMessage.error('批量 SSH 命令执行失败: ' + normalizeError(error))
  } finally {
    batchSshRunning.value = false
  }
}

async function refreshRobots() {
  refreshing.value = true
  try {
    await robotScanStore.refreshScan({ silent: false })
    syncRobotsFromStore()
    selectFallbackDevice()
  } catch (error: any) {
    ElMessage.error('刷新设备失败: ' + (error.message || '未知错误'))
  } finally {
    refreshing.value = false
  }
}

function openInfoDrawer() {
  if (!selectedIp.value) return
  infoDrawerVisible.value = true
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

function handleTabChange(tabName: string | number) {
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
}

function formatServiceStatus(status: RobotInfo['service_status']) {
  const statusMap: Record<RobotInfo['service_status'], string> = {
    normal: '正常',
    error: '异常',
    unknown: '未知'
  }
  return statusMap[status] || '未知'
}

function getRobotDisplayName(ip: string) {
  return availableRobots.value.find(robot => robot.ip === ip)?.name?.trim() || '未命名设备'
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

watch(batchActionTab, async (tabName) => {
  if (tabName !== 'logs') {
    clearLogRecordPollTimer()
  }
  if (tabName === 'logs') {
    await loadLogFolderOptions()
    if (logViewTab.value === 'records') await loadLogRecords()
  }
  if (tabName === 'command' && batchCommandMode.value === 'ssh') {
    if (builtinSshCommands.value.length === 0) await loadSshCommands()
    ensureBatchSshCommandSelection()
  }
})

onBeforeUnmount(() => {
  clearLogPollTimer()
  clearLogRecordPollTimer()
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
  flex: none;
  color: #1f2a37;
  font-weight: 600;
}

.ssh-command-option :deep(.el-tag) {
  flex: none;
}

.ssh-command-option-value {
  min-width: 0;
  overflow: hidden;
  color: #6b7280;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
