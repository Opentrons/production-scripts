<template>
  <section class="agent-panel">
    <header class="agent-panel-header">
      <div>
        <h2>{{ t('agent.knowledge.title') }}</h2>
        <p>{{ t('agent.knowledge.subtitle') }}</p>
      </div>
      <div class="agent-panel-actions">
        <button type="button" class="agent-panel-button" :disabled="loading" @click="loadDocuments">
          <RefreshCw :size="15" aria-hidden="true" />
          {{ t('common.actions.refresh') }}
        </button>
        <label class="agent-panel-button is-primary">
          <Upload :size="15" aria-hidden="true" />
          {{ t('agent.knowledge.import') }}
          <input
            class="agent-file-input"
            type="file"
            multiple
            accept=".txt,.md,.markdown,.csv,.json,.log,.tsv,text/plain"
            :disabled="importing"
            @change="onImport"
          >
        </label>
        <button type="button" class="agent-panel-button is-primary" @click="openCreate">
          <Plus :size="15" aria-hidden="true" />
          {{ t('agent.knowledge.create') }}
        </button>
      </div>
    </header>

    <div class="agent-panel-toolbar">
      <input
        v-model="query"
        type="search"
        :placeholder="t('agent.knowledge.searchPlaceholder')"
        @keydown.enter.prevent="loadDocuments"
      >
      <button type="button" class="agent-panel-button" @click="loadDocuments">{{ t('agent.knowledge.search') }}</button>
    </div>

    <p v-if="error" class="agent-panel-error">{{ error }}</p>
    <p v-else-if="!loading && !documents.length" class="agent-panel-empty">{{ t('agent.knowledge.empty') }}</p>

    <div v-loading="loading" class="agent-knowledge-list">
      <article v-for="doc in documents" :key="doc.id" class="agent-knowledge-card">
        <header>
          <div>
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.category }} · {{ doc.source }}</span>
          </div>
          <div class="agent-panel-actions">
            <button type="button" class="agent-panel-button" @click="editDocument(doc)">{{ t('common.actions.edit') }}</button>
            <button
              type="button"
              class="agent-panel-button is-danger"
              :disabled="Boolean(doc.metadata?.managed)"
              @click="removeDocument(doc)"
            >{{ t('common.actions.delete') }}</button>
          </div>
        </header>
        <p>{{ preview(doc.content) }}</p>
        <footer>
          <span v-for="tag in doc.tags.slice(0, 6)" :key="tag">{{ tag }}</span>
        </footer>
      </article>
    </div>

    <el-dialog
      v-model="editorVisible"
      :title="editingId ? t('agent.knowledge.editTitle') : t('agent.knowledge.createTitle')"
      width="640px"
    >
      <el-form label-position="top">
        <el-form-item :label="t('agent.knowledge.formTitle')">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('agent.knowledge.formCategory')">
          <el-input v-model="form.category" maxlength="80" />
        </el-form-item>
        <el-form-item :label="t('agent.knowledge.formTags')">
          <el-input v-model="form.tagsText" :placeholder="t('agent.knowledge.tagsHint')" />
        </el-form-item>
        <el-form-item :label="t('agent.knowledge.formContent')">
          <el-input v-model="form.content" type="textarea" :rows="12" maxlength="30000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">{{ t('common.actions.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveDocument">{{ t('common.actions.save') }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, RefreshCw, Upload } from '@lucide/vue'
import {
  agentKnowledgeApi,
  type KnowledgeDocument,
} from '@/scripts/modules/agent/agentWorkspaceApi'

const { t } = useI18n()
const loading = ref(false)
const importing = ref(false)
const saving = ref(false)
const error = ref('')
const query = ref('')
const documents = ref<KnowledgeDocument[]>([])
const editorVisible = ref(false)
const editingId = ref('')
const form = reactive({
  title: '',
  content: '',
  category: 'general',
  tagsText: '',
})

function preview(content: string) {
  const text = content.replace(/\s+/g, ' ').trim()
  return text.length > 180 ? `${text.slice(0, 180)}…` : text
}

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const response = await agentKnowledgeApi.list(query.value)
    documents.value = response.documents
  } catch (err: any) {
    error.value = err?.message || t('agent.knowledge.loadFailed')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = ''
  form.title = ''
  form.content = ''
  form.category = 'general'
  form.tagsText = ''
  editorVisible.value = true
}

function editDocument(doc: KnowledgeDocument) {
  editingId.value = doc.id
  form.title = doc.title
  form.content = doc.content
  form.category = doc.category || 'general'
  form.tagsText = (doc.tags || []).join(', ')
  editorVisible.value = true
}

async function saveDocument() {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning(t('agent.knowledge.required'))
    return
  }
  saving.value = true
  try {
    await agentKnowledgeApi.save({
      title: form.title.trim(),
      content: form.content.trim(),
      category: form.category.trim() || 'general',
      tags: form.tagsText.split(/[,，]/).map(item => item.trim()).filter(Boolean),
      source: editingId.value ? 'manual' : 'manual',
    }, editingId.value)
    editorVisible.value = false
    ElMessage.success(t('agent.knowledge.saved'))
    await loadDocuments()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.knowledge.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function removeDocument(doc: KnowledgeDocument) {
  if (doc.metadata?.managed) return
  try {
    await ElMessageBox.confirm(t('agent.knowledge.deleteConfirm', { title: doc.title }), t('common.actions.delete'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await agentKnowledgeApi.remove(doc.id)
    ElMessage.success(t('agent.knowledge.deleted'))
    await loadDocuments()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.knowledge.deleteFailed'))
  }
}

async function onImport(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  input.value = ''
  if (!files.length) return
  importing.value = true
  try {
    const result = await agentKnowledgeApi.importFiles(files)
    ElMessage.success(t('agent.knowledge.imported', { count: result.imported_count }))
    if (result.errors.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    await loadDocuments()
  } catch (err: any) {
    ElMessage.error(err?.message || t('agent.knowledge.importFailed'))
  } finally {
    importing.value = false
  }
}

onMounted(() => {
  void loadDocuments()
})
</script>

<style scoped>
.agent-panel {
  --agent-green: #176b5f;
  --agent-line: #dce4df;
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 24px 28px 32px;
  overflow: auto;
  background: #f7faf8;
}

.agent-panel-header,
.agent-panel-toolbar,
.agent-panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-panel-header {
  justify-content: space-between;
}

.agent-panel-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}

.agent-panel-header p,
.agent-panel-empty,
.agent-inline-hint {
  margin: 0;
  color: #6b7874;
  font-size: 13px;
}

.agent-panel-toolbar input[type='search'] {
  min-width: 0;
  flex: 1;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--agent-line);
  border-radius: 8px;
  background: #fff;
}

.agent-panel-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--agent-line);
  border-radius: 8px;
  color: #40514c;
  background: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.agent-panel-button.is-primary {
  color: #fff;
  border-color: var(--agent-green);
  background: var(--agent-green);
}

.agent-panel-button.is-danger {
  color: #a43f3f;
  border-color: #efc8c8;
}

.agent-panel-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.agent-file-input {
  display: none;
}

.agent-panel-error {
  margin: 0;
  color: #a43f3f;
}

.agent-knowledge-list,
.agent-schedule-list,
.agent-schedule-runs {
  display: grid;
  gap: 12px;
}

.agent-knowledge-card,
.agent-schedule-card,
.agent-schedule-run {
  padding: 16px;
  border: 1px solid var(--agent-line);
  border-radius: 12px;
  background: #fff;
}

.agent-knowledge-card header,
.agent-schedule-card header,
.agent-schedule-run header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.agent-knowledge-card strong,
.agent-schedule-card strong,
.agent-schedule-run strong {
  display: block;
  margin-bottom: 4px;
}

.agent-knowledge-card header span,
.agent-schedule-card header span,
.agent-schedule-run header span,
.agent-schedule-meta {
  color: #74827d;
  font-size: 12px;
}

.agent-knowledge-card p,
.agent-schedule-desc,
.agent-schedule-preview,
.agent-schedule-run p {
  margin: 0;
  color: #42514c;
  line-height: 1.55;
  white-space: pre-wrap;
}

.agent-knowledge-card footer,
.agent-schedule-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.agent-knowledge-card footer span {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef5f2;
  color: #2f6b5f;
  font-size: 11px;
}

.agent-schedule-runs h3 {
  margin: 8px 0 0;
  font-size: 15px;
}

.agent-inline-hint {
  margin-left: 10px;
}
</style>
