<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">V</div>
        <div>
          <strong>Productions</strong>
          <span>Versions</span>
        </div>
      </div>

      <nav class="main-nav" aria-label="主导航">
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'workflows' }"
          type="button"
          @click="activeModule = 'workflows'"
        >
          <el-icon><Connection /></el-icon>
          工作流
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'sop' }"
          type="button"
          @click="activeModule = 'sop'"
        >
          <el-icon><FolderOpened /></el-icon>
          SOP
        </button>
        <button
          class="nav-item"
          :class="{ 'is-active': activeModule === 'duro' }"
          type="button"
          @click="activeModule = 'duro'"
        >
          <el-icon><Box /></el-icon>
          Duro
        </button>
      </nav>

      <div class="sidebar-note">
        <div class="sidebar-note-title">
          <span class="status-dot" :class="dataSourceStatusClass"></span>
          <strong>{{ dataSourceStatusTitle }}</strong>
        </div>
        <span class="sidebar-note-detail" :title="dataSourceErrorDetail">{{ dataSourceStatusDetail }}</span>
      </div>
    </aside>

    <main v-if="activeModule === 'workflows'" class="main-content">
      <header class="topbar">
        <div>
          <p class="eyebrow">VERSION AUTOMATION</p>
          <h1>版本检测工作流</h1>
          <p>创建、编排并运行产品版本与 BOM 核对流程。</p>
        </div>
        <div class="topbar-actions">
          <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">新建工作流</el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadWorkflows">刷新</el-button>
        </div>
      </header>

      <section
        class="workspace"
        :class="{ 'is-list-only': !editorVisible, 'is-list-hidden': editorVisible && !workflowListVisible }"
      >
        <aside v-if="workflowListVisible" class="workflow-list-panel">
          <div class="panel-heading">
            <div>
              <span>WORKFLOWS</span>
              <strong>工作流列表</strong>
            </div>
            <el-button
              v-if="editorVisible"
              text
              :icon="Close"
              aria-label="关闭工作流列表"
              @click="closeWorkflowList"
            >关闭</el-button>
          </div>

          <div class="workflow-list-scroll">
            <div v-if="loading && !workflows.length" class="list-state">正在加载工作流…</div>
            <div v-else-if="!workflows.length" class="list-state">还没有工作流</div>
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
                <strong>{{ workflow.name }}</strong>
                <small class="workflow-list-meta">
                  <span class="workflow-list-meta-left">
                    {{ workflow.steps.length }} 步 · 历史 {{ workflow.run_count || 0 }} 次 ·
                    上一次运行 {{ formatLastRunDate(workflow.last_run_at) }}
                    <span class="workflow-status" :class="`is-${workflow.status}`">{{ statusText[workflow.status] }}</span>
                  </span>
                </small>
              </span>
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                @click.stop
                @command="handleWorkflowCommand(workflow, $event)"
              >
                <button class="workflow-more-button" type="button" aria-label="工作流操作" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="copy" :disabled="isWorkflowCopying(workflow.id)">复制</el-dropdown-item>
                    <el-dropdown-item command="run" :disabled="isWorkflowRunning(workflow.id)">运行</el-dropdown-item>
                    <el-dropdown-item command="history">运行历史</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
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
                <p>{{ editForm.description || '暂无描述' }}</p>
              </div>
            </div>
            <div class="builder-actions">
              <el-button
                :icon="VideoPlay"
                :loading="triggering"
                :disabled="isWorkflowRunning(selectedWorkflow.id)"
                @click="triggerSelectedWorkflow"
              >运行</el-button>
              <template v-if="builderTab === 'editor'">
                <el-button type="primary" :icon="Check" :loading="saving" @click="saveSelectedWorkflow">保存</el-button>
              </template>
              <el-button text :icon="Close" aria-label="关闭" @click="closeWorkflowEditor">关闭</el-button>
            </div>
          </header>

          <nav class="builder-navigation" aria-label="工作流详情导航">
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'editor' }"
              @click="builderTab = 'editor'"
            >
              编辑工作流
            </button>
            <button
              type="button"
              :class="{ 'is-active': builderTab === 'history' }"
              @click="builderTab = 'history'"
            >
              历史运行
              <span>{{ historyTotal }}</span>
            </button>
          </nav>

          <div class="builder-body">
            <template v-if="builderTab === 'editor'">
              <section class="configuration-strip">
                <label class="config-field is-wide">
                  <span>工作流名称</span>
                  <el-input v-model="editForm.name" />
                </label>
                <label class="config-field">
                  <span>状态</span>
                  <el-select v-model="editForm.status">
                    <el-option label="草稿" value="draft" />
                    <el-option label="启用" value="active" />
                    <el-option label="暂停" value="paused" />
                  </el-select>
                </label>
                <label class="config-field schedule-field">
                  <span>定时触发</span>
                  <div class="schedule-control">
                    <el-switch v-model="editForm.schedule.enabled" />
                    <el-input-number
                      v-model="editForm.schedule.interval_minutes"
                      :disabled="!editForm.schedule.enabled"
                      :min="1"
                      :max="10080"
                      controls-position="right"
                    />
                    <em>分钟</em>
                  </div>
                </label>
                <label v-if="editForm.kind === 'duro_bom_check'" class="config-field quantity-warning-field">
                  <span>忽略数量差异告警</span>
                  <div class="quantity-warning-control">
                    <el-switch v-model="sourceConfiguration.ignore_quantity_mismatch_warning" />
                    <em>仍显示数量差异，不计入警告</em>
                  </div>
                </label>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-source-grid">
                <article class="workflow-source-card is-sop">
                  <header>
                    <div class="section-label">
                      <span>SOP SOURCE</span>
                      <strong>SOP 产品</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="sopSourcesLoading"
                      @click="loadSopSources(true)"
                    >手动刷新</el-button>
                  </header>
                  <p>可按产品和工序筛选全部 SOP；核对只使用全文料号引用，不读取物料清单页。</p>
                  <div class="sop-source-filters">
                    <el-select
                      v-model="sopProjectFilter"
                      clearable
                      filterable
                      placeholder="筛选产品"
                      @change="sopProcessFilter = ''"
                    >
                      <el-option
                        v-for="project in sopProjectOptions"
                        :key="project"
                        :label="project"
                        :value="project"
                      />
                    </el-select>
                    <el-select v-model="sopProcessFilter" clearable filterable placeholder="筛选工序">
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
                    placeholder="选择一个或多个 SOP"
                    @change="handleSopSourceChange"
                  >
                    <el-option
                      v-for="entry in displayedSopOptions"
                      :key="`${entry.row_number}-${entry.drive_file_id}`"
                      :label="sopOptionLabel(entry)"
                      :value="entry.drive_file_id || ''"
                    >
                      <div class="source-option">
                        <strong>{{ entry.project || '未分类产品' }}</strong>
                        <span>{{ entry.process }} · {{ entry.issue_date || '无日期' }}</span>
                      </div>
                    </el-option>
                  </el-select>
                  <el-alert v-if="sopSourcesError" type="warning" :closable="false" show-icon>
                    {{ sopSourcesError }}
                  </el-alert>
                  <div v-if="selectedSopEntries.length" class="source-selection-list">
                    <div v-for="entry in selectedSopEntries" :key="entry.drive_file_id || entry.row_number">
                      <strong>{{ entry.project || '未分类产品' }}</strong>
                      <span>{{ entry.process }} · {{ entry.issue_date || '无日期' }}</span>
                    </div>
                  </div>
                </article>

                <article class="workflow-source-card is-duro">
                  <header>
                    <div class="section-label">
                      <span>DURO SOURCE</span>
                      <strong>Duro 产品</strong>
                    </div>
                    <el-button
                      text
                      :icon="Refresh"
                      :loading="duroProductsLoading"
                      @click="loadDuroProducts(true)"
                    >手动刷新</el-button>
                  </header>
                  <p>通过当前 Duro 产品 API 加载产品、料号及当前 Revision。</p>
                  <el-select
                    v-model="sourceConfiguration.duro_product_id"
                    filterable
                    clearable
                    placement="bottom-start"
                    :fallback-placements="['top-start', 'bottom-start']"
                    :loading="duroProductsLoading"
                    placeholder="选择 Duro 产品"
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
                        <span>{{ product.name }} · {{ product.revision || '无 Revision' }}</span>
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
                          <strong>选择子项目</strong>
                          <span>已选择 {{ sourceConfiguration.duro_submenu_ids?.length || 0 }} 项</span>
                        </div>
                      </template>
                      <div class="duro-submenu-heading">
                        <span>子项目仅用于限定扫描范围，本身不参与核对；只扫描其下级 BOM 料号。</span>
                      </div>
                      <div v-if="duroSubmenusLoading" class="duro-submenu-state">正在读取缓存的 BOM 子项目…</div>
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
                            <small>{{ submenu.name || '未命名子项目' }}</small>
                          </span>
                        </el-checkbox>
                      </el-checkbox-group>
                      <div v-else class="duro-submenu-state">该产品没有可选择的第一层 BOM 子项目。</div>
                    </el-collapse-item>
                  </el-collapse>
                  <el-alert v-if="duroProductsError" type="warning" :closable="false" show-icon>
                    {{ duroProductsError }}
                  </el-alert>
                  <label class="source-revision-field">
                    <span>目标 Revision</span>
                    <el-input v-model="sourceConfiguration.target_revision" placeholder="选择产品后自动带入，可手动修改" />
                  </label>
                  <div v-if="selectedDuroProduct" class="source-selection-summary">
                    <span>产品：{{ selectedDuroProduct.name || '—' }}</span>
                    <span>料号：{{ selectedDuroProduct.cpn || '—' }}</span>
                    <span>当前 Revision：{{ selectedDuroProduct.revision || '—' }}</span>
                  </div>
                </article>
              </section>

              <section v-if="editForm.kind === 'duro_bom_check'" class="workflow-filter-panel">
                <div class="workflow-filter-item">
                  <div class="section-label">
                    <span>SOP PRODUCT FILTER</span>
                    <div class="ignore-rule-title">
                      <strong>忽略 SOP 相关产品</strong>
                      <button type="button" aria-label="添加忽略 SOP 产品规则" @click="openIgnoreRuleDialog('sop')">
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
                    已配置 {{ sourceConfiguration.ignored_sop_product_keywords?.length || 0 }} 个产品关键字；
                    SOP 物料名称包含关键片段且顺序一致时不计入差异，片段之间允许出现其它文字。
                  </div>
                </div>

                <div class="workflow-filter-item">
                  <div class="section-label">
                    <span>BOM PART FILTER</span>
                    <div class="ignore-rule-title">
                      <strong>忽略 BOM 料号</strong>
                      <button type="button" aria-label="添加忽略 BOM 料号" @click="openIgnoreRuleDialog('part')">
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
                    已配置 {{ sourceConfiguration.ignored_part_numbers?.length || 0 }} 个忽略料号；
                    执行时会同时从 SOP 与 Duro BOM 中排除。
                  </div>
                </div>
              </section>

              <section class="flow-section">
                <div class="section-heading-row">
                  <div class="section-label">
                    <span>BOM CHECK FLOW</span>
                    <strong>核对流程</strong>
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
                        <small>{{ step.description || '暂无步骤说明' }}</small>
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
                    <strong>历史运行</strong>
                    <button
                      class="history-refresh-icon"
                      type="button"
                      aria-label="刷新运行记录"
                      title="刷新运行记录"
                      :disabled="historyLoading"
                      @click="loadRuns(selectedWorkflow.id)"
                    >
                      <el-icon :class="{ 'is-loading': historyLoading }"><Refresh /></el-icon>
                    </button>
                  </div>
                </div>
                <div class="history-filter-panel">
                  <div class="history-stat-grid">
                    <article class="is-success"><span>成功</span><strong>{{ historySuccessCount }}</strong></article>
                    <article class="is-failed"><span>失败</span><strong>{{ historyFailedCount }}</strong></article>
                    <article class="is-warning"><span>告警</span><strong>{{ historyWarningCount }}</strong></article>
                  </div>
                  <el-date-picker
                    v-model="historyDateRange"
                    type="daterange"
                    range-separator="至"
                    start-placeholder="开始日期"
                    end-placeholder="结束日期"
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
                    <span>{{ selectedRunCount ? '删除全部' : '删除记录' }}</span>
                  </button>
                  <button
                    v-if="historySelectionMode"
                    class="history-selection-cancel"
                    type="button"
                    @click="cancelHistorySelection"
                  >取消</button>
                  <span class="next-run-text">下次运行：{{ formatDate(selectedWorkflow.next_run_at) }}</span>
                </div>
              </div>
              <div v-if="historyLoading" class="empty-runs">正在加载运行历史…</div>
              <div v-else-if="!workflowRuns.length" class="empty-runs">还没有运行记录，点击“手动运行”验证触发链路。</div>
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
                            <em v-if="run.finished_at">· 耗时 {{ formatRunDuration(run) }}</em>
                          </small>
                        </el-tooltip>
                      </div>
                      <div class="run-warning-summary" :class="{ 'is-warning': runHasWarnings(run) }">
                        <template v-if="run.report">
                          <strong class="is-total-warning">警告 {{ runWarningCount(run) }}</strong>
                          <span class="is-missing">Duro 缺失 {{ run.report.missing_in_duro_count }}</span>
                          <span class="is-extra">Duro 冗余 {{ run.report.extra_in_duro_count }}</span>
                          <span class="is-quantity">数量差异 {{ run.report.quantity_mismatch_count }}</span>
                          <span class="is-unknown">数量未知 {{ run.report.quantity_unknown_count }}</span>
                        </template>
                        <span v-else>—</span>
                      </div>
                      <span class="run-trigger-type">{{ run.trigger_type === 'manual' ? '手动' : '定时' }}</span>
                      <time>{{ formatDate(run.created_at) }}</time>
                    </div>
                  </template>

                  <div v-if="runDetailLoading[run.id] && !runDetailLoaded[run.id]" class="empty-runs">
                    正在加载运行结果和核对明细…
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
                      <article><span>SOP 源</span><strong>{{ run.report.sop_source_count }}</strong></article>
                      <article><span>全文引用料号</span><strong>{{ run.report.sop_material_count }}</strong></article>
                      <article><span>Duro 料号</span><strong>{{ run.report.duro_material_count }}</strong></article>
                      <article><span>一致</span><strong>{{ run.report.matched_count }}</strong></article>
                      <article class="is-danger"><span>缺失</span><strong>{{ run.report.missing_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>冗余</span><strong>{{ run.report.extra_in_duro_count }}</strong></article>
                      <article class="is-warning"><span>数量差异</span><strong>{{ run.report.quantity_mismatch_count }}</strong></article>
                      <article><span>数量未知</span><strong>{{ run.report.quantity_unknown_count }}</strong></article>
                      <article class="is-ignored"><span>已忽略</span><strong>{{ run.report.total_ignored_count }}</strong></article>
                    </div>
                    <nav class="report-detail-nav" aria-label="核对结果明细导航">
                      <div class="report-detail-nav-pages">
                        <button
                          type="button"
                          :class="{ 'is-active': reportView(run.id) === 'differences' }"
                          @click="setReportView(run.id, 'differences')"
                        >差异明细 <small>共 {{ run.report.total_difference_count }} 项，显示 {{ filteredReportDifferences(run).length }} 项</small></button>
                        <button
                          type="button"
                          :class="{ 'is-active': reportView(run.id) === 'ignored' }"
                          @click="setReportView(run.id, 'ignored')"
                        >已忽略 <small>共 {{ run.report.total_ignored_count }} 项，显示 {{ filteredReportIgnoredItems(run).length }} 项</small></button>
                      </div>
                      <div class="bom-report-filters">
                        <el-input
                          :model-value="reportSearchText(run.id)"
                          class="report-search-input"
                          :prefix-icon="Search"
                          clearable
                          placeholder="搜索料号 / 名称"
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
                          placeholder="全部下级BOM"
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
                              <span>{{ submenu.name || '未命名子菜单' }}</span>
                            </div>
                          </el-option>
                        </el-select>
                        <el-select
                          :model-value="reportFilter(run.id)"
                          class="difference-filter-select"
                          @change="setReportFilter(run.id, $event)"
                        >
                          <el-option label="全部类型" value="all" />
                          <el-option label="不看数量差异" value="structure" />
                          <el-option label="只看 Duro 缺失" value="missing_in_duro" />
                          <el-option label="只看 Duro 冗余" value="extra_in_duro" />
                          <el-option label="只看数量差异" value="quantity_mismatch" />
                          <el-option label="只看数量未知" value="quantity_unknown" />
                        </el-select>
                      </div>
                    </nav>
                    <template v-if="reportView(run.id) === 'differences'">
                    <el-table
                      :ref="setDifferenceTableRef.bind(null, run.id)"
                      :data="filteredReportDifferences(run)"
                      :row-class-name="differenceRowClassName"
                      row-key="part_number"
                      max-height="520"
                      border
                      empty-text="SOP BOM 与 Duro BOM 一致"
                      @row-click="handleDifferenceRowClick(run.id, $event)"
                    >
                      <el-table-column width="48" align="center">
                        <template #default="{ row }">
                          <el-dropdown
                            trigger="click"
                            :disabled="isDifferenceIgnoreUpdating(run.workflow_id, row.part_number)"
                            @command="handleDifferenceRowMenuCommand(run, row, $event)"
                            @click.stop
                          >
                            <button
                              class="difference-row-menu-button"
                              type="button"
                              aria-label="差异操作"
                              title="差异操作"
                              :disabled="isDifferenceIgnoreUpdating(run.workflow_id, row.part_number)"
                              @click.stop
                            >
                              <el-icon><MoreFilled /></el-icon>
                            </button>
                            <template #dropdown>
                              <el-dropdown-menu>
                                <el-dropdown-item command="ignore" :disabled="row.is_ignored">
                                  忽略料号
                                </el-dropdown-item>
                                <el-dropdown-item v-if="row.is_ignored" command="unignore">
                                  取消忽略
                                </el-dropdown-item>
                                <el-dropdown-item command="expand" divided>
                                  展开
                                </el-dropdown-item>
                              </el-dropdown-menu>
                            </template>
                          </el-dropdown>
                        </template>
                      </el-table-column>
                      <el-table-column
                        type="expand"
                        width="1"
                        class-name="difference-native-expand-column"
                        label-class-name="difference-native-expand-column"
                      >
                        <template #default="{ row }">
                          <div class="semantic-audit-panel">
                            <div class="semantic-audit-summary">
                              <strong>差异汇总说明</strong>
                              <p>{{ differenceSummary(row) }}</p>
                            </div>
                            <div v-if="row.sop_quantity_explanations?.length" class="semantic-audit-summary is-semantic-detail">
                              <strong>语义数量说明</strong>
                              <p v-for="explanation in row.sop_quantity_explanations" :key="explanation">{{ explanation }}</p>
                            </div>
                            <div v-if="row.sop_quantity_decisions?.length" class="semantic-decision-list">
                              <article
                                v-for="(decision, decisionIndex) in row.sop_quantity_decisions"
                                :key="`${decision.source}-${decision.event_id}-${decisionIndex}`"
                                class="semantic-decision-item"
                              >
                                <span class="semantic-decision-badge" :class="decision.accumulate ? 'is-added' : 'is-skipped'">
                                  {{ decision.accumulate ? `累加 ${formatReportQuantity(decision.quantity_delta)}` : '不累加' }}
                                </span>
                                <div>
                                  <strong>{{ decision.action || '语义判断' }}</strong>
                                  <small>
                                    {{ decision.source }}
                                    <template v-if="decision.page_numbers?.length"> · 第 {{ decision.page_numbers.join('、') }} 页</template>
                                    <template v-if="decision.target"> · 目标：{{ decision.target }}</template>
                                    <template v-if="decision.location"> · 位置：{{ decision.location }}</template>
                                  </small>
                                  <p>{{ decision.reason || '—' }}</p>
                                  <blockquote v-if="decision.evidence">{{ decision.evidence }}</blockquote>
                                </div>
                              </article>
                            </div>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column label="差异类型" width="125">
                        <template #default="{ row }">
                          <div class="difference-status-stack">
                            <span class="difference-status" :class="`is-${row.status}`">
                              {{ differenceLabel(row.status) }}
                            </span>
                            <span v-if="row.is_ignored" class="difference-ignored-tag">已忽略</span>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column prop="part_number" label="料号" width="130" />
                      <el-table-column prop="name" label="物料名称" min-width="260" show-overflow-tooltip />
                      <el-table-column label="Duro 子菜单" min-width="150" show-overflow-tooltip>
                        <template #default="{ row }">{{ row.duro_submenu_labels.join('、') || '—' }}</template>
                      </el-table-column>
                      <el-table-column label="SOP 数量" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.sop_quantity) }}</template>
                      </el-table-column>
                      <el-table-column label="Duro 数量" width="100" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.duro_quantity) }}</template>
                      </el-table-column>
                      <el-table-column label="差值" width="90" align="right">
                        <template #default="{ row }">{{ formatReportQuantity(row.quantity_delta) }}</template>
                      </el-table-column>
                      <el-table-column label="SOP 位置" min-width="260" show-overflow-tooltip>
                        <template #default="{ row }">{{ row.sop_locations.join('；') || '—' }}</template>
                      </el-table-column>
                      <el-table-column label="Duro 路径" min-width="300" show-overflow-tooltip>
                        <template #default="{ row }">{{ row.duro_paths.join('；') || '—' }}</template>
                      </el-table-column>
                    </el-table>
                    </template>
                    <template v-else>
                        <el-table :data="filteredReportIgnoredItems(run)" border max-height="520" empty-text="没有符合筛选条件的已忽略数据">
                          <el-table-column type="expand" width="48">
                            <template #default="{ row }">
                              <div class="semantic-audit-panel">
                                <div v-if="row.sop_quantity_explanations?.length" class="semantic-audit-summary">
                                  <strong>数量汇总说明</strong>
                                  <p v-for="explanation in row.sop_quantity_explanations" :key="explanation">{{ explanation }}</p>
                                </div>
                                <article
                                  v-for="(decision, decisionIndex) in row.sop_quantity_decisions || []"
                                  :key="`${decision.source}-${decision.event_id}-${decisionIndex}`"
                                  class="semantic-decision-item"
                                >
                                  <span class="semantic-decision-badge" :class="decision.accumulate ? 'is-added' : 'is-skipped'">
                                    {{ decision.accumulate ? `累加 ${formatReportQuantity(decision.quantity_delta)}` : '不累加' }}
                                  </span>
                                  <div>
                                    <strong>{{ decision.action || '语义判断' }}</strong>
                                    <small>{{ decision.source }}<template v-if="decision.page_numbers?.length"> · 第 {{ decision.page_numbers.join('、') }} 页</template></small>
                                    <p>{{ decision.reason || '—' }}</p>
                                    <blockquote v-if="decision.evidence">{{ decision.evidence }}</blockquote>
                                  </div>
                                </article>
                              </div>
                            </template>
                          </el-table-column>
                          <el-table-column label="原差异" width="120">
                            <template #default="{ row }">
                              <span v-if="row.ignore_type === 'part_number_cleanup'" class="difference-status is-cleanup">物料清洗</span>
                              <span v-else class="difference-status" :class="`is-${row.status}`">{{ differenceLabel(row.status) }}</span>
                            </template>
                          </el-table-column>
                          <el-table-column prop="part_number" label="原料号" width="140" />
                          <el-table-column prop="name" label="物料名称" min-width="180" show-overflow-tooltip />
                          <el-table-column label="Duro 子菜单" min-width="150" show-overflow-tooltip>
                            <template #default="{ row }">{{ row.duro_submenu_labels.join('、') || '—' }}</template>
                          </el-table-column>
                          <el-table-column label="忽略类型" width="130">
                            <template #default="{ row }">
                              {{ row.ignore_type === 'part_number_cleanup' ? '默认料号清洗' : row.ignore_type === 'part_number' ? '忽略料号' : 'SOP 产品关键字' }}
                            </template>
                          </el-table-column>
                          <el-table-column prop="ignore_value" label="命中规则" width="140" show-overflow-tooltip />
                          <el-table-column prop="ignore_reason" label="忽略原因" min-width="220" show-overflow-tooltip />
                          <el-table-column label="开始忽略" width="170">
                            <template #default="{ row }">
                              {{ row.ignored_at ? formatDate(row.ignored_at) : '历史配置' }}
                            </template>
                          </el-table-column>
                        </el-table>
                    </template>
                  </div>
                  <el-alert
                    v-else-if="runDetailLoaded[run.id] && (run.status === 'running' || run.status === 'queued')"
                    title="正在读取并核对 BOM，请稍后刷新运行记录"
                    type="info"
                    :closable="false"
                    show-icon
                  />
                  <div v-else-if="runDetailLoaded[run.id]" class="run-log-list">
                    <span v-for="(log, index) in run.logs" :key="index">{{ log }}</span>
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

      <footer class="workflow-board-footer" aria-label="工作流数量看板">
        <span>工作流 <strong>{{ workflows.length }}</strong></span>
        <span>已启用 <strong>{{ activeWorkflowCount }}</strong></span>
        <span>定时任务 <strong>{{ scheduledWorkflowCount }}</strong></span>
        <span>Duro BOM <strong>{{ duroWorkflowCount }}</strong></span>
      </footer>
    </main>
    <SopOverviewPanel v-else-if="activeModule === 'sop'" />
    <DuroProductsPanel v-else />

    <el-dialog v-model="createDialogVisible" title="新建工作流" width="520px">
      <div class="dialog-form">
        <label>
          <span>工作流名称</span>
          <el-input v-model="createForm.name" placeholder="输入工作流名称" />
        </label>
        <label>
          <span>模板</span>
          <el-radio-group v-model="createForm.template">
            <el-radio-button value="duro">Duro BOM 核对</el-radio-button>
            <el-radio-button value="blank">空白工作流</el-radio-button>
          </el-radio-group>
        </label>
        <label>
          <span>描述</span>
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </label>
      </div>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createWorkflow">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="ignoreRuleDialogVisible"
      :title="ignoreRuleDialogType === 'sop' ? '添加忽略 SOP 产品规则' : '添加忽略 BOM 料号'"
      width="480px"
    >
      <div class="ignore-rule-dialog-form">
        <label>
          <span>{{ ignoreRuleDialogType === 'sop' ? '产品关键字' : 'BOM 料号' }}</span>
          <el-input
            v-if="ignoreRuleDialogType === 'sop'"
            v-model="pendingSopKeyword"
            placeholder="例如 200μl"
            @keyup.enter="addIgnoredSopKeyword"
          />
          <el-input
            v-else
            v-model="pendingPartNumber"
            placeholder="例如 100-00001"
            @keyup.enter="addIgnoredPartNumber"
          />
        </label>
        <label>
          <span>忽略原因</span>
          <el-input
            v-if="ignoreRuleDialogType === 'sop'"
            v-model="pendingSopKeywordReason"
            type="textarea"
            :rows="3"
            placeholder="必填，请说明忽略原因"
          />
          <el-input
            v-else
            v-model="pendingPartNumberReason"
            type="textarea"
            :rows="3"
            placeholder="必填，请说明忽略原因"
          />
        </label>
      </div>
      <template #footer>
        <el-button @click="ignoreRuleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmIgnoreRule">添加</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type TableInstance } from 'element-plus'
