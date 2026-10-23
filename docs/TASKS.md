# TASKS — задачи команды (этап 5)

Правила работы — `AGENTS.md`. Стартовый промпт для любой задачи — `docs/team/prompts/start.md`. Статус задачи виден по PR: открыт, слит, черновик. Таблицу ниже обновляет тимлид.

**Уровень детализации.** Карточки с пометкой **[готова]** можно брать сразу. Карточки **[черновик]** тимлид уточняет перед стартом: проверяет пути и дописывает приёмку по коду, который уже появился.

**Вехи:**
- **M0** — 23.10 вечер: каркас слит в `main`, CI зелёный.
- **M1** — 24.10 23:00, «ходячий скелет»: в Docker персонаж `ip_good` входит, создаёт и подаёт заявку, worker доводит её до `OFFER_ISSUED`, клиент видит оферту в API.
- **M2** — 25.10 20:00: все 6 персонажей проходят свои исходы через API и интерфейс; экраны банка работают.
- **M3** — 26.10 12:00, заморозка: репетиция T20 пройдена, README, чек-лист с доказательствами.

## Сводка

| ID | Задача | Кто (Codex) | Когда | Облако | Зависит от | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| T-00 | Каркас репозитория | Аня (ведёт человек) | 23.10 | нет | — | PR #1: ревью пройдено, CI зелёный |
| L-01 | AGENTS.md, TASKS.md, notify.py, стартовые промпты | тимлид | 23.10 | — | — | идёт |
| L-03 | После M0: CODEOWNERS, Postgres в CI, `.gitignore` для `.notify.env`, команда сидов в compose | тимлид | 23.10 вечер | — | T-00 | — |
| A-02 | Генератор фоновых данных | Катя | 23.10 сейчас | **да** | — | [готова] |
| A-04 | Сценарии проверки (T12) | Катя | 23.10 сейчас | **да** | — | [готова] |
| B-01 | Схемы API и заглушки → полный `openapi.json` | Лана | 23.10 после M0 | **да** | T-00 | [готова] |
| B-02 | Движок решения `decide()` | Лана | 23.10 после M0 | **да** | T-00 | [готова] |
| A-01 | Мок-сервис внешних источников | Катя | 23.10 после M0 | **да** | T-00 | [готова] |
| B-03 | Модели БД, миграция, сиды | Аня (ведёт человек) | 23.10 ночь — 24.10 | нет | T-00 | [готова] |
| F-01 | Оболочка фронтенда: вход, маршруты, роли, клиент API, MSW | Лана | 24.10 8:00 | нет | B-01 | [готова] |
| B-04 | Вход, `/me`, продукты, калькулятор, профиль | Аня | 24.10 с утра | нет | B-01, B-03 | [черновик] |
| B-05 | Заявка: создание и правка, автомат состояний, журнал, лента | Аня | 24.10 15:00 | нет | B-04 | [черновик] |
| B-06 | OTP, согласия, подача, просьба подписать | Аня | 24.10 вечер | нет | B-05 | [черновик] |
| B-07 | Worker: конвейер до решения, дозапрос | Аня | 24.10 вечер | нет | B-02, B-05, A-01 | [черновик] |
| A-03 | Golden-тесты через API | Катя | 24.10 15:00 | нет | B-01 | [черновик] |
| F-02 | Тема из токенов дизайна | Лана | 24.10 11:00 | да | F-01, токены | [черновик] |
| F-03 | Главная клиента, калькулятор, форма заявки | Лана | 24.10 | да | F-01 | [черновик] |
| F-04 | Карточка заявки с лентой (ключевой экран 1) | Лана | 24.10 вечер | да | F-03, макет | [черновик] |
| A-05 | Коллекция HTTP-запросов (T9) | Катя | 24.10 вечер | да | B-01 | [черновик] |
| B-08 | Андеррайтер: очередь, карточка банка, решение | Аня | 25.10 | нет | B-07 | [черновик] |
| B-09 | Оферта, подпись, выдача, отзыв, возражение | Аня | 25.10 | нет | B-07 | [черновик] |
| B-10 | Истечения, `time-shift`, журнал банка, фоновые заявки | Аня | 25.10 | нет | B-09, A-02 | [черновик] |
| F-05 | Решение: оферта, встречное, отказ, дозапрос (ключевой экран 2) | Лана | 25.10 | да | F-04 | [черновик] |
| F-06 | Подача с согласиями и OTP, подписание, участники | Лана | 25.10 | да | F-04 | [черновик] |
| F-07 | Экраны андеррайтера (ключевой экран 3) | Лана | 25.10 | да | F-01, макет | [черновик] |
| F-08 | Журнал банка, демо-управление временем, печать протокола | Лана | 25.10 вечер | да | F-07 | [черновик] |
| F-09 | Playwright: демо-путь целиком | Лана или человек | 25.10 вечер | нет | M2 | [черновик] |
| A-06 | Репетиция T20 на чистом ПК | Катя | 26.10 9:00 | — | M2 | [черновик] |
| L-02 | README для жюри, THIRD_PARTY_NOTICES, чек-лист | тимлид + человек | 25–26.10 | — | M2 | — |

Катя 25.10 отсутствует: её задачи с пометкой «Облако: да» можно запустить в Codex Cloud перед уходом (`docs/team/env-setup.md` §6).

---

## Карточки [готова]

