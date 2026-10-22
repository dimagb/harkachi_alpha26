#!/usr/bin/env python3
"""Проверка Telegram-части хаба на поддельном Bot API: python3 tools/agentbus/test_tg.py"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
calls, updates, lock = [], [], threading.Lock()
msg_id = [100]


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        try:
            self.wfile.write(b)
        except BrokenPipeError:  # хаб уже остановлен в конце теста
            pass

    def do_GET(self):
        if self.path.startswith("/file/"):
            b = b"%PDF-fake"
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)

    def do_POST(self):
        _, tok, method = self.path.split("/", 2)
        tok = tok[3:]
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        with lock:
            calls.append((tok, method, body))
        if method == "getUpdates":
            with lock:
                ups = list(updates); updates.clear()
            if not ups:
                time.sleep(0.3)
            return self._json({"ok": True, "result": ups})
        if method == "sendMessage":
            if tok == "bad":
                return self._json({"ok": False, "error_code": 403, "description": "bot is not a member"}, 403)
            msg_id[0] += 1
            return self._json({"ok": True, "result": {"message_id": msg_id[0]}})
        if method == "getFile":
            return self._json({"ok": True, "result": {"file_path": "documents/tz.pdf"}})
        return self._json({"ok": True, "result": True})


fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=fake.serve_forever, daemon=True).start()
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
env = dict(os.environ, BUS_DB=os.path.join(tmp, "t.db"), BUS_PORT=str(port), BUS_TOKEN="t",
           BUS_ENV_FILE=os.path.join(tmp, "none"), BUS_FILES=os.path.join(tmp, "files"),
           TG_API_BASE=f"http://127.0.0.1:{fake.server_port}", TG_BOT_TOKEN="main", TG_CHAT_ID="-100",
           TG_AGENT_BOTS='{"backend":"bk","ml":"bad"}', TG_MIN_INTERVAL="0.1", TG_BOARD_INTERVAL="0.5")
env.pop("AGENT_ID", None)
hub = subprocess.Popen([sys.executable, os.path.join(HERE, "hub.py")], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
cenv = dict(env, HUB_URL=f"http://127.0.0.1:{port}")
fails = 0


def bus(agent, *args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "bus.py"), "--as", agent, *args],
                       env=cenv, capture_output=True, text=True, cwd=tmp)
    return r.stdout.strip()


def sent(pred, timeout=6):
    end = time.time() + timeout
    while time.time() < end:
        with lock:
            hit = [c for c in calls if pred(c)]
        if hit:
            return hit
        time.sleep(0.1)
    return []


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

    bus("backend", "post", "STATUS", "Взял задачу про вход")
    h = sent(lambda c: c[1] == "sendMessage" and "вход" in c[2].get("text", ""))
    check("сообщение агента уходит от его личного бота без подписи",
          h and h[0][0] == "bk" and not h[0][2]["text"].startswith("["), h)

    bus("ml", "post", "STATUS", "Генерирую сиды")
    h = sent(lambda c: c[0] == "main" and "сиды" in c[2].get("text", ""))
    check("если личный бот не в группе — отправка от главного с подписью",
          h and h[0][2]["text"].startswith("[ML] "), h)

    h = sent(lambda c: c[1] == "pinChatMessage")
    check("доска создана и закреплена", bool(h), calls[-5:])
    bus("lead", "task", "frontend", "Экран статуса")
    h = sent(lambda c: c[1] == "editMessageText" and "#" in c[2].get("text", ""))
    check("доска редактируется при изменениях", bool(h), [c[1] for c in calls])

    with lock:
        updates.append({"update_id": 1, "message": {
            "message_id": 555, "chat": {"id": -100}, "from": {"id": 7, "username": "anna"},
            "caption": "@backend вот уточнённое ТЗ по подписи",
            "document": {"file_id": "F1", "file_name": "ТЗ подпись.pdf", "file_size": 9}}})
    time.sleep(1.5)
    out = bus("backend", "urgent")
    check("сообщение человека с файлом доступно агенту как срочное", "уточнённое ТЗ" in out and "fetch" in out, out)
    fid = out.split("fetch ")[1].split("]")[0] if "fetch " in out else "0"
    out = bus("backend", "fetch", fid)
    check("файл из Telegram скачивается агенту", "сохранено" in out, out)

    rid = bus("backend", "post", "QUESTION", "Код подписи 4 или 6 цифр?", "--to", "lead").split("#")[1]
    h = sent(lambda c: "Код подписи" in c[2].get("text", ""))
    tg_q = msg_id[0]
    with lock:
        updates.append({"update_id": 2, "message": {
            "message_id": 556, "chat": {"id": -100}, "from": {"id": 7, "username": "anna"},
            "text": "6 цифр", "reply_to_message": {"message_id": tg_q}}})
    time.sleep(1.5)
    out = bus("backend", "inbox")
    check("реплай человека в Telegram закрывает вопрос агента", "ANSWER human:anna→backend" in out, out)
finally:
    hub.terminate()
    fake.shutdown()

print("\nИтог:", "все проверки пройдены" if not fails else f"провалено {fails}")
sys.exit(1 if fails else 0)
