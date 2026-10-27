# 田间智能浅埋微灌节水灌溉管控系统后端

Node.js 24 + 原生 HTTP + SQLite（`node:sqlite`）后端，覆盖共享资料导入、服务端认证、按农场/田块授权读取、业务写事务、审计、幂等提交、真实 CSV 导出和 SSE 修订通知。

后端直接复用 `frontend/src/domain` 与 `frontend/src/data` 中的纯业务规则（关联索引、有效水量账本、轮灌资源判定、墒情证据、字段校验和 49 个写 Action），避免前后端出现两套资源/计量口径。SQLite 负责持久化，HTTP 层只做协议、鉴权和事务边界。

## 1. 环境与目录

要求：

- Node.js 24.14 或更高版本（`node:sqlite` 当前仍会打印 ExperimentalWarning，可正常使用）
- 可写的 SQLite 文件目录和导出目录
- 前端已安装依赖并可构建（仅在需要页面联调时）

```text
backend/
  src/
    main.js                 服务启动
    config.js               环境变量与路径
    http/server.js          路由、鉴权、CSRF、SSE、静态文件
    db/schema.js            SQLite 表、关系表与索引
    db/database.js          实体读写、事务、导出文件登记
    services/auth.js        scrypt 口令、会话、Cookie、撤销
    services/store.js       查询投影、提交事务、审计、幂等
    services/exports.js     CSV 后台任务、校验摘要、下载
    services/seed.js        共享资料显式导入
  scripts/
    import-seed.mjs         一次性导入 shared_context.json
    set-password.mjs        交互设置或重置账号口令
  tests/                    HTTP 与持久化测试
  var/                     SQLite（忽略提交）
  exports/                 真实 CSV 文件（忽略提交）
```

## 2. 首次部署

```bash
cd backend
node scripts/import-seed.mjs
node scripts/set-password.mjs zyq.admin
```

- `import-seed.mjs` 只读取项目根目录的 `shared_context.json`，记录来源 SHA-256，不导入共享 `Session`；已有业务用户时默认拒绝重灌，确需重建使用 `--force`。
- `set-password.mjs` 从标准输入隐藏读取口令，只在 `credentials` 表保存随机盐和 scrypt 摘要。共享资料里的 User 不含密码，首次部署必须为至少一名启用 ADMIN 设置口令。设置口令会撤销该账号已有会话。
- 重新执行 `--force` 导入会保留已设置的口令，但会撤销全部旧会话；共享资料中的历史 `ExportJob` 没有本机文件字节，下载时会明确返回不可恢复，不会伪造旧文件。

启动：

```bash
node src/main.js
```

默认监听 `127.0.0.1:3001`。如果 `../frontend/dist` 存在，会同时提供前端静态页面；未配置静态目录时只提供 `/api/v1`。

## 3. 环境变量

复制 `.env.example` 为 `.env` 或在进程环境设置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IRRIGATION_HOST` | `127.0.0.1` | 监听地址 |
| `IRRIGATION_PORT` | `3001` | 监听端口 |
| `IRRIGATION_DB` | `var/irrigation.sqlite` | SQLite 文件，相对 backend 或绝对路径 |
| `IRRIGATION_EXPORT_DIR` | `exports` | CSV 文件目录 |
| `IRRIGATION_STATIC_DIR` | `../frontend/dist` | 前端构建目录；设为空字符串可关闭静态服务 |
| `IRRIGATION_SEED` | `../shared_context.json` | 共享资料路径 |
| `IRRIGATION_SECURE_COOKIE` | `0` | 生产 HTTPS 设为 `1` |
| `IRRIGATION_TRUST_PROXY` | `0` | TLS 终止在反向代理时设为 `1` |
| `IRRIGATION_ALLOWED_ORIGINS` | 空 | 逗号分隔的额外可信 Origin；同 Host 自动允许 |
| `IRRIGATION_SESSION_TTL_MS` | `28800000` | 会话有效期，默认 8 小时 |
| `IRRIGATION_BODY_LIMIT` | `2097152` | 请求体上限，默认 2 MiB |
| `IRRIGATION_DEVICE_CHANNEL` | `disabled` | 当前没有厂家协议/点表/保护签核，控制通道保持禁用 |

SQLite 文件、`.env`、导出文件和密钥目录不要提交到版本库。

## 4. 前端联调

开发时由 Vite 把 `/api` 代理到 3001：

```bash
cd frontend
npm ci
npm run dev:http -- --host 127.0.0.1 --port 5173
```

`npm run dev:http` 使用 HTTP 数据通道，不会加载或回退到浏览器本机快照。Vite 代理保留原始 Host，后端用同源校验 Cookie 与 CSRF。

交付构建：

```bash
cd frontend
npm run build:http
cd ../backend
node src/main.js
```

打开 `http://127.0.0.1:3001`，HTTP 仓储通过 `/api/v1/snapshot`、`/api/v1/query`、`/api/v1/commit` 与后端交互。构建产物不包含共享用户列表或开发预览凭据；API 不可用时页面只报告连接失败，不会静默改用本机快照成功。

