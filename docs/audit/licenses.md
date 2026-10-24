# A-09b — лицензии рабочих зависимостей

Проверка 24.10.2026, `main` / `origin/main` / база ветки: `17d41c9`.
Это инвентаризация для `THIRD_PARTY_NOTICES`, который готовит тимлид.
Зависимости, манифесты и lock-файлы не изменялись.

## Инструменты и воспроизведение

Windows, Python 3.12.15, uv 0.13.5, Node.js 24.22.1, npm 11.19.1,
license-checker 25.0.1, pip-licenses 5.5.5. Временные инструменты не входят
в перечисленные ниже рабочие зависимости.

Frontend, из `frontend/`:

```powershell
npx --yes license-checker@25.0.1 --production --summary
npx --yes license-checker@25.0.1 --production --json
Get-Content node_modules/@fontsource/onest/LICENSE
```

Backend и mocks, по очереди из соответствующей папки:

```powershell
uv export --frozen --no-dev --no-hashes --output-file "$env:TEMP/a09b-requirements.txt"
$packages = Get-Content "$env:TEMP/a09b-requirements.txt" |
  Where-Object { $_ -match '^[a-zA-Z0-9]' } |
  ForEach-Object { ($_ -split '==')[0] }
uv run --frozen --no-dev --with pip-licenses pip-licenses --format=markdown --packages $packages
uv run --frozen --no-dev --with pip-licenses pip-licenses --format=json --packages $packages
```

`--packages` оставляет только пакеты из экспорта `--no-dev`: сам инструмент
и его зависимости не попадают в результат. Вывод markdown содержит 35 строк
backend и 19 строк mocks. Итоговые строки:

```text
backend: | websockets | 17.3 | BSD-3-Clause |
mocks:   | websockets | 17.3 | BSD-3-Clause |
pip-licenses 5.5.5
```

Состав Linux-контейнеров дополнительно проверен без установки пакетов внутрь:

```powershell
docker compose exec -T api /app/.venv/bin/python -c "import importlib.metadata as m,json; print(json.dumps([{'name':d.metadata['Name'],'version':d.version,'license':d.metadata.get('License-Expression') or d.metadata.get('License')} for d in m.distributions()]))"
docker compose exec -T mocks /app/.venv/bin/python -c "import importlib.metadata as m,json; print(json.dumps([{'name':d.metadata['Name'],'version':d.version,'license':d.metadata.get('License-Expression') or d.metadata.get('License')} for d in m.distributions()]))"
```

Итог: **35 пакетов backend, 20 пакетов mocks** в образах Linux. Отличия:
`uvloop==0.23.0` (MIT) присутствует только в Linux; `tzdata==2026.5`
(Apache-2.0) есть только в Windows backend. В Linux системная база часовых
поясов не является Python-пакетом.

## Frontend

Итог `license-checker --production --summary`:

```text
├─ MIT: 40
├─ OFL-1.1: 1
├─ UNLICENSED: 1
├─ BSD-3-Clause: 1
├─ 0BSD: 1
└─ (MIT OR CC0-1.0): 1
```

| Лицензия | Число пакетов |
| --- | ---: |
| MIT | 40 |
| BSD-3-Clause | 1 |
| OFL-1.1 | 1 |
| 0BSD | 1 |
| MIT OR CC0-1.0 | 1 |
| UNLICENSED — собственный корневой пакет | 1 |
| Всего, включая корень | 45 |
| Сторонних пакетов | 44 |

Пакеты вне буквального списка {MIT, BSD, Apache-2.0, ISC, PSF}:

| Пакет | Версия | Лицензия | Примечание для тимлида |
| --- | --- | --- | --- |
| @fontsource/onest | 5.3.1 | OFL-1.1 | Сохранить текст лицензии и copyright шрифта |
| tslib | 2.8.1 | 0BSD | Отдельное SPDX-обозначение, не подменено на BSD-3-Clause |
| type-fest | 5.10.0 | MIT OR CC0-1.0 | Альтернативная лицензия; MIT доступна как вариант |
| credit-cabinet | 0.1.0 | UNLICENSED | Собственный private-пакет, не сторонняя зависимость |

