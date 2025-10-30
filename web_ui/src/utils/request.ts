import axios from "axios"
import {getTokenExpiration} from '../utils/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Action } from 'element-plus'
import { el } from "element-plus/es/locales.mjs"


export const URL = "/api"


const instance = axios.create({
    baseURL: URL,
    timeout: 30000*4,
    headers: { 'Content-Type': 'application/json', "accept": "application/json"}
})

// 请求拦截器
instance.interceptors.request.use(async (config) => {
  if (config.url?.includes('/login') || config.url?.includes('/auth')) {
    return config;
  }

  if (typeof window !== 'undefined'){
    const token = localStorage.getItem('token');
    const isExpired = Date.now() >= getTokenExpiration(token);
    if (isExpired) {
      // 1. 先清除本地存储
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      
      // 2. 显示提示（await 确保弹窗完成显示）
      await ElMessageBox.alert('登录已过期，请重新登录', '提示', {
        confirmButtonText: '确定',
        callback: () => {
          // 3. 跳转登录页
          window.location.href = '/login?expired=1';
        }
      });
      // 4. 中断请求
      return Promise.reject(new Error('Token expired'));
    }
    config.headers.Authorization = `Bearer ${token}`;
  }
  else{
    console.log("Debug Mode, We are using Node")
  }
 
  return config;
}, error => {
  return Promise.reject(error);
});

// 响应拦截器
axios.interceptors.response.use(response => {
    // 对响应数据做点什么
    return response;
}, error => {
    // 捕捉失败的请求
    if (error.response) {
        // 响应错误处理
        console.error('请求失败:', error.response);
    } else if (error.request) {
        // 请求发送失败处理
        console.error('请求发送失败:', error.request);
    } else {
        // 其他错误处理
        console.error('错误:', error.message);
    }
    // 可以在这里做全局的处理，比如提示用户
    // 返回Promise.reject(error);可以让调用这个请求的地方处理错误
    return Promise.reject(error);
});


export const $get = async (url: string, params: object = {}) => {

    const response = await instance.get(url, { params })
     return {
        status_code: response.status,  // 添加状态码
        ...response.data               // 展开原有的数据
    }
        
}

export const $post = async (url: string, params: object = {}) => {
  try {
    const response = await instance.post(url, params)
    return {
        status_code: response.status,  // 添加状态码
        ...response.data               // 展开原有的数据
    }
  } catch (error) {
    if (error.response) {
      return {
        status_code: error.response.status,
        detail: error.response.data.detail,
        success: false
      }
    }
  }

}

// export const $download = async(url: string, file_name: string) => {
    

//     const response = await fetch(`${URL}${url}/${file_name}`);
//     return response
   

// }






