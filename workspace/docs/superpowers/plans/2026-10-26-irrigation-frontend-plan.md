# 灌溉管控 Vue 前端实施计划

日期：2026-10-26，R3。状态：用户已通过「开始执行代码」确认进入Vue前端阶段，执行中。

依据：[详细开发spec R3](../specs/2026-10-26-irrigation-development-spec.md)。截图优先；20业务Screen及13菜单公共壳层；Vue3+Vite+Vue Router hash模式；统一异步仓储和领域求值。功能来源、入口、隐藏Tab和状态提交分别以spec第2.1、4.4、4.6、7.9节为准。原始截图、XML和共享数据只读。

执行顺序必须为：**更新spec → 用户确认 → 子agent编写Vue前端并验证 → 停止等待用户确认 → 子agent编写后端并联调**。spec确认关口已通过，当前允许安装前端依赖和编写Vue代码；后端关口仍未通过。前端完成不代表后端、生产鉴权或现场设备已完成。

## 1. 经核实的起点

- [x] 已有package.json、Vite配置和index.html；src/domain中已有关系、水量、资源、墒情与田块事实模块。
- [x] R2阶段实际重跑28项Node领域测试，28通过、0失败；R3仅修文档，不宣称新增契约已通过测试。
- [ ] 完整领域行为仍待补全：TIME改SCHEDULE、田块soilType校验、有效FINAL修订资格、可比基准面积比例换算、活动运行资源占用、Policy最长编排天数和生产能力边界。
- [ ] 缺少main.js、App、路由、页面、仓储、权限、持久化及依赖锁文件，当前不是可运行前端。
- [ ] 无实际运行截图、浏览器验收脚本、后端或数据库。

旧progress.txt仅作为此前执行记录保留；本次实际现状以本文和spec第14节为准，不把曾经的「第1项完成」解释为所有业务规则已通过。

## 2. 文件边界与子agent协作

主agent统一冻结仓储端口、动作/错误契约、路由和组件props；子agent实现代码。最多2个子agent同时运行；共享文件指定唯一所有者，依赖未完成不得并行猜接口。主agent集成、运行验收，完成证据齐备后才勾选。

| 所有权批次 | 预定文件 | 职责/依赖 |
| --- | --- | --- |
| 领域与仓储子agent | src/domain、src/data/contracts.js及其他data模块、scripts/prepare-preview-credentials.mjs、tests/domain.test.js、tests/repository.test.js、tests/permissions.test.js | 纯业务规则、统一提交、权限与本机会话、终端凭据准备；作为页面开发前置 |
| 公共前端子agent | src/main.js、App.vue、router、styles、components、composables、views/LoginView.vue | 壳层、公共控件、路由、草稿/列表状态；主agent冻结接口后交付其他子agent使用 |
| 资源与感知页面子agent | views/fields、views/network、views/devices、views/monitor | 田块/种植、管网、设备/点位/校准、监测；不改仓储/路由公共文件 |
| 灌溉作业页面子agent | views/strategies、views/plans、views/runs | 策略试算、轮灌编排、资源检查、运行三Tab；只调用冻结端口 |
| 配套页面子agent | views/OverviewView.vue、views/alarms、views/maintenance、views/water、views/settings、views/audit | 总览、告警维护、水量/导出、账号参数和审计；可在前一批完成后复用同一子agent |
| 集成与验证批次 | scripts/validate_frontend.py、frontend/README.md、validation | 子agent补验证脚本/说明，主agent执行实际启动、截图、业务链路和比对修正 |

## 3. 前端实施任务

### F1 纠正已有领域缺口

