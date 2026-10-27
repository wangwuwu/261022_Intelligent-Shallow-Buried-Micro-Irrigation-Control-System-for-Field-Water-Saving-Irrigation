import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildIrrigationIndex, effectiveWaterLedger, projectWaterAccounting, assessRotationResources, validateFieldFacts, assessMoistureTrigger } from '../src/domain/irrigation.js'

const initial = JSON.parse(readFileSync(new URL('../../shared_context.json', import.meta.url))).entities
const clone = () => structuredClone(initial)

// These inputs explicitly select a configured layer; production never infers one.
const assessSelectedMoisture = (index, strategy, now) => assessMoistureTrigger(index, strategy, now, {
  representativePointByZone: Object.fromEntries(strategy.zoneIds.map(zoneId => [zoneId, index.byId.IrrigationZone.get(zoneId)?.soilPointIds[0]])),
})

test('all report totals and field area come from the same effective ledger', () => {
  const report = projectWaterAccounting(buildIrrigationIndex(clone()), { start: '2026-06-01', end: '2026-07-28' })
  assert.equal(report.totalM3, 4963.5)
  assert.equal(report.measuredM3, 4928.9)
  assert.equal(report.allocatedM3, 34.6)
  assert.equal(report.coveredAreaMu, 555)
  assert.equal(report.perMuM3, 8.94)
  assert.equal(report.rows.length, 30)
  assert.equal(report.baseline.savingPercent, 16.52)
  assert.equal(report.farmSavingPercent, null)
})

test('a revised ledger replaces its predecessor and never duplicates field area', () => {
  const entities = clone()
  const original = entities.WaterLedger[0]
  entities.WaterLedger.push({ ...original, ledgerId: 'WTR-REVISION', revisionOf: original.ledgerId, volumeM3: 400 })
  assert.equal(effectiveWaterLedger(entities.WaterLedger).length, 30)
  const report = projectWaterAccounting(buildIrrigationIndex(entities), {})
  assert.equal(report.totalM3, 4977.8)
  assert.equal(report.coveredAreaMu, 555)
  entities.WaterBaseline[0].referenceVolumeM3 = 0
  assert.equal(projectWaterAccounting(buildIrrigationIndex(entities), {}).baseline.savingPercent, null)
})

test('field area cannot shrink below its enabled irrigation zones', () => {
  const index = buildIrrigationIndex(clone())
  assert.match(validateFieldFacts(index, { ...initial.Field[0], areaMu: 30 }).areaMu, /分区/)
  assert.deepEqual(validateFieldFacts(index, initial.Field[0]), {})
})

test('rotation reservations distinguish adjacent intervals from overlapping capacity', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const zone = entities.IrrigationZone[0]
  const draft = { scheduledAt: '2026-07-29T06:00:00+08:00', steps: [{ zoneId: zone.zoneId, targetVolumeM3: 10, expectedFlowM3h: 55, maxDurationMin: 45 }] }
  let result = assessRotationResources(buildIrrigationIndex(entities), draft)
  assert.equal(result.ok, true)
  entities.Plan.push({ planId: 'PLN-OCCUPIED', scheduledAt: draft.scheduledAt, status: 'PUBLISHED' })
  entities.PlanStep.push({ planStepId: 'PST-OCCUPIED', planId: 'PLN-OCCUPIED', zoneId: entities.IrrigationZone[1].zoneId, order: 1, targetVolumeM3: 10, expectedFlowM3h: 45, maxDurationMin: 45 })
  result = assessRotationResources(buildIrrigationIndex(entities), draft)
  assert.equal(result.ok, false)
  assert.ok(result.conflicts.some(conflict => conflict.code === 'SOURCE_CAPACITY'))
  draft.scheduledAt = '2026-07-29T07:00:00+08:00'
  assert.equal(assessRotationResources(buildIrrigationIndex(entities), draft).ok, true)
})