import {
  Box,
  Check,
  Close,
  Connection,
  DataAnalysis,
  Delete,
  DocumentChecked,
  Files,
  FolderOpened,
  Loading,
  MoreFilled,
  Plus,
  Refresh,
  Search,
  VideoPlay
} from '@element-plus/icons-vue'
import DuroProductsPanel from '@/views/DuroProductsPanel.vue'
import SopOverviewPanel from '@/views/SopOverviewPanel.vue'
import { duroApi, type DuroBomNode, type DuroProduct } from '@/api/duro'
import { sopApi, type SopCatalogEntry } from '@/api/sop'
import {
  workflowApi,
  type WorkflowBomDifference,
  type WorkflowBomDifferenceStatus,
  type Workflow,
  type WorkflowKind,
  type WorkflowPayload,
  type WorkflowRun,
  type WorkflowRunStatus,
  type WorkflowStatus,
  type WorkflowStep,
  type WorkflowStepKind
} from '@/api/workflows'


const loading = ref(false)
const activeModule = ref<'workflows' | 'sop' | 'duro'>('workflows')
const saving = ref(false)
const creating = ref(false)
const triggering = ref(false)
const editorVisible = ref(false)
const workflowListVisible = ref(true)
const runningWorkflowIds = ref<Set<string>>(new Set())
const pollingRunIds = ref<Set<string>>(new Set())
const copyingWorkflowIds = ref<Set<string>>(new Set())
const workflows = ref<Workflow[]>([])
const workflowRuns = ref<WorkflowRun[]>([])
const activeRunIds = ref<string[]>([])
const runDetailLoaded = reactive<Record<string, boolean>>({})
const runDetailLoading = reactive<Record<string, boolean>>({})
const runDetailErrors = reactive<Record<string, string>>({})
const runDetailReloadPending = reactive<Record<string, boolean>>({})
const differenceIgnoreUpdating = reactive<Record<string, boolean>>({})
const differenceTableRefs = new Map<string, TableInstance>()
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
}

