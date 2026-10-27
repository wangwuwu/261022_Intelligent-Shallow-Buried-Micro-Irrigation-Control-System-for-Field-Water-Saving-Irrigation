export function validateFieldFacts(index, field) {
  const errors = {}
  if (typeof field.name !== 'string' || !field.name.trim()) errors.name = '田块名称必填'
  const soilTypes = new Set((index.entities.Field ?? []).map(row => row.soilType).filter(Boolean))
  if (!field.soilType || !soilTypes.has(field.soilType)) errors.soilType = '请选择有效的土壤类型'
  if (typeof field.code !== 'string' || !field.code.trim()) errors.code = '田块编码必填'
  else if ((index.entities.Field ?? []).some(existing => existing.fieldId !== field.fieldId && existing.code === field.code.trim())) errors.code = '田块编码已存在'
  if (typeof field.areaMu !== 'number' || !Number.isFinite(field.areaMu) || field.areaMu <= 0) errors.areaMu = '田块面积必须大于零'
  else {
    const enabledAreaMu = (index.zonesByField.get(field.fieldId) ?? []).filter(zone => zone.status === 'ENABLED').reduce((sum, zone) => sum + zone.areaMu, 0)
    if (field.areaMu + 1e-8 < enabledAreaMu) errors.areaMu = '田块面积不能小于已启用分区面积之和'
  }
  const [longitude, latitude] = Array.isArray(field.location) ? field.location : []
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || Math.abs(longitude) > 180 || Math.abs(latitude) > 90) errors.location = '经纬度超出有效范围'
  const manager = index.byId.User.get(field.managerId)
  if (!manager || manager.status !== 'ENABLED' || manager.farmId !== field.farmId) errors.managerId = '请选择同农场的启用负责人'
  const existing = index.byId.Field.get(field.fieldId)
  if (existing && existing.farmId !== field.farmId) errors.farmId = '不能变更田块所属农场'
  return errors
}
