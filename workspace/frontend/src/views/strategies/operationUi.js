import {formatShanghaiDate} from '../../composables/useClock.js'
export const clone=v=>JSON.parse(JSON.stringify(v))
export const stages={JOINTING:'拔节期',SEEDLING:'苗期',TASSELING:'抽雄期',GRAIN_FILLING:'灌浆期',MATURITY:'成熟期'}
export const triggers={MOISTURE:'墒情',VOLUME:'定量',SCHEDULE:'定时'}
export const methods={MEASURED:'实测',ALLOCATED:'分摊',ESTIMATED:'估算'}
export const fmt=(v,short=false)=>formatShanghaiDate(v,{short})
export const localInput=v=>v?formatShanghaiDate(v).replace(' ','T'):''
export const isoInput=v=>v?(v.length===16?v+':00':v)+'+08:00':null
export const columns=items=>items.map(([key,label,width])=>({key,label,width,sortable:!['number','actions'].includes(key)}))
export function ordered(rows,sort){if(!sort)return rows;return [...rows].sort((a,b)=>{const x=a[sort.key],y=b[sort.key];return (typeof x==='number'?x-y:String(x??'').localeCompare(String(y??''),'zh-CN'))*(sort.direction==='desc'?-1:1)})}
let suggestion=null
export function setPlanSuggestion(value){suggestion=clone(value)}
export function takePlanSuggestion(){const v=suggestion;suggestion=null;return v}
export function requestKey(){let key='',last='';return payload=>{const next=JSON.stringify(payload);if(next!==last||!key){key=crypto.randomUUID();last=next}return key}}
