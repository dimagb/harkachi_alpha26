# A-09b — результаты аудита и цифры для README

24.10.2026, база `17d41c9` (`main` и `origin/main` совпали).
Проверены зависимости, контракт, автономность, покрытие и задержки.
Приложение, контракты, манифесты и lock-файлы не изменялись.
Файлы A-09a не затронуты. Лицензии: [licenses.md](licenses.md).

## Итог

| Показатель | Результат |
| --- | --- |
| Backend: покрытие строк | **97%**, 2 609 из 2 690 строк |
| Backend: тесты | **1 376 passed**, 0 failed/skipped/xfail, 2 warnings |
| Frontend: покрытие строк | **97,3%**, 1 119 из 1 150 строк |
| Frontend: итоговые тесты | **292 passed**, 21 файл, 0 failed/skipped/xfail; 2 workers |
| p95 шести эндпоинтов | **8,905–91,914 мс**, таблица ниже |
| Подача → оферта ip_good | **9,657 с**, медиана трёх заявок |
| Известные уязвимости рабочих зависимостей | **0**, high/critical: **0/0** |
| Schemathesis | **1 уникальная находка 500**, 0 находок соответствия схемам ответов |
| Старт без скачивания образов | Прошёл после остановки всех сервисов |
| Полностью отключённая сеть | Ручная проверка человеком ещё не выполнена |

## Стенд, инструменты и ограничения

Windows, Docker Desktop, `http://localhost:8080` (не `127.0.0.1:8080`).
Инструменты: uv 0.13.5, Python 3.12.15, httpx 0.28.1, pytest 9.1.1,
pytest-cov 7.1.0, Ruff 0.17.2, Schemathesis 4.32.4, pip-audit 2.10.1,
Node.js 24.22.1, npm 11.19.1, Vitest / coverage-v8 5.0.5.
Лицензионные инструменты и их версии перечислены во втором отчёте.

```powershell
git switch main
git pull --ff-only
git log -1 --oneline main
git log -1 --oneline origin/main
git switch -c backend/A-09b-audit
docker compose up -d --build --wait
docker compose ps -a
```

Итог: api, worker, web, mocks, db — healthy; migrate — `Exited (0)`.
Перед итоговой приёмкой выполнены `git fetch origin` и `git rebase origin/main`:
база осталась `17d41c9`, `Current branch backend/A-09b-audit is up to date.`
Открытая страница и локальный `frontend/dist/index.html` ссылаются на одинаковые
`index-TpruFAc7.js` и `index-1wEPs_1d.css`.

В рабочей копии до аудита уже был недоступный для чтения каталог
`backend/.pytest-review-b7d2e366aae5442cbd535285e2f0fd0e/`.
Git не показал изменённых/неотслеживаемых файлов, но предупредил о каталоге;
содержимое его проверить не удалось. Каталог не изменялся и не удалялся.
Проверка форматирования всей папки тоже получила `Access denied` на нём;
проверка **всех 115 отслеживаемых Python-файлов backend** прошла.

У uv повреждён основной путь поиска managed Python 3.12. Для точной команды
приёмки применён отдельный временный каталог установки:

```powershell
$env:UV_PYTHON_INSTALL_DIR = "$env:TEMP/a09b-python"
$env:PYTHONUTF8 = '1'
```

Настройка UTF-8 также нужна Schemathesis при перенаправлении вывода в Windows:
первый запуск без неё завершился ошибкой кодировки самого инструмента ещё
до запросов. Эти попытки не включены в цифры двух завершённых прогонов.

## Фаззинг контракта

Схема получена со стенда: `http://localhost:8080/api/v1/openapi.json`.
Для каждой роли выполнена следующая команда, с отдельным токеном, полученным
через `POST /api/v1/auth/login`. Значения токенов не сохранены в отчёте.

