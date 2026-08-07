<template>
  <div v-loading="loading || downloading || deleting" class="testing-data-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <div class="testing-data-toolbar">
        <el-breadcrumb separator="/" class="testing-data-breadcrumb">
          <el-breadcrumb-item
            v-for="(segment, index) in pathSegments"
            :key="`${segment.path}-${index}`"
          >
            <button class="path-link" type="button" @click="openPath(segment.path)">
              {{ segment.label }}
            </button>
          </el-breadcrumb-item>
        </el-breadcrumb>

        <div class="toolbar-actions">
          <el-input
            v-if="entries.length"
            v-model="searchKeyword"
            class="toolbar-search"
            clearable
            size="small"
            placeholder="搜索当前列表"
          />
          <span class="selection-count">已选择 {{ selectedEntries.length }} 项</span>
          <el-button
            :icon="Download"
            type="primary"
            size="small"
            :disabled="selectedEntries.length === 0"
            :loading="downloading"
            @click="downloadSelected"
          >
            下载 ZIP
          </el-button>
          <el-button
            :icon="Delete"
            type="danger"
            plain
            size="small"
            :disabled="selectedEntries.length === 0"
            :loading="deleting"
            @click="deleteSelected"
          >
            删除
          </el-button>
          <el-tooltip content="刷新" placement="top">
            <el-button :icon="Refresh" :loading="loading" circle size="small" @click="refreshDirectory" />
          </el-tooltip>
          <el-tooltip content="上级目录" placement="top">
            <el-button
              :icon="Top"
              circle
              size="small"
              :disabled="currentPath === ROOT_PATH"
              @click="openPath(parentPath)"
            />
          </el-tooltip>
        </div>
      </div>

      <el-table
        ref="tableRef"
        :data="filteredEntries"
        row-key="path"
        class="testing-data-table"
        empty-text="当前目录为空"
        @selection-change="handleSelectionChange"
        @row-dblclick="handleRowOpen"
      >
        <el-table-column type="selection" width="50" reserve-selection />
        <el-table-column label="名称" min-width="320">
          <template #default="{ row }">
            <button
              class="entry-main"
              type="button"
              :disabled="!row.is_dir"
              @click="handleEntryOpen(row)"
            >
              <span class="entry-icon">
                <el-icon>
                  <FolderOpened v-if="row.is_dir" />
                  <Document v-else />
                </el-icon>
              </span>
              <el-tooltip :content="row.name" placement="top" :show-after="400">
                <span class="entry-name">{{ row.name }}</span>
              </el-tooltip>
            </button>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            {{ row.is_dir ? '文件夹' : '文件' }}
          </template>
        </el-table-column>
        <el-table-column label="大小" width="120">
          <template #default="{ row }">
            {{ row.is_dir ? '-' : formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="修改时间" width="190">
          <template #default="{ row }">
            {{ formatTime(row.modified_at) }}
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Download, FolderOpened, Refresh, Top } from '@element-plus/icons-vue'
import { robotApi, type RobotFileEntry } from '@/scripts/api'

const ROOT_PATH = '/data/testing_data'

const props = defineProps<{
  ip: string | null
}>()

const tableRef = ref<TableInstance | null>(null)
const loading = ref(false)
const downloading = ref(false)
const deleting = ref(false)
const currentPath = ref(ROOT_PATH)
const entries = ref<RobotFileEntry[]>([])
const selectedEntries = ref<RobotFileEntry[]>([])
const searchKeyword = ref('')

const filteredEntries = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return entries.value
  return entries.value.filter(entry => entry.name.toLowerCase().includes(keyword))
})

const pathSegments = computed(() => {
  const relativePath = currentPath.value.slice(ROOT_PATH.length).replace(/^\/+/, '')
  const segments = [{ label: 'testing_data', path: ROOT_PATH }]
  if (!relativePath) return segments

  let built = ROOT_PATH
  for (const part of relativePath.split('/').filter(Boolean)) {
    built += `/${part}`
    segments.push({ label: part, path: built })
  }
  return segments
})

