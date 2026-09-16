<template>
  <main class="test-versions-page">
    <header class="test-versions-header">
      <div class="test-versions-brand">
        <a href="/" aria-label="Productions"><span class="test-versions-mark">V</span></a>
        <div>
          <span class="test-versions-kicker">PRODUCTIONS</span>
          <h1>{{ t('versions.testVersions.title') }}</h1>
        </div>
      </div>
      <div class="test-versions-actions">
        <a class="test-versions-home" href="/">{{ t('versions.testVersions.backHome') }}</a>
        <el-button :icon="Refresh" :loading="activeTab === 'duro' ? duroLoading : testLoading" @click="refreshActive">
          {{ t('common.actions.refresh') }}
        </el-button>
        <AuthUserMenu variant="dark" />
      </div>
    </header>

    <section class="test-versions-content">
      <div class="test-versions-intro">
        <div>
          <p class="eyebrow">{{ t('versions.testVersions.eyebrow') }}</p>
          <h2>{{ t('versions.testVersions.heading') }}</h2>
          <p>{{ t('versions.testVersions.subtitle') }}</p>
        </div>
        <div class="test-versions-source" :class="{ 'is-ready': activeTab === 'duro' ? Boolean(duroCatalog) : Boolean(testRecords.length) }">
          <span class="source-dot"></span>
          {{ activeTab === 'duro' ? t('versions.testVersions.duroSource') : t('versions.testVersions.testSource') }}
        </div>
      </div>

      <nav class="test-versions-tabs" role="tablist" :aria-label="t('versions.testVersions.tabNavigation')">
        <button
          class="test-versions-tab"
          :class="{ 'is-active': activeTab === 'duro' }"
          type="button"
          role="tab"
          :aria-selected="activeTab === 'duro'"
          @click="selectTab('duro')"
        >
          <Connection :size="18" aria-hidden="true" />
          <span>Duro Version</span>
          <strong v-if="duroCatalog">{{ duroCatalog.child_component_count }}</strong>
        </button>
        <button
          class="test-versions-tab"
          :class="{ 'is-active': activeTab === 'test' }"
          type="button"
          role="tab"
          :aria-selected="activeTab === 'test'"
          @click="selectTab('test')"
        >
          <Tickets :size="18" aria-hidden="true" />
          <span>Test Version</span>
          <strong v-if="testRecords.length">{{ testRecords.length }}</strong>
        </button>
      </nav>

      <section v-if="activeTab === 'duro'" class="test-versions-panel" role="tabpanel">
        <div v-if="duroCatalog" class="test-versions-summary">
          <div><span>{{ t('versions.testVersions.productsScanned') }}</span><strong>{{ duroCatalog.products_scanned }}</strong></div>
          <div><span>{{ t('versions.testVersions.matchedProducts') }}</span><strong>{{ duroCatalog.matched_products }}</strong></div>
          <div><span>{{ t('versions.testVersions.parentMenus') }}</span><strong>{{ duroCatalog.parent_menu_count }}</strong></div>
          <div><span>{{ t('versions.testVersions.childComponents') }}</span><strong>{{ duroCatalog.child_component_count }}</strong></div>
        </div>

        <div class="test-versions-toolbar">
          <div>
            <p class="panel-kicker">DURO CATALOG</p>
            <h3>{{ t('versions.testVersions.duroTitle') }}</h3>
          </div>
          <el-input v-model="duroSearch" :prefix-icon="Search" clearable :placeholder="t('versions.testVersions.searchPlaceholder')" />
        </div>

        <div v-if="duroLoading && !duroCatalog" class="test-versions-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ t('versions.testVersions.loadingDuro') }}</span>
        </div>
        <el-result v-else-if="duroError && !duroCatalog" icon="warning" :title="t('versions.testVersions.loadFailed')" :sub-title="duroError">
          <template #extra><el-button type="primary" @click="loadDuro(true)">{{ t('common.actions.retry') }}</el-button></template>
        </el-result>
        <div v-else-if="!filteredGroups.length" class="test-versions-state is-empty">
          <Connection :size="34" aria-hidden="true" />
          <strong>{{ duroCatalog ? t('versions.testVersions.noMatches') : t('versions.testVersions.noDuroData') }}</strong>
          <span v-if="duroCatalog">{{ t('versions.testVersions.noMatchesHint') }}</span>
        </div>
        <div v-else class="test-version-table-shell">
          <div class="test-version-tree-head-shell">
            <div class="test-version-tree-head">
              <span>{{ t('versions.testVersions.treeComponent') }}</span>
              <span>{{ t('versions.testVersions.treeKind') }}</span>
              <span>{{ t('versions.testVersions.appVersion') }}</span>
              <span>{{ t('versions.testVersions.firmwareVersion') }}</span>
              <span>{{ t('versions.testVersions.commitHash') }}</span>
              <span>{{ t('versions.testVersions.commitHashId') }}</span>
              <span>{{ t('versions.testVersions.revision') }}</span>
              <span>{{ t('versions.testVersions.description') }}</span>
            </div>
          </div>
          <div class="test-version-tree-shell">
            <el-tree
              class="test-version-tree"
              :data="versionTreeData"
              node-key="key"
              :props="treeProps"
              :default-expanded-keys="defaultExpandedTreeKeys"
              :default-expand-all="false"
              :expand-on-click-node="false"
              :empty-text="t('versions.testVersions.noMatches')"
            >
              <template #default="{ data }">
                <div class="test-version-tree-node" :class="`is-${data.nodeType}`">
                  <div class="tree-node-main">
                    <span class="tree-node-icon">
                      <Box v-if="data.nodeType === 'product'" :size="15" aria-hidden="true" />
                      <FolderOpened v-else-if="data.nodeType === 'parent'" :size="15" aria-hidden="true" />
                      <Box v-else :size="14" aria-hidden="true" />
                    </span>
                    <div>
                      <strong :title="data.cpn || data.id">{{ data.cpn || data.id }}</strong>
                      <span :title="data.name || t('versions.testVersions.unnamedComponent')">{{ data.name || t('versions.testVersions.unnamedComponent') }}</span>
                    </div>
                  </div>
                  <span class="tree-node-kind" :title="data.category || data.nodeTypeLabel || '—'">{{ data.category || data.nodeTypeLabel || '—' }}</span>
                  <span :title="data.app_version || '—'" :class="{ 'version-value': data.app_version }">{{ data.app_version || '—' }}</span>
                  <span :title="data.firmware_version || '—'" :class="{ 'version-value': data.firmware_version }">{{ data.firmware_version || '—' }}</span>
                  <div class="tree-node-commit">
                    <code v-if="data.test_commit_hash" :title="data.test_commit_hash">{{ data.test_commit_hash }}</code>
                    <span v-else title="—">—</span>
                    <small v-if="data.test_tag" :title="data.test_tag">{{ data.test_tag }}</small>
                  </div>
                  <div class="tree-node-commit">
                    <a
                      v-if="data.test_commit_id"
                      class="commit-id-link"
                      :href="`https://github.com/Opentrons/opentrons/commit/${data.test_commit_id}`"
                      target="_blank"
                      rel="noopener noreferrer"
                      :title="data.test_commit_id"
                    >{{ shortCommitId(data.test_commit_id) }}</a>
                    <span v-else title="—">—</span>
                  </div>
                  <span :title="data.revision || '—'">{{ data.revision || '—' }}</span>
                  <span class="description-cell" :title="data.description || data.source_text">{{ descriptionPreview(data.description || data.source_text) }}</span>
                </div>
              </template>
            </el-tree>
          </div>
        </div>
        <el-alert v-if="duroError && duroCatalog" class="test-versions-inline-error" type="warning" :closable="false">{{ duroError }}</el-alert>
        <footer v-if="duroCatalog" class="test-versions-footer">
          <span>{{ t('versions.testVersions.updatedAt', { time: formatDate(duroCatalog.fetched_at) }) }}</span>
          <span>{{ duroCatalog.cached ? t('versions.common.sqliteCache') : t('versions.testVersions.duroSource') }}</span>
        </footer>
      </section>

      <section v-else class="test-versions-panel" role="tabpanel">
        <div class="test-versions-toolbar">
          <div>
            <p class="panel-kicker">TEST CAPTURE</p>
            <h3>{{ t('versions.testVersions.testTitle') }}</h3>
          </div>
          <div class="test-versions-toolbar-actions">
            <el-input v-model="testSearch" :prefix-icon="Search" clearable :placeholder="t('versions.testVersions.testSearchPlaceholder')" />
            <el-button type="primary" :icon="Plus" @click="openAddVersionDialog">
              {{ t('versions.testVersions.addVersion') }}
            </el-button>
          </div>
        </div>
        <div v-if="testLoading && !testRecords.length" class="test-versions-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ t('versions.testVersions.loadingTest') }}</span>
        </div>
        <el-result v-else-if="testError && !testRecords.length" icon="warning" :title="t('versions.testVersions.loadFailed')" :sub-title="testError">
          <template #extra><el-button type="primary" @click="loadTestVersions(true)">{{ t('common.actions.retry') }}</el-button></template>
        </el-result>
        <div v-else-if="!filteredBarcodeRows.length" class="test-versions-state is-empty">
          <Tickets :size="34" aria-hidden="true" />
          <strong>{{ t('versions.testVersions.noTestData') }}</strong>
          <span>{{ t('versions.testVersions.noTestDataHint') }}</span>
          <el-button type="primary" :icon="Plus" @click="openAddVersionDialog">
            {{ t('versions.testVersions.addVersion') }}
          </el-button>
        </div>
        <div v-else class="test-version-table-wrap test-history-table-wrap">
          <table class="test-version-table test-barcode-table">
            <thead>
              <tr>
                <th>{{ t('versions.testVersions.product') }}</th>
                <th>{{ t('versions.testVersions.barcode') }}</th>
                <th>{{ t('versions.testVersions.testField') }}</th>
                <th>{{ t('versions.testVersions.serial') }}</th>
                <th>{{ t('versions.testVersions.testVersion') }}</th>
                <th>{{ t('versions.testVersions.appVersion') }}</th>
                <th>{{ t('versions.testVersions.firmware') }}</th>
                <th>{{ t('versions.testVersions.queriedAt') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in filteredBarcodeRows" :key="row.id">
                <td>
                  <strong>{{ row.product_name }}</strong>
                  <span>{{ row.product_type }}</span>
                </td>
                <td><code>{{ row.barcode }}</code></td>
                <td>
                  <el-select
                    :model-value="selectedTestKeyByBarcode[row.barcode] || row.defaultTestKey"
                    size="small"
                    class="test-field-select"
                    @change="(value: string) => setSelectedTestKey(row.barcode, value)"
                  >
                    <el-option
                      v-for="option in row.testOptions"
                      :key="option.key"
                      :label="option.label"
                      :value="option.key"
                    />
                  </el-select>
                </td>
                <td><code>{{ row.activeTest.sn || row.barcode }}</code></td>
                <td><span class="version-value">{{ row.activeTest.test_version || '—' }}</span></td>
                <td><span :class="{ 'version-value': row.appVersion !== '—' }">{{ row.appVersion }}</span></td>
                <td>{{ row.firmware }}</td>
                <td>{{ formatDate(row.activeTest.queried_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <el-alert v-if="testError && testRecords.length" class="test-versions-inline-error" type="warning" :closable="false">{{ testError }}</el-alert>
      </section>
    </section>

    <el-dialog
      v-model="addDialogVisible"
      :title="t('versions.testVersions.addVersion')"
      width="640px"
      class="test-version-add-dialog"
      destroy-on-close
      @closed="resetAddDialog"
    >
      <div class="add-version-form">
        <label class="add-version-field">
          <span>{{ t('versions.testVersions.selectProduct') }}</span>
          <el-select
            v-model="addForm.productId"
            filterable
            :loading="duroLoading && !duroCatalog"
            :placeholder="t('versions.testVersions.selectProductPlaceholder')"
            @change="onAddProductChange"
          >
            <el-option
              v-for="product in duroProductOptions"
              :key="product.id"
              :label="product.label"
              :value="product.id"
            />
          </el-select>
        </label>

        <label class="add-version-field">
          <span>{{ t('versions.testVersions.selectSoftwareFirmware') }}</span>
          <el-select
            v-model="addForm.parentId"
            filterable
            :disabled="!addForm.productId"
            :placeholder="t('versions.testVersions.selectSoftwareFirmwarePlaceholder')"
            @change="onAddParentChange"
          >
            <el-option
              v-for="group in selectedProductGroups"
              :key="group.parent_id"
              :label="softwareFirmwareLabel(group)"
              :value="group.parent_id"
            />
          </el-select>
        </label>

        <label class="add-version-field">
          <span>{{ t('versions.testVersions.captureProduct') }}</span>
          <el-select
            v-model="addForm.productType"
            :loading="versionProductsLoading"
            :placeholder="t('versions.testVersions.selectCaptureProductPlaceholder')"
            @change="onCaptureProductChange"
          >
            <el-option
              v-for="product in versionProducts"
              :key="product.key"
              :label="product.label"
              :value="product.key"
            />
          </el-select>
          <small v-if="inferredProductTypeHint">{{ inferredProductTypeHint }}</small>
        </label>

        <label class="add-version-field">
          <span>{{ t('versions.testVersions.testField') }}</span>
          <el-select
            v-model="addForm.testName"
            filterable
            :disabled="!addForm.productType"
            :placeholder="t('versions.testVersions.selectTestPlaceholder')"
          >
            <el-option
              v-for="testName in captureTestOptions"
              :key="testName"
              :label="testName"
              :value="testName"
            />
          </el-select>
        </label>

        <label class="add-version-field">
          <span>{{ t('versions.testVersions.selectDevice') }}</span>
          <div class="add-version-device-row">
            <el-select
              v-model="addForm.deviceIp"
              filterable
              class="add-version-device-select"
              :loading="deviceListLoading"
              :placeholder="t('versions.testVersions.selectDevicePlaceholder')"
            >
              <el-option
                v-for="robot in onlineDevices"
                :key="robot.ip"
                :label="deviceLabel(robot)"
                :value="robot.ip"
              />
            </el-select>
            <el-button :icon="Refresh" :loading="deviceListRefreshing" @click="refreshDeviceList">
              {{ t('versions.testVersions.refreshDevices') }}
            </el-button>
          </div>
          <small v-if="!onlineDevices.length && !deviceListLoading">{{ t('versions.testVersions.noDevices') }}</small>
        </label>

        <div v-if="selectedSoftwareFirmwareGroup" class="add-version-reference">
          <p>{{ t('versions.testVersions.duroReference') }}</p>
          <ul>
            <li v-for="child in selectedSoftwareFirmwareGroup.children.slice(0, 6)" :key="child.id">
              <strong>{{ child.name || child.cpn || child.id }}</strong>
              <span>
                App {{ child.app_version || '—' }}
                · FW {{ child.firmware_version || '—' }}
              </span>
            </li>
          </ul>
        </div>

        <el-alert
          v-if="addDialogError"
          type="error"
          :closable="false"
          :title="addDialogError"
          class="add-version-alert"
        />

        <template v-if="addCaptureResult">
          <el-divider />
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item :label="t('versions.testVersions.barcode')">{{ addCaptureResult.test.sn }}</el-descriptions-item>
            <el-descriptions-item :label="t('versions.testVersions.testVersion')">{{ addCaptureResult.test.test_version }}</el-descriptions-item>
            <el-descriptions-item :label="t('versions.testVersions.appVersion')">{{ appVersionFromTest(addCaptureResult.test) }}</el-descriptions-item>
            <el-descriptions-item :label="t('versions.testVersions.firmware')">{{ firmwareSummary(addCaptureResult.test) }}</el-descriptions-item>
            <el-descriptions-item :label="t('versions.testVersions.queriedAt')">{{ formatDate(addCaptureResult.test.queried_at) }}</el-descriptions-item>
            <el-descriptions-item :label="t('versions.testVersions.robotIp')">{{ addCaptureResult.test.robot_ip }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>

      <template #footer>
        <el-button @click="addDialogVisible = false">{{ t('common.actions.close') }}</el-button>
        <el-button
          type="primary"
          :loading="addCaptureLoading"
          :disabled="!canCaptureVersion"
          @click="captureAddVersion"
        >
          {{ t('versions.testVersions.readVersion') }}
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Box, Connection, FolderOpened, Loading, Plus, Refresh, Search, Tickets } from '@element-plus/icons-vue'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import { useAppLocale } from '@/i18n'
import {
  robotApi,
  type RobotInfo,
  type RobotVersionCaptureResponse,
  type RobotVersionHistoryRecord,
  type RobotVersionProduct,
  type RobotVersionProductType,
  type RobotVersionTestEntry,
} from '@/scripts/api'
import { duroApi, type DuroVersionCatalogResponse, type DuroVersionGroup } from '@/scripts/modules/version_modules/api/duro'
import { useRobotScanStore } from '@/scripts/stores/robotScan'
import '@/styles/version_modules/version_modules.css'
import './test_versions.css'

type ActiveTab = 'duro' | 'test'

interface VersionTreeNode {
  key: string
  nodeType: 'product' | 'parent' | 'component'
  nodeTypeLabel?: string
  id: string
  cpn?: string | null
  name: string
  category?: string | null
  revision?: string | null
  app_version?: string | null
  firmware_version?: string | null
  test_commit_hash?: string | null
  test_commit_id?: string | null
  test_tag?: string | null
  description: string
  source_text: string
  children: VersionTreeNode[]
}

interface DuroProductOption {
  id: string
  label: string
  name: string
  cpn?: string | null
}

interface BarcodeTableRow {
  id: string
  barcode: string
  product_name: string
  product_type: string
  robot_ip: string
  defaultTestKey: string
  testOptions: Array<{ key: string; label: string }>
  activeTest: RobotVersionTestEntry
  appVersion: string
  firmware: string
}

const { locale, t } = useAppLocale()
const robotScanStore = useRobotScanStore()

const activeTab = ref<ActiveTab>('duro')
const duroLoading = ref(false)
const duroError = ref('')
const duroSearch = ref('')
const duroCatalog = ref<DuroVersionCatalogResponse | null>(null)
const testLoading = ref(false)
const testError = ref('')
const testSearch = ref('')
const testRecords = ref<RobotVersionHistoryRecord[]>([])
const selectedTestKeyByBarcode = ref<Record<string, string>>({})
const treeProps = { label: 'name', children: 'children' }

const addDialogVisible = ref(false)
const addDialogError = ref('')
const addCaptureLoading = ref(false)
const addCaptureResult = ref<RobotVersionCaptureResponse | null>(null)
const versionProducts = ref<RobotVersionProduct[]>([])
const versionProductsLoading = ref(false)
const deviceListLoading = ref(false)
const deviceListRefreshing = ref(false)
const addForm = reactive({
  productId: '',
  parentId: '',
  productType: '' as RobotVersionProductType | '',
  testName: '',
  deviceIp: '',
})

const versionTreeData = computed(() => filteredGroups.value.map((group) => buildTree(group)))
const defaultExpandedTreeKeys = computed(() => filteredGroups.value.flatMap((group) => defaultExpandedKeys(group)))

const filteredGroups = computed(() => {
  const keyword = duroSearch.value.trim().toLocaleLowerCase()
  if (!keyword) return duroCatalog.value?.groups ?? []
  return (duroCatalog.value?.groups ?? []).filter((group) => {
    const values = [group.product_cpn, group.product_name, group.parent_cpn, group.parent_name, group.parent_description]
    return [...values, ...group.children.flatMap((child) => [child.cpn, child.name, child.description, child.app_version, child.firmware_version, child.test_commit_hash, child.test_commit_id, child.test_tag])]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase().includes(keyword))
  })
})

const duroProductOptions = computed<DuroProductOption[]>(() => {
  const map = new Map<string, DuroProductOption>()
  for (const group of duroCatalog.value?.groups ?? []) {
    if (map.has(group.product_id)) continue
    const name = group.product_name || group.product_cpn || group.product_id
    map.set(group.product_id, {
      id: group.product_id,
      name,
      cpn: group.product_cpn,
      label: group.product_cpn ? `${group.product_cpn} · ${name}` : name,
    })
  }
  return [...map.values()].sort((a, b) => a.label.localeCompare(b.label))
})

const selectedProductGroups = computed(() => (
  (duroCatalog.value?.groups ?? []).filter((group) => group.product_id === addForm.productId)
))

const selectedSoftwareFirmwareGroup = computed(() => (
  selectedProductGroups.value.find((group) => group.parent_id === addForm.parentId) || null
))

const selectedCaptureProduct = computed(() => (
  versionProducts.value.find((product) => product.key === addForm.productType) || null
))

const captureTestOptions = computed(() => selectedCaptureProduct.value?.test_names ?? [])

const onlineDevices = computed<RobotInfo[]>(() => robotScanStore.scanResult?.online_robots ?? [])

const inferredProductTypeHint = computed(() => {
  const inferred = inferProductType(selectedSoftwareFirmwareGroup.value)
  if (!inferred || !addForm.productType || inferred === addForm.productType) return ''
  const label = versionProducts.value.find((product) => product.key === inferred)?.label || inferred
  return t('versions.testVersions.inferredProductHint', { product: label })
})

const canCaptureVersion = computed(() => (
  Boolean(addForm.productId && addForm.parentId && addForm.productType && addForm.testName && addForm.deviceIp)
  && !addCaptureLoading.value
))

const barcodeRows = computed<BarcodeTableRow[]>(() => (
  testRecords.value.map((record) => {
    const testEntries = Object.entries(record.tests || {})
    const defaultTestKey = selectedTestKeyByBarcode.value[record.barcode]
      || latestTestKey(testEntries)
      || testEntries[0]?.[0]
      || ''
    const activeEntry = testEntries.find(([key]) => key === defaultTestKey)?.[1]
      || testEntries[0]?.[1]
      || emptyTestEntry(record)
    return {
      id: record._id || record.barcode,
      barcode: record.barcode,
      product_name: record.product_name,
      product_type: record.product_type,
      robot_ip: record.robot_ip,
      defaultTestKey,
      testOptions: testEntries.map(([key, test]) => ({
        key,
        label: test.test_name || key,
      })),
      activeTest: activeEntry,
      appVersion: appVersionFromTest(activeEntry),
      firmware: firmwareSummary(activeEntry),
    }
  })
))

const filteredBarcodeRows = computed(() => {
  const keyword = testSearch.value.trim().toLocaleLowerCase()
  if (!keyword) return barcodeRows.value
  return barcodeRows.value.filter((row) => {
    const haystack = [
      row.barcode,
      row.product_name,
      row.product_type,
      row.robot_ip,
      row.activeTest.sn,
      row.activeTest.test_name,
      row.activeTest.test_version,
      row.appVersion,
      row.firmware,
      ...row.testOptions.map((option) => option.label),
    ]
    return haystack.some((value) => String(value || '').toLocaleLowerCase().includes(keyword))
  })
})

async function loadDuro(refresh = false): Promise<void> {
  if (duroLoading.value) return
  duroLoading.value = true
  duroError.value = ''
  try {
    const response = await duroApi.versionCatalog(refresh)
    duroCatalog.value = response.data
    if (refresh) ElMessage.success(t('versions.testVersions.duroRefreshed'))
  } catch (error: any) {
    duroError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || t('versions.testVersions.loadFailed')
  } finally {
    duroLoading.value = false
  }
}

async function loadTestVersions(refresh = false): Promise<void> {
  if (testLoading.value) return
  testLoading.value = true
  testError.value = ''
  try {
    const response = await robotApi.getVersionHistory({ page: 1, page_size: 500 })
    testRecords.value = response.data.records
    syncSelectedTestKeys(response.data.records)
    if (refresh) ElMessage.success(t('versions.testVersions.testRefreshed'))
  } catch (error: any) {
    testError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || t('versions.testVersions.loadFailed')
    testRecords.value = []
  } finally {
    testLoading.value = false
  }
}

function syncSelectedTestKeys(records: RobotVersionHistoryRecord[]): void {
  const next: Record<string, string> = { ...selectedTestKeyByBarcode.value }
  for (const record of records) {
    const keys = Object.keys(record.tests || {})
    if (!keys.length) continue
    if (!next[record.barcode] || !keys.includes(next[record.barcode])) {
      next[record.barcode] = latestTestKey(Object.entries(record.tests || {})) || keys[0]
    }
  }
  selectedTestKeyByBarcode.value = next
}

function setSelectedTestKey(barcode: string, testKey: string): void {
  selectedTestKeyByBarcode.value = {
    ...selectedTestKeyByBarcode.value,
    [barcode]: testKey,
  }
}

function selectTab(tab: ActiveTab): void {
  activeTab.value = tab
  if (tab === 'test' && !testRecords.value.length && !testLoading.value) void loadTestVersions()
}

function refreshActive(): void {
  if (activeTab.value === 'duro') void loadDuro(true)
  else void loadTestVersions(true)
}

async function openAddVersionDialog(): Promise<void> {
  addDialogVisible.value = true
  addDialogError.value = ''
  addCaptureResult.value = null
  await Promise.all([
    duroCatalog.value ? Promise.resolve() : loadDuro(),
    loadVersionProducts(),
    loadDeviceList(),
  ])
}

function resetAddDialog(): void {
  addForm.productId = ''
  addForm.parentId = ''
  addForm.productType = ''
  addForm.testName = ''
  addForm.deviceIp = ''
  addDialogError.value = ''
  addCaptureResult.value = null
}

function onAddProductChange(): void {
  addForm.parentId = ''
  addForm.productType = ''
  addForm.testName = ''
  addCaptureResult.value = null
  const groups = selectedProductGroups.value
  if (groups.length === 1) {
    addForm.parentId = groups[0].parent_id
    onAddParentChange()
  }
}

function onAddParentChange(): void {
  addCaptureResult.value = null
  const inferred = inferProductType(selectedSoftwareFirmwareGroup.value)
  if (inferred) {
    addForm.productType = inferred
    onCaptureProductChange()
  } else {
    addForm.productType = ''
    addForm.testName = ''
  }
}

function onCaptureProductChange(): void {
  addCaptureResult.value = null
  const options = captureTestOptions.value
  const matched = matchTestName(selectedSoftwareFirmwareGroup.value, options)
  addForm.testName = matched || options[0] || ''
}

async function loadVersionProducts(): Promise<void> {
  if (versionProducts.value.length || versionProductsLoading.value) return
  versionProductsLoading.value = true
  try {
    const response = await robotApi.getVersionProducts()
    versionProducts.value = response.data.products
  } catch (error: any) {
    addDialogError.value = normalizeError(error) || t('versions.testVersions.loadCaptureOptionsFailed')
  } finally {
    versionProductsLoading.value = false
  }
}

async function loadDeviceList(): Promise<void> {
  if (deviceListLoading.value) return
  deviceListLoading.value = true
  try {
    robotScanStore.loadFromCache()
    await robotScanStore.loadCachedScan()
  } catch (error: any) {
    if (!onlineDevices.value.length) {
      addDialogError.value = normalizeError(error) || t('versions.testVersions.loadDevicesFailed')
    }
  } finally {
    deviceListLoading.value = false
  }
}

async function refreshDeviceList(): Promise<void> {
  if (deviceListRefreshing.value) return
  deviceListRefreshing.value = true
  addDialogError.value = ''
  try {
    await robotScanStore.refreshScan()
    ElMessage.success(t('versions.testVersions.devicesRefreshed', { count: onlineDevices.value.length }))
  } catch (error: any) {
    addDialogError.value = normalizeError(error) || t('versions.testVersions.loadDevicesFailed')
  } finally {
    deviceListRefreshing.value = false
  }
}

async function captureAddVersion(): Promise<void> {
  if (!canCaptureVersion.value || !addForm.productType) return
  const device = onlineDevices.value.find((robot) => robot.ip === addForm.deviceIp)
  addCaptureLoading.value = true
  addDialogError.value = ''
  addCaptureResult.value = null
  try {
    const response = await robotApi.captureVersion({
      ip: addForm.deviceIp,
      port: device?.port ?? 31950,
      product_type: addForm.productType,
      test_name: addForm.testName,
    })
    addCaptureResult.value = response.data
    selectedTestKeyByBarcode.value = {
      ...selectedTestKeyByBarcode.value,
      [response.data.record.barcode]: response.data.test_key,
    }
    await loadTestVersions()
    ElMessage.success(t('versions.testVersions.versionSaved'))
    addDialogVisible.value = false
  } catch (error: any) {
    addDialogError.value = normalizeError(error) || t('versions.testVersions.readVersionFailed')
  } finally {
    addCaptureLoading.value = false
  }
}

function inferProductType(group: DuroVersionGroup | null): RobotVersionProductType | null {
  if (!group) return null
  const text = `${group.product_name} ${group.product_cpn || ''} ${group.parent_name} ${group.parent_cpn || ''}`.toLocaleLowerCase()
  if (text.includes('gripper')) return 'gripper'
  if (text.includes('pipette') || text.includes('p1000') || text.includes('p200') || text.includes('p50') || text.includes('p20')) {
    if (text.includes('96') && (text.includes('1000') || text.includes('p1000'))) return 'pipette_96_channels_1000ul'
    if (text.includes('96') && (text.includes('200') || text.includes('p200'))) return 'pipette_96_channels_200ul'
    if (text.includes('8') || text.includes('multi')) return 'pipette_8_channels'
    return 'pipette_single_channel'
  }
  if (text.includes('robot') || text.includes('flex') || text.includes('ot-3') || text.includes('ot3') || text.includes('gantry')) {
    return 'robot'
  }
  return null
}

function matchTestName(group: DuroVersionGroup | null, options: string[]): string {
  if (!group || !options.length) return ''
  const childNames = group.children.map((child) => child.name.toLocaleLowerCase())
  const parentName = group.parent_name.toLocaleLowerCase()
  let best = ''
  let bestScore = 0
  for (const option of options) {
    const normalized = option.toLocaleLowerCase().replace(/^\d+\.\s*/, '')
    for (const childName of [...childNames, parentName]) {
      const score = overlapScore(normalized, childName)
      if (score > bestScore) {
        bestScore = score
        best = option
      }
    }
  }
  return bestScore >= 2 ? best : ''
}

function overlapScore(left: string, right: string): number {
  const leftTokens = left.split(/[^a-z0-9]+/).filter((token) => token.length > 2)
  const rightTokens = new Set(right.split(/[^a-z0-9]+/).filter((token) => token.length > 2))
  return leftTokens.reduce((score, token) => score + (rightTokens.has(token) ? 1 : 0), 0)
}

function softwareFirmwareLabel(group: DuroVersionGroup): string {
  const name = group.parent_name || group.parent_cpn || group.parent_id
  return group.parent_cpn ? `${group.parent_cpn} · ${name}` : name
}

function deviceLabel(robot: RobotInfo): string {
  const parts = [robot.ip]
  if (robot.name) parts.push(robot.name)
  if (robot.serial_number) parts.push(robot.serial_number)
  return parts.join(' · ')
}

function latestTestKey(entries: Array<[string, RobotVersionTestEntry]>): string {
  if (!entries.length) return ''
  return [...entries].sort((a, b) => {
    const left = Date.parse(a[1].queried_at || '') || 0
    const right = Date.parse(b[1].queried_at || '') || 0
    return right - left
  })[0][0]
}

function emptyTestEntry(record: RobotVersionHistoryRecord): RobotVersionTestEntry {
  return {
    test_name: '',
    sn: record.barcode,
    robot_ip: record.robot_ip,
    test_version: '',
    queried_at: record.updated_at,
  }
}

function appVersionFromTest(test: RobotVersionTestEntry): string {
  const robot = test.robot || {}
  const systemVersion = robot.system_version
  if (typeof systemVersion === 'string' && systemVersion.trim()) return systemVersion.trim()
  const apiVersion = robot.api_version
  if (typeof apiVersion === 'string' && apiVersion.trim()) return apiVersion.trim()
  return '—'
}

function firmwareSummary(test: RobotVersionTestEntry): string {
  if (test.instrument?.firmware_version) return test.instrument.firmware_version
  const versions = (test.subsystems || []).map((item) => `${item.name}: ${item.firmware_version}`).filter(Boolean)
  return versions.join(' · ') || '—'
}

function normalizeError(error: any): string {
  return String(error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || '').trim()
}

function buildTree(group: DuroVersionGroup): VersionTreeNode {
  const parent: VersionTreeNode = {
    key: `parent:${group.product_id}:${group.parent_id}`,
    nodeType: 'parent',
    nodeTypeLabel: 'Version parent',
    id: group.parent_id,
    cpn: `${group.product_cpn || group.product_id} -> ${group.parent_cpn || group.parent_id}`,
    name: `${group.product_name || 'Product'} -> ${group.parent_name || 'Version parent'}`,
    revision: group.parent_revision || group.product_revision,
    description: group.parent_description,
    source_text: group.parent_description,
    children: [],
  }
  const componentNodes = new Map<string, VersionTreeNode>()
  for (const child of group.children) {
    const path = child.path.length > 2 ? child.path.slice(2) : [child.cpn || child.id]
    let siblings = parent.children
    let parentKey = parent.key
    path.forEach((pathPart, index) => {
      const source = group.children.find((item) => (item.cpn || item.id) === pathPart && item.path.slice(2, index + 3).join('/') === path.slice(0, index + 1).join('/')) || (index === path.length - 1 ? child : null)
      if (!source) return
      const key = `${parentKey}/${source.id}`
      let node = componentNodes.get(key)
      if (!node) {
        node = {
          key,
          nodeType: 'component',
          id: source.id,
          cpn: source.cpn,
          name: source.name,
          category: source.category,
          revision: source.revision,
          app_version: source.app_version,
          firmware_version: source.firmware_version,
          test_commit_hash: source.test_commit_hash,
          test_commit_id: source.test_commit_id,
          test_tag: source.test_tag,
          description: source.description,
          source_text: source.source_text,
          children: [],
        }
        siblings.push(node)
        componentNodes.set(key, node)
      }
      siblings = node.children
      parentKey = key
    })
  }
  const keyword = duroSearch.value.trim().toLocaleLowerCase()
  return keyword ? (filterTree(parent, keyword) || parent) : parent
}

function defaultExpandedKeys(_group: DuroVersionGroup): string[] {
  // Keep the Duro catalog compact on first load; users can expand the needed product.
  return []
}

function filterTree(node: VersionTreeNode, keyword: string, ancestorMatched = false): VersionTreeNode | null {
  const nodeMatched = ancestorMatched || [node.cpn, node.name, node.description, node.app_version, node.firmware_version, node.test_commit_hash, node.test_commit_id, node.test_tag]
    .filter(Boolean)
    .some((value) => String(value).toLocaleLowerCase().includes(keyword))
  const children = nodeMatched
    ? node.children
    : node.children
      .map((child) => filterTree(child, keyword))
      .filter((child): child is VersionTreeNode => child !== null)
  if (!nodeMatched && node.nodeType === 'component' && !children.length) return null
  return { ...node, children }
}

function descriptionPreview(value: string): string {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > 130 ? `${text.slice(0, 127)}...` : text || '—'
}

function shortCommitId(value: string): string {
  return value.length > 12 ? value.slice(0, 12) : value
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}

onMounted(() => { void loadDuro() })
</script>
