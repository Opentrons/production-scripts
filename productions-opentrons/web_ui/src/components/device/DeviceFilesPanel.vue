<template>
  <div v-loading="loading" class="device-files-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <div class="files-toolbar">
        <el-breadcrumb separator="/">
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
          <el-tooltip content="刷新" placement="top">
            <el-button :icon="Refresh" circle size="small" @click="refreshDirectory" />
          </el-tooltip>
          <el-tooltip content="上级目录" placement="top">
            <el-button :icon="Top" circle size="small" @click="openPath(parentPath)" />
          </el-tooltip>
        </div>
      </div>

      <div v-if="filteredEntries.length" class="file-list">
        <article
          v-for="entry in filteredEntries"
          :key="entry.path"
          class="file-row"
          @dblclick="handleRowOpen(entry)"
        >
          <button class="entry-main" type="button" @click="handleEntryClick(entry)">
            <span class="entry-icon">
              <el-icon>
                <FolderOpened v-if="entry.is_dir" />
                <Document v-else />
              </el-icon>
            </span>
            <span class="entry-copy">
              <span class="entry-name">{{ entry.name }}</span>
            </span>
          </button>

          <div class="entry-meta">
            <span>{{ entry.is_dir ? '文件夹' : formatSize(entry.size) }}</span>
            <span>{{ formatTime(entry.modified_at) }}</span>
          </div>

          <el-dropdown
            trigger="click"
            class="entry-actions"
            :class="{ 'is-open': activeActionPath === entry.path }"
            @command="(command: FileActionCommand) => handleEntryAction(command, entry)"
            @visible-change="(visible: boolean) => setActionMenuVisible(entry.path, visible)"
            @click.stop
          >
            <el-button
              :icon="MoreFilled"
              circle
              size="small"
              :loading="downloadingPath === entry.path"
              @click.stop
            />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="download" :icon="Download">
                  下载
                </el-dropdown-item>
                <el-dropdown-item command="copy_path" :icon="CopyDocument">
                  复制路径
                </el-dropdown-item>
                <el-dropdown-item v-if="!entry.is_dir" command="edit" :icon="Edit">
                  编辑
                </el-dropdown-item>
                <el-dropdown-item command="delete" :icon="Delete">
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </article>
      </div>

      <el-empty
        v-else
        :description="entries.length ? '没有匹配的文件或文件夹' : '当前目录为空'"
        :image-size="80"
      />
    </template>

    <el-dialog v-model="editorVisible" :title="`编辑文件 - ${editorFileName}`" width="720px">
      <el-input v-model="editorContent" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveFile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, Document, Download, Edit, FolderOpened, MoreFilled, Refresh, Top } from '@element-plus/icons-vue'
import { robotApi, type RobotFileEntry } from '@/api'

const props = defineProps<{
  ip: string | null
}>()

type FileActionCommand = 'download' | 'copy_path' | 'edit' | 'delete'

const loading = ref(false)
const saving = ref(false)
const downloadingPath = ref<string | null>(null)
const currentPath = ref('/')
const entries = ref<RobotFileEntry[]>([])
const editorVisible = ref(false)
const editorPath = ref('')
const editorContent = ref('')
const activeActionPath = ref('')
const searchKeyword = ref('')

const editorFileName = computed(() => editorPath.value.split('/').filter(Boolean).pop() || editorPath.value)

const filteredEntries = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return entries.value
  return entries.value.filter((entry) => entry.name.toLowerCase().includes(keyword))
})

const pathSegments = computed(() => {
  const normalized = currentPath.value || '/'
  if (normalized === '/') {
    return [{ label: 'root', path: '/' }]
  }
  const parts = normalized.split('/').filter(Boolean)
  const segments = [{ label: 'root', path: '/' }]
  let built = ''
  for (const part of parts) {
    built += `/${part}`
    segments.push({ label: part, path: built })
  }
  return segments
})

