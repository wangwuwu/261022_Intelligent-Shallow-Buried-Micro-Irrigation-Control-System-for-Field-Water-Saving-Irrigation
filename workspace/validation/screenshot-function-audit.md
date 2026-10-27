# 截图功能与前端实现核查

核查对象：本目录中的 `screenshots/` 与 `frontend/src/`。逐张查看 21 张截图，对照 Vue 页面、路由和数据操作代码；本次为源码与截图核查，没有重新逐控件执行浏览器操作。已有浏览器回归见 `frontend-validation.md`：41 项通过，但并非覆盖全部控件。`frontend/src` 与此前验收的前端副本 60 个文件哈希一致。

## 结论

截图对应的页面及主要导航、查询、表单、分页和记录入口均可在前端找到实现，但不能认为所有功能已端到端完成：设备接入核验和现场诊断不可用；运行启动、暂停、恢复和停止未连接控制服务；策略自动执行不可开启；数据、账号和状态变更仅保存在本机浏览器，正式 HTTP 服务未实现。受限功能不会伪装成操作成功。

## 截图与页面对应

| 截图 | 代码页面 | 前端实现及限制 |
|---|---|---|
| 公共导航 | `src/components/AppShell.vue` | 菜单、折叠、跳转、账号菜单和退出；没有截图的空白母版独立路由。 |
| 账号登录 | `src/views/LoginView.vue` | 输入校验、本机凭据登录和错误提示；无生产身份服务。 |
| 灌溉总览 | `src/views/OverviewView.vue` | 日期、刷新、指标及地图和记录跳转；农场选择仅当前农场。 |
| 田块与种植 | `src/views/fields/FieldListView.vue` | 名称/状态筛选、新增、档案、种植季、分页。 |
| 田块档案 | `src/views/fields/FieldDetailView.vue` | 田块、种植季、分区、墒情及历史运行与关联跳转；墒情剖面只选择一个点位。 |
| 田块资料编辑 | `src/views/fields/FieldEditView.vue` | 字段编辑、校验、保存、重置和取消；位置为示意网格。 |
| 管网与轮灌分区 | `src/views/network/NetworkView.vue` | 水源、拓扑选择、新增管段/分区、参数与列表；拓扑为简化视图。 |
| 设备接入台账 | `src/views/devices/DeviceListView.vue` | 设备筛选、登记、指标及详情入口；登记不会自动接通设备。 |
| 设备运行档案 | `src/views/devices/DeviceDetailView.vue` | 点位、校准、诊断标签及表单；核验和现场通信诊断未接入。 |
| 墒情与环境监测 | `src/views/monitor/MonitorView.vue` | 分区、点位、深度、日期查询，曲线和表格；目前为土壤含水率。 |
| 灌溉策略 | `src/views/strategies/StrategyListView.vue` | 筛选、新增、编辑、试算及生成计划草稿，受权限与试算结果限制。 |
| 灌溉策略编辑 | `src/views/strategies/StrategyEditView.vue` | 参数编辑、保存、重置、取消；自动执行不可开启。 |
| 灌溉计划 | `src/views/plans/PlanListView.vue` | 筛选、时间轴、编辑、资源检查、发布和取消。 |
| 轮灌计划编排 | `src/views/plans/PlanEditView.vue` | 分区和步骤增删排序、编辑、资源检查和保存。 |
| 灌溉运行 | `src/views/runs/RunListView.vue` | 筛选、卡片、详情和启动确认；启动未连接控制服务。 |
| 灌溉执行控制 | `src/views/runs/RunDetailView.vue` | 步骤、指令、计量标签及暂停/恢复/停止入口；操作受状态、权限和未接入控制服务限制。 |
| 运行告警 | `src/views/alarms/AlarmListView.vue` | 筛选、统计、详情、知悉、派工和关闭，受恢复和工单状态约束。 |
| 巡检与维护 | `src/views/maintenance/MaintenanceView.vue` | 泳道、筛选、详情、新建、接单、提交、验收和退回。 |
| 用水与节水分析 | `src/views/water/WaterReportView.vue` | 查询、图表联动、明细和 CSV 导出、下载、取消与重试。 |
| 账号与系统配置 | `src/views/settings/SettingsView.vue` | 用户、权限和运行参数维护，含自停用及管理员保护；预览账号认证不等于生产认证。 |
| 操作与指令审计 | `src/views/audit/AuditView.vue` | 只读筛选、分页、记录选择、命令阶段和关联对象跳转。 |

路径以 `frontend/` 为根。截图中巡检与维护、用水与节水分析、账号与系统配置的侧栏高亮与当前页面不一致；代码使用当前路由高亮。截图与运行页面的其他视觉差异见 `frontend-validation.md`。

## 关键代码证据

- `frontend/src/data/runtime.js`：HTTP 数据通道尚未配置，预览使用本机仓储。
- `frontend/src/data/actions.js:124`：设备核验在未配置适配器时拒绝。
- `frontend/src/data/actions.js:183`：运行控制在未连接控制服务时拒绝。
- `frontend/src/views/strategies/StrategyEditView.vue`：自动执行控件禁用。

未逐一实测每一个截图控件、每种权限和状态组合；不能据此宣称所有交互均已通过浏览器验证，也不能宣称生产后台及现场设备已验收。
