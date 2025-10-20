import { List } from "echarts";
import { $get, $post } from "../utils/request"

//interface

export interface TestPlanInterface {
    date: Date | string
    product: string
    test_name: string | string[]
    barcode: string
    fixture_name: string
    fixture_ip?: string
    auto_upload: boolean | string

}
export interface RequireKeyInterface {
    barcode: string
}

export interface RequireDeletePlanInterface {
    require_key: RequireKeyInterface
}

interface DeleteTestPlanResponse{
    status_code: number
    detail?: string
}

interface AddTestPlanResponse{
    status_code: number
    detail?: string
}

// utils
async function upload_data_to_db(db_name: string, document_name: string, datas:object): Promise<AddTestPlanResponse> {
    const res = await $post('/api/db/insert/document', {
        db_name: db_name,
        document_name: document_name,
        collections: datas
    })
    return res
}

const fetch_data = async(db_name: string, document_name:string, limit?: number) =>{
     const res: List = await $post('/api/db/read/document', {
      db_name: db_name,
      document_name: document_name,
      limit: limit||100
    })
    return res
}

const delete_data = async(db_name: string, document_name: string, require_key: object): Promise<DeleteTestPlanResponse> => {
    const res = await $post('/api/db/delete/document', {
        db_name: db_name,
        document_name: document_name,
        require_key: require_key
    })
    return res
}

// test management

export async function fetch_test_plan(): Promise<object>{
    const data = await fetch_data("TestPlan", "Index")
    return data
}

export async function add_test_plan(new_plan:TestPlanInterface): Promise<AddTestPlanResponse> {
    const data = upload_data_to_db("TestPlan","Index", new_plan)
    return data
}


export async function delete_test_plan(require:RequireDeletePlanInterface): Promise<DeleteTestPlanResponse> {
    const data = delete_data("TestPlan","Index", require)
    return data
}



