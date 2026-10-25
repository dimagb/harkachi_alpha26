# Модель данных (credit-core, PostgreSQL)

Все таблицы: `id` (UUID), `created_at`, `updated_at`. Деньги — целые рубли `bigint` (платёж — ROUND_HALF_UP до рубля), ставки — `numeric(5,2)`, месяц — `YYYY-MM`. Перечисления — строковые enum. Связь с требованиями — в скобках.

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
| `application` | number (последовательный), company_id, created_by, product_code, amount, term_months, purpose, purpose_text, declared_revenue_year, **state**, current_offer_id, previous_application_id, awaiting_signature, submitted_at, **version** | Заявка; состояние — `state-machine.md` (F5, F6, F19) |
| `party` | application_id, role (`BORROWER_SIGNATORY`/`GUARANTOR`), user_id (nullable), full_name, required_signature, status (`PENDING`/`SIGNED`; в API → `signed: boolean`) | Участники с подписью; задел Б1 |
| `consent` | application_id, party_id, type (`PDN`/`BKI`/`AUTO_DECISION`), granted, signed_at, expires_at, doc_hash | Согласия (F14; БКИ — 1 год для МСП) |
| `info_request` | application_id, source (`SYSTEM`/`UNDERWRITER`), items (json), due_at, response (json), responded_at | Дозапрос (F9) |
| `external_check` | application_id, source (`BKI`/`EGRUL`/`FNS`), request, response, status, attempts, fetched_at | Обогащение (F10) |
| `decision` | application_id, kind (`AUTO`/`MANUAL`), outcome (`APPROVE`/`COUNTER`/`DECLINE`/`MANUAL`/`REQUEST_INFO`), route_reason, grade, score, factors (json), rules_fired (json), internal_reasons (json), client_reason_code, recommendation (json), policy (json), what_if (json), config_version, **inputs_snapshot** (json), made_by, comment | Решение со снимком входов (F11, F12, аудит) |
| `offer` | application_id, **version**, kind (`APPROVED`/`COUNTER`), product_code, amount, term_months, rate, monthly_payment, status (`ACTIVE`/`ACCEPTED`/`REJECTED`/`EXPIRED`/`SUPERSEDED`), expires_at | Версии оферты (F13) |
| `signature` | application_id, party_id, object_type (`CONSENT`/`OFFER`/`GUARANTEE`), object_id, doc_hash, otp_verified_at | Простая подпись кодом (F14) |
| `disbursement` | application_id, amount, disbursed_at, schedule (json) | Смоделированная выдача (F15) |
| `objection` | application_id, text, created_at, resolved_at, outcome | Возражение ИП (152-ФЗ ст. 16) |
| `application_event` | application_id, from_state, to_state, event_type, actor_type, actor_id, reason_code, payload, created_at | Журнал только на добавление: лента статуса, аудит, `BKI_REPORT` |
| `job` | application_id, step, status, attempts, run_after, last_error | Очередь worker-а |
| `otp` | application_id, user_id, party_id (nullable), purpose (`CONSENTS`/`OFFER`/`GUARANTEE`), code_hash, expires_at, attempts, used_at | Одноразовый код подписи (A5), 5 минут, ≤5 попыток; код только хэшем |

Договор отдельной таблицей не хранится: договор = принятая оферта (`offer.status = ACCEPTED`) + подписи (`signature` с `doc_hash`). Ответы источников хранятся в `external_check.response` (в `process.md` они названы `bureau_report`, `registry_record`, `tax_check` — это `external_check` с `source` = `BKI` / `EGRUL` / `FNS`). Все перечисления — `contracts/codes.md`.

## Мок-сервис (external-mocks)
Без БД: ответы строятся из `contracts/personas.json` (тот же файл, что и сиды credit-core) + детерминированный генератор для неизвестных ИНН. Настройка `MOCK_FAILURE_INN` — какие ИНН отвечают ошибкой (демо повторов).

## Синтетические данные (T5)

