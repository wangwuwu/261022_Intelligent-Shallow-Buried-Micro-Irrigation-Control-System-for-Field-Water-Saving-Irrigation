from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib
import json
import re
import xml.etree.ElementTree as E

BASE = Path(__file__).resolve().parents[1]
TEMPLATE = BASE / '实验室样品全生命周期管理WEB_交互需求文档_模板_V2.1.xml'
NAME = '田间智能浅埋微灌节水灌溉管控系统'
OUTPUT = BASE / (NAME + '_交互需求文档.xml')
SOURCE = E.parse(TEMPLATE).getroot()
ROOT = E.Element('requirements_document')
NOW = '2026-10-25T10:18:43+08:00'

def node(parent, tag, text=None, **attrs):
    n = E.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    n.text = text
    return n

def rules(parent, tag, values, item='rule', **attrs):
    n = node(parent, tag, **attrs)
    for value in values:
        node(n, item, value)
    return n

def schema(parent, tag):
    n = deepcopy(SOURCE.find('.//' + tag))
    parent.append(n)
    return n

SCREENS = []
def screen(sid, name, route, parent, module, family, surface, regions, navigation, placement, secondary, detail, difference, params='NONE', roles='ADMIN|MANAGER|OPERATOR|TECHNICIAN|VIEWER'):
    SCREENS.append(dict(screen_id=sid, page_name=name, html_file=name + '.html', route=route,
        parent_screen_id=parent, role=roles, back_fallback=parent if parent != 'NONE' else 'NONE',
        owner_sidebar_menu=module, layout_type='irrigation_' + sid.lower().replace('-', '_'),
        responsive_mode='desktop_and_field_tablet', task_family=family, task_family_origin='custom',
        task_family_rationale=surface + '承担本页主要业务任务', layout_type_origin='custom',
        layout_type_rationale=regions + '按任务依赖排列，数据取自统一 Store，写入边界由本页 Action 定义',
        primary_interaction_surface=surface, ordered_functional_regions=regions,
        navigation_pattern=navigation, action_placement=placement, secondary_surface=secondary,
        detail_opening_mode=detail, composition_difference=difference, required_params=params))

screen('AUTH-LOGIN','账号登录','#/login','NONE','NONE','IDENTITY_ACCESS','凭据验证表单','品牌标识|账号密码|登录动作|连接状态','隔离入口，登录后 replace 到 OVERVIEW','表单底部登录按钮','NONE','stay','无业务导航，以身份认证为唯一任务',roles='ALL')
screen('OVERVIEW','灌溉总览','#/overview','NONE','M01','IRRIGATION_SITUATION','田块运行态势图与实时任务带','日期与农场|运行指标|田块态势|执行任务|告警摘要','一级总览进入，卡片带过滤条件钻取','指标卡片与任务行内','数据新鲜度标识','separate_page','以正在运行的分区和异常优先级组织，区别于报表的历史区间分析')
screen('FIELD-LIST','田块与种植','#/fields','OVERVIEW','M02','FIELD_CATALOG','田块卡片目录','查询条件|面积汇总|田块卡片|分页','田间资源二级菜单，卡片进入 FIELD-DETAIL','查询区新增及卡片种植动作','种植季居中弹窗','dialog|separate_page','以田块面积和当前作物为卡片主信息，区别于设备的接入状态表')
screen('FIELD-DETAIL','田块档案','#/fields/detail','FIELD-LIST','M02','FIELD_PROFILE','田块关联关系与墒情剖面','返回与编号|田块事实|种植季|分区关系|墒情剖面|灌溉记录','仅从田块目录、总览或扫码进入','事实区编辑，关联分区行内查看','二维码预览居中弹窗','dialog|separate_page','先展示田块事实，再串联生育期、分区及历史水量',params='fieldId')
screen('FIELD-EDIT','田块资料编辑','#/fields/edit','FIELD-LIST','M02','FIELD_GEOMETRY_EDIT','田块基础资料分组表单','返回|位置面积|土壤属性|负责人|表单动作','新增携带 mode=create；编辑携带 mode=edit,fieldId','表单底部保存、取消、重置','未保存变更居中确认','dialog','仅编辑田块事实，种植季独立弹窗提交，避免跨域表单混写',params='mode;fieldId when mode=edit',roles='ADMIN|MANAGER')
screen('NETWORK','管网与轮灌分区','#/network','OVERVIEW','M03','HYDRAULIC_TOPOLOGY','水源至末级阀门的层级拓扑','水源选择|管网拓扑|选中分区参数|共享供水约束','田间资源二级菜单，拓扑节点切换当前分区','节点旁关联，参数区保存约束','分区和管段居中编辑弹窗','dialog','拓扑为主表面，无普通目录分页，重点表达水力与计量关联')
screen('DEVICE-LIST','设备接入台账','#/devices','OVERVIEW','M04','DEVICE_ONBOARDING','接入能力与连接状态表','设备筛选|接入状态统计|设备表|分页','感知设备二级菜单，设备编号进入 DEVICE-DETAIL','表上登记，行内接入配置','设备接入居中弹窗','dialog|separate_page','按网关协议、能力验证和在线状态组织接入任务')
screen('DEVICE-DETAIL','设备运行档案','#/devices/detail','DEVICE-LIST','M04','DEVICE_DIAGNOSTICS','设备点位与反馈诊断台','返回与设备标识|能力矩阵|点位映射|实时反馈|校准记录|诊断','设备列表或扫码进入，保留点位选择','能力区接入验证，点位行校准','点位映射、校准与扫码居中弹窗','dialog','强调设备原始反馈与可控能力，不混入灌溉任务按钮',params='deviceId')
screen('MONITOR','墒情与环境监测','#/monitor','OVERVIEW','M04','ROOT_ZONE_OBSERVATION','分深度曲线与时序数据','分区深度与区间|实时读数|土层曲线|数据质量|读数分页','感知设备二级菜单，选择分区联动曲线','图表上时间与单位选择，异常点查看设备','设备详情独立页面','separate_page','按深度叠加时序曲线，过期和缺测以断点呈现')
screen('STRATEGY-LIST','灌溉策略','#/strategies','OVERVIEW','M05','IRRIGATION_RULE_CATALOG','作物生育阶段策略矩阵','作物与状态筛选|策略矩阵|版本与执行方式|分页','灌溉作业二级菜单，策略进入 STRATEGY-EDIT','矩阵行内编辑、启停与试算','策略试算居中弹窗','dialog|separate_page','将触发方式与生育阶段交叉展示，区别于日历计划')
screen('STRATEGY-EDIT','灌溉策略编辑','#/strategies/edit','STRATEGY-LIST','M05','IRRIGATION_RULE_EDIT','阈值与终止条件规则表单','返回|适用范围|触发条件|定量与上限|时间窗口|自动执行门槛|保存区','新增与编辑同一表单，由显式 mode 分支提交','表单底部保存、重置、取消','未保存变更居中确认','dialog','以触发、终止和保护上限为相互依赖的规则输入',params='mode;strategyId when mode=edit',roles='ADMIN|MANAGER')
screen('PLAN-LIST','灌溉计划','#/plans','OVERVIEW','M06','ROTATION_SCHEDULING','泵站轮灌时间轴与计划清单','日期泵站筛选|资源占用时间轴|计划清单|分页','灌溉作业二级菜单，可从策略试算带建议创建','时间轴上新建，行内调整和发布','发布冲突确认居中弹窗','dialog|separate_page','时间轴突出共享泵站冲突，不沿用纯表格目录')
screen('PLAN-EDIT','轮灌计划编排','#/plans/edit','PLAN-LIST','M06','ROTATION_COMPOSITION','分区步骤编排表','返回|计划范围与时间|候选分区|轮灌步骤|资源检查|保存区','create/edit 显式模式，建议参数只能初始化 Draft','步骤行内添加移除上移下移，底部检查与保存','未保存变更居中确认','dialog','顺序步骤编辑与泵站容量校验构成主任务',params='mode;planId when mode=edit',roles='ADMIN|MANAGER')
screen('RUN-LIST','灌溉运行','#/runs','OVERVIEW','M07','LIVE_IRRIGATION_DISPATCH','活动运行分区看板','泵站与状态过滤|活动运行卡|待执行队列|历史运行分页','灌溉作业二级菜单，运行卡进入 RUN-DETAIL','卡片查看，待执行行启动','启动联动确认居中弹窗','dialog|separate_page','活动任务和历史记录分区展示，不把已下发指令当作已运行')
screen('RUN-DETAIL','灌溉执行控制','#/runs/detail','RUN-LIST','M07','PUMP_VALVE_EXECUTION','单次灌溉执行反馈台','返回与任务号|实际流量压力|轮灌步骤|指令确认时间线|运行操作|计量明细','总览、运行看板或告警关联进入','运行区暂停恢复，独立醒目停止入口','控制原因与停止确认居中弹窗','dialog','将任务状态和指令阶段并列，控制动作依赖现场权限与模式',params='runId')
screen('ALARM-LIST','运行告警','#/alarms','OVERVIEW','M08','IRRIGATION_INCIDENT_TRIAGE','按严重度排列的告警工作台','状态严重度筛选|告警计数|告警表|关联对象与处理记录|分页','异常维护二级菜单，行选择展示同页处理区','告警行确认、派工、关闭','确认和关闭原因居中弹窗','dialog|separate_page','选择行后同页查看事件上下文，恢复状态与处理状态分离')
screen('WORKORDER-LIST','巡检与维护','#/workorders','ALARM-LIST','M08','FIELD_MAINTENANCE','维护工单泳道与记录','人员类型筛选|待接单|处理中|待验收|已完成记录分页','异常维护二级菜单，可由告警派工进入','泳道卡片接单、填写结果、验收','工单详情与结果居中弹窗','dialog','按维护责任与验收阶段组织，不复制告警严重度表')
screen('WATER-REPORT','用水与节水分析','#/water','OVERVIEW','M09','WATER_ACCOUNTING','区间水量核算与基准对比','农场种植季区间|用水统计|计量口径|田块对比|基准说明|明细分页|导出任务','统计分析一级入口，明细进入 RUN-DETAIL','筛选区查询，基准区配置，底部导出','基准编辑与文件预览居中弹窗','dialog|separate_page','以水量账本和可比基准为中心，指标均由 Selector 派生')
screen('SETTINGS','账号与系统配置','#/settings','OVERVIEW','M10','IRRIGATION_ACCESS_CONFIGURATION','账号授权与运行参数分栏工作区','用户权限Tab|当前Tab内容|修改草稿|提交结果','系统管理二级菜单，权限和参数同页 Tab','用户行授权、启停，参数区保存','账号授权与启停居中弹窗','dialog','授权管理与运行参数分 Tab，参数草稿独立于正式配置',roles='ADMIN')
screen('AUDIT','操作与指令审计','#/audit','OVERVIEW','M10','CONTROL_AUDIT_TRACE','只读操作与指令链路时间线','人员对象与区间|审计表|选中事件链路|分页','系统管理二级菜单，从运行指令携带 correlationId 进入','查询栏与事件行详情','审计详情居中弹窗','dialog','只读事件链展示 actor、版本与关联命令，不提供修改删除',roles='ADMIN|MANAGER')
S = {x['screen_id']: x for x in SCREENS}
MODS = [
 ('M01','灌溉总览',['OVERVIEW'],'聚合正在灌溉的田块、设备可用性和异常优先级'),
 ('M02','田块与种植管理',['FIELD-LIST','FIELD-DETAIL','FIELD-EDIT'],'维护田块事实、种植季与跨页关联标识'),
 ('M03','浅埋微灌管网管理',['NETWORK'],'表达水源、管段、阀门、分区和计量关系'),
 ('M04','设备与环境监测',['DEVICE-LIST','DEVICE-DETAIL','MONITOR'],'接入既有现场设备并区分读数有效性与控制能力'),
 ('M05','灌溉策略管理',['STRATEGY-LIST','STRATEGY-EDIT'],'形成可校验的触发、用水与执行规则'),
 ('M06','计划与轮灌调度',['PLAN-LIST','PLAN-EDIT'],'按供水容量编排和发布轮灌步骤'),
 ('M07','灌溉执行控制',['RUN-LIST','RUN-DETAIL'],'跟踪现场动作确认、运行中止及实际计量'),
 ('M08','告警与巡检维护',['ALARM-LIST','WORKORDER-LIST'],'建立异常确认、派工、恢复和维护验收闭环'),
 ('M09','用水与节水分析',['WATER-REPORT'],'统一实测和分摊口径，公开基准与统计来源'),
 ('M10','系统管理配套',['AUTH-LOGIN','SETTINGS','AUDIT'],'管理身份、田块授权、参数与不可变审计')]

# Every executable control is represented individually; helpers only encode shared UI mechanics.
COMP = []; BRANCHES = []; OVERLAYS = []; ACTIONS = []; LOCALS = {}; QUERIES = {}; SELECTORS = {}; ENTITIES = {}; ENUMS = {}
DISPATCH_ALIASES={}

def comp(sid, key, match, kind, event, typ, pre, immediate, data, success, failure, disabled, back,
         action='NONE', target='STAY', params='NONE', dialog='NONE', branch=None, family=None, **extra):
    a = dict(component_id=sid+'.'+key, match_mode='all' if kind in ('row','card_repeat','step_button') else 'exact_text',
        match=match, element_kind=kind, event=event, action_type=typ, preconditions=pre,
        dialog_id=dialog, target_screen_id=target, route_params=params, immediate_feedback=immediate,
        data_consequence=data, success_consequence=success, failure_consequence=failure,
        disabled_rule=disabled, return_rule=back, action_id=action, behavior_family=family or key)
    if branch:
        a.update(branch_set_id=branch, dialog_id='BY_BRANCH', target_screen_id='BY_BRANCH', route_params='BY_BRANCH')
    a.update(extra)
    COMP.append((sid,a))
    return a['component_id']

def local(aid, effect, scope='UI_STATE,DRAFT,ROUTER'):
    if aid not in LOCALS: LOCALS[aid] = dict(action_id=aid, scope=scope, effect=effect)
    return aid

def edit(sid,key,label,path,validation,context,kind='input',**extra):
    aid=local('UI_'+sid.replace('-','_')+'_'+key.replace('-','_'),f'仅更新 {path}；{validation}；{context}；不写业务实体','DRAFT,UI_STATE')
    cid=comp(sid,key,label,kind,'change' if kind in ('select','checkbox') else 'input','UPDATE_STATE',
        context, f'{path} 更新为用户输入，清除本字段旧错误；{validation}',
        f'只改变 {path}，正式 Store 实体与统计值保持不变',
        f'本字段草稿值可见；{validation}',f'输入无法解析时保留原始输入并在 {label} 下展示校验原因',
        f'{sid} 提交锁定时禁用；{context}',f'离开 {sid} 经过脏草稿分支；取消离开恢复 {path}',action=aid,family='FIELD_EDIT',template='FIELD_EDIT',**extra)
    next(c for ss,c in COMP if c['component_id']==cid)['match_mode']='nearby_label'
    return cid

def nav(sid,key,label,target,params,pre,context,kind='button'):
    aid=local('NAV_'+sid.replace('-','_')+'_'+key.replace('-','_'),f'保存 {sid} 的 {context}；以 {params} 打开 {target}')
    return comp(sid,key,label,kind,'click','NAVIGATE',pre,
        f'{label} 显示路由加载状态并保存 {context}',
        f'仅保存 Router 来源快照及参数 {params}，不修改正式业务实体',
        f'打开 {target}，执行其 page_lifecycle；导航高亮与目标归属同步',
        f'目标加载失败保留 {sid}、{context}，在 {label} 旁显示 ROUTE_LOAD_FAILED',
        f'不满足 {pre} 时禁止进入并显示原因',f'返回 {sid} 恢复 {context}，依最新 Store 重算数据',
        action=aid,target=target,params=params,family='NAVIGATE',template='NAVIGATE')

def readcomp(sid,key,label,qid,inputpath,impact,empty,kind='button',event='click'):
    cid=comp(sid,key,label,kind,event,'SUBMIT',f'已认证且有 {sid} 查看权限；{inputpath} 可解析',
        f'{impact} 显示读取中，保留旧值和 {inputpath}',
        f'调用 {qid} 读取统一 Store；只更新查询状态 {inputpath}，不复制实体',
        f'{impact} 使用该 Query 的 Selector 结果；{empty}',
        f'保留 {inputpath} 和最近成功的 {impact}，就近显示读取失败及重试入口',
        '同一查询请求未完成时禁止再次提交；过期响应按 requestId 丢弃',
        f'返回 {sid} 恢复 {inputpath} 并校验结果版本',action=qid,family='QUERY',template='QUERY')
    c=next(c for ss,c in COMP if c['component_id']==cid)
    if event in ('input','change'):
        c['immediate_feedback']=f'先将event.value按字段白名单写入{inputpath}；'+c['immediate_feedback']
        c['data_consequence']='查询状态改变只写UI；'+('分页改变不清空筛选；' if kind=='pagination' else '条件改变将对应分页置1；')+c['data_consequence']
    if kind=='search_input':c['match_mode']='placeholder';c['debounce_ms']='300'
    return cid

def branches(bid,source,items,order='first_match'):
    BRANCHES.append(dict(branch_set_id=bid,source_component_id=source,evaluation_order=order,otherwise='BLOCK_AND_REPORT',items=items))

def br(when,aid,typ='SUBMIT',target='STAY',params='NONE',dialog='NONE',tx='NONE',bound='NONE'):
    return dict(when=when,action_id=aid,action_type=typ,target_screen_id=target,route_params=params,dialog_id=dialog,transaction_id=tx,bound_match=bound)

def action(aid, inputs, writes, affected, pre, effect, fail, tx=True, **extra):
    ACTIONS.append(dict(action_id=aid,input=inputs,writes=writes,writes_selector='NONE',
        transaction_id='TX-'+aid.replace('_','-') if tx else 'NONE', affected_screens=affected,
        preconditions=pre, success_result=effect, failure_result=fail, **extra))
    return aid

def overlay(oid,owner,title,fields,confirm,aid,triggers,pre,validation,success,failure,typ='DIALOG'):
    OVERLAYS.append(dict(overlay_id=oid,overlay_type=typ,owner_screen_id=owner,title=title,
        fields=fields,confirm_text=confirm,cancel_text='取消' if confirm!='NONE' else '关闭',
        confirm_action_id=aid,trigger_component_ids='|'.join(triggers),open_preconditions=pre,
        field_validation_policy=validation,draft_policy='OPEN:按 fields 从 Selector 初始化 overlayDraft；EDIT:只改草稿；CANCEL:丢弃弹层改动；FAILURE:保留输入；SUCCESS:清除本实例草稿',
        submit_policy='NO_SUBMIT' if aid=='NONE' else 'ACTION_DISPATCHER',
        submit_lock_policy='确认后锁定触发器、确认、取消及字段，屏蔽重复 Enter；完成后释放',
        idempotency_policy='overlayInstanceId+confirm_action_id+clientRequestId；网络重试复用同一键',
        close_policy='CANCEL_MASK_ESCAPE_WHEN_IDLE',focus_policy='CENTER_MODAL|BACKGROUND_INERT|LOCK_SCROLL|FIRST_INVALID_OR_FIRST_FIELD|FOCUS_TRAP',
        focus_return_rule='优先实际触发 component_id；触发器已卸载时返回 owner_screen_id 主工作区',
        affected_screens='INHERIT_CONFIRM_ACTION' if aid!='NONE' else 'NONE',success_result=success,failure_result=failure,
        presentation='centered_modal',scanner_cleanup='关闭时停止全部媒体轨道、识别 worker 与帧循环' if typ=='SCANNER' else 'NONE'))
    if oid=='DIALOG-SIMULATION':
        OVERLAYS[-1]['draft_policy']='OPEN:保存strategyId和asOf；EDIT:只改试算参数；CANCEL:清理参数和结果；FAILURE:保留输入；SUCCESS:保留参数和只读simulation结果供查看或编排计划'

def opendialog(sid,key,label,oid,pre,immediate,data,success,failure,disabled,back,params='NONE',kind='button'):
    aid=local('OPEN_'+oid.replace('-','_'),f'校验 {oid}.open_preconditions，绑定 owner 与触发器，只创建 overlayDraft 并由弹层宿主打开 {oid}')
    return comp(sid,key,label,kind,'click','OPEN_DIALOG',pre,immediate,data,success,failure,disabled,back,action=aid,dialog=oid,params=params)

def entity(name,idfield,fields,immutable=False):
    ENTITIES[name]=dict(id_field=idfield,fields=fields,immutable=immutable)

def field(name,typ='string',required=True,**attrs):
    return dict(name=name,type=typ,required=str(required).lower(),**attrs)

def select(sid,entities,rule): SELECTORS[sid]=dict(selector_id=sid,derives_from=entities,rule=rule)
def query(aid,entities,selectors,success,empty,failure,params='NONE'):
    QUERIES[aid]=dict(action_id=aid,reads=entities,selectors=selectors,success_result=success,empty_result=empty,failure_result=failure,required_params=params)

ENUMS.update({
 'Role':'ADMIN|MANAGER|OPERATOR|TECHNICIAN|VIEWER','RecordStatus':'ENABLED|DISABLED',
 'CropStage':'SOWING|EMERGENCE|TILLERING|OVERWINTER|GREENING|JOINTING|HEADING|GRAIN_FILLING|HARVESTED',
 'DeviceKind':'PUMP|VALVE|GATEWAY|SOIL_PROBE|FLOW_METER|PRESSURE_SENSOR|WEATHER_STATION',
 'ConnectionState':'ONLINE|OFFLINE|UNKNOWN','VerificationState':'UNVERIFIED|VERIFIED|FAILED',
 'ControlMode':'LOCAL|REMOTE|AUTO','DeviceState':'STOPPED|RUNNING|OPEN|CLOSED|UNKNOWN|FAULT',
 'PointKind':'SOIL_MOISTURE|SOIL_TEMPERATURE|FLOW_RATE|METER_TOTAL|PRESSURE|RAINFALL|PUMP_STATE|VALVE_STATE',
 'ReadingQuality':'VALID|MISSING|OUT_OF_RANGE|CALIBRATING','TriggerMode':'SCHEDULE|VOLUME|MOISTURE',
 'ExecutionMode':'RECOMMEND|CONFIRM_REQUIRED|AUTO','PlanStatus':'DRAFT|PUBLISHED|EXECUTING|COMPLETED|CANCELLED|FAILED',
 'RunStatus':'QUEUED|STARTING|RUNNING|PAUSING|PAUSED|RESUMING|ADVANCING|STOPPING|STOPPED|COMPLETED|FAILED|UNKNOWN',
 'StepStatus':'WAITING|STARTING|RUNNING|PAUSED|FINISHING|COMPLETED|SKIPPED|FAILED|UNKNOWN',
 'CommandIntent':'START|PAUSE|RESUME|STEP_FINISH|STOP','CommandStatus':'PENDING|SENT|ACKNOWLEDGED|CONFIRMED|REJECTED|TIMED_OUT|UNKNOWN',
 'StepEndReason':'TARGET_REACHED|MAX_DURATION|OPERATOR_STOP|FAULT',
 'MeasurementMethod':'MEASURED|ALLOCATED|ESTIMATED','AlarmSeverity':'CRITICAL|HIGH|MEDIUM|LOW',
 'AlarmKind':'PRESSURE_HIGH|PRESSURE_LOW|FLOW_DEVIATION|DEVICE_OFFLINE|STALE_READING|CONTROL_TIMEOUT|RESOURCE_CONFLICT',
 'AlarmStatus':'OPEN|ACKNOWLEDGED|ASSIGNED|CLOSED','RecoveryStatus':'ACTIVE|RECOVERED',
 'WorkOrderKind':'LEAK_CHECK|CLOG_CHECK|FILTER_SERVICE|DEVICE_REPAIR|ROUTINE_INSPECTION',
 'WorkOrderStatus':'ASSIGNED|IN_PROGRESS|PENDING_ACCEPTANCE|COMPLETED|RETURNED',
 'QrStatus':'ACTIVE|REVOKED','ExportStatus':'QUEUED|PROCESSING|READY|EXPIRED|FAILED',
 'BaselineBasis':'SAME_FIELD_PRIOR_SEASON|APPROVED_REFERENCE','WaterQualityStatus':'FINAL|PROVISIONAL|INVALID',
 'FieldDetailTab':'PROFILE|MOISTURE|WATER_HISTORY','DeviceDetailTab':'POINTS|CALIBRATIONS|DIAGNOSTICS',
 'RunDetailTab':'STEPS|COMMANDS|WATER','SettingsTab':'USERS|POLICY'
})

def ef(spec):
    out=[]
    for token in spec.split():
        head,*relation=token.split('@')
        name,*t=head.split(':'); typ=t[0] if t else 'string'
        required=not name.endswith('?'); name=name.rstrip('?')
        attrs={}
        if relation: attrs['relation']=relation[0]
        if typ in ENUMS: attrs['enum']=typ
        if name in ('areaMu','volumeM3','targetVolumeM3','capacityM3h','depthCm','intervalCm'): attrs['min']='0'
        out.append(field(name,typ,required,**attrs))
    return out

entity('Session','sessionId',ef('sessionId userId@User.userId role:Role farmId@Farm.farmId expiresAt:datetime'))
entity('User','userId',ef('userId account name phone role:Role status:RecordStatus farmId@Farm.farmId fieldIds:string[]@Field.fieldId'))
ENTITIES['User']['fields'][1]['unique']='true'
entity('Farm','farmId',ef('farmId name region timezone status:RecordStatus'))
entity('Field','fieldId',ef('fieldId farmId@Farm.farmId code name areaMu:decimal soilType location:json managerId@User.userId status:RecordStatus'))
entity('CropSeason','seasonId',ef('seasonId fieldId@Field.fieldId crop variety plantingDate:date harvestDate?:date stage:CropStage status:RecordStatus'))
entity('PipeNode','nodeId',ef('nodeId farmId@Farm.farmId parentNodeId?@PipeNode.nodeId name kind pumpDeviceId?@Device.deviceId capacityM3h:decimal maxConcurrentZones:integer depthCm:decimal intervalCm:decimal designFlowM3h:decimal status:RecordStatus'))
entity('IrrigationZone','zoneId',ef('zoneId farmId@Farm.farmId fieldId@Field.fieldId sourceNodeId@PipeNode.nodeId valveDeviceId@Device.deviceId meterPointId?@Point.pointId soilPointIds:string[]@Point.pointId name areaMu:decimal designFlowM3h:decimal accountingMethod:MeasurementMethod status:RecordStatus'))
entity('Device','deviceId',ef('deviceId farmId@Farm.farmId code name kind:DeviceKind manufacturer model gatewayDeviceId?@Device.deviceId protocol endpoint connection:ConnectionState lastSeenAt?:datetime verification:VerificationState controlMode:ControlMode reportedState:DeviceState capabilities:json status:RecordStatus'))
entity('Point','pointId',ef('pointId deviceId@Device.deviceId zoneId?@IrrigationZone.zoneId name kind:PointKind address unit depthCm:decimal rangeMin:decimal rangeMax:decimal staleAfterSec:integer scale:decimal offset:decimal writable:boolean'))
entity('TelemetryReading','readingId',ef('readingId pointId@Point.pointId observedAt:datetime ingestedAt:datetime value?:decimal quality:ReadingQuality gatewayMessageId'),True)
entity('Strategy','strategyId',ef('strategyId farmId@Farm.farmId name crop stage:CropStage zoneIds:string[]@IrrigationZone.zoneId triggerMode:TriggerMode thresholdVwc?:decimal targetVolumeM3:decimal maxDurationMin:integer allowedStart allowedEnd executionMode:ExecutionMode status:RecordStatus'))
entity('Plan','planId',ef('planId farmId@Farm.farmId name strategyId?@Strategy.strategyId strategySnapshot?:json scheduledAt:datetime status:PlanStatus conflictHash? createdBy@User.userId'))
entity('PlanStep','planStepId',ef('planStepId planId@Plan.planId zoneId@IrrigationZone.zoneId order:integer targetVolumeM3:decimal maxDurationMin:integer expectedFlowM3h:decimal'))
entity('IrrigationRun','runId',ef('runId farmId@Farm.farmId planId@Plan.planId status:RunStatus actualStartedAt?:datetime actualEndedAt?:datetime requestedAt:datetime activeStepId?@RunStep.runStepId lastCommandId?@CommandOutbox.commandId accountingClosed:boolean'))
entity('RunStep','runStepId',ef('runStepId runId@IrrigationRun.runId planStepId@PlanStep.planStepId zoneId@IrrigationZone.zoneId status:StepStatus targetVolumeM3:decimal meterStart?:decimal meterEnd?:decimal startedAt?:datetime endedAt?:datetime'))
entity('CommandOutbox','commandId',ef('commandId runId@IrrigationRun.runId actorId@User.userId intent:CommandIntent status:CommandStatus expectedRunVersion:integer idempotencyKey correlationId sequenceSnapshot:json requestedAt:datetime ackAt?:datetime confirmedAt?:datetime failureCode?'))
entity('CommandEvent','eventId',ef('eventId commandId@CommandOutbox.commandId deviceId@Device.deviceId gatewayEventId phase:CommandStatus occurredAt:datetime payload:json'),True)
entity('WaterLedger','ledgerId',ef('ledgerId runId@IrrigationRun.runId runStepId@RunStep.runStepId zoneId@IrrigationZone.zoneId seasonId@CropSeason.seasonId startedAt:datetime endedAt:datetime volumeM3:decimal method:MeasurementMethod sourceReadingIds:string[]@TelemetryReading.readingId allocationRule? qualityStatus:WaterQualityStatus revisionOf?@WaterLedger.ledgerId'),True)
entity('Alarm','alarmId',ef('alarmId farmId@Farm.farmId deviceId?@Device.deviceId zoneId?@IrrigationZone.zoneId runId?@IrrigationRun.runId kind:AlarmKind severity:AlarmSeverity status:AlarmStatus recovery:RecoveryStatus openedAt:datetime recoveredAt?:datetime acknowledgedBy?@User.userId acknowledgedAt?:datetime closedAt?:datetime handlingNote?'))
entity('WorkOrder','workOrderId',ef('workOrderId farmId@Farm.farmId alarmId?@Alarm.alarmId zoneId?@IrrigationZone.zoneId deviceId?@Device.deviceId kind:WorkOrderKind status:WorkOrderStatus assigneeId@User.userId dueAt:datetime startedAt?:datetime resultNote? completedAt?:datetime acceptedBy?@User.userId'))
entity('Calibration','calibrationId',ef('calibrationId pointId@Point.pointId actorId@User.userId referenceValue:decimal measuredValue:decimal oldOffset:decimal newOffset:decimal calibratedAt:datetime note'),True)
entity('QrCode','qrId',ef('qrId deviceId?@Device.deviceId fieldId?@Field.fieldId payload checksum status:QrStatus issuedAt:datetime'),True)
entity('WaterBaseline','baselineId',ef('baselineId fieldId@Field.fieldId seasonId@CropSeason.seasonId basis:BaselineBasis referenceAreaMu:decimal referenceVolumeM3:decimal referenceStart:date referenceEnd:date sourceNote approvedBy@User.userId status:RecordStatus'))
entity('ExportJob','exportId',ef('exportId farmId@Farm.farmId createdBy@User.userId filterSnapshot:json status:ExportStatus sourceRevision fileName? downloadUrl? expiresAt?:datetime rowCount?:integer checksum?'))
entity('SystemPolicy','policyId',ef('policyId farmId@Farm.farmId defaultStaleSec:integer commandAckTimeoutSec:integer actionConfirmTimeoutSec:integer maxScheduleDays:integer commandSequence:json localDisconnectPolicy capabilitySignoff:json'))
entity('AuditLog','auditId',ef('auditId farmId@Farm.farmId actorId?@User.userId actionId entityType entityId beforeVersion?:integer afterVersion?:integer occurredAt:datetime correlationId result detail:json'),True)
ENTITIES['CommandOutbox']['fields'] += ef('reason')
ENTITIES['WorkOrder']['fields'] += ef('requestNote reviewNote?')
ENTITIES['Alarm']['fields'] += ef('resolution?')
ENTITIES['IrrigationZone']['fields'] += ef('allocationRule?')
ENTITIES['Device']['fields'] += ef('heartbeatTimeoutSec:integer')
ENTITIES['RunStep']['fields'] += ef('endReason?:StepEndReason')
for ename in ['Field','User','Farm','CropSeason','IrrigationZone','Strategy']:
    for f in ENTITIES[ename]['fields']:
        f['derived']='false'
        if f['name']=='status':f['default']='ENABLED'