### A-02 — Генератор фоновых данных · Катя · Облако: да · ≤3 ч
**Зачем.** Журнал банка и очередь андеррайтера должны выглядеть живыми: около 40 компаний и 60 заявок. Те же данные проверяют модель решения на разнообразных входах (T5).
**Файлы (только эти):** `data/generate_background.py`, `data/background.json`, `data/test_generate_background.py`, `data/README.md`.
**Читать:**
- `docs/data-model.md`, раздел «Синтетические данные»;
- `contracts/personas.json` — первые 60 строк, чтобы увидеть формат одной компании;
- `contracts/decision_reference.py` — функции `inn10`, `inn12`, `turn`, `bki`, `fns`, `company`.

**Сделать:**
1. Скрипт только на стандартной библиотеке Python, запуск `uv run --no-project python -X utf8 data/generate_background.py` из корня. Генератор случайных чисел — `random.Random(20261023)`, никаких других источников случайности (время, `os.urandom`).
2. Пишет `data/background.json`: `{"_meta": {...}, "companies": [...]}` строго так: `path.write_bytes((json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8"))`. Это даёт LF и стабильный порядок ключей. **Ровно 40 компаний.** Верхний уровень каждой компании имеет **тот же набор ключей, что персонаж** в `personas.json`: `code` (`bg_001` … `bg_040`), `kind`, `inn`, `ogrn`, `name`, `okved_main`, `reg_date`, `status`, `address`, `director`, `founders`, `turnover` (12 целых чисел), `bki` (`loans` + `summary`), `fns`, `risk`, `users`, `demo`. Поле `demo.expected` **не заполнять**: исход считает движок.
3. Распределения строго по `data-model.md`:
   - 60% ООО / 40% ИП;
   - ИНН с верной контрольной суммой (функции `inn10`/`inn12` перенести копией), уникальные и не совпадающие с персонажами;
   - ОКВЭД — из ключей `INDUSTRY` эталона плюс 2 компании со стоп-ОКВЭД (`92.xx`, `64.9x`);
   - дата регистрации 3–120 месяцев до 2026-10-23, лог-нормальное распределение, медиана около 30;
   - обороты: среднее 0,3–8 млн в месяц (лог-нормальное) × сезонность ±15% × шум с CV 0,1–0,7;
   - БКИ: у 60% есть кредиты (платёж 5–35% оборота); просрочка 1–30 дней у 10%, 31–90 у 5%, текущая у 3%;
   - ФНС: налоговый долг у 8% (у трети выше 50 000), исполнительные производства у 5%, банкротство у 1% (не меньше одной компании); ПОД/ФТ у 2% (не меньше одной).
4. Вместо `demo.app` у фоновой компании — `demo.apps`: список из 1–2 элементов `{app, consents, target_state}`, всего **ровно 60** заявок. `app` и `consents` — в том же формате, что у персонажей. `target_state` — состояние, до которого B-10 доведёт заявку через **тот же конвейер**, поэтому оно обязано быть достижимым. Сначала вызови `decide()` эталона на `(компания, app, consents)` и получи `state`. Затем выбери `target_state` по таблице:

   | `state` от эталона | допустимые `target_state` |
   | --- | --- |
   | любой | `DRAFT`, `SUBMITTED`, `WITHDRAWN` |
   | `OFFER_ISSUED` | `OFFER_ISSUED`, `SIGNED`, `DISBURSED`, `EXPIRED` |
   | `DECLINED` | `DECLINED` |
   | `MANUAL_REVIEW` | `MANUAL_REVIEW` |
   | `INFO_REQUESTED` | `INFO_REQUESTED` |

   Каждое из 10 значений встречается не реже 3 раз. Генератор подбирает входы так, чтобы это выполнялось: детерминированно, с тем же `Random`. Суммы и сроки — внутри границ продукта из `PRODUCTS` эталона. У пользователя `users[0]` поле `login` равно `code`.
5. `data/README.md`: как запустить, что внутри, правила распределений (5–10 строк).

**Приёмка:**
- Тест детерминизма: генератор дважды пишет файл во временную папку (функция `generate(path)`), `sha256` обоих равны и равны `sha256` закоммиченного `data/background.json`.
- `uv run --no-project --with pytest pytest -q data/` — тесты зелёные и проверяют:
  - 40 компаний и 60 заявок;
  - контрольные суммы всех ИНН;
  - уникальность ИНН и отсутствие пересечения с `personas.json`;
  - доли ООО/ИП ±10 п.п.;
  - каждое `target_state` встречается не реже 3 раз;
  - суммы и сроки в границах продукта;
  - есть хотя бы одна компания с банкротством, одна с ПОД/ФТ и одна со стоп-ОКВЭД;
  - набор ключей **верхнего уровня** каждой компании равен набору ключей персонажа;
  - для каждой заявки `target_state` допустим по таблице из п. 4: тест сам вызывает `decide()` эталона через `importlib` по пути `contracts/decision_reference.py`;
  - все 10 значений `target_state` встречаются не реже 3 раз.
- Размер `background.json` меньше 1 МБ.

**Не делать:** не трогать `contracts/`, не добавлять зависимости, не писать в БД.

### A-04 — Сценарии проверки (T12) · Катя · Облако: да · ≤2 ч
**Зачем.** Жюри требует документ с тестовыми сценариями (T12). Тот же документ — это план автотестов и сценарий демо.
**Файлы:** `docs/test-scenarios.md`.
**Читать:**
- `docs/requirements-checklist.md`, блок F;
- `docs/state-machine.md`, таблица переходов;
- `contracts/personas.json`: поле `demo` у каждого персонажа;
- `contracts/codes.md`.

