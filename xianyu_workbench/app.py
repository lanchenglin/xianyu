from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from filelock import FileLock
from PIL import Image, ImageOps
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .models import (
    AccountIn,
    ActionIn,
    ApprovalIn,
    AssistIn,
    CookiesIn,
    DraftArchiveIn,
    DraftEditIn,
    DraftIn,
    LLMConfigIn,
    MonitorIn,
    ReconciliationIn,
    SearchIn,
)
from .provider import Problem, asset_path
from .security import canonical, parse_cookies
from .service import Service

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or Settings.load()
    s.validate()
    service = Service(s)

    @asynccontextmanager
    async def lifespan(app):
        # SQLite's queue is atomic, and a process lock prevents duplicate schedulers/recovery.
        with FileLock(str(s.data_dir / "server.lock"), timeout=0):
            service.start()
            try:
                yield
            finally:
                service.close()

    app = FastAPI(title="闲鱼 AI 工作台", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.service = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv("XY_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(","))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 12 * 1024 * 1024:
            return JSONResponse({"code": "body_too_large", "message": "请求最大 12MB"}, status_code=413)
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"code": "bad_origin", "message": "禁止跨站调用"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # FastAPI defaults echo invalid input; never echo cookie/key bodies back into logs/UI.
        return JSONResponse({"code": "invalid_request", "message": "输入参数不合法，请检查必填项与格式",
                             "fields": [list(e["loc"]) for e in exc.errors()]}, status_code=422)

    def role(request: Request):
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        if secrets.compare_digest(token.encode(), s.admin_token.encode()):
            return "admin"
        if secrets.compare_digest(token.encode(), s.agent_token.encode()):
            return "agent"
        raise Problem("unauthorized", "请输入有效的工作台访问令牌", 401)

    def admin(current=Depends(role)):
        if current != "admin":
            raise Problem("forbidden", "只有管理员可以审批、导入账号或修改配置", 403)
        return current

    def check_id(item_id: str):
        if not item_id.isdigit() or len(item_id) > 30:
            raise Problem("invalid_id", "商品 ID 必须是数字", 422)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/me")
    def me(current=Depends(role)):
        return {"role": current, "live_enabled": s.live_enabled, "worker_enabled": s.worker_enabled}

    @app.get("/api/schema")
    def schema(current=Depends(role)):
        return app.openapi()

    @app.get("/api/capabilities")
    def capabilities(current=Depends(role)):
        return {"search": True, "item_detail": True, "existing_chats": True, "message_history": True,
                "send_with_approval": True, "publish_with_approval": True, "delete_with_explicit_approval": True,
                "live_publish": False, "publish_complete_snapshot": False,
                "local_drafts": True, "local_draft_edit": True, "local_draft_archive": True,
                "offline_backup_restore_cli": True, "search_monitors": True, "mcp": True,
                "manual_reconciliation": True, "automatic_receipt_verification": False,
                "reconciliation_policy": {"write_role": "admin", "agent_read": "outcome_time_only",
                                          "eligible_states": ["unconfirmed", "submitted", "blocked"],
                                          "outcomes": ["observed", "not_observed", "unresolved"],
                                          "immutable": True, "retries_operation": False},
                "first_contact": False, "platform_edit_price": False, "platform_relist": False,
                "full_inventory_sync": False, "order_sync": False, "autonomous_reply": False,
                "payment": False, "refund": False, "confirm_receipt": False,
                "notice": "False 表示本版本没有开放，不会伪造成功；交易仅在闲鱼人工完成"}

    @app.get("/api/dashboard")
    def dashboard(current=Depends(role)):
        return {"accounts": service.db.one("SELECT COUNT(*) n FROM accounts")["n"],
                "pending": service.db.one("SELECT COUNT(*) n FROM actions WHERE state='pending'")["n"],
                "paused": service.db.one("SELECT COUNT(*) n FROM accounts WHERE paused=1")["n"],
                "monitors": service.db.one("SELECT COUNT(*) n FROM monitors WHERE enabled=1")["n"],
                "llm_calls": service.db.one("SELECT COUNT(*) n FROM audit WHERE event='llm.started'")["n"],
                "llm_failed": service.db.one("SELECT COUNT(*) n FROM audit WHERE event='llm.failed'")["n"],
                "live_enabled": s.live_enabled, "worker_enabled": s.worker_enabled}

    @app.get("/api/accounts")
    def accounts(current=Depends(role)):
        return service.db.all("SELECT id,label,mode,uid,paused,pause_reason,created FROM accounts ORDER BY created")

    @app.post("/api/accounts", status_code=201)
    def add_account(body: AccountIn, current=Depends(admin)):
        if body.mode == "demo" and body.cookies_json:
            raise Problem("invalid_mode", "演示账号不能导入真实登录态", 422)
        cookies = None
        if body.cookies_json:
            try:
                cookies = parse_cookies(body.cookies_json)
            except (ValueError, TypeError):
                raise Problem("invalid_cookies", "Cookie JSON 不完整或格式错误；需有效 unb 和 _m_h5_tk", 422)
        account_id = uuid.uuid4().hex
        service.db.execute("INSERT INTO accounts(id,label,mode,uid,secret,created) VALUES(?,?,?,?,?,?)",
                           (account_id, body.label, body.mode, "99999" if body.mode == "demo" else (cookies or {}).get("unb", ""),
                            service.vault.seal(cookies) if cookies else None, time.time()))
        service.db.audit(current, "account.created", account_id, {"mode": body.mode})
        return {"id": account_id, "label": body.label, "mode": body.mode}

    @app.post("/api/accounts/{account_id}/cookies")
    def update_cookies(account_id: str, body: CookiesIn, current=Depends(admin)):
        account = service.provider.account(account_id)
        if account["mode"] != "live":
            raise Problem("invalid_mode", "只可向真实账号导入登录态", 422)
        try:
            cookies = parse_cookies(body.cookies_json)
        except (ValueError, TypeError):
            raise Problem("invalid_cookies", "Cookie JSON 不完整或格式错误", 422)
        if account["uid"] and account["uid"] != cookies["unb"]:
            raise Problem("account_mismatch", "不能把另一个闲鱼账号的登录态覆盖到此账号，请新建账号", 409)
        service.db.execute("UPDATE accounts SET secret=?,uid=? WHERE id=?", (service.vault.seal(cookies), cookies["unb"], account_id))
        service.db.audit(current, "account.cookies_updated", account_id)
        return {"ok": True, "notice": "登录态已加密保存；若账号暂停，请核实后手动恢复"}

    @app.post("/api/accounts/{account_id}/pause")
    def pause(account_id: str, current=Depends(admin)):
        service.provider.account(account_id)
        service.db.execute("UPDATE accounts SET paused=1,pause_reason='人工暂停' WHERE id=?", (account_id,))
        service.db.audit(current, "account.paused", account_id)
        return {"ok": True}

    @app.post("/api/accounts/{account_id}/resume")
    def resume(account_id: str, body: ApprovalIn, current=Depends(admin)):
        service.provider.account(account_id)
        service.db.execute("UPDATE accounts SET paused=0,pause_reason='' WHERE id=?", (account_id,))
        service.db.audit(current, "account.resumed", account_id)
        return {"ok": True, "notice": "已恢复；被中断或结果不明的旧操作不会自动重试"}

    @app.post("/api/search")
    def search(body: SearchIn, current=Depends(role)):
        result = service.search(body)
        service.db.audit(current, "search.completed", body.account_id, {"count": result["total"]})
        return result

    @app.get("/api/accounts/{account_id}/items/{item_id}")
    def item(account_id: str, item_id: str, current=Depends(role)):
        check_id(item_id)
        account = service.provider.account(account_id)
        result = service.provider.call(account_id, "item", {"item_id": item_id})
        service.save_catalog(account_id, item_id, result, str(result.get("seller_id", "")) == account["uid"] and bool(account["uid"]))
        return {"item": result, "mode": account["mode"]}

    @app.get("/api/accounts/{account_id}/chats")
    def chats(account_id: str, current=Depends(role)):
        return service.provider.call(account_id, "chats", {"fetch_num": 50})

    @app.get("/api/accounts/{account_id}/history")
    def history(account_id: str, cid: str, current=Depends(role)):
        if not cid or len(cid) > 150:
            raise Problem("invalid_cid", "会话 ID 无效", 422)
        return service.provider.call(account_id, "history", {"cid": cid, "limit_per_page": 20})

    @app.post("/api/actions", status_code=201)
    def propose(body: ActionIn, current=Depends(role)):
        return service.propose(body, current)

    @app.get("/api/actions")
    def actions(current=Depends(role)):
        return service.list_actions(current)

    @app.get("/api/actions/{action_id}")
    def action(action_id: str, current=Depends(role)):
        row = service.db.one("SELECT * FROM actions WHERE id=?", (action_id,))
        if not row:
            raise Problem("not_found", "操作不存在", 404)
        return service.action_view(row, current)

    @app.post("/api/actions/{action_id}/reconciliation")
    def reconcile(action_id: str, body: ReconciliationIn, current=Depends(admin)):
        return service.reconcile(action_id, body, current)

    @app.post("/api/actions/{action_id}/approve")
    def approve(action_id: str, body: ApprovalIn, current=Depends(admin)):
        service.approve(action_id, body.digest)
        return {"ok": True, "state": "approved"}

    @app.post("/api/actions/{action_id}/reject")
    def reject(action_id: str, current=Depends(admin)):
        service.reject(action_id)
        return {"ok": True}

    @app.post("/api/accounts/{account_id}/assets", status_code=201)
    async def upload(account_id: str, file: UploadFile = File(...), current=Depends(role)):
        service.provider.account(account_id)
        data = await file.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            raise Problem("image_too_large", "单张图片最大 8MB", 413)
        try:
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in ("JPEG", "PNG", "WEBP") or original.width * original.height > 20_000_000:
                    raise ValueError("image limits")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.info.clear()
                clean = io.BytesIO()
                image.save(clean, format="JPEG", quality=95)
                data = clean.getvalue()
        except Exception:
            raise Problem("invalid_image", "仅接受有效 JPEG/PNG/WebP 图片，最大 2000 万像素；不接受 SVG", 422)
        root = s.data_dir / "assets"
        root.mkdir(exist_ok=True, mode=0o700)
        asset_id = uuid.uuid4().hex
        name = asset_id + ".jpg"
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        service.db.execute("INSERT INTO assets(id,account_id,filename,sha256,created) VALUES(?,?,?,?,?)",
                           (asset_id, account_id, name, hashlib.sha256(data).hexdigest(), time.time()))
        return {"id": asset_id, "account_id": account_id, "notice": "已移除 EXIF 元数据"}

    @app.get("/api/assets/{asset_id}")
    def view_asset(asset_id: str, current=Depends(role)):
        row = service.db.one("SELECT * FROM assets WHERE id=?", (asset_id,))
        if not row:
            raise Problem("not_found", "图片不存在", 404)
        return FileResponse(asset_path(s, row), media_type="image/jpeg")

    @app.post("/api/drafts", status_code=201)
    def draft(body: DraftIn, current=Depends(role)):
        service.provider.account(body.account_id)
        service.validate_assets(body.account_id, body.images)
        draft_id = uuid.uuid4().hex
        service.db.execute("INSERT INTO drafts(id,account_id,content,updated) VALUES(?,?,?,?)",
                           (draft_id, body.account_id, service.vault.seal(body.model_dump(mode="json")), time.time()))
        return {"id": draft_id, "revision": 1, "archived": False, "notice": "仅保存本地草稿，未上架"}

    @app.put('/api/drafts/{draft_id}')
    def edit_draft(draft_id: str, body: DraftEditIn, current=Depends(role)):
        service.validate_assets(body.account_id, body.images)
        with service.db.connect() as c:
            changed = c.execute('UPDATE drafts SET content=?,revision=revision+1,updated=? '
                                'WHERE id=? AND account_id=? AND revision=? AND archived=0',
                                (service.vault.seal(body.model_dump(mode='json', exclude={'revision'})),
                                 time.time(), draft_id, body.account_id, body.revision)).rowcount
            if not changed:
                raise Problem('draft_conflict', '草稿已变化、归档或账号不符，请重新载入', 409)
        return {'id': draft_id, 'revision': body.revision + 1, 'archived': False}

    @app.post('/api/drafts/{draft_id}/archive')
    def archive_draft(draft_id: str, body: DraftArchiveIn, current=Depends(role)):
        with service.db.connect() as c:
            changed = c.execute('UPDATE drafts SET archived=1,revision=revision+1,updated=? '
                                'WHERE id=? AND account_id=? AND revision=? AND archived=0',
                                (time.time(), draft_id, body.account_id, body.revision)).rowcount
            if not changed:
                raise Problem('draft_conflict', '草稿已变化、归档或账号不符，请重新载入', 409)
        return {'id': draft_id, 'revision': body.revision + 1, 'archived': True}

    @app.get("/api/drafts")
    def drafts(current=Depends(role)):
        return [{**row, "content": service.vault.open(row["content"])} for row in service.db.all("SELECT * FROM drafts ORDER BY updated DESC LIMIT 200")]

    @app.get("/api/catalog")
    def catalog(current=Depends(role)):
        return [{**row, "data": json.loads(row["data"])} for row in service.db.all("SELECT * FROM catalog ORDER BY updated DESC LIMIT 200")]

    @app.post("/api/monitors", status_code=201)
    def monitor(body: MonitorIn, current=Depends(role)):
        service.provider.account(body.account_id)
        monitor_id = uuid.uuid4().hex
        filters = body.model_dump(mode="json", exclude={"account_id", "query", "interval_s"})
        service.db.execute("INSERT INTO monitors(id,account_id,query,filters,interval_s) VALUES(?,?,?,?,?)",
                           (monitor_id, body.account_id, body.query, canonical(filters), body.interval_s))
        service.db.audit(current, "monitor.created", monitor_id)
        return {"id": monitor_id, "notice": "程序运行时才会监控；结果在工作台通知栏，不会自动联系卖家"}

    @app.get("/api/monitors")
    def monitors(current=Depends(role)):
        return service.db.all("SELECT * FROM monitors ORDER BY next_run LIMIT 200")

    @app.post("/api/monitors/{monitor_id}/toggle")
    def toggle_monitor(monitor_id: str, current=Depends(admin)):
        service.db.execute("UPDATE monitors SET enabled=1-enabled WHERE id=?", (monitor_id,))
        service.db.audit(current, "monitor.toggled", monitor_id)
        return {"ok": True}

    @app.get("/api/notifications")
    def notifications(current=Depends(role)):
        return [{**row, "content": json.loads(row["content"])} for row in service.db.all("SELECT * FROM notifications ORDER BY id DESC LIMIT 100")]

    @app.get("/api/audit")
    def audit(current=Depends(admin)):
        return [{**row, "detail": json.loads(row["detail"])} for row in service.db.all("SELECT * FROM audit ORDER BY id DESC LIMIT 200")]

    @app.post("/api/llm/config")
    def llm_config(body: LLMConfigIn, current=Depends(admin)):
        parsed = urlparse(body.base_url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise Problem("invalid_url", "模型地址无效", 422)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            raise Problem("invalid_url", "只允许 HTTPS 或本机 HTTP 模型地址", 422)
        value = body.model_dump()
        old = service.db.one("SELECT value FROM settings WHERE key='llm'")
        if not value["api_key"] and old:
            value["api_key"] = service.vault.open(old["value"])["api_key"]
        service.db.execute("INSERT INTO settings(key,value) VALUES('llm',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (service.vault.seal(value),))
        service.db.audit(current, "llm.configured", detail={"model": body.model})
        return {"ok": True}

    @app.get("/api/llm/config")
    def llm_status(current=Depends(admin)):
        row = service.db.one("SELECT value FROM settings WHERE key='llm'")
        if not row:
            return {"configured": False}
        data = service.vault.open(row["value"])
        return {"configured": True, "base_url": data["base_url"], "model": data["model"], "has_api_key": bool(data["api_key"])}

    @app.post("/api/assist")
    def assist(body: AssistIn, current=Depends(role)):
        return service.assist(body)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
