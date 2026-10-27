# 前端实际浏览器验证

运行时间：2026-10-27T04:04:23+00:00。URL：`http://127.0.0.1:5189`。Chromium headless，1536×1024，DPR 1，zh-CN，Asia/Shanghai。浏览器使用一次性临时 context，不读取或覆盖用户现有 localStorage。

本报告只写脚本实际观察到的结果。PASS表示对应UI操作或页面状态已在本轮执行；PARTIAL表示核心检查执行但本轮未取得全部结果；FAIL表示实际断言失败。截图位于`validation/screenshots/`，机器结果为`validation/frontend-validation.json`。

## 结果汇总

PASS 41 · PARTIAL 0 · FAIL 0 · 未执行 0 · pageerror 0 · console.error 0

## 页面与功能结果

| 检查 | 状态 | 操作步骤 | 实际结果 | 证据 |
|---|---|---|---|---|
| 登录空值校验 | **PASS** | 在账号和密码均为空时提交登录表单。 | 空账号被拒绝并显示字段提示；页面没有注册或初始化口令流程。 | `validation/screenshots/reference/账号登录.png` |
| 登录错误凭据拒绝 | **PASS** | 使用一次性随机无效口令提交临时管理员账号。 | 错误口令被拒绝，账号保留且密码清空；随机口令未写入报告。 | — |
| 管理员登录成功 | **PASS** | 使用已设置的临时管理员预览口令登录；口令只在进程内存和本次隔离浏览器操作中使用。 | 临时管理员账号登录成功；口令不写入截图清单或结果JSON。 | — |
| 默认页面：灌溉总览 | **PASS** | 完整导航至 /overview，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“田块面积”；该页面不要求15行分页；保存1536×1024浏览器实际截图。 | — |
| 默认页面：田块与种植 | **PASS** | 完整导航至 /fields，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“田块名称”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：田块档案 | **PASS** | 完整导航至 /fields/FLD-JZ-M9R2，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“田块基本信息”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：田块资料编辑 | **PASS** | 完整导航至 /fields/FLD-JZ-M9R2/edit，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“田块基本资料”；该页面不要求15行分页；保存1536×1024浏览器实际截图。 | — |
| 默认页面：管网与轮灌分区 | **PASS** | 完整导航至 /network，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“水源”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：设备接入台账 | **PASS** | 完整导航至 /devices，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“设备总数”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：设备运行档案 | **PASS** | 完整导航至 /devices/DEV-JZ-S7KW，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“核验接入”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：墒情与环境监测 | **PASS** | 完整导航至 /monitor，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“深度”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：灌溉策略 | **PASS** | 完整导航至 /strategies，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“作物”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：灌溉策略编辑 | **PASS** | 完整导航至 /strategies/STR-JZ-K8QM/edit，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“策略名称”；该页面不要求15行分页；保存1536×1024浏览器实际截图。 | — |
| 默认页面：灌溉计划 | **PASS** | 完整导航至 /plans，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“泵站轮灌时间轴”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：轮灌计划编排 | **PASS** | 完整导航至 /plans/PLN-JZ-M4FD/edit，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“计划名称”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：灌溉运行 | **PASS** | 完整导航至 /runs，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“全场运行中”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：灌溉执行控制 | **PASS** | 完整导航至 /runs/RUN-JZ-18E71500，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“计量明细”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：运行告警 | **PASS** | 完整导航至 /alarms，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“严重度”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：巡检与维护 | **PASS** | 完整导航至 /maintenance，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“待接单”；该页面不要求15行分页；保存1536×1024浏览器实际截图。 | — |
| 默认页面：用水与节水分析 | **PASS** | 完整导航至 /water，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“区间总水量”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：账号与系统配置 | **PASS** | 完整导航至 /settings，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“用户权限”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 默认页面：操作与指令审计 | **PASS** | 完整导航至 /audit，等待networkidle、字体加载和Vue绘制帧。 | 路由可达，主内容包含“操作人”；默认分页显示15条；保存1536×1024浏览器实际截图。 | — |
| 公共导航壳层 | **PASS** | 在总览路由核对公共顶栏、侧栏菜单、角色入口和连接状态。 | ADMIN壳层渲染13个导航入口、当前角色和本机预览连接状态。 | `validation/screenshots/reference/公共导航.png` |
| 默认截图清单完整 | **PASS** | — | 20个业务Screen和公共导航壳层共21张默认截图均已实拍。 | — |
| 田块筛选、详情返回、面积校验和持久化 | **PASS** | 按第一张田块卡片名称筛选，再进入档案并返回。<br>从档案编辑入口将面积改为0并确认非法输入被拒绝。<br>恢复合法面积、修改名称并保存；重载后核对本机隔离快照。 | 非法面积被保留在编辑页并标错；合法名称变更保存后重载仍存在（只在本次临时浏览器profile）。 | `frontend/src/views/fields/FieldListView.vue`<br>`frontend/src/views/fields/FieldEditView.vue` |
| 新增田块与总览地图跨页详情及种植季版本 | **PASS** | 填写有效田块基本信息并新增田块。<br>在总览地图翻到第2页，点击新建田块并核对进入同一个田块ID档案。<br>在新田块上创建种植季，再更新同一season实体。 | 新增田块保存后可读；总览地图第一页显示15块，翻到第2/2页显示新增第16块，点击后进入同一fieldId档案；新建种植季并更新同一season，版本递增到2且二版品种经重载保留。 | `validation/screenshots/states/总览-第16田块地图.png`<br>`validation/screenshots/states/总览-第16田块详情.png`<br>`validation/screenshots/states/田块-新增及种植季.png` |
| 种植季草稿Esc关闭守卫 | **PASS** | 修改种植季Draft后按Escape；拒绝放弃时原弹窗和草稿仍可见。 | Escape先进入放弃确认；拒绝后种植季草稿弹窗继续显示，明确放弃后才关闭。 | — |
| 设备三Tab与未适配器核验拒绝 | **PASS** | 切换设备档案Tab：点位映射。<br>切换设备档案Tab：校准记录。<br>切换设备档案Tab：诊断。<br>请求核验未配置适配器设备，确认不显示成功核验。 | 三个设备Tab均可达；无适配器核验被拒绝，显示：尚未配置可用的设备接入适配器，未执行核验 | — |
| 计划第3页与步骤资源检查 | **PASS** | 进入草稿编排，添加并移除候选分区，再运行资源检查。 | 计划列表可访问第3页（31条/3页）；新草稿添加两步、调整顺序、移除一步；资源检查实际返回“存在资源冲突”。 | — |
| 运行控制拒绝及三Tab | **PASS** | — | 无控制服务时启动被拒绝且待执行状态保留；运行三Tab可切换。初始队列摘要长度=72。 | — |
| 统一水量与真实CSV导出 | **PASS** | 核对统一账本四项总计、单窗口基准和全场不可比说明。 | 账本汇总匹配4963.5/4928.9/34.6/8.94及单窗口16.52%、全场不可比；生成并下载CSV（2356 bytes，UTF-8 BOM，已检查表头和数据行并清理临时文件）。 | — |
| Settings自停用保护与参数草稿 | **PASS** | 检查当前管理员账号停用按钮禁用。<br>创建临时只读账号，在列表中重新打开并编辑后重载核对。<br>确认运行参数修改，读取新的摘要值。 | 自身停用disabled；参数草稿取消被拒时保留、重置恢复；临时用户创建/编辑经重载保留；运行参数修改经确认提交。 | — |
| 审计分页与行选择 | **PASS** | — | 审计列表分页和行选中均可操作；该页为只读。 | — |
| 审计日期控件布局与命令确认时间 | **PASS** | 测量日期区间控件与查询按钮在1536×1024视口中的实际矩形。<br>从本机预览快照中选择命令事件时间与CommandOutbox确认时间不同的审计链路，并核对界面采用后者。 | 日期区间与查询按钮无重叠；审计链路CMD-JZ-R9FV的动作确认时间等于命令confirmedAt（2026-07-28 09:53:08），未采用不同设备事件时间。 | — |
| 策略分区完整显示与滚动 | **PASS** | 检查策略适用分区列表的全部选项、可滚动样式和滚动到底后的最后一项。 | 策略编辑器列出16个适用分区；列表overflow-y=auto，末项滚动后完整可见。 | — |
| 田块历史排除待执行运行 | **PASS** | 逐页读取田块灌溉记录，确认历史列表不展示任何待执行运行。 | 逐页检查15条田块记录；相关待执行运行1条均未出现在历史表。 | — |
| 告警详情在视口内完整布局 | **PASS** | 测量选中告警详情面板和所有详情字段在1536×1024视口中的边界。 | 告警详情面板完整位于视口内（x=266.0..1506.0, y=822.5..1007.5），无横向溢出。 | — |
| 告警重复派工与工单退回验收闭环 | **PASS** | 打开已有活动告警，验证存在未完成工单时派工和未恢复时关闭均禁用。<br>由管理员创建无告警关联工单，明确分配给临时技术员并进入待接单。<br>临时技术员本人接单并提交处理结果。<br>管理员退回一次补充材料，再由本人复提并验收完成。 | 活动未恢复告警的派工/关闭入口均阻断；QA工单经本人接单、提交、管理员退回、本人复提及管理员验收后达到COMPLETED。所有更改仅在一次性预览context。 | — |
| VIEWER只读入口与路由拒绝 | **PASS** | 退出管理员后使用隔离只读账号登录。 | VIEWER只读会话可查看田块、写入入口disabled；直接访问Settings被拒并回到总览。 | — |
| 损坏快照备份与确认恢复 | **PASS** | 损坏快照出现时先下载原始备份，再确认恢复初始数据。 | 下载备份与注入的损坏字节完全一致；确认后只恢复本临时context的参考快照并回到登录。 | — |
| 浏览器未处理错误 | **PASS** | — | Observed expected UI behavior. | — |

