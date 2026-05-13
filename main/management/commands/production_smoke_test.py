from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse


class Command(BaseCommand):
    help = "Run low-risk production smoke checks against local Django routing and settings."

    def add_arguments(self, parser):
        parser.add_argument("--skip-deploy-check", action="store_true", help="Skip Django's check --deploy run.")

    def handle(self, *args, **options):
        if not options["skip_deploy_check"]:
            call_command("check", "--deploy")

        client = Client()
        request_kwargs = self.request_kwargs()
        checks = [
            self.check_route(client, "health_live", 200, request_kwargs),
            self.check_route(client, "health_ready", 200, request_kwargs),
            self.check_route(client, "home", 200, request_kwargs),
            self.check_security_headers(client, request_kwargs),
        ]
        failed = [check for check in checks if check["status"] != "ok"]
        for check in checks:
            self.stdout.write(f"{check['name']}: {check['status']} {check.get('detail', '')}".strip())
        if failed:
            raise CommandError(f"{len(failed)} smoke check(s) failed.")
        self.stdout.write(self.style.SUCCESS("Production smoke test passed."))

    def request_kwargs(self):
        allowed_host = next((host for host in settings.ALLOWED_HOSTS if host not in {"*", ".localhost"}), "testserver")
        return {"secure": bool(settings.SECURE_SSL_REDIRECT), "HTTP_HOST": allowed_host}

    def check_route(self, client, route_name, expected_status, request_kwargs):
        path = reverse(route_name)
        response = client.get(path, **request_kwargs)
        if response.status_code != expected_status:
            return {
                "name": route_name,
                "status": "error",
                "detail": f"expected {expected_status}, got {response.status_code}",
            }
        return {"name": route_name, "status": "ok", "detail": path}

    def check_security_headers(self, client, request_kwargs):
        response = client.get(reverse("home"), **request_kwargs)
        required_headers = [
            "Content-Security-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
            "Permissions-Policy",
            "X-Content-Type-Options",
        ]
        missing = [header for header in required_headers if header not in response.headers]
        if missing:
            return {"name": "security_headers", "status": "error", "detail": f"missing {', '.join(missing)}"}
        return {"name": "security_headers", "status": "ok"}
