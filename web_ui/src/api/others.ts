import { $get, $post } from "../utils/request"


// 登录用户
export const $get_version = async () => {
    let ret = await $get('/get_version');
    console.log(ret);
}