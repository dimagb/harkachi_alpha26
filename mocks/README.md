# Мок-сервис внешних источников (A-01)

Из папки `mocks`: `uv sync`, затем `uv run uvicorn app.main:app --port 8001`.
Проверки: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q -rA`.

При старте загружаются `contracts/personas.json` и необязательный
`data/background.json`. `DATA_ROOT` по умолчанию — корень репозитория,
в Docker — `/`. Каталог `data` копируется в образ целиком.
Сервис работает без обращений к внешним источникам и без секретов.

| Метод и путь | Ответ |
| --- | --- |
| `GET /mock/v1/registry/{inn}` | Сведения ЕГРЮЛ/ЕГРИП |
| `POST /mock/v1/bki/report` | БКИ: тело `{"inn":"7706123455","kind":"INFO"}` |
| `GET /mock/v1/fns/check/{inn}` | Налоги, ФССП, банкротство |
| `GET /mock/v1/health` | `{"status":"ok"}` |

БКИ `INFO` возвращает только сводку; `FULL` — также кредиты и требует
непустого `consent_id` (иначе 403). Согласие здесь не проверяется по БД.
ИНН проверяются по длине и контрольным цифрам; ошибочный ИНН даёт 404.
Неизвестный валидный ИНН даёт детерминированную чистую компанию
(`random.Random(int(inn))`, без текущей даты и глобального генератора).
У ИП ИНН директора совпадает с ИНН ИП, у ООО вычисляется валидный ИНН из 12 цифр.
Ответы и ошибки соответствуют `contracts/external-mocks.md` и формату `ApiError`.

`MOCK_FAILURE_INN=7706123455,7702123454` включает 503 для всех трёх источников
этих компаний. `MOCK_LATENCY_MS` задаёт задержку источников (по умолчанию 300 мс,
для тестов 0); здоровье сервиса остаётся доступным. Настройки читаются при старте.

Проверка Docker из корня: `docker compose up -d --build --wait mocks`, затем
`docker compose exec mocks python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8001/mock/v1/registry/7706123455').read().decode())"`.
