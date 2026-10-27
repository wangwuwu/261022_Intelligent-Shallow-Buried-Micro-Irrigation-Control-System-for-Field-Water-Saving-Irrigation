import { primaryKeys } from '../../../frontend/src/data/contracts.js'

export const entityKinds = Object.freeze(Object.keys(primaryKeys).filter((kind) => kind !== 'Session'))

const common = (kind, row) => ({
  id: row[primaryKeys[kind]],
  farm_id: row.farmId ?? null,
  status: row.status ?? null,
  version: Number.isSafeInteger(row.version) ? row.version : 1,
  created_at: row.createdAt ?? null,
  updated_at: row.updatedAt ?? null,
})

export const entityTables = Object.freeze({
  Farm: {
    table: 'farms',
    extra: (row) => ({ name: row.name ?? null, region: row.region ?? null }),
  },
  User: {
    table: 'users',
    extra: (row) => ({ account: row.account ?? null, name: row.name ?? null, role: row.role ?? null, phone: row.phone ?? null }),
  },
  Field: {
    table: 'fields',
    extra: (row) => ({ code: row.code ?? null, name: row.name ?? null, area_mu: row.areaMu ?? null, soil_type: row.soilType ?? null, manager_id: row.managerId ?? null }),
  },
  CropSeason: {
    table: 'crop_seasons',
    extra: (row) => ({ field_id: row.fieldId ?? null, crop: row.crop ?? null, variety: row.variety ?? null, stage: row.stage ?? null, planting_date: row.plantingDate ?? null, harvest_date: row.harvestDate ?? null }),
  },
  PipeNode: {
    table: 'pipe_nodes',
    extra: (row) => ({ parent_node_id: row.parentNodeId ?? null, name: row.name ?? null, kind: row.kind ?? null, pump_device_id: row.pumpDeviceId ?? null, capacity_m3h: row.capacityM3h ?? null }),
  },
  IrrigationZone: {
    table: 'irrigation_zones',
    extra: (row) => ({ field_id: row.fieldId ?? null, source_node_id: row.sourceNodeId ?? null, valve_device_id: row.valveDeviceId ?? null, meter_point_id: row.meterPointId ?? null, name: row.name ?? null, area_mu: row.areaMu ?? null }),
  },
  Device: {
    table: 'devices',
    extra: (row) => ({ code: row.code ?? null, name: row.name ?? null, kind: row.kind ?? null, gateway_device_id: row.gatewayDeviceId ?? null, connection: row.connection ?? null, verification: row.verification ?? null, last_seen_at: row.lastSeenAt ?? null }),
  },
  Point: {
    table: 'points',
    extra: (row) => ({ device_id: row.deviceId ?? null, zone_id: row.zoneId ?? null, name: row.name ?? null, kind: row.kind ?? null, address: row.address ?? null, unit: row.unit ?? null, depth_cm: row.depthCm ?? null }),
  },
  TelemetryReading: {
    table: 'telemetry_readings',
    extra: (row) => ({ point_id: row.pointId ?? null, observed_at: row.observedAt ?? null, quality: row.quality ?? null, gateway_message_id: row.gatewayMessageId ?? null }),
  },
  Strategy: {
    table: 'strategies',
    extra: (row) => ({ name: row.name ?? null, crop: row.crop ?? null, stage: row.stage ?? null, trigger_mode: row.triggerMode ?? null }),
  },
  Plan: {
    table: 'plans',
    extra: (row) => ({ name: row.name ?? null, strategy_id: row.strategyId ?? null, scheduled_at: row.scheduledAt ?? null, created_by: row.createdBy ?? null, conflict_hash: row.conflictHash ?? null }),
  },
  PlanStep: {
    table: 'plan_steps',
    extra: (row) => ({ plan_id: row.planId ?? null, zone_id: row.zoneId ?? null, step_order: row.order ?? null, target_volume_m3: row.targetVolumeM3 ?? null }),
  },
  IrrigationRun: {
    table: 'irrigation_runs',
    extra: (row) => ({ plan_id: row.planId ?? null, requested_at: row.requestedAt ?? null, actual_started_at: row.actualStartedAt ?? null, actual_ended_at: row.actualEndedAt ?? null, active_step_id: row.activeStepId ?? null, last_command_id: row.lastCommandId ?? null }),
  },
  RunStep: {
    table: 'run_steps',
    extra: (row) => ({ run_id: row.runId ?? null, plan_step_id: row.planStepId ?? null, zone_id: row.zoneId ?? null, step_order: row.order ?? null, target_volume_m3: row.targetVolumeM3 ?? null, started_at: row.startedAt ?? null, ended_at: row.endedAt ?? null }),
  },
  CommandOutbox: {
    table: 'command_outbox',
    extra: (row) => ({ run_id: row.runId ?? null, actor_id: row.actorId ?? null, intent: row.intent ?? null, correlation_id: row.correlationId ?? null, idempotency_key: row.idempotencyKey ?? null, requested_at: row.requestedAt ?? null, ack_at: row.ackAt ?? null, confirmed_at: row.confirmedAt ?? null }),
  },
  CommandEvent: {
    table: 'command_events',
    extra: (row) => ({ command_id: row.commandId ?? null, device_id: row.deviceId ?? null, gateway_event_id: row.gatewayEventId ?? null, phase: row.phase ?? null, occurred_at: row.occurredAt ?? null }),
  },
  WaterLedger: {
    table: 'water_ledger',
    extra: (row) => ({ run_id: row.runId ?? null, run_step_id: row.runStepId ?? null, zone_id: row.zoneId ?? null, season_id: row.seasonId ?? null, ended_at: row.endedAt ?? null, volume_m3: row.volumeM3 ?? null, method: row.method ?? null, quality_status: row.qualityStatus ?? null, revision_of: row.revisionOf ?? null }),
  },
  Alarm: {
    table: 'alarms',
    extra: (row) => ({ device_id: row.deviceId ?? null, zone_id: row.zoneId ?? null, run_id: row.runId ?? null, kind: row.kind ?? null, severity: row.severity ?? null, recovery: row.recovery ?? null, opened_at: row.openedAt ?? null }),
  },
  WorkOrder: {
    table: 'work_orders',
    extra: (row) => ({ alarm_id: row.alarmId ?? null, zone_id: row.zoneId ?? null, device_id: row.deviceId ?? null, assignee_id: row.assigneeId ?? null, kind: row.kind ?? null, due_at: row.dueAt ?? null, started_at: row.startedAt ?? null, completed_at: row.completedAt ?? null }),
  },
  Calibration: {
    table: 'calibrations',
    extra: (row) => ({ point_id: row.pointId ?? null, actor_id: row.actorId ?? null, calibrated_at: row.calibratedAt ?? null, reference_value: row.referenceValue ?? null, measured_value: row.measuredValue ?? null }),
  },
  QrCode: {
    table: 'qr_codes',
    extra: (row) => ({ device_id: row.deviceId ?? null, field_id: row.fieldId ?? null, qr_payload: row.payload ?? null, checksum: row.checksum ?? null, issued_at: row.issuedAt ?? null }),
  },
  WaterBaseline: {
    table: 'water_baselines',
    extra: (row) => ({ field_id: row.fieldId ?? null, season_id: row.seasonId ?? null, reference_start: row.referenceStart ?? null, reference_end: row.referenceEnd ?? null, reference_area_mu: row.referenceAreaMu ?? null, reference_volume_m3: row.referenceVolumeM3 ?? null }),
  },
  ExportJob: {
    table: 'export_jobs',
    extra: (row) => ({ created_by: row.createdBy ?? null, file_name: row.fileName ?? null, checksum: row.checksum ?? null, expires_at: row.expiresAt ?? null, source_revision: row.sourceRevision ?? null }),
  },
  SystemPolicy: {
    table: 'system_policies',
    extra: () => ({}),
  },
  AuditLog: {
    table: 'audit_logs',
    extra: (row) => ({ actor_id: row.actorId ?? null, action_id: row.actionId ?? null, entity_type: row.entityType ?? null, entity_id: row.entityId ?? null, occurred_at: row.occurredAt ?? null, correlation_id: row.correlationId ?? null, result: row.result ?? null }),
  },
})

