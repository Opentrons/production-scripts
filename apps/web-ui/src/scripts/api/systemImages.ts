import { createApiClient } from '@/scripts/api/http'

const api = createApiClient(15000)
const base = '/robots/system-images'
export interface SystemImage {
  name: string
  version: string
  size: number
  modified_at: string
}
export interface SystemImageTask {
  id: string
  kind: 'install' | 'download'
  ip: string
  image: string
  status: 'queued' | 'running' | 'success' | 'failed'
  stage: string
  progress: number | null
  message: string
  logs: string[]
  created_at: string
  finished_at: string | null
}
export const systemImagesApi = {
  list: () => api.get<{ directory: string; images: SystemImage[] }>(base),
  tasks: () => api.get<{ tasks: SystemImageTask[] }>(`${base}/tasks`),
  install: (ips: string[], image: string, port: number) =>
    api.post<{ tasks: SystemImageTask[] }>(`${base}/install`, { ips, image, port }),
  download: (url: string) => api.post<SystemImageTask>(`${base}/download`, { url }),
}
