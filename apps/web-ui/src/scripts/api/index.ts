import { API_BASE_URL, createApiClient } from '@/scripts/api/http'
import type {
  HealthCheckResponse,
  TestDataResponse,
  MessagesResponse,
  CollectionsResponse,
  CollectionDataResponse,
  CollectionFilterOptionsResponse,
  DataLinksResponse,
  DataAnalysisResponse,
  DataAnalysisOnlinePayload,
  DataAnalysisSpecItem,
  DataAnalysisSpecResponse,
  ProductManagementFilterOptionsResponse,
  ProductManagementListResponse,
  ProductManagementManualAddPayload,
  ProductManagementManualAddResponse,
  ProductManagementSyncResponse,
  ProductStatusUpdateResponse,
  UnitTrackerOptionsResponse,
  UnitTrackerRowsResponse,
  UnitTrackerSource,
  UnitTrackerSyncResponse,
  UploadDataResponse,
  UploadFinishSettingPayload,
  UploadFinishSettingItem,
  UploadFinishSettingsResponse,
  UploadRecordFilterOptionsResponse,
  UploadRecordStatsResponse,
  UploadRecordsResponse,
  InformationKind,
  InformationFilesResponse
} from '@/scripts/types'

const api = createApiClient(15000)

export interface RobotInfo {
  ip: string
  port: number
  online: boolean
  service_status: 'normal' | 'error' | 'unknown'
  version?: string
  name?: string
  robot_type?: string
  robot_model?: string
  serial_number?: string
  error?: string
  api_version?: string
  min_api_version?: string
  max_api_version?: string
  fw_version?: string
  health_fetch_failed?: boolean
}

export interface RobotCommandRequest {
  ips: string[]
  port?: number
  method?: string
  path: string
  body?: Record<string, unknown>
  timeout?: number
}

export interface RobotCommandResult {
  ip: string
  success: boolean
  status_code?: number
  response?: unknown
  error?: string
}

export interface RobotBatchCommandResponse {
  results: RobotCommandResult[]
}

export type RobotVersionProductType =
  | 'robot'
  | 'pipette_single_channel'
  | 'pipette_8_channels'
  | 'pipette_96_channels_200ul'
  | 'pipette_96_channels_1000ul'
  | 'gripper'

export interface RobotVersionProduct {
  key: RobotVersionProductType
  label: string
  test_names: string[]
}

export interface RobotSubsystemVersion {
  name: string
  firmware_version: string
  next_firmware_version: string
  revision: string
  ok: boolean | null
  fw_update_needed: boolean | null
}

export interface RobotInstrumentVersion {
  name: string
  model: string
  type: string
  mount: string
  subsystem: string
  firmware_version: string
  ok: boolean | null
}

export interface RobotVersionTestEntry {
  test_name: string
  sn: string
  robot_ip: string
  test_version: string
  queried_at: string
  robot?: Record<string, unknown>
  subsystems?: RobotSubsystemVersion[]
  instrument?: RobotInstrumentVersion
}

export interface RobotVersionHistoryRecord {
  _id: string
  barcode: string
  sn: string
  product_type: RobotVersionProductType
  product_name: string
  robot_ip: string
  tests: Record<string, RobotVersionTestEntry>
  created_at: string
  updated_at: string
}

export interface RobotCurrentVersionsResponse {
  ip: string
  port: number
  barcode: string
  test_version: string
  queried_at: string
  robot: Record<string, unknown>
  subsystems: RobotSubsystemVersion[]
}

export interface RobotVersionCaptureResponse {
  success: boolean
  created: boolean
  storage: 'mongodb' | 'sqlite'
  test_key: string
  test: RobotVersionTestEntry
  record: RobotVersionHistoryRecord
}

export interface RobotVersionHistoryResponse {
  records: RobotVersionHistoryRecord[]
  total: number
  page: number
  page_size: number
  storage: 'mongodb' | 'sqlite'
}

export interface RobotSshCommand {
  id: string
  name: string
  command: string
  description?: string
  source: 'builtin' | 'custom'
  tag: 'general' | 'risk'
  created_at?: string
  updated_at?: string
}

export interface RobotSshCommandListResponse {
  builtin_commands: RobotSshCommand[]
  custom_commands: RobotSshCommand[]
  database_available: boolean
  error?: string | null
}

