<template>
    <div class="top-box">
        <el-text >设备IP地址</el-text>
        <el-input v-model="input_ip_address" style="width: 240px; height: 25px;" placeholder="输入设备地址"  />
        <el-upload
            v-model:file-list="fileList"
            class="upload-demo"
            multiple >
            <el-button type="primary" size="small" style="margin-top:7px"> 选择上传文件 </el-button>
           
        </el-upload>
        <el-text >下载路径</el-text>
        <el-input v-model="input_download_path" style="width: 240px; height: 25px;" placeholder="/data/testing_data" />
        <el-text >使用密钥</el-text>
        <el-switch v-model="use_secret" />
        
    </div>
    <div class="content-box">
        <div class="upload"> 
            <el-icon @click="upload_handel"><UploadFilled /></el-icon>
            <el-text size="">上传</el-text>
        </div>
        <div class="download"> 
            <el-icon @click="download_handel"><Download/></el-icon>
            <el-text>下载</el-text>
        </div>
        <div class="delete"> 
            <el-icon><DeleteFilled/></el-icon>
            <el-text>删除</el-text>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import { computed, ref} from 'vue'
    import {$downloadFiles, } from '../../api/files'
    import {DeleteFilled, UploadFilled, Download} from '@element-plus/icons-vue'

    // input ip address
    const input_ip_address = ref('192.168.6.11')
    const input_download_path = ref('/data/testing_data')
 

    // use secret
    const use_secret = ref(true)

    // interface User {
    // id: string
    // production: string
    // test_type: string

    // }

    // const input_search = ref('')
    // const filterTableData = computed(() =>
    // tableData.filter(
    //     (data) =>
    //         !input_search.value ||
    //         data.production.toLowerCase().includes(input_search.value.toLowerCase())
    // )
    // )
    // const handleEdit = async (index: number, row: User) => {
    //     console.log("download")
    //     let ret = await $downloadFiles('test.txt')
    //     console.log(ret)
    // }

    // const handleDelete = (index: number, row: User) => {
    //     console.log(index, row)
    // }

    // upload
    import { ElMessage, ElMessageBox } from 'element-plus'

    import type { UploadProps, UploadUserFile } from 'element-plus'

    const fileList = ref<UploadUserFile[]>([
    
    ])

    const upload_handel = () => {
        console.log(fileList.value)
    }

    const download_handel = async () => {
        await $downloadFiles('setting.zip')
    }



    
</script>


<style lang="scss" scoped>

   

    .top-box {
        margin-top: 10px;
        display: flex;
        justify-content: left;
        align-items: center;
        * {
            margin-left: 10px;
            margin-right: 20px;
           
        }
    }

    .content-box {
        height: 800px;
        display: flex;
        margin-top: 10px;
        align-items: center;
        justify-content: center;
        font-size: 80px;
        .upload {
           
            display: flex;
            flex-direction: column;
            margin: 100px;
            color: rgb(171, 226, 171)
        }
        .download {
           
            display: flex;
            flex-direction: column;
            margin: 100px;
            color: rgb(103, 154, 241)
        }
        .delete {
          
            display: flex;
            flex-direction: column;
            margin: 100px;
            color: rgb(249, 139, 109)
        }

        
    }


</style>