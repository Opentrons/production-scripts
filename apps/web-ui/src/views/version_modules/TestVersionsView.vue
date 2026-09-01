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
        <div class="test-versions-source" :class="{ 'is-ready': activeTab === 'duro' ? Boolean(duroCatalog) : Boolean(testRows.length) }">
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
          <strong v-if="testRows.length">{{ testRows.length }}</strong>
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
                      <strong>{{ data.cpn || data.id }}</strong>
                      <span>{{ data.name || t('versions.testVersions.unnamedComponent') }}</span>
                    </div>
                  </div>
                  <span class="tree-node-kind">{{ data.category || data.nodeTypeLabel || '—' }}</span>
                  <span :class="{ 'version-value': data.app_version }">{{ data.app_version || '—' }}</span>
                  <span :class="{ 'version-value': data.firmware_version }">{{ data.firmware_version || '—' }}</span>
                  <div class="tree-node-commit">
                    <code v-if="data.test_commit_hash">{{ data.test_commit_hash }}</code>
                    <span v-else>—</span>
                    <small v-if="data.test_tag">{{ data.test_tag }}</small>
                  </div>
                  <span>{{ data.revision || '—' }}</span>
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
          <el-input v-model="testSearch" :prefix-icon="Search" clearable :placeholder="t('versions.testVersions.testSearchPlaceholder')" />
        </div>
        <div v-if="testLoading && !testRows.length" class="test-versions-state">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ t('versions.testVersions.loadingTest') }}</span>
        </div>
        <el-result v-else-if="testError && !testRows.length" icon="warning" :title="t('versions.testVersions.loadFailed')" :sub-title="testError">
          <template #extra><el-button type="primary" @click="loadTestVersions(true)">{{ t('common.actions.retry') }}</el-button></template>
        </el-result>
        <div v-else-if="!filteredTestRows.length" class="test-versions-state is-empty">
          <Tickets :size="34" aria-hidden="true" />
          <strong>{{ t('versions.testVersions.noTestData') }}</strong>
          <span>{{ t('versions.testVersions.noTestDataHint') }}</span>
        </div>
        <div v-else class="test-version-table-wrap test-history-table-wrap">
          <table class="test-version-table">
            <thead>
              <tr>
                <th>{{ t('versions.testVersions.product') }}</th>
                <th>{{ t('versions.testVersions.serial') }}</th>
                <th>{{ t('versions.testVersions.testName') }}</th>
                <th>{{ t('versions.testVersions.testVersion') }}</th>
                <th>{{ t('versions.testVersions.firmware') }}</th>
                <th>{{ t('versions.testVersions.robotIp') }}</th>
                <th>{{ t('versions.testVersions.queriedAt') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in filteredTestRows" :key="row.id">
                <td><strong>{{ row.product_name }}</strong><span>{{ row.product_type }}</span></td>
                <td><code>{{ row.sn }}</code></td>
                <td>{{ row.test_name }}</td>
                <td><span class="version-value">{{ row.test_version || '—' }}</span></td>
                <td>{{ row.firmware }}</td>
                <td>{{ row.robot_ip }}</td>
                <td>{{ formatDate(row.queried_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <el-alert v-if="testError && testRows.length" class="test-versions-inline-error" type="warning" :closable="false">{{ testError }}</el-alert>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Box, Connection, FolderOpened, Loading, Refresh, Search, Tickets } from '@element-plus/icons-vue'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import { useAppLocale } from '@/i18n'
import { robotApi, type RobotVersionHistoryRecord, type RobotVersionTestEntry } from '@/scripts/api'
import { duroApi, type DuroVersionCatalogResponse, type DuroVersionComponent, type DuroVersionGroup } from '@/scripts/modules/version_modules/api/duro'
import '@/styles/version_modules/version_modules.css'
import './test_versions.css'

type ActiveTab = 'duro' | 'test'
interface TestVersionRow {
  id: string
  product_name: string
  product_type: string
  sn: string
  test_name: string
  test_version: string
  firmware: string
  robot_ip: string
  queried_at: string
}

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
  test_tag?: string | null
  description: string
  source_text: string
  children: VersionTreeNode[]
}

const { locale, t } = useAppLocale()
const activeTab = ref<ActiveTab>('duro')
const duroLoading = ref(false)
const duroError = ref('')
const duroSearch = ref('')
const duroCatalog = ref<DuroVersionCatalogResponse | null>(null)
const testLoading = ref(false)
const testError = ref('')
const testSearch = ref('')
const testRows = ref<TestVersionRow[]>([])
const treeProps = { label: 'name', children: 'children' }
const versionTreeData = computed(() => filteredGroups.value.map((group) => buildTree(group)))
const defaultExpandedTreeKeys = computed(() => filteredGroups.value.flatMap((group) => defaultExpandedKeys(group)))

const filteredGroups = computed(() => {
  const keyword = duroSearch.value.trim().toLocaleLowerCase()
  if (!keyword) return duroCatalog.value?.groups ?? []
  return (duroCatalog.value?.groups ?? []).filter((group) => {
    const values = [group.product_cpn, group.product_name, group.parent_cpn, group.parent_name, group.parent_description]
    return [...values, ...group.children.flatMap((child) => [child.cpn, child.name, child.description, child.app_version, child.firmware_version, child.test_commit_hash, child.test_tag])]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase().includes(keyword))
  })
})

const filteredTestRows = computed(() => {
  const keyword = testSearch.value.trim().toLocaleLowerCase()
  if (!keyword) return testRows.value
  return testRows.value.filter((row) => Object.values(row).some((value) => String(value).toLocaleLowerCase().includes(keyword)))
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
    testRows.value = flattenTestHistory(response.data.records)
    if (refresh) ElMessage.success(t('versions.testVersions.testRefreshed'))
  } catch (error: any) {
    testError.value = error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || t('versions.testVersions.loadFailed')
    testRows.value = []
  } finally {
    testLoading.value = false
  }
}

function selectTab(tab: ActiveTab): void {
  activeTab.value = tab
  if (tab === 'test' && !testRows.value.length && !testLoading.value) void loadTestVersions()
}

function refreshActive(): void {
  if (activeTab.value === 'duro') void loadDuro(true)
  else void loadTestVersions(true)
}

function buildTree(group: DuroVersionGroup): VersionTreeNode {
  const product: VersionTreeNode = {
    key: `product:${group.product_id}:${group.parent_id}`,
    nodeType: 'product',
    nodeTypeLabel: 'Product',
    id: group.product_id,
    cpn: group.product_cpn,
    name: group.product_name,
    revision: group.product_revision,
    description: '',
    source_text: '',
    children: [],
  }
  const parent: VersionTreeNode = {
    key: `parent:${group.product_id}:${group.parent_id}`,
    nodeType: 'parent',
    nodeTypeLabel: 'Version parent',
    id: group.parent_id,
    cpn: group.parent_cpn,
    name: group.parent_name,
    revision: group.parent_revision,
    description: group.parent_description,
    source_text: group.parent_description,
    children: [],
  }
  product.children = [parent]
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
  return keyword ? (filterTree(product, keyword) || product) : product
}

function defaultExpandedKeys(group: DuroVersionGroup): string[] {
  return [
    `product:${group.product_id}:${group.parent_id}`,
    `parent:${group.parent_id}`,
  ]
}

function filterTree(node: VersionTreeNode, keyword: string, ancestorMatched = false): VersionTreeNode | null {
  const nodeMatched = ancestorMatched || [node.cpn, node.name, node.description, node.app_version, node.firmware_version, node.test_commit_hash, node.test_tag]
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

function flattenTestHistory(records: RobotVersionHistoryRecord[]): TestVersionRow[] {
  return records.flatMap((record) => Object.entries(record.tests || {}).map(([testKey, test]) => ({
    id: `${record._id}:${testKey}`,
    product_name: record.product_name,
    product_type: record.product_type,
    sn: test.sn || record.barcode,
    test_name: test.test_name || testKey,
    test_version: test.test_version || '',
    firmware: firmwareSummary(test),
    robot_ip: test.robot_ip || record.robot_ip,
    queried_at: test.queried_at || record.updated_at,
  })))
}

function firmwareSummary(test: RobotVersionTestEntry): string {
  if (test.instrument?.firmware_version) return test.instrument.firmware_version
  const versions = (test.subsystems || []).map((item) => `${item.name}: ${item.firmware_version}`).filter(Boolean)
  return versions.join(' · ') || '—'
}

function descriptionPreview(value: string): string {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > 130 ? `${text.slice(0, 127)}...` : text || '—'
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale.value, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date)
}

onMounted(() => { void loadDuro() })
</script>
