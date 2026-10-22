# lead-kit — тимлид команды хакатона

Набор для запуска тимлида в Claude Code. В нём нет готового решения кейса, ролей исполнителей и методики работы команды: их тимлид вырабатывает вместе с вами по этапам. Начните с `SETUP.md`.

```
SETUP.md                          установка: репозиторий, Claude Code, плагины по этапам, первый запуск
TOOLS.md                          памятка: плагины, скиллы, субагенты — что тимлид вызывает сам, что делаете вы
CLAUDE.md                         тимлид: как думает и разговаривает, этапы и ворота, память, экономия лимита
prompts/lead-start.md             стартовый промт
.claude/agents/critic.md          независимый критик перед воротами
.claude/agents/researcher.md      веб-исследование на Sonnet с отчётом в docs/research/
.claude/agents/reviewer.md        ревью PR на этапе разработки
.claude/skills/product-brainstorming/  продуктовый спарринг (Anthropic, Apache-2.0)
.claude/skills/write-spec/        спецификации и PRD (Anthropic, Apache-2.0)
.claude/settings.json             запрет чтения секретов, разрешения на поиск и gh, хук STATE.md
.claude/hooks/state.sh            хук: на старте и после сжатия контекста подставляет docs/STATE.md
docs/case/case.md                 текст условий кейса (case.pdf рядом)
docs/case/webinar-qa-*.md         ответы организаторов
docs/case/clarifications.md       журнал уточнений, свежие важнее
docs/legal/research-prompts.md    промты правового исследования и сведения
docs/team/RESOURCES.md            ресурсы команды и инструменты — вход для этапа 4
drafts/telegram-bus/              заготовка связи через Telegram, не принята
```
