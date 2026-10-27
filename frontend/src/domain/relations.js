const primaryKeys = {
  User: 'userId', Farm: 'farmId', Field: 'fieldId', CropSeason: 'seasonId',
  PipeNode: 'nodeId', IrrigationZone: 'zoneId', Device: 'deviceId', Point: 'pointId',
  TelemetryReading: 'readingId', Strategy: 'strategyId', Plan: 'planId',
  PlanStep: 'planStepId', IrrigationRun: 'runId', RunStep: 'runStepId',
  WaterLedger: 'ledgerId', WaterBaseline: 'baselineId', SystemPolicy: 'policyId',
  Alarm: 'alarmId', WorkOrder: 'workOrderId', Calibration: 'calibrationId', ExportJob: 'exportId', AuditLog:'auditId', CommandOutbox:'commandId', CommandEvent:'eventId',
}

function groupBy(rows, key, compare) {
  const groups = new Map()
  for (const row of rows ?? []) {
    const group = groups.get(row[key]) ?? []
    group.push(row)
    groups.set(row[key], group)
  }
  if (compare) for (const group of groups.values()) group.sort(compare)
  return groups
}

// A repository revision owns its index. Never reorder the source entity arrays.
export function buildIrrigationIndex(entities, revision = 0) {
  const byId = {}
  for (const [kind, key] of Object.entries(primaryKeys)) {
    byId[kind] = new Map()
    for (const row of entities[kind] ?? []) {
      if (!row[key] || byId[kind].has(row[key])) throw new Error(`${kind} 主键缺失或重复`)
      byId[kind].set(row[key], row)
    }
  }
  return {
    entities, revision, byId,
    zonesByField: groupBy(entities.IrrigationZone, 'fieldId'),
    seasonsByField: groupBy(entities.CropSeason, 'fieldId'),
    pointsByDevice: groupBy(entities.Point, 'deviceId'),
    readingsByPoint: groupBy(entities.TelemetryReading, 'pointId', (a, b) => Date.parse(a.observedAt) - Date.parse(b.observedAt)),
    stepsByPlan: groupBy(entities.PlanStep, 'planId', (a, b) => a.order - b.order),
    stepsByRun: groupBy(entities.RunStep, 'runId', (a, b) => a.order - b.order),
    ledgerByRun: groupBy(entities.WaterLedger, 'runId'),
  }
}
