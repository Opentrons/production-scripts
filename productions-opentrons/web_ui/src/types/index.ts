export interface MenuItem {
  id: string
  name: string
  path: string
  icon?: string
  children?: MenuItem[]
}

export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'unknown' | 'running' | 'stopped' | 'failed'
  message: string
  elapsed_ms?: number
}

export interface HealthCheckResponse {
  status: boolean
  elapsed_ms?: number
  services: {
    system_service: HealthStatus
    slack: HealthStatus
    google_drive: HealthStatus
  }
}

export interface TestDataItem {
  _id: string
  serial_number: string
  test_type: string
  test_result: string
  test_date: string
  [key: string]: any
}

export interface TestDataResponse {
  data: TestDataItem[]
  total: number
}

export interface MessageItem {
  _id: string
  message?: string
  content?: string
  title?: string
  new?: boolean
  status?: string
  type?: string
  level?: string
  created_at?: string
  updated_at?: string
  source?: string
  [key: string]: any
}

export interface MessagesResponse {
  messages: MessageItem[]
  total: number
  unread_count?: number
  error?: string
}

export interface CollectionsResponse {
  collections: string[]
  total: number
  error?: string
}

export interface CollectionDataResponse {
  data: Record<string, any>[]
  total: number
  page: number
  page_size: number
  collection: string
  error?: string
}

export interface CollectionFilterOptionsResponse {
  models: string[]
  types: string[]
  total_results: string[]
  error?: string
}

export interface UploadFileInfo {
  path: string
  name: string
  size?: number
  stat_error?: string
}

export interface UploadRecordItem {
  _id: string
  status: 'running' | 'success' | 'failed' | string
  request_started_at?: string
  request_finished_at?: string | null
  updated_at?: string
  csv_file?: UploadFileInfo | null
  zip_file?: UploadFileInfo | null
  file_desc?: Record<string, any> | null
  progress_stage?: string | null
  progress_message?: string | null
  upload_success?: boolean | null
  database_success?: boolean | null
  slack_success?: boolean | null
  slack_notified_at?: string | null
  result?: Record<string, any> | null
  upload_result?: Record<string, any> | null
  error?: string | null
  [key: string]: any
}

export interface UploadRecordsResponse {
  records: UploadRecordItem[]
  total: number
  page: number
  page_size: number
  error?: string
}

export interface UploadProductStats {
  model: string
  total: number
  finished: number
  success: number
  failed: number
  running: number
  success_rate: number
}

export interface UploadTestDurationStats {
  model: string
  test_type: string
  count: number
  avg_seconds: number
}

export interface UploadRecordStatsResponse {
  total: number
  finished: number
  success: number
  failed: number
  running: number
  success_rate: number
  highest_product?: UploadProductStats | null
  lowest_product?: UploadProductStats | null
  products: UploadProductStats[]
  test_durations?: UploadTestDurationStats[]
  error?: string
}

export interface UploadRecordFilterOptionsResponse {
  models: string[]
  statuses: string[]
  error?: string
}

export interface UnitTrackerColumn {
  key: string
  label: string
  group?: string
  group_key?: string
}

export interface UnitTrackerRow {
  _id?: string
  record_id: string
  product: string
  test_type: string
  sn: string
  csv_link?: string
  file_path?: string
  row: Record<string, any>
  updated_at?: string
}

export interface UnitTrackerRowsResponse {
  columns: UnitTrackerColumn[]
  rows: UnitTrackerRow[]
  total: number
  page: number
  page_size: number
  error?: string
}

export interface UnitTrackerSyncResponse {
  success: boolean
  scanned: number
  updated: number
  skipped: number
  errors: Array<{ record_id?: string; message: string }>
  error?: string
}

export interface ProductManagementTest {
  key: string
  upload_record_id?: string
  test_type: string
  status: string
  date?: string
  csv_link?: string
  source_csv_path?: string
  source?: string
}

export interface ProductManagementItem {
  _id: string
  barcode: string
  status: string
  model: string
  oem: string
  tests: ProductManagementTest[]
  test_types?: string[]
  latest_date?: string
  upload_record_count?: number
  [key: string]: any
}

export interface ProductManagementListResponse {
  products: ProductManagementItem[]
  total: number
  page: number
  page_size: number
  error?: string
}

export interface ProductManagementFilterOptionsResponse {
  models: string[]
  statuses: string[]
  test_types: string[]
  error?: string
}

export interface ProductManagementSyncResponse {
  success: boolean
  source_records: number
  skipped_records: number
  total_products: number
  created_count: number
  updated_count: number
  error?: string
}

