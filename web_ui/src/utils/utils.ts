
import {jwtDecode} from 'jwt-decode';

export const $get_current_time = (): string => {
    const currentDate = new Date();
    const year = currentDate.getUTCFullYear();
    const month = (currentDate.getUTCMonth() + 1).toString().padStart(2, '0');
    const day = currentDate.getUTCDate().toString().padStart(2, '0');
    const formattedDate = `${year}-${month}-${day}`;
    return formattedDate
}

/**
 * 从JWT Token中提取过期时间戳
 * @param token JWT Token字符串
 * @returns 过期时间戳（毫秒），解析失败返回null
 */
export function getTokenExpiration(token: string): number | null {
  try {
    // 解码Token payload部分
    const decoded = jwtDecode<{ exp?: number }>(token);
    
    // 检查是否存在exp字段
    if (decoded?.exp === undefined) {
      console.warn('Token does not contain expiration time');
      return null;
    }

    // 将秒级时间戳转为毫秒
    return decoded.exp * 1000; 
  } catch (error) {
    console.error('Failed to decode token:', error);
    return null;
  }
}