const createForm = reactive({
  name: 'Duro BOM 核对',
  template: 'duro' as 'duro' | 'blank',
  description: '核对 Duro 产品 BOM 的结构、料号、数量和版本差异。'
})

const statusText: Record<WorkflowStatus, string> = {
  draft: '草稿',
  active: '启动',
  paused: '暂停'
}

const kindText: Record<WorkflowKind, string> = {
  duro_bom_check: 'Duro BOM',
  custom: '自定义'
}

const stepKindText: Record<WorkflowStepKind, string> = {
  duro_bom_fetch: 'DURO SOURCE',
  bom_compare: 'BOM CHECK',
  report: 'REPORT',
  custom: 'CUSTOM STEP'
}

const runStatusText: Record<WorkflowRunStatus, string> = {
  queued: '等待执行',
  running: '执行中',
  succeeded: '执行成功',
  failed: '执行失败',
  skipped: '等待配置'
}

const differenceStatusText: Record<WorkflowBomDifferenceStatus, string> = {
  missing_in_duro: 'Duro 缺失',
  extra_in_duro: 'Duro 冗余',
  quantity_mismatch: '数量差异',
  quantity_unknown: '数量未知'
}

const selectedWorkflow = computed(() =>
  workflows.value.find((workflow) => workflow.id === selectedWorkflowId.value) ?? null
)
const selectedRunCount = computed(() => selectedRunIds.value.size)

