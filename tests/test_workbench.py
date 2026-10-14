from __future__ import annotations

import asyncio
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image

from xianyu_workbench.app import create_app
from xianyu_workbench.cli import initialize
from xianyu_workbench.config import Settings
from xianyu_workbench.models import ActionIn
from xianyu_workbench.provider import Problem, Provider
from xianyu_workbench.security import parse_cookies, redact

ADMIN = "admin-test-" + "a" * 40
AGENT = "agent-test-" + "b" * 40


@pytest.fixture
def workbench(tmp_path):
    settings = Settings(tmp_path / "data", ADMIN, AGENT, Fernet.generate_key().decode(),
                        worker_enabled=False, read_interval=0, write_interval=0)
    app = create_app(settings)
    with TestClient(app, headers={"Authorization": "Bearer " + ADMIN}) as client:
        yield client, app.state.service


def account(client, mode="demo", cookies=""):
    response = client.post("/api/accounts", json={"label": "测试账号", "mode": mode, "cookies_json": cookies})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def message(client, account_id, key="message-once-001", text="你好，请问有无维修？"):
    return client.post("/api/actions", json={"account_id": account_id, "kind": "message.send",
                                           "payload": {"cid": "demo-chat", "toid": "10001", "text": text},
                                           "idempotency_key": key})


def approve(client, action):
    response = client.post(f"/api/actions/{action['id']}/approve", json={"digest": action["digest"], "confirm": "确认执行"})
    assert response.status_code == 200, response.text


def upload(client, account_id):
    content = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(content, format="PNG")
    response = client.post(f"/api/accounts/{account_id}/assets", files={"file": ("picture.png", content.getvalue(), "image/png")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_health_and_ui(workbench):
    client, _ = workbench
    assert client.get("/healthz", headers={"Authorization": ""}).json()["status"] == "ok"
    assert "闲鱼 AI 工作台" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert "innerHTML" not in client.get("/static/app.js").text
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


@pytest.mark.parametrize("path", ["/api/accounts", "/api/actions", "/api/catalog", "/api/notifications", "/api/schema"])
def test_auth_required(workbench, path):
    client, _ = workbench
    assert client.get(path, headers={"Authorization": ""}).status_code == 401


@pytest.mark.parametrize("path", ["/api/audit", "/api/llm/config"])
def test_agent_cannot_read_admin_config(workbench, path):
    client, _ = workbench
    assert client.get(path, headers={"Authorization": "Bearer " + AGENT}).status_code == 403


def test_agent_cannot_create_accounts(workbench):
    client, _ = workbench
    response = client.post("/api/accounts", headers={"Authorization": "Bearer " + AGENT}, json={"label": "x"})
    assert response.status_code == 403


def test_agent_proposes_but_cannot_approve(workbench):
    client, service = workbench
    aid = account(client)
    proposal = client.post("/api/actions", headers={"Authorization": "Bearer " + AGENT},
                          json={"account_id": aid, "kind": "message.send", "payload": {"cid": "demo-chat", "toid": "10001", "text": "你好"}, "idempotency_key": "agent-proposal-001"})
    assert proposal.status_code == 201
    data = proposal.json()
    assert data["state"] == "pending"
    assert not service.run_once()
    response = client.post(f"/api/actions/{data['id']}/approve", headers={"Authorization": "Bearer " + AGENT}, json={"digest": data["digest"], "confirm": "确认执行"})
    assert response.status_code == 403


def test_idempotency_and_content_conflict(workbench):
    client, _ = workbench
    aid = account(client)
    first = message(client, aid).json()
    second = message(client, aid).json()
    assert first["id"] == second["id"]
    assert message(client, aid, text="另一段内容").status_code == 409
    assert len(client.get("/api/actions").json()) == 1


def test_approval_digest_must_match(workbench):
    client, _ = workbench
    action = message(client, account(client)).json()
    response = client.post(f"/api/actions/{action['id']}/approve", json={"digest": "0" * 64, "confirm": "确认执行"})
    assert response.status_code == 409


def test_demo_message_once(workbench):
    client, service = workbench
    action = message(client, account(client)).json()
    approve(client, action)
    assert service.run_once()
    assert not service.run_once()
    result = client.get(f"/api/actions/{action['id']}").json()
    assert result["state"] == "simulated"
    assert result["result"]["demo"] is True
    assert "未发送" in result["result"]["notice"]


def test_atomic_concurrent_claim(workbench, monkeypatch):
    client, service = workbench
    action = message(client, account(client)).json()
    approve(client, action)
    calls = []
    old = service.provider.call

    def counted(*args, **kwargs):
        if kwargs.get("write"):
            calls.append(args[1])
        return old(*args, **kwargs)

    monkeypatch.setattr(service.provider, "call", counted)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.run_once(), range(4)))
    assert calls == ["message.send"]


