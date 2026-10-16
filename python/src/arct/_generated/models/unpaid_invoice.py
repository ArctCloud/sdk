from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class UnpaidInvoice(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    invoice_number: StrictStr
    total: Decimal
    due_date: datetime
    overdue: StrictBool