**Сделать:**
1. Таблица сценариев: `ID` (`S-01`…), требование (`F…`), персонаж и учётка, шаги (что нажать или вызвать), ожидаемый результат (состояние, что видит клиент, что видит банк), где автоматизировано (`B-02 golden`, `A-03`, `F-09` или «вручную»).
2. Обязательно:
   - все 6 персонажей, в том числе `ooo_gap` с дозапросом, `ooo_load` со встречным и бухгалтером без права подписи, `ooo_border` с ручным одобрением андеррайтером, `ooo_aml` (клиент видит только `ADDITIONAL_CHECKS`);
   - негативные сценарии: недопустимый переход → 409 `INVALID_TRANSITION`, чужая заявка → 404, неверный OTP → 422, подпись без права → 403, сбой источника (`MOCK_FAILURE_INN`) → повторы и `SOURCE_UNAVAILABLE`, истечение оферты через `time-shift`;
   - возражение ИП после авто-отказа (`ip_bad`).
3. Ожидаемые числа (оценка, ставка, сумма, платёж) брать **только** из `demo.expected` в `personas.json`, не пересчитывать.

Для сценария сбоя источника — отдельный запуск стенда с `MOCK_FAILURE_INN=770112345695` (ИНН `ip_good`): заявка `ip_good` уходит в `MANUAL_REVIEW` с `SOURCE_UNAVAILABLE`.

**Приёмка:**
- каждый F-пункт из блока F чек-листа упомянут хотя бы в одном сценарии, либо явно помечен «не относится» с причиной;
- каждая сумма в ₽, ставка в %, балл, оценка и платёж в документе совпадают с `demo.expected` в `personas.json`;
- есть обязательные сценарии:
  - `S-01`…`S-06` — по одному на персонажа;
  - `S-07` — бухгалтер без права подписи просит подписанта;
  - `S-08` — встречное `ooo_load` принято и подписано;
  - `S-09` — андеррайтер одобряет `ooo_border`;
  - `S-10` — возражение `ip_bad`;
  - `S-11` — 409 `INVALID_TRANSITION`;
  - `S-12` — 404 на чужую заявку;
  - `S-13` — неверный OTP → 422;
  - `S-14` — подпись без права → 403;
  - `S-15` — сбой источника;
  - `S-16` — истечение оферты через `time-shift`;
  - `S-17` — клиент `ooo_aml` не видит внутренней причины;
  - `S-18` — выдача и график платежей `ip_good`.

**Не делать:** не придумывать новых кодов и состояний.

### B-01 — Схемы API и заглушки, полный `openapi.json` · Лана · Облако: да · ≤3 ч
**Зачем.** Фронтенд и тесты аналитики работают по реальному OpenAPI с первого дня. Расхождение с контрактом ловит компилятор, а не жюри.
**Файлы:**
- `backend/app/schemas/*.py` (новые);
- `backend/app/api/*.py` (новые роутеры);
- `backend/app/main.py` — только подключение роутеров и `separate_input_output_schemas=False`;
- `backend/app/errors.py` — добавить `NOT_IMPLEMENTED` в `ErrorCode` и класс исключения, если его нет; перевести на русский `message` («Проверьте заполнение полей», «Внутренняя ошибка сервера» и т. п.) и тексты `details.fields` для частых типов ошибок Pydantic (`missing`, `string_too_short`, `string_too_long`, `greater_than`, `less_than_equal`, `literal_error`, `extra_forbidden`, `uuid_parsing`, `int_parsing`): их видит пользователь;
- `backend/tests/fixtures_bodies.py` (новый);
- `backend/tests/test_contract_paths.py`, `backend/tests/test_schemas_validation.py`;
- `contracts/openapi.json` (генерируется);
- `frontend/src/api/schema.d.ts` (генерируется);
- `frontend/contract-parity/parity.ts` (новый, **вне `src/`**);
- `frontend/tsconfig.parity.json` (новый, включает только `contract-parity/` и `../contracts/api-types.ts`) и скрипты в `frontend/package.json`: `typecheck` = `tsc --noEmit -p tsconfig.json && tsc --noEmit -p tsconfig.parity.json`; `build` = `tsc --noEmit -p tsconfig.json && vite build` (**сейчас `build` вызывает `typecheck` — это нужно разорвать**, иначе Docker-сборка упадёт: в её контексте нет `contracts/`).

**Читать:** `contracts/api-types.ts` целиком, `contracts/api.md` целиком, `AGENTS.md` §5.

**Сделать:**
1. Для **каждого** типа из `api-types.ts` — класс Pydantic с тем же именем и полями. У всех схем `ConfigDict(extra="forbid")`. Соответствие типов:

   | В `api-types.ts` | В Pydantic |
   | --- | --- |
   | объединение строк | `Literal[...]` |
   | `number` для денег и счётчиков | `int` |
   | `number` для ставок | `float` |
   | `x: T \| null` | обязательное `x: T \| None` без значения по умолчанию |
   | `x?: T` в запросах | `x: T \| None = None` |
   | `index: 1\|…\|6` | `Literal[1,2,3,4,5,6]` |
   | `pdn: true` | `Literal[True]` |
   | `Page<T>` | обобщённый класс `Page[T]`; имя схемы в OpenAPI — то, что выдаст Pydantic (обычно `Page_BankListItem_`), его же используй в проверке |

2. Ограничения из комментариев `api-types.ts` — через `Field`, у каждого ограничения тест на 422 с `VALIDATION_ERROR` и `details.fields`:
   - `purpose_text` 10–500 символов, обязателен при `purpose = "OTHER"` (валидатор модели);
   - `comment` в ответе на дозапрос 3–1000;
   - текст возражения 10–2000;
   - `info_questions` 1–5 штук;
   - `comment` андеррайтера 5–2000;
   - `days` 1–400;
   - `size` ≤ 100;
   - `declared_revenue_year` > 0;
   - `amount` и `term_months` > 0. Границы продукта здесь не проверяются: это бизнес-правило из B-05.
