from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    admin_token: str
    agent_token: str
    vault_key: str
    live_enabled: bool = False
    worker_enabled: bool = True
    operation_timeout: int = 120
    read_interval: float = 5.0
    write_interval: float = 30.0
    upstream_python: str = ""

    def validate(self) -> None:
        if min(len(self.admin_token), len(self.agent_token)) < 32:
            raise ValueError("先运行 xianyu-workbench init；管理员和 Agent 令牌至少 32 字符")
        if self.admin_token == self.agent_token:
            raise ValueError("管理员与 Agent 必须使用不同令牌")
        Fernet(self.vault_key.encode())
        if self.operation_timeout < 5:
            raise ValueError("operation_timeout 必须 >= 5 秒")

    @classmethod
    def load(cls) -> Settings:
        load_dotenv(override=False)
        obj = cls(
            data_dir=Path(os.getenv("XY_DATA_DIR", "./data")).expanduser().resolve(),
            admin_token=os.getenv("XY_ADMIN_TOKEN", ""),
            agent_token=os.getenv("XY_AGENT_TOKEN", ""),
            vault_key=os.getenv("XY_VAULT_KEY", ""),
            live_enabled=os.getenv("XY_LIVE_ENABLED", "false").lower() == "true",
            worker_enabled=os.getenv("XY_WORKER_ENABLED", "true").lower() == "true",
            operation_timeout=int(os.getenv("XY_OPERATION_TIMEOUT", "120")),
            upstream_python=os.getenv("XY_UPSTREAM_PYTHON", ""),
        )
        obj.validate()
        return obj