const parentPath = computed(() => {
  if (currentPath.value === '/') return '/'
  const parts = currentPath.value.split('/').filter(Boolean)
  parts.pop()
  return parts.length ? `/${parts.join('/')}` : '/'
})

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(timestamp: number | null): string {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

async function refreshDirectory() {
  if (!props.ip) return
  loading.value = true
  try {
    const response = await robotApi.listFiles(props.ip, currentPath.value)
    currentPath.value = response.data.path
    entries.value = response.data.entries
  } catch (error: any) {
    ElMessage.error('读取目录失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

function openPath(path: string) {
  currentPath.value = path || '/'
  searchKeyword.value = ''
  void refreshDirectory()
}

function handleEntryClick(entry: RobotFileEntry) {
  if (entry.is_dir) {
    openPath(entry.path)
    return
  }
  editEntry(entry)
}

function handleRowOpen(row: RobotFileEntry) {
  handleEntryClick(row)
}

function setActionMenuVisible(path: string, visible: boolean) {
  activeActionPath.value = visible ? path : ''
}

function handleEntryAction(command: FileActionCommand, entry: RobotFileEntry) {
  if (command === 'download') {
    void downloadEntry(entry)
    return
  }
  if (command === 'copy_path') {
    void copyEntryPath(entry)
    return
  }
  if (command === 'edit') {
    void editEntry(entry)
    return
  }
  void deleteEntry(entry)
}

async function copyEntryPath(entry: RobotFileEntry) {
  try {
    await navigator.clipboard.writeText(entry.path)
    ElMessage.success('路径已复制')
  } catch {
    ElMessage.error('复制路径失败')
  }
}

async function downloadEntry(entry: RobotFileEntry) {
  if (!props.ip) return
  downloadingPath.value = entry.path
  try {
    const response = await robotApi.downloadFile(props.ip, entry.path)
    const blob = response.data
    const fallbackName = entry.is_dir ? `${entry.name}.zip` : entry.name
    const filename = parseDownloadFilename(response.headers['content-disposition']) || fallbackName
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success(entry.is_dir ? '文件夹已打包下载' : '下载成功')
  } catch (error: any) {
    ElMessage.error('下载失败: ' + (error.message || '未知错误'))
  } finally {
    downloadingPath.value = null
  }
}

function parseDownloadFilename(contentDisposition: string | undefined): string | null {
  if (!contentDisposition) return null
  const match = contentDisposition.match(/filename="([^"]+)"/i)
  return match?.[1] ?? null
}

async function editEntry(entry: RobotFileEntry) {
  if (!props.ip || entry.is_dir) return
  loading.value = true
  try {
    const response = await robotApi.readFile(props.ip, entry.path)
    editorPath.value = entry.path
    editorContent.value = response.data.content
    editorVisible.value = true
  } catch (error: any) {
    ElMessage.error('读取文件失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function saveFile() {
  if (!props.ip || !editorPath.value) return
  saving.value = true
  try {
    await robotApi.writeFile(props.ip, editorPath.value, editorContent.value)
    ElMessage.success('文件已保存')
    editorVisible.value = false
    await refreshDirectory()
  } catch (error: any) {
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function deleteEntry(entry: RobotFileEntry) {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm(`确认删除 ${entry.name} ？`, '删除确认', { type: 'warning' })
    await robotApi.deleteFile(props.ip, entry.path)
    ElMessage.success('删除成功')
    await refreshDirectory()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.message || '未知错误'))
    }
  }
}

watch(
  () => props.ip,
  () => {
    currentPath.value = '/'
    entries.value = []
    searchKeyword.value = ''
    if (props.ip) {
      void refreshDirectory()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.device-files-panel {
  color: #1f2a37;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.files-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-search {
  width: 220px;
}

.path-link,
.entry-main {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.path-link {
  color: #2563eb;
}

:global(.entry-link) {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
}

.file-list {
  display: grid;
  border-top: 1px solid #e6ebf2;
}

.file-row {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(220px, 260px) auto;
  align-items: center;
  gap: 12px;
  min-height: 42px;
  padding: 6px 0;
  border-bottom: 1px solid #e6ebf2;
  transition: background-color 0.18s ease;
}

.file-row:hover {
  background: #f8fbff;
}

.entry-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  text-align: left;
}

.entry-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  color: #2563eb;
  font-size: 18px;
  flex-shrink: 0;
}

.entry-copy {
  display: grid;
  min-width: 0;
}

.entry-name {
  overflow: hidden;
  color: #1f2a37;
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entry-meta {
  color: #6b7280;
  font-size: 12px;
}

.entry-meta {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  white-space: nowrap;
}

.entry-actions {
  justify-self: end;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.16s ease;
}

.file-row:hover .entry-actions,
.entry-actions.is-open {
  opacity: 1;
  pointer-events: auto;
}

@media (max-width: 900px) {
  .files-toolbar,
  .file-row {
    align-items: stretch;
    grid-template-columns: 1fr;
  }

  .files-toolbar {
    flex-direction: column;
  }

  .toolbar-actions,
  .entry-meta,
  .entry-actions {
    justify-content: flex-start;
  }

  .toolbar-actions {
    width: 100%;
  }

  .toolbar-search {
    flex: 1;
    min-width: 0;
    width: auto;
  }
}
</style>
