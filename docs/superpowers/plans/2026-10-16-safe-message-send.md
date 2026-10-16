# Safe single-message send implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; do not dispatch implementation agents.

**Goal:** Deliver a default-off, individually approved existing-conversation text send through the single persistent action queue.

**Architecture:** CDP verifies the current account and conversation pair from bounded read-only samples. A separately administrator-imported Cookie session of the same UID supplies upstream WS transport; it is not extracted from the browser. Freeze the identity, credential fingerprint and message in the encrypted approval payload. Never infer CID or delivery from mid.

**Tech Stack:** Python 3.11/3.12, FastAPI, SQLite, pinned goofish-cli subprocess, Playwright isolated fixtures.

**Spec:** User-approved constraints in this request; detailed contract in docs/MESSAGE_SEND.md.

## Global constraints

- No .env/data/profile reads, no 9235/8099 connections, no real platform writes. Temporary fictional fixtures only.
- No arbitrary JS/URL or automatic first contact. FAQ remains non-executable.
- Default-off administrator deployment switch, exact message.send whitelist; all other CDP writes stay denied.
- Single selected queued execution does not start historical approved actions. Digest, expiry, takeover, revocation, rate and idempotency enforced.
- Unknown writes never retry. A local mid is not an accepted/received/read receipt.
- Evidence in scratch/xianyu-send-evidence; scratch is not committed. Commit source/docs/tests only, no push/deploy.

## Tasks

- [x] 1. Tests RED for default-off configuration, source/account binding, exact bridge whitelist and safe text adapter. Implement and GREEN. Files: config.py, provider.py, browser_adapter.py, bridge.py, message_send.py, tests/test_message_send.py.
- [x] 2. Tests RED for frozen binding, verified peer/CID, expiry/takeover/revoke, single action dispatch and no retry. Implement and GREEN. Files: service.py, message_send.py, tests/test_message_send.py. Use encrypted payload metadata, no schema change.
- [x] 3. Tests RED for admin-only execute-one and HTTP/UI/MCP integration; expose no new model write authority. Implement and GREEN. Files: app.py, static/app.js, scripts/smoke_ui.py, tests.
- [x] 4. Run full suites/pip check on Python 3.11 and 3.12 with env -u PYTHONPATH and stable scratch TMPDIR, real stdio and isolated Chromium UI. Record exact results and missing real-platform evidence.
- [x] 5. Review security diff, update capability/operation/hand-off docs, commit explicit paths without scratch. No push/deploy. Continue subsequent work only within established evidence boundaries.

## Acceptance checks

```python
assert not Settings(...).message_send_enabled
assert execute_one(selected_id) does_not_dispatch_other_approved_actions
assert frozen_uid_and_cookie_fingerprint_match_before_send
assert recipient_pair_is_revalidated_before_send
assert unknown_result_is_terminal_and_not_retried
assert faq_send_allowed is False
```

The last block expresses acceptance invariants, not executable fixture code. Concrete tests live in tests/test_message_send.py. First contact remains disabled until a real create response can be correlated to the request and parsed without guessing.