3. Роутеры: **каждая** строка таблицы `api.md` превращается в эндпоинт с тем же методом и путём под `/api/v1`, с моделью запроса и ответа (`response_model`), тегом по разделу и `summary` на русском. Тело обработчика возвращает 501 с `{"error":{"code":"NOT_IMPLEMENTED","message":"Эндпоинт ещё не реализован","details":{}}}` через механизм ошибок каркаса (`app/errors.py`; если там нет подходящего исключения — добавь класс `ApiErrorException(status, code, message, details)`). У каждого эндпоинта в `responses` объявлены коды ошибок с моделью `ApiError` по правилу:
   - 401 — всем, кроме `/auth/login`;
   - 403 — где в столбце «Роль» есть ограничение;
   - 404 — где в пути есть `{id}`;
   - 409 — где в столбце «Переход» есть переход;
   - 422 — где есть тело или query-параметры;
   - 501 — всем заглушкам. `/health` и `/ready` уже есть в каркасе, их не трогать. Безопасность: `HTTPBearer(auto_error=False)` как зависимость на всех путях, кроме `/auth/login`, `/health`, `/ready`, — чтобы в OpenAPI был `bearerAuth`. Проверку токена делает B-04.
4. `PATCH /applications/{id}` принимает заголовок `If-Match` (параметр `Header`), он виден в OpenAPI.
5. Сгенерировать `contracts/openapi.json` и `schema.d.ts` (команды — в `AGENTS.md` §2).
6. `contract-parity/parity.ts` — проверка совпадения типов на уровне компилятора:
   ```ts
   import type * as C from "../../../contracts/api-types";
   import type { components } from "./schema";
   type S = components["schemas"];
   type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
   type Accepts<Server, Contract> = [Contract] extends [Server] ? true : false;
   // ответы: строго взаимно (сервер отдаёт ровно контракт)
   const _ApplicationClient: Same<S["ApplicationClient"], C.ApplicationClient> = true;
   // запросы: сервер принимает всё, что разрешает контракт
   const _ApplicationCreate: Accepts<S["ApplicationCreate"], C.ApplicationCreate> = true;
   type RequiredKeys<T> = { [K in keyof T]-?: {} extends Pick<T, K> ? never : K }[keyof T];
   // запросы дополнительно: те же ключи и те же обязательные ключи (без лишних необязательных полей)
   const _ApplicationCreateKeys: Same<keyof S["ApplicationCreate"], keyof C.ApplicationCreate> = true;
   const _ApplicationCreateReq: Same<RequiredKeys<S["ApplicationCreate"]>, RequiredKeys<C.ApplicationCreate>> = true;
   ```
   Строки `Same` нужны для **всех** типов ответов: `LoginResponse`, `MeResponse`, `Product`, `CalculatorResponse`, `CompanyProfile`, `ApplicationClient`, `ApplicationListItem`, `OtpResponse`, `QueueItem`, `ApplicationBank`, `Page<BankListItem>`, `TimeShiftResponse`, `ApiError`. Строки `Accepts`, `…Keys` и `…Req` — для **всех** типов запросов: `LoginRequest`, `CalculatorRequest`, `ApplicationCreate`, `ApplicationPatch`, `OtpRequest`, `SubmitRequest`, `InfoResponseRequest`, `AcceptOfferRequest`, `SignRequest`, `ObjectionRequest`, `UnderwriterDecisionRequest`, `TimeShiftRequest`. Если строка не компилируется, исправляй **схему Pydantic**, а не проверку.

**Приёмка:**
- `cd backend && uv run pytest -q -rA` — зелёный, 0 skipped. `test_contract_paths.py` разбирает таблицу `contracts/api.md`:
  - строка «`/health`, `/ready`» разбивается на два пути;
  - `?…` отрезается;
  - строка `/preview` (Б2, зарезервировано) исключается.

  Каждая пара «метод + путь» есть в `app.openapi()["paths"]` под `/api/v1`. Лишних путей нет, кроме `/health`, `/ready`, `/docs`, `/openapi.json`.
- `cd frontend && npm run typecheck` — зелёный, `contract-parity/parity.ts` включён в проверку. Проверка отрицательного случая: если временно удалить одно поле из схемы Pydantic `ApplicationClient`, `typecheck` падает. Это показать в PR, затем вернуть.
- `git diff --exit-code` после повторной генерации обоих файлов — пусто.
- Любой путь из `api.md`, кроме health и ready, отвечает 501 и `{"error":{"code":"NOT_IMPLEMENTED",...}}` (параметризованный тест). Тест отправляет **валидный** запрос: `{id}` — `uuid4`, обязательные query-параметры (`company_id`) — `uuid4`, тело — из `tests/fixtures_bodies.py`, где на каждый тип запроса один валидный пример. Делать поля необязательными, чтобы получить 501, запрещено.
- `docker compose build web` — зелёный: проверка паритета не попала в сборку.
- CI зелёный.

**Не делать:** никакой логики, БД, авторизации, кроме объявления схемы безопасности. Не трогать `backend/app/decision/` (там работает B-02).

### B-02 — Движок решения `decide()` · Лана · Облако: да · ≤3 ч
**Зачем.** Кредитное решение — ядро кейса. Движок — чистые функции, которые обязаны давать ровно те же исходы, что эталон, и выдавать протокол для андеррайтера (обоснованность, §7a).
**Файлы:** `backend/app/decision/*.py`, `backend/tests/decision/*.py`.
**Читать:**
- `docs/decision-model.md` §2–§7a;
- `contracts/decision_reference.py` целиком;
- `contracts/personas.json` — структура одного персонажа;
- `contracts/api-types.ts` — `FactorLine`, `RuleFired`, `PolicyCalc`, `DecisionBank`.

