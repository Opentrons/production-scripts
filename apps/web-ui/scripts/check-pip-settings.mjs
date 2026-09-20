import { readFileSync } from 'node:fs'

const snapshotUrl = new URL('../public/data/pip-settings/opentrons-gen3.json', import.meta.url)
const dataset = JSON.parse(readFileSync(snapshotUrl, 'utf8'))
const errors = []

if (dataset.source?.repository !== 'https://github.com/Opentrons/opentrons') {
  errors.push('Snapshot repository is not Opentrons/opentrons')
}
if (dataset.source?.branch !== 'edge' || !dataset.source?.commit) {
  errors.push('Snapshot must identify its edge branch commit')
}
if (dataset.stats?.pipetteTypes !== 7 || dataset.pipettes?.length !== 7) {
  errors.push('Snapshot must contain all 7 Gen3 pipette types')
}
if (dataset.stats?.pipetteDefinitionFiles !== 109) {
  errors.push('Snapshot must contain 109 pipette definition files')
}
if (dataset.stats?.liquidClassDefinitionFiles !== 9 || dataset.liquidClasses?.length !== 9) {
  errors.push('Snapshot must contain all 9 liquid-class definition files')
}
for (const pipette of dataset.pipettes ?? []) {
  if (!pipette.id || !pipette.displayName || !pipette.revisions?.length) {
    errors.push(`Pipette is incomplete: ${pipette.id ?? 'unknown'}`)
  }
  for (const revision of pipette.revisions ?? []) {
    for (const document of [revision.general, revision.geometry, ...Object.values(revision.liquid ?? {})]) {
      if (document && (!document.sourcePath || typeof document.data !== 'object')) {
        errors.push(`Invalid source document in ${pipette.id} revision ${revision.version}`)
      }
    }
  }
}

if (errors.length) {
  console.error(errors.join('\n'))
  process.exit(1)
}

const sourceFiles = dataset.stats.pipetteDefinitionFiles + dataset.stats.liquidClassDefinitionFiles
console.log(`Pip Settings snapshot verified: ${dataset.pipettes.length} pipettes, ${sourceFiles} source files`)
