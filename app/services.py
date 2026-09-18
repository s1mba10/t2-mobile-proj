from __future__ import annotations

import asyncio
import random
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.instance import instance_id
from app.models import CoverageCity, Payment, Subscriber, SupportTicket, Tariff
from app.security import normalize_phone, verify_pin


async def list_tariffs(session: AsyncSession) -> list[Tariff]:
    result = await session.scalars(select(Tariff).order_by(Tariff.monthly_price))
    return list(result)


async def get_subscriber_by_phone(session: AsyncSession, phone: str) -> Subscriber | None:
    stmt = (
        select(Subscriber)
        .options(selectinload(Subscriber.tariff), selectinload(Subscriber.payments))
        .where(Subscriber.phone == normalize_phone(phone))
    )
    return await session.scalar(stmt)


async def get_subscriber_by_id(session: AsyncSession, subscriber_id: int) -> Subscriber | None:
    stmt = (
        select(Subscriber)
        .options(
            selectinload(Subscriber.tariff),
            selectinload(Subscriber.payments),
            selectinload(Subscriber.tickets),
        )
        .where(Subscriber.id == subscriber_id)
    )
    return await session.scalar(stmt)


async def authenticate(session: AsyncSession, phone: str, pin: str) -> Subscriber | None:
    subscriber = await get_subscriber_by_phone(session, phone)
    if subscriber and verify_pin(pin, subscriber.pin_hash):
        return subscriber
    return None


async def add_payment(
    session: AsyncSession, subscriber: Subscriber, amount, method: str
) -> Payment:
    managed = await session.get(Subscriber, subscriber.id)
    if managed is None:
        raise ValueError("subscriber not found")
    payment = Payment(
        subscriber_id=managed.id,
        amount=amount,
        method=method,
        handled_by=instance_id(),
    )
    managed.balance = Decimal(str(managed.balance or 0)) + Decimal(str(amount))
    session.add(payment)
    await session.commit()
    await session.refresh(managed)
    subscriber.balance = managed.balance
    return payment


async def create_ticket(
    session: AsyncSession,
    *,
    name: str,
    phone: str,
    subject: str,
    message: str,
    subscriber_id: int | None,
) -> SupportTicket:
    ticket = SupportTicket(
        subscriber_id=subscriber_id,
        name=name,
        phone=normalize_phone(phone),
        subject=subject,
        message=message,
        handled_by=instance_id(),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def list_cities(session: AsyncSession) -> list[CoverageCity]:
    result = await session.scalars(select(CoverageCity).order_by(CoverageCity.name))
    return list(result)


async def probe_city(session: AsyncSession, name: str) -> CoverageCity | None:
    city = await session.scalar(select(CoverageCity).where(CoverageCity.name.ilike(name)))
    if city is None:
        return None
    await asyncio.sleep(random.uniform(0.08, 0.28))
    return city


async def probe_network(session: AsyncSession) -> list[dict]:
    cities = await list_cities(session)

    async def _probe(city: CoverageCity) -> dict:
        delay = random.uniform(0.05, 0.22)
        await asyncio.sleep(delay)
        return {
            "city": city.name,
            "region": city.region,
            "lte": city.lte,
            "five_g": city.five_g,
            "population_coverage": city.population_coverage,
            "latency_ms": int(delay * 1000) + random.randint(8, 24),
            "signal_dbm": random.randint(-102, -68),
            "probed_by": instance_id(),
        }

    return await asyncio.gather(*[_probe(city) for city in cities])
