<template>
  <div class="login-container">
    <el-card class="login-card">
      <div class="login-header">
        <h2>欢迎登录</h2>
        <p>请输入您的账号和密码</p>
      </div>

      <el-form
        ref="loginForm"
        :model="loginFormData"
        :rules="rules"
        @submit.prevent="handleSubmit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginFormData.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginFormData.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="rememberMe">记住我</el-checkbox>
          <el-link type="primary" :underline="false" class="forgot-password">
            忘记密码?
          </el-link>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="login-btn"
          >
            登 录
          </el-button>
        </el-form-item>

        <div class="login-footer">
          <span>还没有账号?</span>
          <el-link type="primary" :underline="false" @click="goRegister">
            立即注册
          </el-link>
        </div>
      </el-form>
    </el-card>

    <div class="login-bg"></div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import {useAuthStore} from '../../stores/auth'
import {LoginForm} from '../../types/auth.ts'

const router = useRouter()

// 登录

const authStore = useAuthStore()

const loginFormData = ref<LoginForm>({
  username: '',
  password: '',
  rememberMe: false
})


const rememberMe = ref(false)
const loading = ref(false)
const loginForm = ref<FormInstance>()



// 表单验证规则
const rules = ref<FormRules>({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 12, message: '长度在 3 到 12 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 18, message: '长度在 6 到 18 个字符', trigger: 'blur' }
  ]
})

// 提交登录
const handleSubmit = async () => {
  try {
    loading.value = true
    await loginForm.value?.validate()
    // 这里调用登录API
    const success =  await authStore.login(loginFormData.value)
    if (success) {
      ElMessage.success("登录成功")
      router.push('/')
    }
    else{
      ElMessage.error("登录失败")
    }
  } catch (error) {
    ElMessage.error("登录失败")
  } finally {
    loading.value = false
  }
}

// 跳转注册页
const goRegister = () => {
  router.push('/register')
}
</script>

<style scoped lang="scss">
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: rgb(23, 33, 45);
  position: relative;
  overflow: hidden;

  .login-card {
    width: 420px;
    border-radius: 12px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    z-index: 1;

    :deep(.el-card__body) {
      padding: 40px;
    }
  }

  .login-header {
    text-align: center;
    margin-bottom: 30px;

    h2 {
      color: #303133;
      margin-bottom: 8px;
      font-weight: 500;
    }

    p {
      color: #909399;
      font-size: 14px;
    }
  }

  .forgot-password {
    float: right;
  }

  .login-btn {
    width: 100%;
    letter-spacing: 2px;
  }

  .login-footer {
    text-align: center;
    margin-top: 20px;
    color: #909399;
    font-size: 14px;

    .el-link {
      margin-left: 8px;
    }
  }

  .login-bg {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
    opacity: 0.1;
    z-index: 0;
  }
}

@media (max-width: 768px) {
  .login-container {
    padding: 20px;

    .login-card {
      width: 100%;
      max-width: 420px;
    }
  }
}
</style>