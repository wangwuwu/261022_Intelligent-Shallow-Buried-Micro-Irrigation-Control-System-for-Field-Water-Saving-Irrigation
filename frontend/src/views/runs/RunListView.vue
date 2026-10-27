<script setup>
import {ref,computed} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {useIrrigation} from '../../data/runtime.js'
import {useClock} from '../../composables/useClock.js'
import {useListState} from '../../composables/useListState.js'
import {latestZoneReading} from '../../composables/telemetryReadings.js'
import {projectWaterAccounting} from '../../domain/water-accounting.js'
import DataTable from '../../components/DataTable.vue'
import Pagination from '../../components/Pagination.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import BaseModal from '../../components/BaseModal.vue'
import {columns,ordered,fmt,clone,requestKey} from '../strategies/operationUi.js'
const r=useIrrigation(),route=useRoute(),router=useRouter(),clock=useClock(),state=useListState('runs',{filters:{source:route.query.source||'',status:route.query.status||'',fieldId:route.query.fieldId||''}}),filters=ref({...state.filters}),modal=ref(false),selected=ref(null),reason=ref(''),busy=ref(false),failure=ref(''),key=requestKey()
const all=computed(()=>r.state.entities.IrrigationRun??[]),fields=computed(()=>r.state.entities.Field??[]),nodes=computed(()=>(r.state.entities.PipeNode??[]).filter(n=>n.pumpDeviceId)),runSteps=run=>(r.state.entities.RunStep??[]).filter(s=>s.runId===run.runId),zone=id=>r.getIndex().byId.IrrigationZone.get(id),plan=run=>r.getIndex().byId.Plan.get(run.planId),water=computed(()=>{try{return projectWaterAccounting(r.getIndex())}catch(e){return {rows:[],byRun:[],error:e.message}}}),volume=id=>water.value.byRun.find(x=>x.runId===id)?.volumeM3??0
if(clock.isReference&&!state.filters.source&&!state.filters.fieldId){const f=fields.value.find(f=>f.name==='西泵南畦');const z=(r.state.entities.IrrigationZone??[]).find(z=>z.fieldId===f?.fieldId);state.filters.fieldId=f?.fieldId||'';state.filters.source=z?.sourceNodeId||'';filters.value={...state.filters}}
const rows=computed(()=>ordered(all.value.filter(run=>['COMPLETED','STOPPED','FAILED'].includes(run.status)).filter(run=>{const steps=runSteps(run);return (!state.filters.status||run.status===state.filters.status)&&(!state.filters.fieldId||steps.some(s=>zone(s.zoneId)?.fieldId===state.filters.fieldId))&&(!state.filters.source||steps.some(s=>zone(s.zoneId)?.sourceNodeId===state.filters.source))}).sort((a,b)=>Date.parse(b.actualStartedAt||b.requestedAt)-Date.parse(a.actualStartedAt||a.requestedAt)).map(run=>({...run,water:volume(run.runId)})),state.sort)),visible=computed(()=>rows.value.slice((state.page-1)*15,state.page*15)),active=computed(()=>all.value.filter(r=>['RUNNING','STARTING','PAUSED','PAUSING','RESUMING','STOPPING','UNKNOWN','ADVANCING'].includes(r.status))),queued=computed(()=>all.value.filter(r=>r.status==='QUEUED'))
const cols=columns([['number','序号',70],['runId','运行编号',310],['actualStartedAt','开始时间',235],['actualEndedAt','结束时间',235],['water','实际水量 m³',180],['status','状态',150]])
function detail(run){state.selectedId=run.runId;router.push({path:'/runs/'+run.runId,query:{from:route.fullPath}})}
function start(run){selected.value=clone(run);reason.value='';failure.value='';modal.value=true}
async function submit(){busy.value=true;failure.value='';try{if(reason.value.trim().length<6)throw new Error('启动原因至少6字');const payload={runId:selected.value.runId,reason:reason.value};await r.commit('RUN_START',payload,{expectedVersion:selected.value.version,clientRequestId:key(payload)});modal.value=false}catch(e){failure.value=e.message}finally{busy.value=false}}
function latestReading(run,kind){const steps=runSteps(run),activeSteps=steps.filter(s=>['RUNNING','PAUSED','UNKNOWN'].includes(s.status)),zoneIds=(activeSteps.length?activeSteps:steps).map(s=>s.zoneId),current=latestZoneReading(r.state.entities,zoneIds,kind,clock.displayNow.value);if(!current)return '—';if(current.stale)return '已过期';return Number(current.reading.value).toFixed(kind==='PRESSURE'?2:1)}
function unsettled(run){const step=runSteps(run).find(s=>['RUNNING','PAUSED','UNKNOWN'].includes(s.status));if(!step||step.meterStart===null||step.meterStart===undefined||!Number.isFinite(Number(step.meterStart)))return '—';const current=latestZoneReading(r.state.entities,[step.zoneId],'METER_TOTAL',clock.displayNow.value);if(!current||current.stale||Number(current.reading.value)<Number(step.meterStart))return '—';return (Number(current.reading.value)-Number(step.meterStart)).toFixed(1)}
</script>
<template>
  <div class="page-stack run-list">
    <form class="panel filters" @submit.prevent="state.filters = { ...filters }; state.page = 1">
      <label class="filter-field">历史泵站<select v-model="filters.source"><option value="">全部</option><option v-for="n in nodes" :key="n.nodeId" :value="n.nodeId">{{ n.name }}</option></select></label>
      <label class="filter-field">历史运行状态<select v-model="filters.status"><option value="">全部</option><option v-for="s in ['RUNNING', 'QUEUED', 'PAUSED', 'COMPLETED', 'STOPPED', 'FAILED', 'UNKNOWN']" :key="s" :value="s">{{ ({ RUNNING: '运行中', QUEUED: '待执行', PAUSED: '已暂停', COMPLETED: '已完成', STOPPED: '已停止', FAILED: '失败', UNKNOWN: '待核实' })[s] }}</option></select></label>
      <label class="filter-field">历史田块<select v-model="filters.fieldId"><option value="">全部</option><option v-for="f in fields" :key="f.fieldId" :value="f.fieldId">{{ f.name }}</option></select></label>
      <button class="btn btn-primary">查询</button>
      <button type="button" class="btn" @click="state.filters = { source: '', status: '', fieldId: '' }; filters = { ...state.filters }; state.page = 1">重置</button>
    </form>
    <div class="run-metrics">
      <section class="panel"><span>全场运行中</span><strong>{{ active.length }}</strong></section>
      <section class="panel"><span>全场已完成</span><strong>{{ all.filter(x => x.status === 'COMPLETED').length }}</strong></section>
      <section class="panel"><span>全场待执行</span><strong>{{ queued.length }}</strong></section>
    </div>
    <div class="run-cards">
      <section class="panel active-card">
        <div v-for="run in active" :key="run.runId">
          <div class="card-head"><StatusBadge :status="run.status"/><strong>{{ run.runId }}</strong><small>版本 {{ run.version }}</small><button class="btn btn-sm" @click="detail(run)">查看</button></div>
          <p class="muted">计划编号　{{ run.planId }}</p>
          <div class="active-facts">
            <div><small>运行区域</small><strong>{{ runSteps(run).filter(s => ['RUNNING', 'PAUSED', 'UNKNOWN'].includes(s.status)).map(s => zone(s.zoneId)?.name).join('、') || '待确认' }}</strong></div>
            <div><small>流量</small><strong>{{ latestReading(run, 'FLOW_RATE') }} <span>m³/h</span></strong></div>
            <div><small>管网压力</small><strong>{{ latestReading(run, 'PRESSURE') }} <span>MPa</span></strong></div>
          </div>
          <p class="muted card-bottom">计划水量 {{ runSteps(run).reduce((n, s) => n + s.targetVolumeM3, 0) }} m³　|　暂计水量（未结算）{{ unsettled(run) }} m³　|　开始时间 {{ fmt(run.actualStartedAt) }}</p>
        </div>
        <p v-if="!active.length" class="empty-state">当前没有活动运行</p>
      </section>
      <section class="panel queued-card">
        <div v-for="run in queued" :key="run.runId">
          <div class="card-head"><StatusBadge :status="run.status"/><strong>{{ run.runId }}</strong><button class="btn btn-primary btn-sm" :disabled="!r.can('RUN_START', run)" @click="start(run)">启动</button></div>
          <p class="muted">计划编号　<button class="btn-link" @click="detail(run)">{{ run.planId }}</button></p>
          <div class="queue-time"><span>▣</span><div><small>计划时间</small><strong>{{ fmt(plan(run)?.scheduledAt) }}</strong></div></div>
        </div>
        <p v-if="!queued.length" class="empty-state">没有待执行运行</p>
      </section>
    </div>
    <section class="panel run-table">
      <p v-if="water.error" class="error-text" role="alert">{{ water.error }}</p>
      <DataTable :loading="!r.state.ready" compact :columns="cols" :rows="visible" row-key="runId" :selected-id="state.selectedId" :sort="state.sort" @update:sort="state.sort = $event" @row-click="detail">
        <template #cell-number="{ index }">{{ (state.page - 1) * 15 + index + 1 }}</template>
        <template #cell-actualStartedAt="{ value }">{{ fmt(value, true) }}</template>
        <template #cell-actualEndedAt="{ value }">{{ fmt(value, true) }}</template>
        <template #cell-water="{ row }">{{ water.error ? '—' : volume(row.runId).toFixed(1) }}</template>
        <template #cell-status="{ value }"><StatusBadge :status="value"/></template>
      </DataTable>
      <div class="run-table-footer">
        <Pagination v-model="state.page" :total="rows.length">
          <template #summary>全场共{{ all.length }}个运行；历史表<template v-if="state.filters.fieldId">已筛选{{ fields.find(f => f.fieldId === state.filters.fieldId)?.name || state.filters.fieldId }}，共</template><template v-else>共</template>{{ rows.length }}条，15条/页，第{{ state.page }}页</template>
        </Pagination>
      </div>
    </section>
    <BaseModal v-model="modal" title="启动运行" :busy="busy">
      <p>{{ selected?.runId }} · {{ selected?.planId }}</p>
      <p>启动将请求泵阀联动，只有现场动作确认后才进入运行中。</p>
      <label class="filter-field">启动原因<textarea v-model="reason" rows="3" placeholder="至少6字"/></label>
      <p v-if="failure" class="error-text" role="alert">{{ failure }}</p>
      <template #footer><button class="btn" :disabled="busy" @click="modal = false">取消</button><button class="btn btn-primary" :disabled="busy" @click="submit">确认启动</button></template>
    </BaseModal>
  </div>
