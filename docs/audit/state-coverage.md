# A-07b — доказательства переходов автомата состояний

Дата: 25.10.2026, Москва (UTC+3). База после rebase:
`42f78f34da4bfd18092815f551e373007ae60d78`.
Стенд: `harkachi_alpha26`, `http://localhost:8080`.

**На стенде 25 из 31, модульными тестами 6, не покрыто 0.**

## Что проверено

Новый `tests/e2e/api/test_transitions.py` создаёт отдельную заявку в каждом
из 10 сценариев через API и проверяет состояние клиента и ровно одно
событие нужной пары в банковской карточке этой заявки:

| Проверка | Тест |
| --- | --- |
| Ручной отказ: категория видна клиенту, внутренний комментарий скрыт | `test_manual_decline_category_without_comment` |
| Дозапрос банка и ответ клиента, текущая причина `INFO_RESPONSE` в очереди | `test_manual_info_response_route` |
| Истечение системного дозапроса через 6 дней, `EXPIRED_INFO` | `test_expiry[ooo_gap-INFO_REQUESTED-6-EXPIRED_INFO]` |
| Истечение оферты через 31 день, `EXPIRED_OFFER` | `test_expiry[ip_good-OFFER_ISSUED-31-EXPIRED_OFFER]` |
| Истечение на подписании через 31 день, `EXPIRED_OFFER` | `test_expiry[ip_good-SIGNING-31-EXPIRED_OFFER]` |
| Отзыв из дозапроса, ручного рассмотрения, оферты и подписания | четыре параметра `test_withdraw` |
| Отказ от оферты отдельной командой | `test_decline_offer` |

Расхождение с формулировкой карточки: контракт `contracts/api.md` называет
команду отказа `/applications/{id}/offer/reject`, без тела запроса;
`offer/decline` в контракте отсутствует. Метод клиента `decline_offer`
сохраняет сигнатуру из карточки, но не отправляет `offer_version`,
поскольку контракт его здесь не принимает.

## Воспроизведение и приёмка

Из корня репозитория, PowerShell:

```powershell
$env:Path = "C:\Program Files\Docker\Docker\resources\bin;$env:Path"
$env:COMPOSE_PROJECT_NAME = "harkachi_alpha26"
# Выполнить дважды подряд:
uv run --no-project --python 3.12 --with pytest --with httpx --with jsonschema python -X utf8 -m pytest -q -rA tests/e2e/api/test_transitions.py
# Весь API-набор, включая штатный тест перезапуска worker:
uv run --no-project --python 3.12 --with pytest --with httpx --with jsonschema python -X utf8 -m pytest -q -rA tests/e2e/api
uv run --no-project python tests/e2e/state_coverage.py --self-test
uv run --no-project --with ruff ruff check tests/e2e
uv run --no-project --with ruff ruff format --check tests/e2e
uv run --no-project python tests/e2e/state_coverage.py
```

Два последовательных прогона после последнего rebase:
`10 passed in 155.87s (0:02:35)`; `10 passed in 103.89s (0:01:43)`.
API-набор после rebase: `268 passed in 432.42s (0:07:12)`; failed = 0, skipped = 0, xfail = 0.
Самопроверка скрипта: `Ran 5 tests`, `OK`.
Ruff: `All checks passed!`; форматирование: `13 files already formatted`.
`git diff --check`: пусто. Изменены только четыре разрешённых файла.

Полный набор выполнен без исключений. Оператор уточнил, что штатный
`test_worker_restart_keeps_application` разрешён; прежний вопрос о его
запуске закрыт, уточнение отправлено тимлиду через `QUESTION A-07b`.
Существующие тесты и их требования не менялись.

## Метод подсчёта

- Скрипт читает таблицу модели; 14 состояний берёт из концов стрелок диаграммы.
  Альтернативы раскрываются, дубликаты пар объединяются.
- `DECLINED` исключается из `* до SIGNED` по явному условию строки модели:
  после отказа доступно возражение. Получается 31 пара.
- Стендовое доказательство — событие с допустимым `actor_type`.
  Событие с неверным исполнителем не засчитывается и показывается как лишнее.
- Колонка «Модульный тест» берётся из словаря `MODULE_TESTS` в начале скрипта.
  Модульные доказательства считаются только для пар без стендового события:
  один переход не считается дважды.
