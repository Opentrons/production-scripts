import { $get, $post } from "../utils/request"



// create run
export const $create_run = async (params: object) => {
    let ret = await $post('/tests/create/run', params);
    return ret
}

// get run
export const $get_run = async (params: object) => {
    let ret = await $get('/tests/get/runs', params);
    return ret
}

