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

            <el-button :type="connect_type" color="#409EFF" plain @click="clickConnect"> {{ connect_status }}
            </el-button>

        </div>


        <div class="device-control-content-box">
            <el-row :gutter="20">
                <el-col :span="16">
                    <div class="grid-content control-box-left">
                        <div class="control-main-box">
                            <Jog :mount="mount_value" :device="device_id"></Jog>

                        </div>
                    </div>

                </el-col>
                <el-col :span="8">
                    <div class="grid-content parameter-box-right">

                        <div>
                            <el-divider content-position="center">
                                <el-text>Device Setting</el-text>
                            </el-divider>
                        </div>

                        <div style="display: flex; align-items: center; margin-bottom: 20px;">
                            <el-button style="margin-left: 10px;" type="primary" size="small" @click="homeHandel"
                                :loading="home_button_loading"> Home </el-button>
                            <el-select v-model="axis_value" placeholder="Select"
                                style="width: 240px; margin-left: 10px;" size="small">
                                <el-option v-for="item in axis_options" :key="item.value" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                            <el-button style="margin-left: 10px;" type="primary" size="small"> 重启服务 </el-button>



                        </div>
                        <div style="display: flex; align-items: center; margin-bottom: 20px;">
                            <el-button style="margin-left: 10px;" type="primary" size="small" @click="moveToPointHandel"
                                :loading="moveToPoint_button_loading"> MoveToPoint </el-button>
                            <el-text style="margin-left: 10px;">X</el-text>
                            <el-input v-model="moveToX" style="margin-left: 10px; width: 60px" size="small"></el-input>
                            <el-text style="margin-left: 10px;">Y</el-text>
                            <el-input v-model="moveToY" style="margin-left: 10px; width: 60px" size="small"></el-input>
                            <el-text style="margin-left: 10px;">Z</el-text>
                            <el-input v-model="moveToZ" style="margin-left: 10px; width: 60px" size="small"></el-input>



                        </div>
                    </div>


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
}
</style>