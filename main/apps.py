from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'main'

    def ready(self):
        from django.db.models.signals import post_migrate

        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
        from lexconnect import admin_config  # noqa: F401
        from .services.admin_user import ensure_lexconnect_admin_user

        def _sync_admin_user(sender, **kwargs):
            ensure_lexconnect_admin_user()

        post_migrate.connect(_sync_admin_user, sender=self)
