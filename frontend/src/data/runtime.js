import {reactive} from 'vue'
import seed from 'virtual:irrigation-seed'
import credentials from 'virtual:preview-credentials'
import {createIrrigationRepository} from './repository.js'
import {primaryKeys,reject} from './contracts.js'
import {buildIrrigationIndex} from '../domain/irrigation.js'
let runtime
export function useIrrigation(){
 if(!runtime){
  const channel=import.meta.env?.VITE_DATA_CHANNEL??'preview'
  if(channel==='http'){
   const state=reactive({entities:Object.fromEntries(Object.keys(primaryKeys).map(k=>[k,[]])),revision:0,user:null,publicFarm:null,ready:false,error:null,channel,readOnly:true})
   const unavailable=async()=>reject('BACKEND_NOT_CONFIGURED','正式数据服务尚未配置，不能使用本机数据替代')
   runtime={state,load:async()=>{state.ready=true;return state},login:unavailable,logout:async()=>{state.user=null},query:unavailable,commit:unavailable,can:()=>false,getIndex:()=>buildIrrigationIndex(state.entities),subscribe:()=>()=>{},refresh:unavailable,checkSession:()=>false,exportCorruptSnapshot:unavailable,recoverInitialSnapshot:unavailable}
   return runtime
  }
  const reference=new URLSearchParams(globalThis.location?.search??'').get('reference')==='1'
  runtime=createIrrigationRepository({seed,credentials,reactive,storageKey:reference?'irrigation.reference.snapshot.v1':'irrigation.preview.snapshot.v1',sessionKey:reference?'irrigation.reference.session.v1':'irrigation.preview.session.v1',channel})
 }
 return runtime
}