export interface ProductManagementManualAddPayload {
  barcode: string
  status: string
  model: string
  oem: string
  test_type: string
  csv_link?: string
  source_csv_path?: string
}

export interface ProductManagementManualAddResponse {
  success: boolean
  barcode: string
  created_product: boolean
  added_test: boolean
  product?: ProductManagementItem | null
  error?: string
}

export interface ProductStatusUpdateResponse {
  success: boolean
  barcode: string
  status: string
  matched_count: number
  modified_count: number
  error?: string
}

export interface UploadDataResponse {
  csv_file?: string | null
  zip_file?: string | null
  success: boolean
  record_id?: string | null
  message?: string | null
}

export interface UploadFinishSettingOption {
  model: string
  test_type: string
  config_key: string
  test_display_name: string
}

export interface UploadFinishSettingItem extends UploadFinishSettingOption {
  require_finished: boolean
  source?: 'default' | 'database' | string
  updated_at?: string | null
}

export interface UploadFinishSettingsResponse {
  options: UploadFinishSettingOption[]
  settings: UploadFinishSettingItem[]
  database_available: boolean
  error?: string | null
}

export interface UploadFinishSettingPayload {
  model: string
  test_type: string
  require_finished: boolean
}

export interface DataLinkItem {
  label: string
  link_type: 'spreadsheet' | 'drive_folder' | string
  file_id?: string | null
  url?: string | null
  available: boolean
  note?: string | null
}

export interface DataLinkEntry {
  product: string
  test_type: string
  test_display_name: string
  config_key: string
  templates: DataLinkItem[]
  trackers: DataLinkItem[]
  raw_data_folder: DataLinkItem
  raw_data_parent_folder?: DataLinkItem | null
}

export interface DataLinksResponse {
  environment?: string | null
  config_file?: string | null
  current_date?: string | null
  current_month?: number | null
  links: DataLinkEntry[]
  total: number
  warnings: string[]
  error?: string | null
}

export interface DataAnalysisFileInfo {
  name: string
  path?: string
  size?: number
}

export interface DataAnalysisVolumeMetric {
  volume: number
  action: 'aspirate' | 'dispense' | string
  scope: string
  scope_id: string
  average?: number | null
  cv?: number | null
  d?: number | null
  celsius_pipette_avg?: number | null
  humidity_pipette_avg?: number | null
  time_s?: number | null
}

export interface DataAnalysisTrialPoint {
  volume: number
  trial: number
  channel: string
  aspirate?: number | null
  dispense?: number | null
  aspirate_d?: number | null
  dispense_d?: number | null
  aspirate_cv?: number | null
  dispense_cv?: number | null
  water_remain?: number | null
  aspirate_time_s?: number | null
  dispense_time_s?: number | null
  liquid_height?: number | null
  liquid_height_time_s?: number | null
  aspirate_travel?: number | null
  time_s?: number | null
}

export interface DataAnalysisEnvironmentPoint {
  volume: number
  trial: number
  channel: string
  action: string
  time_s?: number | null
  celsius_pipette?: number | null
  humidity_pipette?: number | null
  celsius_air?: number | null
  humidity_air?: number | null
  celsius_liquid?: number | null
  grams_average?: number | null
}

export interface DataAnalysisVolumeSummary {
  volume: number
  [key: string]: any
}

export interface DataAnalysisChannelTrialValue {
  trial: number
  value?: number | null
  d?: number | null
  water_remain?: number | null
}

export interface DataAnalysisChannelTrialMatrixRow {
  channel: string
  label: string
  trial_values: DataAnalysisChannelTrialValue[]
  average?: number | null
  cv?: number | null
  d?: number | null
  avg_water_remaining?: number | null
}

export interface DataAnalysisChannelTrialMatrix {
  volume: number
  action: 'aspirate' | 'dispense' | string
  trials: number[]
  channels: string[]
  spec?: {
    target?: number | null
    min?: number | null
    max?: number | null
    d?: number | null
    cv?: number | null
  }
  rows: DataAnalysisChannelTrialMatrixRow[]
  trial_summary?: {
    trial: number
    average?: number | null
    cv?: number | null
    d?: number | null
  }[]
}

export interface DataAnalysisSingleChannelTrialMatrixRow {
  trial: number
  channel?: string
  water_remaining?: number | null
  aspirate_time_s?: number | null
  aspirate?: number | null
  aspirate_d?: number | null
  dispense_time_s?: number | null
  dispense?: number | null
  dispense_d?: number | null
  aspirate_travel?: number | null
}