```powershell
uvx schemathesis==4.32.4 --version
uvx schemathesis==4.32.4 run --help
# $token — access_token роли ip_good, затем underwriter.
uvx schemathesis==4.32.4 run http://localhost:8080/api/v1/openapi.json --origin http://localhost:8080 --header "Authorization: Bearer $token" --checks not_a_server_error,response_schema_conformance --phases fuzzing --max-examples 10 --max-time 240 --workers 1 --seed 909 --no-shrink --generation-database none --request-timeout 5 --report json --report-json-path "$env:TEMP/a09b-schemathesis-ROLE.json" --no-color
```

Флаги проверены по `--help` версии 4.32.4. В этой версии фаза fuzzing повторяет
сценарии до исчерпания бюджета времени: `--max-examples 10` не означает
10 запросов за весь прогон. Ограничение 240 секунд соблюдено обоими прогонами;
суммарно они заняли около восьми минут.

| Роль | Операции | Запросы | Находки 5xx | Находки схемы ответа | Время | Exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ip_good | 25/25 | 7 600 | 0 | 0 | 240,04 с | 0 |
| underwriter | 25/25 | 9 957 | 1 | 0 | 240,04 с | 1 |

Итоговые строки:

```text
ip_good: 7600 generated, 7600 passed; 3 warnings in 240.04s
underwriter: 9957 generated, 1 found 1 unique failure
ST101 Server error: 1
1 failure, 2 warnings in 240.04s
```

**Находка ST101**, роль underwriter: `GET /api/v1/bank/applications`.
Исходный запрос Schemathesis (заголовок Authorization опущен целиком):

```http
GET /api/v1/bank/applications?%C3%AE%C2%9AB%C3%AA%C2%AB%C3%BD%C2%93%1F%F1%98%A3%94=&%C2%95%C2%840L=k%F3%92%87%87%F3%A5%8D%B2%10%C3%9CY&%C2%95%C2%840L=q%28%C3%AA&%F3%BD%82%9B%C2%88a=%C2%9E%F3%AB%BB%AD%F0%B8%96%8Cq&%F3%BD%82%9B%C2%88a=%C3%8B&%F3%BD%82%9B%C2%88a=%F1%9A%A9%9D%E4%B1%A7%08%5Dh%C3%B9%C3%8Br&%C2%9B%00%C2%A3%0C%F2%BF%83%9B=&page=15052842692487972973998667464704&size=68&state=ENRICHMENT
```

Отдельно воспроизведён более короткий запрос с обычным токеном underwriter:

```http
GET /api/v1/bank/applications?page=15052842692487972973998667464704&size=68&state=ENRICHMENT
```

Оба вернули **500**, тело:

```json
{"error":{"code":"INTERNAL_ERROR","message":"Внутренняя ошибка сервера","details":{}}}
```

`TODO(lead):` выдать отдельную карточку на обработку чрезмерного `page`.
Ошибка не исправлялась. Название severity `critical` в Schemathesis относится
к ST101 и не прибавляется к числу CVE рабочих зависимостей.

**Ограничения:** в клиентском прогоне 6 операций возвращали только 401/403,
14 — преимущественно 404; у андеррайтера таких операций 16 и 3 соответственно.
Часть 403 ожидаема для противоположной роли. Случайные UUID не обеспечивают
прохождение существующих заявок; stateful-фаза не запускалась. Предупреждение
клиентского прогона о частых отказах валидации `/calculator` не является
падением выбранных проверок. Ноль находок схемы не доказывает полноту проверки
успешных ответов всех переходов. Матрица доступа и гонки относятся к A-09a.

## Уязвимости рабочих зависимостей

```powershell
# frontend/
npm audit --omit=dev --json
# backend/, затем mocks/; TARGET = backend или mocks
uv export --frozen --no-dev --no-hashes --output-file "$env:TEMP/a09b-TARGET-requirements.txt"
uvx pip-audit --version
uvx pip-audit -r "$env:TEMP/a09b-TARGET-requirements.txt" --format json --output "$env:TEMP/a09b-TARGET-audit.json"
```

Дополнительно из фактически установленных пакетов контейнеров сформированы
requirements без платформенных маркеров и выполнено:

