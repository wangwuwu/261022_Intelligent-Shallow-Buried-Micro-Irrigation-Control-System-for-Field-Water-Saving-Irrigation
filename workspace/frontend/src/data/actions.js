import {buildIrrigationIndex,validateFieldFacts,assessRotationResources} from '../domain/irrigation.js'
import {primaryKeys,activeRunStatuses,reject,cloneFacts} from './contracts.js'
import {canOperate,relatedFieldIds,relatedFarmIds,scopeIrrigationFacts} from './permissions.js'

const positive = n=>typeof n==='number'&&Number.isFinite(n)&&n>0
const text = x=>typeof x==='string'?x.trim():''
const requireText=(value,field,label,min=1)=>{if(text(value).length<min)reject('VALIDATION',`${label}至少填写${min}字`,{[field]:`${label}至少填写${min}字`})}
const requirePositive=(value,field,label)=>{if(!positive(value))reject('VALIDATION',`${label}必须大于零`,{[field]:`${label}必须大于零`})}
const validDate=day=>{if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day))return false;const at=Date.parse(`${day}T00:00:00+08:00`);return Number.isFinite(at)&&new Date(at+8*3600000).toISOString().slice(0,10)===day}
const enumerations={CropStage:['SOWING','EMERGENCE','TILLERING','OVERWINTER','GREENING','JOINTING','HEADING','GRAIN_FILLING','HARVESTED'],RecordStatus:['ENABLED','DISABLED'],DeviceKind:['PUMP','VALVE','GATEWAY','SOIL_PROBE','FLOW_METER','PRESSURE_SENSOR','WEATHER_STATION'],PointKind:['SOIL_MOISTURE','SOIL_TEMPERATURE','FLOW_RATE','METER_TOTAL','PRESSURE','RAINFALL','PUMP_STATE','VALVE_STATE'],PipeKind:['SOURCE','MAIN','BRANCH'],WorkOrderKind:['LEAK_CHECK','CLOG_CHECK','FILTER_SERVICE','DEVICE_REPAIR','ROUTINE_INSPECTION']}
const requireEnum=(value,name,field)=>{if(!enumerations[name].includes(value))reject('VALIDATION','请选择有效的业务选项',{[field]:'请选择有效的业务选项'})}
const prefixes={Field:'FLD',CropSeason:'SEA',PipeNode:'PIP',IrrigationZone:'ZON',Device:'DEV',Point:'PT',Calibration:'CAL',Strategy:'STR',Plan:'PLN',PlanStep:'PST',IrrigationRun:'RUN',RunStep:'RST',WorkOrder:'WO',User:'USR',AuditLog:'AUD',ExportJob:'EXP'}
export const createEntityId=kind=>`${prefixes[kind]??kind.toUpperCase()}-RH-${crypto.randomUUID().replaceAll('-','').slice(0,10).toUpperCase()}`
export function reservationFingerprint(entities,draft){
 let hash=2166136261
 const facts=JSON.stringify({draft,versions:['PipeNode','IrrigationZone','Device','Point','Plan','PlanStep','IrrigationRun','RunStep','SystemPolicy'].map(k=>[k,entities[k]?.map(row=>[row[primaryKeys[k]],row.version,row.status,row.connection,row.lastSeenAt,row.startedAt,row.endedAt])])})
 for(let i=0;i<facts.length;i++)hash=Math.imul(hash^facts.charCodeAt(i),16777619)
 return `resources-${(hash>>>0).toString(16)}`
}
export function assessPlanDraft(entities,draft,now){
 const policy=entities.SystemPolicy.find(x=>x.farmId===draft.farmId)||entities.SystemPolicy[0]
 const result=assessRotationResources(buildIrrigationIndex(entities),draft,{includeActualRuns:true,now,maxScheduleDays:policy?.maxScheduleDays})
 return {...result,conflictHash:reservationFingerprint(entities,draft),factVersions:Object.fromEntries(['PipeNode','IrrigationZone','Device','SystemPolicy'].map(k=>[k,entities[k].map(x=>[x[primaryKeys[k]],x.version])]))}
}
export function redactResourceAssessment(assessment,entities,actor){
 const scoped=scopeIrrigationFacts(entities,actor),visible=Object.fromEntries(Object.entries(primaryKeys).map(([kind,key])=>[kind,new Set((scoped[kind]??[]).map(row=>row[key]))]))
 const redact=conflict=>{const row={...conflict};for(const [key,kind]of [['zoneId','IrrigationZone'],['planId','Plan'],['deviceId','Device'],['nodeId','PipeNode']])if(row[key]&&!visible[kind].has(row[key]))delete row[key];for(const [key,kind]of [['zoneIds','IrrigationZone'],['planIds','Plan']])if(row[key])row[key]=row[key].filter(id=>visible[kind].has(id));if(row.resourceKey){const [type,id]=row.resourceKey.split(':');const kind={node:'PipeNode',valve:'Device',zone:'IrrigationZone'}[type];if(kind&&!visible[kind].has(id))delete row.resourceKey}return row}
 return {...assessment,conflicts:assessment.conflicts.map(redact),factVersions:Object.fromEntries(Object.entries(assessment.factVersions??{}).map(([kind,pairs])=>[kind,pairs.filter(([id])=>visible[kind]?.has(id))]))}
}

