import test from 'node:test'
import assert from 'node:assert/strict'
import { createTempBackend, findUser, seedPassword, startServer } from './helpers.js'

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

test('共享资料导入后可以登录并按授权读取总览与用水报表', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  const server = await startServer(context)
  t.after(() => server.close())

  const bootstrap = await server.api('/bootstrap')
  assert.equal(bootstrap.status, 200)
  assert.equal(bootstrap.payload.publicFarm.name, '冀州润禾示范农场')

  const admin = await server.login('zyq.admin', 'AdminPass123!')
  assert.equal(admin.user.role, 'ADMIN')
  assert.match(admin.session.expiresAt, /^\d{4}-\d{2}-\d{2}T/)

  const snapshot = await server.api('/snapshot', { cookie: admin.cookie })
  assert.equal(snapshot.status, 200)
  assert.equal(snapshot.payload.entities.Field.length, 15)
  assert.equal(snapshot.payload.entities.Session.length, 0)

  const overview = await server.api('/overview', { cookie: admin.cookie })
  assert.equal(overview.status, 200)
  assert.equal(overview.payload.fieldAreaMu, 555)
  assert.equal(overview.payload.runningCount, 1)

  const water = await server.api('/water/report', { cookie: admin.cookie })
  assert.equal(water.status, 200)
  assert.equal(water.payload.totalM3, 4963.5)
  assert.equal(water.payload.measuredM3, 4928.9)
  assert.equal(water.payload.allocatedM3, 34.6)
  assert.equal(water.payload.coveredAreaMu, 555)
  assert.equal(water.payload.perMuM3, 8.94)
  assert.equal(water.payload.baseline.savingPercent, 16.52)
  assert.equal(water.payload.farmSavingPercent, null)

  const fields = await server.api('/fields?page=1&pageSize=15', { cookie: admin.cookie })
  assert.equal(fields.status, 200)
  assert.equal(fields.payload.total, 15)
  assert.equal(fields.payload.items.length, 15)
  assert.equal(fields.payload.items[0].name, '东渠北畦')

  const detail = await server.api(`/fields/${fields.payload.items[0].fieldId}`, { cookie: admin.cookie })
  assert.equal(detail.status, 200)
  assert.equal(detail.payload.entity.fieldId, fields.payload.items[0].fieldId)
})

test('只读账号不能写入或读取账号审计', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  const viewer = findUser(context.db, 'VIEWER')
  seedPassword(context.db, viewer.account, 'ViewerPass123!')
  const server = await startServer(context)
  t.after(() => server.close())
  const session = await server.login(viewer.account, 'ViewerPass123!')
  const snapshot = await server.api('/snapshot', { cookie: session.cookie })
  const field = snapshot.payload.entities.Field[0]
  const commit = await server.api('/commit', {
    method: 'POST',
    cookie: session.cookie,
    csrf: session.csrf,
    body: { actionId: 'FIELD_UPDATE', payload: { ...field, name: '越权修改' }, options: { expectedVersion: field.version } },
  })
  assert.equal(commit.status, 403)
  assert.equal(commit.payload.code, 'FORBIDDEN')
  const users = await server.api('/users', { cookie: session.cookie })
  assert.equal(users.status, 403)
})

