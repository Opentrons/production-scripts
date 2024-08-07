import { $get, $post } from "../utils/request"


// 获取device
export const $get_device = async () => {
    let ret = await $get('/device/status');
    return ret
}

// add device
export const $add_device = async (params: object) => {
    let ret = await $post('/device/add/device', params);
    return ret
}

// remove device
export const $remove_device = async (params: object) => {
    let ret = await $post('/device/remove/device', params);
    return ret
}