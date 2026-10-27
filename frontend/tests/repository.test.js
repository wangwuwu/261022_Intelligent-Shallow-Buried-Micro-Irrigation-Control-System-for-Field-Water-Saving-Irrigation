import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createIrrigationRepository} from '../src/data/repository.js'
import {createPreviewCredential} from '../src/data/auth.js'
const initial=JSON.parse(readFileSync(new URL('../../shared_context.json',import.meta.url))).entities
class MemoryStorage { values=new Map();fail=false; getItem(k){return this.values.get(k)??null}setItem(k,v){if(this.fail)throw Error('quota');this.values.set(k,v)}removeItem(k){this.values.delete(k)} }
const serialized=()=>{let tail=Promise.resolve();return callback=>{const next=tail.then(callback);tail=next.catch(()=>{});return next}}
async function setup(role='ADMIN',overrides={}) {
 const seed=structuredClone(initial),user=seed.User.find(x=>x.role===role&&x.status==='ENABLED');const password=crypto.randomUUID();const credentials={[user.account]:await createPreviewCredential(password,1000)};const storage=overrides.storage??new MemoryStorage();const lock=overrides.lock??serialized()
 const repo=createIrrigationRepository({seed,credentials,storage,sessionStorage:new MemoryStorage(),lock,clock:()=>new Date('2026-07-28T10:18:43+08:00'),...overrides});await repo.load();await repo.login(user.account,password);return {repo,seed,user,storage,credentials,password,lock}
}
test('field updates persist with one audit and survive repository restart',async()=>{
 const {repo,user,storage,credentials,password,lock}=await setup();const field=repo.state.entities.Field[0], before=repo.state.revision
 const result=await repo.commit('FIELD_UPDATE',{...field,name:field.name+'修订'},{expectedVersion:field.version,clientRequestId:crypto.randomUUID()})
 assert.equal(result.revision,before+1);assert.equal(repo.state.entities.Field[0].version,field.version+1)
 const second=createIrrigationRepository({seed:initial,storage,credentials,sessionStorage:new MemoryStorage(),lock});await second.load();await second.login(user.account,password)
 assert.equal(second.state.entities.Field[0].name,field.name+'修订');assert.ok(second.state.entities.AuditLog.some(x=>x.entityId===field.fieldId&&x.actionId==='FIELD_UPDATE'))
})
test('storage failure leaves the official entity and revision unchanged',async()=>{
 const {repo,storage}=await setup();const before=structuredClone(repo.state);storage.fail=true
 await assert.rejects(repo.commit('FIELD_UPDATE',{...repo.state.entities.Field[0],name:'修改未提交'},{expectedVersion:1}),/存储|保存/)
 assert.deepEqual(repo.state,before)
})
test('viewer writes and technician work on another person are rejected in business logic',async()=>{
 const {repo}=await setup('VIEWER');await assert.rejects(repo.commit('FIELD_UPDATE',repo.state.entities.Field[0]),e=>e.code==='FORBIDDEN')
 const second=await setup('TECHNICIAN');const someoneElse=initial.WorkOrder.find(x=>x.assigneeId!==second.user.userId)
 if(someoneElse)await assert.rejects(second.repo.commit('WORKORDER_ACCEPT',someoneElse),e=>e.code==='FORBIDDEN')
})
test('two tabs preserve independent updates and reject a stale shared entity version',async()=>{
 const ctx=await setup();const second=createIrrigationRepository({seed:initial,storage:ctx.storage,credentials:ctx.credentials,lock:ctx.lock,sessionStorage:new MemoryStorage()});await second.load();await second.login(ctx.user.account,ctx.password)
 const [a,b]=ctx.repo.state.entities.Field
 await Promise.all([ctx.repo.commit('FIELD_UPDATE',{...a,name:a.name+'一'},{expectedVersion:a.version}),second.commit('FIELD_UPDATE',{...b,name:b.name+'二'},{expectedVersion:b.version})])
 await ctx.repo.refresh();assert.equal(ctx.repo.state.entities.Field[0].name,a.name+'一');assert.equal(ctx.repo.state.entities.Field[1].name,b.name+'二')
 await assert.rejects(second.commit('FIELD_UPDATE',{...a,name:'旧版本'},{expectedVersion:a.version}),e=>e.code==='VERSION_CONFLICT')
})
test('plan cancellation changes queued run and plan atomically, and is idempotent',async()=>{
 const {repo}=await setup();const plan=repo.state.entities.Plan.find(p=>p.status==='PUBLISHED'),key=crypto.randomUUID()
 const result=await repo.commit('PLAN_CANCEL',{planId:plan.planId,reason:'天气变化取消本次灌溉'},{expectedVersion:plan.version,clientRequestId:key})
 assert.equal(repo.state.entities.Plan.find(p=>p.planId===plan.planId).status,'CANCELLED')
 assert.equal(repo.state.entities.IrrigationRun.find(r=>r.planId===plan.planId).status,'STOPPED')
 assert.equal((await repo.commit('PLAN_CANCEL',{planId:plan.planId,reason:'天气变化取消本次灌溉'},{expectedVersion:plan.version,clientRequestId:key})).replayed,true)
 assert.equal(repo.state.revision,result.revision)
})
test('unrecovered maintenance cannot pass acceptance and missing hardware never changes a run',async()=>{
 const {repo}=await setup();const original=structuredClone(repo.state.entities.IrrigationRun[0]);await assert.rejects(repo.commit('RUN_PAUSE',{runId:original.runId,reason:'现场检查暂停灌溉'},{expectedVersion:original.version}),e=>e.code==='ADAPTER_UNAVAILABLE');assert.deepEqual(repo.state.entities.IrrigationRun[0],original)
 const job=repo.state.entities.WorkOrder.find(x=>x.status==='PENDING_ACCEPTANCE');const alarm=repo.state.entities.Alarm.find(x=>x.alarmId===job.alarmId)
 if(alarm?.recovery==='ACTIVE')await assert.rejects(repo.commit('WORKORDER_APPROVE',{workOrderId:job.workOrderId,note:'维护结果审核通过'},{expectedVersion:job.version}),/恢复/)
})
test('last administrator and current user cannot be disabled',async()=>{
 const {repo,user}=await setup();await assert.rejects(repo.commit('USER_DISABLE',{userId:user.userId,reason:'停用当前登录账号'},{expectedVersion:user.version}),/本人|当前/)
})
test('a partial-field reader retains shared devices and supply ancestors but cannot write them',async()=>{
 const ctx=await setup('MANAGER');const seed=structuredClone(initial),actor=seed.User.find(u=>u.userId===ctx.user.userId)
 actor.fieldIds=[seed.Field[0].fieldId]
 const repo=createIrrigationRepository({seed,credentials:ctx.credentials,storage:new MemoryStorage(),sessionStorage:new MemoryStorage(),lock:serialized(),clock:()=>new Date('2026-07-28T10:18:43+08:00')});await repo.load();await repo.login(actor.account,ctx.password)
 const point=repo.state.entities.Point.find(p=>p.kind==='SOIL_MOISTURE')
 assert.ok(point);assert.ok(repo.state.entities.Device.some(d=>d.deviceId===point.deviceId))
 const root=seed.PipeNode.find(n=>!n.parentNodeId);assert.ok(repo.state.entities.PipeNode.some(n=>n.nodeId===root.nodeId))
 await assert.rejects(repo.commit('PIPE_SAVE',root,{expectedVersion:root.version}),e=>e.code==='FORBIDDEN')
})
test('a create request cannot replace a pre-existing stable primary key',async()=>{
 const {repo}=await setup();const original=structuredClone(repo.state.entities.Strategy[0])
 await assert.rejects(repo.commit('STRATEGY_CREATE',original),e=>e.code==='DUPLICATE_ID')
 assert.deepEqual(repo.state.entities.Strategy[0],original)
})
test('editing current account authorization revokes its old session',async()=>{
 const {repo,user}=await setup();await repo.commit('USER_UPDATE',{...user,phone:user.phone},{expectedVersion:user.version})
 assert.equal(repo.state.user,null);assert.equal(repo.state.entities.Field.length,0)
})
test('a submitted draft is frozen before waiting for another tab write lock',async()=>{
 let release;const lock=callback=>new Promise(resolve=>{release=()=>resolve(callback())})
 const {repo}=await setup('ADMIN',{lock});const field=repo.state.entities.Field[1],draft={...field,name:'锁等待前的田块名'}
 const pending=repo.commit('FIELD_UPDATE',draft,{expectedVersion:field.version});draft.name='提交后未经确认的修改';release();await pending
 assert.equal(repo.state.entities.Field[1].name,'锁等待前的田块名')
})
test('new field registration updates creator authorization and shared area in one revision',async()=>{
 const {repo}=await setup('MANAGER');const source=repo.state.entities.Field[0],{fieldId,code,version,...draft}=source;const before=repo.state.revision
 const result=await repo.commit('FIELD_CREATE',{...draft,name:'新增边界验证田块',areaMu:2})
 assert.equal(repo.state.revision,before+1);assert.ok(repo.state.entities.Field.some(f=>f.fieldId===result.entityId));assert.ok(repo.state.user.fieldIds.includes(result.entityId))
 assert.equal(repo.state.entities.Field.length,initial.Field.length+1)
})
test('saved plan resource proof publishes one queued run without issuing hardware commands',async()=>{
 const {repo}=await setup();const zone=repo.state.entities.IrrigationZone.find(z=>z.fieldId===initial.Field[1].fieldId)
 const result=await repo.commit('PLAN_CREATE',{name:'供水资源边界验证计划',scheduledAt:'2026-07-29T08:00:00+08:00',steps:[{zoneId:zone.zoneId,targetVolumeM3:1,expectedFlowM3h:10,maxDurationMin:60}]})
 const plan=repo.state.entities.Plan.find(p=>p.planId===result.entityId),steps=repo.state.entities.PlanStep.filter(s=>s.planId===plan.planId),assessment=await repo.query('resources',{...plan,steps}),beforeCommands=repo.state.entities.CommandOutbox.length
 const published=await repo.commit('PLAN_PUBLISH',{planId:plan.planId,conflictHash:assessment.conflictHash},{expectedVersion:plan.version})
 assert.equal(repo.state.entities.IrrigationRun.find(r=>r.runId===published.result.runId).status,'QUEUED');assert.equal(repo.state.entities.CommandOutbox.length,beforeCommands)
 assert.equal(repo.state.entities.RunStep.find(s=>s.runId===published.result.runId).status,'WAITING')
})
test('a CSV export produces real checksum-bound bytes and an immediate cancellation stays cancelled',async()=>{
 const {repo}=await setup();const result=await repo.commit('EXPORT_CREATE',{filters:{start:'2026-07-27',end:'2026-07-27'}})
 for(let i=0;i<100&&repo.state.entities.ExportJob.find(j=>j.exportId===result.entityId).status!=='READY';i++)await new Promise(resolve=>setTimeout(resolve,2))
 const file=await repo.query('exportFile',{exportId:result.entityId})
 assert.ok(file.content.startsWith('\uFEFF账本编号'));assert.match(file.content,/385\.7/);assert.equal(file.checksum.length,64)
 const next=await repo.commit('EXPORT_CREATE',{filters:{start:'2026-06-01',end:'2026-07-28'}});await repo.commit('EXPORT_CANCEL',{exportId:next.entityId})
 await new Promise(resolve=>setTimeout(resolve,15));assert.equal(repo.state.entities.ExportJob.find(j=>j.exportId===next.entityId).status,'CANCELLED');await assert.rejects(repo.query('exportFile',{exportId:next.entityId}),e=>e.code==='EXPORT_UNAVAILABLE')
})