test('田块修改持久化、版本冲突和幂等重放符合契约', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  let server = await startServer(context)
  const admin = await server.login('zyq.admin', 'AdminPass123!')
  const fields = await server.api('/fields?page=1&pageSize=1', { cookie: admin.cookie })
  const field = fields.payload.items[0]
  const key = 'field-update-test-1'
  const payload = { ...field, name: `${field.name}·后端验证` }
  const updated = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    headers: { 'Idempotency-Key': key },
    body: { actionId: 'FIELD_UPDATE', payload, options: { expectedVersion: field.version } },
  })
  assert.equal(updated.status, 200)
  assert.equal(updated.payload.version, field.version + 1)
  assert.equal(updated.payload.replayed, false)
  assert.ok(updated.payload.changedEntities.some((change) => change.entityType === 'Field'))

  const replay = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    headers: { 'Idempotency-Key': key },
    body: { actionId: 'FIELD_UPDATE', payload, options: { expectedVersion: field.version } },
  })
  assert.equal(replay.status, 200)
  assert.equal(replay.payload.replayed, true)
  assert.equal(replay.payload.revision, updated.payload.revision)

  const stale = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    body: { actionId: 'FIELD_UPDATE', payload: { ...field, name: '旧版本修改' }, options: { expectedVersion: field.version } },
  })
  assert.equal(stale.status, 409)
  assert.equal(stale.payload.code, 'VERSION_CONFLICT')

  const conflict = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    headers: { 'Idempotency-Key': key },
    body: { actionId: 'FIELD_UPDATE', payload: { ...field, name: '不同内容' }, options: { expectedVersion: field.version } },
  })
  assert.equal(conflict.status, 409)
  assert.equal(conflict.payload.code, 'IDEMPOTENCY_CONFLICT')

  await server.close()
  context.db.close()
  context.db = context.reopen()
  server = await startServer(context)
  t.after(() => server.close())
  const again = await server.login('zyq.admin', 'AdminPass123!')
  const after = await server.api('/fields?page=1&pageSize=1', { cookie: again.cookie })
  assert.equal(after.payload.items[0].name, `${field.name}·后端验证`)
  assert.equal(after.payload.items[0].version, field.version + 1)
})

test('取消待执行计划在同一事务中停止排队运行并可幂等重放', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  const server = await startServer(context)
  t.after(() => server.close())
  const admin = await server.login('zyq.admin', 'AdminPass123!')
  const plans = await server.api('/plans?page=1&pageSize=100', { cookie: admin.cookie })
  const plan = plans.payload.items.find((row) => row.status === 'PUBLISHED')
  assert.ok(plan)
  const runs = await server.api(`/runs?planId=${plan.planId}`, { cookie: admin.cookie })
  const run = runs.payload.items.find((row) => row.planId === plan.planId)
  assert.equal(run.status, 'QUEUED')
  const key = 'plan-cancel-test-1'
  const cancel = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    headers: { 'Idempotency-Key': key },
    body: { actionId: 'PLAN_CANCEL', payload: { planId: plan.planId, reason: '天气变化取消本次灌溉' }, options: { expectedVersion: plan.version } },
  })
  assert.equal(cancel.status, 200)
  const planAfter = await server.api(`/plans/${plan.planId}`, { cookie: admin.cookie })
  assert.equal(planAfter.payload.entity.status, 'CANCELLED')
  const runAfter = await server.api(`/runs/${run.runId}`, { cookie: admin.cookie })
  assert.equal(runAfter.payload.entity.status, 'STOPPED')
  const replay = await server.api('/commit', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    headers: { 'Idempotency-Key': key },
    body: { actionId: 'PLAN_CANCEL', payload: { planId: plan.planId, reason: '天气变化取消本次灌溉' }, options: { expectedVersion: plan.version } },
  })
  assert.equal(replay.payload.replayed, true)
})

test('资源检查是只读查询且不需要防跨站令牌', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  const server = await startServer(context)
  t.after(() => server.close())
  const admin = await server.login('zyq.admin', 'AdminPass123!')
  const plans = await server.api('/plans?status=DRAFT&pageSize=50', { cookie: admin.cookie })
  const plan = plans.payload.items[0]
  const detail = await server.api(`/plans/${plan.planId}`, { cookie: admin.cookie })
  const steps = detail.payload.related.PlanStep.filter((step) => step.planId === plan.planId).sort((a, b) => a.order - b.order)
  const assessment = await server.api('/query', {
    method: 'POST',
    cookie: admin.cookie,
    body: { name: 'resources', params: { ...plan, steps } },
  })
  assert.equal(assessment.status, 200)
  assert.equal(typeof assessment.payload.ok, 'boolean')
  assert.match(assessment.payload.conflictHash, /^resources-/)
})

