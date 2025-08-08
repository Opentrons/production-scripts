<template>
  <div class="document-detail-container">
    <el-page-header @back="goBack" content="文档详情" />
    
    <div class="document-header">
      <h1>{{ document.title }}</h1>
      <div class="meta-info">
        <span>作者: {{ document.author }}</span>
        <span>发布日期: {{ document.date }}</span>
        <el-tag type="info">{{ document.tag }}</el-tag>
      </div>
    </div>
    
    <div class="document-content">
      <div class="content-box">
        {{ document.content }}
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const document = ref({
  title: '',
  content: '',
  author: '',
  date: '',
  tag: ''
})

onMounted(() => {
  // 从路由参数中获取文档内容
  document.value = {
    title: route.query.title as string,
    content: route.query.content as string,
    author: route.query.author as string,
    date: route.query.date as string,
    tag: route.query.tag as string
  }
})

const goBack = () => {
  router.go(-1)
}
</script>

<style lang="scss" scoped>
.document-detail-container {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
  
  .document-header {
    margin: 30px 0;
    border-bottom: 1px solid #eee;
    padding-bottom: 20px;
    
    h1 {
      font-size: 28px;
      margin-bottom: 15px;
    }
    
    .meta-info {
      display: flex;
      align-items: center;
      gap: 20px;
      color: #666;
      font-size: 14px;
    }
  }
  
  .document-content {
    margin-top: 30px;
    
    .content-box {
      line-height: 1.8;
      font-size: 16px;
      white-space: pre-line;
    }
  }
}
</style>