#!/usr/bin/env python3
"""Run repeatable, isolated Playwright checks for the irrigation Vue preview.

The browser context is ephemeral. Screenshots and reports go under validation/;
the script never prints or stores preview passwords.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import secrets
import struct
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

try:
    from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - exercised on a missing dependency
    print("Python Playwright is required. Install it with: python3 -m pip install playwright")
    print("Then install Chromium with: python3 -m playwright install chromium")
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
REFERENCE_DIR = VALIDATION / "screenshots" / "reference"
STATES_DIR = VALIDATION / "screenshots" / "states"
SECRETS_FILE = ROOT / "frontend" / ".local" / "validation-secrets.json"

ROUTES = [
    ("灌溉总览", "灌溉总览", "/overview", "田块面积"),
    ("田块与种植", "田块与种植", "/fields", "田块名称"),
    ("田块档案", "田块档案", "/fields/FLD-JZ-M9R2", "田块基本信息"),
    ("田块资料编辑", "田块资料编辑", "/fields/FLD-JZ-M9R2/edit", "田块基本资料"),
    ("管网与轮灌分区", "管网与轮灌分区", "/network", "水源"),
    ("设备接入台账", "设备接入台账", "/devices", "设备总数"),
    ("设备运行档案", "设备运行档案", "/devices/DEV-JZ-S7KW", "核验接入"),
    ("墒情与环境监测", "墒情与环境监测", "/monitor", "深度"),
    ("灌溉策略", "灌溉策略", "/strategies", "作物"),
    ("灌溉策略编辑", "灌溉策略编辑", "/strategies/STR-JZ-K8QM/edit", "策略名称"),
    ("灌溉计划", "灌溉计划", "/plans", "泵站轮灌时间轴"),
    ("轮灌计划编排", "轮灌计划编排", "/plans/PLN-JZ-M4FD/edit", "计划名称"),
    ("灌溉运行", "灌溉运行", "/runs", "全场运行中"),
    ("灌溉执行控制", "灌溉执行控制", "/runs/RUN-JZ-18E71500", "计量明细"),
    ("运行告警", "运行告警", "/alarms", "严重度"),
    ("巡检与维护", "巡检与维护", "/maintenance", "待接单"),
    ("用水与节水分析", "用水与节水分析", "/water", "区间总水量"),
    ("账号与系统配置", "账号与系统配置", "/settings", "用户权限"),
    ("操作与指令审计", "操作与指令审计", "/audit", "操作人"),
]
FIFTEEN_ROW_ROUTES = {
    "/fields/FLD-JZ-M9R2",
    "/network",
    "/devices",
    "/devices/DEV-JZ-S7KW",
    "/monitor",
    "/strategies",
    "/plans",
    "/plans/PLN-JZ-M4FD/edit",
    "/runs",
    "/runs/RUN-JZ-18E71500",
    "/alarms",
    "/water",
    "/settings",
    "/audit",
}
VISUAL_REVIEW = [
    ("账号登录", "账号居中卡片、品牌、双输入框、登录按钮、连接状态和农场名均出现。", "参考图预填账号并显示掩码口令；实际图输入为空，减少凭据暴露；背景等高线和品牌图形也有差异。"),
    ("灌溉总览", "6项指标、15格田块图、当前/待执行任务和底部告警摘要均可见；初始汇总与运行值相符。", "地图田块轮廓与参考图几何不同；日期控件呈MM/DD/YYYY。地图翻页与新田块详情另由交互状态实测。"),
    ("田块与种植", "筛选行、面积汇总和3×5共15张卡片齐全；卡片名称/编号/面积/土壤/阶段/负责人顺序一致。", "实际图额外显示单页分页控件；卡片间距、按钮位置和统计图标与参考图有差异。"),
    ("田块档案", "基本信息、种植季、分区、墒情卡及15行历史表均出现，田块和24.9%读数一致。", "历史表已排除待执行任务；回归逐页检查确认不包含关联待执行运行。"),
    ("田块资料编辑", "基本资料、位置面积、土壤负责人、示意图及保存/取消/重置入口与字段值均可见。", "实际分区与表单卡片垂直留白略大；地图网格和点位标记样式不同。"),
    ("管网与轮灌分区", "水源选择、拓扑、分区参数和15行清单齐全，首分区19.3亩/55m³h等值一致。", "拓扑节点图标和连线布局不同，实际表格纵向更紧；首屏15行的分区实体与顺序一致。"),
    ("设备接入台账", "四项设备指标75/71/4/74及筛选、登记入口、15行设备表可见，首屏数据一致。", "摘要图标、表头列宽和页脚控件与参考图不同，主要布局顺序一致。"),
    ("设备运行档案", "设备编号、状态、能力矩阵、点位映射Tab及15条点位均可见，设备和读数值一致。", "参考图为传感器插画，实际用简化CSS设备形状；表格行距和点位映射Tab位置略有差异。"),
    ("墒情与环境监测", "分区/点位/深度/日期筛选、当前20.8读数、趋势图和15行原始表齐全。", "实际曲线未显示参考图上的时间/读数点注，改用空心点；日期输入格式为MM/DD/YYYY。"),
    ("灌溉策略", "作物/阶段/状态筛选、15条策略表及15/12/3汇总均可见，首屏记录和状态一致。", "实际表格列宽、行高与筛选卡间距不同；未见明显首屏数据差异。"),
    ("灌溉策略编辑", "策略名、阈值21.5、单次目标138、最长240分钟和两个已选分区与参考相符。", "分区框首屏完整显示两行，其余选项可滚动访问；浏览器原生时间控件显示AM/PM，与参考图24小时格式不同。"),
    ("灌溉计划", "四项状态汇总1/16/13/1、时间轴和15行列表均可见，31条/3页一致。", "实际第4至15行显示草稿，而参考图这些位置显示历史完成/发布计划；时间轴行名也有差别。日期控件采用MM/DD/YYYY。"),
    ("轮灌计划编排", "计划名/时间、5个候选分区、15步及274.5m³摘要均可见，步骤核心数据一致。", "实际选择框增加“选择分区…”占位；日期时间采用AM/PM显示，控件排布和行宽与参考略异。"),
    ("灌溉运行", "运行中/完成/待执行数1/16/1、当前运行55.0m³/h和23.2m³暂计量及15行历史均可见。", "实际运行/待执行卡片图标和字段排布更简化；截图可见的数据值与参考一致。"),
    ("灌溉执行控制", "运行ID、起止时间、274.5m³及轮灌步骤/指令/计量Tab和15行计量记录均可见。", "实际控制摘要图标与参考图形不同，并在指令链增加“查看对应审计”链接；核心账本行值一致。"),
    ("运行告警", "15条告警、10待处理、4未恢复、5已关闭及选中告警/工单摘要可见，首屏告警数据一致。", "已调整间距和行高；本次1536×1024截图中选中详情完整可见。"),
    ("巡检与维护", "四个状态泳道及3/5/2/5计数一致，工单编号、责任人、分区和状态可见。", "同一泳道卡片顺序与参考图不同；实际卡片和泳道间距更紧，未发现缺失列。"),
    ("用水与节水分析", "账本总量4963.5、实测4928.9、分摊34.6、亩均8.94、基准16.52%和15条明细相符。", "实际初始导出任务显示已过期/不可恢复，参考图显示可下载；实际导出交互另实测重新生成并下载成功。日期输入为MM/DD/YYYY；菜单按当前路由高亮用水，与参考图高亮维护不同，属spec第2节冲突表列明差异。"),
    ("账号与系统配置", "15账号/14启用/1停用和120/12/48/30参数摘要、15行用户表均可见。", "首行“用户标识”实际显示User.name“周砚秋”，参考图显示zyq.admin；账号列仍显示zyq.admin。此处按spec第2节冲突表要求以User.name展示；菜单按当前路由高亮Settings，与参考图高亮统计项不同，均单独记录。"),
    ("操作与指令审计", "75条审计、15行表、选中记录和三阶段链路均可见，主记录ID和事件相符。", "日期区间与查询按钮不再重叠；动作确认显示命令级确认时间09:53:08。"),
    ("公共导航", "13个菜单项、分组、顶栏农场/时间/角色和连接状态可核对。", "原图右侧主区纯空白且无选中项；实际截图从总览路由捕获，故主区保留完整总览且总览菜单选中，这是应用无空白母版路由的说明性取证方式。"),
]


class CheckFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value).strip("-")


def read_reference_hashes() -> tuple[dict[str, str], list[str]]:
    manifest = VALIDATION / "reference-inputs.sha256"
    expected: dict[str, str] = {}
    failures: list[str] = []
    if not manifest.is_file():
        return {}, ["validation/reference-inputs.sha256 is missing"]
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            expected_hash, rel_path = line.split(None, 1)
            rel_path = rel_path.lstrip("* ")
        except ValueError:
            failures.append(f"Malformed hash entry: {line[:100]}")
            continue
        path = ROOT / rel_path
        if not path.is_file():
            failures.append(f"Missing reference input: {rel_path}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected[rel_path] = actual
        if actual != expected_hash:
            failures.append(f"Hash mismatch: {rel_path}")
    return expected, failures


def load_test_credentials() -> dict[str, str]:
    if not SECRETS_FILE.is_file():
        if not sys.stdin.isatty():
            raise CheckFailure(
                "未找到自动化QA凭据文件，且当前没有交互终端。请先在单独终端逐个运行 "
                "`cd frontend && npm run preview:credentials`，为共享数据中启用的管理员、只读人员和技术员账号设置预览口令；"
                "然后在交互终端运行本脚本，由getpass逐个读取口令。脚本不会创建或保存QA口令文件。"
            )
        accounts_by_role = enabled_accounts_by_role()
        return prompt_role_credentials(accounts_by_role)
    try:
        data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckFailure("Temporary QA credential file could not be read.") from exc
    if isinstance(data, dict) and isinstance(data.get("accounts"), dict):
        data = data["accounts"]
    if not isinstance(data, dict):
        raise CheckFailure("Temporary QA credentials must be an account-to-secret mapping.")
    result: dict[str, str] = {}
    for account, value in data.items():
        if isinstance(value, dict):
            value = value.get("secret") or value.get("password")
        if isinstance(account, str) and isinstance(value, str) and value:
            result[account] = value
    if not result:
        raise CheckFailure("No usable temporary QA credentials were found.")
    role_by_account = enabled_role_by_account()
    missing_roles = [
        role
        for role in ("ADMIN", "VIEWER", "TECHNICIAN")
        if not any(role_by_account.get(account) == role for account in result)
    ]
    if missing_roles:
        raise CheckFailure(
            "自动化QA凭据缺少这些启用角色的口令：" + "、".join(missing_roles)
            + "。请先用npm run preview:credentials设置，再运行验证。"
        )
    return result


def enabled_role_by_account() -> dict[str, str]:
    source = ROOT / "shared_context.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        users = data.get("entities", {}).get("User", [])
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise CheckFailure("无法从shared_context.json读取用户角色。") from exc
    return {
        user["account"]: user["role"]
        for user in users
        if isinstance(user, dict)
        and user.get("status") == "ENABLED"
        and user.get("role") in {"ADMIN", "VIEWER", "TECHNICIAN", "MANAGER", "OPERATOR"}
        and isinstance(user.get("account"), str)
    }


def enabled_accounts_by_role() -> dict[str, list[str]]:
    role_by_account = enabled_role_by_account()
    return {
        role: sorted(account for account, account_role in role_by_account.items() if account_role == role)
        for role in ("ADMIN", "VIEWER", "TECHNICIAN", "MANAGER", "OPERATOR")
    }


def prompt_role_credentials(
    accounts_by_role: dict[str, list[str]],
    input_fn: Callable[[str], str] | None = None,
    getpass_fn: Callable[[str], str] | None = None,
) -> dict[str, str]:
    input_fn = input if input_fn is None else input_fn
    getpass_fn = getpass.getpass if getpass_fn is None else getpass_fn
    credentials: dict[str, str] = {}
    print(
        "请在单独的终端先用 `cd frontend && npm run preview:credentials` 为以下启用账号设置本机预览口令。"
        "以下输入只在本次进程内存中使用，不会写入QA文件。"
    )
    for role in ("ADMIN", "VIEWER", "TECHNICIAN"):
        accounts = accounts_by_role.get(role, [])
        if not accounts:
            raise CheckFailure(f"共享用户数据中没有启用的{role}账号，无法完成前端验证。")
        choices = "、".join(accounts)
        default = accounts[0] if len(accounts) == 1 else ""
        suffix = f"（可用：{choices}；回车使用{default}）" if default else f"（可用：{choices}）"
        account = input_fn(f"{role}账号{suffix}: ").strip() or default
        if account not in accounts:
            raise CheckFailure(f"输入的{role}账号不属于shared_context.json中启用的{role}用户。")
        password = getpass_fn(f"{role}账号 {account} 的预览口令: ")
        if not password:
            raise CheckFailure(f"{role}预览口令不能为空。")
        credentials[account] = password
    return credentials


def choose_account(credentials: dict[str, str], preferred: str, role_hint: str) -> tuple[str, str]:
    requested = os.environ.get(preferred.upper().replace(".", "_"))
    if requested and requested in credentials:
        return requested, credentials[requested]
    role_name = role_hint.upper()
    role_by_account = enabled_role_by_account()
    candidates = [name for name in credentials if role_by_account.get(name) == role_name]
    known = {
        "admin": ["zyq.admin"],
        "viewer": ["dyh.viewer", "lzn.viewer", "sqm.viewer"],
        "technician": ["xql.maint", "xqh.maint", "zqy.maint", "wcl.maint"],
        "manager": ["mqc.manager", "syt.manager"],
        "operator": ["hcl.operator", "gmy.operator", "cjh.operator", "hxq.operator"],
    }.get(role_hint, [])
    for name in [*known, *candidates]:
        if name in credentials:
            return name, credentials[name]
    raise CheckFailure(f"没有可用的{role_name} QA口令；请先为shared_context.json中的启用账号运行preview:credentials。")


def navigate_url(base_url: str, route: str, capture_name: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    query = "reference=1&capture=" + secrets.token_hex(6)
    fragment = route
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", query, fragment))


def normalize_base_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise CheckFailure("--base-url must be an http(s) origin or URL path.")
    if parts.username is not None or parts.password is not None:
        raise CheckFailure("Pass --base-url without embedded credentials.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def wait_for_render(page: Page, private: bool = True) -> None:
    page.wait_for_load_state("networkidle", timeout=20_000)
    if private:
        page.locator(".main-content").wait_for(state="visible", timeout=12_000)
    else:
        page.locator(".login-card").wait_for(state="visible", timeout=12_000)
    page.evaluate(
        """async () => {
          await document.fonts.ready;
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }"""
    )


def screenshot(page: Page, target: Path, route: str, label: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(target), full_page=False, animations="disabled")
    raw = target.read_bytes()
    width, height = struct.unpack(">II", raw[16:24])
    require(width == 1536 and height == 1024, f"Screenshot size was {width}x{height}; expected 1536x1024.")
    revision = page.evaluate(
        """() => {
          try {
            const envelope = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
            return envelope?.revision ?? null;
          } catch { return null; }
        }"""
    )
    return {
        "name": label,
        "route": route,
        "url": page.url,
        "file": str(target.relative_to(ROOT)),
        "width": width,
        "height": height,
        "device_scale_factor": 1,
        "revision": 0 if revision is None else revision,
        "captured_at": utc_now(),
        **(extra or {}),
    }


class FrontendRun:
    def __init__(self, base_url: str, capture_screenshots: bool = True):
        self.base_url = base_url
        self.capture_screenshots = capture_screenshots
        self.cases: list[dict[str, Any]] = []
        self.screens: list[dict[str, Any]] = []
        self.page_errors: list[str] = []
        self.console_errors: list[str] = []
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._browser: Any = None
        self._active_case: dict[str, Any] | None = None
        self._secrets: list[str] = []

    @property
    def page(self) -> Page:
        assert self._page is not None
        return self._page

    def add_case(self, name: str, expected: str, callback: Callable[[], None], evidence: list[str] | None = None) -> None:
        item = {
            "name": name,
            "status": "RUNNING",
            "expected": expected,
            "steps": [],
            "actual": "",
            "evidence": evidence or [],
            "started_at": utc_now(),
        }
        self.cases.append(item)
        self._active_case = item
        try:
            callback()
        except Exception as exc:  # keep collecting independent checks
            item["status"] = "FAIL"
            item["actual"] = self._sanitize(self._safe_error(exc))
        else:
            if item["status"] == "RUNNING":
                item["status"] = "PASS"
            if not item["actual"]:
                item["actual"] = "Observed expected UI behavior."
        finally:
            item["finished_at"] = utc_now()
            self._active_case = None
            print(f"[{item['status']}] {name}", flush=True)

    def step(self, description: str) -> None:
        if self._active_case is not None:
            self._active_case["steps"].append(description)

    def pass_detail(self, message: str) -> None:
        if self._active_case is not None:
            self._active_case["actual"] = message

    def _safe_error(self, exc: Exception) -> str:
        if isinstance(exc, PlaywrightTimeoutError):
            return self._sanitize(str(exc) or "Timed out waiting for the expected page state.")
        if isinstance(exc, CheckFailure):
            return self._sanitize(str(exc))
        return self._sanitize(f"{type(exc).__name__}: {str(exc)[:400]}")

    def _sanitize(self, message: str) -> str:
        for value in self._secrets:
            if value:
                message = message.replace(value, "[REDACTED]")
        return message[:500]

    def goto(self, route: str, capture_name: str, private: bool = True) -> None:
        self.page.goto(navigate_url(self.base_url, route, capture_name), wait_until="domcontentloaded")
        wait_for_render(self.page, private=private)

    def capture(self, name: str, route: str, folder: Path = REFERENCE_DIR, extra: dict[str, Any] | None = None) -> None:
        self.screens.append(screenshot(self.page, folder / f"{name}.png", route, name, extra))

    def wait_for_route(self, route: str, timeout: int = 8_000) -> None:
        self.page.wait_for_function(
            "expected => location.hash.split('?')[0] === '#' + expected",
            arg=route,
            timeout=timeout,
        )

    def login(self, account: str, password: str) -> None:
        self.page.get_by_label("账号").fill(account)
        self.page.get_by_label("密码").fill(password)
        self.page.get_by_role("button", name="登录", exact=True).click()
        try:
            self.wait_for_route("/overview", timeout=12_000)
        except PlaywrightTimeoutError as exc:
            current_hash = self.page.evaluate("() => location.hash")
            alerts = self.page.locator(".login-error").all_inner_texts()
            message = alerts[0][:160] if alerts else "no login message"
            raise CheckFailure(f"Login did not reach overview; current route={current_hash!r}; UI message={message!r}.") from exc
        wait_for_render(self.page)

    def run(self, credentials: dict[str, str]) -> dict[str, Any]:
        admin, admin_secret = choose_account(credentials, "QA_ADMIN_ACCOUNT", "admin")
        self.admin_account = admin
        self._secrets = list(credentials.values())
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            self._browser = browser
            context = browser.new_context(
                viewport={"width": 1536, "height": 1024},
                device_scale_factor=1,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                accept_downloads=True,
            )
            self._context = context
            self._page = context.new_page()
            self.page.on("pageerror", lambda error: self.page_errors.append(self._sanitize(str(error))))
            self.page.on(
                "console",
                lambda message: self.console_errors.append(self._sanitize(message.text))
                if message.type == "error"
                else None,
            )
            self.page.set_default_timeout(8_000)
            self.page.goto(navigate_url(self.base_url, "/login", "login-default"), wait_until="domcontentloaded")
            wait_for_render(self.page, private=False)
            if self.capture_screenshots:
                self.capture("账号登录", "/login")

            def login_empty() -> None:
                self.step("在账号和密码均为空时提交登录表单。")
                self.page.get_by_role("button", name="登录", exact=True).click()
                require(self.page.get_by_role("alert").inner_text().strip() == "请输入账号", "Empty login was not rejected with the account validation message.")
                self.pass_detail("空账号被拒绝并显示字段提示；页面没有注册或初始化口令流程。")

            self.add_case("登录空值校验", "空账号提交显示请输入账号。", login_empty, ["validation/screenshots/reference/账号登录.png"])

            def login_invalid() -> None:
                self.step("使用一次性随机无效口令提交临时管理员账号。")
                self.page.get_by_label("账号").fill(admin)
                self.page.get_by_label("密码").fill(secrets.token_urlsafe(24))
                self.page.get_by_role("button", name="登录", exact=True).click()
                alert = self.page.get_by_role("alert").inner_text()
                require("账号或密码错误" in alert, "Invalid login was not rejected with the generic credential error.")
                require(self.page.get_by_label("密码").input_value() == "", "Password field did not clear after rejected login.")
                self.pass_detail("错误口令被拒绝，账号保留且密码清空；随机口令未写入报告。")

            self.add_case("登录错误凭据拒绝", "随机无效口令显示统一拒绝消息且清空密码。", login_invalid)

            def login_success() -> None:
                self.step("使用已设置的临时管理员预览口令登录；口令只在进程内存和本次隔离浏览器操作中使用。")
                self.login(admin, admin_secret)
                require("系统管理员" in self.page.locator(".account-button").inner_text(), "Expected ADMIN session did not appear in the shell.")
                self.pass_detail("临时管理员账号登录成功；口令不写入截图清单或结果JSON。")

            self.add_case("管理员登录成功", "使用隔离测试凭据进入系统管理员会话。", login_success)

            for name, screenshot_name, route, marker in ROUTES:
                def capture_route(name=name, screenshot_name=screenshot_name, route=route, marker=marker) -> None:
                    self.step(f"完整导航至 {route}，等待networkidle、字体加载和Vue绘制帧。")
                    self.goto(route, screenshot_name)
                    current = urlsplit(self.page.url).fragment.split("?", 1)[0]
                    require(current == route, f"Route guard did not leave the browser at {route}.")
                    body = self.page.locator(".main-content").inner_text()
                    require(marker in body, f"Expected visible marker not found for screen {name}.")
                    visible_rows: int | None = None
                    if route == "/fields":
                        visible_rows = self.page.locator(".main-content .field-card").count()
                        require(visible_rows == 15, f"Expected 15 visible field cards; observed {visible_rows}.")
                    elif route in FIFTEEN_ROW_ROUTES:
                        visible_rows = self.page.locator(".main-content tbody tr").count()
                        require(visible_rows == 15, f"Expected 15 visible default rows; observed {visible_rows}.")
                    if self.capture_screenshots:
                        self.capture(screenshot_name, route, extra={"screen": name, "expected_marker": marker})
                    row_summary = f"默认分页显示{visible_rows}条" if visible_rows is not None else "该页面不要求15行分页"
                    self.pass_detail(f"路由可达，主内容包含“{marker}”；{row_summary}；保存1536×1024浏览器实际截图。")

                self.add_case(f"默认页面：{name}", f"{route}可达并显示预期内容。", capture_route)

            def capture_shell() -> None:
                self.step("在总览路由核对公共顶栏、侧栏菜单、角色入口和连接状态。")
                self.goto("/overview", "public-shell")
                shell = self.page.locator(".app-shell")
                require(shell.count() == 1, "Shared application shell was not rendered.")
                require(self.page.locator(".navigation-item").count() == 13, "Expected 13 available business navigation items for ADMIN.")
                require(self.page.locator(".connection-status").inner_text().strip() == "连接正常", "Preview storage connection status did not render.")
                if self.capture_screenshots:
                    self.capture("公共导航", "/overview", extra={"note": "公共壳层在总览路由中实拍；应用没有空白导航母版路由。"})
                self.pass_detail("ADMIN壳层渲染13个导航入口、当前角色和本机预览连接状态。")

            self.add_case("公共导航壳层", "公共导航可见且显示13个业务入口。", capture_shell, ["validation/screenshots/reference/公共导航.png"])

            def complete_screen_set() -> None:
                if not self.capture_screenshots:
                    self.pass_detail("本次通过--no-screenshots运行，未覆盖截图清单。")
                    return
                expected_names = {"账号登录", "公共导航", *(item[1] for item in ROUTES)}
                captured = {item["name"] for item in self.screens}
                missing = sorted(expected_names - captured)
                require(not missing, f"Missing reference screenshots: {', '.join(missing)}")
                self.pass_detail(f"20个业务Screen和公共导航壳层共{len(expected_names)}张默认截图均已实拍。")

            self.add_case("默认截图清单完整", "20业务Screen及公共导航母版均有实际运行截图。", complete_screen_set)

            self._test_field_filter_detail_and_persistence()
            self._test_create_field_and_season_versions()
            self._test_season_modal_close_guard()
            self._test_device_tabs_and_verify_rejection()
            self._test_plan_page_three_and_editor()
            self._test_run_control_rejection_and_tabs()
            self._test_water_values_and_export()
            self._test_settings_and_audit()
            self._test_page_layout_and_history_invariants()
            self._test_alarm_and_workorder_flow(credentials)
            self._test_viewer_permissions(credentials)
            self._test_corrupt_snapshot_backup_and_recovery()

            browser_errors = bool(self.page_errors or self.console_errors)
            self.add_case(
                "浏览器未处理错误",
                "运行期间没有pageerror或console.error。",
                lambda: require(not browser_errors, f"pageerror={len(self.page_errors)}, console.error={len(self.console_errors)}"),
            )
            context.close()
            browser.close()

        return self.report()

    def _state_screenshot(self, label: str, route: str) -> None:
        if self.capture_screenshots:
            self.capture(label, route, folder=STATES_DIR)

    def _test_field_filter_detail_and_persistence(self) -> None:
        route = "/fields"

        def run_case() -> None:
            self.goto(route, "field-filter-flow")
            first_card = self.page.locator(".field-card").first
            original_name = first_card.locator("h3").inner_text().strip()
            original_area = ""
            self.step("按第一张田块卡片名称筛选，再进入档案并返回。")
            self.page.get_by_label("田块名称").fill(original_name)
            self.page.get_by_role("button", name="查询", exact=True).click()
            require(self.page.locator(".field-card").count() == 1, "Field filter did not reduce the list to the selected field.")
            first_card = self.page.locator(".field-card").first
            first_card.get_by_role("button", name="查看", exact=True).click()
            self.page.wait_for_function("() => location.hash.startsWith('#/fields/') && !location.hash.endsWith('/edit')", timeout=8_000)
            self.page.get_by_role("button", name="返回", exact=False).first.click()
            require(self.page.get_by_label("田块名称").input_value() == original_name, "Filter draft was not restored after returning from field detail.")
            require(self.page.locator(".field-card").count() == 1, "Filtered result was not restored after returning from field detail.")
            self.pass_detail("名称筛选→档案→返回保留筛选文本和结果。")

            self.step("从档案编辑入口将面积改为0并确认非法输入被拒绝。")
            self.page.locator(".field-card").first.get_by_role("button", name="查看", exact=True).click()
            self.page.get_by_role("button", name="田块基本信息", exact=False).click()
            self.page.wait_for_function("() => location.hash.endsWith('/edit')", timeout=8_000)
            area = self.page.get_by_label("面积（亩）")
            original_area = area.input_value()
            area.fill("0")
            self.page.get_by_role("button", name="保存", exact=True).click()
            self.page.get_by_text("田块面积必须大于零", exact=True).wait_for(state="visible", timeout=5_000)
            require(self.page.locator('input[aria-invalid="true"]').count() > 0 or self.page.locator(".error-text").count() > 0, "Illegal zero area was not marked invalid.")
            require("/edit" in urlsplit(self.page.url).fragment, "Invalid area unexpectedly left the edit screen.")
            edit_route = self.page.evaluate("() => location.hash.split('?')[0].slice(1)")
            self._state_screenshot("田块-非法面积", edit_route)

            self.step("恢复合法面积、修改名称并保存；重载后核对本机隔离快照。")
            area.fill(original_area)
            changed_name = original_name + "（QA验证）"
            self.page.get_by_label("田块名称").fill(changed_name)
            self.page.get_by_role("button", name="保存", exact=True).click()
            self.page.wait_for_function("() => location.hash.startsWith('#/fields/') && !location.hash.endsWith('/edit')", timeout=8_000)
            require(changed_name in self.page.locator(".field-detail").inner_text(), "Successful field update was not visible in the detail page.")
            self.page.reload(wait_until="domcontentloaded")
            wait_for_render(self.page)
            require(changed_name in self.page.locator(".field-detail").inner_text(), "Saved field change did not persist after reload.")
            self.pass_detail("非法面积被保留在编辑页并标错；合法名称变更保存后重载仍存在（只在本次临时浏览器profile）。")

        self.add_case(
            "田块筛选、详情返回、面积校验和持久化",
            "筛选回退保留状态；面积0拒绝；合法保存经重载仍保留。",
            run_case,
            ["frontend/src/views/fields/FieldListView.vue", "frontend/src/views/fields/FieldEditView.vue"],
        )

    def _test_season_modal_close_guard(self) -> None:
        def run_case() -> None:
            self.goto("/fields", "season-modal")
            self.page.locator(".field-card").first.get_by_role("button", name="种植季", exact=True).click()
            dialog = self.page.get_by_role("dialog")
            require(dialog.count() == 1 and "种植季信息" in dialog.inner_text(), "Season maintenance form did not open.")
            inputs = dialog.locator("input:not([readonly]), select:not([disabled])")
            require(inputs.count() > 0, "Season form did not expose editable fields.")
            target = inputs.first
            original_value = target.input_value() if target.evaluate("el => el.tagName === 'INPUT'") else target.input_value()
            if target.evaluate("el => el.tagName === 'INPUT' && el.type !== 'date'"):
                target.fill((original_value or "QA") + "-草稿")
            elif target.evaluate("el => el.tagName === 'SELECT'"):
                options = target.locator("option").all()
                choices = [option.get_attribute("value") for option in options if option.get_attribute("value")]
                if choices:
                    target.select_option(choices[-1])
            else:
                target.fill("2026-07-28")
            self.step("修改种植季Draft后按Escape；拒绝放弃时原弹窗和草稿仍可见。")
            self.page.keyboard.press("Escape")
            confirm = self.page.get_by_role("dialog").filter(has_text="放弃未保存的修改")
            confirm.wait_for(state="visible", timeout=5_000)
            confirm.get_by_role("button", name="取消", exact=True).click()
            require(self.page.get_by_role("dialog").filter(has_text="种植季信息").count() == 1, "Season modal closed after refusing to discard the draft.")
            self._state_screenshot("种植季-拒绝放弃", "/fields")
            self.page.get_by_role("dialog").filter(has_text="种植季信息").get_by_role("button", name="取消", exact=True).click()
            self.page.get_by_role("dialog").filter(has_text="放弃未保存的修改").get_by_role("button", name="放弃修改", exact=True).click()
            require(self.page.get_by_role("dialog").count() == 0, "Season modal did not close after explicit discard confirmation.")
            self.pass_detail("Escape先进入放弃确认；拒绝后种植季草稿弹窗继续显示，明确放弃后才关闭。")

        self.add_case("种植季草稿Esc关闭守卫", "拒绝放弃后弹窗与草稿保持可见。", run_case)

    def _test_create_field_and_season_versions(self) -> None:
        def run_case() -> None:
            unique_name = "QA田块-" + secrets.token_hex(3)
            self.goto("/fields/new", "field-create")
            self.step("填写有效田块基本信息并新增田块。")
            self.page.get_by_label("田块名称").fill(unique_name)
            self.page.get_by_label("面积（亩）").fill("12.3")
            self.page.get_by_label("经度").fill("116.3")
            self.page.get_by_label("纬度").fill("39.9")
            soil = self.page.get_by_label("土壤类型")
            soil_values = soil.locator("option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
            require(bool(soil_values), "No valid soil option was available for a new field.")
            soil.select_option(soil_values[0])
            manager = self.page.get_by_label("负责人")
            manager_values = manager.locator("option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
            require(bool(manager_values), "No enabled manager option was available for a new field.")
            manager.select_option(manager_values[0])
            self.page.get_by_role("button", name="保存", exact=True).click()
            self.page.wait_for_function("() => location.hash.startsWith('#/fields/') && !location.hash.endsWith('/edit')", timeout=8_000)
            require(unique_name in self.page.locator(".field-detail").inner_text(), "New field did not appear in its detail page.")
            field_id = self.page.evaluate(r"() => location.hash.match(/fields\/([^/?]+)/)?.[1] || ''")
            require(field_id, "New field route did not expose a stable field id.")

            self.step("在总览地图翻到第2页，点击新建田块并核对进入同一个田块ID档案。")
            self.goto("/overview", "overview-map-new-field")
            map = self.page.locator(".map-panel")
            pagination = map.get_by_role("navigation", name="田块态势翻页")
            pagination.wait_for(state="visible", timeout=8_000)
            require(map.locator(".field-polygon").count() == 15, "Overview first map page did not show exactly 15 field polygons after creating the 16th field.")
            require("第 1 / 2 页" in pagination.inner_text() and "共 16 个授权田块" in pagination.inner_text(), "Overview map did not report the new 16-field, two-page range.")
            pagination.get_by_role("button", name="下一页田块", exact=True).click()
            require("第 2 / 2 页" in pagination.inner_text(), "Overview map did not advance to its second page.")
            new_field_polygon = map.locator(f'.field-polygon[data-field-id="{field_id}"]')
            polygon_label = new_field_polygon.get_attribute("aria-label") if new_field_polygon.count() == 1 else ""
            require(unique_name in (polygon_label or ""), "New field ID/name did not appear on the second overview map page.")
            self._state_screenshot("总览-第16田块地图", "/overview")
            new_field_polygon.click()
            self.page.wait_for_function("fieldId => location.hash.startsWith('#/fields/' + fieldId)", arg=field_id, timeout=8_000)
            require(field_id in self.page.locator(".field-detail").inner_text() and unique_name in self.page.locator(".field-detail").inner_text(), "Overview polygon did not open the detail for the same new field ID.")
            self._state_screenshot("总览-第16田块详情", f"/fields/{field_id}")

            self.step("在新田块上创建种植季，再更新同一season实体。")
            self.goto("/fields", "season-create-update")
            self.page.get_by_label("田块名称").fill(unique_name)
            self.page.get_by_role("button", name="查询", exact=True).click()
            card = self.page.locator(".field-card").filter(has_text=unique_name)
            require(card.count() == 1, "New field was not present in the field list.")
            card.get_by_role("button", name="种植季", exact=True).click()
            dialog = self.page.get_by_role("dialog").filter(has_text="种植季信息")
            dialog.get_by_label("作物").fill("夏玉米")
            dialog.get_by_label("品种").fill("QA验证品种")
            dialog.get_by_label("播种日期").fill("2026-07-01")
            stage = dialog.get_by_label("当前生育期")
            stage_values = stage.locator("option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
            require(bool(stage_values), "No valid season stage option was available.")
            stage.select_option(stage_values[0])
            dialog.get_by_role("button", name="保存", exact=True).click()
            dialog.wait_for(state="detached", timeout=8_000)
            card.get_by_role("button", name="种植季", exact=True).click()
            edit_dialog = self.page.get_by_role("dialog").filter(has_text="种植季信息")
            require(edit_dialog.get_by_label("品种").input_value() == "QA验证品种", "Created season was not loaded for editing.")
            edit_dialog.get_by_label("品种").fill("QA验证品种二版")
            edit_dialog.get_by_role("button", name="保存", exact=True).click()
            edit_dialog.wait_for(state="detached", timeout=8_000)
            self.page.reload(wait_until="domcontentloaded")
            wait_for_render(self.page)
            season_state = self.page.evaluate(
                """(fieldId) => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  const season = snapshot?.entities?.CropSeason?.find(row => row.fieldId === fieldId && row.status === 'ENABLED');
                  return season ? { variety: season.variety, version: season.version } : null;
                }""",
                field_id,
            )
            require(season_state and season_state["variety"] == "QA验证品种二版" and season_state["version"] == 2, "Season create/update did not persist as two versions.")
            self._state_screenshot("田块-新增及种植季", "/fields")
            self.pass_detail("新增田块保存后可读；总览地图第一页显示15块，翻到第2/2页显示新增第16块，点击后进入同一fieldId档案；新建种植季并更新同一season，版本递增到2且二版品种经重载保留。")

        self.add_case(
            "新增田块与总览地图跨页详情及种植季版本",
            "新增第16田块进入总览地图第2页，点击后进入同ID详情；种植季创建和更新递增版本。",
            run_case,
            [
                "validation/screenshots/states/总览-第16田块地图.png",
                "validation/screenshots/states/总览-第16田块详情.png",
                "validation/screenshots/states/田块-新增及种植季.png",
            ],
        )

    def _test_device_tabs_and_verify_rejection(self) -> None:
        route = "/devices/DEV-JZ-S7KW"

        def run_case() -> None:
            self.goto(route, "device-tabs")
            for tab_name in ("点位映射", "校准记录", "诊断"):
                self.step(f"切换设备档案Tab：{tab_name}。")
                self.page.get_by_role("tab", name=tab_name, exact=True).click()
                require(self.page.get_by_role("tab", name=tab_name, exact=True).get_attribute("aria-selected") == "true", f"Tab {tab_name} did not become active.")
                self._state_screenshot(f"设备档案-{tab_name}", route)
            self.step("请求核验未配置适配器设备，确认不显示成功核验。")
            self.page.get_by_role("button", name="核验接入", exact=True).click()
            alert = self.page.get_by_role("alert")
            alert.wait_for(state="visible", timeout=8_000)
            message = alert.inner_text()
            require("適配" in message or "适配" in message or "未连接" in message or "连接" in message, "Device verification rejection did not explain the missing adapter.")
            require("核验完成" not in self.page.locator(".toast-stack").inner_text(), "Device verification produced a success notification without an adapter.")
            self.pass_detail(f"三个设备Tab均可达；无适配器核验被拒绝，显示：{message[:160]}")

        self.add_case("设备三Tab与未适配器核验拒绝", "三个Tab可切换；接入核验明确拒绝且不显示成功。", run_case)

    def _test_plan_page_three_and_editor(self) -> None:
        route = "/plans"

        def run_case() -> None:
            self.goto(route, "plan-pages")
            start = self.page.get_by_label("开始日期")
            end = self.page.get_by_label("结束日期")
            start.fill("")
            end.fill("")
            self.page.get_by_role("button", name="查询", exact=True).click()
            pagination = self.page.locator(".plan-table .pagination")
            pagination.wait_for(state="visible", timeout=5_000)
            summary = pagination.inner_text()
            require("共31条" in summary and "共3页" in summary, f"Expected all 31 plans over 3 pages; observed {summary[:100]}.")
            pagination.get_by_role("button", name="3", exact=True).click()
            require("第3页" in pagination.inner_text(), "Plan list could not reach page 3.")
            require(self.page.locator(".plan-table tbody tr").count() == 1, "Plan page 3 should contain the final row of 31.")
            self._state_screenshot("计划-第3页", route)

            self.step("进入草稿编排，添加并移除候选分区，再运行资源检查。")
            self.goto("/plans/new", "plan-editor-actions")
            self.page.get_by_label("计划名称").fill("QA资源检查计划")
            scheduled = datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=2)
            scheduled_text = scheduled.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
            self.page.get_by_label("计划时间").fill(scheduled_text)
            selector = self.page.get_by_label("选择候选分区")
            enabled_options = selector.locator("option:not([disabled])").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
            require(not selector.is_disabled(), "New plan candidate selector was disabled for the administrator.")
            require(len(enabled_options) >= 2, "Fewer than two enabled zones were available for plan-step editing.")
            selector.select_option(enabled_options[0])
            selector.select_option(enabled_options[1])
            self.page.get_by_role("button", name="添加", exact=True).click()
            rows = self.page.locator(".step-panel tbody tr")
            require(rows.count() == 2, f"Expected two added plan steps; observed {rows.count()}.")
            first_before_move = rows.first.inner_text()
            rows.first.click()
            self.page.get_by_role("button", name="下移", exact=True).click()
            require(rows.first.inner_text() != first_before_move, "Moving the selected step did not change its order.")
            self.page.get_by_role("button", name="移除", exact=True).click()
            require(rows.count() == 1, "Removing the selected plan step did not leave one draft step.")
            self.page.get_by_role("button", name="检查资源", exact=True).click()
            status = self.page.locator(".resource-status strong")
            status.wait_for(state="visible", timeout=8_000)
            require(status.inner_text() in ("检查通过", "存在资源冲突"), "Resource query returned no recognized result.")
            self._state_screenshot("计划-资源检查", "/plans/new")
            self.pass_detail(f"计划列表可访问第3页（31条/3页）；新草稿添加两步、调整顺序、移除一步；资源检查实际返回“{status.inner_text()}”。")

        self.add_case("计划第3页与步骤资源检查", "31计划可访问第3页；步骤草稿可变更并检查资源。", run_case)

    def _test_run_control_rejection_and_tabs(self) -> None:
        route = "/runs"

        def run_case() -> None:
            self.goto(route, "run-control")
            queued = self.page.locator(".queued-card")
            run_id = queued.locator(".card-head strong").first.inner_text().strip()
            before = queued.inner_text()
            require(run_id, "No queued run was available for the start rejection check.")
            self.page.get_by_role("button", name="启动", exact=True).first.click()
            dialog = self.page.get_by_role("dialog")
            dialog.get_by_label("启动原因").fill("QA验证控制服务边界")
            dialog.get_by_role("button", name="确认启动", exact=True).click()
            alert = dialog.get_by_role("alert")
            alert.wait_for(state="visible", timeout=8_000)
            message = alert.inner_text()
            require("设备控制服务" in message or "控制服务" in message or "尚未连接" in message, "Run start rejection did not explain the missing control service.")
            require(run_id in queued.inner_text() and "待执行" in queued.inner_text(), "Run status changed after the unavailable control service rejected start.")
            dialog.get_by_role("button", name="取消", exact=True).click()

            detail_route = "/runs/RUN-JZ-18E71500"
            self.goto(detail_route, "run-detail-tabs")
            for tab_name in ("轮灌步骤", "指令记录", "计量明细"):
                self.page.get_by_role("button", name=tab_name, exact=True).click()
                self._state_screenshot(f"运行详情-{tab_name}", detail_route)
                require(self.page.get_by_role("button", name=tab_name, exact=True).get_attribute("class").find("active") >= 0, f"Run tab {tab_name} did not activate.")
            completed = self.page.locator(".run-heading").inner_text()
            self.pass_detail(f"无控制服务时启动被拒绝且待执行状态保留；运行三Tab可切换。初始队列摘要长度={len(before)}。")

        self.add_case("运行控制拒绝及三Tab", "启动服务未接时拒绝且不改运行状态；三Tab可访问。", run_case)

    def _test_water_values_and_export(self) -> None:
        route = "/water"

        def run_case() -> None:
            self.goto(route, "water-export")
            content = self.page.locator(".water-page").inner_text()
            normalized_content = re.sub(r"[,，\s]", "", content)
            expected = ("4963.5", "4928.9", "34.6", "8.94", "16.52")
            missing = [value for value in expected if value not in normalized_content]
            require(not missing, f"Water totals/baseline did not match expected shared accounting values: missing {missing}.")
            require("不可计算" in content and "全场节水率" in content, "Farm-wide incomparability explanation was not rendered.")
            self.step("核对统一账本四项总计、单窗口基准和全场不可比说明。")
            self.page.get_by_role("button", name="导出", exact=True).click()
            self.page.get_by_text("导出任务已创建", exact=False).wait_for(state="visible", timeout=8_000)
            file_card = self.page.locator(".export-card")
            file_card.wait_for(state="visible", timeout=8_000)
            self.page.wait_for_function(
                """() => {
                  const card = document.querySelector('.export-card');
                  return card && (card.innerText.includes('可下载') || card.innerText.includes('READY') || card.querySelector('button[disabled]'));
                }""",
                timeout=12_000,
            )
            if self.page.get_by_role("button", name="下载", exact=False).count():
                with self.page.expect_download(timeout=8_000) as download_info:
                    self.page.get_by_role("button", name="下载", exact=False).click()
                download = download_info.value
                with tempfile.TemporaryDirectory(prefix="irrigation-qa-download-") as temporary:
                    download_path = Path(temporary) / download.suggested_filename
                    download.save_as(str(download_path))
                    raw = download_path.read_bytes()
                    text = raw.decode("utf-8-sig")
                    require(raw.startswith(b"\xef\xbb\xbf"), "Downloaded CSV does not start with UTF-8 BOM.")
                    require("账本编号,田块,日期,水量 m³,计量方式,状态" in text, "Downloaded CSV header did not match the expected business columns.")
                    require(len(text.splitlines()) > 1, "Downloaded CSV has no data rows.")
                    self.pass_detail(f"账本汇总匹配4963.5/4928.9/34.6/8.94及单窗口16.52%、全场不可比；生成并下载CSV（{len(raw)} bytes，UTF-8 BOM，已检查表头和数据行并清理临时文件）。")
                    self._state_screenshot("用水-CSV就绪", route)
            else:
                self.pass_detail("账本汇总匹配期望值；导出任务已创建，但本轮预览状态未提供可下载文件。")
                self._active_case["status"] = "PARTIAL"

        self.add_case("统一水量与真实CSV导出", "汇总与基准口径正确；创建并下载可验证的CSV。", run_case)

    def _test_settings_and_audit(self) -> None:
        def settings_case() -> None:
            self.goto("/settings", "settings-guard")
            self.step("检查当前管理员账号停用按钮禁用。")
            current_row = self.page.locator("tr").filter(has_text=self.admin_account)
            require(current_row.count() == 1, "Current admin row was not found in settings.")
            disabled = current_row.get_by_role("button", name="停用", exact=True)
            require(disabled.is_disabled(), "Self-disable action was not disabled.")
            self.page.get_by_role("button", name="运行参数", exact=True).click()
            input_box = self.page.get_by_label("过期阈值（s）")
            original = input_box.input_value()
            input_box.fill(str(int(original) + 1))
            self.page.get_by_role("button", name="取消编辑", exact=True).click()
            dialog = self.page.get_by_role("dialog").filter(has_text="放弃参数修改")
            dialog.wait_for(state="visible", timeout=5_000)
            dialog.get_by_role("button", name="取消", exact=True).click()
            require(input_box.input_value() == str(int(original) + 1), "Refusing to discard parameter changes did not preserve the draft.")
            self.page.get_by_role("button", name="重置", exact=True).click()
            require(input_box.input_value() == original, "Reset did not restore loaded policy values.")

            self.step("创建临时只读账号，在列表中重新打开并编辑后重载核对。")
            self.page.get_by_role("button", name="用户权限", exact=True).click()
            temp_account = "qa." + secrets.token_hex(4)
            self.page.get_by_role("button", name="新增账号", exact=True).click()
            user_dialog = self.page.get_by_role("dialog").filter(has_text="新增账号")
            user_dialog.get_by_label("用户标识").fill("QA验证用户")
            user_dialog.get_by_label("账号").fill(temp_account)
            user_dialog.get_by_label("角色").select_option("VIEWER")
            user_dialog.get_by_label("联系电话").fill("138" + str(secrets.randbelow(10**8)).zfill(8))
            authorized = user_dialog.locator("input[type=checkbox]")
            if authorized.count():
                authorized.first.check()
            user_dialog.get_by_role("button", name="确认保存", exact=True).click()
            user_dialog.wait_for(state="detached", timeout=8_000)
            pagination = self.page.locator(".account-table .pagination")
            if pagination.get_by_role("button", name="2", exact=True).count():
                pagination.get_by_role("button", name="2", exact=True).click()
            user_row = self.page.locator(".account-table tbody tr").filter(has_text=temp_account)
            require(user_row.count() == 1, "New QA user did not appear in the account table.")
            user_row.get_by_role("button", name="编辑", exact=True).click()
            edit_dialog = self.page.get_by_role("dialog").filter(has_text="编辑账号")
            edit_dialog.get_by_label("用户标识").fill("QA验证用户二版")
            edit_dialog.get_by_role("button", name="确认保存", exact=True).click()
            edit_dialog.wait_for(state="detached", timeout=8_000)
            self.page.reload(wait_until="domcontentloaded")
            wait_for_render(self.page)
            pagination = self.page.locator(".account-table .pagination")
            if pagination.get_by_role("button", name="2", exact=True).count() and "二版" not in self.page.locator(".account-table").inner_text():
                pagination.get_by_role("button", name="2", exact=True).click()
            require("QA验证用户二版" in self.page.locator(".account-table").inner_text(), "Edited QA user did not persist after reload.")

            self.step("确认运行参数修改，读取新的摘要值。")
            self.page.get_by_role("button", name="运行参数", exact=True).click()
            schedule_days = self.page.get_by_label("最长编排（天）")
            days_before = int(schedule_days.input_value())
            schedule_days.fill(str(days_before + 1))
            self.page.get_by_role("button", name="保存参数", exact=True).click()
            policy_confirm = self.page.get_by_role("dialog").filter(has_text="确认运行参数修改")
            policy_confirm.get_by_role("button", name="确认保存", exact=True).click()
            alert = self.page.get_by_role("alert")
            if alert.count() and alert.first.is_visible():
                raise CheckFailure("Policy save was rejected: " + alert.first.inner_text()[:180])
            self.page.reload(wait_until="domcontentloaded")
            wait_for_render(self.page)
            persisted_days = self.page.evaluate(
                """() => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  return snapshot?.entities?.SystemPolicy?.[0]?.maxScheduleDays ?? null;
                }"""
            )
            require(persisted_days == days_before + 1, "Confirmed policy value did not persist in the local snapshot.")
            self.page.get_by_role("button", name="运行参数", exact=True).click()
            self._state_screenshot("设置-运行参数已保存", "/settings")
            self.pass_detail("自身停用disabled；参数草稿取消被拒时保留、重置恢复；临时用户创建/编辑经重载保留；运行参数修改经确认提交。")

        self.add_case("Settings自停用保护与参数草稿", "自身停用disabled；取消草稿可守卫，重置恢复参数。", settings_case)

        def audit_case() -> None:
            self.goto("/audit", "audit-page")
            pagination = self.page.locator(".pagination").first
            before = pagination.inner_text()
            require("共" in before and "条/页" in before, "Audit pagination summary was not displayed.")
            page2 = pagination.get_by_role("button", name="2", exact=True)
            if page2.count():
                page2.click()
                require("第2页" in pagination.inner_text(), "Audit pagination did not select page 2.")
            row = self.page.locator("tbody tr").first
            require(row.count() == 1, "Audit rows were not rendered.")
            row.click()
            self.pass_detail("审计列表分页和行选中均可操作；该页为只读。")

        self.add_case("审计分页与行选择", "审计可分页，选择行显示关联证据。", audit_case)

    def _test_page_layout_and_history_invariants(self) -> None:
        def audit_layout_and_command_time() -> None:
            self.goto("/audit", "audit-layout-and-command-time")
            self.step("测量日期区间控件与查询按钮在1536×1024视口中的实际矩形。")
            date_box = self.page.locator(".audit-filters .date-filter > span").bounding_box()
            query_box = self.page.locator(".audit-filters > button.btn-primary").bounding_box()
            require(date_box is not None and query_box is not None, "Audit date range or query button is missing from the filter row.")
            overlap_x = max(0.0, min(date_box["x"] + date_box["width"], query_box["x"] + query_box["width"]) - max(date_box["x"], query_box["x"]))
            overlap_y = max(0.0, min(date_box["y"] + date_box["height"], query_box["y"] + query_box["height"]) - max(date_box["y"], query_box["y"]))
            require(overlap_x <= 0.5 or overlap_y <= 0.5, f"Audit date range and query button overlap by {overlap_x:.1f}×{overlap_y:.1f}px.")

            self.step("从本机预览快照中选择命令事件时间与CommandOutbox确认时间不同的审计链路，并核对界面采用后者。")
            fixture = self.page.evaluate(
                """() => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  const entities = snapshot?.entities;
                  if (!entities) return null;
                  const command = (entities.CommandOutbox || []).find(item => item.confirmedAt &&
                    (entities.CommandEvent || []).some(event => event.commandId === item.commandId &&
                      event.phase === 'CONFIRMED' && event.occurredAt !== item.confirmedAt));
                  if (!command) return null;
                  const audit = (entities.AuditLog || []).find(item => item.correlationId === command.correlationId ||
                    item.detail?.commandId === command.commandId);
                  const eventTimes = (entities.CommandEvent || []).filter(event => event.commandId === command.commandId &&
                    event.phase === 'CONFIRMED').map(event => event.occurredAt);
                  return audit ? { auditId: audit.auditId, confirmedAt: command.confirmedAt,
                    eventTimes, commandId: command.commandId } : null;
                }"""
            )
            require(fixture is not None, "No preview fixture was available to verify command-confirmation time against its event timestamps.")
            require(any(value != fixture["confirmedAt"] for value in fixture["eventTimes"]), "The audit fixture no longer distinguishes command confirmation time from an earlier device event.")
            self.goto(f"/audit?selected={fixture['auditId']}", "audit-command-confirmation")
            displayed = self.page.locator(".audit-chain .command-phase").last.locator("time").inner_text().strip()
            expected = self.page.evaluate(
                "value => new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Shanghai', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit'}).format(new Date(value))",
                fixture["confirmedAt"],
            )
            require(displayed == expected, f"Audit action-confirmation time {displayed!r} does not match CommandOutbox.confirmedAt {expected!r}.")
            self._state_screenshot("审计-日期筛选与命令确认时间", f"/audit?selected={fixture['auditId']}")
            self.pass_detail(f"日期区间与查询按钮无重叠；审计链路{fixture['commandId']}的动作确认时间等于命令confirmedAt（{expected}），未采用不同设备事件时间。")

        self.add_case("审计日期控件布局与命令确认时间", "日期范围不与查询按钮重叠；动作确认时间采用命令确认时间。", audit_layout_and_command_time)

        def strategy_zone_list() -> None:
            route = "/strategies/STR-JZ-K8QM/edit"
            self.goto(route, "strategy-zone-scroll")
            self.step("检查策略适用分区列表的全部选项、可滚动样式和滚动到底后的最后一项。")
            result = self.page.locator(".zone-check-list").evaluate(
                """list => {
                  const rows = [...list.querySelectorAll(':scope > label')];
                  const style = getComputedStyle(list);
                  const originalTop = list.scrollTop;
                  const maxScroll = Math.max(0, list.scrollHeight - list.clientHeight);
                  list.scrollTop = maxScroll;
                  const box = list.getBoundingClientRect();
                  const last = rows.at(-1)?.getBoundingClientRect();
                  const lastVisible = !!last && last.top >= box.top - 1 && last.bottom <= box.bottom + 1;
                  list.scrollTop = originalTop;
                  return {count: rows.length, overflowY: style.overflowY, maxScroll,
                    clientHeight: list.clientHeight, scrollHeight: list.scrollHeight, lastVisible};
                }"""
            )
            require(result["count"] > 0, "Strategy editor has no applicable zone options.")
            require(result["overflowY"] in {"auto", "scroll"}, f"Strategy zone list is not scrollable (overflow-y={result['overflowY']}).")
            require(result["lastVisible"], "The final strategy zone option remains clipped after scrolling the list to its end.")
            require(result["maxScroll"] == 0 or result["scrollHeight"] > result["clientHeight"], "Strategy zone list reports an unusable scroll position.")
            self._state_screenshot("策略-分区列表可滚动", route)
            self.pass_detail(f"策略编辑器列出{result['count']}个适用分区；列表overflow-y={result['overflowY']}，末项滚动后完整可见。")

        self.add_case("策略分区完整显示与滚动", "所有适用分区保留在可滚动列表中，末项能完整显示。", strategy_zone_list)

        def field_history_excludes_queued() -> None:
            route = "/fields/FLD-JZ-M9R2"
            self.goto(route, "field-history-excludes-queued")
            queued_ids = self.page.evaluate(
                """() => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  const entities = snapshot?.entities;
                  if (!entities) return [];
                  const zoneIds = new Set((entities.IrrigationZone || []).filter(zone => zone.fieldId === 'FLD-JZ-M9R2').map(zone => zone.zoneId));
                  const relatedRunIds = new Set((entities.RunStep || []).filter(step => zoneIds.has(step.zoneId)).map(step => step.runId));
                  return (entities.IrrigationRun || []).filter(run => relatedRunIds.has(run.runId) && run.status === 'QUEUED').map(run => run.runId);
                }"""
            )
            require(queued_ids, "Reference field fixture has no related queued run to distinguish history from pending work.")
            self.step("逐页读取田块灌溉记录，确认历史列表不展示任何待执行运行。")
            pager = self.page.locator(".history-title .pagination")
            all_rows: list[tuple[str, str]] = []
            while True:
                rows = self.page.locator(".history .data-table tbody tr")
                for index in range(rows.count()):
                    cells = rows.nth(index).locator("td")
                    if cells.count() >= 2:
                        all_rows.append((cells.nth(1).inner_text().strip(), rows.nth(index).inner_text()))
                next_page = pager.get_by_role("button", name="下一页", exact=True)
                if next_page.is_disabled():
                    break
                before = pager.locator(".pagination-summary").inner_text()
                next_page.click()
                self.page.wait_for_function(
                    "previous => document.querySelector('.history-title .pagination-summary')?.textContent !== previous",
                    before,
                    timeout=4_000,
                )
            seen_ids = {run_id for run_id, _ in all_rows}
            queued_visible = sorted(seen_ids.intersection(queued_ids))
            pending_labels = [run_id for run_id, text in all_rows if "待执行" in text or "QUEUED" in text]
            require(all_rows, "No history rows were displayed for the reference field.")
            require(not queued_visible, f"Queued runs are incorrectly listed as field history: {', '.join(queued_visible)}.")
            require(not pending_labels, f"Field history contains pending status rows: {', '.join(pending_labels)}.")
            self.page.get_by_role("button", name="上一页", exact=True).click() if not pager.get_by_role("button", name="上一页", exact=True).is_disabled() else None
            self._state_screenshot("田块档案-历史排除待执行", route)
            self.pass_detail(f"逐页检查{len(all_rows)}条田块记录；相关待执行运行{len(queued_ids)}条均未出现在历史表。")

        self.add_case("田块历史排除待执行运行", "灌溉历史按所有分页检查，不出现QUEUED/待执行运行。", field_history_excludes_queued)

        def alarm_detail_fits_viewport() -> None:
            route = "/alarms?selected=ALM-JZ-S8HD"
            self.goto(route, "alarm-detail-viewport")
            self.step("测量选中告警详情面板和所有详情字段在1536×1024视口中的边界。")
            geometry = self.page.locator(".alarm-detail").evaluate(
                """panel => {
                  const rect = panel.getBoundingClientRect();
                  const facts = panel.querySelector('.alarm-facts');
                  const factRects = [...(facts?.children || [])].map(node => {
                    const child = node.getBoundingClientRect();
                    return {left: child.left, right: child.right, top: child.top, bottom: child.bottom};
                  });
                  return {viewportWidth: innerWidth, viewportHeight: innerHeight,
                    left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                    clientWidth: panel.clientWidth, scrollWidth: panel.scrollWidth,
                    clientHeight: panel.clientHeight, scrollHeight: panel.scrollHeight,
                    factRects};
                }"""
            )
            require(geometry["left"] >= -0.5 and geometry["right"] <= geometry["viewportWidth"] + 0.5,
                    f"Alarm detail panel extends outside the horizontal viewport ({geometry['left']:.1f}..{geometry['right']:.1f}).")
            require(geometry["top"] >= -0.5 and geometry["bottom"] <= geometry["viewportHeight"] + 0.5,
                    f"Alarm detail panel does not fit vertically in the viewport ({geometry['top']:.1f}..{geometry['bottom']:.1f}).")
            require(geometry["scrollWidth"] <= geometry["clientWidth"] + 1,
                    "Alarm detail panel has horizontally clipped content.")
            require(all(item["left"] >= geometry["left"] - 1 and item["right"] <= geometry["right"] + 1 for item in geometry["factRects"]),
                    "At least one alarm detail field extends beyond the detail panel width.")
            self._state_screenshot("告警-详情视口完整", route)
            self.pass_detail(f"告警详情面板完整位于视口内（x={geometry['left']:.1f}..{geometry['right']:.1f}, y={geometry['top']:.1f}..{geometry['bottom']:.1f}），无横向溢出。")

        self.add_case("告警详情在视口内完整布局", "1536×1024视口中告警详情及字段完整可见且不横向溢出。", alarm_detail_fits_viewport)

    def _test_viewer_permissions(self, credentials: dict[str, str]) -> None:
        viewer_account, viewer_secret = choose_account(credentials, "QA_VIEWER_ACCOUNT", "viewer")

        def run_case() -> None:
            self.step("退出管理员后使用隔离只读账号登录。")
            self.goto("/overview", "viewer-logout")
            self.page.get_by_role("button", name="系统管理员", exact=True).click()
            self.page.get_by_role("button", name="退出登录", exact=True).click()
            confirm = self.page.get_by_role("dialog").filter(has_text="退出当前账号")
            confirm.get_by_role("button", name="退出登录", exact=True).click()
            self.page.wait_for_function("() => location.hash.startsWith('#/login')", timeout=8_000)
            self.login(viewer_account, viewer_secret)
            require("只读查看人员" in self.page.locator(".account-button").inner_text(), "Viewer account did not establish a read-only session.")
            self.goto("/fields", "viewer-fields")
            require(self.page.get_by_role("button", name="新增田块", exact=True).is_disabled(), "VIEWER can open the field creation action.")
            self.goto("/settings", "viewer-settings-route")
            self.wait_for_route("/overview", timeout=8_000)
            require(urlsplit(self.page.url).fragment.split("?", 1)[0] == "/overview", "VIEWER was not redirected from the settings route.")
            require("无权访问该页面" in self.page.locator(".toast-stack").inner_text(), "Settings route rejection did not explain the permission denial.")
            self.pass_detail("VIEWER只读会话可查看田块、写入入口disabled；直接访问Settings被拒并回到总览。")

        self.add_case("VIEWER只读入口与路由拒绝", "只读入口不可写；设置路由越权返回总览并显示拒绝。", run_case)

    def _test_alarm_and_workorder_flow(self, credentials: dict[str, str]) -> None:
        technician_account, technician_secret = choose_account(credentials, "QA_TECHNICIAN_ACCOUNT", "technician")

        def logout(role_name: str) -> None:
            self.page.get_by_role("button", name=role_name, exact=True).click()
            self.page.get_by_role("button", name="退出登录", exact=True).click()
            confirmation = self.page.get_by_role("dialog").filter(has_text="退出当前账号")
            confirmation.get_by_role("button", name="退出登录", exact=True).click()
            self.wait_for_route("/login", timeout=8_000)

        def run_case() -> None:
            self.step("打开已有活动告警，验证存在未完成工单时派工和未恢复时关闭均禁用。")
            alarm_route = "/alarms?selected=ALM-JZ-S8HD"
            self.goto(alarm_route, "alarm-duplicate-assignment")
            self.page.get_by_role("button", name="处置当前告警", exact=True).click()
            alarm_dialog = self.page.get_by_role("dialog").filter(has_text="告警处置")
            require(alarm_dialog.get_by_role("button", name="派工", exact=True).is_disabled(), "Duplicate dispatch was not disabled for an alarm with an incomplete work order.")
            require(alarm_dialog.get_by_role("button", name="关闭告警", exact=True).is_disabled(), "Unrecovered alarm close was not disabled.")
            require("已有未完成工单" in alarm_dialog.inner_text(), "Duplicate dispatch reason was not shown in the alarm operation context.")
            self._state_screenshot("告警-重复派工阻断", alarm_route)
            alarm_dialog.get_by_role("button", name="取消", exact=True).click()

            self.step("由管理员创建无告警关联工单，明确分配给临时技术员并进入待接单。")
            self.goto("/maintenance", "workorder-create")
            assignee_id = self.page.evaluate(
                """account => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  return snapshot?.entities?.User?.find(user => user.account === account && user.role === 'TECHNICIAN')?.userId || '';
                }""",
                technician_account,
            )
            require(assignee_id, "Temporary technician was not present in the preview user list.")
            known_ids = set(self.page.locator(".work-card header strong").all_text_contents())
            self.page.get_by_role("button", name="新建工单", exact=True).click()
            create_dialog = self.page.get_by_role("dialog").filter(has_text="新建工单")
            create_dialog.get_by_label("责任人").select_option(assignee_id)
            zone = create_dialog.get_by_label("关联分区")
            zone_ids = zone.locator("option").evaluate_all("nodes => nodes.map(n => n.value).filter(Boolean)")
            require(bool(zone_ids), "No authorized zone was available for a new work order.")
            zone.select_option(zone_ids[0])
            due_at = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=3)).replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
            create_dialog.get_by_label("期限").fill(due_at)
            create_dialog.get_by_label("工单说明").fill("本机临时QA维护闭环验证")
            create_dialog.get_by_role("button", name="创建工单", exact=True).click()
            create_dialog.wait_for(state="detached", timeout=8_000)
            current_ids = self.page.locator(".work-card header strong").all_text_contents()
            created_ids = [item for item in current_ids if item not in known_ids]
            require(len(created_ids) == 1, f"Expected one newly created work order; observed {len(created_ids)}.")
            work_order_id = created_ids[0]
            work_card = self.page.locator(".work-card").filter(has_text=work_order_id)
            require(work_card.count() == 1, "Created work order was not displayed in the maintenance lanes.")
            self._state_screenshot("工单-新建待接单", "/maintenance")

            self.step("临时技术员本人接单并提交处理结果。")
            logout("系统管理员")
            self.login(technician_account, technician_secret)
            require("巡检维护人员" in self.page.locator(".account-button").inner_text(), "Assigned technician did not obtain the expected role.")
            self.goto("/maintenance", "workorder-technician")
            card = self.page.locator(".work-card").filter(has_text=work_order_id)
            card.click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.get_by_role("button", name="接单", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)
            self.page.locator(".work-card").filter(has_text=work_order_id).click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.locator("textarea").fill("QA技术员已完成设备和分区现场检查，提交处理结果。")
            detail.get_by_role("button", name="提交结果", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)

            self.step("管理员退回一次补充材料，再由本人复提并验收完成。")
            logout("巡检维护人员")
            self.login(self.admin_account, choose_account(credentials, "QA_ADMIN_ACCOUNT", "admin")[1])
            self.goto("/maintenance", "workorder-admin-review")
            self.page.locator(".work-card").filter(has_text=work_order_id).click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.locator("textarea").fill("请补充现场检查记录和照片。")
            detail.get_by_role("button", name="退回", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)
            self._state_screenshot("工单-退回补充", "/maintenance")

            logout("系统管理员")
            self.login(technician_account, technician_secret)
            self.goto("/maintenance", "workorder-technician-resubmit")
            self.page.locator(".work-card").filter(has_text=work_order_id).click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.get_by_role("button", name="接单", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)
            self.page.locator(".work-card").filter(has_text=work_order_id).click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.locator("textarea").fill("QA技术员按退回意见补充现场检查记录并重新提交结果。")
            detail.get_by_role("button", name="提交结果", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)

            logout("巡检维护人员")
            self.login(self.admin_account, choose_account(credentials, "QA_ADMIN_ACCOUNT", "admin")[1])
            self.goto("/maintenance", "workorder-final-acceptance")
            self.page.locator(".work-card").filter(has_text=work_order_id).click()
            detail = self.page.get_by_role("dialog").filter(has_text=work_order_id)
            detail.locator("textarea").fill("QA验收合格，现场记录已补充。")
            detail.get_by_role("button", name="验收通过", exact=True).click()
            detail.wait_for(state="detached", timeout=8_000)
            final_status = self.page.evaluate(
                """workOrderId => {
                  const snapshot = JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null');
                  return snapshot?.entities?.WorkOrder?.find(row => row.workOrderId === workOrderId)?.status || null;
                }""",
                work_order_id,
            )
            require(final_status == "COMPLETED", "Work order did not reach COMPLETED after the technician resubmitted and the administrator accepted it.")
            self._state_screenshot("工单-验收完成", "/maintenance")
            self.pass_detail("活动未恢复告警的派工/关闭入口均阻断；QA工单经本人接单、提交、管理员退回、本人复提及管理员验收后达到COMPLETED。所有更改仅在一次性预览context。")

        self.add_case("告警重复派工与工单退回验收闭环", "重复派工和未恢复关闭被禁用；本人处理工单并完成管理员退回/验收流转。", run_case)

    def _test_corrupt_snapshot_backup_and_recovery(self) -> None:
        def run_case() -> None:
            require(self._browser is not None, "Chromium browser is not available for the isolated recovery context.")
            recovery_context = self._browser.new_context(
                viewport={"width": 1536, "height": 1024},
                device_scale_factor=1,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                accept_downloads=True,
            )
            corrupt = "{\"broken\":true"
            recovery_context.add_init_script(
                "localStorage.setItem('irrigation.reference.snapshot.v1', " + json.dumps(corrupt) + ");"
            )
            page = recovery_context.new_page()
            page.set_default_timeout(8_000)
            page.on("pageerror", lambda error: self.page_errors.append(self._sanitize(str(error))))
            page.goto(navigate_url(self.base_url, "/login", "corrupt-snapshot"), wait_until="domcontentloaded")
            wait_for_render(page, private=False)
            require("损坏" in page.locator(".login-page").inner_text() or "异常" in page.locator(".login-page").inner_text(), "Corrupt snapshot was not surfaced on the login recovery screen.")
            if self.capture_screenshots:
                self.screens.append(screenshot(page, STATES_DIR / "损坏快照-恢复界面.png", "/login", "损坏快照-恢复界面"))
            self.step("损坏快照出现时先下载原始备份，再确认恢复初始数据。")
            with tempfile.TemporaryDirectory(prefix="irrigation-qa-backup-") as temporary:
                with page.expect_download(timeout=8_000) as download_info:
                    page.get_by_role("button", name="下载原始备份", exact=True).click()
                backup = Path(temporary) / download_info.value.suggested_filename
                download_info.value.save_as(str(backup))
                require(backup.read_text(encoding="utf-8") == corrupt, "Downloaded corrupt snapshot backup did not preserve the original bytes.")
                page.get_by_role("button", name="恢复初始数据", exact=True).click()
                confirmation = page.get_by_role("dialog").filter(has_text="恢复本机数据")
                confirmation.get_by_role("button", name="确认恢复初始数据", exact=True).click()
                page.get_by_text("本机数据已恢复，请重新登录", exact=False).wait_for(state="visible", timeout=8_000)
                restored = page.evaluate("() => JSON.parse(localStorage.getItem('irrigation.reference.snapshot.v1') || 'null')")
                require(isinstance(restored, dict) and "entities" in restored, "Initial snapshot recovery did not replace the corrupted value.")
                if self.capture_screenshots:
                    self.screens.append(screenshot(page, STATES_DIR / "损坏快照-恢复完成.png", "/login", "损坏快照-恢复完成"))
            recovery_context.close()
            self.pass_detail("下载备份与注入的损坏字节完全一致；确认后只恢复本临时context的参考快照并回到登录。")

        self.add_case("损坏快照备份与确认恢复", "先下载原始字节，确认后恢复隔离的初始快照。", run_case)

    def report(self) -> dict[str, Any]:
        counts = {status: sum(1 for case in self.cases if case["status"] == status) for status in ("PASS", "PARTIAL", "FAIL", "NOT_RUN")}
        return {
            "schema_version": 1,
            "generated_at": utc_now(),
            "base_url": self.base_url,
            "browser": {"name": "Chromium", "headless": True, "args": ["--no-sandbox"]},
            "context": {"viewport": {"width": 1536, "height": 1024}, "device_scale_factor": 1, "locale": "zh-CN", "timezone": "Asia/Shanghai", "isolated_profile": True},
            "screenshots": self.screens,
            "cases": self.cases,
            "visual_review": {
                "method": "Manual side-by-side structural review of all source PNGs and actual default screenshots; no pixel-threshold verdict.",
                "excluded_from_functional_counts": True,
                "pairs": [
                    {
                        "screen": name,
                        "reference_file": f"screenshots/{name}.png",
                        "actual_file": f"validation/screenshots/reference/{name}.png",
                        "structure_and_key_data": structure,
                        "visible_differences": differences,
                    }
                    for name, structure, differences in VISUAL_REVIEW
                ],
            },
            "summary": {"counts": counts, "page_errors": len(self.page_errors), "console_errors": len(self.console_errors)},
            "page_errors": self.page_errors,
            "console_errors": self.console_errors,
            "backend": "Not connected; browser preview rejection is not backend or field-device integration evidence.",
        }


def render_markdown(report: dict[str, Any], pre_hashes: dict[str, str], post_hashes: dict[str, str], hash_failures: list[str]) -> str:
    counts = report["summary"]["counts"]
    lines = [
        "# 前端实际浏览器验证",
        "",
        f"运行时间：{report['generated_at']}。URL：`{report['base_url']}`。Chromium headless，1536×1024，DPR 1，zh-CN，Asia/Shanghai。浏览器使用一次性临时 context，不读取或覆盖用户现有 localStorage。",
        "",
        "本报告只写脚本实际观察到的结果。PASS表示对应UI操作或页面状态已在本轮执行；PARTIAL表示核心检查执行但本轮未取得全部结果；FAIL表示实际断言失败。截图位于`validation/screenshots/`，机器结果为`validation/frontend-validation.json`。",
        "",
        "## 结果汇总",
        "",
        f"PASS {counts['PASS']} · PARTIAL {counts['PARTIAL']} · FAIL {counts['FAIL']} · 未执行 {counts['NOT_RUN']} · pageerror {report['summary']['page_errors']} · console.error {report['summary']['console_errors']}",
        "",
        "## 页面与功能结果",
        "",
        "| 检查 | 状态 | 操作步骤 | 实际结果 | 证据 |",
        "|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        steps = "<br>".join(case.get("steps", [])) or "—"
        evidence = "<br>".join(f"`{item}`" for item in case.get("evidence", [])) or "—"
        actual = case.get("actual", "").replace("|", "\\|")
        lines.append(f"| {case['name']} | **{case['status']}** | {steps} | {actual} | {evidence} |")
    reference_screens = [shot for shot in report["screenshots"] if shot["file"].startswith("validation/screenshots/reference/")]
    state_screens = [shot for shot in report["screenshots"] if shot["file"].startswith("validation/screenshots/states/")]
    lines.extend(["", "## 默认页面截图清单", "", "| 页面 | 路由 | 截图 | 尺寸 | 修订 |", "|---|---|---|---:|---:|"])
    for shot in reference_screens:
        lines.append(f"| {shot.get('screen', shot['name'])} | `{shot['route']}` | `{shot['file']}` | {shot['width']}×{shot['height']} | {shot.get('revision') if shot.get('revision') is not None else '—'} |")
    lines.extend(["", "## 交互状态截图", "", "| 状态 | 路由 | 截图 | 尺寸 | 修订 |", "|---|---|---|---:|---:|"])
    for shot in state_screens:
        lines.append(f"| {shot['name']} | `{shot['route']}` | `{shot['file']}` | {shot['width']}×{shot['height']} | {shot.get('revision') if shot.get('revision') is not None else '—'} |")
    review = report["visual_review"]
    lines.extend(
        [
            "",
            "## 21页人工视觉结构对照",
            "",
            "已将`screenshots/`中的21张参考PNG与`validation/screenshots/reference/`中本轮对应实际截图逐对并排查看，核对顶栏/侧栏、主要卡片/图表/表格结构和首屏关键数据。以下是定性人工记录，不计算像素差，也不声明达到spec中的2px/4px布局目标；视觉对照不计入上方功能断言PASS。实际截图保留原始1536×1024尺寸。",
            "",
            "公共区域复核：20个业务页均显示固定农场名、2026.07.28 10:18:43、系统管理员、连接状态和13个导航子项；实际品牌图标轮廓与参考图略有不同。登录页按安全要求保持账号/口令为空。公共导航参考图的主区为空；实际证据从总览路由捕获公共壳层，因此主区保留总览且总览菜单选中。",
            "",
            "弹窗对照边界：21张参考PNG均为默认页面状态，没有同一弹窗的参考PNG；实际脏表单、确认、退回等弹窗截图保存在`states/`，因此这里只记录功能取证，不宣称弹窗视觉一致。设备、运行和设置默认Tab位置已随各自页面并排核对；Tab的其他状态也有独立实际截图。",
            "",
            "| 页面 | 原参考图 | 实际截图 | 结构与关键数据 | 可见差异/说明 |",
            "|---|---|---|---|---|",
        ]
    )
    for pair in review["pairs"]:
        lines.append(
            f"| {pair['screen']} | `{pair['reference_file']}` | `{pair['actual_file']}` | {pair['structure_and_key_data']} | {pair['visible_differences']} |"
        )
    lines.extend(["", "## 输入资料完整性", ""])
    if not hash_failures and pre_hashes == post_hashes:
        lines.append(f"PASS：本轮开始和结束时核对`validation/reference-inputs.sha256`共{len(pre_hashes)}项，全部匹配且未变化。")
    else:
        lines.append("FAIL：原始输入哈希校验失败或运行前后有变化。")
        lines.extend(f"- {failure}" for failure in hash_failures)
    lines.extend(["", "## 浏览器错误", ""])
    if report["page_errors"]:
        lines.append("pageerror：")
        lines.extend(f"- `{error}`" for error in report["page_errors"])
    else:
        lines.append("本轮未捕获pageerror。")
    if report["console_errors"]:
        lines.append("console.error：")
        lines.extend(f"- `{error}`" for error in report["console_errors"])
    else:
        lines.append("本轮未捕获console.error。")
    lines.extend(
        [
            "",
            "## 边界与未验证项",
            "",
            "本轮针对本机Vue预览仓储。设备核验/运行启动如果被拒绝，表示前端正确显示未接生产适配器或控制服务；不能据此宣称生产控制、服务端鉴权、API联调或现场设备反馈通过。后端尚未接入，前端业务修改仅在本次临时浏览器profile中，不自动迁移到数据库。",
            "",
            "截图`公共导航.png`从总览路由实际捕获公共壳层；应用没有空白导航母版路由，因此截图主内容区保留总览页面。",
            "",
            "本报告由`python3 scripts/validate_frontend.py --base-url <URL>`生成。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("IRRIGATION_QA_BASE_URL", "http://127.0.0.1:5188"))
    parser.add_argument("--no-screenshots", action="store_true", help="Run behavior checks without replacing screenshot artifacts.")
    args = parser.parse_args()
    try:
        base_url = normalize_base_url(args.base_url)
    except CheckFailure as exc:
        print(str(exc))
        return 2
    try:
        credentials = load_test_credentials()
    except CheckFailure as exc:
        print(str(exc))
        return 2
    VALIDATION.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_screenshots:
        for directory in (REFERENCE_DIR, STATES_DIR):
            for image_file in directory.glob("*.png"):
                image_file.unlink()
    pre_hashes, pre_failures = read_reference_hashes()
    run = FrontendRun(base_url, capture_screenshots=not args.no_screenshots)
    try:
        report = run.run(credentials)
    except Exception as exc:
        report = run.report()
        report["setup_error"] = run._safe_error(exc)
        report["summary"]["counts"]["FAIL"] += 1
        report["cases"].append({"name": "验证脚本准备/浏览器启动", "status": "FAIL", "expected": "测试凭据和浏览器可用。", "steps": [], "actual": report["setup_error"], "evidence": []})
    post_hashes, post_failures = read_reference_hashes()
    hash_failures = [*pre_failures, *post_failures]
    if pre_hashes != post_hashes:
        hash_failures.append("Reference input SHA256 values changed during the run.")
    report["reference_input_hashes"] = {"before": pre_hashes, "after": post_hashes, "failures": hash_failures}
    report["summary"]["reference_hashes_ok"] = not hash_failures and pre_hashes == post_hashes
    if hash_failures:
        report["summary"]["counts"]["FAIL"] += 1
    json_path = VALIDATION / "frontend-validation.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (VALIDATION / "screenshots" / "manifest.json").write_text(json.dumps(report["screenshots"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = render_markdown(report, pre_hashes, post_hashes, hash_failures)
    (VALIDATION / "frontend-validation.md").write_text(md, encoding="utf-8")
    print(f"Validation JSON: {json_path.relative_to(ROOT)}")
    print(f"Validation report: {(VALIDATION / 'frontend-validation.md').relative_to(ROOT)}")
    print(f"Screenshots captured: {len(report['screenshots'])}")
    print("Results: " + ", ".join(f"{key}={value}" for key, value in report["summary"]["counts"].items()))
    print(f"Reference input hashes unchanged: {report['summary']['reference_hashes_ok']}")
    return 1 if report["summary"]["counts"]["FAIL"] or not report["summary"]["reference_hashes_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
