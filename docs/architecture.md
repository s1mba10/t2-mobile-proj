# Архитектура t2-mobile

```mermaid
flowchart LR
  User[Клиент] --> Proxy[Nginx HTTP :8080]
  Proxy --> App1[app-1 :8000]
  Proxy --> App2[app-2 :8000]
  App1 --> PG[(PostgreSQL)]
  App2 --> PG
  App1 --> Redis[(Redis sessions)]
  App2 --> Redis
```

## Почему так

- Два одинаковых экземпляра приложения — требование работы №2 и задел под балансировщик работы №3.
- PostgreSQL общий: баланс, тарифы и обращения не привязаны к ноде.
- Redis общий: сессия переживает падение app-1 или app-2.
- TLS на приложении нет: uvicorn слушает HTTP, `SESSION_COOKIE_SECURE=false`.
- Идентичность ноды: заголовок `X-Backend-Instance`, страница `/status`, поле `handled_by` у платежей и тикетов.
