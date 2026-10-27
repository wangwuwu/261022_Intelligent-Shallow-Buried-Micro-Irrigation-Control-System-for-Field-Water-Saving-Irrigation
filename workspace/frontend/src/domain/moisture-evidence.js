const minutesOfDay = time => {
  if (typeof time !== 'string' || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return NaN
  const [hours, minutes] = time.split(':').map(Number)
  return hours * 60 + minutes
}

export function assessMoistureTrigger(index, strategy, now = new Date(), { representativePointByZone = {} } = {}) {
  const nowMs = new Date(now).getTime()
  const local = new Date(nowMs + 8 * 3600000)
  const currentMinute = local.getUTCHours() * 60 + local.getUTCMinutes()
  const allowedStart = minutesOfDay(strategy.allowedStart)
  const allowedEnd = minutesOfDay(strategy.allowedEnd)
  return (strategy.zoneIds ?? []).map(zoneId => {
    const result = { zoneId, eligible: false, targetVolumeM3: null, moistureEvidence: null }
    const reject = reason => ({ ...result, reason })
    const zone = index.byId.IrrigationZone.get(zoneId)
    if (strategy.status !== 'ENABLED') return reject('策略未启用')
    if (!zone || zone.status !== 'ENABLED' || zone.farmId !== strategy.farmId) return reject('目标分区不可用')
    const season = (index.seasonsByField.get(zone.fieldId) ?? []).find(row => row.status === 'ENABLED')
    if (!season || season.crop !== strategy.crop || season.stage !== strategy.stage) return reject('目标分区作物或生育阶段不匹配')
    if (!Number.isFinite(nowMs) || !Number.isFinite(allowedStart) || !Number.isFinite(allowedEnd) || allowedStart >= allowedEnd) return reject('执行时段无效')
    if (currentMinute < allowedStart || currentMinute >= allowedEnd) return reject('当前不在允许执行时段内')
    if (typeof strategy.targetVolumeM3 !== 'number' || !Number.isFinite(strategy.targetVolumeM3) || strategy.targetVolumeM3 <= 0 || typeof strategy.maxDurationMin !== 'number' || !Number.isFinite(strategy.maxDurationMin) || strategy.maxDurationMin <= 0) return reject('策略目标水量或最长时长无效')
    if (!['SCHEDULE', 'VOLUME', 'MOISTURE'].includes(strategy.triggerMode)) return reject('触发模式无效')
    if (strategy.triggerMode === 'MOISTURE') {
      if (typeof strategy.thresholdVwc !== 'number' || !Number.isFinite(strategy.thresholdVwc) || strategy.thresholdVwc < 0 || strategy.thresholdVwc > 100) return reject('墒情阈值无效')
      // Selecting a representative soil layer is an explicit business input.
      // Invalid evidence never falls back to another layer or older observation.
      const points = (zone.soilPointIds ?? []).map(pointId => index.byId.Point.get(pointId)).filter(point => point?.kind === 'SOIL_MOISTURE' && Number.isFinite(point.depthCm))
      const selectedPointId = representativePointByZone[zoneId]
      const point = selectedPointId ? points.find(candidate => candidate.pointId === selectedPointId) : points.length === 1 ? points[0] : null
      if (!point) return reject('代表点位未确定或不属于目标分区')
      const reading = index.readingsByPoint.get(point.pointId)?.at(-1)
      if (!reading) return reject('缺少墒情数据')
      const ageSec = (nowMs - Date.parse(reading.observedAt)) / 1000
      result.moistureEvidence = { pointId: point.pointId, readingId: reading.readingId, observedAt: reading.observedAt, quality: reading.quality, ageSec, measuredVwc: reading.value, correctedVwc: null }
      if (!Number.isFinite(ageSec) || ageSec < 0) return reject('墒情采集时间无效或晚于当前时间')
      if (!Number.isFinite(point.staleAfterSec) || point.staleAfterSec <= 0 || ageSec > point.staleAfterSec) return reject('墒情数据已过期')
      if (reading.quality !== 'VALID' || typeof reading.value !== 'number' || !Number.isFinite(reading.value)) return reject('墒情数据质量无效')
      const device = index.byId.Device.get(point.deviceId)
      if (!device || device.farmId !== zone.farmId || device.status !== 'ENABLED' || device.connection !== 'ONLINE') return reject('墒情设备不属于本农场、离线或已停用')
      const heartbeatAgeSec=(nowMs-Date.parse(device.lastSeenAt))/1000
      if(!Number.isFinite(heartbeatAgeSec)||heartbeatAgeSec<0||heartbeatAgeSec>(device.heartbeatTimeoutSec??120))return reject('墒情设备心跳已过期或通信时间无效')
      if (!Number.isFinite(point.scale) || !Number.isFinite(point.offset) || !Number.isFinite(point.rangeMin) || !Number.isFinite(point.rangeMax) || point.rangeMin >= point.rangeMax) return reject('墒情点位量程或校准参数无效')
      const correctedVwc = reading.value * point.scale + point.offset
      result.moistureEvidence.correctedVwc = correctedVwc
      if (!Number.isFinite(correctedVwc) || correctedVwc < point.rangeMin || correctedVwc > point.rangeMax) return reject('墒情数据超出量程')
      if (correctedVwc >= strategy.thresholdVwc) return reject('墒情尚未低于触发阈值')
    }
    return { ...result, eligible: true, reason: '满足策略条件，待人工确认', targetVolumeM3: strategy.targetVolumeM3 }
  })
}
