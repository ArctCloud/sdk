from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ResizePromo(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    code: StrictStr
    discount_type: StrictStr
    discount_value: Decimal
    label: StrictStr
