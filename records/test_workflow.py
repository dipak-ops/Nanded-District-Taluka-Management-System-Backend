from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from records.models import Record, RecordHistory
from talukas.models import Taluka


class RecordWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_nanded", verbosity=0)
        cls.hadgaon = Taluka.objects.get(code="HAD")
        cls.tahsildar = User.objects.get(username="hadgaon.tahsildar")
        cls.user1 = User.objects.get(username="hadgaon.user1")
        cls.admin = User.objects.get(username="admin")

    def auth(self, username, password):
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"username": username, "password": password},
            format="json",
        )
        token = response.data.get("access")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_user_can_create_own_taluka_record(self):
        """Taluka user can create records in their own Taluka."""
        client = self.auth("hadgaon.user1", "User@12345")
        response = client.post(
            "/api/records/",
            {
                "title": "Test Record",
                "description": "Test Description",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], Record.Status.DRAFT)
        self.assertEqual(data["created_by_username"], "hadgaon.user1")

    def test_user_can_submit_draft_record(self):
        """User can submit a DRAFT record."""
        record = Record.objects.create(
            taluka=self.hadgaon,
            created_by=self.user1,
            updated_by=self.user1,
            record_number="HAD-997",
            title="Draft for Submission",
            description="Test",
            status=Record.Status.DRAFT,
        )
        
        client = self.auth("hadgaon.user1", "User@12345")
        response = client.post(
            f"/api/records/{record.id}/submit/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Record.Status.SUBMITTED)

    def test_tahsildar_can_review_submitted_record(self):
        """Tahsildar can start reviewing a SUBMITTED record."""
        record = Record.objects.create(
            taluka=self.hadgaon,
            created_by=self.user1,
            updated_by=self.user1,
            record_number="HAD-996",
            title="For Review",
            description="Test",
            status=Record.Status.SUBMITTED,
        )
        
        client = self.auth("hadgaon.tahsildar", "Tahsildar@123")
        response = client.post(
            f"/api/records/{record.id}/start_review/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Record.Status.UNDER_REVIEW)

    def test_tahsildar_can_approve_record(self):
        """Tahsildar can approve a record under review."""
        record = Record.objects.create(
            taluka=self.hadgaon,
            created_by=self.user1,
            updated_by=self.user1,
            record_number="HAD-994",
            title="For Approval",
            description="Test",
            status=Record.Status.UNDER_REVIEW,
            reviewed_by=self.tahsildar,
            reviewed_at=timezone.now(),
        )
        
        client = self.auth("hadgaon.tahsildar", "Tahsildar@123")
        response = client.post(
            f"/api/records/{record.id}/approve/",
            {"comment": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Record.Status.APPROVED)

    def test_super_admin_can_finalize_forwarded_record(self):
        """Super Admin can finalize a FORWARDED record."""
        record = Record.objects.create(
            taluka=self.hadgaon,
            created_by=self.user1,
            updated_by=self.user1,
            record_number="HAD-992",
            title="For Finalization",
            description="Test",
            status=Record.Status.FORWARDED,
            forwarded_by=self.tahsildar,
            forwarded_at=timezone.now(),
        )
        
        client = self.auth("admin", "Admin@12345")
        response = client.post(
            f"/api/records/{record.id}/finalize/",
            {"comment": "Finalized"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Record.Status.FINALIZED)

    def test_user_cannot_approve_record(self):
        """Regular user cannot approve records."""
        record = Record.objects.create(
            taluka=self.hadgaon,
            created_by=self.user1,
            updated_by=self.user1,
            record_number="HAD-991",
            title="Cannot Approve",
            description="Test",
            status=Record.Status.UNDER_REVIEW,
        )
        
        client = self.auth("hadgaon.user1", "User@12345")
        response = client.post(
            f"/api/records/{record.id}/approve/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
