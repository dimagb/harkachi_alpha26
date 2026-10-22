#!/usr/bin/env python3
"""
agentbus hub — единая шина для ИИ-агентов команды.

Telegram + SQLite + маленький HTTP API. Только стандартная библиотека Python 3.9+.

Как устроено:
  * Один «главный» бот читает группу (getUpdates может читать только один процесс,
    а боты по умолчанию не видят сообщения других ботов).
  * Сообщения агентов хаб публикует от имени личного бота агента (TG_AGENT_BOTS),
    если он задан, иначе от главного бота с подписью [BACKEND].
  * Хаб фильтрует, что показать каждому агенту, поэтому агент тратит токены
    только на адресные сообщения, а не на весь чат.
  * Закреплённая «доска» в группе показывает прогресс команды без спама.

Запуск:  python3 hub.py           (настройки в tools/agentbus/.env, см. .env.example)
Без TG_BOT_TOKEN хаб работает как локальная шина без Telegram.
"""
import hmac
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env(os.environ.get("BUS_ENV_FILE", os.path.join(HERE, ".env")))


def jenv(name):
    try:
        return json.loads(os.environ.get(name, "{}") or "{}")
    except json.JSONDecodeError:
        sys.exit(f"{name}: некорректный JSON")


AGENTS = [a.strip() for a in os.environ.get("BUS_AGENTS", "lead,backend,frontend,ml,ops").split(",") if a.strip()]
LEAD = os.environ.get("BUS_LEAD", "lead")
DB_PATH = os.environ.get("BUS_DB", os.path.join(HERE, "bus.db"))
FILES_DIR = os.environ.get("BUS_FILES", os.path.join(HERE, "files"))
BIND = os.environ.get("BUS_BIND", "127.0.0.1")
PORT = int(os.environ.get("BUS_PORT", "8787"))
TOKEN = os.environ.get("BUS_TOKEN", "")
TG_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_API = os.environ.get("TG_API_BASE", "https://api.telegram.org").rstrip("/")  # для тестов
TG_CHAT = os.environ.get("TG_CHAT_ID", "")
TG_ALLOWED = {int(x) for x in os.environ.get("TG_ALLOWED_USER_IDS", "").replace(" ", "").split(",") if x}
TG_TOPICS = {k: int(v) for k, v in jenv("TG_TOPICS").items()}
TOPIC_TO_AGENT = {v: k for k, v in TG_TOPICS.items() if k in AGENTS}
TG_AGENT_BOTS = {k: v for k, v in jenv("TG_AGENT_BOTS").items() if k in AGENTS and v}
TG_MIN_INTERVAL = float(os.environ.get("TG_MIN_INTERVAL", "3.5"))  # бот в группе: ~20 сообщений/мин
TG_BOARD = os.environ.get("TG_BOARD", "1") == "1"
BOARD_MIN_INTERVAL = float(os.environ.get("TG_BOARD_INTERVAL", "30"))
MAX_POST = int(os.environ.get("BUS_MAX_POST", "1500"))
TRUNC = int(os.environ.get("BUS_TRUNC", "500"))
MAX_FILE = 20 * 1024 * 1024  # предел Bot API на скачивание

# Порядок = приоритет в инбоксе
TYPES = ["BLOCKER", "ANSWER", "DECISION", "CONTRACT", "TASK", "QUESTION", "NOTE", "DONE", "STATUS", "FYI"]
PRIORITY = {t: i for i, t in enumerate(TYPES)}
TRACKED = {"TASK", "BLOCKER", "QUESTION"}          # имеют состояние open/closed
BROADCAST = {"DECISION", "CONTRACT", "TASK"}       # @all этих типов попадает во все инбоксы
LEAD_WATCH = {"BLOCKER", "QUESTION"}               # тимлид видит их от всех, даже не адресные
CLOSERS = {"DONE", "ANSWER"}                       # ответ на TRACKED закрывает его
URGENT = {"BLOCKER", "ANSWER", "DECISION", "CONTRACT"}  # + всё от людей: доставляется посреди задачи
# Адресат "people" — люди команды в Telegram (вопрос тимлида к людям); ответ реплаем вернётся автору.

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  sender TEXT NOT NULL,
  rcpt TEXT NOT NULL DEFAULT ',',
  type TEXT NOT NULL,
  text TEXT NOT NULL,
  reply_to INTEGER,
  ref TEXT,
  state TEXT,
  source TEXT NOT NULL DEFAULT 'agent',
  tg_id INTEGER,
  tg_sent INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reads(agent TEXT NOT NULL, msg_id INTEGER NOT NULL, PRIMARY KEY(agent, msg_id));
