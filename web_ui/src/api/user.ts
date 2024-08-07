import { $get, $post } from "../utils/request"


// 登录用户
export const $login = async (params: object) => {
    let ret = await $post('/user/login', params);
    return ret
}