const activeWorkflowCount = computed(() => workflows.value.filter((item) => item.status === 'active').length)
const scheduledWorkflowCount = computed(() => workflows.value.filter((item) => item.schedule.enabled).length)
const duroWorkflowCount = computed(() => workflows.value.filter((item) => item.kind === 'duro_bom_check').length)
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
  [...new Set(allSopOptions.value.map((entry) => entry.project || '未分类产品'))].sort((a, b) => a.localeCompare(b))
)
const sopProcessOptions = computed(() =>
  [...new Set(
    allSopOptions.value
      .filter((entry) => !sopProjectFilter.value || (entry.project || '未分类产品') === sopProjectFilter.value)
      .map((entry) => entry.process || '未命名工序')
  )].sort((a, b) => a.localeCompare(b))
)
const filteredSopOptions = computed(() =>
  allSopOptions.value.filter((entry) =>
    (!sopProjectFilter.value || (entry.project || '未分类产品') === sopProjectFilter.value)
    && (!sopProcessFilter.value || (entry.process || '未命名工序') === sopProcessFilter.value)
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
  if (dataSourcesChecking.value) return '正在检测数据源'
  return dataSourcesConnected.value ? '数据源已接入' : '数据源接入失败'
})
const dataSourceStatusDetail = computed(() => {
  if (dataSourcesChecking.value) return '正在检查 SOP / Duro API'
  if (dataSourcesConnected.value) return 'SOP / Duro API'
  if (sopSourcesError.value && duroProductsError.value) return 'SOP、Duro API 获取失败'
  if (sopSourcesError.value) return 'SOP 获取失败'
  return 'Duro API 获取失败'
})
const dataSourceErrorDetail = computed(() =>
  [
    sopSourcesError.value ? `SOP：${sopSourcesError.value}` : '',
    duroProductsError.value ? `Duro API：${duroProductsError.value}` : ''
  ].filter(Boolean).join('\n')
)

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

