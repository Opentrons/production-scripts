import assert from 'node:assert/strict'
import { test } from 'node:test'
import { failureKnowledgeProduct, failureKnowledgeQueries } from '../src/scripts/utils/failureKnowledge.ts'

test('searches one failure name and deduplicates names across bracket styles', () => {
  const summary = [
    `[压力超限] ${'完整测量细节 '.repeat(120)}`,
    '【压力超限】另一份完整细节',
    '[Encoder Motion] measured 3.5 mm',
    '[encoder   motion] measured 4.5 mm',
  ]
  assert.ok(summary.join(' ').length > 500)
  assert.deepEqual(failureKnowledgeQueries(summary), ['压力超限', 'Encoder Motion'])
  assert.match(summary[0], /完整测量细节/)
})

test('uses a short first title for summaries without a bracketed name', () => {
  assert.deepEqual(failureKnowledgeQueries([
    '压力测量异常：详细数值与建议',
    'Encoder motion failed. Check the motor.',
    'Runtime error\nTraceback and complete details',
    '[ ] Empty category fallback: detail',
  ]), ['压力测量异常', 'Encoder motion failed', 'Runtime error', 'Empty category fallback'])
  assert.equal(Array.from(failureKnowledgeQueries(['长'.repeat(200)])[0]).length, 80)
})

test('does not produce a query from empty or punctuation-only content', () => {
  assert.deepEqual(failureKnowledgeQueries(['', '  ', '[]', '【 】', '… — !!!']), [])
})

test('caps long Unicode names at the API limit without splitting surrogate pairs', () => {
  const name = '𠮷'.repeat(700)
  const [query] = failureKnowledgeQueries([`[${name}] full detail`])
  assert.equal(Array.from(query).length, 500)
  assert.equal(query, '𠮷'.repeat(500))
  assert.equal(new URLSearchParams({ q: query, product: 'P1000M' }).get('q'), query)
})

test('preserves the report product without guessing aliases and omits invalid long filters', () => {
  assert.equal(failureKnowledgeProduct('P50M'), 'P50M')
  assert.equal(failureKnowledgeProduct('P50M-G3'), 'P50M-G3')
  assert.equal(failureKnowledgeProduct(''), null)
  assert.equal(failureKnowledgeProduct('  '), null)
  assert.equal(failureKnowledgeProduct('𠮷'.repeat(120)), '𠮷'.repeat(120))
  assert.equal(failureKnowledgeProduct('𠮷'.repeat(121)), null)
})
