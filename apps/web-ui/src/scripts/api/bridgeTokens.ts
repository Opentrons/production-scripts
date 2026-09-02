import { createApiClient } from '@/scripts/api/http'


export type BridgeTokenAction =
  | 'weekly_allocation'
  | 'low_balance_topup'
  | 'weekly_rebalance'
  | 'weekly_reminder'

export interface BridgeTokenBalance {
  key_id: string
  key_name: string
  quota: number
  quota_used: number
  remaining: number
  status: string
  updated_at: string
  email_hint: string
}

export interface CurrentUserBridgeTokens {
  configured: boolean
  linked: boolean
  live: boolean
  username: string
  keys: BridgeTokenBalance[]
  total_quota: number
  total_used: number
  total_remaining: number
  refreshed_at: string | null
  error: string
}

export interface BridgeTokenRecord {
  id: string
  key_id: string
  key_name: string
  action: BridgeTokenAction
  amount: number
  quota_before: number
  quota_after: number
  quota_used: number
  remaining_after: number
  success: boolean
  email_sent: boolean
  message: string
  created_at: string
}

export interface BridgeTokenRecordPage {
  records: BridgeTokenRecord[]
  total: number
  page: number
  page_size: number
}

export type BridgeEmailProvider = 'gmail' | 'smtp'

export interface BridgeTokenConfiguration {
  source: 'mongodb'
  automation_enabled: boolean
  base_url: string
  timezone: string
  quota_threshold: number
  quota_increment: number
  main_balance_alert_threshold: number
  weekly_token_budget: number
  allocation_lookback_days: number
  min_weekly_allocation: number
  min_rebalance_remaining: number
  reminder_subject: string
  admin_email: string
  email_provider: BridgeEmailProvider
  email_from: string
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_use_ssl: boolean
  smtp_starttls: boolean
  access_token_configured: boolean
  refresh_token_configured: boolean
  smtp_password_configured: boolean
  gmail_token_configured: boolean
  updated_at: string
  updated_by: string
}

export interface BridgeTokenConfigurationUpdate {
  automation_enabled: boolean
  base_url: string
  timezone: string
  quota_threshold: number
  quota_increment: number
  main_balance_alert_threshold: number
  weekly_token_budget: number
  allocation_lookback_days: number
  min_weekly_allocation: number
  min_rebalance_remaining: number
  reminder_subject: string
  admin_email: string
  email_provider: BridgeEmailProvider
  email_from: string
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_use_ssl: boolean
  smtp_starttls: boolean
  access_token?: string
  refresh_token?: string
  smtp_password?: string
}

const api = createApiClient(45000)

export const bridgeTokensApi = {
  getMine: (refresh = true) =>
    api.get<CurrentUserBridgeTokens>('/bridge-tokens/me', { params: { refresh } }),
  getMyRecords: (params: { action?: BridgeTokenAction; page: number; page_size: number }) =>
    api.get<BridgeTokenRecordPage>('/bridge-tokens/me/records', { params }),
  getConfiguration: () =>
    api.get<BridgeTokenConfiguration>('/bridge-tokens/configuration'),
  updateConfiguration: (payload: BridgeTokenConfigurationUpdate) =>
    api.put<BridgeTokenConfiguration>('/bridge-tokens/configuration', payload),
}
