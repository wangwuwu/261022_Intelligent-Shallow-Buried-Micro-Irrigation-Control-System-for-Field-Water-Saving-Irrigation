<script setup>
import {computed} from 'vue'
import {useIrrigation} from '../../data/runtime.js'
import FormField from '../../components/FormField.vue'
import {kinds} from './supportUi.js'
const props=defineProps({draft:Object,errors:{type:Object,default:()=>({})},locked:Boolean,busy:Boolean}),r=useIrrigation()
const people=computed(()=>(r.state.entities.User??[]).filter(u=>u.role==='TECHNICIAN'&&u.status==='ENABLED'))
</script>
<template><div class="form-grid"><FormField label="工单类型" :error="errors.kind" required><select v-model="draft.kind" :disabled="busy"><option v-for="(v,k) in kinds" :key="k" :value="k">{{v}}</option></select></FormField><FormField label="责任人" :error="errors.assigneeId" required><select v-model="draft.assigneeId" :disabled="busy"><option value="">请选择</option><option v-for="u in people" :key="u.userId" :value="u.userId">{{u.name}}</option></select></FormField><FormField label="关联分区" :error="errors.zoneId"><select v-model="draft.zoneId" :disabled="locked||busy"><option value="">请选择</option><option v-for="z in r.state.entities.IrrigationZone" :key="z.zoneId" :value="z.zoneId">{{z.name}}</option></select></FormField><FormField label="关联设备" :error="errors.deviceId"><select v-model="draft.deviceId" :disabled="locked||busy"><option value="">请选择</option><option v-for="d in r.state.entities.Device" :key="d.deviceId" :value="d.deviceId">{{d.name}}</option></select></FormField><FormField label="期限" :error="errors.dueAt" required><input v-model="draft.dueAt" type="datetime-local" :disabled="busy"/></FormField><FormField label="工单说明" :error="errors.note" required><textarea v-model="draft.note" rows="3" :disabled="busy"/></FormField></div></template>