def test_wrong_recipient_is_never_sent(workbench, monkeypatch):
    client, service = workbench
    aid = account(client)
    action = client.post("/api/actions", json={"account_id": aid, "kind": "message.send", "payload": {"cid": "demo-chat", "toid": "12345", "text": "你好"}, "idempotency_key": "wrong-recipient-001"}).json()
    approve(client, action)
    service.run_once()
    result = client.get(f"/api/actions/{action['id']}").json()
    assert result["state"] == "failed"
    assert "对应关系" in result["error"]


def test_recovery_never_replays_running_action(workbench):
    client, service = workbench
    action = message(client, account(client)).json()
    service.db.execute("UPDATE actions SET state='running' WHERE id=?", (action["id"],))
    service.recover()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "unconfirmed"
    assert not service.run_once()


def test_timeout_never_retries_a_write(workbench, monkeypatch):
    client, service = workbench
    action = message(client, account(client)).json()
    approve(client, action)
    old = service.provider.call
    calls = []

    def timeout(*args, **kwargs):
        if kwargs.get("write"):
            calls.append(1)
            raise Problem("uncertain", "执行结果不确定", 504)
        return old(*args, **kwargs)

    monkeypatch.setattr(service.provider, "call", timeout)
    service.run_once()
    service.run_once()
    assert calls == [1]
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "unconfirmed"


def test_expired_approval_is_not_executed(workbench):
    client, service = workbench
    action = message(client, account(client)).json()
    approve(client, action)
    service.db.execute("UPDATE actions SET expires=? WHERE id=?", (time.time() - 1, action["id"]))
    assert not service.run_once()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "expired"


def test_reject_approved_action(workbench):
    client, service = workbench
    action = message(client, account(client)).json()
    approve(client, action)
    assert client.post(f"/api/actions/{action['id']}/reject").status_code == 200
    assert not service.run_once()


def test_pause_and_resume_do_not_replay_uncertain(workbench):
    client, service = workbench
    aid = account(client)
    action = message(client, aid).json()
    service.db.execute("UPDATE actions SET state='unconfirmed' WHERE id=?", (action["id"],))
    client.post(f"/api/accounts/{aid}/pause")
    assert client.post("/api/search", json={"account_id": aid, "query": "显卡"}).status_code == 409
    client.post(f"/api/accounts/{aid}/resume", json={"digest": "0" * 64, "confirm": "确认执行"})
    assert not service.run_once()


def test_demo_search_filtering_and_labels(workbench):
    client, _ = workbench
    aid = account(client)
    data = client.post("/api/search", json={"account_id": aid, "query": "显卡", "max_price": "1300", "location": "福州"}).json()
    assert data["mode"] == "demo"
    assert data["total"] == 2
    assert all(i["url"] == "" and "演示" in i["title"] for i in data["items"])


def test_unknown_price_excluded_from_bounded_search(workbench, monkeypatch):
    client, service = workbench
    aid = account(client)
    monkeypatch.setattr(service.provider, "call", lambda *a, **kw: {"items": [{"item_id": "1", "price": "面议"}, {"item_id": "2", "price": "¥1,200.50"}, {"item_id": "2", "price": "1200.50"}]})
    result = client.post("/api/search", json={"account_id": aid, "query": "测试", "min_price": "100"}).json()
    assert [i["item_id"] for i in result["items"]] == ["2"]


