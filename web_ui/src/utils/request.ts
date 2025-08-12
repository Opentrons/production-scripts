import axios from "axios"
import {getTokenExpiration} from '../utils/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Action } from 'element-plus'


export const URL = "http://127.0.0.1:8080"


const instance = axios.create({
    baseURL: URL,
    timeout: 30000*4,
    headers: { 'Content-Type': 'application/json', "accept": "application/json"}
})

// 请求拦截器
instance.interceptors.request.use(async (config) => {
  const token = localStorage.getItem('token');
  if (token) {
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

    let { data } = await instance.get(url, { params })
    return data
        
}

export const $post = async (url: string, params: object = {}) => {

    let { data } = await instance.post(url, params, {
        headers: {
            'Content-Type': 'application/json'
        }
    })
    return data
}

// export const $download = async(url: string, file_name: string) => {
    

//     const response = await fetch(`${URL}${url}/${file_name}`);
//     return response
   

// }






