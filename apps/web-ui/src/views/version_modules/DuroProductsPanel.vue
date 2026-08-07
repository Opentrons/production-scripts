<template>
  <main class="main-content duro-main-content">
    <header class="versions-topbar">
      <div>
        <p class="eyebrow">DURO PRODUCT LIFECYCLE</p>
        <h1>Duro 产品总览</h1>
        <p>读取 Duro 产品、版本、生命周期状态和产品图片。</p>
      </div>
      <div class="versions-topbar-actions">
        <el-button :icon="Link" tag="a" href="https://mfg.duro.app/dashboard" target="_blank">打开 Duro</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadProducts(true)">刷新产品</el-button>
      </div>
    </header>

    <el-alert
      v-if="connectionStatus && (!connectionStatus.configured || (!connectionStatus.token_valid && !connectionStatus.remote_chrome_configured))"
      class="token-alert"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>{{ connectionStatus.configured ? 'Duro token 已过期' : 'Duro token 尚未配置' }}</template>
      <template #default>
        <span v-if="connectionStatus.token_expires_at">过期时间：{{ formatDate(connectionStatus.token_expires_at) }}。</span>
        请配置 Remote Chrome，或在后端设置 <code>PRODUCTION_PLATFORM_DURO_TOKEN</code> 后重新加载。
      </template>
    </el-alert>

    <el-alert
      v-if="connectionStatus?.remote_chrome_configured && connectionStatus.remote_chrome_error"
      class="token-alert"
      type="warning"
      :closable="false"
      show-icon
      title="Duro token 自动刷新未就绪"
    >
      <template #default>
        {{ connectionStatus.remote_chrome_error }}。请在自动打开的专用 Chrome 窗口登录 Duro；登录后后台会自动刷新，无需重启后端。
      </template>
    </el-alert>

    <section class="duro-products-card">
      <div class="duro-toolbar">
        <div class="section-label">
          <span>PRODUCT CATALOG</span>
          <strong>Duro 产品列表</strong>
        </div>
        <div class="duro-filter-row">
          <el-input
            v-model="searchText"
            :prefix-icon="Search"
            clearable
            placeholder="搜索名称、CPN、ID、Alias 或 Revision"
          />
          <el-select v-model="selectedStatus" clearable placeholder="全部状态">
            <el-option v-for="status in statusOptions" :key="status" :label="status" :value="status" />
          </el-select>
          <el-select v-model="selectedRevision" clearable filterable placeholder="全部 Revision">
            <el-option v-for="revision in revisionOptions" :key="revision" :label="revision" :value="revision" />
          </el-select>
        </div>
      </div>

      <div v-if="loading && !productResponse" class="duro-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在读取 Duro 产品信息…</span>
      </div>
      <el-result
        v-else-if="loadError && !productResponse"
        icon="warning"
        title="Duro 产品读取失败"
        :sub-title="loadError"
      >
        <template #extra>
          <el-button type="primary" @click="loadProducts(true)">重试</el-button>
        </template>
      </el-result>
      <el-table
        v-else
        :data="filteredProducts"
        height="clamp(360px, calc(100vh - 300px), 760px)"
        row-class-name="duro-product-row"
        empty-text="没有符合条件的产品"
        @row-click="openProduct"
      >
        <el-table-column label="产品" min-width="310" fixed>
          <template #default="{ row }">
            <div class="product-name-cell">
              <div class="product-thumbnail">
                <img v-if="productImage(row)" :src="productImage(row) || ''" :alt="row.name" />
                <el-icon v-else><Box /></el-icon>
              </div>
              <div>
                <strong>{{ row.name || '未命名产品' }}</strong>
                <span>{{ row.alias || row.cpn || row._id }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="cpn" label="CPN" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.cpn || '—' }}</template>
        </el-table-column>
        <el-table-column prop="revision" label="Revision" width="110">
          <template #default="{ row }">
            <span class="revision-pill">{{ row.revision || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <span class="duro-status-pill" :class="`is-${(row.status || '').toLowerCase()}`">
              {{ row.status || 'UNKNOWN' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="历史版本" width="100" align="center">
          <template #default="{ row }">{{ row.revisions?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="最后修改" width="170">
          <template #default="{ row }">{{ formatDate(row.lastModified) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }">
            <el-button text type="primary" @click.stop="openProduct(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <footer class="product-footer">
        <span>显示 {{ filteredProducts.length }} / {{ productResponse?.count ?? 0 }} 个产品</span>
        <span>更新时间：{{ formatDate(productResponse?.fetched_at ?? null) }}</span>
      </footer>
    </section>

    <footer class="duro-board-footer" aria-label="Duro 产品数量看板">
      <span>产品总数 <strong>{{ productResponse?.count ?? 0 }}</strong></span>
      <span>Production <strong>{{ statusCount('PRODUCTION') }}</strong></span>
      <span>Design <strong>{{ statusCount('DESIGN') }}</strong></span>
      <span>Obsolete <strong>{{ statusCount('OBSOLETE') }}</strong></span>
      <span class="duro-source-state">{{ productResponse?.cached ? 'SQLite 缓存' : 'Duro API' }}</span>
    </footer>

    <el-drawer v-model="productDrawerVisible" size="min(780px, 100vw)" class="duro-product-drawer">
      <template #header>
        <div class="drawer-product-title">
          <span class="drawer-product-icon"><el-icon><Box /></el-icon></span>
          <div>
            <span>DURO PRODUCT</span>
            <strong>{{ selectedProduct?.name }}</strong>
          </div>
        </div>
      </template>

      <div v-if="selectedProduct" class="product-detail-content">
        <el-tabs v-model="detailTab" class="product-detail-tabs" @tab-change="handleDetailTabChange">
          <el-tab-pane label="BOM 结构" name="bom">
            <section class="bom-panel">
              <div class="bom-toolbar">
                <div>
                  <span>BILL OF MATERIALS</span>
                  <strong>可折叠 BOM 树</strong>
                </div>
                <div class="bom-toolbar-actions">
                  <el-button
                    :icon="Link"
                    tag="a"
                    :href="bomResponse?.source_url || duroProductUrl(selectedProduct._id)"
                    target="_blank"
                  >
                    Duro 原页面
                  </el-button>
                  <el-button :icon="Refresh" :loading="bomLoading" @click="loadProductBom(true)">刷新 BOM</el-button>
                </div>
              </div>

              <div v-if="bomResponse" class="bom-summary">
                <article><span>产品 Revision</span><strong>{{ bomResponse.root.revision || '—' }}</strong></article>
                <article><span>第一层物料</span><strong>{{ bomResponse.direct_child_count }}</strong></article>
                <article><span>数据来源</span><strong>{{ bomResponse.cached ? 'SQLite 缓存' : 'Duro API' }}</strong></article>
                <article><span>更新时间</span><strong>{{ formatDate(bomResponse.fetched_at) }}</strong></article>
              </div>

              <div v-if="bomResponse" class="bom-search-row">
                <el-input
                  v-model="bomSearchText"
                  :prefix-icon="Search"
                  clearable
                  placeholder="搜索 BOM 料号或产品名"
                  aria-label="搜索 BOM 料号或产品名"
                />
                <span v-if="bomSearchLoading">正在搜索全部 BOM 层级…</span>
                <span v-else-if="bomSearchResponse && countBomMatches(bomSearchResponse.root)">
                  找到 {{ countBomMatches(bomSearchResponse.root) }} 个匹配项
                </span>
                <span v-else-if="bomSearchResponse">没有匹配的 BOM</span>
              </div>

              <div v-if="bomLoading && !bomResponse" class="bom-loading-state">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在读取产品 BOM…</span>
              </div>
              <el-result
                v-else-if="bomError && !bomResponse"
                icon="warning"
                title="BOM 读取失败"
                :sub-title="bomError"
              >
                <template #extra>
                  <el-button type="primary" @click="loadProductBom(true)">重试</el-button>
                </template>
              </el-result>
              <div v-else-if="bomResponse" class="bom-tree-shell">
                <div class="bom-tree-columns">
                  <span>料号 / 名称</span>
                  <span>Revision</span>
                  <span>数量</span>
                  <span>状态</span>
                </div>
                <el-tree
                  v-if="!bomSearchResponse"
                  :key="bomTreeVersion"
                  class="bom-tree"
                  node-key="ui_key"
                  lazy
                  :load="loadBomTreeNode"
                  :props="bomTreeProps"
                  :default-expanded-keys="[bomRootKey]"
                  :expand-on-click-node="false"
                  empty-text="该产品没有 BOM 子项"
                >
                  <template #default="{ data }">
                    <div class="bom-node-row" :class="{ 'is-product': data.node_type === 'product' }">
                      <div class="bom-node-identity">
                        <el-icon><Box /></el-icon>
                        <div>
                          <strong>{{ data.cpn || data.alias || data.id }}</strong>
                          <span>{{ data.name || '未命名物料' }}</span>
                        </div>
                      </div>
                      <span class="revision-pill">{{ data.revision || '—' }}</span>
                      <span class="bom-quantity">{{ displayQuantity(data) }}</span>
                      <span class="duro-status-pill" :class="`is-${(data.status || '').toLowerCase()}`">
                        {{ data.status || '—' }}
                      </span>
                    </div>
                  </template>
                </el-tree>
                <el-tree
                  v-else
                  class="bom-tree"
                  node-key="ui_key"
                  :data="countBomMatches(bomSearchResponse.root) ? [decorateSearchTree(bomSearchResponse.root, 'search-root', 0)] : []"
                  :props="bomTreeProps"
                  default-expand-all
                  :expand-on-click-node="false"
                  empty-text="没有匹配的 BOM"
                >
                  <template #default="{ data }">
                    <div class="bom-node-row" :class="{ 'is-product': data.node_type === 'product' }">
                      <div class="bom-node-identity">
                        <el-icon><Box /></el-icon>
                        <div>
                          <strong>{{ data.cpn || data.alias || data.id }}</strong>
                          <span>{{ data.name || '未命名物料' }}</span>
                        </div>
                      </div>
                      <span class="revision-pill">{{ data.revision || '—' }}</span>
                      <span class="bom-quantity">{{ displayQuantity(data) }}</span>
                      <span class="duro-status-pill" :class="`is-${(data.status || '').toLowerCase()}`">
                        {{ data.status || '—' }}
                      </span>
                    </div>
                  </template>
                </el-tree>
              </div>
              <el-alert v-if="bomSearchError" class="bom-inline-error" type="warning" :closable="false">
                {{ bomSearchError }}
              </el-alert>
              <el-alert v-if="bomError && bomResponse" class="bom-inline-error" type="warning" :closable="false">
                {{ bomError }}
              </el-alert>
            </section>
          </el-tab-pane>

          <el-tab-pane label="产品信息" name="info">
            <div class="product-hero">
              <img v-if="productImage(selectedProduct)" :src="productImage(selectedProduct) || ''" :alt="selectedProduct.name" />
              <div v-else class="product-hero-placeholder"><el-icon><Box /></el-icon></div>
            </div>

            <div class="product-detail-heading">
              <div>
                <strong>{{ selectedProduct.name }}</strong>
                <span>{{ selectedProduct.description || '暂无产品描述' }}</span>
              </div>
              <span class="duro-status-pill" :class="`is-${(selectedProduct.status || '').toLowerCase()}`">
                {{ selectedProduct.status || 'UNKNOWN' }}
              </span>
            </div>

            <section class="product-detail-grid">
              <article><span>Revision</span><strong>{{ selectedProduct.revision || '—' }}</strong></article>
              <article><span>CPN</span><strong>{{ selectedProduct.cpn || '—' }}</strong></article>
              <article><span>Alias</span><strong>{{ selectedProduct.alias || '—' }}</strong></article>
              <article><span>历史版本</span><strong>{{ selectedProduct.revisions?.length ?? 0 }}</strong></article>
            </section>

            <section class="product-info-list">
              <div><span>Duro ID</span><code>{{ selectedProduct._id }}</code></div>
              <div><span>前一版本</span><strong>{{ displayValue(selectedProduct.previousRevision) }}</strong></div>
              <div><span>前一状态</span><strong>{{ displayValue(selectedProduct.previousStatus) }}</strong></div>
              <div><span>最后修改</span><strong>{{ formatDate(selectedProduct.lastModified) }}</strong></div>
              <div><span>创建时间</span><strong>{{ formatDate(selectedProduct.created) }}</strong></div>
            </section>

            <section v-if="(selectedProduct.images?.length ?? 0) > 1" class="product-image-list">
              <div class="section-label">
                <span>PRODUCT IMAGES</span>
                <strong>产品图片</strong>
              </div>
              <div class="image-grid">
                <img
                  v-for="(image, index) in selectedProduct.images"
                  :key="image._id || index"
                  :src="image.src || ''"
                  :alt="image.name || selectedProduct.name"
                />
              </div>
            </section>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Box, Link, Loading, Refresh, Search } from '@element-plus/icons-vue'
import {
  duroApi,
  type DuroBomNode,
  type DuroConnectionStatus,
  type DuroProduct,
  type DuroProductBomResponse,
  type DuroProductSearchResponse
} from '@/scripts/modules/version_modules/api/duro'


const loading = ref(true)
const loadError = ref('')
const connectionStatus = ref<DuroConnectionStatus | null>(null)
const productResponse = ref<DuroProductSearchResponse | null>(null)
const searchText = ref('')
const selectedStatus = ref('')
const selectedRevision = ref('')
const productDrawerVisible = ref(false)
const selectedProduct = ref<DuroProduct | null>(null)
const detailTab = ref<'bom' | 'info'>('bom')
const bomLoading = ref(false)
const bomError = ref('')
const bomResponse = ref<DuroProductBomResponse | null>(null)
const bomSearchText = ref('')
const bomSearchResponse = ref<DuroProductBomResponse | null>(null)
const bomSearchLoading = ref(false)
const bomSearchError = ref('')
const bomSearchRequestVersion = ref(0)
let bomSearchTimer: ReturnType<typeof setTimeout> | null = null
const bomTreeVersion = ref(0)
const bomRequestVersion = ref(0)
const refreshExpandedComponents = ref(false)
const bomTreeProps = { label: 'name', children: 'children', isLeaf: 'is_leaf' }

type DuroTreeNode = DuroBomNode & {
  ui_key: string
  is_leaf: boolean
}

const bomRootKey = computed(() =>
  bomResponse.value ? `product:${bomResponse.value.product_id}` : 'product:unavailable'
)

const statusOptions = computed(() =>
  [...new Set((productResponse.value?.products ?? []).map((product) => product.status).filter(Boolean) as string[])].sort()
)

const revisionOptions = computed(() =>
  [...new Set((productResponse.value?.products ?? []).map((product) => product.revision).filter(Boolean) as string[])].sort()
)

const filteredProducts = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  return (productResponse.value?.products ?? []).filter((product) => {
    if (selectedStatus.value && product.status !== selectedStatus.value) return false
    if (selectedRevision.value && product.revision !== selectedRevision.value) return false
    if (!keyword) return true
    return [product.name, product.cpn, product._id, product.alias, product.revision, product.description]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword))
  })
})