@pytest.mark.parametrize("extra", [{"limit": 51}, {"limit": 0}, {"min_price": 200, "max_price": 100}, {"max_price": -1}, {"query": ""}])
def test_search_validation(workbench, extra):
    client, _ = workbench
    response = client.post("/api/search", json={"account_id": account(client), "query": "测试", **extra})
    assert response.status_code == 422


def test_images_cannot_cross_accounts(workbench):
    client, _ = workbench
    a, b = account(client), account(client)
    image = upload(client, a)
    response = client.post("/api/actions", json={"account_id": b, "kind": "item.publish", "payload": {"title": "真实商品", "desc": "真实描述", "price": "19.99", "images": [image]}, "idempotency_key": "publish-cross-account"})
    assert response.status_code == 409


def test_publish_with_uploaded_image(workbench):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    action = client.post("/api/actions", json={"account_id": aid, "kind": "item.publish", "payload": {"title": "真实商品", "desc": "真实描述", "price": "19.99", "images": [image]}, "idempotency_key": "publish-once-001"}).json()
    approve(client, action)
    service.run_once()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "simulated"
    assert len(client.get("/api/catalog").json()) == 1


def test_asset_tampering_stops_execution(workbench):
    client, service = workbench
    aid = account(client)
    image = upload(client, aid)
    action = client.post("/api/actions", json={"account_id": aid, "kind": "item.publish", "payload": {"title": "商品", "desc": "描述", "price": "20", "images": [image]}, "idempotency_key": "publish-tamper-001"}).json()
    approve(client, action)
    (service.s.data_dir / "assets" / (image + ".jpg")).write_bytes(b"tampered")
    service.run_once()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "failed"


@pytest.mark.parametrize("image", ["/etc/passwd", "../../secrets", "https://example.com/a.jpg"])
def test_arbitrary_upload_paths_rejected(workbench, image):
    client, _ = workbench
    response = client.post("/api/actions", json={"account_id": account(client), "kind": "item.publish", "payload": {"title": "商品", "desc": "描述", "price": "20", "images": [image]}, "idempotency_key": "publish-bad-path"})
    assert response.status_code == 422


def test_svg_upload_rejected(workbench):
    client, _ = workbench
    response = client.post(f"/api/accounts/{account(client)}/assets", files={"file": ("evil.svg", b"<svg onload='alert(1)'/>", "image/svg+xml")})
    assert response.status_code == 422


def test_delete_requires_explicit_phrase_and_ownership(workbench, monkeypatch):
    client, service = workbench
    aid = account(client)
    body = {"account_id": aid, "kind": "item.delete", "payload": {"item_id": "12345"}, "idempotency_key": "delete-owned-001"}
    assert client.post("/api/actions", json=body).status_code == 422
    body["payload"]["acknowledgement"] = "我理解这可能永久删除商品，不是普通下架"
    action = client.post("/api/actions", json=body).json()
    approve(client, action)
    monkeypatch.setattr(service.provider, "call", lambda *a, **kw: {"seller_id": "not-owner"})
    service.run_once()
    result = client.get(f"/api/actions/{action['id']}").json()
    assert result["state"] == "failed"
    assert "属于当前账号" in result["error"]


@pytest.mark.parametrize("kind", ["payment", "refund", "order.create", "confirm_receipt", "shell", "item.edit"])
def test_transactions_and_unknown_actions_not_exposed(workbench, kind):
    client, service = workbench
    aid = account(client)
    response = client.post("/api/actions", json={"account_id": aid, "kind": kind, "payload": {}, "idempotency_key": "blocked-operation"})
    assert response.status_code == 422
    with pytest.raises(Problem):
        service.provider.call(aid, kind, {}, write=True)


