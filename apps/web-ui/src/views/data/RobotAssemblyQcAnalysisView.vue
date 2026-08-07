<template>
  <div class="diagnostic-analysis-view">
    <header class="diagnostic-header">
      <div>
        <h1>Robot 诊断分析</h1>
        <p>Robot Assembly QC</p>
      </div>
    </header>

    <section class="diagnostic-placeholder">
      <el-empty description="Robot 诊断分析视图已初始化" />
    </section>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.diagnostic-analysis-view {
  min-height: 100%;
  background: #f7f9fc;
}

.diagnostic-header {
  display: flex;
  align-items: center;
  min-height: 64px;
  padding: 0 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.diagnostic-header h1 {
  margin: 0;
  color: #1f2937;
  font-size: 18px;
  font-weight: 700;
}

.diagnostic-header p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.diagnostic-placeholder {
  padding: 24px;
}
</style>
