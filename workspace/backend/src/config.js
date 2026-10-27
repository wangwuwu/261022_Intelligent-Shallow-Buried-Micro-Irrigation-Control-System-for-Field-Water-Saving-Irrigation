import { existsSync, mkdirSync } from 'node:fs'
import { isAbsolute, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const backendRoot = fileURLToPath(new URL('..', import.meta.url))
export const workspaceRoot = resolve(backendRoot, '..')

function loadLocalEnv() {
  const file = resolve(backendRoot, '.env')
  if (existsSync(file) && typeof process.loadEnvFile === 'function') {
    try {
      process.loadEnvFile(file)
    } catch (error) {
      console.warn(`读取 ${file} 失败：${error.message}`)
    }
  }
}
loadLocalEnv()

const bool = (value, fallback = false) => {
  if (value === undefined || value === null || value === '') return fallback
  return ['1', 'true', 'yes', 'on'].includes(String(value).toLowerCase())
}

const absolute = (value, fallback) => {
  const selected = value || fallback
  return isAbsolute(selected) ? selected : resolve(backendRoot, selected)
}

export function loadConfig(overrides = {}) {
  const env = { ...process.env, ...overrides.env }
  const sourcePath = overrides.sourcePath ?? absolute(env.IRRIGATION_SEED || '../shared_context.json')
  const dbPath = overrides.dbPath ?? absolute(env.IRRIGATION_DB, 'var/irrigation.sqlite')
  const exportDir = overrides.exportDir ?? absolute(env.IRRIGATION_EXPORT_DIR, 'exports')
  const staticDir = overrides.staticDir !== undefined ? overrides.staticDir : env.IRRIGATION_STATIC_DIR === '' ? null : absolute(env.IRRIGATION_STATIC_DIR, '../frontend/dist')
  const allowedOrigins = String(env.IRRIGATION_ALLOWED_ORIGINS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  for (const directory of [resolve(dbPath, '..'), exportDir]) mkdirSync(directory, { recursive: true })
  return {
    host: env.IRRIGATION_HOST || '127.0.0.1',
    port: Number(env.IRRIGATION_PORT || 3001),
    dbPath,
    sourcePath,
    exportDir,
    staticDir,
    secureCookie: bool(env.IRRIGATION_SECURE_COOKIE),
    trustProxy: bool(env.IRRIGATION_TRUST_PROXY),
    deviceChannel: env.IRRIGATION_DEVICE_CHANNEL || 'disabled',
    allowedOrigins,
    sessionTtlMs: Number(env.IRRIGATION_SESSION_TTL_MS || 8 * 3600000),
    bodyLimitBytes: Number(env.IRRIGATION_BODY_LIMIT || 2 * 1024 * 1024),
    requestTimeoutMs: Number(env.IRRIGATION_REQUEST_TIMEOUT || 20000),
    seedPath: absolute(env.IRRIGATION_SEED_FILE, sourcePath),
    ...Object.fromEntries(Object.entries(overrides).filter(([, value]) => value !== undefined)),
  }
}
