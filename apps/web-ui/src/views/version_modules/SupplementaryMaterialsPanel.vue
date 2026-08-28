<template>
  <main class="main-content supplies-page">
    <header class="versions-topbar supplies-topbar">
      <div>
        <p class="eyebrow">MASTER DATA</p>
        <h1>{{ t('versions.supplies.title') }}</h1>
        <p>{{ t('versions.supplies.subtitle') }}</p>
      </div>
      <div class="versions-topbar-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadMaterials">
          {{ t('common.actions.refresh') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">
          {{ t('common.actions.add') }}
        </el-button>
      </div>
    </header>

    <section class="supplies-card">
      <div class="supplies-toolbar">
        <div class="section-label">
          <span>ACCESSORY CATALOG</span>
          <strong>{{ t('versions.supplies.list') }}</strong>
        </div>
        <div class="supplies-filter-row" :aria-label="t('versions.supplies.search')">
          <el-input
            v-model="searchText"
            class="supplies-search"
            clearable
            :prefix-icon="Search"
            :placeholder="t('versions.supplies.searchPlaceholder')"
            @keyup.enter="loadMaterials"
            @clear="loadMaterials"
          />
          <el-button :icon="Search" :loading="loading" @click="loadMaterials">
            {{ t('common.actions.search') }}
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="loadError"
        class="supplies-error"
        type="error"
        :closable="false"
        show-icon
      >
        <template #title>
          <div class="supplies-error-content">
            <span>{{ t('versions.supplies.loadFailed', { error: loadError }) }}</span>
            <el-button size="small" type="danger" plain :loading="loading" @click="loadMaterials">
              {{ t('common.actions.retry') }}
            </el-button>
          </div>
        </template>
      </el-alert>

      <el-table
        v-loading="loading"
        :data="materials"
        class="supplies-table"
        height="clamp(360px, calc(100vh - 300px), 760px)"
        border
        stripe
        :empty-text="t('versions.supplies.empty')"
      >
        <el-table-column
          :label="t('versions.supplies.materialNumber')"
          min-width="280"
          fixed="left"
        >
          <template #default="{ row }">
            <div class="supply-number-cell">
              <div class="supply-thumbnail"><el-icon><Files /></el-icon></div>
              <div>
                <strong>{{ row.material_number }}</strong>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          prop="english_name"
          :label="t('versions.supplies.englishName')"
          min-width="330"
          show-overflow-tooltip
        />
        <el-table-column
          prop="chinese_name"
          :label="t('versions.supplies.chineseName')"
          min-width="260"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ row.chinese_name || '—' }}</template>
        </el-table-column>
        <el-table-column
          prop="eid"
          label="EID"
          width="120"
          align="center"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ row.eid || '—' }}</template>
        </el-table-column>
        <el-table-column
          :label="t('versions.common.actions')"
          width="120"
          fixed="right"
          align="center"
        >
          <template #default="{ row }">
            <div class="supply-actions">
              <el-tooltip :content="t('common.actions.edit')" placement="top">
                <el-button
                  text
                  type="primary"
                  :icon="Edit"
                  :aria-label="t('common.actions.edit')"
                  @click="openEdit(row)"
                />
              </el-tooltip>
              <el-tooltip :content="t('common.actions.delete')" placement="top">
                <el-button
                  text
                  type="danger"
                  :icon="Delete"
                  :aria-label="t('common.actions.delete')"
                  @click="deleteMaterial(row)"
                />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <footer class="product-footer">
        <span>{{ t('versions.supplies.total', { count: materials.length }) }}</span>
        <span>{{ t('versions.supplies.storage') }}</span>
      </footer>
    </section>

    <footer class="supplies-board-footer" :aria-label="t('versions.supplies.title')">
      <span>{{ t('versions.supplies.title') }} <strong>{{ materials.length }}</strong></span>
      <span class="supplies-source-state">{{ t('versions.supplies.storage') }}</span>
    </footer>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="620px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="supplies-form"
      >
        <el-form-item :label="t('versions.supplies.materialNumber')" prop="material_number">
          <el-input v-model="form.material_number" clearable />
        </el-form-item>
        <el-form-item :label="t('versions.supplies.englishName')" prop="english_name">
          <el-input v-model="form.english_name" clearable />
        </el-form-item>
        <el-form-item :label="t('versions.supplies.chineseName')" prop="chinese_name">
          <el-input v-model="form.chinese_name" clearable />
        </el-form-item>
        <el-form-item label="EID" prop="eid">
          <el-input v-model="form.eid" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ t('common.actions.save') }}
        </el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Delete, Edit, Files, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { useAppLocale } from '@/i18n'
import {
  suppliesApi,
  type SupplementaryMaterial,
  type SupplementaryMaterialPayload,
} from '@/scripts/modules/version_modules/api/supplies'

