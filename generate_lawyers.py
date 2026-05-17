#!/usr/bin/env python
"""
Import demo lawyers from lawyers.csv into the LexConnect database.

Usage:
    python generate_lawyers.py              # import/update lawyers from CSV
    python generate_lawyers.py --with-slots # also seed availability for demo lawyers
    python generate_lawyers.py --regenerate-csv  # overwrite lawyers.csv (not recommended)
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lexconnect.settings")

import django

django.setup()

from django.conf import settings
from django.db import transaction

from main.models import Lawyer, LawyerAvailability
from main.services.auth import COMMON_DEMO_LAWYER_PASSWORD, reset_all_lawyer_accounts
from main.services.lawyer_import import find_lawyer_csv, import_lawyers_from_csv

DEMO_SLOT_TEMPLATES = [
    [(0, time(9, 0), time(17, 0)), (1, time(9, 0), time(17, 0)), (2, time(9, 0), time(17, 0))],
    [(3, time(9, 0), time(17, 0)), (4, time(9, 0), time(17, 0)), (5, time(10, 0), time(16, 0))],
    [(6, time(10, 0), time(16, 0)), (0, time(14, 0), time(18, 0)), (1, time(14, 0), time(18, 0))],
    [(2, time(9, 30), time(17, 30)), (3, time(9, 30), time(17, 30)), (4, time(9, 30), time(17, 30))],
    [(5, time(10, 0), time(15, 0)), (6, time(10, 0), time(15, 0)), (0, time(10, 0), time(15, 0))],
]


def regenerate_csv(csv_path: Path) -> None:
    names = ["Rahul", "Anita", "Arjun", "Priya", "Vikram", "Sneha", "Rohit", "Kavya", "Manoj", "Pooja"]
    surnames = ["Sharma", "Rao", "Mehta", "Nair", "Singh", "Patil", "Verma", "Shetty", "Kumar", "Jain"]
    specializations = [
        "Criminal Law",
        "Civil Law",
        "Corporate Law",
        "Family Law",
        "Cyber Law",
        "Property Law",
    ]
    locations = [
        "Bangalore",
        "Mysore",
        "Hubli",
        "Mangalore",
        "Delhi",
        "Mumbai",
        "Chennai",
        "Hyderabad",
        "Kolkata",
        "Pune",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "email", "phone", "specialization", "experience", "location"])
        for index in range(1, 121):
            name = f"{random.choice(names)} {random.choice(surnames)}"
            writer.writerow(
                [
                    name,
                    f"lawyer{index}@gmail.com",
                    "9" + str(random.randint(100000000, 999999999)),
                    random.choice(specializations),
                    random.randint(2, 15),
                    random.choice(locations),
                ]
            )
    print(f"Regenerated CSV: {csv_path}")


def seed_demo_availability(lawyers: list[Lawyer]) -> tuple[int, int]:
    created = 0
    updated = 0
    for index, lawyer in enumerate(lawyers):
        template = DEMO_SLOT_TEMPLATES[index % len(DEMO_SLOT_TEMPLATES)]
        for weekday, start_time, end_time in template:
            slot, was_created = LawyerAvailability.objects.get_or_create(
                lawyer=lawyer,
                weekday=weekday,
                start_time=start_time,
                end_time=end_time,
                defaults={"is_active": True, "slot_duration_minutes": 30},
            )
            if was_created:
                created += 1
                continue
            changed = False
            if not slot.is_active:
                slot.is_active = True
                changed = True
            if slot.slot_duration_minutes != 30:
                slot.slot_duration_minutes = 30
                changed = True
            if changed:
                slot.save(update_fields=["is_active", "slot_duration_minutes", "updated_at"])
                updated += 1
    return created, updated


def print_summary(summary) -> None:
    print("")
    print("=" * 60)
    print("LexConnect lawyer seed complete")
    print("=" * 60)
    print(f"CSV file:           {summary.path}")
    print(f"Rows processed:     {summary.total_processed}")
    print(f"Lawyers created:    {summary.created}")
    print(f"Lawyers updated:    {summary.updated}")
    print(f"Rows skipped:       {summary.skipped}")
    print(f"Visible to clients: {Lawyer.objects.visible_to_clients().count()}")
    print(f"Demo password:      {COMMON_DEMO_LAWYER_PASSWORD}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed LexConnect demo lawyers from lawyers.csv")
    parser.add_argument("--regenerate-csv", action="store_true", help="Overwrite lawyers.csv before import")
    parser.add_argument("--with-slots", action="store_true", help="Seed wide weekly availability for the first 5 demo lawyers")
    parser.add_argument("--path", default="", help="Optional CSV path")
    args = parser.parse_args()

    csv_path = Path(args.path) if args.path else find_lawyer_csv(settings.BASE_DIR)
    if args.regenerate_csv:
        target = csv_path or (settings.BASE_DIR / "lawyers.csv")
        regenerate_csv(target)
        csv_path = target

    if csv_path is None or not csv_path.exists():
        print("ERROR: lawyers.csv not found. Place it in the project root or pass --path.")
        return 1

    print(f"Importing lawyers from {csv_path} ...")

    with transaction.atomic():
        summary = import_lawyers_from_csv(settings.BASE_DIR, csv_path=csv_path)
        reset_count = len(reset_all_lawyer_accounts())
        print(f"Reset passwords for {reset_count} lawyer account(s).")

        slot_created = slot_updated = 0
        if args.with_slots:
            demo_lawyers = list(Lawyer.objects.visible_to_clients().order_by("id")[:5])
            if len(demo_lawyers) < 1:
                print("WARNING: No visible lawyers found; availability slots were not seeded.")
            else:
                slot_created, slot_updated = seed_demo_availability(demo_lawyers)
                print(f"Availability slots created: {slot_created}, reactivated: {slot_updated}")

    print_summary(summary)
    print("")
    print("Next steps:")
    print("  python manage.py runserver")
    print("  Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/demo-accounts/")
    if not args.with_slots:
        print("  Optional: python generate_lawyers.py --with-slots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
