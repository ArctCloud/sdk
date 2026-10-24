from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class CreditTransaction(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    created_at: datetime
    type: StrictStr
    description: StrictStr
    amount: Decimal
    balance_after: Decimal
    invoice_id: UUID | None
    order_id: UUID | None
