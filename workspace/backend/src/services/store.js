import { createHash, randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { buildIrrigationIndex, projectWaterAccounting } from '../../../frontend/src/domain/irrigation.js'
import { queryIrrigationFacts } from '../../../frontend/src/data/queries.js'
import { applyIrrigationAction, assessPlanDraft, createEntityId, redactResourceAssessment } from '../../../frontend/src/data/actions.js'
import { canOperate, scopeIrrigationFacts } from '../../../frontend/src/data/permissions.js'
import { cloneFacts } from '../../../frontend/src/data/contracts.js'
import {
  insertExportRows,
  persistEntities,
  readEntities,
  readRevision,
  setMetadata,
  withTransaction,
  writeRevision,
} from '../db/database.js'
import { AppError } from '../errors.js'
import {
  buildExportRows,
  cancelExportJob,
  createExportJob,
  generateExport,
  readExportContent,
} from './exports.js'
import { revokeUserSessions } from './auth.js'

const sha256 = (value) => createHash('sha256').update(value).digest('hex')
const clone = (value) => JSON.parse(JSON.stringify(value))

export class IrrigationStore {
  constructor({ db, config, notify = () => {} }) {
    this.db = db
    this.config = config
    this.notify = notify
  }

  now() {
    return new Date()
  }

  publicFarm() {
    const row = this.db.prepare('SELECT payload FROM farms ORDER BY rowid LIMIT 1').get()
    if (!row) return null
    const farm = JSON.parse(row.payload)
    return { farmId: farm.farmId, name: farm.name }
  }

  readState() {
    return { entities: readEntities(this.db), revision: readRevision(this.db), publicFarm: this.publicFarm() }
  }

  actorFrom(entities, session) {
    if (!session?.userId) throw new AppError('UNAUTHENTICATED', '请先登录', { status: 401 })
    const actor = entities.User.find((row) => row.userId === session.userId)
    if (!actor || actor.status !== 'ENABLED' || actor.version !== session.userVersion) {
      throw new AppError('UNAUTHENTICATED', '会话已失效，请重新登录', { status: 401 })
    }
    return actor
  }

  snapshotFor(actor) {
    const { entities, revision, publicFarm } = this.readState()
    return {
      entities: scopeIrrigationFacts(entities, actor),
      revision,
      user: clone(actor),
      publicFarm,
      serverTime: this.now().toISOString(),
    }
  }

  async query(actor, name, params = {}, { signal, now = this.now() } = {}) {
    if (signal?.aborted) throw new DOMException('读取已取消', 'AbortError')
    if (name === 'publicFarm') return { entity: this.publicFarm(), revision: readRevision(this.db) }
    const { entities, revision } = this.readState()
    const current = this.actorFrom(entities, { userId: actor?.userId, userVersion: actor?.version })
    if (name === 'exportFile') {
      const file = readExportContent({ db: this.db, config: this.config, exportId: params.exportId, actor: current, entities, now })
      let content
      try {
        content = readFileSync(file.file.path, 'utf8')
      } catch {
        throw new AppError('EXPORT_UNAVAILABLE', '原文件不可恢复或已过期，请重新导出', { status: 410 })
      }
      return { fileName: file.job.fileName, content, checksum: file.job.checksum, revision }
    }
    if (['resources', 'planResources', 'PLAN_RESOURCES', 'QUERY_PLAN_CONFLICTS'].includes(name)) {
      if (!canOperate(current, 'PLAN_CREATE', null, entities)) throw new AppError('FORBIDDEN', '无权检查轮灌编排资源', { status: 403 })
      const draft = clone(params.draft ?? params.planDraft ?? params)
      if (draft.farmId && draft.farmId !== current.farmId) throw new AppError('FORBIDDEN', '计划不属于当前农场', { status: 403 })
      draft.farmId = current.farmId
      for (const step of draft.steps ?? []) {
        const zone = entities.IrrigationZone.find((row) => row.zoneId === step.zoneId)
        if (!zone || !canOperate(current, 'PLAN_CREATE', zone, entities)) throw new AppError('FORBIDDEN', '无权检查该轮灌分区', { status: 403 })
      }
      const assessment = redactResourceAssessment(assessPlanDraft(entities, draft, now), entities, current)
      return { ...assessment, revision }
    }
    if (name === 'snapshot') return this.snapshotFor(current)
    const scoped = scopeIrrigationFacts(entities, current)
    return queryIrrigationFacts(scoped, revision, current, name, params, now)
  }

  async commit({ session, actionId, payload = {}, options = {} }, now = this.now()) {
    if (!actionId) throw new AppError('VALIDATION', '缺少业务动作', { status: 422 })
    const clientRequestId = options.clientRequestId || options.idempotencyKey || randomUUID()
    const submitted = clone(payload)
    const requestOptions = {
      ...options,
      clientRequestId,
      expectedVersion: options.expectedVersion,
      expectedVersions: options.expectedVersions,
    }
    const requestHash = sha256(JSON.stringify({ actionId, payload: submitted, expectedVersion: options.expectedVersion ?? null, expectedVersions: options.expectedVersions ?? null }))
    let exportIdToGenerate = null
    let response = null
    let revokedActors = false

    response = withTransaction(this.db, () => {
      const entities = readEntities(this.db)
      const actor = this.actorFrom(entities, session)
      const revision = readRevision(this.db)
      const previous = this.db.prepare('SELECT request_hash, response FROM idempotency_requests WHERE user_id = ? AND action_id = ? AND client_request_id = ?').get(actor.userId, actionId, clientRequestId)
      if (previous) {
        if (previous.request_hash !== requestHash) {
          throw new AppError('IDEMPOTENCY_CONFLICT', '同一请求编号不能提交不同内容', { status: 409 })
        }
        const replayed = JSON.parse(previous.response)
        return { ...replayed, replayed: true }
      }
      if (!canOperate(actor, actionId, null, entities)) throw new AppError('FORBIDDEN', '无权执行此操作', { status: 403 })
      const next = clone(entities)
      let applied
      if (actionId === 'EXPORT_CREATE') {
        const created = createExportJob(next, actor, submitted, now, revision)
        applied = {
          entityId: created.job.exportId,
          version: 1,
          changedEntities: [{ entityType: 'ExportJob', entityId: created.job.exportId, version: 1 }],
          result: { exportId: created.job.exportId },
        }
        applied.pendingExportRows = created.rows
        exportIdToGenerate = created.job.exportId
      } else if (actionId === 'EXPORT_CANCEL') {
        const cancelled = cancelExportJob(next, actor, submitted, requestOptions)
        applied = {
          entityId: cancelled.job.exportId,
          version: cancelled.job.version,
          changedEntities: [{ entityType: 'ExportJob', entityId: cancelled.job.exportId, version: cancelled.job.version }],
          result: { exportId: cancelled.job.exportId },
        }
      } else {
        applied = applyIrrigationAction(next, actor, actionId, submitted, requestOptions, now)
      }
      if (actionId.startsWith('EXPORT_')) {
        const audit = {
          auditId: createEntityId('AuditLog'),
          farmId: actor.farmId,
          actorId: actor.userId,
          actionId,
          entityType: 'ExportJob',
          entityId: applied.entityId,
          beforeVersion: null,
          afterVersion: applied.version,
          occurredAt: new Date(now).toISOString(),
          correlationId: clientRequestId,
          result: 'SUCCESS',
          detail: {},
        }
        next.AuditLog.push(audit)
        applied.changedEntities.push({ entityType: 'AuditLog', entityId: audit.auditId, version: 1 })
      }
      const nextRevision = revision + 1
      persistEntities(this.db, next)
      if (applied.pendingExportRows) insertExportRows(this.db, applied.entityId, applied.pendingExportRows)
      writeRevision(this.db, nextRevision)
      delete applied.pendingExportRows
      const result = { ...applied, revision: nextRevision, replayed: false }
      this.db.prepare('INSERT INTO idempotency_requests(user_id, action_id, client_request_id, request_hash, response, created_at) VALUES (?, ?, ?, ?, ?, ?)')
        .run(actor.userId, actionId, clientRequestId, requestHash, JSON.stringify(result), new Date(now).toISOString())
      const changedUsers = applied.changedEntities.filter((change) => change.entityType === 'User').map((change) => change.entityId)
      if (changedUsers.length) {
        revokeUserSessions(this.db, changedUsers, now)
        if (changedUsers.includes(actor.userId)) revokedActors = true
      }
      return result
    })

    if (response.replayed) return response
    if (exportIdToGenerate) {
      setImmediate(() => {
        generateExport({ db: this.db, config: this.config, exportId: exportIdToGenerate, notify: (event) => this.emit(event) })
          .catch((error) => console.error('导出任务生成失败', error))
      })
    }
    this.emit({
      revision: response.revision,
      changedEntities: response.changedEntities,
      authChanged: revokedActors,
      actionId,
      clientRequestId,
    })
    return { ...response, authChanged: revokedActors }
  }

  emit(event) {
    try {
      this.notify(event)
    } catch (error) {
      console.error('推送业务事件失败', error?.message)
    }
  }

  waterReport(actor, filters) {
    const { entities } = this.readState()
    const current = this.actorFrom(entities, { userId: actor.userId, userVersion: actor.version })
    const scoped = scopeIrrigationFacts(entities, current)
    return projectWaterAccounting(buildIrrigationIndex(scoped), filters)
  }

  async exportFile(actor, exportId) {
    const { entities } = this.readState()
    const current = this.actorFrom(entities, { userId: actor.userId, userVersion: actor.version })
    return readExportContent({ db: this.db, config: this.config, exportId, actor: current, entities, now: this.now() })
  }

  async buildExportPreview(actor, filters) {
    const { entities } = this.readState()
    return buildExportRows(entities, actor, { filters })
  }

  importMetadata() {
    const source = this.db.prepare("SELECT value FROM metadata WHERE key = 'source_sha256'").get()
    const importedAt = this.db.prepare("SELECT value FROM metadata WHERE key = 'imported_at'").get()
    return { sourceSha256: source?.value ?? null, importedAt: importedAt?.value ?? null }
  }

  updateMetadata(key, value) {
    setMetadata(this.db, key, value)
  }
}
