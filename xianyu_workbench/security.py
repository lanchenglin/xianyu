from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from cryptography.fernet import Fernet

SENSITIVE = re.compile(r"cookie|token|authorization|password|secret|api.?key|_m_h5|\bunb\b", re.I)


class InvalidJSON(ValueError):
    """Fixed, non-sensitive error for all JSON trust boundaries."""


def strict_json(text):
    from .message_text import reject_constant, unique_object
    try:
        value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
        # Also rejects finite syntax that overflowed binary floats (e.g. 1e999).
        json.dumps(value, allow_nan=False)
        return value
    except (ValueError, TypeError, RecursionError):
        raise InvalidJSON('JSON 格式无效：不允许重复键或非有限数') from None


def bounded_json(chunks, limit=1_048_576, *, root_types=(dict,)):
    """Consume decoded HTTP bytes with a hard cap, before strict JSON parsing."""
    raw = bytearray()
    try:
        for chunk in chunks:
            if len(chunk) > limit - len(raw):
                raise InvalidJSON('外部 JSON 响应超过限制')
            raw.extend(chunk)
        value = strict_json(bytes(raw))
        if type(value) not in root_types:
            raise InvalidJSON('外部 JSON 响应结构无效')
        return value
    except Exception:
        raise InvalidJSON('外部 JSON 响应无效或超过限制') from None


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)
    except (ValueError, RecursionError):
        raise InvalidJSON('JSON 数据无法安全保存') from None


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
        return strict_json(self.fernet.decrypt(text.encode()))


def parse_cookies(text: str) -> dict[str, str]:
    if len(text) > 100_000:
        raise ValueError("Cookie 文件过大；只导出闲鱼相关域名")
    raw = strict_json(text)
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