DOMAIN_READS={
 'OVERVIEW':('Farm,Field,IrrigationZone,Device,TelemetryReading,Point,IrrigationRun,Alarm,WaterLedger','SELECT-OVERVIEW'),
 'FIELD-LIST':('Field,CropSeason,IrrigationZone,User','SELECT-FIELDS'),
 'FIELD-DETAIL':('Field,CropSeason,IrrigationZone,Point,TelemetryReading,IrrigationRun,WaterLedger,QrCode','SELECT-FIELD-DETAIL'),
 'FIELD-EDIT':('Field,User,Farm','SELECT-FIELD-EDIT'),
 'NETWORK':('PipeNode,IrrigationZone,Field,Device,Point,Plan,PlanStep,IrrigationRun,RunStep','SELECT-NETWORK'),
 'DEVICE-LIST':('Device,Point,IrrigationZone','SELECT-DEVICES'),
 'DEVICE-DETAIL':('Device,Point,TelemetryReading,Calibration,QrCode,SystemPolicy','SELECT-DEVICE-DETAIL'),
 'MONITOR':('Point,TelemetryReading,IrrigationZone,Field,Device','SELECT-MONITOR'),
 'STRATEGY-LIST':('Strategy,IrrigationZone,CropSeason','SELECT-STRATEGIES'),
 'STRATEGY-EDIT':('Strategy,IrrigationZone,Point,Device,PipeNode,CropSeason,SystemPolicy','SELECT-STRATEGY-EDIT'),
 'PLAN-LIST':('Plan,PlanStep,IrrigationZone,PipeNode,IrrigationRun','SELECT-PLANS'),
 'PLAN-EDIT':('Plan,PlanStep,Strategy,IrrigationZone,PipeNode,Device,SystemPolicy,IrrigationRun,RunStep','SELECT-PLAN-EDIT'),
 'RUN-LIST':('IrrigationRun,RunStep,Plan,PlanStep,Device,IrrigationZone,CommandOutbox','SELECT-RUNS'),
 'RUN-DETAIL':('IrrigationRun,RunStep,Plan,PlanStep,Device,Point,TelemetryReading,CommandOutbox,CommandEvent,WaterLedger,SystemPolicy','SELECT-RUN-DETAIL'),
 'ALARM-LIST':('Alarm,Device,IrrigationZone,IrrigationRun,WorkOrder,User','SELECT-ALARMS'),
 'WORKORDER-LIST':('WorkOrder,Alarm,Device,IrrigationZone,User','SELECT-WORKORDERS'),
 'WATER-REPORT':('WaterLedger,IrrigationZone,Field,CropSeason,WaterBaseline,ExportJob,User','SELECT-WATER'),
 'SETTINGS':('User,SystemPolicy,Farm,Field','SELECT-SETTINGS'),
 'AUDIT':('AuditLog,CommandOutbox,CommandEvent,User','SELECT-AUDIT'),
 'AUTH-LOGIN':('Session','SELECT-SESSION')}
Q={sid:'QUERY_'+sid.replace('-','_') for sid in S}
LIST_RULE='先按 session.farmId、角色及 fieldIds 授权，再按显式 filters 过滤，以稳定主键作同值排序第二键；total=过滤后集合长度，rows=同一集合按 page/pageSize 切片；空列表 total=0；卡片统计与分页必须共享该集合'
DERIVE_RULES={
 'OVERVIEW':'以当前农场授权 Field 为全集，面积=sum(areaMu)；运行数=count(IrrigationRun status in RUNNING,PAUSED,STARTING,PAUSING,RESUMING,STOPPING,UNKNOWN)；今日水量按 Asia/Shanghai 自然日切分 FINAL WaterLedger，剔除被 revisionOf 替代记录；告警数=count(status!=CLOSED)；在线率=ONLINE且now-lastSeenAt<=heartbeatTimeoutSec的Device数量 / ENABLED Device数量；设备数为0时显示无设备；同一账本分配不得重复累计',
 'FIELD-LIST':LIST_RULE+'；当前种植季=fieldId 相同且 status=ENABLED 的唯一 CropSeason；分区覆盖面积=sum(ENABLED zone.areaMu)，与田块面积单独展示，不重复累计田块面积',
 'FIELD-DETAIL':'按 routeParams.fieldId 取唯一 Field，关联季节、分区、点位与 FINAL WaterLedger；读数按 pointId 最新 observedAt 取值并按 staleAfterSec 派生过期；历史运行先按 zoneId 关联再按 runId 去重；页面田块名、面积、作物与目录使用同一主键',
 'FIELD-EDIT':'mode=create 生成空 Draft，默认 farmId 来自 Session；mode=edit 读取唯一 Field 和 version 初始化可编辑 Draft，Draft 不加入 Field 正式集合；有效负责人来自 ENABLED 且同 farmId 的 User',
 'NETWORK':'PipeNode 按 parentNodeId 构造无环树；IrrigationZone 按 sourceNodeId 关联，节点流量容量与分区设计流量用于校验；共享泵站并发占用由 PUBLISHED/EXECUTING PlanStep 和运行状态派生，不能在页面存第二份占用数',
 'DEVICE-LIST':LIST_RULE+'；接入能力分别展示 verification、capabilities.read/control/feedback/localSchedule，设备在线状态不代表可远程控制',
 'DEVICE-DETAIL':'按 deviceId 读取 Device，Point 以 deviceId 过滤；实时值从各 Point 的最近有效 TelemetryReading 派生；Calibration 按 calibratedAt 降序；控制能力=VERIFIED且相关 capability=true，不以型号名称猜测',
 'MONITOR':'按授权 zoneId、Point.kind、depthCm、时间区间选择 TelemetryReading；同 pointId+observedAt 依 ingestedAt 去重；原始记录分页与曲线使用同一过滤全集，曲线可进行标明算法的降采样，total 不采用降采样点数；过期由查询时钟推导，MISSING/OUT_OF_RANGE/断网间隙显示断点',
 'STRATEGY-LIST':LIST_RULE+'；状态、作物、stage、triggerMode 均取 Strategy；每个策略使用自身版本展示，列表不存单独的策略计数',
 'STRATEGY-EDIT':'mode=create 初始化 Draft；mode=edit 按 strategyId 读取 Strategy.version；选区候选按 crop 与当前种植季筛选；AUTO 可用性取所有相关 Device 的 VERIFIED反馈能力与 SystemPolicy.capabilitySignoff，不只检查勾选框',
 'PLAN-LIST':LIST_RULE+'；目标水量=sum(PlanStep.targetVolumeM3)，步骤数=count(PlanStep)，时间轴与列表共享 Plan/PlanStep；冲突按泵站容量、并发数和时间窗口派生',
 'PLAN-EDIT':'按 mode 与 planId 初始化计划和有序 PlanStep Draft；新步骤使用随机稳定 stepDraftId；按 sourceNodeId、capacityM3h、maxConcurrentZones 计算候选窗口；不允许把步骤顺序作为 planStepId',
 'RUN-LIST':LIST_RULE+'；活动卡与历史表按同一 IrrigationRun 分组，QUEUED 为待执行队列，RUNNING 与控制过渡态为活动组，终态为历史组；一个 runId 只出现于一个组',
 'RUN-DETAIL':'按 runId 关联 RunStep、Plan、CommandOutbox、CommandEvent；阶段按 gatewayEventId 去重显示；累计实际水量=该 runId 的最终有效 WaterLedger 之和；运行中暂估读数单独标记，不写最终账本统计；控制按钮依 RunStatus、模式、权限和未决指令派生',
 'ALARM-LIST':LIST_RULE+'；恢复态 recovery 与处理态 status 分离，未关闭数只统计 status!=CLOSED；行选择详情使用 alarmId 直接引用同一 Alarm；派工状态从关联 WorkOrder 派生',
 'WORKORDER-LIST':LIST_RULE+'；四条泳道按 WorkOrder.status 分组，当前页卡片按同一个过滤全集切片，total 与泳道标题计数同源；TECHNICIAN 仅见 assigneeId=session.userId 的工单',
 'WATER-REPORT':'有效账本=qualityStatus=FINAL且不存在后续有效 revisionOf 指向其 ledgerId；按 endedAt 归属种植季，跨日记录由来源累计表读数插值并标记方法，跨季需分段入账；按 zoneId 关联 Field 并按 fieldId 去重面积；亩均量=区间账本量/覆盖田块面积；Measured/Allocated/Estimated 分列；节水基准量=referenceVolumeM3/referenceAreaMu*本期可比面积；节水率=(可比基准量-本期可比水量)/可比基准量*100；基准缺失、为零或日期窗口/作物不可比时返回 null 和原因；负值如实显示；明细 total=count(过滤后有效账本)，不以卡片分组数作为明细总数',
 'SETTINGS':'User 依 farmId 授权过滤；账号表 total 与可见行共用集合；系统参数按 policyId 唯一读取；当前账号角色权限来自服务端 Session/User，修改当前账号后立即重新校验授权',
 'AUDIT':LIST_RULE+'；AuditLog 只读，按 correlationId 关联 CommandOutbox/CommandEvent，过滤结果数量与分页同源',
 'AUTH-LOGIN':'只读服务端会话有效性；当前角色以已认证 User.role 为准，不在登录表单中自选角色'}
for sid,(entities,selector) in DOMAIN_READS.items():
    select(selector,entities,DERIVE_RULES[sid])
    query(Q[sid],entities,selector,f'将读取结果归一化合并到唯一 Store，{sid} 订阅 {selector}；只在请求版本仍有效时渲染',
          f'{sid} 展示明确的无记录或无会话状态，保留查询条件，不造默认业务记录',
          f'{sid} 保留最近成功快照与查询 Draft，标记读取失败；实体不存在显示 ENTITY_NOT_FOUND，越权显示 FORBIDDEN，禁止显示伪造空详情',S[sid]['required_params'])
query('QUERY_QR_RESOLVE','QrCode,Device,Field','SELECT-QR-ENTITY','校验载荷 checksum、域名、编码版本及实体授权，返回唯一类型和主键到 ui.scanResolution','展示二维码已撤销或无记录','保留原扫描输入并显示 INVALID_QR、FOREIGN_FARM 或 FORBIDDEN','payload')
select('SELECT-QR-ENTITY','QrCode,Device,Field','按 payload 精确匹配 ACTIVE QrCode；deviceId 与 fieldId 必须且仅有一个非空；不从可见文字反推主键')
query('QUERY_STRATEGY_SIMULATE','Strategy,IrrigationZone,Point,TelemetryReading,Device,SystemPolicy','SELECT-STRATEGY-SIMULATION','渲染各分区触发依据、读数时间、建议水量和不可执行原因','展示策略未绑定有效分区','保留策略和试算区间，禁止把过期读数当作有效触发','strategyId,asOf')
select('SELECT-STRATEGY-SIMULATION','Strategy,IrrigationZone,Point,TelemetryReading,Device,SystemPolicy','依 Strategy.triggerMode、阈值、时段和最新有效读数逐区计算；仅生成 ui.simulation，不创建 Plan；缺测、越界、能力未验证逐项返回阻断原因')
query('QUERY_PLAN_CONFLICTS','Plan,PlanStep,PipeNode,IrrigationZone,Device,SystemPolicy,IrrigationRun,RunStep','SELECT-PLAN-CONFLICTS','生成 conflictHash、冲突泵站及建议窗口，保持 planDraft','无冲突返回 conflicts=[] 和已校验 hash','保留步骤和时间，显示资源检查失败并阻止发布','planDraft,expectedVersions')
select('SELECT-PLAN-CONFLICTS','Plan,PlanStep,PipeNode,IrrigationZone,Device,SystemPolicy,IrrigationRun,RunStep','以 planDraft 步骤时长 targetVolumeM3/expectedFlowM3h*60 与 maxDurationMin 上限计算顺序占用；当前RUNNING/PAUSED/UNKNOWN占用未释放时纳入冲突；检查时段重叠、容量、分区并发、停用设备及过期能力签核；hash 覆盖 Draft 和资源版本；保存与发布必须重新计算')
query('QUERY_EXPORT_STATUS','ExportJob','SELECT-EXPORTS','刷新导出状态并允许下载 READY 文件','无导出记录展示空任务区','保留任务编号和已知状态，退避轮询，不重复创建任务','exportId?')
select('SELECT-EXPORTS','ExportJob','同 farmId 且 createdBy=session.userId 的任务按 createdAt 降序；READY且expiresAt>now才能下载；到期由 now 派生不可下载状态')

ALL='OVERVIEW,FIELD-LIST,FIELD-DETAIL,NETWORK,DEVICE-LIST,DEVICE-DETAIL,MONITOR,STRATEGY-LIST,PLAN-LIST,RUN-LIST,RUN-DETAIL,ALARM-LIST,WORKORDER-LIST,WATER-REPORT,AUDIT'
action('AUTHENTICATE','account,password,clientRequestId','Session','AUTH-LOGIN,OVERVIEW','账号 ENABLED；服务端验证密码与农场权限','建立会话并从服务端 User 取 role；清除密码，replace OVERVIEW','不创建会话；保留账号，清空密码，显示统一认证失败信息',tx=False)
action('SESSION_LOGOUT','sessionId','Session','AUTH-LOGIN','当前会话存在','撤销服务端会话、清空 Store 敏感缓存和订阅，replace AUTH-LOGIN','撤销失败保留会话状态并允许重试，不显示已退出',tx=False)
action('FIELD_CREATE','fieldDraft,clientRequestId','Field,AuditLog','FIELD-LIST,FIELD-DETAIL,NETWORK,OVERVIEW,AUDIT','ADMIN或MANAGER；同农场；面积>0且编码唯一；负责人有效','创建不可变 fieldId 的 Field，version=1；记录 CREATE_FIELD 审计','全部回滚，保留位置面积与负责人输入，重复编码定位 code')
action('FIELD_UPDATE','fieldId,fieldDraft,expectedVersion','Field,AuditLog','FIELD-LIST,FIELD-DETAIL,NETWORK,OVERVIEW,AUDIT','ADMIN或MANAGER；版本一致；新面积不小于已启用分区面积总和','只更新田块基础事实及 version，不修改 CropSeason 或历史账本','全部回滚；面积不足定位 areaMu；版本冲突提供重新读取')
action('SEASON_SAVE','fieldId,seasonDraft,expectedFieldVersion','CropSeason,Field,AuditLog','FIELD-LIST,FIELD-DETAIL,STRATEGY-LIST,WATER-REPORT,AUDIT','MANAGER或ADMIN；同田块同时间仅一个活动季；种植日期不晚于收获日期','新增或更新活动种植季，旧季归档保留；Field.version递增','整笔回滚，保留作物、日期和生育阶段')
action('ZONE_SAVE','zoneDraft,expectedVersions','IrrigationZone,AuditLog','NETWORK,FIELD-DETAIL,PLAN-LIST,MONITOR,WATER-REPORT,AUDIT','ADMIN或MANAGER；无运行中引用；田块面积覆盖有效；阀门与流量点同农场且可归属','建立或修改分区关联、面积、设计流量和计量方法；引用主键保持稳定','不改变既有拓扑与分区；保留关联选择并指出冲突设备')
action('PIPE_SAVE','nodeDraft,expectedVersion','PipeNode,AuditLog','NETWORK,PLAN-LIST,AUDIT','ADMIN或MANAGER；父节点无环；capacityM3h>0；maxConcurrentZones>=1；无活动占用','保存管段参数与供水约束，提升版本并使旧资源检查 hash 失效','回滚节点参数，保留埋深间距草稿；展示环路或占用原因')
action('DEVICE_SAVE','deviceDraft,expectedVersion?,clientRequestId','Device,AuditLog','DEVICE-LIST,DEVICE-DETAIL,NETWORK,AUDIT','ADMIN；设备编码唯一；协议和endpoint经校验；凭据仅写服务端密钥库','登记或更新接入元数据，配置变化置 verification=UNVERIFIED；capabilities 不由表单自证','全部回滚，保留非敏感型号协议输入，清除接入密钥输入')
action('DEVICE_VERIFY','deviceId,expectedVersion,clientRequestId','Device,AuditLog','DEVICE-LIST,DEVICE-DETAIL,RUN-DETAIL,AUDIT','ADMIN；连接可用；执行只读握手与模拟反馈校验，禁止自动启泵','保存真实适配器验证结果和capabilities；FAILED是验证结果而非假在线；不向真实执行器发送动作','验证请求错误时保持旧能力并标记读取失败，不伪造 VERIFIED')
action('POINT_SAVE','deviceId,pointDraft,expectedVersion','Point,Device,AuditLog','DEVICE-DETAIL,MONITOR,NETWORK,RUN-DETAIL,AUDIT','ADMIN；地址唯一；量程 min<max；单位符合 PointKind；现场映射核对通过','保存点位和缩放规则；设备验证状态失效；历史原始读数不可改写','整体回滚，保留地址单位输入，定位重复地址或量纲错误')
action('POINT_CALIBRATE','pointId,referenceValue,measuredValue,note,expectedVersion','Point,Calibration,AuditLog','DEVICE-DETAIL,MONITOR,AUDIT','ADMIN或TECHNICIAN；目标点可校准；参考值在量程内；无活动灌溉使用该触发点','保存offset=referenceValue-measuredValue并追加不可变Calibration，既有原始读数保留','回滚点位offset和校准记录，保留参考值与说明')
action('STRATEGY_CREATE','strategyDraft,clientRequestId','Strategy,AuditLog','STRATEGY-LIST,STRATEGY-EDIT,PLAN-EDIT,AUDIT','MANAGER或ADMIN；阈值量纲正确；目标水量>0；AUTO必须具备已签核本地保护与动作反馈','创建规则与版本；默认CONFIRM_REQUIRED；不自动创建运行任务','整体回滚；阈值或AUTO门槛失败定位对应字段')
action('STRATEGY_UPDATE','strategyId,strategyDraft,expectedVersion','Strategy,AuditLog','STRATEGY-LIST,STRATEGY-EDIT,PLAN-EDIT,AUDIT','MANAGER或ADMIN；版本一致；完整复验触发模式及目标分区能力','提升Strategy.version，既有Plan.strategySnapshot保持原值','保留原策略和表单；版本冲突提示读取新版本后人工核对')
action('STRATEGY_ENABLE','strategyId,expectedVersion','Strategy,AuditLog','STRATEGY-LIST,PLAN-EDIT,AUDIT','MANAGER或ADMIN；status=DISABLED；所有适用分区可用且执行门槛通过','置ENABLED，记录启用者；不立即触发灌溉','保持DISABLED；保留启用确认弹窗并展示缺失能力')
action('STRATEGY_DISABLE','strategyId,expectedVersion','Strategy,AuditLog','STRATEGY-LIST,PLAN-EDIT,AUDIT','MANAGER或ADMIN；status=ENABLED','置DISABLED，停止生成新建议；已发布计划保留快照并要求独立取消','保持ENABLED，保留当前策略确认上下文并显示版本冲突')
action('PLAN_CREATE','planDraft,stepDrafts,clientRequestId','Plan,PlanStep,AuditLog','PLAN-LIST,PLAN-EDIT,RUN-LIST,AUDIT','MANAGER或ADMIN；步骤非空、分区不重复、目标水量和时长>0；服务器重做资源检查','原子创建DRAFT Plan及所有PlanStep，稳定随机主键不依赖排序；保存策略快照','任何步骤失败回滚整张计划，保留时间和所有步骤草稿')
action('PLAN_UPDATE','planId,planDraft,stepDrafts,expectedVersion','Plan,PlanStep,AuditLog','PLAN-LIST,PLAN-EDIT,AUDIT','MANAGER或ADMIN；status=DRAFT；版本与步骤引用有效；重做资源检查','原子更新Plan与步骤集合；删除草稿步骤不删除历史执行记录','全部回滚，保留编排顺序；已发布时显示PLAN_LOCKED')
action('PLAN_PUBLISH','planId,expectedVersion,conflictHash','Plan,IrrigationRun,RunStep,AuditLog','PLAN-LIST,RUN-LIST,RUN-DETAIL,OVERVIEW,AUDIT','MANAGER或ADMIN；DRAFT；当前资源检查通过且hash未过期；时间未过期','Plan置PUBLISHED；创建唯一QUEUED运行及RunStep；尚不下发现场指令','整体回滚且不创建空运行；资源变化要求重新检查并保留计划')
action('PLAN_CANCEL','planId,reason,expectedVersion','Plan,IrrigationRun,AuditLog','PLAN-LIST,RUN-LIST,OVERVIEW,AUDIT','MANAGER或ADMIN；Plan.status in DRAFT,PUBLISHED；运行尚为QUEUED且无未决指令','取消计划并将已排队运行置STOPPED，保留取消原因和历史步骤','原状态保持；已开始执行必须通过RUN_STOP，弹窗显示PLAN_ALREADY_STARTED')

# A database transaction can enqueue a physical command; it cannot undo water already delivered.
for intent,allowed,transitional in [
 ('START','QUEUED','STARTING'),('PAUSE','RUNNING','PAUSING'),('RESUME','PAUSED','RESUMING'),
 ('STOP','STARTING|RUNNING|PAUSING|PAUSED|RESUMING|ADVANCING|UNKNOWN','STOPPING')]:
    action('RUN_'+intent,'runId,reason,expectedVersion,clientRequestId','IrrigationRun,CommandOutbox,AuditLog',
        'RUN-LIST,RUN-DETAIL,PLAN-LIST,OVERVIEW,ALARM-LIST,AUDIT',
        f'OPERATOR、MANAGER或ADMIN且有田块操作权；run.status in {allowed}；设备控制模式允许远程；适配器及动作反馈已验证；'+('不存在未决STOP；允许抢占未决非STOP指令并引用其correlationId；控制模式为LOCAL时只报告需现场停机' if intent=='STOP' else '不存在任何未决指令；通信在线、关键读数新鲜、联动签核有效；START与RESUME重新检查泵站资源'),
        f'原子写 CommandOutbox(intent={intent},status=PENDING) 与审计，运行置{transitional}；发送由服务端outbox执行器承担；UI显示请求已受理，实际'+intent+'需等待CONFIRMED事件',
        '入队失败整体回滚正式实体和命令；传输成功后的超时不回滚现场动作，置UNKNOWN并触发对账告警；禁止盲目重发相反指令',
        hardware_effect='AFTER_COMMIT_OUTBOX_ONLY',finality='REQUIRES_DEVICE_STATE_CONFIRMATION')
action('INGEST_TELEMETRY','gatewayId,messageId,readings','TelemetryReading,Device','OVERVIEW,DEVICE-LIST,DEVICE-DETAIL,MONITOR,RUN-DETAIL',
       '服务端已认证网关；点位归属校验；messageId去重；时间和量纲校验',
       '原子追加原始读数并更新最后心跳；乱序读数保存但不覆盖较新显示值；不据单条读数直接宣告动作完成',
       '整批不入库并记录采集错误，客户端保持上次有效读数且标记过期')
action('RECONCILE_COMMAND','commandId,gatewayEventId,phase,reportedState','CommandOutbox,CommandEvent,IrrigationRun,RunStep,Plan,Alarm,AuditLog',ALL,
       '可信设备事件签名有效或服务端超时调度器身份有效；gatewayEventId或超时键去重；合法阶段转移；反馈对象与命令序列一致',
       '追加CommandEvent；ACK仅更新ACKNOWLEDGED；全部联动反馈满足后CONFIRMED并转RUNNING、PAUSED或STOPPED，同步活动RunStep；首次启动确认后Plan置EXECUTING；拒绝或超时生成Alarm并保持现场状态可追溯',
       '数据库失败整体回滚本次事件入库，保留outbox以幂等重放；不声称撤销已发生的物理动作')
next(a for a in ACTIONS if a['action_id']=='RECONCILE_COMMAND')['state_transition_contract']=json.dumps({
    'SENT':'CommandOutbox.status=SENT; IrrigationRun.status不变',
    'ACKNOWLEDGED':'CommandOutbox.status=ACKNOWLEDGED; IrrigationRun.status不变',
    'CONFIRMED_START':'IrrigationRun=RUNNING; active RunStep=RUNNING; Plan=EXECUTING',
    'CONFIRMED_PAUSE':'IrrigationRun=PAUSED; active RunStep=PAUSED; Plan保持EXECUTING',
    'CONFIRMED_RESUME':'IrrigationRun=RUNNING; active RunStep=RUNNING; Plan保持EXECUTING',
    'CONFIRMED_STOP':'IrrigationRun=STOPPED; active RunStep=COMPLETED并保留实际终止原因; 未执行RunStep=SKIPPED; Plan保持EXECUTING至结算',
    'CONFIRMED_STEP_FINISH':'active RunStep=COMPLETED; endReason=TARGET_REACHED或MAX_DURATION; IrrigationRun保持ADVANCING至本步结算; 后续WAITING步骤不跳过',
    'REJECTED_START':'IrrigationRun=FAILED; active RunStep=FAILED; Plan=FAILED; Alarm=OPEN',
    'REJECTED_PAUSE_OR_RESUME_OR_STOP':'IrrigationRun=UNKNOWN; 保留步骤现场事实; Alarm=OPEN',
    'TIMED_OUT':'CommandOutbox=TIMED_OUT; IrrigationRun=UNKNOWN; Alarm=OPEN; 等待对账',
    'LATE_CONFIRMED':'以当前设备完整状态及关联命令序列对账；旧命令不得覆盖后续已确认STOP；追加CommandEvent与审计'
},ensure_ascii=False,separators=(',',':'))
action('FINALIZE_WATER','runStepId,meterReadings,accountingMethod,expectedVersion','WaterLedger,RunStep,IrrigationRun,Plan,AuditLog',ALL,
       '服务端计量处理器；步骤已结束且终止反馈确认；累计表复位/溢出已识别；相同结算键未处理',
       '建立FINAL账本；无独立表采用批准分摊规则并标记ALLOCATED；本步结算完成且有WAITING步骤时保持ADVANCING，提交后由RUN_ADVANCE申请下一步；所有步骤正常完成时运行及计划COMPLETED、accountingClosed=true；人工停止保留STOPPED并置Plan=CANCELLED；更正通过revisionOf追加，不改原始值',
       '结算失败保持accountingClosed=false及PROVISIONAL显示，不产生部分账本，等待同键重试')
action('RUN_STEP_FINISH','runId,runStepId,endReason,sourceEventId,expectedVersion','IrrigationRun,RunStep,CommandOutbox,AuditLog',ALL,
       '仅可信控制器或调度服务；活动步骤RUNNING；endReason=TARGET_REACHED或MAX_DURATION且有效计量或本地计时证据满足；无STOP抢占；源事件去重',
       '原子入队STEP_FINISH并写结束依据，运行ADVANCING、活动步骤FINISHING；按签核序列结束当前供水；本地保护先行，平台等待现场确认；不得跳过后续WAITING步骤',
       '入队失败整体回滚并告警；若本地已停止则通过签名反馈对账，禁止为回滚而重新开阀',hardware_effect='AFTER_COMMIT_OUTBOX_ONLY')
action('RUN_ADVANCE','runId,completedRunStepId,expectedVersion,clientRequestId','IrrigationRun,RunStep,CommandOutbox,AuditLog',ALL,
       '仅可信调度服务；当前运行ADVANCING；前一步已CONFIRMED并完成FINAL账本；存在下一个WAITING步骤；无STOP或未知反馈；容量、模式与保护重新校验',
       '以PlanStep.order选择唯一下一步，设activeStepId与RunStep=STARTING、IrrigationRun=STARTING，入队START；策略目标使用已发布快照；反馈确认后RUNNING',
       '整体回滚下步启动；保留上步已结算账本和ADVANCING状态，独立告警评估器记录调度异常，禁止越过失败步骤',hardware_effect='AFTER_COMMIT_OUTBOX_ONLY')
action('ALARM_EVALUATE','sourceEventId,farmId,deviceId?,zoneId?,runId?,kind,evidence','Alarm,AuditLog',
       'ALARM-LIST,WORKORDER-LIST,OVERVIEW,RUN-DETAIL,AUDIT',
       '仅可信遥测、反馈或调度服务；sourceEventId去重；异常阈值和恢复持续时间来自已核准配置',
       '同一对象和kind无未关闭告警时创建OPEN；已有未关闭告警将新增证据追加到AuditLog.detail；恢复条件满足置recovery=RECOVERED及recoveredAt；不自动关闭或验收工单',
       '告警与审计整体回滚，保留源事件待幂等重放；不伪造告警已恢复')
action('ALARM_ACK','alarmId,note,expectedVersion','Alarm,AuditLog','ALARM-LIST,OVERVIEW,RUN-DETAIL,AUDIT',
       'OPERATOR、MANAGER或ADMIN；status=OPEN；说明非空','写acknowledgedBy/At，status=ACKNOWLEDGED；不更改recovery也不自动停泵','回滚确认记录；保留处理说明，展示告警已被他人更新')
action('WORKORDER_CREATE','alarmId?,workOrderDraft,expectedVersion?','WorkOrder,Alarm,AuditLog','ALARM-LIST,WORKORDER-LIST,OVERVIEW,AUDIT',
       'MANAGER或ADMIN；责任人TECHNICIAN且同农场ENABLED；关联告警未关闭；不存在同告警未完成工单；到期时间晚于创建',
       '创建ASSIGNED工单，关联告警置ASSIGNED；不改变物理恢复状态','整体回滚工单和告警；保留故障类型、责任人及到期时间')
action('ALARM_CLOSE','alarmId,resolution,expectedVersion','Alarm,AuditLog','ALARM-LIST,OVERVIEW,AUDIT',
       'MANAGER或ADMIN；recovery=RECOVERED；status in ACKNOWLEDGED,ASSIGNED；关联工单已COMPLETED或不存在；说明非空',
       '置CLOSED并写closedAt和resolution，保留异常持续时间','告警原状态保留，未恢复或未验收分别定位原因')
action('WORKORDER_ACCEPT','workOrderId,expectedVersion','WorkOrder,AuditLog','WORKORDER-LIST,ALARM-LIST,AUDIT',
       'TECHNICIAN且assigneeId=session.userId；status in ASSIGNED,RETURNED','置IN_PROGRESS并写startedAt，保留既有退回记录','保持待接单状态；已被更新则刷新单卡')
action('WORKORDER_SUBMIT','workOrderId,resultNote,expectedVersion','WorkOrder,AuditLog','WORKORDER-LIST,ALARM-LIST,AUDIT',
       '本人负责的TECHNICIAN；status=IN_PROGRESS；结果说明不少于12字','置PENDING_ACCEPTANCE并保存排查结论；不直接关闭Alarm','回滚状态；保留排查输入和现场观察')
action('WORKORDER_APPROVE','workOrderId,note,expectedVersion','WorkOrder,AuditLog','WORKORDER-LIST,ALARM-LIST,AUDIT',
       'MANAGER或ADMIN；status=PENDING_ACCEPTANCE；关联故障已恢复或无告警；验收说明非空','置COMPLETED并写acceptedBy/completedAt；告警仍需独立关闭','保持待验收，保留验收说明；故障持续时阻止通过')
action('WORKORDER_RETURN','workOrderId,note,expectedVersion','WorkOrder,AuditLog','WORKORDER-LIST,ALARM-LIST,AUDIT',
       'MANAGER或ADMIN；status=PENDING_ACCEPTANCE；退回理由非空','置RETURNED，保留原结果并追加退回说明，交回原责任人','不改变待验收状态；保留退回原因')
action('BASELINE_SAVE','baselineDraft,expectedVersion?,clientRequestId','WaterBaseline,AuditLog','WATER-REPORT,AUDIT',
       'MANAGER或ADMIN；参考面积和水量>0；来源与可比作物窗口齐全；seasonId属于fieldId',
       '保存核准基准和approvedBy；同田块同季仅一个ENABLED基准；重新派生节水指标','旧基准与报表保持；保留来源、日期与水量输入')
action('EXPORT_CREATE','filterSnapshot,clientRequestId','ExportJob,AuditLog','WATER-REPORT,AUDIT',
       '有用水报表导出权；区间合法且不超过366天；字段按角色脱敏',
       '创建QUEUED任务，固定来源版本和过滤快照；服务端任务生成文件，不同步伪造下载成功','不创建任务或空文件；保留查询条件和导出选项')
action('EXPORT_FINISH','exportId,fileMetadata,expectedVersion','ExportJob,AuditLog','WATER-REPORT,AUDIT',
       '仅服务端导出worker；status in QUEUED,PROCESSING；文件校验通过','写READY、文件URL、checksum、行数和到期时间；失败任务写FAILED并记录原因','元数据失败保持可重试PROCESSING，不公布不完整文件')
action('USER_SAVE','userDraft,expectedVersion?,clientRequestId','User,AuditLog','SETTINGS,AUDIT',
       'ADMIN；账号唯一；手机号格式有效；角色与田块范围一致；不得移除最后一个启用ADMIN','创建或更新账号授权；服务端撤销受影响旧令牌并重新鉴权','整笔回滚账号及权限；保留非密钥输入，定位重复账号或最后管理员约束')
action('USER_DISABLE','userId,reason,expectedVersion','User,AuditLog','SETTINGS,AUDIT',
       'ADMIN；目标非当前账号且非最后启用ADMIN；status=ENABLED','置DISABLED并撤销服务端令牌；已执行灌溉由任务层继续，不删除历史责任记录','保持启用与旧授权，保留停用原因')
action('USER_ENABLE','userId,expectedVersion','User,AuditLog','SETTINGS,AUDIT',
       'ADMIN；status=DISABLED；授权范围当前仍有效','置ENABLED；下次登录使用当前角色与范围，不恢复失效令牌','保持停用，弹窗显示已失效田块授权')
action('POLICY_SAVE','policyId,policyDraft,expectedVersion','SystemPolicy,AuditLog','SETTINGS,DEVICE-DETAIL,RUN-DETAIL,PLAN-EDIT,AUDIT',
       'ADMIN；超时为正且动作确认时限>=通信应答时限；联动参数须现场签核；无受影响活动指令',
       '原子保存超时和调度参数；联动序列变更使capabilitySignoff失效，自动控制须重新核验','整体回滚；保留参数草稿；正在执行的命令继续使用原快照')

