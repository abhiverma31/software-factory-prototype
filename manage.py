#!/usr/bin/env python3
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "software_factory.settings")

    from software_factory.startup import maybe_reset_demo_on_runserver_start

    maybe_reset_demo_on_runserver_start()

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
