from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class TokenInfo(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    name: StrictStr
    scope: StrictStr
    expires_at: datetime | None