function normalizeWorkflowConfiguration(configuration: Record<string, unknown>): WorkflowSourceConfiguration {
  const legacyFileId = typeof configuration.sop_drive_file_id === 'string'
    ? configuration.sop_drive_file_id.trim()
    : ''
  const configuredFileIds = Array.isArray(configuration.sop_drive_file_ids)
    ? configuration.sop_drive_file_ids.map(String).filter(Boolean)
    : []
  const fileIds = configuredFileIds.length ? configuredFileIds : (legacyFileId ? [legacyFileId] : [])
  const configuredSources = Array.isArray(configuration.sop_sources)
    ? configuration.sop_sources.filter((item): item is WorkflowSopSource => Boolean(item && typeof item === 'object'))
    : []
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
    duro_submenu_ids: submenuIds,
    duro_submenus: submenus,
    ignored_sop_product_keywords: ignoredSopProductKeywords,
    ignored_part_numbers: ignoredPartNumbers,
    ignored_sop_product_keyword_reasons: Object.fromEntries(
      ignoredSopProductKeywords.map((keyword) => [keyword, String(keywordReasons[keyword] || '历史配置未填写原因')])
    ),
    ignored_part_number_reasons: Object.fromEntries(
      ignoredPartNumbers.map((partNumber) => [partNumber, String(partReasons[partNumber] || '历史配置未填写原因')])
    ),
    ignore_quantity_mismatch_warning: Boolean(configuration.ignore_quantity_mismatch_warning)
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
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流加载失败，请确认后端已启动')
  } finally {
    loading.value = false
  }
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
  void loadRuns(workflowId)
}

