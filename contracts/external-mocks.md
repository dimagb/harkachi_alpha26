# Контракт мок-сервиса внешних источников (external-mocks v1)

Отдельный сервис, базовый путь `/mock/v1`. Отвечает по ИНН: из фикстуры (демо-персонажи) или детерминированным генератором. Если ИНН есть в `MOCK_FAILURE_INN`, сервис отвечает `503` (демо повторов). Форматы упрощены с сохранением смысла (кейс, Пространство решений п. 5).

## ЕГРЮЛ / ЕГРИП
`GET /registry/{inn}` →
```json
{ "inn": "7701234567", "ogrn": "1197746000000", "kind": "OOO", "name": "ООО «Северный склад»",
  "status": "ACTIVE", "reg_date": "2023-05-12", "okved_main": "52.10", "address": "г. Москва, …",
  "director": { "full_name": "Петров И. И.", "inn": "…" },
  "founders": [ { "full_name": "Петров И. И.", "share_pct": 100 } ] }
```
`status`: `ACTIVE` / `LIQUIDATING` / `LIQUIDATED`.

## БКИ
`POST /bki/report` `{inn, kind: "INFO"/"FULL", consent_id?}` → `FULL` без `consent_id` → `403`.
```json
{ "inn": "…", "kind": "FULL", "loans": [ { "type": "CREDIT", "balance": 1200000, "monthly_payment": 450000,
  "current_overdue": 0, "max_dpd_12m": 0 } ], "summary": { "monthly_payments_total": 450000,
  "total_balance": 7000000, "current_overdue_total": 0, "max_dpd_12m": 0,
  "credit_history_months": 30, "inquiries_30d": 3 } }
```
`INFO` (информационная часть) — только `summary` без деталей по кредитам.

## ФНС («Прозрачный бизнес» + ФССП + банкротство в одном ответе)
`GET /fns/check/{inn}` →
```json
{ "inn": "…", "tax_debt": 0, "enforcement_sum": 0, "arbitration_defendant_sum": 0, "bankruptcy": false,
  "msp_registry": { "included": true, "category": "MICRO" }, "mass_director": false, "mass_address": false }
```

## Служебное
`GET /health`. Ответы для демо-компаний строятся из `contracts/personas.json`: ЕГРЮЛ/ЕГРИП — `inn, ogrn, kind, name, status, reg_date, okved_main, address, director, founders`; БКИ — `bki.loans` + `bki.summary`; ФНС — `fns`; `INFO`-запрос БКИ отдаёт только `summary`. Каждый источник в credit-core вызывается через адаптер (`RegistryProvider`, `BureauProvider`, `TaxProvider`): мок — по умолчанию, реальный провайдер подключается заменой адаптера (раздел «Развитие»).