## 默认页面截图清单

| 页面 | 路由 | 截图 | 尺寸 | 修订 |
|---|---|---|---:|---:|
| 账号登录 | `/login` | `validation/screenshots/reference/账号登录.png` | 1536×1024 | 0 |
| 灌溉总览 | `/overview` | `validation/screenshots/reference/灌溉总览.png` | 1536×1024 | 0 |
| 田块与种植 | `/fields` | `validation/screenshots/reference/田块与种植.png` | 1536×1024 | 0 |
| 田块档案 | `/fields/FLD-JZ-M9R2` | `validation/screenshots/reference/田块档案.png` | 1536×1024 | 0 |
| 田块资料编辑 | `/fields/FLD-JZ-M9R2/edit` | `validation/screenshots/reference/田块资料编辑.png` | 1536×1024 | 0 |
| 管网与轮灌分区 | `/network` | `validation/screenshots/reference/管网与轮灌分区.png` | 1536×1024 | 0 |
| 设备接入台账 | `/devices` | `validation/screenshots/reference/设备接入台账.png` | 1536×1024 | 0 |
| 设备运行档案 | `/devices/DEV-JZ-S7KW` | `validation/screenshots/reference/设备运行档案.png` | 1536×1024 | 0 |
| 墒情与环境监测 | `/monitor` | `validation/screenshots/reference/墒情与环境监测.png` | 1536×1024 | 0 |
| 灌溉策略 | `/strategies` | `validation/screenshots/reference/灌溉策略.png` | 1536×1024 | 0 |
| 灌溉策略编辑 | `/strategies/STR-JZ-K8QM/edit` | `validation/screenshots/reference/灌溉策略编辑.png` | 1536×1024 | 0 |
| 灌溉计划 | `/plans` | `validation/screenshots/reference/灌溉计划.png` | 1536×1024 | 0 |
| 轮灌计划编排 | `/plans/PLN-JZ-M4FD/edit` | `validation/screenshots/reference/轮灌计划编排.png` | 1536×1024 | 0 |
| 灌溉运行 | `/runs` | `validation/screenshots/reference/灌溉运行.png` | 1536×1024 | 0 |
| 灌溉执行控制 | `/runs/RUN-JZ-18E71500` | `validation/screenshots/reference/灌溉执行控制.png` | 1536×1024 | 0 |
| 运行告警 | `/alarms` | `validation/screenshots/reference/运行告警.png` | 1536×1024 | 0 |
| 巡检与维护 | `/maintenance` | `validation/screenshots/reference/巡检与维护.png` | 1536×1024 | 0 |
| 用水与节水分析 | `/water` | `validation/screenshots/reference/用水与节水分析.png` | 1536×1024 | 0 |
| 账号与系统配置 | `/settings` | `validation/screenshots/reference/账号与系统配置.png` | 1536×1024 | 0 |
| 操作与指令审计 | `/audit` | `validation/screenshots/reference/操作与指令审计.png` | 1536×1024 | 0 |
| 公共导航 | `/overview` | `validation/screenshots/reference/公共导航.png` | 1536×1024 | 0 |

