<template>
    <div class="device-status-main-box">
        <div class="device-status-head-box">
            <el-text>设备名称</el-text>
            <el-input v-model="input_device_name" style="width: 240px" placeholder="Please input" />
            <el-text>设备地址</el-text>
            <el-input v-model="input_device_address" style="width: 240px" placeholder="Please input" />
            <el-text>标签</el-text>
            <div>
                <el-tag v-for="tag in dynamicTags" :key="tag" closable :disable-transitions="false"
                    @close="handleClose(tag)">
                    {{ tag }}
                </el-tag>
                <el-input v-if="inputVisible" ref="InputRef" v-model="inputValue" class="w-20" size="small"
                    @keyup.enter="handleInputConfirm" @blur="handleInputConfirm" />
                <el-button v-else class="button-new-tag" size="small" @click="showInput">
                    + New Tag
                </el-button>
            </div>

            <el-button type="primary" @click="addDevice" > 添加设备 </el-button>
        </div>
        <div class="device-status-content-box">

            <el-table :data="filterTableData" style="width: 100%">
                <el-table-column label="添加日期" prop="date" />
                <el-table-column label="作者" prop="auth" />
                <el-table-column label="设备名称" prop="device_name" />
                <el-table-column label="设备地址" prop="device_address" />
                <el-table-column label="标签" prop="device_tag" />
                <el-table-column label="在线状态" prop="online" />
                <el-table-column align="right">
                    <template #header>
                        <el-input v-model="search" size="small" placeholder="根据标签搜索" />
                    </template>
                    <template #default="scope">
                        <el-button size="small" @click="handleEdit(scope.$index, scope.row)" :loading='editLoading' >Ping</el-button>
                        <el-button size="small" type="danger"
                            @click="handleDelete(scope.$index, scope.row)" :loading="deleteLoading">删除</el-button>
                    </template>
                </el-table-column>
            </el-table>



        </div>
       
        <div style="margin-top: 20px; margin-left: 0px">
            <el-button type="primary" @click="output_table" >
                导出<el-icon class="el-icon--right"><Upload /></el-icon>
            </el-button>
        </div>

    </div>



</template>

<script lang="ts" setup>
import { ref, Ref, computed, reactive, onBeforeMount} from 'vue';
import { $get_current_time } from '../../utils/utils'
import {ElMessage, ElMessageBox} from 'element-plus'
import * as XLSX from 'xlsx';
import {saveAs} from 'file-saver';

// device

interface User {
    date: string
    auth: string
    device_name: string
    device_address: string
    device_tag: string
    online: string
}

const search = ref('')

const tableData: Ref<User[]> = ref([])

const freshDevice = async ()  => {
    
    let ret = await $get_device()
    tableData.value = ret.device
   
}

const output_table = async() =>{
    const worksheet = XLSX.utils.json_to_sheet(tableData.value);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1');
    const excelBuffer = XLSX.write(workbook, {
    bookType: 'xlsx',
    type: 'array'
    });
    const blob = new Blob([excelBuffer], { type: 'application/vnd.ms-excel' });
    saveAs(blob, `table-${$get_current_time()}.xlsx`); // 下载文件 文件名


}



const addDevice = async () => {
    const date = $get_current_time()
    const auth = "default"
    let ret = await $add_device(reactive({
        date: date,
        auth: auth,
        device_name: input_device_name.value,
        device_address: input_device_address.value,
        device_tag: dynamicTags.value.toString(),
        online: "Unknow"
    }))
    
    if (ret.success) {
        ElMessage.success(ret.message)
        freshDevice()
    }else{
        ElMessage.error(ret.message)
    }
   

}

onMounted(() => {

    freshDevice()
})


const filterTableData =  computed( () => 

    tableData.value.filter(
        (data) =>
            !search.value ||
            data.device_tag.toLowerCase().includes(search.value.toLowerCase())
    )
   
)


const handleEdit = async (index: number, row: User) => {
   
    let ret = await $testOnline(
        reactive({
            ipaddress: row.device_address
        })
    )
    if (ret.success) {
        row.online = ret.message
    }
}

const handleDelete = async (index: number, row: User) => {
    const ip_address = row.device_address
    ElMessageBox.confirm('确认删除吗?')
    .then( async () => {
        let ret = await $remove_device(reactive({
        device_address: ip_address
        
    }))
        if (ret.success) {
            freshDevice()
        }
        else {
            ElMessage.error(ret.message)
        }
    })
    .catch(() => {
      // catch error
      
    })
}





// head and tag

import { nextTick, onMounted } from 'vue'
import { ElInput } from 'element-plus'
import { $testOnline } from '../../api/hardware';
import { $get_device, $add_device, $remove_device} from '../../api/device'

const input_device_name = ref('96通道老化')
const input_device_address = ref("192.168.6.11")

const inputValue = ref('')
const dynamicTags = ref(['工装', '诊断', '老化'])
const inputVisible = ref(false)
const InputRef = ref<InstanceType<typeof ElInput>>()

// edit /delete
const editLoading = ref(false)
const deleteLoading = ref(false)


const handleClose = (tag: string) => {
    dynamicTags.value.splice(dynamicTags.value.indexOf(tag), 1)
}

const showInput = () => {
    inputVisible.value = true
    nextTick(() => {
        InputRef.value!.input!.focus()
    })
}

const handleInputConfirm = () => {
    if (inputValue.value) {
        dynamicTags.value.push(inputValue.value)
    }
    inputVisible.value = false
    inputValue.value = ''
}



</script>

<style lang="scss" scoped>
.device-status-main-box {
    display: flex;
    height: 100vh -100px;
    width: 100vw -200px;
    flex-direction: column;

    .device-status-head-box {
        display: flex;
        height: 50px;
        align-items: center;
        * {
            margin-left: 10px;
            margin-right: 10px;
        }
    }

    .device-status-content-box {

       

    }

    .column-style {
        ::v-deep .el-table {
            color: red
        }
       
    }
}
</style>