# Authentication and shell. Role is provided by the authenticated account.
edit('AUTH-LOGIN','ACCOUNT','农场账号','draft.login.account','去除首尾空格，长度3至48字符','会话未建立且未提交登录')
edit('AUTH-LOGIN','PASSWORD','登录密码','draft.login.password','密码只保存在内存，不持久化','会话未建立且未提交登录',kind='password_input')
comp('AUTH-LOGIN','PASSWORD-VISIBILITY','显示密码','icon_button','click','TOGGLE','登录未提交',
     '切换ui.passwordVisible并保留输入焦点','不更改密码、会话或正式实体','图标与aria-pressed同步',
     '渲染失败维持掩码输入，不复制密码','认证中禁用','不进入路由历史',
     action=local('UI_PASSWORD_VISIBILITY','仅切换ui.passwordVisible','UI_STATE'))
comp('AUTH-LOGIN','SUBMIT','登录','button','click','SUBMIT','账号密码非空且认证服务可达',
     '登录按钮Loading，锁定凭据输入','AUTHENTICATE通过后建立Session','清空密码，使用服务端角色replace到OVERVIEW，清除认证历史',
     '保留账号，清空密码，表单下显示认证失败或连接失败原因','空凭据或认证中禁用','认证页不留在业务返回栈',action='AUTHENTICATE',target='OVERVIEW')
for sid,label in [('OVERVIEW','灌溉总览'),('FIELD-LIST','田块与种植'),('NETWORK','管网与分区'),('DEVICE-LIST','设备接入'),('MONITOR','墒情监测'),('STRATEGY-LIST','灌溉策略'),('PLAN-LIST','灌溉计划'),('RUN-LIST','灌溉运行'),('ALARM-LIST','运行告警'),('WORKORDER-LIST','巡检维护'),('WATER-REPORT','用水分析'),('SETTINGS','系统配置'),('AUDIT','审计日志')]:
    cid=comp('WEB-SHELL','NAV-'+sid,label,'nav_item','click','RESOLVE_BRANCH',f'Session有效且有{sid}访问权',
        f'将ui.pendingNavigation固定为{sid}并记录当前页过滤分页焦点','只变更导航上下文，不修改灌溉实体',
        f'执行BRANCH-NAV-{sid}，进入目标或打开草稿确认','无命中BLOCK_AND_REPORT，保留当前页和草稿',
        '无权限入口隐藏；业务提交中禁止切换','返回恢复来源筛选页码和选中项',branch='BRANCH-NAV-'+sid,family='NAVIGATE')
    aid=local('NAV_SHELL_'+sid.replace('-','_'),f'Router进入{sid}，恢复模块快照，不写业务实体')
    branches('BRANCH-NAV-'+sid,cid,[br('ui.hasDirtyDraft == true','OPEN_DISCARD_DRAFT','OPEN_DIALOG',dialog='DIALOG-DISCARD-DRAFT'),br('ui.hasDirtyDraft == false',aid,'NAVIGATE',target=sid)])
backcid=comp('WEB-SHELL','BACK','返回','icon_button','click','RESOLVE_BRANCH','非AUTH-LOGIN或OVERVIEW且无业务提交锁',
    '确定ui.returnTarget为已授权真实来源或manifest.back_fallback','只保存返回快照，不修改Field、Plan和运行状态',
    '按BRANCH-GLOBAL-BACK返回确定页面或询问放弃草稿','无效上下文BLOCK_AND_REPORT并保持当前页',
    '根页隐藏；业务提交中禁用','目标恢复查询、页码、选中行和滚动',branch='BRANCH-GLOBAL-BACK',family='NAVIGATE')
local('OPEN_DISCARD_DRAFT','打开DIALOG-DISCARD-DRAFT，设置待去目标，不清除草稿')
local('DRAFT_DISCARD_AND_RETURN','只清除活动Draft；ui.pendingNavigation或ui.returnTarget经manifest和权限校验后导航；不撤销已受理任务')
items=[br('ui.hasDirtyDraft == true','OPEN_DISCARD_DRAFT','OPEN_DIALOG',dialog='DIALOG-DISCARD-DRAFT')]
for sid in S:
    if sid!='AUTH-LOGIN':
        aid=local('RETURN_'+sid.replace('-','_'),f'返回{sid}并恢复已有筛选分页和滚动快照')
        items.append(br(f"ui.hasDirtyDraft == false and ui.returnTarget == '{sid}'",aid,'NAVIGATE',target=sid,params='Router.savedReturnParams'))
branches('BRANCH-GLOBAL-BACK',backcid,items)
lc=opendialog('WEB-SHELL','LOGOUT','退出登录','DIALOG-LOGOUT','Session有效且无未提交事务','居中显示当前账号与退出确认','不立即清除会话','确认调用SESSION_LOGOUT','失败保持当前登录态','业务提交中禁用','取消返回账号菜单')
overlay('DIALOG-LOGOUT','GLOBAL','退出当前账号','NONE','退出登录','SESSION_LOGOUT',[lc],'Session有效；退出不停止服务端灌溉任务','校验sessionId',
        '撤销会话、关闭弹窗并replace AUTH-LOGIN，清理媒体流和订阅','撤销失败保留会话和弹窗，允许重试')
overlay('DIALOG-DISCARD-DRAFT','GLOBAL','放弃未保存的修改','NONE','放弃修改','DRAFT_DISCARD_AND_RETURN',
    [backcid]+[c['component_id'] for sid,c in COMP if sid=='WEB-SHELL' and c['component_id'].startswith('WEB-SHELL.NAV-')],
    'ui.hasDirtyDraft=true且待去目标已解析','校验草稿归属和待去目标，禁止提交业务字段','清空草稿及错误，进入已解析页面','目标失效时保留草稿与原页')

def list_controls(sid,qid,subject,filters,impact):
    path="ui['"+sid+"']"
    readcomp(sid,'SEARCH','搜索'+subject,qid,path+'.query',impact,'未找到'+subject+'时显示清除筛选入口','search_input','input')
    readcomp(sid,'FILTER',filters,qid,path+'.filters',impact,'无结果显示0条并保留条件','filter_group','change')
    readcomp(sid,'PAGINATION','分页与每页条数',qid,path+'.page,pageSize',impact,'越界定位过滤全集最后有效页','pagination','change')
    comp(sid,'RESET-FILTER','清除筛选','button','click','UPDATE_STATE','有非默认筛选且未在读取',
        f'清空{subject}条件，将page置1，保留pageSize',f'只更新{path}并dispatch {qid}',f'{impact}恢复授权全集，total与分页同源',
        '保留默认条件和最近结果，显示读取失败及重试','已是默认筛选时禁用','保存清除后的查询快照',
        action=local('RESET_FILTER_'+sid.replace('-','_'),f'清空{path}.query/filters，page=1，dispatch {qid}'),family='QUERY')

def form_save(sid,bid,ca,ua,idfield,draft):
    domain_checks={'FIELD-EDIT':'田块编码唯一；面积不小于启用分区覆盖；负责人同农场有效',
        'STRATEGY-EDIT':'作物生育阶段匹配分区；MOISTURE具备有效阈值；AUTO反馈、本地保护与联动签核有效',
        'PLAN-EDIT':'步骤非空且分区不重复；水量时长为正；供水容量与时间冲突由服务端重新检查'}[sid]
    create_spec=next(a for a in ACTIONS if a['action_id']==ca)
    update_spec=next(a for a in ACTIONS if a['action_id']==ua)
    cid=comp(sid,'SAVE','保存','button','click','RESOLVE_BRANCH',f'{draft}校验通过；MANAGER或ADMIN；无其他提交',
        f'校验{draft}，通过后锁定保存区',f'{bid}按mode调用{ca}或{ua}，不直接写Store',
        f'成功清空{draft}，按分支返回固定页面并刷新affected_screens',f'整体回滚并保留{draft}、行顺序和首个错误',
        '提交中禁用，字段错误就近提示','失败留表单，成功replace避免重复历史',branch=bid,family='SUBMIT',template='SUBMIT')
    contract=next(c for ss,c in COMP if c['component_id']==cid)
    contract['preconditions']+='；'+domain_checks
    contract['data_consequence']+=f'；{ca}：{create_spec["success_result"]}；{ua}：{update_spec["success_result"]}'
    contract['failure_consequence']+=f'；{ca}：{create_spec["failure_result"]}；{ua}：{update_spec["failure_result"]}'
    target={'FIELD-EDIT':'FIELD-DETAIL','STRATEGY-EDIT':'STRATEGY-LIST','PLAN-EDIT':'PLAN-LIST'}[sid]
    branches(bid,cid,[br("routeParams.mode == 'create'",ca,target=target,params=f'{idfield}=actionResult.{idfield}',tx='TX-'+ca.replace('_','-')),
        br(f"routeParams.mode == 'edit' and routeParams.{idfield} != null",ua,target=target,params=f'{idfield}=routeParams.{idfield}',tx='TX-'+ua.replace('_','-'))])

def form_tools(sid,draft,qid,target):
    cid=comp(sid,'CANCEL','取消编辑','button','click','RESOLVE_BRANCH','无未完成的业务提交',f'固定ui.pendingNavigation={target}，读取草稿dirty',
        '只处理草稿和导航，不写业务实体','脏草稿打开DIALOG-DISCARD-DRAFT；干净草稿返回固定列表','无命中保留输入并BLOCK_AND_REPORT',
        '保存中禁用',f'取消放弃时留在{sid}保留输入',branch='BRANCH-CANCEL-'+sid,family='NAVIGATE')
    aid=local('CANCEL_'+sid.replace('-','_'),f'无脏草稿时进入{target}并恢复目录快照')
    branches('BRANCH-CANCEL-'+sid,cid,[br('ui.hasDirtyDraft == true','OPEN_DISCARD_DRAFT','OPEN_DIALOG',dialog='DIALOG-DISCARD-DRAFT'),br('ui.hasDirtyDraft == false',aid,'NAVIGATE',target=target)])
    next(o for o in OVERLAYS if o['overlay_id']=='DIALOG-DISCARD-DRAFT')['trigger_component_ids']+='|'+cid
    rc=opendialog(sid,'RESET','重置表单','DIALOG-RESET-'+sid,f'{draft}已修改且无提交锁','居中确认重置到本次读取基线','确认前不改输入',
        '确认只恢复Draft初始值','打开失败保留现值','未修改或保存中禁用',f'取消重置回{sid}保留输入')
    reset_detail={
        'FIELD-EDIT':('显示将恢复的田块编码、边界、面积、土壤和负责人','恢复田块事实Draft，不改当前种植季和管网分区；重新派生面积覆盖校验'),
        'STRATEGY-EDIT':('显示将恢复的触发模式、阈值、阶段、分区和执行方式','还原策略规则Draft；重新计算阈值显隐和AUTO能力门槛，不追改已发布快照'),
        'PLAN-EDIT':('显示将丢弃的步骤增删、轮灌顺序、时间和目标水量','恢复本次计划及全部步骤基线，保留原stepDraftId，清除过期资源检查hash并重算Draft总量'),
        'SETTINGS':('显示将恢复的过期秒数、应答时限、动作时限和计划天数','只恢复运行参数Draft，不改账号授权Tab，不重新签核现场联动')}
    reset_contract=next(c for ss,c in COMP if c['component_id']==rc)
    reset_contract['immediate_feedback']=reset_detail[sid][0]+'，确认前保留现有字段'
    reset_contract['data_consequence']=reset_detail[sid][1]
    reset_contract['success_consequence']=reset_detail[sid][1]+'；dirty=false，保留当前编辑会话'
    ra=local('RESET_DRAFT_'+sid.replace('-','_'),f'{draft}恢复本次{qid}基线；create恢复空表单，清除错误和dirty，不改正式实体','DRAFT,UI_STATE')
    overlay('DIALOG-RESET-'+sid,sid,'重置尚未保存的表单','NONE','重置',ra,[rc],f'{draft}已修改且无提交锁','校验编辑会话和基线所属实体',
        '关闭并恢复本次读取基线，清除校验错误','基线失效保留原草稿并显示重新读取入口')

readcomp('OVERVIEW','REFRESH','刷新态势',Q['OVERVIEW'],'ui.overview.date,farmId','指标卡、态势图和任务带','无运行显示当前无灌溉任务')
readcomp('OVERVIEW','DATE','统计日期',Q['OVERVIEW'],'ui.overview.date','当日用水和任务摘要','无账本时显示0及单位','date_picker','change')
for k,label,t,p,ctx,kind in [
 ('RUNNING-CARD','正在灌溉','RUN-LIST','statusGroup=ACTIVE','统计日期和地图缩放','card'),
 ('ALARM-CARD','待处理告警','ALARM-LIST','statusGroup=UNCLOSED','告警排序','card'),
 ('WATER-CARD','今日用水','WATER-REPORT','range=today','当前日期','card'),
 ('FIELD-NODE','态势图田块','FIELD-DETAIL','fieldId=event.entityId','地图视口及选中田块','row'),
 ('RUN-ROW','运行任务编号','RUN-DETAIL','runId=event.entityId','任务带位置','row'),
 ('OFFLINE-CARD','离线设备','DEVICE-LIST','connection=OFFLINE','当前农场','card')]:
    nav('OVERVIEW',k,label,t,p,'有目标数据和页面查看权',ctx,kind)
list_controls('FIELD-LIST',Q['FIELD-LIST'],'田块','作物、生育阶段和负责人','田块卡片、面积汇总及总数')
nav('FIELD-LIST','CREATE','新增田块','FIELD-EDIT','mode=create','MANAGER或ADMIN','查询与页码')
nav('FIELD-LIST','OPEN','田块名称','FIELD-DETAIL','fieldId=event.entityId','Field存在且在授权范围','卡片筛选、页码和滚动','card_repeat')
sc=opendialog('FIELD-LIST','SEASON','维护种植季','DIALOG-SEASON','MANAGER或ADMIN且选中田块存在',
    '从SELECT-FIELDS初始化种植季弹窗Draft','不立即改作物或生育阶段','SEASON_SAVE后目录详情使用同一种植季','读取失败保留卡片并显示错误',
    '无田块维护权隐藏；该田块提交中禁用','关闭恢复原卡片和页码',params='fieldId=event.entityId',kind='row')
overlay('DIALOG-SEASON','FIELD-LIST','维护田块种植季',
    'fieldId:string|required|event.entityId;crop:string|required|overlayDraft;variety:string|required|overlayDraft;plantingDate:date|required|overlayDraft;harvestDate:date|optional|overlayDraft;stage:CropStage|required|overlayDraft',
    '保存种植季','SEASON_SAVE',[sc],'MANAGER或ADMIN且田块版本有效','品种必填，种植日期<=收获日期，stage取CropStage，每田块仅一个活动季',
    '关闭弹窗并刷新FIELD-LIST、FIELD-DETAIL、STRATEGY-LIST和WATER-REPORT','保留全部种植输入，定位日期错误或版本冲突')
nav('FIELD-DETAIL','EDIT','编辑田块','FIELD-EDIT','mode=edit;fieldId=routeParams.fieldId','MANAGER或ADMIN','详情Tab、种植季与历史页码')
readcomp('FIELD-DETAIL','TAB','档案、墒情与灌溉记录',Q['FIELD-DETAIL'],'ui.fieldDetail.activeTab','选中Tab数据区','空Tab显示暂无记录','tab_group','change')
nav('FIELD-DETAIL','ZONE','查看分区','NETWORK','zoneId=event.entityId','分区属于当前田块','当前种植季与Tab','row')
nav('FIELD-DETAIL','RUN','查看灌溉记录','RUN-DETAIL','runId=event.entityId','运行账本与当前田块关联','历史页码和日期','row')
readcomp('FIELD-DETAIL','HISTORY-PAGE','灌溉记录分页',Q['FIELD-DETAIL'],'ui.fieldDetail.historyPage,seasonId','田块灌溉记录','空记录保留种植季选择','pagination','change')
qrf=opendialog('FIELD-DETAIL','QR','查看田块二维码','PREVIEW-FIELD-QR','Field有ACTIVE QrCode',
    '居中预览，真实编码登记payload','仅生成二维码图像和对象URL','显示田块名称、fieldId和编码文本','未登记时显示未登记原因，不生成装饰图案',
    '无ACTIVE码禁用','关闭释放URL并恢复焦点')
overlay('PREVIEW-FIELD-QR','FIELD-DETAIL','田块识别码','payload:string|readonly|SELECT-FIELD-DETAIL.QrCode.payload','NONE','NONE',[qrf],
    'ACTIVE码存在','UTF-8 URL编码；标准QR解码器必须还原相同payload','关闭释放图像URL，正式实体不变','生成失败保留编码文本并提供重新生成图像',typ='PREVIEW')
for k,label,p,v,kind in [('CODE','田块编码','code','同农场唯一，FLD-JZ-四位大写字母数字','input'),('NAME','田块名称','name','2至40字','input'),('AREA','田块面积（亩）','areaMu','>0且不小于启用分区总面积','number_input'),('SOIL','土壤类型','soilType','现场土壤分类有效','select'),('LOCATION','田块位置','location','坐标可解析且在当前农场','coordinate_input'),('MANAGER','田块负责人','managerId','同农场ENABLED账号','select')]:
    edit('FIELD-EDIT',k,label,'draft.field.'+p,v,'MANAGER或ADMIN；mode有效且无版本冲突',kind)
form_save('FIELD-EDIT','BRANCH-FIELD-SAVE','FIELD_CREATE','FIELD_UPDATE','fieldId','draft.field')
form_tools('FIELD-EDIT','draft.field',Q['FIELD-EDIT'],'FIELD-LIST')

readcomp('NETWORK','SOURCE','水源与泵站',Q['NETWORK'],'ui.network.sourceNodeId','管网拓扑与供水占用','无节点显示尚未同步现场管网，并提供本页重试加载','select','change')
comp('NETWORK','NODE','管网节点','tree_node','click','UPDATE_STATE','节点在SELECT-NETWORK授权树且不存在环',
    '高亮nodeId，在同页显示下属分区和供水约束','只改ui.network.selectedNodeId','参数区从同一PipeNode展示容量和埋深间距',
    '节点失效则清除该选择并刷新树，不改正式拓扑','越权节点不可选','恢复选中节点及树展开状态',
    action=local('UI_NETWORK_SELECT','选择nodeId并由SELECT-NETWORK派生参数区','UI_STATE'),family='OBJECT_SELECT')
zc=opendialog('NETWORK','ZONE-EDIT','维护轮灌分区','DIALOG-ZONE','MANAGER或ADMIN；节点无活动占用','居中展示田块、阀门及计量点候选',
    '只创建zoneDraft，不立即绑定阀门','保存后刷新拓扑、覆盖面积和计划候选','读取失败保留当前节点','运行占用或无权时禁用并说明','关闭恢复节点和缩放')
overlay('DIALOG-ZONE','NETWORK','轮灌分区关联',
    'zoneId:string|optional|ui.network.selectedZoneId;name:string|required|overlayDraft;fieldId:string|required|Field;sourceNodeId:string|required|ui.network.selectedNodeId;valveDeviceId:string|required|Device;meterPointId:string|optional|Point;soilPointIds:string[]|optional|Point;areaMu:decimal|required|overlayDraft;designFlowM3h:decimal|required|overlayDraft;accountingMethod:MeasurementMethod|required|overlayDraft;allocationRule:string|optional|overlayDraft',
    '保存分区','ZONE_SAVE',[zc],'ADMIN或MANAGER且无活动占用','面积不超田块，阀门同农场且未被重复关联；MEASURED需独立表；ALLOCATED需批准分摊规则',
    '关闭并选中新zoneId，刷新NETWORK、FIELD-DETAIL、PLAN-LIST、MONITOR及WATER-REPORT','保持关联选择并定位面积、阀门或计量依据错误')
pc=opendialog('NETWORK','PIPE-EDIT','编辑管段与供水约束','DIALOG-PIPE','ADMIN或MANAGER；节点无活动占用',
    '居中显示埋深、间距、容量与并发上限Draft','确认前不影响资源检查','保存后旧检查hash失效','打开失败保留原节点',
    '活动占用时禁用并显示runId','关闭回节点参数区')
overlay('DIALOG-PIPE','NETWORK','管段参数与供水上限',
    'nodeId:string|required|ui.network.selectedNodeId;parentNodeId:string|optional|PipeNode;capacityM3h:decimal|required|overlayDraft;maxConcurrentZones:integer|required|overlayDraft;depthCm:decimal|required|overlayDraft;intervalCm:decimal|required|overlayDraft;designFlowM3h:decimal|required|overlayDraft',
    '保存约束','PIPE_SAVE',[pc],'ADMIN或MANAGER且节点无占用','父子无环，容量>0，并发>=1，埋深间距为现场登记值',
    '保存后关闭，NETWORK与PLAN-LIST重新计算供水约束','保留全部参数输入，不部分保存容量')
nav('NETWORK','DEVICE','查看关联阀门','DEVICE-DETAIL','deviceId=event.deviceId','关联Device存在','节点展开、分区与缩放','row')
comp('NETWORK','ZONE-SELECT','轮灌分区名称','row','click','UPDATE_STATE','分区属于选中供水节点且在授权田块内',
    '高亮分区行并在同页参数区显示阀门、计量方法和面积','只设置ui.network.selectedZoneId，实体从SELECT-NETWORK引用',
    '维护分区入口绑定该zoneId和version，不改现有供水关系','分区已失效时清空选择并重新读取当前节点',
    '无权分区不显示','保留当前节点展开和所选分区',
    action=local('UI_NETWORK_ZONE_SELECT','只设selectedZoneId并显示该分区事实','UI_STATE'),family='OBJECT_SELECT')
zn=opendialog('NETWORK','ZONE-ADD','新增轮灌分区','DIALOG-ZONE','MANAGER或ADMIN；选中节点有可分配供水关系',
    '打开居中分区表单并明确zoneId=null、sourceNodeId=当前节点','只创建全新分区Draft，不覆盖当前已选分区',
    'ZONE_SAVE创建稳定新zoneId并刷新覆盖面积','候选无可分配阀门时保留拓扑并展示原因',
    '无维护权或节点不可用时禁用','取消恢复原节点与原分区选择',params='zoneId=NONE;sourceNodeId=ui.network.selectedNodeId')
next(o for o in OVERLAYS if o['overlay_id']=='DIALOG-ZONE')['trigger_component_ids']+='|'+zn
next(c for sid,c in COMP if c['component_id']=='NETWORK.ZONE-EDIT')['route_params']='zoneId=ui.network.selectedZoneId;sourceNodeId=ui.network.selectedNodeId'
zone_overlay=next(o for o in OVERLAYS if o['overlay_id']=='DIALOG-ZONE')
zone_overlay['fields']=zone_overlay['fields'].replace('ui.network.selectedZoneId','overlayContext.zoneId').replace('ui.network.selectedNodeId','overlayContext.sourceNodeId')

list_controls('DEVICE-LIST',Q['DEVICE-LIST'],'设备','设备类型、连接状态与接入验证','设备台账和在线能力统计')
nav('DEVICE-LIST','OPEN','设备编号','DEVICE-DETAIL','deviceId=event.entityId','有设备查看权','台账筛选、页码和选中设备','row')
dc=opendialog('DEVICE-LIST','REGISTER','登记接入设备','DIALOG-DEVICE','ADMIN；网关候选已读取',
    '打开接入表单，不预填虚构厂家或协议','只初始化deviceDraft；凭据输入不进入Store','DEVICE_SAVE后新设备为UNVERIFIED',
    '网关读取失败保留台账，显示重新读取','无ADMIN权限隐藏入口','关闭恢复设备台账筛选')
de=opendialog('DEVICE-LIST','EDIT','修改接入配置','DIALOG-DEVICE','ADMIN；设备无未决现场指令',
    '读取设备版本并居中编辑接入元数据','只修改deviceDraft；不直接改能力标志','保存配置变化后verification=UNVERIFIED',
    '设备被更新时保留旧台账并显示版本差异','存在未决指令时禁用并显示commandId','关闭回原设备行',params='deviceId=event.entityId',kind='row')
overlay('DIALOG-DEVICE','DEVICE-LIST','设备接入配置',
    'deviceId:string|optional|event.entityId;code:string|required|overlayDraft;name:string|required|overlayDraft;kind:DeviceKind|required|overlayDraft;manufacturer:string|required|overlayDraft;model:string|required|overlayDraft;gatewayDeviceId:string|optional|Device;protocol:string|required|overlayDraft;endpoint:string|required|overlayDraft;secret:string|optional|memoryOnly',
    '保存接入','DEVICE_SAVE',[dc,de],'ADMIN且无活动指令','编码唯一，协议为已实现适配器标识，endpoint可解析，凭据只提交密钥服务不回显',
    '关闭后刷新DEVICE-LIST、DEVICE-DETAIL及NETWORK，需重新验证能力','保留非敏感字段，清空secret，定位连接地址或重复编码')
vc=opendialog('DEVICE-DETAIL','VERIFY','验证接入能力','DIALOG-VERIFY','ADMIN；设备ONLINE且无活动指令',
    '居中列出只读握手与反馈验证项目','不自动启动水泵，不修改capabilities','DEVICE_VERIFY记录实际验证结果','握手资料不全保留当前能力并显示未验证',
    'OFFLINE或缺少适配器时禁用并说明','关闭返回能力矩阵')
overlay('DIALOG-VERIFY','DEVICE-DETAIL','验证设备通信与反馈','deviceId:string|readonly|routeParams.deviceId',
    '开始验证','DEVICE_VERIFY',[vc],'ADMIN且设备ONLINE','仅执行适配器声明的只读验证；真实动作联调需现场签核后独立执行',
    '保存VERIFIED或FAILED结果后关闭，刷新能力矩阵与控制资格','接口失败保持原能力，显示协议错误，不伪造可控制状态')
pm=opendialog('DEVICE-DETAIL','POINT-MAP','维护点位映射','DIALOG-POINT','ADMIN；设备无控制中任务',
    '打开点位地址、量纲、缩放与有效期表单','只初始化pointDraft，历史读数不变','POINT_SAVE后能力验证失效，监测按新映射读取',
    '点位读取失败保留当前点表','活动任务依赖此点位时禁用','关闭回点位列表并恢复选中项',params='pointId=event.pointId',kind='row')
overlay('DIALOG-POINT','DEVICE-DETAIL','点位映射配置',
    'pointId:string|optional|event.pointId;name:string|required|overlayDraft;kind:PointKind|required|overlayDraft;address:string|required|overlayDraft;unit:string|required|overlayDraft;zoneId:string|optional|IrrigationZone;depthCm:decimal|required|overlayDraft;rangeMin:decimal|required|overlayDraft;rangeMax:decimal|required|overlayDraft;scale:decimal|required|overlayDraft;offset:decimal|required|overlayDraft;staleAfterSec:integer|required|overlayDraft',
    '保存点位','POINT_SAVE',[pm],'ADMIN且点位未被活动控制引用','同设备地址唯一；rangeMin<rangeMax；有效期>0；含水率为%VWC、压力为MPa、流量为m³/h',
    '关闭并刷新DEVICE-DETAIL、MONITOR、NETWORK和RUN-DETAIL','保留地址单位缩放输入，点位与设备修改整体回滚')
pa=opendialog('DEVICE-DETAIL','POINT-ADD','登记采集点位','DIALOG-POINT','ADMIN；设备存在且无受影响活动控制',
    '打开空白点位表单，固定deviceId为当前设备且pointId=null','只创建新pointDraft，不改变现有点位列表',
    'POINT_SAVE创建新pointId，设备能力需重新验证','协议尚未核实时保留草稿并标识待核对地址',
    '无ADMIN权限或活动控制引用该映射时禁用','取消返回现有点位表',params='pointId=NONE;deviceId=routeParams.deviceId')
next(o for o in OVERLAYS if o['overlay_id']=='DIALOG-POINT')['trigger_component_ids']+='|'+pa
point_overlay=next(o for o in OVERLAYS if o['overlay_id']=='DIALOG-POINT')
point_overlay['fields']=point_overlay['fields'].replace('event.pointId','overlayContext.pointId')
cc=opendialog('DEVICE-DETAIL','CALIBRATE','登记传感器校准','DIALOG-CALIBRATION','ADMIN或TECHNICIAN；点位可校准且未用于活动自动触发',
    '居中展示点位原offset、当前测量值和参考值输入','暂不修改校准系数','校准后新增Calibration并刷新最新读数换算','点位缺失保留诊断页',
    '运行占用、不可校准或读数缺失时禁用并说明','关闭回校准记录区域',params='pointId=event.pointId',kind='row')
overlay('DIALOG-CALIBRATION','DEVICE-DETAIL','传感器参考值校准',
    'pointId:string|readonly|event.pointId;referenceValue:decimal|required|overlayDraft;measuredValue:decimal|required|overlayDraft;note:string|required|overlayDraft',
    '提交校准','POINT_CALIBRATE',[cc],'ADMIN或TECHNICIAN；点位可校准且无控制占用','参考值在量程内，记录实测值及现场依据；新offset=referenceValue-measuredValue',
    '关闭并刷新校准记录与监测换算值；旧原始数据保留','旧offset保持，保留参考值和说明，标记校准冲突')
readcomp('DEVICE-DETAIL','REFRESH','刷新反馈',Q['DEVICE-DETAIL'],'routeParams.deviceId','反馈、心跳及点位状态','无读数显示未采集，不显示0')
readcomp('DEVICE-DETAIL','TAB','点位、校准与诊断',Q['DEVICE-DETAIL'],'ui.device.activeTab','选中设备Tab','无记录显示暂无校准或诊断记录','tab_group','change')
sq=opendialog('DEVICE-DETAIL','SCAN','扫码查找现场设备','SCANNER-ASSET','有设备查看权；摄像头仅在用户点击后申请',
    '居中打开扫描器，默认可手输或扫码枪输入','仅保存scanDraft和ui.scanResolution，不写Device','QUERY_QR_RESOLVE后由BRANCH-SCAN-RESULT进入设备或田块详情',
    '摄像头拒绝时保留手动输入，未知码不导航','识别请求中禁用重复识别','取消停止轨道并返回当前设备')
local('SCAN_RESOLVE','把scanDraft.payload交给QUERY_QR_RESOLVE，成功后dispatch BRANCH-SCAN-RESULT','UI_STATE,DEVICE_API')
overlay('SCANNER-ASSET','DEVICE-DETAIL','识别设备或田块编码',
    'payload:string|required|scanDraft;cameraId:string|optional|ui.mediaDevices',
    '识别','SCAN_RESOLVE',[sq],'已登录且有资产查看权','只接受https://irrigation.runhe.example/asset/{device|field}/{id}?v=1&c={checksum}；校验域、类型、主键及校验和',
    '清理摄像头并执行BRANCH-SCAN-RESULT到固定详情页','保留扫描输入，显示无效、过期、越权或外场码，允许重新扫描',typ='SCANNER')
nav('DEVICE-DETAIL','MONITOR','查看点位曲线','MONITOR','zoneId=event.zoneId;pointId=event.pointId','点位存在且属于可查看分区','点表滚动和选中点位','row')
readcomp('MONITOR','CONDITIONS','分区、土层深度与指标',Q['MONITOR'],'ui.monitor.zoneId,depthCm,kind','曲线和原始读数表','缺测显示断点与原因','filter_group','change')
readcomp('MONITOR','RANGE','监测时间区间',Q['MONITOR'],'ui.monitor.startAt,endAt','区间读数和数据质量统计','无读数保留时间轴与缺测提示','date_range','change')
readcomp('MONITOR','REFRESH','刷新监测',Q['MONITOR'],'ui.monitor.filters','最近读数、曲线及过期标识','从未采集显示未接入')
readcomp('MONITOR','PAGINATION','读数分页',Q['MONITOR'],'ui.monitor.page,pageSize','原始读数明细','total按原始过滤全集计算','pagination','change')
comp('MONITOR','CURSOR','曲线数据点','chart_point','click','UPDATE_STATE','点位和读数存在于SELECT-MONITOR过滤结果',
    '固定曲线游标，展示observedAt、深度、值、质量与readingId','只改ui.monitor.cursorReadingId','读数卡与表行高亮对应同一readingId',
    '该读数已被过滤移除时清除游标，不生成虚构值','缺测断点不可选，展示缺测原因','离开保存区间但不保留无效游标',
    action=local('UI_MONITOR_CURSOR','按readingId定位已有读数，不保存曲线统计副本','UI_STATE'),family='OBJECT_SELECT')
nav('MONITOR','DEVICE','查看传感器','DEVICE-DETAIL','deviceId=event.deviceId','所选读数对应设备存在','曲线时间区间、深度和游标','row')

list_controls('STRATEGY-LIST',Q['STRATEGY-LIST'],'策略','作物、生育阶段、触发方式与启用状态','策略矩阵及结果总数')
nav('STRATEGY-LIST','CREATE','新建策略','STRATEGY-EDIT','mode=create','MANAGER或ADMIN','矩阵作物和阶段筛选')
nav('STRATEGY-LIST','EDIT','编辑策略','STRATEGY-EDIT','mode=edit;strategyId=event.entityId','MANAGER或ADMIN且策略存在','矩阵筛选与行位置','row')
tc=comp('STRATEGY-LIST','TOGGLE','启用或停用策略','row','click','RESOLVE_BRANCH','MANAGER或ADMIN且选中策略存在',
    '读取所选Strategy.status和version，打开状态专用确认','确认前不改变状态和既有Plan快照','BRANCH-STRATEGY-TOGGLE打开启用或停用弹窗',
    '策略状态无法解析时BLOCK_AND_REPORT并刷新行','无权或该策略已有提交时禁用','关闭后保留矩阵筛选和当前行',branch='BRANCH-STRATEGY-TOGGLE')
