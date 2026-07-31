import axios from 'axios'


export type WorkflowKind = 'duro_bom_check' | 'custom'
export type WorkflowStatus = 'draft' | 'active' | 'paused'
export type WorkflowStepKind = 'duro_bom_fetch' | 'bom_compare' | 'report' | 'custom'
export type WorkflowRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'skipped'
export type WorkflowBomDifferenceStatus =
  | 'missing_in_duro'
  | 'extra_in_duro'
  | 'quantity_mismatch'
  | 'quantity_unknown'

export interface WorkflowStep {
  id: string
  name: string
  kind: WorkflowStepKind
  description: string
  configuration: Record<string, unknown>
}

export interface WorkflowSchedule {
  enabled: boolean
  interval_minutes: number
}

export interface Workflow {
  id: string
  name: string
  description: string
  kind: WorkflowKind
  status: WorkflowStatus
  schedule: WorkflowSchedule
  steps: WorkflowStep[]
  configuration: Record<string, unknown>
  created_at: string
  updated_at: string
  last_run_at: string | null
  next_run_at: string | null
  run_count: number
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  trigger_type: 'manual' | 'scheduled'
  status: WorkflowRunStatus
  message: string
  logs: string[]
  report: WorkflowBomReport | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface WorkflowDuroSubmenu {
  id: string
  label: string
  name: string
}

export interface WorkflowBomDifference {
  status: WorkflowBomDifferenceStatus
  part_number: string
  name: string
  sop_quantity: number | null
  duro_quantity: number | null
  quantity_delta: number | null
  sop_locations: string[]
  sop_quantity_explanations: string[]
  sop_quantity_decisions: WorkflowSopQuantityDecision[]
  duro_paths: string[]
  duro_submenu_ids: string[]
  duro_submenu_labels: string[]
  is_ignored: boolean
  active_ignore_reason: string
  active_ignored_at: string | null
}

export interface WorkflowIgnoredPartRule {
  workflow_id: string
  part_number: string
  reason: string
  ignored_at: string
}

export interface WorkflowSopQuantityDecision {
  source: string
  event_id: string
  page_numbers: number[]
  action: string
  target: string
  location: string
  quantity_delta: number
  accumulate: boolean
  duplicate_of: string | null
  reason: string
  evidence: string
}

export interface WorkflowBomIgnoredItem extends WorkflowBomDifference {
  ignore_type: 'sop_product_keyword' | 'part_number' | 'part_number_cleanup'
  ignore_value: string
  ignore_reason: string
  normalized_part_number: string | null
  ignored_at: string | null
}

export interface WorkflowBomReport {
  generated_at: string
  sop_source_count: number
  sop_material_count: number
  duro_material_count: number
  matched_count: number
  missing_in_duro_count: number
  extra_in_duro_count: number
  quantity_mismatch_count: number
  quantity_unknown_count: number
  duro_submenus: WorkflowDuroSubmenu[]
  differences: WorkflowBomDifference[]
  total_difference_count: number
  ignored_items: WorkflowBomIgnoredItem[]
  total_ignored_count: number
  warning_difference_count: number | null
}

export interface WorkflowRunDetailResponse {
  run: WorkflowRun
  difference_offset: number
  difference_limit: number
  difference_total: number
  has_more: boolean
}

export interface WorkflowRunPage {
  items: WorkflowRun[]
  total: number
  page: number
  page_size: number
  success_count: number
  failed_count: number
  warning_count: number
}

export interface WorkflowRunDeleteResponse {
  deleted_count: number
}

export type WorkflowPayload = Pick<
  Workflow,
  'name' | 'description' | 'kind' | 'status' | 'schedule' | 'steps' | 'configuration'
>

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000
})

export const workflowApi = {
  list: () => api.get<Workflow[]>('/workflows'),
  create: (payload: WorkflowPayload) => api.post<Workflow>('/workflows', payload),
  update: (workflowId: string, payload: Partial<WorkflowPayload>) =>
    api.patch<Workflow>(`/workflows/${workflowId}`, payload),
  remove: (workflowId: string) => api.delete(`/workflows/${workflowId}`),
  ignoredParts: (workflowId: string) =>
    api.get<WorkflowIgnoredPartRule[]>(`/workflows/${encodeURIComponent(workflowId)}/ignored-parts`),
  ignorePart: (workflowId: string, partNumber: string, reason: string) =>
    api.post<WorkflowIgnoredPartRule>(
      `/workflows/${encodeURIComponent(workflowId)}/ignored-parts`,
      { part_number: partNumber, reason }
    ),
  unignorePart: (workflowId: string, partNumber: string) =>
    api.delete(
      `/workflows/${encodeURIComponent(workflowId)}/ignored-parts/${encodeURIComponent(partNumber)}`
    ),
  trigger: (workflowId: string) =>
    api.post<WorkflowRun>(`/workflows/${workflowId}/trigger`, { trigger_type: 'manual' }),
  runs: (
    workflowId: string,
    page = 1,
    pageSize = 10,
    createdFrom?: string,
    createdTo?: string
  ) => api.get<WorkflowRunPage>('/workflow-runs', {
    params: {
      workflow_id: workflowId,
      page,
      page_size: pageSize,
      created_from: createdFrom || undefined,
      created_to: createdTo || undefined
    }
  }),
  runDetail: (runId: string, differenceOffset = 0, differenceLimit = 5000) =>
    api.get<WorkflowRunDetailResponse>(`/workflow-runs/${encodeURIComponent(runId)}`, {
      params: { difference_offset: differenceOffset, difference_limit: differenceLimit }
    }),
  deleteRuns: (runIds: string[]) =>
    api.delete<WorkflowRunDeleteResponse>('/workflow-runs', { data: { run_ids: runIds } })
}