- Журнал общий и накопительный: количества ниже включают прошлые прогоны.
  Новые тесты дополнительно проверяют события собственных заявок через API.
- Источник снимка — единственный `SELECT ... GROUP BY` в `BEGIN READ ONLY`;
  прямых записей в БД, очистки данных и сбоев моков не было. Штатный тест
  A-03 перезапускает worker для проверки восстановления; ради достижения
  промежуточных состояний worker не останавливался.
- Статическая проверка тупиков означает наличие исходящей пары у каждого
  нефинального состояния; она не доказывает достижимость всех условий.

## Проверка модульных доказательств

Существующие тесты прочитаны; ниже указано, почему они выполняют именно
нужную пару. В A-07b они не запускались: доказательство здесь — проверенный
код существующего теста, а не заявление о новом прогоне модульного набора.

| Пары | Доказательство выполнения |
| --- | --- |
| `SUBMITTED` / `VALIDATION` / `ENRICHMENT` / `ASSESSMENT` → `WITHDRAWN` | `backend/tests/offers/test_actions.py::test_withdraw_before_signing[STATE]`: параметр задаёт начальную стадию в изолированной фикстуре; затем настоящий HTTP `withdraw`, проверки `200`, `WITHDRAWN`, увеличения версии и `CLIENT_WITHDREW`; после `drain` состояние остаётся `WITHDRAWN`. Это проверка действия из подготовленной стадии, не сквозной путь получения стадии. |
| `ENRICHMENT` → `MANUAL_REVIEW` | `backend/tests/pipeline/test_pipeline.py::test_bureau_retry_and_other_sources_still_run[3]`: реальная подача и `drain`, три отказа BKI через тестового провайдера, остальные источники работают; проверены `MANUAL_REVIEW`, событие `STATE_CHANGED` и `SOURCE_UNAVAILABLE`, завершение заданий. Разрешённая пара автомата подтверждает исходную стадию этого системного перехода. |
| `MANUAL_REVIEW` → `ENRICHMENT` | `backend/tests/underwriting/test_underwriting.py::test_retry_only_unavailable`: заявка с недоступным реестром, настоящее ручное решение `RETRY_ENRICHMENT`, проверка `200` и `ENRICHMENT`; затем рабочие провайдеры и `drain` до `OFFER_ISSUED`. Для обычной ручной заявки повтор запрещён (`409`). |

Для истечений дополнительно сверены существующие
`backend/tests/expiry/test_service.py::test_due_application_expires_once`
(три параметра), `test_info_time_shift`, `test_time_shift_accumulates_and_shifts_all_deadlines`:
они проверяют реальные действия сервиса и API, события `SYSTEM` и причины
`EXPIRED_INFO` / `EXPIRED_OFFER`. На стенде эти пары уже доказаны новыми e2e.

## Снимок покрытия

Дата UTC: 2026-10-25T18:03:33.121757+00:00
Проект Compose: harkachi_alpha26

