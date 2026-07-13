const UNKNOWN_TEST_TYPE_KEYS = new Set(['', '-', 'na', 'n/a', 'none', 'null', 'unknown', 'unknow'])

const TEST_TYPE_LABELS_BY_KEY: Record<string, string> = {
  gravimetric: 'Gravimetric',
  grav: 'Gravimetric',
  volume: 'Gravimetric',
  '1chupdatevolume': 'Gravimetric',
  '8chupdatevolume': 'Gravimetric',
  assemblyqc: 'Assembly QC',
  qc: 'Assembly QC',
  '1chupdateassemblyqc': 'Assembly QC',
  '8chupdateassemblyqc': 'Assembly QC',
  '96p200updateqc': 'Assembly QC',
  '96p1000updateqc': 'Assembly QC',
  speedcurrent: 'Speed Current',
  currentspeed: 'Speed Current',
  speedcurrenttest: 'Speed Current',
  '1chupdatecurrentspeed': 'Speed Current',
  '8chupdatecurrentspeed': 'Speed Current',
  burninresult: 'Burn In Result',
  burninresulttest: 'Burn In Result',
  '8chupdateburninresult': 'Burn In Result',
  burninrecord: 'Burn In Records',
  burninrecords: 'Burn In Records',
  burninrecordtest: 'Burn In Records',
  '8chupdateburninrecords': 'Burn In Records',
  pressureleakage: 'Pressure Leakage',
  pressureleakagetest: 'Pressure Leakage',
  zstage: 'Z Stage',
  zstagetest: 'Z Stage',
  robotupdatezstage: 'Z Stage',
  diagnostic: 'Diagnostic',
  robotassembly: 'Diagnostic',
  robotupdatediagnostic: 'Diagnostic',
  xycalibration: 'XY Belt Calibration',
  xybeltcalibration: 'XY Belt Calibration',
  robotupdatexybeltcalibration: 'XY Belt Calibration',
  gantrystress: 'Gantry Stress',
  gantrystresstest: 'Gantry Stress',
  robotupdategantrystress: 'Gantry Stress',
  leveling: 'Leveling',
  levelingtest: 'Leveling',
  robotupdateleveling: 'Leveling',
  photometric: 'Photometric'
}

export function normalizeTestTypeKey(value: unknown) {
  return String(value ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '')
}

export function canonicalTestType(value: unknown) {
  const text = String(value ?? '').trim()
  const key = normalizeTestTypeKey(text)
  if (UNKNOWN_TEST_TYPE_KEYS.has(key) || key.startsWith('unknown') || key.startsWith('unknow')) return ''
  const known = TEST_TYPE_LABELS_BY_KEY[key]
  if (known) return known
  if (key.includes('gravimetric') || key.includes('volume')) return 'Gravimetric'
  if (key.includes('assemblyqc') || ((key.includes('assembly') || key.endsWith('qc')) && !key.includes('rawdata'))) return 'Assembly QC'
  if (key.includes('speed') && key.includes('current')) return 'Speed Current'
  if (key.includes('burnin') && key.includes('result')) return 'Burn In Result'
  if (key.includes('burnin') && (key.includes('record') || key.includes('records'))) return 'Burn In Records'
  if (key.includes('pressure') && key.includes('leakage')) return 'Pressure Leakage'
  if (key.includes('zstage')) return 'Z Stage'
  if (key.includes('xy') && key.includes('calibration')) return 'XY Belt Calibration'
  if (key.includes('gantry') && key.includes('stress')) return 'Gantry Stress'
  if (key.includes('leveling')) return 'Leveling'
  if (key.includes('diagnostic')) return 'Diagnostic'
  if (key.includes('photometric')) return 'Photometric'
  return titleCaseTestType(text)
}

export function formatTestType(value: unknown, fallback = '') {
  return canonicalTestType(value) || fallback
}

export function uniqueTestTypes(values: unknown[]) {
  return Array.from(new Set(values.map(canonicalTestType).filter(Boolean))).sort()
}

export function sameTestType(left: unknown, right: unknown) {
  const leftLabel = canonicalTestType(left)
  const rightLabel = canonicalTestType(right)
  return Boolean(leftLabel && leftLabel === rightLabel)
}

function titleCaseTestType(value: string) {
  return value
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map(word => {
      const upperWord = word.toUpperCase()
      if (['QC', 'XY', 'CV', 'SN'].includes(upperWord)) return upperWord
      return `${word.slice(0, 1).toUpperCase()}${word.slice(1).toLowerCase()}`
    })
    .join(' ')
}
