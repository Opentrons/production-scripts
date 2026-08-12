<template>
  <div class="home-view">
    <el-empty :description="t('home.placeholder')" />
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<style scoped>
.home-view {
  height: 100%;
  display: grid;
  place-items: center;
  background: #f5f7fa;
}
</style>