export function applyIrrigationAction(entities,actor,actionId,payload,options,now){
 const draft=cloneFacts(payload.draft??payload.fieldDraft??payload.strategyDraft??payload.planDraft??payload.userDraft??payload.policyDraft??payload)
 const stamp=new Date(now).toISOString();const index=buildIrrigationIndex(entities);const changes=[]
 const get=(kind,id)=>entities[kind]?.find(row=>row[primaryKeys[kind]]===id)
 const must=(kind,id)=>get(kind,id)??reject('NOT_FOUND','记录不存在')
 const authorize=(kind,row)=>{if(!canOperate(actor,actionId,row,entities))reject('FORBIDDEN','无权执行此操作');return row}
 const expected=(kind,row)=>{
  const version=options.expectedVersions?.[row[primaryKeys[kind]]]??options.expectedVersion??draft.expectedVersion??draft.version
  if(version===undefined||Number(version)!==row.version)reject('VERSION_CONFLICT','记录已被其他操作更新，请重新读取后核对修改')
 }
 const save=(kind,record,existing)=>{
  const key=primaryKeys[kind],saved={...existing,...record,[key]:existing?.[key]??record[key]??createEntityId(kind),version:(existing?.version??0)+1,createdAt:existing?.createdAt??stamp,updatedAt:stamp}
  const position=(entities[kind]??=[]).findIndex(row=>row[key]===saved[key])
  if(!existing&&position>=0)reject('DUPLICATE_ID','新增记录不能覆盖已有稳定编号')
  if(position>=0)entities[kind][position]=saved;else entities[kind].push(saved)
  changes.push({entityType:kind,entityId:saved[key],version:saved.version});return saved
 }
 const existingFor=(kind,id)=>{const row=authorize(kind,must(kind,id));expected(kind,row);return row}
 const hasActiveField=fieldId=>(entities.IrrigationRun??[]).some(run=>activeRunStatuses.has(run.status)&&relatedFieldIds(entities,'IrrigationRun',run).includes(fieldId))
 const noActiveReference=(kind,row)=>{if(relatedFieldIds(entities,kind,row).some(hasActiveField))reject('ACTIVE_REFERENCE','存在活动运行引用，暂不能修改此供水或触发配置')}
 const validSameFarm=(kind,id)=>{const row=must(kind,id);if(relatedFarmIds(entities,kind,row).some(farm=>farm!==actor.farmId))reject('FORBIDDEN','关联对象不属于当前农场');return row}
 const resourceDetails=assessment=>redactResourceAssessment(assessment,entities,actor)
 const noteOf=()=>text(draft.note??draft.reason??draft.requestNote)
 const validateStrategy=record=>{
  requireEnum(record.stage,'CropStage','stage');requireEnum(record.status,'RecordStatus','status')
  requireText(record.name,'name','策略名称');requireText(record.crop,'crop','适用作物');requireText(record.stage,'stage','适用阶段')
  if(!Array.isArray(record.zoneIds)||!record.zoneIds.length)reject('VALIDATION','至少选择一个适用分区',{zoneIds:'至少选择一个适用分区'})
  if(!['SCHEDULE','VOLUME','MOISTURE'].includes(record.triggerMode))reject('VALIDATION','请选择有效触发模式',{triggerMode:'请选择有效触发模式'})
  if(record.triggerMode==='MOISTURE'&&(!Number.isFinite(record.thresholdVwc)||record.thresholdVwc<0||record.thresholdVwc>100))reject('VALIDATION','墒情阈值须在0—100之间',{thresholdVwc:'墒情阈值须在0—100之间'})
  if(record.triggerMode!=='MOISTURE')record.thresholdVwc=null
  requirePositive(record.targetVolumeM3,'targetVolumeM3','目标水量');requirePositive(record.maxDurationMin,'maxDurationMin','最长时长')
  if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(record.allowedStart)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(record.allowedEnd)||record.allowedStart>=record.allowedEnd)reject('VALIDATION','执行起止时段无效',{allowedEnd:'结束时刻须晚于开始时刻'})
  if(record.executionMode==='AUTO')reject('CAPABILITY_UNVERIFIED','自动执行尚未取得生产设备反馈、保护和联动签核',{executionMode:'未取得生产现场签核，不能开启自动执行'})
  if(!['RECOMMEND','CONFIRM_REQUIRED'].includes(record.executionMode))reject('VALIDATION','请选择人工确认或建议执行方式')
  for(const zoneId of record.zoneIds){const zone=validSameFarm('IrrigationZone',zoneId);authorize('IrrigationZone',zone);const season=entities.CropSeason.find(s=>s.fieldId===zone.fieldId&&s.status==='ENABLED');if(zone.status!=='ENABLED'||!season||season.crop!==record.crop||season.stage!==record.stage)reject('VALIDATION','分区作物或生育阶段与策略不匹配',{zoneIds:'分区作物或生育阶段与策略不匹配'})}
 }
 if(!canOperate(actor,actionId,null,entities))reject('FORBIDDEN','无权执行此操作')
 let record,kind,result={}
 if(actionId==='FIELD_CREATE'||actionId==='FIELD_UPDATE'){
  kind='Field';const old=actionId==='FIELD_UPDATE'?existingFor(kind,draft.fieldId):null
  record={...old,...draft,fieldId:old?.fieldId??createEntityId(kind),farmId:actor.farmId,name:text(draft.name),code:old?.code??draft.code??null}
  record.code ||= record.fieldId
  const errors=validateFieldFacts(index,record);if(Object.keys(errors).length)reject('VALIDATION','请检查田块资料',errors)
  if(!['ENABLED','DISABLED'].includes(record.status))reject('VALIDATION','请选择田块启用状态',{status:'请选择田块启用状态'})
  if(old&&record.status==='DISABLED'&&hasActiveField(old.fieldId))reject('ACTIVE_REFERENCE','该田块存在活动运行，不能停用')
  record=save(kind,record,old)
  if(!old){const owner=must('User',actor.userId);save('User',{...owner,fieldIds:[...new Set([...owner.fieldIds,record.fieldId])]},owner);result.refreshActor=true}
 }else if(['SEASON_CREATE','SEASON_UPDATE','SEASON_SAVE'].includes(actionId)){
  kind='CropSeason';const field=validSameFarm('Field',draft.fieldId);authorize('Field',field)
  if(actionId==='SEASON_CREATE'&&draft.seasonId)reject('DUPLICATE_ID','新增种植季不能携带已有种植季编号')
  if(actionId==='SEASON_UPDATE'&&!draft.seasonId)reject('NOT_FOUND','编辑种植季必须指定已有编号')
  const fieldVersion=options.expectedVersions?.[field.fieldId]??draft.expectedFieldVersion
  if(fieldVersion===undefined||Number(fieldVersion)!==field.version)reject('VERSION_CONFLICT','田块版本已更新或未提供，请重新读取田块后核对')
  const old=actionId==='SEASON_CREATE'?null:draft.seasonId?existingFor(kind,draft.seasonId):null
  if(old&&old.fieldId!==field.fieldId)reject('FORBIDDEN','种植季不属于当前田块')
  requireText(draft.crop,'crop','作物');requireText(draft.variety,'variety','品种');requireText(draft.stage,'stage','生育阶段')
  requireEnum(draft.stage,'CropStage','stage')
  if(!validDate(draft.plantingDate)||draft.harvestDate&&(!validDate(draft.harvestDate)||draft.harvestDate<draft.plantingDate))reject('VALIDATION','种植与收获日期无效',{plantingDate:'日期须为真实有效自然日，种植日期不得晚于收获日期',harvestDate:'请填写真实有效收获日期'})
  if(draft.stage==='HARVESTED'&&!draft.harvestDate)reject('VALIDATION','收获日期必填',{harvestDate:'收获日期必填'})
  const status=draft.stage==='HARVESTED'?'DISABLED':'ENABLED'
  if(status==='ENABLED'&&entities.CropSeason.some(s=>s.fieldId===field.fieldId&&s.status==='ENABLED'&&s.seasonId!==old?.seasonId))reject('ACTIVE_SEASON','该田块已有活动种植季，请先收获归档')
  record=save(kind,{...draft,status},old);save('Field',field,field)
 }else if(actionId==='PIPE_SAVE'){
  kind='PipeNode';const old=draft.nodeId?existingFor(kind,draft.nodeId):null
  requireEnum(draft.kind??old?.kind,'PipeKind','kind');requireEnum(draft.status??old?.status??'ENABLED','RecordStatus','status')
  requireText(draft.name??old?.name,'name','管段名称');requirePositive(draft.capacityM3h,'capacityM3h','供水能力');requirePositive(draft.designFlowM3h,'designFlowM3h','设计流量')
  if(!Number.isInteger(draft.maxConcurrentZones)||draft.maxConcurrentZones<1)reject('VALIDATION','最多同时运行分区数必须为正整数')
  if(!Number.isFinite(draft.depthCm)||draft.depthCm<0||!Number.isFinite(draft.intervalCm)||draft.intervalCm<0)reject('VALIDATION','埋深和间距不能为负值')
  if(old)noActiveReference(kind,old)
  const seen=new Set(old?[old.nodeId]:[]);let parentId=draft.parentNodeId
  while(parentId){if(seen.has(parentId))reject('SUPPLY_CYCLE','管网父子关系不能形成环路');seen.add(parentId);parentId=validSameFarm('PipeNode',parentId).parentNodeId}
  if(draft.pumpDeviceId){const pump=validSameFarm('Device',draft.pumpDeviceId);authorize('Device',pump);if(pump.kind!=='PUMP')reject('VALIDATION','供水泵必须关联同农场水泵设备',{pumpDeviceId:'请选择水泵设备'})}
  record=save(kind,{...draft,farmId:actor.farmId,status:draft.status??'ENABLED'},old)
 }else if(['ZONE_CREATE','ZONE_UPDATE'].includes(actionId)){
  kind='IrrigationZone';const old=actionId==='ZONE_UPDATE'?existingFor(kind,draft.zoneId):null
  requireEnum(draft.status??old?.status??'ENABLED','RecordStatus','status')
  const field=validSameFarm('Field',draft.fieldId);authorize('Field',field);authorize('PipeNode',validSameFarm('PipeNode',draft.sourceNodeId))
  const valve=validSameFarm('Device',draft.valveDeviceId);authorize('Device',valve);if(valve.kind!=='VALVE')reject('VALIDATION','控制设备必须为阀门')
  requireText(draft.name,'name','分区名称');requirePositive(draft.areaMu,'areaMu','分区面积');requirePositive(draft.designFlowM3h,'designFlowM3h','设计流量')
  const occupied=entities.IrrigationZone.filter(z=>z.fieldId===field.fieldId&&z.status==='ENABLED'&&z.zoneId!==old?.zoneId).reduce((n,z)=>n+z.areaMu,0)
  if(occupied+draft.areaMu>field.areaMu+1e-8)reject('VALIDATION','分区面积超过田块剩余面积',{areaMu:'分区面积超过田块剩余面积'})
  if(entities.IrrigationZone.some(z=>z.zoneId!==old?.zoneId&&z.status==='ENABLED'&&z.valveDeviceId===draft.valveDeviceId))reject('VALVE_OCCUPIED','该阀门已关联其他启用分区')
  if(draft.accountingMethod==='MEASURED'){const meter=validSameFarm('Point',draft.meterPointId);authorize('Point',meter);if(meter.kind!=='METER_TOTAL')reject('VALIDATION','实测计量必须关联累计计量点')}
  else if(draft.accountingMethod==='ALLOCATED')requireText(draft.allocationRule,'allocationRule','分摊依据');else if(draft.accountingMethod!=='ESTIMATED')reject('VALIDATION','请选择计量方式')
  for(const id of draft.soilPointIds??[]){const point=validSameFarm('Point',id);authorize('Point',point);if(point.kind!=='SOIL_MOISTURE')reject('VALIDATION','土层点必须为含水率点位')}
  if(old)noActiveReference(kind,old)
  record=save(kind,{...draft,farmId:actor.farmId,status:draft.status??'ENABLED'},old)
 }else if(actionId==='DEVICE_CREATE'){
  kind='Device';requireEnum(draft.kind,'DeviceKind','kind');if(draft.status!==undefined)requireEnum(draft.status,'RecordStatus','status');for(const [key,label] of [['code','设备编号'],['name','设备名称'],['manufacturer','厂家'],['model','型号'],['protocol','接入方式'],['endpoint','接入端点']])requireText(draft[key],key,label)
  if(entities.Device.some(d=>d.farmId===actor.farmId&&d.code===text(draft.code)))reject('VALIDATION','设备编号已存在',{code:'设备编号已存在'})
  try{new URL(draft.endpoint)}catch{reject('VALIDATION','接入端点格式无效',{endpoint:'接入端点格式无效'})}
  const {secret,password,...safeDraft}=draft
  record=save(kind,{...safeDraft,farmId:actor.farmId,connection:'UNKNOWN',verification:'UNVERIFIED',reportedState:'UNKNOWN',lastSeenAt:null,status:'ENABLED',heartbeatTimeoutSec:120,capabilities:{read:false,control:false,feedback:false,localSchedule:false,localProtection:false}})
 }else if(actionId==='DEVICE_VERIFY'){
  existingFor('Device',draft.deviceId);reject('ADAPTER_UNAVAILABLE','尚未配置可用的设备接入适配器，未执行核验')
 }else if(actionId==='POINT_UPDATE'||actionId==='POINT_CALIBRATE'){
  kind='Point';const old=existingFor(kind,draft.pointId);const zone=entities.IrrigationZone.find(z=>z.zoneId===old.zoneId)
  if(actionId==='POINT_UPDATE'){
   if(draft.deviceId!==undefined&&draft.deviceId!==old.deviceId||draft.farmId!==undefined&&draft.farmId!==old.farmId)reject('IMMUTABLE_FIELD','点位所属设备与农场不能通过映射编辑修改')
   if(draft.zoneId)authorize('IrrigationZone',validSameFarm('IrrigationZone',draft.zoneId))
  }
  if(zone&&hasActiveField(zone.fieldId))reject('ACTIVE_REFERENCE','活动灌溉正在使用该触发点，不能修改映射或系数')
  if(actionId==='POINT_CALIBRATE'){
   if(!Number.isFinite(draft.referenceValue)||draft.referenceValue<old.rangeMin||draft.referenceValue>old.rangeMax||!Number.isFinite(draft.measuredValue))reject('VALIDATION','校准参考值须在量程内且实测值有效',{referenceValue:'校准参考值须在量程内'})
   requireText(draft.note,'note','现场依据');const offset=draft.referenceValue-draft.measuredValue
   record=save(kind,{...old,offset},old)
   save('Calibration',{pointId:old.pointId,actorId:actor.userId,referenceValue:draft.referenceValue,measuredValue:draft.measuredValue,oldOffset:old.offset,newOffset:offset,calibratedAt:stamp,note:text(draft.note)})
  }else{
   requireEnum(draft.kind,'PointKind','kind')
   for(const [k,l]of[['name','点位名称'],['address','点位地址'],['unit','单位']])requireText(draft[k],k,l)
   if(entities.Point.some(p=>p.deviceId===old.deviceId&&p.pointId!==old.pointId&&p.address===draft.address))reject('VALIDATION','同设备点位地址已存在',{address:'同设备点位地址已存在'})
   if(!Number.isFinite(draft.rangeMin)||!Number.isFinite(draft.rangeMax)||draft.rangeMin>=draft.rangeMax||!positive(draft.staleAfterSec)||!Number.isFinite(draft.scale)||!Number.isFinite(draft.offset))reject('VALIDATION','点位量程、比例或有效期无效')
   const units={SOIL_MOISTURE:'%VWC',PRESSURE:'MPa',FLOW_RATE:'m³/h'};if(units[draft.kind]&&draft.unit!==units[draft.kind])reject('VALIDATION','点位单位与类型不匹配',{unit:'点位单位与类型不匹配'})
   record=save(kind,{...draft,deviceId:old.deviceId},old);const device=must('Device',old.deviceId);save('Device',{...device,verification:'UNVERIFIED'},device)
  }
 }else if(actionId.startsWith('STRATEGY_')){
  kind='Strategy';const old=actionId==='STRATEGY_CREATE'?null:existingFor(kind,draft.strategyId)
  const next={executionMode:'CONFIRM_REQUIRED',status:'ENABLED',...old,...draft,farmId:actor.farmId}
  if(actionId==='STRATEGY_ENABLE')next.status='ENABLED';if(actionId==='STRATEGY_DISABLE')next.status='DISABLED'
  validateStrategy(next);record=save(kind,next,old)
 }else if(actionId==='PLAN_CREATE'||actionId==='PLAN_UPDATE'){
  kind='Plan';const old=actionId==='PLAN_UPDATE'?existingFor(kind,draft.planId):null
  if(old?.status!=='DRAFT'&&old)reject('PLAN_LOCKED','已发布或执行过的计划不能编辑')
  requireText(draft.name,'name','计划名称');if(!Number.isFinite(Date.parse(draft.scheduledAt)))reject('VALIDATION','计划时间无效',{scheduledAt:'计划时间无效'})
  const steps=draft.steps??payload.stepDrafts??[];for(const step of steps)authorize('IrrigationZone',must('IrrigationZone',step.zoneId))
  const assessed=assessPlanDraft(entities,{...draft,farmId:actor.farmId,steps},now);if(!assessed.ok)reject('RESOURCE_CONFLICT','供水资源检查未通过',{},resourceDetails(assessed))
  const {steps:ignored,...facts}=draft;const strategy=facts.strategyId?validSameFarm('Strategy',facts.strategyId):null
  record=save(kind,{...facts,farmId:actor.farmId,status:'DRAFT',createdBy:old?.createdBy??actor.userId,strategySnapshot:old?.strategySnapshot??(strategy?cloneFacts(strategy):null),conflictHash:assessed.conflictHash},old)
  const previous=entities.PlanStep.filter(s=>s.planId===record.planId);entities.PlanStep=entities.PlanStep.filter(s=>s.planId!==record.planId)
  steps.forEach((step,order)=>{const was=previous.find(s=>s.planStepId===step.planStepId);if(step.planStepId&&!was&&old)reject('VALIDATION','步骤编号不属于当前计划');save('PlanStep',{...step,planId:record.planId,order:order+1},was)})
 }else if(actionId==='PLAN_PUBLISH'||actionId==='PLAN_CANCEL'){
  kind='Plan';const old=existingFor(kind,draft.planId)
  if(actionId==='PLAN_PUBLISH'){
   if(old.status!=='DRAFT')reject('PLAN_LOCKED','仅草稿计划可以发布')
   if(Date.parse(old.scheduledAt)<=Date.parse(now))reject('SCHEDULE_EXPIRED','计划时间已过期，请先修改时间')
   const steps=entities.PlanStep.filter(s=>s.planId===old.planId).sort((a,b)=>a.order-b.order)
   const assessed=assessPlanDraft(entities,{...old,steps},now)
   if(!assessed.ok)reject('RESOURCE_CONFLICT','供水资源检查未通过',{},resourceDetails(assessed))
   if(!draft.conflictHash||draft.conflictHash!==assessed.conflictHash)reject('RESOURCE_CHANGED','资源检查已失效，请重新检查',{},resourceDetails(assessed))
   if(entities.IrrigationRun.some(r=>r.planId===old.planId))reject('RUN_EXISTS','该计划已有运行记录')
   record=save(kind,{...old,status:'PUBLISHED'},old)
   const run=save('IrrigationRun',{farmId:actor.farmId,planId:old.planId,status:'QUEUED',activeStepId:null,lastCommandId:null,actualStartedAt:null,actualEndedAt:null,requestedAt:null,accountingClosed:false})
   for(const step of steps)save('RunStep',{runId:run.runId,planStepId:step.planStepId,zoneId:step.zoneId,order:step.order,status:'WAITING',targetVolumeM3:step.targetVolumeM3,startedAt:null,endedAt:null,meterStart:null,meterEnd:null,endReason:null})
   result.runId=run.runId
  }else{
   requireText(draft.reason,'reason','取消原因',6)
   const run=entities.IrrigationRun.find(r=>r.planId===old.planId)
   if(!['DRAFT','PUBLISHED'].includes(old.status)||run&&run.status!=='QUEUED'||run&&entities.CommandOutbox.some(c=>c.runId===run.runId&&['PENDING','SENT','ACKNOWLEDGED','UNKNOWN'].includes(c.status)))reject('PLAN_ALREADY_STARTED','该计划已经开始，请进入运行详情停止')
   record=save(kind,{...old,status:'CANCELLED',cancelReason:text(draft.reason)},old)
   if(run)save('IrrigationRun',{...run,status:'STOPPED'},run)
  }
 }else if(actionId.startsWith('RUN_')){
  existingFor('IrrigationRun',draft.runId);requireText(draft.reason,'reason','操作原因',actionId==='RUN_START'?6:1);reject('ADAPTER_UNAVAILABLE','尚未连接设备控制服务，未发送指令')
 }else if(actionId==='ALARM_ACK'||actionId==='ALARM_CLOSE'){
  kind='Alarm';const old=existingFor(kind,draft.alarmId)
  if(actionId==='ALARM_ACK'){
   if(old.status!=='OPEN')reject('ALARM_STATE','该告警已知悉或已关闭');requireText(draft.note,'note','知悉说明',6)
   record=save(kind,{...old,status:'ACKNOWLEDGED',acknowledgedBy:actor.userId,acknowledgedAt:stamp,handlingNote:text(draft.note)},old)
  }else{
   requireText(draft.resolution??draft.note,'resolution','结案依据',12)
   if(!['ACKNOWLEDGED','ASSIGNED'].includes(old.status)||old.recovery!=='RECOVERED')reject('ALARM_NOT_RECOVERED','告警尚未恢复或未知悉，不能关闭')
   if(entities.WorkOrder.some(w=>w.alarmId===old.alarmId&&w.status!=='COMPLETED'))reject('WORKORDER_NOT_ACCEPTED','关联工单尚未完成验收')
   record=save(kind,{...old,status:'CLOSED',closedAt:stamp,resolution:text(draft.resolution??draft.note)},old)
  }
 }else if(actionId==='WORKORDER_CREATE'){
  kind='WorkOrder';const alarm=draft.alarmId?authorize('Alarm',must('Alarm',draft.alarmId)):null
  requireEnum(draft.kind,'WorkOrderKind','kind')
  if(alarm)expected('Alarm',alarm)
  if(alarm?.status==='CLOSED')reject('ALARM_STATE','已关闭告警不能派工')
  if(alarm&&entities.WorkOrder.some(w=>w.alarmId===alarm.alarmId&&w.status!=='COMPLETED'))reject('DUPLICATE_WORKORDER','该告警已有未完成工单')
  const assignee=validSameFarm('User',draft.assigneeId);if(assignee.role!=='TECHNICIAN'||assignee.status!=='ENABLED')reject('VALIDATION','责任人须为启用的巡检维护人员',{assigneeId:'请选择启用的巡检维护人员'})
  const zoneId=alarm?.zoneId??draft.zoneId,deviceId=alarm?.deviceId??draft.deviceId
  if(!zoneId&&!deviceId)reject('VALIDATION','请至少选择一个设备或分区')
  if(zoneId)authorize('IrrigationZone',validSameFarm('IrrigationZone',zoneId));if(deviceId)authorize('Device',validSameFarm('Device',deviceId))
  if(!Number.isFinite(Date.parse(draft.dueAt))||Date.parse(draft.dueAt)<=Date.parse(now))reject('VALIDATION','期限须晚于当前时间',{dueAt:'期限须晚于当前时间'})
  requireText(noteOf(),'note','工单说明');requireText(draft.kind,'kind','工单类型')
  record=save(kind,{...draft,farmId:actor.farmId,alarmId:alarm?.alarmId??null,zoneId,deviceId,status:'ASSIGNED',requestNote:noteOf(),resultNote:null,startedAt:null,completedAt:null,acceptedBy:null})
  if(alarm)save('Alarm',{...alarm,status:'ASSIGNED'},alarm)
 }else if(actionId.startsWith('WORKORDER_')){
  kind='WorkOrder';const old=existingFor(kind,draft.workOrderId)
  if(actionId==='WORKORDER_ACCEPT'){
   if(!['ASSIGNED','RETURNED'].includes(old.status))reject('WORKORDER_STATE','当前工单不能接单')
   record=save(kind,{...old,status:'IN_PROGRESS',startedAt:old.startedAt??stamp},old)
  }else if(actionId==='WORKORDER_SUBMIT'){
   if(!['IN_PROGRESS','RETURNED'].includes(old.status))reject('WORKORDER_STATE','当前工单不能提交结果');requireText(draft.resultNote??draft.note,'resultNote','处理结果',12)
   record=save(kind,{...old,status:'PENDING_ACCEPTANCE',resultNote:text(draft.resultNote??draft.note)},old)
  }else{
   if(old.status!=='PENDING_ACCEPTANCE')reject('WORKORDER_STATE','仅待验收工单可执行此操作')
   requireText(draft.note,'note',actionId==='WORKORDER_RETURN'?'退回理由':'验收说明',actionId==='WORKORDER_RETURN'?6:1)
   if(actionId==='WORKORDER_APPROVE'){
    const alarm=old.alarmId?must('Alarm',old.alarmId):null;if(alarm&&alarm.recovery!=='RECOVERED')reject('ALARM_NOT_RECOVERED','关联故障尚未恢复，不能通过验收')
    record=save(kind,{...old,status:'COMPLETED',acceptedBy:actor.userId,completedAt:stamp,reviewNote:text(draft.note)},old)
   }else record=save(kind,{...old,status:'RETURNED',reviewNote:text(draft.note)},old)
  }
 }else if(actionId.startsWith('USER_')){
  kind='User';const old=actionId==='USER_CREATE'?null:existingFor(kind,draft.userId)
  if(actionId==='USER_DISABLE'||actionId==='USER_ENABLE'){
   if(actionId==='USER_DISABLE'){
    if(old.userId===actor.userId)reject('CURRENT_USER','不能停用当前登录账号本人');requireText(draft.reason,'reason','停用原因',6)
    if(old.role==='ADMIN'&&entities.User.filter(u=>u.farmId===actor.farmId&&u.role==='ADMIN'&&u.status==='ENABLED').length<=1)reject('LAST_ADMIN','不能停用最后一名启用管理员')
   }
   record=save(kind,{...old,status:actionId==='USER_DISABLE'?'DISABLED':'ENABLED'},old)
  }else{
   requireText(draft.account,'account','账号');requireText(draft.name,'name','姓名')
   if(!/^1\d{10}$/.test(draft.phone??''))reject('VALIDATION','联系电话须为11位有效手机号',{phone:'联系电话须为11位有效手机号'})
   if(!['ADMIN','MANAGER','OPERATOR','TECHNICIAN','VIEWER'].includes(draft.role))reject('VALIDATION','请选择有效角色')
   if(entities.User.some(u=>u.userId!==old?.userId&&u.account===text(draft.account)))reject('VALIDATION','账号已存在',{account:'账号已存在'})
   if(!Array.isArray(draft.fieldIds))reject('VALIDATION','请设置田块授权范围');for(const id of draft.fieldIds)validSameFarm('Field',id)
   if(old?.role==='ADMIN'&&old.status==='ENABLED'&&draft.role!=='ADMIN'&&entities.User.filter(u=>u.farmId===actor.farmId&&u.role==='ADMIN'&&u.status==='ENABLED').length<=1)reject('LAST_ADMIN','不能移除最后一名启用管理员')
   record=save(kind,{account:text(draft.account),name:text(draft.name),phone:draft.phone,role:draft.role,fieldIds:[...new Set(draft.fieldIds)],status:old?.status??'ENABLED',farmId:actor.farmId},old)
  }
 }else if(actionId==='POLICY_SAVE'){
  kind='SystemPolicy';const old=existingFor(kind,draft.policyId)
  for(const key of ['defaultStaleSec','commandAckTimeoutSec','actionConfirmTimeoutSec','maxScheduleDays'])if(!Number.isSafeInteger(draft[key])||draft[key]<=0)reject('VALIDATION','运行参数须为正整数',{[key]:'请输入正整数'})
  if(draft.actionConfirmTimeoutSec<draft.commandAckTimeoutSec)reject('VALIDATION','动作确认时限不得小于通信应答时限',{actionConfirmTimeoutSec:'动作确认时限不得小于通信应答时限'})
  if(entities.CommandOutbox.some(c=>['PENDING','SENT','ACKNOWLEDGED','UNKNOWN'].includes(c.status)))reject('ACTIVE_REFERENCE','存在受影响未决指令，暂不能修改运行参数')
  record=save(kind,{...old,...Object.fromEntries(['defaultStaleSec','commandAckTimeoutSec','actionConfirmTimeoutSec','maxScheduleDays'].map(k=>[k,draft[k]]))},old)
 }else reject('ACTION_UNSUPPORTED','此业务操作尚无有效入口')
 const entityId=record?.[primaryKeys[kind]]
 const audit={auditId:createEntityId('AuditLog'),farmId:actor.farmId,actorId:actor.userId,actionId,entityType:kind,entityId,beforeVersion:record?.version>1?record.version-1:null,afterVersion:record?.version??1,occurredAt:stamp,correlationId:options.clientRequestId,result:'SUCCESS',detail:{note:noteOf()||text(draft.resultNote??draft.resolution),changedEntities:changes}}
 entities.AuditLog.push(audit);changes.push({entityType:'AuditLog',entityId:audit.auditId,version:1})
 return {entityId,version:record?.version??1,changedEntities:changes,result}
}
