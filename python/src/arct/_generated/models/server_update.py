from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class ServerUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
    hostname: Annotated[StrictStr, Field(max_length=63, min_length=1, pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')] = None
    delete_protection: StrictBool = None
    labels: Annotated[list[Annotated[StrictStr, Field(max_length=63)]], Field(max_length=100)] = None

    @model_validator(mode='before')
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for key in ['hostname', 'delete_protection', 'labels']:
                if key in value and value[key] is None:
                    raise ValueError(f'{key} cannot be null')
        return value