test('duplicate zones and impossible duration cannot pass resource assessment', () => {
  const step = { zoneId: initial.IrrigationZone[0].zoneId, targetVolumeM3: 100, expectedFlowM3h: 55, maxDurationMin: 10 }
  const result = assessRotationResources(buildIrrigationIndex(clone()), { scheduledAt: '2026-07-29T07:00:00+08:00', steps: [step, step] })
  assert.equal(result.ok, false)
  assert.ok(result.conflicts.some(conflict => conflict.code === 'DUPLICATE_ZONE'))
  assert.ok(result.conflicts.some(conflict => conflict.code === 'DURATION_LIMIT'))
})

test('expired soil evidence cannot recommend an irrigation operation', () => {
  const index = buildIrrigationIndex(clone())
  const strategy = initial.Strategy[0]
  const current = assessSelectedMoisture(index, strategy, new Date('2026-07-28T10:18:43+08:00'))
  assert.equal(current[0].eligible, true)
  const expired = assessSelectedMoisture(index, strategy, new Date('2026-10-26T10:18:43+08:00'))
  assert.equal(expired[0].eligible, false)
  assert.match(expired[0].reason, /过期/)
})

test('empty water reports keep unknown averages and comparisons null', () => {
  const entities = clone()
  entities.WaterLedger = []
  const report = projectWaterAccounting(buildIrrigationIndex(entities), {})
  assert.equal(report.totalM3, 0)
  assert.equal(report.coveredAreaMu, 0)
  assert.equal(report.perMuM3, null)
  assert.equal(report.farmSavingPercent, null)
})

test('non-final corrections retain the previous final water evidence', () => {
  const entities = clone()
  const original = entities.WaterLedger[0]
  entities.WaterLedger.push({ ...original, ledgerId: crypto.randomUUID(), revisionOf: original.ledgerId, qualityStatus: 'PENDING' })
  assert.ok(effectiveWaterLedger(entities.WaterLedger).some(row => row.ledgerId === original.ledgerId))
  assert.equal(effectiveWaterLedger(entities.WaterLedger).length, initial.WaterLedger.length)
})

test('water filters use Shanghai settlement dates and include the entire end day', () => {
  const entities = clone()
  entities.WaterLedger = [entities.WaterLedger[0]]
  const row = entities.WaterLedger[0]
  const day = row.endedAt.slice(0, 10)
  row.endedAt = `${day}T23:59:59+08:00`
  const index = buildIrrigationIndex(entities)
  assert.equal(projectWaterAccounting(index, { start: day, end: day }).totalM3, row.volumeM3)
  assert.equal(projectWaterAccounting(index, { fieldId: entities.Field[0].fieldId }).rows.length, 0)
  row.endedAt = new Date(Date.parse(`${day}T00:00:00+08:00`) + 86400000).toISOString()
  assert.equal(projectWaterAccounting(index, { start: day, end: day }).totalM3, 0)
})

test('malformed water values and orphan relations are rejected instead of counted as zero', () => {
  const entities = clone()
  entities.WaterLedger[0].volumeM3 = null
  assert.throws(() => projectWaterAccounting(buildIrrigationIndex(entities), {}), /水量/)
  entities.WaterLedger[0].volumeM3 = initial.WaterLedger[0].volumeM3
  entities.WaterLedger[0].zoneId = null
  assert.throws(() => projectWaterAccounting(buildIrrigationIndex(entities), {}), /分区/)
})

test('relation indexes keep readings ordered by observation rather than arrival', () => {
  const entities = clone()
  entities.TelemetryReading.reverse()
  const index = buildIrrigationIndex(entities)
  const pointId = entities.Point[0].pointId
  const readings = index.readingsByPoint.get(pointId)
  assert.ok(readings.length)
  assert.deepEqual(readings.map(row => Date.parse(row.observedAt)), readings.map(row => Date.parse(row.observedAt)).sort((a, b) => a - b))
})

