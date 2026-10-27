const DAY_MS = 86400000
const round = (number, digits = 2) => Number(number.toFixed(digits))

function dayBoundary(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error('统计日期格式无效')
  const timestamp = Date.parse(`${day}T00:00:00+08:00`)
  if (!Number.isFinite(timestamp) || new Date(timestamp + 8 * 3600000).toISOString().slice(0, 10) !== day) throw new Error('统计日期无效')
  return timestamp
}

function dateWindow({ start, end }) {
  const from = start ? dayBoundary(start) : -Infinity
  const until = end ? dayBoundary(end) + DAY_MS : Infinity
  if (from >= until) throw new Error('统计开始日期不能晚于结束日期')
  return [from, until]
}

export function effectiveWaterLedger(ledger) {
  const byId = new Map(ledger.map(row => [row.ledgerId, row]))
  const replacedIds = new Set()
  const visited = new Set()
  for (const row of ledger) {
    if (row.qualityStatus !== 'FINAL') continue
    waterTenths(row.volumeM3)
    if (row.revisionOf) {
      if (!byId.has(row.revisionOf) || replacedIds.has(row.revisionOf)) throw new Error('账本修订来源缺失或存在分叉')
      replacedIds.add(row.revisionOf)
    }
    const path = new Set()
    let current = row
    while (current && !visited.has(current.ledgerId)) {
      if (path.has(current.ledgerId)) throw new Error('账本修订存在循环')
      path.add(current.ledgerId)
      current = byId.get(current.revisionOf)
    }
    for (const id of path) visited.add(id)
  }
  return ledger.filter(row => row.qualityStatus === 'FINAL' && !replacedIds.has(row.ledgerId))
}

function waterTenths(volumeM3) {
  if (typeof volumeM3 !== 'number' || !Number.isFinite(volumeM3) || volumeM3 < 0) throw new Error('账本水量缺失或无效')
  const tenths = Math.round(volumeM3 * 10)
  if (!Number.isSafeInteger(tenths) || Math.abs(tenths / 10 - volumeM3) > 1e-8) throw new Error('账本水量必须为安全范围内的 0.1m³ 精度')
  return tenths
}

function addWater(tenths, next) {
  const total = tenths + next
  if (!Number.isSafeInteger(total)) throw new Error('累计水量超出安全范围')
  return total
}

