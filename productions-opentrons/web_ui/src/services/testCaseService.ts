import api from '@/api'

export type TestCaseStatus = 'draft' | 'active' | 'archived'
export type TestNodeKind = 'start' | 'expect' | 'end'
export type TestInputKind = 'none' | 'boolean' | 'text' | 'radio'

export interface NodePosition {
  x: number
  y: number
}

export interface TestCaseInputOption {
  label: string
  value: string
}

export interface TestCaseNode {
  id: string
  name: string
  kind: TestNodeKind
  expect?: string | null
  input_kind: TestInputKind
  input_options: TestCaseInputOption[]
  position: NodePosition
}

export interface TestCaseEdge {
  id: string
  source: string
  target: string
  condition?: string | null
}

export interface TestCaseErrorPattern {
  name: string
  pattern: string
  severity: 'warning' | 'error' | 'fatal'
}

export interface TestCase {
  id: string
  name: string
  product_id: string
  product_name: string
  test_type: string
  command: string
  description?: string | null
  timeout_seconds: number
  status: TestCaseStatus
  nodes: TestCaseNode[]
  edges: TestCaseEdge[]
  error_patterns: TestCaseErrorPattern[]
  tags: string[]
  metadata: Record<string, unknown>
  revision: number
  created_at: string
  updated_at: string
  last_run_at?: string | null
  run_count: number
  success_count: number
  failed_count: number
}

export interface TestCaseCreatePayload {
  name: string
  product_id: string
  product_name: string
  test_type: string
  command: string
  description?: string | null
  timeout_seconds?: number
  status?: TestCaseStatus
  nodes?: TestCaseNode[]
  edges?: TestCaseEdge[]
  error_patterns?: TestCaseErrorPattern[]
  tags?: string[]
  metadata?: Record<string, unknown>
}

export type TestCaseUpdatePayload = Partial<TestCaseCreatePayload>

export interface TestCaseListResponse {
  cases: TestCase[]
  total: number
}

export interface TestProductCreatePayload {
  product_id: string
  product_name: string
}

export interface TestProduct {
  product_id: string
  product_name: string
  created_at: string
  updated_at: string
}

export interface TestTypeCreatePayload {
  test_type: string
}

export interface TestType {
  product_id: string
  test_type: string
  created_at: string
  updated_at: string
}

export interface TestCaseTreeCase {
  id: string
  name: string
  status: TestCaseStatus
  test_type: string
  updated_at: string
}

export interface TestCaseTreeGroup {
  test_type: string
  total: number
  cases: TestCaseTreeCase[]
}

export interface TestCaseTreeProduct {
  product_id: string
  product_name: string
  total: number
  groups: TestCaseTreeGroup[]
}

export interface TestCaseTreeResponse {
  products: TestCaseTreeProduct[]
  total: number
}

export interface ExecutionStatusResponse {
  max_sessions: number
  active_ssh_sessions: number
  observer_clients: number
  running_tests: number
  waiting_input_tests: number
  queued_tests: number
  available_sessions: number
}

export type TestExecutionStatus =
  | 'created'
  | 'running'
  | 'waiting_input'
  | 'passed'
  | 'failed'
  | 'error'
  | 'timeout'
  | 'stopped'

export interface TestExecutionEvent {
  type: string
  node_id?: string | null
  value?: string | null
  message?: string | null
  created_at: string
}

export interface TestExecutionRun {
  id: string
  case_id: string
  case_name: string
  command: string
  status: TestExecutionStatus
  device_ip?: string | null
  current_node_id?: string | null
  waiting_node_id?: string | null
  waiting_input_kind?: TestInputKind | null
  waiting_options: TestCaseInputOption[]
  events: TestExecutionEvent[]
  created_at: string
  updated_at: string
}

export const testCaseService = {
  getTree: () => api.get<TestCaseTreeResponse>('/test-cases/tree'),
  createProduct: (payload: TestProductCreatePayload) => api.post<TestProduct>('/test-products', payload),
  createType: (productId: string, payload: TestTypeCreatePayload) =>
    api.post<TestType>(`/test-products/${productId}/types`, payload),
  listCases: (params?: { productId?: string; testType?: string; includeArchived?: boolean }) =>
    api.get<TestCaseListResponse>('/test-cases', {
      params: {
        product_id: params?.productId,
        test_type: params?.testType,
        include_archived: params?.includeArchived
      }
    }),
  getCase: (caseId: string) => api.get<TestCase>(`/test-cases/${caseId}`),
  createCase: (payload: TestCaseCreatePayload) => api.post<TestCase>('/test-cases', payload),
  updateCase: (caseId: string, payload: TestCaseUpdatePayload) =>
    api.put<TestCase>(`/test-cases/${caseId}`, payload),
  archiveCase: (caseId: string) => api.delete<TestCase>(`/test-cases/${caseId}`),
  getExecutionStatus: () => api.get<ExecutionStatusResponse>('/test-execution/status'),
  startExecution: (payload: { case_id: string; device_ip?: string | null }) =>
    api.post<TestExecutionRun>('/test-execution/runs', payload),
  getExecutionRun: (runId: string) => api.get<TestExecutionRun>(`/test-execution/runs/${runId}`),
  setExecutionCurrentNode: (runId: string, nodeId: string) =>
    api.post<TestExecutionRun>(`/test-execution/runs/${runId}/current-node`, { node_id: nodeId }),
  waitExecutionInput: (
    runId: string,
    payload: {
      node_id: string
      expect?: string | null
      input_kind: TestInputKind
      input_options: TestCaseInputOption[]
    }
  ) => api.post<TestExecutionRun>(`/test-execution/runs/${runId}/wait-input`, payload),
  submitExecutionInput: (runId: string, payload: { node_id: string; value: string }) =>
    api.post<TestExecutionRun>(`/test-execution/runs/${runId}/input`, payload),
  stopExecution: (runId: string) =>
    api.post<TestExecutionRun>(`/test-execution/runs/${runId}/stop`),
  completeExecution: (runId: string, payload: { status: Exclude<TestExecutionStatus, 'created' | 'running' | 'waiting_input'>; message?: string | null }) =>
    api.post<TestExecutionRun>(`/test-execution/runs/${runId}/complete`, payload)
}
