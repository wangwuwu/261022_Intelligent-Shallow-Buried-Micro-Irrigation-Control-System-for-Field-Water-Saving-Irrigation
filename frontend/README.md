# 智能节水灌溉管控系统前端

当前交付是 Vue 3 + Vite 本机预览版。数据保存在当前浏览器的本地快照中；尚未连接后端、数据库或现场设备控制服务。

## 安装和运行

需要 Node.js 24 和 npm。首次安装依赖：

```bash
cd frontend
npm ci
```

本机预览账号由已有启用用户使用，例如管理员账号 `zyq.admin`。首次运行前在交互终端为该账号自行设置预览口令：

```bash
npm run preview:credentials
```

脚本提示输入共享数据中已有的账号和口令两次；口令输入不回显，长度为8至128个字符。不要把口令放进命令行参数、源码或共享文档。工具只在`frontend/.local/preview-credentials.json`保存随机盐和PBKDF2摘要；该文件已排除在Git之外，不包含角色、农场授权、会话或明文口令。它只供本机预览使用，不是生产认证。

启动开发预览：

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

浏览器打开Vite打印的本机地址并登录。需要换端口时，浏览器会把它视为不同origin，旧预览快照仍留在原origin；返回原端口即可继续查看原数据。

## 构建和本机构建预览

静态预览构建会在构建时读取本机预览凭据；请先按上面的步骤设置所需账号，再执行构建。新增或修改预览凭据后，需要重新构建才能更新静态预览。

```bash
npm run build
npm run preview -- --host 127.0.0.1 --port 4173 --strictPort
```

`npm run build`生成`frontend/dist/`。静态构建仍使用本机预览仓储；生成生产文件不代表后端或现场控制已经实现。

## 浏览器验证

从没有QA口令文件的工作区复现验证：

1. 在终端A为共享用户设置本机预览口令。管理员、只读人员和技术员都要各运行一次命令；账号从项目根目录`shared_context.json`的`User`实体中选择，且状态必须是`ENABLED`：

   ```bash
   cd frontend
   npm run preview:credentials
   ```

   该终端工具逐次询问一个账号，并两次隐藏输入口令。为`ADMIN`、`VIEWER`、`TECHNICIAN`各选一个启用账号，重复运行三次。账号摘要保存在`frontend/.local/preview-credentials.json`，明文口令不写入文件。这个凭据准备步骤必须在运行浏览器验证之前单独完成。

2. 在终端A启动Vite预览：

   ```bash
   npm run dev -- --host 127.0.0.1 --port 5173
   ```

3. 在终端B安装Python Playwright及Chromium：

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

4. 在终端B从项目根目录运行验证。没有自动化凭据文件时，脚本按共享用户角色提示输入三个已设置预览口令；输入使用`getpass`隐藏，仅保留在该进程内存中：

```bash
python3 scripts/validate_frontend.py --base-url http://127.0.0.1:5173
```

如果本机 HTTP 代理使浏览器无法访问 `127.0.0.1`，请调整代理绕过设置，或在本次验证命令前临时清除代理变量：

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy python3 scripts/validate_frontend.py --base-url http://127.0.0.1:5173
```

脚本优先读取已存在的自动化QA凭据文件；若无该文件且没有交互终端，会打印上述准备步骤并以非零状态退出。脚本本身不会创建、保存或删除QA口令文件，也不会更改`preview-credentials.json`。验证在独立、一次性Chromium context中以1536×1024、DPR 1、zh-CN和Asia/Shanghai运行，不读取或更改用户浏览器localStorage。`validation/reference-inputs.sha256`中的原始输入会在运行前后复核。截图、步骤结果和机器JSON写入`validation/`；导出CSV只在系统临时目录检查后删除。

没有交互终端时，请在另一个真实终端完成第1步，再从交互终端运行脚本；不要把口令放入命令行参数、环境变量、README或源码。

截图验证URL使用`?reference=1`固定只读展示时钟和参考初始筛选，仓储键为`irrigation.reference.*`，与普通预览的`irrigation.preview.*`分开。自动验证使用临时浏览器context，完成后该context销毁。不要把截图验证profile用于真实业务数据。

## 数据和账号边界

- 前端初始业务实体只读取项目根目录`shared_context.json`中的entities。业务写入进入浏览器localStorage中的本机快照，不改写共享输入文件。
- 普通预览和参考截图使用不同的localStorage键。浏览器存储按scheme、host和port隔离；换端口不会自动带走旧端口的快照。恢复普通预览数据时请使用原来的预览URL。
- 本机账号摘要配置与业务实体快照分开保存。新增或修改用户不会自动设置登录口令；要让某个已有账号登录本机预览，需再次运行凭据准备命令为该账号设置摘要。
- 更换代码、浏览器profile、origin或数据通道时，不会自动迁移本机业务修改。不要手动把`irrigation.preview.*`或`irrigation.reference.*`数据复制到服务端。
- `npm run dev:http`是预留的HTTP通道入口。后端尚未接入时，界面会报告正式数据服务不可用，不回退到本机快照。
- 运行控制、设备核验和硬件反馈没有生产适配器；页面显示拒绝或未连接不表示现场执行。正式服务端鉴权、数据库持久化、跨设备联调和生产控制尚待后续阶段。

## 常用命令

```bash
npm test
npm run build
```

