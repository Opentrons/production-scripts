import { authenticatedFetch, csrfHeaders } from '@/scripts/api/http'
import { i18n } from '@/i18n'

const AGENT_API_BASE = '/api/agent'

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string | { message?: string }; message?: string }
    return (typeof payload.detail === 'string' ? payload.detail : payload.detail?.message)
      || payload.message
      || i18n.global.t('agent.httpFailed', { status: response.status })
  } catch {
    return i18n.global.t('agent.httpFailed', { status: response.status })
  }
}

export interface KnowledgeDocument {
  id: string
  title: string
  content: string
  category: string
  tags: string[]
  source: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface KnowledgeListResponse {
  documents: KnowledgeDocument[]
  total: number
  storage: string
  query?: string
}

export interface KnowledgeImportResponse {
  imported: KnowledgeDocument[]
  imported_count: number
  errors: string[]
  storage: string
}

export interface AgentSchedule {
  id: string
  name: string
  description: string
  enabled: boolean
  schedule_kind: 'interval' | 'daily'
  interval_minutes: number
  daily_time: string | null
  next_run_at: string | null
  last_run_at: string | null
  last_status: 'success' | 'failed' | 'running' | null
  last_result_preview: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface AgentScheduleInput {
  name: string
  description: string
  enabled: boolean
  schedule_kind: 'interval' | 'daily'
  interval_minutes: number
  daily_time?: string | null
}

export interface AgentScheduleRun {
  id: string
  schedule_id: string
  schedule_name: string
  description: string
  status: 'success' | 'failed' | 'running'
  trigger: 'scheduled' | 'manual'
  result: string
  error: string | null
  started_at: string
  finished_at: string | null
}

export interface ProtocolAnalysisEnvironment {
  available: boolean
  root: string | null
  python: string | null
  detail: string
  candidates: string[]
  versions: string[]
  default_version: string | null
  selected_version: string | null
}

export interface ProtocolRuntimeParameter {
  displayName?: string
  variableName: string
  description?: string
  type: string
  value?: boolean | number | string | null
  default?: boolean | number | string | null
  minimum?: number
  maximum?: number
  unit?: string
  choices?: Array<{ displayName: string; value: boolean | number | string }>
  file?: { id?: string; name?: string } | null
}

export interface ProtocolAnalysisErrorItem {
  id?: string | null
  errorType?: string | null
  detail: string
  errorCode?: string | null
}

export interface ProtocolAnalysisResult {
  session_id: string
  protocol_name: string
  filenames: string[]
  result: 'ok' | 'not-ok' | 'parameter-value-required' | 'error' | string
  robot_type: string | null
  metadata: Record<string, unknown>
  run_time_parameters: ProtocolRuntimeParameter[]
  errors: ProtocolAnalysisErrorItem[]
  command_count: number
  labware_count: number
  pipette_count: number
  module_count: number
  liquid_count: number
  analysis: Record<string, unknown>
  opentrons_root: string | null
  opentrons_version: string | null
  stderr: string | null
}

export interface OddRemoteDevice {
  ip: string
  api_port: number
  name: string
  robot_model?: string | null
  robot_type?: string | null
  version?: string | null
  service_status?: string | null
  odd_devtools_port: number
  odd_available: boolean
  odd_title?: string | null
  odd_browser?: string | null
  odd_detail?: string | null
  odd_origin?: string | null
}

export interface OddRemoteDeviceList {
  devtools_port: number
  robot_api_port: number
  total: number
  odd_ready_count: number
  devices: OddRemoteDevice[]
  hint: string
}

export interface OddRemoteSessionInfo {
  ip: string
  port: number
  origin: string
  browser?: string | null
  protocol_version?: string | null
  title?: string | null
  url?: string | null
  webSocketDebuggerUrl?: string | null
  inspector_url?: string | null
  width?: number | null
  height?: number | null
}

export const agentProtocolAnalysisApi = {
  async environment(): Promise<ProtocolAnalysisEnvironment> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/environment`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as ProtocolAnalysisEnvironment
  },

  async listOddDevices(): Promise<OddRemoteDeviceList> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/odd-devices`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as OddRemoteDeviceList
  },

  async oddSession(ip: string, port = 9223): Promise<OddRemoteSessionInfo> {
    const params = new URLSearchParams({ ip, port: String(port) })
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/odd-session?${params}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as OddRemoteSessionInfo
  },

  async oddProbe(ip: string, port = 9223): Promise<{ available: boolean; detail?: string; title?: string | null }> {
    const params = new URLSearchParams({ ip, port: String(port) })
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/odd-probe?${params}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json()
  },

  async oddMetrics(ip: string, port = 9223): Promise<{ ip: string; port: number; width: number; height: number; title?: string | null }> {
    const params = new URLSearchParams({ ip, port: String(port) })
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/odd-metrics?${params}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json()
  },