## 5. 认证、会话与写保护

- 口令：`scrypt`（N=16384, r=8, p=1，64 字节摘要），随机 16 字节盐，`timingSafeEqual` 比较。
- 会话：服务端生成 32 字节随机 token，数据库只保存 SHA-256 摘要；8 小时过期，可撤销；Web 端使用 `HttpOnly; SameSite=Lax` Cookie，HTTPS 可加 `Secure`。
- 写请求：校验同源 `Origin`、`X-CSRF-Token`（会话级随机 token）和 `Idempotency-Key`。会话失效返回 401，越权返回 403。
- 所有业务写入在单个 `BEGIN IMMEDIATE` 事务内完成；实体 `version`、关联约束、权限和幂等响应与审计同提交。
- 用户修改/停用会使该账号旧会话失效；修改本人授权时当前会话也会被撤销。

## 6. API

统一前缀 `/api/v1`。

认证与基础：

| 方法与路径 | 说明 |
| --- | --- |
| `GET /health` | 存活、当前 revision、数据库与通道状态（公开） |
| `GET /bootstrap` | 公开农场名称/编号（公开，供登录页） |
| `POST /auth/login` | 账号口令登录，返回 User、CSRF token、过期时间 |
| `GET /auth/session` | 恢复会话；未登录返回 `user:null` |
| `POST /auth/logout` | 撤销当前会话并清 Cookie |
| `GET /snapshot` | 当前用户授权后的完整实体投影与 revision |
| `POST /query` | 统一只读查询（详见下文） |
| `POST /commit` | 统一业务提交 |
| `GET /events` | SSE 修订通知，`event: revision` |

页面接口：`/overview`、`/fields`、`/fields/:id`、`/fields/:id/seasons`、`/seasons/:id`、`/network`、`/pipe-nodes`、`/zones`、`/devices`、`/devices/:id`、`/devices/:id/points`、`/devices/:id/calibrations`、`/devices/:id/diagnostics`、`/points/:id`、`/points/:id/calibrations`、`/monitor/readings`、`/monitor/series`、`/strategies`、`/strategies/:id/simulate`、`/plans`、`/plans/assess-resources`、`/plans/:id/publish`、`/plans/:id/cancel`、`/runs`、`/runs/:id`、`/runs/:id/steps`、`/runs/:id/commands`、`/runs/:id/water`、`/runs/:id/start|pause|resume|stop`、`/alarms`、`/alarms/:id/acknowledge|close`、`/work-orders`、`/work-orders/:id/accept|submit|approve|return`、`/water/report`、`/water/ledger`、`/water/baselines`、`/exports`、`/exports/:id`、`/exports/:id/cancel`、`/exports/:id/file`、`/users`、`/users/:id`、`/users/:id/disable|enable`、`/policy`、`/audit`、`/audit/:id`。

列表参数：`page>=1`、`pageSize`（最大 100）、`sortBy`、`sortDirection`，其余键作为过滤条件；返回 `{items,total,page,pageSize,revision,summary?}`。详情返回 `{entity,related,revision}`。

### 统一查询

```json
POST /api/v1/query
{"name":"water","params":{"start":"2026-07-27","end":"2026-07-27"}}
```

`name` 支持实体类名或别名 `fields/devices/strategies/plans/runs/alarms/workOrders/users/audit/readings/zones/exports`，以及：

