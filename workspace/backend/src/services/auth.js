import { createHash, randomBytes, randomUUID, scryptSync, timingSafeEqual } from 'node:crypto'
import { AppError } from '../errors.js'

const SCRYPT_PARAMS = Object.freeze({ N: 16384, r: 8, p: 1, keylen: 64 })
const SESSION_COOKIE = 'irrigation_session'

const sha256 = (value) => createHash('sha256').update(value).digest('hex')

function hashPassword(password, salt = randomBytes(16).toString('base64url')) {
  const digest = scryptSync(String(password), salt, SCRYPT_PARAMS.keylen, {
    N: SCRYPT_PARAMS.N,
    r: SCRYPT_PARAMS.r,
    p: SCRYPT_PARAMS.p,
    maxmem: 64 * 1024 * 1024,
  }).toString('base64url')
  return { salt, digest, iterations: SCRYPT_PARAMS.N, hash: 'scrypt-sha256' }
}

export function validatePassword(password) {
  if (typeof password !== 'string' || password.length < 8 || password.length > 128) {
    throw new AppError('VALIDATION', '口令长度须为8至128个字符', { status: 422, fieldErrors: { password: '口令长度须为8至128个字符' } })
  }
}

export function setPassword(db, account, password) {
  validatePassword(password)
  const normalized = String(account ?? '').trim()
  if (!normalized) throw new AppError('VALIDATION', '账号必填', { status: 422, fieldErrors: { account: '账号必填' } })
  const user = db.prepare('SELECT payload FROM users WHERE account = ?').get(normalized)
  if (!user) throw new AppError('NOT_FOUND', '账号不存在', { status: 404 })
  const parsed = JSON.parse(user.payload)
  if (parsed.status !== 'ENABLED') throw new AppError('VALIDATION', '账号已停用，不能设置登录口令', { status: 422 })
  const credentials = hashPassword(password)
  db.prepare(`INSERT INTO credentials(account, salt, digest, iterations, hash, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(account) DO UPDATE SET salt = excluded.salt, digest = excluded.digest, iterations = excluded.iterations, hash = excluded.hash, updated_at = excluded.updated_at`)
    .run(normalized, credentials.salt, credentials.digest, credentials.iterations, credentials.hash, new Date().toISOString())
  db.prepare('UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL').run(new Date().toISOString(), parsed.userId)
  return parsed
}

export function verifyPassword(db, account, password) {
  const credential = db.prepare('SELECT * FROM credentials WHERE account = ?').get(String(account ?? '').trim())
  if (!credential || credential.hash !== 'scrypt-sha256') return false
  const expected = Buffer.from(credential.digest, 'base64url')
  const actual = scryptSync(String(password ?? ''), credential.salt, expected.length, {
    N: credential.iterations,
    r: SCRYPT_PARAMS.r,
    p: SCRYPT_PARAMS.p,
    maxmem: 64 * 1024 * 1024,
  })
  return actual.length === expected.length && timingSafeEqual(actual, expected)
}

export function createSession(db, userId, userVersion, ttlMs, now = new Date()) {
  const token = randomBytes(32).toString('base64url')
  const csrfToken = randomBytes(32).toString('base64url')
  const sessionId = randomUUID()
  const expiresAt = new Date(now.getTime() + ttlMs)
  db.prepare(`INSERT INTO sessions(token_hash, session_id, user_id, user_version, csrf_token, created_at, expires_at, revoked_at, last_seen_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)`)
    .run(sha256(token), sessionId, userId, userVersion, csrfToken, now.toISOString(), expiresAt.toISOString(), now.toISOString())
  return { token, csrfToken, sessionId, expiresAt: expiresAt.toISOString() }
}

export function resolveSession(db, token, now = new Date()) {
  if (!token) return null
  const row = db.prepare('SELECT * FROM sessions WHERE token_hash = ?').get(sha256(token))
  if (!row) return null
  if (row.revoked_at) return null
  if (Date.parse(row.expires_at) <= now.getTime()) return null
  const userRow = db.prepare('SELECT payload FROM users WHERE id = ?').get(row.user_id)
  if (!userRow) return null
  const user = JSON.parse(userRow.payload)
  if (user.status !== 'ENABLED' || user.version !== row.user_version) {
    db.prepare('UPDATE sessions SET revoked_at = ? WHERE token_hash = ?').run(now.toISOString(), row.token_hash)
    return null
  }
  db.prepare('UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?').run(now.toISOString(), row.token_hash)
  return { ...row, token, user, csrfToken: row.csrf_token, expiresAt: row.expires_at }
}

export function revokeSession(db, token, now = new Date()) {
  if (!token) return
  db.prepare('UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL').run(now.toISOString(), sha256(token))
}

export function revokeUserSessions(db, userIds, now = new Date()) {
  const statement = db.prepare('UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL')
  for (const userId of new Set(userIds.filter(Boolean))) statement.run(now.toISOString(), userId)
}

export function cleanupSessions(db, now = new Date()) {
  db.prepare('DELETE FROM sessions WHERE expires_at <= ? OR (revoked_at IS NOT NULL AND revoked_at <= ?)').run(now.toISOString(), new Date(now.getTime() - 86400000).toISOString())
}

export function sessionTokenFromCookie(cookieHeader) {
  if (!cookieHeader) return null
  for (const part of String(cookieHeader).split(';')) {
    const [name, ...rest] = part.trim().split('=')
    if (name === SESSION_COOKIE) return decodeURIComponent(rest.join('='))
  }
  return null
}

export function sessionCookie(token, { secure = false, maxAgeMs = 8 * 3600000 } = {}) {
  return `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${Math.floor(maxAgeMs / 1000)}${secure ? '; Secure' : ''}`
}

export function clearSessionCookie({ secure = false } = {}) {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${secure ? '; Secure' : ''}`
}

export { SESSION_COOKIE }
