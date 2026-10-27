import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildIrrigationIndex, assessMoistureTrigger, validateFieldFacts, effectiveWaterLedger, assessRotationResources } from '../src/domain/irrigation.js'
const initial = JSON.parse(readFileSync(new URL('../../shared_context.json', import.meta.url))).entities
test('SCHEDULE is the source-contract trigger and TIME is rejected',()=>{
 const e=structuredClone(initial);const s={...e.Strategy[0],triggerMode:'SCHEDULE'};const index=buildIrrigationIndex(e)
 assert.equal(assessMoistureTrigger(index,s,new Date('2026-07-28T10:18:43+08:00'))[0].eligible,true)
 s.triggerMode='TIME';assert.equal(assessMoistureTrigger(index,s,new Date('2026-07-28T10:18:43+08:00'))[0].eligible,false)
})
test('soil type must use an established source option',()=>{
 const index=buildIrrigationIndex(initial)
 assert.match(validateFieldFacts(index,{...initial.Field[0],soilType:''}).soilType,/土壤/)
 assert.match(validateFieldFacts(index,{...initial.Field[0],soilType:'unknown'}).soilType,/土壤/)
})
test('final water revision branches and cycles are rejected',()=>{
 const source=initial.WaterLedger[0]
 assert.throws(()=>effectiveWaterLedger([source,{...source,ledgerId:'a',revisionOf:source.ledgerId},{...source,ledgerId:'b',revisionOf:source.ledgerId}]),/修订/)
 assert.throws(()=>effectiveWaterLedger([{...source,ledgerId:'a',revisionOf:'b'},{...source,ledgerId:'b',revisionOf:'a'}]),/修订/)
})
test('an unfinished actual run continues to reserve its valve after planned ending',()=>{
 const e=structuredClone(initial);e.Plan=[];e.PlanStep=[]
 const z=e.IrrigationZone[0];const result=assessRotationResources(buildIrrigationIndex(e),{scheduledAt:'2026-07-30T07:00:00+08:00',steps:[{zoneId:z.zoneId,targetVolumeM3:1,expectedFlowM3h:z.designFlowM3h,maxDurationMin:60}]},{includeActualRuns:true})
 assert.ok(result.conflicts.some(x=>x.code==='VALVE_OCCUPIED'))
})
test('planning with an explicit current clock refuses stale device heartbeats',()=>{
 const e=structuredClone(initial);e.Plan=[];e.PlanStep=[];const z=e.IrrigationZone[0]
 const result=assessRotationResources(buildIrrigationIndex(e),{scheduledAt:'2026-10-28T07:00:00+08:00',steps:[{zoneId:z.zoneId,targetVolumeM3:1,expectedFlowM3h:10,maxDurationMin:60}]},{now:'2026-10-27T10:18:43+08:00'})
 assert.ok(result.conflicts.some(x=>x.code==='DEVICE_UNAVAILABLE'))
})