export interface RobotSshCommandExecuteResult {
  ip: string
  command: string
  environment: Record<string, string>
  success: boolean
  exit_code: number | null
  stdout: string
  stderr: string
  error?: string
  output_truncated: boolean
  started_at: string
  finished_at: string
  duration_ms: number
}

export interface RobotSshCommandBatchExecuteResponse {
  results: RobotSshCommandExecuteResult[]
  total: number
  success_count: number
  failed_count: number
  concurrency: number
}

export interface RobotSshKeyInstallResult {
  ip: string
  success: boolean
  message: string
  exit_code: number | null
  stdout: string
  stderr: string
  output_truncated: boolean
  started_at: string
  finished_at: string
  duration_ms: number
}

export interface RobotSshKeyInstallResponse {
  results: RobotSshKeyInstallResult[]
  total: number
  success_count: number
  failed_count: number
  concurrency: number
}

export interface RobotCodeFlashPreset {
  id: string
  name: string
  description: string
  command: string
}

export interface RobotCodeFlashBranch {
  name: string
  current: boolean
  local: boolean
  remote: boolean
}

export interface RobotCodeFlashPresetsResponse {
  presets: RobotCodeFlashPreset[]
  workdir: string
  available: boolean
  error?: string | null
  current_branch: string
  branches: RobotCodeFlashBranch[]
  clean: boolean
  dirty_files: string[]
}

export type RobotCodeFlashStatus = 'queued' | 'running' | 'success' | 'failed'

export interface RobotCodeFlashTask {
  task_id: string
  ip: string
  status: RobotCodeFlashStatus
  success: boolean | null
  message: string
  command: string
  workdir: string
  branch: string
  pull: boolean
  timeout: number
  logs: string[]
  output_truncated: boolean
  exit_code: number | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms: number
}

export interface RobotScanResponse {
  total: number
  online_count: number
  offline_count: number
  abnormal_count?: number
  scan_network?: string
  server_ip?: string
  gateway?: string
  scan_gateways?: string[]
  online_robots: RobotInfo[]
  offline_robots: RobotInfo[]
  abnormal_robots?: RobotInfo[]
  cached_at?: string | null
  scan_started_at?: string | null
  scan_duration_ms?: number | null
  refreshing?: boolean
  last_error?: string | null
}

export interface RobotScanParams {
  port?: number
  network?: string
}

export interface RobotScanGateway {
  gateway: string
  scan_range: string
  created_at?: string | null
  updated_at?: string | null
}

export interface RobotScanGatewaysResponse {
  gateways: RobotScanGateway[]
}

export type ProtocolMonitorStatus = 'idle' | 'offline' | 'running'

export interface ProtocolMonitorDevice {
  id: string
  name: string
  description: string
  ip: string
  port: number
  created_at: string
  updated_at: string
}

export interface ProtocolMonitorRoom {
  id: string
  name: string
  devices: ProtocolMonitorDevice[]
  created_at: string
  updated_at: string
}

export interface ProtocolMonitorDeviceStatus {
  device_id: string
  status: ProtocolMonitorStatus
  app_version?: string | null
  run_status?: string | null
  run_id?: string | null
  protocol_id?: string | null
  protocol_name?: string | null
  checked_at: string
  error?: string | null
}

export interface ProtocolMonitorRoomsResponse {
  rooms: ProtocolMonitorRoom[]
  storage: 'mongodb' | 'sqlite'
}

export interface ProtocolMonitorStatusResponse {
  room_id: string
  statuses: ProtocolMonitorDeviceStatus[]
  checked_at: string
}

export interface RobotControlSummary {
  ip: string
  port: number
  http_connected: boolean
  ssh_connected: boolean
  health: Record<string, unknown> | null
  instruments: Record<string, unknown> | null
  modules: Record<string, unknown> | null
  positions: Record<string, unknown> | null
  errors: string[]
}

export interface RobotFileEntry {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified_at: number | null
}

export interface RobotFileListResponse {
  path: string
  entries: RobotFileEntry[]
}

export interface RobotActionResponse {
  success: boolean
  message?: string
  data?: Record<string, unknown>
}

