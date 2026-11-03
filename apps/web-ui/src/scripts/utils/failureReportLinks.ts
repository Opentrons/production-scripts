import type { FailureReportSummary } from '../api/testFailures'

export type FailureReportLinkIdentity = Pick<FailureReportSummary, 'id' | 'report_folder' | 'sn' | 'report_run_id' | 'product'>

export function failureReportLinkKey(report: FailureReportLinkIdentity): string {
  const sn = (report.sn || '').trim(), run = (report.report_run_id || '').trim()
  // Never associate separate folders, and never infer a run from another evidence package.
  return JSON.stringify([report.report_folder, sn, run, (report.product || '').trim(), sn && run ? '' : report.id])
}

export function failureReportLinkTargets(reports: FailureReportSummary[]): FailureReportSummary[] {
  const targets = new Map<string, FailureReportSummary>()
  for (const report of reports) {
    const key = failureReportLinkKey(report), existing = targets.get(key)
    if (!existing || (existing.report_role === 'right_reference' && report.report_role !== 'right_reference')) targets.set(key, report)
  }
  return [...targets.values()]
}

export function safeFailureReportUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && !url.port
      && ['docs.google.com', 'drive.google.com'].includes(url.hostname) ? url.href : null
  } catch { return null }
}
