export interface StoredFailureDraft { text: string; version: string }
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
        return typeof draft.text === 'string' && draft.text.length <= 4000 && draft.text.trim()
          && typeof draft.version === 'string' && draft.version.length > 0 && draft.version.length < 500
          ? { text: draft.text, version: draft.version } : null
      } catch { return null }
    },
    write(userId: string, folderId: string, draft: StoredFailureDraft): boolean {
      if (!userId || !folderId) return false
      try {
        const storage = getStorage()
        if (draft.text.trim()) storage.setItem(key(userId, folderId), JSON.stringify({ text: draft.text, version: draft.version }))
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