Onest: локальный файл `frontend/node_modules/@fontsource/onest/LICENSE`,
copyright 2021 The Onest Project Authors, SIL Open Font License 1.1.
Исходный проект указан в файле: [simpals/onest](https://github.com/simpals/onest).
При сборке получено 42 локальных `.woff`/`.woff2`; CDN для шрифта не нужен.

## Backend и mocks

`MIT License` сведено к MIT, `BSD License` у httpx — к BSD-3-Clause,
полная строка Mozilla — к MPL-2.0; SPDX MIT-0 оставлено отдельно.
PSF-2.0 и варианты BSD входят в соответствующие семейства списка карточки.

| Лицензия | Backend Windows | Backend Linux | Mocks Windows | Mocks Linux |
| --- | ---: | ---: | ---: | ---: |
| MIT | 18 | 19 | 11 | 12 |
| BSD-3-Clause | 10 | 10 | 6 | 6 |
| Apache-2.0 | 2 | 1 | 1 | 1 |
| PSF-2.0 | 1 | 1 | 1 | 1 |
| MIT-0 | 1 | 1 | 0 | 0 |
| MPL-2.0 | 1 | 1 | 0 | 0 |
| LGPL-3.0-only | 2 | 2 | 0 | 0 |
| Всего | 35 | 35 | 19 | 20 |

Пакеты вне списка карточки:

| Пакет | Версия | Где | Лицензия |
| --- | --- | --- | --- |
| certifi | 2026.10.23 | backend | MPL-2.0 |
| cffi | 2.1.1 | backend | MIT-0 |
| psycopg | 3.3.6 | backend | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | backend | LGPL-3.0-only |

У mocks исключений среди Python-пакетов не обнаружено.
`TODO(lead):` учесть эти четыре пакета в `THIRD_PARTY_NOTICES`, отдельно
проверить условия поставки бинарного psycopg и включённых в wheel библиотек.
Замена зависимостей в A-09b не выполнялась.

## Базовые Docker-образы

Теги зафиксированы из вывода сборки; версии runtime проверены командами:

```powershell
docker compose exec -T db postgres --version
docker compose exec -T web nginx -v
docker compose exec -T api /app/.venv/bin/python --version
```

| Образ | Программа и версия | Основная лицензия | Источник |
| --- | --- | --- | --- |
| postgres:16-alpine | PostgreSQL 16.15 | PostgreSQL License | [официальная лицензия](https://www.postgresql.org/about/licence/) |
| nginx:alpine | nginx 1.31.8 | BSD-2-Clause | [официальный текст](https://nginx.org/LICENSE) |
| node:24.22.1-alpine | Node.js 24.22.1, стадия сборки | MIT, дополнительные лицензии встроенных компонентов | [LICENSE версии](https://github.com/nodejs/node/blob/v24.22.1/LICENSE) |
| python:3.12.15-slim | CPython 3.12.15 | PSF-2.0, дополнительные лицензии встроенных компонентов | [официальная документация](https://docs.python.org/3.12/license.html) |

Итог runtime-команд: `postgres (PostgreSQL) 16.15`, `nginx/1.31.8`,
`Python 3.12.15`.

Это лицензии основных программ, а не единая лицензия всего Docker-образа.
Системные пакеты Alpine/Debian и встроенные библиотеки имеют собственные
лицензии; полная OS-инвентаризация не входит в карточку. PostgreSQL License
не входит буквально в список карточки и выделена отдельно. Node.js нужен
на стадии сборки, в конечном контейнере frontend работает nginx.

## Вопрос тимлиду

`TODO(lead):` включить перечисленные исключения, Onest и основные программы
образов в `THIRD_PARTY_NOTICES`; определить требуемый объём перечисления
системных и встроенных библиотек. Вопрос не блокирует измерения A-09b.
