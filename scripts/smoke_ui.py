"""Demo-only browser smoke test. No real account, cookies, model, or marketplace I/O.

Install test browsers in a PRIVATE test directory first:
  PLAYWRIGHT_BROWSERS_PATH=/tmp/xy-test-browsers python -m playwright install chromium
  PLAYWRIGHT_BROWSERS_PATH=/tmp/xy-test-browsers python scripts/smoke_ui.py
On PowerShell set $env:PLAYWRIGHT_BROWSERS_PATH instead. Do not use the shared cache.
If download is blocked, XY_TEST_CHROMIUM may point to a locally installed executable;
Playwright still creates a fresh temporary profile, never a user's existing profile.
XY_TEST_SCREENSHOT optionally saves the final demo-only Agent mobile view.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from PIL import Image
from playwright.sync_api import expect, sync_playwright

from xianyu_workbench.cli import initialize


def main():
    with tempfile.TemporaryDirectory(prefix="xy-ui-") as temp:
        directory = Path(temp)
        initialize(directory)
        env = dict(os.environ)
        env.update({k: v for k, v in dotenv_values(directory / ".env").items() if v is not None})
        env["XY_LIVE_ENABLED"] = "false"
        env["XY_WORKER_ENABLED"] = "true"
        env["XY_DATA_DIR"] = str(directory / "data")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen([sys.executable, "-m", "xianyu_workbench.cli", "serve", "--port", str(port)],
                                   cwd=directory, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + env["XY_ADMIN_TOKEN"]}, trust_env=False) as client:
                ready = False
                for _ in range(80):
                    try:
                        ready = client.get("/healthz").status_code == 200
                    except httpx.HTTPError:
                        pass
                    if ready:
                        break
                    time.sleep(0.15)
                assert ready, "Temporary workbench did not start"
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, executable_path=os.getenv("XY_TEST_CHROMIUM") or None)
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto(url)
                    page.locator("#login-token").fill(env["XY_ADMIN_TOKEN"])
                    page.locator("#login-form button").click()
                    expect(page.locator("#shell")).to_be_visible()
                    page.locator('[data-page="accounts"]').click()
                    page.locator('#account-form input[name="label"]').fill("浏览器演示账号")
                    page.locator("#account-form button").click()
                    expect(page.locator("#mode-banner")).to_contain_text("浏览器演示账号")
                    page.locator('[data-page="operations"]').click()
                    page.locator('#sync-messages').click(timeout=3000)
                    expect(page.locator('#messages-samples')).to_contain_text('body unavailable')
                    expect(page.locator('#messages-status')).to_contain_text('部分样本')
                    expect(page.locator('#messages-samples button')).to_have_count(0)
                    expect(page.locator('#observation-status')).to_contain_text('关闭')
                    page.locator('#observation-form input[name="enabled"]').check()
                    page.locator('#observation-form input[name="interval_s"]').fill('300')
                    page.locator('#observation-form button').click()
                    expect(page.locator('#observation-status')).to_contain_text('启用')
                    page.locator('#message-takeover').click()
                    expect(page.locator('#observation-status')).to_contain_text('人工接管')
                    page.locator('#message-release').click()
                    expect(page.locator('#observation-status')).to_contain_text('未接管')
                    page.locator('#faq-form input[name="conversation_ids"]').fill('123@goofish')
                    page.locator('#faq-form input[name="item_ids"]').fill('123')
                    page.locator('#faq-form textarea[name="template"]').fill('您好，请查看商品页面说明。')
                    page.locator('#faq-form input[name="enabled"]').check()
                    page.locator('#faq-form button').click()
                    expect(page.locator('#faq-status')).to_contain_text('send_adapter_unavailable')
                    page.locator('#faq-revoke').click()
                    expect(page.locator('#faq-status')).to_contain_text('disabled')
                    original_account = page.locator('#account-select').input_value()
                    other_account = client.post('/api/accounts', json={'label': '隔离测试账号 B', 'mode': 'demo'}).json()['id']
                    page.reload()
                    page.locator('#login-token').fill(env['XY_ADMIN_TOKEN'])
                    page.locator('#login-form button').click()
                    page.locator('#account-select').select_option(original_account)
                    page.locator('[data-page="operations"]').click()
                    page.locator('#faq-form textarea[name="template"]').fill('账号 A 的未保存内容')
                    page.locator('#account-select').select_option(other_account)
                    expect(page.locator('#faq-form textarea[name="template"]')).to_have_value('')
                    expect(page.locator('#faq-form input[name="enabled"]')).not_to_be_checked()
                    page.locator('#account-select').select_option(original_account)
                    page.locator('[data-page="search"]').click()
                    page.locator('#search-form input[name="query"]').fill("显卡")
                    page.locator("#search-form .primary").click()
                    expect(page.locator("#search-results .item-card")).to_have_count(6)
                    expect(page.locator("#search-summary")).to_contain_text("演示")
                    page.locator("#create-monitor").click()
                    expect(page.locator("#toast")).to_contain_text("监控已创建")
                    page.locator('[data-page="settings"]').click()
                    expect(page.locator('#notification-config-status')).to_contain_text('关闭')
                    page.locator('#notification-form input[name="url"]').fill('https://notify.example.com/events')
                    page.locator('#notification-form input[name="secret"]').fill('fake-test-secret-' + 'x' * 32)
                    page.locator('#notification-form button').click()
                    expect(page.locator('#toast')).to_contain_text('通知配置已保存')
                    expect(page.locator('#notification-form input[name="secret"]')).to_have_value('')
                    page.locator('[data-page="monitors"]').click()
                    expect(page.locator('#notification-list .record')).to_have_count(1, timeout=15000)
                    page.get_by_role('button', name='标为已读', exact=True).click()
                    expect(page.locator('#notification-list')).to_contain_text('已读')
                    page.get_by_role('button', name='归档通知', exact=True).click()
                    expect(page.locator('#notification-list .record')).to_have_count(0)
                    page.locator('[data-page="inbox"]').click()
                    page.locator("#refresh-chats").click()
                    page.locator("#chat-list .record").first.click()
                    expect(page.locator("#chat-history")).to_contain_text("商品还有吗")
                    page.locator("#message-text").fill("这是演示消息，不访问闲鱼。")
                    page.locator("#message-form .primary").click()
                    expect(page.locator("#toast")).to_contain_text("待你审批")
                    page.locator('[data-page="queue"]').click()
                    page.once("dialog", lambda dialog: dialog.accept("确认执行"))
                    page.locator("#queue-list button.primary").first.click()
                    for _ in range(40):
                        actions = client.get("/api/actions").json()
                        if actions and actions[0]["state"] == "simulated":
                            break
                        time.sleep(0.2)
                    assert actions[0]["state"] == "simulated"
                    page.locator("#refresh-queue").click()
                    expect(page.locator("#queue-list")).to_contain_text("演示完成")
                    # Inject an uncertain result into this disposable demo DB only; never enable live.
                    action_id = actions[0]["id"]
                    with sqlite3.connect(directory / "data" / "workbench.db") as db:
                        db.execute("UPDATE actions SET state='unconfirmed' WHERE id=?", (action_id,))
                    original = client.get(f"/api/actions/{action_id}").json()
                    page.locator("#refresh-queue").click()
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.get_by_role("button", name="记录人工核对", exact=True).click()
                    expect(page.locator("#reconcile-dialog")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Reconciliation mobile overflow"
                    expect(page.locator("#reconcile-context")).to_contain_text(action_id)
                    page.locator('#reconcile-form select[name="outcome"]').select_option("observed")
                    evidence = "本地演示人工证据 <img src=x onerror=alert(1)>"
                    page.locator('#reconcile-form textarea[name="evidence"]').fill(evidence)
                    page.locator('#reconcile-form button[type="submit"]').click()
                    expect(page.locator("#reconcile-dialog")).not_to_be_visible()
                    expect(page.locator("#queue-list")).to_contain_text("人工记录：观察到相关平台记录")
                    expect(page.locator("#queue-list")).to_contain_text("结果待核实")
                    expect(page.locator("#queue-list")).to_contain_text(evidence)
                    expect(page.locator("#queue-list img")).to_have_count(0)
                    recorded = client.get(f"/api/actions/{action_id}").json()
                    assert recorded["state"] == original["state"]
                    assert recorded["result"] == original["result"]
                    assert recorded["reconciliation"]["source"] == "manual"
                    assert client.post(f"/api/actions/{action_id}/reconciliation",
                                       headers={"Authorization": "Bearer " + env["XY_AGENT_TOKEN"]},
                                       json={"account_id": original["account_id"], "outcome": "observed",
                                             "evidence": evidence, "idempotency_key": "agent-reconcile-test"}).status_code == 403
                    page.locator('[data-page="listings"]').click()
                    page.locator('#listing-form input[name="title"]').fill("UI 演示商品")
                    page.locator('#listing-form textarea[name="desc"]').fill("仅用于本地演示，不发布到闲鱼")
                    page.locator('#listing-form input[name="price"]').fill("19.99")
                    picture = directory / "sample.png"
                    Image.new("RGB", (100, 80), "white").save(picture)
                    page.locator("#listing-images").set_input_files(picture)
                    expect(page.locator("#image-previews img")).to_have_count(1)
                    page.locator('#save-draft').click()
                    expect(page.locator('#draft-list .record')).to_have_count(1)
                    page.get_by_role('button', name='载入编辑区', exact=True).click()
                    page.locator('#listing-form input[name="title"]').fill('UI 原位编辑商品')
                    page.locator('#save-draft').click()
                    expect(page.locator('#draft-list .record')).to_have_count(1)
                    expect(page.locator('#toast')).to_contain_text('已保存本地草稿')
                    expect(page.locator('#draft-list')).to_contain_text('UI 原位编辑商品')
                    drafts = client.get('/api/drafts').json()
                    assert len(drafts) == 1 and drafts[0]['revision'] == 2
                    # A stale editor must keep the user's text rather than silently overwrite.
                    external = {**drafts[0]['content'], 'title': '另一窗口更新', 'revision': 2}
                    assert client.put('/api/drafts/' + drafts[0]['id'], json=external).status_code == 200
                    page.locator('#save-draft').click()
                    expect(page.locator('#toast')).to_contain_text('草稿已变化')
                    expect(page.locator('#listing-form input[name="title"]')).to_have_value('UI 原位编辑商品')
                    page.locator('[data-page="overview"]').click()
                    page.locator('[data-page="listings"]').click()
                    page.get_by_role('button', name='载入编辑区', exact=True).click()
                    page.locator('#listing-form input[name="title"]').fill('UI 原位编辑商品')
                    page.locator('#save-draft').click()
                    expect(page.locator('#draft-list')).to_contain_text('版本 4')
                    page.locator("#listing-form .primary").click()
                    expect(page.locator("#toast")).to_contain_text("待你审批")
                    page.once('dialog', lambda dialog: dialog.accept())
                    page.get_by_role('button', name='归档草稿', exact=True).click()
                    expect(page.locator('#draft-list')).to_contain_text('已归档')
                    expect(page.get_by_role('button', name='载入编辑区', exact=True)).to_have_count(0)
                    page.locator('[data-page="queue"]').click()
                    expect(page.locator("#queue-list .previews img")).to_have_count(1)
                    page.once("dialog", lambda dialog: dialog.accept("确认执行"))
                    page.locator("#queue-list button.primary").first.click()
                    for _ in range(40):
                        catalog = client.get("/api/catalog").json()
                        if catalog:
                            break
                        time.sleep(0.2)
                    assert catalog and catalog[0]["data"]["title"] == "UI 原位编辑商品"
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.locator('[data-page="overview"]').click()
                    expect(page.locator("#page-overview")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Mobile horizontal overflow"
                    assert not errors, errors
                    page.locator("#logout").click()
                    expect(page.locator("#login")).to_be_visible()
                    page.locator("#login-token").fill(env["XY_AGENT_TOKEN"])
                    page.locator("#login-form button").click()
                    expect(page.locator("#shell")).to_be_visible()
                    page.locator('[data-page="queue"]').click()
                    expect(page.locator("#queue-list")).to_contain_text("人工记录：观察到相关平台记录")
                    expect(page.locator("#queue-list")).not_to_contain_text(evidence)
                    expect(page.get_by_role("button", name="记录人工核对", exact=True)).to_have_count(0)
                    expect(page.get_by_role("button", name="批准这份内容", exact=True)).to_have_count(0)
                    assert not errors, errors
                    screenshot = os.getenv("XY_TEST_SCREENSHOT")
                    if screenshot:
                        page.screenshot(path=screenshot, full_page=True)
                    browser.close()
            print("UI smoke passed: login, account, search, monitor, chat, approvals, manual reconciliation, evidence XSS safety, agent isolation, image upload, publish, mobile, logout")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
