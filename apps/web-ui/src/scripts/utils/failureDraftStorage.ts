export interface StoredFailureDraft { text: string; version: string; confirmer?: string }
type DraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** Session-only drafts are isolated by authenticated account and independent folder ID. */
export function createFailureDraftStorage(getStorage: () => DraftStorage = () => window.sessionStorage) {
  const key = (userId: string, folderId: string) => `test-failure-draft:v1:${JSON.stringify([userId, folderId])}`
  return {
    read(userId: string, folderId: string): StoredFailureDraft | null {
      if (!userId || !folderId) return null
      try {
        const stored = getStorage().getItem(key(userId, folderId))
        if (!stored) return null
        const value: unknown = JSON.parse(stored)
        if (!value || typeof value !== 'object') return null
        const draft = value as Partial<StoredFailureDraft>
        const confirmer = typeof draft.confirmer === 'string' && draft.confirmer.length <= 128 ? draft.confirmer : ''
        if (typeof draft.text !== 'string' || draft.text.length > 4000 || !(draft.text.trim() || confirmer)
          || typeof draft.version !== 'string' || !draft.version || draft.version.length >= 500) return null
        return { text: draft.text, version: draft.version, ...(confirmer ? { confirmer } : {}) }
      } catch { return null }
    },
    write(userId: string, folderId: string, draft: StoredFailureDraft): boolean {
      if (!userId || !folderId) return false
      try {
        const storage = getStorage()
        const { text, version, confirmer } = draft
        if (text.trim() || confirmer) storage.setItem(key(userId, folderId), JSON.stringify({ text, version, confirmer }))
        else storage.removeItem(key(userId, folderId))
        return true
      } catch { return false }
    },
    remove(userId: string, folderId: string): boolean {
      if (!userId || !folderId) return false
      try { getStorage().removeItem(key(userId, folderId)); return true } catch { return false }
    },
  }
}