- `overview`：授权面积、运行、当日 FINAL 账本、告警和设备连接投影。
- `water`：有效账本修订、田块/运行/计量方式聚合、可比基准与不可比原因。
- `resources`：轮灌资源判定，返回 `ok/conflicts/reservations/conflictHash/factVersions/revision`。
- `simulation`：策略试算；多土层必须显式传入 `representativePointByZone`。
- `exportFile`：返回真实 CSV 文本、摘要和 revision。

### 统一提交

```json
POST /api/v1/commit
Idempotency-Key: 4a05...
X-CSRF-Token: ...
{"actionId":"FIELD_UPDATE","payload":{...},"options":{"expectedVersion":1}}
```

返回 `{entityId,version,revision,changedEntities,result,replayed}`。同一用户、同一 `actionId`、同一 `Idempotency-Key` 只执行一次；同一键提交不同内容返回 409。写失败不产生部分实体或授权变化。

### 错误

统一返回：

```json
{"code":"VERSION_CONFLICT","message":"记录已被其他操作更新","fieldErrors":{},"details":{},"requestId":"..."}
```

常用状态：401 未认证、403 越权/CSRF/来源、404 不存在、409 版本/资源/状态/幂等冲突、410 导出文件不可用、422 字段校验、503 设备适配器不可用。

## 7. 导出与任务

- 导出创建时固定筛选、来源 revision、授权田块和有效账本行快照；任务状态 `QUEUED → PROCESSING → READY/FAILED`，只允许 `QUEUED/PROCESSING → CANCELLED`。
- CSV 含 UTF-8 BOM，字段统一引用并防止公式注入；分批写入真实文件，完成后才记录 SHA-256、字节数和 `READY`。
- `/exports/:id/file` 再次校验创建者/ADMIN、农场、任务状态和过期时间，不返回半文件。
- 进度更新会推进 revision 并通过 SSE 通知，前端可见真实进度与取消结果。

## 8. 授权与业务规则

- 所有读取先按 `farmId` 和 `fieldIds` 投影，共享网关/泵站按供水或点位关系保留必要祖先；详情、统计、筛选、分页和冲突证据都使用同一授权投影。
- ADMIN 管理账号、设备接入、参数；MANAGER 维护业务资料/计划、派工验收与操作；OPERATOR 执行授权运行控制和告警知悉；TECHNICIAN 仅本人接单/提交及授权范围校准；VIEWER 只读。
- 写事务复用前端 Action：田块/种植季版本校验、管网无环、分区面积与阀门独占、策略分区作物阶段匹配、计划资源复验、发布生成唯一 QUEUED Run、告警与工单状态机、最后管理员与本人停用保护等。
- 管理员、只读、部分田块账号的越权行为由 `canOperate` 和提交事务双重拒绝，前端隐藏按钮不作为授权依据。

## 9. 设备控制边界

当前资料没有厂家协议、点表、本地保护和现场联动签核，`IRRIGATION_DEVICE_CHANNEL=disabled`。运行控制接口仍会做权限、版本、理由和状态前置校验，但不会伪造 ACK/动作完成，统一返回 503 `ADAPTER_UNAVAILABLE`，不修改运行状态。

这一点符合需求文档的边界：设备受理、通信应答和设备动作确认是不同阶段；在取得真实协议和签核前，不应把隔离样本或页面状态当作现场成功。

## 10. 测试

```bash
cd backend
npm test
```

覆盖：

- 共享资料导入、登录、公开农场和授权快照；
- 只读账号写入/账号列表越权拒绝；
- 田块修改持久化、版本冲突、幂等重放与幂等内容冲突；
- 计划取消同事务停止 QUEUED 运行；
- 资源检查只读查询不要求 CSRF；
- 真实 CSV 后台生成、摘要、BOM 和下载；
- Cookie/CSRF、退出撤销、本人停用保护、未登录不泄露实体。

前端回归与构建：

```bash
cd frontend
npm test
npm run build
npm run build:http
```

## 11. 已知未完成项

- 未实现生产设备适配器、可靠 outbox 发送器、迟到反馈对账、自动告警与自动计量结算；需要厂家协议、点表、现场保护和联动签核后才能实现和验收。
- 未实现基准写入口、二维码服务和账号注册/找回口令页面，与需求文档第一版范围一致。
- SSE 是单进程内存广播；多实例部署需要外接消息总线或共享通知表。
- 导出任务在 API 进程内分批生成；当前数据规模可直接使用，超大报表可再拆到 worker 进程。
