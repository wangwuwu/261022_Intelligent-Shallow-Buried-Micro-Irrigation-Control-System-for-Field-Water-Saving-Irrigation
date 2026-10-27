const reservingStatuses = new Set(['PUBLISHED', 'EXECUTING', 'QUEUED', 'STARTING', 'RUNNING', 'PAUSING', 'PAUSED', 'RESUMING', 'STOPPING', 'UNKNOWN'])
const positive = number => typeof number === 'number' && Number.isFinite(number) && number > 0
const reservationMinutes = step => {
  const exactDurationMin = step.targetVolumeM3 / step.expectedFlowM3h * 60
  // Binary arithmetic noise must not create an extra occupied minute.
  return Math.max(1, Math.ceil(exactDurationMin - Number.EPSILON * Math.abs(exactDurationMin) * 4))
}

export function assessRotationResources(index, rotationDraft, { includeActualRuns = false, now, maxScheduleDays } = {}) {
  const conflicts = []
  const reservations = []
  const addConflict = (code, reason, details = {}) => conflicts.push({ code, reason, ...details })
  const scheduledAt = Date.parse(rotationDraft.scheduledAt)
  if (now && maxScheduleDays && scheduledAt > Date.parse(now) + maxScheduleDays * 86400000) addConflict('SCHEDULE_HORIZON', '计划时间超过最长编排天数')
  if (!Number.isFinite(scheduledAt)) addConflict('SCHEDULE_INVALID', '计划执行时间无效')
  if (!Array.isArray(rotationDraft.steps) || !rotationDraft.steps.length) addConflict('STEPS_REQUIRED', '至少添加一个轮灌分区')

  function supplyPath(zone, candidate) {
    const path = []
    const visited = new Set()
    let nodeId = zone.sourceNodeId
    while (nodeId) {
      if (visited.has(nodeId)) {
        addConflict('SUPPLY_CYCLE', '供水管网父级存在循环', { zoneId: zone.zoneId, nodeId })
        return []
      }
      visited.add(nodeId)
      const node = index.byId.PipeNode.get(nodeId)
      if (!node || node.status !== 'ENABLED' || node.farmId !== zone.farmId || !positive(node.capacityM3h) || !Number.isInteger(node.maxConcurrentZones) || node.maxConcurrentZones < 1) {
        addConflict('SUPPLY_UNAVAILABLE', '供水节点缺失、停用或供水约束无效', { zoneId: zone.zoneId, nodeId })
        return []
      }
      if (candidate && node.pumpDeviceId) assessDevice(node.pumpDeviceId, zone)
      path.push(node)
      nodeId = node.parentNodeId
    }
    if (!path.length) addConflict('SUPPLY_UNAVAILABLE', '分区缺少供水节点', { zoneId: zone.zoneId })
    return path
  }

  function assessDevice(deviceId, zone) {
    const device = index.byId.Device.get(deviceId)
    const heartbeatAgeSec = device && now ? (Date.parse(now) - Date.parse(device.lastSeenAt)) / 1000 : null
    const heartbeatInvalid = now && (!Number.isFinite(heartbeatAgeSec) || heartbeatAgeSec < 0 || heartbeatAgeSec > (device?.heartbeatTimeoutSec ?? 120))
    if (!device || device.farmId !== zone.farmId || device.status !== 'ENABLED' || device.connection !== 'ONLINE' || heartbeatInvalid || device.verification !== 'VERIFIED' || !device.capabilities?.control || !device.capabilities?.feedback) {
      addConflict('DEVICE_UNAVAILABLE', '泵阀设备离线、未核验或缺少控制反馈能力', { zoneId: zone.zoneId, deviceId })
    }
  }

  function reserveSteps(plan, steps, candidate) {
    let startsAt = Date.parse(plan.scheduledAt)
    const seenZones = new Set()
    for (const [position, step] of steps.entries()) {
      if (!step || typeof step !== 'object') {
        addConflict('STEP_INVALID', '轮灌步骤格式无效', { position })
        continue
      }
      const zone = index.byId.IrrigationZone.get(step.zoneId)
      if (candidate && seenZones.has(step.zoneId)) addConflict('DUPLICATE_ZONE', '轮灌分区不能重复', { zoneId: step.zoneId })
      seenZones.add(step.zoneId)
      if (!zone || zone.status !== 'ENABLED' || (plan.farmId && plan.farmId !== zone.farmId)) {
        addConflict('ZONE_UNAVAILABLE', '分区不存在、已停用或不属于计划农场', { zoneId: step.zoneId })
        continue
      }
      const path = supplyPath(zone, candidate)
      if (candidate) assessDevice(zone.valveDeviceId, zone)
      if (![step.targetVolumeM3, step.expectedFlowM3h, step.maxDurationMin].every(positive)) {
        addConflict('STEP_QUANTITY', '目标水量、预计流量和最长时长必须为正数', { zoneId: step.zoneId })
        continue
      }
      const durationMin = reservationMinutes(step)
      if (!Number.isSafeInteger(durationMin) || durationMin > step.maxDurationMin) addConflict('DURATION_LIMIT', '最长时长内无法灌足目标水量', { zoneId: step.zoneId, durationMin })
      const endsAt = startsAt + durationMin * 60000
      if (!Number.isFinite(startsAt) || !Number.isFinite(endsAt) || !Number.isFinite(new Date(endsAt).getTime())) {
        addConflict('SCHEDULE_INVALID', '轮灌占用区间无效', { zoneId: step.zoneId })
        continue
      }
      reservations.push({ planId: plan.planId ?? null, planStepId: step.planStepId ?? null, position, zoneId: zone.zoneId,
        valveDeviceId: zone.valveDeviceId, nodeIds: path.map(node => node.nodeId), startsAt, endsAt, flowM3h: step.expectedFlowM3h, candidate })
      startsAt = endsAt
    }
  }

  reserveSteps(rotationDraft, Array.isArray(rotationDraft.steps) ? rotationDraft.steps : [], true)
  const candidateFrom = reservations.reduce((earliest, reservation) => Math.min(earliest, reservation.startsAt), Infinity)
  const candidateUntil = reservations.reduce((latest, reservation) => Math.max(latest, reservation.endsAt), -Infinity)
  const candidateNodes = new Set(reservations.flatMap(reservation => reservation.nodeIds))
  const candidateZones = new Set(reservations.map(reservation => reservation.zoneId))
  const candidateValves = new Set(reservations.map(reservation => reservation.valveDeviceId))
  function sharesCandidateSupply(step) {
    if (candidateZones.has(step.zoneId)) return true
    const zone = index.byId.IrrigationZone.get(step.zoneId)
    if (!zone) return false
    if (candidateValves.has(zone.valveDeviceId)) return true
    let nodeId = zone.sourceNodeId
    const visited = new Set()
    while (nodeId && !visited.has(nodeId)) {
      if (candidateNodes.has(nodeId)) return true
      visited.add(nodeId)
      nodeId = index.byId.PipeNode.get(nodeId)?.parentNodeId
    }
    return false
  }
  for (const plan of index.entities.Plan ?? []) {
    if (plan.planId === rotationDraft.planId || !reservingStatuses.has(plan.status)) continue
    const steps = index.stepsByPlan.get(plan.planId) ?? []
    if (!steps.some(sharesCandidateSupply)) continue
    const start = Date.parse(plan.scheduledAt)
    const durationMin = steps.reduce((sum, step) => positive(step.targetVolumeM3) && positive(step.expectedFlowM3h) ? sum + reservationMinutes(step) : Infinity, 0)
    if (start >= candidateUntil || start + durationMin * 60000 <= candidateFrom) continue
    reserveSteps(plan, steps, false)
  }

  if (includeActualRuns) for (const run of index.entities.IrrigationRun ?? []) {
    if (!reservingStatuses.has(run.status) || run.status === 'QUEUED' || run.planId === rotationDraft.planId) continue
    for (const step of index.stepsByRun.get(run.runId) ?? []) {
      if (!['STARTING','RUNNING','PAUSED','FINISHING','UNKNOWN'].includes(step.status) || step.endedAt) continue
      const zone = index.byId.IrrigationZone.get(step.zoneId)
      if (!zone || !sharesCandidateSupply(step)) continue
      const start = Date.parse(step.startedAt || run.actualStartedAt || run.requestedAt)
      if (!Number.isFinite(start) || start >= candidateUntil) continue
      const path = supplyPath(zone, false)
      reservations.push({ planId: run.planId, runId: run.runId, zoneId: zone.zoneId, valveDeviceId: zone.valveDeviceId,
        nodeIds: path.map(node=>node.nodeId), startsAt:start, endsAt:Math.max(candidateUntil, start+1), flowM3h:zone.designFlowM3h, candidate:false })
    }
  }

  const resourceEvents = new Map()
  for (const reservation of reservations) {
    const resourceKeys = [...reservation.nodeIds.map(nodeId => `node:${nodeId}`), `zone:${reservation.zoneId}`, `valve:${reservation.valveDeviceId}`]
    for (const resourceKey of resourceKeys) {
      const events = resourceEvents.get(resourceKey) ?? []
      events.push({ at: reservation.startsAt, enter: true, reservation }, { at: reservation.endsAt, enter: false, reservation })
      resourceEvents.set(resourceKey, events)
    }
  }
  for (const [resourceKey, events] of resourceEvents) {
    events.sort((a, b) => a.at - b.at || Number(a.enter) - Number(b.enter))
    const active = new Set()
    let flowM3h = 0
    let candidateCount = 0
    for (let position = 0; position < events.length;) {
      const at = events[position].at
      while (position < events.length && events[position].at === at) {
        const event = events[position++]
        if (event.enter) {
          active.add(event.reservation)
          flowM3h += event.reservation.flowM3h
          if (event.reservation.candidate) candidateCount++
        } else {
          active.delete(event.reservation)
          flowM3h -= event.reservation.flowM3h
          if (event.reservation.candidate) candidateCount--
        }
      }
      if (position === events.length || candidateCount === 0) continue
      const conflictDetails = () => ({ resourceKey, startsAt: at, endsAt: events[position].at, zoneIds: [...active].map(reservation => reservation.zoneId), planIds: [...new Set([...active].map(reservation => reservation.planId))] })
      if (resourceKey.startsWith('node:')) {
        const nodeId = resourceKey.slice(5)
        const node = index.byId.PipeNode.get(nodeId)
        if (flowM3h > node.capacityM3h + 1e-8) addConflict('SOURCE_CAPACITY', '供水节点流量容量不足', { ...conflictDetails(), nodeId, flowM3h, capacityM3h: node.capacityM3h })
        if (active.size > node.maxConcurrentZones) addConflict('SOURCE_CONCURRENCY', '供水节点同时运行分区超限', { ...conflictDetails(), nodeId, maxConcurrentZones: node.maxConcurrentZones })
      } else if (active.size > 1) {
        addConflict(resourceKey.startsWith('zone:') ? 'ZONE_OCCUPIED' : 'VALVE_OCCUPIED', '分区或阀门已被其他计划占用', conflictDetails())
      }
    }
  }
  return { ok: conflicts.length === 0, conflicts, reservations: reservations.filter(reservation => reservation.candidate), revision: index.revision }
}