- [ ] 先补SCHEDULE/VOLUME/MOISTURE行为用例，观察SCHEDULE旧分支失败，再修moisture-evidence.js；不得改共享数据或继续传播TIME枚举。
- [ ] 补soilType必选/非法值、同农场负责人及状态校验；保留原有面积和稳定ID约束。
- [ ] 按XML SELECT-WATER修正有效修订：PROVISIONAL/INVALID不抑制旧FINAL，有效FINAL后继仅计新版；修订链异常拒绝，纠正固化错误预期的旧测试。
- [ ] 按referenceVolumeM3/referenceAreaMu×本期可比面积计算基准量，取消面积必须相等限制；保留田块/作物/窗口和分区子集不可比边界，补面积变化、零面积、负节水率测试。
- [ ] 资源检查纳入活动IrrigationRun/RunStep，防止仅靠Plan.scheduledAt漏掉超时占用；当前草稿自己的预留排除，仍计入其他运行。
- [ ] 检查Policy天数、代表点明确选择、时钟与历史试算分离；生产签核/适配器门槛独立于样本ONLINE/VERIFIED状态。
- [ ] 运行领域测试；验证求值不改变输入实体、复杂度和索引复用未退化。

完成证据：具体测试名/实际命令结果，记录新增覆盖，不能只以28项旧测试通过代替。

### F2 统一仓储、权限、会话与任务

- [ ] 在src/data建立统一query/commit/subscribe端口和本机实现；从shared_context.entities初始化一次，保留原ID及关系，不在各页面复制种子。
- [ ] 按spec第6.2节冻结query/commit/subscribe结果；Web Locks独占锁内重读最新版、验证权限/状态/expectedVersion，再完整持久化，成功才替换内存；变更同事务追加审计。
- [ ] 单独测试Quota失败、损坏数据、storage跨标签冲突、重复发布/派工、部分田块越权，失败保持旧状态及Draft。
- [ ] 编写终端 `preview:credentials` 准备工具，不在登录页新增口令初始化或角色选择；加盐摘要与User隔离、过期/停用会话撤销；不默认登录或接受任意密码。
- [ ] 验证两标签不同实体同刻修改均保留，同实体版本冲突拒绝覆盖；无锁只读、schema升级失败保留原字节、接收更新不覆盖脏Draft。
- [ ] 实现导出异步任务、实际进度、取消、失败和真实Blob；CANCELLED扩展按spec统一，准备HTTP替换端口。

完成证据：仓储/权限/会话测试；种子只读、口令不进实体快照或源码；失败原子性可复现。

### F3 公共UI、路由及导航状态

- [ ] 在frontend目录安装依赖并生成锁文件，确保已有Vite入口可用；不创建第二套前端工程。
- [ ] 子agent编写main/App/hash路由/公共样式，20Screen及新增路径均可访问；详情/编辑激活父菜单。
- [ ] 第4.4节的标题、编号、状态标签用真实可聚焦button/link，默认外观保持PNG；发布/取消与告警处置只在记录上下文弹窗出现，禁止新增常驻操作列。
- [ ] 复用AppShell、导航、MetricCard、StatusBadge、DataTable、Pagination、ModalHost、FormField和图表；PNG实际约70px顶栏、238px侧栏为参考。
- [ ] 分组折叠、角色菜单、退出确认和窄屏居中导航真实开关；登录无壳层，未登录/越权路由拦截。
- [ ] 列表过滤/排序/页码/选择/滚动快照，编辑脏稿离开守卫；加载/空/错误/无实体不同状态。

完成证据：启动后登录/导航/返回、焦点/键盘和弹窗提交锁检查；不能仅检查组件文件存在。

### F4 田块、种植季与管网

- [ ] 田块3×5卡片、统计、筛选、新增/档案/编辑及种植季，字段/动作顺序按spec第4.1/4.2节。
- [ ] 实现档案事实→编辑、分区→network、读数→monitor、历史→run的实际入口，返回保留原列表状态。
- [ ] 管网水源选择、SVG节点、选中参数及分页分区表；新增/编辑管段和分区的真实保存/取消。
- [ ] 测试面积覆盖、唯一活动季、管网无环、阀门冲突、独立计量/分摊规则及运行引用限制。

完成证据：田块修改跨页同步及刷新持久化；图示节点与实体稳定ID关联。

### F5 设备、点位和监测

- [ ] 设备台账4指标/15行/分页、登记；档案能力矩阵和3Tab；点位/校准/诊断共用实体。
- [ ] 核验接入未配置服务明确返回不可核验，不伪造VERIFIED或动作反馈。
- [ ] 分区/点位/深度/日期联动，曲线/当前读数/明细同查询；点选曲线定位原始记录。
- [ ] 过期、质量、离线分别显示，校准追加证据不改原读数；保存映射使能力验证失效。