export interface DataAnalysisSingleChannelTrialMatrix {
  volume: number
  label?: string
  spec?: {
    target?: number | null
    min?: number | null
    max?: number | null
    d?: number | null
    cv?: number | null
  }
  rows: DataAnalysisSingleChannelTrialMatrixRow[]
  summary?: {
    average?: Record<string, number | null>
    cv?: Record<string, number | null>
  }
}

export interface DataAnalysisDiagnosticRow {
  key: string
  label?: string
  time_s?: number | null
  actual?: number | null
  target?: number | null
  values?: string[]
  extra_values?: string[]
  status?: string | null
  passed?: boolean | null
  spec?: {
    min?: number | null
    max?: number | null
    target?: number | null
    expected?: string | number | null
  }
}

export interface DataAnalysisDiagnosticSection {
  section: string
  label?: string
  status?: string | null
  passed?: boolean | null
  total: number
  pass: number
  fail: number
  rows: DataAnalysisDiagnosticRow[]
  metrics?: DataAnalysisDiagnosticRow[]
}

export interface DataAnalysisSectionResult {
  section: string
  label?: string
  status?: string | null
  passed?: boolean | null
  total?: number
  pass?: number
  fail?: number
}

export interface DataAnalysisMetadataRow {
  key: string
  label?: string
  value?: any
  status?: string | null
}

export interface DataAnalysisTestMatrixCell {
  status?: string | null
  passed?: boolean | null
  actual?: number | null
  target?: number | null
  key?: string
  spec?: Record<string, any>
}

export interface DataAnalysisTestMatrix {
  key: string
  section: string
  title: string
  columns: { key: string; label: string }[]
  rows: {
    key: string
    label: string
    values: DataAnalysisTestMatrixCell[]
  }[]
}

export interface DataAnalysisItem {
  file: DataAnalysisFileInfo
  channel: string
  channel_label: string
  analyzer_key?: string
  view_key?: string
  status: string
  result: 'Pass' | 'Fail' | string
  passed: boolean
  product?: string
  sn?: string
  test_name?: string
  test_time_utc?: string
  metadata: Record<string, any>
  config: Record<string, any>
  serial_numbers: Record<string, any>
  volumes: number[]
  volume_metrics: DataAnalysisVolumeMetric[]
  trial_series: DataAnalysisTrialPoint[]
  environment_series: DataAnalysisEnvironmentPoint[]
  environment_summary: DataAnalysisVolumeSummary[]
  environment_overview: Record<string, any>
  water_remain_summary: DataAnalysisVolumeSummary[]
  channel_trial_matrices?: DataAnalysisChannelTrialMatrix[]
  single_channel_trial_matrices?: DataAnalysisSingleChannelTrialMatrix[]
  metadata_table?: DataAnalysisMetadataRow[]
  section_results?: DataAnalysisSectionResult[]
  test_sections?: DataAnalysisDiagnosticSection[]
  test_matrices?: DataAnalysisTestMatrix[]
  checks?: Record<string, any>[]
  summary: Record<string, any>
}

export interface DataAnalysisResponse {
  analyses: DataAnalysisItem[]
  summary: {
    total_files: number
    analyzed: number
    pass: number
    fail: number
    error: number
    yield_rate: number
    products?: { product: string; count: number }[]
    channels?: { channel: string; count: number }[]
    [key: string]: any
  }
  errors: { file?: DataAnalysisFileInfo; message: string }[]
  online_source?: {
    product: string
    test_type: string
    barcode?: string
    csv_link: string
    sheet_name: string
    cols: string[]
    csv_path: string
  }
}

export interface DataAnalysisOnlinePayload {
  barcode?: string
  product: string
  test_type: string
  csv_link: string
}

export interface DataAnalysisSpecVolume {
  volume: number
  cv: number
  d: number
}

export interface DataAnalysisSpecItem {
  product: string
  product_name: string
  analysis_product: string
  test_type: string
  test_name: string
  volumes: DataAnalysisSpecVolume[]
  source?: string
  storage?: string
  updated_at?: string
  [key: string]: any
}

export interface DataAnalysisSpecCatalogItem {
  product: string
  product_name: string
  analysis_product: string
  test_type: string
  test_name: string
}

export interface DataAnalysisSpecResponse {
  products: DataAnalysisSpecCatalogItem[]
  specs: DataAnalysisSpecItem[]
  storage: string
  error?: string | null
}