async function loadProducts(refresh = false) {
  loading.value = true
  loadError.value = ''
  try {
    const statusResponse = await duroApi.status()
    connectionStatus.value = statusResponse.data
    if (
      !statusResponse.data.configured ||
      (!statusResponse.data.token_valid && !statusResponse.data.remote_chrome_configured)
    ) {
      productResponse.value = null
      return
    }
    const response = await duroApi.products(refresh)
    productResponse.value = response.data
    if (refresh) ElMessage.success(`已读取 ${response.data.count} 个 Duro 产品`)
  } catch (error: any) {
    console.error(error)
    loadError.value = error?.response?.data?.detail || error?.message || 'Duro 产品读取失败'
    if (error?.response?.status === 401 && connectionStatus.value) {
      connectionStatus.value = { ...connectionStatus.value, token_valid: false }
    }
  } finally {
    loading.value = false
  }
}

function statusCount(status: string) {
  return (productResponse.value?.products ?? []).filter((product) => product.status === status).length
}

function openProduct(product: DuroProduct) {
  selectedProduct.value = product
  detailTab.value = 'bom'
  bomResponse.value = null
  bomSearchText.value = ''
  bomSearchResponse.value = null
  bomSearchError.value = ''
  bomError.value = ''
  bomTreeVersion.value += 1
  productDrawerVisible.value = true
  void loadProductBom()
}

