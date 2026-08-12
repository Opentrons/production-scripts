<template>
  <el-config-provider :locale="elementLocale">
    <router-view v-if="$route.meta.standalone" />
    <MainLayout v-else />
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useAppLocale } from '@/i18n'
import MainLayout from './layouts/MainLayout.vue'

const { locale } = useAppLocale()
const elementLocale = computed(() => locale.value === 'zh-CN' ? zhCn : en)
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

#app {
  width: 100%;
  height: 100vh;
}
</style>