## 交互状态截图

| 状态 | 路由 | 截图 | 尺寸 | 修订 |
|---|---|---|---:|---:|
| 田块-非法面积 | `/fields/FLD-JZ-D7K4/edit` | `validation/screenshots/states/田块-非法面积.png` | 1536×1024 | 0 |
| 总览-第16田块地图 | `/overview` | `validation/screenshots/states/总览-第16田块地图.png` | 1536×1024 | 2 |
| 总览-第16田块详情 | `/fields/FLD-RH-5B04DBFB36` | `validation/screenshots/states/总览-第16田块详情.png` | 1536×1024 | 2 |
| 田块-新增及种植季 | `/fields` | `validation/screenshots/states/田块-新增及种植季.png` | 1536×1024 | 4 |
| 种植季-拒绝放弃 | `/fields` | `validation/screenshots/states/种植季-拒绝放弃.png` | 1536×1024 | 4 |
| 设备档案-点位映射 | `/devices/DEV-JZ-S7KW` | `validation/screenshots/states/设备档案-点位映射.png` | 1536×1024 | 4 |
| 设备档案-校准记录 | `/devices/DEV-JZ-S7KW` | `validation/screenshots/states/设备档案-校准记录.png` | 1536×1024 | 4 |
| 设备档案-诊断 | `/devices/DEV-JZ-S7KW` | `validation/screenshots/states/设备档案-诊断.png` | 1536×1024 | 4 |
| 计划-第3页 | `/plans` | `validation/screenshots/states/计划-第3页.png` | 1536×1024 | 4 |
| 计划-资源检查 | `/plans/new` | `validation/screenshots/states/计划-资源检查.png` | 1536×1024 | 4 |
| 运行详情-轮灌步骤 | `/runs/RUN-JZ-18E71500` | `validation/screenshots/states/运行详情-轮灌步骤.png` | 1536×1024 | 4 |
| 运行详情-指令记录 | `/runs/RUN-JZ-18E71500` | `validation/screenshots/states/运行详情-指令记录.png` | 1536×1024 | 4 |
| 运行详情-计量明细 | `/runs/RUN-JZ-18E71500` | `validation/screenshots/states/运行详情-计量明细.png` | 1536×1024 | 4 |
| 用水-CSV就绪 | `/water` | `validation/screenshots/states/用水-CSV就绪.png` | 1536×1024 | 10 |
| 设置-运行参数已保存 | `/settings` | `validation/screenshots/states/设置-运行参数已保存.png` | 1536×1024 | 13 |
| 审计-日期筛选与命令确认时间 | `/audit?selected=AUD-JZ-R6HW` | `validation/screenshots/states/审计-日期筛选与命令确认时间.png` | 1536×1024 | 13 |
| 策略-分区列表可滚动 | `/strategies/STR-JZ-K8QM/edit` | `validation/screenshots/states/策略-分区列表可滚动.png` | 1536×1024 | 13 |
| 田块档案-历史排除待执行 | `/fields/FLD-JZ-M9R2` | `validation/screenshots/states/田块档案-历史排除待执行.png` | 1536×1024 | 13 |
| 告警-详情视口完整 | `/alarms?selected=ALM-JZ-S8HD` | `validation/screenshots/states/告警-详情视口完整.png` | 1536×1024 | 13 |
| 告警-重复派工阻断 | `/alarms?selected=ALM-JZ-S8HD` | `validation/screenshots/states/告警-重复派工阻断.png` | 1536×1024 | 13 |
| 工单-新建待接单 | `/maintenance` | `validation/screenshots/states/工单-新建待接单.png` | 1536×1024 | 14 |
| 工单-退回补充 | `/maintenance` | `validation/screenshots/states/工单-退回补充.png` | 1536×1024 | 17 |
| 工单-验收完成 | `/maintenance` | `validation/screenshots/states/工单-验收完成.png` | 1536×1024 | 20 |
| 损坏快照-恢复界面 | `/login` | `validation/screenshots/states/损坏快照-恢复界面.png` | 1536×1024 | 0 |
| 损坏快照-恢复完成 | `/login` | `validation/screenshots/states/损坏快照-恢复完成.png` | 1536×1024 | 0 |

