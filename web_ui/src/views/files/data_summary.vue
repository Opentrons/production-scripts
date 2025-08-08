<template>
  <div class="data-summary-container">
    <div class="header">
      <h2>数据汇总表</h2>
      <div class="action-bar">
        <el-input
          v-model="searchQuery"
          placeholder="按产品名搜索"
          clearable
          style="width: 300px; margin-right: 20px;"
          @clear="handleSearchClear"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button :icon="Search" @click="handleSearch" />
          </template>
        </el-input>
        <el-button type="primary" @click="handleCreate" :icon="Plus">新建数据</el-button>
      </div>
    </div>

    <el-table
      :data="filteredTableData"
      border
      stripe
      style="width: 100%"
      v-loading="loading"
    >
      <el-table-column prop="product" label="产品名" width="180" sortable />
      <el-table-column prop="testName" label="测试名" width="180" />
      <el-table-column prop="dataLink" label="数据链接">
        <template #default="{ row }">
          <el-link type="primary" :href="row.dataLink" target="_blank">{{ row.dataLink }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="createTime" label="创建时间" width="180" sortable />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="totalItems"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="50%"
    >
      <el-form :model="form"  ref="formRef" label-width="100px">
        <el-form-item label="产品名" prop="product">
          <el-input v-model="form.product" placeholder="请输入产品名" />
        </el-form-item>
        <el-form-item label="测试名" prop="testName">
          <el-input v-model="form.testName" placeholder="请输入测试名" />
        </el-form-item>
        <el-form-item label="数据链接" prop="dataLink">
          <el-input v-model="form.dataLink" placeholder="请输入数据链接" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 表格数据
interface TableItem {
  id: string
  product: string
  testName: string
  dataLink: string
  createTime: string
}

const tableData = ref<TableItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const totalItems = ref(0)

// 对话框相关
const dialogVisible = ref(false)
const dialogTitle = ref('新建数据')
const form = ref({
  id: '',
  product: '',
  testName: '',
  dataLink: ''
})
const formRef = ref()
// const rules = {
//   product: [{ required: true, message: '请输入产品名', trigger: 'blur' }],
//   testName: [{ required: true, message: '请输入测试名', trigger: 'blur' }],
//   dataLink: [
//     { required: true, message: '请输入数据链接', trigger: 'blur' },
//     { type: 'url', message: '请输入有效的URL链接', trigger: ['blur', 'change'] }
//   ]
// }

// 获取数据
const fetchData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    // const res = await $get('/api/data-summary', {
    //   page: currentPage.value,
    //   size: pageSize.value,
    //   search: searchQuery.value
    // })
    // tableData.value = res.data
    // totalItems.value = res.total
    
    // 模拟数据
    const mockData: TableItem[] = [
      {
        id: '1',
        product: '智能手机X',
        testName: '电池续航测试',
        dataLink: 'https://example.com/data/smartphone-x-battery',
        createTime: '2023-05-15 10:30'
      },
      {
        id: '2',
        product: '智能手表Y',
        testName: '防水性能测试',
        dataLink: 'https://example.com/data/watch-y-waterproof',
        createTime: '2023-05-16 14:20'
      },
      {
        id: '3',
        product: '笔记本电脑Z',
        testName: '散热性能测试',
        dataLink: 'https://example.com/data/laptop-z-thermal',
        createTime: '2023-05-17 09:15'
      },
      {
        id: '4',
        product: '智能手机X',
        testName: '屏幕显示测试',
        dataLink: 'https://example.com/data/smartphone-x-display',
        createTime: '2023-05-18 11:45'
      }
    ]
    
    // 模拟搜索
    let filtered = mockData
    if (searchQuery.value) {
      filtered = mockData.filter(item => 
        item.product.toLowerCase().includes(searchQuery.value.toLowerCase())
      )
    }
    
    // 模拟分页
    const start = (currentPage.value - 1) * pageSize.value
    tableData.value = filtered.slice(start, start + pageSize.value)
    totalItems.value = filtered.length
    
  } catch (error) {
    ElMessage.error('获取数据失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchData()
}

const handleSearchClear = () => {
  searchQuery.value = ''
  handleSearch()
}

// 分页
const handleSizeChange = (val: number) => {
  pageSize.value = val
  fetchData()
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  fetchData()
}

// 新建/编辑
const handleCreate = () => {
  dialogTitle.value = '新建数据'
  form.value = {
    id: '',
    product: '',
    testName: '',
    dataLink: ''
  }
  dialogVisible.value = true
}

const handleEdit = (row: TableItem) => {
  dialogTitle.value = '编辑数据'
  form.value = { ...row }
  dialogVisible.value = true
}

const submitForm = () => {
  formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        // 模拟API调用
        // if (form.value.id) {
        //   await $put(`/api/data-summary/${form.value.id}`, form.value)
        //   ElMessage.success('更新成功')
        // } else {
        //   await $post('/api/data-summary', form.value)
        //   ElMessage.success('创建成功')
        // }
        
        ElMessage.success(form.value.id ? '更新成功' : '创建成功')
        dialogVisible.value = false
        fetchData()
      } catch (error) {
        ElMessage.error('操作失败: ' + error.message)
      }
    }
  })
}

// 删除
const handleDelete = (row: TableItem) => {
  ElMessageBox.confirm(
    `确定要删除 "${row.product} - ${row.testName}" 的数据吗?`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      // 模拟API调用
      // await $delete(`/api/data-summary/${row.id}`)
      ElMessage.success('删除成功')
      fetchData()
    } catch (error) {
      ElMessage.error('删除失败: ' + error.message)
    }
  }).catch(() => {
    // 取消删除
  })
}

// 计算属性 - 前端搜索过滤
const filteredTableData = computed(() => {
  if (!searchQuery.value) return tableData.value
  return tableData.value.filter(item =>
    item.product.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

// 初始化
onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.data-summary-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.action-bar {
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.el-link {
  word-break: break-all;
}
</style>