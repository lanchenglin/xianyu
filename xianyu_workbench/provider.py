from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager, suppress
from pathlib import Path

from filelock import FileLock, Timeout

from .config import Settings
from .db import DB
from .security import Vault, canonical, redact, strict_json


class Problem(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class Provider:
    """One bounded account operation at a time; never retries a write."""
    def __init__(self, settings: Settings, db: DB, vault: Vault):
        self.s, self.db, self.vault = settings, db, vault
        self.lock_path = str(settings.data_dir / "operations.lock")
        self._selected = threading.local()

    @contextmanager
    def selected_message(self, action_id: str):
        """One-use internal dispatch scope, entered only after queue preflight."""
        self._selected.action_id = action_id
        try:
            yield
        finally:
            self._selected.action_id = None

    def _authorize_message(self, account, payload, expected_binding):
        from .message_send import binding
        from .security import digest
        current = binding(self, account)
        if expected_binding != current:
            raise Problem('send_binding_changed', '审批绑定缺失或已改变，禁止发送', 409)
        action_id = getattr(self._selected, 'action_id', None)
        self._selected.action_id = None
        row = self.db.one('SELECT * FROM actions WHERE id=?', (action_id,)) if action_id else None
        if not row or row['state'] != 'running' or row['kind'] != 'message.send' or row['account_id'] != account['id'] or row['mode'] != 'live' or not row['approved_at'] or row['expires'] <= time.time():
            raise Problem('send_authorization_required', '必须由管理员指定已批准单条队列操作', 409)
        frozen = self.vault.open(row['payload'])
        if (frozen != {**payload, '_binding': current} or row['digest'] != digest(
                {'account_id': account['id'], 'kind': 'message.send', 'payload': frozen, 'mode': 'live'})):
            raise Problem('send_authorization_required', '发送参数与冻结审批不符', 409)

    def account(self, account_id: str) -> dict:
        account = self.db.one("SELECT * FROM accounts WHERE id=?", (account_id,))
        if not account:
            raise Problem("not_found", "账号不存在", 404)
        return account

    def call(self, account_id: str, operation: str, payload: dict, *, write: bool = False, expected_binding: dict | None = None):
        expected_write = operation in {"message.send", "item.publish", "item.delete"}
        if operation not in {"search", "orders", "inventory", "messages", "item", "chats", "history", "message.send", "item.publish", "item.delete"} or write != expected_write:
            raise Problem("unsupported", "该操作没有开放；交易操作必须在闲鱼人工完成", 403)
        if operation in {'orders', 'inventory', 'messages'} and payload:
            raise Problem('invalid_request', '样本同步不接受 URL、脚本或分页参数', 422)
        try:
            with FileLock(self.lock_path, timeout=0.1):
                account = self.account(account_id)
                if account['mode'] == 'live' and operation == 'message.send':
                    self._authorize_message(account, payload, expected_binding)
                elif expected_binding is not None:
                    from .message_send import binding
                    if operation != 'message.send' or binding(self, account) != expected_binding:
                        raise Problem('send_binding_changed', '审批绑定已改变，禁止发送', 409)
                if account["paused"]:
                    raise Problem("account_paused", "账号已暂停：" + account["pause_reason"], 409)
                if operation in {'messages', 'message.send'}:
                    state = self.db.one('SELECT takeover FROM message_observation WHERE account_id=?', (account_id,))
                    if state and state['takeover']:
                        raise Problem('human_takeover', '人工已接管，禁止新消息操作；已发出的操作无法撤回', 409)
                if account["mode"] == "demo":
                    return self.demo(operation, payload)
                if not self.s.live_enabled:
                    raise Problem("live_disabled", "真实执行未启用；由部署者设置 XY_LIVE_ENABLED=true", 409)
                if operation == "item.publish":
                    raise Problem("publish_snapshot_unavailable", "本地预览不等于真实协议已验证；真实发布执行器未开放", 409)
                if operation == 'item.delete':
                    raise Problem('goods_executor_disabled', '真实商品写执行器未开放；删除不能代替普通下架', 409)
                if not self.s.browser_cdp_endpoint and not account["secret"]:
                    raise Problem("auth_required", "请管理员导入此账号的登录态", 409)
                now = time.time()
                interval = self.s.write_interval if write else self.s.read_interval
                previous = account["last_write"] if write else account["last_call"]
                if now - previous < interval:
                    raise Problem("rate_limited", f"请求过快，请在 {int(interval - (now - previous)) + 1} 秒后重新检查", 429)
                self.db.execute("UPDATE accounts SET last_call=? WHERE id=?", (now, account_id))
                if write:
                    self.db.execute("UPDATE accounts SET last_write=? WHERE id=?", (now, account_id))
                return self._live(account, operation, payload, write=write)
        except Timeout as exc:
            raise Problem("busy", "账号操作队列正在执行其他任务，请稍后再试", 409) from exc

    def _live(self, account: dict, operation: str, payload: dict, *, write: bool):
        if operation in {'orders', 'inventory', 'messages'} and not self.s.browser_cdp_endpoint:
            raise Problem('cdp_required', '单页样本同步仅支持管理员绑定的 CDP 账号', 409)
        edit_transport = operation in {'edit.read', 'edit.detail', 'edit.recommend', 'edit.submit'}
        if edit_transport:
            action_id = getattr(self._selected, 'edit_action', None)
            self._selected.edit_action = None
            row = self.db.one('SELECT * FROM actions WHERE id=?', (action_id,)) if action_id else None
            if (not self.s.live_enabled or not self.s.edit_enabled or not row
                    or row['state'] != 'running' or row['kind'] != 'item.edit' or not row['approved_at']
                    or row['account_id'] != account['id'] or row['expires'] <= time.time()
                    or account['paused'] or account['mode'] != 'live' or write != (operation == 'edit.submit')):
                raise Problem('edit_authorization_required', '编辑传输仅限指定队列执行器', 409)
            if operation == 'edit.recommend':
                from .edit_labels import frozen_requests
                frozen = self.vault.open(row['payload']).get('_edit_snapshot', {})
                protocol = frozen.get('protocol', {})
                if not protocol.get('label_dependency'):
                    raise Problem('edit_authorization_required', '未批准推荐依赖', 409)
                allowed = [{'item_id': protocol['item_id'], 'api_version': '2.0', 'template': request}
                           for request in frozen_requests(protocol, frozen.get('label_codes', []))]
                if not any(canonical(payload) == canonical(request) for request in allowed):
                    raise Problem('edit_authorization_required', '推荐请求不匹配冻结审批', 409)
        publish_transport = operation in {'publish.upload', 'publish.submit', 'publish.readback'}
        if publish_transport:
            action_id = getattr(self._selected, 'publish_action', None)
            self._selected.publish_action = None
            row = self.db.one('SELECT * FROM actions WHERE id=?', (action_id,)) if action_id else None
            if (not self.s.live_enabled or not self.s.publish_enabled or not row
                    or row['state'] != 'running' or row['kind'] != 'item.publish'
                    or row['account_id'] != account['id'] or row['expires'] <= time.time()):
                raise Problem('publish_authorization_required', '发布传输仅限指定队列执行器', 409)
        cookie_send = bool((self.s.browser_cdp_endpoint and self.s.message_send_enabled and operation == 'message.send') or publish_transport or edit_transport)
        if self.s.browser_cdp_endpoint:
            if operation not in {'search', 'orders', 'inventory', 'messages'} and not cookie_send:
                raise Problem('cdp_search_only', 'CDP 仅支持搜索、订单、本人商品和末条消息样本；写操作未开放', 409)
            if not (publish_transport or edit_transport) and (account['id'] != self.s.browser_cdp_account_id or account['uid'] != self.s.browser_cdp_uid):
                raise Problem('cdp_binding_mismatch', 'CDP 固定账号绑定不匹配，拒绝执行', 409)
        home = self.s.data_dir / "runtime" / account["id"]
        private = home / ".goofish-cli"
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        home.chmod(0o700)
        private.chmod(0o700)
        cookie_file = private / "cookies.json"
        if not self.s.browser_cdp_endpoint or cookie_send:
            if not account['secret']:
                raise Problem('auth_required', '独立发送登录态缺失，请管理员导入同账号 Cookie', 409)
            cookies = self.vault.open(account["secret"])
            if cookies.get("unb") != account["uid"]:
                raise Problem("account_mismatch", "登录态所属账号不一致，拒绝执行", 409)
            fd = os.open(cookie_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(canonical(cookies))
        cancel_file = private / ('cancel-' + uuid.uuid4().hex)
        safe_keys = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "DISPLAY",
                     "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XAUTHORITY", "LANG", "LC_ALL",
                     "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "LOCALAPPDATA", "TMPDIR"}
        env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
        env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONUTF8": "1",
                    'XY_BRIDGE_CANCEL_FILE': str(cancel_file), "GOOFISH_NO_CHROME_BOOTSTRAP": "1",
                    "GOOFISH_HEADLESS": "0",
                    'XY_BROWSER': self.s.browser, 'XY_BROWSER_EXECUTABLE': self.s.browser_executable,
                    'XY_BROWSER_CDP_ENDPOINT': self.s.browser_cdp_endpoint,
                    'XY_BROWSER_CDP_ACCOUNT_ID': self.s.browser_cdp_account_id,
                    'XY_BROWSER_CDP_UID': self.s.browser_cdp_uid,
                    'XY_MESSAGE_SEND_ENABLED': 'true' if cookie_send and not (publish_transport or edit_transport) else 'false',
                    'XY_EDIT_ENABLED': 'true' if edit_transport else 'false',
                    'XY_PUBLISH_ENABLED': 'true' if publish_transport else 'false',
                    'XY_OPERATION_ACCOUNT_ID': account['id'], 'XY_OPERATION_UID': account['uid']})
        if not self.s.browser_cdp_endpoint or cookie_send:
            env['GOOFISH_COOKIES_PATH'] = str(cookie_file)
        command = [self.s.upstream_python or sys.executable, "-u", "-m", "xianyu_workbench.bridge"]
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                       env=env, cwd=home, start_new_session=os.name != "nt")
            try:
                if operation == 'edit.recommend':
                    from .edit_labels import bounded_communicate
                    try:
                        stdout = bounded_communicate(process, canonical({'operation': operation, 'payload': payload}), self.s.operation_timeout)
                    except (ValueError, UnicodeError):
                        raise Problem('upstream_error', '推荐读取超过限额或编码无效，未提交编辑', 502)
                else:
                    stdout, _ = process.communicate(canonical({"operation": operation, "payload": payload}),
                                                    timeout=self.s.operation_timeout)
            except subprocess.TimeoutExpired:
                if operation == 'edit.recommend':
                    raise Problem('timeout', '推荐读取超时，未提交编辑', 504)
                # Cross-platform cooperative cancellation; do not kill the CDP transport
                # before the bridge has unwound its owned task page.
                with suppress(OSError):
                    cancel_file.touch(mode=0o600)
                try:
                    process.communicate(timeout=8)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        with suppress(OSError, subprocess.TimeoutExpired):
                            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
                    else:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                    with suppress(subprocess.TimeoutExpired):
                        process.communicate(timeout=5)
                raise Problem("uncertain" if write else "timeout", "执行超时；写操作结果不确定，禁止自动重试，请先在闲鱼核对", 504)
            if len(stdout) > 5_000_000:
                raise Problem("uncertain" if write else "upstream_error", "上游返回过大，结果需人工核实", 502)
            try:
                output = strict_json(stdout)
            except (ValueError, TypeError):
                raise Problem("uncertain" if write else "upstream_error", "上游返回无法解析，未记录原始输出以保护登录态", 502)
            if process.returncode or not output.get("ok"):
                code = output.get("code", "upstream_error")
                if code in ("risk_control", "auth_required"):
                    self.db.execute("UPDATE accounts SET paused=1,pause_reason=? WHERE id=?", (code, account["id"]))
                messages = {"risk_control": "平台要求安全验证，已暂停账号，请自行验证后人工恢复",
                            "auth_required": "登录态失效，已暂停账号，请重新导入",
                            'browser_not_found': '未发现所选 Google Chrome / Chromium；请管理员安装或配置 XY_BROWSER_EXECUTABLE，并运行 doctor',
                            'browser_path_invalid': '指定浏览器路径不可执行；请管理员检查 XY_BROWSER_EXECUTABLE，未回退其他浏览器',
                            'browser_config_invalid': '浏览器配置无效；XY_BROWSER 仅允许 auto/chrome/chromium',
                            'cdp_search_only': 'CDP 仅开放搜索及订单/商品/末条消息样本；item、历史及所有写操作均拒绝',
                            'cdp_binding_mismatch': 'CDP 管理员账号绑定不匹配，已停止',
                            'cdp_identity_mismatch': 'CDP 登录态缺失或账号不符，请管理员人工核对；不会注入 Cookie',
                            'cdp_context_ambiguous': 'CDP 有多个或没有 context，无法确认账号，已停止',
                            'cdp_unavailable': '本机 CDP 连接失败或断开，未切换浏览器；请管理员检查独立浏览器',
                            'dependency_missing': '缺少真实连接依赖，请安装 .[live] 和系统 Chrome / Chromium / Node.js'}
                raise Problem(code, messages.get(code, "上游操作异常；写操作可能已发出，请先在闲鱼核实"), 502)
            return redact(output["data"])
        finally:
            # Never retain readable login cookies at rest. Crash residue is removed at startup.
            cancel_file.unlink(missing_ok=True)
            if not self.s.browser_cdp_endpoint or cookie_send:
                cookie_file.unlink(missing_ok=True)
                (private / 'im_token.json').unlink(missing_ok=True)
            shutil.rmtree(private / "profiles", ignore_errors=True)

    @staticmethod
    def demo(operation: str, payload: dict):
        if operation == 'messages':
            return {'items': [{'message_id': '987654', 'cid': '123', 'sender_uid': '22',
                    'created_at': 1780000000000, 'direction': 'incoming', 'body': None,
                    'body_status': 'unavailable', 'recipient_verified': False}],
                    'source': 'demo', 'partial': True, 'completion': 'last_message_samples',
                    'has_more': None, 'cursor_error': 'history_not_collected', 'reported_total': None, 'demo': True}
        if operation in {'orders', 'inventory'}:
            item = ({'order_id': '900001', 'item_id': '100001', 'status': 'DEMO',
                     'created_at': '演示时间', 'status_text': '演示订单，非真实交易'} if operation == 'orders' else
                    {'item_id': '100001', 'status': 0, 'price': '12.30', 'title': '[演示] 本人商品样本'})
            return {'items': [item], 'source': 'demo', 'partial': True, 'completion': 'single_page',
                    'has_more': None, 'cursor_error': 'pagination_semantics_unknown' if operation == 'orders' else None,
                    'reported_total': None, 'demo': True}
        if operation == "search":
            seed = int(hashlib.sha256(payload["query"].encode()).hexdigest()[:8], 16)
            items = [{"item_id": str(100000 + seed % 10000 + i), "title": f"[演示] {payload['query']} 样例 {i+1}",
                      "price": str(800 + i * 150), "location": ("福建 福州", "福建 厦门", "浙江 杭州")[i % 3],
                      "condition": "仅演示数据，不代表实际成色", "seller_id": "10001", "url": ""}
                     for i in range(min(payload.get("limit", 20), 6))]
            return {"items": items, "total": len(items), "demo": True}
        if operation == "item":
            return {"item_id": payload["item_id"], "title": "[演示] 本人商品", "description": "此条为模拟商品",
                    "price": "1280", "seller_id": "99999", "status": "演示在售", "demo": True}
        if operation == "chats":
            return {"sessions": [{"session_id": "demo-chat", "peer_user_id": "10001", "peer_nick": "演示买家",
                                   "last_msg": "你好，商品还有吗？", "unread": 1}], "demo": True}
        if operation == "history":
            return [{"send_user_id": "10001", "send_user_name": "演示买家", "message": "你好，商品还有吗？", "demo": True}]
        if operation == "message.send":
            return {"ok": True, "mid": "demo-not-sent", "demo": True, "notice": "演示模式，未发送到闲鱼"}
        if operation == "item.publish":
            return {"ok": True, "item_id": "99999001", "demo": True, "notice": "演示模式，未发布到闲鱼"}
        if operation == "item.delete":
            return {"ok": True, "item_id": payload["item_id"], "demo": True, "notice": "演示模式，未删除闲鱼商品"}
        raise Problem("unsupported", "不支持的操作", 501)


def asset_path(settings: Settings, row: dict) -> Path:
    root = (settings.data_dir / "assets").resolve()
    path = (root / row["filename"]).resolve()
    if path.parent != root or not path.is_file():
        raise Problem("asset_invalid", "图片不存在或越过素材目录", 409)
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise Problem("asset_changed", "图片已被修改，请重新上传并审批", 409)
    return path