| Из | В | Кто по модели | Кто в журнале | Событий | Покрытие | Модульный тест |
| --- | --- | --- | --- | ---: | --- | --- |
| ASSESSMENT | DECLINED | система | SYSTEM: 44 | 44 | стенд | — |
| ASSESSMENT | MANUAL_REVIEW | система | SYSTEM: 63 | 63 | стенд | — |
| ASSESSMENT | OFFER_ISSUED | система | SYSTEM: 147 | 147 | стенд | — |
| ASSESSMENT | WITHDRAWN | клиент | — | 0 | модульный | backend/tests/offers/test_actions.py::test_withdraw_before_signing[ASSESSMENT] |
| DECLINED | MANUAL_REVIEW | клиент-ИП | CLIENT: 16 | 16 | стенд | — |
| DRAFT | SUBMITTED | подписант | CLIENT: 274 | 274 | стенд | — |
| DRAFT | WITHDRAWN | клиент | CLIENT: 47 | 47 | стенд | — |
| ENRICHMENT | ASSESSMENT | система | SYSTEM: 254 | 254 | стенд | — |
| ENRICHMENT | MANUAL_REVIEW | система | — | 0 | модульный | backend/tests/pipeline/test_pipeline.py::test_bureau_retry_and_other_sources_still_run[3] |
| ENRICHMENT | WITHDRAWN | клиент | — | 0 | модульный | backend/tests/offers/test_actions.py::test_withdraw_before_signing[ENRICHMENT] |
| INFO_REQUESTED | EXPIRED | система | SYSTEM: 9 | 9 | стенд | — |
| INFO_REQUESTED | MANUAL_REVIEW | клиент | CLIENT: 11 | 11 | стенд | — |
| INFO_REQUESTED | VALIDATION | клиент | CLIENT: 14 | 14 | стенд | — |
| INFO_REQUESTED | WITHDRAWN | клиент | CLIENT: 9 | 9 | стенд | — |
| MANUAL_REVIEW | DECLINED | андеррайтер | UNDERWRITER: 10 | 10 | стенд | — |
| MANUAL_REVIEW | ENRICHMENT | андеррайтер | — | 0 | модульный | backend/tests/underwriting/test_underwriting.py::test_retry_only_unavailable |
| MANUAL_REVIEW | INFO_REQUESTED | андеррайтер | UNDERWRITER: 11 | 11 | стенд | — |
| MANUAL_REVIEW | OFFER_ISSUED | андеррайтер | UNDERWRITER: 39 | 39 | стенд | — |
| MANUAL_REVIEW | WITHDRAWN | клиент | CLIENT: 9 | 9 | стенд | — |
| OFFER_ISSUED | EXPIRED | система | SYSTEM: 9 | 9 | стенд | — |
| OFFER_ISSUED | SIGNING | подписант | CLIENT: 73 | 73 | стенд | — |
| OFFER_ISSUED | WITHDRAWN | клиент | CLIENT: 18 | 18 | стенд | — |
| SIGNED | DISBURSED | система | SYSTEM: 32 | 32 | стенд | — |
| SIGNING | EXPIRED | система | SYSTEM: 9 | 9 | стенд | — |
| SIGNING | SIGNED | подписант (+ поручитель) | CLIENT: 32 | 32 | стенд | — |
| SIGNING | WITHDRAWN | клиент | CLIENT: 9 | 9 | стенд | — |
| SUBMITTED | VALIDATION | система | SYSTEM: 274 | 274 | стенд | — |
| SUBMITTED | WITHDRAWN | клиент | — | 0 | модульный | backend/tests/offers/test_actions.py::test_withdraw_before_signing[SUBMITTED] |
| VALIDATION | ENRICHMENT | система | SYSTEM: 254 | 254 | стенд | — |
| VALIDATION | INFO_REQUESTED | система | SYSTEM: 34 | 34 | стенд | — |
| VALIDATION | WITHDRAWN | клиент | — | 0 | модульный | backend/tests/offers/test_actions.py::test_withdraw_before_signing[VALIDATION] |

**покрыто 25 из 31**
**на стенде 25 из 31, модульными тестами 6, не покрыто 0**

### Лишние переходы

Нет.

### Тупики

Нет: у каждого нефинального состояния есть выход.

Событий без смены состояния или с пустой границей: 3360; они исключены из покрытия и лишних переходов.

Время: 0.39 с

## Самопроверка и вопросы тимлиду

Встроенное ревью `codex review --base origin/main` нашло отсутствие проверки
готовности стенда в новом модуле (P2). Исправлено: модульная autouse-фикстура
использует существующий `conftest.require_ready`, как другие сценарии A-03.
`TODO(lead)` у фикстуры объясняет пропуск только при недоступном стенде:
на намеренно недоступном `http://127.0.0.1:1/api/v1` получено `10 skipped`,
а приёмочные прогоны выполняются на настоящем стенде без пропусков.
Самопроверки скрипта воспроизводят обе добавленные функции: до реализации
падали на включённой паре `DECLINED → WITHDRAWN` и отсутствующем модульном
доказательстве, после реализации проходят. Первые e2e до добавления методов
клиента падали из-за их отсутствия; также исправлена ошибка нового теста:
`INFO_RESPONSE` проверяется в текущей очереди, а не в историческом решении.
Приложение не менялось.
Повторное встроенное ревью после исправления P2: actionable-дефектов
в пределах A-07b не найдено; ссылки на модульные тесты подтверждены.
Ревью выполняло статическую проверку, API-тесты и Docker запускал основной агент.
Новые зависимости: нет.

Открытых вопросов по переходам нет. Вопрос A-07 об отзыве из
`DECLINED` закрыт уточнением модели: пара не входит в 31 переход.
