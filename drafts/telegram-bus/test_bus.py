#!/usr/bin/env python3
"""Самопроверка шины без Telegram: python3 tools/agentbus/test_bus.py"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
env = dict(os.environ, BUS_DB=os.path.join(tmp, "t.db"), BUS_PORT=str(port), BUS_TOKEN="t",
           TG_BOT_TOKEN="", BUS_ENV_FILE=os.path.join(tmp, "none"), BUS_FILES=os.path.join(tmp, "files"))
for k in ("AGENT_ID", "AGENTBUS_IDLE_WAIT", "AGENTBUS_POLL_SEC"):
    env.pop(k, None)
hub = subprocess.Popen([sys.executable, os.path.join(HERE, "hub.py")], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
cenv = dict(env, HUB_URL=f"http://127.0.0.1:{port}")
fails = 0


def bus(agent, *args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "bus.py"), "--as", agent, *args],
                       env=cenv, capture_output=True, text=True, cwd=tmp)
    return r.returncode, r.stdout.strip()


def hook(agent, event, extra_env=None, stdin="{}"):
    e = dict(cenv, AGENT_ID=agent, **(extra_env or {}))
    r = subprocess.run([sys.executable, os.path.join(HERE, "hook.py"), event], env=e, input=stdin,
                       capture_output=True, text=True, cwd=tmp)
    return r.stdout.strip()


def check(name, cond, got=""):
    global fails
    print(("OK   " if cond else "FAIL ") + name + ("" if cond else f"\n     got: {got}"))
    fails += 0 if cond else 1


try:
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1); break
        except Exception:
            time.sleep(0.1)

    # --- базовая адресация ---
    _, out = bus("lead", "task", "backend", "Реализовать POST /applications", "--ref", "contracts/openapi.yaml")
    check("тимлид выдаёт задачу", out.startswith("отправлено #1"), out)
    bus("backend", "post", "STATUS", "Взял #1, ориентир 2 ч")
    bus("frontend", "post", "STATUS", "Делаю экран заявки")
    bus("ml", "post", "FYI", "Сиды обновлены")
    _, out = bus("frontend", "inbox")
    check("фронтенд не видит чужую задачу и статусы", "Новых" in out, out)
    _, out = bus("backend", "inbox")
    check("бэкенд видит свою задачу", "#1 TASK" in out and "STATUS" not in out, out)
    _, out = bus("backend", "inbox")
    check("повторный inbox пуст (прочитано)", "Новых" in out, out)

    _, out = bus("frontend", "post", "QUESTION", "Поле amount в копейках или рублях?", "--to", "backend")
    _, out_lead = bus("lead", "inbox")
    check("тимлид видит чужие вопросы, но не статусы", "QUESTION" in out_lead and "STATUS" not in out_lead, out_lead)
    _, out = bus("backend", "inbox")
    check("бэкенд видит вопрос к себе", "#5 QUESTION frontend→backend" in out, out)
    bus("backend", "answer", "5", "В копейках, int64")
    _, out = bus("frontend", "inbox")
    check("ответ приходит автору вопроса", "ANSWER backend→frontend" in out, out)
    _, out = bus("frontend", "tasks", "--all")
    check("вопрос закрыт после ответа", "#5" not in out, out)

    bus("backend", "done", "1", "POST /applications готов", "--ref", "PR #12")
    _, out = bus("lead", "inbox")
    check("тимлид получает DONE по своей задаче", "DONE backend→lead" in out, out)
    _, out = bus("lead", "tasks", "--all")
    check("задача закрыта", "#1 " not in out, out)

    bus("lead", "post", "DECISION", "Суммы во всех API в копейках", "--to", "all")
    bus("lead", "post", "STATUS", "Ревьюю PR", "--to", "all")
    _, out = bus("ml", "inbox")
    check("@all: решение видно всем, статус нет", "DECISION" in out and "STATUS" not in out, out)
    _, out = bus("backend", "post", "DECISION", "Хочу Kafka", "--to", "all")
    check("DECISION разрешён только тимлиду", "ошибка" in out, out)
    _, out = bus("backend", "post", "STATUS", "x" * 2000)
    check("длинные сообщения отклоняются", "ошибка" in out and "репозиторий" in out, out)
    _, out = bus("backend", "post", "STATUS", "привет", "--to", "qa")
    check("неизвестный адресат отклоняется", "ошибка" in out, out)

    for i in range(12):
        bus("lead", "post", "FYI", f"заметка {i}", "--to", "ml")
    bus("lead", "post", "BLOCKER", "Сломан docker-compose", "--to", "ml")
    _, out = bus("ml", "inbox", "--limit", "3")
    check("приоритет: блокер первым, остальное урезано", out.splitlines()[0].find("BLOCKER") > 0
          and "ещё 10" in out, out)
    bus("ml", "inbox", "--limit", "50")

    bus("frontend", "inbox")  # дочитать решение тимлида
    bus("ops", "inbox")
    t0 = time.time()
    _, out = bus("frontend", "wait", "--timeout", "2")
    check("wait возвращается по таймауту", "Ничего нового" in out and time.time() - t0 < 6, out)

    # --- подписки: копия задачи и итог ---
    _, out = bus("lead", "task", "backend", "Эндпоинт статуса заявки", "--cc", "frontend")
    tid = out.split("#")[1].split()[0]
    _, out = bus("frontend", "inbox")
    check("агент в копии видит задачу", f"#{tid} TASK" in out, out)
    bus("backend", "done", tid, "GET /applications/{id} готов", "--ref", "PR #20")
    _, out = bus("frontend", "inbox")
    check("агент в копии получает DONE", "DONE backend→lead" in out, out)
    _, out = bus("ops", "post", "QUESTION", "Какой порт у api?", "--to", "backend")
    qid = out.split("#")[1].split()[0]
    bus("ml", "watch", qid)
    bus("backend", "answer", qid, "8000")
    _, out = bus("ml", "inbox")
    check("watch: подписчик получает ответ", "ANSWER backend→ops" in out, out)

    # --- срочное посреди задачи ---
    for a in ("lead", "backend", "frontend", "ml", "ops"):
        bus(a, "inbox", "--limit", "50")
    bus("lead", "post", "FYI", "не срочно", "--to", "frontend")
    _, out = bus("frontend", "urgent")
    check("urgent молчит, когда срочного нет", out == "", out)
    bus("lead", "post", "BLOCKER", "Сборка web падает на main", "--to", "frontend")
    out = hook("frontend", "post-tool", {"AGENTBUS_POLL_SEC": "0"})
    ok = False
    try:
        j = json.loads(out); ok = "Сборка web падает" in j["hookSpecificOutput"]["additionalContext"]
    except Exception:
        pass
    check("хук post-tool подмешивает срочное как additionalContext", ok, out)
    out = hook("frontend", "post-tool", {"AGENTBUS_POLL_SEC": "0"})
    check("хук post-tool молчит повторно", out == "", out)
    bus("lead", "post", "BLOCKER", "ещё один", "--to", "frontend")
    out = hook("frontend", "post-tool", {"AGENTBUS_POLL_SEC": "3600"})
    check("хук post-tool соблюдает интервал опроса", out == "", out)
    out = hook("frontend", "post-tool", {"AGENTBUS_POLL_SEC": "0"},
               stdin=json.dumps({"agent_id": "x", "agent_type": "qa-e2e"}))
    check("хук post-tool не отдаёт сообщения субагенту", out == "", out)
    bus("frontend", "inbox", "--limit", "50")

    # --- дежурный режим (Stop) ---
    out = hook("backend", "stop", {"AGENTBUS_IDLE_WAIT": "0"})
    check("stop без дежурства не держит агента", out == "", out)
    t0 = time.time()
    out = hook("backend", "stop", {"AGENTBUS_IDLE_WAIT": "2"})
    check("stop отпускает агента по таймауту тишины", out == "" and time.time() - t0 < 8, out)
    threading.Timer(1.5, lambda: bus("lead", "task", "backend", "Добавь SSE для статуса")).start()
    out = hook("backend", "stop", {"AGENTBUS_IDLE_WAIT": "20"})
    ok = False
    try:
        j = json.loads(out); ok = j["decision"] == "block" and "SSE" in j["reason"]
    except Exception:
        pass
    check("stop будит агента новой задачей (decision: block)", ok, out)
    out = hook("backend", "session-start")
    check("session-start называет роль и входящие", "backend" in out and "docs/team/roles/backend.md" in out, out)

    # --- вложения ---
    sys.path.insert(0, HERE)
    os.environ.update(BUS_DB=os.path.join(tmp, "t.db"), BUS_ENV_FILE=os.path.join(tmp, "none"),
                      TG_TOPICS='{"frontend": 77}', BUS_FILES=os.path.join(tmp, "files"))
    import importlib
    import hub as H
    importlib.reload(H)
    b = H.Bus(os.path.join(tmp, "t.db"))

    def fake_download(bus_, mid, file_id, name, size):
        os.makedirs(H.FILES_DIR, exist_ok=True)
        path = os.path.join(H.FILES_DIR, f"{mid}_{H.safe_name(name)}")
        with open(path, "wb") as fh:
            fh.write(b"PNGDATA")
        bus_.attach(mid, H.safe_name(name), path, 7)

    m = H.parse_human(b, {"message_id": 3001, "caption": "@frontend кнопка съехала, см. скрин",
                          "photo": [{"file_id": "a", "file_size": 10}, {"file_id": "b", "file_size": 99}],
                          "from": {"username": "anna"}}, download=fake_download)
    _, out = bus("frontend", "inbox")
    check("скриншот с подписью доходит агенту с файлом", "кнопка съехала" in out and "fetch" in out, out)
    fid = out.split("fetch ")[1].split("]")[0]
    r = subprocess.run([sys.executable, os.path.join(HERE, "bus.py"), "--as", "frontend", "fetch", fid],
                       env=cenv, capture_output=True, text=True, cwd=tmp)
    saved = r.stdout.strip().split("сохранено: ")[-1].split(" (")[0]
    check("fetch скачивает вложение", os.path.exists(saved) and open(saved, "rb").read() == b"PNGDATA", r.stdout)

    # --- разбор сообщений людей ---
    q = b.add("backend", "QUESTION", "Какой срок по овердрафту?", ["lead"])
    b.mark_sent(q, 1001)
    m = H.parse_human(b, {"message_id": 2001, "text": "12 месяцев", "from": {"username": "anna"},
                          "reply_to_message": {"message_id": 1001}})
    r = b.db.execute("SELECT * FROM messages WHERE id=?", (m,)).fetchone()
    check("реплай человека уходит агенту как ANSWER", r["type"] == "ANSWER" and ",backend," in r["rcpt"], dict(r))
    m = H.parse_human(b, {"message_id": 2002, "text": "@frontend @ml #decision тёмную тему не делаем",
                          "from": {"username": "anna"}})
    r = b.db.execute("SELECT * FROM messages WHERE id=?", (m,)).fetchone()
    check("теги адресатов и типа", r["type"] == "DECISION" and r["rcpt"] == ",frontend,ml,", dict(r))
    m = H.parse_human(b, {"message_id": 2003, "text": "кнопка съехала", "message_thread_id": 77,
                          "from": {"username": "anna"}})
    r = b.db.execute("SELECT * FROM messages WHERE id=?", (m,)).fetchone()
    check("сообщение в теме агента уходит ему", r["rcpt"] == ",frontend,", dict(r))
    m = H.parse_human(b, {"message_id": 2004, "text": "жюри просит README", "from": {"username": "anna"}})
    r = b.db.execute("SELECT * FROM messages WHERE id=?", (m,)).fetchone()
    check("неадресное уходит тимлиду", r["rcpt"] == ",lead," and r["type"] == "NOTE", dict(r))

    # --- доска и подписи ---
    board = b.board()
    check("доска показывает всех агентов и счёт задач", all(a.upper() in board for a in H.AGENTS)
          and "Задачи: закрыто" in board, board)
    row = b.db.execute("SELECT * FROM messages WHERE sender='backend' LIMIT 1").fetchone()
    check("подпись агента без личного бота", H.format_tg(row).startswith("[BACKEND] "), H.format_tg(row))
    check("без подписи, если у агента свой бот", not H.format_tg(row, own_bot=True).startswith("["),
          H.format_tg(row, own_bot=True))
finally:
    hub.terminate()

print("\nИтог:", "все проверки пройдены" if not fails else f"провалено {fails}")
sys.exit(1 if fails else 0)
