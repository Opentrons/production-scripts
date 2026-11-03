<template>
  <ul v-if="entries.length" class="tf-summary-list tf-failure-summary">
    <li v-for="(item, index) in entries" :key="index" class="tf-summary-item" :class="{ 'has-name': item.name }">
      <strong v-if="item.name" class="tf-summary-name">{{ item.name }}</strong>
      <span v-if="item.detail" class="tf-summary-detail">{{ item.detail }}</span>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ items: string[] }>()

const entries = computed(() => props.items.map(item => {
  const prefix = item.match(/^\s*(?:\[([^\]\r\n]+)\]|【([^】\r\n]+)】)/)
  const name = (prefix?.[1] || prefix?.[2] || '').trim()
  return prefix && name
    ? { name, detail: item.slice(prefix[0].length).trimStart() }
    : { name: '', detail: item }
}))
</script>