**Сделать:**
1. `models.py` — неизменяемые dataclass (`frozen=True`):
   - `CompanyFacts`: `kind`, `status`, `reg_date: date`, `okved_main`, `mass_director`, `mass_address`;
   - `BureauSummary` — поля `bki.summary`;
   - `TaxCheck`: `tax_debt`, `enforcement_sum`, `arbitration_defendant_sum`, `bankruptcy`;
   - `RiskFlags`: `aml_flag`, `fraud_flag`;
   - `AppParams`: `product_code`, `amount`, `term_months`, `purpose`, `purpose_text`, `declared_revenue_year`;
   - `DecisionInputs`: всё перечисленное, плюс `turnover: tuple[int, ...]` длины 12, `auto_decision_consent: bool`, `answered_items: frozenset[str]`, `as_of: date`.
2. `config.py`: `DecisionConfig` (frozen) — ключевая ставка, параметры продуктов (суммы, сроки, `k`, порог авто-решения, спреды), пороги стоп-факторов, пороги и баллы 12 признаков, словарь отраслей, стоп-ОКВЭД, границы оценок. `DEFAULT_CONFIG` с **ровно** значениями эталона (`KEY_RATE = 14.0`, `PRODUCTS`, `INDUSTRY`, `OKVED_STOP`, пороги из `score()` и `stop_factor()`). Кроме `DEFAULT_CONFIG`, ни одного «магического числа» в коде движка.
3. `engine.py`: `decide(inputs, cfg) -> DecisionResult` — тот же порядок, что `decide()` эталона:
   - проверка данных;
   - стоп-факторы по порядку §3;
   - скоринг;
   - политика §5–6;
   - маршрутизация §7 с приоритетом `NO_AUTO_CONSENT` > `GRADE_C` > `AMOUNT_ABOVE_AUTO`.

   Арифметика — как в эталоне: аннуитет во `float`, деньги через `Decimal(str(x))` и `ROUND_HALF_UP`, встречное вниз до 50 000. Возраст бизнеса — на `inputs.as_of`.
4. `DecisionResult` (frozen):
   - `state`: `INFO_REQUESTED` | `MANUAL_REVIEW` | `OFFER_ISSUED` | `DECLINED`;
   - `validation_rule`;
   - `outcome`: `APPROVE` | `COUNTER` | `DECLINE` | `None` (при дозапросе);
   - `reason_code`, `client_reason_code`, `grade`, `score`;
   - `points: dict[str, int]` — 12 ключей с именами из эталона;
   - `ptr_pct`;
   - `offer`: `amount`, `term_months`, `rate`, `monthly_payment`, или `None`;
   - `route_reason`;
   - `recommendation` — то же, что итог, при `MANUAL_REVIEW`;
   - **протокол:** `factors: list[FactorLine]`, `rules_fired: list[RuleFired]`, `policy: PolicyCalc | None`, `what_if: list[str]`.
5. Правила протокола:
   - `factors` — 12 строк: `code` (ключ из `points`); `title` — столбец «Признак» таблицы §4, **строки 52–65 `decision-model.md`** (не старая таблица под `<details>`), дословно; `value` (значение человекочитаемо: «38 мес.», «0,15», «41,5%»); `points`, `max_points`; `rule` — столбец «Баллы» той же строки, дословно.
   - `rules_fired`: каждый сработавший стоп-фактор (`effect: STOP`), правило проверки данных (`INFO`), причина маршрутизации (`ROUTE`), ограничение политики (`POLICY`: превышен лимит по оборотам или нагрузка). У каждого — фактическое значение и порог.
   - `policy.steps` — ход расчёта по шагам §6, по одной фразе на шаг с числами («Свободный платёж: 30% × 2 000 000 − 450 000 = 150 000 ₽»).
   - `what_if` по правилам:
     - (а) при `COUNTER` и при отказе `HIGH_LOAD`: «Одобрение при сумме ≤ X ₽ на N мес.», где X — максимальная одобряемая сумма на запрошенный срок с шагом 50 000;
     - (б) при стоп-факторе — текст действия из §3 («Погасите просроченную задолженность…»);
     - (в) при оценке C или D — «Оценка выше при: <title>» для двух признаков с наибольшим недобором баллов;
     - (г) при одобрении — пустой список.
6. `DecisionResult.to_expected() -> dict` возвращает словарь **ровно в формате, который возвращает `decide()` эталона**:
   - для одобрения и отказа — `state`, `outcome`, `offer`, `reason_code`, `client_reason_code`, `grade`, `score`, `points`, `ptr_pct`, причём ключи присутствуют только там, где они есть у эталона;
   - для `MANUAL_REVIEW` — `{state, route_reason, recommendation}`, где `recommendation` — такой же словарь итога;
   - для дозапроса — `{state, validation_rule}`.
7. `__init__.py` экспортирует `decide`, `DecisionInputs`, `DecisionResult`, `DEFAULT_CONFIG`. Модуль не импортирует ничего из БД, сети или FastAPI.

