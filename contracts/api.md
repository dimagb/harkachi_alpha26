# Контракт API credit-core (v1)

Базовый путь `/api/v1`. JSON, `snake_case`. Аутентификация — `Authorization: Bearer <JWT>`. Это **контракт-источник**: бэкенд реализует его схемами Pydantic, OpenAPI генерируется из кода (`/api/v1/openapi.json`), фронтенд генерирует TS-клиент из OpenAPI. Изменение контракта — только через тимлида (PR в этот файл).

## Ошибки (единый формат)
```json
{ "error": { "code": "INVALID_TRANSITION", "message": "Нельзя принять оферту в состоянии DECLINED", "details": {} } }
```
Коды: `VALIDATION_ERROR` (422), `UNAUTHORIZED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `INVALID_TRANSITION` (409), `CONFLICT_VERSION` (409), `OFFER_EXPIRED` (409), `SIGN_NOT_ALLOWED` (403), `OTP_INVALID` (422).

## Аутентификация
| Метод | Путь | Роль | Запрос → ответ |
| --- | --- | --- | --- |
| POST | `/auth/login` | все | `{login, password}` → `{access_token, user: {id, full_name, role}}` |
| GET | `/me` | все | → `{user, companies: [{company, position, can_sign, is_founder}]}` |

## Клиент
| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/products` | Каталог: `[{code, name, description, purposes[], min_amount, max_amount, min_term, max_term, rate_from}]` |
| POST | `/calculator` | `{product_code, amount, term_months}` → `{monthly_payment, rate_estimate}` (без скоринга) |
| GET | `/companies/{id}/profile` | Профиль, подставленный из ЕГРЮЛ/ЕГРИП (мок) и профиля банка |
| POST | `/applications` | `{company_id, product_code, amount, term_months, purpose, purpose_text?, declared_revenue_year}` → `ApplicationClient` (DRAFT) |
| PATCH | `/applications/{id}` | Правка черновика, `If-Match: <version>` |
| GET | `/applications?company_id=` | Список заявок компании |
| GET | `/applications/{id}` | `ApplicationClient` (см. ниже) |
| POST | `/applications/{id}/otp` | `{purpose: "CONSENTS"/"OFFER"/"GUARANTEE"}` → `{otp_id, demo_code}` (код показывается на экране — A5) |
| POST | `/applications/{id}/submit` | `{otp_id, code, consents: {pdn: true, bki: true, auto_decision: true/false}}` → DRAFT→SUBMITTED. Только `can_sign` |
| POST | `/applications/{id}/info-response` | `{answers: [{item_code, value, comment}]}` → INFO_REQUESTED→VALIDATION |
| POST | `/applications/{id}/offer/accept` | `{offer_version}` → OFFER_ISSUED→SIGNING. Только `can_sign` |
| POST | `/applications/{id}/offer/reject` | → WITHDRAWN |
| POST | `/applications/{id}/sign` | `{otp_id, code, party_id}` → подпись участника; при всех подписях → SIGNED |
| POST | `/applications/{id}/withdraw` | → WITHDRAWN |
| POST | `/applications/{id}/objection` | `{text}` → DECLINED→MANUAL_REVIEW (только ИП, только авто-решение, ≤30 дней) |

### `ApplicationClient`
```json
{
  "id": "…", "version": 3, "state": "OFFER_ISSUED",
  "stage": { "index": 4, "code": "DECISION", "title": "Решение",
             "what_happens": "Предложение готово", "what_to_do": "Примите или откажитесь до 22.11.2026" },
  "timeline": [ { "stage_code": "APPLICATION", "status": "done", "at": "…" }, … ],
  "product_code": "EXPRESS", "amount": 1500000, "term_months": 24, "purpose": "WORKING_CAPITAL",
  "offer": { "version": 1, "kind": "APPROVED", "amount": 1500000, "term_months": 24, "rate": 22.0,
             "monthly_payment": 77850, "expires_at": "…", "explanation": ["Стабильные обороты", "Нет просрочек"] },
  "client_reason": { "category": "Кредитная история", "text": "…", "action": "…", "retry_after": "2026-11-22" },
  "info_request": { "items": [ { "item_code": "REVENUE_CONFIRM", "question": "…" } ], "due_at": "…" },
  "parties": [ { "id": "…", "role": "GUARANTOR", "full_name": "…", "signed": false } ],
  "can_object": false, "allowed_actions": ["ACCEPT_OFFER", "REJECT_OFFER", "WITHDRAW"]
}
```
Все перечисления (`state`, `stage.code`, `timeline[].status`, `allowed_actions`, `item_code`, коды причин) — `contracts/codes.md`. `allowed_actions` вычисляет бэкенд из машины состояний и прав пользователя — фронтенд показывает только эти кнопки. `offer.explanation` — клиентские формулировки сильных сторон (без баллов и порогов).

## Андеррайтер
| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/underwriting/queue` | Заявки в MANUAL_REVIEW: `[{id, company, product, amount, grade, route_reason, waiting_since}]` |
| GET | `/underwriting/applications/{id}` | `ApplicationBank`: всё из `ApplicationClient` + `decision` (score, grade, factors, rules_fired, internal_reasons, recommendation), `external_checks`, `events` |
| POST | `/underwriting/{id}/decision` | `{outcome: "APPROVE"/"COUNTER"/"DECLINE"/"REQUEST_INFO"/"RETRY_ENRICHMENT", amount?, term_months?, client_reason_category?, info_questions?: [string], comment}` |
| GET | `/bank/applications` | Все заявки с фильтрами по состоянию (журнал банка) |

## Служебное
| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/health`, `/ready` | Проверки для Docker |
| POST | `/demo/time-shift` | `{application_id, days}` — сдвиг сроков для демонстрации истечения (только при `DEMO_MODE=true`) |
| POST | `/preview` | **Б2, зарезервировано:** `{company_id, product_code, amount, term_months}` → `{max_amount, rate, grade_band}` без заявки и без основной части КИ |
