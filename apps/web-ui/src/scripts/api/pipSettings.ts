import { createApiClient } from '@/scripts/api/http'
import type { GitHubBranch, PipSettingsDataset } from '@/views/tools/pip-settings/types'

const client = createApiClient(120_000)

export const pipSettingsApi = {
  async searchBranches(query: string): Promise<GitHubBranch[]> {
    const { data } = await client.get<{ branches: GitHubBranch[] }>('/tools/pip-settings/branches', {
      params: { query },
    })
    return data.branches
  },

  async loadBranch(branch: string): Promise<PipSettingsDataset> {
    const { data } = await client.get<PipSettingsDataset>('/tools/pip-settings/dataset', {
      params: { branch },
    })
    return data
  },
}