```powershell
# SERVICE = api, затем mocks; TARGET = backend, затем mocks
docker compose exec -T SERVICE /app/.venv/bin/python -c "import importlib.metadata as m; print('\n'.join(sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())))"
uvx pip-audit -r "$env:TEMP/a09b-TARGET-linux-requirements.txt" --no-deps --disable-pip --format json --output "$env:TEMP/a09b-TARGET-linux-audit.json"
```

`--no-deps --disable-pip` здесь проверяет полный готовый набор версий Linux
без попытки установить Linux-only `uvloop` в Windows.

| Набор | Пакетов по отчёту | Все известные уязвимости | High | Critical | Пакет / исправленная версия |
| --- | ---: | ---: | ---: | ---: | --- |
| Frontend production | 45 prod в metadata npm | 0 | 0 | 0 | Нет находок |
| Backend Windows | 35 | 0 | 0 | 0 | Нет находок |
| Mocks Windows | 19 | 0 | 0 | 0 | Нет находок |
| Backend Linux | 35 | 0 | 0 | 0 | Нет находок |
| Mocks Linux | 20 | 0 | 0 | 0 | Нет находок |

Итог npm: `vulnerabilities: { high: 0, critical: 0, total: 0 }`.
Каждый pip-audit: `No known vulnerabilities found`, exit 0.
Это результат базы известных advisories на дату проверки, не аудит системных
пакетов Docker-образов и не гарантия отсутствия неизвестных уязвимостей.

## Автономность

```powershell
# frontend/
npm run build
# корень
rg -n 'https?://' backend/app
rg -o 'https?://[^\s"<>]+' frontend/dist
docker compose exec -T web sh -c 'ls /usr/share/nginx/html/assets/*woff* | wc -l'
docker compose stop
docker compose up -d --pull never --wait
docker compose ps -a
```

Поиск bundle дополнительно разобран по уникальным URL и контексту, включая
строки в шаблонных литералах JavaScript. В backend единственное совпадение —
локальное значение `mocks_url` в `app/config.py`; в Docker используется сервис
`mocks`. В dist найдены:

| URL | Назначение, не внешний запрос приложения |
| --- | --- |
| http://localhost | Базовый адрес в библиотеке роутинга |
| http://www.w3.org/1998/Math/MathML, /1999/xlink, /2000/svg, /XML/1998/namespace | Пространства имён DOM/SVG |
| https://react.dev/errors/ | Адрес документации в тексте ошибок React |
| https://mantine.dev/theming/colors/#primary-color | Адрес документации в сообщении Mantine |
| https://reactrouter.com/en/main/routers/picking-a-router. | Адрес документации в сообщении роутера |
| https://github.com/mswjs/msw | Комментарий в mockServiceWorker.js |

Внешних адресов загрузки шрифтов/ресурсов и вызовов внешнего API в проверенных
совпадениях не обнаружено. Onest поставляется локально: **42 файла шрифтов**
как в dist, так и в контейнере web.

Сборка: `built in 3.41s`, exit 0. После **реальной остановки** `--pull never`
поднял api, worker, web, mocks, db до healthy, migrate завершился с 0;
сообщений о скачивании не было. Последующий скрипт выполнил сценарий подачи
ip_good до оферты. Сеть при этих автоматических проверках оставалась включена.

**Ручная проверка для человека:** заранее собрать образы; выключить Wi-Fi и
Ethernet; выполнить `docker compose stop`, затем
`docker compose up -d --pull never --wait`; открыть `http://localhost:8080`;
войти как ip_good, подать заявку, дождаться оферты, принять и подписать до
выдачи; проверить вкладку Network браузера на внешние обращения; записать
результат и включить сеть. Этот ручной пункт передан человеку по карточке.

## Покрытие и проверки

Тесты backend выполнены в отдельной временной PostgreSQL 16, рабочая БД стенда
для них не использовалась. Контейнер тестовой БД после проверки остановлен.

