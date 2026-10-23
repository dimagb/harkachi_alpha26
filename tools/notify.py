"""Одностороннее уведомление «агент → Telegram» (D8, вариант A+). Только stdlib.

Запуск из корня репозитория:
    uv run --no-project python tools/notify.py START|DONE|QUESTION|BLOCKER <ID задачи> "<текст>"
    uv run --no-project python tools/notify.py chats      — показать chat_id групп, где есть бот (для настройки)

Настройки — файл .notify.env в корне клона (не коммитится) или переменные окружения:
    TG_BOT_TOKEN=...   токен бота от @BotFather
    TG_CHAT_ID=...     id группы (отрицательное число)
    AGENT_ID=backend   backend / frontend / analytics / lead
Если настроек нет или Telegram недоступен — печатает сообщение и выходит с кодом 1:
тогда оператор пересылает текст в группу вручную. Работу агента это не останавливает.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TYPES = {"START": "▶️", "DONE": "✅", "QUESTION": "❓", "BLOCKER": "⛔"}
MAX_LEN = 1000


def load_env():
    cfg = {}
    env_file = Path(__file__).resolve().parent.parent / ".notify.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"')
    for k in ("TG_BOT_TOKEN", "TG_CHAT_ID", "AGENT_ID"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def call(token, method, params):
    data = urllib.parse.urlencode(params).encode()
    url = f"https://api.telegram.org/bot{token}/{method}"
    with urllib.request.urlopen(url, data=data, timeout=15) as r:
        return json.loads(r.read().decode())


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    cfg = load_env()
    if len(argv) == 2 and argv[1] == "chats":
        if not cfg.get("TG_BOT_TOKEN"):
            print("Нет TG_BOT_TOKEN в .notify.env")
            return 1
        res = call(cfg["TG_BOT_TOKEN"], "getUpdates", {})
        seen = {}
        for u in res.get("result", []):
            chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat")
            if chat:
                seen[chat["id"]] = chat.get("title") or chat.get("username")
        for cid, title in seen.items():
            print(cid, title)
        if not seen:
            print("Чатов не найдено: напишите любое сообщение в группе с ботом и повторите.")
        return 0

    if len(argv) < 4 or argv[1].upper() not in TYPES:
        print(__doc__)
        return 2
    kind, task_id, text = argv[1].upper(), argv[2], " ".join(argv[3:])
    agent = cfg.get("AGENT_ID", "agent")
    msg = f"{TYPES[kind]} [{agent}] {kind} {task_id}: {text}"[:MAX_LEN]
    if not (cfg.get("TG_BOT_TOKEN") and cfg.get("TG_CHAT_ID")):
        print("Telegram не настроен (.notify.env). Перешлите оператору вручную:\n" + msg)
        return 1
    try:
        res = call(cfg["TG_BOT_TOKEN"], "sendMessage", {"chat_id": cfg["TG_CHAT_ID"], "text": msg})
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Telegram недоступен ({e}). Перешлите вручную:\n{msg}")
        return 1
    if not res.get("ok"):
        print(f"Ошибка Telegram: {res}. Перешлите вручную:\n{msg}")
        return 1
    print("Отправлено:", msg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
