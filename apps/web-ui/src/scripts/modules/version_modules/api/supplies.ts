import { createApiClient } from '@/scripts/api/http'


export interface SupplementaryMaterial {
  id: string
  material_number: string
  english_name: string
  chinese_name: string
  eid: string
  created_at: string
  updated_at: string
}

export interface SupplementaryMaterialListResponse {
  items: SupplementaryMaterial[]
  total: number
}

export interface SupplementaryMaterialPayload {
  material_number: string
  english_name: string
  chinese_name: string
  eid: string
}

const api = createApiClient(15000)

export const suppliesApi = {
  list: (query = '') =>
    api.get<SupplementaryMaterialListResponse>('/supplies', {
      params: query.trim() ? { q: query.trim() } : undefined,
    }),
  create: (payload: SupplementaryMaterialPayload) =>
    api.post<SupplementaryMaterial>('/supplies', payload),
  update: (materialId: string, payload: SupplementaryMaterialPayload) =>
    api.put<SupplementaryMaterial>(`/supplies/${encodeURIComponent(materialId)}`, payload),
  remove: (materialId: string) =>
    api.delete(`/supplies/${encodeURIComponent(materialId)}`),
}
