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

export interface WorkflowBomDifference {
  status: WorkflowBomDifferenceStatus
  part_number: string
  name: string
  sop_quantity: number | null
  duro_quantity: number | null
  quantity_delta: number | null
  sop_locations: string[]
  duro_paths: string[]
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
  differences: WorkflowBomDifference[]
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
  trigger: (workflowId: string) =>
    api.post<WorkflowRun>(`/workflows/${workflowId}/trigger`, { trigger_type: 'manual' }),
  runs: (workflowId: string) =>
    api.get<WorkflowRun[]>('/workflow-runs', { params: { workflow_id: workflowId, limit: 20 } })
}