local('OPEN_STRATEGY_ENABLE','打开DIALOG-STRATEGY-ENABLE，不修改状态')
local('OPEN_STRATEGY_DISABLE','打开DIALOG-STRATEGY-DISABLE，不修改状态')
branches('BRANCH-STRATEGY-TOGGLE',tc,[br("strategy.status == 'DISABLED'",'OPEN_STRATEGY_ENABLE','OPEN_DIALOG',dialog='DIALOG-STRATEGY-ENABLE'),br("strategy.status == 'ENABLED'",'OPEN_STRATEGY_DISABLE','OPEN_DIALOG',dialog='DIALOG-STRATEGY-DISABLE')])
for suffix,title,aid,pre,val,succ,fail in [
 ('ENABLE','启用灌溉策略','STRATEGY_ENABLE','策略DISABLED且分区能力有效','再次核验AUTO的现场签核和新鲜度','策略置ENABLED，刷新矩阵但不立即灌溉','保持DISABLED并展示缺失能力'),
 ('DISABLE','停用灌溉策略','STRATEGY_DISABLE','策略ENABLED','已发布计划独立保留，不当作同步取消','策略置DISABLED，停止新建议，已发布计划不变','保持ENABLED及确认上下文')]:
    overlay('DIALOG-STRATEGY-'+suffix,'STRATEGY-LIST',title,'strategyId:string|readonly|event.entityId',
        '确认'+title,aid,[tc],'MANAGER或ADMIN；'+pre,val,succ,fail)
simc=opendialog('STRATEGY-LIST','SIMULATE','试算灌溉建议','DIALOG-SIMULATION','策略存在且有查看权',
    '居中显示该策略及读取时刻，等待主动试算','只创建simulation UI，不创建Plan','试算后可将建议带到PLAN-EDIT草稿','缺测显示每区阻断原因，不伪造建议',
    '读取策略失败时禁用','取消不产生计划，回矩阵行',params='strategyId=event.entityId',kind='row')
overlay('DIALOG-SIMULATION','STRATEGY-LIST','按当前墒情试算',
    'strategyId:string|readonly|event.entityId;asOf:datetime|required|overlayDraft',
    '执行试算','QUERY_STRATEGY_SIMULATE',[simc],'策略存在且有查看权','asOf不得晚于服务器当前时间；读数须满足点位有效期',
    '保持弹窗显示SELECT-STRATEGY-SIMULATION，展示建议与逐区阻断原因','保留asOf和策略，显示读取失败，不创建任何计划')
for k,l,p,v,kind in [('NAME','策略名称','name','2至48字','input'),('CROP','适用作物与阶段','cropStage','作物和CropStage有效','crop_stage_select'),
 ('ZONES','适用轮灌分区','zoneIds','至少一个启用分区且种植季作物一致','multi_select'),('TRIGGER','触发方式','triggerMode','枚举SCHEDULE、VOLUME或MOISTURE','select'),
 ('THRESHOLD','含水率下限（%VWC）','thresholdVwc','MOISTURE必填且0<值<100，其他触发方式不参与判定','number_input'),('VOLUME','单区目标水量（m³）','targetVolumeM3','>0且不超过配置的单次水量上限','number_input'),
 ('DURATION','最长灌溉时长（分钟）','maxDurationMin','正整数，作为独立终止上限','number_input'),('WINDOW','允许灌溉时间窗口','allowedWindow','同日开始时间早于结束，跨日须显式拆成两个策略','time_range'),
 ('EXECUTION','执行方式','executionMode','AUTO须现场联动、反馈和本地保护全部签核，否则只允许建议或人工确认','select')]:
    edit('STRATEGY-EDIT',k,l,'draft.strategy.'+p,v,'MANAGER或ADMIN；策略版本可编辑',kind)
form_save('STRATEGY-EDIT','BRANCH-STRATEGY-SAVE','STRATEGY_CREATE','STRATEGY_UPDATE','strategyId','draft.strategy')
form_tools('STRATEGY-EDIT','draft.strategy',Q['STRATEGY-EDIT'],'STRATEGY-LIST')

list_controls('PLAN-LIST',Q['PLAN-LIST'],'灌溉计划','日期、泵站与计划状态','计划时间轴、清单与总数')
nav('PLAN-LIST','CREATE','编排计划','PLAN-EDIT','mode=create','MANAGER或ADMIN','所选泵站、日期和清单页码')
nav('PLAN-LIST','EDIT','调整计划','PLAN-EDIT','mode=edit;planId=event.entityId','MANAGER或ADMIN且Plan.status=DRAFT','泵站日历位置与清单筛选','row')
readcomp('PLAN-LIST','CALENDAR','时间轴日期与泵站',Q['PLAN-LIST'],'ui.planCalendar.date,pumpId','时间轴资源占用','无计划显示空闲窗口','calendar_filter','change')
pub=opendialog('PLAN-LIST','PUBLISH','发布轮灌计划','DIALOG-PUBLISH','MANAGER或ADMIN；Plan.status=DRAFT',
    '居中显示步骤、目标水量、预计占用与资源检查结果','确认前不创建运行队列','PLAN_PUBLISH成功创建QUEUED运行，尚未发送指令',
    '冲突结果保留计划，显示泵站与重叠时段','非DRAFT或资源检查未通过时禁用并说明','取消回当前计划行',params='planId=event.entityId',kind='row')
overlay('DIALOG-PUBLISH','PLAN-LIST','发布计划并加入待执行队列','planId:string|readonly|event.entityId;conflictHash:string|required|QUERY_PLAN_CONFLICTS',
    '发布计划','PLAN_PUBLISH',[pub],'MANAGER或ADMIN且DRAFT','服务端重新计算冲突与hash；计划时间未过期，步骤非空',
    '关闭并刷新PLAN-LIST、RUN-LIST、RUN-DETAIL与OVERVIEW，显示已排队，禁止声称已启泵','整体回滚，保留计划；冲突变化显示需重新检查')
can=opendialog('PLAN-LIST','CANCEL-PLAN','取消待执行计划','DIALOG-PLAN-CANCEL','MANAGER或ADMIN；DRAFT或PUBLISHED且运行尚未开始',
    '居中显示计划及取消影响','不先从时间轴移除计划','PLAN_CANCEL后标记取消并释放未执行占用','已开始显示需进入RUN-DETAIL停止',
    '执行中禁用并展示对应runId','取消确认回当前计划行',params='planId=event.entityId',kind='row')
overlay('DIALOG-PLAN-CANCEL','PLAN-LIST','取消未执行的轮灌计划','planId:string|readonly|event.entityId;reason:string|required|overlayDraft',
    '确认取消计划','PLAN_CANCEL',[can],'MANAGER或ADMIN；无已发现场指令','取消原因至少6字，再校验运行仍为QUEUED',
    '关闭并更新计划与待执行队列，保留历史编排','计划原状不变，保留原因；已启动时显示RUN-DETAIL入口')
for k,l,p,v,kind in [('NAME','计划名称','name','2至48字','input'),('TIME','计划开始时间','scheduledAt','晚于服务端当前时间且不超过maxScheduleDays','datetime_input'),
 ('STRATEGY','引用策略','strategyId','仅ENABLED策略；选择后复制版本参数到Draft快照，不绑定可变对象','select'),
 ('CANDIDATES','候选分区选择','selectedZoneIds','同农场ENABLED分区；仅修改候选选择，不自动加入步骤','multi_select')]:
    edit('PLAN-EDIT',k,l,'draft.plan.'+p,v,'MANAGER或ADMIN且create模式或DRAFT计划',kind)
comp('PLAN-EDIT','ADD-STEP','添加分区步骤','button','click','UPDATE_STATE','已选择至少一个候选分区且未重复加入；供水关系完整',
    '按候选顺序追加stepDraft，生成与顺序无关的稳定draftId并聚焦目标水量',
    '只改draft.plan.steps，设置resourceCheck=STALE，不写PlanStep','步骤行可编辑且总目标水量由Draft即时派生',
    '重复分区保留原步骤，候选区显示已添加；关联缺失指明zoneId','无候选或提交中禁用','取消离开经脏草稿确认',
    action=local('DRAFT_PLAN_ADD_STEP','把所选zoneIds去重追加为稳定draftId步骤，清除旧conflictHash','DRAFT,UI_STATE'))
for key,label,effect,pre in [('REMOVE-STEP','移除分区步骤','按stepDraftId移除该步骤，剩余order重新排列但主键不变','目标步骤存在'),
 ('MOVE-UP','上移轮灌步骤','交换本步骤与前一步的order，不改变目标水量和draftId','不是第一步'),
 ('MOVE-DOWN','下移轮灌步骤','交换本步骤与后一步的order，不改变目标水量和draftId','不是最后一步')]:
    comp('PLAN-EDIT',key,label,'step_button','click','UPDATE_STATE','MANAGER或ADMIN；'+pre,
        effect+'；使资源检查过期','仅修改draft.plan.steps，不写正式PlanStep',
        '步骤顺序、序号及Draft总量同步派生，提示需重新检查资源','目标步骤不存在时保持原列表并显示草稿已变化',
        '保存中或'+pre+'不满足时禁用','留在编排表，焦点转相邻步骤',
        action=local('DRAFT_PLAN_'+key.replace('-','_'),effect+'；清除conflictHash','DRAFT,UI_STATE'))
edit('PLAN-EDIT','STEP-VOLUME','步骤目标水量与时长','draft.plan.steps[event.stepDraftId]','targetVolumeM3>0且maxDurationMin为正整数，改变后resourceCheck=STALE',
    '所选stepDraftId存在且计划可编辑',kind='step_fields')
readcomp('PLAN-EDIT','CHECK','检查供水与时间冲突','QUERY_PLAN_CONFLICTS','draft.plan','资源检查结果和时间占用预览','无冲突显示检查通过及版本hash')
form_save('PLAN-EDIT','BRANCH-PLAN-SAVE','PLAN_CREATE','PLAN_UPDATE','planId','draft.plan')
form_tools('PLAN-EDIT','draft.plan',Q['PLAN-EDIT'],'PLAN-LIST')

list_controls('RUN-LIST',Q['RUN-LIST'],'运行任务','泵站、运行状态组与执行日期','活动卡、待执行队列及历史分页')
nav('RUN-LIST','OPEN','运行任务编号','RUN-DETAIL','runId=event.entityId','运行在授权田块范围','活动组、过滤条件和页码','card_repeat')
start=opendialog('RUN-LIST','START','启动待执行任务','DIALOG-RUN-START','OPERATOR、MANAGER或ADMIN；run.status=QUEUED且无未决指令',
    '居中列出首个分区、现场联动序列与当前设备模式','不提前显示RUNNING，不发送现场指令','RUN_START入队后显示STARTING，等待真实反馈',
    '能力未签核或关键读数过期时列出阻断对象','LOCAL模式、离线、资源冲突或无操作权禁用并说明','取消回待执行任务行',params='runId=event.entityId',kind='row')
overlay('DIALOG-RUN-START','RUN-LIST','确认启动田间灌溉',
    'runId:string|readonly|event.entityId;reason:string|required|overlayDraft',
    '下发启动请求','RUN_START',[start],'有操作权；QUEUED；能力与联动签核有效','检查模式REMOTE或AUTO；资源未占用；通信新鲜；原因至少6字；目标设备列表只读',
    '关闭弹窗进入RUN-DETAIL(runId)，显示指令PENDING和运行STARTING；反馈确认后才显示RUNNING',
    '入队失败回滚且保留原因；入队后超时由对账转UNKNOWN并告警，不伪造回滚现场动作')
readcomp('RUN-DETAIL','REFRESH','刷新执行反馈',Q['RUN-DETAIL'],'routeParams.runId','流量压力、步骤及指令阶段','尚无反馈显示等待现场反馈')
readcomp('RUN-DETAIL','TAB','执行步骤、指令与用水',Q['RUN-DETAIL'],'ui.run.activeTab','执行反馈Tab','无账本显示尚未结算','tab_group','change')
nav('RUN-DETAIL','AUDIT','查看指令审计','AUDIT','correlationId=event.correlationId','ADMIN或MANAGER且指令存在','当前步骤与时间线锚点','row')
nav('RUN-DETAIL','DEVICE','查看控制设备','DEVICE-DETAIL','deviceId=event.deviceId','设备属于当前运行步骤','运行Tab和反馈游标','row')
pc=comp('RUN-DETAIL','PAUSE-RESUME','暂停或恢复灌溉','button','click','RESOLVE_BRANCH',
    'OPERATOR、MANAGER或ADMIN且有田块操作权；无未决指令；控制模式非LOCAL',
    '读取run.status和version，打开暂停或恢复专用确认','确认前不改IrrigationRun或CommandOutbox',
    'BRANCH-RUN-PAUSE-RESUME按RUNNING或PAUSED打开唯一弹窗','状态过渡中无分支命中，保持当前运行并BLOCK_AND_REPORT',
    '过渡态、离线、无权或未验证反馈时禁用并列出原因','取消确认留在当前步骤和反馈Tab',branch='BRANCH-RUN-PAUSE-RESUME')
local('OPEN_RUN_PAUSE','打开DIALOG-RUN-PAUSE，读取活动步骤和版本')
local('OPEN_RUN_RESUME','打开DIALOG-RUN-RESUME，读取未完成目标量与供水约束')
branches('BRANCH-RUN-PAUSE-RESUME',pc,[br("run.status == 'RUNNING'",'OPEN_RUN_PAUSE','OPEN_DIALOG',dialog='DIALOG-RUN-PAUSE'),
    br("run.status == 'PAUSED'",'OPEN_RUN_RESUME','OPEN_DIALOG',dialog='DIALOG-RUN-RESUME')])
for intent,title,pre,validation,succ,fail in [
 ('PAUSE','暂停当前灌溉','run.status=RUNNING且无未决指令','复验当前版本、通信与可远程模式；保留已完成计量，不重置目标量',
  '入队后运行置PAUSING，反馈确认置PAUSED；保留步骤进度','入队失败保持RUNNING与原因Draft；反馈超时置UNKNOWN并提示核实现场'),
 ('RESUME','恢复暂停灌溉','run.status=PAUSED且无未决指令','重新检查供水资源、新鲜读数、未完成目标量和现场保护','入队后置RESUMING，确认后RUNNING；仅继续剩余目标量',
  '入队失败保持PAUSED；保留原因，容量变化时禁止恢复')]:
    overlay('DIALOG-RUN-'+intent,'RUN-DETAIL',title,'runId:string|readonly|routeParams.runId;reason:string|required|overlayDraft',
        '下发'+title+'请求','RUN_'+intent,[pc],'有田块操作权；'+pre,validation,succ,fail)
stop=opendialog('RUN-DETAIL','STOP','停止本次灌溉','DIALOG-RUN-STOP','OPERATOR、MANAGER或ADMIN且有田块操作权；运行未终止；可远程停止',
    '独立居中确认目标泵阀、当前分区与停止后果','确认前不改运行，不清空当前计量','RUN_STOP入队后STOPPING，确认后STOPPED并开始结算',
    'LOCAL模式显示需现场停机，不能提示已停止','终态或无远程停止接口时禁用并明确原因','取消恢复原运行Tab和步骤')
overlay('DIALOG-RUN-STOP','RUN-DETAIL','停止当前运行并保留实际用水','runId:string|readonly|routeParams.runId;reason:string|required|overlayDraft',
    '下发停止请求','RUN_STOP',[stop],'有田块操作权；运行未终止；现场提供远程停止接口','原因必填；STOP可抢占未决非STOP指令，沿用关联链路；不能撤销已经浇灌的水量',
    '请求受理显示STOPPING，收到完整停机反馈后STOPPED；最终水量由FINALIZE_WATER结算','入队失败保持运行；发送后结果不明保持UNKNOWN及告警，提供刷新反馈和现场核实提示')

list_controls('ALARM-LIST',Q['ALARM-LIST'],'运行告警','处理状态、恢复状态、严重度与异常类型','告警表、未关闭计数及同页详情')
comp('ALARM-LIST','SELECT','告警编号','row','click','UPDATE_STATE','告警在当前授权过滤结果',
    '高亮alarmId并在表下方展示关联对象及处理记录','仅写ui.alarms.selectedAlarmId，详情读同一Alarm',
    '严重度、恢复态、处理态与处理记录来自SELECT-ALARMS','已被关闭或过滤移除时保留筛选并清除无效选择',
    '无权告警不展示','返回恢复告警选择和分页',action=local('UI_ALARM_SELECT','设置selectedAlarmId并订阅同一Alarm','UI_STATE'),family='OBJECT_SELECT')
ack=opendialog('ALARM-LIST','ACK','确认已知悉告警','DIALOG-ALARM-ACK','OPERATOR、MANAGER或ADMIN；Alarm.status=OPEN',
    '居中展示异常时间、设备与确认说明','不改变recovery或停止设备','ALARM_ACK后写确认人时间，状态ACKNOWLEDGED','并发已确认时保留说明并显示处理人',
    '非OPEN时禁用并显示当前处理态','关闭回所选告警',params='alarmId=event.entityId',kind='row')
overlay('DIALOG-ALARM-ACK','ALARM-LIST','确认收到运行告警','alarmId:string|readonly|event.entityId;note:string|required|overlayDraft',
    '确认知悉','ALARM_ACK',[ack],'告警OPEN且有处理权','说明至少6字；再次校验version',
    '关闭，告警置ACKNOWLEDGED；总览未关闭数不减少，恢复态不变','保留说明；若他人已确认提示最新记录，禁止覆盖')
woc=opendialog('ALARM-LIST','DISPATCH','派发维护工单','DIALOG-WORKORDER','MANAGER或ADMIN；告警未关闭且无未完成关联工单',
    '居中展示故障对象、维护类型、人员和到期时间','不立即改变告警责任态','WORKORDER_CREATE原子创建工单并使告警ASSIGNED',
    '人员读取失败保留原告警','已有未完成工单或无派工权禁用','关闭回所选告警和列表页码',params='alarmId=event.entityId',kind='row')
wn=opendialog('WORKORDER-LIST','CREATE','新增巡检工单','DIALOG-WORKORDER','MANAGER或ADMIN',
    '居中打开非告警巡检表单','只创建工单Draft','创建ASSIGNED工单，不生成虚假告警','候选读取失败保留维护泳道',
    '无派工权隐藏','关闭恢复泳道筛选')
overlay('DIALOG-WORKORDER','ALARM-LIST|WORKORDER-LIST','派发巡检维护工单',
    'alarmId:string|optional|event.entityId when owner=ALARM-LIST;zoneId:string|optional|IrrigationZone;deviceId:string|optional|Device;kind:WorkOrderKind|required|overlayDraft;assigneeId:string|required|User;dueAt:datetime|required|overlayDraft;note:string|required|overlayDraft',
    '派发工单','WORKORDER_CREATE',[woc,wn],'MANAGER或ADMIN；关联告警未关闭且无活动工单','责任人为启用TECHNICIAN；到期时间晚于当前时间；deviceId或zoneId至少一个；说明必填',
    '关闭，创建ASSIGNED工单；有alarmId时原子将告警置ASSIGNED，刷新两个工作台','工单与告警整体回滚，保留类型、人员、时限与说明')
cl=opendialog('ALARM-LIST','CLOSE','关闭已恢复告警','DIALOG-ALARM-CLOSE','MANAGER或ADMIN；recovery=RECOVERED且关联工单已验收或不存在',
    '居中展示恢复证据、确认记录与结案说明','不删除告警或自动验收工单','ALARM_CLOSE后未关闭计数重新派生','未恢复或工单待验收时定位阻断原因',
    'ACTIVE或OPEN未确认或未验收时禁用并列出原因','关闭回原告警行',params='alarmId=event.entityId',kind='row')
overlay('DIALOG-ALARM-CLOSE','ALARM-LIST','关闭已恢复的告警','alarmId:string|readonly|event.entityId;resolution:string|required|overlayDraft',
    '确认关闭','ALARM_CLOSE',[cl],'MANAGER或ADMIN且恢复证据满足','recovery=RECOVERED；status=ACKNOWLEDGED或ASSIGNED；工单已验收；说明至少12字',
    '置CLOSED，保存closedAt，刷新ALARM-LIST及OVERVIEW未关闭数','状态保持，保留结案说明并显示未恢复或未验收原因')
nav('ALARM-LIST','RUN','查看关联运行','RUN-DETAIL','runId=selectedAlarm.runId','告警关联runId非空且有查看权','告警筛选、所选行和处理区滚动')
nav('ALARM-LIST','DEVICE','查看故障设备','DEVICE-DETAIL','deviceId=selectedAlarm.deviceId','deviceId非空且有查看权','当前告警与筛选')
list_controls('WORKORDER-LIST',Q['WORKORDER-LIST'],'维护工单','维护类型、负责人、到期范围与工单状态','工单泳道、计数和已完成记录')
wi=opendialog('WORKORDER-LIST','DETAIL','查看工单','DIALOG-WORKORDER-DETAIL','工单存在且有查看权',
    '居中显示责任对象、处理过程和验收记录','只读已有WorkOrder，禁止复制为可变正式对象','详情来自同一workOrderId，关闭无写入','工单不存在提示已移除并刷新泳道',
    '无权限工单不显示','关闭焦点回工单卡片',params='workOrderId=event.entityId',kind='card_repeat')
overlay('DIALOG-WORKORDER-DETAIL','WORKORDER-LIST','巡检维护记录','workOrderId:string|readonly|event.entityId','NONE','NONE',[wi],
    '有该工单范围权限','只读字段，说明文本按纯文本显示','关闭回原泳道和卡片','读取失败保留卡片与所选工单，显示重试读取')
comp('WORKORDER-LIST','ACCEPT','接单并开始巡检','row','click','SUBMIT','TECHNICIAN本人负责且status=ASSIGNED或RETURNED',
    '当前工单卡片显示接单中，锁定本卡操作','调用WORKORDER_ACCEPT，不改变Alarm.recovery',
    '工单转IN_PROGRESS泳道，写startedAt并刷新关联告警记录','保留原泳道；版本冲突只刷新该工单并提示',
    '非本人、非待接单或正在提交时禁用','保留人员筛选，焦点随同一workOrderId卡片移动',action='WORKORDER_ACCEPT',family='WORKORDER_ACCEPT')
for key,title,oid,aid,pre,valid,succ,fail in [
 ('RESULT','提交巡检结果','DIALOG-WORKORDER-RESULT','WORKORDER_SUBMIT','本人TECHNICIAN且IN_PROGRESS','结果说明至少12字，包含排查对象与实际处理','置PENDING_ACCEPTANCE，保留Alarm未关闭','保持IN_PROGRESS并保留结果输入'),
 ('APPROVE','验收维护结果','DIALOG-WORKORDER-APPROVE','WORKORDER_APPROVE','MANAGER或ADMIN且PENDING_ACCEPTANCE','关联故障已恢复或不存在；验收说明必填','置COMPLETED并记录验收人，不自动关闭告警','保持待验收并保留说明，展示持续故障'),
 ('RETURN','退回重新处理','DIALOG-WORKORDER-RETURN','WORKORDER_RETURN','MANAGER或ADMIN且PENDING_ACCEPTANCE','退回理由至少6字，保留原排查结果','置RETURNED，交回原责任人','保持待验收并保留退回理由')]:
    wc=opendialog('WORKORDER-LIST',key,title,oid,pre,'居中显示目标工单及'+title+'输入','确认前不改状态与结果',succ,fail,
        '不满足'+pre+'时禁用并说明','取消回同一工单卡片',params='workOrderId=event.entityId',kind='row')
    fld='resultNote' if key=='RESULT' else 'note'
    overlay(oid,'WORKORDER-LIST',title,f'workOrderId:string|readonly|event.entityId;{fld}:string|required|overlayDraft',
        title,aid,[wc],pre,valid,succ+'；关闭并刷新WORKORDER-LIST、ALARM-LIST及AUDIT',fail+'，正式事务整体回滚')

readcomp('WATER-REPORT','FILTER','田块、种植季与统计区间',Q['WATER-REPORT'],'ui.water.fieldIds,seasonId,startAt,endAt,method','用水指标、对比图及账本明细','缺少基准显示不可计算及原因','filter_group','change')
readcomp('WATER-REPORT','PAGE','账本明细分页',Q['WATER-REPORT'],'ui.water.page,pageSize','账本明细及总数','无账本仍展示计量口径','pagination','change')
comp('WATER-REPORT','CHART','田块用水柱形','chart_point','click','UPDATE_STATE','柱形对应授权Field且属于当前报表集合',
    '高亮fieldId并在同页账本明细增加该田块过滤，page=1','只更新ui.water.drillFieldId，不复制卡片统计',
    'SELECT-WATER从同一WaterLedger集合派生明细与总数','田块已移出范围则清除钻取且保留原区间','空柱及不可见田块禁用','返回图表保留区间和当前田块高亮',
    action=local('UI_WATER_DRILL','设置drillFieldId，dispatch QUERY_WATER_REPORT，不写账本','UI_STATE'),family='OBJECT_SELECT')
nav('WATER-REPORT','RUN','查看计量来源运行','RUN-DETAIL','runId=event.runId','账本runId存在且有权限','统计区间、计量方法与明细页码','row')
bc=opendialog('WATER-REPORT','BASELINE','配置可比节水基准','DIALOG-BASELINE','MANAGER或ADMIN；选择唯一田块和种植季',
    '居中显示该田块当前基准和来源说明输入','确认前不重算正式节水率','BASELINE_SAVE后所有节水指标由SELECT-WATER重新派生',
    '基准读取失败保留原报表','多田块未选唯一对象或无权时禁用','关闭保留报表区间和计量筛选')
overlay('DIALOG-BASELINE','WATER-REPORT','核准可比用水基准',
    'fieldId:string|readonly|ui.water.fieldId;seasonId:string|readonly|ui.water.seasonId;basis:BaselineBasis|required|overlayDraft;referenceAreaMu:decimal|required|overlayDraft;referenceVolumeM3:decimal|required|overlayDraft;referenceStart:date|required|overlayDraft;referenceEnd:date|required|overlayDraft;sourceNote:string|required|overlayDraft',
    '保存基准','BASELINE_SAVE',[bc],'MANAGER或ADMIN且唯一田块种植季有效','参考面积水量>0；起止有效；来源不少于12字；作物和统计窗口须可比',
    '关闭，保存基准与核准人，刷新WATER-REPORT及AUDIT；不可比区间仍显示null原因','保留原基准和全部输入，不把0当作有效节水率')
ex=opendialog('WATER-REPORT','EXPORT','导出当前用水明细','DIALOG-EXPORT','有导出权且当前统计区间有效',
    '居中显示过滤范围、数据方法和导出列','确认前不创建ExportJob','EXPORT_CREATE只创建QUEUED任务并开始查询状态',
    '无效区间定位筛选，不产生空文件','导出提交中或区间超过366天禁用','取消保留当前报表')
overlay('DIALOG-EXPORT','WATER-REPORT','创建用水导出任务','filterSnapshot:json|readonly|ui.water.filters;columns:string[]|required|overlayDraft',
    '创建导出任务','EXPORT_CREATE',[ex],'有导出权且区间有效','列属于角色可导出白名单，范围不超过366天，来源版本固定',
    '关闭并显示QUEUED任务，QUERY_EXPORT_STATUS轮询READY后提供下载','不创建重复任务，保留列选择及报表筛选')
readcomp('WATER-REPORT','EXPORT-REFRESH','刷新导出任务','QUERY_EXPORT_STATUS','ui.water.exportId','导出任务状态','无任务展示尚未导出')
ep=opendialog('WATER-REPORT','PREVIEW','预览导出文件','PREVIEW-EXPORT','ExportJob.status=READY且未过期；本人任务',
    '居中展示文件元数据和前20行只读内容','只读取下载预览，不改账本或任务状态','可校验文件checksum后下载','文件到期显示重新导出入口',
    '非READY、非本人或到期禁用并说明','关闭释放文件URL回导出任务',params='exportId=event.exportId',kind='row')
overlay('PREVIEW-EXPORT','WATER-REPORT','用水导出预览','exportId:string|readonly|event.exportId','NONE','NONE',[ep],
    '本人READY且未到期的导出任务','文件checksum一致，内容为脱敏列，纯文本渲染','关闭释放对象URL并恢复任务焦点','加载失败保留任务，明确过期或文件不可用',typ='PREVIEW')

readcomp('SETTINGS','TAB','账号权限、运行参数',Q['SETTINGS'],'ui.settings.activeTab','当前配置Tab','无账号时显示联系系统管理员','tab_group','change')
list_controls('SETTINGS',Q['SETTINGS'],'账号','角色、启停状态与田块授权','账号表和授权范围')
uc=opendialog('SETTINGS','USER-CREATE','新增账号','DIALOG-USER','ADMIN',
    '居中打开账号与范围授权表单','不创建临时正式User','USER_SAVE成功后账号进入列表','范围读取失败保留账号表','无ADMIN权不显示','取消回账号Tab')
ue=opendialog('SETTINGS','USER-EDIT','调整账号授权','DIALOG-USER','ADMIN且目标User存在',
    '读取当前角色、fieldIds和版本到overlayDraft','不立即影响在线用户权限','保存后服务端撤销受影响令牌并重新鉴权',
    '版本冲突保留角色选择，要求核对','正在提交目标账号时禁用','关闭回原账号行',params='userId=event.entityId',kind='row')
overlay('DIALOG-USER','SETTINGS','账号与田块授权',
    'userId:string|optional|event.entityId;account:string|required|overlayDraft;name:string|required|overlayDraft;phone:string|required|overlayDraft;role:Role|required|overlayDraft;fieldIds:string[]|required|Field',
    '保存授权','USER_SAVE',[uc,ue],'ADMIN','账号唯一，手机号格式正确，范围同农场，不得移除最后启用ADMIN；新账号凭据由服务端安全渠道设置',
    '关闭并刷新SETTINGS及AUDIT；当前用户权限改变立即重新鉴权','正式账号权限整体回滚，保留非敏感输入')
ut=comp('SETTINGS','USER-TOGGLE','启用或停用账号','row','click','RESOLVE_BRANCH','ADMIN且目标不是当前账号',
    '读取User.status与version，选择专用启停确认','确认前不撤销令牌或改变角色','BRANCH-USER-TOGGLE打开启用或停用弹窗',
    '无命中保持当前账号行并BLOCK_AND_REPORT','当前账号禁用该动作；最后管理员不能停用','关闭后保留账号筛选和页码',branch='BRANCH-USER-TOGGLE')
for state,suffix in [('ENABLED','DISABLE'),('DISABLED','ENABLE')]:
    local('OPEN_USER_'+suffix,'打开DIALOG-USER-'+suffix+'，不直接改账号')
branches('BRANCH-USER-TOGGLE',ut,[br("user.status == 'ENABLED'",'OPEN_USER_DISABLE','OPEN_DIALOG',dialog='DIALOG-USER-DISABLE'),br("user.status == 'DISABLED'",'OPEN_USER_ENABLE','OPEN_DIALOG',dialog='DIALOG-USER-ENABLE')])
overlay('DIALOG-USER-DISABLE','SETTINGS','停用账号并撤销访问','userId:string|readonly|event.entityId;reason:string|required|overlayDraft',
    '停用账号','USER_DISABLE',[ut],'ADMIN且目标非本人和最后启用ADMIN','原因至少6字，重新校验账号版本',
    '关闭，账号置DISABLED并撤销令牌；历史运行责任记录保留','保持ENABLED和原授权，保留原因')
overlay('DIALOG-USER-ENABLE','SETTINGS','恢复账号访问','userId:string|readonly|event.entityId',
    '启用账号','USER_ENABLE',[ut],'ADMIN且目标DISABLED','授权田块仍有效，角色在Role枚举内','关闭并置ENABLED，下次登录使用当前权限','保持DISABLED，展示失效授权对象')
for k,l,p,v in [('STALE','默认数据过期秒数','defaultStaleSec','正整数，不回写各点位独立阈值'),('ACK-TIMEOUT','通信应答时限（秒）','commandAckTimeoutSec','正整数且不超过动作确认时限'),
 ('CONFIRM-TIMEOUT','动作确认时限（秒）','actionConfirmTimeoutSec','不小于通信应答时限'),('SCHEDULE-DAYS','最大计划提前天数','maxScheduleDays','1至90整数')]:
    edit('SETTINGS',k,l,'draft.policy.'+p,v,'ADMIN且参数Tab有效',kind='number_input')
ps=opendialog('SETTINGS','POLICY-SAVE','保存运行参数','DIALOG-POLICY','ADMIN且draft.policy校验通过，无受影响活动指令',
    '居中列出参数前后差异','确认前不改SystemPolicy或现场控制器','POLICY_SAVE成功更新参数版本，活动命令继续使用原快照',
    '冲突保留输入和差异列表','未修改、字段错误或有活动占用时禁用','取消确认回参数Tab保留Draft')
overlay('DIALOG-POLICY','SETTINGS','确认更新运行参数','policyId:string|readonly|SELECT-SETTINGS;policyDraft:json|readonly|draft.policy',
    '确认保存参数','POLICY_SAVE',[ps],'ADMIN且参数合法、无活动占用','服务端重新校验超时大小关系和version；序列改变必须重新现场签核',
    '关闭并清除policyDraft脏标记，刷新SETTINGS、DEVICE-DETAIL、RUN-DETAIL、PLAN-EDIT及AUDIT','全部回滚参数，保留Draft，定位版本或占用冲突')
form_tools('SETTINGS','draft.policy',Q['SETTINGS'],'OVERVIEW')
list_controls('AUDIT',Q['AUDIT'],'审计事件','人员、对象类型、结果、时间与关联指令','只读审计表及链路时间线')
au=opendialog('AUDIT','DETAIL','查看审计详情','DIALOG-AUDIT','ADMIN或MANAGER且事件在农场范围',
    '居中显示actor、动作、版本和correlationId链路','只读AuditLog和CommandEvent，不允许编辑或删除','关闭后审计表保持同一过滤集合',
    '事件读取失败保留原列表并显示错误','无权事件不展示','关闭回审计行',params='auditId=event.entityId',kind='row')
