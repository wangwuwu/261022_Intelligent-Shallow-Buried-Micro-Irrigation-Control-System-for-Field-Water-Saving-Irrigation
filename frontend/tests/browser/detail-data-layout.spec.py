"""Regress terminal-only field history, command confirmation time, and alarm fit.

Run: python3 tests/browser/detail-data-layout.spec.py --url http://127.0.0.1:5188
Requires a running Vite server, validation credentials, Playwright Python, and Chromium.
The test uses isolated reference-mode contexts and makes no business writes.
"""

import argparse
import json
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = Path(__file__).resolve().parents[2]
TERMINAL_RUNS = {"COMPLETED", "STOPPED", "FAILED"}


def login(page, base_url, capture, admin, password):
    page.goto(f"{base_url}/?reference=1&capture={capture}#/login", wait_until="networkidle")
    page.locator("#login-account").fill(admin["account"])
    page.locator("#login-password").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(lambda url: url.endswith("#/overview"))


def test_field_history_omits_future_and_active_runs(browser, base_url, credentials, admin, entities):
    field = next(field for field in entities["Field"] if field["name"] == "西泵南畦")
    zone_ids = {zone["zoneId"] for zone in entities["IrrigationZone"] if zone["fieldId"] == field["fieldId"]}
    run_ids = {step["runId"] for step in entities["RunStep"] if step["zoneId"] in zone_ids}
    terminal_ids = {run["runId"] for run in entities["IrrigationRun"] if run["runId"] in run_ids and run["status"] in TERMINAL_RUNS}

    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = context.new_page()
    capture = "field-history-" + uuid.uuid4().hex
    login(page, base_url, capture, admin, credentials[admin["account"]])
    page.goto(f"{base_url}/?reference=1&capture={capture}#/fields/{field['fieldId']}", wait_until="networkidle")
    table = page.locator(".history")
    table.wait_for()
    summary = page.locator(".history-title .muted").inner_text()
    assert f"相关运行共{len(terminal_ids)}条" in summary, summary
    rows = table.locator("tbody tr")
    assert rows.count() == len(terminal_ids)
    visible_ids = [rows.nth(i).locator("td").nth(1).inner_text() for i in range(rows.count())]
    assert set(visible_ids).issubset(terminal_ids), visible_ids
    assert all("待执行" not in rows.nth(i).inner_text() for i in range(rows.count()))
    context.close()


def test_audit_uses_outbox_confirmation_time(browser, base_url, credentials, admin, entities):
    audit_rows = sorted(entities["AuditLog"], key=lambda item: (item["occurredAt"], item["auditId"]), reverse=True)
    selected = audit_rows[0]
    command = next((item for item in entities["CommandOutbox"] if item["commandId"] == selected.get("detail", {}).get("commandId") or item["correlationId"] == selected.get("correlationId")), None)
    assert command and command.get("confirmedAt")
    expected_time = command["confirmedAt"][11:19]

    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = context.new_page()
    capture = "audit-time-" + uuid.uuid4().hex
    login(page, base_url, capture, admin, credentials[admin["account"]])
    page.goto(f"{base_url}/?reference=1&capture={capture}#/audit", wait_until="networkidle")
    page.locator(".command-phases").wait_for()
    actual = page.locator(".command-phase time").nth(2).inner_text()
    assert expected_time in actual, {"expected": expected_time, "actual": actual}
    context.close()


def test_alarm_detail_fits_without_hiding_its_fields(browser, base_url, credentials, admin):
    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = context.new_page()
    capture = "alarm-fit-" + uuid.uuid4().hex
    login(page, base_url, capture, admin, credentials[admin["account"]])
    page.goto(f"{base_url}/?reference=1&capture={capture}#/alarms", wait_until="networkidle")
    detail = page.locator(".alarm-detail")
    detail.wait_for()
    bounds = detail.bounding_box()
    assert bounds["y"] + bounds["height"] <= 1024, bounds
    assert page.locator(".alarm-detail").inner_text().count("\n") > 0
    assert page.get_by_text("责任人", exact=True).is_visible()
    assert page.locator(".main-content").evaluate("el => el.scrollHeight <= el.clientHeight + 1")
    context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    entities = json.loads((ROOT / "shared_context.json").read_text())["entities"]
    credentials = json.loads((FRONTEND / ".local" / "validation-secrets.json").read_text())
    admin = next(user for user in entities["User"] if user["role"] == "ADMIN")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            test_field_history_omits_future_and_active_runs(browser, base_url, credentials, admin, entities)
            test_audit_uses_outbox_confirmation_time(browser, base_url, credentials, admin, entities)
            test_alarm_detail_fits_without_hiding_its_fields(browser, base_url, credentials, admin)
        finally:
            browser.close()
    print("Field history, audit confirmation time, and alarm detail layout passed")


if __name__ == "__main__":
    main()
