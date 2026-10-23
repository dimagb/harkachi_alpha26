# Окружение на ноутбуке участницы (Windows, PowerShell)

Делать один раз, до первой задачи. Команды выполняются в **PowerShell**. Где написано «от администратора» — в PowerShell, запущенном от имени администратора.

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
