from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.instance import instance_info
from app.redis_client import get_redis
from app.security import format_phone
from app.services import (
    add_payment,
    authenticate,
    create_ticket,
    list_cities,
    list_tariffs,
    probe_network,
)
from app.sessions import RedisSessionStore, recent_hits

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["format_phone"] = format_phone
router = APIRouter()


def ctx(request: Request, **extra):
    subscriber = getattr(request.state, "subscriber", None)
    return {
        "request": request,
        "instance": instance_info(),
        "subscriber": subscriber,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    tariffs = await list_tariffs(db)
    return templates.TemplateResponse(
        request,
        "home.html",
        ctx(request, tariffs=tariffs[:3]),
    )


@router.get("/tariffs", response_class=HTMLResponse)
async def tariffs_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "tariffs.html",
        ctx(request, tariffs=await list_tariffs(db)),
    )


@router.get("/coverage", response_class=HTMLResponse)
async def coverage_page(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "coverage.html",
        ctx(request, cities=await list_cities(db)),
    )


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request, "about.html", ctx(request))


@router.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    return templates.TemplateResponse(
        request,
        "status.html",
        ctx(request, hits=await recent_hits(get_redis())),
    )


@router.get("/support", response_class=HTMLResponse)
async def support_page(request: Request, sent: int = 0):
    return templates.TemplateResponse(
        request,
        "support.html",
        ctx(request, sent=bool(sent), error=None),
    )


@router.post("/support", response_class=HTMLResponse)
async def support_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    name: str = Form(...),
    phone: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
):
    subscriber = getattr(request.state, "subscriber", None)
    await create_ticket(
        db,
        name=name,
        phone=phone,
        subject=subject,
        message=message,
        subscriber_id=subscriber.id if subscriber else None,
    )
    return RedirectResponse("/support?sent=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    if getattr(request.state, "subscriber", None):
        return RedirectResponse("/account", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        ctx(request, error=error),
    )


@router.post("/login")
async def login_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    phone: str = Form(...),
    pin: str = Form(...),
):
    subscriber = await authenticate(db, phone, pin)
    if subscriber is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            ctx(request, error="Неверный номер или PIN-код"),
            status_code=401,
        )
    response = RedirectResponse("/account", status_code=303)
    store = RedisSessionStore(get_redis(), get_settings())
    sid = await store.create({"subscriber_id": subscriber.id})
    store.attach_cookie(response, sid)
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse("/", status_code=303)
    store = RedisSessionStore(get_redis(), get_settings())
    await store.destroy(getattr(request.state, "session_id", None))
    store.clear_cookie(response)
    return response


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    if not getattr(request.state, "subscriber", None):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "account.html",
        ctx(request, topped_up=False, error=None),
    )


@router.post("/account/topup", response_class=HTMLResponse)
async def account_topup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    amount: str = Form(...),
    method: str = Form("card"),
):
    subscriber = getattr(request.state, "subscriber", None)
    if subscriber is None:
        return RedirectResponse("/login", status_code=303)
    try:
        value = Decimal(amount.replace(",", "."))
        if value <= 0 or value > 15000:
            raise ValueError
    except Exception:
        return templates.TemplateResponse(
            request,
            "account.html",
            ctx(request, error="Сумма должна быть от 1 до 15 000 ₽", topped_up=False),
            status_code=400,
        )
    await add_payment(db, subscriber, value, method)
    from app.services import get_subscriber_by_id

    request.state.subscriber = await get_subscriber_by_id(db, subscriber.id)
    return templates.TemplateResponse(
        request,
        "account.html",
        ctx(request, topped_up=True, error=None),
    )


@router.get("/coverage/scan", response_class=HTMLResponse)
async def coverage_scan_fragment(request: Request, db: AsyncSession = Depends(get_db)):
    results = await probe_network(db)
    return templates.TemplateResponse(
        request,
        "partials/scan_results.html",
        ctx(request, results=results),
    )
