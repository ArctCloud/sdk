from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class CreateServerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
    hostname: Annotated[StrictStr, Field(max_length=63, pattern='^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')]
    datacenter: Annotated[StrictStr, Field(pattern='^[A-Za-z]{2,5}[0-9]{1,2}$')] = None
    location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] = None
    plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')]
    image_id: UUID
    billing_period: Literal['monthly', 'quarterly', 'semi_annual', 'yearly'] = None
    ssh_key_ids: Annotated[list[UUID], Field(max_length=20)] = None
    coupon_code: Annotated[StrictStr, Field(max_length=64, min_length=1)] | None = None
    enable_backups: StrictBool = None
    payment_method: Literal['card', 'credit'] = None

    @model_validator(mode='before')
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for key in ['datacenter', 'location', 'billing_period', 'ssh_key_ids', 'enable_backups', 'payment_method']:
                if key in value and value[key] is None:
                    raise ValueError(f'{key} cannot be null')
        return value
