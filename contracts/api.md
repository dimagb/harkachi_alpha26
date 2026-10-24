# Контракт API credit-core (v1) — карта эндпоинтов

**Типы всех запросов и ответов, обязательность полей, ограничения и коды ошибок — только в `contracts/api-types.ts`.** Здесь — пути, роли и переходы. Перечисления — `contracts/codes.md`. Изменение контракта — PR через тимлида.

Базовый путь `/api/v1`. JSON, `snake_case`. Аутентификация — `Authorization: Bearer <JWT>`. Ошибки — `ApiError`. Бэкенд реализует типы схемами Pydantic (`extra="forbid"`); OpenAPI генерируется из кода (`/api/v1/openapi.json`), снимок — `contracts/openapi.json`, фронтенд генерирует TS-клиент из снимка.

| Метод | Путь | Роль | Запрос → ответ (`api-types.ts`) | Переход (`state-machine.md`) |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | все | `LoginRequest` → `LoginResponse` | — |
| GET | `/me` | все | → `MeResponse` | — |
| GET | `/products` | CLIENT, UNDERWRITER | → `Product[]` | — |
| POST | `/calculator` | CLIENT | `CalculatorRequest` → `CalculatorResponse` | — |
| GET | `/companies/{id}/profile` | CLIENT (своя компания) | → `CompanyProfile` | — |
| POST | `/applications` | CLIENT | `ApplicationCreate` → `ApplicationClient` | → DRAFT |
| PATCH | `/applications/{id}` | CLIENT, `If-Match: <version>` | `ApplicationPatch` → `ApplicationClient` | DRAFT |
| GET | `/applications?company_id=` | CLIENT | → `ApplicationListItem[]` | — |
| GET | `/applications/{id}` | CLIENT | → `ApplicationClient` | — |
| POST | `/applications/{id}/request-signature` | CLIENT без `can_sign` | — → `ApplicationClient` | DRAFT (флаг `awaiting_signature`) |
| POST | `/applications/{id}/otp` | CLIENT с `can_sign` (без права подписи → 403 `SIGN_NOT_ALLOWED`) | `OtpRequest` → `OtpResponse` | — |
| POST | `/applications/{id}/submit` | CLIENT с `can_sign` | `SubmitRequest` → `ApplicationClient` | DRAFT → SUBMITTED |
| POST | `/applications/{id}/info-response` | CLIENT | `InfoResponseRequest` → `ApplicationClient` | INFO_REQUESTED → VALIDATION / MANUAL_REVIEW |
| POST | `/applications/{id}/offer/accept` | CLIENT с `can_sign` | `AcceptOfferRequest` → `ApplicationClient` | OFFER_ISSUED → SIGNING |
| POST | `/applications/{id}/offer/reject` | CLIENT с `can_sign` (без права подписи → 403 `SIGN_NOT_ALLOWED`) | — → `ApplicationClient` | OFFER_ISSUED → WITHDRAWN |
| POST | `/applications/{id}/sign` | CLIENT / GUARANTOR (`party.user_id` = я) | `SignRequest` → `ApplicationClient` | SIGNING → SIGNED (все подписи) |
| POST | `/applications/{id}/withdraw` | CLIENT | — → `ApplicationClient` | * до SIGNED → WITHDRAWN |
| POST | `/applications/{id}/objection` | CLIENT с `can_sign` (ИП, авто-отказ, ≤30 дней; без права подписи → 403 `SIGN_NOT_ALLOWED`) | `ObjectionRequest` → `ApplicationClient` | DECLINED → MANUAL_REVIEW |
| GET | `/underwriting/queue` | UNDERWRITER | → `QueueItem[]` | — |
| GET | `/underwriting/applications/{id}` | UNDERWRITER | → `ApplicationBank` | — |
| POST | `/underwriting/{id}/decision` | UNDERWRITER | `UnderwriterDecisionRequest` → `ApplicationBank` | MANUAL_REVIEW → OFFER_ISSUED / DECLINED / INFO_REQUESTED / ENRICHMENT |
| GET | `/bank/applications?state=&page=&size=` | UNDERWRITER | → `Page<BankListItem>` | — |
| GET | `/health`, `/ready` | — | → `{status: "ok"}` | — |
| POST | `/demo/time-shift` | UNDERWRITER, только `DEMO_MODE=true` | `TimeShiftRequest` → `TimeShiftResponse` | истечения (→ EXPIRED) |
| POST | `/preview` | CLIENT — **Б2, зарезервировано** | `{company_id, product_code, amount, term_months}` → `{max_amount, rate, grade_band}` | — |

Системные переходы (SUBMITTED → … → DISBURSED, истечения) делает worker, не API.
