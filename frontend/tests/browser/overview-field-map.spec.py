"""Regress the Overview map against newly created and scoped fields.

Run: python3 tests/browser/overview-field-map.spec.py --url http://127.0.0.1:5188
Requires a running Vite server, validation credentials, Playwright Python, and Chromium.
All browser data is isolated in temporary contexts.
"""

import argparse
import json
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = Path(__file__).resolve().parents[2]


def login(page, base_url, capture, user, password):
    page.goto(f"{base_url}/?reference=1&capture={capture}#/login", wait_until="networkidle")
    page.locator("#login-account").fill(user["account"])
    page.locator("#login-password").fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(lambda url: url.endswith("#/overview"))
    page.locator(".map-panel").wait_for()


def seed_context(context, entities):
    snapshot = {
        "schemaVersion": 1,
        "revision": 0,
        "entities": entities,
        "requests": {},
        "committedAt": None,
    }
    encoded = json.dumps(snapshot, ensure_ascii=False)
    context.add_init_script(
        "localStorage.setItem('irrigation.reference.snapshot.v1', "
        + json.dumps(encoded)
        + ");"
    )


def create_field(page, name):
    page.goto(f"{page.url.split('#')[0]}#/fields/new", wait_until="networkidle")
    page.locator(".form-field").filter(has_text="田块名称").locator("input").fill(name)
    number_inputs = page.locator(".field-edit .form-grid input[type=number]")
    number_inputs.nth(0).fill("2.5")
    number_inputs.nth(1).fill("115.57001")
    number_inputs.nth(2).fill("37.54001")
    page.locator(".form-field").filter(has_text="土壤类型").locator("select").select_option(index=1)
    page.locator(".form-field").filter(has_text="负责人").locator("select").select_option(index=1)
    page.locator(".form-actions .btn-primary").click()
    page.get_by_text(name, exact=True).wait_for()
    return page.url.rsplit("/", 1)[-1]


def test_new_field_is_reachable_on_a_second_map_page(browser, base_url, credentials, admin):
    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    page = context.new_page()
    capture = "field-map-" + uuid.uuid4().hex
    login(page, base_url, capture, admin, credentials[admin["account"]])
    assert page.locator(".field-polygon").count() == 15
    assert page.get_by_role("button", name="下一页田块").count() == 0

    field_name = "新增边界田块"
    field_id = create_field(page, field_name)
    page.goto(f"{base_url}/?reference=1&capture={capture}#/overview", wait_until="networkidle")
    page.locator(".field-polygon").first.wait_for()

    next_page = page.get_by_role("button", name="下一页田块")
    assert next_page.is_visible(), "新增第 16 块后总览地图应提供翻页入口"
    next_page.click()
    new_field = page.get_by_role("link", name=f"{field_name}，查看田块档案")
    assert new_field.is_visible(), "新增田块应出现在地图后续页"
    new_field.click()
    page.wait_for_url(lambda url: url.endswith(f"#/fields/{field_id}"))
    assert page.get_by_text(field_name, exact=True).is_visible()

    page.goto(f"{base_url}/?reference=1&capture={capture}#/overview", wait_until="networkidle")
    page.get_by_role("button", name="下一页田块").click()
    page.get_by_role("link", name=f"{field_name}，查看田块档案").focus()
    page.get_by_role("link", name=f"{field_name}，查看田块档案").press("Enter")
    page.wait_for_url(lambda url: url.endswith(f"#/fields/{field_id}"))
    context.close()


def test_partially_authorized_and_unmapped_fields_render(browser, base_url, credentials, source_entities):
    manager_entities = json.loads(json.dumps(source_entities))
    manager = next(user for user in manager_entities["User"] if user["role"] == "MANAGER")
    manager["fieldIds"] = [manager_entities["Field"][-1]["fieldId"]]

    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    seed_context(context, manager_entities)
    page = context.new_page()
    login(page, base_url, "partial-" + uuid.uuid4().hex, manager, credentials[manager["account"]])
    assert page.locator(".field-polygon").count() == 1, "地图应展示当前授权的单个田块"
    context.close()

    farm_entities = json.loads(json.dumps(source_entities))
    admin = next(user for user in farm_entities["User"] if user["role"] == "ADMIN")
    new_farm_id = "farm-with-unmapped-field"
    new_field_id = "field-without-reference-slot"
    farm_entities["Farm"][0]["farmId"] = new_farm_id
    admin["farmId"] = new_farm_id
    admin["fieldIds"] = [new_field_id]
    field = dict(farm_entities["Field"][0])
    field.update(fieldId=new_field_id, code="field-without-reference-slot", farmId=new_farm_id, name="无参考布局田块")
    farm_entities["Field"] = [field]

    context = browser.new_context(viewport={"width": 1536, "height": 1024}, locale="zh-CN", timezone_id="Asia/Shanghai")
    seed_context(context, farm_entities)
    page = context.new_page()
    login(page, base_url, "unmapped-" + uuid.uuid4().hex, admin, credentials[admin["account"]])
    assert page.locator(".field-polygon").count() == 1, "没有共享参考田块 ID 时，授权田块仍应获得图形位置"
    unmapped_field = page.get_by_role("link", name="无参考布局田块，查看田块档案")
    assert unmapped_field.is_visible()
    unmapped_field.focus()
    unmapped_field.press("Enter")
    page.wait_for_url(lambda url: url.endswith(f"#/fields/{new_field_id}"))
    context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    source_entities = json.loads((ROOT / "shared_context.json").read_text())["entities"]
    credentials = json.loads((FRONTEND / ".local" / "validation-secrets.json").read_text())
    admin = next(user for user in source_entities["User"] if user["role"] == "ADMIN")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            test_new_field_is_reachable_on_a_second_map_page(browser, base_url, credentials, admin)
            test_partially_authorized_and_unmapped_fields_render(browser, base_url, credentials, source_entities)
        finally:
            browser.close()
    print("Overview field map: new field pagination, partial authorization, and unmapped field checks passed")


if __name__ == "__main__":
    main()
