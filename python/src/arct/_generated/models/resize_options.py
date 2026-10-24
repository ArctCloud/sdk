from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.pending_resize import PendingResize
from arct._generated.models.resize_card import ResizeCard
from arct._generated.models.resize_plan import ResizePlan
from arct._generated.models.resize_promo import ResizePromo
from arct._generated.models.unpaid_invoice import UnpaidInvoice

class ResizeOptions(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    can_resize: StrictBool
    blocked_code: StrictStr | None
    blocked_reason: StrictStr | None
    current_plan: StrictStr
    billing_period: StrictStr
    current_price_period: Decimal | None
    period_end: datetime | None
    days_left: StrictInt | None
    card: ResizeCard | None
    payment_methods: list[StrictStr] = None
    credit_balance: Decimal = None
    promo: ResizePromo | None
    unpaid_invoice: UnpaidInvoice | None
    pending_resize: PendingResize | None
    plans: list[ResizePlan]

    @model_validator(mode='before')
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for key in ['payment_methods', 'credit_balance']:
                if key in value and value[key] is None:
                    raise ValueError(f'{key} cannot be null')
        return value
