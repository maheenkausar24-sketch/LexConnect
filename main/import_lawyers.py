"""
Deprecated legacy import script.

Use instead:
    python generate_lawyers.py
    python manage.py import_lawyers_csv
    python manage.py prepare_demo
"""

raise SystemExit(
    "main/import_lawyers.py is deprecated and unsafe.\n"
    "Run: python generate_lawyers.py\n"
    "Or:  python manage.py import_lawyers_csv"
)