overlay('DIALOG-AUDIT','AUDIT','操作与指令证据','auditId:string|readonly|event.entityId','NONE','NONE',[au],
    'ADMIN或MANAGER且审计事件授权有效','detail以纯文本呈现，凭据和敏感载荷脱敏','关闭回审计行，不产生新业务事件','保持查询条件与原事件列表，展示读取失败')

# Compact navigation uses the same business navigation controls in a centered modal.
mc=opendialog('WEB-SHELL','MENU','展开导航','DIALOG-NAVIGATION','Session有效且窄屏折叠导航可见',
    '居中展示已授权的分组导航，背景页面inert','仅创建导航弹层UI，不改业务实体','选择已登记WEB-SHELL.NAV组件后关闭导航层并执行其分支',
    '弹层不可用保留当前页，提示导航加载失败','业务提交中禁用','关闭返回展开导航按钮')
overlay('DIALOG-NAVIGATION','GLOBAL','业务导航','NONE','NONE','NONE',[mc],
    'Session有效且折叠导航可见','复用同一WEB-SHELL.NAV组件ID及权限；侧栏与弹层不能同时可交互',
    '选择确定菜单后关闭本层再执行对应导航分支；关闭按钮不导航','导航失败保持原页面与来源快照')

FIELD_RULES={
 'crop':('选择本农场实际种植作物，空白不合法','修改后清除不兼容品种与阶段候选，历史种植季不变'),
 'variety':('品种2至40字，与当前crop一致','只更新当季品种Draft，不追改历史季'),
 'plantingDate':('合法本地日期，不能晚于harvestDate','重新校验种植季时间重叠并将错误定位日期'),
 'harvestDate':('可空，填写时不早于plantingDate','空值存null，归档前重新核验阶段与时间'),
 'stage':('取CropStage枚举；HARVESTED必须同时确认收获日期','联动显示收获日期，不更改已发布策略快照'),
 'name':('2至48字，不接受全空白','只更新当前对象名称Draft，正式关联ID保持不变'),
 'fieldId':('候选来自当前授权且ENABLED的Field主键','重算可分区面积，清除不属于新田块的计量或土层候选'),
 'sourceNodeId':('同农场供水节点，节点和父链无环','重新读取同供水路径阀门候选，资源检查hash置过期'),
 'valveDeviceId':('同农场VALVE且未被不兼容分区占用','改变阀门关联仅写Draft，重算可远程控制门槛'),
 'meterPointId':('可空；填写必须为同供水路径的METER_TOTAL点','MEASURED需独立归属；共享总表改为ALLOCATED并要求规则'),
 'soilPointIds':('候选Point.kind=SOIL_MOISTURE且覆盖目标田块','仅保存点位ID数组，逐点展示depthCm和过期状态'),
 'areaMu':('正数且精度不超过两位小数，不超田块剩余面积','重新派生剩余覆盖面积，不改变正式田块areaMu'),
 'designFlowM3h':('正数且不超所属供水节点容量','Draft资源预览和预计时长失效，保存时复验'),
 'accountingMethod':('取MEASURED、ALLOCATED或ESTIMATED','切换后重新校验独立表或allocationRule，不把估算改名为实测'),
 'allocationRule':('ALLOCATED必填，需说明来源总表、权重与扣除独立分表步骤','在Draft展示分摊预览，所有分区权重归一化'),
 'parentNodeId':('可空；选择时不得指向当前节点或其后代','重算无环路径，清除旧资源检查hash'),
 'capacityM3h':('>0，现场核定容量，不从设备名称猜测','更新Draft供水上限预览，不改已执行命令快照'),
 'maxConcurrentZones':('>=1整数，不能小于当前已占用数','重新校验未来计划并发，不中止活动任务'),
 'depthCm':('>=0，土层探头为安装深度，滴灌管段为实测埋深','不同对象保留各自量纲用途，不将探头深度当作埋带深度'),
 'intervalCm':('管带间距为正数，水源节点可为0','仅修改对应PipeNode.intervalCm草稿'),
 'code':('设备编号同农场唯一，稳定编码不以记录行号生成','校验重复候选时排除当前deviceId，正式码保存前不变'),
 'kind':('枚举必须属于当前表单对应的DeviceKind、PointKind或WorkOrderKind','按明确字段类型切换合法单位、维护项或设备候选，不依据显示文案分派'),
 'manufacturer':('填写已知厂家，生产记录不得使用验收适配器占位','只存厂家名称Draft，不据厂家名自动判断控制能力'),
 'model':('填写铭牌型号，长度1至80字符','修改型号使后续接入验证待复核，不自动启用控制'),
 'gatewayDeviceId':('同农场GATEWAY主键，网关自身不得循环引用','更换网关后保留原端点Draft供核对，能力需重新验证'),
 'protocol':('选择已实现适配器标识；生产禁用SIMULATED_GATEWAY_V1','重新展示该适配器endpoint格式，不生成未知寄存器地址'),
 'endpoint':('符合所选适配器地址格式，服务端校验目标白名单','只保存地址Draft，不在浏览器直接探测任意网络地址'),
 'secret':('可空；需要时仅以内存掩码输入，经TLS交服务端密钥服务','关闭或提交完成清空输入，失败不回显已有密钥'),
 'address':('同deviceId下唯一，格式由protocol确定','改变地址后能力签核失效，历史原始点位数据保留'),
 'unit':('与PointKind的量纲严格匹配，含水率%VWC、压力MPa','只改映射Draft；界面换算不改历史原始值'),
 'zoneId':('授权ENABLED分区主键；设备映射必须同农场','重算田块和供水路径约束，只保留兼容关联'),
 'deviceId':('候选为当前农场授权Device；至少提供设备或分区之一','维护对象选择只保存deviceId，不赋予该设备控制权限'),
 'rangeMin':('有限数值且小于rangeMax','重新校验参考值及可采集范围，禁止NaN'),
 'rangeMax':('有限数值且大于rangeMin','重算超量程标记预览，不追改原始质量字段'),
 'scale':('非0有限数值，缩放语义由适配器点表定义','预览raw*scale+offset，不修改已入库原始读数'),
 'offset':('有限数值，在量程预览中无溢出','只改点位Draft换算预览，正式校准须专用Action留证据'),
 'staleAfterSec':('正整数，为该Point独立过期阈值','预览当前读数是否过期，不修改observedAt'),
 'referenceValue':('有限数且在目标点位量程内','局部显示候选newOffset=referenceValue-measuredValue，不立即应用'),
 'measuredValue':('填写本次实测原始数，不能用过期UI值自动冒充','与referenceValue共同派生校准预览，保留oldOffset'),
 'note':('按当前确认Action的现场记录要求填写，不接受纯空白','只更新当前弹层说明Draft；成功进入相应维护、校准或确认记录'),
 'reason':('至少6字，说明当前启动、暂停、恢复、停止、取消或停用原因','保留当前动作独立原因；控制原因随CommandOutbox入队，取消原因进入审计'),
 'asOf':('带时区时间，不得晚于服务端当前时刻','更改后旧simulation标为过期，必须重新试算'),
 'assigneeId':('同农场ENABLED且role=TECHNICIAN','选择后只更新派工Draft，原告警责任态保持'),
 'dueAt':('有效带时区时间且晚于当前时刻','同页显示距离到期时长，不按固定序列生成'),
 'resolution':('至少12字，包含恢复依据和结案说明','不自动验收关联工单，保留未恢复阻断原因'),
 'resultNote':('至少12字，包含排查对象、现场处理及当前状态','只保留现场结果Draft，提交后进入PENDING_ACCEPTANCE'),
 'basis':('SAME_FIELD_PRIOR_SEASON或APPROVED_REFERENCE','切换后重新校验参考窗口与来源，旧正式节水率保持至保存'),
 'referenceAreaMu':('正数，不使用0作未知面积','重算Draft亩均基准，保留原WaterBaseline'),
 'referenceVolumeM3':('正数，来源量纲为m³','局部预览基准强度，不把预览加入WaterLedger'),
 'referenceStart':('合法日期且<=referenceEnd','重新验证作物阶段及窗口是否与本期可比'),
 'referenceEnd':('合法日期且>=referenceStart','更改窗口后可比状态需重新计算，不沿用旧比较结果'),
 'sourceNote':('至少12字，含测量或核准来源','只存基准来源Draft，不伪造核准人和时间'),
 'columns':('非空数组且全部属于当前角色可导出列白名单','只改变导出列Draft，任务创建时固定完整filterSnapshot'),
 'account':('3至48字符，同农场唯一且排除当前userId','只改账号Draft；已有令牌在保存前保持原权限'),
 'phone':('符合当前账号联系电话格式，不能用固定占位号码','只改联系信息Draft，提交失败保留以便修正'),
 'role':('取Role枚举，只有ADMIN可设置且不能移除最后管理员','更新候选权限预览，服务端保存后才撤销旧令牌'),
 'fieldIds':('非空且所有ID属于当前Farm','逐项展示田块名称和面积，不能将整个对象复制进User'),
 'payload':('完整UTF-8二维码载荷或已登记编码，不执行其中脚本','清除旧scanResolution，等待QUERY_QR_RESOLVE；输入本身不触发路由'),
 'cameraId':('仅来自用户授权后枚举的videoinput','切换必须停止旧轨道，识别中不允许并行打开多个摄像头')
}
FIELD_LABELS={'crop':'作物','variety':'品种','plantingDate':'种植日期','harvestDate':'收获日期','stage':'生育阶段',
 'name':'名称','fieldId':'所属田块','sourceNodeId':'供水节点','valveDeviceId':'控制阀门','meterPointId':'计量点','soilPointIds':'墒情点位',
 'areaMu':'分区面积（亩）','designFlowM3h':'设计流量（m³/h）','accountingMethod':'计量方式','allocationRule':'分摊依据',
 'parentNodeId':'上级管段','capacityM3h':'供水容量（m³/h）','maxConcurrentZones':'最大同时灌溉分区数','depthCm':'安装深度（cm）','intervalCm':'管带间距（cm）',
 'code':'设备编号','kind':'类型','manufacturer':'生产厂家','model':'设备型号','gatewayDeviceId':'接入网关','protocol':'通信适配器','endpoint':'接入地址','secret':'接入凭据',
 'address':'点位地址','unit':'数据单位','zoneId':'关联分区','deviceId':'维护设备','rangeMin':'量程下限','rangeMax':'量程上限','scale':'换算倍率','offset':'换算偏移','staleAfterSec':'数据有效时长（秒）',
 'referenceValue':'参考仪读数','measuredValue':'现场实测读数','note':'记录说明','reason':'操作原因','asOf':'试算时刻','assigneeId':'维护责任人','dueAt':'完成时限',
 'resolution':'结案依据','resultNote':'现场排查结果','basis':'比较基准类型','referenceAreaMu':'基准面积（亩）','referenceVolumeM3':'基准水量（m³）',
 'referenceStart':'基准起始日期','referenceEnd':'基准结束日期','sourceNote':'基准来源说明','columns':'导出列','account':'账号','phone':'联系电话','role':'角色',
 'fieldIds':'可访问田块','payload':'扫码或手输编码','cameraId':'摄像头设备'}

# Registry-backed overlay controls, including every field, confirm, cancel and scanner tool.
for ov in OVERLAYS:
    owners=ov['owner_screen_id'].split('|') if ov['owner_screen_id']!='GLOBAL' else ['WEB-SHELL']
    if len(owners)>1:owners=['WEB-SHELL']  # one reusable overlay instance, not duplicate controls per owner
    for owner in owners:
        for spec in ov['fields'].split(';'):
            if spec=='NONE': continue
            parts=spec.split('|'); fname,ftype=parts[0].split(':',1)
            if len(parts)>1 and parts[1]=='readonly': continue
            source=parts[-1]
            if source.startswith(('event.','QUERY_','overlayContext.')) or source in ('ui.network.selectedZoneId','ui.network.selectedNodeId'):
                ov['context_readonly_fields']='|'.join(dict.fromkeys((ov.get('context_readonly_fields','')+'|'+fname).strip('|').split('|')))
                continue
            label=FIELD_LABELS[fname]
            field_validation,field_effect=FIELD_RULES[fname]
            if ftype in ENUMS:field_validation+='；可选值='+ENUMS[ftype]
            control_kind='select' if ftype in ENUMS or source in ENTITIES else 'multi_select' if ftype.endswith('[]') else 'number_input' if ftype in ('decimal','integer') else 'date_picker' if ftype in ('date','datetime') else 'input'
            cid=edit(owner,'OVERLAY-'+ov['overlay_id']+'-FIELD-'+fname,label,
                "overlayDraft['"+ov['overlay_id']+"']."+fname,
                field_validation+'；'+ov['field_validation_policy'],
                '活动弹层='+ov['overlay_id']+'；'+ov['open_preconditions'],
                kind=control_kind,overlay_owner_id=ov['overlay_id'],scope='OVERLAY')
            fc=next(c for sid,c in COMP if c['component_id']==cid)
            fc['event']='change' if control_kind in ('select','multi_select','date_picker') else 'input'
            fc['data_consequence']+='；'+field_effect
            fc['immediate_feedback']+='；'+field_effect
            fc['success_consequence']='本字段与依赖预览同步：'+field_effect
        if ov['confirm_action_id']!='NONE':
            aid=ov['confirm_action_id']; a=next((a for a in ACTIONS if a['action_id']==aid),None)
            pre=a['preconditions'] if a else ov['open_preconditions']
            data=a['success_result'] if a else LOCALS.get(aid,QUERIES.get(aid,{})).get('effect',ov['success_result'])
            comp(owner,'OVERLAY-'+ov['overlay_id']+'-CONFIRM',ov['confirm_text'],'button','click','SUBMIT',
                pre+'；'+ov['field_validation_policy'],
                ov['title']+'确认按钮Loading，锁定字段和实际来源触发器',
                aid+'：'+data,ov['success_result'],ov['failure_result'],
                '校验失败或本弹层已在提交时禁用；焦点定位首个错误',
                '失败保持该弹层和输入；成功按照success_result关闭或展示结果',
                action=aid,family='CONFIRM_DIALOG',template='CONFIRM_DIALOG',overlay_owner_id=ov['overlay_id'],scope='OVERLAY')
        cancel=local('CLOSE_'+ov['overlay_id'].replace('-','_'),
            f'关闭{ov["overlay_id"]}，只销毁其overlayDraft，保留来源页Draft；停止本弹层媒体流与URL，焦点回实际触发器','UI_STATE,DRAFT,DEVICE_API')
        comp(owner,'OVERLAY-'+ov['overlay_id']+'-CANCEL',ov['cancel_text'],'button','click','UPDATE_STATE',
            '活动弹层='+ov['overlay_id']+'且无提交锁','关闭居中弹层，清理该实例局部资源',
            '只丢弃该overlayDraft；不调用确认Action，不改变正式业务实体',
            '来源页的筛选、选中对象和未提交输入保持，焦点返回实际触发器',
            '资源清理失败仍关闭界面并上报错误，禁止额外写业务实体',
            '提交中禁用；遮罩、Escape、关闭图标和浏览器返回共享此行为',
            '返回'+ov['owner_screen_id']+'实际来源上下文，不新增历史记录',
            action=cancel,family='OVERLAY_CANCEL',overlay_owner_id=ov['overlay_id'],scope='OVERLAY',
            equivalent_events='cancel_button|close_icon|mask_click|Escape|browser_back_when_idle')
            
scanner_confirm=next(c['component_id'] for sid,c in COMP if c.get('overlay_owner_id')=='SCANNER-ASSET' and c['component_id'].endswith('-CONFIRM'))
for target,kind,param in [('DEVICE-DETAIL','device','deviceId'),('FIELD-DETAIL','field','fieldId')]:
    aid=local('SCAN_NAV_'+kind.upper(),f'关闭SCANNER-ASSET并停止媒体流，进入{target}，主键来自QUERY_QR_RESOLVE授权结果')
branches('BRANCH-SCAN-RESULT',scanner_confirm,[
    br("ui.scanResolution.kind == 'device' and ui.scanResolution.authorized == true",'SCAN_NAV_DEVICE','NAVIGATE',target='DEVICE-DETAIL',params='deviceId=ui.scanResolution.entityId'),
    br("ui.scanResolution.kind == 'field' and ui.scanResolution.authorized == true",'SCAN_NAV_FIELD','NAVIGATE',target='FIELD-DETAIL',params='fieldId=ui.scanResolution.entityId')])
scan_component=next(c for sid,c in COMP if c['component_id']==scanner_confirm)
scan_component.update(action_type='RESOLVE_BRANCH',branch_set_id='BRANCH-SCAN-RESULT',dialog_id='BY_BRANCH',target_screen_id='BY_BRANCH',route_params='BY_BRANCH',
    immediate_feedback='锁定识别输入，先执行QUERY_QR_RESOLVE；Query成功后以ui.scanResolution评估BRANCH-SCAN-RESULT；读取失败保留弹窗且不评估分支',
    data_consequence='只读取QrCode、Device、Field并更新扫码解析UI，不修改正式实体')
next(o for o in OVERLAYS if o['overlay_id']=='SCANNER-ASSET')['confirm_action_id']='DISPATCH_BRANCH_SCAN_RESULT'
for key,label,effect,pre in [('CAMERA','启用摄像头','显式请求camera权限并启动选定摄像头；识别帧统一进入scanDraft.payload','浏览器支持getUserMedia且用户已点击'),
 ('CAMERA-SELECT','切换摄像头','停止旧轨道后切换ui.cameraId并保持扫码结果Draft','已取得权限且存在多个视频输入'),
 ('RETRY','重新扫描','清除ui.scanResolution及旧识别错误，恢复帧识别与输入焦点','没有识别请求在执行')]:
    comp('DEVICE-DETAIL','OVERLAY-SCANNER-'+key,label,'button' if key!='CAMERA-SELECT' else 'select','click' if key!='CAMERA-SELECT' else 'change','UPDATE_STATE',
        'SCANNER-ASSET已打开；'+pre,effect,'只修改扫码UI、Draft和设备媒体资源，不改Device或Field',
        '新扫码输入可用，成功读取payload后仍须QUERY_QR_RESOLVE校验','权限失败停止全部媒体轨道，保留手输入口和已输入编码',
        '识别提交中禁用；无硬件能力时显示原因','关闭弹层停止所有媒体轨道、worker和requestAnimationFrame',
        action=local('SCANNER_'+key.replace('-','_'),effect,'UI_STATE,DRAFT,DEVICE_API'),family='SCANNER_TOOL',overlay_owner_id='SCANNER-ASSET',scope='OVERLAY')
scnav=nav('STRATEGY-LIST','OVERLAY-SIMULATION-CREATE','按建议编排计划','PLAN-EDIT','mode=create;strategyId=ui.simulation.strategyId;suggestedZoneIds=ui.simulation.eligibleZoneIds',
    'MANAGER或ADMIN且至少一个分区试算可执行','试算结果和策略矩阵筛选')
next(c for sid,c in COMP if c['component_id']==scnav).update(overlay_owner_id='DIALOG-SIMULATION',scope='OVERLAY',
    success_consequence='关闭DIALOG-SIMULATION；在PLAN-EDIT初始化建议Draft和策略版本快照，不自动保存或发布Plan')
download=local('EXPORT_DOWNLOAD','校验本人READY任务和未到期URL，fetch文件并核验checksum后创建下载对象URL；完成立即释放；不修改账本','DEVICE_API,UI_STATE')
comp('WATER-REPORT','OVERLAY-EXPORT-DOWNLOAD','下载已生成文件','button','click','SUBMIT','PREVIEW-EXPORT打开；本人任务READY且expiresAt>now',
    '下载按钮Loading并读取文件','只读取文件，不修改WaterLedger、ExportJob或报表筛选','校验checksum后触发带原fileName的下载并释放URL',
    '校验或读取失败不生成空下载，保留预览与任务号；到期提示重新导出','过期、非READY或读取中禁用','下载完成仍在预览，关闭回导出任务',
    action=download,overlay_owner_id='PREVIEW-EXPORT',scope='OVERLAY')
comp('FIELD-DETAIL','OVERLAY-QR-RENDER-RETRY','重新生成二维码图像','button','click','UPDATE_STATE',
    'PREVIEW-FIELD-QR打开且该实体ACTIVE载荷存在，当前图像生成失败','只重新渲染已登记payload，按钮Loading',
    '释放旧图像URL后用标准QR编码器生成新图像；不重置QrCode或变更payload','独立解码还原相同payload后展示新图像，保持预览打开',
    '保留编码文本与原田块详情，图像区域显示失败及再次重试','正在生成或载荷不存在时禁用','关闭释放本次URL并回原二维码入口',
    action=local('QR_RENDER_RETRY','重新编码已有payload并创建图像URL，禁止更新QrCode','UI_STATE,DEVICE_API'),
    overlay_owner_id='PREVIEW-FIELD-QR',scope='OVERLAY')
readcomp('WORKORDER-LIST','OVERLAY-WORKORDER-RETRY','重新读取工单',Q['WORKORDER-LIST'],'ui.workorders.selectedWorkOrderId',
    'DIALOG-WORKORDER-DETAIL工单事实和验收记录','对象不再存在显示ENTITY_NOT_FOUND')
next(c for sid,c in COMP if c['component_id']=='WORKORDER-LIST.OVERLAY-WORKORDER-RETRY').update(overlay_owner_id='DIALOG-WORKORDER-DETAIL',scope='OVERLAY')
comp('DEVICE-DETAIL','OVERLAY-SCANNER-CAPTURE','扫码识别结果','scanner','scan_success','UPDATE_STATE','SCANNER-ASSET处于等待输入且无识别提交锁',
    '将解码文本填入scanDraft.payload，暂停帧识别并聚焦识别按钮','只更新扫码Draft，不把设备码当作会话或直接导航',
    '用户可检查原始载荷并点击识别，后续须QUERY_QR_RESOLVE校验','无法解码继续扫描并显示请对准完整二维码，不制造编号',
    '解析提交中屏蔽重复扫码事件','关闭清空扫码Draft并停止全部媒体轨道',
    action=local('SCANNER_CAPTURE_DRAFT','仅把实际解码文本写入scanDraft.payload并暂停帧循环','DRAFT,UI_STATE,DEVICE_API'),
    overlay_owner_id='SCANNER-ASSET',scope='OVERLAY')

# Explicit page-entry actions and retry states are included in interaction accounting.
for sid in S:
    readcomp(sid,'RETRY-LOAD','重试加载',Q[sid],S[sid]['required_params'],'本页主要业务区域','成功读取但为空时展示本页空状态')
    next(c for ss,c in COMP if c['component_id']==sid+'.RETRY-LOAD')['visibility_rule']='pageState == ERROR'
    aid=local('UI_INIT_'+sid.replace('-','_'),f'进入{sid}时校验角色和必要参数，dispatch {Q[sid]}；进入完成后不再覆盖用户已修改Draft','UI_STATE,DRAFT')

for cid,enum,mapping in [
 ('FIELD-DETAIL.TAB','FieldDetailTab',{'PROFILE':'档案','MOISTURE':'墒情','WATER_HISTORY':'灌溉记录'}),
 ('DEVICE-DETAIL.TAB','DeviceDetailTab',{'POINTS':'点位','CALIBRATIONS':'校准','DIAGNOSTICS':'诊断'}),
 ('RUN-DETAIL.TAB','RunDetailTab',{'STEPS':'执行步骤','COMMANDS':'指令','WATER':'用水'}),
 ('SETTINGS.TAB','SettingsTab',{'USERS':'账号权限','POLICY':'运行参数'})]:
    c=next(c for ss,c in COMP if c['component_id']==cid)
    c.update(option_enum=enum,value_label_mapping=json.dumps(mapping,ensure_ascii=False),default_value=next(iter(mapping)))
for cid,effect,fields in [
 ('STRATEGY-EDIT.CROP','同时写draft.strategy.crop和draft.strategy.stage，清空不匹配zoneIds并重新筛选候选','crop,stage'),
 ('STRATEGY-EDIT.WINDOW','写draft.strategy.allowedStart和allowedEnd，预览限定时段但不生成任务','allowedStart,allowedEnd'),
 ('PLAN-EDIT.CANDIDATES','仅写ui.planEditor.selectedZoneIds，点击添加步骤后才创建stepDraft','selectedZoneIds')]:
    c=next(c for ss,c in COMP if c['component_id']==cid);c['bound_fields']=fields;c['data_consequence']=effect+'；正式实体不变'
    LOCALS[c['action_id']]['effect']=effect

# Create and update are distinct business paths, even when they share one centered editor.
for oid,base,prefix,idfield,identity,create_pre,update_pre,create_effect,update_effect in [
 ('DIALOG-DEVICE','DEVICE_SAVE','DEVICE','deviceId','触发器event.entityId，登记入口固定null',
  'deviceId为空；编码同农场唯一；ADMIN','deviceId存在且expectedVersion匹配；无未决指令',
  '创建稳定deviceId，初始verification=UNVERIFIED、reportedState=UNKNOWN，追加审计，不伪造在线状态',
  '仅更新现有接入元数据，配置变化使verification=UNVERIFIED，保留历史读数与设备主键'),
 ('DIALOG-ZONE','ZONE_SAVE','ZONE','zoneId','触发器route_params.zoneId；新增固定null',
  'zoneId为空；面积覆盖和阀门占用检查通过','zoneId存在且无运行占用；版本一致',
  '创建稳定zoneId并关联田块、供水、阀门、点位及分摊依据，新增覆盖面积由Selector派生',
  '更新现有分区关联和设计参数，不追改历史WaterLedger的归属与计量方法'),
 ('DIALOG-POINT','POINT_SAVE','POINT','pointId','触发器route_params.pointId或event.pointId；登记固定null',
  'pointId为空；设备地址未重复','pointId存在；版本一致且无活动控制引用',
  '创建稳定pointId及量纲映射，设备能力验证失效，新点无历史读数时显示未采集',
  '更新点位映射和有效期，保留原始读数与校准证据，设备能力验证失效'),
 ('DIALOG-USER','USER_SAVE','USER','userId','触发器event.entityId；新增固定null',
  'userId为空；账号唯一且角色范围有效','userId存在且版本一致；不得移除最后管理员',
  '创建稳定userId和授权范围，凭据由服务端安全流程初始化，不在XML或浏览器生成默认密码',
  '更新现有账号角色与fieldIds，保留历史责任引用，服务端撤销旧令牌并重新鉴权'),
 ('DIALOG-BASELINE','BASELINE_SAVE','BASELINE','baselineId','SELECT-WATER中所选fieldId和seasonId的唯一ENABLED基准主键；无则null',
  'baselineId为空；参考面积水量正值且窗口可比','baselineId存在且版本一致；来源与窗口重新核验',
  '创建该田块种植季唯一活动基准，写approvedBy与来源，不修改WaterLedger',
  '更新现有基准参考面积、水量和窗口，保留审计前值并使节水Selector失效'),
 ('DIALOG-SEASON','SEASON_SAVE','SEASON','seasonId','SELECT-FIELDS中该fieldId的唯一活动种植季；无则null',
  'seasonId为空且无时间重叠的活动种植季','seasonId存在且属于当前fieldId；版本一致',
  '创建稳定seasonId和活动种植记录，田块版本递增，历史归档季不变',
  '更新当前种植季；stage=HARVESTED时harvestDate必填并置status=DISABLED；保留历史用水和Field关联')]:
    original=next(a for a in ACTIONS if a['action_id']==base);ACTIONS.remove(original)
    newids=[]
    for suffix,pre,effect in [('CREATE',create_pre,create_effect),('UPDATE',update_pre,update_effect)]:
        aid=prefix+'_'+suffix;newids.append(aid)
        action(aid,original['input']+','+idfield+'?,expectedVersion?',original['writes'],original['affected_screens'],
            original['preconditions']+'；'+pre,effect,original['failure_result']+'；'+('不产生新主键记录' if suffix=='CREATE' else '既有对象版本保持不变'))
    ov=next(o for o in OVERLAYS if o['overlay_id']==oid)
    ov['identity_resolver']=identity+'；打开时冻结ui.activeOverlay.context.'+idfield+'，禁止字段编辑改主键'
    bid='BRANCH-'+prefix+'-COMMIT';dispatcher='DISPATCH_'+bid.replace('-','_')
    ov['confirm_action_id']=dispatcher
    cc=next(c for sid,c in COMP if c.get('overlay_owner_id')==oid and c['component_id'].endswith('-CONFIRM'))
    cc.update(action_type='RESOLVE_BRANCH',action_id=dispatcher,branch_set_id=bid,dialog_id='BY_BRANCH',target_screen_id='BY_BRANCH',route_params='BY_BRANCH',
        immediate_feedback='校验当前弹层字段并锁定确认和来源控件，按已冻结的'+idfield+'解析'+bid,
        data_consequence=newids[0]+'：'+create_effect+'；'+newids[1]+'：'+update_effect,
        preconditions=ov['open_preconditions']+'；'+ov['field_validation_policy'])
    branches(bid,cc['component_id'],[
        br('ui.activeOverlay.context.'+idfield+' == null',newids[0],tx='TX-'+newids[0].replace('_','-')),
        br('ui.activeOverlay.context.'+idfield+' != null',newids[1],tx='TX-'+newids[1].replace('_','-'))])
    DISPATCH_ALIASES[base]=bid

# Consistent, referentially complete fixtures. IDs are semantic codes with hash-like stable suffixes.
SEEDS={name:[] for name in ENTITIES}
def seed(entity_name,**data):
    e=ENTITIES[entity_name]
    if entity_name!='Session' and not e['immutable']:
        data.setdefault('version',1);data.setdefault('createdAt','2026-09-18T14:23:17+08:00');data.setdefault('updatedAt','2026-10-23T16:47:29+08:00')
    SEEDS[entity_name].append(data)
    return data[e['id_field']]

farm='FRM-JZ-RH8Q'
seed('Farm',farmId=farm,name='冀州润禾示范农场',region='河北省衡水市冀州区',timezone='Asia/Shanghai',status='ENABLED')
users=[('USR-JZ-Y8QF','zyq.admin','周砚秋','13831807246','ADMIN'),('USR-JZ-K4MT','mqc.manager','孟启川','13932846185','MANAGER'),
       ('USR-JZ-P6VN','hcl.operator','韩成林','13722859364','OPERATOR'),('USR-JZ-F9RD','xql.maint','邢秋蕾','13633286497','TECHNICIAN'),
       ('USR-JZ-C3HW','dyh.viewer','杜云禾','13582679438','VIEWER')]
fids=['FLD-JZ-D7K4','FLD-JZ-M9R2','FLD-JZ-Q4V8']
for uid,acc,name,phone,role in users:seed('User',userId=uid,account=acc,name=name,phone=phone,role=role,status='ENABLED',farmId=farm,fieldIds=fids)
for fid,name,area,soil,loc,season,plant in [
 (fids[0],'东渠北畦',38.6,'壤土',[115.57864,37.54827],'SEA-JZ-N8HW','2026-10-09'),
 (fids[1],'西泵南畦',52.4,'砂壤土',[115.56391,37.54218],'SEA-JZ-C6QK','2026-10-12'),
 (fids[2],'河沿示范田',26.8,'黏壤土',[115.58643,37.53962],'SEA-JZ-T4FM','2026-10-07')]:
    seed('Field',fieldId=fid,farmId=farm,code=fid,name=name,areaMu=area,soilType=soil,location=loc,managerId=users[1][0],status='ENABLED')
    seed('CropSeason',seasonId=season,fieldId=fid,crop='冬小麦',variety='衡4399',plantingDate=plant,harvestDate=None,stage='EMERGENCE',status='ENABLED')
devs=[('DEV-JZ-G8QP','田间通信网关','GATEWAY'),('DEV-JZ-P4KR','东渠首部水泵','PUMP'),('DEV-JZ-P9VT','西泵首部水泵','PUMP'),
 ('DEV-JZ-V6HA','东渠北段阀','VALVE'),('DEV-JZ-V3QM','东渠南段阀','VALVE'),('DEV-JZ-V8FN','西泵南畦阀','VALVE'),('DEV-JZ-V5RD','河沿分区阀','VALVE'),
 ('DEV-JZ-S7KW','东渠墒情探头','SOIL_PROBE'),('DEV-JZ-S4PV','西泵墒情探头','SOIL_PROBE'),('DEV-JZ-S9MT','河沿墒情探头','SOIL_PROBE'),
 ('DEV-JZ-F8CH','东渠累计流量计','FLOW_METER'),('DEV-JZ-F3NK','西泵累计流量计','FLOW_METER'),('DEV-JZ-F6QV','河沿累计流量计','FLOW_METER'),
 ('DEV-JZ-R4HD','东渠压力变送器','PRESSURE_SENSOR'),('DEV-JZ-R7KP','西泵压力变送器','PRESSURE_SENSOR')]
