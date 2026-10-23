# Окружение на ноутбуке участницы (Windows, PowerShell)

Делать один раз, до первой задачи. **Docker Desktop обязателен только у Ани** (и у человека). Лане и Кате — по желанию: стенд целиком проверяет CI. Если Docker не встал за 20 минут, не бороться, а написать в группу. Команды выполняются в **PowerShell**. Где написано «от администратора» — в PowerShell, запущенном от имени администратора.

## 1. Проверка: что уже стоит
Скопировать целиком и выполнить:
```powershell
foreach ($c in 'git','gh','docker','uv','node','npm','codex') {
  $p = Get-Command $c -ErrorAction SilentlyContinue
  if ($p) { "{0,-7} OK   {1}" -f $c, ((& $c --version 2>$null) | Select-Object -First 1) } else { "{0,-7} НЕТ" -f $c }
}
wsl --status
docker compose version
docker info --format "Docker Engine {{.ServerVersion}} работает"
gh auth status
```
Что должно получиться:
- у каждой программы стоит `OK`;
- `wsl --status` показывает версию 2;
- последняя строка `docker info` — «Docker Engine … работает»;
- `gh auth status` — «Logged in to github.com as <логин>».

Чего нет — ставим по шагу 2.

Python отдельно ставить не нужно: `uv` сам скачает нужную версию.

## 2. Установка недостающего
```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Docker.DockerDesktop -e
```
- **Docker Desktop нужен WSL 2.** Если `wsl --status` выдаёт ошибку, выполнить от администратора `wsl --install` и перезагрузить ноутбук. После установки запустить Docker Desktop из меню «Пуск», принять условия и дождаться надписи «Engine running». Если Docker пишет про виртуализацию, её нужно включить в BIOS — тогда позвать человека.
- **Codex CLI**, если Codex ещё не установлен: `npm install -g @openai/codex`, затем `codex` и войти своим аккаунтом ChatGPT.
- После установки **закрыть и заново открыть PowerShell**, иначе новые команды не найдутся. Затем повторить шаг 1.

## 3. GitHub и репозиторий
Репозиторий приватный (`dimagb/harkachi_alpha26`). Доступ у `manynya556`, `svinokun`, `katelishka` уже есть (проверено 23.10).
```powershell
gh auth login                      # GitHub.com → HTTPS → Login with a web browser
git config --global user.name  "Имя Фамилия"
git config --global user.email "почта-из-github"
cd $HOME\Projects                  # или любая папка без кириллицы и пробелов в пути
gh repo clone dimagb/harkachi_alpha26
cd harkachi_alpha26
```

## 4. Последняя проверка (после того как каркас слит в `main`)
```powershell
git pull
docker compose up -d --build --wait
docker compose ps                  # все сервисы healthy
start http://localhost:8080        # страница «API: ok»
```
Скриншот вывода `docker compose ps` и страницы — в Telegram-группу.

## 5. Настройка Codex: сеть и подтверждения
Без этого Codex не сможет ставить пакеты (`uv`, `npm`), открывать PR (`gh`) и писать в Telegram. Открыть файл настроек:
```powershell
New-Item -ItemType Directory -Force $HOME\.codex | Out-Null
notepad $HOME\.codex\config.toml
```
Вписать (если в файле уже что-то есть — добавить эти строки, не стирая остальное), сохранить, перезапустить Codex:
```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```
Что это даёт: Codex сам работает внутри папки проекта и ходит в сеть, а подтверждение спрашивает только для действий за её пределами. Когда Codex просит подтвердить команду, читать её: `git`, `gh`, `uv`, `npm`, `docker`, `python` внутри проекта — подтверждать; удаление файлов вне проекта, `git push --force` и всё непонятное — не подтверждать, написать в группу.

## 6. Codex Cloud — когда тебя нет за ноутбуком
Codex Cloud входит в Plus. Задача выполняется на серверах OpenAI, **ноутбук можно закрыть**, результат приходит готовым PR. Используй его, когда уходишь, а задача ещё не сделана: Аня 24.10 утром, Катя 25.10.
1. Один раз: зайти на chatgpt.com/codex своим аккаунтом, подключить GitHub и выбрать репозиторий `dimagb/harkachi_alpha26`. Если репозитория нет в списке, написать человеку: приложение ChatGPT для GitHub ставит владелец репозитория.
2. Один раз: создать окружение для репозитория и опубликовать его. В настройках окружения:
   - Codex сначала сам изучит репозиторий и предложит окружение. Дождись, пока он закончит, и открой страницу окружения: поля Repository, Network, **Install script**, Start skill, Access.
   - **Install script** — сверь с текстом ниже. В нём должны быть все три папки; если чего-то нет, замени текст целиком:
     ```
     curl -LsSf https://astral.sh/uv/install.sh | sh
     export PATH="$HOME/.local/bin:$PATH"
     (cd backend && uv sync) ; (cd mocks && uv sync) ; (cd frontend && npm ci)
     uv tool install pytest
     ```
   - **Network** → «Allow Codex to access internet» включено, Allow domains — **Package managers**. Без этого агент не поставит пакеты.
   - В отчёте настройки должно быть видно, что прошли `uv run pytest` в `backend/` и `mocks/` и `npm test` во `frontend/`. Затем **Publish** и дождаться «Environment published». Docker в облаке нет — это нормально.
3. Перед уходом: открыть задачу из `docs/TASKS.md`, у которой стоит пометка **«можно в облаке»**, вставить её стартовый промпт и запустить. Вернувшись — открыть результат, нажать «Create PR» и сообщить в группу.
- **В облаке нет Docker и базы данных**, поэтому туда — только задачи с этой пометкой (без БД: модель решения, проверки, генератор, компоненты интерфейса).
- Своим аккаунтом не делиться: задачу запускает только владелица аккаунта.

## 7. MCP для Codex (делать сейчас, 5 минут; PowerShell, не внутри Codex)
```powershell
codex mcp add context7 -- npx -y @upstash/context7-mcp          # всем: актуальная документация библиотек
codex mcp add playwright npx "@playwright/mcp@latest"           # только Лане: посмотреть экран в браузере
codex mcp list                                                  # должен показать context7 (и playwright у Ланы)
```
Скиллы ставить не нужно: три скилла из superpowers (`test-driven-development`, `systematic-debugging`, `verification-before-completion`) уже лежат в репозитории в `.agents/skills/`, Codex берёт их сам — на ноутбуке и в облаке. Других скиллов и плагинов не искать и не ставить. Скиллы `gh-fix-ci` и `gh-address-comments` по желанию: `$skill-installer gh-fix-ci` внутри Codex.

## 8. Уведомления в Telegram (`.notify.env`)
Человек создаёт бота и присылает каждой участнице токен и id чата личным сообщением, не в общий чат. В корне клона сначала исключить файл из git, затем создать его:
```powershell
Add-Content .git\info\exclude ".notify.env"
notepad .notify.env
```
Содержимое:
```
TG_BOT_TOKEN=<токен>
TG_CHAT_ID=<id группы>
AGENT_ID=<backend | frontend | analytics>
```
Проверка: `uv run --no-project python tools/notify.py START TEST "проверка связи"` — сообщение появилось в группе.
