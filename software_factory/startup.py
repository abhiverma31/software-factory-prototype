import os
import sys


RESET_DONE_ENV = "SOFTWARE_FACTORY_STARTUP_RESET_DONE"


def maybe_reset_demo_on_runserver_start():
    if os.environ.get("SOFTWARE_FACTORY_SKIP_RESET") == "1":
        return

    if os.environ.get(RESET_DONE_ENV) == "1":
        return

    if "runserver" not in sys.argv:
        return

    if os.environ.get("RUN_MAIN") == "true":
        return

    from software_factory.demo_reset import reset_demo_state

    reset_demo_state()
    os.environ[RESET_DONE_ENV] = "1"
