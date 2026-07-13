<template>
  <div class="test-case-tree">
    <header class="tree-head">
      <div>
        <p>Collections</p>
        <h2>测试管理</h2>
      </div>
      <el-tooltip content="新建产品" placement="bottom">
        <button class="icon-button" type="button" @click="$emit('create-product')">
          <el-icon><Plus /></el-icon>
        </button>
      </el-tooltip>
    </header>

    <div v-if="products.length === 0" class="tree-empty">
      <el-icon><FolderOpened /></el-icon>
      <span>点击右上角创建产品</span>
    </div>

    <div v-else class="tree-body">
      <section v-for="product in products" :key="product.product_id" class="tree-product">
        <div class="tree-row product-row">
          <button
            class="row-main"
            type="button"
            :aria-expanded="isProductExpanded(product.product_id)"
            @click="toggleProduct(product.product_id)"
          >
            <el-icon class="expand-icon" :class="{ 'is-expanded': isProductExpanded(product.product_id) }">
              <ArrowRight />
            </el-icon>
            <el-icon><Box /></el-icon>
            <span class="row-text">
              <strong>{{ product.product_name }}</strong>
              <small>{{ product.product_id }}</small>
            </span>
          </button>
          <el-tooltip content="新建测试类型" placement="right">
            <button class="row-action" type="button" @click="$emit('create-type', product)">
              <el-icon><Plus /></el-icon>
            </button>
          </el-tooltip>
        </div>

        <template v-if="isProductExpanded(product.product_id)">
          <div v-if="product.groups.length === 0" class="tree-hint">还没有测试类型</div>

          <section v-for="group in product.groups" :key="group.test_type" class="tree-type">
            <div class="tree-row type-row">
              <button
                class="row-main"
                type="button"
                :aria-expanded="isTypeExpanded(product.product_id, group.test_type)"
                @click="toggleType(product.product_id, group.test_type)"
              >
                <el-icon class="expand-icon" :class="{ 'is-expanded': isTypeExpanded(product.product_id, group.test_type) }">
                  <ArrowRight />
                </el-icon>
                <el-icon><Collection /></el-icon>
                <span class="row-text">
                  <strong>{{ group.test_type }}</strong>
                  <small>{{ group.total }} 个用例</small>
                </span>
              </button>
              <el-tooltip content="新建测试用例" placement="right">
                <button class="row-action" type="button" @click="$emit('create-case', product, group.test_type)">
                  <el-icon><Plus /></el-icon>
                </button>
              </el-tooltip>
            </div>

            <template v-if="isTypeExpanded(product.product_id, group.test_type)">
              <div v-if="group.cases.length === 0" class="tree-hint is-type">还没有用例</div>
              <button
                v-for="item in group.cases"
                :key="item.id"
                class="case-row"
                :class="{ 'is-active': item.id === selectedId }"
                type="button"
                @click="$emit('select-case', item.id)"
              >
                <span class="case-status" :class="`is-${item.status}`"></span>
                <span class="case-name">{{ item.name }}</span>
              </button>
            </template>
          </section>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ArrowRight, Box, Collection, FolderOpened, Plus } from '@element-plus/icons-vue'
import type { TestCaseTreeProduct } from '@/services/testCaseService'

const props = defineProps<{
  products: TestCaseTreeProduct[]
  selectedId: string | null
}>()

defineEmits<{
  (event: 'create-product'): void
  (event: 'create-type', product: TestCaseTreeProduct): void
  (event: 'create-case', product: TestCaseTreeProduct, testType: string): void
  (event: 'select-case', caseId: string): void
}>()

const expandedProducts = ref<Set<string>>(new Set())
const expandedTypes = ref<Set<string>>(new Set())

const selectedPath = computed(() => {
  for (const product of props.products) {
    for (const group of product.groups) {
      if (group.cases.some((item) => item.id === props.selectedId)) {
        return {
          productId: product.product_id,
          typeKey: typeExpandKey(product.product_id, group.test_type)
        }
      }
    }
  }
  return null
})

