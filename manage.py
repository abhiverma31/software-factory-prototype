#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


def factory_status_is_running():
    status_file = Path(__file__).resolve().parent / "factory_status.json"
    if not status_file.exists():
        return False

    try:
        return json.loads(status_file.read_text(encoding="utf-8")).get("state") == "running"
    except (OSError, json.JSONDecodeError):
        return False


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

    should_reset_demo = (
        len(sys.argv) > 1
        and sys.argv[1] == "runserver"
        and os.environ.get("RUN_MAIN") != "true"
        and os.environ.get("SOFTWARE_FACTORY_SKIP_RESET") != "1"
        and not factory_status_is_running()
    )
    if should_reset_demo:
        from software_factory.demo_reset import reset_demo_state

        reset_demo_state()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

