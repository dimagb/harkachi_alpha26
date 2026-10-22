#!/usr/bin/env python3
"""
bus.py — клиент шины агентов. Только стандартная библиотека.

Настройки (переменные окружения или файл .agentbus.env в корне репозитория):
  AGENT_ID   lead | backend | frontend | ml | ops   (адресат people — люди в Telegram)
  HUB_URL    по умолчанию http://127.0.0.1:8787
  BUS_TOKEN  общий токен хаба

Команды:
  inbox [--limit N] [--peek]        адресные непрочитанные (помечает прочитанными)
  urgent                            только срочное (люди, блокеры, ответы, решения); пусто — ничего не печатает
  wait  [--timeout 600]             один блокирующий вызов до первого адресного сообщения
  post TYPE "текст" [--to a,b] [--cc c] [--reply ID] [--ref commit|PR|путь]
  done ID "итог" [--ref ...]        закрыть задачу и сообщить автору и подписчикам
  answer ID "ответ"                 ответить на вопрос или блокер
  task AGENT "текст" [--cc a,b]     (тимлид) выдать задачу; --cc получат итог
  watch ID                          получать итог по чужой задаче или вопросу
  fetch FILE_ID                     скачать вложение из Telegram в .agentbus/files/
  show ID                           полный текст и ветка
  tasks [--all]                     открытые задачи, вопросы, блокеры (мои или все)
  digest | board                    сводка по команде / текст доски
  close ID                          закрыть без сообщения
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def repo_root():
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=3).stdout.strip()
        return r or None
    except Exception:
        return None


def find_env():
    paths = []
    root = repo_root()
    if root:
        paths.append(os.path.join(root, ".agentbus.env"))
    d = os.getcwd()
    while True:
        paths.append(os.path.join(d, ".agentbus.env"))
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


find_env()
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8787").rstrip("/")
TOKEN = os.environ.get("BUS_TOKEN", "")


def _req(path, params=None, body=None):
    url = HUB + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    return urllib.request.Request(url, data=data, headers={"Content-Type": "application/json",
                                                           "X-Bus-Token": TOKEN})


def call(path, params=None, body=None, timeout=30):
    try:
        with urllib.request.urlopen(_req(path, params, body), timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return {"ok": False, "error": f"хаб недоступен ({HUB}): {e}", "offline": True}


def fetch(fid):
    try:
        with urllib.request.urlopen(_req("/file", {"id": fid}), timeout=120) as r:
            name = urllib.parse.unquote(r.headers.get("X-File-Name") or f"file_{fid}")
            data = r.read()
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: файла {fid} нет"}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return {"ok": False, "error": f"хаб недоступен ({HUB}): {e}", "offline": True}
    d = os.path.join(repo_root() or os.getcwd(), ".agentbus", "files")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, os.path.basename(name))
    with open(path, "wb") as fh:
        fh.write(data)
    return {"ok": True, "text": f"сохранено: {path} ({len(data) // 1024} КБ)"}


def csv(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(prog="bus.py", description="Клиент шины агентов")
    p.add_argument("--as", dest="agent", default=os.environ.get("AGENT_ID", ""))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("inbox"); s.add_argument("--limit", type=int, default=8); s.add_argument("--peek", action="store_true")
    sub.add_parser("urgent")
    s = sub.add_parser("wait"); s.add_argument("--timeout", type=int, default=600); s.add_argument("--limit", type=int, default=8)
    s = sub.add_parser("post"); s.add_argument("type"); s.add_argument("text")
    s.add_argument("--to", default=""); s.add_argument("--cc", default="")
    s.add_argument("--reply", type=int); s.add_argument("--ref")
    s = sub.add_parser("done"); s.add_argument("id", type=int); s.add_argument("text"); s.add_argument("--ref")
    s = sub.add_parser("answer"); s.add_argument("id", type=int); s.add_argument("text"); s.add_argument("--ref")
    s = sub.add_parser("task"); s.add_argument("to"); s.add_argument("text")
    s.add_argument("--cc", default=""); s.add_argument("--ref")
    s = sub.add_parser("watch"); s.add_argument("id", type=int)
    s = sub.add_parser("fetch"); s.add_argument("id", type=int)
    s = sub.add_parser("show"); s.add_argument("id", type=int)
    s = sub.add_parser("tasks"); s.add_argument("--all", action="store_true")
    sub.add_parser("digest")
    sub.add_parser("board")
    s = sub.add_parser("close"); s.add_argument("id", type=int)
    a = p.parse_args(argv)

    if a.cmd not in ("show", "digest", "board", "fetch") and not a.agent:
        print("agentbus: не задан AGENT_ID (в .agentbus.env или --as)")
        return 2

    def owner_of(mid):
        r = call("/show", {"id": mid})
        if not r.get("ok"):
            return None
        line = next((l for l in r["text"].splitlines() if l.startswith(f"#{mid} ")), "")
        try:
            return line.split(" ", 3)[2].split("→")[0]
        except IndexError:
            return None

    if a.cmd == "inbox":
        r = call("/inbox", {"agent": a.agent, "limit": a.limit, "peek": "1" if a.peek else "0"})
    elif a.cmd == "urgent":
        r = call("/urgent", {"agent": a.agent}, timeout=5)
        if r.get("ok") and not r.get("text"):
            return 0  # тишина — ноль токенов
    elif a.cmd == "wait":
        r = call("/wait", {"agent": a.agent, "timeout": a.timeout, "limit": a.limit}, timeout=a.timeout + 15)
    elif a.cmd == "post":
        to = csv(a.to)
        if not to and a.type.upper() in ("QUESTION", "BLOCKER"):
            to = ["people"] if a.agent == "lead" else ["lead"]
        r = call("/post", body={"sender": a.agent, "type": a.type, "text": a.text, "to": to,
                                "cc": csv(a.cc), "reply_to": a.reply, "ref": a.ref})
    elif a.cmd in ("done", "answer"):
        own = owner_of(a.id)
        to = [own] if own and not own.startswith("human:") and own not in (a.agent, "hub") else []
        r = call("/post", body={"sender": a.agent, "type": "DONE" if a.cmd == "done" else "ANSWER",
                                "text": a.text, "to": to, "reply_to": a.id, "ref": a.ref})
    elif a.cmd == "task":
        r = call("/post", body={"sender": a.agent, "type": "TASK", "text": a.text,
                                "to": csv(a.to), "cc": csv(a.cc), "ref": a.ref})
    elif a.cmd == "watch":
        r = call("/watch", body={"agent": a.agent, "id": a.id})
    elif a.cmd == "fetch":
        r = fetch(a.id)
    elif a.cmd == "show":
        r = call("/show", {"id": a.id})
    elif a.cmd == "tasks":
        r = call("/tasks", {"agent": a.agent, "all": "1" if a.all else "0"})
    elif a.cmd == "digest":
        r = call("/digest")
    elif a.cmd == "board":
        r = call("/board")
    elif a.cmd == "close":
        r = call("/close", body={"id": a.id, "by": a.agent})
    else:
        return 2

    if r.get("ok"):
        print(r.get("text", "ok"))
        return 0
    if r.get("offline"):
        if a.cmd == "urgent":
            return 0  # хук не должен шуметь, если хаб лежит
        # Не заставляем агента ретраить в цикле: работа важнее шины.
        print(f"agentbus: {r['error']}. Продолжай работу, отправь важное позже одним сообщением.")
        return 0 if a.cmd in ("inbox", "wait", "tasks", "digest", "board") else 3
    print(f"agentbus: ошибка: {r.get('error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
