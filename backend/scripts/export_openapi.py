import json
from pathlib import Path

from app.main import app


def main() -> None:
    output = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"
    output.write_text(
        json.dumps(app.openapi(), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