def test_cookies_encrypted_and_never_exported(workbench):
    client, service = workbench
    marker = "private-cookie-value-test-only"
    aid = account(client, "live", json.dumps({"unb": "12345", "_m_h5_tk": marker}))
    row = service.db.one("SELECT * FROM accounts WHERE id=?", (aid,))
    assert marker not in row["secret"]
    assert service.vault.open(row["secret"])["_m_h5_tk"] == marker
    assert marker not in client.get("/api/accounts").text
    assert "secret" not in client.get("/api/accounts").json()[0]


def test_cookie_import_cannot_switch_identity(workbench):
    client, _ = workbench
    aid = account(client, "live", json.dumps({"unb": "12345", "_m_h5_tk": "test-only"}))
    response = client.post(f"/api/accounts/{aid}/cookies", json={"cookies_json": json.dumps({"unb": "67890", "_m_h5_tk": "other-test-only"})})
    assert response.status_code == 409


def test_live_disabled_by_default(workbench):
    client, _ = workbench
    aid = account(client, "live", json.dumps({"unb": "12345", "_m_h5_tk": "test-only"}))
    assert client.post("/api/search", json={"account_id": aid, "query": "商品"}).status_code == 409
    action = message(client, aid).json()
    response = client.post(f"/api/actions/{action['id']}/approve", json={"digest": action["digest"], "confirm": "确认执行"})
    assert response.status_code == 409


def test_modes_are_frozen_into_approval(workbench):
    client, service = workbench
    aid = account(client)
    action = message(client, aid).json()
    approve(client, action)
    service.db.execute("UPDATE accounts SET mode='live' WHERE id=?", (aid,))
    service.run_once()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "failed"


def test_private_message_payload_is_encrypted_at_rest(workbench):
    client, service = workbench
    action = message(client, account(client), text="private-test-message-marker").json()
    row = service.db.one("SELECT payload FROM actions WHERE id=?", (action["id"],))
    assert "private-test-message-marker" not in row["payload"]
    assert "private-test-message-marker" in action["payload"]["text"]


def test_model_config_is_encrypted_and_key_not_readable(workbench):
    client, service = workbench
    response = client.post("/api/llm/config", json={"base_url": "https://example.com/v1", "model": "test-model", "api_key": "private-test-model-key"})
    assert response.status_code == 200
    assert "private-test-model-key" not in client.get("/api/llm/config").text
    assert "private-test-model-key" not in service.db.one("SELECT value FROM settings WHERE key='llm'")["value"]
    assert client.get("/api/llm/config").json()["has_api_key"] is True


def test_model_requires_configuration(workbench):
    client, _ = workbench
    response = client.post("/api/assist", json={"purpose": "reply", "facts": "你好"})
    assert response.status_code == 409


def test_model_config_rejects_insecure_remote(workbench):
    client, _ = workbench
    assert client.post("/api/llm/config", json={"base_url": "http://example.com/v1", "model": "test"}).status_code == 422
    assert client.post("/api/llm/config", json={"base_url": "http://127.0.0.1:8000/v1", "model": "test"}).status_code == 200


def test_monitors_deduplicate_and_enforce_interval(workbench):
    client, service = workbench
    aid = account(client)
    assert client.post("/api/monitors", json={"account_id": aid, "query": "显卡", "interval_s": 10}).status_code == 422
    monitor = client.post("/api/monitors", json={"account_id": aid, "query": "显卡", "interval_s": 300}).json()
    service.monitor_once()
    first = client.get("/api/notifications").json()
    assert len(first) == 1 and first[0]["content"]["mode"] == "demo"
    service.db.execute("UPDATE monitors SET next_run=0 WHERE id=?", (monitor["id"],))
    service.monitor_once()
    assert len(client.get("/api/notifications").json()) == 1


def test_validation_does_not_echo_sensitive_input(workbench):
    client, _ = workbench
    response = client.post("/api/accounts", json={"label": "x", "mode": "INVALID", "cookies_json": "private-cookie-marker"})
    assert response.status_code == 422
    assert "private-cookie-marker" not in response.text


def test_bad_origin_is_blocked(workbench):
    client, _ = workbench
    assert client.get("/api/accounts", headers={"Origin": "https://evil.example"}).status_code == 403


