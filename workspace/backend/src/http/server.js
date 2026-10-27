import { createReadStream } from 'node:fs'
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, join, normalize, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'
import { AppError, errorPayload, toAppError } from '../errors.js'
import {
  cleanupSessions,
  clearSessionCookie,
  createSession,
  resolveSession,
  revokeSession,
  sessionCookie,
  sessionTokenFromCookie,
  verifyPassword,
} from '../services/auth.js'
import { IrrigationStore } from '../services/store.js'
import {
  API_PREFIX,
  checkOrigin,
  compactFilters,
  csvContentDisposition,
  expectedVersionFrom,
  normalizeLocalTimes,
  parseCookies,
  queryParams,
  readBody,
  requireCsrf,
  sendEmpty,
  sendJson,
} from './util.js'

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json; charset=utf-8',
}

function securityHeaders() {
  return {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
  }
}

function sessionPayload(session, store) {
  const state = store.readState()
  return {
    user: session.user,
    csrfToken: session.csrfToken,
    expiresAt: session.expiresAt,
    serverTime: new Date().toISOString(),
    revision: state.revision,
    publicFarm: state.publicFarm,
  }
}

function routeMatcher(pattern) {
  const segments = pattern.split('/').filter(Boolean)
  return (pathname) => {
    const candidate = pathname.split('/').filter(Boolean)
    if (candidate.length !== segments.length) return null
    const params = {}
    for (let index = 0; index < segments.length; index++) {
      const segment = segments[index]
      if (segment.startsWith(':')) params[segment.slice(1)] = decodeURIComponent(candidate[index])
      else if (segment !== candidate[index]) return null
    }
    return params
  }
}

class Routes {
  constructor() {
    this.routes = []
  }

  add(method, pattern, handler, options = {}) {
    this.routes.push({ method, match: routeMatcher(pattern), handler, options })
  }

  match(method, pathname) {
    for (const route of this.routes) {
      if (route.method !== method) continue
      const params = route.match(pathname)
      if (params) return { route, params }
    }
    return null
  }
}

function parseFiltersFromBody(body, extra = {}) {
  return compactFilters({ ...body, filters: { ...extra, ...(body.filters ?? {}) } })
}