Два слоя, оба детерминированные (фиксированный seed) и воспроизводимые при каждом `docker compose up`:
1. **Персонажи для демо** — `contracts/personas.json`: 6 компаний с точными входами и ожидаемым исходом (golden-тесты). Обороты — 12 месяцев (октябрь 2025 — сентябрь 2026), заданы явно.
2. **Фон для банка** — генератор (`seed --background 40`): ~40 компаний и ~60 заявок в разных состояниях, чтобы журнал банка и очередь андеррайтера выглядели живыми. Правила генерации:
   - тип: 60% ООО / 40% ИП; ИНН с правильной контрольной суммой; ОКВЭД из списка отраслей `decision-model.md`;
   - дата регистрации: 3–120 мес. назад (лог-нормальное, медиана ~30 мес.);
   - обороты: средний 0,3–8 млн/мес. (лог-нормальное) × сезонность (синусоида ±15%) × шум (CV 0,1–0,7);
   - БКИ: у 60% есть кредиты (платежи 5–35% оборота); просрочка 1–30 дней у 10%, 31–90 у 5%, текущая у 3%;
   - ФНС: налоговый долг у 8% (у трети — выше стоп-порога), исполнительные производства у 5%, банкротство у 1%; флаг ПОД/ФТ у 2%;
   - заявки фона проходят **тот же** конвейер и модель решения (не подставляются готовыми результатами) — это заодно нагрузочная проверка правил.
Генератор и сиды — задача агента аналитики; проверка — тест «все персонажи дают `demo.expected`».

## Правила видимости
Клиентский API отдаёт: заявку, ленту (`application_event` → этапы ленты), оферту, `client_reason` (из `reason_catalog` по `client_reason_code`), свои согласия и подписи. **Не отдаёт:** `risk_flag`, `internal_reasons`, `factors`, `rules_fired`, `inputs_snapshot`, пороги. Андеррайтер видит всё.

## Поля формы заявки → где используются в процессе

Клиент вводит только то, чего банк не знает; остальное подставляется из профиля (требование F5). Каждое введённое поле используется дальше — ниже, где именно.

| Поле формы | Таблица / поле | Где используется |
| --- | --- | --- |
| Продукт | `application.product_code` | калькулятор (`catalog/calculator.py`); кредитная политика — лимиты суммы и срока, спред по оценке, порог авто-решения (`decision/policy.py`); нагрузка PTR в оценке — платёж по максимальной ставке продукта (`decision/scoring.py`); маршрут к специалисту при сумме выше порога (`decision/engine.py`); очередь и журнал банка |
| Сумма | `application.amount` | калькулятор; PTR и долг к обороту в оценке; лимит по оборотам и встречное предложение в политике; оферта, договор, выдача и график (`disbursement/service.py`); очередь и карточка андеррайтера |
| Срок | `application.term_months` | калькулятор; платёж в PTR; перебор срока для встречного предложения; оферта, график платежей |
| Цель | `application.purpose`, `purpose_text` | правило полноты: цель «Другое» без пояснения → дозапрос `PURPOSE_DETAILS` (`decision/engine.py`); текст договора и подписи (`signing/`); карточка андеррайтера |
| Выручка за год | `application.declared_revenue_year` | сверка с оборотами по счёту: расхождение > 40 % → дозапрос «Подтвердите выручку» (`VAL_REVENUE_MISMATCH`, A17); ответ клиента обновляет значение (`api/routes.py`); протокол решения |
| Согласия (ПДн, БКИ, авто-решение для ИП) | `consent` | без ПДн и БКИ заявка не подаётся (`signing/submit.py`); согласие на БКИ передаётся в запросе кредитного отчёта; без согласия ИП на авто-решение — маршрут к специалисту (`NO_AUTO_CONSENT`) |
| Из профиля (не вводится): компания, ИНН, ОГРН, руководитель, учредители, обороты за 12 мес. | `company`, `company_member`, `account_turnover` | запросы к ЕГРЮЛ/ЕГРИП, ФНС, БКИ по ИНН; признаки оценки (срок бизнеса, массовый руководитель, обороты); поручитель для ООО — учредитель с долей > 50 % (`signing/submit.py`) |
