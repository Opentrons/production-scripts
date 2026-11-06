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
  sync_status?: SupplementaryMaterialSyncStatus | null
}

export interface SupplementaryMaterialSyncStatus {
  source_url: string
  interval_seconds: number
  auto_sync_enabled: boolean
  last_synced_at: string | null
  last_error: string
  syncing: boolean
}

export interface SupplementaryMaterialSyncResult {
  total: number
  source_url: string
  synced_at: string
  created_count: number
  updated_count: number
  removed_count: number
}

export const SUPPLIES_SOURCE_URL = 'https://docs.google.com/spreadsheets/d/1GhGXTfEEXbN-LYry2bwKJirQJcKP4xAA/edit?gid=921765553#gid=921765553'

export interface SupplementaryMaterialPayload {
  material_number: string
  english_name: string
  chinese_name: string
  eid: string
}

const api = createApiClient(120000)

export const suppliesApi = {
  sync: () => api.post<SupplementaryMaterialSyncResult>('/supplies/sync'),
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