完成证据：Tab/分页/筛选/校准取消和保存、异常读数及无数据验证。

### F6 策略、计划与运行

- [ ] 策略列表/编辑/启停/试算，试算代表点显式选择；目标分区作物阶段一致，AUTO门槛禁用。
- [ ] 计划日期/泵站/状态查询、5天时间轴及真实分页；编排内添加/移除/上移下移/数值编辑。
- [ ] 修改后检查hash失效，保存与发布重验；非草稿只读，发布原子创建唯一QUEUED及RunStep，取消条件复验。
- [ ] 运行全场卡与历史查询分离，详情3Tab、历史账本和3阶段时间线；完成态控制禁用。
- [ ] 本机模式控制确认后明确服务未连接，不模拟ACK/状态推进；不实现后端outbox发送器。

完成证据：策略版本快照、资源冲突、发布/取消/幂等、控制失败原态和详情返回链路。

### F7 总览、维护、水量与系统

- [ ] 总览SVG田块、6指标、活动/待执行卡和告警摘要，点击带条件钻取。
- [ ] 告警筛选即应用、行选中详情，知悉/派工/关闭；维护4泳道和本人接单/提交、管理员验收/退回。
- [ ] 水量4指标、15田块柱图、同窗口基准、明细与导出任务；全部来自统一有效账本投影。
- [ ] 账号表/编辑/停启与参数Tab/摘要，自身及最后管理员保护；审计只读可追关联对象和指令。

完成证据：告警与工单双向同步，未恢复验收拒绝；CSV实际行数/统计一致，角色与参数规则生效。

### F8 实际运行验证和截图修正

- [ ] 单元测试、生产构建通过后启动Vite；编写并实际执行浏览器自动化，不引用尚不存在的脚本为通过证据。
- [ ] Chromium按1536×1024/DPR1采集20业务Screen、公共导航及必要状态，存validation/screenshots。
- [ ] 参考模式使用独立浏览器profile/仓储与spec给出的实体ID；运行验证不改变共享数据，不用截图充当页面背景。
- [ ] 逐项追溯S/F/R/D来源；记录允许差异；按spec第14.3节命名主状态/Tab/弹窗截图及清单，不能只截默认首页。
- [ ] 逐页比对布局、字体、表格列宽/15行、按钮顺序、Tab/弹窗位置、数据和导航；修复明显差异后重采受影响图。
- [ ] 验证spec第14.2节链路及console/pageerror；对失败修复并复测相应链路，不用无关重复测试拖延交付。

完成证据：实际截图文件、命令日志、链路PASS/FAIL/未执行和已知差异，原资料SHA256一致。

### F9 前端交付与停止

- [ ] README明确安装/启动/构建、本机口令/数据恢复、后端未实现与现场服务边界。
- [ ] 明确preview/http数据通道及沙箱不自动迁移；保留旧origin和快照；正式HTTP构建不包含共享实体或开发摘要，断API不回退本机写入。
- [ ] validation/frontend-validation.md链接截图与测试证据；页面对应表保持spec同步。
- [ ] 更新本计划实际完成标记，列出遗留项/具体原因；主agent交付Vue前端后停止等待用户明确确认。
- [ ] 用户确认前不新建backend目录、数据库、控制通道或生产认证实现。

## 4. 预定执行命令

所有shell遵守RTK前缀；命令在指定目录以非登录shell执行，避免环境将cwd重置。下列是计划命令，除npm test已执行外，其余不表示本轮已运行。

frontend目录：`rtk proxy npm install`、`rtk proxy npm test`、`rtk proxy npm run build`、`rtk proxy npm run dev -- --host 0.0.0.0`。

workspace目录：浏览器脚本创建后执行 `rtk proxy python3 scripts/validate_frontend.py`。README给普通用户直接使用的npm命令，不强制最终用户安装RTK。

后端任务按照spec第12节，在前端验收获确认后另细化执行；当前只冻结模型/接口和状态契约。