export function createIrrigationServer({ db, config }) {
  const clients = new Set()
  const store = new IrrigationStore({
    db,
    config,
    notify: (event) => {
      const payload = `id: ${event.revision ?? 0}\nevent: revision\ndata: ${JSON.stringify({ ...event, serverTime: new Date().toISOString() })}\n\n`
      for (const client of clients) {
        try {
          client.res.write(payload)
        } catch {
          clients.delete(client)
        }
      }
    },
  })

  const loginAttempts = new Map()
  const now = () => Date.now()
  function checkLoginRate(ip, account) {
    const key = `${ip}|${account}`
    const entry = loginAttempts.get(key)
    if (!entry || entry.resetAt < now()) return key
    if (entry.count >= 5) throw new AppError('AUTH_RATE_LIMIT', '登录尝试过于频繁，请稍后再试', { status: 429 })
    return key
  }
  function noteFailure(key) {
    const entry = loginAttempts.get(key)
    if (!entry || entry.resetAt < now()) loginAttempts.set(key, { count: 1, resetAt: now() + 600000 })
    else entry.count++
  }
  function noteSuccess(key) {
    loginAttempts.delete(key)
  }

  const routes = new Routes()
  const add = (...args) => routes.add(...args)

  add('GET', `${API_PREFIX}/health`, async ({ res }) => {
    sendJson(res, 200, { ok: true, now: new Date().toISOString(), revision: store.readState().revision, database: config.dbPath, deviceChannel: config.deviceChannel })
  }, { public: true })

  add('GET', `${API_PREFIX}/bootstrap`, async ({ res }) => {
    const state = store.readState()
    sendJson(res, 200, { publicFarm: state.publicFarm, revision: state.revision, serverTime: new Date().toISOString() })
  }, { public: true })

  add('POST', `${API_PREFIX}/auth/login`, async ({ req, res, body }) => {
    checkOrigin(req, config)
    const account = String(body.account ?? '').trim()
    const password = String(body.password ?? '')
    if (!account || !password) throw new AppError('VALIDATION', '请输入账号和密码', { status: 422, fieldErrors: { account: !account ? '账号必填' : undefined, password: !password ? '密码必填' : undefined } })
    const key = checkLoginRate(req.socket.remoteAddress ?? 'unknown', account)
    if (!verifyPassword(db, account, password)) {
      noteFailure(key)
      throw new AppError('AUTH_FAILED', '账号或密码错误，或账号已停用', { status: 401 })
    }
    const userRow = db.prepare('SELECT payload FROM users WHERE account = ?').get(account)
    const user = userRow ? JSON.parse(userRow.payload) : null
    if (!user || user.status !== 'ENABLED') {
      noteFailure(key)
      throw new AppError('AUTH_FAILED', '账号或密码错误，或账号已停用', { status: 401 })
    }
    noteSuccess(key)
    const session = createSession(db, user.userId, user.version, config.sessionTtlMs)
    const payload = sessionPayload({ ...session, user }, store)
    sendJson(res, 200, payload, { 'Set-Cookie': sessionCookie(session.token, { secure: config.secureCookie, maxAgeMs: config.sessionTtlMs }) })
  }, { public: true })

  add('POST', `${API_PREFIX}/auth/logout`, async ({ req, res, session }) => {
    if (session) requireCsrf(req, session)
    revokeSession(db, session?.token)
    sendEmpty(res, 204, { 'Set-Cookie': clearSessionCookie({ secure: config.secureCookie }) })
  }, { optionalSession: true })

  add('GET', `${API_PREFIX}/auth/session`, async ({ res, session }) => {
    if (!session) {
      const state = store.readState()
      sendJson(res, 200, { user: null, publicFarm: state.publicFarm, revision: state.revision, serverTime: new Date().toISOString() })
      return
    }
    sendJson(res, 200, sessionPayload(session, store))
  }, { optionalSession: true })

  add('GET', `${API_PREFIX}/snapshot`, async ({ res, session }) => {
    sendJson(res, 200, store.snapshotFor(session.user))
  })

  add('GET', `${API_PREFIX}/events`, async ({ req, res, session }) => {
    res.writeHead(200, {
      ...securityHeaders(),
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    })
    res.write(`retry: 3000\n\nid: ${store.readState().revision}\nevent: revision\ndata: ${JSON.stringify({ revision: store.readState().revision, serverTime: new Date().toISOString() })}\n\n`)
    const client = { res, userId: session.user.userId, createdAt: Date.now() }
    clients.add(client)
    const heartbeat = setInterval(() => {
      try {
        res.write(`: ping ${new Date().toISOString()}\n\n`)
      } catch {
        clearInterval(heartbeat)
        clients.delete(client)
      }
    }, 20000)
    heartbeat.unref?.()
    req.on('close', () => {
      clearInterval(heartbeat)
      clients.delete(client)
    })
  })

  add('POST', `${API_PREFIX}/query`, async ({ res, session, body }) => {
    const normalized = normalizeLocalTimes(body)
    const result = await store.query(session.user, normalized.name, normalized.params ?? {}, {})
    sendJson(res, 200, result)
  }, { readOnly: true })

  add('POST', `${API_PREFIX}/commit`, async ({ req, res, session, body }) => {
    const normalized = normalizeLocalTimes(body)
    const result = await store.commit({
      session: { userId: session.user.userId, userVersion: session.user.version },
      actionId: normalized.actionId,
      payload: normalized.payload ?? {},
      options: {
        ...(normalized.options ?? {}),
        clientRequestId: req.headers['idempotency-key'] || normalized.options?.clientRequestId || randomUUID(),
      },
    })
    const headers = result.authChanged ? { 'Set-Cookie': clearSessionCookie({ secure: config.secureCookie }) } : {}
    sendJson(res, 200, result, headers)
  })

  const queryHandler = (name, extra = {}) => async ({ url, res, session, params: routeParams }) => {
    const params = compactFilters(queryParams(url, extra))
    if (routeParams?.id) params.id = routeParams.id
    const normalized = normalizeLocalTimes(params)
    const result = await store.query(session.user, name, normalized)
    sendJson(res, 200, result)
  }

  add('GET', `${API_PREFIX}/overview`, queryHandler('overview'))

  add('GET', `${API_PREFIX}/fields`, queryHandler('Field'))
  add('POST', `${API_PREFIX}/fields`, async (ctx) => commitFromRequest(ctx, 'FIELD_CREATE'))
  add('GET', `${API_PREFIX}/fields/:id`, queryHandler('Field', {}))
  add('PATCH', `${API_PREFIX}/fields/:id`, async (ctx) => commitFromRequest(ctx, 'FIELD_UPDATE', { fieldId: ctx.params.id }))
  add('GET', `${API_PREFIX}/fields/:id/seasons`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'CropSeason', compactFilters({ filters: { fieldId: ctx.params.id, ...(queryParams(ctx.url).filters ?? {}) } }))))
  add('POST', `${API_PREFIX}/fields/:id/seasons`, async (ctx) => commitFromRequest(ctx, 'SEASON_CREATE', {
    fieldId: ctx.params.id,
    expectedFieldVersion: ctx.body.expectedFieldVersion ?? ctx.body.fieldVersion ?? ctx.body.expectedVersions?.fieldId ?? expectedVersionFrom(ctx.req, ctx.body),
  }))
  add('PATCH', `${API_PREFIX}/seasons/:id`, async (ctx) => commitFromRequest(ctx, 'SEASON_UPDATE', {
    seasonId: ctx.params.id,
    expectedFieldVersion: ctx.body.expectedFieldVersion ?? ctx.body.fieldVersion ?? ctx.body.expectedVersions?.fieldId,
  }))

  add('GET', `${API_PREFIX}/network`, async ({ res, session }) => {
    const snapshot = store.snapshotFor(session.user)
    sendJson(res, 200, {
      revision: snapshot.revision,
      pipeNodes: snapshot.entities.PipeNode,
      zones: snapshot.entities.IrrigationZone,
      devices: snapshot.entities.Device,
      policies: snapshot.entities.SystemPolicy,
    })
  })
  add('POST', `${API_PREFIX}/pipe-nodes`, async (ctx) => commitFromRequest(ctx, 'PIPE_SAVE'))
  add('PATCH', `${API_PREFIX}/pipe-nodes/:id`, async (ctx) => commitFromRequest(ctx, 'PIPE_SAVE', { nodeId: ctx.params.id }))
  add('POST', `${API_PREFIX}/zones`, async (ctx) => commitFromRequest(ctx, 'ZONE_CREATE'))
  add('PATCH', `${API_PREFIX}/zones/:id`, async (ctx) => commitFromRequest(ctx, 'ZONE_UPDATE', { zoneId: ctx.params.id }))

  add('GET', `${API_PREFIX}/devices`, queryHandler('Device'))
  add('POST', `${API_PREFIX}/devices`, async (ctx) => commitFromRequest(ctx, 'DEVICE_CREATE'))
  add('GET', `${API_PREFIX}/devices/:id`, queryHandler('Device', {}))
  add('POST', `${API_PREFIX}/devices/:id/verify`, async (ctx) => commitFromRequest(ctx, 'DEVICE_VERIFY', { deviceId: ctx.params.id }))
  add('GET', `${API_PREFIX}/devices/:id/points`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'Point', compactFilters({ filters: { deviceId: ctx.params.id, ...(queryParams(ctx.url).filters ?? {}) } }))))
  add('GET', `${API_PREFIX}/devices/:id/calibrations`, async ({ params, res, session }) => {
    const snapshot = store.snapshotFor(session.user)
    const pointIds = new Set(snapshot.entities.Point.filter((point) => point.deviceId === params.id).map((point) => point.pointId))
    const items = snapshot.entities.Calibration.filter((row) => pointIds.has(row.pointId))
    sendJson(res, 200, { items, total: items.length, revision: snapshot.revision })
  })
  add('GET', `${API_PREFIX}/devices/:id/diagnostics`, async ({ params, res, session }) => {
    const snapshot = store.snapshotFor(session.user)
    const device = snapshot.entities.Device.find((row) => row.deviceId === params.id)
    if (!device) throw new AppError('NOT_FOUND', '设备不存在', { status: 404 })
    const points = snapshot.entities.Point.filter((point) => point.deviceId === params.id)
    const pointIds = new Set(points.map((point) => point.pointId))
    const readings = snapshot.entities.TelemetryReading.filter((row) => pointIds.has(row.pointId)).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))
    sendJson(res, 200, { entity: device, points, latestReadings: readings.slice(0, 200), revision: snapshot.revision })
  })
  add('PATCH', `${API_PREFIX}/points/:id`, async (ctx) => commitFromRequest(ctx, 'POINT_UPDATE', { pointId: ctx.params.id }))
  add('POST', `${API_PREFIX}/points/:id/calibrations`, async (ctx) => commitFromRequest(ctx, 'POINT_CALIBRATE', { pointId: ctx.params.id }))

  add('GET', `${API_PREFIX}/monitor/readings`, async (ctx) => {
    const result = monitorResult(ctx)
    sendJson(ctx.res, 200, result)
  })
  add('GET', `${API_PREFIX}/monitor/series`, async (ctx) => {
    const result = monitorResult(ctx, { paginate: false })
    const groups = new Map()
    for (const row of result.items ?? []) {
      const list = groups.get(row.pointId) ?? []
      list.push({ observedAt: row.observedAt, value: row.value, quality: row.quality, readingId: row.readingId })
      groups.set(row.pointId, list)
    }
    const series = [...groups].map(([pointId, readings]) => {
      readings.sort((a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt))
      if (readings.length <= 500) return { pointId, readings }
      const step = readings.length / 500
      return { pointId, readings: Array.from({ length: 500 }, (_, index) => readings[Math.floor(index * step)]) }
    })
    sendJson(ctx.res, 200, { series, total: result.total, revision: result.revision })
  })

  add('GET', `${API_PREFIX}/strategies`, queryHandler('Strategy'))
  add('POST', `${API_PREFIX}/strategies`, async (ctx) => commitFromRequest(ctx, 'STRATEGY_CREATE'))
  add('GET', `${API_PREFIX}/strategies/:id`, queryHandler('Strategy', {}))
  add('PATCH', `${API_PREFIX}/strategies/:id`, async (ctx) => commitFromRequest(ctx, 'STRATEGY_UPDATE', { strategyId: ctx.params.id }))
  add('POST', `${API_PREFIX}/strategies/:id/simulate`, async ({ params, res, session, body }) => {
    const normalized = normalizeLocalTimes(body ?? {})
    sendJson(res, 200, await store.query(session.user, 'simulation', {
      strategyId: params.id,
      asOf: normalized.asOf,
      representativePointByZone: normalized.representativePointByZone ?? {},
    }))
  }, { readOnly: true })

  add('GET', `${API_PREFIX}/plans`, queryHandler('Plan'))
  add('POST', `${API_PREFIX}/plans`, async (ctx) => commitFromRequest(ctx, 'PLAN_CREATE'))
  add('GET', `${API_PREFIX}/plans/:id`, queryHandler('Plan', {}))
  add('PATCH', `${API_PREFIX}/plans/:id`, async (ctx) => commitFromRequest(ctx, 'PLAN_UPDATE', { planId: ctx.params.id }))
  add('POST', `${API_PREFIX}/plans/assess-resources`, async ({ res, session, body }) => {
    const normalized = normalizeLocalTimes(body ?? {})
    sendJson(res, 200, await store.query(session.user, 'resources', normalized))
  }, { readOnly: true })
  add('POST', `${API_PREFIX}/plans/:id/publish`, async (ctx) => commitFromRequest(ctx, 'PLAN_PUBLISH', { planId: ctx.params.id }))
  add('POST', `${API_PREFIX}/plans/:id/cancel`, async (ctx) => commitFromRequest(ctx, 'PLAN_CANCEL', { planId: ctx.params.id }))

  add('GET', `${API_PREFIX}/runs`, queryHandler('IrrigationRun'))
  add('GET', `${API_PREFIX}/runs/:id`, queryHandler('IrrigationRun', {}))
  add('GET', `${API_PREFIX}/runs/:id/steps`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'RunStep', compactFilters({ filters: { runId: ctx.params.id, ...(queryParams(ctx.url).filters ?? {}) } }))))
  add('GET', `${API_PREFIX}/runs/:id/commands`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'CommandOutbox', compactFilters({ filters: { runId: ctx.params.id, ...(queryParams(ctx.url).filters ?? {}) } }))))
  add('GET', `${API_PREFIX}/runs/:id/water`, async ({ params, res, session }) => {
    const report = await store.query(session.user, 'water', {})
    sendJson(res, 200, { rows: report.rows.filter((row) => row.runId === params.id), byRun: report.byRun.filter((row) => row.runId === params.id), revision: report.revision })
  })
  for (const [suffix, action] of [['start', 'RUN_START'], ['pause', 'RUN_PAUSE'], ['resume', 'RUN_RESUME'], ['stop', 'RUN_STOP']]) {
    add('POST', `${API_PREFIX}/runs/:id/${suffix}`, async (ctx) => commitFromRequest(ctx, action, { runId: ctx.params.id }))
  }

  add('GET', `${API_PREFIX}/alarms`, queryHandler('Alarm'))
  add('GET', `${API_PREFIX}/alarms/:id`, queryHandler('Alarm', {}))
  add('POST', `${API_PREFIX}/alarms/:id/acknowledge`, async (ctx) => commitFromRequest(ctx, 'ALARM_ACK', { alarmId: ctx.params.id }))
  add('POST', `${API_PREFIX}/alarms/:id/close`, async (ctx) => commitFromRequest(ctx, 'ALARM_CLOSE', { alarmId: ctx.params.id }))

  add('GET', `${API_PREFIX}/work-orders`, queryHandler('WorkOrder'))
  add('POST', `${API_PREFIX}/work-orders`, async (ctx) => commitFromRequest(ctx, 'WORKORDER_CREATE'))
  add('GET', `${API_PREFIX}/work-orders/:id`, queryHandler('WorkOrder', {}))
  for (const [suffix, action] of [['accept', 'WORKORDER_ACCEPT'], ['submit', 'WORKORDER_SUBMIT'], ['approve', 'WORKORDER_APPROVE'], ['return', 'WORKORDER_RETURN']]) {
    add('POST', `${API_PREFIX}/work-orders/:id/${suffix}`, async (ctx) => commitFromRequest(ctx, action, { workOrderId: ctx.params.id }))
  }

  add('GET', `${API_PREFIX}/water/report`, queryHandler('water'))
  add('GET', `${API_PREFIX}/water/ledger`, async (ctx) => {
    const report = await store.query(ctx.session.user, 'water', compactFilters(queryParams(ctx.url)))
    const page = Math.max(1, Number(ctx.url.searchParams.get('page') || 1))
    const pageSize = Math.min(100, Math.max(1, Number(ctx.url.searchParams.get('pageSize') || 15)))
    const rows = [...report.rows].sort((a, b) => Date.parse(b.endedAt) - Date.parse(a.endedAt) || a.ledgerId.localeCompare(b.ledgerId))
    sendJson(ctx.res, 200, { ...report, items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, pageSize })
  })
  add('GET', `${API_PREFIX}/water/baselines`, queryHandler('WaterBaseline'))

  add('GET', `${API_PREFIX}/exports`, queryHandler('ExportJob'))
  add('POST', `${API_PREFIX}/exports`, async (ctx) => commitFromRequest(ctx, 'EXPORT_CREATE', { filters: ctx.body.filters ?? ctx.body }))
  add('GET', `${API_PREFIX}/exports/:id`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'ExportJob', { id: ctx.params.id })))
  add('POST', `${API_PREFIX}/exports/:id/cancel`, async (ctx) => commitFromRequest(ctx, 'EXPORT_CANCEL', { exportId: ctx.params.id }))
  add('GET', `${API_PREFIX}/exports/:id/file`, async ({ params, res, session }) => {
    const file = await store.exportFile(session.user, params.id)
    const size = file.file.byte_length
    res.writeHead(200, {
      ...securityHeaders(),
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Length': size,
      'Content-Disposition': csvContentDisposition(file.job.fileName),
      'Cache-Control': 'no-store',
    })
    createReadStream(file.file.path).pipe(res)
  })

  add('GET', `${API_PREFIX}/users`, queryHandler('User'))
  add('POST', `${API_PREFIX}/users`, async (ctx) => commitFromRequest(ctx, 'USER_CREATE'))
  add('PATCH', `${API_PREFIX}/users/:id`, async (ctx) => commitFromRequest(ctx, 'USER_UPDATE', { userId: ctx.params.id }))
  add('POST', `${API_PREFIX}/users/:id/disable`, async (ctx) => commitFromRequest(ctx, 'USER_DISABLE', { userId: ctx.params.id, reason: ctx.body.reason }))
  add('POST', `${API_PREFIX}/users/:id/enable`, async (ctx) => commitFromRequest(ctx, 'USER_ENABLE', { userId: ctx.params.id }))
  add('GET', `${API_PREFIX}/policy`, async ({ res, session }) => {
    const current = await store.query(session.user, 'SystemPolicy', { pageSize: 1 })
    sendJson(res, 200, { entity: current.items?.[0] ?? null, revision: current.revision })
  })
  add('PATCH', `${API_PREFIX}/policy`, async (ctx) => {
    const current = await store.query(ctx.session.user, 'SystemPolicy', { pageSize: 1 })
    const policyId = ctx.body.policyId ?? current.items?.[0]?.policyId
    await commitFromRequest(ctx, 'POLICY_SAVE', { policyId })
  })

  add('GET', `${API_PREFIX}/audit`, queryHandler('AuditLog'))
  add('GET', `${API_PREFIX}/audit/:id`, async (ctx) => sendJson(ctx.res, 200, await store.query(ctx.session.user, 'AuditLog', { id: ctx.params.id })))

  async function commitFromRequest(ctx, actionId, additions = {}) {
    const body = normalizeLocalTimes(ctx.body ?? {})
    for (const key of ['expectedVersion', 'expectedVersions', 'clientRequestId', 'idempotencyKey']) delete body[key]
    const payload = { ...body, ...additions }
    if (additions.filters) payload.filters = additions.filters
    const expectedVersion = expectedVersionFrom(ctx.req, ctx.body ?? {})
    const result = await store.commit({
      session: { userId: ctx.session.user.userId, userVersion: ctx.session.user.version },
      actionId,
      payload,
      options: {
        expectedVersion,
        expectedVersions: ctx.body?.expectedVersions,
        clientRequestId: ctx.req.headers['idempotency-key'] || ctx.body?.clientRequestId || randomUUID(),
      },
    })
    const headers = {}
    if (result.authChanged) headers['Set-Cookie'] = clearSessionCookie({ secure: config.secureCookie })
    sendJson(ctx.res, 200, result, headers)
  }

  function monitorResult(ctx, { paginate = true } = {}) {
    const params = compactFilters(queryParams(ctx.url))
    const snapshot = store.snapshotFor(ctx.session.user)
    const pointFilters = params.filters
    const zoneId = pointFilters.zoneId
    const pointIds = new Set(
      snapshot.entities.Point
        .filter((point) => (!zoneId || point.zoneId === zoneId) && (!pointFilters.pointId || point.pointId === pointFilters.pointId) && (!pointFilters.depthCm || String(point.depthCm) === String(pointFilters.depthCm)))
        .map((point) => point.pointId),
    )
    const start = pointFilters.start ? Date.parse(`${pointFilters.start}T00:00:00+08:00`) : -Infinity
    const end = pointFilters.end ? Date.parse(`${pointFilters.end}T00:00:00+08:00`) + 86400000 : Infinity
    let rows = snapshot.entities.TelemetryReading
      .filter((row) => pointIds.has(row.pointId))
      .filter((row) => Date.parse(row.observedAt) >= start && Date.parse(row.observedAt) < end)
      .sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt) || a.readingId.localeCompare(b.readingId))
    const total = rows.length
    const pageSize = Math.min(100, Math.max(1, Number(params.pageSize) || 15))
    const page = Math.min(Math.max(1, Number(params.page) || 1), Math.max(1, Math.ceil(total / pageSize)))
    if (paginate) rows = rows.slice((page - 1) * pageSize, page * pageSize)
    return { items: rows, total, page, pageSize, revision: snapshot.revision }
  }

  async function serveStatic(req, res, url) {
    if (!config.staticDir) {
      sendJson(res, 404, { code: 'NOT_FOUND', message: '未配置前端静态目录' })
      return
    }
    const requested = decodeURIComponent(url.pathname)
    const safePath = normalize(requested).replace(/^(\.\.[/\\])+/, '')
    let filePath = resolve(join(config.staticDir, safePath))
    if (!filePath.startsWith(resolve(config.staticDir))) {
      sendJson(res, 403, { code: 'FORBIDDEN', message: '禁止访问该路径' })
      return
    }
    let info = null
    try {
      info = await stat(filePath)
    } catch {}
    if (!info || info.isDirectory()) {
      if (requested.includes('.')) {
        sendJson(res, 404, { code: 'NOT_FOUND', message: '静态资源不存在' })
        return
      }
      filePath = join(config.staticDir, 'index.html')
      try {
        info = await stat(filePath)
      } catch {
        sendJson(res, 404, { code: 'NOT_FOUND', message: '前端构建产物不存在，请先运行前端构建' })
        return
      }
    }
    const headers = {
      ...securityHeaders(),
      'Content-Type': mimeTypes[extname(filePath).toLowerCase()] ?? 'application/octet-stream',
      'Content-Length': info.size,
      'Cache-Control': filePath.includes(`${join(config.staticDir, 'assets')}`) ? 'public, max-age=31536000, immutable' : 'no-cache',
    }
    res.writeHead(200, headers)
    if (req.method === 'HEAD') res.end()
    else createReadStream(filePath).pipe(res)
  }

  const server = createServer(async (req, res) => {
    const requestId = randomUUID()
    res.setHeader('X-Request-Id', requestId)
    try {
      const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`)
      const pathname = url.pathname.length > 1 ? url.pathname.replace(/\/+$/, '') : url.pathname
      if (!pathname.startsWith('/api')) {
        await serveStatic(req, res, url)
        return
      }
      const matched = routes.match(req.method, pathname)
      if (!matched) {
        if (pathname.startsWith(API_PREFIX)) throw new AppError('NOT_FOUND', '接口不存在', { status: 404 })
        throw new AppError('NOT_FOUND', '资源不存在', { status: 404 })
      }
      const { route, params } = matched
      checkOrigin(req, config)
      const cookies = parseCookies(req.headers.cookie)
      const token = sessionTokenFromCookie(req.headers.cookie) ?? cookies.get('irrigation_session') ?? null
      let session = null
      if (!route.options.public) {
        if (route.options.optionalSession) {
          session = token ? resolveSession(db, token) : null
        } else {
          session = resolveSession(db, token)
          if (!session) throw new AppError('UNAUTHENTICATED', '请先登录', { status: 401 })
          if (!route.options.readOnly) requireCsrf(req, session)
        }
      }
      let body = {}
      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) body = await readBody(req, config.bodyLimitBytes)
      await route.handler({ req, res, url, params, body, session, store, db, config, requestId })
    } catch (error) {
      if (res.writableEnded) return
      if (error?.name === 'AbortError') {
        sendEmpty(res, 499)
        return
      }
      const normalized = toAppError(error, requestId)
      if (normalized.status >= 500) console.error(`[${requestId}] ${req.method} ${req.url}`, error)
      sendJson(res, normalized.status, errorPayload(normalized, requestId))
    }
  })

  const cleanup = setInterval(() => {
    try {
      cleanupSessions(db)
    } catch (error) {
      console.error('清理会话失败', error.message)
    }
    const cutoff = now()
    for (const [key, entry] of loginAttempts) if (entry.resetAt < cutoff) loginAttempts.delete(key)
    try {
      db.prepare('DELETE FROM idempotency_requests WHERE created_at < ?').run(new Date(cutoff - 7 * 86400000).toISOString())
    } catch {}
  }, 3600000)
  cleanup.unref?.()

  server.on('close', () => {
    clearInterval(cleanup)
    for (const client of clients) {
      try {
        client.res.end()
      } catch {}
    }
    clients.clear()
  })

  server.requestTimeout = config.requestTimeoutMs
  server.headersTimeout = Math.min(config.requestTimeoutMs, 20000)
  server.irrigation = { store, clients }
  return server
}
