"""Read-only state-machine audit; run --self-test without Docker."""

import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL_STATES = {"DISBURSED", "WITHDRAWN", "EXPIRED"}
ACTORS = {
    "система": {"SYSTEM"},
    "клиент": {"CLIENT"},
    "клиент-ИП": {"CLIENT"},
    "подписант": {"CLIENT"},
    "подписант (+ поручитель)": {"CLIENT", "GUARANTOR"},
    "андеррайтер": {"UNDERWRITER"},
}


def parse_model(text):
    diagram = re.search(r"```mermaid\s+(.*?)```", text, re.DOTALL)
    table = re.search(
        r"^## Таблица переходов\s*$(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not diagram or not table:
        raise ValueError("Не найдены диаграмма или таблица переходов")
    states = set()
    for line in diagram.group(1).splitlines():
        edge = re.match(r"\s*(\[\*\]|[A-Z_]+)\s*-->\s*(\[\*\]|[A-Z_]+)", line)
        if edge:
            states.update(node for node in edge.groups() if node != "[*]")
    if not FINAL_STATES <= states or "SIGNED" not in states:
        raise ValueError("В диаграмме отсутствуют ожидаемые финальные состояния")
    model = {}
    for line in table.group(1).splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if cells[0] == "Из" or cells[0].startswith("---"):
            continue
        if len(cells) != 5 or cells[3] not in ACTORS:
            raise ValueError(f"Неизвестный формат строки или исполнитель: {line}")
        # TODO(lead): подтвердить, включает ли «* до SIGNED» состояние DECLINED.
        sources = (
            sorted(states - FINAL_STATES - {"SIGNED"})
            if cells[0] == "* до SIGNED"
            else re.split(r"\s*[/,]\s*", cells[0])
        )
        targets = re.split(r"\s*[/,]\s*", cells[1])
        for source in sources:
            for target in targets:
                if source not in states or target not in states:
                    raise ValueError(f"Неизвестное состояние: {source} → {target}")
                labels, actors = model.setdefault((source, target), (set(), set()))
                labels.add(cells[3])
                actors.update(ACTORS[cells[3]])
    if not model:
        raise ValueError("Таблица переходов пуста")
    return model, states


def parse_events(text):
    events = Counter()
    ignored = 0
    for line in text.splitlines():
        source, target, actor, count_text = line.split("|")
        count = int(count_text)
        if count <= 0:
            raise ValueError("Число событий должно быть положительным")
        if not source or not target or source == target:
            ignored += count
        else:
            events[source, target, actor] += count
    return events, ignored


def render_report(model, states, events, ignored):
    lines = [
        "| Из | В | Кто по модели | Кто в журнале | Событий | Покрытие |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    covered = 0
    for (source, target), (labels, actors) in sorted(model.items()):
        observed = {
            actor: count
            for (start, end, actor), count in events.items()
            if (start, end) == (source, target)
        }
        matches = sum(count for actor, count in observed.items() if actor in actors)
        covered += bool(matches)
        who = ", ".join(
            f"{actor}: {count}" for actor, count in sorted(observed.items())
        )
        lines.append(
            f"| {source} | {target} | {', '.join(sorted(labels))} | {who or '—'} | "
            f"{sum(observed.values())} | {'покрыто' if matches else 'не покрыто'} |"
        )
    lines += [
        "",
        f"**покрыто {covered} из {len(model)}**",
        "",
        "### Лишние переходы",
        "",
    ]
    extras = [
        (source, target, actor, count)
        for (source, target, actor), count in sorted(events.items())
        if (source, target) not in model or actor not in model[source, target][1]
    ]
    if extras:
        lines += ["| Из | В | Кто в журнале | Событий |", "| --- | --- | --- | ---: |"]
        lines += [f"| {s} | {t} | {a} | {n} |" for s, t, a, n in extras]
    else:
        lines.append("Нет.")
    dead_ends = sorted((states - FINAL_STATES) - {source for source, _ in model})
    lines += [
        "",
        "### Тупики",
        "",
        ", ".join(dead_ends)
        if dead_ends
        else "Нет: у каждого нефинального состояния есть выход.",
        "",
        (
            f"Событий без смены состояния или с пустой границей: {ignored}; "
            "они исключены из покрытия и лишних переходов."
        ),
    ]
    return "\n".join(lines)


def read_events():
    docker = shutil.which("docker")
    if not docker:
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / (
            "Docker/Docker/resources/bin/docker.exe"
        )
        if candidate.is_file():
            docker = str(candidate)
    if not docker:
        raise ValueError("Docker не найден: добавьте его в PATH")
    environment = os.environ.copy()
    environment.setdefault("COMPOSE_PROJECT_NAME", "harkachi_alpha26")
    query = (
        "BEGIN READ ONLY; "
        "SELECT COALESCE(from_state, ''), COALESCE(to_state, ''), actor_type, COUNT(*) "
        "FROM application_event GROUP BY from_state, to_state, actor_type "
        "ORDER BY from_state, to_state, actor_type; COMMIT;"
    )
    result = subprocess.run(
        [
            docker,
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-X",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "credit",
            "-d",
            "credit",
            "-At",
            "-F",
            "|",
            "-c",
            query,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=40,
        check=True,
    )
    return parse_events(result.stdout)


def main():
    started = time.monotonic()
    try:
        model, states = parse_model((ROOT / "docs/state-machine.md").read_text("utf-8"))
        events, ignored = read_events()
        print(f"Дата UTC: {datetime.now(UTC).isoformat()}")
        print(
            f"Проект Compose: {os.environ.get('COMPOSE_PROJECT_NAME', 'harkachi_alpha26')}"
        )
        print()
        print(render_report(model, states, events, ignored))
        print(f"\nВремя: {time.monotonic() - started:.2f} с")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Проверка не выполнена: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        return 1


class CoverageChecks(unittest.TestCase):
    """Catch lost alternatives, false coverage, and hidden dead ends."""

    fixture = """## Диаграмма
```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SUBMITTED: причина HIGH_LOAD не состояние
    SUBMITTED --> SIGNED
    SIGNED --> DISBURSED
    DECLINED --> [*]
    WITHDRAWN --> [*]
    EXPIRED --> [*]
```
## Таблица переходов
| Из | В | Триггер | Кто | Условие |
| --- | --- | --- | --- | --- |
| DRAFT / SUBMITTED | SIGNED / DECLINED | action | подписант (+ поручитель) | — |
| * до SIGNED | WITHDRAWN | action | клиент | — |
| DRAFT | WITHDRAWN | action | клиент | duplicate |
"""

    def test_alternatives_wildcard_and_duplicate(self):
        model, states = parse_model(self.fixture)
        self.assertEqual(len(model), 7)
        self.assertIn(("DECLINED", "WITHDRAWN"), model)
        self.assertNotIn(("SIGNED", "WITHDRAWN"), model)
        self.assertNotIn(("EXPIRED", "WITHDRAWN"), model)
        self.assertEqual(
            states,
            {
                "DRAFT",
                "SUBMITTED",
                "SIGNED",
                "DISBURSED",
                "DECLINED",
                "WITHDRAWN",
                "EXPIRED",
            },
        )

    def test_actor_mismatch_is_extra_and_does_not_cover(self):
        model, states = parse_model(self.fixture)
        events, ignored = parse_events(
            "DRAFT|SIGNED|SYSTEM|2\n"
            "SUBMITTED|SIGNED|GUARANTOR|1\n"
            "DRAFT|DRAFT|CLIENT|3\n|DRAFT|CLIENT|4\n"
        )
        report = render_report(model, states, events, ignored)
        self.assertIn("покрыто 1 из 7", report)
        self.assertIn("| DRAFT | SIGNED | SYSTEM | 2 |", report)
        self.assertIn("SIGNED", report.split("Тупики", 1)[1])
        self.assertEqual(ignored, 7)

    def test_unknown_actor_and_missing_table_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_model(self.fixture.replace("клиент", "неизвестный"))
        with self.assertRaises(ValueError):
            parse_model("## Диаграмма\nDRAFT --> SIGNED\n")
        with self.assertRaises(ValueError):
            parse_events("DRAFT|SIGNED|CLIENT|oops")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        raise SystemExit(main())
