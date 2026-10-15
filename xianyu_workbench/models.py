from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AccountIn(Model):
    label: str = Field(min_length=1, max_length=50)
    mode: Literal["demo", "live"] = "demo"
    cookies_json: str = Field(default="", max_length=100_000)


class CookiesIn(Model):
    cookies_json: str = Field(min_length=2, max_length=100_000)


class SearchIn(Model):
    account_id: str
    query: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=20, ge=1, le=50)
    min_price: Decimal | None = Field(default=None, ge=0, le=1_000_000)
    max_price: Decimal | None = Field(default=None, ge=0, le=1_000_000)
    location: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def price_range(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("最低价不能高于最高价")
        return self


class MessageIn(Model):
    cid: str = Field(min_length=1, max_length=150, pattern=r"^[\w@.:/+=-]+$")
    toid: str = Field(pattern=r"^\d{1,30}$")
    text: str = Field(min_length=1, max_length=1500)


class PublishIn(Model):
    title: str = Field(min_length=1, max_length=60)
    desc: str = Field(min_length=1, max_length=5000)
    images: list[str] = Field(min_length=1, max_length=9)
    price: Decimal = Field(gt=0, le=1_000_000, decimal_places=2)
    delivery: Literal["包邮", "一口价", "无需邮寄"] = "无需邮寄"
    post_price: Decimal = Field(default=Decimal("0"), ge=0, le=10000, decimal_places=2)
    can_self_pickup: bool = True

    @field_validator("images")
    @classmethod
    def image_ids(cls, values):
        import re
        if not all(re.fullmatch(r"[a-f0-9]{32}", x) for x in values):
            raise ValueError("images 必须是工作台已上传的图片 ID，不接受路径或 URL")
        return list(dict.fromkeys(values))


class DeleteIn(Model):
    item_id: str = Field(pattern=r"^\d{1,30}$")
    acknowledgement: Literal["我理解这可能永久删除商品，不是普通下架"]


ACTION_MODELS = {"message.send": MessageIn, "item.publish": PublishIn, "item.delete": DeleteIn}


class ActionIn(Model):
    account_id: str
    kind: Literal["message.send", "item.publish", "item.delete"]
    payload: dict
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[\w.:-]+$")


class ApprovalIn(Model):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm: Literal["确认执行"]


class ReconciliationIn(Model):
    account_id: str = Field(min_length=1, max_length=100)
    outcome: Literal["observed", "not_observed", "unresolved"]
    evidence: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[\w.:-]+$")


class DraftIn(Model):
    account_id: str
    title: str = Field(default="", max_length=60)
    desc: str = Field(default="", max_length=5000)
    price: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000, decimal_places=2)
    images: list[str] = Field(default_factory=list, max_length=9)
    delivery: Literal["包邮", "一口价", "无需邮寄"] = "无需邮寄"
    post_price: Decimal = Field(default=Decimal("0"), ge=0, le=10000, decimal_places=2)
    can_self_pickup: bool = True


class DraftEditIn(DraftIn):
    revision: int = Field(ge=1)


class DraftArchiveIn(Model):
    account_id: str
    revision: int = Field(ge=1)


class MonitorIn(SearchIn):
    interval_s: int = Field(default=900, ge=300, le=86400)


class LLMConfigIn(Model):
    base_url: str = Field(max_length=400)
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(default="", max_length=1000)


class AssistIn(Model):
    purpose: Literal["listing", "reply", "compare", "inquiry"]
    facts: str = Field(min_length=1, max_length=18000)
    instruction: str = Field(default="", max_length=2000)
