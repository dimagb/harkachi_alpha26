# Модель данных (credit-core, PostgreSQL)

Все таблицы: `id` (UUID), `created_at`, `updated_at`. Деньги — `numeric(15,2)`, ставки — `numeric(5,2)`. Перечисления — строковые enum. Связь с требованиями — в скобках.

## Участники и справочники
| Таблица | Ключевые поля | Назначение |
| --- | --- | --- |
| `user` | login, password_hash, role (`CLIENT`/`UNDERWRITER`/`GUARANTOR`), full_name | Тестовые учётки (F2) |
| `company` | inn, ogrn, kind (`IP`/`OOO`), name, okved_main, reg_date, address | Клиент банка (F3) |
| `company_member` | user_id, company_id, position, **can_sign**, is_founder, share_pct | Право подписи ≠ роль (F14a); поручитель-учредитель |
| `account_turnover` | company_id, month, credit_turnover | Внутренние данные банка: обороты (скоринг) |
| `risk_flag` | company_id, aml_flag, fraud_flag, note | Внутренние флаги — **никогда** не попадают в клиентский API |
| `product` | code (`EXPRESS`/`WORKING_CAPITAL`/`OVERDRAFT`), name, description, params (json: суммы, сроки, лимиты, спреды, порог авто-решения) | Каталог (F4) |
| `decision_config` | version, key_rate, key_rate_date, params (json: пороги, веса), active | Версионированная конфигурация решения (F20) |
| `reason_catalog` | code, client_category, client_text, client_action, client_visible, bki_reason_code | Слой политики причин (legal F93) |

## Заявка и процесс
| Таблица | Ключевые поля | Назначение |
| --- | --- | --- |
| `application` | company_id, created_by, product_code, amount, term_months, purpose, purpose_text, declared_revenue_year, **state**, current_offer_id, previous_application_id, **version** | Заявка; состояние — `state-machine.md` (F5, F6, F19) |
| `party` | application_id, role (`BORROWER_SIGNATORY`/`GUARANTOR`), user_id (nullable), full_name, required_signature, status | Участники с подписью; задел Б1 |
| `consent` | application_id, party_id, type (`PDN`/`BKI`/`AUTO_DECISION`), granted, signed_at, expires_at, doc_hash | Согласия (F14; БКИ — 1 год для МСП) |
| `info_request` | application_id, source (`SYSTEM`/`UNDERWRITER`), items (json), due_at, response (json), responded_at | Дозапрос (F9) |
| `external_check` | application_id, source (`BKI`/`EGRUL`/`FNS`), request, response, status, attempts, fetched_at | Обогащение (F10) |
| `decision` | application_id, kind (`AUTO`/`MANUAL`), outcome (`APPROVE`/`COUNTER`/`DECLINE`/`MANUAL`/`REQUEST_INFO`), route_reason, grade, score, factors (json), rules_fired (json), internal_reasons (json), client_reason_code, recommendation (json), config_version, **inputs_snapshot** (json), made_by, comment | Решение со снимком входов (F11, F12, аудит) |
| `offer` | application_id, **version**, kind (`APPROVED`/`COUNTER`), product_code, amount, term_months, rate, monthly_payment, status (`ACTIVE`/`ACCEPTED`/`REJECTED`/`EXPIRED`/`SUPERSEDED`), expires_at | Версии оферты (F13) |
| `signature` | application_id, party_id, object_type (`CONSENT`/`OFFER`/`GUARANTEE`), object_id, doc_hash, otp_verified_at | Простая подпись кодом (F14) |
| `disbursement` | application_id, amount, disbursed_at, schedule (json) | Смоделированная выдача (F15) |
| `objection` | application_id, text, created_at, resolved_at, outcome | Возражение ИП (152-ФЗ ст. 16) |
| `application_event` | application_id, from_state, to_state, event_type, actor_type, actor_id, reason_code, payload, created_at | Журнал только на добавление: лента статуса, аудит, `BKI_REPORT` |
| `job` | application_id, step, status, attempts, run_after, last_error | Очередь worker-а |

Договор отдельной таблицей не хранится: договор = принятая оферта (`offer.status = ACCEPTED`) + подписи (`signature` с `doc_hash`). Ответы источников хранятся в `external_check.response` (в `process.md` они названы `bureau_report`, `registry_record`, `tax_check` — это `external_check` с `source` = `BKI` / `EGRUL` / `FNS`). Все перечисления — `contracts/codes.md`.

## Мок-сервис (external-mocks)
Без БД: ответы строятся из `contracts/personas.json` (тот же файл, что и сиды credit-core) + детерминированный генератор для неизвестных ИНН. Настройка `MOCK_FAILURE_INN` — какие ИНН отвечают ошибкой (демо повторов).

## Правила видимости
Клиентский API отдаёт: заявку, ленту (`application_event` → этапы ленты), оферту, `client_reason` (из `reason_catalog` по `client_reason_code`), свои согласия и подписи. **Не отдаёт:** `risk_flag`, `internal_reasons`, `factors`, `rules_fired`, `inputs_snapshot`, пороги. Андеррайтер видит всё.
