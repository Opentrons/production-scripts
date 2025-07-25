<template>
  <div class="robot-control-container">
    <el-row :gutter="20" class="control-panel">
      <!-- 机器人控制区域 -->
      <el-col :span="12">
        <el-card class="control-card robot-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Position /></el-icon>
              <span>Robot {{ mainElement.mount }} Control</span>
            </div>
          </template>
          
          <div class="direction-pad">
            <div class="direction-row">
              <el-button 
                @click="moveRelAddY" 
                class="direction-btn" 
                type="primary" 
                :icon="Top" 
                circle
              />
              <el-button 
                @click="moveRelAddZ" 
                class="direction-btn" 
                type="primary" 
                :icon="Top" 
                circle
              />
            </div>
            <div class="direction-row">
              <el-button 
                @click="moveRelSubX" 
                class="direction-btn" 
                type="primary" 
                :icon="Back" 
                circle
              />
              <div class="center-display">
                <span class="axis-label">X: {{ currentPos.x }}</span>
                <span class="axis-label">Y: {{ currentPos.y }}</span>
                <span class="axis-label">Z: {{ currentPos.z }}</span>
              </div>
              <el-button 
                @click="moveRelAddX" 
                class="direction-btn" 
                type="primary" 
                :icon="Right" 
                circle
              />
            </div>
            <div class="direction-row">
              <el-button 
                @click="moveRelSubY" 
                class="direction-btn" 
                type="primary" 
                :icon="Bottom" 
                circle
              />
              <el-button 
                @click="moveRelSubZ" 
                class="direction-btn" 
                type="primary" 
                :icon="Bottom" 
                circle
              />
            </div>
          </div>

          <div class="step-control">
            <span class="step-label">Step Size:</span>
            <el-slider 
              v-model="stepSize" 
              :min="0.1" 
              :max="10" 
              :step="0.1" 
              show-input
            />
          </div>
        </el-card>
      </el-col>

      <!-- 夹爪控制区域 -->
      <el-col :span="12">
        <el-card class="control-card gripper-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Collection /></el-icon>
              <span>Gripper Control</span>
            </div>
          </template>
          
          <div class="gripper-panel">
            <div class="force-indicator">
              <el-progress 
                type="circle" 
                :percentage="gripForce" 
                :color="customColors"
              />
              <span class="force-label">Grip Force: {{ gripForce }}%</span>
            </div>
            
            <div class="gripper-buttons">
              <el-button 
                type="success" 
                class="grip-btn" 
                @click="grip"
              >
                <el-icon><FolderOpened /></el-icon>
                Grip
              </el-button>
              <el-button 
                type="danger" 
                class="grip-btn" 
                @click="ungrip"
              >
                <el-icon><Folder /></el-icon>
                Ungrip
              </el-button>
            </div>
            
            <div class="position-control">
              <el-button 
                @click="moveGripperUp" 
                type="primary" 
                :icon="Top" 
                circle
              />
              <el-button 
                @click="moveGripperDown" 
                type="primary" 
                :icon="Bottom" 
                circle
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { Top, Bottom, Back, Right, Position, Collection, FolderOpened, Folder } from '@element-plus/icons-vue'
import { ref, reactive } from "vue"
import { $moveRel } from '../api/hardware'

const mainElement = defineProps({
  mount: {
    type: String,
    default: "Left"
  },
  device: {
    type: Number,
    default: 0
  }
})

// 状态管理
const currentPos = reactive({
  x: 0,
  y: 0,
  z: 0
})

const stepSize = ref(1)
const gripForce = ref(50)
const customColors = [
  { color: '#f56c6c', percentage: 20 },
  { color: '#e6a23c', percentage: 40 },
  { color: '#5cb87a', percentage: 60 },
  { color: '#1989fa', percentage: 80 },
  { color: '#6f7ad3', percentage: 100 }
]

// 运动控制方法
const moveRelAddY = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: 0, y: stepSize.value, z: 0 }
  })
  currentPos.y += stepSize.value
  console.log(ret)
}

const moveRelAddZ = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: 0, y: 0, z: stepSize.value }
  })
  currentPos.z += stepSize.value
  console.log(ret)
}

const moveRelSubX = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: -stepSize.value, y: 0, z: 0 }
  })
  currentPos.x -= stepSize.value
  console.log(ret)
}

const moveRelAddX = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: stepSize.value, y: 0, z: 0 }
  })
  currentPos.x += stepSize.value
  console.log(ret)
}

const moveRelSubY = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: 0, y: -stepSize.value, z: 0 }
  })
  currentPos.y -= stepSize.value
  console.log(ret)
}

const moveRelSubZ = async () => {
  const ret = await $moveRel({
    mount: mainElement.mount,
    device: mainElement.device,
    point: { x: 0, y: 0, z: -stepSize.value }
  })
  currentPos.z -= stepSize.value
  console.log(ret)
}

// 夹爪控制方法
const grip = () => {
  gripForce.value = Math.min(100, gripForce.value + 10)
}

const ungrip = () => {
  gripForce.value = Math.max(0, gripForce.value - 10)
}

const moveGripperUp = () => {
  console.log("Gripper moved up")
}

const moveGripperDown = () => {
  console.log("Gripper moved down")
}
</script>

<style scoped lang="scss">
.robot-control-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: 100vh;
}

.control-panel {
  margin-bottom: 20px;
}

.control-card {
  height: 500px;
  border-radius: 12px;
  transition: all 0.3s ease;
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
  }
  
  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 600;
    color: #409eff;
  }
}

.robot-card {
  border-top: 4px solid #409eff;
}

.gripper-card {
  border-top: 4px solid #67c23a;
}

.direction-pad {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 15px;
}

.direction-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 30px;
  width: 100%;
}

.direction-btn {
  width: 60px;
  height: 60px;
  font-size: 24px;
}

.center-display {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 150px;
  height: 80px;
  background-color: #f0f2f5;
  border-radius: 8px;
  margin: 0 20px;
}

.axis-label {
  font-size: 14px;
  color: #606266;
  margin: 2px 0;
}

.step-control {
  margin-top: 20px;
  padding: 0 30px;
  
  .step-label {
    display: block;
    margin-bottom: 10px;
    font-size: 14px;
    color: #909399;
  }
}

.gripper-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-around;
  height: 400px;
}

.force-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  
  .force-label {
    font-size: 16px;
    font-weight: 500;
    color: #67c23a;
  }
}

.gripper-buttons {
  display: flex;
  gap: 30px;
  
  .grip-btn {
    width: 120px;
    height: 50px;
    font-size: 16px;
  }
}

.position-control {
  display: flex;
  gap: 20px;
  
  .el-button {
    width: 50px;
    height: 50px;
  }
}
</style>