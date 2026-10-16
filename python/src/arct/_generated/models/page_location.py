from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.location import Location
from arct._generated.models.pagination import Pagination

class PageLocation(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    data: list[Location]
    pagination: Pagination
