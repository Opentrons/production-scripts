<template>
    <el-table :data="mainElement.tableData" style="width: 100%">
        <el-table-column fixed prop="date" label="Date" width="150" />
        <el-table-column prop="auth" label="作者" width="120" />

        <el-table-column prop="robot_name" label="机器名" width="120" />
        <el-table-column prop="device_ip" label="设备IP" width="120" />
        <el-table-column prop="cmd" label="运行命令" width="600" />
        <el-table-column prop="params" label="参数" width="500" />
         <el-table-column prop="use_key" label="密钥" width="120" />
        <el-table-column prop="description" label="说明" width="120" />
        <el-table-column prop="id" label="Id" width="120" />
        <el-table-column fixed="right" label="Operations" width="160">
            <template #default>
                <el-button link type="primary" size="small" @click="handleClick">Detail</el-button>
                <el-button link type="primary" size="small">Edit</el-button>
                <el-button link type="primary" size="small" @click="handleClick">Run</el-button>
            </template>
        </el-table-column>
    </el-table>
</template>

<script lang="ts" setup>

import {ref } from 'vue'

const handleClick = () => {
    console.log('click')
}


const mainElement = defineProps({
    // 接收传值   此处的father就是父组件的自定义名称 
    tableData:{
        default: []  // 未传值时的默认值
    },
    production:{
        default: '' // 未传值时的默认值
    },
   
})

console.log(mainElement.tableData, mainElement.production)

</script>