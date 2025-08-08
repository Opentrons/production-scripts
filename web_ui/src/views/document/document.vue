<template>
    <div class="document-main-box">
        <div class="document-head-box">
            <el-button type="primary" @click="newDocument"> 新建文档 </el-button>
        </div>
        <div class="document-content-box">
          <el-drawer v-model="drawer" title="编辑文档" direction="rtl" :before-close="handleClose" size="50%">
          <MyEditor v-model="editorContent" />
          <div style="text-align: right; margin-top: 20px;">
            <el-button @click="cancelEdit">取消</el-button>
            <el-button type="primary" @click="submitDocument">提交</el-button>
          </div>
        </el-drawer>
            
            <el-table :data="filterTableData" style="width: 100%">
                <el-table-column label="发布日期" prop="date" />
                <el-table-column label="作者" prop="name" />
                <el-table-column label="标题" prop="title" />
                <el-table-column label="标签" prop="tag" />
                <el-table-column align="right">
                <template #header>
                    <el-input v-model="search" size="small" placeholder="根据作者名字搜索" />
                </template>
                <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.$index, scope.row)"
                    >编辑</el-button
                    >
                    <el-button size="small" type="info" @click="handleDetail(scope.row)"
                    >详情</el-button
                    >
                    <el-button
                    size="small"
                    type="danger"
                    @click="handleDelete(scope.$index, scope.row)"
                    >删除</el-button
                    >
                </template>
                </el-table-column>
            </el-table>
        </div>
    </div>
</template>
<script lang="ts" setup>
import MyEditor from '../../components/MyEditor.vue'
import { ref, computed } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const drawer = ref(false)
const editorContent = ref('')
const currentEditingDoc = ref(null) // 当前正在编辑的文档

const newDocument = () => {
  editorContent.value = '<p>新文档内容...</p>'
  currentEditingDoc.value = null
  drawer.value = true
}

const handleEdit = (index: number, row: User) => {
  editorContent.value = row.contex
  currentEditingDoc.value = row
  drawer.value = true
}

const submitDocument = async () => {
  try {
    if (currentEditingDoc.value) {
      // 更新现有文档
      await updateDocument(currentEditingDoc.value.id, {
        contex: editorContent.value,
        // 其他需要更新的字段
      })
      ElMessage.success('文档更新成功')
    } else {
      // 创建新文档
      await createDocument({
        title: '新文档',
        contex: editorContent.value,
        // 其他必要字段
      })
      ElMessage.success('文档创建成功')
    }
    drawer.value = false
    // 刷新文档列表
    fetchDocuments()
  } catch (error) {
    ElMessage.error('提交失败: ' + error.message)
  }
}

const cancelEdit = () => {
  ElMessageBox.confirm('确定要放弃当前编辑的内容吗?', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    drawer.value = false
  }).catch(() => {
    // 取消关闭
  })
}

// 模拟API函数
const updateDocument = async (id, data) => {
  console.log('更新文档:', id, data)
  // 实际项目中替换为真实的API调用
  // await $post(`/api/documents/${id}`, data)
}

const handleClose = () => {}

const createDocument = async (data) => {
  console.log('创建文档:', data)
  // 实际项目中替换为真实的API调用
  // await $post('/api/documents', data)
}

const fetchDocuments = () => {
  console.log('获取文档列表')
  // 实际项目中替换为真实的API调用
  // tableData.value = await $get('/api/documents')
}


// document

interface User {
  date: string
  name: string
  title: string
  contex: string
  tag: string
}

const search = ref('')
const filterTableData = computed(() =>
  tableData.filter(
    (data) =>
      !search.value ||
      data.name.toLowerCase().includes(search.value.toLowerCase())
  )
)



const handleDetail = (row: User) => {
  // 跳转到详情页，并传递文章内容
  router.push({
    path: '/document_detail',
    query: {
      title: row.title,
      content: row.contex,
      author: row.name,
      date: row.date,
      tag: row.tag
    }
  })
}

const handleDelete = (index: number, row: User) => {
  console.log(index, row)
}

const tableData: User[] = [
  {
    date: '2016-05-03',
    name: 'Andy',
    title: "96孔移液器标准测试方法",
    contex: '本文档详细说明了96孔移液器的验证和性能测试流程。包含精度测试方案、体积验证方法以及高通量液体处理系统的维护要求。特别针对多通道移液器的平行性测试提供了标准化操作流程。',
    tag: "测试方法",
  },
  {
    date: '2016-05-02',
    name: 'Andy',
    title: "OT3液体处理工作站验证方案",
    contex: 'OT3自动化液体处理平台的完整测试方法。涵盖系统校准、吸头性能验证、交叉污染评估等关键指标。包括压力测试和长时间运行稳定性验证方案。',
    tag: "测试方法",
  },
  {
    date: '2016-05-04',
    name: 'Andy',
    title: "微量注射针管精度测试规范",
    contex: '针对实验室常用微量注射针管的系统化测试标准。详细描述了不同规格针管的体积准确性测试、重复性测试以及耐腐蚀性评估方法。包含常用溶剂的兼容性测试指南。',
    tag: "测试方法",
  },
  {
    date: '2016-05-01',
    name: 'Andy',
    title: "自动化移液系统综合验证方案",
    contex: '整合96孔移液器、OT3工作站和辅助针管系统的全流程测试方法。重点说明系统间兼容性测试、数据一致性验证以及异常情况处理方案。附有标准测试报告模板和验收标准。',
    tag: "测试方法",
  },
]
</script>

<style lang="scss" scoped>
.document-main-box {
    display: flex;
    height: calc(100vh - 100px);
    width: calc(100vw - 200px);
    flex-direction: column;
    padding: 20px;

    .document-head-box {
        height: 50px;
        margin-bottom: 20px;
    }

    .document-content-box {
        flex: 1;
    }
}
</style>