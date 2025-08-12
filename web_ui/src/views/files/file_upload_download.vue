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
          type="info" 
          :disabled="!isConnected"
          @click="connectToDevice"
          :icon="Connection"
          style="margin-left: 20px"
          >
          连接设备
          </el-button>
          
         <el-button 
            type="primary" 
            :disabled="!isConnected"
            @click="download_testing_data"
            :icon="Download"
            style="margin-left: 20px"
            >
            下载目录
            </el-button>

            <el-button 
            type="danger" 
            :disabled="!isConnected"
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
            <span>上传目录浏览器</span>
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
          <el-table-column prop="name" label="名称" width="300">
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
          <el-table-column prop="modified" label="修改时间" width="180" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button 
                v-if="row.type === 'file'"
                size="small" 
                type="primary" 
                @click.stop="downloadFile()"
                :icon="Download"
              >
                下载
              </el-button>
              <el-button 
                v-else
                size="small" 
                type="info"
                @click.stop=""
                :icon="Right"
              >
                进入
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 上传面板 -->
      <el-card class="upload-panel" shadow="hover">
        <template #header>
          <span>上传文件</span>
        </template>
        
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
          :disabled="!isConnected"
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

// 设备连接相关
const input_ip_address = ref('')
const input_download_path = ref('/data/testing_data')
const flex_list = ref([])
const isDiscover = ref(false)
const use_secret = ref(true)
const isConnected = ref(false)
const currentPath = ref('/')

// 文件列表相关
const fileList = ref([])
const isLoadingFiles = ref(false)

// 上传相关
const uploadUrl = computed(() => `/api/files/upload?device=${input_ip_address.value}&path=${currentPath.value}`)
const uploadHeaders = computed(() => ({
  'Authorization': use_secret.value ? 'Bearer your-secret-token' : ''
}))
const uploadData = computed(() => ({
  path: currentPath.value
}))
const uploadQueue = ref([])

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
      input_ip_address.value = flex_list.value[0]
      
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
    isConnected.value = true;
    
  } else {
    isConnected.value = false;
  }
}

interface ConnectResponse {
  success: boolean
}

// 连接到设备
const connectToDevice = async () => {
  try {
    isLoadingFiles.value = true
    const response: ConnectResponse =await $post('/api/flex/connect', {'host': input_ip_address.value})
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
  success: boolean,
  message: string,
  dir: string
}


// 下载目标OT3目录到服务器

const download_testing_data = async () => {
    ElMessage.info("开始下载")
    
    const this_download: DownloadRequest = {
      host: input_ip_address.value,
      user_name: 'root',
      download_path: input_download_path.value,
      saved_name: 'testing_data'
    }
    console.log(this_download)
    const response = await fetch('/api/flex/download/testing_data', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add authorization header if needed
        // 'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(this_download)

    });
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get('Content-Disposition');
    const filename = contentDisposition?.match(/filename="?(.+?)"?$/)?.[1] 
      || this_download.saved_name || 'download.zip';

    // Create download link
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    
    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);


}

// 刷新文件列表
const refreshFileList = async () => {
  // if (!input_ip_address.value) return
  
  // try {
  //   isLoadingFiles.value = true
  //   const response = await $getFileList(input_ip_address.value, currentPath.value)
  //   fileList.value = response.files.map(file => ({
  //     ...file,
  //     modified: new Date(file.modified).toLocaleString()
  //   }))
  // } catch (error) {
  //   ElMessage.error('获取文件列表失败: ' + error.message)
  // } finally {
  //   isLoadingFiles.value = false
  // }
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
const downloadFile = async () => {
  // try {
  //   ElMessage.info(`开始下载`)
  //   // await $downloadFiles()
  //   ElMessage.success(`下载完成: ${file.name}`)
  // } catch (error) {
  //   ElMessage.error(`下载失败: ${error.message}`)
  // }
}

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
</style>