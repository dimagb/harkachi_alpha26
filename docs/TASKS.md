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
| T-00 | Каркас репозитория | Аня (ведёт человек) | 23.10 | нет | — | слит (PR #1), M0 |
| L-01 | AGENTS.md, TASKS.md, notify.py, стартовые промпты | тимлид | 23.10 | — | — | готово (ворота 4, D10) |
| L-03 | После M0: CODEOWNERS, Postgres в CI (`TEST_DATABASE_URL`), команда сидов в compose (после B-03) | тимлид | 23.10 вечер | — | T-00 | готово: CI с Postgres, CODEOWNERS, сиды в migrate |
| A-02 | Генератор фоновых данных | Катя | 23.10 сейчас | **да** | — | слит (PR #2) |
| A-04 | Сценарии проверки (T12) | Катя | 23.10 сейчас | **да** | — | слит (PR #7) |
| B-01 | Схемы API и заглушки → полный `openapi.json` | Лана | 23.10 после M0 | **да** | T-00 | слит (PR #5) |
| B-02 | Движок решения `decide()` | Лана | 23.10 после M0 | **да** | T-00 | [готова] |
| A-01 | Мок-сервис внешних источников | Катя | 23.10 после M0 | **да** | T-00 | слит (PR #4) |
| B-03 | Модели БД, миграция, сиды | Аня (ведёт человек) | 23.10 ночь — 24.10 | нет | T-00 | слит (PR #3) |
| F-01 | Оболочка фронтенда: вход, маршруты, роли, клиент API, MSW | Лана | 24.10 8:00 | нет | B-01 | слит (PR #8) |
| B-04 | Вход, `/me`, продукты, калькулятор, профиль | Аня | 23.10 вечер (часть 1), после B-01 — часть 2 | нет | B-03 ✔, B-01 (часть 2) | слит (PR #6) |
| B-05 | Заявка: создание и правка, автомат состояний, журнал, лента | Аня | 24.10 15:00 | нет | B-04 | слит (PR #10) |
| B-06 | OTP, согласия, подача, просьба подписать | Аня | 24.10 вечер | нет | B-05 | [готова] |
| B-07 | Worker: конвейер до решения, дозапрос | Аня | 24.10 вечер | нет | B-02, B-05, A-01 | [черновик] |
| A-03 | Сквозные тесты персонажей через API | Катя | 23.10 вечер / 24.10 | **да** | B-01 ✔ | слит (PR #9); прогон на стенде — M1/M2 |
| F-02 | Тема из токенов дизайна | Лана | 24.10 11:00 | нет | F-01, токены | [готова] |
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
- `backend/tests/test_health.py` — **только** две правки (решение тимлида на блокер 23.10): в `test_docs_and_schema` равенство путей заменить на `{"/api/v1/health", "/api/v1/ready"} <= set(schema["paths"])` (полный список проверяет `test_contract_paths.py`); в ожидаемых `message` английские тексты заменить на новые русские **точным равенством**, весь остальной словарь ответа сравнивать как раньше. Удалять тесты и ослаблять другие проверки нельзя;
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
4. Сиды запускаются в сервисе `migrate` после `alembic upgrade head`. **Исключение из владения:** в этом PR разрешено изменить в `docker-compose.yml` только строку `command` сервиса `migrate` на `["sh", "-c", "/app/.venv/bin/alembic upgrade head && /app/.venv/bin/python -m app.seed"]`. Тексты причин, служебные перечисления и `decision_config.params` — в `contracts/codes.md` (разделы «Клиентские тексты причин», «Служебные перечисления», «decision_config.params»). Postgres в CI уже есть: `TEST_DATABASE_URL`.

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

### B-04 — Вход, `/me`, продукты, калькулятор, профиль · Аня · Облако: нет · ≤4 ч
**Зачем.** Вход тестовыми учётками (T5), разграничение доступа по ролям и компаниям (банк не показывает чужое), первые настоящие эндпоинты для фронтенда (F-01, F-03).

**Две части в одном PR.** Часть 1 не зависит от B-01 и делается сразу. Часть 2 — только после того, как B-01 слит в `main` (проверка: `git fetch origin && git ls-tree -r origin/main --name-only | grep '^backend/app/api/'` — непусто). Если часть 1 готова, а B-01 ещё не в `main`: запушить ветку, открыть PR как **draft** (`gh pr create --draft`), отправить `notify QUESTION B-04 "часть 1 готова, жду B-01"` и остановиться. Продолжение — в том же чате: `git fetch origin && git rebase origin/main`, затем часть 2.

**Файлы:**
- `backend/app/auth/*.py` (токены, вход, зависимости доступа);
- `backend/app/catalog/*.py` (новый: продукты, калькулятор);
- `backend/app/companies/*.py` (новый: профиль);
- `backend/app/integrations/__init__.py`, `backend/app/integrations/registry.py` (новые: адаптер реестра);
- часть 2: роутеры B-01 в `backend/app/api/` — **только** обработчики `POST /auth/login`, `GET /me`, `GET /products`, `POST /calculator`, `GET /companies/{id}/profile` и подключение общей зависимости проверки токена (см. п. 6). Сигнатуры, `response_model`, `responses`, `summary` B-01 не менять;
- часть 2: `backend/app/main.py` — только `dependencies=[...]` в `include_router`, если общую зависимость удобнее подключить там;
- часть 2: `backend/app/errors.py` — **только** если в классе исключения B-01 этого нет: необязательный параметр `headers` и сохранение переданных `message`, `details`, `headers` в ответе (тексты по умолчанию для статуса B-01 не менять);
- часть 1 (временно): `backend/app/auth/errors.py` — класс `ApiErrorException(status, code, message, details=None, headers=None)` с `TODO(lead): заменить импортом из app.errors после B-01`; после rebase на B-01 файл удалить, импорты перевести на `app.errors`;
- часть 2: `backend/tests/test_schemas_validation.py` — **только** фикстура подмены `current_user` тестовым `User` со снятием подмены после теста (ответ на вопрос 23.10); тесты и ожидания 422 не менять;
- часть 2: `backend/tests/test_contract_paths.py` — **только** в фикстуре теста 501: `app.dependency_overrides[current_user] = lambda: User(id=uuid4(), role="CLIENT", login="t", full_name="t", password_hash="")` и снятие подмены после теста (без токена заглушки теперь отвечают 401; БД этот тест не использует). Логику `current_user` ради теста не менять; кроме того (ответ на вопрос 23.10), разрешено исключить из параметризации теста 501 **ровно** 5 реализуемых путей — явной константой `IMPLEMENTED` с проверкой `len(IMPLEMENTED) == 5`; что они больше не отвечают 501, проверяют тесты B-04. Обработчикам можно добавлять параметры `Depends(...)` (сессия, пользователь, реестр): «сигнатуры не менять» означает не менять то, что видно в OpenAPI, — критерий пустой дифф `openapi.json`;
- `backend/pyproject.toml`, `backend/uv.lock` — только `pyjwt` и перенос `httpx` из `dev` в основные зависимости;
- тесты: `backend/tests/test_auth.py`, `backend/tests/test_catalog.py`, `backend/tests/test_profile.py`, `backend/tests/test_access_matrix.py` (новые).

**Читать:** `contracts/api.md` (строки этих 5 эндпоинтов и столбец «Роль»), `contracts/api-types.ts` (разделы «Аутентификация», «Каталог и калькулятор», «Профиль компании», `ApiError`), `contracts/codes.md` (раздел «Продукты, цели» с подразделом «Витрина продуктов»), `contracts/external-mocks.md` (раздел «ЕГРЮЛ / ЕГРИП»), `contracts/decision_reference.py` (функции `annuity`, `rub`), `backend/app/models/`, `backend/app/security.py`, `backend/tests/conftest.py`.

**Сделать — часть 1 (сразу):**
1. **Токены** (`app/auth/tokens.py`), библиотека PyJWT. Алгоритм только HS256 (при проверке `algorithms=["HS256"]`), ключ — `settings.jwt_secret`. Поля: `sub` = `user.id` (строка UUID), `role`, `iat`, `exp` = сейчас + `settings.jwt_ttl_hours`. `expires_in` в ответе = `jwt_ttl_hours * 3600`.
2. **Вход** (`app/auth/service.py`): поиск `user` по `login`, проверка `verify_password` из `app/security.py`. Неизвестный логин и неверный пароль — **одинаковая** ошибка 401 `UNAUTHORIZED` «Неверный логин или пароль» (нельзя по ответу узнать, есть ли такой логин). Пароль и токен не пишутся в логи.
3. **Зависимости доступа** (`app/auth/deps.py`) — их будут использовать все следующие задачи, имена фиксированы:
   - `current_user` → объект `User`. Нет заголовка, не `Bearer`, неверная подпись, `alg` не HS256 (в том числе `none`), истёк `exp`, пользователя с таким `sub` нет → 401 `UNAUTHORIZED` «Требуется вход» с заголовком `WWW-Authenticate: Bearer`. В части 1 `current_user(credentials: HTTPAuthorizationCredentials | None, session)` получает учётные данные параметром. В части 2 к нему подключается **тот же объект** `HTTPBearer(auto_error=False)`, что объявил B-01 (найти: `grep -rn HTTPBearer backend/app/api`; импортировать, не создавать новый), иначе изменится `openapi.json`. `jwt.decode(..., algorithms=["HS256"], options={"require": ["exp", "iat", "sub"]})` — токен без `exp` недействителен;
   - `require_roles(*roles)` → чужая роль → 403 `FORBIDDEN` «Недостаточно прав»;
   - `member_company(company_id, user, session)` — **обычная функция, не `Depends`** (иначе FastAPI сделает `company_id` query-параметром и изменит контракт); её вызывает обработчик после проверки роли; → `(Company, CompanyMember)`; если компании нет **или** пользователь в ней не состоит → 404 `NOT_FOUND` «Компания не найдена» (одинаково, чтобы не раскрывать чужие компании).

   Ошибки — исключение `ApiErrorException` (в части 1 — временный класс из `app/auth/errors.py`, в части 2 — класс B-01 из `app/errors.py`), тексты на русском, `message` у каждого случая свой (как написано в этой карточке).
4. **Продукты** (`app/catalog/products.py`): `list_products(session)` → список `Product` по подразделу «Витрина продуктов» в `codes.md`: границы из `product.params`, `rate_from` = `key_rate` активной `decision_config` + `params.spread.A`, `key_rate` и `key_rate_date` (`YYYY-MM-DD`) — из неё же, `purposes` и `requires_guarantor_ooo` — из таблицы витрины (константа в модуле), порядок — как в таблице. Нет активной `decision_config` → 503 `SERVICE_UNAVAILABLE`.
5. **Калькулятор** (`app/catalog/calculator.py`):
   - строки `product` с таким кодом нет в БД → 503 `SERVICE_UNAVAILABLE` (неизвестный код отсекает схема B-01 ещё до обработчика); `amount` вне `[min, max]` продукта или `term_months` вне `[tmin, tmax]` → 422 `VALIDATION_ERROR` с `details.fields.amount` («Сумма от 300 000 до 5 000 000 ₽») или `details.fields.term_months` («Срок от 6 до 36 мес.»), числа — из параметров продукта, разделитель разрядов — обычный пробел U+0020;
   - `rate_estimate` = `rate_from` (оценка A, справочно);
   - `monthly_payment` = аннуитет, рубли, `ROUND_HALF_UP`; для `OVERDRAFT` — `null`. Если в `app/decision/` уже есть функция аннуитета (B-02 слит) — использовать её; иначе своя функция в `calculator.py` с `TODO(lead): заменить на функцию B-02`. В обоих случаях тест сверяет результат с `annuity` + `rub` эталона на сетке значений.
6. **Адаптер реестра** (`app/integrations/registry.py`): `RegistryRecord` (поля ответа `GET /registry/{inn}` из `external-mocks.md`; `director.inn: str | None` — в `personas.json` его нет; лишние поля ответа мока игнорируются, наружу идут только поля `CompanyProfile`), протокол `RegistryProvider.get(inn) -> RegistryRecord`, `HttpRegistryProvider` (`httpx`, база — `settings.mocks_url`, таймаут 3 с, без повторов: повторы — в worker B-07) и `FakeRegistryProvider` (из словаря, для тестов). Ответ 404 мока → `None`; таймаут, ошибка соединения, 5xx → исключение `ProviderUnavailable`. Зависимость FastAPI `get_registry_provider()`, подменяемая в тестах через `dependency_overrides`.
7. **Профиль** (`app/companies/profile.py`): `CompanyProfile` = поля компании из БД (`id`, `inn`, `ogrn`, `kind`, `name`, `reg_date`, `okved_main`, `address`) + из реестра `status`, `director_full_name` (= `director.full_name`), `founders`; `avg_monthly_turnover` = среднее `account_turnover.credit_turnover` компании, рубли, `ROUND_HALF_UP` (нет оборотов → 0); `source_note` = «Данные из ЕГРЮЛ на ДД.ММ.ГГГГ» для `OOO`, «Данные из ЕГРИП на …» для `IP`, дата — `date.today()` с `TODO(lead): заменить на демо-часы B-10`. `ProviderUnavailable` → 503 `SERVICE_UNAVAILABLE` «Реестр временно недоступен, попробуйте позже»; реестр вернул `None` → 404 `NOT_FOUND`.

**Тесты части 1** — сервисы и зависимости без роутеров B-01: тестовое приложение `FastAPI()` создаётся внутри тестового файла. В `app/api/` и `main.py` в части 1 **ничего не создавать и не менять**. HTTP-тесты через `app.main` — только в части 2.

**Сделать — часть 2 (после слияния B-01):**
8. Заполнить 5 обработчиков вместо `NOT_IMPLEMENTED`:
   - `POST /auth/login` — без токена;
   - `GET /me` — любая роль; `companies` — членства пользователя, по `company.name`; у андеррайтера `[]`;
   - `GET /products` и `POST /calculator` — `require_roles("CLIENT")`;
   - `GET /companies/{id}/profile` — `require_roles("CLIENT")` + `member_company`.
9. **Все** остальные пути API, кроме `/auth/login`, `/health`, `/ready`, получают зависимость `current_user` (на уровне роутера; если в роутере есть `/auth/login` — на каждый эндпоинт, а не на роутер): без токена → 401, с токеном → по-прежнему 501. Проверку ролей у заглушек не добавлять: это делают задачи, которые их реализуют.
10. Пересобрать `contracts/openapi.json` и `frontend/src/api/schema.d.ts` командами из `AGENTS.md` §2. **Дифф обоих файлов должен быть пустым**: B-04 не меняет контракт. Если дифф не пуст — сначала искать причину у себя (новая схема безопасности, изменённый `response_model`); если без изменения контракта не обойтись — `notify QUESTION`.

**Приёмка:**
- `cd backend && uv run pytest -q -rA` с заданным `TEST_DATABASE_URL` — зелёный, 0 skipped. Тесты API используют фикстуру `migrated_database` из `conftest.py` (схема с сидами, пароль демо-учёток в ней — `b03-test-password`) и подменяют через `dependency_overrides` `get_session` и `get_registry_provider` (на `FakeRegistryProvider` из `personas.json`) — **во всех** API-тестах, включая `test_access_matrix.py`: в CI моков нет; `conftest.py` не менять, свои фикстуры — в своих тестовых файлах.
- `test_auth.py`:
  - вход каждым логином из `personas.json` и `underwriter` → 200, `token_type = "bearer"`, `expires_in = 28800`, `user.role` верная; токен декодируется, `sub` = id пользователя;
  - неверный пароль и неизвестный логин → 401 с **одинаковым** телом;
  - токен с истёкшим `exp`, с чужим ключом, с `alg: none`, испорченный, без `Bearer` → 401 и `WWW-Authenticate: Bearer`;
  - `GET /me` для `ooo_load_accountant`: одна компания, `can_sign = false`; для `underwriter`: `companies = []`.
- `test_catalog.py`:
  - `GET /products` → 3 продукта в порядке `EXPRESS`, `WORKING_CAPITAL`, `OVERDRAFT`; `EXPRESS`: `min_amount = 300000`, `max_amount = 5000000`, `rate_from = 22.0`, `key_rate = 14.0`, `key_rate_date = "2026-10-23"`; `purposes` и `requires_guarantor_ooo` — точно как в таблице витрины `codes.md` (тест разбирает таблицу);
  - калькулятор, точные значения: `EXPRESS 1 500 000 / 24` → `22.0`, `77817`; `WORKING_CAPITAL 4 000 000 / 12` → `21.0`, `372455`; `EXPRESS 300 000 / 6` → `53257`; `WORKING_CAPITAL 15 000 000 / 24` → `770785`; `OVERDRAFT` → `monthly_payment = null`;
  - сверка с эталоном (`annuity` + `rub`, модуль загружается из `contracts/decision_reference.py` через `importlib`) на сетке: `EXPRESS` и `WORKING_CAPITAL` × 3 суммы (`min`, `(min+max)//2`, `max`) × 3 срока (`tmin`, `(tmin+tmax)//2`, `tmax`); `OVERDRAFT` → `monthly_payment is None`, `rate_estimate == 24.0`;
  - границы: `amount = min − 1`, `max + 1`, `term = tmin − 1`, `tmax + 1` → 422, `details.fields` сверяется строкой целиком: `"Сумма от 300 000 до 5 000 000 ₽"` (EXPRESS), `"Срок от 3 до 24 мес."` (WORKING_CAPITAL); `amount = min` и `max` → 200;
  - нет активной `decision_config` (тест снимает флаг `active` в своей транзакции и откатывает её) → `GET /products` 503.
- `test_profile.py` (реестр — `FakeRegistryProvider` из данных `personas.json`):
  - `ip_good` → `avg_monthly_turnover = 1200000`, `source_note` начинается с «Данные из ЕГРИП на »; `ooo_border` → `912500`, «Данные из ЕГРЮЛ на »; `status`, `director_full_name`, `founders` совпадают с `personas.json`;
  - реестр недоступен → 503 `SERVICE_UNAVAILABLE`; `HttpRegistryProvider` проверен через `httpx.MockTransport`: 200 → запись, 404 → `None`, 500 и таймаут → `ProviderUnavailable`.
- `test_access_matrix.py` — одна параметризованная таблица «эндпоинт × кто → код»:

  | Эндпоинт | без токена | CLIENT своей компании | CLIENT чужой компании | UNDERWRITER |
  | --- | --- | --- | --- | --- |
  | `GET /me` | 401 | 200 | — | 200 |
  | `GET /products` | 401 | 200 | — | 403 |
  | `POST /calculator` | 401 | 200 | — | 403 |
  | `GET /companies/{id}/profile` | 401 | 200 | 404 | 403 |
  | `GET /companies/{случайный uuid}/profile` | 401 | 404 | — | 403 |

  Плюс: каждый путь из `api.md`, кроме `/auth/login`, `/health`, `/ready`, без токена → 401 (тот же разбор таблицы, что в `test_contract_paths.py`; тела и параметры — валидные, из `tests/fixtures_bodies.py`). Все ответы с ошибкой — валидный `ApiError` с кодом из `codes`, сообщения на русском (в `message` есть кириллица).
- `uv run ruff check . && uv run ruff format --check .` — зелёный.
- `git diff --exit-code contracts/openapi.json frontend/src/api/schema.d.ts` после пересборки — пусто.
- Вручную на стенде (`docker compose up -d --build --wait`):
  ```
  curl -s -X POST localhost:8080/api/v1/auth/login -H "Content-Type: application/json" -d '{"login":"ip_good","password":"demo2026"}'
  ```
  → токен; `GET /api/v1/me`, `GET /api/v1/products` с этим токеном → 200. `GET /api/v1/companies/{id}/profile` → 200, если A-01 (моки) уже в `main`; иначе 503 — это ожидаемо, указать в PR. Вывод вставить в PR.
- CI зелёный.

**Не делать:** не трогать `conftest.py`, модели, миграции, сиды и `contracts/`; не реализовывать другие эндпоинты; не добавлять повторы запросов к реестру; не хранить токены в БД; не логировать пароли и токены.

### B-05 — Заявка: создание и правка, автомат состояний, журнал, лента · Аня · Облако: нет · ≤6 ч
**Зачем.** Ядро процесса: заявка проходит только разрешённые переходы (F19, T10), каждый переход виден в журнале (аудит), клиент на каждом шаге понимает, что происходит и что от него нужно (лента — ключевой экран 1).

**Порядок работы.** Два коммита в одном PR: сначала автомат и `test_state_machine.py`, затем API и сериализатор. Если к концу 4-го часа второй коммит не готов — запушить, открыть draft PR, `notify QUESTION B-05 "автомат готов, API в работе"` и продолжать. Ослаблять тесты ради времени нельзя.

**Соглашение (с B-04):** пользователя в обработчик передавать только через зависимости `authenticated_user` / `client_user` из `app/api/routes.py`; свой способ не изобретать.

**Файлы:**
- `backend/app/applications/*.py` (`state_machine.py`, `service.py`, `serializers.py`);
- `backend/app/api/routes.py` — **только** тела обработчиков `POST /applications`, `PATCH /applications/{id}`, `GET /applications`, `GET /applications/{id}` и параметры `Depends(...)`; что видно в OpenAPI, не менять;
- `backend/app/schemas/api.py` — **только** удалить `model_validator` `require_other_purpose` из `ApplicationCreate` и `ApplicationPatch`: проверка переезжает в сервис (п. 2–3), в OpenAPI валидаторы не видны;
- `backend/tests/test_schemas_validation.py` — **только** случай `({"purpose": "OTHER"}, "request")`: перенести в `test_applications_api.py` как API-тест с ожиданием `details.fields.purpose_text`;
- `backend/app/catalog/calculator.py` — **только** вынести проверку границ продукта в функцию `validate_terms(session, product_code, amount, term_months)`, возвращающую строку `Product` (модель `app.models.Product`, в B-04 импортирована как `ProductRow`); тексты ошибок те же, `calculate` вызывает её;
- `backend/tests/test_contract_paths.py` — **только** добавить 4 пути в константу `IMPLEMENTED` и обновить `len(...)` на 9;
- `backend/tests/test_profile.py` — **только** вызов `get_settings.cache_clear()` в фикстуре до и после теста (следствие перехода на `get_settings()`, ответ на вопрос 23.10);
- попутно, замечания ревью B-04: `backend/app/auth/tokens.py` и `backend/app/integrations/registry.py` — `get_settings()` вместо `Settings()`; `backend/app/auth/service.py` — при неизвестном логине вызывать `verify_password(password, DUMMY_HASH)` (одинаковое время ответа); `backend/tests/test_access_matrix.py` — чужая компания = компания конкретного другого персонажа по ИНН + тест, что тело 404 для чужой и несуществующей компании одинаково;
- тесты: `backend/tests/test_state_machine.py`, `backend/tests/test_applications_api.py`, `backend/tests/test_application_view.py` (новые).

**Читать:** `docs/state-machine.md` целиком, `contracts/codes.md` (разделы «Этапы ленты», «Лента и действия по состояниям», «Действия клиента», «Типы событий журнала», «Служебные перечисления»), `contracts/api-types.ts` (`ApplicationCreate`, `ApplicationPatch`, `ApplicationClient`, `ApplicationListItem`, `Stage`, `TimelineItem`, `PartyClient`), `contracts/api.md` (строки `/applications`), `backend/app/models/process.py`, `backend/app/auth/deps.py`, `backend/app/catalog/`, `backend/app/api/routes.py`.

**Главное правило:** переходы, тексты ленты и правила действий — **константы в коде**. `backend/app/` во время работы не читает `docs/` и `contracts/`: в Docker этих папок нет. Тесты сверяют константы с документами.

**Сделать:**
1. **Автомат** (`state_machine.py`). Единица данных — тройка `(из, в, actor_type)`, дубликаты схлопываются (например, `OFFER_ISSUED → WITHDRAWN` встречается дважды). Тройки — ровно по «Таблице переходов» `state-machine.md`.

   Раскрытие ячеек «Из» и «В»: делить по `/` и `,`. `* до SIGNED` — это `DRAFT`, `SUBMITTED`, `VALIDATION`, `INFO_REQUESTED`, `ENRICHMENT`, `ASSESSMENT`, `MANUAL_REVIEW`, `OFFER_ISSUED`, `SIGNING`.

   «Кто» → `actor_type`:
   - система, планировщик → `SYSTEM`;
   - клиент, подписант, клиент-ИП → `CLIENT`;
   - андеррайтер → `UNDERWRITER`;
   - «подписант (+ поручитель)» → две тройки: `CLIENT` и `GUARANTOR`.

   Функция `transition(session, application, to_state, *, actor_type, actor_id, reason_code=None, payload=None)`:
   - тройки нет → `ApiErrorException(409, INVALID_TRANSITION, "Действие недоступно в текущем состоянии заявки")`, в БД ничего не пишется;
   - иначе меняет `state`, пишет `application_event(event_type="STATE_CHANGED", from_state, to_state, actor_type, actor_id, reason_code, payload)`.

   Коммит делает вызывающий. Менять `application.state` вне `state_machine.py` нельзя никаким способом.
2. **Создание** (`service.py`, `POST /applications`, `client_user`):
   - `company_id` не UUID → 404 «Компания не найдена» (не 500);
   - `member_company` → 404 для чужой;
   - границы — `validate_terms` (422 с текстами калькулятора);
   - `purpose` вне `purposes` продукта по `PRODUCT_CATALOG` из `app/catalog/products.py` (не дублировать) → 422 `details.fields.purpose = "Эта цель недоступна для выбранного продукта"`;
   - `purpose = OTHER` без `purpose_text` → 422 `details.fields.purpose_text = "Укажите цель кредита"`;
   - `created_by` = пользователь, `state = DRAFT`, событие `STATE_CHANGED` с `from_state = NULL`, `to_state = DRAFT`, `actor_type = CLIENT`; ответ `ApplicationClient`, код 200.

   Ограничения «одна активная заявка на компанию» нет.
3. **Правка** (`PATCH /applications/{id}`, `client_user`, `If-Match` — номер версии). Порядок проверок:
   1. заявки нет или пользователь не член её компании → 404 «Заявка не найдена»;
   2. `If-Match` ≠ `version` → 409 `CONFLICT_VERSION` «Заявку изменили в другом окне — обновите страницу»;
   3. не `DRAFT` → 409 `INVALID_TRANSITION`;
   4. слияние: `patch.model_dump(exclude_unset=True)` поверх текущих полей; явный `null` в `purpose_text` стирает текст; при смене `purpose` с `OTHER` на другую цель `purpose_text` обнуляется;
   5. полная проверка итоговой заявки как при создании → 422;
   6. `session.flush()` внутри `try`: `StaleDataError` (гонка двух запросов с одной версией) → тот же 409 `CONFLICT_VERSION`.

   Событий правка не пишет; `version` растёт на 1.
4. **Чтение:**
   - `GET /applications/{id}` — 404 для чужой заявки;
   - `GET /applications?company_id=` — `member_company`, затем `ApplicationListItem[]`, сортировка `created_at DESC, number DESC`.
5. **Сериализация** (`serializers.py`): `to_client(session, application, user) -> ApplicationClient` и `to_list_item(...)`.
   - `stage`, `timeline`, `allowed_actions` — строго по разделу «Лента и действия по состояниям» `codes.md`, включая поправки;
   - `parties` — из `party`: `signed = status == "SIGNED"`, `is_me = user_id == user.id`;
   - `offer`, `client_reason`, `info_request`, `objection` — `null` с `TODO(lead): заполнить в B-07/B-09`;
   - `OBJECT` в B-05 не выдаётся никогда (тот же TODO).

   Внутренних полей (`decision`, баллы, `risk_flag`) сериализатор не читает.

**Приёмка:**
- `cd backend && uv run pytest -q -rA` с `TEST_DATABASE_URL` — зелёный, 0 skipped. Фикстуры — как в тестах B-04, `conftest.py` не менять.
- `test_state_machine.py`:
  - тест разбирает «Таблицу переходов» `docs/state-machine.md` по правилам п. 1 и сравнивает множество троек с константой модуля — равны. Нераспознанная ячейка («Из», «В» или «Кто») → тест **падает**, а не пропускает строку;
  - параметризованный тест: 14 × 14 пар состояний (включая `X → X`) × 4 `actor_type` → успех тогда и только тогда, когда тройка есть в таблице; при отказе — 409 и ни одной новой строки в `application_event`. Исходное состояние тест выставляет прямо в фикстуре;
  - успешный переход пишет одно событие со всеми полями;
  - статическая проверка через `ast` по `backend/app/` вне `state_machine.py`: нет присваивания атрибуту `state`, `setattr(..., "state", ...)`, ключа `state=` в вызовах `.values(` / `update(`;
  - grep: в `backend/app/` нет строк `"docs/"` и `"contracts/"` (кроме `config.py` — `contracts_dir` для сидов).
- `test_applications_api.py`:
  - каждый персонаж создаёт заявку с `demo.app` из `personas.json` → 200, `DRAFT`, `number ≥ 1001`, `version = 1`, одно событие;
  - чужая компания и `company_id = "abc"` → 404;
  - `amount = min − 1` → 422 с текстом калькулятора;
  - `WORKING_CAPITAL` + `EQUIPMENT` → 422 `purpose`;
  - `OTHER` без текста → 422 `purpose_text` (POST и PATCH);
  - PATCH `{"purpose": "OTHER"}` при уже сохранённом `purpose_text` → 200;
  - PATCH с верной версией → 200, `version = 2`; со старой → 409 `CONFLICT_VERSION`; без `If-Match` → 422; не в `DRAFT` → 409 `INVALID_TRANSITION`; смена продукта, при которой сумма вне границ → 422;
  - список: две заявки, тест явно проставляет им разные `created_at` (UPDATE в тесте) → новая первой; чужая компания → 404;
  - `UNDERWRITER` на всех 4 путях → 403.
- `test_application_view.py` — для **каждого** из 14 состояний (цепочка разрешённых `transition`):
  - `stage.index`, `what_happens`, `what_to_do`, статусы 6 этапов и `allowed_actions` — как в таблице `codes.md`. Тест разбирает таблицу; из ячейки действий берутся только коды раздела «Действия клиента»; ожидание = разобранный список минус `OBJECT`;
  - условия и поправки — отдельными случаями:
    - `DRAFT` для `ooo_load` (`SUBMIT`) и `ooo_load_accountant` (`REQUEST_SIGNATURE`, статус `current`, «Ждём решения подписанта компании»), затем `awaiting_signature = true` (флаг ставит тест) → `REQUEST_SIGNATURE` пропал;
    - `OFFER_ISSUED` для тех же двух пользователей;
    - `SIGNING`: тест вставляет `party(status=PENDING, user_id=я)` → `SIGN` есть; `party(SIGNED)` или чужой → `SIGN` нет, «Ждём подписи остальных участников»;
    - `WITHDRAWN` с `reason_code = CLIENT_REJECTED_OFFER` → «Вы отказались от предложения»;
  - `WITHDRAWN` из `ENRICHMENT`: `stage.index = 2`, этап 2 `cancelled`, этап 1 `done`, этапы 3–6 `pending`;
  - `at`: тест после цепочки явно проставляет событиям **разные** `created_at` и проверяет, что `at` текущего этапа = первое событие входа в этап (не последнее), а `at` у `cancelled` = последнее событие.
- `uv run ruff check . && uv run ruff format --check .` — зелёный.
- `git diff --exit-code contracts/openapi.json frontend/src/api/schema.d.ts` после пересборки — пусто.
- Вручную на стенде: вход `ip_good` → `POST /api/v1/applications` с `demo.app` → `GET /api/v1/applications/{id}` → вывод в PR.
- CI зелёный.

**Не делать:** не реализовывать submit, OTP, согласия, worker, оферту, отзыв (`withdraw` — B-09), возражение; не менять `conftest.py`, модели, миграции, `contracts/`; не отдавать внутренние поля.

### A-03 — Сквозные тесты персонажей через API · Катя · Облако: да · ≤3 ч
**Зачем.** Главное доказательство для жюри и для нас: на запущенном стенде каждый из 6 персонажей через настоящий HTTP получает ровно тот исход, что записан в `personas.json` (T12, T13), а клиент никогда не видит внутренних причин. Этими тестами тимлид проверяет вехи M1 и M2.

**Особенность.** Стенд с полным процессом появится только после B-06…B-09, а Docker у Кати нет. Поэтому тесты пишутся строго по контракту, а в приёмке два уровня:
- **офлайн-проверка** (`test_harness.py`) — всё, что можно проверить без стенда: тела запросов сверяются со схемами `openapi.json`, ожидания — с `personas.json`, логика ожидания — на подставном транспорте. Она запускается в CI;
- **прогон на стенде** (`test_personas.py`) — делает тимлид на вехах M1 и M2.

**Файлы:** `tests/e2e/api/conftest.py`, `tests/e2e/api/client.py`, `tests/e2e/api/flows.py`, `tests/e2e/api/test_personas.py`, `tests/e2e/api/test_harness.py`, `tests/e2e/api/README.md` (все новые). Больше ничего: ни `backend/`, ни `contracts/`, ни CI (CI добавит тимлид при слиянии).

**Читать:** `contracts/api.md`, `contracts/api-types.ts` (заявка клиента, действия клиента, андеррайтер), `contracts/openapi.json` (схемы запросов), `contracts/personas.json` (`staff`, `personas[].users`, `personas[].demo`), `contracts/codes.md` (разделы «Этапы ленты», «Пункты дозапроса», «Коды причин»), `docs/state-machine.md` (таблица переходов), `docs/test-scenarios.md` (S-01…S-10, S-17, S-18).

**Запуск** (без отдельного проекта, всё через `uv`):
```
uv run --no-project --python 3.12 --with pytest --with httpx --with jsonschema python -X utf8 -m pytest -q tests/e2e/api
```
Переменные: `E2E_BASE_URL` (по умолчанию `http://localhost:8080/api/v1`), `E2E_PASSWORD` (по умолчанию `demo2026`), `E2E_TIMEOUT` (секунды ожидания одного шага конвейера, по умолчанию 60).

**Сделать:**
1. **`client.py`** — тонкая обёртка над `httpx.Client` (`base_url`, `transport` можно подставить для офлайн-тестов): `login(login) -> token`, методы по путям `api.md`. Любой ответ не 2xx → `AssertionError` с текстом `Шаг <имя шага>: HTTP <код> <error.code> — <error.message>`. Так при прогоне на неготовом стенде сразу видно, на каком эндпоинте и с какой ошибкой (например `501 NOT_IMPLEMENTED`) всё остановилось.
2. **`flows.py`** — **чистые** функции, которые строят тела запросов из `personas.json` (их и проверяет офлайн-тест):
   - `create_body(persona, company_id)` — из `demo.app`: `product` → `product_code`, `term` → `term_months`;
   - `submit_body(persona, otp_id, code)` — `consents` из `demo.consents`;
   - `info_response_body(persona)` — из `demo.info_response`;
   - `approve_body(recommendation)` — решение андеррайтера `APPROVE` с суммой и сроком из `recommendation.offer`, комментарий «Одобрено по рекомендации системы после проверки»;
   - `expected_client(persona)` — что должен увидеть клиент: итоговое `state`, `offer` (`amount`, `term_months`, `rate`, `monthly_payment`) или `client_reason.code`;
   - `expected_bank(persona)` — что должен увидеть банк: `grade`, `score`, баллы 12 признаков, `outcome` или `route_reason`.

   Все ожидаемые числа берутся **только** из `demo.expected`, ничего не пересчитывать и не вписывать руками.
3. **Ожидание** `wait_state(client, app_id, *, leave={SUBMITTED, VALIDATION, ENRICHMENT, ASSESSMENT})`: опрашивать `GET /applications/{id}` раз в 1 с, пока состояние в `leave`. Не дождались за `E2E_TIMEOUT` → `AssertionError` с последним `state` и `timeline`.
4. **`test_personas.py`** — параметризация по `code` персонажа, вход под первым пользователем из `users` с `can_sign = true`. Общий путь: вход → `GET /me` (компания по `inn`) → `POST /applications` → `POST …/otp` (`purpose = CONSENTS`) → `POST …/submit` с `demo_code` → `wait_state`. Дальше:
   - `ip_good`, `ooo_load`, `ip_bad`, `ooo_aml` — сравнить с `expected_client` и `expected_bank`;
   - `ooo_gap` — сначала `INFO_REQUESTED`, в `info_request.items` есть `REVENUE_CONFIRM` → `POST …/info-response` → `wait_state` → сравнить с `demo.expected.after_info`;
   - `ooo_border` — `MANUAL_REVIEW`; банк видит `route_reason = GRADE_C` и рекомендацию из `demo.expected.recommendation`; андеррайтер (`staff[0]`) отправляет `approve_body` → клиент видит `OFFER_ISSUED` с офертой рекомендации.

   Сторона банка: вход `underwriter` → `GET /underwriting/applications/{id}` → последнее решение с `kind = AUTO`: `grade`, `score`, `{factor.code: factor.points}` = `points`. Для `ooo_aml` в `rules_fired` есть `SF_ADDITIONAL` с `effect = STOP`.

   Утечки: для **каждого** персонажа во **всех** клиентских ответах (`GET /applications/{id}`, `GET /applications?company_id=`) ключи JSON на любой глубине не содержат `score`, `grade`, `points`, `factors`, `rules_fired`, `internal_reasons`, `risk_flags`, `route_reason`, а сырой текст ответа не содержит `SF_ADDITIONAL`.

   Два полных пути до выдачи (S-08, S-18):
   - `test_full_path_ip_good` — принять оферту (`offer_version`) → для каждой своей неподписанной `party`: OTP (`purpose = OFFER` для `BORROWER_SIGNATORY`, `GUARANTEE` для `GUARANTOR`, с `party_id`) → `sign` → `wait_state(leave={SIGNING, SIGNED})` → `DISBURSED`;
   - `test_counter_signed_ooo_load` — то же для встречного `ooo_load`: директор подписывает и за компанию, и как поручитель.
5. **`conftest.py`**: если `GET {E2E_BASE_URL}/ready` не отвечает 200 за 3 с, тесты `test_personas.py` пропускаются одним `pytest.skip` с текстом «Стенд недоступен: <url>». На `test_harness.py` это не распространяется.
6. **`test_harness.py`** (офлайн, без сети):
   - для каждого персонажа тела `create_body`, `submit_body`, `info_response_body` (где есть), `approve_body` (для `ooo_border`) проходят `jsonschema`-проверку по схемам из `contracts/openapi.json`: `ApplicationCreate`, `SubmitRequest`, `InfoResponseRequest`, `UnderwriterDecisionRequest`, со ссылками `$ref`;
   - `expected_client` и `expected_bank` для каждого персонажа совпадают с полями `demo.expected` (`after_info` для `ooo_gap`, `recommendation` для `ooo_border`); покрыты все 6 персонажей;
   - `wait_state` на `httpx.MockTransport`: последовательность `SUBMITTED → VALIDATION → OFFER_ISSUED` возвращает `OFFER_ISSUED`; бесконечный `VALIDATION` при `E2E_TIMEOUT = 2` падает с текстом, где есть `VALIDATION`;
   - ошибка 501 с телом `ApiError` → `AssertionError`, в тексте имя шага, `501` и `NOT_IMPLEMENTED`;
   - skip-логика `conftest.py`: недоступный `/ready` (MockTransport с `ConnectError`) → skip с текстом про стенд.
7. **`README.md`** — 10–15 строк: что проверяют тесты, команда запуска, переменные, как читать падение («Шаг submit: HTTP 501…» = эндпоинт ещё не готов).

**Приёмка:**
- команда запуска выше, без стенда: `test_harness.py` — все прошли, 0 skipped; `test_personas.py` — 1 skip с текстом «Стенд недоступен». Вывод `-rA` вставить в PR;
- в `tests/e2e/api/` нет чисел из `demo.expected`, вписанных руками (проверка: `grep -E "77817|149264|51878|53875|2850000"` по папке — пусто);
- нет `skip`/`xfail`, кроме единственного skip в `conftest.py`; нет `noqa`;
- `ruff check tests/e2e && ruff format --check tests/e2e` (через `uv run --no-project --with ruff`) — чисто;
- в PR — таблица «персонаж → шаги → что проверяется», ссылки на сценарии S-xx из `docs/test-scenarios.md`.

**Не делать:** не трогать `backend/`, `frontend/`, `contracts/`, CI; не пересчитывать ожидания; не добавлять пауз длиннее 1 с; не создавать проект `pyproject.toml` для тестов.

### F-02 — Тема из токенов дизайна · Лана · Облако: нет (нужны скриншоты) · ≤2 ч
**Зачем.** Единый вид всех экранов в стиле, близком к Альфа-Банку, по токенам человека из Claude Design (D6). Цвета статусов одинаково читаются на ленте, в бейджах и у андеррайтера.

**Файлы:**
- `frontend/src/theme.ts` (заменить);
- `frontend/src/styles/tokens.css` (новый);
- `frontend/src/ui/status.ts` (новый);
- `frontend/src/main.tsx` — только импорты стилей и шрифта;
- `frontend/src/mocks/browser.ts` — только снять `TODO(lead)` (замечание ревью F-01);
- `frontend/eslint.config.js` — только добавить `public/mockServiceWorker.js` в `ignores`;
- `frontend/package.json`, `frontend/package-lock.json` — только `@fontsource/onest`;
- тесты: `frontend/src/theme.test.ts`, `frontend/src/ui/status.test.ts`.

**Читать:** `docs/design/tokens/theme.ts`, `docs/design/tokens/tokens.css` (источник правды), `docs/design/tokens-page/preview.png` (как выглядит), `docs/screens.md` §1–2 (рамка и правила текста), `contracts/codes.md` — раздел «Этапы ленты» (`timeline[].status`).

**Сделать:**
1. `theme.ts` = `docs/design/tokens/theme.ts` **без изменений значений**. Править можно только то, что не компилируется в Mantine 9.7.3 или противоречит `tsc`/`eslint`; каждую такую правку перечислить в PR с причиной.
2. `styles/tokens.css` = `docs/design/tokens/tokens.css` байт в байт; импорт в `main.tsx` после стилей Mantine.
3. Шрифт Onest — **локально** через `@fontsource/onest` (веса 400, 500, 600; импорт в `main.tsx`). Ссылок на `fonts.googleapis.com` в `frontend/` нет: стенд должен работать без интернета (T14).
4. `ui/status.ts` — единые цвета статусов для всех следующих экранов:
   - `stageStatusColor(status)`: `done` → `ok`, `current` → `flow`, `action_required` → `wait`, `failed` → `stop`, `cancelled` → `gray`, `pending` → `gray`;
   - `formatMoney(v: number): string` — через `theme.other.money`;
   - тип параметра — `components['schemas']['TimelineItem']['status']` из `schema.d.ts`, без строковых литералов вручную.
5. Цвета в компонентах — только через тему (`c="flow.7"`, `color="ok"`) или CSS-переменные `--cc-*`. Шестнадцатеричных цветов в `src/` нет, кроме `theme.ts` и `styles/tokens.css`.

**Приёмка:**
- `npm run lint && npm run typecheck && npm test && npm run build` — зелёный; `docker compose build web` — зелёный (или CI `compose-smoke`).
- `theme.test.ts`:
  - `primaryColor = "signal"`;
  - у `signal`, `ok`, `wait`, `flow`, `stop`, `gray` по 10 оттенков; опорные значения: `signal[6] = #DC2C26`, `ok[6] = #1E8E5A`, `wait[6] = #B78006`, `flow[6] = #4A6178`, `stop[6] = #B42318`, `gray[9] = #1F2329`. Импортировать `docs/` из `src/` нельзя: в Docker-сборке этой папки нет. Совпадение остальных значений с `docs/design/tokens/theme.ts` тимлид сверяет диффом;
  - `fontFamily` начинается с `'Onest'`;
  - `theme.other.money(1500000)` после замены всех пробельных символов на обычный пробел = `"1 500 000 ₽"`, а в исходной строке обычных пробелов (U+0020) нет.
- `status.test.ts` — все 6 значений `timeline[].status` → цвет по таблице п. 4; неизвестное значение не компилируется (проверка через `// @ts-expect-error` в тесте разрешена только здесь).
- `grep -rnE "#[0-9A-Fa-f]{6}\b" frontend/src --include=*.ts --include=*.tsx --include=*.css` — только `theme.ts`, `styles/tokens.css` и `theme.test.ts`.
- `grep -rn "fonts.googleapis" frontend/` — пусто.
- Скриншоты `/login` и `/app` в режиме MSW с новой темой — в PR (не коммитить в репозиторий).

**Не делать:** не менять значения токенов, не делать экраны (это F-03…F-08), не трогать `schema.d.ts`.

### B-06 — Код подтверждения, согласия, подача, просьба подписать · Аня · Облако: нет · ≤4 ч
**Зачем.** Подача заявки юридически осмысленна: согласия на ПДн и БКИ подписаны простой подписью кодом, с хэшем документа и журналом (F14, A5). Без права подписи нельзя ни подать, ни подписать (F14a). После подачи заявка встаёт в очередь worker'а (B-07).

**Начинать после слияния B-05** (`git ls-tree -r origin/main --name-only | grep backend/app/applications/state_machine.py` — непусто).

**Соглашение:** пользователь — через `client_user` / `authenticated_user` из `app/api/routes.py`; состояние меняет только `transition` из `app/applications/state_machine.py`; клиентский ответ строит только `to_client` из `app/applications/serializers.py`.

**Файлы:**
- `backend/app/signing/*.py` (новые: `otp.py`, `consents.py`, `submit.py`);
- `backend/app/models/process.py` — **только** новая модель `Otp`;
- `backend/alembic/versions/` — **одна новая** миграция (создана `autogenerate`, вычитана) только для таблицы `otp`;
- `backend/app/api/routes.py` — **только** тела `POST /applications/{id}/otp`, `/submit`, `/request-signature` и `Depends(...)`;
- `backend/tests/test_contract_paths.py` — **только** +3 пути в `IMPLEMENTED`, `len` = 12;
- `backend/tests/test_models_seed.py` — **только** добавить `"otp"` в ожидаемый набор таблиц `TABLES` (ответ на блокер 23.10);
- попутно, замечания ревью B-05: в `routes.py` добавить 404 в `errors(...)` у `POST /applications` и `GET /applications` и пересобрать `contracts/openapi.json` и `frontend/src/api/schema.d.ts` и 409 в `errors(...)` у `POST /applications/{id}/otp` (ответ на вопрос 23.10) — **это единственный разрешённый дифф контракта** (тимлид одобрил); `backend/app/applications/service.py` — явный список полей, которые правит PATCH (без `state`), и `created_at=datetime.now(UTC)` у события создания; тест в `test_applications_api.py`, что PATCH не может изменить `state`;
- тесты: `backend/tests/test_otp.py`, `backend/tests/test_submit.py` (новые).

**Читать:** `docs/state-machine.md` (строка `DRAFT → SUBMITTED`, раздел «Участники подписи»), `docs/data-model.md` (`party`, `consent`, `signature`, `job`, `otp`), `docs/assumptions.md` (A5), `contracts/api-types.ts` (`OtpRequest`, `OtpResponse`, `SubmitRequest`, коды ошибок), `contracts/codes.md` («Служебные перечисления», «Типы событий журнала», «Лента и действия по состояниям»), `backend/app/applications/`.

**Сделать:**
1. **Таблица `otp`:** `application_id`, `user_id`, `party_id` (nullable), `purpose` (`CONSENTS`/`OFFER`/`GUARANTEE`, CHECK), `code_hash`, `expires_at`, `attempts` (int, 0), `used_at` (nullable). Код хранится только хэшем (SHA-256 от `otp.id` + кода).
2. **`POST /applications/{id}/otp`** (`client_user`; заявка своей компании, иначе 404):
   - `CONSENTS` — только в `DRAFT` и только при `can_sign`;
   - `OFFER` — в `OFFER_ISSUED` или `SIGNING`, нужен `party_id` своей `party` с ролью `BORROWER_SIGNATORY`;
   - `GUARANTEE` — в `SIGNING`, нужен `party_id` своей `party` с ролью `GUARANTOR`.

   Нарушение: нет права подписи или `party` не своя → 403 `SIGN_NOT_ALLOWED` «Подписать может только сотрудник с правом подписи»; не то состояние → 409 `INVALID_TRANSITION`; нет нужного `party_id` → 422 `details.fields.party_id`.

   Код — 6 случайных цифр (`secrets`), срок 5 минут. Ответ: `otp_id`, `demo_code` (код при `DEMO_MODE=true`, иначе пустая строка), `expires_at`.
3. **Проверка кода** — функция `verify_otp(session, otp_id, code, *, application, user, purpose, party_id=None)` для B-06 и B-09:
   - чужой, не та цель, не та заявка, не тот `party_id`, уже использован, истёк → 422 `OTP_INVALID` «Код недействителен или истёк — запросите новый»;
   - неверный код → `attempts += 1` и 422 `OTP_INVALID` «Неверный код»; на 5-й неверной попытке код сгорает (`used_at` = сейчас);
   - верный → `used_at` = сейчас.

   Сравнение — `hmac.compare_digest`.
4. **`POST /applications/{id}/submit`** (`DRAFT → SUBMITTED`), всё в одной транзакции:
   - нет `can_sign` → 403 `SIGN_NOT_ALLOWED`; не `DRAFT` → 409 `INVALID_TRANSITION`; затем `verify_otp(purpose=CONSENTS)`;
   - `party`: `BORROWER_SIGNATORY` = текущий пользователь; для `OOO` — `GUARANTOR` = пользователь-учредитель компании с `share_pct > 50` (если такого нет — без поручителя, в PR отметить);
   - `consent` для `BORROWER_SIGNATORY`: `PDN`, `BKI` (`granted = true`), для `IP` — ещё `AUTO_DECISION` (`granted` = значение из запроса; для `OOO` не создаётся). `signed_at` = сейчас; `expires_at`: `BKI` и `PDN` — +1 год, `AUTO_DECISION` — `NULL`. `doc_hash` = SHA-256 от канонического JSON (`sort_keys=True`, `ensure_ascii=False`) `{type, application_id, number, company_inn, user_id, granted, signed_at}`;
   - на каждое согласие — `signature(object_type=CONSENT, object_id=consent.id, doc_hash, otp_verified_at)` и событие `CONSENT_SIGNED` (`reason_code = NULL`, `payload = {type, granted}`);
   - `transition(... SUBMITTED, actor_type=CLIENT)`, `submitted_at` = сейчас, `awaiting_signature = false`;
   - `job(step=VALIDATION, status=PENDING, attempts=0, run_after=сейчас)`;
   - ответ — `to_client` (лента показывает этап 1, `SUBMITTED`).
5. **`POST /applications/{id}/request-signature`:** у пользователя есть `can_sign` → 403 `SIGN_NOT_ALLOWED`; не `DRAFT` → 409; уже `awaiting_signature` → 200 без нового события; иначе `awaiting_signature = true` + событие `SIGNATURE_REQUESTED`. Версия заявки растёт.

**Приёмка:**
- `cd backend && uv run pytest -q -rA` с `TEST_DATABASE_URL` — зелёный, 0 skipped; миграция: `alembic downgrade -1 && alembic upgrade head` проходит.
- `test_otp.py`:
  - `demo_code` из 6 цифр при `DEMO_MODE=true`, пустой при `false`;
  - в таблице нет кода в открытом виде;
  - истёкший (тест сдвигает `expires_at`), повторный, чужой, другой цели, другой заявки → 422 `OTP_INVALID`;
  - 5 неверных попыток → 6-я с верным кодом тоже 422;
  - `CONSENTS` от `ooo_load_accountant` → 403; `OFFER` в `DRAFT` → 409.
- `test_submit.py`:
  - `ip_good`: после подачи `SUBMITTED`, 3 согласия (с `AUTO_DECISION`), 3 подписи, 3 события `CONSENT_SIGNED` + 1 `STATE_CHANGED`, 1 `party`, 1 `job(VALIDATION, PENDING)`; `doc_hash` пересчитывается тестом из записанных полей;
  - `ooo_load`: 2 согласия, 2 `party` (`BORROWER_SIGNATORY` и `GUARANTOR`, у обоих `user_id` директора);
  - неверный код → 422, и в БД ничего не создано (ни согласий, ни `party`, ни `job`, состояние `DRAFT`);
  - повторная подача → 409;
  - `ooo_load_accountant`: `submit` → 403; `request-signature` → 200, `awaiting_signature = true`, одно событие; повтор — 200 без второго события; затем директор видит `awaiting_signature = true` в списке и подаёт заявку → флаг сброшен;
  - `ooo_load` (`can_sign`) → `request-signature` → 403.
- `ruff check` и `ruff format --check` — чисто; в `openapi.json` и `schema.d.ts` после пересборки — только два добавленных ответа 404 и ответ 409 у `/otp`.
- Вручную на стенде: вход `ip_good` → создание → `otp` → `submit` → вывод `GET /applications/{id}` в PR. Если worker уже работает, заявка двинется дальше — это нормально.
- CI зелёный.

**Не делать:** не реализовывать worker, оферту, подпись `/sign` (B-09), согласия поручителя (они на шаге `SIGNING`, B-09); не менять `contracts/`.

### F-01 — Оболочка фронтенда · Лана · Облако: нет (ставит новые npm-пакеты, нужен скриншот) · ≤3 ч
**Зачем.** Каркас всех экранов: вход тестовыми учётками, маршруты по ролям, единая обработка ошибок, работа без бэкенда на моках (MSW) до готовности API.
**Файлы:** `frontend/src/**` (кроме `src/api/schema.d.ts` и `src/theme.ts`), `frontend/package.json`, `frontend/package-lock.json`, `frontend/public/mockServiceWorker.js`. Импорт из `../contracts` или `../../contracts` внутри `src/` **запрещён** (в Docker-сборке их нет). Данные персонажей для MSW копируются в `src/mocks/fixtures.ts`. Каталог продуктов в MSW (ответ на вопрос 23.10): `name`, `description`, `purposes`, `requires_guarantor_ooo` — из «Витрины продуктов» `contracts/codes.md`; границы — `EXPRESS` 300 000–5 000 000 ₽, 6–36 мес., `rate_from` 22.0; `WORKING_CAPITAL` 500 000–15 000 000 ₽, 3–24 мес., 21.0; `OVERDRAFT` 100 000–5 000 000 ₽, 12–12 мес., 24.0; `key_rate` 14.0, `key_rate_date` "2026-10-23". Пароль демо-учёток в MSW — `demo2026` (как `DEMO_PASSWORD` бэкенда).
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

- **B-07.**
  - Worker с `SELECT … FOR UPDATE SKIP LOCKED`, идемпотентные шаги.
  - Шаги: VALIDATION (через `decide()`) → ENRICHMENT (адаптеры `RegistryProvider` — уже есть из B-04, `BureauProvider`, `TaxProvider` — по его образцу в `app/integrations/`: HTTP к мокам и фейк для тестов; 3 повтора с паузой, затем `MANUAL_REVIEW` / `SOURCE_UNAVAILABLE`) → ASSESSMENT (`decide()`, запись `decision` с `inputs_snapshot`) → `OFFER_ISSUED` / `DECLINED` / `MANUAL_REVIEW` / `INFO_REQUESTED`.
  - `info-response` возвращает заявку в VALIDATION.
  - Демо-пауза 1–2 с на шаг.
  - Веха M1.
- **B-08.** Очередь (`QueueItem`, сортировка по ожиданию), `ApplicationBank` со всем протоколом, `POST /underwriting/{id}/decision` со всеми исходами; событие `UNDERWRITER_OVERRIDE` при расхождении с рекомендацией. Клиентская схема не содержит внутренних полей — тест сериализации для `ooo_aml`.
- **B-09.** Принять или отклонить оферту (`offer_version`), подпись участников (`party`), SIGNED → DISBURSED с графиком платежей, отзыв, возражение ИП (≤30 дней после авто-отказа).
- **B-10.** Планировщик истечений (`due_at`, `expires_at`), `POST /demo/time-shift`, `GET /bank/applications` (`Page`), загрузка `data/background.json` через тот же конвейер до `target_state`.
- **A-05.** Коллекция Bruno (`docs/api-collection/`): вход каждым персонажем и полный путь `ip_good` и `ooo_gap`. Проходит на запущенном стенде.
- **A-06.** Репетиция на чистом ПК строго по README; отчёт `docs/demo/rehearsal-T20.md`: время каждого шага, ошибки, скриншоты.
- **F-02…F-09** — по макетам человека (D6) и `screens.md`. Карточки уточняются после получения токенов (24.10 ~11:00).