const { t } = useI18n()
const { locale } = useAppLocale()
const materials = ref<SupplementaryMaterial[]>([])
const loading = ref(false)
const saving = ref(false)
const loadError = ref('')
const searchText = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<SupplementaryMaterialPayload>({
  material_number: '',
  english_name: '',
  chinese_name: '',
  eid: '',
})

const rules = computed<FormRules>(() => ({
  material_number: [
    { required: true, message: t('versions.supplies.validation.materialNumber'), trigger: 'blur' },
  ],
}))

const dialogTitle = computed(() => (
  editingId.value ? t('versions.supplies.editTitle') : t('versions.supplies.addTitle')
))

function apiError(error: any) {
  const detail = error?.response?.data?.detail
  return detail?.message || detail?.error || detail || error?.message || t('errors.unknown')
}

async function loadMaterials() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await suppliesApi.list(searchText.value)
    materials.value = response.data.items
  } catch (error: any) {
    loadError.value = apiError(error)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, {
    material_number: '',
    english_name: '',
    chinese_name: '',
    eid: '',
  })
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(material: SupplementaryMaterial) {
  editingId.value = material.id
  Object.assign(form, {
    material_number: material.material_number,
    english_name: material.english_name,
    chinese_name: material.chinese_name,
    eid: material.eid,
  })
  dialogVisible.value = true
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate()
  if (!valid) return

  const payload = {
    material_number: form.material_number.trim(),
    english_name: form.english_name.trim(),
    chinese_name: form.chinese_name.trim(),
    eid: form.eid.trim(),
  }
  saving.value = true
  try {
    if (editingId.value) {
      await suppliesApi.update(editingId.value, payload)
      ElMessage.success(t('versions.supplies.messages.updated'))
    } else {
      await suppliesApi.create(payload)
      ElMessage.success(t('versions.supplies.messages.created'))
    }
    dialogVisible.value = false
    await loadMaterials()
  } catch (error: any) {
    ElMessage.error(t('versions.supplies.saveFailed', { error: apiError(error) }))
  } finally {
    saving.value = false
  }
}

async function deleteMaterial(material: SupplementaryMaterial) {
  try {
    await ElMessageBox.confirm(
      t('versions.supplies.deleteConfirm', { material: material.material_number }),
      t('versions.supplies.deleteTitle'),
      { type: 'warning', confirmButtonText: t('common.actions.delete'), cancelButtonText: t('common.actions.cancel') },
    )
    await suppliesApi.remove(material.id)
    ElMessage.success(t('versions.supplies.messages.deleted'))
    await loadMaterials()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(t('versions.supplies.deleteFailed', { error: apiError(error) }))
  }
}

onMounted(() => {
  void loadMaterials()
})
</script>

<style scoped>
.supplies-page {
  width: 100%;
  min-width: 0;
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.supplies-topbar {
  flex: 0 0 auto;
}

.supplies-card {
  margin-top: 24px;
  overflow: hidden;
  border: 1px solid #d9e0e5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 34px rgba(18, 33, 47, 0.06);
}

.supplies-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 17px 20px;
  border-bottom: 1px solid #e4e9ec;
}

.supplies-filter-row {
  width: min(520px, 64%);
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 10px;
}

.supplies-search {
  width: 100%;
}

.supplies-error {
  margin: 14px 20px 0;
}

.supplies-error-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  width: 100%;
}

.supplies-table :deep(.el-table__cell .cell) {
  text-align: left;
}

.supplies-table :deep(.el-table__header .cell) {
  color: #475861;
  font-weight: 750;
}

.supply-number-cell {
  display: flex;
  align-items: center;
  gap: 11px;
}

.supply-thumbnail {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  overflow: hidden;
  border: 1px solid #e0e6e9;
  border-radius: 9px;
  background: #f4f7f8;
  color: #29957e;
}

.supply-number-cell strong {
  display: block;
}

.supply-number-cell strong {
  color: #26343d;
  font-size: 12px;
}

.supply-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.product-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 18px;
  border-top: 1px solid #e7ebee;
  color: #71828a;
  font-size: 10px;
}

.supplies-board-footer {
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

.supplies-board-footer span {
  white-space: nowrap;
}

.supplies-board-footer strong {
  margin-left: 4px;
  color: #23313d;
  font-size: 12px;
}

.supplies-source-state {
  color: #29957e;
}

.supplies-form {
  padding: 4px 10px 0;
}

@media (max-width: 760px) {
  .supplies-topbar,
  .supplies-toolbar,
  .supplies-board-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .supplies-filter-row {
    width: 100%;
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .supplies-board-footer {
    justify-content: flex-start;
    gap: 8px 16px;
  }

}

@media (max-width: 560px) {
  .supplies-filter-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
