<template>
  <div class="barcode-provision-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <section class="provision-console">
        <div class="section-header">
          <div>
            <div class="section-title">烧录条码</div>
            <div class="section-subtitle">
              通过 SSH 调用机器人上的 provision 脚本写入条码；当前条码来自设备 HTTP instruments/modules
            </div>
          </div>
          <el-button :loading="loading" :icon="Refresh" @click="loadTargets">刷新</el-button>
        </div>

        <el-alert
          v-if="targetsResponse?.simulating"
          type="info"
          :closable="false"
          title="当前为 Simulating 模式：烧录会写入本地模拟状态，不会真实 SSH"
          class="status-alert"
        />

        <el-alert
          v-for="(message, index) in targetsResponse?.errors ?? []"
          :key="`${message}-${index}`"
          type="warning"
          :closable="false"
          :title="message"
          class="status-alert"
        />

        <div class="connection-row">
          <el-tag :type="targetsResponse?.http_connected ? 'success' : 'danger'" size="small">
            HTTP {{ targetsResponse?.http_connected ? '已连接' : '未连接' }}
          </el-tag>
          <el-tag :type="targetsResponse?.ssh_connected ? 'success' : 'danger'" size="small">
            SSH {{ targetsResponse?.ssh_connected ? '已连接' : '未连接' }}
          </el-tag>
        </div>

        <section class="support-guide">
          <div class="support-guide-title">当前支持的烧录设备类型</div>
          <div class="support-guide-grid">
            <article
              v-for="item in supportedKinds"
              :key="item.kind"
              class="support-card"
              :class="{ unsupported: !item.supported }"
            >
              <div class="support-card-head">
                <span class="support-kind">{{ item.kind }}</span>
                <el-tag :type="item.supported ? 'success' : 'info'" size="small" effect="plain">
                  {{ item.supported ? '可烧录' : '暂不支持' }}
                </el-tag>
              </div>
              <div class="support-name">{{ item.name }}</div>
              <div class="support-format">{{ item.format }}</div>
              <div v-if="item.example" class="support-example">
                <span class="example-label">示例</span>
                <code>{{ item.example }}</code>
                <el-button
                  v-if="item.supported"
                  link
                  type="primary"
                  size="small"
                  @click="serialInput = item.example"
                >
                  填入
                </el-button>
              </div>
              <div v-if="item.notes" class="support-notes">{{ item.notes }}</div>
            </article>
          </div>
        </section>

        <div class="form-grid">
          <label class="field">
            <span>烧录目标</span>
            <el-select
              v-model="selectedTargetId"
              filterable
              placeholder="选择产品 / 挂载位"
              :disabled="loading || !targets.length"
            >
              <el-option
                v-for="target in targets"
                :key="target.id"
                :label="formatTargetOption(target)"
                :value="target.id"
                :disabled="!target.provisionable"
              />
            </el-select>
          </label>

          <label class="field">
            <span>当前条码</span>
            <el-input :model-value="selectedTarget?.current_serial || '—'" readonly />
          </label>

          <label class="field barcode-field">
            <span>新条码</span>
            <el-input
              v-model="serialInput"
              clearable
              placeholder="扫描或输入条码后回车烧录"
              :disabled="!canProvision"
              @keyup.enter="handleProvision"
            />
          </label>
        </div>

        <div v-if="selectedTarget" class="target-meta">
          <div>产品：{{ selectedTarget.product || '—' }}</div>
          <div>类型：{{ selectedTarget.kind }}</div>
          <div v-if="selectedTarget.mount">挂载：{{ selectedTarget.mount }}</div>
          <div v-if="selectedTarget.slot">槽位：{{ selectedTarget.slot }}</div>
          <div v-if="selectedTarget.script">脚本：{{ selectedTarget.script }}</div>
          <div v-if="selectedTarget.hint" class="hint">{{ selectedTarget.hint }}</div>
          <div v-if="!selectedTarget.provisionable" class="hint warn">
            {{ selectedTarget.hint || '该目标暂不支持烧录' }}
          </div>
        </div>

        <div class="actions-row">
          <el-button
            type="primary"
            :loading="provisioning"
            :disabled="!canProvision || !serialInput.trim()"
            @click="handleProvision"
          >
            烧录
          </el-button>
          <el-button :disabled="provisioning || !serialInput" @click="serialInput = ''">清空输入</el-button>
        </div>

        <div
          v-if="lastResult"
          class="provision-result"
          :class="{ 'is-error': !lastResult.success }"
        >
          <div class="result-header">
            <el-tag :type="lastResult.success ? 'success' : 'danger'" size="small">
              {{ lastResult.success ? '成功' : '失败' }}
            </el-tag>
            <span>{{ lastResult.message || '—' }}</span>
          </div>
          <div class="result-meta">
            <span>请求条码：{{ String(lastResult.data?.requested_serial ?? '—') }}</span>
            <span>读回条码：{{ String(lastResult.data?.current_serial ?? '—') }}</span>
            <span>exit：{{ String(lastResult.data?.exit_code ?? '—') }}</span>
          </div>
          <pre v-if="resultOutput" class="result-output">{{ resultOutput }}</pre>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  robotApi,
  type RobotActionResponse,
  type RobotBarcodeTarget,
  type RobotBarcodeTargetsResponse
} from '@/scripts/api'