watch(
  () => props.products,
  (products) => {
    const productIds = new Set(products.map((product) => product.product_id))
    const typeKeys = new Set(
      products.flatMap((product) =>
        product.groups.map((group) => typeExpandKey(product.product_id, group.test_type))
      )
    )

    expandedProducts.value = new Set(
      Array.from(expandedProducts.value).filter((productId) => productIds.has(productId))
    )
    expandedTypes.value = new Set(
      Array.from(expandedTypes.value).filter((typeKey) => typeKeys.has(typeKey))
    )

    if (expandedProducts.value.size === 0 && products.length > 0) {
      expandedProducts.value.add(products[0].product_id)
    }
  },
  { immediate: true, deep: true }
)

watch(
  selectedPath,
  (path) => {
    if (!path) return
    expandedProducts.value.add(path.productId)
    expandedTypes.value.add(path.typeKey)
  },
  { immediate: true }
)

function typeExpandKey(productId: string, testType: string) {
  return `${productId}::${testType}`
}

function isProductExpanded(productId: string) {
  return expandedProducts.value.has(productId)
}

function isTypeExpanded(productId: string, testType: string) {
  return expandedTypes.value.has(typeExpandKey(productId, testType))
}

function toggleProduct(productId: string) {
  const next = new Set(expandedProducts.value)
  if (next.has(productId)) {
    next.delete(productId)
  } else {
    next.add(productId)
  }
  expandedProducts.value = next
}

function toggleType(productId: string, testType: string) {
  const key = typeExpandKey(productId, testType)
  const next = new Set(expandedTypes.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedTypes.value = next
}
</script>

<style scoped>
.test-case-tree {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #f7f9fb;
  color: #172033;
}

.tree-head {
  height: 64px;
  flex: 0 0 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px 0 16px;
  border-bottom: 1px solid #dce3eb;
}

.tree-head p {
  margin: 0 0 4px;
  color: #7a8596;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: 0;
  text-transform: uppercase;
}

.tree-head h2 {
  margin: 0;
  color: #172033;
  font-size: 17px;
  font-weight: 750;
  line-height: 1.2;
}

.icon-button,
.row-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: #526173;
  cursor: pointer;
}

.icon-button {
  width: 30px;
  height: 30px;
  border-radius: 4px;
}

.row-action {
  width: 26px;
  height: 26px;
  border-radius: 4px;
}

.icon-button:hover,
.row-action:hover {
  background: #e7edf4;
  color: #172033;
}

.tree-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px 8px 16px;
}

.tree-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #7b8494;
  font-size: 13px;
}

.tree-product + .tree-product {
  margin-top: 10px;
}

.tree-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 4px;
}

.row-main {
  min-width: 0;
  height: 38px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
}

.expand-icon {
  width: 14px;
  flex: 0 0 14px;
  color: #8a96a8;
  transition: transform 0.16s ease;
}

.expand-icon.is-expanded {
  transform: rotate(90deg);
}

.product-row .row-main {
  font-weight: 700;
}

.type-row .row-main {
  height: 32px;
  color: #3f4b5c;
}

.row-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-text strong,
.row-text small,
.case-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-text strong {
  color: #182132;
  font-size: 13px;
  line-height: 1.1;
}

.row-text small {
  color: #7b8494;
  font-size: 11px;
  line-height: 1.1;
}

.tree-type {
  margin-left: 18px;
}

.tree-hint {
  margin: 2px 0 8px 34px;
  color: #9aa4b2;
  font-size: 12px;
}

.tree-hint.is-type {
  margin-left: 30px;
}

.case-row {
  width: calc(100% - 18px);
  height: 30px;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  margin-left: 18px;
  padding: 0 8px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #394556;
  font: inherit;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.case-row:hover,
.row-main:hover {
  background: #edf2f7;
}

.case-row.is-active {
  background: #dfe9f5;
  color: #0f2f57;
}

.case-status {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #9ca3af;
}

.case-status.is-active {
  background: #2f9e73;
}

.case-status.is-draft {
  background: #d28b28;
}

.case-status.is-archived {
  background: #9ca3af;
}
</style>
