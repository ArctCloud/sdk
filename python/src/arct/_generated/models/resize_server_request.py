from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ResizeServerRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
    plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')]
    expected_amount: Annotated[Decimal, Field(ge=0.0)] | StrictStr | None = None
    payment_method: Literal['card', 'credit'] = None

    @model_validator(mode='before')
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for key in ['payment_method']:
                if key in value and value[key] is None:
                    raise ValueError(f'{key} cannot be null')
        return value
