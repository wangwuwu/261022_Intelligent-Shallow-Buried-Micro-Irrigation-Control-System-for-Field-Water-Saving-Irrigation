import {primaryKeys,reject,activeRunStatuses} from './contracts.js'
import {buildIrrigationIndex,projectWaterAccounting,assessMoistureTrigger} from '../domain/irrigation.js'
import {assessPlanDraft} from './actions.js'
export function effectiveDeviceConnection(device,now=new Date()){
 if(device.connection!=='ONLINE')return device.connection??'UNKNOWN'
 const age=(Date.parse(now)-Date.parse(device.lastSeenAt))/1000
 return Number.isFinite(age)&&age>=0&&age<=(device.heartbeatTimeoutSec??120)?'ONLINE':'OFFLINE'
}
const aliases={fields:'Field',devices:'Device',strategies:'Strategy',plans:'Plan',runs:'IrrigationRun',alarms:'Alarm',workOrders:'WorkOrder',users:'User',audit:'AuditLog',readings:'TelemetryReading',zones:'IrrigationZone',exports:'ExportJob'}
export function queryIrrigationFacts(entities,revision,user,name,params={},clock=new Date()){
 if(name==='publicFarm')return {entity:entities.Farm?.[0]??null,revision}
 if(!user)reject('UNAUTHENTICATED','请先登录')
 const index=buildIrrigationIndex(entities,revision)
 if(name==='overview'||name==='OVERVIEW'){
  const asOf=params.asOf??clock,date=params.date??new Date(Date.parse(clock)+8*3600000).toISOString().slice(0,10)
  const water=projectWaterAccounting(index,{start:date,end:date}),devices=entities.Device.filter(d=>d.status==='ENABLED'),online=devices.filter(d=>effectiveDeviceConnection(d,asOf)==='ONLINE').length
  const activeRuns=entities.IrrigationRun.filter(r=>activeRunStatuses.has(r.status)),queuedRuns=entities.IrrigationRun.filter(r=>r.status==='QUEUED'),alarms=entities.Alarm.filter(a=>a.status!=='CLOSED').sort((a,b)=>Date.parse(b.openedAt)-Date.parse(a.openedAt))
  return {revision,date,fieldAreaMu:Math.round(entities.Field.reduce((n,f)=>n+f.areaMu,0)*10)/10,runningCount:activeRuns.length,settledWaterM3:water.totalM3,pendingAlarmCount:alarms.length,offlineDeviceCount:devices.filter(d=>effectiveDeviceConnection(d,asOf)==='OFFLINE').length,deviceOnlineRate:devices.length?Number((online/devices.length*100).toFixed(2)):null,activeRuns,queuedRuns,alarmSummary:alarms[0]??null}
 }
 if(name==='water'||name==='waterReport'||name==='WATER_REPORT')return {...projectWaterAccounting(index,params.filters??params),revision}
 if(['resources','planResources','PLAN_RESOURCES','QUERY_PLAN_CONFLICTS'].includes(name))return {...assessPlanDraft(entities,params.draft??params.planDraft??params,clock),revision}
 if(['simulation','strategySimulation','QUERY_STRATEGY_SIMULATE'].includes(name)){
  const strategy=entities.Strategy.find(x=>x.strategyId===params.strategyId);if(!strategy)reject('NOT_FOUND','策略不存在')
  const asOf=params.asOf??clock;if(Date.parse(asOf)>Date.parse(clock))reject('VALIDATION','试算时刻不能晚于当前时间')
  return {strategyId:strategy.strategyId,asOf,zoneAssessments:assessMoistureTrigger(index,strategy,asOf,{representativePointByZone:params.representativePointByZone??{}}),revision}
 }
 if(name==='exportFile'){
  const job=entities.ExportJob.find(x=>x.exportId===params.exportId);if(!job)reject('NOT_FOUND','导出任务不存在')
  if(job.status!=='READY'||!job.csvContent||Date.parse(job.expiresAt)<=Date.parse(clock))reject('EXPORT_UNAVAILABLE','原文件不可恢复或已过期，请重新导出')
  return {fileName:job.fileName,content:job.csvContent,checksum:job.checksum,revision}
 }
 const kind=aliases[name]??name;if(!primaryKeys[kind])reject('QUERY_UNSUPPORTED','查询名称无效')
 if(kind==='User'&&user.role!=='ADMIN')reject('FORBIDDEN','无权读取账号管理列表')
 if(kind==='AuditLog'&&!['ADMIN','MANAGER'].includes(user.role))reject('FORBIDDEN','无权读取操作审计')
 let items=[...(entities[kind]??[])]
 const filters=params.filters??params
 if(params.id){const entity=items.find(x=>x[primaryKeys[kind]]===params.id);if(!entity)reject('NOT_FOUND','记录不存在');return {entity,related:entities,revision}}
 if(kind==='Device')items=items.map(x=>({...x,connection:effectiveDeviceConnection(x,params.asOf??clock)}))
 items=items.filter(row=>Object.entries(filters).every(([key,value])=>{
  if(value===undefined||value===null||value===''||value==='ALL'||['page','pageSize','sortBy','sortDirection','asOf','start','end','id'].includes(key))return true
  if(key==='search')return `${row.name??''} ${row.code??''} ${row[primaryKeys[kind]]??''}`.toLowerCase().includes(String(value).trim().toLowerCase())
  if(key==='name'||key==='code')return String(row[key]??'').toLowerCase().includes(String(value).trim().toLowerCase())
  return row[key]===value
 }))
 if(filters.start||filters.end){const start=filters.start?Date.parse(`${filters.start}T00:00:00+08:00`):-Infinity;const until=filters.end?Date.parse(`${filters.end}T00:00:00+08:00`)+86400000:Infinity;items=items.filter(row=>{const at=Date.parse(row.observedAt??row.occurredAt??row.scheduledAt??row.openedAt??row.createdAt);return at>=start&&at<until})}
 const summary={total:items.length,enabled:items.filter(x=>x.status==='ENABLED').length,disabled:items.filter(x=>x.status==='DISABLED').length,areaMu:items.reduce((n,x)=>n+(x.areaMu??0),0),online:items.filter(x=>x.connection==='ONLINE').length,offline:items.filter(x=>x.connection==='OFFLINE').length,verified:items.filter(x=>x.verification==='VERIFIED').length}
 if(params.sortBy){const direction=params.sortDirection==='desc'?-1:1;const key=params.sortBy;items.sort((a,b)=>((typeof a[key]==='number'&&typeof b[key]==='number')?a[key]-b[key]:String(a[key]??'').localeCompare(String(b[key]??''),'zh-CN'))*direction||String(a[primaryKeys[kind]]).localeCompare(String(b[primaryKeys[kind]])))}
 const pageSize=Math.min(100,Math.max(1,Number(params.pageSize)||15)),total=items.length,page=Math.min(Math.max(1,Number(params.page)||1),Math.max(1,Math.ceil(total/pageSize)))
 return {items:items.slice((page-1)*pageSize,page*pageSize),total,page,pageSize,revision,summary}
}
