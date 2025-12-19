from django.apps import AppConfig


class BiobankConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'biobank'

    def ready(self):
        from . import signals  # noqa