for did,name,kind in devs:
    ctrl=kind in ('PUMP','VALVE');offline=did=='DEV-JZ-S9MT'
    model={'GATEWAY':'JH-GW4G-L2','PUMP':'JH-PC-7K5','VALVE':'JH-DN50-LR','SOIL_PROBE':'JH-TS2-D40','FLOW_METER':'JH-FM-DN80','PRESSURE_SENSOR':'JH-PT-1M'}[kind]
    seed('Device',deviceId=did,farmId=farm,code=did,name=name,kind=kind,manufacturer='冀禾田间测控',model=model,
         gatewayDeviceId=None if kind=='GATEWAY' else devs[0][0],protocol='SIMULATED_GATEWAY_V1',endpoint='gateway://'+did,
         connection='OFFLINE' if offline else 'ONLINE',lastSeenAt='2026-10-25T08:47:26+08:00' if offline else '2026-10-25T10:18:37+08:00',
         verification='UNVERIFIED' if offline else 'VERIFIED',controlMode='REMOTE',reportedState=('RUNNING' if did=='DEV-JZ-P4KR' else 'OPEN' if did=='DEV-JZ-V6HA' else 'STOPPED' if kind=='PUMP' else 'CLOSED' if kind=='VALVE' else 'UNKNOWN'),
         capabilities=dict(read=True,control=ctrl,feedback=ctrl,localSchedule=ctrl,localProtection=ctrl),status='ENABLED',heartbeatTimeoutSec=120)
nodes=[('PIP-JZ-E8QK','东渠水源',None,None,80,2),('PIP-JZ-N4VH','东渠首部主管','PIP-JZ-E8QK','DEV-JZ-P4KR',80,2),('PIP-JZ-W7MT','西泵首部主管',None,'DEV-JZ-P9VT',110,1)]
for nid,name,parent,pump,cap,concurrent in nodes:
    seed('PipeNode',nodeId=nid,farmId=farm,parentNodeId=parent,name=name,kind='SOURCE' if not pump else 'MAIN',pumpDeviceId=pump,
         capacityM3h=cap,maxConcurrentZones=concurrent,depthCm=4.2 if pump else 0,intervalCm=30 if pump else 0,designFlowM3h=cap,status='ENABLED')
zone_specs=[('ZON-JZ-A7KM',fids[0],'PIP-JZ-N4VH','DEV-JZ-V6HA','东渠北段',19.3,55,'PT-JZ-F8CN'),
 ('ZON-JZ-H4QW',fids[0],'PIP-JZ-N4VH','DEV-JZ-V3QM','东渠南段',19.3,45,'PT-JZ-F8CN'),
 ('ZON-JZ-R9FV',fids[1],'PIP-JZ-W7MT','DEV-JZ-V8FN','西泵南畦',52.4,96,'PT-JZ-F3NM'),
 ('ZON-JZ-T6PH',fids[2],'PIP-JZ-N4VH','DEV-JZ-V5RD','河沿试验区',26.8,34,'PT-JZ-F6QH')]
soil_ids=['PT-JZ-S7KA','PT-JZ-S7KB','PT-JZ-S4PC','PT-JZ-S9MD']
for i,(zid,fid,nid,vid,name,area,flow,mp) in enumerate(zone_specs):
    seed('IrrigationZone',zoneId=zid,farmId=farm,fieldId=fid,sourceNodeId=nid,valveDeviceId=vid,meterPointId=mp,
         soilPointIds=soil_ids[:2] if i<2 else [soil_ids[i]],name=name,areaMu=area,designFlowM3h=flow,
         accountingMethod='ALLOCATED' if i<2 else 'MEASURED',status='ENABLED',allocationRule='共享总表增量扣除独立分表后按各阀门实际有效开启时长×经核准流量权重分配，权重归一化且和等于剩余增量' if i<2 else None)
point_specs=[('PT-JZ-S7KA','DEV-JZ-S7KW','ZON-JZ-A7KM','SOIL_MOISTURE','%VWC',20,20.8),('PT-JZ-S7KB','DEV-JZ-S7KW','ZON-JZ-A7KM','SOIL_MOISTURE','%VWC',40,23.6),
 ('PT-JZ-S4PC','DEV-JZ-S4PV','ZON-JZ-R9FV','SOIL_MOISTURE','%VWC',20,24.9),('PT-JZ-S9MD','DEV-JZ-S9MT','ZON-JZ-T6PH','SOIL_MOISTURE','%VWC',20,18.4),
 ('PT-JZ-F8CN','DEV-JZ-F8CH',None,'METER_TOTAL','m³',0,4832.7),('PT-JZ-F3NM','DEV-JZ-F3NK','ZON-JZ-R9FV','METER_TOTAL','m³',0,9274.3),('PT-JZ-F6QH','DEV-JZ-F6QV','ZON-JZ-T6PH','METER_TOTAL','m³',0,1863.2),
 ('PT-JZ-R4HA','DEV-JZ-R4HD','ZON-JZ-A7KM','PRESSURE','MPa',0,0.16),('PT-JZ-R7KB','DEV-JZ-R7KP','ZON-JZ-R9FV','PRESSURE','MPa',0,0.02),
 ('PT-JZ-F8CV','DEV-JZ-F8CH',None,'FLOW_RATE','m³/h',0,55.0),('PT-JZ-F3NV','DEV-JZ-F3NK','ZON-JZ-R9FV','FLOW_RATE','m³/h',0,0),
 ('PT-JZ-P4KS','DEV-JZ-P4KR',None,'PUMP_STATE','state',0,1),('PT-JZ-P9VS','DEV-JZ-P9VT',None,'PUMP_STATE','state',0,0),
 ('PT-JZ-V6HS','DEV-JZ-V6HA','ZON-JZ-A7KM','VALVE_STATE','state',0,1),('PT-JZ-V3QS','DEV-JZ-V3QM','ZON-JZ-H4QW','VALVE_STATE','state',0,0)]
for idx,(pid,did,zid,kind,unit,depth,value) in enumerate(point_specs):
    seed('Point',pointId=pid,deviceId=did,zoneId=zid,name=next(d[1] for d in devs if d[0]==did)+'·'+kind,kind=kind,address='register:'+hashlib.sha256(pid.encode()).hexdigest()[:4],unit=unit,
        depthCm=depth,rangeMin=0,rangeMax=100 if kind=='SOIL_MOISTURE' else 1 if kind in ('PRESSURE','PUMP_STATE','VALVE_STATE') else 99999999,
        staleAfterSec=900 if kind=='SOIL_MOISTURE' else 60,scale=1,offset=0,writable=False)
    stamp='2026-10-25T08:46:53+08:00' if did=='DEV-JZ-S9MT' else ['2026-10-25T10:17:46+08:00','2026-10-25T10:18:07+08:00','2026-10-25T10:18:29+08:00'][idx%3]
    rid='RDG-JZ-'+hashlib.sha256((pid+stamp).encode()).hexdigest()[:10].upper()
    seed('TelemetryReading',readingId=rid,pointId=pid,observedAt=stamp,ingestedAt=stamp,value=value,quality='VALID',gatewayMessageId='GW-'+rid)
for pid,base in [('PT-JZ-S7KA',20.8),('PT-JZ-S7KB',23.6),('PT-JZ-S4PC',24.9)]:
    for t,delta in [('2026-10-25T06:13:47+08:00',0.7),('2026-10-25T07:26:18+08:00',0.4),('2026-10-25T08:54:39+08:00',0.2),('2026-10-25T09:41:26+08:00',-0.1)]:
        rid='RDG-JZ-'+hashlib.sha256((pid+t).encode()).hexdigest()[:10].upper()
        seed('TelemetryReading',readingId=rid,pointId=pid,observedAt=t,ingestedAt=t,value=round(base+delta,1),quality='VALID',gatewayMessageId='GW-'+rid)
strategies=[('STR-JZ-K8QM','冬小麦出苗补水规则','MOISTURE',21.5,138,240,'ENABLED'),('STR-JZ-F4NW','西泵定量补水规则','VOLUME',None,385.7,300,'ENABLED'),('STR-JZ-P7VH','河沿墒情观察规则','MOISTURE',20.0,176.2,360,'DISABLED')]
for i,(sid,name,mode,threshold,vol,dur,status) in enumerate(strategies):
    seed('Strategy',strategyId=sid,farmId=farm,name=name,crop='冬小麦',stage='EMERGENCE',zoneIds=[zone_specs[0][0],zone_specs[1][0]] if i==0 else [zone_specs[i+1][0]],triggerMode=mode,
        thresholdVwc=threshold,targetVolumeM3=vol,maxDurationMin=dur,allowedStart='05:30',allowedEnd='18:20',executionMode='CONFIRM_REQUIRED',status=status)
plans=[('PLN-JZ-Q7KR','东渠北段出苗补水','STR-JZ-K8QM','2026-10-25T09:52:31+08:00','EXECUTING','ZON-JZ-A7KM',138,240,55),
       ('PLN-JZ-C9VH','西泵南畦补水','STR-JZ-F4NW','2026-10-24T05:41:28+08:00','COMPLETED','ZON-JZ-R9FV',385.7,300,96),
       ('PLN-JZ-M4FD','东渠南段轮灌编排','STR-JZ-K8QM','2026-10-25T14:36:17+08:00','DRAFT','ZON-JZ-H4QW',138,240,45)]
step_ids={}
for pid,name,st,at,status,zid,vol,dur,flow in plans:
    seed('Plan',planId=pid,farmId=farm,name=name,strategyId=st,strategySnapshot=next(x for x in SEEDS['Strategy'] if x['strategyId']==st).copy(),scheduledAt=at,status=status,conflictHash=None,createdBy=users[1][0])
    psid='PST-JZ-'+hashlib.sha256(pid.encode()).hexdigest()[:6].upper();step_ids[pid]=psid
    seed('PlanStep',planStepId=psid,planId=pid,zoneId=zid,order=1,targetVolumeM3=vol,maxDurationMin=dur,expectedFlowM3h=flow)
run1='RUN-JZ-N8QF';run2='RUN-JZ-V4KM';rs1='RST-JZ-T8QW';rs2='RST-JZ-C6HP';cmd='CMD-JZ-R9FV'
seed('IrrigationRun',runId=run1,farmId=farm,planId=plans[0][0],status='RUNNING',actualStartedAt='2026-10-25T09:53:08+08:00',actualEndedAt=None,requestedAt='2026-10-25T09:52:46+08:00',activeStepId=rs1,lastCommandId=cmd,accountingClosed=False)
seed('IrrigationRun',runId=run2,farmId=farm,planId=plans[1][0],status='COMPLETED',actualStartedAt='2026-10-24T05:42:13+08:00',actualEndedAt='2026-10-24T09:43:17+08:00',requestedAt='2026-10-24T05:41:44+08:00',activeStepId=None,lastCommandId=None,accountingClosed=True)
seed('RunStep',runStepId=rs1,runId=run1,planStepId=step_ids[plans[0][0]],zoneId='ZON-JZ-A7KM',status='RUNNING',targetVolumeM3=138,meterStart=4809.5,meterEnd=None,startedAt='2026-10-25T09:53:08+08:00',endedAt=None)
seed('RunStep',runStepId=rs2,runId=run2,planStepId=step_ids[plans[1][0]],zoneId='ZON-JZ-R9FV',status='COMPLETED',targetVolumeM3=385.7,meterStart=8888.6,meterEnd=9274.3,startedAt='2026-10-24T05:42:13+08:00',endedAt='2026-10-24T09:43:17+08:00')
seed('CommandOutbox',commandId=cmd,runId=run1,actorId=users[2][0],intent='START',status='CONFIRMED',expectedRunVersion=1,idempotencyKey='START-'+run1+'-R8QH',correlationId='COR-JZ-D7MN',sequenceSnapshot={'sourceNodeId':'PIP-JZ-N4VH','signed':True,'steps':['OPEN:DEV-JZ-V6HA','START:DEV-JZ-P4KR'],'note':'仅用于验收的已签核顺序，生产需按现场工艺替换'},requestedAt='2026-10-25T09:52:46+08:00',ackAt='2026-10-25T09:52:49+08:00',confirmedAt='2026-10-25T09:53:08+08:00',failureCode=None,reason='按已发布出苗补水计划启动东渠北段。')
for phase,t,did in [('ACKNOWLEDGED','2026-10-25T09:52:49+08:00','DEV-JZ-G8QP'),('CONFIRMED','2026-10-25T09:53:02+08:00','DEV-JZ-V6HA'),('CONFIRMED','2026-10-25T09:53:08+08:00','DEV-JZ-P4KR')]:
    ev='CEV-JZ-'+hashlib.sha256((phase+t).encode()).hexdigest()[:6].upper()
    seed('CommandEvent',eventId=ev,commandId=cmd,deviceId=did,gatewayEventId='GWE-'+ev,phase=phase,occurredAt=t,payload={'source':'signed_fixture','stateConfirmed':phase=='CONFIRMED'})
water_refs=[]
for t,val in [('2026-10-24T05:42:13+08:00',8888.6),('2026-10-24T09:43:17+08:00',9274.3)]:
    rid='RDG-JZ-'+hashlib.sha256(t.encode()).hexdigest()[:10].upper();water_refs.append(rid)
    seed('TelemetryReading',readingId=rid,pointId='PT-JZ-F3NM',observedAt=t,ingestedAt=t,value=val,quality='VALID',gatewayMessageId='GW-'+rid)
seed('WaterLedger',ledgerId='WTR-JZ-Q6MF',runId=run2,runStepId=rs2,zoneId='ZON-JZ-R9FV',seasonId='SEA-JZ-C6QK',startedAt='2026-10-24T05:42:13+08:00',endedAt='2026-10-24T09:43:17+08:00',volumeM3=385.7,method='MEASURED',sourceReadingIds=water_refs,allocationRule=None,qualityStatus='FINAL',revisionOf=None)
seed('Alarm',alarmId='ALM-JZ-S8HD',farmId=farm,deviceId='DEV-JZ-S9MT',zoneId='ZON-JZ-T6PH',runId=None,kind='DEVICE_OFFLINE',severity='MEDIUM',status='ASSIGNED',recovery='ACTIVE',openedAt='2026-10-25T09:03:11+08:00',recoveredAt=None,acknowledgedBy=users[2][0],acknowledgedAt='2026-10-25T09:08:27+08:00',closedAt=None,handlingNote='河沿探头心跳中断，已通知现场检查供电与接线。')
seed('WorkOrder',workOrderId='WO-JZ-K7QV',farmId=farm,alarmId='ALM-JZ-S8HD',zoneId='ZON-JZ-T6PH',deviceId='DEV-JZ-S9MT',kind='DEVICE_REPAIR',status='IN_PROGRESS',assigneeId=users[3][0],dueAt='2026-10-25T15:26:39+08:00',startedAt='2026-10-25T09:29:16+08:00',resultNote=None,completedAt=None,acceptedBy=None,requestNote='检查河沿探头供电端子、太阳能电源和网关通信链路。',reviewNote=None)
seed('Calibration',calibrationId='CAL-JZ-N4MH',pointId='PT-JZ-S7KA',actorId=users[3][0],referenceValue=22.1,measuredValue=22.1,oldOffset=0,newOffset=0,calibratedAt='2026-10-20T14:38:27+08:00',note='以现场参考仪复核，偏差在记录要求内，保持原系数。')
for kind,eid in [('field',fids[0]),('device','DEV-JZ-S7KW')]:
    payload_base=f'https://irrigation.runhe.example/asset/{kind}/{eid}?v=1'
    checksum=hashlib.sha256((kind+':'+eid+':1').encode()).hexdigest()[:12]
    seed('QrCode',qrId='QR-JZ-'+hashlib.sha256(eid.encode()).hexdigest()[:6].upper(),deviceId=eid if kind=='device' else None,fieldId=eid if kind=='field' else None,
         payload=payload_base+'&c='+checksum,checksum=checksum,status='ACTIVE',issuedAt='2026-09-22T11:46:37+08:00')
seed('WaterBaseline',baselineId='BAS-JZ-H4QM',fieldId=fids[1],seasonId='SEA-JZ-C6QK',basis='APPROVED_REFERENCE',referenceAreaMu=52.4,referenceVolumeM3=462.0,referenceStart='2026-10-24',referenceEnd='2026-10-24',sourceNote='演示核准值，用于同田块同作物单次出苗补水窗口比较，不代表通用农艺定额。',approvedBy=users[1][0],status='ENABLED')
EXPORT_CONTENT='ledgerId,fieldId,fieldName,runId,volumeM3,method\nWTR-JZ-Q6MF,FLD-JZ-M9R2,西泵南畦,RUN-JZ-V4KM,385.7,MEASURED\n'
seed('ExportJob',exportId='EXP-JZ-M8QV',farmId=farm,createdBy=users[1][0],filterSnapshot={'fieldId':fids[1],'startAt':'2026-10-24T00:00:00+08:00','endAt':'2026-10-25T00:00:00+08:00'},status='READY',sourceRevision='REV-JZ-Q6MN',fileName='西泵南畦_20261024_用水明细.csv',downloadUrl='/api/exports/EXP-JZ-M8QV/content',expiresAt='2026-10-26T09:36:41+08:00',rowCount=1,checksum=hashlib.sha256(EXPORT_CONTENT.encode()).hexdigest())
seed('SystemPolicy',policyId='POL-JZ-F8QM',farmId=farm,defaultStaleSec=120,commandAckTimeoutSec=12,actionConfirmTimeoutSec=48,maxScheduleDays=30,
     commandSequence={'PIP-JZ-N4VH':{'start':['OPEN_SELECTED_VALVE','CONFIRM_VALVE_OPEN','START_PUMP','CONFIRM_PUMP_RUNNING'],'stop':['STOP_PUMP','CONFIRM_PUMP_STOPPED','CLOSE_SELECTED_VALVE','CONFIRM_VALVE_CLOSED']}},
     localDisconnectPolicy='演示控制器保持本地保护并禁止云端自动补发；生产规则需现场签核',capabilitySignoff={'fixtureOnly':True,'signedBy':users[1][0],'signedAt':'2026-10-21T16:53:28+08:00'})
seed('AuditLog',auditId='AUD-JZ-R6HW',farmId=farm,actorId=users[2][0],actionId='RUN_START',entityType='IrrigationRun',entityId=run1,beforeVersion=1,afterVersion=2,occurredAt='2026-10-25T09:52:46+08:00',correlationId='COR-JZ-D7MN',result='ACCEPTED',detail={'commandId':cmd,'runStatus':'STARTING','note':'仅为指令受理，动作完成另有反馈证据。'})

# Runtime metadata follows event chronology, not a fixed incrementing timestamp pattern.
plan_dates={plans[0][0]:('2026-10-24T16:32:47+08:00','2026-10-25T09:53:08+08:00'),
    plans[1][0]:('2026-10-23T17:16:28+08:00','2026-10-24T09:43:17+08:00'),
    plans[2][0]:('2026-10-25T08:23:41+08:00','2026-10-25T08:47:19+08:00')}
for r in SEEDS['Plan']+SEEDS['PlanStep']:
    r['createdAt'],r['updatedAt']=plan_dates[r['planId']]
for r in SEEDS['IrrigationRun']:
    r['createdAt']=r['requestedAt'];r['updatedAt']=r['actualEndedAt'] or '2026-10-25T10:18:29+08:00';r['version']=4 if r['status']=='COMPLETED' else 3
for r in SEEDS['RunStep']:
    run=next(x for x in SEEDS['IrrigationRun'] if x['runId']==r['runId'])
    r['createdAt']=run['requestedAt'];r['updatedAt']=r['endedAt'] or '2026-10-25T10:18:29+08:00'
for r in SEEDS['CommandOutbox']:r['createdAt']=r['requestedAt'];r['updatedAt']=r['confirmedAt'];r['version']=3
for r in SEEDS['Alarm']:r['createdAt']=r['openedAt'];r['updatedAt']='2026-10-25T09:13:52+08:00';r['version']=3
for r in SEEDS['WorkOrder']:r['createdAt']='2026-10-25T09:13:52+08:00';r['updatedAt']=r['startedAt'];r['version']=2
for r in SEEDS['ExportJob']:r['createdAt']='2026-10-25T09:34:18+08:00';r['updatedAt']='2026-10-25T09:36:41+08:00';r['version']=2

def build_document():
    di=node(ROOT,'document_info')
    for tag,text in {
        'system_name':NAME,'document_type':'真实设备接入型桌面Web前端交互需求规格说明书','version':'V1.0（沿用模板契约Schema V2.1）',
        'created_date':'2026-10-26','updated_date':'2026-10-26',
        'document_purpose':'定义田块、种植、管网、墒情、策略、轮灌计划、现场执行、维护和用水核算的页面与可执行契约。全部正式实体由统一Store管理，页面只维护Draft与UI。页面、组件、Branch、Overlay、Action、Transaction、Selector、Query和生命周期均以稳定ID互相引用。本文是前端需求文档，不代表已完成现场硬件联调。',
        'scope_statement':'按用户选择B和已有设备接入场景建设。第一版为9个业务模块加1个系统管理配套模块，共20个Screen；详情和编辑不成为一级菜单。现有设备型号、协议和点表尚未提供，生产适配器默认UNVERIFIED，远程操作必须经过能力核验与现场联动签核。验收模拟网关与生产通道隔离，禁止模拟数据驱动真实设备。第一版以规则建议、人工确认及受控自动能力为范围。'
    }.items():node(di,tag,text)
    bg=node(ROOT,'industry_background')
    node(bg,'business_context','服务农场灌溉管理、泵阀操作和田间维护人员，将田块—种植季—管网—分区—设备—计量关系形成可追溯闭环。浅埋滴灌设施不可仅凭页面显示判断状态，系统以压力、流量、根区墒情及设备反馈辅助控制和排查；业务异常必须保留现场证据及处理责任。')
    concepts=node(bg,'professional_concepts')
    for name,text in [('浅埋微灌','记录现场滴灌带埋深、间距、规格及分区供水关系，参数为实测登记，不预设统一技术定额。'),('根区墒情','按点位深度、采样时间和质量标识展示体积含水率；过期数据不能当作有效自动触发依据。'),('轮灌分区','由确定阀门和计量关系控制的供水单元，多个分区共享泵站时须校验容量和并发约束。'),('指令受理与动作确认','服务端持久化命令、通信应答、设备实际反馈是不同阶段，ACK不能直接转换为运行成功。'),('计量口径','实测、分摊与估算分开统计；分摊同一总表读数时所有分区之和不得超过有效总表增量。'),('可比节水基准','基准必须声明田块、作物、面积和比较窗口，缺少可比依据显示不可计算而不是0%。')]:
        node(concepts,'concept',text,name=name)
    rules(bg,'reference_principles',[
        '页面范围遵循已确认的第一版功能范围文档，水肥一体化和预测需水模型列为后续扩展。',
        '模板结构和Schema字段保持，原行业业务实体与示例按田间灌溉重新建模。',
        '所有多业务路径组件由结构化分支选择；无命中必须BLOCK_AND_REPORT。',
        '物理设备动作不具有数据库回滚语义：事务原子性止于指令入队和记录；现场未知结果通过对账和告警解决。',
        '生产控制能力以真实厂家协议、点表、现场工艺和签核为依据，资料未核验时禁用控制并显示原因。',
        '不设计右侧抽屉，不在主内容区上方添加页面描述或左上角说明性副标题。'
    ],item='principle')
    overall=node(ROOT,'overall_requirements')
    rules(overall,'business_goals',[
        '建立田块与种植季事实，历史记录不随当前种植信息被覆盖。','将水源、泵站、分区、阀门和计量点准确关联。',
        '以有效监测数据形成可解释灌溉建议并编排供水资源。','以现场反馈验证泵阀动作，保留未知结果和异常对账。',
        '闭环记录告警确认、维护派工、现场结果和验收。','以统一水量账本和可比基准核算用水及节水。'
    ],item='goal')
    roles=node(overall,'user_roles')
    descriptions={'ADMIN':'配置设备接入、账号、运行参数；具备灌溉管理权限但不能绕过现场保护。',
        'MANAGER':'维护授权田块、管网、策略和计划，派工验收，核准基准及查看审计。',
        'OPERATOR':'查看授权田块监测与计划，执行泵阀相关运行控制、确认告警；不修改接入协议和账号。',
        'TECHNICIAN':'查看授权设备，登记校准、处理本人维护工单；不发布灌溉计划和核准基准。',
        'VIEWER':'只读授权田块、监测、运行和统计；无正式写权限和维护执行权限。'}
    role_names={'ADMIN':'系统管理员','MANAGER':'灌溉管理人员','OPERATOR':'灌溉操作人员','TECHNICIAN':'巡检维护人员','VIEWER':'只读查看人员'}
    for role,desc in descriptions.items():node(roles,'role',desc,code=role,name=role_names[role])
    ml=node(overall,'module_list',expected_module_count=len(MODS))
    for mid,name,sids,obj in MODS:node(ml,'module_ref',name,module_id=mid,id=mid,name=name,sidebar_menu='|'.join(sids))
    navs=node(overall,'navigation_structure')
    navgroups=[('田间总览',['OVERVIEW']),('田间资源',['FIELD-LIST','NETWORK']),('感知设备',['DEVICE-LIST','MONITOR']),
        ('灌溉作业',['STRATEGY-LIST','PLAN-LIST','RUN-LIST']),('异常维护',['ALARM-LIST','WORKORDER-LIST']),('统计分析',['WATER-REPORT']),('系统管理',['SETTINGS','AUDIT'])]
    for label,sids in navgroups:
        node(navs,'sidebar_item',' | '.join(S[x]['page_name']+':'+x for x in sids),name=label,screen_ids='|'.join(sids),level='1_with_optional_level2',role='ADMIN|MANAGER' if label=='系统管理' else 'AUTHORIZED')
    sp=node(overall,'secondary_pages')
    for mid,name,sids,obj in MODS:node(sp,'page_group','|'.join(sids),module_id=mid,name=name,owner=mid)
    rules(overall,'secondary_page_switching_rules',[
        '详情和编辑仅从目录、卡片、行操作、扫码或关联业务进入，不注册一级菜单。',
        '切换模块、页面返回、浏览器返回、表单取消均先经统一Draft离开守卫。',
        '列表返回恢复query、filters、sort、page、pageSize、selectedId和scrollTop，数据更新后先重算再定位。',
        '详情路由必须包含稳定实体ID，实体不存在展示ENTITY_NOT_FOUND及固定回退入口。',
        '路由权限由session.role和fieldIds共同决定，隐藏按钮不代替服务端鉴权。',
        '一时刻仅一个活动Screen和一个活动模态上下文可交互；隐藏页面不可聚焦。'
    ])
    for r in overall.find('secondary_page_switching_rules'):r.set('owner','GLOBAL')

    pic=node(ROOT,'page_integration_contract',version='2.0',authority='highest')
    node(pic,'contract_purpose','通过manifest、组件契约和可执行扩展定义20个Screen的确定行为。ID为唯一绑定依据，模板示例计数不具有本系统业务含义。')
    rules(pic,'authority_and_conflict_rules',[
        '明确业务范围和本系统实体优先于旧行业示例；结构化执行契约优先于解释性文本。',
        '实体字段、枚举与Action以data_model_contract为准；可见组件不可直接改实体。',
        'screen_manifest为页面与路由唯一清单；组件目标和页面布局不得凭标题猜测。',
        '多路径以structured_condition_branches为准；Schema兼容的DRAWER或OPEN_DRAWER不启用实际抽屉。'
    ])
    rules(pic,'single_page_runtime',[
        '最终前端采用统一Router、Store、Action Dispatcher和Overlay宿主，HTML文件名仅用于页面绑定，不创建独立业务Store。',
        '桌面Web采用顶栏农场身份与分组侧栏，窄屏将同一导航折叠为居中导航弹窗，禁止右侧抽屉。',
        'Router管理currentScreenId、routeParams、historyStack、returnSnapshot和pendingNavigation。',
        'Store规范化管理data_model_contract所有实体；页面只存Draft和UI状态，计算结果由Selector缓存并随依赖版本失效。',
        '正式写操作由服务端Action返回权威数据后合并Store；不乐观显示泵阀动作成功。',
        '订阅仅在活动页注册，卸载AbortController、计时器、防抖、事件和媒体资源；已受理的服务端任务不随页面卸载取消。',
        '扫码只读取已登记实体载荷，摄像头由用户主动开启，手输和扫码枪使用相同解析Query。',
        '生产与模拟连接由部署配置固定，验收UI禁止切到真实设备通道。'
    ])
    binding=node(pic,'filename_and_text_binding_protocol')
    rules(binding,'page_binding',['以screen_manifest.html_file完整文件名精确绑定screen_id，重复或缺失标记PAGE_UNMAPPED。','同一文件只能对应一个Screen；路由文件加载失败保持来源页，不猜测目标。'])
    rules(binding,'component_binding',[
        '优先注入data-component-id；首次绑定只在Screen或overlay_owner_id指定作用域内使用match。',
        'match_mode包括exact_text、placeholder、nearby_label、text_with_region、icon_position、all、occurrence；occurrence必须带region与occurrence。',
        'all仅适用于同族重复行、卡片或步骤，事件从data-entity-id或data-step-draft-id读取稳定主键，不以行号识别。',
        '匹配0个为MISSING，多于预期为AMBIGUOUS，均阻止验收；重复弹窗文字按scope=OVERLAY限定。',
        '绑定完成后事件只依赖component_id和显式参数，禁止通过文本、颜色、DOM顺序推导动作。',
        'field_group与component_group仅为兼容绑定声明，expanded_component_ids指向完整组件，不额外生成可操作控件。'
    ])
    schema(pic,'screen_layout_contract_schema')
    manifest=node(pic,'screen_manifest',expected_screen_count=len(SCREENS))
    for s in SCREENS:node(manifest,'screen',**{k:v for k,v in s.items() if k!='required_params'})
    shell=node(pic,'web_shell_component_contracts')
    node(shell,'rule','所有已认证页面继承这里的导航、返回与退出契约。窄屏菜单使用居中DIALOG-NAVIGATION；主内容区不得添加页面描述或说明性副标题；标题只呈现必要页面名或实体标识。')
    for sid,c in COMP:
        if sid=='WEB-SHELL':node(shell,'component',**c)
    cs=schema(pic,'component_contract_schema')
    for fieldtext in ['match_mode：匹配方式必须显式提供；动态组件必须绑定实体主键。','element_kind：实际元素类型，不以div代替可访问按钮。','action_id：调用唯一Action、Local Action或Query；RESOLVE_BRANCH通过branch_set_id解析。','branch_set_id：仅RESOLVE_BRANCH提供，必须可解析，otherwise=BLOCK_AND_REPORT。','affected_screens：通过业务Action的affected_screens获取，不在页面维护统计副本。']:
        node(cs,'required_field',fieldtext)
    templates=node(pic,'global_behavior_templates')
    common={'FIELD_EDIT':'只修改可追踪Draft，依字段契约清除错误；离开前dirty守卫。',
        'QUERY':'读取保留条件和最后成功结果，requestId防止旧响应覆盖；空结果与失败分离。',
        'SUBMIT':'先验角色、范围、版本、状态和字段，提交锁与幂等键阻止重复；成功合并权威Store，失败整体回滚正式写入并保留输入。',
        'CONFIRM_DIALOG':'居中展示确定影响对象和后果；提交锁定关闭，取消只销毁overlayDraft。',
        'NAVIGATE':'目标必须在manifest，参数和权限通过后保存来源快照并导航；返回恢复上下文。',
        'DISABLED':'禁用控件无路由和业务副作用，aria-disabled及就近原因可读取。'}
    for k,t in common.items():node(templates,'template',t,id=k)
    sc=node(pic,'screen_component_contracts')
    shellids='|'.join(c['component_id'] for sid,c in COMP if sid=='WEB-SHELL')
    for s in SCREENS:
        sid=s['screen_id'];sn=node(sc,'screen_contract',screen_id=sid,html_file=s['html_file'],inherited_shell_components='NONE' if sid=='AUTH-LOGIN' else shellids)
        for ss,c in COMP:
            if ss==sid:node(sn,'component',**c)
    for c in sc.findall('./screen_contract/component'):
        cid=c.get('component_id');sid=next(sid for sid,meta in COMP if meta['component_id']==cid)
        c.set('region',c.get('overlay_owner_id') or S[sid]['primary_interaction_surface'])
        if cid=='AUTH-LOGIN.SUBMIT':c.set('match_mode','occurrence');c.set('occurrence','1')
    # Preserve group structures without introducing incompletely specified controls.
    sn=next(x for x in sc if x.get('screen_id')=='FIELD-EDIT')
    fg=node(sn,'field_group',component_id_prefix='FIELD-EDIT',labels='田块编码|田块名称|田块面积（亩）|土壤类型|田块位置|田块负责人',match_mode='nearby_label',event='input',action_type='UPDATE_STATE',template='FIELD_EDIT',declaration_only='true',expanded_component_ids='|'.join('FIELD-EDIT.'+x for x in ['CODE','NAME','AREA','SOIL','LOCATION','MANAGER']))
    for t,v in {'preconditions':'逐项使用expanded_component_ids的完整契约，不产生额外组件。','immediate_feedback':'每个字段按自己的校验更新draft.field，不批量覆盖。','data_consequence':'只写对应Draft字段，不写正式Field。','failure_consequence':'保留各自输入并在具体字段定位错误。','disabled_rule':'继承对应字段的权限、版本与提交锁。'}.items():node(fg,t,v)
    sn=next(x for x in sc if x.get('screen_id')=='RUN-DETAIL')
    cg=node(sn,'component_group',component_id_prefix='RUN-DETAIL',matches='暂停或恢复灌溉',match_mode='exact_text',element_kind='button',event='click',action_type='RESOLVE_BRANCH',branch_set_id='BRANCH-RUN-PAUSE-RESUME',declaration_only='true',expanded_component_ids='RUN-DETAIL.PAUSE-RESUME')
    node(cg,'branch_set_ref','BRANCH-RUN-PAUSE-RESUME')
    pause=next(c for sid,c in COMP if c['component_id']=='RUN-DETAIL.PAUSE-RESUME')
    for t in ['preconditions','immediate_feedback','data_consequence','success_consequence','failure_consequence','disabled_rule','return_rule']:node(cg,t,pause[t])
    rules(pic,'navigation_and_return_rules',[
        '合法screen_id以manifest为准；缺少必要ID显示PARAMETER_MISSING，实体不存在显示ENTITY_NOT_FOUND；错误面板提供WEB-SHELL.BACK及总览入口。',
        '普通进入push，保存成功replace到指定列表或详情；相同screen_id和参数不得重复压栈。',
        '全局返回通过BRANCH-GLOBAL-BACK，ui.returnTarget只允许真实来源或manifest.back_fallback。',
        'Draft已修改时所有离开意图经DIALOG-DISCARD-DRAFT，确认后才能清理；原生关闭浏览器使用beforeunload提示。',
        '会话失效replace AUTH-LOGIN并保存pendingNavigation；重新登录后由用户重试原入口，不自动重新提交写Action。',
        '未决命令不因返回或刷新消失，RUN-DETAIL重新进入从CommandOutbox读取真实状态。'
    ])
    rules(pic,'shared_state_and_consequence_rules',[
        'Store只保留权威实体；Draft使用draftNamespace+entityId+editingSessionId隔离，禁止作为统计输入。',
        '泵阀控制事务同时创建CommandOutbox、运行过渡态与审计；发送在提交之后，失败不能虚构已撤销物理动作。',
        '水量结算同时写WaterLedger与运行完成状态，来源读数保留；修订以revisionOf追加。',
        '告警派工同时写WorkOrder与Alarm处理态；验收工单不等于关闭告警。',
        '策略版本变化不改已发布计划快照；管网容量变更使旧资源检查hash失效。',
        '统计、分页、泳道计数和卡片来自对应Selector的同一过滤全集，任何页面不得维护独立计数。',
        'Action成功按affected_screens通知依赖失效与重查；隐藏页面下次进入读取最新Store而非修改隐藏DOM。'
    ])

    ex=node(pic,'executable_contract_extensions',version='2.1',authority='execution_override')
    rules(ex,'interpretation_rules',[
        'Branch表达式只读Session、Route、Store与显式UI；无分支命中BLOCK_AND_REPORT，不猜测默认目标。',
        '别名strategy、run、user、selectedAlarm分别由事件entityId或routeParams主键从Strategy、IrrigationRun、User、Alarm读取；别名缺失阻断。',
        'Action_id在action_registry、local_action_registry或query_registry中唯一；分发器仅组合已有Action，不持有业务副本。',
        '正式写入必须由服务端Action校验权限、version与幂等键；Local Action只允许UI、Draft、Router和设备读取API。',
        'BY_BRANCH、STAY、NONE是保留值而非实际ID；只有RESOLVE_BRANCH使用BY_BRANCH。',
        '同意硬件接入范围不表示未知厂家协议已具备；生产适配器必须按能力验证结果启用。'
    ])
    bs=node(ex,'structured_condition_branches');schema(bs,'branch_schema')
    rules(bs,'expression_rules',[
        "角色来自session.role，值为ADMIN、MANAGER、OPERATOR、TECHNICIAN、VIEWER。",
        'routeParams.mode只允许create或edit，实体ID必须满足各页required_params。',
        'strategy.status、run.status和user.status均读取本次事件对应的最新Store对象；ui.hasDirtyDraft由活动Draft与基线比较。',
        'ui.pendingNavigation、ui.returnTarget、ui.scanResolution必须由白名单解析器产生，不读取按钮文案或DOM顺序。',
        '所有分支按evaluation_order执行first_match，条件不得隐含第二个未登记业务路径；otherwise固定BLOCK_AND_REPORT。'
    ])
    for b in BRANCHES:
        be=node(bs,'branch_set',**{k:v for k,v in b.items() if k!='items'})
        for item in b['items']:node(be,'branch',**item)
    lc=node(ex,'page_lifecycle_contracts')
    rules(lc,'lifecycle_rules',[
        '页面进入按必要参数、角色和实体范围校验，再dispatch enter_action_id及queries，挂载selectors；不可在render函数中写业务实体。',
        'LOADING→READY/EMPTY/ERROR/FORBIDDEN状态确定；失败保持最后成功结果并展示对应错误；页面自己的RETRY-LOAD重试同Query。',
        '卸载取消页面资源但不取消服务端已受理CommandOutbox、导出或计量事务；订阅响应按screenInstanceId隔离。'
    ])
    for s in SCREENS:
        sid=s['screen_id']; ents,sel=DOMAIN_READS[sid]
        cleanup='中止查询与SSE订阅，取消防抖、定时器、图表实例和DOM事件；保留筛选分页返回快照'
        if sid in ('FIELD-EDIT','STRATEGY-EDIT','PLAN-EDIT','SETTINGS'):cleanup+='；离开守卫确认后清理活动Draft及校验错误'
        if sid=='DEVICE-DETAIL':cleanup+='；关闭SCANNER-ASSET，停止所有媒体轨道、worker及帧循环，释放二维码URL'
        if sid=='RUN-DETAIL':cleanup+='；服务端未决命令与反馈对账继续，禁止卸载触发停泵或删除命令'
        if sid=='WATER-REPORT':cleanup+='；取消导出状态轮询和文件URL，服务端导出任务继续'
        if sid=='AUTH-LOGIN':cleanup+='；清除密码内存与认证定时器'
        node(lc,'page_lifecycle',screen_id=sid,enter_action_id=Q[sid],required_params=s['required_params'],selectors=sel,queries=Q[sid],read_entities=ents,
             enter_ui_action_id='UI_INIT_'+sid.replace('-','_'),optional_params='query,filters,sort,page=1,pageSize=10; only recognized keys applied',
             state_contract='LOADING|READY|EMPTY|ERROR|FORBIDDEN|PARAMETER_MISSING|ENTITY_NOT_FOUND',unmount_cleanup=cleanup)
    oc=node(ex,'overlay_contract');schema(oc,'overlay_schema')
    rules(oc,'global_overlay_rules',[
        'overlay_registry是所有弹层唯一注册表，触发component.dialog_id或branch.dialog_id必须解析到唯一overlay_id。',
        '实际展示只允许居中模态，不使用右侧抽屉；Schema保留DRAWER兼容值但本系统实例不使用。',
        'owner_screen_id限定来源，GLOBAL只用于全局退出、离开确认和导航；每层必须登记实际触发器。',
        '字段来自Selector、Route、Draft或常量，打开不写正式实体；控件定义以scope=OVERLAY和overlay_owner_id限定。',
        '确认通过Action Dispatcher，重验权限、版本、状态和字段；提交期间锁触发器与确认、取消、遮罩、Escape及返回。',
        '重试复用同一clientRequestId，成功清理本实例Draft，失败保留可修正输入与正式Store原状态。',
        '打开background inert、滚动锁和焦点圈定；关闭回实际触发器，已卸载则回owner主工作区。',
        'Scanner关闭、切换摄像头和卸载必须停止媒体轨道；Preview关闭释放URL；不得在打开瞬间申请摄像头。',
        '字段编辑、确认、取消、关闭、遮罩、Escape及浏览器返回均由完整组件契约覆盖；不存在隐式业务按钮。'
    ])
    reg=node(oc,'overlay_registry')
    for o in OVERLAYS:node(reg,'overlay',**o)
    rules(ex,'overlay_integrity_contract',[
        'overlay_id、owner、触发器、确认Action及affected_screens必须互相可解析；未注册弹层禁止出现。',
        '模板原有弹层Schema字段保留，实际表单内容和状态机依据灌溉对象重建。',
        '关闭与取消不改变正式实体；成功回填以Action结果与Selector为准，不复制另一个业务对象。',
        '逐弹层验收前置条件、字段错误、Loading、防重复、取消、焦点、成功、失败及事务回滚。'
    ],version='2.1')
    build_model(ex)
    build_browser(ex)
    migrations=node(ex,'interaction_migration_registry',source='screen_component_contracts|web_shell_component_contracts|page_lifecycle_contracts',
                    migrated_count=len(COMP)+len(SCREENS),source_removed_after_migration='false')
    for sid,c in COMP:node(migrations,'migration',interaction_id='INT.'+c['component_id'],execution_ref='component:'+c['component_id'])
    for s in SCREENS:node(migrations,'migration',interaction_id='INT.'+s['screen_id']+'.ENTER',execution_ref='page_lifecycle:'+s['screen_id']+'|query:'+Q[s['screen_id']])
    rules(pic,'integration_acceptance_criteria',[
        '20个Screen、全部路由和组件ID唯一，manifest和生命周期一一对应。',
        '所有Action、Branch、Overlay、Query、Selector、Transaction引用可解析，Entity关系和主键完整。',
        '每个可操作控件的完整属性均非空；多路径组件只能RESOLVE_BRANCH且无命中阻断。',
        '未验证生产设备控制禁用；ACK与现场确认分开显示；超时UNKNOWN必须能重新查询和对账。',
        '全部正式写入由统一Action和事务处理，跨实体失败不留下部分业务记录。',
        '卡片、列表、筛选和分页同源，水量不重复计入，总览与报表口径一致。',
        '实际使用居中弹窗或独立详情页，无右侧抽屉、页面说明副标题和装饰二维码。',
        '交互迁移数量按组件和页面进入实际生成，不沿用模板计数。'
    ],item='criterion')
    for criterion in pic.find('integration_acceptance_criteria'):
        criterion.set('id','INT-AC-'+hashlib.sha256(criterion.text.encode()).hexdigest()[:8].upper())
    build_interaction_sections()
    build_modules()
    build_tail()

