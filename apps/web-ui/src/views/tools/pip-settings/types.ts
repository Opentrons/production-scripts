export type JsonPrimitive = string | number | boolean | null
export type JsonObject = { [key: string]: JsonValue }
export type JsonValue = JsonPrimitive | JsonValue[] | JsonObject

export interface SourceDocument {
  sourcePath: string
  data: JsonObject
}

export interface PipetteRevision {
  version: string
  general?: SourceDocument
  geometry?: SourceDocument
  liquid: Record<string, SourceDocument>
}

export interface PipetteDefinition {
  id: string
  liquidClassModel: string | null
  displayName: string
  displayCategory: string
  channelType: string
  channelLabel: string
  channels: number
  model: string
  maxVolume: number
  revisions: PipetteRevision[]
}

export interface LiquidClassPipetteDefinition {
  pipetteModel: string
  byTipType: JsonObject[]
}

export interface LiquidClassDefinition {
  id: string
  liquidClassName: string
  displayName: string
  description: string
  schemaVersion: number
  version: number
  namespace: string
  sourcePath: string
  byPipette: LiquidClassPipetteDefinition[]
}

export interface PipSettingsDataset {
  source: {
    repository: string
    branch: string
    commit: string
    pipetteDefinitions: string
    liquidClassDefinitions: string
  }
  stats: {
    pipetteTypes: number
    pipetteDefinitionFiles: number
    liquidClassDefinitionFiles: number
  }
  pipettes: PipetteDefinition[]
  liquidClasses: LiquidClassDefinition[]
}

export interface GitHubBranch {
  name: string
  commit: string
}

export type TreeAction = 'auto' | 'expand' | 'collapse'

export interface TreeCommand {
  action: TreeAction
  token: number
}

export interface NodePresentation {
  title: string
  subtitle?: string
  technicalName?: string
  omitKeys?: string[]
}

export interface DocumentDescriptor {
  title: string
  titleZh?: string
  subtitle?: string
  document: SourceDocument
}
