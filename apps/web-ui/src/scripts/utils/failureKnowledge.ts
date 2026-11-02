const MAX_KNOWLEDGE_QUERY_LENGTH = 500
const MAX_FALLBACK_TITLE_LENGTH = 80
const MAX_KNOWLEDGE_PRODUCT_LENGTH = 120

export function failureKnowledgeProduct(product: string): string | null {
  const name = product.trim()
  return name && Array.from(name).length <= MAX_KNOWLEDGE_PRODUCT_LENGTH ? name : null
}

/** Build one bounded search phrase per failure without sending full report details. */
export function failureKnowledgeQueries(summaries: readonly string[]): string[] {
  const queries: string[] = []
  const seen = new Set<string>()
  for (const summary of summaries) {
    const text = summary.trim()
    const prefix = text.match(/^(?:\[([^\]\r\n]*)\]|【([^】\r\n]*)】)/u)
    const name = (prefix?.[1] ?? prefix?.[2] ?? '').trim()
    const detail = prefix ? text.slice(prefix[0].length).trim() : text
    const title = name || detail.split(/\r?\n|[:：。！？!?;；]|\.\s+/u, 1)[0]
    const limit = name ? MAX_KNOWLEDGE_QUERY_LENGTH : MAX_FALLBACK_TITLE_LENGTH
    // Python's API length check counts Unicode code points, not UTF-16 units.
    const query = Array.from(title.replace(/\s+/gu, ' ').trim()).slice(0, limit).join('').trim()
    const key = query.toLowerCase()
    if (!/[\p{L}\p{N}]/u.test(query) || seen.has(key)) continue
    seen.add(key)
    queries.push(query)
  }
  return queries
}
