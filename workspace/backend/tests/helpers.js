import { mkdtempSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { loadConfig } from '../src/config.js'
import { openDatabase } from '../src/db/database.js'
import { createIrrigationServer } from '../src/http/server.js'
import { importSeed } from '../src/services/seed.js'
import { setPassword } from '../src/services/auth.js'

export function createTempBackend() {
  const directory = mkdtempSync(join(tmpdir(), 'irrigation-backend-'))
  const config = loadConfig({
    dbPath: join(directory, 'test.sqlite'),
    exportDir: join(directory, 'exports'),
    staticDir: null,
  })
  const db = openDatabase(config)
  importSeed(db, config.sourcePath, { force: true })
  return {
    directory,
    config,
    db,
    reopen() {
      const next = openDatabase(config)
      return next
    },
    cleanup() {
      try {
        db.close()
      } catch {}
      rmSync(directory, { recursive: true, force: true })
    },
  }
}

export async function startServer(context) {
  const server = createIrrigationServer({ db: context.db, config: context.config })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  const base = `http://127.0.0.1:${address.port}/api/v1`
  async function api(path, { method = 'GET', body, cookie, csrf, headers = {} } = {}) {
    const response = await fetch(`${base}${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(cookie ? { Cookie: cookie } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    let payload = null
    try {
      payload = await response.json()
    } catch {}
    return { status: response.status, payload, headers: response.headers }
  }
  async function login(account, password) {
    const response = await api('/auth/login', { method: 'POST', body: { account, password } })
    if (response.status !== 200) throw new Error(`登录失败：${response.status} ${JSON.stringify(response.payload)}`)
    const raw = response.headers.getSetCookie?.()[0] ?? response.headers.get('set-cookie')
    const cookie = raw.split(';')[0]
    return { cookie, csrf: response.payload.csrfToken, user: response.payload.user, session: response.payload }
  }
  async function close() {
    await new Promise((resolve) => server.close(resolve))
  }
  return { server, base, api, login, close, store: server.irrigation.store }
}

export function findUser(db, role) {
  const rows = db.prepare('SELECT payload FROM users').all()
  return rows.map((row) => JSON.parse(row.payload)).find((user) => user.role === role && user.status === 'ENABLED')
}

export function seedPassword(db, account, password) {
  return setPassword(db, account, password)
}
