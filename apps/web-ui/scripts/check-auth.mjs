import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import axios from 'axios'

const source = readFileSync(new URL('../src/scripts/api/http.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source.replace('import.meta.env.VITE_API_BASE_URL', 'undefined'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText

function harness({ failRefresh = false, forbidden = false, alwaysUnauthorized = false } = {}) {
  const calls = []
  const redirects = []
  const document = { cookie: 'production_csrf_token=before-refresh' }
  let expired = true
  const adapter = async (config) => {
    calls.push({ url: config.url, method: config.method, csrf: config.headers.get('X-CSRF-Token') })
    let status = 200
    if (config.url === '/auth/refresh') {
      status = failRefresh ? 401 : 200
      if (!failRefresh) {
        expired = false
        document.cookie = 'production_csrf_token=after-refresh'
      }
    } else if (config.url === '/auth/me') status = expired ? 401 : 200
    else if (forbidden) status = 403
    else if (expired || alwaysUnauthorized) status = 401
    const response = { status, data: {}, statusText: String(status), headers: {}, config }
    if (status >= 400) throw new axios.AxiosError('Request failed', 'ERR_BAD_REQUEST', config, undefined, response)
    return response
  }
  // Keep real Axios request/response interceptors; replace only the network.
  const transport = { ...axios, create: options => axios.create({ ...options, adapter }) }
  const exports = {}
  vm.runInNewContext(compiled, {
    exports, document,
    window: { location: { pathname: '/settings', search: '', hash: '', assign: value => redirects.push(value) } },
    require: name => name === 'axios' ? transport : { currentLocale: () => 'zh-CN' },
  })
  return { api: exports.createApiClient(), calls, redirects }
}

for (const [method, url] of [['get', '/auth/accounts'], ['post', '/auth/accounts'], ['patch', '/auth/accounts/test-id']]) {
  const { api, calls, redirects } = harness()
  assert.equal((await api.request({ method, url, data: { role: 'guest' } })).status, 200)
  assert.deepEqual(calls.map(call => call.url), [url, '/auth/me', '/auth/refresh', url])
  if (method !== 'get') assert.equal(calls.at(-1).csrf, 'after-refresh')
  assert.equal(redirects.length, 0)
}
{
  const { api, calls, redirects } = harness({ failRefresh: true })
  await assert.rejects(api.get('/auth/accounts'))
  assert.equal(calls.filter(call => call.url === '/auth/refresh').length, 1)
  assert.equal(redirects[0], '/login?redirect=%2Fsettings')
}
{
  const { api, calls } = harness({ forbidden: true })
  await assert.rejects(api.get('/auth/accounts'))
  assert.equal(calls.length, 1)
}
{
  const { api, calls } = harness({ alwaysUnauthorized: true })
  await assert.rejects(api.get('/auth/accounts'))
  assert.equal(calls.length, 4) // One retry only.
}
for (const url of ['/auth/login', '/auth/refresh', '/auth/password-reset/confirm']) {
  const { api, calls } = harness({ failRefresh: true })
  await assert.rejects(api.post(url))
  assert.equal(calls.length, 1)
}
console.log('Authentication requests: renewal, rotated CSRF, logout, permissions and retry limits verified')
