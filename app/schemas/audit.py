from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    old_values: dict | None = None
    new_values: dict | None = None
    changed_by: str
    change_source: str
    change_reason: str | None = None
    source_reference: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