const props = defineProps<{
  ip: string | null
}>()

const loading = ref(false)
const provisioning = ref(false)
const targetsResponse = ref<RobotBarcodeTargetsResponse | null>(null)
const selectedTargetId = ref('')
const serialInput = ref('')
const lastResult = ref<RobotActionResponse | null>(null)

const targets = computed(() => targetsResponse.value?.targets ?? [])
const selectedTarget = computed(
  () => targets.value.find((item) => item.id === selectedTargetId.value) ?? null
)
const sshConnected = computed(() => Boolean(targetsResponse.value?.ssh_connected))
const canProvision = computed(
  () => (
    Boolean(selectedTarget.value?.provisionable)
    && sshConnected.value
    && !loading.value
    && !provisioning.value
  )
)

const SSH_UNAVAILABLE_MESSAGE = '当前SSH未连接，烧录条码不可用，请检查设备是否安装密钥'

const supportedKinds = [
  {
    kind: 'robot',
    name: 'Robot / Flex 主机',
    supported: true,
    format: 'FLX + 版本 + YYYYMMDD + 三位序号',
    example: 'FLXA1020230605001',
    notes: '脚本：provision_robot（写 EEPROM + /var/serial）'
  },
  {
    kind: 'pipette',
    name: 'Pipette（left / right）',
    supported: true,
    format: 'PNNNVMM + 序列码（如 P1KS / P1KM / P50S / P50M / P1KH / P50H / P2HH）',
    example: 'P1KSV0120250101001',
    notes: '脚本：provision_pipette --which left|right'
  },
  {
    kind: 'gripper',
    name: 'Gripper',
    supported: true,
    format: 'GRPV + 两位型号 + 序列码',
    example: 'GRPV0120250101001',
    notes: '脚本：provision_gripper'
  },
  {
    kind: 'module',
    name: 'HEPA / UV Module',
    supported: true,
    format: 'HUV + 两位型号 + 序列码',
    example: 'HUV0120250101001',
    notes: '脚本：provision_hepauv（目前唯一支持烧录的 module）'
  },
  {
    kind: 'module*',
    name: '其它 Module',
    supported: false,
    format: 'Thermocycler / Heater-Shaker / Absorbance 等',
    example: '',
    notes: 'Opentrons 源码暂无对应工厂烧录脚本，仅展示当前条码'
  }
] as const

async function warnSshUnavailable() {
  await ElMessageBox.alert(SSH_UNAVAILABLE_MESSAGE, 'SSH 未连接', {
    type: 'warning',
    confirmButtonText: '知道了'
  })
}
const resultOutput = computed(() => {
  const data = lastResult.value?.data
  if (!data) return ''
  const stdout = typeof data.stdout === 'string' ? data.stdout.trim() : ''
  const stderr = typeof data.stderr === 'string' ? data.stderr.trim() : ''
  const command = typeof data.command === 'string' ? data.command.trim() : ''
  const parts = [
    command ? `$ ${command}` : '',
    stdout,
    stderr ? `[stderr]\n${stderr}` : ''
  ].filter(Boolean)
  return parts.join('\n\n')
})

function formatTargetOption(target: RobotBarcodeTarget): string {
  const mark = target.provisionable ? '' : '（不可烧录）'
  return `${target.label}${mark}`
}

