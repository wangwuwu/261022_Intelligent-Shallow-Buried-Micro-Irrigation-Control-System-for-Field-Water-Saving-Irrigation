import { createHash } from 'node:crypto'
import { appendFile, rename, rm, stat, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { buildIrrigationIndex, projectWaterAccounting } from '../../../frontend/src/domain/irrigation.js'
import { scopeIrrigationFacts } from '../../../frontend/src/data/permissions.js'
import { createEntityId } from '../../../frontend/src/data/actions.js'
import { AppError } from '../errors.js'
import { readRevision, setExportFile, setMetadata, withTransaction } from '../db/database.js'

const methodLabels = { MEASURED: '实测', ALLOCATED: '分摊', ESTIMATED: '估算' }
const DAY_MS = 86400000

export function csvCell(value) {
  let text = String(value ?? '')
  if (/^[=+@\-\t\r]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

function normalizeFilters(payload) {
  const filters = JSON.parse(JSON.stringify(payload.filterSnapshot ?? payload.filters ?? {}))
  if (filters.startAt && !filters.start) filters.start = filters.startAt.slice(0, 10)
  if (filters.endAt && !filters.end) filters.end = new Date(Date.parse(filters.endAt) - 1).toISOString().slice(0, 10)
  if (filters.start && filters.end && (Date.parse(filters.end) - Date.parse(filters.start)) / DAY_MS > 365) {
    throw new AppError('EXPORT_WINDOW', '导出区间不能超过366天', { status: 422 })
  }
  delete filters.startAt
  delete filters.endAt
  return filters
}

export function buildExportRows(entities, actor, payload) {
  const filters = normalizeFilters(payload)
  const scoped = scopeIrrigationFacts(entities, actor)
  const projection = projectWaterAccounting(buildIrrigationIndex(scoped), filters)
  return {
    filters,
    rows: projection.rows.map((row) => ({
      ledgerId: row.ledgerId,
      fieldId: row.fieldId,
      fieldName: row.fieldName,
      endedAt: row.endedAt,
      volumeM3: row.volumeM3,
      method: row.method,
      qualityStatus: row.qualityStatus,
    })),
  }
}

export function createExportJob(entities, actor, payload, now = new Date(), revision = 0) {
  const { filters, rows } = buildExportRows(entities, actor, payload)
  const stamp = now.toISOString()
  const exportId = createEntityId('ExportJob')
  const job = {
    exportId,
    farmId: actor.farmId,
    createdBy: actor.userId,
    filterSnapshot: filters,
    sourceRevision: revision,
    status: 'QUEUED',
    fileName: `用水明细_${new Date(now.getTime() + 8 * 3600000).toISOString().slice(0, 10).replaceAll('-', '')}.csv`,
    rowCount: rows.length,
    processedRows: 0,
    progress: 0,
    checksum: null,
    downloadUrl: `/api/v1/exports/${exportId}/file`,
    expiresAt: new Date(now.getTime() + DAY_MS).toISOString(),
    createdAt: stamp,
    updatedAt: stamp,
    version: 1,
    authorizedFieldIds: [...new Set(rows.map((row) => row.fieldId))],
  }
  entities.ExportJob.push(job)
  return { job, rows }
}

export function cancelExportJob(entities, actor, payload, options = {}) {
  const job = entities.ExportJob.find((row) => row.exportId === payload.exportId)
  if (!job) throw new AppError('NOT_FOUND', '导出任务不存在', { status: 404 })
  if (job.farmId !== actor.farmId) throw new AppError('FORBIDDEN', '无权取消此农场的导出任务', { status: 403 })
  if (job.createdBy !== actor.userId && actor.role !== 'ADMIN') throw new AppError('FORBIDDEN', '无权取消此任务', { status: 403 })
  if (!['QUEUED', 'PROCESSING'].includes(job.status)) throw new AppError('EXPORT_STATE', '当前导出任务不能取消', { status: 409 })
  if (options.expectedVersion !== undefined && Number(options.expectedVersion) !== job.version) {
    throw new AppError('VERSION_CONFLICT', '导出任务已更新，请重试取消', { status: 409 })
  }
  Object.assign(job, { status: 'CANCELLED', csvContent: null, updatedAt: new Date().toISOString(), version: job.version + 1 })
  return { job, rows: [] }
}

function directJobUpdate(db, exportId, transform, now = new Date()) {
  const row = db.prepare('SELECT payload FROM export_jobs WHERE id = ?').get(exportId)
  if (!row) return null
  const job = JSON.parse(row.payload)
  transform(job)
  job.version = (job.version ?? 1) + 1
  job.updatedAt = now.toISOString()
  const revision = readRevision(db) + 1
  db.prepare('UPDATE export_jobs SET payload = ?, status = ?, version = ?, updated_at = ? WHERE id = ?').run(JSON.stringify(job), job.status ?? null, job.version, job.updatedAt, exportId)
  setMetadata(db, 'revision', revision)
  return { job, revision }
}

export async function generateExport({ db, config, exportId, notify = () => {} }) {
  let current = await Promise.resolve(withTransaction(db, () => directJobUpdate(db, exportId, (job) => {
    if (job.status !== 'QUEUED') return
    job.status = 'PROCESSING'
    job.processedRows = 0
    job.progress = 0
  })))
  if (!current || current.job.status !== 'PROCESSING') return null
  notify({ revision: current.revision, changedEntities: [{ entityType: 'ExportJob', entityId: exportId, version: current.job.version }] })
  const rows = db.prepare('SELECT payload FROM export_rows WHERE export_id = ? ORDER BY seq').all(exportId).map((row) => JSON.parse(row.payload))
  const partPath = join(config.exportDir, `${exportId}.csv.part`)
  const targetPath = join(config.exportDir, `${exportId}.csv`)
  const hash = createHash('sha256')
  try {
    await writeFile(partPath, '', 'utf8')
    const header = '\uFEFF' + ['账本编号', '田块', '日期', '水量 m³', '计量方式', '状态'].map(csvCell).join(',') + '\r\n'
    hash.update(header, 'utf8')
    await appendFile(partPath, header, 'utf8')
    for (let offset = 0; offset < rows.length; offset += 10) {
      const batch = rows.slice(offset, offset + 10)
      let chunk = ''
      for (const row of batch) {
        const day = new Date(Date.parse(row.endedAt) + 8 * 3600000).toISOString().slice(0, 10)
        chunk += [row.ledgerId, row.fieldName, day, row.volumeM3, methodLabels[row.method] ?? row.method, '已结算'].map(csvCell).join(',') + '\r\n'
      }
      hash.update(chunk, 'utf8')
      await appendFile(partPath, chunk, 'utf8')
      current = await Promise.resolve(withTransaction(db, () => directJobUpdate(db, exportId, (job) => {
        if (job.status !== 'PROCESSING') return
        job.processedRows = Math.min(offset + batch.length, job.rowCount)
        job.progress = job.rowCount ? Math.floor(job.processedRows / job.rowCount * 100) : 100
      })))
      if (!current || current.job.status !== 'PROCESSING') {
        await rm(partPath, { force: true })
        return current?.job ?? null
      }
      notify({ revision: current.revision, changedEntities: [{ entityType: 'ExportJob', entityId: exportId, version: current.job.version }] })
      await new Promise((resolve) => setImmediate(resolve))
    }
    const bytes = await stat(partPath)
    const checksum = hash.digest('hex')
    await rename(partPath, targetPath)
    current = await Promise.resolve(withTransaction(db, () => {
      const result = directJobUpdate(db, exportId, (job) => {
        if (job.status !== 'PROCESSING') return
        Object.assign(job, { status: 'READY', progress: 100, processedRows: job.rowCount, checksum, byteLength: bytes.size, downloadUrl: `/api/v1/exports/${exportId}/file`, failureReason: null })
      })
      if (result?.job.status === 'READY') {
        setExportFile(db, exportId, { path: targetPath, byteLength: bytes.size, checksum, createdAt: new Date().toISOString() })
      }
      return result
    }))
    if (current?.job.status !== 'READY') await rm(targetPath, { force: true })
    notify({ revision: current?.revision ?? readRevision(db), changedEntities: [{ entityType: 'ExportJob', entityId: exportId, version: current?.job.version ?? 1 }] })
    return current?.job ?? null
  } catch (error) {
    await rm(partPath, { force: true })
    await rm(targetPath, { force: true })
    const failed = await Promise.resolve(withTransaction(db, () => directJobUpdate(db, exportId, (job) => {
      Object.assign(job, { status: 'FAILED', failureReason: error.message, rowsSnapshot: [], csvContent: null })
    })))
    notify({ revision: failed?.revision ?? readRevision(db), changedEntities: [{ entityType: 'ExportJob', entityId: exportId, version: failed?.job.version ?? 1 }] })
    return failed?.job ?? null
  }
}

export function readExportContent({ db, config, exportId, actor, entities, now = new Date() }) {
  const job = entities.ExportJob.find((row) => row.exportId === exportId)
  if (!job) throw new AppError('NOT_FOUND', '导出任务不存在', { status: 404 })
  if (job.farmId !== actor.farmId) throw new AppError('FORBIDDEN', '无权读取此导出任务', { status: 403 })
  if (job.createdBy !== actor.userId && actor.role !== 'ADMIN') throw new AppError('FORBIDDEN', '无权读取此导出文件', { status: 403 })
  if (job.status === 'CANCELLED') throw new AppError('EXPORT_UNAVAILABLE', '导出任务已取消', { status: 410 })
  if (job.status !== 'READY') throw new AppError('EXPORT_UNAVAILABLE', '导出任务尚未完成', { status: 410 })
  if (Date.parse(job.expiresAt) <= now.getTime()) throw new AppError('EXPORT_UNAVAILABLE', '原文件已过期，请重新导出', { status: 410 })
  const file = db.prepare('SELECT * FROM export_files WHERE export_id = ?').get(exportId)
  if (!file) throw new AppError('EXPORT_UNAVAILABLE', '原文件不可恢复或已过期，请重新导出', { status: 410 })
  return { job, file }
}
