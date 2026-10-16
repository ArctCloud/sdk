from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ResizeResponse(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    status: StrictStr
    resize_id: UUID
    invoice_id: UUID | None
    invoice_number: StrictStr | None
    amount: Decimal
    to_plan: StrictStr
    restart_required: StrictBool