```powershell
# корень: порт тестовой БД выбирается Docker, здесь получен 58401
docker run --rm -d --name harkachi-a09b-coverage-db -e POSTGRES_USER=audit -e POSTGRES_PASSWORD=audit -e POSTGRES_DB=audit -p 127.0.0.1::5432 postgres:16-alpine
docker port harkachi-a09b-coverage-db 5432
# backend/
$env:TEST_DATABASE_URL='postgresql+psycopg://audit:audit@localhost:58401/audit'
uv run --frozen --with pytest-cov pytest --cov=app --cov-report=term -q -rA --basetemp "$env:TEMP/a09b-pytest"
uv run --frozen --with ruff ruff check .
$files = git ls-files -- '*.py'
uv run --frozen --with ruff ruff format --check $files
# frontend/
npm i --no-save --package-lock=false @vitest/coverage-v8@5.0.5
npx vitest run --coverage
npx vitest run --coverage --coverage.reportOnFailure --maxWorkers 2
npm run lint
npm run typecheck
```

```text
Backend: TOTAL 2690 81 97%
1376 passed, 2 warnings in 490.49s (0:08:10)
Ruff: All checks passed!; 115 files already formatted
Frontend, первый запуск: 6 failed | 15 passed files; 8 failed | 284 passed tests
Frontend, итоговый запуск: Test Files 21 passed (21); Tests 292 passed (292)
Duration 86.38s
Statements: 90.22% (1486/1647)
Branches: 86.19% (1811/2101)
Functions: 90.08% (436/484)
Lines: 97.3% (1119/1150)
Frontend lint: 0 errors, 4 warnings; typecheck: exit 0
```

Backend warnings: deprecation httpx в Starlette TestClient и короткий HMAC-ключ
в тесте заведомо неверного HS384-токена. Frontend lint warnings относятся
к `react-refresh/only-export-components` в CompanyContext, BankLayout и Sources.

Первый frontend-прогон с покрытием выполнялся одновременно с другими
проверками; 8 упавших тестов перечислены ниже. Полный повтор с двумя workers
прошёл без изменения таймаутов, утверждений или исходников. Результат согласуется
с влиянием нагрузки/параллелизма, но причина окончательно не установлена.

- `src/App.test.tsx`: «вход ip_good открывает главную по роли».
- `src/screens/ApplicationCard.test.tsx`: «ставка 22 без лишних нулей».
- `src/screens/MyApplications.test.tsx`: «показывает пустой список ip_good и открывает подбор»; «показывает номер, продукт, сумму, этап, дату и открывает карточку».
- `src/screens/NewApplication.test.tsx`: «оборудование предлагает только экспресс, кассовый разрыв — три продукта».
- `src/screens/bank/UnderwriterCard.test.tsx`: «показывает эталонные группы, итог, рекомендацию и платёж»; «валидирует комментарий, встречное и максимум пяти вопросов».
- `src/screens/application/sections/DecisionSection.test.tsx`: «OFFER_ISSUED с офертой: параметры содержат пять строк исходной заявки без плиток».

## Задержки

Итоговый запуск завершён **24.10.2026 в 22:08 МСК**, после остановки фаззинга
и тестов и повторного старта стенда без скачивания образов.
Условия: **ноутбук, Docker Desktop, 1 пользователь, пауза конвейера 2 с
между шагами**. Фактическая настройка worker проверена: `pipeline_step_delay_sec = 2.0`.
В компании ip_good во время серии было 30 заявок; БД сохраняла прежние демоданные.

```powershell
uv run --no-project --python 3.12 --with httpx python -X utf8 scripts/audit/latency.py
```

Exit 0, Python 3.12.15 / httpx 0.28.1. Скрипт создаёт три последовательно
подаваемые заявки для времени до решения и четвёртую фоновую перед серией GET.
Оставляет их на стенде. Использует клиентскую и банковскую роли последовательно,
по одному запросу; исключает один прогрев каждого эндпоинта; снимает 50 запросов
с HTTP 200 на каждый; ошибки прерывают замер с ненулевым exit.
Фоновая заявка может завершиться в ходе серии: постоянная нагрузка не моделируется.