</template>
<style scoped>.run-list{gap:12px;margin-top:-8px}.run-list>.filters{padding:11px 22px;gap:24px}.run-list .filter-field{flex:1}.run-list .filters>.btn{min-width:92px}.run-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.run-metrics .panel{box-sizing:border-box;height:84px;min-height:84px;padding:9px 23px}.run-metrics .panel:first-child{background:#eaf8f1;border-color:#c2e7d8}.run-metrics .panel:last-child{background:#fff7e7;border-color:#f4dfac;color:#a96113}.run-metrics strong{display:block;font-size:30px;line-height:1.2;margin-top:4px}.run-cards{display:grid;grid-template-columns:1.36fr 1fr;gap:14px}.run-cards .panel{box-sizing:border-box;height:174px;min-height:0;padding:13px 17px}.active-card{background:linear-gradient(110deg,#edf9f2,#f8fcfa);border-color:#c4e6d6}.queued-card{background:#fffaf0;border-color:#f6e4ba}.card-head{display:flex;align-items:center;gap:14px}.card-head>.btn{margin-left:auto;min-width:85px}.run-cards p{margin:4px 0 10px 98px;font-size:13px}.active-facts{display:flex;gap:20px;margin-left:98px;margin-top:12px}.active-facts>div{flex:1}.active-facts>div+div{border-left:1px solid #c7dbd2;padding-left:18px}.active-facts small,.queue-time small{color:#627e84;display:block;margin-bottom:5px}.active-facts strong{font-size:24px;white-space:nowrap}.active-facts strong span{font-size:18px}.run-cards .card-bottom{font-size:12px;margin-top:10px;white-space:nowrap}.queue-time{display:flex;gap:30px;margin:12px 10px}.queue-time>span{font-size:46px}.queue-time strong{font-size:20px}.run-table{padding:0}.run-table :deep(td){height:28px;padding-top:2px;padding-bottom:2px}.run-table-footer{display:flex;align-items:center;justify-content:space-between;padding:8px 16px 12px 24px}.run-table-footer>span{font-size:13px}.run-table-footer :deep(.pagination){margin:0;width:100%}</style>
