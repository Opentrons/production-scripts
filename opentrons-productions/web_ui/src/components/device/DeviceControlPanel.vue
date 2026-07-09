<template>
  <div class="device-control-panel">
    <div v-if="!ip" class="panel-empty">
      <el-empty description="请先选择一台设备" />
    </div>

    <template v-else>
      <section class="control-console">
        <div class="section-header">
          <div>
            <div class="section-title">设备控制</div>
            <div class="section-subtitle">常用动作与坐标移动</div>
          </div>
        </div>

        <div class="control-actions">
          <el-button type="primary" :loading="actionLoading === 'home'" @click="handleHome">
            Home
          </el-button>
          <el-button :loading="actionLoading === 'reset'" @click="handleReset">
            复位
          </el-button>
          <el-button type="danger" :loading="actionLoading === 'reboot'" @click="handleReboot">
            重启
          </el-button>
        </div>

        <div class="move-console">
          <div class="move-options">
            <label class="field-block">
              <span class="field-label">Mount</span>
              <el-segmented v-model="moveMount" :options="mountOptions" />
            </label>
            <label class="field-block">
              <span class="field-label">Target</span>
              <el-segmented v-model="moveTarget" :options="targetOptions" />
            </label>
          </div>

          <div class="axis-row">
            <label
              v-for="(axis, index) in axisLabels"
              :key="axis"
              class="axis-field"
            >
              <span class="field-label">{{ axis }}</span>
              <el-input-number v-model="movePoint[index]" :step="1" controls-position="right" />
            </label>
            <el-button
              class="move-button"
              type="primary"
              :loading="actionLoading === 'move'"
              @click="handleMove"
            >
              移动
            </el-button>
          </div>
        </div>
      </section>
    </template>

  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { robotApi } from '@/api'

const props = defineProps<{
  ip: string | null
}>()

const actionLoading = ref<'home' | 'move' | 'reset' | 'reboot' | null>(null)
const moveMount = ref('left')
const moveTarget = ref('mount')
const movePoint = ref<[number, number, number]>([100, 100, 80])
const mountOptions = ['left', 'right']
const targetOptions = ['mount', 'pipette']
const axisLabels = ['X', 'Y', 'Z'] as const

async function handleHome() {
  if (!props.ip) return
  actionLoading.value = 'home'
  try {
    await robotApi.homeRobot(props.ip, { target: 'robot' })
    ElMessage.success('Home 命令已发送')
  } catch (error: any) {
    ElMessage.error(error.message || 'Home 失败')
  } finally {
    actionLoading.value = null
  }
}

async function handleMove() {
  if (!props.ip) return
  actionLoading.value = 'move'
  try {
    await robotApi.moveRobot(props.ip, {
      target: moveTarget.value,
      mount: moveMount.value,
      point: [...movePoint.value]
    })
    ElMessage.success('移动命令已发送')
  } catch (error: any) {
    ElMessage.error(error.message || '移动失败')
  } finally {
    actionLoading.value = null
  }
}

async function handleReset() {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm('确认复位设备相关设置？', '复位确认', { type: 'warning' })
    actionLoading.value = 'reset'
    await robotApi.resetRobot(props.ip)
    ElMessage.success('复位命令已发送')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '复位失败')
    }
  } finally {
    actionLoading.value = null
  }
}

async function handleReboot() {
  if (!props.ip) return
  try {
    await ElMessageBox.confirm('确认重启设备？', '重启确认', { type: 'warning' })
    actionLoading.value = 'reboot'
    await robotApi.rebootRobot(props.ip)
    ElMessage.success('重启命令已发送')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '重启失败')
    }
  } finally {
    actionLoading.value = null
  }
}
</script>

<style scoped>
.device-control-panel {
  min-height: 240px;
  color: #1f2a37;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.control-console {
  max-width: 840px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 650;
  color: #1f2a37;
}

.section-subtitle {
  margin-top: 3px;
  color: #7b8797;
  font-size: 12px;
}

.control-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.move-console {
  display: grid;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid #eef2f7;
}

.move-options {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
}

.field-block,
.axis-field {
  display: grid;
  gap: 7px;
}

.field-label {
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.axis-row {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 8px;
}

.axis-field :deep(.el-input-number) {
  width: 132px;
}

.move-button {
  min-width: 88px;
}

@media (max-width: 720px) {
  .axis-field :deep(.el-input-number) {
    width: 100%;
  }

  .axis-field,
  .move-button {
    flex: 1 1 100%;
  }
}
</style>
