from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class SshKeyCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
    name: Annotated[StrictStr, Field(max_length=255, min_length=1)]
    public_key: Annotated[StrictStr, Field(max_length=8192, min_length=1)]