async function loadProductBom(refresh = false) {
  const productId = selectedProduct.value?._id
  if (!productId) return
  const requestVersion = ++bomRequestVersion.value
  bomLoading.value = true
  bomError.value = ''
  refreshExpandedComponents.value = refresh
  try {
    const response = await duroApi.productBom(productId, refresh)
    if (selectedProduct.value?._id !== productId) return
    bomResponse.value = response.data
    bomTreeVersion.value += 1
    if (refresh) ElMessage.success(`已刷新 ${response.data.root.name || productId} 的 BOM`)
  } catch (error: any) {
    console.error(error)
    if (bomRequestVersion.value !== requestVersion || selectedProduct.value?._id !== productId) return
    bomError.value = error?.response?.data?.detail || error?.message || 'Duro BOM 读取失败'
  } finally {
    if (bomRequestVersion.value === requestVersion) bomLoading.value = false
  }
}

function handleDetailTabChange(name: string | number) {
  if (name === 'bom' && !bomResponse.value && !bomLoading.value) void loadProductBom()
}

async function loadBomTreeNode(node: any, resolve: (children: DuroTreeNode[]) => void) {
  if (node.level === 0) {
    const root = bomResponse.value?.root
    resolve(root ? [decorateBomNode(root, 'product', 0, true)] : [])
    return
  }

  const current = node.data as DuroTreeNode
  if (current.node_type === 'product') {
    resolve(decorateBomChildren(bomResponse.value?.root.children ?? [], current.ui_key))
    return
  }
  if (!current.has_children) {
    resolve([])
    return
  }

  try {
    const response = await duroApi.componentChildren(current.id, refreshExpandedComponents.value)
    resolve(decorateBomChildren(response.data.children, current.ui_key))
  } catch (error: any) {
    console.error(error)
    bomError.value = error?.response?.data?.detail || error?.message || `组件 ${current.cpn || current.id} 展开失败`
    resolve([])
  }
}

