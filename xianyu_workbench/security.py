from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from cryptography.fernet import Fernet

SENSITIVE = re.compile(r"cookie|token|authorization|password|secret|api.?key|_m_h5|\bunb\b", re.I)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SENSITIVE.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", value)
        return re.sub(r"(?i)((?:_m_h5_tk\w*|cookie|api_key|access_token|password)\s*[=:]\s*)[^\s;,]+", r"\1[REDACTED]", value)
    return value


class Vault:
    def __init__(self, key: str):
        self.fernet = Fernet(key.encode())

    def seal(self, obj: Any) -> str:
        return self.fernet.encrypt(canonical(obj).encode()).decode()

    def open(self, text: str) -> Any:
        return json.loads(self.fernet.decrypt(text.encode()))


def parse_cookies(text: str) -> dict[str, str]:
    if len(text) > 100_000:
        raise ValueError("Cookie 文件过大；只导出闲鱼相关域名")
    raw = json.loads(text)
    if isinstance(raw, list):
        allowed = []
        for c in raw:
            if not isinstance(c, dict):
                raise ValueError("Cookie 数组元素必须是对象")
            domain = str(c.get("domain", "")).lstrip(".").lower()
            if domain and not any(domain == d or domain.endswith("." + d) for d in ("goofish.com", "taobao.com")):
                continue
            allowed.append(c)
        cookies = {c["name"]: c["value"] for c in allowed if "name" in c and "value" in c}
    elif isinstance(raw, dict):
        cookies = raw
    else:
        raise ValueError("需要 JSON 对象或 name/value 数组")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in cookies.items()):
        raise ValueError("Cookie 的键和值必须是字符串")
    if not cookies.get("unb", "").isdigit() or not cookies.get("_m_h5_tk"):
        raise ValueError("缺少有效的 unb 或 _m_h5_tk；请自行在浏览器登录后导入")
    return cookies
