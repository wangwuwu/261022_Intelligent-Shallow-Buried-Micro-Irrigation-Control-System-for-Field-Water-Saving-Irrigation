"""Exercise the real modal component against a running Vite development server.

Run: python3 tests/browser/modal-close.spec.py --url http://127.0.0.1:5173
Requires the validation environment's Playwright Python package and Chromium.
The harness changes no business entities or browser persistence.
"""

import argparse
import json

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(args.url, wait_until="networkidle")
        results = page.evaluate(
            """async () => {
              const { createApp, h, ref, nextTick } =
                await import('/node_modules/.vite/deps/vue.js');
              const { default: BaseModal } =
                await import('/src/components/BaseModal.vue');
              const settle = async () => {
                await nextTick();
                await new Promise(resolve => setTimeout(resolve, 30));
                await nextTick();
              };
              let sequence = 0;
              async function harness({ busy = false, requestOnly = false } = {}) {
                const title = '受控关闭验证-' + ++sequence;
                const container = document.createElement('div');
                const trigger = document.createElement('button');
                trigger.textContent = '打开验证弹窗';
                document.body.append(trigger, container);
                trigger.focus();
                const accepted = ref(false), open = ref(true);
                let requests = 0, closed = 0;
                const props = {
                  title,
                  busy,
                  onClose: () => closed++,
                  'onUpdate:modelValue': async value => {
                    requests++;
                    await Promise.resolve();
                    if (accepted.value) open.value = value;
                  },
                };
                if (requestOnly) props.onRequestClose = async () => {
                  requests++;
                  await Promise.resolve();
                  if (accepted.value) open.value = false;
                };
                const app = createApp({
                  setup: () => () => h(BaseModal, { ...props, modelValue: open.value },
                    () => h('input', { value: '未保存的输入' })),
                });
                app.mount(container);
                await settle();
                const dialog = () => [...document.querySelectorAll('dialog')]
                  .find(element => element.getAttribute('aria-label') === title);
                return {
                  accepted, open, dialog,
                  get requests() { return requests; },
                  get closed() { return closed; },
                  trigger,
                  cleanup() { app.unmount(); container.remove(); trigger.remove(); },
                };
              }

              const guarded = await harness();
              guarded.dialog().querySelector('[aria-label="关闭"]').click();
              await settle();
              const rejected = {
                passed: guarded.open.value && guarded.dialog()?.open &&
                  guarded.dialog().querySelector('input').value === '未保存的输入' &&
                  guarded.requests === 1 && guarded.closed === 0,
              };
              guarded.dialog().dispatchEvent(new Event('cancel', { cancelable: true }));
              await settle();
              const escapeRejected = {
                passed: guarded.dialog()?.open && guarded.requests === 2 && guarded.closed === 0,
              };
              guarded.accepted.value = true;
              guarded.dialog().querySelector('[aria-label="关闭"]').click();
              await settle();
              const accepted = {
                passed: !guarded.open.value && !guarded.dialog() &&
                  guarded.closed === 1 && document.activeElement === guarded.trigger,
              };
              guarded.cleanup();

              const busy = await harness({ busy: true });
              busy.dialog().dispatchEvent(new Event('cancel', { cancelable: true }));
              await settle();
              const busyBlocked = {
                passed: busy.dialog()?.open && busy.requests === 0 && busy.closed === 0,
              };
              busy.cleanup();

              const controlled = await harness({ requestOnly: true });
              controlled.dialog().querySelector('[aria-label="关闭"]').click();
              await settle();
              const requestOnly = {
                passed: controlled.dialog()?.open && controlled.open.value &&
                  controlled.requests === 1 && controlled.closed === 0,
              };
              controlled.accepted.value = true;
              controlled.dialog().querySelector('[aria-label="关闭"]').click();
              await settle();
              requestOnly.passed = requestOnly.passed && !controlled.open.value &&
                !controlled.dialog() && controlled.requests === 2 && controlled.closed === 1;
              controlled.cleanup();

              return { rejected, escapeRejected, accepted, busyBlocked, requestOnly };
            }"""
        )
        browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    assert all(result["passed"] for result in results.values()), results


if __name__ == "__main__":
    main()
