import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from main.services.operations import health_report, runtime_configuration_summary


class Command(BaseCommand):
    help = "Print sanitized runtime diagnostics for production deployment verification."

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-warning", action="store_true", help="Return a non-zero exit code when warnings are present.")

    def handle(self, *args, **options):
        diagnostics = {
            "runtime": runtime_configuration_summary(),
            "health": health_report(),
            "cache_roundtrip": self.cache_roundtrip(),
            "channel_layer_roundtrip": self.channel_layer_roundtrip(),
        }
        warnings = self.warnings(diagnostics)
        diagnostics["warnings"] = warnings
        self.stdout.write(json.dumps(diagnostics, indent=2, sort_keys=True, default=str))
        if diagnostics["health"]["status"] == "error":
            raise CommandError("Deployment diagnostics found health errors.")
        if warnings and options["fail_on_warning"]:
            raise CommandError("Deployment diagnostics found warnings.")

    def cache_roundtrip(self):
        key = "diagnostics:cache"
        value = "ok"
        try:
            cache.set(key, value, timeout=30)
            return {"status": "ok" if cache.get(key) == value else "error"}
        except Exception as exc:
            return {"status": "error", "detail": exc.__class__.__name__}

    def channel_layer_roundtrip(self):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return {"status": "error", "detail": "no channel layer configured"}
        try:
            channel_name = async_to_sync(channel_layer.new_channel)("diagnostics")
            async_to_sync(channel_layer.send)(channel_name, {"type": "diagnostics.message", "status": "ok"})
            message = async_to_sync(channel_layer.receive)(channel_name)
            return {"status": message.get("status", "error"), "backend": channel_layer.__class__.__name__}
        except Exception as exc:
            return {"status": "error", "backend": channel_layer.__class__.__name__, "detail": exc.__class__.__name__}

    def warnings(self, diagnostics):
        warnings = []
        runtime = diagnostics["runtime"]
        if runtime["debug"]:
            warnings.append("DEBUG is enabled.")
        if runtime["database_engine"] == "django.db.backends.sqlite3":
            warnings.append("SQLite is configured; use PostgreSQL for production.")
        if runtime["channel_layer"] == "InMemoryChannelLayer":
            warnings.append("In-memory channel layer cannot support multi-process websocket deployments.")
        if runtime["cache_backend"] == "django.core.cache.backends.locmem.LocMemCache":
            warnings.append("Local memory cache weakens shared rate limits and readiness checks.")
        if runtime["celery_eager"]:
            warnings.append("Celery eager mode is enabled; workers are not being exercised.")
        if runtime["demo_accounts_enabled"]:
            warnings.append("Demo account page is enabled.")
        if diagnostics["channel_layer_roundtrip"]["status"] != "ok":
            warnings.append("Channel layer roundtrip failed.")
        if diagnostics["cache_roundtrip"]["status"] != "ok":
            warnings.append("Cache roundtrip failed.")
        return warnings
