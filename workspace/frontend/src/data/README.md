# 前端仓储接口

`useIrrigation()`来自`./runtime.js`，是应用唯一运行仓储。请勿从组件访问localStorage或复制另一份实体数据。所有方法均异步，`can/getIndex/subscribe/checkSession`除外。

返回字段：`state={entities,revision,user,publicFarm,ready,error,channel,readOnly}`。未登录时entities为空集合；publicFarm仅公开name/farmId供登录卡显示。已登录entities是当前用户授权后的投影，可只读用于computed；表单必须JSON克隆成Draft。`getIndex()`返回同一修订的`{entities,revision,byId,zonesByField,seasonsByField,pointsByDevice,readingsByPoint,stepsByPlan,stepsByRun,ledgerByRun}`。byId按实体类型映射到Map。

`load()`启动恢复本机会话但不接受历史种子Session。`login(account,password)`验证终端工具生成的摘要，成功写state.user。`logout()`清理本机会话。`checkSession()`同步重验会话并返回是否仍有效；到期timer主动撤销会话，can/getIndex/refresh也会补查，撤销同时清空state.user、授权entities与关系索引。测试可注入clock、schedule(callback,delay)、cancelSchedule(handle)。`refresh()`读取其他标签的最新修订。`can(actionId,entity?)`控制写入口，但提交仍在锁内复验。

`query(name,params,{signal})`支持：

- 任意实体类名，如`Field`、`Device`、`Plan`；别名fields/devices/strategies/plans/runs/alarms/workOrders/users/audit/readings/zones/exports。
- 列表params可含`filters`、page/pageSize/sortBy/sortDirection；返回`{items,total,page,pageSize,revision,summary}`。默认15条，summary按当前过滤全集。`params.id`返回`{entity,related,revision}`。
- `water`或`waterReport`调用统一有效账本领域投影；params={start,end,farmId?,fieldId?,seasonId?,seasonIds?,zoneId?,crop?}；返回totalM3/measuredM3/allocatedM3/estimatedM3/coveredAreaMu/perMuM3/rows/byField/byRun/baseline/baselineComparisons/farmSavingPercent。图表/统计请使用此投影或同一个domain函数，不能再手写账本sum。
- `resources`或`QUERY_PLAN_CONFLICTS`：传入完整`{...plan,steps}`，返回ok/conflicts/reservations/conflictHash/factVersions/revision；包括当前真实活动运行占用。
- `simulation`或`QUERY_STRATEGY_SIMULATE`：`{strategyId,asOf,representativePointByZone}`；返回zoneAssessments；asOf不晚于真实时刻。
- `exportFile`：`{exportId}`，返回`{fileName,content,checksum,revision}`。仅本机真实生成且未过期READY文件可下载，Blob以content创建。
- `publicFarm`无需会话，返回公开农场。
- `overview`传`{date?,asOf?}`返回fieldAreaMu/runningCount/settledWaterM3/pendingAlarmCount/offlineDeviceCount/deviceOnlineRate/activeRuns/queuedRuns/alarmSummary；date仅影响当日水量，asOf仅只读连接评估。

`commit(actionId,payload,{expectedVersion,expectedVersions,clientRequestId})`返回entityId/version/revision/changedEntities/result/replayed。页面更新请传原实体version；新建不传expectedVersion。expectedVersions可按实体ID传多实体版本；重复请求保留同clientRequestId。返回之前已完成真实持久化。错误具有code/message/fieldErrors/details/requestId。

