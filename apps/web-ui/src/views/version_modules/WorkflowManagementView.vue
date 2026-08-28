<template>
  <div class="versions-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">V</div>
        <div>
          <strong>Productions</strong>
          <span>Versions</span>
        </div>
      </div>

      <div class="sidebar-note">
        <div class="sidebar-note-title">
          <span class="status-dot" :class="dataSourceStatusClass"></span>
          <strong>{{ dataSourceStatusTitle }}</strong>
          <button
            type="button"
            class="sidebar-note-toggle"
            :class="{ 'is-expanded': dataSourceDetailsExpanded }"
            :aria-label="w(dataSourceDetailsExpanded ? 'collapseDataSources' : 'expandDataSources')"
            :aria-expanded="dataSourceDetailsExpanded"
            :title="w(dataSourceDetailsExpanded ? 'collapseDataSources' : 'expandDataSources')"
            @click="dataSourceDetailsExpanded = !dataSourceDetailsExpanded"
          >
            <el-icon><ArrowDown /></el-icon>
          </button>
        </div>
        <template v-if="dataSourceDetailsExpanded">
          <span class="sidebar-note-detail" :title="dataSourceErrorDetail">{{ dataSourceStatusDetail }}</span>
          <div v-if="duroConnectionStatus && !dataSourcesChecking" class="sidebar-note-credential">
            <span :class="{ 'is-expiring': duroApiKeyExpiring }">{{ duroApiKeyExpiryText }}</span>
            <button type="button" @click="openDuroApiKeyDialog">{{ w('updateDuroApiKey') }}</button>
          </div>
        </template>
      </div>

      <nav class="main-nav" :aria-label="w('mainNavigation')">
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'workflows' }"
          type="button"
          @click="selectVersionModule('workflows')"
        >
          <el-icon><Connection /></el-icon>
          {{ w('workflows') }}
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'sop' }"
          type="button"
          @click="selectVersionModule('sop')"
        >
          <el-icon><FolderOpened /></el-icon>
          SOP
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'duro' }"
          type="button"
          @click="selectVersionModule('duro')"
        >
          <el-icon><Box /></el-icon>
          Duro
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'accessory-materials' }"
          type="button"
          @click="selectVersionModule('accessory-materials')"
        >
          <el-icon><Files /></el-icon>
          {{ t('versions.supplies.title') }}
        </button>
      </nav>

      <div class="versions-auth-menu">
        <AuthUserMenu variant="dark" dropdown-placement="top" />
      </div>
    </aside>

    <main v-if="activeModule === 'workflows'" class="main-content">
      <header class="versions-topbar">
        <div>
          <p class="eyebrow">VERSION AUTOMATION</p>
          <h1>{{ w('title') }}</h1>
          <p>{{ w('subtitle') }}</p>
        </div>
        <div class="versions-topbar-actions">
          <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">{{ w('newWorkflow') }}</el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadWorkflows">{{ t('common.actions.refresh') }}</el-button>
        </div>
      </header>

      <section
        class="workflow-attention-board"
        :class="{ 'is-collapsed': !attentionBoardExpanded }"
        :aria-label="w('attentionOverview')"
      >
        <div class="attention-board-header">
          <div class="attention-board-title panel-heading-copy">
            <div>
              <span>ALERTS</span>
              <strong>{{ w('alertBoard') }}</strong>
            </div>
            <small v-if="!attentionBoardExpanded" class="attention-board-summary">
              {{ w('attentionSummary', { workflows: workflows.length, warnings: totalWarningCount, pending: pendingWorkflowSummaries.length }) }}
              <template v-if="!pendingWorkflowSummaries.length"> · {{ w('nothingToHandle') }}</template>
            </small>
          </div>
          <el-button
            text
            type="primary"
            class="attention-board-toggle"
            :icon="attentionBoardExpanded ? ArrowUp : ArrowDown"
            :aria-label="attentionBoardExpanded ? w('collapseBoard') : w('expandBoard')"
            :title="attentionBoardExpanded ? w('collapseBoard') : w('expandBoard')"
            @click="toggleAttentionBoard"
          />
        </div>

        <template v-if="attentionBoardExpanded">
          <div class="attention-stat-row">
            <article>
              <span>{{ w('workflows') }}</span>
              <strong>{{ workflows.length }}</strong>
            </article>
            <article :class="{ 'is-alert': totalWarningCount > 0 }">
              <span>{{ w('warnings') }}</span>
              <strong>{{ totalWarningCount }}</strong>
            </article>
            <article :class="{ 'is-pending': pendingWorkflowSummaries.length > 0 }">
              <span>{{ w('pending') }}</span>
              <strong>{{ pendingWorkflowSummaries.length }}</strong>
            </article>
          </div>

          <div v-if="attentionSummaryLoading" class="attention-empty">{{ w('countingWarnings') }}</div>
          <div v-else-if="!pendingWorkflowSummaries.length" class="attention-empty is-clear">
            {{ w('nothingToHandle') }}
          </div>
          <div v-else class="attention-shortcuts">
            <span class="attention-shortcuts-label">{{ w('pendingWorkflows') }}</span>
            <div class="attention-shortcut-list">
              <button
                v-for="item in pendingWorkflowSummaries"
                :key="item.id"
                type="button"
                class="attention-shortcut-button"
                @click="openWorkflowHistory(item.id)"
              >
                <span class="attention-shortcut-name">{{ item.name }}</span>
                <small>
                  {{ w('shortcutMeta', { history: item.runHistoryCount, warnings: item.warningCount }) }}
                  <template v-if="item.failedCount"> · {{ w('recentFailure') }}</template>
                </small>
              </button>
            </div>
          </div>
        </template>

        <div
          v-else-if="pendingWorkflowSummaries.length"
          class="attention-shortcut-list is-compact"
        >
          <button
            v-for="item in pendingWorkflowSummaries"
            :key="item.id"
            type="button"
            class="attention-shortcut-button is-compact"
            @click="openWorkflowHistory(item.id)"
          >
            <span class="attention-shortcut-name">{{ item.name }}</span>
            <small>{{ w('shortcutMeta', { history: item.runHistoryCount, warnings: item.warningCount }) }}</small>
          </button>
        </div>
      </section>

      <section
        class="workspace"
        :class="{ 'is-list-only': !editorVisible, 'is-list-hidden': editorVisible && !workflowListVisible }"
      >
        <aside v-if="workflowListVisible" class="workflow-list-panel">
          <div class="panel-heading">
            <div>
              <span>WORKFLOWS</span>
              <strong>{{ w('workflowList') }}</strong>
            </div>
            <el-button
              v-if="editorVisible"
              text
              :icon="Close"
              :aria-label="w('closeWorkflowList')"
              @click="closeWorkflowList"
            >{{ t('common.actions.close') }}</el-button>
          </div>

          <div class="workflow-list-scroll">
            <div v-if="loading && !workflows.length" class="list-state">{{ w('loadingWorkflows') }}</div>
            <div v-else-if="!workflows.length" class="list-state">{{ w('noWorkflows') }}</div>
            <div
              v-for="workflow in workflows"
              :key="workflow.id"
              class="workflow-list-item"
              :class="{ 'is-selected': workflow.id === selectedWorkflowId }"
              @click="openWorkflowEditor(workflow.id)"
            >
              <span class="workflow-type-icon" :class="`is-${workflow.kind}`">
                <el-icon><Files v-if="workflow.kind === 'duro_bom_check'" /><Connection v-else /></el-icon>
              </span>
              <span class="workflow-list-copy">
                <strong>
                  {{ workflow.name }}
                  <span
                    class="workflow-runtime-status"
                    :class="isWorkflowRunning(workflow.id) ? 'is-running' : 'is-idle'"
                  >
                    {{ isWorkflowRunning(workflow.id) ? w('running') : w('idle') }}
                  </span>
                </strong>
                <small class="workflow-list-meta">
                  <span class="workflow-list-meta-left">
                    <span class="workflow-status" :class="`is-${workflow.status}`">{{ statusText[workflow.status] }}</span>
                    · {{ w('historyCount', { count: workflow.run_count || 0 }) }} ·
                    {{ w('lastRun', { time: formatLastRunDate(workflow.last_run_at) }) }}
                  </span>
                </small>
              </span>
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                @click.stop
                @command="handleWorkflowCommand(workflow, $event)"
              >
                <button class="workflow-more-button" type="button" :aria-label="w('workflowActions')" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">{{ t('common.actions.edit') }}</el-dropdown-item>
                    <el-dropdown-item command="copy" :disabled="isWorkflowCopying(workflow.id)">{{ w('copy') }}</el-dropdown-item>
                    <el-dropdown-item command="run" :disabled="isWorkflowRunning(workflow.id)">{{ w('run') }}</el-dropdown-item>
                    <el-dropdown-item command="history">{{ w('runHistory') }}</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>{{ t('common.actions.delete') }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </aside>

        <section v-if="editorVisible && selectedWorkflow && editForm" class="builder-panel">
          <header class="builder-header">
            <div class="builder-title">
              <span class="builder-icon"><el-icon><Files /></el-icon></span>
              <div>
                <div class="title-row">
                  <h2>{{ editForm.name }}</h2>
                  <span class="kind-pill">{{ kindText[editForm.kind] }}</span>
                </div>
                <p>{{ editForm.description || w('noDescription') }}</p>
              </div>
            </div>
            <div class="builder-actions">
              <el-button
                :icon="VideoPlay"
                :loading="triggering"
                :disabled="isWorkflowRunning(selectedWorkflow.id)"
                @click="triggerSelectedWorkflow"
              >{{ w('run') }}</el-button>
              <template v-if="builderTab === 'editor'">
                <el-button type="primary" :icon="Check" :loading="saving" @click="saveSelectedWorkflow">{{ t('common.actions.save') }}</el-button>
              </template>
              <el-button text :icon="Close" :aria-label="t('common.actions.close')" @click="closeWorkflowEditor">{{ t('common.actions.close') }}</el-button>
            </div>
          </header>

          <nav class="builder-navigation" :aria-label="w('detailNavigation')">
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'editor' }"
              @click="builderTab = 'editor'"
            >
              {{ w('editWorkflow') }}
            </button>
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'history' }"
              @click="builderTab = 'history'"
            >
              {{ w('historicalRuns') }}
              <span>{{ historyTotal }}</span>
            </button>
          </nav>

          <div class="builder-body">
            <template v-if="builderTab === 'editor'">
              <section class="configuration-strip">
                <label class="config-field is-wide">
                  <span>{{ w('workflowName') }}</span>
                  <el-input v-model="editForm.name" />
                </label>
                <label class="config-field">
                  <span>{{ t('versions.common.status') }}</span>
                  <el-select v-model="editForm.status">
                    <el-option :label="w('statuses.draft')" value="draft" />
                    <el-option :label="w('statuses.active')" value="active" />
                    <el-option :label="w('statuses.paused')" value="paused" />
                  </el-select>
                </label>
                <label class="config-field schedule-field">
                  <span>{{ w('scheduledTrigger') }}</span>
                  <div class="schedule-control">
                    <el-switch v-model="editForm.schedule.enabled" />
                    <el-input-number
                      v-model="editForm.schedule.interval_minutes"
                      :disabled="!editForm.schedule.enabled"
                      :min="1"
                      :max="10080"
                      controls-position="right"
                    />
                    <em>{{ w('minutes') }}</em>
                  </div>
                </label>
                <label v-if="editForm.kind === 'duro_bom_check'" class="config-field quantity-warning-field">
                  <span>{{ w('ignoreQuantityWarning') }}</span>
                  <div class="quantity-warning-control">
                    <el-switch v-model="sourceConfiguration.ignore_quantity_mismatch_warning" />
                    <em>{{ w('ignoreQuantityHint') }}</em>
                  </div>
                </label>
                <label v-if="editForm.kind === 'duro_bom_check'" class="config-field quantity-warning-field">
                  <span>{{ w('checkParentBom') }}</span>
                  <div class="quantity-warning-control">
                    <el-switch v-model="sourceConfiguration.check_parent_bom" />
                  </div>
                </label>
                <label v-if="editForm.kind === 'duro_bom_check'" class="config-field quantity-warning-field">
                  <span>{{ w('checkSupplies') }}</span>
                  <div class="quantity-warning-control">
                    <el-switch v-model="sourceConfiguration.check_supplies" />
                  </div>
                </label>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-source-grid">
                <article class="workflow-source-card is-sop">
                  <header>
                    <div class="section-label">
                      <span>SOP SOURCE</span>
                      <strong>{{ w('sopProducts') }}</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="sopSourcesLoading"
                      @click="loadSopSources(true)"
                    >{{ w('manualRefresh') }}</el-button>
                  </header>
                  <p>{{ w('sopSourceHint') }}</p>
                  <div class="sop-source-filters">
                    <el-select
                      v-model="sopProjectFilter"
                      clearable
                      filterable
                      :placeholder="w('filterProducts')"
                      @change="sopProcessFilter = ''"
                    >
                      <el-option
                        v-for="project in sopProjectOptions"
                        :key="project"
                        :label="project"
                        :value="project"
                      />
                    </el-select>
                    <el-select v-model="sopProcessFilter" clearable filterable :placeholder="w('filterProcesses')">
                      <el-option
                        v-for="process in sopProcessOptions"
                        :key="process"
                        :label="process"
                        :value="process"
                      />
                    </el-select>
                  </div>
                  <el-select
                    v-model="sourceConfiguration.sop_drive_file_ids"
                    filterable
                    clearable
                    multiple
                    collapse-tags
                    :max-collapse-tags="2"
                    :loading="sopSourcesLoading"
                    :placeholder="w('selectSops')"
                    @change="handleSopSourceChange"
                  >
                    <el-option
                      v-for="entry in displayedSopOptions"
                      :key="`${entry.row_number}-${entry.drive_file_id}`"
                      :label="sopOptionLabel(entry)"
                      :value="entry.drive_file_id || ''"
                    >
                      <div class="source-option">
                        <strong>{{ entry.project || w('uncategorizedProduct') }}</strong>
                        <span>{{ entry.process }} · {{ entry.issue_date || w('noDate') }}</span>
                      </div>
                    </el-option>
                  </el-select>
                  <el-alert v-if="sopSourcesError" type="warning" :closable="false" show-icon>
                    {{ sopSourcesError }}
                  </el-alert>
                  <div v-if="selectedSopEntries.length" class="source-selection-list">
                    <div v-for="entry in selectedSopEntries" :key="entry.drive_file_id || entry.row_number">
                      <strong>{{ entry.project || w('uncategorizedProduct') }}</strong>
                      <span>{{ entry.process }} · {{ entry.issue_date || w('noDate') }}</span>
                    </div>
                  </div>
                  <label class="sop-bom-process-field">
                    <span>{{ w('sopBomProcesses') }}</span>
                    <el-select
                      v-model="sourceConfiguration.sop_bom_processes"
                      multiple
                      filterable
                      clearable
                      collapse-tags
                      :max-collapse-tags="2"
                      :placeholder="w('sopBomProcessesPlaceholder')"
                    >
                      <el-option
                        v-for="option in sopBomProcessOptions"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                    <small>{{ w('sopBomProcessesHint') }}</small>
                  </label>
                </article>

                <article class="workflow-source-card is-duro">
                  <header>
                    <div class="section-label">
                      <span>DURO SOURCE</span>
                      <strong>{{ w('duroProducts') }}</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="duroProductsLoading"
                      @click="loadDuroProducts(true)"
                    >{{ w('manualRefresh') }}</el-button>
                  </header>
                  <p>{{ w('duroSourceHint') }}</p>
                  <el-select
                    v-model="sourceConfiguration.duro_product_id"
                    filterable
                    clearable
                    placement="bottom-start"
                    :fallback-placements="['top-start', 'bottom-start']"
                    :loading="duroProductsLoading"
                    :placeholder="w('selectDuroProduct')"
                    @change="handleDuroProductChange"
                  >
                    <el-option
                      v-for="product in duroProductOptions"
                      :key="product._id"
                      :label="duroProductLabel(product)"
                      :value="product._id"
                    >
                      <div class="source-option">
                        <strong>{{ product.cpn || product.name || product._id }}</strong>
                        <span>{{ product.name }} · {{ product.revision || w('noRevision') }}</span>
                      </div>
                    </el-option>
                  </el-select>
                  <el-collapse
                    v-if="sourceConfiguration.duro_product_id"
                    v-model="duroSubmenuCollapse"
                    class="duro-submenu-selector"
                  >
                    <el-collapse-item name="submenus">
                      <template #title>
                        <div class="duro-submenu-collapse-title">
                          <strong>{{ w('selectSubprojects') }}</strong>
                          <span>{{ w('selectedItems', { count: sourceConfiguration.duro_submenu_ids?.length || 0 }) }}</span>
                        </div>
                      </template>
                      <div class="duro-submenu-heading">
                        <span>{{ w('subprojectHint') }}</span>
                      </div>
                      <div v-if="duroSubmenusLoading" class="duro-submenu-state">{{ w('loadingSubprojects') }}</div>
                      <el-alert v-else-if="duroSubmenusError" type="warning" :closable="false" show-icon>
                        {{ duroSubmenusError }}
                      </el-alert>
                      <el-checkbox-group
                        v-else-if="duroSubmenuOptions.length"
                        v-model="sourceConfiguration.duro_submenu_ids"
                        class="duro-submenu-options"
                        @change="handleDuroSubmenuChange"
                      >
                        <el-checkbox v-for="submenu in duroSubmenuOptions" :key="submenu.id" :value="submenu.id">
                          <span class="duro-submenu-option-copy">
                            <strong>{{ duroSubmenuLabel(submenu) }}</strong>
                            <small>{{ submenu.name || w('unnamedSubproject') }}</small>
                          </span>
                        </el-checkbox>
                      </el-checkbox-group>
                      <div v-else class="duro-submenu-state">{{ w('noSubprojects') }}</div>
                    </el-collapse-item>
                  </el-collapse>
                  <el-alert v-if="duroProductsError" type="warning" :closable="false" show-icon>
                    {{ duroProductsError }}
                  </el-alert>
                  <label class="source-revision-field">
                    <span>{{ w('targetRevision') }}</span>
                    <el-input v-model="sourceConfiguration.target_revision" :placeholder="w('targetRevisionHint')" />
                  </label>
                  <div v-if="selectedDuroProduct" class="source-selection-summary">
                    <span>{{ w('selectedProduct', { product: selectedDuroProduct.name || '—' }) }}</span>
                    <span>{{ w('selectedPart', { part: selectedDuroProduct.cpn || '—' }) }}</span>
                    <span>{{ w('currentRevision', { revision: selectedDuroProduct.revision || '—' }) }}</span>
                  </div>
                </article>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-filter-panel">
                <div class="workflow-filter-item">
                  <div class="section-label">
                    <span>SOP PRODUCT FILTER</span>
                    <div class="ignore-rule-title">
                      <strong>{{ w('ignoreSopProducts') }}</strong>
                      <button type="button" :aria-label="w('addIgnoreSopRule')" @click="openIgnoreRuleDialog('sop')">
                        <el-icon><Plus /></el-icon>
                      </button>
                    </div>
                  </div>
                  <div v-if="sourceConfiguration.ignored_sop_product_keywords?.length" class="ignore-rule-list">
                    <div v-for="keyword in sourceConfiguration.ignored_sop_product_keywords" :key="keyword">
                      <el-tag closable @close="removeIgnoredSopKeyword(keyword)">{{ keyword }}</el-tag>
                      <span>{{ sourceConfiguration.ignored_sop_product_keyword_reasons?.[keyword] }}</span>
                    </div>
                  </div>
                  <div class="workflow-filter-summary">
                    {{ w('ignoredSopHint', { count: sourceConfiguration.ignored_sop_product_keywords?.length || 0 }) }}
                  </div>
                </div>

                <div class="workflow-filter-item">
                  <div class="section-label">
                    <span>BOM PART FILTER</span>
                    <div class="ignore-rule-title">
                      <strong>{{ w('ignoreBomParts') }}</strong>
                      <button
                        type="button"
                        :aria-label="w('refreshIgnoredParts')"
                        :title="w('refreshIgnoredParts')"
                        :disabled="Boolean(ignoredPartRulesLoading[selectedWorkflow.id])"
                        @click="refreshWorkflowIgnoredPartRules(selectedWorkflow.id, true)"
                      >
                        <el-icon :class="{ 'is-loading': ignoredPartRulesLoading[selectedWorkflow.id] }"><Refresh /></el-icon>
                      </button>
                      <button type="button" :aria-label="w('addIgnoreBomPart')" @click="openIgnoreRuleDialog('part')">
                        <el-icon><Plus /></el-icon>
                      </button>
                    </div>
                  </div>
                  <div v-if="sourceConfiguration.ignored_part_numbers?.length" class="ignore-rule-list">
                    <div v-for="partNumber in sourceConfiguration.ignored_part_numbers" :key="partNumber">
                      <el-tag closable @close="removeIgnoredPartNumber(partNumber)">{{ partNumber }}</el-tag>
                      <span>{{ sourceConfiguration.ignored_part_number_reasons?.[partNumber] }}</span>
                    </div>
                  </div>
                  <div class="workflow-filter-summary">
                    {{ w('ignoredPartsHint', { count: sourceConfiguration.ignored_part_numbers?.length || 0 }) }}
                  </div>
                </div>
              </section>

              <section class="flow-section">
                <div class="section-heading-row">
                  <div class="section-label">
                    <span>BOM CHECK FLOW</span>
                    <strong>{{ w('verificationFlow') }}</strong>
                  </div>
                </div>

                <div class="flow-canvas is-compact">
                  <template v-for="(step, index) in editForm.steps" :key="step.id">
                    <div v-if="index > 0" class="flow-connector"><span></span></div>
                    <article class="flow-node">
                      <div class="node-order">{{ String(index + 1).padStart(2, '0') }}</div>
                      <div class="node-icon"><el-icon><component :is="stepIcon(step.kind)" /></el-icon></div>
                      <div class="node-copy">
                        <span>{{ stepKindText[step.kind] }}</span>
                        <strong>{{ step.name }}</strong>
                        <small>{{ step.description || w('noStepDescription') }}</small>
                      </div>
                    </article>
                  </template>
                </div>
              </section>
            </template>

            <section v-else class="run-section is-history-tab">
              <div class="section-heading-row">
                <div class="section-label">
                  <span>EXECUTION HISTORY</span>
                  <div class="history-title-line">
                    <strong>{{ w('historicalRuns') }}</strong>
                    <button
                      class="history-refresh-icon"
                      type="button"
                      :aria-label="w('refreshRuns')"
                      :title="w('refreshRuns')"
                      :disabled="historyLoading"
                      @click="loadRuns(selectedWorkflow.id)"
                    >
                      <el-icon :class="{ 'is-loading': historyLoading }"><Refresh /></el-icon>
                    </button>
                  </div>
                </div>
                <div class="history-filter-panel">
                  <div class="history-stat-grid">
                    <article class="is-success"><span>{{ w('success') }}</span><strong>{{ historySuccessCount }}</strong></article>
                    <article class="is-failed"><span>{{ w('failed') }}</span><strong>{{ historyFailedCount }}</strong></article>
                    <article class="is-warning"><span>{{ w('warnings') }}</span><strong>{{ historyWarningCount }}</strong></article>
                  </div>
                  <el-date-picker
                    v-model="historyDateRange"
                    type="daterange"
                    :range-separator="w('to')"
                    :start-placeholder="w('startDate')"
                    :end-placeholder="w('endDate')"
                    unlink-panels
                    clearable
                    @change="handleHistoryDateChange"
                  />
                </div>
                <div class="history-actions">
                  <button
                    class="history-delete-button"
                    type="button"
                    :disabled="deletingRuns"
                    @click="handleHistoryDeleteButton"
                  >
                    <el-icon><Delete /></el-icon>
                    <span>{{ selectedRunCount ? w('deleteAll') : w('deleteRecords') }}</span>
                  </button>
                  <button
                    v-if="historySelectionMode"
                    class="history-selection-cancel"
                    type="button"
                    @click="cancelHistorySelection"
                  >{{ t('common.actions.cancel') }}</button>
                  <span class="next-run-text">{{ w('nextRun', { time: formatDate(selectedWorkflow.next_run_at) }) }}</span>
                </div>
              </div>
              <div v-if="historyLoading" class="empty-runs">{{ w('loadingRunHistory') }}</div>
              <div v-else-if="!workflowRuns.length" class="empty-runs">{{ w('noRunHistory') }}</div>
              <el-collapse
                v-else
                v-model="activeRunIds"
                class="run-history-collapse"
                @change="handleRunCollapseChange"
              >
                <el-collapse-item v-for="run in workflowRuns" :key="run.id" :name="run.id">
                  <template #title>
                    <div
                      class="run-history-title"
                      :class="{ 'has-warning': runHasWarnings(run), 'is-selecting': historySelectionMode }"
                    >
                      <span v-if="historySelectionMode" class="run-history-checkbox" @click.stop>
                        <el-checkbox
                          :model-value="selectedRunIds.has(run.id)"
                          @change="toggleRunSelection(run.id, Boolean($event))"
                        />
                      </span>
                      <div class="run-summary-copy">
                        <span class="run-primary-status" :class="runStatusClass(run)">
                          <el-icon v-if="run.status === 'running'" class="run-status-glyph is-running">
                            <Loading />
                          </el-icon>
                          <span v-else class="run-status-icon" :class="runStatusClass(run)"></span>
                          {{ runStatusText[run.status] }}
                        </span>
                        <el-tooltip :content="runMessageText(run)" placement="top" :show-after="300">
                          <small class="run-message-line" :class="{ 'is-failure-reason': run.status === 'failed' }">
                            <span>{{ truncatedRunMessage(run) }}</span>
                            <em v-if="run.finished_at">· {{ w('duration', { duration: formatRunDuration(run) }) }}</em>
                          </small>
                        </el-tooltip>
                      </div>
                      <div class="run-warning-summary" :class="{ 'is-warning': runHasWarnings(run) }">
                        <template v-if="run.report">
                          <strong class="is-total-warning">{{ w('warningCount', { count: runWarningCount(run) }) }}</strong>
                          <span class="is-missing">{{ w('missingCount', { count: run.report.missing_in_duro_count }) }}</span>
                          <span class="is-extra">{{ w('extraCount', { count: run.report.extra_in_duro_count }) }}</span>
                          <span class="is-quantity">{{ w('mismatchCount', { count: run.report.quantity_mismatch_count }) }}</span>
                          <span class="is-unknown">{{ w('unknownCount', { count: run.report.quantity_unknown_count }) }}</span>
                        </template>
                        <span v-else>—</span>
                      </div>
                      <span class="run-trigger-type">{{ run.trigger_type === 'manual' ? w('manual') : w('scheduled') }}</span>
                      <time>{{ formatDate(run.created_at) }}</time>
                    </div>
                  </template>

                  <div v-if="runDetailLoading[run.id] && !runDetailLoaded[run.id]" class="empty-runs">
                    {{ w('loadingRunDetails') }}
                  </div>
                  <el-alert
                    v-else-if="runDetailErrors[run.id]"
                    :title="runDetailErrors[run.id]"
                    type="warning"
                    :closable="false"
                    show-icon
                  />
                  <div v-else-if="runDetailLoaded[run.id] && run.report" class="bom-report">
                    <div class="bom-report-metrics">
                      <article><span>{{ w('sopSources') }}</span><strong>{{ run.report.sop_source_count }}</strong></article>
                      <article><span>{{ w('fullTextParts') }}</span><strong>{{ run.report.sop_material_count }}</strong></article>
                      <article><span>{{ w('duroParts') }}</span><strong>{{ run.report.duro_material_count }}</strong></article>
                      <article><span>{{ w('matched') }}</span><strong>{{ run.report.matched_count }}</strong></article>
                      <article class="is-danger"><span>{{ w('missing') }}</span><strong>{{ run.report.missing_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>{{ w('extra') }}</span><strong>{{ run.report.extra_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>{{ w('quantityMismatch') }}</span><strong>{{ run.report.quantity_mismatch_count }}</strong></article>
                      <article><span>{{ w('quantityUnknown') }}</span><strong>{{ run.report.quantity_unknown_count }}</strong></article>
                      <article class="is-ignored"><span>{{ w('ignored') }}</span><strong>{{ run.report.total_ignored_count }}</strong></article>
                    </div>
                    <nav class="report-detail-nav" :aria-label="w('reportNavigation')">
                      <div class="report-detail-nav-pages">
                        <button
                          type="button"
                          :class="{ 'is-active': reportView(run.id) === 'differences' }"
                          @click="setReportView(run.id, 'differences')"
                        >{{ w('differenceDetails') }} <small>{{ w('showingItems', { total: run.report.total_difference_count, shown: filteredReportDifferences(run).length }) }}</small></button>
                        <button
                          type="button"
                          :class="{ 'is-active': reportView(run.id) === 'ignored' }"
                          @click="setReportView(run.id, 'ignored')"
                        >{{ w('ignored') }} <small>{{ w('showingItems', { total: run.report.total_ignored_count, shown: filteredReportIgnoredItems(run).length }) }}</small></button>
                      </div>
                      <div class="bom-report-filters">
                        <el-button
                          class="report-export-button"
                          :icon="Download"
                          :loading="Boolean(runExporting[run.id])"
                          @click="exportWorkflowRun(run)"
                        >{{ w('exportExcel') }}</el-button>
                        <el-input
                          :model-value="reportSearchText(run.id)"
                          class="report-search-input"
                          :prefix-icon="Search"
                          clearable
                          :placeholder="w('searchPartOrName')"
                          @input="setReportSearchText(run.id, String($event))"
                        />
                        <el-select
                          v-if="run.report.duro_submenus.length"
                          :model-value="reportSubmenuFilter(run.id)"
                          class="submenu-filter-select"
                          multiple
                          clearable
                          collapse-tags
                          :max-collapse-tags="2"
                          popper-class="submenu-filter-popper"
                          :placeholder="w('allChildBom')"
                          @change="setReportSubmenuFilter(run.id, $event)"
                        >
                          <el-option
                            v-for="submenu in run.report.duro_submenus"
                            :key="submenu.id"
                            :label="reportSubmenuLabel(submenu)"
                            :value="submenu.id"
                          >
                            <div class="report-submenu-option">
                              <strong>{{ submenu.label }}</strong>
                              <span>{{ submenu.name || w('unnamedSubmenu') }}</span>
                            </div>
                          </el-option>
                        </el-select>
                        <el-select
                          :model-value="reportFilter(run.id)"
                          class="difference-filter-select"
                          @change="setReportFilter(run.id, $event)"
                        >
                          <el-option :label="w('filters.all')" value="all" />
                          <el-option :label="w('filters.structure')" value="structure" />
                          <el-option :label="w('filters.missing')" value="missing_in_duro" />
                          <el-option :label="w('filters.extra')" value="extra_in_duro" />
                          <el-option :label="w('filters.mismatch')" value="quantity_mismatch" />
                          <el-option :label="w('filters.unknown')" value="quantity_unknown" />
                          <el-option :label="w('parentBomIgnored')" value="parent_bom_ignored" />
                        </el-select>
                      </div>
                    </nav>
                    <template v-if="reportView(run.id) === 'differences'">
                    <el-table
                      :ref="setDifferenceTableRef.bind(null, run.id)"
                      class="run-history-data-table"
                      :data="filteredReportDifferences(run)"
                      :row-class-name="differenceRowClassName"
                      row-key="part_number"
                      height="520"
                      border
                      show-overflow-tooltip
                      :empty-text="w('bomMatched')"
                      @row-click="handleDifferenceRowClick(run.id, $event)"
                      @row-contextmenu="handleDifferenceRowContextMenu.bind(null, run)"
                    >
                      <el-table-column
                        type="expand"
                        width="48"
                      >
                        <template #default="{ row }">
                          <div class="semantic-audit-panel">
                            <div class="semantic-audit-actions">
                              <el-button
                                class="difference-ignore-button"
                                :class="`is-${row.status}`"
                                type="warning"
                                size="small"
                                :loading="isDifferenceIgnoreUpdating(run.workflow_id, row.part_number)"
                                :disabled="isDifferenceIgnoreUpdating(run.workflow_id, row.part_number)"
                                @click.stop="ignoreWorkflowDifference(run, row)"
                              >
                                {{ w('ignoreDifference') }}
                              </el-button>
                            </div>
                            <section class="difference-analysis-card">
                              <header class="difference-analysis-header">
                                <div>
                                  <small>DIFFERENCE ANALYSIS</small>
                                  <strong>{{ w('differenceAnalysis') }}</strong>
                                </div>
                                <span class="difference-status" :class="`is-${row.status}`">
                                  {{ differenceLabel(row.status) }}
                                </span>
                              </header>

                              <div class="difference-analysis-overview">
                                <strong>{{ w('verificationConclusion') }}</strong>
                                <p>{{ differenceSummary(row) }}</p>
                              </div>

                              <div class="difference-analysis-metrics">
                                <article class="is-occurrence">
                                  <span>{{ w('sopTextOccurrences') }}</span>
                                  <strong>{{ w('times', { count: differenceSopOccurrenceCount(row) }) }}</strong>
                                  <small>{{ row.sop_locations.join('; ') || w('notInText') }}</small>
                                </article>
                                <article class="is-total">
                                  <span>{{ w('finalQuantity') }}</span>
                                  <strong>{{ differenceFinalSopQuantity(row) }}</strong>
                                  <small>{{ w('summedBelow') }}</small>
                                </article>
                                <article class="is-duro">
                                  <span>Duro BOM</span>
                                  <strong>{{ row.duro_quantity === null ? w('notPresent') : w('present') }}</strong>
                                  <small>{{ row.duro_quantity === null ? w('notInScanScope') : w('bomQuantity', { quantity: formatReportQuantity(row.duro_quantity) }) }}</small>
                                </article>
                              </div>

                              <section class="difference-occurrence-flow">
                                <header>
                                  <div>
                                    <strong>{{ w('textAccumulation') }}</strong>
                                    <small>{{ w('textAccumulationHint') }}</small>
                                  </div>
                                  <span>{{ w('totalDelta', { delta: formatOccurrenceDelta(differenceOccurrenceTotal(row)) }) }}</span>
                                </header>
                                <div v-if="differenceOccurrenceSteps(row).length" class="difference-occurrence-list">
                                  <article
                                    v-for="(step, stepIndex) in differenceOccurrenceSteps(row)"
                                    :key="`${step.source}-${step.page_number}-${stepIndex}`"
                                    class="difference-occurrence-step"
                                  >
                                    <div class="difference-occurrence-rail">
                                      <span>{{ stepIndex + 1 }}</span>
                                    </div>
                                    <div class="difference-occurrence-content">
                                      <div class="difference-occurrence-meta">
                                        <span>{{ step.source || 'SOP' }}<template v-if="step.page_number"> · {{ w('pageNumber', { number: step.page_number }) }}</template></span>
                                        <strong :class="step.quantity_delta ? 'is-added' : 'is-zero'">
                                          {{ formatOccurrenceDelta(step.quantity_delta) }}
                                        </strong>
                                      </div>
                                      <blockquote>{{ step.evidence || w('noEvidence') }}</blockquote>
                                      <p v-if="step.action || step.reason">
                                        <strong v-if="step.action">{{ step.action }}</strong>
                                        <span>{{ step.reason }}</span>
                                      </p>
                                    </div>
                                  </article>
                                </div>
                                <div v-else class="difference-occurrence-empty">
                                  {{ w('legacyEvidenceMissing') }}
                                </div>
                              </section>

                              <section v-if="row.sop_quantity_explanations?.length" class="difference-semantic-notes">
                                <strong>{{ w('semanticStatistics') }}</strong>
                                <p v-for="explanation in row.sop_quantity_explanations" :key="explanation">{{ explanation }}</p>
                              </section>
                            </section>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column
                        :label="w('differenceType')"
                        :render-header="historyTableHeader('Diff. Type')"
                        width="125"
                      >
                        <template #default="{ row }">
                          <el-tooltip :content="differenceLabel(row.status)" placement="top" :show-after="300">
                            <span class="difference-status" :class="`is-${row.status}`">
                              {{ compactDifferenceLabel(row.status) }}
                            </span>
                          </el-tooltip>
                        </template>
                      </el-table-column>
                      <el-table-column
                        :label="w('partNumber')"
                        :render-header="historyTableHeader('Part No.')"
                        width="170"
                      >
                        <template #default="{ row }">
                          <div class="difference-part-number">
                            <span>{{ row.part_number }}</span>
                            <span v-if="row.is_ignored" class="difference-ignored-tag">{{ w('ignored') }}</span>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column prop="name" :label="w('materialName')" :render-header="historyTableHeader('Material')" min-width="260" />
                      <el-table-column :label="w('duroSubmenu')" :render-header="historyTableHeader('Duro Menu')" min-width="150">
                        <template #default="{ row }">{{ row.duro_submenu_labels.join(', ') || '—' }}</template>
                      </el-table-column>
                      <el-table-column :label="w('sopQuantity')" :render-header="historyTableHeader('SOP Qty')" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.sop_quantity) }}</template>
                      </el-table-column>
                      <el-table-column :label="w('duroQuantity')" :render-header="historyTableHeader('Duro Qty')" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.duro_quantity) }}</template>
                      </el-table-column>
                      <el-table-column :label="w('delta')" :render-header="historyTableHeader('Delta')" width="90" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.quantity_delta) }}</template>
                      </el-table-column>
                      <el-table-column :label="w('sopLocation')" :render-header="historyTableHeader('SOP Location')" min-width="260">
                        <template #default="{ row }">{{ row.sop_locations.join('; ') || '—' }}</template>
                      </el-table-column>
                      <el-table-column :label="w('duroPath')" :render-header="historyTableHeader('Duro Path')" min-width="300">
                        <template #default="{ row }">{{ row.duro_paths.join('; ') || '—' }}</template>
                      </el-table-column>
                    </el-table>
                    </template>
                    <template v-else>
                        <el-table
                          class="run-history-data-table"
                          :data="filteredReportIgnoredItems(run)"
                          border
                          height="520"
                          show-overflow-tooltip
                          :empty-text="w('noIgnoredData')"
                          @row-contextmenu="handleIgnoredRowContextMenu.bind(null, run)"
                        >
                          <el-table-column type="expand" width="48">
                            <template #default="{ row }">
                              <div class="semantic-audit-panel">
                                <div v-if="row.sop_quantity_explanations?.length" class="semantic-audit-summary">
                                  <strong>{{ w('quantityExplanation') }}</strong>
                                  <p v-for="explanation in row.sop_quantity_explanations" :key="explanation">{{ explanation }}</p>
                                </div>
                                <article
                                  v-for="(decision, decisionIndex) in row.sop_quantity_decisions || []"
                                  :key="`${decision.source}-${decision.event_id}-${decisionIndex}`"
                                  class="semantic-decision-item"
                                >
                                  <span class="semantic-decision-badge" :class="decision.accumulate ? 'is-added' : 'is-skipped'">
                                    {{ decision.accumulate ? w('accumulate', { quantity: formatReportQuantity(decision.quantity_delta) }) : w('doNotAccumulate') }}
                                  </span>
                                  <div>
                                    <strong>{{ decision.action || w('semanticDecision') }}</strong>
                                    <small>{{ decision.source }}<template v-if="decision.page_numbers?.length"> · {{ w('pageNumbers', { pages: decision.page_numbers.join(', ') }) }}</template></small>
                                    <p>{{ decision.reason || '—' }}</p>
                                    <blockquote v-if="decision.evidence">{{ decision.evidence }}</blockquote>
                                  </div>
                                </article>
                              </div>
                            </template>
                          </el-table-column>
                          <el-table-column
                            :label="w('originalDifference')"
                            :render-header="historyTableHeader('Orig. Diff.')"
                            width="120"
                          >
                            <template #default="{ row }">
                              <el-tooltip :content="ignoredDifferenceLabel(row)" placement="top" :show-after="300">
                                <span
                                  class="difference-status"
                                  :class="row.ignore_type === 'part_number_cleanup' ? 'is-cleanup' : `is-${row.status}`"
                                >
                                  {{ compactIgnoredDifferenceLabel(row) }}
                                </span>
                              </el-tooltip>
                            </template>
                          </el-table-column>
                          <el-table-column prop="part_number" :label="w('originalPartNumber')" :render-header="historyTableHeader('Orig. Part No.')" width="140" />
                          <el-table-column prop="name" :label="w('materialName')" :render-header="historyTableHeader('Material')" min-width="180" />
                          <el-table-column :label="w('duroSubmenu')" :render-header="historyTableHeader('Duro Menu')" min-width="150">
                            <template #default="{ row }">{{ row.duro_submenu_labels.join(', ') || '—' }}</template>
                          </el-table-column>
                          <el-table-column :label="w('ignoreType')" :render-header="historyTableHeader('Ignore Type')" width="130">
                            <template #default="{ row }">
                              <el-tooltip :content="ignoredTypeLabel(row.ignore_type)" placement="top" :show-after="300">
                                <span class="history-table-cell-text">{{ compactIgnoredTypeLabel(row.ignore_type) }}</span>
                              </el-tooltip>
                            </template>
                          </el-table-column>
                          <el-table-column prop="ignore_value" :label="w('matchedRule')" :render-header="historyTableHeader('Matched Rule')" width="140" />
                          <el-table-column prop="ignore_reason" :label="w('ignoreReason')" :render-header="historyTableHeader('Reason')" min-width="220" />
                          <el-table-column :label="w('ignoredSince')" :render-header="historyTableHeader('Ignored Since')" width="170">
                            <template #default="{ row }">
                              <el-tooltip
                                :content="row.ignored_at ? formatDate(row.ignored_at) : w('legacyConfiguration')"
                                placement="top"
                                :show-after="300"
                              >
                                <span class="history-table-cell-text">
                                  {{ row.ignored_at ? formatDate(row.ignored_at) : compactEnglishText(w('legacyConfiguration'), 'Legacy Config.') }}
                                </span>
                              </el-tooltip>
                            </template>
                          </el-table-column>
                        </el-table>
                    </template>
                  </div>
                  <div v-else-if="runDetailLoaded[run.id]" class="run-log-list">
                    <span
                      v-for="(log, index) in run.logs"
                      :key="index"
                      class="run-log-entry"
                      :class="{ 'is-current': isRunInProgress(run) && index === run.logs.length - 1 }"
                    >
                      <span class="run-log-entry-marker" aria-hidden="true">
                        <el-icon v-if="isRunInProgress(run) && index === run.logs.length - 1"><Loading /></el-icon>
                        <span v-else class="run-log-entry-dot"></span>
                      </span>
                      <span>{{ log }}</span>
                    </span>
                    <span v-if="!run.logs.length" class="run-log-entry is-current">
                      <span class="run-log-entry-marker" aria-hidden="true">
                        <el-icon><Loading /></el-icon>
                      </span>
                      <span>{{ w('workflowRunning') }}</span>
                    </span>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-pagination
                v-if="historyTotal > historyPageSize"
                class="history-pagination"
                background
                layout="prev, pager, next, total"
                :current-page="historyPage"
                :page-size="historyPageSize"
                :total="historyTotal"
                @current-change="handleHistoryPageChange"
              />
            </section>
          </div>
        </section>

      </section>

      <footer class="workflow-board-footer" :aria-label="w('boardAria')">
        <span>{{ w('workflows') }} <strong>{{ workflows.length }}</strong></span>
        <span>{{ w('enabled') }} <strong>{{ activeWorkflowCount }}</strong></span>
        <span>{{ w('scheduledTasks') }} <strong>{{ scheduledWorkflowCount }}</strong></span>
        <span>Duro BOM <strong>{{ duroWorkflowCount }}</strong></span>
      </footer>
    </main>
    <SopOverviewPanel v-else-if="activeModule === 'sop'" />
    <DuroProductsPanel v-else-if="activeModule === 'duro'" :key="duroCredentialRevision" />
    <SupplementaryMaterialsPanel v-else />

    <el-dialog v-model="createDialogVisible" :title="w('newWorkflow')" width="520px">
      <div class="dialog-form">
        <label>
          <span>{{ w('workflowName') }}</span>
          <el-input v-model="createForm.name" :placeholder="w('workflowNamePlaceholder')" />
        </label>
        <label>
          <span>{{ w('template') }}</span>
          <el-radio-group v-model="createForm.template">
            <el-radio-button value="duro">{{ w('duroBomCheck') }}</el-radio-button>
            <el-radio-button value="blank">{{ w('blankWorkflow') }}</el-radio-button>
          </el-radio-group>
        </label>
        <label>
          <span>{{ w('description') }}</span>
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </label>
      </div>
      <template #footer>
        <el-button @click="createDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="createWorkflow">{{ w('create') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ignoreRuleDialogVisible"
      :title="ignoreRuleDialogType === 'sop' ? w('addIgnoreSopRule') : w('addIgnoreBomPart')"
      width="480px"
    >
      <div class="ignore-rule-dialog-form">
        <label>
          <span>{{ ignoreRuleDialogType === 'sop' ? w('productKeyword') : w('bomPartNumber') }}</span>
          <el-input
            v-if="ignoreRuleDialogType === 'sop'"
            v-model="pendingSopKeyword"
            :placeholder="w('keywordExample')"
            @keyup.enter="addIgnoredSopKeyword"
          />
          <el-input
            v-else
            v-model="pendingPartNumber"
            :placeholder="w('partExample')"
            @keyup.enter="addIgnoredPartNumber"
          />
        </label>
        <label>
          <span>{{ w('ignoreReason') }}</span>
          <el-input
            v-if="ignoreRuleDialogType === 'sop'"
            v-model="pendingSopKeywordReason"
            type="textarea"
            :rows="3"
            :placeholder="w('ignoreReasonPlaceholder')"
          />
          <el-input
            v-else
            v-model="pendingPartNumberReason"
            type="textarea"
            :rows="3"
            :placeholder="w('ignoreReasonPlaceholder')"
          />
        </label>
      </div>
      <template #footer>
        <el-button @click="ignoreRuleDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" @click="confirmIgnoreRule">{{ t('common.actions.add') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="duroApiKeyDialogVisible"
      :title="w('updateDuroApiKeyTitle')"
      width="min(480px, calc(100vw - 24px))"
      @closed="duroApiKey = ''"
    >
      <div class="duro-api-key-form">
        <label>
          <span>duro_api_key</span>
          <el-input
            v-model="duroApiKey"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="w('duroApiKeyPlaceholder')"
            @keyup.enter="submitDuroApiKey"
          />
        </label>
      </div>
      <template #footer>
        <el-button :disabled="updatingDuroApiKey" @click="duroApiKeyDialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="updatingDuroApiKey" @click="submitDuroApiKey">{{ w('updateDuroApiKey') }}</el-button>
      </template>
    </el-dialog>

    <Teleport to="body">
      <div
        v-if="differenceContextMenu.visible && differenceContextMenu.run && differenceContextMenu.row"
        class="difference-context-menu"
        role="menu"
        :aria-label="w('differenceActions')"
        :style="{ left: `${differenceContextMenu.x}px`, top: `${differenceContextMenu.y}px` }"
        @click.stop
        @contextmenu.prevent
      >
        <template v-if="differenceContextMenu.source === 'ignored'">
          <button
            type="button"
            role="menuitem"
            :title="ignoredDifferenceRestoreHint(differenceContextMenu.row)"
            :disabled="!canRestoreIgnoredDifference(differenceContextMenu.row) || isDifferenceIgnoreUpdating(differenceContextMenu.run.workflow_id, differenceContextMenu.row.part_number)"
            @click="handleDifferenceContextMenuCommand('restore')"
          >
            {{ w('restoreDifference', { type: differenceLabel(differenceContextMenu.row.status) }) }}
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            role="menuitem"
            :disabled="isDifferenceIgnoreUpdating(differenceContextMenu.run.workflow_id, differenceContextMenu.row.part_number)"
            @click="handleDifferenceContextMenuCommand('ignore')"
          >
            {{ w('ignorePart') }}
          </button>
          <div class="difference-context-menu-divider" role="separator"></div>
          <button type="button" role="menuitem" @click="handleDifferenceContextMenuCommand('expand')">
            {{ w('expand') }}
          </button>
        </template>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElTooltip, type TableInstance } from 'element-plus'
import {
  ArrowDown,
  ArrowUp,
  Box,
  Check,
  Close,
  Connection,
  DataAnalysis,
  Delete,
  DocumentChecked,
  Download,
  Files,
  FolderOpened,
  Loading,
  MoreFilled,
  Plus,
  Refresh,
  Search,
  VideoPlay
} from '@element-plus/icons-vue'
import DuroProductsPanel from '@/views/version_modules/DuroProductsPanel.vue'
import SopOverviewPanel from '@/views/version_modules/SopOverviewPanel.vue'
import SupplementaryMaterialsPanel from '@/views/version_modules/SupplementaryMaterialsPanel.vue'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import { useAppLocale } from '@/i18n'
import '@/styles/version_modules/version_modules.css'
import { duroApi, type DuroBomNode, type DuroConnectionStatus, type DuroProduct } from '@/scripts/modules/version_modules/api/duro'
import { sopApi, type SopCatalogEntry } from '@/scripts/modules/version_modules/api/sop'
import {
  workflowApi,
  type WorkflowBomDifference,
  type WorkflowBomIgnoredItem,
  type WorkflowBomDifferenceStatus,
  type WorkflowIgnoredPartRule,
  type WorkflowSopOccurrenceStep,
  type Workflow,
  type WorkflowKind,
  type WorkflowPayload,
  type WorkflowRun,
  type WorkflowRunStatus,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowStepKind
} from '@/scripts/modules/version_modules/api/workflows'

type VersionModule = 'workflows' | 'sop' | 'duro' | 'accessory-materials'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { locale } = useAppLocale()
const w = (key: string, params?: Record<string, unknown>) => t(`versions.workflow.${key}`, params || {})

const apiError = (error: any, fallback: string) => (
  error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || fallback
)

function versionModuleFromQuery(value: unknown): VersionModule {
  const module = Array.isArray(value) ? value[0] : value
  if (module === 'sop') return 'sop'
  if (module === 'duro' || module === 'ecn') return 'duro'
  if (module === 'accessory-materials') return 'accessory-materials'
  return 'workflows'
}

const loading = ref(true)
const activeModule = ref<VersionModule>(versionModuleFromQuery(route.query.module))
watch(() => route.query.module, (value) => {
  activeModule.value = versionModuleFromQuery(value)
})

function selectVersionModule(module: VersionModule) {
  activeModule.value = module
  void router.replace({
    query: {
      ...route.query,
      module: module === 'workflows' ? undefined : module,
    },
  })
}
const saving = ref(false)
const creating = ref(false)
const triggering = ref(false)
const editorVisible = ref(false)
const workflowListVisible = ref(true)
const runningWorkflowIds = ref<Set<string>>(new Set())
const pollingRunIds = ref<Set<string>>(new Set())
const workflowPollingRunIds = ref<Record<string, string>>({})
const copyingWorkflowIds = ref<Set<string>>(new Set())
const workflows = ref<Workflow[]>([])
const ATTENTION_BOARD_STORAGE_KEY = 'versions.workflowAttentionBoardExpanded'

function readAttentionBoardExpanded(): boolean {
  try {
    const saved = sessionStorage.getItem(ATTENTION_BOARD_STORAGE_KEY)
    if (saved === '0') return false
    if (saved === '1') return true
  } catch {
    // ignore storage failures
  }
  return true
}

const attentionBoardExpanded = ref(readAttentionBoardExpanded())
const attentionSummaryLoading = ref(false)
const workflowAttentionMap = ref<Record<string, {
  warningCount: number
  failedCount: number
  runHistoryCount: number
}>>({})
const workflowRuns = ref<WorkflowRun[]>([])
const activeRunIds = ref<string[]>([])
const runDetailLoaded = reactive<Record<string, boolean>>({})
const runDetailLoading = reactive<Record<string, boolean>>({})
const runDetailErrors = reactive<Record<string, string>>({})
const runDetailReloadPending = reactive<Record<string, boolean>>({})
const runExporting = reactive<Record<string, boolean>>({})
const ignoredPartRulesLoading = reactive<Record<string, boolean>>({})
const differenceIgnoreUpdating = reactive<Record<string, boolean>>({})
const differenceTableRefs = new Map<string, TableInstance>()
const differenceContextMenu = reactive<{
  visible: boolean
  x: number
  y: number
  source: 'differences' | 'ignored'
  run: WorkflowRun | null
  row: WorkflowBomDifference | WorkflowBomIgnoredItem | null
}>({
  visible: false,
  x: 0,
  y: 0,
  source: 'differences',
  run: null,
  row: null
})
const historyLoading = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)
const historySuccessCount = ref(0)
const historyFailedCount = ref(0)
const historyWarningCount = ref(0)
const historyDateRange = ref<[Date, Date] | null>(null)
const historySelectionMode = ref(false)
const selectedRunIds = ref<Set<string>>(new Set())
const deletingRuns = ref(false)
const selectedWorkflowId = ref<string | null>(null)
const editForm = ref<WorkflowPayload | null>(null)
const createDialogVisible = ref(false)
const builderTab = ref<'editor' | 'history'>('editor')
const sopSourcesLoading = ref(false)
const sopSourcesError = ref('')
const sopSourceChecked = ref(false)
const sopCatalogEntries = ref<SopCatalogEntry[]>([])
const sopProjectFilter = ref('')
const sopProcessFilter = ref('')
const duroProductsLoading = ref(false)
const duroProductsError = ref('')
const duroSourceChecked = ref(false)
const duroProducts = ref<DuroProduct[]>([])
const duroConnectionStatus = ref<DuroConnectionStatus | null>(null)
const duroApiKeyDialogVisible = ref(false)
const duroApiKey = ref('')
const updatingDuroApiKey = ref(false)
const duroCredentialRevision = ref(0)
const dataSourceDetailsExpanded = ref(false)
const duroSubmenusLoading = ref(false)
const duroSubmenusError = ref('')
const duroSubmenuOptions = ref<DuroBomNode[]>([])
const duroSubmenuCollapse = ref<string[]>([])
const reportDifferenceFilters = reactive<Record<string, ReportDifferenceFilter>>({})
const reportSubmenuFilters = reactive<Record<string, string[]>>({})
const reportViews = reactive<Record<string, 'differences' | 'ignored'>>({})
const reportSearchTexts = reactive<Record<string, string>>({})
const pendingSopKeyword = ref('')
const pendingSopKeywordReason = ref('')
const pendingPartNumber = ref('')
const pendingPartNumberReason = ref('')
const ignoreRuleDialogVisible = ref(false)
const ignoreRuleDialogType = ref<'sop' | 'part'>('sop')

