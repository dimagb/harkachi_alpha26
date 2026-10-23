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
  "current_overdue_total": 0, "max_dpd_12m": 0 } }
```
`INFO` (информационная часть) — только `summary` без деталей по кредитам.

## ФНС («Прозрачный бизнес» + ФССП + банкротство в одном ответе)
`GET /fns/check/{inn}` →
```json
{ "inn": "…", "tax_debt": 0, "enforcement_sum": 0, "bankruptcy": false,
  "msp_registry": { "included": true, "category": "MICRO" }, "mass_director": false, "mass_address": false }
```

## Служебное
`GET /health`. Фикстуры — `external-mocks/fixtures/{inn}.json`, по одному файлу на демо-компанию (`decision-model.md` §8).
