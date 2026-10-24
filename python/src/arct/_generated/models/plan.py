from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator


class Plan(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    slug: StrictStr
    name: StrictStr
    location: StrictStr
    datacenters: list[StrictStr]
    tier: StrictStr
    cpu_cores: StrictInt
    ram_gb: StrictInt
    storage_gb: StrictInt
    bandwidth_tb: StrictInt
    network_speed_gbps: StrictInt | None
    price_monthly: Decimal
    in_stock: StrictBool
    backups_available: StrictBool
