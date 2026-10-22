#!/usr/bin/env bash
# Хук SessionStart: на старте, после /clear и после сжатия контекста
# подставляет текущее состояние проекта, чтобы оно не потерялось.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if [ -f docs/STATE.md ]; then
  echo "Текущее состояние проекта из docs/STATE.md (источник правды после сжатия контекста):"
  echo
  head -n 80 docs/STATE.md
else
  echo "docs/STATE.md ещё нет: проект на этапе 0."
fi
exit 0
