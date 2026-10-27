import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createIrrigationRepository} from '../src/data/repository.js'
import {createPreviewCredential} from '../src/data/auth.js'
import {buildIrrigationIndex,assessMoistureTrigger,projectWaterAccounting} from '../src/domain/irrigation.js'
const initial=JSON.parse(readFileSync(new URL('../../shared_context.json',import.meta.url))).entities
class MemoryStorage {values=new Map();getItem(k){return this.values.get(k)??null}setItem(k,v){this.values.set(k,v)}removeItem(k){this.values.delete(k)}}
async function repository(seed=structuredClone(initial),role='ADMIN'){
 const user=seed.User.find(u=>u.role===role&&u.status==='ENABLED'),password=crypto.randomUUID(),credentials={[user.account]:await createPreviewCredential(password,1000)}
 const repo=createIrrigationRepository({seed,credentials,storage:new MemoryStorage(),sessionStorage:new MemoryStorage(),lock:fn=>fn(),clock:()=>new Date('2026-07-28T10:18:43+08:00')})
 await repo.load();await repo.login(user.account,password);return {repo,user,seed}
}
function addForeign(seed){
 const field={...seed.Field[1],fieldId:'foreign-field',farmId:'foreign-farm'};const device={...seed.Device.find(d=>d.kind==='SOIL_PROBE'),deviceId:'foreign-device',farmId:'foreign-farm'}
 const zone={...seed.IrrigationZone[1],zoneId:'foreign-zone',fieldId:field.fieldId,farmId:'foreign-farm'}
 const point={...seed.Point[0],pointId:'foreign-point',deviceId:device.deviceId,zoneId:zone.zoneId}
 seed.Field.push(field);seed.Device.push(device);seed.IrrigationZone.push(zone);seed.Point.push(point);return {field,device,zone,point}
}
test('SEASON_CREATE cannot overwrite an existing season identity',async()=>{
 const {repo}=await repository();const season=repo.state.entities.CropSeason[1],field=repo.state.entities.Field.find(f=>f.fieldId===season.fieldId)
 await assert.rejects(repo.commit('SEASON_CREATE',season,{expectedVersions:{[field.fieldId]:field.version}}),e=>e.code==='DUPLICATE_ID')
 assert.equal(repo.state.entities.CropSeason.find(s=>s.seasonId===season.seasonId).version,season.version)
})
test('season mutations require the owning field version and reject malformed harvest dates',async()=>{
 const {repo}=await repository();const season=repo.state.entities.CropSeason[1],field=repo.state.entities.Field.find(f=>f.fieldId===season.fieldId)
 await assert.rejects(repo.commit('SEASON_UPDATE',{...season,variety:season.variety+'改'},{expectedVersion:season.version}),e=>e.code==='VERSION_CONFLICT')
 await assert.rejects(repo.commit('SEASON_UPDATE',{...season,stage:'HARVESTED',harvestDate:'2026-09-31'},{expectedVersion:season.version,expectedVersions:{[field.fieldId]:field.version}}),e=>e.code==='VALIDATION')
})
test('an administrator cannot calibrate a point indirectly owned by another farm',async()=>{
 const seed=structuredClone(initial),foreign=addForeign(seed),{repo}=await repository(seed)
 assert.equal(repo.can('POINT_CALIBRATE',foreign.point),false)
 await assert.rejects(repo.commit('POINT_CALIBRATE',{pointId:foreign.point.pointId,referenceValue:20,measuredValue:19,note:'现场仪器校准依据'},{expectedVersion:1}),e=>e.code==='FORBIDDEN')
})
test('new pipe pump association must refer to a same-farm pump',async()=>{
 const seed=structuredClone(initial),foreign=addForeign(seed),{repo}=await repository(seed)
 const draft={name:'管段引用校验',kind:'MAIN',parentNodeId:null,capacityM3h:30,maxConcurrentZones:1,depthCm:4,intervalCm:30,designFlowM3h:20,pumpDeviceId:foreign.device.deviceId}
 await assert.rejects(repo.commit('PIPE_SAVE',draft),e=>e.code==='FORBIDDEN')
 await assert.rejects(repo.commit('PIPE_SAVE',{...draft,pumpDeviceId:initial.Device.find(d=>d.kind==='SOIL_PROBE').deviceId}),e=>e.code==='VALIDATION')
})
test('zone point association cannot cross farm through a point without its own farmId',async()=>{
 const seed=structuredClone(initial),foreign=addForeign(seed);const source=seed.IrrigationZone.find(z=>z.fieldId===seed.Field[1].fieldId)
 seed.IrrigationZone=seed.IrrigationZone.filter(z=>z.zoneId!==source.zoneId);const {repo}=await repository(seed)
 const draft={...source,zoneId:undefined,name:'分区关联校验',areaMu:1,accountingMethod:'ALLOCATED',allocationRule:'已批准的计量时长权重分摊',soilPointIds:[foreign.point.pointId]}
 await assert.rejects(repo.commit('ZONE_CREATE',draft),e=>e.code==='FORBIDDEN')
})
test('point mapping refuses device transfer and foreign replacement zones',async()=>{
 const seed=structuredClone(initial),foreign=addForeign(seed),{repo}=await repository(seed),point=repo.state.entities.Point.find(p=>p.zoneId===initial.IrrigationZone[2].zoneId)
 await assert.rejects(repo.commit('POINT_UPDATE',{...point,deviceId:foreign.device.deviceId},{expectedVersion:point.version}),e=>['FORBIDDEN','IMMUTABLE_FIELD'].includes(e.code))
 await assert.rejects(repo.commit('POINT_UPDATE',{...point,zoneId:foreign.zone.zoneId},{expectedVersion:point.version}),e=>e.code==='FORBIDDEN')
})
test('export cancellation and reads never cross the current farm boundary',async()=>{
 const seed=structuredClone(initial),owner=seed.User.find(u=>u.role==='ADMIN');seed.ExportJob.push({...seed.ExportJob[0],exportId:'foreign-export',farmId:'foreign-farm',createdBy:owner.userId,status:'QUEUED'})
 const {repo}=await repository(seed);await assert.rejects(repo.commit('EXPORT_CANCEL',{exportId:'foreign-export'}),e=>e.code==='FORBIDDEN');await assert.rejects(repo.query('exportFile',{exportId:'foreign-export'}),e=>['FORBIDDEN','NOT_FOUND'].includes(e.code))
})
test('moisture trigger refuses an online device whose heartbeat is stale',()=>{
 const seed=structuredClone(initial),strategy=seed.Strategy[0],zone=seed.IrrigationZone.find(z=>z.zoneId===strategy.zoneIds[0]),point=seed.Point.find(p=>p.pointId===zone.soilPointIds[0]);seed.Device.find(d=>d.deviceId===point.deviceId).lastSeenAt='2026-07-27T00:00:00+08:00'
 const result=assessMoistureTrigger(buildIrrigationIndex(seed),strategy,new Date('2026-07-28T10:18:43+08:00'),{representativePointByZone:{[zone.zoneId]:point.pointId}})
 assert.equal(result[0].eligible,false);assert.match(result[0].reason,/心跳|通信/)
})
test('logout invalidates the previously cached authorized relation index',async()=>{
 const {repo}=await repository();assert.equal(repo.getIndex().entities.Field.length,initial.Field.length);await repo.logout();assert.equal(repo.getIndex().entities.Field.length,0)
})
test('duplicate comparable baselines invalidate the single-card comparison too',()=>{
 const seed=structuredClone(initial),reference=seed.WaterBaseline[0];seed.WaterBaseline.push({...reference,baselineId:'duplicate-reference'})
 const report=projectWaterAccounting(buildIrrigationIndex(seed),{start:'2026-06-01',end:'2026-07-28'})
 assert.equal(report.baseline.comparable,false);assert.equal(report.baseline.savingPercent,null);assert.match(report.baseline.reason,/重复|唯一/)
})
test('dispatch requires the selected alarm version before it creates a work order',async()=>{
 const seed=structuredClone(initial),alarm=seed.Alarm[0];seed.WorkOrder=seed.WorkOrder.filter(w=>w.alarmId!==alarm.alarmId);const {repo}=await repository(seed)
 const draft={alarmId:alarm.alarmId,kind:'DEVICE_REPAIR',assigneeId:seed.User.find(u=>u.role==='TECHNICIAN').userId,dueAt:'2026-07-29T15:00:00+08:00',note:'现场检查设备供电与接线情况'}
 await assert.rejects(repo.commit('WORKORDER_CREATE',draft,{expectedVersions:{[alarm.alarmId]:alarm.version-1}}),e=>e.code==='VERSION_CONFLICT')
})
test('export date uses the Shanghai business day for UTC source timestamps',async()=>{
 const seed=structuredClone(initial);seed.WaterLedger=[{...seed.WaterLedger[0],startedAt:'2026-07-26T16:00:00Z',endedAt:'2026-07-26T17:00:00Z'}];const {repo}=await repository(seed)
 const created=await repo.commit('EXPORT_CREATE',{filters:{start:'2026-07-27',end:'2026-07-27'}})
 for(let i=0;i<100&&repo.state.entities.ExportJob.find(j=>j.exportId===created.entityId).status!=='READY';i++)await new Promise(resolve=>setTimeout(resolve,2))
 const result=await repo.query('exportFile',{exportId:created.entityId});assert.match(result.content,/"2026-07-27"/)
})
test('resource rejection evidence does not disclose unpermitted plan, zone, or device identifiers',async()=>{
 const seed=structuredClone(initial),manager=seed.User.find(u=>u.role==='MANAGER');manager.fieldIds=[seed.Field[1].fieldId];seed.PipeNode.find(n=>n.nodeId===seed.IrrigationZone[2].sourceNodeId).parentNodeId=seed.PipeNode[0].nodeId;const {repo}=await repository(seed,'MANAGER'),zone=repo.state.entities.IrrigationZone.find(z=>z.fieldId===seed.Field[1].fieldId)
 await assert.rejects(repo.commit('PLAN_CREATE',{name:'跨授权资源证据验证',scheduledAt:'2026-07-29T08:00:00+08:00',steps:[{zoneId:zone.zoneId,targetVolumeM3:1,expectedFlowM3h:60,maxDurationMin:60}]}),error=>{
  assert.equal(error.code,'RESOURCE_CONFLICT');const details=JSON.stringify(error.details)
  for(const hidden of [seed.IrrigationZone[0].zoneId,seed.IrrigationRun[0].planId,seed.Device.find(d=>d.deviceId===seed.IrrigationZone[0].valveDeviceId).deviceId])assert.equal(details.includes(hidden),false)
  return true
 })
})
test('domain enum rules reject unsupported crop stages and record states',async()=>{
 const {repo}=await repository();const season=repo.state.entities.CropSeason[1],field=repo.state.entities.Field.find(f=>f.fieldId===season.fieldId)
 await assert.rejects(repo.commit('SEASON_UPDATE',{...season,stage:'SEEDLING'},{expectedVersion:season.version,expectedVersions:{[field.fieldId]:field.version}}),e=>e.code==='VALIDATION')
 await assert.rejects(repo.commit('PIPE_SAVE',{name:'非法状态管段',kind:'MAIN',capacityM3h:10,maxConcurrentZones:1,designFlowM3h:5,depthCm:4,intervalCm:30,status:'UNKNOWN'}),e=>e.code==='VALIDATION')
})
test('device, pipe and work-order kinds are constrained by the source vocabulary',async()=>{
 const {repo}=await repository();await assert.rejects(repo.commit('DEVICE_CREATE',{code:crypto.randomUUID(),name:'类型校验设备',kind:'UNKNOWN_KIND',manufacturer:'现场登记',model:'未核验型号',protocol:'',endpoint:''}),e=>e.code==='VALIDATION')
 await assert.rejects(repo.commit('PIPE_SAVE',{name:'类型校验管段',kind:'UNKNOWN_KIND',capacityM3h:10,maxConcurrentZones:1,designFlowM3h:5,depthCm:4,intervalCm:30}),e=>e.code==='VALIDATION')
 await assert.rejects(repo.commit('WORKORDER_CREATE',{kind:'UNKNOWN_KIND',zoneId:initial.IrrigationZone[2].zoneId,assigneeId:initial.User.find(u=>u.role==='TECHNICIAN').userId,dueAt:'2026-07-29T15:00:00+08:00',note:'工单类型校验要求填写实际检查'}),e=>e.code==='VALIDATION')
})
test('valid dual-version season edit and alarm-version dispatch remain atomic successful flows',async()=>{
 const seed=structuredClone(initial),alarm=seed.Alarm[0];seed.WorkOrder=seed.WorkOrder.filter(w=>w.alarmId!==alarm.alarmId);const {repo}=await repository(seed),season=repo.state.entities.CropSeason[1],field=repo.state.entities.Field.find(f=>f.fieldId===season.fieldId)
 await repo.commit('SEASON_UPDATE',{...season,variety:season.variety+'复核'},{expectedVersion:season.version,expectedVersions:{[field.fieldId]:field.version}})
 assert.equal(repo.state.entities.CropSeason.find(s=>s.seasonId===season.seasonId).version,season.version+1);assert.equal(repo.state.entities.Field.find(f=>f.fieldId===field.fieldId).version,field.version+1)
 const revision=repo.state.revision;const result=await repo.commit('WORKORDER_CREATE',{alarmId:alarm.alarmId,kind:'DEVICE_REPAIR',assigneeId:seed.User.find(u=>u.role==='TECHNICIAN').userId,dueAt:'2026-07-29T15:00:00+08:00',note:'现场检查设备供电与接线情况'},{expectedVersions:{[alarm.alarmId]:alarm.version}})
 assert.equal(repo.state.revision,revision+1);assert.equal(repo.state.entities.Alarm.find(a=>a.alarmId===alarm.alarmId).version,alarm.version+1);assert.equal(repo.state.entities.WorkOrder.find(w=>w.workOrderId===result.entityId).status,'ASSIGNED')
})
test('device registration keeps connection method and endpoint required before unverified saving',async()=>{
 const {repo}=await repository(),draft={code:crypto.randomUUID(),name:'待核验接入设备',kind:'SOIL_PROBE',manufacturer:'现场登记厂家',model:'现场登记型号',protocol:'',endpoint:''}
 await assert.rejects(repo.commit('DEVICE_CREATE',draft),error=>error.code==='VALIDATION'&&!!error.fieldErrors.protocol)
 await assert.rejects(repo.commit('DEVICE_CREATE',{...draft,protocol:'FIELD_GATEWAY',endpoint:''}),error=>error.code==='VALIDATION'&&!!error.fieldErrors.endpoint)
 await assert.rejects(repo.commit('DEVICE_CREATE',{...draft,protocol:'FIELD_GATEWAY',endpoint:'invalid endpoint'}),error=>error.code==='VALIDATION'&&!!error.fieldErrors.endpoint)
 const created=await repo.commit('DEVICE_CREATE',{...draft,protocol:'FIELD_GATEWAY',endpoint:'gateway://field-probe'})
 const device=repo.state.entities.Device.find(d=>d.deviceId===created.entityId);assert.equal(device.verification,'UNVERIFIED');assert.equal(device.connection,'UNKNOWN')
})

