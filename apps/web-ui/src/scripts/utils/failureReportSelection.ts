import type { FailureDevice } from '../api/testFailures'

/** Select evidence that actually matched the active filters, within this folder only. */
export function defaultFailureReportId(device: FailureDevice): string {
  return device.matched_report_ids?.find(id => device.reports.some(report => report.id === id))
    || device.reports[0]?.id || ''
}
