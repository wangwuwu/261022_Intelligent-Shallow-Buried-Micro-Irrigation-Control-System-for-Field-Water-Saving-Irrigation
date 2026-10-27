import { primaryKeys,actionRoles,cloneFacts } from './contracts.js'
export function relatedFarmIds(entities,kind,entity,visited=new Set()) {
 if(!entity)return []
 const token=`${kind}:${entity[primaryKeys[kind]]??'draft'}`;if(visited.has(token))return [];visited.add(token)
 const farms=new Set(entity.farmId?[entity.farmId]:[])
 const references={fieldId:'Field',zoneId:'IrrigationZone',deviceId:'Device',pointId:'Point',runId:'IrrigationRun',planId:'Plan',sourceNodeId:'PipeNode',parentNodeId:'PipeNode',pumpDeviceId:'Device',valveDeviceId:'Device',gatewayDeviceId:'Device',meterPointId:'Point'}
 const include=(target,id)=>{if(!id||target===kind&&id===entity[primaryKeys[kind]])return;const row=(entities[target]??[]).find(x=>x[primaryKeys[target]]===id);for(const farm of relatedFarmIds(entities,target,row,visited))farms.add(farm)}
 for(const [key,target]of Object.entries(references))include(target,entity[key])
 for(const id of entity.zoneIds??[])include('IrrigationZone',id)
 for(const id of entity.soilPointIds??[])include('Point',id)
 for(const id of entity.fieldIds??[])include('Field',id)
 return [...farms]
}
export function relatedFieldIds(entities,kind,entity) {
 if(!entity)return []
 if(kind==='Field')return [entity.fieldId]
 if(entity.fieldId)return [entity.fieldId]
 if(kind==='IrrigationZone')return [entity.fieldId]
 if(entity.zoneId)return (entities.IrrigationZone??[]).filter(z=>z.zoneId===entity.zoneId).map(z=>z.fieldId)
 if(entity.zoneIds)return (entities.IrrigationZone??[]).filter(z=>entity.zoneIds.includes(z.zoneId)).map(z=>z.fieldId)
 if(kind==='Plan')return [...new Set((entities.PlanStep??[]).filter(s=>s.planId===entity.planId).flatMap(s=>relatedFieldIds(entities,'PlanStep',s)))]
 if(kind==='IrrigationRun')return [...new Set((entities.RunStep??[]).filter(s=>s.runId===entity.runId).flatMap(s=>relatedFieldIds(entities,'RunStep',s)))]
 if(kind==='PipeNode') {
  const nodes=new Set([entity.nodeId]);let previous=-1
  while(previous!==nodes.size){ previous=nodes.size;for(const n of entities.PipeNode??[])if(nodes.has(n.parentNodeId))nodes.add(n.nodeId) }
  return [...new Set((entities.IrrigationZone??[]).filter(z=>nodes.has(z.sourceNodeId)).map(z=>z.fieldId))]
 }
 if(kind==='Device')return [...new Set([...(entities.Point??[]).filter(p=>p.deviceId===entity.deviceId&&p.zoneId).flatMap(p=>(entities.IrrigationZone??[]).filter(z=>z.zoneId===p.zoneId).map(z=>z.fieldId)),...(entities.IrrigationZone??[]).filter(z=>z.valveDeviceId===entity.deviceId).map(z=>z.fieldId),...(entities.PipeNode??[]).filter(n=>n.pumpDeviceId===entity.deviceId).flatMap(n=>relatedFieldIds(entities,'PipeNode',n))])]
 if(entity.deviceId){const d=(entities.Device??[]).find(d=>d.deviceId===entity.deviceId);return relatedFieldIds(entities,'Device',d)}
 if(entity.pointId){const p=(entities.Point??[]).find(p=>p.pointId===entity.pointId);return relatedFieldIds(entities,'Point',p)}
 if(entity.runId){const r=(entities.IrrigationRun??[]).find(r=>r.runId===entity.runId);return relatedFieldIds(entities,'IrrigationRun',r)}
 return []
}
export function canOperate(user,actionId,entity,entities={}) {
 if(!user||user.status!=='ENABLED'||!actionRoles[actionId]?.includes(user.role))return false
 if(entity?.farmId&&entity.farmId!==user.farmId)return false
 if(actionId.startsWith('WORKORDER_')&&['WORKORDER_ACCEPT','WORKORDER_SUBMIT'].includes(actionId)&&entity&&entity.assigneeId!==user.userId)return false
 const kind=Object.keys(primaryKeys).reverse().find(k=>entity?.[primaryKeys[k]]&&k!=='Session')
 const fields=relatedFieldIds(entities,kind,entity)
 if(relatedFarmIds(entities,kind,entity).some(farmId=>farmId!==user.farmId)||fields.some(id=>entities.Field?.find(f=>f.fieldId===id)?.farmId!==user.farmId))return false
 return user.role==='ADMIN'||fields.every(id=>user.fieldIds?.includes(id))
}
export function scopeIrrigationFacts(entities,user) {
 const scoped=Object.fromEntries(Object.keys(primaryKeys).map(k=>[k,[]]))
 if(!user)return scoped
 const admin=user.role==='ADMIN';const fieldIds=new Set((entities.Field??[]).filter(f=>f.farmId===user.farmId&&(admin||user.fieldIds?.includes(f.fieldId))).map(f=>f.fieldId))
 const permitted=(kind,row)=>{if(relatedFarmIds(entities,kind,row).some(id=>id!==user.farmId))return false;const ids=relatedFieldIds(entities,kind,row);return ids.length?(kind==='PipeNode'||kind==='Device'?ids.some(id=>fieldIds.has(id)):ids.every(id=>fieldIds.has(id))):admin}
 for(const kind of ['Farm','Field','CropSeason','IrrigationZone','PipeNode','Device','Point','Strategy','Plan','PlanStep','IrrigationRun','RunStep','Alarm','WorkOrder','Calibration','WaterLedger','WaterBaseline']) {
  scoped[kind]=(entities[kind]??[]).filter(row=>kind==='Farm'?row.farmId===user.farmId:permitted(kind,row)).filter(row=>kind!=='WorkOrder'||user.role!=='TECHNICIAN'||row.assigneeId===user.userId)
 }
 const pointIds=new Set(scoped.Point.map(x=>x.pointId)), runIds=new Set(scoped.IrrigationRun.map(x=>x.runId))
 const deviceIds=new Set(scoped.Device.map(x=>x.deviceId));for(const device of [...scoped.Device])if(device.gatewayDeviceId){const gateway=entities.Device.find(x=>x.deviceId===device.gatewayDeviceId&&x.farmId===user.farmId);if(gateway&&!deviceIds.has(gateway.deviceId)){scoped.Device.push(gateway);deviceIds.add(gateway.deviceId)}}
 if(!admin)scoped.Device=scoped.Device.map(({endpoint,protocol,...visible})=>visible)
 scoped.TelemetryReading=(entities.TelemetryReading??[]).filter(x=>pointIds.has(x.pointId))
 scoped.CommandOutbox=(entities.CommandOutbox??[]).filter(x=>runIds.has(x.runId));const commandIds=new Set(scoped.CommandOutbox.map(x=>x.commandId))
 scoped.CommandEvent=(entities.CommandEvent??[]).filter(x=>commandIds.has(x.commandId))
 scoped.User=(entities.User??[]).filter(x=>x.farmId===user.farmId).map(x=>admin||x.userId===user.userId?x:{userId:x.userId,name:x.name,role:x.role,status:x.status,farmId:x.farmId,fieldIds:x.fieldIds.filter(id=>fieldIds.has(id)),version:x.version})
 scoped.SystemPolicy=(entities.SystemPolicy??[]).filter(x=>x.farmId===user.farmId).map(x=>admin?x:{policyId:x.policyId,farmId:x.farmId,defaultStaleSec:x.defaultStaleSec,commandAckTimeoutSec:x.commandAckTimeoutSec,actionConfirmTimeoutSec:x.actionConfirmTimeoutSec,maxScheduleDays:x.maxScheduleDays,version:x.version})
 scoped.ExportJob=(entities.ExportJob??[]).filter(x=>x.farmId===user.farmId&&(admin||x.createdBy===user.userId&&(x.authorizedFieldIds??(x.filterSnapshot?.fieldId?[x.filterSnapshot.fieldId]:[])).every(id=>fieldIds.has(id))))
 if(['ADMIN','MANAGER'].includes(user.role)) scoped.AuditLog=(entities.AuditLog??[]).filter(x=>x.farmId===user.farmId&&(admin||!x.entityId||Object.keys(scoped).some(k=>scoped[k].some(row=>row[primaryKeys[k]]===x.entityId))))
 return cloneFacts(scoped)
}
