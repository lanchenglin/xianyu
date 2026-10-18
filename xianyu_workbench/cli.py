from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

from cryptography.fernet import Fernet


def initialize(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".env"
    content = "\n".join([
        "# 此文件是本地机密，禁止上传 Git 或发给 AI。请分别分发不同角色令牌。",
        "XY_ADMIN_TOKEN=" + secrets.token_urlsafe(36),
        "XY_AGENT_TOKEN=" + secrets.token_urlsafe(36),
        "XY_VAULT_KEY=" + Fernet.generate_key().decode(),
        "XY_DATA_DIR=./data", "XY_LIVE_ENABLED=false", "XY_WORKER_ENABLED=true",
        "XY_OPERATION_TIMEOUT=120", "XY_ALLOWED_HOSTS=localhost,127.0.0.1,[::1]", "",
    ])
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)
    return path


def main():
    parser = argparse.ArgumentParser(description="闲鱼 AI 工作台")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="生成本地随机访问令牌与加密密钥，不覆盖旧配置")
    serve = sub.add_parser("serve", help="启动工作台与单实例队列")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8099, type=int)
    sub.add_parser("doctor", help="检查依赖，不访问闲鱼或登录态")
    backup = sub.add_parser('backup', help='离线私有备份数据库和素材，不导出配置密钥')
    backup.add_argument('--data-dir', type=Path, required=True)
    backup.add_argument('--output', type=Path, required=True)
    restore = sub.add_parser('restore', help='离线恢复并使历史待执行申请失效')
    restore.add_argument('--data-dir', type=Path, required=True)
    restore.add_argument('--archive', type=Path, required=True)
    restore.add_argument('--offline', action='store_true', required=True)
    schedule = sub.add_parser('backup-schedule', help='默认关闭的离线备份调度；不安装宿主任务')
    schedule.add_argument('--data-dir', type=Path, required=True)
    schedule.add_argument('--destination', type=Path, required=True)
    schedule.add_argument('--enabled', action='store_true')
    schedule.add_argument('--interval', type=int, default=86400)
    schedule.add_argument('--keep', type=int, default=7)
    schedule.add_argument('--watch', action='store_true', help='每60秒检查到期；活动服务跳过')
    daily = sub.add_parser('daily-publish', help='管理员 HTTP 每日授权入口；不启动第二 worker，不读取 .env')
    daily.add_argument('operation', choices=('status', 'configure', 'revoke', 'tick'))
    daily.add_argument('--url', required=True, help='固定工作台 URL，拒绝重定向')
    daily.add_argument('--account-id', required=True)
    daily.add_argument('--config', type=Path, help='configure 使用的管理员 JSON 文件')
    args = parser.parse_args()
    if args.command == 'daily-publish':
        from urllib.parse import quote, urlsplit

        import httpx
        try:
            url = urlsplit(args.url)
            if url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
                raise ValueError('invalid endpoint')
            if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')):
                raise ValueError('insecure endpoint')
            token = os.environ.get('XY_ADMIN_TOKEN', '')
            if not token:
                raise ValueError('admin token required')
            endpoint = args.url.rstrip('/') + '/api/accounts/' + quote(args.account_id, safe='') + '/daily-publish'
            method, body = 'GET', None
            if args.operation == 'configure':
                method = 'PUT'
                body = json.loads(args.config.read_text(encoding='utf-8'))
            elif args.operation in ('revoke', 'tick'):
                method, endpoint = 'POST', endpoint + '/' + args.operation
            with httpx.Client(follow_redirects=False, trust_env=False, timeout=300) as client:
                response = client.request(method, endpoint, json=body, headers={'Authorization': 'Bearer ' + token})
                response.raise_for_status()
                print(json.dumps(response.json(), ensure_ascii=False))
        except Exception:
            parser.exit(1, '每日发布请求失败；不自动重试，请在管理员队列核对结果。\n')
        return
    if args.command == "init":
        try:
            path = initialize(Path.cwd())
        except FileExistsError:
            parser.exit(1, ".env 已存在，未覆盖。请先备份原配置；切勿丢失加密密钥。\n")
        print(f"配置已写入 {path}；请自行查看管理员令牌登录，Agent 只使用 XY_AGENT_TOKEN。")
    elif args.command in ('backup', 'restore'):
        # Redirected Windows streams may use cp1252: escape unsupported characters
        # without changing the caller's encoding or misreporting a completed restore.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(errors='backslashreplace')
        from .backup import create_backup, restore_backup
        from .security import Vault
        try:
            # Deliberately do not load .env or require API tokens for offline administration.
            vault = Vault(os.environ.get('XY_VAULT_KEY', ''))
            directory = args.data_dir.absolute()
            if args.command == 'backup':
                create_backup(directory, args.output.absolute(), vault)
                print('私有备份完成；包含隐私，禁止提交 Git。密钥须独立保管。')
            else:
                rollback = restore_backup(directory, args.archive.absolute(), vault)
                print(f'恢复完成；账号/监控暂停，旧待执行申请失效。回滚副本：{rollback}')
        except Exception:
            parser.exit(1, '备份/恢复失败：请检查离线状态、密钥、路径、备份完整性与权限；未输出敏感异常。\n')
    elif args.command == 'backup-schedule':
        import time

        from .backup_schedule import tick
        from .security import Vault
        if not args.enabled:
            print('disabled')
            return
        try:
            vault = Vault(os.environ.get('XY_VAULT_KEY', ''))
            while True:
                print(tick(args.data_dir, args.destination, vault, enabled=True,
                           interval_s=args.interval, keep=args.keep), flush=True)
                if not args.watch:
                    break
                time.sleep(60)
        except KeyboardInterrupt:
            return
        except Exception:
            parser.exit(1, '离线调度失败：请检查专属目录、密钥、恢复状态与权限；未输出敏感异常。\n')
    elif args.command == "serve":
        import uvicorn

        from .app import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)
    else:
        from .browser_config import diagnostic
        print(json.dumps({"browser": diagnostic(),
                          "goofish_installed": importlib.util.find_spec("goofish_cli") is not None,
                          "mcp_installed": importlib.util.find_spec("mcp") is not None,
                          "node_found": bool(shutil.which("node")),
                          "chrome_found_in_path": bool(shutil.which("google-chrome") or shutil.which("chrome")),
                          "notice": "仅检查已导出的管理员环境配置；不读取 .env、不连接 CDP、不验证登录态。隔离启动支持 Chrome / Chromium"},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