def build_model(ex):
    dm=node(ex,'data_model_contract',naming_style='camelCase',id_policy='global_unique',mutation_policy='action_only')
    rules(dm,'model_rules',[
        '正式实体以entity.id_field为唯一主键归一化存入Store；所有跨页关系只存ID。Draft/UI State不得作为正式实体数据源。',
        '除Session和immutable=true实体外，业务实体含version、createdAt、updatedAt；所有更新携带expectedVersion并做compare-and-swap。',
        '编号使用对象前缀、地区与稳定随机后缀，不按记录序号或创建顺序生成连续尾号；步骤order只表示显示顺序，不是ID。',
        '面积使用亩，体积使用m³，流量m³/h，压力MPa，含水率%VWC，深度cm；数值与单位分离，计算不使用格式化字符串。',
        '时间保存带时区ISO-8601，统计边界按Asia/Shanghai计算，范围使用[startAt,endAt)避免相邻区间重复计量。',
        'Point至IrrigationZone允许共享土层监测点但必须明确代表性；单总表分摊必须保存规则与来源读数，禁止全量记入每个分区。',
        '页面统一fields.id、name、areaMu、seasonId、zoneId和deviceId含义；重复列表组件从entityId读取对象，不凭可见文字查找。',
        'TelemetryReading、WaterLedger、Calibration、CommandEvent及AuditLog不可原地改写；更正水量以revisionOf追加，Selector剔除被替代记录。',
        'CommandOutbox是可靠发送队列，数据库提交后才向设备发送；状态不明不得自动生成相反操作以模拟回滚。',
        '服务端承担生产幂等、权限和事务；浏览器Store是权威实体的单一客户端缓存，不承担真实设备安全保护。',
        'fixture数据只进入隔离模拟适配器；未取得协议、型号、点表和工艺签核时生产控制为UNVERIFIED。',
        '缺少数据返回null与原因；NaN、缺测和过期不得转为0；基准为0不得计算百分比。',
        'QrCode.payload编码格式为https://irrigation.runhe.example/asset/{kind}/{entityId}?v=1&c={checksum}；kind仅device或field；checksum=SHA256(kind+":"+entityId+":1")前12位小写hex，仅检测载荷损坏，不能代替授权或签名。'
    ])
    im=node(dm,'implicit_fields',applies_to='除Session和immutable=true的实体')
    node(im,'field',name='version',type='integer',required='true',default='1')
    node(im,'field',name='createdAt',type='datetime',required='true')
    node(im,'field',name='updatedAt',type='datetime',required='true')
    enums=node(dm,'enum_definitions')
    for name,values in ENUMS.items():node(enums,'enum',name=name,values=values)
    entities=node(dm,'entities')
    for name,meta in ENTITIES.items():
        en=node(entities,'entity',name=name,id_field=meta['id_field'],immutable=str(meta['immutable']).lower())
        for f in meta['fields']:node(en,'field',**f)
    ar=node(dm,'action_registry')
    for a in ACTIONS:node(ar,'action',**a)
    ads=node(dm,'action_dispatchers')
    for b in BRANCHES:
        aid='DISPATCH_'+b['branch_set_id'].replace('-','_')
        concrete_actions=[a for a in ACTIONS if a['action_id'] in {i['action_id'] for i in b['items']}]
        affected=','.join(dict.fromkeys(s for a in concrete_actions for s in a['affected_screens'].split(','))) or 'NONE'
        node(ads,'dispatcher',action_id=aid,branch_set_id=b['branch_set_id'],dispatches_to='|'.join(dict.fromkeys(x['action_id'] for x in b['items'])),
             pre_query_id='QUERY_QR_RESOLVE' if b['branch_set_id']=='BRANCH-SCAN-RESULT' else 'NONE',
             execution_order='await pre_query_id then evaluate branch_set_id; query failure retains current overlay' if b['branch_set_id']=='BRANCH-SCAN-RESULT' else 'evaluate branch_set_id then execute exactly one action',
             affected_screens=affected)
        for ss,c in COMP:
            if c.get('branch_set_id')==b['branch_set_id']:c['action_id']=aid
        for c in ROOT.findall('.//screen_component_contracts//component')+ROOT.findall('.//web_shell_component_contracts/component'):
            if c.get('branch_set_id')==b['branch_set_id']:c.set('action_id',aid)
    for alias,bid in DISPATCH_ALIASES.items():
        branch=next(b for b in BRANCHES if b['branch_set_id']==bid)
        ids='|'.join(i['action_id'] for i in branch['items'])
        node(ads,'dispatcher',action_id=alias,branch_set_id=bid,dispatches_to=ids,pre_query_id='NONE',
             execution_order='alias of DISPATCH_'+bid.replace('-','_')+'; shared editor identity resolves exactly one registered create or update action')
    la=node(dm,'local_action_registry',mutation_limit='UI_STATE|DRAFT|ROUTER|DEVICE_API')
    for a in LOCALS.values():node(la,'local_action',**a)
    txs=node(dm,'transaction_rules')
    for a in ACTIONS:
        if a['transaction_id']=='NONE':continue
        key='actionId+clientRequestId+actorId'
        if a['action_id']=='INGEST_TELEMETRY':key='gatewayId+messageId'
        elif a['action_id']=='RECONCILE_COMMAND':key='commandId+gatewayEventId'
        elif a['action_id']=='FINALIZE_WATER':key='runStepId+settlementRevision'
        elif a['action_id']=='PLAN_PUBLISH':key='planId+expectedVersion+PUBLISH'
        node(txs,'transaction',transaction_id=a['transaction_id'],atomic='true',idempotency_key=key,rollback='all',partial_success='false',
            boundary='database_entities_and_outbox_only',rollback_detail='任何数据库写失败恢复该事务全部实体；已经提交后发生的硬件发送、现场水量和动作不可物理回滚，使用对账事件及告警处理')
    sr=node(dm,'selector_registry')
    for s in SELECTORS.values():node(sr,'selector',**s)
    qr=node(dm,'query_registry')
    for q in QUERIES.values():node(qr,'query',**q)

def build_browser(ex):
    bc=node(ex,'browser_acceptance_contract',runner='Playwright',browser='Chromium',transport='local_http')
    env=node(bc,'environment')
    settings={'defaultViewport':'1366x864','additionalViewports':'1024x768|768x1024','deviceScaleFactor':'1','locale':'zh-CN','timezoneId':'Asia/Shanghai',
        'reducedMotion':'reduce','animationPolicy':'等待transitionend后断言，必要时仅测试环境禁用动画','visualPixelThreshold':'0.10','maxDiffPixelRatio':'0.001',
        'geometryToleranceCssPx':'1','evidenceDirectory':'reports/browser-evidence/<screen_id>/',
        'sourceBaseline':'每个HTML注入统一行为前的截图及关键元素几何信息；业务重设计不要求保持旧行业视觉',
        'frozenClock':NOW,'adapterMode':'SIMULATED_GATEWAY_ONLY','realHardwareTraffic':'DENIED',
        'fixtureSemantics':'以下数据为隔离验收情境，不代表现场实际型号、读数或农艺阈值；beforeEach恢复同一实体种子'}
    settings['fixtureExportContent']=EXPORT_CONTENT
    settings['fixtureAuthentication']='隔离认证服务由测试运行器创建一次性凭据，不在XML保存密码；以User.account和role生成对应Session，测试运行器不得将夹具认证用于生产'
    for k,v in settings.items():node(env,'setting',name=k,value=v)
    fixtures=node(bc,'fixed_test_fixtures')
    for name,records in SEEDS.items():
        for record in records:
            attrs={'id':'FIXTURE.'+record[ENTITIES[name]['id_field']],'entity':name}
            attrs.update({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) for k,v in record.items()})
            node(fixtures,'fixture',**attrs)
    rules(bc,'execution_rules',[
        '先校验静态XML和引用再运行真实浏览器；当前文档生成阶段不将未执行的浏览器测试标为PASS。',
        '每个Screen必须通过路由实际打开；隐藏在内存、截图或假DOM不能替代真实交互。',
        '模拟适配器按命令阶段回放ACK、拒绝、丢包、超时和迟到反馈，隔离环境不访问真实网关。',
        '每个Overlay从注册触发器实际打开，逐字段输入与校验，确认、取消、关闭、焦点及锁定都需断言。',
        '每条Branch至少覆盖一次命中及一次无命中，验证无命中BLOCK_AND_REPORT且不改实体。',
        '跨页写入后比较Store、卡片、完整列表、筛选结果与分页总数，禁止仅看Toast。',
        '测试数据时间使用明确事件关系，成功受理后才可收到ACK，现场确认后才可结算账本。',
        '最终提交截图、trace、请求日志、Store前后差异、命中Branch与失败明细。'
    ])
    suites=node(bc,'required_test_suites')
    cases={
      'BROWSER-BINDING':['20个Screen文件名、route及data-component-id一一映射。','每个可操作元素必须属于完整组件或声明的可复用实例，MISSING/AMBIGUOUS均失败。','详情和编辑不占一级菜单，继承Shell权限一致。'],
      'BROWSER-VISUAL-BASELINE':['1366x864与1024x768下主要动作可见，768x1024导航使用居中菜单。','无右侧抽屉、页面顶部描述或左上角说明性副标题。','图表、时间轴、拓扑、泳道和表单各自保留manifest的功能区顺序及构图差异。'],
      'BROWSER-OVERLAY':['逐个注册弹层验证来源、字段和Action引用。','取消、遮罩、Escape与返回无正式数据副作用；提交中全部锁定。','验证背景inert、焦点圈定与归还，Scanner关闭后所有轨道readyState=ended。','二维码截图由独立解码器还原payload并对应唯一实体。'],
      'BROWSER-FORM':['田块面积小于已分区覆盖面积时不写Field。','策略MOISTURE缺阈值、AUTO未签核时不能保存；错误后输入保留。','编排步骤添加移除和上下移动只改Draft，稳定主键不随order变化。','重置需确认；取消重置保留现值，确认恢复本次读取基线。'],
      'BROWSER-BRANCH':['所有branch_set命中路径完整覆盖，无命中BLOCK_AND_REPORT。','新增与编辑分别调用CREATE和UPDATE，禁止靠按钮文字分派。','暂停与恢复按RUNNING和PAUSED分别打开专用弹窗。'],
      'BROWSER-STORE-REFRESH':['FIELD_UPDATE后目录、详情、管网覆盖面积和总览同时重算。','派工后工单ASSIGNED与Alarm处理态原子变化；失败两者都不变。','最终水量在总览、运行详情与报表一致，PROVISIONAL不混入FINAL总量。','过滤计数、卡片和分页使用同一实体全集，排序分页不改变total。'],
      'BROWSER-ROUTER-RETURN':['返回恢复查询、筛选、页码、选中实体和滚动。','缺少fieldId或runId时展示确定错误及back_fallback。','脏表单切换菜单需确认，取消后保持全部输入。'],
      'BROWSER-FAILURE-RECOVERY':['VERSION_CONFLICT保留Draft，禁止覆盖他人版本。','写入事务任一失败无部分实体；重复clientRequestId只产生一条命令。','数据读取失败保留上次成功结果，过期响应不覆盖新查询。'],
      'BROWSER-COMMAND-FEEDBACK':['START请求入队只显示STARTING/PENDING，ACK只显示ACKNOWLEDGED。','收到阀门和泵全部确认后RUNNING；单个设备确认不足以成功。','反馈超时置UNKNOWN，迟到反馈幂等对账；停止请求不删除已交付水量。','模拟生产能力未验证、LOCAL或离线时控制禁用且展示具体阻断对象。'],
      'BROWSER-WATER-ACCOUNTING':['西泵单次FINAL账本385.7m³，面积52.4亩，亩均7.360687m³/亩，显示7.36。','基准462.0m³的同日可比窗口节水率16.515151%，显示16.52%；缺基准显示不可计算。','共享总表同时供水按批准流量与时长分摊，分区和等于总表有效增量。','原始读数缺失、表复位或时钟异常不得直接当成0或负用水。'],
      'BROWSER-CONSOLE-RESOURCE':['所有页面无未捕获异常、资源404和泄露密钥。','每页进入退出后无重复订阅、计时器、摄像头轨道或未释放URL。'],
      'BROWSER-MIGRATED-INTERACTIONS':['逐条执行interaction_migration_registry并保存interaction_id覆盖记录。','migrated_count等于完整组件数加20个页面进入，不把声明型组件组计两次。','未实际执行的Interaction不得凭静态生成结果标记浏览器通过。']}
    for ident,items in cases.items():
        sn=node(suites,'suite',id=ident)
        for text in items:node(sn,'assertion',text)
    schema(bc,'screen_result_schema')
    node(bc,'browser_gate',f'只有20个页面实际打开、{len(OVERLAYS)}个弹层逐项验证、全部Branch覆盖、所有写入与失败恢复满足契约、Store跨页一致、全部Interaction实际执行且无控制台错误时才允许PASS。文档静态检查通过不等于浏览器验收通过。任一失败记录screen_id、test_id、fixture_id、预期、实际、截图和trace，完成余下测试后总门禁FAIL。')

def build_interaction_sections():
    ir=node(ROOT,'interaction_requirements')
    rules(ir,'interaction_principles',[
        '所有可操作元素通过完整组件契约触发唯一Action、Query或Branch，不保留无响应按钮。',
        '以任务为中心组织拓扑、曲线、时间轴、泳道和表单，避免把不同页面都做成相同统计卡加表格。',
        '用户可以识别当前操作对象、权限范围、设备模式、数据时间与真实反馈阶段。',
        'Draft与正式数据视觉区分，取消表单不写实体，确认失败保留输入并定位具体错误。',
        '动作禁用给出业务原因，例如LOCAL模式、过期读数、资源占用或未签核能力，不只降低透明度。',
        '危险操作由明确对象与后果的居中确认弹窗承接，取消无副作用。',
        '键盘与鼠标均可操作，焦点可见，状态不只用颜色区分。',
        '页面主内容区不设置描述性顶部段落，左上角不出现说明性副标题。'
    ],item='principle')
    states=node(ir,'global_page_states')
    for code,name,text in [('LOADING','读取中','保留查询与旧结果，骨架只遮挡待更新区域。'),('READY','可操作','数据有效且具备相应权限。'),('EMPTY','无记录','显示业务空状态与已定义清除筛选入口。'),('ERROR','读取失败','保留旧数据和条件，显示本页RETRY-LOAD。'),('FORBIDDEN','无权限','隐藏越权数据，返回已授权来源。'),('OFFLINE','连接中断','标明最后数据时间，禁用依赖在线能力的控制。'),('STALE','数据过期','显示过期时长，不参与自动触发。'),('SUBMITTING','提交中','锁定提交、重复Enter和关闭。'),('UNKNOWN','现场结果待确认','保留指令与关联运行，允许查询反馈，禁止宣告已完成。')]:node(states,'state',text,code=code,name=name)
    cc=node(ir,'common_components')
    for name,text in [('分组导航','复用WEB-SHELL.NAV组件，窄屏居中菜单承载。'),('带时间的读数卡','数值、单位、深度、observedAt和质量同时显示。'),('分页目录','query、filters、sort、page、pageSize与total同源。'),('实体关联行','事件携带明确entityId，打开确定详情页。'),('阈值规则表单','字段依触发模式校验，隐藏无关值不参与计算。'),('步骤编排','使用稳定stepDraftId，排序只改变order。'),('指令时间线','PENDING、SENT、ACKNOWLEDGED、CONFIRMED、UNKNOWN逐阶段显示。'),('居中确认','提供对象、后果、确认、取消、校验和提交锁。'),('扫码弹窗','可解码载荷与实体绑定，支持摄像头、扫码枪和手输。'),('导出任务区','区分任务创建、处理中、可下载、失败与到期。')]:node(cc,'component',text,name=name)
    matrix=node(ir,'component_behavior_matrix')
    behavior=[('分组业务导航','按13个入口实际生成','点击先验角色与Draft，再命中确定导航Branch。','禁用时不切页并显示无权或提交中原因。','无可见子菜单时隐藏该组。','加载失败保持原页面。'),
        ('田块卡片','SELECT-FIELDS过滤后分页','携带fieldId进入FIELD-DETAIL。','越权卡片不展示。','显示无田块及新增入口。','对象不存在刷新目录。'),
        ('管网拓扑节点','按PipeNode树生成','选中nodeId，同页参数区读取关联分区。','循环或越权节点阻断。','无节点显示尚未同步现场管网，可重试加载。','关系读取失败保留已知树。'),
        ('墒情曲线','按Point深度分组','游标通过readingId关联原始读数行。','缺测断点不提供伪造数值。','保留坐标轴并说明未采集。','读取失败保留区间。'),
        ('策略矩阵操作','按Strategy生成','启用停用经BRANCH-STRATEGY-TOGGLE专用确认。','AUTO签核不足时不能启用。','保留作物阶段过滤。','旧策略不变且保留输入。'),
        ('轮灌步骤','按Draft稳定ID生成','添加、移除、排序只改Draft并使资源检查过期。','首尾移动和重复分区按实际条件禁用。','至少添加一步后才能保存。','资源冲突保留全部编排。'),
        ('运行控制栏','每个RUN-DETAIL一组','暂停恢复按状态分支，停止独立确认。','LOCAL、无接口和未知能力逐项说明。','无runId显示参数错误。','发送后未知结果进入UNKNOWN而非假回滚。'),
        ('告警处理行','按Alarm分页生成','确认、派工和关闭分别调用独立Action。','未恢复或未验收不能关闭。','零告警显示正常监测状态。','失败保留处理说明与原告警。'),
        ('维护工单卡','按WorkOrder泳道生成','接单、结果、验收、退回形成独立状态转移。','非本人不能提交现场结果。','空泳道显示无待处理工单。','失败留在原泳道并保留说明。'),
        ('用水基准弹窗','每个田块种植季至多一个活动基准','确认保存来源、面积、体积和可比窗口。','基准<=0或窗口不可比禁止计算节水率。','无基准显示不可计算。','原报表和基准不部分改变。')]
    for name,count,click,disabled,empty,error in behavior:
        c=node(matrix,'component',name=name,count=count)
        for tag,text in [('click_behavior',click),('disabled_behavior',disabled),('empty_behavior',empty),('error_behavior',error)]:node(c,tag,text)
    wl=node(ir,'web_layout_and_visual_requirements')
    rules(wl,'viewport_and_responsive',[
        '目标为桌面Web与田间横竖屏平板，基准1366x864，验证1024x768与768x1024；不机械沿用模板视口。',
        '宽屏显示固定分组侧栏；窄屏导航居中弹窗，业务表格允许自身横向滚动，页面整体不可横向溢出。',
        '关键运行控制、告警确认和表单提交保持可达，触控目标至少44px。',
        '居中弹窗最大宽度min(760px,视口减32px)，内容超高在弹窗内部滚动，确认取消始终可见。',
        '不得实际展示右侧抽屉，不在页面顶部放描述段落或左上角说明性副标题。'
    ])
    vd=node(wl,'visual_design_system',name='Field Irrigation Accessible Web System')
    rules(vd,'style_principles',['田块态势、土层曲线、轮灌时间轴和执行反馈使用各自适配的主表面。','农业绿色用于选中和正常状态，故障与警示提供文字和图标，不只靠颜色。','数据字号、单位和更新时间有清晰层级，不能将UNKNOWN伪装为成功绿色。','不增加未登记可点击装饰卡片、帮助按钮或随机更多菜单。'])
    rules(vd,'color_tokens',['主色#166534，正文#17231C，背景#F5F7F2，边框#D8E0D6。','告警#B42318，警示#9A6700，信息#175CD3，过期#667085；文字对比至少4.5:1。','禁用颜色配合aria-disabled和具体原因，实时读数用数据质量图标标识。'])
    rules(vd,'component_style',['表格行高至少44px，数值右对齐并保留单位；分页total由Selector提供。','所有弹窗居中、焦点圈定、关闭回触发器，运行停止按钮在操作区独立呈现。','表单字段错误就近显示，提交失败可聚焦首错；Loading不改变按钮宽度。'])
    patterns=node(wl,'page_layout_patterns')
    node(patterns,'rule','每个页面按照manifest功能区顺序落实布局，同布局签名不超过3页；本系统20页采用20个任务布局标识，不以仅换标题实现差异。')
    for s in SCREENS:node(patterns,'pattern',s['primary_interaction_surface']+'；顺序='+s['ordered_functional_regions']+'；'+s['composition_difference'],code=s['layout_type'],screen_id=s['screen_id'])

MODULE_REQS={
 'M01':[
  ('SITUATION','总览以授权田块、活动运行和未关闭告警为全集，不显示越权对象。'),('FRESHNESS','每张读数卡显示采集时间和有效性，离线设备不计入在线分子。'),('DRILL','运行、告警、用水、离线卡分别进入RUN-LIST、ALARM-LIST、WATER-REPORT、DEVICE-LIST并携带筛选。'),('TODAY','当日水量仅按FINAL账本自然日边界计算，运行中暂估另列。')],
 'M02':[
  ('FIELD_FACT','田块编码唯一，面积大于0，负责人为启用账号。'),('COVERAGE','田块面积更新不得低于启用分区面积之和。'),('SEASON','每田块同一时间仅一个活动种植季，旧季历史不覆盖。'),('QR','田块二维码从QrCode.payload真实编码，解码后必须指向同一fieldId。'),('PROFILE','详情关联的分区、监测和历史用水均通过稳定fieldId读取。')],
 'M03':[
  ('TOPOLOGY','水源至阀门拓扑无环，父节点与分区同农场。'),('ZONE_LINK','分区绑定田块、阀门、土层点和计量来源，阀门不能被互斥运行分区重复控制。'),('CAPACITY','共享泵站容量和并发上限参与计划检查，运行占用时禁止修改。'),('DRIP','埋深、间距与设计流量保留现场值和单位。'),('ALLOCATION','共享累计表的分摊需有批准规则，不能将全量记给每个分区。')],
 'M04':[
  ('ADAPTER','未知生产协议保留UNVERIFIED，只有适配器验证后才开放相应能力。'),('POINT','点位单位、地址、量程、缩放和有效期必须完整，旧原始读数不可重写。'),('QUALITY','曲线缺测为断点，过期读数不参与自动触发。'),('CALIBRATION','校准原子保存Point偏移与Calibration证据，活动控制引用时禁止改系数。'),('SCANNER','摄像头需主动授权，所有输入经过QUERY_QR_RESOLVE及明确类型分支。')],
 'M05':[
  ('TRIGGER','定时、定量、墒情三类触发只使用各自有效参数，MOISTURE必填%VWC阈值。'),('STAGE','策略适用作物与阶段必须匹配所选分区活动种植季。'),('AUTO_GATE','AUTO须设备反馈、保护能力与联动签核全部满足，否则禁止保存或启用。'),('SIMULATION','试算只产生UI建议，不自动创建、发布计划或发送设备指令。'),('VERSION','修改策略版本不追改既有Plan.strategySnapshot。')],
 'M06':[
  ('STEPS','计划至少一个步骤，分区不重复，水量时长正值，步骤主键不随order变化。'),('CHECK','保存和发布均由服务端重算泵站容量、并发、时间和状态冲突。'),('PUBLISH','发布原子生成QUEUED运行，不自动声称已启动现场。'),('CANCEL','仅未执行计划可取消，已启动必须进入运行详情通过停止Action。'),('DRAFT','添加、删除、排序和重置全部在Draft中完成，保存失败保持完整编排。')],
 'M07':[
  ('OUTBOX','控制事务只原子入队与更新过渡态，硬件发送在提交后执行。'),('CONFIRM','ACK不是动作完成，必须核对全部设备反馈才改变最终运行态。'),('TRANSITION','暂停、恢复与停止分别使用自身前置状态和反馈条件。'),('UNKNOWN','控制超时进入UNKNOWN并对账，禁止把未知当作成功或直接撤销现场动作。'),('ACCOUNTING','停止与完成保留已灌水量，最终结算通过FINALIZE_WATER。')],
 'M08':[
  ('ACK','知悉告警只记录确认人时间，不修改恢复态。'),('DISPATCH','派工在一事务创建工单并更新告警处理态，重复派工被阻断。'),('OWNERSHIP','只有本人TECHNICIAN可接单和提交现场结果。'),('REVIEW','结果提交与管理验收分离，可退回原责任人重新处理。'),('CLOSE','告警已恢复且关联工单已完成后才允许独立关闭。')],
 'M09':[
  ('LEDGER','总览、运行详情与报表读取同一有效WaterLedger集合。'),('METHOD','实测、分摊、估算分列展示，修订不重复累计。'),('DENOMINATOR','亩均用水按区间覆盖田块面积去重，不按账本行重复加面积。'),('BASELINE','节水率必须明确比较基准、作物和窗口，缺失或为零显示不可计算。'),('EXPORT','导出由服务端任务生成，区分QUEUED、READY、EXPIRED与FAILED，下载须校验权限及checksum。')],
 'M10':[
  ('AUTH','认证使用服务端账号角色，不提供自主提权角色选择。'),('SCOPE','账号权限与田块范围共同校验，停用或变更撤销受影响旧令牌。'),('LAST_ADMIN','不得停用本人或移除最后启用管理员。'),('POLICY','时限参数大小关系必须校验，活动指令使用原快照。'),('AUDIT','审计只读，以correlationId关联指令阶段，禁止前端修改删除。')]
}
MODULE_ENTITIES={
 'M01':['Farm'],'M02':['Field','CropSeason','QrCode'],'M03':['PipeNode','IrrigationZone'],
 'M04':['Device','Point','TelemetryReading','Calibration'],'M05':['Strategy'],'M06':['Plan','PlanStep'],
 'M07':['IrrigationRun','RunStep','CommandOutbox','CommandEvent'],'M08':['Alarm','WorkOrder'],
 'M09':['WaterLedger','WaterBaseline','ExportJob'],'M10':['Session','User','SystemPolicy','AuditLog']}
