from django.apps import AppConfig


class FactoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "factory"

    def ready(self):
        from software_factory.startup import maybe_reset_demo_on_runserver_start

        maybe_reset_demo_on_runserver_start()