function decorateBomChildren(children: DuroBomNode[], parentKey: string) {
  return children.map((child, index) => decorateBomNode(child, parentKey, index))
}

function decorateBomNode(node: DuroBomNode, parentKey: string, index: number, isRoot = false): DuroTreeNode {
  const identity = node.relationship_id || node.id || String(index)
  return {
    ...node,
    children: [],
    ui_key: isRoot ? `product:${node.id}` : `${parentKey}/${identity}:${index}`,
    is_leaf: !node.has_children
  }
}

function decorateSearchTree(node: DuroBomNode, parentKey: string, index: number): DuroTreeNode {
  const decorated = decorateBomNode(node, parentKey, index, node.node_type === 'product')
  decorated.children = node.children.map((child, childIndex) =>
    decorateSearchTree(child, decorated.ui_key, childIndex)
  )
  decorated.is_leaf = decorated.children.length === 0
  return decorated
}

async function searchProductBom() {
  const productId = selectedProduct.value?._id
  const query = bomSearchText.value.trim()
  if (!productId || !query) return
  const requestVersion = ++bomSearchRequestVersion.value
  bomSearchLoading.value = true
  bomSearchError.value = ''
  try {
    const response = await duroApi.searchProductBom(productId, query)
    if (
      requestVersion !== bomSearchRequestVersion.value ||
      selectedProduct.value?._id !== productId ||
      bomSearchText.value.trim() !== query
    ) return
    bomSearchResponse.value = response.data
  } catch (error: any) {
    console.error(error)
    if (requestVersion !== bomSearchRequestVersion.value) return
    bomSearchError.value = error?.response?.data?.detail || error?.message || 'BOM 全层级搜索失败'
  } finally {
    if (requestVersion === bomSearchRequestVersion.value) bomSearchLoading.value = false
  }
}

