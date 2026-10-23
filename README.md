# Быстрый старт для разработчика

Нужны Git и запущенный Docker Desktop с Linux containers и Docker Compose v2. Из корня репозитория в PowerShell:

```powershell
docker compose up -d --build --wait
```

Файл `.env` не требуется. Откройте [http://localhost:8080](http://localhost:8080): появится «API: ok». Swagger: [http://localhost:8080/api/v1/docs](http://localhost:8080/api/v1/docs). Готовность БД: [http://localhost:8080/api/v1/ready](http://localhost:8080/api/v1/ready).

На хост опубликован только web. Если порт занят:

```powershell
$env:WEB_PORT = "8081"
docker compose up -d --build --wait
```

Настройки перечислены в `.env.example`; при необходимости скопируйте его в `.env`. При изменении учётных данных PostgreSQL обновите также `DATABASE_URL`. Значения по умолчанию предназначены для локального демо на синтетических данных. Пользователей и бизнес-таблиц каркас пока не создаёт.

```powershell
docker compose ps -a
docker compose logs -f api worker
docker compose up -d
docker compose down
```

Повторный запуск сохраняет данные и повторяет идемпотентные миграции. `docker compose down -v` удаляет локальную БД — используйте только для чистого прогона.

Для локальной разработки установите uv и Node 24.22.1. Python 3.12 uv загрузит сам. Проверки:

```powershell
cd backend
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m scripts.export_openapi
cd ../mocks
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pytest
cd ../frontend
npm ci
npm run gen:api
npm run lint
npm run typecheck
npm test
npm run build
cd ..
python -X utf8 contracts/decision_reference.py --write
```

API локально: из `backend/` — `uv run uvicorn app.main:app --reload --port 8000`; frontend: из `frontend/` — `npm run dev`. Vite проксирует `/api` на localhost:8000. Для `/ready` нужна доступная локальному процессу PostgreSQL и соответствующий `DATABASE_URL`; контейнерная БД на хост не публикуется. Моки: из `mocks/` — `uv run uvicorn app.main:app --port 8001`.

После изменения API выполните экспорт OpenAPI, затем `npm run gen:api`. Снимки фиксируются в Git и проверяются CI; вручную их не редактируют.
