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
  scrollbar-width: none;
  -ms-overflow-style: none;
}

*::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

/* Keep the compact global chrome, but make dense data surfaces scrollable. */
:where(
  .el-overlay,
  .el-overlay-dialog,
  .el-dialog,
  .el-dialog__body,
  .el-table,
  .el-table__body-wrapper,
  .el-table__header-wrapper,
  .el-table__footer-wrapper,
  [class*="table-wrap"],
  [class*="table-shell"]
) {
  scrollbar-width: auto;
  -ms-overflow-style: auto;
}

:where(
  .el-overlay,
  .el-overlay-dialog,
  .el-dialog,
  .el-dialog__body,
  .el-table,
  .el-table__body-wrapper,
  .el-table__header-wrapper,
  .el-table__footer-wrapper,
  [class*="table-wrap"],
  [class*="table-shell"]
)::-webkit-scrollbar {
  width: 8px;
  height: 8px;
  display: block;
}

:where(
  .el-overlay,
  .el-overlay-dialog,
  .el-dialog,
  .el-dialog__body,
  .el-table,
  .el-table__body-wrapper,
  .el-table__header-wrapper,
  .el-table__footer-wrapper,
  [class*="table-wrap"],
  [class*="table-shell"]
)::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 8px;
  background: #aebbc1;
  background-clip: padding-box;
}

:where(
  .el-overlay,
  .el-overlay-dialog,
  .el-dialog,
  .el-dialog__body,
  .el-table,
  .el-table__body-wrapper,
  .el-table__header-wrapper,
  .el-table__footer-wrapper,
  [class*="table-wrap"],
  [class*="table-shell"]
)::-webkit-scrollbar-track {
  background: #edf1f3;
}

.el-dialog__body {
  max-height: min(70vh, 720px);
  overflow: auto;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

#app {
  width: 100%;
  height: 100vh;
}
</style>
