<template>
  <section class="system-image-panel">
    <div class="image-heading">
      <div>
        <h3>{{ t('devices.systemImages.title') }}</h3>
        <p>{{ t('devices.systemImages.description') }}</p>
      </div>
      <div class="image-actions">
        <el-button :icon="Refresh" :loading="loading" @click="refresh">{{ t('devices.systemImages.refresh') }}</el-button>
        <el-button :icon="Download" @click="downloadVisible = true">{{ t('devices.systemImages.download') }}</el-button>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-form label-position="top" class="image-form">
      <el-form-item :label="t('devices.systemImages.image')">
        <el-select v-model="selectedImage" filterable :placeholder="t('devices.systemImages.selectImage')" style="width: 100%">
          <el-option v-for="image in images" :key="image.name" :value="image.name"
            :label="`${image.name} · ${(image.size / 1024 / 1024).toFixed(1)} MiB`" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('devices.systemImages.port')">
        <el-input-number v-model="port" :min="1" :max="65535" :controls="false" />
      </el-form-item>
    </el-form>
    <p v-if="!loading && !images.length" class="image-hint">{{ t('devices.systemImages.empty') }}</p>
    <div class="target-list">
      <span>{{ t('devices.systemImages.targets', { count: ips.length }) }}</span>
      <el-tag v-for="ip in ips" :key="ip" effect="plain">{{ ip }}</el-tag>
    </div>
    <div class="image-actions install-actions">
      <el-button type="primary" :loading="submitting" :disabled="!canInstall" @click="install">
        {{ t('devices.systemImages.install') }}
      </el-button>
      <span class="image-hint">{{ t('devices.systemImages.restartHint') }}</span>
    </div>
    <h3>{{ t('devices.systemImages.tasks') }}</h3>
    <el-table :data="tasks" row-key="id" stripe :empty-text="t('common.empty')">
      <el-table-column type="expand">
        <template #default="{ row }"><pre class="task-logs">{{ row.logs.join('\n') || row.message }}</pre></template>
      </el-table-column>
      <el-table-column :label="t('devices.systemImages.target')" min-width="135">
        <template #default="{ row }">{{ row.ip || t('devices.systemImages.downloadTask') }}</template>
      </el-table-column>
      <el-table-column prop="image" :label="t('devices.systemImages.image')" min-width="245" show-overflow-tooltip />
      <el-table-column :label="t('devices.systemImages.status')" width="115">
        <template #default="{ row }">
          <el-tag :type="row.status === 'failed' ? 'danger' : row.status === 'success' ? 'success' : 'info'">
            {{ t(`devices.systemImages.states.${row.status}`) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.systemImages.progress')" min-width="250">
        <template #default="{ row }">
          <div class="task-stage">{{ t(`devices.systemImages.stages.${row.stage}`) }}</div>
          <el-progress v-if="row.progress !== null" :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : row.status === 'success' ? 'success' : undefined" />
          <div class="task-message">{{ row.message }}</div>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="downloadVisible" :title="t('devices.systemImages.download')" width="min(600px, 94vw)" append-to-body>
      <el-form label-position="top" @submit.prevent="download">
        <el-form-item :label="t('devices.systemImages.url')" required>
          <el-input v-model="downloadUrl" :placeholder="t('devices.systemImages.urlPlaceholder')" clearable :disabled="downloading" />
        </el-form-item>
        <p class="image-hint">{{ t('devices.systemImages.destination', { path: directory }) }}</p>
      </el-form>
      <template #footer>
        <el-button @click="downloadVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="downloading" :disabled="!downloadUrl.trim()" @click="download">{{ t('devices.systemImages.startDownload') }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Download, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemImagesApi, type SystemImage, type SystemImageTask } from '@/scripts/api/systemImages'
import { useAppLocale } from '@/i18n'

const props = withDefaults(defineProps<{ ips: string[]; active?: boolean }>(), { active: true })
const { t } = useAppLocale()
const images = ref<SystemImage[]>([])
const tasks = ref<SystemImageTask[]>([])
const directory = ref('/opt/ot3-system')
const selectedImage = ref('')
const port = ref(31950)
const error = ref('')
const loading = ref(false)
const submitting = ref(false)
const downloadVisible = ref(false)
const downloadUrl = ref('')
const downloading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false
const canInstall = computed(() => props.ips.length > 0 && images.value.some(image => image.name === selectedImage.value)
  && !tasks.value.some(task => task.kind === 'install' && ['queued', 'running'].includes(task.status) && props.ips.includes(task.ip)))

function message(cause: any): string {
  const detail = cause?.response?.data?.detail
  return (typeof detail === 'string' ? detail : detail?.message) || cause?.message || t('errors.unknown')
}
async function refresh() {
  if (loading.value || disposed) return
  clearTimeout(timer)
  loading.value = true
  try {
    const [library, history] = await Promise.all([systemImagesApi.list(), systemImagesApi.tasks()])
    images.value = library.data.images
    directory.value = library.data.directory
    tasks.value = history.data.tasks
    if (selectedImage.value && !images.value.some(image => image.name === selectedImage.value)) selectedImage.value = ''
    error.value = ''
  } catch (cause) {
    error.value = message(cause)
  } finally {
    loading.value = false
    if (!disposed && props.active) timer = setTimeout(refresh, 2500)
  }
}
async function install() {
  const ips = [...props.ips]
  const image = selectedImage.value
  const targetPort = port.value
  if (!canInstall.value || submitting.value) return
  submitting.value = true
  try {
    await ElMessageBox.confirm(t('devices.systemImages.confirm', { image, ips: ips.join(', ') }), t('devices.systemImages.title'), {
      type: 'warning', confirmButtonText: t('devices.systemImages.install'), cancelButtonText: t('common.actions.cancel'),
    })
    const response = await systemImagesApi.install(ips, image, targetPort)
    tasks.value = [...response.data.tasks, ...tasks.value]
    ElMessage.success(t('devices.systemImages.queued'))
    await refresh()
  } catch (cause) {
    if (cause !== 'cancel' && cause !== 'close') ElMessage.error(message(cause))
  } finally {
    submitting.value = false
  }
}
async function download() {
  if (downloading.value) return
  downloading.value = true
  try {
    const response = await systemImagesApi.download(downloadUrl.value.trim())
    tasks.value = [response.data, ...tasks.value]
    downloadVisible.value = false
    downloadUrl.value = ''
    ElMessage.success(t('devices.systemImages.downloadQueued'))
    await refresh()
  } catch (cause) {
    ElMessage.error(message(cause))
  } finally {
    downloading.value = false
  }
}
watch(() => props.active, active => {
  clearTimeout(timer)
  if (active) void refresh()
}, { immediate: true })
onBeforeUnmount(() => { disposed = true; clearTimeout(timer) })
</script>

<style scoped>
.system-image-panel { padding: 8px 2px 28px; min-width: 0; }
.image-heading, .image-actions, .target-list { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.image-heading { justify-content: space-between; margin-bottom: 20px; }
h3 { font-size: 14px; font-weight: 650; color: #1f2a37; margin: 12px 0; }
.image-heading p, .image-hint { color: #6b7280; font-size: 12px; }
.image-form { display: grid; grid-template-columns: minmax(250px, 1fr) 150px; gap: 16px; max-width: 880px; margin-top: 20px; }
.target-list { font-size: 12px; color: #6b7280; }
.install-actions { margin: 18px 0 28px; }
.task-logs { padding: 16px; margin: 0; background: #111827; color: #dbeafe; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 300px; overflow: auto; }
.task-stage { font-size: 12px; font-weight: 600; }
.task-message { font-size: 12px; color: #6b7280; overflow-wrap: anywhere; }
@media (max-width: 650px) { .image-form { grid-template-columns: 1fr; } }
</style>
