# Промпт для Codex: каркас репозитория (задача T-00)

Кто запускает: человек на ноутбуке Ани, в корне свежего клона, Codex с доступом к сети. Ветка `chore/scaffold`, результат — один PR в `main`. Ревью делает тимлид.
Перед запуском: в клоне есть `.gitattributes` (LF) и `docs/team/` — сначала `git pull`. На ноутбуке установлены Docker Desktop (запущен), Git, `gh` (выполнен `gh auth login`), Python 3.12+, `uv`, Node LTS. Если чего-то нет, Codex останавливается и говорит, что поставить.

Текст ниже копируется в Codex целиком.

---

Ты собираешь **каркас** репозитория для хакатонного прототипа «Умный кредитный кабинет предпринимателя». Бизнес-логику не пишешь: только структуру, сборку, запуск и CI, на которые завтра трое агентов будут класть код. Важнее всего качество и воспроизводимость: жюри поднимет проект одной командой `docker compose up` на чистом Windows-ПК.

## Что прочитать (только это, экономь лимит)
- `docs/architecture.md`, разделы 1–4: стек, компоненты, практики.
- `contracts/api.md`, первые 5 строк: базовый путь `/api/v1`, формат.
- `contracts/api-types.ts`, строки 45–53: формат ошибки `ApiError`.
- `contracts/external-mocks.md`, первая строка раздела: базовый путь `/mock/v1`.
- `docs/requirements-checklist.md`, строки T2, T3, T13, T14, T20.

Актуальные версии библиотек и их API проверяй через MCP `context7`, если он подключён, а не по памяти. Особенно это касается Mantine 9 (какая версия React нужна), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Vite, openapi-typescript.

## Структура (создать ровно так)
```
backend/                 # сервис credit-core: api и worker из одного образа
  pyproject.toml, uv.lock, Dockerfile, alembic.ini
  alembic/env.py, alembic/versions/   # env читает DATABASE_URL; миграций с таблицами НЕТ
  app/main.py            # FastAPI, все маршруты под /api/v1
  app/config.py          # pydantic-settings
  app/db.py              # SQLAlchemy 2: engine, session, DeclarativeBase (без моделей)
  app/errors.py          # обработчики ошибок в формате ApiError
  app/logging.py         # JSON-логи + middleware X-Correlation-ID
  app/worker.py          # цикл-заглушка worker-а
  app/{auth,applications,pipeline,decision,underwriting,signing,disbursement,audit}/__init__.py  # пустые модули
  scripts/export_openapi.py   # пишет ../contracts/openapi.json из app (без запуска сервера)
  tests/test_health.py
mocks/                   # сервис external-mocks
  pyproject.toml, uv.lock, Dockerfile
  app/main.py            # FastAPI, все маршруты под /mock/v1
  tests/test_health.py
frontend/
  package.json, package-lock.json, Dockerfile, nginx.conf, .dockerignore, vite.config.ts, tsconfig*.json, eslint.config.js
  src/main.tsx, src/App.tsx, src/theme.ts, src/api/client.ts, src/api/schema.d.ts (сгенерирован)
data/README.md           # «здесь будет фоновый генератор (задача аналитики)»
tests/e2e/README.md      # «здесь будут сквозные тесты (задача аналитики)»
docker-compose.yml
.dockerignore            # корневой: контекст сборки api/worker/mocks — корень
.env.example
.github/workflows/ci.yml
README.md                # только раздел «Быстрый старт для разработчика», остальное позже
```

## Требования по частям

**backend**
- Python 3.12, менеджер `uv`, версии зафиксированы в `uv.lock`. Зависимости: fastapi, uvicorn[standard], pydantic v2, pydantic-settings, sqlalchemy 2 (psycopg 3), alembic. Для разработки: pytest, httpx, ruff.
- `GET /api/v1/health` → `{"status":"ok"}` без обращения к БД. `GET /api/v1/ready` → `{"status":"ok"}`, если `SELECT 1` в БД прошёл, иначе 503 в формате `ApiError`.
- Swagger UI — `/api/v1/docs`, схема — `/api/v1/openapi.json`.
- Ошибки: обработчики `HTTPException` и `RequestValidationError` возвращают `{"error":{"code","message","details"}}`. Для 422 код `VALIDATION_ERROR` и `details.fields` (поле → текст), коды и HTTP-статусы — из `api-types.ts`.
- Настройки (`config.py`): `DATABASE_URL`, `JWT_SECRET`, `JWT_TTL_HOURS=8`, `DEMO_MODE=true`, `MOCKS_URL`, `LOG_LEVEL=INFO`. У всех есть значения по умолчанию для локального запуска.
- Логи: одна строка JSON на событие (`ts`, `level`, `msg`, `correlation_id`, `path`, `status`, `duration_ms`). `X-Correlation-ID` из запроса берётся или генерируется и возвращается в ответе.
- `worker.py`: бесконечный цикл, раз в 5 с пишет в лог `worker heartbeat` и обновляет файл `/tmp/worker-heartbeat`. Корректно завершается по SIGTERM.
- Контейнер api при старте выполняет `alembic upgrade head`, потом uvicorn на порту 8000. Пустая цепочка миграций допустима, но команда должна проходить. Контейнер worker запускает `python -m app.worker`. Оба процесса работают не от root.
- `scripts/export_openapi.py` пишет `contracts/openapi.json` (отсортированные ключи, отступ 2, перевод строки в конце). Запусти скрипт и закоммить результат.

**mocks**
- Тот же стек, без БД. `GET /mock/v1/health` → `{"status":"ok"}`. Порт 8001. Других маршрутов **не делай** (это задача аналитики).

