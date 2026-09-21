import type {
  JsonObject,
  JsonPrimitive,
  JsonValue,
  NodePresentation,
  PipetteDefinition,
} from './types'
import { pipSettingsFieldLabelsZh, pipSettingsZh as zh } from '@/i18n/locales/pipSettings'

const FIELD_LABELS_EN: Record<string, string> = {
  $otSharedSchema: 'Opentrons Shared Schema',
  validNozzleMaps: 'Valid Nozzle Maps',
  pickUpTipConfigurations: 'Pick-Up Tip Configurations',
  dropTipConfigurations: 'Drop Tip Configurations',
  pressFit: 'Press Fit',
  tipOverlaps: 'Tip Overlap',
  configurationsByNozzleMap: 'Configurations by Nozzle Map',
  plungerEject: 'Plunger Eject',
  plungerMotorConfigurations: 'Plunger Motor Current',
  plungerPositionsConfigurations: 'Plunger Positions',
  plungerHomingConfigurations: 'Plunger Homing',
  partialTipConfigurations: 'Partial Tip Configurations',
  partialTipSupported: 'Partial Tip Supported',
  backCompatNames: 'Backward-Compatible Names',
  shaftDiameter: 'Shaft Diameter',
  shaftULperMM: 'Shaft Displacement',
  backlashDistance: 'Backlash Distance',
  pathTo3D: '3D Model Path',
  nozzleOffset: 'Nozzle Origin Offset',
  pipetteBoundingBoxOffsets: 'Pipette Bounding Box',
  backLeftCorner: 'Back-Left Corner',
  frontRightCorner: 'Front-Right Corner',
  orderedRows: 'Nozzle Rows',
  orderedColumns: 'Nozzle Columns',
  orderedNozzles: 'Ordered Nozzles',
  nozzleMap: 'Nozzle Coordinates',
  lldSettings: 'Liquid Level Detection',
  uiMaxFlowRate: 'Maximum UI Flow Rate',
  defaultAspirateFlowRate: 'Default Aspirate Flow Rate',
  defaultDispenseFlowRate: 'Default Dispense Flow Rate',
  defaultBlowOutFlowRate: 'Default Blow-Out Flow Rate',
  defaultFlowAcceleration: 'Default Flow Acceleration',
  defaultTipLength: 'Default Tip Length',
  defaultReturnTipHeight: 'Default Return Tip Height',
  defaultPushOutVolume: 'Default Push-Out Volume',
  defaultTipracks: 'Default Tip Racks',
  valuesByApiLevel: 'Values by API Level',
  liquidClassName: 'Liquid Class ID',
  schemaVersion: 'Schema Version',
  pipetteModel: 'Pipette Model',
  byTipType: 'Tip Types',
  tiprack: 'Tip Type',
  aspiratePosition: 'Aspirate Position',
  dispensePosition: 'Dispense Position',
  positionReference: 'Position Reference',
  correctionByVolume: 'Correction by Volume',
  flowRateByVolume: 'Flow Rate by Volume',
  pushOutByVolume: 'Push-Out by Volume',
  conditioningByVolume: 'Conditioning by Volume',
  disposalByVolume: 'Disposal by Volume',
  airGapByVolume: 'Air Gap by Volume',
  preWet: 'Pre-Wet',
  startPosition: 'Start Position',
  endPosition: 'End Position',
  touchTip: 'Touch Tip',
  mmFromEdge: 'Distance from Edge',
  zOffset: 'Z Offset',
  multiDispense: 'Multi-Dispense',
  singleDispense: 'Single Dispense',
}

export function normalize(value: string): string {
  return value.trim().toLocaleLowerCase()
}

export function humanize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/^./, character => character.toUpperCase())
}

export function fieldLabelEn(key: string): string {
  if (/^\[\d+\]$/.test(key)) return `Item ${key.slice(1, -1)}`
  if (/^t\d+$/i.test(key)) return `${key.slice(1)} µL Tip`
  if (/^v\d+$/i.test(key)) return `Version ${key.slice(1)}`
  return FIELD_LABELS_EN[key] ?? humanize(key)
}

export function fieldLabelZh(key: string): string {
  if (/^\[\d+\]$/.test(key)) return zh.item(key.slice(1, -1))
  if (/^t\d+$/i.test(key)) return zh.tip(key.slice(1))
  if (/^v\d+$/i.test(key)) return zh.namedVersion(key.slice(1))
  return pipSettingsFieldLabelsZh[key] ?? ''
}

export function isContainer(value: JsonValue): value is JsonValue[] | JsonObject {
  return typeof value === 'object' && value !== null
}

export function isPrimitiveArray(value: JsonValue): value is JsonPrimitive[] {
  return Array.isArray(value) && value.every(item => !isContainer(item))
}

