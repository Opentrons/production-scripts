<template>
    <div class="top-box">
        <el-text >Flex设备</el-text>
        <el-select 
            v-model="input_ip_address" 
            placeholder="Select" 
            style="width: 240px"
            filterable
            allow-create
          
            >
            <el-option
                v-for="item in flex_list"
                :key="item.value"
                :label="item.label"
                :value="item.value"
            />
        </el-select>
   
        <el-button :disabled="isDiscover" type="primary" size="small" @click="fetchFlexList" style="margin-top:7px"> 刷新设备 </el-button>
    
        <el-text >下载路径</el-text>
        <el-input v-model="input_download_path" style="width: 240px; height: 25px;" placeholder="/data/testing_data" />
        <el-text >使用密钥</el-text>
        <el-switch v-model="use_secret" />
        
    </div>
    <div class="content-box">
        <div class="upload"> 
            <el-icon @click=""><UploadFilled /></el-icon>
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
    import {$get, $post} from '../../utils/request'

    // input ip address
    const input_ip_address = ref('')
    const input_download_path = ref('/data/testing_data')
    const flex_list = ref([

    ])

    const isDiscover = ref(false)
    // use secret
    const use_secret = ref(true)


    import { ElMessage, ElMessageBox } from 'element-plus'

    import type { UploadProps, UploadUserFile } from 'element-plus'
    import { utils } from 'xlsx'

    async function fetchFlexList() {
        
        interface ApiResponse {
        flex_group: Record<string, Record<string, any>>; // 键是 IP 地址，值是 FlexGroupItem
        message: string;
        success: boolean;
        }
        isDiscover.value = true

        flex_list.value = []
        try {
            const response: ApiResponse = await $get('/api/flex/discover')
            const flex_group = response.flex_group
         
            for (const key in flex_group) {
                console.log(key, flex_group[key]["name"]); // 输出键和值
                flex_list.value.push({
                    value: key,       // 使用键作为 label（例如 IP 地址）
                    label: flex_group[key]["name"] + "(" + key + ")"      // 使用键作为 value（也可以使用 dict[key] 的某个属性）
                });
                
            }
            ElMessage.success('刷新完成!');
        } catch (error) {
            console.error('Error:', error);
            ElMessage.error(error);
        }
        input_ip_address.value = flex_list.value[0]["label"]
        isDiscover.value = false
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