import { createApiClient } from './http'

export type FailureKind = 'test_failure' | 'runtime_error' | 'mixed' | 'incomplete'
export type AttachmentKind = 'json' | 'log' | 'encoder'
export type FailureConfirmationFilter = 'all' | 'pending' | 'confirmed'
export interface FailureConfirmationCoverage {
  report_id: string
  revision: string
  report_folder: string | null
  source_name: string | null
  report_role: string | null
  test_time: string | null
  current: boolean
  metadata_recorded: boolean
}
export interface FailureConfirmation {
  id: string
  text: string
  created_by: string
  created_by_name: string
  created_at: string
  coverage?: FailureConfirmationCoverage[]
}
export interface FailureReportSummary {
  id: string
  report_folder: string
  sn: string
  report_run_id: string | null
  product?: string
  revision: string
  evidence_version?: string
  mode: string
  test_time: string | null
  kind: FailureKind
  stage: string
  report_role?: 'main' | 'right_reference'
  reference_tip_volume_ul?: number | null
  run_group_id?: string
  summary: string[]
  failure_count: number
  parse_status: 'ready' | 'log_only' | 'incomplete'
  source_format: string
  confirmation_status?: 'confirmed' | 'pending'
  covered_by?: string[]
}
export interface FailureDevice {
  id: string
  report_folder: string
  sn: string
  product: string
  last_test_at: string | null
  report_count: number
  unconfirmed_count: number
  failure_types: string[]
  summary: string[]
  summary_total?: number
  summary_omitted?: number
  matched_report_ids?: string[]
  version: string
  confirmation: FailureConfirmation | null
  recent_confirmations?: FailureConfirmation[]
  reports: FailureReportSummary[]
}
export interface FailureEvidence {
  evidence_id: string
  section: string
  tag: string
  index: number | string | null
  result: unknown
  data: unknown
  error_codes: string[]
  failure_reasons: string[]
  elapsed_seconds: number | null
}
export interface FailureRecommendation {
  category: string
  status: string
  evidence: unknown
  next_checks: unknown
  retest: unknown
}
export interface FailureReport extends FailureReportSummary {
  reference_handled?: boolean | null
  sn: string
  product: string
  failures: FailureEvidence[]
  tests: Record<string, { status: string; error?: unknown; blocking_stage?: string; last_handled_exception?: unknown }>
  runtime_error: Record<string, unknown> | null
  last_failure: Record<string, unknown> | null
  recommendations: FailureRecommendation[]
  warnings: string[]
  attachments: { kind: AttachmentKind; name: string; available: boolean; size: number }[]
  source_name: string
  identity: Record<string, unknown>
}
export interface FailureScan {
  running: boolean
  last_scan_at: string | null
  last_successful_scan_at?: string | null
  source_status?: 'unknown' | 'available' | 'degraded' | 'unavailable'
  error: string | null
  errors: { path: string; message: string }[]
  pending_files: number
}
export interface FailureDeviceQuery {
  q?: string
  product?: string
  date_from?: string
  date_to?: string
  mode?: string
  kind?: FailureKind | ''
  confirmation?: FailureConfirmationFilter
  page: number
  page_size: number
}
export interface FailureDevicesResponse {
  devices: FailureDevice[]
  total: number
  page: number
  page_size: number
  summary: { devices: number; pending: number; reports: number; parse_errors: number }
  options: { products: string[]; modes: string[] }
  facets: {
    all: FailureDeviceCounts
    products: (FailureDeviceCounts & { product: string })[]
    confirmation: FailureDeviceCounts
  }
  scan: FailureScan
}
export interface FailureDeviceCounts {
  total: number
  pending: number
  confirmed: number
}
export interface FailureAttachmentPreview {
  kind: AttachmentKind
  text?: string
  columns?: string[]
  rows?: string[][]
  truncated: boolean
}
export interface FailureReportLink {
  status: 'running' | 'matched' | 'not_found' | 'ambiguous' | 'unavailable' | 'missing_identity' | 'disabled'
  sn: string
  report_run_id: string | null
  checked_at: string | null
  stale: boolean
  matches: { url: string; sheet_title: string; sheet_id: number; row: number; source_url: string }[]
  error_code: string | null
}
export type FailureAnalysisStatus = 'idle' | 'running' | 'complete' | 'failed' | 'unsupported' | 'stale'
export interface FailureAnalysisFinding {
  finding_id: string
  category: string
  status: string
  observed: unknown
  checks: unknown
  direction: unknown
  retest: unknown
  evidence_refs: string[]
  threshold_evidence_refs?: string[]
  omitted_evidence_refs?: number
}
export interface FailureAnalysisAssessment {
  finding_id: string
  priority: number
  reasoning: string
  next_question: string
  evidence_refs: string[]
}
export interface FailureAnalysis {
  status: FailureAnalysisStatus
  report_id: string
  report_revision: string
  generated_at: string | null
  mode: 'rules_only' | 'model'
  error: string | null
  result: {
    evidence: {
      deterministic_findings: FailureAnalysisFinding[]
      blocked_tests: { evidence_ref: string; status: string; tip_volume_ul?: number; blocked_by?: unknown; original_result?: string; numeric_values_are_placeholders?: boolean }[]
      limitations: string[]
      evidence_catalog: Record<string, unknown>
    }
    model_analysis: { status: string; model?: string; assessments: FailureAnalysisAssessment[] }
  } | null
}

