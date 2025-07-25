<template>
  <div class="register-container">
    <el-card class="register-card">
      <div class="register-header">
        <h2>用户注册</h2>
        <p>创建您的账户</p>
      </div>

      <el-form
        ref="registerForm"
        :model="form"
        :rules="rules"
        @submit.prevent="handleSubmit"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="email">
          <el-input
            v-model="form.email"
            placeholder="请输入邮箱"
            prefix-icon="Message"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请确认密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item prop="agreement">
          <el-checkbox v-model="form.agreement">
            我已阅读并同意
            <el-link type="primary" :underline="false">用户协议</el-link>
            和
            <el-link type="primary" :underline="false">隐私政策</el-link>
          </el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="register-btn"
          >
            注 册
          </el-button>
        </el-form-item>

        <div class="register-footer">
          <span>已有账号?</span>
          <el-link type="primary" :underline="false" @click="goLogin">
            立即登录
          </el-link>
        </div>
      </el-form>
    </el-card>

    <div class="register-bg"></div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { FormInstance, FormRules, ElMessage } from 'element-plus'

const router = useRouter()

// 表单数据
const form = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreement: false
})

const loading = ref(false)
const registerForm = ref<FormInstance>()

// 自定义验证规则：确认密码
const validatePass = (rule: any, value: string, callback: Function) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.value.password) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

// 表单验证规则
const rules = ref<FormRules>({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 12, message: '长度在 3 到 12 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 18, message: '长度在 6 到 18 个字符', trigger: 'blur' },
    { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: '必须包含字母和数字', trigger: 'blur' }
  ],
  confirmPassword: [
    { validator: validatePass, trigger: 'blur' }
  ],
  agreement: [
    { validator: (rule, value, callback) => {
      if (!value) {
        callback(new Error('请同意用户协议'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ]
})

// 提交注册
const handleSubmit = async () => {
  try {
    loading.value = true
    await registerForm.value?.validate()
    // 这里调用注册API
    // await registerApi(form.value)
    console.log('注册成功', form.value)
    ElMessage.success('注册成功')
    router.push('/login')
  } catch (error) {
    console.error('注册失败', error)
    ElMessage.error('请检查表单填写是否正确')
  } finally {
    loading.value = false
  }
}

// 跳转登录页
const goLogin = () => {
  router.push('/login')
}
</script>

<style scoped lang="scss">
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: rgb(23, 33, 45);
  position: relative;
  overflow: hidden;

  .register-card {
    width: 450px;
    border-radius: 12px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    z-index: 1;

    :deep(.el-card__body) {
      padding: 40px;
    }
  }

  .register-header {
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

  .register-btn {
    width: 100%;
    letter-spacing: 2px;
    margin-top: 10px;
  }

  .register-footer {
    text-align: center;
    margin-top: 20px;
    color: #909399;
    font-size: 14px;

    .el-link {
      margin-left: 8px;
    }
  }

  .register-bg {
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
  .register-container {
    padding: 20px;

    .register-card {
      width: 100%;
      max-width: 450px;
    }
  }
}

:deep(.el-form-item__content) {
  .el-checkbox {
    margin-right: 10px;
  }
  
  .el-link {
    vertical-align: baseline;
  }
}
</style>