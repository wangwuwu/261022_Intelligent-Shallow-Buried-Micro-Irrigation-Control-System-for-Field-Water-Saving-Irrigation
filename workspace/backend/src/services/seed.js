import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { buildIrrigationIndex } from '../../../frontend/src/domain/irrigation.js'
import { emptyEntities, normalizeEntities } from '../db/entities.js'
import { persistEntities, readEntities, setMetadata, withTransaction, writeRevision } from '../db/database.js'
import { AppError } from '../errors.js'

export function readSeed(sourcePath) {
  let raw
  try {
    raw = readFileSync(sourcePath, 'utf8')
  } catch (error) {
    throw new AppError('SEED_UNAVAILABLE', `无法读取共享数据：${error.message}`, { status: 500 })
  }
  const sourceSha256 = createHash('sha256').update(raw, 'utf8').digest('hex')
  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch (error) {
    throw new AppError('SEED_INVALID', `共享数据不是有效 JSON：${error.message}`, { status: 500 })
  }
  if (!parsed?.entities || typeof parsed.entities !== 'object') throw new AppError('SEED_INVALID', '共享数据缺少 entities', { status: 500 })
  const entities = normalizeEntities(parsed.entities)
  entities.Session = []
  for (const [kind, rows] of Object.entries(entities)) {
    if (!Array.isArray(rows)) throw new AppError('SEED_INVALID', `${kind} 不是数组`, { status: 500 })
  }
  try {
    buildIrrigationIndex(entities)
  } catch (error) {
    throw new AppError('SEED_INVALID', `共享数据主键校验失败：${error.message}`, { status: 500 })
  }
  if (!entities.Farm.length) throw new AppError('SEED_INVALID', '共享数据缺少农场', { status: 500 })
  return { entities, sourceSha256, statistics: parsed.statistics ?? {} }
}

export function importSeed(db, sourcePath, { force = false, now = new Date() } = {}) {
  const existingUsers = db.prepare('SELECT COUNT(*) AS count FROM users').get()?.count ?? 0
  if (existingUsers > 0 && !force) {
    throw new AppError('SEED_EXISTS', '数据库已有业务用户，如需重新导入请显式使用 --force', { status: 409 })
  }
  const { entities, sourceSha256, statistics } = readSeed(sourcePath)
  withTransaction(db, () => {
    const empty = emptyEntities()
    empty.Session = []
    persistEntities(db, empty)
    db.prepare('DELETE FROM export_rows').run()
    db.prepare('DELETE FROM export_files').run()
    persistEntities(db, entities)
    writeRevision(db, 1)
    setMetadata(db, 'source_sha256', sourceSha256)
    setMetadata(db, 'source_path', sourcePath)
    setMetadata(db, 'imported_at', now.toISOString())
    setMetadata(db, 'statistics', JSON.stringify(statistics))
    db.prepare('UPDATE sessions SET revoked_at = ? WHERE revoked_at IS NULL').run(now.toISOString())
  })
  return { entities, sourceSha256, statistics }
}

export function verifySeedIntegrity(db, sourcePath) {
  const stored = db.prepare("SELECT value FROM metadata WHERE key = 'source_sha256'").get()?.value
  const { sourceSha256 } = readSeed(sourcePath)
  return { stored, actual: sourceSha256, matches: stored === sourceSha256 }
}

export function counts(db) {
  const entities = readEntities(db)
  return Object.fromEntries(Object.entries(entities).filter(([, rows]) => rows.length).map(([kind, rows]) => [kind, rows.length]))
}
