import { DatabaseSync } from 'node:sqlite'
import { entityKinds, entityTables, entityRow, normalizeEntities, relationTables } from './entities.js'
import { primaryKeys } from '../../../frontend/src/data/contracts.js'
import { createSchema } from './schema.js'
import { AppError } from '../errors.js'

export function openDatabase(config) {
  const db = new DatabaseSync(config.dbPath)
  createSchema(db)
  return db
}

export function withTransaction(db, callback) {
  db.exec('BEGIN IMMEDIATE')
  try {
    const result = callback()
    db.exec('COMMIT')
    return result
  } catch (error) {
    try {
      db.exec('ROLLBACK')
    } catch {}
    throw error
  }
}

export function getMetadata(db, key, fallback = null) {
  const row = db.prepare('SELECT value FROM metadata WHERE key = ?').get(key)
  return row ? row.value : fallback
}

export function setMetadata(db, key, value) {
  db.prepare('INSERT INTO metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value').run(key, String(value))
}

export function readRevision(db) {
  const revision = Number(getMetadata(db, 'revision', '0'))
  return Number.isSafeInteger(revision) && revision >= 0 ? revision : 0
}

export function writeRevision(db, revision) {
  setMetadata(db, 'revision', revision)
}

export function readEntities(db) {
  const entities = normalizeEntities()
  for (const kind of entityKinds) {
    const definition = entityTables[kind]
    const rows = db.prepare(`SELECT payload FROM ${definition.table} ORDER BY rowid`).all()
    entities[kind] = rows.map((row) => {
      try {
        return JSON.parse(row.payload)
      } catch {
        throw new AppError('STORAGE_CORRUPT', `${kind} 记录无法解析`, { status: 500 })
      }
    })
  }
  return entities
}

const statementCache = new WeakMap()

function upsertStatement(db, table, columns) {
  let cache = statementCache.get(db)
  if (!cache) { cache = new Map(); statementCache.set(db, cache) }
  const key = `${table}:${columns.join(',')}`
  if (cache.has(key)) return cache.get(key)
  const placeholders = columns.map(() => '?').join(', ')
  const updates = columns.filter((column) => column !== 'id').map((column) => `${column} = excluded.${column}`).join(', ')
  const statement = db.prepare(`INSERT INTO ${table} (${columns.join(', ')}) VALUES (${placeholders}) ON CONFLICT(id) DO UPDATE SET ${updates}`)
  cache.set(key, statement)
  return statement
}

export function persistEntities(db, entities) {
  const indexes = {}
  for (const kind of entityKinds) {
    const definition = entityTables[kind]
    const rows = entities[kind] ?? []
    const seen = new Set()
    const columns = [...['id', 'farm_id', 'status', 'version', 'created_at', 'updated_at', 'payload'], ...Object.keys(definition.extra({}))]
    const statement = upsertStatement(db, definition.table, columns)
    for (const row of rows) {
      const record = entityRow(kind, row, entities, indexes)
      if (!record.id) throw new AppError('STORAGE_CORRUPT', `${kind} 缺少稳定主键`, { status: 500 })
      if (seen.has(record.id)) throw new AppError('STORAGE_CORRUPT', `${kind} 主键重复：${record.id}`, { status: 500 })
      seen.add(record.id)
      const values = columns.map((column) => {
        if (column === 'payload') return JSON.stringify(row)
        return record[column] ?? null
      })
      statement.run(...values)
    }
    const existing = db.prepare(`SELECT id FROM ${definition.table}`).all()
    const remove = db.prepare(`DELETE FROM ${definition.table} WHERE id = ?`)
    for (const row of existing) if (!seen.has(row.id)) remove.run(row.id)
  }
  for (const relation of Object.values(relationTables)) {
    db.prepare(`DELETE FROM ${relation.table}`).run()
  }
  for (const definition of Object.values(relationTables)) {
    const insert = db.prepare(`INSERT OR IGNORE INTO ${definition.table} (${definition.left}, ${definition.right}) VALUES (?, ?)`)
    for (const row of entities[definition.kind] ?? []) {
      const ownerId = row[primaryKeys[definition.kind]]
      for (const value of row[definition.field] ?? []) insert.run(ownerId, value)
    }
  }
  return entities
}

export function exportRowsFor(db, exportId) {
  return db.prepare('SELECT payload FROM export_rows WHERE export_id = ? ORDER BY seq').all(exportId).map((row) => JSON.parse(row.payload))
}

export function insertExportRows(db, exportId, rows) {
  db.prepare('DELETE FROM export_rows WHERE export_id = ?').run(exportId)
  const insert = db.prepare('INSERT INTO export_rows(export_id, seq, payload) VALUES (?, ?, ?)')
  rows.forEach((row, index) => insert.run(exportId, index + 1, JSON.stringify(row)))
}

export function setExportFile(db, exportId, { path, byteLength, checksum, createdAt }) {
  db.prepare('INSERT INTO export_files(export_id, path, byte_length, checksum, created_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(export_id) DO UPDATE SET path = excluded.path, byte_length = excluded.byte_length, checksum = excluded.checksum, created_at = excluded.created_at').run(exportId, path, byteLength, checksum, createdAt)
}

export function exportFileFor(db, exportId) {
  return db.prepare('SELECT * FROM export_files WHERE export_id = ?').get(exportId) ?? null
}

export function removeExportFile(db, exportId) {
  db.prepare('DELETE FROM export_files WHERE export_id = ?').run(exportId)
}
