from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from accounts.models import User
from records.models import Record, RecordMonthlyTransaction, RecordWithdrawal
from talukas.models import Taluka

TALUKAS = [
    ("Ardhapur", "ARD"),
    ("Bhokar", "BHO"),
    ("Biloli", "BIL"),
    ("Degloor", "DEG"),
    ("Dharmabad", "DHA"),
    ("Hadgaon", "HAD"),
    ("Himayatnagar", "HIM"),
    ("Kandhar", "KAN"),
    ("Kinwat", "KIN"),
    ("Loha", "LOH"),
    ("Mahoor", "MAH"),
    ("Mudkhed", "MUD"),
    ("Mukhed", "MUK"),
    ("Naigaon", "NAI"),
    ("Nanded", "NAN"),
    ("Umri", "UMR"),
]

RECORD_TEMPLATES = [
    (1, "land revenue inspection"),
    (2, "mutation / 7-12 extract follow-up"),
    (3, "public grievance redressal"),
    (4, "disaster preparedness checklist"),
    (5, "village revenue meeting minutes"),
]

GPF_SUBSCRIBERS = [
    ("Raj Kumar Sharma", "Raj Sharma", "2025001", "1965-03-15"),
    ("Priya Verma", "Priya Verma", "2025002", "1970-06-22"),
    ("Sanjay Patel", "Sanjay Patel", "2025003", "1968-11-10"),
    ("Anita Sharma", "Anita Sharma", "2025004", "1975-02-08"),
    ("Vijay Gopal", "Vijay Gopal", "2025005", "1972-09-14"),
]

SUPER_ADMIN_PASSWORD = "Admin@12345"
TAHSILDAR_PASSWORD = "Tahsildar@123"
USER_PASSWORD = "User@12345"


def slug_username(name: str) -> str:
    return name.lower().replace(" ", "")


