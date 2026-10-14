"""Private subprocess boundary for the pinned upstream. Not a general CLI/MCP server.

The parent supplies an isolated HOME and one account's temporary cookie file.
No arbitrary module/function names, shell commands, or transaction operations are accepted.
"""
from __future__ import annotations

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
    if operation not in READS | WRITES:
        raise ValueError("operation not allowed")
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


def main() -> None:
    try:
        request = json.loads(sys.stdin.read(250_000))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            data = dispatch(request["operation"], request["payload"])
        output = {"ok": True, "data": data}
    except Exception as exc:
        text = str(exc).lower()
        code = "upstream_error"
        if any(x in text for x in ("rgv587", "验证码", "安全验证", "异常访问", "风控", "punish", "user_validate")):
            code = "risk_control"
        elif getattr(exc, "exit_code", 0) == 77:
            code = "auth_required"
        elif isinstance(exc, (ImportError, ModuleNotFoundError)):
            code = "dependency_missing"
        output = {"ok": False, "code": code, "exception_type": type(exc).__name__}
    print(json.dumps(output, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