const client = createApiClient(30000)
const base = '/defect-search/test-failures'
const reportPath = (id: string) => `${base}/reports/${encodeURIComponent(id)}`
export const testFailuresApi = {
  devices: (params: FailureDeviceQuery, signal?: AbortSignal) => client.get<FailureDevicesResponse>(`${base}/devices`, {
    params: Object.fromEntries(Object.entries(params).filter(([, value]) => value !== '' && value != null)), signal,
  }),
  report: (id: string, signal?: AbortSignal) => client.get<FailureReport>(reportPath(id), { signal }),
  reportLink: (id: string, signal?: AbortSignal) => client.get<FailureReportLink>(`${reportPath(id)}/report-link`, { signal }),
  refreshReportLink: (id: string, signal?: AbortSignal) => client.post<FailureReportLink>(`${reportPath(id)}/report-link`, {}, { signal }),
  analysis: (id: string, signal?: AbortSignal) => client.get<FailureAnalysis>(`${reportPath(id)}/analysis`, { signal }),
  startAnalysis: (id: string, reportRevision: string, signal?: AbortSignal, force = false) => client.post<FailureAnalysis>(`${reportPath(id)}/analysis`, { report_revision: reportRevision, force }, { signal }),
  preview: (id: string, kind: AttachmentKind, signal?: AbortSignal) => client.get<FailureAttachmentPreview>(`${reportPath(id)}/attachments/${kind}/preview`, { signal }),
  attachment: (id: string, kind: AttachmentKind, signal?: AbortSignal) => client.get<Blob>(`${reportPath(id)}/attachments/${kind}`, { responseType: 'blob', signal }),
  scan: (signal?: AbortSignal) => client.get<FailureScan>(`${base}/scan`, { signal }),
  startScan: (signal?: AbortSignal) => client.post<FailureScan>(`${base}/scan`, {}, { signal }),
  confirmations: (id: string, signal?: AbortSignal) => client.get<{ items: FailureConfirmation[] }>(`${base}/devices/${encodeURIComponent(id)}/confirmations`, { signal }),
  confirm: (id: string, text: string, version: string, signal?: AbortSignal) => client.post<{ confirmation: FailureConfirmation; device: FailureDevice }>(`${base}/devices/${encodeURIComponent(id)}/confirmations`, { text, version }, { signal }),
}

export function formatFailureTime(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/i.test(value) ? value : `${value.replace(' ', 'T')}Z`
  const date = new Date(normalized)
  if (!Number.isFinite(date.getTime())) return value
  return new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).format(date)
}

export function failureValue(value: unknown): string {
  if (value == null || value === '') return '—'
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}
