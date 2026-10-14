"""Demo-only browser smoke test. No real account, cookies, model, or marketplace I/O.

Install test browsers in a PRIVATE test directory first:
  PLAYWRIGHT_BROWSERS_PATH=/tmp/xy-test-browsers python -m playwright install chromium
  PLAYWRIGHT_BROWSERS_PATH=/tmp/xy-test-browsers python scripts/smoke_ui.py
On PowerShell set $env:PLAYWRIGHT_BROWSERS_PATH instead. Do not use the shared cache.
"""
from __future__ import annotations

import os
import socket
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
                    browser = pw.chromium.launch(headless=True)
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
                    page.locator('[data-page="search"]').click()
                    page.locator('#search-form input[name="query"]').fill("显卡")
                    page.locator("#search-form .primary").click()
                    expect(page.locator("#search-results .item-card")).to_have_count(6)
                    expect(page.locator("#search-summary")).to_contain_text("演示")
                    page.locator("#create-monitor").click()
                    expect(page.locator("#toast")).to_contain_text("监控已创建")
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
                    page.locator('[data-page="listings"]').click()
                    page.locator('#listing-form input[name="title"]').fill("UI 演示商品")
                    page.locator('#listing-form textarea[name="desc"]').fill("仅用于本地演示，不发布到闲鱼")
                    page.locator('#listing-form input[name="price"]').fill("19.99")
                    picture = directory / "sample.png"
                    Image.new("RGB", (100, 80), "white").save(picture)
                    page.locator("#listing-images").set_input_files(picture)
                    expect(page.locator("#image-previews img")).to_have_count(1)
                    page.locator("#listing-form .primary").click()
                    expect(page.locator("#toast")).to_contain_text("待你审批")
                    page.locator('[data-page="queue"]').click()
                    expect(page.locator("#queue-list .previews img")).to_have_count(1)
                    page.once("dialog", lambda dialog: dialog.accept("确认执行"))
                    page.locator("#queue-list button.primary").first.click()
                    for _ in range(40):
                        catalog = client.get("/api/catalog").json()
                        if catalog:
                            break
                        time.sleep(0.2)
                    assert catalog and catalog[0]["data"]["title"] == "UI 演示商品"
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.locator('[data-page="overview"]').click()
                    expect(page.locator("#page-overview")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Mobile horizontal overflow"
                    assert not errors, errors
                    page.locator("#logout").click()
                    expect(page.locator("#login")).to_be_visible()
                    browser.close()
            print("UI smoke passed: login, account, search, monitor, chat, approvals, image upload, publish, mobile, logout")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
