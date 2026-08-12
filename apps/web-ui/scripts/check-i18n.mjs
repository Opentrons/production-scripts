import enUS from '../src/i18n/locales/en-US.ts'
import zhCN from '../src/i18n/locales/zh-CN.ts'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { extname, join, relative } from 'node:path'

function flatten(value, prefix = '', result = new Map()) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      flatten(child, prefix ? `${prefix}.${key}` : key, result)
    }
    return result
  }
  result.set(prefix, typeof value)
  return result
}

const zhKeys = flatten(zhCN)
const enKeys = flatten(enUS)
const errors = []

for (const [key, type] of zhKeys) {
  if (!enKeys.has(key)) errors.push(`Missing en-US key: ${key}`)
  else if (enKeys.get(key) !== type) errors.push(`Type mismatch for ${key}: zh-CN=${type}, en-US=${enKeys.get(key)}`)
}
for (const key of enKeys.keys()) {
  if (!zhKeys.has(key)) errors.push(`Missing zh-CN key: ${key}`)
}

if (errors.length) {
  console.error(errors.join('\n'))
  process.exit(1)
}

const srcRoot = new URL('../src', import.meta.url).pathname
const sourceFiles = []
const sourceExtensions = new Set(['.js', '.ts', '.vue'])

function collectSourceFiles(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry)
    if (statSync(path).isDirectory()) collectSourceFiles(path)
    else if (sourceExtensions.has(extname(path))) sourceFiles.push(path)
  }
}

collectSourceFiles(srcRoot)
for (const path of sourceFiles) {
  const relativePath = relative(srcRoot, path)
  if (relativePath.replaceAll('\\', '/').startsWith('i18n/locales/')) continue
  const source = readFileSync(path, 'utf8')
    .replace(/<!--[^]*?-->/g, '')
    .replace(/^\s*\/\/.*$/gm, '')
  if (/\p{Script=Han}/u.test(source)) {
    errors.push(`Hardcoded Chinese text in ${relativePath}`)
  }
}

if (errors.length) {
  console.error(errors.join('\n'))
  process.exit(1)
}

console.log(`i18n catalogs match: ${zhKeys.size} keys`)
