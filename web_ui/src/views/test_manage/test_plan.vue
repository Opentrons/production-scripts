<template>
  <div class="test-plan-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight: bolder;">每日测试计划 <em>（注意：请每日及时更新，保证数据自动上传！）</em></span>
          <el-button type="primary" :icon="Plus" @click="handleCreate">
            新建测试产品
          </el-button>
        </div>
      </template>

      <!-- 产品数据表格 -->
      <el-table :data="tableData" style="width: 100%" empty-text="暂无测试产品数据">
        <el-table-column prop="date" label="日期" min-width="50" />
        <el-table-column prop="product" label="产品" min-width="60" />
        <el-table-column prop="test_name" label="测试内容" min-width="100" />
        <el-table-column prop="barcode" label="条码" min-width="80" />
        <el-table-column prop="fixture_name" label="测试工装名" min-width="50" />
        <el-table-column prop="fixture_ip" label="测试工装IP" min-width="50" />
        <el-table-column prop="auto_upload" label="数据状态" min-width="50" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.$index, scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.$index, scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog :title="dialogTitle" v-model="dialogVisible" width="500px">
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="100px">
        <el-form-item label="产品名称" prop="product">
          <el-select v-model="production_value" placeholder="请选择产品">
            <el-option v-for="item in product_options" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="条码" prop="barcode">
          <el-input v-model="formData.barcode" placeholder="请输入条码" />
        </el-form-item>
        <el-form-item label="测试内容" prop="test_name">
          <el-select v-model="test_name_value" multiple placeholder="请选择测试内容">
            <el-option v-for="item in test_name_options" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试工装名" prop="fixture_name">
          <el-input v-model="formData.fixture_name" placeholder="请输入工装名称" />
        </el-form-item>
        <el-form-item label="测试工装IP" prop="fixture_ip">
          <el-input v-model="formData.fixture_ip" placeholder="请输入测试工装IP地址" />
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
import { ref, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox, FormInstance, FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  add_test_plan, fetch_test_plan, TestPlanInterface,
  delete_test_plan
} from '../../api/require_db'
import { $get_current_time, delay } from '../../utils/utils'
import { da } from 'element-plus/es/locales.mjs'


// 新建测试计划
const production_value = ref('');

const product_options = [
  {
    value: 'Robot',
    label: 'OT3',
  },
  {
    value: 'P200CH96',
    label: '96CH Pipette 200',
  },
  {
    value: 'P1000CH96',
    label: '96CH Pipette 1000',
  },
  {
    value: 'P50S',
    label: '1CH Pipette P50',
  },
  {
    value: 'P1000S',
    label: '1CH Pipette P1000',
  },
  {
    value: 'P50M',
    label: '8CH Pipette P50',
  },
   {
    value: 'P1000M',
    label: '8CH Pipette P1000',
  }
];

const test_name_value = ref('')

const test_name_options = [
  {
    value: 'assembly_qc',
    label: 'AssemblyQCTest',
  },
  {
    value: 'z_stage',
    label: 'ZStageTest',
  },
  {
    value: 'level_test',
    label: 'LevelingTest',
  },
  {
    value: 'gantry_stress',
    label: 'GantryStressTest',
  },
  {
    value: 'xy_belt_calibration',
    label: 'XYBeltCalibrationTest',
  },
  {
    value: 'speed_current_test',
    label: 'Speed&CurrentTest',
  },
  {
    value: 'grav_test',
    label: 'GravimetricTest',
  }
]




// 表格数据
const tableData = ref<TestPlanInterface[]>(
  []
);

// 对话框控制
const dialogVisible = ref(false)
const dialogTitle = ref('新建测试产品')
const isEditing = ref(false)
const editingIndex = ref(-1)

// 表单数据和校验规则
const formRef = ref<FormInstance>()
const formData = ref<TestPlanInterface>({
  date: '',
  product: '',
  test_name: '',
  barcode: '',
  fixture_name: '',
  fixture_ip: '',
  auto_upload: ''
})

