from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.instance import instance_info
from app.metrics import render as render_metrics
from app.redis_client import get_redis
from app.schemas import CoverageProbeOut, InstanceOut, LoginIn, TariffOut, TicketIn, TopUpIn
from app.services import (
    add_payment,
    authenticate,
    create_ticket,
    list_tariffs,
    probe_city,
    probe_network,
)
from app.sessions import RedisSessionStore, recent_hits

router = APIRouter()


def current_subscriber(request: Request):
    return request.state.subscriber


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", **instance_info()}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    pong = await get_redis().ping()
    if not pong:
        raise HTTPException(status_code=503, detail="redis unavailable")
    return {"status": "ready", **instance_info()}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Метрики для Prometheus. Каждая серия помечена идентификатором ноды."""
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@router.get("/v1/instance", response_model=InstanceOut)
async def instance_endpoint() -> dict:
    return instance_info()


@router.get("/v1/hits")
async def hits() -> dict:
    return {"hits": await recent_hits(get_redis()), "served_by": instance_info()}


@router.get("/v1/tariffs", response_model=list[TariffOut])
async def tariffs(db: AsyncSession = Depends(get_db)) -> list:
    return await list_tariffs(db)


@router.post("/v1/auth/login")
async def login(
    payload: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscriber = await authenticate(db, payload.phone, payload.pin)
    if subscriber is None:
        raise HTTPException(status_code=401, detail="Неверный номер или PIN")
    store = RedisSessionStore(get_redis(), get_settings())
    sid = await store.create({"subscriber_id": subscriber.id})
    store.attach_cookie(response, sid)
    return {
        "ok": True,
        "full_name": subscriber.full_name,
        "phone": subscriber.phone,
        "served_by": instance_info(),
    }


@router.post("/v1/auth/logout")
async def logout(request: Request, response: Response) -> dict:
    store = RedisSessionStore(get_redis(), get_settings())
    await store.destroy(request.state.session_id)
    store.clear_cookie(response)
    return {"ok": True}


@router.get("/v1/account")
async def account(request: Request) -> dict:
    subscriber = current_subscriber(request)
    if subscriber is None:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    return {
        "full_name": subscriber.full_name,
        "phone": subscriber.phone,
        "balance": str(subscriber.balance),
        "tariff": subscriber.tariff.name if subscriber.tariff else None,
        "remaining_gb": str(subscriber.remaining_gb),
        "remaining_minutes": subscriber.remaining_minutes,
        "remaining_sms": subscriber.remaining_sms,
        "served_by": instance_info(),
    }


@router.post("/v1/account/topup")
async def topup(
    payload: TopUpIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscriber = current_subscriber(request)
    if subscriber is None:
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    payment = await add_payment(db, subscriber, payload.amount, payload.method)
    return {
        "ok": True,
        "balance": str(subscriber.balance),
        "payment_id": payment.id,
        "handled_by": payment.handled_by,
        "served_by": instance_info(),
    }


@router.post("/v1/tickets")
async def tickets(
    payload: TicketIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    subscriber = current_subscriber(request)
    ticket = await create_ticket(
        db,
        name=payload.name,
        phone=payload.phone,
        subject=payload.subject,
        message=payload.message,
        subscriber_id=subscriber.id if subscriber else None,
    )
    return {"ok": True, "ticket_id": ticket.id, "handled_by": ticket.handled_by}


@router.get("/v1/coverage/probe/{city}", response_model=CoverageProbeOut)
async def coverage_probe(city: str, db: AsyncSession = Depends(get_db)) -> dict:
    found = await probe_city(db, city)
    if found is None:
        raise HTTPException(status_code=404, detail="Город не найден в сети t2")
    return {
        "city": found.name,
        "region": found.region,
        "lte": found.lte,
        "five_g": found.five_g,
        "population_coverage": found.population_coverage,
        "latency_ms": 18,
        "signal_dbm": -79,
        "probed_by": instance_info()["instance_id"],
    }


@router.get("/v1/coverage/scan")
async def coverage_scan(db: AsyncSession = Depends(get_db)) -> dict:
    results = await probe_network(db)
    return {"results": results, "served_by": instance_info()}


@router.get("/v1/events")
async def events() -> StreamingResponse:
    async def _stream():
        while True:
            payload = json.dumps(
                {"type": "heartbeat", "served_by": instance_info()},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(_stream(), media_type="text/event-stream")
