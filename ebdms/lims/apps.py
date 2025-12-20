from django.apps import AppConfig


class LimsConfig(AppConfig):
    name = "lims"

    def ready(self):
        from . import signals  # noqa