| Эндпоинт (префикс /api/v1) | Роль | n | p50, мс | p95, мс | max, мс |
| --- | --- | ---: | ---: | ---: | ---: |
| GET /applications/{id} | ip_good | 50 | 11,607 | 12,823 | 14,923 |
| GET /applications?company_id= | ip_good | 50 | 65,037 | 91,914 | 99,339 |
| GET /underwriting/queue | underwriter | 50 | 9,763 | 14,717 | 17,290 |
| GET /bank/applications | underwriter | 50 | 10,277 | 12,271 | 62,046 |
| GET /underwriting/applications/{id} | underwriter | 50 | 16,876 | 19,284 | 20,001 |
| POST /calculator | ip_good | 50 | 6,235 | 8,905 | 9,689 |

p50 — медиана, p95 — nearest rank: 48-й элемент отсортированной выборки из 50.
Калькулятор: EXPRESS, 1 000 000 рублей, 12 месяцев.
Заявка: та же сумма/срок, WORKING_CAPITAL, заявленная годовая выручка
12 000 000 рублей, все три согласия true.

Подача → OFFER_ISSUED: **9,674 / 9,485 / 9,657 с**, медиана **9,657 с**.
Таймер начинается перед POST submit; проверка состояния раз в 0,2 с добавляет
задержку обнаружения решения. Это наблюдение на данном стенде, не гарантия SLA.
Первый пробный запуск с одновременным аудитом дал p95 до 364,526 мс и медиану
9,8 с; в итоговую таблицу он не включён из-за другой фоновой нагрузки.

Скрипт дополнительно проверен командой с вручную заданной выборкой 1…50
(p50=25,5; p95=48; max=50), одиночной выборкой и транспортом httpx, возвращающим
500: `summary: PASS`, `non-2xx rejected: PASS`. Ruff для скрипта: `All checks
passed!`, `1 file already formatted`.

## Вопросы тимлиду

- `TODO(lead):` отдельная карточка на 500 банковского журнала при большом page.
- `TODO(lead):` учесть исключения лицензий из [licenses.md](licenses.md).
- `TODO(lead):` учитывать чувствительность frontend-тестов с покрытием
  к параллелизму; исходный красный прогон не скрыт и тесты не ослаблялись.
- Ручное отключение сети — действие человека, предусмотренное карточкой.

Уведомления QUESTION отправлены. Исправления найденного в приложении не делались.

## Доля автоматических решений (25.10, тимлид)

Стенд с нуля на `main` 5808672 (`docker compose down -v` → `up -d --build --wait`), в БД только 60 фоновых заявок B-10b, заявок персонажей нет. Первый выход каждой заявки из оценки по журналу `application_event`:

```sql
WITH first_exit AS (
  SELECT DISTINCT ON (e.application_id) e.application_id, e.from_state, e.to_state
  FROM application_event e
  WHERE e.from_state IN ('ASSESSMENT','ENRICHMENT')
    AND e.to_state IN ('OFFER_ISSUED','DECLINED','MANUAL_REVIEW')
  ORDER BY e.application_id, e.created_at)
SELECT from_state, to_state, count(*) FROM first_exit GROUP BY 1, 2 ORDER BY 1, 2;
```

Результат: `ASSESSMENT → OFFER_ISSUED` 19, `ASSESSMENT → DECLINED` 6, `ASSESSMENT → MANUAL_REVIEW` 11; сбоев источников (`ENRICHMENT → MANUAL_REVIEW`) нет. Из 36 заявок, дошедших до решения, **25 (69 %) решены без специалиста**, 11 (31 %) — у специалиста. Остальные 24 из 60 — черновики, отозванные до решения и т. п.

**Ограничение.** Распределение задано генератором синтетических данных (`data/generate_background.py`) и не является прогнозом доли автоматических решений на реальном потоке. Цифра показывает, что механизм работает и измеряется по журналу одним запросом; на реальных данных это метрика STP (доля заявок без ручного шага).