class Command(BaseCommand):
    help = "Seed Nanded district demo talukas, users, and records (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding Nanded District Taluka Management demo data...")

        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@nanded.local",
                "first_name": "District",
                "last_name": "Administrator",
                "phone": "9000000000",
                "role": User.Role.SUPER_ADMIN,
                "taluka": None,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created:
            admin.set_password(SUPER_ADMIN_PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created super admin: admin"))
        else:
            admin.role = User.Role.SUPER_ADMIN
            admin.taluka = None
            admin.is_staff = True
            admin.is_superuser = True
            admin.email = admin.email or "admin@nanded.local"
            admin.save()
            self.stdout.write("Super admin already exists (not duplicating).")

        for name, code in TALUKAS:
            taluka, t_created = Taluka.objects.get_or_create(
                code=code,
                defaults={"name": name, "is_active": True},
            )
            if not t_created and taluka.name != name:
                taluka.name = name
                taluka.save(update_fields=["name"])
            slug = slug_username(name)

            tahsildar_username = f"{slug}.tahsildar"
            tahsildar, th_created = User.objects.get_or_create(
                username=tahsildar_username,
                defaults={
                    "email": f"{tahsildar_username}@nanded.local",
                    "first_name": name,
                    "last_name": "Tahsildar",
                    "phone": f"91{code[:3].ljust(3, '0')}00001"[:15],
                    "role": User.Role.TAHSILDAR,
                    "taluka": taluka,
                    "is_active": True,
                },
            )
            if th_created:
                tahsildar.set_password(TAHSILDAR_PASSWORD)
                tahsildar.save()
            else:
                tahsildar.role = User.Role.TAHSILDAR
                tahsildar.taluka = taluka
                tahsildar.is_active = True
                tahsildar.save()

            users = []
            for idx in range(1, 4):
                username = f"{slug}.user{idx}"
                user, u_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@nanded.local",
                        "first_name": name,
                        "last_name": f"User {idx}",
                        "phone": f"92{code[:3].ljust(3, '0')}000{idx}"[:15],
                        "role": User.Role.TALUKA_USER,
                        "taluka": taluka,
                        "is_active": True,
                    },
                )
                if u_created:
                    user.set_password(USER_PASSWORD)
                    user.save()
                else:
                    user.role = User.Role.TALUKA_USER
                    user.taluka = taluka
                    user.is_active = True
                    user.save()
                users.append(user)

            # Create records in various workflow states
            for seq, topic in RECORD_TEMPLATES:
                record_number = f"{code}-{seq:03d}"
                title = f"{name} Record {seq:03d}"
                description = (
                    f"Demo administrative record created for {name} Taluka "
                    f"({topic}). Record number {record_number}."
                )
                
                # Get GPF subscriber details (cycle through the list)
                gpf_subscriber = GPF_SUBSCRIBERS[seq % len(GPF_SUBSCRIBERS)]
                subscriber_name, employee_name, gpf_account_number, dob_str = gpf_subscriber
                
                record, r_created = Record.objects.get_or_create(
                    record_number=record_number,
                    defaults={
                        "taluka": taluka,
                        "created_by": users[seq % len(users)] if users else tahsildar,
                        "updated_by": users[seq % len(users)] if users else tahsildar,
                        "title": title,
                        "description": description,
                        "status": Record.Status.DRAFT,
                        "is_active": True,
                        # GPF Fields
                        "subscriber_name": subscriber_name,
                        "employee_name": employee_name,
                        "gpf_account_number": gpf_account_number,
                        "date_of_birth": dob_str,
                        "ddo_name": f"{name} DDO Office",
                        "ddo_code": code,
                        "department": "Revenue",
                        "treasury": "District Treasury",
                        "financial_year": "2025-2026",
                        "interest_rate": Decimal("10.50"),
                        "opening_balance": Decimal("150000.00"),
                        "total_deposit": Decimal("50000.00"),
                        "total_withdrawal": Decimal("10000.00"),
                        "interest_amount": Decimal("15750.00"),
                        "closing_balance": Decimal("205750.00"),
                        "amount_in_words": "Two lakh five thousand seven hundred fifty rupees only",
                    },
                )
                
                # Assign workflow states to different records for testing
                if r_created:
                    if seq == 1:
                        # Keep as DRAFT
                        pass
                    elif seq == 2:
                        # SUBMITTED
                        record.status = Record.Status.SUBMITTED
                    elif seq == 3:
                        # UNDER_REVIEW
                        record.status = Record.Status.UNDER_REVIEW
                        record.reviewed_by = tahsildar
                        record.reviewed_at = timezone.now()
                    elif seq == 4:
                        # CORRECTION_REQUIRED
                        record.status = Record.Status.CORRECTION_REQUIRED
                        record.reviewed_by = tahsildar
                        record.reviewed_at = timezone.now()
                        record.correction_comment = "Please review and correct the data."
                    elif seq == 5:
                        # APPROVED
                        record.status = Record.Status.APPROVED
                        record.reviewed_by = tahsildar
                        record.reviewed_at = timezone.now()
                        record.approved_by = tahsildar
                        record.approved_at = timezone.now()
                    
                    record.save()
                    
                    # Create sample monthly transactions for April to September
                    months = ["04/2025", "05/2025", "06/2025", "07/2025", "08/2025", "09/2025"]
                    for idx, month in enumerate(months):
                        RecordMonthlyTransaction.objects.get_or_create(
                            record=record,
                            month=month,
                            defaults={
                                "subscription": Decimal("8000.00") + (Decimal(idx * 100)),
                                "refund_of_withdrawals": Decimal("0.00") if idx % 2 == 0 else Decimal("500.00"),
                                "other_credit": Decimal("250.00") if idx % 3 == 0 else Decimal("0.00"),
                            },
                        )
                    
                    # Create sample withdrawal records
                    if seq in [2, 3, 5]:
                        withdrawal_date = timezone.now().date() - timedelta(days=30)
                        RecordWithdrawal.objects.get_or_create(
                            record=record,
                            withdrawal_amount=Decimal("10000.00"),
                            withdrawal_date=withdrawal_date,
                            defaults={
                                "withdrawal_type": "Regular",
                                "withdrawal_voucher_no": f"{code}-WD-{seq:03d}",
                                "remarks": "Regular withdrawal request",
                            },
                        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write(f"  Talukas: {Taluka.objects.count()}")
        self.stdout.write(
            f"  Tahsildars: {User.objects.filter(role=User.Role.TAHSILDAR).count()}"
        )
        self.stdout.write(
            f"  Taluka users: {User.objects.filter(role=User.Role.TALUKA_USER).count()}"
        )
        self.stdout.write(f"  Records: {Record.objects.count()}")
        self.stdout.write(f"  Monthly Transactions: {RecordMonthlyTransaction.objects.count()}")
        self.stdout.write(f"  Withdrawals: {RecordWithdrawal.objects.count()}")
        self.stdout.write(self.style.WARNING("DEMO passwords are for development only. Change them in production."))