type ReportDifferenceFilter = 'all' | 'structure' | WorkflowBomDifferenceStatus

interface WorkflowSopSource {
  drive_file_id: string
  project: string
  process: string
  issue_date: string
  link_url: string | null
  row_number: number
}

interface WorkflowSourceConfiguration extends Record<string, unknown> {
  sop_drive_file_ids?: string[]
  sop_sources?: WorkflowSopSource[]
  sop_bom_processes?: string[]
  sop_drive_file_id?: string
  sop_project?: string
  sop_process?: string
  sop_issue_date?: string
  sop_link_url?: string
  sop_row_number?: number | null
  duro_product_id?: string
  duro_product_name?: string
  duro_product_cpn?: string
  duro_product_revision?: string
  target_revision?: string
  duro_submenu_ids?: string[]
  duro_submenus?: Array<{ id: string; label: string }>
  ignored_sop_product_keywords?: string[]
  ignored_part_numbers?: string[]
  ignored_sop_product_keyword_reasons?: Record<string, string>
  ignored_part_number_reasons?: Record<string, string>
  ignore_quantity_mismatch_warning?: boolean
  check_parent_bom?: boolean
  check_supplies?: boolean
}

const createForm = reactive({
  name: w('duroBomCheck'),
  template: 'duro' as 'duro' | 'blank',
  description: w('defaultDescription')
})

