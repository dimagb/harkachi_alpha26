# Реестр кодов (единственный источник перечислений)

Бэкенд (enum), фронтенд (тексты), сиды и тесты берут коды **только отсюда**. Новый код — PR в этот файл через тимлида.

## Состояния заявки (`application.state`)
`DRAFT`, `SUBMITTED`, `VALIDATION`, `INFO_REQUESTED`, `ENRICHMENT`, `ASSESSMENT`, `MANUAL_REVIEW`, `OFFER_ISSUED`, `DECLINED`, `SIGNING`, `SIGNED`, `DISBURSED`, `WITHDRAWN`, `EXPIRED`.

## Этапы ленты (`stage.code`)
| index | code | title | Состояния |
| --- | --- | --- | --- |
| 1 | `APPLICATION` | Заявка | DRAFT, SUBMITTED |
| 2 | `CHECK` | Проверка данных | VALIDATION, ENRICHMENT, INFO_REQUESTED |
| 3 | `ASSESSMENT` | Оценка | ASSESSMENT, MANUAL_REVIEW |
| 4 | `DECISION` | Решение | OFFER_ISSUED, DECLINED |
| 5 | `SIGNING` | Подписание | SIGNING, SIGNED |
| 6 | `DISBURSEMENT` | Выдача | DISBURSED |
`timeline[].status`: `done` / `current` / `action_required` (ждём клиента) / `pending` / `failed` (отказ) / `cancelled` (отзыв, истечение).

## Продукты, цели
Продукты: `EXPRESS`, `WORKING_CAPITAL`, `OVERDRAFT`. Цели (`purpose`): `WORKING_CAPITAL` (оборотные средства), `CASH_GAP` (кассовый разрыв), `EQUIPMENT` (оборудование и развитие), `OTHER` (нужен `purpose_text`).

## Действия клиента (`allowed_actions`)
`EDIT_DRAFT`, `SUBMIT`, `REQUEST_SIGNATURE` (у пользователя без `can_sign`: просит подписанта, в продукте, без почты), `ANSWER_INFO_REQUEST`, `ACCEPT_OFFER`, `REJECT_OFFER`, `SIGN` (свою или за участника, где `party.user_id` = текущий пользователь), `WITHDRAW`, `OBJECT`, `NEW_APPLICATION`.

## Пункты дозапроса (`info_request.items[].item_code`)
| item_code | Источник | Вопрос клиенту | Ответ |
| --- | --- | --- | --- |
| `REVENUE_CONFIRM` | правило `VAL_REVENUE_MISMATCH` | «Выручка в заявке заметно отличается от поступлений на ваш счёт в банке. Подтвердите выручку и поясните разницу» | `value` (выручка, число) + `comment` (обязателен) |
| `PURPOSE_DETAILS` | правило `VAL_PURPOSE_UNCLEAR` | «Опишите, на что пойдут деньги» | `comment` |
| `UNDERWRITER_QUESTION` | андеррайтер | текст андеррайтера | `comment` |
Ответ на пункт **закрывает** правило: повторно на той же заявке оно не срабатывает (нет цикла).

## Причины маршрутизации к андеррайтеру (`decision.route_reason`)
`GRADE_C` (пограничная оценка), `AMOUNT_ABOVE_AUTO` (сумма выше порога авто-решения), `NO_AUTO_CONSENT` (ИП не дал согласия на авто-решение), `SOURCE_UNAVAILABLE` (источник недоступен), `OBJECTION` (возражение ИП), `INFO_RESPONSE` (ответ на вопрос андеррайтера).

## Решения андеррайтера (`outcome` в `/underwriting/{id}/decision`)
`APPROVE`, `COUNTER`, `DECLINE`, `REQUEST_INFO`, `RETRY_ENRICHMENT` (только при `SOURCE_UNAVAILABLE`). Эти же значения (+ `MANUAL` для авто-решения «к андеррайтеру») — в `decision.outcome`.

## Коды причин (`reason_catalog.code`)
| code | Тип | Клиентская категория | client_visible | БКИ (758-П, блок 57) |
| --- | --- | --- | --- | --- |
| `SF_INACTIVE` | стоп-фактор | Данные о компании | да | несоответствие данных |
| `SF_BANKRUPTCY` | стоп-фактор | Финансовое положение | да | банкротство |
| `SF_AGE` | стоп-фактор | Срок ведения бизнеса | да | кредитная политика |
| `SF_OVERDUE` | стоп-фактор | Кредитная история | да | кредитная история |
| `SF_TAX_DEBT` | стоп-фактор | Налоги и обязательства | да | кредитная политика |
| `SF_OKVED` | стоп-фактор | Условия продукта | да | кредитная политика |
| `SF_ADDITIONAL` | стоп-фактор (ПОД/ФТ, антифрод) | → клиенту **`ADDITIONAL_CHECKS`** | **нет** (внутренний) | предупреждение мошенничества |
| `ADDITIONAL_CHECKS` | клиентский код для `SF_ADDITIONAL` | Дополнительные проверки | да | — |
| `LOW_SCORE` | оценка D | Финансовые показатели | да | кредитная политика |
| `HIGH_LOAD` | политика | Долговая нагрузка | да | долговая нагрузка |
| `UNDERWRITER_DECLINE` | ручной отказ (+ комментарий внутрь) | Решение специалиста; категория выбирается андеррайтером из клиентских | да | по выбранной категории |
| `CLIENT_REJECTED_OFFER` | отзыв клиентом | — | да | — |
| `CLIENT_WITHDREW` | отзыв клиентом | — | да | — |
| `EXPIRED_INFO` / `EXPIRED_OFFER` | истечение | — | да | — |

## Типы событий журнала (`application_event.event_type`)
`STATE_CHANGED`, `SIGNATURE_REQUESTED`, `CONSENT_SIGNED`, `CHECK_REQUESTED`, `CHECK_RECEIVED`, `CHECK_FAILED`, `DECISION_MADE`, `OFFER_ISSUED`, `OFFER_ACCEPTED`, `SIGNED`, `DISBURSED`, `BKI_REPORT`, `OBJECTION_FILED`, `UNDERWRITER_OVERRIDE` (решение расходится с рекомендацией).

## Данные персонажей
`contracts/personas.json` — единственный источник: из него генерируются сиды БД и фикстуры моков. Генерируется `contracts/decision_reference.py --write`; руками не править. `demo.expected` — golden-тесты: `{state, outcome, offer?, reason_code?, client_reason_code?, grade, score, points}`, для дозапроса — `{first_state, validation_rule, after_info}`, для ручного рассмотрения — `{state: MANUAL_REVIEW, route_reason, recommendation}`. `demo.consents` и `demo.info_response` — что вводит тест (и жюри по README).
