import { fi } from "element-plus/es/locales.mjs";
import { $get, $post } from "../utils/request"
import {URL} from '../utils/request'


// 下载
export const $downloadFiles = async (uri: string, datas: Object) => {
const response = await fetch(`${URL}${uri}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add authorization header if needed
        // 'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(datas)

    });
    if (!response.ok) {
      const errorData = await response.json();
    
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Get filename from Content-Disposition header or use default
    const contentDisposition = response.headers.get('Content-Disposition');
   
    const filename = contentDisposition?.match(/filename="?(.+?)"?$/)?.[1] 
    || 'download.zip';
  
    // Create download link
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
   
    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);

}

export const $getFileList = async (file_name: string) => {}


export const $uploadFile = async (file_name: string) => {}