test('rotation event boundaries release capacity before admitting the next reservation', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const [zone, otherZone] = entities.IrrigationZone
  const scheduledAt = initial.Plan[0].scheduledAt
  const step = { zoneId: zone.zoneId, targetVolumeM3: zone.designFlowM3h, expectedFlowM3h: zone.designFlowM3h, maxDurationMin: 60 }
  const nextAt = new Date(Date.parse(scheduledAt) + 3600000).toISOString()
  entities.Plan.push({ ...initial.Plan[0], scheduledAt, status: 'PUBLISHED' })
  entities.PlanStep.push({ ...initial.PlanStep[0], ...step, zoneId: otherZone.zoneId, expectedFlowM3h: otherZone.designFlowM3h, targetVolumeM3: otherZone.designFlowM3h })
  const index = buildIrrigationIndex(entities)
  assert.equal(assessRotationResources(index, { scheduledAt: nextAt, steps: [step] }).ok, true)
  assert.equal(assessRotationResources(index, { scheduledAt, steps: [step] }).ok, false)
})

test('disabled zones, offline valves, invalid numbers and cyclic supplies block planning', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const zone = entities.IrrigationZone[0]
  const draft = { scheduledAt: initial.Plan[0].scheduledAt, steps: [{ zoneId: zone.zoneId, targetVolumeM3: 1, expectedFlowM3h: 1, maxDurationMin: 60 }] }
  zone.status = 'DISABLED'
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'ZONE_UNAVAILABLE'))
  zone.status = 'ENABLED'
  entities.Device.find(row => row.deviceId === zone.valveDeviceId).connection = 'OFFLINE'
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'DEVICE_UNAVAILABLE'))
  draft.steps[0].targetVolumeM3 = null
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'STEP_QUANTITY'))
  entities.PipeNode.find(row => row.nodeId === zone.sourceNodeId).parentNodeId = zone.sourceNodeId
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'SUPPLY_CYCLE'))
})

test('own saved reservation is excluded when checking an edit, but other plans still reserve', () => {
  const entities = clone()
  entities.Plan = [entities.Plan[0]]
  entities.PlanStep = entities.PlanStep.filter(row => row.planId === entities.Plan[0].planId)
  const plan = entities.Plan[0]
  const draft = { ...plan, steps: entities.PlanStep }
  assert.equal(assessRotationResources(buildIrrigationIndex(entities), draft).ok, true)
})

test('invalid schedule and an empty rotation never pass assessment', () => {
  const index = buildIrrigationIndex(clone())
  assert.equal(assessRotationResources(index, { scheduledAt: '', steps: [] }).ok, false)
})

test('field validation reports invalid coordinates, duplicate codes and disabled managers', () => {
  const entities = clone()
  const field = { ...entities.Field[0], name: ' ', code: entities.Field[1].code, areaMu: null, location: [181, -91] }
  entities.User.find(row => row.userId === field.managerId).status = 'DISABLED'
  const errors = validateFieldFacts(buildIrrigationIndex(entities), field)
  for (const key of ['name', 'code', 'areaMu', 'location', 'managerId']) assert.ok(errors[key], key)
})

test('invalid latest moisture evidence cannot fall back to an older valid reading', () => {
  const entities = clone()
  const strategy = entities.Strategy[0]
  const zone = entities.IrrigationZone.find(row => row.zoneId === strategy.zoneIds[0])
  const point = entities.Point.find(row => row.pointId === zone.soilPointIds[0])
  const latest = entities.TelemetryReading.filter(row => row.pointId === point.pointId).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0]
  latest.quality = 'INVALID'
  const result = assessSelectedMoisture(buildIrrigationIndex(entities), strategy, new Date(latest.observedAt))
  assert.equal(result[0].eligible, false)
  assert.match(result[0].reason, /质量/)
})

test('moisture threshold equality, future evidence and disabled strategy do not trigger', () => {
  const entities = clone()
  const strategy = entities.Strategy[0]
  const point = entities.Point.find(row => row.pointId === entities.IrrigationZone[0].soilPointIds[0])
  const readings = entities.TelemetryReading.filter(row => row.pointId === point.pointId).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))
  const latest = readings[0]
  latest.value = strategy.thresholdVwc
  assert.equal(assessSelectedMoisture(buildIrrigationIndex(entities), strategy, new Date(latest.observedAt))[0].eligible, false)
  latest.value = strategy.thresholdVwc - 1
  assert.equal(assessSelectedMoisture(buildIrrigationIndex(entities), strategy, new Date(Date.parse(latest.observedAt) - 1))[0].eligible, false)
  strategy.status = 'DISABLED'
  assert.equal(assessSelectedMoisture(buildIrrigationIndex(entities), strategy, new Date(latest.observedAt))[0].eligible, false)
})

