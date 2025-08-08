import { fi } from "element-plus/es/locales.mjs";
import { $get, $post } from "../utils/request"


// 下载
export const $downloadFiles = async (file_name: string) => {
    // try {
    //     // 使用 fetch 请求下载文件
    //     const response = await $post('/files/download', file_name);
    //     console.log("OK?", response)
    //     if (response.status) {
    //         // 将文件转换为 Blob
    //         const blob = await response.blob();

    //         // 创建一个链接并设置下载属性
    //         const link = document.createElement('a');
    //         link.href = window.URL.createObjectURL(blob);
    //         link.download = file_name;

    //         // 模拟点击下载链接
    //         link.click();
    //     } else {
    //         alert('从后端downloadfile目录里下载此文件失败.');
    //     }
    // } catch (error) {
    //     console.error(error);
    //     alert('下载文件出错.');
    // }


}

export const $getFileList = async (file_name: string) => {}


export const $uploadFile = async (file_name: string) => {}