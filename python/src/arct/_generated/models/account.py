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
    credit_balance: Decimal
    credit_autopay: StrictBool
    token: TokenInfo