**Приёмка:**
- **Golden** `tests/decision/test_golden_personas.py`. Для каждого из 6 персонажей `personas.json` входы собираются из файла (`as_of` = `_meta.as_of`). Проверка: `assert result.to_expected() == demo.expected` — **словарь целиком**. Для `ooo_gap`: первый вызов → `{state: "INFO_REQUESTED", validation_rule}` против `first_state`/`validation_rule`, повтор с `answered_items={"REVENUE_CONFIRM"}` → `to_expected() == after_info` целиком.
- **Сверка с эталоном** `tests/decision/test_parity_reference.py`. Эталон импортируется через `importlib` по пути `contracts/decision_reference.py`. Тест генерирует ровно **2000** вариантов: `random.Random(7)`, мутации персонажей — сумма ×0,2–3,0 в границах продукта, срок в границах, все 3 продукта, обороты ×0,3–3,0, `max_dpd_12m` ∈ {0, 15, 45, 75}, `current_overdue_total` ∈ {0, 10 000}, `tax_debt` ∈ {0, 30 000, 80 000}, флаги ПОД/ФТ, согласие на авто-решение, дата регистрации. Для **каждого** варианта `engine.to_expected() == reference.decide(...)` — **словарь целиком**, включая `points`, `ptr_pct`, `client_reason_code`, `validation_rule`, `recommendation`. Расхождений должно быть **0**. При падении тест печатает первый расходящийся вариант и разницу. Тест печатает число вариантов на каждый исход, и в выборке есть все 4 состояния и все 3 исхода.
- **Протокол:**
  - `ooo_load`: `policy.steps` не пусты; `what_if[0] == "Одобрение при сумме ≤ 1 550 000 ₽ на 12 мес."` (свободный платёж 150 000 ₽, ставка 23%, 12 мес. → 1 550 000 после округления вниз до 50 000);
  - `ip_bad`: в `rules_fired` есть `SF_OVERDUE` с `effect="STOP"`;
  - `ooo_aml`: `client_reason_code == "ADDITIONAL_CHECKS"`, `reason_code == "SF_ADDITIONAL"`;
  - у всех персонажей со скорингом — ровно 12 `factors`, сумма `points` равна `score`, `max_points` в сумме дают 100.
- `uv run ruff check . && uv run pytest -q` — зелёный.
- AST-тест `tests/decision/test_no_magic_numbers.py`: во всех `app/decision/*.py`, кроме `config.py`, нет числовых литералов вне множества {0, 1, 2, 12, 100, 1200}.

**Не делать:** не трогать `contracts/`. Не менять ожидаемые значения. Если golden не сходится, ошибка в движке.

### A-01 — Мок-сервис внешних источников · Катя · Облако: да · ≤3 ч
**Зачем.** Сбор сведений из БКИ, ЕГРЮЛ/ЕГРИП и ФНС без внешних сетей (автономность, T14) с форматами, близкими к реальным, и сбоем по запросу (демо повторов).
**Файлы:** `mocks/app/*.py`, `mocks/tests/*.py`, `mocks/Dockerfile` (`COPY contracts/personas.json` и `COPY data/ …` — **папку целиком**: `background.json` может ещё не быть, загрузчик это переносит), `mocks/pyproject.toml` и `mocks/uv.lock` (только если нужна зависимость), `mocks/README.md`.
**Читать:** `contracts/external-mocks.md` целиком; `contracts/personas.json` — поля одного персонажа; `data/README.md`, если A-02 уже слит.

**Сделать:**
1. При старте загрузить `<DATA_ROOT>/contracts/personas.json` и, если есть, `<DATA_ROOT>/data/background.json`. `DATA_ROOT` — переменная окружения; по умолчанию — корень репозитория (два уровня вверх от `mocks/app`). В Docker каркас уже кладёт `contracts` в `/contracts`, поэтому в образе `DATA_ROOT=/` (`ENV` в `mocks/Dockerfile`) и `COPY data /data`. Компании индексируются по ИНН.
2. Эндпоинты ровно из `external-mocks.md`:
   - `GET /mock/v1/registry/{inn}`;
   - `POST /mock/v1/bki/report` (`kind=FULL` без `consent_id` → 403; `INFO` отдаёт только `summary`);
   - `GET /mock/v1/fns/check/{inn}`;
   - `GET /mock/v1/health`.

   Поля ответа — ровно как в контракте, для каждого ответа своя модель Pydantic с `extra="forbid"`.
3. `director.inn`: у ИП — ИНН самого ИП; у ООО — детерминированный валидный 12-значный ИНН, вычисленный из ИНН компании (`random.Random(int(inn))`). Неизвестный ИНН с верной контрольной суммой — детерминированный ответ генератора: `random.Random(int(inn))`, «чистая» компания со средними показателями. ИНН с неверной контрольной суммой или неверной длины → 404. Формат ошибки — `{"error":{"code":"NOT_FOUND",...}}`.
4. `MOCK_FAILURE_INN` — ИНН через запятую: для них **все** три источника отвечают 503. `MOCK_LATENCY_MS` — искусственная задержка, по умолчанию 300, для живого демо.
5. Тесты на каждый эндпоинт и каждого из 6 персонажей: ответ совпадает с данными `personas.json` поле в поле. Плюс тесты на 403, 404, 503, детерминированность неизвестного ИНН (два вызова → одинаково).

**Приёмка:**
- `cd mocks && uv run ruff check . && uv run pytest -q` — зелёный.
- Тест: `GET /mock/v1/registry/7706123455` → `name == "ООО «Альфа-Трейд»"`; `GET /mock/v1/fns/check/{inn}` и `POST /bki/report` для каждого персонажа → поля равны `personas.json`.
- Ручная проверка из корня (в облаке пропускается, проверяет тимлид): `docker compose up -d --build --wait mocks`, затем `docker compose exec mocks python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8001/mock/v1/registry/7706123455').read().decode())"` печатает «Альфа-Трейд».
- Компаний с неверной контрольной суммой ИНН в ответах нет.

**Не делать:** не трогать `contracts/`, `backend/`, `docker-compose.yml`. Если нужна правка compose (переменные `MOCK_FAILURE_INN`, `MOCK_LATENCY_MS`, `DATA_ROOT`), опиши её в PR (`TODO(lead)`), тимлид поправит compose.

