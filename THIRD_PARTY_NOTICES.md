# THIRD_PARTY_NOTICES

Сторонние компоненты, шрифты, изображения, данные и сервисы проекта (требование T6). Полный список зависимостей с версиями — lock-файлы `backend/uv.lock`, `mocks/uv.lock`, `frontend/package-lock.json`. Сверка лицензий всех рабочих зависимостей (инструменты `license-checker`, `pip-licenses`) — [docs/audit/licenses.md](docs/audit/licenses.md).

## Модели, датасеты и внешние сервисы

- **ML-моделей и LLM нет.** Оценка заявки — правила и балльная модель, написанные командой (`backend/app/decision/`, `contracts/decision_reference.py`).
- **Датасетов нет.** Все данные синтетические, сгенерированы командой: персонажи (`contracts/personas.json`), фоновые компании и заявки (`data/generate_background.py`, `data/background.json`). Совпадения ИНН, ОГРН, имён и названий с реальными лицами и компаниями случайны.
- **Внешних и платных сервисов нет.** БКИ, ЕГРЮЛ/ЕГРИП и ФНС (налоговый долг, ФССП, банкротство) смоделированы локальным сервисом `mocks/` с синтетическими ответами (`contracts/external-mocks.md`). Реальные источники не вызываются.

## Изображения и шрифты

| Материал | Источник | Лицензия / основание | Где |
| --- | --- | --- | --- |
| Логотип Альфа-Банка | официальный файл | использование разрешено организаторами хакатона (ответы вебинара, `docs/case/webinar-qa-2.md`, вопрос 6); товарный знак принадлежит АО «Альфа-Банк» | `frontend/src/assets/alfa-logo.svg` |
| Шрифт Onest 5.3.1 (`@fontsource/onest`) | [simpals/onest](https://github.com/simpals/onest), © 2021 The Onest Project Authors | SIL Open Font License 1.1 | встраивается в сборку фронтенда, CDN не нужен |

## Фронтенд (рабочие зависимости)

44 сторонних пакета: MIT — 40, BSD-3-Clause — 1, OFL-1.1 — 1 (Onest), 0BSD — 1 (`tslib`), MIT OR CC0-1.0 — 1 (`type-fest`, используется по MIT).

| Компонент | Версия | Лицензия | Зачем |
| --- | --- | --- | --- |
| React, React DOM | 19.3.1 | MIT | интерфейс |
| Mantine (`core`, `hooks`, `notifications`) | 9.7.3 | MIT | компоненты интерфейса и уведомления |
| TanStack Query | 5.104.5 | MIT | загрузка и кэш данных API |
| openapi-fetch | 0.17.0 | MIT | типизированный клиент API по контракту |
| tslib | 2.8.1 | 0BSD | служебная библиотека TypeScript |

Для разработки и проверок (в сборку не входят): Vite 8.3.5 (MIT), Vitest 5.0.5 (MIT), Testing Library (MIT), MSW 3.0.3 (MIT), Playwright 1.64.1 (Apache-2.0), axe-core (MPL-2.0, ставится только на время автообхода).

## Бэкенд и сервис внешних источников (рабочие зависимости)

Бэкенд — 35 пакетов: MIT — 19, BSD-3-Clause — 10, Apache-2.0 — 1–2, PSF-2.0 — 1, MIT-0 — 1, MPL-2.0 — 1, LGPL-3.0-only — 2. Сервис `mocks` — 19–20 пакетов: MIT, BSD-3-Clause, Apache-2.0, PSF-2.0 (без исключений).

| Компонент | Версия | Лицензия | Зачем |
| --- | --- | --- | --- |
| FastAPI | 0.161.1 | MIT | REST API (`api`, `mocks`) |
| Starlette | 1.9.0 | BSD-3-Clause | основа FastAPI |
| Uvicorn | 0.54.0 | BSD-3-Clause | веб-сервер приложения |
| Pydantic, pydantic-settings | 2.14.1, 2.16.1 | MIT | схемы API и настройки |
| SQLAlchemy | 2.1.6 | MIT | работа с БД |
| Alembic | 1.20.1 | MIT | миграции БД |
| psycopg, psycopg-binary | 3.3.6 | LGPL-3.0-only | драйвер PostgreSQL; используется без изменений как отдельная библиотека. Бинарная сборка содержит libpq (PostgreSQL License) и OpenSSL (Apache-2.0) |
| httpx | 0.28.1 | BSD-3-Clause | запросы `worker` к сервису внешних источников |
| PyJWT | 2.15.1 | MIT | токены входа |
| argon2-cffi 25.1.0 (+ argon2-cffi-bindings — MIT, cffi — MIT-0, pycparser — BSD-3-Clause) | 25.1.0 | MIT | хэш паролей |
| certifi | 2026.10.23 | MPL-2.0 | корневые сертификаты; используется без изменений |

Для разработки и проверок (в образы не входят): pytest (MIT), Ruff (MIT), Schemathesis (MIT), pip-audit (Apache-2.0), Bruno CLI (MIT, коллекция `docs/api-collection/`).

## Базовые Docker-образы

| Образ | Программа | Лицензия программы |
| --- | --- | --- |
| `postgres:16-alpine` | PostgreSQL 16 | PostgreSQL License |
| `nginx:alpine` | nginx | BSD-2-Clause |
| `python:3.12.15-slim` | CPython 3.12.15 | PSF-2.0 |
| `node:24.22.1-alpine` | Node.js 24.22.1 (только стадия сборки фронтенда) | MIT |

Указаны лицензии основных программ. Системные пакеты Alpine и Debian внутри образов распространяются под собственными лицензиями, их тексты — в самих образах.

## Материалы для разработки

| Компонент | Источник | Лицензия | Где |
| --- | --- | --- | --- |
| Скиллы superpowers (3 шт.) | https://github.com/obra/superpowers, коммит 2ce8aa1 | MIT, © 2025 Jesse Vincent | `.agents/skills/` |
