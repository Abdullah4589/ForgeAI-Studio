from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _as_utc_iso(value: datetime) -> str:
    # SQLite drops tzinfo; every timestamp we store is UTC, so restore it before serialising.
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


UtcDatetime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=(), str_strip_whitespace=True)
