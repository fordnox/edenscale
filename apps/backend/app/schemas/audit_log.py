import json
from datetime import datetime
from typing import Any

from pydantic import UUID4, BaseModel, ConfigDict, field_validator


class AuditLogRead(BaseModel):
    id: UUID4
    user_id: UUID4 | None
    organization_id: UUID4 | None
    action: str
    entity_type: str | None
    entity_id: UUID4 | None
    audit_metadata: dict[str, Any] | None
    ip_address: str | None
    country: str | None
    user_agent: str | None
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
