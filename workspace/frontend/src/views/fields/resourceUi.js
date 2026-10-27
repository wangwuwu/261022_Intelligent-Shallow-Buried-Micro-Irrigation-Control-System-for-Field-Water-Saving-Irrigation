import {effectiveDeviceConnection} from '../../data/queries.js'
export const stageNames={SOWING:'播种期',EMERGENCE:'出苗期',TILLERING:'分蘖期',OVERWINTER:'越冬期',GREENING:'返青期',JOINTING:'拔节期',HEADING:'抽穗期',GRAIN_FILLING:'灌浆期',HARVESTED:'已收获'}
export const kindNames={GATEWAY:'网关',PUMP:'水泵',VALVE:'阀门',SOIL_PROBE:'墒情探头',SOIL_SENSOR:'墒情探头',SOIL_MOISTURE:'墒情探头',FLOW_METER:'流量计',PRESSURE_SENSOR:'压力传感器',PRESSURE:'压力传感器',WEATHER:'气象站',SOURCE:'水源',MAIN:'主管',BRANCH:'支管'}
export const accountingNames={MEASURED:'实测',ALLOCATED:'分摊',ESTIMATED:'估算'}
export const clone=x=>JSON.parse(JSON.stringify(x))
export const stamp=x=>x?new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(x)):'—'
export const shortStamp=x=>x?stamp(x).slice(5):'—'
export const day=x=>stamp(x).slice(0,10)
export const options=(rows,key,label='name')=>rows.map(r=>({value:r[key],label:r[label]??r[key]}))
export const latest=(rows,id)=>rows.filter(r=>r.pointId===id).sort((a,b)=>Date.parse(b.observedAt)-Date.parse(a.observedAt))[0]
export function sortRows(rows,sort){if(!sort?.key)return rows;return [...rows].sort((a,b)=>(typeof a[sort.key]==='number'?a[sort.key]-b[sort.key]:String(a[sort.key]??'').localeCompare(String(b[sort.key]??''),'zh-CN'))*(sort.direction==='desc'?-1:1))}

export const readingNumber=value=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(1):'—'
export const qualityNames={VALID:'有效',MISSING:'缺失',OUT_OF_RANGE:'超量程',CALIBRATING:'校准中',INVALID:'无效'}
export function readingFacts(reading,point,device,asOf){if(!reading)return '暂无读数';const facts=[];if(!Number.isFinite(reading.value))facts.push('读数缺失');if(reading.quality!=='VALID')facts.push(qualityNames[reading.quality]??'质量异常');const age=(Date.parse(asOf)-Date.parse(reading.observedAt))/1000;if(!Number.isFinite(age)||age<0)facts.push('采集时间异常');else if(age>(point?.staleAfterSec??900))facts.push('读数已过期');if(device&&effectiveDeviceConnection(device,asOf)!=='ONLINE')facts.push(effectiveDeviceConnection(device,asOf)==='OFFLINE'?'设备离线':'设备连接未知');return [...new Set(facts)].join('；')}
