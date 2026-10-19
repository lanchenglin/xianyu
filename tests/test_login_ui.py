"""Event-gated login initialization against a disposable local API only."""
import asyncio
import os

import pytest

from tests.test_mcp_stdio import api_server as api_server


@pytest.mark.parametrize('viewport', [{'width': 1440, 'height': 1000}, {'width': 390, 'height': 844}],
                         ids=['desktop', 'mobile'])
@pytest.mark.parametrize('role', ['admin', 'agent'])
@pytest.mark.parametrize('endpoint', ['me', 'accounts', 'dashboard'])
def test_login_keeps_navigation_hidden_until_initialized(api_server, viewport, role, endpoint):
    executable = os.getenv('XY_TEST_CHROMIUM')
    if not executable:
        pytest.skip('set XY_TEST_CHROMIUM for isolated UI')
    from playwright.async_api import async_playwright, expect

    url, settings, _ = api_server

    async def check():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=executable, headless=True)
            try:
                page = await browser.new_page(viewport=viewport)
                entered, release = asyncio.Event(), asyncio.Event()

                async def gate(route):
                    entered.set()
                    await release.wait()
                    await route.continue_()

                await page.route(f'**/api/{endpoint}', gate)
                await page.goto(url)
                await page.locator('#login-token').fill(getattr(settings, role + '_token'))
                await page.locator('#login-form button').click()
                await asyncio.wait_for(entered.wait(), timeout=5)
                try:
                    await expect(page.locator('#shell')).to_be_hidden()
                    await expect(page.locator('#login')).to_be_visible()
                    await expect(page.locator('#login-form button')).to_be_disabled()
                finally:
                    release.set()
                await expect(page.locator('#shell')).to_be_visible()
                await expect(page.locator('#login')).to_be_hidden()
                await expect(page.locator('#role-badge')).to_have_text('管理员' if role == 'admin' else 'Agent')
                await page.locator('[data-page="listings"]').click()
                await expect(page.locator('#page-listings')).to_be_visible()
                await expect(page.locator('#page-overview')).to_be_hidden()
                for selector in ['#edit-protocol-form textarea', '#daily-publish-status']:
                    if role == 'admin':
                        await expect(page.locator(selector)).to_be_visible()
                    else:
                        await expect(page.locator(selector)).to_be_hidden()
            finally:
                await browser.close()

    asyncio.run(check())


@pytest.mark.parametrize('endpoint', ['me', 'accounts', 'dashboard'])
def test_login_initialization_failure_can_retry(api_server, endpoint):
    executable = os.getenv('XY_TEST_CHROMIUM')
    if not executable:
        pytest.skip('set XY_TEST_CHROMIUM for isolated UI')
    from playwright.async_api import async_playwright, expect

    url, settings, _ = api_server

    async def check():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=executable, headless=True)
            try:
                page = await browser.new_page(viewport={'width': 1440, 'height': 1000})

                async def fail(route):
                    await route.fulfill(status=503, json={'message': 'Fictional initialization failure'})

                await page.route(f'**/api/{endpoint}', fail, times=1)
                await page.goto(url)
                await page.locator('#login-token').fill(settings.admin_token)
                await page.locator('#login-form button').click()
                await expect(page.locator('#login-error')).to_have_text('Fictional initialization failure')
                await expect(page.locator('#shell')).to_be_hidden()
                await expect(page.locator('#login')).to_be_visible()
                await expect(page.locator('#login-form button')).to_be_enabled()
                await page.locator('#login-token').fill(settings.agent_token)
                await page.locator('#login-form button').click()
                await expect(page.locator('#shell')).to_be_visible()
                await expect(page.locator('#login-error')).to_be_empty()
                await expect(page.locator('#role-badge')).to_have_text('Agent')
                await page.locator('[data-page="listings"]').click()
                await expect(page.locator('#page-listings')).to_be_visible()
                await expect(page.locator('#edit-protocol-form')).to_be_hidden()
            finally:
                await browser.close()

    asyncio.run(check())
