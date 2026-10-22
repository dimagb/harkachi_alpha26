# SETUP — запуск тимлида

Около 20 минут. Остальных агентов, их инструменты и связь через Telegram вы спроектируете вместе с тимлидом на этапе 4.

## 1. Репозиторий

1. Создайте приватный репозиторий на GitHub и сразу дайте доступ аккаунту жюри `alfa-hack-2026`.
2. Распакуйте архив в корень, закоммитьте в `main`.
3. Установите GitHub CLI и войдите: `gh auth login`. Тимлид будет смотреть PR и CI через `gh` — это дешевле по лимиту, чем MCP.

## 2. Claude Code

1. Установите Claude Code и запускайте на своём компьютере в корне репозитория: `claude`.
2. Модель тимлида — Opus: `/model opus`. Субагент `researcher` сам работает на Sonnet, чтобы экономить лимит.
3. Плагины — сейчас:
   ```
   /plugin install superpowers@claude-plugins-official
   /plugin install code-review@claude-plugins-official
   /plugin install commit-commands@claude-plugins-official
   ```
4. Плагины — позже, когда понадобятся (каждый добавляет постоянные токены в контекст):
   | Когда | Что | Команда |
   | --- | --- | --- |
   | Этап 3: выбор стека и библиотек | MCP `context7` (актуальная документация библиотек) | `npx ctx7 setup --claude` в терминале |
   | Этап 3–4: бриф дизайна, ревью интерфейса | `frontend-design` | `/plugin install frontend-design@claude-plugins-official` |
   | Этап 5: разработка | `security-guidance` (проверка правок на уязвимости; агентная проверка при коммитах расходует лимит) | `/plugin install security-guidance@claude-plugins-official` |
   | Этап 5–6: проверить прототип в браузере | Playwright CLI со скиллами | `npm install -g @playwright/cli@latest`, затем `playwright-cli install --skills` |
   | Этап 6: аудит безопасности перед сдачей | `trailofbits/skills` | `/plugin marketplace add trailofbits/skills`, затем `/plugin` → вкладка Discover → нужный плагин этого каталога |
5. При установке выбирайте **Install for you (user scope)**; если в конце написано `Run /reload-plugins to apply`, введите `/reload-plugins`. Проверка установленного — `claude plugin list`, стоимость в контексте — `claude plugin details <имя>`.
   Подробно о том, что тимлид вызывает сам, а что делаете вы, — в `TOOLS.md`.
6. Проверка: спросите тимлида «какие скиллы и субагенты тебе доступны?». В ответе должны быть `product-brainstorming`, `write-spec`, скиллы `superpowers` и субагенты `critic`, `researcher`, `reviewer`.

## 3. Первый запуск

При первом запуске Claude Code спросит, доверяете ли вы папке проекта, — ответьте «да». Без этого не сработает хук из `.claude/settings.json`, который после каждого сжатия контекста возвращает тимлиду `docs/STATE.md`.


Вставьте промт из `prompts/lead-start.md`. Тимлид перескажет задачу, назовёт противоречия в материалах и задаст вопросы. Дальше работайте по этапам: на каждых воротах он предложит варианты и спросит ваше решение.

Новая сессия: напишите «продолжаем» — тимлид прочитает `docs/STATE.md`.

## 4. Правовое исследование (параллельно)

Промты для Алисы AI, ChatGPT и Claude и промт сведения — в `docs/legal/research-prompts.md`. Итог положите в `docs/legal/legal-basis.md`, а исходные ответы — в `docs/legal/sources/`. Лучше успеть к этапу 1 («Исследование»).

## 5. Новые уточнения организаторов

Добавляйте сверху в `docs/case/clarifications.md` с датой и дословным текстом и скажите тимлиду «новое уточнение». Более свежее уточнение важнее старых ответов.
