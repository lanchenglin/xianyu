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
    args = parser.parse_args()
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
    elif args.command == "serve":
        import uvicorn

        from .app import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port, access_log=False)
    else:
        print(json.dumps({"goofish_installed": importlib.util.find_spec("goofish_cli") is not None,
                          "mcp_installed": importlib.util.find_spec("mcp") is not None,
                          "node_found": bool(shutil.which("node")),
                          "chrome_found_in_path": bool(shutil.which("google-chrome") or shutil.which("chrome")),
                          "notice": "真实搜索需安装系统 Chrome；Windows Chrome 常不在 PATH 中，请自行确认安装"},
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
