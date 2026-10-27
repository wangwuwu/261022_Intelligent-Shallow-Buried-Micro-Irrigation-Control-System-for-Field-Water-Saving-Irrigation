import {primaryKeys,cloneFacts,reject,IrrigationError} from './contracts.js'
import {verifyPreviewPassword} from './auth.js'
import {scopeIrrigationFacts,canOperate} from './permissions.js'
import {buildIrrigationIndex,projectWaterAccounting} from '../domain/irrigation.js'
import {applyIrrigationAction,createEntityId,assessPlanDraft,redactResourceAssessment} from './actions.js'
import {queryIrrigationFacts} from './queries.js'

export function createIrrigationRepository({seed,credentials={},storage=globalThis.localStorage,sessionStorage=globalThis.sessionStorage,lock,clock=()=>new Date(),reactive=value=>value,storageKey='irrigation.preview.snapshot.v1',sessionKey='irrigation.preview.session.v1',channel='preview',schedule=globalThis.setTimeout,cancelSchedule=globalThis.clearTimeout}={}){
 const empty=()=>Object.fromEntries(Object.keys(primaryKeys).map(k=>[k,[]]))
 const initial=cloneFacts({...empty(),...seed,Session:[]})
 const state=reactive({entities:empty(),revision:0,user:null,publicFarm:initial.Farm[0]?{name:initial.Farm[0].name,farmId:initial.Farm[0].farmId}:null,ready:false,error:null,channel,readOnly:!lock&&!globalThis.navigator?.locks})
 let snapshot={schemaVersion:1,revision:0,entities:initial,requests:{},committedAt:null};let session=null,indexCache=null,indexRevision=-1,expiryTimer=null
 const subscribers=new Set();const useLock=lock??(callback=>globalThis.navigator?.locks?globalThis.navigator.locks.request(storageKey,{mode:'exclusive'},callback):Promise.reject(new IrrigationError('STORAGE_READ_ONLY','当前浏览器缺少安全的本机写入锁，请使用localhost或HTTPS下的受支持浏览器')))
 const parseSnapshot=raw=>{
  if(!raw)return {schemaVersion:1,revision:0,entities:cloneFacts(initial),requests:{},committedAt:null}
  let parsed;try{parsed=JSON.parse(raw)}catch{reject('STORAGE_CORRUPT','本机数据已损坏，原始内容已保留，请备份后恢复')}
  if(parsed.schemaVersion!==1||!Number.isSafeInteger(parsed.revision)||!parsed.entities)reject('STORAGE_SCHEMA','本机数据版本无法读取，原始内容已保留')
  for(const [kind,key]of Object.entries(primaryKeys)){
   const rows=parsed.entities[kind];if(!Array.isArray(rows))reject('STORAGE_CORRUPT',`${kind} 数据集合损坏`)
   const seen=new Set();for(const row of rows){if(!row||!row[key]||seen.has(row[key]))reject('STORAGE_CORRUPT',`${kind} 编号缺失或重复`);seen.add(row[key])}
  }
  parsed.requests??={};return parsed
 }
 const readLatest=()=>{try{return parseSnapshot(storage.getItem(storageKey))}catch(error){if(error instanceof IrrigationError)throw error;reject('STORAGE_UNAVAILABLE','无法读取本机存储，未载入替代数据')}}
 const persist=next=>{try{storage.setItem(storageKey,JSON.stringify(next))}catch{reject('STORAGE_FAILED','本机存储保存失败，原数据与草稿保持不变')}}
 const clearSession=()=>{if(expiryTimer!==null)cancelSchedule(expiryTimer);expiryTimer=null;session=null;try{sessionStorage?.removeItem(sessionKey)}catch{} }
 const saveSession=()=>{try{if(session)sessionStorage?.setItem(sessionKey,JSON.stringify(session))}catch{} }
 const actorFor=(facts=snapshot)=>{
  if(!session||!Number.isFinite(Date.parse(session.expiresAt))||Date.parse(session.expiresAt)<=Date.parse(clock()))return null
  const user=facts.entities.User.find(x=>x.userId===session.userId)
  return user&&user.status==='ENABLED'&&user.version===session.userVersion?user:null
 }
 const notify=(changes,authChanged=false)=>{for(const listener of subscribers)try{listener({revision:state.revision,changedEntities:changes,authChanged})}catch(error){console.error('仓储订阅回调异常',error?.message)}}
 const publish=(next,changes=[])=>{
  const previousUser=state.user;snapshot=next;const actor=actorFor(next);if(session&&!actor)clearSession()
  state.user=actor?cloneFacts(actor):null;state.entities=scopeIrrigationFacts(next.entities,actor);state.revision=next.revision;indexCache=null;indexRevision=-1;armSessionExpiry();notify(changes,previousUser?.userId!==state.user?.userId||previousUser?.version!==state.user?.version)
 }
 function armSessionExpiry(){
  if(expiryTimer!==null)cancelSchedule(expiryTimer);expiryTimer=null
  if(!session)return
  const delay=Math.max(0,Date.parse(session.expiresAt)-Date.parse(clock()))
  expiryTimer=schedule(()=>{expiryTimer=null;if(checkSession())armSessionExpiry()},Math.min(delay,2147483647));expiryTimer?.unref?.()
 }
 function checkSession(){if((session||state.user)&&!actorFor()){clearSession();publish(snapshot)}return !!state.user}
 async function exportCorruptSnapshot(){
  let content;try{content=storage.getItem(storageKey)}catch{reject('STORAGE_UNAVAILABLE','无法读取本机存储，不能生成备份')}
  try{parseSnapshot(content)}catch(error){if(['STORAGE_CORRUPT','STORAGE_SCHEMA'].includes(error.code))return {fileName:`irrigation-corrupt-${Date.parse(clock())}.json`,content};throw error}
  reject('RECOVERY_NOT_REQUIRED','当前本机数据可以正常读取，无需损坏恢复')
 }
 async function recoverInitialSnapshot({confirmed=false}={}){
  if(confirmed!==true)reject('CONFIRMATION_REQUIRED','恢复将替换本机业务数据，请先备份损坏快照并明确确认')
  return useLock(async()=>{
   await exportCorruptSnapshot()
   const next=parseSnapshot(null);persist(next);clearSession();publish(next);state.error=null;state.ready=true;return state
  })
 }
 async function load(){
  try{
   snapshot=readLatest();try{session=JSON.parse(sessionStorage?.getItem(sessionKey)??'null')}catch{clearSession()}
   publish(snapshot);state.error=null
  }catch(error){state.error=error;clearSession();publish(snapshot);state.entities=empty()}
  state.ready=true;return state
 }
 async function login(account,password){
  if(!String(account??'').trim()||!password)reject('VALIDATION','请输入账号和密码',{account:!String(account??'').trim()?'账号必填':undefined,password:!password?'密码必填':undefined})
  const current=readLatest(),user=current.entities.User.find(x=>x.account===String(account).trim())
  const verified=await verifyPreviewPassword(password,credentials[String(account).trim()])
  if(!verified||!user||user.status!=='ENABLED')reject('AUTH_FAILED','账号或密码错误，或账号已停用')
  session={sessionId:crypto.randomUUID(),userId:user.userId,userVersion:user.version,expiresAt:new Date(Date.parse(clock())+8*3600000).toISOString()};saveSession();publish(current);state.error=null;return cloneFacts(user)
 }
 async function logout(){clearSession();publish(snapshot)}
 async function refresh(){checkSession();const next=readLatest();if(next.revision!==snapshot.revision||actorFor(next)?.version!==state.user?.version)publish(next);return state}
 const can=(actionId,entity)=>{checkSession();return canOperate(actorFor(),actionId,entity,snapshot.entities)}
 const getIndex=()=>{checkSession();if(!indexCache||indexRevision!==state.revision){indexCache=buildIrrigationIndex(state.entities,state.revision);indexRevision=state.revision}return indexCache}
 async function query(name,params={},options={}){
  if(options.signal?.aborted)throw new DOMException('读取已取消','AbortError')
  await refresh();if(name==='publicFarm')return {entity:state.publicFarm,revision:state.revision}
  if(['resources','planResources','PLAN_RESOURCES','QUERY_PLAN_CONFLICTS'].includes(name)){
   const actor=actorFor();if(!actor||!canOperate(actor,'PLAN_CREATE',null,snapshot.entities))reject('FORBIDDEN','无权检查轮灌编排资源')
   const draft=cloneFacts(params.draft??params.planDraft??params)
   if(draft.farmId&&draft.farmId!==actor.farmId)reject('FORBIDDEN','计划不属于当前农场')
   draft.farmId=actor.farmId
   for(const step of draft.steps??[]){const zone=snapshot.entities.IrrigationZone.find(z=>z.zoneId===step.zoneId);if(!zone||!canOperate(actor,'PLAN_CREATE',zone,snapshot.entities))reject('FORBIDDEN','无权检查该轮灌分区')}
   const assessment=redactResourceAssessment(assessPlanDraft(snapshot.entities,draft,clock()),snapshot.entities,actor)
   return {...assessment,revision:state.revision}
  }
  return queryIrrigationFacts(state.entities,state.revision,state.user,name,params,clock())
 }
 const csvCell=value=>{let v=String(value??'');if(/^[=+@\-\t\r]/.test(v))v=`'${v}`;return `"${v.replaceAll('"','""')}"`}
 function createExport(current,actor,payload,options){
  const filters=cloneFacts(payload.filterSnapshot??payload.filters??{}),now=new Date(clock()).toISOString()
  if(filters.startAt&&!filters.start)filters.start=filters.startAt.slice(0,10)
  if(filters.endAt&&!filters.end)filters.end=new Date(Date.parse(filters.endAt)-1).toISOString().slice(0,10)
  if(filters.start&&filters.end&&(Date.parse(filters.end)-Date.parse(filters.start))/86400000>365)reject('EXPORT_WINDOW','导出区间不能超过366天')
  const rows=projectWaterAccounting(buildIrrigationIndex(scopeIrrigationFacts(current.entities,actor)),filters).rows.map(row=>({ledgerId:row.ledgerId,fieldId:row.fieldId,fieldName:row.fieldName,endedAt:row.endedAt,volumeM3:row.volumeM3,method:row.method,qualityStatus:row.qualityStatus}))
  const job={exportId:createEntityId('ExportJob'),farmId:actor.farmId,createdBy:actor.userId,filterSnapshot:filters,sourceRevision:current.revision,status:'QUEUED',fileName:`用水明细_${new Date(clock()).toISOString().slice(0,10).replaceAll('-','')}.csv`,rowCount:rows.length,processedRows:0,progress:0,rowsSnapshot:rows,csvContent:null,checksum:null,downloadUrl:null,expiresAt:new Date(Date.parse(clock())+86400000).toISOString(),createdAt:now,updatedAt:now,version:1}
  job.authorizedFieldIds=[...new Set(rows.map(x=>x.fieldId))];current.entities.ExportJob.push(job)
  return {entityId:job.exportId,version:1,changedEntities:[{entityType:'ExportJob',entityId:job.exportId,version:1}],result:{exportId:job.exportId}}
 }
 function cancelExport(current,actor,payload,options){
  const job=current.entities.ExportJob.find(x=>x.exportId===payload.exportId)
  if(!job)reject('NOT_FOUND','导出任务不存在')
  if(job.farmId!==actor.farmId)reject('FORBIDDEN','无权取消此农场的导出任务')
  if(job.createdBy!==actor.userId&&actor.role!=='ADMIN')reject('FORBIDDEN','无权取消此任务')
  if(!['QUEUED','PROCESSING'].includes(job.status))reject('EXPORT_STATE','当前导出任务不能取消')
  if(options.expectedVersion!==undefined&&Number(options.expectedVersion)!==job.version)reject('VERSION_CONFLICT','导出任务已更新，请重试取消')
  Object.assign(job,{status:'CANCELLED',csvContent:null,rowsSnapshot:[],updatedAt:new Date(clock()).toISOString(),version:job.version+1})
  return {entityId:job.exportId,version:job.version,changedEntities:[{entityType:'ExportJob',entityId:job.exportId,version:job.version}],result:{exportId:job.exportId}}
 }
 async function commit(actionId,submittedPayload={},options={}){
  const payload=cloneFacts(submittedPayload)
  const request={...options,clientRequestId:options.clientRequestId??crypto.randomUUID()}
  const response=await useLock(async()=>{
   const current=readLatest(),actor=actorFor(current)
   if(!actor){clearSession();publish(current);reject('UNAUTHENTICATED','会话已失效，请重新登录')}
   if(!canOperate(actor,actionId,null,current.entities))reject('FORBIDDEN','无权执行此操作')
   const replayKey=`${actor.userId}:${actionId}:${request.clientRequestId}`,requestBody=JSON.stringify(payload),previous=current.requests[replayKey]
   if(previous){if(previous.requestBody!==requestBody)reject('IDEMPOTENCY_CONFLICT','同一请求编号不能提交不同内容');publish(current);return {...previous.response,replayed:true}}
   const next=cloneFacts(current);let applied
   if(actionId==='EXPORT_CREATE')applied=createExport(next,actor,payload,request)
   else if(actionId==='EXPORT_CANCEL')applied=cancelExport(next,actor,payload,request)
   else applied=applyIrrigationAction(next.entities,actor,actionId,payload,request,clock())
   if(actionId.startsWith('EXPORT_')){
    const audit={auditId:createEntityId('AuditLog'),farmId:actor.farmId,actorId:actor.userId,actionId,entityType:'ExportJob',entityId:applied.entityId,beforeVersion:null,afterVersion:applied.version,occurredAt:new Date(clock()).toISOString(),correlationId:request.clientRequestId,result:'SUCCESS',detail:{}}
    next.entities.AuditLog.push(audit);applied.changedEntities.push({entityType:'AuditLog',entityId:audit.auditId,version:1})
   }
   next.revision=current.revision+1;next.committedAt=new Date(clock()).toISOString()
   const result={...applied,revision:next.revision,replayed:false};next.requests[replayKey]={requestBody,response:result}
   parseSnapshot(JSON.stringify(next));persist(next)
   if(applied.result.refreshActor){session.userVersion=next.entities.User.find(x=>x.userId===actor.userId).version;saveSession()}
   publish(next,applied.changedEntities);return result
  })
  if(actionId==='EXPORT_CREATE'&&!response.replayed)queueMicrotask(()=>generateExport(response.entityId).catch(error=>{state.error=error}))
  return response
 }
 async function updateExport(exportId,transform){return useLock(async()=>{
  const current=readLatest(),next=cloneFacts(current),job=next.entities.ExportJob.find(x=>x.exportId===exportId)
  if(!job||!['QUEUED','PROCESSING'].includes(job.status))return null
  const creator=next.entities.User.find(x=>x.userId===job.createdBy)
  if(!creator||creator.status!=='ENABLED'){Object.assign(job,{status:'FAILED',failureReason:'导出账号已停用',rowsSnapshot:[],csvContent:null})}else transform(job)
  job.version++;job.updatedAt=new Date(clock()).toISOString();next.revision++;persist(next);publish(next,[{entityType:'ExportJob',entityId:job.exportId,version:job.version}]);return cloneFacts(job)
 })}
 async function generateExport(exportId){
  let job=await updateExport(exportId,j=>{j.status='PROCESSING'})
  if(!job||job.status!=='PROCESSING')return
  const lines=['账本编号,田块,日期,水量 m³,计量方式,状态'];const method={MEASURED:'实测',ALLOCATED:'分摊',ESTIMATED:'估算'}
  try{
   for(let offset=0;offset<job.rowsSnapshot.length;offset+=10){
    const rows=job.rowsSnapshot.slice(offset,offset+10)
    for(const row of rows)lines.push([row.ledgerId,row.fieldName,new Date(Date.parse(row.endedAt)+8*3600000).toISOString().slice(0,10),row.volumeM3,method[row.method]??row.method,'已结算'].map(csvCell).join(','))
    job=await updateExport(exportId,j=>{j.processedRows=Math.min(offset+rows.length,j.rowCount);j.progress=j.rowCount?Math.floor(j.processedRows/j.rowCount*100):100})
    if(!job||job.status!=='PROCESSING')return
    await new Promise(resolve=>setTimeout(resolve,0))
   }
   const csvContent='\uFEFF'+lines.join('\r\n'),bytes=new TextEncoder().encode(csvContent),checksum=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('')
   await updateExport(exportId,j=>{Object.assign(j,{status:'READY',progress:100,csvContent,checksum,rowsSnapshot:[],byteLength:bytes.byteLength})})
  }catch(error){await updateExport(exportId,j=>{Object.assign(j,{status:'FAILED',failureReason:error.message,rowsSnapshot:[],csvContent:null})})}
 }
 const subscribe=listener=>{subscribers.add(listener);return()=>subscribers.delete(listener)}
 if(globalThis.addEventListener)globalThis.addEventListener('storage',event=>{if(event.key===storageKey)refresh().catch(error=>{state.error=error})})
 return {state,load,login,logout,refresh,query,commit,subscribe,can,getIndex,checkSession,exportCorruptSnapshot,recoverInitialSnapshot}
}
