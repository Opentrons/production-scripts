<template>
  <div class="tf-folder-report-links">
    <TestFailureReportLink v-for="report in reports" :key="failureReportLinkKey(report)" :report="report" :show-identity="reports.length > 1" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FailureDevice } from '@/scripts/api/testFailures'
import { failureReportLinkKey, failureReportLinkTargets } from '@/scripts/utils/failureReportLinks'
import TestFailureReportLink from './TestFailureReportLink.vue'

const props = defineProps<{ device: FailureDevice }>()
const reports = computed(() => failureReportLinkTargets(props.device.reports))
</script>