| 动作 | payload |
| --- | --- |
| FIELD_CREATE / FIELD_UPDATE | 完整Field Draft，新增可无fieldId/code，自动生成；修改保留fieldId |
| SEASON_CREATE / SEASON_UPDATE | 完整CropSeason Draft：fieldId/crop/variety/plantingDate/harvestDate/stage；CREATE禁止seasonId、UPDATE必须seasonId。两种操作均强制options.expectedVersions[fieldId]匹配Field版本；UPDATE还必须expectedVersion匹配Season版本。下一季先收获归档 |
| PIPE_SAVE | PipeNode Draft；无nodeId新增，有nodeId修改 |
| ZONE_CREATE / ZONE_UPDATE | IrrigationZone Draft，含所有实体关联与计量依据 |
| DEVICE_CREATE / DEVICE_VERIFY | 新增编号/名称/合法类型/厂家/型号/protocol/endpoint必填；endpoint须可解析，保存为UNVERIFIED不代表可以省略接入配置。核验传deviceId，未接适配器时明确拒绝 |
| POINT_UPDATE / POINT_CALIBRATE | 更新完整Point；校准`{pointId,referenceValue,measuredValue,note}` |
| STRATEGY_CREATE / STRATEGY_UPDATE / STRATEGY_ENABLE / STRATEGY_DISABLE | 完整Strategy；启停传strategyId与version |
| PLAN_CREATE / PLAN_UPDATE | `{...plan,steps:[{planStepId?,zoneId,order,targetVolumeM3,expectedFlowM3h,maxDurationMin}]}`，原有步骤ID保留 |
| PLAN_PUBLISH | `{planId,conflictHash}`，hash由已保存当前Plan+步骤重新query resources得到 |
| PLAN_CANCEL | `{planId,reason}`，至少6字；与编排取消编辑不同 |
| RUN_START / RUN_PAUSE / RUN_RESUME / RUN_STOP | `{runId,reason}`，本机未接控制服务统一拒绝，不伪造反馈 |
| ALARM_ACK / ALARM_CLOSE | `{alarmId,note}`至少6字；关闭传resolution或note至少12字 |
| WORKORDER_CREATE | `{alarmId?,zoneId?,deviceId?,kind,assigneeId,dueAt,note}`，期限用实际未来时间；关联告警时强制options.expectedVersions[alarmId]为选中告警版本（expectedVersion兼容），未传或过期拒绝，不创建工单 |
| WORKORDER_ACCEPT / SUBMIT / APPROVE / RETURN | `{workOrderId,resultNote?/note?}`；提交结果12字、退回理由6字 |
| USER_CREATE / USER_UPDATE | User Draft；姓名/账号/角色/电话/fieldIds；不包含口令 |
| USER_DISABLE / USER_ENABLE | `{userId,reason?}`；停用理由6字 |
| POLICY_SAVE | SystemPolicy Draft，仅修改四个运行参数，不改联动序列 |
| EXPORT_CREATE / EXPORT_CANCEL | `{filters:{start,end,fieldId?,seasonId?,seasonIds?}}` / `{exportId}`；异步任务在entities.ExportJob刷新真实progress/status |

`subscribe(listener)`返回unsubscribe，事件`{revision,changedEntities,authChanged}`，登录、注销、到期或当前账号版本失效会发布authChanged=true供导航回登录页。Vue页面通常直接computed state，列表快照与脏稿由页面持有，不能被新修订清空。

正常读写时钟始终是真实Date；参考显示时钟由公共`useClock`提供。只读设备连接展示可从queries.js导入`effectiveDeviceConnection(device,displayNow)`；资源/写操作不能把reference时刻作为实际时刻传入。本机reference=1使用独立存储键，不修改用户普通预览数据。

损坏恢复仅由启动故障界面的明确操作调用，不是业务菜单：

- `exportCorruptSnapshot()`返回`{fileName,content}`，content逐字保留当前损坏/不兼容快照，UI以Blob下载，不改写存储。正常快照拒绝此操作。
- `recoverInitialSnapshot({confirmed:true})`要求UI明确确认替换本机数据（先提供备份入口）。仓储在写锁内再次确认当前快照损坏/不兼容，持久化完整初始快照成功后清会话/授权集合/索引/故障状态，回到登录；未确认返回CONFIRMATION_REQUIRED，正常快照返回RECOVERY_NOT_REQUIRED，写入失败保留损坏字节和原故障。未接正式HTTP通道不能执行本机恢复。
