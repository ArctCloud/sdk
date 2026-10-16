from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.order import Order
from arct._generated.models.server import Server

class CreateServerResponse(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    order: Order
    server: Server | None
    password: SecretStr | None = None