const statusText = computed<Record<WorkflowStatus, string>>(() => ({
  draft: w('statuses.draft'), active: w('statuses.active'), paused: w('statuses.paused')
}))

const kindText = computed<Record<WorkflowKind, string>>(() => ({
  duro_bom_check: 'Duro BOM', custom: w('custom')
}))

const stepKindText: Record<WorkflowStepKind, string> = {
  duro_bom_fetch: 'DURO SOURCE',
  bom_compare: 'BOM CHECK',
  report: 'REPORT',
  custom: 'CUSTOM STEP'
}

const runStatusText = computed<Record<WorkflowRunStatus, string>>(() => ({
  queued: w('runStatuses.queued'), running: w('runStatuses.running'), succeeded: w('runStatuses.succeeded'),
  failed: w('runStatuses.failed'), skipped: w('runStatuses.skipped')
}))

const differenceStatusText = computed<Record<WorkflowBomDifferenceStatus, string>>(() => ({
  missing_in_duro: w('missing'), extra_in_duro: w('extra'), quantity_mismatch: w('quantityMismatch'), quantity_unknown: w('quantityUnknown'), parent_bom_ignored: w('parentBomIgnored')
}))

const selectedWorkflow = computed(() =>
  workflows.value.find((workflow) => workflow.id === selectedWorkflowId.value) ?? null
)
const selectedRunCount = computed(() => selectedRunIds.value.size)