const parentPath = computed(() => {
  if (currentPath.value === ROOT_PATH) return ROOT_PATH
  const relativeParts = currentPath.value.slice(ROOT_PATH.length).split('/').filter(Boolean)
  relativeParts.pop()
  return relativeParts.length ? `${ROOT_PATH}/${relativeParts.join('/')}` : ROOT_PATH
})

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatTime(timestamp: number | null): string {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

function clearSelection() {
  selectedEntries.value = []
  tableRef.value?.clearSelection()
}

async function refreshDirectory() {
  if (!props.ip) return
  loading.value = true
  try {
    const response = await robotApi.listTestingData(props.ip, currentPath.value)
    currentPath.value = response.data.path
    entries.value = response.data.entries
    clearSelection()
  } catch (error: any) {
    entries.value = []
    clearSelection()
    ElMessage.error('读取测试数据失败: ' + normalizeError(error))
  } finally {
    loading.value = false
  }
}

function openPath(path: string) {
  currentPath.value = path || ROOT_PATH
  searchKeyword.value = ''
  void refreshDirectory()
}

function handleEntryOpen(entry: RobotFileEntry) {
  if (entry.is_dir) openPath(entry.path)
}

function handleRowOpen(entry: RobotFileEntry) {
  handleEntryOpen(entry)
}

function handleSelectionChange(selection: RobotFileEntry[]) {
  selectedEntries.value = selection
}

function parseDownloadFilename(contentDisposition: string | undefined): string | null {
  if (!contentDisposition) return null
  const match = contentDisposition.match(/filename="([^"]+)"/i)
  return match?.[1] ?? null
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function downloadSelected() {
  if (!props.ip || selectedEntries.value.length === 0) return
  downloading.value = true
  try {
    const paths = selectedEntries.value.map(entry => entry.path)
    const response = await robotApi.downloadTestingData(props.ip, paths)
    const fallbackName = `testing-data-${props.ip.replace(/\./g, '-')}.zip`
    const filename = parseDownloadFilename(response.headers['content-disposition']) || fallbackName
    saveBlob(response.data, filename)
    ElMessage.success(`已将 ${paths.length} 项打包下载`)
  } catch (error: any) {
    ElMessage.error('下载测试数据失败: ' + normalizeError(error))
  } finally {
    downloading.value = false
  }
}

async function deleteSelected() {
  if (!props.ip || selectedEntries.value.length === 0) return
  const entriesToDelete = [...selectedEntries.value]
  const names = entriesToDelete.map(entry => entry.name)
  const preview = names.length > 5
    ? `${names.slice(0, 5).join('、')} 等 ${names.length} 项`
    : names.join('、')

  try {
    await ElMessageBox.confirm(
      `确认删除 ${preview}？删除后无法恢复。`,
      '删除测试数据',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        closeOnClickModal: false
      }
    )
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    throw error
  }

  deleting.value = true
  try {
    await robotApi.deleteTestingData(props.ip, entriesToDelete.map(entry => entry.path))
    ElMessage.success(`已删除 ${entriesToDelete.length} 项测试数据`)
    await refreshDirectory()
  } catch (error: any) {
    ElMessage.error('删除测试数据失败: ' + normalizeError(error))
  } finally {
    deleting.value = false
  }
}

watch(
  () => props.ip,
  () => {
    currentPath.value = ROOT_PATH
    entries.value = []
    searchKeyword.value = ''
    clearSelection()
    if (props.ip) void refreshDirectory()
  },
  { immediate: true }
)
</script>

<style scoped>
.testing-data-panel {
  color: #1f2a37;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.testing-data-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.testing-data-breadcrumb {
  min-width: 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.toolbar-search {
  width: 220px;
}

.selection-count {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}

.path-link,
.entry-main {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.path-link {
  color: #2563eb;
}

.testing-data-table {
  width: 100%;
}

.entry-main {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  min-width: 0;
  text-align: left;
}

.entry-main:disabled {
  cursor: default;
}

.entry-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  color: #2563eb;
  font-size: 18px;
}

.entry-name {
  overflow: hidden;
  min-width: 0;
  color: #1f2a37;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 960px) {
  .testing-data-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-actions {
    flex-wrap: wrap;
    width: 100%;
  }

  .toolbar-search {
    flex: 1;
    min-width: 180px;
    width: auto;
  }
}
</style>
