import axios from 'axios'


export interface SopCatalogEntry {
  row_number: number
  project: string
  process: string
  issue_date: string
  link_label: string
  link_url: string | null
  drive_file_id: string | null
  status: string
  note: string
  raw_values: string[]
}

export interface SopMasterSheet {
  spreadsheet_id: string
  sheet_gid: number
  sheet_title: string
  source_url: string
  headers: string[]
  total_rows: number
  linked_file_count: number
  status_counts: Record<string, number>
  entries: SopCatalogEntry[]
  fetched_at: string
  cached: boolean
}

export interface SopBomMaterial {
  part_number: string
  name: string
  quantity: number | null
  quantity_complete: boolean
  unit: string | null
  sections: string[]
  pages: number[]
  occurrences: number
  confidence: number
  source_lines: string[]
}

export interface SopBomSection {
  name: string
  page_number: number
  materials: SopBomMaterial[]
}

export interface SopPartReference {
  part_number: string
  name: string
  occurrences: number
  quantity: number
  pages: number[]
  source_lines: string[]
}

export interface SopPdfPage {
  page_number: number
  text: string
  text_length: number
  category: 'instruction' | 'material_list' | 'tool_list'
}

export interface SopPdfAnalysis {
  file_id: string
  filename: string
  mime_type: string
  size: number
  modified_time: string | null
  page_count: number
  text_length: number
  text_truncated: boolean
  metadata: Record<string, string>
  pages: SopPdfPage[]
  bom_detected: boolean
  bom_material_count: number
  bom_occurrence_count: number
  bom_sections: SopBomSection[]
  bom_materials: SopBomMaterial[]
  full_text_material_count: number
  full_text_occurrence_count: number
  full_text_references: SopPartReference[]
  ai_enabled: boolean
  ai_used: boolean
  ai_fallback: boolean
  ai_error: string | null
  cached: boolean
  analyzed_at: string
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 240000
})

export const sopApi = {
  masterSheet: (refresh = false) =>
    api.get<SopMasterSheet>('/sop/master-sheet', { params: { refresh } }),
  analyze: (fileId: string, refresh = false) =>
    api.get<SopPdfAnalysis>(`/sop/files/${encodeURIComponent(fileId)}/analysis`, { params: { refresh } })
}
