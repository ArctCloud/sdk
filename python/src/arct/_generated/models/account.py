from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.token_info import TokenInfo

class Account(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    email: StrictStr
    name: StrictStr | None
    email_verified: StrictBool
    created_at: datetime
    credit_balance: Decimal = None
    credit_autopay: StrictBool = None
    token: TokenInfo

    @model_validator(mode='before')
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for key in ['credit_balance', 'credit_autopay']:
                if key in value and value[key] is None:
                    raise ValueError(f'{key} cannot be null')
        return value
