<template>
    <div class="device-control-main-box">
        <div class="device-control-head-box">

            <el-text>设备IP地址</el-text>
            <el-input v-model="input_ip_address" style="width: 240px; height: 25px;" placeholder="输入设备地址" />
            <el-text>Mount</el-text>
            <el-select v-model="mount_value" placeholder="Select" style="width: 240px" size="small">
                <el-option v-for="item in mount_options" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-text>使用密钥</el-text>
            <el-switch v-model="use_secret" />

            <el-button type="primary" color="#409EFF" plain @click="clickConnect"> {{ connect_status }}
            </el-button>

        </div>


        <div class="device-control-content-box">
            <el-row :gutter="20">
                <el-col :span="15">
                    <div class="grid-content control-box-left">
                        <div class="control-main-box">
                            <Jog :mount="mount_value" :device="device_id"></Jog>

                        </div>
                    </div>

                </el-col>
                <el-col :span="9">
  <el-card class="control-card setting-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <el-icon><Setting /></el-icon>
        <span class="panel-title">Device Setting</span>
      </div>
    </template>

    <div class="setting-content">
      <!-- Home 控制区 -->
      <div class="control-group">
        <el-button 
          type="primary" 
          class="action-btn"
          @click="homeHandel"
          :loading="home_button_loading"
        >
          <el-icon><HomeFilled /></el-icon>
          Home
        </el-button>
        
        <el-select 
          v-model="axis_value" 
          placeholder="Select Axis"
          class="axis-select"
          
        >
          <el-option 
            v-for="item in axis_options" 
            :key="item.value" 
            :label="item.label"
            :value="item.value" 
          />
        </el-select>
        
        <el-button 
          type="warning" 
          class="action-btn"
          @click=""
        >
          <el-icon><Refresh /></el-icon>
          重启服务
        </el-button>
      </div>

      <!-- MoveToPoint 控制区 - 单行布局 -->
      <div class="control-group move-to-group">
        <el-button 
          type="success" 
          class="move-to-btn"
          @click="moveToPointHandel"
          :loading="moveToPoint_button_loading"
        >
          <el-icon><Position /></el-icon>
          MoveToPoint
        </el-button>
        
        <div class="coordinate-inputs">
          <div class="coordinate-item">
            <span class="axis-label">X</span>
            <el-input-number 
              v-model="moveToX" 
              :min="0" 
              :max="1000" 
              :step="1"
              size="small"
              controls-position="right"
            />
          </div>
          
          <div class="coordinate-item">
            <span class="axis-label">Y</span>
            <el-input-number 
              v-model="moveToY" 
              :min="0" 
              :max="1000" 
              :step="1"
              size="small"
              controls-position="right"
            />
          </div>
          
          <div class="coordinate-item">
            <span class="axis-label">Z</span>
            <el-input-number 
              v-model="moveToZ" 
              :min="0" 
              :max="1000" 
              :step="1"
              size="small"
              controls-position="right"
            />
          </div>
        </div>
      </div>
    </div>
  </el-card>
</el-col>
            </el-row>

        </div>

    </div>


</template>

<script lang="ts" setup>

import { ref, reactive } from "vue"
import type { EpPropMergeType } from "element-plus/es/utils/vue/props/types"
import Jog from '../../components/Jog.vue'
import { $build_connect, $home, $moveTo } from '../../api/hardware'
import { ElMessage } from 'element-plus'

const input_ip_address = ref("192.168.6.11")
let use_secret = ref(true)
const connect_type = ref("default")
const connect_status = ref("连接设备")
const home_button_loading = ref(false)
const moveToPoint_button_loading = ref(false)

const moveToX = ref(100)
const moveToY = ref(100)
const moveToZ = ref(300)


let device_id: number = 0

const mount_value = ref('Left')