function openWorkflowEditor(workflowId: string) {
  selectWorkflow(workflowId)
  builderTab.value = 'editor'
  editorVisible.value = true
  workflowListVisible.value = false
}

function openWorkflowHistory(workflowId: string) {
  selectWorkflow(workflowId)
  builderTab.value = 'history'
  editorVisible.value = true
  workflowListVisible.value = false
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
    sopSourcesError.value = error?.response?.data?.detail || error?.message || 'SOP 数据源加载失败'
  } finally {
    sopSourcesLoading.value = false
    sopSourceChecked.value = true
  }
}

async function loadDuroProducts(refresh = false) {
  duroProductsLoading.value = true
  duroProductsError.value = ''
  try {
    const response = await duroApi.products(refresh)
    duroProducts.value = response.data.products
  } catch (error: any) {
    console.error(error)
    duroProductsError.value = error?.response?.data?.detail || error?.message || 'Duro 产品加载失败'
  } finally {
    duroProductsLoading.value = false
    duroSourceChecked.value = true
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
    duroSubmenusError.value = error?.response?.data?.detail || error?.message || 'Duro BOM 子菜单加载失败'
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
  if (!partNumber) return ElMessage.warning('请输入 BOM 料号')
  if (!reason) return ElMessage.warning('添加忽略料号前必须填写原因')
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
  if (!keyword) return ElMessage.warning('请输入 SOP 产品关键字')
  if (!reason) return ElMessage.warning('添加产品关键字前必须填写原因')
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
  return `${entry.project || '未分类产品'} · ${entry.process}${entry.issue_date ? ` · ${entry.issue_date}` : ''}`
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
      `确认删除选中的 ${selectedRunCount.value} 条运行记录？删除后无法恢复。`,
      '批量删除运行记录',
      {
        confirmButtonText: '删除全部',
        cancelButtonText: '取消',
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
    ElMessage.success(`已删除 ${deletedCount} 条运行记录`)
  } catch (error) {
    console.error(error)
    ElMessage.error('运行记录删除失败')
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
    runDetailErrors[runId] = error?.response?.data?.detail || error?.message || '运行明细加载失败'
  } finally {
    runDetailLoading[runId] = false
    if (runDetailReloadPending[runId]) {
      runDetailReloadPending[runId] = false
      void loadRunDetail(runId, true)
    }
  }
}

async function saveSelectedWorkflow() {
  if (!selectedWorkflowId.value || !editForm.value) return
  if (!editForm.value.name.trim()) {
    ElMessage.warning('请输入工作流名称')
    return
  }
  saving.value = true
  try {
    const response = await workflowApi.update(selectedWorkflowId.value, editForm.value)
    const index = workflows.value.findIndex((item) => item.id === response.data.id)
    if (index >= 0) workflows.value[index] = response.data
    editForm.value = cloneWorkflowPayload(response.data)
    ElMessage.success('工作流已保存')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流保存失败')
  } finally {
    saving.value = false
  }
}

async function createWorkflow() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入工作流名称')
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
    ElMessage.success('工作流已创建')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流创建失败')
  } finally {
    creating.value = false
  }
}

