#!/usr/bin/env python3
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

    should_reset_demo = (
        len(sys.argv) > 1
        and sys.argv[1] == "runserver"
        and os.environ.get("RUN_MAIN") != "true"
        and os.environ.get("SOFTWARE_FACTORY_SKIP_RESET") != "1"
    )
    if should_reset_demo:
        from software_factory.demo_reset import reset_demo_state

        reset_demo_state()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
