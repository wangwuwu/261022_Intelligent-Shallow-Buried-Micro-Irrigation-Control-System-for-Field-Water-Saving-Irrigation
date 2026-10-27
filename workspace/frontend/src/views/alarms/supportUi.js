export const roles={ADMIN:'系统管理员',MANAGER:'灌溉管理人员',OPERATOR:'灌溉操作人员',TECHNICIAN:'巡检维护人员',VIEWER:'只读查看人员'}
export const kinds={DEVICE_REPAIR:'设备维修',INSPECTION:'巡检',PIPE_REPAIR:'管网维修',OTHER:'其他'}
export const alarmStates={OPEN:'未知悉',ACKNOWLEDGED:'已知悉',ASSIGNED:'已派工',CLOSED:'已关闭'}
export const severity={HIGH:'高',MEDIUM:'中',LOW:'低'}
export const recovery={ACTIVE:'未恢复',RECOVERED:'已恢复'}
export const actionNames={RUN_START:'启动灌溉',RUN_STOP:'停止灌溉',RUN_PAUSE:'暂停灌溉',RUN_RESUME:'恢复灌溉',END_STEP:'结束步骤',SWITCH_ZONE:'切换分区',FINALIZE_WATER:'水量结算',ALARM_ACK:'知悉告警',ALARM_CLOSE:'关闭告警',WORKORDER_CREATE:'创建工单',WORKORDER_ACCEPT:'工单接单',WORKORDER_SUBMIT:'提交处理结果',WORKORDER_APPROVE:'工单验收',WORKORDER_RETURN:'退回工单',USER_CREATE:'新增账号',USER_UPDATE:'编辑账号',USER_DISABLE:'停用账号',USER_ENABLE:'启用账号',POLICY_SAVE:'保存运行参数'}
export function dateText(value,short=false){if(!value||!Number.isFinite(Date.parse(value)))return '—';const text=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(value));return short?text.slice(5):text}
export function numberText(value,digits=1){return Number.isFinite(value)?value.toLocaleString('zh-CN',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'—'}
export const clone=value=>JSON.parse(JSON.stringify(value))
export const columns=items=>items.map(([key,label,width])=>({key,label,width,sortable:!['number','actions'].includes(key)}))
export function ordered(rows,sort){if(!sort?.key)return rows;const id=row=>row.alarmId??row.userId??row.auditId??row.ledgerId??'';return [...rows].sort((a,b)=>{const rawX=a[sort.key],rawY=b[sort.key],x=Array.isArray(rawX)?rawX.length:rawX,y=Array.isArray(rawY)?rawY.length:rawY;return (typeof x==='number'&&typeof y==='number'?x-y:String(x??'').localeCompare(String(y??''),'zh-CN'))*(sort.direction==='desc'?-1:1)||id(a).localeCompare(id(b))})}
export function failureText(e){return [e.message,...Object.values(e.fieldErrors??{})].filter((x,i,a)=>x&&a.indexOf(x)===i).join('；')}
export function localInput(value){return new Date(Date.parse(value)+8*3600000).toISOString().slice(0,16)}
export const futureInput=()=>localInput(new Date(Date.now()+86400000).toISOString())
export const isoInput=value=>value?value+':00+08:00':null
