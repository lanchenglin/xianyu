"""Offline contracts in CHILD processes. Never loads a user session.

Upstream imports modify subprocess.Popen globally; importing it into the API/MCP
process would break dependencies. This test intentionally uses the production boundary.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from importlib.metadata import distribution

import pytest

if importlib.util.find_spec("goofish_cli") is None:
    pytest.skip("Install .[live] to check the pinned upstream contract", allow_module_level=True)

PIN = "c2d5a02ad83b18863514389cedf7afbd993b683d"


def isolated(script: str, tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path), GOOFISH_NO_CHROME_BOOTSTRAP="1")
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(script)], text=True,
                            capture_output=True, timeout=30, env=env, check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("module,name,parameters", [
    ("search.search", "search", {"query", "limit"}),
    ("item.view", "view", {"item_id"}),
    ("message.list_chats", "list_chats", {"fetch_num"}),
    ("message.history", "history", {"cid", "limit_per_page"}),
    ("message.send", "send", {"cid", "toid", "text"}),
    ("item.publish", "publish", {"title", "desc", "images", "price", "delivery", "post_price", "can_self_pickup"}),
    ("item.delete", "delete", {"item_id"}),
])
def test_function_contract(module, name, parameters, tmp_path):
    actual = isolated(f"""
        import importlib, inspect, json
        function = getattr(importlib.import_module('goofish_cli.commands.' + {module!r}), {name!r})
        print(json.dumps(list(inspect.signature(function).parameters)))
    """, tmp_path)
    assert parameters.issubset(actual)


def test_installed_commit_is_pinned():
    direct = distribution("goofish-cli").read_text("direct_url.json")
    assert direct, "Install via the pinned .[live] extra, not an unrelated PyPI package"
    data = json.loads(direct)
    assert data.get("vcs_info", {}).get("commit_id") == PIN


def test_upstream_allows_disabling_auth_retries(tmp_path):
    result = isolated("""
        import inspect, json
        from goofish_cli.core.mtop import call
        print(json.dumps(list(inspect.signature(call).parameters)))
    """, tmp_path)
    assert "_auto_refresh" in result


def test_publish_preserves_cents_with_decimal(tmp_path):
    result = isolated("""
        import json
        from decimal import Decimal
        from goofish_cli.commands.item.publish import _build_publish_data
        result = _build_publish_data(title='offline test', desc='test description', image_infos=[], price=Decimal('19.99'),
                                     original_price=None, delivery='一口价', post_price=Decimal('2.99'),
                                     can_self_pickup=True,
                                     cat_info={'cat_id': '1', 'cat_name': 'test', 'channel_cat_id': '2', 'tb_cat_id': '3'},
                                     location={})
        print(json.dumps(result))
    """, tmp_path)
    assert result["itemPriceDTO"]["priceInCent"] == "1999"
    assert result["itemPostFeeDTO"]["postPriceInCent"] == "299"
