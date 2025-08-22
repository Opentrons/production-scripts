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
      <el-table-column prop="Production" label="产品名" width="180" sortable  />
      <el-table-column prop="TestName" label="测试名" width="320" />
      <el-table-column prop="NPI" label="NPI" width="120" />
      <el-table-column prop="Link" label="数据链接">
        <template #default="{ row }">
          <el-link type="primary" :href="row.Link" target="_blank">{{ row.LinkLabel }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="CreateTime" label="创建时间" width="180" sortable />
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
        <el-form-item label="产品名" prop="Production">
          <el-input v-model="form.Production" placeholder="请输入产品名" />
        </el-form-item>
        <el-form-item label="测试名" prop="testName">
          <el-input v-model="form.TestName" placeholder="请输入测试名" />
        </el-form-item>
         <el-form-item label="NPI" prop="NPI">
          <el-input v-model="form.NPI" placeholder="请输入NPI" />
        </el-form-item>
        <el-form-item label="链接名" prop="LinkLabel">
          <el-input v-model="form.LinkLabel" placeholder="请输入数据链接名" />
        </el-form-item>
        <el-form-item label="数据链接" prop="Link">
          <el-input v-model="form.Link" placeholder="请输入链接" />
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
import {$post} from '../../utils/request'

// 表格数据
interface TableItem {
  _id: string
  Production: string
  TestName: string
  NPI: string
  Link: string
  LinkLabel: string
  CreateTime: string
}

const tableData = ref<TableItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref('ProductionDataSummary')
const pageSize = ref(10)
const totalItems = ref(0)

// 对话框相关
const dialogVisible = ref(false)
const dialogTitle = ref('新建数据')
const form = ref({
  Production: '',
  TestName: '',
  NPI: '',
  Link: '',
  LinkLabel: '',
  CreateTime: ''
})
const formRef = ref()
const rules = {
  Production: [{ required: true, message: '请输入产品名', trigger: 'blur' }],
  TestName: [{ required: true, message: '请输入测试名', trigger: 'blur' }],
  Link: [
    { required: true, message: '请输入数据链接', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL链接', trigger: ['blur', 'change'] }
  ]
}

interface DataResponse{
  success: boolean,
  all_docs: any,
  message: string
}

// 获取数据
const fetchData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    const res: DataResponse = await $post('/api/db/read/document', {
      db_name: currentPage.value,
      document_name: 'ProductionData2025',
      limit: 100
    })
    
    tableData.value = res.all_docs
    totalItems.value = res.all_docs
    // tableData.value = res.data
    // totalItems.value = res.total
    
   
    // 模拟搜索
    let filtered = tableData
    if (searchQuery.value) {
      filtered.value = tableData.value.filter(item => 
        item.Production.toLowerCase().includes(searchQuery.value.toLowerCase())
      )
    }
    
    // // 模拟分页
    // const start = (currentPage.value - 1) * pageSize.value
    // tableData.value = filtered.slice(start, start + pageSize.value)
    // totalItems.value = filtered.length
    
  } catch (error) {
    ElMessage.error('获取数据失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  // currentPage.value = 1
  // fetchData()
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
  // currentPage.value = val
  // fetchData()
}

// 新建/编辑
const handleCreate = () => {
  dialogTitle.value = '新建数据'
  form.value = {
    Production: '',
    TestName: '',
    NPI: '',
    Link: '',
    LinkLabel: '',
    CreateTime: ''
  }
  dialogVisible.value = true
}

function getCurrentDate(): string {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0'); // 月份从0开始
  const day = String(date.getDate()).padStart(2, '0');
  
  return `${year}-${month}-${day}`;
}

const handleEdit = (row: TableItem) => {
  // dialogTitle.value = '编辑数据'
  // form.value = { ...row }
  // dialogVisible.value = true
}

interface InsertCollectionResponse {
  status_code: number
  detail: string
}

const submitForm = () => {
  formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        // 模拟API调用
        form.value.CreateTime = getCurrentDate();
        if (form.value.Link) {
        const response: InsertCollectionResponse = await $post('/api/db/insert/document', {
          "db_name": "ProductionDataSummary", "document_name": "ProductionData2025", "collections": form.value})
        console.log(response)
        ElMessage.success(form.value.Link ? '更新成功' : '创建成功')
        dialogVisible.value = false
        fetchData()}
      } catch (error) {
        ElMessage.error('操作失败: ' + error.message)
      }
    }
  })
}

// 删除
const handleDelete = (row: TableItem) => {
  // ElMessageBox.confirm(
  //   `确定要删除 "${row.product} - ${row.testName}" 的数据吗?`,
  //   '警告',
  //   {
  //     confirmButtonText: '确定',
  //     cancelButtonText: '取消',
  //     type: 'warning'
  //   }
  // ).then(async () => {
  //   try {
  //     // 模拟API调用
  //     // await $delete(`/api/data-summary/${row.id}`)
  //     ElMessage.success('删除成功')
  //     fetchData()
  //   } catch (error) {
  //     ElMessage.error('删除失败: ' + error.message)
  //   }
  // }).catch(() => {
  //   // 取消删除
  // })
}

// 计算属性 - 前端搜索过滤
const filteredTableData = computed(() => {
  if (!searchQuery.value) return tableData.value
  return tableData.value.filter(item =>
    item.Production.toLowerCase().includes(searchQuery.value.toLowerCase())
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