def test_cookie_domains_filtering():
    values = [{"name": "unb", "value": "1234", "domain": ".goofish.com"}, {"name": "_m_h5_tk", "value": "test-only", "domain": ".taobao.com"}, {"name": "unrelated", "value": "do-not-import", "domain": "bank.example"}]
    assert "unrelated" not in parse_cookies(json.dumps(values))


def test_redaction():
    value = redact({"cookie": "secret", "nested": {"api_key": "secret"}, "message": "Bearer private-value"})
    assert "secret" not in json.dumps(value)
    assert "private-value" not in json.dumps(value)


def test_init_does_not_overwrite_secrets(tmp_path):
    path = initialize(tmp_path)
    first = path.read_bytes()
    with pytest.raises(FileExistsError):
        initialize(tmp_path)
    assert path.read_bytes() == first


def test_mcp_exposes_no_approval_credentials_or_transaction_tools():
    from xianyu_workbench.mcp_server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {"search_items", "propose_message", "propose_listing", "list_actions"}.issubset(names)
    assert not any(any(block in name for block in ("approve", "reconcile", "reconciliation", "cookie", "payment", "refund", "shell")) for name in names)


def test_action_schema_forbids_extra_fields():
    with pytest.raises(ValueError):
        ActionIn(account_id="x", kind="message.send", payload={}, idempotency_key="test-extra", approved=True)


def test_provider_write_flag_cannot_be_bypassed(workbench):
    client, service = workbench
    with pytest.raises(Problem):
        service.provider.call(account(client), "message.send", {}, write=False)


def test_wrong_vault_key_rejects_startup_without_changing_data(tmp_path):
    from dataclasses import replace

    settings = Settings(tmp_path / "data", ADMIN, AGENT, Fernet.generate_key().decode(), worker_enabled=False)
    app = create_app(settings)
    with TestClient(app, headers={"Authorization": "Bearer " + ADMIN}) as client:
        message(client, account(client), text="保留的加密正文")
    db = app.state.service.db
    before = db.one("SELECT * FROM actions")
    with pytest.raises(ValueError, match="密钥不匹配|加密数据损坏"):
        create_app(replace(settings, vault_key=Fernet.generate_key().decode()))
    assert db.one("SELECT * FROM actions") == before
    assert create_app(settings).state.service.action_view(before)["payload"]["text"] == "保留的加密正文"


def reconciliation_body(action, **changes):
    return {"account_id": action["account_id"], "outcome": "observed",
            "evidence": "人工查看平台记录：测试证据，不代表送达或已读",
            "idempotency_key": "reconcile-once-001", **changes}


def uncertain_action(client, service, state="unconfirmed"):
    action = message(client, account(client)).json()
    service.db.execute("UPDATE actions SET state=?,result=?,error=? WHERE id=?",
                       (state, service.vault.seal({"mid": "not-a-receipt"}), "原始不确定原因", action["id"]))
    return action


