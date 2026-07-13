"""Render config/*.template files using container environment variables."""

import os
from pathlib import Path
from string import Template


TEMPLATE_DIR = Path(os.environ.get("CONFIG_TEMPLATE_DIR", "/workspace/app/config"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/workspace/app/config"))


def main() -> None:
    if not TEMPLATE_DIR.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for template_path in TEMPLATE_DIR.glob("*.template"):
        target_path = CONFIG_DIR / template_path.with_suffix("").name
        target_path.write_text(
            Template(template_path.read_text(encoding="utf-8")).substitute(os.environ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
