from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InstanceOut(BaseModel):
    instance_id: str
    hostname: str
    pid: int
    platform: str
    started_at: str
    uptime_seconds: int
    tls_terminated_here: bool


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    monthly_price: int
    internet: str
    minutes: str
    sms: str
    extras: str
    highlighted: bool
    price_frozen_until: int | None


class LoginIn(BaseModel):
    phone: str
    pin: str = Field(min_length=4, max_length=8)


class TopUpIn(BaseModel):
    amount: Decimal = Field(gt=0, le=15000)
    method: str = "card"


class TicketIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=8, max_length=4000)


class CoverageProbeOut(BaseModel):
    city: str
    region: str
    lte: bool
    five_g: bool
    population_coverage: int
    latency_ms: int
    signal_dbm: int
    probed_by: str