const formRules = reactive<FormRules>({
  product: [
    { required: true, message: '请输入产品名称', trigger: 'blur' }
  ],
  barcode: [
    { required: true, message: '请输入条码', trigger: 'blur' }
  ],
  fixture_name: [
    { required: true, message: '请输入Robot Name', trigger: 'blur' }
  ],
  test_name: [
    { required: true, message: '请输入测试内容', trigger: 'blur' }
  ],
  fixture_ip: [
    { required: false, message: '请输入测试工装IP', trigger: 'blur' },
    { pattern: /^(\d{1,3}\.){3}\d{1,3}$/, message: '请输入有效的IP地址', trigger: 'blur' }
  ]
})


interface DataInterface {
  success: boolean
  all_docs: TestPlanInterface[]
}

const refreshTableData = () => {
  fetch_test_plan()
    .then((data: DataInterface) => {
      tableData.value = data.all_docs.map(item => ({
        ...item,
        auto_upload: item.auto_upload === true || item.auto_upload === 'True'
          ? '已上传'
          : '未上传'
      }));

    })
    .catch((error: Error) => {
      console.error('异步操作发生错误:', error);
    });
};

// 打开新建对话框
const handleCreate = () => {
  dialogTitle.value = '新建测试产品'
  isEditing.value = false
  editingIndex.value = -1

  // 重置表单数据
  Object.assign(formData, {
    date: '',
    product: '',
    test_name: '',
    barcode: '',
    fixture_name: '',
    fixture_ip: '',
    auto_upload: ''
  })

  dialogVisible.value = true
  nextTick(() => {
    if (formRef.value) {
      formRef.value.clearValidate()
    }
  })
}

// 打开编辑对话框
const handleEdit = (index: number, row: TestPlanInterface) => {
  dialogTitle.value = '编辑测试产品'
  isEditing.value = true
  editingIndex.value = index

  // 填充表单数据
  Object.assign(formData.value, { ...row })
  production_value.value = row.product
  // test_name_value.value = row.test_name
  
  

  dialogVisible.value = true
  nextTick(() => {
    if (formRef.value) {
      formRef.value.clearValidate('fixture_ip')
    }
  })
}

// 提交表单
const submitForm = async () => {

  // update the formTable
  formData.value.product = production_value.value
  formData.value.test_name = test_name_value.value
  const current_date = $get_current_time()
  formData.value.date = current_date
  formData.value.auto_upload = false

  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (valid) {
      if (isEditing.value) {
        // 更新现有产品
        // tableData.value[editingIndex.value] = { ...formData }
        ElMessage.success('产品更新成功')


      }
      else {
        // 添加新产品
        add_test_plan(formData.value)
          .then(data => {
            if (data.status_code == 200) {
              ElMessage.success('产品添加成功')
              refreshTableData()
            } else {
              ElMessage.error("产品添加失败: " + data.detail)
            }
          })
          .catch(error => {
            ElMessage.error("添加新产品出现异常: ", error)
          })


      }
      dialogVisible.value = false
    }
  } catch (error) {
    console.log('表单验证失败', error)
  }
}



// 删除产品
const handleDelete = (index: number, row: TestPlanInterface) => {
  ElMessageBox.confirm(
    `确定要删除产品"${row.product}"吗?`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(() => {
      delete_test_plan({ require_key: { barcode: row.barcode } })
        .then(data => {
          console.log(data)
          if (data.status_code == 200) {
            ElMessage.success('产品删除成功')
            refreshTableData()
          } else {
            const detail = data.detail
            ElMessage.error('产品删除失败 ' + detail)
          }

        })
        .catch(error => {
          console.error('异步操作发生错误:', error);
          // 在这里处理错误
        });


    })
    .catch(() => {
      // 取消删除
    })
}

// run
refreshTableData()

</script>

<style scoped>
.test-plan-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.box-card {
  margin-bottom: 20px;
}
</style>