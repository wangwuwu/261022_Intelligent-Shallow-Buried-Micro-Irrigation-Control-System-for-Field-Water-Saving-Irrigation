import {reactive} from 'vue'
import seed from 'virtual:irrigation-seed'
import credentials from 'virtual:preview-credentials'
import {createIrrigationRepository} from './repository.js'
import {createHttpIrrigationRepository} from './httpRepository.js'
let runtime
export function useIrrigation(){
 if(!runtime){
  const channel=import.meta.env?.VITE_DATA_CHANNEL??'preview'
  if(channel==='http'){
   runtime=createHttpIrrigationRepository({reactiveState:reactive})
   return runtime
  }
  const reference=new URLSearchParams(globalThis.location?.search??'').get('reference')==='1'
  runtime=createIrrigationRepository({seed,credentials,reactive,storageKey:reference?'irrigation.reference.snapshot.v1':'irrigation.preview.snapshot.v1',sessionKey:reference?'irrigation.reference.session.v1':'irrigation.preview.session.v1',channel})
 }
 return runtime
}
