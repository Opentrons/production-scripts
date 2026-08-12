<template>
  <div class="robot-info-table">
    <el-alert
      v-if="showServiceWarning"
      type="warning"
      :closable="false"
      show-icon
      :title="t('devices.infoTable.serviceWarning')"
      class="service-warning"
    />
    <el-alert
      v-else-if="showPartialWarning"
      type="info"
      :closable="false"
      show-icon
      :title="t('devices.infoTable.partialWarning')"
      class="service-warning"
    />
    <el-table :data="tableRows" border stripe size="small">
      <el-table-column prop="label" :label="t('devices.infoTable.field')" width="140" />
      <el-table-column prop="value" :label="t('devices.infoTable.value')" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RobotInfo } from '@/scripts/api'
import { useAppLocale } from '@/i18n'

const { t } = useAppLocale()

const props = defineProps<{
  robot: RobotInfo
}>()

function formatField(value: string | undefined | null): string {
  if (value === null || value === undefined || String(value).trim() === '') {
    return 'N/A'
  }
  return String(value)
}

function formatApiLevel(minVersion: string | undefined, maxVersion: string | undefined): string {
  return `${formatField(minVersion)} - ${formatField(maxVersion)}`
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
    { label: t('devices.infoTable.ip'), value: formatField(robot.ip) },
    { label: t('devices.infoTable.port'), value: formatField(String(robot.port)) },
    { label: t('devices.infoTable.name'), value: formatField(robot.name) },
    { label: t('devices.infoTable.serial'), value: formatField(robot.serial_number) },
    { label: t('devices.infoTable.type'), value: formatField(robot.robot_model ?? robot.robot_type) },
    { label: 'API Level', value: formatApiLevel(robot.min_api_version, robot.max_api_version) },
    { label: t('devices.infoTable.apiVersion'), value: formatField(robot.api_version) },
    { label: t('devices.infoTable.firmwareVersion'), value: formatField(robot.fw_version) },
    {
      label: t('devices.infoTable.onlineStatus'),
      value: robot.online ? t('common.status.online') : t('common.status.offline')
    },
    {
      label: t('devices.infoTable.serviceStatus'),
      value: robot.service_status === 'normal' ? t('common.status.healthy') : t('common.status.abnormal')
    },
    ...(robot.error ? [{ label: t('devices.infoTable.error'), value: robot.error }] : [])
  ]
})
</script>

<style scoped>
.service-warning {
  margin-bottom: 12px;
}
</style>
