import {$get, $post} from '../utils/request'
import { LoginForm, RegisterForm } from '../types/auth'

interface AuthResponse {
  user: any
  token_type: string
  access_token: string
  success: boolean
  message: string
}


export const loginUser = async (credentials: LoginForm): Promise<AuthResponse> => {
  const response = await $post('/api/user/login', credentials)
  return response
}

export const registerUser = async (userData: RegisterForm): Promise<AuthResponse> => {
  const response = await $post('/api/user/register', userData)
  return response
}