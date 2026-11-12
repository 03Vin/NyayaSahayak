"""
Management command to seed demo citizen and administrator accounts.
Usage:
    python manage.py seed_demo
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Seeds demo citizen and staff superuser accounts for testing."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding NyayaSahayak Demo Accounts ==="))

        # 1. Demo Citizen User
        citizen_username = "citizen_demo"
        citizen_email = "citizen@example.com"
        citizen_pass = "DemoUser@123"

        citizen_user, created = User.objects.get_or_create(
            username=citizen_username,
            defaults={
                "email": citizen_email,
                "first_name": "Rohan",
                "last_name": "Sharma",
                "is_staff": False,
                "is_superuser": False
            }
        )
        citizen_user.set_password(citizen_pass)
        citizen_user.save()
        status_c = "Created new" if created else "Updated existing"
        self.stdout.write(self.style.SUCCESS(f" [PASS] {status_c} demo citizen: '{citizen_username}' / '{citizen_pass}'"))

        # 2. Demo Admin / Staff User
        admin_username = "admin"
        admin_email = "admin@nyayasahayak.gov.in"
        admin_pass = "NyayaAdmin@123"

        admin_user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                "email": admin_email,
                "first_name": "Nyaya",
                "last_name": "Administrator",
                "is_staff": True,
                "is_superuser": True
            }
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(admin_pass)
        admin_user.save()
        status_a = "Created new" if created else "Updated existing"
        self.stdout.write(self.style.SUCCESS(f" [PASS] {status_a} superuser/staff: '{admin_username}' / '{admin_pass}'"))

        self.stdout.write("\n" + "=" * 55)
        self.stdout.write(self.style.SUCCESS("Demo accounts ready for evaluation and web login!"))
        self.stdout.write(f"Citizen Login:  {citizen_username} / {citizen_pass}")
        self.stdout.write(f"Admin Login:    {admin_username} / {admin_pass}")

