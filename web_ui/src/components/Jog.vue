<template>
    <div class="jog">

        <el-row :gutter="20">
            <el-col :span="8">

                <div class="jogging_parameter">
                    <div>
                        <el-divider content-position="center">
                            <el-text>Jogging</el-text>
                        </el-divider>

                    </div>

                    <div class="listenning_switch">

                    </div>

                    <div class="slider-demo-block">
                        <span class="demonstration">Step-X</span>
                        <el-slider v-model="step_x" show-input :step="0.1" />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-Y</span>
                        <el-slider v-model="step_y" show-input :step="0.1" />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-Z</span>
                        <el-slider v-model="step_z" show-input :step="0.1" />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-Z-P</span>
                        <el-slider v-model="step_z_p" show-input :step="0.1" />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Step-G</span>
                        <el-slider v-model="step_g" show-input :step="0.1" />
                    </div>
                    <div class="slider-demo-block">
                        <span class="demonstration">Grip-Force</span>
                        <el-slider v-model="grip_force" show-input :step="1" />
                    </div>
                </div>

            </el-col>
            <el-col :span="8">

                <div class="robot_control">
                    <div>
                        <el-divider content-position="center">
                            <span>Robot {{ mainElement.mount }}</span>
                        </el-divider>

                    </div>
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <el-button @click="moveRelAddY" type="primary" plain :icon="Top" />
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <el-button @click="moveRelAddZ" type="primary" plain :icon="Top" />
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="0">
                            <el-button @click="moveRelSubX" type="primary" plain :icon="Back" />
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <el-button @click="moveRelAddX" type="primary" plain :icon="Right" />
                        </el-col>
                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="6" :offset="6">
                            <el-button @click="moveRelSubY" type="primary" plain :icon="Bottom" />
                        </el-col>
                        <el-col :span="6" :offset="6">
                            <el-button @click="moveRelSubZ" type="primary" plain :icon="Bottom" />
                        </el-col>
                    </el-row>

                </div>
            </el-col>

            <el-col :span="8">

                <div class="gripper_control">
                    <div>
                        <el-divider content-position="center">
                            <span>Gripper</span>
                        </el-divider>
                    </div>
                    <el-row :gutter="20">
                        <el-col :span="18">
                            <el-button type="primary" plain style="width: 100px;"> Grip </el-button>
                        </el-col>
                        <el-col :span="6" :offset="-6">
                            <el-button type="primary" plain :icon="Top" />
                        </el-col>

                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="18">

                        </el-col>
                        <el-col :span="6">

                        </el-col>

                    </el-row>
                    <el-row :gutter="20">
                        <el-col :span="18">
                            <el-button type="primary" plain style="width: 100px;"> Ungrip </el-button>
                        </el-col>
                        <el-col :span="6" :offset="-6">
                            <el-button type="primary" plain :icon="Bottom" />
                        </el-col>

                    </el-row>

                </div>

            </el-col>
        </el-row>
    </div>

</template>

<script setup lang="ts">
import { dataType } from 'element-plus/es/components/table-v2/src/common';
import { Top, Bottom, Back, Right } from '@element-plus/icons-vue'
import { ref, defineProps, reactive} from "vue"
import { isStringNumber } from 'element-plus/es/utils/types.mjs';

import {$moveRel} from '../api/hardware'




const mainElement = defineProps({
    // 接收传值   此处的father就是父组件的自定义名称 
    mount: {
        type: String,  // 数据类型
        default: "Left"  // 未传值时的默认值
    },
    device: {
        type: Number,
        default: 0
    }
})

const moveRelAddY = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": 0,
                "y": step_y.value,
                "z": 0
            }
        })
    )
    console.log(ret)

}

const moveRelAddZ = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": 0,
                "y": 0,
                "z": step_z.value
            }
        })
    )
    console.log(ret)

}

const moveRelSubX = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": -step_x.value,
                "y": 0,
                "z": 0
            }
        })
    )
    console.log(ret)

}

const moveRelAddX = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": step_x.value,
                "y": 0,
                "z": 0
            }
        })
    )
    console.log(ret)

}

const moveRelSubY = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": 0,
                "y": -step_y.value,
                "z": 0
            }
        })
    )
    console.log(ret)

}

const moveRelSubZ = async () => {
    let ret = await $moveRel(
        reactive({
            mount: mainElement.mount,
            device: mainElement.device,
            point: {
                "x": 0,
                "y": 0,
                "z": step_z.value
            }
        })
    )
    console.log(ret)

}



const step_x = ref(1)
const step_y = ref(1)
const step_z = ref(1)
const step_z_p = ref(1)
const step_g = ref(1)
const grip_force = ref(10)



</script>

<style scoped lang="scss">
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

.jog {

    padding-left: 0px;
    padding-right: 0px;

    .jogging_parameter {
        border: solid 1px rgb(226, 224, 224);
        width: auto;
        height: 350px;
        padding: 5px;

        .listenning_switch {
            padding-top: 0px;
            padding-bottom: 0px;
        }
    }

    .robot_control {
        padding: 5px;
        border: solid 1px rgb(226, 224, 224);
        width: auto;
        height: 350px;

    }

    .gripper_control {
        padding: 5px;
        border: solid 1px rgb(226, 224, 224);
        width: auto;
        height: 350px;
    }
}

.head_jog {
    text-align: center;
    padding-left: 30px;
    padding-right: 30px;
}


el-col {

    text-align: center;
}

p {
    text-align: center;
}

.slider-demo-block {
    display: flex;
    align-items: left;
}

.slider-demo-block .el-slider {
    margin-top: 0;
    margin-left: 12px;
}

.slider-demo-block .demonstration {
    font-size: 14px;
    color: var(--el-text-color-secondary);
    line-height: 44px;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 0;
}

.slider-demo-block .demonstration+.el-slider {
    flex: 0 0 70%;
}


.Arrow {
    text-align: center;
}




p {
    text-align: left;
    color: #2c3e50;

}
</style>