test('baseline comparison scales reference water to the comparable field area', () => {
  const entities = clone()
  const reference = entities.WaterBaseline[0]
  const filters = { fieldId: reference.fieldId, seasonId: reference.seasonId, start: reference.referenceStart, end: reference.referenceEnd }
  const report = projectWaterAccounting(buildIrrigationIndex(entities), filters)
  const expected = Number(((reference.referenceVolumeM3 - report.totalM3) / reference.referenceVolumeM3 * 100).toFixed(2))
  assert.equal(report.farmSavingPercent, expected)
  reference.referenceAreaMu += 1
  const comparableReference = reference.referenceVolumeM3 / reference.referenceAreaMu * report.coveredAreaMu
  assert.equal(projectWaterAccounting(buildIrrigationIndex(entities), filters).farmSavingPercent, Number(((comparableReference-report.totalM3)/comparableReference*100).toFixed(2)))
  reference.referenceAreaMu -= 1
  entities.WaterBaseline.push({ ...reference, baselineId: crypto.randomUUID() })
  assert.equal(projectWaterAccounting(buildIrrigationIndex(entities), filters).farmSavingPercent, null)
})

test('ancestor supply limits and concurrency limits both participate in resource assessment', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const [zone, otherZone] = entities.IrrigationZone
  const main = entities.PipeNode.find(row => row.nodeId === zone.sourceNodeId)
  const ancestor = entities.PipeNode.find(row => row.nodeId === main.parentNodeId)
  const draft = { scheduledAt: initial.Plan[0].scheduledAt, steps: [{ zoneId: zone.zoneId, targetVolumeM3: 1, expectedFlowM3h: zone.designFlowM3h, maxDurationMin: 60 }] }
  main.capacityM3h = zone.designFlowM3h + otherZone.designFlowM3h
  ancestor.capacityM3h = zone.designFlowM3h / 2
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'SOURCE_CAPACITY' && row.nodeId === ancestor.nodeId))
  ancestor.capacityM3h = main.capacityM3h
  main.maxConcurrentZones = 1
  entities.Plan.push({ ...initial.Plan[0], status: 'PUBLISHED', scheduledAt: draft.scheduledAt })
  entities.PlanStep.push({ ...initial.PlanStep[0], zoneId: otherZone.zoneId, targetVolumeM3: 1, expectedFlowM3h: otherZone.designFlowM3h, maxDurationMin: 60 })
  assert.ok(assessRotationResources(buildIrrigationIndex(entities), draft).conflicts.some(row => row.code === 'SOURCE_CONCURRENCY'))
})

test('resource checks reject valve sharing even when water capacity would allow it', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const [zone, otherZone] = entities.IrrigationZone
  otherZone.valveDeviceId = zone.valveDeviceId
  const scheduledAt = initial.Plan[0].scheduledAt
  const step = { zoneId: zone.zoneId, targetVolumeM3: 1, expectedFlowM3h: 1, maxDurationMin: 60 }
  entities.Plan.push({ ...initial.Plan[0], scheduledAt, status: 'PUBLISHED' })
  entities.PlanStep.push({ ...initial.PlanStep[0], ...step, zoneId: otherZone.zoneId })
  const result = assessRotationResources(buildIrrigationIndex(entities), { scheduledAt, steps: [step] })
  assert.ok(result.conflicts.some(row => row.code === 'VALVE_OCCUPIED'))
})

test('domain evaluation leaves original entity arrays and records unchanged', () => {
  const entities = clone()
  const before = structuredClone(entities)
  const index = buildIrrigationIndex(entities)
  projectWaterAccounting(index, {})
  assessRotationResources(index, { scheduledAt: entities.Plan[0].scheduledAt, steps: entities.PlanStep.filter(row => row.planId === entities.Plan[0].planId) })
  assessSelectedMoisture(index, entities.Strategy[0], new Date(entities.TelemetryReading[0].observedAt))
  validateFieldFacts(index, entities.Field[0])
  assert.deepEqual(entities, before)
})