## 21页人工视觉结构对照

已将`screenshots/`中的21张参考PNG与`validation/screenshots/reference/`中本轮对应实际截图逐对并排查看，核对顶栏/侧栏、主要卡片/图表/表格结构和首屏关键数据。以下是定性人工记录，不计算像素差，也不声明达到spec中的2px/4px布局目标；视觉对照不计入上方功能断言PASS。实际截图保留原始1536×1024尺寸。

公共区域复核：20个业务页均显示固定农场名、2026.07.28 10:18:43、系统管理员、连接状态和13个导航子项；实际品牌图标轮廓与参考图略有不同。登录页按安全要求保持账号/口令为空。公共导航参考图的主区为空；实际证据从总览路由捕获公共壳层，因此主区保留总览且总览菜单选中。

弹窗对照边界：21张参考PNG均为默认页面状态，没有同一弹窗的参考PNG；实际脏表单、确认、退回等弹窗截图保存在`states/`，因此这里只记录功能取证，不宣称弹窗视觉一致。设备、运行和设置默认Tab位置已随各自页面并排核对；Tab的其他状态也有独立实际截图。

| 页面 | 原参考图 | 实际截图 | 结构与关键数据 | 可见差异/说明 |
|---|---|---|---|---|
| 账号登录 | `screenshots/账号登录.png` | `validation/screenshots/reference/账号登录.png` | 账号居中卡片、品牌、双输入框、登录按钮、连接状态和农场名均出现。 | 参考图预填账号并显示掩码口令；实际图输入为空，减少凭据暴露；背景等高线和品牌图形也有差异。 |
| 灌溉总览 | `screenshots/灌溉总览.png` | `validation/screenshots/reference/灌溉总览.png` | 6项指标、15格田块图、当前/待执行任务和底部告警摘要均可见；初始汇总与运行值相符。 | 地图田块轮廓与参考图几何不同；日期控件呈MM/DD/YYYY。地图翻页与新田块详情另由交互状态实测。 |
| 田块与种植 | `screenshots/田块与种植.png` | `validation/screenshots/reference/田块与种植.png` | 筛选行、面积汇总和3×5共15张卡片齐全；卡片名称/编号/面积/土壤/阶段/负责人顺序一致。 | 实际图额外显示单页分页控件；卡片间距、按钮位置和统计图标与参考图有差异。 |
| 田块档案 | `screenshots/田块档案.png` | `validation/screenshots/reference/田块档案.png` | 基本信息、种植季、分区、墒情卡及15行历史表均出现，田块和24.9%读数一致。 | 历史表已排除待执行任务；回归逐页检查确认不包含关联待执行运行。 |
| 田块资料编辑 | `screenshots/田块资料编辑.png` | `validation/screenshots/reference/田块资料编辑.png` | 基本资料、位置面积、土壤负责人、示意图及保存/取消/重置入口与字段值均可见。 | 实际分区与表单卡片垂直留白略大；地图网格和点位标记样式不同。 |
| 管网与轮灌分区 | `screenshots/管网与轮灌分区.png` | `validation/screenshots/reference/管网与轮灌分区.png` | 水源选择、拓扑、分区参数和15行清单齐全，首分区19.3亩/55m³h等值一致。 | 拓扑节点图标和连线布局不同，实际表格纵向更紧；首屏15行的分区实体与顺序一致。 |
| 设备接入台账 | `screenshots/设备接入台账.png` | `validation/screenshots/reference/设备接入台账.png` | 四项设备指标75/71/4/74及筛选、登记入口、15行设备表可见，首屏数据一致。 | 摘要图标、表头列宽和页脚控件与参考图不同，主要布局顺序一致。 |
| 设备运行档案 | `screenshots/设备运行档案.png` | `validation/screenshots/reference/设备运行档案.png` | 设备编号、状态、能力矩阵、点位映射Tab及15条点位均可见，设备和读数值一致。 | 参考图为传感器插画，实际用简化CSS设备形状；表格行距和点位映射Tab位置略有差异。 |
| 墒情与环境监测 | `screenshots/墒情与环境监测.png` | `validation/screenshots/reference/墒情与环境监测.png` | 分区/点位/深度/日期筛选、当前20.8读数、趋势图和15行原始表齐全。 | 实际曲线未显示参考图上的时间/读数点注，改用空心点；日期输入格式为MM/DD/YYYY。 |
| 灌溉策略 | `screenshots/灌溉策略.png` | `validation/screenshots/reference/灌溉策略.png` | 作物/阶段/状态筛选、15条策略表及15/12/3汇总均可见，首屏记录和状态一致。 | 实际表格列宽、行高与筛选卡间距不同；未见明显首屏数据差异。 |
| 灌溉策略编辑 | `screenshots/灌溉策略编辑.png` | `validation/screenshots/reference/灌溉策略编辑.png` | 策略名、阈值21.5、单次目标138、最长240分钟和两个已选分区与参考相符。 | 分区框首屏完整显示两行，其余选项可滚动访问；浏览器原生时间控件显示AM/PM，与参考图24小时格式不同。 |
| 灌溉计划 | `screenshots/灌溉计划.png` | `validation/screenshots/reference/灌溉计划.png` | 四项状态汇总1/16/13/1、时间轴和15行列表均可见，31条/3页一致。 | 实际第4至15行显示草稿，而参考图这些位置显示历史完成/发布计划；时间轴行名也有差别。日期控件采用MM/DD/YYYY。 |
| 轮灌计划编排 | `screenshots/轮灌计划编排.png` | `validation/screenshots/reference/轮灌计划编排.png` | 计划名/时间、5个候选分区、15步及274.5m³摘要均可见，步骤核心数据一致。 | 实际选择框增加“选择分区…”占位；日期时间采用AM/PM显示，控件排布和行宽与参考略异。 |
| 灌溉运行 | `screenshots/灌溉运行.png` | `validation/screenshots/reference/灌溉运行.png` | 运行中/完成/待执行数1/16/1、当前运行55.0m³/h和23.2m³暂计量及15行历史均可见。 | 实际运行/待执行卡片图标和字段排布更简化；截图可见的数据值与参考一致。 |
| 灌溉执行控制 | `screenshots/灌溉执行控制.png` | `validation/screenshots/reference/灌溉执行控制.png` | 运行ID、起止时间、274.5m³及轮灌步骤/指令/计量Tab和15行计量记录均可见。 | 实际控制摘要图标与参考图形不同，并在指令链增加“查看对应审计”链接；核心账本行值一致。 |
| 运行告警 | `screenshots/运行告警.png` | `validation/screenshots/reference/运行告警.png` | 15条告警、10待处理、4未恢复、5已关闭及选中告警/工单摘要可见，首屏告警数据一致。 | 已调整间距和行高；本次1536×1024截图中选中详情完整可见。 |
| 巡检与维护 | `screenshots/巡检与维护.png` | `validation/screenshots/reference/巡检与维护.png` | 四个状态泳道及3/5/2/5计数一致，工单编号、责任人、分区和状态可见。 | 同一泳道卡片顺序与参考图不同；实际卡片和泳道间距更紧，未发现缺失列。 |
| 用水与节水分析 | `screenshots/用水与节水分析.png` | `validation/screenshots/reference/用水与节水分析.png` | 账本总量4963.5、实测4928.9、分摊34.6、亩均8.94、基准16.52%和15条明细相符。 | 实际初始导出任务显示已过期/不可恢复，参考图显示可下载；实际导出交互另实测重新生成并下载成功。日期输入为MM/DD/YYYY；菜单按当前路由高亮用水，与参考图高亮维护不同，属spec第2节冲突表列明差异。 |
| 账号与系统配置 | `screenshots/账号与系统配置.png` | `validation/screenshots/reference/账号与系统配置.png` | 15账号/14启用/1停用和120/12/48/30参数摘要、15行用户表均可见。 | 首行“用户标识”实际显示User.name“周砚秋”，参考图显示zyq.admin；账号列仍显示zyq.admin。此处按spec第2节冲突表要求以User.name展示；菜单按当前路由高亮Settings，与参考图高亮统计项不同，均单独记录。 |
| 操作与指令审计 | `screenshots/操作与指令审计.png` | `validation/screenshots/reference/操作与指令审计.png` | 75条审计、15行表、选中记录和三阶段链路均可见，主记录ID和事件相符。 | 日期区间与查询按钮不再重叠；动作确认显示命令级确认时间09:53:08。 |
| 公共导航 | `screenshots/公共导航.png` | `validation/screenshots/reference/公共导航.png` | 13个菜单项、分组、顶栏农场/时间/角色和连接状态可核对。 | 原图右侧主区纯空白且无选中项；实际截图从总览路由捕获，故主区保留完整总览且总览菜单选中，这是应用无空白母版路由的说明性取证方式。 |

## 输入资料完整性

PASS：本轮开始和结束时核对`validation/reference-inputs.sha256`共45项，全部匹配且未变化。

## 浏览器错误

本轮未捕获pageerror。
本轮未捕获console.error。

## 边界与未验证项

本轮针对本机Vue预览仓储。设备核验/运行启动如果被拒绝，表示前端正确显示未接生产适配器或控制服务；不能据此宣称生产控制、服务端鉴权、API联调或现场设备反馈通过。后端尚未接入，前端业务修改仅在本次临时浏览器profile中，不自动迁移到数据库。

截图`公共导航.png`从总览路由实际捕获公共壳层；应用没有空白导航母版路由，因此截图主内容区保留总览页面。

本报告由`python3 scripts/validate_frontend.py --base-url <URL>`生成。