function countBomMatches(node: DuroBomNode): number {
  const keyword = bomSearchText.value.trim().toLowerCase()
  const currentMatches = keyword && [node.cpn, node.name, node.alias, node.id]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(keyword)) ? 1 : 0
  return currentMatches + node.children.reduce((total, child) => total + countBomMatches(child), 0)
}

function displayQuantity(node: DuroBomNode) {
  if (node.node_type === 'product') return '1'
  if (node.quantity === null || node.quantity === undefined || node.quantity === '') return '—'
  const unit = node.unit_of_measure ? ` ${displayValue(node.unit_of_measure)}` : ''
  return `${displayValue(node.quantity)}${unit}`
}

function duroProductUrl(productId: string) {
  return `https://mfg.duro.app/product/view/${encodeURIComponent(productId)}`
}

function productImage(product: DuroProduct) {
  return product.images?.find((image) => image.src && !image.archived)?.src ?? null
}

function formatDate(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  const normalized = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

watch(bomSearchText, (value) => {
  if (bomSearchTimer) clearTimeout(bomSearchTimer)
  bomSearchRequestVersion.value += 1
  bomSearchLoading.value = false
  bomSearchResponse.value = null
  bomSearchError.value = ''
  if (!value.trim()) {
    return
  }
  bomSearchLoading.value = true
  bomSearchTimer = setTimeout(() => {
    bomSearchTimer = null
    void searchProductBom()
  }, 400)
})

onMounted(() => loadProducts())
onBeforeUnmount(() => {
  if (bomSearchTimer) clearTimeout(bomSearchTimer)
})
</script>

<style scoped>
.token-alert {
  margin-top: 20px;
}

.token-alert code {
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(30, 43, 52, 0.08);
  font-size: 11px;
}

.duro-products-card {
  margin-top: 24px;
  overflow: hidden;
  border: 1px solid #d9e0e5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(18, 33, 47, 0.06);
}

.duro-board-footer {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 22px;
  margin-top: 8px;
  padding: 0 12px;
  border-top: 1px solid #e2e7ea;
  color: #7d8993;
  font-size: 10px;
}

.duro-board-footer span {
  white-space: nowrap;
}

.duro-board-footer strong {
  margin-left: 4px;
  color: #23313d;
  font-size: 12px;
}

.duro-board-footer .duro-source-state {
  color: #29957e;
}

.duro-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 17px 20px;
  border-bottom: 1px solid #e4e9ec;
}

