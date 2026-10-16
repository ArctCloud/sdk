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
