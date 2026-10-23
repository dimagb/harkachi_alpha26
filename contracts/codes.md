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

### Витрина продуктов (`GET /products`, поля вне `product.params`)
| code | name | description | purposes | requires_guarantor_ooo |
| --- | --- | --- | --- | --- |
| `EXPRESS` | Экспресс-кредит | На любые цели бизнеса | `WORKING_CAPITAL`, `CASH_GAP`, `EQUIPMENT`, `OTHER` | да |
| `WORKING_CAPITAL` | Оборотный кредит | На пополнение оборотных средств | `WORKING_CAPITAL`, `CASH_GAP` | да |
| `OVERDRAFT` | Овердрафт | На покрытие кассовых разрывов | `CASH_GAP`, `WORKING_CAPITAL` | да |

`name` и `description` берутся из таблицы `product` (сиды B-03, совпадают с этой таблицей). `rate_from` = `decision_config.key_rate` активной версии + `params.spread.A` продукта; `min_amount`/`max_amount`/`min_term_months`/`max_term_months` = `params.min`/`max`/`tmin`/`tmax`. Порядок выдачи — как в этой таблице. Цель заявки вне `purposes` продукта — 422 (проверяет B-05).

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

## Клиентские тексты причин (`reason_catalog.client_text`, `client_action`)
Источник для сидов `reason_catalog`. `{date}` и `retry_after` подставляет бэкенд. `client_visible = нет` только у `SF_ADDITIONAL`.

| code | client_text | client_action |
| --- | --- | --- |
| `SF_INACTIVE` | По данным реестра компания не действует | Проверьте сведения о компании в ЕГРЮЛ/ЕГРИП |
| `SF_BANKRUPTCY` | Есть сведения о процедуре банкротства | — |
| `SF_AGE` | Бизнесу меньше 6 месяцев | Подайте заявку после {date} |
| `SF_OVERDUE` | Есть просроченная задолженность по кредитам | Погасите просрочку и подайте заявку повторно через 30 дней |
| `SF_TAX_DEBT` | Есть задолженность перед бюджетом или по исполнительным листам | Погасите задолженность и подайте заявку снова |
| `SF_OKVED` | Вид деятельности не подходит для этого продукта | — |
| `SF_ADDITIONAL` | (клиенту не показывается — используется `ADDITIONAL_CHECKS`) | — |
| `ADDITIONAL_CHECKS` | Заявка не прошла дополнительные проверки банка | — |
| `LOW_SCORE` | Финансовые показатели бизнеса пока не позволяют одобрить заявку | Попробуйте меньшую сумму или овердрафт |
| `HIGH_LOAD` | Ежемесячный платёж был бы слишком большим для текущих оборотов | Рассмотрите овердрафт или подайте заявку позже |
| `UNDERWRITER_DECLINE` | Заявку рассмотрел специалист банка и не смог её одобрить | — |
| `CLIENT_REJECTED_OFFER` | Вы отказались от предложения банка | Можно подать новую заявку |
| `CLIENT_WITHDREW` | Вы отозвали заявку | Можно подать новую заявку |
| `EXPIRED_INFO` | Срок ответа на запрос банка истёк | Подайте новую заявку |
| `EXPIRED_OFFER` | Срок действия предложения истёк | Подайте новую заявку |

`client_action = —` хранится как NULL. `client_category` и код БКИ — из таблицы «Коды причин» выше (для `UNDERWRITER_DECLINE` категорию выбирает андеррайтер, в каталоге NULL).

## Служебные перечисления (только БД и worker, в API не выходят)
| Поле | Значения |
| --- | --- |
| `job.step` | `VALIDATION`, `ENRICHMENT`, `ASSESSMENT`, `DISBURSEMENT`, `EXPIRY_CHECK`, `BACKGROUND_LOAD` |
| `job.status` | `PENDING`, `RUNNING`, `DONE`, `FAILED` |
| `external_check.source` / `status` | `BKI`, `EGRUL`, `FNS` / `PENDING`, `OK`, `FAILED` (= `CheckSource` / `CheckStatus` в `api-types.ts`) |
| `application_event.actor_type` | `CLIENT`, `UNDERWRITER`, `GUARANTOR`, `SYSTEM` |
| `objection.outcome` | `UPHELD` (решение пересмотрено), `REJECTED` (оставлено в силе); NULL, пока не рассмотрено. В API: `status` = `RESOLVED`, если `resolved_at` не NULL, иначе `PENDING` |
| `decision.kind` | `AUTO`, `MANUAL` |
| `consent.type` | `PDN`, `BKI`, `AUTO_DECISION` |
| `info_request.source` | `SYSTEM`, `UNDERWRITER` |
| `party.role` / `status` | `BORROWER_SIGNATORY`, `GUARANTOR` / `PENDING`, `SIGNED` |
| `signature.object_type` | `CONSENT`, `OFFER`, `GUARANTEE` |
| `offer.kind` / `status` | `APPROVED`, `COUNTER` / `ACTIVE`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `SUPERSEDED` |
| `company.kind`, `user.role` | `IP`, `OOO`; `CLIENT`, `UNDERWRITER`, `GUARANTOR` |

## `decision_config.params` (версия 1)
JSON с параметрами эталона `contracts/decision_reference.py` — один к одному: `products` (= `PRODUCTS`: `min`, `max`, `tmin`, `tmax`, `k`, `auto`, `spread`), `industry` (= `INDUSTRY`), `okved_stop` (= `OKVED_STOP`), `stop` (`max_dpd_12m`: 60, `tax_debt`: 50000, `enforcement_sum`: 100000, `min_age_months`: 6), `validation` (`revenue_mismatch`: 0.40), `grades` (`A`: 75, `B`: 60, `C`: 45), `policy` (`free_payment_share`: 0.30, `counter_round`: 50000, `overdraft_payment_share`: 0.10). `key_rate` и `key_rate_date` — отдельные столбцы. После слияния B-02 тест сверяет эти значения с `DEFAULT_CONFIG`.

## Данные персонажей
`contracts/personas.json` — единственный источник: из него генерируются сиды БД и фикстуры моков. Генерируется `contracts/decision_reference.py --write`; руками не править. `demo.expected` — golden-тесты: `{state, outcome, offer?, reason_code?, client_reason_code?, grade, score, points}`, для дозапроса — `{first_state, validation_rule, after_info}`, для ручного рассмотрения — `{state: MANUAL_REVIEW, route_reason, recommendation}`. `demo.consents` и `demo.info_response` — что вводит тест (и жюри по README).