const mount_options = [
    {
        value: 'Left',
        label: 'Left',
    },
    {
        value: 'Right',
        label: 'Right',
    },
    {
        value: 'Gripper',
        label: 'Gripper',
    },
    {
        value: 'Null',
        label: 'Null',
    }
]


const axis_value = ref('All')

const axis_options = [
    {
        value: 'all',
        label: 'All',
    },
    {
        value: 'x',
        label: 'X',
    },
    {
        value: 'y',
        label: 'Y',
    },
    {
        value: 'z',
        label: 'Z Left',
    },
    {
        value: 'r',
        label: 'P Right',
    },
    {
        value: 'p_l',
        label: 'Plunger Left',
    },
    {
        value: 'p_r',
        label: 'Plunger Right',
    },
    {
        value: 'z_g',
        label: 'Z Gripper',
    },
    {
        value: 'g',
        label: 'G Gripper',
    }
]

const clickConnect = async () => {
    if (connect_status.value == "连接设备") {
        let ret = await $build_connect(
            reactive({
                ip: input_ip_address.value

            }))

        if (ret.success) {
            ElMessage({
                message: ret.message,
                type: 'success'
            })
            connect_status.value = "断开连接"
            connect_type.value = "Primary"
            device_id = ret.device_id

        }
        else {
            ElMessage.error("新建失败" + ret.message)
        }
    }
    else {
        connect_status.value = "连接设备"
        connect_type.value = "Primary"
    }

}

const homeHandel = async () => {
    home_button_loading.value = true
    let ret = await $home(
        reactive({
            device: device_id,
            axis: "all"
        })
    )
    if (ret.success) {
        home_button_loading.value = false
    }
}

const moveToPointHandel = async () => {
    console.log(`move to (${moveToX.value} ${moveToY.value} ${moveToZ.value})`)
    let ret = await $moveTo(
        reactive({
            device: device_id,
            mount: mount_value.value,
            point: {
                "x": moveToX.value,
                "y": moveToY.value,
                "z": moveToZ.value
            }
        })
    )
    console.log(ret)

}



</script>

<style lang="scss" scoped>
.device-control-main-box {

    display: flex;
    flex-direction: column;


    .device-control-head-box {
        height: 40px;
        display: flex;
        align-items: center;
    }

    .device-control-head-box>*+* {
        margin-left: 20px;
    }

    .device-control-content-box {
        height: 100vh;
        margin-top: 10px;

        .el-row {
            margin-bottom: 20px;
        }

        .el-row:last-child {
            margin-bottom: 0;
        }

        .el-col {
            border-radius: 4px;
        }

        .grid-content {
            border-radius: 4px;
            min-height: 36px;

        }

        .control-box-left {
            height: 100vh;
        }

        .parameter-box-right {

            border: solid 1px rgb(226, 224, 224);
            height: 100vh;
        }

    }

.setting-card {
  border-top: 4px solid #e6a23c;
  height: 100%;
  
  .card-header {
    .panel-title {
      font-size: 18px;
      font-weight: 600;
      color: #409eff; // 与前面面板一致的蓝色
      margin-left: 8px;
    }
  }
  
  .setting-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding: 15px;
  }
  
  .control-group {
    display: flex;
    align-items: center;
    gap: 12px;
    
    &.move-to-group {
      display: flex;
      align-items: center;
      gap: 15px;
    }
  }
  
  .action-btn, .move-to-btn {
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    
    .el-icon {
      font-size: 16px;
    }
  }
  
  .axis-select {
    width: 160px;
  }
  
  .coordinate-inputs {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-grow: 1;
  }
  
  .coordinate-item {
    display: flex;
    align-items: center;
    gap: 5px;
    
    .axis-label {
      font-weight: bold;
      color: #606266;
      min-width: 18px;
      font-size: 14px;
    }
    
    .el-input-number {
      width: 90px;
      
      &.is-controls-right {
        ::v-deep .el-input__inner {
          padding-left: 5px;
          padding-right: 35px;
        }
      }
    }
  }
}
}
</style>