async function copyWorkflow(workflow: Workflow) {
  if (isWorkflowCopying(workflow.id)) return
  copyingWorkflowIds.value = new Set(copyingWorkflowIds.value).add(workflow.id)
  try {
    const payload = cloneWorkflowPayload(workflow)
    payload.name = `${workflow.name}-副本`
    await workflowApi.create(payload)
    await loadWorkflows()
    ElMessage.success(`已复制“${workflow.name}”`)
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流复制失败')
  } finally {
    const next = new Set(copyingWorkflowIds.value)
    next.delete(workflow.id)
    copyingWorkflowIds.value = next
  }
}

async function deleteWorkflow(workflow: Workflow) {
  try {
    await ElMessageBox.confirm(`确认删除“${workflow.name}”？`, '删除工作流', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await workflowApi.remove(workflow.id)
    workflows.value = workflows.value.filter((item) => item.id !== workflow.id)
    if (selectedWorkflowId.value === workflow.id) {
      selectedWorkflowId.value = null
      editForm.value = null
      workflowRuns.value = []
      editorVisible.value = false
      workflowListVisible.value = true
    }
    ElMessage.success('工作流已删除')
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流删除失败')
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
    ElMessage.success('工作流已触发')
    if (editorVisible.value && selectedWorkflowId.value === workflow.id) builderTab.value = 'history'
    startPollingWorkflowRun(workflow.id, response.data.id)
    await loadWorkflows()
  } catch (error) {
    console.error(error)
    ElMessage.error('工作流触发失败')
    setWorkflowRunning(workflow.id, false)
  } finally {
    triggering.value = false
  }
}

function startPollingWorkflowRun(workflowId: string, runId: string) {
  if (pollingRunIds.value.has(runId)) return
  pollingRunIds.value = new Set(pollingRunIds.value).add(runId)
  void pollWorkflowRun(workflowId, runId)
}

function stopPollingWorkflowRun(runId: string) {
  const next = new Set(pollingRunIds.value)
  next.delete(runId)
  pollingRunIds.value = next
}

async function pollWorkflowRun(workflowId: string, runId: string, attempt = 0) {
  try {
    const response = await workflowApi.runDetail(runId, 0, 1)
    const run = response.data.run
    if (!run || !['queued', 'running'].includes(run.status) || attempt >= 1800) {
      stopPollingWorkflowRun(runId)
      setWorkflowRunning(workflowId, false)
      if (selectedWorkflowId.value === workflowId) await loadRuns(workflowId)
      return
    }
  } catch (error) {
    console.error(error)
    if (attempt >= 1800) {
      stopPollingWorkflowRun(runId)
      setWorkflowRunning(workflowId, false)
      return
    }
  }
  window.setTimeout(() => void pollWorkflowRun(workflowId, runId, attempt + 1), 1000)
}

function duroTemplateSteps(): WorkflowStep[] {
  return [
    createStep('核对 Duro BOM', 'bom_compare', '汇总所选 SOP 的全文料号引用，并与 Duro BOM 核对料号和出现次数。'),
    createStep('核对报告', 'report', '输出缺失料号、冗余料号、数量差异和无法比较项。')
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
  return workflow.schedule.enabled ? `每 ${workflow.schedule.interval_minutes} 分钟` : '仅手动'
}

function formatDate(value: string | null) {
  if (!value) return '未安排'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatLastRunDate(value: string | null) {
  if (!value) return '从未运行'
  return new Date(value).toLocaleString('zh-CN', {
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
  if (milliseconds < 1000) return `${milliseconds} 毫秒`
  const totalSeconds = Math.round(milliseconds / 1000)
  if (totalSeconds < 60) return `${totalSeconds} 秒`
  const totalMinutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (totalMinutes < 60) return `${totalMinutes} 分 ${seconds} 秒`
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours} 小时 ${minutes} 分`
}

function formatReportQuantity(value: number | null) {
  if (value === null || value === undefined) return '—'
  return Number.isInteger(value) ? value.toString() : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
}

function differenceLabel(status: string) {
  return differenceStatusText[status as WorkflowBomDifferenceStatus] || status
}

function differenceSummary(row: WorkflowBomDifference) {
  const material = row.name ? `${row.part_number}（${row.name}）` : row.part_number
  if (row.status === 'missing_in_duro') {
    const locations = row.sop_locations.join('；') || '未记录 SOP 位置'
    return `${material} 在 SOP 正文中出现，统计数量为 ${formatReportQuantity(row.sop_quantity)}，但在当前 Duro BOM 扫描范围内未找到。SOP 位置：${locations}。`
  }
  if (row.status === 'extra_in_duro') {
    const paths = row.duro_paths.join('；') || '未记录 Duro 路径'
    return `${material} 存在于当前 Duro BOM，数量为 ${formatReportQuantity(row.duro_quantity)}，但在所选 SOP 正文中未识别到。Duro 路径：${paths}。`
  }
  if (row.status === 'quantity_mismatch') {
    return `${material} 在 SOP 中统计为 ${formatReportQuantity(row.sop_quantity)}，Duro BOM 中为 ${formatReportQuantity(row.duro_quantity)}，差值为 ${formatReportQuantity(row.quantity_delta)}（Duro - SOP）。`
  }
  return `${material} 已在 SOP 和 Duro BOM 中匹配，但 SOP 数量无法可靠确定；Duro 数量为 ${formatReportQuantity(row.duro_quantity)}。`
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
  differenceTableRefs.get(runId)?.toggleRowExpansion(row)
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
      `料号：${row.part_number}${row.name ? ` · ${row.name}` : ''}`,
      '忽略该差异',
      {
        confirmButtonText: '确认忽略',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '必填，请填写忽略原因',
        inputValidator: (value) => value.trim().length > 0 || '请填写忽略原因'
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
    await loadRunDetail(run.id, true)
    ElMessage.success(`已忽略料号 ${row.part_number}`)
  } catch (error: any) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || '忽略料号失败')
  } finally {
    differenceIgnoreUpdating[key] = false
  }
}

async function unignoreWorkflowDifference(run: WorkflowRun, row: WorkflowBomDifference) {
  try {
    await ElMessageBox.confirm(
      `确认取消忽略料号 ${row.part_number}？后续运行将重新统计该差异。`,
      '取消忽略',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '返回',
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
    await loadRunDetail(run.id, true)
    ElMessage.success(`已取消忽略料号 ${row.part_number}`)
  } catch (error: any) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || '取消忽略失败')
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
  if (run.status === 'succeeded' && run.report) return `核对完成：${runWarningCount(run)} 项警告`
  const message = run.message.trim()
  if (message) return run.status === 'failed' ? `失败原因：${message}` : message
  if (run.status === 'failed') {
    const lastLog = run.logs[run.logs.length - 1]?.replace(/^运行失败[：:]\s*/, '').trim()
    return `失败原因：${lastLog || '未提供失败原因'}`
  }
  return '工作流正在运行'
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
  void loadWorkflows()
  void loadSopSources()
  void loadDuroProducts()
})
</script>
