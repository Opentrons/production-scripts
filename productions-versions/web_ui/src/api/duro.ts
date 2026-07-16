import axios from 'axios'


export interface DuroProductImage {
  _id?: string
  name?: string
  mime?: string
  size?: number
  src?: string
  key?: string
  archived?: boolean
  [key: string]: unknown
}

export interface DuroProduct {
  _id: string
  name: string
  cpn?: string | null
  cpnVariant?: unknown
  alias?: string | null
  description?: string | null
  revision?: string | null
  status?: string | null
  company?: unknown
  eid?: unknown
  images?: DuroProductImage[]
  revisions?: unknown[]
  lastModified?: number | string | null
  modified?: number | string | null
  created?: number | string | null
  lastReleasePrdRev?: unknown
  previousRevision?: unknown
  previousStatus?: unknown
  [key: string]: unknown
}

export interface DuroProductSearchResponse {
  success: boolean
  count: number
  products: DuroProduct[]
  request: {
    page: number
    sort: string
    reverse: boolean
    limit: number
    lean: boolean
    populate: string
  }
  cached: boolean
  fetched_at: string
}

export interface DuroConnectionStatus {
  configured: boolean
  token_valid: boolean
  token_expires_at: string | null
  base_url: string
}

export interface DuroBomNode {
  id: string
  relationship_id: string | null
  node_type: 'product' | 'component' | string
  name: string
  cpn: string | null
  cpn_variant: unknown
  alias: string | null
  revision: string | null
  status: string | null
  quantity: unknown
  item_number: unknown
  notes: string | null
  reference_designators: unknown
  waste: unknown
  unit_of_measure: unknown
  has_children: boolean
  children: DuroBomNode[]
  ui_key?: string
}

export interface DuroProductBomResponse {
  success: boolean
  product_id: string
  root: DuroBomNode
  direct_child_count: number
  source_url: string
  cached: boolean
  fetched_at: string
}

export interface DuroComponentChildrenResponse {
  success: boolean
  component_id: string
  children: DuroBomNode[]
  count: number
  cached: boolean
  fetched_at: string
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000
})

export const duroApi = {
  status: () => api.get<DuroConnectionStatus>('/duro/status'),
  products: (refresh = false) =>
    api.get<DuroProductSearchResponse>('/duro/products', { params: { refresh } }),
  productBom: (productId: string, refresh = false) =>
    api.get<DuroProductBomResponse>(`/duro/products/${encodeURIComponent(productId)}/bom`, { params: { refresh } }),
  componentChildren: (componentId: string, refresh = false) =>
    api.get<DuroComponentChildrenResponse>(`/duro/components/${encodeURIComponent(componentId)}/children`, {
      params: { refresh }
    })
}
