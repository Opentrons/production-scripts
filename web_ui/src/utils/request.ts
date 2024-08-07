import axios from "axios"


const URL = "http://127.0.0.1:9090"


const instance = axios.create({
    baseURL: URL,
    timeout: 30000*4,
    headers: { 'Access-Control-Allow-origin': '*', "accept": "application/json"}
})

// 请求拦截器
instance.interceptors.request.use(config => {
    // 在发送请求之前做些什么
    return config;
}, error => {
    // 对请求错误做些什么
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
    // await instance.get(url, {params})
    //     .then(response => {
    //         return response
    //     })
    //     .catch(error => {
    //         return error
    //     });
        
}

export const $post = async (url: string, params: object = {}) => {

    let { data } = await instance.post(url, { params })
    return data
    // await instance.post(url, {params})
    //     .then(response => {
    //         console.log(response)
    //         return response
    //     })
    //     .catch(error => {
    //         return error
    //     });
}

export const $download = async(url: string, file_name: string) => {
    

    const response = await fetch(`${URL}${url}/${file_name}`);
    return response
   

}