async function loadTargets(options?: { warnSsh?: boolean }) {
  if (!props.ip) {
    targetsResponse.value = null
    selectedTargetId.value = ''
    return
  }

  const shouldWarnSsh = options?.warnSsh !== false
  loading.value = true
  try {
    const previousId = selectedTargetId.value
    const response = await robotApi.getBarcodeTargets(props.ip)
    targetsResponse.value = response.data
    const nextTargets = response.data.targets || []
    if (previousId && nextTargets.some((item) => item.id === previousId)) {
      selectedTargetId.value = previousId
    } else {
      const firstProvisionable = nextTargets.find((item) => item.provisionable)
      selectedTargetId.value = firstProvisionable?.id || nextTargets[0]?.id || ''
    }

    if (
      shouldWarnSsh
      && !response.data.simulating
      && !response.data.ssh_connected
    ) {
      await warnSshUnavailable()
    }
  } catch (error: any) {
    targetsResponse.value = null
    ElMessage.error(error?.response?.data?.detail?.message || error?.message || '加载烧录目标失败')
  } finally {
    loading.value = false
  }
}

async function handleProvision() {
  if (!props.ip || !selectedTarget.value?.provisionable) return
  if (!sshConnected.value && !targetsResponse.value?.simulating) {
    await warnSshUnavailable()
    return
  }
  const serial = serialInput.value.trim()
  if (!serial) {
    ElMessage.warning('请输入条码')
    return
  }

  const kind = selectedTarget.value.kind
  if (kind !== 'robot' && kind !== 'pipette' && kind !== 'gripper' && kind !== 'hepauv') {
    ElMessage.warning('该目标不支持烧录')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将 ${selectedTarget.value.label} 条码烧录为\n${serial}？`,
      '确认烧录',
      {
        type: 'warning',
        confirmButtonText: '烧录',
        cancelButtonText: '取消'
      }
    )
  } catch {
    return
  }

  provisioning.value = true
  lastResult.value = null
  try {
    const response = await robotApi.provisionBarcode(props.ip, {
      kind,
      serial,
      mount: selectedTarget.value.mount === 'left' || selectedTarget.value.mount === 'right'
        ? selectedTarget.value.mount
        : undefined,
      target_id: selectedTarget.value.id,
      port: targetsResponse.value?.port
    })
    lastResult.value = response.data
    if (response.data.success) {
      ElMessage.success(response.data.message || '烧录成功')
      serialInput.value = ''
      await loadTargets()
    } else {
      ElMessage.error(response.data.message || '烧录失败')
      await loadTargets()
    }
  } catch (error: any) {
    const message = error?.response?.data?.detail?.message || error?.message || '烧录请求失败'
    lastResult.value = { success: false, message, data: {} }
    ElMessage.error(message)
  } finally {
    provisioning.value = false
  }
}

watch(
  () => props.ip,
  () => {
    serialInput.value = ''
    lastResult.value = null
    void loadTargets()
  },
  { immediate: true }
)
</script>

<style scoped>
.barcode-provision-panel {
  min-height: 320px;
}

.panel-empty {
  padding: 48px 0;
}

.provision-console {
  display: grid;
  gap: 16px;
  padding: 4px 2px 12px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 650;
  color: #0f172a;
}

.section-subtitle {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}

.status-alert {
  margin: 0;
}

.connection-row {
  display: flex;
  gap: 8px;
}

.support-guide {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.support-guide-title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 650;
}

.support-guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.support-card {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.support-card.unsupported {
  background: #f8fafc;
  opacity: 0.92;
}

.support-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.support-kind {
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.support-name {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.support-format,
.support-notes {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.support-example {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.example-label {
  color: #94a3b8;
  font-size: 11px;
}

.support-example code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #ecfdf5;
  color: #166534;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) minmax(180px, 1fr) minmax(240px, 1.4fr);
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
}

.target-meta {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
}

.hint {
  color: #64748b;
}

.hint.warn {
  color: #b45309;
}

.actions-row {
  display: flex;
  gap: 10px;
}

.provision-result {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  background: #f0fdf4;
}

.provision-result.is-error {
  border-color: #fecaca;
  background: #fef2f2;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #64748b;
  font-size: 12px;
}

.result-output {
  margin: 0;
  max-height: 280px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .section-header {
    flex-direction: column;
  }
}
</style>
