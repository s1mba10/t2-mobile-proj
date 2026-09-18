from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    monthly_price: Mapped[int] = mapped_column(Integer)
    internet: Mapped[str] = mapped_column(String(120))
    minutes: Mapped[str] = mapped_column(String(120))
    sms: Mapped[str] = mapped_column(String(80))
    extras: Mapped[str] = mapped_column(Text)
    highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    price_frozen_until: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subscribers: Mapped[list[Subscriber]] = relationship(back_populates="tariff")


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    pin_hash: Mapped[str] = mapped_column(String(128))
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    remaining_gb: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    remaining_minutes: Mapped[int] = mapped_column(Integer, default=0)
    remaining_sms: Mapped[int] = mapped_column(Integer, default=0)
    region: Mapped[str] = mapped_column(String(80), default="Москва")
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tariff: Mapped[Tariff] = relationship(back_populates="subscribers")
    payments: Mapped[list[Payment]] = relationship(back_populates="subscriber")
    tickets: Mapped[list[SupportTicket]] = relationship(back_populates="subscriber")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String(40), default="card")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    handled_by: Mapped[str] = mapped_column(String(64))

    subscriber: Mapped[Subscriber] = relationship(back_populates="payments")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber_id: Mapped[int | None] = mapped_column(ForeignKey("subscribers.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(15))
    subject: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    handled_by: Mapped[str] = mapped_column(String(64))

    subscriber: Mapped[Subscriber | None] = relationship(back_populates="tickets")


class CoverageCity(Base):
    __tablename__ = "coverage_cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    region: Mapped[str] = mapped_column(String(80))
    lte: Mapped[bool] = mapped_column(Boolean, default=True)
    five_g: Mapped[bool] = mapped_column(Boolean, default=False)
    population_coverage: Mapped[int] = mapped_column(Integer, default=90)