### B-03 — Модели БД, миграция, сиды · Аня (ведёт человек) · Облако: нет · ≤4 ч
**Зачем.** Хранилище всего процесса (T11: модель данных совпадает с миграциями) и тестовые учётки (T5).
**Файлы:** `backend/app/models/*.py`, `backend/alembic/versions/*.py`, `backend/alembic/env.py` (только `target_metadata`), `backend/app/config.py` (только `contracts_dir`), `backend/Dockerfile` (только `ENV CONTRACTS_DIR`), `backend/app/seed.py`, `backend/app/security.py` (хэш паролей), `backend/tests/test_models_seed.py`, `backend/tests/conftest.py`, `backend/app/db.py` (только импорт моделей), `backend/pyproject.toml` и `backend/uv.lock` (только зависимость для хэша паролей).
**Читать:** `docs/data-model.md` целиком, `contracts/codes.md` (перечисления), `contracts/personas.json` (структура), `docs/decision-model.md` §5 (продукты).

**Сделать:**
1. SQLAlchemy 2 (`Mapped[...]`) — **все** таблицы `data-model.md` с перечисленными полями, плюс `id` (UUID), `created_at`, `updated_at`. Деньги — `BigInteger`, ставки — `Numeric(5,2)`, перечисления — строки с `CheckConstraint` на значения из `codes.md`. Внешние ключи и индексы: `application(company_id, state)`, `application_event(application_id, created_at)`, `job(status, run_after)`. `application.number` — последовательность с 1001. `application.version` — целое, начинается с 1 (оптимистическая блокировка через `version_id_col`).
2. Одна миграция Alembic, созданная `autogenerate` и вычитанная вручную. `downgrade` удаляет всё.
3. Путь к `personas.json` — настройка `contracts_dir` в `app/config.py` (по умолчанию корень репозитория + `contracts`; в Docker каркас кладёт их в `/contracts`, значение по умолчанию задаётся через `CONTRACTS_DIR=/contracts` в `backend/Dockerfile`). `python -m app.seed` — идемпотентная загрузка (второй запуск ничего не дублирует, ключ — `inn` и `login`):
   - из `personas.json`: компании, пользователи (пароль из `DEMO_PASSWORD`, хэш bcrypt или argon2), `company_member`, `account_turnover` (12 месяцев `2025-10`…`2026-09`), `risk_flag`;
   - сотрудник `underwriter`;
   - `product` × 3 — параметры из `DEFAULT_CONFIG` в B-02, а если B-02 ещё не слит — из `PRODUCTS` эталона с `TODO(lead)`;
   - `decision_config` v1 (`key_rate` 14.0 на `2026-10-23`, активна);
   - `reason_catalog` — все коды раздела «Коды причин» `codes.md` с клиентскими текстами из `decision-model.md` §3.

   Фоновые данные здесь **не** загружаются (это B-10).
4. Сиды запускаются в сервисе `migrate` после `alembic upgrade head`. Правка команды в `docker-compose.yml` — через `TODO(lead)` в PR, compose правит тимлид.

**Приёмка:**
- `cd backend && uv run pytest -q` — зелёный. Тесты берут БД из `TEST_DATABASE_URL`: локально это `docker compose up -d db` с открытым портом из `docker-compose.override.yml` (файл не коммитить), в CI — сервис Postgres, который добавляет тимлид (L-03). Если переменной нет, тесты БД пропускаются с понятным сообщением. Тесты применяют миграции и сиды дважды, затем проверяют:
  - 6 компаний, 8 пользователей (7 клиентов + андеррайтер);
  - у `ooo_load_accountant` стоит `can_sign=false`;
  - 72 строки оборотов;
  - 3 продукта;
  - коды `reason_catalog` равны списку из `codes.md`;
  - повторный запуск сидов не меняет число строк.
- В PR — вывод `uv run pytest -q -rs` **с заданным `TEST_DATABASE_URL`**: 0 skipped. PR не сливается до L-03 (Postgres в CI).
- `uv run alembic downgrade base && uv run alembic upgrade head` проходит.
- `docker compose down -v && docker compose up -d --build --wait` → `migrate` выходит с кодом 0, `api` в состоянии `healthy`.
- Вручную: `docker compose exec db psql -U postgres -c "\dt"` показывает все таблицы `data-model.md`. Вывод вставить в PR.

**Не делать:** эндпоинтов не писать; модели не импортируются в `app/decision/`.

### F-01 — Оболочка фронтенда · Лана · Облако: нет (ставит новые npm-пакеты, нужен скриншот) · ≤3 ч
**Зачем.** Каркас всех экранов: вход тестовыми учётками, маршруты по ролям, единая обработка ошибок, работа без бэкенда на моках (MSW) до готовности API.
**Файлы:** `frontend/src/**` (кроме `src/api/schema.d.ts` и `src/theme.ts`), `frontend/package.json`, `frontend/package-lock.json`, `frontend/public/mockServiceWorker.js`. Импорт из `../contracts` или `../../contracts` внутри `src/` **запрещён** (в Docker-сборке их нет). Данные персонажей для MSW копируются в `src/mocks/fixtures.ts`.
**Читать:** `docs/screens.md` (список экранов и маршрутов), `contracts/api-types.ts`: аутентификация, `ApiError`, `MeResponse`.

**Сделать:**
1. Маршруты:
   - `/login`;
   - клиент: `/app` (главная), `/app/applications/new`, `/app/applications/:id`;
   - андеррайтер: `/bank/queue`, `/bank/applications/:id`, `/bank/journal`.

   Пока в каждом маршруте заглушка: заголовок экрана из `screens.md`.