test('decimal water quantities do not round an exact twenty-minute reservation up', () => {
  const entities = clone()
  entities.Plan = []
  entities.PlanStep = []
  const draft = { scheduledAt: initial.Plan[0].scheduledAt, steps: [{ zoneId: entities.IrrigationZone[0].zoneId, targetVolumeM3: 0.1, expectedFlowM3h: 0.3, maxDurationMin: 20 }] }
  const result = assessRotationResources(buildIrrigationIndex(entities), draft)
  assert.equal(result.ok, true)
  assert.equal(result.reservations[0].endsAt - result.reservations[0].startsAt, 20 * 60000)
})

test('malformed rotation step collections return business conflicts rather than throwing', () => {
  const index = buildIrrigationIndex(clone())
  for (const steps of [{}, '', null, [null]]) {
    const result = assessRotationResources(index, { scheduledAt: initial.Plan[0].scheduledAt, steps })
    assert.equal(result.ok, false)
  }
})

test('a zone-filtered subset cannot be compared with an entire field water baseline', () => {
  const entities = clone()
  const ledger = entities.WaterLedger[0]
  const zone = entities.IrrigationZone.find(row => row.zoneId === ledger.zoneId)
  const field = entities.Field.find(row => row.fieldId === zone.fieldId)
  const day = ledger.endedAt.slice(0, 10)
  Object.assign(entities.WaterBaseline[0], { fieldId: field.fieldId, seasonId: ledger.seasonId, referenceAreaMu: field.areaMu, referenceStart: day, referenceEnd: day })
  const report = projectWaterAccounting(buildIrrigationIndex(entities), { zoneId: zone.zoneId, start: day, end: day })
  assert.equal(report.baseline.comparable, false)
  assert.equal(report.farmSavingPercent, null)
})

test('soil evidence belonging to another farm cannot trigger a strategy', () => {
  const entities = clone()
  const point = entities.Point.find(row => row.pointId === entities.IrrigationZone[0].soilPointIds[0])
  entities.Device.find(row => row.deviceId === point.deviceId).farmId = crypto.randomUUID()
  const latest = entities.TelemetryReading.filter(row => row.pointId === point.pointId).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0]
  assert.equal(assessSelectedMoisture(buildIrrigationIndex(entities), entities.Strategy[0], new Date(latest.observedAt))[0].eligible, false)
})

test('unrelated historical reservations do not block a future rotation', () => {
  const entities = clone()
  const occupiedPlan = entities.Plan[0]
  entities.Plan = [{ ...occupiedPlan, status: 'PUBLISHED' }]
  entities.PlanStep = entities.PlanStep.filter(row => row.planId === occupiedPlan.planId)
  const occupiedZone = entities.IrrigationZone.find(row => row.zoneId === entities.PlanStep[0].zoneId)
  const availableZone = entities.IrrigationZone.find(row => row.sourceNodeId !== occupiedZone.sourceNodeId && row.status === 'ENABLED')
  occupiedZone.status = 'DISABLED'
  const draft = { scheduledAt: new Date(Date.parse(occupiedPlan.scheduledAt) + 365 * 86400000).toISOString(), steps: [{ zoneId: availableZone.zoneId, targetVolumeM3: 1, expectedFlowM3h: 1, maxDurationMin: 60 }] }
  assert.equal(assessRotationResources(buildIrrigationIndex(entities), draft).ok, true)
})

test('multiple soil layers require an explicit representative point before recommending water', () => {
  const index = buildIrrigationIndex(clone())
  const strategy = index.entities.Strategy[0]
  const now = new Date(index.entities.TelemetryReading[0].observedAt)
  const result = assessMoistureTrigger(index, strategy, now)
  assert.equal(result[0].eligible, false)
  assert.match(result[0].reason, /代表点位/)
  const wrongPoint = index.entities.Point.find(point => !index.byId.IrrigationZone.get(strategy.zoneIds[0]).soilPointIds.includes(point.pointId))
  const selected = assessMoistureTrigger(index, strategy, now, { representativePointByZone: { [strategy.zoneIds[0]]: wrongPoint.pointId } })
  assert.equal(selected[0].eligible, false)
  assert.match(selected[0].reason, /代表点位/)
})