.duro-filter-row {
  width: min(760px, 72%);
  display: grid;
  grid-template-columns: minmax(280px, 1fr) 150px 160px;
  gap: 10px;
}

.duro-loading-state {
  height: clamp(360px, calc(100vh - 300px), 760px);
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  color: #7f8c95;
  font-size: 12px;
}

.duro-loading-state .el-icon {
  color: #29957e;
  font-size: 30px;
}

.product-name-cell {
  display: flex;
  align-items: center;
  gap: 11px;
}

.product-thumbnail {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid #e0e6e9;
  border-radius: 9px;
  background: #f4f7f8;
  color: #8c999f;
}

.product-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.product-name-cell strong,
.product-name-cell span {
  display: block;
}

.product-name-cell strong {
  max-width: 370px;
  overflow: hidden;
  color: #26343d;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-name-cell span {
  margin-top: 5px;
  color: #929da5;
  font-size: 9px;
}

.revision-pill,
.duro-status-pill {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 10px;
  font-size: 9px;
  font-weight: 850;
}

.revision-pill {
  background: #edf1f4;
  color: #576a76;
}

.duro-status-pill {
  background: #e8edf0;
  color: #687781;
}

.duro-status-pill.is-production {
  background: #dff3eb;
  color: #218469;
}

.duro-status-pill.is-design {
  background: #e5effb;
  color: #3979b4;
}

.duro-status-pill.is-obsolete {
  background: #f4e6e5;
  color: #b45750;
}

.product-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 18px;
  border-top: 1px solid #e7ebee;
  color: #87939b;
  font-size: 10px;
}

:deep(.duro-product-row) {
  cursor: pointer;
}

.drawer-product-title {
  display: flex;
  align-items: center;
  gap: 11px;
}

.drawer-product-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: #dff3ee;
  color: #258c75;
}

.drawer-product-title span,
.drawer-product-title strong {
  display: block;
}

.drawer-product-title div > span {
  color: #29957e;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.13em;
}

.drawer-product-title strong {
  max-width: 440px;
  margin-top: 4px;
  overflow: hidden;
  color: #21303a;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 18px;
}

.bom-panel {
  min-height: 520px;
}

.bom-toolbar,
.bom-toolbar-actions,
.bom-summary,
.bom-node-row,
.bom-node-identity {
  display: flex;
  align-items: center;
}

.bom-toolbar {
  justify-content: space-between;
  gap: 18px;
}

.bom-toolbar > div:first-child > span,
.bom-toolbar > div:first-child > strong {
  display: block;
}

.bom-toolbar > div:first-child > span {
  color: #29957e;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.13em;
}

.bom-toolbar > div:first-child > strong {
  margin-top: 5px;
  color: #26343d;
  font-size: 16px;
}

.bom-toolbar-actions {
  gap: 8px;
}

.bom-summary {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1.45fr;
  gap: 9px;
  margin-top: 17px;
}

.bom-search-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.bom-search-row .el-input {
  width: min(420px, 100%);
}

.bom-search-row > span {
  color: #87939b;
  font-size: 10px;
}