2. Вход: форма логина и пароля (Mantine). Токен хранится в `sessionStorage`. `GET /me` после входа. Редирект по роли: `CLIENT` → `/app`, `UNDERWRITER` → `/bank/queue`. Выход очищает токен. Защищённые маршруты без токена ведут на `/login`, чужая роль — на свою главную.
3. Клиент API (`openapi-fetch` из каркаса) подставляет `Authorization`. При 401 — выход и переход на `/login`. Ошибки `ApiError` показываются уведомлением Mantine с текстом `error.message`; `details.fields` отдаются форме.
4. Переключатель «моки или настоящий API»: переменная `VITE_USE_MSW=true` включает MSW в режиме `dev`. Обработчики MSW: `/auth/login`, `/me`, `/products`, `/applications` (GET и POST), `/applications/{id}` — с данными персонажей `ip_good` и `ooo_load`, скопированными в `src/mocks/fixtures.ts`. Типы обработчиков — из `schema.d.ts`, без `any`. В сборке `build` MSW не включается.
5. Шапка: имя пользователя, компания (если их несколько — выбор), кнопка «Выйти». На клиентской части — ссылка «Новая заявка».

**Приёмка:**
- `npm run lint && npm run typecheck && npm test && npm run build` — зелёный.
- Тесты (vitest + Testing Library):
  - вход `ip_good` → оказываемся на `/app`;
  - вход `underwriter` → `/bank/queue`;
  - без токена `/app` → `/login`;
  - 401 от API → выход;
  - `ApiError` показан уведомлением.
- В коде нет `any` и `@ts-ignore` (правила eslint `no-explicit-any` и `ban-ts-comment` в режиме error).
- `docker compose build web` — зелёный.
- Скриншот `/login` и `/app` в режиме MSW — в PR.

**Не делать:** не трогать `theme.ts` (это F-02), не делать экраны сверх заглушек, не хранить токен в `localStorage`.

---

## Карточки [черновик] (тимлид уточнит перед стартом)

- **B-04.** `POST /auth/login` (JWT на 8 ч, ошибки 401 и 422), `GET /me`, проверка роли на каждом эндпоинте, доступ клиента только к своим компаниям (чужая компания → 404). `GET /products` из таблицы `product` и `decision_config`. `POST /calculator` — ставка по оценке A и аннуитет. `GET /companies/{id}/profile` — реестр через адаптер плюс средний оборот. Тесты на роли: таблица «эндпоинт × роль → код ответа».
- **B-05.**
  - Модуль `applications/state_machine.py`: таблица переходов из `state-machine.md` как данные. Недопустимый переход → 409 `INVALID_TRANSITION`; каждый переход пишет событие в `application_event`.
  - Вычисление `stage`, `timeline` и `allowed_actions` по `codes.md`.
  - POST, PATCH (`If-Match`, иначе 409 `CONFLICT_VERSION`), GET, список.
  - Границы продукта → 422.
  - Тест: каждая пара «состояние × событие» из таблицы.
- **B-06.**
  - OTP: 6 цифр, 5 минут, `demo_code` в ответе только при `DEMO_MODE`.
  - Согласия с `doc_hash` SHA-256.
  - `submit`: только `can_sign`, у ИП обязателен `auto_decision`.
  - `request-signature`: только без `can_sign`, только в DRAFT.
  - Постановка задачи `job` для worker.
- **B-07.**
  - Worker с `SELECT … FOR UPDATE SKIP LOCKED`, идемпотентные шаги.
  - Шаги: VALIDATION (через `decide()`) → ENRICHMENT (адаптеры `RegistryProvider`, `BureauProvider`, `TaxProvider`: HTTP к мокам и фейк для тестов; 3 повтора с паузой, затем `MANUAL_REVIEW` / `SOURCE_UNAVAILABLE`) → ASSESSMENT (`decide()`, запись `decision` с `inputs_snapshot`) → `OFFER_ISSUED` / `DECLINED` / `MANUAL_REVIEW` / `INFO_REQUESTED`.
  - `info-response` возвращает заявку в VALIDATION.
  - Демо-пауза 1–2 с на шаг.
  - Веха M1.
- **B-08.** Очередь (`QueueItem`, сортировка по ожиданию), `ApplicationBank` со всем протоколом, `POST /underwriting/{id}/decision` со всеми исходами; событие `UNDERWRITER_OVERRIDE` при расхождении с рекомендацией. Клиентская схема не содержит внутренних полей — тест сериализации для `ooo_aml`.
- **B-09.** Принять или отклонить оферту (`offer_version`), подпись участников (`party`), SIGNED → DISBURSED с графиком платежей, отзыв, возражение ИП (≤30 дней после авто-отказа).
- **B-10.** Планировщик истечений (`due_at`, `expires_at`), `POST /demo/time-shift`, `GET /bank/applications` (`Page`), загрузка `data/background.json` через тот же конвейер до `target_state`.
- **A-03.** `tests/e2e/api/test_personas.py`: для каждого персонажа через HTTP — вход, создание и подача заявки (`demo.app`, `demo.consents`), ожидание итогового состояния (до 60 с), проверка `demo.expected`. Для `ooo_gap` — ответ `demo.info_response`, для `ooo_border` — решение андеррайтера. Пока стенда нет, тест пропускается по `pytest.mark.skipif`, если `/api/v1/ready` недоступен.
- **A-05.** Коллекция Bruno (`docs/api-collection/`): вход каждым персонажем и полный путь `ip_good` и `ooo_gap`. Проходит на запущенном стенде.
- **A-06.** Репетиция на чистом ПК строго по README; отчёт `docs/demo/rehearsal-T20.md`: время каждого шага, ошибки, скриншоты.
- **F-02…F-09** — по макетам человека (D6) и `screens.md`. Карточки уточняются после получения токенов (24.10 ~11:00).
