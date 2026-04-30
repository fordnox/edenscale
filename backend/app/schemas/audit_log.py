import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLogRead(BaseModel):
    id: int
    user_id: int | None
    organization_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    audit_metadata: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("audit_metadata", mode="before")
    @classmethod
    def _parse_metadata(cls, value: Any) -> Any:
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {"raw": value}
        return value