.bom-summary article {
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #e1e7ea;
  border-radius: 9px;
  background: #f8fafb;
}

.bom-summary span,
.bom-summary strong {
  display: block;
}

.bom-summary span {
  color: #909ba3;
  font-size: 9px;
}

.bom-summary strong {
  margin-top: 5px;
  overflow: hidden;
  color: #31404a;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bom-loading-state {
  min-height: 430px;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 12px;
  color: #7f8c95;
  font-size: 11px;
}

.bom-loading-state .el-icon {
  color: #29957e;
  font-size: 30px;
}

.bom-tree-shell {
  margin-top: 16px;
  overflow: auto;
  border: 1px solid #dde4e7;
  border-radius: 10px;
}

.bom-tree-columns {
  min-width: 660px;
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 82px 72px 98px;
  gap: 10px;
  padding: 9px 14px 9px 40px;
  border-bottom: 1px solid #e1e6e9;
  background: #f2f5f6;
  color: #7f8b93;
  font-size: 9px;
  font-weight: 750;
  letter-spacing: 0.04em;
}

.bom-tree {
  min-width: 660px;
  padding: 4px 0;
}

:deep(.bom-tree .el-tree-node__content) {
  min-height: 56px;
  height: auto;
  padding-right: 14px;
  border-bottom: 1px solid #edf0f2;
}

:deep(.bom-tree > .el-tree-node:last-child > .el-tree-node__content) {
  border-bottom: 0;
}

:deep(.bom-tree .el-tree-node__content:hover) {
  background: #f3f8f7;
}

.bom-node-row {
  min-width: 0;
  width: 100%;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 82px 72px 98px;
  gap: 10px;
}

.bom-node-row.is-product {
  font-weight: 750;
}

.bom-node-identity {
  min-width: 0;
  gap: 9px;
}

.bom-node-identity > .el-icon {
  flex: 0 0 auto;
  color: #39947f;
}

.bom-node-identity div {
  min-width: 0;
}

.bom-node-identity strong,
.bom-node-identity span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bom-node-identity strong {
  color: #2b3942;
  font-size: 11px;
}

.bom-node-identity span {
  margin-top: 4px;
  color: #87939b;
  font-size: 9px;
}

.bom-quantity {
  color: #34434c;
  font-size: 11px;
  font-weight: 750;
}

.bom-inline-error {
  margin-top: 12px;
}

.product-hero {
  height: 270px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border: 1px solid #dfe5e8;
  border-radius: 12px;
  background: #f6f8f9;
}

.product-hero img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.product-hero-placeholder {
  color: #9ba6ad;
  font-size: 58px;
}

.product-detail-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-top: 18px;
}

.product-detail-heading div strong,
.product-detail-heading div span {
  display: block;
}

.product-detail-heading div strong {
  color: #21303a;
  font-size: 17px;
}

.product-detail-heading div span {
  margin-top: 7px;
  color: #7f8c95;
  font-size: 11px;
  line-height: 1.6;
}

.product-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 9px;
  margin-top: 18px;
}

.product-detail-grid article {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e1e6e9;
  border-radius: 9px;
}

.product-detail-grid span,
.product-detail-grid strong {
  display: block;
}

.product-detail-grid span {
  color: #909ba3;
  font-size: 9px;
}

.product-detail-grid strong {
  margin-top: 5px;
  overflow: hidden;
  color: #283640;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-info-list {
  margin-top: 18px;
  border-top: 1px solid #e5eaed;
}

.product-info-list div {
  min-height: 46px;
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #edf0f2;
}

.product-info-list span {
  color: #8b969e;
  font-size: 10px;
}

.product-info-list strong,
.product-info-list code {
  overflow: hidden;
  color: #35434d;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-image-list {
  margin-top: 22px;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 9px;
  margin-top: 11px;
}

.image-grid img {
  width: 100%;
  height: 120px;
  object-fit: contain;
  border: 1px solid #e0e6e9;
  border-radius: 8px;
  background: #f7f9fa;
}

@media (max-width: 900px) {
  .duro-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .duro-filter-row {
    width: 100%;
    grid-template-columns: minmax(0, 1fr) repeat(2, minmax(120px, 0.5fr));
  }

  .duro-board-footer {
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 8px 16px;
  }
}

@media (max-width: 560px) {
  .duro-filter-row,
  .image-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
