from django.db.models import Q, Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from records.models import Record
from talukas.models import Taluka
from accounts.permissions import IsTahsildar, IsSuperAdmin


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard endpoints for different roles."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def tahsildar_dashboard(self, request):
        """Get Tahsildar dashboard with record statistics."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this dashboard.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        # Get all records for this Taluka
        records = Record.objects.filter(taluka_id=user.taluka_id, is_active=True)
        
        dashboard_data = {
            "taluka": {
                "id": user.taluka.id,
                "name": user.taluka.name,
                "code": user.taluka.code,
            },
            "users": User.objects.filter(
                taluka_id=user.taluka_id,
                role=User.Role.TALUKA_USER,
                is_active=True
            ).count(),
            "status_counts": {
                "draft": records.filter(status=Record.Status.DRAFT).count(),
                "submitted": records.filter(status=Record.Status.SUBMITTED).count(),
                "under_review": records.filter(status=Record.Status.UNDER_REVIEW).count(),
                "correction_required": records.filter(status=Record.Status.CORRECTION_REQUIRED).count(),
                "approved": records.filter(status=Record.Status.APPROVED).count(),
                "forwarded": records.filter(status=Record.Status.FORWARDED).count(),
                "finalized": records.filter(status=Record.Status.FINALIZED).count(),
            },
            "total_records": records.count(),
        }
        
        return Response(dashboard_data)

    @action(detail=False, methods=["get"])
    def super_admin_dashboard(self, request):
        """Get Super Admin dashboard with global statistics."""
        user = request.user
        
        if not user.is_super_admin:
            raise PermissionDenied("Only Super Admin can view this dashboard.")
        
        # Get all active records
        records = Record.objects.filter(is_active=True)
        
        # Get Taluka-wise statistics
        taluka_stats = []
        for taluka in Taluka.objects.filter(is_active=True):
            taluka_records = records.filter(taluka=taluka)
            taluka_stats.append({
                "taluka_id": taluka.id,
                "taluka_name": taluka.name,
                "taluka_code": taluka.code,
                "total_records": taluka_records.count(),
                "draft": taluka_records.filter(status=Record.Status.DRAFT).count(),
                "submitted": taluka_records.filter(status=Record.Status.SUBMITTED).count(),
                "under_review": taluka_records.filter(status=Record.Status.UNDER_REVIEW).count(),
                "correction_required": taluka_records.filter(status=Record.Status.CORRECTION_REQUIRED).count(),
                "approved": taluka_records.filter(status=Record.Status.APPROVED).count(),
                "forwarded": taluka_records.filter(status=Record.Status.FORWARDED).count(),
                "finalized": taluka_records.filter(status=Record.Status.FINALIZED).count(),
            })
        
        dashboard_data = {
            "global_stats": {
                "total_talukas": Taluka.objects.filter(is_active=True).count(),
                "total_tahsildars": User.objects.filter(
                    role=User.Role.TAHSILDAR,
                    is_active=True
                ).count(),
                "total_users": User.objects.filter(
                    role=User.Role.TALUKA_USER,
                    is_active=True
                ).count(),
                "total_records": records.count(),
            },
            "status_counts": {
                "draft": records.filter(status=Record.Status.DRAFT).count(),
                "submitted": records.filter(status=Record.Status.SUBMITTED).count(),
                "under_review": records.filter(status=Record.Status.UNDER_REVIEW).count(),
                "correction_required": records.filter(status=Record.Status.CORRECTION_REQUIRED).count(),
                "approved": records.filter(status=Record.Status.APPROVED).count(),
                "forwarded": records.filter(status=Record.Status.FORWARDED).count(),
                "finalized": records.filter(status=Record.Status.FINALIZED).count(),
            },
            "taluka_wise_stats": taluka_stats,
        }
        
        return Response(dashboard_data)
