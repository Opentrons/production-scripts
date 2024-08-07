<template>
    <div class="login">
        <div class="form-box">
            <h2>Opentrons测试线上平台</h2>
            <el-form ref="formRef" style="max-width: 400px" :model="formData" status-icon :rules="rules" label-width="auto"
                class="demo-ruleForm">
                <el-form-item label="用户" prop="username">
                    <el-input v-model="formData.username" />
                </el-form-item>
                <el-form-item label="密码" prop="password">
                    <el-input v-model="formData.password" type="password" autocomplete="off" />
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" @click="submitForm(formRef)">登录</el-button>
                    <el-button @click="resetForm(formRef)">取消</el-button>
                </el-form-item>
            </el-form>

        </div>
    </div>
</template>

<script setup lang="ts">

import { reactive, ref } from 'vue'
import type { FormInstance, FormRules} from 'element-plus'
import {ElMessage} from 'element-plus'
import {$login} from "../api/user"

import { useRouter } from 'vue-router'

const router = useRouter()

const formRef = ref<FormInstance>()

const formData = reactive({
    username: '',
    password: '',
})

const validatePwd = (rule: any, value: any, callback: any) => {
    if (value === '') {
        callback(new Error('请输入密码'))
    } else {
        callback()
    }
}

const validateName = (rule: any, value: any, callback: any) => {
    if (value === '') {
        callback(new Error('请输入用户名'))
    } else {
        callback()
    }
}

const rules = reactive<FormRules<typeof formData>>({
    username: [{ validator: validateName, trigger: 'blur' }],
    password: [{ validator: validatePwd, trigger: 'blur' }],
})

const submitForm = (formEl: FormInstance | undefined) => {
    if (!formEl) return
    formEl.validate(async (valid) => {
        if (valid) {
            let ret = await $login(formData)
            if (ret.success) {
                // store token
                localStorage.setItem("token", ret.token)
                ElMessage({
                            message: ret.message,
                            type: 'success',
                          })
                // push to /index
                router.push('/index')

             }
            else {
                ElMessage.error(ret.message)
            }

        } else {
            ElMessage.error("submit error !")
            return false
        }
    })
}

const resetForm = (formEl: FormInstance | undefined) => {
    if (!formEl) return
    formEl.resetFields()
}

</script>

<style scoped lang="scss">
.login {
    width: 100vw;
    height: 100vh;
    background-color: rgb(54, 131, 208);
    display: flex;

    .form-box {
        width: 400px;
        height: 200px;
        border: 1px solid white;
        padding: 20px;
        margin: auto;
        h2 {
            color: white;
            font-size: 20px;
            text-align: center;
            margin-bottom: 10px;
        }

        ::v-deep .el-form-item__label {
            color: white;
        }
    }
}
</style>