STATE_MAP={
 'M01':[('CURRENT','当日态势'),('STALE','部分数据过期')],
 'M02':[('ENABLED','启用田块或种植季'),('DISABLED','归档或停用')],
 'M03':[('AVAILABLE','可分配供水'),('OCCUPIED','正在被运行占用')],
 'M04':[('UNVERIFIED','能力未核验'),('VERIFIED','能力已核验'),('OFFLINE','连接离线')],
 'M05':[('ENABLED','启用策略'),('DISABLED','停用策略')],
 'M06':[('DRAFT','草稿'),('PUBLISHED','已发布'),('EXECUTING','执行中'),('COMPLETED','已完成'),('CANCELLED','已取消'),('FAILED','失败')],
 'M07':[(x,x) for x in ENUMS['RunStatus'].split('|')],
 'M08':[('OPEN','新告警'),('ACKNOWLEDGED','已知悉'),('ASSIGNED','已派工'),('CLOSED','已关闭'),('IN_PROGRESS','维护中'),('PENDING_ACCEPTANCE','待验收'),('RETURNED','退回处理')],
 'M09':[('FINAL','已核算'),('PROVISIONAL','暂估待结算'),('INVALID','来源无效')],
 'M10':[('ENABLED','账号启用'),('DISABLED','账号停用')]}

def build_modules():
    cm=node(ROOT,'core_modules',expected_module_count=len(MODS))
    for mid,name,sids,obj in MODS:
        m=node(cm,'module',id=mid)
        node(m,'module_name',name)
        node(m,'sidebar_menu','|'.join(S[s]['page_name'] for s in sids if S[s]['parent_screen_id'] in ('OVERVIEW','NONE','ALARM-LIST') and s!='AUTH-LOGIN'))
        node(m,'module_objective',obj)
        scope=node(m,'business_scope')
        for key,text in MODULE_REQS[mid]:node(scope,'item',text)
        wf=node(m,'workflow_states')
        for code,label in STATE_MAP[mid]:node(wf,'state',label,code=code)
        pg=node(m,'page_group_components')
        for sid in sids:
            p=node(pg,'page',name=S[sid]['page_name'],screen_id=sid)
            for region in S[sid]['ordered_functional_regions'].split('|'):node(p,'component',region)
            node(p,'component','可操作组件以screen_component_contracts中本screen_id的完整component为准；应用壳层继承web_shell_component_contracts。')
        fr=node(m,'functional_requirements')
        for key,text in MODULE_REQS[mid]:node(fr,'requirement',text,id=mid+'-F-'+key,priority='高')
        sd=node(m,'state_definitions')
        for code,label in STATE_MAP[mid]:node(sd,'state',label+'；状态由对应实体或Selector读取，不维护独立页面业务状态。',code=code,name=label)
        md=node(m,'mock_data',source='browser_acceptance_contract.fixed_test_fixtures',clock=NOW,environment='ISOLATED_FIXTURE')
        for ename in MODULE_ENTITIES[mid]:
            for record in SEEDS[ename]:
                rn=node(md,'record',entity=ename,fixture_id='FIXTURE.'+record[ENTITIES[ename]['id_field']])
                for key,value in record.items():node(rn,key,json.dumps(value,ensure_ascii=False,separators=(',',':')))
        ac=node(m,'acceptance_criteria')
        for key,text in MODULE_REQS[mid]:node(ac,'criterion',text+' 验证成功路径、阻断原因与失败后原状态保持。',requirement_ref=mid+'-F-'+key)

def build_tail():
    cp=node(ROOT,'cross_module_processes')
    processes=[
      ('田块种植与管网关联',['FIELD-LIST新增田块进入FIELD-EDIT(mode=create)。','FIELD_CREATE成功后FIELD-DETAIL读取同一fieldId。','DIALOG-SEASON通过SEASON_SAVE维护活动种植季。','NETWORK通过ZONE_SAVE关联田块、阀门、监测点与计量点。','SELECT-FIELDS与SELECT-NETWORK共同验证面积覆盖及关系。']),
      ('设备接入与监测',['DEVICE-LIST登记厂家型号、适配器和网关。','DEVICE_SAVE后保持UNVERIFIED。','DEVICE-DETAIL通过POINT_SAVE维护点位量纲和有效期。','DEVICE_VERIFY只做已声明验证；生产控制能力需现场签核。','INGEST_TELEMETRY归一化入Store，MONITOR按深度和质量显示。']),
      ('墒情建议到计划发布',['STRATEGY-EDIT保存有效策略和版本。','DIALOG-SIMULATION执行QUERY_STRATEGY_SIMULATE。','可执行建议进入PLAN-EDIT，仅初始化Draft。','添加分区、调整目标量和轮灌顺序，QUERY_PLAN_CONFLICTS检查资源。','PLAN_CREATE保存DRAFT；PLAN_PUBLISH再次校验并创建QUEUED运行。']),
      ('启动到反馈确认',['RUN-LIST打开DIALOG-RUN-START。','RUN_START事务创建CommandOutbox和STARTING状态。','事务提交后outbox执行器按签核序列发送。','RECONCILE_COMMAND记录SENT及ACKNOWLEDGED，但运行仍处过渡态。','全部设备动作反馈确认后置RUNNING。','RUN-DETAIL展示流量压力、步骤与命令时间线。']),
      ('暂停恢复与停止',['RUN-DETAIL按run.status进入暂停或恢复专用确认。','RUN_PAUSE或RUN_RESUME入队后显示PAUSING或RESUMING。','现场确认后转换PAUSED或RUNNING，剩余目标量不重置。','RUN_STOP可抢占未决非STOP命令但不删除历史指令。','停机反馈确认STOPPED；FINALIZE_WATER保存最终水量。']),
      ('现场反馈超时与迟到对账',['命令超过动作确认时限仍缺完整反馈。','RECONCILE_COMMAND将运行置UNKNOWN并生成CONTROL_TIMEOUT告警。','UI保留指令号及已知状态，提示现场核实。','迟到事件按gatewayEventId去重并重新对账。','对账成功更新运行与告警恢复态，告警仍需处理关闭。']),
      ('告警派工与验收',['ALARM-LIST通过ALARM_ACK记录知悉。','WORKORDER_CREATE同时创建工单并更新告警处理态。','TECHNICIAN本人WORKORDER_ACCEPT进入IN_PROGRESS。','WORKORDER_SUBMIT保存排查结果并待验收。','MANAGER通过WORKORDER_APPROVE验收或WORKORDER_RETURN退回。','recovery=RECOVERED且工单完成后ALARM_CLOSE结案。']),
      ('水量结算与节水核算',['停止或完成步骤后校验累计表起止值、复位与溢出。','FINALIZE_WATER原子生成WaterLedger并更新运行。','共享总表按批准规则分摊，保留来源读数和方法。','SELECT-WATER剔除被修订记录并汇总同一有效全集。','BASELINE_SAVE核准可比窗口后计算节水率。','EXPORT_CREATE生成固定过滤快照任务，READY后校验checksum下载。']),
      ('资产扫码追溯',['DEVICE-DETAIL打开SCANNER-ASSET，手输和扫码枪无需摄像头权限。','用户主动开启摄像头后才请求媒体资源。','QUERY_QR_RESOLVE精确校验域、版本、checksum与ACTIVE实体。','BRANCH-SCAN-RESULT按device或field进入唯一详情。','关闭Scanner及页面卸载停止轨道、帧循环和worker。']),
      ('权限变更与审计',['ADMIN在SETTINGS通过USER_SAVE或USER_DISABLE调整账号权限。','服务端校验最后管理员和田块范围，变更后撤销受影响令牌。','任何后续Action重新鉴权，前端隐藏入口不代替服务端校验。','AuditLog保留actor、对象、版本与correlationId。','AUDIT只读关联CommandOutbox和CommandEvent还原完整指令链路。'])]
    for name,steps in processes:
        p=node(cp,'process',name=name)
        for i,t in enumerate(steps,1):node(p,'step',t,order=i)
    ds=node(ROOT,'data_standards_and_integration')
    rules(ds,'standards',[
        '主键使用类型前缀-地区-稳定随机后缀，跨页按ID引用，禁止行号或连续尾号充当业务编号。',
        '时间采用带时区ISO-8601；界面展示Asia/Shanghai；采集时间与入库时间分别保存。',
        '面积亩、体积m³、流量m³/h、压力MPa、含水率%VWC和深度cm，接口值与单位分离。',
        '所有实体字段与枚举以data_model_contract为准，读数质量与数据新鲜度分开。',
        '设备协议不按名称臆测；实际寄存器、Topic、API、心跳和应答格式通过厂家资料映射。',
        '固定测试夹具是数据合同示例，不是现场参数建议；生产导入须验证关联与单位。'
    ],item='standard')
    ints=node(ds,'interfaces')
    for name,text in [
        ('认证与授权','POST /api/session、DELETE /api/session；服务端账号角色和范围为准，密码不写日志。'),
        ('规范化业务读取','GET /api/fields、/api/zones、/api/devices、/api/plans、/api/runs；支持filters、stableSort、page及pageSize，返回total与revision。'),
        ('业务Action','POST /api/actions/{action_id}；包含clientRequestId、expectedVersion和明确input；返回权威实体delta、affected_screens和correlationId。'),
        ('遥测接入','服务端适配器将厂家数据转换为INGEST_TELEMETRY；签名网关身份、messageId、pointId、时间、值和quality必填。'),
        ('控制发送与反馈','outbox worker发送签核序列，反馈交RECONCILE_COMMAND；具体通信协议待现场资料核实，界面不直连任意设备地址。'),
        ('状态订阅','GET /api/events提供经授权SSE；断开后以revision重读，按eventId去重，不重复提交控制。'),
        ('二维码解析','QUERY_QR_RESOLVE按已登记payload读取唯一实体；checksum仅用于完整性检测，所有访问仍需登录鉴权。'),
        ('导出任务','POST Action EXPORT_CREATE，GET /api/exports/{exportId}及/content；鉴权、到期与checksum校验后下载。')]:node(ints,'interface',text,name=name)
    rules(ROOT,'security_compliance_requirements',[
        '账号角色与田块范围双重校验，读取与写入都由服务端验证；越权请求返回FORBIDDEN且不得暴露实体详情。',
        '控制指令使用认证会话、幂等键、版本与审计；设备接入凭据保存在服务端密钥设施，不写浏览器持久化或XML种子。',
        '生产控制须现场反馈、本地保护和联动签核，云端Web不能取代控制柜保护；模拟适配器不能连接真实执行器。',
        '账号停用和授权变化撤销旧令牌；当前用户与最后启用ADMIN保护由服务端校验。',
        '审计与原始计量证据只追加不可直接删除；导出按角色脱敏，下载URL有时效且再次鉴权。',
        '文本、扫码载荷、备注和导出内容按不可信输入处理，输出编码防止脚本执行；文件按白名单列和内容类型处理。'
    ],item='requirement')
    nf=node(ROOT,'non_functional_requirements')
    rules(nf,'performance',[
        '隔离验收环境在1000田块、3000设备、10000运行记录下，普通列表Query的p95目标<=2秒，分页默认10条。',
        '监测查询默认最近24小时，原始读数按服务端分页；曲线降采样不得改变明细total。',
        '控制请求受理反馈目标p95<=1秒；现场动作完成时限由协议和SystemPolicy决定，不能用页面Loading时长替代。',
        '搜索防抖300ms，旧请求取消或按requestId丢弃；SSE事件去重合并，避免每事件重载整个应用。',
        '报表导出异步执行并显示任务状态，大文件不阻塞运行控制页面。'
    ],item='item')
    rules(nf,'availability',[
        '刷新或返回后未决指令从服务端outbox恢复，不依赖页面内存。',
        '数据库事务失败整体回滚；消息重放幂等；硬件未知结果保留UNKNOWN并告警。',
        '断网时读取保留上次成功时间与质量，写操作明确失败或待对账，不伪造已执行。',
        '生产网关断网后的本地行为按已签核控制器能力执行，未核实能力前不能启用AUTO。'
    ],item='item')
    rules(nf,'usability',[
        '控件语义、键盘操作、焦点可见与弹窗焦点圈定完整，触控区域>=44px。',
        '页面不出现主内容区顶部描述或说明性副标题，数据说明放在对应指标或字段帮助区域且不新增未契约化按钮。',
        '运行停止入口清晰独立，提交前展示对象与后果，状态未知不可显示成功色。',
        '所有表单确认、取消、重置和失败后的状态可验证，输入不因读取失败被无声清空。',
        '页面不存在右侧抽屉；需要明细、编辑或确认使用居中弹窗及既有详情页。',
        '编号稳定不依赖排序，时间按业务事实分布，所有跨页实体名称、面积和状态一致。'
    ],item='item')
    rules(ROOT,'acceptance_summary',[
        '第一版20个页面、9个业务模块加1个系统配套模块，目录、详情和编辑层级清晰。',
        '所有组件完整定义行为字段，全部引用闭合且Interaction数量动态计算。',
        '从田块和管网建档到监测、策略、计划、运行、维护与水量核算形成闭环。',
        '真实控制必须区分受理、通信应答与现场确认，支持超时未知和迟到反馈对账。',
        '正式业务写入统一Action与原子事务，失败不产生部分记录；物理动作按实际反馈追溯。',
        '所有统计、列表和分页同源，基准缺失不虚构节水率。',
        '静态XML验证、组件行为重复审查及真实浏览器验收分别记录，不混淆完成状态。'
    ],item='criterion')
    rules(ROOT,'interactive_ui_acceptance_criteria',[
        '每个Screen真实打开并执行其page_lifecycle读取与卸载清理。',
        '按钮、字段、Tab、卡片、列表行、拓扑、曲线、分页和弹层操作均能定位到component_id。',
        '每个RESOLVE_BRANCH都有可解析branch_set_id，所有命中和otherwise均可测试。',
        '全部Overlay由登记触发器打开，确认Action和成功失败结果闭合。',
        '表单成功、字段错误、版本冲突、取消、重置及关闭状态都有可观察结果。',
        '写入成功后affected_screens使用最新Store派生，返回恢复上下文。',
        '扫码图像可实际解码，摄像头关闭资源释放，未知或越权编码不跳转。',
        '现场控制无法验证时禁用并说明，不依赖成功Toast证明设备完成。',
        '差异化页面布局、居中弹窗和禁止说明性副标题规则满足视觉验收。'
    ],item='criterion')
    refs=node(ROOT,'reference_basis')
    for text in [
        '用户本轮XML生成规则第1至22条，包含20页上限、结构保留、组件差异化和禁止右侧抽屉。',
        '用户已选择真实设备接入版B，现场设备已经安装；厂家资料与通信协议尚未提供。',
        'docs/superpowers/specs/2026-10-25-irrigation-design.md：已确认九个业务模块及硬件依赖。',
        '用户提供的V2.1 XML模板：作为章节、Schema、Registry与Contract结构来源，原行业实体和业务示例全部重建。',
        'docs/superpowers路径当前仅有上述功能范围文档，没有额外可读取的技术栈或编码约束；本文以该范围作为当前开发约束。',
        '生产接入实施依据：现场设备清单、厂家协议及点表、管网关系、控制柜模式和联动保护签核；未核实资料不被当成已具备能力。'
    ]:node(refs,'reference',text)

def validate_document():
    errors=[]; checks=[]
    def check(condition,label,detail=''):
        checks.append(dict(name=label,status='PASS' if condition else 'FAIL',detail=detail))
        if not condition:errors.append(label+': '+detail)
    def unique(items,key,label):
        values=[x.get(key) for x in items]
        dup=[k for k,v in Counter(values).items() if v>1 or not k]
        check(not dup,label,','.join(str(x) for x in dup))
        return set(values)
    screens=ROOT.findall('.//screen_manifest/screen')
    sids=unique(screens,'screen_id','Screen ID唯一')
    unique(screens,'route','Route唯一')
    unique(screens,'html_file','HTML文件名唯一')
    check(len(screens)<=20,'页面不超过20个',str(len(screens)))
    check(int(ROOT.find('.//screen_manifest').get('expected_screen_count'))==len(screens),'页面计数一致')
    for a in SCREENS:
        required={'screen_id','page_name','html_file','route','parent_screen_id','role','back_fallback','owner_sidebar_menu',
            'layout_type','responsive_mode','task_family','task_family_origin','task_family_rationale','layout_type_origin','layout_type_rationale',
            'primary_interaction_surface','ordered_functional_regions','navigation_pattern','action_placement','secondary_surface','detail_opening_mode','composition_difference'}
        check(all(a.get(k) for k in required),'Manifest完整:'+a['screen_id'])
    comps=ROOT.findall('.//web_shell_component_contracts/component')+ROOT.findall('.//screen_component_contracts/screen_contract/component')
    cids=unique(comps,'component_id','Component ID唯一')
    overlays=ROOT.findall('.//overlay_registry/overlay');oids=unique(overlays,'overlay_id','Overlay ID唯一')
    branches_=ROOT.findall('.//structured_condition_branches/branch_set');bids=unique(branches_,'branch_set_id','Branch Set ID唯一')
    actionnodes=ROOT.findall('.//action_registry/action')
    localnodes=ROOT.findall('.//local_action_registry/local_action')
    querynodes=ROOT.findall('.//query_registry/query')
    dispatchnodes=ROOT.findall('.//action_dispatchers/dispatcher')
    aids=unique(actionnodes+localnodes+querynodes+dispatchnodes,'action_id','全部Action命名空间唯一')
    txnodes=ROOT.findall('.//transaction_rules/transaction');tids=unique(txnodes,'transaction_id','Transaction ID唯一')
    selnodes=ROOT.findall('.//selector_registry/selector');selids=unique(selnodes,'selector_id','Selector ID唯一')
    entities=ROOT.findall('.//entities/entity');enames=unique(entities,'name','Entity名称唯一')
    qids={n.get('action_id') for n in querynodes}
    required_comp={'component_id','match_mode','match','element_kind','event','action_type','preconditions','dialog_id','target_screen_id','route_params',
        'immediate_feedback','data_consequence','success_consequence','failure_consequence','disabled_rule','return_rule','action_id'}
    check(all(all(c.get(k) for k in required_comp) for c in comps),'全部组件行为字段完整')
    for c in comps:
        cid=c.get('component_id')
        check(c.get('target_screen_id') in sids|{'STAY','NONE','BY_BRANCH'},'组件目标可解析:'+cid)
        check(c.get('dialog_id') in oids|{'NONE','BY_BRANCH'},'组件弹层可解析:'+cid)
        check(c.get('action_id') in aids|{'NONE'},'组件Action可解析:'+cid)
        b=c.get('branch_set_id')
        check((b in bids and c.get('dialog_id')=='BY_BRANCH' and c.get('target_screen_id')=='BY_BRANCH') if c.get('action_type')=='RESOLVE_BRANCH' else not b,'组件分支规则:'+cid)
        if c.get('scope')=='OVERLAY':check(c.get('overlay_owner_id') in oids,'弹层组件归属:'+cid)
    for b in branches_:
        check(b.get('source_component_id') in cids,'分支来源可解析:'+b.get('branch_set_id'))
        check(b.get('otherwise')=='BLOCK_AND_REPORT','无命中阻断:'+b.get('branch_set_id'))
        for path in b:
            check(path.get('action_id') in aids,'分支Action可解析:'+path.get('action_id'))
            check(path.get('dialog_id') in oids|{'NONE'},'分支Overlay可解析:'+path.get('action_id'))
            check(path.get('target_screen_id') in sids|{'STAY'},'分支目标可解析:'+path.get('action_id'))
            check(path.get('transaction_id') in tids|{'NONE'},'分支事务可解析:'+path.get('action_id'))
    for n in actionnodes:
        check(n.get('transaction_id') in tids|{'NONE'},'Action事务可解析:'+n.get('action_id'))
        check(set(n.get('writes').split(','))<=enames,'Action写入实体存在:'+n.get('action_id'))
        check(set(n.get('affected_screens').split(','))<=sids,'Action刷新页面存在:'+n.get('action_id'))
        if len(n.get('writes').split(','))>1:check(n.get('transaction_id')!='NONE','多实体写入原子事务:'+n.get('action_id'))
    for n in dispatchnodes:
        check(n.get('branch_set_id') in bids and set(n.get('dispatches_to').split('|'))<=aids,'Dispatcher可解析:'+n.get('action_id'))
        check(n.get('pre_query_id') in qids|{'NONE'},'Dispatcher前置Query可解析:'+n.get('action_id'))
    overlay_required=set(SOURCE.find('.//overlay_registry/overlay').attrib)
    cmap={c.get('component_id'):c for c in comps}
    for o in overlays:
        oid=o.get('overlay_id');triggers=o.get('trigger_component_ids').split('|')
        check(overlay_required<=set(o.attrib) and all(o.get(k) for k in overlay_required),'Overlay完整Schema:'+oid)
        check(set(triggers)<=cids and len(triggers)>0,'Overlay触发器可解析:'+oid)
        check(o.get('confirm_action_id') in aids|{'NONE'},'Overlay确认Action可解析:'+oid)
        check(o.get('presentation')=='centered_modal' and o.get('overlay_type')!='DRAWER','居中弹层:'+oid)
        owners=set(o.get('owner_screen_id').split('|'))
        for cid in triggers:
            check('GLOBAL' in owners or cid.rsplit('.',1)[0] in owners,'Overlay来源归属:'+oid+':'+cid)
            direct=cmap[cid].get('dialog_id')==oid
            via=any(b.get('source_component_id')==cid and any(x.get('dialog_id')==oid for x in b) for b in branches_)
            check(direct or via,'Overlay触发引用闭合:'+oid+':'+cid)
        confirms=[c for c in comps if c.get('overlay_owner_id')==oid and c.get('component_id').endswith('-CONFIRM')]
        if o.get('confirm_action_id')!='NONE':
            check(bool(confirms) and all(c.get('action_id')==o.get('confirm_action_id') for c in confirms),'Overlay确认控件一致:'+oid)
        check(any(c.get('overlay_owner_id')==oid and c.get('component_id').endswith('-CANCEL') for c in comps),'Overlay取消控件存在:'+oid)
    for n in selnodes:check(set(n.get('derives_from').split(','))<=enames,'Selector实体存在:'+n.get('selector_id'))
    for n in querynodes:
        check(set(n.get('reads').split(','))<=enames,'Query实体存在:'+n.get('action_id'))
        check(set(n.get('selectors').split(','))<=selids,'Query Selector存在:'+n.get('action_id'))
    life=ROOT.findall('.//page_lifecycle_contracts/page_lifecycle')
    check(len(life)==len(sids) and {n.get('screen_id') for n in life}==sids,'生命周期覆盖全部页面')
    for n in life:
        check(n.get('enter_action_id') in qids,'生命周期进入Query:'+n.get('screen_id'))
        check(set(n.get('selectors').split(','))<=selids and all(n.get(k) for k in ['required_params','unmount_cleanup','read_entities']),'生命周期字段完整:'+n.get('screen_id'))
    migrations=ROOT.findall('.//interaction_migration_registry/migration')
    unique(migrations,'interaction_id','Interaction ID唯一')
    check(len(migrations)==len(comps)+len(life)==int(ROOT.find('.//interaction_migration_registry').get('migrated_count')),'Interaction计数与实际组件及页面进入一致',str(len(migrations)))
    for n in migrations:
        for ref in n.get('execution_ref').split('|'):
            kind,value=ref.split(':',1)
            check(value in {'component':cids,'page_lifecycle':sids,'query':qids}[kind],'Interaction引用可解析:'+n.get('interaction_id'))
    check([x.tag for x in ROOT]==[x.tag for x in SOURCE],'顶层章节和顺序保留')
    for tag in ['page_integration_contract','executable_contract_extensions','data_model_contract']:
        a=ROOT.find('.//'+tag);b=SOURCE.find('.//'+tag)
        check([x.tag for x in a]==[x.tag for x in b],'关键Contract子章节与顺序保留:'+tag)
    for tag in ['screen_layout_contract_schema','component_contract_schema','branch_schema','overlay_schema','screen_result_schema']:
        a=ROOT.find('.//'+tag);b=SOURCE.find('.//'+tag)
        source_fields=[x.text for x in b.findall('required_field')]
        target_fields=[x.text for x in a.findall('required_field')]
        check(all(t in target_fields for t in source_fields),'模板Schema必填字段保留:'+tag)
    def structural_inventory(root):
        result={}
        def walk(n,path=''):
            path+='/'+n.tag;result.setdefault(path,set()).update(n.attrib)
            for child in n:walk(child,path)
        walk(root);return result
    source_paths=structural_inventory(SOURCE);target_paths=structural_inventory(ROOT)
    generic_paths={p:attrs for p,attrs in source_paths.items() if '/mock_data/record/' not in p}
    missing_paths=sorted(set(generic_paths)-set(target_paths))
    check(not missing_paths,'模板通用标签路径完整保留',json.dumps(missing_paths))
    missing_attrs=[(p,sorted(attrs-target_paths.get(p,set()))) for p,attrs in generic_paths.items()
        if not p.endswith('/fixture') and attrs-target_paths.get(p,set())]
    check(not missing_attrs,'模板通用结构属性字段完整保留',json.dumps(missing_attrs))
    # Validate primary keys, foreign keys, enum values, required fields and fixture mirror consistency.
    seedids={en:{r[meta['id_field']] for r in SEEDS[en]} for en,meta in ENTITIES.items()}
    for en,meta in ENTITIES.items():
        check(len(seedids[en])==len(SEEDS[en]),'种子主键唯一:'+en)
        fields={f['name']:f for f in meta['fields']}
        check(meta['id_field'] in fields,'实体主键字段存在:'+en)
        for record in SEEDS[en]:
            check(all(f['name'] in record and record[f['name']] is not None for f in fields.values() if f['required']=='true'),'种子必填完整:'+record[meta['id_field']])
            check(set(record)<=set(fields)|{'version','createdAt','updatedAt'},'种子无未定义字段:'+record[meta['id_field']])
            for fname,f in fields.items():
                val=record.get(fname)
                if val is None:continue
                if f.get('enum'):check(val in ENUMS[f['enum']].split('|'),'种子枚举有效:'+en+'.'+fname)
                if f.get('relation'):
                    target,tfield=f['relation'].split('.')
                    check(target in ENTITIES and tfield==ENTITIES[target]['id_field'],'模型关系存在:'+en+'.'+fname)
                    values=val if isinstance(val,list) else [val]
                    check(set(values)<=seedids[target],'种子外键有效:'+en+'.'+fname)
    check(sum(r['areaMu'] for r in SEEDS['Field'])==117.8,'田块总面积口径','117.8亩')
    for f in SEEDS['Field']:
        area=sum(z['areaMu'] for z in SEEDS['IrrigationZone'] if z['fieldId']==f['fieldId'])
        check(abs(area-f['areaMu'])<1e-9,'分区覆盖面积一致:'+f['fieldId'])
    for qr in SEEDS['QrCode']:
        kind='field' if qr['fieldId'] else 'device';eid=qr['fieldId'] or qr['deviceId']
        checksum=hashlib.sha256((kind+':'+eid+':1').encode()).hexdigest()[:12]
        check(qr['checksum']==checksum and qr['payload'].endswith('c='+checksum),'二维码载荷与实体一致:'+qr['qrId'])
    from datetime import datetime
    for en,records in SEEDS.items():
        for record in records:
            if 'createdAt' in record and 'updatedAt' in record:
                check(datetime.fromisoformat(record['createdAt'])<=datetime.fromisoformat(record['updatedAt'])<=datetime.fromisoformat(NOW),'种子元数据时间顺序:'+record[ENTITIES[en]['id_field']])
    check(hashlib.sha256(EXPORT_CONTENT.encode()).hexdigest()==SEEDS['ExportJob'][0]['checksum'],'导出文件夹具校验和一致')
    check(abs(SEEDS['WaterLedger'][0]['volumeM3']-385.7)<1e-9 and round(385.7/52.4,2)==7.36 and round((462-385.7)/462*100,2)==16.52,'示例用水与节水计算正确')
    text=E.tostring(ROOT,encoding='unicode')
    stale=re.findall(r'实验室|样品|危险品|库位|领用|借用|LIMS|ELN|Sample|Borrow|Approval|SMP-',text)
    check(not stale,'无原行业业务残留',str(sorted(set(stale))))
    check(not any(x in text for x in ['省略','同上','其余类似','...','执行对应操作','跳转相关页面','根据情况处理']),'无省略及模糊行为表达')
    check(not any(c.get('action_type')=='OPEN_DRAWER' for c in comps),'无实际抽屉操作')
    # Exact duplicates across unrelated business families are rejected, and normalized similarities are reported.
    keys=['preconditions','immediate_feedback','data_consequence','success_consequence','failure_consequence','disabled_rule','return_rule']
    dup=[]; signatures={}
    for c in comps:
        sig=tuple(c.get(k) for k in keys)
        if sig in signatures:dup.append([signatures[sig],c.get('component_id')])
        else:signatures[sig]=c.get('component_id')
    check(not dup,'组件七项行为无完全重复',json.dumps(dup,ensure_ascii=False))
    # Cross-domain prose comparison strips only IDs, not the business verbs or state consequences.
    from difflib import SequenceMatcher
    normalized=[];suspicious=[]
    reusable={'FIELD_EDIT','QUERY','SUBMIT','CONFIRM_DIALOG','NAVIGATE','OVERLAY_CANCEL','SCANNER_TOOL'}
    for c in comps:
        if c.get('behavior_family') in reusable:continue
        words='|'.join(c.get(k,'') for k in keys)
        words=re.sub(r'\b[A-Z][A-Z0-9_-]{3,}\b','ID',words)
        normalized.append((c.get('component_id'),c.get('behavior_family'),words))
    for i,(cid,family,words) in enumerate(normalized):
        for oid,other,owords in normalized[:i]:
            if cid.split('.')[0]==oid.split('.')[0]:continue
            score=SequenceMatcher(None,words,owords).ratio()
            if score>0.90:suspicious.append(dict(left=oid,right=cid,score=round(score,4)))
    check(not suspicious,'非通用业务组件归一化相似检查',json.dumps(suspicious,ensure_ascii=False))
    check(E.fromstring(E.tostring(ROOT,encoding='utf-8')).tag=='requirements_document','XML可完整解析与标签闭合')
    return checks,errors,dict(screens=len(screens),modules=len(MODS),components=len(comps),interactions=len(migrations),overlays=len(overlays),
        branch_sets=len(branches_),branches=sum(len(b) for b in branches_),entities=len(entities),business_actions=len(actionnodes),local_actions=len(localnodes),dispatchers=len(dispatchnodes),
        transactions=len(txnodes),selectors=len(selnodes),queries=len(querynodes),fixture_records=sum(len(x) for x in SEEDS.values()),behavior_duplicate_pairs=dup,suspicious_similarity_pairs=suspicious)

if __name__=='__main__':
    build_document()
    E.indent(ROOT,space='  ')
    checks,errors,counts=validate_document()
    reportdir=BASE/'reports';reportdir.mkdir(exist_ok=True)
    report={'document':OUTPUT.name,'template_sha256':hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
        'template_elements_parsed':sum(1 for _ in SOURCE.iter()),'counts':counts,'static_validation':'FAIL' if errors else 'PASS',
        'browser_validation':'NOT_EXECUTED_DOCUMENT_ONLY','checks':checks,'errors':errors}
    (reportdir/'irrigation-requirements-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:
        print(json.dumps({'counts':counts,'errors':errors},ensure_ascii=False,indent=2))
        raise SystemExit(1)
    E.ElementTree(ROOT).write(OUTPUT,encoding='utf-8',xml_declaration=True)
    print(json.dumps({'output':str(OUTPUT),'bytes':OUTPUT.stat().st_size,'counts':counts,'checks_passed':len(checks)},ensure_ascii=False,indent=2))