const activeWorkflowCount = computed(() => workflows.value.filter((item) => item.status === 'active').length)
const scheduledWorkflowCount = computed(() => workflows.value.filter((item) => item.schedule.enabled).length)
const duroWorkflowCount = computed(() => workflows.value.filter((item) => item.kind === 'duro_bom_check').length)

const pendingWorkflowSummaries = computed(() => (
  workflows.value
    .map((workflow) => {
      const summary = workflowAttentionMap.value[workflow.id]
      const warningCount = summary?.warningCount ?? 0
      const failedCount = summary?.failedCount ?? 0
      const runHistoryCount = summary?.runHistoryCount ?? workflow.run_count ?? 0
      return {
        id: workflow.id,
        name: workflow.name,
        warningCount,
        failedCount,
        runHistoryCount,
        alertCount: warningCount + failedCount
      }
    })
    .filter((item) => item.alertCount > 0)
    .sort((left, right) => right.alertCount - left.alertCount || left.name.localeCompare(right.name, locale.value))
))

const totalWarningCount = computed(() => (
  workflows.value.reduce((total, workflow) => {
    return total + (workflowAttentionMap.value[workflow.id]?.warningCount ?? 0)
  }, 0)
))
const sourceConfiguration = computed(
  () => editForm.value?.configuration as WorkflowSourceConfiguration
)
const allSopOptions = computed(() =>
  sopCatalogEntries.value
    .filter((entry) => Boolean(entry.drive_file_id))
    .sort((left, right) =>
      `${left.project}\u0000${left.process}\u0000${left.issue_date}`.localeCompare(
        `${right.project}\u0000${right.process}\u0000${right.issue_date}`
      )
    )
)
const sopProjectOptions = computed(() =>
  [...new Set(allSopOptions.value.map((entry) => entry.project || w('uncategorizedProduct')))].sort((a, b) => a.localeCompare(b))
)
const sopProcessOptions = computed(() =>
  [...new Set(
    allSopOptions.value
      .filter((entry) => !sopProjectFilter.value || (entry.project || w('uncategorizedProduct')) === sopProjectFilter.value)
      .map((entry) => entry.process || w('unnamedProcess'))
  )].sort((a, b) => a.localeCompare(b))
)
const sopBomProcessOptions = computed(() => {
  const labels = new Map<string, string>()
  for (const entry of allSopOptions.value) {
    const label = entry.process.trim()
    const value = normalizeSopProcess(label)
    if (value && !labels.has(value)) labels.set(value, label)
  }
  if (!labels.has('packaging')) labels.set('packaging', 'packaging')
  return [...labels.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((left, right) => left.label.localeCompare(right.label))
})
const filteredSopOptions = computed(() =>
  allSopOptions.value.filter((entry) =>
    (!sopProjectFilter.value || (entry.project || w('uncategorizedProduct')) === sopProjectFilter.value)
    && (!sopProcessFilter.value || (entry.process || w('unnamedProcess')) === sopProcessFilter.value)
  )
)
const displayedSopOptions = computed(() => {
  const selectedIds = new Set(sourceConfiguration.value?.sop_drive_file_ids ?? [])
  return allSopOptions.value.filter((entry) =>
    filteredSopOptions.value.includes(entry) || Boolean(entry.drive_file_id && selectedIds.has(entry.drive_file_id))
  )
})
const duroProductOptions = computed(() =>
  [...duroProducts.value].sort((left, right) =>
    (left.cpn || left.name || left._id).localeCompare(right.cpn || right.name || right._id)
  )
)
const selectedSopEntries = computed(() => {
  const fileIds = new Set(sourceConfiguration.value?.sop_drive_file_ids ?? [])
  return allSopOptions.value.filter((entry) => entry.drive_file_id && fileIds.has(entry.drive_file_id))
})
const selectedDuroProduct = computed(() => {
  const productId = sourceConfiguration.value?.duro_product_id
  return duroProducts.value.find((product) => product._id === productId) ?? null
})
const dataSourcesChecking = computed(() =>
  sopSourcesLoading.value || duroProductsLoading.value || !sopSourceChecked.value || !duroSourceChecked.value
)
const dataSourcesConnected = computed(() =>
  !dataSourcesChecking.value && !sopSourcesError.value && !duroProductsError.value
)
const dataSourceStatusClass = computed(() => ({
  'is-ready': dataSourcesConnected.value,
  'is-error': !dataSourcesChecking.value && !dataSourcesConnected.value
}))
const dataSourceStatusTitle = computed(() => {
  if (dataSourcesChecking.value) return w('checkingSources')
  return dataSourcesConnected.value ? w('sourcesConnected') : w('sourcesFailed')
})
const dataSourceStatusDetail = computed(() => {
  if (dataSourcesChecking.value) return w('checkingSopDuro')
  if (dataSourcesConnected.value) return 'SOP / Duro API'
  if (sopSourcesError.value && duroProductsError.value) return w('bothSourcesFailed')
  if (sopSourcesError.value) return w('sopSourceFailed')
  return w('duroSourceFailed')
})
const dataSourceErrorDetail = computed(() =>
  [
    sopSourcesError.value ? `SOP：${sopSourcesError.value}` : '',
    duroProductsError.value ? `Duro API：${duroProductsError.value}` : ''
  ].filter(Boolean).join('\n')
)
const duroApiKeyExpiring = computed(() => {
  const expiresAt = duroConnectionStatus.value?.api_key_expires_at
  if (!expiresAt) return false
  const remaining = Date.parse(expiresAt) - Date.now()
  return remaining <= 14 * 24 * 60 * 60 * 1000
})
const duroApiKeyExpiryText = computed(() => {
  const status = duroConnectionStatus.value
  if (!status?.configured) return w('duroApiKeyMissing')
  if (!status.api_key_expires_at) return w('duroApiKeyExpiryUnknown')
  return w('duroApiKeyExpiresAt', { time: formatDate(status.api_key_expires_at) })
})

function cloneWorkflowPayload(workflow: Workflow): WorkflowPayload {
  return {
    name: workflow.name,
    description: workflow.description,
    kind: workflow.kind,
    status: workflow.status,
    schedule: { ...workflow.schedule },
    steps: workflow.steps.map((step) => ({
      ...step,
      configuration: { ...step.configuration }
    })),
    configuration: normalizeWorkflowConfiguration(workflow.configuration)
  }
}

function normalizeSopProcess(value: unknown) {
  return String(value ?? '').trim().replace(/\s+/g, '').toLowerCase()
}

function normalizeWorkflowConfiguration(configuration: Record<string, unknown>): WorkflowSourceConfiguration {
  const singleFileId = typeof configuration.sop_drive_file_id === 'string'
    ? configuration.sop_drive_file_id.trim()
    : ''
  const configuredFileIds = Array.isArray(configuration.sop_drive_file_ids)
    ? configuration.sop_drive_file_ids.map(String).filter(Boolean)
    : []
  const fileIds = configuredFileIds.length ? configuredFileIds : (singleFileId ? [singleFileId] : [])
  const configuredSources = Array.isArray(configuration.sop_sources)
    ? configuration.sop_sources.filter((item): item is WorkflowSopSource => Boolean(item && typeof item === 'object'))
    : []
  const rawBomProcesses = configuration.sop_bom_processes
  const bomProcesses = Array.isArray(rawBomProcesses)
    ? [...new Set(rawBomProcesses.map(normalizeSopProcess).filter(Boolean))]
    : ['packaging']
  const ignoredPartNumbers = Array.isArray(configuration.ignored_part_numbers)
    ? [...new Set(configuration.ignored_part_numbers.map((value) => String(value).trim().toUpperCase()).filter(Boolean))]
    : []
  const ignoredSopProductKeywords = Array.isArray(configuration.ignored_sop_product_keywords)
    ? uniqueKeywords(configuration.ignored_sop_product_keywords.map(String))
    : []
  const keywordReasons = configuration.ignored_sop_product_keyword_reasons && typeof configuration.ignored_sop_product_keyword_reasons === 'object'
    ? configuration.ignored_sop_product_keyword_reasons as Record<string, unknown>
    : {}
  const partReasons = configuration.ignored_part_number_reasons && typeof configuration.ignored_part_number_reasons === 'object'
    ? configuration.ignored_part_number_reasons as Record<string, unknown>
    : {}
  const submenuIds = Array.isArray(configuration.duro_submenu_ids)
    ? [...new Set(configuration.duro_submenu_ids.map(String).filter(Boolean))]
    : []
  const submenus = Array.isArray(configuration.duro_submenus)
    ? configuration.duro_submenus.filter((item): item is { id: string; label: string } => Boolean(item && typeof item === 'object' && 'id' in item))
    : []
  return {
    sop_drive_file_id: '',
    sop_project: '',
    sop_process: '',
    sop_issue_date: '',
    sop_link_url: '',
    sop_row_number: null,
    duro_product_id: '',
    duro_product_name: '',
    duro_product_cpn: '',
    duro_product_revision: '',
    target_revision: '',
    ...configuration,
    sop_drive_file_ids: fileIds,
    sop_sources: configuredSources,
    sop_bom_processes: bomProcesses,
    duro_submenu_ids: submenuIds,
    duro_submenus: submenus,
    ignored_sop_product_keywords: ignoredSopProductKeywords,
    ignored_part_numbers: ignoredPartNumbers,
    ignored_sop_product_keyword_reasons: Object.fromEntries(
      ignoredSopProductKeywords.map((keyword) => [keyword, String(keywordReasons[keyword] || w('legacyReasonMissing'))])
    ),
    ignored_part_number_reasons: Object.fromEntries(
      ignoredPartNumbers.map((partNumber) => [partNumber, String(partReasons[partNumber] || w('legacyReasonMissing'))])
    ),
    ignore_quantity_mismatch_warning: Boolean(configuration.ignore_quantity_mismatch_warning),
    check_parent_bom: Boolean(configuration.check_parent_bom),
    check_supplies: Boolean(configuration.check_supplies)
  }
}

async function loadWorkflows() {
  loading.value = true
  try {
    const response = await workflowApi.list()
    workflows.value = response.data
    const currentId = selectedWorkflowId.value
    const nextSelection = response.data.find((item) => item.id === currentId) ?? null
    if (nextSelection && editorVisible.value) {
      selectWorkflow(nextSelection.id)
    } else if (!nextSelection) {
      selectedWorkflowId.value = null
      editForm.value = null
      workflowRuns.value = []
      editorVisible.value = false
      workflowListVisible.value = true
    }
    void loadWorkflowAttentionSummary(response.data)
  } catch (error) {
    console.error(error)
    workflowAttentionMap.value = {}
    ElMessage.error(w('messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadWorkflowAttentionSummary(items: Workflow[] = workflows.value) {
  if (!items.length) {
    workflowAttentionMap.value = {}
    attentionSummaryLoading.value = false
    return
  }

  attentionSummaryLoading.value = true
  try {
    const results = await Promise.all(
      items.map(async (workflow) => {
        try {
          // 取最近一次运行的告警条目数（warning_difference_count），
          // 不要用 page.warning_count（那是「有告警的运行次数」）。
          const response = await workflowApi.runs(workflow.id, 1, 1)
          const latest = response.data.items?.[0]
          const warningCount = latestRunWarningCount(latest)
          const failedCount = latest?.status === 'failed' ? 1 : 0
          const runHistoryCount = Number(response.data.total || workflow.run_count || 0)
          if (latest && ['queued', 'running'].includes(latest.status)) {
            setWorkflowRunning(workflow.id, true)
            startPollingWorkflowRun(workflow.id, latest.id)
          } else if (!workflowPollingRunIds.value[workflow.id]) {
            setWorkflowRunning(workflow.id, false)
          }
          return [
            workflow.id,
            {
              warningCount,
              failedCount,
              runHistoryCount
            }
          ] as const
        } catch (error) {
          console.error(error)
          return [
            workflow.id,
            {
              warningCount: 0,
              failedCount: 0,
              runHistoryCount: workflow.run_count || 0
            }
          ] as const
        }
      })
    )
    workflowAttentionMap.value = Object.fromEntries(results)
  } finally {
    attentionSummaryLoading.value = false
  }
}

function latestRunWarningCount(run: WorkflowRun | undefined): number {
  if (!run || run.status !== 'succeeded' || !run.report) return 0
  const warningItems = run.report.warning_difference_count
  if (typeof warningItems === 'number') return Math.max(0, warningItems)
  const totalItems = run.report.total_difference_count
  if (typeof totalItems === 'number') return Math.max(0, totalItems)
  return Math.max(0, run.report.differences?.length || 0)
}

function selectWorkflow(workflowId: string) {
  const workflow = workflows.value.find((item) => item.id === workflowId)
  if (!workflow) return
  if (selectedWorkflowId.value !== workflowId) {
    historyPage.value = 1
    historyDateRange.value = null
    activeRunIds.value = []
  }
  selectedWorkflowId.value = workflowId
  editForm.value = cloneWorkflowPayload(workflow)
  const productId = String(editForm.value.configuration.duro_product_id || '')
  if (workflow.kind === 'duro_bom_check' && productId) void loadDuroSubmenus(productId)
  if (workflow.kind === 'duro_bom_check') void refreshWorkflowIgnoredPartRules(workflowId)
  void loadRuns(workflowId)
}

async function refreshWorkflowIgnoredPartRules(workflowId: string, notify = false) {
  if (ignoredPartRulesLoading[workflowId]) return
  ignoredPartRulesLoading[workflowId] = true
  try {
    const response = await workflowApi.ignoredParts(workflowId)
    const rules = response.data as WorkflowIgnoredPartRule[]
    const partNumbers = [...new Set(rules.map((rule) => rule.part_number.trim().toUpperCase()))]
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right))
    const reasons = Object.fromEntries(
      rules.map((rule) => [rule.part_number.trim().toUpperCase(), rule.reason])
    )
    const workflow = workflows.value.find((item) => item.id === workflowId)
    if (workflow) {
      workflow.configuration = {
        ...workflow.configuration,
        ignored_part_numbers: partNumbers,
        ignored_part_number_reasons: reasons
      }
    }
    if (selectedWorkflowId.value === workflowId && editForm.value) {
      sourceConfiguration.value.ignored_part_numbers = partNumbers
      sourceConfiguration.value.ignored_part_number_reasons = reasons
    }
    if (notify) ElMessage.success(w('messages.ignoredPartsRefreshed', { count: partNumbers.length }))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.refreshIgnoredPartsFailed')))
  } finally {
    ignoredPartRulesLoading[workflowId] = false
  }
}

function setAttentionBoardExpanded(expanded: boolean) {
  attentionBoardExpanded.value = expanded
  try {
    sessionStorage.setItem(ATTENTION_BOARD_STORAGE_KEY, expanded ? '1' : '0')
  } catch {
    // ignore storage failures
  }
}

function toggleAttentionBoard() {
  setAttentionBoardExpanded(!attentionBoardExpanded.value)
}

function openWorkflowEditor(workflowId: string) {
  selectWorkflow(workflowId)
  builderTab.value = 'editor'
  editorVisible.value = true
  workflowListVisible.value = false
  setAttentionBoardExpanded(false)
}

function openWorkflowHistory(workflowId: string) {
  selectWorkflow(workflowId)
  builderTab.value = 'history'
  editorVisible.value = true
  workflowListVisible.value = false
  setAttentionBoardExpanded(false)
}

function closeWorkflowEditor() {
  editorVisible.value = false
  workflowListVisible.value = true
  editForm.value = null
  workflowRuns.value = []
  activeRunIds.value = []
}

function closeWorkflowList() {
  if (!editorVisible.value) return
  workflowListVisible.value = false
}

function handleWorkflowCommand(workflow: Workflow, command: string | number | object) {
  if (command === 'edit') {
    openWorkflowEditor(workflow.id)
    return
  }
  if (command === 'run') {
    void triggerWorkflow(workflow)
    return
  }
  if (command === 'copy') {
    void copyWorkflow(workflow)
    return
  }
  if (command === 'history') {
    openWorkflowHistory(workflow.id)
    return
  }
  if (command === 'delete') void deleteWorkflow(workflow)
}

function isWorkflowRunning(workflowId: string) {
  return runningWorkflowIds.value.has(workflowId)
}

function isWorkflowCopying(workflowId: string) {
  return copyingWorkflowIds.value.has(workflowId)
}

function setWorkflowRunning(workflowId: string, running: boolean) {
  const next = new Set(runningWorkflowIds.value)
  if (running) next.add(workflowId)
  else next.delete(workflowId)
  runningWorkflowIds.value = next
}

async function loadSopSources(refresh = false) {
  sopSourcesLoading.value = true
  sopSourcesError.value = ''
  try {
    const response = await sopApi.masterSheet(refresh)
    sopCatalogEntries.value = response.data.entries
  } catch (error: any) {
    console.error(error)
    sopSourcesError.value = apiError(error, w('messages.sopSourceLoadFailed'))
  } finally {
    sopSourcesLoading.value = false
    sopSourceChecked.value = true
  }
}

async function loadDuroProducts(refresh = false) {
  duroProductsLoading.value = true
  duroProductsError.value = ''
  try {
    const statusResponse = await duroApi.status()
    duroConnectionStatus.value = statusResponse.data
    const response = await duroApi.products(refresh)
    duroProducts.value = response.data.products
  } catch (error: any) {
    console.error(error)
    duroProductsError.value = apiError(error, w('messages.duroProductsLoadFailed'))
  } finally {
    duroProductsLoading.value = false
    duroSourceChecked.value = true
  }
}

function openDuroApiKeyDialog() {
  duroApiKey.value = ''
  duroApiKeyDialogVisible.value = true
}

async function submitDuroApiKey() {
  const value = duroApiKey.value.trim()
  if (!value) {
    ElMessage.warning(w('messages.duroApiKeyRequired'))
    return
  }
  updatingDuroApiKey.value = true
  try {
    const response = await duroApi.updateApiKey(value)
    duroConnectionStatus.value = response.data
    duroApiKeyDialogVisible.value = false
    duroApiKey.value = ''
    duroCredentialRevision.value += 1
    await loadDuroProducts(true)
    ElMessage.success(w('messages.duroApiKeyUpdated'))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.duroApiKeyUpdateFailed')))
  } finally {
    updatingDuroApiKey.value = false
  }
}

function handleSopSourceChange(fileIds: string[]) {
  if (!editForm.value) return
  const configuration = sourceConfiguration.value
  const selected = allSopOptions.value.filter(
    (entry) => entry.drive_file_id && fileIds.includes(entry.drive_file_id)
  )
  configuration.sop_drive_file_ids = selected.map((entry) => entry.drive_file_id || '').filter(Boolean)
  configuration.sop_sources = selected.map((entry) => ({
    drive_file_id: entry.drive_file_id || '',
    project: entry.project,
    process: entry.process,
    issue_date: entry.issue_date,
    link_url: entry.link_url,
    row_number: entry.row_number
  }))
  const first = selected[0]
  configuration.sop_drive_file_id = first?.drive_file_id || ''
  configuration.sop_project = first?.project || ''
  configuration.sop_process = first?.process || ''
  configuration.sop_issue_date = first?.issue_date || ''
  configuration.sop_link_url = first?.link_url || ''
  configuration.sop_row_number = first?.row_number ?? null
}

function handleDuroProductChange(productId: string) {
  if (!editForm.value) return
  const configuration = sourceConfiguration.value
  const product = duroProducts.value.find((item) => item._id === productId)
  configuration.duro_product_id = product?._id || ''
  configuration.duro_product_name = product?.name || ''
  configuration.duro_product_cpn = product?.cpn || ''
  configuration.duro_product_revision = product?.revision || ''
  configuration.target_revision = product?.revision || ''
  configuration.duro_submenu_ids = []
  configuration.duro_submenus = []
  duroSubmenuOptions.value = []
  duroSubmenusError.value = ''
  duroSubmenuCollapse.value = productId ? ['submenus'] : []
  if (productId) void loadDuroSubmenus(productId)
}

async function loadDuroSubmenus(productId: string) {
  duroSubmenusLoading.value = true
  duroSubmenusError.value = ''
  try {
    const response = await duroApi.productBom(productId, false)
    duroSubmenuOptions.value = response.data.root.children
    const validIds = new Set(duroSubmenuOptions.value.map((item) => item.id))
    if (editForm.value) {
      const configuration = sourceConfiguration.value
      configuration.duro_submenu_ids = (configuration.duro_submenu_ids ?? []).filter((id) => validIds.has(id))
      handleDuroSubmenuChange(configuration.duro_submenu_ids)
    }
  } catch (error: any) {
    console.error(error)
    duroSubmenuOptions.value = []
    duroSubmenusError.value = apiError(error, w('messages.submenusLoadFailed'))
  } finally {
    duroSubmenusLoading.value = false
  }
}

function handleDuroSubmenuChange(submenuIds: string[]) {
  if (!editForm.value) return
  const selectedIds = new Set(submenuIds)
  sourceConfiguration.value.duro_submenus = duroSubmenuOptions.value
    .filter((submenu) => selectedIds.has(submenu.id))
    .map((submenu) => ({ id: submenu.id, label: duroSubmenuLabel(submenu) }))
}

function duroSubmenuLabel(submenu: DuroBomNode) {
  return submenu.cpn || submenu.alias || submenu.name || submenu.id
}

function addIgnoredPartNumber() {
  const partNumber = pendingPartNumber.value.trim().toUpperCase()
  const reason = pendingPartNumberReason.value.trim()
  if (!partNumber) return ElMessage.warning(w('messages.enterBomPart'))
  if (!reason) return ElMessage.warning(w('messages.ignoreReasonRequired'))
  sourceConfiguration.value.ignored_part_numbers = [
    ...new Set([...(sourceConfiguration.value.ignored_part_numbers ?? []), partNumber])
  ]
  sourceConfiguration.value.ignored_part_number_reasons = {
    ...(sourceConfiguration.value.ignored_part_number_reasons ?? {}),
    [partNumber]: reason
  }
  pendingPartNumber.value = ''
  pendingPartNumberReason.value = ''
  ignoreRuleDialogVisible.value = false
}

function removeIgnoredPartNumber(partNumber: string) {
  sourceConfiguration.value.ignored_part_numbers = (sourceConfiguration.value.ignored_part_numbers ?? [])
    .filter((value) => value !== partNumber)
  const reasons = { ...(sourceConfiguration.value.ignored_part_number_reasons ?? {}) }
  delete reasons[partNumber]
  sourceConfiguration.value.ignored_part_number_reasons = reasons
}

function addIgnoredSopKeyword() {
  const keyword = pendingSopKeyword.value.trim()
  const reason = pendingSopKeywordReason.value.trim()
  if (!keyword) return ElMessage.warning(w('messages.enterSopKeyword'))
  if (!reason) return ElMessage.warning(w('messages.ignoreKeywordReasonRequired'))
  sourceConfiguration.value.ignored_sop_product_keywords = uniqueKeywords([
    ...(sourceConfiguration.value.ignored_sop_product_keywords ?? []),
    keyword
  ])
  sourceConfiguration.value.ignored_sop_product_keyword_reasons = {
    ...(sourceConfiguration.value.ignored_sop_product_keyword_reasons ?? {}),
    [keyword]: reason
  }
  pendingSopKeyword.value = ''
  pendingSopKeywordReason.value = ''
  ignoreRuleDialogVisible.value = false
}

function openIgnoreRuleDialog(type: 'sop' | 'part') {
  ignoreRuleDialogType.value = type
  pendingSopKeyword.value = ''
  pendingSopKeywordReason.value = ''
  pendingPartNumber.value = ''
  pendingPartNumberReason.value = ''
  ignoreRuleDialogVisible.value = true
}

function confirmIgnoreRule() {
  if (ignoreRuleDialogType.value === 'sop') addIgnoredSopKeyword()
  else addIgnoredPartNumber()
}

function removeIgnoredSopKeyword(keyword: string) {
  sourceConfiguration.value.ignored_sop_product_keywords = (sourceConfiguration.value.ignored_sop_product_keywords ?? [])
    .filter((value) => value !== keyword)
  const reasons = { ...(sourceConfiguration.value.ignored_sop_product_keyword_reasons ?? {}) }
  delete reasons[keyword]
  sourceConfiguration.value.ignored_sop_product_keyword_reasons = reasons
}

function uniqueKeywords(values: string[]) {
  const seen = new Set<string>()
  return values.map((value) => value.trim()).filter((value) => {
    const normalized = value.toLocaleLowerCase()
    if (!normalized || seen.has(normalized)) return false
    seen.add(normalized)
    return true
  })
}

function sopOptionLabel(entry: SopCatalogEntry) {
  return `${entry.project || w('uncategorizedProduct')} · ${entry.process}${entry.issue_date ? ` · ${entry.issue_date}` : ''}`
}

function duroProductLabel(product: DuroProduct) {
  const identity = product.cpn || product.name || product._id
  const revision = product.revision ? ` · ${product.revision}` : ''
  return `${identity}${product.name && product.name !== identity ? ` · ${product.name}` : ''}${revision}`
}

async function loadRuns(workflowId: string) {
  historyLoading.value = true
  try {
    const [createdFrom, createdTo] = historyDateParams()
    const response = await workflowApi.runs(
      workflowId,
      historyPage.value,
      historyPageSize.value,
      createdFrom,
      createdTo
    )
    if (selectedWorkflowId.value === workflowId) {
      const currentRuns = new Map(workflowRuns.value.map((run) => [run.id, run]))
      const expandedRunIds = new Set(activeRunIds.value)
      const detailRunIdsToReload = new Set<string>()
      historyTotal.value = response.data.total
      historySuccessCount.value = response.data.success_count
      historyFailedCount.value = response.data.failed_count
      historyWarningCount.value = response.data.warning_count
      workflowRuns.value = response.data.items.map((summary) => {
        const current = currentRuns.get(summary.id)
        const statusChanged = Boolean(current && current.status !== summary.status)
        if (statusChanged) {
          // 历史列表只返回摘要（差异数组为空）。运行结束后必须让旧的运行中明细失效，
          // 否则展开项会一直把空摘要当成已经加载完成的明细。
          runDetailLoaded[summary.id] = false
          runDetailErrors[summary.id] = ''
          if (expandedRunIds.has(summary.id)) detailRunIdsToReload.add(summary.id)
        }
        if (
          current?.report &&
          summary.report &&
          runDetailLoaded[summary.id] &&
          current.status === summary.status
        ) {
          return {
            ...summary,
            report: {
              ...summary.report,
              differences: current.report.differences,
              total_difference_count: summary.report.total_difference_count,
              ignored_items: current.report.ignored_items,
              total_ignored_count: summary.report.total_ignored_count
            }
          }
        }
        return summary
      })
      for (const run of workflowRuns.value) {
        if (['queued', 'running'].includes(run.status)) {
          setWorkflowRunning(workflowId, true)
          startPollingWorkflowRun(workflowId, run.id)
          if (expandedRunIds.has(run.id) && !runDetailLoaded[run.id]) {
            void loadRunDetail(run.id)
          }
        }
      }
      for (const runId of detailRunIdsToReload) {
        void loadRunDetail(runId, true)
      }
    }
    return response.data.items
  } catch (error) {
    console.error(error)
    return []
  } finally {
    historyLoading.value = false
  }
}

function historyDateParams(): [string | undefined, string | undefined] {
  if (!historyDateRange.value) return [undefined, undefined]
  const start = new Date(historyDateRange.value[0])
  const end = new Date(historyDateRange.value[1])
  start.setHours(0, 0, 0, 0)
  end.setHours(23, 59, 59, 999)
  return [start.toISOString(), end.toISOString()]
}

function handleHistoryDateChange() {
  historyPage.value = 1
  activeRunIds.value = []
  cancelHistorySelection()
  if (selectedWorkflowId.value) void loadRuns(selectedWorkflowId.value)
}

function handleHistoryPageChange(page: number) {
  historyPage.value = page
  activeRunIds.value = []
  cancelHistorySelection()
  if (selectedWorkflowId.value) void loadRuns(selectedWorkflowId.value)
}

function toggleRunSelection(runId: string, selected: boolean) {
  const next = new Set(selectedRunIds.value)
  if (selected) next.add(runId)
  else next.delete(runId)
  selectedRunIds.value = next
}

function cancelHistorySelection() {
  historySelectionMode.value = false
  selectedRunIds.value = new Set()
}

async function handleHistoryDeleteButton() {
  if (!historySelectionMode.value) {
    historySelectionMode.value = true
    return
  }
  if (!selectedRunCount.value || deletingRuns.value) return
  try {
    await ElMessageBox.confirm(
      w('dialogs.deleteRunsBody', { count: selectedRunCount.value }),
      w('dialogs.deleteRunsTitle'),
      {
        confirmButtonText: w('deleteAll'),
        cancelButtonText: t('common.actions.cancel'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  deletingRuns.value = true
  try {
    const response = await workflowApi.deleteRuns([...selectedRunIds.value])
    const deletedCount = response.data.deleted_count
    const remainingTotal = Math.max(0, historyTotal.value - deletedCount)
    const lastPage = Math.max(1, Math.ceil(remainingTotal / historyPageSize.value))
    historyPage.value = Math.min(historyPage.value, lastPage)
    cancelHistorySelection()
    if (selectedWorkflowId.value) await loadRuns(selectedWorkflowId.value)
    await loadWorkflows()
    ElMessage.success(w('messages.runsDeleted', { count: deletedCount }))
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.deleteRunsFailed'))
  } finally {
    deletingRuns.value = false
  }
}

function handleRunCollapseChange(activeNames: string | number | Array<string | number>) {
  const names = Array.isArray(activeNames) ? activeNames.map(String) : [String(activeNames)]
  for (const runId of names) {
    if (runId && !runDetailLoaded[runId] && !runDetailLoading[runId]) {
      void loadRunDetail(runId)
    }
  }
}

async function loadRunDetail(runId: string, force = false) {
  if (runDetailLoading[runId]) {
    if (force) runDetailReloadPending[runId] = true
    return
  }
  const run = workflowRuns.value.find((item) => item.id === runId)
  if (!run) return
  if (force) runDetailLoaded[runId] = false
  runDetailLoading[runId] = true
  runDetailErrors[runId] = ''
  try {
    const response = await workflowApi.runDetail(runId)
    const index = workflowRuns.value.findIndex((item) => item.id === runId)
    if (index < 0) return
    const detail = response.data.run
    workflowRuns.value[index] = detail
    runDetailLoaded[runId] = true
  } catch (error: any) {
    console.error(error)
    runDetailErrors[runId] = apiError(error, w('messages.runDetailFailed'))
  } finally {
    runDetailLoading[runId] = false
    if (runDetailReloadPending[runId]) {
      runDetailReloadPending[runId] = false
      void loadRunDetail(runId, true)
    }
  }
}

async function exportWorkflowRun(run: WorkflowRun) {
  if (runExporting[run.id]) return
  runExporting[run.id] = true
  try {
    const response = await workflowApi.exportRun(run.id)
    const contentDisposition = String(response.headers['content-disposition'] || '')
    const encodedFilename = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition)?.[1]
    const quotedFilename = /filename="([^"]+)"/i.exec(contentDisposition)?.[1]
    const fallbackName = `${run.workflow_name.replace(/[\\/:*?"<>|]+/g, '_') || w('workflows')}_${w('differenceDetails')}.xlsx`
    let filename = quotedFilename || fallbackName
    if (encodedFilename) {
      try {
        filename = decodeURIComponent(encodedFilename)
      } catch {
        filename = fallbackName
      }
    }
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(w('messages.exported'))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.exportFailed')))
  } finally {
    runExporting[run.id] = false
  }
}

async function saveSelectedWorkflow() {
  if (!selectedWorkflowId.value || !editForm.value) return
  if (!editForm.value.name.trim()) {
    ElMessage.warning(w('messages.enterWorkflowName'))
    return
  }
  saving.value = true
  try {
    const response = await workflowApi.update(selectedWorkflowId.value, editForm.value)
    const index = workflows.value.findIndex((item) => item.id === response.data.id)
    if (index >= 0) workflows.value[index] = response.data
    editForm.value = cloneWorkflowPayload(response.data)
    await refreshWorkflowIgnoredPartRules(response.data.id)
    ElMessage.success(w('messages.saved'))
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function createWorkflow() {
  if (!createForm.name.trim()) {
    ElMessage.warning(w('messages.enterWorkflowName'))
    return
  }
  creating.value = true
  try {
    const isDuro = createForm.template === 'duro'
    const payload: WorkflowPayload = {
      name: createForm.name.trim(),
      description: createForm.description.trim(),
      kind: isDuro ? 'duro_bom_check' : 'custom',
      status: 'draft',
      schedule: { enabled: false, interval_minutes: 60 },
      configuration: isDuro
        ? normalizeWorkflowConfiguration({})
        : {},
      steps: isDuro ? duroTemplateSteps() : []
    }
    const response = await workflowApi.create(payload)
    workflows.value = [response.data, ...workflows.value]
    selectWorkflow(response.data.id)
    editorVisible.value = false
    workflowListVisible.value = true
    createDialogVisible.value = false
    ElMessage.success(w('messages.created'))
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.createFailed'))
  } finally {
    creating.value = false
  }
}

async function copyWorkflow(workflow: Workflow) {
  if (isWorkflowCopying(workflow.id)) return
  copyingWorkflowIds.value = new Set(copyingWorkflowIds.value).add(workflow.id)
  try {
    const payload = cloneWorkflowPayload(workflow)
    payload.name = w('copyName', { name: workflow.name })
    await workflowApi.create(payload)
    await loadWorkflows()
    ElMessage.success(w('messages.copied', { name: workflow.name }))
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.copyFailed'))
  } finally {
    const next = new Set(copyingWorkflowIds.value)
    next.delete(workflow.id)
    copyingWorkflowIds.value = next
  }
}

async function deleteWorkflow(workflow: Workflow) {
  try {
    await ElMessageBox.confirm(w('dialogs.deleteWorkflowBody', { name: workflow.name }), w('dialogs.deleteWorkflowTitle'), {
      confirmButtonText: t('common.actions.delete'),
      cancelButtonText: t('common.actions.cancel'),
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await workflowApi.remove(workflow.id)
    workflows.value = workflows.value.filter((item) => item.id !== workflow.id)
    const nextAttention = { ...workflowAttentionMap.value }
    delete nextAttention[workflow.id]
    workflowAttentionMap.value = nextAttention
    if (selectedWorkflowId.value === workflow.id) {
      selectedWorkflowId.value = null
      editForm.value = null
      workflowRuns.value = []
      editorVisible.value = false
      workflowListVisible.value = true
    }
    ElMessage.success(w('messages.deleted'))
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.deleteFailed'))
  }
}

async function triggerSelectedWorkflow() {
  const workflow = selectedWorkflow.value
  if (!workflow) return
  await triggerWorkflow(workflow)
}

async function triggerWorkflow(workflow: Workflow) {
  if (isWorkflowRunning(workflow.id)) return
  setWorkflowRunning(workflow.id, true)
  triggering.value = true
  try {
    const response = await workflowApi.trigger(workflow.id)
    ElMessage.success(w('messages.triggered'))
    if (editorVisible.value && selectedWorkflowId.value === workflow.id) {
      builderTab.value = 'history'
      activeRunIds.value = [response.data.id]
    }
    startPollingWorkflowRun(workflow.id, response.data.id)
    await loadWorkflows()
  } catch (error) {
    console.error(error)
    ElMessage.error(w('messages.triggerFailed'))
    setWorkflowRunning(workflow.id, false)
  } finally {
    triggering.value = false
  }
}

function startPollingWorkflowRun(workflowId: string, runId: string) {
  if (pollingRunIds.value.has(runId)) return
  pollingRunIds.value = new Set(pollingRunIds.value).add(runId)
  workflowPollingRunIds.value = {
    ...workflowPollingRunIds.value,
    [workflowId]: runId
  }
  void pollWorkflowRun(workflowId, runId)
}

function stopPollingWorkflowRun(workflowId: string, runId: string) {
  const next = new Set(pollingRunIds.value)
  next.delete(runId)
  pollingRunIds.value = next
  if (workflowPollingRunIds.value[workflowId] === runId) {
    const { [workflowId]: _removed, ...rest } = workflowPollingRunIds.value
    workflowPollingRunIds.value = rest
  }
}

async function pollWorkflowRun(workflowId: string, runId: string, attempt = 0) {
  try {
    const response = await workflowApi.runDetail(runId, 0, 1)
    const run = response.data.run
    mergePolledWorkflowRun(run)
    if (!run || !['queued', 'running'].includes(run.status) || attempt >= 1800) {
      stopPollingWorkflowRun(workflowId, runId)
      setWorkflowRunning(workflowId, false)
      if (selectedWorkflowId.value === workflowId) await loadRuns(workflowId)
      void loadWorkflowAttentionSummary()
      return
    }
  } catch (error) {
    console.error(error)
    if (attempt >= 1800) {
      stopPollingWorkflowRun(workflowId, runId)
      setWorkflowRunning(workflowId, false)
      return
    }
  }
  window.setTimeout(() => void pollWorkflowRun(workflowId, runId, attempt + 1), 1000)
}

function mergePolledWorkflowRun(run: WorkflowRun | undefined) {
  if (!run) return
  const index = workflowRuns.value.findIndex((item) => item.id === run.id)
  if (index < 0) return
  const current = workflowRuns.value[index]
  workflowRuns.value[index] = {
    ...current,
    status: run.status,
    message: run.message,
    logs: run.logs,
    started_at: run.started_at,
    finished_at: run.finished_at
  }
  if (activeRunIds.value.includes(run.id)) {
    runDetailLoaded[run.id] = true
    runDetailErrors[run.id] = ''
  }
}

function duroTemplateSteps(): WorkflowStep[] {
  return [
    createStep(w('steps.compareName'), 'bom_compare', w('steps.compareDescription')),
    createStep(w('steps.reportName'), 'report', w('steps.reportDescription'))
  ]
}

function createStep(name: string, kind: WorkflowStepKind, description: string): WorkflowStep {
  return {
    id: `step_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    name,
    kind,
    description,
    configuration: {}
  }
}

function stepIcon(kind: WorkflowStepKind) {
  if (kind === 'duro_bom_fetch') return Files
  if (kind === 'bom_compare') return DataAnalysis
  if (kind === 'report') return DocumentChecked
  return Connection
}

function scheduleText(workflow: Workflow) {
  return workflow.schedule.enabled ? w('everyMinutes', { minutes: workflow.schedule.interval_minutes }) : w('manualOnly')
}

function formatDate(value: string | null) {
  if (!value) return w('notScheduled')
  return new Date(value).toLocaleString(locale.value, { hour12: false })
}

function formatLastRunDate(value: string | null) {
  if (!value) return w('neverRun')
  return new Date(value).toLocaleString(locale.value, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

function formatRunDuration(run: WorkflowRun) {
  if (!run.finished_at) return '—'
  const start = new Date(run.started_at || run.created_at).getTime()
  const finish = new Date(run.finished_at).getTime()
  const milliseconds = Math.max(0, finish - start)
  if (milliseconds < 1000) return w('milliseconds', { count: milliseconds })
  const totalSeconds = Math.round(milliseconds / 1000)
  if (totalSeconds < 60) return w('seconds', { count: totalSeconds })
  const totalMinutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (totalMinutes < 60) return w('minutesSeconds', { minutes: totalMinutes, seconds })
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return w('hoursMinutes', { hours, minutes })
}

function formatReportQuantity(value: number | null) {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? value.toString() : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
}

function differenceLabel(status: string) {
  return differenceStatusText.value[status as WorkflowBomDifferenceStatus] || status
}

function compactEnglishText(fullText: string, abbreviatedText: string) {
  return locale.value.toLowerCase().startsWith('en') ? abbreviatedText : fullText
}

function historyTableHeader(abbreviatedText: string) {
  return ({ column }: { column: { label: string } }) => h(
    ElTooltip,
    { content: column.label, placement: 'top', showAfter: 300 },
    { default: () => h('span', { class: 'history-table-header-text' }, compactEnglishText(column.label, abbreviatedText)) }
  )
}

function compactDifferenceLabel(status: string) {
  const abbreviatedLabels: Record<WorkflowBomDifferenceStatus, string> = {
    missing_in_duro: 'Missing',
    extra_in_duro: 'Extra',
    quantity_mismatch: 'Qty Mismatch',
    quantity_unknown: 'Qty Unknown',
    parent_bom_ignored: 'Parent BOM'
  }
  return compactEnglishText(
    differenceLabel(status),
    abbreviatedLabels[status as WorkflowBomDifferenceStatus] || status
  )
}

function ignoredDifferenceLabel(row: WorkflowBomIgnoredItem) {
  if (row.ignore_type === 'parent_bom') return w('parentBomIgnored')
  return row.ignore_type === 'part_number_cleanup' ? w('materialCleanup') : differenceLabel(row.status)
}

function compactIgnoredDifferenceLabel(row: WorkflowBomIgnoredItem) {
  if (row.ignore_type === 'parent_bom') return compactEnglishText(w('parentBomIgnored'), 'Parent BOM')
  return row.ignore_type === 'part_number_cleanup'
    ? compactEnglishText(w('materialCleanup'), 'Cleanup')
    : compactDifferenceLabel(row.status)
}

function ignoredTypeLabel(ignoreType: string) {
  if (ignoreType === 'part_number_cleanup') return w('defaultPartCleanup')
  if (ignoreType === 'part_number') return w('ignoredPart')
  if (ignoreType === 'parent_bom') return w('parentBom')
  if (ignoreType === 'supply') return w('supply')
  return w('sopProductKeyword')
}

function compactIgnoredTypeLabel(ignoreType: string) {
  const abbreviatedText = ignoreType === 'part_number_cleanup'
    ? 'Part Cleanup'
    : ignoreType === 'part_number' ? 'Part No.' : ignoreType === 'parent_bom' ? 'Parent BOM' : ignoreType === 'supply' ? 'Supply' : 'SOP Keyword'
  return compactEnglishText(ignoredTypeLabel(ignoreType), abbreviatedText)
}

function differenceOccurrenceSteps(row: WorkflowBomDifference): WorkflowSopOccurrenceStep[] {
  if (row.sop_occurrence_steps?.length) return row.sop_occurrence_steps
  return (row.sop_quantity_decisions || []).flatMap((decision) => {
    const pages = decision.page_numbers?.length ? decision.page_numbers : [0]
    return pages.map((pageNumber, pageIndex) => ({
      source: decision.source,
      page_number: pageNumber,
      evidence: decision.evidence,
      quantity_delta: pageIndex === 0 && decision.accumulate ? decision.quantity_delta : 0,
      accumulate: pageIndex === 0 && decision.accumulate,
      action: decision.action,
      reason: pageIndex === 0 ? decision.reason : w('sameEventOtherLocation')
    }))
  })
}

function differenceSopOccurrenceCount(row: WorkflowBomDifference) {
  if (row.sop_occurrence_count > 0) return row.sop_occurrence_count
  return differenceOccurrenceSteps(row).length
}

function differenceFinalSopQuantity(row: WorkflowBomDifference) {
  if (row.status === 'extra_in_duro' && row.sop_quantity === null) return '0'
  return formatReportQuantity(row.sop_quantity)
}

function differenceOccurrenceTotal(row: WorkflowBomDifference) {
  return differenceOccurrenceSteps(row).reduce((total, step) => total + Number(step.quantity_delta || 0), 0)
}

function formatOccurrenceDelta(value: number) {
  const formatted = formatReportQuantity(value)
  return value >= 0 ? `+${formatted}` : formatted
}

function differenceSummary(row: WorkflowBomDifference) {
  const material = row.name ? `${row.part_number} (${row.name})` : row.part_number
  const occurrenceCount = differenceSopOccurrenceCount(row)
  if (row.status === 'missing_in_duro') {
    return w('summaries.missing', { material, occurrences: occurrenceCount, sopQuantity: formatReportQuantity(row.sop_quantity) })
  }
  if (row.status === 'extra_in_duro') {
    return w('summaries.extra', { material, duroQuantity: formatReportQuantity(row.duro_quantity) })
  }
  if (row.status === 'quantity_mismatch') {
    return w('summaries.mismatch', { material, occurrences: occurrenceCount, sopQuantity: formatReportQuantity(row.sop_quantity), duroQuantity: formatReportQuantity(row.duro_quantity), delta: formatReportQuantity(row.quantity_delta) })
  }
  return w('summaries.unknown', { material, occurrences: occurrenceCount, duroQuantity: formatReportQuantity(row.duro_quantity) })
}

function differenceIgnoreKey(workflowId: string, partNumber: string) {
  return `${workflowId}:${partNumber}`
}

function isDifferenceIgnoreUpdating(workflowId: string, partNumber: string) {
  return Boolean(differenceIgnoreUpdating[differenceIgnoreKey(workflowId, partNumber)])
}

function setDifferenceTableRef(runId: string, instance: unknown) {
  if (instance) differenceTableRefs.set(runId, instance as TableInstance)
  else differenceTableRefs.delete(runId)
}

function handleDifferenceRowClick(runId: string, row: WorkflowBomDifference) {
  closeDifferenceContextMenu()
  differenceTableRefs.get(runId)?.toggleRowExpansion(row)
}

function handleDifferenceRowContextMenu(
  run: WorkflowRun,
  row: WorkflowBomDifference,
  _column: unknown,
  event: MouseEvent
) {
  openDifferenceContextMenu(run, row, event, 'differences')
}

function handleIgnoredRowContextMenu(
  run: WorkflowRun,
  row: WorkflowBomIgnoredItem,
  _column: unknown,
  event: MouseEvent
) {
  openDifferenceContextMenu(run, row, event, 'ignored')
}

function openDifferenceContextMenu(
  run: WorkflowRun,
  row: WorkflowBomDifference | WorkflowBomIgnoredItem,
  event: MouseEvent,
  source: 'differences' | 'ignored'
) {
  event.preventDefault()
  event.stopPropagation()

  const menuWidth = 220
  const menuHeight = source === 'ignored' ? 48 : 94
  const viewportPadding = 8
  differenceContextMenu.x = Math.max(
    viewportPadding,
    Math.min(event.clientX, window.innerWidth - menuWidth - viewportPadding)
  )
  differenceContextMenu.y = Math.max(
    viewportPadding,
    Math.min(event.clientY, window.innerHeight - menuHeight - viewportPadding)
  )
  differenceContextMenu.source = source
  differenceContextMenu.run = run
  differenceContextMenu.row = row
  differenceContextMenu.visible = true
}

function closeDifferenceContextMenu() {
  differenceContextMenu.visible = false
}

async function handleDifferenceContextMenuCommand(command: 'ignore' | 'expand' | 'restore') {
  const run = differenceContextMenu.run
  const row = differenceContextMenu.row
  closeDifferenceContextMenu()
  if (!run || !row) return
  if (command === 'restore') {
    if ('ignore_type' in row) await restoreIgnoredWorkflowDifference(run, row)
    return
  }
  await handleDifferenceRowMenuCommand(run, row, command)
}

function handleDifferenceContextMenuKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') closeDifferenceContextMenu()
}

async function handleDifferenceRowMenuCommand(
  run: WorkflowRun,
  row: WorkflowBomDifference,
  command: string | number | object
) {
  if (command === 'ignore') {
    await ignoreWorkflowDifference(run, row)
  } else if (command === 'unignore') {
    await unignoreWorkflowDifference(run, row)
  } else if (command === 'expand') {
    differenceTableRefs.get(run.id)?.toggleRowExpansion(row, true)
  }
}

async function ignoreWorkflowDifference(run: WorkflowRun, row: WorkflowBomDifference) {
  let reason = ''
  try {
    const response = await ElMessageBox.prompt(
      w('dialogs.partIdentity', { part: row.part_number, name: row.name ? ` · ${row.name}` : '' }),
      w('dialogs.ignoreDifferenceTitle'),
      {
        confirmButtonText: w('confirmIgnore'),
        cancelButtonText: t('common.actions.cancel'),
        inputType: 'textarea',
        inputPlaceholder: w('ignoreReasonPlaceholder'),
        inputValidator: (value) => value.trim().length > 0 || w('enterIgnoreReason')
      }
    )
    reason = response.value.trim()
  } catch {
    return
  }

  const key = differenceIgnoreKey(run.workflow_id, row.part_number)
  differenceIgnoreUpdating[key] = true
  try {
    await workflowApi.ignorePart(run.workflow_id, row.part_number, reason)
    await refreshWorkflowIgnoredPartRules(run.workflow_id)
    await loadRunDetail(run.id, true)
    ElMessage.success(w('messages.partIgnored', { part: row.part_number }))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.ignorePartFailed')))
  } finally {
    differenceIgnoreUpdating[key] = false
  }
}

async function unignoreWorkflowDifference(run: WorkflowRun, row: WorkflowBomDifference) {
  try {
    await ElMessageBox.confirm(
      w('dialogs.unignoreBody', { part: row.part_number }),
      w('dialogs.unignoreTitle'),
      {
        confirmButtonText: w('confirmUnignore'),
        cancelButtonText: w('back'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  const key = differenceIgnoreKey(run.workflow_id, row.part_number)
  differenceIgnoreUpdating[key] = true
  try {
    await workflowApi.unignorePart(run.workflow_id, row.part_number)
    await refreshWorkflowIgnoredPartRules(run.workflow_id)
    await loadRunDetail(run.id, true)
    ElMessage.success(w('messages.partUnignored', { part: row.part_number }))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.unignoreFailed')))
  } finally {
    differenceIgnoreUpdating[key] = false
  }
}

function canRestoreIgnoredDifference(
  row: WorkflowBomDifference | WorkflowBomIgnoredItem
): row is WorkflowBomIgnoredItem {
  return 'ignore_type' in row && row.ignore_type === 'part_number' && Boolean(row.ignored_at)
}

function ignoredDifferenceRestoreHint(row: WorkflowBomDifference | WorkflowBomIgnoredItem) {
  if (!('ignore_type' in row)) return ''
  if (row.ignore_type === 'sop_product_keyword') return w('restoreHints.sopKeyword')
  if (row.ignore_type === 'part_number_cleanup') return w('restoreHints.cleanup')
  if (!row.ignored_at) return w('restoreHints.fixedConfig')
  return w('restoreHints.restoreAs', { type: differenceLabel(row.status) })
}

async function restoreIgnoredWorkflowDifference(run: WorkflowRun, row: WorkflowBomIgnoredItem) {
  if (!canRestoreIgnoredDifference(row)) return
  try {
    await ElMessageBox.confirm(
      w('dialogs.restoreBody', { part: row.part_number, type: differenceLabel(row.status) }),
      w('dialogs.restoreTitle'),
      {
        confirmButtonText: w('confirmRestore'),
        cancelButtonText: t('common.actions.cancel'),
        type: 'warning'
      }
    )
  } catch {
    return
  }

  const key = differenceIgnoreKey(run.workflow_id, row.part_number)
  differenceIgnoreUpdating[key] = true
  try {
    await workflowApi.unignorePart(run.workflow_id, row.part_number)
    await refreshWorkflowIgnoredPartRules(run.workflow_id)
    await loadRunDetail(run.id, true)
    ElMessage.success(w('messages.restored', { type: differenceLabel(row.status), part: row.part_number }))
  } catch (error: any) {
    console.error(error)
    ElMessage.error(apiError(error, w('messages.restoreFailed')))
  } finally {
    differenceIgnoreUpdating[key] = false
  }
}

function runWarningCount(run: WorkflowRun) {
  return run.report?.warning_difference_count
    ?? run.report?.total_difference_count
    ?? run.report?.differences.length
    ?? 0
}

function runHasWarnings(run: WorkflowRun) {
  return run.status === 'succeeded' && runWarningCount(run) > 0
}

function runStatusClass(run: WorkflowRun) {
  return runHasWarnings(run) ? 'is-warning' : `is-${run.status}`
}

function runMessageText(run: WorkflowRun) {
  if (run.status === 'succeeded' && run.report) return w('verificationCompleted', { count: runWarningCount(run) })
  if (isRunInProgress(run)) {
    return run.logs[run.logs.length - 1]?.trim() || w('workflowRunning')
  }
  const message = run.message.trim()
  if (message) return run.status === 'failed' ? w('failureReason', { reason: message }) : message
  if (run.status === 'failed') {
    const lastLog = run.logs[run.logs.length - 1]?.replace(/^[^:：]+[：:]\s*/, '').trim()
    return w('failureReason', { reason: lastLog || w('noFailureReason') })
  }
  return w('workflowRunning')
}

function isRunInProgress(run: WorkflowRun) {
  return run.status === 'queued' || run.status === 'running'
}

function truncatedRunMessage(run: WorkflowRun, limit = 38) {
  const message = runMessageText(run)
  return message.length > limit ? `${message.slice(0, limit)}…` : message
}

function reportFilter(runId: string): ReportDifferenceFilter {
  return reportDifferenceFilters[runId] || 'all'
}

function reportView(runId: string) {
  return reportViews[runId] || 'differences'
}

function setReportView(runId: string, view: 'differences' | 'ignored') {
  reportViews[runId] = view
}

function reportSearchText(runId: string) {
  return reportSearchTexts[runId] || ''
}

function setReportSearchText(runId: string, value: string) {
  reportSearchTexts[runId] = value
}

function setReportFilter(runId: string, value: string) {
  reportDifferenceFilters[runId] = value as ReportDifferenceFilter
}

function reportSubmenuFilter(runId: string) {
  return reportSubmenuFilters[runId] || []
}

function setReportSubmenuFilter(runId: string, value: string[]) {
  reportSubmenuFilters[runId] = value || []
}

function reportSubmenuLabel(submenu: { label: string; name: string }) {
  return submenu.name && submenu.name !== submenu.label
    ? `${submenu.label} · ${submenu.name}`
    : submenu.label
}

function filteredReportDifferences(run: WorkflowRun) {
  return filterReportItems(run.report?.differences ?? [], run.id)
}

function filteredReportIgnoredItems(run: WorkflowRun) {
  return filterReportItems(run.report?.ignored_items ?? [], run.id)
}

function filterReportItems<T extends {
  status: WorkflowBomDifferenceStatus
  duro_submenu_ids: string[]
  part_number: string
  name: string
  normalized_part_number?: string | null
}>(
  items: T[],
  runId: string
) {
  const filter = reportFilter(runId)
  const submenuFilters = reportSubmenuFilter(runId)
  const keyword = reportSearchText(runId).trim().toLowerCase()
  const bySearch = keyword
    ? items.filter((item) => [item.part_number, item.normalized_part_number, item.name]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword)))
    : items
  const bySubmenu = submenuFilters.length === 0
    ? bySearch
    : bySearch.filter((item) => item.duro_submenu_ids.some((id) => submenuFilters.includes(id)))
  if (filter === 'all') return bySubmenu
  if (filter === 'structure') {
    return bySubmenu.filter((item) => ['missing_in_duro', 'extra_in_duro'].includes(item.status))
  }
  return bySubmenu.filter((item) => item.status === filter)
}

function differenceRowClassName({ row }: { row: WorkflowBomDifference }) {
  return `difference-row is-${row.status}${row.is_ignored ? ' is-ignored' : ''}`
}

onMounted(() => {
  document.addEventListener('click', closeDifferenceContextMenu)
  document.addEventListener('scroll', closeDifferenceContextMenu, true)
  document.addEventListener('keydown', handleDifferenceContextMenuKeydown)
  window.addEventListener('resize', closeDifferenceContextMenu)
  void loadWorkflows()
  void loadSopSources()
  void loadDuroProducts()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeDifferenceContextMenu)
  document.removeEventListener('scroll', closeDifferenceContextMenu, true)
  document.removeEventListener('keydown', handleDifferenceContextMenuKeydown)
  window.removeEventListener('resize', closeDifferenceContextMenu)
})
</script>