async function expiryRepository(extra={}){
 let now=new Date('2026-07-28T10:18:43+08:00');const seed=structuredClone(initial),user=seed.User.find(u=>u.role==='ADMIN'),password=crypto.randomUUID(),credentials={[user.account]:await createPreviewCredential(password,1000)},storage=new MemoryStorage()
 const repo=createIrrigationRepository({seed,credentials,storage,sessionStorage:new MemoryStorage(),lock:fn=>fn(),clock:()=>now,...extra});await repo.load();await repo.login(user.account,password)
 return {repo,storage,advance:()=>{now=new Date(+now+9*3600000)}}
}
test('expiry through can clears published entities and the cached relation index and emits auth change',async()=>{
 const {repo,advance}=await expiryRepository();repo.getIndex();const events=[];repo.subscribe(event=>events.push(event));advance()
 assert.equal(repo.can('FIELD_CREATE'),false);assert.equal(repo.state.user,null);assert.equal(repo.state.entities.Field.length,0);assert.equal(repo.getIndex().entities.Field.length,0);assert.equal(events.at(-1).authChanged,true)
})
test('expiry through getIndex or explicit check clears the session without another operation',async()=>{
 for(const method of ['getIndex','checkSession']){const {repo,advance}=await expiryRepository();repo.getIndex();advance();repo[method]();assert.equal(repo.state.user,null);assert.equal(repo.getIndex().entities.Field.length,0)}
})
test('scheduled expiry clears the session and emits auth change',async()=>{
 let scheduled;const {repo,advance}=await expiryRepository({schedule:(callback,delay)=>{scheduled={callback,delay};return 1},cancelSchedule:()=>{}})
 assert.equal(scheduled.delay,8*3600000);const events=[];repo.subscribe(event=>events.push(event));advance();scheduled.callback();assert.equal(repo.state.user,null);assert.equal(events.at(-1).authChanged,true)
})
test('corrupt snapshot can be exported verbatim and recovery requires explicit confirmation',async()=>{
 const storage=new MemoryStorage(),raw='{broken original snapshot';storage.setItem('irrigation.preview.snapshot.v1',raw)
 const repo=createIrrigationRepository({seed:initial,storage,sessionStorage:new MemoryStorage(),lock:fn=>fn()});await repo.load();assert.equal(repo.state.error.code,'STORAGE_CORRUPT')
 const backup=await repo.exportCorruptSnapshot();assert.equal(backup.content,raw);assert.match(backup.fileName,/\.json$/)
 await assert.rejects(repo.recoverInitialSnapshot(),error=>error.code==='CONFIRMATION_REQUIRED');assert.equal(storage.getItem('irrigation.preview.snapshot.v1'),raw)
 await repo.recoverInitialSnapshot({confirmed:true});assert.equal(repo.state.error,null);assert.equal(repo.state.user,null);assert.equal(repo.getIndex().entities.Field.length,0);assert.equal(JSON.parse(storage.getItem('irrigation.preview.snapshot.v1')).entities.Field.length,initial.Field.length)
 await assert.rejects(repo.recoverInitialSnapshot({confirmed:true}),error=>error.code==='RECOVERY_NOT_REQUIRED')
})
test('failed snapshot recovery preserves the damaged bytes and visible error',async()=>{
 const storage=new MemoryStorage(),raw='unreadable original';storage.setItem('irrigation.preview.snapshot.v1',raw);const repo=createIrrigationRepository({seed:initial,storage,lock:fn=>fn()});await repo.load();storage.setItem=()=>{throw new Error('quota')}
 await assert.rejects(repo.recoverInitialSnapshot({confirmed:true}),error=>error.code==='STORAGE_FAILED');assert.equal(storage.getItem('irrigation.preview.snapshot.v1'),raw);assert.equal(repo.state.error.code,'STORAGE_CORRUPT')
})