export interface RobotBarcodeTarget {
  id: string
  kind: 'robot' | 'pipette' | 'gripper' | 'hepauv' | 'module' | string
  label: string
  mount?: string | null
  slot?: string | null
  product?: string | null
  current_serial?: string | null
  provisionable: boolean
  script?: string | null
  hint?: string | null
  reason?: string | null
}

export interface RobotBarcodeTargetsResponse {
  ip: string
  port: number
  http_connected: boolean
  ssh_connected: boolean
  simulating?: boolean
  targets: RobotBarcodeTarget[]
  errors: string[]
}

export interface RobotLogFolderOption {
  key: string
  label: string
  description: string
  default_selected: boolean
}

export interface RobotLogFolderOptionsResponse {
  folders: RobotLogFolderOption[]
  download_root: string
  max_concurrency: number
}

export type RobotLogDownloadStatus =
  | 'queued'
  | 'running'
  | 'success'
  | 'warning'
  | 'failed'
  | 'completed'
  | 'completed_with_warnings'
  | 'completed_with_errors'

export interface RobotLogCommandEntry {
  id: string
  label: string
  command: string
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at?: string | null
  output?: string
  error?: string | null
}

export interface RobotLogDownloadRecord {
  _id: string
  task_id: string
  robot_ip: string
  device_name: string
  selected_folders: Array<{ key: string; label: string; description?: string }>
  server_directory: string
  archive_path?: string | null
  archive_name?: string | null
  archive_size?: number
  status: RobotLogDownloadStatus
  progress: number
  current_step: string
  completed_steps: number
  total_steps: number
  started_at: string
  downloaded_at?: string | null
  finished_at?: string | null
  error?: string | null
  cleanup_status?: 'not_started' | 'running' | 'pending' | 'success' | 'invalid'
  cleanup_attempts?: number
  cleanup_error?: string | null
  cleanup_finished_at?: string | null
  command_logs: RobotLogCommandEntry[]
  file_available: boolean
  file_unavailable_reason?: string | null
  file_deleted_at?: string | null
}

export interface RobotLogDownloadTask {
  task_id: string
  status: RobotLogDownloadStatus
  concurrency?: number | null
  active_workers: number
  folder_keys: string[]
  folders: Array<{ key: string; label: string; description?: string }>
  total_devices: number
  completed_devices: number
  successful_devices: number
  warning_devices: number
  failed_devices: number
  progress: number
  started_at: string
  finished_at?: string | null
  devices: RobotLogDownloadRecord[]
}

export interface RobotLogDownloadRecordsResponse {
  records: RobotLogDownloadRecord[]
  total: number
  page: number
  page_size: number
}

export const healthApi = {
  getHealth: () => api.get<HealthCheckResponse>('/health'),
  refreshHealth: () => api.post<HealthCheckResponse>('/health/refresh')
}

export const protocolMonitorApi = {
  listRooms: () => api.get<ProtocolMonitorRoomsResponse>('/protocol-monitor/rooms'),
  createRoom: (name: string) =>
    api.post<ProtocolMonitorRoom>('/protocol-monitor/rooms', { name }),
  updateRoom: (roomId: string, name: string) =>
    api.put<ProtocolMonitorRoom>(`/protocol-monitor/rooms/${encodeURIComponent(roomId)}`, { name }),
  deleteRoom: (roomId: string) =>
    api.delete(`/protocol-monitor/rooms/${encodeURIComponent(roomId)}`),
  addDevice: (roomId: string, payload: { name: string; description: string; ip: string; port: number }) =>
    api.post<ProtocolMonitorRoom>(
      `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices`,
      payload
    ),
  updateDevice: (
    roomId: string,
    deviceId: string,
    payload: { name: string; description: string; ip: string; port: number }
  ) => api.put<ProtocolMonitorRoom>(
    `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}`,
    payload
  ),
  deleteDevice: (roomId: string, deviceId: string) =>
    api.delete<ProtocolMonitorRoom>(
      `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}`
    ),
  refreshRoomStatus: (roomId: string) =>
    api.post<ProtocolMonitorStatusResponse>(
      `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/status`,
      undefined,
      { timeout: 30000 }
    ),
  enableDeviceLivestream: (roomId: string, deviceId: string) =>
    api.post<{ enabled: boolean; idle_override: boolean; lease_id: string | null }>(
      `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}/livestream/enable`,
      undefined,
      { timeout: 40000 }
    ),
  releaseDeviceLivestream: (roomId: string, deviceId: string, leaseId: string) =>
    api.post<{ released: boolean; stopped: boolean }>(
      `/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}/livestream/${encodeURIComponent(leaseId)}/release`,
      undefined,
      { timeout: 40000 }
    ),
  deviceLivestreamReleaseUrl: (roomId: string, deviceId: string, leaseId: string) =>
    `${API_BASE_URL}/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}/livestream/${encodeURIComponent(leaseId)}/release`,
  deviceLivestreamUrl: (roomId: string, deviceId: string, leaseId = '') => {
    const base = `${API_BASE_URL}/protocol-monitor/rooms/${encodeURIComponent(roomId)}/devices/${encodeURIComponent(deviceId)}/livestream/stream.m3u8`
    return leaseId ? `${base}?lease_id=${encodeURIComponent(leaseId)}` : base
  },
}

