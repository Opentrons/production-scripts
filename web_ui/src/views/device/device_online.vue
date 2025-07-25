<template>
  <div class="device-online-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="header">
          <h2></h2>
          <el-tag type="success">在线设备: {{ onlineDevices.length }}</el-tag>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="device-list">
      <el-col 
        v-for="device in onlineDevices" 
        :key="device.id" 
        :xs="12" :sm="8" :md="6" :lg="6" :xl = '4'
      >
        <el-card class="device-card" shadow="hover">
          <div class="device-status">
            <el-tag :type="device.status === 'online' ? 'success' : 'danger'" size="small">
              <span class="status-dot" :class="device.status"></span>
              {{ device.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </div>
          
          <div class="device-image">
            <el-image 
              :src="deviceImage" 
              fit="contain" 
              class="robot-image"
              style="display: inline-block;" 
            >
              <template #error>
                <div class="image-error">
                  <el-icon><Picture /></el-icon>
                  <span>图片加载失败</span>
                </div>
              </template>
            </el-image>
          </div>
          
          <div class="device-info">
            <h3 class="device-name">{{ device.name }}</h3>
            <div class="info-item">
              <el-icon><Link /></el-icon>
              <span>IP: {{ device.ip }}</span>
            </div>
            <div class="info-item">
              <el-icon><Cpu /></el-icon>
              <span>型号: {{ device.model }}</span>
            </div>
            <div class="info-item">
              <el-icon><Clock /></el-icon>
              <span>上线时间: {{ device.lastOnline }}</span>
            </div>
          </div>
          
          <div class="device-actions">
            <el-button type="primary" size="small" @click="showDetail(device)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
            <el-button type="warning" size="small" @click="controlDevice(device)">
              <el-icon><Connection /></el-icon>
              控制
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import deviceImage from '../../assets/device_flex.png'
import { ref } from 'vue'
import { 
  Picture, Link, Cpu, Clock, View, Connection 
} from '@element-plus/icons-vue'


// 模拟在线设备数据
const onlineDevices = ref([
  {
    id: 1,
    name: '机械臂-01',
    ip: '192.168.1.101',
    model: 'UR5e',
    status: 'online',
    image: 'https://example.com/robot1.jpg',
    lastOnline: '2023-05-15 14:30:22'
  },
  {
    id: 2,
    name: 'AGV小车-02',
    ip: '192.168.1.102',
    model: 'MiR250',
    status: 'online',
    image: 'https://example.com/robot2.jpg',
    lastOnline: '2023-05-15 14:25:10'
  },
  {
    id: 3,
    name: '协作机器人-03',
    ip: '192.168.1.103',
    model: 'UR10',
    status: 'online',
    image: 'https://example.com/robot3.jpg',
    lastOnline: '2023-05-15 14:28:45'
  },
  {
    id: 4,
    name: '机械臂-04',
    ip: '192.168.1.104',
    model: 'UR3',
    status: 'offline',
    image: 'https://example.com/robot4.jpg',
    lastOnline: '2023-05-14 18:15:33'
  },
  {
    id: 1,
    name: '机械臂-01',
    ip: '192.168.1.101',
    model: 'UR5e',
    status: 'online',
    image: 'https://example.com/robot1.jpg',
    lastOnline: '2023-05-15 14:30:22'
  },
  
])

const showDetail = (device) => {
  console.log('查看设备详情:', device)
  // 这里可以跳转到详情页或打开弹窗
}

const controlDevice = (device) => {
  console.log('控制设备:', device)
  // 这里可以跳转到控制页面
}
</script>

<style scoped lang="scss">
.device-online-container {
  padding: 20px;
  background-color: #f5f7fa;
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h2 {
      color: #303133;
      margin: 0;
    }
  }
  
  .device-list {
    margin-top: 10px;
  }
  
  .device-card {
    margin-bottom: 20px;
    position: relative;
    transition: all 0.3s;
    
    &:hover {
      transform: translateY(-5px);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
    }
    
    .device-status {
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 2;
      
      .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 5px;
        
        &.online {
          background-color: #67c23a;
        }
        
        &.offline {
          background-color: #f56c6c;
        }
      }
    }
    
    .device-image {
      height: 180px;
      display: flex;
      justify-content: center;
      align-items: center;
      background-color: #f0f2f5;
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 15px;
      
      .robot-image {
        width: 100%;
        height: 100%;
      }
      
      .image-error {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: #909399;
        
        .el-icon {
          font-size: 40px;
          margin-bottom: 10px;
        }
      }
    }
    
    .device-info {
      margin-bottom: 15px;
      
      .device-name {
        margin: 0 0 10px 0;
        color: #303133;
        font-size: 16px;
        text-align: center;
      }
      
      .info-item {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
        font-size: 13px;
        color: #606266;
        
        .el-icon {
          margin-right: 8px;
          color: #909399;
        }
      }
    }
    
    .device-actions {
      display: flex;
      justify-content: space-between;
      
      .el-button {
        flex: 1;
        margin: 0 5px;
        
        .el-icon {
          margin-right: 5px;
        }
      }
    }
  }
}
</style>