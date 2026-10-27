"""Check the audit date filter and strategy zone-list layout in Chromium.

Run: python3 tests/browser/audit-strategy-layout.spec.py --url http://127.0.0.1:5188
Requires a running Vite server, validation credentials, Playwright Python, and Chromium.
The test uses isolated reference-mode browser contexts and makes no business writes.
"""

import argparse
import json
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = Path(__file__).resolve().parents[2]


def login(page, base_url, capture, admin, password):
    page.goto(f"{base_url}/?reference=1&capture={capture}#/login", wait_until="networkidle")
    page.locator("#login-account").fill(admin["account"])
    page.locator("#login-password").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(lambda url: url.endswith("#/overview"))


def assert_audit_filter_fits(page):
    layout = page.locator(".audit-filters").evaluate(
        "form => {"
        "const range=form.querySelector('.date-filter > span').getBoundingClientRect();"
        "const button=form.querySelector('button').getBoundingClientRect();"
        "const bounds=form.getBoundingClientRect();"
        "return {range:{left:range.left,right:range.right,top:range.top,bottom:range.bottom},"
        "button:{left:button.left,right:button.right,top:button.top,bottom:button.bottom},"
        "bounds:{left:bounds.left,right:bounds.right,clientWidth:form.clientWidth,scrollWidth:form.scrollWidth}};"
        "}"
    )
    date_range, button, bounds = layout["range"], layout["button"], layout["bounds"]
    assert date_range["right"] <= button["left"] or date_range["bottom"] <= button["top"], layout
    assert date_range["left"] >= bounds["left"] and button["right"] <= bounds["right"], layout
    assert bounds["scrollWidth"] <= bounds["clientWidth"] + 1, layout


def assert_strategy_rows_are_whole_and_scrollable(page):
    result = page.locator(".zone-checks").evaluate(
        "box => {"
        "const scroller=box.querySelector('.zone-check-list')||box;"
        "const clip=scroller.getBoundingClientRect();"
        "const labels=[...box.querySelectorAll('label')];"
        "const rects=labels.map(label=>{const r=label.getBoundingClientRect();"
        "return {top:r.top,bottom:r.bottom,visibleTop:Math.max(r.top,clip.top),"
        "visibleBottom:Math.min(r.bottom,clip.bottom)};});"
        "const visible=rects.filter(r=>r.visibleBottom>r.visibleTop);"
        "return {total:labels.length,visibleCount:visible.length,"
        "partial:visible.filter(r=>r.visibleTop>r.top+1||r.visibleBottom<r.bottom-1),"
        "clientHeight:scroller.clientHeight,scrollHeight:scroller.scrollHeight,"
        "checked:labels.filter(label=>label.querySelector('input').checked).length};"
        "}"
    )
    assert result["total"] == 16, result
    assert result["visibleCount"] == 2 and not result["partial"], result
    assert result["scrollHeight"] > result["clientHeight"], result
    assert result["checked"] == 2, result

    page.locator(".zone-check-list").evaluate("el => { el.scrollTop=el.scrollHeight; }")
    last_row = page.locator(".zone-checks label").last
    assert last_row.is_visible()
    reaches_last_row = page.locator(".zone-check-list").evaluate(
        "el => {const row=el.lastElementChild.getBoundingClientRect();"
        "const clip=el.getBoundingClientRect();return row.top>=clip.top&&row.bottom<=clip.bottom;}"
    )
    assert reaches_last_row
    assert page.locator(".zone-checks input:checked").count() == 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    entities = json.loads((ROOT / "shared_context.json").read_text())["entities"]
    credentials = json.loads((FRONTEND / ".local" / "validation-secrets.json").read_text())
    admin = next(user for user in entities["User"] if user["role"] == "ADMIN")
    strategy_id = entities["Strategy"][0]["strategyId"]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
            page = context.new_page()
            login(page, base_url, "audit-layout-" + uuid.uuid4().hex, admin, credentials[admin["account"]])
            page.goto(f"{base_url}/?reference=1&capture=audit-layout#{'/audit'}", wait_until="networkidle")
            page.locator(".audit-filters").wait_for()
            assert_audit_filter_fits(page)
            page.get_by_label("开始日期").fill("2026-06-01")
            page.get_by_label("结束日期").fill("2026-07-28")
            page.get_by_role("button", name="查询").click()
            assert page.get_by_label("开始日期").input_value() == "2026-06-01"
            assert page.locator(".audit-list tbody tr").count() == 15

            page.set_viewport_size({"width": 1024, "height": 768})
            assert_audit_filter_fits(page)
            page.set_viewport_size({"width": 650, "height": 768})
            assert_audit_filter_fits(page)
            context.close()

            context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
            page = context.new_page()
            capture = "strategy-layout-" + uuid.uuid4().hex
            login(page, base_url, capture, admin, credentials[admin["account"]])
            page.goto(f"{base_url}/?reference=1&capture={capture}#/strategies/{strategy_id}/edit", wait_until="networkidle")
            page.locator(".zone-checks").wait_for()
            assert_strategy_rows_are_whole_and_scrollable(page)

            time_fields = page.locator('.strategy-edit input[type="time"]')
            assert time_fields.count() == 2
            assert [time_fields.nth(i).input_value() for i in range(2)] == ["05:30", "18:20"]
            time_fields.nth(0).fill("06:15")
            assert time_fields.nth(0).input_value() == "06:15"
            time_fields.nth(0).fill("05:30")
            unavailable = page.locator('.auto-row input[aria-describedby="auto-execution-unavailable"]')
            assert unavailable.is_disabled()
            assert page.locator("#auto-execution-unavailable").inner_text()
            assert "visually-hidden" in page.locator("#auto-execution-unavailable").get_attribute("class")
            context.close()
        finally:
            browser.close()

    print("Audit filter layout, date editing, strategy zone scroll, and stored time values passed")


if __name__ == "__main__":
    main()
