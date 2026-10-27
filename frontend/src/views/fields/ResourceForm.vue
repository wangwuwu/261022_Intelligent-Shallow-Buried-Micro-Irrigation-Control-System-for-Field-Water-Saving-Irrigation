<script setup>
import {ref,computed,nextTick,watch} from 'vue'
import BaseModal from '../../components/BaseModal.vue'
import FormField from '../../components/FormField.vue'
import {useIrrigation} from '../../data/runtime.js'
import {useDraftGuard} from '../../composables/useDraftGuard.js'
import {notify,confirmAction} from '../../composables/feedback.js'
import {clone} from './resourceUi.js'
const props=defineProps({title:String,action:String,record:Object,fields:Array,readOnly:Boolean,expectedVersions:Object})
const emit=defineEmits(['close','saved'])
const modalKey=ref(0),formElement=ref();const r=useIrrigation(),draft=ref(clone(props.record)),baseline=ref(JSON.stringify(props.record)),busy=ref(false),errors=ref({}),failure=ref('')
const expectedVersion=props.record.version,expectedVersions=clone(props.expectedVersions??{}),sourceChanged=ref(false)
const actionEntity={FIELD_UPDATE:['Field','fieldId'],SEASON_UPDATE:['CropSeason','seasonId'],PIPE_SAVE:['PipeNode','nodeId'],ZONE_UPDATE:['IrrigationZone','zoneId'],POINT_UPDATE:['Point','pointId'],POINT_CALIBRATE:['Point','pointId']}[props.action]
watch(()=>r.state.revision,()=>{const original=actionEntity&&r.state.entities[actionEntity[0]]?.find(row=>row[actionEntity[1]]===props.record[actionEntity[1]]);if(actionEntity&&props.record[actionEntity[1]]&&(!original||original.version!==expectedVersion))sourceChanged.value=true;for(const [id,version] of Object.entries(expectedVersions)){const field=r.state.entities.Field?.find(row=>row.fieldId===id);if(!field||field.version!==version)sourceChanged.value=true}})
const dirty=computed(()=>JSON.stringify(draft.value)!==baseline.value)
const guard=useDraftGuard(()=>dirty.value)
async function close(){if(busy.value)return;if(dirty.value&&!await confirmAction({title:'放弃未保存的修改',message:'当前修改尚未保存，确认放弃？',confirmText:'放弃修改'})){modalKey.value++;return;}baseline.value=JSON.stringify(draft.value);emit('close')}
async function save(){busy.value=true;errors.value={};failure.value='';try{const result=await r.commit(props.action,draft.value,{expectedVersion,expectedVersions,clientRequestId:crypto.randomUUID()});baseline.value=JSON.stringify(draft.value);guard.markClean();notify('保存成功');emit('saved',result);emit('close')}catch(e){errors.value=e.fieldErrors??{};failure.value=e.message;await nextTick();formElement.value?.querySelector('[aria-invalid=true]')?.focus()}finally{busy.value=false}}
</script>
<template><BaseModal :key="modalKey" :model-value="true" :title="title" :busy="busy" :width="760" @update:model-value="close"><p v-if="sourceChanged" class="inline-error" role="status">来源记录已更新，当前草稿已保留。请取消后重新打开并核对最新版本。</p><form ref="formElement" class="form-grid" @submit.prevent="save"><FormField v-for="f in fields" :key="f.key" :label="f.label" :error="errors[f.key]" :required="f.required" :class="{'full-width':f.type==='textarea'}"><select v-if="f.options" v-model="draft[f.key]" :aria-invalid="!!errors[f.key]" :multiple="f.multiple" :disabled="readOnly||f.readonly"><option v-if="!f.multiple" value="">请选择</option><option v-for="o in f.options" :key="o.value" :value="o.value">{{o.label}}</option></select><textarea v-else-if="f.type==='textarea'" v-model="draft[f.key]" :aria-invalid="!!errors[f.key]" :readonly="readOnly||f.readonly"/><input v-else-if="f.type==='number'" v-model.number="draft[f.key]" type="number" :aria-invalid="!!errors[f.key]" step="any" :readonly="readOnly||f.readonly"/><input v-else v-model="draft[f.key]" :aria-invalid="!!errors[f.key]" :type="f.type||'text'" :readonly="readOnly||f.readonly"/></FormField><p v-if="failure" class="error-text full-width" role="alert">{{failure}}</p><slot :draft="draft"/></form><template #footer><button class="btn" :disabled="busy" @click="close">取消</button><button v-if="!readOnly" class="btn btn-primary" :disabled="busy" @click="save">{{busy?'保存中…':'保存'}}</button></template></BaseModal></template>
