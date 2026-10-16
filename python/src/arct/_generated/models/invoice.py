from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.invoice_item import InvoiceItem
from arct._generated.models.invoice_status import InvoiceStatus

class Invoice(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    invoice_number: StrictStr
    status: InvoiceStatus
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    refunded_total: Decimal
    period_start: datetime
    period_end: datetime
    due_date: datetime
    paid_at: datetime | None
    payment_method: StrictStr | None
    hosted_invoice_url: StrictStr | None
    created_at: datetime
    items: list[InvoiceItem]
