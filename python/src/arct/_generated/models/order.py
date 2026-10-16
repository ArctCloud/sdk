from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class Order(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    order_number: StrictStr
    status: StrictStr
    payment_method: StrictStr
    amount: Decimal
    currency: StrictStr
    created_at: datetime
    paid_at: datetime | None
    server_id: UUID | None