export function projectWaterAccounting(index, filters = {}) {
  const [from, until] = dateWindow(filters)
  const rows = []
  const fieldTotals = new Map()
  const runTotals = new Map()
  const methodTotals = new Map()
  const settlementSeries = new Map()
  let totalTenths = 0

  for (const ledger of effectiveWaterLedger(index.entities.WaterLedger ?? [])) {
    const zone = index.byId.IrrigationZone.get(ledger.zoneId)
    const field = zone && index.byId.Field.get(zone.fieldId)
    if (!zone || !field) throw new Error('账本关联分区或田块不存在')
    const settledAt = Date.parse(ledger.endedAt)
    if (!Number.isFinite(settledAt)) throw new Error('账本结算时间无效')
    const tenths = waterTenths(ledger.volumeM3)
    if (settledAt < from || settledAt >= until ||
        (filters.fieldId && field.fieldId !== filters.fieldId) ||
        (filters.farmId && field.farmId !== filters.farmId) ||
        (filters.zoneId && zone.zoneId !== filters.zoneId) ||
        (filters.seasonId && ledger.seasonId !== filters.seasonId) ||
        (filters.seasonIds?.length && !filters.seasonIds.includes(ledger.seasonId))) continue
    const season = index.byId.CropSeason.get(ledger.seasonId)
    if (filters.crop && season?.crop !== filters.crop) continue
    rows.push({ ...ledger, fieldId: field.fieldId, fieldName: field.name, zoneName: zone.name })
    totalTenths = addWater(totalTenths, tenths)
    fieldTotals.set(field.fieldId, addWater(fieldTotals.get(field.fieldId) ?? 0, tenths))
    runTotals.set(ledger.runId, addWater(runTotals.get(ledger.runId) ?? 0, tenths))
    methodTotals.set(ledger.method, addWater(methodTotals.get(ledger.method) ?? 0, tenths))
    const seasons = settlementSeries.get(field.fieldId) ?? new Map()
    const settlements = seasons.get(ledger.seasonId) ?? []
    settlements.push({ at: settledAt, tenths })
    seasons.set(ledger.seasonId, settlements)
    settlementSeries.set(field.fieldId, seasons)
  }

  for (const seasons of settlementSeries.values()) for (const settlements of seasons.values()) {
    settlements.sort((a, b) => a.at - b.at)
    let prefixTenths = 0
    for (const settlement of settlements) settlement.prefixTenths = prefixTenths = addWater(prefixTenths, settlement.tenths)
  }
  const prefixBefore = (settlements, boundary) => {
    let low = 0
    let high = settlements.length
    while (low < high) {
      const middle = Math.floor((low + high) / 2)
      if (settlements[middle].at < boundary) low = middle + 1
      else high = middle
    }
    return { count: low, tenths: settlements[low - 1]?.prefixTenths ?? 0 }
  }

  let areaTenths = 0
  const byField = [...fieldTotals].map(([fieldId, tenths]) => {
    const field = index.byId.Field.get(fieldId)
    if (typeof field.areaMu !== 'number' || !Number.isFinite(field.areaMu) || field.areaMu <= 0) throw new Error('统计田块面积无效')
    areaTenths += Math.round(field.areaMu * 10)
    return { fieldId, fieldName: field.name, areaMu: field.areaMu, volumeM3: tenths / 10, perMuM3: round(tenths / 10 / field.areaMu) }
  })

  // Each reference owns an exact comparison window. A single-field reference
  // never supplies a farm-wide percentage for a broader reporting window.
  const baselineKey=reference=>JSON.stringify([reference.fieldId,reference.seasonId,reference.referenceStart,reference.referenceEnd])
  const baselineCounts=new Map()
  for(const reference of index.entities.WaterBaseline??[])if(reference.status==='ENABLED')baselineCounts.set(baselineKey(reference),(baselineCounts.get(baselineKey(reference))??0)+1)
  const baselineComparisons = (index.entities.WaterBaseline ?? []).flatMap(reference => {
    if (reference.status !== 'ENABLED' || !fieldTotals.has(reference.fieldId) ||
        (filters.seasonId && reference.seasonId !== filters.seasonId)) return []
    const [referenceFrom, referenceUntil] = dateWindow({ start: reference.referenceStart, end: reference.referenceEnd })
    const field = index.byId.Field.get(reference.fieldId)
    const settlements = settlementSeries.get(reference.fieldId)?.get(reference.seasonId) ?? []
    const before = prefixBefore(settlements, referenceFrom)
    const through = prefixBefore(settlements, referenceUntil)
    const completeWindow = from <= referenceFrom && until >= referenceUntil
    const duplicate=baselineCounts.get(baselineKey(reference))>1
    const comparable = !duplicate && !filters.zoneId && completeWindow && through.count > before.count && Number.isFinite(reference.referenceAreaMu) && reference.referenceAreaMu > 0 &&
      typeof reference.referenceVolumeM3 === 'number' && Number.isFinite(reference.referenceVolumeM3) && reference.referenceVolumeM3 > 0
    const actualM3 = (through.tenths - before.tenths) / 10
    const comparableReferenceM3 = reference.referenceVolumeM3 / reference.referenceAreaMu * field.areaMu
    const reason=duplicate?'存在重复可比基准，无法确定唯一参考口径':comparable?null:'缺少同田块同作物同窗口的有效可比基准'
    return [{ ...reference, actualM3, comparableReferenceM3, comparable, reason, savingPercent: comparable ? round((comparableReferenceM3 - actualM3) / comparableReferenceM3 * 100) : null }]
  })
  const fullWindowReferences = baselineComparisons.filter(reference => reference.comparable && dayBoundary(reference.referenceStart) === from && dayBoundary(reference.referenceEnd) + DAY_MS === until)
  const referenceFields = new Set(fullWindowReferences.map(reference => reference.fieldId))
  const referenceSeasons = new Map(fullWindowReferences.map(reference => [reference.fieldId, reference.seasonId]))
  const fullyComparable = rows.length > 0 && referenceFields.size === fieldTotals.size && fullWindowReferences.length === referenceFields.size &&
    rows.every(row => referenceSeasons.get(row.fieldId) === row.seasonId)
  const referenceM3 = fullWindowReferences.reduce((sum, row) => sum + row.comparableReferenceM3, 0)

  return {
    rows, byField, byRun: [...runTotals].map(([runId, tenths]) => ({ runId, volumeM3: tenths / 10 })),
    totalM3: totalTenths / 10,
    measuredM3: (methodTotals.get('MEASURED') ?? 0) / 10,
    allocatedM3: (methodTotals.get('ALLOCATED') ?? 0) / 10,
    estimatedM3: (methodTotals.get('ESTIMATED') ?? 0) / 10,
    coveredAreaMu: areaTenths / 10,
    perMuM3: areaTenths > 0 ? round(totalTenths / areaTenths) : null,
    baseline: baselineComparisons[0] ?? null, baselineComparisons,
    farmSavingPercent: fullyComparable ? round((referenceM3 - totalTenths / 10) / referenceM3 * 100) : null,
  }
}
