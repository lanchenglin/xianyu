"""Private subprocess boundary for the pinned upstream. Not a general CLI/MCP server.

The parent supplies an isolated HOME and one account's temporary cookie file.
No arbitrary module/function names, shell commands, or transaction operations are accepted.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import io
import json
import sys
from decimal import Decimal

READS = {
    "search": ("search.search", "search"),
    "item": ("item.view", "view"),
    "chats": ("message.list_chats", "list_chats"),
    "history": ("message.history", "history"),
}
WRITES = {
    "message.send": ("message.send", "send"),
    "item.publish": ("item.publish", "publish"),
    "item.delete": ("item.delete", "delete"),
}


def dispatch(operation: str, payload: dict):
    if operation in {'publish.upload', 'publish.submit', 'publish.readback'}:
        return dispatch_publish(operation, payload)
    if operation == 'message.send':
        from .models import MessageIn
        if set(payload) != {'cid', 'toid', 'text'}:
            raise ValueError('text_send_payload')
        validated = MessageIn.model_validate(payload).model_dump()
        if validated != payload:
            raise ValueError('text_send_payload')
    if operation in {'orders', 'inventory', 'messages'}:
        if payload:
            raise ValueError('operation takes no parameters')
        from .operations_browser import collect
        return collect(operation)
    if operation not in READS | WRITES:
        raise ValueError("operation not allowed")
    from .browser_adapter import install
    install(operation)
    from goofish_cli.core import mtop
    from loguru import logger

    logger.remove()  # Do not forward upstream logs/cookies into the application or LLM.
    original = mtop.call

    def once(*args, **kwargs):
        kwargs["_auto_refresh"] = False
        return original(*args, **kwargs)

    mtop.call = once
    module, name = (READS | WRITES)[operation]
    function = getattr(importlib.import_module("goofish_cli.commands." + module), name)
    if operation == "item.publish":
        # Upstream computes int(price * 100). Decimal prevents a float rounding cent loss.
        payload["price"] = Decimal(str(payload["price"]))
        payload["post_price"] = Decimal(str(payload.get("post_price", 0)))
    return function(**payload)


def dispatch_publish(operation, payload):
    """Private fixed transport; no browser, recommendation, default lookup or retry."""
    import os
    from pathlib import Path
    if os.environ.get('XY_PUBLISH_ENABLED') != 'true':
        raise ValueError('publish_disabled')
    from goofish_cli.core import Session
    from goofish_cli.core.mtop import call
    from goofish_cli.core.session import USER_AGENT
    session = Session.load()
    if not session.unb or session.unb != os.environ.get('XY_OPERATION_UID'):
        raise ValueError('account_mismatch')
    if operation == 'publish.upload':
        import hashlib
        content = Path(payload['path']).read_bytes()
        if hashlib.sha256(content).hexdigest() != payload.get('sha256'):
            raise ValueError('asset_changed')
        with io.BytesIO(content) as image:
            response = session.http.post('https://stream-upload.goofish.com/api/upload.api',
                headers={'accept': '*/*', 'origin': 'https://www.goofish.com',
                         'referer': 'https://www.goofish.com/', 'user-agent': USER_AGENT},
                params={'floderId': '0', 'appkey': 'xy_chat', '_input_charset': 'utf-8'},
                files={'file': ('image.png', image, 'image/png')}, timeout=60, allow_redirects=False)
            response.raise_for_status()
            obj = response.json().get('object') or {}
        width, height = map(int, str(obj.get('pix', '0x0')).split('x'))
        return {'url': obj.get('url', ''), 'width': width, 'height': height}
    # requests follows redirects by default: suppress all redirects, including 307 POST replay.
    original_post = session.http.post
    def post_once(*args, **kwargs):
        kwargs['allow_redirects'] = False
        return original_post(*args, **kwargs)
    session.http.post = post_once
    return call(session,
        api='mtop.idle.pc.idleitem.publish' if operation == 'publish.submit' else 'mtop.taobao.idle.pc.detail',
        data=payload, version='1.0',
        spm_cnt='a21ybx.publish.0.0' if operation == 'publish.submit' else 'a21ybx.item.0.0',
        _auto_refresh=False)


def main() -> None:
    try:
        request = json.loads(sys.stdin.read(250_000))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            data = dispatch(request["operation"], request["payload"])
        output = {"ok": True, "data": data}
    except asyncio.CancelledError:
        output = {'ok': False, 'code': 'timeout'}
    except Exception as exc:
        text = str(exc).lower()
        from .browser_config import BrowserError
        code = "upstream_error"
        if isinstance(exc, BrowserError):
            code = exc.code
        elif any(x in text for x in ("rgv587", "验证码", "安全验证", "异常访问", "风控", "punish", "user_validate")):
            code = "risk_control"
        elif getattr(exc, "exit_code", 0) == 77:
            code = "auth_required"
        elif isinstance(exc, (ImportError, ModuleNotFoundError)):
            code = "dependency_missing"
        output = {"ok": False, "code": code, "exception_type": type(exc).__name__}
    print(json.dumps(output, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