test('真实CSV导出在后台完成并可下载校验摘要', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  const server = await startServer(context)
  t.after(() => server.close())
  const admin = await server.login('zyq.admin', 'AdminPass123!')
  const created = await server.api('/exports', {
    method: 'POST',
    cookie: admin.cookie,
    csrf: admin.csrf,
    body: { filters: { start: '2026-07-27', end: '2026-07-27' } },
  })
  assert.equal(created.status, 200)
  const exportId = created.payload.entityId
  let job = null
  for (let attempt = 0; attempt < 100; attempt++) {
    const detail = await server.api(`/exports/${exportId}`, { cookie: admin.cookie })
    job = detail.payload.entity
    if (job.status === 'READY' || job.status === 'FAILED') break
    await delay(20)
  }
  assert.equal(job.status, 'READY')
  assert.equal(job.rowCount, 1)
  assert.match(job.checksum, /^[0-9a-f]{64}$/)

  const file = await server.api(`/exports/${exportId}/file`, { cookie: admin.cookie })
  assert.equal(file.status, 200)
  const text = await file.headers.get('content-type')
  assert.match(text, /text\/csv/)
  const raw = Buffer.from(await (await fetch(`http://127.0.0.1:${server.server.address().port}/api/v1/exports/${exportId}/file`, { headers: { Cookie: admin.cookie } })).arrayBuffer())
  assert.equal(raw.subarray(0, 3).toString('hex'), 'efbbbf')
  const content = raw.toString('utf8')
  assert.match(content, /账本编号/)
  assert.match(content, /385\.7/)

  const preview = await server.api('/query', {
    method: 'POST',
    cookie: admin.cookie,
    body: { name: 'exportFile', params: { exportId } },
  })
  assert.equal(preview.status, 200)
  assert.equal(preview.payload.checksum, job.checksum)
})

test('会话 Cookie、防跨站校验、退出撤销和最后管理员保护', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  seedPassword(context.db, 'zyq.admin', 'AdminPass123!')
  const server = await startServer(context)
  t.after(() => server.close())
  const login = await server.api('/auth/login', { method: 'POST', body: { account: 'zyq.admin', password: 'AdminPass123!' } })
  assert.equal(login.status, 200)
  const rawCookie = login.headers.getSetCookie?.()[0] ?? login.headers.get('set-cookie')
  assert.match(rawCookie, /HttpOnly/)
  assert.match(rawCookie, /SameSite=Lax/)
  const cookie = rawCookie.split(';')[0]
  const csrf = login.payload.csrfToken

  const noCsrf = await server.api('/commit', {
    method: 'POST',
    cookie,
    body: { actionId: 'FIELD_UPDATE', payload: {}, options: {} },
  })
  assert.equal(noCsrf.status, 403)
  assert.equal(noCsrf.payload.code, 'CSRF_FAILED')

  const wrongCsrf = await server.api('/commit', {
    method: 'POST',
    cookie,
    csrf: 'not-the-token',
    body: { actionId: 'FIELD_UPDATE', payload: {}, options: {} },
  })
  assert.equal(wrongCsrf.status, 403)

  const selfDisable = await server.api(`/users/${login.payload.user.userId}/disable`, {
    method: 'POST',
    cookie,
    csrf,
    body: { reason: '测试停用当前账号本人', expectedVersion: login.payload.user.version },
  })
  assert.equal(selfDisable.status, 409)
  assert.equal(selfDisable.payload.code, 'CURRENT_USER')

  const logout = await server.api('/auth/logout', { method: 'POST', cookie, csrf })
  assert.equal(logout.status, 204)
  const after = await server.api('/snapshot', { cookie })
  assert.equal(after.status, 401)
})

test('未登录请求不泄露业务实体', async (t) => {
  const context = createTempBackend()
  t.after(() => context.cleanup())
  const server = await startServer(context)
  t.after(() => server.close())
  for (const path of ['/snapshot', '/fields', '/overview', '/water/report']) {
    const response = await server.api(path)
    assert.equal(response.status, 401, path)
  }
})
