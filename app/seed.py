from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoverageCity, Subscriber, Tariff
from app.security import hash_pin

TARIFFS = [
    {
        "slug": "moy-online",
        "name": "Мой онлайн",
        "monthly_price": 500,
        "internet": "Безлимит + 50 ГБ каждый месяц",
        "minutes": "400 минут по России, безлимит на t2",
        "sms": "100 SMS по России",
        "extras": "Гигабэк, вечные минуты и ГБ, цена заморожена",
        "highlighted": True,
        "price_frozen_until": 2027,
    },
    {
        "slug": "moy-online-plus",
        "name": "Мой онлайн+",
        "monthly_price": 600,
        "internet": "Безлимит + 50 ГБ каждый месяц",
        "minutes": "800 минут по России, безлимит на t2",
        "sms": "100 SMS по России",
        "extras": "Гигабэк, вечные минуты и ГБ, цена заморожена",
        "highlighted": False,
        "price_frozen_until": 2027,
    },
    {
        "slug": "bezlimit",
        "name": "Безлимит",
        "monthly_price": 900,
        "internet": "Безлимит на общение и развлечения + 100 ГБ",
        "minutes": "1000 минут по России, безлимит на t2",
        "sms": "100 SMS по России",
        "extras": "Домашний интернет от 100 Мбит/с, цена заморожена",
        "highlighted": False,
        "price_frozen_until": 2027,
    },
    {
        "slug": "igrovoj",
        "name": "Игровой",
        "monthly_price": 950,
        "internet": "30 ГБ + 50 ГБ каждый месяц",
        "minutes": "700 минут по России, безлимит на t2",
        "sms": "100 SMS по России",
        "extras": "Приоритет для игрового трафика, без скрытых подписок",
        "highlighted": False,
        "price_frozen_until": None,
    },
    {
        "slug": "internet-devices",
        "name": "Интернет для устройств",
        "monthly_price": 1000,
        "internet": "60 ГБ + 50 ГБ каждый месяц",
        "minutes": "0 минут, безлимит на t2",
        "sms": "0 SMS",
        "extras": "Для модемов, планшетов и камер",
        "highlighted": False,
        "price_frozen_until": None,
    },
    {
        "slug": "internet-devices-plus",
        "name": "Интернет для устройств+",
        "monthly_price": 1300,
        "internet": "100 ГБ + 50 ГБ каждый месяц",
        "minutes": "0 минут, безлимит на t2",
        "sms": "0 SMS",
        "extras": "Максимум трафика для устройств, цена заморожена",
        "highlighted": False,
        "price_frozen_until": 2027,
    },
]

CITIES = [
    ("Москва", "Москва и область", True, True, 98),
    ("Санкт-Петербург", "Северо-Запад", True, True, 97),
    ("Волгоград", "Юг", True, True, 92),
    ("Челябинск", "Урал", True, True, 93),
    ("Екатеринбург", "Урал", True, True, 94),
    ("Пермь", "Урал", True, True, 91),
    ("Красноярск", "Сибирь", True, True, 90),
    ("Новосибирск", "Сибирь", True, False, 94),
    ("Казань", "Волга", True, False, 93),
    ("Ростов-на-Дону", "Юг", True, False, 92),
    ("Хабаровск", "Дальний Восток", True, False, 85),
    ("Калининград", "Северо-Запад", True, False, 90),
]


async def seed_if_empty(session: AsyncSession) -> None:
    existing = await session.scalar(select(Tariff.id).limit(1))
    if existing:
        return

    tariffs: dict[str, Tariff] = {}
    for item in TARIFFS:
        tariff = Tariff(**item)
        session.add(tariff)
        tariffs[item["slug"]] = tariff
    await session.flush()

    session.add_all(
        [
            Subscriber(
                phone="79001234567",
                full_name="Иван Петров",
                pin_hash=hash_pin("1234"),
                balance=847.50,
                remaining_gb=38.4,
                remaining_minutes=276,
                remaining_sms=81,
                region="Москва",
                tariff_id=tariffs["moy-online"].id,
            ),
            Subscriber(
                phone="79007654321",
                full_name="Анна Соколова",
                pin_hash=hash_pin("5678"),
                balance=120.00,
                remaining_gb=91.0,
                remaining_minutes=844,
                remaining_sms=64,
                region="Санкт-Петербург",
                tariff_id=tariffs["bezlimit"].id,
            ),
        ]
    )

    session.add_all(
        [
            CoverageCity(
                name=name,
                region=region,
                lte=lte,
                five_g=five_g,
                population_coverage=coverage,
            )
            for name, region, lte, five_g, coverage in CITIES
        ]
    )
    await session.commit()
