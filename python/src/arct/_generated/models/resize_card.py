from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ResizeCard(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    brand: StrictStr | None = None
    last4: StrictStr | None = None
    exp_month: StrictInt | None = None
    exp_year: StrictInt | None = None
