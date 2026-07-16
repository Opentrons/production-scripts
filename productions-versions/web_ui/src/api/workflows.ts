import axios from 'axios'


export type WorkflowKind = 'duro_bom_check' | 'custom'
export type WorkflowStatus = 'draft' | 'active' | 'paused'
export type WorkflowStepKind = 'duro_bom_fetch' | 'bom_compare' | 'report' | 'custom'
export type WorkflowRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'skipped'

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
  created_at: string
  started_at: string | null
  finished_at: string | null
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