export function isPrimitiveMatrix(value: JsonValue): value is JsonPrimitive[][] {
  return Array.isArray(value) && value.length > 0
    && value.every(row => Array.isArray(row) && row.every(item => !isContainer(item)))
}

export function keyMatches(key: string, query: string): boolean {
  if (!query.trim()) return true
  return normalize(`${key} ${fieldLabelEn(key)} ${fieldLabelZh(key)}`).includes(normalize(query))
}

export function valueMatches(value: JsonValue | undefined, query: string): boolean {
  if (!query.trim()) return true
  if (value === undefined) return false
  const normalizedQuery = normalize(query)
  if (!isContainer(value)) return normalize(String(value)).includes(normalizedQuery)
  if (Array.isArray(value)) return value.some(item => valueMatches(item, query))
  return Object.entries(value).some(([key, child]) => keyMatches(key, query) || valueMatches(child, query))
}

function stringProperty(value: JsonObject, key: string): string | null {
  const property = value[key]
  return typeof property === 'string' && property ? property : null
}

export function formatTiprackName(path: string): string {
  const identifier = path.split('/').at(-2) ?? path
  return identifier
    .replace(/^opentrons_/, '')
    .replace(/filtertiprack/g, 'filter_tip_rack')
    .replace(/tiprack/g, 'tip_rack')
    .split('_')
    .filter(Boolean)
    .map(part => {
      if (part === 'flex') return 'Flex'
      if (/^\d+ul$/i.test(part)) return `${part.replace(/ul$/i, '')} µL`
      return part.charAt(0).toUpperCase() + part.slice(1)
    })
    .join(' ')
}

export function formatPipetteModel(model: string): string {
  const match = model.match(/^flex_(\d+)channel(_em)?_(\d+)$/)
  if (!match) return humanize(model)
  return `Flex ${match[1]}-Channel${match[2] ? ' EM' : ''} ${match[3]} µL`
}

export function getArrayItemPresentation(parentName: string, item: JsonValue, index: number): NodePresentation {
  const fallback = { title: `Item ${index + 1}`, subtitle: zh.item(index + 1), technicalName: '' }
  if (!isContainer(item) || Array.isArray(item)) return fallback

  const tiprack = stringProperty(item, 'tiprack')
  if (tiprack) return { title: formatTiprackName(tiprack), subtitle: zh.tipType, technicalName: '', omitKeys: ['tiprack'] }
  const displayName = stringProperty(item, 'displayName')
  if (displayName) return { title: displayName, subtitle: zh.displayName, technicalName: '', omitKeys: ['displayName'] }
  const pipetteModel = stringProperty(item, 'pipetteModel')
  if (pipetteModel) return { title: formatPipetteModel(pipetteModel), subtitle: zh.applicablePipette, technicalName: '', omitKeys: ['pipetteModel'] }
  const key = stringProperty(item, 'key')
  if (key) {
    const isRow = parentName === 'orderedRows'
    const isColumn = parentName === 'orderedColumns'
    return {
      title: isRow ? `Row ${key}` : isColumn ? `Column ${key}` : humanize(key),
      subtitle: isRow ? zh.nozzleRow : isColumn ? zh.nozzleColumn : zh.configurationItem,
      technicalName: '',
      omitKeys: ['key'],
    }
  }
  for (const identityKey of ['name', 'liquidClassName', 'model', 'type', 'id']) {
    const identity = stringProperty(item, identityKey)
    if (identity) {
      return {
        title: identityKey === 'model' ? identity.toUpperCase() : humanize(identity),
        subtitle: fieldLabelZh(identityKey),
        technicalName: '',
        omitKeys: [identityKey],
      }
    }
  }
  return fallback
}

export function unitForKey(key: string): string {
  const normalizedKey = key.toLowerCase()
  if (normalizedKey.includes('ulpermm')) return 'µL/mm'
  if (normalizedKey.includes('flowacceleration')) return 'µL/s²'
  if (normalizedKey.includes('flowrate')) return 'µL/s'
  if (normalizedKey.includes('volume')) return 'µL'
  if (normalizedKey.includes('current')) return 'A'
  if (normalizedKey.includes('duration')) return 's'
  if (normalizedKey.includes('speed')) return 'mm/s'
  if (['distance', 'height', 'length', 'diameter', 'offset'].some(unit => normalizedKey.includes(unit))) return 'mm'
  return ''
}

export function formatPrimitive(value: JsonPrimitive): string {
  if (value === null) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return value.toLocaleString('en-US', { maximumFractionDigits: 6 })
  return value
}

export function formatChannelLabel(pipette: PipetteDefinition): string {
  return `${pipette.channels}-Channel${pipette.channelType === 'eight_channel_em' ? ' EM' : ''}`
}
