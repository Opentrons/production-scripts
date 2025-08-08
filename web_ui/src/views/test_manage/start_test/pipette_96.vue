<template>
    <div class="main-box">
        <div class="left-box">
            <el-button type="primary" :icon="CirclePlusFilled" @click="dialogFormTest4Visible = true" style="margin: 10px">新建</el-button>
            <el-dialog v-model="dialogFormTest4Visible" title="新建运行" width="500">
                <el-form :model="dialogFormData" label-width="auto" style="max-width: 600px">
                    <el-form-item label="机器名">
                    <el-input v-model="dialogFormData.robot_name" />
                    </el-form-item>

                    <el-form-item label="设备IP">
                    <el-input v-model="dialogFormData.device_ip" />
                    </el-form-item>  
                
                    
                    <el-form-item label="使用密钥">
                    <el-switch v-model="dialogFormData.use_key" />
                    </el-form-item>
                    <el-form-item label="添加类别">
                    <el-checkbox-group v-model="dialogFormData.type">
                        <el-checkbox value="diagnostic" name="type">
                        诊断测试
                        </el-checkbox>
                        <el-checkbox value="protocol" name="type">
                        协议测试
                        </el-checkbox>
                        <el-checkbox value="gravimetric" name="type">
                        容量测试
                        </el-checkbox>
                        <el-checkbox value="lifetime" name="type">
                        老化测试
                        </el-checkbox>
                    </el-checkbox-group>
                    </el-form-item>

                    <el-form-item label="运行命令">
                        <el-input v-model="dialogFormData.cmd" />
                    </el-form-item>
                    <el-form-item label="参数">
                        <div>
                        <el-tag v-for="tag in paramsTags" :key="tag" closable :disable-transitions="false"
                            @close="handleClose(tag)" style="margin-right: 10px">
                            {{ tag }}
                        </el-tag>
                        <el-input v-if="inputVisible" ref="InputRef" v-model="inputValue" class="w-20" size="small"
                            @keyup.enter="handleInputConfirm" @blur="handleInputConfirm" />
                        <el-button v-else class="button-new-tag" size="small" @click="showInput">
                            + New Tag
                        </el-button>
                    </div>
                    </el-form-item>
                    
                    <el-form-item label="详情">
                    <el-input v-model="dialogFormData.description" type="textarea" />
                    </el-form-item>
                    <el-form-item>
                    
                    </el-form-item>
                </el-form>


                <template #footer>
                    <div class="dialog-footer">
                        <el-button @click="dialogFormTest4Visible = false">Cancel</el-button>
                        <el-button type="primary" @click="confirmNewRun">
                            Confirm
                        </el-button>
                    </div>
                </template>
            </el-dialog>
            <el-tabs type="border-card">
                <el-tab-pane label="诊断测试">

                    <CommandTable> </CommandTable>
                </el-tab-pane>
                <el-tab-pane label="Protocol 测试">
                    Protocol
                </el-tab-pane>
                <el-tab-pane label="容量测试">
                    Grav
                </el-tab-pane>
                <el-tab-pane label="老化测试">
                    <div class="test4-mian">
                        <div class="test4-top">
                        

                        </div>
                        <div class="test4-content">
                            <CommandTable :tableData="tableData96ch" :production="_production"> </CommandTable>
                        </div>
                    </div>

                </el-tab-pane>
            </el-tabs>


        </div>
        <div class="right-box">

        </div>
    </div>
</template>

<script lang="ts" setup>

import CommandTable from "../../../components/CommandTable.vue"
import { CirclePlusFilled } from '@element-plus/icons-vue'
import { ref, reactive, nextTick, onMounted} from 'vue'
import { ElInput } from 'element-plus'
import { $get_current_time } from '../../../utils/utils'
// import { $create_run, $get_run} from '../../../api/tests'

// paramter tag
const paramsTags = ref(['--chnannel 8', '--update', '--operator Andy'])

const inputValue = ref('')
const inputVisible = ref(false)
const InputRef = ref<InstanceType<typeof ElInput>>()

let dialogFormTest4Visible = ref(false)
const formLabelWidth = '140px'
const this_time = $get_current_time()

const tableData96ch = ref([])
const _production = '96ch'

const dialogFormData = reactive({
    date: this_time,
    auth: 'default',
    robot_name: '',
    device_ip: '192.168.6.11',
    cmd: "",
    params: paramsTags.value,
    use_key: true,
    
    description: '',
    production: _production,
    type: [],
    
})

const getRunForm96CH = async() => {
    // let ret = await $get_run(
    //     {"type": "96ch"}
    // )
    // if (ret.success){
    //     tableData96ch.value = ret.data
    // }
  
}


getRunForm96CH()


onMounted(() => {
    

})


const handleClose = (tag: string) => {
    paramsTags.value.splice(paramsTags.value.indexOf(tag), 1)
}

const handleInputConfirm = () => {
    if (inputValue.value) {
        paramsTags.value.push(inputValue.value)
    }
    inputVisible.value = false
    inputValue.value = ''
}

const showInput = () => {
    inputVisible.value = true
    nextTick(() => {
        InputRef.value!.input!.focus()
    })
}

const confirmNewRun = async() => {

    // let ret = await $create_run(dialogFormData)
    // getRunForm96CH()
    // dialogFormTest4Visible.value = false
}

</script>

<style lang="scss" scoped>
.main-box {

    display: flex;

    justify-content: center;
    align-items: center;

    .left-box {
        width: 70vw;
        height: 100vh;
        margin-right: 10px;

        border: solid gray 1px;

        .test4-mian {
     
            display: flex;
            flex-direction: column;

            .test4-top {}

        }
    }

    .right-box {
        flex: 1;
        height: 100vh;

        border: solid gray 1px;
    }
}
</style>