CREATE TABLE IF NOT EXISTS watches(agent TEXT NOT NULL, msg_id INTEGER NOT NULL, PRIMARY KEY(agent, msg_id));
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER NOT NULL,
  name TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS ix_tg ON messages(tg_id);
CREATE INDEX IF NOT EXISTS ix_reply ON messages(reply_to);
"""


class BusError(Exception):
    pass


def age(ts):
    s = int(time.time() - ts)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def rcpt_list(r):
    return [x for x in (r or "").split(",") if x]


class Bus:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()
        self.cv = threading.Condition(threading.RLock())

    # ---------- запись ----------
    def _agents(self, names, allow_all=True):
        out = []
        for r in names or ():
            r = r.strip().lower()
            if not r:
                continue
            if r not in AGENTS and not (allow_all and r in ("all", "people")):
                raise BusError(f"неизвестный адресат {r}")
            if r not in out:
                out.append(r)
        return out

    def add(self, sender, type_, text, rcpt=(), reply_to=None, ref=None, cc=(),
            source="agent", tg_id=None, tg_sent=0, check_sender=True):
        type_ = (type_ or "").upper()
        if type_ not in PRIORITY:
            raise BusError(f"неизвестный тип {type_}; допустимо: {', '.join(TYPES)}")
        if check_sender and sender not in AGENTS:
            raise BusError(f"неизвестный агент {sender}; допустимо: {', '.join(AGENTS)}")
        text = (text or "").strip()
        if not text:
            raise BusError("пустое сообщение")
        if source == "agent" and len(text) > MAX_POST:
            raise BusError(f"сообщение {len(text)} символов > {MAX_POST}. "
                           "Положи детали в репозиторий (docs/notes/...) и дай --ref")
        rc = self._agents(rcpt)
        cc = self._agents(cc, allow_all=False)
        with self.cv:
            if reply_to is not None and not self.db.execute(
                    "SELECT 1 FROM messages WHERE id=?", (reply_to,)).fetchone():
                raise BusError(f"нет сообщения #{reply_to}")
            if type_ == "DECISION" and source == "agent" and sender != LEAD:
                raise BusError("DECISION публикует только тимлид; предложи решение через QUESTION")
            state = "open" if type_ in TRACKED else None
            cur = self.db.execute(
                "INSERT INTO messages(ts,sender,rcpt,type,text,reply_to,ref,state,source,tg_id,tg_sent)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (time.time(), sender, "," + ",".join(rc) + ",", type_, text, reply_to, ref,
                 state, source, tg_id, tg_sent))
            mid = cur.lastrowid
            self.db.executemany("INSERT OR IGNORE INTO watches(agent,msg_id) VALUES(?,?)",
                                [(c, mid) for c in cc if c != sender])
            if reply_to is not None and type_ in CLOSERS:
                self.db.execute("UPDATE messages SET state='closed' WHERE id=? AND state='open'", (reply_to,))
            self.db.commit()
            self.cv.notify_all()
        return mid

    def close(self, mid, by):
        with self.cv:
            n = self.db.execute("UPDATE messages SET state='closed' WHERE id=? AND state='open'",
                                (mid,)).rowcount
            self.db.commit()
            self.cv.notify_all()
        return n

    def watch(self, agent, mid):
        if agent not in AGENTS:
            raise BusError(f"неизвестный агент {agent}")
        with self.cv:
            if not self.db.execute("SELECT 1 FROM messages WHERE id=?", (mid,)).fetchone():
                raise BusError(f"нет сообщения #{mid}")
            self.db.execute("INSERT OR IGNORE INTO watches(agent,msg_id) VALUES(?,?)", (agent, mid))
            self.db.commit()

    def attach(self, mid, name, path, size):
        with self.cv:
            fid = self.db.execute("INSERT INTO files(msg_id,name,path,size) VALUES(?,?,?,?)",
                                  (mid, name, path, size)).lastrowid
            self.db.commit()
        return fid

    def file(self, fid):
        with self.cv:
            return self.db.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()

    # ---------- чтение ----------
    def _relevant(self, agent):
        """Непрочитанные сообщения, которые касаются агента."""
        bc = ",".join(f"'{t}'" for t in BROADCAST)
        conds = [
            ("rcpt LIKE ?", f"%,{agent},%"),                                           # адресовано мне
            (f"(rcpt LIKE '%,all,%' AND type IN ({bc}))", None),                       # важное для всех
            ("reply_to IN (SELECT id FROM messages WHERE sender=?)", agent),           # ответы мне
            ("id IN (SELECT msg_id FROM watches WHERE agent=?)", agent),               # я в копии
            ("reply_to IN (SELECT msg_id FROM watches WHERE agent=?)", agent),         # итог того, за чем слежу
        ]
        if agent == LEAD:
            lw = ",".join(f"'{t}'" for t in LEAD_WATCH)
            conds.append((f"type IN ({lw})", None))
        where = " OR ".join(c for c, _ in conds)
        params = [p for _, p in conds if p is not None]
        sql = ("SELECT * FROM messages WHERE sender != ? "
               "AND id NOT IN (SELECT msg_id FROM reads WHERE agent=?) "
               f"AND ({where})")
        rows = self.db.execute(sql, [agent, agent] + params).fetchall()
        return sorted(rows, key=lambda r: (PRIORITY.get(r["type"], 99), r["id"]))

    def line(self, r, trunc=TRUNC):
        to = ",".join(rcpt_list(r["rcpt"])) or "-"
        text = r["text"].replace("\n", " / ")
        if trunc and len(text) > trunc:
            text = text[:trunc] + f" …(+{len(text) - trunc}, show {r['id']})"
        extra = ""
        if r["reply_to"]:
            extra += f" ↩#{r['reply_to']}"
        if r["ref"]:
            extra += f" [ref {r['ref']}]"
        if r["state"]:
            extra += f" ({r['state']})"
        files = self.db.execute("SELECT id,name,size FROM files WHERE msg_id=?", (r["id"],)).fetchall()
        tail = "".join(f" [файл {f['name']}, {f['size'] // 1024} КБ: fetch {f['id']}]" for f in files)
        return f"#{r['id']} {r['type']} {r['sender']}→{to} {age(r['ts'])}{extra}: {text}{tail}"

    def _take(self, agent, rows, limit, peek):
        shown = rows[:limit]
        if not peek:
            self.db.executemany("INSERT OR IGNORE INTO reads(agent,msg_id) VALUES(?,?)",
                                [(agent, r["id"]) for r in shown])
            self.db.commit()
        return [self.line(r) for r in shown], len(rows) - len(shown)

    def inbox(self, agent, limit=8, peek=False):
        if agent not in AGENTS:
            raise BusError(f"неизвестный агент {agent}")
        with self.cv:
            lines, rest = self._take(agent, self._relevant(agent), limit, peek)
        if not lines:
            return "Новых адресных сообщений нет."
        out = "\n".join(lines)
        if rest > 0:
            out += f"\n… ещё {rest} (менее срочных). Вызови inbox после текущей задачи."
        return out

    def urgent(self, agent, limit=5):
        """Только то, что стоит прочитать посреди задачи: сообщения людей и URGENT-типы. Пусто — ''."""
        if agent not in AGENTS:
            raise BusError(f"неизвестный агент {agent}")
        with self.cv:
            rows = [r for r in self._relevant(agent) if r["source"] == "human" or r["type"] in URGENT]
            lines, rest = self._take(agent, rows, limit, False)
        out = "\n".join(lines)
        if rest > 0:
            out += f"\n… ещё {rest} срочных — вызови inbox."
        return out

    def wait(self, agent, timeout=600, limit=8):
        deadline = time.time() + min(max(timeout, 1), 6 * 3600)
        with self.cv:
            while not self._relevant(agent):
                rem = deadline - time.time()
                if rem <= 0:
                    return f"Ничего нового за {int(timeout)} с. Продолжай другую работу."
                self.cv.wait(min(rem, 5))
            return self.inbox(agent, limit)

    def show(self, mid):
        with self.cv:
            r = self.db.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
            if not r:
                raise BusError(f"нет сообщения #{mid}")
            out = [self.line(r, trunc=0)]
            if r["reply_to"]:
                p = self.db.execute("SELECT * FROM messages WHERE id=?", (r["reply_to"],)).fetchone()
                if p:
                    out.insert(0, "в ответ на: " + self.line(p, trunc=200))
            for c in self.db.execute("SELECT * FROM messages WHERE reply_to=? ORDER BY id", (mid,)):
                out.append("  ответ: " + self.line(c, trunc=200))
        return "\n".join(out)

    def tasks(self, agent=None, include_all=False):
        with self.cv:
            q = "SELECT * FROM messages WHERE state='open'"
            p = []
            if agent and not include_all:
                q += " AND rcpt LIKE ?"
                p.append(f"%,{agent},%")
            rows = self.db.execute(q + " ORDER BY id", p).fetchall()
        if not rows:
            return "Открытых задач, вопросов и блокеров нет."
        return "\n".join(self.line(r, trunc=160) for r in rows)

    def _agent_state(self, a):
        st = self.db.execute(
            "SELECT * FROM messages WHERE sender=? AND type IN ('STATUS','DONE') ORDER BY id DESC LIMIT 1",
            (a,)).fetchone()
        open_tasks = self.db.execute(
            "SELECT id FROM messages WHERE state='open' AND type='TASK' AND rcpt LIKE ? ORDER BY id",
            (f"%,{a},%",)).fetchall()
        return st, [r["id"] for r in open_tasks]

    def digest(self):
        out = []
        with self.cv:
            for a in AGENTS:
                st, ids = self._agent_state(a)
                last = f"{st['type']} {age(st['ts'])} назад: {st['text'][:140]}" if st else "статусов не было"
                out.append(f"{a}: открытых задач {len(ids)}; {last}")
            blk = self.db.execute(
                "SELECT * FROM messages WHERE state='open' AND type IN ('BLOCKER','QUESTION') ORDER BY id").fetchall()
        if blk:
            out.append("Открытые блокеры и вопросы:")
            out += ["  " + self.line(r, trunc=160) for r in blk]
        else:
            out.append("Открытых блокеров и вопросов нет.")
        return "\n".join(out)

    def board(self):
        """Текст закреплённой доски. Без времени, чтобы правка была только при реальных изменениях."""
        lines = ["ДОСКА КОМАНДЫ", ""]
        with self.cv:
            for a in AGENTS:
                st, ids = self._agent_state(a)
                now = (f"{'готово' if st['type'] == 'DONE' else 'в работе'}: {st['text'][:110]}") if st else "—"
                tasks = f" | задачи: {', '.join('#' + str(i) for i in ids)}" if ids else ""
                lines.append(f"{a.upper()} — {now}{tasks}")
            blk = self.db.execute(
                "SELECT * FROM messages WHERE state='open' AND type IN ('BLOCKER','QUESTION') ORDER BY id").fetchall()
            done = self.db.execute("SELECT COUNT(*) FROM messages WHERE type='TASK' AND state='closed'").fetchone()[0]
            total = self.db.execute("SELECT COUNT(*) FROM messages WHERE type='TASK'").fetchone()[0]
        lines += ["", f"Задачи: закрыто {done} из {total}"]
        if blk:
            lines.append("Ждут ответа:")
            lines += [f"  #{r['id']} {r['type']} {r['sender']}→{','.join(rcpt_list(r['rcpt']))}: {r['text'][:90]}"
                      for r in blk]
        return "\n".join(lines)

    # ---------- Telegram ----------
    def parent_by_tg(self, tg_id):
        with self.cv:
            return self.db.execute("SELECT * FROM messages WHERE tg_id=?", (tg_id,)).fetchone()

    def next_unsent(self):
        with self.cv:
            return self.db.execute(
                "SELECT * FROM messages WHERE source='agent' AND tg_sent=0 ORDER BY id LIMIT 1").fetchone()

    def mark_sent(self, mid, tg_id, ok=True):
        with self.cv:
            self.db.execute("UPDATE messages SET tg_sent=?, tg_id=? WHERE id=?", (1 if ok else 2, tg_id, mid))
            self.db.commit()

    def kv_get(self, k, default=None):
        with self.cv:
            r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r["v"] if r else default

    def kv_set(self, k, v):
        with self.cv:
            self.db.execute("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", (k, str(v)))
            self.db.commit()


# ---------- разбор сообщений людей ----------
_TAG_RE = None
TYPE_RE = re.compile(r"(?<![\w])#(task|decision|answer|fyi|question|blocker|contract|note)\b", re.I)


def tag_re():
    global _TAG_RE
    if _TAG_RE is None:
        names = "|".join(re.escape(a) for a in AGENTS + ["all"])
        _TAG_RE = re.compile(rf"(?<![\w])[@#]({names})\b", re.I)
    return _TAG_RE


def tg_file_of(msg):
    """(file_id, имя, размер) вложения сообщения или None."""
    if msg.get("document"):
        d = msg["document"]
        return d["file_id"], d.get("file_name") or f"document_{msg['message_id']}", d.get("file_size", 0)
    if msg.get("photo"):
        p = max(msg["photo"], key=lambda x: x.get("file_size", 0))
        return p["file_id"], f"photo_{msg['message_id']}.jpg", p.get("file_size", 0)
    return None


def parse_human(bus, msg, download=None):
    """Превращает сообщение человека из Telegram в запись шины. Возвращает id или None."""
    text = (msg.get("text") or msg.get("caption") or "").strip()
    fmeta = tg_file_of(msg)
    if not text and not fmeta:
        return None
    frm = msg.get("from") or {}
    rcpt = [m.lower() for m in tag_re().findall(text)]
    tm = TYPE_RE.search(text)
    type_ = tm.group(1).upper() if tm else None
    reply_to = None
    rep = msg.get("reply_to_message")
    if rep:
        parent = bus.parent_by_tg(rep.get("message_id"))
        if parent:
            reply_to = parent["id"]
            if not rcpt and parent["sender"] in AGENTS:
                rcpt = [parent["sender"]]
            if type_ is None and parent["type"] in ("QUESTION", "BLOCKER"):
                type_ = "ANSWER"
    thread = msg.get("message_thread_id")
    if not rcpt and thread in TOPIC_TO_AGENT:
        rcpt = [TOPIC_TO_AGENT[thread]]
    if not rcpt:
        rcpt = [LEAD]  # тимлид разбирает всё неадресное
    sender = "human:" + str(frm.get("username") or frm.get("first_name") or frm.get("id") or "?")
    mid = bus.add(sender, type_ or "NOTE", text or "(вложение без подписи)", rcpt, reply_to=reply_to,
                  source="human", tg_id=msg.get("message_id"), tg_sent=1, check_sender=False)
    if fmeta and download:
        try:
            download(bus, mid, *fmeta)
        except Exception as e:  # вложение не должно ронять приём сообщений
            print(f"[tg] файл не скачан для #{mid}: {e}", file=sys.stderr)
    return mid


def safe_name(name):
    name = re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE).strip("._") or "file"
    return name[:120]


def tg_download(bus, mid, file_id, name, size):
    if size and size > MAX_FILE:
        bus.add("hub", "FYI", f"Файл {name} больше 20 МБ — положите его в репозиторий", check_sender=False)
        return
    res = tg_call("getFile", {"file_id": file_id})
    if not res.get("ok"):
        raise RuntimeError(res.get("description"))
    fp = res["result"]["file_path"]
    os.makedirs(FILES_DIR, exist_ok=True)
    path = os.path.join(FILES_DIR, f"{mid}_{safe_name(name)}")
    with urllib.request.urlopen(f"{TG_API}/file/bot{TG_TOKEN}/{fp}", timeout=120) as r, \
            open(path, "wb") as out:
        out.write(r.read(MAX_FILE + 1))
    bus.attach(mid, safe_name(name), path, os.path.getsize(path))


def format_tg(r, own_bot=False):
    to = ",".join(rcpt_list(r["rcpt"]))
    who = "" if own_bot else f"[{r['sender'].upper()}] "
    head = f"{who}{r['type']} #{r['id']}{' → ' + to if to else ''}"
    if r["state"] == "open":
        head += " (open)"
    body = r["text"]
    if r["ref"]:
        body += f"\nref: {r['ref']}"
    return (head + "\n" + body)[:4000]


def tg_call(method, params, timeout=65, token=None):
    url = f"{TG_API}/bot{token or TG_TOKEN}/{method}"
    data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "description": str(e)}
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return {"ok": False, "description": f"сеть: {e}"}


def tg_thread_for(r):
    rc = [x for x in rcpt_list(r["rcpt"]) if x != "all"]
    if len(rc) == 1 and rc[0] != LEAD and rc[0] in TG_TOPICS:
        return TG_TOPICS[rc[0]]
    return TG_TOPICS.get(r["sender"]) or TG_TOPICS.get("general")


def tg_sender_loop(bus):
    while True:
        r = bus.next_unsent()
        if not r:
            time.sleep(1)
            continue
        token = TG_AGENT_BOTS.get(r["sender"])
        params = {"chat_id": TG_CHAT, "text": format_tg(r, own_bot=bool(token)), "disable_web_page_preview": True}
        th = tg_thread_for(r)
        if th:
            params["message_thread_id"] = th
        if r["reply_to"]:
            with bus.cv:
                p = bus.db.execute("SELECT tg_id FROM messages WHERE id=?", (r["reply_to"],)).fetchone()
            if p and p["tg_id"]:
                params["reply_parameters"] = {"message_id": p["tg_id"], "allow_sending_without_reply": True}
        res = tg_call("sendMessage", params, token=token)
        if not res.get("ok") and token and res.get("error_code") != 429:
            # личный бот агента не в группе или без прав — публикуем от главного
            print(f"[tg] бот {r['sender']}: {res.get('description')}; отправляю от главного", file=sys.stderr)
            params["text"] = format_tg(r, own_bot=False)
            res = tg_call("sendMessage", params)
        if res.get("ok"):
            bus.mark_sent(r["id"], res["result"]["message_id"])
        elif res.get("error_code") == 429:
            time.sleep(int(res.get("parameters", {}).get("retry_after", 5)) + 1)
            continue
        else:
            print(f"[tg] не отправлено #{r['id']}: {res.get('description')}", file=sys.stderr)
            bus.mark_sent(r["id"], None, ok=False)
        time.sleep(TG_MIN_INTERVAL)


def tg_board_loop(bus):
    """Одно закреплённое сообщение, которое хаб редактирует, когда меняется прогресс."""
    last_text, last_edit = None, 0.0
    while True:
        time.sleep(5)
        text = bus.board()
        if text == last_text or time.time() - last_edit < BOARD_MIN_INTERVAL:
            continue
        mid = bus.kv_get("board_msg_id")
        stamp = time.strftime("%H:%M")
        body = f"{text}\n\nобновлено {stamp} · /digest — подробнее"
        ok = False
        if mid:
            res = tg_call("editMessageText", {"chat_id": TG_CHAT, "message_id": int(mid), "text": body})
            ok = res.get("ok") or "not modified" in str(res.get("description", ""))
        if not ok:
            params = {"chat_id": TG_CHAT, "text": body, "disable_notification": True}
            if TG_TOPICS.get("general"):
                params["message_thread_id"] = TG_TOPICS["general"]
            res = tg_call("sendMessage", params)
            if res.get("ok"):
                new_id = res["result"]["message_id"]
                bus.kv_set("board_msg_id", new_id)
                pin = tg_call("pinChatMessage", {"chat_id": TG_CHAT, "message_id": new_id,
                                                 "disable_notification": True})
                if not pin.get("ok"):
                    print(f"[tg] доску не закрепить (нужны права админа): {pin.get('description')}",
                          file=sys.stderr)
                ok = True
        if ok:
            last_text, last_edit = text, time.time()


HELP = ("Шина агентов. Адресуйте сообщения: @lead @backend @frontend @ml @ops @all.\n"
        "Тип хэштегом: #task #decision #answer #question #blocker #fyi.\n"
        "Реплай на сообщение агента уходит этому агенту. Без адреса пишется тимлиду.\n"
        "Файл или скриншот с подписью «@frontend …» тоже дойдёт до агента.\n"
        "/digest — сводка, /tasks — открытые задачи, /chatid — id чата и темы.")


def tg_poll_loop(bus):
    offset = int(bus.kv_get("tg_offset", "0"))
    while True:
        res = tg_call("getUpdates", {"offset": offset, "timeout": 50, "allowed_updates": ["message"]}, timeout=70)
        if not res.get("ok"):
            print(f"[tg] getUpdates: {res.get('description')}", file=sys.stderr)
            time.sleep(5)
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            bus.kv_set("tg_offset", offset)
            msg = u.get("message")
            if not msg:
                continue
            chat_id = str(msg.get("chat", {}).get("id"))
            frm = msg.get("from") or {}
            text = (msg.get("text") or "").strip()
            if text.startswith("/chatid"):
                tg_call("sendMessage", {"chat_id": chat_id,
                                        "text": f"chat_id={chat_id} thread_id={msg.get('message_thread_id')} "
                                                f"user_id={frm.get('id')}",
                                        **({"message_thread_id": msg["message_thread_id"]}
                                           if msg.get("message_thread_id") else {})})
                continue
            if not TG_CHAT:
                print(f"[tg] сообщение из чата {chat_id}; укажи TG_CHAT_ID", file=sys.stderr)
                continue
            if chat_id != str(TG_CHAT) or frm.get("is_bot"):
                continue
            if TG_ALLOWED and frm.get("id") not in TG_ALLOWED:
                continue
            cmd = text.split("@")[0].split()[0] if text.startswith("/") else ""
            try:
                if cmd in ("/digest", "/status"):
                    bus.add("hub", "FYI", bus.digest(), check_sender=False)
                elif cmd == "/tasks":
                    bus.add("hub", "FYI", bus.tasks(include_all=True), check_sender=False)
                elif cmd in ("/help", "/start"):
                    bus.add("hub", "FYI", HELP, check_sender=False)
                elif not cmd:
                    parse_human(bus, msg, download=tg_download)
            except BusError as e:
                print(f"[tg] {e}", file=sys.stderr)


# ---------- HTTP API ----------
def make_handler(bus):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _auth(self):
            if not TOKEN:
                return True
            if hmac.compare_digest(self.headers.get("X-Bus-Token", ""), TOKEN):
                return True
            self._send(401, {"ok": False, "error": "bad token"})
            return False

        def _send_file(self, fid):
            f = bus.file(fid)
            if not f or not os.path.exists(f["path"]):
                return self._send(404, {"ok": False, "error": f"нет файла {fid}"})
            with open(f["path"], "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("X-File-Name", urllib.parse.quote(f["name"]))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _route(self, method):
            u = urllib.parse.urlparse(self.path)
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query).items()}
            if u.path == "/health":
                return self._send(200, {"ok": True, "agents": AGENTS, "telegram": bool(TG_TOKEN),
                                        "agent_bots": sorted(TG_AGENT_BOTS)})
            if not self._auth():
                return
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length", "0") or 0)
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            try:
                if method == "POST" and u.path == "/post":
                    rt = body.get("reply_to")
                    mid = bus.add(body.get("sender", ""), body.get("type", ""), body.get("text", ""),
                                  body.get("to") or [], reply_to=int(rt) if rt else None, ref=body.get("ref"),
                                  cc=body.get("cc") or [])
                    return self._send(200, {"ok": True, "id": mid, "text": f"отправлено #{mid}"})
                if method == "POST" and u.path == "/close":
                    n = bus.close(int(body["id"]), body.get("by", ""))
                    return self._send(200, {"ok": True, "text": f"закрыто #{body['id']}" if n else "уже закрыто"})
                if method == "POST" and u.path == "/watch":
                    bus.watch(body.get("agent", ""), int(body["id"]))
                    return self._send(200, {"ok": True, "text": f"слежу за #{body['id']}"})
                if u.path == "/inbox":
                    return self._send(200, {"ok": True, "text": bus.inbox(
                        q.get("agent", ""), int(q.get("limit", 8)), q.get("peek") == "1")})
                if u.path == "/urgent":
                    return self._send(200, {"ok": True, "text": bus.urgent(q.get("agent", ""),
                                                                           int(q.get("limit", 5)))})
                if u.path == "/wait":
                    return self._send(200, {"ok": True, "text": bus.wait(
                        q.get("agent", ""), float(q.get("timeout", 600)), int(q.get("limit", 8)))})
                if u.path == "/show":
                    return self._send(200, {"ok": True, "text": bus.show(int(q["id"]))})
                if u.path == "/tasks":
                    return self._send(200, {"ok": True, "text": bus.tasks(q.get("agent"), q.get("all") == "1")})
                if u.path == "/digest":
                    return self._send(200, {"ok": True, "text": bus.digest()})
                if u.path == "/board":
                    return self._send(200, {"ok": True, "text": bus.board()})
                if u.path == "/file":
                    return self._send_file(int(q["id"]))
                return self._send(404, {"ok": False, "error": "not found"})
            except (BusError, KeyError, ValueError) as e:
                return self._send(400, {"ok": False, "error": str(e)})

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

    return H


def main():
    bus = Bus(DB_PATH)
    if BIND not in ("127.0.0.1", "localhost") and not TOKEN:
        sys.exit("BUS_TOKEN обязателен, если хаб слушает не только localhost")
    if TG_TOKEN:
        threading.Thread(target=tg_poll_loop, args=(bus,), daemon=True).start()
        if TG_CHAT:
            threading.Thread(target=tg_sender_loop, args=(bus,), daemon=True).start()
            if TG_BOARD:
                threading.Thread(target=tg_board_loop, args=(bus,), daemon=True).start()
    srv = ThreadingHTTPServer((BIND, PORT), make_handler(bus))
    print(f"agentbus hub: http://{BIND}:{PORT}  agents={AGENTS}  telegram={'on' if TG_TOKEN else 'off'}"
          f"  agent_bots={sorted(TG_AGENT_BOTS) or '-'}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
