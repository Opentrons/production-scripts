import { $get, $post } from "../utils/request"

// 新建连接
export const $build_connect = async (params: object) => {
    let ret = await $post('/device/hardware/build', params);
    return ret
}

// home Axis
export const $home = async (params: object) => {
    let ret = await $post('/device/hardware/home', params);
    return ret
}

// move To
export const $moveTo = async (params: object) => {
    let ret = await $post('/device/hardware/move_to', params)
    return ret
}

// move Rel
export const $moveRel = async (params: object) => {
    let ret = await $post('/device/hardware/move_rel', params)
    return ret
}

// test online
export const $testOnline = async (params: object) => {
    let ret = await $post('/device/hardware/test/online', params)
    return ret
}

