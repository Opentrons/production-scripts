// 用户基本信息类型
export interface User {
  id: number | string
  username: string
  email: string
  avatar?: string  // 可选属性
  roles?: string[] // 用户角色数组
  createdAt?: string // 创建时间
}

// 登录表单数据类型
export interface LoginForm {
  username: string
  password: string
  rememberMe: boolean // 可选记住我选项
}

// 注册表单数据类型
export interface RegisterForm {
  username: string
  email: string
  password: string
  confirmPassword: string // 确认密码字段
  agreement: boolean    // 是否同意协议
}

// 认证响应数据类型
export interface AuthResponse {
  user: User
  token: string
  refreshToken?: string // 可选的刷新令牌
  expiresIn?: number   // token过期时间(秒)
}

// 错误响应类型
export interface AuthError {
  code: number
  message: string
  errors?: Record<string, string[]> // 字段错误详情
}

// 重置密码类型
export interface ResetPasswordForm {
  email: string
  code?: string      // 验证码(可选)
  newPassword?: string // 新密码(可选)
}

// 修改密码类型
export interface ChangePasswordForm {
  oldPassword: string
  newPassword: string
  confirmPassword: string
}