  async oddInput(payload: {
    ip: string
    port?: number
    type: string
    x: number
    y: number
    button?: string
    clickCount?: number
    deltaX?: number
    deltaY?: number
    steps?: number
  }): Promise<{ ok: boolean; width?: number; height?: number; x?: number; y?: number }> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/odd-input`, {
      method: 'POST',
      headers: {
        ...csrfHeaders('POST'),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        port: 9223,
        button: 'left',
        clickCount: 1,
        deltaX: 0,
        deltaY: 0,
        steps: 8,
        ...payload,
      }),
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json()
  },

  oddScreenshotUrl(ip: string, port = 9223, quality = 55) {
    const params = new URLSearchParams({
      ip,
      port: String(port),
      quality: String(quality),
      t: String(Date.now()),
    })
    return `${AGENT_API_BASE}/protocol-analysis/odd-screenshot?${params}`
  },

  oddStreamUrl(ip: string, port = 9223, quality = 45) {
    const params = new URLSearchParams({
      ip,
      port: String(port),
      quality: String(quality),
    })
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${AGENT_API_BASE}/protocol-analysis/odd-stream?${params}`
  },

  async fetchOddScreenshot(ip: string, port = 9223, quality = 55): Promise<Blob> {
    const response = await authenticatedFetch(
      `${AGENT_API_BASE}/protocol-analysis/odd-screenshot?${new URLSearchParams({
        ip,
        port: String(port),
        quality: String(quality),
      })}`,
      { cache: 'no-store' },
    )
    if (!response.ok) throw new Error(await responseError(response))
    return await response.blob()
  },

  async analyze(payload: {
    protocolFiles: File[]
    labwareFiles?: File[]
    rtpValues?: Record<string, boolean | number | string>
    csvFiles?: Array<{ variableName: string; file: File }>
    opentronsVersion?: string
  }): Promise<ProtocolAnalysisResult> {
    const form = new FormData()
    for (const file of payload.protocolFiles) form.append('protocol_files', file)
    for (const file of payload.labwareFiles || []) form.append('labware_files', file)
    form.set('rtp_values', JSON.stringify(payload.rtpValues || {}))
    if (payload.opentronsVersion) form.set('opentrons_version', payload.opentronsVersion)
    for (const item of payload.csvFiles || []) {
      form.append('csv_variable_names', item.variableName)
      form.append('csv_files', item.file)
    }
    const response = await authenticatedFetch(`${AGENT_API_BASE}/protocol-analysis/analyze`, {
      method: 'POST',
      headers: csrfHeaders('POST'),
      body: form,
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as ProtocolAnalysisResult
  },
}

export const agentKnowledgeApi = {
  async list(query = '', category = ''): Promise<KnowledgeListResponse> {
    const params = new URLSearchParams()
    if (query.trim()) params.set('query', query.trim())
    if (category.trim()) params.set('category', category.trim())
    params.set('limit', '100')
    const response = await authenticatedFetch(`${AGENT_API_BASE}/knowledge?${params}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as KnowledgeListResponse
  },

  async save(payload: {
    title: string
    content: string
    category?: string
    tags?: string[]
    source?: string
  }, documentId = ''): Promise<KnowledgeDocument> {
    const params = documentId ? `?document_id=${encodeURIComponent(documentId)}` : ''
    const response = await authenticatedFetch(`${AGENT_API_BASE}/knowledge${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...csrfHeaders('POST') },
      body: JSON.stringify({
        title: payload.title,
        content: payload.content,
        category: payload.category || 'general',
        tags: payload.tags || [],
        source: payload.source || 'manual',
        metadata: {},
      }),
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as KnowledgeDocument
  },

  async importFiles(files: File[], category = 'imported'): Promise<KnowledgeImportResponse> {
    const form = new FormData()
    form.set('category', category)
    for (const file of files) form.append('files', file)
    const response = await authenticatedFetch(`${AGENT_API_BASE}/knowledge/import`, {
      method: 'POST',
      headers: csrfHeaders('POST'),
      body: form,
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as KnowledgeImportResponse
  },

  async remove(documentId: string): Promise<void> {
    const response = await authenticatedFetch(
      `${AGENT_API_BASE}/knowledge/${encodeURIComponent(documentId)}?confirm=true`,
      { method: 'DELETE', headers: csrfHeaders('DELETE') },
    )
    if (!response.ok) throw new Error(await responseError(response))
  },
}

export const agentScheduleApi = {
  async list(): Promise<{ items: AgentSchedule[]; total: number; storage: string }> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedules`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json()
  },

  async create(payload: AgentScheduleInput): Promise<AgentSchedule> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...csrfHeaders('POST') },
      body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as AgentSchedule
  },

  async update(scheduleId: string, payload: AgentScheduleInput): Promise<AgentSchedule> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedules/${encodeURIComponent(scheduleId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...csrfHeaders('PUT') },
      body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as AgentSchedule
  },

  async remove(scheduleId: string): Promise<void> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedules/${encodeURIComponent(scheduleId)}`, {
      method: 'DELETE',
      headers: csrfHeaders('DELETE'),
    })
    if (!response.ok) throw new Error(await responseError(response))
  },

  async runNow(scheduleId: string): Promise<AgentScheduleRun> {
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedules/${encodeURIComponent(scheduleId)}/run`, {
      method: 'POST',
      headers: csrfHeaders('POST'),
    })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json() as AgentScheduleRun
  },

  async listRuns(scheduleId = '', limit = 30): Promise<{ items: AgentScheduleRun[]; total: number }> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (scheduleId) params.set('schedule_id', scheduleId)
    const response = await authenticatedFetch(`${AGENT_API_BASE}/schedule-runs?${params}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(await responseError(response))
    return await response.json()
  },
}
