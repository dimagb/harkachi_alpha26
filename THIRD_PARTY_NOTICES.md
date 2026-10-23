# THIRD_PARTY_NOTICES

Сторонние компоненты, модели, данные и сервисы проекта (T6). Полный список зависимостей — lock-файлы `backend/uv.lock`, `mocks/uv.lock`, `frontend/package-lock.json`; итоговая сверка — перед сдачей (L-02).

## Материалы для разработки
| Компонент | Источник | Лицензия | Где |
| --- | --- | --- | --- |
| Скиллы superpowers (3 шт.) | https://github.com/obra/superpowers, коммит 2ce8aa1 | MIT, © 2025 Jesse Vincent | `.agents/skills/` |

## Заметные зависимости бэкенда
| Компонент | Лицензия | Зачем |
| --- | --- | --- |
| argon2-cffi 25.1.0 (+ argon2-cffi-bindings — MIT, cffi — MIT-0, pycparser — BSD-3-Clause) | MIT | хэш паролей (B-03) |

## Смоделированные интеграции
Внешние источники (БКИ, ЕГРЮЛ/ЕГРИП, ФНС) — моки с синтетическими данными (`mocks/`, `contracts/external-mocks.md`); реальные сервисы не используются.