export const relationTables = Object.freeze({
  UserField: { table: 'user_fields', left: 'user_id', right: 'field_id', kind: 'User', field: 'fieldIds' },
  StrategyZone: { table: 'strategy_zones', left: 'strategy_id', right: 'zone_id', kind: 'Strategy', field: 'zoneIds' },
  ZoneSoilPoint: { table: 'zone_soil_points', left: 'zone_id', right: 'point_id', kind: 'IrrigationZone', field: 'soilPointIds' },
})

function index(kind, entities) {
  const key = primaryKeys[kind]
  return new Map((entities[kind] ?? []).map((row) => [row[key], row]))
}

export function resolveFarmId(kind, row, entities, indexes = {}) {
  if (row.farmId) return row.farmId
  const get = (target) => indexes[target] ?? (indexes[target] = index(target, entities))
  switch (kind) {
    case 'PlanStep': {
      const plan = get('Plan').get(row.planId)
      return plan?.farmId ?? null
    }
    case 'RunStep': {
      const run = get('IrrigationRun').get(row.runId)
      return run?.farmId ?? null
    }
    case 'CommandEvent': {
      const command = get('CommandOutbox').get(row.commandId)
      const run = command ? get('IrrigationRun').get(command.runId) : null
      return run?.farmId ?? null
    }
    case 'Calibration': {
      const point = get('Point').get(row.pointId)
      const device = point ? get('Device').get(point.deviceId) : null
      return device?.farmId ?? null
    }
    case 'QrCode': {
      const field = row.fieldId ? get('Field').get(row.fieldId) : null
      if (field) return field.farmId
      const device = row.deviceId ? get('Device').get(row.deviceId) : null
      return device?.farmId ?? null
    }
    case 'WaterLedger': {
      const zone = get('IrrigationZone').get(row.zoneId)
      return zone?.farmId ?? null
    }
    case 'WaterBaseline': {
      const field = get('Field').get(row.fieldId)
      return field?.farmId ?? null
    }
    default:
      return null
  }
}

export function entityRow(kind, row, entities, indexes) {
  const definition = entityTables[kind]
  if (!definition) throw new Error(`未知实体类型 ${kind}`)
  return {
    ...common(kind, row),
    farm_id: row.farmId ?? resolveFarmId(kind, row, entities, indexes),
    ...definition.extra(row),
  }
}

export function payloadOf(kind, row) {
  return JSON.stringify(row)
}

export function emptyEntities() {
  return Object.fromEntries(Object.keys(primaryKeys).map((kind) => [kind, []]))
}

export function normalizeEntities(raw = {}) {
  return Object.fromEntries(
    Object.keys(primaryKeys).map((kind) => [kind, Array.isArray(raw[kind]) ? raw[kind] : []]),
  )
}