**frontend**
- React + TypeScript + Vite + Mantine 9 (`@mantine/core`, `@mantine/hooks`) + `@tanstack/react-query` + `react-router`. npm, `package-lock.json`.
- `src/theme.ts` — `createTheme` с основным красным цветом-заглушкой (Альфа-подобный, например `#EF3124`) и комментарием, что настоящая тема придёт из токенов дизайна.
- `src/api/schema.d.ts` генерируется скриптом `npm run gen:api` (`openapi-typescript ../contracts/openapi.json -o src/api/schema.d.ts`). `src/api/client.ts` — типизированный клиент (`openapi-fetch`) с базовым URL `/api/v1`.
- `App.tsx`: одна страница на Mantine — заголовок «Кредитный кабинет — каркас», запрос `/api/v1/health` через клиент и TanStack Query, бейдж «API: ok» или «API: недоступен».
- Скрипты: `dev` (proxy `/api` → `http://localhost:8000`), `build`, `lint`, `typecheck` (`tsc --noEmit`), `test` (vitest, один тест рендера App), `gen:api`.
- Dockerfile в два этапа: node собирает, `nginx:alpine` отдаёт статику. `nginx.conf` проксирует `/api/` → `http://api:8000`, для SPA `try_files $uri /index.html`.

**docker-compose.yml**
- Сервисы `db` (`postgres:16-alpine`, том `pgdata`, healthcheck `pg_isready`), `mocks`, `api`, `worker`, `web`.
- Для `api`, `worker` и `mocks` контекст сборки — **корень репозитория** (`context: .`, `dockerfile: backend/Dockerfile` или `mocks/Dockerfile`): завтра им понадобится `contracts/personas.json`. Корневой `.dockerignore` исключает `.git`, `node_modules`, `.venv`, `docs/`. У `web` контекст — `frontend/`.
- На хост открыт **только** `web`: `${WEB_PORT:-8080}:80`. Остальные доступны только внутри сети compose (меньше конфликтов портов у жюри).
- Healthcheck у каждого сервиса (worker — по свежести `/tmp/worker-heartbeat`). `depends_on` с `condition: service_healthy`: api и worker ждут db и mocks, web ждёт api.
- Всё работает **без файла `.env`**: значения по умолчанию задаются в compose (`${VAR:-default}`). `.env.example` перечисляет все переменные с комментариями.
- `docker compose up -d --build` с нуля укладывается в ~5 минут и потребляет меньше 1,5 ГБ ОЗУ в простое.

**CI (`.github/workflows/ci.yml`)** — на push в `main` и на каждый PR, отдельные jobs:
1. `backend`: `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest`.
2. `mocks`: то же самое.
3. `frontend`: `npm ci`, `lint`, `typecheck`, `test`, `build`.
   Также `npm run gen:api` и `git diff --exit-code src/api/schema.d.ts`: сгенерированный клиент совпадает со снимком.
4. `contracts`: (а) `cd backend && uv run python scripts/export_openapi.py`, затем `git diff --exit-code contracts/openapi.json` — снимок совпадает с кодом; (б) `python -X utf8 contracts/decision_reference.py --write`, затем `git diff --exit-code contracts/personas.json` — персонажи совпадают с эталоном.
5. `compose-smoke`: `docker compose up -d --build --wait`, затем `curl -f http://localhost:8080/api/v1/ready` и `curl -f http://localhost:8080/`, затем `docker compose down -v`.

## Границы — НЕ делай
- Не создавай таблицы, модели, эндпоинты, кроме health/ready, авторизацию, страницы, кроме одной, тексты для пользователя.
- Не меняй ничего в `docs/` и `contracts/`, кроме генерируемого `contracts/openapi.json`. Не создавай `AGENTS.md` и `CODEOWNERS` — их пишет тимлид.
- Не добавляй Redis, Celery, Kafka, Tailwind, shadcn, ORM-генераторы, LLM-библиотеки, платные сервисы.
- Не коммить `.env`, секреты, `node_modules`, `.venv`, `dist`.
- Если требование противоречит документации или не реализуется, не придумывай обход. Остановись и опиши проблему в PR.

## Как работать с git
`git switch -c chore/scaffold`. Делай небольшие осмысленные коммиты (backend, mocks, frontend, compose, ci). Затем `git push -u origin chore/scaffold` и `gh pr create --base main --title "Каркас репозитория (T-00)"`, в описании — отчёт ниже. Если CI красный, чини, пока не станет зелёным.

## Проверка перед «готово» (выполни сам и вставь вывод в PR)
1. `docker compose down -v` → `docker compose up -d --build --wait` → `docker compose ps`: все сервисы `healthy`.
2. `curl http://localhost:8080/api/v1/ready` → `{"status":"ok"}`. Страница `http://localhost:8080` показывает «API: ok». `http://localhost:8080/api/v1/docs` открывается.
3. `curl http://localhost:8080/api/v1/nope` → 404 в формате `ApiError`. В ответах есть заголовок `X-Correlation-ID`.
4. `docker compose stop worker`, затем `docker compose start worker`: worker снова `healthy`. `docker stats --no-stream`: сумма памяти меньше 1,5 ГБ.
5. Второй `docker compose up -d` без `down` ничего не ломает: миграции идемпотентны.
6. CI в PR зелёный.

## Отчёт в описании PR
Версии (Python, Node, ключевые библиотеки), дерево файлов, вывод проверок 1–5, что сделано иначе, чем написано здесь, и почему, открытые вопросы к тимлиду.
