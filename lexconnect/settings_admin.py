"""
Settings for the dedicated LexConnect admin server (default port 9000).

Usage:
    python manage.py runadminserver
    # or
    python manage.py runserver 127.0.0.1:9000 --settings=lexconnect.settings_admin
"""

from .settings import *  # noqa: F403

ROOT_URLCONF = "lexconnect.urls_console"
