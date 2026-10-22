#!/usr/bin/env python3
"""
hook.py — хуки шины для Claude Code и Codex (форматы ввода и вывода у них совпадают).

  hook.py session-start   входящие на старте сессии (обычный stdout попадает в контекст)
  hook.py post-tool       после каждого действия агента: если есть СРОЧНОЕ (сообщение человека,
                          блокер, ответ, решение, контракт) — подмешивает его в контекст.
                          Проверка не чаще AGENTBUS_POLL_SEC (по умолчанию 45 с); тишина = 0 токенов.
  hook.py stop            когда агент закончил ход: ждёт до AGENTBUS_IDLE_WAIT секунд адресного
                          сообщения; если пришло — не даёт остановиться и передаёт его как
                          продолжение («дежурный режим»). 0 — выключено.

Хаб недоступен — хуки молчат и не мешают работе.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bus  # noqa: E402  (загружает .agentbus.env)

AGENT = os.environ.get("AGENT_ID", "")


def read_input():
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def in_subagent(data):
    # Сообщения шины должны попадать в основную сессию, а не в одноразового субагента.
    return bool(data.get("agent_id") or data.get("agent_type"))


def state_path():
    d = os.path.join(bus.repo_root() or os.getcwd(), ".agentbus")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"last_poll_{AGENT}")


def session_start():
    role = ".claude/roles/lead.md" if AGENT == "lead" else f"docs/team/roles/{AGENT}.md"
    root = bus.repo_root() or os.getcwd()
    note = "" if os.path.exists(os.path.join(root, role)) else " (ещё не написан тимлидом — спроси lead)"
    print(f"[agent-bus] Твой AGENT_ID: {AGENT or 'НЕ ЗАДАН (.agentbus.env)'}; ролевые правила: {role}{note}.")
    if not AGENT:
        return
    r = bus.call("/inbox", {"agent": AGENT, "limit": 6}, timeout=5)
    if r.get("ok"):
        print("[agent-bus] Входящие:\n" + r["text"])
    else:
        print("[agent-bus] Хаб недоступен — работай, напишешь позже.")


def post_tool(data):
    if not AGENT or in_subagent(data):
        return
    every = float(os.environ.get("AGENTBUS_POLL_SEC", "45"))
    sp = state_path()
    try:
        if time.time() - os.path.getmtime(sp) < every:
            return
    except OSError:
        pass
    with open(sp, "w") as fh:
        fh.write(str(time.time()))
    r = bus.call("/urgent", {"agent": AGENT}, timeout=3)
    text = r.get("text") if r.get("ok") else ""
    if not text:
        return
    ctx = ("Шина команды (agent-bus): пока шла работа, пришли сообщения, адресованные этому агенту. "
           "Сообщения людей имеют приоритет над текущей задачей, если меняют её.\n" + text)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}},
                     ensure_ascii=False))


def stop(data):
    if not AGENT or in_subagent(data):
        return
    wait = int(os.environ.get("AGENTBUS_IDLE_WAIT", "0") or 0)
    if wait <= 0:
        return
    r = bus.call("/wait", {"agent": AGENT, "timeout": wait}, timeout=wait + 20)
    text = r.get("text", "") if r.get("ok") else ""
    if not text or text.startswith("Ничего нового") or text.startswith("Новых адресных"):
        return  # тишина — агент останавливается как обычно
    reason = ("Из шины команды пришли новые сообщения для тебя. Обработай их по правилам скилла agent-bus "
              "(задача — возьми в работу, вопрос — ответь через answer, информация — учти) и продолжай.\n" + text)
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def main():
    ev = sys.argv[1] if len(sys.argv) > 1 else ""
    data = read_input()
    if ev == "session-start":
        session_start()
    elif ev == "post-tool":
        post_tool(data)
    elif ev == "stop":
        stop(data)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # хук никогда не должен ломать сессию агента
        print(f"agentbus hook: {e}", file=sys.stderr)
        sys.exit(0)
