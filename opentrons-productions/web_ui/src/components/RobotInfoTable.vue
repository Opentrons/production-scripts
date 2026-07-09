<template>
  <div class="robot-info-table">
    <el-alert
      v-if="showServiceWarning"
      type="warning"
      :closable="false"
      show-icon
      title="当前设备服务异常，获取信息失败"
      class="service-warning"
    />
    <el-alert
      v-else-if="showPartialWarning"
      type="info"
      :closable="false"
      show-icon
      title="部分详细字段未能获取，已显示可用信息"
      class="service-warning"
    />
    <el-table :data="tableRows" border stripe size="small">
      <el-table-column prop="label" label="字段" width="140" />
      <el-table-column prop="value" label="值" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RobotInfo } from '@/api'

const props = defineProps<{
  robot: RobotInfo
}>()

function formatField(value: string | undefined | null): string {
  if (value === null || value === undefined || String(value).trim() === '') {
    return 'N/A'
  }
  return String(value)
}

const showServiceWarning = computed(() => {
  return !props.robot.online || props.robot.service_status !== 'normal'
})

const showPartialWarning = computed(() => {
  return props.robot.online && props.robot.health_fetch_failed
})

const tableRows = computed(() => {
  const robot = props.robot
  return [
    { label: 'IP地址', value: formatField(robot.ip) },
    { label: '端口', value: formatField(String(robot.port)) },
    { label: '设备名称', value: formatField(robot.name) },
    { label: '序列号', value: formatField(robot.serial_number) },
    { label: '设备类型', value: formatField(robot.robot_type) },
    { label: 'Server版本', value: formatField(robot.version) },
    { label: 'API版本', value: formatField(robot.api_version) },
    { label: 'FW版本', value: formatField(robot.fw_version) },
    {
      label: '在线状态',
      value: robot.online ? '在线' : '离线'
    },
    {
      label: '服务状态',
      value: robot.service_status === 'normal' ? '正常' : '异常'
    },
    ...(robot.error ? [{ label: '错误信息', value: robot.error }] : [])
  ]
})
</script>

<style scoped>
.service-warning {
  margin-bottom: 12px;
}
</style>
