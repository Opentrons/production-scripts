<template>
  <div class="file-manager-container">
    <!-- 顶部连接控制栏 -->
    <div class="connection-bar">
      <el-card shadow="hover">
        <div class="connection-controls">
          <el-text class="control-label">FLEX设备</el-text>
          <el-select
            v-model="input_ip_address"
            placeholder="选择设备"
            style="width: 300px"
            filterable
            allow-create
            clearable
            @change="handleDeviceChange"
          >
            <el-option
              v-for="item in flex_list"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          
          <el-button 
            :loading="isDiscover" 
            type="primary" 
            size="small" 
            @click="fetchFlexList"
            :icon="Refresh"
          >
            刷新设备
          </el-button>
          
          <el-divider direction="vertical" />
          
          <el-text class="control-label">下载路径</el-text>
          <el-input 
            v-model="input_download_path" 
            style="width: 300px" 
            placeholder="/data/testing_data" 
            clearable
          />
        
         <el-button 
            type="primary" 
            :disabled="!isAvailable"
            @click="download_testing_data"
            :icon="Download"
            style="margin-left: 20px"
            >
            {{downloading}}
            </el-button>

            <el-button 
            type="danger" 
            :disabled="!isAvailable"
            @click=""
            :icon="Delete"
            style="margin-left: 10px"
            >
            删除目录
        </el-button>
        </div>
      </el-card>
    </div>
    
    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 文件浏览器 -->
      <el-card class="file-browser" shadow="hover">
        <template #header>
          <div class="browser-header">
            <span>文件服务器</span>
            <div class="path-navigator">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item 
                  v-for="(path, index) in currentPathParts" 
                  :key="index"
                  @click="navigateToPath(index)"
                >
                  {{ path || '根目录' }}
                </el-breadcrumb-item>
              </el-breadcrumb>
            </div>
          </div>
        </template>
        
        <el-table
          :data="fileList"
          style="width: 100%"
          height="100%"
          @row-click=""
          v-loading="isLoadingFiles"
        >
          <el-table-column prop="name" label="名称" width="400">
            <template #default="{ row }">
              <div class="file-item">
                <el-icon v-if="row.type === 'directory'">
                  <Folder />
                </el-icon>
                <el-icon v-else>
                  <Document />
                </el-icon>
                <span class="file-name">{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="size" label="大小" width="120">
            <template #default="{ row }">
              {{ row.type === 'directory' ? '-' : formatFileSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column prop="modified" label="修改时间" width="200" />
          <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              type="primary" 
              @click.stop="handleDownload(row)"
              title="下载"
            >
              下载
            </el-button>
            <el-button 
              size="small" 
              type="danger"
              @click.stop="handleDelete(row)"
              title="删除"
              style="margin-left: 8px"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 上传面板 -->
      <el-card class="upload-panel" shadow="hover">
       

        <!-- 产品名称下拉框 -->
      <span style="margin-bottom: 12px;">上传到Google Drive</span>
      <div class="upload-row">
        
        <el-select style="margin-right: 10px; width: 220px;" v-model="selectedProduct" placeholder="请选择产品" clearable>
          <el-option
            v-for="product in productList"
            :key="product.value"
            :label="product.label"
            :value="product.value"
          />
        </el-select>
        <el-select v-model="selectedTest" placeholder="请选择测试名" clearable>
          <el-option
            v-for="product in TestList"
            :key="product.value"
            :label="product.label"
            :value="product.value"
          />
        </el-select>
      </div>

      <!-- 年份和季度选择 -->
      <div class="upload-row">
        <span class="upload-label">季度：</span>
       
        <el-select v-model="selectedQuarter" placeholder="选择季度" style="width: 150px; margin-left: 2px; margin-right: 10px;">
          <el-option
            v-for="quarter in quarterList"
            :key="quarter.value"
            :label="quarter.label"
            :value="quarter.value"
            
          />
      </el-select>

      <el-tooltip content="请输入条码，如果为空，默认上传文件内所有的测试结果" placement="top">
      <el-input
        v-model="serial_number"
        type=""
        placeholder="输入条码"
       
        style="width: 200px; margin-left: auto;"
      />
    </el-tooltip>
      </div>

        
        <el-upload
          class="upload-area"
          drag
          multiple
          :action="uploadUrlGoogle"
          :headers="uploadHeaders"
          :data="uploadData"
          :before-upload="beforeUpload"
          :on-success="handleUploadSuccessGoogle"
          :on-error="handleUploadError"
          :show-file-list="false"
        
        >
          <el-icon class="el-icon--upload2"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或<em>点击上传到Google Drive</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              请选择下载的 testing_data.zip 上传
            </div>
          </template>
        </el-upload>
        
        <div class="upload-queue">
          <div v-for="(file, index) in uploadQueueGoogleDrive" :key="file.name + index" class="queue-item">
            <div class="file-info">
              <el-icon><Document /></el-icon>
              <span>{{ file.name }}</span>
            </div>
            <div class="file-progress">
              <el-progress 
                :percentage="file.progress" 
                :status="file.status"
                :stroke-width="12"
              />
            </div>
            <div class="file-actions">
              <el-button 
                v-if="file.status === 'uploading'" 
                size="small" 
                type="danger" 
                @click="cancelUpload(index)"
                :icon="Close"
                circle
              />
            </div>
          </div>
        </div>


        
        <span style="margin-bottom: 6px;">上传到文件服务器</span>
    
        
        <el-upload
          class="upload-area"
          drag
          multiple
          :action="uploadUrl"
          :headers="uploadHeaders"
          :data="uploadData"
          :before-upload="beforeUpload"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          :show-file-list="false"
    
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持上传多个文件，单文件最大100MB
            </div>
          </template>
        </el-upload>
        
        <div class="upload-queue">
          <div v-for="(file, index) in uploadQueue" :key="file.name + index" class="queue-item">
            <div class="file-info">
              <el-icon><Document /></el-icon>
              <span>{{ file.name }}</span>
            </div>
            <div class="file-progress">
              <el-progress 
                :percentage="file.progress" 
                :status="file.status"
                :stroke-width="12"
              />
            </div>
            <div class="file-actions">
              <el-button 
                v-if="file.status === 'uploading'" 
                size="small" 
                type="danger" 
                @click="cancelUpload(index)"
                :icon="Close"
                circle
              />
            </div>
          </div>
        </div>
      </el-card>

      
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue'
import { 
  DeleteFilled, 
  UploadFilled, 
  Download,
  Refresh,
  Folder,
  Document,
  Right,
  Close,
  Delete,
  Connection
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadProps, UploadUserFile } from 'element-plus'
import { $downloadFiles, $getFileList, $uploadFile } from '../../api/files'
import { $get, $post } from '../../utils/request'
import { tr } from 'element-plus/es/locales.mjs'
import {URL} from '../../utils/request'
import { List, number } from 'echarts'



// 设备连接相关
const input_ip_address = ref('')
const input_download_path = ref('/data/testing_data')
const flex_list = ref([])
const isDiscover = ref(false)
const use_secret = ref(true)
const isAvailable = ref(false)
const currentPath = ref('/')

const serial_number = ref('')

const downloading = ref('下载目录')

// 文件列表相关
const fileList = ref([])
const isLoadingFiles = ref(false)

// 上传相关
const uploadUrl = computed(() => `${URL}/api/files/upload?file=${currentPath.value}`)
const uploadHeaders = computed(() => ({
  'Authorization': use_secret.value ? 'Bearer your-secret-token' : ''
}))
const uploadData = computed(() => ({
  path: currentPath.value
}))
const uploadQueue = ref([])

// 上传到google相关
const uploadUrlGoogle = computed(() => `${URL}/api/files/upload/testing_data?file=${currentPath.value}`)
const uploadQueueGoogleDrive = ref([])



// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 当前路径拆分为部分
const currentPathParts = computed(() => {
  return currentPath.value.split('/').filter(part => part !== '')
})

// 获取设备列表
async function fetchFlexList() {
  interface ApiResponse {
    flex_group: Record<string, Record<string, any>>;
    message: string;
    success: boolean;
  }
  
  isDiscover.value = true
  flex_list.value = []
  
  try {
    const response: ApiResponse = await $get('/api/flex/discover')
    const flex_group = response.flex_group
   
    for (const key in flex_group) {
      flex_list.value.push({
        value: key,
        label: `${flex_group[key]["name"]} (${key})`
      })
    }
    const device_len = Object.keys(flex_group).length;
    if (device_len > 0)
    {
      input_ip_address.value = flex_list.value[0].value
      isAvailable.value = true
      
    }
    ElMessage.info(`找到${device_len}个设备!`)
  } catch (error) {
    console.error('Error:', error)
    ElMessage.error('设备刷新失败: ' + error.message)
  } finally {
    isDiscover.value = false
  }
}

// 设备变更处理
const handleDeviceChange = (value) => {
  if (value) {
    isAvailable.value = true;
    
  } else {
    isAvailable.value = false;
  }
}

interface ConnectResponse {
  success: boolean
}

// 连接到设备
const connectToDevice = async () => {
  try {
    isLoadingFiles.value = true
    const response: ConnectResponse =await $post(`/api/flex/connect`, {'host': input_ip_address.value})
    if (response.success)
    {ElMessage.success('连接成功')} else
    {ElMessage.error('连接失败')}
  } catch (error) {
    ElMessage.error('连接失败: ' + error.message)
    
  } finally {
    isLoadingFiles.value = false
  }
}

interface DownloadRequest {
  host: string,
  user_name: string,
  download_path: string,
  saved_name: string
}

interface DownloadResponse {
  status_code: number,
  detail: string,
}


// 下载目标OT3目录到服务器

const download_testing_data = async () => {
    ElMessage.info("开始下载")
    downloading.value = '正在下载'
    isAvailable.value = false
    const this_download: DownloadRequest = {
      host: input_ip_address.value,
      user_name: 'root',
      download_path: input_download_path.value,
      saved_name: 'testing_data'
    }
    const response = await fetch(`${URL}/api/flex/download/testing_data`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add authorization header if needed
        // 'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(this_download)

    });
    if (!response.ok) {
      const errorData = await response.json();
      ElMessage.error(`下载失败, ${errorData.detail}`)
      downloading.value = '下载目录'
      isAvailable.value = true

       
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get('Content-Disposition');
   
    const filename = contentDisposition?.match(/filename="?(.+?)"?$/)?.[1] 
    || 'download.zip';
  
    // Create download link
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    ElMessage.success("下载成功")
    downloading.value = '下载目录'
    isAvailable.value = true
    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);

}


// 刷新文件列表
const refreshFileList = async () => {

  try {
    isLoadingFiles.value = true
    const response = await $get('/api/files/fetch/filelist')
    fileList.value = response.files.map(file => ({
      ...file,
      modified: file.modified
    }))
  } catch (error) {
    ElMessage.error('获取文件列表失败: ' + error.message)
  } finally {
    isLoadingFiles.value = false
  }
}

// 进入目录
const enterDirectory = (row) => {
  if (row.type === 'directory') {
    currentPath.value = currentPath.value.endsWith('/') 
      ? currentPath.value + row.name 
      : currentPath.value + '/' + row.name
    refreshFileList()
  }
}

// 导航到路径
const navigateToPath = (index) => {
  const parts = currentPathParts.value.slice(0, index + 1)
  currentPath.value = '/' + parts.join('/')
  refreshFileList()
}

// 下载文件

interface handleDownloadRequest {
  url: string
  file_name: string
}

const handleDownload = async (row) => {
  const this_handledownload_request = {
    url: row.url,
    file_name: row.name
  }
  await $downloadFiles('/api/files/download', this_handledownload_request)


}

const handleDelete = async (row) => {
  try {
    // 1. 显示确认对话框
    await ElMessageBox.confirm(
      `确定要删除文件 "${row.name}" 吗？此操作不可恢复！`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    // 2. 用户确认后执行删除
    interface DeleteResponse {
      status_code: number
      detail: string
    }

    const deleteRequest = {
      url: row.url,
      file_name: row.name
    }

    const response: DeleteResponse = await $post('api/files/delete', deleteRequest)
    
    if (response.status_code === 200) {
      ElMessage.success("删除成功")
      await refreshFileList()
    } else {
      ElMessage.error(`删除失败: ${response.detail}`)
    }

  } catch (error) {
    // 3. 处理用户取消或删除失败的情况
    if (error !== 'cancel') {  // 不是用户主动取消的情况
      console.error('删除出错:', error)
      ElMessage.error(`删除操作出错: ${error.message || error}`)
    }
    // 用户点击取消不需要特殊处理
  }
}

//上传相关

// 产品列表
const productList = ref([
  { label: 'PVT-Robot', value: 'product_a' },
  { label: 'PVT-Robot-Ultima', value: 'product_b' },
  { label: 'PVT-Pipette', value: 'product_c' },
]);
const selectedProduct = ref('');
const selectedTest = ref('');

const TestList = ref([
  { label: 'belt-calibration-ot3', value: 'belt-calibration-ot3' },
  { label: 'robot-assembly-qc-ot3', value: 'robot-assembly-qc-ot3' },
  { label: 'stress-test-qc-ot3', value: 'stress-test-qc-ot3' },
]);


// 年份列表（动态生成最近5年）
const currentYear = new Date().getFullYear();
const yearList = ref(Array.from({ length: 5 }, (_, i) => currentYear - i));
const selectedYear = ref(currentYear);

// 季度列表

const quarterList = ref([
  { label: `${currentYear}-Q1 (1-3月)`, value: `${currentYear}-Q1` },
  { label:  `${currentYear}-Q2 (4-6月)`, value: `${currentYear}-Q2` },
  { label:  `${currentYear}-Q3 (7-9月)`, value: `${currentYear}-Q3` },
  { label:  `${currentYear}-Q4 (10-12月)`, value: `${currentYear}-Q4`},
]);
const selectedQuarter = ref('2025-Q1');


// 上传前处理
const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  if (file.size > 100 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过100MB')
    return false
  }
  
  uploadQueue.value.push({
    name: file.name,
    size: file.size,
    progress: 0,
    status: 'uploading',
    file: file
  })
  
  return true
}

// 上传成功处理
const handleUploadSuccess: UploadProps['onSuccess'] = (response, file) => {
  const index = uploadQueue.value.findIndex(item => item.name === file.name)
  if (index !== -1) {
    uploadQueue.value[index].progress = 100
    uploadQueue.value[index].status = 'success'
  }
  refreshFileList()
  ElMessage.success(`${file.name} 上传成功`)
}

// google drive 上传

const handleUploadSuccessGoogle: UploadProps['onSuccess'] = async (response, file) => {
  const index = uploadQueue.value.findIndex(item => item.name === file.name)
  if (index !== -1) {
    uploadQueue.value[index].progress = 100
    uploadQueue.value[index].status = 'success'
  }
  const status = response.status
  const files_list = response.files_list
  if (status != "success")
  {
    ElMessage.error("上传失败")
    return
  }else
  {
    interface UploadToGoogleDrive {
      product_name: string
      quarter_name: string
      sn: string
      test_name: string
      files_list: List
    }

    const upload_testing_data_request: UploadToGoogleDrive = {
      product_name: selectedProduct.value,
      quarter_name: selectedQuarter.value,
      sn: serial_number.value,
      test_name: selectedTest.value,
      files_list: files_list
    };

    const response = await $post('/api/google/drive/upload/report', upload_testing_data_request)


    ElMessage.success(`${file.name} 上传成功`)
  }
}

// 上传错误处理
const handleUploadError: UploadProps['onError'] = (error, file) => {
  const index = uploadQueue.value.findIndex(item => item.name === file.name)
  if (index !== -1) {
    uploadQueue.value[index].status = 'exception'
  }
  ElMessage.error(`${file.name} 上传失败: ${error.message}`)
}

// 取消上传
const cancelUpload = (index) => {
  // 这里应该有取消上传的逻辑
  uploadQueue.value[index].status = 'exception'
  ElMessage.warning(`已取消上传: ${uploadQueue.value[index].name}`)
}

// 初始化
onMounted(() => {
  fetchFlexList()
  refreshFileList()
})
</script>

<style lang="scss" scoped>
.file-manager-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background-color: #f5f7fa;
  
  .connection-bar {
    margin-bottom: 20px;
    
    .connection-controls {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 15px;
      
      .control-label {
        font-weight: bold;
        min-width: 60px;
      }
    }
  }
  
  .main-content {
    display: flex;
    flex: 1;
    gap: 20px;
    
    .file-browser {
      flex: 2;
      display: flex;
      flex-direction: column;
      
      .browser-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .path-navigator {
          flex: 1;
          margin-left: 20px;
          
          .el-breadcrumb {
            :deep(.el-breadcrumb__inner) {
              cursor: pointer;
              &:hover {
                color: var(--el-color-primary);
              }
            }
          }
        }
      }
      
      .file-item {
        display: flex;
        align-items: center;
        gap: 8px;
        
        .file-name {
          margin-left: 5px;
        }
      }
    }
    
    .upload-panel {
      flex: 1;
      min-width: 350px;
      display: flex;
      flex-direction: column;

      
      .upload-area {
        margin-bottom: 20px;
        
        :deep(.el-upload) {
          width: 100%;
        }
        
        .el-icon--upload {
          font-size: 50px;
          color: var(--el-color-primary);
          margin: 20px 0;
        }
        .el-icon--upload2 {
          font-size: 50px;
          color: var(--el-color-warning-light-3);
          margin: 20px 0;
        }
        
        .el-upload__text {
          font-size: 16px;
          margin-bottom: 10px;
        }
        
        .el-upload__tip {
          font-size: 12px;
          color: var(--el-text-color-secondary);
        }
      }
      
      .upload-queue {
        flex: 1;
        overflow-y: auto;
        
        .queue-item {
          padding: 10px;
          border-bottom: 1px solid var(--el-border-color-light);
          display: flex;
          flex-direction: column;
          
          .file-info {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 5px;
          }
          
          .file-progress {
            flex: 1;
          }
          
          .file-actions {
            margin-top: 5px;
            display: flex;
            justify-content: flex-end;
          }
        }
      }
    }
  }
}

.el-card {
  height: 100%;
  
  :deep(.el-card__body) {
    height: calc(100% - 60px);
    display: flex;
    flex-direction: column;
  }
}

.el-table {
  flex: 1;
}

.upload-row {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.upload-label {
  margin-right: 10px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.upload-area {
  margin-top: 20px;
}
</style>