export const robotApi = {
  scanRobots: (params?: RobotScanParams) =>
    api.post<RobotScanResponse>('/robots/scan', undefined, { params }),
  getRobots: (params?: RobotScanParams) => api.get<RobotScanResponse>('/robots', { params }),
  listScanGateways: () =>
    api.get<RobotScanGatewaysResponse>('/robots/scan-gateways'),
  addScanGateway: (gateway: string) =>
    api.post<RobotScanGateway>('/robots/scan-gateways', { gateway }),
  deleteScanGateway: (gateway: string) =>
    api.delete<RobotActionResponse>(`/robots/scan-gateways/${encodeURIComponent(gateway)}`),
  getRobotDetail: (ip: string, port?: number) => api.get<RobotInfo>(`/robot/${ip}`, { params: { port } }),
  getVersionProducts: () =>
    api.get<{ products: RobotVersionProduct[] }>('/robots/version-products'),
  getCurrentVersions: (ip: string, port?: number) =>
    api.get<RobotCurrentVersionsResponse>(`/robots/${encodeURIComponent(ip)}/versions/current`, { params: { port } }),
  captureVersion: (payload: {
    ip: string
    port?: number
    product_type: RobotVersionProductType
    test_name: string
  }) => api.post<RobotVersionCaptureResponse>('/robots/version-records', payload, { timeout: 0 }),
  getVersionHistory: (params?: { page?: number; page_size?: number }) =>
    api.get<RobotVersionHistoryResponse>('/robots/version-history', { params }),
  executeCommands: (payload: RobotCommandRequest) =>
    api.post<RobotBatchCommandResponse>('/robots/commands', payload, { timeout: 0 }),
  getSshCommands: () =>
    api.get<RobotSshCommandListResponse>('/robots/ssh-commands'),
  executeSshCommand: (payload: { ip: string; command: string; timeout?: number }) =>
    api.post<RobotSshCommandExecuteResult>('/robots/ssh-commands/execute', payload, { timeout: 0 }),
  executeBatchSshCommands: (payload: {
    ips: string[]
    command: string
    timeout?: number
    concurrency?: number
  }) => api.post<RobotSshCommandBatchExecuteResponse>('/robots/ssh-commands/batch-execute', payload, { timeout: 0 }),
  installSshKeys: (payload: {
    ips: string[]
    timeout?: number
    concurrency?: number
  }) => api.post<RobotSshKeyInstallResponse>('/robots/ssh-keys/install', payload, { timeout: 0 }),
  getCodeFlashPresets: () =>
    api.get<RobotCodeFlashPresetsResponse>('/robots/code-flash/presets'),
  createCodeFlashTask: (payload: {
    ip: string
    command: string
    timeout?: number
    branch: string
    pull: boolean
  }) =>
    api.post<RobotCodeFlashTask>('/robots/code-flash/tasks', payload, { timeout: 30000 }),
  getCodeFlashTask: (taskId: string) =>
    api.get<RobotCodeFlashTask>(`/robots/code-flash/tasks/${encodeURIComponent(taskId)}`),
  createSshCommand: (payload: {
    name: string
    command: string
    description?: string
    tag: 'general' | 'risk'
  }) =>
    api.post<RobotSshCommand>('/robots/ssh-commands', payload),
  updateSshCommand: (commandId: string, payload: {
    name: string
    command: string
    description?: string
    tag: 'general' | 'risk'
  }) =>
    api.put<RobotSshCommand>(`/robots/ssh-commands/${encodeURIComponent(commandId)}`, payload),
  deleteSshCommand: (commandId: string) =>
    api.delete<{ success: boolean; id: string }>(`/robots/ssh-commands/${encodeURIComponent(commandId)}`),
  getLogDownloadFolders: () =>
    api.get<RobotLogFolderOptionsResponse>('/robots/log-downloads/folders'),
  createLogDownloadTask: (payload: {
    devices: Array<{ ip: string; name?: string }>
    folder_keys: string[]
    concurrency: number
  }) => api.post<RobotLogDownloadTask>('/robots/log-downloads/tasks', payload, { timeout: 30000 }),
  getLogDownloadTask: (taskId: string) =>
    api.get<RobotLogDownloadTask>(`/robots/log-downloads/tasks/${encodeURIComponent(taskId)}`),
  getLogDownloadRecords: (params?: { page?: number; pageSize?: number; robotIp?: string }) =>
    api.get<RobotLogDownloadRecordsResponse>('/robots/log-downloads/records', {
      params: { page: params?.page, page_size: params?.pageSize, robot_ip: params?.robotIp }
    }),
  getServerLogDownloadUrl: (recordId: string) =>
    `/api/robots/log-downloads/records/${encodeURIComponent(recordId)}/file`,
  getAppLogDownloadUrl: (ip: string, port?: number) =>
    `/api/robots/${encodeURIComponent(ip)}/logs/app-download${port ? `?port=${port}` : ''}`,
  deleteServerLog: (recordId: string) =>
    api.delete<{
      success: boolean
      record_id: string
      already_deleted: boolean
      deleted_path: string
      file_deleted_at: string
    }>(`/robots/log-downloads/records/${encodeURIComponent(recordId)}/file`),
  getControlSummary: (ip: string, port?: number) =>
    api.get<RobotControlSummary>(`/robots/${ip}/control/summary`, { params: { port }, timeout: 30000 }),
  homeRobot: (ip: string, payload?: { target?: string; mount?: string; port?: number }) =>
    api.post<RobotActionResponse>(`/robots/${ip}/control/home`, payload ?? {}),
  moveRobot: (
    ip: string,
    payload: { target: string; point: number[]; mount: string; model?: string; port?: number }
  ) => api.post<RobotActionResponse>(`/robots/${ip}/control/move`, payload),
  resetRobot: (ip: string, payload: { axes: string[]; port?: number }) =>
    api.post<RobotActionResponse>(`/robots/${ip}/control/reset`, payload, { timeout: 0 }),
  createJogRun: (ip: string, port?: number) =>
    api.post<RobotActionResponse>(`/robots/${ip}/control/jog/runs`, { port: port ?? 31950 }, { timeout: 0 }),
  moveJogRobot: (ip: string, runId: string, payload: {
    direction: 'up' | 'down' | 'left' | 'right' | 'z_up' | 'z_down' | 'plunger_up' | 'plunger_down'
    step_mm: number
    mount: 'left' | 'right' | 'gripper'
    port?: number
  }) => api.post<RobotActionResponse>(
    `/robots/${ip}/control/jog/runs/${encodeURIComponent(runId)}/move`,
    payload,
    { timeout: 0 }
  ),
  dropJogTip: (ip: string, runId: string, payload: {
    pipette_id: string
    home_after?: boolean
    port?: number
  }) => api.post<RobotActionResponse>(
    `/robots/${ip}/control/jog/runs/${encodeURIComponent(runId)}/drop-tip`,
    payload,
    { timeout: 0 }
  ),
  controlJogGripper: (ip: string, runId: string, payload: {
    action: 'grip' | 'ungrip'
    port?: number
  }) => api.post<RobotActionResponse>(
    `/robots/${ip}/control/jog/runs/${encodeURIComponent(runId)}/gripper`,
    payload,
    { timeout: 0 }
  ),
  releaseJogRun: (ip: string, runId: string, port?: number) =>
    api.delete<RobotActionResponse>(`/robots/${ip}/control/jog/runs/${encodeURIComponent(runId)}`, {
      params: { port: port ?? 31950 },
      timeout: 0
    }),
  rebootRobot: (ip: string) => api.post<RobotActionResponse>(`/robots/${ip}/control/reboot`),
  getBarcodeTargets: (ip: string, port?: number) =>
    api.get<RobotBarcodeTargetsResponse>(`/robots/${ip}/barcode/targets`, {
      params: { port: port ?? 31950 },
      timeout: 30000
    }),
  provisionBarcode: (
    ip: string,
    payload: {
      kind: 'robot' | 'pipette' | 'gripper' | 'hepauv'
      serial: string
      mount?: 'left' | 'right'
      target_id?: string
      port?: number
    }
  ) =>
    api.post<RobotActionResponse>(`/robots/${ip}/barcode/provision`, payload, {
      timeout: 0
    }),
  listFiles: (ip: string, path = '/') =>
    api.get<RobotFileListResponse>(`/robots/${ip}/files`, { params: { path }, timeout: 30000 }),
  readFile: (ip: string, path: string) =>
    api.get<{ path: string; content: string }>(`/robots/${ip}/files/content`, { params: { path } }),
  writeFile: (ip: string, path: string, content: string, options?: { createIfMissing?: boolean }) =>
    api.put<RobotActionResponse>(`/robots/${ip}/files/content`, {
      path,
      content,
      create_if_missing: options?.createIfMissing ?? true
    }),
  uploadFile: (ip: string, path: string, file: File) => {
    const formData = new FormData()
    formData.append('path', path)
    formData.append('file', file)
    return api.post<RobotActionResponse>(`/robots/${ip}/files/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0
    })
  },
  deleteFile: (ip: string, path: string) =>
    api.delete<RobotActionResponse>(`/robots/${ip}/files`, { params: { path } }),
  downloadFile: (ip: string, path: string) =>
    api.get<Blob>(`/robots/${ip}/files/download`, { params: { path }, responseType: 'blob', timeout: 0 }),
  listTestingData: (ip: string, path?: string) =>
    api.get<RobotFileListResponse>(`/robots/${ip}/testing-data`, {
      params: path ? { path } : undefined,
      timeout: 30000
    }),
  downloadTestingData: (ip: string, paths: string[]) =>
    api.post<Blob>(`/robots/${ip}/testing-data/download`, { paths }, {
      responseType: 'blob',
      timeout: 0
    }),
  deleteTestingData: (ip: string, paths: string[]) =>
    api.delete<RobotActionResponse>(`/robots/${ip}/testing-data`, { data: { paths }, timeout: 0 }),
  listProtocols: (ip: string, port?: number) =>
    api.get<{ protocols: Record<string, unknown>[] }>(`/robots/${ip}/protocols`, { params: { port } }),
  downloadProtocol: (
    ip: string,
    protocolId: string,
    format: 'json' | 'source' = 'json',
    port?: number
  ) =>
    api.get<Blob>(`/robots/${ip}/protocols/${protocolId}/download`, {
      params: { port, format },
      responseType: 'blob',
      timeout: 0
    }),
  uploadProtocol: (ip: string, files: File[], options?: { key?: string; protocolKind?: string; port?: number }) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    if (options?.key) formData.append('key', options.key)
    if (options?.protocolKind) formData.append('protocol_kind', options.protocolKind)
    return api.post<RobotActionResponse>(`/robots/${ip}/protocols/upload`, formData, {
      params: options?.port ? { port: options.port } : undefined,
      timeout: 0,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  analyzeProtocol: (ip: string, protocolId: string, body?: Record<string, unknown>, port?: number) =>
    api.post<RobotActionResponse>(`/robots/${ip}/protocols/${protocolId}/analyze`, { body, port }),
  getProtocolAnalyses: (ip: string, protocolId: string, port?: number) =>
    api.get<RobotActionResponse>(`/robots/${ip}/protocols/${protocolId}/analyses`, { params: { port } }),
  listDataFiles: (ip: string, port?: number) =>
    api.get<RobotActionResponse>(`/robots/${ip}/data-files`, { params: { port } }),
  listProtocolDataFiles: (ip: string, protocolId: string, port?: number) =>
    api.get<RobotActionResponse>(`/robots/${ip}/protocols/${protocolId}/data-files`, { params: { port } }),
  uploadDataFile: (ip: string, file: File, port?: number) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<RobotActionResponse>(`/robots/${ip}/data-files/upload`, formData, {
      params: port ? { port } : undefined,
      timeout: 0,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listRuns: (ip: string, port?: number) =>
    api.get<{ runs: Record<string, unknown>[] }>(`/robots/${ip}/runs`, { params: { port } }),
  createRun: (ip: string, protocolId: string, port?: number) =>
    api.post<RobotActionResponse>(`/robots/${ip}/runs`, { protocol_id: protocolId, port }),
  controlRun: (ip: string, runId: string, actionType: string, port?: number) =>
    api.post<RobotActionResponse>(`/robots/${ip}/runs/${runId}/actions`, {
      action_type: actionType,
      port
    })
}

export const testDataApi = {
  getTestData: (params?: { page?: number; pageSize?: number; testType?: string }) => 
    api.get<TestDataResponse>('/test-data', { params })
}

export const messageApi = {
  getMessages: () => api.get<MessagesResponse>('/messages'),
  markAsRead: (messageId: string) => api.put(`/messages/${messageId}/read`),
  markAllAsRead: () => api.put('/messages/read-all')
}

export const collectionApi = {
  getCollections: () => api.get<CollectionsResponse>('/collections'),
  getCollectionData: (
    collectionName: string,
    page: number = 1,
    pageSize: number = 20,
    filters?: {
      model?: string
      type?: string
      totalResult?: string
      barcode?: string
      startDate?: string
      endDate?: string
    }
  ) =>
    api.get<CollectionDataResponse>('/collection-data', { 
      params: {
        collection_name: collectionName,
        page,
        page_size: pageSize,
        model: filters?.model,
        type: filters?.type,
        total_result: filters?.totalResult,
        barcode: filters?.barcode,
        start_date: filters?.startDate,
        end_date: filters?.endDate
      }
    }),
  getCollectionFilterOptions: (collectionName: string) =>
    api.get<CollectionFilterOptionsResponse>('/collection-filter-options', {
      params: { collection_name: collectionName }
    })
}

export const dataLinksApi = {
  getDataLinks: () => api.get<DataLinksResponse>('/data-links')
}

export const informationApi = {
  getFiles: (kind: InformationKind, refresh = false) =>
    api.get<InformationFilesResponse>(`/information/${kind}`, {
      params: refresh ? { refresh: true } : undefined
    })
}

export const dataAnalysisApi = {
  getSpecs: () => api.get<DataAnalysisSpecResponse>('/data-analysis/specs'),
  saveGravimetricSpec: (payload: DataAnalysisSpecItem) =>
    api.put<DataAnalysisSpecItem>('/data-analysis/specs/gravimetric', payload),
  analyzeFiles: (files: File[]) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return api.post<DataAnalysisResponse>('/data-analysis/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0
    })
  },
  analyzePaths: (filePaths: string[]) =>
    api.post<DataAnalysisResponse>('/data-analysis/analyze-paths', { file_paths: filePaths }, { timeout: 0 }),
  analyzeOnline: (payload: DataAnalysisOnlinePayload) =>
    api.post<DataAnalysisResponse>('/data-analysis/analyze-online', payload, { timeout: 0 })
}

export const productManagementApi = {
  getProducts: (params?: {
    page?: number
    pageSize?: number
    barcode?: string
    model?: string
    testType?: string
    status?: string
  }) =>
    api.get<ProductManagementListResponse>('/product-management/products', {
      params: {
        page: params?.page,
        page_size: params?.pageSize,
        barcode: params?.barcode,
        model: params?.model,
        test_type: params?.testType,
        status: params?.status
      }
    }),
  getFilterOptions: () =>
    api.get<ProductManagementFilterOptionsResponse>('/product-management/filter-options'),
  syncProducts: () =>
    api.post<ProductManagementSyncResponse>('/product-management/sync', {}, { timeout: 0 }),
  addManual: (payload: ProductManagementManualAddPayload) =>
    api.post<ProductManagementManualAddResponse>('/product-management/manual-add', payload),
  updateStatus: (barcode: string, status: string) =>
    api.put<ProductStatusUpdateResponse>('/product-management/product-status', { barcode, status })
}

export const uploadRecordApi = {
  getUploadRecords: (params?: {
    page?: number
    pageSize?: number
    recordId?: string
    status?: string
    model?: string
    barcode?: string
    startDate?: string
    endDate?: string
  }) =>
    api.get<UploadRecordsResponse>('/upload-records', {
      params: {
        page: params?.page,
        page_size: params?.pageSize,
        record_id: params?.recordId,
        status: params?.status,
        model: params?.model,
        barcode: params?.barcode,
        start_date: params?.startDate,
        end_date: params?.endDate
      }
    }),
  getUploadRecordStats: (params?: {
    recordId?: string
    status?: string
    model?: string
    barcode?: string
    startDate?: string
    endDate?: string
  }) =>
    api.get<UploadRecordStatsResponse>('/upload-record-stats', {
      params: {
        record_id: params?.recordId,
        status: params?.status,
        model: params?.model,
        barcode: params?.barcode,
        start_date: params?.startDate,
        end_date: params?.endDate
      }
    }),
  getUploadRecordFilterOptions: () =>
    api.get<UploadRecordFilterOptionsResponse>('/upload-record-filter-options'),
  startUploadRecord: (payload: {
    csvFileName?: string
    zipFileName?: string
    source?: string
    idempotencyKey?: string
    csvSize?: number
    csvSha256?: string
  }) =>
    api.post<UploadDataResponse>('/upload-records/start', {
      csv_file_name: payload.csvFileName || '',
      zip_file_name: payload.zipFileName,
      source: payload.source || 'web',
      idempotency_key: payload.idempotencyKey,
      csv_size: payload.csvSize,
      csv_sha256: payload.csvSha256
    }),
  markUploadRecordFailed: (
    recordId: string,
    payload: { failureStage?: string; failureCode?: string; message: string; detail?: string }
  ) =>
    api.post<UploadDataResponse>(`/upload-records/${encodeURIComponent(recordId)}/fail`, {
      failure_stage: payload.failureStage || 'request_transport',
      failure_code: payload.failureCode || 'client_request_failed',
      message: payload.message,
      detail: payload.detail || payload.message
    }),
  getUnitTrackerOptions: () =>
    api.get<UnitTrackerOptionsResponse>('/unit-tracker/options'),
  getUnitTrackerRows: (params?: {
    page?: number
    pageSize?: number
    product?: string
    testType?: string
    barcode?: string
    source?: UnitTrackerSource
    refresh?: boolean
  }) =>
    api.get<UnitTrackerRowsResponse>('/unit-tracker/rows', {
      params: {
        page: params?.page,
        page_size: params?.pageSize,
        product: params?.product,
        test_type: params?.testType,
        barcode: params?.barcode,
        source: params?.source,
        refresh: params?.refresh
      }
    }),
  syncUnitTrackerRows: (limit?: number) =>
    api.post<UnitTrackerSyncResponse>('/unit-tracker/sync', {}, { params: { limit }, timeout: 0 }),
  uploadManualData: (
    csvFile: File,
    includeSourceZip: boolean,
    allFiles = false,
    meta?: Record<string, unknown>,
    recordId?: string
  ) => {
    const formData = new FormData()
    formData.append('csv_file', csvFile)
    formData.append('include_source_zip', String(includeSourceZip))
    formData.append('all_files', String(allFiles))
    if (recordId) formData.append('record_id', recordId)
    if (meta && Object.keys(meta).length > 0) {
      formData.append('meta', JSON.stringify(meta))
    }
    return api.post<UploadDataResponse>('/upload-data/manual', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0
    })
  }
}

export const settingsApi = {
  getUploadFinishSettings: () =>
    api.get<UploadFinishSettingsResponse>('/settings/upload/finish'),
  updateUploadFinishSetting: (payload: UploadFinishSettingPayload) =>
    api.put<UploadFinishSettingItem>('/settings/upload/finish', payload),
  getSimulatingStatus: () =>
    api.get<SimulatingStatusResponse>('/system/simulating'),
  updateSimulatingStatus: (simulating: boolean) =>
    api.put<SimulatingStatusResponse>('/system/simulating', { simulating })
}

export interface SimulatingStatusResponse {
  simulating: boolean
  persistence: string
  auth_persistence?: string
  device_scan_mode?: string
  db_root: string
  active_db_dir: string
  business_db_dir: string
  simulating_db_dir: string
  platform_db_path: string
  auth_db_path?: string
}

export default api
