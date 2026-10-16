from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ResizePlan(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    slug: StrictStr
    name: StrictStr
    cpu_cores: StrictInt
    ram_gb: StrictInt
    storage_gb: StrictInt
    bandwidth_tb: StrictInt
    price_period: Decimal
    price_period_list: Decimal
    promo_applies: StrictBool
    is_current: StrictBool
    eligible: StrictBool
    reason: StrictStr | None
    reason_label: StrictStr | None
    amount_due_today: Decimal | None