def test_admin_reconciliation_preserves_original_execution_and_encrypts_evidence(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    before = service.db.one("SELECT * FROM actions WHERE id=?", (action["id"],))
    body = reconciliation_body(action)
    response = client.post(f"/api/actions/{action['id']}/reconciliation", json=body)
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["action_id"] == action["id"]
    assert record["account_id"] == action["account_id"]
    assert record["outcome"] == "observed"
    assert record["source"] == "manual"
    assert record["evidence"] == body["evidence"]
    assert record["recorded_at"] > 0
    assert service.db.one("SELECT * FROM actions WHERE id=?", (action["id"],)) == before
    stored = service.db.one("SELECT * FROM reconciliations WHERE action_id=?", (action["id"],))
    assert body["evidence"] not in str(stored)
    assert body["evidence"] not in client.get("/api/audit").text
    assert len(service.db.all("SELECT * FROM audit WHERE event='action.reconciled'")) == 1
    assert not service.run_once()


def test_agent_cannot_reconcile_via_api_or_service(workbench):
    from xianyu_workbench.models import ReconciliationIn

    client, service = workbench
    action = uncertain_action(client, service)
    body = reconciliation_body(action)
    response = client.post(f"/api/actions/{action['id']}/reconciliation", json=body,
                           headers={"Authorization": "Bearer " + AGENT})
    assert response.status_code == 403
    with pytest.raises(Problem) as exc:
        service.reconcile(action["id"], ReconciliationIn(**body), "agent")
    assert exc.value.status == 403
    assert not service.db.all("SELECT * FROM reconciliations")


def test_reconciliation_rejects_cross_account_binding(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    response = client.post(f"/api/actions/{action['id']}/reconciliation",
                           json=reconciliation_body(action, account_id=account(client)))
    assert response.status_code == 409
    assert response.json()["code"] == "account_mismatch"
    assert not service.db.all("SELECT * FROM reconciliations")


@pytest.mark.parametrize("state", ["pending", "approved", "running", "failed", "rejected", "expired", "simulated"])
def test_reconciliation_rejects_noneligible_states(workbench, state):
    client, service = workbench
    action = uncertain_action(client, service, state)
    response = client.post(f"/api/actions/{action['id']}/reconciliation", json=reconciliation_body(action))
    assert response.status_code == 409
    assert response.json()["code"] == "state_conflict"
    assert not service.db.all("SELECT * FROM reconciliations")


def test_reconciliation_same_request_is_idempotent_and_conflicts_are_explicit(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    path = f"/api/actions/{action['id']}/reconciliation"
    body = reconciliation_body(action)
    first = client.post(path, json=body)
    second = client.post(path, json=body)
    assert second.status_code == 200
    assert first.json() == second.json()
    for changes in ({"evidence": "不同证据"}, {"outcome": "not_observed"}, {"idempotency_key": "new-key-0002"}):
        assert client.post(path, json={**body, **changes}).status_code == 409
    assert len(service.db.all("SELECT * FROM reconciliations")) == 1
    assert len(service.db.all("SELECT * FROM audit WHERE event='action.reconciled'")) == 1
    assert not service.run_once()


def test_reconciliation_read_scope_admin_evidence_agent_summary_only(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    body = reconciliation_body(action)
    client.post(f"/api/actions/{action['id']}/reconciliation", json=body).raise_for_status()
    admin_view = client.get(f"/api/actions/{action['id']}").json()
    assert admin_view["reconciliation"]["evidence"] == body["evidence"]
    headers = {"Authorization": "Bearer " + AGENT}
    for path in (f"/api/actions/{action['id']}", "/api/actions"):
        response = client.get(path, headers=headers)
        value = response.json()
        row = value[0] if isinstance(value, list) else value
        assert row["reconciliation"]["outcome"] == "observed"
        assert row["reconciliation"]["source"] == "manual"
        assert "evidence" not in row["reconciliation"]
        assert body["evidence"] not in response.text
    repeated_proposal = message(client, action["account_id"])
    assert "evidence" not in repeated_proposal.json()["reconciliation"]


@pytest.mark.parametrize("state", ["unconfirmed", "submitted", "blocked"])
def test_reconciliation_concurrency_and_recovery_never_replay(workbench, state):
    from xianyu_workbench.models import ReconciliationIn

    client, service = workbench
    action = uncertain_action(client, service, state)
    body = ReconciliationIn(**reconciliation_body(action))
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: service.reconcile(action["id"], body, "admin"), range(4)))
    assert all(record == records[0] for record in records)
    assert len(service.db.all("SELECT * FROM audit WHERE event='action.reconciled'")) == 1
    service.recover()
    assert not service.run_once()
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == state


def test_concurrent_conflicting_reconciliations_have_one_winner(workbench):
    from xianyu_workbench.models import ReconciliationIn

    client, service = workbench
    action = uncertain_action(client, service)

    def submit(index):
        body = ReconciliationIn(**reconciliation_body(action, evidence=f"人工证据 {index}"))
        try:
            return service.reconcile(action["id"], body, "admin")
        except Problem as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count(409) == 3
    assert len(service.db.all("SELECT * FROM reconciliations")) == 1


def test_reconciliation_idempotency_key_cannot_bind_another_operation(workbench):
    client, service = workbench
    first = uncertain_action(client, service)
    second = message(client, first["account_id"], key="second-operation").json()
    service.db.execute("UPDATE actions SET state='unconfirmed' WHERE id=?", (second["id"],))
    assert client.post(f"/api/actions/{first['id']}/reconciliation", json=reconciliation_body(first)).status_code == 200
    response = client.post(f"/api/actions/{second['id']}/reconciliation", json=reconciliation_body(second))
    assert response.status_code == 409
    assert len(service.db.all("SELECT * FROM reconciliations")) == 1


@pytest.mark.parametrize("changes", [{"outcome": "delivered"}, {"outcome": "read"}, {"outcome": "payment"},
                                    {"evidence": "   "}, {"evidence": "x" * 2001}, {"retry": True},
                                    {"account_id": ""}, {"idempotency_key": "x"}])
def test_reconciliation_input_cannot_claim_receipts_or_retry(workbench, changes):
    client, service = workbench
    action = uncertain_action(client, service)
    response = client.post(f"/api/actions/{action['id']}/reconciliation", json=reconciliation_body(action, **changes))
    assert response.status_code == 422
    assert not service.db.all("SELECT * FROM reconciliations")


def test_reconciliation_missing_action_is_404(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    assert client.post("/api/actions/missing/reconciliation", json=reconciliation_body(action)).status_code == 404


def test_reconciliation_and_audit_rollback_together(workbench):
    client, service = workbench
    action = uncertain_action(client, service)
    service.db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit WHEN NEW.event='action.reconciled' "
                       "BEGIN SELECT RAISE(ABORT, 'test audit failure'); END")
    from xianyu_workbench.models import ReconciliationIn

    with pytest.raises(Exception, match="test audit failure"):
        service.reconcile(action["id"], ReconciliationIn(**reconciliation_body(action)), "admin")
    assert not service.db.all("SELECT * FROM reconciliations")
    assert client.get(f"/api/actions/{action['id']}").json()["state"] == "unconfirmed"


def test_capabilities_distinguish_manual_reconciliation_from_receipts(workbench):
    client, _ = workbench
    value = client.get("/api/capabilities").json()
    assert value["manual_reconciliation"] is True
    assert value["automatic_receipt_verification"] is False
    assert value["reconciliation_policy"] == {
        "write_role": "admin", "agent_read": "outcome_time_only",
        "eligible_states": ["unconfirmed", "submitted", "blocked"],
        "outcomes": ["observed", "not_observed", "unresolved"],
        "immutable": True, "retries_operation": False,
    }
    schema = client.get("/api/schema").json()
    assert "/api/actions/{action_id}/reconciliation" in schema["paths"]
    assert "ReconciliationIn" in schema["components"]["schemas"]


def test_reconciliation_survives_real_restart_without_replay(tmp_path):
    settings = Settings(tmp_path / "data", ADMIN, AGENT, Fernet.generate_key().decode(),
                        worker_enabled=False, read_interval=0, write_interval=0)
    app = create_app(settings)
    headers = {"Authorization": "Bearer " + ADMIN}
    with TestClient(app, headers=headers) as client:
        action = uncertain_action(client, app.state.service)
        record = client.post(f"/api/actions/{action['id']}/reconciliation", json=reconciliation_body(action)).json()
    restarted = create_app(settings)
    with TestClient(restarted, headers=headers) as client:
        value = client.get(f"/api/actions/{action['id']}").json()
        assert value["reconciliation"] == record
        assert value["state"] == "unconfirmed"
        assert value["result"] == {"mid": "not-a-receipt"}
        assert not restarted.state.service.run_once()
        assert len(restarted.state.service.db.all("SELECT * FROM audit WHERE event='action.reconciled'")) == 1


def test_demo_provider_never_generates_real_product_links():
    result = Provider.demo("search", {"query": "3080", "limit": 3})
    assert result["demo"] is True
    assert all(not item["url"] for item in result["items"])
